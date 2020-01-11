import binance_client
import huobi_client
import kraken_client
import totle_client
import dexag_client
import oneinch_client
import token_utils


# print(totle_client.get_pairs('USDC'))
print(dexag_client.get_pairs())

ALL_CEX_CLIENTS = [binance_client, huobi_client, kraken_client]
ALL_AGG_CLIENTS = [totle_client, dexag_client, oneinch_client]

QUOTE = 'ETH'
for c in ALL_CEX_CLIENTS + ALL_AGG_CLIENTS:
    overlap_pairs = [(b, q) for b, q in c.get_pairs(QUOTE) if b in token_utils.tokens()]
    overlap_tokens = sorted([ b for b,q in overlap_pairs ])
    print(f"{c.name()} has {len(overlap_pairs)} overlap XXX/ETH pairs:", overlap_tokens)
    if 'DAI' in overlap_tokens: print(f"{c.name()} has DAI")




