import functools
import requests
import json
import token_utils

API_BASE = 'https://api.dex.ag'
TOKENS_ENDPOINT = API_BASE + '/tokens'
TOKENS_NAMES_ENDPOINT = API_BASE + '/token-list-full'
PRICE_ENDPOINT = API_BASE + '/price'
TRADE_ENDPOINT = API_BASE + '/trade'
# https://api.dex.ag/token-list-full

TAKER_FEE_PCT = 0.0 # unfairly optimistic, but currently too difficult to calculate
# "We charge 0 fees and any DEX-related fees are factored into the total cost of your trade"
# https://concourseopen.com/blog/dex-ag-x-blaster/
# https://ethgasstation.info/blog/dex-ag-sets-new-record-volume-294733/

class DexAGAPIException(Exception):
    pass

def name():
    return 'DEX.AG'

def fee_pct():
    return TAKER_FEE_PCT


##############################################################################################
#
# API calls
#

# get exchanges
DEX_NAME_MAP = {'ag': 'ag', 'all':'all', '0xMesh': 'radar-relay', 'Bancor': 'bancor', 'DDEX': 'ddex', 'Ethfinex': 'ethfinex', 'IDEX': 'idex',
                'Kyber': 'kyber', 'Oasis': 'oasis', 'Paradex': 'paradex', 'Radar Relay': 'radar-relay', 'Uniswap': 'uniswap' }

def exchanges():
    # there is no exchanges endpoint yet so we are just using the ones from an ETH/DAI price query where dex == all
    dex_names = ['ag', 'bancor', 'ddex', 'ethfinex', 'idex', 'kyber', 'oasis', 'paradex', 'radar-relay', 'uniswap']

    # DEX.AG does not have exchange ids, but to keep the same interface we put in 0's for id
    id = 0
    return { e: id for e in dex_names }



@functools.lru_cache()
def get_pairs(quote='ETH'):
    # DEX.AG doesn't have a pairs endpoint, so we just use its tokens endpoint to get tokens, which are assumed to pair with quote
    tokens_json = requests.get(TOKENS_ENDPOINT).json()

    # use only the tokens that are listed in token_utils.tokens() and use the canonical name
    canonical_symbols = [token_utils.canonical_symbol(t) for t in tokens_json]  # may contain None values
    return [(t, quote) for t in canonical_symbols if t]

CACHED_SUPPORTED_TOKENS = [{'name': 'ETH ', 'symbol': 'ETH', 'address': '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'}, {'name': 'SAI old DAI (SAI)', 'symbol': 'SAI', 'address': '0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359'}, {'name': 'DAI (DAI)', 'symbol': 'DAI', 'address': '0x6b175474e89094c44da98b954eedeac495271d0f'}, {'name': 'Maker (MKR)', 'symbol': 'MKR', 'address': '0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2'}, {'name': 'USD Coin (USDC)', 'symbol': 'USDC', 'address': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'}, {'name': 'Basic Attention Token (BAT)', 'symbol': 'BAT', 'address': '0x0d8775f648430679a709e98d2b0cb6250d2887ef'}, {'name': 'Wrapped Bitcoin (WBTC)', 'symbol': 'WBTC', 'address': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599'}, {'name': 'Chainlink (LINK)', 'symbol': 'LINK', 'address': '0x514910771AF9Ca656af840dff83E8264EcF986CA'}, {'name': 'Augur (REP)', 'symbol': 'REP', 'address': '0x1985365e9f78359a9B6AD760e32412f4a445E862'}, {'name': '0x (ZRX)', 'symbol': 'ZRX', 'address': '0xE41d2489571d322189246DaFA5ebDe1F4699F498'}, {'name': 'Kyber Network (KNC)', 'symbol': 'KNC', 'address': '0xdd974D5C2e2928deA5F71b9825b8b646686BD200'}, {'name': 'sUSD (SUSD)', 'symbol': 'SUSD', 'address': '0x57Ab1ec28D129707052df4dF418D58a2D46d5f51'}, {'name': 'Synthetix Network Token (SNX)', 'symbol': 'SNX', 'address': '0xC011a73ee8576Fb46F5E1c5751cA3B9Fe0af2a6F'}, {'name': 'Zilliqa (ZIL)', 'symbol': 'ZIL', 'address': '0x05f4a42e251f2d52b8ed15E9FEdAacFcEF1FAD27'}, {'name': 'cSAI (cSAI)', 'symbol': 'CSAI', 'address': '0xf5dce57282a584d2746faf1593d3121fcac444dc'}, {'name': 'Status (SNT)', 'symbol': 'SNT', 'address': '0x744d70FDBE2Ba4CF95131626614a1763DF805B9E'}, {'name': 'Loom Network (LOOM)', 'symbol': 'LOOM', 'address': '0xA4e8C3Ec456107eA67d3075bF9e3DF3A75823DB0'}, {'name': 'OmiseGO (OMG)', 'symbol': 'OMG', 'address': '0xd26114cd6ee289accf82350c8d8487fedb8a0c07'}, {'name': 'Grid+ (GRID)', 'symbol': 'GRID', 'address': '0x12B19D3e2ccc14Da04FAe33e63652ce469b3F2FD'}, {'name': 'Enjin (ENJ)', 'symbol': 'ENJ', 'address': '0xF629cBd94d3791C9250152BD8dfBDF380E2a3B9c'}, {'name': 'Golem (GNT)', 'symbol': 'GNT', 'address': '0xa74476443119A942dE498590Fe1f2454d7D4aC0d'}, {'name': 'Gnosis (GNO)', 'symbol': 'GNO', 'address': '0x6810e776880C02933D47DB1b9fc05908e5386b96'}, {'name': 'Bancor (BNT)', 'symbol': 'BNT', 'address': '0x1F573D6Fb3F13d689FF844B4cE37794d79a7FF1C'}, {'name': 'USDT (USDT)', 'symbol': 'USDT', 'address': '0xdac17f958d2ee523a2206206994597c13d831ec7'}, {'name': 'TrueUSD (TUSD)', 'symbol': 'TUSD', 'address': '0x0000000000085d4780B73119b644AE5ecd22b376'}, {'name': 'Decentraland (MANA)', 'symbol': 'MANA', 'address': '0x0F5D2fB29fb7d3CFeE444a200298f468908cC942'}, {'name': 'district0x (DNT)', 'symbol': 'DNT'}, {'name': 'Aragon (ANT)', 'symbol': 'ANT', 'address': '0x960b236A07cf122663c4303350609A66A7B288C0'}, {'name': 'Fulcrum iSAI (iSAI)', 'symbol': 'ISAI', 'address': '0x14094949152eddbfcd073717200da82fed8dc960'}, {'name': 'Melon (MLN)', 'symbol': 'MLN', 'address': '0xec67005c4e498ec7f55e092bd1d35cbc47c91892'}, {'name': 'SpankChain (SPANK)', 'symbol': 'SPANK', 'address': '0x42d6622deCe394b54999Fbd73D108123806f6a18'}, {'name': 'QASH (QASH)', 'symbol': 'QASH'}, {'name': 'Loopring (LRC)', 'symbol': 'LRC', 'address': '0xBBbbCA6A901c926F240b89EacB641d8Aec7AEafD'}, {'name': 'Huobi Token (HT)', 'symbol': 'HT'}, {'name': 'Waltonchain (WTC)', 'symbol': 'WTC'}, {'name': 'Bee Token (BEE)', 'symbol': 'BEE', 'address': '0x4D8fc1453a0F359e99c9675954e656D80d996FbF'}, {'name': 'Crypto.com (MCO)', 'symbol': 'MCO', 'address': '0xB63B606Ac810a52cCa15e44bB630fd42D8d1d83d'}, {'name': 'Nexo (NEXO)', 'symbol': 'NEXO', 'address': '0xB62132e35a6c13ee1EE0f84dC5d40bad8d815206'}, {'name': 'Raiden Network Token (RDN)', 'symbol': 'RDN', 'address': '0x255Aa6DF07540Cb5d3d297f0D0D4D84cb52bc8e6'}, {'name': 'TokenCard (TKN)', 'symbol': 'TKN', 'address': '0xaAAf91D9b90dF800Df4F55c205fd6989c977E73a'}, {'name': 'AMPL (AMPL)', 'symbol': 'AMPL', 'address': '0xD46bA6D942050d489DBd938a2C909A5d5039A161'}, {'name': 'FOAM (FOAM)', 'symbol': 'FOAM', 'address': '0x4946Fcea7C692606e8908002e55A582af44AC121'}, {'name': 'Ren (REN)', 'symbol': 'REN', 'address': '0x408e41876cCCDC0F92210600ef50372656052a38'}, {'name': 'WAX (WAX)', 'symbol': 'WAX', 'address': '0x39Bb259F66E1C59d5ABEF88375979b4D20D98022'}, {'name': 'Storj (STORJ)', 'symbol': 'STORJ', 'address': '0xB64ef51C888972c908CFacf59B47C1AfBC0Ab8aC'}, {'name': 'Polymath (POLY)', 'symbol': 'POLY', 'address': '0x9992ec3cf6a55b00978cddf2b27bc6882d88d1ec'}, {'name': 'Bloom (BLT)', 'symbol': 'BLT'}, {'name': 'iExec RLC (RLC)', 'symbol': 'RLC', 'address': '0x607F4C5BB672230e8672085532f7e901544a7375'}, {'name': 'QuarkChain (QKC)', 'symbol': 'QKC', 'address': '0xea26c4ac16d4a5a106820bc8aee85fd0b7b2b664'}, {'name': 'Santiment Network Token (SAN)', 'symbol': 'SAN', 'address': '0x7C5A0CE9267ED19B22F8cae653F198e3E8daf098'}, {'name': 'Enigma (ENG)', 'symbol': 'ENG', 'address': '0xf0Ee6b27b759C9893Ce4f094b49ad28fd15A23e4'}, {'name': 'SingularityNET (AGI)', 'symbol': 'AGI', 'address': '0x8eB24319393716668D768dCEC29356ae9CfFe285'}, {'name': 'FunFair (FUN)', 'symbol': 'FUN', 'address': '0x419D0d8BdD9aF5e606Ae2232ed285Aff190E711b'}, {'name': 'Ripio (RCN)', 'symbol': 'RCN', 'address': '0xF970b8E36e23F7fC3FD752EeA86f8Be8D83375A6'}, {'name': 'Civic (CVC)', 'symbol': 'CVC', 'address': '0x41e5560054824eA6B0732E656E3Ad64E20e94E45'}, {'name': 'Power Ledger (POWR)', 'symbol': 'POWR', 'address': '0x595832F8FC6BF59c85C527fEC3740A1b7a361269'}, {'name': 'Eidoo (EDO)', 'symbol': 'EDO', 'address': '0xced4e93198734ddaff8492d525bd258d49eb388e'}, {'name': 'IoTeX (IOTX)', 'symbol': 'IOTX', 'address': '0x6fB3e0A217407EFFf7Ca062D46c26E5d60a14d69'}, {'name': 'Live Peer (LPT)', 'symbol': 'LPT', 'address': '0x58b6A8A3302369DAEc383334672404Ee733aB239'}, {'name': 'Aelf (ELF)', 'symbol': 'ELF', 'address': '0xbf2179859fc6D5BEE9Bf9158632Dc51678a4100e'}, {'name': 'Pax (PAX)', 'symbol': 'PAX', 'address': '0x8E870D67F660D95d5be530380D0eC0bd388289E1'}, {'name': 'Numeraire (NMR)', 'symbol': 'NMR', 'address': '0x1776e1F26f98b1A5dF9cD347953a26dd3Cb46671'}, {'name': 'Pundi X  (NPXS)', 'symbol': 'NPXS', 'address': '0xA15C7Ebe1f07CaF6bFF097D8a589fb8AC49Ae5B3'}, {'name': 'Synthetix sETH (SETH)', 'symbol': 'SETH', 'address': '0x5e74C9036fb86BD7eCdcb084a0673EFc32eA31cb'}, {'name': 'CryptoFranc (XCHF)', 'symbol': 'XCHF', 'address': '0xB4272071eCAdd69d933AdcD19cA99fe80664fc08'}, {'name': 'Rocket Pool (RPL)', 'symbol': 'RPL', 'address': '0xB4EFd85c19999D84251304bDA99E90B92300Bd93'}, {'name': 'DigixDAO (DGD)', 'symbol': 'DGD', 'address': '0xE0B7927c4aF23765Cb51314A0E0521A9645F0E2A'}, {'name': 'Darwinia Network Token (RING)', 'symbol': 'RING', 'address': '0x9469D013805bFfB7D3DEBe5E7839237e535ec483'}, {'name': 'Coin Bank International (CBI)', 'symbol': 'CBI', 'address': '0x43E5F59247b235449E16eC84c46BA43991Ef6093'}, {'name': 'Streamr (DATA)', 'symbol': 'DATA', 'address': '0x0Cf0Ee63788A0849fE5297F3407f701E122cC023'}, {'name': 'ETH Lend (LEND)', 'symbol': 'LEND', 'address': '0x80fB784B7eD66730e8b1DBd9820aFD29931aab03'}, {'name': 'ArcBlock (ABT)', 'symbol': 'ABT', 'address': '0xB98d4C97425d9908E66E53A6fDf673ACcA0BE986'}, {'name': 'Bluezelle (BLZ)', 'symbol': 'BLZ', 'address': '0x5732046A883704404F284Ce41FfADd5b007FD668'}, {'name': 'Datum (DAT)', 'symbol': 'DAT', 'address': '0x81c9151de0c8bafcd325a57e3db5a5df1cebf79c'}, {'name': 'EchoLink (EKO)', 'symbol': 'EKO', 'address': '0xa6a840e50bcaa50da017b91a0d86b8b2d41156ee'}, {'name': 'Abyss Token (ABYSS)', 'symbol': 'ABYSS', 'address': '0x0E8d6b471e332F140e7d9dbB99E5E3822F728DA6'}, {'name': 'Blox (CDT)', 'symbol': 'CDT', 'address': '0x177d39ac676ed1c67a2b268ad7f1e58826e5b0af'}, {'name': 'Cindicator (CND)', 'symbol': 'CND', 'address': '0xd4c435F5B09F855C3317c8524Cb1F586E42795fa'}, {'name': 'BTU Protocol (BTU)', 'symbol': 'BTU', 'address': '0xb683D83a532e2Cb7DFa5275eED3698436371cc9f'}, {'name': 'Dragonchain (DRGN)', 'symbol': 'DRGN', 'address': '0x419c4dB4B9e25d6Db2AD9691ccb832C8D9fDA05E'}, {'name': 'SIRIN Labs Token (SRN)', 'symbol': 'SRN', 'address': '0x68d57c9a1c35f63e2c83ee8e49a64e9d70528d25'}, {'name': 'Bounty0x (BNTY)', 'symbol': 'BNTY', 'address': '0xd2d6158683aeE4Cc838067727209a0aAF4359de3'}, {'name': 'Liquidity.Network (LQD)', 'symbol': 'LQD', 'address': '0xD29F0b5b3F50b07Fe9a9511F7d86F4f4bAc3f8c4'}, {'name': 'Matic Token (MATIC)', 'symbol': 'MATIC', 'address': '0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0'}, {'name': 'Panvala Token (PAN)', 'symbol': 'PAN', 'address': '0xD56daC73A4d6766464b38ec6D91eB45Ce7457c44'}, {'name': 'Pinakion (PNK)', 'symbol': 'PNK', 'address': '0x93ED3FBe21207Ec2E8f2d3c3de6e058Cb73Bc04d'}, {'name': 'POA ERC20 (POA20)', 'symbol': 'POA20', 'address': '0x6758B7d441a9739b98552B373703d8d3d14f9e62'}, {'name': 'RHOC (RHOC)', 'symbol': 'RHOC', 'address': '0x168296bb09e24A88805CB9c33356536B980D3fC5'}, {'name': 'Salt (SALT)', 'symbol': 'SALT', 'address': '0x4156D3342D5c385a87D264F90653733592000581'}, {'name': 'TrueAUD (TAUD)', 'symbol': 'TAUD', 'address': '0x00006100F7090010005F1bd7aE6122c3C2CF0090'}, {'name': 'TrueGBP (TGBP)', 'symbol': 'TGBP', 'address': '0x00000000441378008EA67F4284A57932B1c000a5'}, {'name': 'TrueHKD (THKD)', 'symbol': 'THKD', 'address': '0x0000852600CEB001E08e00bC008be620d60031F2'}, {'name': 'Unblocked Ledger (ULT)', 'symbol': 'ULT', 'address': '0x09617F6fD6cF8A71278ec86e23bBab29C04353a7'}, {'name': 'DAOstack (GEN)', 'symbol': 'GEN', 'address': '0x543Ff227F64Aa17eA132Bf9886cAb5DB55DCAddf'}, {'name': 'Dev (DEV)', 'symbol': 'DEV', 'address': '0x98626E2C9231f03504273d55f397409deFD4a093'}, {'name': 'Decentralized Insurance (DIP)', 'symbol': 'DIP', 'address': '0xc719d010B63E5bbF2C0551872CD5316ED26AcD83'}, {'name': 'Union Network (UNDT)', 'symbol': 'UNDT', 'address': '0x7C6C3b4e91923F080d6CC847A68d7330400a95d7'}, {'name': 'Amon (AMN)', 'symbol': 'AMN', 'address': '0x737F98AC8cA59f2C68aD658E3C3d8C8963E40a4c'}, {'name': 'Trustcoin (TRST)', 'symbol': 'TRST', 'address': '0xCb94be6f13A1182E4A4B6140cb7bf2025d28e41B'}, {'name': 'Crypto20 (C20)', 'symbol': 'C20', 'address': '0x26E75307Fc0C021472fEb8F727839531F112f317'}, {'name': 'FintruX Network (FTX)', 'symbol': 'FTX', 'address': '0xd559f20296FF4895da39b5bd9ADd54b442596a61'}, {'name': 'Rupiah Token (IDRT)', 'symbol': 'IDRT', 'address': '0x998FFE1E43fAcffb941dc337dD0468d52bA5b48A'}, {'name': 'Vials of Goo (GOO)', 'symbol': 'GOO', 'address': '0xDF0960778C6E6597f197Ed9a25F12F5d971da86c'}, {'name': 'FundRequest (FND)', 'symbol': 'FND'}, {'name': 'Magnolia Token (MGN)', 'symbol': 'MGN', 'address': '0x80f222a749a2e18Eb7f676D371F19ad7EFEEe3b7'}, {'name': 'SHUF Token (SHUF)', 'symbol': 'SHUF', 'address': '0x3A9FfF453d50D4Ac52A6890647b823379ba36B9E'}, {'name': 'Wrapped Cryptokitties (WCK)', 'symbol': 'WCK', 'address': '0x09fE5f0236F0Ea5D930197DCE254d77B04128075'}]

@functools.lru_cache(1)
def supported_tokens():
    r = requests.get(TOKENS_NAMES_ENDPOINT)
    try: # this often fails to return a good response, so we used cached data when it does
        supp_tokens_json = r.json()
    except json.decoder.JSONDecodeError as e:
        print(f"dexag_client.supported_tokens() using CACHED_SUPPORTED_TOKENS")
        supp_tokens_json = CACHED_SUPPORTED_TOKENS

    return [t['symbol'] for t in (supp_tokens_json)]

# get quote
AG_DEX = 'ag'
def get_quote(from_token, to_token, from_amount=None, to_amount=None, dex='all', verbose=False, debug=False):
    """Returns the price in terms of the from_token - i.e. how many from_tokens to purchase 1 to_token"""

    # don't bother to make the call if either of the tokens are not supported
    for t in [from_token, to_token]:
        if t != 'ETH' and t not in supported_tokens():
            print(f"{t} is not supported by {name()}")
            return {}

    # buy: https://api.dex.ag/price?from=ETH&to=DAI&fromAmount=1.5&dex=all
    # sell: https://api.dex.ag/price?from=DAI&to=ETH&toAmount=1.5&dex=all
    query = {'from': from_token, 'to': to_token, 'dex': dex}
    if from_amount:
        query['fromAmount'] = from_amount
    elif to_amount:
        query['toAmount'] = to_amount
    else:
        raise ValueError(f"{name()} only accepts either from_amount or to_amount, not both")

    if debug: print(f"REQUEST to {PRICE_ENDPOINT}:\n{json.dumps(query, indent=3)}\n\n")
    r = None
    try:
        r = requests.get(PRICE_ENDPOINT, params=query)
        j = r.json()
        if debug: print(f"RESPONSE from {PRICE_ENDPOINT}:\n{json.dumps(j, indent=3)}\n\n")

        if 'error' in j: raise ValueError(j['error'])

        # Response:
        # {"dex": "ag", "price": "159.849003708050647455", "pair": {"base": "ETH", "quote": "DAI"}, "liquidity": {"uniswap": 38, "bancor": 62}}

        # if dex=='all' j will be an array of dicts like this
        # [ {"dex": "bancor", "price": "159.806431928046276401", "pair": {"base": "ETH", "quote": "DAI"}},
        #   {"dex": "uniswap", "price": "159.737708484933187899", "pair": {"base": "ETH", "quote": "DAI"}}, ... ]
        ag_data, exchanges_prices = {}, {}
        if isinstance(j, list):
            for dex_data in j:
                dex, dexag_price = dex_data['dex'], float(dex_data['price'])
                check_pair(dex_data, query, dex=dex)
                exchanges_prices[dex] = 1 / dexag_price if from_amount else dexag_price
                if dex == AG_DEX: ag_data = dex_data
        else:
            ag_data = j
            check_pair(ag_data, query, dex=AG_DEX)

        if not ag_data: return {}

        # BUG? DEX.AG price is not a simple function of base and quote. It changes base on whether you specify toAmount
        # or fromAmount even though base and quote stay the same! So it has nothing to do with base and quote.
        # Here are four examples:
        # https://api.dex.ag/price?from=ETH&to=DAI&toAmount=1.5&dex=ag -> price: 0.0055    <- buy (OK)
        # https://api.dex.ag/price?from=ETH&to=DAI&fromAmount=1.5&dex=ag -> price: 180     <- buy (inverted)
        # https://api.dex.ag/price?from=DAI&to=ETH&toAmount=1.5&dex=ag -> price: 180       <- sell (OK)
        # https://api.dex.ag/price?from=DAI&to=ETH&fromAmount=1.5&dex=ag -> price: 0.0055  <- sell (inverted)

        dexag_price = float(ag_data['price'])
        if debug: print(f"dexag_price={dexag_price}")

        # We always want to return price in terms of how many from_tokens for 1 to_token, which means we need to
        # invert DEX.AG's price whenever from_amount is specified.
        if from_amount: # When from_amount is specified, dexag_price is the amount of to_tokens per 1 from_token.
            source_amount, destination_amount = (from_amount, from_amount * dexag_price)
            price = 1 / dexag_price
        else: # When to_amount is specified, price is the amount of from_tokens per 1 to_token.
            source_amount, destination_amount = (to_amount * dexag_price, to_amount)
            price = dexag_price

        # "liquidity": {"uniswap": 38, "bancor": 62}, ...
        exchanges_parts = ag_data['liquidity'] if ag_data.get('liquidity') else {}

        return {
            'source_token': from_token,
            'source_amount': source_amount,
            'destination_token': to_token,
            'destination_amount': destination_amount,
            'price': price,
            'exchanges_parts': exchanges_parts,
            'exchanges_prices': exchanges_prices
        }

    except (ValueError, requests.exceptions.RequestException) as e:
        print(f"{name()} {query} raised {e}: {r.text[:128] if r else 'no JSON returned'}")
        return {}


def check_pair(ag_data, query, dex=AG_DEX):
    """sanity check that asserts base == from and quote == to, but the base and quote actually don't matter in how the price is quoted"""
    if 'pair' not in ag_data:
        print(f"NO PAIR!\n\n{json.dumps(ag_data, indent=3)}")
    pair = ag_data['pair']
    if (pair['base'], pair['quote']) != (query['from'], query['to']):
        raise ValueError(f"unexpected base,quote: dex={dex} pair={pair} but query={query}")

