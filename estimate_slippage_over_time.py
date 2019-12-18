import csv
import json
from collections import defaultdict

import data_import
import summarize_csvs
import dexag_client
import estimate_totle_split_savings


TOKEN_STUDIED = 'BAT'
DEX_STUDIED = 'Kyber'

def get_prices_and_slippage(over_time_csvs, dex):
    ex_label_ts_price = defaultdict(lambda: defaultdict(dict))
    ex_label_ts_slippage = defaultdict(lambda: defaultdict(dict))

    for csv_file, label in over_time_csvs:
        csv_file = f"../{csv_file}"
        # TODO infer DEX from file name rather than accept as parameter
        with open(csv_file, newline='') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=None)
            # time,action,trade_size,token,exchange,exchange_price,slippage,cost
            for row in reader:
                # time = datetime.fromisoformat(row['time']).isoformat(' ', 'seconds')
                trade_size = float(row['trade_size'])
                price = float(row['exchange_price'])
                slippage = float(row['slippage'])
                ex_label_ts_price[dex][label][trade_size] = price
                ex_label_ts_slippage[dex][label][trade_size] = slippage

    return ex_label_ts_price, ex_label_ts_slippage

def print_over_time_csv(ex_label_ts_val, trade_sizes, label="Price Slippage"):
    for ex, label_ts_val in ex_label_ts_val.items():
        print(f"{label} over time for {TOKEN_STUDIED} on {ex}")
        sorted_labels = sorted(label_ts_val.keys())
        print(f"Trade Size,{','.join(sorted_labels)}")
        for ts in trade_sizes:
            p_vals = [ label_ts_val[label].get(ts) for label in sorted_labels ]
            p_vals = [ str(v) if v else '' for v in p_vals ]
            print(f"{ts},{','.join(p_vals)}")


OVER_TIME_CSVS = [
    ('outputs/Kyber_BAT_2019-11-16_00:00:00_DEX.AG_buy_slippage.csv', '2019-11-16_00:00'),
    ('outputs/Kyber_BAT_2019-11-16_02:00:01_DEX.AG_buy_slippage.csv', '2019-11-16_02:00'),
    ('outputs/Kyber_BAT_2019-11-16_04:00:00_DEX.AG_buy_slippage.csv', '2019-11-16_04:00'),
    ('outputs/Kyber_BAT_2019-11-16_06:00:00_DEX.AG_buy_slippage.csv', '2019-11-16_06:00'),
    ('outputs/Kyber_BAT_2019-11-16_08:00:00_DEX.AG_buy_slippage.csv', '2019-11-16_08:00'),
    ('outputs/Kyber_BAT_2019-11-16_10:00:01_DEX.AG_buy_slippage.csv', '2019-11-16_10:00'),
    ('outputs/Kyber_BAT_2019-11-16_12:00:00_DEX.AG_buy_slippage.csv', '2019-11-16_12:00'),
    ('outputs/Kyber_BAT_2019-11-16_14:00:01_DEX.AG_buy_slippage.csv', '2019-11-16_14:00'),
    ('outputs/Kyber_BAT_2019-11-16_16:00:00_DEX.AG_buy_slippage.csv', '2019-11-16_16:00'),
    ('outputs/Kyber_BAT_2019-11-16_18:00:00_DEX.AG_buy_slippage.csv', '2019-11-16_18:00'),
    ('outputs/Kyber_BAT_2019-11-16_20:00:01_DEX.AG_buy_slippage.csv', '2019-11-16_20:00'),
    ('outputs/Kyber_BAT_2019-11-16_22:00:00_DEX.AG_buy_slippage.csv', '2019-11-16_22:00'),
]


ex_label_ts_price, ex_label_ts_slippage = get_prices_and_slippage(OVER_TIME_CSVS, DEX_STUDIED)

ts_dicts = sum([list(map(dict, label_ts_prices.values())) for ex, label_ts_prices in ex_label_ts_price.items()], [])
trade_sizes = summarize_csvs.sorted_trade_sizes(*ts_dicts)

print_over_time_csv(ex_label_ts_price, trade_sizes, label="Absolute Price")
print_over_time_csv(ex_label_ts_slippage, trade_sizes, label="Price Slippage")



