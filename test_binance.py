import ccxt
exchange = ccxt.binance({
    'apiKey': 'RZ3x3KlwYPmtkJwh7ni0w4nkHMRSQovlvxXC9B5R74d5PI8VIg4t4sikBQfqUjpr',
    'secret': 'M4NVCD9XSZ2sfzqz3PKoCKpPeiWpdVMjtQ8x6dMF4YbwEcwZtDoBecxqI6uoOgz6',
    'enableRateLimit': True,
})
exchange.set_sandbox_mode(True)
try:
    balance = exchange.fetch_balance()
    print("✅ Conexión a Binance Testnet Exitosa!")
    print(f"💰 Saldo USDT de prueba: {balance.get('USDT', {}).get('free', 0)}")
except Exception as e:
    print(f"❌ Error de conexión: {e}")
