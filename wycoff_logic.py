import pandas as pd
import numpy as np

def sightline_check(y_series, i0: int, i1: int, is_low: bool = True, tol: float = 0.0) -> bool:
    """
    Verifica que los valores intermedios entre dos extremos (i0, i1) no violen la
    recta secante que une (i0, y[i0]) y (i1, y[i1]).
    
    - is_low=True (mínimos/soporte): ningún valor intermedio debe caer por debajo de (recta - tol).
    - is_low=False (máximos/resistencia): ningún valor intermedio debe superar (recta + tol).
    """
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
        if is_low:
            if val < (line_val - tol):
                return False
        else:
            if val > (line_val + tol):
                return False
    return True

def find_swing_pivots(series, is_low: bool = True, radius: int = 1) -> list:
    """
    Identifica índices locales donde el valor es un extremo relativo respecto
    a sus vecinos inmediatos dentro del radio especificado.
    """
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

def detect_divergences(df: pd.DataFrame, lookback: int = 20, min_separation: int = 3, delta_rsi: float = 1.0):
    """
    Detecta divergencias RSI clásicas (Bullish/Bearish) con validación geométrica
    Line of Sight (visión directa entre pivotes sin rupturas intermedias espurias).
    
    Returns: 'BULLISH', 'BEARISH', or None
    """
    if len(df) < min_separation + 2 or 'rsi' not in df.columns:
        return None
    
    # Extraer ventana relevante de análisis
    sub = df.tail(lookback + 2).copy().reset_index(drop=True)
    n = len(sub)
    if n < min_separation + 2:
        return None
        
    lows = sub['low'].values
    highs = sub['high'].values
    rsis = sub['rsi'].values
    
    # Tolerancia adaptativa basada en volatilidad real (ATR)
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
        return None
    
    # 1. EVALUAR DIVERGENCIA ALCISTA (BULLISH / SPRING)
    low_pivots = find_swing_pivots(lows, is_low=True, radius=1)
    valid_low_pivots = [p for p in low_pivots if (curr_idx - p) >= min_separation]
    
    # Fallback seguro al mínimo absoluto si el mercado es plano y no formó fractal perfecto
    if not valid_low_pivots:
        search_range = range(0, curr_idx - min_separation)
        if search_range:
            p_min = min(search_range, key=lambda idx: lows[idx])
            valid_low_pivots = [p_min]
            
    for p1 in reversed(valid_low_pivots):
        if np.isnan(rsis[p1]):
            continue
        # Precio: nuevo mínimo o mínimo equivalente (tolerancia de ruido)
        price_lower = lows[curr_idx] < (lows[p1] + tol_price * 0.5)
        # RSI: divergencia ascendente clara
        rsi_higher = rsis[curr_idx] > (rsis[p1] + delta_rsi)
        
        if price_lower and rsi_higher:
            # Comprobación de Línea de Visión directa en precio y en RSI
            price_clean = sightline_check(lows, p1, curr_idx, is_low=True, tol=tol_price)
            rsi_clean = sightline_check(rsis, p1, curr_idx, is_low=True, tol=tol_rsi)
            
            if price_clean and rsi_clean:
                return 'BULLISH'
                
    # 2. EVALUAR DIVERGENCIA BAJISTA (BEARISH / UPTHRUST)
    high_pivots = find_swing_pivots(highs, is_low=False, radius=1)
    valid_high_pivots = [p for p in high_pivots if (curr_idx - p) >= min_separation]
    
    if not valid_high_pivots:
        search_range = range(0, curr_idx - min_separation)
        if search_range:
            p_max = max(search_range, key=lambda idx: highs[idx])
            valid_high_pivots = [p_max]
            
    for p1 in reversed(valid_high_pivots):
        if np.isnan(rsis[p1]):
            continue
        price_higher = highs[curr_idx] > (highs[p1] - tol_price * 0.5)
        rsi_lower = rsis[curr_idx] < (rsis[p1] - delta_rsi)
        
        if price_higher and rsi_lower:
            price_clean = sightline_check(highs, p1, curr_idx, is_low=False, tol=tol_price)
            rsi_clean = sightline_check(rsis, p1, curr_idx, is_low=False, tol=tol_rsi)
            
            if price_clean and rsi_clean:
                return 'BEARISH'
                
    return None
