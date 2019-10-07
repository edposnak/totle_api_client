import v2_client
from collections import defaultdict
from datetime import datetime

##############################################################################################
#
# functions to compute and print price differences
#

def compare_prices(token, supported_pairs, non_liquid_tokens, liquid_dexs, params=None, verbose=True, debug=False):
    """Returns a dict containing Totle and other DEX prices"""

    savings = {}
    from_token, to_token, bidask = ('ETH', token, 'ask') if params['orderType'] == 'buy' else (token, 'ETH', 'bid')
    k_params = {'params': params, 'verbose': verbose, 'debug': debug }
    totle_ex = v2_client.TOTLE_EX
    
    # Get the best price using Totle's aggregated order books
    totle_sd = v2_client.try_swap(totle_ex, from_token, to_token, **k_params)

    if totle_sd:
        totle_used = totle_sd['totleUsed']
        swap_prices = {totle_ex: totle_sd['price']}

        for dex, pair in totle_sd['dexPairs'].items():
            supported_pairs[dex].append(pair)

        # Compare to best prices from other DEXs
        # don't compare to the one that Totle used, unless Totle used multiple DEXs
        dexs_to_compare = [ dex for dex in liquid_dexs if dex != totle_used[0] or len(totle_used) > 1 ]
        for dex in dexs_to_compare:
            dex_sd = v2_client.try_swap(dex, from_token, to_token, exchange=dex, **k_params)
            if dex_sd:
                swap_prices[dex] = dex_sd['price']
                if swap_prices[dex] < 0.0:
                    raise ValueError(f"{dex} had an invalid price={swap_prices[dex]}")
                supported_pairs[dex].append([from_token, to_token])

        other_dexs = [k for k in swap_prices if k != totle_ex]
        if other_dexs:  # there is data to compare
            totle_price = swap_prices[totle_ex]
            for e in other_dexs:
                ratio = totle_price/swap_prices[e] # totle_price assumed lower
                pct_savings = 100 - (100.0 * ratio)
                savings[e] = {'time': datetime.now().isoformat(), 'action': params['orderType'], 'pct_savings': pct_savings, 'totle_used': '/'.join(totle_used), 'totle_price': totle_price, 'exchange_price': swap_prices[e]}
                print(f"Totle saved {pct_savings:.2f} percent vs {e} {params['orderType']}ing {token} on {totle_used} trade size={params['tradeSize']} ETH")
        else:
            print(f"Could not compare {token} prices. Only valid price was {swap_prices}")
            # although we'll likely get the same result at higher trade sizes, don't over-
            # optimize. Past data shows there are more liquid tokens at higher trade sizes
            # than what we get with this optimization
            # non_liquid_tokens.append(token) 
    else:
        non_liquid_tokens.append(token)

    return savings

def print_average_savings(all_savings):
    for trade_size in all_savings:
        print(f"\nAverage Savings trade size = {trade_size} ETH vs")
        print_average_savings_by_dex(all_savings[trade_size])

def print_average_savings_by_dex(avg_savings):
    dex_savings = defaultdict(list)

    for token_savings in [ avg_savings[token] for token in avg_savings ]:
        for dex in token_savings:
            dex_savings[dex].append(token_savings[dex]['pct_savings'])

    for dex in dex_savings:
        sum_savings, n_samples = sum(dex_savings[dex]), len(dex_savings[dex])
        if n_samples:
            print(f"   {dex}: {sum_savings/n_samples:.2f}% ({n_samples} samples)")
        else:
            print(f"   {dex}: - (no samples)")

    return dex_savings



