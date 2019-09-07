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
exchanges = { e['name']: e['id'] for e in r['exchanges'] }
enabled_exchanges = [ e['name'] for e in r['exchanges'] if e['enabled'] ]
exchange_by_id = { e['id']: e['name'] for e in r['exchanges'] }
TOTLE_EX = 'Totle' # 'Totle' is used for comparison with other exchanges

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
    totle_used = orders[0]['exchange']['name'] if dex == TOTLE_EX else None
                
    source_token = orders[0]['sourceAsset']['symbol']
    source_div = 10**int(orders[0]['sourceAsset']['decimals'])
    destination_token = orders[0]['destinationAsset']['symbol']
    destination_div = 10**int(orders[0]['destinationAsset']['decimals'])
    source_amount = 0
    destination_amount = 0
    exchange_fee_token = orders[0]['fee']['asset']['symbol']
    exchange_fee_div =  10**int(orders[0]['fee']['asset']['decimals'])
    exchange_fee = 0

    for o in orders:
        if dex == TOTLE_EX: # Update totle_used if Totle used different exchanges
            if o['exchange']['name'] != totle_used: 
                totle_used += f"/{o['exchange']['name']}"

        # get weighted sum of the order source/destination/fee amounts
        if o['sourceAsset']['symbol'] != source_token or o['destinationAsset']['symbol'] != destination_token:
            raise Exception(f"mismatch between orders' source/destination tokens", {}, response)
        source_amount += int(o['sourceAmount']) 
        destination_amount += int(o['destinationAmount'])

        f = o['fee']
        if f['asset']['symbol'] != exchange_fee_token:
            raise Exception(f"mismatch between orders' exchange fee tokens", {}, response)
        exchange_fee += int(f['amount'])
        
    if dex == TOTLE_EX:
        # set up to compute price with totle fee included (i.e. subtracted from destinationAmount)
        tf = summary['totleFee']
        totle_fee_token = tf['asset']['symbol']
        totle_fee_div = 10**int(tf['asset']['decimals'])
        totle_fee = int(tf['amount'])
        pf = summary['partnerFee']
        partner_fee_token = pf['asset']['symbol']
        partner_fee_div = 10**int(pf['asset']['decimals'])
        partner_fee = int(pf['amount'])
        
        if totle_fee_token != destination_token:
            raise Exception(f"totle_fee_token = {totle_fee_token} does not match destination_token = {destination_token}", {}, response)
        summary_source_amount = int(summary['sourceAmount'])
        # For sells, Totle requires more source tokens from the user's wallet than are shown in
        # the orders JSON. There appears to be an undocumented order that buys ETH to pay the fee.
        # In this case, we must use the summary source amount to compute the price using Totle.
        if totle_fee_token == 'ETH':
            source_amount = summary_source_amount
        # For buys source_amount must always equal summary_source_amount because Totle takes its
        # fees from the destination_tokens, and these are always accounted for in the orders JSON
        else: 
            destination_amount -= totle_fee

        if source_amount != summary_source_amount:
            raise Exception(f"source_amount = {source_amount} does not match summary_source_amount = {summary_source_amount}", {}, response)

        summary_destination_amount = int(summary['destinationAmount'])
        if destination_amount != summary_destination_amount:
            raise Exception(f"destination_amount = {destination_amount} does not match summary_destination_amount = {summary_destination_amount}", {}, response)

        totle_fee = totle_fee / totle_fee_div
        partner_fee = partner_fee / partner_fee_div

    else:
        totle_fee_token = None
        totle_fee = None
        partner_fee_token = None
        partner_fee = None

    source_amount = source_amount / source_div
    destination_amount = destination_amount / destination_div
    exchange_fee = exchange_fee / exchange_fee_div
        
    price = source_amount / destination_amount

    return {
        "tradeSize": trade_size,
        "sourceToken": source_token,
        "sourceAmount": source_amount,
        "destinationToken": destination_token,
        "destinationAmount": destination_amount,
        "totleUsed": totle_used,
        "price": price,
        "exchangeFee": exchange_fee,
        "exchangeFeeToken": exchange_fee_token,
        "totleFee": totle_fee,
        "totleFeeToken": totle_fee_token,
        "partnerFee": partner_fee,
        "partnerFeeToken": partner_fee_token,
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
            print(f"{dex}: swap raised {type(e).__name__}: {e.args[0]}")
            if len(e.args) > 1: print(f"FAILED REQUEST:\n{pp(e.args[1])}\n")
            if len(e.args) > 2: print(f"FAILED RESPONSE:\n{pp(e.args[2])}\n\n")

    if sd:
        if dex == TOTLE_EX:
            test_type = 'A'
            fee_data = f"(includes exchange_fee={sd['exchangeFee']} {sd['exchangeFeeToken']} totle_fee={sd['totleFee']} {sd['totleFeeToken']})" # leave out partner_fee since it is always 0
        else:
            test_type = 'B'
            fee_data = f"(includes exchange_fee={sd['exchangeFee']} {sd['exchangeFeeToken']})"

        print(f"{test_type}: swap {sd['sourceAmount']} {sd['sourceToken']} for {sd['destinationAmount']} {sd['destinationToken']} on {sd['totleUsed']} price={sd['price']} {fee_data}")

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
        totle_used = totle_sd['totleUsed']
        swap_prices = {TOTLE_EX: totle_sd['price']}
        if totle_used not in supported_pairs:
            supported_pairs[totle_used] = []
        supported_pairs[totle_used].append((from_token, to_token))

        # Compare to best prices from other DEXs
        for dex in [dex for dex in supported_pairs if dex != totle_used]:
            dex_sd = try_swap(dex, from_token, to_token, exchange=dex, params=params, debug=debug)
            if dex_sd:
                swap_prices[dex] = dex_sd['price']
                if swap_prices[dex] < 0.0:
                    raise Exception(f"{dex} had an invalid price={swap_prices[dex]}")
                supported_pairs[dex].append((from_token, to_token))


        other_dexs = [k for k in swap_prices if k != TOTLE_EX]
        if other_dexs:  # there is data to compare
            totle_price = swap_prices[TOTLE_EX]
            for e in other_dexs:
                ratio = totle_price/swap_prices[e] # totle_price assumed lower
                pct_savings = 100 - (100.0 * ratio)
                savings[e] = {'time': datetime.datetime.now().isoformat(), 'action': params['orderType'], 'pct_savings': pct_savings, 'totle_used':totle_used, 'totle_price': totle_price, 'exchange_price': swap_prices[e]}
                print(f"Totle saved {pct_savings:.2f} percent vs {e} {params['orderType']}ing {token} on {totle_used} trade size={params['tradeSize']} ETH")
        else:
            print(f"Could not compare {token} prices. Only valid price was {swap_prices}")
            non_liquid_tokens.append(token) # expect the same result at higher trade sizes
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

# liquid_dexs = enabled_exchanges
# don't waste time on non-liquid dexes
non_liquid_dexs = [ 'Compound', '0xMesh' ]
liquid_dexs = [e for e in enabled_exchanges if e not in non_liquid_dexs ] 

liquid_tokens = [t for t in tokens if t != 'ETH'] # start with all tradable tokens
all_savings, all_supported_pairs = {}, {}
order_type = params['orderType']

with open(f"{filename}.csv", 'w', newline='') as csvfile:
    csv_writer = csv.DictWriter(csvfile, fieldnames=['time', 'action', 'trade_size', 'token', 'exchange', 'exchange_price', 'totle_used','totle_price', 'pct_savings'])
    csv_writer.writeheader()

    for trade_size in TRADE_SIZES:
        params['tradeSize'] = trade_size
        print(d, params)

        non_liquid_tokens = []
        all_savings[trade_size] = {}
        all_supported_pairs[trade_size] = {dex: [] for dex in liquid_dexs} # compare_prices() uses these keys to know what dexs to try
        print(f"\n========================================\nNEW ROUND TRADE SIZE = {trade_size} ETH trying {len(liquid_tokens)} liquid tokens on the following DEXs: {liquid_dexs}")
        for token in liquid_tokens:
            print(f"\n----------------------------------------\n{order_type} {token} trade size = {trade_size} ETH")
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

