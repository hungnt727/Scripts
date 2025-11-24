import ccxt
import json

def inspect_bybit():
    exchange = ccxt.bybit()
    print("Loading Bybit markets...")
    markets = exchange.load_markets()
    
    usdt_pairs = [s for s in markets if s.endswith('/USDT')]
    print(f"Found {len(usdt_pairs)} USDT pairs.")
    print("Example pairs:", usdt_pairs[:5])
    
    # Check if a specific pair exists and what its type is
    if 'BTC/USDT' in markets:
        print("\nBTC/USDT details:")
        # simplify output
        details = markets['BTC/USDT']
        print(f"Type: {details.get('type')}")
        print(f"Spot: {details.get('spot')}")
        print(f"Swap: {details.get('swap')}")
        
    # Check for perps which might differ in symbol naming in ccxt versions
    print("\nChecking for 'BTC/USDT:USDT' style symbols:")
    perp_pairs = [s for s in markets if 'BTC' in s and 'USDT' in s]
    print(perp_pairs[:5])

if __name__ == "__main__":
    inspect_bybit()
