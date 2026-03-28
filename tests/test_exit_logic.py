import sys
import os
import numpy as np
import pandas as pd
import torch
from unittest.mock import MagicMock

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from neural.rl.integration import IntegratedTradingSystem
from neural.rl.config import HARD_EXITS, RL_CONFIG

class MockModel:
    def eval(self): pass
    def to(self, device): pass
    def __call__(self, x):
        return torch.zeros((1, 3)), torch.zeros((1, 2))
    def predict_proba(self, x):
        return np.array([[0.1, 0.1, 0.8]]) # LONG

class MockAgent:
    def eval(self): pass
    def to(self, device): pass
    def get_action(self, state, action_type="strike", deterministic=True):
        if action_type == "strike":
            return 4, None, None # ATM
        return torch.tensor([0]), None, None # HOLD

def test_trailing_stop():
    print("Testing trailing stop logic...")
    
    # Temporarily modify configuration for testing
    HARD_EXITS["trailing_stop_pct"] = 0.30            # 30% drop from peak
    HARD_EXITS["trailing_stop_activation_pct"] = 0.40 # Only activate if profit >= 40%
    HARD_EXITS["max_profit_pct"] = 1.50               # 150% take profit
    
    mlp = MockModel()
    agent = MockAgent()
    normalizer = MagicMock()
    normalizer.transform.side_effect = lambda x: x
    
    its = IntegratedTradingSystem(mlp, normalizer, agent, [])
    
    # 1. Entry
    spot = 4000.0
    timestamp = pd.Timestamp("2026-03-23 10:00:00", tz="America/New_York")
    options_data = {
        "calls": {4000.0: {"price": 10.0, "delta": 0.5, "iv": 0.15, "gamma": 0.001}},
        "puts": {4000.0: {"price": 10.0, "delta": -0.5, "iv": 0.15, "gamma": 0.001}}
    }
    market_features = np.zeros(163)
    
    res = its.on_new_minute(market_features, options_data, spot, timestamp)
    entry_price = its.open_position["entry_price"]
    print(f"Entry action: {res['action']}, Entry price: {entry_price}")
    assert "BUY_CALL" in res["action"]
    
    # 2. Case: Retrace below activation threshold (+20% retrace to -10%)
    # Profit +20% (Price: 10.3 * 1.2 = 12.36)
    # Then drop to -10% (Price: 10.3 * 0.9 = 9.27)
    # Drawdown is 30% from peak, but activation (40%) was never hit. Should HOLD.
    print("Case A: Retrace below activation threshold (+20% peak, -10% current)")
    options_data_a1 = {"calls": {4000.0: {"price": 12.36, "delta": 0.5, "iv": 0.15, "gamma": 0.001}}}
    its.on_new_minute(market_features, options_data_a1, spot, timestamp + pd.Timedelta(minutes=5))
    
    options_data_a2 = {"calls": {4000.0: {"price": 9.27, "delta": 0.5, "iv": 0.15, "gamma": 0.001}}}
    res_a = its.on_new_minute(market_features, options_data_a2, spot, timestamp + pd.Timedelta(minutes=6))
    print(f"Action (no activation): {res_a['action']}")
    assert res_a["action"] == "HOLD"
    
    # 3. Case: Retrace after activation (+80% peak, +40% current)
    # Peak profit +80% (Price: 10.3 * 1.8 = 18.54)
    # Drop to +40% (Price: 10.3 * 1.4 = 14.42)
    # Drawdown is 40% from peak. 40% > 30% trailing stop AND activation (40%) was hit. Should EXIT.
    print("Case B: Retrace after activation (+80% peak, +40% current)")
    options_data_b1 = {"calls": {4000.0: {"price": 18.54, "delta": 0.5, "iv": 0.15, "gamma": 0.001}}}
    its.on_new_minute(market_features, options_data_b1, spot, timestamp + pd.Timedelta(minutes=10))
    
    options_data_b2 = {"calls": {4000.0: {"price": 14.42, "delta": 0.5, "iv": 0.15, "gamma": 0.001}}}
    res_b = its.on_new_minute(market_features, options_data_b2, spot, timestamp + pd.Timedelta(minutes=11))
    print(f"Action (activated): {res_b['action']}, Reason: {res_b['details'].get('exit_reason')}")
    
    # Post-implementation assertions:
    assert res_b["action"] == "EXIT"
    assert res_b["details"]["exit_reason"] == "TRAILING_STOP"

if __name__ == "__main__":
    test_trailing_stop()
