import csv
import sys

all_savings = {}
pos_samples, neg_samples = 0, 0

for file in sys.argv[1:]:
    print(f"processing {file} ...")

    with open(file, newline='') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=None)
        for row in reader:
            trade_size = row['trade_size']
            if trade_size not in all_savings:
                all_savings[trade_size] = {}
            trade_size_savings = all_savings[trade_size]

            dex = row['exchange']
            if dex not in trade_size_savings:
                trade_size_savings[dex] = []

            pct_savings = float(row['pct_savings'])
            trade_size_savings[dex].append(pct_savings)
            if pct_savings > 0.0:
                pos_samples += 1
            else:
                neg_samples += 1

total_samples = pos_samples + neg_samples
neg_pct = 100.0 * neg_samples / total_samples

print(f"\n\nOut of {total_samples} data points, Totle's fees exceeded the price savings {neg_samples} times, resulting in negative price savings {neg_pct:.1f}% of the time. Overall average price savings by trade size are shown below.")

for trade_size in all_savings:
    trade_size_savings = all_savings[trade_size]
    
    print(f"\nAverage Savings trade size = {trade_size} ETH vs")
    for dex in trade_size_savings:
        sum_savings, n_samples = sum(trade_size_savings[dex]), len(trade_size_savings[dex])
        print(f"   {dex}: {sum_savings/n_samples:.2f}% ({n_samples} samples)")
    
            
