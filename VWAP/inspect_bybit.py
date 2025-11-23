import ccxt
import json

def inspect_bybit():
    exchange = ccxt.bybit()
    try:
        print("Fetching markets from Bybit...")
        markets = exchange.load_markets()
        
        # Find a USDT linear perpetual pair
        symbol = 'BTC/USDT:USDT' # ccxt usually uses this format for linear perps on Bybit
        
        if symbol not in markets:
            # Try finding any USDT pair
            for s in markets:
                if 'USDT' in s and markets[s]['linear']:
                    symbol = s
                    break
        
        print(f"Inspecting symbol: {symbol}")
        market = markets[symbol]
        
        # Print relevant fields
        print(f"ID: {market['id']}")
        print(f"Type: {market['type']}")
        print(f"Linear: {market['linear']}")
        print(f"Inverse: {market['inverse']}")
        
        # Check for funding info in 'info' (raw response)
        if 'info' in market:
            print("\n--- Raw Info ---")
            # Print keys to avoid huge output
            print("Keys in info:", market['info'].keys())
            if 'fundingInterval' in market['info']:
                print(f"fundingInterval: {market['info']['fundingInterval']}")
            else:
                print("fundingInterval NOT found in info")
                
        # Check if ccxt parses it
        if 'fundingRate' in market:
             print(f"fundingRate (ccxt): {market['fundingRate']}")
             
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_bybit()
