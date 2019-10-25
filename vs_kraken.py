import token_utils
from v2_compare_prices import get_cex_savings, print_savings
import kraken_client


#####################################################################

TRADE_SIZES = [0.1, 1.0, 5.0, 10.0]
quote='ETH'
overlap_pairs = [ (b,q) for b,q in kraken_client.get_pairs(quote) if b in token_utils.top_tokens() ]

for order_type in ['buy', 'sell']:
    savings = get_cex_savings(kraken_client, order_type, overlap_pairs, TRADE_SIZES)
    print_savings(order_type, savings, TRADE_SIZES)
