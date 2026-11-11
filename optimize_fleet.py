#!/usr/bin/env python3
"""
GaTDSEQ Fleet Optimizer (Mac Worker Edition)
=============================================
Calibracion Walk-Forward (In-Sample 70% / Out-of-Sample 30%) para la flota
de 27 bots (4h, 1d, 1w). Genera 'fleet_optimized.json' para produccion.
"""

import argparse
import json
import os
import time
from datetime import datetime
import pandas as pd

from backtesting.data_manager import load_dataset
from backtesting.indicators import prepare_market_indicators
from backtesting.optimizer import DEFAULT_PARAM_GRID, run_walk_forward
from core.strategy import FLEET_STRATEGIES, FLEET_TIMEFRAMES

DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "HYPE/USDT"]
DEFAULT_TIMEFRAMES = list(FLEET_TIMEFRAMES)
DEFAULT_STRATEGIES = list(FLEET_STRATEGIES)

_WARMUP_DAYS = {
    "1h": 15,
    "4h": 45,
    "1d": 210,
    "1w": 700,
}


def optimize_target(symbol: str, tf: str, strategy: str, days: int, bank: float, weekly_df=None):
    print(f"\n⚡ [OPTIMIZER] Walk-Forward para {symbol} [{tf}] | Estrategia: {strategy} ({days} días)...")
    t0 = time.time()
    try:
        fetch_days = days + _WARMUP_DAYS.get(tf, 60)
        raw_df = load_dataset(symbol=symbol, timeframe=tf, days=fetch_days)
        if days and "datetime" in raw_df.columns:
            cutoff = raw_df["datetime"].max() - pd.Timedelta(days=fetch_days)
            raw_df = raw_df[raw_df["datetime"] >= cutoff].reset_index(drop=True)

        df = prepare_market_indicators(raw_df)
        wf = run_walk_forward(
            df=df,
            symbol=symbol,
            timeframe=tf,
            strategy=strategy,
            initial_bank=bank,
            param_grid=DEFAULT_PARAM_GRID,
            weekly_df=weekly_df,
        )

        oos = wf["out_of_sample"]
        elapsed = time.time() - t0
        status = "CALIBRATED" if wf["is_calibrated"] else "DEFAULT (LOW SAMPLE)"
        print(
            f"✅ [DONE {elapsed:.1f}s] {symbol} [{tf}] {strategy} [{status}] | "
            f"OOS Sharpe={oos['sharpe_ratio']:.2f} | OOS PnL=+${oos['net_profit']:,.2f} | "
            f"B&H={oos.get('bh_return_pct', 0.0):+.2f}% | Trades={oos['total_trades']}"
        )
        return {
            "symbol": symbol,
            "timeframe": tf,
            "strategy": strategy,
            "is_calibrated": wf["is_calibrated"],
            "best_params": wf["best_params"],
            "metrics": {
                "net_pnl": float(oos["net_profit"]),
                "net_pnl_pct": float(oos["net_profit_pct"]),
                "bh_return_pct": float(oos.get("bh_return_pct", 0.0)),
                "alpha_vs_bh_pct": float(oos.get("alpha_vs_bh_pct", 0.0)),
                "sharpe": float(oos["sharpe_ratio"]),
                "profit_factor": float(oos["profit_factor"]),
                "win_rate": float(oos["win_rate"]),
                "max_dd_pct": float(oos["max_drawdown_pct"]),
                "trades": int(oos["total_trades"]),
                "in_sample_trades": int(wf["in_sample"]["trades"]),
                "in_sample_sharpe": float(wf["in_sample"]["sharpe"]),
            },
        }
    except Exception as e:
        print(f"❌ Error optimizando {symbol} [{tf}] {strategy}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="GaTDSEQ Fleet Optimizer (Walk-Forward)")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, help="Simbolos a optimizar")
    parser.add_argument("--tf", nargs="+", default=DEFAULT_TIMEFRAMES, help="Timeframes a optimizar")
    parser.add_argument("--strategies", nargs="+", default=DEFAULT_STRATEGIES, help="Estrategias")
    parser.add_argument("--days", type=int, default=365, help="Dias de ventana de evaluacion")
    parser.add_argument("--bank", type=float, default=10000.0, help="Capital base por bot")
    parser.add_argument("--out", type=str, default="fleet_optimized.json", help="Ruta de exportacion")
    args = parser.parse_args()

    print("=" * 80)
    print("  🏛  GATDSEQ FLEET SYSTEMATIC OPTIMIZER | WALK-FORWARD EDITION")
    print(f"  TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    fleet_results = {}
    if os.path.exists(args.out):
        try:
            with open(args.out, "r") as f:
                existing = json.load(f)
            # Conservar entradas vigentes del universo canonico (4h, 1d, 1w) para actualizaciones parciales
            for k, v in existing.items():
                if v.get("timeframe") in DEFAULT_TIMEFRAMES:
                    fleet_results[k] = v
        except Exception as e:
            print(f"⚠️ Aviso al leer {args.out}: {e}")

    weekly_cache = {}
    for symbol in args.symbols:
        try:
            w_raw = load_dataset(symbol=symbol, timeframe="1w", days=max(args.days + 400, 1000))
            weekly_cache[symbol] = prepare_market_indicators(w_raw)
        except Exception as e:
            print(f"⚠️ Sin contexto 1W para {symbol}: {e}")
            weekly_cache[symbol] = None

    for symbol in args.symbols:
        for tf in args.tf:
            for strat in args.strategies:
                key = f"{symbol}_{tf}_{strat}"
                w_df = weekly_cache.get(symbol) if tf in ("1h", "4h", "1d") else None
                res = optimize_target(symbol, tf, strat, args.days, args.bank, weekly_df=w_df)
                if res:
                    fleet_results[key] = res

    with open(args.out, "w") as f:
        json.dump(fleet_results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"📁 Matriz de parametros optimizados guardada en: {args.out}")
    print("=" * 80)


if __name__ == "__main__":
    main()
