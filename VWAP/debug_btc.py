import ccxt
import pandas as pd
import pandas_ta as ta

exchange = ccxt.binance()
symbol = 'APEUSDT'
timeframe = '1h'

try:
    print(f"Fetching data for {symbol} {timeframe}...")
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=1000) # Get enough data
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # VWAP (Month Anchor)
    df.set_index('timestamp', inplace=True, drop=False)
    df['vwap'] = ta.vwap(high=df['high'], low=df['low'], close=df['close'], volume=df['volume'], anchor='M')
    
    # VWAP Trend (MA 20)
    df['vwap_ma'] = df['vwap'].rolling(window=20).mean()
    
    # Reset index for Ichimoku to avoid frequency inference issues
    df.reset_index(drop=True, inplace=True)
    
    # Ichimoku
    ichimoku_data, span_data = ta.ichimoku(df['high'], df['low'], df['close'])
    print("Ichimoku Data Columns:", ichimoku_data.columns)
    
    # Concat
    df = pd.concat([df, ichimoku_data], axis=1)
    
    # Define columns
    span_a_col = ichimoku_data.columns[0]
    span_b_col = ichimoku_data.columns[1]

    # Analyze around target date
    target_date = pd.Timestamp('2025-11-11')
    start_date = target_date - pd.Timedelta(days=2)
    end_date = target_date + pd.Timedelta(days=2)
    
    subset = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
    
    print("\n--- Analysis Data ---")
    for index, row in subset.iterrows():
        ts = row['timestamp']
        open_price = row['open']
        close = row['close']
        vwap = row['vwap']
        vwap_ma = row['vwap_ma']
        span_a = row[span_a_col]
        span_b = row[span_b_col]
        
        print(f"Date: {ts}")
        print(f"  Open: {open_price:.2f}")
        print(f"  Close: {close:.2f}")
        print(f"  VWAP: {vwap:.2f}")
        print(f"  VWAP MA(20): {vwap_ma:.2f}")
        print(f"  Span A: {span_a:.2f}")
        print(f"  Span B: {span_b:.2f}")
        
        # Check Conditions
        # Bearish: Open > VWAP and Close < VWAP
        is_bearish_cross_candle = (open_price > vwap) and (close < vwap)
        is_downtrend = (vwap < vwap_ma)
        is_below_cloud = (vwap < span_a) and (vwap < span_b)
        
        print(f"  Condition: Open > VWAP & Close < VWAP? {is_bearish_cross_candle}")
        print(f"  Condition: VWAP < MA? {is_downtrend}")
        print(f"  Condition: VWAP < Cloud? {is_below_cloud}")
        print("-" * 30)
        
    # Check Crossover specifically for 11/11
    # We need prev candle (11/10) and current (11/11)
    try:
        curr = df[df['timestamp'] == '2025-11-11'].iloc[0]
        prev = df[df['timestamp'] == '2025-11-10'].iloc[0]
        
        print("\n--- Crossover Check ---")
        print(f"Prev (11/10): Close={prev['close']:.2f}, VWAP={prev['vwap']:.2f}")
        print(f"Curr (11/11): Open={curr['open']:.2f}, Close={curr['close']:.2f}, VWAP={curr['vwap']:.2f}")
        
        bearish_cross_prev_curr = (prev['close'] > prev['vwap']) and (curr['close'] < curr['vwap'])
        bearish_cross_candle = (curr['open'] > curr['vwap']) and (curr['close'] < curr['vwap'])
        
        print(f"Bearish Crossover (Prev Close > VWAP and Curr Close < VWAP)? {bearish_cross_prev_curr}")
        print(f"Bearish Candle (Curr Open > VWAP and Curr Close < VWAP)? {bearish_cross_candle}")
    except IndexError:
        print("Could not find 11/10 or 11/11 data")

    exit()
    
    # Filter for dates around 2025-11-11
    target_date = pd.Timestamp('2025-11-11')
    start_date = target_date - pd.Timedelta(days=5)
    end_date = target_date + pd.Timedelta(days=5)
    
    subset = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
    
    print("\n--- Analysis Data ---")
    for index, row in subset.iterrows():
        ts = row['timestamp']
        close = row['close']
        vwap = row['vwap']
        vwap_ma = row['vwap_ma']
        span_a = row[span_a_col]
        span_b = row[span_b_col]
        
        print(f"Date: {ts}")
        print(f"  Close: {close:.2f}")
        print(f"  VWAP: {vwap:.2f}")
        print(f"  VWAP MA(20): {vwap_ma:.2f}")
        print(f"  Span A: {span_a:.2f}")
        print(f"  Span B: {span_b:.2f}")
        
        # Check Conditions
        is_bearish_crossover = (close < vwap) # Simplified check for current state
        is_downtrend = (vwap < vwap_ma)
        is_below_cloud = (vwap < span_a) and (vwap < span_b)
        
        print(f"  Condition: Close < VWAP? {is_bearish_crossover}")
        print(f"  Condition: VWAP < MA? {is_downtrend}")
        print(f"  Condition: VWAP < Cloud? {is_below_cloud}")
        print("-" * 30)

except Exception as e:
    print(f"Error: {e}")
