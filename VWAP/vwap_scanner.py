import os
import time
import requests
import pandas as pd
import numpy as np
import pandas_ta as ta
import ccxt
import telegram
import asyncio
import sys

if os.name == 'nt':
    import msvcrt

from scanner_config import *


# Khởi tạo sàn giao dịch (sử dụng Binance làm ví dụ)
exchange = ccxt.binance()

def get_target_coins():
    """Lấy danh sách coin mục tiêu (Cố định hoặc Top N từ CMC)."""
    if USE_FIXED_LIST:
        print(f"Đang sử dụng danh sách cố định ({len(FIXED_SYMBOLS)} coin).")
        return FIXED_SYMBOLS

    """Lấy danh sách 100 loại tiền điện tử hàng đầu từ CoinMarketCap."""
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
            # Lọc các cặp giao dịch có sẵn trên Binance với USDT
            symbols = [f"{coin['symbol']}/USDT" for coin in data['data']]
            markets = exchange.load_markets()
            available_symbols = [s for s in symbols if s in markets]
            print(f"Đã tìm thấy {len(available_symbols)}/{TOP_N_COINS} cặp giao dịch có sẵn trên Binance với USDT.")
            return available_symbols
    except Exception as e:
        print(f"Lỗi khi lấy danh sách tiền điện tử: {e}")
    return []

def get_ohlcv(symbol, timeframe):
    """Lấy dữ liệu OHLCV cho một cặp giao dịch."""
    try:
        # Tải dữ liệu nến, giới hạn là 1000 nến để đảm bảo đủ dữ liệu cho VWAP tuần (đặc biệt là khung 15m)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=1000)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        # print(f"Không thể lấy dữ liệu cho {symbol}: {e}")
        return None

def send_telegram_message(message):
    """Gửi tin nhắn đến kênh Telegram."""
    try:
        async def _send():
            bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.send_message(chat_id=VWAP_TELEGRAM_CHAT_ID, text=message)
        
        asyncio.run(_send())
        print(f"Đã gửi thông báo: {message}")
    except Exception as e:
        print(f"Lỗi khi gửi tin nhắn Telegram: {e}")

def write_signal_to_file(message):
    """Ghi thông báo tín hiệu vào file text."""
    try:
        os.makedirs('output', exist_ok=True)
        with open('output/vwap_signal.txt', 'a', encoding='utf-8') as f:
            f.write(f"{pd.Timestamp.now()} - {message}\n" + "-"*50 + "\n")
        print("Đã ghi tín hiệu vào file output/vwap_signal.txt")
    except Exception as e:
        print(f"Lỗi khi ghi file: {e}")


def wait_with_interaction(seconds, message=None):
    """Chờ đợi với khả năng tương tác phím (q: quit, r: restart)."""
    if message:
        print(f"{message} (Nhấn 'q' để thoát, 'r' để khởi động lại ngay)", end="", flush=True)
    
    start_time = time.time()
    while time.time() - start_time < seconds:
        if os.name == 'nt' and msvcrt.kbhit():
            key = msvcrt.getch().decode('utf-8').lower()
            if key == 'q':
                print("\nĐã nhận lệnh thoát ('q'). Dừng chương trình.")
                sys.exit()
            elif key == 'r':
                print("\nĐã nhận lệnh khởi động lại ('r'). Đang khởi động lại...")
                os.execl(sys.executable, sys.executable, *sys.argv)
        time.sleep(0.1)
    
    if message:
        print() # Xuống dòng sau khi chờ xong

def check_signals(df, symbol, timeframe, anchor_period='M'):
    """Kiểm tra tín hiệu dựa trên cấu hình SETUP_CONFIGS."""
    if df is None or len(df) < 2:
        return

    # --- Tính toán VWAP và Bands thủ công ---
    # Tính Typical Price
    df['tp'] = (df['high'] + df['low'] + df['close']) / 3
    df['tp_v'] = df['tp'] * df['volume']
    df['tp_sq_v'] = (df['tp'] ** 2) * df['volume']

    # Xác định nhóm Anchor
    if anchor_period == 'W':
        grouper = df['timestamp'].dt.to_period('W')
    elif anchor_period == 'M':
        grouper = df['timestamp'].dt.to_period('M')
    elif anchor_period == 'Q':
        grouper = df['timestamp'].dt.to_period('Q')
    elif anchor_period == 'Y':
        grouper = df['timestamp'].dt.to_period('Y')
    else:
        # Mặc định là Tháng nếu không xác định được
        grouper = df['timestamp'].dt.to_period('M')

    # Tính tổng tích lũy theo nhóm
    df['cum_v'] = df.groupby(grouper)['volume'].cumsum()
    df['cum_tp_v'] = df.groupby(grouper)['tp_v'].cumsum()
    df['cum_tp_sq_v'] = df.groupby(grouper)['tp_sq_v'].cumsum()
    
    # Tính Anchor Index (Số thứ tự nến trong Anchor Period)
    df['anchor_idx'] = df.groupby(grouper).cumcount()

    # Tính VWAP
    df['vwap'] = df['cum_tp_v'] / df['cum_v']

    # Tính Variance và Stdev
    # Var = E[X^2] - (E[X])^2
    # E[X^2] = cum_tp_sq_v / cum_v
    # E[X] = vwap
    df['variance'] = (df['cum_tp_sq_v'] / df['cum_v']) - (df['vwap'] ** 2)
    df['variance'] = df['variance'].clip(lower=0) # Đảm bảo không âm
    df['stdev'] = np.sqrt(df['variance'])

    # Tính Bands
    df['upper_band_1'] = df['vwap'] + (VWAP_BAND_MULTIPLIER * df['stdev'])
    df['lower_band_1'] = df['vwap'] - (VWAP_BAND_MULTIPLIER * df['stdev'])
    
    df['upper_band_2'] = df['vwap'] + (VWAP_TP_BAND_MULTIPLIER * df['stdev'])
    df['lower_band_2'] = df['vwap'] - (VWAP_TP_BAND_MULTIPLIER * df['stdev'])

    df['upper_band_3'] = df['vwap'] + (VWAP_BAND_3_MULTIPLIER * df['stdev'])
    df['lower_band_3'] = df['vwap'] - (VWAP_BAND_3_MULTIPLIER * df['stdev'])

    # Tính trung bình VWAP để xác định xu hướng
    df['vwap_ma'] = df['vwap'].rolling(window=VWAP_TREND_WINDOW).mean()
    
    # Tính độ rộng VWAP và trung bình độ rộng (N=1000)
    df['vwap_width'] = df['upper_band_1'] - df['vwap']
    avg_width_1000 = df['vwap_width'].mean() # Trung bình của toàn bộ 1000 nến đã fetch
    
    # Tính EMA 200 và Volume MA 20
    try:
        df['ema_200'] = ta.ema(df['close'], length=200)
        df['vol_ma_20'] = df['volume'].rolling(window=20).mean()
    except:
        pass

    # Tính toán Ichimoku Cloud
    try:
        ichimoku_data, span_data = ta.ichimoku(df['high'], df['low'], df['close'])
        # Gộp ichimoku_data vào df chính
        df = pd.concat([df, ichimoku_data], axis=1)
        span_a_col = ichimoku_data.columns[0] 
        span_b_col = ichimoku_data.columns[1] 
    except Exception as e:
        # print(f"Lỗi tính Ichimoku cho {symbol}: {e}")
        return

    # Tính toán RSI và 3 đường EMA của RSI
    try:
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema_rsi_1'] = ta.ema(df['rsi'], length=RSI_EMA_1)
        df['ema_rsi_2'] = ta.ema(df['rsi'], length=RSI_EMA_2)
        df['ema_rsi_3'] = ta.ema(df['rsi'], length=RSI_EMA_3)
    except Exception as e:
        # print(f"Lỗi tính RSI/EMA cho {symbol}: {e}")
        return

    # Tính toán Super Trend
    try:
        sti = ta.supertrend(df['high'], df['low'], df['close'], length=SUPER_TREND_LENGTH, multiplier=SUPER_TREND_MULTIPLIER)
        if sti is not None and not sti.empty:
            df = pd.concat([df, sti], axis=1)
            st_dir_col = f"SUPERTd_{SUPER_TREND_LENGTH}_{SUPER_TREND_MULTIPLIER}"
            if st_dir_col not in df.columns:
                 # Fallback search
                 cols = [c for c in df.columns if c.startswith('SUPERTd_')]
                 if cols: st_dir_col = cols[0]
        else:
            st_dir_col = None
    except Exception as e:
        # print(f"Lỗi tính Super Trend cho {symbol}: {e}")
        st_dir_col = None

    # Lấy N cây nến cuối cùng để kiểm tra
    for i in range(LOOKBACK_CANDLES):
        if len(df) < (i + 2 + VWAP_BAND_LOOKBACK):
            break

        # Index của nến hiện tại (đang xét)
        curr_idx = -1 - i
        last_candle = df.iloc[curr_idx]

        # Bỏ qua nếu thiếu dữ liệu
        if pd.isna(last_candle['vwap']) or pd.isna(last_candle['vwap_ma']) or \
           pd.isna(last_candle[span_a_col]) or pd.isna(last_candle[span_b_col]) or \
           pd.isna(last_candle['ema_rsi_1']) or pd.isna(last_candle['ema_rsi_2']) or pd.isna(last_candle['ema_rsi_3']):
            continue

        signal_time = last_candle['timestamp']

        # Kiểm tra thời gian
        tf_seconds = 0
        if timeframe.endswith('m'): tf_seconds = int(timeframe[:-1]) * 60
        elif timeframe.endswith('h'): tf_seconds = int(timeframe[:-1]) * 3600
        elif timeframe.endswith('d'): tf_seconds = int(timeframe[:-1]) * 86400
        
        if (pd.Timestamp.utcnow().tz_localize(None) - signal_time).total_seconds() > (tf_seconds * LOOKBACK_CANDLES):
            continue

        # Duyệt qua từng Setup trong Configuration
        for setup in VWAP_SETUP_CONFIGS:
            if not setup.get('enabled', True):
                continue

            line_name = setup['line']
            
            if line_name not in df.columns:
                continue

            # Logic phát hiện tín hiệu VWAP (Window-based)
            is_crossover = False
            reversal_dist = -1
            
            # 1. Tìm điểm giao cắt (High/Low quét qua line) trong cửa sổ VWAP_SIGNAL_WINDOW
            for k in range(VWAP_SIGNAL_WINDOW):
                target_idx = curr_idx - k
                if abs(target_idx) > len(df): break
                
                k_candle = df.iloc[target_idx]
                if pd.isna(k_candle[line_name]): continue
                
                # High/Low quét qua line: line nằm giữa Low và High
                if k_candle['low'] <= k_candle[line_name] <= k_candle['high']:
                    is_crossover = True
                    reversal_dist = k
                    break
            
            if not is_crossover:
                continue

            # 2. Chiều tín hiệu dựa vào Close của nến đang xét (last_candle)
            is_long = False
            is_short = False
            
            if setup['signal_type'] == 'LONG' and last_candle['close'] > last_candle[line_name]:
                is_long = True
            elif setup['signal_type'] == 'SHORT' and last_candle['close'] < last_candle[line_name]:
                is_short = True
            
            if not is_long and not is_short:
                continue
            
            # --- Kiểm tra Filter (Chỉ cần 1 trong các nến trong window thỏa mãn) ---
            conditions_met = True
            filter_msg = ""
            win_indices = [curr_idx - x for x in range(reversal_dist + 1)]
            
            # 1. RSI EMA Filter
            if setup.get('enable_rsi_ema', False):
                rsi_ema_ok = False
                for idx_w in win_indices:
                    c = df.iloc[idx_w]
                    if is_long:
                        if c['ema_rsi_1'] > c['ema_rsi_2'] and c['ema_rsi_1'] > c['ema_rsi_3']:
                            rsi_ema_ok = True; break
                    elif is_short:
                        if c['ema_rsi_1'] < c['ema_rsi_2'] and c['ema_rsi_1'] < c['ema_rsi_3']:
                            rsi_ema_ok = True; break
                if not rsi_ema_ok: 
                    conditions_met = False
                else: 
                    filter_msg += "RSI EMA: OK (in window)\n"

            # 2. Ichimoku Filter
            if conditions_met and setup.get('enable_ichimoku', False):
                ichi_ok = False
                for idx_w in win_indices:
                    c = df.iloc[idx_w]
                    if is_long and c['close'] > c[span_b_col]: ichi_ok = True; break
                    if is_short and c['close'] < c[span_b_col]: ichi_ok = True; break
                if not ichi_ok: 
                    conditions_met = False
                else: 
                    filter_msg += "Ichimoku: OK (in window)\n"

            # 3. EMA Trend Filter
            if conditions_met and setup.get('enable_ema_trend', False):
                ema_trend_ok = False
                for idx_w in win_indices:
                    c = df.iloc[idx_w]
                    if 'ema_200' in df.columns and pd.notna(c['ema_200']):
                        if is_long and c['close'] > c['ema_200']: ema_trend_ok = True; break
                        if is_short and c['close'] < c['ema_200']: ema_trend_ok = True; break
                if not ema_trend_ok: 
                    conditions_met = False
                else: 
                    filter_msg += "EMA Trend: OK (in window)\n"
            
            # 4. Volume Filter
            if conditions_met and setup.get('enable_volume_filter', False):
                vol_ok = False
                for idx_w in win_indices:
                    c = df.iloc[idx_w]
                    if 'vol_ma_20' in df.columns and pd.notna(c['vol_ma_20']):
                        if c['volume'] > c['vol_ma_20']: vol_ok = True; break
                if not vol_ok: 
                    conditions_met = False
                else: 
                    filter_msg += "Volume: OK (in window)\n"

            # 5. Super Trend Filter
            if conditions_met and setup.get('enable_super_trend', False):
                st_ok = False
                for idx_w in win_indices:
                    c = df.iloc[idx_w]
                    if st_dir_col and st_dir_col in df.columns:
                        if is_long and c[st_dir_col] == 1: st_ok = True; break
                        if is_short and c[st_dir_col] == -1: st_ok = True; break
                if not st_ok: 
                    conditions_met = False
                else: 
                    filter_msg += "Super Trend: OK (in window)\n"
            
            # 6. Anchor Index Validation
            if last_candle['anchor_idx'] < VWAP_MIN_FROM_BEGIN:
                conditions_met = False

            # 7. VWAP Width Validation (Current > Avg 1000)
            if last_candle['vwap_width'] <= avg_width_1000:
                conditions_met = False
            else:
                filter_msg += f"VWAP Width: {last_candle['vwap_width']:.4f} > Avg ({avg_width_1000:.4f}) (OK)\n"

            if conditions_met:
                # Convert signal_time to local time (Asia/Ho_Chi_Minh)
                try:
                    local_signal_time = signal_time.tz_localize('UTC').tz_convert('Asia/Ho_Chi_Minh')
                except Exception:
                    local_signal_time = signal_time + pd.Timedelta(hours=7)

                icon = "🚀" if is_long else "🔻"
                
                message = f"{icon} TÍN HIỆU {setup['name'].upper()}: {symbol} ({timeframe})\n" \
                          f"Thời gian: {local_signal_time.strftime('%Y-%m-%d %H:%M:%S')}\n" \
                          f"Cách đây: {i} nến\n" \
                          f"Quét qua {line_name} cách đây: {reversal_dist} nến\n" \
                          f"Anchor Index: {last_candle['anchor_idx']}\n" \
                          f"Giá: {last_candle['close']:.4f} | VWAP Line ({line_name}): {last_candle[line_name]:.4f}\n" \
                          f"--------------------\n" \
                          f"{filter_msg}" \
                          f"--------------------\n" \
                          f"🛑 Gợi ý SL/TP: Tự xác định theo cấu trúc."
                
                send_telegram_message(message)
                write_signal_to_file(message)

def calculate_vwap_avg_width(df, n_candles=20):
    """
    Tính độ rộng trung bình của VWAP: trung bình khoảng cách 
    từ đường vwap tới đường upper_band_1 của N cây nến gần nhất.
    """
    if df is None or len(df) < n_candles:
        return None
        
    if 'vwap' not in df.columns or 'upper_band_1' not in df.columns:
        return None
        
    # Tính khoảng cách tại mỗi cây nến
    df['vwap_width'] = df['upper_band_1'] - df['vwap']
    
    # Tính trung bình của N cây nến gần nhất
    avg_width = df['vwap_width'].tail(n_candles).mean()
    
    return avg_width

def main():
    """Hàm chính để chạy máy quét."""
    print("--- Bắt đầu máy quét tín hiệu VWAP ---")
    send_telegram_message("--- Bắt đầu máy quét tín hiệu VWAP ---")
    top_coins = get_target_coins()

    if not top_coins:
        print("Không thể lấy danh sách tiền điện tử. Thoát.")
        return

    while True:
        print("\n--- Bắt đầu chu kỳ quét mới ---")
        for config in VWAP_TIMEFRAME_CONFIGS:
            timeframe = config['timeframe']
            anchor_period = config['anchor']
            
            for coin in top_coins:
                print(f"Đang quét {coin} trên khung {timeframe} (Anchor: {anchor_period})...")
                df = get_ohlcv(coin, timeframe)
                if df is not None:
                    check_signals(df, coin, timeframe, anchor_period)
                wait_with_interaction(1) # Tạm dừng ngắn, cho phép ngắt
            wait_with_interaction(1) # Tạm dừng giữa các config

        print(f"--- Đã hoàn thành chu kỳ quét. Chờ 30 phút cho lần quét tiếp theo ---")
        send_telegram_message("--- Đã hoàn thành chu kỳ quét. Chờ 30 phút cho lần quét tiếp theo ---")
        wait_with_interaction(1800, "Đang chờ") # Chờ 30 phút với tương tác

if __name__ == '__main__':
    main()