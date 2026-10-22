import time
import ccxt
import pandas as pd
from volume_profile import calculate_volume_profile
from wycoff_logic import detect_divergences
import json
import os
import builtins
import datetime as dt_module

_old_print = builtins.print
def _timestamped_print(*args, **kwargs):
    _old_print(f"[{dt_module.datetime.now().strftime('%H:%M:%S')}]", *args, **kwargs)
builtins.print = _timestamped_print

import requests
import datetime
import math
import argparse

TIMEFRAME = '4h'

# Archivos de estado
STATE_FILE = "state.json"
TRADES_FILE = "trades.json"

from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = "1097154358"

INITIAL_BANK = 10000.0

import threading

def _send_telegram_async(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Error sending telegram:", e)

def send_telegram(msg):
    threading.Thread(target=_send_telegram_async, args=(msg,), daemon=True).start()

# --- ATOMIC STORAGE & STATE HELPERS ---
def load_state(filepath=None):
    target = filepath or STATE_FILE
    if os.path.exists(target):
        try:
            with open(target, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            print(f"⚠️ Alerta: {target} corrupto o inaccesible. Retornando IDLE.")
            return {"status": "IDLE"}
    return {"status": "IDLE"}

def save_state(state, filepath=None):
    target = filepath or STATE_FILE
    tmp_target = f"{target}.tmp"
    try:
        with open(tmp_target, "w") as f:
            json.dump(state, f)
        os.replace(tmp_target, target)
    except Exception as e:
        print(f"Error en escritura atómica de {target}: {e}")

def load_trades(filepath=None):
    target = filepath or TRADES_FILE
    if os.path.exists(target):
        try:
            with open(target, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            print(f"⚠️ Alerta: {target} corrupto. Iniciando lista vacía.")
            return []
    return []

def save_trades(trades, filepath=None):
    target = filepath or TRADES_FILE
    tmp_target = f"{target}.tmp"
    try:
        with open(tmp_target, "w") as f:
            json.dump(trades, f)
        os.replace(tmp_target, target)
    except Exception as e:
        print(f"Error en escritura atómica de {target}: {e}")

# --- DYNAMIC QUANTITATIVE PARAMETER LOADER (Worker Cluster Synchronization) ---
FLEET_OPTIMIZED_FILE = "fleet_optimized.json"
_FLEET_PARAMS_CACHE = {"timestamp": 0, "data": {}}

def get_bot_params(symbol="BTC", timeframe="1h", strategy="HYB"):
    """
    Carga dinámicamente los parámetros de Stop Loss, Take Profit y Break-Even
    desde fleet_optimized.json si el Worker Node los ha calibrado.
    Fallback seguro a los defaults institucionales si el archivo no existe.
    """
    global _FLEET_PARAMS_CACHE
    defaults = {
        "atr_sl_trend": 1.5,
        "atr_tp_trend": 2.5,
        "atr_sl_counter": 1.5,
        "atr_tp_counter": 2.0,
        "atr_sl_wyckoff": 1.5,
        "atr_tp_wyckoff": 2.0,
        "be_threshold_atr": 1.0,
        "scale_out_atr": 1.0,
        "scale_out_pct": 0.5,
        "enable_scale_out": True
    }
    
    now = time.time()
    # Cache con TTL de 60s para no saturar I/O de disco en bucle continuo
    if now - _FLEET_PARAMS_CACHE["timestamp"] > 60:
        if os.path.exists(FLEET_OPTIMIZED_FILE):
            try:
                with open(FLEET_OPTIMIZED_FILE, "r") as f:
                    _FLEET_PARAMS_CACHE["data"] = json.load(f)
                    _FLEET_PARAMS_CACHE["timestamp"] = now
            except Exception as e:
                print(f"⚠️ Error cargando {FLEET_OPTIMIZED_FILE}: {e}")
        else:
            _FLEET_PARAMS_CACHE["data"] = {}
            _FLEET_PARAMS_CACHE["timestamp"] = now

    data = _FLEET_PARAMS_CACHE.get("data", {})
    if not data:
        return defaults

    clean_sym = symbol.replace("/", "_").replace(":USDT", "")
    for key, val in data.items():
        k_clean = key.replace("/", "_").replace(":USDT", "")
        if clean_sym in k_clean and f"_{timeframe}_" in k_clean and f"_{strategy}" in k_clean:
            bp = val.get("best_params", {})
            merged = dict(defaults)
            merged.update(bp)
            return merged

    return defaults

# Inicializar Binance
exchange = ccxt.binance({
    'enableRateLimit': True,
})

def calculate_rsi(series, period=14):
    delta = series.diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    # TradingView EXACT MATCH: Wilder's Smoothing (alpha=1/period) instead of EMA
    roll_up = up.ewm(alpha=1/period, adjust=False).mean()
    roll_down = down.abs().ewm(alpha=1/period, adjust=False).mean()
    rs = roll_up / roll_down
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    # TradingView EXACT MATCH: Wilder's Smoothing (RMA) instead of Simple Moving Average (SMA)
    return true_range.ewm(alpha=1/period, adjust=False).mean()

def get_data(symbol="BTC/USDT", timeframe="4h", limit=1500):
    for attempt in range(3):
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            break
        except Exception as e:
            if attempt == 2:
                print(f"❌ Error crítico de red tras 3 reintentos: {e}")
                return None
            import time
            time.sleep(2) # Retrying...
    try:
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']) # Descartar vela actual en formación
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Filtro Macro (EMA 200)
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # Filtro de Agotamiento (RSI)
        df['rsi'] = calculate_rsi(df['close'], 14)
        
        # Volatilidad para Stop Loss Dinámico (ATR)
        df['atr'] = calculate_atr(df, 14)
        
        # Filtro de Volumen (Institucional)
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        
        # Bandas de Bollinger (SMA 20, 2 StdDev)
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['std_20'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['sma_20'] + (df['std_20'] * 2)
        df['bb_lower'] = df['sma_20'] - (df['std_20'] * 2)
        
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def calculate_td_sequential(df):
    setup_up = 0
    setup_down = 0
    countdown_up = 0
    countdown_down = 0
    setup_up_active = False
    setup_down_active = False
    
    td_counts = []
    td_countdowns = []
    td_perfected_list = []
    tdst_res_list = []
    tdst_sup_list = []
    
    last_tdst_res = 0.0
    last_tdst_sup = 0.0
    last_perfected = False
    
    for i in range(len(df)):
        if i < 4:
            td_counts.append(0)
            td_countdowns.append(0)
            td_perfected_list.append(False)
            tdst_res_list.append(0.0)
            tdst_sup_list.append(0.0)
            continue
            
        close = df['close'].iloc[i]
        close_4_ago = df['close'].iloc[i-4]
        
        # 1. SETUP PHASE (Tom DeMark Setup)
        if close > close_4_ago:
            setup_up += 1
            setup_down = 0
            td_counts.append(setup_up)
            if setup_up == 9:
                setup_up_active = True
                setup_down_active = False
                countdown_up = 0
                # DeMark Setup Perfection: High de barra 8 o 9 >= max(High barra 6, High barra 7)
                if i >= 3:
                    h6 = df['high'].iloc[i-3]
                    h7 = df['high'].iloc[i-2]
                    h8 = df['high'].iloc[i-1]
                    h9 = df['high'].iloc[i]
                    last_perfected = bool((h8 >= max(h6, h7)) or (h9 >= max(h6, h7)))
                else:
                    last_perfected = False
                # TDST Levels: True High y True Low del bloque de 9 barras
                start_idx = max(0, i - 8)
                last_tdst_res = float(df['high'].iloc[start_idx:i+1].max())
                last_tdst_sup = float(df['low'].iloc[start_idx:i+1].min())
            elif setup_up > 9:
                pass
            else:
                last_perfected = False
        elif close < close_4_ago:
            setup_down += 1
            setup_up = 0
            td_counts.append(-setup_down)
            if setup_down == 9:
                setup_down_active = True
                setup_up_active = False
                countdown_down = 0
                # DeMark Setup Perfection: Low de barra 8 o 9 <= min(Low barra 6, Low barra 7)
                if i >= 3:
                    l6 = df['low'].iloc[i-3]
                    l7 = df['low'].iloc[i-2]
                    l8 = df['low'].iloc[i-1]
                    l9 = df['low'].iloc[i]
                    last_perfected = bool((l8 <= min(l6, l7)) or (l9 <= min(l6, l7)))
                else:
                    last_perfected = False
                # TDST Levels: True High y True Low del bloque de 9 barras
                start_idx = max(0, i - 8)
                last_tdst_res = float(df['high'].iloc[start_idx:i+1].max())
                last_tdst_sup = float(df['low'].iloc[start_idx:i+1].min())
            elif setup_down > 9:
                pass
            else:
                last_perfected = False
        else:
            setup_up = 0
            setup_down = 0
            td_counts.append(0)
            last_perfected = False
            
        td_perfected_list.append(last_perfected)
        tdst_res_list.append(last_tdst_res)
        tdst_sup_list.append(last_tdst_sup)
            
        # 2. COUNTDOWN PHASE
        if i >= 2:
            high_2_ago = df['high'].iloc[i-2]
            low_2_ago = df['low'].iloc[i-2]
            
            if setup_up_active and close > high_2_ago:
                countdown_up += 1
            
            if setup_down_active and close < low_2_ago:
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
    df['td_perfected'] = td_perfected_list
    df['tdst_res'] = tdst_res_list
    df['tdst_sup'] = tdst_sup_list
    return df


# ==============================================================================
# INSTITUTIONAL PORTFOLIO & CORRELATION SHIELD (Fleet Exposure Caps)
# ==============================================================================
MAX_TOTAL_FLEET_TRADES = 9       # Máximo 9 de los 27 bots en trade simultáneamente (33% de la flota)
MAX_DIRECTIONAL_TRADES = 6       # Máximo 6 LONGs o 6 SHORTs concurrentes en toda la flota
MAX_TRADES_PER_SYMBOL = 3        # Máximo 3 concurrentes en el mismo subyacente (ej. BTC)

def get_fleet_position_stats():
    """
    Escanea todos los archivos state_*.json y consolida el estado global de la cartera.
    """
    import glob, json
    stats = {
        'total': 0,
        'longs': 0,
        'shorts': 0,
        'by_symbol': {'BTC': 0, 'ETH': 0, 'HYPE': 0}
    }
    for file in glob.glob("state_*.json"):
        try:
            with open(file, "r") as f:
                st = json.load(f)
                if st.get("status") == "IN_TRADE":
                    stats['total'] += 1
                    pos = st.get("position", "BUY")
                    if pos == "BUY":
                        stats['longs'] += 1
                    else:
                        stats['shorts'] += 1
                    
                    base = os.path.basename(file)
                    parts = base.replace("state_", "").split("_")
                    if len(parts) > 0 and parts[0] in stats['by_symbol']:
                        stats['by_symbol'][parts[0]] += 1
        except Exception:
            pass
    return stats

# ==============================================================================
# MACRO SENTIMENT & CARRY COST GATES (Fear & Greed + Funding Rate)
# ==============================================================================
_FNG_CACHE = {"value": 50, "last_fetch": 0}
_FUNDING_CACHE = {} # symbol -> {'rate': float, 'last_fetch': float}

def get_fear_and_greed():
    """
    Consulta el índice Crypto Fear & Greed (alternative.me) con caché de 1 hora en memoria.
    Retorna 50 (Neutral) como fallback seguro si no hay conectividad.
    """
    global _FNG_CACHE
    now = time.time()
    if now - _FNG_CACHE["last_fetch"] < 3600 and _FNG_CACHE["last_fetch"] > 0:
        return _FNG_CACHE["value"]
    
    try:
        resp = requests.get('https://api.alternative.me/fng/?limit=1', headers={'User-Agent': 'GaTDSEQ/2.2'}, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            val = int(data['data'][0]['value'])
            _FNG_CACHE["value"] = val
            _FNG_CACHE["last_fetch"] = now
            return val
    except Exception:
        pass
    return _FNG_CACHE["value"]

def get_funding_rate(symbol):
    """
    Consulta la tasa de financiación de Binance Futures para el símbolo con caché de 1 hora.
    Retorna la tasa como float (ej: 0.0001 = 0.01%). Fallback seguro 0.0.
    """
    global _FUNDING_CACHE
    now = time.time()
    cached = _FUNDING_CACHE.get(symbol)
    if cached and (now - cached['last_fetch'] < 3600):
        return cached['rate']
    
    pair = f"{symbol}USDT"
    try:
        url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={pair}&limit=1"
        resp = requests.get(url, headers={'User-Agent': 'GaTDSEQ/2.2'}, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                rate = float(data[0].get('fundingRate', 0.0))
                _FUNDING_CACHE[symbol] = {'rate': rate, 'last_fetch': now}
                return rate
    except Exception:
        pass
    return 0.0

MIN_CONFIDENCE = 0.55

def calculate_confidence_score(candle, action, divergence, is_counter_trend, fng_index=50, funding_rate=0.0, weekly_context=None):
    """
    Funnel Architecture: Calcula una puntuación de convicción multidimensional (0.0 a 1.0).
    Ejes: 
    1. Setup DeMark (30%) 
    2. Momentum RSI (25%) 
    3. Volumen (25%) 
    4. Tendencia EMA200 (20%)
    5. Macro Confluence: Fear & Greed Index (Modulador ±10%)
    6. Carry Cost: Tasa de financiación en futuros (Modulador ±5%)
    7. Top-Down Macro Alignment: TD Sequential Semanal [1W] (Modulador ±15%)
    """
    score = 0.0
    # 1. Setup DeMark
    count = abs(candle.get('td_count', 0))
    if count >= 9: score += 0.30
    elif count >= 7: score += 0.15
    
    # 2. RSI & Divergencia
    rsi = candle.get('rsi', 50.0)
    if action == "BUY":
        if divergence == 'BULLISH': score += 0.25
        elif rsi <= 30: score += 0.20
        elif rsi <= 40: score += 0.10
    else:
        if divergence == 'BEARISH': score += 0.25
        elif rsi >= 70: score += 0.20
        elif rsi >= 60: score += 0.10
        
    # 3. Volumen Institucional vs SMA 20
    vol = candle.get('volume', 0.0)
    avg_vol = candle.get('volume_sma', vol)
    if avg_vol > 0:
        vol_ratio = vol / avg_vol
        if vol_ratio >= 1.5: score += 0.25
        elif vol_ratio >= 1.0: score += 0.15
        else: score += 0.05
        
    # 4. Tendencia Macro EMA 200
    if not is_counter_trend:
        score += 0.20
    else:
        score += 0.05
        
    # 5. Macro Confluence: Fear & Greed Index
    if fng_index is not None:
        if action == "BUY":
            if fng_index <= 25: score += 0.10     # Pánico Extremo: Smart Money acumula
            elif fng_index <= 40: score += 0.05    # Pánico moderado: Descuento
            elif fng_index >= 75: score -= 0.10    # Euforia Extrema: Riesgo de atrapar cuchillos en techos
        elif action == "SELL":
            if fng_index >= 75: score += 0.10     # Euforia Extrema: Distribución institucional
            elif fng_index >= 60: score += 0.05    # Codicia: Buen punto de agotamiento
            elif fng_index <= 25: score -= 0.10    # Pánico Extremo: Riesgo de vender en el suelo
            
    # 6. Carry Cost: Funding Rate en Perpetuos
    if funding_rate != 0.0:
        if action == "BUY":
            if funding_rate > 0.0004: score -= 0.05   # Longs pagando funding caro (>0.04%/8h)
            elif funding_rate < -0.0002: score += 0.05 # Shorts pagando a longs (carry positivo)
        elif action == "SELL":
            if funding_rate < -0.0004: score -= 0.05  # Shorts pagando funding caro
            elif funding_rate > 0.0002: score += 0.05  # Longs pagando a shorts (carry positivo)

    # 7. Top-Down Macro Alignment: DeMark Semanal [1W] (Anti-Bias Shield Ponderado con Perfección)
    if weekly_context:
        is_sell_exh = weekly_context.get('is_sell_exhaustion_active', False)
        is_buy_exh = weekly_context.get('is_buy_exhaustion_active', False)
        macro_modulator = weekly_context.get('macro_weight', 0.06)
        
        if is_sell_exh:
            if action == "SELL":
                score += macro_modulator  # Viento a favor macro verificado
            elif action == "BUY":
                score -= macro_modulator  # Leve filtro de prudencia en compras cerca de resistencia semanal
        elif is_buy_exh:
            if action == "BUY":
                score += macro_modulator  # Viento a favor macro verificado
            elif action == "SELL":
                score -= macro_modulator  # Leve filtro de prudencia en ventas cerca de soporte semanal

    return round(score, 2)

def analyze_market(df, bot_id, strategy_type, precomputed_context=None, weekly_context=None):
    global TIMEFRAME, SYMBOL, STATE_FILE, TRADES_FILE
    STATE_FILE = f"state_{bot_id}_{TIMEFRAME}.json"
    TRADES_FILE = f"trades_{bot_id}_{TIMEFRAME}.json"
    
    # SEPARACIÓN CRÍTICA: Vela Cerrada (Entradas) vs Vela Viva (Salidas/StopLoss)
    closed_candle = df.iloc[-2]
    live_candle = df.iloc[-1]
    
    # Parametros para ENTRADAS (Siempre sobre la vela confirmada y cerrada)
    current_live_price = closed_candle['close']
    ema200 = closed_candle['ema_200']
    rsi = closed_candle['rsi']
    raw_atr = closed_candle['atr']
    bb_upper = closed_candle.get('bb_upper', 0)
    bb_lower = closed_candle.get('bb_lower', float('inf'))
    
    # --- ATR DYNAMIC SCALING & FLOOR ATR (Institutional Volatility Guard) ---
    if TIMEFRAME == '5m': tf_mult = 2.0
    elif TIMEFRAME == '15m': tf_mult = 1.8
    elif TIMEFRAME == '1h': tf_mult = 1.5
    elif TIMEFRAME == '4h': tf_mult = 1.2
    elif TIMEFRAME == '1d': tf_mult = 1.0
    else: tf_mult = 0.8 # 1w
    
    atr = raw_atr * tf_mult
    # Suelo de volatilidad mínima: previene stops de papel durante consolidaciones o fines de semana
    min_atr_pct = 0.006 if TIMEFRAME == '1h' else (0.010 if TIMEFRAME == '4h' else (0.015 if TIMEFRAME == '1d' else 0.025))
    floor_atr = current_live_price * min_atr_pct
    atr = max(atr, floor_atr)
    # ------------------------------------------------------------------------
    
    count = closed_candle['td_count']
    countdown = closed_candle['td_countdown']
    trigger_time = str(closed_candle['timestamp'])
    
    # --- WYCKOFF CORE (Optimizado con contexto precalculado) ---
    if precomputed_context and 'vp_data' in precomputed_context:
        vp_data = precomputed_context['vp_data']
        poc = vp_data['poc']
        vah = vp_data['vah']
        val = vp_data['val']
        divergence = precomputed_context.get('divergence')
    else:
        vp_data = calculate_volume_profile(df.tail(100), bins=20)
        poc = vp_data['poc']
        vah = vp_data['vah']
        val = vp_data['val']
        divergence = detect_divergences(df.iloc[:-1])
    
    avg_vol = df['volume'].iloc[-20:-1].mean()
    volume = closed_candle.get('volume', 0)
    climatic_volume = volume > (avg_vol * 1.5)
    
    candle_range = closed_candle['high'] - closed_candle['low']
    if candle_range == 0: candle_range = 1
    close_pct = (closed_candle['close'] - closed_candle['low']) / candle_range
    
    wyckoff_spring = (closed_candle['low'] < val) and climatic_volume and (close_pct >= 0.5) and (divergence == 'BULLISH')
    wyckoff_upthrust = (closed_candle['high'] > vah) and climatic_volume and (close_pct <= 0.5) and (divergence == 'BEARISH')
    
    # Cargar y sincronizar estado con Dirty-Check para preservar la vida útil de la MicroSD
    state = load_state()
    new_td = int(count)
    new_countdown = int(countdown)
    div_str = divergence or "NONE"
    
    td_perf = bool(closed_candle.get('td_perfected', False))
    tdst_res_val = round(float(closed_candle.get('tdst_res', 0.0)), 2)
    tdst_sup_val = round(float(closed_candle.get('tdst_sup', 0.0)), 2)
    
    state_dirty = False
    if state.get("poc") != poc:
        state["poc"] = poc
        state_dirty = True
    if state.get("wyckoff_div") != div_str:
        state["wyckoff_div"] = div_str
        state_dirty = True
    if state.get("td_count") != new_td:
        state["td_count"] = new_td
        state_dirty = True
    if state.get("td_countdown") != new_countdown:
        state["td_countdown"] = new_countdown
        state_dirty = True
    if state.get("td_perfected") != td_perf:
        state["td_perfected"] = td_perf
        state_dirty = True
    if state.get("tdst_res") != tdst_res_val:
        state["tdst_res"] = tdst_res_val
        state_dirty = True
    if state.get("tdst_sup") != tdst_sup_val:
        state["tdst_sup"] = tdst_sup_val
        state_dirty = True
        
    if state_dirty:
        save_state(state)
    
    if abs(count) >= 7 or state.get("status") == "IN_TRADE":
        print(f"Analizando {SYMBOL} en {TIMEFRAME} con Inteligencia Cuantitativa (TD9 + EMA200 + RSI + ATR)...")
        print(f"{SYMBOL} | Precio: ${current_live_price:.2f} | TD Count: {count} | RSI: {rsi:.2f} | EMA200: {ema200:.2f}")

    
    if state.get("status") == "IDLE":
        td_buy = (count <= -9) and (closed_candle['close'] > df.iloc[-3]['high']) # Confirmación de reversión
        td_sell = (count >= 9) and (closed_candle['close'] < df.iloc[-3]['low']) # Confirmación de reversión
        
        trigger_buy = False
        trigger_sell = False
        reason_buy = ""
        reason_sell = ""
        
        if strategy_type in ["TD9", "HYB"]:
            if td_buy:
                trigger_buy = True
                reason_buy = "TD9 Buy"
            if td_sell:
                trigger_sell = True
                reason_sell = "TD9 Sell"
                
        if strategy_type in ["WYK", "HYB"]:
            if wyckoff_spring and not trigger_buy:
                trigger_buy = True
                reason_buy = "Wyckoff Spring"
            if wyckoff_upthrust and not trigger_sell:
                trigger_sell = True
                reason_sell = "Wyckoff Upthrust"

        if trigger_buy:
            if rsi < 70: # Permitir compras si no está extremadamente sobrecomprado
                is_counter_trend = current_live_price < ema200
                fng_val = get_fear_and_greed()
                funding_val = get_funding_rate(SYMBOL)
                conf_score = calculate_confidence_score(closed_candle, "BUY", divergence, is_counter_trend, fng_val, funding_val, weekly_context)
                w_td_str = f" | 1W TD: {weekly_context.get('td_count', 0)}" if weekly_context else ""
                print(f"🎯 Funnel Gate ({SYMBOL} [{TIMEFRAME}]) | Convicción: {conf_score:.2f} (Umbral: {MIN_CONFIDENCE}) | F&G: {fng_val} | Funding: {funding_val*100:+.3f}%{w_td_str}")

                # --- PORTFOLIO & CORRELATION SHIELD ---
                fleet_stats = get_fleet_position_stats()
                if conf_score < MIN_CONFIDENCE:
                    print(f"🛑 SKIP: Señal BUY descartada por baja convicción ({conf_score:.2f} < {MIN_CONFIDENCE}).")
                elif TIMEFRAME == "4h" and is_counter_trend and weekly_context and weekly_context.get('is_sell_exhaustion_active'):
                    print(f"🛑 MACRO SHIELD: Compra contra-tendencia descartada en {SYMBOL} [4h] por corrección semanal activa.")
                elif TIMEFRAME == "4h" and is_counter_trend and weekly_context and (-8 <= weekly_context.get('td_count', 0) < 0):
                    print(f"🛑 MACRO TREND SHIELD: Compra contra-tendencia descartada en {SYMBOL} [4h] por impulso bajista semanal en curso (1W TD: {weekly_context.get('td_count', 0)}).")
                elif fleet_stats['total'] >= MAX_TOTAL_FLEET_TRADES:
                    print(f"🛑 PORTFOLIO SHIELD: Cap total de cartera alcanzado ({fleet_stats['total']}/{MAX_TOTAL_FLEET_TRADES} trades activos). Omitiendo BUY.")
                elif fleet_stats['longs'] >= MAX_DIRECTIONAL_TRADES:
                    print(f"🛑 CORRELATION SHIELD: Cap direccional LONG alcanzado ({fleet_stats['longs']}/{MAX_DIRECTIONAL_TRADES} LONGs activos). Omitiendo BUY.")
                elif fleet_stats['by_symbol'].get(SYMBOL, 0) >= MAX_TRADES_PER_SYMBOL:
                    print(f"🛑 ASSET CONCENTRATION SHIELD: Cap de activo alcanzado ({SYMBOL}: {fleet_stats['by_symbol'].get(SYMBOL, 0)}/{MAX_TRADES_PER_SYMBOL} trades activos). Omitiendo BUY.")
                elif state.get("last_trigger_time") == trigger_time:
                    print("⚠️ Señal ya operada en esta vela.")
                else:
                    bot_params = get_bot_params(SYMBOL, TIMEFRAME, strategy_type)
                    sl_trend = bot_params.get("atr_sl_trend", 1.5)
                    tp_trend = bot_params.get("atr_tp_trend", 2.5)
                    sl_counter = bot_params.get("atr_sl_counter", 1.5)
                    tp_counter = bot_params.get("atr_tp_counter", 2.0)
                    sl_wyk = bot_params.get("atr_sl_wyckoff", 1.5)
                    tp_wyk = bot_params.get("atr_tp_wyckoff", 2.0)

                    if "TD9" in reason_buy:
                        if is_counter_trend:
                            print(f">>> ALERTA DE COMPRA <<< (TD9 Contra Tendencia) [SL:{sl_counter:.1f}x TP:{tp_counter:.1f}x ATR]")
                            stop_loss = current_live_price - (atr * sl_counter)
                            take_profit = current_live_price + (atr * tp_counter)
                            reason = f"TD9 Buy (Counter-Trend) [Conf: {conf_score:.2f} | F&G: {fng_val}]"
                        else:
                            print(f">>> ALERTA DE COMPRA <<< (TD9 A Favor de Tendencia) [SL:{sl_trend:.1f}x TP:{tp_trend:.1f}x ATR]")
                            stop_loss = current_live_price - (atr * sl_trend)
                            take_profit = current_live_price + (atr * tp_trend)
                            reason = f"TD9 Buy (Trend) [Conf: {conf_score:.2f} | F&G: {fng_val}]"
                    else:
                        print(f">>> ALERTA DE COMPRA <<< (Wyckoff) [SL:{sl_wyk:.1f}x TP:{tp_wyk:.1f}x ATR]")
                        stop_loss = current_live_price - (atr * sl_wyk)
                        take_profit = current_live_price + (atr * tp_wyk)
                        reason = f"Wyckoff Spring + RSI {rsi:.1f} [Conf: {conf_score:.2f} | F&G: {fng_val}]"

                    # Institutional Risk Parity & Volatility Sizing (Max 1.5% - 2.5% per trade)
                    risk_matrix = {"1w": 0.025, "1d": 0.02, "4h": 0.015, "1h": 0.01, "15m": 0.005, "5m": 0.005}
                    base_risk = risk_matrix.get(TIMEFRAME, 0.015)
                    conviction_multiplier = 1.25 if rsi < 30 else 1.0
                    
                    # High-Beta Altcoin Risk Parity: HYPE tiene ATR relativo alto, modular riesgo al 65%
                    asset_dampener = 0.65 if SYMBOL == "HYPE" else 1.0
                    
                    # Dynamic Portfolio Dampening: Si ya hay 2 o más posiciones LONG, modular riesgo al 75%
                    portfolio_dampening = 0.75 if fleet_stats['longs'] >= 2 else 1.0
                    final_risk = base_risk * conviction_multiplier * asset_dampener * portfolio_dampening
                    execute_trade("BUY", current_live_price, stop_loss, take_profit, reason, trigger_time, final_risk)

        elif trigger_sell:
            if rsi > 30: # Permitir ventas si no está extremadamente sobrevendido
                is_counter_trend = current_live_price > ema200
                fng_val = get_fear_and_greed()
                funding_val = get_funding_rate(SYMBOL)
                conf_score = calculate_confidence_score(closed_candle, "SELL", divergence, is_counter_trend, fng_val, funding_val, weekly_context)
                w_td_str = f" | 1W TD: {weekly_context.get('td_count', 0)}" if weekly_context else ""
                print(f"🎯 Funnel Gate ({SYMBOL} [{TIMEFRAME}]) | Convicción: {conf_score:.2f} (Umbral: {MIN_CONFIDENCE}) | F&G: {fng_val} | Funding: {funding_val*100:+.3f}%{w_td_str}")

                # --- PORTFOLIO & CORRELATION SHIELD ---
                fleet_stats = get_fleet_position_stats()
                if conf_score < MIN_CONFIDENCE:
                    print(f"🛑 SKIP: Señal SELL descartada por baja convicción ({conf_score:.2f} < {MIN_CONFIDENCE}).")
                elif TIMEFRAME == "4h" and is_counter_trend and weekly_context and weekly_context.get('is_buy_exhaustion_active'):
                    print(f"🛑 MACRO SHIELD: Venta contra-tendencia descartada en {SYMBOL} [4h] por rebote semanal activo.")
                elif TIMEFRAME == "4h" and is_counter_trend and weekly_context and (0 < weekly_context.get('td_count', 0) <= 8):
                    print(f"🛑 MACRO TREND SHIELD: Venta contra-tendencia descartada en {SYMBOL} [4h] por impulso alcista semanal en curso (1W TD: +{weekly_context.get('td_count', 0)}).")
                elif fleet_stats['total'] >= MAX_TOTAL_FLEET_TRADES:
                    print(f"🛑 PORTFOLIO SHIELD: Cap total de cartera alcanzado ({fleet_stats['total']}/{MAX_TOTAL_FLEET_TRADES} trades activos). Omitiendo SELL.")
                elif fleet_stats['shorts'] >= MAX_DIRECTIONAL_TRADES:
                    print(f"🛑 CORRELATION SHIELD: Cap direccional SHORT alcanzado ({fleet_stats['shorts']}/{MAX_DIRECTIONAL_TRADES} SHORTs activos). Omitiendo SELL.")
                elif fleet_stats['by_symbol'].get(SYMBOL, 0) >= MAX_TRADES_PER_SYMBOL:
                    print(f"🛑 ASSET CONCENTRATION SHIELD: Cap de activo alcanzado ({SYMBOL}: {fleet_stats['by_symbol'].get(SYMBOL, 0)}/{MAX_TRADES_PER_SYMBOL} trades activos). Omitiendo SELL.")
                elif state.get("last_trigger_time") == trigger_time:
                    print("⚠️ Señal ya operada en esta vela.")
                else:
                    bot_params = get_bot_params(SYMBOL, TIMEFRAME, strategy_type)
                    sl_trend = bot_params.get("atr_sl_trend", 1.5)
                    tp_trend = bot_params.get("atr_tp_trend", 2.5)
                    sl_counter = bot_params.get("atr_sl_counter", 1.5)
                    tp_counter = bot_params.get("atr_tp_counter", 2.0)
                    sl_wyk = bot_params.get("atr_sl_wyckoff", 1.5)
                    tp_wyk = bot_params.get("atr_tp_wyckoff", 2.0)

                    if "TD9" in reason_sell:
                        if is_counter_trend:
                            print(f">>> ALERTA DE VENTA <<< (TD9 Contra Tendencia) [SL:{sl_counter:.1f}x TP:{tp_counter:.1f}x ATR]")
                            stop_loss = current_live_price + (atr * sl_counter)
                            take_profit = current_live_price - (atr * tp_counter)
                            reason = f"TD9 Sell (Counter-Trend) [Conf: {conf_score:.2f} | F&G: {fng_val}]"
                        else:
                            print(f">>> ALERTA DE VENTA <<< (TD9 A Favor de Tendencia) [SL:{sl_trend:.1f}x TP:{tp_trend:.1f}x ATR]")
                            stop_loss = current_live_price + (atr * sl_trend)
                            take_profit = current_live_price - (atr * tp_trend)
                            reason = f"TD9 Sell (Trend) [Conf: {conf_score:.2f} | F&G: {fng_val}]"
                    else:
                        print(f">>> ALERTA DE VENTA <<< (Wyckoff) [SL:{sl_wyk:.1f}x TP:{tp_wyk:.1f}x ATR]")
                        stop_loss = current_live_price + (atr * sl_wyk)
                        take_profit = current_live_price - (atr * tp_wyk)
                        reason = f"Wyckoff Upthrust + RSI {rsi:.1f} [Conf: {conf_score:.2f} | F&G: {fng_val}]"

                    # Institutional Risk Parity & Volatility Sizing (Max 1.5% - 2.5% per trade)
                    risk_matrix = {"1w": 0.025, "1d": 0.02, "4h": 0.015, "1h": 0.01, "15m": 0.005, "5m": 0.005}
                    base_risk = risk_matrix.get(TIMEFRAME, 0.015)
                    conviction_multiplier = 1.25 if rsi > 70 else 1.0
                    
                    # High-Beta Altcoin Risk Parity: HYPE tiene ATR relativo alto, modular riesgo al 65%
                    asset_dampener = 0.65 if SYMBOL == "HYPE" else 1.0
                    
                    # Dynamic Portfolio Dampening: Si ya hay 2 o más posiciones SHORT, modular riesgo al 75%
                    portfolio_dampening = 0.75 if fleet_stats['shorts'] >= 2 else 1.0
                    final_risk = base_risk * conviction_multiplier * asset_dampener * portfolio_dampening
                    execute_trade("SELL", current_live_price, stop_loss, take_profit, reason, trigger_time, final_risk)

    elif state.get("status") == "IN_TRADE":
        pos = state.get("position")
        if pos == "BUY" and countdown == -13 and not state.get("reinforced_13"):
            print(">>> ALERTA DE REFUERZO (DCA) TD-13 (LONG) <<<")
            execute_reinforcement(current_live_price, atr, state, "BUY")
        elif pos == "SELL" and countdown == 13 and not state.get("reinforced_13"):
            print(">>> ALERTA DE REFUERZO (DCA) TD-13 (SHORT) <<<")
            execute_reinforcement(current_live_price, atr, state, "SELL")
            
        check_exit_conditions(live_candle, closed_candle, atr, state, weekly_context, strategy_type)

def execute_reinforcement(price, atr, state, action):
    import time
    
    trades = load_trades()
    current_bank = INITIAL_BANK + sum(t.get('pnl', 0.0) for t in trades)
    
    # Calculate Risk (Matching execute_trade's standard risk)
    # Since we can't easily fetch conviction multiplier here, we use a standard flat risk
    # Wait, execute_trade defaults risk_pct=0.01 but analyze_market computes it based on TF.
    # Let's just mirror the actual_risk_amount or risk_usd from the state!
    # state["risk_usd"] already has the dollar amount we risked on the first bullet!
    # Recuperar el riesgo objetivo total y aplicar el 65% restante (El Batallón)
    full_target = state.get("full_target_risk_usd", state.get("risk_usd", current_bank * 0.05) / 0.35)
    base_risk_usd = full_target * 0.65
    print(f"🛡 EL BATALLÓN (TD13): Inyectando el 65% de riesgo restante (${base_risk_usd:.2f}) para promediar a la baja.")
    
    if action == "BUY":
        new_sl = price - (atr * 2.0)
        new_tp_offset = atr * 2.5
    else:
        new_sl = price + (atr * 2.0)
        new_tp_offset = - (atr * 2.5)
        
    sl_pct = abs(price - new_sl) / price
    if sl_pct < 0.001: sl_pct = 0.001
    
    added_usd = base_risk_usd / sl_pct
    max_allowed = current_bank * 10
    if added_usd > max_allowed: added_usd = max_allowed
    added_btc = added_usd / price
    
    old_entry = state["entry_price"]
    old_usd = state["size_usd"]
    old_btc = state["size_btc"]
    
    new_btc = old_btc + added_btc
    new_usd = old_usd + added_usd
    avg_entry = new_usd / new_btc
    
    if action == "BUY": new_tp = avg_entry + new_tp_offset
    else: new_tp = avg_entry + new_tp_offset
    
    state["size_btc"] = new_btc
    state["size_usd"] = new_usd
    state["entry_price"] = avg_entry
    state["stop_loss"] = new_sl
    state["take_profit"] = new_tp
    state["reinforced_13"] = True
    
    save_state(state)
        
    icon = "🟩" if action == "BUY" else "🟥"
    msg = (f"🚀 <b>DCA DEPLOYED | {SYMBOL} [{TIMEFRAME}]</b>\n\n"
           f"<b>Trigger:</b> TD-13 Exhaustion (Averaging Down)\n"
           f"<b>Type:</b> MARKET {action} (Reinforcement)\n"
           f"<b>New Avg Entry:</b> ${avg_entry:,.2f} (Was ${old_entry:,.2f})\n"
           f"<b>Capital Added:</b> ${added_usd:,.2f} ({added_btc:.4f} {SYMBOL})\n"
           f"<b>Total Position:</b> ${new_usd:,.2f} ({new_btc:.4f} {SYMBOL})\n"
           f"<b>New Stop Loss:</b> ${new_sl:,.2f}\n"
           f"<b>New Take Profit:</b> ${new_tp:,.2f}")
    send_telegram(msg)
    print(f"Refuerzo DCA Ejecutado a ${price:.2f} | Nuevo Avg: ${avg_entry:.2f}")

def execute_trade(action, price, sl, tp, reason, trigger_time=None, risk_pct=0.01):
    time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trade_id = str(int(time.time()))
    
    # Risk Management Engine
    trades = load_trades()
    current_bank = INITIAL_BANK + sum(t.get('pnl', 0.0) for t in trades)
    
    # 1. Calculamos cuanto estamos dispuestos a perder ($)
    risk_amount = current_bank * risk_pct
    
    # 2. Calculamos la distancia del precio al stop loss
    sl_dist_price = abs(price - sl)
    if sl_dist_price == 0: 
        sl_dist_price = 0.00001 # Prevenir división por cero si la volatilidad (ATR) muere por completo
        
    # 3. Calculamos la cantidad de BTC que debemos comprar para que, si el precio llega al SL, perdamos exactamente 'risk_amount'
    position_size_btc = risk_amount / sl_dist_price
    
    # 4. Valor total de la posicion (Notional Value)
    position_size_usd = position_size_btc * price
    
    # 5. Dynamic Futures Leverage Calculation
    required_leverage = position_size_usd / current_bank
    if required_leverage < 1.0: required_leverage = 1.0
    
    # Cap Leverage at 50x (Safety Guard for Paper Trading)
    MAX_LEVERAGE = 50.0
    if required_leverage > MAX_LEVERAGE:
        print(f"⚠️ Alerta: Apalancamiento ({required_leverage:.1f}x) supera el máximo de {MAX_LEVERAGE}x. Capping a {MAX_LEVERAGE}x.")
        required_leverage = MAX_LEVERAGE
        position_size_usd = current_bank * MAX_LEVERAGE
        position_size_btc = position_size_usd / price
        actual_risk_amount = position_size_btc * sl_dist_price
    else:
        actual_risk_amount = risk_amount
        
    print(f"🚀 Apalancamiento Dinámico Aplicado: {required_leverage:.2f}x")

    # Institutional Guard: Binance Spot Minimum Order Size ($10)
    if position_size_usd < 10.0:
        print(f"⚠️ Operación abortada: Tamaño de posición (${position_size_usd:.2f}) inferior al mínimo de Binance ($10).")
        return
    
    # Deduct 0.04% Binance Futures Fee on Entry Notional
    entry_fee_usd = position_size_usd * 0.0004
    
    state = {
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
        "leverage": required_leverage,
        "last_trigger_time": trigger_time
    }
    save_state(state)
    
    # Registro de apertura
    trades.append({
        "trade_id": trade_id,
        "time": time_str,
        "type": "COMPRA (Apertura)" if action == "BUY" else "VENTA (Apertura)",
        "reason": reason,
        "price": price,
        "pnl": 0.0
    })
    save_trades(trades)
        
    direction = "LONG" if action == "BUY" else "SHORT"
    icon = "🟩" if action == "BUY" else "🟥"
    msg = (f"{icon} <b>ORDER EXECUTED | {SYMBOL} [{TIMEFRAME}]</b>\n\n"
           f"<b>Type:</b> MARKET {direction}\n"
           f"<b>Entry Price:</b> ${price:,.2f}\n"
           f"<b>Stop Loss:</b> ${sl:,.2f}\n"
           f"<b>Take Profit:</b> ${tp:,.2f}\n"
           f"<b>Position Size:</b> ${position_size_usd:,.2f} ({position_size_btc:.4f} {SYMBOL})\n"
           f"<b>Leverage:</b> {required_leverage:.2f}x\n"
           f"<b>Risk Exposure:</b> ${actual_risk_amount:,.2f} ({(actual_risk_amount/current_bank)*100:.2f}%)\n"
           f"<b>Current Bank:</b> ${current_bank:,.2f}\n"
           f"<b>Model:</b> {reason}")
    send_telegram(msg)
    print(f"Trade {action} Ejecutado a ${price:.2f} | Inversión: ${position_size_usd:.2f} | Riesgo: ${actual_risk_amount:.2f}")

def check_exit_conditions(live_candle, closed_candle, atr, state, weekly_context=None, strategy_type="HYB"):
    action = state["position"]
    current_live_price = live_candle['close']
    current_closed_price = closed_candle['close']
    low_price = live_candle['low']
    high_price = live_candle['high']

    sl = state["stop_loss"]
    tp = state["take_profit"]
    entry = state["entry_price"]
    trade_id = state.get("trade_id", str(int(time.time())))
    
    # Recuperar tamaño de posición
    size_btc = state.get("size_btc", 0.15) # Default seguro si es antiguo
    
    closed = False
    pnl_dollars = 0.0
    updated_sl = sl
    close_reason = ""
    
    # --- MACRO WEEKLY CONFLUENCE SHIELD (Exhaustion Neutralizer con Filtro Anti-Sesgo) ---
    if weekly_context:
        is_sell_exh = weekly_context.get('is_sell_exhaustion_active', False)
        is_buy_exh = weekly_context.get('is_buy_exhaustion_active', False)
        
        # Solo activa el escudo preventivo si el agotamiento macro semanal sigue activo y no se ha invalidado
        if action == "BUY" and is_sell_exh and current_live_price > entry and updated_sl < entry:
            updated_sl = entry
            state["stop_loss"] = updated_sl
            print(f"🛡 MACRO SHIELD: Corrección semanal activa en {SYMBOL}. Subiendo Stop de LONG a Break-Even (${updated_sl:.2f}).")
            send_telegram(f"🛡 <b>MACRO SHIELD | {SYMBOL} [{TIMEFRAME}]</b>\nActive weekly pullback confirmed on {SYMBOL}. Immediate Break-Even shield activated on LONG position.")
        elif action == "SELL" and is_buy_exh and current_live_price < entry and updated_sl > entry:
            updated_sl = entry
            state["stop_loss"] = updated_sl
            print(f"🛡 MACRO SHIELD: Rebote semanal activo en {SYMBOL}. Bajando Stop de SHORT a Break-Even (${updated_sl:.2f}).")
            send_telegram(f"🛡 <b>MACRO SHIELD | {SYMBOL} [{TIMEFRAME}]</b>\nActive weekly rebound confirmed on {SYMBOL}. Immediate Break-Even shield activated on SHORT position.")

    # --- BREAK EVEN & SCALE-OUT PARAMETERS (Dynamic Worker Optimization) ---
    bot_params = get_bot_params(SYMBOL, TIMEFRAME, strategy_type)
    be_mult = bot_params.get("be_threshold_atr", 1.0)
    so_mult = bot_params.get("scale_out_atr", 1.0)
    enable_so = bot_params.get("enable_scale_out", True)

    # --- BREAK EVEN LOGIC (DYNAMIC ATR INSTITUTIONAL SHIELD) ---
    if action == "BUY" and live_candle['high'] >= (entry + (atr * be_mult)):
        if updated_sl < entry:
            updated_sl = entry
            state["stop_loss"] = updated_sl
            print(f"✅ BREAK EVEN ACTIVADO! Stop Loss subido a ${updated_sl:.2f} (+{be_mult:.2f} ATR favorable)")
            send_telegram(f"🛡 <b>BREAKEVEN SHIELD | {SYMBOL} [{TIMEFRAME}]</b>\nPrice advanced {be_mult:.2f} ATR in favor. Risk neutralized.\n\n<b>Stop Loss:</b> Moved to Entry (${entry:,.2f})")
    elif action == "SELL" and live_candle['low'] <= (entry - (atr * be_mult)):
        if updated_sl > entry:
            updated_sl = entry
            state["stop_loss"] = updated_sl
            print(f"✅ BREAK EVEN ACTIVADO! Stop Loss bajado a ${updated_sl:.2f} (+{be_mult:.2f} ATR favorable)")
            send_telegram(f"🛡 <b>BREAKEVEN SHIELD | {SYMBOL} [{TIMEFRAME}]</b>\nPrice advanced {be_mult:.2f} ATR in favor. Risk neutralized.\n\n<b>Stop Loss:</b> Moved to Entry (${entry:,.2f})")
    # ----------------------------------------------------

    
    if action == "BUY":
        # Scale-Out Parcial (Asegurar 50% de Ganancias en dynamic ATR)
        if enable_so and current_live_price >= entry + (atr * so_mult) and not state.get("scaled_out", False):
            import datetime as dt_mod
            print("💰 SCALE-OUT: Asegurando 50% de las ganancias (BUY a +1.0 ATR).")
            partial_pnl = ((current_live_price - entry) * (size_btc * 0.5)) - (state.get("entry_fee_usd", 0) * 0.5) - (current_live_price * (size_btc * 0.5) * 0.0004)
            trades = load_trades()
            trades.append({
                "trade_id": trade_id + "_partial",
                "time": dt_mod.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "VENTA (Cierre Parcial 50%)",
                "reason": "Scale-Out Táctico (+1.0 ATR)",
                "price": current_live_price,
                "pnl": partial_pnl
            })
            save_trades(trades)
            
            # Actualizar State
            state["size_btc"] = size_btc * 0.5
            state["size_usd"] = state.get("size_usd", 0) * 0.5
            state["entry_fee_usd"] = state.get("entry_fee_usd", 0) * 0.5
            state["scaled_out"] = True
            
            if updated_sl < entry:
                updated_sl = entry
                state["stop_loss"] = updated_sl
            save_state(state)
                
            send_telegram(f"💰 <b>SCALE-OUT (50%) | {SYMBOL} [{TIMEFRAME}]</b>\nLocked in profit on half the position. Risk neutralized to Breakeven.\n\n<b>Partial PnL:</b> ${partial_pnl:,.2f}")
            

        # Trailing stop based strictly on firmly closed candle to avoid Time Paradox
        new_sl = current_closed_price - (atr * 2.0)
        if new_sl > updated_sl:
            updated_sl = new_sl
            print(f"Trailing Stop (Buy) actualizado a ${updated_sl:.2f}")
            send_telegram(f"🛡 <b>RISK MITIGATION | {SYMBOL} [{TIMEFRAME}]</b>\nTrailing Stop advanced to lock in favorable delta.\n\n<b>New Stop Loss:</b> ${updated_sl:,.2f}\n<b>Current Price:</b> ${current_live_price:,.2f}")
            
        # Evaluate against the candle wicks (low/high) for realism
        if low_price <= updated_sl:
            print("❌ Stop Loss impactado en la mecha inferior.")
            pnl_dollars = (updated_sl - entry) * size_btc
            exit_fee = (updated_sl * size_btc) * 0.0004
            pnl_dollars -= (state.get("entry_fee_usd", 0) + exit_fee)
            closed = True
            close_reason = "Stop Loss"
            current_live_price = updated_sl # For closing log
        elif high_price >= tp:
            if live_candle.get('rsi', 50) >= 65:
                # Dynamic TP Extension (Let winners run)
                print(f"🔥 Take Profit alcanzado pero mercado eufórico (RSI >= 65). Extendiendo TP.")
                send_telegram(f"🔥 <b>TP EXTENSION | {SYMBOL} [{TIMEFRAME}]</b>\nStrong momentum detected at Take Profit. Letting the winner run.\n\n<b>New TP:</b> ${tp + (atr * 2.5):,.2f}\n<b>Locked SL:</b> ${max(updated_sl, tp - (atr * 1.0)):,.2f}")
                state["take_profit"] = tp + (atr * 2.5)
                if (tp - (atr * 1.0)) > updated_sl:
                    updated_sl = tp - (atr * 1.0)
            else:
                print("✅ Take Profit alcanzado en la mecha superior.")
                pnl_dollars = (tp - entry) * size_btc
                exit_fee = (tp * size_btc) * 0.0004
                pnl_dollars -= (state.get("entry_fee_usd", 0) + exit_fee)
                closed = True
                close_reason = "Take Profit"
                current_live_price = tp # For closing log
            
    elif action == "SELL":
        # Scale-Out Parcial (Asegurar 50% de Ganancias en dynamic ATR)
        if enable_so and current_live_price <= entry - (atr * so_mult) and not state.get("scaled_out", False):
            import datetime as dt_mod
            print("💰 SCALE-OUT: Asegurando 50% de las ganancias (SELL a -1.0 ATR).")
            partial_pnl = ((entry - current_live_price) * (size_btc * 0.5)) - (state.get("entry_fee_usd", 0) * 0.5) - (current_live_price * (size_btc * 0.5) * 0.0004)
            trades = load_trades()
            trades.append({
                "trade_id": trade_id + "_partial",
                "time": dt_mod.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "COMPRA (Cierre Parcial 50%)",
                "reason": "Scale-Out Táctico (+1.0 ATR)",
                "price": current_live_price,
                "pnl": partial_pnl
            })
            save_trades(trades)
            
            # Actualizar State
            state["size_btc"] = size_btc * 0.5
            state["size_usd"] = state.get("size_usd", 0) * 0.5
            state["entry_fee_usd"] = state.get("entry_fee_usd", 0) * 0.5
            state["scaled_out"] = True
            
            if updated_sl > entry:
                updated_sl = entry
                state["stop_loss"] = updated_sl
            save_state(state)
                
            send_telegram(f"💰 <b>SCALE-OUT (50%) | {SYMBOL} [{TIMEFRAME}]</b>\nLocked in profit on half the position. Risk neutralized to Breakeven.\n\n<b>Partial PnL:</b> ${partial_pnl:,.2f}")

        # Trailing stop based strictly on firmly closed candle to avoid Time Paradox
        new_sl = current_closed_price + (atr * 2.0)
        if new_sl < updated_sl:
            updated_sl = new_sl
            print(f"Trailing Stop (Sell) actualizado a ${updated_sl:.2f}")
            send_telegram(f"🛡 <b>RISK MITIGATION | {SYMBOL} [{TIMEFRAME}]</b>\nTrailing Stop advanced to lock in favorable delta.\n\n<b>New Stop Loss:</b> ${updated_sl:,.2f}\n<b>Current Price:</b> ${current_live_price:,.2f}")
            
        # Evaluate against the candle wicks (low/high) for realism
        if high_price >= updated_sl:
            print("❌ Stop Loss impactado en la mecha superior.")
            pnl_dollars = (entry - updated_sl) * size_btc
            exit_fee = (updated_sl * size_btc) * 0.0004
            pnl_dollars -= (state.get("entry_fee_usd", 0) + exit_fee)
            closed = True
            close_reason = "Stop Loss"
            current_live_price = updated_sl # For closing log
        elif low_price <= tp:
            if live_candle.get('rsi', 50) <= 35:
                # Dynamic TP Extension (Let winners run)
                print(f"🔥 Take Profit alcanzado pero mercado eufórico (RSI <= 35). Extendiendo TP.")
                send_telegram(f"🔥 <b>TP EXTENSION | {SYMBOL} [{TIMEFRAME}]</b>\nStrong momentum detected at Take Profit. Letting the winner run.\n\n<b>New TP:</b> ${tp - (atr * 2.5):,.2f}\n<b>Locked SL:</b> ${min(updated_sl, tp + (atr * 1.0)):,.2f}")
                state["take_profit"] = tp - (atr * 2.5)
                if (tp + (atr * 1.0)) < updated_sl:
                    updated_sl = tp + (atr * 1.0)
            else:
                print("✅ Take Profit alcanzado en la mecha inferior.")
                pnl_dollars = (entry - tp) * size_btc
                exit_fee = (tp * size_btc) * 0.0004
                pnl_dollars -= (state.get("entry_fee_usd", 0) + exit_fee)
                closed = True
                close_reason = "Take Profit"
                current_live_price = tp # For closing log

    # Save state if trailing stop moved
    if updated_sl != sl and not closed:
        state["stop_loss"] = updated_sl
        save_state(state)
            
    if closed:
        trades = load_trades()
        current_bank = INITIAL_BANK + sum(t.get('pnl', 0.0) for t in trades)
        pnl_pct_on_bank = (pnl_dollars / current_bank) * 100
        new_bank = current_bank + pnl_dollars
        
        print(f"Operación cerrada. Beneficio/Pérdida: ${pnl_dollars:.2f} ({pnl_pct_on_bank:.2f}% de la cuenta)")
        
        # Guardar cierre en el registro
        time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        trades.append({
            "trade_id": trade_id + "_close",
            "time": time_str,
            "type": "VENTA (Cierre)" if action == "BUY" else "COMPRA (Cierre)",
            "reason": close_reason,
            "price": current_live_price,
            "pnl": pnl_dollars
        })
        save_trades(trades)
            
        # Reset state
        state["status"] = "IDLE"
        save_state(state)
            
        emoji = "🟩" if pnl_dollars > 0 else "🟥"
        result_str = "PROFIT" if pnl_dollars > 0 else "LOSS"
        sign = "+" if pnl_dollars > 0 else ""
        msg = (f"{emoji} <b>POSITION CLOSED | {SYMBOL} [{TIMEFRAME}]</b>\n\n"
               f"<b>Trigger:</b> {close_reason}\n"
               f"<b>Exit Price:</b> ${current_live_price:,.2f}\n"
               f"<b>Net {result_str}:</b> {sign}${pnl_dollars:,.2f}\n"
               f"<b>Updated Bank:</b> ${new_bank:,.2f}")
        send_telegram(msg)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--bank', type=float, default=10000.0, help='Initial bankroll')
    args = parser.parse_args()

    INITIAL_BANK = args.bank
    print(f"Iniciando GaTDSEQ Bot UNIFICADO (27 BOTS) | Bank: ${INITIAL_BANK}...")
    send_telegram("🏛 <b>SYSTEM INITIALIZED</b>\n\nQuantitative Core online. Engine tracking macro multi-timeframe pipeline (4h, 1d & 1w - 27 bots).")
    
    timeframes = ['4h', '1d', '1w']
    bots = [
        {'id': 'BTC_TD9', 'symbol': 'BTC', 'strategy': 'TD9'},
        {'id': 'BTC_WYK', 'symbol': 'BTC', 'strategy': 'WYK'},
        {'id': 'BTC_HYB', 'symbol': 'BTC', 'strategy': 'HYB'},
        {'id': 'ETH_TD9', 'symbol': 'ETH', 'strategy': 'TD9'},
        {'id': 'ETH_WYK', 'symbol': 'ETH', 'strategy': 'WYK'},
        {'id': 'ETH_HYB', 'symbol': 'ETH', 'strategy': 'HYB'},
        {'id': 'HYPE_TD9', 'symbol': 'HYPE', 'strategy': 'TD9'},
        {'id': 'HYPE_WYK', 'symbol': 'HYPE', 'strategy': 'WYK'},
        {'id': 'HYPE_HYB', 'symbol': 'HYPE', 'strategy': 'HYB'}
    ]
    
    while True:
        # Precalcular contexto Macro Semanal para Top-Down Confluence (Con Anti-Bias Shield)
        weekly_context_cache = {}
        for symbol in ['BTC', 'ETH', 'HYPE']:
            try:
                w_raw = get_data(f"{symbol}/USDT", "1w", limit=100)
                if w_raw is not None and len(w_raw) >= 5:
                    w_df = calculate_td_sequential(w_raw)
                    w_closed = w_df.iloc[-2]
                    w_live = w_df.iloc[-1]
                    w_td = int(w_closed.get('td_count', 0))
                    
                    # 1. ANTI-BIAS SHIELD: Ventana de Caducidad DeMark (Max 4 Barras / 1 to 4 bars decay)
                    is_within_sell_window = (9 <= w_td <= 12)
                    is_within_buy_window = (-12 <= w_td <= -9)
                    
                    # 2. ANTI-BIAS SHIELD: Price Flip & TDST Risk Line Invalidation Guard
                    w_closed_high = float(w_closed.get('high', float('inf')))
                    w_closed_low = float(w_closed.get('low', 0.0))
                    w_live_price = float(w_live.get('close', w_closed.get('close', 0.0)))
                    w_perf = bool(w_closed.get('td_perfected', False))
                    w_tdst_res = float(w_closed.get('tdst_res', 0.0))
                    w_tdst_sup = float(w_closed.get('tdst_sup', 0.0))
                    
                    tdst_invalidated = False
                    if w_td >= 9 and w_tdst_res > 0 and w_live_price > w_tdst_res:
                        tdst_invalidated = True
                    elif w_td <= -9 and w_tdst_sup > 0 and w_live_price < w_tdst_sup:
                        tdst_invalidated = True
                    
                    # Para Venta: activo solo si está dentro de la ventana de 4 barras, precio <= max vela 9 y NO invalidado por TDST
                    is_sell_exhaustion_active = is_within_sell_window and (w_live_price <= w_closed_high) and not tdst_invalidated
                    # Para Compra: activo solo si está dentro de la ventana de 4 barras, precio >= min vela 9 y NO invalidado por TDST
                    is_buy_exhaustion_active = is_within_buy_window and (w_live_price >= w_closed_low) and not tdst_invalidated

                    # Modulador dinámico de convicción DeMark:
                    # Perfeccionado = ±0.06 (alta probabilidad de reversión según DeMark)
                    # No perfeccionado = ±0.03 (impulso no culminado, sesgo atenuado para no bloquear longs)
                    macro_weight = 0.06 if w_perf else 0.03

                    weekly_context_cache[symbol] = {
                        'td_count': w_td,
                        'td_countdown': int(w_closed.get('td_countdown', 0)),
                        'td_perfected': w_perf,
                        'tdst_res': w_tdst_res,
                        'tdst_sup': w_tdst_sup,
                        'macro_weight': macro_weight,
                        'rsi': float(w_closed.get('rsi', 50.0)),
                        'is_sell_exhaustion_active': is_sell_exhaustion_active,
                        'is_buy_exhaustion_active': is_buy_exhaustion_active,
                        'df': w_df
                    }
                    perf_str = "PERF" if w_perf else "UNPERF"
                    if is_sell_exhaustion_active:
                        print(f"🏛 MACRO CONFLUENCE [1W] | {symbol} | TD: {w_td} [{perf_str}] | TDST Res: ${w_tdst_res:.2f} | Sesgo Correctivo Activo (Ventana: {w_td}/12, Mod: ±{macro_weight})")
                    elif is_buy_exhaustion_active:
                        print(f"🏛 MACRO CONFLUENCE [1W] | {symbol} | TD: {w_td} [{perf_str}] | TDST Sup: ${w_tdst_sup:.2f} | Sesgo Acumulativo Activo (Ventana: {abs(w_td)}/12, Mod: ±{macro_weight})")
                    elif tdst_invalidated:
                        print(f"🏛 MACRO CONFLUENCE [1W] | {symbol} | TD: {w_td} | Sesgo Invalidado por Ruptura TDST (${w_live_price:.2f} vs TDST ${w_tdst_res:.2f})")
                    elif abs(w_td) >= 7:
                        print(f"🏛 MACRO CONFLUENCE [1W] | {symbol} | TD: {w_td} | Sesgo Neutralizado (Runaway Trend / Extensión)")
            except Exception as e:
                print(f"Error fetching weekly context for {symbol}: {e}")

        for tf in timeframes:
            df_cache = {}
            market_context_cache = {}
            for symbol in ['BTC', 'ETH', 'HYPE']:
                try:
                    if tf == '1w' and symbol in weekly_context_cache:
                        df = weekly_context_cache[symbol]['df']
                    else:
                        raw_df = get_data(f"{symbol}/USDT", tf)
                        df = calculate_td_sequential(raw_df) if raw_df is not None else None
                        
                    if df is not None and len(df) >= 5:
                        df_cache[symbol] = df
                        # Precalcular Volume Profile y Divergencias Wyckoff 1 SOLA VEZ por activo y timeframe
                        vp_data = calculate_volume_profile(df.tail(min(100, len(df))), bins=20)
                        divergence = detect_divergences(df.iloc[:-1])
                        market_context_cache[symbol] = {
                            'vp_data': vp_data,
                            'divergence': divergence
                        }
                except Exception as e:
                    print(f"Error fetching {symbol} ({tf}): {e}")
                    
            for bot in bots:
                symbol = bot['symbol']
                if symbol not in df_cache: continue
                
                TIMEFRAME = tf
                SYMBOL = symbol
                try:
                    analyze_market(
                        df_cache[symbol], 
                        bot['id'], 
                        bot['strategy'], 
                        market_context_cache.get(symbol),
                        weekly_context_cache.get(symbol)
                    )
                except Exception as e:
                    print(f"Error analizando {bot['id']} [{tf}]: {e}")
            import gc
            gc.collect()
            
        import time as time_mod
        now = time_mod.time()
        sleep_sec = 300 - (now % 300)
        time_mod.sleep(sleep_sec + 3)