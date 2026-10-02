import os
import json
import subprocess
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def index(): return render_template('index.html')

@app.route('/lite')
def lite(): return render_template('lite.html')

@app.route('/api/system')
def api_system():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f: temp = float(f.read()) / 1000.0
    except: temp = 0.0
    try:
        cpu = float(subprocess.check_output("vmstat 1 2 | tail -1 | awk '{print 100-$15}'", shell=True).decode('utf-8').strip())
    except: cpu = 0.0
    try:
        ram = float(subprocess.check_output("free -m | awk 'NR==2{printf \"%.1f\", $3*100/$2 }'", shell=True).decode('utf-8').strip())
    except: ram = 0.0
    return jsonify({"temp": round(temp, 1), "cpu": round(cpu, 1), "ram": round(ram, 1)})

@app.route('/api/fleet')
def api_fleet():
    fleet = {}
    INITIAL_BANK = 10000.0
    
    try:
        is_running = subprocess.call("pgrep -f 'bot.py' > /dev/null", shell=True) == 0
    except:
        is_running = False
        
    for tf in ['5m', '15m', '1h', '4h', '1d']:
        state_file = f"state_{tf}.json"

        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                try: fleet[tf] = json.load(f)
                except: fleet[tf] = {"status": "ERROR"}
        else:
            fleet[tf] = {"status": "IDLE" if is_running else "OFFLINE"}
            
        trades_file = f"trades_{tf}.json"
        fleet[tf]['trades_count'] = 0
        fleet[tf]['recent_trades'] = []
        fleet[tf]['bank'] = INITIAL_BANK
        fleet[tf]['win_rate'] = 0.0
        fleet[tf]['drawdown'] = 0.0
        fleet[tf]['profit_factor'] = 0.0
        
        if os.path.exists(trades_file):
            with open(trades_file, "r") as f:
                try: 
                    t = json.load(f)
                    fleet[tf]['recent_trades'] = t[-5:]
                    
                    wins = 0
                    closed_trades = 0
                    peak = INITIAL_BANK
                    current = INITIAL_BANK
                    max_dd = 0.0
                    
                    gross_profit = 0.0
                    gross_loss = 0.0
                    
                    for trade in t:
                        if 'pnl' in trade:
                            closed_trades += 1
                            pnl = float(trade['pnl'])
                            if pnl > 0: 
                                wins += 1
                                gross_profit += pnl
                            else:
                                gross_loss += abs(pnl)
                            
                            current += pnl
                            if current > peak: peak = current
                            dd = ((peak - current) / peak) * 100
                            if dd > max_dd: max_dd = dd
                            
                    fleet[tf]['trades_count'] = closed_trades
                    fleet[tf]['bank'] = current
                    fleet[tf]['win_rate'] = (wins / closed_trades * 100) if closed_trades > 0 else 0.0
                    fleet[tf]['profit_factor'] = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
                    fleet[tf]['drawdown'] = max_dd
                except: pass
    return jsonify(fleet)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
