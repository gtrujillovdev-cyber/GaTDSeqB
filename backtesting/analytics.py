import math
import numpy as np
import pandas as pd
from typing import List, Dict, Any

def compute_metrics(
    initial_bank: float,
    final_bank: float,
    trades: List[Dict[str, Any]],
    equity_df: pd.DataFrame,
    timeframe: str = "1h"
) -> Dict[str, Any]:
    net_profit = final_bank - initial_bank
    net_profit_pct = (net_profit / initial_bank) * 100.0 if initial_bank > 0 else 0.0
    
    total_trades = len(trades)
    if total_trades == 0:
        return {
            "initial_bank": initial_bank,
            "final_bank": final_bank,
            "net_profit": 0.0,
            "net_profit_pct": 0.0,
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0
        }
        
    pnls = [t['pnl'] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades) * 100.0
    
    gross_profits = sum(wins)
    gross_losses = abs(sum(losses))
    profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else (99.9 if gross_profits > 0 else 0.0)
    
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = abs(np.mean(losses)) if losses else 0.0
    win_loss_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0
    
    # Expectancy ($ per trade)
    expectancy = (win_rate/100.0 * avg_win) - ((1.0 - win_rate/100.0) * avg_loss)
    
    # Max Drawdown from equity curve
    if not equity_df.empty and 'equity' in equity_df.columns:
        equity_series = equity_df['equity']
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax
        max_drawdown_pct = abs(float(drawdown.min())) * 100.0
        max_drawdown_usd = float((cummax - equity_series).max())
        
        # Returns for Sharpe & Sortino
        returns = equity_series.pct_change().dropna()
        # Periods per year
        if timeframe == '5m': periods_per_year = 365 * 24 * 12
        elif timeframe == '15m': periods_per_year = 365 * 24 * 4
        elif timeframe == '1h': periods_per_year = 365 * 24
        elif timeframe == '4h': periods_per_year = 365 * 6
        else: periods_per_year = 365 # 1d
        
        std = returns.std()
        if std > 0:
            sharpe_ratio = float((returns.mean() / std) * math.sqrt(periods_per_year))
        else:
            sharpe_ratio = 0.0
            
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std()
        if downside_std > 0:
            sortino_ratio = float((returns.mean() / downside_std) * math.sqrt(periods_per_year))
        else:
            sortino_ratio = 0.0
    else:
        max_drawdown_pct = 0.0
        max_drawdown_usd = 0.0
        sharpe_ratio = 0.0
        sortino_ratio = 0.0
        
    return {
        "initial_bank": initial_bank,
        "final_bank": final_bank,
        "net_profit": net_profit,
        "net_profit_pct": net_profit_pct,
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
        "sortino_ratio": sortino_ratio
    }

def print_bloomberg_report(metrics: Dict[str, Any], symbol: str, timeframe: str, strategy: str, period_str: str = ""):
    """
    Imprime un informe en la consola con estetica Bloomberg Terminal
    """
    W = 68
    sep = "=" * W
    subsep = "-" * W
    
    print("\n" + sep)
    print(f"  🏛  GATDSEQ INSTITUTIONAL QUANT LAB | BLOOMBERG TERMINAL AUDIT")
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
    print(f"    Gross Profits:          ${metrics['gross_profits']:>12,.2f} USD")
    print(f"    Gross Losses:           ${metrics['gross_losses']:>12,.2f} USD")
    
    print(subsep)
    print(f"  {amber}RISK & RETURN PROFILE{reset}")
    print(f"    Profit Factor:           {metrics['profit_factor']:>12.2f}")
    print(f"    Sharpe Ratio (Ann.):     {metrics['sharpe_ratio']:>12.2f}")
    print(f"    Sortino Ratio (Ann.):    {metrics['sortino_ratio']:>12.2f}")
    print(f"    Max Drawdown (MDD):      \033[91m-{metrics['max_drawdown_pct']:>11.2f}% (${metrics['max_drawdown_usd']:,.2f})\033[0m")
    
    print(subsep)
    print(f"  {amber}TRADE EXECUTION EFFICIENCY{reset}")
    print(f"    Total Events:            {metrics['total_trades']:>12d}")
    print(f"    Winning Trades:          {metrics['win_count']:>12d}")
    print(f"    Losing Trades:           {metrics['loss_count']:>12d}")
    print(f"    Win Rate:                {metrics['win_rate']:>11.1f}%")
    print(f"    Win / Loss Ratio:        {metrics['win_loss_ratio']:>12.2f}")
    print(f"    Average Win:            ${metrics['avg_win']:>12,.2f} USD")
    print(f"    Average Loss:           ${metrics['avg_loss']:>12,.2f} USD")
    print(f"    Expectancy / Trade:     ${metrics['expectancy']:>12,.2f} USD")
    print(sep + "\n")
