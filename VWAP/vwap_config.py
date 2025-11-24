# --- CẤU HÌNH ---
# Thay thế bằng thông tin của bạn
COINMARKETCAP_API_KEY = 'a2d1ccdd-c9b4-4e30-b3ac-c0ed36849565'
TELEGRAM_BOT_TOKEN = '6468221540:AAEYfM-Zv7ETzXrRfIyMee7ouDCIesGc9pg'
TELEGRAM_CHAT_ID = '-4054954598'  # Ví dụ: '@kenhcuaban' hoặc '-100123456789'

# Cài đặt cho việc quét
TIMEFRAME_CONFIGS = [
    {'timeframe': '1h', 'anchor': 'M'},  # Anchor Tháng
    {'timeframe': '4h', 'anchor': 'Q'},  # Anchor Quý
    {'timeframe': '1d', 'anchor': 'Y'},  # Anchor Năm
] 
USE_FIXED_LIST = False # True: Chạy danh sách cố định, False: Chạy Top N CoinMarketCap
FIXED_SYMBOLS = [
    'APE/USDT'
]
TOP_N_COINS = 300
LOOKBACK_CANDLES = 2 # Số lượng nến để kiểm tra tín hiệu (ví dụ: 5 cây nến gần nhất)
VWAP_TREND_WINDOW = 10 # Số phiên để tính trung bình VWAP xác định xu hướng
VWAP_MIN_FROM_BEGIN = 50 # Số phiên tối thiểu bắt đầu mỗi chu kỳ
VWAP_BAND_MULTIPLIER = 1.0 # Hệ số nhân cho dải băng VWAP (Stdev)
VWAP_TP_BAND_MULTIPLIER = 2.0 # Hệ số nhân cho TP (Band 2)
VWAP_BAND_3_MULTIPLIER = 3.0 # Hệ số nhân cho Band 3
VWAP_BAND_LOOKBACK = 20 # Số nến nhìn lại để kiểm tra giao cắt với dải băng
SUPER_TREND_LENGTH = 10
SUPER_TREND_MULTIPLIER = 3.0

# Cấu hình các Setup giao dịch
SETUP_VWAP_CONFIGS = [
    # --- VWAP Line ---
    {
        'name': 'VWAP Breakout Long',
        'enabled': True,
        'line': 'vwap',
        'signal_type': 'LONG',
        'enable_rsi_ema': True,
        'enable_ichimoku': True,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': True
    },
    {
        'name': 'VWAP Breakdown Short',
        'enabled': True,
        'line': 'vwap',
        'signal_type': 'SHORT',
        'enable_rsi_ema': True,
        'enable_ichimoku': False,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': True
    },
    # --- Upper Band 1 ---
    {
        'name': 'Upper Band 1 Breakout Long',
        'enabled': True,
        'line': 'upper_band_1',
        'signal_type': 'LONG',
        'enable_rsi_ema': True,
        'enable_ichimoku': True, 
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': True
    },
    {
        'name': 'Upper Band 1 Breakdown Short',
        'enabled': True,
        'line': 'upper_band_1',
        'signal_type': 'SHORT',
        'enable_rsi_ema': True,
        'enable_ichimoku': False,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': False
    },
    # --- Lower Band 1 ---
    {
        'name': 'Lower Band 1 Breakout Long',
        'enabled': True,
        'line': 'lower_band_1',
        'signal_type': 'LONG',
        'enable_rsi_ema': True,
        'enable_ichimoku': True,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': True
    },
    {
        'name': 'Lower Band 1 Breakdown Short',
        'enabled': True,
        'line': 'lower_band_1',
        'signal_type': 'SHORT',
        'enable_rsi_ema':  True ,
        'enable_ichimoku': False,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': True
    },
    # --- Upper Band 2 ---
    {
        'name': 'Upper Band 2 Breakout Long',
        'enabled': False,
        'line': 'upper_band_2',
        'signal_type': 'LONG',
        'enable_rsi_ema': True,
        'enable_ichimoku': True,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': True
    },
    {
        'name': 'Upper Band 2 Breakdown Short',
        'enabled': True,
        'line': 'upper_band_2',
        'signal_type': 'SHORT',
        'enable_rsi_ema': False,
        'enable_ichimoku': False,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': True
    },
     # --- Lower Band 2 ---
    {
        'name': 'Lower Band 2 Breakout Long',
        'enabled': True,
        'line': 'lower_band_2',
        'signal_type': 'LONG',
        'enable_rsi_ema': True,
        'enable_ichimoku': False,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': True
    },
    {
        'name': 'Lower Band 2 Breakdown Short',
        'enabled': False,
        'line': 'lower_band_2',
        'signal_type': 'SHORT',
        'enable_rsi_ema': True,
        'enable_ichimoku': False,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': True
    },
    # --- Upper Band 3 ---
    {
        'name': 'Upper Band 3 Breakout Long',
        'enabled': False,
        'line': 'upper_band_3',
        'signal_type': 'LONG',
        'enable_rsi_ema': True,
        'enable_ichimoku': False,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': True
    },
    {
        'name': 'Upper Band 3 Breakdown Short',
        'enabled': True,   
        'line': 'upper_band_3',
        'signal_type': 'SHORT',
        'enable_rsi_ema': False,
        'enable_ichimoku': False,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': True
    },
     # --- Lower Band 3 ---
    {
        'name': 'Lower Band 3 Breakout Long',
        'enabled': True,
        'line': 'lower_band_3',
        'signal_type': 'LONG',
        'enable_rsi_ema': True,
        'enable_ichimoku': False,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': True
    },
    {
        'name': 'Lower Band 3 Breakdown Short',
        'enabled': False,
        'line': 'lower_band_3',
        'signal_type': 'SHORT',
        'enable_rsi_ema': True,
        'enable_ichimoku': False,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': True
    },
]

# Cờ bật/tắt các điều kiện lọc (Mặc định cho code cũ hoặc dùng chung nếu cần)
ENABLE_VWAP_TREND = True  
ENABLE_BAND_TOUCH = False
