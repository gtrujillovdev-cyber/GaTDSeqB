from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import json
import os
import subprocess
import backtest

app = Flask(__name__)
CORS(app)

STATE_FILE = "state.json"
TRADES_FILE = "trades.json"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/lite')
def lite():
    return render_template('lite.html')

@app.route('/api/state')
def api_state():
    state = {"status": "IDLE"}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            try: state = json.load(f)
            except: pass
    return jsonify(state)

@app.route('/api/trades')
def api_trades():
    trades = []
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "r") as f:
            try: trades = json.load(f)
            except: pass
    return jsonify(trades)

@app.route('/api/system')
def api_system():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read()) / 1000.0
    except: temp = 0.0

    try:
        cpu_cmd = "vmstat 1 2 | tail -1 | awk '{print 100-$15}'"
        cpu_out = subprocess.check_output(cpu_cmd, shell=True).decode('utf-8').strip()
        cpu = float(cpu_out)
    except: cpu = 0.0

    try:
        ram_cmd = "free -m | awk 'NR==2{printf \"%.1f\", $3*100/$2 }'"
        ram_out = subprocess.check_output(ram_cmd, shell=True).decode('utf-8').strip()
        ram = float(ram_out)
    except: ram = 0.0
        
    return jsonify({"temp": round(temp, 1), "cpu": round(cpu, 1), "ram": round(ram, 1)})

@app.route('/api/backtest', methods=['POST'])
def api_backtest():
    data = request.json
    tf = data.get('timeframe', '1d')
    risk = data.get('risk', 50) / 100.0
    results = backtest.run_simulation(tf, risk)
    return jsonify(results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
