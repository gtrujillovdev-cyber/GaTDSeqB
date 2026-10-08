import time
import ccxt
import pandas as pd
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

def get_data(symbol="BTC/USDT", timeframe="4h", limit=1000):
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
    
    for i in range(len(df)):
        if i < 4:
            td_counts.append(0)
            td_countdowns.append(0)
            continue
            
        close = df['close'].iloc[i]
        close_4_ago = df['close'].iloc[i-4]
        
        # 1. SETUP PHASE
        if close > close_4_ago:
            setup_up += 1
            setup_down = 0
            td_counts.append(setup_up)
            if setup_up == 9:
                setup_up_active = True
                setup_down_active = False
                countdown_up = 0
        elif close < close_4_ago:
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
            
        # 2. COUNTDOWN PHASE
        if i >= 2:
            high_2_ago = df['high'].iloc[i-2]
            low_2_ago = df['low'].iloc[i-2]
            
            if setup_up_active and close > high_2_ago:
                countdown_up += 1
                if countdown_up == 13: setup_up_active = False
            
            if setup_down_active and close < low_2_ago:
                countdown_down += 1
                if countdown_down == 13: setup_down_active = False
        
        if setup_up_active and countdown_up > 0: td_countdowns.append(countdown_up)
        elif setup_down_active and countdown_down > 0: td_countdowns.append(-countdown_down)
        else: td_countdowns.append(0)
            
    df['td_count'] = td_counts
    df['td_countdown'] = td_countdowns
    return df


def get_global_open_trades():
    import glob, json
    open_count = 0
    for file in glob.glob("state_*.json"):
        try:
            with open(file, "r") as f:
                if json.load(f).get("status") == "IN_TRADE": open_count += 1
        except: pass
    return open_count

def analyze_market():
    global TIMEFRAME, SYMBOL
    
    df = get_data(f"{SYMBOL}/USDT", TIMEFRAME)
    if df is None: return
    
    df = calculate_td_sequential(df)
    
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
    
    # --- ATR DYNAMIC SCALING (Volatility Adjustment) ---
    if TIMEFRAME == '5m': tf_mult = 2.0
    elif TIMEFRAME == '15m': tf_mult = 1.8
    elif TIMEFRAME == '1h': tf_mult = 1.5
    elif TIMEFRAME == '4h': tf_mult = 1.2
    else: tf_mult = 1.0 # 1d
    
    atr = raw_atr * tf_mult
    # ---------------------------------------------------
    
    count = closed_candle['td_count']
    countdown = closed_candle['td_countdown']
    trigger_time = str(closed_candle['timestamp'])
    
    state = load_state()
    
    if abs(count) >= 7 or state.get("status") == "IN_TRADE":
        print(f"Analizando {SYMBOL} en {TIMEFRAME} con Inteligencia Cuantitativa (TD9 + EMA200 + RSI + ATR)...")
        print(f"{SYMBOL} | Precio: ${current_live_price:.2f} | TD Count: {count} | RSI: {rsi:.2f} | EMA200: {ema200:.2f}")
    
    # Save the current TD Count to state so the dashboard can display it
    # UI Trick: Show Countdown if active, else Setup
    state["td_count"] = int(countdown) if countdown != 0 else int(count)
    import json
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

    
    if state.get("status") == "IDLE":
        # CONDICIÓN DE COMPRA LONG (Agotamiento bajista)
        if count == -9:
            if rsi < 45: # Permitir compras si no está extremadamente sobrecomprado
                is_counter_trend = current_live_price < ema200 # Comprar bajo la EMA200 es contra tendencia principal
                if is_counter_trend:
                    print(">>> ALERTA DE COMPRA <<< (TD9 Contra Tendencia - Scalp 1 a 4 Velas)")
                    stop_loss = current_live_price - (atr * 1.0)
                    take_profit = current_live_price + (atr * 1.5)
                    reason = "TD9 Buy (Counter-Trend)"
                else:
                    print(">>> ALERTA DE COMPRA <<< (TD9 A Favor de Tendencia)")
                    stop_loss = current_live_price - (atr * 1.5)
                    take_profit = current_live_price + (atr * 3.0)
                    reason = "TD9 Buy (Trend)"
                    
                if state.get("last_trigger_time") == trigger_time:
                    print("⚠️ Señal ya operada en esta vela. Ignorando para evitar bucle de reentradas (Gatling Bug).")
                else:
                    risk_matrix = {"1d": 0.15, "4h": 0.10, "1h": 0.05, "15m": 0.02, "5m": 0.01}
                    base_risk = risk_matrix.get(TIMEFRAME, 0.01)
                    if is_counter_trend: base_risk *= 0.5 # Mitad de riesgo contra tendencia
                    
                    conviction_multiplier = 1.0
                    if rsi < 30: conviction_multiplier += 0.5
                    bb_bypass = False
                    if current_live_price <= bb_lower:
                        print("🔥 COMPRESIÓN BOLLINGER: Precio perforando la Banda Inferior. Multiplicador aumentado.")
                        conviction_multiplier += 0.5
                        bb_bypass = True
                        reason += " [🔥BB]"
                        
                    final_risk = base_risk * conviction_multiplier
                    
                    # 1. VOLUME FILTER
                    volume = closed_candle.get('volume', 0)
                    volume_sma = closed_candle.get('volume_sma', 0)
                    if volume < volume_sma * 0.8:
                        if bb_bypass:
                            print("🔥 EXCEPCIÓN BOLLINGER: Falta volumen, pero la extrema dilatación salva el trade.")
                        else:
                            print("🛡 Filtro de Volumen: TD9 ignorado por falta de liquidez institucional.")
                            return
                        
                    # 2. VANGUARD SCALING (35% Riesgo Inicial)
                    state["full_target_risk_usd"] = final_risk
                    final_risk = final_risk * 0.35
                    print(f"🎯 VANGUARDIA SCALING: Entrando con solo 35% del riesgo normal (${final_risk:.2f}).")
                    
                    execute_trade("BUY", current_live_price, stop_loss, take_profit, reason, trigger_time, final_risk)
            else:
                print("TD9 ignorado: El RSI no permite la compra.")
                
        # CONDICIÓN DE VENTA SHORT (Agotamiento alcista)
        elif count == 9:
            if rsi > 55: # Permitir ventas si no está extremadamente sobrevendido
                is_counter_trend = current_live_price > ema200 # Vender sobre la EMA200 es contra tendencia principal
                if is_counter_trend:
                    print(">>> ALERTA DE VENTA <<< (TD9 Contra Tendencia - Scalp 1 a 4 Velas)")
                    stop_loss = current_live_price + (atr * 1.0)
                    take_profit = current_live_price - (atr * 1.5)
                    reason = "TD9 Sell (Counter-Trend)"
                else:
                    print(">>> ALERTA DE VENTA <<< (TD9 A Favor de Tendencia)")
                    stop_loss = current_live_price + (atr * 1.5)
                    take_profit = current_live_price - (atr * 3.0)
                    reason = "TD9 Sell (Trend)"
                    
                if state.get("last_trigger_time") == trigger_time:
                    print("⚠️ Señal ya operada en esta vela. Ignorando para evitar bucle de reentradas (Gatling Bug).")
                else:
                    risk_matrix = {"1d": 0.15, "4h": 0.10, "1h": 0.05, "15m": 0.02, "5m": 0.01}
                    base_risk = risk_matrix.get(TIMEFRAME, 0.01)
                    if is_counter_trend: base_risk *= 0.5 # Mitad de riesgo contra tendencia
                    
                    conviction_multiplier = 1.0
                    if rsi > 70: conviction_multiplier += 0.5
                    bb_bypass = False
                    if current_live_price >= bb_upper:
                        print("🔥 COMPRESIÓN BOLLINGER: Precio perforando la Banda Superior. Multiplicador aumentado.")
                        conviction_multiplier += 0.5
                        bb_bypass = True
                        reason += " [🔥BB]"
                        
                    final_risk = base_risk * conviction_multiplier
                    
                    # 1. VOLUME FILTER
                    volume = closed_candle.get('volume', 0)
                    volume_sma = closed_candle.get('volume_sma', 0)
                    if volume < volume_sma * 0.8:
                        if bb_bypass:
                            print("🔥 EXCEPCIÓN BOLLINGER: Falta volumen, pero la extrema dilatación salva el trade.")
                        else:
                            print("🛡 Filtro de Volumen: TD9 ignorado por falta de liquidez institucional.")
                            return
                        
                    # 2. VANGUARD SCALING (35% Riesgo Inicial)
                    state["full_target_risk_usd"] = final_risk
                    final_risk = final_risk * 0.35
                    print(f"🎯 VANGUARDIA SCALING: Entrando con solo 35% del riesgo normal (${final_risk:.2f}).")
                    
                    execute_trade("SELL", current_live_price, stop_loss, take_profit, reason, trigger_time, final_risk)
            else:
                print("TD9 ignorado: El RSI no permite el short.")
                
    elif state.get("status") == "IN_TRADE":
        pos = state.get("position")
        if pos == "BUY" and countdown == -13 and not state.get("reinforced_13"):
            print(">>> ALERTA DE REFUERZO (DCA) TD-13 (LONG) <<<")
            execute_reinforcement(current_live_price, atr, state, "BUY")
        elif pos == "SELL" and countdown == 13 and not state.get("reinforced_13"):
            print(">>> ALERTA DE REFUERZO (DCA) TD-13 (SHORT) <<<")
            execute_reinforcement(current_live_price, atr, state, "SELL")
            
        check_exit_conditions(live_candle, closed_candle, atr, state)

def execute_reinforcement(price, atr, state, action):
    import time, json
    
    trades = []
    import os
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "r") as f:
            try: trades = json.load(f)
            except: pass
            
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
        new_sl = price - (atr * 1.5)
        new_tp_offset = atr * 2.0
    else:
        new_sl = price + (atr * 1.5)
        new_tp_offset = - (atr * 2.0)
        
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
    
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
        
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
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
    
    # Registro de apertura
    trades.append({
        "trade_id": trade_id,
        "time": time_str,
        "type": "COMPRA (Apertura)" if action == "BUY" else "VENTA (Apertura)",
        "reason": reason,
        "price": price,
        "pnl": 0.0
    })
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f)
        
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

def check_exit_conditions(live_candle, closed_candle, atr, state):
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
    
    if action == "BUY":
        # Scale-Out Parcial (Asegurar 50% de Ganancias en 1.0 ATR)
        if current_live_price >= entry + (atr * 1.0) and not state.get("scaled_out", False):
            import datetime as dt_mod
            print("💰 SCALE-OUT: Asegurando 50% de las ganancias.")
            partial_pnl = ((current_live_price - entry) * (size_btc * 0.5)) - (state.get("entry_fee_usd", 0) * 0.5) - (current_live_price * (size_btc * 0.5) * 0.0004)
            trades = load_trades()
            trades.append({
                "trade_id": trade_id + "_partial",
                "time": dt_mod.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "VENTA (Cierre Parcial 50%)",
                "reason": "Scale-Out Táctico",
                "price": current_live_price,
                "pnl": partial_pnl
            })
            with open(TRADES_FILE, "w") as f:
                json.dump(trades, f)
            
            # Actualizar State
            state["size_btc"] = size_btc * 0.5
            state["size_usd"] = state.get("size_usd", 0) * 0.5
            state["entry_fee_usd"] = state.get("entry_fee_usd", 0) * 0.5
            state["scaled_out"] = True
            
            if updated_sl < entry:
                updated_sl = entry
                state["stop_loss"] = updated_sl
                
            send_telegram(f"💰 <b>SCALE-OUT (50%) | {SYMBOL} [{TIMEFRAME}]</b>\nLocked in profit on half the position. Risk neutralized to Breakeven.\n\n<b>Partial PnL:</b> ${partial_pnl:,.2f}")
            
        # Escudo Breakeven (0.75 ATR a favor -> Stop a precio de entrada)
        if current_live_price >= entry + (atr * 0.75) and updated_sl < entry:
            updated_sl = entry
            state["stop_loss"] = updated_sl
            print(f"🛡 BREAKEVEN SHIELD ACTIVO: SL subido a precio de entrada (${entry:.2f})")
            send_telegram(f"🛡 <b>BREAKEVEN SHIELD | {SYMBOL} [{TIMEFRAME}]</b>\nPrice advanced 0.75 ATR in favor. Risk neutralized.\n\n<b>Stop Loss:</b> Moved to Entry (${entry:,.2f})")
            
        # Trailing stop based strictly on firmly closed candle to avoid Time Paradox
        new_sl = current_closed_price - (atr * 1.5)
        if new_sl > sl:
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
                send_telegram(f"🔥 <b>TP EXTENSION | {SYMBOL} [{TIMEFRAME}]</b>\nStrong momentum detected at Take Profit. Letting the winner run.\n\n<b>New TP:</b> ${tp + (atr * 2.0):,.2f}\n<b>Locked SL:</b> ${max(updated_sl, tp - (atr * 0.5)):,.2f}")
                state["take_profit"] = tp + (atr * 2.0)
                if (tp - (atr * 0.5)) > updated_sl:
                    updated_sl = tp - (atr * 0.5)
            else:
                print("✅ Take Profit alcanzado en la mecha superior.")
                pnl_dollars = (tp - entry) * size_btc
                exit_fee = (tp * size_btc) * 0.0004
                pnl_dollars -= (state.get("entry_fee_usd", 0) + exit_fee)
                closed = True
                close_reason = "Take Profit"
                current_live_price = tp # For closing log
            
    elif action == "SELL":
        # Trailing stop based strictly on firmly closed candle to avoid Time Paradox
        new_sl = current_closed_price + (atr * 1.5)
        if new_sl < sl:
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
                send_telegram(f"🔥 <b>TP EXTENSION | {SYMBOL} [{TIMEFRAME}]</b>\nStrong momentum detected at Take Profit. Letting the winner run.\n\n<b>New TP:</b> ${tp - (atr * 2.0):,.2f}\n<b>Locked SL:</b> ${min(updated_sl, tp + (atr * 0.5)):,.2f}")
                state["take_profit"] = tp - (atr * 2.0)
                if (tp + (atr * 0.5)) < updated_sl:
                    updated_sl = tp + (atr * 0.5)
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
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
            
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
        with open(TRADES_FILE, "w") as f:
            json.dump(trades, f)
            
        # Reset state
        state["status"] = "IDLE"
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
            
        emoji = "🟩" if pnl_dollars > 0 else "🟥"
        result_str = "PROFIT" if pnl_dollars > 0 else "LOSS"
        sign = "+" if pnl_dollars > 0 else ""
        msg = (f"{emoji} <b>POSITION CLOSED | {SYMBOL} [{TIMEFRAME}]</b>\n\n"
               f"<b>Trigger:</b> {close_reason}\n"
               f"<b>Exit Price:</b> ${current_live_price:,.2f}\n"
               f"<b>Net {result_str}:</b> {sign}${pnl_dollars:,.2f}\n"
               f"<b>Updated Bank:</b> ${new_bank:,.2f}")
        send_telegram(msg)

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Alerta: {STATE_FILE} corrupto. Restaurando a IDLE.")
            return {"status": "IDLE"}
    return {"status": "IDLE"}

def load_trades():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Alerta: {TRADES_FILE} corrupto. Iniciando lista vacía.")
            return []
    return []

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--bank', type=float, default=10000.0, help='Initial bankroll')
    args = parser.parse_args()

    INITIAL_BANK = args.bank
    print(f"Iniciando GaTDSEQ Bot UNIFICADO | Bank: ${INITIAL_BANK}...")
    send_telegram("🏛 <b>SYSTEM INITIALIZED</b>\n\nQuantitative Core online. Engine tracking multi-asset pipeline (5 Timeframes).")
    
    timeframes = ['1h', '4h', '1d']
    assets = ['BTC', 'ETH', 'HYPE']
    
    while True:
        for symbol in assets:
            for tf in timeframes:
                # Reassign globals for the functions to use
                # No global needed here
                TIMEFRAME = tf
                SYMBOL = symbol
                STATE_FILE = f"state_{symbol}_{tf}.json"
                TRADES_FILE = f"trades_{symbol}_{tf}.json"
                
                try:
                    analyze_market()
                    import gc
                    gc.collect() # Free up dataframe RAM aggressively
                except Exception as e:
                    print(f"Error analizando {symbol} {tf}: {e}")
                    
        # Sincronización de reloj militar (Evita el drift del sleep)
        # Despierta siempre exactamente en los minutos: 00, 05, 10, 15, 20...
        import time as time_mod
        now = time_mod.time()
        sleep_sec = 300 - (now % 300)
        # Añadimos 3 segundos de gracia para que Binance haya cerrado y publicado la vela
        time_mod.sleep(sleep_sec + 3)

