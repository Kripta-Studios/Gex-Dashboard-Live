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

        self.optimizer = optim.Adam(
            self.agent.parameters(),
            lr=RL_CONFIG["learning_rate"],
        )
        self.reward_normalizer = RunningMeanStd()
        self.curriculum = CurriculumScheduler()
        self.best_profit_factor = 0.0

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

    def collect_episodes(self, n_episodes: int, min_confidence: float = 0.60,
                         training: bool = True) -> tuple:
        """
        Collect n_episodes by running the current policy in the environment.
        Uses multiprocessing pool if self.num_workers > 1 and training is True.
        """
        buffer = RolloutBuffer()
        episode_infos = []
        
        curriculum_phase = getattr(self.env, "_curriculum_phase", 3)
        
        if self.pool is not None and training:
            # Move agent weights to CPU to be safely serialized
            self.agent.cpu()
            state_dict = {k: v.cpu() for k, v in self.agent.state_dict().items()}
            self.agent.to(self.device)
            
            futures = []
            for _ in range(n_episodes):
                futures.append(self.pool.submit(worker_collect, state_dict, min_confidence, curriculum_phase))
                
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

        # Filter environment episodes by curriculum confidence
        valid_mask = self.env.episode_index["mlp_confidence"] >= min_confidence
        valid_indices = self.env.episode_index[valid_mask].index.tolist()

        if not valid_indices:
            print(f"[RL] Warning: no episodes with confidence >= {min_confidence}")
            valid_indices = list(range(len(self.env.episode_index)))

        collected = 0
        max_attempts = n_episodes * 3

        for attempt in range(max_attempts):
            if collected >= n_episodes:
                break

            idx = np.random.choice(valid_indices)
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
                # Augment state during training
                if training:
                    state_input = augment_state(state)
                else:
                    state_input = state

                state_tensor = torch.FloatTensor(state_input).unsqueeze(0).to(self.device)

                with torch.no_grad():
                    if self.env._position is None and self.env._sniper_mode:
                        action_type = "sniper_entry"
                    elif self.env._position is None:
                        action_type = "strike"
                    else:
                        action_type = "exit"

                    action, log_prob, value = self.agent.get_action(
                        state_tensor, action_type, deterministic=not training)

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

    def ppo_update(self, buffer: RolloutBuffer) -> dict:
        """
        Run PPO clipped objective update on collected rollout data.

        Returns: dict with loss components.
        """
        self.agent.train()
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy_loss = 0.0
        n_batches = 0

        for epoch in range(RL_CONFIG["ppo_epochs"]):
            for batch in buffer.get_batches(RL_CONFIG["batch_size"]):
                states = batch["states"].to(self.device)
                actions = batch["actions"] # list of dict/int
                old_log_probs = batch["old_log_probs"].to(self.device)
                returns = batch["returns"].to(self.device)
                advantages = batch["advantages"].to(self.device)
                action_types = batch["action_types"]

                # Evaluate current policy
                log_probs, entropy, values = self.agent.evaluate_actions(
                    states, actions, action_types)

                # PPO clipped objective
                ratio = torch.exp(log_probs - old_log_probs)
                clip_eps = RL_CONFIG["clip_epsilon"]
                surr1 = ratio * advantages
                surr2 = torch.clamp(ratio, 1.0 - clip_eps, 1.0 + clip_eps) * advantages
                policy_loss = -torch.min(surr1, surr2).mean()

                # Value loss
                value_loss = nn.MSELoss()(values, returns)

                # Entropy bonus — per-action-type coefficient
                # Sniper steps get higher entropy to force exploration of WAIT vs ENTER
                sniper_entropy_coeff = RL_CONFIG.get("sniper_entropy_coeff", 0.10)
                base_entropy_coeff = RL_CONFIG["entropy_coeff"]
                is_sniper = torch.tensor(
                    [at == "sniper_entry" for at in action_types],
                    dtype=torch.float32, device=self.device
                )
                per_sample_coeff = is_sniper * sniper_entropy_coeff + (1 - is_sniper) * base_entropy_coeff
                entropy_loss = -(entropy * per_sample_coeff).mean()

                # Total loss
                loss = (policy_loss
                        + RL_CONFIG["value_loss_coeff"] * value_loss
                        + entropy_loss)

                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.agent.parameters(),
                                         RL_CONFIG["max_grad_norm"])
                self.optimizer.step()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy_loss += entropy_loss.item()
                n_batches += 1

        n_batches = max(n_batches, 1)
        return {
            "policy_loss": total_policy_loss / n_batches,
            "value_loss": total_value_loss / n_batches,
            "entropy_loss": total_entropy_loss / n_batches,
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
        step_times = []

        # Eval history for overfitting comparison
        eval_history = {
            "step": [], "eval_pf": [], "eval_wr": [], "eval_pnl": [],
            "train_pf": [], "train_wr": [], "train_pnl": [],
        }

        train_start = time.time()

        for update_step in range(total_updates):
            t_start = time.time()

            # Get curriculum phase
            phase_info = self.curriculum.get_phase_info(update_step)
            min_conf = phase_info["min_confidence"]

            # Propagate curriculum phase to environment for min-wait enforcement
            self.env._curriculum_phase = phase_info["phase"]

            # Collect episodes
            buffer, episode_infos = self.collect_episodes(
                n_episodes=n_episodes,
                min_confidence=min_conf,
                training=True,
            )

            if len(buffer) == 0:
                print(f"[{update_step}] No data collected, skipping...")
                continue

            # PPO update
            losses = self.ppo_update(buffer)

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
            rolling_policy_loss.append(losses["policy_loss"])
            rolling_value_loss.append(losses["value_loss"])
            rolling_entropy.append(losses["entropy_loss"])

            # Keep only last ROLLING_WINDOW
            if len(rolling_pf) > ROLLING_WINDOW:
                rolling_pf.pop(0)
                rolling_wr.pop(0)
                rolling_pnl.pop(0)
                rolling_policy_loss.pop(0)
                rolling_value_loss.pop(0)
                rolling_entropy.pop(0)

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
                bar_len = 20
                filled = int(bar_len * (update_step + 1) / total_updates)
                bar = "█" * filled + "░" * (bar_len - filled)

                # Rolling averages
                r_pf = np.mean(rolling_pf)
                r_wr = np.mean(rolling_wr)
                r_pnl = np.mean(rolling_pnl)
                r_pi = np.mean(rolling_policy_loss)
                r_v = np.mean(rolling_value_loss)
                r_h = np.mean(rolling_entropy)

                print(f"\n  [{bar}] {pct_done:5.1f}% | Step {update_step}/{total_updates} | "
                      f"ETA: {eta_min:.1f}min | Phase {phase_info['phase']}")
                print(f"  ├─ This step:  PF={profit_factor:.2f} WR={win_rate:.1%} "
                      f"PnL={mean_pnl:+.4f} Hold={mean_hold:.0f}m "
                      f"L/S={n_long}/{n_short} Stop={hard_stop_rate:.0%}")
                if RL_CONFIG.get("use_sniper_mode"):
                    print(f"  ├─ Sniper:     AvgWait={mean_sniper_wait:.1f}m "
                          f"Timeouts={sniper_timeouts}/{len(episode_infos)}")
                print(f"  ├─ Rolling{ROLLING_WINDOW:2d}: PF={r_pf:.2f} WR={r_wr:.1%} "
                      f"PnL={r_pnl:+.4f}")
                print(f"  ├─ Losses:     π={losses['policy_loss']:.4f} "
                      f"V={losses['value_loss']:.4f} "
                      f"H={losses['entropy_loss']:.4f} "
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
                    training=False,  # No augmentation, deterministic
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
        """Get a cache entry by key (format: 'TICKER_YYYYMMDD_HH:MM')."""
        parts = key.split('_')
        if len(parts) >= 3:
            date_str = parts[1]
        else:
            date_str = parts[0]
        
        if date_str not in self.loaded_days:
            if not self._load_day(date_str):
                return default
        else:
            self._touch(date_str)
        
        return self.loaded_days[date_str].get(key, default)
    
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

def worker_collect(agent_state_dict, min_confidence, curriculum_phase):
    """Worker function to collect a single episode."""
    global g_worker_env, g_worker_agent
    import torch
    import numpy as np
    from rl.config import RL_CONFIG
    from rl.utils import augment_state
    
    g_worker_agent.load_state_dict(agent_state_dict)
    g_worker_env._curriculum_phase = curriculum_phase
    
    valid_mask = g_worker_env.episode_index["mlp_confidence"] >= min_confidence
    valid_indices = g_worker_env.episode_index[valid_mask].index.tolist()
    if not valid_indices:
        valid_indices = list(range(len(g_worker_env.episode_index)))
        
    for _ in range(10):
        idx = np.random.choice(valid_indices)
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
                state_input = augment_state(state)
                # Ensure it runs on CPU inside the worker
                state_tensor = torch.FloatTensor(state_input).unsqueeze(0)
                
                if g_worker_env._position is None and g_worker_env._use_sniper:
                    action_type = "sniper_entry"
                elif g_worker_env._position is None:
                    action_type = "strike"
                else:
                    action_type = "exit"
                    
                action, log_prob, value = g_worker_agent.get_action(
                    state_tensor, action_type, deterministic=False)
                    
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
