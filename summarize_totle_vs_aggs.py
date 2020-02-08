import glob
from collections import defaultdict

import csv

import data_import
import dexag_client
import exchange_utils
import oneinch_client
import paraswap_client

from summarize_csvs import aggregated_savings, print_savings_summary_table_csv, print_neg_savings_stats, \
    print_savings_summary_table, compute_mean, sorted_trade_sizes, do_splits_vs_non_splits

from v2_compare_prices import canonicalize_totle_splits, is_multi_split

CSV_FIELDS = "time action trade_size token quote exchange exchange_price totle_used totle_price pct_savings splits ex_prices".split()

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

def do_neg_savings(per_token_savings, trade_sizes):
    neg_savings, pos_savings = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    neg_savings_without_fee = defaultdict(lambda: defaultdict(int))
    for token, trade_size, agg, pct_savings in data_import.pct_savings_gen(per_token_savings):
        for pct in pct_savings:
            if pct > 0.0:
                pos_savings[agg][trade_size] += 1
            else:
                neg_savings[agg][trade_size] += 1
                if pct < -0.25:
                    neg_savings_without_fee[agg][trade_size] += 1

    neg_samples, pos_samples, neg_without_fee_samples = 0, 0, 0
    aggs = sorted(list(set(neg_savings.keys()) | set(pos_savings.keys())))
    for agg in aggs:
        neg_samples_agg = sum(neg_savings[agg].values())
        neg_samples += neg_samples_agg
        neg_without_fee_samples_agg = sum(neg_savings_without_fee[agg].values())
        neg_without_fee_samples += neg_without_fee_samples_agg
        pos_samples_agg = sum(pos_savings[agg].values())
        pos_samples += pos_samples_agg

        total_samples_agg = neg_samples_agg + pos_samples_agg
        neg_pct_agg = 100.0 * neg_samples_agg / total_samples_agg
        neg_pct_without_fee_agg = 100.0 * neg_without_fee_samples_agg / total_samples_agg
        print(f"\nOut of {total_samples_agg} comparisons, Totle's price (without fees) was worse than {agg}'s {neg_without_fee_samples_agg} times, resulting in worse price {neg_pct_without_fee_agg:.1f}% of the time.")
        # print(f"Out of {total_samples_agg} comparisons, Totle's fees exceeded the price savings {neg_samples_agg} times, resulting in negative price savings {neg_pct_agg:.1f}% of the time.")


    total_samples = neg_samples + pos_samples
    neg_pct = 100.0 * neg_samples / total_samples
    neg_pct_without_fee = 100.0 * neg_without_fee_samples / total_samples

    print(f"\n\nOut of {total_samples} comparisons, Totle's price (without fees) was worse than competitor's {neg_without_fee_samples} times, resulting in worse price {neg_pct_without_fee:.1f}% of the time.")
    print(f"Out of {total_samples} comparisons, Totle's fees exceeded the price savings {neg_samples} times, resulting in negative price savings {neg_pct:.1f}% of the time.")

    print_neg_savings_csv(pos_savings, neg_savings, aggs, trade_sizes, label="Negative Price Savings Pct. vs Competitors")
    print_neg_savings_csv(pos_savings, neg_savings_without_fee, aggs, trade_sizes, label="Worse price (without fees) vs Competitors")


def print_neg_savings_csv(pos_savings, neg_savings, aggs, trade_sizes, label="Negative Price Savings"):
    print(f"\n{label}")
    csv_header = f"\nTrade Size,{','.join(aggs)}"
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

def print_savings_summary_by_pair_csv(per_pair_savings, only_trade_size, agg_names, only_token=None, min_stablecoins=0, label="Average Savings"):
    print(f"\n{label}")

    pair_agg_savings = defaultdict(lambda: defaultdict(list))
    print(f"\nPair,{','.join(agg_names)}")

    for pair, trade_size, agg, pct_savings_list in data_import.pct_savings_gen(per_pair_savings):
        if trade_size != only_trade_size: continue
        # if only_token and only_token not in pair: continue
        # if only_token and pair[0] != only_token: continue
        if only_token and pair[1] != only_token: continue
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
            if abs(avg_savings)  > print_threshold:
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

STABLECOINS = ['DAI', 'PAX', 'SAI', 'TUSD', 'USDC', 'USDT']
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

def print_large_neg_savings(large_neg_savings, min_samples=10):
    for k, s in sorted(large_neg_savings.items()):
        if s[0] > min_samples: print_sample(k, s,  print_num_times=True)

def print_sample(tok_ts_agg, prices_splits, print_num_times=False):
    to_token, trade_size, agg = tok_ts_agg
    n_samples, totle_price, totle_splits, agg_price, agg_splits = prices_splits

    price_diff = 100.0 * totle_price / agg_price - 100
    add_data = f"({n_samples} times)" if print_num_times else ''
    print(f"{to_token} for {trade_size} ETH vs {agg} (Totle's price is {price_diff:.2f}% higher) {add_data}")
    totle, agg = 'Totle:', f"{agg}:"
    print(f"\t{totle:<10}  {totle_price:.6f}    {totle_splits}")
    print(f"\t{agg:<10}  {agg_price:.6f}    {agg_splits}")


def do_summary_erc20(csv_files):
    """Returns a dict containing pct savings token: { trade_size:  {exchange: [sample, sample, ...], ...}"""
    per_pair_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    inlier_pair_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    outlier_pair_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    ss_split_count_by_agg, ss_non_split_count_by_agg = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    stablecoin_stablecoin_prices = defaultdict(lambda: defaultdict(list))

    agg_names = set()

    for filename in csv_files:
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=None)
            for row in reader:
                from_token, to_token = row['quote'], row['token']
                pair = (from_token, to_token)
                trade_size, pct_savings = float(row['trade_size']), float(row['pct_savings'])
                agg = row['exchange']
                agg_price = float(row['exchange_price'])
                splits = exchange_utils.canonical_keys(eval(row.get('splits') or '{}'))

                agg_names.add(agg)

                # if 'PAX' in pair and 'Uniswap' in splits:
                #     # print(f"PAX/UNI: {agg} split {pair} at ${trade_size} between {splits} for price {agg_price} and savings of {pct_savings}% totle_used={totle_used}")
                #     continue

                if both_stablecoins(pair):
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

    agg_names = sorted(agg_names)
    trade_sizes = sorted_trade_sizes(*inlier_pair_savings.values())

    # print_neg_savings_table(inlier_pair_savings, trade_sizes)
    # if outlier_pair_savings: print_neg_savings_table(outlier_pair_savings, trade_sizes)

    # per_trade_size_savings = aggregated_savings(per_pair_savings)
    # print_savings_summary_table_csv(per_trade_size_savings, agg_names, label="Average Savings (all samples)")


    # Stablecoin savings
    # print_stablecoin_pairs(per_pair_savings, trade_sizes)
    # print_stablecoin_pcts(per_pair_savings)
    # print_stablecoin_pcts(inlier_pair_savings)
    # print_stablecoin_pcts(outlier_pair_savings)
    # print_savings_summary_table_csv(aggregated_savings(per_pair_savings, filter=both_stablecoins), agg_names, label="Stablecoin/Stablecoin Savings (all samples)")
    # print_savings_summary_table_csv(aggregated_savings(inlier_pair_savings, filter=both_stablecoins), agg_names, label="Stablecoin/Stablecoin Savings (inlier samples)")
    # print_savings_summary_table_csv(aggregated_savings(outlier_pair_savings, filter=both_stablecoins), agg_names, label="Stablecoin/Stablecoin Savings (outlier samples)")
    # print_stablecoin_stablecoin_price_table(stablecoin_stablecoin_prices, agg_names, trade_sizes)

    # print_avg_savings_per_pair_by_agg(per_pair_savings, 10.0, print_threshold=0, samples=True, min_stablecoins=2)
    # for trade_size in USD_TRADE_SIZES[0:-1]:
    #     print_avg_savings_per_pair_by_agg(per_pair_savings, trade_size, filtered=True, samples=True)

    print_top_ten_pairs_savings(per_pair_savings)
    print_top_ten_savings_by_token(per_pair_savings)
    print("\n\n---\n\n")

    for trade_size in trade_sizes:
        # print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='ENJ', label=f"Average Savings at trade size {trade_size}")
        # print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='POWR', label=f"Average Savings at trade size {trade_size}")
        # print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='ANT', label=f"Average Savings at trade size {trade_size}")
        # print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='RCN', label=f"Average Savings at trade size {trade_size}")
        # print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='TUSD', label=f"Average Savings at trade size {trade_size}")
        print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='USDT', label=f"Average Savings at trade size {trade_size}")
        print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='CVC', label=f"Average Savings at trade size {trade_size}")


def do_totle_splits_vs_non_splits(csv_files, aggs):
    per_token_splits_only_savings, _ = data_import.parse_csv_files(csv_files, only_totle_splits=True)
    per_token_non_splits_only_savings, _ = data_import.parse_csv_files(csv_files, only_totle_non_splits=True)

    per_trade_size_splits_only = aggregated_savings(per_token_splits_only_savings)
    per_trade_size_non_splits = aggregated_savings(per_token_non_splits_only_savings)

    print_savings_summary_table_csv(per_trade_size_non_splits, aggs, label="All tokens savings by trade size (only Totle non-splits)")
    print_savings_summary_table_csv(per_trade_size_splits_only, aggs, label="All tokens savings by trade size (only Totle splits)")

def do_both_splitting(per_token_both_splitting_savings, aggs):
    # print average savings summary table
    per_trade_size_splits_only = aggregated_savings(per_token_both_splitting_savings)

    # print splits vs non-splits summary CSV
    print_savings_summary_table_csv(per_trade_size_splits_only, aggs, label="All tokens savings by trade size (both Totle and agg splitting)")


def print_avg_savings_by_token(per_token_savings, only_trade_size=None, only_aggs=None):
    token_savings = defaultdict(lambda: defaultdict(list))
    for token, trade_size, agg, pct_savings in data_import.pct_savings_gen(per_token_savings):
        if only_trade_size and trade_size != only_trade_size: continue
        token_savings[token][agg] += pct_savings

    print(f"\nAverage Savings by Token for Trade Size={only_trade_size}")
    print(f"\nToken,{','.join(only_aggs)}")

    for token, savings in sorted(token_savings.items()):
        row = f"{token}"
        for agg in only_aggs:
            if agg in savings:
                row += f",{compute_mean(savings[agg]) :.2f}"
            else:
                row += f","
        print(row)

def do_summary_eth_pairs(csv_files):
    """Returns a dict containing pct savings token: { trade_size:  {exchange: [sample, sample, ...], ...}"""
    per_pair_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    split_count_by_agg, non_split_count_by_agg = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    all_samples, totle_split_samples = defaultdict(int), defaultdict(int)
    agg_names = set()
    large_neg_savings = {}
    select_samples = defaultdict(list)

    print(f"Processing {len(csv_files)} CSV files")

    for filename in csv_files:
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=None)
            for row in reader:
                from_token, to_token = row['quote'], row['token']
                pair = (from_token, to_token)
                trade_size, pct_savings = float(row['trade_size']), float(row['pct_savings'])
                agg = row['exchange']
                agg_price = float(row['exchange_price'])
                totle_price = float(row['totle_price'])

                agg_names.add(agg)
                all_samples[trade_size] += 1

                totle_splits = canonicalize_totle_splits(eval(row['totle_splits'])) if 'totle_splits' in row else {}
                if len(totle_splits) > 1: totle_split_samples[trade_size] += 1

                agg_splits = exchange_utils.canonical_keys(eval(row.get('splits') or '{}'))
                if len(agg_splits) > 1: split_count_by_agg[agg][trade_size] += 1
                else: non_split_count_by_agg[agg][trade_size] += 1

                # if agg == 'DEX.AG' and trade_size == 10.0 and totle_price / agg_price > 1.008:
                # if is_multi_split(totle_splits) and totle_price / agg_price > 3:
                if totle_price / agg_price > 1.1: # 10% worse
                    key = (to_token, trade_size, agg)
                    select_samples[key].append((0, totle_price, totle_splits, agg_price, agg_splits))

                if pct_savings < -10:
                    key = (to_token, trade_size, agg)
                    print(f"Totle price is {totle_price} agg_price is {agg_price} -> {totle_price / agg_price}% GREATER")

                    if key in large_neg_savings:
                        n_samples, old_totle_price, old_totle_splits, old_agg_price, old_agg_splits = large_neg_savings[key]
                        if totle_price / agg_price > old_totle_price / old_agg_price:
                            large_neg_savings[key] = (n_samples + 1, totle_price, totle_splits, agg_price, agg_splits)
                        else:
                            large_neg_savings[key] = (n_samples + 1, old_totle_price, old_totle_splits, old_agg_price, old_agg_splits)
                    else:
                        large_neg_savings[key] = (1, totle_price, totle_splits, agg_price, agg_splits)


                # print(f"{to_token}/{from_token} trade_size={trade_size} {from_token} \n\ttotle_splits={totle_splits} \n\tagg_splits={splits} savings={pct_savings}")

                per_pair_savings[pair][trade_size][agg].append(pct_savings)

    agg_names = sorted(agg_names)
    trade_sizes = sorted_trade_sizes(*per_pair_savings.values())

    do_neg_savings(per_pair_savings, trade_sizes)


    #
    # print("\n\nPercent Totle Splits by Trade Size")
    # for trade_size in trade_sizes:
    #     print(f"{trade_size}:\t{100 * totle_split_samples[trade_size]/all_samples[trade_size]:.2f}")
    #
    print_large_neg_savings(large_neg_savings)

    print(f"\nGot {len(select_samples)} select samples")
    for tok_ts_agg, prices_splits_list in select_samples.items():
        print(f"\n\n{tok_ts_agg}")
        for prices_splits in prices_splits_list:
            print_sample(tok_ts_agg, prices_splits)

    exit(0)


    print_savings_summary_table_csv(aggregated_savings(per_pair_savings), agg_names, label="Average Savings (all samples)")
    print_avg_savings_by_token(per_pair_savings, only_trade_size=10.0, only_aggs=agg_names)


    # do_splits_vs_non_splits(tuple(csv_files), agg_names)

    # Does Totle win more when it splits

    # do_totle_splits_vs_non_splits(tuple(csv_files), agg_names)
    # per_token_both_splitting_savings, _ = data_import.parse_csv_files(tuple(csv_files), only_splits=True, only_totle_splits=True)
    # do_neg_savings(per_token_both_splitting_savings, trade_sizes)
    #
    # do_both_splitting(per_token_both_splitting_savings, agg_names)
    # do_neg_savings(per_token_both_splitting_savings, trade_sizes)
    # print_avg_savings_by_token(per_token_both_splitting_savings, only_trade_size=10.0, only_aggs=agg_names)
    # print_avg_savings_by_token(per_token_both_splitting_savings, only_trade_size=100.0, only_aggs=agg_names)


    exit(0)


    print_avg_savings_per_pair_by_agg(per_pair_savings, 10.0, print_threshold=4, samples=True, min_stablecoins=0)
    # for trade_size in trade_sizes:
    #     print_avg_savings_per_pair_by_agg(per_pair_savings, trade_size, samples=True)
    for trade_size in trade_sizes:
        print_avg_savings_per_pair_by_agg(per_pair_savings, trade_size, print_threshold=10, samples=False)

    exit(0)



    print("\n\n---\n\n")
    # TODO add totle to agg_names
    # print_split_counts_table(split_count_by_agg, non_split_count_by_agg, agg_names, trade_sizes)



    print_savings_summary_table(per_trade_size_savings, agg_names)
    print_savings_summary_table_csv(per_trade_size_savings, agg_names, label="Per Pair Average Savings")


    # print_avg_savings_per_pair_by_trade_size(per_pair_savings, trade_sizes)



########################################################################################################################
def main():
    # do_summary_erc20(glob.glob(f'outputs/totle_vs_agg_overlap_*'))
    # do_summary_erc20(glob.glob(f'outputs/totle_vs_agg_overlap_pairs_*'))
    # do_summary_erc20(glob.glob(f'outputs/totle_vs_agg_overlap_reversed_pairs_*'))

    # do_summary_eth_pairs(glob.glob(f'outputs/totle_vs_agg_eth_pairs_2020-01-[01]*'))
    do_summary_eth_pairs(glob.glob(f'outputs/totle_vs_agg_eth_pairs_2020-01-3*'))

if __name__ == "__main__":
    main()
