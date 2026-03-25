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
                        trailing_drawdown: float = 0.0) -> float:
    """
    V7 Step Reward: Oriented to decision quality and long-term stay.
    Including hold-time shaping to overcome noise floor.
    """
    delta_pnl = curr_pnl_pct - prev_pnl_pct
    
    # context_bonus: ¿fue correcto aguantar este minuto?
    if curr_pnl_pct > 0.05:
        context_bonus = 0.02 * (1 + spot_momentum)
    elif curr_pnl_pct < -0.10 and recovery_rate < 0.35:
        context_bonus = -0.015 * (1 - recovery_rate)
    else:
        context_bonus = 0.0

    # Hold-time shaping: small nonlinear bonus for staying in the trade
    # Gives +0.006 at 10m, +0.012 at 30m, +0.016 at 60m (doubled from v6)
    if curr_pnl_pct > -0.15:   # only for trades that aren't near the stop
        hold_bonus = 0.002 * min(hold_time_minutes, 60) ** 0.5
    else:
        hold_bonus = 0.0
        
    # Trailing Drawdown Penalty: Gracefully penalize giving back gains
    # To prevent micro-scalping, we only care if drawdown > 15% 
    # meaning we actually had some profits to lock in.
    drawdown_penalty = 0.0
    drawdown_tolerance = 0.15
    if trailing_drawdown > drawdown_tolerance:
        drawdown_penalty = (trailing_drawdown - drawdown_tolerance) * 0.05
    
    step_reward = delta_pnl + context_bonus + hold_bonus - drawdown_penalty
    return float(step_reward)


def compute_terminal_reward(final_pnl_pct: float, exit_type: str, 
                            hold_time_minutes: int) -> float:
    """
    V7 Terminal Reward: Optimized for Homerun Strategy.
    Prevents "fearful exits" by dynamic penalization.
    """
    if final_pnl_pct > 0:
        # Ganador: recompensar proporcionalmente al PnL y al tiempo aguantado
        base_reward = final_pnl_pct * 2.0
        # Homerun patience bonus (Issue: scale reward to overcome discount)
        if hold_time_minutes > 60:
            base_reward += final_pnl_pct * 3.0  
        elif hold_time_minutes > 30:
            base_reward += final_pnl_pct * 2.0
            
    elif exit_type == "agent_exit":
        # Loser: agent chose to exit manually
        
        # Strict linear penalty: -0.10 loss -> -0.40 reward. -0.50 loss (hard stop) -> -2.0 reward.
        base_reward = (final_pnl_pct / 0.50) * 2.0
        
        # Flee penalty: extra punishment for exiting before 10 mins (prevents micro-exits)
        if hold_time_minutes < 10:
            time_factor = (10 - hold_time_minutes) / 10.0 # 1.0 at minute 0, 0.1 at minute 9
            base_reward -= (0.50 * time_factor)
            
    elif exit_type == "hard_stop_loss":
        # Llegó al hard stop: máxima penalización (reduced to -2.0 to prevent over-correction)
        base_reward = -2.0
    elif exit_type == "signal_reversal":
        # Inversión de señal (GBM flip): recompensa neutral/PnL 
        # (similar al time close pero identificado explícitamente)
        base_reward = final_pnl_pct * 1.2 # Pequeño bono por "salvación"
    else:
        # Otros casos (time close, etc.)
        base_reward = final_pnl_pct * 1.0
    
    return float(max(base_reward, -2.0))