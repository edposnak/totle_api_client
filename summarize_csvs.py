#!/usr/local/bin/python3
from datetime import datetime
import sys
from collections import defaultdict

import data_import

########################################################################################################################
# data derivative functions

# get savings by trade_size
def aggregated_savings(per_token_savings, filter=None):
    """Aggregates savings over all tokens for each trade_size returns a dict { trade_size: { agg: savings_list, ..."""
    per_trade_size_savings = defaultdict(lambda: defaultdict(list))

    for pair, trade_size, agg, pct_savings in data_import.pct_savings_gen(per_token_savings):
        if not filter or filter(pair):
            per_trade_size_savings[trade_size][agg] += pct_savings

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
    neg_savings_ts, pos_savings_ts = defaultdict(int), defaultdict(int)
    for token, trade_size, exchange, pct_savings in data_import.pct_savings_gen(per_token_savings):
        for pct in pct_savings:
            if pct > 0.0:
                pos_savings[exchange] += 1
                pos_savings_ts[trade_size] += 1
            else:
                neg_savings[exchange] += 1
                neg_savings_ts[trade_size] += 1

    exchanges = sorted(list(set(neg_savings.keys()) | set(pos_savings.keys())))
    neg_samples = sum(neg_savings.values())
    pos_samples = sum(pos_savings.values())
    total_samples = neg_samples + pos_samples
    neg_pct = 100.0 * neg_samples / total_samples

    print(f"\n\nOut of {total_samples} data points, Totle's fees exceeded the price savings {neg_samples} times, resulting in negative price savings {neg_pct:.1f}% of the time.")

    header = ''.join([ f"{s:<14}" for s in ['NPS % vs'] + exchanges ])
    print(f"\n{header}")
    row = ["total"]
    for exchange in exchanges:
        if exchange in neg_savings:
            pct_neg_savings = 100 * neg_savings[exchange] / (neg_savings[exchange] + pos_savings[exchange])
            row.append(f"{pct_neg_savings:.2f}%")
        else:
            row.append("")
    print(''.join([ f"{s:<14}" for s in row ]))

    trade_sizes = sorted_trade_sizes(pos_savings_ts, neg_savings_ts)

    header = ''.join([ f"{s:<14}" for s in ['Trade Size'] + trade_sizes ])
    print(f"\n{header}")
    row = ["total NPS%"]
    for trade_size in trade_sizes:
        if trade_size in neg_savings_ts:
            pct_neg_savings = 100 * neg_savings_ts[trade_size] / (neg_savings_ts[trade_size] + pos_savings_ts[trade_size])
            row.append(f"{pct_neg_savings:.2f}%")
        else:
            row.append("")
    print(''.join([ f"{s:<14}" for s in row ]))


def print_avg_savings_per_token(per_token_savings, only_trade_size=None):
    token_savings = defaultdict(list)
    for token, trade_size, exchange, pct_savings in data_import.pct_savings_gen(per_token_savings):
        if only_trade_size and trade_size != only_trade_size: continue
        token_savings[token] += pct_savings

    print(f"\n\nToken\tSavings for trade_size={only_trade_size}")
    for token, savings in sorted(token_savings.items()):
        print(f"{token}\t{savings}")

    print(f"\n\nToken\tMean Pct. Savings")
    for token, savings in sorted(token_savings.items()):
        print(f"{token}\t{compute_mean(savings):.2f}")


def print_per_token_savings_summary_tables(per_token_savings, exchanges):
    for token, tss in per_token_savings.items():
        print(f"\n\n{token}")
        print_savings_summary_table(tss, exchanges)

def print_savings_summary_table(per_trade_size_savings, all_exchanges, label=''):
    print(f"\n{label}")
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

def print_per_token_savings_summary_table_csvs(per_token_savings, exchanges):
    for token, tss in per_token_savings.items():
        print_savings_summary_table_csv(tss, exchanges, label=f"{token}")

def print_savings_summary_table_csv(per_trade_size_savings, only_exchanges, label="Average Savings"):
    print(f"\n{label}")
    print(f"\nTrade Size,{','.join(only_exchanges)}")
    for trade_size in sorted_trade_sizes(per_trade_size_savings):
        savings = per_trade_size_savings[trade_size]
        row = f"{trade_size}"
        for exchange in only_exchanges:
            if exchange in savings:
                row += f",{compute_mean(savings[exchange]) :.2f}"
            else:
                row += f","
        print(row)


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
    print(f"\nSplit vs Non-Split Savings Summary")
    print(f"Trade Size,{','.join(map(lambda x: f'{x} (non-split),{x} (splits-only)', aggs))}")
    for trade_size in sorted_trade_sizes(per_trade_size_splits_only, per_trade_size_non_splits_only):
        non_splits = per_trade_size_non_splits_only.get(trade_size)
        splits_only = per_trade_size_splits_only.get(trade_size)
        row = f"{trade_size}"
        for agg in aggs:
            non_split_str = f"{compute_mean(non_splits[agg]):.2f}" if non_splits and non_splits.get(agg) else ''
            split_str = f"{compute_mean(splits_only[agg]):.2f}" if splits_only and splits_only.get(agg) else ''
            row += f",{non_split_str},{split_str}"
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
    mean_pct_savings = sum_savings / n_samples
    return mean_pct_savings


basis_points = lambda x: x * 10000

# def sorted_trade_sizes(savings_by_trade_size):
#     return map(str, sorted(map(float, savings_by_trade_size.keys())))

def sorted_trade_sizes(*dicts):
    """Finds and sorts all trade sizes in the given dicts, which should be of the form {trade_size: stuff}"""
    all_trade_sizes = set(sum([ list(d.keys()) for d in dicts ], []))
    return sorted(map(float, all_trade_sizes))


########################################################################################################################
def do_splits_vs_non_splits(csv_files, aggs):
    # print average savings summary table
    per_token_splits_only_savings, _ = data_import.parse_csv_files(csv_files, only_splits=True)
    per_token_non_splits_only_savings, non_splits_only_slip_price_splits = data_import.parse_csv_files(csv_files, only_non_splits=True)
    per_trade_size_splits_only = aggregated_savings(per_token_splits_only_savings)
    per_trade_size_non_splits = aggregated_savings(per_token_non_splits_only_savings)

    # print splits vs non-splits summary CSV
    print_savings_summary_table_csv(per_trade_size_non_splits, aggs, label="All tokens savings by trade size (non-splits)")
    print_savings_summary_table_csv(per_trade_size_splits_only, aggs, label="All tokens savings by trade size (only splits)")
    # print("\n\nAll tokens savings by trade size splits vs non-splits")
    print_split_vs_non_split_savings_summary_table_csv(per_trade_size_splits_only, per_trade_size_non_splits, aggs)
    # TODO EJP csv where each row is it's own curve. See how MKR/ETH on Uniswap changes over time
    # print_pmm_savings_table_csv(non_splits_only_slip_price_splits, 'USDT USDC PAX TUSD WBTC DAI'.split())
    # print("\n\nSavings for each token by trade size (non-splits)")
    # print_per_token_savings_summary_tables(per_token_non_splits_only_savings, aggs)
    # print("\n\nSavings for each token by trade size (only splits)")
    # print_per_token_savings_summary_tables(per_token_splits_only_savings, aggs)
    # for token in ['ENJ', 'BAT', 'MKR', 'DAI']:
    #     print_savings_summary_table_csv(per_token_splits_only_savings[token], aggs, label=f"{token}")



def main():
    csv_files = tuple(sys.argv[1:])
    if len(csv_files) < 1:
        print("no CSV files provided")
        exit(1)
    else:
        print(f"processing {len(csv_files)} CSV files ...")
    per_token_savings, slip_price_splits = data_import.parse_csv_files(csv_files)
    aggs_or_exchanges = unique_exchanges(per_token_savings)
    print(f"aggs_or_exchanges={aggs_or_exchanges}")

    per_trade_size_savings = aggregated_savings(per_token_savings)

    # print slippage vs splits
    # print_slippage_split_pct_csvs(slip_price_splits)
    # print negative savings vs exchanges
    print_neg_savings_stats(per_token_savings)
    # print average savings by trade_size, exchange with num samples
    # print("\n\nAll tokens savings by trade size with num samples")
    # print_savings_with_num_samples(per_trade_size_savings)

    # print_per_token_savings_summary_table_csvs(per_token_savings, aggs_or_exchanges)

    # print average savings by token
    # print("\n\nSavings for each token by trade size (all)")
    # print_per_token_savings_summary_tables(per_token_savings, aggs_or_exchanges)

    # print_savings_summary_table_csv(per_trade_size_savings, ['Binance', 'BinanceC', 'Huobi', 'HuobiC', 'Kraken', 'KrakenC'])
    print_savings_summary_table_csv(per_trade_size_savings, sorted(set(aggs_or_exchanges) - {'BinanceC', 'HuobiC', 'KrakenC'}))
    # print_savings_summary_table_csv(per_trade_size_savings, aggs_or_exchanges)

    for trade_size in [0.1]:
        print(f"Savings for trade size {trade_size}")
        print_avg_savings_per_token(per_token_savings, trade_size)

    # do_splits_vs_non_splits(csv_files, aggs_or_exchanges)

    # print outlier data
    # print_outliers(per_token_savings)
    # print_big_savings(per_token_savings, lower_bound_pct=-7.0)




if __name__ == "__main__":
    main()
