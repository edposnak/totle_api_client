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

def compare_totle_and_aggs(agg_clients, from_token, to_token, from_amount):
    agg_savings = {}

    totle_sd = v2_client.try_swap(v2_client.name(), from_token, to_token, params={'fromAmount': from_amount}, verbose=False, debug=False)
    if totle_sd:
        futures_agg = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for agg_client in agg_clients:
                future = executor.submit(agg_client.get_quote, from_token, to_token, from_amount=from_amount)
                futures_agg[future] = agg_client.name()

        for f in concurrent.futures.as_completed(futures_agg):
            agg_name = futures_agg[f]
            pq = f.result()
            if pq:
                splits = exchange_utils.canonical_keys(pq['exchanges_parts'])
                ex_prices = pq.get('exchanges_prices') and exchange_utils.canonical_and_splittable(pq['exchanges_prices'])
                savings = get_savings(agg_name, pq['price'], totle_sd, to_token, from_amount, 'buy', splits=splits, ex_prices=ex_prices, print_savings=False)
                savings['quote'] = from_token # TODO: add this to get_savings
                print(f"Totle saved {savings['pct_savings']:.2f} percent vs {agg_name} buying {to_token} with {from_amount} {from_token} on {','.join(savings['totle_used'])}")

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


def parse_csv(filename):
    agg_pairs = defaultdict(list)
    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=None)
        for row in reader:
            trade_size, token, quote = row['trade_size'], row['token'], row['quote']
            exchange, exchange_price = row['exchange'], float(row['exchange_price'])
            agg_pairs[exchange].append((token, quote))
    return agg_pairs


AGG_CLIENTS = [dexag_client, oneinch_client, paraswap_client]
CSV_FIELDS = "time action trade_size token quote exchange exchange_price totle_used totle_price pct_savings splits ex_prices".split()

OVERLAP_PAIRS = [('USDC', 'REQ'), ('REP', 'SNT'), ('GNO', 'RCN'), ('OMG', 'ANT'), ('POWR', 'ENJ'), ('RDN', 'MKR'), ('KNC', 'REQ'), ('USDC', 'OMG'), ('GNO', 'BNT'), ('OMG', 'ZRX'), ('REP', 'MANA'), ('KNC', 'RCN'), ('USDC', 'TUSD'),
                 ('ZRX', 'KNC'), ('USDT', 'REN'), ('ANT', 'REQ'), ('ZRX', 'GNO'), ('POE', 'TUSD'), ('MKR', 'ENJ'), ('PAX', 'REP'), ('TKN', 'DAI'), ('MKR', 'RDN'), ('USDT', 'TUSD'), ('MANA', 'ETH'), ('LINK', 'RCN'), ('ENJ', 'KNC'),
                 ('ENJ', 'REQ'), ('RDN', 'ETH'), ('USDC', 'BAT'), ('MANA', 'ANT'), ('RLC', 'GNO'), ('TKN', 'XDCE'), ('REN', 'RCN'), ('ENJ', 'BNT'), ('MKR', 'RCN'), ('BAT', 'ZRX'), ('TUSD', 'REN'), ('ANT', 'DAI'), ('ANT', 'KNC'),
                 ('REP', 'REN'), ('PAX', 'ANT'), ('OMG', 'RCN'), ('RLC', 'RDN'), ('KNC', 'REN'), ('POE', 'LINK'), ('WBTC', 'DAI'), ('REN', 'PAX'), ('USDT', 'PAX'), ('ENJ', 'PAX'), ('RLC', 'BNT'), ('BNT', 'TUSD'), ('PAX', 'GNO'),
                 ('MANA', 'RCN'), ('REQ', 'RDN'), ('PAX', 'KNC'), ('LINK', 'RDN'), ('LINK', 'PAX'), ('CVC', 'DAI'), ('MANA', 'BNT'), ('BAT', 'REQ'), ('USDC', 'KNC'), ('ZRX', 'REN'), ('REQ', 'ENJ'), ('TKN', 'TUSD'), ('ANT', 'PAX'),
                 ('RCN', 'BNT'), ('USDC', 'GNO'), ('PAX', 'RDN'), ('SNT', 'ANT'), ('OMG', 'ETH'), ('POE', 'PAX'), ('RDN', 'OMG'), ('OMG', 'RDN'), ('SNT', 'BNT'), ('KNC', 'PAX'), ('TKN', 'ETH'), ('POWR', 'SNT'), ('ZRX', 'ANT'),
                 ('POWR', 'KNC'), ('MKR', 'TUSD'), ('REP', 'ENJ'), ('RLC', 'REN'), ('USDC', 'PAX'), ('TKN', 'PAX'), ('GNO', 'REP'), ('SNT', 'MKR'), ('TUSD', 'GNO'), ('SNT', 'RDN'), ('RCN', 'LINK'), ('OMG', 'KNC'), ('KNC', 'ANT'),
                 ('OMG', 'GNO'), ('POE', 'DAI'), ('SNT', 'REQ'), ('RDN', 'ZRX'), ('TUSD', 'ANT'), ('MANA', 'REQ'), ('USDT', 'LINK'), ('USDC', 'ETH'), ('MKR', 'LINK'), ('ENJ', 'MANA'), ('BAT', 'RDN'), ('PAX', 'TUSD'), ('BAT', 'ETH'),
                 ('POE', 'REN'), ('BAT', 'RCN'), ('TKN', 'RDN'), ('MTL', 'GNO'), ('MTL', 'XDCE'), ('MTL', 'KNC'), ('RCN', 'TUSD'), ('KNC', 'RDN'), ('OMG', 'MANA'), ('WBTC', 'REN'), ('POWR', 'BNT'), ('ANT', 'ETH'), ('MKR', 'BAT'),
                 ('ZRX', 'RCN'), ('LINK', 'MKR'), ('SNT', 'XDCE'), ('GNO', 'ENJ'), ('USDC', 'DAI'), ('RCN', 'RDN'), ('CVC', 'SNT'), ('GNO', 'REN'), ('REN', 'RDN'), ('POWR', 'TUSD'), ('BAT', 'TUSD'), ('RCN', 'DAI'), ('RCN', 'ENJ'),
                 ('USDT', 'KNC'), ('POWR', 'OMG'), ('OMG', 'REN'), ('CVC', 'RCN'), ('BAT', 'REN'), ('MKR', 'OMG'), ('POWR', 'REQ'), ('ZRX', 'SNT'), ('USDT', 'ETH'), ('ZRX', 'RDN'), ('POLY', 'ETH'), ('GNO', 'MKR'), ('MKR', 'PAX'),
                 ('LINK', 'REN'), ('REP', 'GNO'), ('ENJ', 'DAI'), ('RDN', 'PAX'), ('REP', 'KNC'), ('POWR', 'LINK'), ('BAT', 'SNT'), ('REQ', 'RCN'), ('ENJ', 'XDCE'), ('REN', 'GNO'), ('KNC', 'BNT'), ('MKR', 'ZRX'), ('TUSD', 'ETH'),
                 ('POWR', 'WBTC'), ('ANT', 'XDCE'), ('POE', 'REP'), ('ENJ', 'REN'), ('USDT', 'BNT'), ('POWR', 'MTL'), ('SNT', 'OMG'), ('OMG', 'BNT'), ('MTL', 'RDN'), ('REQ', 'TUSD'), ('REN', 'ANT'), ('MTL', 'ETH'), ('KNC', 'DAI'),
                 ('MKR', 'REN'), ('BAT', 'GNO'), ('GNO', 'LINK'), ('KNC', 'XDCE'), ('ENJ', 'TUSD'), ('RLC', 'OMG'), ('MTL', 'ENJ'), ('POWR', 'RCN'), ('ANT', 'REN'), ('REP', 'DAI'), ('GNO', 'PAX'), ('BAT', 'KNC'), ('KNC', 'GNO'),
                 ('OMG', 'REQ'), ('XDCE', 'ETH'), ('ZRX', 'MANA'), ('OMG', 'REP'), ('RCN', 'ANT'), ('RCN', 'REQ'), ('MKR', 'KNC'), ('MKR', 'XDCE'), ('POWR', 'RDN'), ('LINK', 'DAI'), ('TUSD', 'PAX'), ('MKR', 'GNO'), ('CVC', 'PAX'),
                 ('RDN', 'DAI'), ('PAX', 'OMG'), ('RDN', 'KNC'), ('RDN', 'XDCE'), ('GNO', 'POLY'), ('REP', 'TUSD'), ('REN', 'DAI'), ('ENJ', 'ETH'), ('RLC', 'DAI'), ('USDC', 'MANA'), ('MKR', 'DAI'), ('MANA', 'SNT'), ('KNC', 'TUSD'),
                 ('LINK', 'BAT'), ('USDT', 'DAI'), ('POLY', 'RDN'), ('OMG', 'DAI'), ('BNT', 'REN'), ('DAI', 'ETH'), ('ANT', 'ENJ'), ('OMG', 'SNT'), ('PAX', 'ETH'), ('REP', 'REQ'), ('ZRX', 'LINK'), ('MKR', 'SNT'), ('OMG', 'TUSD'),
                 ('KNC', 'MANA'), ('ANT', 'BNT'), ('POWR', 'XDCE'), ('RDN', 'SNT'), ('LINK', 'SNT'), ('BNT', 'DAI'), ('REQ', 'DAI'), ('USDT', 'MANA'), ('RCN', 'GNO'), ('CVC', 'MKR'), ('ANT', 'ZRX'), ('RLC', 'REQ'), ('TUSD', 'RCN'),
                 ('RLC', 'ENJ'), ('GNO', 'OMG'), ('CVC', 'KNC'), ('SNT', 'ETH'), ('BAT', 'ANT'), ('MKR', 'REP'), ('RDN', 'REN'), ('PAX', 'BNT'), ('REN', 'BNT'), ('KNC', 'SNT'), ('USDT', 'ZRX'), ('ZRX', 'BNT'), ('POWR', 'TKN'),
                 ('GNO', 'REQ'), ('POWR', 'ZRX'), ('GNO', 'ANT'), ('GNO', 'XDCE'), ('GNO', 'SNT'), ('REP', 'RCN'), ('POWR', 'DAI'), ('ANT', 'OMG'), ('RDN', 'BNT'), ('OMG', 'ENJ'), ('USDC', 'REN'), ('POWR', 'ANT'), ('GNO', 'ZRX'),
                 ('USDC', 'BNT'), ('ZRX', 'REP'), ('LINK', 'OMG'), ('ANT', 'TUSD'), ('MKR', 'MANA'), ('BAT', 'BNT'), ('LINK', 'ETH'), ('POWR', 'REN'), ('ANT', 'RCN'), ('USDC', 'ANT'), ('ENJ', 'SNT'), ('BNT', 'PAX'), ('USDT', 'OMG'),
                 ('CVC', 'GNO'), ('RLC', 'XDCE'), ('CVC', 'ANT'), ('REQ', 'PAX'), ('MTL', 'RCN'), ('USDC', 'ZRX'), ('CVC', 'REQ'), ('REN', 'ETH'), ('BAT', 'REP'), ('RLC', 'RCN'), ('PAX', 'DAI'), ('RCN', 'PAX'), ('MTL', 'REQ'),
                 ('CVC', 'BNT'), ('MANA', 'DAI'), ('ZRX', 'DAI'), ('POWR', 'MKR'), ('LINK', 'GNO'), ('RDN', 'ANT'), ('OMG', 'PAX'), ('OMG', 'LINK'), ('GNO', 'KNC'), ('USDT', 'BAT'), ('TUSD', 'REP'), ('ZRX', 'TUSD'), ('CVC', 'REP'),
                 ('PAX', 'SNT'), ('GNO', 'ETH'), ('ANT', 'RDN'), ('TKN', 'REN'), ('CVC', 'RDN'), ('REP', 'OMG'), ('REQ', 'ETH'), ('POWR', 'PAX'), ('RLC', 'ANT'), ('USDT', 'ENJ'), ('USDC', 'SNT'), ('RLC', 'ZRX'), ('ENJ', 'GNO'),
                 ('SNT', 'DAI'), ('REN', 'MANA'), ('RLC', 'KNC'), ('BAT', 'OMG'), ('SNT', 'REN'), ('TUSD', 'DAI'), ('LINK', 'MANA'), ('POWR', 'GNO'), ('ANT', 'GNO'), ('REP', 'LINK'), ('GNO', 'DAI'), ('LINK', 'KNC'), ('RDN', 'REQ'),
                 ('SNT', 'TUSD'), ('GNO', 'RDN'), ('KNC', 'LINK'), ('KNC', 'ETH'), ('MANA', 'LINK'), ('MANA', 'GNO'), ('MKR', 'REQ'), ('MKR', 'BNT'), ('BAT', 'MANA'), ('BAT', 'XDCE'), ('MANA', 'XDCE'), ('BAT', 'DAI'), ('TUSD', 'OMG'),
                 ('ZRX', 'ENJ'), ('OMG', 'XDCE'), ('ANT', 'LINK'), ('PAX', 'REN'), ('REP', 'ANT'), ('USDC', 'RDN'), ('RCN', 'REN'), ('MTL', 'BNT'), ('REP', 'BNT'), ('USDT', 'REP'), ('MANA', 'OMG'), ('ENJ', 'LINK'), ('USDC', 'RCN'),
                 ('RCN', 'KNC'), ('RLC', 'ETH'), ('LINK', 'REP'), ('MKR', 'ANT'), ('ZRX', 'OMG'), ('GNO', 'TUSD'), ('PAX', 'RCN'), ('ANT', 'REP'), ('CVC', 'ZRX'), ('REP', 'RDN'), ('MANA', 'RDN'), ('ENJ', 'ANT'), ('ZRX', 'PAX'),
                 ('RCN', 'ETH'), ('USDC', 'WBTC'), ('USDT', 'SNT'), ('RLC', 'SNT'), ('LINK', 'BNT'), ('BAT', 'PAX'), ('MANA', 'MKR'), ('USDC', 'REP'), ('REQ', 'XDCE'), ('ENJ', 'RCN'), ('LINK', 'ANT'), ('SNT', 'RCN'), ('CVC', 'OMG'),
                 ('ENJ', 'RDN'), ('LINK', 'TUSD'), ('POLY', 'DAI'), ('USDT', 'RDN'), ('RLC', 'MANA'), ('BNT', 'ETH'), ('RCN', 'XDCE'), ('CVC', 'ETH'), ('REN', 'REQ'), ('LINK', 'ZRX'), ('USDT', 'REQ')]

OVERLAP_PAIRS = [('USDC', 'REQ'), ('REP', 'SNT')]
USD_TRADE_SIZES = [1.0, 5.0, 10.0, 50.0, 100.0, 500.0, 1000.0]
USD_TRADE_SIZES = [1.0, 5.0, 10.0]

def do_overlap_pairs():
    all_buy_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(dict))) # extra lambda prevents KeyError in print_savings
    order_type = 'buy'

    overlap_tokens = set()
    for p in OVERLAP_PAIRS: overlap_tokens |= set(p)
    usd_prices = get_token_prices(overlap_tokens)

    filename = get_filename_base(prefix='totle_vs_agg_overlap_pairs', suffix=order_type)
    with SavingsCSV(filename, fieldnames=CSV_FIELDS) as csv_writer:
        for from_token, to_token in OVERLAP_PAIRS:
            for usd_trade_size in USD_TRADE_SIZES:
                # set the from_amount so it's roughly the same ($10 USD) across all swaps
                from_amount = usd_trade_size / usd_prices[from_token]
                print(f"\n\nBuying {to_token} for {from_amount} {from_token} trade_size=${usd_trade_size:.2f} (which is {from_amount} {from_token} at a price of ${usd_prices[from_token]:.2f})")
                agg_savings = compare_totle_and_aggs(AGG_CLIENTS, from_token, to_token, from_amount)
                for agg_name, savings in agg_savings.items():
                    all_buy_savings[agg_name][from_token][usd_trade_size] = savings
                    csv_writer.append(savings)

    # print(json.dumps(all_buy_savings, indent=3))

    # Prints a savings dict, token => trade_size => savings values
    for agg_name in all_buy_savings:
        print_savings(order_type, all_buy_savings[agg_name], USD_TRADE_SIZES, title=f"Savings vs. {agg_name}")


TOTLE_39 = ['ANT','AST','BAT','BNT','CDT','CND','CVC','DAI','ENG','ENJ','ETHOS','GNO','KNC','LINK','MANA','MCO','MKR','OMG','PAX','PAY','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','STORJ','TKN','TUSD','USDC','USDT','WBTC','ZRX']
HI_SPLIT_TOKENS = ['BAT', 'ENJ', 'GNO', 'KNC', 'MANA', 'OMG', 'POE', 'POWR', 'RCN', 'RDN', 'REN', 'REP', 'REQ', 'RLC', 'SNT']
STABLECOINS = ['CUSDC', 'DAI', 'PAX', 'SAI', 'TUSD', 'USDC', 'USDT']
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
                agg_savings = compare_totle_and_aggs(AGG_CLIENTS, quote, base, trade_size)
                for agg_name, savings in agg_savings.items():
                    all_buy_savings[agg_name][quote][trade_size] = savings
                    csv_writer.append(savings)

    # print(json.dumps(all_buy_savings, indent=3))

    # Prints a savings dict, token => trade_size => savings values
    for agg_name in all_buy_savings:
        print_savings(order_type, all_buy_savings[agg_name], USD_TRADE_SIZES, title=f"Savings vs. {agg_name}")


########################################################################################################################
def main():
    working_dir = os.path.dirname(__file__)
    if working_dir: os.chdir(working_dir)

    do_overlap_pairs()
    # do_eth_pairs()

if __name__ == "__main__":
    main()
