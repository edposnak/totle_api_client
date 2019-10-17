import v2_client
import datetime
from v2_compare_prices import compare_dex_prices

###############################################################3
non_liquid_dexs = [ 'Compound' ]
liquid_dexs = [e for e in v2_client.enabled_exchanges if e not in non_liquid_dexs ] 

non_liquid_tokens = []

trade_size = 0.1

all_savings = {}
all_savings[trade_size] = {}

all_supported_pairs = {}
all_supported_pairs[trade_size] = {dex: [] for dex in liquid_dexs} # compare_prices() uses these keys to know what dexs to try

# buy ETHOS trade size = 0.1 ETH
savings = compare_dex_prices('ETHOS', all_supported_pairs[trade_size], non_liquid_tokens, {'orderType': 'buy', 'tradeSize': trade_size}, debug=True)

# buy DATA trade size = 0.1 ETH
savings = compare_dex_prices('DATA', all_supported_pairs[trade_size], non_liquid_tokens, {'orderType': 'buy', 'tradeSize': trade_size}, debug=False)

# sell REN trade size = 0.1 ETH (1 trade 1 order)
# savings = compare_prices('REN', all_supported_pairs[trade_size], non_liquid_tokens, {'orderType': 'sell', 'tradeSize': trade_size}, debug=True)

# sell CDAI trade size = 0.1 ETH (2 trades)
# config = { 'exchanges':  {"list": [ 1, 15 ], "type": "black"} }
# savings = compare_prices('CDAI', all_supported_pairs[trade_size], non_liquid_tokens, {'orderType': 'sell', 'tradeSize': trade_size, 'config': config}, debug=True)

