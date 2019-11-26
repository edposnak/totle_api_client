import binance_client
import huobi_client
import kraken_client


def test_translate_to_from_kraken():
    print(f"kraken_client.kraken_client.translate_to_kraken('ETH') = {kraken_client.translate_to_kraken('ETH')}")
    print(f"kraken_client.translate_from_kraken('XETH') = {kraken_client.translate_from_kraken('XETH')}")
    print(f"kraken_client.translate_to_kraken('ZEUR') = {kraken_client.translate_to_kraken('ZEUR')}")
    print(f"kraken_client.translate_from_kraken('ZEUR') = {kraken_client.translate_from_kraken('ZEUR')}")
    print(f"kraken_client.translate_to_kraken('USDT') = {kraken_client.translate_to_kraken('USDT')}")
    print(f"kraken_client.translate_from_kraken('USDT') = {kraken_client.translate_from_kraken('USDT')}")

#######################################################################################################################

test_translate_to_from_kraken()

