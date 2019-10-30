import json
import sys
from collections import defaultdict
from datetime import datetime
import v2_client
import dexag_client
import oneinch_client
import paraswap_client

import exchange_utils

TOTLE_EX = v2_client.name()

QUOTE = 'ETH'

# Tokens supported by Totle and most aggs
TOKENS = ['ABYSS','ANT','AST','BAT','BNT','CDAI','CDT','CETH','CND','CUSDC','CVC','CWBTC','CZRX','DAI','DENT','ENG','ENJ','ETHOS','FUN','GNO','KNC','LEND','LINK','LRC','MANA','MCO','MKR','MLN','MTL','NEXO','NPXS','OMG','PAX','PAY','PLR','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','SPANK','STORJ','TAU','TKN','TUSD','USDC','USDT','VERI','WBTC','XDCE','ZRX']

# Tokens not supported by any aggs, including Totle
UNSUPPORTED_TOKENS = ['CBAT','CREP','IETH','IKNC','ILINK','IREP','IUSDC','IWBTC','IZRX','PPP','PPT','SETH','WTC']

# These are tokens supported by one or more aggs, but not Totle
MORE_AGG_TOKENS = ['ABT','APPC','BLZ','BTU','CBI','DAT','DGX','DTA','ELF','EQUAD','GEN','IDAI','LBA','MOC','MYB','OST','QKC','SPN','UPP','WETH','XCHF']

# These are tokens supported by Totle but no aggs
MORE_TOTLE_TOKENS = ['BMC']

TRADE_SIZES = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0]

# don't bother recording price info for these DEXs; they are never going to be used in splits
EXCLUDE_DEXS = ['ag', 'IDEX', 'DDEX', 'Ethfinex', 'Paradex']

def get_agg_data(*clients, tokens=TOKENS, trade_sizes=TRADE_SIZES, quote=QUOTE):
    filename_base = get_filename_base()

    # get list of tokens on dexag and 1-inch that are tradable/splittable
    tok_ts_dexs_with_pair = defaultdict(dict)
    tok_ts_splits_by_agg = defaultdict(dict)
    tok_ts_agg_prices = defaultdict(dict)
    tok_ts_dex_prices = defaultdict(dict)

    # TODO: sells and compare with buys
    for base in tokens:
        for trade_size in trade_sizes:
            print(f"Doing {base} at {trade_size} {quote} ...")
            dexs_with_pair, splits_by_agg, agg_prices, dex_prices = set(), {}, {}, {}
            for client in clients:
                pq = client.get_quote(quote, base, from_amount=trade_size, dex='all')
                agg_name = client.name()
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

def get_totle_data(tokens=TOKENS, trade_sizes=TRADE_SIZES, quote=QUOTE):
    filename_base = get_filename_base(prefix='totle_')

    # get list of tokens on dexag and 1-inch that are tradable/splittable
    integrated_exchanges = list(v2_client.exchanges().keys())
    tok_ts_dexs_with_pair = defaultdict(dict)
    tok_ts_splits_by_agg = defaultdict(dict)
    tok_ts_dex_prices = defaultdict(dict)

    # TODO: sells and compare with buys
    for base in tokens:
        for trade_size in trade_sizes:
            print(f"Doing {base} at {trade_size} {quote} ...")
            dexs_with_pair, splits_by_agg, dex_prices = set(), {}, {}
            splits_by_agg[TOTLE_EX] = {} # there will just be this one entry, which will list individual DEXs that returned prices

            for dex in integrated_exchanges:
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

def get_filename_base(prefix=''):
    d = datetime.today()
    fb = f"{DATA_DIR}/{prefix}{d.year}-{d.month:02d}-{d.day:02d}_{d.hour:02d}:{d.minute:02d}:{d.second:02d}"
    print(f"output will go to {fb}*.json")
    return fb

########################################################################################################################
# main

if len(sys.argv) < 2:
    print(f"usage: {sys.argv[0]} totle|aggs")
    exit(0)

if sys.argv[1] == 'totle':
    get_totle_data(tokens=['BAT', 'DAI'], trade_sizes=[0.2])
    get_totle_data(tokens=sorted(set(TOKENS + MORE_TOTLE_TOKENS)))
elif sys.argv[1] == 'aggs':
    # get_agg_data(dexag_client, oneinch_client, paraswap_client, tokens=['BAT', 'DAI'], trade_sizes=[0.2])
    get_agg_data(dexag_client, oneinch_client, paraswap_client, tokens=sorted(set(TOKENS + MORE_AGG_TOKENS)))
else:
    print(f"Unrecognized data set '{sys.argv[1]}'")
