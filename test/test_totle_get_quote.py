import totle_client


def test_get_quote(to_token, from_token='ETH', trade_sizes=[1.0], dex=None, verbose=True, debug=True):
    n_quotes = 0
    for trade_size in trade_sizes:
        pq = totle_client.get_quote(from_token, to_token, from_amount=trade_size, dex=dex, verbose=verbose, debug=debug)
        if not pq:
            print(f"{dex} did not have {from_token} to {to_token} at trade size={trade_size}")
        else:
            n_quotes += 1
            print(pq)
    return n_quotes


# test_get_quote('MKR', verbose=False, debug=False)
pq = totle_client.get_quote('ETH', 'MKR', to_amount=1.0, debug=True)
print(pq)

exit(0)
# test_get_quote('MKR', trade_sizes=[0.1, 0.5, 1.0, 5.0], dex='Kyber')
# test_get_quote('MKR', trade_sizes=[0.1, 1000.0], dex=(totle_client.DEX_NAME_MAP.get('Oasis')))
#
# test_get_quote('MKR', trade_sizes=[1.0, 2.0, 10.0], dex='0xMesh')
# test_get_quote('ZRX', trade_sizes=[1.0, 2.0, 10.0], dex='0xMesh')
#

for to_token in ['MANA', 'REP', 'KNC']:
    test_get_quote(to_token, trade_sizes=[0.1, 0.5, 1.0, 2.0, 3.0], dex='0xMesh', debug=False)

#
# test_get_quote('USDC', trade_sizes=[100.0, 200.0, 300.0, 400.0, 500.0])
#

# for dex in ['EtherDelta', 'Kyber', 'Bancor', 'Eth2dai', 'Uniswap', 'Compound', '0xMesh', 'Stablecoinswap', 'Fulcrum']:
#     test_get_quote('OMG', trade_sizes=[0.1, 1.0], dex=dex, verbose=False, debug=False)
exit(0)

TOTLE_39 = ['ANT','AST','BAT','BNT','CDT','CND','CVC','DAI','ENG','ENJ','ETHOS','GNO','KNC','LINK','MANA','MCO','MKR','OMG','PAX','PAY','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','STORJ','TKN','TUSD','USDC','USDT','WBTC','ZRX']

for to_token in ['MKR', 'GNO', 'KNC']:
    # n_quotes = test_get_quote(to_token, trade_sizes=[0.1, 1.0], dex='Kyber', debug=True)
    n_quotes = test_get_quote(to_token, trade_sizes=[0.1, 1.0], debug=True)
    print(f"{to_token}: {n_quotes}")


