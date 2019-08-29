import sys
import json
import requests
import argparse
import datetime
import time
import csv

##############################################################################################
#
# Library functions for exchanges and tokens
#
# get exchanges

API_BASE = 'https://api.totle.com'
EXCHANGES_ENDPOINT = API_BASE + '/exchanges'
TOKENS_ENDPOINT = API_BASE + '/tokens'
SWAP_ENDPOINT = API_BASE + '/swap'

r = requests.get(EXCHANGES_ENDPOINT).json()
exchanges = { e['name']: e['id'] for e in r['exchanges'] if e['enabled'] }
exchange_by_id = { e['id']: e['name'] for e in r['exchanges'] }
TOTLE_EX = 'Totle' # 'Totle' is used for comparison with other exchanges

def get_integrated_dexs():
    """determines the integrated DEXs by querying the suggester and checking for a valid response"""
    integrated_dexs = []
    for dex in exchanges:
        try:
            # call_swap will either succeed (meaning the dex is integrated) or raise an exception
            call_swap(dex, 'ETH', 'DAI', exchange=dex, params={'tradeSize':0.1}, debug=False)
            integrated_dexs.append(dex)

        except Exception as e:
            r = e.args[0]
            if type(r) == dict and r['name'] == 'NoUsableExchangeError':
                pass # dex is not integrated
            else:
                # TODO: consider trying different tokens (e.g. ['DAI', 'USDC', 'BAT']) if this error occurs
                if len(e.args) > 1: print(f"FAILED REQUEST:\n{e.args[1]}\n")
                if len(e.args) > 2: print(f"FAILED RESPONSE:\n{pp(e.args[2])}\n\n")
                e_info = r['name'] if type(r) == dict else f"{type(e).__name__} {e}"
                raise Exception(f"call_swap for {dex} raised {e_info} while trying to determine integrated dexs")

    return integrated_dexs

# get tokens
r = requests.get(TOKENS_ENDPOINT).json()
tokens = { t['symbol']: t['address'] for t in r['tokens'] if t['tradable']}
token_decimals = { t['symbol']: t['decimals'] for t in r['tokens'] if t['tradable']}

def addr(token):
    """Returns the string address that identifies the token"""
    return tokens[token]

def int_amount(float_amount, token):
    """Returns the integer amount of token units for the given float_amount and token"""
    return int(float(float_amount) * (10**token_decimals[token]))

def real_amount(int_amount, token):
    """Returns the decimal number of tokens for the given integer amount and token"""
    return int(int_amount) / (10**token_decimals[token])

def pp(data):
    return json.dumps(data, indent=3)


##############################################################################################
#
# functions to call swap and extract data
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
        raise Exception(f"Failed to extract JSON response after {num_retries} retries. status code={r.status_code}", inputs, {})

    
def swap_data(response, trade_size, dex):
    """Extracts relevant data from a swap/rebalance API endpoint response"""

    summary = response['summary']
    if len(summary) != 1:
        raise Exception(f"len(trades) = {len(trades)}", {}, response)
    else:
        summary = summary[0]

    trades = summary['trades']
    if not trades: return {} # Suggester has no trades
    if len(trades) != 1:
        raise Exception(f"len(trades) = {len(trades)}", {}, response)
    
    orders = trades[0]['orders']
    if not orders: return {} # Suggester has no orders

    source_token = summary['sourceAsset']['symbol']
    destination_token = summary['destinationAsset']['symbol']
    
    # Assume there is only 1 order (seems to always be true)
    if len(orders) != 1:
        raise Exception(f"len(orders) = {len(orders)}", {}, response)
    o = orders[0]
    exchange = o['exchange']['name']

    if dex == TOTLE_EX: # price with totle fee included
        source_amount = real_amount(summary['sourceAmount'], source_token)
        destination_amount = real_amount(summary['destinationAmount'], destination_token)

    else: # price of the order (without totle fee)
        source_amount = real_amount(o['sourceAmount'], source_token)
        destination_amount = real_amount(o['destinationAmount'], destination_token)
        
    price = source_amount / destination_amount

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
    """Calls the swap API endpoint with the given token pair and whitelisting exchange if given. Returns the result as a swap_data dict or raises an exception if the call failed"""
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
    eth_amount = int_amount(trade_size, 'ETH')
    if from_token == 'ETH':
        swap_inputs["swap"]["sourceAmount"] = eth_amount
    elif to_token == 'ETH':
        swap_inputs["swap"]["destinationAmount"] = eth_amount
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
        raise Exception(j['response'], swap_inputs, j)

def try_swap(dex, from_token, to_token, exchange=None, params={}, debug=None):
    """Wraps call_swap with an exception handler and returns None if an exception is caught"""
    sd = None
    try:
        sd = call_swap(dex, from_token, to_token, exchange=exchange, params=params, debug=debug)
    except Exception as e:
        normal_exceptions = ["NotEnoughVolumeError", "MarketSlippageTooHighError"]
        r = e.args[0]
        if type(r) == dict and r['name'] in normal_exceptions:
            print(f"{dex}: Suggester returned no orders for {from_token}->{to_token} trade size={params['tradeSize']} ETH due to {r['name']}")
        else: # print req/resp for uncommon failures
            print(f"{dex}: swap raised {type(e).__name__} {e}")
            if len(e.args) > 1: print(f"FAILED REQUEST:\n{e.args[1]}\n")
            if len(e.args) > 2: print(f"FAILED RESPONSE:\n{pp(e.args[2])}\n\n")

    if sd:
        if dex == TOTLE_EX:
            test_type = 'A'
            fee_data = f"(includes exchange_fee={sd['exchangeFee']} {sd['exchangeFeeToken']} totle_fee={sd['totleFee']} {sd['totleFeeToken']})" # leave out partner_fee since it is always 0
        else:
            test_type = 'B'
            fee_data = f"(includes exchange_fee={sd['exchangeFee']} {sd['exchangeFeeToken']})"

        print(f"{test_type}: swap {sd['sourceAmount']} {sd['sourceToken']} for {sd['destinationAmount']} {sd['destinationToken']} on {sd['exchange']} price={sd['price']} {fee_data}")

    return sd


##############################################################################################
#
# functions to compute and print price differences
#

def compare_prices(token, supported_pairs, non_liquid_tokens, params=None, debug=False):
    """Returns a dict containing Totle and other DEX prices"""

    savings = {}
    from_token, to_token, bidask = ('ETH', token, 'ask') if params['orderType'] == 'buy' else (token, 'ETH', 'bid')

    # Get the best price using Totle's aggregated order books
    totle_sd = try_swap(TOTLE_EX, from_token, to_token, params=params, debug=debug)

    if totle_sd:
        swap_prices = {TOTLE_EX: totle_sd['price']}
        supported_pairs[totle_sd['exchange']].append((from_token, to_token))

        # Compare to best prices from other DEXs
        for dex in [dex for dex in supported_pairs if dex != totle_sd['exchange']]:
            dex_sd = try_swap(dex, from_token, to_token, exchange=dex, params=params, debug=debug)
            if dex_sd:
                swap_prices[dex] = dex_sd['price']
                if swap_prices[dex] < 0.0:
                    raise Exception(f"{dex} had an invalid price={swap_prices[dex]}")
                supported_pairs[dex].append((from_token, to_token))


        if TOTLE_EX in swap_prices and len(swap_prices) > 1:  # there is data to compare
            totle_price = swap_prices[TOTLE_EX]
            for e in [k for k in swap_prices if k != TOTLE_EX]:
                ratio = totle_price/swap_prices[e] # totle_price assumed lower
                pct_savings = 100 - (100.0 * ratio)
                savings[e] = {'time': datetime.datetime.now().isoformat(), 'action': params['orderType'], 'pct_savings': pct_savings, 'totle_used':totle_sd['exchange'], 'totle_price': totle_price, 'exchange_price': swap_prices[e]}
                print(f"Totle saved {pct_savings:.2f} percent vs {e} {params['orderType']}ing {token} on {totle_sd['exchange']} trade size={params['tradeSize']} ETH")
        else:
            print(f"Could not compare {token} prices. Only valid price was {swap_prices}")
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

TRADE_SIZES = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]

liquid_tokens = [t for t in tokens if t != 'ETH'] # start with all tradable tokens
all_savings, all_supported_pairs = {}, {}
order_type = params['orderType']

integrated_dexs = get_integrated_dexs()
print(f"using the following DEXs, which appear to be integrated: {integrated_dexs}")

for trade_size in TRADE_SIZES:
    params['tradeSize'] = trade_size
    print(d, params)

    non_liquid_tokens = []
    all_savings[trade_size] = {}
    all_supported_pairs[trade_size] = {dex: [] for dex in integrated_dexs} # compare_prices() depends on these keys being present
    print(f"\n========================================\nNEW ROUND TRADE SIZE = {trade_size} ETH trying {len(liquid_tokens)} liquid tokens")
    for token in liquid_tokens:
        print(f"\n----------------------------------------\n{order_type} {token} trade size = {trade_size} ETH")
        savings = compare_prices(token, all_supported_pairs[trade_size], non_liquid_tokens, params, debug=False)
        if savings:
            all_savings[trade_size][token] = savings

    # don't try non_liquid_tokens at higher trade sizes
    print(f"\n\nremoving {len(non_liquid_tokens)} non-liquid tokens for the next round")
    liquid_tokens = [ t for t in liquid_tokens if t not in non_liquid_tokens ]


print_csv(f"{filename}.csv")
print_average_savings(all_savings)
print_supported_pairs(all_supported_pairs)
report_failures(all_savings)

