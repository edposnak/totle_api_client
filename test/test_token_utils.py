import json
import token_utils
import requests

token = 'ETH'

print(token_utils.tokens_json())
print(token_utils.tokens())
print(token_utils.token_decimals())
print(token_utils.ten_to_the_decimals(token))
print(token_utils.tokens_by_addr())
print(token_utils.addr(token))

print(token_utils.int_amount(1.2, token))
print(token_utils.real_amount(123456789, token))

print("\n\n", token_utils.top_tokens())
exit(0)

# Below is code to compare Totle's tokens endpoint to 1-Inch's

import oneinch_client

cmp_client = oneinch_client
cmp_name = cmp_client.name()

totle_tokens_json = token_utils.tokens_json()
# print("Totle\n", json.dumps(totle_tokens_json, indent=3))

cmp_tokens_json = requests.get(oneinch_client.TOKENS_ENDPOINT).json()
# print(f"{cmp_name}\n", json.dumps(cmp_tokens_json, indent=3))

SYMBOL_MAP = {
    'CDAI': 'cDAI',
    'CBAT': 'cBAT',
    'CETH': 'cETH',
    'CREP': 'cREP',
    'CUSDC': 'cUSDC',
    'CWBTC': 'cWBTC',
    'CZRX': 'cZRX',
    'IDAI': 'iDAI',
    'SETH': 'sETH',
    'IUSDC': 'iUSDC',
    'IETH': 'iETH',
    'IWBTC': 'iWBTC',
    'ILINK': 'iLINK',
    'IZRX': 'iZRX',
    'IREP': 'iREP',
    'IKNC': 'iKNC',
}

overlap_cnt = 0


for t in totle_tokens_json:
    symbol, address, decimals = t['symbol'], t['address'], t['decimals']
    symbol = SYMBOL_MAP.get(symbol, symbol) # translate some symbols to 1-Inch names
    if cmp_tokens_json.get(symbol):
        overlap_cnt += 1
        cmp = cmp_tokens_json[symbol]
        if cmp['symbol'] != symbol: print(f"{symbol}: symbol mismatch. Totle={symbol} {cmp_name}={cmp['symbol']}")
        if cmp['address'].lower() != address: print(f"{symbol}: address mismatch. Totle={address} {cmp_name}={cmp['address']}")
        if cmp['decimals'] != decimals: print(f"{symbol}: decimals mismatch. Totle={decimals} {cmp_name}={cmp['decimals']}")

        # for s in ['MLN', 'LRC', 'NEXO']:
        if cmp['symbol'] != symbol or cmp['address'].lower() != address or cmp['decimals'] != decimals:
            print("Totle\n", json.dumps(t, indent=3))
            print(f"{cmp_name}\n", json.dumps(cmp, indent=3))

    else:
        if True: print(f"{oneinch_client.name()} does not have {symbol}")

mapped_totle_tokens = [ SYMBOL_MAP.get(t['symbol'], t['symbol']) for t in totle_tokens_json ]
for symbol in cmp_tokens_json:
    if symbol not in mapped_totle_tokens: print(f"{symbol} is listed by {oneinch_client.name()} but not Totle", json.dumps(cmp_tokens_json[symbol]))

print(f"Out of {len(totle_tokens_json)} tokens listed by Totle and {len(cmp_tokens_json)} tokens listed by {oneinch_client.name()}, {overlap_cnt} are listed by both")
