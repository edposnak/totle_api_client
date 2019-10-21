import sys
import json
import requests
import time

##############################################################################################
#
# Library functions for exchanges and tokens
#
# get exchanges

TOTLE_API_KEY = '7d2adad7-13a5-4388-ad4e-6ee05dd5925d'

API_BASE = 'https://api.totle.com'
EXCHANGES_ENDPOINT = API_BASE + '/exchanges'
TOKENS_ENDPOINT = API_BASE + '/tokens'
SWAP_ENDPOINT = API_BASE + '/swap'

DATA_ENDPOINT = API_BASE + '/data'
PAIRS_ENDPOINT = DATA_ENDPOINT + '/pairs'
TRADES_ENDPOINT = DATA_ENDPOINT + '/trades' # trades/DAI/ETH?limit=100&page=1&begin=156992998&end=156900998
DATA_EXCHANGES_ENDPOINT = DATA_ENDPOINT + '/exchanges'

# pretty print function
def pp(data):
    return json.dumps(data, indent=3)

# custom exception type
class TotleAPIException(Exception):
    def __init__(self, message, request, response):
        if not message and response:
            # JSON may be either a response or a response container
            if 'response' in response: response = response['response']
            message = f"{response['name']} ({response['code']}): {response['message']}"

        super().__init__(message, request, response)

            

# get exchanges
r = requests.get(EXCHANGES_ENDPOINT).json()
exchanges = { e['name']: e['id'] for e in r['exchanges'] }
enabled_exchanges = [ e['name'] for e in r['exchanges'] if e['enabled'] ]

r = requests.get(DATA_EXCHANGES_ENDPOINT).json()
data_exchanges = { e['name']: e['id'] for e in r['exchanges'] }
data_exchanges_by_id = { v:k for k,v in data_exchanges.items() }


# get tokens
r = requests.get(TOKENS_ENDPOINT).json()
tokens = { t['symbol']: t['address'] for t in r['tokens'] if t['tradable']}
token_decimals = { t['symbol']: t['decimals'] for t in r['tokens'] if t['tradable']}

data_tokens_by_addr = { t['address']: t['symbol'] for t in r['tokens'] }

def addr(token):
    """Returns the string address that identifies the token"""
    return tokens[token]

def int_amount(float_amount, token):
    """Returns the integer amount of token units for the given float_amount and token"""
    return int(float(float_amount) * (10**token_decimals[token]))

def real_amount(int_amount, token):
    """Returns the decimal number of tokens for the given integer amount and token"""
    return int(int_amount) / (10**token_decimals[token])

TOTLE_EX = 'Totle' # 'Totle' is used for comparison with other exchanges

##############################################################################################
#
# functions to convert response JSON into price data

def get_summary_data(response):
    summary = response['summary']
    if len(summary) != 1:
        raise ValueError(f"len(summary) = {len(summary)}")
    else:
        summary = summary[0]
    source_token = summary['sourceAsset']['symbol']
    source_div = 10**int(summary['sourceAsset']['decimals'])
    destination_token = summary['destinationAsset']['symbol']
    destination_div = 10**int(summary['destinationAsset']['decimals'])

    base_token = summary['baseAsset']['symbol'] if 'baseAsset' in summary else None

    return summary, base_token, source_token, source_div, destination_token, destination_div

def calc_exchange_fees(trade):
    orders = trade['orders']
    fee_tokens = [ o['fee']['asset']['symbol'] for o in orders ]
    if len(set(fee_tokens)) != 1:
        raise ValueError(f"different exchange fee tokens in same trade {fee_tokens}", {}, response)
        
    exchange_fee_token = fee_tokens[0]
    exchange_fee_div = 10**int(orders[0]['fee']['asset']['decimals'])
    exchange_fee = sum([ int(o['fee']['amount']) for o in orders ]) / exchange_fee_div

    return exchange_fee_token, exchange_fee

def get_exchange_fees(trades):
    # In the two trade case, we use the trade that has positive exchange fees 
    t0_exchange_fee_token, t0_exchange_fee = calc_exchange_fees(trades[0])
    t1_exchange_fee_token, t1_exchange_fee = calc_exchange_fees(trades[1])
    
    # If only one trade has positive exchange fees then use only that trade
    if t0_exchange_fee > 0 and t1_exchange_fee == 0:
        return t0_exchange_fee_token, t0_exchange_fee
    elif t1_exchange_fee > 0 and t0_exchange_fee == 0:
        return t1_exchange_fee_token, t1_exchange_fee
    elif t0_exchange_fee == 0 and t1_exchange_fee == 0:
        return t0_exchange_fee_token, t0_exchange_fee
    else: # return strings assuming this is just used for printing
        return f"{t0_exchange_fee_token} and {t1_exchange_fee_token}", f"{t0_exchange_fee} and {t1_exchange_fee}" 

def get_dex_pairs(trades):
    dex_pairs = {}
    for o in [order for t in trades for order in t['orders']]:
        dex_pairs[o['exchange']['name']] = [o['sourceAsset']['symbol'], o['destinationAsset']['symbol']]

    return dex_pairs
    
def get_totle_fees(summary):
    tf = summary['totleFee']
    totle_fee_token = tf['asset']['symbol']
    totle_fee_div = 10**int(tf['asset']['decimals'])
    totle_fee = int(tf['amount']) / totle_fee_div
    
    pf = summary['partnerFee']
    partner_fee_token = pf['asset']['symbol']
    partner_fee_div = 10**int(pf['asset']['decimals'])
    partner_fee = int(pf['amount']) / partner_fee_div
        
    return totle_fee_token, totle_fee, partner_fee_token, partner_fee

def sum_amounts(trade, src_dest, summary_token):
    asset_key, amount_key = src_dest + 'Asset', src_dest + 'Amount'
    total_amount = 0

    for o in trade['orders']:
        order_token = o[asset_key]['symbol']
        if order_token != summary_token:
            raise ValueError(f"order {asset_key}={order_token} but summary {asset_key}={summary_token}")
        total_amount += int(o[amount_key])
        
    return total_amount

HACK_UNTIL_SUMMARY_FIXED=True

def adjust_for_totle_fees(is_totle, source_amount, destination_amount, summary):
    """adjust source and destination amounts so price reflects paying totle fee"""
    # Assumes source_amount and destination amount are sums of order amounts

    buying_tokens_with_eth = summary['sourceAsset']['symbol'] == 'ETH'
    summary_destination_token = summary['destinationAsset']['symbol']

    totle_fee_token = summary['totleFee']['asset']['symbol']
    totle_fee_pct = float(summary['totleFee']['percentage'])

    # Until the summary is fixed we can just assume summary amounts correctly include Totle fees in
    # all cases (maybe not a good assumption) and subtract them out for non is_totle cases
    if HACK_UNTIL_SUMMARY_FIXED:
        summary_source_amount = int(summary['sourceAmount'])
        summary_destination_amount = int(summary['destinationAmount'])
        if is_totle:
            return summary_source_amount, summary_destination_amount
        else: # subtract out Totle fee
            source_amount, destination_amount = summary_source_amount, summary_destination_amount
            if buying_tokens_with_eth: # user could have gotten more destination tokens
                destination_amount = summary_destination_amount / (1 - (totle_fee_pct / 100))
            else: # for sells, user could have paid less than source_amount 
                source_amount = summary_source_amount * (1 - (totle_fee_pct / 100))
            return source_amount, destination_amount
    

    if not is_totle: # subtract fees
        # Only subtract fees for buys where Totle takes fees in the intermediate token. For buys without
        # an intermediate token, destination_amount > summary_destination_amount and for all sells,
        # source_amounts < summary source_amount, so the fees will be added by changing source_amount or
        # destination_amount in the is_totle case below
        if buying_tokens_with_eth and totle_fee_token != summary_destination_token: # Totle fee is in intermediate token
            destination_amount /= (1 - (totle_fee_pct / 100))

    else: # add fees for most is_totle cases
        summary_source_amount = int(summary['sourceAmount'])
        summary_destination_amount = int(summary['destinationAmount'])
        totle_fee_amount = int(summary['totleFee']['amount'])
        
        if not buying_tokens_with_eth: 
            # For sells, Totle requires more source tokens from the user's wallet than are shown in the
            # orders JSON. The summary_source_amount is larger than the sum of the orders source_amounts
            # by the Totle fee (denominated in source tokens) so we just use it to account for Totle's fees
            if source_amount < summary_source_amount:
                source_amount = summary_source_amount
            else:
                raise ValueError(f"Totle's fee not accounted for in summary. Summary source_amount={summary_source_amount}, sum of orders source_amount={source_amount}")
                
        else: # buying tokens with ETH
            # For buys source_amount always equals summary_source_amount because Totle takes its fees
            # from the destination or intermediate tokens. 
            if totle_fee_token == summary_destination_token:
                # When Totle takes fees in the destination token we can just subtract out the totle_fee
                # and the destination_amount should end up equalling the summary_destination_amount
                destination_amount -= totle_fee_amount
            else: # totle fees are in the intermediate token
                if totle_fee_token != summary['baseAsset']['symbol']:
                    raise ValueError(f"totle_fee_token={totle_fee_token} does not match intermediate token={summary['baseAsset']['symbol']}")

                # WHY WE DO NOTHING HERE:
                # When Totle takes fees in the intermediate token the sum of the order amounts will equal
                # the summary amounts, and we'll need to adjust (subtract out) Totle fees from the amounts
                # computed for whitelisted DEXs (see not is_totle case above)
                #
                # There is currently a bug in buy (thru base) situations where Totle's fees aren't accounted for.
                # All intermediate tokens acquired in the first trade are used to acquire destination assets in
                # the second. We don't have this problem for sells, because the summary_source_amount is greater
                # than the sum or order source_amounts, i.e. the fee is accounted for in the summary. If the bug
                # is fixed as expected, by sending 99.75% of the first trade's proceeds to the second trade, then
                # the summary likely won't account for Totle's fees like it does for sells and the fee will have
                # to be subtracted (see not is_totle case above)

        # Summary amounts should now add up in the is_totle case 
        # Suggester bugs (floating point to decimal?) mean things don't always add up exactly
        if source_amount != summary_source_amount:
            raise ValueError(f"adjusted orders source_amount={source_amount} different from summary source_amount={summary_source_amount}")

        if destination_amount != summary_destination_amount:
            raise ValueError(f"adjusted orders destination_amount={destination_amount} different from summary destination_amount={summary_destination_amount}")
    return source_amount, destination_amount
        

def swap_data(response, is_totle):
    """Extracts relevant data from a swap/rebalance API endpoint response"""

    try:
        summary, base_token, source_token, source_div, destination_token, destination_div = get_summary_data(response)

        if 'trades' not in summary: return {} # Suggester has no trades
        trades = summary['trades']
        if len(trades) > 2: # currently can only handle going through 1 additional token
            raise ValueError(f"len(trades) = {len(trades)}", {}, response)

        exchange_fee_token, exchange_fee = calc_exchange_fees(trades[0]) if len(trades) == 1 else get_exchange_fees(trades)
        
        totle_used, dex_pairs = None, None
        totle_fee_token, totle_fee, partner_fee_token, partner_fee = None, None, None, None
        if is_totle:
            dex_pairs = get_dex_pairs(trades)
            totle_used = list(dex_pairs.keys())
            totle_fee_token, totle_fee, partner_fee_token, partner_fee = get_totle_fees(summary)
            
        source_amount = sum_amounts(trades[0], 'source', source_token)
        destination_amount = sum_amounts(trades[-1], 'destination', destination_token)
        source_amount, destination_amount = adjust_for_totle_fees(is_totle, source_amount, destination_amount, summary)
        source_amount = source_amount / source_div
        destination_amount = destination_amount / destination_div
        
        trade_size = source_amount if source_token == 'ETH' else destination_amount
        price = source_amount / destination_amount

        return {
            "tradeSize": trade_size,
            "sourceToken": source_token,
            "sourceAmount": source_amount,
            "destinationToken": destination_token,
            "destinationAmount": destination_amount,
            "totleUsed": totle_used,
            "dexPairs": dex_pairs, 
            "baseToken": base_token,
            "price": price,
            "exchangeFee": exchange_fee,
            "exchangeFeeToken": exchange_fee_token,
            "totleFee": totle_fee,
            "totleFeeToken": totle_fee_token,
            "partnerFee": partner_fee,
            "partnerFeeToken": partner_fee_token,
        }
    except ValueError as e:
        raise ValueError(e.args[0], {}, response)


##############################################################################################
#
# functions to call swap with retries
#

def post_with_retries(endpoint, inputs, num_retries=3, debug=False):
    if debug: print(f"REQUEST to {SWAP_ENDPOINT}:\n{pp(inputs)}\n\n")

    for attempt in range(num_retries):
        try:
            # weirdly, inputs has to be converted to a string input to work with Totle
            r = requests.post(endpoint, data=json.dumps(inputs))
            j = r.json()
            if debug: print(f"RESPONSE from {SWAP_ENDPOINT}:\n{pp(j)}\n\n")
            return j
        except:
            print(f"failed to extract JSON, retrying ...")
            time.sleep(1)
        else:
            break
    else: # all attempts failed
        time.sleep(60)  # wait for servers to reboot, as we've probably killed them all
        raise TotleAPIException(f"Failed to extract JSON response after {num_retries} retries.", inputs, {})


    
# Default parameters for swap. These can be overridden by passing params
DEFAULT_WALLET_ADDRESS = "0xD18CEC4907b50f4eDa4a197a50b619741E921B4D"
DEFAULT_TRADE_SIZE = 1.0 # the amount of ETH to spend or acquire, used to calculate amount
DEFAULT_MAX_SLIPPAGE_PERCENT = 10
DEFAULT_MIN_FILL_PERCENT = 80
DEFAULT_CONFIG = {
    "transactions": False, # just get the prices
    #         "fillNonce": bool,
    "skipBalanceChecks": True,
}


def swap_inputs(from_token, to_token, exchange=None, params={}):
    """returns a dict of the swap API endpoint with the given token pair and whitelisting exchange, if given."""
    # the swap_data dict is defined by the return statement in swap_data method above

    if from_token == 'ETH' and to_token == 'ETH':
        raise ValueError('from_token and to_token cannot both be ETH')
    if from_token != 'ETH' and to_token != 'ETH':
        raise ValueError('either from_token or to_token must be ETH')

    params = dict(params) # defensive copy, params should not be modified

    base_inputs = {
        "address": params.get('walletAddress') or DEFAULT_WALLET_ADDRESS,
        "config": { **DEFAULT_CONFIG, **(params.get('config') if 'config' in params else {} ) }
    }

    if exchange: # whitelist the given exchange
        base_inputs["config"]["exchanges"] = { "list": [ exchanges[exchange] ], "type": "white" }

    base_inputs['apiKey'] = params.get('apiKey') or TOTLE_API_KEY

    if params.get('partnerContract'):
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
    trade_size = params.get('tradeSize') or DEFAULT_TRADE_SIZE
    eth_amount = int_amount(trade_size, 'ETH')
    if from_token == 'ETH':
        swap_inputs["swap"]["sourceAmount"] = eth_amount
    elif to_token == 'ETH':
        swap_inputs["swap"]["destinationAmount"] = eth_amount
    else:
        raise ValueError('either from_token or to_token must be ETH')
        
    return {**swap_inputs, **base_inputs}

def handle_swap_exception(e, dex, from_token, to_token, params, verbose=True):
    has_args1, has_args2 = len(e.args) > 1 and bool(e.args[1]), len(e.args) > 2 and bool(e.args[2])
    normal_exceptions = ["NotEnoughVolumeError", "MarketSlippageTooHighError"]

    # Check for normal exceptions, maybe print them
    if has_args2 and type(e.args[2]) == dict and 'name' in e.args[2] and e.args[2]['name'] in normal_exceptions:
        if verbose: print(f"{dex}: Suggester returned no orders for {from_token}->{to_token} trade size={params['tradeSize']} ETH due to {e.args[2]['name']}")

    else: # print req/resp for uncommon failures
        print(f"{dex}: swap raised {type(e).__name__}: {e.args[0]}")
        if verbose:
            if has_args1: print(f"FAILED REQUEST:\n{pp(e.args[1])}\n")
            if has_args2: print(f"FAILED RESPONSE:\n{pp(e.args[2])}\n\n")

def try_swap(dex, from_token, to_token, exchange=None, params={}, verbose=True, debug=False):
    """calls swap endpoint Returns the result as a swap_data dict, {} if the call failed"""
    try:
        is_totle = dex == TOTLE_EX
        inputs = swap_inputs(from_token, to_token, exchange, params)
        j = post_with_retries(SWAP_ENDPOINT, inputs, debug=debug)

        if 'success' not in j:
            raise TotleAPIException("Unexpected JSON response", inputs, j)
        elif not j['success']:
            raise TotleAPIException(None, inputs, j)
        else:
            sd = swap_data(j['response'], is_totle)

        if sd and verbose:
            if is_totle:
                test_type, dex_used = 'A', '/'.join(sd['totleUsed'])
                fee_data = f"(includes exchange_fee={sd['exchangeFee']} {sd['exchangeFeeToken']} totle_fee={sd['totleFee']} {sd['totleFeeToken']})" # leave out partner_fee since it is always 0
            else:
                test_type, dex_used = 'B', exchange
                fee_data = f"(includes exchange_fee={sd['exchangeFee']} {sd['exchangeFeeToken']})"
            print(f"{test_type}: swap {sd['sourceAmount']} {sd['sourceToken']} for {sd['destinationAmount']} {sd['destinationToken']} on {dex_used} price={sd['price']} {fee_data}")

        return sd

    except Exception as e:
        handle_swap_exception(e, dex, from_token, to_token, params, verbose=verbose)
        return {}


##############################################################################################
#
# functions to call data APIs
#

# get token pairs
r = requests.get(PAIRS_ENDPOINT).json()
if r['success']:
    supported_pairs = r['response']
else: # some uncommon error we should look into
    raise TotleAPIException(None, None, r)

# get token pairs
def get_trades(base_asset, quote_asset, limit=None, page=None, begin=None, end=None):
    """Returns the latest trades on all exchanges for the given base/quote assets"""
    if limit or page or begin or end:
        query = { k:v for k,v in vars().items() if v and k not in ['base_asset', 'quote_asset'] }
    else:
        query = {}

    url = TRADES_ENDPOINT + f"/{base_asset}/{quote_asset}"

    j = requests.get(url, params=query).json()

    if j['success']:
        return j['response']
    else: # some uncommon error we should look into
        raise TotleAPIException(None, locals(), j)

