import time
import ccxt
import pandas as pd
import json
import os
import requests
import datetime
import math
import argparse

TIMEFRAME = '4h'

# Archivos de estado
STATE_FILE = "state.json"
TRADES_FILE = "trades.json"

TELEGRAM_TOKEN = "8897428364:AAEXvrsysxH7_dOQftBnQbtQr_c_uof5qhU"
CHAT_ID = "1097154358"
RISK_PCT = 0.02 # Riesgo del 2% por operacion
INITIAL_BANK = 10000.0

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Error sending telegram:", e)

# Inicializar Binance
exchange = ccxt.binance({
    'enableRateLimit': True,
})

def calculate_rsi(series, period=14):
    delta = series.diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    roll_up = up.ewm(span=period, min_periods=period).mean()
    roll_down = down.abs().ewm(span=period, min_periods=period).mean()
    rs = roll_up / roll_down
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()

def get_data(symbol="BTC/USDT", timeframe="4h", limit=500):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Filtro Macro (EMA 200)
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # Filtro de Agotamiento (RSI)
        df['rsi'] = calculate_rsi(df['close'], 14)
        
        # Volatilidad para Stop Loss Dinámico (ATR)
        df['atr'] = calculate_atr(df, 14)
        
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def calculate_td_sequential(df):
    setup_up = 0
    setup_down = 0
    td_counts = []
    
    for i in range(len(df)):
        if i < 4:
            td_counts.append(0)
            continue
            
        close = df['close'].iloc[i]
        close_4_ago = df['close'].iloc[i-4]
        
        if close > close_4_ago:
            setup_up += 1
            setup_down = 0
            td_counts.append(setup_up)
        elif close < close_4_ago:
            setup_down += 1
            setup_up = 0
            td_counts.append(-setup_down)
        else:
            setup_up = 0
            setup_down = 0
            td_counts.append(0)
            
    df['td_count'] = td_counts
    return df

def analyze_market():
    print("Analizando mercado con Inteligencia Cuantitativa (TD9 + EMA200 + RSI + ATR)...")
    global TIMEFRAME
    df = get_data("BTC/USDT", TIMEFRAME)
    if df is None: return
    
    df = calculate_td_sequential(df)
    last_candle = df.iloc[-1]
    
    # Parametros actuales
    current_price = last_candle['close']
    ema200 = last_candle['ema_200']
    rsi = last_candle['rsi']
    atr = last_candle['atr']
    count = last_candle['td_count']
    
    state = load_state()
    
    print(f"Precio: ${current_price:.2f} | TD Count: {count} | RSI: {rsi:.2f} | EMA200: {ema200:.2f}")
    
    # Save the current TD Count to state so the dashboard can display it
    state["td_count"] = int(count)
    import json
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

    
    if state.get("status") == "IDLE":
        # CONDICIÓN DE COMPRA LONG (Agotamiento bajista)
        if count == -9:
            if current_price > ema200 and rsi < 40:
                print(">>> ALERTA DE COMPRA <<< (TD9 Bajista completado + Tendencia Alcista + RSI favorable)")
                stop_loss = current_price - (atr * 1.5)
                take_profit = current_price + (atr * 3.0)
                execute_trade("BUY", current_price, stop_loss, take_profit, "TD9 Buy Perf")
            else:
                print("TD9 ignorado: Filtro Macro (EMA200) o RSI no permitieron la compra.")
                
        # CONDICIÓN DE VENTA SHORT (Agotamiento alcista)
        elif count == 9:
            if current_price < ema200 and rsi > 60:
                print(">>> ALERTA DE VENTA <<< (TD9 Alcista completado + Tendencia Bajista + RSI favorable)")
                stop_loss = current_price + (atr * 1.5)
                take_profit = current_price - (atr * 3.0)
                execute_trade("SELL", current_price, stop_loss, take_profit, "TD9 Sell Perf")
            else:
                print("TD9 ignorado: Filtro Macro o RSI no permitieron el short.")
                
    elif state.get("status") == "IN_TRADE":
        check_exit_conditions(current_price, atr, state)

def execute_trade(action, price, sl, tp, reason):
    time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trade_id = str(int(time.time()))
    
    # Risk Management Engine
    trades = load_trades()
    current_bank = INITIAL_BANK + sum(t.get('pnl', 0.0) for t in trades)
    
    # 1. Calculamos cuanto estamos dispuestos a perder ($)
    risk_amount = current_bank * RISK_PCT
    
    # 2. Calculamos la distancia del precio al stop loss
    sl_dist_price = abs(price - sl)
    
    # 3. Calculamos la cantidad de BTC que debemos comprar para que, si el precio llega al SL, perdamos exactamente 'risk_amount'
    position_size_btc = risk_amount / sl_dist_price
    
    # 4. Valor total de la posicion (Notional Value)
    position_size_usd = position_size_btc * price
    
    # 5. Spot Market Limit: No usar margen / apalancamiento (Capping al saldo disponible)
    if position_size_usd > current_bank:
        position_size_usd = current_bank
        position_size_btc = position_size_usd / price
        actual_risk_amount = position_size_btc * sl_dist_price
        print(f"Alerta: Capital insuficiente para riesgo completo. Operando sin apalancamiento. Riesgo ajustado a ${actual_risk_amount:.2f}")
    else:
        actual_risk_amount = risk_amount
    
    state = {
        "status": "IN_TRADE",
        "trade_id": trade_id,
        "position": action,
        "entry_price": price,
        "stop_loss": sl,
        "take_profit": tp,
        "timestamp": time_str,
        "size_btc": position_size_btc,
        "size_usd": position_size_usd,
        "risk_usd": actual_risk_amount
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
        
    msg = (f"🟢 <b>NUEVA OPERACIÓN ({action})</b>\n\n"
           f"💰 Precio: ${price:,.2f}\n"
           f"🛡 Stop Loss: ${sl:,.2f}\n"
           f"🎯 Take Profit: ${tp:,.2f}\n"
           f"💵 Inversión: ${position_size_usd:,.2f} ({position_size_btc:.4f} BTC)\n"
           f"⚠️ Riesgo Máximo: ${actual_risk_amount:,.2f} ({(actual_risk_amount/current_bank)*100:.2f}%)\n"
           f"🏦 Bankroll: ${current_bank:,.2f}\n"
           f"🧠 Estrategia: {reason}")
    send_telegram(msg)
    print(f"Trade {action} Ejecutado a ${price:.2f} | Inversión: ${position_size_usd:.2f} | Riesgo: ${actual_risk_amount:.2f}")

def check_exit_conditions(current_price, atr, state):
    action = state["position"]
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
        # Trailing stop
        new_sl = current_price - (atr * 1.5)
        if new_sl > sl:
            updated_sl = new_sl
            print(f"Trailing Stop (Buy) actualizado a ${updated_sl:.2f}")
            send_telegram(f"📈 <b>Trailing Stop Movido a tu favor</b>\n\n🛡 Nuevo Stop Loss: ${updated_sl:,.2f}\n💵 Precio actual: ${current_price:,.2f}")
            
        if current_price <= updated_sl:
            print("❌ Stop Loss impactado.")
            pnl_dollars = (updated_sl - entry) * size_btc
            closed = True
            close_reason = "Stop Loss"
        elif current_price >= tp:
            print("✅ Take Profit alcanzado.")
            pnl_dollars = (tp - entry) * size_btc
            closed = True
            close_reason = "Take Profit"
            
    elif action == "SELL":
        # Trailing stop
        new_sl = current_price + (atr * 1.5)
        if new_sl < sl:
            updated_sl = new_sl
            print(f"Trailing Stop (Sell) actualizado a ${updated_sl:.2f}")
            send_telegram(f"📉 <b>Trailing Stop Movido a tu favor</b>\n\n🛡 Nuevo Stop Loss: ${updated_sl:,.2f}\n💵 Precio actual: ${current_price:,.2f}")
            
        if current_price >= updated_sl:
            print("❌ Stop Loss impactado.")
            pnl_dollars = (entry - updated_sl) * size_btc
            closed = True
            close_reason = "Stop Loss"
        elif current_price <= tp:
            print("✅ Take Profit alcanzado.")
            pnl_dollars = (entry - tp) * size_btc
            closed = True
            close_reason = "Take Profit"

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
            "price": current_price,
            "pnl": pnl_dollars
        })
        with open(TRADES_FILE, "w") as f:
            json.dump(trades, f)
            
        # Reset state
        state["status"] = "IDLE"
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
            
        emoji = "✅" if pnl_dollars > 0 else "❌"
        msg = (f"{emoji} <b>OPERACIÓN CERRADA ({close_reason})</b>\n\n"
               f"💰 Precio Cierre: ${current_price:,.2f}\n"
               f"💵 Beneficio/Pérdida: ${pnl_dollars:,.2f}\n"
               f"🏦 Nuevo Bankroll: ${new_bank:,.2f}")
        send_telegram(msg)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"status": "IDLE"}

def load_trades():
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "r") as f:
            return json.load(f)
    return []

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--bank', type=float, default=10000.0, help='Initial bankroll')
    args = parser.parse_args()

    INITIAL_BANK = args.bank
    print(f"Iniciando GaTDSEQ Bot UNIFICADO | Bank: ${INITIAL_BANK}...")
    send_telegram("🤖 <b>Bot UNIFICADO Iniciado</b>\n\nControlando 5 timeframes simultáneamente para ahorrar RAM.")
    
    timeframes = ['5m', '15m', '1h', '4h', '1d']
    
    while True:
        for tf in timeframes:
            # Reassign globals for the functions to use
            # global TIMEFRAME, STATE_FILE, TRADES_FILE
            TIMEFRAME = tf
            STATE_FILE = f"state_{tf}.json"
            TRADES_FILE = f"trades_{tf}.json"
            
            try:
                analyze_market()
            except Exception as e:
                print(f"Error analizando {tf}: {e}")
                
        # Sleep for 5 minutes before checking all again
        
        # Sincronización de reloj militar (Evita el drift del sleep)
        # Despierta siempre exactamente en los minutos: 00, 05, 10, 15, 20...
        import time as time_mod
        now = time_mod.time()
        sleep_sec = 300 - (now % 300)
        # Añadimos 3 segundos de gracia para que Binance haya cerrado y publicado la vela
        time_mod.sleep(sleep_sec + 3)

