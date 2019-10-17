import v2_client
from v2_compare_prices import get_savings, print_savings
import huobi_client

#####################################################################

TAKER_FEE_PCT = 0.2
# 0.2% for lowest tier (sources: https://www.huobi.co/en-us/fee https://huobiglobal.zendesk.com/hc/en-us/articles/360000210281-Announcement-New-Tiered-Fee-Structure)
# 0.03% for VIPs (DMs?) (sources: https://www.huobi.co/en-us/fee https://huobiglobal.zendesk.com/hc/en-us/articles/360000113122-Fees)

# TRADE_SIZES = [0.1, 1.0, 5.0, 10.0]
TRADE_SIZES = [0.1]
quote='ETH'
overlap_pairs = [ (b,q) for b,q in huobi_client.get_pairs() if q == quote and b in v2_client.tokens ]

for order_type in ['buy', 'sell']:
    savings = get_savings(huobi_client, order_type, overlap_pairs, TRADE_SIZES, TAKER_FEE_PCT, redirect=False)
    print_savings(order_type, savings, TRADE_SIZES)

