import json
import time

import dexag_client
import exchange_utils
import token_utils


def test_get_quote(to_token, trade_sizes, dex=dexag_client.AG_DEX, from_token='ETH', to_amount=None, verbose=True, debug=True, client=dexag_client):
    n_quotes = 0
    if to_amount:
        pq = client.get_quote(from_token, to_token, to_amount=to_amount, dex=dex, verbose=verbose, debug=debug)
    else:
        for trade_size in trade_sizes:
            pq = client.get_quote(from_token, to_token, from_amount=trade_size, dex=dex, verbose=verbose, debug=debug)
    if not pq:
        print(f"{dex} did not have {from_token} to {to_token} at trade size={trade_size}")
    else:
        n_quotes += 1
        # print(f"price={pq['price']} from {from_token} to {to_token}\nexchanges_prices={pq['exchanges_prices']}")
        print(pq)
    print(f"{to_token}: {n_quotes}")
    return n_quotes


def test_print_dex_names():
    dexs = dexag_client.exchanges()
    for dex_name in dexs:
        can_name = exchange_utils.canonical_name(dex_name)
        print(f"{can_name} => {dexag_client.DEX_NAME_MAP[can_name]}")

def test_which_tokens_supported(tradable_tokens, trade_size=0.1, dex=None, from_token='ETH', debug=False, verbose=False):
    supported_tokens = []
    for to_token in tradable_tokens:
        print(f"swap {trade_size} {from_token} to {to_token} on {dex if dex else 'all DEXs'}")
        pq = dexag_client.get_quote(from_token, to_token, from_amount=0.1, dex=dex, verbose=verbose, debug=debug)
        print(pq)
        if pq.get('exchanges_prices') and 'radar-relay' in pq['exchanges_prices']:
            supported_tokens.append(to_token)
        # time.sleep(0.2)
    print(f"{len(supported_tokens)}/{len(tradable_tokens)} tokens supported by Radar Relay: {supported_tokens}")

#######################################################################################################################

test_get_quote('MKR', [1.0], dex='all')

test_get_quote('ETHOS', [1.0])
test_get_quote('ETHOS', [1], to_amount=200.0)


test_get_quote('OMG', [1.0])
test_get_quote('OMG', [1], to_amount=200.0)

test_get_quote('ETH', [1.0], from_token='OMG')
test_get_quote('ETH', [1], from_token='OMG', to_amount=200.0)

test_get_quote('BAT', [100.0], dex='all', debug=True)

test_print_dex_names()

test_which_tokens_supported(tokens = token_utils.tokens(), dex='0xMesh')

