import sys
import time
import functools
import json
import traceback
from collections import defaultdict

import requests
import token_utils

##############################################################################################
#
# Library functions for exchanges and tokens
#
# get exchanges

TOTLE_API_KEY = '99306bc3-e304-43ee-b350-111e61548083'

API_BASE = 'https://api.totle.com'

EXCHANGES_ENDPOINT = API_BASE + '/exchanges'
TOKENS_ENDPOINT = API_BASE + '/tokens'
SWAP_ENDPOINT = API_BASE + '/swap/coinbase'

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
            if response.get('name') and response.get('code') and response.get('message'):
                message = f"{response['name']} ({response['code']}): {response['message']}"
            else:
                message = str(response)

        super().__init__(message, request, response)

def name():
    return 'Totle' # 'Totle' is used for comparison with other exchanges


DEX_NAME_MAP = {'0x V2': '0x V2', '0x V3': '0x V3', '0xMesh': '0xMesh', 'Aave': 'Aave', 'Bancor': 'Bancor', 'Balancer': 'Balancer', 'Chai': 'Chai', 'Compound': 'Compound',
                'Curve.fi Compound': 'CurveFi Compound', 'Curve.fi Pool #1': 'CurveFi Pool #1', 'Curve.fi Pool #2': 'CurveFi Pool #2', 'Curve.fi Pool #3': 'CurveFi Pool #3', 'Curve.fi 3pool': 'Curve.fi 3pool',
                'Curve.fi USDT': 'CurveFi USDT', 'Curve.fi Y': 'CurveFi Y', 'Curve.fi PAX': 'CurveFi Pax', 'Curve.fi sUSDV2': 'CurveFi sUSDV2', 'Curve.fi renBTC': 'CurveFi Ren', 'Curve.fi sBTC': 'CurveFi sBTC',
                'Curve.fi hBTC': 'CurveFi hBTC', 'Curve.fi tBTC': 'Curve.fi tBTC', 'CurveFi gUSD': 'CurveFi gUSD',  'CurveFi dUSD': 'CurveFi dUSD',  'CurveFi hUSD':  'CurveFi hUSD', 'CurveFi mUSD':  'CurveFi mUSD',
                'CurveFi USDK': 'CurveFi USDK',  'CurveFi USDN': 'CurveFi USDN', 'CurveFi RSV': 'CurveFi RSV', 'DODO': 'DODO',
                'Ether Delta': 'EtherDelta', 'Fulcrum': 'Fulcrum', 'IdleFinance' : 'IdleFinance', 'IEarnFinance': 'IEarnFinance', 'Kyber': 'Kyber', 'Mooniswap': 'Mooniswap',
                'Oasis': 'Oasis', 'PMM': 'PMM', 'SetProtocol': 'SetProtocol', 'StableCoinSwap': 'Stablecoinswap', 'Sushi Swap': 'Sushiswap', 'Swerve': 'Swerve', 'Uniswap': 'Uniswap', 'Uniswap V2': 'UniswapV2'}


def exchanges():
    return { e['name']: e['id'] for e in exchanges_json() }

def exchanges_by_id():
    return { **data_exchanges_by_id(), **{ v:k for k,v in exchanges().items() } }

def enabled_exchanges():
    return [ e['name'] for e in exchanges_json() if e['enabled'] ]

@functools.lru_cache(1)
def exchanges_json():
    print(f"EXCHANGES_ENDPOINT={EXCHANGES_ENDPOINT}")
    r = requests.get(EXCHANGES_ENDPOINT).json()
    return r['exchanges']

def data_exchanges_by_id():
    return { v:k for k,v in data_exchanges().items() }

@functools.lru_cache(1)
def data_exchanges():
    r = requests.get(DATA_EXCHANGES_ENDPOINT).json()
    return { e['name']: e['id'] for e in r['exchanges'] }

def get_snapshot(response_id):
    print(f"get_snapshot fetching: https://totle-api-snapshot.s3.amazonaws.com/{response_id}")
    return requests.get(f"https://totle-api-snapshot.s3.amazonaws.com/{response_id}").json()


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
    # Totle no longer has a 'fee' field associated with orders
    return None, 0

    orders = trade['orders']
    non_zero_fee_orders = [ o for o in orders if int(o['fee']['amount']) != 0 ] # ignore orders with no exchange fees

    non_zero_fee_tokens = [ o['fee']['asset']['symbol'] for o in non_zero_fee_orders ]
    if len(set(non_zero_fee_tokens)) == 0:
        return None, 0
    if len(set(non_zero_fee_tokens)) != 1:
        raise ValueError(f"different exchange fee tokens in same trade {non_zero_fee_tokens}")
        
    exchange_fee_token = non_zero_fee_tokens[0]
    exchange_fee_div = 10**int(non_zero_fee_orders[0]['fee']['asset']['decimals'])
    exchange_fee = sum([ int(o['fee']['amount']) for o in non_zero_fee_orders ]) / exchange_fee_div

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


def get_totle_fees(summary):
    if 'totleFee' not in summary: return None, None, None, None # Totle has removed fees from the summary

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

def adjust_for_totle_fees(is_totle, source_amount, destination_amount, summary):
    """adjust source and destination amounts so price reflects paying totle fee"""

    if 'totleFee' not in summary: return source_amount, destination_amount

    # Assumes source_amount and destination amount are sums of order amounts
    buying_tokens_with_eth = summary['sourceAsset']['symbol'] == 'ETH'
    summary_source_token = summary['sourceAsset']['symbol']
    summary_destination_token = summary['destinationAsset']['symbol']

    totle_fee_token = summary['totleFee']['asset']['symbol']
    totle_fee_pct = float(summary['totleFee']['percentage'])

    if is_totle:
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

        else:  # buying tokens with ETH
            if totle_fee_token == summary_source_token:
                # When Totle takes fees in the source token we can just add the totle_fee
                # and the source_amount should end up equal to the summary_source_amount
                if summary_source_amount != source_amount+totle_fee_amount:
                    print(f"summary_source_amount == source_amount+totle_fee_amount={summary_source_amount == source_amount+totle_fee_amount}")
                    print(f"    source_amount={source_amount} totle_fee_amount={totle_fee_amount}")
                    print(f"    summary_source_amount={summary_source_amount} source_amount+totle_fee_amount={source_amount + totle_fee_amount}")
                source_amount += totle_fee_amount
            else: # fee is in destination or base token
                # source_amount always equals summary_source_amount
                if source_amount != summary_source_amount:
                    raise ValueError(f"Totle fees were taken in destination token, but source_amount ({source_amount} is different from summary_source_amount ({summary_source_amount}")

                if totle_fee_token == summary_destination_token:
                    # When Totle takes fees in the destination token we can just subtract the totle_fee
                    # and the destination_amount should end up equal to the summary_destination_amount
                    destination_amount -= totle_fee_amount
                else:  # totle fees are in the intermediate token

                    base_token = summary['baseAsset']['symbol']  # key error means fees were not taken in base token
                    if totle_fee_token != base_token:
                        raise ValueError(f"totle_fee_token={totle_fee_token} does not match intermediate token={base_token}")

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
                    # to be subtracted (see not buying_tokens_with_eth case above)

        # Summary amounts should now add up for all is_totle cases
        # Suggester bugs? and conversions from floating point to decimal mean things don't always add up exactly
        # e.g. Totle: swap raised ValueError: adjusted orders destination_amount=605285284 different from summary destination_amount=605285283
        if source_amount != summary_source_amount:
            raise ValueError(f"adjusted orders source_amount={source_amount} different from summary source_amount={summary_source_amount}")

        if destination_amount != summary_destination_amount:
            raise ValueError(f"adjusted orders destination_amount={destination_amount} different from summary destination_amount={summary_destination_amount}")

    else: # getting DEX price from Totle by whitelisting
        # Only subtract fees for buys where Totle takes fees in the intermediate token.
        if buying_tokens_with_eth and totle_fee_token != summary_destination_token: # Totle fee is in intermediate token
            destination_amount /= (1 - (totle_fee_pct / 100))
        # For buys without an intermediate token, destination_amount > summary_destination_amount and for all
        # sells, source_amount < summary_source_amount, so the and source_amount and destination_amount represent
        # the amounts without fees.

    return source_amount, destination_amount
        
def get_split(trade):
    dex_src_amounts, sum_source_amount = defaultdict(int), 0
    reported_splits = defaultdict(float)
    for o in trade['orders']:
        order_source_amount = int(o['sourceAmount'])
        dex = o['exchange']['name']
        dex_src_amounts[dex] += order_source_amount
        sum_source_amount += order_source_amount
        reported_splits[dex] += float(o['splitPercentage']) # TODO: is splitPercentage always an integer?

    computed_splits = {dex: round(100 * src_amount / sum_source_amount, 1) for dex, src_amount in dex_src_amounts.items()}
    # print(f"computed_splits={computed_splits}\nreported_splits={dict(reported_splits)}")
    return computed_splits


def swap_data(response, is_totle, request={}):
    """Extracts relevant data from a swap API endpoint response"""
    try:
        response_id = response['id']
        summary, base_token, source_token, source_div, destination_token, destination_div = get_summary_data(response)

        if 'trades' not in summary: return {} # Suggester has no trades
        trades = summary['trades']
        if len(trades) > 2: # currently can only handle going through 1 additional token
            raise ValueError(f"len(trades) = {len(trades)}", {}, response)

        exchange_fee_token, exchange_fee = calc_exchange_fees(trades[0]) if len(trades) == 1 else get_exchange_fees(trades)
        
        totle_used, totle_splits = None, None
        totle_fee_token, totle_fee, partner_fee_token, partner_fee = None, None, None, None
        if is_totle:
            totle_splits = {}
            if len(trades) == 1:
                # when no base_token is used, totle_splits look like other agg splits e.g.
                # totle_splits = {'Uniswap':10, 'Kyber':90}
                # totle_used = ['Uniswap', 'Kyber']
                totle_splits = get_split(trades[0])
                totle_used = list(totle_splits.keys())
            else: # multiple trades => multiple splits
                # when  there are multiple trades totle_splits and totle_used looks like this:
                # totle_splits = { 'ETH/DAI': {'Uniswap':10, 'Kyber':90}, 'DAI/PAX' : {'PMM': 100} } }
                # totle_used = ['Uniswap', 'Kyber', 'PMM']
                dexs_used = set()
                for trade in trades:
                    pair_label = f"{trade['destinationAsset']['symbol']}/{trade['sourceAsset']['symbol']}"
                    split = get_split(trade)
                    totle_splits[pair_label] = split
                    dexs_used |= split.keys()
                totle_used = list(dexs_used)

            totle_fee_token, totle_fee, partner_fee_token, partner_fee = get_totle_fees(summary)

            # dex_pairs = {}
            # for t in trades:
            #     for o in t['orders']:
            #         dex_pairs[o['exchange']['name']] = [o['sourceAsset']['symbol'], o['destinationAsset']['symbol']]
            # if len(dex_pairs) > 1:
            #     print(f"\n\ndex_pairs={dex_pairs} for {destination_token}/{source_token} (base_token={base_token}) ")
            #     print(json.dumps(response, indent=3))


        source_amount = sum_amounts(trades[0], 'source', source_token)
        destination_amount = sum_amounts(trades[-1], 'destination', destination_token)
        source_amount, destination_amount = adjust_for_totle_fees(is_totle, source_amount, destination_amount, summary)
        source_amount = source_amount / source_div
        destination_amount = destination_amount / destination_div

        if request.get('swap'):
            trade_size = source_amount if 'sourceAmount' in request['swap'] else destination_amount
        else: # hack to infer from JSON response assuming the specified amount ends with 0000's (not used in production)
            trade_size = source_amount if summary['sourceAmount'].endswith('0000') else destination_amount

        price = source_amount / destination_amount

        return {
            "responseId": response_id,
            "tradeSize": trade_size,
            "sourceToken": source_token,
            "sourceAmount": source_amount,
            "destinationToken": destination_token,
            "destinationAmount": destination_amount,
            "totleUsed": totle_used,
            "totleSplits": totle_splits,
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
        raise ValueError(e.args[0], request, response)


##############################################################################################
#
# functions to call swap with retries
#

def post_with_retries(endpoint, inputs, num_retries=3, debug=False, timer=False):
    if debug: print(f"REQUEST to {endpoint}:\n{pp(inputs)}\n\n")

    timer_start = time.time()
    for attempt in range(num_retries):
        try:
            # for production inputs has to be converted to a string input to work
            r = requests.post(endpoint, data=json.dumps(inputs))
            j = r.json()

            timer_end = time.time()
            if timer: print(f"call to {endpoint} {pp(inputs)} took {timer_end - timer_start:.1f} seconds")
            if debug: print(f"RESPONSE from {endpoint}:\n{pp(j)}\n\n")
            return j
        except Exception as e:
            print(f"failed to extract JSON: {e} \nretrying ...")
            time.sleep(1)

    # all attempts failed
    time.sleep(60)  # wait for servers to reboot, as we've probably killed them all
    raise TotleAPIException(f"Failed to extract JSON response after {num_retries} retries.", inputs, {})


    
# Default parameters for swap. These can be overridden by passing params
# DEFAULT_WALLET_ADDRESS = "0xD18CEC4907b50f4eDa4a197a50b619741E921B4D"
DEFAULT_WALLET_ADDRESS = "0x8d12A197cB00D4747a1fe03395095ce2A5CC6819" # Ether Delta address with lots of tokens
DEFAULT_TRADE_SIZE = 1.0 # the amount of ETH to spend or acquire, used to calculate amount
DEFAULT_MAX_SLIPPAGE_PERCENT = 50
DEFAULT_MIN_FILL_PERCENT = 80
DEFAULT_CONFIG = {
    "transactions": False, # just get the prices
    #         "fillNonce": bool,
    "skipBalanceChecks": True,
    "debugMode": True,
    "strategy": {"main": "curves", "backup":"curves"}
}


DISABLE_SMART_ROUTING = False

def swap_inputs(from_token, to_token, exchange=None, params={}):
    """returns a dict of the swap API endpoint with the given token pair and whitelisting exchange, if given."""
    # the swap_data dict is defined by the return statement in swap_data method above
    params = dict(params) # defensive copy, params should not be modified

    base_inputs = {
        "address": params.get('walletAddress') or DEFAULT_WALLET_ADDRESS,
        "config": { **DEFAULT_CONFIG, **(params.get('config') if 'config' in params else {} ) }
    }

    if exchange: # whitelist the given exchange
        base_inputs["config"]["exchanges"] = { "list": [ exchanges()[exchange] ], "type": "white" }

    if DISABLE_SMART_ROUTING:
        base_inputs["config"]["disablePaths"] = True

    base_inputs['apiKey'] = params.get('apiKey') or TOTLE_API_KEY

    if params.get('partnerContract'):
        base_inputs['partnerContract'] = params['partnerContract']

    from_token_addr = token_utils.addr(from_token)
    to_token_addr = token_utils.addr(to_token)
    max_mkt_slip = params.get('maxMarketSlippagePercent') or DEFAULT_MAX_SLIPPAGE_PERCENT
    max_exe_slip = params.get('maxExecutionSlippagePercent') or DEFAULT_MAX_SLIPPAGE_PERCENT
    min_fill = params.get('minFillPercent') or DEFAULT_MIN_FILL_PERCENT

    swap_inputs = {
        "swap": {
            "sourceAsset": from_token_addr,
            "destinationAsset": to_token_addr,
            "minFillPercent": min_fill,
            "highExecutionSlippage": True,
            "maxMarketSlippagePercent": max_mkt_slip,
            "maxExecutionSlippagePercent": max_exe_slip,
            "isOptional": False,
        }
    }

    # add sourceAmount or destinationAmount
    if 'fromAmount' in params:
        swap_inputs['swap']['sourceAmount'] = token_utils.int_amount(params['fromAmount'], from_token)
    elif 'toAmount' in params:
        swap_inputs['swap']['destinationAmount'] = token_utils.int_amount(params['toAmount'], to_token)
    else: # implied behavior based on params['trade_size'] and which token is 'ETH'
        raise ValueError('either fromAmount or toAmount must be provided (tradeSize is no longer supported)')

    return {**swap_inputs, **base_inputs}

def handle_swap_exception(e, dex, from_token, to_token, params, verbose=True):
    has_args1, has_args2 = len(e.args) > 1 and bool(e.args[1]), len(e.args) > 2 and bool(e.args[2])
    # normal_messages = ["Endpoint request timed out", "The market slippage is higher than acceptable percentage.", "We couldn't find enough orders to fill your request for"] # this response does not come with error code or name, just a message
    normal_errors = {
        2100: "We couldn't find enough orders to fill your request for ",
        2101: "The market slippage is higher than acceptable percentage."
    }
    # Check for normal exceptions, maybe print them
    if has_args2 and type(e.args[2]) == dict and e.args[2].get('code') in normal_errors:
        if verbose:
            eth_amount = params.get('fromAmount') or params.get('toAmount')
            error_info, id = f"{e.args[2]['name']} {e.args[2]['code']}: {e.args[2]['message']}", e.args[2].get('id')
            print(f"{dex}: Suggester returned no orders for {from_token}->{to_token} ({eth_amount} {from_token}) (id={id}) due to {error_info}")
    else: # print req/resp for uncommon failures
        print(f"{dex}: swap {to_token} for {from_token} raised {type(e).__name__}: {e.args[0]}")
        traceback.print_exc(file=sys.stdout)
        if has_args1: print(f"FAILED REQUEST:\n{pp(e.args[1])}\n")
        if has_args2: print(f"FAILED RESPONSE:\n{pp(e.args[2])}\n\n")

def try_swap(label, from_token, to_token, exchange=None, params={}, verbose=True, debug=False):
    """calls swap endpoint Returns the result as a swap_data dict, {} if the call failed"""
    try:
        is_totle = label == name()
        inputs = swap_inputs(from_token, to_token, exchange, params)
        j = post_with_retries(SWAP_ENDPOINT, inputs, debug=debug)

        if 'success' not in j:
            raise TotleAPIException("Unexpected JSON response", inputs, j)
        elif not j['success']:
            raise TotleAPIException(None, inputs, j)
        else:
            sd = swap_data(j['response'], is_totle, request=inputs)

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
        handle_swap_exception(e, label, from_token, to_token, params, verbose=verbose)
        return {}

# get quote
def get_quote(from_token, to_token, from_amount=None, to_amount=None, dex=None, params={}, verbose=False, debug=False):
    if from_amount and to_amount:
        raise ValueError(f"{name()} only accepts either from_amount or to_amount, not both")
    elif from_amount:
        params['fromAmount'] = from_amount
    elif to_amount:
        params['toAmount'] = to_amount
    else:
        raise ValueError(f"{name()}: either from_amount or to_amount must be specified")

    sd = try_swap(dex or name(), from_token, to_token, exchange=dex, params=params, verbose=verbose, debug=debug)

    if sd:
        # keep consistent with exchanges_parts from other aggregators
        # TODO, this is not an order split, it is a multi-hop route
        exchanges_parts = sd['totleSplits']
        return {
            'source_token': sd['sourceToken'],
            'source_amount': sd['sourceAmount'],
            'destination_token': sd['destinationToken'],
            'destination_amount': sd['destinationAmount'],
            'price': sd['price'],
            'exchanges_parts': exchanges_parts,
        }
    else:
        return {}

def get_pairs(quote='ETH'):
    # Totle's trade/pairs endpoint returns only select pairs used for the data API, so we just use its tokens
    # endpoint to get tokens, which, if tradable=true, are assumed to pair with quote
    tokens_json = requests.get(TOKENS_ENDPOINT).json()

    # use only the tokens that are listed in token_utils.tokens() and use the canonical name
    canonical_symbols = [ token_utils.canonical_symbol(t['symbol']) for t in tokens_json['tokens'] if t['tradable'] ]
    return [(t, quote) for t in canonical_symbols if t]


##############################################################################################
#
# functions to call data APIs
#

@functools.lru_cache(1)
def get_trades_pairs():
    """Returns the set of trade pairs which can be passed to get_trades"""
    r = requests.get(PAIRS_ENDPOINT).json()
    if r['success']:
        return r['response']
    else:  # some uncommon error we should look into
        raise TotleAPIException(None, None, r)


def get_trades(base_asset, quote_asset, limit=None, page=None, begin=None, end=None):
    """Returns the latest trades on all exchanges for the given base/quote assets"""
    if limit or page or begin or end:
        query = { k:v for k,v in vars().items() if v and k not in ['base_asset', 'quote_asset'] }
    else:
        query = {}

    url = TRADES_ENDPOINT + f"/{base_asset}/{quote_asset}"
    timer_start = time.time()
    try:
        r = requests.get(url, params=query)
        j = r.json()
    except ValueError as e:
        print(f"get_trades raised {type(e).__name__}: {e.args[0]}\nresponse was: {r}")

    timer_end = time.time()
    print(f"get_trades {base_asset}/{quote_asset} {query} took {timer_end - timer_start:.1f} seconds")

    if j.get('success'):
        return j['response']
    else: # some uncommon error we should look into
        raise TotleAPIException(None, vars(), j)

