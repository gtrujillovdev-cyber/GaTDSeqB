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

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculo de ADX identico a TradingView / Welles Wilder (14 periodos).
    Utiliza RMA smoothing (alpha=1/period, adjust=False).
    """
    up_move = df['high'] - df['high'].shift(1)
    down_move = df['low'].shift(1) - df['low']
    
    pos_dm = pd.Series(0.0, index=df.index)
    neg_dm = pd.Series(0.0, index=df.index)
    
    pos_mask = (up_move > down_move) & (up_move > 0)
    neg_mask = (down_move > up_move) & (down_move > 0)
    
    pos_dm[pos_mask] = up_move[pos_mask]
    neg_dm[neg_mask] = down_move[neg_mask]
    
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close = (df['low'] - df['close'].shift(1)).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    tr = ranges.max(axis=1)
    
    tr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    pos_dm_smooth = pos_dm.ewm(alpha=1/period, adjust=False).mean()
    neg_dm_smooth = neg_dm.ewm(alpha=1/period, adjust=False).mean()
    
    tr_safe = tr_smooth.replace(0, np.nan)
    plus_di = 100.0 * (pos_dm_smooth / tr_safe)
    minus_di = 100.0 * (neg_dm_smooth / tr_safe)
    
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx.fillna(0.0)

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

def sightline_check(y_series, i0: int, i1: int, is_low: bool = True, tol: float = 0.0) -> bool:
    """Verifica que los valores entre (i0, i1) no violen la línea de visión directa."""
    dx = i1 - i0
    if dx <= 1:
        return True
    y0 = float(y_series[i0])
    y1 = float(y_series[i1])
    slope = (y1 - y0) / dx
    for k in range(i0 + 1, i1):
        line_val = y0 + slope * (k - i0)
        val = float(y_series[k])
        if np.isnan(val):
            continue
        if is_low and val < (line_val - tol):
            return False
        if not is_low and val > (line_val + tol):
            return False
    return True

def find_swing_pivots(series, is_low: bool = True, radius: int = 1) -> list:
    """Identifica índices de extremos relativos (fractales swing)."""
    n = len(series)
    pivots = []
    for i in range(radius, n - radius):
        val = series[i]
        if np.isnan(val):
            continue
        if is_low:
            if all(val <= series[i - r] and val <= series[i + r] for r in range(1, radius + 1)):
                pivots.append(i)
        else:
            if all(val >= series[i - r] and val >= series[i + r] for r in range(1, radius + 1)):
                pivots.append(i)
    return pivots

def detect_divergences(df_slice: pd.DataFrame, lookback: int = 20, min_separation: int = 3, delta_rsi: float = 1.0) -> str:
    """Detecta divergencias RSI Bullish/Bearish con validación geométrica Line of Sight."""
    if len(df_slice) < min_separation + 2 or 'rsi' not in df_slice.columns:
        return "NONE"
        
    sub = df_slice.tail(lookback + 2).copy().reset_index(drop=True)
    n = len(sub)
    if n < min_separation + 2:
        return "NONE"
        
    lows = sub['low'].values
    highs = sub['high'].values
    rsis = sub['rsi'].values
    
    if 'atr' in sub.columns and pd.notna(sub['atr'].iloc[-1]) and sub['atr'].iloc[-1] > 0:
        atr = float(sub['atr'].iloc[-1])
    else:
        atr = float((sub['high'] - sub['low']).mean())
        if atr <= 0 or np.isnan(atr):
            atr = float(sub['close'].iloc[-1]) * 0.005
            
    tol_price = 0.25 * atr
    tol_rsi = 2.5
    curr_idx = n - 1
    if np.isnan(rsis[curr_idx]):
        return "NONE"
        
    # 1. Bullish Divergence
    low_pivots = find_swing_pivots(lows, is_low=True, radius=1)
    valid_low_pivots = [p for p in low_pivots if (curr_idx - p) >= min_separation]
    if not valid_low_pivots:
        search_range = range(0, curr_idx - min_separation)
        if search_range:
            p_min = min(search_range, key=lambda idx: lows[idx])
            valid_low_pivots = [p_min]
            
    for p1 in reversed(valid_low_pivots):
        if np.isnan(rsis[p1]): continue
        price_lower = lows[curr_idx] < (lows[p1] + tol_price * 0.5)
        rsi_higher = rsis[curr_idx] > (rsis[p1] + delta_rsi)
        if price_lower and rsi_higher:
            if sightline_check(lows, p1, curr_idx, is_low=True, tol=tol_price) and \
               sightline_check(rsis, p1, curr_idx, is_low=True, tol=tol_rsi):
                return 'BULLISH'
                
    # 2. Bearish Divergence
    high_pivots = find_swing_pivots(highs, is_low=False, radius=1)
    valid_high_pivots = [p for p in high_pivots if (curr_idx - p) >= min_separation]
    if not valid_high_pivots:
        search_range = range(0, curr_idx - min_separation)
        if search_range:
            p_max = max(search_range, key=lambda idx: highs[idx])
            valid_high_pivots = [p_max]
            
    for p1 in reversed(valid_high_pivots):
        if np.isnan(rsis[p1]): continue
        price_higher = highs[curr_idx] > (highs[p1] - tol_price * 0.5)
        rsi_lower = rsis[curr_idx] < (rsis[p1] - delta_rsi)
        if price_higher and rsi_lower:
            if sightline_check(highs, p1, curr_idx, is_low=False, tol=tol_price) and \
               sightline_check(rsis, p1, curr_idx, is_low=False, tol=tol_rsi):
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
                    
            if setup_down_active and c < low_2_ago:
                countdown_down += 1
                    
        if setup_up_active and countdown_up > 0:
            td_countdowns.append(countdown_up)
            if countdown_up >= 13:
                setup_up_active = False
                countdown_up = 0
        elif setup_down_active and countdown_down > 0:
            td_countdowns.append(-countdown_down)
            if countdown_down >= 13:
                setup_down_active = False
                countdown_down = 0
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
    df['adx'] = calculate_adx(df, period=14)
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df = calculate_td_sequential(df)
    return df
