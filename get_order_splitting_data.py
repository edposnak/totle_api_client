import json
import sys
from collections import defaultdict
import concurrent.futures

import v2_client
import dexag_client
import oneinch_client
import paraswap_client

import exchange_utils
from v2_compare_prices import get_filename_base

TOTLE_EX = v2_client.name()

QUOTE = 'ETH'

# # Tokens not priced by any aggs, including Totle
# UNSUPPORTED_TOKENS = ['CBAT','CREP','IETH','IKNC','ILINK','IREP','IUSDC','IWBTC','IZRX','PPP','PPT','SETH','WTC']
# # Tokens priced by one or more aggs, but not Totle
# MORE_AGG_TOKENS = ['ABT','APPC','BLZ','BTU','CBI','DAT','DGX','DTA','ELF','EQUAD','GEN','IDAI','LBA','MOC','MYB','OST','QKC','SPN','UPP','WETH','XCHF']

# 38 Tokens priced by all aggs (maybe Totle)
ALL_AGGS_TOKENS = ['ABT','ANT','BAT','BNT','BTU','CVC','DAI','DGX','ELF','ENJ','GEN','GNO','KNC','LINK','MANA','MKR','MLN','MTL','OMG','PAX','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','SNT','SNX','TKN','TUSD','USDC','USDT','WBTC','WETH','ZRX']
# Tokens priced by 1-Inch and DEX.AG (maybe Totle)
MORE_ONEINCH_DEXAG_TOKENS = ['ABYSS','APPC','AST','BLZ','CBI','CDT','CND','ENG','EQUAD','ETHOS','FUN','LBA','LEND','LRC','MCO','MOC','NEXO','OST','PAY','PLR','QKC','RPL','SPANK','SPN','STORJ','TAU','UPP','XCHF','XDCE']
# Tokens only priced by 1-Inch (maybe Totle)
MORE_ONEINCH_TOKENS = ['DAT','DENT','DTA','MYB','NPXS']
# Tokens only priced by DEX.AG (maybe Totle)
MORE_DEX_AG_TOKENS = ['CDAI','CETH','CUSDC','CWBTC','CZRX','IDAI','VERI']
# Tokens only priced by Paraswap (maybe Totle)
MORE_PARASwAP_TOKENS = []
# 47 Tokens priced by Totle and all aggs
TOTLE_ONEINCH_DEXAG_TOKENS = ['ANT','AST','BAT','BNT','CDT','CND','CVC','DAI','ENG','ENJ','ETHOS','FUN','GNO','KNC','LEND','LINK','MANA','MCO','MKR','MTL','NEXO','OMG','PAX','PAY','PLR','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','SPANK','STORJ','TAU','TKN','TUSD','USDC','USDT','WBTC','XDCE','ZRX']
# 3 Tokens not priced by Totle but were by both 1-Inch and DEX.AG (maybe Paraswap)
TOTLE_UNPRICED_TOKENS_TO_TRY = ['ABYSS','LRC','MLN']


print(len(TOTLE_ONEINCH_DEXAG_TOKENS))
exit(0)
TRADE_SIZES = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0, 500.0]

# don't bother recording price info for these DEXs; they are never going to be used in splits
EXCLUDE_DEXS = ['ag', 'IDEX', 'DDEX', 'Ethfinex', 'Paradex']

def get_agg_data(*agg_clients, tokens=ALL_AGGS_TOKENS, trade_sizes=TRADE_SIZES, quote=QUOTE):
    filename_base = get_filename_base(dir=DATA_DIR, prefix='agg')

    # get list of tokens on dexag and 1-inch that are tradable/splittable
    tok_ts_dexs_with_pair = defaultdict(dict)
    tok_ts_splits_by_agg = defaultdict(dict)
    tok_ts_agg_prices = defaultdict(dict)
    tok_ts_dex_prices = defaultdict(dict)

    # TODO: sells and compare with buys
    for base in tokens:
        for trade_size in trade_sizes:
            print(f"Doing {base} at {trade_size} {quote} ...")
            futures_agg = {}
            with concurrent.futures.ThreadPoolExecutor() as executor:
                for agg_client in agg_clients:
                    future = executor.submit(agg_client.get_quote, quote, base, from_amount=trade_size, dex='all')
                    futures_agg[future] = agg_client.name()

            dexs_with_pair, splits_by_agg, agg_prices, dex_prices = set(), {}, {}, {}
            for f in concurrent.futures.as_completed(futures_agg):
                agg_name = futures_agg[f]
                pq = f.result()
                if not pq:
                    print(f"{agg_name} did not quote {quote} to {base} at trade size={trade_size}")
                else:
                    splits = exchange_utils.canonical_keys(pq['exchanges_parts'])
                    splits_by_agg[agg_name] = splits
                    dexs_with_pair |= splits.keys()   # assumes each DEX client strips out keys with 0 pct in exchanges_parts
                    agg_prices[agg_name] = pq['price']
                    if pq.get('exchanges_prices'):
                        dps = exchange_utils.canonical_keys(pq['exchanges_prices'])
                        dex_prices[agg_name] = { d: p for d, p in dps.items() if d not in EXCLUDE_DEXS }

            tok_ts_dexs_with_pair[base][trade_size] = list(dexs_with_pair)
            tok_ts_splits_by_agg[base][trade_size] = splits_by_agg
            tok_ts_agg_prices[base][trade_size] = agg_prices
            tok_ts_dex_prices[base][trade_size] = dex_prices

    with open(f'{filename_base}_tok_ts_dexs_with_pair.json', 'w') as outfile:
        json.dump(tok_ts_dexs_with_pair, outfile, indent=3)
    with open(f'{filename_base}_tok_ts_splits_by_agg.json', 'w') as outfile:
        json.dump(tok_ts_splits_by_agg, outfile, indent=3)
    with open(f'{filename_base}_tok_ts_agg_prices.json', 'w') as outfile:
        json.dump(tok_ts_agg_prices, outfile, indent=3)
    with open(f'{filename_base}_tok_ts_dex_prices.json', 'w') as outfile:
        json.dump(tok_ts_dex_prices, outfile, indent=3)


COMPOUND_TOKENS = ['CBAT','CDAI','CETH','CREP','CUSDC','CWBTC','CZRX']
TOTLE_EXCHANGES = integrated_exchanges = list(v2_client.exchanges().keys())


def get_totle_data(tokens=ALL_AGGS_TOKENS, trade_sizes=TRADE_SIZES, quote=QUOTE, exchanges=TOTLE_EXCHANGES):
    filename_base = get_filename_base(dir=DATA_DIR, prefix='totle')

    # get list of tokens on dexag and 1-inch that are tradable/splittable
    tok_ts_dexs_with_pair = defaultdict(dict)
    tok_ts_splits_by_agg = defaultdict(dict)
    tok_ts_dex_prices = defaultdict(dict)

    # TODO: sells and compare with buys
    for base in tokens:
        for trade_size in trade_sizes:
            print(f"Doing {base} at {trade_size} {quote} ...")
            dexs_with_pair, splits_by_agg, dex_prices = set(), {}, {}
            splits_by_agg[TOTLE_EX] = {} # there will just be this one entry, which will list individual DEXs that returned prices

            for dex in exchanges:
                can_dex = exchange_utils.canonical_name(dex)
                if dex == 'Compound' and not base in COMPOUND_TOKENS: continue  # don't waste queries for non-C tokens

                pq = v2_client.get_quote(quote, base, from_amount=trade_size, dex=dex)
                if not pq:
                    print(f"{can_dex} did not have {quote} to {base} at trade size={trade_size}")
                else:
                    splits_by_agg[TOTLE_EX][can_dex] = -1  # -1 indicates this is not a split, just a list of dexs that could be used
                    dexs_with_pair.add(can_dex)
                    dex_prices[can_dex] = pq['price']

            tok_ts_dexs_with_pair[base][trade_size] = list(dexs_with_pair)
            tok_ts_splits_by_agg[base][trade_size] = splits_by_agg
            tok_ts_dex_prices[base][trade_size] = dex_prices

    with open(f'{filename_base}_tok_ts_dexs_with_pair.json', 'w') as outfile:
        json.dump(tok_ts_dexs_with_pair, outfile, indent=3)
    with open(f'{filename_base}_tok_ts_splits_by_agg.json', 'w') as outfile:
        json.dump(tok_ts_splits_by_agg, outfile, indent=3)
    # there is no tok_ts_agg_prices.json file yet
    # TODO: we could create one by calling get_quote() with dex=None and seeing what Totle's price is
    with open(f'{filename_base}_tok_ts_dex_prices.json', 'w') as outfile:
        json.dump(tok_ts_dex_prices, outfile, indent=3)

DATA_DIR='order_splitting_data'

########################################################################################################################
# main

if len(sys.argv) < 2:
    print(f"usage: {sys.argv[0]} totle|aggs")
    exit(0)

tokens_to_try = sorted(set(TOTLE_ONEINCH_DEXAG_TOKENS + TOTLE_UNPRICED_TOKENS_TO_TRY))

if sys.argv[1] == 'totle':
    # get_totle_data(tokens=['BAT', 'DAI'], trade_sizes=[0.2])
    get_totle_data(tokens=tokens_to_try)
elif sys.argv[1] == 'aggs':
    # get_agg_data(dexag_client, oneinch_client, paraswap_client, tokens=['BAT', 'DAI'], trade_sizes=[0.2])
    get_agg_data(dexag_client, oneinch_client, paraswap_client, tokens=tokens_to_try)
else:
    print(f"Unrecognized data set '{sys.argv[1]}'")
