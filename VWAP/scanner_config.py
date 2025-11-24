# ============================================
# SHARED CONFIGURATION FOR ALL SCANNERS
# ============================================

# --- API KEYS & TELEGRAM ---
COINMARKETCAP_API_KEY = 'a2d1ccdd-c9b4-4e30-b3ac-c0ed36849565'
TELEGRAM_BOT_TOKEN = '6468221540:AAEYfM-Zv7ETzXrRfIyMee7ouDCIesGc9pg'
EMA_RSI_TELEGRAM_CHAT_ID = '-4054954598'
VWAP_TELEGRAM_CHAT_ID = '-4257808412'
# --- COIN SELECTION ---
USE_FIXED_LIST = False  # True: Chạy danh sách cố định, False: Chạy Top N CoinMarketCap
FIXED_SYMBOLS = [
    'APE/USDT'
]
TOP_N_COINS = 300

# --- COMMON PARAMETERS ---
LOOKBACK_CANDLES = 2  # Số lượng nến để kiểm tra tín hiệu
SUPER_TREND_LENGTH = 10
SUPER_TREND_MULTIPLIER = 3.0
RSI_EMA_1 = 5
RSI_EMA_2 = 10
RSI_EMA_3 = 20

# ============================================
# VWAP SCANNER CONFIGURATION
# ============================================

# Cấu hình timeframe và anchor period cho VWAP
VWAP_TIMEFRAME_CONFIGS = [
    {'timeframe': '5m', 'anchor': 'D'},  # Anchor Ngày
    {'timeframe': '1h', 'anchor': 'M'},  # Anchor Tháng
    {'timeframe': '4h', 'anchor': 'Q'},  # Anchor Quý
    {'timeframe': '1d', 'anchor': 'Y'},  # Anchor Năm
]

# VWAP Parameters
VWAP_TREND_WINDOW = 10  # Số phiên để tính trung bình VWAP xác định xu hướng
VWAP_MIN_FROM_BEGIN = 50  # Số phiên tối thiểu bắt đầu mỗi chu kỳ
VWAP_SIGNAL_WINDOW = 3  # Số nến tối đa để xét tín hiệu (quét qua vwap)
VWAP_BAND_MULTIPLIER = 1.0  # Hệ số nhân cho dải băng VWAP (Stdev)
VWAP_TP_BAND_MULTIPLIER = 2.0  # Hệ số nhân cho TP (Band 2)
VWAP_BAND_3_MULTIPLIER = 3.0  # Hệ số nhân cho Band 3
VWAP_BAND_LOOKBACK = 20  # Số nến nhìn lại để kiểm tra giao cắt với dải băng

# Cờ bật/tắt các điều kiện lọc VWAP
ENABLE_VWAP_TREND = True
ENABLE_BAND_TOUCH = False

# Cấu hình các Setup giao dịch VWAP
VWAP_SETUP_CONFIGS = [
    # --- VWAP Line ---
    {
        'name': 'VWAP Breakout Long',
        'enabled': False,
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
        'enable_super_trend': False
    },
    # --- Upper Band 1 ---
    {
        'name': 'Upper Band 1 Breakout Long',
        'enabled': False,
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
        'enabled': False,
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
        'enabled': False,
        'line': 'lower_band_1',
        'signal_type': 'SHORT',
        'enable_rsi_ema': True,
        'enable_ichimoku': False,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': False
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
        'enable_rsi_ema': True,
        'enable_ichimoku': False,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': False
    },
    # --- Lower Band 2 ---
    {
        'name': 'Lower Band 2 Breakout Long',
        'enabled': False,
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
        'enable_rsi_ema': True,
        'enable_ichimoku': False,
        'enable_ema_trend': False,
        'enable_volume_filter': True,
        'enable_super_trend': False
    },
    # --- Lower Band 3 ---
    {
        'name': 'Lower Band 3 Breakout Long',
        'enabled': False,
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

# EMA RSI SCANNER CONFIGURATION
# ============================================

# Số cây nến tối đa tính từ lúc đảo chiều EMA RSI
EMA_RSI_SIGNAL_WINDOW = 3

# Cấu hình timeframe để quét EMA RSI
EMA_RSI_TIMEFRAME_CONFIGS = [
    # {'timeframe': '15m'},
    # {'timeframe': '1h'},
    {'timeframe': '4h'},
    {'timeframe': '1d'},
    {'timeframe': '1w'},
]

# Cấu hình các Setup cho EMA RSI
EMA_RSI_SETUP_CONFIGS = [
    {
        'name': 'EMA RSI Long',
        'enabled': True,
        'signal_type': 'LONG',
        'enable_ichimoku': True,
        'enable_volume_filter': True,
        'enable_super_trend': True,
        'min_ema_rsi_distance': 3.0,
        'min_rsi': 30.0
    },
    {
        'name': 'EMA RSI Short',
        'enabled': True,
        'signal_type': 'SHORT',
        'enable_ichimoku': False,
        'enable_volume_filter': False,
        'enable_super_trend': False,
        'min_ema_rsi_distance': 3.0,
        'min_rsi': 50.0
    },
]
