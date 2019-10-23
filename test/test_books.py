import binance_client
import huobi_client
import kraken_client

ALL_CLIENTS = [binance_client, huobi_client, kraken_client]

QUOTE = 'ETH'

def in_all(t, tokens_by_client):
    for c in tokens_by_client:
        if t not in tokens_by_client[c]: return False
    return True

tokens_by_client = {}
for c in ALL_CLIENTS:
    print(f"{c.name()} Pairs")
    pairs = sorted([(b, q) for b, q in c.get_pairs(QUOTE)])
    print(pairs)
    tokens_by_client[c] = list(map(lambda p: p[0], pairs))

for c, tokens in tokens_by_client.items():
    print(f"{c.name()} tokens: {','.join(tokens)}")

overlap_tokens = [ t for t in tokens_by_client[kraken_client] if in_all(t, tokens_by_client) ]
print(f"overlap tokens: {','.join(overlap_tokens)}")
# overlap tokens: ADA,BAT,EOS,ICX,LINK,QTUM,SC,WAVES

for base in overlap_tokens:
    print(f"\n\n{QUOTE}/{base}")
    for c in ALL_CLIENTS:
        bids, asks = c.get_depth(base, QUOTE)
        print(f"    {c.name()} Bids: ", bids[0:4])
        print(f"    {c.name()} Asks: ", asks[0:4])

