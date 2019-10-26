import top_tokens


top_n, day_volume = 80, 90

print(f"\n\nTop {top_n} tokens by {day_volume}-day volume")
top_by_volume = top_tokens.top_tokens_by_volume(top_n, day_volume)
print(top_by_volume)


print(f"\n\nTop {top_n} tokens by market cap")
top_by_market_cap = top_tokens.top_tokens_by_market_cap(top_n)
print(top_by_market_cap)

overlap = set(top_by_market_cap) & set(top_by_volume)
print(f"\n\nOverlap of top tokens by market cap and volume ({len(overlap)} tokens)", overlap)

underlap = [ t for t in top_by_market_cap if not t in top_by_volume ]
print(f"\n\nTop tokens by market cap not in top volume ({len(underlap)} tokens)", underlap)


for t in top_by_volume:
    if t not in overlap: print(f"{t} is not in overlap")