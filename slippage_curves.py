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

def run_optimization_algorithms(ts_ex_pscs, target_trade_sizes):
    base_price, sorted_dex_names, sorted_float_trade_sizes = extract(ts_ex_pscs)
    price_matrix = get_price_matrix(ts_ex_pscs, base_price)
    # TARGET_TRADE_SIZE = 5
    for target_trade_size in target_trade_sizes:
        print(f"\n\nBest splits for a target trade size of {target_trade_size}")
        enum_winner, enum_best = enumerate_solutions(target_trade_size, price_matrix, sorted_dex_names, sorted_float_trade_sizes)
        # greedy_winner, greedy_best, best_steps = greedy_solutions(target_trade_size, price_matrix, sorted_dex_names)
        branch_winner = branch_and_bound_solutions(target_trade_size, price_matrix, sorted_dex_names)
        # superlinear(target_trade_size, price_matrix, sorted_dex_names)

        enum_baseline = enum_best[1] or enum_best[2] or enum_best[3]
        compare_costs("Enumerated solution", enum_baseline, enum_winner, price_matrix)
        # compare_costs(f"Greedy (steps={best_steps})", enum_baseline, greedy_winner, price_matrix)
        # compare_costs(f"Greedy vs enum (steps={best_steps})", enum_winner, greedy_winner, price_matrix)
        compare_costs(f"Branch", enum_baseline, branch_winner, price_matrix)
        compare_costs(f"Branch vs enum", enum_winner, branch_winner, price_matrix)


def enumerate_solutions(target_trade_size, price_matrix, dexs, sorted_float_trade_sizes):
    """Evaluates solutions of the form { 'Bancor': 12, 'Kyber': 8 } """
    trade_sizes = [sts for sts in sorted_float_trade_sizes if sts <= target_trade_size]
    best, winner = [{}]*(len(dexs)+1), None
    sol_cost = lambda solution: solution_cost(solution, price_matrix)

    for n in range(1, len(best)):
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

def superlinear(target_trade_size, price_matrix, dexs):
    sorted_dexs = rank_by_cost(dexs, target_trade_size, price_matrix)

    for dex in sorted_dexs[1:]:
        dex_price, ts_allocation = 0.0, 0.0
        step = round(target_trade_size / 100, 4)
        baseline_price = get_price(sorted_dexs[0], target_trade_size, price_matrix)
        while dex_price < baseline_price and ts_allocation < target_trade_size:
            ts_allocation += step
            best_allocation = target_trade_size - ts_allocation
            dex_price = get_price(dex, ts_allocation, price_matrix)
            baseline_price = get_price(sorted_dexs[0], best_allocation, price_matrix)
            if dex == 'Uniswap':
                # Uniswap price at 1.80 = 0.00133 Kyber price at 7.20 = 0.00203 est. cost=0.01701
                #               = 1.8 * 0.00133 + 7.2 * 0.00203
                # Uniswap price at 2.79 = 0.00182 Kyber price at 6.21 = 0.00203 est. cost=0.01769
                #               = 2.8 * 0.00182 + 6.2 * 0.00203
                #
                est_cost = get_cost(dex, ts_allocation, price_matrix) + get_cost(sorted_dexs[0], best_allocation, price_matrix)
                print(f"{dex} price at {ts_allocation:.2f} = {dex_price:.5f} {sorted_dexs[0]} price at {best_allocation:.2f} = {baseline_price:.5f} est. cost={est_cost:.5f}")

        print(f"{dex} at exceeded {sorted_dexs[0]} price at {ts_allocation} / {target_trade_size-ts_allocation}")

def branch_and_bound_solutions(target_trade_size, price_matrix, dexs):
    # get a ranking of dexs by lowest cost at target_trade_size
    sorted_dexs = rank_by_cost(dexs, target_trade_size, price_matrix)
    # start with baseline candidate: 1 DEX with the lowest cost at target_trade_size
    best_new_candidate = {sorted_dexs[0]: target_trade_size}
    print(f"baseline={best_new_candidate} sorted_dexs[1:]={sorted_dexs[1:]}")


    # loop over remaining DEXs adding some amount of each as long as cost gets lower
    for ex in sorted_dexs[1:]:
        print(f"doing {ex}")
        best_for_ex = None
        for i in range(1,100):
            frac = i/100
            new_candidate = { e: t*(1-frac) for e,t in best_new_candidate.items() }
            new_candidate[ex] = frac * target_trade_size
            # print(f"new_candidate sum allocations = {sum(new_candidate.values())}")
            if is_better(new_candidate, best_for_ex, price_matrix):
                # print(f"better: {new_candidate}")
                best_for_ex = new_candidate

        if is_better(best_for_ex, best_new_candidate, price_matrix):
            # print(f"new best: {best_for_ex}")
            best_new_candidate = best_for_ex

    return best_new_candidate


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

def is_better(candidate, best_candidate, price_matrix):
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
    print(f"{label}: ({savings_pct:.2f}%) {candidate} -> {candidate_cost} vs baseline: {baseline} -> {baseline_cost:.4f} saved {savings:.4f} ETH")

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
# main

CSV_FILES = [
    'outputs/Bancor_BAT_2019-11-15_14:00:00_DEX.AG_buy_slippage.csv',
    'outputs/Kyber_BAT_2019-11-15_14:00:00_DEX.AG_buy_slippage.csv',
    'outputs/Radar Relay_BAT_2019-11-15_14:00:14_DEX.AG_buy_slippage.csv',
    'outputs/Uniswap_BAT_2019-11-15_14:00:00_DEX.AG_buy_slippage.csv',
    'outputs/0xMesh_BAT_2019-11-15_14:00:00_Totle_buy_slippage.csv',
]


csv_files = tuple(sys.argv[1:])
if len(csv_files) < 1:
    csv_files = tuple(CSV_FILES)
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

# TODO: move to test_slippage_curves
#
# solutions = [
#     {'0xMesh': 5.0, 'Bancor': 1.0, 'Kyber': 20.0, 'Radar Relay': 1.0, 'Uniswap': 3.0},  # enum (31.15%)
#     {'0xMesh': 7.0, 'Bancor': 2.0, 'Kyber': 8.0, 'Radar Relay': 9.0, 'Uniswap': 4.0},   # greedy 30 steps (22.85%)
#     {'0xMesh': 6.0, 'Bancor': 1.5, 'Kyber': 8.0, 'Radar Relay': 10.0, 'Uniswap': 4.5},  # greedy 60 steps
#     {'0xMesh': 5.0, 'Bancor': 0.0, 'Kyber': 20.0, 'Radar Relay': 0.0, 'Uniswap': 5.0}   # greedy 6 steps (27.98%)
#     {'0xMesh': 4.2857, 'Bancor': 0.0, 'Kyber': 17.142900000000004, 'Radar Relay': 4.2857, 'Uniswap': 4.2857} greedy 7 steps (27.90%)
#     {'0xMesh': 3.75, 'Bancor': 0.0, 'Kyber': 18.75, 'Radar Relay': 3.75, 'Uniswap': 3.75} # greedy 8 steps (27.94%)
#     {'0xMesh': 6.6666, 'Bancor': 0.0, 'Kyber': 19.9998, 'Radar Relay': 0.0, 'Uniswap': 3.3335999999999992} # greedy 9 steps (28.59%)
#     {'0xMesh': 6.0, 'Bancor': 0.0, 'Kyber': 18.0, 'Radar Relay': 3.0, 'Uniswap': 3.0} # greedy 10 steps (28.47%)
#     {'0xMesh': 5.4546, 'Bancor': 0.0, 'Kyber': 19.0911, 'Radar Relay': 2.7270000000000003, 'Uniswap': 2.7273} # greedy 11 steps (28.76%)
#     {'0xMesh': 5.0, 'Bancor': 2.5, 'Kyber': 20.0, 'Radar Relay': 0.0, 'Uniswap': 2.5}  # greedy 12 steps (29.41%)
#     {'0xMesh': 5.0001, 'Bancor': 1.6667, 'Kyber': 19.9998, 'Uniswap': 3.3334,  }            # greedy 18 steps (31.23%)
#     {'0xMesh': 6.0, 'Bancor': 1.5, 'Kyber': 17.0, 'Radar Relay': 1.0, 'Uniswap': 4.5},  # wtf?
#     {'0xMesh': 5.0, 'Bancor': 1.0, 'Kyber': 19.0, 'Radar Relay': 1.0, 'Uniswap': 4.0},
#     ]

# 0xMesh at exceeded Kyber price at 1.6000000000000003 / 8.4
# Radar Relay at exceeded Kyber price at 0.1 / 9.9
# Uniswap at exceeded Kyber price at 3.3000000000000016 / 6.699999999999998
# Bancor at exceeded Kyber price at 0.2 / 9.8
solutions = [
    {'Kyber': 10.0}, # Baseline
    {'0xMesh': 0.5, 'Bancor': 0.5, 'Kyber': 7.0, 'Uniswap': 2.0}, # Enumerated solution: (25.34%)
    {'0xMesh': 0.5, 'Bancor': 0.5, 'Kyber': 7.3, 'Uniswap': 1.7}, #
    {'0xMesh': 0.5, 'Bancor': 0.5, 'Kyber': 7.4, 'Uniswap': 1.6}, #
    {'0xMesh': 0.5, 'Bancor': 0.5, 'Kyber': 7.5, 'Uniswap': 1.5}, #
    {'0xMesh': 0.5, 'Bancor': 0.5, 'Kyber': 7.6, 'Uniswap': 1.4}, #
    {'0xMesh': 0.5, 'Bancor': 0.5, 'Kyber': 7.7, 'Uniswap': 1.3}, #
    {'0xMesh': 0.5, 'Bancor': 0.5, 'Kyber': 7.8, 'Uniswap': 1.2}, #
    {'0xMesh': 0.5, 'Bancor': 0.5, 'Kyber': 7.9, 'Uniswap': 1.1}, #

    {'Kyber': 6.0, 'Uniswap': 4.0},  #
    {'Kyber': 6.1, 'Uniswap': 3.9},  #
    {'Kyber': 6.2, 'Uniswap': 3.8},  #
    {'Kyber': 6.3, 'Uniswap': 3.7},  #
    {'Kyber': 6.7, 'Uniswap': 3.3},  #
    {'Kyber': 7.1, 'Uniswap': 2.9},  #
    {'Kyber': 7.5, 'Uniswap': 2.5},  #
    {'Kyber': 7.9, 'Uniswap': 2.1},  #
    {'Kyber': 8.0, 'Uniswap': 2.0},  #
    {'Kyber': 8.1, 'Uniswap': 1.9},  #
    {'Kyber': 8.2, 'Uniswap': 1.8},  #
    {'Kyber': 8.3, 'Uniswap': 1.7},  #

]


for solution in solutions:
    cost = solution_cost(solution, price_matrix)
    print(f"{cost}: \t{solution} ")

run_optimization_algorithms(tok_ts_ex_pscs[token], range(10,110,10))
# run_optimization_algorithms(tok_ts_ex_pscs[token], [10.0, 15.0, 20.0, 30.0, 40.0])


