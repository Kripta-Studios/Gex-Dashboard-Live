"""
RL Utilities — RunningMeanStd, State Augmentation, Curriculum Scheduler
"""

import numpy as np
from .config import RL_CONFIG, POSITION_STATE_DIM, MLP_CONTEXT_DIM, SNIPER_STATE_DIM


class RunningMeanStd:
    """
    Welford's online algorithm for running mean/variance.
    Used for reward normalization — prevents volatile periods from
    dominating gradient updates.
    """

    def __init__(self, epsilon: float = 1e-4):
        self.mean = 0.0
        self.var = 1.0
        self.count = epsilon

    def update(self, x: np.ndarray):
        """Update running statistics with a batch of values."""
        batch_mean = np.mean(x)
        batch_var = np.var(x)
        batch_count = len(x)
        delta = batch_mean - self.mean
        total_count = self.count + batch_count
        self.mean += delta * batch_count / total_count
        m_a = self.var * self.count
        m_b = batch_var * batch_count
        self.var = (m_a + m_b + delta ** 2 * self.count * batch_count / total_count) / total_count
        self.count = total_count

    def normalize(self, x: np.ndarray) -> np.ndarray:
        """Normalize using running statistics, clip to [-5, 5]."""
        return np.clip((x - self.mean) / (np.sqrt(self.var) + 1e-8), -5.0, 5.0)

    def state_dict(self) -> dict:
        return {"mean": self.mean, "var": self.var, "count": self.count}

    def load_state_dict(self, d: dict):
        self.mean = d["mean"]
        self.var = d["var"]
        self.count = d["count"]


def augment_state(state: np.ndarray, market_feature_dim: int = None,
                  noise_std: float = None) -> np.ndarray:
    """
    Observation noise injection during training.

    Adds Gaussian noise ONLY to market features (first N dims).
    Does NOT noise position state or MLP context — those must be exact
    because noise on P&L features would corrupt the reward signal.
    """
    if market_feature_dim is None:
        # Position + MLP context + (sniper if active) = non-market dims
        # noise applies to BOTH static (163) and dynamic (8) market features
        non_market = (SNIPER_STATE_DIM + POSITION_STATE_DIM + MLP_CONTEXT_DIM
                      if RL_CONFIG.get("use_sniper_mode")
                      else POSITION_STATE_DIM + MLP_CONTEXT_DIM)  # 10 or 12
        market_feature_dim = RL_CONFIG["state_dim"] - non_market
    if noise_std is None:
        noise_std = RL_CONFIG.get("obs_noise_std", 0.02)

    state_aug = state.copy()
    noise = np.random.randn(market_feature_dim) * noise_std
    state_aug[:market_feature_dim] += noise
    return state_aug


class CurriculumScheduler:
    """
    Gradual curriculum learning with linear interpolation between nodes.
    Prevents "cliff effects" when transitioning between phases.
    """

    def __init__(self, total_updates: int = None):
        self.total_updates = total_updates or RL_CONFIG["total_updates"]
        self.phases = RL_CONFIG["curriculum_phases"]

    def get_phase_info(self, update_step: int) -> dict:
        """
        Linearly interpolate curriculum parameters based on training progress.
        Returns: {phase, min_confidence, progress}
        """
        progress = min(update_step / max(self.total_updates, 1), 1.0)
        
        # Sort nodes by pct to find the interval
        nodes = sorted(self.phases.items(), key=lambda x: x[1]["pct"])
        
        lower = nodes[0][1]
        upper = nodes[-1][1]
        current_phase = nodes[0][0]
        
        for i in range(len(nodes) - 1):
            if nodes[i][1]["pct"] <= progress <= nodes[i+1][1]["pct"]:
                lower = nodes[i][1]
                upper = nodes[i+1][1]
                current_phase = nodes[i][0]
                break
        
        # Linear interpolation factor
        if upper["pct"] == lower["pct"]:
            alpha = 1.0
        else:
            alpha = (progress - lower["pct"]) / (upper["pct"] - lower["pct"])
            
        conf = lower["min_confidence"] + alpha * (upper["min_confidence"] - lower["min_confidence"])
        strike = lower["min_strike_bucket"] + alpha * (upper["min_strike_bucket"] - lower["min_strike_bucket"])
        max_s = lower.get("max_strike_bucket", 6) + alpha * (upper.get("max_strike_bucket", 6) - lower.get("max_strike_bucket", 6))
        hold = lower.get("min_hold_minutes", 0) + alpha * (upper.get("min_hold_minutes", 0) - lower.get("min_hold_minutes", 0))
        
        return {
            "phase": current_phase,
            "min_confidence": float(conf),
            "min_strike_bucket": int(round(strike)),
            "max_strike_bucket": int(round(max_s)),
            "min_hold_minutes": int(round(hold)),
            "progress": progress
        }


class RolloutBuffer:
    """
    Storage for PPO rollout data collected during episode execution.
    Stores states, actions, rewards, log_probs, values, dones.
    """

    def __init__(self):
        self.clear()

    def clear(self):
        self.states = []
        self.actions = []
        self.action_types = []  # "strike" or "exit"
        self.rewards = []
        self.log_probs = []
        self.values = []
        self.dones = []

    def add(self, state: np.ndarray, action: int, action_type: str,
            reward: float, log_prob: float, value: float, done: bool):
        self.states.append(state)
        self.actions.append(action)
        self.action_types.append(action_type)
        self.rewards.append(reward)
        self.log_probs.append(log_prob)
        self.values.append(value)
        self.dones.append(done)

    def __len__(self):
        return len(self.states)

    def get_batches(self, batch_size: int = 128):
        """Yield random mini-batches for PPO updates."""
        import torch
        n = len(self.states)
        indices = np.random.permutation(n)

        states = np.array(self.states, dtype=np.float32)
        old_log_probs = np.array(self.log_probs, dtype=np.float32)
        returns = np.array(self.rewards, dtype=np.float32)  # pre-computed in GAE
        values = np.array(self.values, dtype=np.float32)

        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            idx = indices[start:end]
            yield {
                "states": torch.FloatTensor(states[idx]),
                "actions": [self.actions[i] for i in idx],
                "action_types": [self.action_types[i] for i in idx],
                "old_log_probs": torch.FloatTensor(old_log_probs[idx]),
                "returns": torch.FloatTensor(returns[idx]),
                "values": torch.FloatTensor(values[idx]),
            }

def get_delta_bucket(delta: float) -> int:
    """Bucketize absolute delta [0.1-0.7] into 6 categories."""
    d = abs(delta)
    if d < 0.2: return 0
    if d < 0.3: return 1
    if d < 0.4: return 2
    if d < 0.5: return 3
    if d < 0.6: return 4
    return 5 # > 0.6

def get_iv_bucket(iv: float) -> int:
    """Bucketize IV into 3 categories."""
    if iv < 0.15: return 0
    if iv < 0.25: return 1
    return 2 # > 0.25

def get_pnl_bucket(pnl: float) -> int:
    """Bucketize PnL [-0.5 to 0] into 6 floor categories."""
    if pnl < -0.40: return 0
    if pnl < -0.30: return 1
    if pnl < -0.20: return 2
    if pnl < -0.10: return 3
    if pnl < -0.05: return 4
    return 5 # -0.05 to 0
