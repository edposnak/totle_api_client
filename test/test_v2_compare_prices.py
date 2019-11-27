import json

import v2_compare_prices

def test_csv_writer():
    with v2_compare_prices.SavingsCSV('foobar', fieldnames="foo bar".split()) as csv_writer:
        csv_writer.append({'foo':1, 'bar':2})

def test_print_average_savings_by_dex():
    avg_savings = {
        'BAT' : {
            'Uniswap': {'pct_savings': 0.02},
            'Kyber': {'pct_savings': 0.03},
        },
        'CVC' : {
            'Uniswap': {'pct_savings': 0.5},
            'Kyber': {'pct_savings': 0.4},
        },
    }

    v2_compare_prices.print_average_savings_by_dex(avg_savings)

def test_best_price_with_fees():
    j = json.load(open('test_data/cryptowatch-bateth-orderbook.json'))
    r = j['result']
    asks, bids = r['asks'], r['bids']

    buysell, book = 'buy', asks
    fee_pct = 0.25

    for trade_size in [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 300.0, 400.0, 500.0]:
        price = v2_compare_prices.best_price_with_fees(trade_size, book, buysell, fee_pct)
        print(f"trade_size={trade_size} price={price}")

# test_csv_writer()
# test_print_average_savings_by_dex
test_best_price_with_fees()