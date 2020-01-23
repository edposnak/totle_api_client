import sys
import glob
import functools
import csv
from collections import defaultdict

import dexag_client
import data_import
import exchange_utils
import slippage_curves
from v2_compare_prices import get_pct_savings, get_filename_base, SavingsCSV

#######################################################################################################################
# totle_vs_agg CSV parsing (summary creation)

def get_cost_comparisons(csv_files):
    """Yields cost comparison data"""

    for csv_file in csv_files:
        price_estimators = get_price_estimators(csv_file)
        if not price_estimators:
            print(f"Skipping {csv_file} because it had no price data from which to create slippage curves")
            continue

        # Get price and split data, estimate Totle savings from splitting, and record estimates along with metrics for accuracy of price curves
        for time, action, trade_size, token, agg, agg_price, no_split_totle_used, no_split_totle_price, no_split_pct_savings, agg_split, ex_prices in data_import.csv_row_gen(csv_file):
            estimator = price_estimators.get(token)
            if not estimator:
                print(f"\n\nskipping {agg} {action} {token} for {trade_size} ETH because no price estimator exists for {token}")
                continue
            dexs_with_one_price_point = [e for e, pp in estimator.num_price_points.items() if pp < 2]
            if any(dexs_with_one_price_point):
                print(f"\n\nskipping {agg} {action} {token} for {trade_size} ETH because price estimator for {token} has insufficient price data for {dexs_with_one_price_point}")
                continue

            actual_agg_dest_amount = trade_size / agg_price

            exclude_dexs = ['Radar Relay'] # always exclude Radar Relay, Totle uses 0xMesh
            totle_solution = slippage_curves.splitting_algorithm(trade_size, estimator, exclude_dexs=exclude_dexs)
            est_totle_dest_amount, est_totle_split_pct_savings = estimate_savings(totle_solution, estimator, actual_agg_dest_amount, agg_split)

            # TODO Account for situations where agg knows Kyber is using Uniswap (or is excluding Uniswap reserve) and using Uniswap
            if {'Uniswap', 'Kyber'}.issubset(totle_solution):
                if ('Uniswap' in agg_split or 'Kyber' in agg_split) and not {'Uniswap', 'Kyber'}.issubset(agg_split):
                    # print(f"RECALCULATE: {time} {token} {trade_size} {est_totle_split_pct_savings} \nTotle: amt={est_totle_dest_amount} {totle_solution}\n{agg} amt={actual_agg_dest_amount} {agg_split}")
                    exclude_dexs += ['Kyber'] if 'Uniswap' in agg_split else ['Uniswap']
                    totle_solution = slippage_curves.splitting_algorithm(trade_size, estimator, exclude_dexs=exclude_dexs)
                    est_totle_dest_amount, est_totle_split_pct_savings = estimate_savings(totle_solution, estimator, actual_agg_dest_amount, agg_split)

            totle_split = slippage_curves.to_percentages(totle_solution)
            est_totle_split_price = trade_size / est_totle_dest_amount
            cost_error_pct, tokens_error_pct = get_error_pcts(actual_agg_dest_amount, estimator, trade_size, agg_price, agg_split)

            print(f"\n\n{agg} {action} {token} for {trade_size} ETH agg_price={agg_price:.6f} totle_price={no_split_totle_price:.6f} pct_savings={no_split_pct_savings:.2f}")
            print(f"Totle  split={totle_split} est. price={est_totle_split_price} est. amount={est_totle_dest_amount}")
            print(f"{agg[:6]:6} split={agg_split} actual price={agg_price:.6f} actual amount={actual_agg_dest_amount}")
            print(f"Totle non-split pct_savings={no_split_pct_savings:.2f} Totle split pct_savings={est_totle_split_pct_savings :.2f}")

            yield {
                'time': time,
                'action': action,
                'trade_size': trade_size,
                'token': token,
                'agg': agg,
                'agg_price': agg_price,
                'agg_split': agg_split,
                'no_split_totle_used': no_split_totle_used,
                'no_split_totle_price': no_split_totle_price,
                'no_split_pct_savings': no_split_pct_savings,
                'totle_split': totle_split,
                'totle_split_price': est_totle_split_price,
                'totle_split_pct_savings': est_totle_split_pct_savings,
                'cost_error_pct': cost_error_pct,
                'tokens_error_pct': tokens_error_pct,
            }

TOTLE_PRESUMED_FEE = 0.0025
TOTLE_MEASURED_FEE = 0.00251256281407
TOTLE_FEE = 0.0025125
def estimate_savings(totle_solution, estimator, actual_agg_dest_amount, agg_split):
    totle_split = slippage_curves.to_percentages(totle_solution)
    if totle_split == agg_split: # use the aggregator's amount for more accurate price comparison
        est_totle_dest_amount = actual_agg_dest_amount
    else:
        est_totle_dest_amount = estimator.destination_amount(totle_solution)

    est_totle_dest_amount *= (1 - TOTLE_FEE) # subtract Totle's fee from dest amount
    est_totle_split_pct_savings = get_pct_savings(actual_agg_dest_amount, est_totle_dest_amount)
    return est_totle_dest_amount, est_totle_split_pct_savings




def get_price_estimators(csv_file):
    tok_ex_ts_prices, tok_ex_known_liquidity = get_all_prices_and_known_liquidities(csv_file)
    price_estimators = {token: slippage_curves.PriceEstimator(token, prices, tok_ex_known_liquidity[token]) for token, prices in tok_ex_ts_prices.items()}

    # These are just sanity checks
    for token, ex_ts_prices in tok_ex_ts_prices.items():
        estimator = price_estimators[token]
        for ex, ts_prices in ex_ts_prices.items():
            # check that the prices are close to the sample
            for ts, price in ts_prices.items():
                ls_price = estimator.get_ls_price(ex, ts)
                if abs(ls_price - price) > 0.001:
                    print(f"ESTIMATOR LEAST SQUARES PRICE DIFF: {token} {ts} {ex}: {price} ls_price={ls_price} (diff={ls_price - price:.8f})")
                mx_price = estimator.get_absolute_price(ex, ts)
                if abs(mx_price - price) > 0.001:
                    print(f"ESTIMATOR ABSOLUTE PRICE DIFF: {token} {ts} {ex}: {price} mx_price={mx_price} (diff={mx_price - price:.8f})")

    return price_estimators


@functools.lru_cache()
def get_all_prices_and_known_liquidities(csv_file):
    tok_ex_ts_prices = defaultdict(lambda: defaultdict(dict))
    tok_ex_known_liquidity = defaultdict(lambda: defaultdict(float))
    # Use splits and non-splits to get price data
    for time, action, trade_size, token, agg, agg_price, totle_used, totle_price, pct_savings, agg_split, ex_prices in data_import.csv_row_gen(csv_file):
        if ex_prices and agg == dexag_client.name():  # only use DEX.AG ex_prices data
            for ex, price in ex_prices.items():
                tok_ex_ts_prices[token][ex][trade_size] = price
        for ex in agg_split:
            eth_used = trade_size * agg_split[ex] / 100
            if eth_used > tok_ex_known_liquidity[token][ex]:
                tok_ex_known_liquidity[token][ex] = eth_used
    return tok_ex_ts_prices, tok_ex_known_liquidity


# These are arbitrary values. We want a very tight tokens_error margin because that is what prices are based on. Cost error varies widely with
# small differences in price. If the price error is low, then the price data is good, even if estimated costs vary somewhat wildly.
MAX_COST_ERROR_PCT = 25
MAX_TOKENS_ERROR_PCT = 1

def get_error_pcts(actual_agg_dest_amount, estimator, trade_size, agg_price, agg_split):
    # we don't have price curves for AirSwap or Oasis so we can't get est_agg_solution_cost to compare
    if 'AirSwap' in agg_split or 'Oasis' in agg_split:
        return 999999999, 999999999
    actual_agg_solution_cost = trade_size * (agg_price - estimator.base_price) / estimator.base_price
    agg_solution = slippage_curves.to_trade_size_allocations(agg_split, trade_size)
    est_agg_dest_amount = estimator.destination_amount(agg_solution)
    est_agg_solution_cost = estimator.solution_cost(agg_solution)

    # This is to ensure that the prices and slippage curves we're using are reasonably close
    cost_error = est_agg_solution_cost - actual_agg_solution_cost
    cost_error_pct = round(100 * cost_error / (actual_agg_solution_cost or 0.0001), 1)
    if abs(cost_error_pct) > MAX_COST_ERROR_PCT:
        print(f"COST ERROR: {cost_error_pct}% actual_agg_solution_cost={actual_agg_solution_cost:.8f} est_agg_solution_cost={est_agg_solution_cost:.8f}")

    # This is to ensure that the estimated amounts used to calculate pct_savings are very accurate
    tokens_error = est_agg_dest_amount - actual_agg_dest_amount
    tokens_error_pct = round(100 * tokens_error / actual_agg_dest_amount, 1)
    # print(f"errord tokens acquire by {tokens_error:.1f} tokens out of {actual_agg_dest_amount:.1f} ({tokens_error_pct:.2f}%)")
    if abs(tokens_error_pct) > MAX_TOKENS_ERROR_PCT:
        print(f"TOKENS ERROR: {tokens_error_pct}% actual amount={actual_agg_dest_amount:.1f} est. amount={est_agg_dest_amount:.1f}")

    return cost_error_pct, tokens_error_pct

#######################################################################################################################
# Summary CSV parsing

CSV_FIELDS = "time action trade_size token agg agg_price agg_split no_split_totle_used no_split_totle_price no_split_pct_savings totle_split totle_split_price totle_split_pct_savings cost_error_pct tokens_error_pct".split()

def summary_csv_row_gen(summary_csv_file, only_splits=False, only_non_splits=False, max_cost_error_pct=MAX_COST_ERROR_PCT, max_tokens_error_pct=MAX_TOKENS_ERROR_PCT):
    """Reads in the summary CSV and yields rows based on price data that meets max_cost_error_pct and max_tokens_error_pct constraints"""
    print(f"\n\nsummary_csv_row_gen doing {summary_csv_file}, only_splits={only_splits}, only_non_splits={only_non_splits}) ...")

    with open(summary_csv_file, newline='') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=None)
        for row in reader:
            if not row.get('agg_split'): print(f"WARNING no agg_split value for row in {summary_csv_file}")
            agg_split = exchange_utils.canonical_keys(eval(row.get('agg_split') or '{}'))
            if only_splits and len(agg_split) < 2: continue
            if only_non_splits and len(agg_split) > 1: continue

            # get all the column values
            time, action = row['time'], row['action']
            trade_size, token = float(row['trade_size']), row['token']
            agg, agg_price =  row['agg'], row['agg_price'] # agg_split was done at the top
            no_split_totle_used, no_split_totle_price, no_split_pct_savings = row['no_split_totle_used'], float(row['no_split_totle_price']), float(row['no_split_pct_savings']),
            totle_split = exchange_utils.canonical_keys(eval(row.get('totle_split') or '{}'))
            totle_split_price, totle_split_pct_savings = float(row['totle_split_price']), float(row['totle_split_pct_savings'])
            cost_error_pct, tokens_error_pct = float(row['cost_error_pct']), float(row['tokens_error_pct'])


            # Discard rows where calculations are off because price data is incomplete/different
            if cost_error_pct < max_cost_error_pct and tokens_error_pct < max_tokens_error_pct:
                if token == 'RDN' and trade_size == 10.0 and agg == '1-Inch':
                    print(f"HIYALL {token} {trade_size} {agg}: {agg_split} Totle: {totle_split} pct_savings={totle_split_pct_savings:.2f} cost_error_pct={cost_error_pct} tokens_error_pct={tokens_error_pct}")
                yield time, action, trade_size, token, agg, agg_price, agg_split, no_split_totle_used, no_split_totle_price, no_split_pct_savings, totle_split, totle_split_price, totle_split_pct_savings
            else:
                pass
                # print(f"discarding {token} {trade_size} {agg}: {agg_split} Totle: {totle_split} pct_savings={totle_split_pct_savings:.2f} cost_error_pct={cost_error_pct} {tokens_error_pct}")


def get_per_token_savings(summary_csv_file):
    per_token_splits_only_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    per_token_non_splits_only_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    row_count = 0
    agg_split_totle_no, totle_split_agg_no = 0, 0

    rows = summary_csv_row_gen(summary_csv_file, max_cost_error_pct=MAX_COST_ERROR_PCT, max_tokens_error_pct=MAX_TOKENS_ERROR_PCT)
    for time, _, trade_size, token, agg, _, agg_split, _, _, no_split_pct_savings, totle_split, _, totle_split_pct_savings in rows:

        # Account for situations where DEX.AG knows Kyber is using Uniswap (or is excluding Uniswap reserve) and using Uniswap 100%
        # and simulated Totle is seeing great savings from a 50/50 split, but real Totle would do the same as DEX.AG
        # Totle saved: 21.932107231440355 Totle: {'Uniswap': 50, 'Kyber': 50} 	DEX.AG: {'Uniswap': 100}
        if totle_split == {'Uniswap': 50, 'Kyber': 50} and agg_split == {'Uniswap': 100}:
            # print(f"skipping Totle: {totle_split} {agg} {agg_split}")
            continue

        if abs(totle_split_pct_savings) > 10:
            print(f"{totle_split_pct_savings} vs {agg} {token} {trade_size} ")
            # if token == 'RLC':
            if agg == 'DEX.AG':
                print(f"    {time} {totle_split} vs {agg_split}")

        ###############################################################################################################

        # currently don't do anything with no_split_pct_savings, but it would be great to compare to totle_split_pct_savings
        if len(agg_split) > 1:
            per_token_splits_only_savings[token][trade_size][agg].append(totle_split_pct_savings)
            if len(totle_split) < 2: agg_split_totle_no +=1
        else:
            per_token_non_splits_only_savings[token][trade_size][agg].append(totle_split_pct_savings)
            if len(totle_split) > 1:
                # print(f"TOTLE SPLIT BUT NOT AGG: Totle: {totle_split} \t{agg}: {agg_split}")
                totle_split_agg_no +=1



        if totle_split_pct_savings < -200:
            print(f"BAD {time} {token} {trade_size} savings={totle_split_pct_savings:.2f} Totle: {totle_split} {agg} {agg_split}")

        row_count += 1
        # if row_count > 10:
        #     print(f"agg_split_totle_no={agg_split_totle_no}, totle_split_agg_no={totle_split_agg_no}")
        #     break

    return per_token_splits_only_savings, per_token_non_splits_only_savings

# get aggregated savings (over all tokens) by trade_size
def aggregated_savings(per_token_savings):
    """Aggregates savings over all tokens for each trade_size"""
    per_trade_size_savings = defaultdict(lambda: defaultdict(list))

    for token, trade_size, agg, totle_split_pct_savings_list in data_import.pct_savings_gen(per_token_savings):
        per_trade_size_savings[trade_size][agg] += totle_split_pct_savings_list

    return per_trade_size_savings

def print_split_vs_non_split_savings_summary_table_csv(csv_summary_file):
    per_token_splits_only_savings, per_token_non_splits_only_savings = get_per_token_savings(csv_summary_file)

    per_trade_size_splits_only = aggregated_savings(per_token_splits_only_savings)
    per_trade_size_non_splits_only = aggregated_savings(per_token_non_splits_only_savings)

    # print(f"per_trade_size_splits_only=\n{json.dumps(per_trade_size_splits_only, indent=3)}")
    # print(f"per_trade_size_non_splits_only=\n{json.dumps(per_trade_size_non_splits_only, indent=3)}")

    aggs = ['1-Inch', 'DEX.AG', 'Paraswap']
    print(f"Trade Size,{','.join(map(lambda x: f'{x} (non-split),{x} (splits-only)', aggs))}")

    for trade_size in [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0, 500.0]: # lifted from totle_vs_aggs.py
        non_splits = per_trade_size_non_splits_only.get(trade_size)
        splits_only = per_trade_size_splits_only.get(trade_size)

        row = f"{trade_size}"
        for agg in aggs:
            non_split_str = f"{compute_mean(non_splits[agg]):.2f}" if non_splits and non_splits.get(agg) else ''
            split_str = f"{compute_mean(splits_only[agg]):.2f}" if splits_only and splits_only.get(agg) else ''
            row += f",{non_split_str},{split_str}"

        print(row)

def print_dex_used_pcts(summary_csv_file, include_non_splits=False):
    rows_used, agg_dex_count = 0, defaultdict(lambda: defaultdict(int))
    rows = summary_csv_row_gen(summary_csv_file, max_cost_error_pct=MAX_COST_ERROR_PCT, max_tokens_error_pct=MAX_TOKENS_ERROR_PCT)
    for time, _, trade_size, token, agg, _, agg_split, _, _, no_split_pct_savings, totle_split, _, totle_split_pct_savings in rows:
        for dex in agg_split:
            if len(agg_split) > 1 or include_non_splits:
                rows_used += 1
                agg_dex_count[agg][dex] += 1
    print(f"Based on {rows_used} samples")
    for agg, dex_count in agg_dex_count.items():
        n_samples = sum(dex_count.values())
        dex_count_pct = {dex: round(100 * (count / n_samples), 1) for dex, count in dex_count.items()}
        print(f"{agg}: {dex_count_pct}")

def compute_mean(savings_list):
    if not savings_list: return None
    sum_savings, n_samples = sum(savings_list), len(savings_list)
    pct_savings = sum_savings / n_samples
    return pct_savings


########################################################################################################################

def main():
    # print_dex_used_pcts('outputs/summarized_totle_split_savings_2019-11-23_13:30:47.csv', include_non_splits=True)
    # exit(0)

    do_summary_file = True

    if do_summary_file:
        summary_csv_file = sys.argv[1] if len(sys.argv) > 1 else 'outputs/summarized_totle_split_savings_2019-11-24_13:30:22.csv'
        print_split_vs_non_split_savings_summary_table_csv(summary_csv_file)
    else:
        csv_files = tuple(sys.argv[1:])
        if len(csv_files) < 1:
            csv_files = glob.glob(f'outputs/totle_vs_agg_splits_*')
        print(f"processing {len(csv_files)} CSV files ...")

        filename = get_filename_base(prefix='summarized_totle_split_savings')
        with SavingsCSV(filename, fieldnames=CSV_FIELDS) as csv_writer:
            for csv_data in get_cost_comparisons(csv_files):
                csv_writer.append(csv_data)

if __name__ == "__main__":
    main()
