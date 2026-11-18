import argparse
import builtins
import datetime
import datetime as dt_module
import gc
import glob
import json
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import ccxt
import pandas as pd
import requests
from dotenv import load_dotenv

from core.indicators import (
    calculate_adx,
    calculate_atr,
    calculate_rsi,
    calculate_td_sequential,
    calculate_volume_profile,
    detect_divergences,
    prepare_market_indicators,
)
from core.strategy import (
    FLEET_ASSETS,
    FLEET_STRATEGIES,
    FLEET_TIMEFRAMES,
    MIN_CONFIDENCE,
    calculate_confidence_score,
    check_td_signal,
    check_wyckoff_signal,
    compute_conviction_boost,
    compute_conviction_multiplier,
    compute_entry_levels,
    compute_portfolio_dampening,
    compute_rolling_corr_and_vol,
    compute_weekly_context,
    evaluate_hyb_meta_gate,
    evaluate_orthogonal_signal,
    get_base_risk,
    get_scaled_atr,
    load_fleet_params,
    load_meta_weights,
    normalize_symbol,
)

# Defaults globales (respaldo para llamadas legacy; en produccion se pasan explicitos)
TIMEFRAME = "1d"
SYMBOL = "BTC"
STATE_FILE = "state.json"
TRADES_FILE = "trades.json"
INITIAL_BANK = 10000.0
FLEET_OPTIMIZED_FILE = "fleet_optimized.json"
META_WEIGHTS_FILE = "meta_model_weights.json"
FLEET_RISK_FILE = "fleet_risk.json"

MAX_TOTAL_FLEET_TRADES = 6
MAX_DIRECTIONAL_TRADES = 4
MAX_TRADES_PER_SYMBOL = 2
MAX_FLEET_DRAWDOWN_PCT = 15.0

_TELEGRAM_TOKEN: Optional[str] = None
_CHAT_ID: Optional[str] = None
_EXCHANGE = None
_PRINT_INSTALLED = False

_FNG_CACHE: Dict[str, Any] = {"value": 50, "last_fetch": 0.0}
_FUNDING_CACHE: Dict[str, Dict[str, float]] = {}


def _install_timestamped_print():
    global _PRINT_INSTALLED
    if _PRINT_INSTALLED:
        return
    old_print = builtins.print

    def _timestamped_print(*args, **kwargs):
        old_print(f"[{dt_module.datetime.now().strftime('%H:%M:%S')}]", *args, **kwargs)

    builtins.print = _timestamped_print
    _PRINT_INSTALLED = True


def _ensure_env_loaded():
    global _TELEGRAM_TOKEN, _CHAT_ID
    if _TELEGRAM_TOKEN is None:
        load_dotenv()
        _TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
        _CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1097154358")


def get_exchange():
    global _EXCHANGE
    if _EXCHANGE is None:
        _EXCHANGE = ccxt.binance({"enableRateLimit": True})
    return _EXCHANGE


def _send_telegram_async(msg: str):
    _ensure_env_loaded()
    if not _TELEGRAM_TOKEN or not _CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{_TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": _CHAT_ID, "text": msg, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Error sending telegram:", e)


def send_telegram(msg: str):
    threading.Thread(target=_send_telegram_async, args=(msg,), daemon=True).start()


# --- ATOMIC STORAGE & STATE HELPERS ---
def load_state(filepath: Optional[str] = None) -> Dict[str, Any]:
    target = filepath or STATE_FILE
    if os.path.exists(target):
        try:
            with open(target, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            print(f"⚠️ Alerta: {target} corrupto o inaccesible. Retornando IDLE.")
            return {"status": "IDLE"}
    return {"status": "IDLE"}


def save_state(state: Dict[str, Any], filepath: Optional[str] = None):
    target = filepath or STATE_FILE
    tmp_target = f"{target}.tmp"
    try:
        with open(tmp_target, "w") as f:
            json.dump(state, f, allow_nan=False)
        os.replace(tmp_target, target)
    except Exception as e:
        print(f"Error en escritura atómica de {target}: {e}")


def load_trades(filepath: Optional[str] = None) -> list:
    target = filepath or TRADES_FILE
    if os.path.exists(target):
        try:
            with open(target, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            print(f"⚠️ Alerta: {target} corrupto. Iniciando lista vacía.")
            return []
    return []


def save_trades(trades: list, filepath: Optional[str] = None):
    target = filepath or TRADES_FILE
    tmp_target = f"{target}.tmp"
    try:
        with open(tmp_target, "w") as f:
            json.dump(trades, f, allow_nan=False)
        os.replace(tmp_target, target)
    except Exception as e:
        print(f"Error en escritura atómica de {target}: {e}")


def get_bot_params(symbol: str = "BTC", timeframe: str = "4h", strategy: str = "HYB") -> Dict[str, Any]:
    """Carga dinamicamente hiperparametros desde fleet_optimized.json con cache TTL 60s."""
    return load_fleet_params(
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy,
        fleet_file=FLEET_OPTIMIZED_FILE,
        ttl_seconds=60.0,
    )


def get_data(symbol: str = "BTC/USDT", timeframe: str = "4h", limit: int = 350) -> Optional[pd.DataFrame]:
    ex = get_exchange()
    ohlcv = None
    for attempt in range(3):
        try:
            ohlcv = ex.fetch_ohlcv(symbol, timeframe, limit=limit)
            break
        except Exception as e:
            if attempt == 2:
                print(f"❌ Error crítico de red tras 3 reintentos ({symbol} {timeframe}): {e}")
                return None
            time.sleep(2)
    try:
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return prepare_market_indicators(df)
    except Exception as e:
        print(f"Error fetching data ({symbol} {timeframe}): {e}")
        return None


def _check_4h_td9_confluence(symbol: str, action: str) -> bool:
    """
    Comprueba si hay un TD9 reciente en 4H alineado con `action` (BUY/SELL).
    Cubre una ventana de 3 dias (18 velas de 4H). Solo se llama desde bots 1D.
    Falla de forma silenciosa y devuelve False ante cualquier error de red.
    """
    try:
        df4 = get_data(symbol, "4h", limit=25)
        if df4 is None or len(df4) < 5:
            return False
        window = df4.iloc[-19:-1]  # ultimas 18 velas cerradas (3 dias)
        for idx in range(2, len(window)):
            candle = window.iloc[idx]
            candle_2ago = window.iloc[idx - 2]
            td_buy, td_sell = check_td_signal(candle, candle_2ago)
            if action == "BUY" and td_buy:
                return True
            if action == "SELL" and td_sell:
                return True
    except Exception as e:
        print(f"[4H-Gate] Error comprobando confluencia 4H para {symbol}: {e}")
    return False


def get_fleet_position_stats(base_dir: str = ".") -> Dict[str, Any]:
    """
    Escanea state_*.json y trades_*.json para consolidar exposicion global, posiciones activas y drawdown.
    """
    stats: Dict[str, Any] = {
        "total": 0,
        "longs": 0,
        "shorts": 0,
        "by_symbol": {sym: 0 for sym in FLEET_ASSETS},
        "active_positions": [],
        "fleet_drawdown_pct": 0.0,
    }
    for file in glob.glob(os.path.join(base_dir, "state_*.json")):
        try:
            with open(file, "r") as f:
                st = json.load(f)
            if st.get("status") == "IN_TRADE":
                stats["total"] += 1
                pos_side = st.get("position", "BUY")
                if pos_side == "BUY":
                    stats["longs"] += 1
                else:
                    stats["shorts"] += 1
                base = os.path.basename(file)
                parts = base.replace("state_", "").split("_")
                sym_part = parts[0] if parts else ""
                if sym_part in stats["by_symbol"]:
                    stats["by_symbol"][sym_part] += 1
                risk_usd = float(st.get("risk_usd", INITIAL_BANK * 0.02))
                stats["active_positions"].append(
                    {
                        "symbol": sym_part,
                        "position": pos_side,
                        "risk_pct": risk_usd / max(10.0, INITIAL_BANK),
                    }
                )
        except Exception:
            pass

    # Drawdown agregado de cartera sobre los bots con ledger
    trade_files = glob.glob(os.path.join(base_dir, "trades_*.json"))
    if trade_files:
        fleet_count = max(1, len(FLEET_ASSETS) * len(FLEET_TIMEFRAMES) * len(FLEET_STRATEGIES))
        total_initial = INITIAL_BANK * float(fleet_count)
        total_realized = 0.0
        for tf_file in trade_files:
            try:
                with open(tf_file, "r") as f:
                    t_list = json.load(f)
                total_realized += sum(float(t.get("pnl", 0.0)) for t in t_list)
            except Exception:
                pass
        if total_realized < 0 and total_initial > 0:
            stats["fleet_drawdown_pct"] = (abs(total_realized) / total_initial) * 100.0
    return stats


def save_fleet_risk_snapshot(
    corr_matrix: Dict[Tuple[str, str], float],
    vols: Dict[str, float],
    fleet_stats: Dict[str, Any],
    meta_active: bool,
    filepath: str = FLEET_RISK_FILE,
):
    """Persiste de forma atomica la matriz de correlacion 30d y presupuesto de riesgo para el Kiosko."""
    active = fleet_stats.get("active_positions", [])
    net_risk: Dict[str, float] = {}
    for pos in active:
        sym = normalize_symbol(pos.get("symbol", ""))
        sign = 1.0 if pos.get("position", "BUY") == "BUY" else -1.0
        net_risk[sym] = net_risk.get(sym, 0.0) + sign * float(pos.get("risk_pct", 0.02))

    var_p = 0.0
    for s1, r1 in net_risk.items():
        for s2, r2 in net_risk.items():
            rho = 1.0 if s1 == s2 else corr_matrix.get((s1, s2), corr_matrix.get((s2, s1), 0.65))
            var_p += r1 * r2 * rho
    sigma_p_pct = round((var_p ** 0.5) * 100.0, 2) if var_p > 0 else 0.0

    payload = {
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "corr_btc_eth": round(float(corr_matrix.get(("BTC", "ETH"), 0.65)), 2),
        "corr_btc_hype": round(float(corr_matrix.get(("BTC", "HYPE"), 0.65)), 2),
        "corr_eth_hype": round(float(corr_matrix.get(("ETH", "HYPE"), 0.65)), 2),
        "vol_30d": {k: round(float(v) * 100.0, 2) for k, v in vols.items()},
        "fleet_sigma_pct": sigma_p_pct,
        "max_fleet_sigma_pct": 4.5,
        "meta_active": bool(meta_active),
    }
    tmp_target = f"{filepath}.tmp"
    try:
        with open(tmp_target, "w") as f:
            json.dump(payload, f, allow_nan=False)
        os.replace(tmp_target, filepath)
    except Exception as e:
        print(f"Error en escritura atomica de {filepath}: {e}")


_LAST_HEARTBEAT_DAY: Optional[int] = None


def check_and_send_heartbeat(pos_stats: Dict[str, Any], initial_bank: float = 10000.0) -> None:
    """
    Emite un reporte institucional de latido (Heartbeat / Dead Man's Snitch) a partir de las 08:00 UTC
    una vez al dia para verificar la salud operativa del bot sin requerir intervencion humana.
    """
    global _LAST_HEARTBEAT_DAY
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    if now_dt.hour >= 8 and _LAST_HEARTBEAT_DAY != now_dt.day:
        _LAST_HEARTBEAT_DAY = now_dt.day
        active_count = pos_stats.get("total", 0)
        longs = pos_stats.get("longs", 0)
        shorts = pos_stats.get("shorts", 0)

        fleet_count = max(1, len(FLEET_ASSETS) * len(FLEET_TIMEFRAMES) * len(FLEET_STRATEGIES))
        total_initial = initial_bank * float(fleet_count)
        total_realized = 0.0
        for tf_file in glob.glob("trades_*.json"):
            try:
                with open(tf_file, "r") as tf_f:
                    tr_list = json.load(tf_f)
                    total_realized += sum(float(t.get("pnl", 0.0)) for t in tr_list)
            except Exception:
                pass

        total_bank = total_initial + total_realized
        dd_pct = pos_stats.get("fleet_drawdown_pct", 0.0)

        msg = (
            f"🟢 <b>GaTDSEQ DAILY HEARTBEAT</b>\n\n"
            f"<b>Status:</b> Operativo 24/7 (Nominal)\n"
            f"<b>Fleet Equity:</b> ${total_bank:,.2f} USD\n"
            f"<b>Posiciones:</b> {active_count}/9 activas ({longs}L / {shorts}S)\n"
            f"<b>Drawdown:</b> -{dd_pct:.2f}%\n"
            f"<b>Timestamp:</b> {now_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"<i>Todo en orden. Sin intervencion requerida.</i>"
        )
        send_telegram(msg)


def get_fear_and_greed() -> int:
    global _FNG_CACHE
    now = time.time()
    if now - _FNG_CACHE["last_fetch"] < 3600 and _FNG_CACHE["last_fetch"] > 0:
        return int(_FNG_CACHE["value"])
    try:
        resp = requests.get(
            "https://api.alternative.me/fng/?limit=1",
            headers={"User-Agent": "GaTDSEQ/2.6"},
            timeout=4,
        )
        if resp.status_code == 200:
            data = resp.json()
            val = int(data["data"][0]["value"])
            _FNG_CACHE["value"] = val
            _FNG_CACHE["last_fetch"] = now
            return val
    except Exception as e:
        print(f"⚠️ Fear&Greed fallback ({_FNG_CACHE['value']}): {e}")
    return int(_FNG_CACHE["value"])


def get_funding_rate(symbol: str) -> float:
    global _FUNDING_CACHE
    now = time.time()
    clean_sym = symbol.replace("/", "").replace("USDT", "")
    cached = _FUNDING_CACHE.get(clean_sym)
    if cached and (now - cached["last_fetch"] < 900):
        return float(cached["rate"])

    pair = f"{clean_sym}USDT"
    try:
        url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={pair}&limit=1"
        resp = requests.get(url, headers={"User-Agent": "GaTDSEQ/2.6"}, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                rate = float(data[0].get("fundingRate", 0.0))
                _FUNDING_CACHE[clean_sym] = {"rate": rate, "last_fetch": now}
                return rate
    except Exception as e:
        print(f"⚠️ Funding rate fallback 0.0 ({pair}): {e}")
    return 0.0


def _clear_trade_fields(state: Dict[str, Any]):
    trade_keys = [
        "position",
        "entry_price",
        "stop_loss",
        "take_profit",
        "size_btc",
        "size_usd",
        "risk_usd",
        "full_target_risk_usd",
        "leverage",
        "scaled_out",
        "runner_active",
        "reinforced_13",
        "entry_fee_usd",
        "atr_at_entry",
        "trade_id",
        "timestamp",
        "strategy_mode",
        "meta_prob",
        "portfolio_dampening",
        "regime_scale",
    ]
    for k in trade_keys:
        state.pop(k, None)


def execute_reinforcement(
    price: float,
    atr: float,
    state: Dict[str, Any],
    action: str,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    state_file: Optional[str] = None,
    trades_file: Optional[str] = None,
):
    sym = symbol or SYMBOL
    tf = timeframe or TIMEFRAME
    s_file = state_file or STATE_FILE
    t_file = trades_file or TRADES_FILE

    trades = load_trades(t_file)
    current_bank = INITIAL_BANK + sum(float(t.get("pnl", 0.0)) for t in trades)

    # Tope estricto: maximo 50% del riesgo objetivo original y nunca > 3% del bank actual
    full_target = float(state.get("full_target_risk_usd", state.get("risk_usd", 0.0)))
    base_risk_usd = min(full_target * 0.50, current_bank * 0.03)
    if base_risk_usd <= 0:
        return

    print(f"🛡 EL BATALLON (TD13): Refuerzo controlado (+${base_risk_usd:.2f} riesgo maximo).")

    if action == "BUY":
        new_sl = price - (atr * 2.0)
        new_tp_offset = atr * 2.5
    else:
        new_sl = price + (atr * 2.0)
        new_tp_offset = -(atr * 2.5)

    sl_pct = max(0.001, abs(price - new_sl) / price)
    added_usd = min(base_risk_usd / sl_pct, current_bank * 10.0)
    added_btc = added_usd / price

    old_entry = float(state["entry_price"])
    old_usd = float(state["size_usd"])
    old_btc = float(state["size_btc"])

    new_btc = old_btc + added_btc
    new_usd = old_usd + added_usd
    avg_entry = new_usd / new_btc
    new_tp = avg_entry + new_tp_offset

    added_fee = added_usd * 0.0004
    state["entry_fee_usd"] = float(state.get("entry_fee_usd", 0.0)) + added_fee
    state["risk_usd"] = float(state.get("risk_usd", 0.0)) + base_risk_usd
    state["size_btc"] = new_btc
    state["size_usd"] = new_usd
    state["entry_price"] = avg_entry
    state["stop_loss"] = new_sl
    state["take_profit"] = new_tp
    state["reinforced_13"] = True

    save_state(state, s_file)

    msg = (
        f"🚀 <b>DCA DEPLOYED | {sym} [{tf}]</b>\n\n"
        f"<b>Trigger:</b> TD-13 Exhaustion\n"
        f"<b>Type:</b> MARKET {action} (Reinforcement)\n"
        f"<b>New Avg Entry:</b> ${avg_entry:,.2f} (Was ${old_entry:,.2f})\n"
        f"<b>Capital Added:</b> ${added_usd:,.2f} ({added_btc:.4f} {sym})\n"
        f"<b>Total Position:</b> ${new_usd:,.2f} ({new_btc:.4f} {sym})\n"
        f"<b>New Stop Loss:</b> ${new_sl:,.2f}\n"
        f"<b>New Take Profit:</b> ${new_tp:,.2f}"
    )
    send_telegram(msg)
    print(f"Refuerzo DCA Ejecutado a ${price:.2f} | Nuevo Avg: ${avg_entry:.2f}")


def execute_trade(
    action: str,
    price: float,
    sl: float,
    tp: float,
    reason: str,
    trigger_time: Optional[str] = None,
    risk_pct: float = 0.01,
    atr: Optional[float] = None,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    state_file: Optional[str] = None,
    trades_file: Optional[str] = None,
    existing_state: Optional[Dict[str, Any]] = None,
    strategy_mode: str = "HYB",
):
    sym = symbol or SYMBOL
    tf = timeframe or TIMEFRAME
    s_file = state_file or STATE_FILE
    t_file = trades_file or TRADES_FILE

    # Invariante direccional
    if action == "BUY" and not (sl < price < tp):
        raise ValueError(f"Invariante BUY violada: sl={sl}, entry={price}, tp={tp}")
    if action == "SELL" and not (tp < price < sl):
        raise ValueError(f"Invariante SELL violada: tp={tp}, entry={price}, sl={sl}")

    time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trade_id = str(int(time.time()))

    trades = load_trades(t_file)
    current_bank = INITIAL_BANK + sum(float(t.get("pnl", 0.0)) for t in trades)
    if current_bank <= 10.0:
        print(f"⚠️ Operación abortada: Bank insuficiente (${current_bank:.2f}).")
        return

    risk_amount = current_bank * risk_pct
    sl_dist_price = abs(price - sl)
    if sl_dist_price == 0:
        sl_dist_price = 0.00001

    position_size_btc = risk_amount / sl_dist_price
    position_size_usd = position_size_btc * price

    required_leverage = max(1.0, position_size_usd / current_bank)
    MAX_LEVERAGE = 50.0
    if required_leverage > MAX_LEVERAGE:
        print(f"⚠️ Alerta: Apalancamiento ({required_leverage:.1f}x) supera {MAX_LEVERAGE}x. Capping a {MAX_LEVERAGE}x.")
        required_leverage = MAX_LEVERAGE
        position_size_usd = current_bank * MAX_LEVERAGE
        position_size_btc = position_size_usd / price
        actual_risk_amount = position_size_btc * sl_dist_price
    else:
        actual_risk_amount = risk_amount

    if position_size_usd < 10.0:
        print(f"⚠️ Operación abortada: Tamaño (${position_size_usd:.2f}) < $10.")
        return

    entry_fee_usd = position_size_usd * 0.0004

    # Preservar telemetria y cooldown previos al actualizar el estado
    state = dict(existing_state) if existing_state is not None else load_state(s_file)
    _clear_trade_fields(state)
    state.update(
        {
            "status": "IN_TRADE",
            "entry_fee_usd": entry_fee_usd,
            "trade_id": trade_id,
            "position": action,
            "entry_price": price,
            "stop_loss": sl,
            "take_profit": tp,
            "timestamp": time_str,
            "size_btc": position_size_btc,
            "size_usd": position_size_usd,
            "risk_usd": actual_risk_amount,
            "full_target_risk_usd": actual_risk_amount,
            "atr_at_entry": float(atr) if atr is not None else sl_dist_price,
            "leverage": required_leverage,
            "last_trigger_time": trigger_time,
            "scaled_out": False,
            "runner_active": False,
            "reinforced_13": False,
            "strategy_mode": strategy_mode,
        }
    )
    save_state(state, s_file)

    trades.append(
        {
            "trade_id": trade_id,
            "time": time_str,
            "type": "COMPRA (Apertura)" if action == "BUY" else "VENTA (Apertura)",
            "reason": reason,
            "price": price,
            "pnl": 0.0,
        }
    )
    save_trades(trades, t_file)

    direction = "LONG" if action == "BUY" else "SHORT"
    icon = "🟩" if action == "BUY" else "🟥"
    msg = (
        f"{icon} <b>ORDER EXECUTED | {sym} [{tf}]</b>\n\n"
        f"<b>Type:</b> MARKET {direction}\n"
        f"<b>Entry Price:</b> ${price:,.2f}\n"
        f"<b>Stop Loss:</b> ${sl:,.2f}\n"
        f"<b>Take Profit:</b> ${tp:,.2f}\n"
        f"<b>Position Size:</b> ${position_size_usd:,.2f} ({position_size_btc:.4f} {sym})\n"
        f"<b>Leverage:</b> {required_leverage:.2f}x\n"
        f"<b>Risk Exposure:</b> ${actual_risk_amount:,.2f} ({(actual_risk_amount / current_bank) * 100:.2f}%)\n"
        f"<b>Current Bank:</b> ${current_bank:,.2f}\n"
        f"<b>Model:</b> {reason}"
    )
    send_telegram(msg)
    print(f"Trade {action} Ejecutado a ${price:.2f} | Inversión: ${position_size_usd:.2f} | Riesgo: ${actual_risk_amount:.2f}")


def check_exit_conditions(
    live_candle,
    closed_candle,
    atr: float,
    state: Dict[str, Any],
    weekly_context: Optional[Dict[str, Any]] = None,
    strategy_type: str = "HYB",
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    state_file: Optional[str] = None,
    trades_file: Optional[str] = None,
):
    sym = symbol or SYMBOL
    tf = timeframe or TIMEFRAME
    s_file = state_file or STATE_FILE
    t_file = trades_file or TRADES_FILE

    action = state["position"]
    current_live_price = float(live_candle["close"])
    current_closed_price = float(closed_candle["close"])
    low_price = float(live_candle["low"])
    high_price = float(live_candle["high"])

    sl = float(state["stop_loss"])
    tp = state.get("take_profit")
    tp_val = float(tp) if tp is not None else None
    entry = float(state["entry_price"])
    trade_id = state.get("trade_id", str(int(time.time())))
    size_btc = float(state.get("size_btc", 0.15))
    trade_atr = float(state.get("atr_at_entry", atr))

    closed = False
    pnl_dollars = 0.0
    updated_sl = sl
    close_reason = ""

    strat_mode = state.get("strategy_mode", strategy_type)
    is_regime_mr = (strat_mode == "REGIME_MR") or (strategy_type == "MR")
    is_regime_trend = (strat_mode == "REGIME_TREND")
    is_hybrid = (not is_regime_mr) and (not is_regime_trend)

    # 1. Macro Weekly Confluence Shield (solo para HYB)
    if is_hybrid and weekly_context:
        is_sell_exh = weekly_context.get("is_sell_exhaustion_active", False)
        is_buy_exh = weekly_context.get("is_buy_exhaustion_active", False)
        if action == "BUY" and is_sell_exh and current_live_price > entry and updated_sl < entry:
            updated_sl = entry
            state["stop_loss"] = updated_sl
            print(f"🛡 MACRO SHIELD: Corrección semanal activa en {sym}. Stop a BE (${updated_sl:.2f}).")
            send_telegram(f"🛡 <b>MACRO SHIELD | {sym} [{tf}]</b>\nWeekly pullback confirmed. Breakeven shield activated on LONG.")
        elif action == "SELL" and is_buy_exh and current_live_price < entry and updated_sl > entry:
            updated_sl = entry
            state["stop_loss"] = updated_sl
            print(f"🛡 MACRO SHIELD: Rebote semanal activo en {sym}. Stop a BE (${updated_sl:.2f}).")
            send_telegram(f"🛡 <b>MACRO SHIELD | {sym} [{tf}]</b>\nWeekly rebound confirmed. Breakeven shield activated on SHORT.")

    # 2. Parametros dinamicos
    bot_params = get_bot_params(sym, tf, strategy_type)
    be_mult = max(1.0, float(bot_params.get("be_threshold_atr", 1.5)))
    so_mult = float(bot_params.get("scale_out_atr", 2.0))
    so_pct = float(bot_params.get("scale_out_pct", 0.5))
    enable_so = is_hybrid and bool(bot_params.get("enable_scale_out", True))

    # 3. Breakeven Shield (solo para HYB)
    if is_hybrid:
        if action == "BUY" and high_price >= (entry + (trade_atr * be_mult)):
            if updated_sl < entry:
                updated_sl = entry
                state["stop_loss"] = updated_sl
                print(f"✅ BREAK EVEN ACTIVADO! SL subido a ${updated_sl:.2f} (+{be_mult:.2f} ATR)")
                send_telegram(f"🛡 <b>BREAKEVEN SHIELD | {sym} [{tf}]</b>\nStop Loss moved to Entry (${entry:,.2f}).")
        elif action == "SELL" and low_price <= (entry - (trade_atr * be_mult)):
            if updated_sl > entry:
                updated_sl = entry
                state["stop_loss"] = updated_sl
                print(f"✅ BREAK EVEN ACTIVADO! SL bajado a ${updated_sl:.2f} (+{be_mult:.2f} ATR)")
                send_telegram(f"🛡 <b>BREAKEVEN SHIELD | {sym} [{tf}]</b>\nStop Loss moved to Entry (${entry:,.2f}).")

    if action == "BUY":
        if enable_so and high_price >= entry + (trade_atr * so_mult) and not state.get("scaled_out", False):
            so_price = entry + (trade_atr * so_mult)
            so_units = size_btc * so_pct
            alloc_fee = float(state.get("entry_fee_usd", 0.0)) * so_pct
            partial_pnl = ((so_price - entry) * so_units) - alloc_fee - (so_price * so_units * 0.0004)
            trades = load_trades(t_file)
            trades.append(
                {
                    "trade_id": trade_id + "_partial",
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "type": f"VENTA (Cierre Parcial {int(so_pct * 100)}%)",
                    "reason": f"Scale-Out Tactico (+{so_mult:.1f} ATR)",
                    "price": so_price,
                    "pnl": partial_pnl,
                }
            )
            save_trades(trades, t_file)

            size_btc = size_btc - so_units
            state["size_btc"] = size_btc
            state["size_usd"] = float(state.get("size_usd", 0.0)) * (1.0 - so_pct)
            state["entry_fee_usd"] = float(state.get("entry_fee_usd", 0.0)) - alloc_fee
            state["scaled_out"] = True
            if updated_sl < entry:
                updated_sl = entry
                state["stop_loss"] = updated_sl
            save_state(state, s_file)
            send_telegram(f"💰 <b>SCALE-OUT ({int(so_pct * 100)}%) | {sym} [{tf}]</b>\nPartial PnL: ${partial_pnl:,.2f}")

        if is_regime_trend or is_hybrid:
            trail_mult = 2.5 if state.get("runner_active") else (3.5 if is_regime_trend else float(bot_params.get("trailing_atr", 2.0)))
            new_sl = current_closed_price - (trade_atr * trail_mult)
            if new_sl > updated_sl:
                updated_sl = new_sl
                print(f"Trailing Stop (Buy) actualizado a ${updated_sl:.2f}")

        dc_low_10 = closed_candle.get("dc_low_10")
        ch_exit = is_regime_trend and dc_low_10 is not None and dc_low_10 == dc_low_10 and current_closed_price < float(dc_low_10)

        if low_price <= updated_sl:
            close_reason = "Runner Trailing Exit (+Macro Trend)" if state.get("runner_active") else (
                "Stop Loss" if updated_sl < entry else "Breakeven / Trailing SL"
            )
            pnl_dollars = (updated_sl - entry) * size_btc
            exit_fee = (updated_sl * size_btc) * 0.0004
            pnl_dollars -= (float(state.get("entry_fee_usd", 0.0)) + exit_fee)
            closed = True
            current_live_price = updated_sl
        elif ch_exit:
            close_reason = "Donchian Channel Exit"
            pnl_dollars = (current_live_price - entry) * size_btc
            exit_fee = (current_live_price * size_btc) * 0.0004
            pnl_dollars -= (float(state.get("entry_fee_usd", 0.0)) + exit_fee)
            closed = True
        elif not state.get("runner_active") and tp_val is not None and high_price >= tp_val:
            if not is_hybrid:
                close_reason = "Take Profit"
                pnl_dollars = (tp_val - entry) * size_btc
                exit_fee = (tp_val * size_btc) * 0.0004
                pnl_dollars -= (float(state.get("entry_fee_usd", 0.0)) + exit_fee)
                closed = True
                current_live_price = tp_val
            else:
                tp2_units = size_btc * 0.5
                alloc_fee = float(state.get("entry_fee_usd", 0.0)) * 0.5
                tp2_pnl = ((tp_val - entry) * tp2_units) - alloc_fee - (tp_val * tp2_units * 0.0004)
                pct_label = "25%" if state.get("scaled_out") else "50%"
                trades = load_trades(t_file)
                trades.append(
                    {
                        "trade_id": trade_id + "_tp2",
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "type": f"VENTA (Cierre Parcial TP2 {pct_label})",
                        "reason": "Take Profit Objetivo",
                        "price": tp_val,
                        "pnl": tp2_pnl,
                    }
                )
                save_trades(trades, t_file)

                state["size_btc"] = size_btc - tp2_units
                state["size_usd"] = float(state.get("size_usd", 0.0)) * 0.5
                state["entry_fee_usd"] = float(state.get("entry_fee_usd", 0.0)) - alloc_fee
                state["runner_active"] = True
                updated_sl = max(updated_sl, entry + (trade_atr * 2.0))
                state["stop_loss"] = updated_sl
                state["take_profit"] = None  # JSON estandar valido (null)
                save_state(state, s_file)
                send_telegram(f"🚀 <b>RUNNER DEPLOYED ({pct_label}) | {sym} [{tf}]</b>\nTP2 Locked: +${tp2_pnl:,.2f}")

    elif action == "SELL":
        if enable_so and low_price <= entry - (trade_atr * so_mult) and not state.get("scaled_out", False):
            so_price = entry - (trade_atr * so_mult)
            so_units = size_btc * so_pct
            alloc_fee = float(state.get("entry_fee_usd", 0.0)) * so_pct
            partial_pnl = ((entry - so_price) * so_units) - alloc_fee - (so_price * so_units * 0.0004)
            trades = load_trades(t_file)
            trades.append(
                {
                    "trade_id": trade_id + "_partial",
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "type": f"COMPRA (Cierre Parcial {int(so_pct * 100)}%)",
                    "reason": f"Scale-Out Tactico (+{so_mult:.1f} ATR)",
                    "price": so_price,
                    "pnl": partial_pnl,
                }
            )
            save_trades(trades, t_file)

            size_btc = size_btc - so_units
            state["size_btc"] = size_btc
            state["size_usd"] = float(state.get("size_usd", 0.0)) * (1.0 - so_pct)
            state["entry_fee_usd"] = float(state.get("entry_fee_usd", 0.0)) - alloc_fee
            state["scaled_out"] = True
            if updated_sl > entry:
                updated_sl = entry
                state["stop_loss"] = updated_sl
            save_state(state, s_file)
            send_telegram(f"💰 <b>SCALE-OUT ({int(so_pct * 100)}%) | {sym} [{tf}]</b>\nPartial PnL: ${partial_pnl:,.2f}")

        if is_regime_trend or is_hybrid:
            trail_mult = 2.5 if state.get("runner_active") else (3.5 if is_regime_trend else float(bot_params.get("trailing_atr", 2.0)))
            new_sl = current_closed_price + (trade_atr * trail_mult)
            if new_sl < updated_sl:
                updated_sl = new_sl
                print(f"Trailing Stop (Sell) actualizado a ${updated_sl:.2f}")

        dc_high_10 = closed_candle.get("dc_high_10")
        ch_exit = is_regime_trend and dc_high_10 is not None and dc_high_10 == dc_high_10 and current_closed_price > float(dc_high_10)

        if high_price >= updated_sl:
            close_reason = "Runner Trailing Exit (+Macro Trend)" if state.get("runner_active") else (
                "Stop Loss" if updated_sl > entry else "Breakeven / Trailing SL"
            )
            pnl_dollars = (entry - updated_sl) * size_btc
            exit_fee = (updated_sl * size_btc) * 0.0004
            pnl_dollars -= (float(state.get("entry_fee_usd", 0.0)) + exit_fee)
            closed = True
            current_live_price = updated_sl
        elif ch_exit:
            close_reason = "Donchian Channel Exit"
            pnl_dollars = (entry - current_live_price) * size_btc
            exit_fee = (current_live_price * size_btc) * 0.0004
            pnl_dollars -= (float(state.get("entry_fee_usd", 0.0)) + exit_fee)
            closed = True
        elif not state.get("runner_active") and tp_val is not None and low_price <= tp_val:
            if not is_hybrid:
                close_reason = "Take Profit"
                pnl_dollars = (entry - tp_val) * size_btc
                exit_fee = (tp_val * size_btc) * 0.0004
                pnl_dollars -= (float(state.get("entry_fee_usd", 0.0)) + exit_fee)
                closed = True
                current_live_price = tp_val
            else:
                tp2_units = size_btc * 0.5
                alloc_fee = float(state.get("entry_fee_usd", 0.0)) * 0.5
                tp2_pnl = ((entry - tp_val) * tp2_units) - alloc_fee - (tp_val * tp2_units * 0.0004)
                pct_label = "25%" if state.get("scaled_out") else "50%"
                trades = load_trades(t_file)
                trades.append(
                    {
                        "trade_id": trade_id + "_tp2",
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "type": f"COMPRA (Cierre Parcial TP2 {pct_label})",
                        "reason": "Take Profit Objetivo",
                        "price": tp_val,
                        "pnl": tp2_pnl,
                    }
                )
                save_trades(trades, t_file)

                state["size_btc"] = size_btc - tp2_units
                state["size_usd"] = float(state.get("size_usd", 0.0)) * 0.5
                state["entry_fee_usd"] = float(state.get("entry_fee_usd", 0.0)) - alloc_fee
                state["runner_active"] = True
                updated_sl = min(updated_sl, entry - (trade_atr * 2.0))
                state["stop_loss"] = updated_sl
                state["take_profit"] = None  # JSON estandar valido (null)
                save_state(state, s_file)
                send_telegram(f"🚀 <b>RUNNER DEPLOYED ({pct_label}) | {sym} [{tf}]</b>\nTP2 Locked: +${tp2_pnl:,.2f}")

    if updated_sl != sl and not closed:
        state["stop_loss"] = updated_sl
        save_state(state, s_file)

    if closed:
        trades = load_trades(t_file)
        current_bank = INITIAL_BANK + sum(float(t.get("pnl", 0.0)) for t in trades)
        pnl_pct_on_bank = (pnl_dollars / current_bank) * 100 if current_bank > 0 else 0.0
        new_bank = current_bank + pnl_dollars

        print(f"Operación cerrada ({close_reason}). PnL: ${pnl_dollars:.2f} ({pnl_pct_on_bank:.2f}%)")

        trades.append(
            {
                "trade_id": trade_id + "_close",
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "VENTA (Cierre)" if action == "BUY" else "COMPRA (Cierre)",
                "reason": close_reason,
                "price": current_live_price,
                "pnl": pnl_dollars,
            }
        )
        save_trades(trades, t_file)

        if close_reason == "Stop Loss":
            cooldown_map = {"5m": 900, "15m": 2700, "1h": 10800, "4h": 43200, "1d": 259200, "1w": 1209600}
            state["last_sl_time"] = time.time()
            state["sl_cooldown_secs"] = cooldown_map.get(tf, 43200)

        _clear_trade_fields(state)
        state["status"] = "IDLE"
        save_state(state, s_file)

        emoji = "🟩" if pnl_dollars > 0 else "🟥"
        result_str = "PROFIT" if pnl_dollars > 0 else "LOSS"
        sign = "+" if pnl_dollars > 0 else ""
        send_telegram(
            f"{emoji} <b>POSITION CLOSED | {sym} [{tf}]</b>\n\n"
            f"<b>Trigger:</b> {close_reason}\n"
            f"<b>Exit Price:</b> ${current_live_price:,.2f}\n"
            f"<b>Net {result_str}:</b> {sign}${pnl_dollars:,.2f}\n"
            f"<b>Updated Bank:</b> ${new_bank:,.2f}"
        )


def analyze_market(
    df: pd.DataFrame,
    bot_id: str,
    strategy_type: str,
    precomputed_context: Optional[Dict[str, Any]] = None,
    weekly_context: Optional[Dict[str, Any]] = None,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    portfolio_context: Optional[Dict[str, Any]] = None,
):
    sym = symbol or bot_id.split("_")[0] or SYMBOL
    tf = timeframe or TIMEFRAME
    s_file = f"state_{bot_id}_{tf}.json"
    t_file = f"trades_{bot_id}_{tf}.json"

    closed_candle = df.iloc[-2]
    live_candle = df.iloc[-1]

    current_live_price = float(closed_candle["close"])
    # Guard contra activos recien listados sin historia suficiente para EMA200 (ej. HYPE 1w/1d)
    if len(df) >= 200:
        ema200 = float(closed_candle["ema_200"])
    elif len(df) >= 50:
        ema200 = float(df["close"].iloc[:-1].ewm(span=50, adjust=False).mean().iloc[-1])
    else:
        ema200 = current_live_price  # Neutraliza sesgo direccional falso cuando hay < 50 velas
    rsi = float(closed_candle["rsi"])
    raw_atr = float(closed_candle["atr"])
    atr = get_scaled_atr(raw_atr, current_live_price, tf)

    count = int(closed_candle["td_count"])
    countdown = int(closed_candle["td_countdown"])
    trigger_time = str(closed_candle["timestamp"])

    if precomputed_context and "vp_data" in precomputed_context:
        vp_data = precomputed_context["vp_data"]
        divergence = precomputed_context.get("divergence")
    else:
        closed_slice = df.iloc[:-1]
        vp_data = calculate_volume_profile(closed_slice.tail(min(300, len(closed_slice))), bins=20)
        divergence = detect_divergences(closed_slice)

    poc, vah, val = vp_data["poc"], vp_data["vah"], vp_data["val"]
    avg_vol = float(df["volume"].iloc[-21:-1].mean())

    state = load_state(s_file)
    div_str = divergence or "NONE"
    td_perf = bool(closed_candle.get("td_perfected", False))
    tdst_res_val = round(float(closed_candle.get("tdst_res", 0.0)), 2)
    tdst_sup_val = round(float(closed_candle.get("tdst_sup", 0.0)), 2)
    p_trend_val = round(float(closed_candle.get("p_trend", 0.5)), 3)
    ker_val = round(float(closed_candle.get("ker", 0.5)), 3)
    vr_val = round(float(closed_candle.get("vr", 1.0)), 3)
    adx_rounded = round(float(closed_candle.get("adx", 0.0)), 1)
    if adx_rounded > 24.0:
        regime_label = "TREND"
    elif p_trend_val <= 0.45:
        regime_label = "RANGE"
    else:
        regime_label = "NEUTRAL"
    vols_map = (portfolio_context or {}).get("vols", {})
    vol_30d = vols_map.get(normalize_symbol(sym))
    meta_weights = load_meta_weights(strategy_type, weights_file=META_WEIGHTS_FILE)

    state_dirty = False
    updates = {
        "poc": poc,
        "wyckoff_div": div_str,
        "td_count": count,
        "td_countdown": countdown,
        "td_perfected": td_perf,
        "tdst_res": tdst_res_val,
        "tdst_sup": tdst_sup_val,
        "adx": adx_rounded,
        "p_trend": p_trend_val,
        "ker": ker_val,
        "vr": vr_val,
        "regime_label": regime_label,
        "meta_active": meta_weights is not None,
    }
    if vol_30d is not None:
        updates["vol_30d"] = round(float(vol_30d) * 100.0, 2)
    if weekly_context:
        updates["w_td_count"] = int(weekly_context.get("td_count", 0))
        updates["w_td_perfected"] = bool(weekly_context.get("td_perfected", False))
        updates["w_tdst_res"] = round(float(weekly_context.get("tdst_res", 0.0)), 2)
        updates["w_tdst_sup"] = round(float(weekly_context.get("tdst_sup", 0.0)), 2)
    for k, v in updates.items():
        if state.get(k) != v:
            state[k] = v
            state_dirty = True
    if state_dirty:
        save_state(state, s_file)

    if abs(count) >= 7 or state.get("status") == "IN_TRADE":
        adx_log = float(closed_candle.get("adx", 0.0))
        print(
            f"[{bot_id}] {sym} [{tf}] [{strategy_type}] | Price: ${current_live_price:,.2f} | "
            f"TD: {count} | RSI: {rsi:.1f} | ADX: {adx_log:.1f} | P_TREND: {p_trend_val:.2f} ({regime_label}) | EMA200: ${ema200:,.2f}"
        )

    if state.get("status") == "IDLE":
        last_sl = float(state.get("last_sl_time", 0.0))
        cooldown = float(state.get("sl_cooldown_secs", 0.0))
        if cooldown > 0 and (time.time() - last_sl) < cooldown:
            rem_h = (cooldown - (time.time() - last_sl)) / 3600.0
            print(f"[{bot_id}] Cooldown post-SL activo: {rem_h:.1f}h restantes.")
            return

        if strategy_type in ("MR", "DUAL"):
            adx_val = float(closed_candle.get("adx", 0.0))
            bot_params = get_bot_params(sym, tf, strategy_type)
            funding_val = get_funding_rate(sym) if meta_weights else 0.0
            htf_aligned = False
            sig = evaluate_orthogonal_signal(
                strategy_type,
                closed_candle,
                df.iloc[-3],
                adx_val,
                ema200,
                bot_params,
                funding_rate=funding_val,
                htf_4h_aligned=htf_aligned,
                meta_weights=None,
            )
            if sig is not None and meta_weights and bool(bot_params.get("use_meta_gate", False)):
                htf_aligned = _check_4h_td9_confluence(sym, sig["action"])
                sig = evaluate_orthogonal_signal(
                    strategy_type,
                    closed_candle,
                    df.iloc[-3],
                    adx_val,
                    ema200,
                    bot_params,
                    funding_rate=funding_val,
                    htf_4h_aligned=htf_aligned,
                    meta_weights=meta_weights,
                )
            if sig is not None:
                _enter_orthogonal(
                    sig=sig,
                    price=current_live_price,
                    atr=atr,
                    trigger_time=trigger_time,
                    bot_id=bot_id,
                    symbol=sym,
                    timeframe=tf,
                    state=state,
                    state_file=s_file,
                    trades_file=t_file,
                    portfolio_context=portfolio_context,
                )
            return

        td_buy, td_sell = check_td_signal(closed_candle, df.iloc[-3])
        wyckoff_spring, wyckoff_upthrust = check_wyckoff_signal(closed_candle, vah, val, avg_vol)

        trigger_buy = False
        trigger_sell = False
        reason_buy = ""
        reason_sell = ""

        if strategy_type in ("TD9", "HYB"):
            if td_buy:
                trigger_buy = True
                reason_buy = "TD9 Buy"
            if td_sell:
                trigger_sell = True
                reason_sell = "TD9 Sell"

            if strategy_type == "HYB" and trigger_buy and "TD9" in reason_buy:
                td_state = load_state(f"state_{sym}_TD9_{tf}.json")
                if td_state.get("last_trigger_time") == trigger_time or td_state.get("status") == "IN_TRADE":
                    trigger_buy = False
                    reason_buy = ""
            if strategy_type == "HYB" and trigger_sell and "TD9" in reason_sell:
                td_state = load_state(f"state_{sym}_TD9_{tf}.json")
                if td_state.get("last_trigger_time") == trigger_time or td_state.get("status") == "IN_TRADE":
                    trigger_sell = False
                    reason_sell = ""

        if strategy_type in ("WYK", "HYB"):
            if wyckoff_spring and not trigger_buy:
                trigger_buy = True
                reason_buy = "Wyckoff Spring"
            if strategy_type == "HYB" and trigger_buy and "Wyckoff" in reason_buy:
                wyk_state = load_state(f"state_{sym}_WYK_{tf}.json")
                if wyk_state.get("last_trigger_time") == trigger_time or wyk_state.get("status") == "IN_TRADE":
                    trigger_buy = False
                    reason_buy = ""
            if wyckoff_upthrust and not trigger_sell:
                trigger_sell = True
                reason_sell = "Wyckoff Upthrust"
            if strategy_type == "HYB" and trigger_sell and "Wyckoff" in reason_sell:
                wyk_state = load_state(f"state_{sym}_WYK_{tf}.json")
                if wyk_state.get("last_trigger_time") == trigger_time or wyk_state.get("status") == "IN_TRADE":
                    trigger_sell = False
                    reason_sell = ""

        if trigger_buy and rsi < 70:
            _evaluate_and_enter(
                action="BUY",
                signal_reason=reason_buy,
                closed_candle=closed_candle,
                price=current_live_price,
                ema200=ema200,
                rsi=rsi,
                atr=atr,
                divergence=divergence,
                trigger_time=trigger_time,
                weekly_context=weekly_context,
                bot_id=bot_id,
                strategy_type=strategy_type,
                symbol=sym,
                timeframe=tf,
                state=state,
                state_file=s_file,
                trades_file=t_file,
                portfolio_context=portfolio_context,
            )
        elif trigger_sell and rsi > 30:
            _evaluate_and_enter(
                action="SELL",
                signal_reason=reason_sell,
                closed_candle=closed_candle,
                price=current_live_price,
                ema200=ema200,
                rsi=rsi,
                atr=atr,
                divergence=divergence,
                trigger_time=trigger_time,
                weekly_context=weekly_context,
                bot_id=bot_id,
                strategy_type=strategy_type,
                symbol=sym,
                timeframe=tf,
                state=state,
                state_file=s_file,
                trades_file=t_file,
                portfolio_context=portfolio_context,
            )

    elif state.get("status") == "IN_TRADE":
        pos = state.get("position")
        strat_mode = state.get("strategy_mode", strategy_type)
        if strat_mode == "HYB":
            if pos == "BUY" and countdown == -13 and not state.get("reinforced_13"):
                execute_reinforcement(
                    current_live_price, atr, state, "BUY", symbol=sym, timeframe=tf, state_file=s_file, trades_file=t_file
                )
            elif pos == "SELL" and countdown == 13 and not state.get("reinforced_13"):
                execute_reinforcement(
                    current_live_price, atr, state, "SELL", symbol=sym, timeframe=tf, state_file=s_file, trades_file=t_file
                )
        check_exit_conditions(
            live_candle,
            closed_candle,
            atr,
            state,
            weekly_context,
            strategy_type,
            symbol=sym,
            timeframe=tf,
            state_file=s_file,
            trades_file=t_file,
        )


def _enter_orthogonal(
    sig: Dict[str, Any],
    price: float,
    atr: float,
    trigger_time: str,
    bot_id: str,
    symbol: str,
    timeframe: str,
    state: Dict[str, Any],
    state_file: str,
    trades_file: str,
    portfolio_context: Optional[Dict[str, Any]] = None,
):
    action = sig["action"]
    fleet_stats = get_fleet_position_stats()
    if fleet_stats.get("fleet_drawdown_pct", 0.0) >= MAX_FLEET_DRAWDOWN_PCT:
        print(f"🛑 CIRCUIT BREAKER: Drawdown {fleet_stats['fleet_drawdown_pct']:.2f}% >= {MAX_FLEET_DRAWDOWN_PCT}%.")
        return
    if fleet_stats["total"] >= MAX_TOTAL_FLEET_TRADES:
        print(f"🛑 PORTFOLIO SHIELD [{bot_id}]: Cap total ({fleet_stats['total']}/{MAX_TOTAL_FLEET_TRADES}).")
        return
    dir_key = "longs" if action == "BUY" else "shorts"
    if fleet_stats[dir_key] >= MAX_DIRECTIONAL_TRADES:
        print(f"🛑 CORRELATION SHIELD [{bot_id}]: Cap direccional {action} alcanzado.")
        return
    if fleet_stats["by_symbol"].get(symbol, 0) >= MAX_TRADES_PER_SYMBOL:
        print(f"🛑 ASSET SHIELD [{bot_id}]: Cap de {symbol} alcanzado.")
        return
    if state.get("last_trigger_time") == trigger_time:
        return

    sl_mult = float(sig["sl_mult"])
    tp_mult = float(sig["tp_mult"])
    if action == "BUY":
        sl = price - (atr * sl_mult)
        tp = price + (atr * tp_mult)
    else:
        sl = price + (atr * sl_mult)
        # Bounded TP: ensure TP never drops to <= 0 on extreme volatility
        tp = max(price * 0.05, price - (atr * tp_mult))

    p_ctx = portfolio_context or {}
    vol_30d = p_ctx.get("vols", {}).get(normalize_symbol(symbol))
    corr_matrix = p_ctx.get("corr_matrix")
    base_risk = get_base_risk(symbol, timeframe, realized_vol_30d=vol_30d)
    risk_scale = float(sig.get("risk_scale", sig.get("regime_scale", 1.0)))
    cand_risk = base_risk * risk_scale
    portfolio_dampening = compute_portfolio_dampening(
        symbol, action, cand_risk, fleet_stats.get("active_positions", []), corr_matrix=corr_matrix
    )
    final_risk = cand_risk * portfolio_dampening
    if final_risk <= 1e-6:
        print(f"🛑 PORTFOLIO RISK BUDGET [{bot_id}]: Ex-ante sigma excedido.")
        return

    state["portfolio_dampening"] = round(portfolio_dampening, 2)
    state["regime_scale"] = round(float(sig.get("regime_scale", 1.0)), 2)
    if "meta_prob" in sig:
        state["meta_prob"] = round(float(sig["meta_prob"]), 2)

    execute_trade(
        action=action,
        price=price,
        sl=sl,
        tp=tp,
        reason=sig["reason"],
        trigger_time=trigger_time,
        risk_pct=final_risk,
        atr=atr,
        symbol=symbol,
        timeframe=timeframe,
        state_file=state_file,
        trades_file=trades_file,
        existing_state=state,
        strategy_mode=sig["mode"],
    )


def _evaluate_and_enter(
    action: str,
    signal_reason: str,
    closed_candle,
    price: float,
    ema200: float,
    rsi: float,
    atr: float,
    divergence: Optional[str],
    trigger_time: str,
    weekly_context: Optional[Dict[str, Any]],
    bot_id: str,
    strategy_type: str,
    symbol: str,
    timeframe: str,
    state: Dict[str, Any],
    state_file: str,
    trades_file: str,
    portfolio_context: Optional[Dict[str, Any]] = None,
):
    is_counter_trend = (price < ema200) if action == "BUY" else (price > ema200)
    fng_val = get_fear_and_greed()
    funding_val = get_funding_rate(symbol)
    conf_score = calculate_confidence_score(
        closed_candle, action, divergence, is_counter_trend, fng_val, funding_val, weekly_context
    )
    req_conf = 0.70 if symbol == "HYPE" else MIN_CONFIDENCE

    fleet_stats = get_fleet_position_stats()
    if conf_score < req_conf:
        print(f"🛑 SKIP [{bot_id}]: {action} descartada ({conf_score:.2f} < {req_conf}).")
        return
    if fleet_stats.get("fleet_drawdown_pct", 0.0) >= MAX_FLEET_DRAWDOWN_PCT:
        print(f"🛑 CIRCUIT BREAKER: Drawdown de flota {fleet_stats['fleet_drawdown_pct']:.2f}% >= {MAX_FLEET_DRAWDOWN_PCT}%.")
        return

    if timeframe == "4h" and is_counter_trend and weekly_context:
        w_td = weekly_context.get("td_count", 0)
        if action == "BUY" and (weekly_context.get("is_sell_exhaustion_active") or (-8 <= w_td < 0)):
            print(f"🛑 MACRO SHIELD [{bot_id}]: BUY contra-tendencia bloqueado por contexto 1W.")
            return
        if action == "SELL" and (weekly_context.get("is_buy_exhaustion_active") or (0 < w_td <= 8)):
            print(f"🛑 MACRO SHIELD [{bot_id}]: SELL contra-tendencia bloqueado por contexto 1W.")
            return

    adx_val = float(closed_candle.get("adx", 0.0))
    if is_counter_trend and adx_val >= 32.0:
        print(f"🛑 ADX SAFETY SWITCH [{bot_id}]: ADX={adx_val:.1f} >= 32.0.")
        return
    if fleet_stats["total"] >= MAX_TOTAL_FLEET_TRADES:
        print(f"🛑 PORTFOLIO SHIELD: Cap total alcanzado ({fleet_stats['total']}/{MAX_TOTAL_FLEET_TRADES}).")
        return
    dir_key = "longs" if action == "BUY" else "shorts"
    if fleet_stats[dir_key] >= MAX_DIRECTIONAL_TRADES:
        print(f"🛑 CORRELATION SHIELD: Cap direccional {action} alcanzado.")
        return
    if fleet_stats["by_symbol"].get(symbol, 0) >= MAX_TRADES_PER_SYMBOL:
        print(f"🛑 ASSET SHIELD: Cap de {symbol} alcanzado.")
        return
    if state.get("last_trigger_time") == trigger_time:
        return

    bot_params = get_bot_params(symbol, timeframe, strategy_type)
    sl, tp, tag, _, _ = compute_entry_levels(action, signal_reason, price, atr, is_counter_trend, bot_params)
    reason = f"{signal_reason} ({tag}) [Conf: {conf_score:.2f} | F&G: {fng_val}]" if "TD9" in signal_reason else f"{signal_reason} + RSI {rsi:.1f} [Conf: {conf_score:.2f} | F&G: {fng_val}]"

    p_ctx = portfolio_context or {}
    vol_30d = p_ctx.get("vols", {}).get(normalize_symbol(symbol))
    corr_matrix = p_ctx.get("corr_matrix")
    base_risk = get_base_risk(symbol, timeframe, realized_vol_30d=vol_30d)
    conviction_mult = compute_conviction_multiplier(action, rsi)
    conviction_boost = compute_conviction_boost(symbol, conf_score)

    # Gate de confluencia multi-timeframe: si el 4H también tiene un TD9 reciente
    # en la misma dirección, se escala el riesgo base un +30%.
    # Solo aplica en bots 1D (evita recursión en bots 4H y no existe en 1W).
    htf_boost = 1.0
    htf_aligned = False
    if timeframe == "1d" and _check_4h_td9_confluence(symbol, action):
        htf_aligned = True
        htf_boost = 1.3
        reason += " [+4H✓]"
        print(f"📡 HTF CONFLUENCE [{bot_id}]: TD9 4H alineado → boost +30% (riesgo x{htf_boost})")

    hyb_weights = load_meta_weights(strategy_type, weights_file=META_WEIGHTS_FILE)
    allowed_meta, meta_prob, meta_mult = evaluate_hyb_meta_gate(
        closed_candle, action, ema200, funding_val, htf_aligned, is_counter_trend, bot_params, hyb_weights
    )
    if not allowed_meta:
        print(f"🛑 META-GATE [{bot_id}]: {action} filtrada por baja prob ({meta_prob:.2f}).")
        return

    cand_risk = base_risk * conviction_mult * conviction_boost * htf_boost * meta_mult
    portfolio_dampening = compute_portfolio_dampening(
        symbol, action, cand_risk, fleet_stats.get("active_positions", []), corr_matrix=corr_matrix
    )
    final_risk = cand_risk * portfolio_dampening
    if final_risk <= 1e-6:
        print(f"🛑 PORTFOLIO RISK BUDGET [{bot_id}]: Ex-ante sigma excedido.")
        return

    state["portfolio_dampening"] = round(portfolio_dampening, 2)
    if hyb_weights and bool(bot_params.get("use_hyb_meta_gate", True)):
        state["meta_prob"] = round(meta_prob, 2)
    execute_trade(
        action=action,
        price=price,
        sl=sl,
        tp=tp,
        reason=reason,
        trigger_time=trigger_time,
        risk_pct=final_risk,
        atr=atr,
        symbol=symbol,
        timeframe=timeframe,
        state_file=state_file,
        trades_file=trades_file,
        existing_state=state,
        strategy_mode="HYB",
    )


def main():
    global INITIAL_BANK
    _install_timestamped_print()
    _ensure_env_loaded()

    parser = argparse.ArgumentParser()
    parser.add_argument("--bank", type=float, default=10000.0, help="Initial bankroll")
    args = parser.parse_args()

    INITIAL_BANK = args.bank
    n_bots = len(FLEET_ASSETS) * len(FLEET_TIMEFRAMES) * len(FLEET_STRATEGIES)
    print(f"Iniciando GaTDSEQ Bot UNIFICADO ({n_bots} BOTS) | Bank: ${INITIAL_BANK}...")
    send_telegram(
        f"🏛 <b>SYSTEM INITIALIZED</b>\n\nQuantitative Core online. Engine tracking {n_bots}-bot validated 1D pipeline ({', '.join(FLEET_ASSETS)}) + 1W Macro Shield."
    )

    bots = [
        {"id": f"{sym}_{strat}", "symbol": sym, "strategy": strat}
        for sym in FLEET_ASSETS
        for strat in FLEET_STRATEGIES
    ]

    while True:
        weekly_context_cache: Dict[str, Dict[str, Any]] = {}
        for symbol in FLEET_ASSETS:
            try:
                w_raw = get_data(f"{symbol}/USDT", "1w", limit=250)
                if w_raw is not None and len(w_raw) >= 5:
                    w_ctx = compute_weekly_context(w_raw)
                    if w_ctx is not None:
                        w_ctx["df"] = w_raw
                        weekly_context_cache[symbol] = w_ctx
            except Exception as e:
                print(f"Error fetching weekly context for {symbol}: {e}")

        for tf in FLEET_TIMEFRAMES:
            df_cache: Dict[str, pd.DataFrame] = {}
            market_context_cache: Dict[str, Dict[str, Any]] = {}
            for symbol in FLEET_ASSETS:
                try:
                    if tf == "1w" and symbol in weekly_context_cache:
                        df = weekly_context_cache[symbol]["df"]
                    else:
                        df = get_data(f"{symbol}/USDT", tf)

                    if df is not None and len(df) >= 5:
                        df_cache[symbol] = df
                        # Excluir vela viva (iloc[-1]) de VP y divergencias para evitar look-ahead intravela
                        closed_slice = df.iloc[:-1]
                        vp_data = calculate_volume_profile(closed_slice.tail(min(300, len(closed_slice))), bins=20)
                        divergence = detect_divergences(closed_slice)
                        market_context_cache[symbol] = {"vp_data": vp_data, "divergence": divergence}
                except Exception as e:
                    print(f"Error fetching {symbol} ({tf}): {e}")

            # Matriz de correlacion 30d y volatilidad realizada sobre velas estrictamente cerradas
            closed_map = {sym: d.iloc[:-1] for sym, d in df_cache.items() if len(d) >= 5}
            corr_matrix, vols = compute_rolling_corr_and_vol(closed_map, window=30)
            portfolio_ctx = {"corr_matrix": corr_matrix, "vols": vols}

            for bot in bots:
                symbol = bot["symbol"]
                if symbol not in df_cache:
                    continue
                try:
                    analyze_market(
                        df_cache[symbol],
                        bot["id"],
                        bot["strategy"],
                        market_context_cache.get(symbol),
                        weekly_context_cache.get(symbol),
                        symbol=symbol,
                        timeframe=tf,
                        portfolio_context=portfolio_ctx,
                    )
                except Exception as e:
                    print(f"Error analizando {bot['id']} [{tf}]: {e}")

            meta_active = os.path.exists(META_WEIGHTS_FILE)
            pos_stats = get_fleet_position_stats()
            save_fleet_risk_snapshot(corr_matrix, vols, pos_stats, meta_active)
            check_and_send_heartbeat(pos_stats, INITIAL_BANK)
            gc.collect()

        now = time.time()
        sleep_sec = 300 - (now % 300)
        time.sleep(sleep_sec + 3)


if __name__ == "__main__":
    main()
