from datetime import datetime
import glob
from collections import defaultdict

import csv

import data_import
import snapshot_utils

from summarize_csvs import aggregated_savings, print_savings_summary_table_csv, print_neg_savings_stats, \
    print_savings_summary_table, compute_mean, sorted_trade_sizes, do_splits_vs_non_splits

from split_utils import is_multi_split, canonicalize_and_sort_splits

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

BEST_WORSE_THRESHOLD = 0.0001

def better_worse_same_counts(pct_savings_list):
    better_count, worse_count, same_count = 0, 0, 0
    for pct in pct_savings_list:
        if pct > BEST_WORSE_THRESHOLD:
            better_count += 1
        elif pct < -BEST_WORSE_THRESHOLD:
            worse_count += 1
        else:
            same_count += 1

    return better_count, worse_count, same_count

def better_worse_same_pcts(pct_savings_list):
    better_count, worse_count, same_count = better_worse_same_counts(pct_savings_list)
    total_count = better_count + worse_count + same_count
    return round(100 * better_count / total_count), round(100 * worse_count / total_count), round(100 * same_count / total_count)

def do_better_worse_same_price(per_pair_savings, label, agg_breakdown=False):
    print(f"\n{label}")
    better_price, worse_price, same_price = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))

    for token, trade_size, agg, pct_savings in data_import.pct_savings_gen(per_pair_savings):
        better_count, worse_count, same_count = better_worse_same_counts(pct_savings)
        better_price[agg][trade_size] += better_count
        worse_price[agg][trade_size] += worse_count
        same_price[agg][trade_size] += same_count

    better_price_samples, worse_price_samples, same_price_samples = 0, 0, 0
    better_pct, worse_pct, same_pct = {}, {}, {}
    aggs = sorted(list(set(better_price.keys()) | set(worse_price.keys()) | set(worse_price.keys())))
    for agg in aggs:
        better_price_samples_agg = sum(better_price[agg].values())
        better_price_samples += better_price_samples_agg
        worse_price_samples_agg = sum(worse_price[agg].values())
        worse_price_samples += worse_price_samples_agg
        same_price_samples_agg = sum(same_price[agg].values())
        same_price_samples += same_price_samples_agg

        total_samples_agg = better_price_samples_agg + worse_price_samples_agg + same_price_samples_agg

        better_pct[agg] = 100.0 * better_price_samples_agg / total_samples_agg
        worse_pct[agg] = 100.0 * worse_price_samples_agg / total_samples_agg
        same_pct[agg] = 100.0 * same_price_samples_agg / total_samples_agg

    if agg_breakdown:
        header = 'Totle price was         better           worse           same'
        print(f"\n{header}")
        for agg in aggs:
            print(f"{agg:<14} {better_pct[agg]:14.2f}% {worse_pct[agg]:14.2f}% {same_pct[agg]:14.2f}%" )

        # do csv
        *a, b, c, d = header.split()
        print(','.join([' '.join(a), b, c, d]))
        for agg in aggs:
            print(f"{agg},{better_pct[agg]:.2f}%,{worse_pct[agg]:.2f}%,{same_pct[agg]:.2f}%" )


    total_samples = better_price_samples + worse_price_samples + same_price_samples
    better_pct = 100.0 * better_price_samples / total_samples
    worse_pct = 100.0 * worse_price_samples / total_samples
    same_pct = 100.0 * same_price_samples / total_samples

    print("\n")
    print(f"Out of {total_samples} comparisons, Totle's price was better than competitor's {better_pct:.1f}% of the time, worse {worse_pct:.1f}% of the time, and the same {same_pct:.1f}% of the time.")

    # print_neg_savings_csv(pos_savings, neg_savings, aggs, trade_sizes, label="Negative Price Savings Pct. vs Competitors")
    return total_samples


def do_better_worse_same_by_trade_size(per_pair_savings, label):
    print(f"\n{label}")
    better_price, worse_price, same_price, total_samples = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
    trade_sizes = set()
    total_samples

    for pair, trade_size, agg, pct_savings in data_import.pct_savings_gen(per_pair_savings):
        trade_sizes.add(trade_size)
        better_count, worse_count, same_count = better_worse_same_counts(pct_savings)
        better_price[trade_size] += better_count
        worse_price[trade_size] += worse_count
        same_price[trade_size] += same_count
        total_samples[trade_size] += better_count + worse_count + same_count

    better_pct, worse_pct, same_pct = {}, {}, {}
    for trade_size in trade_sizes:
        better_pct[trade_size] = 100.0 * better_price[trade_size] / total_samples[trade_size]
        worse_pct[trade_size] = 100.0 * worse_price[trade_size] / total_samples[trade_size]
        same_pct[trade_size] = 100.0 * same_price[trade_size] / total_samples[trade_size]


    header = 'Totle price was         better           worse           same'
    print(f"\n{header}")
    for trade_size in sorted(trade_sizes):
        print(f"{trade_size:<14} {better_pct[trade_size]:14.2f}% {worse_pct[trade_size]:14.2f}% {same_pct[trade_size]:14.2f}%" )

    # do CSV
    *a, b, c, d = header.split()
    print(','.join([' '.join(a), b, c, d]))
    for trade_size in sorted(trade_sizes):
        print(f"{trade_size},{better_pct[trade_size]:.2f}%,{worse_pct[trade_size]:.2f}%,{same_pct[trade_size]:.2f}%" )



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


def print_savings_summary_by_pair_csv(per_pair_savings, only_trade_size, agg_names, only_token=None, min_stablecoins=0, label="Average Savings by ETH pair"):
    print(f"\n{label} trade size = {only_trade_size}")

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
        print(f"{pair[1]}\t{compute_mean(sum(agg_savings.values(), [])):.2f}")

        for agg, savings in agg_savings.items():
            better_pct, worse_pct, same_pct = better_worse_same_pcts(savings)
            avg_savings = compute_mean(savings)
            if abs(avg_savings)  > print_threshold:
                print(f"    {agg:<8}\t{better_pct:>3}/{worse_pct:>3}/{same_pct:>3}\t{avg_savings:.2f}")
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
    printed_samples = 0
    for k, s in sorted(large_neg_savings.items()):
        if s[0] > min_samples:
            print_sample(k, s,  print_num_times=True)
            printed_samples += 1
    print(f"printed_samples={printed_samples}")

def print_sample(tok_ts_agg, prices_splits, print_num_times=False, print_snapshot=False):
    pair_or_token, trade_size, agg = tok_ts_agg

    to_token, from_token = ('ETH', pair_or_token) if type(pair_or_token) == str else pair_or_token

    id_or_n_samples, totle_price, totle_splits, agg_price, agg_splits = prices_splits
    totle_rate, agg_rate = 1 / totle_price, 1 / agg_price

    if totle_price / agg_price > 1.0001:
        price_description = f"{100.0 * totle_price / agg_price - 100:.2f}% higher than {agg}'s"
    elif agg_price / totle_price > 1.0001:
        price_description = f"{100.0 * agg_price / totle_price - 100:.2f}% lower than {agg}'s"
    else:
        price_description = f"the same as {agg}'s"


    if print_num_times:
        add_data = f"({id_or_n_samples} times)"
    else:
        timestamp = datetime.fromisoformat(timestamp_by_id[id_or_n_samples])
        # add_data = f"({timestamp})"
        add_data = f"({timestamp})\nid={id_or_n_samples}"

    if trade_size >= 1: trade_size = round(trade_size)

    print(f"\n{from_token}>{to_token} trade size={trade_size}  vs {agg} {add_data}")
    totle_c, agg_c = 'Totle:', f"{agg}:"
    print(f"\t{totle_c:<10}  {totle_price:.6f}    {totle_splits}")
    print(f"\t{agg_c:<10}  {agg_price:.6f}    {agg_splits}")
    print(f"Totle's price is {price_description}. Totle rate={totle_rate:.6g} {agg} rate={agg_rate:.6g}")

    if print_snapshot and not print_num_times:
        # pass
        # snapshot_utils.print_max_allocs(snapshot_utils.fetch_and_get_curve_info(id_or_n_samples), pct_inc=2)
        snapshot_utils.fetch_and_print_curve_info(id_or_n_samples)

def print_data_points(data_points, single_data_points, multi_data_points, timestamp_by_id):
    print(f"Total number of Totle price quotes that were compared to competitor price quotes={len(timestamp_by_id)}")
    print(f"Total number of comparisons={data_points}")
    print(f"   comparisons where Totle used a single segment split={single_data_points} ({round(100.0 * single_data_points / data_points)}%)")
    print(f"   comparisons where Totle used a multi-segment smart route={multi_data_points} ({round(100.0 * multi_data_points / data_points)}%)")



def parse_row(row):
    agg = row['exchange']
    id = row['id']
    time = row['time']
    from_token, to_token = row['quote'], row['token']
    trade_size, pct_savings = float(row['trade_size']), float(row['pct_savings'])
    totle_price = float(row['totle_price'])
    totle_splits = canonicalize_and_sort_splits(row.get('totle_splits'))

    agg_price = float(row['exchange_price'])
    agg_splits = canonicalize_and_sort_splits(row.get('splits'))
    return id, time, from_token, to_token, trade_size, totle_price, totle_splits, agg, agg_price, agg_splits, pct_savings


def do_summary_erc20_pairs(csv_files):
    """Returns a dict containing pct savings token: { trade_size:  {exchange: [sample, sample, ...], ...}"""
    print(f"Processing {len(csv_files)} CSV files")

    global timestamp_by_id

    per_pair_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    ss_split_count_by_agg, ss_non_split_count_by_agg = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    stablecoin_stablecoin_prices = defaultdict(lambda: defaultdict(list))

    split_count_by_agg, non_split_count_by_agg = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))

    select_samples = defaultdict(list)
    data_points, single_data_points, multi_data_points = 0, 0, 0
    data_points_by_agg = defaultdict(int)

    agg_names = set()

    for filename in csv_files:
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=None)
            for row in reader:
                id, time, from_token, to_token, trade_size, totle_price, totle_splits, agg, agg_price, agg_splits, pct_savings = parse_row(row)
                pair = (to_token, from_token)

                if pair[0] != to_token: raise ValueError(f"id={id} pair[0]=={pair[0]} but to_token={to_token}")
                from_token = pair[1]

                # Remove all WETH<>ETH pairs
                if to_token in ('WETH','ETH') and from_token in ('WETH','ETH'):
                    continue

                # Remove the 13 outliers where a bug caused > 1000% price diff
                if totle_price / agg_price > 1000:
                    continue

                agg_names.add(agg)
                timestamp_by_id[id] = time
                if len(agg_splits) > 1: split_count_by_agg[agg][trade_size] += 1
                else: non_split_count_by_agg[agg][trade_size] += 1
                data_points += 1
                data_points_by_agg[agg] += 1

                # ******************* Select Samples (saves all samples) **************************
                # if totle_splits == agg_splits and totle_price / agg_price > 1.05: # same split diff price indicates price data discrepancy
                # if totle_price / agg_price > 1.05 and totle_splits != agg_splits and trade_size == 100 and to_token == 'REP' and agg not in ['1-Inch', '1-Inch V2']:
                # if id == '0x49a6c1f9578d48f5bb855ebe0b59cb5cff0caec8f7474e2aa0720763b0f55fff':
                if from_token == 'UNI' and to_token == 'ETH' and totle_price / agg_price > 1.1:
                    key = (pair, trade_size, agg)
                    select_samples[key].append((id, totle_price, totle_splits, agg_price, agg_splits))


                # if both_stablecoins(pair):
                    # if trade_size == 1.0 and agg == '1-Inch' and agg_price < 0.6:
                    #     if 'PMM' not in agg_splits or agg_splits['PMM'] != 10:
                    #         print(f"1-Inch: {agg} split {pair} at ${trade_size} between {agg_splits} for price {agg_price} and savings of {pct_savings}% totle_used={totle_used}")
                    # stablecoin_stablecoin_prices[trade_size][agg].append(agg_price)
                    # if len(agg_splits) < 2:
                    #     ss_non_split_count_by_agg[agg][trade_size] += 1
                    # else:
                    #     ss_split_count_by_agg[agg][trade_size] += 1


                per_pair_savings[pair][trade_size][agg].append(pct_savings)
                if is_multi_split(totle_splits):
                    multi_data_points += 1
                else:
                    single_data_points += 1


    agg_names = sorted(agg_names)
    trade_sizes = sorted_trade_sizes(*per_pair_savings.values())

    print_data_points(data_points, single_data_points, multi_data_points, timestamp_by_id)
    for agg in agg_names: print(f"{agg}: {data_points_by_agg[agg]}")

    if True:
        print_savings_summary_table_csv(aggregated_savings(per_pair_savings), agg_names, label="Average Savings (all samples)")
        print_avg_savings_by_pair(per_pair_savings, only_aggs=agg_names)
        print_avg_savings_by_pair(per_pair_savings, only_trade_size=3000000.0, only_aggs=agg_names)
        print_avg_savings_by_pair(per_pair_savings, only_trade_size=4000000.0, only_aggs=agg_names)
        # print_avg_savings_by_pair(per_pair_savings, only_trade_size=1000.0, only_aggs=agg_names)
        # print_avg_savings_by_pair(per_pair_savings, only_trade_size=10000.0, only_aggs=agg_names)
        # print_avg_savings_by_pair(per_pair_savings, only_trade_size=100000.0, only_aggs=agg_names)
        # print_avg_savings_by_pair(per_pair_savings, only_trade_size=1000000.0, only_aggs=agg_names)


    # Stablecoin savings
    # print_stablecoin_pairs(per_pair_savings, trade_sizes)
    # print_stablecoin_pcts(per_pair_savings)
    # print_stablecoin_pcts(per_pair_savings)
    # print_stablecoin_pcts(outlier_pair_savings)
    # print_savings_summary_table_csv(aggregated_savings(per_pair_savings, filter=both_stablecoins), agg_names, label="Stablecoin/Stablecoin Savings (all samples)")
    # print_stablecoin_stablecoin_price_table(stablecoin_stablecoin_prices, agg_names, trade_sizes)

    # print_avg_savings_per_pair_by_agg(per_pair_savings, 10.0, print_threshold=0, samples=True, min_stablecoins=2)
    # for trade_size in USD_TRADE_SIZES[0:-1]:
    #     print_avg_savings_per_pair_by_agg(per_pair_savings, trade_size, filtered=True, samples=True)

    if False:
        print_top_ten_pairs_savings(per_pair_savings)
        print_top_ten_savings_by_token(per_pair_savings)
        print("\n\n---\n\n")

    if False:
        for trade_size in trade_sizes:
            # print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='ENJ', label=f"Average Savings at trade size {trade_size}")
            # print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='POWR', label=f"Average Savings at trade size {trade_size}")
            # print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='ANT', label=f"Average Savings at trade size {trade_size}")
            # print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='RCN', label=f"Average Savings at trade size {trade_size}")
            # print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='TUSD', label=f"Average Savings at trade size {trade_size}")
            print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='USDT', label=f"Average Savings at trade size {trade_size}")
            print_savings_summary_by_pair_csv(per_pair_savings, trade_size, agg_names, only_token='CVC', label=f"Average Savings at trade size {trade_size}")

    # **************** BETTER WORSE SAME / SAVINGS SUMMARY TABLE **********************
    if True:
        total_samples = do_better_worse_same_price(per_pair_savings, "All Samples by Competitor", agg_breakdown=True)
        do_better_worse_same_by_trade_size(per_pair_savings, "All Samples by Trade Size", )

    # **************** SELECT SAMPLES **********************
    if True:
        print(f"\n********************************************* SELECT SAMPLES *********************************************************\n")
        n_select_samples = sum([ len(v) for k,v in select_samples.items() ])
        print(f"\nGot total of {n_select_samples} select samples ({100 * n_select_samples / total_samples}%)")
        id_to_timestamp = lambda ps: datetime.fromisoformat(timestamp_by_id[ps[0]])

        # zero_alloc_count = 0
        for pair_ts_agg, prices_splits_list in sorted(select_samples.items()):
            # print(f"\n\n{pair_ts_agg}")
            for prices_splits in sorted(prices_splits_list, key=id_to_timestamp):
                print_sample(pair_ts_agg, prices_splits)
                # print_sample(pair_ts_agg, prices_splits, print_snapshot=True)


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


def print_avg_savings_by_pair(per_pair_savings, only_trade_size=None, only_aggs=None, show_only_to=False):
    token_savings = defaultdict(lambda: defaultdict(list))
    for pair, trade_size, agg, pct_savings in data_import.pct_savings_gen(per_pair_savings):
        if only_trade_size and trade_size != only_trade_size: continue
        token_savings[pair][agg] += pct_savings

    print(f"\nAverage Savings by Pair for Trade Size={only_trade_size}")
    print(f"\nPair,{','.join(only_aggs)}")

    for pair, savings in sorted(token_savings.items()):
        row = f"{pair[1]}" if show_only_to else f"{pair[1]}>{pair[0]}"
        for agg in only_aggs:
            if agg in savings:
                row += f",{compute_mean(savings[agg]) :.2f}"
            else:
                row += f","
        print(row)


def print_best_splits_over_time(best_splits, only_trade_size=50, label='Best Split'):
    """prints each of the splits contained in best_splits"""
    for pair, ts_id_best in sorted(best_splits.items()):
        print(f"\n\n====================================================================\n{pair}")
        for trade_size, id_best in ts_id_best.items():
            print(f"{trade_size} != {only_trade_size}")
            if trade_size != only_trade_size: continue
            print(f"\n{label} for {pair} at {trade_size}")

            ts_best_split = sorted([(timestamp_by_id[id], best['split']) for id, best in id_best.items() ])
            for timestamp, best_split in ts_best_split:
                print(f"{timestamp}: #{best_split}")


def do_summary_eth_pairs(csv_files):
    """Returns a dict containing pct savings token: { trade_size:  {exchange: [sample, sample, ...], ...}"""

    global timestamp_by_id

    per_pair_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    per_pair_savings_with_routing = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    per_pair_savings_without_routing = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    split_count_by_agg, non_split_count_by_agg = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))

    agg_names = set()
    large_neg_savings = {}
    select_samples = defaultdict(list)
    large_neg_savings_count, large_neg_savings_with_routing_count = 0, 0

    data_points, single_data_points, multi_data_points = 0, 0, 0

    best_splits = defaultdict(lambda: defaultdict(lambda: defaultdict()))
    totle_best_splits = defaultdict(lambda: defaultdict(lambda: defaultdict()))

    for filename in csv_files:
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=None)
            for row in reader:
                id, time, from_token, to_token, trade_size, totle_price, totle_splits, agg, agg_price, agg_splits, pct_savings = parse_row(row)
                pair = (to_token, from_token)

                agg_names.add(agg)
                timestamp_by_id[id] = time
                data_points += 1

                if len(agg_splits) > 1: split_count_by_agg[agg][trade_size] += 1
                else: non_split_count_by_agg[agg][trade_size] += 1

                # ******************* Select Samples (saves all samples) **************************
                # if totle_splits == agg_splits and totle_price / agg_price > 1.05: # same split diff price indicates price data discrepancy
                # if totle_price / agg_price > 1.05 and totle_splits != agg_splits and trade_size == 100 and to_token == 'REP' and agg not in ['1-Inch', '1-Inch V2']:
                if totle_price / agg_price > 1.05 and trade_size == 100 and to_token == 'REP' and agg == 'Paraswap':
                # if id == '0xda29700714084710ab72d95e0510a044881839807586493c870d4d7a7000a444':
                    key = (to_token, trade_size, agg)
                    select_samples[key].append((id, totle_price, totle_splits, agg_price, agg_splits))

                # ******************* Large neg savings (saves only the worst sample, keeps tally in the key) ***********************
                if trade_size == 50 and pct_savings < -2 and agg != 'DEX.AG':
                    large_neg_savings_count += 1
                    if is_multi_split(totle_splits): large_neg_savings_with_routing_count += 1
                    key = (to_token, trade_size, agg)
                    # print(f"{to_token} for {trade_size} ETH Totle price is {totle_price} {agg} price is {agg_price} -> Totle's price is {100 * ((totle_price - agg_price) / agg_price)}% GREATER\n   id={id}\n   Totle Split:\t{totle_splits}\n   {agg} Split:\t{agg_splits}")

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
                if is_multi_split(totle_splits):
                    multi_data_points += 1
                    per_pair_savings_with_routing[pair][trade_size][agg].append(pct_savings)
                else:
                    single_data_points += 1
                    per_pair_savings_without_routing[pair][trade_size][agg].append(pct_savings)

                totle_current = {'price': totle_price, 'split': totle_splits}
                totle_best_splits[pair][trade_size][id] = totle_current
                current = {'price': agg_price, 'split': agg_splits} if totle_price > agg_price else totle_current
                if (best_splits[pair][trade_size].get(id) is None) or (best_splits[pair][trade_size][id]['price'] > current['price']):
                    best_splits[pair][trade_size][id] = current


    agg_names = sorted(agg_names)
    # trade_sizes = sorted_trade_sizes(*per_pair_savings.values())

    print_data_points(data_points, single_data_points, multi_data_points, timestamp_by_id)

    # ************ BEST SPLITS OVER TIME ****************
    if False:
        print_best_splits_over_time(best_splits, only_trade_size=1000, label='Best split')

    if False:
        print_best_splits_over_time(totle_best_splits, only_trade_size=1000, label='Totle split')



    # ************ AVERAGE SAVINGS ****************
    if True:
        print_savings_summary_table_csv(aggregated_savings(per_pair_savings), agg_names, label="Average Savings (all samples)")
        print_avg_savings_by_pair(per_pair_savings, only_aggs=agg_names, show_only_to=True)
        print_avg_savings_by_pair(per_pair_savings, only_trade_size=1.0, only_aggs=agg_names, show_only_to=True)
        print_avg_savings_by_pair(per_pair_savings, only_trade_size=10.0, only_aggs=agg_names, show_only_to=True)
        print_avg_savings_by_pair(per_pair_savings, only_trade_size=100.0, only_aggs=agg_names, show_only_to=True)

    if False:
        print_savings_summary_table_csv(aggregated_savings(per_pair_savings, lambda pair: pair[1] == 'BAL'), agg_names, label="Average Savings (BAL/ETH)")
        print_savings_summary_table_csv(aggregated_savings(per_pair_savings, lambda pair: pair[1] == 'KNC'), agg_names, label="Average Savings (KNC/ETH)")
        print_savings_summary_table_csv(aggregated_savings(per_pair_savings, lambda pair: pair[1] == 'REP'), agg_names, label="Average Savings (REP/ETH)")


    # **************** BETTER WORSE SAME / SAVINGS SUMMARY TABLE **********************
    if True:
        total_samples = do_better_worse_same_price(per_pair_savings, "All Samples", agg_breakdown=True)


    # **************** BETTER WORSE SAME / WITH/WITHOUT ROUTING **********************
    if False:
        do_better_worse_same_price(per_pair_savings_with_routing, "Samples Where Totle Employed Smart Routing")
        print_savings_summary_table_csv(aggregated_savings(per_pair_savings_with_routing), agg_names, label="Average Savings (samples with smart routing)")

        do_better_worse_same_price(per_pair_savings_without_routing, "Samples Where Totle Did Not Employ Smart Routing")
        print_savings_summary_table_csv(aggregated_savings(per_pair_savings_without_routing), agg_names, label="Average Savings (samples without smart routing)")


    # **************** NEGATIVE SAVINGS **********************
    if False:
        print(f"\n\nNegative Savings Analysis")
        do_neg_savings(per_pair_savings, trade_sizes)


    # **************** LARGE NEG SAVINGS **********************
    if False:
        print(f"\n\nlarge_neg_savings_with_routing_count={large_neg_savings_with_routing_count}")
        print(f"large_neg_savings_count={large_neg_savings_count}")
        print_large_neg_savings(large_neg_savings, min_samples=10)


    # **************** SELECT SAMPLES **********************
    if False:
        print(f"\n********************************************* SELECT SAMPLES *********************************************************\n")
        n_select_samples = sum([ len(v) for k,v in select_samples.items() ])
        print(f"\nGot total of {n_select_samples} select samples ({100 * n_select_samples / total_samples}%)")
        id_to_timestamp = lambda ps: datetime.fromisoformat(timestamp_by_id[ps[0]])

        # zero_alloc_count = 0
        for tok_ts_agg, prices_splits_list in sorted(select_samples.items()):
            # print(f"\n\n{tok_ts_agg}")
            for prices_splits in sorted(prices_splits_list, key=id_to_timestamp):
                print_sample(tok_ts_agg, prices_splits)
                # print_sample(tok_ts_agg, prices_splits, print_snapshot=True)

    # ****************************************  Does Totle win more when it splits **********************
    if False:
        do_splits_vs_non_splits(csv_files, agg_names)
        do_totle_splits_vs_non_splits(csv_files, agg_names)
        per_token_both_splitting_savings, _ = data_import.parse_csv_files(csv_files, only_splits=True, only_totle_splits=True)
        do_neg_savings(per_token_both_splitting_savings, trade_sizes)

        do_both_splitting(per_token_both_splitting_savings, agg_names)
        do_neg_savings(per_token_both_splitting_savings, trade_sizes)
        print_avg_savings_by_pair(per_token_both_splitting_savings, only_trade_size=10.0, only_aggs=agg_names, show_only_to=True)
        print_avg_savings_by_pair(per_token_both_splitting_savings, only_trade_size=100.0, only_aggs=agg_names, show_only_to=True)


    # ***************************** PER PAIR SAVINGS **********************
    if False:
        print_avg_savings_per_pair_by_agg(per_pair_savings, 10.0, print_threshold=4, samples=True, min_stablecoins=0)
        print_savings_summary_by_pair_csv(per_pair_savings, 50.0, agg_names)
        for trade_size in trade_sizes:
            print_avg_savings_per_pair_by_agg(per_pair_savings, trade_size, print_threshold=0, samples=False)
        print_avg_savings_per_pair_by_trade_size(per_pair_savings, trade_sizes)


    # ***************************** SPLIT COUNTS **********************
    if False:
        print("\n\n---\n\n")
        # TODO add totle to agg_names
        print_split_counts_table(split_count_by_agg, non_split_count_by_agg, agg_names, trade_sizes)



# ************************** GLOBAL VARIABLES ***************************
timestamp_by_id = {} # id => timestamp


########################################################################################################################
def main():
    # csv_files = glob.glob(f'outputs/totle_vs_agg_metamask_top_pairs_2021-*csv')
    # do_summary_eth_pairs(tuple(csv_files))

    pre_pmm_files = glob.glob(f'outputs/mar-20/pre-pmm-uniq/*.csv')
    post_pmm_files = glob.glob(f'outputs/mar-20/post-pmm-uniq/*.csv')
    post_fix_files = glob.glob(f'outputs/totle_vs_agg_metamask_top_pairs_2021-03-24*csv')
    # do_summary_erc20_pairs(tuple(pre_pmm_files))
    # do_summary_erc20_pairs(tuple(post_pmm_files))
    do_summary_erc20_pairs(tuple(post_fix_files))

if __name__ == "__main__":
    main()
