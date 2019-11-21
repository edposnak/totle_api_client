import dexag_client

def test_get_quote(to_token, trade_sizes, from_token='ETH', dex=dexag_client.AG_DEX, to_amount=None, verbose=True, debug=True, client=dexag_client):
    n_quotes = 0
    for trade_size in trade_sizes:
        if to_amount:
            pq = client.get_quote(from_token, to_token, to_amount=to_amount, dex=dex, verbose=verbose, debug=debug)
        else:
            pq = client.get_quote(from_token, to_token, from_amount=trade_size, dex=dex, verbose=verbose, debug=debug)
        if not pq:
            print(f"{dex} did not have {from_token} to {to_token} at trade size={trade_size}")
        else:
            n_quotes += 1
            # print(f"price={pq['price']} from {from_token} to {to_token}\nexchanges_prices={pq['exchanges_prices']}")
            print(pq)
    return n_quotes

# dexs = dexag_client.exchanges()
# for dex_name in dexs:
#     can_name = exchange_utils.canonical_name(dex_name)
#     print(f"{can_name} => {dexag_client.DEX_NAME_MAP[can_name]}")

for base in ['BAT']:
    # n_quotes = test_get_quote(base, [0.1, 1.0], dex='Kyber', debug=True)
    n_quotes = test_get_quote(base, [100.0], dex='all', debug=True)
    print(f"{base}: {n_quotes}")
exit(0)

test_get_quote('MKR', [1.0], dex='all')

test_get_quote('ETHOS', [1.0])
test_get_quote('ETHOS', [1], to_amount=200.0)


test_get_quote('OMG', [1.0])
test_get_quote('OMG', [1], to_amount=200.0)

test_get_quote('ETH', [1.0], from_token='OMG')
test_get_quote('ETH', [1], from_token='OMG', to_amount=200.0)



