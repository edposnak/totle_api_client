import exchange_utils



print(exchange_utils.canonical_keys({'UNISWAP': 70, 'BANCOR': 30}))
print(exchange_utils.canonical_keys({'uniswap': 3, 'kyber': 97}))
print(exchange_utils.canonical_keys({}))

