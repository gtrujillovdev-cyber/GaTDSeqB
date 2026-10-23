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
10. [Distributed Infrastructure & SecOps Manual (Tailscale Mesh)](docs/manual_infraestructura.md)

---

## 🏛️ Architectural Overview

```
                      ┌──────────────────────────────────────────────┐
                      │          BINANCE FUTURES API (CCXT)          │
                      └──────────────────────┬───────────────────────┘
                                             │ OHLCV / Live Tickers
                         ┌───────────────────┴───────────────────┐
                         ▼                                       ▼
        ┌─────────────────────────────────┐    ┌─────────────────────────────────┐
        │  COMPUTE WORKER (MacBook Pro)   │    │    EDGE CORE (Raspberry Pi 3B)  │
        │ - Parquet Historical Ingestion  │    │ - 27 Virtual Bots (bot.py)      │
        │ - Grid Search Optimizer         │    │ - Dynamic Param Loader (TTL 60s)│
        │   (optimize_fleet.py: 54 comb.) │    │ - Atomic POSIX State Storage    │
        │ - Validation: Sharpe & Drawdown │    │ - Zero Flash-Wear Memory Shields│
        └────────────────┬────────────────┘    └────────────────┬────────────────┘
                         │                                      │
                         │ Dynamic Hyperparameters              │ Local State Deltas
                         ▼ (fleet_optimized.json)               ▼ (state_*.json)
        ┌─────────────────────────────────┐    ┌─────────────────────────────────┐
        │  HOT-SWAP PARAMETER PIPELINE    │───►│ TELEMETRY SERVER (server.py)    │
        │ - Zero-Downtime Hot Swapping    │    │ - Flask + Eventlet + WebSockets │
        │ - Calibrated BE & ATR Bands     │    │ - psutil C-Binding Metrics      │
        └─────────────────────────────────┘    └────────────────┬────────────────┘
                                                                │
                                         ┌──────────────────────┴──────────────────────┐
                                         ▼                                             ▼
                        ┌─────────────────────────────────┐           ┌─────────────────────────────────┐
                        │  LG ULTRAGEAR 21:9 KIOSK UI     │           │  MOBILE & WALL KIOSK TELEMETRY  │
                        │ - Bloomberg Amber/Mono Aesthetic│           │ - iPhone 16 Mobile Ops (iSH CLI)│
                        │ - Pure Client-Side Math Engine  │           │ - Xiaomi TV A1 Pro Live Console │
                        │ - Real-Time Unrealized P&L/ROE  │           │ - Tailscale WireGuard Mesh 24/7 │
                        └─────────────────────────────────┘           └─────────────────────────────────┘
```

The system operates strictly as a decoupled **three-tier distributed architecture**:
1. **The Compute Worker (`optimize_fleet.py` on MacBook Pro)**: Dedicated high-throughput quantitative worker that ingests historical OHLCV data into Parquet format, sweeps 54-combination Grid Searches across assets and timeframes, and serializes the optimal parameter matrix (`fleet_optimized.json`).
2. **The Quantitative Edge Engine (`bot.py` on Raspberry Pi 3B)**: Low-power edge execution node that evaluates 27 concurrent bots at candle close. Dynamically hot-swaps calibrated risk thresholds via `get_bot_params()` (60s TTL memory cache) without restarting services or interrupting live positions.
3. **The Telemetry & Kiosk Plane (`server.py` & `lite.html`)**: WebSockets streaming server broadcasting state deltas across the private WireGuard mesh (Tailscale MagicDNS) to the Bloomberg Kiosk, Xiaomi TV wall console, and mobile operators.

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
- **Dynamic Floor ATR:** To prevent Stop Loss collapse during prolonged low-volatility consolidations, a floor clamp ($ATR_{\text{min}} = \max(ATR, 0.006 \times Price)$) prevents premature stop-outs during noise sweeps.
- **TD-13 DCA & Exhaustion Battalion:** If an active trade faces extended counter-momentum that reaches a DeMark Countdown 13, the system initiates a calculated dollar-cost average tranche to lower average entry price before mean reversion.

### Dynamic Hyperparameter Hot-Swapping (`fleet_optimized.json`)
Rather than relying on static, rigid ATR multipliers across all assets, `bot.py` incorporates an in-memory **Dynamic Parameter Loader (`get_bot_params`)** with a 60-second TTL cache:
- **Zero-Downtime Hot Swapping:** Risk levels (`atr_sl_trend`, `atr_tp_trend`, `be_threshold_atr`, `scale_out_atr`, `enable_scale_out`) are updated live as soon as a new optimization matrix is pushed by the Worker node, without restarting `gatdseq-bot.service` or disturbing open trades.
- **Empirical Alpha Validation:** In systematic Grid Searches on 30-day historical Parquet data (`BTC/USDT [1h]`), tuning the Break-Even trigger from static 1.0 ATR to **0.5x ATR** converted an unprofitable strategy (PnL: -\$503.64, Sharpe: -1.71, MDD: -16.17%) into a high-conviction winner (**PnL: +\$1,515.97 [+15.16%], Sharpe: 7.11, MDD: -4.00%**).

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
├── bot.py                  # Quantitative engine: 27-bot A/B/C matrix, Dynamic Param Loader, CCXT execution
├── server.py               # Telemetry server: Flask-SocketIO, Eventlet, WebSockets, psutil metrics
├── optimize_fleet.py       # High-performance parallel Grid Search optimizer (Mac worker)
├── fleet_optimized.json    # Calibrated dynamic risk matrix loaded dynamically by production bots
├── run_backtest.py         # Institutional backtesting CLI (Terminal Bloomberg reports)
├── volume_profile.py       # Vectorized volume distribution calculator (POC / VAH / VAL)
├── wycoff_logic.py         # Wyckoff market phase detector and volume divergence analyzer
├── portfolio.json          # Portfolio asset allocation definitions for live Kiosk display
├── requirements.txt        # Python dependency manifest
├── auto_clean.sh -> scripts/auto_clean.sh # Backward-compatible maintenance symlink
├── backtesting/            # High-performance local backtesting suite for Mac (Parquet, event-driven)
│   ├── data_manager.py     # Paged CCXT fetcher & local Parquet caching
│   ├── indicators.py       # Vectorized Wilder's RMA indicators & Volume Profile
│   ├── engine.py           # Bar-by-bar simulation engine with fees & dynamic leverage
│   ├── analytics.py        # Financial metrics (Sharpe, Sortino, MaxDD, Profit Factor)
│   └── optimizer.py        # Multi-parameter Grid Search engine
├── docs/                   # Institutional documentation & system manuals
│   ├── manual_infraestructura.md # Distributed architecture manual (Tailscale Mesh, Edge-Worker hybrid)
│   └── RESEARCH_FUNNEL_ARCHITECTURE.md # Quantitative whitepaper on Multi-Stage Funnel Design
├── scripts/                # Operations, DevOps, and Self-Healing Maintenance Suite
│   ├── auto_clean.sh       # Edge maintenance script (RAM drop_caches, log truncation)
│   ├── start.sh            # Local development environment launcher
│   ├── worker_maintenance.sh # Self-healing RAM purge, cache sweep, and telemetry daemon
│   ├── install_worker_maintenance.sh # One-click installer for macOS worker nodes
│   ├── com.gatdseq.maintenance.plist # Scheduled daily maintenance LaunchDaemon (04:30 AM)
│   └── com.gatdseq.caffeinate.plist  # Root LaunchDaemon anti-sleep clamshell persistence
├── templates/              # Institutional Bloomberg Kiosk Frontend
│   └── lite.html           # Zero-scroll UltraGear 21:9 dashboard (V8 Vanilla JS math engine)
├── tests/                  # Test suites & connectivity diagnostics
│   ├── __init__.py
│   └── test_binance.py     # Binance Futures API and authentication test script
├── legacy/                 # Historical prototypes and deprecated development files
│   ├── README.md           # Archive rationale & provenance documentation
│   ├── backtest.py         # Day 1 prototype single-asset backtesting script
│   ├── dashboard.py        # Day 1 Streamlit prototype web interface
│   └── index.html          # Early prototype Tailwind CSS dashboard template
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

## 🌐 Distributed Infrastructure & SecOps (Tailscale Mesh)

GaTDSEQ operates over a private, encrypted **WireGuard Mesh Network (Tailscale MagicDNS RFC 1123)** across 5 physical endpoints without public port forwarding:

| Hostname (MagicDNS) | IP Tailscale | Platform | Infrastructure Role | Key Daemons |
| :--- | :--- | :--- | :--- | :--- |
| `gtrujillo-raspberry-pi-3b` | `100.95.199.1` | Debian 12 (ARMv7) | Edge Core (27 Bots) | `gatdseq-bot`, `gatdseq-server` |
| `gtrujillo-macbook-pro` | `100.108.212.124` | macOS 11.7 (x86_64) | Compute Worker (ML/Opt) | `com.gatdseq.maintenance`, `caffeinate` |
| `gtrujillo-macbook-air-m4` | `100.108.32.67` | macOS 15.x (ARM64) | Workstation & Control | Application Firewall (`socketfilterfw`) |
| `iphone16` | `100.67.23.122` | iOS 18 (iSH Alpine) | Mobile Ops Terminal | SSH Aliases (`mac`, `pi`, `m4`) |
| `tv` | `100.90.61.47` | Android TV | 24/7 Wall Telemetry | Fullscreen Bloomberg WebSockets Kiosk |

### Headless Bootstrap & Self-Healing Suite (Mac Worker)
To prevent thermal stress, battery swelling, and RAM fragmentation on the 24/7 Clamshell MacBook Pro:
- **Root LaunchDaemons:** `com.gatdseq.maintenance.plist` executes daily at **04:30 AM** to purge inactive memory (`/usr/sbin/purge`), sweep bytecode caches, and perform safe reboots (automatically deferred if a backtest or ML job is actively executing).
- **Headless Auto-Recovery:** With FileVault disabled, Wi-Fi keys in `System.keychain`, and `caffeinate -s -i -m -u` running as a root daemon, the worker reboots in 35s and reconnects to Tailscale and SSH without graphical user login.

*For full operational details, network mapping, and emergency runbooks, consult the [Comprehensive Infrastructure Manual](docs/manual_infraestructura.md).*

---

## ⚖️ License & Disclaimer

*This software is developed strictly for educational and quantitative research purposes. Algorithmic trading and cryptocurrency derivatives involve substantial financial risk. Past performance does not guarantee future results.*
