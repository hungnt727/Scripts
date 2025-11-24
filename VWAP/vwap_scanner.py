import os
import time
import requests
import pandas as pd
import numpy as np
import pandas_ta as ta
import ccxt
import telegram
import asyncio

# --- CẤU HÌNH ---
# Thay thế bằng thông tin của bạn
COINMARKETCAP_API_KEY = 'a2d1ccdd-c9b4-4e30-b3ac-c0ed36849565'
TELEGRAM_BOT_TOKEN = '6468221540:AAEYfM-Zv7ETzXrRfIyMee7ouDCIesGc9pg'
TELEGRAM_CHAT_ID = '-4054954598'  # Ví dụ: '@kenhcuaban' hoặc '-100123456789'

# Cài đặt cho việc quét
# TIMEFRAMES = ['5m', '15m', '1h', '4h', '1d']  # Khung thời gian nến (ví dụ: '15m', '1h', '4h', '1d')
TIMEFRAMES = ['15m','1h', '4h', '1d'] 
USE_FIXED_LIST = False # True: Chạy danh sách cố định, False: Chạy Top N CoinMarketCap
FIXED_SYMBOLS = [
    'APE/USDT'
#    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
#    'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'TRX/USDT', 'DOT/USDT',
#   'LINK/USDT', 'MATIC/USDT', 'LTC/USDT', 'BCH/USDT', 'ATOM/USDT'
]
TOP_N_COINS = 300
LOOKBACK_CANDLES = 5 # Số lượng nến để kiểm tra tín hiệu (ví dụ: 5 cây nến gần nhất)
VWAP_TREND_WINDOW = 10 # Số phiên để tính trung bình VWAP xác định xu hướng
VWAP_MIN_FROM_BEGIN = 10 # Số phiên tối thiểu bắt đầu mỗi chu kỳ
VWAP_BAND_MULTIPLIER = 1.0 # Hệ số nhân cho dải băng VWAP (Stdev)
VWAP_TP_BAND_MULTIPLIER = 2.0 # Hệ số nhân cho TP (Band 2)
VWAP_BAND_LOOKBACK = 20 # Số nến nhìn lại để kiểm tra giao cắt với dải băng

# Cờ bật/tắt các điều kiện lọc
ENABLE_VWAP_TREND = True  # Bật/tắt điều kiện xu hướng VWAP (VWAP > MA hoặc VWAP < MA)
ENABLE_RSI_EMA = True     # Bật/tắt điều kiện RSI EMA (EMA10 > EMA20 > EMA30)
ENABLE_ICHIMOKU = True    # Bật/tắt điều kiện Ichimoku Cloud (Close so với Span A, B)
ENABLE_EMA_TREND = True    # Bật/tắt điều kiện xu hướng EMA 200
ENABLE_VOLUME_FILTER = True # Bật/tắt điều kiện Volume > Avg 20
ENABLE_BAND_TOUCH = False


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
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        
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

def check_vwap_crossover(df, symbol, timeframe):
    """Kiểm tra sự giao cắt của nến với đường VWAP và gửi thông báo."""
    if df is None or len(df) < 2:
        return

    # --- Tính toán VWAP và Bands thủ công ---
    # Tính Typical Price
    df['tp'] = (df['high'] + df['low'] + df['close']) / 3
    df['tp_v'] = df['tp'] * df['volume']
    df['tp_sq_v'] = (df['tp'] ** 2) * df['volume']

    # Xác định nhóm Anchor
    if timeframe.endswith('d') or timeframe.endswith('w'):
        # Anchor theo tháng cho khung D trở lên
        grouper = df['timestamp'].dt.to_period('M')
    else:
        # Anchor theo tuần cho khung H trở xuống
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

    # Tính trung bình VWAP để xác định xu hướng
    df['vwap_ma'] = df['vwap'].rolling(window=VWAP_TREND_WINDOW).mean()
    
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
        df['ema_rsi_10'] = ta.ema(df['rsi'], length=10)
        df['ema_rsi_20'] = ta.ema(df['rsi'], length=20)
        df['ema_rsi_30'] = ta.ema(df['rsi'], length=30)
    except Exception as e:
        # print(f"Lỗi tính RSI/EMA cho {symbol}: {e}")
        return

    # Lấy N cây nến cuối cùng để kiểm tra
    for i in range(LOOKBACK_CANDLES):
        if len(df) < (i + 2 + VWAP_BAND_LOOKBACK):
            break

        # Index của nến hiện tại (đang xét)
        curr_idx = -1 - i
        prev_idx = -2 - i
        
        last_candle = df.iloc[curr_idx]
        prev_candle = df.iloc[prev_idx]

        # Bỏ qua nếu thiếu dữ liệu
        if pd.isna(last_candle['vwap']) or pd.isna(prev_candle['vwap']) or pd.isna(last_candle['vwap_ma']) or \
           pd.isna(last_candle[span_a_col]) or pd.isna(last_candle[span_b_col]) or \
           pd.isna(last_candle['ema_rsi_10']) or pd.isna(last_candle['ema_rsi_20']) or pd.isna(last_candle['ema_rsi_30']):
            continue

        signal_time = last_candle['timestamp']

        # Kiểm tra thời gian
        tf_seconds = 0
        if timeframe.endswith('m'): tf_seconds = int(timeframe[:-1]) * 60
        elif timeframe.endswith('h'): tf_seconds = int(timeframe[:-1]) * 3600
        elif timeframe.endswith('d'): tf_seconds = int(timeframe[:-1]) * 86400
        
        if (pd.Timestamp.utcnow().tz_localize(None) - signal_time).total_seconds() > (tf_seconds * LOOKBACK_CANDLES):
            continue

        # --- Logic phát hiện giao cắt ---
        
        # Giao cắt lên (Bullish)
        if prev_candle['close'] < prev_candle['vwap'] and last_candle['close'] > last_candle['vwap'] and last_candle['open'] < last_candle['vwap']:
            # Kiểm tra điều kiện Band: Có nến nào chạm/cắt Lower Band 1 trong 20 nến gần nhất không?
            start_pos = len(df) + curr_idx - VWAP_BAND_LOOKBACK + 1
            end_pos = len(df) + curr_idx + 1
            
            recent_lows = df['low'].iloc[start_pos:end_pos]
            recent_lower_bands = df['lower_band_1'].iloc[start_pos:end_pos]
            
            # Điều kiện: Low <= Lower Band
            band_touch_ok = True    
            if ENABLE_BAND_TOUCH: band_touch_ok = (recent_lows <= recent_lower_bands).any()

            vwap_trend_ok = True
            if ENABLE_VWAP_TREND: vwap_trend_ok = last_candle['vwap'] > last_candle['vwap_ma']
            
            ichimoku_ok = True
            #if ENABLE_ICHIMOKU: ichimoku_ok = last_candle['close'] > last_candle[span_a_col] and last_candle['close'] > last_candle[span_b_col]
            if ENABLE_ICHIMOKU: ichimoku_ok = last_candle['close'] > last_candle[span_b_col]
            
            rsi_ema_ok = True
            if ENABLE_RSI_EMA: rsi_ema_ok = last_candle['ema_rsi_10'] > last_candle['ema_rsi_20'] > last_candle['ema_rsi_30']
            
            # New Filters: Trend (EMA 200) & Volume
            trend_ok = True
            if ENABLE_EMA_TREND and 'ema_200' in df.columns and pd.notna(last_candle['ema_200']):
                trend_ok = last_candle['close'] > last_candle['ema_200']
            
            volume_ok = True
            if ENABLE_VOLUME_FILTER and 'vol_ma_20' in df.columns and pd.notna(last_candle['vol_ma_20']):
                volume_ok = last_candle['volume'] > last_candle['vol_ma_20']
            
            anchor_ok = last_candle['anchor_idx'] >= VWAP_MIN_FROM_BEGIN

            if vwap_trend_ok and ichimoku_ok and rsi_ema_ok and band_touch_ok and trend_ok and volume_ok and anchor_ok:
                
                # Convert signal_time to local time (Asia/Ho_Chi_Minh)
                try:
                    local_signal_time = signal_time.tz_localize('UTC').tz_convert('Asia/Ho_Chi_Minh')
                except Exception:
                    local_signal_time = signal_time + pd.Timedelta(hours=7)

                message = f"🚀 TÍN HIỆU BULLISH: {symbol} trên khung {timeframe}\n" \
                          f"Thời gian: {local_signal_time.strftime('%Y-%m-%d %H:%M:%S')}\n" \
                          f"Cách đây: {i} nến\n" \
                          f"Anchor Index: {last_candle['anchor_idx']}\n" \
                          f"Giá vừa CẮT LÊN trên đường VWAP.\n"
                
                if ENABLE_VWAP_TREND: message += f"Xu hướng VWAP: TĂNG (VWAP > MA{VWAP_TREND_WINDOW})\n"
                if ENABLE_ICHIMOKU: message += f"Ichimoku: Giá TRÊN Mây (Close > Span A, B)\n"
                if ENABLE_RSI_EMA: message += f"RSI EMA: 10 > 20 > 30 (Tăng)\n"
                if ENABLE_EMA_TREND: message += f"EMA 200: Giá > EMA 200 (Uptrend)\n"
                if ENABLE_VOLUME_FILTER: message += f"Volume: Cao hơn TB 20 phiên\n"
                
                message += f"Band Condition: Đã chạm Lower Band 1 trong {VWAP_BAND_LOOKBACK} nến\n"
                
                message += f"Giá đóng cửa: {last_candle['close']:.4f}\n" \
                           f"VWAP: {last_candle['vwap']:.4f}\n" \
                           f"VWAP MA: {last_candle['vwap_ma']:.4f}\n" \
                           f"VWAP/VWAP MA: {((last_candle['vwap'] / last_candle['vwap_ma']) * 100):.2f}%\n" \
                           f"🎯 Gợi ý TP: {last_candle['upper_band_2']:.4f} (Band 2)\n" \
                           f"🛑 Gợi ý SL: Đóng nến dưới VWAP ({last_candle['vwap']:.4f})"
                
                send_telegram_message(message)
                write_signal_to_file(message)

        # Giao cắt xuống (Bearish)
        if prev_candle['close'] > prev_candle['vwap'] and last_candle['close'] < last_candle['vwap'] and last_candle['open'] > last_candle['vwap']:
            # Kiểm tra điều kiện Band: Có nến nào chạm/cắt Upper Band 1 trong 20 nến gần nhất không?
            start_pos = len(df) + curr_idx - VWAP_BAND_LOOKBACK + 1
            end_pos = len(df) + curr_idx + 1
            
            recent_highs = df['high'].iloc[start_pos:end_pos]
            recent_upper_bands = df['upper_band_1'].iloc[start_pos:end_pos]
            
            # Điều kiện: High >= Upper Band
            band_touch_ok = True    
            if ENABLE_BAND_TOUCH: band_touch_ok = (recent_highs >= recent_upper_bands).any()

            vwap_trend_ok = True
            if ENABLE_VWAP_TREND: vwap_trend_ok = last_candle['vwap'] < last_candle['vwap_ma']
            
            ichimoku_ok = True
            #if ENABLE_ICHIMOKU: ichimoku_ok = last_candle['close'] < last_candle[span_a_col] and last_candle['close'] < last_candle[span_b_col]
            if ENABLE_ICHIMOKU: ichimoku_ok = last_candle['close'] < last_candle[span_b_col]
            
            rsi_ema_ok = True
            if ENABLE_RSI_EMA: rsi_ema_ok = last_candle['ema_rsi_10'] < last_candle['ema_rsi_20'] < last_candle['ema_rsi_30']
            
            # New Filters: Trend (EMA 200) & Volume
            trend_ok = True
            if ENABLE_EMA_TREND and 'ema_200' in df.columns and pd.notna(last_candle['ema_200']):
                trend_ok = last_candle['close'] < last_candle['ema_200']
            
            volume_ok = True
            if ENABLE_VOLUME_FILTER and 'vol_ma_20' in df.columns and pd.notna(last_candle['vol_ma_20']):
                volume_ok = last_candle['volume'] > last_candle['vol_ma_20']
            
            anchor_ok = last_candle['anchor_idx'] >= VWAP_MIN_FROM_BEGIN

            if vwap_trend_ok and ichimoku_ok and rsi_ema_ok and band_touch_ok and trend_ok and volume_ok and anchor_ok:
                
                # Convert signal_time to local time (Asia/Ho_Chi_Minh)
                try:
                    local_signal_time = signal_time.tz_localize('UTC').tz_convert('Asia/Ho_Chi_Minh')
                except Exception:
                    local_signal_time = signal_time + pd.Timedelta(hours=7)

                message = f"🔻 TÍN HIỆU BEARISH: {symbol} trên khung {timeframe}\n" \
                          f"Thời gian: {local_signal_time.strftime('%Y-%m-%d %H:%M:%S')}\n" \
                          f"Cách đây: {i} nến\n" \
                          f"Anchor Index: {last_candle['anchor_idx']}\n" \
                          f"Giá vừa CẮT XUỐNG dưới đường VWAP.\n"
                
                if ENABLE_VWAP_TREND: message += f"Xu hướng VWAP: GIẢM (VWAP < MA{VWAP_TREND_WINDOW})\n"
                if ENABLE_ICHIMOKU: message += f"Ichimoku: Giá DƯỚI Mây (Close < Span A, B)\n"
                if ENABLE_RSI_EMA: message += f"RSI EMA: 10 < 20 < 30 (Giảm)\n"
                if ENABLE_EMA_TREND: message += f"EMA 200: Giá < EMA 200 (Downtrend)\n"
                if ENABLE_VOLUME_FILTER: message += f"Volume: Cao hơn TB 20 phiên\n"
                
                message += f"Band Condition: Đã chạm Upper Band 1 trong {VWAP_BAND_LOOKBACK} nến\n"
                
                message += f"Giá đóng cửa: {last_candle['close']:.4f}\n" \
                           f"VWAP: {last_candle['vwap']:.4f}\n" \
                           f"VWAP MA: {last_candle['vwap_ma']:.4f}\n" \
                           f"VWAP/VWAP MA: {((last_candle['vwap'] / last_candle['vwap_ma']) * 100):.2f}%\n" \
                           f"🎯 Gợi ý TP: {last_candle['lower_band_2']:.4f} (Band 2)\n" \
                           f"🛑 Gợi ý SL: Đóng nến trên VWAP ({last_candle['vwap']:.4f})"
                
                send_telegram_message(message)
                write_signal_to_file(message)

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
        for timeframe in TIMEFRAMES:
            for coin in top_coins:
                print(f"Đang quét {coin} trên khung {timeframe}...")
                df = get_ohlcv(coin, timeframe)
                if df is not None:
                    check_vwap_crossover(df, coin, timeframe)
                time.sleep(1) # Tạm dừng ngắn
            time.sleep(1) # Tạm dừng giữa các coin

        print(f"--- Đã hoàn thành chu kỳ quét. Chờ 30 phút cho lần quét tiếp theo ---")
        time.sleep(1800) # Chờ 30 phút

if __name__ == '__main__':
    main()