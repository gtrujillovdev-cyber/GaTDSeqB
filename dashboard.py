import streamlit as st
import json
import ccxt
import os
import time

st.set_page_config(page_title="Bot TD Secuencial", layout="wide")
st.title("🤖 Consola de Control - TD Secuencial")

CONTROL_FILE = "control.json"
LOG_FILE = "bot_log.txt"

def load_control():
    if not os.path.exists(CONTROL_FILE):
        return {"status": "stopped", "timeframe": "1m", "risk": 10}
    with open(CONTROL_FILE, 'r') as f:
        return json.load(f)
        
def save_control(data):
    with open(CONTROL_FILE, 'w') as f:
        json.dump(data, f)
        
control = load_control()

# Sidebar
st.sidebar.header("🏦 Cartera Binance (Testnet)")
try:
    exchange = ccxt.binance({
        'apiKey': 'RZ3x3KlwYPmtkJwh7ni0w4nkHMRSQovlvxXC9B5R74d5PI8VIg4t4sikBQfqUjpr',
        'secret': 'M4NVCD9XSZ2sfzqz3PKoCKpPeiWpdVMjtQ8x6dMF4YbwEcwZtDoBecxqI6uoOgz6',
        'enableRateLimit': True,
    })
    exchange.set_sandbox_mode(True)
    balance = exchange.fetch_balance()
    usdt = balance.get('USDT', {}).get('free', 0)
    btc = balance.get('BTC', {}).get('free', 0)
    st.sidebar.metric("USDT Disponible", f"${usdt:.2f}")
    st.sidebar.metric("BTC Disponible", f"₿ {btc:.4f}")
except Exception as e:
    st.sidebar.error("Error conectando a Binance")

# Main Panel
col1, col2 = st.columns(2)

with col1:
    st.subheader("⚙️ Configuración")
    opciones_tf = ["1m", "5m", "15m", "1h", "4h", "1d"]
    idx = opciones_tf.index(control['timeframe']) if control['timeframe'] in opciones_tf else 0
    new_tf = st.selectbox("Temporalidad (Timeframe)", opciones_tf, index=idx)
    new_risk = st.slider("Riesgo por Operación (% del Saldo)", 1, 100, control['risk'])
    
    if new_tf != control['timeframe'] or new_risk != control['risk']:
        control['timeframe'] = new_tf
        control['risk'] = new_risk
        save_control(control)
        st.success("Configuración actualizada.")

with col2:
    st.subheader("🚀 Estado del Bot")
    if control['status'] == 'running':
        st.success("🟢 EL BOT ESTÁ EN MARCHA Y ESCANEANDO")
        if st.button("🛑 DETENER BOT", use_container_width=True):
            control['status'] = 'stopped'
            save_control(control)
            st.rerun()
    else:
        st.error("🔴 EL BOT ESTÁ DETENIDO")
        if st.button("▶️ INICIAR BOT", use_container_width=True):
            control['status'] = 'running'
            save_control(control)
            st.rerun()

st.subheader("📜 Registro de Actividad (Logs en vivo)")
if st.button("🔄 Actualizar Logs"):
    pass

if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r") as f:
        logs = f.readlines()
        if logs:
            st.code("".join(logs[-15:][::-1]), language='bash')
        else:
            st.info("No hay registros todavía.")
else:
    st.info("El archivo de logs se creará cuando el bot arranque.")
