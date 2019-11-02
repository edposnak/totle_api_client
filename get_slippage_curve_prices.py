import csv
import json
from collections import defaultdict
import concurrent.futures
from datetime import datetime
import time

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

TOKENS_MAXTS_DEXS = {
    'DAI': (500.0, ['0xMesh', 'Oasis', 'Bancor', 'Uniswap', 'Ether Delta', 'Kyber']),
    'USDC': (500.0, ['0xMesh', 'Uniswap', 'Kyber']),
    'TUSD': (100.0, ['Uniswap', 'Ether Delta', 'Kyber']),
    'MKR': (500.0, ['0xMesh', 'Oasis', 'Bancor', 'Uniswap', 'Kyber']),
    'BAT': (100.0, ['0xMesh', 'Bancor', 'Uniswap', 'Kyber']),
    'ZRX': (10.0, ['0xMesh', 'Uniswap', 'Ether Delta', 'Kyber']),
    'KNC': (50.0, ['0xMesh', 'Bancor', 'Uniswap', 'Ether Delta', 'Kyber']),
    'ENJ': (50.0, ['0xMesh', 'Bancor', 'Uniswap', 'Ether Delta', 'Kyber']),
}

DEXS = ['0xMesh', 'Ether Delta', 'Bancor', 'Uniswap']

AGG_CLIENTS = [dexag_client, oneinch_client, paraswap_client]
# BUY           0.1     0.5       1       5      10      50   1e+02   5e+02

# BAT         -0.18   -0.27   -0.26   -0.25   -0.25    -2.5    -4.1       -
# BAT         -0.24   -0.33   -0.33   -0.43   -0.39    -2.9    -4.4       -
# DAI         -0.25   -0.25   -0.25   -0.28   -0.32   -0.35   -0.35   -0.25
# DAI         -0.37   -0.38   -0.39   -0.42   -0.39   -0.35   -0.33   -0.34
# ENJ         -0.25   -0.41   -0.38   -0.25   -0.26       -       -       -
# ENJ         -0.25   -0.41   -0.38   -0.46   -0.84       -       -       -
# KNC         -0.25   -0.25   -0.44   -0.25   -0.25       -       -       -
# KNC         -0.25   -0.25   -0.44   -0.28   -0.34       -       -       -
# MKR         -0.25   -0.25   -0.25   -0.25   -0.25    -0.4   -0.66    -2.8
# MKR         -0.25   -0.25   -0.25   -0.25   -0.25    -0.4   -0.66    -2.8
# TUSD        -0.34   -0.25   -0.25   -0.25   -0.25   -0.25   -0.25       -
# TUSD        -0.37   -0.63   -0.61   -0.56   -0.47   -0.45   -0.54       -
# USDC        -0.28    -0.3   -0.32   -0.54   -0.68    -0.7   -0.78   -0.61
# USDC        -0.28    -0.3   -0.32   -0.54   -0.68   -0.73   -0.81   -0.76
# ZRX         -0.25   -0.25   -0.28   -0.25   -0.25       -       -       -
# ZRX         -0.25   -0.25   -0.28   -0.25   -0.25       -       -       -

TRADE_SIZES  = [0.1, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0,
                10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0,
                100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0]

CSV_FIELD_NAMES = "time action trade_size token exchange exchange_price".split()
TOTLE_DEX_NAME_MAP = {'Ether Delta': 'EtherDelta', 'Oasis': 'Eth2dai' }

def do_dex_token(dex, to_token, trade_sizes, from_token='ETH', order_type='buy'):
    filename = f"{get_filename_base(prefix=f'{dex}_{to_token}', suffix='buy_slippage')}.csv"
    print(f"Doing {order_type} {to_token}/{from_token} on {dex} trade_sizes={trade_sizes} -> {filename}")
    with open(filename, 'w', newline='') as csvfile:
        csv_writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELD_NAMES)
        csv_writer.writeheader()

        num_prices = 0
        for trade_size in trade_sizes:
            params = {'orderType': order_type, 'tradeSize': trade_size}
            totle_dex_name = TOTLE_DEX_NAME_MAP.get(dex) or dex
            totle_sd = v2_client.try_swap(v2_client.name(), from_token, to_token, exchange=totle_dex_name, params=params, verbose=False)
            if not totle_sd:
                print(f"No price from Totle for {order_type} {to_token}/{from_token} on {dex} trade_size={trade_size}")
            else:
                num_prices+= 1
                dex_price = totle_sd['price']
                if dex != exchange_utils.canonical_name(totle_sd['totleUsed'][0]):
                    print(f"dex = {dex} but totle_sd['totleUsed'] = {totle_sd['totleUsed'][0]}")
                    exit(-1)

                csv_writer.writerow({'time': datetime.now().isoformat(), 'action': order_type, 'trade_size': trade_size,
                                     'token': to_token, 'exchange': dex, 'exchange_price': dex_price})
                csvfile.flush()
    return num_prices

########################################################################################################################
# main

todo = []
for to_token, (max_ts, dexs) in TOKENS_MAXTS_DEXS.items():
    trade_sizes = [ t for t in TRADE_SIZES if t <= max_ts ]
    for dex in dexs:
        todo.append((do_dex_token, dex, to_token, trade_sizes))

MAX_THREADS = 8
with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    futures_p = { executor.submit(*p): p for p in todo }

for f in concurrent.futures.as_completed(futures_p):
    _, dex, token, trade_sizes = futures_p[f]
    print(f"{dex} {token} -> {f.result()}")







