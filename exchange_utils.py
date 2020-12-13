import functools

# Every API has different names and ids for exchanges. So this map can be used to correlate data across APIs.
# It must be maintained manually based on the strings returned by the various APIs

SYM_TO_NAME = {
    'zero_x': '0x V3',
    '0x': '0x V3',
    '0x relays': '0x V3',
    '0x api':  '0x API',
    '0x v2': '0x V2',
    '0x v3': '0x V3',
    '0xmesh': '0xMesh',
    '0x mesh': '0xMesh',
    'aave': 'Aave',
    'ag': 'ag',
    'airswap': 'AirSwap',
    'bamboorelay': 'Bamboo Relay',
    'balancer': 'Balancer',
    'bancor': 'Bancor',
    'beth': 'BETH',
    'c.r.e.a.m. swap': 'C.R.E.A.M. Swap',
    'chi minter': 'Chi Minter',
    'chai': 'Chai',
    'compound': 'Compound',
    'curve': 'Curve',
    'curve.fi': 'Curve.fi',
    'curve.fi v2': 'Curve.fi v2',
    'curve.fi iearn': 'Curve.fi iearn',
    'curve.fi busd': 'Curve.fi BUSD',
    'curve.fi susd': 'Curve.fi sUSD',
    'curve.fi pax': 'Curve.fi PAX',
    'curve.fi renbtc': 'Curve.fi renBTC',
    'curve.fi tbtc': 'Curve.fi tBTC',
    'curve.fi sbtc': 'Curve.fi sBTC',
    'curve.fi hbtc': 'Curve.fi hBTC',
    'curve.fi 3pool': 'Curve.fi 3pool',
    'curve.fi susdv2': 'Curve.fi sUSDV2',
    'curve.fi compound': 'Curve.fi Compound',
    'curvefi compound': 'Curve.fi Compound',
    'curvefi pool #1': 'CurveFi Pool #1',
    'curvefi pool #2': 'CurveFi Pool #2',
    'curvefi pool #3': 'CurveFi Pool #3',
    'curvefi usdt': 'Curve.fi USDT',
    'curvefi y': 'Curve.fi Y',
    'curvefi pax': 'Curve.fi PAX',
    'curvefi susdv2': 'Curve.fi sUSDV2',
    'curvefi ren': 'Curve.fi renBTC',
    'curvefi sbtc': 'Curve.fi sBTC',
    'curvefi hbtc': 'Curve.fi hBTC',
    'curvefi tbtc': 'Curve.fi tBTC',
    'curvefi 3pool': 'Curve.fi 3pool',
    'curvefi dusd': 'CurveFi dUSD',
    'curvefi gusd': 'CurveFi gUSD',
    'curvefi husd': 'CurveFi hUSD',
    'curvefi musd': 'CurveFi mUSD',
    'curvefi usdk': 'CurveFi USDK',
    'curvefi usdn': 'CurveFi USDN',
    'curvefi rsv': 'CurveFi RSV',
    'defiswap': 'DefiSwap',
    'deversifi': 'deversifi',
    'ddex': 'DDEX',
    'dforce': 'dForce Swap',
    'dforce swap': 'dForce Swap',
    'dodo': 'DODO',
    'dydx': 'dYdX',
    'erc dex': 'ERC DEX',
    'eth2dai': 'Oasis',
    'etherdelta': 'Ether Delta',
    'ether delta': 'Ether Delta',
    'ethex': 'Ethex',
    'ethfinex': 'Ethfinex',
    'fulcrum': 'Fulcrum',
    'idex': 'IDEX',
    'idle': 'IdleFinance',
    'idlefinance': 'IdleFinance',
    'iearnfinance': 'IEarnFinance',
    'iearn': 'IEarnFinance',
    'kyber': 'Kyber',
    'liquidityprovider': 'LiquidityProvider',
    'makerdao': 'MakerDAO',
    'mooniswap': 'Mooniswap',
    'mstable': 'mStable',
    'multihop': 'MultiHop',
    'multipath': 'MultiPath',
    'multisplit': 'MultiSplit',
    'multi uniswap': 'Multi Uniswap',
    'multibridge': 'MultiBridge',
    'oasis': 'Oasis',
    'oasisdex': 'Oasis',
    'paradex': 'Paradex',
    'pathfinder': 'Pathfinder',
    'paraswappool2': 'ParaSwapPool2',
    'pmm': 'PMM',
    'pmm1': 'PMM1',
    'pmm2': 'PMM2',
    'pmm3': 'PMM3',
    'pmm4': 'PMM4',
    'pmm5': 'PMM5',
    'paraswappool' : 'PMM',
    'radar-relay': 'Radar Relay',
    'radarrelay': 'Radar Relay',
    'radar relay': 'Radar Relay',
    'setprotocol': 'SetProtocol',
    'sharkrelay': 'Shark Relay',
    'shark relay': 'Shark Relay',
    'shell': 'Shell',
    'stablecoinswap': 'StableCoinSwap',
    'star bit': 'STAR BIT',
    'sushi swap': 'Sushi Swap',
    'sushiswap': 'Sushi Swap',
    'sushi': 'Sushi Swap',
    'swerve': 'Swerve',
    'swerve.fi': 'Swerve',
    'synthetix': 'Synthetix',
    'synth depot': 'Synth Depot',
    'thetokenstore': 'Token Store',
    'token store': 'Token Store',
    'uniswap': 'Uniswap',
    'uniswap_v2': 'Uniswap V2',
    'uniswapv2': 'Uniswap V2',
    'uniswap v2': 'Uniswap V2',
    'weidex': 'weiDex',
    'weth': 'WETH',
    'zero_x_v2': 'zero_x_v2',
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
        raise ValueError(f"'{dex_name}' is an unknown exchange (using '{sym}')")

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
    return {k:v for k,v in canonical_keys(dex_dict).items() if k not in EXCLUDE_DEXS}

########################################################################################################################
# To generate the SYM_TO_NAME map
#
# import totle_client
# import dexag_client
# import oneinch_client
# import dexwatch_client
#
# all_dexs = set(totle_client.data_exchanges().keys())
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
