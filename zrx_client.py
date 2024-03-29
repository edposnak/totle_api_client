import json
import sys
import functools
import requests
import token_utils

# https://0x.org/docs/api
API_BASE = 'https://api.0x.org'
TOKENS_ENDPOINT = API_BASE + '/swap/v0/tokens'
SWAP_ENDPOINT = API_BASE + '/swap/v0/quote'

TAKER_FEE_PCT = 0.0 # unknown fees

class ZrxAPIException(Exception):
    pass

def name():
    return '0x'

def fee_pct():
    return TAKER_FEE_PCT


##############################################################################################
#
# API calls
#


# get quote
def get_quote(from_token, to_token, from_amount=None, to_amount=None, dex=None, verbose=False, debug=False):
    return get_swap(from_token, to_token, from_amount=from_amount, to_amount=to_amount, dex=dex, verbose=verbose, debug=debug)


def get_swap(from_token, to_token, from_amount=None, to_amount=None, dex=None, from_address=None, slippage=50, verbose=False, debug=False):
    """Returns the price in terms of the from_token - i.e. how many from_tokens to purchase 1 to_token"""

    # Request: from ETH to DAI
    # https://api.0x.org/swap/v0/quote?buyToken=DAI&sellToken=ETH&buyAmount=1000000000000000000

    query = {'sellToken': from_token, 'buyToken': to_token, 'slippagePercentage': slippage / 100}  # slippagePercentage is really just a fraction (default = 0.01)
    if from_amount and to_amount:
        raise ValueError(f"{name()} only accepts either from_amount or to_amount, not both")
    elif from_amount:
        query['sellAmount'] = token_utils.int_amount(from_amount, from_token)
    elif to_amount:
        query['buyAmount'] = token_utils.int_amount(to_amount, to_token)
    else:
        raise ValueError(f"{name()}: either from_amount or to_amount must be specified")

    if from_address:
        query['takerAddress'] = from_address

    if debug: print(f"REQUEST to {SWAP_ENDPOINT}:\n{json.dumps(query, indent=3)}\n\n")
    r = None
    try:
        r = requests.get(SWAP_ENDPOINT, params=query)
        j = r.json()
        if debug: print(f"RESPONSE from {SWAP_ENDPOINT}:\n{json.dumps(j, indent=3)}\n\n")

        # Response:
        # {
        #   "price": "0.00607339681846613",
        #   "to": "0x61935cbdd02287b511119ddb11aeb42f1593b7ef",
        #   "data": "0x8bc8efb3000000..."
        #   "value": "750000000000000",
        #   "gasPrice": "5000000000",
        #   "protocolFee": "750000000000000",
        #   "buyAmount": "100000000000000000",
        #   "sellAmount": "607339681846613",
        #   "orders": []


        if not j.get('price'):
            if verbose: print(f"FAILURE RESPONSE from {SWAP_ENDPOINT}:\n{json.dumps(j, indent=3)}\n\n")
            return {}

        zrx_price = float(j['price'])
        # We always want to return price in terms of how many from_tokens for 1 to_token, which means we need to
        # invert 0x's price whenever from_amount is specified.
        price = 1 / zrx_price if from_amount else zrx_price

        source_amount = token_utils.real_amount(j['sellAmount'], from_token)
        destination_amount = token_utils.real_amount(j['buyAmount'], to_token)

        fee_amount = token_utils.real_amount(j['protocolFee'], from_token)
        if verbose: print(f"0x fee = {100 * fee_amount/source_amount:.4f}%")

        exchanges_parts = {}
        for source in j['sources']:
            exchanges_parts[source['name']] = 100 * float(source['proportion'])

        payload = j['orders']

        return {
            'source_token': from_token,
            'source_amount': source_amount,
            'destination_token': to_token,
            'destination_amount': destination_amount,
            'price': price,
            'exchanges_parts': exchanges_parts,
            'payload': payload,
            # 'exchanges_prices': exchanges_prices
        }

    except (ValueError, requests.exceptions.RequestException) as e:
        print(f"{name()} {query} raised {e}: {r.text[:128] if r else 'no JSON returned'}")
        return {}

