import sys
import functools
import requests
import token_utils

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
def exchanges():
    # there is no exchanges endpoint yet so we are just using the ones from an ETH/DAI price query where dex == all
    ['ag', 'bancor', 'uniswap', 'kyber', 'radar-relay', 'idex', 'paradex', 'oasis', 'ddex', 'ethfinex']


@functools.lru_cache()
def get_pairs(quote='ETH'):
    # DEX.AG doesn't have a pairs endpoint, so we just use its tokens endpoint to get tokens, which are assumed to pair with quote
    tokens_json = requests.get(TOKENS_ENDPOINT).json()

    # use only the tokens that are listed in token_utils.tokens() and use the canonical name
    canonical_symbols = [token_utils.canonical_symbol(t) for t in tokens_json]  # will contain lots of None values
    return [(t, quote) for t in canonical_symbols if t]


# get quote
def get_quote(from_token, to_token, from_amount=None, to_amount=None, dex='ag'):
    """Returns the price in terms of the from_token - i.e. how many from_tokens to purchase 1 to_token"""

    # buy: https://api.dex.ag/price?from=ETH&to=DAI&fromAmount=1&dex=all
    # sell: https://api.dex.ag/price?from=DAI&to=ETH&toAmount=1&dex=all
    query = {'from': from_token, 'to': to_token, 'dex': dex}
    if from_amount:
        query['fromAmount'] = from_amount
    elif to_amount:
        query['toAmount'] = to_amount
    else:
        raise ValueError(f"{name()} only accepts either from_amount or to_amount, not both")

    r = requests.get(PRICE_ENDPOINT, params=query)
    try:
        j = r.json()
        # Response:
        # {"dex": "ag", "price": "159.849003708050647455", "pair": {"base": "ETH", "quote": "DAI"}, "liquidity": {"uniswap": 38, "bancor": 62}}

        # TODO: if dex=='all' j will be an array of dicts like this
        # [ {"dex": "bancor", "price": "159.806431928046276401", "pair": {"base": "ETH", "quote": "DAI"}},
        #   {"dex": "uniswap", "price": "159.737708484933187899", "pair": {"base": "ETH", "quote": "DAI"}}, ... ]

        # DEX.AG price is always in quote currency (for 1 base token) and quote is always to_token
        pair = j['pair']
        if (pair['base'], pair['quote']) != (query['from'], query['to']):
            raise ValueError(f"unexpected base,quote: j['pair']={pair} but query={query}")

        dexag_price = float(j['price']) # number of to_tokens for 1 from_token
        # we want to return price in terms of the from_token (base token), so we invert the dexag_price
        price = 1 / dexag_price # number of from_tokens for 1 to_token

        if from_amount:
            source_amount, destination_amount = from_amount, from_amount * dexag_price
        else: # to_amount was given
            source_amount, destination_amount = to_amount * price, to_amount

        exchanges_parts = j['liquidity'] if j.get('liquidity') else {}

        return {
            'source_token': from_token,
            'source_amount': source_amount,
            'destination_token': to_token,
            'destination_amount': destination_amount,
            'price': price,
            'exchanges_parts': exchanges_parts,
        }

    except ValueError as e:
        raise DexAGAPIException(r.text, query, r)
