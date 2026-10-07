import os
import json
import subprocess
import urllib.request
import time
import threading
import psutil
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route('/')
def index(): return render_template('index.html')

@app.route('/lite')
def lite(): return render_template('lite.html')

MSTR_CACHE = {'price': 160.24, 'change': 0.0, 'time': 0}

def update_mstr_price_loop():
    global MSTR_CACHE
    while True:
        try:
            req = urllib.request.Request('https://query2.finance.yahoo.com/v8/finance/chart/MSTR', headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read())
                MSTR_CACHE['price'] = res_data['chart']['result'][0]['meta']['regularMarketPrice']
                MSTR_CACHE['prev_close'] = res_data['chart']['result'][0]['meta']['chartPreviousClose']
                MSTR_CACHE['change'] = MSTR_CACHE['price'] - MSTR_CACHE['prev_close']
                MSTR_CACHE['time'] = time.time()
        except:
            pass
        time.sleep(300)

threading.Thread(target=update_mstr_price_loop, daemon=True).start()

@app.route('/api/portfolio')
def api_portfolio():
    try:
        with open("portfolio.json", "r") as f:
            data = json.load(f)
        data['prices'] = {'MSTR': MSTR_CACHE['price']}
        data['changes'] = {'MSTR': MSTR_CACHE.get('change', 0.0)}
        return jsonify(data)
    except:
        return jsonify({"activos": {}, "prices": {}})

@app.route('/api/system')
def api_system():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f: temp = float(f.read()) / 1000.0
    except: temp = 0.0
    try:
        cpu = psutil.cpu_percent(interval=None)
    except: cpu = 0.0
    try:
        ram = psutil.virtual_memory().percent
    except: ram = 0.0
    return jsonify({"temp": round(temp, 1), "cpu": round(cpu, 1), "ram": round(ram, 1)})


TRADES_CACHE = {}

def get_fleet_data():
    fleet = {}
    INITIAL_BANK = 10000.0
    try:
        is_running = subprocess.call("pgrep -f 'bot.py' > /dev/null", shell=True) == 0
    except:
        is_running = False
        
    for asset in ['BTC', 'ETH', 'HYPE']:
        fleet[asset] = {}
        for tf in ['5m', '15m', '1h', '4h', '1d']:
            state_file = f"state_{asset}_{tf}.json"
            if os.path.exists(state_file):
                with open(state_file, "r") as f:
                    try: fleet[asset][tf] = json.load(f)
                    except: fleet[asset][tf] = {"status": "ERROR"}
            else:
                fleet[asset][tf] = {"status": "IDLE" if is_running else "OFFLINE"}
                
            trades_file = f"trades_{asset}_{tf}.json"
            fleet[asset][tf]['trades_count'] = 0
            fleet[asset][tf]['recent_trades'] = []
            fleet[asset][tf]['bank'] = INITIAL_BANK
            fleet[asset][tf]['win_rate'] = 0.0
            fleet[asset][tf]['drawdown'] = 0.0
            fleet[asset][tf]['profit_factor'] = 0.0
            
            cache_key = f"{asset}_{tf}"
            if os.path.exists(trades_file):
                try:
                    mtime = os.path.getmtime(trades_file)
                    if cache_key not in TRADES_CACHE or TRADES_CACHE[cache_key]['mtime'] != mtime:
                        with open(trades_file, "r") as f:
                            t = json.load(f)
                            recent = t[-5:]
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
                                    
                            win_rate = (wins / closed_trades * 100) if closed_trades > 0 else 0.0
                            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
                            TRADES_CACHE[cache_key] = {
                                'mtime': mtime, 'recent_trades': recent, 'trades_count': closed_trades,
                                'bank': current, 'win_rate': win_rate, 'profit_factor': profit_factor, 'drawdown': max_dd
                            }
                    c = TRADES_CACHE[cache_key]
                    fleet[asset][tf]['recent_trades'] = c['recent_trades']
                    fleet[asset][tf]['trades_count'] = c['trades_count']
                    fleet[asset][tf]['bank'] = c['bank']
                    fleet[asset][tf]['win_rate'] = c['win_rate']
                    fleet[asset][tf]['profit_factor'] = c['profit_factor']
                    fleet[asset][tf]['drawdown'] = c['drawdown']
                except: pass
    return fleet


@app.route('/api/fleet')
def api_fleet():
    return jsonify(get_fleet_data())



terminal_buffer = []

def log_tailer_loop():
    global terminal_buffer
    import subprocess
    log_file = "/home/raspberry/GaTDSEQ/bot_unified.log"
    if not os.path.exists(log_file): open(log_file, 'a').close()
    proc = subprocess.Popen(['tail', '-F', '-n', '8', log_file], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while True:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue
        try:
            line_str = line.decode('utf-8').strip()
            if line_str:
                terminal_buffer.append(line_str)
                if len(terminal_buffer) > 8:
                    terminal_buffer.pop(0)
                if clients > 0:
                    socketio.emit('terminal_log', {'msg': line_str})
        except:
            pass

threading.Thread(target=log_tailer_loop, daemon=True).start()

# --- WEBSOCKETS LOGIC ---

clients = 0

@socketio.on('connect')
def handle_connect():
    global clients
    clients += 1
    # Emit initial data on connect
    emit('fleet_update', get_fleet_data())
    for line in terminal_buffer:
        emit('terminal_log', {'msg': line})

@socketio.on('disconnect')
def handle_disconnect():
    global clients
    clients -= 1

def websocket_monitor_loop():
    last_mtimes = {}
    while True:
        if clients > 0:
            changed = False
            for asset in ['BTC', 'ETH', 'HYPE']:
                for tf in ['5m', '15m', '1h', '4h', '1d']:
                    state_file = f"state_{asset}_{tf}.json"
                    if os.path.exists(state_file):
                        m = os.path.getmtime(state_file)
                        if last_mtimes.get(state_file) != m:
                            last_mtimes[state_file] = m
                            changed = True
            
            if changed:
                socketio.emit('fleet_update', get_fleet_data())
        
        # Check every 0.5 seconds for true sub-second latency
        time.sleep(0.5)

threading.Thread(target=websocket_monitor_loop, daemon=True).start()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001)
