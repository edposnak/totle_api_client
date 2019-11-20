import functools

# Every API has different names and ids for exchanges. So this map can be used to correlate data across APIs.
# It must be maintained manually based on the strings returned by the various APIs

SYM_TO_NAME = {
   '0x': '0xMesh',
   '0x relays': '0xMesh',
   '0xmesh': '0xMesh',
   '0x mesh': '0xMesh',
   'ag': 'ag',
   'airswap': 'AirSwap',
   'bamboorelay': 'Bamboo Relay',
   'bancor': 'Bancor',
   'compound': 'Compound',
   'ddex': 'DDEX',
   'dydx': 'dYdX',
   'erc dex': 'ERC DEX',
   'eth2dai': 'Oasis',
   'etherdelta': 'Ether Delta',
   'ether delta': 'Ether Delta',
   'ethex': 'Ethex',
   'ethfinex': 'Ethfinex',
   'fulcrum': 'Fulcrum',
   'idex': 'IDEX',
   'kyber': 'Kyber',
   'oasis': 'Oasis',
   'oasisdex': 'Oasis',
   'paradex': 'Paradex',
   'pmm': 'PMM',
   'radar-relay': 'Radar Relay',
   'radarrelay': 'Radar Relay',
   'radar relay': 'Radar Relay',
   'sharkrelay': 'Shark Relay',
   'shark relay': 'Shark Relay',
   'stablecoinswap': 'StableCoinSwap',
   'star bit': 'STAR BIT',
   'thetokenstore': 'Token Store',
   'token store': 'Token Store',
   'uniswap': 'Uniswap',
   'weidex': 'weiDex',
   'weth': 'WETH'
}

# get tokens
@functools.lru_cache(1)
def exchanges():
    return list(set(SYM_TO_NAME.values()))

def canonical_name(dex_name):
    """Returns the canonical name for the given dex_name if it is one of the known exchanges, else raises ValueError"""
    sym = dex_name.lower()
    if sym in SYM_TO_NAME:
        return SYM_TO_NAME[sym]
    else:
        raise ValueError(f"'{dex_name}' is an unknown exchange")

def canonical_names(dex_names):
    """Returns a list of canonical names for the given dex_names"""
    return [ canonical_name(d) for d in dex_names ]

def canonical_keys(dex_dict):
    """Returns a dict with canonical dex names as keys by translating the given keys"""
    r = { canonical_name(d): v for d, v in dex_dict.items() }
    # if the keys include e.g. 'Eth2dai' and 'Oasis' the result will be shorter so we catch that here
    if len(r) != len(dex_dict):
        raise ValueError(f"dict contains conflicting keys: {dex_dict.keys()}")
    return r

def canonical_and_splittable(dex_dict):
    # these DEXs are never going to be used in splits
    EXCLUDE_DEXS = ['ag', 'IDEX', 'DDEX', 'Ethfinex', 'Paradex']
    canonical_keys(dex_dict)

########################################################################################################################
# To generate the SYM_TO_NAME map
#
# import v2_client
# import dexag_client
# import oneinch_client
# import dexwatch_client
#
# all_dexs = set(v2_client.data_exchanges().keys())
# all_dexs |= set(oneinch_client.exchanges())
# all_dexs |= set(dexag_client.exchanges())
# all_dexs |= set(dexwatch_client.exchanges())
#
# sorted_dexs = sorted(all_dexs, key=str.casefold)
# print(f"\n\nall_dexes={json.dumps(sorted_dexs, indent=3)}")
#
# print(f"\n\nAPI Name    \tCanonical Name")
# for d in sorted_dexs:
#     print(f"{d:<12}\t{exchange_utils.canonical_name(d)}")
#
#
# map = { dex.lower(): dex for dex in sorted_dexs}
# print(f"\n\nSYM_TO_NAME = {json.dumps(map, indent=3)}")
#
