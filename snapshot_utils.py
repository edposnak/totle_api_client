import functools
import json
import os
from collections import defaultdict

import token_utils
import totle_client

DEFAULT_PCT_INC = 2

@functools.lru_cache(64)
def exchange_name(ex_id):
    return totle_client.exchanges_by_id()[ex_id]

SNAP_DATA_DIRECTORY = '/Users/ejp/projects/totle_api_client/snap_data'
def fetch_snapshot(id):
    json_filename = os.path.join(SNAP_DATA_DIRECTORY, str(id))
    if os.path.exists(json_filename):
        # print(f"FOUND JSON file for {id}!")
        return json.load(open(json_filename))
    else:
        # print(f"FETCHING JSON from network, saving into {json_filename}")
        j = totle_client.get_snapshot(id)
        with open(json_filename, 'w') as outfile:
            json.dump(j, outfile, indent=3)
        return j


def fetch_and_print_curve_info(id):
    print_curve_info(fetch_and_get_curve_info(id))

def fetch_and_get_curve_info(id):
    '''Returns an array of swaps and the info related to their best routes for the given id'''
    return get_curve_info(fetch_snapshot(id))


def get_curve_info(j):
    '''Returns an array of swaps and the info related to their best routes for the given JSON'''
    curve_info = []
    # sd = totle_client.swap_data(j['response']['response'], True)

    respresp = j['response']['response']
    response_id = respresp['id']
    # if len(respresp['summary']) > 1: raise ValueError(f"response response has multiple summaries")
    summary = respresp['summary'][0]
    summary_source_asset = summary['sourceAsset']['symbol']
    summary_source_amount = token_utils.real_amount(summary['sourceAmount'], summary_source_asset)
    summary_rate = float(summary['rate'])

    for swap in j['swaps']:
        swap_data = {}

        swap_source_asset = swap['sourceAsset']['symbol']
        swap_source_amount = token_utils.real_amount(swap['sourceAmount'], swap_source_asset)

        if swap_source_asset == summary_source_asset and round(swap_source_amount) != round(summary_source_amount):
            raise ValueError(f"swap_source_amount={round(swap_source_amount)} {swap_source_asset} DOES NOT EQUAL summary_source_amount {round(summary_source_amount)} {summary_source_asset}")

        viable_routes = swap['routes']

        for i, route in enumerate(viable_routes):
            route_source_asset = route['sourceAsset']['symbol']
            if route_source_asset != swap_source_asset:
                raise ValueError(f"route source asset={route_source_asset} BUUUUUT swap_source_asset={swap_source_asset}")
            if route['rate'] == swap['rate'] and swap_source_amount - token_utils.real_amount(route['sourceAmount'], route['sourceAsset']['symbol']) < 0.5:
                used_route = route
            #
            # route_data = {
            #     'source_asset': route['sourceAsset']['symbol'],
            #     'destination_asset': route['destinationAsset']['symbol'],
            #     'real_source_amount': token_utils.real_amount(route['sourceAmount'], route_source_asset),
            #     'real_destination_amount': token_utils.real_amount(route['destinationAmount'], route['destinationAsset']['symbol']),
            #     'num_trades': len(route['trades']),
            #     'rate': float(route['rate']),
            #     'trades': get_trades_info(route['trades'])
            # }
            # print(f"DEBUG Route {i} = { route_data['real_source_amount']} {route_data['source_asset']} gets {round(route_data['real_destination_amount'])} {route_data['destination_asset']} price={1 / route_data['rate']:.6g} rate={route_data['rate']:.6g} using {route_data['num_trades']} trades")


        # filter out routes that don't have enough liquidity (sourceAmount)
        # viable_routes = filter(lambda route: swap_source_amount - token_utils.real_amount(route['sourceAmount'], route['sourceAsset']['symbol']) < 0.5, viable_routes)
        best_route = max(viable_routes, key=lambda r: float(r['rate']))
        best_route_source_asset = best_route['sourceAsset']['symbol']
        best_route_source_amount = token_utils.real_amount(best_route['sourceAmount'], best_route_source_asset)
        # if best_route_source_asset == swap_source_asset and round(best_route_source_amount) != round(swap_source_amount):
        #     raise ValueError(f"best_route_source_asset={round(best_route_source_amount)} {best_route_source_asset} DOES NOT EQUAL swap_source_amount {round(swap_source_amount)} {swap_source_asset}")

        swap_data['used_route'] = {
            'source_asset': used_route['sourceAsset']['symbol'],
            'destination_asset': used_route['destinationAsset']['symbol'],
            'real_source_amount': swap_source_amount,
            'real_destination_amount': token_utils.real_amount(swap['destinationAmount'], swap['destinationAsset']['symbol']),
            'num_trades': len(used_route['trades']),
            'rate': float(used_route['rate']),
            'trades': get_trades_info(used_route['trades'])
        }

        swap_data['best_route'] = {
            'source_asset': best_route['sourceAsset']['symbol'],
            'destination_asset': best_route['destinationAsset']['symbol'],
            'real_source_amount': token_utils.real_amount(best_route['sourceAmount'], best_route_source_asset),
            'real_destination_amount': token_utils.real_amount(best_route['destinationAmount'], best_route['destinationAsset']['symbol']),
            'num_trades': len(best_route['trades']),
            'rate': float(best_route['rate']),
            'trades': get_trades_info(best_route['trades'])
        }
        
        if swap_data['best_route']['rate'] != summary_rate:
            print(f"DIFF RATE: best_route rate={swap_data['best_route']['rate']} summary_rate={summary_rate}\n{response_id}")

        # sdbr = swap_data['best_route']
        # print(f"DEBUG BEST Route = { sdbr['real_source_amount']} {sdbr['source_asset']} gets {round(sdbr['real_destination_amount'])} {sdbr['destination_asset']} price={1 / sdbr['rate']:.6g} rate={sdbr['rate']:.6g} using {sdbr['num_trades']} trades")

        curve_info.append(swap_data)

    return curve_info


def get_trades_info(trades):
    trade_datas = []
    for trade in trades:
        trade_data = {
            'source_asset': trade['sourceAsset']['symbol'],
            'destination_asset': trade['destinationAsset']['symbol'],
            'real_source_amount': token_utils.real_amount(trade['sourceAmount'], trade['sourceAsset']['symbol']),
            'real_destination_amount': token_utils.real_amount(trade['destinationAmount'], trade['destinationAsset']['symbol']),
            'rate': float(trade['rate']),
            'orders': [],
            'splits': []
        }
        # print(f"DEBUG Trade n from {trade_data['source_asset']} to {trade_data['destination_asset']}")
        # print("---------------------")
        # print(json.dumps(trade, indent=3))
        # print("---------------------")

        rates = {}  # need to extract these from orders and plug them in to split['rate']
        for order in trade['orders']['main']:
            rates[exchange_name(order['exchangeId'])] = float(order['rate'])

            order_data = {
                'source_asset': order['sourceAsset']['symbol'],
                'destination_asset': order['destinationAsset']['symbol'],
                'real_source_amount': token_utils.real_amount(order['destinationAmount'], order['destinationAsset']['symbol']),
                'real_destination_amount': token_utils.real_amount(order['sourceAmount'], order['sourceAsset']['symbol']),  # order['volume'] doesn't exist in 0xce2e80f540c847f4a13053d87ad68cfd965760992989480b92a7fceec2c550b1
                'dex': exchange_name(order['exchangeId']),
                'pct': order['splitPercentage'],
                'rate': float(order['rate']),
            }
            # print(f"   DEBUG Order n on {order_data['dex']} from {order_data['source_asset']} to {order_data['destination_asset']}")
            trade_data['orders'].append(order_data)

        for s in trade['split']:
            dex = exchange_name(s['exchangeId'])
            pct = float(s['percentage'])
            if not pct: # sometimes there are 0% splits with DEXs that are not in rates because there are no orders for that DEX
                print(f"   WARNING: skipping {dex} with {pct}% split")
                continue
            real_split_source_amount = trade_data['real_source_amount'] * pct / 100
            amt_rates = [[float(amt), float(rate)] for amt, rate in s['dataPoints']]

            # print(f"   DEBUG: {dex} ({pct}% split) spends {round(real_split_source_amount)} {trade_data['source_asset']} to get {trade_data['destination_asset']} at rate = {rates[dex]})")

            split_low_index = -1  # sometimes the dataPoints start at an amount > trade size
            for i, amt_rate in enumerate(amt_rates):
                if amt_rate[0] < real_split_source_amount: split_low_index = i
            split_high_index, split_last_index = split_low_index + 1, len(amt_rates) - 1

            # print(f"\nDEBUG {dex} dataPoints")
            # for amt_rate in amt_rates: print_amt_rate(amt_rate)

            split_data = {
                'dex': dex,
                'pct': pct,
                'rate': rates[dex],
                'real_source_amount': real_split_source_amount,
                'low_index': split_low_index,
                'high_index': split_high_index,
                'last_index': split_last_index,
                'curve': {'min': amt_rates[0],
                          'split_low': amt_rates[split_low_index] if split_low_index > 0 else None,
                          'split_high': amt_rates[split_high_index] if split_high_index < split_last_index else None,
                          'max': amt_rates[-1]
                          },
            }

            trade_data['splits'].append(split_data)

        trade_datas.append(trade_data)
    return trade_datas


def print_curve_info(curve_info, pct_inc=DEFAULT_PCT_INC):
    for swap in curve_info:
        best_route = swap['best_route']
        print(f"BEST Route {round(best_route['real_source_amount'])} {best_route['source_asset']} gets {round(best_route['real_destination_amount'])} {best_route['destination_asset']} price={1/best_route['rate']:.6g} rate={best_route['rate']:.6g} using {best_route['num_trades']} trade(s)")
        print_trades_info(best_route['trades'])

        used_route = swap['used_route']
        print(f"USED Route {round(used_route['real_source_amount'])} {used_route['source_asset']} gets {round(used_route['real_destination_amount'])} {used_route['destination_asset']} price={1/used_route['rate']:.6g} rate={used_route['rate']:.6g} using {used_route['num_trades']} trade(s)")
        print_trades_info(used_route['trades'])

def print_trades_info(trades, with_orders=True):
    for i, trade in enumerate(trades):
        print(f"   Trade {i} {round(trade['real_source_amount'])} {trade['source_asset']} for {round(trade['real_destination_amount'])} {trade['destination_asset']} rate={trade['rate']:.6g}")
        for split in trade['splits']:
            split_low, split_high = split['curve']['split_low'], split['curve']['split_high']

            print(f"      {split['dex']} ({split['pct']}% split) for {trade['destination_asset']}/{trade['source_asset']} (spends {round(split['real_source_amount'])} {trade['source_asset']} rate={split['rate']:.3f})")

            print_amt_rate(split['curve']['min'])
            if split_low: print_amt_rate(split_low)
            print_amt_rate([split['real_source_amount'], split['rate']], suffix=f"<- split value (interpolated) {'MAX POSSIBLE ALLOCATION' if is_max_alloc(split) else ''}")
            if split_high: print_amt_rate(split_high)
            print_amt_rate(split['curve']['max'])

            # print(f"top_liquidity={is_top_liquidity(split)} max_alloc={is_max_alloc(split, pct_inc=pct_inc)}")

        if not with_orders: return

        for order in trade['orders']:
            print(f"      Order got {round(order['real_source_amount'])} {order['destination_asset']} for {round(order['real_destination_amount'])} {order['source_asset']} (rate={order['rate']:.6g} on {order['dex']} ({order['pct']} % of split)")


def print_amt_rate(amt_rate, indent=6, suffix=''):
    amount, rate = amt_rate
    print(indent*' ', f"{amount:>10.6g} {rate:.3f} {suffix}")

def print_max_allocs(curve_info, only_dexs=['Kyber', 'Uniswap', 'Oasis'], pct_inc=DEFAULT_PCT_INC):
    for swap in curve_info:
        best_route = swap['best_route']
        for trade in best_route['trades']:
            for split in trade['splits']:
                if is_max_alloc(split, pct_inc=pct_inc): # and split['dex'] in only_dexs:
                    print(f"   MAX POSSIBLE ALLOCATION of {split['pct']}% to {split['dex']} for {trade['destination_asset']}/{trade['source_asset']} (rate={split['rate']})")


def is_max_alloc(split, pct_inc=DEFAULT_PCT_INC):
    return split['real_source_amount'] * (split['pct'] + pct_inc) / split['pct'] > split['curve']['max'][0]

def is_top_liquidity(split):
    return split['high_index'] == split['last_index']


