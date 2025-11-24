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

from scanner_config import (
    COINMARKETCAP_API_KEY,
    TELEGRAM_BOT_TOKEN,
    EMA_RSI_TELEGRAM_CHAT_ID,
    USE_FIXED_LIST,
    FIXED_SYMBOLS,
    TOP_N_COINS,
    LOOKBACK_CANDLES,
    SUPER_TREND_LENGTH,
    SUPER_TREND_MULTIPLIER,
    EMA_RSI_TIMEFRAME_CONFIGS,
    EMA_RSI_SETUP_CONFIGS,
    EMA_RSI_SIGNAL_WINDOW
)



# Khởi tạo sàn giao dịch - Bybit Futures
exchange = ccxt.bybit({
    'options': {
        'defaultType': 'linear',  # USDT Perpetual
    }
})

def get_target_coins():
    """Lấy danh sách coin mục tiêu (Cố định hoặc Top N từ CMC)."""
    if USE_FIXED_LIST:
        print(f"Đang sử dụng danh sách cố định ({len(FIXED_SYMBOLS)} coin).")
        return FIXED_SYMBOLS

    """Lấy danh sách loại tiền điện tử hàng đầu từ CoinMarketCap."""
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
        # Tải dữ liệu nến
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=500)
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
            await bot.send_message(chat_id=EMA_RSI_TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
        
        asyncio.run(_send())
        print(f"Đã gửi thông báo: {message}")
    except Exception as e:
        print(f"Lỗi khi gửi tin nhắn Telegram: {e}")

def write_signal_to_file(message):
    """Ghi thông báo tín hiệu vào file text."""
    try:
        os.makedirs('output', exist_ok=True)
        with open('output/ema_rsi_signal.txt', 'a', encoding='utf-8') as f:
            f.write(f"{pd.Timestamp.now()} - {message}\n" + "-"*50 + "\n")
        print("Đã ghi tín hiệu vào file output/ema_rsi_signal.txt")
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

def check_ema_rsi_signals(df, symbol, timeframe):
    """Kiểm tra tín hiệu EMA RSI và trả về danh sách tín hiệu tìm được."""
    signals_found = []
    if df is None or len(df) < 50:
        return signals_found

    # Tính toán RSI và 3 đường EMA của RSI
    try:
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema_rsi_5'] = ta.ema(df['rsi'], length=5)
        df['ema_rsi_10'] = ta.ema(df['rsi'], length=10)
        df['ema_rsi_20'] = ta.ema(df['rsi'], length=20)
    except Exception as e:
        # print(f"Lỗi tính RSI/EMA cho {symbol}: {e}")
        return

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
        if len(df) < (i + 2):
            break

        # Index của nến hiện tại (đang xét)
        curr_idx = -1 - i
        last_candle = df.iloc[curr_idx]

        # Bỏ qua nếu thiếu dữ liệu
        if pd.isna(last_candle['ema_rsi_5']) or pd.isna(last_candle['ema_rsi_10']) or pd.isna(last_candle['ema_rsi_20']) or \
           pd.isna(last_candle[span_a_col]) or pd.isna(last_candle[span_b_col]):
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
        for setup in EMA_RSI_SETUP_CONFIGS:
            if not setup.get('enabled', True):
                continue

            # Logic phát hiện tín hiệu EMA RSI (Window-based)
            is_long = False
            is_short = False
            reversal_dist = -1
            
            # Trạng thái hiện tại
            curr_long_state = (last_candle['ema_rsi_5'] > last_candle['ema_rsi_10'] and 
                               last_candle['ema_rsi_5'] > last_candle['ema_rsi_20'])
            curr_short_state = (last_candle['ema_rsi_5'] < last_candle['ema_rsi_10'] and 
                                last_candle['ema_rsi_5'] < last_candle['ema_rsi_20'])

            if setup['signal_type'] == 'LONG':
                if curr_long_state:
                    # Tìm điểm đảo chiều gần nhất trong cửa sổ EMA_RSI_SIGNAL_WINDOW
                    for k in range(EMA_RSI_SIGNAL_WINDOW):
                        target_idx = curr_idx - k
                        prev_target_idx = target_idx - 1
                        if abs(prev_target_idx) > len(df): break
                        
                        k_candle = df.iloc[target_idx]
                        k_prev_candle = df.iloc[prev_target_idx]
                        
                        k_is_long = (k_candle['ema_rsi_5'] > k_candle['ema_rsi_10'] and 
                                     k_candle['ema_rsi_5'] > k_candle['ema_rsi_20'])
                        k_prev_is_long = (k_prev_candle['ema_rsi_5'] > k_prev_candle['ema_rsi_10'] and 
                                         k_prev_candle['ema_rsi_5'] > k_prev_candle['ema_rsi_20'])
                        
                        if k_is_long and not k_prev_is_long:
                            reversal_dist = k
                            is_long = True
                            break
                        if not k_is_long: break
            elif setup['signal_type'] == 'SHORT':
                if curr_short_state:
                    for k in range(EMA_RSI_SIGNAL_WINDOW):
                        target_idx = curr_idx - k
                        prev_target_idx = target_idx - 1
                        if abs(prev_target_idx) > len(df): break
                        
                        k_candle = df.iloc[target_idx]
                        k_prev_candle = df.iloc[prev_target_idx]
                        
                        k_is_short = (k_candle['ema_rsi_5'] < k_candle['ema_rsi_10'] and 
                                      k_candle['ema_rsi_5'] < k_candle['ema_rsi_20'])
                        k_prev_is_short = (k_prev_candle['ema_rsi_5'] < k_prev_candle['ema_rsi_10'] and 
                                          k_prev_candle['ema_rsi_5'] < k_prev_candle['ema_rsi_20'])
                        
                        if k_is_short and not k_prev_is_short:
                            reversal_dist = k
                            is_short = True
                            break
                        if not k_is_short: break

            if not is_long and not is_short:
                continue
            
            # --- Kiểm tra Filter (Chỉ cần 1 trong các nến trong window thỏa mãn) ---
            conditions_met = True
            filter_msg = ""
            win_indices = [curr_idx - x for x in range(reversal_dist + 1)]

            # 0. EMA RSI Distance Filter
            if setup.get('min_ema_rsi_distance', 0) > 0:
                dist_ok = False
                for idx_w in win_indices:
                    c = df.iloc[idx_w]
                    spread = max(c['ema_rsi_5'], c['ema_rsi_10'], c['ema_rsi_20']) - min(c['ema_rsi_5'], c['ema_rsi_10'], c['ema_rsi_20'])
                    if spread >= setup['min_ema_rsi_distance']:
                        dist_ok = True; filter_msg += f"EMA RSI Spread: {spread:.2f} (OK)\n"; break
                if not dist_ok: conditions_met = False

            # 1. Ichimoku Filter
            if conditions_met and setup.get('enable_ichimoku', False):
                ichi_ok = False
                for idx_w in win_indices:
                    c = df.iloc[idx_w]
                    if is_long and c['close'] > c[span_b_col]: ichi_ok = True; break
                    if is_short and c['close'] < c[span_b_col]: ichi_ok = True; break
                if not ichi_ok: conditions_met = False
                else: filter_msg += "Ichimoku: OK (in window)\n"
            
            # 2. Volume Filter
            if conditions_met and setup.get('enable_volume_filter', False):
                vol_ok = False
                for idx_w in win_indices:
                    c = df.iloc[idx_w]
                    if 'vol_ma_20' in df.columns and pd.notna(c['vol_ma_20']):
                        if c['volume'] > c['vol_ma_20']: vol_ok = True; break
                if not vol_ok: conditions_met = False
                else: filter_msg += "Volume: OK (in window)\n"

            # 3. Super Trend Filter
            if conditions_met and setup.get('enable_super_trend', False):
                st_ok = False
                for idx_w in win_indices:
                    c = df.iloc[idx_w]
                    if st_dir_col and st_dir_col in df.columns:
                        if is_long and c[st_dir_col] == 1: st_ok = True; break
                        if is_short and c[st_dir_col] == -1: st_ok = True; break
                if not st_ok: conditions_met = False
                else: filter_msg += "Super Trend: OK (in window)\n"
            
            if conditions_met:
                # Convert signal_time to local time (Asia/Ho_Chi_Minh)
                try:
                    local_signal_time = signal_time.tz_localize('UTC').tz_convert('Asia/Ho_Chi_Minh')
                except Exception:
                    local_signal_time = signal_time + pd.Timedelta(hours=7)

                icon = "🚀" if is_long else "🔻"
                
                signal_data = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'time': local_signal_time,
                    'type': setup['signal_type'],
                    'price': last_candle['close'],
                    'ema_rsi_5': last_candle['ema_rsi_5'],
                    'ema_rsi_10': last_candle['ema_rsi_10'],
                    'ema_rsi_20': last_candle['ema_rsi_20'],
                    'setup_name': setup['name'],
                    'icon': icon,
                    'candles_ago': i,
                    'reversal_dist': reversal_dist
                }
                signals_found.append(signal_data)
                
                # Format for local file
                file_msg = f"{icon} TÍN HIỆU {setup['name'].upper()}: {symbol} ({timeframe}) - {local_signal_time.strftime('%Y-%m-%d %H:%M:%S')}"
                write_signal_to_file(file_msg)
    
    return signals_found

def send_aggregated_signals(signals):
    """Gửi tất cả tín hiệu trong một bảng duy nhất đến Telegram."""
    if not signals:
        return

    # Sắp xếp theo thời gian (mới nhất lên đầu)
    signals.sort(key=lambda x: x['time'], reverse=True)

    msg_lines = []
    msg_lines.append(f"🎯 *EMA RSI SIGNALS* - {pd.Timestamp.now(tz='Asia/Ho_Chi_Minh').strftime('%H:%M')}")
    msg_lines.append("```")
    msg_lines.append(f"{'Name':<8} {'TF':<4} {'Type':<6} {'Price':<10} {'EMA RSI':<10} {'Time':<12} {'Ago':<4} {'Rev':<4}")
    msg_lines.append("-" * 58)

    for sig in signals:
        # Rút gọn symbol (e.g., BTC/USDT -> BTC)
        name = sig['symbol'].split('/')[0]
        tf = sig['timeframe']
        type_str = sig['type']
        price = sig['price']
        
        # Price formatting matching Bybit
        p_str = f"${price:.4f}" if price < 100 else f"${price:.2f}"
        
        # EMA RSI values (compact)
        ers_str = f"{sig['ema_rsi_5']:.0f}/{sig['ema_rsi_10']:.0f}/{sig['ema_rsi_20']:.0f}"
        
        # Time (HH:MM format)
        time_str = sig['time'].strftime('%m-%d %H:%M')
        
        # Candles ago and reversal
        ago_str = f"{sig['candles_ago']}n"
        rev_str = f"{sig['reversal_dist']}n"
        
        row_str = f"{name:<8} {tf:<4} {type_str:<6} {p_str:<10} {ers_str:<10} {time_str:<12} {ago_str:<4} {rev_str:<4}"
        msg_lines.append(row_str)

    msg_lines.append("```")
    
    full_message = "\n".join(msg_lines)
    send_telegram_message(full_message)

def main():
    """Hàm chính để chạy máy quét EMA RSI."""
    print("--- Bắt đầu máy quét tín hiệu EMA RSI ---")
    send_telegram_message("--- Bắt đầu máy quét tín hiệu EMA RSI ---")
    top_coins = get_target_coins()

    if not top_coins:
        print("Không thể lấy danh sách tiền điện tử. Thoát.")
        return

    while True:
        print("\n--- Bắt đầu chu kỳ quét mới ---")
        all_signals = []
        for config in EMA_RSI_TIMEFRAME_CONFIGS:
            timeframe = config['timeframe']
            
            for coin in top_coins:
                print(f"Đang quét {coin} trên khung {timeframe}...")
                df = get_ohlcv(coin, timeframe)
                if df is not None:
                    found = check_ema_rsi_signals(df, coin, timeframe)
                    if found:
                        all_signals.extend(found)
                wait_with_interaction(0.1) # Tạm dừng ngắn
            
        if all_signals:
            print(f"Đã tìm thấy {len(all_signals)} tín hiệu. Gửi Telegram...")
            send_aggregated_signals(all_signals)
        else:
            print("Không có tín hiệu mới.")

        print(f"--- Đã hoàn thành chu kỳ quét. Chờ 30 phút cho lần quét tiếp theo ---")
        wait_with_interaction(1800, "Đang chờ") # Chờ 30 phút với tương tác

if __name__ == '__main__':
    main()
