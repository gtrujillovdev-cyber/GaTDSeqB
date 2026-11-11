# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@GEMINI.md

---

## Development Commands

```bash
# Activate virtual environment (Python 3.13, always required)
source .venv/bin/activate

# Start full stack locally (bot + server)
bash scripts/start.sh
# → Bloomberg Kiosk at http://localhost:5001/lite

# Run telemetry server only
python3 server.py

# Run bot engine only
python3 bot.py

# Install/update dependencies
pip install -r requirements.txt
```

### Backtesting (Mac Worker only — do NOT deploy to Pi)

```bash
# Single backtest — Bloomberg terminal report
python3 run_backtest.py --symbol BTC/USDT --tf 4h --strategy HYB --days 365

# Run Walk-Forward optimizer (generates fleet_optimized.json)
python3 optimize_fleet.py --symbols BTC/USDT ETH/USDT HYPE/USDT --tf 4h 1d 1w --days 365
```

### Tests

All tests must be run from the **project root** (not from `tests/`) because they import `bot.py` directly.

```bash
# Run a single test file
python3 -m pytest tests/test_monte_carlo.py -v

# Run all tests
python3 -m pytest tests/ -v
```

Available test files:
- `test_monte_carlo.py` — Bootstrap Monte Carlo validation (z-score ≥ 2.50 threshold), MFE/MAE metrics
- `test_confidence_gate.py` — Unit tests for `calculate_confidence_score()` and `get_bot_params()` in `bot.py`
- `test_divergences_sightline.py` — Geometric line-of-sight algorithm for RSI divergence detection and fractal pivots
- `test_binance.py` — Live Binance Futures connectivity; **requires valid credentials in `.env`**

### Production (Raspberry Pi via Tailscale)

```bash
# Deploy backend changes
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude 'backtesting/' ./ pi@100.95.199.1:~/GaTDSEQ/

# Restart services after Python changes
ssh pi@100.95.199.1 "sudo systemctl restart gatdseq-bot gatdseq-server"

# Monitor logs
ssh pi@100.95.199.1 "tail -n 100 ~/GaTDSEQ/bot_unified.log"
```

---

## Architecture

GaTDSEQ is a **3-tier distributed trading system** split across two physical machines:

### Tier 1 — Compute Worker (MacBook Pro `100.108.212.124`)
- **`optimize_fleet.py`**: Walk-Forward Grid Search over 54 parameter combinations (In-Sample 70% / Out-of-Sample 30%); outputs `fleet_optimized.json`.
- **`data_manager.py`** (root): Canonical CCXT Parquet fetcher with staleness checks (`backtesting/data_manager.py` re-exports from root). Caches candles under `backtesting/data/`.
- **`backtesting/`**: Self-contained Python package (has `__init__.py`), used **exclusively** on the Mac worker.
  - `data_manager.py` — re-exports root `data_manager.py` using `backtesting/data/`
  - `indicators.py` — re-exports `core/indicators.py` (Single Source of Truth)
  - `engine.py` — Bar-by-bar simulation with fees, slippage, funding, liquidation check, and dynamic leverage
  - `analytics.py` — Sharpe, Sortino, Calmar, Buy & Hold Benchmark, MaxDrawdown, Profit Factor, Monte Carlo
  - `optimizer.py` — Grid Search & Walk-Forward coordinator

### Shared Quantitative Core (`core/` — deploy to Pi alongside `bot.py`)
- **`core/indicators.py`**: Wilder's RMA RSI/ATR/ADX, TD Sequential, Volume Profile, Line-of-Sight RSI divergences.
- **`core/strategy.py`**: `calculate_confidence_score()`, `compute_entry_levels()`, `get_base_risk()`, `load_fleet_params()`, `compute_weekly_context()`. Used identically by `bot.py` and `backtesting/engine.py`.

### Tier 2 — Edge Engine (Raspberry Pi 3B `100.95.199.1`, 1 GB RAM)
- **`bot.py`**: The main 27-bot execution engine running in a single Python process. Key internals:
  - `get_bot_params(symbol, tf, strategy)` — hot-swaps hyperparameters from `fleet_optimized.json` with a 60-second in-memory TTL cache (zero-downtime).
  - `calculate_confidence_score(candle, direction, trend, perfected)` — 4-dimensional conviction gate; signals with score < 0.55 are skipped (`SKIP`).
  - `save_state()` / `load_state()` — atomic POSIX writes via `os.replace()` to prevent state corruption on power loss. Dirty-check before every write reduces microSD flash wear by >80%.
  - All print calls are monkey-patched at module load time to prepend `[HH:MM:SS]` timestamps.
- **`volume_profile.py`**: Vectorized POC/VAH/VAL volume distribution calculator, imported by `bot.py`.
- **`wycoff_logic.py`**: Wyckoff phase detector (Accumulation/Distribution, Spring, UTAD) and RSI divergence analyzer using geometric line-of-sight. Imported by `bot.py`.

### Tier 3 — Telemetry & Kiosk (`server.py` + `templates/lite.html`)
- **`server.py`**: Flask + Flask-SocketIO (Eventlet) on port 5001. Reads all `state_*.json` files via glob, broadcasts deltas over WebSockets. Daemon thread fetches macro tickers from Binance, Yahoo Finance, and CoinGecko (BTC dominance throttled to every 300 s).
- **`templates/lite.html`**: Pure Vanilla JS Bloomberg Kiosk. **All P&L, ROE, and trailing stop math runs client-side** — zero CPU cost on the Pi.

### Bot Naming Convention
Bot IDs follow the pattern `{ASSET}_{STRATEGY}_{TF}` — e.g., `BTC_HYB_4h`, `ETH_TD9_1d`, `HYPE_WYK_1w`.
State files are named `state_{BOT_ID}.json`; trade ledgers are `trades_{BOT_ID}.json`.

### Bot Matrix (27 bots)
3 assets × 3 timeframes × 3 strategies = 27 concurrent virtual bots, each with isolated `$10,000` virtual equity.

| Strategy | Logic |
|---|---|
| **TD9** | Pure DeMark Sequential (Setup 9 + Countdown 13) |
| **WYK** | Wyckoff Volume Spread Analysis |
| **HYB** | TD9 trigger AND Wyckoff phase confirmation (logical AND) |

Assets: `BTC`, `ETH`, `HYPE` — Timeframes: `4h`, `1d`, `1w`

### Key Config Files
| File | Purpose |
|---|---|
| `fleet_optimized.json` | Live risk parameter matrix hot-loaded by `bot.py` (keys: `atr_sl_trend`, `atr_tp_trend`, `be_threshold_atr`, `scale_out_atr`) |
| `portfolio.json` | Asset allocation definitions for Kiosk Holdings panel |
| `state_{BOT_ID}.json` | Per-bot runtime state (written atomically by `bot.py`, read by `server.py` via glob) |
| `trades_{BOT_ID}.json` | Per-bot trade ledger (git-excluded — Raspberry Pi only) |
| `.env` | `BINANCE_API_KEY`, `BINANCE_SECRET`, `TELEGRAM_TOKEN` |

### Tailscale Mesh Nodes
| Role | Hostname | IP |
|---|---|---|
| Edge Core (27 bots) | `gtrujillo-raspberry-pi-3b` | `100.95.199.1` |
| Compute Worker (ML/Opt) | `gtrujillo-macbook-pro` | `100.108.212.124` |
| Workstation | `gtrujillo-macbook-air-m4` | `100.108.32.67` |
