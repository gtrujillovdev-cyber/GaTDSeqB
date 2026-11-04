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

### Backtesting (Mac Worker)

```bash
# Single backtest — Bloomberg terminal report
python3 run_backtest.py --symbol BTC/USDT --tf 4h --strat HYB --days 30

# Run grid search optimizer (generates fleet_optimized.json)
python3 optimize_fleet.py --symbols BTC/USDT ETH/USDT HYPE/USDT --tf 4h 1d --days 30
```

### Tests

```bash
# Run a single test file
python3 -m pytest tests/test_monte_carlo.py -v

# Run all tests
python3 -m pytest tests/ -v
```

Available test files:
- `test_monte_carlo.py` — Bootstrap Monte Carlo validation (z-score ≥ 2.50 threshold), MFE/MAE metrics
- `test_confidence_gate.py` — Unit tests for `calculate_confidence_score()` in `bot.py` (anti-directional bias, threshold 0.55)
- `test_divergences_sightline.py` — Geometric line-of-sight algorithm for RSI divergence detection and fractal pivots
- `test_binance.py` — Binance Futures API connectivity and authentication

### Production (Raspberry Pi via Tailscale)

```bash
# Deploy backend changes
rsync -avz --exclude '.venv' --exclude '__pycache__' ./ pi@100.95.199.1:~/GaTDSEQ/

# Restart services after Python changes
ssh pi@100.95.199.1 "sudo systemctl restart gatdseq-bot gatdseq-server"

# Monitor logs
ssh pi@100.95.199.1 "tail -n 100 ~/GaTDSEQ/bot_unified.log"
```

---

## Architecture

GaTDSEQ is a **3-tier distributed trading system** split across two physical machines:

### Tier 1 — Compute Worker (MacBook Pro `100.108.212.124`)
- **`optimize_fleet.py`**: Runs a parallel Grid Search over 54 parameter combinations, ingesting Parquet OHLCV data. Outputs `fleet_optimized.json`.
- **`data_manager.py`** (root): CCXT Parquet fetcher used directly by `run_backtest.py` and `optimize_fleet.py`. Stores cached candles under `data/`.
- **`backtesting/`**: Self-contained backtesting suite used exclusively on the Mac worker.
  - `data_manager.py` — CCXT Parquet fetcher/cache (same logic, used by the backtesting package internally)
  - `indicators.py` — Vectorized Wilder's RMA, TD Sequential, Wyckoff
  - `engine.py` — Bar-by-bar simulation with fees and dynamic leverage
  - `analytics.py` — Sharpe, Sortino, MaxDrawdown, Profit Factor
  - `optimizer.py` — Grid Search coordinator

### Tier 2 — Edge Engine (Raspberry Pi 3B `100.95.199.1`, 1 GB RAM)
- **`bot.py`**: The main 27-bot A/B/C execution engine. Runs all bots in a single Python process. Key design decisions:
  - `get_bot_params(symbol, tf, strategy)` — hot-swaps hyperparameters from `fleet_optimized.json` with a 60-second in-memory TTL cache (zero-downtime, no process restart needed).
  - `calculate_confidence_score(candle, direction, trend, perfected)` — 4-dimensional conviction gate; signals with score < 0.55 are skipped (`SKIP`). Tests in `tests/test_confidence_gate.py`.
  - `save_state()` / `load_state()` — atomic POSIX writes via `os.replace()` to prevent state corruption on power loss.
  - Dirty-check before every write to reduce microSD flash wear by >80%.
- **`volume_profile.py`**: Vectorized POC/VAH/VAL volume distribution calculator, imported by `bot.py`.
- **`wycoff_logic.py`**: Wyckoff market phase detector (Accumulation/Distribution, Spring, UTAD) and RSI divergence analyzer using geometric line-of-sight. Imported by `bot.py`.

### Tier 3 — Telemetry & Kiosk (server.py + lite.html)
- **`server.py`**: Flask + Flask-SocketIO (Eventlet) telemetry server on port 5001. Reads `state_*.json` files written by `bot.py` and broadcasts deltas over WebSockets. Also fetches macro tickers (Binance, Yahoo Finance, CoinGecko) in a daemon thread.
- **`templates/lite.html`**: Pure Vanilla JS Bloomberg Kiosk. **All math (P&L, ROE, trailing stop distance) is computed on the client** to keep Raspberry Pi CPU at 0%.

### Bot Matrix (27 bots)
3 assets × 3 timeframes × 3 strategies = 27 concurrent virtual bots, each with isolated `$10,000` virtual equity.

| Strategy | ID | Logic |
|---|---|---|
| **TD9** | `[ASSET]_TD9_[TF]` | Pure DeMark Sequential (Setup 9 + Countdown 13) |
| **WYK** | `[ASSET]_WYK_[TF]` | Wyckoff Volume Spread Analysis |
| **HYB** | `[ASSET]_HYB_[TF]` | TD9 trigger AND Wyckoff phase confirmation (logical AND) |

Assets: `BTC`, `ETH`, `HYPE` — Timeframes: `4h`, `1d`, `1w`

### Key Config Files
| File | Purpose |
|---|---|
| `fleet_optimized.json` | Live risk parameter matrix hot-loaded by `bot.py` (keys: `atr_sl_trend`, `atr_tp_trend`, `be_threshold_atr`, `scale_out_atr`) |
| `portfolio.json` | Asset allocation definitions for Kiosk display |
| `state_[BOT_ID].json` | Per-bot runtime state (written atomically by `bot.py`, read by `server.py`) |
| `trades_[BOT_ID].json` | Per-bot trade ledger (excluded from git — Raspberry Pi only) |
| `.env` | `BINANCE_API_KEY`, `BINANCE_SECRET`, `TELEGRAM_TOKEN` (never commit) |

### Tailscale Mesh Nodes
| Role | Hostname | IP |
|---|---|---|
| Edge Core (27 bots) | `gtrujillo-raspberry-pi-3b` | `100.95.199.1` |
| Compute Worker (ML/Opt) | `gtrujillo-macbook-pro` | `100.108.212.124` |
| Workstation | `gtrujillo-macbook-air-m4` | `100.108.32.67` |
