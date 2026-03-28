"""
PPO Training Pipeline — Walk-Forward RL Training

Matches the MLP's temporal split protocol:
- 3-month train windows, 1-month test windows
- Curriculum learning: high-conf → medium → full
- GAE advantage estimation, clipped PPO objective
"""

import os
import sys
import time
import json
import pickle
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEURAL_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, NEURAL_DIR)

from .config import RL_CONFIG
from .agent import PPOAgent
from .environment import SPXOptionsEnv
from .utils import RunningMeanStd, CurriculumScheduler, RolloutBuffer, augment_state
from .evaluate import evaluate_agent


def compute_gae(rewards: list, values: list, dones: list,
                gamma: float = None, gae_lambda: float = None) -> np.ndarray:
    """
    Generalized Advantage Estimation (GAE, λ=0.95).

    Returns: array of discounted returns (rewards-to-go with advantage).
    """
    gamma = gamma or RL_CONFIG["gamma"]
    gae_lambda = gae_lambda or RL_CONFIG["gae_lambda"]

    n = len(rewards)
    returns = np.zeros(n, dtype=np.float32)
    gae = 0.0

    for t in reversed(range(n)):
        if t == n - 1:
            next_value = 0.0
        else:
            next_value = values[t + 1]

        delta = rewards[t] + gamma * next_value * (1.0 - float(dones[t])) - values[t]
        gae = delta + gamma * gae_lambda * (1.0 - float(dones[t])) * gae
        returns[t] = gae + values[t]

    return returns


class PPOTrainer:
    """
    PPO trainer with walk-forward splits matching MLP protocol.
    """

    def __init__(self, agent: PPOAgent, env: SPXOptionsEnv,
                 device: torch.device = None, num_workers: int = 1,
                 episode_index_path: str = None, options_cache_dir: str = None):
        self.agent = agent
        self.env = env
        self.device = device or torch.device(
            "cuda" if torch.cuda.is_available() else "cpu")
        self.agent.to(self.device)
        self.num_workers = num_workers

        # Split parameters into policy and value groups (Fix 2)
        policy_params = []
        value_params  = []
        for name, param in self.agent.named_parameters():
            if "value" in name or "critic" in name:
                value_params.append(param)
            else:
                policy_params.append(param)

        self.optimizer = optim.Adam([
            {"params": policy_params, "lr": RL_CONFIG["learning_rate"]},       # 3e-5
            {"params": value_params,  "lr": RL_CONFIG["learning_rate"] * 5},   # 1.5e-4
        ], weight_decay=1e-4)

        # Fix 6: Decoupled LR Decay (Issue: value head needs higher floor)
        def get_lr_lambda(group_idx):
            def _lambda(step):
                # Warmup (First 20 steps)
                if step < 20:
                    return 0.3 + 0.7 * (step / 20.0)
                # Platform (20 to 250)
                if step < 250:
                    return 1.0
                # Decay (250 to 500+)
                total_updates = RL_CONFIG.get("total_updates", 500)
                decay_steps = total_updates - 250
                if decay_steps <= 0: return 1.0
                
                prog = min((step - 250) / float(decay_steps), 1.0)
                floor = RL_CONFIG.get("value_lr_decay_floor", 0.4) if group_idx == 1 else 0.2
                return 1.0 - (1.0 - floor) * prog
            return _lambda

        self.scheduler = optim.lr_scheduler.LambdaLR(
            self.optimizer, 
            lr_lambda=[get_lr_lambda(0), get_lr_lambda(1)]
        )
        
        # Split verification (Fix 2)
        print("\n================================")
        print("  OPTIMIZER PARAMETER GROUPS")
        print("================================")
        for i, group in enumerate(self.optimizer.param_groups):
            n_params = sum(p.numel() for p in group["params"])
            lr = group["lr"]
            role = "VALUE/CRITIC" if lr > RL_CONFIG["learning_rate"] else "POLICY/BACKBONE"
            print(f"  Group {i} ({role:15}): {n_params:6d} params | LR={lr:.2e}")
        print("================================\n")

        self.reward_normalizer = RunningMeanStd()
        self.curriculum = CurriculumScheduler()
        self.best_profit_factor = 0.0

        # Fix 6: Chronological Date Split (80/20) for Train/Eval Separation
        # Ensures evaluation is always out-of-sample relative to training data
        all_dates = sorted(self.env.episode_index['date'].unique())
        split_idx = int(len(all_dates) * 0.8)
        self.train_dates = all_dates[:split_idx]
        self.eval_dates  = all_dates[split_idx:]
        print(f"[RL] Date Split: {len(self.train_dates)} train days, {len(self.eval_dates)} eval days.")

        # Multiprocessing pool
        self.pool = None
        if self.num_workers > 1 and episode_index_path and options_cache_dir:
            from concurrent.futures import ProcessPoolExecutor
            # Reduce max days based on worker count to prevent MemoryError
            worker_max_days = max(2, int(150 / self.num_workers))
            self.pool = ProcessPoolExecutor(
                max_workers=self.num_workers,
                initializer=init_worker,
                initargs=(
                    episode_index_path, 
                    options_cache_dir, 
                    worker_max_days, 
                    env.feature_columns,
                    RL_CONFIG["state_dim"],
                    RL_CONFIG["hidden_dims"]
                )
            )
            print(f"[RL] Initialized multiprocessing pool with {self.num_workers} workers.")

        # Training history
        self.history = {
            "update_step": [],
            "mean_reward": [],
            "mean_pnl_pct": [],
            "profit_factor": [],
            "win_rate": [],
            "mean_hold_minutes": [],
            "hard_stop_rate": [],
            "phase": [],
        }

        # Pre-compute direction indices for balanced sampling (anti-bias)
        self._long_indices_train = self.env.episode_index[
            (self.env.episode_index['mlp_direction'] == 'LONG') &
            (self.env.episode_index['date'].isin(self.train_dates))
        ].index.tolist()
        self._short_indices_train = self.env.episode_index[
            (self.env.episode_index['mlp_direction'] == 'SHORT') &
            (self.env.episode_index['date'].isin(self.train_dates))
        ].index.tolist()
        self._long_indices_eval = self.env.episode_index[
            (self.env.episode_index['mlp_direction'] == 'LONG') &
            (self.env.episode_index['date'].isin(self.eval_dates))
        ].index.tolist()
        self._short_indices_eval = self.env.episode_index[
            (self.env.episode_index['mlp_direction'] == 'SHORT') &
            (self.env.episode_index['date'].isin(self.eval_dates))
        ].index.tolist()
        print(f"[RL] Balanced sampling: Train L={len(self._long_indices_train)} S={len(self._short_indices_train)} | "
              f"Eval L={len(self._long_indices_eval)} S={len(self._short_indices_eval)}")

    def collect_episodes(self, n_episodes: int, min_confidence: float = 0.60,
                         min_strike: int = 0,
                         training: bool = True, update_step: int = 0, total_updates: int = 400,
                         logit_noise_level: float = 0.0, obs_noise: bool = True) -> tuple:
        """
        Collect n_episodes by running the current policy in the environment.
        Uses multiprocessing pool if self.num_workers > 1 and training is True.
        """
        buffer = RolloutBuffer()
        episode_infos = []
        
        phase_info = self.curriculum.get_phase_info(update_step)
        min_confidence = phase_info["min_confidence"]
        min_strike = phase_info["min_strike_bucket"]
        max_strike = phase_info.get("max_strike_bucket", 6)
        min_hold = phase_info.get("min_hold_minutes", 0)
        curriculum_phase = phase_info["phase"]

        if self.pool is not None and training:
            # Move agent weights to CPU to be safely serialized
            self.agent.cpu()
            state_dict = {k: v.cpu() for k, v in self.agent.state_dict().items()}
            self.agent.to(self.device)
            
            # --- Direction-balanced sampling from date-restricted pool ---
            long_pool = self._long_indices_train if training else self._long_indices_eval
            short_pool = self._short_indices_train if training else self._short_indices_eval
            
            if not long_pool and not short_pool:
                print(f"  [!] No eligible episodes for {'train' if training else 'eval'}")
                return buffer, episode_infos

            futures = []
            for i in range(n_episodes):
                # Alternate 50/50 between LONG and SHORT episodes
                if long_pool and short_pool:
                    pool_to_use = long_pool if i % 2 == 0 else short_pool
                elif long_pool:
                    pool_to_use = long_pool
                else:
                    pool_to_use = short_pool
                ep_idx = np.random.choice(pool_to_use)
                futures.append(self.pool.submit(
                    worker_collect, state_dict, min_confidence, min_strike, max_strike, min_hold,
                    curriculum_phase, update_step, total_updates, logit_noise_level, ep_idx, obs_noise
                ))
                
            import concurrent.futures
            collected = 0
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res is not None:
                    (e_states, e_actions, e_action_types, 
                     e_rewards, e_log_probs, e_values, e_dones, info) = res
                     
                    returns = compute_gae(e_rewards, e_values, e_dones)
                    self.reward_normalizer.update(np.array(e_rewards))
                    
                    for i in range(len(e_states)):
                        buffer.add(
                            state=e_states[i],
                            action=e_actions[i],
                            action_type=e_action_types[i],
                            reward=float(returns[i]),
                            log_prob=e_log_probs[i],
                            value=e_values[i],
                            done=e_dones[i],
                        )
                    
                    if info.get("final_pnl_pct") is not None:
                        episode_infos.append(info)
                    
                    collected += 1
            
            return buffer, episode_infos

        # single-threaded fallback (used for eval and non-pool)
        self.agent.eval()

        # Direction-balanced sampling (single-threaded path)
        long_pool = self._long_indices_train if training else self._long_indices_eval
        short_pool = self._short_indices_train if training else self._short_indices_eval
        
        # Apply confidence filter
        if min_confidence > 0:
            conf_series = self.env.episode_index["mlp_confidence"]
            long_pool = [i for i in long_pool if conf_series.iloc[i] >= min_confidence] if long_pool else []
            short_pool = [i for i in short_pool if conf_series.iloc[i] >= min_confidence] if short_pool else []

        if not long_pool and not short_pool:
            print(f"[RL] Warning: no episodes with confidence >= {min_confidence} for {'train' if training else 'eval'} split.")
            # Fallback: use all direction indices without confidence filter
            long_pool = self._long_indices_train if training else self._long_indices_eval
            short_pool = self._short_indices_train if training else self._short_indices_eval
            if not long_pool and not short_pool:
                print(f"[RL] Critical: No episodes found for {'train' if training else 'eval'} split.")
                return buffer, episode_infos


        collected = 0
        max_attempts = n_episodes * 3

        for attempt in range(max_attempts):
            if collected >= n_episodes:
                break

            # Alternate 50/50 between LONG and SHORT
            if long_pool and short_pool:
                pool_to_use = long_pool if attempt % 2 == 0 else short_pool
            elif long_pool:
                pool_to_use = long_pool
            else:
                pool_to_use = short_pool
            idx = np.random.choice(pool_to_use)
            self.env._current_min_confidence = min_confidence
            self.env._current_min_strike_bucket = min_strike
            self.env._current_max_strike_bucket = phase_info.get("max_strike_bucket", 6)
            state = self.env.reset(episode_idx=idx)

            episode_states = []
            episode_actions = []
            episode_action_types = []
            episode_rewards = []
            episode_log_probs = []
            episode_values = []
            episode_dones = []

            done = False
            step_count = 0

            while not done and step_count < RL_CONFIG["session_length_minutes"]:
                state_input = augment_state(state) if obs_noise else state
                state_tensor = torch.FloatTensor(state_input).unsqueeze(0).to(self.device)

                with torch.no_grad():
                    if self.env._position is None and self.env._sniper_mode:
                        action_type = "sniper_entry"
                    elif self.env._position is None:
                        action_type = "strike"
                    else:
                        action_type = "exit"

                    # Apply logit noise for strike exploration in early Phase 1
                    l_noise = 0.5 if training and update_step < (total_updates * 0.1) and action_type == "strike" else 0.0
                    
                    action, log_prob, value = self.agent.get_action(
                        state_tensor, action_type, deterministic=not training, logit_noise=l_noise)

                # action is now an int (strike bucket, sniper choice, or exit choice)
                env_action = action
                log_prob_float = log_prob.item() if isinstance(log_prob, torch.Tensor) else log_prob
                value_float = value.item() if isinstance(value, torch.Tensor) else value

                next_state, reward, done, info = self.env.step(env_action)

                episode_states.append(state)
                episode_actions.append(env_action)
                episode_action_types.append(action_type)
                episode_rewards.append(reward)
                episode_log_probs.append(log_prob_float)
                episode_values.append(value_float)
                episode_dones.append(done)

                state = next_state
                step_count += 1

            if step_count == 0:
                continue

            # Compute GAE returns for this episode
            returns = compute_gae(
                episode_rewards, episode_values, episode_dones)

            # Normalize rewards
            self.reward_normalizer.update(np.array(episode_rewards))

            # Add to buffer with GAE returns replacing raw rewards
            for i in range(len(episode_states)):
                buffer.add(
                    state=episode_states[i],
                    action=episode_actions[i],
                    action_type=episode_action_types[i],
                    reward=float(returns[i]),  # GAE return, not raw reward
                    log_prob=episode_log_probs[i],
                    value=episode_values[i],
                    done=episode_dones[i],
                )

            if info.get("final_pnl_pct") is not None:
                episode_infos.append(info)

            collected += 1

        return buffer, episode_infos

    def ppo_update(self, buffer: RolloutBuffer, update_step: int = 0) -> dict:
        """Run PPO clipped objective update with entropy annealing and KL stopping."""
        
        # Scheduled base entropy coefficient (annealed)
        progress = min(update_step / RL_CONFIG.get("entropy_anneal_end", 350), 1.0)
        base_coeff  = RL_CONFIG["entropy_coeff"]
        floor_coeff = RL_CONFIG.get("entropy_coeff_min", 0.04)
        current_coeff = base_coeff - (base_coeff - floor_coeff) * progress
        
        kl_target = RL_CONFIG.get("kl_target", 0.015)
        entropy_target = RL_CONFIG.get("entropy_target", 0.05)
        
        self.agent.train()
        total_policy_loss = total_value_loss = total_entropy_loss = 0.0
        total_mean_entropy = 0.0
        total_approx_kl = 0.0
        n_batches = 0

        # Per-head entropy for diagnostics (Issue 1)
        total_h_strike = 0.0
        total_h_exit = 0.0

        for epoch in range(RL_CONFIG["ppo_epochs"]):
            epoch_kls = []
            for batch in buffer.get_batches(RL_CONFIG["batch_size"]):
                states = batch["states"].to(self.device)
                actions = batch["actions"]
                action_types = batch["action_types"]
                old_log_probs = batch["old_log_probs"].to(self.device)
                returns = batch["returns"].to(self.device)

                if states.shape[0] < 2:
                    continue

                # ── Recompute log_probs, entropy, and values with CURRENT weights (Fix 4) ──
                log_probs, entropy, values = self.agent.evaluate_actions(
                    states, actions, action_types)

                if update_step == 0 and epoch == 0 and n_batches == 0:
                    print(f"\n[DEBUG] Entropy sample: min={entropy.min():.4f} "
                          f"max={entropy.max():.4f} mean={entropy.mean():.4f}")
                    print(f"[DEBUG] Action types sample: {action_types[:10]}")

                # ── Advantages computed fresh, using current V_θ (Fix 4) ──
                # Use .detach() on the value prediction used for advantages to separate gradients
                advantages = returns - values.detach()
                adv_std = advantages.std(unbiased=False)
                advantages = (advantages - advantages.mean()) / (adv_std + 1e-8)

                # ── PPO clipped objective ──
                ratio = torch.exp(log_probs - old_log_probs)
                
                # Track approximate KL for early stopping
                with torch.no_grad():
                    approx_kl = ((ratio - 1) - torch.log(ratio)).mean().item()
                    epoch_kls.append(approx_kl)
                
                clip_eps = RL_CONFIG["clip_epsilon"]
                surr1 = ratio * advantages
                surr2 = torch.clamp(ratio, 1.0 - clip_eps, 1.0 + clip_eps) * advantages
                policy_loss = -torch.min(surr1, surr2).mean()

                # ── Per-head entropy for diagnostics (Issue 1) ──
                with torch.no_grad():
                    # Map action types to indices for boolean masking
                    is_strike_batch = torch.tensor([at != "exit" for at in action_types], device=self.device)
                    is_exit_batch = ~is_strike_batch
                    
                    h_strike = entropy[is_strike_batch].mean().item() if is_strike_batch.any() else 0.0
                    h_exit = entropy[is_exit_batch].mean().item() if is_exit_batch.any() else 0.0

                # ── Normalized Value Loss (Issue 3) ──
                # Use batch-wise std to scale returns/values to stable range (~N(0,1))
                # Clamp at 1.0 to avoid inflating loss during low-variance early steps
                ret_std = returns.std().clamp(min=1.0)
                value_loss = nn.MSELoss()(values / ret_std, returns / ret_std)

                # ── Entropy bonus (Conditional Regularization) ──
                # Issue: Emergency boost must be per-sample to avoid masking collapse (Strike H masks Exit H)
                exit_tgt = RL_CONFIG.get("exit_entropy_target", 0.40)
                strike_tgt = RL_CONFIG.get("entropy_target", 0.25)
                
                mean_ent_val = entropy.mean().item() # for logging

                coeffs = []
                for i, at in enumerate(action_types):
                    e_val = entropy[i].item()
                    
                    if at == "sniper_entry":
                        coeffs.append(RL_CONFIG.get("sniper_entropy_coeff", 0.10))
                        continue
                    
                    tgt = exit_tgt if at == "exit" else strike_tgt
                    deficit_ratio = max(0.0, (tgt - e_val) / tgt)
                    
                    # Emergency multiplier only kicks in when deficit > 30% of target (Issue: overcorrection)
                    if deficit_ratio > 0.30:
                        em = 1.0 + deficit_ratio * 3.0
                    else:
                        em = 1.0
                    
                    base = current_coeff * (1.1 if at == "exit" else 1.0)
                    # Hard cap: never exceed 2x current_coeff to prevent entropy dominating policy loss
                    coeffs.append(min(base * em, current_coeff * 2.0))
                
                per_sample_coeff = torch.tensor(coeffs, dtype=torch.float32, device=self.device)
                entropy_loss = -(entropy * per_sample_coeff).mean()

                # Total loss
                # Values and returns both normalized by ret_std — stable scale regardless of hold duration
                loss = (policy_loss
                        + RL_CONFIG["value_loss_coeff"] * value_loss
                        + entropy_loss)

                if not torch.isfinite(loss):
                    continue

                self.optimizer.zero_grad()
                loss.backward()

                # Gradient cleaning & clipping
                for p in self.agent.parameters():
                    if p.grad is not None:
                        p.grad.nan_to_num_(nan=0.0, posinf=0.0, neginf=0.0)

                # Separate, tighter clipping for value head to prevent spikes during hold duration shifts (Issue 3)
                value_params = list(self.agent.value_head.parameters())
                nn.utils.clip_grad_norm_(value_params, max_norm=1.0)

                # Clip only non-value parameters to max_grad_norm (Issue 3 Fix: avoid double-clipping)
                non_value_params = [p for p in self.agent.parameters() if not any(p is vp for vp in value_params)]
                nn.utils.clip_grad_norm_(non_value_params, RL_CONFIG["max_grad_norm"])
                self.optimizer.step()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy_loss += entropy_loss.item()
                total_mean_entropy += mean_ent_val
                
                # Diagnostics (Issue 1)
                total_h_strike += h_strike
                total_h_exit += h_exit

                total_approx_kl += approx_kl
                n_batches += 1
            
            # KL early stopping (Fix 1)
            if epoch_kls and np.mean(epoch_kls) > kl_target:
                break

        n_batches = max(n_batches, 1)
        return {
            "policy_loss":  total_policy_loss / n_batches,
            "value_loss":   total_value_loss / n_batches,
            "entropy_loss": total_entropy_loss / n_batches,
            "mean_entropy": total_mean_entropy / n_batches,
            "h_strike":     total_h_strike / n_batches,
            "h_exit":       total_h_exit / n_batches,
            "approx_kl":    total_approx_kl / n_batches,
        }

    def train(self, save_dir: str = "../rl_models",
              log_interval: int = 5,
              eval_interval: int = 25) -> dict:
        """
        Full training loop with walk-forward splits.
        Enhanced with ETA, overfitting detection, and rolling stats.
        """
        os.makedirs(save_dir, exist_ok=True)
        total_updates = RL_CONFIG["total_updates"]
        n_episodes = RL_CONFIG["n_episodes_per_update"]
        eval_pf = 0

        print("=" * 70)
        print("PPO-RL TRAINING — SPX 0DTE OPTIONS AGENT")
        print("=" * 70)
        print(f"  Total updates:     {total_updates}")
        print(f"  Episodes/update:   {n_episodes}")
        print(f"  PPO epochs:        {RL_CONFIG['ppo_epochs']}")
        print(f"  Batch size:        {RL_CONFIG['batch_size']}")
        print(f"  Log interval:      every {log_interval} steps")
        print(f"  Eval interval:     every {eval_interval} steps")
        print(f"  Device:            {self.device}")
        print(f"  State dim:         {RL_CONFIG['state_dim']}")
        print("=" * 70)

        # Rolling stats for smoothed progress
        ROLLING_WINDOW = 20
        rolling_pf = []
        rolling_wr = []
        rolling_pnl = []
        rolling_policy_loss = []
        rolling_value_loss = []
        rolling_entropy = []
        rolling_mean_entropy = []
        rolling_kl = []
        step_times = []
        self._next_logit_noise = 0.0

        # Eval history for overfitting comparison
        eval_history = {
            "step": [], "eval_pf": [], "eval_wr": [], "eval_pnl": [],
            "train_pf": [], "train_wr": [], "train_pnl": [],
            "stochastic_train_pf": [], # Added for Issue 2
        }

        train_start = time.time()

        for update_step in range(total_updates):
            t_start = time.time()

            # Fix 7: Dynamic Logit Noise (PREVIOUSLY calculated level)
            noise_level = getattr(self, "_next_logit_noise", 0.0)
            
            # Get curriculum phase (interpolated)
            phase_info = self.curriculum.get_phase_info(update_step)
            min_conf = phase_info["min_confidence"]

            # Propagate curriculum to environment
            min_strike = phase_info["min_strike_bucket"]
            self.env._curriculum_phase = phase_info["phase"]
            self.env._current_min_confidence = min_conf
            self.env._current_min_strike_bucket = min_strike
            self.env._current_max_strike_bucket = phase_info.get("max_strike_bucket", 6)
            self.env._current_min_hold_minutes = phase_info.get("min_hold_minutes", 0)
            
            # Sniper min_wait lookup
            sniper_curriculum = RL_CONFIG.get("sniper_min_wait_curriculum", {})
            self.env._current_min_wait = sniper_curriculum.get(phase_info["phase"], {"min_wait": 0}).get("min_wait", 0)

            # Collect episodes with dynamic noise
            buffer, episode_infos = self.collect_episodes(
                n_episodes=n_episodes,
                min_confidence=min_conf,
                min_strike=min_strike,
                training=True,
                update_step=update_step,
                total_updates=total_updates,
                logit_noise_level=noise_level,
                obs_noise=True # Training uses observation noise
            )

            if len(buffer) == 0:
                print(f"[{update_step}] No data collected, skipping...")
                continue

            # PPO update
            losses = self.ppo_update(buffer, update_step=update_step)
            self.scheduler.step()

            # Compute episode-level statistics
            pnl_pcts = [info["final_pnl_pct"] for info in episode_infos
                        if "final_pnl_pct" in info]
            hold_mins = [info["hold_minutes"] for info in episode_infos
                         if "hold_minutes" in info]
            exit_types = [info["exit_type"] for info in episode_infos
                          if "exit_type" in info]
            directions = [info.get("direction", "?") for info in episode_infos]

            # Sniper stats
            sniper_waits = [info.get("sniper_minutes_waited", 0) for info in episode_infos
                            if "sniper_minutes_waited" in info]
            sniper_timeouts = sum(1 for info in episode_infos
                                 if info.get("exit_type") == "sniper_timeout")

            if pnl_pcts:
                wins = [p for p in pnl_pcts if p > 0]
                losses_list = [p for p in pnl_pcts if p <= 0]
                win_rate = len(wins) / len(pnl_pcts) if pnl_pcts else 0
                pf_num = sum(wins) if wins else 0
                pf_den = abs(sum(losses_list)) if losses_list else 1e-6
                profit_factor = pf_num / pf_den if pf_den > 0 else 0
                mean_pnl = np.mean(pnl_pcts)
                mean_hold = np.mean(hold_mins) if hold_mins else 0
                hard_stop_count = sum(1 for e in exit_types if e == "hard_stop_loss")
                hard_stop_rate = hard_stop_count / len(exit_types) if exit_types else 0
            else:
                win_rate = profit_factor = mean_pnl = mean_hold = hard_stop_rate = 0

            mean_sniper_wait = np.mean(sniper_waits) if sniper_waits else 0

            # Direction balance
            n_long = sum(1 for d in directions if d == "LONG")
            n_short = sum(1 for d in directions if d == "SHORT")
            n_total_dir = max(n_long + n_short, 1)

            # Update rolling stats
            rolling_pf.append(profit_factor)
            rolling_wr.append(win_rate)
            rolling_pnl.append(mean_pnl)
            # Track Stochastic Train PF (Issue 2)
            # Collect 64 episodes (increased for statistical significance) on train dates without noise
            with torch.no_grad():
                _, s_infos = self.collect_episodes(
                    n_episodes=64,
                    training=True, 
                    update_step=update_step,
                    logit_noise_level=0.0,
                    obs_noise=False 
                )
            s_pf = 0.0
            if s_infos:
                s_wins = sum(1 for info in s_infos if info.get("final_pnl_pct", 0) > 0)
                s_losses = sum(1 for info in s_infos if info.get("final_pnl_pct", 0) < 0)
                s_total_win = sum(info.get("final_pnl_pct", 0) for info in s_infos if info.get("final_pnl_pct", 0) > 0)
                s_total_loss = abs(sum(info.get("final_pnl_pct", 0) for info in s_infos if info.get("final_pnl_pct", 0) < 0))
                s_pf = s_total_win / s_total_loss if s_total_loss > 0 else (2.0 if s_total_win > 0 else 1.0)

            # Logging
            rolling_policy_loss.append(losses["policy_loss"])
            rolling_value_loss.append(losses["value_loss"])
            rolling_entropy.append(losses["entropy_loss"])
            rolling_mean_entropy.append(losses.get("mean_entropy", 0.05))
            rolling_kl.append(losses.get("approx_kl", 0))

            # Keep only last ROLLING_WINDOW
            if len(rolling_pf) > ROLLING_WINDOW:
                rolling_pf.pop(0)
                rolling_wr.pop(0)
                rolling_pnl.pop(0)
                rolling_policy_loss.pop(0)
                rolling_value_loss.pop(0)
                rolling_entropy.pop(0)
                rolling_mean_entropy.pop(0)
                rolling_kl.pop(0)

            # Fix 7: Calculate noise for the NEXT step based on RAW mean entropy
            r_h_raw = np.mean(rolling_mean_entropy) if rolling_mean_entropy else 0.08
            if r_h_raw < 0.035:
                self._next_logit_noise = min((0.035 - r_h_raw) * 10.0, 1.5)
            else:
                self._next_logit_noise = 0.0

            # Save history
            self.history["update_step"].append(update_step)
            self.history["mean_reward"].append(float(np.mean(buffer.rewards)) if buffer.rewards else 0)
            self.history["mean_pnl_pct"].append(mean_pnl)
            self.history["profit_factor"].append(profit_factor)
            self.history["win_rate"].append(win_rate)
            self.history["mean_hold_minutes"].append(mean_hold)
            self.history["hard_stop_rate"].append(hard_stop_rate)
            self.history["phase"].append(phase_info["phase"])

            elapsed = time.time() - t_start
            step_times.append(elapsed)
            if len(step_times) > 50:
                step_times.pop(0)

            # ETA calculation
            avg_step_time = np.mean(step_times)
            remaining_steps = total_updates - update_step - 1
            eta_seconds = remaining_steps * avg_step_time
            eta_min = eta_seconds / 60

            # ─── PROGRESS LOG ───
            if update_step % log_interval == 0 or update_step == total_updates - 1:
                pct_done = (update_step + 1) / total_updates * 100
                bar_len = 25
                filled = int(bar_len * (update_step + 1) / total_updates)
                bar = "█" * filled + "░" * (bar_len - filled)

                # Rolling averages (protect vs empty)
                r_pf = np.mean(rolling_pf) if rolling_pf else 1.0
                r_wr = np.mean(rolling_wr) if rolling_wr else 0.5
                r_pnl = np.mean(rolling_pnl) if rolling_pnl else 0.0
                r_pi = np.mean(rolling_policy_loss) if rolling_policy_loss else 0.0
                r_v = np.mean(rolling_value_loss) if rolling_value_loss else 0.0
                r_h = np.mean(rolling_mean_entropy) if rolling_mean_entropy else 0.08
                r_kl = np.mean(rolling_kl) if rolling_kl else 0.0

                # Issue 1: Display per-head entropy to detect collapse early
                h_s = losses.get("h_strike", 0.0)
                h_e = losses.get("h_exit", 0.0)

                print(f"\n  [{bar}] {pct_done:5.1f}% | Update {update_step}/{total_updates} | "
                      f"ETA: {eta_min:.1f}min | Phase {phase_info['phase']}")
                print(f"  ├─ Current:    PF={profit_factor:.2f} WR={win_rate:.1%} "
                      f"PnL={mean_pnl:+.4f} Hold={mean_hold:.0f}m "
                      f"L/S={n_long}/{n_short} Stop={hard_stop_rate:.0%}")
                
                # Manual request: explicit Entropy and KL monitor
                print(f"  ├─ Entropy:    {r_h:.4f} (target: 0.03-0.10) H[S/E]={h_s:.2f}/{h_e:.2f}")
                print(f"  ├─ Approx KL:  {losses.get('approx_kl', 0):.4f} (avg:{r_kl:.4f})")

                if RL_CONFIG.get("use_sniper_mode"):
                    print(f"  ├─ Sniper:     AvgWait={mean_sniper_wait:.1f}m "
                          f"Timeouts={sniper_timeouts}/{len(episode_infos)}")
                
                print(f"  ├─ Rolling{ROLLING_WINDOW:2d}: PF={r_pf:.2f} WR={r_wr:.1%} "
                      f"PnL={r_pnl:+.4f}")
                print(f"  ├─ Losses:     π={losses['policy_loss']:.4f} V={losses['value_loss']:.4f} "
                      f"(avg: π={r_pi:.4f} V={r_v:.4f})")
                print(f"  └─ Timing:     {elapsed:.1f}s/step | "
                      f"Total: {(time.time()-train_start)/60:.1f}min")

            # ─── EVAL + OVERFITTING CHECK ───
            if update_step > 0 and update_step % eval_interval == 0:
                print(f"\n  {'─'*60}")
                print(f"  📊 EVAL CHECKPOINT (step {update_step})")
                print(f"  {'─'*60}")

                # Collect eval episodes (no augmentation, deterministic)
                eval_buffer, eval_infos = self.collect_episodes(
                    n_episodes=min(n_episodes, 200),
                    min_confidence=min_conf,
                    min_strike=min_strike,
                    training=False,  # No augmentation, deterministic
                    update_step=update_step,
                    obs_noise=False # No observation noise for eval
                )

                eval_pnls = [info["final_pnl_pct"] for info in eval_infos
                             if "final_pnl_pct" in info]

                if eval_pnls:
                    eval_wins = [p for p in eval_pnls if p > 0]
                    eval_losses = [p for p in eval_pnls if p <= 0]
                    eval_wr = len(eval_wins) / len(eval_pnls)
                    eval_pf_num = sum(eval_wins) if eval_wins else 0
                    eval_pf_den = abs(sum(eval_losses)) if eval_losses else 1e-6
                    eval_pf = eval_pf_num / eval_pf_den if eval_pf_den > 0 else 0
                    eval_mean_pnl = np.mean(eval_pnls)
                else:
                    eval_wr = eval_pf = eval_mean_pnl = 0

                # Use rolling train stats for comparison
                train_pf_avg = np.mean(rolling_pf)
                train_wr_avg = np.mean(rolling_wr)
                train_pnl_avg = np.mean(rolling_pnl)

                eval_history["step"].append(update_step)
                eval_history["eval_pf"].append(eval_pf)
                eval_history["eval_wr"].append(eval_wr)
                eval_history["eval_pnl"].append(eval_mean_pnl)
                eval_history["train_pf"].append(train_pf_avg)
                eval_history["train_wr"].append(train_wr_avg)
                eval_history["train_pnl"].append(train_pnl_avg)
                eval_history["stochastic_train_pf"].append(s_pf) # Added for Issue 2

                print(f"  {'Metric':<18} {'Train (rolling)':>16} {'Eval (determ.)':>16} {'Gap':>10}")
                print(f"  {'─'*60}")
                print(f"  {'Profit Factor':<18} {train_pf_avg:>16.2f} {eval_pf:>16.2f} "
                      f"{train_pf_avg - eval_pf:>+10.2f}")
                print(f"  {'Win Rate':<18} {train_wr_avg:>15.1%} {eval_wr:>15.1%} "
                      f"{(train_wr_avg - eval_wr)*100:>+9.1f}%")
                print(f"  {'Mean PnL':<18} {train_pnl_avg:>+16.4f} {eval_mean_pnl:>+16.4f} "
                      f"{train_pnl_avg - eval_mean_pnl:>+10.4f}")

                # Overfitting warnings
                pf_gap = train_pf_avg - eval_pf
                wr_gap = train_wr_avg - eval_wr

                if pf_gap > 0.5 and eval_pf < 1.0:
                    print(f"\n  ⚠️  OVERFITTING WARNING: Train PF >> Eval PF "
                          f"(gap={pf_gap:.2f}). Policy memorizing train episodes.")
                elif pf_gap > 0.3:
                    print(f"\n  ⚡ Mild overfitting: PF gap = {pf_gap:.2f}. Monitor closely.")
                elif eval_pf > train_pf_avg and eval_pf > 1.0:
                    print(f"\n  ✅ Healthy: Eval PF ({eval_pf:.2f}) ≥ Train PF ({train_pf_avg:.2f})")
                print(f"  Train:      PF {train_pf_avg:.2f} | WR {train_wr_avg:.1%} | PnL {train_pnl_avg:+.2%}")
                print(f"  StochTrain: PF {s_pf:.2f} (clean states)")
                if eval_pf > 0:
                    pass # Already printed above
                if eval_wr < 0.40:
                    print(f"  ⚠️  LOW EVAL WIN RATE: {eval_wr:.1%} — agent may be guessing.")

                print(f"  {'─'*60}")

            # Save best model by profit factor
            if eval_pf > self.best_profit_factor and update_step > 10:
                self.best_profit_factor = eval_pf
                self.agent.save(os.path.join(save_dir, "best_rl_agent.pt"))
                print(f"  → New best Eval PF: {eval_pf:.3f}")

            # Periodic checkpoint
            if (update_step + 1) % 50 == 0:
                self.agent.save(os.path.join(save_dir, f"rl_agent_step_{update_step}.pt"))

        # Final save
        self.agent.save(os.path.join(save_dir, "final_rl_agent.pt"))

        # Save training history + eval history
        combined_history = {**self.history, "eval": eval_history}
        with open(os.path.join(save_dir, "rl_training_history.json"), "w") as f:
            json.dump(combined_history, f, indent=2)

        total_time = (time.time() - train_start) / 60
        print(f"\n{'=' * 70}")
        print("TRAINING COMPLETE")
        print(f"  Best Profit Factor: {self.best_profit_factor:.3f}")
        print(f"  Total time:         {total_time:.1f} min")
        print(f"  Models saved to:    {save_dir}")
        if eval_history["eval_pf"]:
            print(f"  Last Eval PF:       {eval_history['eval_pf'][-1]:.3f}")
            print(f"  Last Train PF:      {eval_history['train_pf'][-1]:.3f}")
        print("=" * 70)

        return self.history


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

class ChunkedOptionsCache:
    """
    Lazy-loading cache that reads per-day .pkl shards on demand.
    
    Avoids loading the entire options cache into RAM at once,
    preventing MemoryError when dealing with hundreds of dates.
    Uses LRU eviction to keep at most `max_days_in_ram` days loaded.
    """
    def __init__(self, cache_dir, max_days_in_ram=30):
        self.cache_dir = Path(cache_dir)
        self.max_days = max_days_in_ram
        self.loaded_days = {}
        self.access_order = []

    def _load_day(self, date_str):
        """Load a single day's shard from disk."""
        file_path = self.cache_dir / f"{date_str}.pkl"
        if not file_path.exists():
            return False
        
        with open(file_path, "rb") as f:
            self.loaded_days[date_str] = pickle.load(f)
        
        self.access_order.append(date_str)
        # Evict oldest day if we exceed RAM budget
        if len(self.access_order) > self.max_days:
            oldest = self.access_order.pop(0)
            del self.loaded_days[oldest]
        
        return True

    def _touch(self, date_str):
        """Move a day to the end of the access order (most recently used)."""
        if date_str in self.access_order:
            self.access_order.remove(date_str)
            self.access_order.append(date_str)

    def get(self, key, default=None):
        """
        Get a cache entry by key (format: 'TICKER_DATE_HH:MM').
        
        If the loaded shard is in the new 'Global Minute' format, it
        dynamically reconstructs the 180-minute forward window for the episode.
        """
        parts = key.split('_')
        if len(parts) >= 3:
            ticker = parts[0]
            date_str = parts[1]
            time_str = parts[2]
        else:
            date_str = parts[0]
            ticker = "SPX"
            time_str = ""

        if date_str not in self.loaded_days:
            if not self._load_day(date_str):
                return default
        else:
            self._touch(date_str)
        
        shard = self.loaded_days[date_str]
        
        # 1. New Format: Shared Minute Data
        if "minute_data" in shard and "episodes" in shard:
            ep_info = shard["episodes"].get(key)
            if not ep_info:
                return default
            
            # Reconstruct the 'minutes' dictionary (offset 0 to 180)
            # using the sorted timestamps available in the shard
            timestamps = shard.get("timestamps", [])
            if not timestamps:
                # Fallback: just return the ep_info if no minutes needed
                return ep_info
            
            try:
                start_idx = timestamps.index(time_str)
            except ValueError:
                return ep_info # Should not happen with well-formed cache
            
            reconstructed_minutes = {}
            # Build forward window (matches max_forward_minutes from preprocess)
            # Default is 180 minutes
            max_forward = 180 
            for offset in range(max_forward + 1):
                idx = start_idx + offset
                if idx >= len(timestamps):
                    break
                ts = timestamps[idx]
                
                # Check for ticker-specific minute data
                ticker_data = shard["minute_data"].get(ticker, {})
                if ts in ticker_data:
                    reconstructed_minutes[offset] = ticker_data[ts]
            
            # Return a complete object that matches the Environment's expectations
            return {
                "spot": ep_info.get("spot", 0),
                "day_atr": ep_info.get("day_atr", 5.0),
                "calls": ep_info.get("calls", {}),
                "puts": ep_info.get("puts", {}),
                "minutes": reconstructed_minutes
            }

        # 2. Old Format: Redundant Per-Episode Data
        return shard.get(key, default)
    
    def __contains__(self, key):
        return self.get(key) is not None

    def __getitem__(self, key):
        result = self.get(key)
        if result is None:
            raise KeyError(key)
        return result


# ═══════════════════════════════════════════════════════════════════════════
# MULTIPROCESSING WORKERS
# ═══════════════════════════════════════════════════════════════════════════

g_worker_env = None
g_worker_agent = None


def init_worker(episode_index_path, options_cache_dir, max_days, feature_columns, state_dim, hidden_dims):
    """Initialize global environment and agent per worker process."""
    global g_worker_env, g_worker_agent
    import pandas as pd
    from rl.environment import SPXOptionsEnv
    from rl.agent import PPOAgent
    
    # Reset seeds per worker to avoid identically sampled trajectories
    import numpy as np
    import random
    from datetime import datetime
    seed = int(datetime.now().timestamp() * 1000) % 1000000 + os.getpid()
    np.random.seed(seed)
    torch.manual_seed(seed)
    random.seed(seed)
    
    episode_index = pd.read_parquet(episode_index_path)
    options_cache = ChunkedOptionsCache(options_cache_dir, max_days_in_ram=max_days)
    
    g_worker_env = SPXOptionsEnv(
        episode_index=episode_index,
        options_cache=options_cache,
        feature_columns=feature_columns,
    )
    g_worker_agent = PPOAgent(state_dim=state_dim, hidden_dims=hidden_dims)
    g_worker_agent.eval()

def worker_collect(agent_state_dict, min_confidence, min_strike, max_strike, min_hold,
                   curriculum_phase, update_step, total_updates, logit_noise_level=0.0, 
                   episode_idx=None, obs_noise=True):
    """Worker function to collect a single episode."""
    global g_worker_env, g_worker_agent
    import torch
    import numpy as np
    from rl.config import RL_CONFIG
    from rl.utils import augment_state
    
    g_worker_agent.load_state_dict(agent_state_dict)
    g_worker_env._curriculum_phase = curriculum_phase
    g_worker_env._current_min_confidence = min_confidence
    g_worker_env._current_min_strike_bucket = min_strike
    g_worker_env._current_max_strike_bucket = max_strike
    g_worker_env._current_min_hold_minutes = min_hold
    
    # Use pre-sampled index if provided (Issue 6)
    if episode_idx is not None:
        idx = episode_idx
    else:
        # Fallback to internal sampling if not provided (should not happen with new logic)
        valid_mask = g_worker_env.episode_index["mlp_confidence"] >= min_confidence
        valid_indices = g_worker_env.episode_index[valid_mask].index.tolist()
        if not valid_indices:
            valid_indices = list(range(len(g_worker_env.episode_index)))
        idx = np.random.choice(valid_indices)

    for _ in range(1): # No longer need multiple attempts here as index is pre-verified
        state = g_worker_env.reset(episode_idx=idx)
        
        episode_states = []
        episode_actions = []
        episode_action_types = []
        episode_rewards = []
        episode_log_probs = []
        episode_values = []
        episode_dones = []
        
        done = False
        step_count = 0
        
        with torch.no_grad():
            while not done and step_count < RL_CONFIG["session_length_minutes"]:
                state_input = augment_state(state) if obs_noise else state
                # Ensure it runs on CPU inside the worker
                state_tensor = torch.FloatTensor(state_input).unsqueeze(0)
                
                if g_worker_env._position is None and g_worker_env._use_sniper:
                    action_type = "sniper_entry"
                elif g_worker_env._position is None:
                    action_type = "strike"
                else:
                    action_type = "exit"
                    
                # Fix: Apply logit noise to 'exit' if policy is collapsing (dynamic)
                # Also keep the early-phase strike noise for exploration
                l_noise = 0.0
                if action_type == "strike" and update_step < (total_updates * 0.1):
                    l_noise = 0.5
                elif action_type == "exit":
                    # Exit Head: HOLD(0) or EXIT(1)
                    override = RL_CONFIG.get("logit_noise_exit_override", 0.0)
                    l_noise = max(logit_noise_level, override)
                
                action, log_prob, value = g_worker_agent.get_action(
                    state_tensor, action_type, deterministic=False, logit_noise=l_noise)
                    
                action_val = action
                log_prob_float = log_prob.item() if isinstance(log_prob, torch.Tensor) else log_prob
                value_float = value.item() if isinstance(value, torch.Tensor) else value
                
                env_action = action_val["strike"] if isinstance(action_val, dict) else action_val
                next_state, reward, done, info = g_worker_env.step(env_action)
                
                episode_states.append(state)
                episode_actions.append(action_val)
                episode_action_types.append(action_type)
                episode_rewards.append(reward)
                episode_log_probs.append(log_prob_float)
                episode_values.append(value_float)
                episode_dones.append(done)
                
                state = next_state
                step_count += 1
                
        if step_count > 0:
            return (episode_states, episode_actions, episode_action_types, 
                    episode_rewards, episode_log_probs, episode_values, episode_dones, info)
            
    return None

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train RL agent")
    parser.add_argument("--episode-index", type=str, required=True,
                        help="Path to episode_index.parquet")
    parser.add_argument("--options-cache", type=str, required=True,
                        help="Directory of chunked per-day .pkl cache shards")
    parser.add_argument("--save-dir", type=str, default="../rl_models")
    parser.add_argument("--total-updates", type=int, default=None)
    parser.add_argument("--episodes-per-update", type=int, default=None)
    parser.add_argument("--max-days-in-ram", type=int, default=260,
                        help="Max number of day shards to keep in RAM (LRU)")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of background CPU workers for data collection")
    args = parser.parse_args()

    from hybrid_model import FEATURE_COLUMNS

    episode_index = pd.read_parquet(args.episode_index)
    print(f"Loaded episode index: {len(episode_index)} episodes")

    # Use lazy chunked cache instead of loading monolithic pickle
    options_cache = ChunkedOptionsCache(args.options_cache, max_days_in_ram=args.max_days_in_ram)
    print(f"Using Lazy Chunked Cache targeting directory: {args.options_cache}")

    if args.total_updates:
        RL_CONFIG["total_updates"] = args.total_updates
    if args.episodes_per_update:
        RL_CONFIG["n_episodes_per_update"] = args.episodes_per_update

    env = SPXOptionsEnv(
        episode_index=episode_index,
        options_cache=options_cache,
        feature_columns=FEATURE_COLUMNS,
    )

    agent = PPOAgent()
    trainer = PPOTrainer(
        agent=agent, 
        env=env,
        num_workers=args.workers,
        episode_index_path=args.episode_index,
        options_cache_dir=args.options_cache
    )
    trainer.train(save_dir=args.save_dir)