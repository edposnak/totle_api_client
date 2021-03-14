import functools

# Every API has different names and ids for exchanges. So this map can be used to correlate data across APIs.
# It must be maintained manually based on the strings returned by the various APIs

SYM_TO_NAME = {
    'zrx': '0x V3',
    'zero_x': '0x V3',
    '0x': '0x V3',
    '0x relays': '0x V3',
    '0x api':  '0x API',
    '0x v2': '0x V2',
    '0x v3': '0x V3',
    '0xmesh': '0xMesh',
    '0x mesh': '0xMesh',
    'aave': 'Aave',
    'aave_v2': 'Aave V2',
    'aave_liquidator': 'Aave Liquidator',
    'ag': 'ag',
    'airswap': 'AirSwap',
    'bamboorelay': 'Bamboo Relay',
    'balancer': 'Balancer',
    'bancor': 'Bancor',
    'beth': 'BETH',
    'blackholeswap': 'BlackHoleSwap',
    'cofix': 'cofix',
    'c.r.e.a.m. swap': 'CreamSwap',
    'creamswap': 'CreamSwap',
    'chi minter': 'Chi Minter',
    'chai': 'Chai',
    'compound': 'Compound',
    'curve': 'Curve',
    'curve.fi': 'Curve.fi',
    'curve.fi v2': 'Curve.fi v2',
    'curve.fi aave': 'Curve.fi Aave',
    'curve.fi compound': 'Curve.fi Compound',
    'curve.fi iearn': 'Curve.fi iearn',
    'curve.fi busd': 'Curve.fi BUSD',
    'curve.fi susd': 'Curve.fi sUSD',
    'curve.fi pax': 'Curve.fi PAX',
    'curve.fi renbtc': 'Curve.fi renBTC',
    'curve.fi bbtc': 'Curve.fi bBTC',
    'curve.fi hbtc': 'Curve.fi hBTC',
    'curve.fi obtc': 'Curve.fi oBTC',
    'curve.fi pbtc': 'Curve.fi pBTC',
    'curve.fi sbtc': 'Curve.fi sBTC',
    'curve.fi tbtc': 'Curve.fi tBTC',
    'curve.fi 3pool': 'Curve.fi 3pool',
    'curve.fi susdv2': 'Curve.fi sUSDV2',
    'curvefi aave': 'Curve.fi Aave',
    'curvefi compound': 'Curve.fi Compound',
    'curvefi pool #1': 'Curve.fi Pool #1',
    'curvefi pool #2': 'Curve.fi Pool #2',
    'curvefi pool #3': 'Curve.fi Pool #3',
    'curvefi usdt': 'Curve.fi USDT',
    'curvefi ust': 'Curve.fi UST',
    'curvefi euro': 'Curve.fi Euro',
    'curvefi y': 'Curve.fi Y',
    'curvefi pax': 'Curve.fi PAX',
    'curvefi susdv2': 'Curve.fi sUSDV2',
    'curvefi ren': 'Curve.fi renBTC',
    'curvefi bbtc': 'Curve.fi bBTC',
    'curvefi hbtc': 'Curve.fi hBTC',
    'curvefi obtc': 'Curve.fi oBTC',
    'curvefi pbtc': 'Curve.fi pBTC',
    'curvefi sbtc': 'Curve.fi sBTC',
    'curvefi tbtc': 'Curve.fi tBTC',
    'curvefi 3pool': 'Curve.fi 3pool',
    'curvefi busd': 'CurveFi bUSD',
    'curvefi dusd': 'CurveFi dUSD',
    'curvefi gusd': 'CurveFi gUSD',
    'curvefi husd': 'CurveFi hUSD',
    'curvefi linkusd': 'Curve.fi linkUSD',
    'curvefi musd': 'Curve.fi mUSD',
    'curvefi usdk': 'Curve.fi USDK',
    'curvefi usdn': 'Curve.fi USDN',
    'curvefi rsv': 'Curve.fi RSV',
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
    'indexed_finance': 'indexed_finance',
    'kyber': 'Kyber',
    'linkswap': 'LINKSWAP',
    'liquidityprovider': 'LiquidityProvider',
    'luaswap': 'LuaSwap',
    'makerdao': 'MakerDAO',
    'miniswap': 'MiniSwap',
    'mooniswap': 'Mooniswap',
    'mstable': 'mStable',
    'multihop': 'MultiHop',
    'multipath': 'MultiPath',
    'multisplit': 'MultiSplit',
    'multi uniswap': 'Multi Uniswap',
    'multibridge': 'MultiBridge',
    'oasis': 'Oasis',
    'oasisdex': 'Oasis',
    'one_inch_lp': '1-Inch LP',
    'one_inch_lp_1_1': '1-Inch LP V1_1',
    'one_inch_lp_migrator': '1-Inch LP Migrator',
    'one_inch_lp_migrator_v1_1': '1-Inch LP Migrator V1_1',
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
    'powerindex': 'PowerIndex',
    'psm': 'PSM',
    'radar-relay': 'Radar Relay',
    'radarrelay': 'Radar Relay',
    'radar relay': 'Radar Relay',
    's_finance': 'S_FINANCE',
    'setprotocol': 'SetProtocol',
    'sharkrelay': 'Shark Relay',
    'shark relay': 'Shark Relay',
    'shell': 'Shell',
    'stablecoinswap': 'StableCoinSwap',
    'star bit': 'STAR BIT',
    'st_eth': 'ST ETH',
    'sushi swap': 'Sushi Swap',
    'sushiswap_migrator': 'Sushi Swap',
    'sushiswap': 'Sushi Swap',
    'sushi': 'Sushi Swap',
    'swerve': 'Swerve',
    'swerve.fi': 'Swerve',
    'synthetix': 'Synthetix',
    'synth depot': 'Synth Depot',
    'thetokenstore': 'Token Store',
    'token store': 'Token Store',
    'uniswap': 'Uniswap',
    'uniswap_v1': 'Uniswap',
    'uniswap_v2': 'Uniswap V2',
    'uniswap_v2_migrator': 'Uniswap V2',
    'uniswapv2': 'Uniswap V2',
    'uniswap v2': 'Uniswap V2',
    'valueliquid': 'Value Liquid',
    'weidex': 'weiDex',
    'weth': 'WETH',
    'xsigma': 'xSigma',
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
