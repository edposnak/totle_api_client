usage: totle_api_client.py [-h] [--sell]
                           [tradeSize] [minSlippagePercent] [minFillPercent]

Run price comparisons

positional arguments:
  tradeSize           the size (in ETH) of the order
  minSlippagePercent  acceptable percent of slippage
  minFillPercent      acceptable percent of amount to acquire

optional arguments:
  -h, --help          show this help message and exit
  --sell              execute sell orders (default is buy)
