import requests

API_BASE = 'https://api.cryptowat.ch'

STAGING_API_BASE = 'https://staging-api.service.cryptowat.ch'
TOTLE_API_BASE = STAGING_API_BASE + '/markets/totle'

MARKETS_API_BASE = API_BASE + '/markets'

class CryptowatchAPIException(Exception):
    pass

def name():
    return 'Cryptowatch'

def trades_endpoint(base, quote):
    return TOTLE_API_BASE + f"/{base + quote}/trades"

def orderbook_endpoint(cex_name, base, quote):
    return MARKETS_API_BASE + f"/{cex_name.lower()}/{base.lower()}{quote.lower()}" + '/orderbook'

##############################################################################################
#
# API calls
#

def get_trades(base, quote):
    """returns an array of dicts, which include timestamp, price, and amount for each trade"""
    j = requests.get(trades_endpoint(base, quote)).json()

    # {"result": [ [0, 1571697560, 0.0057971780392391387, 1023.32814569], [0, 1571698284, 0.00581010009964029642, 138.079838830444032476] ], ... }
    result = []
    for t in j['result']:
        id, timestamp, price, amount = t
        result.append({'timestamp': timestamp, 'price': price, 'amount': amount})

    return result

def get_books(cex_name, base, quote='ETH'):
    """gets the bids and asks on the given CEX for the given pair"""
    # supported CEXs include: bitflyer bittrex gemini luno gate.io bitfinex kraken cexio bisq bitmex okex cryptofacilities
    #   liquid quoine bitbay hitbtc binance binance-us huobi poloniex coinbase-pro bitstamp bit-z bithumb coinone dex okcoin
    # https://api.cryptowat.ch/markets/binance/omgeth/orderbook
    url = orderbook_endpoint(cex_name, base, quote)
    j = requests.get(orderbook_endpoint(cex_name, base, quote)).json()
    r = j['result']
    return r['bids'], r['asks']


