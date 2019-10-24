from datetime import datetime
from collections import OrderedDict

import mysql.connector
# from mysql.connector import Error
from mysql.connector.conversion import Decimal
import json
import v2_client
 
def connect(conn_info):
    """ Connect to MySQL database """
    return mysql.connector.connect(**conn_info)

def close(conn):
    if conn and conn.is_connected():
        print("closing DB connection ...")
        cursor = conn.cursor()
        cursor.close()
        conn.close()
 
def execute(conn, sql):
    cursor = conn.cursor()
    cursor.execute(sql)
    return cursor.fetchall()

def column_names():
    return "id blockNumber logIndex timestampSeconds makerToken takerToken makerAmount takerAmount exchangeId".split()
 
#########################################################################

# if makerAmount is the amount of takerToken the maker gets then:
def print_row_and_json(r, api_json):
    dex = v2_client.data_exchanges_by_id()[r['exchangeId']]
    maker_token, taker_token = map(lambda p: v2_client.tokens_by_addr()[r[p]], ['makerToken', 'takerToken'])
    maker_amount = v2_client.real_amount(r['makerAmount'], maker_token)
    taker_amount = v2_client.real_amount(r['takerAmount'], taker_token)

    j = OrderedDict(id=r['id'], exchangeId=r['exchangeId'], timestamp=r['timestampSeconds'])
    
    side = 'buy' if taker_token == 'ETH' else 'sell' # side is always the taker's side
    if side == 'buy':
        j['amount'] = str(maker_amount)  # amount is always the amount of the non-ETH token
        j['price'] = taker_amount/maker_amount # price is always the amount of ETH / amount of non-ETH token
    else: # side == 'sell'
        j['amount'] = str(taker_amount)
        j['price'] = maker_amount/taker_amount
    j['side'] = side

    print(f"{r['id']}: {side} - {dex} at {datetime.fromtimestamp(j['timestamp'])} --- maker got {taker_amount} {taker_token} taker got {maker_amount} {maker_token} (price={j['price']})")
    print(f"from db:  {json.dumps(j)}")
    print(f"from api: {api_json}")


def do_pair(api_json):
    ids = tuple(map(lambda r: r['id'], api_json))
    sql = f"SELECT * from trade WHERE id IN {ids} ORDER BY id DESC"
    print(f"\nExecuting SQL: {sql!r}")
    rows = execute(conn, sql)

    for r in map(lambda r: dict(zip(column_names(), r)), rows):
        from_api = next(filter(lambda h: h['id'] == r['id'], api_json))
        print_row_and_json(r, from_api)

#########################################################################

CONN_INFO = OrderedDict(host='totle-data.c0umqlycacce.us-east-1.rds.amazonaws.com', database='totle', user='user_ed', password='rHI[ySF}A1c0})8o0f[Q39m>o8i3<2p[(Ie2a5Co2WyL0OZU')

if __name__ == '__main__':
    print(f"Connecting to {CONN_INFO['host']}")
    conn = connect(CONN_INFO)

    do_pair(v2_client.get_trades('CVC', 'ETH', limit=20))
    exit(0)

    # 1. Print last buy and sell by exchange
    # This assumes X/ETH pairs, i.e. it ignores DAI/USD
    print("Exchange\tlast buy\tlast sell")
    for dex_id in v2_client.data_exchanges_by_id():
        brows = execute(conn, f"SELECT timestampSeconds from trade WHERE takerToken='0x0000000000000000000000000000000000000000' AND exchangeId={dex_id} ORDER BY timestampSeconds DESC LIMIT 1")
        last_buy = datetime.fromtimestamp(brows[0][0]) if brows else "\t"
        srows = execute(conn, f"SELECT timestampSeconds from trade WHERE makerToken='0x0000000000000000000000000000000000000000' AND exchangeId={dex_id} ORDER BY timestampSeconds DESC LIMIT 1")
        last_sell = datetime.fromtimestamp(srows[0][0]) if srows else "\t"
        print(f"{v2_client.data_exchanges_by_id()[dex_id]:8}:\t{last_buy}\t{last_sell}")

    # 2. List exchanges with number of 0-amount (infinitely-priced) trades
    print("Exchange\tnum records with makerAmount=0 and takerAmount != 0:")
    mrows = execute(conn, f"SELECT COUNT(*), exchangeId from trade WHERE makerAmount=0 AND NOT takerAmount=0 GROUP BY exchangeId")
    for r in mrows:
        count, dex_id = r
        print(f"{v2_client.data_exchanges_by_id()[dex_id]:8}:\t{count}")
    print("Exchange\tnum records with takerAmount=0 and makerAmount != 0:")
    trows = execute(conn, f"SELECT COUNT(*), exchangeId from trade WHERE takerAmount=0 AND NOT makerAmount=0 GROUP BY exchangeId")
    for r in trows:
        count, dex_id = r
        print(f"{v2_client.data_exchanges_by_id()[dex_id]:8}:\t{count}")

    # 3. Check a few pairs JSON
    # CW missing data: TUSD/ETH, TKN/ETH, REQ/ETH, DGX/ETH, SNT/ETH, CVC/ETH, DATA/ETH
    do_pair(v2_client.get_trades('TUSD', 'ETH', limit=20))
    do_pair(v2_client.get_trades('CVC', 'ETH', limit=20))
    do_pair(v2_client.get_trades('SNT', 'ETH', limit=20))

    close(conn)

