import requests
import json

API_BASE = 'https://api.huobi.pro'
SYMBOLS_ENDPOINT = API_BASE + '/v1/common/symbols'
DEPTH_ENDPOINT = API_BASE + '/market/depth'

TAKER_FEE_PCT = 0.2
# 0.2% for lowest tier (sources: https://www.huobi.co/en-us/fee https://huobiglobal.zendesk.com/hc/en-us/articles/360000210281-Announcement-New-Tiered-Fee-Structure)
# 0.03% for VIPs (DMs?) (sources: https://www.huobi.co/en-us/fee https://huobiglobal.zendesk.com/hc/en-us/articles/360000113122-Fees)

class HuobiAPIException(Exception):
    pass

def name():
    return 'Huobi'

def fee_pct():
    return TAKER_FEE_PCT

##############################################################################################
#
# API calls
#

BAD_PAIRS = [('ven', 'eth')]

def get_pairs(quote='ETH'):
    """Returns pairs for the given quote asset"""
    h_quote = quote.lower()
    j = requests.get(SYMBOLS_ENDPOINT).json()
    if j['status'] == 'ok':
        lower_pairs = [ (t['base-currency'], t['quote-currency']) for t in j['data'] if t['quote-currency'] == h_quote ]
        # remove pairs that raise errors
        lower_pairs = list(filter(lambda p: p not in BAD_PAIRS, lower_pairs))
        return [ (b.upper(), q.upper()) for b,q in lower_pairs ]
    else:
        raise HuobiAPIException(f"get_pairs({vars()}) raised {j}")

def get_overlap_pairs(totle_tokens, quote='ETH'):
    return [ (b,q) for b,q in get_pairs(quote) if b in totle_tokens ]


def get_depth(base, quote, level=0):
    """returns a dict of price to quantity available at that price"""
    # e.g. symbol=btcusdt&type=step1
    query = { 'symbol': base.lower() + quote.lower(), 'type': f"step{level}" }
    j = requests.get(DEPTH_ENDPOINT, params=query).json()

    if j['status'] == 'ok':
        return j['tick']['bids'], j['tick']['asks']
    else:
        raise HuobiAPIException(f"get_depth({vars()}) raised {j['err-code']}: {j['err-msg']}")

