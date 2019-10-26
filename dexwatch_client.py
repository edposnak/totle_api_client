import sys
import functools
import requests
import token_utils

API_BASE = 'https://dex.watch/api'
EXCHANGES_ENDPOINT = API_BASE + '/exchanges'

class DexWatchAPIException(Exception):
    pass

def name():
    return 'dex.watch'


##############################################################################################
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
