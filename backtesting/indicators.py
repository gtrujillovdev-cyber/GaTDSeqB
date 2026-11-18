import pandas as pd

from core.indicators import (
    calculate_adx,
    calculate_atr,
    calculate_regime_indicators,
    calculate_rsi,
    calculate_td_sequential,
    calculate_volume_profile,
    detect_divergences,
    find_swing_pivots,
    prepare_market_indicators,
    sightline_check,
)


def inject_htf_confluence(
    df_1d: pd.DataFrame,
    df_4h: pd.DataFrame,
    lookback_days: int = 3,
) -> pd.DataFrame:
    """
    Inyecta columnas td9_4h_buy_recent / td9_4h_sell_recent en un DataFrame 1D.

    Para cada vela 1D cerrada en T, las columnas son True si se disparó una señal
    TD9 en el timeframe 4H dentro de la ventana [T - lookback_days, T).

    La señal 4H es idéntica a check_td_signal():
        buy  → td_count <= -9 AND (td_perfected OR close > close_2ago OR close > high_2ago)
        sell → td_count >= 9  AND (td_perfected OR close < close_2ago OR close < low_2ago)
    """
    df_1d = df_1d.copy()

    if df_4h is None or df_4h.empty or "td_count" not in df_4h.columns:
        df_1d["td9_4h_buy_recent"] = False
        df_1d["td9_4h_sell_recent"] = False
        return df_1d

    df4 = df_4h.copy()
    close_2ago = df4["close"].shift(2)
    high_2ago  = df4["high"].shift(2)
    low_2ago   = df4["low"].shift(2)
    td_perf = df4["td_perfected"] if "td_perfected" in df4.columns else pd.Series(False, index=df4.index)

    df4["_buy"] = (
        (df4["td_count"] <= -9)
        & (td_perf | (df4["close"] > close_2ago) | (df4["close"] > high_2ago))
    ).fillna(False).astype(int)

    df4["_sell"] = (
        (df4["td_count"] >= 9)
        & (td_perf | (df4["close"] < close_2ago) | (df4["close"] < low_2ago))
    ).fillna(False).astype(int)

    # Normalizar datetimes
    df4["datetime"] = pd.to_datetime(df4["datetime"]).dt.tz_localize(None)
    df4 = df4.set_index("datetime").sort_index()

    lb = f"{lookback_days}D"
    buy_roll  = df4["_buy"].rolling(lb, min_periods=1).max()
    sell_roll = df4["_sell"].rolling(lb, min_periods=1).max()

    # Resamplear a 1D con forward-fill para el merge_asof
    buy_daily  = buy_roll.resample("1D").max().ffill().rename("val")
    sell_daily = sell_roll.resample("1D").max().ffill().rename("val")

    dt_1d = pd.to_datetime(df_1d["datetime"]).dt.tz_localize(None)
    base = pd.DataFrame({"datetime": dt_1d.values}).sort_values("datetime")

    df_1d["td9_4h_buy_recent"] = (
        pd.merge_asof(base, buy_daily.reset_index(), on="datetime", direction="backward")["val"]
        .fillna(0).astype(bool).values
    )
    df_1d["td9_4h_sell_recent"] = (
        pd.merge_asof(base, sell_daily.reset_index(), on="datetime", direction="backward")["val"]
        .fillna(0).astype(bool).values
    )

    return df_1d


__all__ = [
    "calculate_rsi",
    "calculate_atr",
    "calculate_adx",
    "calculate_regime_indicators",
    "calculate_volume_profile",
    "sightline_check",
    "find_swing_pivots",
    "detect_divergences",
    "calculate_td_sequential",
    "prepare_market_indicators",
    "inject_htf_confluence",
]
