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
    token_utils.addr(token.lower()) # should not raise keyError
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

def test_missing():
    not_found_1203 = ['0xb4272071ecadd69d933adcd19ca99fe80664fc08', '0xc86d054809623432210c107af2e3f619dcfbf652',
                      '0x20f7a3ddf244dc9299975b4da1c39f8d5d75f05a', '0xea26c4ac16d4a5a106820bc8aee85fd0b7b2b664',
                      '0x2c4e8f2d746113d0696ce89b35f0d8bf88e0aeca', '0x5d60d8d7ef6d37e16ebabc324de3be57f135e0bc',
                      '0xfe5f141bf94fe84bc28ded0ab966c16b17490657', '0xf013406a0b1d544238083df0b93ad0d2cbe0f65f',
                      '0x14094949152eddbfcd073717200da82fed8dc960', '0x543ff227f64aa17ea132bf9886cab5db55dcaddf',
                      '0xc28e931814725bbeb9e670676fabbcb694fe7df2', '0xbf2179859fc6d5bee9bf9158632dc51678a4100e',
                      '0x69b148395ce0015c13e36bffbad63f49ef874e03', '0xb98d4c97425d9908e66e53a6fdf673acca0be986',
                      '0x1a7a8bd9106f2b8d977e08582dc7d24c723ab0db', '0x5732046a883704404f284ce41ffadd5b007fd668',
                      '0xb683d83a532e2cb7dfa5275eed3698436371cc9f', '0x43e5f59247b235449e16ec84c46ba43991ef6093',
                      '0x81c9151de0c8bafcd325a57e3db5a5df1cebf79c', '0x43e5f59247b235449e16ec84c46ba43991ef6093',
                      '0xb4272071ecadd69d933adcd19ca99fe80664fc08', '0x1cc9567ea2eb740824a45f8026ccf8e46973234d',
                      '0x1d496da96caf6b518b133736beca85d5c4f9cbc5', '0xbd56e9477fc6997609cf45f84795efbdac642ff1',
                      '0xf013406a0b1d544238083df0b93ad0d2cbe0f65f', '0xba9262578efef8b3aff7f60cd629d6cc8859c8b5',
                      '0xa7eb2bc82df18013ecc2a6c533fc29446442edee', '0x5e74c9036fb86bd7ecdcb084a0673efc32ea31cb',

                      ]
    not_tradable_2103 = ['0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', '0x4f3afec4e5a3f2a6a1a411def7d7dfe50ee057bf',
                         '0x865ec58b06bf6305b886793aa20a2da31d034e68']

    not_found_tokens, not_tradable_tokens, tradable_tokens = [], [], []

    print("These tokens return TokenNotFoundError (1203):")
    for t in token_utils.tokens_json():
        if t['address'] in not_found_1203:
            print(t)
            not_found_tokens.append(t['symbol'])

    print("These tokens return TokenNotTradableError (2103):")
    for t in token_utils.tokens_json():
        if t['address'] in not_tradable_2103:
            print(t)
            not_tradable_tokens.append(t['symbol'])

    print("These tokens never returned prices from Totle")
    for t in token_utils.tokens_json():
        if t['symbol'] in ['ABYSS', 'LRC', 'MLN']:
            t.pop('tradable')
            t.pop('iconUrl')
            print(t)
            tradable_tokens.append(t['symbol'])

    print(f"len(not_found_tokens)={len(not_found_tokens)}")
    print(not_found_tokens)
    print(f"len(not_tradable_tokens)={len(not_tradable_tokens)}")
    print(not_tradable_tokens)
    print(f"len(tradable_tokens)={len(tradable_tokens)}")
    print(tradable_tokens)

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

# test_find_duplicates()
test_missing()


