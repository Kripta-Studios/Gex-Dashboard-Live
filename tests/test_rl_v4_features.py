import unittest
import numpy as np
import pandas as pd
import os
import sys
import pickle

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from neural.rl.environment import SPXOptionsEnv
from neural.rl.config import RL_CONFIG

class TestRLV4Features(unittest.TestCase):
    def setUp(self):
        # Create a dummy episode index
        self.df = pd.DataFrame([{
            "ticker": "SPX",
            "date": "20240101",
            "time": "10:00",
            "spot_price": 5000.0,
            "mlp_direction": "LONG",
            "mlp_confidence": 0.8,
            "mlp_time_to_target": 0.5,
            "mlp_log_sigma": 0.0,
            "vix_regime": 0
        }])
        
        # Create a dummy options cache
        self.cache = {
            "SPX_20240101_10:00": {
                "spot": 5000.0,
                "calls": {
                    5000.0: {"price": 10.0, "delta": 0.5, "iv": 0.15, "theta": -0.05, "gamma": 0.001}
                },
                "puts": {},
                "minutes": {
                    1: {
                        "spot": 4995.0,
                        "calls": {
                            5000.0: {"price": 9.0, "delta": 0.48, "iv": 0.15, "theta": -0.05, "gamma": 0.001}
                        }
                    }
                }
            }
        }
        
        # Create a dummy recovery stats file if it doesn't exist
        self.stats_path = "rl_data/recovery_stats.pkl"
        self.created_dummy_stats = False
        if not os.path.exists(self.stats_path):
            os.makedirs("rl_data", exist_ok=True)
            dummy_stats = {(3, 1, 4): 0.75} # (delta_0.5, iv_0.15, pnl_-0.10)
            with open(self.stats_path, "wb") as f:
                pickle.dump(dummy_stats, f)
            self.created_dummy_stats = True

    def test_drawdown_recovery_feature(self):
        env = SPXOptionsEnv(self.df, self.cache, [])
        state = env.reset()
        
        # Enter position (strike_action=4 is ATM)
        state, _, _, _ = env.step(4)
        
        # Advance 1 minute to show drawdown
        # Entry price was 10.0, current 9.0 -> PnL -10%
        # Delta at entry 0.5 (bucket 3), IV 0.15 (bucket 1), PnL -0.10 (bucket 4)
        state, reward, done, info = env.step(0) # Action 0 = Hold
        
        # Position features Group 3 starts at MARKET_FEATURE_DIM(163) + DYNAMIC_MARKET_DIM(8) = 171
        # Position features: [pnl, time, delta, recovery_rate, iv, mae]
        # recovery_rate is at index 171 + 3 = 174
        
        recovery_rate = state[174]
        print(f"Detected recovery rate in state: {recovery_rate}")
        
        # Verify it's not the default 0.0 and it's within [0, 1]
        self.assertGreater(recovery_rate, 0.0)
        self.assertLessEqual(recovery_rate, 1.0)
        
        # Verify internal attribute exists with preferred name
        self.assertTrue(hasattr(env, '_recovery_lookup'))
        
    def tearDown(self):
        if self.created_dummy_stats:
            # Maybe keep it for the real run? 
            # Actually, I already generated a real one in the previous step.
            # So I should only delete it if I created it as a dummy.
            pass

if __name__ == "__main__":
    unittest.main()
