import sys
import json
from collections import defaultdict
from datetime import datetime

import dexag_client
import oneinch_client

DEX_AG = dexag_client.name()
ONE_INCH = oneinch_client.name()

def get_split_pairs(tok_ts_dexs_used, verbose=True):
    """Returns dicts of token: trade_sizes for dex.ag and 1-inch"""
    ag_split_pairs, oi_split_pairs  = defaultdict(list), defaultdict(list)
    for token, ts_dexs_used in tok_ts_dexs_used.items():
        for trade_size, dexs_used in ts_dexs_used.items():
            ag_used = dexs_used.get(DEX_AG)
            if ag_used and len(ag_used) > 1:
                ag_split_pairs[token].append(trade_size)
                if verbose: print(f"{token} {trade_size} {DEX_AG} {ag_used}")

            oi_used = dexs_used.get(ONE_INCH)
            if oi_used and len(oi_used) > 1:
                oi_split_pairs[token].append(trade_size)
                if verbose: print(f"{token} {trade_size} {ONE_INCH} {oi_used}")
    return ag_split_pairs, oi_split_pairs


########################################################################################################################
#
filename = sys.argv[1] if len(sys.argv) > 1 else 'order_splitting_data/2019-10-26_16:45:02_tok_ts'
p = filename.partition('tok_ts') # strip off anything after tok_ts
filename = p[0]+p[1]

tok_ts_dexs_with_pair = json.load(open(f'{filename}_dexs_with_pair.json'))
tokens = list(tok_ts_dexs_with_pair.keys())

print(f"\n\nTokens and DEXs that have some liquidity")
for token, ts_dexs in tok_ts_dexs_with_pair.items():
    print(f"{token}: {sorted(list(set(sum(ts_dexs.values(), []))))}")
    
tok_ts_dexs_used = json.load(open(f'{filename}_dexs_used.json'))
ag_split_pairs, oi_split_pairs = get_split_pairs(tok_ts_dexs_used, verbose=False)
print(f"\n\nActual {DEX_AG} splits of token at various trade sizes")
for token, trade_sizes in ag_split_pairs.items(): print(f"{token}: {trade_sizes}")
print(f"\n\nActual {ONE_INCH} splits of token at various trade sizes")
for token, trade_sizes in oi_split_pairs.items(): print(f"{token}: {trade_sizes}")
for t in tokens:
    if t not in ag_split_pairs: print(f"{t} was never split by {DEX_AG}")
    if t not in oi_split_pairs: print(f"{t} was never split by {ONE_INCH}")

tok_ts_prices = json.load(open(f'{filename}_prices.json'))
print("\n\n")
for token, aggs in tok_ts_prices.items():
    if not any(aggs.values()): print(f"{token} had no prices for all trade sizes")


