#!/usr/bin/env python3
"""
Tier 1 (Mac Worker) - Meta-Labeling L2 Training Pipeline
=========================================================
Entrena pesos L2 regularizados sobre trades historicos de 4 anos (Split 70% IS con
embargo temporal estricto) y los exporta con el StandardScaler absorbido en
`meta_model_weights.json` para inferencia O(1) en NumPy sobre Raspberry Pi 3B.
"""

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backtesting.analytics import aggregate_round_trip_trades
from backtesting.data_manager import load_dataset, load_funding_dataset
from backtesting.engine import BacktestEngine
from backtesting.indicators import inject_htf_confluence, prepare_market_indicators
from core.strategy import DEFAULT_BOT_PARAMS, extract_meta_features, predict_meta_probability

BASKET_12 = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
    "XRP/USDT", "ADA/USDT", "DOGE/USDT", "AVAX/USDT",
    "LINK/USDT", "LTC/USDT", "DOT/USDT", "UNI/USDT",
]


def _fit_l2_logistic_numpy(X: np.ndarray, y: np.ndarray, l2_lam: float = 2.0) -> tuple:
    """Regresion logistica L2 en NumPy puro con plegado de StandardScaler."""
    mu = X.mean(axis=0)
    sd = np.where(X.std(axis=0) > 1e-8, X.std(axis=0), 1.0)
    Xs = (X - mu) / sd

    w = np.zeros(Xs.shape[1], dtype=np.float64)
    b = 0.0
    lr = 0.1
    n_s = float(len(y))
    for _ in range(1500):
        logits = Xs @ w + b
        probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -20.0, 20.0)))
        err = probs - y
        grad_w = (Xs.T @ err) / n_s + (l2_lam / n_s) * w
        grad_b = float(np.mean(err))
        w -= lr * grad_w
        b -= lr * grad_b

    w_prime = w / sd
    b_prime = float(b - np.sum((w * mu) / sd))
    return w_prime, b_prime


def _collect_dataset(strategy: str, params: dict) -> pd.DataFrame:
    rows = []
    for sym in BASKET_12:
        df = prepare_market_indicators(load_dataset(sym, "1d", 1460))
        try:
            df4 = prepare_market_indicators(load_dataset(sym, "4h", 1460))
            df = inject_htf_confluence(df, df4, lookback_days=3)
        except Exception:
            pass
        f_df = load_funding_dataset(sym, 1460)
        try:
            w_df = prepare_market_indicators(load_dataset(sym, "1w", 1800))
        except Exception:
            w_df = None

        eng = BacktestEngine(sym, "1d", strategy, 10000.0, slippage_bps=5.0, params=params)
        res = eng.run(df, weekly_df=w_df, funding_df=f_df)
        rts = aggregate_round_trip_trades(res["trades"])
        raw_map = {}
        for t in res["trades"]:
            pid = t.get("parent_id", t.get("id"))
            if pid not in raw_map:
                raw_map[pid] = t

        work = df.copy()
        if f_df is not None and not f_df.empty:
            left = work.sort_values("datetime").copy()
            left["datetime"] = pd.to_datetime(left["datetime"]).astype("datetime64[ns]")
            right = f_df[["datetime", "fundingRate"]].sort_values("datetime").copy()
            right["datetime"] = pd.to_datetime(right["datetime"]).astype("datetime64[ns]")
            work = pd.merge_asof(left, right, on="datetime", direction="backward")
            work["funding_rate"] = work["fundingRate"].fillna(0.0001)
        else:
            work["funding_rate"] = 0.0001
        dt_to_idx = {pd.Timestamp(ts): idx for idx, ts in enumerate(work["datetime"])}

        for rt in rts:
            raw = raw_map.get(rt["parent_id"], {})
            entry_ts = pd.Timestamp(raw.get("entry_time"))
            exit_ts = pd.Timestamp(raw.get("exit_time"))
            i = dt_to_idx.get(entry_ts)
            if i is None or i < 2:
                continue
            closed = work.iloc[i - 1]
            action = raw.get("action", "BUY")
            reason = str(raw.get("model", raw.get("reason", "")))
            ema200 = float(closed["ema_200"]) if pd.notna(closed["ema_200"]) else float(closed["close"])
            htf = bool(closed.get("td9_4h_buy_recent", False)) if action == "BUY" else bool(closed.get("td9_4h_sell_recent", False))
            is_trend = ("REGIME_TREND" in reason) or ("(Trend)" in reason)
            feats = extract_meta_features(
                closed, action, ema200,
                funding_rate=float(closed.get("funding_rate", 0.0)),
                htf_4h_aligned=htf,
                is_trend_mode=is_trend,
            )
            rows.append({
                "entry_time": entry_ts,
                "exit_time": exit_ts,
                "pnl": float(rt["pnl"]),
                "win": 1.0 if float(rt["pnl"]) > 0 else 0.0,
                "f1": feats[0], "f2": feats[1], "f3": feats[2], "f4": feats[3], "f5": feats[4],
            })
    return pd.DataFrame(rows)


def main():
    output_path = os.path.join(REPO_ROOT, "meta_model_weights.json")
    # Entrenamos sin gate previo para obtener etiquetas limpias In-Sample
    base_params = dict(DEFAULT_BOT_PARAMS, use_hyb_meta_gate=False, use_meta_gate=False)

    payload = {
        "version": "v3.1-l2",
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    for strat, thresh in [("HYB", 0.55)]:
        tdf = _collect_dataset(strat, base_params).sort_values("entry_time").reset_index(drop=True)
        split_dt = tdf["entry_time"].quantile(0.70)
        is_df = tdf[(tdf["entry_time"] < split_dt) & (tdf["exit_time"] < split_dt)]
        oos_df = tdf[tdf["entry_time"] >= split_dt]

        X_is = is_df[["f1", "f2", "f3", "f4", "f5"]].values.astype(np.float64)
        y_is = is_df["win"].values.astype(np.float64)
        w_prime, b_prime = _fit_l2_logistic_numpy(X_is, y_is, l2_lam=2.0)

        entry = {
            "weights": [round(float(v), 6) for v in w_prime],
            "bias": round(float(b_prime), 6),
            "threshold": thresh,
            "is_samples": int(len(is_df)),
            "oos_samples": int(len(oos_df)),
        }
        payload[strat] = entry

        # Verificacion OOS
        X_oos = oos_df[["f1", "f2", "f3", "f4", "f5"]].values.astype(np.float64)
        kept = [oos_df.iloc[idx]["pnl"] for idx in range(len(oos_df)) if predict_meta_probability(X_oos[idx], entry)[1] > 0]
        wins = [p for p in kept if p > 0]
        losses = [abs(p) for p in kept if p < 0]
        pf = sum(wins) / sum(losses) if sum(losses) > 0 else 99.9
        wr = (len(wins) / len(kept) * 100.0) if kept else 0.0
        print(f"[{strat}] IS={len(is_df)} OOS={len(oos_df)} -> Gate p>={thresh}: N={len(kept)}, WR={wr:.1f}%, PF={pf:.2f}, Net=${sum(kept):.2f}")

    tmp = f"{output_path}.tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, output_path)
    print(f"Exportado: {output_path}")


if __name__ == "__main__":
    main()
