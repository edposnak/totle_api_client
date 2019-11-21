import data_import
import slippage_curves

solutions_at_ts_30 = [
    {'0xMesh': 5, 'Bancor': 1.3, 'Kyber': 20, 'Radar Relay': 0.7, 'Uniswap': 3},         # hi-res enum
    {'0xMesh': 5.0, 'Bancor': 1.0, 'Kyber': 20.0, 'Radar Relay': 1.0, 'Uniswap': 3.0},  # enum (31.15%)
    {'0xMesh': 7.0, 'Bancor': 2.0, 'Kyber': 8.0, 'Radar Relay': 9.0, 'Uniswap': 4.0},   # greedy 30 steps (22.85%)
    {'0xMesh': 6.0, 'Bancor': 1.5, 'Kyber': 8.0, 'Radar Relay': 10.0, 'Uniswap': 4.5},  # greedy 60 steps
    {'0xMesh': 5.0, 'Bancor': 0.0, 'Kyber': 20.0, 'Radar Relay': 0.0, 'Uniswap': 5.0},   # greedy 6 steps (27.98%)
    {'0xMesh': 4.2857, 'Bancor': 0.0, 'Kyber': 17.142900000000004, 'Radar Relay': 4.2857, 'Uniswap': 4.2857}, # greedy 7 steps (27.90%)
    {'0xMesh': 3.75, 'Bancor': 0.0, 'Kyber': 18.75, 'Radar Relay': 3.75, 'Uniswap': 3.75}, # greedy 8 steps (27.94%)
    {'0xMesh': 6.6666, 'Bancor': 0.0, 'Kyber': 19.9998, 'Radar Relay': 0.0, 'Uniswap': 3.3335999999999992}, # greedy 9 steps (28.59%)
    {'0xMesh': 6.0, 'Bancor': 0.0, 'Kyber': 18.0, 'Radar Relay': 3.0, 'Uniswap': 3.0}, # greedy 10 steps (28.47%)
    {'0xMesh': 5.4546, 'Bancor': 0.0, 'Kyber': 19.0911, 'Radar Relay': 2.7270000000000003, 'Uniswap': 2.7273}, # greedy 11 steps (28.76%)
    {'0xMesh': 5.0, 'Bancor': 2.5, 'Kyber': 20.0, 'Radar Relay': 0.0, 'Uniswap': 2.5},  # greedy 12 steps (29.41%)
    {'0xMesh': 5.0001, 'Bancor': 1.6667, 'Kyber': 19.9998, 'Uniswap': 3.3334},           # greedy 18 steps (31.23%)
    {'0xMesh': 6.0, 'Bancor': 1.5, 'Kyber': 17.0, 'Radar Relay': 1.0, 'Uniswap': 4.5},  # wtf?
    {'0xMesh': 5.0, 'Bancor': 1.0, 'Kyber': 19.0, 'Radar Relay': 1.0, 'Uniswap': 4.0},
    ]

solutions_at_ts_10 = [
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

TOKEN = 'BAT'
CSV_FILES = (
    '../outputs/Bancor_BAT_2019-11-15_14:00:00_DEX.AG_buy_slippage.csv',
    '../outputs/Kyber_BAT_2019-11-15_14:00:00_DEX.AG_buy_slippage.csv',
    '../outputs/Radar Relay_BAT_2019-11-15_14:00:14_DEX.AG_buy_slippage.csv',
    '../outputs/Uniswap_BAT_2019-11-15_14:00:00_DEX.AG_buy_slippage.csv',
    '../outputs/0xMesh_BAT_2019-11-15_14:00:00_Totle_buy_slippage.csv',
)

tok_ts_ex_pscs = data_import.read_slippage_csvs(CSV_FILES)
base_price, *_ = slippage_curves.extract(tok_ts_ex_pscs[TOKEN])

price_estimator = slippage_curves.construct_price_estimator(TOKEN, tok_ts_ex_pscs[TOKEN])

for ts, ex_pscs in tok_ts_ex_pscs[TOKEN].items():
    for ex, pscs in ex_pscs.items():
        mx_price = slippage_curves.first_price(pscs)
        ls_price = price_estimator.get_price(ex, ts)
        diff = mx_price - ls_price
        # if diff > 0.000001: print(f"{TOKEN} {ts} {ex} LS is off by {diff}  ({100.0 * diff / mx_price}%)")

for trade_size, ex_nprices in price_estimator.price_matrix.items():
    if trade_size not in [10.0, 30.0]: continue
    print(f"\n\nTrade Size = {trade_size}")
    for ex, nprice in ex_nprices.items():
        matrix_price = slippage_curves.first_price(tok_ts_ex_pscs[TOKEN][trade_size][ex])
        ls_price = price_estimator.get_price(ex, trade_size)
        print(f"{ex} matrix price = {matrix_price}  LS price = {ls_price} base_price={base_price} ls base_price={price_estimator.base_price}")
        print(f"{ex} matrix price - base_price = {matrix_price - base_price}  LS price - ls base_price = {ls_price - price_estimator.base_price}")
        print(f"{ex} matrix price NORMD = {(matrix_price - base_price)/base_price}  LS price NORMD = {(ls_price - price_estimator.base_price)/price_estimator.base_price}")
        ls_nprice = price_estimator.get_normalized_slippage_price(ex, trade_size)
        mx_nprice = price_estimator.get_normalized_price(ex, trade_size)
        print(f"{ex} matrix normalized price = {nprice}  LS normalized price = {ls_nprice}")
        print(f"{ex} matrix normalized cost = {trade_size * nprice}  LS normalized cost = {trade_size * ls_nprice}")
        print("\n")

for solution in solutions_at_ts_10:
    cost = price_estimator.solution_cost(solution)
    print(f"{cost}: \t{solution} ")

for solution in solutions_at_ts_30:
    cost = price_estimator.solution_cost(solution)
    print(f"{cost}: \t{solution} ")
