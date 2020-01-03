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
import v2_client
from v2_compare_prices import get_savings, print_savings, get_filename_base, SavingsCSV
from summarize_csvs import aggregated_savings, print_savings_summary_table_csv, print_neg_savings_stats, print_savings_summary_table, compute_mean, sorted_trade_sizes

AGG_CLIENTS = [dexag_client, oneinch_client, paraswap_client]
CSV_FIELDS = "time action trade_size token quote exchange exchange_price totle_used totle_price pct_savings splits ex_prices".split()

def compare_totle_and_aggs(from_token, to_token, from_amount, usd_trade_size=None):
    agg_savings = {}

    totle_sd = v2_client.try_swap(v2_client.name(), from_token, to_token, params={'fromAmount': from_amount}, verbose=False, debug=False)
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

    totle_sd = v2_client.try_swap(v2_client.name(), from_token, to_token, params={'fromAmount': from_amount}, verbose=False, debug=False)
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
            totle_sd = v2_client.try_swap(v2_client.name(), 'USDC', missing_token, params={'toAmount': 0.1}, verbose=False, debug=False)

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
STABLECOINS = ['DAI', 'PAX', 'SAI', 'TUSD', 'USDC', 'USDT']
UNSUPPORTED_STABLECOINS = ['CSAI', 'IDAI']
TOKENS = HI_SPLIT_TOKENS
TRADE_SIZES  = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0, 500.0]
# TOKENS, TRADE_SIZES = ['CVC', 'DAI', 'LINK'], [0.5, 5.0]
def do_eth_pairs():
    all_buy_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(dict))) # extra lambda prevents KeyError in print_savings
    order_type, quote = 'buy', 'ETH'
    filename = get_filename_base(prefix='totle_vs_agg_eth_pairs', suffix=order_type)
    with SavingsCSV(filename, fieldnames=CSV_FIELDS) as csv_writer:
        for base in TOKENS:
            for trade_size in TRADE_SIZES:
                print(f"Doing {base} for {trade_size} {quote}")
                # set the from_amount so it's roughly the same ($10 USD) across all swaps
                print(f"\n\nBuying {base} for {trade_size} {quote}")
                agg_savings = compare_totle_and_aggs_parallel(quote, base, trade_size) # TODO, parallelize here and remove the _parallel version
                for agg_name, savings in agg_savings.items():
                    all_buy_savings[agg_name][quote][trade_size] = savings
                    csv_writer.append(savings)

    # print(json.dumps(all_buy_savings, indent=3))

    # Prints a savings dict, token => trade_size => savings values
    for agg_name in all_buy_savings:
        print_savings(order_type, all_buy_savings[agg_name], USD_TRADE_SIZES, title=f"Savings vs. {agg_name}")

########################################################################################################################
# CSV processing

def check_overlap(per_pair_savings):
    # TODO: Why are there so many pairs not supported by all 3
    all_pairs, remove_pairs, bad_pairs = set(), set(), set()
    for pair, ts_agg_savings in per_pair_savings.items():
        all_pairs.add(pair)
        for ts, agg_savings in ts_agg_savings.items():
            if not (len(agg_savings) == 3):
                remove_pairs.add(pair)
                # print(f"{pair} trade_size={ts} only has data for {list(agg_savings.keys())}")
            if not (len(agg_savings) < 2):
                    bad_pairs.add(pair)
    print(f"{len(remove_pairs)}/{len(all_pairs)} pairs were not supported by all aggregators")
    print(f"{len(bad_pairs)}/{len(all_pairs)} pairs were supported by < 2 aggregators")
    full_overlap_pair_savings = { pair: sav for pair, sav in per_pair_savings.items() if pair not in remove_pairs }
    print(f"{len(full_overlap_pair_savings)} pairs fully overlap")

def print_neg_savings_table(per_token_savings, trade_sizes):
    neg_savings, pos_savings = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    for token, trade_size, agg, pct_savings in data_import.pct_savings_gen(per_token_savings):
        for pct in pct_savings:
            if pct > 0.0:
                pos_savings[agg][trade_size] += 1
            else:
                neg_savings[agg][trade_size] += 1

    aggs = sorted(list(set(neg_savings.keys()) | set(pos_savings.keys())))

    neg_samples, pos_samples = 0, 0
    for agg in aggs:
        neg_samples += sum(neg_savings[agg].values())
        pos_samples += sum(pos_savings[agg].values())


    total_samples = neg_samples + pos_samples
    neg_pct = 100.0 * neg_samples / total_samples

    print(f"\n\nOut of {total_samples} data points, Totle's fees exceeded the price savings {neg_samples} times, resulting in negative price savings {neg_pct:.1f}% of the time.")

    csv_header = f"Trade Size,{','.join(aggs)}"
    print(csv_header)
    for trade_size in trade_sizes:
        csv_row = f"{trade_size}"
        for agg in aggs:
            if agg in neg_savings and trade_size in neg_savings[agg]:
                neg_sav = neg_savings[agg][trade_size]
                pos_sav = pos_savings[agg][trade_size]
                pct_neg_savings = 100 * neg_sav / (neg_sav + pos_sav)
                csv_row += f",{pct_neg_savings}"
            else:
                csv_row += ","
        print(csv_row)


def print_split_counts_table(split_count_by_agg, non_split_count_by_agg, agg_names, trade_sizes):
    print(f"\n\nSplit percentages by agg and trade size")
    csv_header = f"Trade Size,{','.join(agg_names)}"
    print(csv_header)
    for trade_size in trade_sizes:
        csv_row = f"{trade_size}"
        for agg in agg_names:
            splits = split_count_by_agg[agg][trade_size]
            non_splits = non_split_count_by_agg[agg][trade_size]
            csv_row += f",{100 * splits / (splits + non_splits)}"
        print(csv_row)

def print_savings_summary_by_pair_csv(per_pair_savings, only_trade_size, agg_names, min_stablecoins=0, label="Average Savings"):
    print(f"\n{label}")

    pair_agg_savings = defaultdict(lambda: defaultdict(list))
    print(f"\nPair,{','.join(agg_names)}")

    for pair, trade_size, agg, pct_savings_list in data_import.pct_savings_gen(per_pair_savings):
        if trade_size != only_trade_size: continue
        if min_stablecoins == 1 and not has_stablecoin(pair): continue
        if min_stablecoins == 2 and not both_stablecoins(pair): continue

        pair_agg_savings[pair][agg] += pct_savings_list

    for pair in sorted(pair_agg_savings):
        row = f"{pair[0]}/{pair[1]}"
        agg_savings = pair_agg_savings[pair]
        for agg in agg_names:
            if agg in agg_savings:
                row += f",{compute_mean(agg_savings[agg]) :.2f}"
            else:
                row += f","
        print(row)


def print_avg_savings_per_pair_by_agg(per_pair_savings, only_trade_size=None, print_threshold=0, samples=False, min_stablecoins=0):
    for_trade_size = f"for Trade Size = {only_trade_size}" if only_trade_size else ''

    pair_agg_savings = defaultdict(lambda: defaultdict(list))

    for pair, trade_size, agg, pct_savings in data_import.pct_savings_gen(per_pair_savings):
        if only_trade_size and trade_size != only_trade_size: continue
        if min_stablecoins == 1 and not has_stablecoin(pair): continue
        if min_stablecoins == 2 and not both_stablecoins(pair): continue

        pair_agg_savings[pair][agg] += pct_savings

    print(f"\n\nAverage Savings {for_trade_size} (min_stablecoins={min_stablecoins})")

    print(f"\nToken\tMean Pct. Savings")
    for pair, agg_savings in sorted(pair_agg_savings.items()):
        print(f"{pair}\t{compute_mean(sum(agg_savings.values(), [])):.2f}")

        for agg, savings in agg_savings.items():
            avg_savings = compute_mean(savings)
            if avg_savings < -print_threshold or avg_savings > print_threshold:
                print(f"    {agg}:\t{avg_savings}")
                if samples: print(f"    {agg}:\t{savings}")



def print_top_ten_pairs_savings(per_pair_savings, only_trade_size=None):
    for_trade_size = f"for Trade Size = {only_trade_size}" if only_trade_size else ''

    pair_savings = defaultdict(list)
    for pair, trade_size, exchange, pct_savings in data_import.pct_savings_gen(per_pair_savings):
        if only_trade_size and trade_size != only_trade_size: continue
        pair_savings[pair] += pct_savings

    avg_savings_pairs = {}
    for pair, savings_list in pair_savings.items():
        avg_savings_pairs[compute_mean(savings_list)] = pair
    sorted_avg_savings_pairs = sorted(avg_savings_pairs.items())

    print(f"\nTop 10 Negative Price Savings {for_trade_size}")
    for pct_savings, pair in sorted_avg_savings_pairs[0:10]: print(f"{pair[0]}/{pair[1]}\t{pct_savings:.2f}%")
    print(f"\nTop 10 Positive Price Savings {for_trade_size}")
    for pct_savings, pair in reversed(sorted_avg_savings_pairs[-10:-1]): print(f"{pair[0]}/{pair[1]}\t{pct_savings:.2f}%")


def print_top_ten_savings_by_token(per_pair_savings, only_trade_size=None):
    for_trade_size = f"for Trade Size = {only_trade_size}" if only_trade_size else ''

    token_savings = defaultdict(list)
    for pair, trade_size, exchange, pct_savings in data_import.pct_savings_gen(per_pair_savings):
        if only_trade_size and trade_size != only_trade_size: continue
        token_savings[pair[0]] += pct_savings
        token_savings[pair[1]] += pct_savings

    avg_savings_tokens = {}
    for token, savings_list in token_savings.items():
        avg_savings_tokens[compute_mean(savings_list)] = token
    sorted_avg_savings_tokens = sorted(avg_savings_tokens.items())

    print(f"\nTop 10 Negative Price Savings {for_trade_size}")
    for pct_savings, token in sorted_avg_savings_tokens[0:10]: print(f"{token}\t{pct_savings:.2f}%")
    print(f"\nTop 10 Positive Price Savings {for_trade_size}")
    for pct_savings, token in reversed(sorted_avg_savings_tokens[-10:-1]): print(f"{token}\t{pct_savings:.2f}%")

def print_avg_savings_per_pair_by_trade_size(per_pair_savings, only_trade_sizes):
    pairs_trade_size_savings = defaultdict(lambda: defaultdict(list))
    for pair, trade_size, agg, pct_savings in data_import.pct_savings_gen(per_pair_savings):
        pairs_trade_size_savings[pair][trade_size] += pct_savings

    trade_size_strs = map(lambda ts: f"{ts:8.1f}", only_trade_sizes)
    print(f"Pair            {''.join(trade_size_strs)}")
    for pair, trade_size_savings in pairs_trade_size_savings.items():
        row = f"{str(pair):<16}"
        for ts in only_trade_sizes:
            row += f"{compute_mean(trade_size_savings[ts]):8.2f}" if ts in trade_size_savings else "      "
        print(row)

def print_largest_absolute_savings_samples(per_pair_savings):
    for pair, trade_size, agg, pct_savings_list in data_import.pct_savings_gen(per_pair_savings):
        mean_savings = compute_mean(pct_savings_list)
        if abs(mean_savings) > 50:
            print(f"{pair} ${trade_size} vs {agg} mean_savings={mean_savings}%")


def print_stablecoin_pairs(pair_savings, only_trade_sizes):
    pairs_trade_size_savings = defaultdict(lambda: defaultdict(list))
    for pair, trade_size, agg, pct_savings_list in data_import.pct_savings_gen(pair_savings):
        if both_stablecoins(pair):
            pairs_trade_size_savings[pair][trade_size] += pct_savings_list
            mean_savings = compute_mean(pct_savings_list)
            # print(f"{pair} ${trade_size} vs {agg} mean_savings={mean_savings}%")

    trade_size_strs = map(lambda ts: f"{ts:8.1f}", only_trade_sizes)
    print(f"\nPair            {''.join(trade_size_strs)}")
    for pair, trade_size_savings in sorted(pairs_trade_size_savings.items()):
        row = f"{str(pair):<16}"
        for ts in only_trade_sizes:
            row += f"{compute_mean(trade_size_savings[ts]):8.2f}" if ts in trade_size_savings else "      "
        print(row)


def print_stablecoin_pcts(pair_savings):
    """counts what percent of  savings were due to stablecoin/stablecoin pairs"""
    ss_count, all_count = 0, 0
    for pair, trade_size, agg, pct_savings_list in data_import.pct_savings_gen(pair_savings):
        all_count += len(pct_savings_list)
        if has_stablecoin(pair):
            ss_count += len(pct_savings_list)

    # print(f"\n{ss_count}/{all_count} ({100*ss_count/all_count}%) outliers were stablecoin/stablecoin pairs")
    print(f"\n{ss_count}/{all_count} ({100*ss_count/all_count}%) involved a stablecoin")


def has_stablecoin(pair):
    return pair[0] in STABLECOINS or pair[1] in STABLECOINS

def both_stablecoins(pair):
    return pair[0] in STABLECOINS and pair[1] in STABLECOINS

def print_stablecoin_stablecoin_price_table(stablecoin_stablecoin_prices, agg_names, trade_sizes):
    print(f"\nStablecoin/Stablecoin Prices")

    print(f"\nTrade Size,{','.join(agg_names)}")
    for trade_size in trade_sizes:
        agg_prices = stablecoin_stablecoin_prices[trade_size]
        row = f"{trade_size}"
        for agg in agg_names:
            if agg in agg_prices:
                row += f",{compute_mean(agg_prices[agg]) :.2f}"
            else:
                row += f","
        print(row)



def do_summary(csv_files):
    """Returns a dict containing pct savings token: { trade_size:  {exchange: [sample, sample, ...], ...}"""
    per_pair_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    inlier_pair_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    outlier_pair_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    ss_split_count_by_agg, ss_non_split_count_by_agg = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))

    stablecoin_stablecoin_prices = defaultdict(lambda: defaultdict(list))

    for filename in csv_files:
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=None)
            for row in reader:
                from_token, to_token = row['quote'], row['token']
                pair = (from_token, to_token)
                trade_size, pct_savings = float(row['trade_size']), float(row['pct_savings'])
                agg = row['exchange']
                agg_price = float(row['exchange_price'])
                totle_used = row['totle_used']
                splits = exchange_utils.canonical_keys(eval(row.get('splits') or '{}'))

                if both_stablecoins(pair):
                    if agg_price > 4: continue # remove (most) outliers PAX on Uniswap
                    if 'PAX' in pair and 'Uniswap' in splits:
                        continue
                        # print(f"PAX/UNI: {agg} split {pair} at ${trade_size} between {splits} for price {agg_price} and savings of {pct_savings}% totle_used={totle_used}")

                    # if trade_size == 1.0 and agg == '1-Inch' and agg_price < 0.6:
                    #     if 'PMM' not in splits or splits['PMM'] != 10:
                    #         print(f"1-Inch: {agg} split {pair} at ${trade_size} between {splits} for price {agg_price} and savings of {pct_savings}% totle_used={totle_used}")


                    stablecoin_stablecoin_prices[trade_size][agg].append(agg_price)

                    if len(splits) < 2:
                        ss_non_split_count_by_agg[agg][trade_size] += 1
                    else:
                        ss_split_count_by_agg[agg][trade_size] += 1

                per_pair_savings[pair][trade_size][agg].append(pct_savings)
                if abs(pct_savings) > 10:
                    outlier_pair_savings[pair][trade_size][agg].append(pct_savings)
                else:
                    inlier_pair_savings[pair][trade_size][agg].append(pct_savings)

    # print(f"\ninlier_pair_savings had {len(inlier_pair_savings)} pairs")
    # print(f"outlier_pair_savings had {len(outlier_pair_savings)} pairs")

    agg_names = sorted([a.name() for a in AGG_CLIENTS])
    trade_sizes = sorted_trade_sizes(*inlier_pair_savings.values())

    print_stablecoin_pairs(per_pair_savings, trade_sizes)
    # print_stablecoin_pcts(inlier_pair_savings)
    # print_stablecoin_pcts(outlier_pair_savings)

    # print_neg_savings_table(inlier_pair_savings, trade_sizes)
    # if outlier_pair_savings: print_neg_savings_table(outlier_pair_savings, trade_sizes)

    print_savings_summary_table_csv(aggregated_savings(per_pair_savings, filter=both_stablecoins), agg_names, label="Stablecoin/Stablecoin Savings (all samples)")
    print_savings_summary_table_csv(aggregated_savings(inlier_pair_savings, filter=both_stablecoins), agg_names, label="Stablecoin/Stablecoin Savings (inlier samples)")
    print_savings_summary_table_csv(aggregated_savings(outlier_pair_savings, filter=both_stablecoins), agg_names, label="Stablecoin/Stablecoin Savings (outlier samples)")

    print_stablecoin_stablecoin_price_table(stablecoin_stablecoin_prices, agg_names, trade_sizes)

    print_avg_savings_per_pair_by_agg(per_pair_savings, 10.0, print_threshold=0, samples=True, min_stablecoins=2)

    # print_savings_summary_by_pair_csv(per_pair_savings, 10.0, agg_names, min_stablecoins=2, label="Average stablecoin/stablecoin Savings at trade size 10.0")
    # print_savings_summary_by_pair_csv(per_pair_savings, 100.0, agg_names, min_stablecoins=2, label="Average stablecoin/stablecoin Savings at trade size 100.0")
    # print_savings_summary_by_pair_csv(per_pair_savings, 1000.0, agg_names, min_stablecoins=2, label="Average stablecoin/stablecoin Savings at trade size 1000.0")

    # print_split_counts_table(ss_split_count_by_agg, ss_non_split_count_by_agg, agg_names, trade_sizes)

    # print(f"\n\n-----\n\n")
    # print_largest_absolute_savings_samples(inlier_pair_savings)
    # print_largest_absolute_savings_samples(outlier_pair_savings)

    # if outlier_pair_savings:
    #     print_top_ten_pairs_savings(outlier_pair_savings)
    #     print_top_ten_savings_by_token(outlier_pair_savings)
    #
    #     print("\n\n")
    #
    #     for trade_size in trade_sizes:
    #         print_top_ten_pairs_savings(outlier_pair_savings, trade_size)
    #         print_top_ten_savings_by_token(outlier_pair_savings, trade_size)


    # for trade_size in trade_sizes:
    #     print_avg_savings_per_pair_by_agg(outlier_pair_savings, trade_size, print_threshold=10, samples=False)
    #
    # check_overlap(inlier_pair_savings)

    # per_trade_size_savings = aggregated_savings(inlier_pair_savings)
    # print_savings_summary_table(per_trade_size_savings, agg_names)
    # print_savings_summary_table_csv(per_trade_size_savings, agg_names, label="Inlier Pair Average Savings")
    #

    # for trade_size in USD_TRADE_SIZES[0:-1]:
    #     print_avg_savings_per_pair_by_agg(per_pair_savings, trade_size, filtered=True, samples=True)

    # print_top_ten_pairs_savings(inlier_pair_savings)
    print_top_ten_pairs_savings(per_pair_savings)

    # print_avg_savings_per_pair_by_trade_size(per_pair_savings, trade_sizes)

    exit(0)



########################################################################################################################
def main():
    working_dir = os.path.dirname(__file__)
    if working_dir: os.chdir(working_dir)

    do_summary(glob.glob(f'outputs/totle_vs_agg_overlap_*'))
    # do_summary(glob.glob(f'outputs/totle_vs_agg_overlap_pairs_*'))
    # do_summary(glob.glob(f'outputs/totle_vs_agg_overlap_reversed_pairs_*'))
    exit(0)


    do_overlap_pairs()
    # do_eth_pairs()

if __name__ == "__main__":
    main()
