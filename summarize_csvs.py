import sys
from collections import defaultdict
import csv

csv_files = sys.argv[1:]
if len(csv_files) < 1:
    print("no CSV files provided")
    exit(1)
else:
    print(f"processing {len(csv_files)} CSV files ...")


all_savings = defaultdict(lambda: defaultdict(list))
pos_samples, neg_samples = 0, 0

neg_savings = defaultdict(int)
pos_savings = defaultdict(int)

for file in csv_files:
    with open(file, newline='') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=None)
        for row in reader:
            trade_size = row['trade_size']
            trade_size_savings = all_savings[trade_size]

            dex = row['exchange']
            pct_savings = float(row['pct_savings'])

            trade_size_savings[dex].append(pct_savings)
            if pct_savings > 0.0:
                pos_samples += 1
                pos_savings[dex] += 1
            else:
                neg_samples += 1
                neg_savings[dex] += 1

############################################################################
# print neg savings stuff
dexs = ['AirSwap', 'Bancor', 'Kyber', 'Uniswap']

total_samples = pos_samples + neg_samples
neg_pct = 100.0 * neg_samples / total_samples

print(f"\n\nOut of {total_samples} data points, Totle's fees exceeded the price savings {neg_samples} times, resulting in negative price savings {neg_pct:.1f}% of the time.")

header = "\t".join(['NPS %'] + dexs)
print(f"\n{header}")
row = [ "buys" ]
for dex in dexs:
    if dex in neg_savings:
        pct_neg_savings = 100 * neg_savings[dex] / (neg_savings[dex] + pos_savings[dex])
        row.append(f"{pct_neg_savings:.2f}%")
    else:
        row.append("")

print("\t".join(row))
      

############################################################################
# print human readable average savings
print(f"\n\nOverall average price savings by trade size are shown below.")
for trade_size in all_savings:
    trade_size_savings = all_savings[trade_size]
    
    print(f"\nAverage Savings trade size = {trade_size} ETH vs")
    for dex in trade_size_savings:
        sum_savings, n_samples = sum(trade_size_savings[dex]), len(trade_size_savings[dex])
        print(f"   {dex}: {sum_savings/n_samples:.2f}% ({n_samples} samples)")
    
            
############################################################################
# print average savings summary table
print("\n\n")
print("\t".join(['Trade Size'] + dexs))

for trade_size in all_savings:
    row = [ f"{trade_size} ETH " ]
    savings = all_savings[trade_size]
    for dex in dexs:
        if dex in savings:
            sum_savings, n_samples = sum(savings[dex]), len(savings[dex])
            pct_savings = sum_savings/n_samples
            row.append(f"{pct_savings:.2f}%")
        else:
            row.append("")
    print("\t".join(row))
