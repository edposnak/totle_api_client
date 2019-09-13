import sys
import json
import requests
import time

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

def call_swap(dex, from_token, to_token, exchange=None, params={}, verbose=True, debug=None):
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

def try_swap(dex, from_token, to_token, exchange=None, params={}, verbose=True, debug=None):
    """Wraps call_swap with an exception handler and returns None if an exception is caught"""
    sd = None
    try:
        sd = call_swap(dex, from_token, to_token, exchange=exchange, params=params, verbose=verbose, debug=debug)
    except Exception as e:
        normal_exceptions = ["NotEnoughVolumeError", "MarketSlippageTooHighError"]
        r = e.args[0]
        if type(r) == dict and r['name'] in normal_exceptions:
            if verbose: print(f"{dex}: Suggester returned no orders for {from_token}->{to_token} trade size={params['tradeSize']} ETH due to {r['name']}")
        else: # print req/resp for uncommon failures
            print(f"{dex}: swap raised {type(e).__name__}: {e.args[0]}")
            if len(e.args) > 1: print(f"FAILED REQUEST:\n{pp(e.args[1])}\n")
            if len(e.args) > 2: print(f"FAILED RESPONSE:\n{pp(e.args[2])}\n\n")

    if sd:
        if dex == TOTLE_EX:
            test_type = 'A'
            dex_used = sd['totleUsed']
            fee_data = f"(includes exchange_fee={sd['exchangeFee']} {sd['exchangeFeeToken']} totle_fee={sd['totleFee']} {sd['totleFeeToken']})" # leave out partner_fee since it is always 0
        else:
            test_type = 'B'
            dex_used = exchange
            fee_data = f"(includes exchange_fee={sd['exchangeFee']} {sd['exchangeFeeToken']})"

        if verbose: print(f"{test_type}: swap {sd['sourceAmount']} {sd['sourceToken']} for {sd['destinationAmount']} {sd['destinationToken']} on {dex_used} price={sd['price']} {fee_data}")

    return sd

