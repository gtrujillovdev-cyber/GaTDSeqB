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

### Tier 1 — Compute Worker (MacBook Pro)
- **`optimize_fleet.py`**: Runs a parallel Grid Search over 54 parameter combinations, ingesting Parquet OHLCV data cached by `backtesting/data_manager.py`. Outputs `fleet_optimized.json`.
- **`backtesting/`**: Self-contained backtesting suite used exclusively on the Mac worker.
  - `data_manager.py` — CCXT Parquet fetcher/cache
  - `indicators.py` — Vectorized Wilder's RMA, TD Sequential, Wyckoff
  - `engine.py` — Bar-by-bar simulation with fees and dynamic leverage
  - `analytics.py` — Sharpe, Sortino, MaxDrawdown, Profit Factor
  - `optimizer.py` — Grid Search coordinator

### Tier 2 — Edge Engine (Raspberry Pi 3B, 1 GB RAM)
- **`bot.py`**: The main 27-bot A/B/C execution engine. Runs all bots in a single Python process. Key design decisions:
  - `get_bot_params(symbol, tf, strategy)` — hot-swaps hyperparameters from `fleet_optimized.json` with a 60-second in-memory TTL cache (zero-downtime, no process restart needed).
  - `save_state()` / `load_state()` — atomic POSIX writes via `os.replace()` to prevent state corruption on power loss.
  - Dirty-check before every write to reduce microSD flash wear by >80%.
- **`volume_profile.py`** and **`wycoff_logic.py`**: Imported by `bot.py` for live signal generation.

### Tier 3 — Telemetry & Kiosk (server.py + lite.html)
- **`server.py`**: Flask + Flask-SocketIO (Eventlet) telemetry server on port 5001. Reads `state_*.json` files written by `bot.py` and broadcasts deltas over WebSockets. Also fetches macro tickers (Binance, Yahoo Finance, CoinGecko) in a daemon thread.
- **`templates/lite.html`**: Pure Vanilla JS Bloomberg Kiosk. **All math (P&L, ROE, trailing stop distance) is computed on the client** to keep Raspberry Pi CPU at 0%.

### Bot Naming Convention
`[ASSET]_[STRATEGY]_[TIMEFRAME]` → e.g. `BTC_HYB_4h`, `ETH_WYK_1d`, `HYPE_TD9_1w`

- **TD9** — Pure DeMark Sequential (Setup 9 + Countdown 13)
- **WYK** — Wyckoff Volume Spread Analysis
- **HYB** — Hybrid: requires both TD9 trigger AND Wyckoff phase confirmation

### Key Config Files
| File | Purpose |
|---|---|
| `fleet_optimized.json` | Live risk parameter matrix hot-loaded by `bot.py` |
| `portfolio.json` | Asset allocation definitions for Kiosk display |
| `state_[BOT_ID].json` | Per-bot runtime state (written atomically by `bot.py`, read by `server.py`) |
| `trades_[BOT_ID].json` | Per-bot trade ledger (excluded from git — Raspberry Pi only) |
| `.env` | `BINANCE_API_KEY`, `BINANCE_SECRET`, `TELEGRAM_TOKEN` (never commit) |
