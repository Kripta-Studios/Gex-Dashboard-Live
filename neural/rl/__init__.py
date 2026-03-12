"""
SPX 0DTE Options RL Agent — Strike Selection + Exit Optimization

PPO-based RL agent that operates as the execution layer on top of
the existing Hybrid Attention-MLP classifier.

MLP's job:  Predict direction (LONG/SHORT) with confidence.
RL's job:   Choose strike + decide when to exit.
"""

# Only import lightweight config eagerly — safe for multiprocessing workers
from .config import RL_CONFIG, STRIKE_BUCKETS, HARD_EXITS


def __getattr__(name):
    """Lazy-load heavy modules (torch-dependent) on first access only."""
    if name == "PPOAgent":
        from .agent import PPOAgent
        return PPOAgent
    if name in ("compute_step_reward", "compute_terminal_reward"):
        from .rewards import compute_step_reward, compute_terminal_reward
        return compute_step_reward if name == "compute_step_reward" else compute_terminal_reward
    if name in ("RunningMeanStd", "augment_state", "CurriculumScheduler"):
        from .utils import RunningMeanStd, augment_state, CurriculumScheduler
        if name == "RunningMeanStd":
            return RunningMeanStd
        if name == "augment_state":
            return augment_state
        return CurriculumScheduler
    raise AttributeError(f"module 'rl' has no attribute {name!r}")

