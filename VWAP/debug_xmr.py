import ccxt
import pandas as pd
from datetime import datetime

exchange = ccxt.binance()
symbol = 'XMR/USDT'
timeframe = '15m'

try:
    print(f"Fetching data for {symbol}...")
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=5)
    if not ohlcv:
        print("No data returned.")
    else:
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        last_candle = df.iloc[-1]
        print(f"Last candle timestamp: {last_candle['timestamp']}")
        print(f"Current system time: {pd.Timestamp.now()}")
        
        diff = pd.Timestamp.now() - last_candle['timestamp']
        print(f"Difference: {diff}")
        
except Exception as e:
    print(f"Error: {e}")
