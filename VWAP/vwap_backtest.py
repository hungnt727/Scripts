import os
import time
import requests
import pandas as pd
import numpy as np
import pandas_ta as ta
import ccxt
import sys
import io

# Set stdout to utf-8 to handle Vietnamese characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- CẤU HÌNH ---
# Thay thế bằng thông tin của bạn
COINMARKETCAP_API_KEY = 'a2d1ccdd-c9b4-4e30-b3ac-c0ed36849565'

# Cài đặt cho việc backtest
TIMEFRAMES = ['15m', '1h', '4h', '1d']
TOP_N_COINS = 300 # Giới hạn số lượng coin để backtest
VWAP_TREND_WINDOW = 10
VWAP_BAND_MULTIPLIER = 1.0
VWAP_TP_BAND_MULTIPLIER = 2.0
VWAP_BAND_LOOKBACK = 20

# Cờ bật/tắt các điều kiện lọc (Giống scanner)
ENABLE_VWAP_TREND = True
ENABLE_RSI_EMA = False
ENABLE_ICHIMOKU = True

# Khởi tạo sàn giao dịch
exchange = ccxt.binance()

def get_top_coins():
    """Lấy danh sách coin từ CoinMarketCap."""
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
            symbols = [f"{coin['symbol']}/USDT" for coin in data['data']]
            markets = exchange.load_markets()
            available_symbols = [s for s in symbols if s in markets]
            return available_symbols
    except Exception as e:
        print(f"Lỗi khi lấy danh sách coin: {e}")
    return []

def get_ohlcv(symbol, timeframe):
    """Lấy dữ liệu OHLCV."""
    try:
        # Lấy tối đa 1000 nến
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=1000)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        return None

def calculate_indicators(df, timeframe):
    """Tính toán các chỉ báo kỹ thuật."""
    if df is None or len(df) < 50:
        return None

    # --- VWAP & Bands ---
    df['tp'] = (df['high'] + df['low'] + df['close']) / 3
    df['tp_v'] = df['tp'] * df['volume']
    df['tp_sq_v'] = (df['tp'] ** 2) * df['volume']

    if timeframe.endswith('d') or timeframe.endswith('w'):
        grouper = df['timestamp'].dt.to_period('M')
    else:
        grouper = df['timestamp'].dt.to_period('W')

    df['cum_v'] = df.groupby(grouper)['volume'].cumsum()
    df['cum_tp_v'] = df.groupby(grouper)['tp_v'].cumsum()
    df['cum_tp_sq_v'] = df.groupby(grouper)['tp_sq_v'].cumsum()

    df['vwap'] = df['cum_tp_v'] / df['cum_v']
    
    # Tính Anchor Index
    df['anchor_idx'] = df.groupby(grouper).cumcount()
    
    df['variance'] = (df['cum_tp_sq_v'] / df['cum_v']) - (df['vwap'] ** 2)
    df['variance'] = df['variance'].clip(lower=0)
    df['stdev'] = np.sqrt(df['variance'])

    df['upper_band_1'] = df['vwap'] + (VWAP_BAND_MULTIPLIER * df['stdev'])
    df['lower_band_1'] = df['vwap'] - (VWAP_BAND_MULTIPLIER * df['stdev'])
    
    df['upper_band_2'] = df['vwap'] + (VWAP_TP_BAND_MULTIPLIER * df['stdev'])
    df['lower_band_2'] = df['vwap'] - (VWAP_TP_BAND_MULTIPLIER * df['stdev'])

    df['vwap_ma'] = df['vwap'].rolling(window=VWAP_TREND_WINDOW).mean()
    
    # --- EMA 200 & Volume MA ---
    try:
        df['ema_200'] = ta.ema(df['close'], length=200)
        df['vol_ma_20'] = df['volume'].rolling(window=20).mean()
    except:
        return None

    # --- Ichimoku ---
    try:
        ichimoku_data, _ = ta.ichimoku(df['high'], df['low'], df['close'])
        df = pd.concat([df, ichimoku_data], axis=1)
    except:
        return None

    # --- RSI EMA ---
    try:
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema_rsi_10'] = ta.ema(df['rsi'], length=10)
        df['ema_rsi_20'] = ta.ema(df['rsi'], length=20)
        df['ema_rsi_30'] = ta.ema(df['rsi'], length=30)
    except:
        return None

    return df

def backtest_series(df, symbol, timeframe):
    """Thực hiện backtest trên dữ liệu lịch sử."""
    if df is None: return []

    trades = []
    position = None
    entry_price = 0
    entry_sl_price = 0 # Hard SL price (Low/High of entry candle)
    entry_index = 0
    tp1_hit = False
    tp1_price = 0
    partial_exit_done = False
    
    try:
        span_a_col = [c for c in df.columns if c.startswith('ISA_')][0]
        span_b_col = [c for c in df.columns if c.startswith('ISB_')][0]
    except IndexError:
        # Ichimoku columns not found, skip this symbol
        return []

    start_idx = max(VWAP_TREND_WINDOW, 200)
    
    for i in range(start_idx, len(df)):
        curr_candle = df.iloc[i]
        prev_candle = df.iloc[i-1]
        
        if position == 'LONG':
            exit_price = 0
            exit_reason = ''
            pnl = 0
            
            # 1. Check Hard SL first (Low of current candle hits Entry Candle Low)
            if curr_candle['low'] <= entry_sl_price:
                exit_price = entry_sl_price
                exit_reason = 'SL_CANDLE'
                position = None
                pnl = (exit_price - entry_price) / entry_price
            
            # 2. Check TP / Soft SL
            elif not tp1_hit:
                if curr_candle['high'] >= curr_candle['upper_band_1']:
                    tp1_hit = True
                    tp1_price = curr_candle['upper_band_1']
                    partial_exit_done = True
                    
                    if curr_candle['high'] >= curr_candle['upper_band_2']:
                        exit_price = curr_candle['upper_band_2']
                        exit_reason = 'TP1+TP2'
                        position = None
                        # PnL = 25% TP1 + 75% TP2
                        pnl = 0.25 * ((tp1_price - entry_price) / entry_price) + 0.75 * ((exit_price - entry_price) / entry_price)
                    else:
                        pass
                
                elif curr_candle['close'] < curr_candle['vwap']:
                    exit_price = curr_candle['close']
                    exit_reason = 'SL_VWAP'
                    position = None
                    pnl = (exit_price - entry_price) / entry_price

            elif position == 'LONG' and tp1_hit:
                if curr_candle['high'] >= curr_candle['upper_band_2']:
                    exit_price = curr_candle['upper_band_2']
                    exit_reason = 'TP2'
                    position = None
                    
                    if partial_exit_done:
                        # PnL = 25% TP1 + 75% TP2
                        pnl = 0.25 * ((tp1_price - entry_price) / entry_price) + 0.75 * ((exit_price - entry_price) / entry_price)
                    else:
                        pnl = (exit_price - entry_price) / entry_price
                
                elif partial_exit_done and curr_candle['low'] <= entry_price:
                    exit_price = entry_price
                    exit_reason = 'SL_BE'
                    position = None
                    # PnL = 25% TP1 + 75% BE (0)
                    pnl = 0.25 * ((tp1_price - entry_price) / entry_price) + 0
                    
                elif not partial_exit_done and curr_candle['close'] < curr_candle['vwap']:
                    exit_price = curr_candle['close']
                    exit_reason = 'SL_VWAP'
                    position = None
                    pnl = (exit_price - entry_price) / entry_price

            if position is None:
                trades.append({
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'type': 'LONG',
                    'entry_time': df.iloc[entry_index]['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': curr_candle['timestamp'],
                    'exit_price': exit_price,
                    'reason': exit_reason,
                    'pnl': pnl,
                    'duration': i - entry_index
                })
                continue

        elif position == 'SHORT':
            exit_price = 0
            exit_reason = ''
            pnl = 0
            
            # 1. Check Hard SL first (High of current candle hits Entry Candle High)
            if curr_candle['high'] >= entry_sl_price:
                exit_price = entry_sl_price
                exit_reason = 'SL_CANDLE'
                position = None
                pnl = (entry_price - exit_price) / entry_price

            # 2. Check TP / Soft SL
            elif not tp1_hit:
                if curr_candle['low'] <= curr_candle['lower_band_1']:
                    tp1_hit = True
                    tp1_price = curr_candle['lower_band_1']
                    partial_exit_done = True
                    
                    if curr_candle['low'] <= curr_candle['lower_band_2']:
                        exit_price = curr_candle['lower_band_2']
                        exit_reason = 'TP1+TP2'
                        position = None
                        # PnL = 25% TP1 + 75% TP2
                        pnl = 0.25 * ((entry_price - tp1_price) / entry_price) + 0.75 * ((entry_price - exit_price) / entry_price)
                    else:
                        pass
                
                elif curr_candle['close'] > curr_candle['vwap']:
                    exit_price = curr_candle['close']
                    exit_reason = 'SL_VWAP'
                    position = None
                    pnl = (entry_price - exit_price) / entry_price

            elif position == 'SHORT' and tp1_hit:
                if curr_candle['low'] <= curr_candle['lower_band_2']:
                    exit_price = curr_candle['lower_band_2']
                    exit_reason = 'TP2'
                    position = None
                    
                    if partial_exit_done:
                        # PnL = 25% TP1 + 75% TP2
                        pnl = 0.25 * ((entry_price - tp1_price) / entry_price) + 0.75 * ((entry_price - exit_price) / entry_price)
                    else:
                        pnl = (entry_price - exit_price) / entry_price
                
                elif partial_exit_done and curr_candle['high'] >= entry_price:
                    exit_price = entry_price
                    exit_reason = 'SL_BE'
                    position = None
                    # PnL = 25% TP1 + 75% BE (0)
                    pnl = 0.25 * ((entry_price - tp1_price) / entry_price) + 0
                    
                elif not partial_exit_done and curr_candle['close'] > curr_candle['vwap']:
                    exit_price = curr_candle['close']
                    exit_reason = 'SL_VWAP'
                    position = None
                    pnl = (entry_price - exit_price) / entry_price

            if position is None:
                trades.append({
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'type': 'SHORT',
                    'entry_time': df.iloc[entry_index]['timestamp'],
                    'entry_price': entry_price,
                    'exit_time': curr_candle['timestamp'],
                    'exit_price': exit_price,
                    'reason': exit_reason,
                    'pnl': pnl,
                    'duration': i - entry_index
                })
                continue

        if position is None:
            if prev_candle['close'] < prev_candle['vwap'] and curr_candle['close'] > curr_candle['vwap'] and curr_candle['open'] < curr_candle['vwap']:
                vwap_trend_ok = not ENABLE_VWAP_TREND or (curr_candle['vwap'] > curr_candle['vwap_ma'])
                ichimoku_ok = not ENABLE_ICHIMOKU or (curr_candle['close'] > curr_candle[span_a_col] and curr_candle['close'] > curr_candle[span_b_col])
                rsi_ema_ok = not ENABLE_RSI_EMA or (curr_candle['ema_rsi_10'] > curr_candle['ema_rsi_20'] > curr_candle['ema_rsi_30'])
                
                trend_ok = curr_candle['close'] > curr_candle['ema_200']
                volume_ok = curr_candle['volume'] > curr_candle['vol_ma_20']

                start_pos = i - VWAP_BAND_LOOKBACK + 1
                if start_pos < 0: start_pos = 0
                recent_lows = df['low'].iloc[start_pos:i+1]
                recent_lower_bands = df['lower_band_1'].iloc[start_pos:i+1]
                band_touch_ok = (recent_lows <= recent_lower_bands).any()
                
                anchor_ok = curr_candle['anchor_idx'] >= 10
                
                if vwap_trend_ok and ichimoku_ok and rsi_ema_ok and band_touch_ok and trend_ok and volume_ok and anchor_ok:
                    position = 'LONG'
                    entry_price = curr_candle['close']
                    entry_sl_price = curr_candle['low'] # Hard SL at Entry Candle Low
                    entry_index = i
                    
                    if entry_price >= curr_candle['upper_band_1']:
                        tp1_hit = True
                        partial_exit_done = False
                    else:
                        tp1_hit = False
                        partial_exit_done = False
            
            elif prev_candle['close'] > prev_candle['vwap'] and curr_candle['close'] < curr_candle['vwap'] and curr_candle['open'] > curr_candle['vwap']:
                vwap_trend_ok = not ENABLE_VWAP_TREND or (curr_candle['vwap'] < curr_candle['vwap_ma'])
                ichimoku_ok = not ENABLE_ICHIMOKU or (curr_candle['close'] < curr_candle[span_a_col] and curr_candle['close'] < curr_candle[span_b_col])
                rsi_ema_ok = not ENABLE_RSI_EMA or (curr_candle['ema_rsi_10'] < curr_candle['ema_rsi_20'] < curr_candle['ema_rsi_30'])
                
                trend_ok = curr_candle['close'] < curr_candle['ema_200']
                volume_ok = curr_candle['volume'] > curr_candle['vol_ma_20']

                start_pos = i - VWAP_BAND_LOOKBACK + 1
                if start_pos < 0: start_pos = 0
                recent_highs = df['high'].iloc[start_pos:i+1]
                recent_upper_bands = df['upper_band_1'].iloc[start_pos:i+1]
                band_touch_ok = (recent_highs >= recent_upper_bands).any()
                
                anchor_ok = curr_candle['anchor_idx'] >= 10
                
                if vwap_trend_ok and ichimoku_ok and rsi_ema_ok and band_touch_ok and trend_ok and volume_ok and anchor_ok:
                    position = 'SHORT'
                    entry_price = curr_candle['close']
                    entry_sl_price = curr_candle['high'] # Hard SL at Entry Candle High
                    entry_index = i
                    
                    if entry_price <= curr_candle['lower_band_1']:
                        tp1_hit = True
                        partial_exit_done = False
                    else:
                        tp1_hit = False
                        partial_exit_done = False

    return trades

def run_backtest():
    print("--- Starting VWAP Strategy Backtest ---")
    top_coins = get_top_coins()
    if not top_coins:
        print("Could not fetch coin list.")
        return

    all_trades = []
    
    for timeframe in TIMEFRAMES:
        print(f"\nBacktesting timeframe {timeframe}...")
        for coin in top_coins:
            df = get_ohlcv(coin, timeframe)
            df = calculate_indicators(df, timeframe)
            trades = backtest_series(df, coin, timeframe)
            all_trades.extend(trades)
            
    if not all_trades:
        print("\nNo trades executed.")
        return

    df_res = pd.DataFrame(all_trades)
    
    print("\n" + "="*50)
    print("BACKTEST RESULTS")
    print("="*50)
    
    def print_stats(df, title="ALL TIMEFRAMES"):
        if df.empty:
            print(f"\n--- {title} ---")
            print("No trades.")
            return

        total_trades = len(df)
        win_trades = df[df['pnl'] > 0]
        loss_trades = df[df['pnl'] <= 0]
        win_rate = len(win_trades) / total_trades * 100
        
        avg_pnl = df['pnl'].mean() * 100
        total_pnl = df['pnl'].sum() * 100
        
        win_band1_only = df[(df['reason'] == 'SL_BE') & (df['pnl'] > 0)]
        win_band2 = df[(df['reason'].isin(['TP1+TP2', 'TP2'])) & (df['pnl'] > 0)]
        
        loss_vwap = df[(df['reason'] == 'SL_VWAP') & (df['pnl'] <= 0)]
        loss_candle = df[(df['reason'] == 'SL_CANDLE') & (df['pnl'] <= 0)]
        
        avg_win_pnl = win_trades['pnl'].mean() * 100 if not win_trades.empty else 0
        avg_loss_pnl = loss_trades['pnl'].mean() * 100 if not loss_trades.empty else 0
        
        print(f"\n--- {title} ---")
        print(f"Tổng số lệnh: {total_trades}")
        print(f"Winrate: {win_rate:.2f}%")
        print(f"Tổng số lệnh thắng: {len(win_trades)}")
        print(f"Số lệnh thắng chạm Band 1 (không chạm Band 2): {len(win_band1_only)}")
        print(f"Số lệnh thắng chạm Band 2: {len(win_band2)}")
        print(f"Tổng số lệnh thua: {len(loss_trades)}")
        print(f"Số lệnh thua đảo ngược vwap: {len(loss_vwap)}")
        print(f"Số lệnh thua đảo ngược nến: {len(loss_candle)}")
        print(f"Lời trung bình các lệnh thắng: {avg_win_pnl:+.2f}%")
        print(f"Lỗ trung bình các lệnh thua: {avg_loss_pnl:+.2f}%")
        print(f"Lời/Lỗ trung bình tất cả các lệnh: {avg_pnl:+.2f}%")

    print_stats(df_res, "OVERALL")

    for tf in TIMEFRAMES:
        df_tf = df_res[df_res['timeframe'] == tf]
        print_stats(df_tf, f"TIMEFRAME {tf}")

    os.makedirs('output', exist_ok=True)
    df_res.to_csv('output/backtest_results.csv', index=False)
    print(f"\nTrade details saved to output/backtest_results.csv")

if __name__ == "__main__":
    run_backtest()
