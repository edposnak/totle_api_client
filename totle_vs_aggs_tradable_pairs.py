import csv
import json
import os
import random
from collections import defaultdict
import concurrent.futures
from itertools import permutations, combinations

import dexag_client
import oneinch_client
import paraswap_client
import token_utils
import v2_client

from v2_compare_prices import get_filename_base, SavingsCSV


AGG_CLIENTS = [v2_client, dexag_client, oneinch_client, paraswap_client]
CSV_FIELDS = ['base', 'quote'] + [ a.name() for a in AGG_CLIENTS ]

def check_pair(base, quote, usd_price_of_quote, csv_writer):
    result = {'base': base, 'quote': quote}

    # set the from_amount so it's roughly the same ($10 USD) across all swaps
    from_amount = 10 / usd_price_of_quote

    # Now see who has the pair
    for agg_client in AGG_CLIENTS:
        try:
            pq = agg_client.get_quote(quote, base, from_amount=from_amount)
            result[agg_client.name()] = True if pq else None
        except Exception as e:
            # print(e)
            pass

    print(f"returning {result}")
    csv_writer.append(result)
    return result

def summarize_csv(filename):
    agg_pairs, all_pairs = defaultdict(list), []
    agg_names = [ agg_client.name() for agg_client in AGG_CLIENTS ]
    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=None)
        for row in reader:
            base, quote = row['base'], row['quote']
            pair = (base, quote)
            all_pairs.append(pair)
            for agg_name in agg_names:
                if row[agg_name]: agg_pairs[agg_name].append(pair)

    print(f"\n\n{filename.split('tokens_')[1]}")
    for agg, pairs in agg_pairs.items():
        print(f"{agg}: {len(pairs)} / {len(all_pairs)} pairs")

    return agg_pairs

def do_summary():
    # agg_pairs = summarize_csv('outputs/totle_vs_agg_supported_tokens_2019-12-07_11:06:53.csv')
    # print(f"agg_pairs['Totle'] ({len(agg_pairs['Totle'])} pairs) = {agg_pairs['Totle']}")
    # exit(0)

    csv_files = ['totle_vs_agg_supported_tokens_2019-12-05_18:47:50.csv', 'totle_vs_agg_supported_tokens_2019-12-06_11:25:17.csv', 'totle_vs_agg_supported_tokens_2019-12-06_17:55:13.csv', 'totle_vs_agg_supported_tokens_2019-12-07_13:04:21.csv', 'totle_vs_agg_supported_tokens_2019-12-07_11:06:53.csv', 'totle_vs_agg_supported_tokens_2019-12-07_17:09:20.csv', 'totle_vs_agg_supported_tokens_2019-12-07_17:54:29.csv']

    agg_pairs = defaultdict(set)
    for csv_file in csv_files:
        agg_pairs_f = summarize_csv(f'outputs/{csv_file}')
        for agg_name, pairs in agg_pairs_f.items():
            agg_pairs[agg_name] |= set(pairs)

    agg_tokens = {}
    for agg_name, pairs in agg_pairs.items():
        agg_tokens[agg_name] = set(sum(map(list, pairs), []))

    print("\n\n")
    for agg, pairs in agg_pairs.items():
        print(f"{agg} supports a total of {len(pairs)}  ERC-20/ERC-20 pairs")

    totle_pairs, totle_tokens = agg_pairs[v2_client.name()], agg_tokens[v2_client.name()]
    all_other_agg_exc_tokens, all_other_agg_exc_pairs = set(), set()
    summary_csv = ['Competitor,"Overlap","Exclusive to Totle","Exclusive to Competitor"']
    for other_agg_name in agg_pairs:
        if other_agg_name == v2_client.name(): continue

        other_agg_tokens = agg_tokens[other_agg_name]
        totle_exc_tokens = set(totle_tokens) - set(other_agg_tokens)
        other_agg_exc_tokens = set(other_agg_tokens) - set(totle_tokens)
        all_other_agg_exc_tokens |= other_agg_exc_tokens
        print(f"\nTotle supports {len(totle_exc_tokens)} tokens that {other_agg_name} doesn't: {totle_exc_tokens}")
        print(f"{other_agg_name} supports {len(other_agg_exc_tokens)} tokens that Totle doesn't: {other_agg_exc_tokens}")

        other_agg_pairs = agg_pairs[other_agg_name]
        totle_exc_pairs = set(totle_pairs) - set(other_agg_pairs)
        other_agg_exc_pairs = set(other_agg_pairs) - set(totle_pairs)
        all_other_agg_exc_pairs |= other_agg_exc_pairs
        overlap = set(totle_pairs) & set(other_agg_pairs)
        summary_csv.append(f"{other_agg_name},{len(overlap)},{len(totle_exc_pairs)},{len(other_agg_exc_pairs)}")
        # print(f"\nTotle and {other_agg_name} overlap in {len(overlap)} ERC-20/ERC-20 pairs")
        # print(f"Totle supports {len(totle_has)} pairs that {other_agg_name} doesn't: Totle: {len(set(totle_pairs))} {other_agg_name}: {len(set(other_agg_pairs))} diff={len(set(totle_pairs))-len(set(other_agg_pairs))}")
        # print(f"{other_agg_name} supports {len(other_agg_has)} pairs that Totle doesn't:")

        exc_pair_involving_exc_token = [ p for p in other_agg_exc_pairs if p[0] in other_agg_exc_tokens or p[1] in other_agg_exc_tokens]
        print(f"Of {other_agg_name}'s {len(other_agg_exc_pairs)} exclusive pairs, {len(exc_pair_involving_exc_token)} involved {other_agg_exc_tokens}")

    print(f"\n\n\nall_other_agg_exc_tokens={all_other_agg_exc_tokens}")
    all_exc_pair_involving_exc_token = [ p for p in all_other_agg_exc_pairs if p[0] in all_other_agg_exc_tokens or p[1] in all_other_agg_exc_tokens]
    print(f"Of all {len(all_other_agg_exc_pairs)} pairs exclusive to competitors, {len(all_exc_pair_involving_exc_token)} involved {all_other_agg_exc_tokens}")
    bad_pairs = all_other_agg_exc_pairs - set(all_exc_pair_involving_exc_token)
    bad_pairs_strs = sorted([ f"{p[0]}/{p[1]}" for p in bad_pairs ])
    print(f"The {len(bad_pairs)} pairs exclusive to competitors not involving these {len(all_other_agg_exc_tokens)} tokens were: {bad_pairs_strs}")
    bad_tokens = set(sum(map(list, bad_pairs), []))
    print(f"These pairs were various combinations of the following {len(bad_tokens)} tokens: {bad_tokens}")

    bad_tokens = {'CETH', 'MLN', 'LRC'}
    for t in bad_tokens:
        for agg_name, pairs in agg_pairs.items():
            agg_has_bad = [ p for p in pairs if t in p]
            print(f"{agg_name} {t} pairs: {agg_has_bad}")

        totle_has_bad = [ p for p in totle_pairs if t in p]
        print(f"Totle has {len(totle_has_bad)} pairs with {t}")

    print(f"\n\n")
    for row in summary_csv:
        print(row)

    print(f"\n\nOverlap Pairs")
    overlap_pairs = []
    for o_pair in agg_pairs[paraswap_client.name()]: # iterate through the agg with the least pairs
        if all([ o_pair in pairs for _, pairs in agg_pairs.items() ]):
            overlap_pairs.append(o_pair)
    print(f"there are {len(overlap_pairs)} pairs supported by Totle and all competitors")


    print(f"\n\nAppendix A: Pairs supported by other aggregators but not Totle")
    # base_pairstr_map = defaultdict(list)
    # for pair in sorted(all_other_agg_exc_pairs):
    #     base_pairstr_map[pair[0]].append(f"{pair[0]}/{pair[1]}")
    # for _, pair_str in base_pairstr_map.items():
    #     print(', '.join(pair_str))

ETH_PRICE = 148.00

def get_token_prices(tokens = None):
    all_tradable_tokens = tokens or token_utils.tradable_tokens()
    # TODO: remove ETH it's not really an ERC-20
    cmc_data = json.load(open(f'data/cmc_tokens.json'))['data']
    usd_prices = {t['symbol']: float(t['quote']['USD']['price']) for t in cmc_data if t['symbol'] in all_tradable_tokens}

    skipped_tokens, missing_tokens = set(), set(all_tradable_tokens) - set(usd_prices)
    print(f"CMC had prices for {len(usd_prices)}/{len(all_tradable_tokens)} tokens. Querying Totle for prices on the remaining {len(missing_tokens)} tokens")
    for missing_token in missing_tokens:
        if missing_token == 'CETH':
            usd_prices[missing_token] = 2.83
        else:
            totle_sd = v2_client.try_swap(v2_client.name(), missing_token, 'ETH', params={'toAmount': 0.1}, verbose=False, debug=False)

            if totle_sd:  # set the from_amount so it's roughly the same across all swaps
                usd_prices[missing_token] = ETH_PRICE / totle_sd['price']
            else:
                # If we can't get a price from CMC or Totle, then just discard this token. Other aggs may have the pair, but if you can't
                # buy it for ETH on Totle, then it is essentially not a "tradable" token as curated by Totle, and thus not in this study.
                skipped_tokens.add(missing_token)

    print(f"Skipping {skipped_tokens} because we couldn't get a price from CMC or Totle")
    return usd_prices

########################################################################################################################
BAD_PAIRS = {('NPXS', 'RCN'), ('FUN', 'MKR'), ('TAU', 'CND'), ('POE', 'RLC'), ('POE', 'MKR'), ('CVC', 'BLT'), ('TAU', 'KNC'), ('TKN', 'VERI'), ('TAU', 'BNT'), ('REN', 'DENT'), ('KIN', 'TUSD'), ('AST', 'MKR'), ('PAX', 'NPXS'), ('SAI', 'USDC'), ('POWR', 'DENT'), ('MKR', 'ETHOS'), ('NPXS', 'STORJ'), ('NPXS', 'ANT'), ('KNC', 'SPANK'), ('RDN', 'ETHOS'), ('WBTC', 'BLT'), ('TAU', 'MTL'), ('ZRX', 'BLT'), ('TAU', 'TKN'), ('PAX', 'DENT'), ('RCN', 'DENT'), ('LINK', 'BLT'), ('CND', 'DENT'), ('ENG', 'POLY'), ('NEXO', 'DENT'), ('NPXS', 'TAU'), ('LEND', 'POLY'), ('OMG', 'ETHOS'), ('GNO', 'BLT'), ('ABYSS', 'SPANK'), ('USDT', 'DENT'), ('TUSD', 'POLY'), ('POE', 'TUSD'), ('NPXS', 'FUN'), ('CND', 'REP'), ('CDT', 'POLY'), ('PAX', 'ETHOS'), ('FUN', 'MCO'), ('REP', 'ETHOS'), ('BAT', 'NPXS'), ('REP', 'POLY'), ('XDCE', 'SPANK'), ('RLC', 'LINK'), ('KNC', 'POLY'), ('MKR', 'BLT'), ('TUSD', 'RPL'), ('BNT', 'POLY'), ('CDT', 'GNO'), ('STORJ', 'POLY'), ('POE', 'ETHOS'), ('RLC', 'POLY'), ('SPANK', 'ETHOS'), ('KNC', 'DENT'), ('XDCE', 'WBTC'), ('MANA', 'AST'), ('MANA', 'BLT'), ('REP', 'DENT'), ('NPXS', 'LEND'), ('AST', 'REP'), ('RPL', 'ETHOS'), ('CDT', 'DENT'), ('BAT', 'DENT'), ('TUSD', 'DENT'), ('TAU', 'USDT'), ('USDT', 'POLY'), ('KIN', 'KNC'), ('NPXS', 'PAY'), ('AST', 'CZRX'), ('XDCE', 'ETHOS'), ('CDT', 'ETHOS'), ('USDC', 'NPXS'), ('KIN', 'WBTC'), ('ENG', 'DENT'), ('ZRX', 'CDT'), ('NPXS', 'POLY'), ('RDN', 'VERI'), ('TAU', 'PAY'), ('CVC', 'REP'), ('USDC', 'PAY'), ('TAU', 'TUSD'), ('AST', 'DENT'), ('POWR', 'CZRX'), ('ABYSS', 'PAX'), ('POWR', 'POLY'), ('MANA', 'ETHOS'), ('SPANK', 'POLY'), ('MCO', 'POLY'), ('KIN', 'USDC'), ('RLC', 'ETHOS'), ('TAU', 'OMG'), ('DAI', 'KIN'), ('REN', 'POLY'), ('ANT', 'ETHOS'), ('BNT', 'ETHOS'), ('RDN', 'POLY'), ('TAU', 'PAX'), ('AST', 'ETHOS'), ('ABYSS', 'DAI'), ('NPXS', 'SPANK'), ('ABYSS', 'TAU'), ('USDT', 'ETHOS'), ('SNT', 'POWR'), ('SNT', 'MKR'), ('LEND', 'REP'), ('OMG', 'POLY'), ('KIN', 'LINK'), ('POE', 'ANT'), ('NPXS', 'MANA'), ('RPL', 'VERI'), ('TAU', 'DAI'), ('NPXS', 'XDCE'), ('TUSD', 'BLT'), ('CVC', 'MKR'), ('FUN', 'ETHOS'), ('MKR', 'POLY'), ('TUSD', 'NPXS'), ('FUN', 'POLY'), ('TAU', 'XDCE'), ('POE', 'ENG'), ('REN', 'BLT'), ('MANA', 'DENT'), ('STORJ', 'REP'), ('ANT', 'POLY'), ('REN', 'ETHOS'), ('NPXS', 'REN'), ('NPXS', 'CND'), ('MCO', 'ETHOS'), ('POE', 'OMG'), ('ZRX', 'POLY'), ('MTL', 'DENT'), ('USDC', 'POLY'), ('ABYSS', 'ETH'), ('ENG', 'ETHOS'), ('WBTC', 'XDCE'), ('POWR', 'MKR'), ('NEXO', 'NPXS'), ('LINK', 'POLY'), ('TAU', 'RCN'), ('CND', 'REQ'), ('NPXS', 'ETHOS'), ('SPANK', 'WBTC'), ('CND', 'ETHOS'), ('MANA', 'MKR'), ('ENG', 'CND'), ('NEXO', 'ETHOS'), ('NPXS', 'AST'), ('NPXS', 'PLR'), ('ZRX', 'DENT'), ('TAU', 'ZRX'), ('MTL', 'POLY'), ('AST', 'MCO'), ('PAX', 'BLT'), ('MANA', 'POLY'), ('POE', 'REP'), ('ENJ', 'POLY'), ('NPXS', 'DAI'), ('FUN', 'REP'), ('MKR', 'DENT'), ('TAU', 'REN'), ('SNT', 'POLY'), ('KIN', 'TKN'), ('USDC', 'ETHOS'), ('STORJ', 'ETHOS'), ('WBTC', 'ABYSS'), ('ZRX', 'ETHOS'), ('CVC', 'DENT'), ('POE', 'PAX'), ('GNO', 'ETHOS'), ('DENT', 'ETHOS'), ('TAU', 'SPANK'), ('POE', 'STORJ'), ('CVC', 'ETHOS'), ('REQ', 'ETHOS'), ('POE', 'GNO'), ('POWR', 'BLT'), ('REQ', 'BLT'), ('NPXS', 'RDN'), ('NPXS', 'POE'), ('ABYSS', 'USDT'), ('POWR', 'ETHOS'), ('RDN', 'DENT'), ('AST', 'GNO'), ('POE', 'POLY'), ('LINK', 'BAT'), ('WBTC', 'KIN'), ('MCO', 'DENT'), ('PLR', 'ETHOS'), ('SAI', 'BLT'), ('TAU', 'LINK'), ('PAY', 'POE'), ('LEND', 'MKR'), ('AST', 'POLY'), ('MANA', 'ABYSS'), ('KIN', 'REN'), ('POLY', 'DAI'), ('SPANK', 'MKR'), ('LEND', 'ETHOS'), ('CZRX', 'PAX'), ('CZRX', 'DAI'), ('RDN', 'MKR'), ('GNO', 'DENT'), ('SPANK', 'MCO'), ('SPANK', 'VERI'), ('REP', 'BLT'), ('KIN', 'PAX'), ('REQ', 'POLY'), ('TAU', 'MCO'), ('KNC', 'BLT'), ('TAU', 'VERI'), ('CVC', 'POLY'), ('TAU', 'USDC'), ('KNC', 'ETHOS'), ('MTL', 'ETHOS'), ('NPXS', 'RPL'), ('CDT', 'MKR'), ('SNT', 'DENT'), ('REQ', 'MKR'), ('DAI', 'ETH'), ('STORJ', 'DENT'), ('ENJ', 'DENT'), ('SAI', 'POLY'), ('SNT', 'NPXS'), ('ANT', 'BLT'), ('RLC', 'DENT'), ('POE', 'USDC'), ('CDT', 'MCO'), ('TAU', 'NEXO'), ('POE', 'USDT'), ('TAU', 'WBTC'), ('NPXS', 'REQ'), ('NPXS', 'CDT'), ('BNT', 'DENT'), ('POE', 'LINK'), ('NPXS', 'GNO'), ('SNT', 'ETHOS'), ('AST', 'WBTC'), ('PAY', 'ETHOS'), ('TAU', 'ABYSS'), ('TKN', 'BLT'), ('SNT', 'BLT'), ('TAU', 'ENG'), ('TKN', 'ETHOS'), ('PAY', 'AST'), ('BAT', 'ETHOS'), ('KIN', 'DAI'), ('LINK', 'DENT'), ('TAU', 'ENJ'), ('LEND', 'DENT'), ('REP', 'RPL'), ('BAT', 'BLT'), ('RCN', 'BLT'), ('NPXS', 'MTL'), ('RCN', 'ETHOS'), ('TAU', 'NPXS'), ('NEXO', 'POLY'), ('USDT', 'ENJ'), ('RCN', 'POLY'), ('CDT', 'REP'), ('CND', 'POLY'), ('POE', 'KNC'), ('PAX', 'POLY'), ('USDC', 'DENT'), ('TUSD', 'ETHOS'), ('POLY', 'ETHOS'), ('RLC', 'BLT'), ('NPXS', 'TKN'), ('BNT', 'BLT'), ('ANT', 'DENT'), ('ENJ', 'BLT'), ('FUN', 'DENT'), ('ENJ', 'ETHOS'), ('CND', 'MCO'), ('NPXS', 'CVC'), ('SAI', 'RLC'), ('TAU', 'REP'), ('NPXS', 'BNT'), ('USDT', 'NPXS'), ('USDC', 'BLT'), ('WBTC', 'ETHOS'), ('NPXS', 'POWR'), ('DENT', 'POLY'), ('WBTC', 'REN'), ('RDN', 'BLT'), ('TAU', 'PLR'), ('OMG', 'DENT'), ('BAT', 'POLY'), ('LINK', 'ETHOS'), ('POE', 'MCO')}

def main():
    do_summary()
    exit(0)

    working_dir = os.path.dirname(__file__)
    if working_dir: os.chdir(working_dir)

    usd_prices = get_token_prices()
    # usd_prices = get_token_prices(tokens=set(sum(map(list, BAD_PAIRS), [])))

    filename = get_filename_base(prefix='totle_vs_agg_supported_tokens')
    with SavingsCSV(filename, fieldnames=CSV_FIELDS) as csv_writer:
        todo = []
        combos = list(combinations(usd_prices, 2))
        random.shuffle(combos)
        for base, quote in combos:
        # for base, quote in BAD_PAIRS:
            todo.append((check_pair, base, quote, usd_prices[quote], csv_writer))

        print(f"{todo[0:5]}")

        MAX_THREADS = 8
        print(f"Queueing up {len(todo)} pairs for execution on {MAX_THREADS} workers")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures_p = {executor.submit(*p): p for p in todo}

            for f in concurrent.futures.as_completed(futures_p):
                _, base, quote, *_ = futures_p[f]
                print(f"Completed: {base}/{quote}: result={f.result()}")



if __name__ == "__main__":
    main()
