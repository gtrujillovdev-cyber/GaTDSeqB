import json
import os
import time
from typing import Any, Dict, Optional, Tuple

MIN_CONFIDENCE = 0.55

FLEET_ASSETS = ["BTC", "ETH", "HYPE"]
FLEET_TIMEFRAMES = ["4h", "1d", "1w"]
FLEET_STRATEGIES = ["TD9", "WYK", "HYB"]

DEFAULT_BOT_PARAMS: Dict[str, Any] = {
    "atr_sl_trend": 1.5,
    "atr_tp_trend": 3.5,
    "atr_sl_counter": 1.5,
    "atr_tp_counter": 2.5,
    "atr_sl_wyckoff": 1.5,
    "atr_tp_wyckoff": 3.0,
    "be_threshold_atr": 1.5,
    "scale_out_atr": 2.0,
    "scale_out_pct": 0.5,
    "trailing_atr": 2.0,
    "min_confidence": MIN_CONFIDENCE,
    "enable_scale_out": True,
    "enable_breakeven": True,
    "enable_dca_13": True,
    "enable_trailing": True,
}

_FLEET_PARAMS_CACHE: Dict[str, Any] = {"timestamp": 0.0, "data": {}, "filepath": ""}


def normalize_symbol(symbol: str) -> str:
    """Normaliza simbolos como 'BTC/USDT', 'BTC/USDT:USDT' o 'BTCUSDT' a 'BTC'."""
    s = str(symbol).upper().strip()
    if "/" in s:
        s = s.split("/")[0]
    if ":" in s:
        s = s.split(":")[0]
    if s.endswith("USDT") and len(s) > 4:
        s = s[:-4]
    return s


def get_atr_multiplier(timeframe: str) -> float:
    return {
        "5m": 2.0,
        "15m": 1.8,
        "1h": 1.5,
        "4h": 1.2,
        "1d": 1.0,
        "1w": 0.8,
    }.get(timeframe, 1.0)


def get_min_atr_pct(timeframe: str) -> float:
    return {
        "5m": 0.003,
        "15m": 0.004,
        "1h": 0.006,
        "4h": 0.010,
        "1d": 0.015,
        "1w": 0.025,
    }.get(timeframe, 0.015)


def get_scaled_atr(raw_atr: float, price: float, timeframe: str) -> float:
    """Calcula ATR escalado por timeframe con suelo minimo institucional."""
    atr = float(raw_atr) * get_atr_multiplier(timeframe)
    floor_atr = float(price) * get_min_atr_pct(timeframe)
    return max(atr, floor_atr)


def get_base_risk(symbol: str, timeframe: str) -> float:
    """Riesgo base por timeframe con paridad de riesgo para altcoins de alta beta."""
    risk_matrix = {
        "1w": 0.025,
        "1d": 0.020,
        "4h": 0.015,
        "1h": 0.010,
        "15m": 0.005,
        "5m": 0.005,
    }
    base = risk_matrix.get(timeframe, 0.015)
    if normalize_symbol(symbol) == "HYPE":
        base *= 0.65
    return base


def load_fleet_params(
    symbol: str = "BTC",
    timeframe: str = "4h",
    strategy: str = "HYB",
    fleet_file: str = "fleet_optimized.json",
    ttl_seconds: float = 60.0,
) -> Dict[str, Any]:
    """
    Carga dinamicamente los parametros de riesgo desde fleet_optimized.json con cache TTL.
    Fallback seguro a DEFAULT_BOT_PARAMS si el archivo o entrada no existen.
    """
    global _FLEET_PARAMS_CACHE
    now = time.time()

    if (
        ttl_seconds <= 0
        or _FLEET_PARAMS_CACHE["filepath"] != fleet_file
        or (now - _FLEET_PARAMS_CACHE["timestamp"]) > ttl_seconds
    ):
        if os.path.exists(fleet_file):
            try:
                with open(fleet_file, "r") as f:
                    _FLEET_PARAMS_CACHE["data"] = json.load(f)
            except Exception:
                _FLEET_PARAMS_CACHE["data"] = {}
        else:
            _FLEET_PARAMS_CACHE["data"] = {}
        _FLEET_PARAMS_CACHE["timestamp"] = now
        _FLEET_PARAMS_CACHE["filepath"] = fleet_file

    data = _FLEET_PARAMS_CACHE.get("data", {})
    if not data:
        return dict(DEFAULT_BOT_PARAMS)

    clean_sym = normalize_symbol(symbol)
    strat_up = strategy.upper()
    for key, val in data.items():
        k_sym = normalize_symbol(key.split("_")[0] if "_" in key else key)
        k_clean = key.replace("/", "_").replace(":USDT", "")
        if k_sym == clean_sym and f"_{timeframe}_" in k_clean and k_clean.endswith(f"_{strat_up}"):
            bp = val.get("best_params", {})
            merged = dict(DEFAULT_BOT_PARAMS)
            merged.update(bp)
            # Garantia anti-choke en runtime por si un JSON externo trae < 1.0 ATR
            if merged.get("be_threshold_atr", 1.5) < 1.0:
                merged["be_threshold_atr"] = 1.0
            return merged

    return dict(DEFAULT_BOT_PARAMS)


def compute_weekly_context(w_df) -> Optional[Dict[str, Any]]:
    """
    Calcula contexto Macro Semanal [1W] a partir de un DataFrame semanal con TD Sequential.
    Usa solo la ultima vela cerrada (iloc[-2]) para evitar look-ahead bias, y el precio vivo
    de iloc[-1] para validar invalidacion TDST / ventana de 4 barras.
    """
    if w_df is None or len(w_df) < 5:
        return None

    w_closed = w_df.iloc[-2]
    w_live = w_df.iloc[-1]
    w_td = int(w_closed.get("td_count", 0))

    is_within_sell_window = 9 <= w_td <= 12
    is_within_buy_window = -12 <= w_td <= -9

    w_closed_high = float(w_closed.get("high", float("inf")))
    w_closed_low = float(w_closed.get("low", 0.0))
    w_live_price = float(w_live.get("close", w_closed.get("close", 0.0)))
    w_perf = bool(w_closed.get("td_perfected", False))
    w_tdst_res = float(w_closed.get("tdst_res", 0.0))
    w_tdst_sup = float(w_closed.get("tdst_sup", 0.0))

    tdst_invalidated = False
    if w_td >= 9 and w_tdst_res > 0 and w_live_price > w_tdst_res:
        tdst_invalidated = True
    elif w_td <= -9 and w_tdst_sup > 0 and w_live_price < w_tdst_sup:
        tdst_invalidated = True

    is_sell_exhaustion_active = (
        is_within_sell_window and (w_live_price <= w_closed_high) and not tdst_invalidated
    )
    is_buy_exhaustion_active = (
        is_within_buy_window and (w_live_price >= w_closed_low) and not tdst_invalidated
    )

    macro_weight = 0.06 if w_perf else 0.03

    return {
        "td_count": w_td,
        "td_countdown": int(w_closed.get("td_countdown", 0)),
        "td_perfected": w_perf,
        "tdst_res": w_tdst_res,
        "tdst_sup": w_tdst_sup,
        "tdst_invalidated": tdst_invalidated,
        "macro_weight": macro_weight,
        "rsi": float(w_closed.get("rsi", 50.0)),
        "is_sell_exhaustion_active": is_sell_exhaustion_active,
        "is_buy_exhaustion_active": is_buy_exhaustion_active,
    }


def calculate_confidence_score(
    candle,
    action: str,
    divergence: Optional[str],
    is_counter_trend: bool,
    fng_index: Optional[int] = 50,
    funding_rate: float = 0.0,
    weekly_context: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Funnel Architecture: puntuacion de conviccion multidimensional (0.0 a 1.0) sin sesgo direccional.
    """
    score = 0.0
    if divergence == "NONE":
        divergence = None

    # 1. Setup DeMark (30%)
    raw_count = candle.get("td_count", 0)
    is_perf = bool(candle.get("td_perfected", False))
    if action == "BUY":
        if raw_count <= -9:
            score += 0.30
            if is_perf:
                score += 0.05
        elif raw_count <= -7:
            score += 0.15
        elif raw_count >= 9:
            score -= 0.10
    elif action == "SELL":
        if raw_count >= 9:
            score += 0.30
            if is_perf:
                score += 0.05
        elif raw_count >= 7:
            score += 0.15
        elif raw_count <= -9:
            score -= 0.10

    # 2. RSI & Divergencia (25% max)
    rsi = candle.get("rsi", 50.0)
    mom_score = 0.0
    if action == "BUY":
        if divergence == "BULLISH":
            mom_score += 0.15
        elif divergence == "BEARISH":
            mom_score -= 0.10
        if rsi <= 30:
            mom_score += 0.10
        elif rsi <= 40:
            mom_score += 0.05
        elif rsi >= 70:
            mom_score -= 0.10
    else:
        if divergence == "BEARISH":
            mom_score += 0.15
        elif divergence == "BULLISH":
            mom_score -= 0.10
        if rsi >= 70:
            mom_score += 0.10
        elif rsi >= 60:
            mom_score += 0.05
        elif rsi <= 30:
            mom_score -= 0.10

    score += max(-0.15, min(0.25, mom_score))

    # 3. Volumen Institucional vs SMA 20 (25%)
    vol = candle.get("volume", 0.0)
    avg_vol = candle.get("volume_sma", vol)
    if avg_vol > 0:
        vol_ratio = vol / avg_vol
        if vol_ratio >= 1.5:
            score += 0.25
        elif vol_ratio >= 1.0:
            score += 0.15
        else:
            score += 0.05

    # 4. Tendencia Macro EMA 200 (20%)
    score += 0.05 if is_counter_trend else 0.20

    # 5. Macro Confluence: Fear & Greed Index (+-10%)
    if fng_index is not None:
        if action == "BUY":
            if fng_index <= 25:
                score += 0.10
            elif fng_index <= 40:
                score += 0.05
            elif fng_index >= 75:
                score -= 0.10
        elif action == "SELL":
            if fng_index >= 75:
                score += 0.10
            elif fng_index >= 60:
                score += 0.05
            elif fng_index <= 25:
                score -= 0.10

    # 6. Derivatives Sentiment & Carry Cost: Funding Rate (+-10%)
    if funding_rate != 0.0:
        if action == "BUY":
            if funding_rate <= -0.0003:
                score += 0.10
            elif funding_rate < -0.0001:
                score += 0.05
            elif funding_rate >= 0.0005:
                score -= 0.10
            elif funding_rate > 0.0002:
                score -= 0.05
        elif action == "SELL":
            if funding_rate >= 0.0004:
                score += 0.10
            elif funding_rate > 0.0001:
                score += 0.05
            elif funding_rate <= -0.0005:
                score -= 0.10
            elif funding_rate < -0.0002:
                score -= 0.05

    # 7. Regimen ADX (14) (+-5%)
    adx_val = candle.get("adx", 0.0)
    if adx_val > 0.0:
        if not is_counter_trend:
            if adx_val >= 25.0:
                score += 0.05
            elif adx_val < 18.0:
                score -= 0.05
        else:
            if adx_val < 20.0:
                score += 0.05
            elif adx_val >= 28.0:
                score -= 0.05

    # 8. Top-Down Macro Alignment: DeMark Semanal [1W]
    if weekly_context:
        is_sell_exh = weekly_context.get("is_sell_exhaustion_active", False)
        is_buy_exh = weekly_context.get("is_buy_exhaustion_active", False)
        macro_weight = weekly_context.get("macro_weight", 0.06)

        if is_sell_exh:
            if action == "SELL":
                score += macro_weight
            elif action == "BUY":
                score -= macro_weight
        elif is_buy_exh:
            if action == "BUY":
                score += macro_weight
            elif action == "SELL":
                score -= macro_weight

    return max(0.0, min(1.0, round(score, 2)))


def check_td_signal(closed_candle, candle_2_ago) -> Tuple[bool, bool]:
    """Regla unica de activacion TD9 con Price-Flip o Setup Perfection."""
    count = closed_candle["td_count"]
    td_perf = bool(closed_candle.get("td_perfected", False))
    close_p = closed_candle["close"]

    td_buy = bool(
        (count <= -9) and (td_perf or close_p > candle_2_ago["close"] or close_p > candle_2_ago["high"])
    )
    td_sell = bool(
        (count >= 9) and (td_perf or close_p < candle_2_ago["close"] or close_p < candle_2_ago["low"])
    )
    return td_buy, td_sell


def check_wyckoff_signal(closed_candle, vah: float, val: float, avg_vol: float) -> Tuple[bool, bool]:
    """Regla unica de Spring / Upthrust Wyckoff."""
    volume = closed_candle.get("volume", 0.0)
    climatic_volume = bool(avg_vol > 0 and volume > (avg_vol * 1.5))

    candle_range = closed_candle["high"] - closed_candle["low"]
    if candle_range <= 0:
        candle_range = 1.0
    close_pct = (closed_candle["close"] - closed_candle["low"]) / candle_range

    wyckoff_spring = bool((closed_candle["low"] < val) and climatic_volume and (close_pct >= 0.5))
    wyckoff_upthrust = bool((closed_candle["high"] > vah) and climatic_volume and (close_pct <= 0.5))
    return wyckoff_spring, wyckoff_upthrust


def compute_entry_levels(
    action: str,
    signal_reason: str,
    entry_price: float,
    atr: float,
    is_counter_trend: bool,
    params: Dict[str, Any],
) -> Tuple[float, float, str, float, float]:
    """
    Calcula (stop_loss, take_profit, regime_tag, sl_mult, tp_mult).
    Garantiza invariante direccional:
      BUY  -> sl < entry_price < tp
      SELL -> tp < entry_price < sl
    """
    if "TD9" in signal_reason:
        if is_counter_trend:
            sl_mult = float(params.get("atr_sl_counter", 1.5))
            tp_mult = float(params.get("atr_tp_counter", 2.5))
            tag = "Counter-Trend"
        else:
            sl_mult = float(params.get("atr_sl_trend", 1.5))
            tp_mult = float(params.get("atr_tp_trend", 3.5))
            tag = "Trend"
    else:
        sl_mult = float(params.get("atr_sl_wyckoff", 1.5))
        tp_mult = float(params.get("atr_tp_wyckoff", 3.0))
        tag = "Wyckoff"

    if action == "BUY":
        sl = entry_price - (atr * sl_mult)
        tp = entry_price + (atr * tp_mult)
    elif action == "SELL":
        sl = entry_price + (atr * sl_mult)
        tp = entry_price - (atr * tp_mult)
    else:
        raise ValueError(f"Accion invalida: {action}")

    return float(sl), float(tp), tag, sl_mult, tp_mult


def compute_conviction_multiplier(action: str, rsi: float) -> float:
    if action == "BUY" and rsi < 30:
        return 1.25
    if action == "SELL" and rsi > 70:
        return 1.25
    return 1.0


def compute_conviction_boost(symbol: str, conf_score: float) -> float:
    clean_sym = normalize_symbol(symbol)
    if clean_sym in ("BTC", "ETH"):
        if conf_score >= 0.75:
            return 2.0
        if conf_score >= 0.65:
            return 1.5
    return 1.0
