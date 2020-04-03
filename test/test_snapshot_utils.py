import glob
import json

import snapshot_utils


def test_fetch_and_print_curve_info(id):
    # snapshot_utils.fetch_and_print_curve_info(id)
    j = snapshot_utils.fetch_snapshot(id)
    ci = snapshot_utils.get_curve_info(j)
    snapshot_utils.print_curve_info(ci, pct_inc=2)


#######################################################################################################################

# test_dex_name_map()

# OMG for 300 ETH vs Paraswap (2020-03-22 20:09:21.960482)
# 	Totle:      0.009681    {'Bancor': 92, 'Kyber': 8}
# 	Paraswap:   0.008915    {'Bancor': 88, 'Kyber': 12}
# Totle's price is 8.60% higher than Paraswap's
# Totle's rate=103.291 Paraswap:'s rate=112.173
# test_fetch_and_print_curve_info('0x3eb5a92ce6f44667a121cfded941f95197c8ddf61bc5411f9e82682a3468793f')

# OMG for 300 ETH vs Paraswap (2020-03-22 21:11:09.195667)
# 	Totle:      0.009687    {'Bancor': 92, 'Kyber': 8}
# 	Paraswap:   0.008922    {'Bancor': 88, 'Kyber': 12}
# Totle's price is 8.57% higher than Paraswap's
# Totle's rate=103.23 Paraswap:'s rate=112.082
# test_fetch_and_print_curve_info('0x7d1b243b46cb432d8b6989e3f33ce2839faed76a90134d7d9d89b71fef2af67a')

# OMG for 300 ETH vs Paraswap (2020-03-23 07:10:12.568315)
# 	Totle:      0.011662    {'Bancor': 100}
# 	Paraswap:   0.011083    {'Bancor': 98, 'Kyber': 2}
# Totle's price is 5.23% higher than Paraswap's
# Totle's rate=85.7475 Paraswap:'s rate=90.2286
#    MAX POSSIBLE ALLOCATION of 100.0% to Bancor for OMG/ETH (rate=85.74747114903911)
# test_fetch_and_print_curve_info('0x7d1b243b46cb432d8b6989e3f33ce2839faed76a90134d7d9d89b71fef2af67a')

# LEND for 100 ETH vs Paraswap (2020-03-22 19:08:47.507457)
# 	Totle:      0.000300    {'Kyber': 18, 'Uniswap': 82}
# 	Paraswap:   0.000293    {'Kyber': 20, 'Uniswap': 80}
# Totle's price is 2.43% higher than Paraswap's
# Totle's rate=3333.55 Paraswap:'s rate=3414.62
# test_fetch_and_print_curve_info('0x7c71eae6ed6145c591b300d691e9f67b099f04facceb41aebd57b46e59d7fa37')

# PAX for 400 ETH vs Paraswap (2020-03-24 01:10:05.534014)
# id=0x4ba8103852404a07aa563d5cb80e9f4a293438e18449456aa12ab0f164729a81
# 	Totle:      0.009010    {'DAI/ETH': {'Oasis': 74, 'PMM': 26}, 'PAX/DAI': {'Kyber': 50, 'PMM': 32, 'Uniswap': 18}}
# 	Paraswap:   0.007311    {'Kyber': 90, 'PMM': 10}
# Totle's price is 23.24% higher than Paraswap's
# Totle's rate=110.986 Paraswap:'s rate=136.78
# test_fetch_and_print_curve_info('0x4ba8103852404a07aa563d5cb80e9f4a293438e18449456aa12ab0f164729a81')

# SNT for 500 ETH vs Paraswap (2020-03-26 08:58:00.631351)
# id=0x64bed9ac2aa34ea090ae4d8a50e39ebdd58616d56b3c4ce98e7ab9f0c32cbc00
# 	Totle:      0.000377    {'Bancor': 21, 'Kyber': 2, 'Uniswap': 77}
# 	Paraswap:   0.000367    {'Bancor': 36, 'Kyber': 2, 'Uniswap': 62}
# Totle's price is 2.63% higher than Paraswap's
# Totle's rate=2655.3 Paraswap:'s rate=2725.17
# test_fetch_and_print_curve_info('0x64bed9ac2aa34ea090ae4d8a50e39ebdd58616d56b3c4ce98e7ab9f0c32cbc00')

# ENJ for 5000 ETH vs Paraswap (2020-04-02 15:18:22.466309)
# id=0xd9919152a010406dba827f92bd15b2bb62779acef0c54c88b4c360ef23730641
# 	Totle:      0.090606    {'SAI/ETH': {'Uniswap': 100}, 'ENJ/SAI': {'Kyber': 0, 'Uniswap': 100}}
# 	Paraswap:   0.006477    {'Bancor': 92, 'Uniswap': 8}
# Totle's price is 1298.89% higher than Paraswap's. Totle rate=11.0368 Paraswap: rate=154.393
# test_fetch_and_print_curve_info('0xd9919152a010406dba827f92bd15b2bb62779acef0c54c88b4c360ef23730641')

all_snapshots = tuple(glob.glob(f'{snapshot_utils.SNAP_DATA_DIRECTORY}/*'))
for snap_id in all_snapshots:
    j = snapshot_utils.fetch_snapshot(snap_id)
    ci = snapshot_utils.get_curve_info(j)


