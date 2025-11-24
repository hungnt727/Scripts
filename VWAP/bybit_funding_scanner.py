
import ccxt
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
import telegram
import asyncio

# --- CẤU HÌNH ---
# CMC API Key taken from candle_width_stat.py
COINMARKETCAP_API_KEY = 'a2d1ccdd-c9b4-4e30-b3ac-c0ed36849565' 
SCAN_INTERVAL = 300  # Quét mỗi 5 phút (Funding Rate không thay đổi quá nhanh)

# --- CONFIG FOR FIXED LIST ---
USE_FIXED_LIST = False
FIXED_SYMBOLS = [
    'FLOW/USDT', 'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 
    'DOGE/USDT', 'SWELL/USDT', 'XION/USDT'
]

# --- TELEGRAM CONFIG ---
TELEGRAM_BOT_TOKEN = '6468221540:AAEYfM-Zv7ETzXrRfIyMee7ouDCIesGc9pg'
TELEGRAM_CHAT_ID = '-4090797883'

def send_telegram_message(message):
    """Gửi tin nhắn đến kênh Telegram."""
    try:
        async def _send():
            bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
        
        asyncio.run(_send())
        # print(f"Đã gửi thông báo Telegram.")
    except Exception as e:
        print(f"Lỗi khi gửi tin nhắn Telegram: {e}")

# Khởi tạo sàn Bybit
exchange = ccxt.bybit()

def get_market_caps(symbols):
    """
    Lấy Market Cap từ CoinMarketCap cho danh sách các symbol.
    Input: ['BTC/USDT', 'ETH/USDT', ...]
    Output: {'BTC/USDT': 123456789.0, ...}
    """
    if not symbols:
        return {}
        
    # Extract base currencies (BTC, ETH)
    base_map = {} # BTC -> BTC/USDT
    base_symbols = []
    
    for sym in symbols:
        base = sym.split('/')[0]
        base_map[base] = sym
        if base not in base_symbols:
            base_symbols.append(base)
            
    # CMC API
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': COINMARKETCAP_API_KEY,
    }
    
    # Chunking requests if too many symbols (limit is usually high but safer to chunk if > 100)
    # Top 10 logic -> we only need 10 items. But if we need rank, maybe 10 is fine.
    # The requirement is "Sort list top 10 (N) theo funding fee".
    # So we only need MC for the FINAL top 10.
    
    parameters = {
        'symbol': ','.join(base_symbols),
        'convert': 'USDT'
    }
    
    results = {}
    try:
        response = requests.get(url, params=parameters, headers=headers)
        data = response.json()
        
        if 'data' in data:
            for base, coin_data in data['data'].items():
                if isinstance(coin_data, list):
                    coin_data = coin_data[0] # Handle duplicates
                
                quote = coin_data.get('quote', {}).get('USDT', {})
                mcap = quote.get('market_cap', 0)
                
                # Map back to Bybit symbol
                if base in base_map:
                    bybit_sym = base_map[base]
                    results[bybit_sym] = mcap
    except Exception as e:
        print(f"Lỗi lấy Market Cap: {e}")
        
    return results

def get_target_coins():
    """
    Lấy danh sách coin mục tiêu.
    Nếu USE_FIXED_LIST = True: Trả về danh sách cố định kèm interval.
    Nếu False: Quét tất cả coin có Funding Interval = 1h.
    Output: {'BTC/USDT': 60, 'ETH/USDT': 60, ...}
    """
    try:
        markets = exchange.load_markets(reload=True)
        results = {}
        
        if USE_FIXED_LIST:
            # print(f"Using Fixed List: {FIXED_SYMBOLS}") # Optional log
            for symbol in FIXED_SYMBOLS:
                interval_found = 'N/A'
                
                # Try to find the interval directly or via linear equivalent
                if symbol in markets:
                    market = markets[symbol]
                    if market.get('linear') and 'fundingInterval' in market.get('info', {}):
                        interval_found = int(market['info']['fundingInterval'])
                    else:
                        # Try to find linear counterpart
                        base = market.get('base')
                        quote = market.get('quote')
                        if base and quote:
                             for m_sym, m_mkt in markets.items():
                                 if m_mkt['base'] == base and m_mkt['quote'] == quote and m_mkt['linear']:
                                     if 'fundingInterval' in m_mkt.get('info', {}):
                                         interval_found = int(m_mkt['info']['fundingInterval'])
                                         break
                
                results[symbol] = interval_found
        else:
            # Auto Scan 1h and 2h
            for symbol, market in markets.items():
                if market.get('linear') and market.get('quote') == 'USDT':
                    info = market.get('info', {})
                    interval = info.get('fundingInterval')
                    
                    if interval and int(interval) in [60, 120]:
                        results[symbol] = int(interval)
                        
        return results
    except Exception as e:
        print(f"Lỗi lấy danh sách coin: {e}")
        return {}

def get_price_changes(symbol):
    """Lấy giá hiện tại, thay đổi 1h và 4h."""
    try:
        # Lấy 5 cây nến 1h gần nhất
        # [TimeStamp, Open, High, Low, Close, Volume]
        # Index: -1 (Current), -2 (1h ago completed + current duration), ...
        # Change 1h: (Close[-1] - Open[-1]) / Open[-1] ? 
        # Hoặc so với close của cây trước?
        # Standard: Change = (Current Price - Price N time ago) / Price N time ago
        
        # Để lấy change 4h chuẩn xác:
        # Lấy nến 1h. 
        # Current Price = Close[-1] (nến đang chạy)
        # Price 1h ago = Open[-1] (Giá mở cửa nến hiện tại - tức là giá 1h trước? Không, Open nến 1h là giá lúc chỉnh giờ. Ví dụ 12:00. Bây giờ là 12:50.)
        # Nếu muốn "1h Rolling Change": (Price Now - Price 60 mins ago).
        # Nếu muốn đơn giản: Change % của nến 1H hiện tại và Tổng 4 nến gần nhất.
        
        # Cách đơn giản nhất và phổ biến:
        # 1h Change = % thay đổi của nến hiện tại (nếu mới bắt đầu giờ thì gần 0). 
        # Hoặc dùng (Price - Open).
        
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=5)
        if not ohlcv or len(ohlcv) < 5:
            return None, 0, 0
            
        current_candle = ohlcv[-1]
        current_price = current_candle[4]
        
        # 1h change: So sánh giá hiện tại với giá MỞ CỬA của nến 1h hiện tại (Intraday hourly change)
        # Hoặc so với Close của nến trước? Thường là so với Close nến trước (Change vs Previous Close).
        # Nếu user muốn "1h Change" theo kiểu Rolling thì khó hơn.
        # Ta dùng: (Price - Open 1h candle) -> Change trong giờ này.
        # Hoặc (Price - Close[prev]).
        # Hãy dùng: % Change from Open of Current Candle (Thay đổi trong phiên 1h này).
        price_open_1h = current_candle[1]
        change_1h = ((current_price - price_open_1h) / price_open_1h) * 100
        
        # 4h change: So sánh giá hiện tại với giá MỞ CỬA của nến 3 cây TRƯỚC đó (tổng 4h).
        # ohlcv[-1] là H0. ohlcv[-4] là H-3. Open của ohlcv[-4] là thời điểm bắt đầu 4h trước.
        # Ví dụ: list có 5 cây: 0, 1, 2, 3, 4(current).
        # Cây 4 bắt đầu lúc 12:00. Cây 3: 11:00. Cây 2: 10:00. Cây 1: 09:00.
        # Open của cây 1 (09:00) đến hiện tại (12:xx) là gần 4 tiếng.
        # Lấy open của ohlcv[-4]
        
        price_open_4h = ohlcv[-4][1]
        change_4h = ((current_price - price_open_4h) / price_open_4h) * 100
        
        return current_price, change_1h, change_4h
    except Exception as e:
        return 0, 0, 0
        return current_price, change_1h, change_4h
    except Exception as e:
        return 0, 0, 0

def get_funding_history(symbol):
    """
    Lay lich su funding rate.
    Tra ve list [rate1, rate2, rate3] (Gan nhat truoc)
    """
    try:
        # Fetching last 4 to skip current if duplicated? 
        # Usually fetching history returns *past* settled rates.
        # The 'fundingRate' in ticker is the *predicted* next rate.
        # User wants: Current (Predicted) + History.
        # fetch_funding_rate_history usually returns settled rates.
        # limit=3 returns last 3 settled rates.
        
        # We need to map symbol to linear symbol if needed.
        # But here we are passing symbols that worked for fetch_ohlcv?
        # In main(), 'sym' comes from 'top_10' which has symbols from 'all_funding'.
        # 'all_funding' used 'linear_symbols' or 'target_symbols'.
        # Let's try passing the symbol as is. If it fails, we handle it.
        
        # Note: 'symbol' passed here is the 'simple_sym' used in display (e.g. BTC/USDT).
        # CCXT needs the unified symbol or ID.
        # If simple_sym matches a market in load_markets, likely fine.
        
        history = exchange.fetch_funding_rate_history(symbol, limit=3)
        # History is usually sorted by time ascending.
        # We want "Nearest" first? "Example: -1.02% (-1.12%, -1.22%, -1.52%)"
        # The format implies recent past.
        # So we should reverse the list if it is ascending.
        
        rates = [x['fundingRate'] for x in history]
        # Check sort order. Typically API returns chronological. 
        # So rates[-1] is the most recent SETTLED rate.
        # We want to display nearest first.
        rates.reverse()
        return rates
    except Exception as e:
        # Try appending :USDT if linear
        try:
             if not symbol.endswith(':USDT'):
                 history = exchange.fetch_funding_rate_history(symbol + ':USDT', limit=3)
                 rates = [x['fundingRate'] for x in history]
                 rates.reverse()
                 return rates
        except:
            pass
        return []

# ... (Keep Imports)

# ... (Functions same)

def main():
    print(f"--- Bybit High Frequency Funding Scanner ---")
    if USE_FIXED_LIST:
        print("Mode: Fixed List")
    else:
        print("Mode: Auto Scan (Interval = 1h, 2h)")
    
    while True:
        try:
            # 1. Lấy danh sách targets
            print("Scanning list of coins...")
            target_map = get_target_coins() # {symbol: interval}
            target_symbols = list(target_map.keys())
            print(f"Found {len(target_symbols)} coins.")
            
            if not target_symbols:
                time.sleep(60)
                continue
                
            if USE_FIXED_LIST:
                # For fixed list, we need to ensure we use the correct Market ID or Symbol for funding API
                # Bybit often wants "BTC/USDT:USDT" for linear
                # Let's map our simple "BTC/USDT" to the Exchange's ID if possible
                linear_symbols = []
                symbol_map_reverse = {} # LinearSym -> SimpleSym
                
                markets = exchange.load_markets()
                for sym in target_symbols:
                    # Find the linear market for this symbol
                    # If sym is exactly "BTC/USDT", check if it implies linear
                    market = markets.get(sym)
                    if market:
                        linear_symbols.append(market['id']) # Use ID (e.g. BTCUSDT) or symbol?
                        # fetch_funding_rates usually takes unified symbols if loaded.
                        # But the error said "spot markets" which implies it thinks BTC/USDT is spot.
                        # On Bybit, BTC/USDT is usually Spot. BTC/USDT:USDT is Linear.
                        
                        # Try to find the Linear counterpart if this is treated as spot
                        if market['spot']:
                             # Look for linear with same base/quote
                             found_linear = False
                             for m_sym, m_mkt in markets.items():
                                 if m_mkt['base'] == market['base'] and m_mkt['quote'] == market['quote'] and m_mkt['linear']:
                                     linear_symbols.append(m_sym)
                                     symbol_map_reverse[m_sym] = sym
                                     found_linear = True
                                     break
                             if not found_linear:
                                 print(f"Skipping {sym}: No linear market found.")
                        else:
                            linear_symbols.append(sym)
                            symbol_map_reverse[sym] = sym
                    else:
                        print(f"Warning: {sym} not found in markets.")

                # 2. Lấy Funding Rates
                print("Fetching Funding Rates...")
                if not linear_symbols:
                    print("No linear symbols found.")
                    time.sleep(60)
                    continue
                    
                all_funding = exchange.fetch_funding_rates(linear_symbols, params={'category': 'linear'})
                
                data_list = []
                
                for f_sym, data in all_funding.items():
                    # Map back to simple symbol if needed
                    # The fetch returns keys as passed or as exchange IDs?
                    # Usually returns as Unified Symbols (e.g. BTC/USDT:USDT)
                    
                    simple_sym = symbol_map_reverse.get(f_sym, f_sym)
                    
                    # If we passed IDs (e.g. BTCUSDT), response keys might be different.
                    # Let's check if the key is in our target map (which has simple symbols)
                    # target_map keys are what we started with.
                    
                    # If f_sym is BTC/USDT:USDT, and target_map has BTC/USDT
                    # We need to link them.
                    
                    # Try to clean symbol
                    if simple_sym not in target_symbols:
                         # Attempt to find if f_sym contains the target
                         for t_s in target_symbols:
                             if t_s in f_sym:
                                 simple_sym = t_s
                                 break
                    
                    if simple_sym not in target_symbols:
                        continue
                        
                    funding_rate = data.get('fundingRate')
                    if funding_rate is None:
                        continue
                    
                    data_list.append({
                        'symbol': simple_sym,
                        'funding_rate': funding_rate,
                        'interval': target_map.get(simple_sym, 'N/A')
                    })
            else:
                # Auto Scan mode uses symbols returned by get_1h_funding_coins which are already filtered for 'linear' and 'USDT'
                # But wait, get_1h_funding_coins iterates markets and checks 'linear'. 
                # So the symbols there ARE ALREADY Linear symbols (e.g. BTC/USDT:USDT or similar).
                # existing code: `target_symbols = list(target_map.keys())`
                # previous `get_1h_funding_coins` returned `symbol` from `markets.items()`.
                # If `ccxt` loads `BTC/USDT` as Spot and `BTC/USDT:USDT` as Linear, 
                # then `get_1h_funding_coins` would have returned `BTC/USDT:USDT`.
                
                # The FIXED_LIST has `BTC/USDT`. This is likely the SPOT symbol in CCXT structure.
                # So for Fixed List, we must convert to Linear.
                
                print("Fetching Funding Rates (Auto Mode)...")
                all_funding = exchange.fetch_funding_rates(target_symbols, params={'category': 'linear'})
                 
                data_list = []
                for sym, data in all_funding.items():
                    if sym not in target_symbols:
                        continue
                        
                    funding_rate = data.get('fundingRate')
                    if funding_rate is None:
                        continue
                    
                    data_list.append({
                        'symbol': sym,
                        'funding_rate': funding_rate,
                        'interval': target_map.get(sym, 'N/A')
                    })
                
            # 3. Sort Top 10
            data_list.sort(key=lambda x: abs(x['funding_rate']), reverse=True)
            top_10 = data_list[:10]
            
            # 4. Lấy chi tiết cho Top 10
            print("Fetching details (Market Cap & Price Change) for Top 10...")
            
            top_symbols = [x['symbol'] for x in top_10]
            mcaps = get_market_caps(top_symbols)
            
            final_display = []
            
            for item in top_10:
                sym = item['symbol']
                price, chg1h, chg4h = get_price_changes(sym)
                
                mcap = mcaps.get(sym, 0)
                
                # Fetch history
                hist_rates = get_funding_history(sym)
                
                # Format Interval string
                interval_val = item['interval']
                if interval_val == 60:
                    interval_str = "1h"
                elif interval_val == 120:
                    interval_str = "2h"
                elif isinstance(interval_val, int):
                    interval_str = f"{interval_val}m"
                else:
                    interval_str = str(interval_val)

                final_display.append({
                    'Name': sym,
                    'Price': price,
                    'Funding Rate %': item['funding_rate'],
                    'History': hist_rates,
                    'Interval': interval_str,
                    '1h Change': chg1h,
                    '4h Change': chg4h,
                    'MarketCap': mcap
                })
                
            # 5. Hiển thị
            print("\n" + "="*120)
            print(f"TOP 10 COINS WITH HIGHEST FUNDING RATE - {datetime.now().strftime('%H:%M:%S')}")
            print("="*120)
            
            # Widen the Funding Rate column to accommodate history
            print(f"{'Name':<15} {'Price':<12} {'Funding Rate % (Hist)':<35} {'Interval':<10} {'1h Change':<12} {'4h Change':<12} {'Market Cap':<15}")
            print("-" * 120)
            
            for item in final_display:
                current_rate = item['Funding Rate %']
                hist = item['History']
                
                # Format: Cur% (H1%, H2%, H3%)
                # Example: -1.0211% (-1.1211% , -1.2211% , -1.5211% )
                
                cur_str = f"{current_rate*100:+.4f}%"
                
                hist_str = ""
                if hist:
                    hist_strs = [f"{r*100:+.4f}%" for r in hist]
                    hist_str = f" ({', '.join(hist_strs)})"
                    
                full_rate_str = cur_str + hist_str
                
                p_price = f"${item['Price']:.4f}" if item['Price'] < 100 else f"${item['Price']:.2f}"
                c1h = f"{item['1h Change']:+.2f}%"
                c4h = f"{item['4h Change']:+.2f}%"
                
                mc = item['MarketCap']
                if mc >= 1_000_000_000:
                    mcap_str = f"${mc/1_000_000_000:.2f}B"
                elif mc >= 1_000_000:
                    mcap_str = f"${mc/1_000_000:.2f}M"
                else:
                    mcap_str = f"${mc:,.0f}" if mc > 0 else "N/A"
                
                print(f"{item['Name']:<15} {p_price:<12} {full_rate_str:<35} {item['Interval']:<10} {c1h:<12} {c4h:<12} {mcap_str:<15}")
                
            # --- SEND TELEGRAM ---
            try:
                msg_lines = []
                msg_lines.append(f"🔥 *TOP COINS FUNDING RATE* - {datetime.now().strftime('%H:%M')}")
                msg_lines.append("```")
                msg_lines.append(f"{'Name':<10} {'Rate%':<10} {'Interval':<5}")
                msg_lines.append("-" * 30)
                
                for item in final_display[:10]: # Limit to top 10 for TG
                    cur_rate_pct = item['Funding Rate %'] * 100
                    # Shorten name if too long for mobile
                    name = item['Name'].split('/')[0]
                    
                    hist = item['History']
                    # Show only current rate in table to save space, or maybe current + 1 hist?
                    # User requested 'information above', which likely means the table.
                    # But full table with history is too wide for mobile.
                    # Let's try to fit essential info.
                    
                    # Row 1: Name, Rate, Interval
                    row_str = f"{name:<10} {cur_rate_pct:+.4f}% {item['Interval']:<5}"
                    msg_lines.append(row_str)
                    
                    # Row 2 (Optional): History?
                    # "Manta: -1.0% (-1.1, -1.2)"
                    if hist:
                        h_strs = [f"{h*100:+.3f}%" for h in hist]
                        hist_txt = f"Hist: {', '.join(h_strs)}"
                        msg_lines.append(f"  {hist_txt}")
                        
                msg_lines.append("```")
                telegram_msg = "\n".join(msg_lines)
                
                # print("Sending to Telegram...")
                send_telegram_message(telegram_msg)
                
            except Exception as e:
                print(f"Error preparing Telegram msg: {e}")
            
                print(f"Error preparing Telegram msg: {e}")
            
            # --- Schedule: Wait for next 15 minutes ---
            now = datetime.now()
            # Calculate next 15 minute interval (00, 15, 30, 45)
            minutes_to_add = 15 - (now.minute % 15)
            next_run = (now + timedelta(minutes=minutes_to_add)).replace(second=0, microsecond=0)
            
            wait_seconds = (next_run - now).total_seconds()
            
            print(f"\nWaiting {wait_seconds/60:.2f} minutes for next update at {next_run.strftime('%H:%M:%S')}...")
            time.sleep(wait_seconds)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Program stopped.")
