# GaTDSEQ: Institutional Edge-Trading Kiosk

GaTDSEQ is a fully automated quantitative trading engine and real-time monitoring kiosk built natively for ARM Edge devices (Raspberry Pi). Originally designed as a Shadow-Trading (paper-trading) monitor, the system has evolved into a highly optimized, Multi-Asset algorithmic engine.

## 🚀 Key Features

*   **Multi-Asset Intelligence:** Concurrently monitors and trades **BTC, ETH, and HYPE** across 5 timeframes (5m, 15m, 1h, 4h, 1d) amounting to 15 concurrent algorithmic states.
*   **Zero-Latency WebSockets:** The frontend Dashboard receives sub-second updates using `Flask-SocketIO` and `Eventlet` instead of traditional HTTP polling, providing a true institutional terminal experience.
*   **Dual-Mode Trading:** 
    *   *Trend-Following:* Seeks massive TP (Take Profit) setups aligned with the EMA200.
    *   *Counter-Trend Scalping:* Halves risk exposure and tightens SL/TP when trading against the macro trend, specifically targeting 1-to-4 candle pullbacks identified by TD Sequential.
*   **Visual Trailing Progress:** The frontend mathematically simulates and renders live visual progress bars, showing the precise distance between the asset's current price and the active SL/TP bounds at zero CPU cost.
*   **Dynamic Risk Matrix:** Capital allocation adapts automatically based on the Timeframe (higher TF = higher risk) and RSI Conviction levels.
*   **Memory & CPU Hardening:**
    *   Hardware telemetry migrated to native Python `psutil`, cutting server process spawns by 95% and cooling the edge device.
    *   Automated memory purging via Cron (`auto_clean.sh`) preventing Pandas memory leaks.
    *   Aggressive `gc.collect()` within the multi-asset loop to maintain <250MB RAM footprint.

## 🏗 System Architecture

1.  **Quantitative Engine (`bot.py`):** Runs on an endless loop, fetching OHLCV data from Binance via `ccxt`. It executes the TD Sequential, EMA200, RSI, and ATR calculations precisely synced with TradingView's RMA smoothing algorithms.
2.  **WebSocket Tunnel (`server.py`):** A lightweight `Flask` server that hooks into filesystem `mtime` modifications of the JSON state files, streaming immediate push notifications to connected web clients.
3.  **Kiosk Interface (`templates/lite.html`):** A responsive, dark-mode terminal view built purely in HTML/CSS/JS. Idle bots collapse dynamically to save screen space, while active trades expand to reveal real-time trailing data and Live Portfolio Net Worth integrations.
4.  **Hardware Guard (`auto_clean.sh`):** A daily Cron script that flushes OS caches and gracefully restarts daemon processes to protect 1GB RAM edge devices from memory fragmentation.

## 🛠 Tech Stack
- **Backend:** Python 3.11+, Flask, Eventlet, SocketIO, CCXT, Pandas, Psutil
- **Frontend:** Vanilla JavaScript, CSS Flexbox
- **Infrastructure:** Systemd Daemons, Tailscale (Zero-Trust Mesh), SSH, Bash

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- `pip install -r requirements.txt` (including `ccxt`, `pandas`, `flask`, `flask-socketio`, `eventlet`, `psutil`)

### Running the Engine
```bash
# 1. Start the WebSocket Server (Port 5001)
python3 server.py

# 2. Start the Quantitative Bot
python3 bot.py
```

### Accessing the Kiosk
Open your browser and navigate to `http://localhost:5001/lite` to access the real-time terminal.

---

*This project is designed as a technical portfolio piece demonstrating systems integration, edge computing, and backend development.*
