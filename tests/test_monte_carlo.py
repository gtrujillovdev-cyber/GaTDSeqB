import unittest
import numpy as np
from backtesting.analytics import compute_monte_carlo_edge

class TestMonteCarloBootstrap(unittest.TestCase):
    
    def test_empty_trades(self):
        """Verifica que maneje listas vacías de forma segura."""
        res = compute_monte_carlo_edge([])
        self.assertFalse(res['has_data'])
        self.assertEqual(res['z_score'], 0.0)
        self.assertFalse(res['is_significant'])

    def test_strong_positive_edge_significance(self):
        """Verifica que una serie consistente de trades ganadores genere Z >= 2.50 y p <= 0.01."""
        trades = []
        for i in range(25):
            trades.append({
                'mfe_r': 3.5,
                'mae_r': 0.8,
                'realized_r': 2.0 + (i % 3) * 0.2
            })
            
        res = compute_monte_carlo_edge(trades, n_simulations=1000, seed=42)
        self.assertTrue(res['has_data'])
        self.assertGreaterEqual(res['z_score'], 2.50)
        self.assertLessEqual(res['p_value'], 0.01)
        self.assertTrue(res['is_significant'])
        self.assertGreater(res['mfe_mae_ratio'], 3.0)

    def test_random_noise_zero_edge(self):
        """Verifica que una estrategia sin alfa (retornos simétricos centrados en 0) acepte H0."""
        trades = []
        for i in range(20):
            r = 1.0 if (i % 2 == 0) else -1.0
            trades.append({
                'mfe_r': 1.2,
                'mae_r': 1.2,
                'realized_r': r
            })
            
        res = compute_monte_carlo_edge(trades, n_simulations=1000, seed=42)
        self.assertTrue(res['has_data'])
        self.assertLess(res['z_score'], 2.50)
        self.assertFalse(res['is_significant'])

    def test_mfe_mae_computation(self):
        """Verifica el cálculo exacto de los ratios MFE y MAE."""
        trades = [
            {'mfe_r': 3.0, 'mae_r': 1.0, 'realized_r': 2.0},
            {'mfe_r': 4.0, 'mae_r': 2.0, 'realized_r': 1.5},
            {'mfe_r': 2.0, 'mae_r': 0.0, 'realized_r': 1.0}
        ]
        res = compute_monte_carlo_edge(trades, n_simulations=100, seed=42)
        self.assertAlmostEqual(res['avg_mfe_r'], 3.0, places=2)
        self.assertAlmostEqual(res['avg_mae_r'], 1.0, places=2)
        self.assertAlmostEqual(res['mfe_mae_ratio'], 3.0, places=2)

if __name__ == '__main__':
    unittest.main()
