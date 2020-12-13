import random
import sys
import functools
import threading
import time

import requests
import json
import token_utils

API_BASE = 'https://api.1inch.exchange/v2.0'
EXCHANGES_ENDPOINT = API_BASE + 'https://api.1inch.exchange/v1.1/exchanges'
TOKENS_ENDPOINT = API_BASE + '/tokens'
QUOTE_ENDPOINT = API_BASE + '/quote'
SWAP_ENDPOINT = API_BASE + '/swap'

ETH_ADDRESS = '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'

IDEX_ADDRESS = '0x2a0c0DBEcC7E4D658f48E01e3fA353F44050c208'
DEFAULT_MAX_SLIPPAGE_PERCENT = 50


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
    return '1-Inch V2'

def fee_pct():
    return TAKER_FEE_PCT

##############################################################################################
#
# API calls
#

# map from canonical name to 1-Inch name
DEX_NAME_MAP = {'0x API': '0x API', '0x V3': '0x V3', 'Aave': 'Aave', 'AirSwap': 'AirSwap', 'Balancer': 'Balancer', 'Bancor': 'Bancor', 'BETH':'BETH', 'C.R.E.A.M. Swap': 'C.R.E.A.M. Swap', 'Chai': 'Chai', 'Chi Minter': 'Chi Minter', 'Compound': 'Compound',
                'Curve.fi': 'Curve.fi', 'Curve.fi v2': 'Curve.fi v2', 'Curve.fi iearn': 'Curve.fi iearn', 'Curve.fi sUSD': 'Curve.fi sUSD', 'Curve.fi BUSD': 'Curve.fi BUSD', 'Curve.fi PAX': 'Curve.fi PAX',
                'Curve.fi renBTC': 'Curve.fi renBTC', 'Curve.fi tBTC': 'Curve.fi tBTC', 'Curve.fi sBTC': 'Curve.fi sBTC', 'Curve.fi hBTC': 'Curve.fi hBTC', 'Curve.fi 3pool': 'Curve.fi 3pool',
                'dForce Swap': 'dForce Swap', 'DODO': 'DODO', 'Fulcrum': 'Fulcrum', 'IdleFinance': 'Idle', 'IEarnFinance': 'iearn', 'Kyber': 'Kyber', 'MakerDAO': 'MakerDAO', 'Mooniswap': 'Mooniswap', 'MultiSplit': 'MultiSplit', 'Multi Uniswap': 'Multi Uniswap', 'mStable': 'mStable', 'Oasis': 'Oasis', 'Pathfinder': 'Pathfinder',
                'PMM': 'PMM',  'PMM1': 'PMM1', 'PMM2': 'PMM2',  'PMM3': 'PMM3',  'PMM4': 'PMM4',  'PMM5': 'PMM5',
                'StableCoinSwap': 'StableCoinSwap', 'Sushi Swap': 'Sushi Swap', 'SUSHI': 'Sushi Swap','Swerve': 'Swerve', 'Synth Depot': 'Synth Depot', 'Synthetix': 'Synthetix', 'Uniswap': 'Uniswap', 'Uniswap V2':'Uniswap V2', 'WETH': 'WETH'}


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


CACHED_SUPPORTED_TOKENS = ['ABT','ABYSS','AMPL','ANT','APPC','AST','BAL','BAT','BLZ','BNT','BTU','CBI','CDT','CND','COMP','CVC','DAI','DAT','DENT','DGX','DTA','ELF','ENG','ENJ','EQUAD','ETHOS','FUN',
            'GEN','GNO','KNC','LBA','LEND','LINK','LRC','MANA','MCO','MKR','MLN','MOC','MTL','MYB','NEXO','NPXS','OMG','OST','PAX','PAY','PLR','POE','POLY','POWR',
            'QKC','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','SPANK','SPN','STORJ','TAU','TKN','TUSD','UNI', 'UMA', 'UPP','USDC','USDT','WBTC','WETH','XCHF','XDCE', 'YFI', 'ZRX']

@functools.lru_cache(1)
def supported_tokens_critical():
    r = requests.get(TOKENS_ENDPOINT)
    try: # this often fails to return a good response, so we used cached data when it does
        supp_tokens_json = r.json()['tokens']
        # print(json.dumps(supp_tokens_json, indent=3))
        return [t['symbol'] for t in supp_tokens_json.values()]
    except json.decoder.JSONDecodeError as e:
        print(f"oneinch_client.supported_tokens() using CACHED_SUPPORTED_TOKENS")
        return CACHED_SUPPORTED_TOKENS


# get quote
def get_quote(from_token, to_token, from_amount=None, to_amount=None, dex=None, verbose=False, debug=False):
    """Returns the price in terms of the from_token - i.e. how many from_tokens to purchase 1 to_token"""
    endpoint = QUOTE_ENDPOINT

    if to_amount or not from_amount: raise ValueError(f"{name()} only works with from_amount")
    for t in [from_token, to_token]:
        if t != 'ETH' and t not in supported_tokens(): return {} # temporary speedup

    from_token_addr = token_utils.addr(from_token)
    to_token_addr = token_utils.addr(to_token)
    query = {'fromTokenAddress': from_token_addr, 'toTokenAddress': to_token_addr, 'amount': token_utils.int_amount(from_amount, from_token)}
    r = None
    try:
        r = requests.get(endpoint, params=query)
        if debug:
            print(f"r.status_code={r.status_code}")
        j = r.json()
        if debug:
            print(f"REQUEST to {endpoint}:\n{json.dumps(query, indent=3)}\n\n")
            print(f"RESPONSE from {endpoint}:\n{json.dumps(j, indent=3)}\n\n")

        if j.get('message'):
            print(f"{sys._getframe(  ).f_code.co_name} returned {j['message']} request was {query} response was {j}")

            time.sleep(1.0 + random.random())  # block each thread for 1-2 seconds to keep from getting rate limited
            return {}
        else:
            # Response:
            # {
            #   "fromToken": {
            #     "symbol": "USDT",
            #     "name": "Tether USD",
            #     "address": "0xdac17f958d2ee523a2206206994597c13d831ec7",
            #     "decimals": 6,
            #     "logoURI": "https://tokens.1inch.exchange/0xdac17f958d2ee523a2206206994597c13d831ec7.png"
            #   },
            #   "toToken": {
            #     "symbol": "WBTC",
            #     "name": "Wrapped BTC",
            #     "address": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
            #     "decimals": 8,
            #     "logoURI": "https://tokens.1inch.exchange/0x2260fac5e5542a773aa44fbcfedf7c193bc2c599.png"
            #   },
            #   "toTokenAmount": "53797189",  // result amount of WBTC (0.538 WBTC)
            #   "fromTokenAmount": "10000000000",
            #   "protocols": [
            #     [
            #       [
            #         {
            #           "name": "CURVE",
            #           "part": 100,
            #           "fromTokenAddress": "0xdac17f958d2ee523a2206206994597c13d831ec7",
            #           "toTokenAddress": "0x6b175474e89094c44da98b954eedeac495271d0f"
            #         }
            #       ],
            #       [
            #         {
            #           "name": "SUSHI",
            #           "part": 100,
            #           "fromTokenAddress": "0x6b175474e89094c44da98b954eedeac495271d0f",
            #           "toTokenAddress": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
            #         }
            #       ],
            #       [
            #         {
            #           "name": "BALANCER",
            #           "part": 100,
            #           "fromTokenAddress": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
            #           "toTokenAddress": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
            #         }
            #       ]
            #     ]
            #   ],
            #   "estimatedGas": 590385   // do not use gas limit from the quote method
            # }

            source_token = j['fromToken']['symbol']
            source_amount = token_utils.real_amount(j['fromTokenAmount'], source_token)
            destination_token = j['toToken']['symbol']
            destination_amount = token_utils.real_amount(j['toTokenAmount'], destination_token)
            price = source_amount / destination_amount if destination_amount else 0.0

            routes = j['protocols']
            # if len(routes) > 1: print(f"\n\nNUM ROUTES = {len(routes)}\n\n")
            first_route = routes[0]
            if len(first_route) == 1:
                segment = first_route[0]
                exchanges_parts = {ex['name']: ex['part'] for ex in segment if ex['part']}
            else: # multiple segments
                exchanges_parts = {}
                for segment in first_route:
                    segment_from_token = token_utils.tokens_by_addr().get(segment[0]['fromTokenAddress'])
                    segment_to_token = token_utils.tokens_by_addr().get(segment[0]['toTokenAddress'])
                    pair_label = f"{segment_to_token}/{segment_from_token}"
                    exchanges_parts[pair_label] = {ex['name']: ex['part'] for ex in segment if ex['part']}
            # print(f"exchanges_parts={exchanges_parts}")

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
            if debug: print(f"FAILED REQUEST to {endpoint}:\n{json.dumps(query, indent=3)}\n\n")
        return {}

def get_swap(from_token, to_token, from_amount=None, to_amount=None, dex=None, from_address=None, slippage=50, verbose=False, debug=False):
    endpoint = SWAP_ENDPOINT
    query = {'fromTokenSymbol': from_token, 'toTokenSymbol': to_token, 'amount': token_utils.int_amount(from_amount, from_token),
             'fromAddress': IDEX_ADDRESS, 'slippage': DEFAULT_MAX_SLIPPAGE_PERCENT }

    if debug: print(f"REQUEST to {endpoint}:\n{json.dumps(query, indent=3)}\n\n")
    r = None
    try:
        r = requests.get(endpoint, params=query)
        j = r.json()
        if debug: print(f"RESPONSE from {endpoint}:\n{json.dumps(j, indent=3)}\n\n")

        if j.get('message'):
            print(f"{sys._getframe(  ).f_code.co_name} returned {j['message']} request was {query} response was {j}")
            return {}
        else:
            source_token_addr = j['from']
            # TODO: implement response parsing

    except (ValueError, requests.exceptions.RequestException) as e:
        print(f"{name()} {query} raised {e}: {r.text[:128] if r else 'no JSON returned'}")
        return {}