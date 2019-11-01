#!/usr/local/bin/python3

import sys
import glob
import json
from collections import defaultdict

import dexag_client
import oneinch_client
import paraswap_client
import v2_client
import exchange_utils

DEX_AG = dexag_client.name()
ONE_INCH = oneinch_client.name()
PARASWAP = paraswap_client.name()
TOTLE_EX = v2_client.name()

AGG_NAMES = [DEX_AG, ONE_INCH, PARASWAP]

COMMON_DEXS = ['0xMesh', 'AirSwap', 'Bancor', 'Kyber', 'Oasis', 'Radar Relay', 'Uniswap']

def get_tokens_dexs(tok_ts_dex_prices, totle_tok_ts_dex_prices, tok_ts_dexs_with_pair):
    """Returns a dict of tokens: dexes found to support the token based on the 3 input dicts"""
    token_dexs = defaultdict(set)

    # get dexs used by agg's supplying dex prices
    for token, ts_agg_dex_prices in tok_ts_dex_prices.items():
        dexs_for_token = set()
        for ts, agg_dex_prices in ts_agg_dex_prices.items():
            for agg, dex_prices in agg_dex_prices.items():
                for prices in dex_prices:
                    dexs_for_token |= prices.keys()
        token_dexs[token] |= dexs_for_token

    # since 1-Inch doesn't provide any dex prices we use tok_ts_dexs_with_pair, to take into account 1-Inch's splits
    for token, ts_dexs in tok_ts_dexs_with_pair.items():
        token_dexs[token] |= set(sum(ts_dexs.values(), []))

    # add in Totle's dex prices
    for token, ts_agg_dex_prices in totle_tok_ts_dex_prices.items():
        dexs_for_token = set()
        for ts, agg_dex_prices in ts_agg_dex_prices.items():
            for agg, dex_prices in agg_dex_prices.items():
                for prices in dex_prices:
                    dexs_for_token |= prices.keys()
        token_dexs[token] |= dexs_for_token

    # sort the keys and canonize/uniq the values
    return { token: list(set(exchange_utils.canonical_names(dexs))) for token, dexs in sorted(token_dexs.items()) }


def print_tokens_num_dexs_csv(token_dexs, supported_tokens=None, supported_dexs=None):
    ndexs_tokens = defaultdict(list)
    supported_tokens = supported_tokens or token_dexs.keys()
    for totle_token in supported_tokens:
        dexs = token_dexs[totle_token]
        filtered_dexs = [d for d in dexs if d in supported_dexs] if supported_dexs else dexs
        ndexs_tokens[len(filtered_dexs)].append(totle_token)
    print(f"Num DEXs,Pairs")
    for ndexs, tokens in sorted(ndexs_tokens.items()):
        print(f"{ndexs},\"{','.join(tokens)}\"")

def print_tokens_dex_csv(token_dexs, dex_columns):
    print(f"Token,{','.join(dex_columns)}")
    for token, dexs in token_dexs.items():
        dex_strs = map(lambda d: 'X' if d in dexs else '', dex_columns)
        print(f"{token},{','.join(dex_strs)}")

def print_tokens_split_by_agg_csv(tokens_by_agg, tokens_supported_by_totle=None):
    print(f"Aggregator,Num Pairs,Tokens")
    for agg in AGG_NAMES:
        print(f"{agg},{len(tokens_by_agg[agg])},\"{','.join(tokens_by_agg[agg])}\"")

    union_tokens = sorted(set(sum(tokens_by_agg.values(), [])))
    print(f"Union,{len(union_tokens)},\"{','.join(union_tokens)}\"")
    intersection_tokens = [token for token in union_tokens if all(map(lambda tokens: token in tokens, tokens_by_agg.values()))]
    print(f"Intersection,{len(intersection_tokens)},\"{','.join(intersection_tokens)}\"")

    if tokens_supported_by_totle:
        union_tokens = [ t for t in union_tokens if t in tokens_supported_by_totle ]
        print(f"Union with Totle,{len(union_tokens)},\"{','.join(union_tokens)}\"")
        intersection_tokens = [ t for t in intersection_tokens if t in tokens_supported_by_totle ]
        print("\n\n")
        print(f"Intersection with Totle,{len(intersection_tokens)},\"{','.join(intersection_tokens)}\"")

def min_splits(tok_ts_splits_by_agg, verbose=False):
    """Returns dict of split thresholds for various tokens by each DEX aggregator, i.e. token: { agg: min_trade_size }"""

    # { 'BAT': { 'DEX.AG': 1.0, '1-Inch': 5.0, 'Paradex': inf }, 'CVC': {...}, ...
    min_splits_by_token_agg = defaultdict(lambda: defaultdict(lambda: float('inf')))

    for token, ts_splits_by_agg in tok_ts_splits_by_agg.items():
        for trade_size, agg_splits in ts_splits_by_agg.items():
            for agg, splits in agg_splits.items():
                if any([ len(s) > 1 for s in splits]):
                    if verbose: print(f"{token} {trade_size} {agg} {splits} prev={min_splits_by_token_agg[token][agg]} min={min(min_splits_by_token_agg[token][agg], float(trade_size))}")
                    min_splits_by_token_agg[token][agg] = min(min_splits_by_token_agg[token][agg], float(trade_size))

    return dict(sorted(min_splits_by_token_agg.items()))

def token_splits_dex_counts(tok_ts_splits_by_agg, verbose=False):
    """Returns dict of exchanges used for various splits, i.e. token: { dex: n_times }"""

    # { 'BAT': { 'Uniswap': 29, 'Kyber': 43 }, 'CVC': {...}, ...
    tokens_dexs = defaultdict(lambda: defaultdict(int))

    for token, ts_splits_by_agg in tok_ts_splits_by_agg.items():
        for trade_size, agg_splits in ts_splits_by_agg.items():
            for agg, splits in agg_splits.items():
                for split in splits:
                    if len(split) > 1:
                        for dex in split:
                            tokens_dexs[token][dex] += 1

    return dict(sorted(tokens_dexs.items()))

def tokens_split_by_agg(tok_ts_splits_by_agg):
    agg_tokens = defaultdict(set)
    for token, ts_splits_by_agg in tok_ts_splits_by_agg.items():
        for trade_size, agg_splits in ts_splits_by_agg.items():
            for agg, splits in agg_splits.items():
                for split in splits:
                    if len(split) > 1:
                        agg_tokens[agg].add(token)

    return {agg: sorted(list(tokens)) for agg, tokens in agg_tokens.items()}


def token_aggs_quoting(tok_ts_agg_prices):
    """Returns a dict of token: aggs, e.g. {'BAT': ['1-Inch', 'DEX.AG'], 'CVC': ['1-Inch']"""
    token_aggs = {}

    for token, ts_agg_prices in tok_ts_agg_prices.items():
        aggs = set()
        for ts, agg_prices in ts_agg_prices.items():
            aggs |= agg_prices.keys()
        token_aggs[token] = list(aggs)

    return token_aggs


def all_dexs_and_tokens(tok_ts_dexs_with_pair, totle_tok_ts_dexs_with_pair):
    agg_dexs = unique_dexs(tok_ts_dexs_with_pair)
    totle_dexs = unique_dexs(totle_tok_ts_dexs_with_pair)
    all_dexs = sorted(list(set(agg_dexs + totle_dexs)))

    agg_tokens = sorted(tok_ts_dexs_with_pair.keys())
    totle_tokens = sorted(totle_tok_ts_dexs_with_pair.keys())  # subset of agg_tokens
    all_tokens = sorted(list(set(agg_tokens + totle_tokens)))

    return all_dexs, all_tokens

def unique_dexs(tok_ts_dexs_with_pair):
    """Returns a sorted list of all dexs that were used"""
    all_dexs = set()
    for token, ts_dexs in tok_ts_dexs_with_pair.items():
        all_dexs |= set(sum(ts_dexs.values(), []))
    return sorted(list(all_dexs))

########################################################################################################################
# JSON file aggregation functions

def get_all_dexs_with_pair(files):
    """Returns an aggregated dict of DEXs used in splits, i.e. token: {trade_size: [dex, dex, ...]}"""
    tok_ts_dexs_with_pair = defaultdict(lambda: defaultdict(list))

    for f in files:
        for token, ts_dexs_with_pair in json.load(open(f)).items():
            for ts, dexs in ts_dexs_with_pair.items():
                tok_ts_dexs_with_pair[token][ts] = list(set(tok_ts_dexs_with_pair[token][ts] + dexs))

    return dict(sorted(tok_ts_dexs_with_pair.items()))

def get_all_splits_by_agg(files):
    """Returns an aggregated dict of split data, i.e. token: {trade_size: {agg: [{dex: pct, dex: pct}, {...}, ...]}}"""
    tok_ts_splits_by_agg = defaultdict(lambda: defaultdict(dict)) # TODO defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for f in files:
        for token, ts_splits_by_agg in json.load(open(f)).items():
            for ts, agg_splits in ts_splits_by_agg.items():
                for agg, split in agg_splits.items():
                    tok_ts_splits_by_agg[token][ts][agg] = (tok_ts_splits_by_agg[token][ts].get(agg) or []) + [split]

    return dict(sorted(tok_ts_splits_by_agg.items()))

def get_all_dex_prices(files):
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

def get_all_agg_prices(files):
    tok_ts_agg_prices = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for f in files:
        for token, ts_agg_prices in json.load(open(f)).items():
            for ts, agg_prices in ts_agg_prices.items():
                for agg, price in agg_prices.items():
                    tok_ts_agg_prices[token][ts][agg].append(price)

    return dict(sorted(tok_ts_agg_prices.items()))


########################################################################################################################
# main

DATA_DIR = 'order_splitting_data'

# This allows parsing a single set of files at a particular timestamp
# filename = sys.argv[1] if len(sys.argv) > 1 else 'order_splitting_data/2019-10-27_17:06:03_tok_ts'
# p = filename.partition('tok_ts') # strip off anything after tok_ts
# filename = p[0]+p[1]

# Aggregate all the 2019* JSON files (2019* filters out totle*)
tok_ts_splits_by_agg = get_all_splits_by_agg(glob.glob(f'{DATA_DIR}/2019*ts_splits_by_agg.json'))
tok_ts_dexs_with_pair = get_all_dexs_with_pair(glob.glob(f'{DATA_DIR}/2019*ts_dexs_with_pair.json'))
tok_ts_agg_prices = get_all_agg_prices(glob.glob(f'{DATA_DIR}/2019*ts_agg_prices.json'))
tok_ts_dex_prices = get_all_dex_prices(glob.glob(f'{DATA_DIR}/2019*ts_dex_prices.json'))

# Aggregate all the totle* JSON files
totle_tok_ts_splits_by_agg = get_all_splits_by_agg(glob.glob(f'{DATA_DIR}/totle*ts_splits_by_agg.json'))
totle_tok_ts_dexs_with_pair = get_all_dexs_with_pair(glob.glob(f'{DATA_DIR}/totle*ts_dexs_with_pair.json'))
totle_tok_ts_dex_prices = get_all_dex_prices(glob.glob(f'{DATA_DIR}/totle*ts_dex_prices.json'))

all_dexs, all_tokens = all_dexs_and_tokens(tok_ts_dexs_with_pair, totle_tok_ts_dexs_with_pair)

totle_tokens = sorted(totle_tok_ts_dexs_with_pair.keys())  # subset of agg_tokens
print(f"len(totle_tokens)={len(totle_tokens)}")

# Print dex/token matrix in CSV form
token_dexs = get_tokens_dexs(tok_ts_dex_prices, totle_tok_ts_dex_prices, tok_ts_dexs_with_pair)
# print_tokens_dex_csv(token_dexs, all_dexs)

# print a list of tokens supported by each exchange
for dex in all_dexs:
    supported_tokens = [t for t in token_dexs if dex in token_dexs[t]]
    print(f"{dex},{len(supported_tokens)},\"{','.join(supported_tokens)}\"" )

print(f"{len(all_tokens)} tokens: ", ', '.join(all_tokens))
print(f"{len(all_dexs)} DEXs: ", ', '.join(all_dexs))

# print(f"\n\nTokens by number of DEXs listing the ETH pair: ({len(all_tokens)} tokens)")
# print_tokens_num_dexs_csv(token_dexs, supported_tokens=all_tokens, supported_dexs=all_dexs)

TOTLE_56 = ['ANT','AST','BAT','BMC','BNT','CDAI','CDT','CETH','CND','CUSDC','CVC','CWBTC','CZRX','DAI','DENT','ENG','ENJ','ETHOS','FUN','GNO','KNC','LEND','LINK','MANA','MCO','MKR','MTL','NEXO','NPXS','OMG','PAX','PAY','PLR','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','SPANK','STORJ','TAU','TKN','TUSD','USDC','USDT','VERI','WBTC','XDCE','ZRX']
TOTLE_39 = ['ANT','AST','BAT','BNT','CDT','CND','CVC','DAI','ENG','ENJ','ETHOS','GNO','KNC','LINK','MANA','MCO','MKR','OMG','PAX','PAY','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','STORJ','TKN','TUSD','USDC','USDT','WBTC','ZRX']

# To compute TOTLE_56
# totle_56_tokens = set()
# for token, ts_dexs in totle_tok_ts_dexs_with_pair.items():
#     for ts, dexs in ts_dexs.items():
#         if dexs: totle_56_tokens.add(token)
# print(f"len(totle_56_tokens)={len(totle_56_tokens)}")
# print(f"TOTLE_56 = [{','.join(map(repr, totle_56_tokens)) }]")
# These were a tries at comprehensions that don't filter correctly
# sup_tokens = set([ token for ts, dexs in ts_dexs.items() for token, ts_dexs in totle_tok_ts_dexs_with_pair.items() if dexs ])
# sup_tokens = set([ token for ts, dexs in ts_dexs.items() if dexs for token, ts_dexs in totle_tok_ts_dexs_with_pair.items()  ])
# print(f"len(sup_tokens)={len(sup_tokens)}")
ACTIVE_TOTLE_DEXS = ['Ether Delta', 'Kyber', 'Bancor', 'Oasis', 'Uniswap', 'Compound', '0xMesh']

print(f"\n\nTokens supported by Totle by number of DEXs active on Totle: ({len(TOTLE_56)} tokens)")
print_tokens_num_dexs_csv(token_dexs, supported_tokens=TOTLE_56, supported_dexs=ACTIVE_TOTLE_DEXS)


# print("\n\nCount of DEXs used to split each token")
# print(json.dumps(token_splits_dex_counts(tok_ts_splits_by_agg), indent=3))

print("\n\nList of tokens split by agg")
aggs_tokens = tokens_split_by_agg(tok_ts_splits_by_agg)
print_tokens_split_by_agg_csv(aggs_tokens, tokens_supported_by_totle=TOTLE_56)

print(f"\n\nTotle tokens that were never split by any aggregator but listed on multiple DEXs:")
tokens_split = sorted(set(sum(aggs_tokens.values(), [])))
totle_tokens_split = [t for t in tokens_split if t in TOTLE_56]
not_split = [t for t in TOTLE_56 if t not in totle_tokens_split]
print(f"\n\nToken,Num DEXs,DEXs")
for token in not_split:
    if len(token_dexs[token]) > 1:
        print(f"{token},{len(token_dexs[token])},\"{','.join(token_dexs[token])}\"")

# To compute TOTLE_39
# print(f"len(totle_tokens_split)={len(totle_tokens_split)}")
# print(f"TOTLE_39 = [{','.join(map(repr, totle_tokens_split)) }]")


exit(0)

# print("\n\nTokens and aggregators providing quotes")
# aggs_quoted = token_aggs_quoting(tok_ts_agg_prices)
# for token, aggs in aggs_quoted.items():
#     # print(f"{token}: {', '.join(aggs)}")
#     for agg in AGG_NAMES:
#         if not agg in aggs: print(f"{agg} had no prices for {token} at any trade size")
#
# print("\n\nAggregators list of tokens quoted")
# for agg in AGG_NAMES:
#     print(f"{agg}: {','.join([token for token,aggs in aggs_quoted.items() if agg in aggs])}")
#
#
# min_splits(tok_ts_splits_by_agg, verbose=True)
#
# print("\n\nAggregators list of tokens split")
# for agg in AGG_NAMES:
#     print(f"{agg}: {','.join([token for token,aggs in aggs_quoted.items() if agg in aggs])}")
#
#
