import json
import os
import tempfile
import unittest

import numpy as np
import pandas as pd

import bot
from backtesting.analytics import compute_metrics, compute_monte_carlo_edge
from backtesting.engine import BacktestEngine
from backtesting.indicators import prepare_market_indicators
from core.strategy import (
    DEFAULT_BOT_PARAMS,
    compute_conviction_boost,
    compute_entry_levels,
)
from core.telemetry import aggregate_trade_ledger


class TestBacktestAndRiskInvariants(unittest.TestCase):
    def test_entry_levels_directional_invariants(self):
        """BUY siempre tiene SL < entry < TP; SELL (Trend, Counter, Wyckoff) siempre tiene TP < entry < SL."""
        entry = 50000.0
        atr = 1000.0
        for reason in ("TD9 Buy", "Wyckoff Spring"):
            for counter in (False, True):
                sl, tp, _, _, _ = compute_entry_levels("BUY", reason, entry, atr, counter, DEFAULT_BOT_PARAMS)
                self.assertLess(sl, entry, f"BUY SL debe estar bajo entrada ({reason}, counter={counter})")
                self.assertGreater(tp, entry, f"BUY TP debe estar sobre entrada ({reason}, counter={counter})")

        for reason in ("TD9 Sell", "Wyckoff Upthrust"):
            for counter in (False, True):
                sl, tp, _, _, _ = compute_entry_levels("SELL", reason, entry, atr, counter, DEFAULT_BOT_PARAMS)
                self.assertGreater(sl, entry, f"SELL SL debe estar sobre entrada ({reason}, counter={counter})")
                self.assertLess(tp, entry, f"SELL TP debe estar bajo entrada ({reason}, counter={counter})")

    def test_backtest_sell_stop_loss_is_real_loss(self):
        """Verifica que un SHORT en Trend/Wyckoff que sube contra la entrada cierre en perdida, nunca en ganancia falsa."""
        engine = BacktestEngine(
            symbol="BTC/USDT",
            timeframe="4h",
            strategy="TD9",
            initial_bank=10000.0,
            slippage_bps=0.0,
            funding_rate_8h=0.0,
            params={"enable_trailing": False, "enable_breakeven": False, "enable_scale_out": False},
        )
        sl, tp, _, _, _ = compute_entry_levels("SELL", "TD9 Sell", 100.0, 2.0, False, engine.params)
        self.assertGreater(sl, 100.0)
        self.assertLess(tp, 100.0)

        engine._open_trade("SELL", 100.0, sl, tp, "TD9 Sell (Trend)", pd.Timestamp("2026-01-01 00:00:00"), 0.015, 2.0)
        self.assertIsNotNone(engine.active_trade)

        live_candle = pd.Series(
            {
                "datetime": pd.Timestamp("2026-01-01 04:00:00"),
                "open": 100.0,
                "high": sl + 1.0,
                "low": 99.5,
                "close": sl + 0.5,
            }
        )
        closed_candle = pd.Series({"close": 100.0, "td_countdown": 0})
        engine._manage_active_trade(live_candle, closed_candle, pd.DataFrame(), 0)

        self.assertIsNone(engine.active_trade)
        self.assertEqual(len(engine.trades), 1)
        self.assertLess(engine.trades[0]["pnl"], 0.0)
        self.assertLess(engine.bank, 10000.0)

    def test_conviction_boost_symbol_normalization_parity(self):
        """BTC/USDT y ETH/USDT en BacktestEngine deben recibir el mismo boost que BTC y ETH en bot.py."""
        self.assertEqual(compute_conviction_boost("BTC/USDT", 0.78), 2.0)
        self.assertEqual(compute_conviction_boost("BTC", 0.78), 2.0)
        self.assertEqual(compute_conviction_boost("ETH/USDT", 0.68), 1.5)
        self.assertEqual(compute_conviction_boost("ETH", 0.68), 1.5)
        self.assertEqual(compute_conviction_boost("HYPE/USDT", 0.85), 1.0)

    def test_dca_13_risk_cap_and_state_preservation(self):
        """Verifica que execute_trade preserve cooldown y execute_reinforcement limite el riesgo adicional."""
        with tempfile.TemporaryDirectory() as tmpdir:
            s_file = os.path.join(tmpdir, "state_BTC_HYB_4h.json")
            t_file = os.path.join(tmpdir, "trades_BTC_HYB_4h.json")

            bot.save_state({"status": "IDLE", "last_sl_time": 1700000000.0, "sl_cooldown_secs": 43200}, s_file)
            bot.execute_trade(
                action="BUY",
                price=50000.0,
                sl=48500.0,
                tp=53500.0,
                reason="TD9 Buy (Trend)",
                trigger_time="2026-01-01 00:00:00",
                risk_pct=0.02,
                atr=1000.0,
                symbol="BTC",
                timeframe="4h",
                state_file=s_file,
                trades_file=t_file,
            )

            st = bot.load_state(s_file)
            self.assertEqual(st["status"], "IN_TRADE")
            self.assertEqual(st["last_sl_time"], 1700000000.0)
            self.assertAlmostEqual(st["full_target_risk_usd"], 200.0, places=2)

            bot.execute_reinforcement(
                price=49000.0,
                atr=1000.0,
                state=st,
                action="BUY",
                symbol="BTC",
                timeframe="4h",
                state_file=s_file,
                trades_file=t_file,
            )

            st_after = bot.load_state(s_file)
            self.assertTrue(st_after["reinforced_13"])
            # Riesgo total maximo = 200 + 0.50*200 = 300 (nunca 2.857x = 571.4)
            self.assertLessEqual(st_after["risk_usd"], 300.01)

    def test_runner_state_writes_valid_strict_json_and_cleans_on_close(self):
        """Verifica que runner_active use take_profit=None (no Infinity) y que al cerrar limpie el state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            s_file = os.path.join(tmpdir, "state_BTC_HYB_4h.json")
            t_file = os.path.join(tmpdir, "trades_BTC_HYB_4h.json")

            bot.execute_trade(
                action="BUY",
                price=100.0,
                sl=97.0,
                tp=107.0,
                reason="TD9 Buy (Trend)",
                trigger_time="2026-01-01 00:00:00",
                risk_pct=0.02,
                atr=2.0,
                symbol="BTC",
                timeframe="4h",
                state_file=s_file,
                trades_file=t_file,
            )
            st = bot.load_state(s_file)
            # Simular vela que alcanza TP2 sin tocar SL
            live = pd.Series({"close": 107.5, "high": 108.0, "low": 100.5})
            closed = pd.Series({"close": 100.5})
            bot.check_exit_conditions(
                live, closed, 2.0, st, strategy_type="HYB", symbol="BTC", timeframe="4h", state_file=s_file, trades_file=t_file
            )

            with open(s_file, "r") as f:
                raw = f.read()
            self.assertNotIn("Infinity", raw)
            parsed = json.loads(raw)
            self.assertTrue(parsed["runner_active"])
            self.assertIsNone(parsed["take_profit"])

            # Simular vela que cierra el runner por trailing stop
            live_close = pd.Series({"close": 102.0, "high": 107.0, "low": 101.0})
            bot.check_exit_conditions(
                live_close, closed, 2.0, parsed, strategy_type="HYB", symbol="BTC", timeframe="4h", state_file=s_file, trades_file=t_file
            )
            final_st = bot.load_state(s_file)
            self.assertEqual(final_st["status"], "IDLE")
            self.assertNotIn("runner_active", final_st)
            self.assertNotIn("take_profit", final_st)

    def test_analytics_groups_partials_and_enforces_min_sample(self):
        """Los parciales con mismo parent_id cuentan como 1 trade round-trip y <15 trades no dan Z significativo."""
        events = [
            {"id": "1_partial", "parent_id": 1, "pnl": 100.0, "mfe_r": 2.0, "mae_r": 0.5, "realized_r": 1.0},
            {"id": "1_tp2", "parent_id": 1, "pnl": 150.0, "mfe_r": 3.5, "mae_r": 0.5, "realized_r": 2.5},
            {"id": "1", "parent_id": 1, "pnl": 200.0, "mfe_r": 4.0, "mae_r": 0.5, "realized_r": 3.0},
            {"id": "2", "parent_id": 2, "pnl": -120.0, "mfe_r": 0.4, "mae_r": 1.5, "realized_r": -1.5},
        ]
        eq = pd.DataFrame({"close": [100.0, 105.0], "equity": [10000.0, 10330.0]})
        m = compute_metrics(10000.0, 10330.0, events, eq, timeframe="4h")
        self.assertEqual(m["total_trades"], 2)
        self.assertEqual(m["win_count"], 1)
        self.assertAlmostEqual(m["win_rate"], 50.0, places=2)
        self.assertAlmostEqual(m["bh_return_pct"], 5.0, places=2)

        mc = compute_monte_carlo_edge(events)
        self.assertFalse(mc["is_significant"])
        self.assertEqual(mc["sample_size"], 2)

    def test_engine_runs_on_short_1w_dataset_without_skipping(self):
        """Un dataset 1w de 100 velas debe evaluarse sin devolver 0 barras por start_idx=200."""
        n = 100
        dates = pd.date_range("2024-01-01", periods=n, freq="7D")
        closes = np.linspace(40000.0, 60000.0, n)
        df = pd.DataFrame(
            {
                "datetime": dates,
                "open": closes - 100,
                "high": closes + 300,
                "low": closes - 300,
                "close": closes,
                "volume": np.full(n, 1000.0),
            }
        )
        df = prepare_market_indicators(df)
        engine = BacktestEngine(symbol="BTC/USDT", timeframe="1w", strategy="TD9")
        res = engine.run(df)
        self.assertGreater(len(res["equity_curve"]), 50)

    def test_telemetry_ledger_ignores_openings_and_groups_partials(self):
        """Verifica que el agregador del Kiosko ignore aperturas y agrupe parciales por trade_id."""
        ledger = [
            {"trade_id": "100", "type": "COMPRA (Apertura)", "pnl": 0.0},
            {"trade_id": "100_partial", "type": "VENTA (Cierre Parcial 50%)", "pnl": 150.0},
            {"trade_id": "100_tp2", "type": "VENTA (Cierre Parcial TP2 25%)", "pnl": 200.0},
            {"trade_id": "100_close", "type": "VENTA (Cierre)", "pnl": 100.0},
            {"trade_id": "200", "type": "VENTA (Apertura)", "pnl": 0.0},
            {"trade_id": "200_close", "type": "COMPRA (Cierre)", "pnl": -100.0},
        ]
        agg = aggregate_trade_ledger(ledger, initial_bank=10000.0)
        self.assertEqual(agg["trades_count"], 2)
        self.assertEqual(agg["wins_count"], 1)
        self.assertAlmostEqual(agg["win_rate"], 50.0, places=2)
        self.assertAlmostEqual(agg["bank"], 10350.0, places=2)


if __name__ == "__main__":
    unittest.main()
