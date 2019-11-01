from collections import defaultdict
import token_utils
import dexag_client
from v2_compare_prices import compare_to_totle, print_savings, get_filename_base, SavingsCSV


#####################################################################

quote='ETH'
# TRADE_SIZES = [0.1, 1.0, 5.0, 10.0]
# overlap_pairs = [(b,q) for b,q in dexag_client.get_pairs(quote) if b in token_utils.select_tokens()]
TRADE_SIZES = [0.1, 1.0]
overlap_pairs = [('BAT',quote), ('DAI',quote)]

all_buy_savings, all_sell_savings = defaultdict(lambda: defaultdict(dict)), defaultdict(lambda: defaultdict(dict))


for order_type in ['buy', 'sell']:
    filename = get_filename_base(prefix='dexag', suffix=order_type)
    print(f"Sending output to {filename}")
    with SavingsCSV(filename) as csv_writer:

        for base, quote in sorted(overlap_pairs):
            for trade_size in TRADE_SIZES:
                print(f"{order_type} {base}/{quote} trade_size={trade_size}")
                if order_type == 'buy':
                    pq = dexag_client.get_quote(quote, base, from_amount=trade_size)
                    savings_data = all_buy_savings[base]
                else: #  order_type == 'sell'
                    pq = dexag_client.get_quote(base, quote, to_amount=trade_size)
                    savings_data = all_sell_savings[base]

                if not pq:
                    print(f"No price quote for {order_type} {base} / {quote}")
                    continue
                price = pq['price']

                print(f"dexag price={price}")

                splits = pq['exchanges_parts']
                savings = compare_to_totle(base, quote, order_type, trade_size, dexag_client.name(), price, splits)
                if savings:
                    savings_data[trade_size] = savings
                    csv_writer.append(savings)



print_savings('buy', all_buy_savings, TRADE_SIZES)
print_savings('sell', all_sell_savings, TRADE_SIZES)
