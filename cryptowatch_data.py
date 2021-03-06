import os
import csv
import json
from datetime import datetime
import totle_client
import cryptowatch_client

########################################################################################################################
# read in data
DATA_DIR = f"{os.path.dirname(os.path.abspath(__file__))}/data"

DAY_VOLUME = 90
MAX_RANK = 100


########################################################################################################################
# get recommendations for better tokens to use in data/pairs API

def get_rank_and_mkt_cap(t, mkt_cap_data):
    rank, mkt_cap = mkt_cap_data[t] if t in mkt_cap_data else ('?', '?')
    if mkt_cap != '?': mkt_cap = f"${mkt_cap / 10 ** 6:.0f}M"
    rank = str(rank)
    return rank, mkt_cap

def get_dexwatch_vol_trades(day_volume=DAY_VOLUME):
    dexwatch_vol_trades = {}
    with open(f'{DATA_DIR}/dexwatch_top_300_tokens_by_{day_volume}_day_volume.csv', newline='') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=None)
        for row in reader:
            token = row['TOKEN']
            volume = float(row['VOLUME'])
            trades = int(row['TRADES'])
            if token != 'ETH':
                dexwatch_vol_trades[token] = (volume, trades)
    return dexwatch_vol_trades

def get_cmc_token_market_cap():
    cmc_token_market_cap, rank = {}, 0
    with open(f'{DATA_DIR}/cmc_tokens.json') as f:
        cmc_data = json.load(f)['data']
        for t in cmc_data:
            rank += 1
            sym, platform = t['symbol'], t['platform'].get('name')
            if platform and (platform == 'Ethereum' or sym == 'USDT'):
                mkt_cap = float(t['quote']['USD']['market_cap'] or 0)
                if mkt_cap > 0 and sym not in cmc_token_market_cap:
                    cmc_token_market_cap[sym] = (rank, mkt_cap)
    return cmc_token_market_cap


def recommend_better_tokens(day_volume=DAY_VOLUME):
    dexwatch_vol_trades = get_dexwatch_vol_trades(day_volume)
    cmc_token_market_cap = get_cmc_token_market_cap()
    totle_pairs = totle_client.get_trades_pairs()

    # global volume, trades, token, rank, mkt_cap
    min_volume = min([v for v, t in dexwatch_vol_trades.values()])  # min_volume puts an upper bound on tokens not in dexwatch_vol_trades
    totle_pairs_with_stats = []
    for b, _ in totle_pairs:
        if b in dexwatch_vol_trades:
            volume, trades = dexwatch_vol_trades[b]
            totle_pairs_with_stats.append((volume, trades, b))
        else:
            totle_pairs_with_stats.append((0, 0, b))

    print(f"\n\nCurrent Totle tokens sorted by {day_volume}-day volume")
    for volume, trades, token in reversed(sorted(totle_pairs_with_stats)):
        rank, mkt_cap = get_rank_and_mkt_cap(token, cmc_token_market_cap)
        print(f"{token:<8}\tvolume={volume:<10} \ttrades={trades:<8} \tmarket_cap={mkt_cap} (#{rank})")

    print(f"\n\nPotential replacements based on {day_volume}-day volume alone:")
    for token in dexwatch_vol_trades:
        volume, trades = dexwatch_vol_trades[token]
        if [token, 'ETH'] not in totle_pairs and volume > 10.0 * day_volume:
            rank, mkt_cap = get_rank_and_mkt_cap(token, cmc_token_market_cap)
            print(f"{token:<8}\tvolume={volume:<10} \ttrades={trades:<8} \tmarket_cap={mkt_cap} (#{rank})")

    print(f"\n\nPotential replacements based on {day_volume}-day volume and CMC rank < {MAX_RANK}:")
    for token in dexwatch_vol_trades:
        volume, trades = dexwatch_vol_trades[token]
        if [token, 'ETH'] not in totle_pairs and volume > 2.0 * day_volume:
            rank, mkt_cap = get_rank_and_mkt_cap(token, cmc_token_market_cap)
            if rank == '?' or int(rank) > MAX_RANK: continue
            print(f"{token:<8}\tvolume={volume:<10} \ttrades={trades:<8} \tmarket_cap={mkt_cap} (#{rank})")



########################################################################################################################
# Compare Totle's API results to CW's, list any discrepancies

def find(t, trades):
    for j in trades:
        if j['timestamp'] == t['timestamp'] and float(j['price']) == t['price'] and float(j['amount']) == t['amount']:
            return t
    return None


def check_cw_api_with_totle_trades_api(verbose=False, print_last=False):
    pairs= totle_client.get_trades_pairs()
    # pairs, verbose = [('CVC', 'ETH')], True
    try:
        for base, quote in pairs:
            print(f"\n\nDoing {base}/{quote} ...")
            # totle_trades = totle_client.get_trades(base, quote, limit=10)
            # tts = [f"{j['timestamp']}\t{float(j['price']):.8f}\t{float(j['amount']):<20.6f}" for j in totle_trades]
            # for i in range(len(tts)): print(f"{tts[i]}")

            cw_trades = cryptowatch_client.get_trades(base, quote)

            found = []
            totle_trades = totle_client.get_trades(base, quote, limit=len(cw_trades))
            for t in cw_trades:
                ft = find(t, totle_trades)
                if ft: found.append(ft)

            print(f"found {len(found)}/{len(cw_trades)} trades")
            print(f"last CW trade was: {datetime.fromtimestamp(list(reversed(cw_trades))[0]['timestamp'])}")

            if verbose or len(found) != len(cw_trades):
                print(f"Totle                                           Cryptowatch")
                tts = [f"{j['timestamp']}\t{float(j['price']):.8f}\t{float(j['amount']):<20.6f}" for j in totle_trades]
                cts = [f"{j['timestamp']}\t{float(j['price']):.8f}\t{float(j['amount']):<20.6f}" for j in reversed(cw_trades)]
                for i in range(len(tts)): print(f"{tts[i]}\t{cts[i]}")

    except totle_client.TotleAPIException as e:
        print(f"{type(e)} {e}")
        for a in e.args: print(a)

########################################################################################################################
# main

# recommend_better_tokens()
check_cw_api_with_totle_trades_api()

