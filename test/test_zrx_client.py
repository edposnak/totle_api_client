import json

import zrx_client
import token_utils

def test_dex_name_map():
    pass

def test_get_quote(to_token, from_token='ETH', from_amount=None, to_amount=None, dex=None, verbose=False, debug=False):
    kw_params = dict(dex=dex, verbose=verbose, debug=debug)

    if from_amount:
        kw_params['from_amount'] = from_amount
    elif to_amount:
        kw_params['to_amount'] = to_amount
    else:
        raise ValueError(f"either from_amount or to_amount must be specified")

    try:
        pq = zrx_client.get_quote(from_token, to_token, **kw_params)
        if not pq:
            print(f"{zrx_client.name()} did not have {from_token} to {to_token} from_amount={from_amount} to_amount={to_amount}")
        else:
            # print(f"price={pq['price']} from {from_token} to {to_token} from_amount={from_amount} to_amount={to_amount}\nexchanges_prices={pq['exchanges_prices']}")
            print(pq)
    except (zrx_client.ZrxAPIException, ValueError) as e:
        print(json.dumps(e, indent=3))



#######################################################################################################################
test_dex_name_map()

test_get_quote('MKR', from_amount=1.0, debug=True)
# test_get_quote('MKR', to_amount=1.0)
exit(0)

TOTLE_39 = ['ANT','AST','BAT','BNT','CDT','CND','CVC','DAI','ENG','ENJ','ETHOS','GNO','KNC','LINK','MANA','MCO','MKR','OMG','PAX','PAY','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','STORJ','TKN','TUSD','USDC','USDT','WBTC','ZRX']
TOKENS = [t for t in TOTLE_39 if t not in ['CDT', 'CND', 'CVC', 'ENG', 'ETHOS', 'MCO', 'PAY', 'POE', 'POLY', 'RCN', 'RPL', 'TKN']]

TOKENS = ['SNX', 'WETH', 'sETH', 'UBT']
for token in TOKENS:
    test_get_quote(token, from_amount=0.1)


