import json
import sys
import functools
import requests
import token_utils

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
    """Returns the price in terms of the from_token - i.e. how many from_tokens to purchase 1 to_token"""

    # Request: from ETH to DAI
    # https://api.0x.org/swap/v0/quote?buyToken=DAI&sellToken=ETH&buyAmount=1000000000000000000

    query = {'sellToken': from_token, 'buyToken': to_token}
    if from_amount:
        query['sellAmount'] = token_utils.int_amount(from_amount, from_token)
    elif to_amount:
        query['buyAmount'] = token_utils.int_amount(to_amount, to_token)
    else:
        raise ValueError(f"{name()} only accepts either from_amount or to_amount, not both")

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
        #   "data": "0x8bc8efb30000000000000000000000000000000000000000000000000000000000000060000000000000000000000000000000000000000000000000016345785d8a00000000000000000000000000000000000000000000000000000000000000000320000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000200000000000000000000000006924a03bb710eaf199ab6ac9f2bb148215ae9b5d0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000a258b39954cef5cb142fd567a46cddb31a670124000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000003e655571bd9a9c000000000000000000000000000000000000000000000000000061032c48dc4e09b200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000005e21158a0000000000000000000000000000000000000000000000000000016fb139642a00000000000000000000000000000000000000000000000000000000000001c00000000000000000000000000000000000000000000000000000000000000220000000000000000000000000000000000000000000000000000000000000022000000000000000000000000000000000000000000000000000000000000002200000000000000000000000000000000000000000000000000000000000000024f47261b00000000000000000000000006b175474e89094c44da98b954eedeac495271d0f000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000024f47261b0000000000000000000000000c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000421c3eeac38e15fda3618314cbf5ce23522edd06a51d11e8987fd67a852feadea2f564616f0e2c19da4d29737906e889372896868b5719443e683c750cd19f85e07403000000000000000000000000000000000000000000000000000000000000",
        #   "value": "750000000000000",
        #   "gasPrice": "5000000000",
        #   "protocolFee": "750000000000000",
        #   "buyAmount": "100000000000000000",
        #   "sellAmount": "607339681846613",
        #   "orders": []


        if not j.get('price'):
            print(json.dumps(j, indent=3))
            return {}

        zrx_price = float(j['price'])
        # We always want to return price in terms of how many from_tokens for 1 to_token, which means we need to
        # invert 0x's price whenever from_amount is specified.
        price = 1 / zrx_price if from_amount else zrx_price

        source_amount = token_utils.real_amount(j['sellAmount'], from_token)
        destination_amount = token_utils.real_amount(j['buyAmount'], to_token)

        return {
            'source_token': from_token,
            'source_amount': source_amount,
            'destination_token': to_token,
            'destination_amount': destination_amount,
            'price': price,
            'exchanges_parts': [],
            # 'exchanges_prices': exchanges_prices
        }

    except (ValueError, requests.exceptions.RequestException) as e:
        print(f"{name()} {query} raised {e}: {r.text[:128] if r else 'no JSON returned'}")
        return {}

