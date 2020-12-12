import exchange_utils

def is_multi_split(splits):
    """ returns True if there are multiple splits keyed by pair e.g. {'BAT/ETH': {'Kyber':90, 'Uniswap':10}, 'ETH/DAT': {...}}"""
    return bool(splits) and type(list(splits.values())[0]) == dict


def canonicalize_and_sort_splits(raw_splits):
    """Canonicalizes any DEX named in the given raw_splits, which may be a string or a dict"""

    h = eval(raw_splits or '{}') if isinstance(raw_splits, str) else raw_splits

    if is_multi_split(h):
        return {pair: canonized_sorted_rounded_splits(flat_split) for pair, flat_split in h.items()}
    else:
        return canonized_sorted_rounded_splits(h)

def canonized_sorted_rounded_splits(flat_splits):
    a_splits = exchange_utils.canonical_keys(flat_splits)
    return {k: round(v) for k, v in sorted(a_splits.items()) if round(v) > 0}


