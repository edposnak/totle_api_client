import oneinch_client
import exchange_utils

dexs = oneinch_client.exchanges()

# map = {exchange_utils.canonical_name(dex_name): dex_name for dex_name in sorted(dexs)}
# print(f"DEX_NAME_MAP = {map}")
# exit(0)
for dex_name in dexs:
    can_name = exchange_utils.canonical_name(dex_name)
    print(f"{can_name}: {dex_name},")
    # print(f"{can_name} => {oneinch_client.DEX_NAME_MAP[can_name]}")

from_token, to_token = 'ETH', 'OMG'
from_amount, to_amount = 1.0, 200.0

pq = oneinch_client.get_quote(from_token, to_token, from_amount=from_amount)
print(f"price={pq['price']} from {from_token} to {to_token} from_amount={from_amount}")

try:
    pq = oneinch_client.get_quote(from_token, to_token, to_amount=to_amount)
    print(f"price={pq['price']} from {from_token} to {to_token} to_amount={to_amount}")
except ValueError as e:
    print(e)


from_token, to_token = 'OMG', 'ETH'
from_amount, to_amount = 200.0, 1.0

pq = oneinch_client.get_quote(from_token, to_token, from_amount=from_amount)
print(f"price={pq['price']} from {from_token} to {to_token} from_amount={from_amount}")

try:
    pq = oneinch_client.get_quote(from_token, to_token, to_amount=to_amount)
    print(f"price={pq['price']} from {from_token} to {to_token} to_amount={to_amount}")
except ValueError as e:
    print(e)



