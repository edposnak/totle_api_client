import dexwatch_client

########################################################################################################################
# test

MORE_AGG_TOKENS = ['ABT','APPC','BLZ','BTU','CBI','DAT','DGX','DTA','ELF','EQUAD','GEN','IDAI','LBA','MOC','MYB','OST','QKC','SPN','UPP','WETH','XCHF']
UNSUPPORTED_TOKENS = ['IDAI','IKNC','ILINK','IREP','IUSDC','IWBTC','IZRX','SETH']

vol_interval='30d'
pf = lambda v: f"{v:<16}"
pd = lambda f: f"{float(f):<16.4f}"
print(pf('Token'), pf('DEX'), pf('Num Trades'), pf(f"{vol_interval} Vol"), pf("Prev Vol"))
for token in MORE_AGG_TOKENS + UNSUPPORTED_TOKENS:
    vol_info = dexwatch_client.eth_pair_json(token, interval=vol_interval)
    for v in vol_info:
        dex, num_trades = v['dex_name'], v['trades']
        vol, prev_vol = v['volume'], v['volume_previous']
        print(f"{pf(token)} {pf(dex)} {pf(num_trades)} {pd(vol)} {pd(prev_vol)}")
