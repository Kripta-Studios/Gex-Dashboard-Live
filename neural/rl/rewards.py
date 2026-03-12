"""
RL Reward Functions — Step (Dense) + Terminal (Sparse) + Sniper (Pre-Entry)

HOMERUN STRATEGY:
The reward function is tuned to force the agent to HOLD winning trades
for 60-120 minutes, pursuing +300-400% returns on 0DTE options.
Early exits on profitable trades are severely punished (FOMO penalty).
"""

import numpy as np


def compute_sniper_step_reward() -> float:
    """
    PRE_ENTRY reward signal — intentionally neutral.

    During the sniper window, step rewards are 0.0 so the agent
    is not biased toward entering early or late. The learning signal
    for optimal entry timing comes entirely from the terminal reward:
    better entries → higher terminal PnL → stronger signal.

    The timeout penalty (-0.05) is applied by the environment when the
    sniper window expires without entry, not by this function.
    """
    return 0.0

def compute_step_reward(prev_pnl_pct: float, curr_pnl_pct: float,
                        theta_vs_premium: float, minutes_to_close: float,
                        mae_ratio: float, hold_time_minutes: int = 0) -> float:
    """
    Dense reward signal at each timestep while holding a position.

    Components:
    1. Delta P&L (weight 0.3) — immediate price movement
    2. Theta penalty (weight 0.2) — penalize holding through decay
       Doubles in severity in the last hour (exponential)
    3. Drawdown penalty (weight 0.1) — penalize new MAE extensions
    4. Time-scaled hold incentive — GROWS with hold time to reward patience

    Returns: float, intentionally small per step but accumulates
    """
    # 1. Delta P&L
    delta_pnl = curr_pnl_pct - prev_pnl_pct

    # 2. Theta penalty — exponential near close (softened to reduce exit pressure)
    theta_weight = 1.0 + 1.0 * np.exp(-minutes_to_close / 60.0)
    if curr_pnl_pct > 0.03: 
        # No theta penalty if we are in profit (>3%), removes the "fear" of holding winners.
        theta_penalty = 0.0
    else:
        theta_penalty = theta_vs_premium * theta_weight

    # 3. Drawdown penalty — only on new MAE extensions
    if curr_pnl_pct < mae_ratio and curr_pnl_pct < 0:
        drawdown_penalty = (curr_pnl_pct - mae_ratio) * 0.2
    else:
        drawdown_penalty = 0.0  

    # 4. Time-scaled hold incentive (HOMERUN STRATEGY)
    # The bonus GROWS with hold time — makes every minute of holding increasingly valuable.
    # This directly fights the agent's urge to scalp at +10-20%.
    if curr_pnl_pct > 0.05:
        # Trade is green >5% — aggressive patience reward that escalates with time
        if hold_time_minutes < 15:
            hold_incentive = 0.01   # Tiny: scalping zone, almost no reward
        elif hold_time_minutes < 45:
            hold_incentive = 0.05   # Moderate: patience building
        elif hold_time_minutes < 90:
            hold_incentive = 0.15   # Large: deep patience
        else:
            hold_incentive = 0.25   # Maximum: Homerun territory

        # Additional "coin collecting" bonus proportional to hold time
        hold_incentive += 0.02 * min(hold_time_minutes / 90.0, 1.0)
    elif curr_pnl_pct > 0.0:
        # Slightly profitable — moderate hold incentive
        hold_incentive = 0.005 + 0.01 * min(hold_time_minutes / 60.0, 1.0)
    else:
        # Losing or flat — minimal base incentive (don't encourage holding losers)
        hold_incentive = 0.001

    r_step = (0.3 * delta_pnl
          - 0.02 * abs(theta_penalty)
          - 0.05 * abs(drawdown_penalty)
          + hold_incentive)


    return float(r_step)


def compute_terminal_reward(final_pnl_pct: float, hold_time_norm: float,
                            entry_delta: float, mlp_confidence: float,
                            exit_type: str, entry_iv: float,
                            entry_price_improvement: float = 0.0,
                            max_move_pct: float = 0.0,
                            hold_time_minutes: int = 0) -> float:
    """
    Primary learning signal. Received once per episode (trade).

    Components:
    1. Core P&L reward — asymmetric (linear gains ×2, losses ×1.5)
    2. Patience bonus — rewards holding through big winners
    3. Hard stop penalty — additional −1.0 if agent hit the hard stop
    4. Strike quality bonus — +0.5 for ITM winners, +0.1 for OTM sweet-spot
    5. FOMO penalty — MASSIVE punishment for exiting winners before 60 min
    6. Under-capture penalty — penalizes exiting with <30% of available move
    7. Entry timing bonus — up to +0.3 for capturing pullback during sniper window
    8. Transaction penalty — flat cost per trade (-1.0)

    Scaled by MLP confidence, clipped to [-20, +500].
    """
    # 0. Volatility Scaling (normalize to 15% IV)
    vol_scaled_pnl = final_pnl_pct * (0.15 / max(entry_iv, 0.05))

    # 1. Core P&L reward (asymmetric — key to profit factor)
    if vol_scaled_pnl >= 0:
        # Recompensa lineal directa. Si gana el triple, recibe el triple.
        pnl_reward = (vol_scaled_pnl * 2.0) + (vol_scaled_pnl ** 2.0) * 5.0
    else:
        pnl_reward = vol_scaled_pnl * 1.5          

    # 2. Patience bonus — rewards holding IF the gain is meaningful
    # Aggressively scales with BOTH hold time and magnitude for Homeruns
    if final_pnl_pct >= 1.00:
        # Explosive winner (≥100%): massive time bonus
        patience_factor = min(hold_time_norm / 0.7, 1.0)  # maxes at ~120min
        time_bonus = final_pnl_pct * 0.5 * (0.5 + 1.5 * patience_factor)
    elif final_pnl_pct >= 0.03:
        # Moderate winner (3-100%): bonus scales UP with hold time
        # Increased multiplier from 0.5 → 1.5 and patience window to 120min
        patience_factor = min(hold_time_norm / 0.67, 1.0)  # maxes at ~120min
        time_bonus = final_pnl_pct * 1.5 * (0.2 + 0.8 * patience_factor)
    elif final_pnl_pct > 0.0 and hold_time_norm >= 0.05:
        # Tiny winner: small bonus only if held >9 min (no scalping reward)
        time_bonus = final_pnl_pct * 0.1
    else:
        time_bonus = 0.0

    # 3. Hard stop penalty
    hard_stop_penalty = -1.0 if exit_type == "hard_stop_loss" else 0.0  

    # 4. Strike quality bonus
    if abs(entry_delta) >= 0.50 and final_pnl_pct > 0:
        strike_bonus = 0.5    # ITM winners — strongest signal
    elif 0.25 <= abs(entry_delta) <= 0.45 and final_pnl_pct > 0:
        strike_bonus = 0.1    # OTM sweet-spot winners
    elif abs(entry_delta) >= 0.50:
        strike_bonus = 0.05   # ITM exploration even on losers
    else:
        strike_bonus = 0.0

    # 5. Cowardice amplifier (soft, data-driven — NO hard time threshold)
    # If the agent voluntarily exits a winner AND left significant upside
    # on the table, we amplify the penalty. This lets the RL discover the
    # optimal exit time from data, not from an arbitrary minute cutoff.
    cowardice_penalty = 0.0
    if exit_type == "agent_exit" and final_pnl_pct > 0 and max_move_pct > 0:
        capture_ratio = final_pnl_pct / max_move_pct
        if capture_ratio < 0.50:
            # Exited way too early relative to what the market offered
            # Scale: how much was left × how poor the capture was
            missed_pct = max_move_pct - final_pnl_pct
            cowardice_penalty = -2.0 * missed_pct * (1.0 - capture_ratio)
            cowardice_penalty = max(cowardice_penalty, -20.0)  # cap

    # 6. Early exit penalty on LOSERS (unchanged)
    early_exit_penalty = 0.0
    if exit_type == "agent_exit" and hold_time_norm < 0.10 and final_pnl_pct <= 0:
        early_exit_penalty = -0.3

    # 7. Under-capture penalty: did the agent leave money on the table?
    # Threshold lowered from 0.45 → 0.30, multiplier increased from -2.0 → -4.0
    upside_penalty = 0.0
    if max_move_pct > 0 and final_pnl_pct > 0:
        capture_ratio = final_pnl_pct / max_move_pct
        if capture_ratio < 0.30:
            # Devastating penalty for leaving huge money on the table
            missed_pct = max_move_pct - final_pnl_pct
            upside_penalty = -4.0 * missed_pct * (1.0 - capture_ratio)

    # 8. Entry timing bonus — reward for capturing a pullback before entering
    entry_timing_bonus = min(entry_price_improvement * 5.0, 0.3) if entry_price_improvement > 0 else 0.0

    # 9. Transaction penalty (increased from -0.50 → -1.0)
    # Makes every trade "cost" more, discouraging frequent open/close cycles
    transaction_penalty = -1.0

    terminal_reward = (pnl_reward + time_bonus + hard_stop_penalty
                       + strike_bonus + cowardice_penalty + early_exit_penalty
                       + upside_penalty + entry_timing_bonus
                       + transaction_penalty)
    # Scale by MLP confidence
    confidence_scale = 0.5 + mlp_confidence
    terminal_reward *= confidence_scale
    
    # Unleashed clipping ceiling to allow for massive +400% targets
    return float(np.clip(terminal_reward, -20.0, 500.0))
