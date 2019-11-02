import sys
from collections import defaultdict
import csv

import exchange_utils

csv_files = sys.argv[1:]
if len(csv_files) < 1:
    print("no CSV files provided")
    exit(1)
else:
    print(f"processing {len(csv_files)} CSV files ...")

# trade_size: {exchange: [sample, sample, ...], ...}
per_trade_size_savings = defaultdict(lambda: defaultdict(list))

# token: { trade_size:  {exchange: [sample, sample, ...], ...}
per_token_savings = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

pos_samples, neg_samples = 0, 0
neg_savings, pos_savings = defaultdict(int), defaultdict(int)

ONLY_SPLITS, ONLY_NON_SPLITS = True, False
EXCLUDES = [('DEX.AG', 'ETHOS')]

for file in csv_files:
    with open(file, newline='') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=None)
        for row in reader:
            if row.get('splits'):
                splits = exchange_utils.canonical_keys(eval(row['splits']))
                if ONLY_SPLITS and len(splits) < 2: continue
                if ONLY_NON_SPLITS and len(splits) > 1: continue

            token = row['token']
            trade_size = row['trade_size']
            trade_size_savings = per_trade_size_savings[trade_size]
            exchange = row['exchange']
            pct_savings = float(row['pct_savings'])

            if (exchange, token) in EXCLUDES:
                # print(f"Excluding data for {token} on {exchange}")
                continue

            if exchange == '1-Inch' and token =='ZRX' and trade_size in ['0.1', '0.5'] and pct_savings < -1.0:
                print(f"Excluding {row}")
                continue

            trade_size_savings[exchange].append(pct_savings)
            per_token_savings[token][trade_size][exchange].append(pct_savings)

            if pct_savings > 0.0:
                pos_samples += 1
                pos_savings[exchange] += 1
            else:
                neg_samples += 1
                neg_savings[exchange] += 1

############################################################################
# print neg savings stuff
exchanges = sorted(list(set(neg_savings.keys()) | set(pos_savings.keys())))

total_samples = pos_samples + neg_samples
neg_pct = 100.0 * neg_samples / total_samples

print(f"\n\nOut of {total_samples} data points, Totle's fees exceeded the price savings {neg_samples} times, resulting in negative price savings {neg_pct:.1f}% of the time.")

header = "\t".join(['NPS %'] + exchanges)
print(f"\n{header}")
row = [ "buys" ]
for exchange in exchanges:
    if exchange in neg_savings:
        pct_neg_savings = 100 * neg_savings[exchange] / (neg_savings[exchange] + pos_savings[exchange])
        row.append(f"{pct_neg_savings:.2f}%")
    else:
        row.append("")

print("\t".join(row))

############################################################################
# print average savings by trade_size, exchange with num samples
def print_savings_with_num_samples(savings_by_trade_size):
    print(f"\n\nOverall average price savings by trade size are shown below.")
    for trade_size, trade_size_savings in savings_by_trade_size.items():
        print(f"\nAverage Savings trade size = {trade_size} ETH vs")
        for exchange in trade_size_savings:
            sum_savings, n_samples = sum(trade_size_savings[exchange]), len(trade_size_savings[exchange])
            print(f"   {exchange}: {sum_savings / n_samples:.2f}% ({n_samples} samples)")

print_savings_with_num_samples(per_trade_size_savings)


############################################################################
# print average savings summary table

def print_savings_summary_table(savings_by_trade_size, all_exchanges):
    headers = ''.join(list(map(lambda e: f"{e:<18}", all_exchanges)))
    print(f"{'Trade Size':<18}{headers}")
    # for trade_size, savings in savings_by_trade_size.items():
    for trade_size in map(str, sorted(map(float, savings_by_trade_size.keys()))):
        savings = savings_by_trade_size[trade_size]
        row = f"{trade_size:<6} ETH        "
        for exchange in all_exchanges:
            if exchange in savings:
                sum_savings, n_samples = sum(savings[exchange]), len(savings[exchange])
                pct_savings = sum_savings / n_samples
                row += f"{pct_savings:<18.2f}"
            else:
                row += f"{'-':18}"
        print("".join(row))

def print_savings_summary_table_csv(savings_by_trade_size, all_exchanges):
    print(f"Trade Size,{','.join(all_exchanges)}")
    for trade_size in map(str, sorted(map(float, savings_by_trade_size.keys()))):
        savings = savings_by_trade_size[trade_size]
        row = f"{trade_size}"
        for exchange in all_exchanges:
            if exchange in savings:
                sum_savings, n_samples = sum(savings[exchange]), len(savings[exchange])
                pct_savings = sum_savings / n_samples
                row += f",{pct_savings:.2f}"
            else:
                row += f","
        print(row)


print("\n\n")
print_savings_summary_table(per_trade_size_savings, exchanges)
print("\n\n")
print_savings_summary_table_csv(per_trade_size_savings, exchanges)

############################################################################
# print average savings by token

def print_per_token_savings_summary_tables(per_token_savings, exchanges):
    for token, tss in per_token_savings.items():
        print(f"\n\n{token}")
        print_savings_summary_table(tss, exchanges)

print("\n\n")
print_per_token_savings_summary_tables(per_token_savings, exchanges)

for token in ['ENJ','BAT','MKR','DAI']:
    print(f"\n{token}")
    print_savings_summary_table_csv(per_token_savings[token], exchanges)
