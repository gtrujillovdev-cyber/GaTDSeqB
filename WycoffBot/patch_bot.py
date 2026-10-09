import re

with open('bot.py', 'r') as f:
    code = f.read()

# 1. Add imports
import_statement = "from volume_profile import calculate_volume_profile\nfrom wycoff_logic import detect_divergences\n"
if "from volume_profile" not in code:
    code = code.replace("import pandas as pd\n", "import pandas as pd\n" + import_statement)

# 2. Rewrite analyze_market
new_analyze_market = """def analyze_market():
    global TIMEFRAME, SYMBOL
    
    df = get_data(f"{SYMBOL}/USDT", TIMEFRAME)
    if df is None or len(df) < 50: return
    
    # Calculate Volume Profile using the last 50 candles (approx)
    vp_data = calculate_volume_profile(df.tail(100), bins=20)
    poc = vp_data['poc']
    vah = vp_data['vah']
    val = vp_data['val']
    
    # --- VELAS ---
    closed_candle = df.iloc[-2]
    live_candle = df.iloc[-1]
    
    # Parametros para ENTRADAS
    current_live_price = closed_candle['close']
    ema200 = closed_candle['ema_200']
    rsi = closed_candle['rsi']
    raw_atr = closed_candle['atr']
    
    # --- ATR DYNAMIC SCALING ---
    if TIMEFRAME == '5m': tf_mult = 2.0
    elif TIMEFRAME == '15m': tf_mult = 1.8
    elif TIMEFRAME == '1h': tf_mult = 1.5
    elif TIMEFRAME == '4h': tf_mult = 1.2
    else: tf_mult = 1.0 # 1d
    
    atr = raw_atr * tf_mult
    trigger_time = str(closed_candle['timestamp'])
    
    # --- WYCKOFF + RSI LOGIC ---
    divergence = detect_divergences(df.iloc[:-1]) # Analizamos hasta la vela cerrada
    
    # Volumen climático
    volume = closed_candle.get('volume', 0)
    avg_vol = df['volume'].iloc[-20:-1].mean()
    climatic_volume = volume > (avg_vol * 1.5)
    
    # Acción del precio (rechazo)
    candle_range = closed_candle['high'] - closed_candle['low']
    if candle_range == 0: candle_range = 1
    close_pct = (closed_candle['close'] - closed_candle['low']) / candle_range # 0 = low, 1 = high
    
    state = load_state()
    
    # Update UI state
    state["poc"] = poc
    state["vah"] = vah
    state["val"] = val
    state["rsi_divergence"] = divergence
    import json
    with open(f"state_{TIMEFRAME}.json", "w") as f:
        json.dump(state, f)
        
    if state.get("status") == "IN_TRADE": return
    
    print(f"Wyckoff {SYMBOL} [{TIMEFRAME}] | Price: {current_live_price:.2f} | VAL: {val:.0f} | VAH: {vah:.0f} | RSI: {rsi:.2f}")
    
    # SPRING (Bullish)
    if closed_candle['low'] < val and climatic_volume and close_pct >= 0.5:
        if divergence == 'BULLISH' or rsi < 45: # Como en el bot original (filtro RSI)
            print(">>> SPRING DETECTED (LONG) <<<")
            stop_loss = current_live_price - (atr * 1.0)
            take_profit = current_live_price + (atr * 1.5)
            reason = f"Wyckoff Spring + RSI {rsi:.1f}"
            
            risk_matrix = {"1d": 0.15, "4h": 0.10, "1h": 0.05, "15m": 0.02, "5m": 0.01}
            base_risk = risk_matrix.get(TIMEFRAME, 0.01)
            
            conviction_multiplier = 1.5 if rsi < 30 else 1.0 # Manteniendo la matriz de convicción del bot original
            final_risk = base_risk * conviction_multiplier
            
            execute_trade("BUY", current_live_price, stop_loss, take_profit, reason, trigger_time, final_risk)
            
    # UPTHRUST (Bearish)
    elif closed_candle['high'] > vah and climatic_volume and close_pct <= 0.5:
        if divergence == 'BEARISH' or rsi > 55:
            print(">>> UPTHRUST DETECTED (SHORT) <<<")
            stop_loss = current_live_price + (atr * 1.0)
            take_profit = current_live_price - (atr * 1.5)
            reason = f"Wyckoff Upthrust + RSI {rsi:.1f}"
            
            risk_matrix = {"1d": 0.15, "4h": 0.10, "1h": 0.05, "15m": 0.02, "5m": 0.01}
            base_risk = risk_matrix.get(TIMEFRAME, 0.01)
            
            conviction_multiplier = 1.5 if rsi > 70 else 1.0
            final_risk = base_risk * conviction_multiplier
            
            execute_trade("SELL", current_live_price, stop_loss, take_profit, reason, trigger_time, final_risk)
"""

# We need to replace the analyze_market function in bot.py
pattern = re.compile(r"def analyze_market\(\):.*?elif state\.get\(\"status\"\) == \"IN_TRADE\":", re.DOTALL)
# wait, my regex might miss or cut too much. Let's just find the index of def analyze_market and def execute_reinforcement
start_idx = code.find("def analyze_market():")
end_idx = code.find("def execute_reinforcement(")

if start_idx != -1 and end_idx != -1:
    code = code[:start_idx] + new_analyze_market + "\n\n" + code[end_idx:]
    with open('bot.py', 'w') as f:
        f.write(code)
    print("Patch applied successfully.")
else:
    print("Could not find analyze_market or execute_reinforcement bounds.")
