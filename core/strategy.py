import json
import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

MIN_CONFIDENCE = 0.55

# Hard Risk Caps (v5.0 Risk Engineering)
MAX_RISK_TREND = 0.015     # 1.50% max risk per trade in trend-aligned strategies
MAX_RISK_COUNTER = 0.0075  # 0.75% max risk per trade in counter-trend / range strategies

FLEET_ASSETS = ["BTC", "ETH", "SOL", "BNB", "AVAX"]
FLEET_TIMEFRAMES = ["1d"]
FLEET_STRATEGIES = ["TREND"]

DEFAULT_BOT_PARAMS: Dict[str, Any] = {
    "atr_sl_trend": 2.0,
    "atr_tp_trend": 8.0,
    "atr_sl_counter": 1.5,
    "atr_tp_counter": 2.5,
    "atr_sl_wyckoff": 1.5,
    "atr_tp_wyckoff": 3.0,
    "be_threshold_atr": 1.5,
    "scale_out_atr": 2.0,
    "scale_out_pct": 0.5,
    "trailing_atr": 3.0,
    "min_confidence": MIN_CONFIDENCE,
    "enable_scale_out": False,
    "enable_breakeven": False,
    "enable_dca_13": False,
    "enable_trailing": True,
    # Parametros v3.1 / v4.0 / v5.0
    "dc_period": 55,
    "dc_exit_period": 10,
    "adx_min": 20.0,
    "adx_split": 24.0,
    "adx_max": 24.0,
    "mr_sl_atr": 1.5,
    "mr_tp_atr": 2.5,
    "pb_sl_atr": 1.5,
    "pb_tp_atr": 3.0,
    "pb_rsi_buy": 42.0,
    "pb_rsi_sell": 58.0,
    "regime_mr_max_p_trend": 0.45,
    "regime_trend_min_p_trend": 0.55,
    "meta_threshold": 0.55,
    "meta_soft_sizing": True,
    "use_meta_gate": False,
    "use_hyb_meta_gate": True,
}

_FLEET_PARAMS_CACHE: Dict[str, Any] = {"timestamp": 0.0, "data": {}, "filepath": ""}
_META_WEIGHTS_CACHE: Dict[str, Any] = {"timestamp": 0.0, "data": {}, "filepath": ""}


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


def get_base_risk(
    symbol: str,
    timeframe: str,
    realized_vol_30d: Optional[float] = None,
    target_daily_vol: float = 0.030,
) -> float:
    """
    Riesgo base por timeframe con paridad de riesgo dinamica opcional.
    Si realized_vol_30d es None, conserva exactamente el fallback historico (HYPE *= 0.65).
    """
    risk_matrix = {
        "1w": 0.025,
        "1d": 0.020,
        "4h": 0.015,
        "1h": 0.010,
        "15m": 0.005,
        "5m": 0.005,
    }
    base = risk_matrix.get(timeframe, 0.015)
    if realized_vol_30d is not None and realized_vol_30d > 1e-6:
        vol_scale = max(0.35, min(1.25, target_daily_vol / float(realized_vol_30d)))
        return base * vol_scale
    if normalize_symbol(symbol) == "HYPE":
        base *= 0.65
    return base


def _load_json_ttl(cache: Dict[str, Any], filepath: str, ttl_seconds: float) -> Dict[str, Any]:
    now = time.time()
    if (
        ttl_seconds <= 0
        or cache["filepath"] != filepath
        or (now - cache["timestamp"]) > ttl_seconds
    ):
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    cache["data"] = json.load(f)
            except Exception:
                cache["data"] = {}
        else:
            cache["data"] = {}
        cache["timestamp"] = now
        cache["filepath"] = filepath
    return cache.get("data", {})


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
    data = _load_json_ttl(_FLEET_PARAMS_CACHE, fleet_file, ttl_seconds)
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


def is_bot_calibrated(
    symbol: str,
    timeframe: str,
    strategy: str,
    fleet_file: str = "fleet_optimized.json",
    ttl_seconds: float = 60.0,
) -> bool:
    """
    Compuerta de Admision a Produccion (v5.0 Production Gate).
    Retorna True unicamente si el bot figura en fleet_optimized.json con is_calibrated == True.
    """
    data = _load_json_ttl(_FLEET_PARAMS_CACHE, fleet_file, ttl_seconds)
    if not data:
        return False
    clean_sym = normalize_symbol(symbol)
    strat_up = strategy.upper()
    for key, val in data.items():
        k_sym = normalize_symbol(key.split("_")[0] if "_" in key else key)
        k_clean = key.replace("/", "_").replace(":USDT", "")
        if k_sym == clean_sym and f"_{timeframe}_" in k_clean and k_clean.endswith(f"_{strat_up}"):
            return bool(val.get("is_calibrated", False))
    return False


def cap_trade_risk(risk_pct: float, is_counter_trend: bool = False) -> float:
    """
    Techo duro de riesgo por operacion (v5.0 Risk Engineering).
      - Tendencia / Pullback alineado: <= 1.50% (MAX_RISK_TREND)
      - Contratendencia / Rango:       <= 0.75% (MAX_RISK_COUNTER)
    """
    cap = MAX_RISK_COUNTER if is_counter_trend else MAX_RISK_TREND
    return max(0.0, min(float(risk_pct), cap))


def load_meta_weights(
    strategy: str = "MR",
    weights_file: str = "meta_model_weights.json",
    ttl_seconds: float = 60.0,
) -> Optional[Dict[str, Any]]:
    """Carga pesos L2 pre-escalados para inferencia O(1) en ARMv7 sin scikit-learn."""
    data = _load_json_ttl(_META_WEIGHTS_CACHE, weights_file, ttl_seconds)
    entry = data.get(strategy.upper())
    if not isinstance(entry, dict) or "weights" not in entry or "bias" not in entry:
        return None
    return entry


def extract_meta_features(
    closed_candle,
    action: str,
    ema200: float,
    funding_rate: float = 0.0,
    htf_4h_aligned: bool = False,
    is_trend_mode: bool = False,
) -> np.ndarray:
    """Extrae 5 features estacionarias, adimensionales y causales de la vela cerrada."""
    y_side = 1.0 if action == "BUY" else -1.0
    p_trend = float(closed_candle.get("p_trend", 0.5))
    if p_trend != p_trend:  # NaN guard
        p_trend = 0.5
    f1_regime = p_trend if is_trend_mode else (1.0 - p_trend)
    f2_htf = 1.0 if htf_4h_aligned else 0.0
    f3_funding = -y_side * max(-2.0, min(2.0, float(funding_rate) / 0.0005))

    close_p = float(closed_candle["close"])
    atr = max(float(closed_candle.get("atr", close_p * 0.015)), 1e-8)
    f4_ema_dist = y_side * max(-5.0, min(5.0, (close_p - float(ema200)) / atr))

    vol = float(closed_candle.get("volume", 0.0))
    vol_sma = float(closed_candle.get("volume_sma", vol))
    vol_ratio = (vol / vol_sma) if vol_sma > 1e-8 else 1.0
    f5_log_vol = math.log(max(0.2, min(5.0, vol_ratio)))

    return np.array([f1_regime, f2_htf, f3_funding, f4_ema_dist, f5_log_vol], dtype=np.float64)


def predict_meta_probability(
    features: np.ndarray,
    meta_weights: Optional[Dict[str, Any]],
) -> Tuple[float, float]:
    """
    Inferencia logistica pura en NumPy (< 0.01 ms en Pi 3B).
    Retorna (probabilidad_exito, multiplicador_tamano).
    """
    if not meta_weights:
        return 1.0, 1.0
    w = np.asarray(meta_weights["weights"], dtype=np.float64)
    if w.shape[0] != features.shape[0]:
        return 1.0, 1.0
    b = float(meta_weights["bias"])
    thresh = float(meta_weights.get("threshold", 0.55))

    logit = float(np.dot(w, features)) + b
    prob = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, logit))))
    if prob < thresh:
        return prob, 0.0
    denom = max(1e-6, 1.0 - thresh)
    bet_mult = max(0.25, min(1.25, 0.25 + ((prob - thresh) / denom)))
    return prob, bet_mult


def compute_rolling_corr_and_vol(
    closed_dfs: Dict[str, Any],
    window: int = 30,
    prior_corr: float = 0.65,
) -> Tuple[Dict[Tuple[str, str], float], Dict[str, float]]:
    """
    Calcula la matriz de correlacion 30d con shrinkage lineal hacia prior cripto
    y las volatilidades diarias realizadas por activo sobre velas estrictamente cerradas.
    """
    returns_map: Dict[str, np.ndarray] = {}
    vols: Dict[str, float] = {}

    for sym, df in closed_dfs.items():
        if df is None or len(df) < 5:
            continue
        clean = normalize_symbol(sym)
        closes = df["close"].to_numpy(dtype=np.float64)
        tail = closes[-(window + 1):]
        if len(tail) < 3:
            continue
        rets = np.diff(np.log(np.maximum(tail, 1e-12)))
        returns_map[clean] = rets
        vols[clean] = float(np.std(rets, ddof=1)) if len(rets) >= 2 else 0.03

    corr_matrix: Dict[Tuple[str, str], float] = {}
    syms = sorted(returns_map.keys())
    for i, s1 in enumerate(syms):
        corr_matrix[(s1, s1)] = 1.0
        r1 = returns_map[s1]
        for s2 in syms[i + 1:]:
            r2 = returns_map[s2]
            n_obs = min(len(r1), len(r2))
            if n_obs < 5:
                rho = prior_corr
            else:
                a, b = r1[-n_obs:], r2[-n_obs:]
                std_a, std_b = float(np.std(a, ddof=1)), float(np.std(b, ddof=1))
                if std_a <= 1e-12 or std_b <= 1e-12:
                    rho = prior_corr
                else:
                    sample_rho = float(np.corrcoef(a, b)[0, 1])
                    if not math.isfinite(sample_rho):
                        sample_rho = prior_corr
                    lam = min(1.0, n_obs / float(window))
                    rho = max(-0.99, min(0.99, lam * sample_rho + (1.0 - lam) * prior_corr))
            corr_matrix[(s1, s2)] = round(rho, 4)
            corr_matrix[(s2, s1)] = round(rho, 4)

    return corr_matrix, vols


def compute_portfolio_dampening(
    candidate_symbol: str,
    candidate_action: str,
    candidate_risk_pct: float,
    active_positions: List[Dict[str, Any]],
    corr_matrix: Optional[Dict[Tuple[str, str], float]] = None,
    gamma: float = 0.85,
    max_fleet_sigma: float = 0.045,
    ref_risk: float = 0.020,
) -> float:
    """
    Calcula factor de amortiguacion [0.0, 1.0] ajustado por matriz de correlacion 30d
    y presupuesto de riesgo agregado de flota.
    """
    if not active_positions:
        return 1.0

    cand_sym = normalize_symbol(candidate_symbol)
    cand_sign = 1.0 if candidate_action == "BUY" else -1.0

    def _corr(a: str, b: str) -> float:
        if a == b:
            return 1.0
        if corr_matrix:
            if (a, b) in corr_matrix:
                return float(corr_matrix[(a, b)])
            if (b, a) in corr_matrix:
                return float(corr_matrix[(b, a)])
        return 0.65

    overlap = 0.0
    for pos in active_positions:
        p_sym = normalize_symbol(pos.get("symbol", ""))
        p_sign = 1.0 if pos.get("position", "BUY") == "BUY" else -1.0
        p_risk = float(pos.get("risk_pct", ref_risk))
        rho = _corr(cand_sym, p_sym)
        directional_corr = max(0.0, cand_sign * p_sign * rho)
        overlap += directional_corr * (p_risk / max(1e-6, ref_risk))

    damp = max(0.25, 1.0 / math.sqrt(1.0 + gamma * overlap))
    proposed_risk = candidate_risk_pct * damp

    net_risk: Dict[str, float] = {}
    for pos in active_positions:
        p_sym = normalize_symbol(pos.get("symbol", ""))
        p_sign = 1.0 if pos.get("position", "BUY") == "BUY" else -1.0
        net_risk[p_sym] = net_risk.get(p_sym, 0.0) + p_sign * float(pos.get("risk_pct", ref_risk))
    net_risk[cand_sym] = net_risk.get(cand_sym, 0.0) + cand_sign * proposed_risk

    syms = list(net_risk.keys())
    var_p = 0.0
    for s1 in syms:
        for s2 in syms:
            var_p += net_risk[s1] * net_risk[s2] * _corr(s1, s2)
    sigma_p = math.sqrt(max(0.0, var_p))

    if sigma_p > max_fleet_sigma and sigma_p > 1e-8:
        damp *= (max_fleet_sigma / sigma_p)

    return max(0.0, min(1.0, round(damp, 4)))


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
    # Evidencia empirica 4a: en contratendencia (TD9 fade), volumen explosivo >=1.5x es ruptura adversa
    vol = candle.get("volume", 0.0)
    avg_vol = candle.get("volume_sma", vol)
    if avg_vol > 0:
        vol_ratio = vol / avg_vol
        if is_counter_trend:
            if vol_ratio >= 1.5:
                score += 0.05
            elif 0.8 <= vol_ratio < 1.3:
                score += 0.20
            else:
                score += 0.10
        else:
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

    # 7. Regimen Hibrido ADX (14) + p_trend Continuo (+-5%)
    adx_val = float(candle.get("adx", 0.0) or 0.0)
    p_trend = candle.get("p_trend", None)
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
    if p_trend is not None and p_trend == p_trend:
        pt = float(p_trend)
        if not is_counter_trend and pt >= 0.55:
            score += 0.03
        elif is_counter_trend and pt > 0.55:
            score -= 0.03

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
    """
    Regla unica de activacion TD9 (v5.0):
      - En Setup Perfection (td_perf), solo dispara en finalizacion exacta (-9/-13 o +9/+13),
        evitando disparar en caida libre continua (-10, -11, ..., -19).
      - Tras superar 9, exige confirmacion real de giro de precio (Price-Flip vs 2 velas atras).
    """
    count = closed_candle["td_count"]
    td_perf = bool(closed_candle.get("td_perfected", False))
    close_p = closed_candle["close"]

    td_buy = bool(
        ((count in (-9, -13)) and td_perf)
        or ((count <= -9) and (close_p > candle_2_ago["close"] or close_p > candle_2_ago["high"]))
    )
    td_sell = bool(
        ((count in (9, 13)) and td_perf)
        or ((count >= 9) and (close_p < candle_2_ago["close"] or close_p < candle_2_ago["low"]))
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


def compute_conviction_boost(symbol: str, conf_score: float, is_counter_trend: bool = False) -> float:
    """
    v5.0: Prohibido amplificar riesgo en contratendencia (reduce a 0.5x).
    En tendencia, boost acotado a 1.25x (en lugar de 2.0x) para evitar tail-risk.
    """
    if is_counter_trend:
        return 0.5
    clean_sym = normalize_symbol(symbol)
    if clean_sym in ("BTC", "ETH", "SOL", "BNB"):
        if conf_score >= 0.75:
            return 1.25
        if conf_score >= 0.65:
            return 1.10
    return 1.0


def _compute_soft_sizing(prob: float, meta_weights: Dict[str, Any]) -> float:
    """
    Mapeo estrictamente monotono creciente [0.65x .. 1.25x] para prob >= soft_floor.
    Rechaza unicamente la cola toxica extrema (prob < soft_floor, por defecto 0.20).
    """
    soft_floor = float(meta_weights.get("soft_floor", 0.20))
    soft_ceil = float(meta_weights.get("soft_ceil", 0.85))
    if prob < soft_floor:
        return 0.0
    span = max(1e-6, soft_ceil - soft_floor)
    norm = max(0.0, min(1.0, (prob - soft_floor) / span))
    return 0.65 + norm * (1.25 - 0.65)


def evaluate_hyb_meta_gate(
    closed_candle,
    action: str,
    ema200: float,
    funding_rate: float,
    htf_4h_aligned: bool,
    is_counter_trend: bool,
    params: Dict[str, Any],
    meta_weights: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, float, float]:
    """
    SSOT Meta-Gate L2 para estrategia HYB (v4.0 Soft-Sizing monotono).
    Si meta_weights es None o use_hyb_meta_gate es False, deja pasar con multiplicador 1.0.
    """
    if not meta_weights or not bool(params.get("use_hyb_meta_gate", True)):
        return True, 1.0, 1.0
    feats = extract_meta_features(
        closed_candle,
        action,
        ema200,
        funding_rate=funding_rate,
        htf_4h_aligned=htf_4h_aligned,
        is_trend_mode=(not is_counter_trend),
    )
    prob, _ = predict_meta_probability(feats, meta_weights)
    soft_mult = _compute_soft_sizing(prob, meta_weights)
    if soft_mult <= 0.0:
        return False, round(prob, 4), 0.0
    return True, round(prob, 4), round(soft_mult, 4)


def _apply_meta_gate(
    sig: Dict[str, Any],
    closed_candle,
    ema200: float,
    params: Dict[str, Any],
    funding_rate: float,
    htf_4h_aligned: bool,
    meta_weights: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    is_trend = sig["mode"] == "REGIME_TREND"
    if not meta_weights or not bool(params.get("use_meta_gate", False)):
        sig.setdefault("meta_prob", 1.0)
        sig.setdefault("risk_scale", sig.get("regime_scale", 1.0))
        return sig

    feats = extract_meta_features(
        closed_candle,
        sig["action"],
        ema200,
        funding_rate=funding_rate,
        htf_4h_aligned=htf_4h_aligned,
        is_trend_mode=is_trend,
    )
    prob, bet_mult = predict_meta_probability(feats, meta_weights)
    if bool(params.get("meta_soft_sizing", True)):
        mult = _compute_soft_sizing(prob, meta_weights)
        if mult <= 0.0:
            return None
    else:
        if bet_mult <= 0.0:
            return None
        mult = bet_mult
    sig["meta_prob"] = round(prob, 4)
    sig["risk_scale"] = round(sig.get("regime_scale", 1.0) * mult, 4)
    return sig


def evaluate_orthogonal_signal(
    strategy_type: str,
    closed_candle,
    candle_2_ago,
    adx_val: float,
    ema200: float,
    params: Dict[str, Any],
    funding_rate: float = 0.0,
    htf_4h_aligned: bool = False,
    meta_weights: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    SSOT v4.0 para las estrategias ortogonales (MR y DUAL):
      - MR: conjuncion estricta ADX <= 24 AND p_trend <= 0.45.
      - DUAL: expansion tendencial ante ADX > 24 OR p_trend >= 0.55; zona neutra exige TD9 perf.
      - Fallback determinista por adx_val <= 24 si no hay p_trend.
    """
    strat = strategy_type.upper()
    signal_price = float(closed_candle["close"])
    p_trend_raw = closed_candle.get("p_trend", None)
    has_continuous = p_trend_raw is not None and p_trend_raw == p_trend_raw

    mr_max_pt = float(params.get("regime_mr_max_p_trend", 0.45))
    tr_min_pt = float(params.get("regime_trend_min_p_trend", 0.55))

    # --- v5.0 SLEEVE 1: CORE TREND FOLLOWING PURO (Sin contaminacion MR) ---
    if strat == "TREND":
        adx_min = float(params.get("adx_min", 20.0))
        in_trend = (adx_val >= adx_min) or (has_continuous and float(p_trend_raw) >= tr_min_pt)
        if not in_trend:
            return None

        dc_period = int(params.get("dc_period", 55))
        dc_hi = closed_candle.get(f"dc_high_{dc_period}")
        dc_lo = closed_candle.get(f"dc_low_{dc_period}")
        if dc_hi is None or dc_lo is None or dc_hi != dc_hi or dc_lo != dc_lo:
            return None
        dc_hi_f = float(dc_hi)
        dc_lo_f = float(dc_lo)

        if signal_price > dc_hi_f and signal_price > ema200:
            action = "BUY"
        elif signal_price < dc_lo_f and signal_price < ema200:
            action = "SELL"
        else:
            return None

        sl_mult = float(params.get("atr_sl_trend", 2.0))
        tp_mult = float(params.get("atr_tp_trend", 8.0))
        reg_scale = max(0.75, min(1.05, 0.55 + 0.55 * float(p_trend_raw))) if has_continuous else 1.0
        sig = {
            "action": action,
            "reason": f"TREND DC{dc_period} {'Buy' if action == 'BUY' else 'Sell'}",
            "sl_mult": sl_mult,
            "tp_mult": tp_mult,
            "mode": "REGIME_TREND",
            "regime_scale": round(reg_scale, 4),
            "is_counter_trend": False,
        }
        return _apply_meta_gate(sig, closed_candle, ema200, params, funding_rate, htf_4h_aligned, meta_weights)

    # --- v5.0 SLEEVE 2: TREND-ALIGNED PULLBACK (Reversion a favor de EMA200) ---
    if strat == "PULLBACK":
        pb_adx_max = float(params.get("pb_adx_max", 45.0))
        if adx_val > pb_adx_max:
            return None

        td_buy, td_sell = check_td_signal(closed_candle, candle_2_ago)
        rsi_val = float(closed_candle.get("rsi", 50.0))
        pb_rsi_buy = float(params.get("pb_rsi_buy", 42.0))
        pb_rsi_sell = float(params.get("pb_rsi_sell", 58.0))
        c2_close = float(candle_2_ago["close"])

        # Solo entradas alineadas con la macro tendencia (EMA200) + confirmacion de giro
        action = None
        if signal_price > ema200 and (td_buy or (rsi_val <= pb_rsi_buy and signal_price > c2_close)):
            action = "BUY"
            tag = "TD9" if td_buy else f"RSI {rsi_val:.0f}"
        elif signal_price < ema200 and (td_sell or (rsi_val >= pb_rsi_sell and signal_price < c2_close)):
            action = "SELL"
            tag = "TD9" if td_sell else f"RSI {rsi_val:.0f}"
        else:
            return None

        sl_mult = float(params.get("pb_sl_atr", 1.5))
        tp_mult = float(params.get("pb_tp_atr", 3.0))
        sig = {
            "action": action,
            "reason": f"PULLBACK {tag} {'Buy' if action == 'BUY' else 'Sell'} (EMA200)",
            "sl_mult": sl_mult,
            "tp_mult": tp_mult,
            "mode": "REGIME_PULLBACK",
            "regime_scale": 1.0,
            "is_counter_trend": False,
        }
        return _apply_meta_gate(sig, closed_candle, ema200, params, funding_rate, htf_4h_aligned, meta_weights)

    if strat in ("MR", "TD9_MR"):
        adx_max = float(params.get("adx_max", 24.0))
        if adx_val > adx_max:
            return None
        if has_continuous:
            p_trend = float(p_trend_raw)
            if p_trend > mr_max_pt:
                return None
            p_range = 1.0 - p_trend
            reg_scale = max(0.50, min(1.50, (p_range - 0.25) / 0.35))
        else:
            reg_scale = 1.25

        td_buy, td_sell = check_td_signal(closed_candle, candle_2_ago)
        if not (td_buy or td_sell):
            return None
        action = "BUY" if td_buy else "SELL"
        sig = {
            "action": action,
            "reason": f"MR TD9 {'Buy' if action == 'BUY' else 'Sell'} (Range)",
            "sl_mult": float(params.get("mr_sl_atr", 1.5)),
            "tp_mult": float(params.get("mr_tp_atr", 2.5)),
            "mode": "REGIME_MR",
            "regime_scale": round(reg_scale, 4),
        }
        return _apply_meta_gate(sig, closed_candle, ema200, params, funding_rate, htf_4h_aligned, meta_weights)

    if strat in ("DUAL", "REGIME_DUAL"):
        adx_split = float(params.get("adx_split", 24.0))
        if has_continuous:
            p_trend = float(p_trend_raw)
            in_mr = (adx_val <= adx_split) and (p_trend <= mr_max_pt)
            in_trend = (adx_val > adx_split) or (p_trend >= tr_min_pt)
            in_neutral = (not in_mr) and (not in_trend)
        else:
            in_mr = adx_val <= adx_split
            in_trend = adx_val > adx_split
            in_neutral = False

        if in_mr or in_neutral:
            td_buy, td_sell = check_td_signal(closed_candle, candle_2_ago)
            if td_buy or td_sell:
                if in_neutral and not bool(closed_candle.get("td_perfected", False)):
                    return None
                reg_scale = (
                    0.50
                    if in_neutral
                    else (max(0.50, min(1.30, ((1.0 - float(p_trend_raw)) - 0.25) / 0.35)) if has_continuous else 1.0)
                )
                action = "BUY" if td_buy else "SELL"
                sig = {
                    "action": action,
                    "reason": f"DUAL MR TD9 {'Buy' if action == 'BUY' else 'Sell'}",
                    "sl_mult": float(params.get("mr_sl_atr", 1.5)),
                    "tp_mult": float(params.get("mr_tp_atr", 2.5)),
                    "mode": "REGIME_MR",
                    "regime_scale": round(reg_scale, 4),
                }
                return _apply_meta_gate(sig, closed_candle, ema200, params, funding_rate, htf_4h_aligned, meta_weights)
            return None

        if in_trend:
            dc_period = int(params.get("dc_period", 55))
            dc_hi = closed_candle.get(f"dc_high_{dc_period}")
            dc_lo = closed_candle.get(f"dc_low_{dc_period}")
            if dc_hi is None or dc_lo is None or dc_hi != dc_hi or dc_lo != dc_lo:
                return None
            dc_hi_f = float(dc_hi)
            dc_lo_f = float(dc_lo)
            sl_mult = float(params.get("atr_sl_trend", params.get("trend_sl_atr", 1.5)))
            tp_mult = float(params.get("atr_tp_trend", params.get("trend_tp_atr", 3.0)))
            reg_scale = max(0.65, min(1.05, 0.45 + 0.65 * float(p_trend_raw))) if has_continuous else 1.0

            if signal_price > dc_hi_f and signal_price > ema200:
                action = "BUY"
            elif signal_price < dc_lo_f and signal_price < ema200:
                action = "SELL"
            else:
                return None

            sig = {
                "action": action,
                "reason": f"DUAL Trend DC{dc_period} {'Buy' if action == 'BUY' else 'Sell'}",
                "sl_mult": sl_mult,
                "tp_mult": tp_mult,
                "mode": "REGIME_TREND",
                "regime_scale": round(reg_scale, 4),
            }
            return _apply_meta_gate(sig, closed_candle, ema200, params, funding_rate, htf_4h_aligned, meta_weights)

    return None
