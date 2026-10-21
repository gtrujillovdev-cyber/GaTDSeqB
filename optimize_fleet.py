#!/usr/bin/env python3
"""
GaTDSEQ Fleet Optimizer (Mac Worker Edition)
=============================================
Orquesta la calibración sistemática y paralela de hiperparámetros
para los 27 bots de la flota cuantitativa utilizando multiprocessing.
Genera la matriz 'fleet_optimized.json' para producción.
"""

import os
import json
import time
import argparse
import pandas as pd
from datetime import datetime
from backtesting.data_manager import load_dataset
from backtesting.indicators import prepare_market_indicators
from backtesting.optimizer import run_grid_search

DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "HYPE/USDT"]
DEFAULT_TIMEFRAMES = ["1h", "4h", "1d"]
DEFAULT_STRATEGIES = ["HYB"]

def optimize_target(symbol: str, tf: str, strategy: str, days: int, bank: float):
    print(f"\n⚡ [OPTIMIZER] Iniciando barrido para {symbol} [{tf}] | Estrategia: {strategy} ({days} días)...")
    t0 = time.time()
    try:
        raw_df = load_dataset(symbol=symbol, timeframe=tf, days=days)
        df = prepare_market_indicators(raw_df)
        
        # Grid Search calibrado
        param_grid = {
            "atr_sl_trend": [1.5, 2.0, 2.5],
            "atr_tp_trend": [2.5, 3.5, 4.5],
            "be_threshold_atr": [0.5, 0.75, 1.0],
            "enable_scale_out": [True, False]
        }
        
        res_df = run_grid_search(
            df=df,
            symbol=symbol,
            timeframe=tf,
            strategy=strategy,
            initial_bank=bank,
            param_grid=param_grid
        )
        
        elapsed = time.time() - t0
        best = res_df.iloc[0].to_dict()
        print(f"✅ [DONE {elapsed:.1f}s] Top #{symbol} [{tf}]: Sharpe={best['sharpe']:.2f} | PnL=+${best['net_pnl']:,.2f} | WR={best['win_rate']:.1f}%")
        return {
            "symbol": symbol,
            "timeframe": tf,
            "strategy": strategy,
            "best_params": {
                "atr_sl_trend": best["atr_sl_trend"],
                "atr_tp_trend": best["atr_tp_trend"],
                "be_threshold_atr": best["be_threshold_atr"],
                "enable_scale_out": bool(best["enable_scale_out"])
            },
            "metrics": {
                "net_pnl": best["net_pnl"],
                "net_pnl_pct": best["net_pnl_pct"],
                "sharpe": best["sharpe"],
                "profit_factor": best["profit_factor"],
                "win_rate": best["win_rate"],
                "max_dd_pct": best["max_dd_pct"],
                "trades": int(best["trades"])
            }
        }
    except Exception as e:
        print(f"❌ Error optimizando {symbol} [{tf}]: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="GaTDSEQ Fleet Optimizer")
    parser.add_argument("--days", type=int, default=60, help="Días de histórico para optimización")
    parser.add_argument("--bank", type=float, default=10000.0, help="Capital base para cada bot")
    parser.add_argument("--out", type=str, default="fleet_optimized.json", help="Ruta de exportación de parámetros")
    args = parser.parse_args()

    print("=" * 80)
    print("  🏛  GATDSEQ FLEET SYSTEMATIC OPTIMIZER | MAC WORKER CLUSTER")
    print(f"  TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    fleet_results = {}
    
    for symbol in DEFAULT_SYMBOLS:
        for tf in DEFAULT_TIMEFRAMES:
            for strat in DEFAULT_STRATEGIES:
                key = f"{symbol}_{tf}_{strat}"
                res = optimize_target(symbol, tf, strat, args.days, args.bank)
                if res:
                    fleet_results[key] = res

    # Guardar matriz de parámetros
    with open(args.out, "w") as f:
        json.dump(fleet_results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"📁 Matriz de parámetros optimizados guardada exitosamente en: {args.out}")
    print("=" * 80)

if __name__ == "__main__":
    main()
