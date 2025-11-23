import pandas as pd
import pandas_ta as ta
import numpy as np

# Create dummy data
data = {
    'timestamp': pd.date_range(start='2023-01-01', periods=100, freq='1h'),
    'open': np.random.rand(100) * 100,
    'high': np.random.rand(100) * 100,
    'low': np.random.rand(100) * 100,
    'close': np.random.rand(100) * 100,
    'volume': np.random.rand(100) * 1000
}
df = pd.DataFrame(data)

# Case 1: No DatetimeIndex
print("--- Case 1: Integer Index ---")
try:
    vwap1 = ta.vwap(high=df['high'], low=df['low'], close=df['close'], volume=df['volume'])
    print(f"VWAP (Integer Index) Last Value: {vwap1.iloc[-1]}")
    print(f"VWAP (Integer Index) NaNs: {vwap1.isna().sum()}")
except Exception as e:
    print(f"Error: {e}")

# Case 2: With DatetimeIndex
print("\n--- Case 2: DatetimeIndex ---")
df_idx = df.set_index('timestamp')
try:
    vwap2 = ta.vwap(high=df_idx['high'], low=df_idx['low'], close=df_idx['close'], volume=df_idx['volume'])
    # If vwap2 is a Series, it matches the index of df_idx.
    print(f"VWAP (DatetimeIndex) Last Value: {vwap2.iloc[-1]}")
    print(f"VWAP (DatetimeIndex) NaNs: {vwap2.isna().sum()}")
except Exception as e:
    print(f"Error: {e}")
