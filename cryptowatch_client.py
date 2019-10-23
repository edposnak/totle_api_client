import requests

API_BASE = 'https://staging-api.service.cryptowat.ch/markets/totle'

TRADES_ENDPOINT = API_BASE + '/daieth/trades'

EXCHANGE_INFO_ENDPOINT = API_BASE + '/exchangeInfo'
DEPTH_ENDPOINT = API_BASE + '/depth'


class CryptowatchAPIException(Exception):
    pass

def name():
    return 'Cryptowatch'

def trades_endpoint(base, quote):
    return API_BASE + f"/{base + quote}/trades"

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

