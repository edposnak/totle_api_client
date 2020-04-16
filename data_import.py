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
import totle_client

import exchange_utils
from v2_compare_prices import canonicalize_and_sort_splits

CSV_DATA_DIR = f"{os.path.dirname(os.path.abspath(__file__))}/outputs"

# don't lru_cache() a generator, the second time it will not produce any data
def csv_row_gen(file, only_splits=False, only_non_splits=False, only_totle_splits=False, only_totle_non_splits=False):
    # print(f"csv_row_gen doing {file}, only_splits={only_splits}, only_non_splits={only_non_splits}) ...")
    with open(file, newline='') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=None)

        for row in reader:
            splits = canonicalize_and_sort_splits(row.get('splits'))
            totle_splits = canonicalize_and_sort_splits(row.get('totle_splits'))

            if only_splits and len(splits) < 2: continue
            if only_totle_splits and len(totle_splits) < 2: continue
            if only_non_splits and len(splits) > 1: continue
            if only_totle_non_splits and len(totle_splits) > 1: continue

            id, time, action = row['id'], row['time'], row['action']  # datetime.fromisoformat(row['time']).isoformat(' ', 'seconds')

            trade_size, token = float(row['trade_size']), row['token']
            exchange, exchange_price = row['exchange'], float(row['exchange_price'])
            totle_used, totle_price, pct_savings = row['totle_used'], float(row['totle_price']), float(row['pct_savings']),
            # Some older CSVs have the non-splittable dexs in the ex_prices column
            ex_prices = exchange_utils.canonical_and_splittable(eval(row.get('ex_prices') or '{}'))

            if pct_savings < -1.0:
                print(f"{pct_savings} vs {exchange} buying {token} for {trade_size} ETH using {totle_used} {totle_splits} id={id}")

            yield time, action, trade_size, token, exchange, exchange_price, totle_used, totle_price, pct_savings, splits, ex_prices



@functools.lru_cache()
def parse_csv_files(csv_files, **kwargs):
    """Returns 2 dicts containing pct savings and prices/split data both having the form
    token: { trade_size:  {exchange: [sample, sample, ...], ...}
    kwargs have these defaults: only_splits=False, only_non_splits=False
    """

    per_token_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    slip_price_diff_splits = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for file in csv_files:
        per_file_base_prices = {}
        for _, _, trade_size, token, exchange, exchange_price, _, totle_price, pct_savings, splits, _ in csv_row_gen(file, **kwargs):
            if not per_file_base_prices.get(token): # this assumes prices recorded from lowest to highest for a token
                per_file_base_prices[token] = totle_price  # should be same for all aggs, but is slightly different sometimes

            slip = (totle_price / per_file_base_prices[token]) - 1.0  # should be 0 for the lowest trade_size
            # i.e. slip = (totle_price - per_file_base_prices[token]) / per_file_base_prices[token]

            slip = 0.0 if slip < 0.0 and slip > -0.00001 else slip # get rid of -0.0000
            price_diff = (totle_price - exchange_price) / exchange_price

            slip_price_diff_splits[token][trade_size][exchange].append((slip, price_diff, splits))
            per_token_savings[token][trade_size][exchange].append(pct_savings)


    return per_token_savings, slip_price_diff_splits

@functools.lru_cache()
def read_slippage_csvs(csv_files=None):
    """Returns a dict of price_slip_cost data points, i.e. {token: {trade_size: {exchange: [ (psc), (psc) ] }}}"""
    csv_files = csv_files or glob.glob(f'{CSV_DATA_DIR}/*buy_slippage.csv')

    tok_ts_ex_pscs = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for file in csv_files:
        print(f"reading {file} ...")
        f_exchange, f_token, *_ = os.path.basename(file).split('_')
        with open(file, newline='') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=None)
            # time,action,trade_size,token,exchange,exchange_price,slippage,cost
            for row in reader:
                # time = datetime.fromisoformat(row['time']).isoformat(' ', 'seconds')
                trade_size = float(row['trade_size'])
                tok_ts_ex_pscs[f_token][trade_size][f_exchange].append( (float(row['exchange_price']), float(row['slippage']), float(row['cost'])) )

    return tok_ts_ex_pscs # TODO: don't return defaultdicts, users should get key errors


# generator
def pct_savings_gen(per_token_savings):
    """Generates a sequence of (token, trade_size, agg/exchange, [pct_savings]) for all leaves in the given dict"""
    for token, ts_ex_savings in sorted(per_token_savings.items()):
        for trade_size, ex_savings in ts_ex_savings.items():
            for exchange, pct_savings in ex_savings.items():
                yield token, trade_size, exchange, pct_savings



########################################################################################################################
# JSON file aggregation functions

DEX_AG = dexag_client.name()
ONE_INCH = oneinch_client.name()
PARASWAP = paraswap_client.name()
TOTLE_EX = totle_client.name()
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
