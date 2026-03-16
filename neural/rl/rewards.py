"""
RL Reward Functions — Step (Dense) + Terminal (Sparse) + Sniper (Pre-Entry)

HOMERUN STRATEGY:
The reward function is tuned to force the agent to HOLD winning trades
for 60-120 minutes, pursuing +300-400% returns on 0DTE options.
Early exits on profitable trades are severely punished (FOMO penalty).

CHANGELOG v4:
- BUG FIX: cowardice_penalty inicializada a 0.0 (evitaba NameError en ~60% episodios)
- BUG FIX: combined_exit_penalty = min(cowardice, upside) — sin doble penalización
- transaction_penalty = -1.0 flat (restaurado al original)
- confidence_scale aplicada solo a base_reward, no a transaction_penalty
- NUEVO: hold_incentive en compute_step_reward basado en TIEMPO independientemente
  del PnL actual. Antes solo se activaba con curr_pnl_pct > 0.05, lo que hacía
  que en los primeros 30-45 min el agente recibiera ~0.001 de incentive y saliera.
  Ahora recibe incentive por aguantar independientemente de si está verde o rojo.
"""

import numpy as np


def compute_sniper_step_reward() -> float:
    return 0.0


def compute_step_reward(prev_pnl_pct: float, curr_pnl_pct: float,
                        theta_vs_premium: float, minutes_to_close: float,
                        mae_ratio: float, hold_time_minutes: int = 0) -> float:
    # 1. Delta P&L
    delta_pnl = curr_pnl_pct - prev_pnl_pct

    # 2. Theta penalty
    theta_weight = 1.0 + 1.0 * np.exp(-minutes_to_close / 60.0)
    if curr_pnl_pct > 0.03:
        theta_penalty = 0.0
    else:
        theta_penalty = theta_vs_premium * theta_weight

    # 3. Drawdown penalty — only on new MAE extensions
    if curr_pnl_pct < mae_ratio and curr_pnl_pct < 0:
        drawdown_penalty = (curr_pnl_pct - mae_ratio) * 0.2
    else:
        drawdown_penalty = 0.0

    # 4. Hold incentive — basado en TIEMPO, independiente del PnL actual
    # CLAVE: el agente recibe incentive por aguantar aunque el trade esté plano o rojo
    # Esto evita que salga a los 30 min (el mínimo forzado) en cuanto puede
    if hold_time_minutes < 15:
        time_incentive = 0.002
    elif hold_time_minutes < 45:
        time_incentive = 0.015
    elif hold_time_minutes < 90:
        time_incentive = 0.04
    else:
        time_incentive = 0.06

    # Bonus adicional si el trade está en verde (mantener lógica original)
    if curr_pnl_pct > 0.05:
        pnl_bonus = 0.05
    elif curr_pnl_pct > 0.0:
        pnl_bonus = 0.01
    else:
        pnl_bonus = 0.0

    hold_incentive = time_incentive + pnl_bonus

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
    # 0. Volatility Scaling
    vol_scaled_pnl = final_pnl_pct * (0.15 / max(entry_iv, 0.05))

    # 1. Core P&L reward (asymmetric)
    if vol_scaled_pnl >= 0:
        pnl_reward = (vol_scaled_pnl * 2.0) + (vol_scaled_pnl ** 2.0) * 5.0
    else:
        pnl_reward = vol_scaled_pnl * 1.5

    # 2. Patience bonus
    if final_pnl_pct >= 1.00:
        patience_factor = min(hold_time_norm / 0.7, 1.0)
        time_bonus = final_pnl_pct * 0.5 * (0.5 + 1.5 * patience_factor)
    elif final_pnl_pct >= 0.03:
        patience_factor = min(hold_time_norm / 0.67, 1.0)
        time_bonus = final_pnl_pct * 1.5 * (0.2 + 0.8 * patience_factor)
    elif final_pnl_pct > 0.0 and hold_time_norm >= 0.05:
        time_bonus = final_pnl_pct * 0.1
    else:
        time_bonus = 0.0

    # 3. Hard stop penalty
    hard_stop_penalty = -1.0 if exit_type == "hard_stop_loss" else 0.0

    # 4. Strike quality bonus
    if abs(entry_delta) >= 0.50 and final_pnl_pct > 0:
        strike_bonus = 0.5
    elif 0.25 <= abs(entry_delta) <= 0.45 and final_pnl_pct > 0:
        strike_bonus = 0.1
    elif abs(entry_delta) >= 0.50:
        strike_bonus = 0.05
    else:
        strike_bonus = 0.0

    # 5. Combined exit penalty — BUG FIX: aplicar la más severa
    combined_exit_penalty = 0.0

    if exit_type == "agent_exit" and final_pnl_pct > 0 and max_move_pct > 0:
        capture_ratio = final_pnl_pct / max_move_pct
        missed_pct = max_move_pct - final_pnl_pct
        
        if capture_ratio < 0.30:
            upside_penalty = -4.0 * missed_pct * (1.0 - capture_ratio)
            combined_exit_penalty = max(upside_penalty, -20.0)
        elif capture_ratio < 0.50:
            cowardice_penalty = -2.0 * missed_pct * (1.0 - capture_ratio)
            combined_exit_penalty = max(cowardice_penalty, -20.0)

    # 6. Early exit penalty on losers
    early_exit_penalty = 0.0
    if exit_type == "agent_exit" and hold_time_norm < 0.10 and final_pnl_pct <= 0:
        early_exit_penalty = -0.3

    # 7. Entry timing bonus
    entry_timing_bonus = (min(entry_price_improvement * 5.0, 0.3)
                          if entry_price_improvement > 0 else 0.0)

    # 8. Transaction penalty — proporcional a la confianza
    transaction_penalty = -0.15 * (2.0 - mlp_confidence)

    base_reward = (pnl_reward + time_bonus + hard_stop_penalty
                   + strike_bonus + combined_exit_penalty + early_exit_penalty
                   + entry_timing_bonus)

    confidence_scale = 0.5 + mlp_confidence
    terminal_reward = base_reward * confidence_scale + transaction_penalty

    return float(np.clip(terminal_reward, -20.0, 500.0))