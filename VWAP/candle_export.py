# -*- coding: utf-8 -*-
import pandas as pd
import pandas_ta as ta
import ccxt
from datetime import datetime
import sys
import io

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Khởi tạo sàn giao dịch - Bybit Futures
exchange = ccxt.bybit({
    'options': {
        'defaultType': 'linear',  # USDT Perpetual
    }
})

def export_recent_candles(symbol, timeframe, num_candles=10):
    """
    Xuất thông tin của N cây nến gần đây nhất cho một cặp giao dịch.
    
    Parameters:
    -----------
    symbol : str
        Cặp giao dịch (ví dụ: 'BTC/USDT')
    timeframe : str
        Khung thời gian (ví dụ: '1h', '4h', '1d')
    num_candles : int
        Số lượng nến cần xuất (mặc định: 10)
    
    Returns:
    --------
    pandas.DataFrame
        DataFrame chứa thông tin các nến
    """
    try:
        # Lấy dữ liệu OHLCV (cần thêm dữ liệu để tính EMA RSI)
        # Cần ít nhất 50 nến để tính RSI và EMA chính xác
        limit = max(num_candles + 50, 100)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        if not ohlcv or len(ohlcv) < num_candles:
            print(f"Không đủ dữ liệu cho {symbol}")
            return None
        
        # Tạo DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Tính RSI
        df['rsi'] = ta.rsi(df['close'], length=14)
        
        # Tính EMA của RSI
        df['ema_rsi_5'] = ta.ema(df['rsi'], length=5)
        df['ema_rsi_10'] = ta.ema(df['rsi'], length=10)
        df['ema_rsi_20'] = ta.ema(df['rsi'], length=20)
        df['ema_rsi_30'] = ta.ema(df['rsi'], length=30)
        
        # Lấy N nến gần nhất
        recent_candles = df.tail(num_candles).copy()
        
        # Chọn và sắp xếp lại các cột theo yêu cầu
        result = recent_candles[[
            'timestamp',
            'volume',
            'open',
            'close',
            'high',
            'low',
            'ema_rsi_5',
            'ema_rsi_10',
            'ema_rsi_20',
            'ema_rsi_30'
        ]].copy()
        
        # Đổi tên cột timestamp thành time cho dễ đọc
        result.rename(columns={'timestamp': 'time'}, inplace=True)
        
        # Reset index để dễ đọc
        result.reset_index(drop=True, inplace=True)
        
        return result
        
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu cho {symbol}: {e}")
        return None


def print_candles(symbol, timeframe, num_candles=10):
    """
    In ra thông tin các nến gần đây nhất.
    
    Parameters:
    -----------
    symbol : str
        Cặp giao dịch (ví dụ: 'BTC/USDT')
    timeframe : str
        Khung thời gian (ví dụ: '1h', '4h', '1d')
    num_candles : int
        Số lượng nến cần xuất (mặc định: 10)
    """
    print(f"\n{'='*120}")
    print(f"THÔNG TIN {num_candles} CÂY NẾN GẦN NHẤT - {symbol} ({timeframe})")
    print(f"{'='*120}\n")
    
    df = export_recent_candles(symbol, timeframe, num_candles)
    
    if df is None:
        print("Không thể lấy dữ liệu.")
        return
    
    # Hiển thị với format đẹp
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)
    
    # Format các cột số
    df_display = df.copy()
    df_display['time'] = df_display['time'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df_display['volume'] = df_display['volume'].apply(lambda x: f"{x:,.2f}")
    df_display['open'] = df_display['open'].apply(lambda x: f"{x:.4f}")
    df_display['close'] = df_display['close'].apply(lambda x: f"{x:.4f}")
    df_display['high'] = df_display['high'].apply(lambda x: f"{x:.4f}")
    df_display['low'] = df_display['low'].apply(lambda x: f"{x:.4f}")
    df_display['ema_rsi_5'] = df_display['ema_rsi_5'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
    df_display['ema_rsi_10'] = df_display['ema_rsi_10'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
    df_display['ema_rsi_20'] = df_display['ema_rsi_20'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
    df_display['ema_rsi_30'] = df_display['ema_rsi_30'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
    
    print(df_display.to_string(index=True))
    print(f"\n{'='*120}\n")


def export_to_csv(symbol, timeframe, num_candles=10, filename=None):
    """
    Xuất thông tin các nến ra file CSV.
    
    Parameters:
    -----------
    symbol : str
        Cặp giao dịch (ví dụ: 'BTC/USDT')
    timeframe : str
        Khung thời gian (ví dụ: '1h', '4h', '1d')
    num_candles : int
        Số lượng nến cần xuất (mặc định: 10)
    filename : str
        Tên file output (mặc định: auto-generated)
    """
    df = export_recent_candles(symbol, timeframe, num_candles)
    
    if df is None:
        print("Không thể xuất dữ liệu.")
        return
    
    # Tạo tên file nếu không được cung cấp
    if filename is None:
        symbol_clean = symbol.replace('/', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"candles_{symbol_clean}_{timeframe}_{timestamp}.csv"
    
    # Xuất ra CSV
    df.to_csv(filename, index=False)
    print(f"Đã xuất dữ liệu ra file: {filename}")


# Ví dụ sử dụng
if __name__ == '__main__':
    # In ra màn hình
    print_candles('WLD/USDT', '1d', 10)
    
    # Hoặc xuất ra CSV
    # export_to_csv('BTC/USDT', '4h', 10)
    
    # Hoặc lấy DataFrame để xử lý tiếp
    # df = export_recent_candles('ETH/USDT', '1d', 10)
    # print(df)
