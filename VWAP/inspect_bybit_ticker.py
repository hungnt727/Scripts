
import ccxt
import json

exchange = ccxt.bybit()
markets = exchange.load_markets()
symbol = 'BTC/USDT'
ticker = exchange.fetch_ticker(symbol)

print("Ticker keys:", ticker.keys())
print("Funding Rate in ticker:", ticker.get('fundingRate'))
print("Info keys:", ticker['info'].keys())
if 'fundingRate' in ticker['info']:
    print("Funding Rate in info:", ticker['info']['fundingRate'])
