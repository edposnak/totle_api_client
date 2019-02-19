import http.client
import json
import requests

##############################################################################################
#
# Library functions for exchanges, tokens, and prices
#
# get exchanges
r = requests.get('https://services.totlesystem.com/exchanges').json()
exchanges = { e['name']: e['id'] for e in r['exchanges'] }
exchange_by_id = { e['id']: e['name'] for e in r['exchanges'] }


# get tokens
r = requests.get('https://services.totlesystem.com/tokens').json()
tokens = { t['symbol']: t['address'] for t in r['tokens'] if t['tradable']}
token_symbols = { t['address']: t['symbol'] for t in r['tokens'] if t['tradable']}
token_decimals = { t['symbol']: t['decimals'] for t in r['tokens'] if t['tradable']}
ETH_ADDRESS = "0x0000000000000000000000000000000000000000" 

def addr(token):
    """Returns the string address that identifies the token"""
    # convert 'ETH' and 'WETH' to addr 0x000... in anticipation of fix to swap
    return ETH_ADDRESS if token in ['ETH', 'WETH'] else tokens[token]

def int_amount(float_amount, token):
    """Returns the integer amount of token units for the given float_amount and token"""
    return int(float(float_amount) * (10**token_decimals[token]))

def real_amount(int_amount, token):
    """Returns the decimal number of tokens for the given integer amount and token"""
    return int(int_amount) / (10**token_decimals[token])

# get all token prices on all exchanges
all_prices = requests.get('https://services.totlesystem.com/tokens/prices').json()['response']

# We assume that the prices endpoints returns the lowest 'ask' and highest 'bid' price for
# a given token. If it does not, then that would explain why rebalance returns orders
# with lower prices than the ask price
def price(token, exchange):
    """Returns lowest ask price in ETH for the given token on the given exchange"""
    return all_prices[tokens[token]][str(exchanges[exchange])]['ask']

def best_ask_price(token):
    """Returns lowest ask price in ETH for the given token across all exchanges"""
    ap = all_prices[tokens[token]]
    return min([ float(ap[v]['ask']) for v in ap ])

def best_bid_price(token):
    """Returns highest bid price in ETH for the given token across all exchanges"""
    ap = all_prices[tokens[token]]
    return max([ float(ap[v]['bid']) for v in ap ])

def best_prices(token, bidask='ask'):
    """Returns lowest ask or highest bid prices in ETH for all exchanges"""
    token_prices = all_prices[tokens[token]]
    return { exchange_by_id[int(i)]: token_prices[i][bidask] for i in token_prices }

def show_prices(from_token, to_token):
    if from_token == 'ETH':
        print(f"Lowest ask prices for {to_token}: {pp(best_prices(to_token, 'ask'))}")
    elif to_token == 'ETH':
        print(f"Highest bid prices for {from_token}: {pp(best_prices(from_token, 'bid'))}")
    else:
        # once ERC20/ERC20 swaps, which have both buys and sells, are supported by the swap_data
        # extractor method, then we can get rid of the exception below and do something useful
        raise Exception("ERC20/ERC20 swaps haven't been implemented yet")

def wei_to_eth(wei_amount):
    """Returns a decimal value of the amount of ETH for the given wei_amount"""
    return int(wei_amount) / 10**18

def pp(data):
    return json.dumps(data, indent=3)


##############################################################################################
#
# functions to call swap/rebalance and extract data
#
def swap_data(response):
    """Extracts relevant data from a swap/rebalance API endpoint response"""
    summary = response['summary']
    buys, sells = summary['buys'], summary['sells']

    if len(buys) + len(sells) == 0: # Suggester has no orders
        return {}


    # This method assumes the summary includes either a single buy or sell, i.e. that rebalance 
    # was called with a single buy or sell or (someday) that swap was called with an ETH pair
    # This method would need to be modified to handle results from a call to swap with an
    # ERC20/ERC20 pair, which would contain both buys and sells.
    if len(buys) + len(sells) > 1:
        err_msg = f"expected payload to have either 1 buy or 1 sell, but it has {len(buys)} buys and {len(sells)} sells.\nresponse={pp(response)}"
        raise Exception(err_msg)

    action, bsd = ("buy", buys[0]) if buys else ("sell", sells[0])

    token_sym = token_symbols[bsd['token']]

    x = real_amount(bsd['amount'], token_sym)
    
    return {
        "action": action,
        "weiAmount": int(response['ethValue']),
        "ethAmount": wei_to_eth(response['ethValue']),
        "token": bsd['token'],
        "tokenSymbol": token_sym,
        "exchange": bsd['exchange'],
        "price": float(bsd['price']),
        "intAmount": int(bsd['amount']),
        "realAmount": x,
        "fee": bsd['fee']
    }

def call_swap(from_token, to_token, exchange=None, debug=None):
    """Calls the swap API endpoint with the given token pair and whitelisting exchange if given. Returns the result as a swap_data dict """
    # the swap_data dict is defined by the return statement in swap_data method above

    from_token_addr = addr(from_token)
    to_token_addr = addr(to_token)

    if from_token_addr == ETH_ADDRESS and to_token_addr == ETH_ADDRESS:
        raise Exception('from_token and to_token cannot both be ETH')

    if from_token_addr != ETH_ADDRESS and to_token_addr != ETH_ADDRESS:
        swap_endpoint = 'https://services.totlesystem.com/swap'
        real_amount_to_sell = 1.0 / best_bid_price(from_token)
        amount_to_sell = int_amount(real_amount_to_sell, from_token)
        if debug: print(f"selling {real_amount_to_sell} {from_token} tokens ({amount_to_sell} units)")
        swap_inputs = {
            "swap": {
                "from": from_token_addr,
                "to": to_token_addr,
                "amount": amount_to_sell
            },
        }
    
    else: # for now we have to call the rebalance endpoint because swap doesn't support ETH
        swap_endpoint = 'https://services.totlesystem.com/rebalance'

        if from_token_addr == ETH_ADDRESS and to_token_addr != ETH_ADDRESS:
            real_amount_to_buy = 1.0 / best_ask_price(to_token)
            amount_to_buy = int_amount(real_amount_to_buy, to_token)
            if debug: print(f"buying {real_amount_to_buy} {to_token} tokens ({amount_to_buy} units)")
            swap_inputs = {
                "buys": [ {
                    "token": addr(to_token),
                    "amount": amount_to_buy
                } ],
            }

        else: # from_token_addr != ETH_ADDRESS and to_token_addr == ETH_ADDRESS
            real_amount_to_sell = 1.0 / best_bid_price(from_token)
            amount_to_sell = int_amount(real_amount_to_sell, from_token)
            if debug: print(f"selling {real_amount_to_sell} {from_token} tokens ({amount_to_sell} units)")
            swap_inputs = {
                "sells": [ {
                    "token": addr(from_token),
                    "amount": amount_to_sell
                } ],
            }
            
    wallet_addr = { "address": "0xD18CEC4907b50f4eDa4a197a50b619741E921B4D" }
    swap_inputs = {**swap_inputs, **wallet_addr}
    
    if exchange: # whitelist the given exchange
        exchange_wl = { "exchanges": { "list": [ exchanges[exchange] ], "type": "white" } }
        swap_inputs = {**swap_inputs, **exchange_wl}
        
    swap_inputs = pp(swap_inputs)
    if debug: print(f"REQUEST to {swap_endpoint}:\n{swap_inputs}\n\n")

    r = requests.post(swap_endpoint, data=swap_inputs).json()

    if r['success']:
        return swap_data(r['response'])
    else:
        raise Exception(r['response'])

def print_results(label, sd):
    """Prints a formatted results string based on given label and swap_data sd"""
    # This should ultimately be used to send output to a CSV or some file that calculations
    # can be run on 
    print(f"{label}: {sd['action']} {sd['realAmount']} {sd['tokenSymbol']} for {sd['ethAmount']} ETH on {sd['exchange']} price={sd['price']} fee={sd['fee']}")


    
##############################################################################################
#
# Main program
#

DEBUG = False

TOKENS_TO_BUY = [ 'BNB', 'DAI', 'MKR', 'OMG', 'BAT', 'REP', 'ZRX', 'AE', 'ZIL', 'SNT', 'LINK' ]

# For now, all price comparisons are done by buying the ERC20 token with ETH (i.e. from_token == 'ETH')
from_token = 'ETH'

for to_token in TOKENS_TO_BUY:
    print(f"\n\n----------------------------------------\n{to_token}")
    if to_token not in tokens:
        print(f"'{to_token}' is not a listed token or is not tradable")
        continue
    show_prices(from_token, to_token)

    # Get the best price using Totle's aggregated order books
    totle_sd = call_swap(from_token, to_token, debug=DEBUG)
    if DEBUG: print(pp(totle_sd))
    if totle_sd:
        print_results('Totle', totle_sd)
        price_comparisons = {'Totle': totle_sd['price']}
        
        # Compare to best prices from other DEXs 
        for dex in best_prices(totle_sd['tokenSymbol']):
            if dex != totle_sd['exchange']:
                dex_sd = call_swap(from_token, to_token, dex, debug=DEBUG)
                if dex_sd:
                    print_results(dex, dex_sd)
                    price_comparisons[dex] = dex_sd['price']
                else:
                    print(f"{dex}: Suggester returned no orders for {from_token}->{to_token}")

    else:
        print(f"Totle: Suggester returned no orders for {from_token}->{to_token}")
            
