from collections import defaultdict
import token_utils
import oneinch_client
from v2_compare_prices import compare_to_totle, print_savings

#####################################################################

TRADE_SIZES = [0.1, 1.0, 5.0, 10.0]
quote='ETH'
overlap_pairs = [(b,q) for b,q in oneinch_client.get_pairs(quote) if b in token_utils.select_tokens()]


print(f"{len(overlap_pairs)} overlapping pairs")
print([t for t,_ in overlap_pairs])
exit(0)

all_buy_savings, all_sell_savings = defaultdict(lambda: defaultdict(dict)), defaultdict(lambda: defaultdict(dict))

for trade_size in TRADE_SIZES:
    for base, quote in overlap_pairs:
        # We have to do buys and sells together because 1-Inch doesn't support to_amount, so we use the amount
        # from the buy as from_amount in the sell to get approximately trade_size tokens. This approximation should
        # be good enough for price comparisons at the same trade size
        order_type = 'buy'
        print(quote, base, trade_size)
        pq = oneinch_client.get_quote(quote, base, trade_size)
        if not pq:
            print(f"No price quote for {order_type} {base} with {quote}")
            continue
        price = pq['price']
        print(f"{order_type} {pq['destination_token']} with {pq['source_amount']} {pq['source_token']} price={price}")
        if not price:
            print(f"price quote was {price} for {order_type} {base} with {quote}")
            continue
        savings = compare_to_totle(base, quote, order_type, trade_size, oneinch_client.name(), price)
        if savings: all_buy_savings[base][trade_size] = savings

        order_type = 'sell'
        amt_to_sell = pq['destination_amount'] # should fetch a little less than trade_size
        print(base, quote, trade_size, amt_to_sell)
        pq = oneinch_client.get_quote(base, quote, amt_to_sell)
        if not pq:
            print(f"No price quote for {order_type} {base} for {quote}")
            continue
        price = pq['price']
        print(f"{order_type} {pq['source_token']} for {pq['destination_amount']} {pq['destination_token']} price={price}")
        if not price:
            print(f"price quote was {price} for {order_type} {base} with {quote}")
            continue
        savings = compare_to_totle(base, quote, order_type, trade_size, oneinch_client.name(), price)
        if savings: all_sell_savings[base][trade_size] = savings


print_savings('buy', all_buy_savings, TRADE_SIZES)
print_savings('sell', all_sell_savings, TRADE_SIZES)
