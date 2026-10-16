import numpy as np
import pandas as pd

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculo de RSI identico a TradingView (Wilder's Smoothing alpha=1/period)."""
    delta = series.diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0] = 0.0
    down[down > 0] = 0.0
    roll_up = up.ewm(alpha=1/period, adjust=False).mean()
    roll_down = down.abs().ewm(alpha=1/period, adjust=False).mean()
    rs = roll_up / (roll_down + 1e-10)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculo de ATR identico a TradingView (Wilder's RMA)."""
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.ewm(alpha=1/period, adjust=False).mean()

def calculate_volume_profile(df_slice: pd.DataFrame, bins: int = 20, value_area_pct: float = 0.70) -> dict:
    """Calcula POC, VAH y VAL vectorizado con NumPy sobre un slice de velas."""
    if len(df_slice) < 5:
        p = float(df_slice['close'].iloc[-1]) if len(df_slice) > 0 else 0.0
        return {"poc": p, "vah": p, "val": p}
        
    typical_price = (df_slice['high'] + df_slice['low'] + df_slice['close']) / 3
    volume = df_slice['volume']
    
    min_price = float(df_slice['low'].min())
    max_price = float(df_slice['high'].max())
    
    if min_price == max_price:
        return {"poc": min_price, "vah": min_price, "val": min_price}
        
    price_bins = np.linspace(min_price, max_price, bins)
    inds = np.digitize(typical_price, price_bins)
    vp = np.zeros(bins)
    
    vol_vals = volume.values
    for i in range(len(vol_vals)):
        bin_idx = min(inds[i] - 1, bins - 1)
        vp[bin_idx] += vol_vals[i]
        
    poc_idx = int(np.argmax(vp))
    poc = float(price_bins[poc_idx])
    
    total_volume = float(np.sum(vp))
    va_volume_target = total_volume * value_area_pct
    va_volume = float(vp[poc_idx])
    upper_idx = poc_idx
    lower_idx = poc_idx
    
    while va_volume < va_volume_target and (upper_idx < bins - 1 or lower_idx > 0):
        vol_up = float(vp[upper_idx + 1]) if upper_idx < bins - 1 else 0.0
        vol_down = float(vp[lower_idx - 1]) if lower_idx > 0 else 0.0
        
        if vol_up >= vol_down and upper_idx < bins - 1:
            upper_idx += 1
            va_volume += vol_up
        elif lower_idx > 0:
            lower_idx -= 1
            va_volume += vol_down
        else:
            break
            
    vah = float(price_bins[upper_idx])
    val = float(price_bins[lower_idx])
    return {"poc": poc, "vah": vah, "val": val}

def detect_divergences(df_slice: pd.DataFrame, lookback: int = 10) -> str:
    """Detecta divergencias RSI Bullish/Bearish."""
    if len(df_slice) < lookback + 2:
        return "NONE"
        
    recent_low_idx = df_slice['low'].iloc[-lookback:-1].idxmin()
    recent_high_idx = df_slice['high'].iloc[-lookback:-1].idxmax()
    
    current_low = df_slice['low'].iloc[-1]
    current_high = df_slice['high'].iloc[-1]
    current_rsi = df_slice['rsi'].iloc[-1]
    
    past_low = df_slice['low'].loc[recent_low_idx]
    past_rsi_low = df_slice['rsi'].loc[recent_low_idx]
    
    past_high = df_slice['high'].loc[recent_high_idx]
    past_rsi_high = df_slice['rsi'].loc[recent_high_idx]
    
    if current_low < past_low and current_rsi > past_rsi_low:
        return 'BULLISH'
    if current_high > past_high and current_rsi < past_rsi_high:
        return 'BEARISH'
        
    return "NONE"

def calculate_td_sequential(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula Setup 9 / -9 y Countdown 13 / -13 con fidelidad 1:1 al bot."""
    setup_up = 0
    setup_down = 0
    countdown_up = 0
    countdown_down = 0
    setup_up_active = False
    setup_down_active = False
    
    td_counts = []
    td_countdowns = []
    
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    n = len(df)
    
    for i in range(n):
        if i < 4:
            td_counts.append(0)
            td_countdowns.append(0)
            continue
            
        c = closes[i]
        c4 = closes[i-4]
        
        # 1. SETUP
        if c > c4:
            setup_up += 1
            setup_down = 0
            td_counts.append(setup_up)
            if setup_up == 9:
                setup_up_active = True
                setup_down_active = False
                countdown_up = 0
        elif c < c4:
            setup_down += 1
            setup_up = 0
            td_counts.append(-setup_down)
            if setup_down == 9:
                setup_down_active = True
                setup_up_active = False
                countdown_down = 0
        else:
            setup_up = 0
            setup_down = 0
            td_counts.append(0)
            
        # 2. COUNTDOWN
        if i >= 2:
            high_2_ago = highs[i-2]
            low_2_ago = lows[i-2]
            
            if setup_up_active and c > high_2_ago:
                countdown_up += 1
                if countdown_up == 13:
                    setup_up_active = False
                    
            if setup_down_active and c < low_2_ago:
                countdown_down += 1
                if countdown_down == 13:
                    setup_down_active = False
                    
        if setup_up_active and countdown_up > 0:
            td_countdowns.append(countdown_up)
        elif setup_down_active and countdown_down > 0:
            td_countdowns.append(-countdown_down)
        else:
            td_countdowns.append(0)
            
    df['td_count'] = td_counts
    df['td_countdown'] = td_countdowns
    return df

def prepare_market_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara todos los indicadores requeridos vectorizados."""
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['rsi'] = calculate_rsi(df['close'], period=14)
    df['atr'] = calculate_atr(df, period=14)
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df = calculate_td_sequential(df)
    return df
