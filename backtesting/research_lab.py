import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from .analytics import aggregate_round_trip_trades, compute_metrics, compute_monte_carlo_edge
from .engine import BacktestEngine


def _slice_by_date(df: pd.DataFrame, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> pd.DataFrame:
    return df[(df["datetime"] >= start_dt) & (df["datetime"] < end_dt)].reset_index(drop=True)


def run_single_asset_eval(
    df: pd.DataFrame,
    funding_df: Optional[pd.DataFrame],
    symbol: str,
    timeframe: str,
    strategy: str,
    params: Dict[str, Any],
    initial_bank: float = 10000.0,
    slippage_bps: float = 5.0,
) -> Dict[str, Any]:
    engine = BacktestEngine(
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy,
        initial_bank=initial_bank,
        slippage_bps=slippage_bps,
        params=params,
    )
    res = engine.run(df, funding_df=funding_df)
    m = compute_metrics(initial_bank, res["final_bank"], res["trades"], res["equity_curve"], timeframe)
    rt = aggregate_round_trip_trades(res["trades"])
    return {"metrics": m, "round_trips": rt, "equity_curve": res["equity_curve"], "raw_trades": res["trades"]}


def evaluate_basket(
    datasets: Dict[str, Tuple[pd.DataFrame, Optional[pd.DataFrame]]],
    timeframe: str,
    strategy: str,
    params: Dict[str, Any],
    name: str = "",
    initial_bank: float = 10000.0,
    slippage_bps: float = 5.0,
) -> Dict[str, Any]:
    """Evalua una estrategia en una cesta multi-activo con funding historico real y curva de cartera agregada."""
    all_rts: List[Dict[str, Any]] = []
    per_asset: Dict[str, Dict[str, Any]] = {}
    sharpes: List[float] = []
    calmars: List[float] = []
    mdds: List[float] = []
    bhs: List[float] = []
    total_net = 0.0
    pnl_curves: List[pd.Series] = []

    for sym, (df, f_df) in datasets.items():
        out = run_single_asset_eval(df, f_df, sym, timeframe, strategy, params, initial_bank, slippage_bps)
        m = out["metrics"]
        per_asset[sym] = m
        for idx, rt in enumerate(out["round_trips"]):
            rt_copy = dict(rt)
            rt_copy["parent_id"] = f"{sym}_{idx}_{rt.get('parent_id', idx)}"
            all_rts.append(rt_copy)
        sharpes.append(m["sharpe_ratio"])
        calmars.append(m["calmar_ratio"])
        mdds.append(m["max_drawdown_pct"])
        bhs.append(m["bh_return_pct"])
        total_net += m["net_profit"]
        eq_df = out["equity_curve"]
        if not eq_df.empty and "timestamp" in eq_df.columns:
            s = eq_df.set_index("timestamp")["equity"] - initial_bank
            s.name = sym
            pnl_curves.append(s)

    total_initial = initial_bank * len(datasets)
    roi_pct = (total_net / total_initial) * 100.0 if total_initial > 0 else 0.0
    pnls = [float(t["pnl"]) for t in all_rts]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    gross_p = float(sum(wins))
    gross_l = float(abs(sum(losses)))
    pf = (gross_p / gross_l) if gross_l > 0 else (99.9 if gross_p > 0 else 0.0)
    wr = (len(wins) / len(pnls) * 100.0) if pnls else 0.0
    mc = compute_monte_carlo_edge(all_rts)

    # Curva agregada de cartera (capital combinado real)
    portfolio_sharpe = 0.0
    portfolio_calmar = 0.0
    portfolio_mdd_pct = 0.0
    if pnl_curves:
        port_df = pd.concat(pnl_curves, axis=1).ffill().fillna(0.0)
        port_eq = total_initial + port_df.sum(axis=1)
        cummax = port_eq.cummax()
        dd = (port_eq - cummax) / cummax.replace(0, np.nan)
        portfolio_mdd_pct = abs(float(dd.min())) * 100.0 if not dd.dropna().empty else 0.0
        rets = port_eq.pct_change().dropna()
        periods_map = {"1h": 365 * 24, "4h": 365 * 6, "1d": 365, "1w": 52}
        ppy = periods_map.get(timeframe, 365)
        std = rets.std()
        if std > 0:
            portfolio_sharpe = float((rets.mean() / std) * math.sqrt(ppy))
        years = max(1e-6, len(port_eq) / ppy)
        if total_initial > 0 and port_eq.iloc[-1] > 0 and portfolio_mdd_pct > 0:
            cagr_pct = (((port_eq.iloc[-1] / total_initial) ** (1.0 / years)) - 1.0) * 100.0
            portfolio_calmar = float(cagr_pct / portfolio_mdd_pct)

    return {
        "name": name or strategy,
        "strategy": strategy,
        "timeframe": timeframe,
        "trades": len(all_rts),
        "win_rate": wr,
        "profit_factor": pf,
        "net_pnl": total_net,
        "roi_pct": roi_pct,
        "avg_sharpe": float(np.mean(sharpes)) if sharpes else 0.0,
        "avg_calmar": float(np.mean(calmars)) if calmars else 0.0,
        "portfolio_sharpe": portfolio_sharpe,
        "portfolio_calmar": portfolio_calmar,
        "portfolio_mdd_pct": portfolio_mdd_pct,
        "max_dd_pct": float(max(mdds)) if mdds else 0.0,
        "avg_bh_pct": float(np.mean(bhs)) if bhs else 0.0,
        "z_score": mc["z_score"],
        "p_value": mc["p_value"],
        "is_significant": mc["is_significant"],
        "avg_mfe_r": mc["avg_mfe_r"],
        "avg_mae_r": mc["avg_mae_r"],
        "round_trips": all_rts,
        "per_asset": per_asset,
    }


def run_rolling_walk_forward_basket(
    datasets: Dict[str, Tuple[pd.DataFrame, Optional[pd.DataFrame]]],
    timeframe: str,
    strategy: str,
    param_grid_list: List[Dict[str, Any]],
    train_days: int = 365,
    test_days: int = 90,
    initial_bank: float = 10000.0,
    slippage_bps: float = 5.0,
) -> Dict[str, Any]:
    """
    Rolling Walk-Forward sobre cesta multi-activo:
    Entrena en ventanas de train_days -> elige mejor config con >= 20 trades -> evalua en test_days OOS.
    Concatena todos los trades Out-of-Sample.
    """
    # Determinar rango comun de fechas
    min_dt = max(df["datetime"].min() for df, _ in datasets.values())
    max_dt = min(df["datetime"].max() for df, _ in datasets.values())

    cursor = min_dt + pd.Timedelta(days=train_days)
    oos_rts: List[Dict[str, Any]] = []
    windows = []
    chosen_history = []

    while cursor + pd.Timedelta(days=30) <= max_dt:
        train_start = cursor - pd.Timedelta(days=train_days)
        test_end = min(max_dt, cursor + pd.Timedelta(days=test_days))

        # 1. Seleccionar mejores parametros en IS (train_start -> cursor)
        best_cfg = param_grid_list[0]
        best_score = -999.0
        for cfg in param_grid_list:
            is_ds = {}
            for sym, (df, f_df) in datasets.items():
                sub = _slice_by_date(df, train_start, cursor)
                if len(sub) > 220:
                    is_ds[sym] = (sub, f_df)
            if not is_ds:
                continue
            res = evaluate_basket(is_ds, timeframe, strategy, cfg, initial_bank=initial_bank, slippage_bps=slippage_bps)
            if res["trades"] >= 20 and res["avg_sharpe"] > best_score:
                best_score = res["avg_sharpe"]
                best_cfg = cfg

        chosen_history.append(best_cfg)

        # 2. Evaluar OOS (cursor -> test_end, incluyendo 220 velas previas como warmup)
        oos_net = 0.0
        win_trades = 0
        for sym, (df, f_df) in datasets.items():
            full_sub = df[df["datetime"] < test_end].reset_index(drop=True)
            eval_mask = full_sub["datetime"] >= cursor
            if not eval_mask.any():
                continue
            eval_idx = int(eval_mask.idxmax())
            if eval_idx < 200:
                continue
            eng = BacktestEngine(
                symbol=sym,
                timeframe=timeframe,
                strategy=strategy,
                initial_bank=initial_bank,
                slippage_bps=slippage_bps,
                params=best_cfg,
            )
            r = eng.run(full_sub, eval_start_idx=eval_idx, funding_df=f_df)
            rts = aggregate_round_trip_trades(r["trades"])
            for idx, rt in enumerate(rts):
                rt_copy = dict(rt)
                rt_copy["parent_id"] = f"{cursor.strftime('%Y%m%d')}_{sym}_{idx}"
                oos_rts.append(rt_copy)
            oos_net += (r["final_bank"] - initial_bank)
            win_trades += len(rts)

        windows.append({"start": cursor.strftime("%Y-%m-%d"), "end": test_end.strftime("%Y-%m-%d"), "trades": win_trades, "net_pnl": oos_net})
        cursor += pd.Timedelta(days=test_days)

    pnls = [float(t["pnl"]) for t in oos_rts]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_p = float(sum(wins))
    gross_l = float(abs(sum(losses)))
    pf = (gross_p / gross_l) if gross_l > 0 else (99.9 if gross_p > 0 else 0.0)
    wr = (len(wins) / len(pnls) * 100.0) if pnls else 0.0
    mc = compute_monte_carlo_edge(oos_rts)

    return {
        "windows": len(windows),
        "window_details": windows,
        "oos_trades": len(oos_rts),
        "oos_win_rate": wr,
        "oos_profit_factor": pf,
        "oos_net_pnl": float(sum(pnls)),
        "oos_z_score": mc["z_score"],
        "oos_p_value": mc["p_value"],
        "oos_significant": mc["is_significant"],
        "oos_round_trips": oos_rts,
        "chosen_configs": chosen_history,
    }


def fragility_top5_removal(round_trips: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Elimina el mejor 5% de los trades ganadores para detectar dependencia de outliers."""
    if not round_trips:
        return {"remaining_trades": 0, "net_pnl": 0.0, "profit_factor": 0.0, "survived": False}

    pnls = sorted([float(t["pnl"]) for t in round_trips], reverse=True)
    n_remove = max(1, math.ceil(len(pnls) * 0.05))
    trimmed = pnls[n_remove:]
    wins = [p for p in trimmed if p > 0]
    losses = [p for p in trimmed if p < 0]
    gp = float(sum(wins))
    gl = float(abs(sum(losses)))
    pf = (gp / gl) if gl > 0 else (99.9 if gp > 0 else 0.0)
    net = float(sum(trimmed))
    return {
        "removed_top": n_remove,
        "remaining_trades": len(trimmed),
        "net_pnl": net,
        "profit_factor": pf,
        "survived": (net > 0 and pf >= 1.0),
    }


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Acklam's inverse normal CDF approximation (pure math, accuracy ~1e-9)."""
    p = max(1e-12, min(1.0 - 1e-12, float(p)))
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00)
    plow, phigh = 0.02425, 1.0 - 0.02425
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1.0)
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1.0)
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1.0)


def compute_deflated_sharpe_ratio(
    returns: List[float],
    n_trials: int = 1,
    trial_sharpes_var: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calcula el Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014) corrigiendo
    asimetria, curtosis y sesgo de seleccion por multiples pruebas (N trials).
    """
    arr = np.asarray(returns, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    t_len = len(arr)
    if t_len < 10:
        return {"dsr": 0.0, "sr_obs": 0.0, "sr_star": 0.0, "passed": False}

    mu = float(np.mean(arr))
    sd = float(np.std(arr, ddof=1))
    if sd <= 1e-12:
        return {"dsr": 0.0, "sr_obs": 0.0, "sr_star": 0.0, "passed": False}

    sr_obs = mu / sd
    centered = (arr - mu) / sd
    skew = float(np.mean(centered ** 3))
    kurt = float(np.mean(centered ** 4))  # Curtosis de Pearson (Normal = 3.0)

    if n_trials <= 1:
        sr_star = 0.0
    else:
        euler_gamma = 0.5772156649
        v_sr = float(trial_sharpes_var) if (trial_sharpes_var is not None and trial_sharpes_var > 0) else (1.0 / max(1, t_len - 1))
        z1 = _norm_ppf(1.0 - 1.0 / float(n_trials))
        z2 = _norm_ppf(1.0 - 1.0 / (float(n_trials) * math.e))
        sr_star = math.sqrt(v_sr) * ((1.0 - euler_gamma) * z1 + euler_gamma * z2)

    denom_sq = max(1e-12, 1.0 - skew * sr_obs + ((kurt - 1.0) / 4.0) * (sr_obs ** 2))
    z_stat = ((sr_obs - sr_star) * math.sqrt(max(1, t_len - 1))) / math.sqrt(denom_sq)
    dsr = _norm_cdf(z_stat)
    return {
        "dsr": round(dsr, 4),
        "sr_obs": round(sr_obs, 4),
        "sr_star": round(sr_star, 4),
        "skew": round(skew, 4),
        "kurtosis": round(kurt, 4),
        "passed": dsr >= 0.95,
    }


def check_go_nogo_gates(
    basket_res: Dict[str, Any],
    wf_res: Dict[str, Any],
    frag_res: Dict[str, Any],
    slip2x_res: Dict[str, Any],
    dsr_res: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Aplica los criterios estrictos institucionales antes de pasar a dinero real."""
    eff_sharpe = max(basket_res.get("portfolio_sharpe", 0.0), basket_res.get("avg_sharpe", 0.0))
    eff_calmar = max(basket_res.get("portfolio_calmar", 0.0), basket_res.get("avg_calmar", 0.0))
    gates = {
        "sample_>=_100": wf_res["oos_trades"] >= 100 or basket_res["trades"] >= 100,
        "oos_pf_>=_1.30": wf_res["oos_profit_factor"] >= 1.30,
        "sharpe_>=_1.20": eff_sharpe >= 1.20,
        "calmar_>=_1.00": eff_calmar >= 1.00,
        "monte_carlo_z_>=_2.50": wf_res["oos_z_score"] >= 2.50 and wf_res["oos_p_value"] <= 0.01,
        "fragility_top5_survived": frag_res["survived"],
        "slippage_2x_positive": slip2x_res["net_pnl"] > 0 and slip2x_res["profit_factor"] >= 1.05,
    }
    if dsr_res is not None:
        gates["dsr_>=_0.95"] = bool(dsr_res.get("passed", False))
    passed = all(gates.values())
    return {"passed_all": passed, "gates": gates}
