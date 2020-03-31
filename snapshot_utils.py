import functools
import json
import os

import token_utils
import totle_client

@functools.lru_cache(64)
def exchange_name(ex_id):
    return totle_client.exchanges_by_id()[ex_id]

SNAP_DATA_DIRECTORY = '/Users/ejp/projects/totle_api_client/snap_data'
def fetch_snapshot(id):
    json_filename = os.path.join(SNAP_DATA_DIRECTORY, str(id))
    print(f"looking for {json_filename}!")
    if os.path.exists(json_filename):
        print(f"FOUND JSON file for {id}!")
        return json.load(open(json_filename))
    else:
        print(f"no JSON file for {id}, fetching from network")
        j = totle_client.get_snapshot(id)
        with open(json_filename, 'w') as outfile:
            json.dump(j, outfile, indent=3)
        return j


def print_curve_info(j):
    # sd = totle_client.swap_data(j['response']['response'], True)
    # print(json.dumps(sd, indent=3))
    for swap in j['swaps']:
        # source_amount = swap['sourceAmount']
        # destination_amount = swap['destinationAmount']
        real_source_amount = token_utils.real_amount(swap['sourceAmount'], swap['sourceAsset']['symbol'])
        real_destination_amount = token_utils.real_amount(swap['destinationAmount'], swap['destinationAsset']['symbol'])

        # for route in swap['routes']:
        best_route = max(swap['routes'], key=lambda r: float(r['rate']))
        source_asset = best_route['sourceAsset']['symbol']
        destination_asset = best_route['destinationAsset']['symbol']
        num_trades = len(best_route['trades'])
        best_rate = float(best_route['rate'])
        best_price = 1 / best_rate
        print(f"BEST Route {round(real_source_amount)} {source_asset} gets {round(real_destination_amount)} {destination_asset} price={best_price:.6g} rate={best_rate:.6g} using {num_trades} trades")

        for trade in best_route['trades']:
            rates = {}
            for i, order in enumerate(trade['orders']['main']):
                order_source_asset = order['sourceAsset']['symbol']
                order_destination_asset = order['destinationAsset']['symbol']
                order_real_source_amount = token_utils.real_amount(int(order['destinationAmount']), order_destination_asset)
                order_real_destination_amount = token_utils.real_amount(int(order['volume']), order_source_asset)
                order_dex = exchange_name(order['exchangeId'])
                order_pct = order['splitPercentage']
                order_rate = float(order['rate'])
                rates[order_dex] = order_rate
                print(f"   Order {i} got {round(order_real_source_amount)} {order_destination_asset} for {round(order_real_destination_amount)} {order_source_asset} (rate={order_rate:.6g} on {order_dex} ({order_pct} % of split)")


            for s in trade['split']:
                dex = exchange_name(s['exchangeId'])
                pct = float(s['percentage'])
                real_split_source_amount = real_source_amount * pct / 100
                print(f"   Split for {destination_asset}/{source_asset} on {dex} ({pct}% of split spends {real_split_source_amount} {source_asset})")
                amt_rates = [ [float(amt), float(rate)] for amt, rate in s['dataPoints'] ]
                for i, amt_rate in enumerate(amt_rates):
                    if amt_rate[0] < real_split_source_amount: split_index = i

                print(f"      {amt_rates[0][0]:>10.6g} {amt_rates[0][1]:.3f}")
                if split_index > 0:
                    print(f"      {amt_rates[split_index][0]:>10.6g} {amt_rates[split_index][1]:.3f}")
                print(f"      {real_split_source_amount:>10.6g} {rates[dex]:.3f} <- split value (interpolated)")
                if len(amt_rates) > split_index + 2:
                    print(f"      {amt_rates[split_index+1][0]:>10.6g} {amt_rates[split_index+1][1]:.3f}")
                print(f"      {amt_rates[-1][0]:>10.6g} {amt_rates[-1][1]:.3f}")

            # for c in trade['curveData']:
            #     dex = exchange_name(c['exchangeId'])
            #     print(f"   Curve Data for {destination_asset}/{source_asset} on {dex}")
            #     print(f"      {float(c['curveData'][0][0]):.6g}:\t{float(c['curveData'][0][1]):.3f} - {float(c['curveData'][-1][0]):.6g}:\t{float(c['curveData'][-1][1]):.3f}")

