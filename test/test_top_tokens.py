import json

import top_tokens
import token_utils
import v2_client
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
OS_TOKENS = ['BAT', 'DAI', 'ENJ', 'KNC', 'LINK', 'LRC', 'MANA', 'MCO', 'MKR', 'NEXO', 'NPXS', 'OMG', 'PAX', 'POWR',
             'RCN', 'REN', 'REP', 'RLC', 'SNT', 'SNX', 'TKN', 'TUSD', 'USDC', 'USDT', 'VERI', 'WBTC', 'XDCE', 'ZRX']


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

    OS_TOKENS = ['BAT', 'DAI', 'ENJ', 'KNC', 'LINK', 'LRC', 'MANA', 'MKR', 'NPXS', 'OMG', 'POWR', 'PPT', 'RCN', 'REN',
              'REP', 'RLC', 'SNX', 'TKN', 'TUSD', 'USDC', 'USDT', 'ZRX']

    #
    # PAX #9 by  market_cap	    ADD THIS TO ORDER SPLITTING
    # MCO #24 by  market_cap	ADD THIS TO ORDER SPLITTING
    # NEXO #25 by  market_cap	ADD THIS TO ORDER SPLITTING
    # SNT #33 by  market_cap	ADD THIS TO ORDER SPLITTING
    for r, t in sorted(tokens_by_market_cap):
        add = 'ADD THIS TO ORDER SPLITTING' if r < 100 and t not in OS_TOKENS else ''
        print(f"{t} #{r} by market_cap\t{add}")




########################################################################################################################
# main
# get_best_tokens_for_dexs()
tradable_tokens_by_volume()
# tradable_tokens_by_market_cap()


