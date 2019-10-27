import csv
import json
import os

########################################################################################################################
# read in data
DATA_DIR = f"{os.path.dirname(os.path.abspath(__file__))}/data"
print(f"DATA_DIR={DATA_DIR}")

VALID_DAY_VOLUMES = [30,90]
DAY_VOLUME = VALID_DAY_VOLUMES[-1] # currently tells which CSV to query, eventually can be used with dex.watch API for arbitary period


def top_tokens_by_volume(top_n=50, day_volume=DAY_VOLUME):
    if day_volume not in VALID_DAY_VOLUMES: raise ValueError(f"day_volume={day_volume} is not supported. Valid values are {VALID_DAY_VOLUMES}")
    return list(top_tokens_by_volume_with_volume(day_volume).keys())[:top_n]


def top_tokens_by_volume_with_volume(day_volume=DAY_VOLUME):
    with open(csv_filename(day_volume), newline='') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=None)
        return { row['TOKEN'] : row['VOLUME'] for row in reader if row['TOKEN'] != 'ETH' }

def top_tokens_by_market_cap(top_n=50):
    return list(top_tokens_by_market_cap_with_market_cap().keys())[:top_n]

def top_tokens_by_market_cap_with_market_cap():
    cmc_token_market_cap, rank = {}, 0
    for t in get_cmc_data():
        rank += 1
        sym, platform = t['symbol'], t['platform'].get('name')
        if platform and (platform == 'Ethereum' or sym == 'USDT'):
            mkt_cap = float(t['quote']['USD']['market_cap'] or 0)
            if mkt_cap > 0 and sym not in cmc_token_market_cap:
                cmc_token_market_cap[sym] = (rank, mkt_cap)
    return cmc_token_market_cap


def csv_filename(day_volume):
    return f'{DATA_DIR}/dexwatch_top_300_tokens_by_{day_volume}_day_volume.csv'

def get_cmc_data(filename='cmc_tokens.json'):
    f = open(f'{DATA_DIR}/{filename}')
    return json.load(f)['data']
