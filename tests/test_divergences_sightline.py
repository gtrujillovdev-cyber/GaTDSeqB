import unittest
import pandas as pd
import numpy as np
from wycoff_logic import detect_divergences, sightline_check

class TestDivergencesSightline(unittest.TestCase):
    
    def test_clean_bullish_divergence(self):
        """Verifica que una divergencia alcista limpia con visión directa sea detectada."""
        # 10 velas: P1 en vela 2 (low=100, rsi=30), sube a 105 (rsi=45), P2 en vela 8 (low=95, rsi=36)
        lows =  [110, 105, 100, 102, 104, 103,  98,  96,  95,  97]
        highs = [115, 110, 106, 107, 108, 107, 102, 100,  99, 101]
        closes= [112, 106, 102, 104, 106, 104, 100,  98,  97,  99]
        rsis =  [ 50,  40,  30,  35,  45,  42,  38,  37,  36,  40]
        
        df = pd.DataFrame({'low': lows, 'high': highs, 'close': closes, 'rsi': rsis})
        df['atr'] = 2.0
        
        # P1 en índice 2 (low 100, rsi 30), P2 en índice 8 (low 95 < 100, rsi 36 > 30)
        # Evaluamos hasta la vela 8
        result = detect_divergences(df.iloc[:9], lookback=10)
        self.assertEqual(result, 'BULLISH')

    def test_broken_bullish_divergence_sightline_violation(self):
        """Verifica que si una vela intermedia quiebra violentamente la línea de visión, se rechace la divergencia."""
        # Mismo escenario pero vela 5 se desploma a 85 (ruptura de estructura intermedia)
        lows =  [110, 105, 100, 102, 104,  85,  98,  96,  95,  97]
        highs = [115, 110, 106, 107, 108,  90, 102, 100,  99, 101]
        closes= [112, 106, 102, 104, 106,  88, 100,  98,  97,  99]
        rsis =  [ 50,  40,  30,  35,  45,  20,  38,  37,  36,  40]
        
        df = pd.DataFrame({'low': lows, 'high': highs, 'close': closes, 'rsi': rsis})
        df['atr'] = 2.0
        
        result = detect_divergences(df.iloc[:9], lookback=10)
        # Debe ser rechazada porque la vela en 85 quiebra la línea de visión recta
        self.assertIsNone(result)

    def test_clean_bearish_divergence(self):
        """Verifica que una divergencia bajista limpia con visión directa sea detectada."""
        # P1 en vela 2 (high=100, rsi=70), retroceso a 95 (rsi=55), P2 en vela 8 (high=105, rsi=62)
        highs = [ 90,  95, 100,  98,  96,  97, 102, 104, 105, 103]
        lows =  [ 85,  90,  95,  93,  92,  93,  98, 100, 101,  99]
        closes= [ 88,  93,  98,  95,  94,  96, 100, 102, 103, 101]
        rsis =  [ 50,  60,  70,  65,  55,  58,  60,  61,  62,  58]
        
        df = pd.DataFrame({'low': lows, 'high': highs, 'close': closes, 'rsi': rsis})
        df['atr'] = 2.0
        
        result = detect_divergences(df.iloc[:9], lookback=10)
        self.assertEqual(result, 'BEARISH')

    def test_broken_bearish_divergence_sightline_violation(self):
        """Verifica que un mechazo alcista desproporcionado intermedio invalide la divergencia bajista."""
        # Mismo escenario pero vela 5 salta a 120 (quiebra la línea de visión superior)
        highs = [ 90,  95, 100,  98,  96, 120, 102, 104, 105, 103]
        lows =  [ 85,  90,  95,  93,  92, 115,  98, 100, 101,  99]
        closes= [ 88,  93,  98,  95,  94, 118, 100, 102, 103, 101]
        rsis =  [ 50,  60,  70,  65,  55,  85,  60,  61,  62,  58]
        
        df = pd.DataFrame({'low': lows, 'high': highs, 'close': closes, 'rsi': rsis})
        df['atr'] = 2.0
        
        result = detect_divergences(df.iloc[:9], lookback=10)
        self.assertIsNone(result)

    def test_trend_continuation_no_divergence(self):
        """Verifica que una tendencia sana sin divergencias retorne None."""
        # Precio sube y RSI sube concordantemente
        highs = [ 90,  93,  96,  99, 102, 105, 108, 111, 114, 117]
        lows =  [ 85,  88,  91,  94,  97, 100, 103, 106, 109, 112]
        closes= [ 88,  91,  94,  97, 100, 103, 106, 109, 112, 115]
        rsis =  [ 45,  48,  52,  55,  58,  62,  65,  69,  72,  75]
        
        df = pd.DataFrame({'low': lows, 'high': highs, 'close': closes, 'rsi': rsis})
        df['atr'] = 2.0
        
        result = detect_divergences(df, lookback=10)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
