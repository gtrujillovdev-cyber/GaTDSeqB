import time
import ccxt
import pandas as pd
import json
import os
import requests
import datetime
import math

# Archivos de estado
STATE_FILE = "state.json"
TRADES_FILE = "trades.json"

TELEGRAM_TOKEN = "8897428364:AAEXvrsysxH7_dOQftBnQbtQr_c_uof5qhU"
CHAT_ID = "1097154358"

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
    df = get_data("BTC/USDT", "4h")
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
    
    state = {
        "status": "IN_TRADE",
        "trade_id": trade_id,
        "position": action,
        "entry_price": price,
        "stop_loss": sl,
        "take_profit": tp,
        "timestamp": time_str
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
    
    # Registro de apertura
    trades = load_trades()
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
        
    msg = f"🟢 <b>NUEVA OPERACIÓN ({action})</b>\n\n💰 Precio: ${price:,.2f}\n🛡 Stop Loss: ${sl:,.2f}\n🎯 Take Profit: ${tp:,.2f}\n🧠 Estrategia: {reason}"
    send_telegram(msg)
    print(f"Trade {action} Ejecutado a ${price:.2f} | SL: ${sl:.2f} | TP: ${tp:.2f}")

def check_exit_conditions(current_price, atr, state):
    action = state["position"]
    sl = state["stop_loss"]
    tp = state["take_profit"]
    entry = state["entry_price"]
    trade_id = state.get("trade_id", str(int(time.time())))
    
    closed = False
    pnl_pct = 0
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
            pnl_pct = ((current_price - entry) / entry) * 100
            closed = True
            close_reason = "Stop Loss"
        elif current_price >= tp:
            print("✅ Take Profit alcanzado.")
            pnl_pct = ((current_price - entry) / entry) * 100
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
            pnl_pct = ((entry - current_price) / entry) * 100
            closed = True
            close_reason = "Stop Loss"
        elif current_price <= tp:
            print("✅ Take Profit alcanzado.")
            pnl_pct = ((entry - current_price) / entry) * 100
            closed = True
            close_reason = "Take Profit"

    # Save state if trailing stop moved
    if updated_sl != sl and not closed:
        state["stop_loss"] = updated_sl
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
            
    if closed:
        # Calcular PNL en dolares asumiendo un banco de $10,000 para el registro local
        pnl_dollars = (pnl_pct / 100) * 10000.0
        print(f"Operación cerrada. Beneficio/Pérdida: {pnl_pct:.2f}% (${pnl_dollars:.2f})")
        
        # Guardar cierre en el registro
        time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        trades = load_trades()
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
        msg = f"{emoji} <b>OPERACIÓN CERRADA ({close_reason})</b>\n\n💰 Precio Cierre: ${current_price:,.2f}\n💵 Beneficio (Virtual): ${pnl_dollars:,.2f}\n📈 Rendimiento: {pnl_pct:.2f}%"
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
    print("Iniciando GaTDSEQ Bot (Modo Cuantitativo)...")
    send_telegram("🤖 <b>Bot Reiniciado</b>\n\nEl sistema se ha conectado con éxito. Monitorizando BTC/USDT en temporalidad 4H.")
    while True:
        analyze_market()
        time.sleep(60 * 5) # Comprueba cada 5 minutos
