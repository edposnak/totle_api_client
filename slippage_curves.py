import sys
from collections import defaultdict
from itertools import permutations, combinations_with_replacement
import data_import

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

def get_price_matrix(ts_ex_pscs, base_price):
    ts_ex_prices = defaultdict(dict)
    for trade_size, ex_pscs in ts_ex_pscs.items():
        for ex, pscs in ex_pscs.items():
            ts_ex_prices[trade_size][ex] = first_price_normalized(pscs, trade_size, base_price)
    return {float(ts): ec for ts, ec in ts_ex_prices.items()}

def get_hi_res_price_matrix(low_res_price_matrix, max_trade_size=100):
    ts_ex_prices = defaultdict(dict)

    dexs = sorted(low_res_price_matrix.get(min(low_res_price_matrix.keys())).keys())

    # do 0.1 ETH granularity up to trade_size = 2
    for i in range(1, 10*min(max_trade_size, 2)):
        ts = i / 10
        for ex in dexs:
            ts_ex_prices[ts][ex] = get_price(ex, ts, low_res_price_matrix)

    for i in range(2, int(max_trade_size)+1):
        ts = round(float(i),1)
        for ex in dexs:
            ts_ex_prices[ts][ex] = get_price(ex, ts, low_res_price_matrix)

    return ts_ex_prices

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

def enumerate_stuff(ts_ex_pscs, target_trade_sizes):
    base_price, sorted_dex_names, _ = extract(ts_ex_pscs)
    lo_res_price_matrix = get_price_matrix(ts_ex_pscs, base_price)
    hi_res_price_matrix = get_hi_res_price_matrix(lo_res_price_matrix)

    for target_trade_size in target_trade_sizes:
        print(f"\n\nBest splits for a target trade size of {target_trade_size}")
        lo_res_enum_winner, lo_res_enum_best = enumerate_solutions(target_trade_size, lo_res_price_matrix, sorted_dex_names)
        print(f"\n\ncalling enumerate_solutions with hi_res_price_matrix sorted_dex_names={sorted_dex_names} target_trade_size={target_trade_size}\n\n")
        hi_res_enum_winner, hi_res_enum_best = enumerate_solutions(target_trade_size, hi_res_price_matrix, sorted_dex_names)
        print(f"hi_res_enum_winner={hi_res_enum_winner}")
        compare_costs(f"Hi-res vs Low-res", lo_res_enum_winner, hi_res_enum_winner, hi_res_price_matrix)


def enumerate_solutions(target_trade_size, price_matrix, dexs, max_ways=None):
    """Evaluates solutions of the form { 'Bancor': 12, 'Kyber': 8 } """
    price_matrix = get_hi_res_price_matrix(price_matrix)
    trade_sizes = [sts for sts in price_matrix.keys() if sts <= target_trade_size]
    max_ways = max_ways or len(dexs)
    best, winner = [{}]*(max_ways+1), None
    sol_cost = lambda solution: solution_cost(solution, price_matrix)

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

########################################################################################################################
# optimization algorithms

def run_optimization_algorithms(ts_ex_pscs, target_trade_sizes):
    base_price, sorted_dex_names, _ = extract(ts_ex_pscs)
    price_matrix = get_price_matrix(ts_ex_pscs, base_price)

    for target_trade_size in target_trade_sizes:
        baseline, _ = enumerate_solutions(target_trade_size, price_matrix, sorted_dex_names, max_ways=1)
        optimal = OPTIMAL_SOLUTIONS.get(target_trade_size)
        if not optimal: raise ValueError(f"target_trade_size={target_trade_size} but we only have solutions for trade sizes {list(OPTIMAL_SOLUTIONS.keys())}")

        print(f"\n\nBest splits for a target trade size of {target_trade_size}")
        # greedy_winner, greedy_best, best_steps = greedy_solutions(target_trade_size, price_matrix, sorted_dex_names)
        branch_winner = branch_and_bound_solutions(target_trade_size, price_matrix, sorted_dex_names)
        # rebalancing_branch_winner = rebalancing_branch_and_bound_solutions(target_trade_size, price_matrix, sorted_dex_names)

        # compare_costs(f"Optimal", baseline, optimal, price_matrix)
        # compare_costs(f"Greedy ({best_steps} steps)", baseline, greedy_winner, price_matrix)
        # compare_costs(f"Greedy ({best_steps} steps) vs optimal", optimal, greedy_winner, price_matrix)
        compare_costs(f"Basic Branch", baseline, branch_winner, price_matrix)
        compare_costs(f"Basic Branch vs optimal", optimal, branch_winner, price_matrix)
        # compare_costs(f"Rebalancing Branch vs optimal", optimal, rebalancing_branch_winner, price_matrix)
        # compare_costs(f"Rebalancing Branch vs Basic Branch", branch_winner, rebalancing_branch_winner, price_matrix)




def branch_and_bound_solutions(target_trade_size, price_matrix, dexs, precision=4):
    # get a ranking of dexs by lowest cost at target_trade_size
    sorted_dexs = rank_by_cost(dexs, target_trade_size, price_matrix)
    # start with baseline candidate: 1 DEX with the lowest cost at target_trade_size
    best_new_candidate = {sorted_dexs[0]: target_trade_size}
    print(f"baseline={best_new_candidate} sorted_dexs[1:]={sorted_dexs[1:]}")

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

            if is_better(new_candidate, best_for_ex, price_matrix):
                if best_for_ex:
                    how_much_better = solution_cost(new_candidate, price_matrix) - solution_cost(best_for_ex, price_matrix)
                    # print(f"{ex} at {new_alloc} is {how_much_better:.4f} better: \t{new_candidate}")
                best_for_ex = new_candidate

        if is_better(best_for_ex, best_new_candidate, price_matrix):
            # print(f"new best: {best_for_ex}")
            best_new_candidate = best_for_ex

    return best_new_candidate


def rebalancing_branch_and_bound_solutions(target_trade_size, price_matrix, dexs, precision=4):
    # get a ranking of dexs by lowest cost at target_trade_size
    sorted_dexs = rank_by_cost(dexs, target_trade_size, price_matrix)
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

            if is_better(new_candidate, best_for_ex, price_matrix):
                if best_for_ex:
                    how_much_better = solution_cost(new_candidate, price_matrix) - solution_cost(best_for_ex, price_matrix)
                    # print(f"{ex} at {new_alloc} is {how_much_better:.4f} better: \t{new_candidate}")
                best_for_ex = new_candidate

        if is_better(best_for_ex, best_new_candidate, price_matrix):
            print(f"rebal new best: {best_for_ex}")
            # what does rebalancing do?
            if len(best_for_ex) == 3:
                print(f"starting rebalance on {sorted_dexs[2]} best_for_ex={best_for_ex} sorted_dexs={sorted_dexs}")
                even_better_candidate = optimal_rebalance(ex, best_for_ex, price_matrix)
                how_much = solution_cost(even_better_candidate, price_matrix) - solution_cost(best_for_ex, price_matrix)
                print(f"rebal even better {how_much:.4f}: {even_better_candidate}")
                best_for_ex = even_better_candidate

            best_new_candidate = best_for_ex

    return best_new_candidate

def optimal_rebalance(new_ex, new_candidate, price_matrix):
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
        how_much_better = solution_cost(test_candidate, price_matrix) - solution_cost(best_candidate, price_matrix)
        # print(f"\t\t{how_much_better} better: \t{solution_cost(test_candidate, price_matrix)} - {solution_cost(best_candidate, price_matrix)} \t{test_candidate}")

        if is_better(test_candidate, best_candidate, price_matrix):
            best_candidate = test_candidate

    return best_candidate



def greedy_solutions(target_trade_size, price_matrix, dexs):
    max_steps = round(target_trade_size * 2)
    best, winner = [{}]*(max_steps+1), None

    for steps in range(1, max_steps + 1):
        best[steps] = greedy_alg(target_trade_size, price_matrix, dexs, steps)
        if is_better(best[steps], winner, price_matrix):
            # print(f"{steps} steps is best so far for target_trade_size={target_trade_size}")
            winner = best[steps]
            best_steps = steps

    return winner, best, best_steps

def greedy_alg(target_trade_size, price_matrix, dexs, steps):
    """Finds a solution by choosing the best option at each step (steps=10 takes ten steps)"""
    candidate = defaultdict(float)
    step_size = round(target_trade_size / steps, 4)
    while sum(candidate.values()) < target_trade_size:
        next_step_size = min(target_trade_size - sum(candidate.values()), step_size)
        best_new_candidate = None
        for ex in dexs:
            new_candidate = candidate.copy()
            new_candidate[ex] += next_step_size
            if is_better(new_candidate, best_new_candidate, price_matrix):
                best_new_candidate = new_candidate
        candidate = best_new_candidate
        # print(f"allocated={sum(candidate.values())} best_dex={best_dex}, best_cost={best_cost} next_step_size={next_step_size} candidate={dict(candidate)}")
    return dict(candidate)

########################################################################################################################
# utility methods
def is_better(candidate, best_candidate, price_matrix):
    """Returns True of the best_candidate is falsey or the price of candidate is lower than best_candidate"""
    if not best_candidate: return True
    return solution_cost(candidate, price_matrix) < solution_cost(best_candidate, price_matrix)

def rank_by_cost(dexs, target_trade_size, price_matrix):
    sorted_dex_costs = sorted([(solution_cost({ex: target_trade_size}, price_matrix), ex) for ex in dexs])

    sorted_dexs = [ dc[1] for dc in sorted_dex_costs ]
    print(f"sorted_dex_costs={sorted_dex_costs}")
    return sorted_dexs

def compare_costs(label, baseline, candidate, price_matrix):
    baseline = dict(sorted(baseline.items()))
    candidate = dict(sorted(candidate.items()))

    baseline_cost = solution_cost(baseline, price_matrix)
    candidate_cost = solution_cost(candidate, price_matrix)
    savings = baseline_cost - candidate_cost # will be positive if candidate is a better solution
    savings_pct = 0.0 if baseline_cost == 0 else 100.0 * (1 - candidate_cost / baseline_cost)
    print(f"{label}: saved {savings:.4f} ETH ({savings_pct:.2f}%)\n\tcandidate: {candidate} -> {candidate_cost}\n\tbaseline:  {baseline} -> {baseline_cost:.4f}")

def solution_cost(solution, price_matrix):
    sum_cost = 0.0
    for ex, ts in solution.items():
        sum_cost += get_cost(ex, ts, price_matrix)
    return sum_cost

def get_cost(ex, ts, price_matrix):
    return ts * get_price(ex, ts, price_matrix)

def get_price(ex, ts, price_matrix):
    if ts == 0: return 0
    if price_matrix.get(ts) and ex in price_matrix[ts]:
        return price_matrix[ts][ex]
    try:
        return interpolate_price(ex, ts, price_matrix)
    except ValueError:
        return float('inf')

def interpolate_price(ex, ts, price_matrix):
    lower, higher = 0.0, float('inf')
    ex_trade_sizes = [ets for ets in price_matrix.keys() if price_matrix[ets].get(ex)]
    for trade_size in ex_trade_sizes:
        if price_matrix[trade_size].get(ex):
            if trade_size < ts and trade_size > lower:
                lower = trade_size
            if trade_size > ts and trade_size < higher:
                higher = trade_size

    if higher == float('inf'): raise ValueError(f"Can't interpolate {ts} for {ex} because there is no higher value in the price matrix.\ntrade_sizes for {ex}={ex_trade_sizes}")

    l_price = 0.0 if lower == 0.0 else price_matrix[lower][ex]
    h_price = price_matrix[higher][ex]
    frac = (ts-lower) / (higher-lower)
    return l_price + frac * (h_price - l_price)

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
    return float(trade_size) * (first_price(pscs) - base_price)/base_price


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
    ts_ex_pscs = tok_ts_ex_pscs[token]
    base_price, sorted_dex_names, sorted_float_trade_sizes = extract(ts_ex_pscs)
    price_matrix = get_price_matrix(ts_ex_pscs, base_price)

    # enumerate_stuff(tok_ts_ex_pscs[token], [20.0])
    run_optimization_algorithms(tok_ts_ex_pscs[token], OPTIMAL_SOLUTIONS.keys())


if __name__ == "__main__":
    main()

