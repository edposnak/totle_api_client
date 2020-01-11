import json

import top_tokens
import token_utils
import totle_client
import requests


def get_best_tokens_for_dexs(top_n=100, day_volume=90):
    top_by_volume = top_tokens.top_tokens_by_volume(top_n, day_volume)
    top_by_market_cap = top_tokens.top_tokens_by_market_cap(top_n)

    overlap = set(top_by_market_cap) & set(top_by_volume)
    print(f"\n\nOverlap of top tokens by market cap and volume ({len(overlap)} tokens)", overlap)

    missing = [ t for t in overlap if t not in token_utils.tokens() ]
    print(f"\n\nFrom Top Volume/Top Market Cap token_utils is missing {sorted(missing)}")
    print(f"proabably because they are only available on IDEX")

    good = [ t for t in overlap if t in token_utils.tokens() ]
    print(f"\n\nList of Top Volume/Top Market Cap tokens available on DEXs {sorted(good)}")


    # for t in top_by_volume:
    #     if t not in overlap: print(f"{t} is a top_by_volume token not in overlap")
    #
    # underlap = [ t for t in top_by_market_cap if not t in top_by_volume ]
    # print(f"\n\nTop tokens by market cap not in top volume ({len(underlap)} tokens)", underlap)
    #
    # underlap = [ t for t in top_by_volume if not t in top_by_market_cap ]
    # print(f"\n\nTop tokens by volume not in top market cap ({len(underlap)} tokens)", underlap)


# Order splitting tokens
# OS_TOKENS = ['BAT', 'DAI', 'ENJ', 'KNC', 'LINK', 'LRC', 'MANA', 'MCO', 'MKR', 'NEXO', 'NPXS', 'OMG', 'PAX', 'POWR', 'RCN', 'REN', 'REP', 'RLC', 'SNT', 'SNX', 'TKN', 'TUSD', 'USDC', 'USDT', 'VERI', 'WBTC', 'XDCE', 'ZRX']

OS_TOKENS = ['ABYSS', 'ANT', 'AST', 'BAT', 'BNT', 'CDAI', 'CDT', 'CETH', 'CND', 'CUSDC', 'CVC', 'CWBTC', 'CZRX', 'DAI',
             'DENT', 'ENG', 'ENJ', 'ETHOS', 'FUN', 'GNO', 'KNC', 'LEND', 'LINK', 'LRC', 'MANA', 'MCO', 'MKR', 'MLN',
             'MTL', 'NEXO', 'NPXS', 'OMG', 'PAX', 'PAY', 'PLR', 'POE', 'POLY', 'POWR', 'RCN', 'RDN', 'REN', 'REP',
             'REQ', 'RLC', 'RPL', 'SNT', 'SNX', 'SPANK', 'STORJ', 'TAU', 'TKN', 'TUSD', 'USDC', 'USDT', 'VERI', 'WBTC',
             'XDCE', 'ZRX']


def tradable_tokens_by_volume(top_n=100, day_volume=90):
    """List tradable tokens ordered by volume (does not include those not in the top_n"""
    top_by_volume = list(enumerate(top_tokens.top_tokens_by_volume(top_n, day_volume)))

    tokens_by_volume = []
    for t in token_utils.tradable_tokens():
        vr = [r+1 for r, s in top_by_volume if s == t]
        if vr: tokens_by_volume.append((vr[0], t))


    # WBTC, VERI, XDCE, BMC, PAX, MCO, NEXO, SNT
    # WBTC  # 7 by 90-day volume	ADD THIS TO ORDER SPLITTING
    # VERI  # 17 by 90-day volume	ADD THIS TO ORDER SPLITTING
    # XDCE  # 33 by 90-day volume	ADD THIS TO ORDER SPLITTING
    # BMC  # 47 by 90-day volume	ADD THIS TO ORDER SPLITTING
    for r, t in sorted(tokens_by_volume):
        add = 'ADD THIS TO ORDER SPLITTING' if r < 100 and t not in OS_TOKENS else ''
        print(f"{t} #{r} by {day_volume}-day volume\t{add}")

def tradable_tokens_by_market_cap(top_n=100):
    """List tradable tokens ordered by market cap (does not include those not in the top_n"""
    top_by_market_cap = list(enumerate(top_tokens.top_tokens_by_market_cap(top_n)))

    tokens_by_market_cap = []
    for t in token_utils.tradable_tokens():
        vr = [r+1 for r, s in top_by_market_cap if s == t]
        if vr: tokens_by_market_cap.append((vr[0], t))

    #
    # PAX #9 by  market_cap	    ADD THIS TO ORDER SPLITTING
    # MCO #24 by  market_cap	ADD THIS TO ORDER SPLITTING
    # NEXO #25 by  market_cap	ADD THIS TO ORDER SPLITTING
    # SNT #33 by  market_cap	ADD THIS TO ORDER SPLITTING
    for r, t in sorted(tokens_by_market_cap):
        add = 'ADD THIS TO ORDER SPLITTING' if r < 100 and t not in OS_TOKENS else ''
        print(f"{t:<8} #{r} by market_cap\t{add}")



def print_volume_and_market_cap_rank(tokens):
    token_rank_mkt_cap = top_tokens.top_tokens_by_market_cap_with_market_cap()
    token_vol = top_tokens.top_tokens_by_volume_with_volume(90)

    print(f"{'Token':<8}{'90-day Vol':<11}Market Cap Rank")
    for token in tokens:
        mkt_cap_rank = token_rank_mkt_cap.get(token)
        if mkt_cap_rank: mkt_cap_rank = mkt_cap_rank[0]
        print(f"{token:<8}{token_vol.get(token) or '?':<11}{mkt_cap_rank or '?'}")


########################################################################################################################
# main
# get_best_tokens_for_dexs()
tradable_tokens_by_volume()
# tradable_tokens_by_market_cap()


MORE_AGG_TOKENS = ['ABT','APPC','BLZ','BTU','CBI','DAT','DGX','DTA','ELF','EQUAD','GEN','IDAI','LBA','MOC','MYB','OST','QKC','SPN','UPP','WETH','XCHF']
print_volume_and_market_cap_rank(MORE_AGG_TOKENS)
UNSUPPORTED_TOKENS = ['IDAI','IKNC','ILINK','IREP','IUSDC','IWBTC','IZRX','SETH']
print_volume_and_market_cap_rank(UNSUPPORTED_TOKENS)





