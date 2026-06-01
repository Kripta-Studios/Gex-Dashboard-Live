"""
RL Reward Functions — Step (Dense) + Terminal (Sparse) + Sniper (Pre-Entry)

    PROFIT FACTOR STRATEGY:
    The reward function values positive convexity, but does not pay the
    agent simply for holding time. Preserving capital before the hard stop
    is materially better than waiting for a forced loss.

CHANGELOG v6:
- compute_step_reward ahora acepta y usa explícitamente los cuatro
  parámetros que environment.py pasa: recovery_rate, spot_momentum,
  trailing_drawdown, is_new_hwm.  Antes iban a **kwargs y se ignoraban,
  lo que inutilizaba la señal de densidad de recompensa v5/v6.
- recovery_rate: bonifica holdear cuando la probabilidad histórica de
  recuperación es alta (lookup de compute_recovery_stats).
- spot_momentum: pequeño refuerzo contextual si el subyacente va a favor.
- trailing_drawdown: penalización adicional proporcional al retroceso
  desde el máximo no realizado — disuade aguantar perdedores que ya
  tocaron un HWM y lo perdieron.
- is_new_hwm: bonificación puntual al marcar un nuevo máximo no realizado,
  para reforzar la convexidad positiva.

CHANGELOG v5 (previo):
- hold_incentive ASYMMETRIC: full incentive for winning/flat trades,
  scaled down for losing trades.
- Terminal reward scaled ×3.0.
- Step reward delta_pnl weight increased 0.3 → 1.0.
"""

import numpy as np


def compute_sniper_step_reward() -> float:
    return 0.0


def compute_step_reward(
    prev_pnl_pct: float,
    curr_pnl_pct: float,
    hold_time_minutes: int,
    theta_decay_per_minute: float = 0.0,
    recovery_rate: float = 0.3,
    spot_momentum: float = 0.0,
    trailing_drawdown: float = 0.0,
    is_new_hwm: bool = False,
) -> float:
    """
    Theta-adjusted step reward con señales de densidad v6.

    Componentes:
      1. delta_pnl − theta_decay   → señal base (counterfactual)
      2. drawdown_penalty          → penalización convexa por pérdida profunda
      3. trailing_drawdown_penalty → penalización por retroceso desde HWM
      4. recovery_bonus            → incentivo a holdear si la recuperación
                                     histórica es probable
      5. momentum_bonus            → contexto de subyacente a favor
      6. hwm_bonus                 → refuerzo puntual al marcar nuevo máximo

    Parámetros
    ----------
    prev_pnl_pct          PnL del step anterior (fracción de premium)
    curr_pnl_pct          PnL del step actual
    hold_time_minutes     Minutos en posición (no usado en cálculo, reservado)
    theta_decay_per_minute Decay theta por minuto (negativo, e.g. −0.005)
    recovery_rate         Probabilidad histórica de recuperación en este bucket
                          (delta × IV × PnL), de compute_recovery_stats.pkl
    spot_momentum         Indicador de tendencia del subyacente en [−1, 1],
                          positivo = subyacente sube (favorable para LONG)
    trailing_drawdown     Retroceso desde el máximo no realizado (≥ 0)
    is_new_hwm            True si este step marca un nuevo High Water Mark
    """
    # ── 1. Señal base: delta PnL ajustado por theta ──
    delta_pnl = curr_pnl_pct - prev_pnl_pct
    reward = delta_pnl + theta_decay_per_minute

    # ── 2. Penalización convexa por profundidad de pérdida ──
    # Holdear un perdedor profundo cuesta más por step que uno superficial
    if curr_pnl_pct < -0.10:
        drawdown_penalty = (curr_pnl_pct + 0.10) ** 2 * 0.5
        reward -= drawdown_penalty

    # ── 3. Penalización por trailing drawdown desde HWM ──
    # Si la posición ganó terreno y lo perdió, se penaliza el retroceso.
    # Escalado para que un retroceso del 30% desde HWM quite ~0.015 por step.
    if trailing_drawdown > 0.05:
        td_penalty = trailing_drawdown * 0.05
        reward -= td_penalty

    # ── 4. Bonus de recuperación — incentiva holdear cuando tiene sentido ──
    # Solo activo si estamos en pérdida moderada (−0.40 < pnl < 0) y la
    # probabilidad histórica de recuperar es alta. Evita premiar stubborn holds
    # cuando el bucket de recuperación es malo.
    if -0.40 < curr_pnl_pct < 0.0:
        # recovery_rate va de ~0.1 (bucket malo) a ~0.6 (bucket bueno)
        # El bonus máximo es pequeño (~0.005) para no dominar el delta_pnl
        recovery_bonus = (recovery_rate - 0.30) * 0.02
        reward += recovery_bonus

    # ── 5. Bonus de momentum — contexto del subyacente ──
    # spot_momentum en [−1, 1]. Si va a favor (>0) hay un pequeño incentivo
    # a mantenerse; si va en contra (<0) hay una pequeña penalización.
    # Acotado para no distorsionar la señal principal.
    momentum_bonus = float(np.clip(spot_momentum, -1.0, 1.0)) * 0.003
    reward += momentum_bonus

    # ── 6. Bonus puntual por nuevo HWM ──
    # Refuerza la convexidad positiva: cada vez que se marca un nuevo máximo
    # se da un pequeño bonus único.
    if is_new_hwm and curr_pnl_pct > 0.05:
        reward += 0.015

    return float(reward)



def compute_terminal_reward(final_pnl_pct: float, exit_type: str, 
                            hold_time_minutes: int) -> float:
    """
    Profit-factor terminal reward on a critic-friendly scale.
    """
    if exit_type == "hard_stop_loss":
        return -2.0
    
    if exit_type == "agent_exit":
        if final_pnl_pct > 0:
            if final_pnl_pct < 0.50 and hold_time_minutes < 60:
                # Penalty for taking small profits too early
                base_reward = final_pnl_pct * 1.0 - 0.50
            else:
                base_reward = final_pnl_pct * 4.0
                if final_pnl_pct > 1.0:
                    base_reward += (final_pnl_pct - 1.0) * 3.0
        else:
            base_reward = final_pnl_pct * 2.5
            
    elif exit_type == "signal_reversal":
        base_reward = final_pnl_pct * 3.0
    else:
        base_reward = final_pnl_pct * 4.0
        if final_pnl_pct > 1.0:
            base_reward += (final_pnl_pct - 1.0) * 3.0
            
    return float(np.clip(base_reward, -2.0, 4.0))