import oneinch_client
import exchange_utils

def test_dex_name_map():
    dexs = oneinch_client.exchanges()

    # map = {exchange_utils.canonical_name(dex_name): dex_name for dex_name in sorted(dexs)}
    # print(f"DEX_NAME_MAP = {map}")
    # exit(0)
    for dex_name in dexs:
        can_name = exchange_utils.canonical_name(dex_name)
        print(f"{can_name}: {dex_name},")
        # print(f"{can_name} => {oneinch_client.DEX_NAME_MAP[can_name]}")


def test_get_quote(to_token, from_token='ETH', from_amount=None, to_amount=None, dex=None, verbose=True, debug=True):
    kw_params = dict(dex=dex, verbose=verbose, debug=debug)

    if from_amount:
        kw_params['from_amount'] = from_amount
    elif to_amount:
        kw_params['to_amount'] = to_amount
    else:
        raise ValueError(f"either from_amount or to_amount must be specified")

    try:
        pq = oneinch_client.get_quote(from_token, to_token, **kw_params)
        if not pq:
            print(f"{dex} did not have {from_token} to {to_token} from_amount={from_amount} to_amount={to_amount}")
        else:
            print(f"price={pq['price']} from {from_token} to {to_token} from_amount={from_amount} to_amount={to_amount}")
            print(pq)
    except (oneinch_client.DexAGAPIException, ValueError) as e:
        print(e)

#######################################################################################################################

test_dex_name_map()
exit(0)

test_get_quote('OMG', from_amount=1.0)
test_get_quote('OMG', to_amount=200)

test_get_quote('ETH', 'OMG', from_amount=200)
test_get_quote('ETH', 'OMG', to_amount=1.0)

