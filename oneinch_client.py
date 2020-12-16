import random
import sys
import functools
import threading
import time

import requests
import json
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
    return '1-Inch'

def fee_pct():
    return TAKER_FEE_PCT

##############################################################################################
#
# API calls
#

# map from canonical name to 1-Inch name
DEX_NAME_MAP = {'0x API': '0x API', '0x V3': '0x V3', 'Aave': 'Aave', 'AAVE_LIQUIDATOR': 'AAVE_LIQUIDATOR', 'AirSwap': 'AirSwap', 'Balancer': 'Balancer', 'Bancor': 'Bancor', 'BETH':'BETH', 'C.R.E.A.M. Swap': 'C.R.E.A.M. Swap', 'Chai': 'Chai', 'Chi Minter': 'Chi Minter', 'Compound': 'Compound',
                'Curve.fi': 'Curve.fi', 'Curve.fi v2': 'Curve.fi v2', 'Curve.fi iearn': 'Curve.fi iearn', 'Curve.fi sUSD': 'Curve.fi sUSD', 'Curve.fi BUSD': 'Curve.fi BUSD', 'Curve.fi PAX': 'Curve.fi PAX',
                'Curve.fi renBTC': 'Curve.fi renBTC', 'Curve.fi tBTC': 'Curve.fi tBTC', 'Curve.fi sBTC': 'Curve.fi sBTC', 'Curve.fi hBTC': 'Curve.fi hBTC', 'Curve.fi 3pool': 'Curve.fi 3pool',
                'dForce Swap': 'dForce Swap', 'DODO': 'DODO', 'Fulcrum': 'Fulcrum', 'IdleFinance': 'Idle', 'IEarnFinance': 'iearn', 'Kyber': 'Kyber', 'MakerDAO': 'MakerDAO', 'Mooniswap': 'Mooniswap', 'MultiSplit': 'MultiSplit', 'Multi Uniswap': 'Multi Uniswap', 'mStable': 'mStable', 'Oasis': 'Oasis', 'Pathfinder': 'Pathfinder',
                'PMM': 'PMM',  'PMM1': 'PMM1', 'PMM2': 'PMM2',  'PMM3': 'PMM3',  'PMM4': 'PMM4',  'PMM5': 'PMM5',
                'StableCoinSwap': 'StableCoinSwap', 'Sushi Swap': 'Sushi Swap', 'SUSHI': 'Sushi Swap','Swerve': 'Swerve', 'Synth Depot': 'Synth Depot', 'Synthetix': 'Synthetix', 'UNISWAP_V1': 'Uniswap', 'Uniswap': 'Uniswap', 'Uniswap V2':'Uniswap V2', 'WETH': 'WETH'}




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
    canonical_symbols = [ token_utils.canonical_symbol(t) for t in tokens_json ] # may contain None values
    return [ (t, quote) for t in canonical_symbols if t ]

supported_tokens_lock = threading.Lock()
def supported_tokens():
    supported_tokens_lock.acquire()
    j =  supported_tokens_critical()
    supported_tokens_lock.release()
    return j


JSON_FILENAME = 'data/cached_oneinch_tokens.json'

@functools.lru_cache(1)
def supported_tokens_critical():
    r = requests.get(TOKENS_ENDPOINT)
    try: # this often fails to return a good response, so we used cached data when it does
        supp_tokens_json = r.json()
        with open(JSON_FILENAME, 'w') as f:
            json.dump(supp_tokens_json, f)

    except json.decoder.JSONDecodeError as e:
        print(f"oneinch_client.supported_tokens() using {JSON_FILENAME}")
        with open(JSON_FILENAME) as f:
            supp_tokens_json = json.load(f)

    return { t['symbol']: t['address'] for t in supp_tokens_json.values() }

@functools.lru_cache(1)
def tokens_by_addr():
    return { addr: sym for sym, addr in supported_tokens().items() }

# get quote
def get_quote(from_token, to_token, from_amount=None, to_amount=None, dex=None, verbose=False, debug=False):
    """Returns the price in terms of the from_token - i.e. how many from_tokens to purchase 1 to_token"""
    if to_amount or not from_amount: raise ValueError(f"{name()} only works with from_amount")
    for t in [from_token, to_token]:
        if t != 'ETH' and t not in supported_tokens(): return {} # temporary speedup

    # https://api.1inch.exchange/v1.1/quote?fromTokenSymbol=ETH&toTokenSymbol=DAI&amount=100000000000000000000&disabledExchangesList=Bancor
    query = {'fromTokenSymbol': from_token, 'toTokenSymbol': to_token, 'amount': token_utils.int_amount(from_amount, from_token)}
    r = None
    try:
        r = requests.get(QUOTE_ENDPOINT, params=query)
        if debug:
            print(f"r.status_code={r.status_code}")
        j = r.json()
        if debug:
            print(f"REQUEST to {QUOTE_ENDPOINT}:\n{json.dumps(query, indent=3)}\n\n")
            print(f"RESPONSE from {QUOTE_ENDPOINT}:\n{json.dumps(j, indent=3)}\n\n")

        if j.get('message'):
            print(f"{sys._getframe(  ).f_code.co_name} returned {j['message']} request was {query} response was {j}")

            time.sleep(1.0 + random.random())  # block each thread for 1-2 seconds to keep from getting rate limited
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

            time.sleep(1.0 + random.random())  # block each thread for 1-2 seconds to keep from getting rate limited
            return {
                'source_token': source_token,
                'source_amount': source_amount,
                'destination_token': destination_token,
                'destination_amount': destination_amount,
                'price': price,
                'exchanges_parts': exchanges_parts,
            }

    except (ValueError, requests.exceptions.RequestException) as e:
        if r is None:
            print(f"Failed to connect: #{e}")
        elif r.status_code == 429:
            print(f"RATE LIMITED {name()} {query}")
            time.sleep(300)
        else:
            print(f"{name()} {query} raised {e}: {r.text[:128] if r else 'no JSON returned'} status_code={r.status_code}")
            if debug: print(f"FAILED REQUEST to {QUOTE_ENDPOINT}:\n{json.dumps(query, indent=3)}\n\n")
        return {}

def get_swap(from_token, to_token, from_amount=None, to_amount=None, dex=None, from_address=None, slippage=50, verbose=False, debug=False):
    # https://api.1inch.exchange/v1.1/swap?fromTokenSymbol=ETH&toTokenSymbol=DAI&amount=100000000000000000000&fromAddress=0x8d12A197cB00D4747a1fe03395095ce2A5CC6819&slippage=10

    query = {'fromTokenSymbol': from_token, 'toTokenSymbol': to_token, 'amount': token_utils.int_amount(from_amount, from_token)}
    if debug: print(f"REQUEST to {QUOTE_ENDPOINT}:\n{json.dumps(query, indent=3)}\n\n")
    r = None
    try:
        r = requests.get(QUOTE_ENDPOINT, params=query)
        j = r.json()
        if debug: print(f"RESPONSE from {QUOTE_ENDPOINT}:\n{json.dumps(j, indent=3)}\n\n")

        if j.get('message'):
            print(f"{sys._getframe(  ).f_code.co_name} returned {j['message']} request was {query} response was {j}")
            return {}
        else:
            # Response: {
            #    "from":"0x8d12A197cB00D4747a1fe03395095ce2A5CC6819",
            #    "to":"0x11111254369792b2Ca5d084aB5eEA397cA8fa48B",
            #    "gas":"1862857",
            #    "gasPrice":"88000000000",
            #    "value":"100000000000000000000",
            #    "data":"0xf88309d7000000000000000000000000eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee0000000000000000000000006b175474e89094c44da98b954eedeac495271d0f0000000000000000000000000000000000000000000000056bc75e2d631000000000000000000000000000000000000000000000000001d2ed255d96ab94a920000000000000000000000000000000000000000000000206ce9b4b8af788bbeb0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000014000000000000000000000000000000000000000000000000000000000000001a00000000000000000000000000000000000000000000000000000000000000380000000000000000000000000000000000000000000000000000000000000040000000000000000000000000000000000000000000000000000000000000000020000000000000000000000002a1530c4c41db0b0b2bb646cb5eb1a67b71586670000000000000000000000001814222fa8c8c1c1bf380e3bbfbd9de8657da47600000000000000000000000000000000000000000000000000000000000001a8f39b5b9b0000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000005e6c2b80e2a7515e000000000000000000000000eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee0000000000000000000000006b175474e89094c44da98b954eedeac495271d0f0000000000000000000000000000000000000000000000000de0b6b3a7640000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000c0000000000000000000000000000000000000000000000000000000000000000b0000000000000000000000000000000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000030000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000004400000000000000000000000000000000000000000000000000000000000001a800000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000055de6a779bbac00000000000000000000000000000000000000000000000000000de0b6b3a7640000"}
            source_token_addr = j['from']
            # TODO: implement response parsing

    except (ValueError, requests.exceptions.RequestException) as e:
        print(f"{name()} {query} raised {e}: {r.text[:128] if r else 'no JSON returned'}")
        return {}