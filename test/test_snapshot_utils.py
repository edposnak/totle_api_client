import json

import snapshot_utils


def test_fetch_snapshot(id):
    j = snapshot_utils.fetch_snapshot(id)
    snapshot_utils.print_curve_info(j)


#######################################################################################################################

# test_dex_name_map()

test_fetch_snapshot('0x4f5aff3ef4214365b648ad4a06ce6a21902e9542e06c423fbe96aa3d3733d7e1')
test_fetch_snapshot('0xc98f6226a1ad4c0191e4a02daad3a85196c92e2fe5e443e2aa6e0375b4728213')
test_fetch_snapshot('0xb31c670026db4819a14fd574b0ca719b580b50f740cb4dc5baddb2ca5ea4e447')  # PAX for 400 ETH vs Paraswap (2020-03-24 22:11:12.384360)
test_fetch_snapshot('0xe77390dff6d448b9810f1aba056f17016be97febb0484031a1bf5e94fa87e3c4') # PAX for 400 ETH vs Paraswap 2020-03-24 23:09:20


exit(0)
