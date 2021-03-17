import glob
import os
import random
import time
from collections import defaultdict
import concurrent.futures

import json

import dexag_client
import exchange_utils
import oneinch_client
import oneinch_v2_client
import oneinch_v3_client
import paraswap_client
import split_utils
import token_utils
import zrx_client
import totle_client
from v2_compare_prices import get_savings, print_savings, get_filename_base, SavingsCSV


AGG_CLIENTS = [dexag_client, oneinch_client, oneinch_v2_client, oneinch_v3_client, paraswap_client, zrx_client]
CSV_FIELDS = "time id action trade_size token quote exchange exchange_price totle_used totle_price totle_splits pct_savings splits ex_prices".split()

def compare_totle_and_aggs_parallel(from_token, to_token, from_amount, usd_trade_size=None):
    agg_savings = {}

    totle_quote = totle_client.try_swap(totle_client.name(), from_token, to_token, params={'fromAmount': from_amount}, verbose=False, debug=False)
    if totle_quote:
        # print(f"SUCCESSFUL getting Totle API Quote buying {to_token} with {from_amount} {from_token}")
        futures_agg = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for agg_client in AGG_CLIENTS:
                future = executor.submit(agg_client.get_quote, from_token, to_token, from_amount=from_amount)
                futures_agg[future] = agg_client.name()

        for f in concurrent.futures.as_completed(futures_agg):
            agg_name = futures_agg[f]
            agg_quote = f.result()
            if agg_quote:
                # print(f"SUCCESSFUL getting {agg_name} quote for buying {to_token} with {from_amount} {from_token}")
                if agg_quote['price'] == 0:
                    print(f"DIVISION BY ZERO: {agg_name} buying {to_token} with {from_amount} {from_token} returned a price of {agg_quote['price']}")
                    continue
                savings = get_savings(agg_name, agg_quote['price'], totle_quote, to_token, usd_trade_size or from_amount, 'buy', agg_quote=agg_quote, quote_token=from_token, print_savings=False)
                print(f"Totle saved {savings['pct_savings']:.2f} percent vs {agg_name} buying {to_token} with {from_amount} {from_token} on {savings['totle_used']}")
                agg_savings[agg_name] = savings
            else:
                print(f"FAILED getting {agg_name} quote: had no price quote for buying {to_token} with {from_amount} {from_token}")

    else:
        print(f"FAILED getting Totle API Quote buying {to_token} with {from_amount} {from_token}")

    return agg_savings

def get_token_prices(tokens):
    cmc_data = json.load(open(f'data/cmc_tokens.json'))['data']
    usd_prices = {t['symbol']: float(t['quote']['USD']['price']) for t in cmc_data if t['symbol'] in tokens and t['platform']['token_address'] not in token_utils.ADDRESSES_TO_FILTER_OUT }

    # if 'WETH' in usd_prices and 'ETH' not in usd_prices: usd_prices['ETH'] = usd_prices['WETH']
    print(f"usd_prices={json.dumps(usd_prices, indent=3)}")

    skipped_tokens, missing_tokens = set(), set(tokens) - set(usd_prices)
    print(f"CMC had prices for {len(usd_prices)}/{len(tokens)} tokens.")
    if len(missing_tokens) > 0:
        print(f"Querying Totle for prices on the remaining {len(missing_tokens)} tokens ({missing_tokens})")
        for missing_token in missing_tokens:
            totle_quote = totle_client.try_swap(totle_client.name(), 'USDC', missing_token, params={'fromAmount': 1}, verbose=False, debug=False)

            if totle_quote:  # set the from_amount so it's roughly the same across all swaps
                print(f"totle_quote for {missing_token} = {totle_quote['price']}")
                usd_prices[missing_token] = totle_quote['price']
            else:
                # If we can't get a price from CMC or Totle, then just discard this token. Other aggs may have the pair, but if you can't
                # buy it for ETH on Totle, then it is essentially not a "tradable" token as curated by Totle, and thus not in this study.
                skipped_tokens.add(missing_token)

    if any(skipped_tokens):
        raise ValueError(f"Skipping {skipped_tokens} because we couldn't get a price from CMC or Totle")
    return usd_prices

# From
# ['USDT > ETH', 'ETH > USDT', 'WETH > ETH', 'ETH > WETH', 'USDC > ETH', 'USDT > WBTC', 'ETH > USDC', 'USDT > USDC', 'DAI > ETH', 'UNI > ETH', 'USDC > WBTC', 'ETH > DAI', 'WBTC > ETH', 'USDC > USDT']
METAMASK_TOP_PAIRS = [('ETH', 'USDT'), ('USDT', 'ETH'), ('ETH', 'WETH'), ('WETH', 'ETH'), ('ETH', 'USDC'), ('WBTC', 'USDT'), ('USDC', 'ETH'), ('USDC', 'USDT'), ('ETH', 'DAI'), ('ETH', 'UNI'), ('WBTC', 'USDC'), ('DAI', 'ETH'), ('ETH', 'WBTC'), ('USDT', 'USDC')]

USD_TRADE_SIZES = [1000.0, 5000.0, 10000.0, 50000.0, 100000.0, 500000.0, 1000000.0]

def do_metamask_top_pairs():
    all_buy_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(dict))) # extra lambda prevents KeyError in print_savings
    order_type = 'buy'

    metamask_top_tokens = set()
    for p in METAMASK_TOP_PAIRS: metamask_top_tokens |= set(p)

    usd_prices = get_token_prices(metamask_top_tokens)

    filename = get_filename_base(prefix='totle_vs_agg_metamask_top_pairs', suffix=order_type)
    with SavingsCSV(filename, fieldnames=CSV_FIELDS) as csv_writer:
        for pair in METAMASK_TOP_PAIRS: # these were recorded as (base,quote) i.e. (to_token, from_token)
            to_token, from_token = pair
            for usd_trade_size in USD_TRADE_SIZES:
                # set the from_amount so it's roughly the same ($10 USD) across all swaps
                from_amount = usd_trade_size / usd_prices[from_token]

                agg_savings = compare_totle_and_aggs_parallel(from_token, to_token, from_amount, usd_trade_size)
                for agg_name, savings in agg_savings.items():
                    all_buy_savings[agg_name][pair][usd_trade_size] = savings
                    print(f"WRITING savings to CSV ...")
                    csv_writer.append(savings)
                    print(f"\n\nBuying {to_token} for {from_amount} {from_token} usd_trade_size=${usd_trade_size:.2f} (which is {from_amount:.4f} {from_token} at a price of ${usd_prices[from_token]:.2f})")

                    for agg_name, savings in agg_savings.items():
                        all_buy_savings[agg_name][from_token][usd_trade_size] = savings
                        csv_writer.append(savings)

    # print(json.dumps(all_buy_savings, indent=3))

    # Prints a savings dict, token => trade_size => savings values
    for agg_name in all_buy_savings:
        print_savings(order_type, all_buy_savings[agg_name], USD_TRADE_SIZES, title=f"Savings vs. {agg_name}")

#######################################################################################################################
TOKENS = ['UNI', 'YFI', 'LINK', 'WBTC', 'COMP', 'BAL', 'REP', 'AMPL', 'KNC', 'UMA', 'LEND', 'SNX', 'USDT', 'USDC', 'DAI']
ADDITIONAL_TOP_DUNE_TOKENS = ['USDT', 'USDC', 'CORE', 'DAI', 'ANATHA', 'POLS', 'XFI', 'BID']

ROWAN_SPLIT_FRIENDLY = ['DAI', 'USDC', 'USDT', 'WBTC', 'UMA', 'renBTC', 'SNX', 'MKR', 'RSR', 'CRV', 'LINK', 'COMP', 'YFI', 'AAVE', 'UNI', 'AMPL', 'ESD',]  # + 'USDC/DAI'
GANG_OF_FOUR = ['BAL', 'KNC', 'LEND', 'REPV2']


tokens = ROWAN_SPLIT_FRIENDLY + GANG_OF_FOUR
random.shuffle(tokens)
TRADE_SIZES  = [20.0, 30.0, 40.0, 50.0, 100.0, 200.0, 300.0, 400.0, 500.0, 1000.0, 1500.0, 2000.0, 2500.0]

def do_eth_pairs_parallel():
    all_buy_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(dict))) # extra lambda prevents KeyError in print_savings
    order_type, quote = 'buy', 'ETH'
    filename = get_filename_base(prefix='totle_vs_agg_eth_pairs', suffix=order_type)
    with SavingsCSV(filename, fieldnames=CSV_FIELDS) as csv_writer:
        todo = []

        for base in tokens:
            for trade_size in TRADE_SIZES:
                todo.append((compare_totle_and_aggs_parallel, quote, base, trade_size))

        MAX_THREADS = 1
        print(f"Queueing up {len(todo)} todos ({len(tokens)} tokens x {len(TRADE_SIZES)} trade sizes) for execution on {MAX_THREADS} workers")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures_p = {executor.submit(*p): p for p in todo}

            for f in concurrent.futures.as_completed(futures_p):
                _, quote, base, trade_size = futures_p[f]
                agg_savings = f.result()
                for agg_name, savings in agg_savings.items():
                    all_buy_savings[agg_name][base][trade_size] = savings
                    print(f"WRITING savings to CSV ...")
                    csv_writer.append(savings)

    # print(json.dumps(all_buy_savings, indent=3))

    # Prints a savings dict, token => trade_size => savings values
    for agg_name in all_buy_savings:
        print_savings(order_type, all_buy_savings[agg_name], TRADE_SIZES, title=f"Savings vs. {agg_name}")

    print("\n\n")
    for agg_name in all_buy_savings:
        print(f"{agg_name} {list(all_buy_savings[agg_name].keys())}")


def do_eth_pairs():
    all_buy_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(dict))) # extra lambda prevents KeyError in print_savings
    order_type, quote = 'buy', 'ETH'
    filename = get_filename_base(prefix='totle_vs_agg_eth_pairs', suffix=order_type)
    with SavingsCSV(filename, fieldnames=CSV_FIELDS) as csv_writer:
        for base in tokens:
            for trade_size in TRADE_SIZES:
                agg_savings = compare_totle_and_aggs_parallel(quote, base, trade_size)
                for agg_name, savings in agg_savings.items():
                    all_buy_savings[agg_name][base][trade_size] = savings
                    print(f"WRITING savings to CSV ...")
                    csv_writer.append(savings)

    # Prints a savings dict, token => trade_size => savings values
    for agg_name in all_buy_savings:
        print_savings(order_type, all_buy_savings[agg_name], TRADE_SIZES, title=f"Savings vs. {agg_name}")

    print("\n\n")
    for agg_name in all_buy_savings:
        print(f"{agg_name} {list(all_buy_savings[agg_name].keys())}")

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

    do_metamask_top_pairs()
    # do_eth_pairs()

if __name__ == "__main__":
    main()
