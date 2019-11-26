import json

import token_utils
import v2_client

def test_basics():
    print(v2_client.name())
    print(v2_client.exchanges())
    print(v2_client.enabled_exchanges())
    print(v2_client.data_exchanges())

def test_summary_bug_2(token_to_buy='SHP', json_response_file=None):
    if json_response_file:
        j = json.load(open(json_response_file))
    else:
        inputs = v2_client.swap_inputs('ETH', token_to_buy, params={'tradeSize':0.1})
        j = v2_client.post_with_retries(v2_client.SWAP_ENDPOINT, inputs, debug=True)

    summary_src_amount, summary_dest_amount, trades0_src_amount, trades0_dest_amount, orders00_src_amount, orders00_dest_amount, \
        trades1_src_amount, trades1_dest_amount, orders10_src_amount, orders10_dest_amount, totle_fee = parse_swap_response2(j)
    print(f"summary_src_amount={summary_src_amount} summary_dest_amount={summary_dest_amount}")
    print(f"totle_fee={totle_fee}")
    print(f"    trades0_src_amount={trades0_src_amount} trades0_dest_amount={trades0_dest_amount}")
    print(f"        orders00_src_amount={orders00_src_amount} orders00_dest_amount={orders00_dest_amount}")
    print(f"    trades1_src_amount={trades1_src_amount} trades1_dest_amount={trades1_dest_amount}")
    print(f"        orders10_src_amount={orders10_src_amount} orders10_dest_amount={orders10_dest_amount}")

    # bug 2 checks
    if totle_fee != (orders00_dest_amount - trades0_dest_amount):
        print(f"BUG: totle_fee={totle_fee} but orders00_dest_amount - trades0_dest_amount={orders00_dest_amount - trades0_dest_amount} diff={totle_fee - (orders00_dest_amount - trades0_dest_amount)}")
    if trades1_src_amount != trades0_dest_amount and trades1_src_amount == orders00_dest_amount:
        print(f"BUG: trades1_src_amount should have been equal to trades0_dest_amount, but it was equal to orders00_dest_amount, and thus did not account for the fee being taken out")

    if orders10_src_amount != trades0_dest_amount and orders10_src_amount == orders00_dest_amount:
        print(f"BUG:orders10_src_amount should have been equal to trades0_dest_amount, but it was equal to orders00_dest_amount, and thus did not account for the fee being taken out")

def parse_swap_response1(j):
    r = j['response']
    summary = r['summary'][0]
    summary_src_amount, summary_dest_amount = int(summary['sourceAmount']), int(summary['destinationAmount'])
    trades0 = summary['trades'][0]
    trades0_src_amount, trades0_dest_amount = int(trades0['sourceAmount']), int(trades0['destinationAmount'])
    orders00 = trades0['orders'][0]
    orders00_src_amount, orders00_dest_amount = int(orders00['sourceAmount']), int(orders00['destinationAmount'])
    totle_fee = int(summary['totleFee']['amount'])

    return summary_src_amount, summary_dest_amount, trades0_src_amount, trades0_dest_amount, orders00_src_amount, orders00_dest_amount, totle_fee

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

    return summary_src_amount, summary_dest_amount, trades0_src_amount, trades0_dest_amount, orders00_src_amount, orders00_dest_amount, trades1_src_amount, trades1_dest_amount, orders10_src_amount, orders10_dest_amount, totle_fee


def test_summary_bug_3(token_to_buy='MKR', dex='Eth2dai'):
    # buy ~283 MKR for 100 ETH,
    # pq = v2_client.get_quote('ETH', token_to_buy, from_amount=100.0, dex=dex, debug=True, verbose=True)
    inputs = v2_client.swap_inputs('ETH', token_to_buy, exchange=dex, params={'tradeSize':100.0})
    j = v2_client.post_with_retries(v2_client.SWAP_ENDPOINT, inputs, debug=True)
    summary_src_amount, summary_dest_amount, trades0_src_amount, trades0_dest_amount, orders00_src_amount, orders00_dest_amount, totle_fee = parse_swap_response1(j)

    # bug 3 checks
    if summary_dest_amount > orders00_dest_amount:
        print(f"BUG: summary_dest_amount > orders00_dest_amount should not be possible. summary_dest_amount={summary_dest_amount} orders00_dest_amount={orders00_dest_amount}")


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

# test_summary_bug_2(token_to_buy='SHP')
test_summary_bug_2(token_to_buy='BAT', json_response_file='test_data/bug2_plus_fee.json')
# test_summary_bug_3(token_to_buy='MKR', dex='Oasis')

# # tradable_tokens = ['BAT', 'CVC', 'ZIL']
# test_get_quote(tradable_tokens)
# test_what_tokens_supported(tradable_tokens, dex='0xMesh')

# test_what_tokens_supported(tradable_tokens, dex='Stablecoinswap')
# test_what_tokens_supported(tradable_tokens, dex='Fulcrum')

# test_get_quote(['CETH'], dex='Fulcrum')
