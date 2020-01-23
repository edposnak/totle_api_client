import exchange_utils
import paraswap_client


def test_dex_name_map():
    dexs = paraswap_client.exchanges()
    # map = {exchange_utils.canonical_name(dex_name): dex_name for dex_name in sorted(dexs)}
    # print(f"DEX_NAME_MAP = {map}")
    # exit(0)
    for dex_name in dexs:
        can_name = exchange_utils.canonical_name(dex_name)
        print(f"{can_name} => {paraswap_client.DEX_NAME_MAP[can_name]}")




def test_get_quote(from_token, to_token, from_amount=None, to_amount=None, dex=None, verbose=False, debug=False):
    kw_params = dict(dex=dex, verbose=verbose, debug=debug)

    if from_amount:
        kw_params['from_amount'] = from_amount
    elif to_amount:
        kw_params['to_amount'] = to_amount
    else:
        raise ValueError(f"either from_amount or to_amount must be specified")

    try:
        pq = paraswap_client.get_quote(from_token, to_token, **kw_params)
        print(f"price={pq['price']} from {from_token} to {to_token} from_amount={from_amount} to_amount={to_amount}")
    except (paraswap_client.ParaswapAPIException, ValueError) as e:
        print(e)

#######################################################################################################################
test_dex_name_map()

# Buying RDN for 156.19586819370878 REN
test_get_quote('REN', 'RDN', from_amount=156.19586819370878, debug=True)

# test_get_quote('REQ', 'USDC', from_amount=9.935)
exit(0)


test_get_quote('OMG', 'ETH', from_amount=200.0)
test_get_quote('OMG', 'ETH', to_amount=1.0)

test_get_quote('ETH', 'BAT', from_amount=10.0)
test_get_quote('ETH', 'BAT', to_amount=200.0)

