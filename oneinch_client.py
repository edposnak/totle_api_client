import sys
import functools
import requests

API_BASE = 'https://api.1inch.exchange/v1.0'
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

# TODO put these and overlap functions into a tokens lib
@functools.lru_cache(1)
def token_decimals():
    r = requests.get(TOKENS_ENDPOINT).json()
    return { t['symbol']: t['decimals'] for _,t in r.items() }

# helper needed to compute amounts from JSON
def real_amount(int_amount, token):
    """Returns the decimal number of tokens for the given integer amount and token"""
    return int(int_amount) / (10**token_decimals()[token])

# helper needed to convert amounts to request input
def int_amount(float_amount, token):
    """Returns the integer amount of token units for the given float_amount and token"""
    return int(float(float_amount) * (10**token_decimals()[token]))

##############################################################################################
#
# API calls
#

# get exchanges
@functools.lru_cache(1)
def exchanges():
    return requests.get(EXCHANGES_ENDPOINT).json()

# get tokens
@functools.lru_cache(1)
def tokens():
    r = requests.get(TOKENS_ENDPOINT).json()
    return {t['symbol']: t['address'] for _, t in r.items()}

def get_pairs(quote='ETH'):
    return [ (t, quote) for t in tokens() ]

# get quote
def get_quote(from_token, to_token, from_amount):
    # https://api.1inch.exchange/v1.0/quote?fromTokenSymbol=ETH&toTokenSymbol=DAI&amount=100000000000000000000&disabledExchangesList=Bancor
    query = {'fromTokenSymbol': from_token, 'toTokenSymbol': to_token, 'amount': int_amount(from_amount, from_token)}
    j = requests.get(QUOTE_ENDPOINT, params=query).json()

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
        source_amount = real_amount(j['fromTokenAmount'], source_token)
        destination_token = j['toToken']['symbol']
        destination_amount = real_amount(j['toTokenAmount'], destination_token)
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

