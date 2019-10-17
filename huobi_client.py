import requests
import json

API_BASE = 'https://api.huobi.pro'
SYMBOLS_ENDPOINT = API_BASE + '/v1/common/symbols'
DEPTH_ENDPOINT = API_BASE + '/market/depth'

class HuobiAPIException(Exception):
    pass

def name():
    return 'Huobi'

##############################################################################################
#
# API calls
#

def get_pairs(uppercase=True):
    j = requests.get(SYMBOLS_ENDPOINT).json()
    if j['status'] == 'ok':

        lower_pairs = [ (t['base-currency'], t['quote-currency']) for t in j['data'] ]
        # remove pairs that raise errors
        lower_pairs.remove(('ven', 'eth'))
        return [ (b.upper(), q.upper()) for b,q in lower_pairs ] if uppercase else lower_pairs
    else:
        raise HuobiAPIException(f"get_pairs({vars()}) raised {j}")

def get_depth(base, quote, level=0):
    """returns a dict of price to quantity available at that price"""
    # e.g. symbol=btcusdt&type=step1
    query = { 'symbol': base.lower() + quote.lower(), 'type': f"step{level}" }
    j = requests.get(DEPTH_ENDPOINT, params=query).json()

    if j['status'] == 'ok':
        return j['tick']['bids'], j['tick']['asks']
    else:
        raise HuobiAPIException(f"get_depth({vars()}) raised {j['err-code']}: {j['err-msg']}")

