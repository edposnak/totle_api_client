This library isn't well-documented or even user friendly, as it was not developed for general use. Below is a quick guide.

Works with python 3.8.5 and maybe earlier versions. Definitely not 2.x.

To generate price comparison data run:
`python totle_vs_aggs.py`

The above will capture price comparison data in a timestampe CSV file in the outputs directory.

Each row of the CSV contains a price comparison of a Totle price vs a competitor's price. The meanings of the CSV columns are as follows:
* time - when the price quote comparison happened
* id - a Totle id to correlate with additional data in Totle's database
* action - buy or sell
* trade_size - trade size in ETH
* token - the token being bought
* quote - the token being sold
* exchange - the exchange or competitor against which Totle is being compared
* exchange_price - the price quoted by the exchange or competitor
* totle_used - the exchange(s) used by Totle
* totle_price - the price quoted by Totle
* totle_splits - the allocations of the trade sizes to the exchanges used by Totle
* pct_savings - the amount of savings Totle got relative to exchange or competitor (negative value means Totle got worse price)
* splits - the allocations of the trade sizes to the exchanges used by exchange or competitor
* ex_prices - additional price quotes from individual exchanges (if provided by competitor)

To analyze price comparison data run:
`python summarize_totle_vs_aggs.py`

Currently neither of these programs are configurable. Configuration (e.g. changing pairs, trade sizes etc.) requires changing the python code.


