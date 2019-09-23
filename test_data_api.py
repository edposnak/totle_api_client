import v2_client
from v2_client import TotleAPIException, supported_pairs, get_trades

def print_trades(trades, limit=None):
    print(f"Got {len(trades)} {trades[0]['side']}s:")
    print(f"DEX       \t    Price\t  Amount\tAmountB\tTimestamp")
    for t in trades[0:min(limit or len(trades), len(trades))]:
        dex = v2_client.all_exchanges_by_id[t['exchangeId']]

        price, amount, = float(t['price']), float(t['amount'])
        amount_b = amount if t['side'] == 'buy' else price * amount

        price_s = f"{price:8.2f}" if price > 1 else f"{price:8.2}"
        amount_s = f"{amount:8.2f}" if amount > 1 else f"{amount:8.2}"
        print(f"{dex:10}\t{price_s}\t{amount_s}\t{amount_b:.3}\t{t['timestamp']}")

PAGE_SIZE = 200
NUM_PAGES = 5

try:
    pairs = v2_client.supported_pairs

    for base, quote in pairs:
        buys, sells, page_num = [], [], 0
        while page_num < NUM_PAGES:
            trades = v2_client.get_trades(base, quote, limit=PAGE_SIZE, page=page_num)
            buys += [ t for t in trades if t['side'] == 'buy' ]
            sells += [ t for t in trades if t['side'] == 'sell' ]
            page_num += 1

        buy_amount = sum([ float(t['amount']) for t in buys  ])
        sell_amount = sum([ (float(t['amount']) * float(t['price'])) for t in sells  ])
        print(f"\n\n#####################")
        print(f"{base}/{quote}\n{len(buys)} buys, {len(sells)} sells, weighted buy/sell={(buy_amount/sell_amount):.4f}")
        # print_trades(buys, limit=20)
        # print_trades(sells, limit=20)


except v2_client.TotleAPIException as e:
    e.print()

    

