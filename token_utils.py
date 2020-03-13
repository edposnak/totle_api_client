import functools
import threading
import requests

import oneinch_client


def addr(token):
    """Returns the string address that identifies the token"""
    token_addr = tokens().get(canonize(token))
    if not token_addr:
        raise ValueError(f"the symbol '{token}' was not found in the tokens list")
    else:
        return token_addr

def int_amount(float_amount, token):
    """Returns the integer amount of token units for the given float_amount and token"""
    return int(float(float_amount) * ten_to_the_decimals(canonize(token)))

def real_amount(int_amount, token):
    """Returns the decimal number of tokens for the given integer amount and token"""
    return int(int_amount) / ten_to_the_decimals(canonize(token))

def canonical_symbol(symbol):
    """Returns the canonical symbol name for the given symbol if it is one of the listed tokens, else None"""
    sym = canonize(symbol)
    return sym if sym in tokens() else None

def canonize(symbol):
    return symbol.upper()

LOW_VOLUME_TOKENS = ['CVC', 'DATA', 'TUSD', 'SNT', 'GNO']
@functools.lru_cache(1)
def select_tokens():
    """Returns the best tokens listed in Totle's data/pairs API endpoint"""
    r = requests.get('https://api.totle.com/data/pairs').json()
    if r['success']:
        return [ base for base, quote in r['response'] if quote == 'ETH' and base not in LOW_VOLUME_TOKENS ] # filters out DAI pairs and low-volume tokens
    else:
        raise ValueError(f"{r['name']} ({r['code']}): {r['message']}")

# get tokens
@functools.lru_cache(1)
def tokens():
    return { t['symbol']: t['address'] for t in tokens_json() }

@functools.lru_cache(1)
def tradable_tokens():
    return { t['symbol']: t['address'] for t in tokens_json() if t.get('tradable') }

@functools.lru_cache(1)
def tokens_by_addr():
    return { addr: sym for sym, addr in tokens().items() }

@functools.lru_cache(1)
def token_decimals():
    return { t['symbol']: t['decimals'] for t in tokens_json() }

def ten_to_the_decimals(token):
    return 10 ** token_decimals()[token]

tokens_json_lock = threading.Lock()
def tokens_json(use_oneinch_tokens=False):
    tokens_json_lock.acquire()
    j =  tokens_json_critical(use_oneinch_tokens)
    tokens_json_lock.release()
    return j

@functools.lru_cache(1)
def tokens_json_critical(use_oneinch_tokens=False):
    """Returns the tokens json from Totle and optionally 1-Inch"""
    print(f"************** EXECUTING tokens_json() ...")
    # get Totle tokens
    totle_tokens = totle_tokens_json()
    for t in totle_tokens: t['address'] = t['address'].lower()

    # 1-Inch has severe rate limiting without an API key, causing API calls to return 'Forbidden'
    if not use_oneinch_tokens: return totle_tokens

    # get 1-inch tokens
    oneinch_tokens = oneinch_tokens_json()
    for t in oneinch_tokens: t['address'] = t['address'].lower()

    # Combine Totle's and 1-Inch's info
    r, syms, addrs = totle_tokens, [ t['symbol'] for t in totle_tokens ], [ t['address'] for t in totle_tokens ]
    for t in oneinch_tokens:
        if not (t['symbol'] in syms or t['address'] in addrs):
            r.append(t) # Totle's info takes precendence
    return r

@functools.lru_cache(2)
def totle_tokens_json(canonical_symbols=True):
    # totle_client imports token_utils so we avoid a circular dependency by not using TOKENS_ENDPOINT
    # j = requests.get(totle_client.TOKENS_ENDPOINT).json()
    j = requests.get('https://api.totle.com/tokens').json()
    tokens = j['tokens']
    if canonical_symbols:
        for t in tokens: t['symbol'] = canonize(t['symbol'])
    return tokens

@functools.lru_cache(2)
def oneinch_tokens_json(canonical_symbols=True):
    j = requests.get(oneinch_client.TOKENS_ENDPOINT).json()
    tokens = list(j.values())
    if canonical_symbols:
        for t in tokens: t['symbol'] = canonize(t['symbol'])
    return tokens
