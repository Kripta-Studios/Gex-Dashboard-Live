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

from .config import RL_CONFIG, STRIKE_BUCKETS, NUM_STRIKE_ACTIONS
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
            {"params": policy_params, "lr": RL_CONFIG["learning_rate"], "weight_decay": 0.0},
            {"params": value_params,  "lr": RL_CONFIG["learning_rate"] * 2.5, "weight_decay": 1e-4}, # Reduced from 5x to 2.5x
        ], weight_decay=0.0)


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
            worker_max_days = max(2, int(12 / self.num_workers))
            self.pool = ProcessPoolExecutor(
                max_workers=self.num_workers,
                initializer=init_worker,
                initargs=(
                    episode_index_path, 
                    options_cache_dir, 
                    worker_max_days, 
                    env.feature_columns,
                    RL_CONFIG["state_dim"],
                    RL_CONFIG["hidden_dims"],
                    RL_CONFIG.get("use_entry_skip_action", False),
                    RL_CONFIG.get("force_hold_exit_training", False),
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

        conf_series = self.env.episode_index["mlp_confidence"]

        def _apply_confidence_filter(long_pool, short_pool):
            long_filtered = list(long_pool or [])
            short_filtered = list(short_pool or [])

            if min_confidence > 0:
                long_filtered = [
                    idx for idx in long_filtered
                    if float(conf_series.loc[idx]) >= min_confidence
                ]
                short_filtered = [
                    idx for idx in short_filtered
                    if float(conf_series.loc[idx]) >= min_confidence
                ]

            if long_filtered or short_filtered:
                return long_filtered, short_filtered

            print(
                f"[RL] Warning: no episodes with confidence >= {min_confidence} for "
                f"{'train' if training else 'eval'} split."
            )
            return list(long_pool or []), list(short_pool or [])

        if self.pool is not None and training:
            # Just copy state_dict to CPU without moving the GPU model
            state_dict = {k: v.detach().cpu() for k, v in self.agent.state_dict().items()}
            
            # --- Direction-balanced sampling from date-restricted pool ---
            long_pool = self._long_indices_train if training else self._long_indices_eval
            short_pool = self._short_indices_train if training else self._short_indices_eval
            long_pool, short_pool = _apply_confidence_filter(long_pool, short_pool)
            
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
                    (e_states, e_actions, e_action_types, e_action_masks,
                     e_policy_active, e_rewards, e_log_probs, e_values,
                     e_dones, info) = res
                     
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
                            action_mask=e_action_masks[i],
                            policy_active=e_policy_active[i],
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
        long_pool, short_pool = _apply_confidence_filter(long_pool, short_pool)

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
            self.env._current_min_hold_minutes = min_hold
            self.env._curriculum_phase = curriculum_phase
            state = self.env.reset(episode_idx=idx)

            episode_states = []
            episode_actions = []
            episode_action_types = []
            episode_action_masks = []
            episode_policy_active = []
            episode_rewards = []
            episode_log_probs = []
            episode_values = []
            episode_dones = []

            done = False
            step_count = 0

            # ── Strike action mask — alineada con currículo actual ──
            from .config import NUM_STRIKE_ACTIONS
            _st_mask = [(min_strike <= i <= max_strike) for i in range(NUM_STRIKE_ACTIONS)]
            if not any(_st_mask):
                _st_mask = [True] * NUM_STRIKE_ACTIONS
            _entry_mask = [True] + list(_st_mask)

            while not done and step_count < RL_CONFIG["session_length_minutes"]:
                state_input = augment_state(state) if obs_noise else state
                state_tensor = torch.FloatTensor(state_input).unsqueeze(0).to(self.device)

                with torch.no_grad():
                    if self.env._position is None and (
                        self.env._sniper_mode or RL_CONFIG.get("use_entry_skip_action", False)
                    ):
                        action_type = "sniper_entry"
                        current_mask = _entry_mask
                    elif self.env._position is None:
                        action_type = "strike"
                        current_mask = _st_mask
                    else:
                        action_type = "exit"
                        current_mask = None

                    force_hold_exit = (
                        action_type == "exit"
                        and RL_CONFIG.get("force_hold_exit_training", False)
                    )
                    if force_hold_exit:
                        _, value = self.agent.forward(state_tensor, action_type)
                        action = 0
                        log_prob = torch.zeros(1, device=self.device)
                    else:
                        # Apply logit noise for strike exploration in early Phase 1
                        l_noise = (
                            0.5
                            if training
                            and update_step < (total_updates * 0.1)
                            and action_type in ("strike", "sniper_entry")
                            else 0.0
                        )

                        action, log_prob, value = self.agent.get_action(
                            state_tensor, action_type, deterministic=not training,
                            logit_noise=l_noise, action_mask=current_mask)

                # action is now an int (strike bucket, sniper choice, or exit choice)
                env_action = action
                value_float = value.item() if isinstance(value, torch.Tensor) else value

                next_state, reward, done, info = self.env.step(env_action)
                
                # [FIX] Mismatch detection: recalcula log_prob con la máscara correcta
                effective_action = info.get("effective_action", env_action)
                policy_active = (effective_action == env_action) and not force_hold_exit
                
                if effective_action != env_action:
                    with torch.no_grad():
                        new_log_probs, _, _, _ = self.agent.evaluate_actions(
                            state_tensor, [effective_action], [action_type],
                            action_masks=[current_mask])
                        log_prob_float = new_log_probs.item()
                else:
                    log_prob_float = log_prob.item() if isinstance(log_prob, torch.Tensor) else log_prob

                episode_states.append(state)
                episode_actions.append(effective_action)
                episode_action_types.append(action_type)
                episode_action_masks.append(current_mask)
                episode_policy_active.append(policy_active)
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
                    action_mask=episode_action_masks[i],
                    policy_active=episode_policy_active[i],
                )

            if info.get("final_pnl_pct") is not None:
                episode_infos.append(info)

            collected += 1

        return buffer, episode_infos

    def _simulate_hold_episode(self, episode_idx: int, strike_action: int) -> tuple[float, str]:
        """
        Run one cached episode with a forced strike and HOLD-only exits.

        This is used only for train-period oracle labelling. It mirrors the
        force-hold RL setup, so labels are generated from the same environment
        reward surface PPO later optimizes.
        """
        self.env.reset(episode_idx=episode_idx)
        _, _, done, info = self.env.step(int(strike_action))

        steps = 0
        while not done and steps < RL_CONFIG["session_length_minutes"]:
            _, _, done, info = self.env.step(0)
            steps += 1

        return float(info.get("final_pnl_pct", 0.0)), str(info.get("exit_type", ""))

    def _sample_oracle_indices(self, samples: int, min_confidence: float) -> list[int]:
        """Balanced ticker/direction sampling from the chronological train split."""
        train_mask = self.env.episode_index["date"].isin(self.train_dates)
        conf_mask = self.env.episode_index["mlp_confidence"].astype(float) >= float(min_confidence)
        pool_df = self.env.episode_index[train_mask & conf_mask]

        grouped: list[list[int]] = []
        if "ticker" in pool_df.columns and "mlp_direction" in pool_df.columns:
            for _, group in pool_df.groupby(["ticker", "mlp_direction"], sort=True):
                indices = group.index.tolist()
                if indices:
                    grouped.append(indices)

        if not grouped:
            indices = pool_df.index.tolist()
            if not indices:
                raise RuntimeError("No train episodes available for strike oracle pretraining.")
            grouped = [indices]

        sampled: list[int] = []
        rng = np.random.default_rng(20260531)
        for i in range(int(samples)):
            bucket = grouped[i % len(grouped)]
            sampled.append(int(rng.choice(bucket)))
        rng.shuffle(sampled)
        return sampled

    def pretrain_strike_oracle(
        self,
        samples: int = 0,
        epochs: int = 3,
        lr: float = 1e-4,
        min_confidence: float = None,
        save_dir: str = None,
    ) -> dict:
        """
        Supervised warm-start for the strike head using train-period oracle labels.

        The oracle never reads Apr/May 2026 or the eval split. It simulates all
        strike buckets for sampled train episodes and labels the bucket with the
        highest final option PnL under HOLD-only exit rules.
        """
        if samples <= 0:
            return {}

        min_conf = float(min_confidence if min_confidence is not None else RL_CONFIG.get("min_confidence", 0.0))
        indices = self._sample_oracle_indices(samples=samples, min_confidence=min_conf)
        print("\n" + "=" * 70)
        print("STRIKE ORACLE PRETRAIN")
        print(f"  Samples:        {len(indices)}")
        print(f"  Epochs:         {epochs}")
        print(f"  LR:             {lr:.2e}")
        print(f"  Min confidence: {min_conf:.3f}")
        print("  Label split:    chronological train dates only")
        print("=" * 70)

        states = []
        labels = []
        weights = []
        label_rows = []
        skipped = 0

        label_start = time.time()
        for n, ep_idx in enumerate(indices, start=1):
            state = self.env.reset(episode_idx=ep_idx).astype(np.float32)
            pnls = []
            exits = []
            for action in range(NUM_STRIKE_ACTIONS):
                pnl, exit_type = self._simulate_hold_episode(ep_idx, action)
                pnls.append(pnl)
                exits.append(exit_type)

            if all(exit_type == "no_strike_available" for exit_type in exits):
                skipped += 1
                continue

            best_action = int(np.argmax(pnls))
            sorted_pnls = sorted(pnls, reverse=True)
            best_pnl = float(sorted_pnls[0])
            margin = float(sorted_pnls[0] - sorted_pnls[1]) if len(sorted_pnls) > 1 else 0.0
            # Weight high-opportunity and clear-margin labels without letting
            # a few huge option winners dominate the classifier.
            sample_weight = float(np.clip(0.25 + abs(best_pnl) + max(margin, 0.0), 0.25, 4.0))

            ep = self.env.episode_index.loc[ep_idx]
            states.append(state)
            labels.append(best_action)
            weights.append(sample_weight)
            label_rows.append({
                "episode_index": int(ep_idx),
                "ticker": ep.get("ticker", ""),
                "date": ep.get("date", ""),
                "time": ep.get("time", ""),
                "direction": ep.get("mlp_direction", ""),
                "confidence": float(ep.get("mlp_confidence", 0.0)),
                "best_bucket": best_action,
                "best_label": STRIKE_BUCKETS.get(best_action, {}).get("label", str(best_action)),
                "best_pnl_pct": best_pnl,
                "second_best_margin": margin,
                **{f"bucket_{i}_pnl_pct": float(v) for i, v in enumerate(pnls)},
            })

            if n % 500 == 0:
                elapsed = (time.time() - label_start) / 60.0
                print(f"  labelled {n}/{len(indices)} episodes ({elapsed:.1f} min)")

        if not states:
            raise RuntimeError("Strike oracle pretraining could not build any labels.")

        states_t = torch.tensor(np.asarray(states, dtype=np.float32), dtype=torch.float32, device=self.device)
        labels_t = torch.tensor(labels, dtype=torch.long, device=self.device)
        weights_t = torch.tensor(weights, dtype=torch.float32, device=self.device)
        weights_t = weights_t / (weights_t.mean() + 1e-8)

        params = list(self.agent.backbone.parameters()) + list(self.agent.strike_head.parameters())
        optimizer = optim.Adam(params, lr=float(lr), weight_decay=1e-4)
        batch_size = min(1024, max(64, len(labels) // 4))
        criterion = nn.CrossEntropyLoss(reduction="none", label_smoothing=0.05)

        self.agent.train()
        metrics = {}
        for epoch in range(1, int(epochs) + 1):
            perm = torch.randperm(states_t.size(0), device=self.device)
            epoch_loss = 0.0
            correct = 0
            seen = 0

            for start in range(0, states_t.size(0), batch_size):
                batch_idx = perm[start:start + batch_size]
                logits, _ = self.agent.forward(states_t[batch_idx], action_type="strike")
                per_sample_loss = criterion(logits, labels_t[batch_idx])
                loss = (per_sample_loss * weights_t[batch_idx]).mean()

                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(params, RL_CONFIG["max_grad_norm"])
                optimizer.step()

                with torch.no_grad():
                    pred = torch.argmax(logits, dim=-1)
                    correct += int((pred == labels_t[batch_idx]).sum().item())
                    seen += int(batch_idx.numel())
                    epoch_loss += float(loss.item()) * int(batch_idx.numel())

            metrics = {
                "samples": int(len(labels)),
                "skipped": int(skipped),
                "epoch": int(epoch),
                "loss": epoch_loss / max(seen, 1),
                "accuracy": correct / max(seen, 1),
            }
            print(
                f"  epoch {epoch}/{epochs}: "
                f"loss={metrics['loss']:.4f} acc={metrics['accuracy']:.1%}"
            )

        label_df = pd.DataFrame(label_rows)
        print("  Label distribution:")
        label_counts = label_df["best_bucket"].value_counts().sort_index()
        for bucket, count in label_counts.items():
            label = STRIKE_BUCKETS.get(int(bucket), {}).get("label", str(bucket))
            print(f"    {int(bucket)} {label:<10}: {int(count)}")

        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            labels_path = os.path.join(save_dir, "strike_oracle_pretrain_labels.csv")
            label_df.to_csv(labels_path, index=False)
            print(f"  Labels saved to: {labels_path}")

        print("=" * 70 + "\n")
        return metrics

    def pretrain_entry_oracle_from_labels(
        self,
        labels_path: str,
        epochs: int = 8,
        lr: float = 1e-4,
        target_entry_rate: float = 0.75,
        min_enter_pnl: float | None = None,
        fixed_enter_bucket: int | None = None,
        save_dir: str = None,
    ) -> dict:
        """
        Supervised warm-start for direct SKIP/ENTER+bucket decisions.

        The labels file must come from pretrain_strike_oracle(), which only
        simulates train-period episodes. Action 0 skips; actions 1..7 enter
        with bucket 0..6. A target entry rate is selected on train labels only
        to preserve trade volume without looking at Apr/May outcomes.
        """
        if not labels_path:
            return {}

        label_df = pd.read_csv(labels_path)
        required = {"episode_index", "ticker", "best_bucket", "best_pnl_pct"}
        missing = required - set(label_df.columns)
        if missing:
            raise ValueError(f"Entry oracle labels missing columns: {sorted(missing)}")

        label_df = label_df.copy()
        target_entry_rate = float(target_entry_rate)
        if not (0.0 < target_entry_rate <= 1.0):
            raise ValueError("--entry-oracle-target-entry-rate must be in (0, 1].")

        thresholds = {}
        if min_enter_pnl is None:
            q = max(0.0, min(1.0, 1.0 - target_entry_rate))
            for ticker, group in label_df.groupby("ticker", sort=True):
                thresholds[str(ticker)] = float(group["best_pnl_pct"].quantile(q))
        else:
            for ticker in label_df["ticker"].dropna().unique():
                thresholds[str(ticker)] = float(min_enter_pnl)

        def _action(row):
            ticker = str(row["ticker"])
            threshold = thresholds.get(ticker, float(min_enter_pnl or 0.0))
            if float(row["best_pnl_pct"]) < threshold:
                return 0
            if fixed_enter_bucket is not None:
                return int(fixed_enter_bucket) + 1
            return int(row["best_bucket"]) + 1

        label_df["entry_action"] = label_df.apply(_action, axis=1).astype(int)

        states = []
        labels = []
        tickers = []
        skipped_missing = 0
        for _, row in label_df.iterrows():
            ep_idx = int(row["episode_index"])
            if ep_idx < 0 or ep_idx >= len(self.env.episode_index):
                skipped_missing += 1
                continue
            state = self.env.reset(episode_idx=ep_idx).astype(np.float32)
            states.append(state)
            labels.append(int(row["entry_action"]))
            tickers.append(str(row["ticker"]))

        if not states:
            raise RuntimeError("Entry oracle pretraining could not build any states.")

        states_t = torch.tensor(np.asarray(states, dtype=np.float32), dtype=torch.float32, device=self.device)
        labels_t = torch.tensor(labels, dtype=torch.long, device=self.device)

        class_counts = torch.bincount(labels_t, minlength=8).float()
        class_weights = class_counts.sum() / torch.clamp(class_counts, min=1.0)
        class_weights = class_weights / class_weights.mean()
        class_weights = torch.clamp(class_weights, 0.25, 4.0)

        params = list(self.agent.backbone.parameters()) + list(self.agent.sniper_head.parameters())
        optimizer = optim.Adam(params, lr=float(lr), weight_decay=1e-4)
        criterion = nn.CrossEntropyLoss(weight=class_weights, label_smoothing=0.03)
        batch_size = min(2048, max(128, states_t.size(0) // 4))

        print("\n" + "=" * 70)
        print("ENTRY ORACLE PRETRAIN")
        print(f"  Labels:             {labels_path}")
        print(f"  Samples:            {states_t.size(0)} (skipped missing: {skipped_missing})")
        print(f"  Epochs:             {epochs}")
        print(f"  LR:                 {lr:.2e}")
        print(f"  Target entry rate:  {target_entry_rate:.1%}")
        if fixed_enter_bucket is not None:
            fixed_label = STRIKE_BUCKETS.get(int(fixed_enter_bucket), {}).get("label", str(fixed_enter_bucket))
            print(f"  Fixed enter bucket: {int(fixed_enter_bucket)} {fixed_label}")
        print("  Thresholds by ticker:")
        for ticker, threshold in sorted(thresholds.items()):
            sub = label_df[label_df["ticker"].astype(str) == ticker]
            entry_rate = float((sub["entry_action"] > 0).mean()) if len(sub) else 0.0
            print(f"    {ticker}: threshold={threshold:+.4f}, labelled_entry={entry_rate:.1%}, n={len(sub)}")
        print("  Action distribution:")
        for action, count in label_df["entry_action"].value_counts().sort_index().items():
            name = "SKIP" if int(action) == 0 else STRIKE_BUCKETS.get(int(action) - 1, {}).get("label", str(action))
            print(f"    {int(action)} {name:<10}: {int(count)}")
        print("=" * 70)

        self.agent.train()
        metrics = {}
        for epoch in range(1, int(epochs) + 1):
            perm = torch.randperm(states_t.size(0), device=self.device)
            epoch_loss = 0.0
            correct = 0
            seen = 0

            for start in range(0, states_t.size(0), batch_size):
                idx = perm[start:start + batch_size]
                logits, _ = self.agent.forward(states_t[idx], action_type="sniper_entry")
                loss = criterion(logits, labels_t[idx])

                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(params, RL_CONFIG["max_grad_norm"])
                optimizer.step()

                with torch.no_grad():
                    pred = torch.argmax(logits, dim=-1)
                    correct += int((pred == labels_t[idx]).sum().item())
                    seen += int(idx.numel())
                    epoch_loss += float(loss.item()) * int(idx.numel())

            metrics = {
                "samples": int(states_t.size(0)),
                "epoch": int(epoch),
                "loss": epoch_loss / max(seen, 1),
                "accuracy": correct / max(seen, 1),
            }
            print(
                f"  epoch {epoch}/{epochs}: "
                f"loss={metrics['loss']:.4f} acc={metrics['accuracy']:.1%}"
            )

        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            out_labels = os.path.join(save_dir, "entry_oracle_pretrain_labels.csv")
            label_df.to_csv(out_labels, index=False)
            self.agent.save(os.path.join(save_dir, "entry_oracle_agent.pt"), update_step=0)
            print(f"  Labels saved to: {out_labels}")
            print(f"  Agent saved to:  {os.path.join(save_dir, 'entry_oracle_agent.pt')}")

        print("=" * 70 + "\n")
        return metrics

    def ppo_update(self, buffer: RolloutBuffer, update_step: int = 0) -> dict:
        """Run PPO clipped objective update with per-head entropy and KL stopping."""
        
        # Annealing progress
        progress = min(update_step / RL_CONFIG.get("entropy_anneal_end", 300), 1.0)
        
        # Per-head entropy coefficients (Fix: strike head collapse)
        # Strike head: high initial coeff with a floor that never reaches zero
        strike_coeff_base = RL_CONFIG.get("strike_entropy_coeff", 0.08)
        strike_coeff_floor = RL_CONFIG.get("strike_entropy_floor", 0.03)
        self._current_strike_coeff = max(
            strike_coeff_base - (strike_coeff_base - strike_coeff_floor) * progress,
            strike_coeff_floor
        )
        # Exit head: lower coefficient (binary choice needs less exploration)
        exit_coeff_base = RL_CONFIG.get("exit_entropy_coeff", 0.02)
        exit_coeff_floor = RL_CONFIG.get("entropy_coeff_min", 0.01)
        self._current_exit_coeff = max(
            exit_coeff_base - (exit_coeff_base - exit_coeff_floor) * progress,
            exit_coeff_floor
        )
        
        kl_target = RL_CONFIG.get("kl_target", 0.015)
        entropy_target = RL_CONFIG.get("entropy_target", 0.05)
        
        self.agent.train()
        total_policy_loss = total_value_loss = total_entropy_loss = 0.0
        total_mean_entropy = 0.0
        total_approx_kl = 0.0
        total_h_strike = 0.0
        total_h_exit = 0.0
        total_gating_probs = None
        
        n_batches = 0

        if len(buffer) < RL_CONFIG["batch_size"]:
            return {
                "policy_loss": 0, "value_loss": 0, "entropy_loss": 0, 
                "mean_entropy": 0, "h_strike": 0, "h_exit": 0, "approx_kl": 0, "moe_gating": np.ones(1)
            }

        for epoch in range(RL_CONFIG["ppo_epochs"]):
            epoch_kls = []
            stop_update = False
            for batch in buffer.get_batches(RL_CONFIG["batch_size"]):
                states = batch["states"].to(self.device)
                actions = batch["actions"]
                action_types = batch["action_types"]
                action_masks = batch["action_masks"]
                policy_active = batch["policy_active"].to(self.device)
                old_log_probs = batch["old_log_probs"].to(self.device)
                returns = batch["returns"].to(self.device)

                if states.shape[0] < 2:
                    continue

                # ── Recompute log_probs, entropy, and values with CURRENT weights (Fix 4) ──
                log_probs, entropy, values, gating_probs = self.agent.evaluate_actions(
                    states, actions, action_types,
                    action_masks=action_masks,
                    detach_value=True)

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
                active_mask = policy_active.bool()
                active_count = int(active_mask.sum().item())
                if active_count > 0:
                    ratio = torch.exp(log_probs[active_mask] - old_log_probs[active_mask])
                    active_advantages = advantages[active_mask]
                else:
                    ratio = torch.ones(1, dtype=log_probs.dtype, device=self.device)
                    active_advantages = torch.zeros(1, dtype=advantages.dtype, device=self.device)
                
                # Track approximate KL for early stopping
                with torch.no_grad():
                    approx_kl = ((ratio - 1) - torch.log(ratio)).mean().item()
                    epoch_kls.append(approx_kl)
                    
                    # [STABILITY FIX] Intra-batch KL early stop
                    # CRITICAL: Skip on the first batch of each epoch so entropy gradients always flow.
                    if n_batches > 0 and approx_kl > (kl_target * 1.5):
                        stop_update = True
                        break
                
                clip_eps = RL_CONFIG["clip_epsilon"]
                if active_count > 0:
                    surr1 = ratio * active_advantages
                    surr2 = torch.clamp(ratio, 1.0 - clip_eps, 1.0 + clip_eps) * active_advantages
                    policy_loss = -torch.min(surr1, surr2).mean()
                else:
                    policy_loss = values.sum() * 0.0

                # ── Per-head entropy for diagnostics (Issue 1) ──
                with torch.no_grad():
                    # Map action types to indices for boolean masking
                    is_strike_batch = torch.tensor([at != "exit" for at in action_types], device=self.device) & active_mask
                    is_exit_batch = ~is_strike_batch
                    is_exit_batch = is_exit_batch & active_mask
                    
                    h_strike = entropy[is_strike_batch].mean().item() if is_strike_batch.any() else 0.0
                    h_exit = entropy[is_exit_batch].mean().item() if is_exit_batch.any() else 0.0

                # ── Raw Value Loss (Bug #4 Fix) ──
                # Use returns as-is to keep the critic on the reward scale.
                value_loss = nn.MSELoss()(values, returns)

                # ── Per-Head Entropy Bonus (Fix: strike head collapse) ──
                # Strike head gets its own coefficient with a floor that never
                # reaches zero. Exit head gets a separate, lower coefficient.
                # The old system set coeff=0.0 when entropy exceeded target,
                # which killed the exploration gradient and caused irreversible
                # collapse to otm_light (99.2% of trades).
                exit_tgt = RL_CONFIG.get("exit_entropy_target", 0.40)
                strike_tgt = RL_CONFIG.get("entropy_target", 0.25)
                
                active_entropy = entropy[active_mask] if active_count > 0 else entropy
                mean_ent_val = active_entropy.mean().item() # for logging

                coeffs = []
                for i, at in enumerate(action_types):
                    if not bool(active_mask[i].item()):
                        coeffs.append(0.0)
                        continue
                    e_val = entropy[i].item()
                    
                    if at == "sniper_entry":
                        coeffs.append(RL_CONFIG.get("sniper_entropy_coeff", 0.10))
                        continue
                    
                    if at == "strike":
                        # Strike head: ALWAYS maintain minimum exploration
                        # Never set to 0 — that caused irreversible collapse
                        deficit = max(0, strike_tgt - e_val) / (strike_tgt + 1e-8)
                        boost = 1.0 + deficit * 3.0  # Stronger boost when collapsed
                        coeffs.append(self._current_strike_coeff * boost)
                    else:
                        # Exit head: reduced but never zero
                        deficit = max(0, exit_tgt - e_val) / (exit_tgt + 1e-8)
                        if deficit > 0:
                            boost = 1.0 + deficit * 2.0
                            coeffs.append(self._current_exit_coeff * boost)
                        else:
                            # Above target: reduce but keep small gradient
                            coeffs.append(self._current_exit_coeff * 0.5)
                
                per_sample_coeff = torch.tensor(coeffs, dtype=torch.float32, device=self.device)
                entropy_loss = -(entropy * per_sample_coeff).mean()

                # ── MoE Load Balancing Loss ──
                expert_mean_prob = gating_probs.mean(dim=0)
                moe_loss = RL_CONFIG.get("moe_load_balance_coeff", 0.01) * torch.sum(expert_mean_prob ** 2) * gating_probs.size(1)

                # Total loss
                # Values and returns both normalized by ret_std — stable scale regardless of hold duration
                loss = (policy_loss
                        + RL_CONFIG["value_loss_coeff"] * value_loss
                        + entropy_loss
                        + moe_loss)

                if not torch.isfinite(loss):
                    print(f"  [!] Non-finite loss detected: {loss.item()}. Skipping batch.")
                    continue

                self.optimizer.zero_grad()
                loss.backward()

                # Gradient cleaning & clipping
                for p in self.agent.parameters():
                    if p.grad is not None:
                        if not torch.isfinite(p.grad).all():
                            p.grad.zero_() # Wipe corrupted gradients
                        else:
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
                if total_gating_probs is None:
                    total_gating_probs = expert_mean_prob.detach().cpu().numpy()
                else:
                    total_gating_probs += expert_mean_prob.detach().cpu().numpy()
                
                n_batches += 1
            
            # KL early stopping (Fix 1) — relaxed to 3x to allow entropy gradients to flow
            if stop_update or (epoch_kls and np.mean(epoch_kls) > kl_target * 1.5):
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
            "moe_gating":   total_gating_probs / n_batches if total_gating_probs is not None else np.ones(1),
        }

    def pretrain_critic(self):
        epochs = RL_CONFIG.get("pretrain_critic_epochs", 10)
        samples = RL_CONFIG.get("pretrain_critic_samples", 5000)
        
        print("\n" + "=" * 70)
        print(f"PRE-TRAINING CRITIC (Value Head) - {epochs} epochs, {samples} samples")
        print("=" * 70)
        
        # Target transitions, not episodes. The old formula requested only
        # ~13 episodes for 5k samples, leaving the critic nearly untrained.
        pretrain_episodes = max(128, int(np.ceil(samples / 20)))
        buffer, _ = self.collect_episodes(
            n_episodes=pretrain_episodes,
            min_confidence=0.5,
            min_strike=0,
            training=True,
            update_step=0,
            obs_noise=False,
            logit_noise_level=0.5
        )
        
        if len(buffer) == 0:
            print("[!] No data collected for pre-training. Skipping.")
            return

        print(
            f"[RL] Collected {len(buffer)} transitions from {pretrain_episodes} "
            f"episodes for Value Pre-training."
        )
        
        for param in self.agent.strike_head.parameters(): param.requires_grad = False
        for param in self.agent.exit_head.parameters(): param.requires_grad = False
        if hasattr(self.agent, "sniper_head"):
            for param in self.agent.sniper_head.parameters(): param.requires_grad = False
            
        value_optimizer = optim.Adam(
            list(self.agent.value_head.parameters()) + 
            list(self.agent.backbone.parameters()),
            lr=RL_CONFIG.get("learning_rate", 3e-4) * 3
        )
        
        self.agent.train()
        for epoch in range(epochs):
            total_loss = 0.0
            batches = 0
            for batch in buffer.get_batches(RL_CONFIG["batch_size"]):
                states = batch["states"].to(self.device)
                returns = batch["returns"].to(self.device)
                
                _, _, values, _ = self.agent.evaluate_actions(states, batch["actions"], batch["action_types"])
                
                loss = nn.MSELoss()(values, returns)
                
                value_optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.agent.parameters(), 1.0)
                value_optimizer.step()
                
                total_loss += loss.item()
                batches += 1
            
            print(f"  Epoch {epoch+1}/{epochs} - Value Loss: {total_loss/max(batches, 1):.4f}")
            
        for param in self.agent.parameters():
            param.requires_grad = True
            
        print("Pre-training complete.\n")

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
        print("PPO-RL TRAINING - SPX 0DTE OPTIONS AGENT")
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
        rolling_gating = []
        step_times = []
        self._next_logit_noise = 0.0
        strike_collapse_counter = 0  # Track consecutive low-entropy strike steps

        # Eval history for overfitting comparison
        eval_history = {
            "step": [], "eval_pf": [], "eval_wr": [], "eval_pnl": [],
            "train_pf": [], "train_wr": [], "train_pnl": [],
            "stochastic_train_pf": [], # Added for Issue 2
        }

        train_start = time.time()

        if RL_CONFIG.get("pretrain_critic_epochs", 0) > 0:
            self.pretrain_critic()

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
            non_trade_exit_types = {"entry_skip", "sniper_timeout"}
            trade_infos = [
                info for info in episode_infos
                if info.get("exit_type") not in non_trade_exit_types
            ]
            skip_count = sum(
                1 for info in episode_infos
                if info.get("exit_type") in non_trade_exit_types
            )
            entry_rate = len(trade_infos) / max(len(episode_infos), 1)
            pnl_pcts = [info["final_pnl_pct"] for info in trade_infos
                        if "final_pnl_pct" in info]
            hold_mins = [info["hold_minutes"] for info in trade_infos
                         if "hold_minutes" in info]
            exit_types = [info["exit_type"] for info in trade_infos
                          if "exit_type" in info]
            directions = [info.get("direction", "?") for info in trade_infos]

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
            # Logging
            rolling_policy_loss.append(losses["policy_loss"])
            rolling_value_loss.append(losses["value_loss"])
            rolling_entropy.append(losses["entropy_loss"])
            rolling_mean_entropy.append(losses.get("mean_entropy", 0.05))
            rolling_kl.append(losses.get("approx_kl", 0))
            rolling_gating.append(np.asarray(losses.get("moe_gating", np.ones(1)), dtype=float).reshape(-1))

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
                rolling_gating.pop(0)

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
                bar = "=" * filled + "." * (bar_len - filled)

                # Rolling averages (protect vs empty)
                r_pf = np.mean(rolling_pf) if rolling_pf else 1.0
                r_wr = np.mean(rolling_wr) if rolling_wr else 0.5
                r_pnl = np.mean(rolling_pnl) if rolling_pnl else 0.0
                r_pi = np.mean(rolling_policy_loss) if rolling_policy_loss else 0.0
                r_v = np.mean(rolling_value_loss) if rolling_value_loss else 0.0
                r_h = np.mean(rolling_mean_entropy) if rolling_mean_entropy else 0.08
                r_kl = np.mean(rolling_kl) if rolling_kl else 0.0
                r_gating = (
                    np.mean(np.vstack(rolling_gating), axis=0)
                    if rolling_gating else np.ones(1)
                )
                gating_str = "[" + ", ".join([f"{x:.2f}" for x in r_gating]) + "]"

                # Issue 1: Display per-head entropy to detect collapse early
                h_s = losses.get("h_strike", 0.0)
                h_e = losses.get("h_exit", 0.0)

                print(f"\n  [{bar}] {pct_done:5.1f}% | Update {update_step}/{total_updates} | "
                      f"ETA: {eta_min:.1f}min | Phase {phase_info['phase']}")
                print(f"  |- Current:    PF={profit_factor:.2f} WR={win_rate:.1%} "
                      f"PnL={mean_pnl:+.4f} Hold={mean_hold:.0f}m "
                      f"L/S={n_long}/{n_short} Stop={hard_stop_rate:.0%} "
                      f"Entry={entry_rate:.0%} Skip={skip_count}")
                
                # Per-head entropy monitor with strike coefficient visibility
                strike_c = getattr(self, '_current_strike_coeff', 0.0)
                exit_c = getattr(self, '_current_exit_coeff', 0.0)
                print(f"  |- Entropy:    {r_h:.4f} (target: 0.03-0.10) "
                      f"H[Strike]={h_s:.2f} H[Exit]={h_e:.2f} "
                      f"coeff_s={strike_c:.4f} coeff_e={exit_c:.4f}")
                print(f"  |- Approx KL:  {losses.get('approx_kl', 0):.4f} (avg:{r_kl:.4f})")
                print(f"  |- MoE Gating: {gating_str}")
                
                # Strike collapse warning
                if h_s < 0.10:
                    strike_collapse_counter += 1
                    if strike_collapse_counter >= 5:
                        print(f"  [!!] STRIKE COLLAPSE WARNING: H[Strike]={h_s:.4f} < 0.10 "
                              f"for {strike_collapse_counter} consecutive steps")
                else:
                    strike_collapse_counter = 0

                if RL_CONFIG.get("use_sniper_mode"):
                    print(f"  |- Sniper:     AvgWait={mean_sniper_wait:.1f}m "
                          f"Timeouts={sniper_timeouts}/{len(episode_infos)}")
                
                print(f"  |- Rolling{ROLLING_WINDOW:2d}: PF={r_pf:.2f} WR={r_wr:.1%} "
                      f"PnL={r_pnl:+.4f}")
                print(f"  |- Losses:     pi={losses['policy_loss']:.4f} V={losses['value_loss']:.4f} "
                      f"(avg: pi={r_pi:.4f} V={r_v:.4f})")
                print(f"  `- Timing:     {elapsed:.1f}s/step | "
                      f"Total: {(time.time()-train_start)/60:.1f}min")

            # ─── EVAL + OVERFITTING CHECK ───
            if update_step > 0 and update_step % eval_interval == 0:
                print(f"\n  {'-'*60}")
                print(f"  EVAL CHECKPOINT (step {update_step})")
                print(f"  {'-'*60}")

                # Collect eval episodes (no augmentation, deterministic)
                eval_buffer, eval_infos = self.collect_episodes(
                    n_episodes=max(min(n_episodes, 200), RL_CONFIG.get("eval_episodes", 200)),
                    min_confidence=min_conf,
                    min_strike=min_strike,
                    training=False,  # No augmentation, deterministic
                    update_step=update_step,
                    obs_noise=False # No observation noise for eval
                )

                eval_trade_infos = [
                    info for info in eval_infos
                    if info.get("exit_type") not in non_trade_exit_types
                ]
                eval_skip_count = len(eval_infos) - len(eval_trade_infos)
                eval_entry_rate = len(eval_trade_infos) / max(len(eval_infos), 1)
                eval_pnls = [info["final_pnl_pct"] for info in eval_trade_infos
                             if "final_pnl_pct" in info]

                if eval_pnls:
                    eval_wins = [p for p in eval_pnls if p > 0]
                    eval_losses = [p for p in eval_pnls if p <= 0]
                    eval_wr = len(eval_wins) / len(eval_pnls)
                    eval_pf_num = sum(eval_wins) if eval_wins else 0
                    eval_pf_den = abs(sum(eval_losses)) if eval_losses else 1e-6
                    eval_pf = eval_pf_num / eval_pf_den if eval_pf_den > 0 else 0
                    eval_mean_pnl = np.mean(eval_pnls)
                    eval_exit_types = [info.get("exit_type", "") for info in eval_trade_infos]
                    eval_hold_minutes = [
                        info.get("hold_minutes", 0) for info in eval_trade_infos
                        if "hold_minutes" in info
                    ]
                    eval_mean_hold = float(np.mean(eval_hold_minutes)) if eval_hold_minutes else 0.0
                    eval_agent_exit_rate = (
                        sum(1 for e in eval_exit_types if e == "agent_exit") / len(eval_exit_types)
                        if eval_exit_types else 0.0
                    )
                    eval_hard_stop_rate = (
                        sum(1 for e in eval_exit_types if e == "hard_stop_loss") / len(eval_exit_types)
                        if eval_exit_types else 0.0
                    )
                else:
                    eval_wr = eval_pf = eval_mean_pnl = 0
                    eval_hard_stop_rate = 0.0
                    eval_mean_hold = 0.0
                    eval_agent_exit_rate = 0.0
                    eval_entry_rate = 0.0
                    eval_skip_count = len(eval_infos)

                # Use rolling train stats for comparison
                train_pf_avg = np.mean(rolling_pf)
                train_wr_avg = np.mean(rolling_wr)
                train_pnl_avg = np.mean(rolling_pnl)

                eval_history["step"].append(update_step)
                eval_history["eval_pf"].append(eval_pf)
                eval_history["eval_wr"].append(eval_wr)
                eval_history["eval_pnl"].append(eval_mean_pnl)
                eval_history.setdefault("eval_hard_stop_rate", []).append(eval_hard_stop_rate)
                eval_history.setdefault("eval_entry_rate", []).append(eval_entry_rate)
                eval_history["train_pf"].append(train_pf_avg)
                eval_history["train_wr"].append(train_wr_avg)
                eval_history["train_pnl"].append(train_pnl_avg)

                print(f"  {'Metric':<18} {'Train (rolling)':>16} {'Eval (determ.)':>16} {'Gap':>10}")
                print(f"  {'-'*60}")
                print(f"  {'Profit Factor':<18} {train_pf_avg:>16.2f} {eval_pf:>16.2f} "
                      f"{train_pf_avg - eval_pf:>+10.2f}")
                print(f"  {'Win Rate':<18} {train_wr_avg:>15.1%} {eval_wr:>15.1%} "
                      f"{(train_wr_avg - eval_wr)*100:>+9.1f}%")
                print(f"  {'Mean PnL':<18} {train_pnl_avg:>+16.4f} {eval_mean_pnl:>+16.4f} "
                      f"{train_pnl_avg - eval_mean_pnl:>+10.4f}")
                print(f"  {'Hard Stop Rate':<18} {hard_stop_rate:>15.1%} {eval_hard_stop_rate:>15.1%} "
                      f"{(hard_stop_rate - eval_hard_stop_rate)*100:>+9.1f}%")
                print(f"  {'Mean Hold':<18} {mean_hold:>15.1f}m {eval_mean_hold:>15.1f}m "
                      f"{mean_hold - eval_mean_hold:>+9.1f}m")
                print(f"  {'Agent Exit Rate':<18} {'':>16} {eval_agent_exit_rate:>15.1%} {'':>10}")
                print(f"  {'Entry Rate':<18} {entry_rate:>15.1%} {eval_entry_rate:>15.1%} "
                      f"{(entry_rate - eval_entry_rate)*100:>+9.1f}%")
                print(f"  {'Skips':<18} {skip_count:>16} {eval_skip_count:>16} {'':>10}")

                # Overfitting warnings
                pf_gap = train_pf_avg - eval_pf
                wr_gap = train_wr_avg - eval_wr

                if pf_gap > 0.5 and eval_pf < 1.0:
                    print(f"\n  WARN OVERFITTING: Train PF >> Eval PF "
                          f"(gap={pf_gap:.2f}). Policy memorizing train episodes.")
                elif pf_gap > 0.3:
                    print(f"\n  WARN Mild overfitting: PF gap = {pf_gap:.2f}. Monitor closely.")
                elif eval_pf > train_pf_avg and eval_pf > 1.0:
                    print(f"\n  OK Healthy: Eval PF ({eval_pf:.2f}) >= Train PF ({train_pf_avg:.2f})")
                print(f"  Train:      PF {train_pf_avg:.2f} | WR {train_wr_avg:.1%} | PnL {train_pnl_avg:+.2%}")
                if eval_pf > 0:
                    pass # Already printed above
                if eval_wr < 0.40:
                    print(f"  WARN LOW EVAL WIN RATE: {eval_wr:.1%} - agent may be guessing.")

                # Quality Score: prefer PF/WR that survives deterministic OOS eval
                # and explicitly penalize policies that reach many hard stops.
                current_hold_min = phase_info.get("min_hold_minutes", 0)
                min_best_hold = float(RL_CONFIG.get("min_best_hold_minutes", 0))
                hold_factor = max(0.10, min(eval_mean_hold / 90.0, 1.50))
                wr_factor = max(eval_wr / 0.45, 0.10)
                hard_stop_factor = max(0.10, 1.0 - (eval_hard_stop_rate / 0.35))
                agent_exit_factor = max(0.10, 1.0 - max(0.0, eval_agent_exit_rate - 0.55) / 0.35)
                min_entry_rate = float(RL_CONFIG.get("min_best_entry_rate", 0.0))
                entry_rate_factor = (
                    max(0.10, min(eval_entry_rate / max(min_entry_rate, 1e-6), 1.25))
                    if min_entry_rate > 0
                    else 1.0
                )
                current_score = (
                    eval_pf
                    * hold_factor
                    * wr_factor
                    * hard_stop_factor
                    * agent_exit_factor
                    * entry_rate_factor
                )

                if (
                    current_score > getattr(self, "best_score", 0)
                    and update_step > 10
                    and current_hold_min >= min_best_hold
                    and eval_entry_rate >= min_entry_rate
                ):
                    self.best_score = current_score
                    self.best_profit_factor = eval_pf
                    self.agent.save(os.path.join(save_dir, "best_rl_agent.pt"), update_step=update_step)
                    print(f"  -> New best Model found at step {update_step}")
                    print(
                        f"     Score: {current_score:.3f} "
                        f"(PF: {eval_pf:.2f} * HoldFactor: {hold_factor:.2f} * "
                        f"WRFactor: {wr_factor:.2f} * HardStopFactor: {hard_stop_factor:.2f} * "
                        f"AgentExitFactor: {agent_exit_factor:.2f} * "
                        f"EntryRateFactor: {entry_rate_factor:.2f})"
                    )
                elif current_hold_min < min_best_hold:
                    print(
                        f"  -> Best checkpoint gated: curriculum min_hold "
                        f"{current_hold_min}m < required {min_best_hold:.0f}m"
                    )
                elif eval_entry_rate < min_entry_rate:
                    print(
                        f"  -> Best checkpoint gated: eval entry rate "
                        f"{eval_entry_rate:.1%} < required {min_entry_rate:.1%}"
                    )

                # [NEW] Save history periodically
                combined_history = {**self.history, "eval": eval_history}
                with open(os.path.join(save_dir, "rl_training_history.json"), "w") as f:
                    json.dump(combined_history, f, indent=2)

                # ── EARLY STOPPING on Eval PF degradation ──
                # If Eval PF has degraded for N consecutive checkpoints after
                # a good-enough best was found, stop to prevent overfitting.
                eval_patience = 3
                if len(eval_history["eval_pf"]) >= eval_patience + 1:
                    best_ever_pf = max(eval_history["eval_pf"])
                    recent_pfs = eval_history["eval_pf"][-eval_patience:]
                    if all(pf < best_ever_pf * 0.85 for pf in recent_pfs) and best_ever_pf > 1.5:
                        print(f"\n  [EARLY STOP] Eval PF degraded for {eval_patience} consecutive "
                              f"checkpoints. Best={best_ever_pf:.2f}, "
                              f"Recent={[f'{p:.2f}' for p in recent_pfs]}")
                        print(f"  Stopping training at step {update_step} to prevent overfitting.")
                        print(f"  {'-'*60}")
                        break

                print(f"  {'-'*60}")

            # Periodic checkpoint
            if (update_step + 1) % 50 == 0:
                self.agent.save(os.path.join(save_dir, f"rl_agent_step_{update_step}.pt"), update_step=update_step)

        # Final save
        self.agent.save(os.path.join(save_dir, "final_rl_agent.pt"), update_step=total_updates)

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


def init_worker(
    episode_index_path,
    options_cache_dir,
    max_days,
    feature_columns,
    state_dim,
    hidden_dims,
    use_entry_skip_action=False,
    force_hold_exit_training=False,
):
    """Initialize global environment and agent per worker process."""
    global g_worker_env, g_worker_agent
    import pandas as pd
    from rl.environment import SPXOptionsEnv
    from rl.agent import PPOAgent
    from rl.config import RL_CONFIG
    RL_CONFIG["use_entry_skip_action"] = bool(use_entry_skip_action)
    RL_CONFIG["force_hold_exit_training"] = bool(force_hold_exit_training)
    
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
        episode_action_masks = []
        episode_policy_active = []
        episode_rewards = []
        episode_log_probs = []
        episode_values = []
        episode_dones = []
        
        done = False
        step_count = 0
        
        # ── Pre-build strike action mask (fijo por episodio según currículo) ──
        # Alinea la distribución de política con lo que el entorno realmente ejecuta.
        # Sin esta máscara el agente muestrea libremente y el env corrige en silencio,
        # creando una discrepancia política/entorno que colapsa el strike head en deep_otm.
        from rl.config import NUM_STRIKE_ACTIONS, NUM_EXIT_ACTIONS, NUM_SNIPER_ACTIONS
        _n_strike = NUM_STRIKE_ACTIONS  # 7
        strike_action_mask = [
            (min_strike <= i <= max_strike) for i in range(_n_strike)
        ]
        # Garantía de seguridad: al menos un bucket válido
        if not any(strike_action_mask):
            strike_action_mask = [True] * _n_strike
        entry_action_mask = [True] + list(strike_action_mask)

        with torch.no_grad():
            while not done and step_count < RL_CONFIG["session_length_minutes"]:
                state_input = augment_state(state) if obs_noise else state
                # Ensure it runs on CPU inside the worker
                state_tensor = torch.FloatTensor(state_input).unsqueeze(0)
                
                if g_worker_env._position is None and (
                    g_worker_env._use_sniper or RL_CONFIG.get("use_entry_skip_action", False)
                ):
                    action_type = "sniper_entry"
                    current_mask = entry_action_mask
                elif g_worker_env._position is None:
                    action_type = "strike"
                    current_mask = strike_action_mask
                else:
                    action_type = "exit"
                    current_mask = None  # exit es binario, sin restricción
                    
                force_hold_exit = (
                    action_type == "exit"
                    and RL_CONFIG.get("force_hold_exit_training", False)
                )
                if force_hold_exit:
                    _, value = g_worker_agent.forward(state_tensor, action_type)
                    action = 0
                    log_prob = torch.zeros(1)
                else:
                    # Fix: Apply logit noise to 'exit' if policy is collapsing (dynamic)
                    # Also keep the early-phase strike noise for exploration
                    l_noise = 0.0
                    if action_type in ("strike", "sniper_entry") and update_step < (total_updates * 0.1):
                        l_noise = 0.5
                    elif action_type == "exit":
                        # Exit Head: HOLD(0) or EXIT(1)
                        override = RL_CONFIG.get("logit_noise_exit_override", 0.0)
                        l_noise = max(logit_noise_level, override)

                    action, log_prob, value = g_worker_agent.get_action(
                        state_tensor, action_type, deterministic=False,
                        logit_noise=l_noise, action_mask=current_mask)
                    
                action_val = action
                value_float = value.item() if isinstance(value, torch.Tensor) else value
                
                env_action = action_val["strike"] if isinstance(action_val, dict) else action_val
                next_state, reward, done, info = g_worker_env.step(env_action)
                
                # [FIX] Mismatch detection in worker
                # Si el entorno forzó una acción diferente (e.g. min_hold),
                # recalculamos el log_prob con la máscara correcta.
                effective_action = info.get("effective_action", action_val)
                policy_active = (effective_action == action_val) and not force_hold_exit
                if effective_action != action_val:
                    with torch.no_grad():
                        new_log_probs, _, _, _ = g_worker_agent.evaluate_actions(
                            state_tensor, [effective_action], [action_type],
                            action_masks=[current_mask])
                        log_prob_float = new_log_probs.item()
                else:
                    log_prob_float = log_prob.item() if isinstance(log_prob, torch.Tensor) else log_prob

                episode_states.append(state)
                episode_actions.append(effective_action)
                episode_action_types.append(action_type)
                episode_action_masks.append(current_mask)
                episode_policy_active.append(policy_active)
                episode_rewards.append(reward)
                episode_log_probs.append(log_prob_float)
                episode_values.append(value_float)
                episode_dones.append(done)
                
                state = next_state
                step_count += 1
                
        if step_count > 0:
            return (
                episode_states, episode_actions, episode_action_types,
                episode_action_masks, episode_policy_active,
                episode_rewards, episode_log_probs, episode_values,
                episode_dones, info,
            )
            
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
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=None,
        help="Override RL_CONFIG min_confidence and curriculum phase thresholds.",
    )
    parser.add_argument("--max-days-in-ram", type=int, default=260,
                        help="Max number of day shards to keep in RAM (LRU)")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of background CPU workers for data collection")
    parser.add_argument(
        "--entry-skip-action",
        action="store_true",
        help="Use sniper_head as direct SKIP(0) / ENTER+strike(1-7) entry policy.",
    )
    parser.add_argument(
        "--force-hold-exit",
        action="store_true",
        help="During training, force exit actions to HOLD and train only entry/strike plus critic.",
    )
    parser.add_argument(
        "--strike-oracle-pretrain-samples",
        type=int,
        default=0,
        help="Train-period episodes to label with all-strike oracle before PPO (0 disables).",
    )
    parser.add_argument(
        "--strike-oracle-pretrain-epochs",
        type=int,
        default=3,
        help="Supervised epochs for --strike-oracle-pretrain-samples.",
    )
    parser.add_argument(
        "--strike-oracle-pretrain-lr",
        type=float,
        default=1e-4,
        help="Learning rate for strike oracle supervised warm-start.",
    )
    parser.add_argument(
        "--entry-oracle-labels",
        type=str,
        default=None,
        help="CSV from strike oracle labels to train SKIP/ENTER+bucket sniper_head.",
    )
    parser.add_argument(
        "--entry-oracle-pretrain-epochs",
        type=int,
        default=8,
        help="Supervised epochs for --entry-oracle-labels.",
    )
    parser.add_argument(
        "--entry-oracle-pretrain-lr",
        type=float,
        default=1e-4,
        help="Learning rate for entry oracle supervised warm-start.",
    )
    parser.add_argument(
        "--entry-oracle-target-entry-rate",
        type=float,
        default=0.75,
        help="Train-label entry rate used to set per-ticker SKIP thresholds.",
    )
    parser.add_argument(
        "--entry-oracle-min-enter-pnl",
        type=float,
        default=None,
        help="Fixed best_pnl_pct threshold for ENTER labels; overrides target entry-rate quantile.",
    )
    parser.add_argument(
        "--entry-oracle-fixed-enter-bucket",
        type=int,
        default=None,
        help="If set, all ENTER labels use this bucket instead of oracle best bucket.",
    )
    parser.add_argument(
        "--entry-oracle-only",
        action="store_true",
        help="Save entry-oracle checkpoint as best/final and skip PPO updates.",
    )
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
    if args.min_confidence is not None:
        RL_CONFIG["min_confidence"] = float(args.min_confidence)
        for phase in RL_CONFIG.get("curriculum_phases", {}).values():
            phase["min_confidence"] = float(args.min_confidence)
        print(f"[RL] min_confidence override: {args.min_confidence:.3f}")
    if args.entry_skip_action:
        RL_CONFIG["use_entry_skip_action"] = True
        print("[RL] entry skip action enabled: SKIP(0) / ENTER+strike(1-7)")
    if args.force_hold_exit:
        RL_CONFIG["force_hold_exit_training"] = True
        print("[RL] force-hold exit training enabled: exit head policy gradients disabled")

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
    if args.strike_oracle_pretrain_samples and args.strike_oracle_pretrain_samples > 0:
        trainer.pretrain_strike_oracle(
            samples=args.strike_oracle_pretrain_samples,
            epochs=args.strike_oracle_pretrain_epochs,
            lr=args.strike_oracle_pretrain_lr,
            min_confidence=args.min_confidence,
            save_dir=args.save_dir,
        )
    if args.entry_oracle_labels:
        trainer.pretrain_entry_oracle_from_labels(
            labels_path=args.entry_oracle_labels,
            epochs=args.entry_oracle_pretrain_epochs,
            lr=args.entry_oracle_pretrain_lr,
            target_entry_rate=args.entry_oracle_target_entry_rate,
            min_enter_pnl=args.entry_oracle_min_enter_pnl,
            fixed_enter_bucket=args.entry_oracle_fixed_enter_bucket,
            save_dir=args.save_dir,
        )
        if args.entry_oracle_only:
            os.makedirs(args.save_dir, exist_ok=True)
            agent.save(os.path.join(args.save_dir, "best_rl_agent.pt"), update_step=0)
            agent.save(os.path.join(args.save_dir, "final_rl_agent.pt"), update_step=0)
            print("[RL] entry-oracle-only enabled: saved best/final checkpoint and skipped PPO.")
            sys.exit(0)
    trainer.train(save_dir=args.save_dir)
