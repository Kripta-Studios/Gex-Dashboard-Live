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
    "max_profit_pct":    +2.50,   # exit if position gained 250% (Homerun cap)
    "trailing_stop_pct":  0.30,   # retrace % (inactive — activation unreachable)
    "trailing_stop_activation_pct": 9.99, # Disabled: RL alpha is best without trail
    "minutes_to_close":   5,      # always exit 5 min before market close
    "max_hold_minutes":   180,    # maximum hold time = MLP lookahead
    "min_hold_minutes":   30,      # minimum hold time before RL agent can choose to exit
}

# ═══════════════════════════════════════════════════════════════════════════
# TRANSACTION COST MODEL — half-spread estimates by delta regime
# ═══════════════════════════════════════════════════════════════════════════

SPREAD_MODEL = {
    "otm":  0.03,
    "atm":  0.015,
    "itm":  0.01,
}

def get_half_spread(abs_delta: float) -> float:
    if abs_delta < 0.30:
        return SPREAD_MODEL["otm"]
    elif abs_delta > 0.60:
        return SPREAD_MODEL["itm"]
    return SPREAD_MODEL["atm"]

# ═══════════════════════════════════════════════════════════════════════════
# STATE DIMENSIONS
# ═══════════════════════════════════════════════════════════════════════════

MARKET_FEATURE_DIM = 163
DYNAMIC_MARKET_DIM = 8   # per-minute features from options cache
POSITION_STATE_DIM = 7
MLP_CONTEXT_DIM = 4
TOTAL_STATE_DIM = MARKET_FEATURE_DIM + DYNAMIC_MARKET_DIM + POSITION_STATE_DIM + MLP_CONTEXT_DIM  # 182

# ═══════════════════════════════════════════════════════════════════════════
# SNIPER ENTRY WINDOW
# ═══════════════════════════════════════════════════════════════════════════

SNIPER_STATE_DIM = 2
SNIPER_WINDOW_MINUTES = 15
NUM_SNIPER_ACTIONS = NUM_STRIKE_ACTIONS + 1  # 8: WAIT(0) + ENTER with strike(1-7)
SNIPER_TOTAL_STATE_DIM = TOTAL_STATE_DIM + SNIPER_STATE_DIM  # 183

# ═══════════════════════════════════════════════════════════════════════════
# PPO HYPERPARAMETERS
# ═══════════════════════════════════════════════════════════════════════════

RL_CONFIG = {
    # Architecture
    "state_dim":            TOTAL_STATE_DIM,
    "hidden_dims":          [256, 256, 128],
    "backbone_dropout":     0.05,
    "num_experts":          3,
    "moe_load_balance_coeff": 0.01,
    "pretrain_critic_epochs": 10,
    "pretrain_critic_samples": 5000,

    # PPO core
    # PPO core
    "learning_rate": 1e-05,   # Increased from 3e-5 to escape local minima faster
    "gamma": 0.998,  
    "gae_lambda":           0.95,
    "clip_epsilon": 0.1,   # Standard PPO value for stability
    "value_loss_coeff": 0.05,    
    "entropy_coeff": 0.02,
    "entropy_coeff_min":    0.01,   # Raised from 0.002: old value allowed total entropy death
    "entropy_target":       0.15,   
    "exit_entropy_target":  0.20,   
    "entropy_anneal_end":   400,    # Slower annealing

    # Per-head entropy coefficients (Fix: strike head collapse to otm_light)
    # Strike head gets 4x the exit coefficient + a floor that never anneals to zero
    "strike_entropy_coeff":  0.08,  # High: prevent 7-way categorical collapse
    "strike_entropy_floor":  0.03,  # Minimum strike coeff (never anneal below)
    "exit_entropy_coeff":    0.02,  # Exit head (binary) needs less exploration
    "kl_target":            0.030,  
    "max_grad_norm":        0.5,
    "value_lr_decay_floor": 0.4,    

    # Training schedule
    "ppo_epochs": 3,
    "n_episodes_per_update": 256,
    "total_updates":        500,    
    "batch_size": 1024,

    # Walk-forward
    "train_months":         3,
    "test_months":          1,

    # Regularization
    "obs_noise_std":        0.05,
    # Deployment/backtest signal threshold promoted by neural/run_pipeline.ps1.
    # Keep this aligned with episode extraction, PPO sampling and live routing.
    "min_confidence":       0.420,
    "short_confidence_offset": 0.025,
    "signal_reversal_min_confidence": 0.50,
    "signal_eval_cadence_minutes": 5,

    # Curriculum — Linear interpolation
    # Confidence remains stable at the promoted deployment threshold.
    "curriculum_phases": {
        0: {"pct": 0.00, "min_confidence": 0.550, "min_strike_bucket": 1, "max_strike_bucket": 3, "min_hold_minutes": 45},  
        1: {"pct": 0.20, "min_confidence": 0.520, "min_strike_bucket": 0, "max_strike_bucket": 4, "min_hold_minutes": 75},  
        2: {"pct": 0.45, "min_confidence": 0.500, "min_strike_bucket": 0, "max_strike_bucket": 5, "min_hold_minutes": 105},  
        3: {"pct": 0.70, "min_confidence": 0.480, "min_strike_bucket": 0, "max_strike_bucket": 6, "min_hold_minutes": 150},  
    },

    # Session
    "session_length_minutes": 390,

    # Sniper Entry Window — DISABLED: was trained but never used in production,
    # causing train/prod distribution mismatch at 175 vs 173 dims.
    "use_sniper_mode":          False,
    "sniper_window_minutes":    SNIPER_WINDOW_MINUTES,
    "sniper_timeout_penalty":   -0.05,
    "sniper_entropy_coeff":     0.10,
    "exit_entropy_coeff":       0.05,

    # Safety Fallback: Force noise in exit head regardless of measured entropy
    "logit_noise_exit_override": 0.0,  # set to 0.3+ if entropy triggers fail
    
    "sniper_min_wait_curriculum": {
        0: {"min_wait": 5},
        1: {"min_wait": 3},
        2: {"min_wait": 1},
        3: {"min_wait": 0},
    },

}

# ── Apply state_dim override when sniper mode is active ──
if RL_CONFIG["use_sniper_mode"]:
    RL_CONFIG["state_dim"] = SNIPER_TOTAL_STATE_DIM
