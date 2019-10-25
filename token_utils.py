import functools
import requests


# get tokens
@functools.lru_cache(1)
def tokens():
    return { t['symbol']: t['address'] for t in tokens_json() }

@functools.lru_cache(1)
def tokens_by_addr():
    return { addr: sym for sym, addr in tokens().items() }

@functools.lru_cache(1)
def token_decimals():
    return { t['symbol']: t['decimals'] for t in tokens_json() }

def ten_to_the_decimals(token):
    return 10 ** token_decimals()[token]

def canonical_symbol(symbol):
    """Returns the canonical symbol name for the given symbol if it is one of the listed tokens, else None"""
    sym = symbol.upper()
    return sym if sym in tokens() else None

LOW_VOLUME_TOKENS = ['CVC', 'DATA', 'TUSD', 'SNT', 'GNO']
@functools.lru_cache(1)
def top_tokens():
    """Returns the tokens listed in Totle's data/pairs API endpoint"""
    r = requests.get('https://api.totle.com/data/pairs').json()
    if r['success']:
        return [ base for base, quote in r['response'] if quote == 'ETH' and base not in LOW_VOLUME_TOKENS ] # filters out DAI pairs and low-volume tokens
    else:
        raise ValueError(f"{r['name']} ({r['code']}): {r['message']}")


@functools.lru_cache(1)
def tokens_json():
    """Returns the tokens json filtering out non-tradable tokens"""
    # For now we'll just use Totle's view of the ERC-20 world. Eventually we can include data from 1-Inch etc.
    r = requests.get('https://api.totle.com/tokens').json()

    # Totle is currently only returning tradable tokens, so there is no need for this filter
    return list(filter(lambda t: t['tradable'], r['tokens']))


def addr(token):
    """Returns the string address that identifies the token"""
    return tokens()[token]

def int_amount(float_amount, token):
    """Returns the integer amount of token units for the given float_amount and token"""
    return int(float(float_amount) * ten_to_the_decimals(token))

def real_amount(int_amount, token):
    """Returns the decimal number of tokens for the given integer amount and token"""
    return int(int_amount) / ten_to_the_decimals(token)

