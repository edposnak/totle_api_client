import paraswap_client

from_token, to_token = 'ETH', 'OMG'
from_amount, to_amount = 1.0, 200.0

pq = paraswap_client.get_quote(from_token, to_token, from_amount=from_amount)
print(f"price={pq['price']} from {from_token} to {to_token} from_amount={from_amount}")

try:
    pq = paraswap_client.get_quote(from_token, to_token, to_amount=to_amount)
    print(f"price={pq['price']} from {from_token} to {to_token} to_amount={to_amount}")
except ValueError as e:
    print(e)


from_token, to_token = 'OMG', 'ETH'
from_amount, to_amount = 200.0, 1.0

pq = paraswap_client.get_quote(from_token, to_token, from_amount=from_amount)
print(f"price={pq['price']} from {from_token} to {to_token} from_amount={from_amount}")

try:
    pq = paraswap_client.get_quote(from_token, to_token, to_amount=to_amount)
    print(f"price={pq['price']} from {from_token} to {to_token} to_amount={to_amount}")
except ValueError as e:
    print(e)

