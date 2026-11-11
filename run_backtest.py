#!/usr/bin/env python3
import argparse
import pandas as pd
from backtesting import (
    BacktestEngine,
    compute_metrics,
    load_dataset,
    prepare_market_indicators,
    print_bloomberg_report,
    print_optimization_table,
    run_grid_search,
)


def _load_weekly_if_needed(symbol: str, tf: str, days: int):
    if tf not in ("5m", "15m", "1h", "4h", "1d"):
        return None
    try:
        w_raw = load_dataset(symbol=symbol, timeframe="1w", days=max(days + 400, 1000))
        return prepare_market_indicators(w_raw)
    except Exception:
        return None


def run_single(symbol: str, tf: str, strat: str, days: int, bank: float, export_csv: str = None):
    raw_df = load_dataset(symbol=symbol, timeframe=tf, days=days)
    df = prepare_market_indicators(raw_df)
    weekly_df = _load_weekly_if_needed(symbol, tf, days)

    engine = BacktestEngine(
        symbol=symbol,
        timeframe=tf,
        strategy=strat,
        initial_bank=bank,
    )
    result = engine.run(df, weekly_df=weekly_df)

    metrics = compute_metrics(
        initial_bank=bank,
        final_bank=result["final_bank"],
        trades=result["trades"],
        equity_df=result["equity_curve"],
        timeframe=tf,
    )

    period_str = f"{df['datetime'].iloc[0].strftime('%Y-%m-%d')} -> {df['datetime'].iloc[-1].strftime('%Y-%m-%d')}"
    print_bloomberg_report(metrics, symbol, tf, strat, period_str)

    if export_csv and result["trades"]:
        trades_df = pd.DataFrame(result["trades"])
        trades_df.to_csv(export_csv, index=False)
        print(f"📁 Ledger de trades exportado a: {export_csv}")

    return metrics, result


def run_strategy_comparison(symbol: str, tf: str, days: int, bank: float):
    print(f"\n⚡ COMPARATIVA DE ESTRATEGIAS CUANTITATIVAS | {symbol} [{tf}] ({days} días)")
    raw_df = load_dataset(symbol=symbol, timeframe=tf, days=days)
    df = prepare_market_indicators(raw_df)
    weekly_df = _load_weekly_if_needed(symbol, tf, days)

    strategies = ["TD9", "WYK", "HYB"]
    results = []

    for strat in strategies:
        engine = BacktestEngine(symbol=symbol, timeframe=tf, strategy=strat, initial_bank=bank)
        res = engine.run(df, weekly_df=weekly_df)
        m = compute_metrics(bank, res["final_bank"], res["trades"], res["equity_curve"], tf)
        results.append(
            {
                "Strategy": strat,
                "Net Profit": f"{'+' if m['net_profit'] >= 0 else ''}${m['net_profit']:,.2f}",
                "ROI": f"{m['net_profit_pct']:.2f}%",
                "B&H": f"{m.get('bh_return_pct', 0.0):+.2f}%",
                "Win Rate": f"{m['win_rate']:.1f}%",
                "Profit Factor": f"{m['profit_factor']:.2f}",
                "Max DD": f"-{m['max_drawdown_pct']:.2f}%",
                "Sharpe": f"{m['sharpe_ratio']:.2f}",
                "Trades": m["total_trades"],
            }
        )

    comp_df = pd.DataFrame(results)
    print("\n" + "=" * 90)
    print(comp_df.to_string(index=False))
    print("=" * 90 + "\n")


def main():
    parser = argparse.ArgumentParser(description="GaTDSEQ Institutional Backtesting Suite (Mac Edition)")
    parser.add_argument("--symbol", type=str, default="BTC/USDT", help="Simbolo a evaluar (ej: BTC/USDT)")
    parser.add_argument("--tf", type=str, default="4h", choices=["5m", "15m", "1h", "4h", "1d", "1w"], help="Temporalidad")
    parser.add_argument("--strategy", "--strat", dest="strategy", type=str, default="HYB", choices=["TD9", "WYK", "HYB", "ALL"], help="Estrategia")
    parser.add_argument("--days", type=int, default=365, help="Dias de historico a simular")
    parser.add_argument("--bank", type=float, default=10000.0, help="Capital inicial (USD)")
    parser.add_argument("--optimize", action="store_true", help="Ejecutar Grid Search para calibrar parametros")
    parser.add_argument("--export-csv", type=str, default=None, help="Ruta de archivo para exportar trades")

    args = parser.parse_args()

    if args.optimize:
        raw_df = load_dataset(symbol=args.symbol, timeframe=args.tf, days=args.days)
        df = prepare_market_indicators(raw_df)
        weekly_df = _load_weekly_if_needed(args.symbol, args.tf, args.days)
        res_df = run_grid_search(df, symbol=args.symbol, timeframe=args.tf, strategy=args.strategy, initial_bank=args.bank, weekly_df=weekly_df)
        print_optimization_table(res_df, top_n=10)
    elif args.strategy == "ALL":
        run_strategy_comparison(args.symbol, args.tf, args.days, args.bank)
    else:
        run_single(args.symbol, args.tf, args.strategy, args.days, args.bank, args.export_csv)


if __name__ == "__main__":
    main()
