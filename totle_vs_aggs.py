import os
from collections import defaultdict
import concurrent.futures

import dexag_client
import exchange_utils
import oneinch_client
import paraswap_client
import v2_client
from v2_compare_prices import savings_data, print_savings, get_filename_base, SavingsCSV

def compare_totle_and_aggs(agg_clients, base, quote, trade_size, order_type='buy'):
    agg_savings = {}
    from_token, to_token = quote, base
    # this hardcodes sourceAmount=trade_size because from_token (AKA quote) is ETH
    params = {'orderType': order_type, 'tradeSize': trade_size}
    totle_sd = v2_client.try_swap(v2_client.name(), from_token, to_token, params=params, verbose=False)
    if totle_sd:
        totle_price = totle_sd['price']
        totle_used = totle_sd['totleUsed']

        futures_agg = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for agg_client in agg_clients:
                future = executor.submit(agg_client.get_quote, from_token, to_token, from_amount=trade_size)
                futures_agg[future] = agg_client.name()

        for f in concurrent.futures.as_completed(futures_agg):
            agg_name = futures_agg[f]
            pq = f.result()
            # print(f"{agg_name}: {pq}")
            if pq:
                agg_price = pq['price']
                pct_savings = 100 - (100.0 * totle_price / agg_price)
                splits = exchange_utils.canonical_keys(pq['exchanges_parts'])
                savings = savings_data(order_type, trade_size, base, agg_name, pct_savings, totle_used, totle_price, agg_price, splits)
                agg_savings[agg_name] = savings
                trade_info = f"trade size={trade_size} ETH (Totle price={totle_price:.5g} {agg_name} price={agg_price:.5g})"
                if splits: trade_info += f"splits={splits}"
                print(f"Totle saved {pct_savings:.2f} percent vs {agg_name} {order_type}ing {base} on {','.join(totle_used)} {trade_info}")

            else:
                print(f"{agg_name} had no price quote for {order_type} {base} / {trade_size} {quote}")
    return agg_savings

########################################################################################################################
def main():


    working_dir = os.path.dirname(__file__)
    if working_dir: os.chdir(working_dir)

    quote='ETH'
    order_type = 'buy'

    TOTLE_39 = ['ANT','AST','BAT','BNT','CDT','CND','CVC','DAI','ENG','ENJ','ETHOS','GNO','KNC','LINK','MANA','MCO','MKR','OMG','PAX','PAY','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','STORJ','TKN','TUSD','USDC','USDT','WBTC','ZRX']
    AGG_CLIENTS = [dexag_client, oneinch_client, paraswap_client]
    all_buy_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(dict))) # extra lambda prevents KeyError in print_savings

    TOKENS, TRADE_SIZES  = TOTLE_39, [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0, 500.0]
    # TOKENS, TRADE_SIZES = ['CVC', 'DAI', 'LINK'], [0.5, 5.0]

    filename = get_filename_base(prefix='totle_vs_aggs', suffix=order_type)


    with SavingsCSV(filename) as csv_writer:
        for base in TOKENS:
            for trade_size in TRADE_SIZES:
                agg_savings = compare_totle_and_aggs(AGG_CLIENTS, base, quote, trade_size)
                for agg_name, savings in agg_savings.items():
                    all_buy_savings[agg_name][base][trade_size] = savings
                    csv_writer.append(savings)

    # print(json.dumps(all_buy_savings, indent=3))

    # Prints a savings dict, token => trade_size => savings values
    for agg_name in all_buy_savings:
        print_savings(order_type, all_buy_savings[agg_name], TRADE_SIZES, title=f"Savings vs. {agg_name}")

