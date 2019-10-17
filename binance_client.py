import requests

API_BASE = 'https://api.binance.com/api/v1'
EXCHANGE_INFO_ENDPOINT = API_BASE + '/exchangeInfo'
DEPTH_ENDPOINT = API_BASE + '/depth'

class BinanceAPIException(Exception):
    pass

def name():
    return 'Binance'

##############################################################################################
#
# API calls
#

def get_pairs():
    j = requests.get(EXCHANGE_INFO_ENDPOINT).json()

    return [ (s['baseAsset'], s['quoteAsset']) for s in j['symbols'] ]

def get_overlap_pairs(totle_tokens, quote='ETH'):
    return [ (b,q) for b,q in get_pairs() if q == quote and b in totle_tokens ]


DEPTH_LEVELS = [5, 10, 20, 50, 100, 500, 1000, 5000]

def get_depth(base, quote, level=4):
    query = { 'symbol': base + quote, 'limit': DEPTH_LEVELS[level] }
    j = requests.get(DEPTH_ENDPOINT, params=query).json()

    s_to_f = lambda p: tuple(map(float, p))
    return list(map(s_to_f, j['bids'])), list(map(s_to_f, j['asks']))


