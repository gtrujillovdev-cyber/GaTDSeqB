import gc
import json
import os
import threading
import time
import urllib.request

import psutil
import requests
from flask import Flask, jsonify, make_response, redirect, render_template, request, url_for
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from core.strategy import FLEET_ASSETS, FLEET_STRATEGIES, FLEET_TIMEFRAMES
from core.telemetry import aggregate_trade_ledger

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_FILE = os.getenv("GATDSEQ_LOG_FILE", os.path.join(BASE_DIR, "bot_unified.log"))

TICKER_CACHE = {
    "BTC": [0, 0],
    "ETH": [0, 0],
    "HYPE": [0, 0],
    "SP500": [0, 0],
    "NASDAQ": [0, 0],
    "DXY": [0, 0],
    "VIX": [0, 0],
    "BTCD": [0, 0],
}
MSTR_CACHE = {"price": 160.24, "change": 0.0, "time": 0}
TRADES_CACHE = {}
_BOT_STATUS_CACHE = {"checked": 0.0, "running": False}
_FNG_SERVER_CACHE = {"val": 68, "classification": "GREED", "time": 0.0}
terminal_buffer = []
clients = 0
_THREADS_STARTED = False

_cors_env = os.getenv("GATDSEQ_CORS_ORIGINS", "")
_allowed_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else None

app = Flask(__name__)
if _allowed_origins:
    CORS(app, resources={r"/api/*": {"origins": _allowed_origins}})
    socketio = SocketIO(app, cors_allowed_origins=_allowed_origins)
else:
    CORS(app)
    socketio = SocketIO(app, cors_allowed_origins=[])


def ticker_fetch_loop():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    session = requests.Session()
    session.headers.update(headers)
    last_coingecko_fetch = 0.0

    while True:
        try:
            r = session.get(
                "https://api.binance.com/api/v3/ticker/24hr?symbols=%5B%22BTCUSDT%22,%22ETHUSDT%22,%22HYPEUSDT%22%5D",
                timeout=6,
            )
            if r.status_code == 200:
                for d in r.json():
                    sym = d["symbol"].replace("USDT", "")
                    TICKER_CACHE[sym] = [float(d["lastPrice"]), float(d["priceChangePercent"])]

            for ticker, sym in [("^GSPC", "SP500"), ("^IXIC", "NASDAQ"), ("DX-Y.NYB", "DXY"), ("^VIX", "VIX")]:
                try:
                    r = session.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}", timeout=5)
                    if r.status_code == 200:
                        data = r.json()["chart"]["result"][0]["meta"]
                        price = data["regularMarketPrice"]
                        prev = data.get("chartPreviousClose", price)
                        pct = ((price - prev) / prev) * 100 if prev else 0
                        TICKER_CACHE[sym] = [price, pct]
                except Exception:
                    pass

            now_ts = time.time()
            if now_ts - last_coingecko_fetch > 300:
                try:
                    r_cg = session.get("https://api.coingecko.com/api/v3/global", timeout=6)
                    if r_cg.status_code == 200:
                        cg_data = r_cg.json().get("data", {})
                        btc_dom = cg_data.get("market_cap_percentage", {}).get("btc", 0.0)
                        if btc_dom > 0:
                            TICKER_CACHE["BTCD"] = [btc_dom, 0.0]
                            last_coingecko_fetch = now_ts
                except Exception:
                    pass
        except Exception as e:
            print(f"Error fetching ticker: {e}")

        time.sleep(30)


def update_mstr_price_loop():
    while True:
        try:
            req = urllib.request.Request(
                "https://query2.finance.yahoo.com/v8/finance/chart/MSTR",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read())
                MSTR_CACHE["price"] = res_data["chart"]["result"][0]["meta"]["regularMarketPrice"]
                MSTR_CACHE["prev_close"] = res_data["chart"]["result"][0]["meta"]["chartPreviousClose"]
                MSTR_CACHE["change"] = MSTR_CACHE["price"] - MSTR_CACHE["prev_close"]
                MSTR_CACHE["time"] = time.time()
        except Exception:
            pass
        time.sleep(300)


@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "-1"
    return response


@app.route("/")
def index():
    return redirect(url_for("lite"))


@app.route("/lite")
def lite():
    response = make_response(render_template("lite.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "-1"
    response.headers["Clear-Site-Data"] = '"cache"'
    return response


@app.route("/api/portfolio")
def api_portfolio():
    try:
        with open(os.path.join(BASE_DIR, "portfolio.json"), "r") as f:
            data = json.load(f)
        data["prices"] = {"MSTR": MSTR_CACHE["price"]}
        data["changes"] = {"MSTR": MSTR_CACHE.get("change", 0.0)}
        return jsonify(data)
    except Exception:
        return jsonify({"activos": {}, "prices": {}})


@app.route("/api/system")
def api_system():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read()) / 1000.0
    except Exception:
        temp = 0.0
    try:
        cpu = psutil.cpu_percent(interval=None)
    except Exception:
        cpu = 0.0
    try:
        ram = psutil.virtual_memory().percent
    except Exception:
        ram = 0.0
    return jsonify({"temp": round(temp, 1), "cpu": round(cpu, 1), "ram": round(ram, 1)})


def is_bot_active(base_dir: str = BASE_DIR) -> bool:
    now = time.time()
    if now - _BOT_STATUS_CACHE["checked"] < 10:
        return _BOT_STATUS_CACHE["running"]
    _BOT_STATUS_CACHE["checked"] = now
    try:
        log_path = DEFAULT_LOG_FILE if os.path.exists(DEFAULT_LOG_FILE) else os.path.join(base_dir, "bot_unified.log")
        if os.path.exists(log_path) and (now - os.path.getmtime(log_path) < 480):
            _BOT_STATUS_CACHE["running"] = True
            return True
        for proc in psutil.process_iter(["name", "cmdline"]):
            cmdline = proc.info.get("cmdline") or []
            if any("bot.py" in str(part) for part in cmdline):
                _BOT_STATUS_CACHE["running"] = True
                return True
        _BOT_STATUS_CACHE["running"] = False
        return False
    except Exception:
        return _BOT_STATUS_CACHE["running"]


def _aggregate_trade_ledger(trades_list: list, initial_bank: float = 10000.0) -> dict:
    return aggregate_trade_ledger(trades_list, initial_bank=initial_bank)


def get_fleet_data(base_dir: str = ".") -> dict:
    fleet = {}
    INITIAL_BANK = 10000.0
    is_running = is_bot_active(base_dir=base_dir)
    bot_names = [f"{sym}_{strat}" for sym in FLEET_ASSETS for strat in FLEET_STRATEGIES]

    for asset in bot_names:
        fleet[asset] = {}
        for tf in FLEET_TIMEFRAMES:
            state_file = os.path.join(base_dir, f"state_{asset}_{tf}.json")
            if os.path.exists(state_file):
                with open(state_file, "r") as f:
                    try:
                        fleet[asset][tf] = json.load(f)
                    except Exception:
                        fleet[asset][tf] = {"status": "ERROR"}
            else:
                fleet[asset][tf] = {"status": "IDLE" if is_running else "OFFLINE"}

            fleet[asset][tf].update(
                {
                    "trades_count": 0,
                    "wins_count": 0,
                    "recent_trades": [],
                    "bank": INITIAL_BANK,
                    "win_rate": 0.0,
                    "drawdown": 0.0,
                    "profit_factor": 0.0,
                }
            )

            trades_file = os.path.join(base_dir, f"trades_{asset}_{tf}.json")
            cache_key = f"{os.path.abspath(base_dir)}::{asset}_{tf}"
            if os.path.exists(trades_file):
                try:
                    mtime = os.path.getmtime(trades_file)
                    if cache_key not in TRADES_CACHE or TRADES_CACHE[cache_key]["mtime"] != mtime:
                        with open(trades_file, "r") as f:
                            t = json.load(f)
                        agg = _aggregate_trade_ledger(t, initial_bank=INITIAL_BANK)
                        agg["mtime"] = mtime
                        TRADES_CACHE[cache_key] = agg

                    c = TRADES_CACHE[cache_key]
                    fleet[asset][tf]["recent_trades"] = c["recent_trades"]
                    fleet[asset][tf]["trades_count"] = c["trades_count"]
                    fleet[asset][tf]["wins_count"] = c["wins_count"]
                    fleet[asset][tf]["bank"] = c["bank"]
                    fleet[asset][tf]["win_rate"] = c["win_rate"]
                    fleet[asset][tf]["profit_factor"] = c["profit_factor"]
                    fleet[asset][tf]["drawdown"] = c["drawdown"]
                except Exception:
                    pass
    return fleet


@app.route("/api/fleet")
def api_fleet():
    return jsonify(get_fleet_data(base_dir=BASE_DIR))


@app.route("/api/ticker")
def api_ticker():
    return jsonify(TICKER_CACHE)


@app.route("/api/fng")
def api_fng():
    global _FNG_SERVER_CACHE
    now = time.time()
    if now - _FNG_SERVER_CACHE["time"] > 1800:
        try:
            r = requests.get(
                "https://api.alternative.me/fng/?limit=1",
                headers={"User-Agent": "GaTDSEQ/2.6"},
                timeout=4,
            )
            if r.status_code == 200:
                d = r.json()
                _FNG_SERVER_CACHE = {
                    "val": int(d["data"][0]["value"]),
                    "classification": d["data"][0]["value_classification"].upper(),
                    "time": now,
                }
        except Exception:
            pass
    return jsonify(_FNG_SERVER_CACHE)


def log_tailer_loop():
    global terminal_buffer
    log_file = DEFAULT_LOG_FILE
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    if not os.path.exists(log_file):
        open(log_file, "a").close()

    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
            terminal_buffer = [line.strip() for line in lines[-8:] if line.strip()]
    except Exception:
        pass

    last_log_time = time.time()
    with open(log_file, "r") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if line:
                try:
                    line_str = line.strip()
                    if line_str:
                        terminal_buffer.append(line_str)
                        if len(terminal_buffer) > 8:
                            terminal_buffer.pop(0)
                        if clients > 0:
                            socketio.emit("terminal_log", {"msg": line_str})
                        last_log_time = time.time()
                except Exception:
                    pass
            else:
                now = time.time()
                if now - last_log_time > 15:
                    sleep_sec = 300 - (int(now) % 300)
                    hb_msg = f"AWAITING NEXT CANDLE CLOSE... T-MINUS {sleep_sec} SECONDS"
                    if clients > 0:
                        socketio.emit("terminal_log", {"msg": hb_msg})
                    last_log_time = now
                time.sleep(0.5)


@socketio.on("connect")
def handle_connect():
    global clients
    clients += 1
    emit("fleet_update", get_fleet_data(base_dir=BASE_DIR))
    for line in terminal_buffer:
        emit("terminal_log", {"msg": line})


@socketio.on("disconnect")
def handle_disconnect():
    global clients
    clients = max(0, clients - 1)


@app.route("/api/reload", methods=["POST", "GET"])
def api_force_reload():
    admin_token = os.getenv("GATDSEQ_ADMIN_TOKEN")
    if admin_token:
        provided = request.headers.get("X-Admin-Token") or request.args.get("token")
        if provided != admin_token:
            return jsonify({"error": "unauthorized"}), 401
    socketio.emit("force_reload", {})
    return jsonify({"status": "broadcasted force_reload to all clients"})


def websocket_monitor_loop():
    last_mtimes = {}
    loop_count = 0
    last_broadcast_time = 0.0
    bot_names = [f"{sym}_{strat}" for sym in FLEET_ASSETS for strat in FLEET_STRATEGIES]
    while True:
        now_ts = time.time()
        changed = False
        for asset in bot_names:
            for tf in FLEET_TIMEFRAMES:
                state_file = os.path.join(BASE_DIR, f"state_{asset}_{tf}.json")
                if os.path.exists(state_file):
                    m = os.path.getmtime(state_file)
                    if last_mtimes.get(state_file) != m:
                        last_mtimes[state_file] = m
                        changed = True

        if changed or (now_ts - last_broadcast_time > 10):
            try:
                socketio.emit("fleet_update", get_fleet_data(base_dir=BASE_DIR))
            except Exception:
                pass
            last_broadcast_time = now_ts

        loop_count += 1
        if loop_count % 300 == 0:
            gc.collect()

        time.sleep(1.2)


def start_background_tasks():
    global _THREADS_STARTED
    if _THREADS_STARTED:
        return
    _THREADS_STARTED = True
    threading.Thread(target=ticker_fetch_loop, daemon=True).start()
    threading.Thread(target=update_mstr_price_loop, daemon=True).start()
    threading.Thread(target=log_tailer_loop, daemon=True).start()
    threading.Thread(target=websocket_monitor_loop, daemon=True).start()


if __name__ == "__main__":
    start_background_tasks()
    socketio.run(app, host="0.0.0.0", port=5001)
