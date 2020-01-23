#!/usr/local/bin/python3

import glob
from collections import defaultdict

import data_import
import dexag_client
import oneinch_client
import paraswap_client
import totle_client
import exchange_utils

DEX_AG = dexag_client.name()
ONE_INCH = oneinch_client.name()
PARASWAP = paraswap_client.name()
TOTLE_EX = totle_client.name()

AGG_NAMES = [DEX_AG, ONE_INCH, PARASWAP]

########################################################################################################################
# functions to get dexs and tokens

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

########################################################################################################################
# functions to get tokens split/not split

def print_tokens_split_by_agg_csv(tokens_by_agg, tokens_supported_by_totle=None):
    print(f"Aggregator,Num Pairs,Tokens")
    for agg in AGG_NAMES:
        print(f"{agg},{len(tokens_by_agg[agg])},\"{','.join(tokens_by_agg[agg])}\"")

    union_tokens = sorted(set(sum(tokens_by_agg.values(), [])))
    print(f"Splittable by any,{len(union_tokens)},\"{','.join(union_tokens)}\"")
    intersection_tokens = [token for token in union_tokens if all(map(lambda tokens: token in tokens, tokens_by_agg.values()))]
    print(f"Splittable by all,{len(intersection_tokens)},\"{','.join(intersection_tokens)}\"")

    if tokens_supported_by_totle:
        union_tokens = [ t for t in union_tokens if t in tokens_supported_by_totle ]
        print(f"Splittable by any and supported by Totle ,{len(union_tokens)},\"{','.join(union_tokens)}\"")
        intersection_tokens = [ t for t in intersection_tokens if t in tokens_supported_by_totle ]
        print(f"Intersection with Totle,{len(intersection_tokens)},\"{','.join(intersection_tokens)}\"")

def print_tokens_not_split_csv():
    tokens_split = sorted(set(sum(aggs_tokens.values(), [])))
    print(f"Total number of tokens_split = {len(tokens_split)}")
    totle_tokens_split = [t for t in tokens_split if t in TOTLE_56]
    not_split = [t for t in TOTLE_56 if t not in totle_tokens_split]
    print(f"Token,Num DEXs,DEXs")
    for token in not_split:
        if len(token_dexs[token]) > 1:
            print(f"{token},{len(token_dexs[token])},\"{','.join(token_dexs[token])}\"")

def min_splits(tok_ts_splits_by_agg, verbose=False):
    """Returns dict of split thresholds for various tokens by each DEX aggregator, i.e. token: { agg: min_trade_size }"""

    # { 'BAT': { 'DEX.AG': 1.0, '1-Inch': 5.0, 'Paradex': inf }, 'CVC': {...}, ...
    min_splits_by_token_agg = defaultdict(lambda: defaultdict(lambda: float('inf')))

    for token, trade_size, agg, split in data_import.token_ts_agg_split_gen(tok_ts_splits_by_agg):
        if len(split) > 1:
            if verbose: print(f"{token} {trade_size} {agg} {split} prev={min_splits_by_token_agg[token][agg]} min={min(min_splits_by_token_agg[token][agg], float(trade_size))}")
            min_splits_by_token_agg[token][agg] = min(min_splits_by_token_agg[token][agg], float(trade_size))

    return dict(sorted(min_splits_by_token_agg.items()))



def token_splits_dex_counts(tok_ts_splits_by_agg, verbose=False):
    """Returns dict of exchanges used for various splits, i.e. token: { dex: n_times }"""
    # { 'BAT': { 'Uniswap': 29, 'Kyber': 43 }, 'CVC': {...}, ...
    tokens_dexs = defaultdict(lambda: defaultdict(int))

    for token, trade_size, agg, split in data_import.token_ts_agg_split_gen(tok_ts_splits_by_agg):
        if len(split) > 1:
            for dex in split:
                tokens_dexs[token][dex] += 1

    return dict(sorted(tokens_dexs.items()))

def tokens_split_by_agg(tok_ts_splits_by_agg):
    """Returns a dict of agg: tokens containing the set of tokens split by each agg"""
    agg_tokens = defaultdict(set)
    for token, trade_size, agg, split in data_import.token_ts_agg_split_gen(tok_ts_splits_by_agg):
        if len(split) > 1:
            agg_tokens[agg].add(token)

    return {agg: sorted(list(tokens)) for agg, tokens in agg_tokens.items()}

def tokens_samples_by_agg(tok_ts_splits_by_agg, only_trade_size=None):
    token_agg_samples = defaultdict(lambda: defaultdict(int))
    for token, trade_size, agg, split in data_import.token_ts_agg_split_gen(tok_ts_splits_by_agg):
        if only_trade_size is None or trade_size == only_trade_size:
            token_agg_samples[token][agg] += 1

    return { token: agg_samples for token, agg_samples in sorted(token_agg_samples.items()) }

def print_token_constants(tok_ts_splits_by_agg, totle_tokens):
    all_aggs, oneinch_dexag, oneinch, dexag, paraswap = [], [], [], [], []

    for token, agg_samples in tokens_samples_by_agg(tok_ts_splits_by_agg).items():
        if len(agg_samples) == 3:
            all_aggs.append(token)
        elif len(agg_samples) == 2:
            oneinch_dexag.append(token)
        else:
            if ONE_INCH in agg_samples: oneinch.append(token)
            if DEX_AG in agg_samples: dexag.append(token)
            if PARASWAP in agg_samples: paraswap.append(token)

    print(f"ALL_AGGS_TOKENS = [{','.join([repr(t) for t in all_aggs])}]")
    print(f"MORE_ONEINCH_DEXAG_TOKENS = [{','.join([repr(t) for t in oneinch_dexag])}]")
    print(f"MORE_ONEINCH_TOKENS = [{','.join([repr(t) for t in oneinch])}]")
    print(f"MORE_DEX_AG_TOKENS = [{','.join([repr(t) for t in dexag])}]")
    print(f"MORE_PARASwAP_TOKENS = [{','.join([repr(t) for t in paraswap])}]")
    print(f"TOTLE_ONEINCH_DEXAG_TOKENS = [{','.join([ repr(t) for t in totle_tokens if t in (all_aggs + oneinch_dexag)])}]")
    print("TOTLE_UNPRICED_TOKENS_TO_TRY = ['ABYSS','LRC','MLN']")


def print_split_pcts_by_token_csv(tok_ts_splits_by_agg, all_trade_sizes, only_token=None, only_agg=None):
    tokens_ts_pcts = data_import.tokens_split_pct(tok_ts_splits_by_agg, only_token=only_token, only_agg=only_agg)
    print(f"\nTOKEN,{','.join(all_trade_sizes)}")
    for token, ts_pcts in tokens_ts_pcts.items():
        print(f"{token}," + ','.join([f"{ts_pcts.get(ts) or '-'}" for ts in all_trade_sizes]))

def token_aggs_quoting(tok_ts_agg_prices):
    """Returns a dict of token: aggs, e.g. {'BAT': ['1-Inch', 'DEX.AG'], 'CVC': ['1-Inch']"""
    token_aggs = {}

    for token, ts_agg_prices in tok_ts_agg_prices.items():
        aggs = set()
        for ts, agg_prices in ts_agg_prices.items():
            aggs |= agg_prices.keys()
        token_aggs[token] = list(aggs)

    return token_aggs

########################################################################################################################
# main

DATA_DIR = 'order_splitting_data'

# This allows parsing a single set of files at a particular timestamp
# filename = sys.argv[1] if len(sys.argv) > 1 else 'order_splitting_data/2019-10-27_17:06:03_tok_ts'
# p = filename.partition('tok_ts') # strip off anything after tok_ts
# filename = p[0]+p[1]

# Aggregate all the 2019* JSON files (which are defaults)
tok_ts_splits_by_agg = data_import.get_all_splits_by_agg()
tok_ts_dexs_with_pair = data_import.get_all_dexs_with_pair()
tok_ts_agg_prices = data_import.get_all_agg_prices()
tok_ts_dex_prices = data_import.get_all_dex_prices()

# Aggregate all the totle* JSON files
totle_tok_ts_splits_by_agg = data_import.get_all_splits_by_agg(tuple(glob.glob(f'{DATA_DIR}/totle*ts_splits_by_agg.json')))
totle_tok_ts_dexs_with_pair = data_import.get_all_dexs_with_pair(tuple(glob.glob(f'{DATA_DIR}/totle*ts_dexs_with_pair.json')))
totle_tok_ts_dex_prices = data_import.get_all_dex_prices(tuple(glob.glob(f'{DATA_DIR}/totle*ts_dex_prices.json')))

all_dexs, all_tokens = all_dexs_and_tokens(tok_ts_dexs_with_pair, totle_tok_ts_dexs_with_pair)
# print(f"{len(all_tokens)} tokens: ", ', '.join(all_tokens))
# print(f"{len(all_dexs)} DEXs: ", ', '.join(all_dexs))
all_trade_sizes = data_import.sorted_unique_trade_sizes(tok_ts_splits_by_agg)
# print(f"{len(all_trade_sizes)} trade_sizes: ", ', '.join(all_trade_sizes))

token_dexs = get_tokens_dexs(tok_ts_dex_prices, totle_tok_ts_dex_prices, tok_ts_dexs_with_pair)
# Print dex/token matrix in CSV form
# print_tokens_dex_csv(token_dexs, all_dexs)

# print a list of tokens supported by each exchange
print(f"\n\nList of tokens supported by each exchange")
for dex in all_dexs:
    supported_tokens = [t for t in token_dexs if dex in token_dexs[t]]
    print(f"{dex},{len(supported_tokens)},\"{','.join(supported_tokens)}\"" )

tokens_samples = tokens_samples_by_agg(tok_ts_splits_by_agg, only_trade_size='2.0')
for t, agg_samples in tokens_samples.items(): print(f"{t} {dict(agg_samples)}")

# print(f"\n\nTokens by number of DEXs listing the ETH pair: ({len(all_tokens)} tokens)")
# print_tokens_num_dexs_csv(token_dexs, supported_tokens=all_tokens, supported_dexs=all_dexs)

# Tokens for which Totle quoted a price
TOTLE_56 = ['ANT','AST','BAT','BMC','BNT','CDAI','CDT','CETH','CND','CUSDC','CVC','CWBTC','CZRX','DAI','DENT','ENG','ENJ','ETHOS','FUN','GNO','KNC','LEND','LINK','MANA','MCO','MKR','MTL','NEXO','NPXS','OMG','PAX','PAY','PLR','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','SPANK','STORJ','TAU','TKN','TUSD','USDC','USDT','VERI','WBTC','XDCE','ZRX']
# To compute TOTLE_56
# totle_56_tokens = set()
# for token, ts_dexs in totle_tok_ts_dexs_with_pair.items():
#     if any(ts_dexs.values()): totle_56_tokens.add(token)
# print(f"len(totle_56_tokens)={len(totle_56_tokens)}")
# print(f"TOTLE_56 = [{','.join(map(repr, totle_56_tokens)) }]")

# print(f"Totle tokens not priced (in TOTLE_56): {set(tok_ts_dexs_with_pair.keys()) - set(TOTLE_56)}")

# print(f"\n\nConstants useful for selecting per-DEX token pairs")
# print_token_constants(tok_ts_splits_by_agg, TOTLE_56)

ACTIVE_TOTLE_DEXS = ['Ether Delta', 'Kyber', 'Bancor', 'Oasis', 'Uniswap', 'Compound', '0xMesh']

# print(f"\n\nTokens supported by Totle by number of DEXs active on Totle: ({len(TOTLE_56)} tokens)")
# print_tokens_num_dexs_csv(token_dexs, supported_tokens=TOTLE_56, supported_dexs=ACTIVE_TOTLE_DEXS)
#
# print(f"\n\nTokens supported by Totle by number of DEXs: ({len(TOTLE_56)} tokens)")
# print_tokens_num_dexs_csv(token_dexs, supported_tokens=TOTLE_56)

# print("\n\nCount of DEXs used to split each token")
# print(json.dumps(token_splits_dex_counts(tok_ts_splits_by_agg), indent=3))

print("\n\nList of tokens split by agg")
aggs_tokens = tokens_split_by_agg(tok_ts_splits_by_agg)
print_tokens_split_by_agg_csv(aggs_tokens, tokens_supported_by_totle=TOTLE_56)

print(f"\n\nTotle tokens that were never split by any aggregator but listed on multiple DEXs:")
print_tokens_not_split_csv()

# Tokens priced by Totle and split by at least 1 agg
TOTLE_39 = ['ANT','AST','BAT','BNT','CDT','CND','CVC','DAI','ENG','ENJ','ETHOS','GNO','KNC','LINK','MANA','MCO','MKR','OMG','PAX','PAY','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','STORJ','TKN','TUSD','USDC','USDT','WBTC','ZRX']
# To compute TOTLE_39
# print(f"len(totle_tokens_split)={len(totle_tokens_split)}")
# print(f"TOTLE_39 = [{','.join(map(repr, totle_tokens_split)) }]")

print("\n\nSplit percentage by token")
# print_split_pcts_by_token_csv(tok_ts_splits_by_agg, all_trade_sizes)
for token in ['ENJ', 'MKR']:
    print(f"\n{token} (all)")
    print_split_pcts_by_token_csv(tok_ts_splits_by_agg, all_trade_sizes, only_token=token)
    for agg in [ONE_INCH, DEX_AG, PARASWAP]:
        print(f"{token} ({agg} only)")
        print_split_pcts_by_token_csv(tok_ts_splits_by_agg, all_trade_sizes, only_token=token, only_agg=agg)
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
# print("\n\nAggregators list of tokens split")
# for agg in AGG_NAMES:
#     print(f"{agg}: {','.join([token for token,aggs in aggs_quoted.items() if agg in aggs])}")
#
#
