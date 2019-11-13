#!/usr/local/bin/python3
from datetime import datetime
import sys
from collections import defaultdict

import data_import

########################################################################################################################
# data derivative functions

# get savings by trade_size
def aggregated_savings(per_token_savings):
    """Aggregates savings over all tokens for each trade_size"""
    per_trade_size_savings = defaultdict(lambda: defaultdict(list))

    for token, trade_size, exchange, pct_savings in data_import.pct_savings_gen(per_token_savings):
        per_trade_size_savings[trade_size][exchange] += pct_savings

    return per_trade_size_savings

# get a list of unique exchanges
def unique_exchanges(per_token_savings):
    return sorted(list(set(exchange for _, _, exchange, _ in data_import.pct_savings_gen(per_token_savings))))


########################################################################################################################
# functions to print tables etc.

def print_savings_with_num_samples(savings_by_trade_size):
    print(f"\n\nOverall average price savings by trade size are shown below.")
    for trade_size in sorted_trade_sizes(savings_by_trade_size):
        print(f"\nAverage Savings trade size = {trade_size} ETH vs")
        for exchange, pct_savings in savings_by_trade_size[trade_size].items():
            print(f"   {exchange}: {compute_mean(pct_savings):.2f}% ({len(pct_savings)} samples)")

def print_neg_savings_stats(per_token_savings):
    neg_savings, pos_savings = defaultdict(int), defaultdict(int)
    for token, trade_size, exchange, pct_savings in data_import.pct_savings_gen(per_token_savings):
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
                row += f"{compute_mean(savings[exchange]):<18.2f}"
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
                row += f",{compute_mean(savings[exchange]) :.2f}"
            else:
                row += f","
        print(row)

#                 slip_price_splits[token][trade_size][exchange].append((slip, price_diff, splits))


def print_pmm_savings_table_csv(slip_price_splits, tokens):
    sorted_tokens = sorted(tokens)
    print(f"Trade Size,{','.join(sorted_tokens)}")

    ts_tok_savings = defaultdict(lambda: defaultdict(list))
    for token, ts_ex_slip_price_splits in slip_price_splits.items():
        for trade_size, ex_slip_price_splits in ts_ex_slip_price_splits.items():
            for dex, slip_price_splits in ex_slip_price_splits.items():
                for _, price_diff, split in slip_price_splits:
                    if 'PMM' in split:
                        ts_tok_savings[trade_size][token].append(-100 * price_diff)

    for trade_size in sorted_trade_sizes(ts_tok_savings):
        per_token_savings = ts_tok_savings[trade_size]
        row = f"{trade_size}"
        for token in sorted_tokens:
            if token in per_token_savings:
                row += f",{compute_mean(per_token_savings[token]) :.2f}"
            else:
                row += f","
        print(row)

def print_split_vs_non_split_savings_summary_table_csv(per_trade_size_splits_only, per_trade_size_non_splits_only, aggs):
    print(f"Trade Size,{','.join(map(lambda x: f'{x} (non-split), {x} (splits-only)', aggs))}")
    for trade_size in sorted_trade_sizes(per_trade_size_splits_only, per_trade_size_non_splits_only):
        non_splits = per_trade_size_non_splits_only[trade_size]
        splits_only = per_trade_size_splits_only[trade_size]
        row = f"{trade_size}"
        for agg in aggs:
            if agg in splits_only:
                non_split_str = f"{compute_mean(non_splits[agg]):.2f}" if non_splits[agg] else ''
                split_str = f"{compute_mean(splits_only[agg]):.2f}" if splits_only[agg] else ''
                row += f",{non_split_str},{split_str}"
            else:
                row += f",,"
        print(row)

def print_non_split_savings_for_oneinch(per_token_non_splits_only_savings):
    for token, ts_agg_savings in per_token_non_splits_only_savings.items():
        savings = ts_agg_savings['300.0']['1-Inch']
        print(f"{token}: {savings}")

def print_big_savings(per_token_savings, lower_bound_pct=-5.0, upper_bound_pct=5.0):
    for token, trade_size, exchange, pct_savings in data_import.pct_savings_gen(per_token_savings):
        for pct in pct_savings:
            if pct < lower_bound_pct or pct > upper_bound_pct:
                print(f"BIG SAVINGS: {token} {trade_size} {exchange} {pct}")

def print_outliers(per_token_savings, min_diff_pct=2.0):
    for token, ts_ex_savings in per_token_savings.items():
        for trade_size, ex_savings in ts_ex_savings.items():
            averages = {}
            for exchange, savings in ex_savings.items():
                averages[exchange] = compute_mean(savings)

            for agg1 in averages:
                for agg2 in averages:
                    agg1_pct, agg2_pct = averages[agg1], averages[agg2]
                    if agg1_pct - agg2_pct > min_diff_pct:
                        print(f"OUTLIER for {token} {trade_size}: {agg1} saved {agg1_pct}, {agg2} saved {agg2_pct}")

def print_slippage_split_pct_csvs(slip_price_splits):
    # TODO combine CSV and JSON data.
    # DO THIS to incorporate JSON split data
    # tok_ts_splits_by_agg = data_import.get_all_splits_by_agg()
    # tokens_ts_pcts = data_import.tokens_split_pct(tok_ts_splits_by_agg)

    for token, ts_agg_price_splits in slip_price_splits.items():
        print(f"\n\n{token}/ETH\nTrade Size,Mean Slippage,Mean Cost,Pct Split")
        for trade_size, agg_price_splits in ts_agg_price_splits.items():
            slips, price_diffs, splits = [], [], []
            for _, slip_price_splits in agg_price_splits.items():
                slips += [sps[0] for sps in slip_price_splits]
                price_diffs += [sps[1] for sps in slip_price_splits]
                splits += [1  if len(sps[2]) > 1 else 0 for sps in slip_price_splits]

            avg_slip = basis_points(compute_mean(slips))
            avg_price_diff = basis_points(compute_mean(price_diffs))
            split_pct = 100.0 * compute_mean(splits)
            print(f"{trade_size},{avg_slip:.8f},{avg_price_diff},{split_pct}")

def compute_mean(savings_list):
    if not savings_list: return None
    sum_savings, n_samples = sum(savings_list), len(savings_list)
    pct_savings = sum_savings / n_samples
    return pct_savings


basis_points = lambda x: x * 10000

# def sorted_trade_sizes(savings_by_trade_size):
#     return map(str, sorted(map(float, savings_by_trade_size.keys())))

def sorted_trade_sizes(*dicts):
    all_trade_sizes = set(sum([ list(d.keys()) for d in dicts ], []))
    return map(str, sorted(map(float, all_trade_sizes)))


########################################################################################################################
# main

csv_files = tuple(sys.argv[1:])
if len(csv_files) < 1:
    print("no CSV files provided")
    exit(1)
else:
    print(f"processing {len(csv_files)} CSV files ...")

per_token_savings, slip_price_splits = data_import.parse_csv_files(csv_files)
per_trade_size_savings = aggregated_savings(per_token_savings)
per_token_splits_only_savings, _ = data_import.parse_csv_files(csv_files, only_splits=True)
per_token_non_splits_only_savings, non_splits_only_slip_price_splits = data_import.parse_csv_files(csv_files, only_non_splits=True)
per_trade_size_splits_only = aggregated_savings(per_token_splits_only_savings)
per_trade_size_non_splits = aggregated_savings(per_token_non_splits_only_savings)

# print slippage vs splits
# print_slippage_split_pct_csvs(slip_price_splits)

# print negative savings vs exchanges
# print_neg_savings_stats(per_token_savings)

# print average savings by trade_size, exchange with num samples
# print("\n\nAll tokens savings by trade size with num samples")
# print_savings_with_num_samples(per_trade_size_savings)

# print average savings summary table
# aggs = exchanges = unique_exchanges(per_token_savings)

# print splits vs non-splits summary CSV
# print("\n\nAll tokens savings by trade size (non-splits)")
# print_savings_summary_table(per_trade_size_non_splits, exchanges)
# print("\n\nAll tokens savings by trade size (only splits)")
# print_savings_summary_table_csv(per_trade_size_splits_only, exchanges)
#
# print("\n\nAll tokens savings by trade size splits vs non-splits")
# print_split_vs_non_split_savings_summary_table_csv(per_trade_size_splits_only, per_trade_size_non_splits, aggs)

# TODO EJP csv where each row is it's own curve. See how MKR/ETH on Uniswap changes over time
print_pmm_savings_table_csv(non_splits_only_slip_price_splits, 'USDT USDC PAX TUSD WBTC DAI'.split())
exit(0)

# print average savings by token
# print("\n\nSavings for each token by trade size (all)")
# print_per_token_savings_summary_tables(per_token_savings, exchanges)
# print("\n\nSavings for each token by trade size (non-splits)")
# print_per_token_savings_summary_tables(per_token_non_splits_only_savings, exchanges)
# print("\n\nSavings for each token by trade size (only splits)")
# print_per_token_savings_summary_tables(per_token_splits_only_savings, exchanges)
# for token in ['ENJ','BAT','MKR','DAI']:
#     print(f"\n{token}")
#     print_savings_summary_table_csv(per_token_splits_only_savings[token], exchanges)
#
# # print outlier data
# print_outliers(per_token_savings)
# print_big_savings(per_token_savings, lower_bound_pct=-7.0)

