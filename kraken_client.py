import requests


API_BASE = 'https://api.kraken.com/0/public'
PAIRS_ENDPOINT = API_BASE + '/AssetPairs'
DEPTH_ENDPOINT = API_BASE + '/Depth'

TAKER_FEE_PCT = 0.26 # lowest tier $0-$50K volume
# https://www.kraken.com/en-us/features/fee-schedule

class KrakenAPIException(Exception):
    pass

def name():
    return 'Kraken'

def fee_pct():
    return TAKER_FEE_PCT

# "The X and Z in front of some pairs is a classification system, which will not be used for the newest coins, where X stands
# for cryptocurrency based assets while Z is for fiat based assets."
X_TOKENS = ['ETH', 'XBT', 'LTC', 'ETC', 'MLN', 'REP', 'XDG', 'XLM', 'XMR', 'XRP', 'ZEC'] # note: DOGE -> XDG
Z_CURRS = ['CAD', 'EUR', 'USD', 'GBP', 'JPY']
def translate_to_kraken(token_symbol):
    """Translates symbols to Kraken names, some of which have Z and X prefixes"""
    if token_symbol in X_TOKENS: return 'X' + token_symbol
    if token_symbol in Z_CURRS: return 'Z' + token_symbol
    return token_symbol

def translate_from_kraken(kraken_symbol):
    """Translates symbols from Kraken names, some of which have Z and X prefixes"""
    t_symbol = kraken_symbol[1:]
    return t_symbol if t_symbol in X_TOKENS + Z_CURRS else kraken_symbol


##############################################################################################
#
# API calls
#

def get_pairs(quote='ETH'):
    """Returns pairs for the given quote asset"""
    k_quote_sym = translate_to_kraken(quote)

    j = requests.get(PAIRS_ENDPOINT).json()

    # {"error":[],"result":{"BATETH":{"altname":"BATETH","wsname":"BAT\/ETH","aclass_base":"currency","base":"BAT","aclass_quote":"currency","quote":"XETH",...
    if j.get('error'):
        raise KrakenAPIException(j['error'])
    else:
        r = j['result']
        return [ (translate_from_kraken(s['base']), translate_from_kraken(s['quote'])) for _, s in r.items() if s['quote'] == k_quote_sym ]

def get_overlap_pairs(totle_tokens, quote='ETH'):
    return [ (b,q) for b,q in get_pairs(quote) if b in totle_tokens ]


DEPTH_LEVELS = [5, 10, 20, 50, 100, 150, 200, 250] # arbitrary translation from level to count

# https://api.kraken.com/0/public/Depth?pair=xbteur&count=4

def get_depth(base, quote, level=4):
    count = level*10

    # https://api.kraken.com/0/public/Depth?pair=REPETH&count=100
    # No need to translate_to_kraken, non-[X,Z] names are ok for pair parameter
    query = { 'pair': base + quote, 'count': DEPTH_LEVELS[level] }
    j = requests.get(DEPTH_ENDPOINT, params=query).json()

    # {"error":[],"result":{"XREPXETH":{"asks":[["0.047650","61.300",1571684656],["0.047720","32.091",1571684657],
    if j.get('error'):
        raise KrakenAPIException(f"{query} got {j['error']}")
    else:
        r = list(j['result'].values())[0]
        s_to_f = lambda p: tuple(map(float, p[:2])) # discard timestamp
        return list(map(s_to_f, r['bids'])), list(map(s_to_f, r['asks']))
