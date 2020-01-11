import binance_client
import huobi_client
import kraken_client

import token_utils


def print_cex_overlap():
    kraken_pairs = kraken_client.get_pairs()
    kraken_tokens = sorted([pair[0] for pair in kraken_pairs])
    print(f"kraken: {kraken_tokens}")
    binance_pairs = binance_client.get_pairs()
    binance_tokens = sorted([pair[0] for pair in binance_pairs])
    print(f"binance: {binance_tokens}")
    huobi_pairs = huobi_client.get_pairs()
    huobi_tokens = sorted([pair[0] for pair in huobi_pairs])
    print(f"huobi: {huobi_tokens}")
    kraken_binance_tokens = sorted([t for t in kraken_tokens if t in binance_tokens])
    print(f"kraken/binance: {kraken_binance_tokens}")
    kraken_huobi_tokens = sorted([t for t in kraken_tokens if t in huobi_tokens])
    print(f"kraken/huobi: {kraken_huobi_tokens}")
    binance_huobi_tokens = sorted([t for t in binance_tokens if t in huobi_tokens])
    print(f"binance/huobi: {binance_huobi_tokens}")
    kraken_binance_huobi_tokens = sorted([t for t in kraken_binance_tokens if t in binance_huobi_tokens])
    print(f"kraken/binance/huobi: {kraken_binance_huobi_tokens}")



def print_totle_cex_overlap():
    totle_tokens = token_utils.tradable_tokens()
    kraken_overlap_pairs = kraken_client.get_overlap_pairs(totle_tokens)
    binance_overlap_pairs = binance_client.get_overlap_pairs(totle_tokens)
    huobi_overlap_pairs = huobi_client.get_overlap_pairs(totle_tokens)

    totle_kraken_binance_tokens = sorted([b for b,q in kraken_overlap_pairs if (b,q) in binance_overlap_pairs])
    print(f"totle_kraken_binance_tokens={totle_kraken_binance_tokens}")
    totle_kraken_huobi_tokens = sorted([b for b,q in kraken_overlap_pairs if (b,q) in huobi_overlap_pairs])
    print(f"totle_kraken_huobi_tokens={totle_kraken_huobi_tokens}")
    totle_binance_huobi_tokens = sorted([b for b,q in binance_overlap_pairs if (b,q) in huobi_overlap_pairs])
    print(f"totle_binance_huobi_tokens={totle_binance_huobi_tokens}")


#######################################################################################################################

print_cex_overlap()

print_totle_cex_overlap()

