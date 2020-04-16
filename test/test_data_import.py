import data_import
import glob

csv_files = tuple(glob.glob(f'../outputs/2020-03-22_1[123]*buy.csv'))
#     per_token_savings, slip_price_splits = data_import.parse_csv_files(csv_files)
count = 0

print(f"processing {len(csv_files)} CSV files ...")
for csv_file in csv_files:
    for time, *_ in data_import.csv_row_gen(csv_file):
        count +=1

print(f"count={count}")

