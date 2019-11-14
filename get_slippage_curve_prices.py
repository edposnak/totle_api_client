import os
import csv
import concurrent.futures
from datetime import datetime

import dexag_client
import exchange_utils
import oneinch_client
import paraswap_client
import v2_client
from v2_compare_prices import savings_data, print_savings, get_filename_base, SavingsCSV

#####################################################################

quote='ETH'
order_type = 'buy'

# MKR (5) $1,712,406
# DAI (6) $1,364,461
# BAT(4) $341,225
# USDC(3) $330,350
# cDAI(2) $244,397
# ZRX(4) $63,225
# GNO(4) $56,529
# LRC(?) $198,427
# SPANK(3) $185,372
# REP(2) $92,941
# TUSD(3)  $26,184
# KNC(5) $16,308
# ENJ(5) $5,044

# Intersection,31,"BAT,BTU,CVC,DAI,DGX,ELF,ENJ,GEN,GNO,KNC,LINK,MANA,MKR,MLN,OMG,PAX,POE,POWR,RCN,RDN,REN,REP,REQ,RLC,SNT,SNX,TKN,TUSD,USDC,WBTC,ZRX"

# 1,"BMC,CUSDC,CWBTC,CZRX,FUN,PLR,VERI"
# 2,"CDAI,CDT,CETH,CVC,DENT,ETHOS,LEND,MTL,NEXO,NPXS,PAX,PAY,REP,SNX,STORJ,TAU,USDT,XDCE"
# 3,"ANT,CND,ENG,MCO,OMG,POE,POLY,RCN,RPL,SPANK,TUSD,USDC"
# 4,"AST,BAT,GNO,LINK,MANA,POWR,REN,REQ,RLC,SNT,TKN,WBTC,ZRX"
# 5,"BNT,ENJ,KNC,MKR,RDN"
# 6,"DAI"

# DAI: ['0xMesh', 'Oasis', 'Bancor', 'Uniswap', 'Ether Delta', 'Kyber']
# USDC: ['0xMesh', 'Uniswap', 'Kyber']
# TUSD: ['Uniswap', 'Ether Delta', 'Kyber']
# MKR: ['0xMesh', 'Oasis', 'Bancor', 'Uniswap', 'Kyber']
# BAT: ['0xMesh', 'Bancor', 'Uniswap', 'Kyber']
# ZRX: ['0xMesh', 'Uniswap', 'Ether Delta', 'Kyber']
# KNC: ['0xMesh', 'Bancor', 'Uniswap', 'Ether Delta', 'Kyber']
# ENJ: ['0xMesh', 'Bancor', 'Uniswap', 'Ether Delta', 'Kyber']

# Choose 8 coins, which:
# 1. represent a wide range of liquidity on Uniswap
# 2. are supported by at least 3 DEXs (at least 1 pool and 1 order book)
# 3. were split by DEX.AG, 1-Inch, and Paraswap

STABLE_COINS = ['DAI','USDC','TUSD']
NETWORK_COINS = ['MKR', 'BAT', 'ZRX', 'KNC', 'ENJ']
TOKENS = STABLE_COINS + NETWORK_COINS

# TOKENS_MAXTS_DEXS = {
#     'DAI': (500.0, ['0xMesh', 'Oasis', 'Bancor', 'Uniswap', 'Ether Delta', 'Kyber']),
#     'USDC': (500.0, ['0xMesh', 'Uniswap', 'Kyber']),
#     'TUSD': (100.0, ['Uniswap', 'Ether Delta', 'Kyber']),
#     'MKR': (500.0, ['0xMesh', 'Oasis', 'Bancor', 'Uniswap', 'Kyber']),
#     'BAT': (100.0, ['0xMesh', 'Bancor', 'Uniswap', 'Kyber']),
#     'ZRX': (10.0, ['0xMesh', 'Uniswap', 'Ether Delta', 'Kyber']),
#     'KNC': (50.0, ['0xMesh', 'Bancor', 'Uniswap', 'Ether Delta', 'Kyber']),
#     'ENJ': (50.0, ['0xMesh', 'Bancor', 'Uniswap', 'Ether Delta', 'Kyber']),
# }

# with DEFAULT_MAX_SLIPPAGE_PERCENT = 30
# {'DAI': 1000.0, 'ENJ': 100.0, 'KNC': 60.0, 'ZRX': 100.0, 'BAT': 500.0, 'MKR': 1000.0, 'TUSD': 400.0, 'USDC': 700.0}
# {'DAI': 1000.0, 'ENJ': 100.0, 'KNC': 60.0, 'ZRX': 100.0, 'BAT': 500.0, 'MKR': 1000.0, 'TUSD': 400.0, 'USDC': 800.0}

TOKENS_MAXTS_DEXS = {
    'BAT': (1000.0, ['0xMesh', 'Bancor', 'Uniswap', 'Kyber']),
    'DAI': (1000.0, ['0xMesh', 'Oasis', 'Bancor', 'Uniswap', 'Ether Delta', 'Kyber']),
    'ENJ': (100.0, ['0xMesh', 'Bancor', 'Uniswap', 'Ether Delta', 'Kyber']),
    'KNC': (60.0, ['0xMesh', 'Bancor', 'Uniswap', 'Ether Delta', 'Kyber']),
    'MKR': (1000.0, ['0xMesh', 'Oasis', 'Bancor', 'Uniswap', 'Kyber']),
    'OMG': (500.0, ['0xMesh', 'Bancor', 'Uniswap', 'Kyber']),
    'TUSD': (400.0, ['Uniswap', 'Ether Delta', 'Kyber']),
    'USDC': (800.0, ['0xMesh', 'Uniswap', 'Kyber']),
    'ZRX': (100.0, ['0xMesh', 'Uniswap', 'Ether Delta', 'Kyber']),
}


AGG_CLIENTS = [dexag_client, oneinch_client, paraswap_client]

TRADE_SIZES  = [0.1, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0,
                10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0,
                100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0]

CSV_FIELD_NAMES = "time action trade_size token exchange exchange_price slippage cost".split()

def do_dex_token_on_agg(client, dex, to_token, trade_sizes, from_token='ETH', order_type='buy'):
    agg_name = client.name()
    dex_name = client.DEX_NAME_MAP.get(dex)
    if not dex_name:  # skip DEXs that aren't supported by this client
        return 0

    filename = f"{get_filename_base(prefix=f'{dex}_{to_token}', suffix=f'{agg_name}_buy_slippage')}.csv"
    print(f"Doing on {agg_name} {order_type} {to_token}/{from_token} on {dex} trade_sizes={trade_sizes} -> {filename}")
    with open(filename, 'w', newline='') as csvfile:
        csv_writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELD_NAMES)
        csv_writer.writeheader()

        base_price, num_prices = None, 0
        for trade_size in trade_sizes:
            pq = client.get_quote(from_token, to_token, from_amount=trade_size, dex=dex_name)
            if not pq:
                print(f"No price from {agg_name} for {order_type} {to_token}/{from_token} on {dex} trade_size={trade_size}")
            else:
                num_prices+= 1
                price = pq['price']
                base_price = base_price or price
                slippage = (price - base_price) / base_price
                cost = trade_size * slippage

                csv_writer.writerow({'time': datetime.now().isoformat(), 'action': order_type,
                                     'trade_size': trade_size, 'token': to_token, 'exchange': dex,
                                     'exchange_price': price, 'slippage': slippage, 'cost': cost})
                csvfile.flush()
    return num_prices


########################################################################################################################
# main
working_dir = os.path.dirname(__file__)
if working_dir: os.chdir(working_dir)

todo = []
for to_token, (max_ts, dexs) in TOKENS_MAXTS_DEXS.items():
    trade_sizes = [ t for t in TRADE_SIZES if t <= max_ts ]
    for dex in dexs:
        for client in [v2_client, dexag_client]:
            todo.append((do_dex_token_on_agg, client, dex, to_token, trade_sizes))

MAX_THREADS = 8
with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    futures_p = { executor.submit(*p): p for p in todo }

for f in concurrent.futures.as_completed(futures_p):
    _, _, dex, token, trade_sizes = futures_p[f]
    print(f"{dex} {token} -> {f.result()}")

