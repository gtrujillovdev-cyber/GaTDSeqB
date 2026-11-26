import json
import os
import tempfile
import unittest

import pandas as pd

from core.strategy import (
    FLEET_ASSETS,
    FLEET_STRATEGIES,
    FLEET_TIMEFRAMES,
    MAX_RISK_COUNTER,
    MAX_RISK_TREND,
    cap_trade_risk,
    check_td_signal,
    compute_conviction_boost,
    evaluate_orthogonal_signal,
    is_bot_calibrated,
)


class TestV5QuantRestructuring(unittest.TestCase):
    def test_fleet_ssot_v5(self):
        self.assertEqual(FLEET_ASSETS, ["BTC", "ETH", "SOL", "BNB", "AVAX"])
        self.assertEqual(FLEET_TIMEFRAMES, ["1d"])
        self.assertEqual(FLEET_STRATEGIES, ["TREND"])
        self.assertNotIn("HYPE", FLEET_ASSETS)

    def test_check_td_signal_no_falling_knife_spam(self):
        c2 = pd.Series({"close": 100.0, "high": 102.0, "low": 98.0})
        # Falling knife at td_count=-11 with td_perf=True but no price flip -> MUST NOT trigger
        c_fall = pd.Series({"close": 90.0, "high": 95.0, "low": 88.0, "td_count": -11, "td_perfected": True})
        td_buy, td_sell = check_td_signal(c_fall, c2)
        self.assertFalse(td_buy)
        self.assertFalse(td_sell)

        # Exact TD -9 perfected -> triggers
        c_9 = pd.Series({"close": 90.0, "high": 95.0, "low": 88.0, "td_count": -9, "td_perfected": True})
        td_buy, _ = check_td_signal(c_9, c2)
        self.assertTrue(td_buy)

        # TD -11 with genuine price flip above c2 close -> triggers
        c_flip = pd.Series({"close": 101.0, "high": 102.0, "low": 95.0, "td_count": -11, "td_perfected": False})
        td_buy, _ = check_td_signal(c_flip, c2)
        self.assertTrue(td_buy)

    def test_conviction_boost_and_hard_risk_caps(self):
        # Counter-trend must NEVER amplify risk (reduced to 0.5x)
        self.assertEqual(compute_conviction_boost("BTC", 0.90, is_counter_trend=True), 0.5)
        self.assertEqual(compute_conviction_boost("ETH", 0.85, is_counter_trend=True), 0.5)
        # Trend-aligned capped at 1.25x
        self.assertEqual(compute_conviction_boost("BTC", 0.85, is_counter_trend=False), 1.25)
        # Hard risk caps
        self.assertAlmostEqual(cap_trade_risk(0.05, is_counter_trend=False), MAX_RISK_TREND)
        self.assertAlmostEqual(cap_trade_risk(0.05, is_counter_trend=True), MAX_RISK_COUNTER)

    def test_trend_sleeve_pure_donchian_breakout(self):
        c2 = pd.Series({"close": 95.0, "high": 96.0, "low": 94.0})
        params = {"dc_period": 55, "adx_min": 18.0, "atr_sl_trend": 1.5, "atr_tp_trend": 3.5, "use_meta_gate": False}

        # Bullish breakout above DC55 & EMA200
        c_buy = pd.Series({"close": 110.0, "dc_high_55": 105.0, "dc_low_55": 80.0, "p_trend": 0.65, "td_count": -9, "td_perfected": True})
        sig = evaluate_orthogonal_signal("TREND", c_buy, c2, adx_val=25.0, ema200=90.0, params=params)
        self.assertIsNotNone(sig)
        self.assertEqual(sig["action"], "BUY")
        self.assertEqual(sig["mode"], "REGIME_TREND")
        self.assertFalse(sig["is_counter_trend"])

        # Bearish regime with TD -9 perfected -> TREND must NOT open a counter-trend MR long!
        c_mr = pd.Series({"close": 75.0, "dc_high_55": 105.0, "dc_low_55": 70.0, "p_trend": 0.30, "td_count": -9, "td_perfected": True})
        sig_none = evaluate_orthogonal_signal("TREND", c_mr, c2, adx_val=15.0, ema200=90.0, params=params)
        self.assertIsNone(sig_none)

    def test_production_gate_calibration_check(self):
        # Verify official fleet_optimized.json passes all 5 calibrated bots and rejects HYPE
        for sym in FLEET_ASSETS:
            self.assertTrue(is_bot_calibrated(sym, "1d", "TREND", fleet_file="fleet_optimized.json", ttl_seconds=0.0))
        self.assertFalse(is_bot_calibrated("HYPE", "1d", "TREND", fleet_file="fleet_optimized.json", ttl_seconds=0.0))

        # Verify explicit is_calibrated=False blocks admission
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump({"HYPE/USDT_1d_TREND": {"is_calibrated": False, "best_params": {}}}, tf)
            tmp_path = tf.name
        try:
            self.assertFalse(is_bot_calibrated("HYPE", "1d", "TREND", fleet_file=tmp_path, ttl_seconds=0.0))
        finally:
            os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
