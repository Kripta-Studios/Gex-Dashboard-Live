import sys
import os
import numpy as np
import pandas as pd
import torch
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from neural.rl.integration import IntegratedTradingSystem
from neural.rl.config import RL_CONFIG

class MockModel:
    def eval(self): pass
    def to(self, device): pass
    def __call__(self, x):
        return torch.zeros((1, 3)), torch.zeros((1, 2))
    def predict_proba(self, x):
        # 0=SHORT, 1=HOLD, 2=LONG
        return np.array([[0.1, 0.1, 0.8]]) # LONG signal

class MockAgent:
    def eval(self): pass
    def to(self, device): pass
    def get_action(self, state, action_type="strike", deterministic=True):
        if action_type == "strike":
            return 4, None, None # ATM
        return torch.tensor([0]), None, None # HOLD

def test_dynamic_features_alignment():
    print("Testing dynamic features alignment...")
    
    mlp = MockModel()
    agent = MockAgent()
    normalizer = type('MockNormalizer', (), {'transform': lambda self, x: x})()
    
    its = IntegratedTradingSystem(mlp, normalizer, agent, [])
    
    # Mock data
    spot = 4000.0
    timestamp = pd.Timestamp("2026-03-23 10:00:00", tz="America/New_York")
    options_data = {
        "calls": {4000.0: {"price": 10.0, "delta": 0.5, "iv": 0.15, "gamma": 0.001}},
        "puts": {4000.0: {"price": 10.0, "delta": -0.5, "iv": 0.15, "gamma": 0.001}}
    }
    market_features = np.zeros(163)
    
    # 1. First minute: Signal should be detected and signal_spot locked
    print("Step 1: Signal detection")
    res1 = its.on_new_minute(market_features, options_data, spot, timestamp)
    
    assert its._signal_spot == 4000.0
    assert its._signal_direction == "LONG"
    assert its.open_position is not None
    assert its._position_entry_spot == 4000.0
    
    # 2. Second minute: Move spot to 4040 (+1%)
    print("Step 2: PnL and Velocity check")
    spot2 = 4040.0
    timestamp2 = timestamp + pd.Timedelta(minutes=1)
    # Add some history for velocity
    for _ in range(5):
        its._spot_history.append(4000.0)
    its._spot_history.append(4040.0)
    
    # Calculate expected dynamic[0] (change since signal)
    # spot=4040, signal_spot=4000 => change = +1% => dynamic[0] = 1.0
    
    # Calculate expected dynamic[1] (velocity)
    # Env: (spot - spot_5m_ago) / signal_spot * 100
    # (4040 - 4000) / 4000 * 100 = 1.0
    
    # Calculate expected dynamic[4] (change since entry)
    # spot=4040, entry_spot=4000 => +1% => dynamic[4] = 1.0 (sign + for LONG)
    
    its._update_dynamic_features(options_data, spot2, timestamp2)
    dyn = its._dynamic_market_state
    
    print(f"Dynamic features: {dyn}")
    assert np.isclose(dyn[0], 1.0), f"Expected dynamic[0]=1.0, got {dyn[0]}"
    assert np.isclose(dyn[1], 1.0), f"Expected dynamic[1]=1.0, got {dyn[1]}"
    assert np.isclose(dyn[4], 1.0), f"Expected dynamic[4]=1.0, got {dyn[4]}"
    
    # 3. Test Trend Lookback (dynamic[7])
    print("Step 3: Trend lookback check")
    its._spot_history.clear()
    for i in range(50):
        its._spot_history.append(4000.0 + i) # Steady uptrend
    
    its._update_dynamic_features(options_data, spot2, timestamp2)
    # diffs should be from last 20 mins. np.diff([4030...4049]) => all positive.
    # (20 - 0) / 20 = 1.0
    assert dyn[7] == 1.0
    
    print("All alignment tests passed!")

if __name__ == "__main__":
    test_dynamic_features_alignment()
