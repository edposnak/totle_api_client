import json
import sys
import functools
import requests
import token_utils

# https://paraswapv2.docs.apiary.io/#
API_BASE = 'https://api.paraswap.io/v2'
# the /1 in these endpoints is /{network_id}
# guessed 1 because tokens endpoint returns the correct ERC-20 addresses
TOKENS_ENDPOINT = API_BASE + '/tokens/1'
PRICES_ENDPOINT = API_BASE + '/prices/1'
TRANSACTIONS_ENDPOINT = API_BASE + '/transactions/1'
# https://api.dex.ag/token-list-full

TAKER_FEE_PCT = 0.0 # currently 0 fees
# "We chose not to take fees for the MVP stage so that our users can fully experiment with the product."
# "The simplest method we’ve found is to take small commissions on each transaction. We’re also exploring other ideas
# such as a SAAS model, where regular traders can only pay a fixed monthly fee and make fee-less transactions."
# https://defiprime.com/paraswap

ETH_ADDRESS = '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'

class ParaswapAPIException(Exception):
    pass

def name():
    return 'Paraswap'

def fee_pct():
    return TAKER_FEE_PCT


##############################################################################################
#
# API calls
#

# get exchanges
# DEX_NAME_MAP = { '0x V3': '0x', 'Bancor': 'Bancor', 'Compound': 'Compound', 'Fulcrum': 'Fulcrum', 'Kyber': 'Kyber', 'MakerDAO': 'MakerDAO', 'Oasis': 'Oasis', 'PMM': 'ParaSwapPool', 'Uniswap': 'Uniswap' }

@functools.lru_cache()
def exchanges():
    # there is no exchanges endpoint yet so we are just using the ones from an ETH/DAI price query
    dex_names = ['0x', 'Bancor', 'Compound', 'Fulcrum', 'Kyber', 'MakerDAO', 'Oasis', 'ParaSwapPool', 'ParaSwapPool2', 'Uniswap']

    # Paraswap does not have exchange ids, but to keep the same interface we put in 0's for id
    id = 0
    return { e: id for e in dex_names }


@functools.lru_cache()
def get_pairs(quote='ETH'):
    # Paraswap doesn't have a pairs endpoint, so we just use its tokens endpoint to get tokens, which are assumed to pair with quote
    tokens_json = requests.get(TOKENS_ENDPOINT).json()

    # use only the tokens that are listed in token_utils.tokens() and use the canonical name
    canonical_symbols = [token_utils.canonical_symbol(t) for t in tokens_json]  # may contain None values
    return [(t, quote) for t in canonical_symbols if t]


def supported_tokens():
    """Returns a (short) list of tokens provided by the tokens endpoint"""
    return list(map(lambda t: t['symbol'], tokens_json()))


@functools.lru_cache(128)
def paraswap_addr(token_symbol):
    """Returns Paraswap's case-sensitive address for the given (canonized) token symbol"""
    j = next(filter(lambda t: token_utils.canonize(t['symbol']) == token_symbol, tokens_json()), None)
    return j and j['address']


@functools.lru_cache(1)
def tokens_json():
    # "symbol":"DEV","address":"0x5cAf454Ba92e6F2c929DF14667Ee360eD9fD5b26",
    raw_tokens_json = requests.get(TOKENS_ENDPOINT).json()['tokens']
    return [ t for t in raw_tokens_json if t['address'] not in token_utils.ADDRESSES_TO_FILTER_OUT ]


# get quote
def get_quote(from_token, to_token, from_amount=None, to_amount=None, dex=None, verbose=False, debug=False):
    """Returns the price in terms of the from_token - i.e. how many from_tokens to purchase 1 to_token"""
    if to_amount or not from_amount: raise ValueError(f"{name()} only works with from_amount")

    # these addresses are case-sensitive so we have to use paraswap_addr to map them.
    from_addr, to_addr = paraswap_addr(from_token), paraswap_addr(to_token)
    for addr, token in [(from_addr, from_token), (to_addr, to_token)]:
        if not addr: # token is not supported
            print(f"{token} could not be mapped to case-sensitive {name()} address")
            return {}

    # Request: from ETH to DAI
    # https://paraswap.io/api/v1/prices/1/0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359/10000000000000000
    req_url = f"{PRICES_ENDPOINT}/{from_addr}/{to_addr}/{token_utils.int_amount(from_amount, from_token)}"
    if debug: print(f"REQUEST to {req_url}: (from_token={from_token}, to_token={to_token} from_amount={from_amount})\n\n")

    r = None
    try:
        r = requests.get(req_url)
        j = r.json()
        if debug: print(f"RESPONSE from {PRICES_ENDPOINT}:\n{json.dumps(j, indent=3)}\n\n")

        # Response:
        # {"priceRoute": {
        #     "amount": "1811400076272265830",
        #     "bestRoute": [
        #          {"exchange": "BANCOR", "percent": "100", "srcAmount": "10000000000000000", "amount": "1811400076272265830"},
        #          {"exchange": "UNISWAP", "percent": "0", "srcAmount": "0", "amount": "1807813865444263126"},
        #          {"exchange": "KYBER", "percent": "0", "srcAmount": "0", "amount": "1804732523842902460"},
        #          {"exchange": "ETH2DAI", "percent": "0", "srcAmount": "0", "amount": "1801799999999999999"},
        #          {"exchange": "COMPOUND", "percent": "0", "srcAmount": "0", "amount": "0"}],
        #     "others": [ ... ] }}

        price_route = j.get('priceRoute')
        if not price_route:
            print(f"{sys._getframe(  ).f_code.co_name} had no priceRoute request was {req_url} response was {j}")
            return {}
        else:
            exchanges_parts, exchanges_prices = {}, {}
            source_amount = from_amount
            destination_amount = token_utils.real_amount(price_route['amount'], to_token)
            if destination_amount == 0:
                print(f"{name()} destination_amount={0} price_route={json.dumps(price_route, indent=3)}")
                return {}

            price = source_amount / destination_amount
            for dex_alloc in price_route['bestRoute']:
                # We use custom int_conv because sometimes Paraswap splits produce amounts expressed as strings with
                # decimal points causing int(s) to raise "invalid literal for int() with base 10"
                dex, pct, src_amt, dest_amt = dex_alloc['exchange'], int(dex_alloc['percent']), int_conv(dex_alloc['srcAmount']), int_conv(dex_alloc['amount'])
                if pct > 0:
                    exchanges_parts[dex] = pct

                # Don't try to compute exchanges_prices because these amounts are wack. They add up to more than
                # destination_amount, and are sometimes 0 even when percent > 0
                #
                # if dest_amt > 0: # a price quote with amount=0 is not a price quote
                #     # when price quotes have srcAmount=0 use the source_amount
                #     real_src_amt = token_utils.real_amount(src_amt, from_token) if src_amt > 0 else source_amount
                #     exchanges_prices[dex] = real_src_amt / token_utils.real_amount(dest_amt, to_token)

            return {
                'source_token': from_token,
                'source_amount': source_amount,
                'destination_token': to_token,
                'destination_amount': destination_amount,
                'price': price,
                'exchanges_parts': exchanges_parts,
                # 'exchanges_prices': exchanges_prices
            }



    except (ValueError, requests.exceptions.RequestException) as e:
        print(f"{name()} {req_url} raised {e}: {r.text[:128] if r else 'no JSON returned'}")
        return {}


def get_swap(from_token, to_token, from_amount=None, to_amount=None, dex=None, from_address=None, slippage=50, verbose=False, debug=False):
    raise NotImplementedError(f"get_swap requires input from the response of get_quote and so can't be implemented with the current standard method signature for get_swap")


def int_conv(s):
    """Converts a string, which may have a decimal point, to an integer"""
    if s.find('.') < 0:
        return int(s)
    else: # split into integer and fraction parts and round
        integer, fraction = s.split('.')
        return int(integer) + round(int(fraction) / 10**len(fraction))
