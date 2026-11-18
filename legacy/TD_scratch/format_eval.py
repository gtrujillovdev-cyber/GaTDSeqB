import json
import glob
import math

assets = ["BTC", "ETH", "HYPE"]
tfs = ["5m", "15m", "1h", "4h", "1d"]

print("### 1. Rendimiento Global (Bankrolls)\n")
total_bank = 0
for a in assets:
    for tf in tfs:
        fn = f"state_{a}_{tf}.json"
        try:
            with open(fn, 'r') as f:
                d = json.load(f)
                b = d.get('bank', 10000)
                status = d.get('status', 'IDLE')
                total_bank += b
                roi = ((b - 10000) / 10000) * 100
                if roi != 0 or status != 'IDLE':
                    print(f"- **{a} [{tf}]**: ${b:,.2f} ({roi:+.2f}%) | Estado: {status}")
        except:
            total_bank += 10000

print(f"\n**Global Equity Estimado**: ${total_bank:,.2f}\n")
