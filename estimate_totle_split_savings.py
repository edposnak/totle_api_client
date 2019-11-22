import sys
import glob
import functools
from collections import defaultdict
from datetime import datetime

import dexag_client
import data_import
import slippage_curves
from v2_compare_prices import get_pct_savings, get_filename_base, SavingsCSV


def get_cost_comparisons(csv_files):
    """Yields cost comparison data"""
    for csv_file in csv_files:
        price_estimators = get_price_estimators(csv_file)
        if not price_estimators:
            print(f"Skipping {csv_file} because it had no price data from which to create slippage curves")
            continue

        # Compare only splits
        for time, action, trade_size, token, agg, agg_price, no_split_totle_used, no_split_totle_price, no_split_pct_savings, agg_split, ex_prices in data_import.csv_row_gen(csv_file, only_splits=True):
            estimator = price_estimators.get(token)
            if not estimator:
                print(f"\n\nskipping {agg} {action} {token} for {trade_size} ETH because no price estimator exists for {token}")
                continue

            totle_solution = slippage_curves.branch_and_bound_solutions(trade_size, estimator,
                                                                        exclude_dexs=['Radar Relay'])
            est_totle_dest_amount = estimator.destination_amount(totle_solution, infinite_liquidity=True)
            if est_totle_dest_amount == 0:  # Cannot estimate price (have only 1 data point)
                print(
                    f"\n\nskipping {agg} {action} {token} for {trade_size} ETH because price estimator exists for {token} has insufficient data")
                continue
            est_totle_split_price = trade_size / est_totle_dest_amount

            actual_agg_dest_amount = trade_size / agg_price
            est_totle_dest_amount *= 0.9975  # subtract Totle's .25% fee, which is taken from dest tokens
            totle_split_price = trade_size / est_totle_dest_amount
            cost_overestimate_pct, tokens_overestimate_pct = get_overestimate_pcts(actual_agg_dest_amount, estimator,
                                                                                   trade_size, agg_price, agg_split)
            totle_split_pct_savings = get_pct_savings(actual_agg_dest_amount, est_totle_dest_amount)
            totle_split = slippage_curves.to_percentages(totle_solution)

            print(f"\n\n{agg} {action} {token} for {trade_size} ETH agg_price={agg_price:.6f} totle_price={no_split_totle_price:.6f} pct_savings={no_split_pct_savings:.2f}")
            print(f"Totle  split={totle_split} est. price={est_totle_split_price} est. amount={est_totle_dest_amount}")
            print(f"{agg[:6]:6} split={agg_split} actual price={agg_price:.6f} actual amount={actual_agg_dest_amount}")
            print(f"Totle non-split pct_savings={no_split_pct_savings:.2f} Totle split pct_savings={totle_split_pct_savings :.2f}")
            yield {
                'time': datetime.now().isoformat(),
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
                'totle_split_price': totle_split_price,
                'totle_split_pct_savings': totle_split_pct_savings,
                'cost_overestimate_pct': cost_overestimate_pct,
                'tokens_overestimate_pct': tokens_overestimate_pct,
            }

def get_price_estimators(csv_file):
    tok_ex_ts_prices = get_all_prices(csv_file)
    price_estimators = {token1: slippage_curves.PriceEstimator(token1, prices) for token1, prices in tok_ex_ts_prices.items()}

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
def get_all_prices(csv_file):
    tok_ex_ts_prices = defaultdict(lambda: defaultdict(dict))
    # Use splits and non-splits to get price data
    for time, action, trade_size, token, agg, agg_price, totle_used, totle_price, pct_savings, splits, ex_prices in data_import.csv_row_gen(csv_file):
        # print(action, trade_size, token, agg, agg_price, totle_used, totle_price, pct_savings)
        if ex_prices and agg == dexag_client.name():  # only use DEX.AG ex_prices data
            for ex, price in ex_prices.items():
                tok_ex_ts_prices[token][ex][trade_size] = price
    return tok_ex_ts_prices


def get_overestimate_pcts(actual_agg_dest_amount, estimator, trade_size, agg_price, agg_split):
    # we don't have price curves for AirSwap or Oasis so we can't get est_agg_solution_cost to compare
    if 'AirSwap' in agg_split or 'Oasis' in agg_split:
        return 999999999, 999999999
    actual_agg_solution_cost = trade_size * (agg_price - estimator.base_price) / estimator.base_price
    agg_solution = slippage_curves.to_trade_size_allocations(agg_split, trade_size)
    est_agg_dest_amount = estimator.destination_amount(agg_solution, infinite_liquidity=True)
    est_agg_solution_cost = estimator.solution_cost(agg_solution, infinite_liquidity=True)

    # This is to ensure that the prices and slippage curves we're using are reasonably close
    cost_overestimate = est_agg_solution_cost - actual_agg_solution_cost
    cost_overestimate_pct = round(100 * cost_overestimate / actual_agg_solution_cost, 1)
    if abs(cost_overestimate_pct) > 25:
        print(f"COST OVERESTIMATE: {cost_overestimate_pct}% actual_agg_solution_cost={actual_agg_solution_cost:.8f} est_agg_solution_cost={est_agg_solution_cost:.8f}")

    # This is to ensure that the estimated amounts used to calculate pct_savings are very accurate
    tokens_overestimate = est_agg_dest_amount - actual_agg_dest_amount
    tokens_overestimate_pct = round(100 * tokens_overestimate / actual_agg_dest_amount, 1)
    # print(f"overestimated tokens acquire by {tokens_overestimate:.1f} tokens out of {actual_agg_dest_amount:.1f} ({tokens_overestimate_pct:.2f}%)")
    if abs(tokens_overestimate_pct) > 1:
        print(f"TOKENS OVERESTIMATE: {tokens_overestimate_pct}% actual amount={actual_agg_dest_amount:.1f} est. amount={est_agg_dest_amount:.1f}")

    return cost_overestimate_pct, tokens_overestimate_pct

########################################################################################################################

def main():
    csv_files = tuple(sys.argv[1:])
    if len(csv_files) < 1:
        csv_files = glob.glob(f'../outputs/totle_vs_agg_splits_*')

    print(f"processing {len(csv_files)} CSV files ...")

    CSV_FIELDS = "time action trade_size token agg agg_price agg_split no_split_totle_used no_split_totle_price no_split_pct_savings totle_split totle_split_price totle_split_pct_savings cost_overestimate_pct tokens_overestimate_pct".split()

    filename = get_filename_base(prefix='summarized_totle_split_savings')
    with SavingsCSV(filename, fieldnames=CSV_FIELDS) as csv_writer:
        for csv_data in get_cost_comparisons(csv_files):
            csv_writer.append(csv_data)

if __name__ == "__main__":
    main()
