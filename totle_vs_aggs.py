import glob
import operator
import os
import functools
from collections import defaultdict
import concurrent.futures

import csv
import json

import data_import
import dexag_client
import exchange_utils
import oneinch_client
import paraswap_client
import totle_client
from v2_compare_prices import get_savings, print_savings, get_filename_base, SavingsCSV
from summarize_csvs import aggregated_savings, print_savings_summary_table_csv, print_neg_savings_stats, print_savings_summary_table, compute_mean, sorted_trade_sizes

AGG_CLIENTS = [dexag_client, oneinch_client, paraswap_client]
CSV_FIELDS = "time action trade_size token quote exchange exchange_price totle_used totle_price totle_splits pct_savings splits ex_prices".split()

def compare_totle_and_aggs(from_token, to_token, from_amount, usd_trade_size=None):
    agg_savings = {}

    totle_sd = totle_client.try_swap(totle_client.name(), from_token, to_token, params={'fromAmount': from_amount}, verbose=False, debug=False)
    if totle_sd:
        for agg_client in AGG_CLIENTS:
            pq = agg_client.get_quote(from_token, to_token, from_amount=from_amount)
            agg_name = agg_client.name()
            if pq:
                splits = exchange_utils.canonical_keys(pq['exchanges_parts'])
                ex_prices = pq.get('exchanges_prices') and exchange_utils.canonical_and_splittable(pq['exchanges_prices'])
                if pq['price'] == 0:
                    print(f"DIVISION BY ZERO: {agg_name} buying {to_token} with {from_amount} {from_token} returned a price of {pq['price']}")
                    continue
                savings = get_savings(agg_name, pq['price'], totle_sd, to_token, usd_trade_size or from_amount, 'buy', splits=splits, ex_prices=ex_prices, print_savings=False)
                savings['quote'] = from_token # TODO: add this to get_savings
                print(f"Totle saved {savings['pct_savings']:.2f} percent vs {agg_name} buying {to_token} with {from_amount} {from_token} on {savings['totle_used']}")
                agg_savings[agg_name] = savings
            else:
                print(f"{agg_name} had no price quote for buying {to_token} with {from_amount} {from_token}")
    return agg_savings

def compare_totle_and_aggs_parallel(from_token, to_token, from_amount, usd_trade_size=None):
    agg_savings = {}

    totle_sd = totle_client.try_swap(totle_client.name(), from_token, to_token, params={'fromAmount': from_amount}, verbose=False, debug=False)
    if totle_sd:
        futures_agg = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for agg_client in AGG_CLIENTS:
                future = executor.submit(agg_client.get_quote, from_token, to_token, from_amount=from_amount)
                futures_agg[future] = agg_client.name()

        for f in concurrent.futures.as_completed(futures_agg):
            agg_name = futures_agg[f]
            pq = f.result()
            if pq:
                splits = exchange_utils.canonical_keys(pq['exchanges_parts'])
                ex_prices = pq.get('exchanges_prices') and exchange_utils.canonical_and_splittable(pq['exchanges_prices'])
                if pq['price'] == 0:
                    print(f"DIVISION BY ZERO: {agg_name} buying {to_token} with {from_amount} {from_token} returned a price of {pq['price']}")
                    continue
                savings = get_savings(agg_name, pq['price'], totle_sd, to_token, usd_trade_size or from_amount, 'buy', splits=splits, ex_prices=ex_prices, print_savings=False)
                savings['quote'] = from_token # TODO: add this to get_savings
                print(f"Totle saved {savings['pct_savings']:.2f} percent vs {agg_name} buying {to_token} with {from_amount} {from_token} on {savings['totle_used']}")
                agg_savings[agg_name] = savings
            else:
                print(f"{agg_name} had no price quote for buying {to_token} with {from_amount} {from_token}")
    return agg_savings

def get_token_prices(tokens):
    cmc_data = json.load(open(f'data/cmc_tokens.json'))['data']
    usd_prices = {t['symbol']: float(t['quote']['USD']['price']) for t in cmc_data if t['symbol'] in tokens}

    skipped_tokens, missing_tokens = set(), set(tokens) - set(usd_prices)
    print(f"CMC had prices for {len(usd_prices)}/{len(tokens)} tokens. Querying Totle for prices on the remaining {len(missing_tokens)} tokens")
    for missing_token in missing_tokens:
        if missing_token == 'CETH':
            usd_prices[missing_token] = 2.83
        else:
            totle_sd = totle_client.try_swap(totle_client.name(), 'USDC', missing_token, params={'toAmount': 0.1}, verbose=False, debug=False)

            if totle_sd:  # set the from_amount so it's roughly the same across all swaps
                usd_prices[missing_token] = totle_sd['price']
            else:
                # If we can't get a price from CMC or Totle, then just discard this token. Other aggs may have the pair, but if you can't
                # buy it for ETH on Totle, then it is essentially not a "tradable" token as curated by Totle, and thus not in this study.
                skipped_tokens.add(missing_token)

    if any(skipped_tokens):
        raise ValueError(f"Skipping {skipped_tokens} because we couldn't get a price from CMC or Totle")
    return usd_prices


OVERLAP_PAIRS = [('REN', 'MANA'), ('ENJ', 'BNT'), ('ENJ', 'DAI'), ('ENJ', 'REN'), ('USDT', 'DAI'), ('USDC', 'OMG'), ('REP', 'DAI'), ('RDN', 'DAI'), ('PAX', 'REN'), ('PAX', 'DAI'), ('MKR', 'PAX'), ('POWR', 'MKR'), ('ANT', 'BNT'),
                 ('RCN', 'ENJ'), ('RLC', 'DAI'), ('POWR', 'REN'), ('POWR', 'DAI'), ('RDN', 'OMG'), ('USDC', 'PAX'), ('BAT', 'ZRX'), ('MKR', 'REN'), ('GNO', 'OMG'), ('LINK', 'PAX'), ('KNC', 'REN'), ('KNC', 'DAI'), ('OMG', 'REP'),
                 ('ZRX', 'PAX'), ('ENJ', 'TUSD'), ('USDT', 'OMG'), ('ENJ', 'LINK'), ('USDC', 'GNO'), ('REN', 'ANT'), ('USDT', 'LINK'), ('RCN', 'TUSD'), ('RCN', 'LINK'), ('RDN', 'PAX'), ('REP', 'REN'), ('CVC', 'RDN'), ('TUSD', 'ANT'),
                 ('POWR', 'ENJ'), ('RDN', 'MKR'), ('ZRX', 'LINK'), ('SNT', 'ANT'), ('TUSD', 'REP'), ('ZRX', 'ENJ'), ('CVC', 'ANT'), ('KNC', 'TUSD'), ('POLY', 'DAI'), ('USDT', 'PAX'), ('REP', 'TUSD'), ('USDT', 'ZRX'), ('TUSD', 'GNO'),
                 ('OMG', 'LINK'), ('GNO', 'DAI'), ('BAT', 'ANT'), ('GNO', 'REN'), ('MKR', 'DAI'), ('RCN', 'GNO'), ('RDN', 'REN'), ('RCN', 'KNC'), ('CVC', 'OMG'), ('ANT', 'REP'), ('BNT', 'PAX'), ('LINK', 'ZRX'), ('USDT', 'RDN'),
                 ('USDT', 'REP'), ('USDC', 'REN'), ('ZRX', 'DAI'), ('ENJ', 'SNT'), ('POWR', 'RDN'), ('USDT', 'SNT'), ('CVC', 'REP'), ('KNC', 'BNT'), ('OMG', 'ENJ'), ('BAT', 'SNT'), ('ZRX', 'BNT'), ('GNO', 'LINK'), ('POWR', 'GNO'),
                 ('USDC', 'ZRX'), ('ZRX', 'GNO'), ('ANT', 'OMG'), ('ANT', 'TUSD'), ('RLC', 'REN'), ('POWR', 'ANT'), ('PAX', 'GNO'), ('REP', 'ENJ'), ('MKR', 'ANT'), ('OMG', 'TUSD'), ('WBTC', 'REN'), ('WBTC', 'DAI'), ('RDN', 'ZRX'),
                 ('ZRX', 'REN'), ('MKR', 'RDN'), ('ENJ', 'MANA'), ('REN', 'DAI'), ('OMG', 'RDN'), ('CVC', 'GNO'), ('POLY', 'RDN'), ('POWR', 'ZRX'), ('OMG', 'ANT'), ('SNT', 'BNT'), ('TUSD', 'PAX'), ('RCN', 'ANT'), ('CVC', 'BNT'),
                 ('CVC', 'SNT'), ('SNT', 'RCN'), ('LINK', 'RDN'), ('GNO', 'SNT'), ('CVC', 'ZRX'), ('GNO', 'BNT'), ('USDC', 'RDN'), ('MANA', 'ANT'), ('MKR', 'OMG'), ('RDN', 'SNT'), ('POWR', 'OMG'), ('KNC', 'RCN'), ('RDN', 'ANT'),
                 ('TKN', 'RDN'), ('CVC', 'MKR'), ('PAX', 'OMG'), ('TKN', 'TUSD'), ('BAT', 'RCN'), ('USDC', 'SNT'), ('USDC', 'WBTC'), ('POWR', 'TKN'), ('ENJ', 'RCN'), ('GNO', 'RDN'), ('MANA', 'OMG'), ('BNT', 'TUSD'), ('RLC', 'RCN'),
                 ('USDC', 'ANT'), ('MANA', 'RCN'), ('MKR', 'KNC'), ('ZRX', 'KNC'), ('BAT', 'OMG'), ('PAX', 'RCN'), ('POWR', 'KNC'), ('REP', 'RCN'), ('RLC', 'ENJ'), ('ANT', 'ZRX'), ('GNO', 'TUSD'), ('LINK', 'BNT'), ('GNO', 'POLY'),
                 ('LINK', 'SNT'), ('PAX', 'SNT'), ('RLC', 'KNC'), ('LINK', 'REP'), ('TUSD', 'OMG'), ('RCN', 'DAI'), ('PAX', 'KNC'), ('ZRX', 'MANA'), ('BAT', 'PAX'), ('LINK', 'BAT'), ('OMG', 'SNT'), ('MANA', 'DAI'), ('MKR', 'TUSD'),
                 ('MKR', 'BNT'), ('MKR', 'SNT'), ('GNO', 'ENJ'), ('BNT', 'DAI'), ('BAT', 'MANA'), ('USDC', 'KNC'), ('PAX', 'RDN'), ('USDT', 'ENJ'), ('ENJ', 'GNO'), ('USDC', 'TUSD'), ('USDT', 'MANA'), ('BAT', 'RDN'), ('TUSD', 'RCN'),
                 ('BAT', 'REP'), ('RCN', 'BNT'), ('RCN', 'REN'), ('USDT', 'BNT'), ('RDN', 'KNC'), ('POWR', 'WBTC'), ('OMG', 'ZRX'), ('BAT', 'BNT'), ('PAX', 'REP'), ('GNO', 'KNC'), ('REN', 'RDN'), ('TKN', 'DAI'), ('KNC', 'RDN'),
                 ('TKN', 'REN'), ('MANA', 'BNT'), ('MANA', 'LINK'), ('CVC', 'KNC'), ('PAX', 'ANT'), ('ANT', 'RCN'), ('ZRX', 'RDN'), ('REN', 'BNT'), ('REP', 'SNT'), ('GNO', 'MKR'), ('REP', 'BNT'), ('ZRX', 'RCN'), ('ANT', 'RDN'),
                 ('MKR', 'ZRX'), ('MANA', 'GNO'), ('LINK', 'RCN'), ('SNT', 'RDN'), ('REN', 'RCN'), ('KNC', 'GNO'), ('REN', 'GNO'), ('OMG', 'PAX'), ('RLC', 'BNT'), ('REP', 'GNO'), ('MKR', 'BAT'), ('REP', 'KNC'), ('GNO', 'ZRX'),
                 ('LINK', 'MKR'), ('OMG', 'RCN'), ('KNC', 'ANT'), ('REN', 'PAX'), ('RLC', 'MANA'), ('MKR', 'RCN'), ('ZRX', 'ANT'), ('SNT', 'TUSD'), ('TKN', 'PAX'), ('LINK', 'REN'), ('LINK', 'DAI'), ('REP', 'MANA'), ('SNT', 'OMG'),
                 ('TUSD', 'DAI'), ('TUSD', 'REN'), ('OMG', 'MANA'), ('POWR', 'TUSD'), ('REP', 'OMG'), ('SNT', 'REN'), ('ZRX', 'TUSD'), ('GNO', 'PAX'), ('LINK', 'OMG'), ('OMG', 'REN'), ('OMG', 'DAI'), ('USDT', 'REN'), ('ZRX', 'OMG'),
                 ('ANT', 'GNO'), ('MKR', 'LINK'), ('BAT', 'KNC'), ('USDC', 'MANA'), ('ENJ', 'ANT'), ('USDC', 'BAT'), ('BAT', 'REN'), ('LINK', 'MANA'), ('PAX', 'TUSD'), ('USDT', 'KNC'), ('OMG', 'KNC'), ('ENJ', 'KNC'), ('BNT', 'REN'),
                 ('USDC', 'REP'), ('REP', 'RDN'), ('ANT', 'DAI'), ('POWR', 'RCN'), ('CVC', 'PAX'), ('RLC', 'SNT'), ('ANT', 'KNC'), ('LINK', 'KNC'), ('MANA', 'RDN'), ('RLC', 'RDN'), ('GNO', 'REP'), ('MKR', 'ENJ'), ('POWR', 'BNT'),
                 ('GNO', 'RCN'), ('POWR', 'SNT'), ('ENJ', 'RDN'), ('RLC', 'GNO'), ('RCN', 'RDN'), ('ZRX', 'SNT'), ('MANA', 'SNT'), ('ZRX', 'REP'), ('KNC', 'SNT'), ('PAX', 'BNT'), ('SNT', 'MKR'), ('BAT', 'TUSD'), ('RDN', 'BNT'),
                 ('REP', 'ANT'), ('OMG', 'GNO'), ('MANA', 'MKR'), ('LINK', 'TUSD'), ('BAT', 'GNO'), ('USDC', 'RCN'), ('RLC', 'ZRX'), ('ANT', 'ENJ'), ('RLC', 'ANT'), ('CVC', 'DAI'), ('KNC', 'MANA'), ('OMG', 'BNT'), ('ANT', 'LINK'),
                 ('ENJ', 'PAX'), ('MKR', 'MANA'), ('LINK', 'GNO'), ('USDC', 'BNT'), ('REP', 'LINK'), ('RCN', 'PAX'), ('CVC', 'RCN'), ('POWR', 'PAX'), ('GNO', 'ANT'), ('BAT', 'DAI'), ('USDT', 'BAT'), ('ANT', 'PAX'), ('KNC', 'PAX'),
                 ('MKR', 'REP'), ('LINK', 'ANT'), ('RLC', 'OMG'), ('USDT', 'TUSD'), ('POWR', 'LINK'), ('ANT', 'REN'), ('MKR', 'GNO'), ('USDC', 'DAI'), ('KNC', 'LINK'), ('SNT', 'DAI')]

# OVERLAP_PAIRS = [('USDC', 'REQ'), ('REP', 'SNT')]
USD_TRADE_SIZES = [1.0, 5.0, 10.0, 50.0, 100.0, 500.0, 1000.0]
# USD_TRADE_SIZES = [1.0, 5.0, 10.0]

def do_overlap_pairs():
    all_buy_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(dict))) # extra lambda prevents KeyError in print_savings
    order_type = 'buy'

    overlap_tokens = set()
    for p in OVERLAP_PAIRS: overlap_tokens |= set(p)
    usd_prices = get_token_prices(overlap_tokens)

    filename = get_filename_base(prefix='totle_vs_agg_overlap_pairs', suffix=order_type)
    with SavingsCSV(filename, fieldnames=CSV_FIELDS) as csv_writer:
        todo = []

        for to_token, from_token in OVERLAP_PAIRS: # these were recorded as (base,quote) i.e. (to_token, from_token)
        # for from_token, to_token in OVERLAP_PAIRS: # try the pairs in reverse
            for usd_trade_size in USD_TRADE_SIZES:
                # set the from_amount so it's roughly the same ($10 USD) across all swaps
                from_amount = usd_trade_size / usd_prices[from_token]
                todo.append((compare_totle_and_aggs_parallel, from_token, to_token, from_amount, usd_trade_size))

        MAX_THREADS = 12
        print(f"Queueing up {len(todo)} todos for execution on {MAX_THREADS} workers")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures_p = {executor.submit(*p): p for p in todo}

            for f in concurrent.futures.as_completed(futures_p):
                _, from_token, to_token, from_amount, usd_trade_size = futures_p[f]
                print(f"\n\nBuying {to_token} for {from_amount} {from_token} usd_trade_size=${usd_trade_size:.2f} (which is {from_amount:.4f} {from_token} at a price of ${usd_prices[from_token]:.2f})")
                agg_savings = f.result()
                for agg_name, savings in agg_savings.items():
                    all_buy_savings[agg_name][from_token][usd_trade_size] = savings
                    csv_writer.append(savings)

    # print(json.dumps(all_buy_savings, indent=3))

    # Prints a savings dict, token => trade_size => savings values
    for agg_name in all_buy_savings:
        print_savings(order_type, all_buy_savings[agg_name], USD_TRADE_SIZES, title=f"Savings vs. {agg_name}")


TOTLE_39 = ['ANT','AST','BAT','BNT','CDT','CND','CVC','DAI','ENG','ENJ','ETHOS','GNO','KNC','LINK','MANA','MCO','MKR','OMG','PAX','PAY','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','STORJ','TKN','TUSD','USDC','USDT','WBTC','ZRX']
HI_SPLIT_TOKENS = ['BAT', 'ENJ', 'GNO', 'KNC', 'MANA', 'OMG', 'POE', 'POWR', 'RCN', 'RDN', 'REN', 'REP', 'REQ', 'RLC', 'SNT']
TOTLE_74 = ['DNT','CZRX','ONG','CSAI','CUSDC','BNTY','XDCE','QSP','ANT','MKR','ASTRO','BNT','FLIXX','OMG','DATA','REP','WLK','USDS','REAL','STORM','STORJ','MLN','MTL','DRT','DALC','ZRX','TKN','TRST','PRG','SHP','DRGN','VIB','ABYSS','PAX','LEV','RHOC','ENJ','SCL','WBTC','POLY','LRC','ZIL','RCN','ERC20','USDC','ISAI','KNC','NEXO','STX','REN','ELEC','SUSD','WABI','CBAT','CETH','NPXS','VERI','BAT','TUSD','ENG','RPL','ART','PAY','CND','WINGS','REQ','MCO','CDAI','LINK','KIN','PLR','BNB','DAI','SWT']


STABLECOINS = ['DAI', 'PAX', 'SAI', 'TUSD', 'USDC', 'USDT']
UNSUPPORTED_STABLECOINS = ['CSAI', 'IDAI']
# TOKENS = HI_SPLIT_TOKENS
TOKENS = [t for t in TOTLE_39 if t != 'SNX']
TRADE_SIZES  = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0, 500.0]
# TRADE_SIZES = [1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0, 500.0]

def do_eth_pairs():
    all_buy_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(dict))) # extra lambda prevents KeyError in print_savings
    order_type, quote = 'buy', 'ETH'
    filename = get_filename_base(prefix='totle_vs_agg_eth_pairs', suffix=order_type)
    with SavingsCSV(filename, fieldnames=CSV_FIELDS) as csv_writer:
        todo = []

        for base in TOKENS:
            for trade_size in TRADE_SIZES:
                todo.append((compare_totle_and_aggs_parallel, quote, base, trade_size))

        MAX_THREADS = 16
        print(f"Queueing up {len(todo)} todos ({len(TOKENS)} tokens x {len(TRADE_SIZES)} trade sizes) for execution on {MAX_THREADS} workers")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures_p = {executor.submit(*p): p for p in todo}

            for f in concurrent.futures.as_completed(futures_p):
                _, quote, base, trade_size = futures_p[f]
                agg_savings = f.result()
                for agg_name, savings in agg_savings.items():
                    all_buy_savings[agg_name][base][trade_size] = savings
                    csv_writer.append(savings)

    # print(json.dumps(all_buy_savings, indent=3))

    # Prints a savings dict, token => trade_size => savings values
    for agg_name in all_buy_savings:
        print_savings(order_type, all_buy_savings[agg_name], TRADE_SIZES, title=f"Savings vs. {agg_name}")

########################################################################################################################
def main():
    working_dir = os.path.dirname(__file__)
    if working_dir: os.chdir(working_dir)

    # do_summary_erc20(glob.glob(f'outputs/totle_vs_agg_overlap_*'))
    # do_summary_erc20(glob.glob(f'outputs/totle_vs_agg_overlap_pairs_*'))
    # do_summary_erc20(glob.glob(f'outputs/totle_vs_agg_overlap_reversed_pairs_*'))
    # exit(0)


    # do_summary(glob.glob(f'outputs/totle_vs_agg_eth_pairs_2020*'))
    # exit(0)

    # do_overlap_pairs()
    do_eth_pairs()

if __name__ == "__main__":
    main()
