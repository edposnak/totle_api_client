import json
import sys
import functools
import requests
import token_utils

API_BASE = 'https://dex.watch/api'
EXCHANGES_ENDPOINT = API_BASE + '/exchanges'
PAIRS_ENDPOINT = API_BASE + '/pairs'
PAIR_ETH_ENDPOINT = API_BASE + '/pair/ETH'

class DexWatchAPIException(Exception):
    pass

def name():
    return 'dex.watch'


########################################################################################################################
#
# API calls
#

# get exchanges
@functools.lru_cache(1)
def exchanges():
    return { e['dex_name']: e['dex'] for e in exchanges_json() }

@functools.lru_cache(1)
def exchanges_json():
    r = requests.get(EXCHANGES_ENDPOINT).json()
    return r['exchanges']


# get pairs
@functools.lru_cache(1)
def pairs():
    return { e['symbol']: e['volume'] for e in pairs_json() }

@functools.lru_cache(1)
def pairs_json():
    r = requests.get(PAIRS_ENDPOINT).json()
    return r['pairs']


def eth_pair_json(token, interval='1d'):
    # https://dex.watch/api/pair/ETH/0d8775f648430679a709e98d2b0cb6250d2887ef?interval=1d
    query = {'interval': interval }
    token_addr_without_0x = token_utils.addr(token)[2:]

    url = f"{PAIR_ETH_ENDPOINT}/{token_addr_without_0x}"
    r = requests.get(url, params=query).json()
    return r['per_dexes']

