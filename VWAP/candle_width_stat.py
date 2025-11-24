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
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT','CC/USDT','STABLE/USDT','NIGHT/USDT','H/USDT',
    'DOGE/USDT', 'MON/USDT', 'ASTER/USDT', 'FARTCOIN/USDT', 'POPCAT/USDT', 'PEOPLE/USDT', 'JASMY/USDT', 'ZEC/USDT'
]
TOP_N_COINS = 200
TOP_RESULTS_COUNT = 20 # Number of top results to display/save
TIMEFRAME = '5m'
DURATION_HOURS = 24
OUTPUT_FILE = 'candle_width_ranking.txt'

# Initialize Exchange
exchange = ccxt.bybit()

def get_target_coins():
    """Fetches target coins with metadata (Rank, Market Cap).
    Returns a list of dicts: {'symbol': 'BTC/USDT', 'rank': 1, 'market_cap': 123456...}
    """
    targets = [] # List of {'symbol': '...', 'rank': int, 'market_cap': float}

    if USE_FIXED_LIST:
        print(f"Using fixed list of {len(FIXED_SYMBOLS)} symbols.")
        # We need to fetch metadata for these specific coins.
        # 1. Extract base symbols (e.g., BTC from BTC/USDT)
        base_symbols = [s.split('/')[0] for s in FIXED_SYMBOLS]
        symbol_map = {s.split('/')[0]: s for s in FIXED_SYMBOLS} # Map BTC -> BTC/USDT
        
        # 2. Query CMC Quotes
        print("Fetching metadata for fixed list from CoinMarketCap...")
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
        parameters = {
            'symbol': ','.join(base_symbols),
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
                for base_sym, full_sym in symbol_map.items():
                    # CMC keys result by symbol
                    coin_data = data['data'].get(base_sym)
                    
                    rank = 9999
                    mcap = 0.0
                    
                    if coin_data:
                        # API can return a list if multiple coins share symbol, or dict if unique.
                        # v1 quotes/latest usually returns a dict if unique or list ?? 
                        # Actually v1 keyed by symbol usually returns the object. 
                        # But wait, if multiple exist, it might be tricky. For now assume standard top coins.
                        # If coin_data is list (duplicate symbols), take first.
                        if isinstance(coin_data, list):
                            coin_data = coin_data[0]
                            
                        rank = coin_data.get('cmc_rank', 9999)
                        quote = coin_data.get('quote', {}).get('USDT', {})
                        mcap = quote.get('market_cap', 0.0)
                    
                    targets.append({
                        'symbol': full_sym,
                        'rank': rank,
                        'market_cap': mcap
                    })
            else:
                print(f"Warning: CMC response invalid: {data}")
                # Fallback
                for s in FIXED_SYMBOLS:
                    targets.append({'symbol': s, 'rank': 9999, 'market_cap': 0})
                    
        except Exception as e:
            print(f"Error fetching metadata for fixed list: {e}")
            # Fallback
            for s in FIXED_SYMBOLS:
                targets.append({'symbol': s, 'rank': 9999, 'market_cap': 0})
        
        return targets

    # --- TOP N MODE ---
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
            # Map symbol -> metadata
            cmc_map = {}
            for coin in data['data']:
                symbol_pair = f"{coin['symbol']}/USDT"
                cmc_map[symbol_pair] = {
                    'rank': coin['cmc_rank'],
                    'market_cap': coin['quote']['USDT']['market_cap']
                }
            
            # Filter for symbols available on Bybit
            # Create a provisional list of pair strings to check against exchange
            provisional_symbols = list(cmc_map.keys())
            
            print("Loading Bybit markets...")
            markets = exchange.load_markets()
            
            available_symbols = [s for s in provisional_symbols if s in markets]
            print(f"Found {len(available_symbols)}/{TOP_N_COINS} pairs available on Bybit.")
            
            # Build final target list
            for s in available_symbols:
                meta = cmc_map[s]
                targets.append({
                    'symbol': s,
                    'rank': meta['rank'],
                    'market_cap': meta['market_cap']
                })
                
            return targets
    except Exception as e:
        print(f"Error fetching coin list: {e}")
    return []

def fetch_history(symbol, timeframe, limit):
    """Fetches historical ohlcv with pagination if limit > 1000."""
    all_ohlcv = []
    MAX_LIMIT = 1000
    
    duration_ms = limit * exchange.parse_timeframe(timeframe) * 1000
    since = exchange.milliseconds() - duration_ms
    
    while len(all_ohlcv) < limit:
        remaining = limit - len(all_ohlcv)
        fetch_limit = min(remaining, MAX_LIMIT)
        
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=fetch_limit)
        except Exception as e:
            break
            
        if not ohlcv:
            break
            
        all_ohlcv.extend(ohlcv)
        last_timestamp = ohlcv[-1][0]
        since = last_timestamp + 1
        
        if len(ohlcv) < fetch_limit:
            break
            
        time.sleep(0.1) 
        
    return all_ohlcv

def get_candle_width_stats(symbol):
    """Fetches candles and calculates average width percentage. 
       Returns (avg_width, last_price) or None."""
    try:
        minutes_per_candle = int(TIMEFRAME[:-1])
        needed_candles = int((DURATION_HOURS * 60) / minutes_per_candle)
        fetch_limit = needed_candles + 20
        
        ohlcv = fetch_history(symbol, TIMEFRAME, fetch_limit)
        
        if not ohlcv:
            return None
            
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Ensure we look at exactly the required duration
        if len(df) > needed_candles:
            df = df.iloc[-needed_candles:]
            
        # Last price (current price)
        last_price = df.iloc[-1]['close'] if not df.empty else 0.0

        # Calculate Width %: ((High - Low) / Open) * 100
        df = df[df['open'] > 0]
        df['width_percent'] = ((df['high'] - df['low']) / df['open']) * 100
        
        avg_width = df['width_percent'].mean()
        return avg_width, last_price
        
    except Exception as e:
        return None

def format_market_cap(mcap):
    if mcap is None: return "N/A"
    if mcap >= 1_000_000_000:
        return f"${mcap/1_000_000_000:.2f}B"
    elif mcap >= 1_000_000:
        return f"${mcap/1_000_000:.2f}M"
    else:
        return f"${mcap:,.0f}"

def format_price(price):
    if price is None: return "N/A"
    if price < 0.01:
        return f"${price:.6f}"
    if price < 1:
        return f"${price:.4f}"
    else:
        return f"${price:.2f}"

def main():
    print(f"--- Starting Volatility Scan (Top {TOP_N_COINS}, {TIMEFRAME} candles, last {DURATION_HOURS}h) ---")
    
    targets = get_target_coins()
    if not targets:
        print("No symbols found. Exiting.")
        return

    results = []
    
    print("Processing candles...")
    for i, item in enumerate(targets):
        symbol = item['symbol']
        stats = get_candle_width_stats(symbol)
        
        if stats is not None:
            avg_width, last_price = stats
            results.append({
                'symbol': symbol,
                'avg_width': avg_width,
                'price': last_price,
                'rank': item['rank'],
                'market_cap': item['market_cap']
            })
            
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{len(targets)}...")
        
        time.sleep(0.05)

    # Sort by Average Width Descending
    results.sort(key=lambda x: x['avg_width'], reverse=True)
    
    # Take Top N
    top_n_results = results[:TOP_RESULTS_COUNT]
    
    # Output content
    output_lines = []
    header = f"Top {TOP_RESULTS_COUNT} Average {TIMEFRAME} Candle Width (Last {DURATION_HOURS}h)"
    div = "=" * 90
    output_lines.append(header)
    output_lines.append(div)
    # Header cols: Rank(CMC) | M.Cap | Symbol | Price | Avg Width
    output_lines.append(f"{'#CMC':<6} {'Market Cap':<10} {'Symbol':<15} {'Price':<12} {'Avg Width (%)':<15}")
    output_lines.append("-" * 70)
    
    print("\n" + "\n".join(output_lines))
    
    for res in top_n_results:
        mcap_str = format_market_cap(res['market_cap'])
        price_str = format_price(res['price'])
        cmc_rank = res['rank'] if res['rank'] != 9999 else "-"
        
        line = f"{cmc_rank:<6} {mcap_str:<10} {res['symbol']:<15} {price_str:<12} {res['avg_width']:.4f}%"
        output_lines.append(line)
        print(line)
        
    # Write to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(output_lines))
    
    print(f"\nResult saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
