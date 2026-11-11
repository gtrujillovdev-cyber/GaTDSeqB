#!/usr/bin/env python3
"""
GaTDSEQ Quantitative Strategy Research & Ablation Lab
======================================================
Ejecuta experimentos por capas (Capa 0 -> Capa 1 -> Capa 2),
Rolling Walk-Forward, estres de slippage 2x y test de fragilidad Top-5%
sobre 3-4 anos de datos reales OHLCV + Funding Rate historico.
"""

import argparse
from typing import Any, Dict, List
from backtesting.data_manager import load_dataset, load_funding_dataset
from backtesting.indicators import prepare_market_indicators
from backtesting.research_lab import (
    check_go_nogo_gates,
    evaluate_basket,
    fragility_top5_removal,
    run_rolling_walk_forward_basket,
)

DEFAULT_BASKET = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "AVAX/USDT",
    "LINK/USDT",
    "LTC/USDT",
    "DOT/USDT",
    "UNI/USDT",
]


def build_experiments() -> List[Dict[str, Any]]:
    """Define las hipotesis ortogonales por capas (sin mezclar regimenes)."""
    return [
        # --- FAMILIA A: MEAN REVERSION / AGOTAMIENTO (TD9) ---
        {
            "name": "A0_TD9_NAKED (L0: SL2/TP3)",
            "strategy": "TD9_L0",
            "params": {
                "atr_sl_trend": 2.0,
                "atr_tp_trend": 3.0,
                "enable_breakeven": False,
                "enable_scale_out": False,
                "enable_trailing": False,
                "enable_dca_13": False,
                "enable_runner": False,
            },
        },
        {
            "name": "A1_TD9_RANGING (L1: ADX<=24)",
            "strategy": "TD9_MR",
            "params": {
                "adx_max": 24.0,
                "atr_sl_trend": 2.0,
                "atr_tp_trend": 3.0,
                "enable_breakeven": False,
                "enable_scale_out": False,
                "enable_trailing": False,
                "enable_dca_13": False,
                "enable_runner": False,
            },
        },
        {
            "name": "A2_TD9_RANGING+FUND (L2: ADX<=24 + Funding)",
            "strategy": "TD9_MR",
            "params": {
                "adx_max": 24.0,
                "require_funding_filter": True,
                "atr_sl_trend": 2.0,
                "atr_tp_trend": 3.0,
                "enable_breakeven": True,
                "be_threshold_atr": 1.25,
                "enable_scale_out": False,
                "enable_trailing": False,
                "enable_dca_13": False,
                "enable_runner": False,
            },
        },
        # --- FAMILIA B: TREND FOLLOWING / DONCHIAN BREAKOUT ---
        {
            "name": "B0_DONCHIAN_20_NAKED (L0: ChExit)",
            "strategy": "TREND_DC",
            "params": {
                "dc_period": 20,
                "adx_min": 0.0,
                "use_ema200_filter": False,
                "atr_sl_trend": 2.5,
                "atr_tp_trend": 25.0,
                "enable_breakeven": False,
                "enable_scale_out": False,
                "enable_trailing": True,
                "trailing_atr": 3.0,
                "enable_dca_13": False,
                "enable_runner": False,
                "enable_channel_exit": True,
            },
        },
        {
            "name": "B1_DONCHIAN_20_REGIME (L1: EMA200 + ADX>=20)",
            "strategy": "TREND_DC",
            "params": {
                "dc_period": 20,
                "adx_min": 20.0,
                "use_ema200_filter": True,
                "atr_sl_trend": 2.5,
                "atr_tp_trend": 25.0,
                "enable_breakeven": False,
                "enable_scale_out": False,
                "enable_trailing": True,
                "trailing_atr": 3.0,
                "enable_dca_13": False,
                "enable_runner": False,
                "enable_channel_exit": True,
            },
        },
        {
            "name": "B2_DONCHIAN_55_MACRO (L2: 55-bar + Trail 3.5 ATR)",
            "strategy": "TREND_DC",
            "params": {
                "dc_period": 55,
                "adx_min": 18.0,
                "use_ema200_filter": True,
                "atr_sl_trend": 3.0,
                "atr_tp_trend": 30.0,
                "enable_breakeven": False,
                "enable_scale_out": False,
                "enable_trailing": True,
                "trailing_atr": 3.5,
                "enable_dca_13": False,
                "enable_runner": False,
                "enable_channel_exit": True,
            },
        },
        # --- FAMILIA C: MOMENTUM EMA PULLBACK & FUNDING SQUEEZE ---
        {
            "name": "C1_EMA50_200_MOM (ADX>=22 + Trail 2.5)",
            "strategy": "TREND_EMA",
            "params": {
                "adx_min": 22.0,
                "atr_sl_trend": 2.0,
                "atr_tp_trend": 12.0,
                "enable_breakeven": True,
                "be_threshold_atr": 1.5,
                "enable_scale_out": False,
                "enable_trailing": True,
                "trailing_atr": 2.5,
                "enable_dca_13": False,
                "enable_runner": False,
            },
        },
        {
            "name": "D1_FUNDING_SQUEEZE (Contrarian Carry)",
            "strategy": "FUND_SQUEEZE",
            "params": {
                "funding_long_max": -0.0002,
                "funding_short_min": 0.0004,
                "atr_sl_trend": 2.0,
                "atr_tp_trend": 3.5,
                "enable_breakeven": True,
                "be_threshold_atr": 1.25,
                "enable_scale_out": False,
                "enable_trailing": False,
                "enable_dca_13": False,
                "enable_runner": False,
            },
        },
        # --- BENCHMARK ACTUAL GATDSEQ & REGIME DUAL ---
        {
            "name": "E1_REGIME_DUAL (MR ADX<=24 + DC55 Trend)",
            "strategy": "REGIME_DUAL",
            "params": {
                "adx_split": 24.0,
                "dc_period": 55,
                "mr_sl_atr": 2.0,
                "mr_tp_atr": 3.0,
                "trend_sl_atr": 3.0,
                "trend_tp_atr": 30.0,
                "trailing_atr": 3.5,
                "enable_breakeven": False,
                "enable_scale_out": False,
                "enable_dca_13": False,
                "enable_runner": False,
            },
        },
        {
            "name": "Z_CURRENT_HYB (Sistema Actual)",
            "strategy": "HYB",
            "params": {},
        },
    ]


def main():
    parser = argparse.ArgumentParser(description="GaTDSEQ Research & Ablation Lab")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_BASKET)
    parser.add_argument("--tf", type=str, default="4h", choices=["1h", "4h", "1d"])
    parser.add_argument("--days", type=int, default=1460)
    args = parser.parse_args()

    print("=" * 105)
    print(f"  🔬 GATDSEQ QUANT RESEARCH LAB | TF={args.tf} | HORIZONTE={args.days}d | CESTA={','.join(args.symbols)}")
    print("=" * 105)

    datasets = {}
    for sym in args.symbols:
        raw_df = load_dataset(symbol=sym, timeframe=args.tf, days=args.days)
        df = prepare_market_indicators(raw_df)
        f_df = load_funding_dataset(symbol=sym, days=args.days)
        datasets[sym] = (df, f_df)

    experiments = build_experiments()
    results = []

    print(f"\n{'Experimento':<42} | {'Tr':>4} | {'WR%':>5} | {'PF':>5} | {'NetPnL($)':>10} | {'P.Shp':>6} | {'P.Cal':>6} | {'P.MDD%':>6} | {'Z':>6}")
    print("-" * 108)

    for exp in experiments:
        res = evaluate_basket(datasets, args.tf, exp["strategy"], exp["params"], name=exp["name"])
        results.append((exp, res))
        print(
            f"{res['name']:<42} | {res['trades']:>4d} | {res['win_rate']:>5.1f} | "
            f"{res['profit_factor']:>5.2f} | {res['net_pnl']:>+10,.2f} | "
            f"{res['portfolio_sharpe']:>+6.2f} | {res['portfolio_calmar']:>+6.2f} | "
            f"-{res['portfolio_mdd_pct']:>5.1f} | {res['z_score']:>+6.2f}"
        )

    # Seleccionar el mejor candidato por Portfolio Sharpe / PF con >= 50 trades para Stress Testing
    viable = [item for item in results if item[1]["trades"] >= 50]
    if not viable:
        viable = results
    best_exp, best_res = max(viable, key=lambda x: (x[1]["portfolio_sharpe"], x[1]["profit_factor"]))

    print("\n" + "=" * 105)
    print(f"  🧪 DEEP AUDIT AL MEJOR CANDIDATO: {best_res['name']}")
    print("=" * 105)

    # Rolling Walk-Forward con grilla vecina (Meseta adaptada a la familia)
    strat = best_exp["strategy"]
    base_p = dict(best_exp["params"])
    grid = []
    if strat in ("TD9_L0", "TD9_MR"):
        for sl_m in [1.5, 2.0, 2.5]:
            for tp_m in [2.5, 3.0, 3.5]:
                p = dict(base_p)
                p["atr_sl_trend"] = sl_m
                p["atr_tp_trend"] = tp_m
                grid.append(p)
    elif strat == "REGIME_DUAL":
        for adx_s in [22.0, 24.0, 26.0]:
            for tr_m in [3.0, 3.5, 4.0]:
                p = dict(base_p)
                p["adx_split"] = adx_s
                p["trailing_atr"] = tr_m
                grid.append(p)
    else:
        for sl_m in [2.0, 2.5, 3.0]:
            for tr_m in [2.5, 3.0, 3.5]:
                p = dict(base_p)
                p["atr_sl_trend"] = sl_m
                p["trailing_atr"] = tr_m
                grid.append(p)

    wf = run_rolling_walk_forward_basket(datasets, args.tf, strat, grid, train_days=365, test_days=90)
    frag = fragility_top5_removal(wf["oos_round_trips"] if wf["oos_round_trips"] else best_res["round_trips"])
    slip2x = evaluate_basket(datasets, args.tf, strat, base_p, slippage_bps=10.0)
    verdict = check_go_nogo_gates(best_res, wf, frag, slip2x)

    print(f"  Rolling Walk-Forward ({wf['windows']} ventanas OOS): Trades={wf['oos_trades']} | WR={wf['oos_win_rate']:.1f}% | PF={wf['oos_profit_factor']:.2f} | OOS PnL=${wf['oos_net_pnl']:+,.2f} | Z={wf['oos_z_score']:+.2f} (p={wf['oos_p_value']:.4f})")
    print(f"  Fragilidad (sin Top 5% mejores = -{frag['removed_top']} trades): Rem={frag['remaining_trades']} | PF={frag['profit_factor']:.2f} | PnL=${frag['net_pnl']:+,.2f} | Sobrevive={frag['survived']}")
    print(f"  Estres Slippage 2x (10 bps): PF={slip2x['profit_factor']:.2f} | Net PnL=${slip2x['net_pnl']:+,.2f} | Sharpe={slip2x['avg_sharpe']:+.2f}")
    print("\n  GO / NO-GO GATES:")
    for gate, ok in verdict["gates"].items():
        print(f"    - {gate:<28}: {'✅ PASS' if ok else '❌ FAIL'}")
    print(f"\n  VEREDICTO FINAL: {'🟢 APROBADA PARA SHADOW/MICRO-CAPITAL' if verdict['passed_all'] else '🔴 NO APTA PARA CAPITAL REAL'}")
    print("=" * 105 + "\n")


if __name__ == "__main__":
    main()
