import v2_compare_prices

# with v2_compare_prices.SavingsCSV('foobar', fieldnames="foo bar".split()) as csv_writer:
#     csv_writer.append({'foo':1, 'bar':2})

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
