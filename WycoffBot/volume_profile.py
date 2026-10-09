import numpy as np
import pandas as pd

def calculate_volume_profile(df, bins=50, value_area_pct=0.70):
    """
    Calculates Volume Profile, POC, VAH, and VAL from standard OHLCV Klines.
    Optimized for Raspberry Pi using NumPy instead of tick-by-tick loops.
    
    :param df: Pandas DataFrame with columns ['high', 'low', 'close', 'volume']
    :param bins: Number of price levels to group volume into (higher = more precision, more CPU)
    :param value_area_pct: Percentage of volume to include in the Value Area (default 70%)
    :return: Dictionary with POC, VAH, VAL
    """
    if df.empty:
        return {"poc": 0, "vah": 0, "val": 0}

    # 1. Use Typical Price for the candle's center of mass
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    volume = df['volume']
    
    # 2. Define discrete price bins (from absolute low to absolute high)
    min_price = df['low'].min()
    max_price = df['high'].max()
    
    if min_price == max_price:
        return {"poc": min_price, "vah": min_price, "val": min_price}
        
    price_bins = np.linspace(min_price, max_price, bins)
    
    # 3. Distribute volume into bins
    inds = np.digitize(typical_price, price_bins)
    vp = np.zeros(bins)
    
    for i in range(len(volume)):
        bin_idx = min(inds[i] - 1, bins - 1)
        vp[bin_idx] += volume.iloc[i]
        
    # 4. Find Point of Control (POC) - The bin with the highest volume
    poc_idx = np.argmax(vp)
    poc = price_bins[poc_idx]
    
    # 5. Calculate Value Area High (VAH) and Value Area Low (VAL)
    total_volume = np.sum(vp)
    va_volume_target = total_volume * value_area_pct
    
    va_volume = vp[poc_idx]
    upper_idx = poc_idx
    lower_idx = poc_idx
    
    # Expand outwards from POC until we capture the target volume percentage
    while va_volume < va_volume_target and (upper_idx < bins - 1 or lower_idx > 0):
        vol_up = vp[upper_idx + 1] if upper_idx < bins - 1 else 0
        vol_down = vp[lower_idx - 1] if lower_idx > 0 else 0
        
        if vol_up >= vol_down and upper_idx < bins - 1:
            upper_idx += 1
            va_volume += vol_up
        elif lower_idx > 0:
            lower_idx -= 1
            va_volume += vol_down
        else:
            break
            
    vah = price_bins[upper_idx]
    val = price_bins[lower_idx]
    
    return {
        "poc": float(poc),
        "vah": float(vah),
        "val": float(val)
    }

# Si ejecutamos este script solo para testear:
if __name__ == "__main__":
    print("Testing Volume Profile module...")
    # Mock data
    mock_data = {
        'high': [61000, 61500, 62000, 61800, 62500],
        'low':  [60000, 60500, 61000, 61200, 61500],
        'close':[60500, 61200, 61800, 61500, 62200],
        'volume':[1.5, 2.0, 5.5, 1.2, 3.0] # 5.5 vol on the 3rd candle means POC should be around there
    }
    df_mock = pd.DataFrame(mock_data)
    result = calculate_volume_profile(df_mock, bins=20)
    print("Resultados:", result)
