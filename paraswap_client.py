import sys
import functools
import requests
import token_utils

API_BASE = 'https://paraswap.io/api/v1'
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
def exchanges():
    # there is no exchanges endpoint yet so we are just using the ones from an ETH/DAI price query
    dex_names = ['KYBER','UNISWAP','BANCOR','ETH2DAI','COMPOUND']

    # Paraswap does not have exchange ids, but to keep the same interface we put in 0's for id
    id = 0
    return { e: id for e in dex_names }


@functools.lru_cache()
def get_pairs(quote='ETH'):
    # DEX.AG doesn't have a pairs endpoint, so we just use its tokens endpoint to get tokens, which are assumed to pair with quote
    tokens_json = requests.get(TOKENS_ENDPOINT).json()

    # use only the tokens that are listed in token_utils.tokens() and use the canonical name
    canonical_symbols = [token_utils.canonical_symbol(t) for t in tokens_json]  # may contain None values
    return [(t, quote) for t in canonical_symbols if t]


# get quote
AG_DEX = 'ag'
def get_quote(from_token, to_token, from_amount=None, to_amount=None, dex=None):
    """Returns the price in terms of the from_token - i.e. how many from_tokens to purchase 1 to_token"""
    if to_amount or not from_amount: raise ValueError(f"{name()} only works with from_amount")

    # Request: from ETH to DAI
    # https://paraswap.io/api/v1/prices/1/0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359/10000000000000000
    from_addr, to_addr = token_utils.addr(from_token), token_utils.addr(to_token)
    if from_token == 'ETH': from_addr = ETH_ADDRESS
    req_url = f"{PRICES_ENDPOINT}/{from_addr}/{to_addr}/{token_utils.int_amount(from_amount, from_token)}"
    r = requests.get(req_url)
    try:
        j = r.json()
        # Response:
        # {"priceRoute": {
        #     "amount": "1811400076272265830",
        #     "bestRoute": [
        #          {"exchange": "BANCOR", "percent": "100", "srcAmount": "10000000000000000", "destAmount": "1811400076272265830"},
        #          {"exchange": "UNISWAP", "percent": "0", "srcAmount": "0", "destAmount": "1807813865444263126"},
        #          {"exchange": "KYBER", "percent": "0", "srcAmount": "0", "destAmount": "1804732523842902460"},
        #          {"exchange": "ETH2DAI", "percent": "0", "srcAmount": "0", "destAmount": "1801799999999999999"},
        #          {"exchange": "COMPOUND", "percent": "0", "srcAmount": "0", "destAmount": "0"}],
        #     "others": [ ... ] }}

        price_route = j.get('priceRoute')
        if not price_route:
            print(f"{sys._getframe(  ).f_code.co_name} had no priceRoute request was {req_url} response was {j}")
            return {}
        else:
            exchanges_parts, exchanges_prices = {}, {}
            source_amount = token_utils.real_amount(from_amount, from_token)
            destination_amount = token_utils.real_amount(price_route['amount'], to_token)
            price = source_amount / destination_amount

            for dd in price_route['bestRoute']:
                dex, pct, src_amt, dest_amt = dd['exchange'], int(dd['percent']), int(dd['srcAmount']), int(dd['destAmount'])
                if pct > 0:
                    exchanges_parts[dex] = pct
                    exchanges_prices[dex] = token_utils.real_amount(src_amt, from_token) / token_utils.real_amount(dest_amt, to_token)

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



