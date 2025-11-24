import os
import time
import requests
import pandas as pd
import ccxt

# --- CONFIGURATION ---

# --- CONFIGURATION ---
COINMARKETCAP_API_KEY = 'a2d1ccdd-c9b4-4e30-b3ac-c0ed36849565'
USE_FIXED_LIST = False # True: Use fixed list below, False: Use Top N from CoinMarketCap
FIXED_SYMBOLS = [
    'MON/USDT','BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
    'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'TRX/USDT', 'DOT/USDT' 
]
TOP_N_COINS = 300
TIMEFRAME = '5m'
DURATION_HOURS = 240
OUTPUT_FILE = 'candle_width_ranking.txt'

# Initialize Exchange
exchange = ccxt.bybit()

def get_target_coins():
    """Fetches target coins (Fixed list or Top N from CoinMarketCap)."""
    if USE_FIXED_LIST:
        print(f"Using fixed list of {len(FIXED_SYMBOLS)} symbols.")
        return FIXED_SYMBOLS

    print(f"Fetching top {TOP_N_COINS} coins from CoinMarketCap...")
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    parameters = {
        'start': '1',
        'limit': str(TOP_N_COINS),
        'convert': 'USDT'
    }
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': COINMARKETCAP_API_KEY,
    }
    
    try:
        response = requests.get(url, params=parameters, headers=headers)
        data = response.json()
        if 'data' in data:
            # Filter for symbols available on Binance with USDT
            symbols = [f"{coin['symbol']}/USDT" for coin in data['data']]
            
            # Load Binance markets efficiently
            print("Loading Bybit markets...")
            markets = exchange.load_markets()
            available_symbols = [s for s in symbols if s in markets]
            
            print(f"Found {len(available_symbols)}/{TOP_N_COINS} pairs available on Bybit.")
            return available_symbols
    except Exception as e:
        print(f"Error fetching coin list: {e}")
    return []

def fetch_history(symbol, timeframe, limit):
    """Fetches historical ohlcv with pagination if limit > 1000."""
    all_ohlcv = []
    
    # Binance limit per request
    MAX_LIMIT = 1000
    
    # Calculate start time based on limit
    # This is approximate, better to use while loop backwards or 'since' if we want exact range
    # But for "last N hours", fetching latest is easiest.
    # Since Binance fetch_ohlcv returns LATEST candles when 'since' is None,
    # but only up to 1000. 
    # To get MORE than 1000 latest candles, we need to fetch backwards using 'endTime' (not supported by all ccxt unified) 
    # OR fetch using 'since' from calculated start time.
    
    # Strategy: Calculate start timestamp (now - duration) and fetch forward
    duration_ms = limit * exchange.parse_timeframe(timeframe) * 1000
    since = exchange.milliseconds() - duration_ms
    
    while len(all_ohlcv) < limit:
        remaining = limit - len(all_ohlcv)
        fetch_limit = min(remaining, MAX_LIMIT)
        
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=fetch_limit)
        except Exception as e:
            # print(f"Error fetching {symbol}: {e}")
            break
            
        if not ohlcv:
            break
            
        all_ohlcv.extend(ohlcv)
        
        # Update 'since' for next batch: timestamp of last candle + 1 timeframe
        last_timestamp = ohlcv[-1][0]
        since = last_timestamp + 1
        
        # Safety break if we got fewer than requested (end of data)
        if len(ohlcv) < fetch_limit:
            break
            
        time.sleep(0.1) # Rate limit
        
    return all_ohlcv

def get_candle_width_stats(symbol):
    """Fetches candles and calculates average width percentage."""
    try:
        # Calculate needed candles
        minutes_per_candle = int(TIMEFRAME[:-1])
        needed_candles = int((DURATION_HOURS * 60) / minutes_per_candle)
        # Add buffer
        fetch_limit = needed_candles + 20
        
        # Fetch OHLCV
        ohlcv = fetch_history(symbol, TIMEFRAME, fetch_limit)
        
        if not ohlcv:
            return None
            
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Ensure we look at exactly the required duration
        if len(df) > needed_candles:
            df = df.iloc[-needed_candles:]
            
        # Calculate Width %: ((High - Low) / Open) * 100
        df = df[df['open'] > 0]
        df['width_percent'] = ((df['high'] - df['low']) / df['open']) * 100
        
        avg_width = df['width_percent'].mean()
        return avg_width
        
    except Exception as e:
        # print(f"Error processing {symbol}: {e}")
        return None

def main():
    print(f"--- Starting Volatility Scan (Top {TOP_N_COINS}, {TIMEFRAME} candles, last {DURATION_HOURS}h) ---")
    
    symbols = get_target_coins()
    if not symbols:
        print("No symbols found. Exiting.")
        return

    results = []
    
    print("Processing candles...")
    for i, symbol in enumerate(symbols):
        avg_width = get_candle_width_stats(symbol)
        if avg_width is not None:
            results.append({'symbol': symbol, 'avg_width': avg_width})
            # Simple progress indicator
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{len(symbols)}...")
        
        # Respect rate limits slightly
        time.sleep(0.05)

    # Sort by Average Width Descending
    results.sort(key=lambda x: x['avg_width'], reverse=True)
    
    # Take Top 10
    top_10 = results[:10]
    
    # Output content
    output_lines = []
    header = f"Top 10 Average {TIMEFRAME} Candle Width (Last {DURATION_HOURS}h)"
    output_lines.append(header)
    output_lines.append("=" * len(header))
    output_lines.append(f"{'Rank':<5} {'Symbol':<15} {'Avg Width (%)':<15}")
    output_lines.append("-" * 35)
    
    print("\n" + "\n".join(output_lines))
    
    for rank, item in enumerate(top_10, 1):
        line = f"{rank:<5} {item['symbol']:<15} {item['avg_width']:.4f}%"
        output_lines.append(line)
        print(line)
        
    # Write to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(output_lines))
    
    print(f"\nResult saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
