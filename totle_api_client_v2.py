import sys
import argparse
import datetime
import csv

import v2_client

##############################################################################################
#
# functions to compute and print price differences
#

def compare_prices(token, supported_pairs, non_liquid_tokens, params=None, verbose=True, debug=False):
    """Returns a dict containing Totle and other DEX prices"""

    savings = {}
    from_token, to_token, bidask = ('ETH', token, 'ask') if params['orderType'] == 'buy' else (token, 'ETH', 'bid')
    k_params = {'params': params, 'verbose': verbose, 'debug': debug }
    totle_ex = v2_client.TOTLE_EX
    
    # Get the best price using Totle's aggregated order books
    totle_sd = v2_client.try_swap(totle_ex, from_token, to_token, **k_params)

    if totle_sd:
        totle_used = totle_sd['totleUsed']
        swap_prices = {totle_ex: totle_sd['price']}
        if totle_used not in supported_pairs:
            supported_pairs[totle_used] = []
        supported_pairs[totle_used].append((from_token, to_token))

        # Compare to best prices from other DEXs
        for dex in [dex for dex in supported_pairs if dex != totle_used]:
            dex_sd = v2_client.try_swap(dex, from_token, to_token, exchange=dex, **k_params)
            if dex_sd:
                swap_prices[dex] = dex_sd['price']
                if swap_prices[dex] < 0.0:
                    raise ValueError(f"{dex} had an invalid price={swap_prices[dex]}")
                supported_pairs[dex].append((from_token, to_token))


        other_dexs = [k for k in swap_prices if k != totle_ex]
        if other_dexs:  # there is data to compare
            totle_price = swap_prices[totle_ex]
            for e in other_dexs:
                ratio = totle_price/swap_prices[e] # totle_price assumed lower
                pct_savings = 100 - (100.0 * ratio)
                savings[e] = {'time': datetime.datetime.now().isoformat(), 'action': params['orderType'], 'pct_savings': pct_savings, 'totle_used':totle_used, 'totle_price': totle_price, 'exchange_price': swap_prices[e]}
                print(f"Totle saved {pct_savings:.2f} percent vs {e} {params['orderType']}ing {token} on {totle_used} trade size={params['tradeSize']} ETH")
        else:
            print(f"Could not compare {token} prices. Only valid price was {swap_prices}")
            # although we'll likely get the same result at higher trade sizes, don't over-
            # optimize. Past data shows there are more liquid tokens at higher trade sizes
            # than what we get with this optimization
            # non_liquid_tokens.append(token) 
    else:
        non_liquid_tokens.append(token)

    return savings

def print_average_savings(all_savings):
    for trade_size in all_savings:
        print(f"\nAverage Savings trade size = {trade_size} ETH vs")
        print_average_savings_by_dex(all_savings[trade_size])

def print_average_savings_by_dex(avg_savings):
    dex_savings = {}

    for token_savings in [ avg_savings[token] for token in avg_savings ]:
        for dex in token_savings:
            if dex not in dex_savings:
                dex_savings[dex] = []
            dex_savings[dex].append(token_savings[dex]['pct_savings'])

    for dex in dex_savings:
        sum_savings, n_samples = sum(dex_savings[dex]), len(dex_savings[dex])
        if n_samples:
            print(f"   {dex}: {sum_savings/n_samples:.2f}% ({n_samples} samples)")
        else:
            print(f"   {dex}: - (no samples)")

    return dex_savings

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

# liquid_dexs = v2_client.enabled_exchanges
# don't waste time on non-liquid dexes
non_liquid_dexs = [ 'Compound' ]
liquid_dexs = [e for e in v2_client.enabled_exchanges if e not in non_liquid_dexs ] 

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
        all_supported_pairs[trade_size] = {dex: [] for dex in liquid_dexs} # compare_prices() uses these keys to know what dexs to try
        print(f"\n\nNEW ROUND TRADE SIZE = {trade_size} ETH trying {len(liquid_tokens)} liquid tokens on the following DEXs: {liquid_dexs}")
        for token in liquid_tokens:
            print(f"\n----------------------------------------")
            print(f"\n{order_type} {token} trade size = {trade_size} ETH")
            savings = compare_prices(token, all_supported_pairs[trade_size], non_liquid_tokens, params, debug=False)
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
        liquid_dexs = [ e for e in liquid_dexs if all_supported_pairs[trade_size][e] ]

print_average_savings(all_savings)
print_supported_pairs(all_supported_pairs)
report_failures(all_savings)

