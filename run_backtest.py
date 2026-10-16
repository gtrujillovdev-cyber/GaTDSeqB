#!/usr/bin/env python3
import sys
import argparse
import pandas as pd
from backtesting import (
    load_dataset,
    prepare_market_indicators,
    BacktestEngine,
    compute_metrics,
    print_bloomberg_report,
    run_grid_search,
    print_optimization_table
)

def run_single(symbol: str, tf: str, strat: str, days: int, bank: float, export_csv: str = None):
    # 1. Cargar datos
    raw_df = load_dataset(symbol=symbol, timeframe=tf, days=days)
    
    # 2. Preparar indicadores
    df = prepare_market_indicators(raw_df)
    
    # 3. Ejecutar motor
    engine = BacktestEngine(
        symbol=symbol,
        timeframe=tf,
        strategy=strat,
        initial_bank=bank
    )
    result = engine.run(df)
    
    # 4. Calcular métricas
    metrics = compute_metrics(
        initial_bank=bank,
        final_bank=result['final_bank'],
        trades=result['trades'],
        equity_df=result['equity_curve'],
        timeframe=tf
    )
    
    # 5. Imprimir reporte Bloomberg
    period_str = f"{df['datetime'].iloc[0].strftime('%Y-%m-%d')} -> {df['datetime'].iloc[-1].strftime('%Y-%m-%d')}"
    print_bloomberg_report(metrics, symbol, tf, strat, period_str)
    
    # Exportar trades si se solicita
    if export_csv and result['trades']:
        trades_df = pd.DataFrame(result['trades'])
        trades_df.to_csv(export_csv, index=False)
        print(f"📁 Ledger de trades exportado a: {export_csv}")
        
    return metrics, result

def run_strategy_comparison(symbol: str, tf: str, days: int, bank: float):
    print(f"\n⚡ COMPARATIVA DE ESTRATEGIAS CUANTITATIVAS | {symbol} [{tf}] ({days} días)")
    raw_df = load_dataset(symbol=symbol, timeframe=tf, days=days)
    df = prepare_market_indicators(raw_df)
    
    strategies = ["TD9", "WYK", "HYB"]
    results = []
    
    for strat in strategies:
        engine = BacktestEngine(symbol=symbol, timeframe=tf, strategy=strat, initial_bank=bank)
        res = engine.run(df)
        m = compute_metrics(bank, res['final_bank'], res['trades'], res['equity_curve'], tf)
        results.append({
            "Strategy": strat,
            "Net Profit": f"{'+' if m['net_profit']>=0 else ''}${m['net_profit']:,.2f}",
            "ROI": f"{m['net_profit_pct']:.2f}%",
            "Win Rate": f"{m['win_rate']:.1f}%",
            "Profit Factor": f"{m['profit_factor']:.2f}",
            "Max DD": f"-{m['max_drawdown_pct']:.2f}%",
            "Sharpe": f"{m['sharpe_ratio']:.2f}",
            "Trades": m['total_trades']
        })
        
    comp_df = pd.DataFrame(results)
    print("\n" + "=" * 80)
    print(comp_df.to_string(index=False))
    print("=" * 80 + "\n")

def main():
    parser = argparse.ArgumentParser(description="GaTDSEQ Institutional Backtesting Suite (Mac Edition)")
    parser.add_argument("--symbol", type=str, default="BTC/USDT", help="Símbolo a evaluar (ej: BTC/USDT, ETH/USDT)")
    parser.add_argument("--tf", type=str, default="1h", choices=["5m", "15m", "1h", "4h", "1d"], help="Temporalidad")
    parser.add_argument("--strategy", type=str, default="HYB", choices=["TD9", "WYK", "HYB", "ALL"], help="Estrategia a simular")
    parser.add_argument("--days", type=int, default=180, help="Días de histórico a simular")
    parser.add_argument("--bank", type=float, default=10000.0, help="Capital inicial (USD)")
    parser.add_argument("--optimize", action="store_true", help="Ejecutar Grid Search para calibrar parámetros")
    parser.add_argument("--export-csv", type=str, default=None, help="Ruta de archivo para exportar trades")
    
    args = parser.parse_args()
    
    if args.optimize:
        raw_df = load_dataset(symbol=args.symbol, timeframe=args.tf, days=args.days)
        df = prepare_market_indicators(raw_df)
        res_df = run_grid_search(df, symbol=args.symbol, timeframe=args.tf, strategy=args.strategy, initial_bank=args.bank)
        print_optimization_table(res_df, top_n=10)
    elif args.strategy == "ALL":
        run_strategy_comparison(args.symbol, args.tf, args.days, args.bank)
    else:
        run_single(args.symbol, args.tf, args.strategy, args.days, args.bank, args.export_csv)

if __name__ == "__main__":
    main()
