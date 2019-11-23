import sys
from collections import defaultdict
from itertools import permutations, combinations_with_replacement
import data_import
from v2_compare_prices import get_pct_savings


class PriceEstimator:
    def __init__(self, token, ex_ts_prices, ex_known_liquidity):

        # Since DEX.AG uses 'Radar Relay' we never get any price quotes for 0xMesh, which is used in Totle and
        # Paradex swaps. So we create a 0xMesh price curve based on Radar's prices
        if 'Radar Relay' in ex_ts_prices:
            ex_ts_prices['0xMesh'] = ex_ts_prices['Radar Relay'].copy()
            ex_known_liquidity['0xMesh'] = ex_known_liquidity['Radar Relay']

        self.token = token
        self.ex_known_liquidity = ex_known_liquidity
        self.num_price_points = { ex: len(ts_prices) for ex, ts_prices in ex_ts_prices.items()}

        # get the set of dexs and price_funcs (currently used only to set self.base_price)
        self.all_dexs, self.price_funcs = set(), {}
        for ex, ts_prices in ex_ts_prices.items():
            self.all_dexs.add(ex)
            if len(ts_prices) == 0: print(f"WARNING: no ts_prices for {token} {ex} all prices will be infinite")
            self.price_funcs[ex] = self.get_price_func(ts_prices)
        self.all_dexs = sorted(self.all_dexs)

        # set the base price
        self.base_price = float('inf')
        # Old base price was just the lowest price sample
        # for ex, ts_prices in ex_ts_prices.items():
        #     for trade_size, price in ts_prices.items():
        #         self.base_price = min(self.base_price, price)

        for ex, pf in self.price_funcs.items():
            self.base_price = min(self.base_price, pf(0.01))

        # create the absolute and normalized slippage price matrices based on base_price
        self.absolute_prices = defaultdict(dict)
        for ex, ts_prices in ex_ts_prices.items():
            for trade_size, price in ts_prices.items():
                self.absolute_prices[float(trade_size)][ex] = price
                # self.normalized_slippage_prices[float(trade_size)][ex] = (price - self.base_price) / self.base_price
                # if token == 'GNO' and ex == 'Kyber':
                #     print(f"{ex} {token} {trade_size} price={price} np={(price - self.base_price) / self.base_price}")

    @classmethod
    def construct(cls, token, ts_ex_pscs):
        """Returns a PriceEstimator by converting the given pscs into prices"""
        ex_ts_prices = defaultdict(lambda: defaultdict(dict))
        for ts, ex_pscs in ts_ex_pscs.items():
            for ex, pscs in ex_pscs.items():
                ex_ts_prices[ex][ts] = first_price(pscs)
        return cls(token, ex_ts_prices)

    def __repr__(self):
        return f"CostEstimator<{self.token}>[{self.all_dexs}]"

    def is_better(self, candidate, best_candidate, delta=0.0):
        """Returns True of the best_candidate is falsey or the price of candidate is lower than best_candidate"""
        if not best_candidate: return True
        return self.solution_cost(candidate) + delta < self.solution_cost(best_candidate)

    def dexs_ranked_by_cost(self, target_trade_size):
        sorted_dex_costs = sorted([ (self.get_slippage_cost(ex, target_trade_size), ex) for ex in self.all_dexs ])
        sorted_dexs = [dc[1] for dc in sorted_dex_costs]
        # print(f"sorted_dex_costs={sorted_dex_costs}")
        return sorted_dexs

    def compare_costs(self, label, baseline, candidate):
        baseline = dict(sorted(baseline.items()))
        candidate = dict(sorted(candidate.items()))

        baseline_cost = self.solution_cost(baseline)
        candidate_cost = self.solution_cost(candidate)
        savings = baseline_cost - candidate_cost  # will be positive if candidate is a better solution
        savings_pct = 0.0 if baseline_cost == 0 else get_pct_savings(candidate_cost, baseline_cost)
        print(f"{label}: saved {savings:.4f} ETH ({savings_pct:.2f}%)\n\tcandidate: {candidate} -> {candidate_cost}\n\tbaseline:  {baseline} -> {baseline_cost:.4f}")
        print(f"    In percent allocations:\n\tcandidate: {to_percentages(candidate)} -> {candidate_cost}\n\tbaseline:  {to_percentages(baseline)} -> {baseline_cost:.4f}")

    def destination_amount(self, solution, infinite_liquidity=False):
        for ex, ts in solution.items():
            abs_price = self.get_absolute_price(ex,ts,infinite_liquidity=infinite_liquidity)
            normz_price = self.base_price + self.base_price * self.get_normalized_price(ex, ts, infinite_liquidity=infinite_liquidity)
            if abs(normz_price - abs_price) > 0.00001:
                print(f"destination_amount({solution}, inf_liq={infinite_liquidity}) PRICE DISCREPENCY: {ex} {ts} abs_price={abs_price} normz_price={normz_price} abs_price - normz price = {abs_price-normz_price:.6f} self.base_price={self.base_price}")

        # All of the above is just a check, this function is a one-liner
        return sum([ ts / self.get_absolute_price(ex,ts,infinite_liquidity=infinite_liquidity) for ex, ts in solution.items()])

    def solution_cost(self, solution, infinite_liquidity=False):
        sum_cost = 0.0
        for ex, ts in solution.items():
            sum_cost += self.get_slippage_cost(ex, ts, infinite_liquidity=infinite_liquidity)
        return sum_cost

    def get_slippage_cost(self, ex, ts, infinite_liquidity=False):
        # Assumption is that interpolating between two known data points is more accurate than interpolating off the
        # least squares line, especially when prices jump at certain trade sizes (as happens on 0x and Kyber)
        # return ts * self.get_ls_normalized_slippage_price(ex, ts)
        return ts * self.get_normalized_price(ex, ts, infinite_liquidity=infinite_liquidity)

    def get_normalized_price(self, ex, ts, infinite_liquidity=False):
        abs_price = self.get_absolute_price(ex, ts, infinite_liquidity=infinite_liquidity)
        return (abs_price - self.base_price) / self.base_price
        # return self.get_price_from(self.normalized_slippage_prices, ex, ts, infinite_liquidity=infinite_liquidity)

    def get_absolute_price(self, ex, ts, infinite_liquidity=False):
        ts = float(ts) # self.absolute_prices was created with float keys
        if ts == 0: return 0
        if self.absolute_prices.get(ts) and ex in self.absolute_prices[ts]: return self.absolute_prices[ts][ex]
        return self.interpolate_price(ex, ts, self.absolute_prices, infinite_liquidity=infinite_liquidity)

    # TODO now that we have known_liquidty, remove infinite_liquidity
    def interpolate_price(self, ex, ts, matrix, infinite_liquidity=False):
        lower_ts, higher_ts = 0.0, float('inf')
        ex_trade_sizes = [ets for ets in matrix.keys() if matrix[ets].get(ex)]
        for trade_size in ex_trade_sizes:
            if matrix[trade_size].get(ex):
                if trade_size < ts and trade_size > lower_ts:
                    lower_ts = trade_size
                if trade_size > ts and trade_size < higher_ts:
                    higher_ts = trade_size

        if higher_ts == float('inf'):
            if len(ex_trade_sizes) > 1:
                # return self.get_ls_price(ex, ts)
                # use the slope between the closest 2 samples to estimate price
                t1, t2 = ex_trade_sizes[-2:]
                if not infinite_liquidity: # extend only to known_liquidity for ex
                    if ts > self.ex_known_liquidity[ex] : return float('inf')

                dydx = (matrix[t2][ex] - matrix[t1][ex]) / (t2 - t1)
                return matrix[t2][ex] + ((ts - t2) * dydx)
            else:
                # return self.get_ls_normalized_slippage_price(ex, ts) <- only works when matrix is normalized
                return float('inf')  # <- This is the behavior optimal solutions were based on

        l_price = self.base_price if lower_ts == 0.0 else matrix[lower_ts][ex]
        h_price = matrix[higher_ts][ex]

        frac = (ts - lower_ts) / (higher_ts - lower_ts)
        # print(f"\tinterpolate_price lower_ts={lower_ts} higher_ts={higher_ts} l_price={l_price} h_price={h_price} frac={frac:.4f}")
        return l_price + frac * (h_price - l_price)

    def get_price_func(self, ts_prices):
        if len(ts_prices) == 0:  # no prices, so return a func that ensures this DEX won't be used
            print(f"WARNING: len(ts_prices) == 0")
            return lambda ts: float('inf')
        elif len(ts_prices) == 1:  # one prices, so return a func that returns that one price
            one_ts, one_price = list(ts_prices.items())[0]
            return lambda ts: one_price if float(ts) == one_ts else float('inf')
        else:  # return a func based on least squares
            slope, intercept = self.least_squares(ts_prices)
            return lambda ts: slope * ts + intercept

    def least_squares(self, ts_prices):
        # number of observations/points
        n_samples = len(ts_prices)

        mean_ts, mean_price = sum(ts_prices.keys()) / n_samples, sum(ts_prices.values()) / n_samples

        # calculating cross-deviation and deviation about x
        SS_xy = sum([x * y for x, y in ts_prices.items()]) - n_samples * mean_price * mean_ts
        SS_xx = sum([x * x for x, _ in ts_prices.items()]) - n_samples * mean_ts * mean_ts

        # calculating regression coefficients
        slope = SS_xy / SS_xx
        intercept = mean_price - slope * mean_ts

        return slope, intercept

    # used to compare price_funcs with interpolated
    def get_ls_normalized_slippage_price(self, ex, ts):
        if ts == 0: return 0
        return (self.get_ls_price(ex, ts) - self.base_price) / self.base_price

    def get_ls_price(self, ex, ts):
        return self.price_funcs[ex](ts)


def to_percentages(solution):
    """Converts a solution in ETH allocations to percent allocations (percents are rounded and not guaranteed to add up to 100)"""
    trade_size = sum(solution.values())
    return {x: round(100 * t/trade_size) for x, t in solution.items()}

def to_trade_size_allocations(solution, trade_size, precision=4):
    """Converts a solution in percentages to ETH allocations (allocations are rounded and not guaranteed to add up to trade_size)"""
    return {x: round(trade_size * t / 100, precision) for x, t in solution.items()}

# although the hi-res matrix has fractional trade size allocations (from 0.0 to 2.0) these rarely add up to an exact
# target trade size like 20.0 so we're more likely to find a whole number solution because we try more whole number solutions
# With tracing enabled we do see fractional allocation candidates temporarily winning e.g.
# new best {'Bancor': 1.2, '0xMesh': 1.8, 'Uniswap': 3.0, 'Kyber': 14.0} cost=0.0483389230307891
# but then beaten by a whole number solution like
# WINNER {'Bancor': 1.0, 'Uniswap': 3.0, '0xMesh': 4.0, 'Kyber': 12.0} cost=0.04747026247667824

OPTIMAL_SOLUTIONS = {
    5.0:  {'0xMesh': 0.8, 'Bancor': 0.9, 'Kyber': 1.4, 'Uniswap': 1.9},
    10.0: {'0xMesh': 0.6, 'Bancor': 0.8, 'Kyber': 7, 'Uniswap': 1.6},
    15.0: {'0xMesh': 4.0, 'Bancor': 1.0, 'Kyber': 8.0, 'Uniswap': 2.0},
    20.0: {'0xMesh': 4, 'Bancor': 1.0, 'Kyber': 12, 'Uniswap': 3},
    25.0: {'0xMesh': 4.0, 'Bancor': 1.0, 'Kyber': 17.0, 'Uniswap': 3.0},
    30.0: {'0xMesh': 5, 'Bancor': 1.3, 'Kyber': 20, 'Radar Relay': 0.7, 'Uniswap': 3},
    35.0: {'0xMesh': 6.0, 'Bancor': 1.0, 'Kyber': 20.0, 'Radar Relay': 4.0, 'Uniswap': 4.0},
    40.0: {'0xMesh': 7.0, 'Bancor': 2.0, 'Kyber': 20.0, 'Radar Relay': 7.0, 'Uniswap': 4.0},  # coincidentally same for both hi-res and low-res
    45.0: {'0xMesh': 8.0, 'Bancor': 2.0, 'Kyber': 20.0, 'Radar Relay': 10.0, 'Uniswap': 5.0},
    50.0: {'0xMesh': 10.0, 'Bancor': 2.0, 'Kyber': 23.0, 'Radar Relay': 10.0, 'Uniswap': 5.0},
    55.0: {'0xMesh': 10.0, 'Bancor': 2.0, 'Kyber': 27.0, 'Radar Relay': 10.0, 'Uniswap': 6.0},
    60.0: {'0xMesh': 10.0, 'Bancor': 3.0, 'Kyber': 30.0, 'Radar Relay': 10.0, 'Uniswap': 7.0}, # coincidentally same for both hi-res and low-res
    65.0: {'0xMesh': 10.0, 'Bancor': 3.0, 'Kyber': 32.0, 'Radar Relay': 11.0, 'Uniswap': 9.0},
    70.0: {'0xMesh': 11.0, 'Bancor': 3.0, 'Kyber': 35.0, 'Radar Relay': 12.0, 'Uniswap': 9.0},
    80.0: {'0xMesh': 10.0, 'Bancor': 3.0, 'Kyber': 50.0, 'Radar Relay': 10.0, 'Uniswap': 7.0},
    85.0: {'0xMesh': 11.0, 'Bancor': 3.0, 'Kyber': 50.0, 'Radar Relay': 12.0, 'Uniswap': 9.0},
    90.0: {'0xMesh': 12.0, 'Bancor': 4.0, 'Kyber': 50.0, 'Radar Relay': 14.0, 'Uniswap': 10.0},
    95.0: {'0xMesh': 14.0, 'Bancor': 4.0, 'Kyber': 50.0, 'Radar Relay': 15.0, 'Uniswap': 12.0}
}


def enumerate_solutions(target_trade_size, price_estimator, dexs, max_ways=None):
    """Evaluates solutions of the form { 'Bancor': 12, 'Kyber': 8 } """
    hi_res_price_matrix = get_hi_res_price_matrix(price_estimator)
    trade_sizes = [sts for sts in hi_res_price_matrix.keys() if sts <= target_trade_size]
    max_ways = max_ways or len(dexs)
    best, winner = [{}]*(max_ways+1), None
    sol_cost = lambda solution: price_estimator.solution_cost(solution)

    for n in range(1, len(best)):
        # print(f"enumerate_solutions: computing the best {n}-DEX splits")
        for dex_combos in permutations(dexs, n): # groups of n unique dexs
            for ts_combos in combinations_with_replacement(trade_sizes, n): # groups of n trade sizes (including duplicates)
                if sum(ts_combos) == target_trade_size:
                    candidate_solution = dict(zip(dex_combos, ts_combos))
                    candidate_cost = sol_cost(candidate_solution)
                    if not best[n] or candidate_cost < sol_cost(best[n]):
                        best[n] = candidate_solution
                        if not winner or candidate_cost < sol_cost(winner):
                            winner = candidate_solution

    return winner, best


def get_hi_res_price_matrix(price_estimator, max_trade_size=100):
    ts_ex_prices = defaultdict(dict)
    # do 0.1 ETH granularity up to trade_size = 2
    for i in range(1, 10*min(max_trade_size, 2)):
        ts = i / 10
        for ex in price_estimator.all_dexs:
            ts_ex_prices[ts][ex] = price_estimator.get_normalized_price(ex, ts)

    for i in range(2, int(max_trade_size)+1):
        ts = round(float(i),1)
        for ex in price_estimator.all_dexs:
            ts_ex_prices[ts][ex] = price_estimator.get_normalized_price(ex, ts)

    return ts_ex_prices


########################################################################################################################
# optimization algorithms

def run_optimization_algorithms(token, ts_ex_pscs, target_trade_sizes, delta=0.005):
    _, sorted_dex_names, _ = extract(ts_ex_pscs)

    price_estimator = PriceEstimator.construct(token, ts_ex_pscs)

    for target_trade_size in target_trade_sizes:
        baseline, _ = enumerate_solutions(target_trade_size, price_estimator, sorted_dex_names, max_ways=1)
        optimal = OPTIMAL_SOLUTIONS.get(target_trade_size)
        if not optimal: raise ValueError(f"target_trade_size={target_trade_size} but we only have solutions for trade sizes {list(OPTIMAL_SOLUTIONS.keys())}")

        print(f"\n\nBest splits for a target trade size of {target_trade_size}")
        # greedy_winner, greedy_best, best_steps = greedy_solutions(target_trade_size, price_estimator, sorted_dex_names)
        branch_winner = branch_and_bound_solutions(target_trade_size, price_estimator, delta=delta)
        # rebalancing_branch_winner = rebalancing_branch_and_bound_solutions(target_trade_size, price_estimator, sorted_dex_names)

        # price_estimator.compare_costs(f"Optimal", baseline, optimal)
        # price_estimator.compare_costs(f"Greedy ({best_steps} steps)", baseline, greedy_winner)
        # price_estimator.compare_costs(f"Greedy ({best_steps} steps) vs optimal", optimal, greedy_winner)
        price_estimator.compare_costs(f"Basic Branch (delta={delta})", baseline, branch_winner)
        price_estimator.compare_costs(f"Basic Branch (delta={delta}) vs optimal", optimal, branch_winner)
        # price_estimator.compare_costs(f"Rebalancing Branch vs optimal", optimal, rebalancing_branch_winner)
        # price_estimator.compare_costs(f"Rebalancing Branch vs Basic Branch", branch_winner, rebalancing_branch_winner)


def branch_and_bound_solutions(target_trade_size, price_estimator, delta=0.005, exclude_dexs=[], precision=4):
    """Performs the branch and bound algorithm on all dexs not in exclude_dexs, adding DEXs that lower cost by more than delta"""

    # get a ranking of dexs by lowest cost at target_trade_size
    sorted_dexs = price_estimator.dexs_ranked_by_cost(target_trade_size)
    if exclude_dexs: sorted_dexs = [d for d in sorted_dexs if d not in exclude_dexs]

    # start with baseline candidate: 1 DEX with the lowest cost at target_trade_size
    best_new_candidate = {sorted_dexs[0]: target_trade_size}
    # print(f"baseline={best_new_candidate} sorted_dexs[1:]={sorted_dexs[1:]}")

    # loop over remaining DEXs adding some amount of each as long as cost gets lower
    for ex in sorted_dexs[1:]:
        best_for_ex = None
        # Iterate over all i because the slippage cost function has multiple local minima
        for i in range(1,100):
            frac = i/100
            # create a new candidate with frac allocated to ex and (1 - frac) allocated to DEXs in existing solution
            new_candidate = { e: round(t*(1-frac),precision) for e,t in best_new_candidate.items() }
            new_alloc = round(target_trade_size - sum(new_candidate.values()), precision)
            new_candidate[ex] = new_alloc # frac * target_trade_size

            if abs(sum(new_candidate.values()) - target_trade_size) > 10**-precision:
                raise ValueError(f"new_candidate sum allocations = {sum(new_candidate.values())}\n{new_candidate}")
                # print(f"new_candidate sum allocations = {sum(new_candidate.values())}")

            # Find the candidate with the minimum cost (no delta) for this exchange. If it beats the existing best by delta,
            # then we'll add the exchange to the best solution
            if price_estimator.is_better(new_candidate, best_for_ex):
                best_for_ex = new_candidate

        if price_estimator.is_better(best_for_ex, best_new_candidate, delta):
            # print(f"new best: {best_for_ex}")
            best_new_candidate = best_for_ex

    return best_new_candidate


def rebalancing_branch_and_bound_solutions(target_trade_size, price_estimator, dexs, precision=4):
    # get a ranking of dexs by lowest cost at target_trade_size
    sorted_dexs = price_estimator.dexs_ranked_by_cost(target_trade_size)
    # start with baseline candidate: 1 DEX with the lowest cost at target_trade_size
    best_new_candidate = {sorted_dexs[0]: target_trade_size}
    print(f"rebal baseline={best_new_candidate} sorted_dexs[1:]={sorted_dexs[1:]}")

    # loop over remaining DEXs adding some amount of each as long as cost gets lower
    for ex in sorted_dexs[1:]:
        best_for_ex = None
        for i in range(1,100):
            frac = i/100
            # adjust allocations to precision digits
            new_candidate = { e: round(t*(1-frac),precision) for e,t in best_new_candidate.items() }
            new_alloc = round(target_trade_size - sum(new_candidate.values()), precision)

            if abs(new_alloc - (frac * target_trade_size)) > 2 * 10**-precision:
                raise ValueError(f"BIG DIFF ({abs(new_alloc - (frac * target_trade_size)):.4f}) between new_alloc={new_alloc:.4f} and (frac * target_trade_size) {frac * target_trade_size:.4f}")

            new_candidate[ex] = new_alloc # frac * target_trade_size

            if abs(sum(new_candidate.values()) - target_trade_size) > 10**-precision:
                raise ValueError(f"new_candidate sum allocations = {sum(new_candidate.values())}\n{new_candidate}")
                # print(f"new_candidate sum allocations = {sum(new_candidate.values())}")

            if price_estimator.is_better(new_candidate, best_for_ex):
                if best_for_ex:
                    how_much_better = price_estimator.solution_cost(new_candidate) - price_estimator.solution_cost(best_for_ex)
                    # print(f"{ex} at {new_alloc} is {how_much_better:.4f} better: \t{new_candidate}")
                best_for_ex = new_candidate

        if price_estimator.is_better(best_for_ex, best_new_candidate):
            print(f"rebal new best: {best_for_ex}")
            # what does rebalancing do?
            if len(best_for_ex) == 3:
                print(f"starting rebalance on {sorted_dexs[2]} best_for_ex={best_for_ex} sorted_dexs={sorted_dexs}")
                even_better_candidate = optimal_rebalance(ex, best_for_ex, price_estimator)
                how_much = price_estimator.solution_cost(even_better_candidate) - price_estimator.solution_cost(best_for_ex)
                print(f"rebal even better {how_much:.4f}: {even_better_candidate}")
                best_for_ex = even_better_candidate

            best_new_candidate = best_for_ex

    return best_new_candidate

def optimal_rebalance(new_ex, new_candidate, price_estimator):
    """Given some new DEX and solution try to find a better one by optimizing the split between the existing DEXs"""
    new_ex_fixed_alloc = new_candidate[new_ex]
    old_exs_allocs = {x: t for x, t in new_candidate.items() if x != new_ex }
    if not len(old_exs_allocs) == 2:
        raise ValueError(f"This only works with 2 existing dexs and 1 new one, but existing_allocs={old_exs_allocs}")
    d1, d2 = list(old_exs_allocs.keys())
    sum_old_allocs = sum(old_exs_allocs.values())

    best_candidate = new_candidate.copy()
    for i in range(1, 101):
        frac = i / 100
        test_candidate = {new_ex: new_ex_fixed_alloc}
        test_candidate[d1] = round(sum_old_allocs * frac, 4)
        test_candidate[d2] = round(sum_old_allocs - test_candidate[d1], 4)
        how_much_better = price_estimator.solution_cost(test_candidate) - price_estimator.solution_cost(best_candidate)
        # print(f"\t\t{how_much_better} better: \t{price_estimator.solution_cost(test_candidate)} - {solution_cost(price_estimator.best_candidate)} \t{test_candidate}")

        if price_estimator.is_better(test_candidate, best_candidate):
            best_candidate = test_candidate

    return best_candidate



def greedy_solutions(target_trade_size, price_estimator, dexs):
    max_steps = round(target_trade_size * 2)
    best, winner = [{}]*(max_steps+1), None

    for steps in range(1, max_steps + 1):
        best[steps] = greedy_alg(target_trade_size, price_estimator, dexs, steps)
        if price_estimator.is_better(best[steps], winner):
            # print(f"{steps} steps is best so far for target_trade_size={target_trade_size}")
            winner = best[steps]
            best_steps = steps

    return winner, best, best_steps

def greedy_alg(target_trade_size, price_estimator, dexs, steps):
    """Finds a solution by choosing the best option at each step (steps=10 takes ten steps)"""
    candidate = defaultdict(float)
    step_size = round(target_trade_size / steps, 4)
    while sum(candidate.values()) < target_trade_size:
        next_step_size = min(target_trade_size - sum(candidate.values()), step_size)
        best_new_candidate = None
        for ex in dexs:
            new_candidate = candidate.copy()
            new_candidate[ex] += next_step_size
            if price_estimator.is_better(new_candidate, best_new_candidate):
                best_new_candidate = new_candidate
        candidate = best_new_candidate
        # print(f"allocated={sum(candidate.values())} best_dex={best_dex}, best_cost={best_cost} next_step_size={next_step_size} candidate={dict(candidate)}")
    return dict(candidate)

########################################################################################################################
# CSV generation functions


def extract(ts_ex_pscs):
    all_dexs, all_trade_sizes = set(), set()
    base_price = float('inf')
    for trade_size, ex_pscs in ts_ex_pscs.items():
        all_trade_sizes.add(trade_size)
        all_dexs |= ex_pscs.keys()
        for ex, pscs in ex_pscs.items():
            price = first_price(pscs)
            base_price = min(base_price, price)
    sorted_float_trade_sizes = sorted(map(float, (all_trade_sizes)))
    sorted_dex_names = sorted(all_dexs)
    return base_price, sorted_dex_names, sorted_float_trade_sizes

def print_dex_cost_comparison_csv(tok_ts_ex_pscs, dexs=None):
    for token, ts_ex_pscs in tok_ts_ex_pscs.items():
        base_price, sorted_dex_names, sorted_float_trade_sizes = extract(ts_ex_pscs)
        dexs = sorted(dexs) if dexs else sorted_dex_names
        print(f"\n\n{token}/ETH slippage cost by trade size for {','.join(dexs)}")
        print(f"token,trade_size,{','.join(dexs)}")
        for trade_size in map(str,sorted_float_trade_sizes):
            row = f"{token},{trade_size}"
            for dex in dexs:
                pscs = ts_ex_pscs[trade_size].get(dex)
                # cost is based on a common base price across DEXs
                cost = first_slippage_cost(pscs, trade_size, base_price) if pscs else ''
                row += f",{cost}"
            print(row)

def print_dex_price_comparison_csv(tok_ts_ex_pscs, dexs=None):
    for token, ts_ex_pscs in tok_ts_ex_pscs.items():
        base_price, sorted_dex_names, sorted_float_trade_sizes = extract(ts_ex_pscs)
        dexs = sorted(dexs) if dexs else sorted_dex_names
        print(f"\n\n{token}/ETH price by trade size for {','.join(dexs)}")
        print(f"token,trade_size,{','.join(dexs)}")
        for trade_size in map(str,sorted_float_trade_sizes):
            row = f"{token},{trade_size}"
            for dex in dexs:
                pscs = ts_ex_pscs[trade_size].get(dex)
                # cost is based on a common base price across DEXs
                price = first_price_normalized(pscs, trade_size, base_price) if pscs else ''
                row += f",{price}"
            print(row)

def first_price(pscs):
    """ Returns the first price of the first psc tuple in the given list of tuples"""
    if len(pscs) != 1: raise ValueError(f"expected 1 cost data set, but had {len(pscs)}")
    psc = pscs[0]
    return psc[0]

def first_price_normalized(pscs, trade_size, base_price):
    return (first_price(pscs) - base_price) / base_price

# lambda slippage_cost : float(trade_size) * (first_price(pscs) - base_prices[token]) / base_prices[token]
def first_slippage_cost(pscs, trade_size, base_price):
    """Returns a cost in ETH of the slippage expressed as a percent difference in the price vs base_price"""
    return float(trade_size) * first_price_normalized(pscs, trade_size, base_price)


########################################################################################################################

CSV_FILES = (
    'outputs/Bancor_BAT_2019-11-15_14:00:00_DEX.AG_buy_slippage.csv',
    'outputs/Kyber_BAT_2019-11-15_14:00:00_DEX.AG_buy_slippage.csv',
    'outputs/Radar Relay_BAT_2019-11-15_14:00:14_DEX.AG_buy_slippage.csv',
    'outputs/Uniswap_BAT_2019-11-15_14:00:00_DEX.AG_buy_slippage.csv',
    'outputs/0xMesh_BAT_2019-11-15_14:00:00_Totle_buy_slippage.csv',
)

def main():
    csv_files = tuple(sys.argv[1:])
    if len(csv_files) < 1:
        csv_files = CSV_FILES
    else:
        print(f"processing {len(csv_files)} CSV files ...")

    tok_ts_ex_pscs = data_import.read_slippage_csvs(csv_files)
    # print_dex_cost_comparison_csv(tok_ts_ex_pscs)
    # print_dex_price_comparison_csv(tok_ts_ex_pscs)

    # for token in tok_ts_ex_pscs:
    token = list(tok_ts_ex_pscs.keys())[0]

    # enumerate_stuff(tok_ts_ex_pscs[token], [20.0])
    # run_optimization_algorithms(tok_ts_ex_pscs[token], OPTIMAL_SOLUTIONS.keys())
    run_optimization_algorithms(token, tok_ts_ex_pscs[token], [30.0], delta=0.005)


if __name__ == "__main__":
    main()

