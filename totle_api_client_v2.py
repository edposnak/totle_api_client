import sys
import argparse
import datetime
import csv
from collections import defaultdict

import v2_client
from v2_compare_prices import compare_prices, print_average_savings

##############################################################################################
#
# functions to print things for a given run
#
def print_supported_pairs(all_supported_pairs):
    for trade_size in all_supported_pairs:
        print(f"\nLiquidity at trade size of {trade_size} ETH:")
        for e in all_supported_pairs[trade_size]:
            pairs = [f"{t}/{f}" for f, t in all_supported_pairs[trade_size][e]]
            print(f"   {e}: {len(pairs)} pairs {pairs}")

def report_failures(all_savings):
    succs, fails = 0, 0
    for trade_size in all_savings:
        asts = all_savings[trade_size]
        for savings in [asts[token] for token in asts]:
            for e in savings:
                pct_savings = savings[e]['pct_savings']
                if pct_savings > 0:
                    succs += 1
                else:
                    fails += 1

    samples = succs + fails
    print(f"\n\n")
    print(f"Totle failed to get the best price {fails}/{samples} times ({100*fails/samples:.2f}%)")

    
##############################################################################################
#
# Main program
#

# Define program arguments
parser = argparse.ArgumentParser(description='Run price comparisons')
parser.add_argument('--sell', dest='orderType', action='store_const', const='sell', default='buy', help='execute sell orders (default is buy)')
parser.add_argument('tradeSize', type=float, nargs='?', help='the size (in ETH) of the order')
parser.add_argument('maxMarketSlippagePercent', type=int, nargs='?', help='acceptable percent of slippage')
parser.add_argument('maxExecutionSlippagePercent', type=int, nargs='?', help='acceptable percent of execution slippage')
parser.add_argument('minFillPercent', type=int, nargs='?', help='acceptable percent of amount to acquire')
parser.add_argument('partnerContract', nargs='?', help='address of partner fee contract')
parser.add_argument('apiKey', nargs='?', help='API key')

params = vars(parser.parse_args())

d = datetime.datetime.today()
filename = f"outputs/{d.year}-{d.month:02d}-{d.day:02d}_{d.hour:02d}:{d.minute:02d}:{d.second:02d}_{params['orderType']}"

# Redirect output to a .txt file in outputs directory
# Comment out the following 3 lines to see output on console
output_filename = f"{filename}.txt"
print(f"sending output to {output_filename} ...")
sys.stdout = open(output_filename, 'w')

TRADE_SIZES = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]

# don't waste time on non-liquid dexes
non_liquid_dexs = [ 'Compound' ]
liquid_dexs = tuple(filter(lambda e: e not in non_liquid_dexs, v2_client.enabled_exchanges))


liquid_tokens = [t for t in v2_client.tokens if t != 'ETH'] # start with all tradable tokens
all_savings, all_supported_pairs = {}, {}
order_type = params['orderType']

CSV_FIELDS = "time action trade_size token exchange exchange_price totle_used totle_price pct_savings".split()
with open(f"{filename}.csv", 'w', newline='') as csvfile:
    csv_writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
    csv_writer.writeheader()

    for trade_size in TRADE_SIZES:
        params['tradeSize'] = trade_size
        print(d, params)

        non_liquid_tokens = []
        all_savings[trade_size] = {}
        all_supported_pairs[trade_size] = defaultdict(list)
        print(f"\n\nNEW ROUND TRADE SIZE = {trade_size} ETH trying {len(liquid_tokens)} liquid tokens on the following DEXs: {liquid_dexs}")
        for token in liquid_tokens:
            print(f"\n----------------------------------------")
            print(f"\n{order_type} {token} trade size = {trade_size} ETH")
            savings = compare_prices(token, all_supported_pairs[trade_size], non_liquid_tokens, liquid_dexs, params, debug=False)
            if savings:
                all_savings[trade_size][token] = savings
                for exchange in savings:
                    row = {**{'trade_size': trade_size, 'token' : token, 'exchange': exchange}, **savings[exchange]}
                    csv_writer.writerow(row)
                    csvfile.flush()
            
        # don't try non_liquid_tokens at higher trade sizes
        print(f"\n\nremoving {len(non_liquid_tokens)} non-liquid tokens for the next round")
        liquid_tokens = [ t for t in liquid_tokens if t not in non_liquid_tokens ]

        # don't try non_liquid_dexs at higher trade sizes
        # for now, try all dexs and see how illiquid they really are
        # liquid_dexs = tuple(filter(lambda e: all_supported_pairs[trade_size][e], liquid_dexs))

print_average_savings(all_savings)
print_supported_pairs(all_supported_pairs)
report_failures(all_savings)

