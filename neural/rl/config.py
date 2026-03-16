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
    "max_profit_pct":    +4.00,   # exit if position gained 400%
    "minutes_to_close":   5,      # always exit 5 min before market close
    "max_hold_minutes":   180,    # maximum hold time = MLP lookahead
}

# ═══════════════════════════════════════════════════════════════════════════
# TRANSACTION COST MODEL — half-spread estimates by delta regime
# ═══════════════════════════════════════════════════════════════════════════

SPREAD_MODEL = {
    "otm":  0.06,
    "atm":  0.03,
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
POSITION_STATE_DIM = 6
MLP_CONTEXT_DIM = 4
TOTAL_STATE_DIM = MARKET_FEATURE_DIM + POSITION_STATE_DIM + MLP_CONTEXT_DIM  # 173

# ═══════════════════════════════════════════════════════════════════════════
# SNIPER ENTRY WINDOW
# ═══════════════════════════════════════════════════════════════════════════

SNIPER_STATE_DIM = 2
SNIPER_WINDOW_MINUTES = 15
NUM_SNIPER_ACTIONS = NUM_STRIKE_ACTIONS + 1  # 8: WAIT(0) + ENTER with strike(1-7)
SNIPER_TOTAL_STATE_DIM = TOTAL_STATE_DIM + SNIPER_STATE_DIM  # 175

# ═══════════════════════════════════════════════════════════════════════════
# PPO HYPERPARAMETERS
# ═══════════════════════════════════════════════════════════════════════════

RL_CONFIG = {
    # Architecture
    "state_dim":            TOTAL_STATE_DIM,
    "hidden_dims":          [256, 256, 128],
    "backbone_dropout":     0.1,

    # PPO core
    "learning_rate":        3e-4,
    "gamma":                0.99,
    "gae_lambda":           0.95,
    "clip_epsilon":         0.20,
    "value_loss_coeff":     0.5,
    "entropy_coeff":        0.05,
    "max_grad_norm":        0.5,

    # Training schedule
    "ppo_epochs":           10,
    "n_episodes_per_update": 256,
    "total_updates":        400,
    "batch_size":           128,

    # Walk-forward
    "train_months":         3,
    "test_months":          1,

    # Regularization
    "obs_noise_std":        0.02,
    "min_confidence":       0.50,

    # Curriculum — todos los phases usan min_confidence=0.50 (sin filtro)
    "curriculum_phases": {
        1: {"pct_training": 0.30, "min_confidence": 0.50},
        2: {"pct_training": 0.70, "min_confidence": 0.50},
        3: {"pct_training": 1.00, "min_confidence": 0.50},
    },

    # Session
    "session_length_minutes": 390,

    # Sniper Entry Window — DISABLED: was trained but never used in production,
    # causing train/prod distribution mismatch at 175 vs 173 dims.
    "use_sniper_mode":          False,
    "sniper_window_minutes":    SNIPER_WINDOW_MINUTES,
    "sniper_timeout_penalty":   -0.05,
    "sniper_entropy_coeff":     0.10,
    "sniper_min_wait_curriculum": {
        1: {"min_wait": 3},
        2: {"min_wait": 1},
        3: {"min_wait": 0},
    },

    # Minimum hold time — AUMENTADO para forzar al agente a experimentar
    # holds más largos y aprender que son rentables
    # ANTES: Phase 3 = 30 min → agente salía exactamente a los 30 min
    # AHORA: Phase 3 = 45 min → agente debe aguantar 15 min más mínimo
    "hold_min_minutes_curriculum": {
        1: {"min_hold": 60},   # Phase 1: ≥60 min (aprende con trades largos)
        2: {"min_hold": 45},   # Phase 2: ≥45 min
        3: {"min_hold": 30},   # Phase 3: ≥30 min (era 30 — el agente salía exactamente aquí)
    },

    # Emergency stop: bypass min_hold si el trade va muy mal muy rápido
    "emergency_stop_pct": -0.3,
}

# ── Apply state_dim override when sniper mode is active ──
if RL_CONFIG["use_sniper_mode"]:
    RL_CONFIG["state_dim"] = SNIPER_TOTAL_STATE_DIM