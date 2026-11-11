from typing import Any, Dict, List


def aggregate_trade_ledger(trades_list: List[Dict[str, Any]], initial_bank: float = 10000.0) -> Dict[str, Any]:
    """
    Calcula metricas del ledger de produccion agrupando cierres parciales (_partial, _tp2)
    con su cierre final (_close) e ignorando filas de apertura ('Apertura') en win rate.
    """
    recent = trades_list[-5:]
    peak = initial_bank
    current = initial_bank
    max_dd = 0.0
    gross_profit = 0.0
    gross_loss = 0.0
    grouped_pnl: Dict[str, float] = {}

    for trade in trades_list:
        t_type = str(trade.get("type", ""))
        if "Apertura" in t_type:
            continue
        if "pnl" not in trade:
            continue

        pnl = float(trade["pnl"])
        current += pnl
        if pnl > 0:
            gross_profit += pnl
        elif pnl < 0:
            gross_loss += abs(pnl)

        if current > peak:
            peak = current
        if peak > 0:
            dd = ((peak - current) / peak) * 100.0
            if dd > max_dd:
                max_dd = dd

        raw_id = str(trade.get("trade_id", ""))
        base_id = raw_id.replace("_partial", "").replace("_tp2", "").replace("_close", "")
        if not base_id:
            base_id = f"_idx_{len(grouped_pnl)}"
        grouped_pnl[base_id] = grouped_pnl.get(base_id, 0.0) + pnl

    closed_positions = len(grouped_pnl)
    wins = sum(1 for p in grouped_pnl.values() if p > 0)
    win_rate = (wins / closed_positions * 100.0) if closed_positions > 0 else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

    return {
        "recent_trades": recent,
        "trades_count": closed_positions,
        "wins_count": wins,
        "bank": current,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "drawdown": max_dd,
    }
