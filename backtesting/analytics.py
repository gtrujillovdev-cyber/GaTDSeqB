import math
from typing import Any, Dict, List
import numpy as np
import pandas as pd

MIN_MONTE_CARLO_SAMPLE = 15


def aggregate_round_trip_trades(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Agrupa eventos parciales (_partial, _tp2) y cierre final (FULL_EXIT) por parent_id
    para evitar inflar artificialmente el conteo de trades, win rate y Z-score de Monte Carlo.
    Si los dicts no contienen parent_id (ej. tests unitarios sinteticos), se preservan 1:1.
    """
    if not trades:
        return []

    grouped: Dict[Any, Dict[str, Any]] = {}
    passthrough: List[Dict[str, Any]] = []

    for idx, t in enumerate(trades):
        pid = t.get("parent_id")
        if pid is None:
            passthrough.append(t)
            continue

        if pid not in grouped:
            grouped[pid] = {
                "parent_id": pid,
                "pnl": float(t.get("pnl", 0.0)),
                "mfe_r": float(t.get("mfe_r", 0.0)),
                "mae_r": float(t.get("mae_r", 0.0)),
                "realized_rs": [float(t["realized_r"])] if "realized_r" in t else [],
            }
        else:
            g = grouped[pid]
            g["pnl"] += float(t.get("pnl", 0.0))
            g["mfe_r"] = max(g["mfe_r"], float(t.get("mfe_r", 0.0)))
            g["mae_r"] = max(g["mae_r"], float(t.get("mae_r", 0.0)))
            if "realized_r" in t:
                g["realized_rs"].append(float(t["realized_r"]))

    aggregated: List[Dict[str, Any]] = list(passthrough)
    for g in grouped.values():
        realized_r = float(np.mean(g["realized_rs"])) if g["realized_rs"] else 0.0
        aggregated.append(
            {
                "parent_id": g["parent_id"],
                "pnl": g["pnl"],
                "mfe_r": g["mfe_r"],
                "mae_r": g["mae_r"],
                "realized_r": realized_r,
            }
        )
    return aggregated


def compute_monte_carlo_edge(
    trades: List[Dict[str, Any]],
    n_simulations: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Test de Hipotesis Nula e Inferencia Estadistica Cuantitativa (Monte Carlo Bootstrap).
    Evalua si la distribucion de retornos por posicion cerrada bate al azar
    con significancia Z >= 2.50 (p <= 0.01) mediante Rademacher Sign-Flip.
    Exige un minimo de 15 trades round-trip para inferencia valida.
    """
    round_trips = aggregate_round_trip_trades(trades)
    if not round_trips:
        return {
            "has_data": False,
            "z_score": 0.0,
            "p_value": 1.0,
            "is_significant": False,
            "avg_mfe_r": 0.0,
            "avg_mae_r": 0.0,
            "mfe_mae_ratio": 0.0,
            "avg_realized_r": 0.0,
            "sample_size": 0,
            "n_simulations": n_simulations,
        }

    mfes = [float(t.get("mfe_r", 0.0)) for t in round_trips if "mfe_r" in t]
    maes = [float(t.get("mae_r", 0.0)) for t in round_trips if "mae_r" in t]
    realized_rs = [float(t.get("realized_r", 0.0)) for t in round_trips if "realized_r" in t]

    avg_mfe = float(np.mean(mfes)) if mfes else 0.0
    avg_mae = float(np.mean(maes)) if maes else 0.0
    mfe_mae_ratio = (avg_mfe / avg_mae) if avg_mae > 0 else 0.0
    avg_realized = float(np.mean(realized_rs)) if realized_rs else 0.0

    if len(realized_rs) < MIN_MONTE_CARLO_SAMPLE:
        return {
            "has_data": True,
            "z_score": 0.0,
            "p_value": 1.0,
            "is_significant": False,
            "null_mean": 0.0,
            "null_std": 0.0,
            "observed_mean": avg_realized,
            "avg_mfe_r": avg_mfe,
            "avg_mae_r": avg_mae,
            "mfe_mae_ratio": mfe_mae_ratio,
            "avg_realized_r": avg_realized,
            "sample_size": len(realized_rs),
            "n_simulations": n_simulations,
        }

    rng = np.random.default_rng(seed)
    rs_arr = np.array(realized_rs)
    observed_mean = float(np.mean(rs_arr))

    signs = rng.choice([-1.0, 1.0], size=(n_simulations, len(rs_arr)))
    null_means = np.mean(signs * rs_arr, axis=1)

    null_mean = float(np.mean(null_means))
    null_std = float(np.std(null_means, ddof=1))
    z_score = float((observed_mean - null_mean) / null_std) if null_std > 0 else 0.0
    p_value = float(np.mean(null_means >= observed_mean))
    is_significant = (z_score >= 2.50) and (p_value <= 0.01)

    return {
        "has_data": True,
        "z_score": z_score,
        "p_value": p_value,
        "is_significant": is_significant,
        "null_mean": null_mean,
        "null_std": null_std,
        "observed_mean": observed_mean,
        "avg_mfe_r": avg_mfe,
        "avg_mae_r": avg_mae,
        "mfe_mae_ratio": mfe_mae_ratio,
        "avg_realized_r": avg_realized,
        "sample_size": len(realized_rs),
        "n_simulations": n_simulations,
    }


def compute_metrics(
    initial_bank: float,
    final_bank: float,
    trades: List[Dict[str, Any]],
    equity_df: pd.DataFrame,
    timeframe: str = "4h",
) -> Dict[str, Any]:
    net_profit = final_bank - initial_bank
    net_profit_pct = (net_profit / initial_bank) * 100.0 if initial_bank > 0 else 0.0

    round_trips = aggregate_round_trip_trades(trades)
    total_trades = len(round_trips)

    # Benchmark Buy & Hold sobre el mismo periodo evaluado
    bh_return_pct = 0.0
    if not equity_df.empty and "close" in equity_df.columns and len(equity_df) >= 2:
        first_close = float(equity_df["close"].iloc[0])
        last_close = float(equity_df["close"].iloc[-1])
        if first_close > 0:
            bh_return_pct = ((last_close - first_close) / first_close) * 100.0
    alpha_vs_bh_pct = net_profit_pct - bh_return_pct

    if total_trades == 0:
        return {
            "initial_bank": initial_bank,
            "final_bank": final_bank,
            "net_profit": 0.0,
            "net_profit_pct": 0.0,
            "bh_return_pct": bh_return_pct,
            "alpha_vs_bh_pct": alpha_vs_bh_pct,
            "total_trades": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "gross_profits": 0.0,
            "gross_losses": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "win_loss_ratio": 0.0,
            "expectancy": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown_usd": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "monte_carlo": compute_monte_carlo_edge([]),
        }

    pnls = [float(t["pnl"]) for t in round_trips]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades) * 100.0

    gross_profits = float(sum(wins))
    gross_losses = float(abs(sum(losses)))
    profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else (99.9 if gross_profits > 0 else 0.0)

    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(abs(np.mean(losses))) if losses else 0.0
    win_loss_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0
    expectancy = (win_rate / 100.0 * avg_win) - ((1.0 - win_rate / 100.0) * avg_loss)

    if not equity_df.empty and "equity" in equity_df.columns:
        equity_series = equity_df["equity"]
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax.replace(0, np.nan)
        max_drawdown_pct = abs(float(drawdown.min())) * 100.0 if not drawdown.dropna().empty else 0.0
        max_drawdown_usd = float((cummax - equity_series).max())

        returns = equity_series.pct_change().dropna()
        periods_map = {
            "5m": 365 * 24 * 12,
            "15m": 365 * 24 * 4,
            "1h": 365 * 24,
            "4h": 365 * 6,
            "1d": 365,
            "1w": 52,
        }
        periods_per_year = periods_map.get(timeframe, 365 * 6)

        std = returns.std()
        sharpe_ratio = float((returns.mean() / std) * math.sqrt(periods_per_year)) if std > 0 else 0.0

        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std()
        sortino_ratio = float((returns.mean() / downside_std) * math.sqrt(periods_per_year)) if downside_std > 0 else 0.0

        n_bars = max(1, len(equity_series))
        years = n_bars / periods_per_year
        cagr_pct = (((final_bank / initial_bank) ** (1.0 / years)) - 1.0) * 100.0 if (initial_bank > 0 and final_bank > 0 and years > 0) else 0.0
        calmar_ratio = (cagr_pct / max_drawdown_pct) if max_drawdown_pct > 0 else 0.0
    else:
        max_drawdown_pct = 0.0
        max_drawdown_usd = 0.0
        sharpe_ratio = 0.0
        sortino_ratio = 0.0
        calmar_ratio = 0.0

    mc_edge = compute_monte_carlo_edge(trades)

    return {
        "initial_bank": initial_bank,
        "final_bank": final_bank,
        "net_profit": net_profit,
        "net_profit_pct": net_profit_pct,
        "bh_return_pct": bh_return_pct,
        "alpha_vs_bh_pct": alpha_vs_bh_pct,
        "total_trades": total_trades,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "gross_profits": gross_profits,
        "gross_losses": gross_losses,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "win_loss_ratio": win_loss_ratio,
        "expectancy": expectancy,
        "max_drawdown_pct": max_drawdown_pct,
        "max_drawdown_usd": max_drawdown_usd,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "calmar_ratio": calmar_ratio,
        "monte_carlo": mc_edge,
    }


def print_bloomberg_report(metrics: Dict[str, Any], symbol: str, timeframe: str, strategy: str, period_str: str = ""):
    """Imprime un informe en la consola con estetica Bloomberg Terminal."""
    W = 68
    sep = "=" * W
    subsep = "-" * W

    print("\n" + sep)
    print("  🏛  GATDSEQ INSTITUTIONAL QUANT LAB | BLOOMBERG TERMINAL AUDIT")
    print(sep)
    print(f"  TARGET: {symbol} [{timeframe}] | STRATEGY: {strategy} {f'| {period_str}' if period_str else ''}")
    print(subsep)

    net_p = metrics["net_profit"]
    sign = "+" if net_p >= 0 else "-"
    abs_net_p = abs(net_p)
    p_color = "\033[92m" if net_p >= 0 else "\033[91m"
    reset = "\033[0m"
    amber = "\033[93m"

    print(f"  {amber}CAPITAL PERFORMANCE{reset}")
    print(f"    Initial Capital:        ${metrics['initial_bank']:>12,.2f} USD")
    print(f"    Final Capital:          ${metrics['final_bank']:>12,.2f} USD")
    print(f"    Net PnL:               {p_color}{sign}${abs_net_p:>11,.2f} USD ({sign}{abs(metrics['net_profit_pct']):.2f}%){reset}")
    print(f"    Buy & Hold Benchmark:    {metrics.get('bh_return_pct', 0.0):>+11.2f}%")
    print(f"    Alpha vs Buy & Hold:     {metrics.get('alpha_vs_bh_pct', 0.0):>+11.2f}%")
    print(f"    Gross Profits:          ${metrics['gross_profits']:>12,.2f} USD")
    print(f"    Gross Losses:           ${metrics['gross_losses']:>12,.2f} USD")

    print(subsep)
    print(f"  {amber}RISK & RETURN PROFILE{reset}")
    print(f"    Profit Factor:           {metrics['profit_factor']:>12.2f}")
    print(f"    Sharpe Ratio (Ann.):     {metrics['sharpe_ratio']:>12.2f}")
    print(f"    Sortino Ratio (Ann.):    {metrics['sortino_ratio']:>12.2f}")
    print(f"    Calmar Ratio:            {metrics.get('calmar_ratio', 0.0):>12.2f}")
    print(f"    Max Drawdown (MDD):      \033[91m-{metrics['max_drawdown_pct']:>11.2f}% (${metrics['max_drawdown_usd']:,.2f})\033[0m")

    print(subsep)
    print(f"  {amber}TRADE EXECUTION EFFICIENCY (ROUND-TRIP){reset}")
    print(f"    Closed Positions:        {metrics['total_trades']:>12d}")
    print(f"    Winning Positions:       {metrics['win_count']:>12d}")
    print(f"    Losing Positions:        {metrics['loss_count']:>12d}")
    print(f"    Win Rate:                {metrics['win_rate']:>11.1f}%")
    print(f"    Win / Loss Ratio:        {metrics['win_loss_ratio']:>12.2f}")
    print(f"    Average Win:            ${metrics['avg_win']:>12,.2f} USD")
    print(f"    Average Loss:           ${metrics['avg_loss']:>12,.2f} USD")
    print(f"    Expectancy / Trade:     ${metrics['expectancy']:>12,.2f} USD")

    mc = metrics.get("monte_carlo", {})
    if mc and mc.get("has_data"):
        print(subsep)
        print(f"  {amber}STATISTICAL EDGE & NOISE REJECTION (MONTE CARLO BOOTSTRAP){reset}")
        print(f"    Sample Size (Round-Trip):{mc.get('sample_size', 0):>12d} (Min: {MIN_MONTE_CARLO_SAMPLE})")
        print(f"    Monte Carlo Runs:        {mc['n_simulations']:>12,d} permutations")
        print(f"    Average Realized R:      {mc['avg_realized_r']:>+12.2f} R")
        print(f"    Avg. MFE (Max Favorable):{mc['avg_mfe_r']:>+12.2f} R")
        print(f"    Avg. MAE (Max Adverse):  {mc['avg_mae_r']:>+12.2f} R")
        print(f"    MFE / MAE Ratio:         {mc['mfe_mae_ratio']:>12.2f}x")

        z_str = f"{mc['z_score']:+.2f}"
        p_str = f"{mc['p_value']:.4f}"
        if mc["is_significant"]:
            status_color = "\033[92m"
            verdict = "REJECTED (CONFIRMED EDGE)"
        else:
            status_color = "\033[93m"
            verdict = "ACCEPTED (INSUFFICIENT SAMPLE / NOISE)"

        print(f"    Z-Score vs Random Walk:  {status_color}{z_str:>12s}{reset} (Threshold: Z >= +2.50)")
        print(f"    Empirical p-Value:       {p_str:>12s} (Significance: p <= 0.01)")
        print(f"    H0 Null Hypothesis:      {status_color}{verdict:>12s}{reset}")

    print(sep + "\n")
