import json, glob
import os

stats = []
for file in glob.glob("state_*.json"):
    try:
        with open(file, 'r') as f:
            data = json.load(f)
            stats.append({
                "bot": file.replace('state_', '').replace('.json', ''),
                "status": data.get("status"),
                "roi": ((data.get("bank", 10000) - 10000) / 10000) * 100,
                "win_rate": data.get("win_rate", 0),
                "td_count": data.get("td_count", 0)
            })
    except: pass

print("--- RENDIMIENTO ---")
for s in sorted(stats, key=lambda x: x["roi"], reverse=True):
    print(f"{s['bot'].upper():<10} | STATUS: {s['status']:<8} | ROI: {s['roi']:>5.2f}% | WIN RATE: {s['win_rate']:>5.1f}% | TD: {s['td_count']}")
