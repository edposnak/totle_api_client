import v2_client


def test_get_quote(base, trade_sizes, quote='ETH', dex=None, verbose=True, debug=True, client=v2_client):
    n_quotes = 0
    for trade_size in trade_sizes:
        pq = client.get_quote(quote, base, from_amount=trade_size, dex=dex, verbose=verbose, debug=debug)
        if not pq:
            print(f"{dex} did not have {quote} to {base} at trade size={trade_size}")
        else:
            n_quotes += 1
            print(pq)
    return n_quotes


# test_get_quote('MKR', [0.1, 0.5, 1.0, 5.0], dex='Kyber')
# test_get_quote('MKR', [0.1, 1000.0], dex=(v2_client.DEX_NAME_MAP.get('Oasis')))
#
# test_get_quote('MKR', [1.0, 2.0, 10.0], dex='0xMesh')
# test_get_quote('ZRX', [1.0, 2.0, 10.0], dex='0xMesh')
#
# # EtherDelta bug
# for base in [ 'AST','CDT','CND','CVC','ETHOS','GNO','LEND','POLY','POWR','REQ','STORJ' ]:
#     test_get_quote(base, [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0], dex='EtherDelta', debug=False)
#
# test_get_quote('USDC', [100.0, 200.0, 300.0, 400.0, 500.0])
#

for dex in ['EtherDelta', 'Kyber', 'Bancor', 'Eth2dai', 'Uniswap', 'Compound', '0xMesh', 'Stablecoinswap', 'Fulcrum']:
    test_get_quote('OMG', [0.1, 1.0], dex=dex, verbose=False, debug=False)
exit(0)

TOTLE_39 = ['ANT','AST','BAT','BNT','CDT','CND','CVC','DAI','ENG','ENJ','ETHOS','GNO','KNC','LINK','MANA','MCO','MKR','OMG','PAX','PAY','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','STORJ','TKN','TUSD','USDC','USDT','WBTC','ZRX']

for base in ['MKR', 'GNO', 'KNC']:
    # n_quotes = test_get_quote(base, [0.1, 1.0], dex='Kyber', debug=True)
    n_quotes = test_get_quote(base, [0.1, 1.0], debug=True)
    print(f"{base}: {n_quotes}")


