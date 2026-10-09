import pandas as pd

def detect_divergences(df, lookback=10):
    """
    Detects RSI divergences.
    Returns: 'BULLISH', 'BEARISH', or None
    """
    if len(df) < lookback + 2:
        return None
    
    # We look for the lowest low in the recent past (excluding current candle)
    recent_low_idx = df['low'].iloc[-lookback:-1].idxmin()
    recent_high_idx = df['high'].iloc[-lookback:-1].idxmax()
    
    current_low = df['low'].iloc[-1]
    current_high = df['high'].iloc[-1]
    current_rsi = df['rsi'].iloc[-1]
    
    past_low = df['low'].loc[recent_low_idx]
    past_rsi_low = df['rsi'].loc[recent_low_idx]
    
    past_high = df['high'].loc[recent_high_idx]
    past_rsi_high = df['rsi'].loc[recent_high_idx]
    
    # Bullish Divergence (Spring): Price lower low, RSI higher low
    if current_low < past_low and current_rsi > past_rsi_low:
        return 'BULLISH'
        
    # Bearish Divergence (Upthrust): Price higher high, RSI lower high
    if current_high > past_high and current_rsi < past_rsi_high:
        return 'BEARISH'
        
    return None
