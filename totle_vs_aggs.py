import csv
import json
import os
from collections import defaultdict
import concurrent.futures
from itertools import permutations

import dexag_client
import exchange_utils
import oneinch_client
import paraswap_client
import v2_client
from v2_compare_prices import get_savings, print_savings, get_filename_base, SavingsCSV

def compare_totle_and_aggs(agg_clients, base, quote, trade_size, order_type='buy'):
    agg_savings = {}

    if order_type == 'buy':
        from_token, to_token, params = quote, base, {'fromAmount': trade_size}
    else:
        from_token, to_token, params = base, quote, {'toAmount': trade_size}

    totle_sd = v2_client.try_swap(v2_client.name(), from_token, to_token, params=params, verbose=False, debug=True)
    if totle_sd:
        futures_agg = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for agg_client in agg_clients:
                future = executor.submit(agg_client.get_quote, from_token, to_token, from_amount=trade_size)
                futures_agg[future] = agg_client.name()

        for f in concurrent.futures.as_completed(futures_agg):
            agg_name = futures_agg[f]
            pq = f.result()
            if pq:
                splits = exchange_utils.canonical_keys(pq['exchanges_parts'])
                ex_prices = pq.get('exchanges_prices') and exchange_utils.canonical_and_splittable(pq['exchanges_prices'])
                savings = get_savings(agg_name, pq['price'], totle_sd, base, trade_size, order_type, splits=splits, ex_prices=ex_prices, print_savings=False)
                savings['quote'] = quote # TODO: add this to get_savings
                print(f"Totle saved {savings['pct_savings']:.2f} percent vs {agg_name} {order_type}ing {base}/{quote} on {','.join(savings['totle_used'])}")

                agg_savings[agg_name] = savings
            else:
                print(f"{agg_name} had no price quote for {order_type} {base} / {trade_size} {quote}")
    return agg_savings

def parse_csv(filename):
    agg_pairs = defaultdict(list)
    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=None)
        for row in reader:
            trade_size, token, quote = row['trade_size'], row['token'], row['quote']
            exchange, exchange_price = row['exchange'], float(row['exchange_price'])
            agg_pairs[exchange].append((token, quote))
    return agg_pairs

########################################################################################################################
def main():
    working_dir = os.path.dirname(__file__)
    if working_dir: os.chdir(working_dir)

    quote='ETH'
    order_type = 'buy'

    AGG_CLIENTS = [dexag_client, oneinch_client, paraswap_client]
    all_buy_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(dict))) # extra lambda prevents KeyError in print_savings

    TOTLE_39 = ['ANT','AST','BAT','BNT','CDT','CND','CVC','DAI','ENG','ENJ','ETHOS','GNO','KNC','LINK','MANA','MCO','MKR','OMG','PAX','PAY','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','STORJ','TKN','TUSD','USDC','USDT','WBTC','ZRX']
    HI_SPLIT_TOKENS = ['BAT', 'ENJ', 'GNO', 'KNC', 'MANA', 'OMG', 'POE', 'POWR', 'RCN', 'RDN', 'REN', 'REP', 'REQ', 'RLC', 'SNT']

    STABLECOINS = ['CUSDC', 'DAI', 'PAX', 'SAI', 'TUSD', 'USDC', 'USDT']
    UNSUPPORTED_STABLECOINS = ['CSAI', 'IDAI']
    TOKENS = HI_SPLIT_TOKENS

    TRADE_SIZES  = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0, 500.0]
    # TOKENS, TRADE_SIZES = ['CVC', 'DAI', 'LINK'], [0.5, 5.0]

    CSV_FIELDS = "time action trade_size token quote exchange exchange_price totle_used totle_price pct_savings splits ex_prices".split()

    filename = get_filename_base(prefix='totle_vs_agg_stablecoins', suffix=order_type)
    with SavingsCSV(filename, fieldnames=CSV_FIELDS) as csv_writer:
        # for base, quote in permutations(STABLECOINS, 2):
            # for trade_size in [1.0, 10.0]:
        for base in TOKENS:
            for trade_size in TRADE_SIZES:
                print(f"Doing {base} for {trade_size} {quote}")
                agg_savings = compare_totle_and_aggs(AGG_CLIENTS, base, quote, trade_size, order_type)
                for agg_name, savings in agg_savings.items():
                    all_buy_savings[agg_name][base][trade_size] = savings
                    csv_writer.append(savings)

    # print(json.dumps(all_buy_savings, indent=3))

    # Prints a savings dict, token => trade_size => savings values
    for agg_name in all_buy_savings:
        print_savings(order_type, all_buy_savings[agg_name], TRADE_SIZES, title=f"Savings vs. {agg_name}")


if __name__ == "__main__":
    main()
