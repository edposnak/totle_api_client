import json
from collections import defaultdict
from datetime import datetime
import v2_client
import dexag_client
import oneinch_client
import paraswap_client

import exchange_utils


QUOTE = 'ETH'

TOKENS = ['ABT','ABYSS','ANT','APPC','AST','BAT','BLZ','BNT','BTU','CBI','CDAI','CDT','CETH','CND','CUSDC','CVC','CWBTC','CZRX','DAI','DAT','DENT','DGX','DTA','ELF','ENG','ENJ','EQUAD','ETHOS','FUN','GEN','GNO','IDAI','IUSDC','KNC','LBA','LEND','LINK','LRC','MANA','MCO','MKR','MLN','MOC','MTL','MYB','NEXO','NPXS','OMG','OST','PAX','PAY','PLR','POE','POLY','POWR','QKC','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','SPANK','SPN','STORJ','TAU','TKN','TUSD','UPP','USDC','USDT','VERI','WBTC','WETH','XCHF','XDCE','ZRX']
NO_TRADE_TOKENS = ['BMC', 'PPP', 'PPT', 'WTC', 'CBAT', 'CREP', 'SETH', 'IUSDC', 'IETH', 'IWBTC', 'ILINK', 'IZRX', 'IREP', 'IKNC']

TRADE_SIZES = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0]



def get_order_splitting_data(*clients, tokens=TOKENS, trade_sizes=TRADE_SIZES, quote=QUOTE):
    d = datetime.today()
    filename_base = f"../order_splitting_data/{d.year}-{d.month:02d}-{d.day:02d}_{d.hour:02d}:{d.minute:02d}:{d.second:02d}"
    print(f"sending output to {filename_base}*")
    # get list of tokens on dexag and 1-inch that are tradable/splittable
    tok_ts_dexs_with_pair = defaultdict(dict)
    tok_ts_dexs_used = defaultdict(dict)
    tok_ts_prices = defaultdict(dict)
    # TODO: sells and compare with buys


    for base in tokens:
        for trade_size in trade_sizes:
            print(f"Doing {base} at {trade_size} {quote} ...")
            dexs_with_pair, dexs_used, dex_prices = set(), {}, {}
            for client in clients:
                pq = client.get_quote(quote, base, from_amount=trade_size, dex='all')
                if not pq:
                    print(f"{client.name()} did not quote {quote} to {base} at trade size={trade_size}")
                else:
                    splits = exchange_utils.canonical_keys(pq['exchanges_parts'])
                    dexs_used[client.name()] = splits
                    dexs_with_pair |= splits.keys()
                    dex_prices[client.name()] = pq['price']

            tok_ts_dexs_with_pair[base][trade_size] = list(dexs_with_pair)
            tok_ts_dexs_used[base][trade_size] = dexs_used
            tok_ts_prices[base][trade_size] = dex_prices
    with open(f'{filename_base}_tok_ts_dexs_with_pair.json', 'w') as outfile:
        json.dump(tok_ts_dexs_with_pair, outfile, indent=3)
    with open(f'{filename_base}_tok_ts_dexs_used.json', 'w') as outfile:
        json.dump(tok_ts_dexs_used, outfile, indent=3)
    with open(f'{filename_base}_tok_ts_prices.json', 'w') as outfile:
        json.dump(tok_ts_prices, outfile, indent=3)


# get_order_splitting_data(dexag_client, oneinch_client, paraswap_client, tokens=['BAT', 'DAI', 'SPANK'], trade_sizes=[0.2, 2.0])
get_order_splitting_data(dexag_client, oneinch_client, paraswap_client)
