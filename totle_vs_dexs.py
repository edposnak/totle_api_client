import os
import sys
import argparse
from collections import defaultdict

import token_utils
import totle_client
from v2_compare_prices import compare_dex_prices, print_average_savings, get_filename_base, SavingsCSV, redirect_stdout

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

def reportnegative_savings(all_savings):
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


TRADE_SIZES  = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0, 500.0]

def do_eth_pairs():
    # don't waste time on non-liquid dexes
    non_liquid_dexs = ['Compound']
    # liquid_dexs = tuple(filter(lambda e: e not in non_liquid_dexs, totle_client.enabled_exchanges()))
    liquid_dexs = ('Kyber', 'Uniswap')
    # liquid_tokens = [ t for t in token_utils.tokens() if t != 'ETH' ] # start with all tradable tokens
    liquid_tokens = ['SAI', 'MKR', 'WBTC', 'USDC', 'USDT', 'KNC', 'BNT', 'LINK', 'DAI', 'TUSD', 'BAT', 'RLC', 'ENG', 'REP', 'REN', 'ENJ', 'ZRX', 'XDCE', 'ANT', 'TKN', 'LEND', 'MANA', 'OMG', 'LRC', 'NMR', 'PAX', 'RPL', 'SPANK', 'RCN', 'SNT',
                     'RDN', 'NEXO']
    all_savings, all_supported_pairs = {}, {}
    order_type = params['orderType']
    CSV_FIELDS = "time id action trade_size token quote exchange exchange_price totle_used totle_price totle_splits pct_savings splits ex_prices".split()
    with SavingsCSV(filename, fieldnames=CSV_FIELDS) as csv_writer:
        for trade_size in TRADE_SIZES:
            if order_type == 'buy':
                params['fromAmount'] = trade_size
            elif order_type == 'sell':
                params['toAmount'] = trade_size
            else:
                raise ValueError(f"order_type must be 'buy' or 'sell'")

            non_liquid_tokens = []
            all_savings[trade_size] = {}
            all_supported_pairs[trade_size] = defaultdict(list)
            print(f"\n\nNEW ROUND TRADE SIZE = {trade_size} ETH trying {len(liquid_tokens)} liquid tokens on {liquid_dexs}")
            for token in liquid_tokens:
                print(f"\n----------------------------------------")
                print(f"\n{order_type} {token} trade size = {trade_size} ETH")
                savings = compare_dex_prices(token, all_supported_pairs[trade_size], non_liquid_tokens, liquid_dexs, order_type=order_type, params=params, debug=False)
                if savings:
                    all_savings[trade_size][token] = savings
                    for exchange in savings:
                        csv_writer.append(savings[exchange])

            # don't try non_liquid_tokens at higher trade sizes
            print(f"\n\nremoving {len(non_liquid_tokens)} non-liquid tokens for the next round")
            liquid_tokens = [t for t in liquid_tokens if t not in non_liquid_tokens]

            # don't try non_liquid_dexs at higher trade sizes
            # for now, try all dexs and see how illiquid they really are
            # liquid_dexs = tuple(filter(lambda e: all_supported_pairs[trade_size][e], liquid_dexs))

    return all_savings, all_supported_pairs

##############################################################################################
#
# Main program
#

working_dir = os.path.dirname(__file__)
if working_dir: os.chdir(working_dir)


# Define program arguments
parser = argparse.ArgumentParser(description='Run price comparisons')
parser.add_argument('--sell', dest='orderType', action='store_const', const='sell', default='buy', help='execute sell orders (default is buy)')
parser.add_argument('maxMarketSlippagePercent', type=int, nargs='?', help='acceptable percent of slippage')
parser.add_argument('maxExecutionSlippagePercent', type=int, nargs='?', help='acceptable percent of execution slippage')
parser.add_argument('minFillPercent', type=int, nargs='?', help='acceptable percent of amount to acquire')
parser.add_argument('partnerContract', nargs='?', help='address of partner fee contract')
parser.add_argument('apiKey', nargs='?', help='API key')

params = vars(parser.parse_args())

filename = get_filename_base(suffix=params['orderType'])
redirect_stdout(filename)


all_savings, all_supported_pairs = do_eth_pairs()

print_average_savings(all_savings)
print_supported_pairs(all_supported_pairs)
reportnegative_savings(all_savings)

