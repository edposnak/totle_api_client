import json

import token_utils
import v2_client

class FoundBugException(Exception):
    pass

def test_basics():
    print(v2_client.name())
    print(v2_client.exchanges())
    print(v2_client.enabled_exchanges())
    print(v2_client.data_exchanges())

# BUG 1. partial fills not reflected in the summary
def test_summary_bug_1(token_to_buy='ZRX', endpoint=v2_client.SWAP_ENDPOINT, debug=False):
    inputs = v2_client.swap_inputs('ETH', token_to_buy, params={'tradeSize': 0.1})
    j = v2_client.post_with_retries(endpoint, inputs, debug=debug)
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
def test_summary_bug_2(token_to_buy='SHP', token_to_sell='ETH', json_response_file=None, endpoint=v2_client.SWAP_ENDPOINT):
    if json_response_file:
        j = json.load(open(json_response_file))
    else:
        inputs = v2_client.swap_inputs(token_to_sell, token_to_buy, params={'tradeSize':0.1})
        print(f"Using endpoint {endpoint}")
        j = v2_client.post_with_retries(endpoint, inputs, debug=True)

    summary_src_amount, summary_dest_amount, trades0_src_amount, trades0_dest_amount, orders00_src_amount, orders00_dest_amount, \
        trades1_src_amount, trades1_dest_amount, orders10_src_amount, orders10_dest_amount, totle_fee_amount,\
        totle_fee_token, totle_fee_in_base_token, source_to_base_rate, source_token, base_token = parse_swap_response2(j)
    print(f"summary_src_amount={summary_src_amount} summary_dest_amount={summary_dest_amount}")
    print(f"totle_fee={totle_fee_amount} {totle_fee_token}")
    print(f"    trades0_src_amount={trades0_src_amount} trades0_dest_amount={trades0_dest_amount}")
    print(f"        orders00_src_amount={orders00_src_amount} orders00_dest_amount={orders00_dest_amount}")
    print(f"    trades1_src_amount={trades1_src_amount} trades1_dest_amount={trades1_dest_amount}")
    print(f"        orders10_src_amount={orders10_src_amount} orders10_dest_amount={orders10_dest_amount}")


    # bug 2 checks
    bug_msg = ''
    if totle_fee_in_base_token != (orders00_dest_amount - trades0_dest_amount):
        bug_msg += f"\nBUG 2: totle_fee={totle_fee_in_base_token} but orders00_dest_amount - trades0_dest_amount={orders00_dest_amount - trades0_dest_amount} diff={totle_fee_in_base_token - (orders00_dest_amount - trades0_dest_amount)}"
        if source_to_base_rate:
            calc_totle_fee = token_utils.real_amount(totle_fee_in_base_token, base_token)
            actual_totle_fee = token_utils.real_amount(orders00_dest_amount - trades0_dest_amount, base_token)
            bug_msg += f"\nBUG 2: Based on fee of {totle_fee_amount} {totle_fee_token} and a rate of source_to_base_rate of {source_to_base_rate:.2f} {base_token}/{source_token} the difference should have been {calc_totle_fee:.2f} {base_token} but it was {actual_totle_fee}"

    if trades1_src_amount != trades0_dest_amount and trades1_src_amount == orders00_dest_amount:
        bug_msg += f"\nBUG 2: trades1_src_amount should have been equal to trades0_dest_amount, but it was equal to orders00_dest_amount, and thus did not account for the fee being taken out"

    if orders10_src_amount != trades0_dest_amount and orders10_src_amount == orders00_dest_amount:
        bug_msg += f"\nBUG 2:orders10_src_amount should have been equal to trades0_dest_amount, but it was equal to orders00_dest_amount, and thus did not account for the fee being taken out"

    if bug_msg: raise FoundBugException(bug_msg)

# BUG 3. liquidity appears infinite based on single small trade (e.g. buy 283 MKR for 100 ETH)
def test_summary_bug_3(token_to_buy='MKR', dex='Eth2dai'):
    # buy ~283 MKR for 100 ETH,
    # pq = v2_client.get_quote('ETH', token_to_buy, from_amount=100.0, dex=dex, debug=True, verbose=True)
    inputs = v2_client.swap_inputs('ETH', token_to_buy, exchange=dex, params={'tradeSize':100.0})
    j = v2_client.post_with_retries(v2_client.SWAP_ENDPOINT, inputs, debug=True)
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

def parse_swap_response2(j):
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
    totle_fee = int(summary['totleFee']['amount'])

    base_token = summary['baseAsset']['symbol']
    source_token = summary['sourceAsset']['symbol']
    destination_token = summary['destinationAsset']['symbol']
    totle_fee_token = summary['totleFee']['asset']['symbol']

    source_to_base_rate = None
    if totle_fee_token == base_token:
        totle_fee_in_base_token = totle_fee  # totle_fee is already denominated in base token
    elif totle_fee_token == source_token: # convert totle_fee to an amount in base token
        source_to_base_rate = token_utils.real_amount(orders00_dest_amount, orders00['destinationAsset']['symbol']) / token_utils.real_amount(orders00_src_amount, orders00['sourceAsset']['symbol'])
        totle_fee_in_base_token = totle_fee * source_to_base_rate
    else:
        raise ValueError(f"totle_feee_token({totle_fee_token}) is neither base_token({base_token}) nor source_token({source_token})")

    return summary_src_amount, summary_dest_amount, trades0_src_amount, trades0_dest_amount, orders00_src_amount, orders00_dest_amount, trades1_src_amount, trades1_dest_amount, orders10_src_amount, orders10_dest_amount, totle_fee, totle_fee_token, totle_fee_in_base_token, source_to_base_rate, source_token, base_token


def test_get_quote(tradable_tokens, trade_size=0.1, dex=None, from_token='ETH', debug=False, verbose=False):
    for to_token in tradable_tokens:
        print(f"swap {trade_size} {from_token} to {to_token} on {dex if dex else 'all DEXs'}")
        pq = v2_client.get_quote(from_token, to_token, from_amount=trade_size, dex=dex, debug=debug, verbose=verbose)
        print(pq)

def test_which_tokens_supported(tradable_tokens, trade_size=0.1, dex='0xMesh', from_token='ETH', debug=False, verbose=False):
    token_map = {}
    supported_tokens = []
    for to_token in tradable_tokens:
        print(f"swap {trade_size} {from_token} to {to_token} on {dex if dex else 'all DEXs'}")
        pq = v2_client.get_quote('ETH', to_token, from_amount=trade_size, dex=dex) # , verbose=True, debug=True)
        print(pq)
        if pq and pq.get('price'):
            supported_tokens.append(to_token)
        token_map[to_token] = pq

    print(f"\n\n{len(supported_tokens)}/{len(tradable_tokens)} tokens supported by {dex}: {supported_tokens}\n\n")
    print(token_map)


#######################################################################################################################

tradable_tokens = token_utils.tradable_tokens()

try:
    # for token in token_utils.tradable_tokens():
    #     test_summary_bug_1(token)

    test_summary_bug_2(token_to_buy='SHP', token_to_sell='ETH')
    # test_summary_bug_2(token_to_buy='SHP', endpoint='https://services.totlenext.com/suggester/optimized/swap')
    # test_summary_bug_2(token_to_buy='BAT', json_response_file='test_data/bug2_plus_fee.json')
    # test_summary_bug_2(token_to_buy='BAT', json_response_file='test_data/bug_2_fee_in_source_asset.json')

    # test_summary_bug_3(token_to_buy='MKR', dex='Oasis')
except FoundBugException as e:
    print(e)

# # tradable_tokens = ['BAT', 'CVC', 'ZIL']
# test_get_quote(tradable_tokens)
# test_what_tokens_supported(tradable_tokens, dex='0xMesh')

# test_what_tokens_supported(tradable_tokens, dex='Stablecoinswap')
# test_what_tokens_supported(tradable_tokens, dex='Fulcrum')

# test_get_quote(['CETH'], dex='Fulcrum')
