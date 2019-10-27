import sys
import functools
import requests
import token_utils

API_BASE = 'https://api.1inch.exchange/v1.1'
EXCHANGES_ENDPOINT = API_BASE + '/exchanges'
TOKENS_ENDPOINT = API_BASE + '/tokens'
QUOTE_ENDPOINT = API_BASE + '/quote'
SWAP_ENDPOINT = API_BASE + '/swap'

ETH_ADDRESS = '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'

TAKER_FEE_PCT = 0.0 # unfairly optimistic, but currently too difficult to calculate
# 1inch fees appear to be part of the savings
# fee is 13.88% of (returnAmount - guaranteedAmount) according to the contract code
# https://etherscan.io/address/0x11111254369792b2Ca5d084aB5eEA397cA8fa48B#code
#
# Swapped events show fees are sometimes 0
# https://etherscan.io/address/0x11111254369792b2Ca5d084aB5eEA397cA8fa48B#events
#
# also not clear whether exchange fees are included in their quotes
# https://twitter.com/scott_lew_is/status/1178064935210733568?s=20

class OneInchAPIException(Exception):
    pass

def name():
    return '1Inch'

def fee_pct():
    return TAKER_FEE_PCT

##############################################################################################
#
# API calls
#

# get exchanges
@functools.lru_cache(1)
def exchanges():
    r = requests.get(EXCHANGES_ENDPOINT)
    # 1-Inch does not have exchange ids, but to keep the same interface we put in 0's for id
    id = 0
    return { j['name']: id for j in r.json() }

@functools.lru_cache()
def get_pairs(quote='ETH'):
    # 1-Inch doesn't have a pairs endpoint, so we just use its tokens endpoint to get tokens, which are assumed to pair with quote
    tokens_json = requests.get(TOKENS_ENDPOINT).json()
    # Returns:
    # {"ABT":{"symbol":"ABT","name":"ArcBlock","address":"0xb98d4c97425d9908e66e53a6fdf673acca0be986","decimals":18},
    # "ABX":{"symbol":"ABX","name":"Arbidex","address":"0x9a794dc1939f1d78fa48613b89b8f9d0a20da00e","decimals":18}, ...}

    # use only the tokens that are listed in token_utils.tokens() and use the canonical name
    canonical_symbols = [ token_utils.canonical_symbol(t) for t in tokens_json ] # will contain lots of None values
    return [ (t, quote) for t in canonical_symbols if t ]

# get quote
def get_quote(from_token, to_token, from_amount=None, to_amount=None):
    """Returns the price in terms of the from_token - i.e. how many from_tokens to purchase 1 to_token"""
    if to_amount or not from_amount: raise ValueError(f"{name()} only works with from_amount")

    # https://api.1inch.exchange/v1.1/quote?fromTokenSymbol=ETH&toTokenSymbol=DAI&amount=100000000000000000000&disabledExchangesList=Bancor
    query = {'fromTokenSymbol': from_token, 'toTokenSymbol': to_token, 'amount': token_utils.int_amount(from_amount, from_token)}
    r = requests.get(QUOTE_ENDPOINT, params=query)
    try:
        j = r.json()

        if j.get('message'):
            print(f"{sys._getframe(  ).f_code.co_name} returned {j['message']} request was {query} response was {j}")
            return {}
        else:
            # Response:
            # {"fromToken":{"symbol":"ETH","name":"Ethereum","decimals":18,"address":"0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"},
            #  "toToken":{"symbol":"DAI","name":"DAI","address":"0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359","decimals":18},
            #  "toTokenAmount":"17199749926766572897346",
            #  "fromTokenAmount":"100000000000000000000",
            #  "exchanges":[{"name":"Oasis","part":66},{"name":"Radar Relay","part":0},{"name":"Uniswap","part":17},{"name":"Kyber","part":7},{"name":"Other 0x","part":10},{"name":"AirSwap","part":0}]}
            source_token = j['fromToken']['symbol']
            source_amount = token_utils.real_amount(j['fromTokenAmount'], source_token)
            destination_token = j['toToken']['symbol']
            destination_amount = token_utils.real_amount(j['toTokenAmount'], destination_token)
            price = source_amount / destination_amount if destination_amount else 0.0
            exchanges_parts = {ex['name']: ex['part'] for ex in j['exchanges'] if ex['part']}

            return {
                'source_token': source_token,
                'source_amount': source_amount,
                'destination_token': destination_token,
                'destination_amount': destination_amount,
                'price': price,
                'exchanges_parts': exchanges_parts,
            }

    except ValueError as e:
        print(f"{name()} {query} raised {r}: {r.text:128}")
        return {}

