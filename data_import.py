#!/usr/local/bin/python3
import functools
import glob
import os
import sys
from datetime import datetime
from collections import defaultdict
import csv
import json

import dexag_client
import oneinch_client
import paraswap_client
import v2_client

import exchange_utils

CSV_DATA_DIR = f"{os.path.dirname(os.path.abspath(__file__))}/outputs"

@functools.lru_cache()
def parse_csv_files(csv_files, only_splits=False, only_non_splits=False):
    """Returns 2 dicts containing pct savings and prices/split data both having the form
    token: { trade_size:  {exchange: [sample, sample, ...], ...}"""

    per_token_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    slip_price_diff_splits = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))


    for file in csv_files:
        with open(file, newline='') as csvfile:
            per_file_base_prices = {}
            reader = csv.DictReader(csvfile, fieldnames=None)
            for row in reader:
                if row.get('splits'):
                    splits = exchange_utils.canonical_keys(eval(row['splits']))
                    if only_splits and len(splits) < 2: continue
                    if only_non_splits and len(splits) > 1: continue

                # time = datetime.fromisoformat(row['time']).isoformat(' ', 'seconds')
                token, trade_size, exchange = row['token'], row['trade_size'], row['exchange']
                exchange_price, totle_price = float(row['exchange_price']), float(row['totle_price'])
                pct_savings, totle_used = float(row['pct_savings']), row['totle_used']

                # Exclude suspicious data
                # if (exchange, token) in  [('DEX.AG', 'ETHOS')]:
                #     # print(f"Excluding data for {token} on {exchange}")
                #     print(f"Excluding {row}")
                #     continue
                # if trade_size in ['0.1', '0.5'] and token == 'ZRX' and exchange == '1-Inch':
                if exchange == '1-Inch' and token == 'ZRX' and trade_size in ['0.1', '0.5'] and pct_savings < -1.0:
                    # print(f"{time} {token} {trade_size} {pct_savings:.2f}% savings: {exchange} price={exchange_price} using {splits} Totle price={totle_price} using {totle_used} ")
                    continue

                if pct_savings > 10.0 or (len(splits) < 1 and pct_savings < -5.0) or (float(trade_size) < 1 and pct_savings < -5.0):
                    # print(f"{time} {token} {trade_size} {pct_savings:.2f}% savings: {exchange} price={exchange_price} using {splits} Totle price={totle_price} using {totle_used} ")
                    continue

                # get slippage and splits
                # TODO use lowest price, maybe DEX.AG is better for this
                if not per_file_base_prices.get(token): # this assumes prices recorded from lowest to highest for a token
                    per_file_base_prices[token] = totle_price  # should be same for all aggs, but is slightly different sometimes

                slip = (totle_price / per_file_base_prices[token]) - 1.0  # should be 0 when trade_size == '0.1'
                # i.e.
                # slip = (totle_price - per_file_base_prices[token]) / per_file_base_prices[token]

                slip = 0.0 if slip < 0.0 and slip > -0.00001 else slip # get rid of -0.0000
                price_diff = (totle_price - exchange_price) / exchange_price

                slip_price_diff_splits[token][trade_size][exchange].append((slip, price_diff, splits))
                per_token_savings[token][trade_size][exchange].append(pct_savings)


    return per_token_savings, slip_price_diff_splits

@functools.lru_cache()
def read_slippage_csvs(csv_files=None):
    """Returns a dict of price_slip_cost data points, i.e. {exchange: {token: [{trade_size: slip}, {trade_size: slip}}]}} """
    exchange_token_pscs = defaultdict(lambda: defaultdict(list))
    csv_files = csv_files or glob.glob(f'{CSV_DATA_DIR}/*buy_slippage.csv')


    for file in csv_files:
        print(f"reading {file} ...")
        f_exchange, f_token, *_ = os.path.basename(file).split('_')
        with open(file, newline='') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=None)
            ts_prices = {}
            # time,action,trade_size,token,exchange,exchange_price,slippage,cost
            for row in reader:
                # time = datetime.fromisoformat(row['time']).isoformat(' ', 'seconds')
                trade_size = row['trade_size']
                ts_prices[trade_size] = (float(row['exchange_price']), float(row['slippage']), float(row['cost']))

            # only include slips that have a baseline quote at 0.1 ETH
            if '0.1' in ts_prices:
                exchange_token_pscs[f_exchange][f_token].append(ts_prices)
            else: # slippage was based off of higher trade_size trades
                print(f"{file}: does not have baseline price for trade_size of 0.1 ETH")

    return exchange_token_pscs


# generator
def pct_savings_gen(per_token_savings):
    """Generates a sequence of (token, trade_size, agg/exchange, [pct_savings]) for all leaves in the given dict"""
    for token, ts_ex_savings in per_token_savings.items():
        for trade_size, ex_savings in ts_ex_savings.items():
            for exchange, pct_savings in ex_savings.items():
                yield token, trade_size, exchange, pct_savings



########################################################################################################################
# JSON file aggregation functions

DEX_AG = dexag_client.name()
ONE_INCH = oneinch_client.name()
PARASWAP = paraswap_client.name()
TOTLE_EX = v2_client.name()
AGG_NAMES = [DEX_AG, ONE_INCH, PARASWAP]

JSON_DATA_DIR = f"{os.path.dirname(os.path.abspath(__file__))}/order_splitting_data"

@functools.lru_cache()
def get_all_splits_by_agg(files=None):
    """Returns an aggregated dict of split data, i.e. token: {trade_size: {agg: [{dex: pct, dex: pct}, {...}, ...]}}"""
    files = files or glob.glob(f'{JSON_DATA_DIR}/2019*ts_splits_by_agg.json')
    tok_ts_splits_by_agg = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for f in files:
        for token, ts_splits_by_agg in json.load(open(f)).items():
            for ts, agg_splits in ts_splits_by_agg.items():
                for agg, split in agg_splits.items():
                    tok_ts_splits_by_agg[token][ts][agg].append(split)

    return dict(sorted(tok_ts_splits_by_agg.items()))

@functools.lru_cache()
def get_all_dexs_with_pair(files=None):
    """Returns an aggregated dict of DEXs used in splits, i.e. token: {trade_size: [dex, dex, ...]}"""
    files = files or glob.glob(f'{JSON_DATA_DIR}/2019*ts_dexs_with_pair.json')

    tok_ts_dexs_with_pair = defaultdict(lambda: defaultdict(list))

    for f in files:
        for token, ts_dexs_with_pair in json.load(open(f)).items():
            for ts, dexs in ts_dexs_with_pair.items():
                tok_ts_dexs_with_pair[token][ts] = list(set(tok_ts_dexs_with_pair[token][ts] + dexs))

    return dict(sorted(tok_ts_dexs_with_pair.items()))

@functools.lru_cache()
def get_all_agg_prices(files=None):
    files = files or glob.glob(f'{JSON_DATA_DIR}/2019*ts_agg_prices.json')

    tok_ts_agg_prices = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for f in files:
        for token, ts_agg_prices in json.load(open(f)).items():
            for ts, agg_prices in ts_agg_prices.items():
                for agg, price in agg_prices.items():
                    tok_ts_agg_prices[token][ts][agg].append(price)

    return dict(sorted(tok_ts_agg_prices.items()))

@functools.lru_cache()
def get_all_dex_prices(files=None):
    files = files or glob.glob(f'{JSON_DATA_DIR}/2019*ts_dex_prices.json')

    tok_ts_dex_prices = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for f in files:
        for token, ts_agg_prices in json.load(open(f)).items():
            for ts, agg_prices in ts_agg_prices.items():
                # test for agg_name keys because Totle's JSON structure is different from aggs
                if any(map(lambda k: k in AGG_NAMES, agg_prices.keys())):
                    # agg dex_prices files look like this:
                    #       "0.1": {
                    #          "DEX.AG": {
                    #             "Uniswap": 0.003936408446252657,
                    #             "Bancor": 0.003993840558066265
                    #          },
                    #          "Paraswap": { ... }
                    for agg, prices in agg_prices.items():
                        tok_ts_dex_prices[token][ts][agg].append(prices)
                else:
                    # Totle's dex_prices file looks like this:
                    #       "0.1": {
                    #          "Ether Delta": 0.00735650292064385,
                    #          "Bancor": 0.003993865645004445,
                    #          "Uniswap": 0.003936433172436365
                    #       },
                    #       "0.5": { ... }
                    # insert Totle as the agg_name in the aggregated data structure
                    tok_ts_dex_prices[token][ts][TOTLE_EX].append(agg_prices)

    return dict(sorted(tok_ts_dex_prices.items()))


# generator
def token_ts_agg_split_gen(tok_ts_splits_by_agg):
    """Generates a sequence of (token, trade_size, agg, split) for all leaves in the given dict"""
    for token, ts_splits_by_agg in tok_ts_splits_by_agg.items():
        for trade_size, agg_splits in ts_splits_by_agg.items():
            for agg, splits in agg_splits.items():
                for split in splits:
                    yield token, trade_size, agg, split

def sorted_unique_trade_sizes(tok_ts_splits_by_agg):
    all_trade_sizes = set(trade_size for token, trade_size, agg, split in token_ts_agg_split_gen(tok_ts_splits_by_agg))
    return list(map(str, sorted(map(float, all_trade_sizes))))


def tokens_split_pct(tok_ts_splits_by_agg, only_token=None, only_agg=None):
    """Returns a dict of token: {trade_size: split_pct}"""
    result = defaultdict(dict)
    n_samples, n_splits = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))

    for token, trade_size, agg, split in token_ts_agg_split_gen(tok_ts_splits_by_agg):
        if only_token and token != only_token: continue
        if only_agg and agg != only_agg: continue
        n_samples[token][trade_size] += 1
        if len(split) > 1: n_splits[token][trade_size] += 1
        # if len(split) > 1: print(f"{token} {trade_size}: {split}")
        result[token][trade_size] = (100.0 * n_splits[token][trade_size]) / n_samples[token][trade_size]
    return result
