from datetime import datetime
import v2_client


def print_trades(trades, limit=None):
    print(f"Got {len(trades)} {trades[0]['side']}s:")
    print(f"DEX       \t   Price\t  Amount\tBase Amount\tTimestamp")
    for t in trades[0:min(limit or len(trades), len(trades))]:
        dex = v2_client.data_exchanges_by_id[t['exchangeId']]

        price, amount, = float(t['price']), float(t['amount'])
        amount_b = amount if t['side'] == 'buy' else price * amount

        price_s = f"{price:8.3f}" if price > 0.1 else f"{price:8.3}"
        amount_s = f"{amount:8.2f}" if amount > 0.1 else f"{amount:8.2}"
        timestamp_s = f"{datetime.fromtimestamp(int(t['timestamp']))}"
        print(f"{dex:10}\t{price_s}\t{amount_s}\t   {amount_b:8.2f}\t{timestamp_s}")


def print_summary(base, quote, buys, sells):
    print(f"\n\n#####################")
    print(f"{base}/{quote}")

    last_buy = datetime.fromtimestamp(int(buys[0]['timestamp']))
    first_buy = datetime.fromtimestamp(int(buys[-1]['timestamp']))
    buy_time = last_buy-first_buy
    seconds_per_buy = buy_time.total_seconds() / len(buys)
    buy_amount = sum([ float(t['amount']) for t in buys  ])

    last_sell = datetime.fromtimestamp(int(sells[0]['timestamp']))
    first_sell = datetime.fromtimestamp(int(sells[-1]['timestamp']))
    sell_time = last_sell-first_sell
    seconds_per_sell = sell_time.total_seconds() / len(sells)
    sell_amount = sum([ (float(t['amount']) * float(t['price'])) for t in sells  ])


    print(f"{len(buys)} buys totaling {buy_amount} {quote} from {first_buy} to {last_buy} ({buy_time})")
    print(f"1 buy every {seconds_per_buy:.1f} seconds")

    print(f"{len(sells)} sells totaling {sell_amount} {quote} from {first_sell} to {last_sell} ({sell_time}) ")
    print(f"1 sell every {seconds_per_sell:.1f} seconds")

    print(f"buy/sell amount ratio={(buy_amount/sell_amount):.4f}")
    # buy/sell freq = (1/seconds_per_buy) / (1/seconds_per_sell)
    print(f"buy/sell frequency ratio={(seconds_per_sell/seconds_per_buy):.2f}")


PAGE_SIZE = 200
NUM_PAGES = 5

try:
    for base, quote in v2_client.supported_pairs:
        buys, sells, page_num = [], [], 0
        while page_num < NUM_PAGES:
            trades = v2_client.get_trades(base, quote, limit=PAGE_SIZE, page=page_num)
            buys += [ t for t in trades if t['side'] == 'buy' ]
            sells += [ t for t in trades if t['side'] == 'sell' ]
            page_num += 1


        print_summary(base, quote, buys, sells)
        # print_trades(buys, limit=20)
        # print_trades(sells, limit=20)

except v2_client.TotleAPIException as e:
    e.print()

    

