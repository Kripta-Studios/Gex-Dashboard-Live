import sys
import os
import numpy as np

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from neural.rl.rewards import compute_terminal_reward
from neural.rl.config import RL_CONFIG

def test_emergency_stop_penalty():
    print("Testing Emergency Stop Penalty...")
    
    # Common parameters
    final_pnl = -0.35
    hold_time_norm = 0.1
    entry_delta = 0.5
    mlp_confidence = 0.6
    entry_iv = 0.2
    
    # 1. Test emergency_stop exit
    reward_es = compute_terminal_reward(
        final_pnl_pct=final_pnl,
        hold_time_norm=hold_time_norm,
        entry_delta=entry_delta,
        mlp_confidence=mlp_confidence,
        exit_type="emergency_stop",
        entry_iv=entry_iv
    )
    
    # 2. Test agent_exit with same PnL
    reward_ae = compute_terminal_reward(
        final_pnl_pct=final_pnl,
        hold_time_norm=hold_time_norm,
        entry_delta=entry_delta,
        mlp_confidence=mlp_confidence,
        exit_type="agent_exit",
        entry_iv=entry_iv
    )
    
    # The difference should be exactly -1.5 (additive outside confidence scale)
    diff = reward_es - reward_ae
    print(f"Reward (Emergency Stop): {reward_es:.4f}")
    print(f"Reward (Agent Exit):     {reward_ae:.4f}")
    print(f"Difference:              {diff:.4f}")
    
    expected_diff = -1.5
    assert abs(diff - expected_diff) < 1e-5, f"Expected difference {expected_diff}, got {diff}"
    print("✓ Emergency stop penalty correctly applied (additive).")

def test_config_changes():
    print("\nTesting Config Changes...")
    p0 = RL_CONFIG["curriculum_phases"][0]
    print(f"Phase 0 min_confidence: {p0['min_confidence']}")
    print(f"Phase 0 min_hold:       {p0['min_hold']}")
    
    assert p0["min_confidence"] == 0.60
    assert p0["min_hold"] == 60
    
    h0 = RL_CONFIG["hold_min_minutes_curriculum"][0]
    print(f"Hold curriculum 0 min_hold: {h0['min_hold']}")
    assert h0["min_hold"] == 60
    
    print(f"Emergency stop pct:      {RL_CONFIG['emergency_stop_pct']}")
    assert RL_CONFIG["emergency_stop_pct"] == -0.40
    print("✓ Config changes verified.")

if __name__ == "__main__":
    try:
        test_emergency_stop_penalty()
        test_config_changes()
        print("\nALL VERIFICATIONS PASSED ✓")
    except AssertionError as e:
        print(f"\nVERIFICATION FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAN ERROR OCCURRED: {e}")
        sys.exit(1)
