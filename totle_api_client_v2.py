import sys
import json
import requests
import argparse
import datetime
import time
import csv

##############################################################################################
#
# Library functions for exchanges, tokens, and prices
#
# get exchanges

API_BASE_R = 'https://services.totlesystem.com'
API_BASE_W = 'https://api.totle.com'
EXCHANGES_ENDPOINT = API_BASE_R + '/exchanges'
TOKENS_ENDPOINT = API_BASE_R + '/tokens'
PRICES_ENDPOINT = API_BASE_R + '/tokens/prices'
SWAP_ENDPOINT = API_BASE_W + '/swap'
# REBALANCE_ENDPOINT = API_BASE + '/rebalance'
# SWAP_ENDPOINT = REBALANCE_ENDPOINT = "https://services.totlesystem.com/orders/suggestions/v0-5-5"

r = requests.get(EXCHANGES_ENDPOINT).json()
exchanges = { e['name']: e['id'] for e in r['exchanges'] }
exchange_by_id = { e['id']: e['name'] for e in r['exchanges'] }
TOTLE_EX = 'Totle' # 'Totle' is used for comparison with other exchanges

# get tokens
r = requests.get(TOKENS_ENDPOINT).json()
tokens = { t['symbol']: t['address'] for t in r['tokens'] if t['tradable']}
token_symbols = { tokens[sym]: sym for sym in tokens }
token_decimals = { t['symbol']: t['decimals'] for t in r['tokens'] if t['tradable']}
token_decimals['ETH'] = 18

ETH_ADDRESS = "0x0000000000000000000000000000000000000000" 

def addr(token):
    """Returns the string address that identifies the token"""
    # convert 'ETH' to addr 0x000... in anticipation of fix to swap
    return ETH_ADDRESS if token == 'ETH' else tokens[token]

def int_amount(float_amount, token):
    """Returns the integer amount of token units for the given float_amount and token"""
    return int(float(float_amount) * (10**token_decimals[token]))

def real_amount(int_amount, token):
    """Returns the decimal number of tokens for the given integer amount and token"""
    return int(int_amount) / (10**token_decimals[token])

# get all token prices on all exchanges
all_prices_json = requests.get(PRICES_ENDPOINT).json()['response']


# remove new bidOrders and askOrders
all_prices = {t : {k : all_prices_json[t][k] for k in all_prices_json[t] if k.isdigit()} for t in all_prices_json}

# We assume that the prices endpoints returns the lowest 'ask' and highest 'bid' price for
# a given token. If it does not, then that would explain why rebalance returns orders
# with lower prices than the ask price
def price(token, exchange):
    """Returns lowest ask price in ETH for the given token on the given exchange"""
    return float(all_prices[tokens[token]][str(exchanges[exchange])]['ask'])

def best_ask_price(token):
    """Returns lowest ask price in ETH for the given token across all exchanges"""
    ap = all_prices[tokens[token]]
    return min([ float(ap[v]['ask']) for v in ap if ap[v]['ask'] ])

def best_bid_price(token):
    """Returns highest bid price in ETH for the given token across all exchanges"""
    ap = all_prices[tokens[token]]
    return max([ float(ap[v]['bid']) for v in ap if ap[v]['bid'] ])

def best_prices(token, bidask='ask'):
    """Returns lowest ask or highest bid prices in ETH for all exchanges"""
    token_prices = all_prices[tokens[token]]
    return { exchange_by_id[int(i)]: float(token_prices[i][bidask]) for i in token_prices if token_prices[i][bidask] }

def show_prices(token, order_type):
    if order_type == 'buy':
        print(f"Lowest ask prices for {token}: {pp(best_prices(token, 'ask'))}")
    else: # order_type == 'sell':
        print(f"Highest bid prices for {token}: {pp(best_prices(token, 'bid'))}")

def wei_to_eth(wei_amount):
    """Returns a decimal value of the amount of ETH for the given wei_amount"""
    return int(wei_amount) / 10**18

def eth_to_wei(eth_amount):
    return int(float(eth_amount) * 10**18)

def pp(data):
    return json.dumps(data, indent=3)

def all_liquid_tokens(min_exchanges=2):
    """returns all the tokens for which price data exists on at least min_exchanges DEXs"""
    if min_exchanges > len(exchanges):
        raise Exception(f"min_exchanges set to {min_exchanges}, but there are only {len(exchanges)} possible")

    taddrs = [ ta for ta in all_prices if ta in token_symbols ]

    return [ token_symbols[taddr] for taddr in taddrs if len(all_prices[taddr]) > min_exchanges ] 


##############################################################################################
#
# functions to call swap/rebalance and extract data
#

def post_with_retries(endpoint, inputs, num_retries=3):
    r = None
    for attempt in range(num_retries):
        try:
            r = requests.post(endpoint, data=inputs)
            return r.json()
        except:
            print(f"failed to extract JSON, retrying ...")
            time.sleep(1)
        else:
            break
    else: # all attempts failed
        time.sleep(60)  # wait for servers to reboot, as we've probably killed them all
        raise Exception(f"Failed to extract JSON response after {num_retries} retries. status code={r.status_code}")


    
def swap_data(response, trade_size, dex):
    """Extracts relevant data from a swap/rebalance API endpoint response"""

    summary = response['summary']
    if len(summary) != 1:
        raise Exception(f"len(trades) = {len(trades)}")
    else:
        summary = summary[0]

    trades = summary['trades']
    if not trades: return {} # Suggester has no trades
    if len(trades) != 1:
        raise Exception(f"len(trades) = {len(trades)}")
    
    orders = trades[0]['orders']
    if not orders: return {} # Suggester has no orders

    source_token = summary['sourceAsset']['symbol']
    source_amount_i = summary['sourceAmount']
    source_amount = real_amount(source_amount_i, source_token)
    
    destination_token = summary['destinationAsset']['symbol']
    destination_amount_i = summary['destinationAmount']
    destination_amount = real_amount(destination_amount_i, destination_token)
    
    # Assume there is only 1 order (seems to always be true)
    if len(orders) != 1:
        raise Exception(f"len(orders) = {len(orders)}")
    o = orders[0]
    exchange = o['exchange']['name']

    if dex == TOTLE_EX: # price with totle fee included
        price = 1.0 / float(summary['rate'])
    else: # price of the order (without totle fee)
        price = real_amount(o['sourceAmount'], source_token) / real_amount(o['destinationAmount'], destination_token)

    f = o['fee']
    exchange_fee_asset = f['asset']['symbol']
    exchange_fee = int(f['amount']) / 10**int(f['asset']['decimals'])

    f = summary['totleFee']
    totle_fee_asset = f['asset']['symbol']
    totle_fee = int(f['amount']) / 10**int(f['asset']['decimals'])
    
    f = summary['partnerFee']
    partner_fee_asset = f['asset']['symbol']
    partner_fee = int(f['amount']) / 10**int(f['asset']['decimals'])

    return {
        "tradeSize": trade_size,
        "sourceToken": source_token,
        "sourceAmount": source_amount,
        "destinationToken": destination_token,
        "destinationAmount": destination_amount,
        "exchange": exchange,
        "price": price,
        "exchangeFee": exchange_fee,
        "exchangeFeeToken": exchange_fee_asset,
        "totleFee": totle_fee,
        "totleFeeToken": totle_fee_asset,
        "partnerFee": partner_fee,
        "partnerFeeToken": partner_fee_asset,
    }

# Default parameters for swap. These can be overridden by passing params
DEFAULT_WALLET_ADDRESS = "0xD18CEC4907b50f4eDa4a197a50b619741E921B4D"
DEFAULT_TRADE_SIZE = 1.0 # the amount of ETH to spend or acquire, used to calculate amount
DEFAULT_MAX_SLIPPAGE_PERCENT = 10
DEFAULT_MIN_FILL_PERCENT = 80


def call_swap(dex, from_token, to_token, exchange=None, params={}, debug=None):
    """Calls the swap API endpoint with the given token pair and whitelisting exchange if given. Returns the result as a swap_data dict """
    # the swap_data dict is defined by the return statement in swap_data method above

    if from_token == 'ETH' and to_token == 'ETH':
        raise Exception('from_token and to_token cannot both be ETH')
    if from_token != 'ETH' and to_token != 'ETH':
        raise Exception('either from_token or to_token must be ETH')

    # trade_size is not an endpoint input so we extract it from params (after making a local copy)
    params = dict(params) # copy params to localize any modifications
    trade_size = params.get('tradeSize') or DEFAULT_TRADE_SIZE

    base_inputs = {
        "address": params.get('walletAddress') or DEFAULT_WALLET_ADDRESS,
        "config": {
            "transactions": False, # just get the prices
            #         "fillNonce": bool,
            "skipBalanceChecks": True,
        }
    }

    if exchange: # whitelist the given exchange:
        base_inputs["config"]["exchanges"] = { "list": [ exchanges[exchange] ], "type": "white" }

    if params.get('apiKey'):
        base_inputs['apiKey'] = params['apiKey']

    if params.get('partnerContract'): #
        base_inputs['partnerContract'] = params['partnerContract']

    from_token_addr = addr(from_token)
    to_token_addr = addr(to_token)
    max_mkt_slip = params.get('maxMarketSlippagePercent') or DEFAULT_MAX_SLIPPAGE_PERCENT
    max_exe_slip = params.get('maxExecutionSlippagePercent') or DEFAULT_MAX_SLIPPAGE_PERCENT
    min_fill = params.get('minFillPercent') or DEFAULT_MIN_FILL_PERCENT

    swap_inputs = {
        "swap": {
            "sourceAsset": from_token_addr,
            "destinationAsset": to_token_addr,
            "minFillPercent": min_fill,
            "maxMarketSlippagePercent": max_mkt_slip,
            "maxExecutionSlippagePercent": max_exe_slip,
            "isOptional": False,
        }
    }

    # add sourceAmount or destinationAmount
    if from_token == 'ETH':
        swap_inputs["swap"]["sourceAmount"] = eth_to_wei(trade_size)
    elif to_token == 'ETH':
        swap_inputs["swap"]["destinationAmount"] = eth_to_wei(trade_size)
    else:
        raise Exception('either from_token or to_token must be ETH')
        
    swap_inputs = pp({**swap_inputs, **base_inputs})

    swap_endpoint = SWAP_ENDPOINT
    if debug: print(f"REQUEST to {swap_endpoint}:\n{swap_inputs}\n\n")
    j = post_with_retries(swap_endpoint, swap_inputs)
    if debug: print(f"RESPONSE from {swap_endpoint}:\n{pp(j)}\n\n")

    if j['success']:
        return swap_data(j['response'], trade_size, dex)
    else: # some uncommon error we should look into
        raise Exception(j['response'], swap_inputs, pp(j))

def try_swap(dex, from_token, to_token, exchange=None, params={}, debug=None):
    """Wraps call_swap with an exception handler and returns None if an exception is caught"""
    sd = None
    try:
        sd = call_swap(dex, from_token, to_token, exchange=exchange, params=params, debug=debug)
    except Exception as e:
        r = e.args[0]
        if r['name'] in ["NotEnoughVolumeError", "MarketSlippageTooHighError"]:
            print(f"{dex}: Suggester returned no orders for {from_token}->{to_token} trade size={params['tradeSize']} ETH due to {r['name']}")
        else: # print req/resp for uncommon failures
            print(f"{dex}: swap raised {e}")
            print(f"FAILED REQUEST:\n{e.args[1]}\n")
            print(f"FAILED RESPONSE:\n{e.args[2]}\n\n")

    if sd:
        print(f"{dex}: swap {sd['sourceAmount']} {sd['sourceToken']} for {sd['destinationAmount']} {sd['destinationToken']} on {sd['exchange']} price={sd['price']} exchange_fee={sd['exchangeFee']} {sd['exchangeFeeToken']} totle_fee={sd['totleFee']} {sd['totleFeeToken']} partner_fee={sd['partnerFee']} {sd['partnerFeeToken']}")

    return sd


##############################################################################################
#
# functions to compute and print price differences
#

def compare_prices(token, supported_pairs, params=None, debug=False):
    """Returns a dict containing Totle and other DEX prices"""

    savings = {}
    from_token, to_token, bidask = ('ETH', token, 'ask') if params['orderType'] == 'buy' else (token, 'ETH', 'bid')

    # Get the best price using Totle's aggregated order books
    totle_sd = try_swap(TOTLE_EX, from_token, to_token, params=params, debug=debug)

    if totle_sd:
        swap_prices = {TOTLE_EX: totle_sd['price']}
        supported_pairs[totle_sd['exchange']].append((from_token, to_token))

        # Compare to best prices from other DEXs
        for dex in best_prices(token, bidask):
            if dex != totle_sd['exchange']:
                dex_sd = try_swap(dex, from_token, to_token, exchange=dex, params=params, debug=debug)
                if dex_sd:
                    swap_prices[dex] = dex_sd['price']
                    if swap_prices[dex] < 0.0:
                        raise Exception(f"{dex} had an invalid price={swap_prices[dex]}")
                    supported_pairs[dex].append((from_token, to_token))


        if TOTLE_EX in swap_prices and len(swap_prices) > 1:  # there is data to compare
            totle_price = swap_prices[TOTLE_EX]
            other_exchanges = [k for k in swap_prices if k != TOTLE_EX]
            for e in other_exchanges:
                ratio = totle_price/swap_prices[e] # totle_price assumed lower
                pct_savings = 100 - (100.0 * ratio)
                savings[e] = {'time': datetime.datetime.now().isoformat(), 'action': params['orderType'], 'pct_savings': pct_savings, 'totle_used':totle_sd['exchange'], 'totle_price': totle_price, 'exchange_price': swap_prices[e]}
                print(f"Totle saved {pct_savings:.2f} percent vs {e} {params['orderType']}ing {token} on {totle_sd['exchange']} trade size={params['tradeSize']} ETH")
        else:
            print(f"Could not compare {token} prices. Only valid price was {swap_prices}")

    return savings

def print_average_savings(all_savings):
    for trade_size in all_savings:
        print(f"\nAverage Savings trade size = {trade_size} ETH")
        print_average_savings_by_dex(all_savings[trade_size])

def print_average_savings_by_dex(avg_savings):
    dex_savings = { k: [] for k in exchanges }
    savings = [avg_savings[t] for t in avg_savings if avg_savings[t]]
    for s in savings:
        for e in s:
            dex_savings[e].append(s[e]['pct_savings'])

    for e in dex_savings:
        sum_e, n_samples = sum(dex_savings[e]), len(dex_savings[e])
        if n_samples:
            print(f"   {e}: {sum_e/n_samples:.2f}% ({n_samples} samples)")
        else:
            print(f"   {e}: - (no samples)")

    return dex_savings

def print_csv(csv_file):
    with open(csv_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['time', 'action', 'trade_size', 'token', 'exchange', 'exchange_price', 'totle_used','totle_price', 'pct_savings'])
        writer.writeheader()

        for trade_size in all_savings:
            trade_size_savings = all_savings[trade_size]
            for token in trade_size_savings:
                token_savings = trade_size_savings[token]
                for exchange in token_savings:
                    row = {**{'trade_size': trade_size, 'token' : token, 'exchange': exchange}, **token_savings[exchange]}
                    writer.writerow(row)


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
    print(f"Totle failed to get the best price {fails}/{samples} times ({100*fails/samples:.2f}%)")


    
##############################################################################################
#
# Main program
#

# Define program arguments
parser = argparse.ArgumentParser(description='Run price comparisons')
parser.add_argument('--sell', dest='orderType', action='store_const', const='sell', default='buy', help='execute sell orders (default is buy)')
parser.add_argument('tradeSize', type=float, nargs='?', default=DEFAULT_TRADE_SIZE, help='the size (in ETH) of the order')
parser.add_argument('maxMarketSlippagePercent', nargs='?', default=DEFAULT_MAX_SLIPPAGE_PERCENT, type=int, help='acceptable percent of slippage')
parser.add_argument('maxExecutionSlippagePercent', nargs='?', default=DEFAULT_MAX_SLIPPAGE_PERCENT, type=int, help='acceptable percent of execution slippage')
parser.add_argument('minFillPercent', nargs='?', default=DEFAULT_MIN_FILL_PERCENT, type=int, help='acceptable percent of amount to acquire')
parser.add_argument('partnerContract', nargs='?', help='address of partner fee contract')
parser.add_argument('apiKey', nargs='?', help='API key')

params = vars(parser.parse_args())

# Redirect output to a .txt file in outputs directory
# Comment out the following 3 lines to see output on console
d = datetime.datetime.today()
filename = f"outputs/{d.year}-{d.month:02d}-{d.day:02d}_{d.hour:02d}-{d.minute:02d}-{d.second:02d}_{params['orderType']}_{params['tradeSize']}-{params['maxMarketSlippagePercent']}-{params['maxExecutionSlippagePercent']}-{params['minFillPercent']}"
output_filename = f"{filename}.txt"
print(f"sending output to {output_filename} ...")
sys.stdout = open(output_filename, 'w')

TOKENS = all_liquid_tokens()
TRADE_SIZES = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]

all_savings, all_supported_pairs = {}, {}
order_type = params['orderType']

for trade_size in TRADE_SIZES:
    params['tradeSize'] = trade_size
    print(d, params)
    all_savings[trade_size] = {}
    all_supported_pairs[trade_size] = {e: [] for e in exchanges}
    for token in TOKENS:
        if token not in tokens:
            print(f"'{token}' is not a listed token or is not tradable")
            continue
        print(f"\n----------------------------------------\n{order_type} {token} trade size = {trade_size} ETH")
        show_prices(token, order_type)
        savings = compare_prices(token, all_supported_pairs[trade_size], params, debug=False)
        all_savings[trade_size][token] = savings


print_csv(f"{filename}.csv")
print_average_savings(all_savings)
print_supported_pairs(all_supported_pairs)
report_failures(all_savings)

