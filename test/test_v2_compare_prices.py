import v2_compare_prices

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
