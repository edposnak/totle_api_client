#!/usr/local/bin/python3
from datetime import datetime
import sys
from collections import defaultdict
import csv

import exchange_utils

def parse_csv_files(csv_files, only_tokens=None, only_splits=False, only_non_splits=False):
    """Returns 2 dicts containing pct savings and prices/split data both having the form
    token: { trade_size:  {exchange: [sample, sample, ...], ...}"""

    per_token_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    prices_splits = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for file in csv_files:
        with open(file, newline='') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=None)
            for row in reader:
                if row.get('splits'):
                    splits = exchange_utils.canonical_keys(eval(row['splits']))
                    if only_splits and len(splits) < 2: continue
                    if only_non_splits and len(splits) > 1: continue

                time = datetime.fromisoformat(row['time']).isoformat(' ', 'seconds')
                token, trade_size, exchange = row['token'], row['trade_size'], row['exchange']
                exchange_price, totle_price, pct_savings, totle_used = row['exchange_price'], row['totle_price'], float(row['pct_savings']), row['totle_used']

                # Exclude suspicious data
                # if (exchange, token) in  [('DEX.AG', 'ETHOS')]:
                #     # print(f"Excluding data for {token} on {exchange}")
                #     print(f"Excluding {row}")
                #     continue
                # if trade_size in ['0.1', '0.5'] and token == 'ZRX' and exchange == '1-Inch':
                if exchange == '1-Inch' and token == 'ZRX' and trade_size in ['0.1', '0.5'] and pct_savings < -1.0:
                    print(f"{time} {token} {trade_size} {pct_savings:.2f}% savings: {exchange} price={exchange_price} using {splits} Totle price={totle_price} using {totle_used} ")
                    continue

                if pct_savings > 10.0 or (len(splits) < 1 and pct_savings < -5.0) or (float(trade_size) < 1 and pct_savings < -5.0):
                    print(f"{time} {token} {trade_size} {pct_savings:.2f}% savings: {exchange} price={exchange_price} using {splits} Totle price={totle_price} using {totle_used} ")
                    continue

                prices_splits[token][trade_size][exchange].append((totle_price, exchange_price, splits))
                per_token_savings[token][trade_size][exchange].append(pct_savings)


    return per_token_savings, prices_splits

def aggregated_savings(per_token_savings):
    """Aggregates savings over all tokens for each trade_size"""
    per_trade_size_savings = defaultdict(lambda: defaultdict(list))

    for token, trade_size, exchange, pct_savings in pct_savings_gen(per_token_savings):
        per_trade_size_savings[trade_size][exchange] += pct_savings

    return per_trade_size_savings

def unique_exchanges(per_token_savings):
    return sorted(list(set(exchange for _, _, exchange, _ in pct_savings_gen(per_token_savings))))


########################################################################################################################
# functions to print tables etc.


def print_savings_with_num_samples(savings_by_trade_size):
    print(f"\n\nOverall average price savings by trade size are shown below.")
    for trade_size in sorted_trade_sizes(savings_by_trade_size):
        print(f"\nAverage Savings trade size = {trade_size} ETH vs")
        for exchange, pct_savings in savings_by_trade_size[trade_size].items():
            sum_savings, n_samples = sum(pct_savings), len(pct_savings)
            print(f"   {exchange}: {sum_savings / n_samples:.2f}% ({n_samples} samples)")

def print_neg_savings_stats(per_token_savings):
    neg_savings, pos_savings = defaultdict(int), defaultdict(int)
    for token, trade_size, exchange, pct_savings in pct_savings_gen(per_token_savings):
        for pct in pct_savings:
            if pct > 0.0:
                pos_savings[exchange] += 1
            else:
                neg_savings[exchange] += 1

    exchanges = sorted(list(set(neg_savings.keys()) | set(pos_savings.keys())))
    neg_samples = sum(neg_savings.values())
    pos_samples = sum(pos_savings.values())
    total_samples = neg_samples + pos_samples
    neg_pct = 100.0 * neg_samples / total_samples

    print(f"\n\nOut of {total_samples} data points, Totle's fees exceeded the price savings {neg_samples} times, resulting in negative price savings {neg_pct:.1f}% of the time.")
    header = "\t".join(['NPS %'] + exchanges)
    print(f"\n{header}")
    row = ["buys"]
    for exchange in exchanges:
        if exchange in neg_savings:
            pct_neg_savings = 100 * neg_savings[exchange] / (neg_savings[exchange] + pos_savings[exchange])
            row.append(f"{pct_neg_savings:.2f}%")
        else:
            row.append("")
    print("\t".join(row))

def print_per_token_savings_summary_tables(per_token_savings, exchanges):
    for token, tss in per_token_savings.items():
        print(f"\n\n{token}")
        print_savings_summary_table(tss, exchanges)

def print_savings_summary_table(per_trade_size_savings, all_exchanges):
    headers = ''.join(list(map(lambda e: f"{e:<18}", all_exchanges)))
    print(f"{'Trade Size':<18}{headers}")
    # for trade_size, savings in savings_by_trade_size.items():
    for trade_size in sorted_trade_sizes(per_trade_size_savings):
        savings = per_trade_size_savings[trade_size]
        row = f"{trade_size:<6} ETH        "
        for exchange in all_exchanges:
            if exchange in savings:
                sum_savings, n_samples = sum(savings[exchange]), len(savings[exchange])
                pct_savings = sum_savings / n_samples
                row += f"{pct_savings:<18.2f}"
            else:
                row += f"{'-':18}"
        print("".join(row))

def print_savings_summary_table_csv(per_trade_size_savings, all_exchanges):
    print(f"Trade Size,{','.join(all_exchanges)}")
    for trade_size in sorted_trade_sizes(per_trade_size_savings):
        savings = per_trade_size_savings[trade_size]
        row = f"{trade_size}"
        for exchange in all_exchanges:
            if exchange in savings:
                sum_savings, n_samples = sum(savings[exchange]), len(savings[exchange])
                pct_savings = sum_savings / n_samples
                row += f",{pct_savings:.2f}"
            else:
                row += f","
        print(row)

def print_big_savings(per_token_savings, lower_bound_pct=-5.0, upper_bound_pct=5.0):
    for token, trade_size, exchange, pct_savings in pct_savings_gen(per_token_savings):
        for pct in pct_savings:
            if pct < lower_bound_pct or pct > upper_bound_pct:
                print(f"BIG SAVINGS: {token} {trade_size} {exchange} {pct}")

def print_outliers(per_token_savings, min_diff_pct=2.0):
    for token, ts_ex_savings in per_token_savings.items():
        for trade_size, ex_savings in ts_ex_savings.items():
            averages = {}
            for exchange, savings in ex_savings.items():
                sum_savings, n_samples = sum(savings), len(savings)
                averages[exchange] = sum_savings / n_samples

            for agg1 in averages:
                for agg2 in averages:
                    agg1_pct, agg2_pct = averages[agg1], averages[agg2]
                    if agg1_pct - agg2_pct > min_diff_pct:
                        print(f"OUTLIER for {token} {trade_size}: {agg1} saved {agg1_pct}, {agg2} saved {agg2_pct}")



def pct_savings_gen(per_token_savings):
    """Generates a sequence of (token, trade_size, agg/exchange, [pct_savings]) for all leaves in the given dict"""
    for token, ts_ex_savings in per_token_savings.items():
        for trade_size, ex_savings in ts_ex_savings.items():
            for exchange, pct_savings in ex_savings.items():
                yield token, trade_size, exchange, pct_savings


def sorted_trade_sizes(savings_by_trade_size):
    return map(str, sorted(map(float, savings_by_trade_size.keys())))

########################################################################################################################
# main

csv_files = sys.argv[1:]
if len(csv_files) < 1:
    print("no CSV files provided")
    exit(1)
else:
    print(f"processing {len(csv_files)} CSV files ...")

per_token_savings, prices_splits = parse_csv_files(csv_files)
per_trade_size_savings = aggregated_savings(per_token_savings)

print_neg_savings_stats(per_token_savings)

# print average savings by trade_size, exchange with num samples
print_savings_with_num_samples(per_trade_size_savings)

# print average savings summary table
aggs = exchanges = unique_exchanges(per_token_savings)
print("\n\n")
print_savings_summary_table(per_trade_size_savings, exchanges)
print("\n\n")
print_savings_summary_table_csv(per_trade_size_savings, exchanges)
exit(0)
# print average savings by token
print("\n\n")
print_per_token_savings_summary_tables(per_token_savings, exchanges)

for token in ['ENJ','BAT','MKR','DAI']:
    print(f"\n{token}")
    print_savings_summary_table_csv(per_token_savings[token], exchanges)

# print outlier data
print_outliers(per_token_savings)
print_big_savings(per_token_savings, lower_bound_pct=-7.0)

# def print_pct_split(token, )