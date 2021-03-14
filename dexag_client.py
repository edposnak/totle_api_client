import functools
import threading

import requests
import json
import token_utils

# https://docs.dex.ag/
API_BASE = 'https://api.dex.ag'
TOKENS_ENDPOINT = API_BASE + '/tokens'
TOKENS_NAMES_ENDPOINT = API_BASE + '/token-list-full'
PRICE_ENDPOINT = API_BASE + '/price'
TRADE_ENDPOINT = API_BASE + '/trade'
# https://api.dex.ag/token-list-full

TAKER_FEE_PCT = 0.0 # unfairly optimistic, but currently too difficult to calculate
# "We charge 0 fees and any DEX-related fees are factored into the total cost of your trade"
# https://concourseopen.com/blog/dex-ag-x-blaster/
# https://ethgasstation.info/blog/dex-ag-sets-new-record-volume-294733/

class DexAGAPIException(Exception):
    pass

def name():
    return 'DEX.AG'

def fee_pct():
    return TAKER_FEE_PCT


##############################################################################################
#
# API calls
#

# get exchanges
# DEX_NAME_MAP = {'ag': 'ag', 'all':'all', '0xMesh': 'radar-relay', 'Bancor': 'bancor', 'DDEX': 'ddex', 'Ethfinex': 'ethfinex', 'IDEX': 'idex',
#                 'Kyber': 'kyber', 'Oasis': 'oasis', 'Paradex': 'paradex', 'Radar Relay': 'radar-relay', 'Uniswap': 'uniswap' }

def exchanges():
    # there is no exchanges endpoint yet so we are just using the ones from an ETH/DAI price query where dex == all
    dex_names = ['0x v3', 'ag', 'bancor', 'curvefi', 'ddex', 'ethfinex', 'idex', 'kyber', 'oasis', 'paradex', 'radar-relay', 'synthetix', 'uniswap']

    # DEX.AG does not have exchange ids, but to keep the same interface we put in 0's for id
    id = 0
    return { e: id for e in dex_names }



@functools.lru_cache()
def get_pairs(quote='ETH'):
    # DEX.AG doesn't have a pairs endpoint, so we just use its tokens endpoint to get tokens, which are assumed to pair with quote
    tokens_json = requests.get(TOKENS_ENDPOINT).json()

    # use only the tokens that are listed in token_utils.tokens() and use the canonical name
    canonical_symbols = [token_utils.canonical_symbol(t) for t in tokens_json]  # may contain None values
    return [(t, quote) for t in canonical_symbols if t]


supported_tokens_lock = threading.Lock()
def supported_tokens():
    supported_tokens_lock.acquire()
    j =  supported_tokens_critical()
    supported_tokens_lock.release()
    return j


JSON_FILENAME = 'data/cached_dexag_tokens.json'

@functools.lru_cache(1)
def supported_tokens_critical():
    r = requests.get(TOKENS_NAMES_ENDPOINT)
    try: # this often fails to return a good response, so we used cached data when it does
        supp_tokens_json = r.json()
        with open(JSON_FILENAME, 'w') as f:
            json.dump(supp_tokens_json, f)

    except json.decoder.JSONDecodeError as e:
        print(f"dexag_client.supported_tokens() using {JSON_FILENAME}")
        with open(JSON_FILENAME) as f:
            supp_tokens_json = json.load(f)

    return [t['symbol'] for t in (supp_tokens_json)]


def calc_amounts_and_price(from_amount, to_amount, dexag_price):
    """Returns the source_amount, destination_amount, and price in terms of the from_token - i.e. how many from_tokens to purchase 1 to_token"""

    # BUG? DEX.AG price is not a simple function of base and quote. It changes base on whether you specify toAmount
    # or fromAmount even though base and quote stay the same! So it has nothing to do with base and quote.
    # Here are four examples:
    # https://api.dex.ag/price?from=ETH&to=DAI&toAmount=1.5&dex=ag -> price: 0.0055    <- buy (OK)
    # https://api.dex.ag/price?from=ETH&to=DAI&fromAmount=1.5&dex=ag -> price: 180     <- buy (inverted)
    # https://api.dex.ag/price?from=DAI&to=ETH&toAmount=1.5&dex=ag -> price: 180       <- sell (OK)
    # https://api.dex.ag/price?from=DAI&to=ETH&fromAmount=1.5&dex=ag -> price: 0.0055  <- sell (inverted)

    # We always want to return price in terms of how many from_tokens for 1 to_token, which means we need to
    # invert DEX.AG's price whenever from_amount is specified.
    if from_amount:  # When from_amount is specified, dexag_price is the amount of to_tokens per 1 from_token.
        source_amount, destination_amount = (from_amount, from_amount * dexag_price)
        price = 1 / dexag_price
    else:  # When to_amount is specified, price is the amount of from_tokens per 1 to_token.
        source_amount, destination_amount = (to_amount * dexag_price, to_amount)
        price = dexag_price
    return source_amount, destination_amount, price


# get quote
AG_DEX = 'ag'
def get_quote(from_token, to_token, from_amount=None, to_amount=None, dex='all', verbose=False, debug=False):
    """Returns the price in terms of the from_token - i.e. how many from_tokens to purchase 1 to_token"""

    # don't bother to make the call if either of the tokens are not supported
    for t in [from_token, to_token]:
        if t != 'ETH' and t not in supported_tokens():
            print(f"{t} is not supported by {name()}")
            return {}

    # buy: https://api.dex.ag/price?from=ETH&to=DAI&fromAmount=1.5&dex=all
    # sell: https://api.dex.ag/price?from=DAI&to=ETH&toAmount=1.5&dex=all
    query = {'from': from_token, 'to': to_token, 'dex': dex}

    if from_amount and to_amount:
        raise ValueError(f"{name()} only accepts either from_amount or to_amount, not both")
    elif from_amount:
        query['fromAmount'] = from_amount
    elif to_amount:
        query['toAmount'] = to_amount
    else:
        raise ValueError(f"{name()}: either from_amount or to_amount must be specified")

    if debug: print(f"REQUEST to {PRICE_ENDPOINT}:\n{json.dumps(query, indent=3)}\n\n")
    r = None
    try:
        r = requests.get(PRICE_ENDPOINT, params=query)
        j = r.json()
        if debug: print(f"RESPONSE from {PRICE_ENDPOINT}:\n{json.dumps(j, indent=3)}\n\n")

        if 'error' in j: raise ValueError(j['error'])

        # Response:
        # {"dex": "ag", "price": "159.849003708050647455", "pair": {"base": "ETH", "quote": "DAI"}, "liquidity": {"uniswap": 38, "bancor": 62}}

        # if dex=='all' j will be an array of dicts like this
        # [ {"dex": "bancor", "price": "159.806431928046276401", "pair": {"base": "ETH", "quote": "DAI"}},
        #   {"dex": "uniswap", "price": "159.737708484933187899", "pair": {"base": "ETH", "quote": "DAI"}}, ... ]
        ag_data, exchanges_prices = {}, {}
        if isinstance(j, list):
            for dex_data in j:
                dex, dexag_price = dex_data['dex'], float(dex_data['price'])
                exchanges_prices[dex] = 1 / dexag_price if from_amount else dexag_price
                if dex == AG_DEX: ag_data = dex_data
        else:
            ag_data = j

        if not ag_data: return {}

        source_amount, destination_amount, price = calc_amounts_and_price(from_amount, to_amount, float(ag_data['price']))


        # "liquidity": {"uniswap": 38, "bancor": 62}, ...
        exchanges_parts = ag_data['liquidity'] if ag_data.get('liquidity') else {}

        return {
            'source_token': from_token,
            'source_amount': source_amount,
            'destination_token': to_token,
            'destination_amount': destination_amount,
            'price': price,
            'exchanges_parts': exchanges_parts,
            'exchanges_prices': exchanges_prices
        }

    except (ValueError, requests.exceptions.RequestException) as e:
        print(f"{name()} {query} raised {e}: {r.text[:128] if r else 'no JSON returned'}")
        return {}


def get_swap(from_token, to_token, from_amount=None, to_amount=None, dex='ag', from_address=None, slippage=50, verbose=False, debug=False):
    """Returns the price in terms of the from_token - i.e. how many from_tokens to purchase 1 to_token"""

    # don't bother to make the call if either of the tokens are not supported
    for t in [from_token, to_token]:
        if t != 'ETH' and t not in supported_tokens():
            print(f"{t} is not supported by {name()}")
            return {}

    # buy: https://api.dex.ag/price?from=ETH&to=DAI&fromAmount=1.5&dex=all
    # sell: https://api.dex.ag/price?from=DAI&to=ETH&toAmount=1.5&dex=all
    query = {'from': from_token, 'to': to_token, 'dex': dex}
    if from_amount:
        query['fromAmount'] = from_amount
    elif to_amount:
        query['toAmount'] = to_amount
    else:
        raise ValueError(f"{name()} only accepts either from_amount or to_amount, not both")

    # TODO limitAmount - The limit of "from" token to still execute the trade (specifies slippage)
    # query['limitAmount'] = some_function_of(splippage, from_amount)

    if debug: print(f"REQUEST to {TRADE_ENDPOINT}:\n{json.dumps(query, indent=3)}\n\n")
    r = None
    try:
        r = requests.get(TRADE_ENDPOINT, params=query)
        j = r.json()
        if debug: print(f"RESPONSE from {TRADE_ENDPOINT}:\n{json.dumps(j, indent=3)}\n\n")

        if 'error' in j: raise ValueError(j['error'])

        # Response:
        # {
        #   "trade": { "to": "0xA540fb50288cc31639305B1675c70763C334953b", "data": "0x5d46..." "value": "1500000000000000000" },
        #   "metadata": {
        #     "source": { "dex": "ag", "price": "80.13582764310020105533", "liquidity": { "uniswap": 100 } },
        #     "query": { "from": "ETH", "to": "DAI", "fromAmount": "1.5", "dex": "ag" }
        #   }
        # }

        payload=j['trade']['data']
        ag_data = j['metadata']['source']
        if not ag_data: return {}

        source_amount, destination_amount, price = calc_amounts_and_price(from_amount, to_amount, float(ag_data['price']))
        exchanges_parts = ag_data['liquidity'] if ag_data.get('liquidity') else {}

        return {
            'source_token': from_token,
            'source_amount': source_amount,
            'destination_token': to_token,
            'destination_amount': destination_amount,
            'price': price,
            'exchanges_parts': exchanges_parts,
            'exchanges_prices': {},
            'payload': payload
        }

    except (ValueError, requests.exceptions.RequestException) as e:
        print(f"{name()} {query} raised {e}: {r.text[:128] if r else 'no JSON returned'}")
        return {}


