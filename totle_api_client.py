import sys
import json
import requests
import argparse
import datetime
import time

##############################################################################################
#
# Library functions for exchanges, tokens, and prices
#
# get exchanges

API_BASE = 'https://services.totlesystem.com'
EXCHANGES_ENDPOINT = API_BASE + '/exchanges'
TOKENS_ENDPOINT = API_BASE + '/tokens'
PRICES_ENDPOINT = API_BASE + '/tokens/prices'
REBALANCE_ENDPOINT = API_BASE + '/rebalance'
SWAP_ENDPOINT = API_BASE + '/swap'

r = requests.get(EXCHANGES_ENDPOINT).json()
exchanges = { e['name']: e['id'] for e in r['exchanges'] }
exchange_by_id = { e['id']: e['name'] for e in r['exchanges'] }
TOTLE_EX = 'Totle' # 'Totle' is used for comparison with other exchanges

# get tokens
r = requests.get(TOKENS_ENDPOINT).json()
tokens = { t['symbol']: t['address'] for t in r['tokens'] if t['tradable']}
token_symbols = { tokens[sym]: sym for sym in tokens }
token_decimals = { t['symbol']: t['decimals'] for t in r['tokens'] if t['tradable']}

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
all_prices = requests.get(PRICES_ENDPOINT).json()['response']

# We assume that the prices endpoints returns the lowest 'ask' and highest 'bid' price for
# a given token. If it does not, then that would explain why rebalance returns orders
# with lower prices than the ask price
def price(token, exchange):
    """Returns lowest ask price in ETH for the given token on the given exchange"""
    return float(all_prices[tokens[token]][str(exchanges[exchange])]['ask'])

def best_ask_price(token):
    """Returns lowest ask price in ETH for the given token across all exchanges"""
    ap = all_prices[tokens[token]]
    return min([ float(ap[v]['ask']) for v in ap ])

def best_bid_price(token):
    """Returns highest bid price in ETH for the given token across all exchanges"""
    ap = all_prices[tokens[token]]
    return max([ float(ap[v]['bid']) for v in ap ])

def best_prices(token, bidask='ask'):
    """Returns lowest ask or highest bid prices in ETH for all exchanges"""
    token_prices = all_prices[tokens[token]]
    return { exchange_by_id[int(i)]: float(token_prices[i][bidask]) for i in token_prices }

def show_prices(from_token, to_token):
    if from_token == 'ETH':
        print(f"Lowest ask prices for {to_token}: {pp(best_prices(to_token, 'ask'))}")
    elif to_token == 'ETH':
        print(f"Highest bid prices for {from_token}: {pp(best_prices(from_token, 'bid'))}")
    else:
        # once ERC20/ERC20 swaps, which have both buys and sells, are supported by the swap_data
        # extractor method, then we can get rid of the exception below and do something useful
        raise Exception("ERC20/ERC20 swaps haven't been implemented yet")

def wei_to_eth(wei_amount):
    """Returns a decimal value of the amount of ETH for the given wei_amount"""
    return int(wei_amount) / 10**18

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

def swap_data(response, trade_size):
    """Extracts relevant data from a swap/rebalance API endpoint response"""
    summary = response['summary']
    buys, sells = summary['buys'], summary['sells']

    # This method assumes the summary includes either buys or sells. It would need to be modified to
    # handle results from a call to swap with an ERC20/ERC20 pair, which would contain both buys and sells.
    if buys and sells:
        err_msg = f"expected payload to have either buys or sells, but it has both.\nresponse={pp(response)}"
        raise Exception(err_msg)

    if not buys and not sells: return {} # Suggester has no orders

    action, orders = ('buy', buys) if buys else ('sell', sells)
    exchange, token_addr = orders[0]['exchange'], orders[0]['token']
    token_sym = token_symbols[token_addr]

    i_amount = sum([int(o['amount']) for o in orders])
    i_fee = sum([int(o['fee']) for o in orders])
    weighted_price = sum([int(o['amount']) * float(o['price']) for o in orders])

    r_amount = real_amount(i_amount, token_sym)
    r_fee = wei_to_eth(i_fee) if action == 'buy' else real_amount(i_fee, token_sym)
    price = weighted_price / i_amount

    return {
        "action": action,
        "tradeSize": trade_size,
        "weiAmount": int(response['ethValue']),
        "ethAmount": wei_to_eth(response['ethValue']),
        "token": token_addr,
        "tokenSymbol": token_sym,
        "exchange": exchange,
        "price": price,
        "intAmount": i_amount,
        "realAmount": r_amount,
        "intFee": i_fee,
        "realFee": r_fee
    }

# Default parameters for swap. These can be overridden by passing params
DEFAULT_WALLET_ADDRESS = "0xD18CEC4907b50f4eDa4a197a50b619741E921B4D"
DEFAULT_TRADE_SIZE = 1.0 # the amount of ETH to spend or acquire, used to calculate amount
DEFAULT_MIN_SLIPPAGE_PERCENT = 10
DEFAULT_MIN_FILL_PERCENT = 80

def call_swap(from_token, to_token, exchange=None, params=None, debug=None):
    """Calls the swap API endpoint with the given token pair and whitelisting exchange if given. Returns the result as a swap_data dict """
    # the swap_data dict is defined by the return statement in swap_data method above

    # trade_size is not an endpoint input so we extract it from params (after making a local copy)
    params = dict(params)
    trade_size = params.pop('tradeSize') if params and 'tradeSize' in params else DEFAULT_TRADE_SIZE

    base_inputs = {
        "address": DEFAULT_WALLET_ADDRESS,
        "minSlippagePercent": DEFAULT_MIN_SLIPPAGE_PERCENT,
        "minFillPercent": DEFAULT_MIN_FILL_PERCENT
    }
    if params:
        base_inputs = {**base_inputs, **params}

    if exchange: # whitelist the given exchange:
        base_inputs["exchanges"] = { "list": [ exchanges[exchange] ], "type": "white" } 

    from_token_addr = addr(from_token)
    to_token_addr = addr(to_token)

    if from_token_addr == ETH_ADDRESS and to_token_addr == ETH_ADDRESS:
        raise Exception('from_token and to_token cannot both be ETH')

    if from_token_addr != ETH_ADDRESS and to_token_addr != ETH_ADDRESS:
        swap_endpoint = SWAP_ENDPOINT
        real_amount_to_sell = trade_size / best_bid_price(from_token)
        amount_to_sell = int_amount(real_amount_to_sell, from_token)
        if debug: print(f"selling {real_amount_to_sell} {from_token} tokens ({amount_to_sell} units)")
        swap_inputs = {
            "swap": {
                "from": from_token_addr,
                "to": to_token_addr,
                "amount": amount_to_sell
            },
        }
    
    else: # for now we have to call the rebalance endpoint because swap doesn't support ETH
        swap_endpoint = REBALANCE_ENDPOINT

        if from_token_addr == ETH_ADDRESS and to_token_addr != ETH_ADDRESS:
            real_amount_to_buy = trade_size / best_ask_price(to_token)
            amount_to_buy = int_amount(real_amount_to_buy, to_token)
            if debug: print(f"buying {real_amount_to_buy} {to_token} tokens ({amount_to_buy} units)")
            swap_inputs = {
                "buys": [ {
                    "token": addr(to_token),
                    "amount": amount_to_buy
                } ],
            }

        else: # from_token_addr != ETH_ADDRESS and to_token_addr == ETH_ADDRESS
            real_amount_to_sell = trade_size / best_bid_price(from_token)
            amount_to_sell = int_amount(real_amount_to_sell, from_token)
            if debug: print(f"selling {real_amount_to_sell} {from_token} tokens ({amount_to_sell} units)")
            swap_inputs = {
                "sells": [ {
                    "token": addr(from_token),
                    "amount": amount_to_sell
                } ],
            }


    swap_inputs = pp({**swap_inputs, **base_inputs})
    if debug: print(f"REQUEST to {swap_endpoint}:\n{swap_inputs}\n\n")
    j = post_with_retries(swap_endpoint, swap_inputs)
    if debug: print(f"RESPONSE from {swap_endpoint}:\n{pp(j)}\n\n")

    if j['success']:
        return swap_data(j['response'], trade_size)
    elif j['response'].startswith('Not enough orders'):
        pass # this is a common failure to fill
    else:
        print(f"FAILED REQUEST:\n{swap_inputs}\n")
        print(f"FAILED RESPONSE:\n{pp(j)}\n\n")
        raise Exception(j['response'])

def post_with_retries(endpoint, inputs, num_retries=3):
    r = None
    for attempt in range(num_retries):
        try:
            r = requests.post(endpoint, data=inputs)
            return r.json()
        except:
            print(f"failed to extract JSON, retrying ...")
        else:
            break
    else: # all attempts failed
        time.sleep(60)  # wait for servers to reboot, as we've probably killed them all
        raise Exception(f"Failed to extract JSON response after {num_retries} retries. Response={r.text}")


def print_results(label, sd):
    """Prints a formatted results string based on given label and swap_data sd"""
    print(f"{label}: {sd['action']} {sd['realAmount']} {sd['tokenSymbol']} for {sd['ethAmount']} ETH on {sd['exchange']} price={sd['price']} fee={sd['realFee']}")


def compare_prices(from_token, to_token, supported_pairs, params=None, debug=False):
    """Returns a dict containing Totle and other DEX prices"""
    savings = {}
    totle_sd = None

    # Get the best price using Totle's aggregated order books
    try:
        totle_sd = call_swap(from_token, to_token, params=params, debug=debug)
    except Exception as e:
        print(f"{TOTLE_EX}: swap raised {e}")
        return savings

    if totle_sd:
        print_results(TOTLE_EX, totle_sd)
        swap_prices = {TOTLE_EX: totle_sd['price']}
        supported_pairs[totle_sd['exchange']].append((from_token, to_token))

        # Compare to best prices from other DEXs
        for dex in best_prices(to_token):
            if dex != totle_sd['exchange']:
                dex_sd = None
                try:
                    dex_sd = call_swap(from_token, to_token, dex, params=params, debug=debug)
                except Exception as e:
                    print(f"{dex}: swap raised {e}")
                else:
                    if dex_sd:
                        print_results(dex, dex_sd)
                        swap_prices[dex] = dex_sd['price']
                        supported_pairs[dex].append((from_token, to_token))
                    else:
                        print(f"{dex}: Suggester returned no orders for {from_token}->{to_token} trade size={params['tradeSize']} ETH")


        if len(swap_prices) > 1:  # there is data to compare
            other_exchanges = [k for k in swap_prices if k != TOTLE_EX]
            for e in other_exchanges:
                if swap_prices[TOTLE_EX] < 0.0:
                    print(
                        f"Totle savings could not be computed since Totle received an invalid price={swap_prices[TOTLE_EX]} buying {token} on {chosen_dex}")
                elif swap_prices[e] < 0.0:
                    print(
                        f"Totle savings could not be computed since {e} received an invalid price={swap_prices[e]} buying {token}")
                else:
                    savings[e] = 100 - (100.0 * (swap_prices[TOTLE_EX] / swap_prices[e]))
                    print(f"Totle saved {savings[e]:.2f} percent vs {e} buying {to_token} on {totle_sd['exchange']} trade size={params['tradeSize']} ETH")
        else:
            print(f"No {to_token} prices for comparison were found on other DEXs")

    else:
        print(f"{TOTLE_EX}: Suggester returned no orders for {from_token}->{to_token} trade size={params['tradeSize']} ETH")

    return savings

def print_average_savings(all_savings):
    for trade_size in all_savings:
        print_average_savings_by_dex(all_savings[trade_size], trade_size)

def print_average_savings_by_dex(avg_savings, trade_size):
    dex_savings = { k: [] for k in exchanges }
    savings = [avg_savings[t] for t in avg_savings if avg_savings[t]]
    for s in savings:
        for e in s:
            dex_savings[e].append(s[e])

    for e in dex_savings:
        l = dex_savings[e]
        n_samples = len(l)
        if n_samples:
            print(f"Average savings vs {e} for trade size {trade_size} ETH is {sum(l)/n_samples:.2f}% ({n_samples} samples)")
        else:
            print(f"No savings comparison samples for {e}")

    return dex_savings

def print_supported_pairs(all_supported_pairs):
    for trade_size in all_supported_pairs:
        print(f"\nAt trade size of {trade_size} ETH:")
        for e in all_supported_pairs[trade_size]:
            pairs = [f"{t}/{f}" for f, t in all_supported_pairs[trade_size][e]]
            print(f"   {e} supports {pairs}")

##############################################################################################
#
# Main program
#


# Accept tradeSize, minSlippagePercent, and minFillPercent as program arguments
parser = argparse.ArgumentParser(description='Run price comparisons')
parser.add_argument('tradeSize', type=float, nargs='?', default=DEFAULT_TRADE_SIZE, help='the size (in ETH) of the order')
parser.add_argument('minSlippagePercent', nargs='?', default=DEFAULT_MIN_SLIPPAGE_PERCENT, type=float, help='acceptable percent of slippage')
parser.add_argument('minFillPercent', nargs='?', default=DEFAULT_MIN_FILL_PERCENT, type=float, help='acceptable percent of amount to acquire')

params = vars(parser.parse_args())

# Redirect output to a .txt file in outputs directory
# Comment out the following 3 lines to see output on console
d = datetime.datetime.today()
output_filename = f"outputs/{d.year}-{d.month:02d}-{d.day:02d}_{d.hour:02d}-{d.minute:02d}-{d.second:02d}_{params['tradeSize']}-{params['minSlippagePercent']}-{params['minFillPercent']}.txt"
print(f"sending output to {output_filename} ...")
sys.stdout = open(output_filename, 'w')


TOKENS_TO_BUY = all_liquid_tokens()

# For now, all price comparisons are done by buying the ERC20 token with ETH (i.e. from_token == 'ETH')
from_token = 'ETH'

TRADE_SIZES = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]

all_savings, all_supported_pairs = {}, {}

for trade_size in TRADE_SIZES:
    params['tradeSize'] = trade_size
    print(d, params)
    all_savings[trade_size] = {}
    all_supported_pairs[trade_size] = {e: [] for e in exchanges}
    for to_token in TOKENS_TO_BUY:
        print(f"\n----------------------------------------\nBUY {to_token} trade size = {trade_size} ETH")
        if to_token not in tokens:
            print(f"'{to_token}' is not a listed token or is not tradable")
            continue
        show_prices(from_token, to_token)
        savings = compare_prices(from_token, to_token, all_supported_pairs[trade_size], params, debug=False)
        all_savings[trade_size][to_token] = savings

# print(pp(all_savings))
print_average_savings(all_savings)
print_supported_pairs(all_supported_pairs)



