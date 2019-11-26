import os
from collections import defaultdict
import concurrent.futures

import exchange_utils
import binance_client
import huobi_client
import kraken_client
import v2_client
from v2_compare_prices import best_price_with_fees, get_savings, print_savings, get_filename_base, SavingsCSV


def compare_totle_and_cexs(cex_clients, base, quote, trade_size, books, order_type):
    cex_savings = {}

    # this hardcodes sourceAmount=trade_size when from_token is ETH
    from_token, to_token = (quote, base) if order_type == 'buy' else (base, quote)
    totle_sd = v2_client.try_swap(v2_client.name(), from_token, to_token, params={'tradeSize': trade_size}, verbose=False)
    if totle_sd:
        for cex_client in cex_clients:
            cex_name = cex_client.name()
            try:
                cex_price = best_price_with_fees(trade_size, books[cex_name], order_type, cex_client.fee_pct())
                cex_savings[cex_name] = get_savings(cex_name, cex_price, totle_sd, base, trade_size, order_type)
            except ValueError as e:
                print(f"{cex_name} raised {e} which resulted in no price quote for {order_type} {base} / {trade_size} {quote}")


    return cex_savings

########################################################################################################################
def main():
    working_dir = os.path.dirname(__file__)
    if working_dir: os.chdir(working_dir)

    CEX_CLIENTS = [binance_client, huobi_client, kraken_client]

    QUOTE_TOKEN='ETH'
    all_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(dict))) # extra lambda prevents KeyError in print_savings

    TOTLE_BINANCE_HUOBI_TOKENS = ['ADX', 'AST', 'BAT', 'CVC', 'ENG', 'KNC', 'LINK', 'MANA', 'MCO', 'NPXS', 'OMG', 'POWR', 'QSP', 'RCN', 'RDN', 'REQ', 'SALT', 'THETA', 'WTC', 'ZIL', 'ZRX']
    TOKENS = ['BAT', 'LINK', 'OMG'] # Only 3 tokens overlap Totle and all three CEXs

    TRADE_SIZES  = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0, 500.0]

    CSV_FIELDS = "time action trade_size token exchange exchange_price totle_used totle_price pct_savings splits ex_prices".split()

    for order_type in ['buy', 'sell']:
        filename = get_filename_base(prefix='totle_vs_cexs', suffix=order_type)
        with SavingsCSV(filename, fieldnames=CSV_FIELDS) as csv_writer:
            for token in TOKENS:
                bids, asks = {}, {}
                for cex_client in CEX_CLIENTS:
                    cex_name = cex_client.name()
                    try:
                        bids[cex_name], asks[cex_name] = cex_client.get_depth(token, QUOTE_TOKEN)
                    except (binance_client.BinanceAPIException, huobi_client.HuobiAPIException, kraken_client.KrakenAPIException) as e:
                        print(f"{cex_name} get_depth({token}/{QUOTE_TOKEN}) raised {e}")

                books = asks if order_type == 'buy' else bids
                for trade_size in TRADE_SIZES:
                    cex_savings = compare_totle_and_cexs(CEX_CLIENTS, token, QUOTE_TOKEN, trade_size, books, order_type)
                    for cex_name, savings in cex_savings.items():
                        all_savings[cex_name][token][trade_size] = savings
                        csv_writer.append(savings)

        # Prints a savings dict, token => trade_size => savings values
        for cex_name in all_savings:
            print_savings(order_type, all_savings[cex_name], TRADE_SIZES, title=f"Savings vs. {cex_name}")


if __name__ == "__main__":
    main()
