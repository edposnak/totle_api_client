import v2_client
from v2_compare_prices import get_savings, print_savings
import binance_client

#####################################################################

TAKER_FEE_PCT = 0.1
# https://www.binance.com/en/fee/schedule
# Taker fee is 0.1% up to VIP 4 level

TRADE_SIZES = [0.1, 1.0, 5.0, 10.0]
quote='ETH'
overlap_pairs = [ (b,q) for b,q in binance_client.get_pairs() if q == quote and b in v2_client.tokens ]

for order_type in ['buy', 'sell']:
    savings = get_savings(binance_client, order_type, overlap_pairs, TRADE_SIZES, TAKER_FEE_PCT, redirect=False)
    print_savings(order_type, savings, TRADE_SIZES)
