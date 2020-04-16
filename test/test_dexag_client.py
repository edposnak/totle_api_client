import json
import time

import dexag_client
import exchange_utils
import token_utils

def test_dex_name_map():
    dexs = dexag_client.exchanges()
    # map = {exchange_utils.canonical_name(dex_name): dex_name for dex_name in sorted(dexs)}
    # print(f"DEX_NAME_MAP = {map}")
    # exit(0)

    for dex_name in dexs:
        can_name = exchange_utils.canonical_name(dex_name)
        print(f"{can_name} => {dexag_client.DEX_NAME_MAP[can_name]}")


def test_get_quote(to_token, from_token='ETH', from_amount=None, to_amount=None, dex=dexag_client.AG_DEX, verbose=True, debug=True):
    kw_params = get_kw_params(from_amount, to_amount, dex, verbose, debug)

    try:
        pq = dexag_client.get_quote(from_token, to_token, **kw_params)
        if not pq:
            print(f"{dex} did not have {from_token} to {to_token} from_amount={from_amount} to_amount={to_amount}")
        else:
            # print(f"price={pq['price']} from {from_token} to {to_token} from_amount={from_amount} to_amount={to_amount}\nexchanges_prices={pq['exchanges_prices']}")
            print(pq)
    except (dexag_client.DexAGAPIException, ValueError) as e:
        print(e)

def test_get_swap(to_token, from_token='ETH', from_amount=None, to_amount=None, dex=dexag_client.AG_DEX, verbose=True, debug=True):
    kw_params = get_kw_params(from_amount, to_amount, dex, verbose, debug)

    try:
        pq = dexag_client.get_swap(from_token, to_token, **kw_params)
        if not pq:
            print(f"{dex} did not have {from_token} to {to_token} from_amount={from_amount} to_amount={to_amount}")
        else:
            # print(f"price={pq['price']} from {from_token} to {to_token} from_amount={from_amount} to_amount={to_amount}\nexchanges_prices={pq['exchanges_prices']}")
            print(pq)
    except (dexag_client.DexAGAPIException, ValueError) as e:
        print(e)

def get_kw_params(from_amount, to_amount, dex, verbose, debug):
    kw_params = dict(dex=dex, verbose=verbose, debug=debug)
    if from_amount:
        kw_params['from_amount'] = from_amount
    elif to_amount:
        kw_params['to_amount'] = to_amount
    else:
        raise ValueError(f"either from_amount or to_amount must be specified")
    return kw_params


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

def test_supported_tokens():
    supported_tokens = dexag_client.supported_tokens()
    print(f"supported_tokens={supported_tokens}")


#######################################################################################################################
# test_dex_name_map()

# https://api.dex.ag/price?from=ETH&to=DAI&toAmount=1.5&dex=ag -> price: 0.0055    <- buy (OK)
test_get_swap('DAI', from_token='ETH', to_amount=1.5)
print(f"price ^ should be 0.0055")
# https://api.dex.ag/price?from=ETH&to=DAI&fromAmount=1.5&dex=ag -> price: 180     <- buy (inverted)
test_get_swap('DAI', from_token='ETH', from_amount=1.5)
print(f"price ^ should be 0.0055")

# https://api.dex.ag/price?from=DAI&to=ETH&toAmount=1.5&dex=ag -> price: 180       <- sell (OK)
test_get_swap('ETH', from_token='DAI', to_amount=1.5)
print(f"price ^ should be 180")
# https://api.dex.ag/price?from=DAI&to=ETH&fromAmount=1.5&dex=ag -> price: 0.0055  <- sell (inverted)
test_get_swap('ETH', from_token='DAI', from_amount=1.5)
print(f"price ^ should be 180")

exit(0)

# test_get_quote('MKR', to_amount=1.0)
test_get_swap('MKR', from_amount=1.0)

# Buying CVC for 993.5942467706458 PAX
test_get_quote('CVC', from_token='PAX', from_amount=994)


test_get_quote('MKR', from_amount=1.0, dex='all')

test_get_quote('ETHOS', from_amount=1.0)
test_get_quote('ETHOS', from_amount=1, to_amount=200.0)


test_get_quote('OMG', from_amount=1.0)
test_get_quote('OMG', to_amount=200.0)

test_get_quote('ETH', from_token='OMG', from_amount=1.0)
test_get_quote('ETH', from_token='OMG', to_amount=200.0)

test_get_quote('BAT', from_amount=100.0, dex='all', debug=True)


test_which_tokens_supported(token_utils.tokens(), dex='0xMesh')

