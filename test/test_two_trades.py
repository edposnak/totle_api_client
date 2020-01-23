import json
import totle_client

TEST_DATA_DIR = 'test_data'

def run_test(name, trade_size=0.1, from_token='ETH', to_token='BAT', whitelist_exchange='Uniswap'):
    print("\n\n----------------------------------------------------\n")
    with open(f"{TEST_DATA_DIR}/{name}.json") as json_file:
        j = json.load(json_file)
        if j['success']:
            inputs = totle_client.swap_inputs(from_token, to_token, params={'tradeSize': trade_size})

            response = j['response']
            sd = totle_client.swap_data(response, True, request=inputs)
            print(f"\n{json.dumps(sd, indent=3)}")

            if whitelist_exchange:
                sd = totle_client.swap_data(response, False, request=inputs)
                print(f"\n{json.dumps(sd, indent=3)}")

        else:
            print(json.dumps(j, indent=3))
            e = totle_client.TotleAPIException(None, {}, j)
            totle_client.handle_swap_exception(e, totle_client.name(), from_token, to_token, {'tradeSize': trade_size})


# run_test('buy_ethos_fail', to_token='ETHOS', whitelist_exchange=None)
run_test('buy_data_for_0.1_eth', to_token='DATA')
# run_test('sell_cdai_for_0.1_eth', from_token='CDAI', to_token='ETH')

