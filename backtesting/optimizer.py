import pandas as pd
from typing import List, Dict, Any
from .engine import BacktestEngine
from .analytics import compute_metrics

def run_grid_search(
    df: pd.DataFrame,
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    strategy: str = "HYB",
    initial_bank: float = 10000.0,
    param_grid: Dict[str, List[Any]] = None
) -> pd.DataFrame:
    """
    Ejecuta un barrido de parametros (Grid Search) para afinar la estrategia.
    """
    if param_grid is None:
        param_grid = {
            "atr_sl_trend": [1.5, 2.0, 2.5],
            "atr_tp_trend": [2.5, 3.5, 4.5],
            "be_threshold_atr": [0.5, 0.75, 1.0],
            "enable_scale_out": [True, False]
        }
        
    import itertools
    keys = list(param_grid.keys())
    combinations = list(itertools.product(*[param_grid[k] for k in keys]))
    
    print(f"\n🔬 INICIANDO OPTIMIZACIÓN QUANT | {len(combinations)} combinaciones para {symbol} [{timeframe}]...")
    
    results = []
    for idx, combo in enumerate(combinations, 1):
        params = dict(zip(keys, combo))
        engine = BacktestEngine(
            symbol=symbol,
            timeframe=timeframe,
            strategy=strategy,
            initial_bank=initial_bank,
            params=params
        )
        res = engine.run(df)
        m = compute_metrics(initial_bank, res['final_bank'], res['trades'], res['equity_curve'], timeframe)
        
        row = dict(params)
        row.update({
            "net_pnl": m["net_profit"],
            "net_pnl_pct": m["net_profit_pct"],
            "win_rate": m["win_rate"],
            "profit_factor": m["profit_factor"],
            "max_dd_pct": m["max_drawdown_pct"],
            "sharpe": m["sharpe_ratio"],
            "trades": m["total_trades"]
        })
        results.append(row)
        
    res_df = pd.DataFrame(results)
    # Ordenar por Sharpe Ratio y luego por Beneficio Neto
    res_df.sort_values(by=["sharpe", "net_pnl"], ascending=[False, False], inplace=True)
    res_df.reset_index(drop=True, inplace=True)
    return res_df

def print_optimization_table(res_df: pd.DataFrame, top_n: int = 5):
    print("\n" + "=" * 90)
    print("  🏆 TOP PARAMETER COMBINATIONS (OPTIMIZACIÓN DE ESTRATEGIA)")
    print("=" * 90)
    print(f"{'Rank':<5} | {'SL':<5} | {'TP':<5} | {'BE ATR':<7} | {'ScaleOut':<9} | {'Net PnL ($)':<12} | {'WinRate':<8} | {'PF':<6} | {'MaxDD':<7} | {'Sharpe':<6}")
    print("-" * 90)
    
    for i in range(min(top_n, len(res_df))):
        r = res_df.iloc[i]
        sl = r.get("atr_sl_trend", "-")
        tp = r.get("atr_tp_trend", "-")
        be = r.get("be_threshold_atr", "-")
        so = "YES" if r.get("enable_scale_out", True) else "NO"
        pnl = r['net_pnl']
        wr = r['win_rate']
        pf = r['profit_factor']
        dd = r['max_dd_pct']
        sh = r['sharpe']
        
        pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
        print(f"#{i+1:<4} | {sl:<5} | {tp:<5} | {be:<7} | {so:<9} | {pnl_str:<12} | {wr:>6.1f}% | {pf:>5.2f} | -{dd:>5.1f}% | {sh:>6.2f}")
    print("=" * 90 + "\n")
