import json
import token_utils
import requests


def test_basics():
    print("\n", token_utils.tokens_json())
    print("\n", token_utils.tokens())
    print("\n", token_utils.token_decimals())
    print("\n", token_utils.select_tokens())
    print("\n", token_utils.tradable_tokens())

def test_token_functions(token='ETH'):
    print("\n", token_utils.ten_to_the_decimals(token))
    print("\n", token_utils.tokens_by_addr())
    print("\n", token_utils.addr(token))
    print("\n", token_utils.int_amount(1.2, token))
    print("\n", token_utils.real_amount(123456789, token))

def test_int_amount_on_range_of_floats():
    trade_sizes = list(map(lambda x: x * 0.2, range(1,5)))
    for ts in trade_sizes:
        amt = token_utils.int_amount(ts, 'ETH')
        print(f"\n\n{ts} ETH => {amt}")

def test_find_duplicates():
    print(f"\nlen(token_utils.tokens()) = {len(token_utils.tokens())}" )
    print(f"\nlen(token_utils.tokens_by_addr()) = {len(token_utils.tokens_by_addr())}" )

    for s, a in token_utils.tokens().items():
        # if s.upper() != s: print(f"token_utils: {s.upper()} != {s}")
        lookup_sym = token_utils.tokens_by_addr().get(a)
        if not lookup_sym:
            print(f"{s} address {a} is not in addr")
        else:
            if s != lookup_sym: print(f"token_utils: addr->{lookup_sym} but tokens->{s}")

    tu_syms = [s for s in token_utils.tokens()]
    print(f"\nduplicate symbols in tokens(): {set([s for s in tu_syms if tu_syms.count(s) > 1])}")


# Below is code to compare Totle's tokens endpoint to 1-Inch's
def compare_totle_to_oneinch(verbose=False):
    import oneinch_client

    cmp_client = oneinch_client
    cmp_name = cmp_client.name()

    tu_tokens_json = token_utils.tokens_json()
    # print("Totle\n", json.dumps(tu_tokens_json, indent=3))

    cmp_tokens_json = requests.get(oneinch_client.TOKENS_ENDPOINT).json()
    # print(f"{cmp_name}\n", json.dumps(cmp_tokens_json, indent=3))

    oneinch_names = {
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
    overlap = []
    for t in tu_tokens_json:
        symbol, address, decimals = t['symbol'], t['address'], t['decimals']
        symbol = oneinch_names.get(symbol, symbol) # translate some symbols to 1-Inch names
        if cmp_tokens_json.get(symbol):
            overlap.append(symbol)
            overlap_cnt += 1
            cmp = cmp_tokens_json[symbol]
            cmp_addr, tot_addr = cmp['address'].lower(), address.lower()
            if cmp['symbol'] != symbol: print(f"{symbol}: symbol mismatch. Totle={symbol} {cmp_name}={cmp['symbol']}")
            if cmp_addr != tot_addr: print(f"{symbol}: address mismatch. Totle={tot_addr} {cmp_name}={cmp_addr}")
            if cmp['decimals'] != decimals: print(f"{symbol}: decimals mismatch. Totle={decimals} {cmp_name}={cmp['decimals']}")

            # for s in ['MLN', 'LRC', 'NEXO']:
            if cmp['symbol'] != symbol or cmp_addr != tot_addr or cmp['decimals'] != decimals:
                print("Totle\n", json.dumps(t, indent=3))
                print(f"{cmp_name}\n", json.dumps(cmp, indent=3))

        else:
            if verbose: print(f"{oneinch_client.name()} does not have {symbol}")

    mapped_tu_tokens = [ oneinch_names.get(t['symbol'], t['symbol']) for t in tu_tokens_json ]
    for symbol in cmp_tokens_json:
        if symbol not in mapped_tu_tokens: print(f"{symbol} is listed by {oneinch_client.name()} but not Totle", json.dumps(cmp_tokens_json[symbol]))

    print(f"Out of {len(tu_tokens_json)} tokens listed in token_utils and {len(cmp_tokens_json)} tokens listed by {oneinch_client.name()}, {overlap_cnt} are listed by both")
    print(f"duplicate symbols: {set([s for s in overlap if overlap.count(s) > 1])}")

# test_basics()
# test_token_functions('ETH')
# test_int_amount_on_range_of_floats()
# compare_totle_to_oneinch()

test_find_duplicates()


