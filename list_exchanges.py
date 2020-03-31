#!/usr/local/bin/python3

import totle_client
print(totle_client.enabled_exchanges())

print(f"\nSwap Exchanges")
for name, id in totle_client.exchanges().items():
    print(f"{id:<3}: {name}")

print(f"\nData Exchanges")
for name, id in totle_client.data_exchanges().items():
    print(f"{id:<3}: {name}")
