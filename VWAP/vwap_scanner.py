import os
import time
import requests
import pandas as pd
import pandas_ta as ta
import ccxt
import telegram

# --- CẤU HÌNH ---
# Thay thế bằng thông tin của bạn
COINMARKETCAP_API_KEY = 'a2d1ccdd-c9b4-4e30-b3ac-c0ed36849565'
TELEGRAM_BOT_TOKEN = '6468221540:AAEYfM-Zv7ETzXrRfIyMee7ouDCIesGc9pg'
TELEGRAM_CHAT_ID = '-4090797883'  # Ví dụ: '@kenhcuaban' hoặc '-100123456789'

# Cài đặt cho việc quét
TIMEFRAMES = ['15m', '1h', '4h', '1d']  # Khung thời gian nến (ví dụ: '15m', '1h', '4h', '1d')
TOP_N_COINS = 300
LOOKBACK_CANDLES = 5 # Số lượng nến để kiểm tra tín hiệu (ví dụ: 5 cây nến gần nhất)
VWAP_TREND_WINDOW = 20 # Số phiên để tính trung bình VWAP xác định xu hướng

# Khởi tạo sàn giao dịch (sử dụng Binance làm ví dụ)
exchange = ccxt.binance()

def get_top_100_coins():
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
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
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

    # Tính toán VWAP. Pine Script sử dụng hlc3 làm nguồn mặc định.
    # Cần set index là datetime để pandas_ta tính toán đúng anchor
    # Anchor mặc định là "D" (Day/Session). Đổi sang "M" (Month) theo yêu cầu.
    df.set_index('timestamp', inplace=True, drop=False)
    df['vwap'] = ta.vwap(high=df['high'], low=df['low'], close=df['close'], volume=df['volume'], anchor='M')

    # Tính trung bình VWAP để xác định xu hướng
    df['vwap_ma'] = df['vwap'].rolling(window=VWAP_TREND_WINDOW).mean()

    # Tính toán Ichimoku Cloud
    # ta.ichimoku trả về 2 DataFrame: (Tenkan, Kijun, Chikou, Span A, Span B) và (Span A, Span B future)
    # Chúng ta cần Span A và Span B từ DataFrame đầu tiên để có dữ liệu hiện tại
    try:
        ichimoku_data, span_data = ta.ichimoku(df['high'], df['low'], df['close'])
        # Gộp ichimoku_data vào df chính
        df = pd.concat([df, ichimoku_data], axis=1)
        
        # Xác định tên cột Span A và Span B
        # Thứ tự cột trong ichimoku_data thường là: ISA, ISB, ITS, IKS, ICS
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
    # Duyệt ngược từ cây nến mới nhất về quá khứ
    for i in range(LOOKBACK_CANDLES):
        # i = 0: cây nến cuối cùng (last_candle)
        # i = 1: cây nến trước đó (prev_candle)
        
        if len(df) < (i + 2):
            break

        last_candle = df.iloc[-1 - i]
        prev_candle = df.iloc[-2 - i]

        # Bỏ qua nếu không có dữ liệu VWAP hoặc VWAP MA hoặc Ichimoku hoặc RSI EMA
        if pd.isna(last_candle['vwap']) or pd.isna(prev_candle['vwap']) or pd.isna(last_candle['vwap_ma']) or \
           pd.isna(last_candle[span_a_col]) or pd.isna(last_candle[span_b_col]) or \
           pd.isna(last_candle['ema_rsi_10']) or pd.isna(last_candle['ema_rsi_20']) or pd.isna(last_candle['ema_rsi_30']):
            continue

        # Thời gian của cây nến tín hiệu
        signal_time = last_candle['timestamp']

        # Kiểm tra dữ liệu có quá cũ không (tránh coin bị delist hoặc không có giao dịch)
        # Chuyển đổi timeframe sang giây
        tf_seconds = 0
        if timeframe.endswith('m'):
            tf_seconds = int(timeframe[:-1]) * 60
        elif timeframe.endswith('h'):
            tf_seconds = int(timeframe[:-1]) * 3600
        elif timeframe.endswith('d'):
            tf_seconds = int(timeframe[:-1]) * 86400
        
        # Nếu nến cuối cùng cũ hơn LOOKBACK_CANDLES lần khung thời gian thì bỏ qua
        if (pd.Timestamp.now() - signal_time).total_seconds() > (tf_seconds * LOOKBACK_CANDLES):
            continue

        # --- Logic phát hiện giao cắt ---
        # Giao cắt lên (Bullish Crossover)
        # Điều kiện thêm: VWAP hiện tại > VWAP MA (Xu hướng tăng)
        # Điều kiện Ichimoku: VWAP > Span A và VWAP > Span B
        # Điều kiện nến: Open < VWAP và Close > VWAP (Nến xanh cắt lên)
        # Điều kiện RSI EMA: EMA10 > EMA20 > EMA30
        if prev_candle['close'] < prev_candle['vwap'] and last_candle['close'] > last_candle['vwap'] and last_candle['open'] < last_candle['vwap']:
            if last_candle['vwap'] > last_candle['vwap_ma']:
                if last_candle['vwap'] > last_candle[span_a_col] and last_candle['vwap'] > last_candle[span_b_col]:
                    if last_candle['ema_rsi_10'] > last_candle['ema_rsi_20'] > last_candle['ema_rsi_30']:
                        message = f"🚀 TÍN HIỆU BULLISH: {symbol} trên khung {timeframe}\n" \
                                  f"Thời gian: {signal_time}\n" \
                                  f"Cách đây: {i} nến\n" \
                                  f"Giá vừa CẮT LÊN trên đường VWAP.\n" \
                                  f"Xu hướng VWAP: TĂNG (VWAP > MA{VWAP_TREND_WINDOW})\n" \
                                  f"Ichimoku: VWAP nằm TRÊN Mây (Span A, B)\n" \
                                  f"RSI EMA: 10 > 20 > 30 (Tăng)\n" \
                                  f"Giá đóng cửa: {last_candle['close']:.4f}\n" \
                                  f"VWAP: {last_candle['vwap']:.4f}"
                        send_telegram_message(message)
                        write_signal_to_file(message)

        # Giao cắt xuống (Bearish Crossover)
        # Điều kiện thêm: VWAP hiện tại < VWAP MA (Xu hướng giảm)
        # Điều kiện Ichimoku: VWAP < Span A và VWAP < Span B
        # Điều kiện nến: Open > VWAP và Close < VWAP (Nến đỏ cắt xuống)
        # Điều kiện RSI EMA: EMA10 < EMA20 < EMA30
        if prev_candle['close'] > prev_candle['vwap'] and last_candle['close'] < last_candle['vwap'] and last_candle['open'] > last_candle['vwap']:
            if last_candle['vwap'] < last_candle['vwap_ma']:
                if last_candle['vwap'] < last_candle[span_a_col] and last_candle['vwap'] < last_candle[span_b_col]:
                    if last_candle['ema_rsi_10'] < last_candle['ema_rsi_20'] < last_candle['ema_rsi_30']:
                        message = f"🔻 TÍN HIỆU BEARISH: {symbol} trên khung {timeframe}\n" \
                                  f"Thời gian: {signal_time}\n" \
                                  f"Cách đây: {i} nến\n" \
                                  f"Giá vừa CẮT XUỐNG dưới đường VWAP.\n" \
                                  f"Xu hướng VWAP: GIẢM (VWAP < MA{VWAP_TREND_WINDOW})\n" \
                                  f"Ichimoku: VWAP nằm DƯỚI Mây (Span A, B)\n" \
                                  f"RSI EMA: 10 < 20 < 30 (Giảm)\n" \
                                  f"Giá đóng cửa: {last_candle['close']:.4f}\n" \
                                  f"VWAP: {last_candle['vwap']:.4f}"
                        send_telegram_message(message)
                        write_signal_to_file(message)

def main():
    """Hàm chính để chạy máy quét."""
    print("--- Bắt đầu máy quét tín hiệu VWAP ---")
    top_coins = get_top_100_coins()

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