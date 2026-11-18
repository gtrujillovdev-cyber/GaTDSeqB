import json
import glob
import re

assets = ['BTC', 'ETH', 'HYPE']
timeframes = ['5m', '15m', '1h', '4h', '1d']

# 1. READ STATES
active_trades = []
for asset in assets:
    for tf in timeframes:
        file = f"/home/raspberry/GaTDSEQ/state_{asset}_{tf}.json"
        try:
            with open(file, 'r') as f:
                state = json.load(f)
                if state.get("status") == "IN_TRADE":
                    active_trades.append({
                        "asset": asset,
                        "tf": tf,
                        "position": state["position"],
                        "entry": state["entry_price"],
                        "size": state["size_usd"]
                    })
        except:
            pass

print("ACTIVE TRADES:")
for t in active_trades:
    print(t)

# 2. PROXIMITY TO TRADE (Read bot_unified.log)
# We need to find the LATEST "Analizando <asset> en <tf>"
print("\nPROXIMITY:")
import subprocess
try:
    log_output = subprocess.check_output("tail -n 100 /home/raspberry/GaTDSEQ/bot_unified.log", shell=True).decode('utf-8')
    
    metrics = {}
    for line in log_output.split('\n'):
        if " | TD Count: " in line:
            # BTC | Precio: $83321.81 | TD Count: -1 | RSI: 52.94 | EMA200: 75167.33
            m = re.match(r'^([^ ]+) \| Precio: \$([^ ]+) \| TD Count: ([-\d]+) \| RSI: ([^ ]+) \| EMA200:', line)
            if m:
                asset, price, td, rsi = m.groups()
                # Wait, this line doesn't have the timeframe!
                # It comes from the PREVIOUS line!
                pass

    # A better way to parse is to iterate line by line
    lines = log_output.split('\n')
    current_asset = ""
    current_tf = ""
    for line in lines:
        if "Analizando " in line:
            m = re.search(r'Analizando (.*?) en (.*?) con', line)
            if m:
                current_asset = m.group(1)
                current_tf = m.group(2)
        elif " | TD Count: " in line:
            m = re.search(r'TD Count: ([-\d]+) \| RSI: ([^ ]+)', line)
            if m:
                if current_asset and current_tf:
                    metrics[f"{current_asset} {current_tf}"] = {
                        "td": int(m.group(1)),
                        "rsi": float(m.group(2))
                    }
                    
    for k, v in metrics.items():
        print(f"{k}: TD={v['td']} RSI={v['rsi']}")

except Exception as e:
    print("Error parsing logs:", e)
