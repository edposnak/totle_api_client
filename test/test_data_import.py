import data_import
import glob

csv_files = glob.glob(f'../outputs/totle_vs_agg_splits_*')
count = 0

print(f"processing {len(csv_files)} CSV files ...")
for csv_file in csv_files:
    for time, *_ in data_import.csv_row_gen(csv_file):
        count +=1

print(f"count={count}")

