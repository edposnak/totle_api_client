import exchange_utils

def is_multi_route(splits):
    """ returns True if there are multiple routes in a list, each a hash containing a multi or non-multi split
        e.g. [ {'0x':73, 'Uniswap':30}, {'BAT/ETH': {'Kyber':90, 'Uniswap':10}, 'OMG/BAT': {...}}, {...}, ...] """
    return type(splits) == list


def is_multi_split(splits):
    """ returns True if there are multiple splits keyed by pair e.g. {'BAT/ETH': {'Kyber':90, 'Uniswap':10}, 'OMG/BAT': {...}}"""
    return bool(splits) and type(list(splits.values())[0]) == dict

def canonicalize_and_sort_splits(raw_splits):
    """Canonicalizes any DEX named in the given raw_splits, which may be a string or a dict"""

    split_obj = eval(raw_splits or '{}') if isinstance(raw_splits, str) else raw_splits

    if is_multi_route(split_obj):
        return [ cs_route(route) for route in split_obj ]
    else:
        return cs_route(split_obj)


def cs_route(split_obj):
    if is_multi_split(split_obj):
        return {pair: canonized_sorted_rounded_splits(flat_split) for pair, flat_split in split_obj.items()}
    else:
        return canonized_sorted_rounded_splits(split_obj)

def canonized_sorted_rounded_splits(flat_splits):
    a_splits = exchange_utils.canonical_keys(flat_splits)
    return {k: round(v) for k, v in sorted(a_splits.items()) if round(v) > 0}


