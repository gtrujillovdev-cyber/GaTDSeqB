import unittest
import json
import os
from bot import calculate_confidence_score, get_bot_params

class TestConfidenceGate(unittest.TestCase):
    
    def test_anti_directional_bias_buy(self):
        """Verifica que un Setup TD +9 (sobrecompra/techo) penalice compras en lugar de bonificarlas."""
        candle_down = {'td_count': -9, 'td_perfected': True, 'rsi': 28.0, 'volume': 150.0, 'volume_sma': 100.0}
        candle_up = {'td_count': 9, 'td_perfected': True, 'rsi': 28.0, 'volume': 150.0, 'volume_sma': 100.0}
        
        score_aligned = calculate_confidence_score(candle_down, "BUY", "BULLISH", False)
        score_adverse = calculate_confidence_score(candle_up, "BUY", "BULLISH", False)
        
        # El score con setup alcista alineado (-9) debe superar claramente al adverso (+9)
        self.assertGreater(score_aligned, score_adverse)
        self.assertGreaterEqual(score_aligned, 0.55)
        
    def test_anti_directional_bias_sell(self):
        """Verifica que un Setup TD -9 (sobreventa/suelo) penalice ventas en lugar de bonificarlas."""
        candle_up = {'td_count': 9, 'td_perfected': True, 'rsi': 72.0, 'volume': 150.0, 'volume_sma': 100.0}
        candle_down = {'td_count': -9, 'td_perfected': True, 'rsi': 72.0, 'volume': 150.0, 'volume_sma': 100.0}
        
        score_aligned = calculate_confidence_score(candle_up, "SELL", "BEARISH", False)
        score_adverse = calculate_confidence_score(candle_down, "SELL", "BEARISH", False)
        
        self.assertGreater(score_aligned, score_adverse)
        self.assertGreaterEqual(score_aligned, 0.55)

    def test_contrary_divergence_penalty(self):
        """Verifica que una divergencia contraria reduzca la convicción."""
        candle = {'td_count': -9, 'td_perfected': True, 'rsi': 35.0, 'volume': 120.0, 'volume_sma': 100.0}
        
        score_neutral = calculate_confidence_score(candle, "BUY", "NONE", False)
        score_contrary = calculate_confidence_score(candle, "BUY", "BEARISH", False)
        
        self.assertGreater(score_neutral, score_contrary)

    def test_score_bounded_between_zero_and_one(self):
        """Verifica que el score nunca exceda [0.0, 1.0] bajo condiciones extremas."""
        extreme_candle = {'td_count': -12, 'td_perfected': True, 'rsi': 10.0, 'volume': 500.0, 'volume_sma': 10.0}
        extreme_context = {'is_buy_exhaustion_active': True, 'macro_weight': 0.15}
        
        score = calculate_confidence_score(extreme_candle, "BUY", "BULLISH", False, fng_index=10, funding_rate=-0.001, weekly_context=extreme_context)
        self.assertLessEqual(score, 1.0)
        self.assertGreaterEqual(score, 0.0)

    def test_adx_trend_regime(self):
        """Verifica moduladores de ADX: tendencia estructurada vs contratendencia acelerada."""
        base_candle = {'td_count': -9, 'td_perfected': False, 'rsi': 45.0, 'volume': 100.0, 'volume_sma': 100.0}
        
        # Con tendencia: ADX alto (fuerte) debe dar mayor score que ADX plano (<18)
        candle_strong_adx = dict(base_candle, adx=28.0)
        candle_flat_adx = dict(base_candle, adx=15.0)
        score_strong = calculate_confidence_score(candle_strong_adx, "BUY", "NONE", False)
        score_flat = calculate_confidence_score(candle_flat_adx, "BUY", "NONE", False)
        self.assertGreater(score_strong, score_flat)
        
        # Contra tendencia: ADX alto (tendencia violenta en contra) debe penalizar
        score_counter_violent = calculate_confidence_score(candle_strong_adx, "BUY", "NONE", True)
        score_counter_calm = calculate_confidence_score(candle_flat_adx, "BUY", "NONE", True)
        self.assertLess(score_counter_violent, score_counter_calm)

    def test_funding_rate_short_squeeze_boost(self):
        """Verifica que un funding rate muy negativo (short squeeze fuel) amplifique convicción de compra."""
        candle = {'td_count': -9, 'td_perfected': False, 'rsi': 45.0, 'volume': 100.0, 'volume_sma': 100.0}
        
        score_neutral_funding = calculate_confidence_score(candle, "BUY", "NONE", False, funding_rate=0.0)
        score_negative_funding = calculate_confidence_score(candle, "BUY", "NONE", False, funding_rate=-0.0004) # Shorts hacinados
        score_euphoric_funding = calculate_confidence_score(candle, "BUY", "NONE", False, funding_rate=0.0006)  # Euforia longs
        
        self.assertGreater(score_negative_funding, score_neutral_funding)
        self.assertLess(score_euphoric_funding, score_neutral_funding)

    def test_breakeven_threshold_non_choking(self):
        """Verifica que ningún parámetro de breakeven en fleet_optimized.json sea menor a 1.0 ATR."""
        with open("fleet_optimized.json", "r") as f:
            data = json.load(f)
        for bot_key, config in data.items():
            be_atr = config.get("best_params", {}).get("be_threshold_atr", 1.0)
            self.assertGreaterEqual(be_atr, 1.0, f"Error en {bot_key}: be_threshold_atr={be_atr} es menor a 1.0 ATR (Choke Effect)")

if __name__ == '__main__':
    unittest.main()
