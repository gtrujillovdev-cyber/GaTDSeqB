import os
import ccxt
from dotenv import load_dotenv

load_dotenv()

exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_SECRET'),
    'enableRateLimit': True,
})
exchange.set_sandbox_mode(True)
try:
    balance = exchange.fetch_balance()
    print("✅ Conexión a Binance Testnet Exitosa!")
    print(f"💰 Saldo USDT de prueba: {balance.get('USDT', {}).get('free', 0)}")
except Exception as e:
    print(f"❌ Error de conexión: {e}")
