"""
RL Agent Configuration — Constants, Hyperparameters, Strike Buckets

All tunable parameters in one place. No magic numbers in other files.
"""

import numpy as np

# ═══════════════════════════════════════════════════════════════════════════
# STRIKE BUCKETS — delta targets for the 7 discrete strike choices
# ═══════════════════════════════════════════════════════════════════════════

STRIKE_BUCKETS = {
    0: {"label": "deep_otm",  "delta_target": 0.10},
    1: {"label": "otm_far",   "delta_target": 0.20},
    2: {"label": "otm_near",  "delta_target": 0.30},
    3: {"label": "otm_light", "delta_target": 0.40},
    4: {"label": "atm",       "delta_target": 0.50},
    5: {"label": "itm_light", "delta_target": 0.60},
    6: {"label": "itm",       "delta_target": 0.70},
}

NUM_STRIKE_ACTIONS = len(STRIKE_BUCKETS)
NUM_EXIT_ACTIONS = 2  # HOLD=0, EXIT=1

# ═══════════════════════════════════════════════════════════════════════════
# HARD EXIT RULES — non-negotiable risk limits (environment enforces these)
# ═══════════════════════════════════════════════════════════════════════════

HARD_EXITS = {
    "max_loss_pct":      -0.50,   # exit if position lost 50% of premium
    "max_profit_pct":    +4.00,   # exit if position gained 400% (target expanded)
    "minutes_to_close":   5,      # always exit 5 min before market close
    "max_hold_minutes":   180,    # maximum hold time = MLP lookahead
}

# ═══════════════════════════════════════════════════════════════════════════
# TRANSACTION COST MODEL — half-spread estimates by delta regime
# ═══════════════════════════════════════════════════════════════════════════

SPREAD_MODEL = {
    "otm":  0.06,   # Δ < 0.30 → 6% of mid
    "atm":  0.03,   # 0.30 ≤ Δ ≤ 0.60 → 3% of mid
    "itm":  0.01,   # Δ > 0.60 → 1% of mid
}

def get_half_spread(abs_delta: float) -> float:
    """Return half-spread estimate based on option delta."""
    if abs_delta < 0.30:
        return SPREAD_MODEL["otm"]
    elif abs_delta > 0.60:
        return SPREAD_MODEL["itm"]
    return SPREAD_MODEL["atm"]

# ═══════════════════════════════════════════════════════════════════════════
# STATE DIMENSIONS
# ═══════════════════════════════════════════════════════════════════════════

MARKET_FEATURE_DIM = 163   # from FEATURE_COLUMNS in hybrid_model.py (was 162 — fixed after adding nearest_level_dist_bps)
POSITION_STATE_DIM = 6     # pnl, time_held, delta, theta, iv_ratio, mae
MLP_CONTEXT_DIM = 4        # confidence, time_to_target, mins_since_signal, log_sigma (uncertainty)
TOTAL_STATE_DIM = MARKET_FEATURE_DIM + POSITION_STATE_DIM + MLP_CONTEXT_DIM  # 173

# ═══════════════════════════════════════════════════════════════════════════
# SNIPER ENTRY WINDOW — PRE_ENTRY observation phase
# ═══════════════════════════════════════════════════════════════════════════

SNIPER_STATE_DIM = 2       # sniper_minutes_remaining (norm), sniper_entry_attempted (binary)
SNIPER_WINDOW_MINUTES = 15 # max minutes to observe before entering
NUM_SNIPER_ACTIONS = NUM_STRIKE_ACTIONS + 1  # 8: WAIT(0) + ENTER with strike bucket(1-7)
SNIPER_TOTAL_STATE_DIM = TOTAL_STATE_DIM + SNIPER_STATE_DIM  # 175

# ═══════════════════════════════════════════════════════════════════════════
# PPO HYPERPARAMETERS
# ═══════════════════════════════════════════════════════════════════════════

RL_CONFIG = {
    # Architecture (state_dim set after config based on use_sniper_mode)
    "state_dim":            TOTAL_STATE_DIM,
    "hidden_dims":          [256, 256, 128],
    "backbone_dropout":     0.1,

    # PPO core
    "learning_rate":        3e-4,
    "gamma":                0.99,     # discount — 0.99^180 = 0.16, still meaningful
    "gae_lambda":           0.95,     # GAE smoothing
    "clip_epsilon":         0.20,     # PPO trust region clip
    "value_loss_coeff":     0.5,

    "entropy_coeff":        0.05,     # increased to prevent premature convergence
    "max_grad_norm":        0.5,

    # Training schedule
    "ppo_epochs":           10,       # PPO update epochs per data collection round
    "n_episodes_per_update": 256,     # episodes to collect before PPO update
    "total_updates":        400,      # kept high — eval checkpoint captures best moment
    "batch_size":           128,

    # Walk-forward
    "train_months":         3,
    "test_months":          1,

    # Regularization
    "obs_noise_std":        0.02,     # noise injection on market features
    "min_confidence":       0.50,     # minimum MLP confidence to trade (aligned with backtest threshold)

    # Curriculum learning thresholds
    "curriculum_phases": {
        1: {"pct_training": 0.30, "min_confidence": 0.50},
        2: {"pct_training": 0.70, "min_confidence": 0.50},
        3: {"pct_training": 1.00, "min_confidence": 0.50},
    },

    # Session
    "session_length_minutes": 390,    # 9:30 to 16:00

    # Sniper Entry Window
    "use_sniper_mode":          True,
    "sniper_window_minutes":    SNIPER_WINDOW_MINUTES,
    "sniper_timeout_penalty":   -0.05,
    "sniper_entropy_coeff":     0.10,    # 5× base entropy — force exploration of WAIT vs ENTER
    "sniper_min_wait_curriculum": {       # Forced minimum wait by curriculum phase
        1: {"min_wait": 3},              # Phase 1: must observe 3 min before entering
        2: {"min_wait": 1},              # Phase 2: relax to 1 min
        3: {"min_wait": 0},              # Phase 3: full freedom
    },

    # Minimum hold time — forces agent to experience longer holds
    "hold_min_minutes_curriculum": {
        1: {"min_hold": 60},             # Phase 1: must hold ≥60 min
        2: {"min_hold": 45},             # Phase 2: relax to 45 min
        3: {"min_hold": 30},             # Phase 3: floor at 30 min (Homerun minimum)
    },

    # Emergency stop: bypass min_hold if trade goes very wrong very fast
    "emergency_stop_pct": -0.3,         # -30% premium loss → instant exit regardless of min_hold
}

# ── Apply state_dim override when sniper mode is active ──
if RL_CONFIG["use_sniper_mode"]:
    RL_CONFIG["state_dim"] = SNIPER_TOTAL_STATE_DIM
