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
    TELEGRAM_CHAT_ID,
    USE_FIXED_LIST,
    FIXED_SYMBOLS,
    TOP_N_COINS,
    LOOKBACK_CANDLES,
    SUPER_TREND_LENGTH,
    SUPER_TREND_MULTIPLIER,
    EMA_RSI_TIMEFRAME_CONFIGS,
    EMA_RSI_SETUP_CONFIGS
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
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        
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
    """Kiểm tra tín hiệu EMA RSI dựa trên cấu hình EMA_RSI_SETUP_CONFIGS."""
    if df is None or len(df) < 50:
        return

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
        prev_idx = -2 - i
        
        last_candle = df.iloc[curr_idx]
        prev_candle = df.iloc[prev_idx]

        # Bỏ qua nếu thiếu dữ liệu
        if pd.isna(last_candle['ema_rsi_5']) or pd.isna(last_candle['ema_rsi_10']) or pd.isna(last_candle['ema_rsi_20']) or \
           pd.isna(prev_candle['ema_rsi_5']) or pd.isna(prev_candle['ema_rsi_10']) or pd.isna(prev_candle['ema_rsi_20']) or \
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

            # Logic phát hiện tín hiệu EMA RSI
            is_long = False
            is_short = False
            
            # Kiểm tra trạng thái EMA RSI hiện tại và trước đó
            curr_ema_long = (last_candle['ema_rsi_5'] > last_candle['ema_rsi_10'] and 
                            last_candle['ema_rsi_5'] > last_candle['ema_rsi_20'])
            curr_ema_short = (last_candle['ema_rsi_5'] < last_candle['ema_rsi_10'] and 
                             last_candle['ema_rsi_5'] < last_candle['ema_rsi_20'])
            
            prev_ema_long = (prev_candle['ema_rsi_5'] > prev_candle['ema_rsi_10'] and 
                            prev_candle['ema_rsi_5'] > prev_candle['ema_rsi_20'])
            prev_ema_short = (prev_candle['ema_rsi_5'] < prev_candle['ema_rsi_10'] and 
                             prev_candle['ema_rsi_5'] < prev_candle['ema_rsi_20'])
            
            if setup['signal_type'] == 'LONG':
                # Tín hiệu LONG: Chuyển từ không phải long sang long
                # (EMA5 <= EMA10 hoặc EMA5 <= EMA20) => (EMA5 > EMA10 và EMA5 > EMA20)
                if not prev_ema_long and curr_ema_long:
                    is_long = True
            elif setup['signal_type'] == 'SHORT':
                # Tín hiệu SHORT: Chuyển từ không phải short sang short
                # (EMA5 >= EMA10 hoặc EMA5 >= EMA20) => (EMA5 < EMA10 và EMA5 < EMA20)
                if not prev_ema_short and curr_ema_short:
                    is_short = True
            
            if not is_long and not is_short:
                continue
            
            # --- Kiểm tra Filter ---
            conditions_met = True
            filter_msg = ""
            
            # 1. Ichimoku Filter
            if setup.get('enable_ichimoku', False):
                if is_long:
                    if not (last_candle['close'] > last_candle[span_b_col]):
                         conditions_met = False
                    else:
                         filter_msg += "Ichimoku: Close > Span B (OK)\n"
                elif is_short:
                    if not (last_candle['close'] < last_candle[span_b_col]):
                        conditions_met = False
                    else:
                        filter_msg += "Ichimoku: Close < Span B (OK)\n"
            
            # 2. Volume Filter
            if setup.get('enable_volume_filter', False):
                if 'vol_ma_20' in df.columns and pd.notna(last_candle['vol_ma_20']):
                    if not (last_candle['volume'] > last_candle['vol_ma_20']):
                        conditions_met = False
                    else:
                        filter_msg += "Volume: > MA 20 (OK)\n"

            # 3. Super Trend Filter
            if setup.get('enable_super_trend', False):
                if st_dir_col and st_dir_col in df.columns:
                     st_direction = last_candle[st_dir_col] # 1 or -1
                     if is_long:
                         if st_direction != 1:
                             conditions_met = False
                         else:
                             filter_msg += "Super Trend: Bullish (OK)\n"
                     elif is_short:
                         if st_direction != -1:
                             conditions_met = False
                         else:
                             filter_msg += "Super Trend: Bearish (OK)\n"
                else:
                     # If Super Trend calculation failed but filter is enabled
                     conditions_met = False
            
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
                          f"Giá: {last_candle['close']:.4f}\n" \
                          f"EMA RSI 5: {last_candle['ema_rsi_5']:.2f} | EMA RSI 10: {last_candle['ema_rsi_10']:.2f} | EMA RSI 20: {last_candle['ema_rsi_20']:.2f}\n" \
                          f"--------------------\n" \
                          f"{filter_msg}" \
                          f"--------------------\n" \
                          f"🛑 Gợi ý SL/TP: Tự xác định theo cấu trúc."
                
                send_telegram_message(message)
                write_signal_to_file(message)

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
        for config in EMA_RSI_TIMEFRAME_CONFIGS:
            timeframe = config['timeframe']
            
            for coin in top_coins:
                print(f"Đang quét {coin} trên khung {timeframe}...")
                df = get_ohlcv(coin, timeframe)
                if df is not None:
                    check_ema_rsi_signals(df, coin, timeframe)
                wait_with_interaction(1) # Tạm dừng ngắn, cho phép ngắt
            wait_with_interaction(1) # Tạm dừng giữa các config

        print(f"--- Đã hoàn thành chu kỳ quét. Chờ 30 phút cho lần quét tiếp theo ---")
        send_telegram_message("--- Đã hoàn thành chu kỳ quét. Chờ 30 phút cho lần quét tiếp theo ---")
        wait_with_interaction(1800, "Đang chờ") # Chờ 30 phút với tương tác

if __name__ == '__main__':
    main()
