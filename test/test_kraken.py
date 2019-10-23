from kraken_client import translate_from_kraken, translate_to_kraken, get_pairs


print(f"translate_to_kraken('ETH') = {translate_to_kraken('ETH')}")
print(f"translate_from_kraken('XETH') = {translate_from_kraken('XETH')}")
print(f"translate_to_kraken('ZEUR') = {translate_to_kraken('ZEUR')}")
print(f"translate_from_kraken('ZEUR') = {translate_from_kraken('ZEUR')}")
print(f"translate_to_kraken('USDT') = {translate_to_kraken('USDT')}")
print(f"translate_from_kraken('USDT') = {translate_from_kraken('USDT')}")

p = get_pairs()
for b,q in p: print(b,q)




