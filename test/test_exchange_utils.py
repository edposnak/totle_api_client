import exchange_utils



print(exchange_utils.canonical_keys({'UNISWAP': 70, 'BANCOR': 30}))
print(exchange_utils.canonical_keys({'uniswap': 3, 'kyber': 97}))
print(exchange_utils.canonical_keys({}))

exchanges_prices = {'ag': 0.001372651378552163, 'uniswap': 0.00140777550778961, 'kyber': 0.0014079096668652288, 'bancor': 0.0015514654984085873, 'ddex': 0.0021565979626955154, 'idex': 0.005014703805865163}

can_splittable = exchange_utils.canonical_and_splittable(exchanges_prices)
print(f"can_splittable={can_splittable}")

