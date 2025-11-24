
import ccxt
import time

exchange = ccxt.bybit()

symbol = 'BTC/USDT:USDT' 
# Bybit often needs the unified symbol for linear

try:
    print(f"Fetching funding history for {symbol}...")
    # bybit usually supports fetchFundingRateHistory
    history = exchange.fetch_funding_rate_history(symbol, limit=3)
    
    print(f"Found {len(history)} records.")
    for rate in history:
        print(f"Time: {rate['datetime']}, Rate: {rate['fundingRate']}")
        
except Exception as e:
    print(f"Error: {e}")
    # Try alternate if standard fails
    try:
        print("Retrying with implicit symbol...")
        history = exchange.fetch_funding_rate_history('BTC/USDT', limit=3)
        print(f"Found {len(history)} records (retry).")
        for rate in history:
            print(f"Time: {rate['datetime']}, Rate: {rate['fundingRate']}")
    except Exception as e2:
        print(f"Retry Error: {e2}")
