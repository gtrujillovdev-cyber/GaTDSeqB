import json
import glob

assets = ["BTC", "ETH", "HYPE"]
tfs = ["5m", "15m", "1h", "4h", "1d"]

print("### 1. Estado de Rendimiento Global (Bankrolls)\n")
total_bank = 0

for a in assets:
    for tf in tfs:
        bank = 10000.0
        try:
            with open(f"trades_{a}_{tf}.json", 'r') as f:
                trades = json.load(f)
                bank += sum(t.get('pnl', 0.0) for t in trades)
        except:
            pass
        
        status = "IDLE"
        td_count = "N/A"
        try:
            with open(f"state_{a}_{tf}.json", 'r') as f:
                state = json.load(f)
                status = state.get('status', 'IDLE')
                if status != 'IDLE':
                    status = "IN TRADE"
                td_count = state.get('td_count', 'N/A')
        except:
            pass
            
        roi = ((bank - 10000) / 10000) * 100
        total_bank += bank
        
        # Only print if ROI is not 0 or status is IN TRADE
        if roi != 0 or status != 'IDLE':
            print(f"- **{a} [{tf}]**: ${bank:,.2f} ({roi:+.2f}%)")

print(f"\n**Global Equity**: ${total_bank:,.2f} ({(total_bank - 150000)/150000 * 100:+.2f}%)\n")
