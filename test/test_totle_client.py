import json

import exchange_utils
import token_utils
import totle_client

class FoundBugException(Exception):
    pass

def test_dex_name_map():
    dexs = totle_client.exchanges()
    # map = {exchange_utils.canonical_name(dex_name): dex_name for dex_name in sorted(dexs)}
    # print(f"DEX_NAME_MAP = {map}")
    # exit(0)

    for dex_name in dexs:
        can_name = exchange_utils.canonical_name(dex_name)
        print(f"{can_name} => {totle_client.DEX_NAME_MAP[can_name]}")

def test_basics():
    print(totle_client.name())
    print(totle_client.exchanges())
    print(totle_client.enabled_exchanges())
    print(totle_client.data_exchanges())

# BUG 1. partial fills not reflected in the summary
def test_summary_bug_1(token_to_buy='ZRX', endpoint=totle_client.SWAP_ENDPOINT, debug=False):
    inputs = totle_client.swap_inputs('ETH', token_to_buy, params={'tradeSize': 0.1})
    j = totle_client.post_with_retries(endpoint, inputs, debug=debug)
    summary_src_amount, summary_dest_amount, trades0_src_amount, trades0_dest_amount, orders00_src_amount, orders00_dest_amount, totle_fee_amount, totle_used = parse_swap_response1(j)

    print(f"summary_src_amount={summary_src_amount} summary_dest_amount={summary_dest_amount}")
    print(f"totle_fee={totle_fee_amount}")
    print(f"    trades0_src_amount={trades0_src_amount} trades0_dest_amount={trades0_dest_amount}")
    print(f"        orders00_src_amount={orders00_src_amount} orders00_dest_amount={orders00_dest_amount}")

    if summary_dest_amount != orders00_dest_amount + totle_fee_amount:
        raise FoundBugException(f"BUG 1: buying {token_to_buy} on {totle_used} summary_dest_amount={summary_dest_amount} but orders00_dest_amount + totle_fee_amount = {orders00_dest_amount + totle_fee_amount}")
    else:
        print(f"BUG1 buying {token_to_buy} on {totle_used} checks out")



# BUG 2. fees not accounted for when baseAsset is used (e.g. buying SHP with ETH)
def test_summary_bug_2(token_to_buy='SHP', token_to_sell='ETH', json_response_file=None, endpoint=totle_client.SWAP_ENDPOINT):
    if json_response_file:
        j = json.load(open(json_response_file))
    else:
        inputs = totle_client.swap_inputs(token_to_sell, token_to_buy, params={'fromAmount': 10})
        print(f"Using endpoint {endpoint}")
        j = totle_client.post_with_retries(endpoint, inputs, debug=True)

    # parse the response
    r = j['response']
    summary = r['summary'][0]
    summary_src_amount, summary_dest_amount = int(summary['sourceAmount']), int(summary['destinationAmount'])
    trades0 = summary['trades'][0]
    trades0_src_amount, trades0_dest_amount = int(trades0['sourceAmount']), int(trades0['destinationAmount'])
    orders00 = trades0['orders'][0]
    orders00_src_amount, orders00_dest_amount = int(orders00['sourceAmount']), int(orders00['destinationAmount'])
    trades1 = summary['trades'][1]
    trades1_src_amount, trades1_dest_amount = int(trades1['sourceAmount']), int(trades1['destinationAmount'])
    orders10 = trades1['orders'][0]
    orders10_src_amount, orders10_dest_amount = int(orders10['sourceAmount']), int(orders10['destinationAmount'])
    totle_fee_amount = int(summary['totleFee']['amount'])

    base_token = summary['baseAsset']['symbol']
    source_token = summary['sourceAsset']['symbol']
    totle_fee_token = summary['totleFee']['asset']['symbol']

    print(f"summary_src_amount={summary_src_amount} summary_dest_amount={summary_dest_amount}")
    print(f"totle_fee={totle_fee_amount} {totle_fee_token}")
    print(f"    trades0_src_amount={trades0_src_amount} trades0_dest_amount={trades0_dest_amount}")
    print(f"        orders00_src_amount={orders00_src_amount} orders00_dest_amount={orders00_dest_amount}")
    print(f"    trades1_src_amount={trades1_src_amount} trades1_dest_amount={trades1_dest_amount}")
    print(f"        orders10_src_amount={orders10_src_amount} orders10_dest_amount={orders10_dest_amount}")


    # bug 2 checks
    bug_msg = ''
    if totle_fee_token == source_token:
        if totle_fee_amount != (summary_src_amount - orders00_src_amount):
            bug_msg += f"\nBUG 2: totle_fee={totle_fee_amount} {totle_fee_token} but summary_src_amount - orders00_src_amount={summary_src_amount - orders00_src_amount} diff={summary_src_amount - (summary_src_amount - orders00_src_amount)}"
        if orders00_dest_amount != orders10_src_amount:
            bug_msg += f"\nBUG 2: totle_fee was taken in source asset but orders00_dest_amount != orders10_src_amount orders00_dest_amount={orders00_dest_amount} orders10_src_amount={orders10_src_amount}"
    elif totle_fee_token == base_token:
        if totle_fee_amount != (orders00_dest_amount - trades0_dest_amount):
            bug_msg += f"\nBUG 2: totle_fee={totle_fee_amount} but orders00_dest_amount - trades0_dest_amount={orders00_dest_amount - trades0_dest_amount} diff={totle_fee_amount - (orders00_dest_amount - trades0_dest_amount)}"

        if trades1_src_amount != trades0_dest_amount and trades1_src_amount == orders00_dest_amount:
            bug_msg += f"\nBUG 2: trades1_src_amount should have been equal to trades0_dest_amount, but it was equal to orders00_dest_amount, and thus did not account for the fee being taken out"

        if orders10_src_amount != trades0_dest_amount and orders10_src_amount == orders00_dest_amount:
            bug_msg += f"\nBUG 2:orders10_src_amount should have been equal to trades0_dest_amount, but it was equal to orders00_dest_amount, and thus did not account for the fee being taken out"

    else:
        raise ValueError(f"totle_feee_token({totle_fee_token}) is neither base_token({base_token}) nor source_token({source_token})")

    if bug_msg: raise FoundBugException(bug_msg)

# BUG 3. liquidity appears infinite based on single small trade (e.g. buy 283 MKR for 100 ETH)
def test_summary_bug_3(token_to_buy='MKR', dex='Eth2dai'):
    # buy ~283 MKR for 100 ETH,
    # pq = totle_client.get_quote('ETH', token_to_buy, from_amount=100.0, dex=dex, debug=True, verbose=True)
    inputs = totle_client.swap_inputs('ETH', token_to_buy, exchange=dex, params={'tradeSize':100.0})
    j = totle_client.post_with_retries(totle_client.SWAP_ENDPOINT, inputs, debug=True)
    summary_src_amount, summary_dest_amount, trades0_src_amount, trades0_dest_amount, orders00_src_amount, orders00_dest_amount, totle_fee_amount, totle_used = parse_swap_response1(j)

    # bug 3 checks
    if summary_dest_amount > orders00_dest_amount:
        raise FoundBugException(f"BUG 3: summary_dest_amount > orders00_dest_amount should not be possible. summary_dest_amount={summary_dest_amount} orders00_dest_amount={orders00_dest_amount}")


def parse_swap_response1(j):
    r = j['response']
    summary = r['summary'][0]
    summary_src_amount, summary_dest_amount = int(summary['sourceAmount']), int(summary['destinationAmount'])
    if len(summary['trades']) > 1:
        raise ValueError(f"Expected summary to only contain 1 trade, but it had {len(summary['trades'])}")
    trades0 = summary['trades'][0]
    trades0_src_amount, trades0_dest_amount = int(trades0['sourceAmount']), int(trades0['destinationAmount'])
    orders00 = trades0['orders'][0]
    orders00_src_amount, orders00_dest_amount = int(orders00['sourceAmount']), int(orders00['destinationAmount'])
    totle_fee_amount = int(summary['totleFee']['amount'])
    totle_used = orders00['exchange']['name']

    return summary_src_amount, summary_dest_amount, trades0_src_amount, trades0_dest_amount, orders00_src_amount, orders00_dest_amount, totle_fee_amount, totle_used

def test_get_quote(tradable_tokens, trade_size=0.1, dex=None, from_token='ETH', debug=False, verbose=False):
    for to_token in tradable_tokens:
        print(f"\nswap {trade_size} {from_token} to {to_token} on {dex if dex else 'all DEXs'}")
        pq = totle_client.get_quote(from_token, to_token, from_amount=trade_size, dex=dex, debug=debug, verbose=verbose)
        print(pq)

def test_which_tokens_supported(tradable_tokens, trade_size=0.1, dex='0xMesh', from_token='ETH', debug=False, verbose=False):
    token_map = {}
    supported_tokens = []
    for to_token in tradable_tokens:
        print(f"swap {trade_size} {from_token} to {to_token} on {dex if dex else 'all DEXs'}")
        pq = totle_client.get_quote('ETH', to_token, from_amount=trade_size, dex=dex) # , verbose=True, debug=True)
        print(pq)
        if pq and pq.get('price'):
            supported_tokens.append(to_token)
        token_map[to_token] = pq

    print(f"\n\n{len(supported_tokens)}/{len(tradable_tokens)} tokens supported by {dex}: {supported_tokens}\n\n")
    print(token_map)


def test_summary_bug_4(token_to_buy='AST', token_to_sell='ETH', json_response_file=None, endpoint=totle_client.SWAP_ENDPOINT):
    if json_response_file:
        test_swap_data(json_response_file)
    else:
        inputs = totle_client.swap_inputs(token_to_sell, token_to_buy, params={'fromAmount': 10})
        print(f"Using endpoint {endpoint}")
        j = totle_client.post_with_retries(endpoint, inputs, debug=True)
        sd = totle_client.swap_data(j, True)
        print(json.dumps(sd, indent=3))

def test_swap_data(json_response_file):
    j = json.load(open(json_response_file))['response']

    sd = totle_client.swap_data(j, True)
    print(json.dumps(sd, indent=3))

def test_get_snapshot(id):
    j = totle_client.get_snapshot(id)
    print(json.dumps(j, indent=3))

#######################################################################################################################

# test_get_snapshot('0x998f9d03d108475998aba20c525009fd263a3ece5f724cbaa013b4a2283300a0')
test_swap_data('test_data/suggester-response-with-path.json')
exit(0)

test_dex_name_map()

tradable_tokens = token_utils.tradable_tokens()

try:
    # for token in token_utils.tradable_tokens():
    #     test_summary_bug_1(token)

    # test_summary_bug_2(token_to_buy='SHP', token_to_sell='ETH')
    # test_summary_bug_2(token_to_buy='CDAI', token_to_sell='BAT', endpoint='https://services.totlenext.com/suggester/fix-amounts')
    # test_summary_bug_2(token_to_buy='CDAI', token_to_sell='ETH', endpoint='https://services.totlenext.com/suggester/fix-amounts')
    # test_summary_bug_2(token_to_buy='DAI', token_to_sell='BAT', endpoint='https://services.totlenext.com/suggester/fix-amounts')
    # test_summary_bug_2(token_to_buy='BAT', json_response_file='test_data/bug2_plus_fee.json')
    # test_summary_bug_2(token_to_buy='BAT', json_response_file='test_data/bug_2_fee_in_source_asset.json')

    # test_summary_bug_3(token_to_buy='MKR', dex='Oasis')

    test_summary_bug_4(token_to_buy='AST', json_response_file='test_data/summary_bug_4.json')
except FoundBugException as e:
    print(e)

# # tradable_tokens = ['BAT', 'CVC', 'ZIL']
# test_get_quote(tradable_tokens)
# test_what_tokens_supported(tradable_tokens, dex='0xMesh')

# test_what_tokens_supported(tradable_tokens, dex='Stablecoinswap')
# test_what_tokens_supported(tradable_tokens, dex='Fulcrum')

# test_get_quote(['CETH'], dex='Fulcrum')
