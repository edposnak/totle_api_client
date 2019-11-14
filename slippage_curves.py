import sys
from collections import defaultdict
import data_import


########################################################################################################################
# Slippage curves

csv_files = tuple(sys.argv[1:])
if len(csv_files) < 1:
    print("no CSV files provided")
    exit(1)
else:
    print(f"processing {len(csv_files)} CSV files ...")

def print_dex_cost_comparison_csv(exchange_token_pscs, dexs=None):
    dexs = dexs or exchange_token_pscs.keys()
    sorted_dex_names = sorted(dexs)
    all_trade_sizes = set()
    base_prices = defaultdict(float)
    tok_ts_ex_pscs = defaultdict(lambda: defaultdict(dict))
    for dex, token_pscs in exchange_token_pscs.items():
        for token, pscs in token_pscs.items():
            # print(f"\n{token}/ETH Slippage on {dex}")
            if len(pscs) != 1: raise ValueError(f"expected 1 cost data set, but had {len(pscs)}")
            psc_by_trade_size = pscs[0] # price, slippage, cost
            for trade_size, psc in psc_by_trade_size.items():
                tok_ts_ex_pscs[token][trade_size][dex] = psc
                base_prices[token] = min(base_prices[token], psc[0]) if base_prices[token] else psc[0]
            all_trade_sizes |= psc_by_trade_size.keys()
    sorted_trade_sizes = list(map(str, sorted(map(float, all_trade_sizes))))


    for token, ts_ex_costs in tok_ts_ex_pscs.items():
        print(f"\n\n{token}/ETH slippage cost by trade size for {','.join(sorted_dex_names)}")
        print(f"token,trade_size,{','.join(sorted_dex_names)}")
        for trade_size in sorted_trade_sizes:
            row = f"{token},{trade_size}"
            for dex in sorted_dex_names:
                psc = ts_ex_costs[trade_size].get(dex)
                # cost = psc[2] is based on DEX-specific base price. Here we compute cost
                cost = psc and float(trade_size) * (psc[0] - base_prices[token]) / base_prices[token]
                row += f",{cost}"
            print(row)

########################################################################################################################
# main


exchange_token_pscs = data_import.read_slippage_csvs(csv_files)

print_dex_cost_comparison_csv(exchange_token_pscs, ['Bancor', 'Kyber', 'Uniswap'])
