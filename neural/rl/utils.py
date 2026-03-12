"""
RL Utilities — RunningMeanStd, State Augmentation, Curriculum Scheduler
"""

import numpy as np
from .config import RL_CONFIG


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
        # 6 position + 3 MLP + (2 sniper if active) = 9 or 11 non-market dims
        non_market = 11 if RL_CONFIG.get("use_sniper_mode") else 9
        market_feature_dim = RL_CONFIG["state_dim"] - non_market
    if noise_std is None:
        noise_std = RL_CONFIG.get("obs_noise_std", 0.02)

    state_aug = state.copy()
    noise = np.random.randn(market_feature_dim) * noise_std
    state_aug[:market_feature_dim] += noise
    return state_aug


class CurriculumScheduler:
    """
    3-phase curriculum learning for RL training.

    Phase 1 (first 30%):  High-confidence signals only (≥0.80)
    Phase 2 (next 40%):   Medium-confidence (≥0.65)
    Phase 3 (final 30%):  Full distribution (≥0.60)
    """

    def __init__(self, total_updates: int = None):
        self.total_updates = total_updates or RL_CONFIG["total_updates"]
        self.phases = RL_CONFIG["curriculum_phases"]

    def get_min_confidence(self, update_step: int) -> float:
        """Return the minimum MLP confidence threshold for the current phase."""
        progress = update_step / max(self.total_updates, 1)
        for phase_idx in sorted(self.phases.keys()):
            phase = self.phases[phase_idx]
            if progress <= phase["pct_training"]:
                return phase["min_confidence"]
        return RL_CONFIG["min_confidence"]

    def get_phase_info(self, update_step: int) -> dict:
        """Return full phase info for logging."""
        progress = update_step / max(self.total_updates, 1)
        for phase_idx in sorted(self.phases.keys()):
            phase = self.phases[phase_idx]
            if progress <= phase["pct_training"]:
                return {"phase": phase_idx, "progress": progress, **phase}
        return {"phase": len(self.phases), "progress": progress,
                "min_confidence": RL_CONFIG["min_confidence"],
                "description": "full"}


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
        advantages = returns - values

        # Normalize advantages
        adv_mean, adv_std = advantages.mean(), advantages.std() + 1e-8
        advantages = (advantages - adv_mean) / adv_std

        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            idx = indices[start:end]
            yield {
                "states": torch.FloatTensor(states[idx]),
                "actions": [self.actions[i] for i in idx],
                "action_types": [self.action_types[i] for i in idx],
                "old_log_probs": torch.FloatTensor(old_log_probs[idx]),
                "returns": torch.FloatTensor(returns[idx]),
                "advantages": torch.FloatTensor(advantages[idx]),
            }
