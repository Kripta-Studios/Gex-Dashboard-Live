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

    # PPO core
    "learning_rate":        6e-5,   # Slightly higher to force exit from zero-gradient trap
    "gamma":                0.995,  
    "gae_lambda":           0.95,
    "clip_epsilon":         0.30,   # Increased from 0.25 to allow bolder updates
    "value_loss_coeff":     0.5,    
    "entropy_coeff":        0.002,  
    "entropy_coeff_min":    0.0005, 
    "entropy_target":       0.10,   
    "exit_entropy_target":  0.15,   
    "entropy_anneal_end":   300,    
    "kl_target":            0.050,  # Increased from 0.02 to allow the policy to move
    "max_grad_norm":        0.5,
    "value_lr_decay_floor": 0.4,    # Keep critic learning at a higher floor than policy (40% vs 20%)

    # Training schedule
    "ppo_epochs":           4,
    "n_episodes_per_update": 256,
    "total_updates":        500,    # Asegurar que coincide con el run_pipeline
    "batch_size":           128,

    # Walk-forward
    "train_months":         3,
    "test_months":          1,

    # Regularization
    "obs_noise_std":        0.05,
    "min_confidence":       0.550,
    "short_confidence_offset": 0.025,
    "signal_reversal_min_confidence": 0.50,
    "signal_eval_cadence_minutes": 5,

    # Curriculum — linear interpolation will be used between these nodes:
    # Redesigned: force longer holds early + OTM/ATM exploration before ITM
    "curriculum_phases": {
        0: {"pct": 0.00, "min_confidence": 0.675, "min_strike_bucket": 1, "max_strike_bucket": 3, "min_hold_minutes": 120},  
        1: {"pct": 0.15, "min_confidence": 0.625, "min_strike_bucket": 0, "max_strike_bucket": 4, "min_hold_minutes": 90},  
        2: {"pct": 0.35, "min_confidence": 0.550, "min_strike_bucket": 0, "max_strike_bucket": 5, "min_hold_minutes": 60},  
        3: {"pct": 0.60, "min_confidence": 0.550, "min_strike_bucket": 0, "max_strike_bucket": 6, "min_hold_minutes": 45},  
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
