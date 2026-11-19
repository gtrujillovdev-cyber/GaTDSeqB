import json
import os
import tempfile
import unittest

import numpy as np
import pandas as pd

import bot
import server
from backtesting.research_lab import check_go_nogo_gates, compute_deflated_sharpe_ratio
from core.indicators import calculate_regime_indicators, prepare_market_indicators
from core.strategy import (
    DEFAULT_BOT_PARAMS,
    compute_portfolio_dampening,
    compute_rolling_corr_and_vol,
    evaluate_hyb_meta_gate,
    evaluate_orthogonal_signal,
    extract_meta_features,
    get_base_risk,
    predict_meta_probability,
)


class TestV3QuantModules(unittest.TestCase):
    def test_continuous_regime_indicators_and_causality(self):
        """KER, VR y p_trend deben distinguir tendencia vs rango sin look-ahead bias."""
        n = 120
        trend_close = pd.Series(np.linspace(100.0, 220.0, n))
        rng = np.random.default_rng(42)
        chop_close = pd.Series(100.0 + np.sin(np.arange(n) * 1.4) * 3.0 + rng.normal(0.0, 0.2, n))

        ker_t, _, pt_t = calculate_regime_indicators(trend_close)
        ker_c, _, pt_c = calculate_regime_indicators(chop_close)

        self.assertGreater(float(ker_t.iloc[-1]), 0.85)
        self.assertGreater(float(pt_t.iloc[-1]), 0.70)
        self.assertLess(float(ker_c.iloc[-1]), 0.45)
        self.assertLess(float(pt_c.iloc[-1]), 0.50)

        # Cero look-ahead: modificar barras futuras no debe alterar p_trend previo
        modified = chop_close.copy()
        modified.iloc[-10:] = np.linspace(100.0, 500.0, 10)
        _, _, pt_mod = calculate_regime_indicators(modified)
        self.assertAlmostEqual(float(pt_c.iloc[-11]), float(pt_mod.iloc[-11]), places=12)

    def test_continuous_regime_orthogonal_signal_and_hysteresis(self):
        """MR exige conjuncion ADX<=24 y p_trend<=0.45; DUAL aplica filtro neutro en p_trend>0.45 con ADX<=24."""
        c2 = pd.Series({"close": 100.0, "high": 102.0, "low": 98.0})
        closed_mr = pd.Series(
            {"close": 105.0, "td_count": -9, "td_perfected": True, "p_trend": 0.25, "dc_high_55": 110.0, "dc_low_55": 90.0}
        )
        # Con ADX<=24 y p_trend<=0.45 -> entra MR con TP 2.4 ATR
        sig_mr = evaluate_orthogonal_signal("MR", closed_mr, c2, 18.0, 100.0, DEFAULT_BOT_PARAMS)
        self.assertIsNotNone(sig_mr)
        self.assertEqual(sig_mr["mode"], "REGIME_MR")
        self.assertAlmostEqual(sig_mr["tp_mult"], 2.4, places=2)
        self.assertGreater(sig_mr["regime_scale"], 0.8)

        # Con ADX>24 -> el crash-guard bloquea MR aunque p_trend sea bajo
        self.assertIsNone(evaluate_orthogonal_signal("MR", closed_mr, c2, 30.0, 100.0, DEFAULT_BOT_PARAMS))

        closed_neutral_unperf = pd.Series(
            {"close": 105.0, "td_count": -9, "td_perfected": False, "p_trend": 0.50, "dc_high_55": 110.0, "dc_low_55": 90.0}
        )
        self.assertIsNone(evaluate_orthogonal_signal("DUAL", closed_neutral_unperf, c2, 20.0, 100.0, DEFAULT_BOT_PARAMS))

        closed_trend = pd.Series(
            {"close": 115.0, "td_count": 3, "td_perfected": False, "p_trend": 0.78, "dc_high_55": 110.0, "dc_low_55": 90.0}
        )
        sig_tr = evaluate_orthogonal_signal("DUAL", closed_trend, c2, 28.0, 100.0, DEFAULT_BOT_PARAMS)
        self.assertIsNotNone(sig_tr)
        self.assertEqual(sig_tr["mode"], "REGIME_TREND")
        self.assertEqual(sig_tr["action"], "BUY")

        # Verificar SSOT evaluate_hyb_meta_gate
        bad_w = {"weights": [0.0, 0.0, 0.0, 0.0, 0.0], "bias": -2.0, "threshold": 0.55}
        ok_pass, _, mult_pass = evaluate_hyb_meta_gate(closed_mr, "BUY", 100.0, 0.0, False, False, DEFAULT_BOT_PARAMS, None)
        self.assertTrue(ok_pass)
        self.assertEqual(mult_pass, 1.0)
        ok_blk, _, mult_blk = evaluate_hyb_meta_gate(closed_mr, "BUY", 100.0, 0.0, False, False, DEFAULT_BOT_PARAMS, bad_w)
        self.assertFalse(ok_blk)
        self.assertEqual(mult_blk, 0.0)

    def test_meta_labeling_inference_and_gate(self):
        """Meta-Labeling L2 debe filtrar senales de baja probabilidad y escalar las de alta."""
        c2 = pd.Series({"close": 100.0, "high": 102.0, "low": 98.0})
        candle = pd.Series(
            {
                "close": 105.0,
                "atr": 2.0,
                "volume": 200.0,
                "volume_sma": 100.0,
                "td_count": -9,
                "td_perfected": True,
                "p_trend": 0.20,
                "dc_high_55": 110.0,
                "dc_low_55": 90.0,
            }
        )
        feats_good = extract_meta_features(candle, "BUY", 100.0, funding_rate=-0.0005, htf_4h_aligned=True, is_trend_mode=False)
        self.assertEqual(feats_good.shape, (5,))

        weights = {"weights": [0.8, 1.2, 0.5, 0.2, 0.3], "bias": -0.8, "threshold": 0.55}
        prob_good, mult_good = predict_meta_probability(feats_good, weights)
        self.assertGreater(prob_good, 0.55)
        self.assertGreater(mult_good, 0.25)

        params_gated = dict(DEFAULT_BOT_PARAMS, use_meta_gate=True)
        sig_pass = evaluate_orthogonal_signal(
            "MR", candle, c2, 18.0, 100.0, params_gated, funding_rate=-0.0005, htf_4h_aligned=True, meta_weights=weights
        )
        self.assertIsNotNone(sig_pass)
        self.assertGreater(sig_pass["meta_prob"], 0.55)

        bad_weights = {"weights": [0.0, 0.0, 0.0, 0.0, 0.0], "bias": -2.0, "threshold": 0.55}
        sig_reject = evaluate_orthogonal_signal(
            "MR", candle, c2, 18.0, 100.0, params_gated, meta_weights=bad_weights
        )
        self.assertIsNone(sig_reject)

    def test_v4_monotonic_soft_sizing_and_dual_or_conjunction(self):
        """Soft-Sizing debe ser monotono creciente en [0.65..1.25] y DUAL debe activar Trend con p_trend>=0.55."""
        c2 = pd.Series({"close": 100.0, "high": 102.0, "low": 98.0})
        base_candle = {
            "close": 115.0,
            "atr": 2.0,
            "volume": 100.0,
            "volume_sma": 100.0,
            "td_count": 3,
            "td_perfected": False,
            "dc_high_55": 110.0,
            "dc_low_55": 90.0,
        }
        # Con ADX <= 24 pero p_trend >= 0.55, DUAL debe entrar en modo tendencial (OR-gate)
        sig_or = evaluate_orthogonal_signal(
            "DUAL", pd.Series(dict(base_candle, p_trend=0.60)), c2, 18.0, 100.0, DEFAULT_BOT_PARAMS
        )
        self.assertIsNotNone(sig_or)
        self.assertEqual(sig_or["mode"], "REGIME_TREND")

        # Monotonicidad estricta en evaluate_hyb_meta_gate sobre [0.20 .. 0.85]
        w_mono = {"weights": [1.0, 0.0, 0.0, 0.0, 0.0], "bias": -0.5, "soft_floor": 0.20, "soft_ceil": 0.85}
        mults = []
        for pt in [0.95, 0.70, 0.50, 0.30, 0.05]:  # f1 = 1 - pt en counter-trend -> prob crece
            c_m = pd.Series(dict(base_candle, p_trend=pt))
            ok, prob, mult = evaluate_hyb_meta_gate(c_m, "BUY", 120.0, 0.0, False, True, DEFAULT_BOT_PARAMS, w_mono)
            self.assertTrue(ok)
            mults.append((prob, mult))
        for (p_lo, m_lo), (p_hi, m_hi) in zip(mults, mults[1:]):
            self.assertLess(p_lo, p_hi)
            self.assertLessEqual(m_lo, m_hi)
            self.assertGreaterEqual(m_lo, 0.65)
            self.assertLessEqual(m_hi, 1.25)

    def test_portfolio_correlation_dampening_and_vol_parity(self):
        """Correlacion positiva en misma direccion amortigua riesgo; coberturas opuestas no se penalizan."""
        self.assertLess(get_base_risk("HYPE", "1d", realized_vol_30d=0.06), get_base_risk("BTC", "1d", realized_vol_30d=0.025))

        rng = np.random.default_rng(7)
        base_ret = rng.normal(0.0, 0.02, 40)
        btc_df = pd.DataFrame({"close": 50000.0 * np.exp(np.cumsum(base_ret))})
        eth_df = pd.DataFrame({"close": 3000.0 * np.exp(np.cumsum(base_ret * 1.1 + rng.normal(0, 0.003, 40)))})
        corr_mat, vols = compute_rolling_corr_and_vol({"BTC": btc_df, "ETH": eth_df}, window=30)
        self.assertGreater(corr_mat[("BTC", "ETH")], 0.80)
        self.assertIn("BTC", vols)

        active_long_btc = [{"symbol": "BTC", "position": "BUY", "risk_pct": 0.02}]
        damp_same_dir = compute_portfolio_dampening("ETH", "BUY", 0.02, active_long_btc, corr_matrix=corr_mat)
        damp_hedge = compute_portfolio_dampening("ETH", "SELL", 0.02, active_long_btc, corr_matrix=corr_mat)
        self.assertLess(damp_same_dir, 0.85)
        self.assertAlmostEqual(damp_hedge, 1.0, places=4)

    def test_deflated_sharpe_ratio_and_kiosk_risk_endpoint(self):
        """DSR debe penalizar ensayos multiples y server.get_fleet_risk debe leer snapshot atomico."""
        rng = np.random.default_rng(123)
        flat_rets = rng.normal(0.0001, 0.02, 400).tolist()
        strong_rets = rng.normal(0.004, 0.015, 400).tolist()

        dsr_noise = compute_deflated_sharpe_ratio(flat_rets, n_trials=20)
        dsr_alpha = compute_deflated_sharpe_ratio(strong_rets, n_trials=20)
        self.assertFalse(dsr_noise["passed"])
        self.assertTrue(dsr_alpha["passed"])

        gates = check_go_nogo_gates(
            {"trades": 120, "portfolio_sharpe": 1.6, "portfolio_calmar": 1.4},
            {"oos_trades": 120, "oos_profit_factor": 1.6, "oos_z_score": 2.8, "oos_p_value": 0.002},
            {"survived": True},
            {"net_pnl": 500.0, "profit_factor": 1.25},
            dsr_res=dsr_noise,
        )
        self.assertFalse(gates["passed_all"])
        self.assertFalse(gates["gates"]["dsr_>=_0.95"])

        with tempfile.TemporaryDirectory() as tmpdir:
            risk_path = os.path.join(tmpdir, "fleet_risk.json")
            bot.save_fleet_risk_snapshot(
                {("BTC", "ETH"): 0.84, ("BTC", "HYPE"): 0.52, ("ETH", "HYPE"): 0.48},
                {"BTC": 0.025, "ETH": 0.032, "HYPE": 0.055},
                {"active_positions": [{"symbol": "BTC", "position": "BUY", "risk_pct": 0.02}]},
                meta_active=False,
                filepath=risk_path,
            )
            loaded = server.get_fleet_risk(base_dir=tmpdir)
            self.assertAlmostEqual(loaded["corr_btc_eth"], 0.84, places=2)
            self.assertGreater(loaded["fleet_sigma_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
