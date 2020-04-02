import sys
import csv
from collections import defaultdict
from datetime import datetime

import exchange_utils
import totle_client

# Common struct returned by compare_dex_prices and compare_cex_prices
def savings_data(order_type, trade_size, token, exchange, pct_savings, totle_used, totle_price, exchange_price,
                 splits=None, totle_splits=None, ex_prices=None, quote_token=None, response_id=None):
    """Returns a savings entry suitable for logging or appending to CSV"""
    # CSV header=time, action, trade_size, token, exchange, exchange_price, totle_used, totle_price, pct_savings, splits, ex_prices
    return {
        'time': datetime.now().isoformat(),
        'id': response_id,
        'action': order_type,
        'trade_size': trade_size,
        'token': token,
        'quote': quote_token,
        'exchange': exchange,
        'exchange_price': exchange_price,
        'totle_used': '/'.join(totle_used),
        'totle_price': totle_price,
        'pct_savings': pct_savings,
        'splits': splits,
        'totle_splits': totle_splits,
        'ex_prices': ex_prices
    }


##############################################################################################
#
# DEX functions to compute and print price differences
#

def compare_dex_prices(token, supported_pairs, non_liquid_tokens, liquid_dexs, order_type, params=None, verbose=True, debug=False):
    """Returns a dict of dex: savings_data for Totle and other DEXs"""

    kw_params = { k:v for k,v in vars().items() if k in ['params', 'verbose', 'debug'] }
    savings = {}
    # TODO: replace token with from_token, to_token
    if order_type == 'buy':
        trade_size = params['fromAmount']
        from_token, to_token, bidask = ('ETH', token, 'ask')
    elif order_type == 'sell':
        trade_size = params['toAmount']
        from_token, to_token, bidask = (token, 'ETH', 'bid')
    else:
        raise ValueError(f"order_type must be either 'buy' or 'sell'")

    totle_ex = totle_client.name()
    
    # Get the best price using Totle's aggregated order books
    totle_sd = totle_client.try_swap(totle_ex, from_token, to_token, **kw_params)

    if totle_sd:
        totle_used = totle_sd['totleUsed']
        swap_prices = {totle_ex: totle_sd['price']}

        # we only need to pre-populate of if len(totle_used) <= 1, otherwise dexs_to_compare will include all dexes
        if len(totle_used) == 1: supported_pairs[totle_used[0]].append([from_token, to_token])

        # Compare to best prices from other DEXs
        # don't compare to the one that Totle used, unless Totle used multiple DEXs
        dexs_to_compare = [ dex for dex in liquid_dexs if dex != totle_used[0] or len(totle_used) > 1 ]
        for dex in dexs_to_compare:
            dex_sd = totle_client.try_swap(dex, from_token, to_token, exchange=dex, **kw_params)
            if dex_sd:
                swap_prices[dex] = dex_sd['price']
                if swap_prices[dex] < 0.0:
                    raise ValueError(f"{dex} had an invalid price={swap_prices[dex]}")
                supported_pairs[dex].append([from_token, to_token])

        other_dexs = [k for k in swap_prices if k != totle_ex]
        if other_dexs:  # there is data to compare
            totle_price = swap_prices[totle_ex]
            for e in other_dexs:
                # totle_price assumed lower
                pct_savings = get_pct_savings(totle_price, swap_prices[e])
                savings[e] = get_savings(e, swap_prices[e], totle_sd, token, trade_size, order_type, quote_token='ETH', print_savings=True)

                print(f"Totle saved {pct_savings:.2f} percent vs {e} {order_type}ing {token} on {totle_used} trade size={trade_size} ETH")
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


##############################################################################################
#
# CEX functions to extract orders from books and compare prices
#

def get_orders(trade_size, book):
    """returns the set of orders from book that will spend the given trade_size of quote tokens."""
    book_total = sum([p * q for p, q in book])
    if trade_size > book_total:
        raise ValueError(f"not enough orders trade_size={trade_size} book total={book_total}")

    orders, total = [], 0.0
    for p, q in book:
        if total + p * q < trade_size:
            orders.append((p, q))
            total += p * q
        else:
            # The last order may be partially filled to get the exact trade_size
            orders.append((p, (trade_size - total) / p))
            return orders

def best_price(trade_size, book):
    """returns the price (in quote token) for taking the top orders in the book to satisfy trade_size"""
    orders = get_orders(trade_size, book)
    n_base = sum([q for p, q in orders])
    n_quote = sum([q * p for p, q in orders])
    # return len(orders), n_base, n_quote
    return n_quote / n_base  # e.g 0.5 ETH / 100 DAI = 0.005 ETH / DAI

def best_price_with_fees(trade_size, book, buysell, fee_pct):
    """returns the best price in *spent* token unless using book and accounting for exchange fees"""
    p = best_price(trade_size, book) # this is always denominated in quote token
    markup = 1 + (fee_pct / 100)
    if buysell == 'buy':  # assume user pays fee_pct more quote tokens
        # e.g. buy DAI with ETH at 10% fee: price (in ETH) = 0.005 * 1.1 = 0.0055 # user has to pay 10% more ETH
        return p * markup
    else:  # assume user pays fee_pct more base tokens
        # e.g. sell DAI for ETH with 10% fee: price (in DAI) = (1.1 * (1 / .005)) # user has to pay 10% more DAI
        return markup / p

def get_from_to_params(order_type, base, quote, trade_size):
    """returns base, quote ordered as from, to based on order_type"""
    # buy: selling from (from) quote tokens to buy (to) base tokens
    # sell: selling (from) base tokens to buy (to) quote tokens
    from_token, to_token = (quote, base) if order_type == 'buy' else (base, quote)

    if order_type == 'buy':
        from_token, to_token = (quote, base)
        params = {'fromAmount': trade_size}
    elif order_type == 'sell':
        from_token, to_token = (base, quote)
        params = {'toAmount': trade_size}
    else:
        raise ValueError(f"order_type must be 'buy' or 'sell'")

    return from_token, to_token, params


def get_cex_savings(cex_client, order_type, pairs, trade_sizes, redirect=True):
    """Returns a dict of token: { trade_size: savings } for various tokens and trade_sizes"""
    filename = get_filename_base(suffix=order_type)  # TODO add cex_client.name() prefix
    if redirect: redirect_stdout(filename)

    all_savings = defaultdict(lambda: defaultdict(dict))
    with SavingsCSV(filename) as csv_writer:
        for base, quote in sorted(pairs):
            try:
                bids, asks = cex_client.get_depth(base, quote)
                book = asks if order_type == 'buy' else bids
                for trade_size in trade_sizes:
                    cex_price = best_price_with_fees(trade_size, book, order_type, cex_client.fee_pct())
                    savings = compare_to_totle(base, quote, order_type, trade_size, cex_client.name(), cex_price)
                    if savings:
                        all_savings[base][trade_size] = savings
                        csv_writer.append(savings)
            except ValueError as e:
                print(f"Compare {base}/{quote} raised {e}")

    return all_savings

def compare_to_totle(base, quote, order_type, trade_size, exchange, ex_price, splits=None):
    """Returns a savings_data dict comparing price (in *spent* token) to totle's price"""
    from_token, to_token, params = get_from_to_params(order_type, base, quote, trade_size)
    totle_sd = totle_client.try_swap(totle_client.name(), from_token, to_token, params=params, verbose=False)
    if totle_sd:
        return get_savings(exchange, ex_price, totle_sd, base, trade_size, order_type, splits)
    else:
        print(f"Compare {order_type} {base}/{quote} trade size={trade_size} got no result from Totle")

def get_savings(exchange, exchange_price, totle_sd, token, trade_size, order_type, splits=None, ex_prices=None, quote_token=None, print_savings=True):
    response_id = totle_sd['responseId']
    totle_price = totle_sd['price']
    totle_used = totle_sd['totleUsed']

    totle_splits = canonicalize_and_sort_splits(totle_sd.get('totleSplits'))

    pct_savings = get_pct_savings(totle_price, exchange_price)
    if print_savings:
        trade_info = f"trade size={trade_size} ETH (Totle price={totle_price:.5g} {exchange} price={exchange_price:.5g})"
        if splits: trade_info += f" splits={splits}"
        if totle_splits: trade_info += f" totle_splits={totle_splits}"
        print(f"Totle saved {pct_savings:.2f} percent vs {exchange} {order_type}ing {token} on {','.join(totle_used)} {trade_info}")
    return savings_data(order_type, trade_size, token, exchange, pct_savings, totle_used, totle_price, exchange_price,
                        splits=splits, totle_splits=totle_splits, ex_prices=ex_prices, quote_token=quote_token, response_id=response_id)


def canonicalize_and_sort_splits(raw_splits):
    """Canonicalizes any DEX named in Totle splits"""

    h = eval(raw_splits or '{}') if isinstance(raw_splits, str) else raw_splits

    if is_multi_split(h):
        return {pair: sorted_splits(flat_split) for pair, flat_split in h.items()}
    else:
        return sorted_splits(h)

def sorted_splits(flat_splits):
    a_splits = exchange_utils.canonical_keys(flat_splits)
    return { k:round(v) for k, v in sorted(a_splits.items()) }

def is_multi_split(totle_splits):
    """ returns True if there are multiple splits keyed by pair e.g. {'BAT/ETH': {'Kyber':90, 'Uniswap':10}, 'ETH/DAT': {...}}"""
    return bool(totle_splits) and type(list(totle_splits.values())[0]) == dict



def print_savings(order_type, savings, trade_sizes, title="Savings"):
    """Prints a savings dict, token => trade_size => savings values"""
    ph = lambda x: f"{x:>8}"
    pf = lambda x: f"{x:>8.2f}"
    print(f"\n{title}\n{order_type.upper():<8}", ''.join(map(ph, trade_sizes)))
    for base, ts_savings in savings.items():
        vals = [ ts_savings.get(ts) for ts in trade_sizes ]
        str_vals = [pf(v['pct_savings']) if v else ph('-') for v in vals]
        print(f"{base:<8}", ''.join(str_vals))

def get_pct_savings(base_price, competitor_price):
    return 100 - (100.0 * base_price / competitor_price)

##############################################################################################
#
# CSV methods
#

CSV_FIELDS = "time action trade_size token exchange exchange_price totle_used totle_price pct_savings splits".split()

def get_filename_base(dir='outputs', prefix=None, suffix=None):
    prefix_str = f"{prefix}_" if prefix else ''
    suffix_str = f"_{suffix}" if suffix else ''
    d = datetime.today()
    return f"{dir}/{prefix_str}{d.year}-{d.month:02d}-{d.day:02d}_{d.hour:02d}:{d.minute:02d}:{d.second:02d}{suffix_str}"


class SavingsCSV():
    def __init__(self, filename, fieldnames=CSV_FIELDS):
        self.filename = filename if filename.endswith('.csv') else filename + '.csv'
        self.fieldnames = fieldnames

    def __enter__(self):
        self.csvfile = open(self.filename, 'w', newline='') 
        self.csv_writer = csv.DictWriter(self.csvfile, fieldnames=self.fieldnames)
        self.csv_writer.writeheader()
        return self

    def append(self, savings):
        self.writerow(savings)

    def writerow(self, rowdict):
        self.csv_writer.writerow(rowdict)
        self.csvfile.flush()
        
    def writerows(self, rowdicts):
        for r in rowdicts: self.writerow(r)

    def __exit__(self, type, value, traceback):
        self.csvfile.close()

##############################################################################################
#
# txt file methods
#

def redirect_stdout(filename):
    """Redirects console output to a .txt file in outputs directory"""
    output_filename = filename if filename.endswith('.txt') else filename + '.txt'
    print(f"sending output to {output_filename} ...")
    sys.stdout = open(output_filename, 'w')


