# 🏛️ GaTDSEQ: Institutional Edge-Trading Kiosk & Multi-Agent Quantitative Engine

[![System Status](https://img.shields.io/badge/Production-Raspberry%20Pi%203B%20ARMv7-00ff66?style=flat-square&logo=raspberrypi&logoColor=black)](https://github.com/gtrujillovdev-cyber/GaTDSeqB)
[![Architecture](https://img.shields.io/badge/Engine-27%20Virtual%20Bots%20(A%2FB%2FC)-ffb000?style=flat-square)](https://github.com/gtrujillovdev-cyber/GaTDSeqB)
[![Frontend UI](https://img.shields.io/badge/Interface-Bloomberg%20Terminal%2021:9-ffb000?style=flat-square)](https://github.com/gtrujillovdev-cyber/GaTDSeqB)
[![License](https://img.shields.io/badge/License-Proprietary-red?style=flat-square)](https://github.com/gtrujillovdev-cyber/GaTDSeqB)

**GaTDSEQ** is an autonomous, swing quantitative trading engine and real-time execution kiosk designed from the ground up for low-power ARM Edge hardware (Raspberry Pi 3B, 1GB RAM). Operating on perpetual crypto markets (BTC, ETH, HYPE), the system runs an automated multivariate **A/B/C testing matrix across 27 concurrent algorithmic bots**, orchestrating DeMark Sequential, Wyckoff volume analysis, Top-Down Weekly Macro Confluence, dynamic risk management shields, and a zero-latency Bloomberg-style monitoring console.

---

## 📑 Table of Contents
1. [Architectural Overview](#-architectural-overview)
2. [Quantitative Strategy Matrix (A/B/C Framework)](#-quantitative-strategy-matrix-abc-framework)
3. [Execution & Dynamic Risk Engine](#-execution--dynamic-risk-engine)
4. [UltraGear 21:9 Bloomberg Kiosk UI](#-ultragear-219-bloomberg-kiosk-ui)
5. [Hardware Hardening & ARM Edge Optimization](#-hardware-hardening--arm-edge-optimization)
6. [TradingView Pine Script v5 Indicator](#-tradingview-pine-script-v5-indicator)
7. [Repository Structure](#-repository-structure)
8. [Installation & Deployment](#-installation--deployment)
9. [Telemetry & Operational Verification](#-telemetry--operational-verification)
10. [Distributed Infrastructure & SecOps Manual (Tailscale Mesh)](manual_infraestructura.md)

---

## 🏛️ Architectural Overview

```
                      ┌──────────────────────────────────────────────┐
                      │          BINANCE FUTURES API (CCXT)          │
                      └──────────────────────┬───────────────────────┘
                                             │ OHLCV / Live Tickers
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │          QUANTITATIVE ENGINE (bot.py)        │
                      │  - 27 Algorithmic Bots Concurrently Evaluated │
                      │  - Top-Down 1W Weekly Macro Confluence Gate   │
                      │  - Precision DeMark TD Sequential (9 / 13)   │
                      │  - Wyckoff Phase Detection & Volume Spikes   │
                      │  - Wilders Smoothing RSI & Dynamic Floor ATR │
                      └──────────────┬───────────────────────────────┘
                                     │ Atomic Replace (.tmp -> .json)
                                     │ Dirty-Check Flash Wear Shield
                                     ▼
                      ┌──────────────────────────────────────────────┐
                      │        EDGE LOCAL STORAGE (Raspberry Pi)     │
                      │       state_*.json  /  trades_unified.json   │
                      └──────────────┬───────────────────────────────┘
                                     │ inotify / mtime Polling Tunnel
                                     ▼
                      ┌──────────────────────────────────────────────┐
                      │         TELEMETRY SERVER (server.py)         │
                      │  - Flask + Eventlet + Flask-SocketIO (WS)    │
                      │  - psutil Zero-Spawn Hardware Metrics Engine │
                      │  - /api/ticker Financial Tape Streaming      │
                      └──────────────┬───────────────────────────────┘
                                     │ WebSockets (Zero-Polling)
                                     ▼
                      ┌──────────────────────────────────────────────┐
                      │     LG ULTRAGEAR 21:9 MONITORING KIOSK       │
                      │  - Strict Bloomberg Amber/Mono Aesthetic     │
                      │  - Client-Side Visual P&L / Trailing Ranges  │
                      │  - A/B/C Comparative Alpha Leaderboard       │
                      │  - Top-Down 1W Situational Awareness Badges  │
                      └──────────────────────────────────────────────┘
```

The system operates strictly as a decoupled **two-tier architecture**:
1. **The Quantitative Engine (`bot.py`)**: Responsible solely for market data acquisition, mathematical indicator calculations, algorithmic state progression, and order executions. Writes persistent state files atomically.
2. **The Telemetry Server (`server.py`)**: Hooks into the filesystem changes, broadcasting structured delta events over WebSockets (`Flask-SocketIO` + `Eventlet`) to connected Bloomberg Kiosk frontends without locking the database or eating CPU cycles.

---

## 🔬 Quantitative Strategy Matrix (A/B/C Framework)

GaTDSEQ trades across 3 primary assets (**BTC**, **ETH**, **HYPE**) over 3 macro timeframes (**4h**, **1d**, **1w**), yielding 9 core trading lanes. Each lane is cloned into an **A/B/C strategy archetype**, resulting in **27 concurrent virtual bots** forward-testing different mathematical hypotheses simultaneously:

| Archetype | Identifier | Core Quantitative Thesis | Filter Mechanism |
| :--- | :--- | :--- | :--- |
| **A: TD9 Pure** | `[ASSET]_TD9_[TF]` | Pure DeMark TD Sequential Setup 9 and Countdown 13 reversal system. | RSI Overbought/Oversold filters (Wilder's RMA smoothing). |
| **B: Wyckoff Core** | `[ASSET]_WYK_[TF]` | Volume Spread Analysis (VSA) identifying Institutional Accumulation / Distribution. | Upthrust After Distribution (UTAD), Spring patterns, and 2.0x Volume spikes. |
| **C: Hybrid Vanguard** | `[ASSET]_HYB_[TF]` | Dual-confluence institutional entry requiring both TD exhaustion and Wyckoff volume confirmation. | Strict logical AND filter: TD9 trigger + Wyckoff Phase conformation. |

### Capital Allocation & Margin Rules
- **Isolated Portfolio Model:** Each bot operates with a dedicated virtual equity tranche (\$10,000 USD base), preventing cross-contamination of performance metrics.
- **Dynamic Risk Sizing:** Allocation expands on macro timeframes (1W: 3.0x base risk, 1D: 2.5x base risk) where signal-to-noise ratio is maximized, maintaining controlled exposure on swing entries (4h: 1.5x base risk).

---

## 🛡️ Execution & Dynamic Risk Engine

The execution layer implements defensive risk mechanics engineered to preserve capital in volatile crypto derivatives environments:

```
 Entry Price
     │
     ├───────────────────► [+1.0 ATR]  BREAK EVEN SHIELD & SCALE-OUT (50%)
     │                                 Stop Loss moved to Entry Price (Zero Risk).
     │                                 50% of position size closed at market. Locks realized alpha.
     │                                 Monotonic Trailing Stop Loss latches onto remaining 50%.
     │
     └───────────────────► [Take Profit Level] 100% POSITION CLOSED
```

### Key Risk & Funnel Modules
- **Multi-Stage Funnel Filter (Confidence Gate):** All prospective signals must pass a 4-dimensional conviction vector (DeMark Setup Purity, RSI Extreme/Divergence, Institutional Volume vs SMA20, and Macro EMA200 Trend). Signals with $S < 0.55$ are automatically skipped (`SKIP`), dodging low-conviction noise trades.
- **1.0 ATR Break Even Shield:** Once unrealized profit reaches Average True Range ($+1.0\times\text{ATR}$), the Stop Loss is automatically repositioned to the exact entry price. Calibrated to eradicate the "Choke Effect" of premature 0.5 ATR triggers.
- **1.0 ATR Symmetric Scale-Out:** When favorable momentum hits $+1.0\times\text{ATR}$, 50% of the active position is closed immediately at market price. Realized profit is locked, and the trade card is badged with `[💰 50% SCALED]`.
- **Dynamic Floor ATR:** To prevent Stop Loss collapse during prolonged low-volatility consolidations, a floor clamp ($ATR_{\text{min}} = \max(ATR, 0.006 \times Price)$) prevents premature stop-outs during noise sweeps.
- **TD-13 DCA & Exhaustion Battalion:** If an active trade faces extended counter-momentum that reaches a DeMark Countdown 13, the system initiates a calculated dollar-cost average tranche to lower average entry price before mean reversion.

---

## 🖥️ UltraGear 21:9 Bloomberg Kiosk UI

Built strictly adhering to the **Bloomberg Terminal Aesthetic** (Black `#000000`, Amber `#ffb000`, Bright Green `#00ff66`, Pure Red `#ff3333`, Monospace font, and 0px border radius):

- **Zero-Scroll Multi-Asset Grid:** The entire 27-bot fleet is grouped into 3 vertical macro-columns (`BTC`, `ETH`, `HYPE`), subdivided into horizontal `[WYK | HYB | TD9]` rows per timeframe (`4h`, `1d`, `1w`), fitting cleanly on 1080p and 1440p ultrawide displays with enhanced visual breathing room.
- **Real-Time Client-Side Math:** All trailing distance calculations, unrealized P&L in USD and ROE (%), and progress range bars are computed on the client's V8 engine using pure Vanilla JavaScript, maintaining 0% CPU consumption on the Raspberry Pi server.
- **A/B/C Comparative Leaderboard:** Displays real-time aggregate performance, realized P&L, Win Rate, and trade frequency comparison between TD9, Wyckoff, and Hybrid strategies.
- **Institutional Order Ledger:** Live telemetry table streaming entries, `[PRT]` partial scale-outs, and `[CLS]` position closes.

---

## ⚡ Hardware Hardening & ARM Edge Optimization

Designed to run indefinitely on a **Raspberry Pi 3B (ARMv7, 1GB RAM)**:

1. **Atomic State Persistence:** All JSON writes utilize temporary file staging (`state_*.json.tmp`) followed by atomic POSIX renames (`os.replace`). This guarantees zero state corruption during sudden power losses or concurrent reads by `server.py`.
2. **Dirty-Check Flash Wear Shield:** State files are only overwritten if memory state attributes have actually changed since the previous iteration, reducing MicroSD card write amplification by over 80%.
3. **Zero-Spawn Hardware Telemetry:** Server telemetry fetches CPU, memory, and temperature metrics directly using native C-bindings via `psutil`, completely eliminating Linux shell subprocess spawning (`vcgencmd`, `cat /proc/meminfo`).
4. **Pandas Memory Guard:** Periodic garbage collection passes (`gc.collect()`) inside the multi-asset execution loop prevent memory fragmentation, maintaining memory consumption under 250 MB total.

---

## 📈 TradingView Pine Script v5 Indicator

To verify and visually backtest the signals directly on TradingView charts, the matching algorithmic engine is available in `pinescript/gatdseq_core.pine`:
- **Complete DeMark Engine:** Setup 9 with institutional bar colorations, Countdown 13 exhaustion, and Price Flip validation.
- **Wilder's RMA Smoothing:** Exact mathematical parity with Python's Pandas indicator pipeline.
- **Visual Alert Overlays:** Displays Break Even threshold indicators and ATR expansion channels.

---

## 📂 Repository Structure

```
GaTDSEQ/
├── bot.py                  # Quantitative engine: 27-bot A/B/C matrix, Funnel Gate, CCXT data acquisition
├── server.py               # Telemetry server: Flask-SocketIO, Eventlet, WebSockets, psutil metrics
├── run_backtest.py         # Institutional backtesting CLI (Terminal Bloomberg reports)
├── backtesting/            # High-performance local backtesting suite for Mac (Parquet, event-driven)
│   ├── data_manager.py     # Paged CCXT fetcher & local Parquet caching
│   ├── indicators.py       # Vectorized Wilder's RMA indicators & Volume Profile
│   ├── engine.py           # Bar-by-bar simulation engine with fees & dynamic leverage
│   ├── analytics.py        # Financial metrics (Sharpe, Sortino, MaxDD, Profit Factor)
│   └── optimizer.py        # Multi-parameter Grid Search engine
├── docs/
│   └── RESEARCH_FUNNEL_ARCHITECTURE.md # Quantitative whitepaper on Multi-Stage Funnel Design
├── templates/
│   └── lite.html           # Institutional Bloomberg Kiosk UI (UltraGear 21:9 zero-scroll dashboard)
├── pinescript/
│   └── gatdseq_core.pine   # TradingView Pine Script v5 official indicator
├── auto_clean.sh           # Hardware maintenance cron script (cache drops, RAM defragmentation)
├── requirements.txt        # Python dependency manifest
├── manual_infraestructura.md # Distributed architecture manual (Tailscale Mesh, Edge-Worker hybrid, SecOps)
├── scripts/                # Self-healing maintenance suite & LaunchDaemons for Mac Worker
│   ├── worker_maintenance.sh # Self-healing RAM purge, cache sweep, and telemetry daemon
│   ├── com.gatdseq.maintenance.plist # Scheduled daily maintenance LaunchDaemon (04:30 AM)
│   ├── com.gatdseq.caffeinate.plist  # Root LaunchDaemon anti-sleep clamshell persistence
│   └── install_worker_maintenance.sh # One-click installer for macOS worker nodes
├── GEMINI.md               # Project development rules, conventions, and operational macro protocols
├── DIARIO_DE_DESARROLLO.md # Chronological technical development diary
└── README.md               # Institutional documentation (this file)
```

---

## 🚀 Installation & Deployment

### 1. Prerequisites
- Python 3.11+
- Virtual environment (`venv`)
- Git

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/gtrujillovdev-cyber/GaTDSeqB.git
cd GaTDSeqB

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install required dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Execution (Production Services via Systemd)
The production deployment on Edge devices runs under `systemd` daemon management:

```bash
# Start WebSockets Telemetry Server (Port 5001)
python3 server.py

# Start Quantitative Bot Engine
python3 bot.py
```

Access the Bloomberg Kiosk in your browser at:
```
http://<EDGE_DEVICE_IP>:5001/lite
```

---

## 📊 Telemetry & Operational Verification

Live production telemetry snapshot from the Raspberry Pi 3B edge node:
- **System Uptime:** `3 days, 11 hours+ continuous execution`
- **Total Portfolio Equity:** `$289,005.57 USD`
- **Accumulated Realized P&L:** `+$19,005.57 USD (+7.04% ROI)`
- **Core Strategy Alpha Leader:** `HYPE_WYK_4h` (`+$8,057.19 USD`), `HYPE_HYB_4h` (`+$8,006.08 USD`)
- **Active Hedging Mechanics:** 100% operational Break Even Shields & 1.0 ATR Partial Closures.

---

## ⚖️ License & Disclaimer

*This software is developed strictly for educational and quantitative research purposes. Algorithmic trading and cryptocurrency derivatives involve substantial financial risk. Past performance does not guarantee future results.*
