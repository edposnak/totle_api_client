import v2_client

quote='ETH'

dex = 'EtherDelta'
for base in [ 'AST','CDT','CND','CVC','ETHOS','GNO','LEND','POLY','POWR','REQ','STORJ' ]:
    for trade_size in [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0]:
        pq = v2_client.get_quote(quote, base, from_amount=trade_size, dex=dex)
        if not pq:
            print(f"{dex} did not have {quote} to {base} at trade size={trade_size}")
        else:
            print(pq)

base = 'USDC'
for trade_size in [100.0, 200.0, 300.0, 400.0, 500.0]:
    pq = v2_client.get_quote(quote, base, from_amount=trade_size, verbose=True)
    if pq: print(pq)


exit(0)

TOTLE_39 = ['ANT','AST','BAT','BNT','CDT','CND','CVC','DAI','ENG','ENJ','ETHOS','GNO','KNC','LINK','MANA','MCO','MKR','OMG','PAX','PAY','POE','POLY','POWR','RCN','RDN','REN','REP','REQ','RLC','RPL','SNT','SNX','STORJ','TKN','TUSD','USDC','USDT','WBTC','ZRX']

print("\n\nwhitelisting Kyber")
for base in TOTLE_39:
    for trade_size in [1.0, 10.0, 100.0]:
        pq = v2_client.get_quote(quote, base, from_amount=trade_size, dex='Kyber', verbose=True)
        if pq: print(pq)


