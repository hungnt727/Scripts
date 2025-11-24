
import ccxt
import pandas as pd

exchange = ccxt.bybit()
try:
    # Try fetching all funding rates
    funding_rates = exchange.fetch_funding_rates(['BTC/USDT:USDT', 'ETH/USDT:USDT'], params={'category': 'linear'})
    print("Fetched specific rates:", list(funding_rates.keys()))
    
    # Try fetching all?
    # funding_rates_all = exchange.fetch_funding_rates() # careful with this
    # print("Fetched all len:", len(funding_rates_all))
    
    sample = funding_rates['BTC/USDT']
    print("Sample BTC funding:", sample)
    
except Exception as e:
    print("Error fetching funding rates:", e)
