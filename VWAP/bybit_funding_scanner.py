import time
import ccxt
import telegram
import asyncio

# --- CẤU HÌNH ---
TELEGRAM_BOT_TOKEN = '6468221540:AAEYfM-Zv7ETzXrRfIyMee7ouDCIesGc9pg'
TELEGRAM_CHAT_ID = '-4090797883'
SCAN_INTERVAL = 60  # Quét mỗi 60 giây

# Khởi tạo sàn Bybit
exchange = ccxt.bybit()

# Cache lưu trữ interval trước đó: {symbol: interval_minutes}
previous_intervals = {}

async def send_telegram_message(message):
    """Gửi tin nhắn đến kênh Telegram (Async)."""
    try:
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        print(f"Đã gửi thông báo: {message}")
    except Exception as e:
        print(f"Lỗi khi gửi tin nhắn Telegram: {e}")

def get_funding_intervals():
    """Lấy thông tin funding interval của tất cả các cặp USDT."""
    try:
        # Reload markets để cập nhật thông tin mới nhất
        markets = exchange.load_markets(reload=True)
        intervals = {}
        
        for symbol, market in markets.items():
            # Chỉ lấy các cặp USDT Linear Perpetual (Swap)
            if market['linear'] and market['quote'] == 'USDT':
                if 'info' in market and 'fundingInterval' in market['info']:
                    try:
                        interval = int(market['info']['fundingInterval'])
                        intervals[symbol] = interval
                    except ValueError:
                        pass
        return intervals
    except Exception as e:
        print(f"Lỗi khi lấy thông tin thị trường: {e}")
        return {}

async def main():
    print("--- Bắt đầu Bybit Funding Rate Scanner ---")
    print(f"Bot Token: {TELEGRAM_BOT_TOKEN[:5]}...")
    print(f"Chat ID: {TELEGRAM_CHAT_ID}")
    
    await send_telegram_message("--- Bắt đầu Bybit Funding Rate Scanner ---")

    # Lần chạy đầu tiên để khởi tạo cache
    print("Đang khởi tạo dữ liệu ban đầu...")
    global previous_intervals
    previous_intervals = get_funding_intervals()
    
    print(f"Đã tìm thấy {len(previous_intervals)} cặp giao dịch.")
    
    print("\nBắt đầu vòng lặp theo dõi...")
    
    while True:
        try:
            current_intervals = get_funding_intervals()
            
            if not current_intervals:
                print("Không lấy được dữ liệu, thử lại sau...")
                time.sleep(10)
                continue

            # So sánh với cache cũ
            for symbol, current_interval in current_intervals.items():
                # Nếu là cặp mới list
                if symbol not in previous_intervals:
                    previous_intervals[symbol] = current_interval
                    print(f"Cặp mới: {symbol} (Interval: {current_interval}m)")
                    continue
                
                old_interval = previous_intervals[symbol]
                
                # Kiểm tra thay đổi
                if current_interval != old_interval:
                    print(f"PHÁT HIỆN THAY ĐỔI: {symbol} {old_interval}m -> {current_interval}m")
                    
                    # Chỉ báo động nếu interval GIẢM (ngắn hơn)
                    if current_interval < old_interval:
                        message = f"🚨 CẢNH BÁO FUNDING RATE: {symbol}\n" \
                                  f"Funding Interval đã GIẢM!\n" \
                                  f"Từ: {old_interval} phút ({old_interval/60}h)\n" \
                                  f"Xuống: {current_interval} phút ({current_interval/60}h)\n" \
                                  f"⚠️ Biến động mạnh có thể xảy ra!"
                        await send_telegram_message(message)
                    
                    # Cập nhật cache
                    previous_intervals[symbol] = current_interval
            
            # Cập nhật danh sách (bao gồm cả việc xóa các cặp bị delist nếu cần, nhưng ở đây ta chỉ update)
            # previous_intervals = current_intervals # Không gán đè toàn bộ để tránh mất lịch sử nếu fetch lỗi 1 phần?
            # Tốt nhất là update từng phần hoặc gán đè nếu tin tưởng get_funding_intervals trả về đủ.
            # Với load_markets(reload=True), nó trả về đủ.
            previous_intervals = current_intervals
            
            print(".", end="", flush=True) # Dấu chấm để biết đang chạy
            time.sleep(SCAN_INTERVAL)
            
        except Exception as e:
            print(f"\nLỗi trong vòng lặp chính: {e}")
            time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nĐã dừng scanner.")
