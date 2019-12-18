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

def eth_pair_json(token, interval='1d'):
    # https://dex.watch/api/pair/ETH/0d8775f648430679a709e98d2b0cb6250d2887ef?interval=1d
    query = {'interval': interval }
    token_addr_without_0x = token_utils.addr(token)[2:]

    url = f"{PAIR_ETH_ENDPOINT}/{token_addr_without_0x}"
    r = requests.get(url, params=query).json()
    return r['per_dexes']

########################################################################################################################
# test

MORE_AGG_TOKENS = ['ABT','APPC','BLZ','BTU','CBI','DAT','DGX','DTA','ELF','EQUAD','GEN','IDAI','LBA','MOC','MYB','OST','QKC','SPN','UPP','WETH','XCHF']
UNSUPPORTED_TOKENS = ['IDAI','IKNC','ILINK','IREP','IUSDC','IWBTC','IZRX','SETH']

vol_interval='30d'
pf = lambda v: f"{v:<16}"
pd = lambda f: f"{float(f):<16.4f}"
print(pf('Token'), pf('DEX'), pf('Num Trades'), pf(f"{vol_interval} Vol"), pf("Prev Vol"))
for token in MORE_AGG_TOKENS + UNSUPPORTED_TOKENS:
    vol_info = eth_pair_json(token, interval=vol_interval)
    for v in vol_info:
        dex, num_trades = v['dex_name'], v['trades']
        vol, prev_vol = v['volume'], v['volume_previous']
        print(f"{pf(token)} {pf(dex)} {pf(num_trades)} {pd(vol)} {pd(prev_vol)}")
