import itertools
from typing import Any, Dict, List, Optional
import pandas as pd

from core.strategy import DEFAULT_BOT_PARAMS
from .analytics import compute_metrics
from .engine import BacktestEngine

DEFAULT_PARAM_GRID: Dict[str, List[Any]] = {
    "atr_sl_trend": [1.5, 2.0, 2.5],
    "atr_tp_trend": [2.5, 3.5, 4.5],
    "be_threshold_atr": [1.0, 1.25, 1.5],
    "enable_scale_out": [True, False],
}


def run_grid_search(
    df: pd.DataFrame,
    symbol: str = "BTC/USDT",
    timeframe: str = "4h",
    strategy: str = "HYB",
    initial_bank: float = 10000.0,
    param_grid: Optional[Dict[str, List[Any]]] = None,
    weekly_df: Optional[pd.DataFrame] = None,
    eval_start_idx: Optional[int] = None,
) -> pd.DataFrame:
    """
    Ejecuta un barrido de parametros (Grid Search) para afinar la estrategia.
    Nunca explora be_threshold_atr < 1.0 para evitar el efecto Choke.
    """
    if param_grid is None:
        param_grid = dict(DEFAULT_PARAM_GRID)

    keys = list(param_grid.keys())
    combinations = list(itertools.product(*[param_grid[k] for k in keys]))

    print(f"\n🔬 INICIANDO OPTIMIZACION QUANT | {len(combinations)} combinaciones para {symbol} [{timeframe}] ({strategy})...")

    start_for_cache = eval_start_idx if eval_start_idx is not None else (200 if len(df) > 250 else min(50, max(25, len(df) // 4)))
    precomputed = BacktestEngine.precompute_bar_context(df, weekly_df=weekly_df, start_idx=start_for_cache)

    results = []
    for combo in combinations:
        params = dict(zip(keys, combo))
        engine = BacktestEngine(
            symbol=symbol,
            timeframe=timeframe,
            strategy=strategy,
            initial_bank=initial_bank,
            params=params,
        )
        res = engine.run(df, weekly_df=weekly_df, eval_start_idx=eval_start_idx, precomputed_context=precomputed)
        m = compute_metrics(initial_bank, res["final_bank"], res["trades"], res["equity_curve"], timeframe)

        row = dict(params)
        row.update(
            {
                "net_pnl": m["net_profit"],
                "net_pnl_pct": m["net_profit_pct"],
                "bh_return_pct": m["bh_return_pct"],
                "alpha_vs_bh_pct": m["alpha_vs_bh_pct"],
                "win_rate": m["win_rate"],
                "profit_factor": m["profit_factor"],
                "max_dd_pct": m["max_drawdown_pct"],
                "sharpe": m["sharpe_ratio"],
                "trades": m["total_trades"],
            }
        )
        results.append(row)

    res_df = pd.DataFrame(results)
    res_df.sort_values(by=["trades", "sharpe", "net_pnl"], ascending=[False, False, False], inplace=True)
    # Priorizar combinaciones con muestra minima (>= 5 trades) sobre las vacias
    if (res_df["trades"] >= 5).any():
        sufficient = res_df[res_df["trades"] >= 5].sort_values(by=["sharpe", "net_pnl"], ascending=[False, False])
        insufficient = res_df[res_df["trades"] < 5].sort_values(by=["sharpe", "net_pnl"], ascending=[False, False])
        res_df = pd.concat([sufficient, insufficient], ignore_index=True)
    else:
        res_df.sort_values(by=["sharpe", "net_pnl"], ascending=[False, False], inplace=True)
        res_df.reset_index(drop=True, inplace=True)
    return res_df


def run_walk_forward(
    df: pd.DataFrame,
    symbol: str = "BTC/USDT",
    timeframe: str = "4h",
    strategy: str = "HYB",
    initial_bank: float = 10000.0,
    param_grid: Optional[Dict[str, List[Any]]] = None,
    weekly_df: Optional[pd.DataFrame] = None,
    is_ratio: float = 0.70,
    min_is_trades: int = 5,
) -> Dict[str, Any]:
    """
    Validacion Walk-Forward (In-Sample 70% / Out-of-Sample 30%).
    Previene overfitting: selecciona parametros en IS y reporta rendimiento real en OOS.
    Si IS tiene menos de min_is_trades, mantiene defaults institucionales.
    """
    total = len(df)
    warmup = min(200, max(30, total // 5))
    usable = total - warmup
    split_idx = warmup + int(usable * is_ratio)

    if usable < 40 or split_idx <= warmup + 10 or split_idx >= total - 10:
        # Dataset demasiado corto para split; usar defaults evaluando todo el rango
        engine = BacktestEngine(symbol=symbol, timeframe=timeframe, strategy=strategy, initial_bank=initial_bank)
        res = engine.run(df, weekly_df=weekly_df, eval_start_idx=warmup)
        m = compute_metrics(initial_bank, res["final_bank"], res["trades"], res["equity_curve"], timeframe)
        in_sample_norm = {
            "net_pnl": float(m["net_profit"]),
            "net_pnl_pct": float(m["net_profit_pct"]),
            "sharpe": float(m["sharpe_ratio"]),
            "profit_factor": float(m["profit_factor"]),
            "win_rate": float(m["win_rate"]),
            "max_dd_pct": float(m["max_drawdown_pct"]),
            "trades": int(m["total_trades"]),
        }
        return {
            "is_calibrated": False,
            "best_params": {
                "atr_sl_trend": DEFAULT_BOT_PARAMS["atr_sl_trend"],
                "atr_tp_trend": DEFAULT_BOT_PARAMS["atr_tp_trend"],
                "be_threshold_atr": DEFAULT_BOT_PARAMS["be_threshold_atr"],
                "enable_scale_out": DEFAULT_BOT_PARAMS["enable_scale_out"],
            },
            "in_sample": in_sample_norm,
            "out_of_sample": m,
        }

    df_is = df.iloc[:split_idx].reset_index(drop=True)
    res_df = run_grid_search(
        df=df_is,
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy,
        initial_bank=initial_bank,
        param_grid=param_grid,
        weekly_df=weekly_df,
        eval_start_idx=warmup,
    )

    top = res_df.iloc[0].to_dict()
    is_calibrated = int(top["trades"]) >= min_is_trades

    if is_calibrated:
        chosen_params = {
            "atr_sl_trend": float(top["atr_sl_trend"]),
            "atr_tp_trend": float(top["atr_tp_trend"]),
            "be_threshold_atr": max(1.0, float(top["be_threshold_atr"])),
            "enable_scale_out": bool(top["enable_scale_out"]),
        }
    else:
        chosen_params = {
            "atr_sl_trend": DEFAULT_BOT_PARAMS["atr_sl_trend"],
            "atr_tp_trend": DEFAULT_BOT_PARAMS["atr_tp_trend"],
            "be_threshold_atr": DEFAULT_BOT_PARAMS["be_threshold_atr"],
            "enable_scale_out": DEFAULT_BOT_PARAMS["enable_scale_out"],
        }

    # Evaluar en Out-Of-Sample usando df completo pero empezando exactamente en split_idx (con warm-up intacto)
    oos_engine = BacktestEngine(
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy,
        initial_bank=initial_bank,
        params=chosen_params,
    )
    oos_res = oos_engine.run(df, weekly_df=weekly_df, eval_start_idx=split_idx)
    oos_metrics = compute_metrics(initial_bank, oos_res["final_bank"], oos_res["trades"], oos_res["equity_curve"], timeframe)

    return {
        "is_calibrated": is_calibrated,
        "best_params": chosen_params,
        "in_sample": {
            "net_pnl": float(top["net_pnl"]),
            "net_pnl_pct": float(top["net_pnl_pct"]),
            "sharpe": float(top["sharpe"]),
            "profit_factor": float(top["profit_factor"]),
            "win_rate": float(top["win_rate"]),
            "max_dd_pct": float(top["max_dd_pct"]),
            "trades": int(top["trades"]),
        },
        "out_of_sample": oos_metrics,
    }


def print_optimization_table(res_df: pd.DataFrame, top_n: int = 5):
    print("\n" + "=" * 96)
    print("  🏆 TOP PARAMETER COMBINATIONS (OPTIMIZACION DE ESTRATEGIA)")
    print("=" * 96)
    print(f"{'Rank':<5} | {'SL':<5} | {'TP':<5} | {'BE ATR':<7} | {'ScaleOut':<9} | {'Net PnL ($)':<12} | {'WinRate':<8} | {'PF':<6} | {'MaxDD':<7} | {'Sharpe':<6} | {'Trades':<6}")
    print("-" * 96)

    for i in range(min(top_n, len(res_df))):
        r = res_df.iloc[i]
        sl = r.get("atr_sl_trend", "-")
        tp = r.get("atr_tp_trend", "-")
        be = r.get("be_threshold_atr", "-")
        so = "YES" if r.get("enable_scale_out", True) else "NO"
        pnl = r["net_pnl"]
        wr = r["win_rate"]
        pf = r["profit_factor"]
        dd = r["max_dd_pct"]
        sh = r["sharpe"]
        tr = int(r["trades"])

        pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
        print(f"#{i+1:<4} | {sl:<5} | {tp:<5} | {be:<7} | {so:<9} | {pnl_str:<12} | {wr:>6.1f}% | {pf:>5.2f} | -{dd:>5.1f}% | {sh:>6.2f} | {tr:<6}")
    print("=" * 96 + "\n")
