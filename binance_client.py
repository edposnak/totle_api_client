import requests

API_BASE = 'https://api.binance.com/api/v1'
EXCHANGE_INFO_ENDPOINT = API_BASE + '/exchangeInfo'
DEPTH_ENDPOINT = API_BASE + '/depth'

TAKER_FEE_PCT = 0.1
# https://www.binance.com/en/fee/schedule
# Taker fee is 0.1% up to VIP 4 level

class BinanceAPIException(Exception):
    pass

def name():
    return 'Binance'

def fee_pct():
    return TAKER_FEE_PCT

##############################################################################################
#
# API calls
#

def get_pairs(quote='ETH'):
    """Returns pairs for the given quote asset"""
    j = requests.get(EXCHANGE_INFO_ENDPOINT).json()

    # if j.get('msg'): # not sure this simple query can possibly return an error
    return [ (s['baseAsset'], s['quoteAsset']) for s in j['symbols'] if s['quoteAsset'] == quote ]

def get_overlap_pairs(totle_tokens, quote='ETH'):
    return [ (b,q) for b,q in get_pairs(quote) if b in totle_tokens ]



DEPTH_LEVELS = [5, 10, 20, 50, 100, 500, 1000, 5000]

def get_depth(base, quote, level=4):
    query = { 'symbol': base + quote, 'limit': DEPTH_LEVELS[level] }
    j = requests.get(DEPTH_ENDPOINT, params=query).json()

    if j.get('msg'):
        raise BinanceAPIException(f"{j['msg']} ({j['code']}): request was {query} response was {j}")
    else:
        s_to_f = lambda p: tuple(map(float, p))
        return list(map(s_to_f, j['bids'])), list(map(s_to_f, j['asks']))


