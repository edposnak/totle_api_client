import functools
import requests
import json
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
DEX_NAME_MAP = {'ag': 'ag', 'all':'all', '0xMesh': 'radar-relay', 'Bancor': 'bancor', 'DDEX': 'ddex', 'Ethfinex': 'ethfinex', 'IDEX': 'idex',
                'Kyber': 'kyber', 'Oasis': 'oasis', 'Paradex': 'paradex', 'Radar Relay': 'radar-relay', 'Uniswap': 'uniswap' }

def exchanges():
    # there is no exchanges endpoint yet so we are just using the ones from an ETH/DAI price query where dex == all
    dex_names = ['ag', 'bancor', 'ddex', 'ethfinex', 'idex', 'kyber', 'oasis', 'paradex', 'radar-relay', 'uniswap']

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


def supported_tokens():
    # guess based on empirical data
    return ['ABT','ABYSS','ANT','APPC','AST','BAT','BLZ','BNT','BTU','CBI','CDAI','CDT','CETH','CND','CUSDC','CVC','CWBTC','CZRX','DAI','DGX','ELF','ENG','ENJ','EQUAD','ETHOS','FUN','GEN','GNO','IDAI','KNC','LBA','LEND','LINK','LRC','MANA','MCO','MKR','MLN','MOC','MTL','NEXO','OMG','OST','PAX','PAY','PLR','POE','POLY','POWR','QKC','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','SPANK','SPN','STORJ','TAU','TKN','TUSD','UPP','USDC','USDT','VERI','WBTC','WETH','XCHF','XDCE','ZRX']


# get quote
AG_DEX = 'ag'
def get_quote(from_token, to_token, from_amount=None, to_amount=None, dex='all', verbose=False, debug=False):
    """Returns the price in terms of the from_token - i.e. how many from_tokens to purchase 1 to_token"""

    for t in [from_token, to_token]:
        if t != 'ETH' and t not in supported_tokens(): return {} # temporary speedup

    # buy: https://api.dex.ag/price?from=ETH&to=DAI&fromAmount=1.5&dex=all
    # sell: https://api.dex.ag/price?from=DAI&to=ETH&toAmount=1.5&dex=all
    query = {'from': from_token, 'to': to_token, 'dex': dex}
    if from_amount:
        query['fromAmount'] = from_amount
    elif to_amount:
        query['toAmount'] = to_amount
    else:
        raise ValueError(f"{name()} only accepts either from_amount or to_amount, not both")

    if debug: print(f"REQUEST to {PRICE_ENDPOINT}:\n{json.dumps(query, indent=3)}\n\n")
    r = requests.get(PRICE_ENDPOINT, params=query)
    try:
        j = r.json()
        if debug: print(f"RESPONSE from {PRICE_ENDPOINT}:\n{json.dumps(j, indent=3)}\n\n")

        # Response:
        # {"dex": "ag", "price": "159.849003708050647455", "pair": {"base": "ETH", "quote": "DAI"}, "liquidity": {"uniswap": 38, "bancor": 62}}

        # if dex=='all' j will be an array of dicts like this
        # [ {"dex": "bancor", "price": "159.806431928046276401", "pair": {"base": "ETH", "quote": "DAI"}},
        #   {"dex": "uniswap", "price": "159.737708484933187899", "pair": {"base": "ETH", "quote": "DAI"}}, ... ]
        exchanges_prices = {}
        if isinstance(j, list):
            for dex_data in j:
                dex, dexag_price = dex_data['dex'], float(dex_data['price'])
                check_pair(dex_data, query, dex=dex)
                exchanges_prices[dex] = 1 / dexag_price if from_amount else dexag_price
                if dex == AG_DEX: ag_data = dex_data
        else:
            ag_data = j
            check_pair(ag_data, query, dex=AG_DEX)

        # BUG? DEX.AG price is not a simple function of base and quote. It changes base on whether you specify toAmount
        # or fromAmount even though base and quote stay the same! So it has nothing to do with base and quote.
        # Here are four examples:
        # https://api.dex.ag/price?from=ETH&to=DAI&toAmount=1.5&dex=ag -> price: 0.0055    <- buy (OK)
        # https://api.dex.ag/price?from=ETH&to=DAI&fromAmount=1.5&dex=ag -> price: 180     <- buy (inverted)
        # https://api.dex.ag/price?from=DAI&to=ETH&toAmount=1.5&dex=ag -> price: 180       <- sell (OK)
        # https://api.dex.ag/price?from=DAI&to=ETH&fromAmount=1.5&dex=ag -> price: 0.0055  <- sell (inverted)

        dexag_price = float(ag_data['price'])
        if debug: print(f"dexag_price={dexag_price}")

        # We always want to return price in terms of how many from_tokens for 1 to_token, which means we need to
        # invert DEX.AG's price whenever from_amount is specified.
        if from_amount: # When from_amount is specified, dexag_price is the amount of to_tokens per 1 from_token.
            source_amount, destination_amount = (from_amount, from_amount * dexag_price)
            price = 1 / dexag_price
        else: # When to_amount is specified, price is the amount of from_tokens per 1 to_token.
            source_amount, destination_amount = (to_amount * dexag_price, to_amount)
            price = dexag_price

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

    except ValueError as e:
        print(f"{name()} {query} raised {r}: {r.text[:128]}")
        return {}


def check_pair(ag_data, query, dex=AG_DEX):
    """sanity check that asserts base == from and quote == to, but the base and quote actually don't matter in how the price is quoted"""
    pair = ag_data['pair']
    if (pair['base'], pair['quote']) != (query['from'], query['to']):
        raise ValueError(f"unexpected base,quote: dex={dex} pair={pair} but query={query}")

