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
    SONICR_TELEGRAM_CHAT_ID,
    USE_FIXED_LIST,
    TOP_N_COINS,
    LOOKBACK_CANDLES,
    SUPER_TREND_LENGTH,
    SUPER_TREND_MULTIPLIER,
    SONICR_TIMEFRAME_CONFIGS,
    SONICR_SETUP_CONFIGS,
    SONICR_SIGNAL_WINDOW
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
            # Lọc các cặp giao dịch có sẵn trên Bybit/Binance với USDT
            symbols = [f"{coin['symbol']}/USDT" for coin in data['data']]
            markets = exchange.load_markets()
            available_symbols = [s for s in symbols if s in markets]
            print(f"Đã tìm thấy {len(available_symbols)}/{TOP_N_COINS} cặp giao dịch có sẵn trên sàn với USDT.")
            return available_symbols
    except Exception as e:
        print(f"Lỗi khi lấy danh sách tiền điện tử: {e}")
    return []

def get_ohlcv(symbol, timeframe):
    """Lấy dữ liệu OHLCV cho một cặp giao dịch."""
    try:
        # Tải dữ liệu nến
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
            await bot.send_message(chat_id=SONICR_TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
        
        asyncio.run(_send())
        print(f"Đã gửi thông báo:\n{message}")
    except Exception as e:
        print(f"Lỗi khi gửi tin nhắn Telegram: {e}")

def write_signal_to_file(message):
    """Ghi thông báo tín hiệu vào file text."""
    try:
        os.makedirs('output', exist_ok=True)
        with open('output/sonicr_signal.txt', 'a', encoding='utf-8') as f:
            f.write(f"{pd.Timestamp.now()} - {message}\n" + "-"*50 + "\n")
        print("Đã ghi tín hiệu vào file output/sonicr_signal.txt")
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
        print() 

def check_sonicr_signals(df, symbol, timeframe, htf_df=None):
    """Kiểm tra tín hiệu Sonic R và trả về danh sách tín hiệu tìm được."""
    signals_found = []
    if df is None or len(df) < 610:
        return signals_found

    # Tính toán HTF Super Trend nếu được truyền vào
    htf_st_dir = None
    if htf_df is not None and not htf_df.empty:
        try:
            htf_sti = ta.supertrend(htf_df['high'], htf_df['low'], htf_df['close'], length=SUPER_TREND_LENGTH, multiplier=SUPER_TREND_MULTIPLIER)
            if htf_sti is not None and not htf_sti.empty:
                htf_df = pd.concat([htf_df, htf_sti], axis=1)
                st_dir_col_htf = f"SUPERTd_{SUPER_TREND_LENGTH}_{SUPER_TREND_MULTIPLIER}"
                if st_dir_col_htf not in htf_df.columns:
                     cols = [c for c in htf_df.columns if c.startswith('SUPERTd_')]
                     if cols: st_dir_col_htf = cols[0]
                
                if st_dir_col_htf in htf_df.columns:
                    htf_st_dir = htf_df.iloc[-1][st_dir_col_htf]
        except Exception:
            pass

    # Tính toán EMA Close
    try:
        df['ema_rsi_34'] = ta.ema(df['close'], length=34)
        df['ema_rsi_89'] = ta.ema(df['close'], length=89)
        df['ema_rsi_200'] = ta.ema(df['close'], length=200)
        df['ema_rsi_610'] = ta.ema(df['close'], length=610)
    except Exception as e:
        # print(f"Lỗi tính EMA cho {symbol}: {e}")
        return []

    # Tính Volume MA 20
    try:
        df['vol_ma_20'] = df['volume'].rolling(window=20).mean()
    except:
        pass

    # Tính toán Ichimoku Cloud
    try:
        ichimoku_data, span_data = ta.ichimoku(df['high'], df['low'], df['close'])
        df = pd.concat([df, ichimoku_data], axis=1)
        span_a_col = ichimoku_data.columns[0] 
        span_b_col = ichimoku_data.columns[1] 
    except Exception as e:
        span_a_col = span_b_col = None

    # Tính toán Super Trend
    try:
        sti = ta.supertrend(df['high'], df['low'], df['close'], length=SUPER_TREND_LENGTH, multiplier=SUPER_TREND_MULTIPLIER)
        if sti is not None and not sti.empty:
            df = pd.concat([df, sti], axis=1)
            st_dir_col = f"SUPERTd_{SUPER_TREND_LENGTH}_{SUPER_TREND_MULTIPLIER}"
            if st_dir_col not in df.columns:
                 cols = [c for c in df.columns if c.startswith('SUPERTd_')]
                 if cols: st_dir_col = cols[0]
        else:
            st_dir_col = None
    except Exception as e:
        st_dir_col = None

    # Lấy N cây nến cuối cùng để kiểm tra
    for i in range(LOOKBACK_CANDLES):
        if len(df) < (i + 2):
            break

        # Index của nến hiện tại (đang xét)
        curr_idx = -1 - i
        last_candle = df.iloc[curr_idx]

        # Bỏ qua nếu thiếu dữ liệu
        if pd.isna(last_candle['ema_rsi_34']) or pd.isna(last_candle['ema_rsi_89']) or \
           pd.isna(last_candle['ema_rsi_200']) or pd.isna(last_candle['ema_rsi_610']):
            continue

        if span_a_col and span_b_col and (pd.isna(last_candle[span_a_col]) or pd.isna(last_candle[span_b_col])):
            continue

        signal_time = last_candle['timestamp']

        # Kiểm tra thời gian
        tf_seconds = 0
        if timeframe.endswith('m'): tf_seconds = int(timeframe[:-1]) * 60
        elif timeframe.endswith('h'): tf_seconds = int(timeframe[:-1]) * 3600
        elif timeframe.endswith('d'): tf_seconds = int(timeframe[:-1]) * 86400
        elif timeframe.endswith('w'): tf_seconds = int(timeframe[:-1]) * 604800
        
        if (pd.Timestamp.utcnow().tz_localize(None) - signal_time).total_seconds() > (tf_seconds * LOOKBACK_CANDLES):
            continue

        # Duyệt qua từng Setup trong Configuration
        for setup in SONICR_SETUP_CONFIGS:
            if not setup.get('enabled', True):
                continue

            # Logic phát hiện tín hiệu Sonic R (Window-based)
            is_long = False
            is_short = False
            reversal_dist = -1
            
            c = last_candle['close']
            e34 = last_candle['ema_rsi_34']
            e89 = last_candle['ema_rsi_89']
            e200 = last_candle['ema_rsi_200']
            e610 = last_candle['ema_rsi_610']

            # Trạng thái hiện tại
            curr_long_state = (c > e34 and e34 > e89 and e89 > e200 and e200 > e610)
            curr_short_state = (c < e34 and e34 < e89 and e89 < e200 and e200 < e610)

            if setup['signal_type'] == 'LONG':
                if curr_long_state:
                    # Tìm điểm đảo chiều gần nhất trong cửa sổ
                    for k in range(SONICR_SIGNAL_WINDOW):
                        target_idx = curr_idx - k
                        prev_target_idx = target_idx - 1
                        if abs(prev_target_idx) > len(df): break
                        
                        k_candle = df.iloc[target_idx]
                        k_prev_candle = df.iloc[prev_target_idx]
                        
                        kc = k_candle['close']
                        k34 = k_candle['ema_rsi_34']
                        k89 = k_candle['ema_rsi_89']
                        k200 = k_candle['ema_rsi_200']
                        k610 = k_candle['ema_rsi_610']

                        k_is_long = (kc > k34 and k34 > k89 and k89 > k200 and k200 > k610)

                        kpc = k_prev_candle['close']
                        kp34 = k_prev_candle['ema_rsi_34']
                        kp89 = k_prev_candle['ema_rsi_89']
                        kp200 = k_prev_candle['ema_rsi_200']
                        kp610 = k_prev_candle['ema_rsi_610']

                        k_prev_is_long = (kpc > kp34 and kp34 > kp89 and kp89 > kp200 and kp200 > kp610)
                        
                        if k_is_long and not k_prev_is_long:
                            reversal_dist = k
                            is_long = True
                            break
                        if not k_is_long: break
            elif setup['signal_type'] == 'SHORT':
                if curr_short_state:
                    for k in range(SONICR_SIGNAL_WINDOW):
                        target_idx = curr_idx - k
                        prev_target_idx = target_idx - 1
                        if abs(prev_target_idx) > len(df): break
                        
                        k_candle = df.iloc[target_idx]
                        k_prev_candle = df.iloc[prev_target_idx]
                        
                        kc = k_candle['close']
                        k34 = k_candle['ema_rsi_34']
                        k89 = k_candle['ema_rsi_89']
                        k200 = k_candle['ema_rsi_200']
                        k610 = k_candle['ema_rsi_610']

                        k_is_short = (kc < k34 and k34 < k89 and k89 < k200 and k200 < k610)

                        kpc = k_prev_candle['close']
                        kp34 = k_prev_candle['ema_rsi_34']
                        kp89 = k_prev_candle['ema_rsi_89']
                        kp200 = k_prev_candle['ema_rsi_200']
                        kp610 = k_prev_candle['ema_rsi_610']

                        k_prev_is_short = (kpc < kp34 and kp34 < kp89 and kp89 < kp200 and kp200 < kp610)
                        
                        if k_is_short and not k_prev_is_short:
                            reversal_dist = k
                            is_short = True
                            break
                        if not k_is_short: break

            if not is_long and not is_short:
                continue
            
            # --- Kiểm tra Filter ---
            conditions_met = True
            win_indices = [curr_idx - x for x in range(reversal_dist + 1)]

            # 1. Ichimoku Filter
            if conditions_met and setup.get('enable_ichimoku', False) and span_b_col:
                ichi_ok = False
                for idx_w in win_indices:
                    c_w = df.iloc[idx_w]
                    if is_long and c_w['close'] > c_w[span_b_col]: ichi_ok = True; break
                    if is_short and c_w['close'] < c_w[span_b_col]: ichi_ok = True; break
                if not ichi_ok: conditions_met = False

            # 2. Volume Filter
            if conditions_met and setup.get('enable_volume_filter', False):
                vol_ok = False
                for idx_w in win_indices:
                    c_w = df.iloc[idx_w]
                    if 'vol_ma_20' in df.columns and pd.notna(c_w['vol_ma_20']):
                        if c_w['volume'] > c_w['vol_ma_20']: vol_ok = True; break
                if not vol_ok: conditions_met = False

            # 3. Super Trend Filter
            if conditions_met and setup.get('enable_super_trend', False):
                st_ok = False
                for idx_w in win_indices:
                    c_w = df.iloc[idx_w]
                    if st_dir_col and st_dir_col in df.columns:
                        if is_long and c_w[st_dir_col] == 1: st_ok = True; break
                        if is_short and c_w[st_dir_col] == -1: st_ok = True; break
                if not st_ok: conditions_met = False

            # 4. HTF Super Trend Filter
            if conditions_met and setup.get('enable_htf_super_trend', False):
                if htf_st_dir is not None:
                    if is_long and htf_st_dir != 1: conditions_met = False
                    if is_short and htf_st_dir != -1: conditions_met = False
                else:
                    conditions_met = False

            if not conditions_met:
                continue
            
            # Tính khoảng cách nến từ lần cắt nhau gần nhất của EMA200 và EMA610
            cross_distance = -1
            curr_pos = len(df) + curr_idx
            for j in range(curr_pos, 0, -1):
                c_j = df.iloc[j]
                c_prev = df.iloc[j - 1]
                
                # Cắt lên (EMA200 > EMA610) hoặc Cắt xuống (EMA200 < EMA610)
                if pd.notna(c_prev['ema_rsi_610']):
                    if (c_j['ema_rsi_200'] > c_j['ema_rsi_610'] and c_prev['ema_rsi_200'] <= c_prev['ema_rsi_610']) or \
                       (c_j['ema_rsi_200'] < c_j['ema_rsi_610'] and c_prev['ema_rsi_200'] >= c_prev['ema_rsi_610']):
                        cross_distance = curr_pos - j
                        break
            
            if cross_distance == -1:
                cross_distance = 9999
            
            # Kiểm tra Max Cross Ago
            max_cross_ago = setup.get('max_cross_ago', 0)
            if max_cross_ago > 0 and cross_distance > max_cross_ago:
                continue

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
                'ema_rsi_34': e34,
                'ema_rsi_89': e89,
                'ema_rsi_200': e200,
                'ema_rsi_610': e610,
                'setup_name': setup['name'],
                'icon': icon,
                'candles_ago': i,
                'reversal_dist': reversal_dist,
                'cross_distance': cross_distance
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
    msg_lines.append(f"🎯 *SONICR SIGNALS* - {pd.Timestamp.now(tz='Asia/Ho_Chi_Minh').strftime('%H:%M')}")
    msg_lines.append("```")
    msg_lines.append(f"{'Name':<8} {'TF':<4} {'Type':<6} {'Price':<9} {'E34':<6} {'E89':<6} {'E200':<6} {'E610':<6} {'CrossAgo':<8}")
    msg_lines.append("-" * 69)

    for sig in signals:
        # Rút gọn symbol (e.g., BTC/USDT -> BTC)
        name = sig['symbol'].split('/')[0]
        tf = sig['timeframe']
        type_str = sig['type']
        price = sig['price']
        
        # Price formatting matching Bybit
        p_str = f"${price:.4f}" if price < 100 else f"${price:.2f}"
        
        # EMA values
        e34_str = f"{sig['ema_rsi_34']:.2f}" if sig['ema_rsi_34'] < 100 else f"{sig['ema_rsi_34']:.0f}"
        e89_str = f"{sig['ema_rsi_89']:.2f}" if sig['ema_rsi_89'] < 100 else f"{sig['ema_rsi_89']:.0f}"
        e200_str = f"{sig['ema_rsi_200']:.2f}" if sig['ema_rsi_200'] < 100 else f"{sig['ema_rsi_200']:.0f}"
        e610_str = f"{sig['ema_rsi_610']:.2f}" if sig['ema_rsi_610'] < 100 else f"{sig['ema_rsi_610']:.0f}"
        
        # Cross Distance
        cross_str = f"{sig['cross_distance']}n"
        
        row_str = f"{name:<8} {tf:<4} {type_str:<6} {p_str:<9} {e34_str:<6} {e89_str:<6} {e200_str:<6} {e610_str:<6} {cross_str:<8}"
        msg_lines.append(row_str)

    msg_lines.append("```")
    
    full_message = "\n".join(msg_lines)
    send_telegram_message(full_message)

def main():
    """Hàm chính để chạy máy quét Sonic R."""
    print("--- Bắt đầu máy quét tín hiệu Sonic R ---")
    send_telegram_message("--- Bắt đầu máy quét tín hiệu Sonic R ---")
    top_coins = get_target_coins()

    if not top_coins:
        print("Không thể lấy danh sách tiền điện tử. Thoát.")
        return

    while True:
        print("\n--- Bắt đầu chu kỳ quét mới ---")
        send_telegram_message("--- Bắt đầu chu kỳ quét mới ---")
        all_signals = []
        for config in SONICR_TIMEFRAME_CONFIGS:
            timeframe = config['timeframe']
            htf = config.get('htf')
            
            for coin in top_coins:
                print(f"Đang quét {coin} trên khung {timeframe}...")
                df = get_ohlcv(coin, timeframe)
                
                htf_df = None
                if htf and df is not None:
                    if any(s.get('enable_htf_super_trend') for s in SONICR_SETUP_CONFIGS if s.get('enabled', True)):
                        htf_df = get_ohlcv(coin, htf)

                if df is not None:
                    found = check_sonicr_signals(df, coin, timeframe, htf_df)
                    if found:
                        all_signals.extend(found)
                wait_with_interaction(0.1) # Tạm dừng ngắn
            
        if all_signals:
            print(f"Đã tìm thấy {len(all_signals)} tín hiệu. Gửi Telegram...")
            send_aggregated_signals(all_signals)
        else:
            print("Không có tín hiệu mới.")
            send_telegram_message("--- Không có tín hiệu mới ---")

        print(f"--- Đã hoàn thành chu kỳ quét. Chờ 30 phút cho lần quét tiếp theo ---")
        wait_with_interaction(1800, "Đang chờ") # Chờ 30 phút với tương tác

if __name__ == '__main__':
    main()
