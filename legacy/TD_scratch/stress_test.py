import json
import glob
import os
import shutil

# Backup existing states
os.makedirs("backup_states", exist_ok=True)
for f in glob.glob("state_*.json"):
    shutil.copy(f, f"backup_states/{f}")

# Generate dummy IN_TRADE state
dummy_state = {
    "status": "IN_TRADE",
    "td_count": -9,
    "position": "BUY",
    "entry_price": 50000.0,
    "stop_loss": 49000.0,
    "take_profit": 52000.0,
    "size_usd": 500.0,
    "size_btc": 0.01,
    "risk_usd": 25.0,
    "leverage": 5.0,
    "bank": 10050.0,
    "win_rate": 55.5,
    "drawdown": -2.3
}

# Overwrite all 15 files
assets = ['BTC', 'ETH', 'HYPE']
tfs = ['5m', '15m', '1h', '4h', '1d']
for asset in assets:
    for tf in tfs:
        with open(f"state_{asset}_{tf}.json", "w") as f:
            json.dump(dummy_state, f)

print("Stress test applied. All 15 bots are IN_TRADE.")
