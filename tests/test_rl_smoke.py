"""Smoke test for the RL agent module."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

print("=" * 50)
print("RL AGENT SMOKE TEST")
print("=" * 50)

# 1. Config imports
print("\n[1/4] Testing imports...")
from neural.rl.config import RL_CONFIG, STRIKE_BUCKETS, HARD_EXITS, TOTAL_STATE_DIM
from neural.rl.rewards import compute_step_reward, compute_terminal_reward
from neural.rl.utils import RunningMeanStd, augment_state, CurriculumScheduler, RolloutBuffer
from neural.rl.agent import PPOAgent
print(f"  State dim: {TOTAL_STATE_DIM}")
print(f"  Strike buckets: {len(STRIKE_BUCKETS)}")
print("  ✓ All imports OK")

# 2. Agent forward pass
print("\n[2/4] Testing agent forward pass...")
import torch
import numpy as np

agent = PPOAgent()
n_params = sum(p.numel() for p in agent.parameters())
print(f"  Parameters: {n_params:,}")

state = torch.randn(1, TOTAL_STATE_DIM)
logits_s, value_s = agent.forward(state, "strike")
logits_e, value_e = agent.forward(state, "exit")
assert logits_s.shape == (1, 7), f"Bad strike shape: {logits_s.shape}"
assert logits_e.shape == (1, 2), f"Bad exit shape: {logits_e.shape}"

action, log_prob, value = agent.get_action(state, "strike")
assert isinstance(action, (int, np.integer)), f"Action should be int, got {type(action)}"
print(f"  Strike logits: {logits_s.shape}")
print(f"  Exit logits:   {logits_e.shape}")
print(f"  Value:         {value_s.item():.3f}")
print("  ✓ Forward pass OK")

# 3. Rewards
print("\n[3/4] Testing reward functions...")
r_step = compute_step_reward(0.0, 0.02, -0.05, 60.0, -0.01)
r_win = compute_terminal_reward(0.40, 0.3, 0.30, 0.80, "agent_exit", 0.15)
r_loss = compute_terminal_reward(-0.30, 0.5, 0.50, 0.70, "hard_stop_loss", 0.15)
print(f"  Step reward:      {r_step:.4f}")
print(f"  Terminal (win):   {r_win:.4f}")
print(f"  Terminal (loss):  {r_loss:.4f}")
assert r_win > 0, "Winner should be positive"
assert r_loss < 0, "Loser should be negative"
print("  ✓ Rewards OK (asymmetry confirmed)")

# 4. Utilities
print("\n[4/4] Testing utilities...")
rms = RunningMeanStd()
rms.update(np.array([1.0, 2.0, 3.0, 4.0, 5.0]))
print(f"  RunningMeanStd: mean={rms.mean:.2f}")

state_np = np.random.randn(TOTAL_STATE_DIM).astype(np.float32)
state_aug = augment_state(state_np)
diff = np.abs(state_np - state_aug)
assert diff[:171].sum() > 0, "Market features should change"
assert diff[171:].sum() == 0, "Position+MLP should NOT change"
print("  ✓ Augment: market noised, position untouched")

curriculum = CurriculumScheduler(total_updates=100)
c1 = curriculum.get_phase_info(10)["min_confidence"]
c2 = curriculum.get_phase_info(50)["min_confidence"]
c3 = curriculum.get_phase_info(90)["min_confidence"]
print(f"  Curriculum: p1={c1:.2f}, p2={c2:.2f}, p3={c3:.2f}")
print("  ✓ Utilities OK")

# 5. evaluate_actions (mixed batch)
print("\n[5/5] Testing evaluate_actions (mixed batch)...")
batch_states = torch.randn(4, TOTAL_STATE_DIM)
batch_actions = torch.tensor([3, 0, 1, 5])
batch_types = ["strike", "exit", "exit", "strike"]
log_probs, entropy, values = agent.evaluate_actions(batch_states, batch_actions, batch_types)
assert log_probs.shape == (4,)
assert entropy.shape == (4,)
assert values.shape == (4,)
print(f"  Log probs: {log_probs.detach().numpy()}")
print(f"  Entropy:   {entropy.detach().numpy()}")
print("  ✓ Mixed-batch evaluate_actions OK")

print("\n" + "=" * 50)
print("ALL RL SMOKE TESTS PASSED ✓")
print("=" * 50)
