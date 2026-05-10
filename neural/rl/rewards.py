"""
RL Reward Functions — Step (Dense) + Terminal (Sparse) + Sniper (Pre-Entry)

HOMERUN STRATEGY:
The reward function is tuned to force the agent to HOLD winning trades
for 60-120 minutes, pursuing +300-400% returns on 0DTE options.
Early exits on profitable trades are severely punished (FOMO penalty).

CHANGELOG v5:
- hold_incentive ASYMMETRIC: full incentive for winning/flat trades,
  scaled down for losing trades. Prevents rewarding stubborn losers
  while still encouraging holding (anti-flee behavior).
- Terminal reward scaled ×3.0 — ensures final PnL signal dominates
  over accumulated step rewards in GAE returns.
- Step reward delta_pnl weight increased 0.3 → 1.0 for stronger signal.
"""

import numpy as np


def compute_sniper_step_reward() -> float:
    return 0.0


def compute_step_reward(prev_pnl_pct: float, curr_pnl_pct: float,
                        hold_time_minutes: int, recovery_rate: float = 0.3,
                        spot_momentum: float = 0.0,
                        trailing_drawdown: float = 0.0,
                        is_new_hwm: bool = False) -> float:
    """
    V8-Homerun Step Reward: De-emphasizes noise, rewards patience.
    """
    # Reduced delta weight (0.4x) to focus on the long-term goal
    delta_pnl = (curr_pnl_pct - prev_pnl_pct) * 0.4
    
    # context_bonus: ¿fue correcto aguantar este minuto?
    if curr_pnl_pct > 0.05:
        context_bonus = 0.01 * (1 + spot_momentum)
    elif curr_pnl_pct < -0.10 and recovery_rate < 0.35:
        context_bonus = -0.01 * (1 - recovery_rate)
    else:
        context_bonus = 0.0

    # Stronger hold-time incentive: linear growth to reward staying in the trade
    if curr_pnl_pct > -0.20:
        hold_bonus = 0.005 * (hold_time_minutes / 60.0)
    else:
        hold_bonus = 0.0
        
    # High-Water Mark Bonus: reward reaching new equity peaks
    hwm_bonus = 0.05 if is_new_hwm and curr_pnl_pct > 0 else 0.0

    # Trailing Drawdown Penalty: Gracefully penalize giving back gains
    drawdown_penalty = 0.0
    drawdown_tolerance = 0.35
    if trailing_drawdown > drawdown_tolerance:
        drawdown_penalty = (trailing_drawdown - drawdown_tolerance) * 0.02
    
    step_reward = delta_pnl + context_bonus + hold_bonus + hwm_bonus - drawdown_penalty
    return float(step_reward)


def compute_terminal_reward(final_pnl_pct: float, exit_type: str, 
                            hold_time_minutes: int) -> float:
    """
    V8-Homerun Terminal Reward: Convex incentives and 'Weak Hands' penalties.
    Optimized for 300%+ outliers.
    """
    if final_pnl_pct > 0:
        # Base winner multiplier
        base_reward = final_pnl_pct * 5.0
        
        # [NEW] Convex Bonus: Reward outliers exponentially (Jackpot effect)
        if final_pnl_pct > 1.0:
            base_reward += (final_pnl_pct ** 2) * 2.0
            
        # [NEW] Weak Hands Penalty: Penalize closing winners too early
        if hold_time_minutes < 45:
            base_reward *= 0.6  # 40% reduction for cowardly exits
            
        # Homerun patience bonus
        if hold_time_minutes > 90:
            base_reward += 5.0  
        elif hold_time_minutes > 60:
            base_reward += 2.0  
            
    elif exit_type == "agent_exit":
        # Loser: agent chose to exit manually
        base_reward = (final_pnl_pct / 0.50) * 4.0
        
        # Flee penalty: extra punishment for exiting before 15 mins
        if hold_time_minutes < 15:
            time_factor = (15 - hold_time_minutes) / 15.0
            base_reward -= (1.5 * time_factor)
            
    elif exit_type == "hard_stop_loss":
        base_reward = -5.0
    elif exit_type == "signal_reversal":
        base_reward = final_pnl_pct * 2.5
    else:
        base_reward = final_pnl_pct * 2.0
    
    return float(np.clip(base_reward, -6.0, 20.0))