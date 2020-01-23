import json
import sys
from collections import defaultdict
from datetime import datetime
import totle_client
import dexag_client
import oneinch_client
import paraswap_client

import exchange_utils

TOTLE_EX = totle_client.name()

QUOTE = 'ETH'
TRADE_SIZES = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0]
TOKENS = ['BAT','DAI','REP']
COMPOUND_TOKENS = ['CBAT','CDAI','CETH','CREP','CUSDC','CWBTC','CZRX']
TOTLE_EXCHANGES = integrated_exchanges = list(totle_client.exchanges().keys())


def get_totle_data(tokens=TOKENS, trade_sizes=TRADE_SIZES, quote=QUOTE, exchanges=TOTLE_EXCHANGES):
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

                pq = totle_client.get_quote(quote, base, from_amount=trade_size, dex=dex)
                if not pq:
                    print(f"{can_dex} did not have {quote} to {base} at trade size={trade_size}")
                else:
                    splits_by_agg[TOTLE_EX][can_dex] = -1  # -1 indicates this is not a split, just a list of dexs that could be used
                    dexs_with_pair.add(can_dex)
                    dex_prices[can_dex] = pq['price']

            tok_ts_dexs_with_pair[base][trade_size] = list(dexs_with_pair)
            tok_ts_splits_by_agg[base][trade_size] = splits_by_agg
            tok_ts_dex_prices[base][trade_size] = dex_prices

    print(json.dumps(tok_ts_dexs_with_pair, indent=3))

########################################################################################################################
# main
get_totle_data(tokens=COMPOUND_TOKENS, trade_sizes=[0.2, 2.0], exchanges=['Compound'])
