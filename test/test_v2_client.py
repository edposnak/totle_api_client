import json
import v2_client

print(v2_client.name())


print(v2_client.exchanges())
print(v2_client.enabled_exchanges())
print(v2_client.data_exchanges())

print(v2_client.tokens_json())
print(v2_client.tokens())
print(v2_client.token_decimals())
print(v2_client.tokens_by_addr())

print(v2_client.int_amount(1.2, 'ETH'))