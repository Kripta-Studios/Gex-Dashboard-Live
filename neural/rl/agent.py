"""
PPO Agent — Shared-Backbone with Triple Action Heads

Architecture:
    State(181/183) → Backbone(256→256→128) → Strike Head(7) + Exit Head(2)
                                            + Sniper Head(8) + Value Head(1)

The Strike Head is only active at trade entry (immediate mode).
The Sniper Head is active during PRE_ENTRY phase (WAIT=0, ENTER+strike=1-7).
The Exit Head is active every minute while a position is open.
The Value Head (critic) is shared across all action types.

NOTE: sizing_head was removed — it was trained but never used in production,
introducing noise into PPO gradients without affecting actual position sizing.
"""

# pyrefly: ignore [missing-import]
import torch
import torch.nn as nn
import numpy as np
from torch.distributions import Categorical
from pathlib import Path

from .config import RL_CONFIG, NUM_STRIKE_ACTIONS, NUM_EXIT_ACTIONS, NUM_SNIPER_ACTIONS


class PPOAgent(nn.Module):
    """
    Proximal Policy Optimization agent with shared backbone and triple action heads.
    """

    def __init__(self, state_dim: int = None, hidden_dims: list = None):
        super().__init__()
        self.state_dim = state_dim or RL_CONFIG["state_dim"]
        self.update_step = 0
        self.total_updates = RL_CONFIG.get("total_updates", 500)
        hidden_dims = hidden_dims or RL_CONFIG["hidden_dims"]

        # ── Pure MLP Backbone ──
        layers = []
        prev = self.state_dim
        for h in hidden_dims:
            layers.extend([
                nn.Linear(prev, h),
                nn.LayerNorm(h),
                nn.GELU(),
                nn.Dropout(RL_CONFIG.get("backbone_dropout", 0.1)),
            ])
            prev = h
        self.backbone = nn.Sequential(*layers)

        last_dim = hidden_dims[-1]
        self.last_dim = last_dim

        # ── Strike selection head (immediate entry, 7 delta buckets) ──
        self.strike_head = nn.Sequential(
            nn.Linear(last_dim, 64),
            nn.GELU(),
            nn.Linear(64, NUM_STRIKE_ACTIONS),
        )

        # ── Exit decision head (every minute, HOLD/EXIT) ──
        self.exit_head = nn.Sequential(
            nn.Linear(last_dim, 64),
            nn.GELU(),
            nn.Linear(64, NUM_EXIT_ACTIONS),
        )

        # ── Sniper entry head (PRE_ENTRY phase: WAIT=0, ENTER+strike=1-7) ──
        self.sniper_head = nn.Sequential(
            nn.Linear(last_dim, 64),
            nn.GELU(),
            nn.Linear(64, NUM_SNIPER_ACTIONS),
        )

        # NOTE: sizing_head removed — was trained but never used in production.
        # Its gradients added noise to the shared backbone without affecting returns.

        # ── Value head (critic, shared) ──
        self.value_head = nn.Sequential(
            nn.Linear(last_dim, 64),
            nn.GELU(),
            nn.Linear(64, 1),
        )

        self._init_weights()

    def _init_weights(self):
        """Initialize with small weights to prevent early overfitting."""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=1.0)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

        # Start the exit policy slightly biased toward HOLD. The environment
        # still enforces emergency/hard exits, but this prevents fresh PPO
        # runs from discovering the trivial min-hold EXIT shortcut first.
        exit_out = self.exit_head[-1]
        if isinstance(exit_out, nn.Linear) and exit_out.bias is not None:
            with torch.no_grad():
                exit_out.bias[0] = 0.30
                exit_out.bias[1] = -0.30

    def _forward_backbone(self, state: torch.Tensor):
        features = self.backbone(state)
        # Return dummy gating probs for compatibility with existing training loop
        gating_probs = torch.ones(state.size(0), 1, device=state.device)
        return features, gating_probs

    def forward(self, state: torch.Tensor, action_type: str = "exit"):
        """
        Forward pass through backbone + appropriate head.

        Args:
            state: (batch, state_dim) tensor
            action_type: "strike" (entry), "exit" (holding), or "sniper_entry" (pre-entry)

        Returns:
            logits: action logits from the appropriate head
            value:  critic state value estimate
        """
        features, _ = self._forward_backbone(state)
        value = self.value_head(features).squeeze(-1)

        if action_type == "strike":
            logits = self.strike_head(features)
        elif action_type == "sniper_entry":
            logits = self.sniper_head(features)
        else:
            logits = self.exit_head(features)

        # Clamp logits to prevent extreme values and numerical instability
        logits = torch.clamp(logits, -20.0, 20.0)

        return logits, value

    @staticmethod
    def _apply_action_mask(logits: torch.Tensor, action_mask):
        """Mask invalid discrete actions by removing them from the policy support."""
        if action_mask is None:
            return logits

        mask = torch.as_tensor(action_mask, dtype=torch.bool, device=logits.device)
        if mask.dim() == 1:
            mask = mask.unsqueeze(0).expand_as(logits)
        else:
            mask = mask.to(logits.device)
            if mask.shape != logits.shape:
                mask = mask.expand_as(logits)

        if not mask.any(dim=-1).all():
            raise ValueError("Action mask must leave at least one valid action per sample")

        return logits.masked_fill(~mask, torch.finfo(logits.dtype).min)

    def get_action(self, state: torch.Tensor, action_type: str,
                   deterministic: bool = False, logit_noise: float = 0.0,
                   action_mask=None):
        """
        Sample an action from the policy or take argmax.
        """
        logits, value = self.forward(state, action_type)
        
        # Save clean logits for true policy log_prob calculation (Crucial for PPO stability)
        clean_logits = self._apply_action_mask(logits.clone(), action_mask)

        if not deterministic and logit_noise > 0:
            noise = torch.randn_like(logits) * logit_noise
            logits = logits + noise
        logits = self._apply_action_mask(logits, action_mask)

        if action_type == "strike":
            # Discrete Strike (delta bucket 0-6)
            dist_original = Categorical(logits=logits)
            
            if not deterministic:
                with torch.no_grad():
                    if dist_original.entropy().item() < 0.5:
                        # Temperature scaling for EXPLORATION only
                        logits = logits / 2.0

            if deterministic:
                action = torch.argmax(logits, dim=-1)
            else:
                dist_sample = Categorical(logits=logits)
                action = dist_sample.sample()
            
            # CRITICAL: Always store log_prob from the TRUE CLEAN policy distribution
            dist_clean = Categorical(logits=clean_logits)
            log_prob = dist_clean.log_prob(action)
            action = action.item()

        elif action_type == "sniper_entry":
            # Discrete Sniper: WAIT(0) or ENTER with strike(1-7)
            dist = Categorical(logits=logits)
            if deterministic:
                action = torch.argmax(logits, dim=-1)
            else:
                action = dist.sample()
            dist_clean = Categorical(logits=clean_logits)
            log_prob = dist_clean.log_prob(action)
            action = action.item()

        else:
            # Discrete Exit: HOLD(0) or EXIT(1)
            dist_original = Categorical(logits=logits)
            
            if not deterministic:
                with torch.no_grad():
                    if dist_original.entropy().item() < 0.15:
                        # Temperature scaling for EXPLORATION only
                        logits = logits / 2.0
            
            if deterministic:
                action = torch.argmax(logits, dim=-1)
            else:
                dist_sample = Categorical(logits=logits)
                action = dist_sample.sample()
                
            # CRITICAL: Always store log_prob from the TRUE CLEAN policy distribution
            dist_clean = Categorical(logits=clean_logits)
            log_prob = dist_clean.log_prob(action)
            action = action.item()

        return action, log_prob, value

    def evaluate_actions(self, states: torch.Tensor, actions: list,
                          action_types: list, action_masks=None,
                          detach_value: bool = False):
        """
        Evaluate log_probs and entropy for a batch of (state, action) pairs.
        Uses raw logits (no entropy guard) to ensure PPO ratios are valid.
        """
        features, gating_probs = self._forward_backbone(states)
        if detach_value:
            values = self.value_head(features.detach()).squeeze(-1)
        else:
            values = self.value_head(features).squeeze(-1)

        strike_logits = self.strike_head(features)
        exit_logits = self.exit_head(features)
        sniper_logits = self.sniper_head(features)

        # Classify each sample
        is_strike_list = []
        is_sniper_list = []
        strike_acts = []
        exit_acts = []
        sniper_acts = []
        strike_masks = []
        exit_masks = []
        sniper_masks = []
        action_masks = action_masks or [None] * len(action_types)

        for i, at in enumerate(action_types):
            raw_mask = action_masks[i]
            if at == "strike":
                is_strike_list.append(True)
                is_sniper_list.append(False)
                strike_acts.append(actions[i])
                exit_acts.append(0)
                sniper_acts.append(0)
                strike_masks.append(raw_mask if raw_mask is not None else [True] * NUM_STRIKE_ACTIONS)
                exit_masks.append([True] * NUM_EXIT_ACTIONS)
                sniper_masks.append([True] * NUM_SNIPER_ACTIONS)
            elif at == "sniper_entry":
                is_strike_list.append(False)
                is_sniper_list.append(True)
                strike_acts.append(0)
                exit_acts.append(0)
                sniper_acts.append(actions[i])
                strike_masks.append([True] * NUM_STRIKE_ACTIONS)
                exit_masks.append([True] * NUM_EXIT_ACTIONS)
                sniper_masks.append(raw_mask if raw_mask is not None else [True] * NUM_SNIPER_ACTIONS)
            else:
                is_strike_list.append(False)
                is_sniper_list.append(False)
                strike_acts.append(0)
                exit_acts.append(actions[i])
                sniper_acts.append(0)
                strike_masks.append([True] * NUM_STRIKE_ACTIONS)
                exit_masks.append(raw_mask if raw_mask is not None else [True] * NUM_EXIT_ACTIONS)
                sniper_masks.append([True] * NUM_SNIPER_ACTIONS)

        is_strike = torch.tensor(is_strike_list, dtype=torch.bool, device=states.device)
        is_sniper = torch.tensor(is_sniper_list, dtype=torch.bool, device=states.device)
        strike_acts_t = torch.tensor(strike_acts, dtype=torch.long, device=states.device)
        exit_acts_t = torch.tensor(exit_acts, dtype=torch.long, device=states.device)
        sniper_acts_t = torch.tensor(sniper_acts, dtype=torch.long, device=states.device)
        strike_masks_t = torch.tensor(strike_masks, dtype=torch.bool, device=states.device)
        exit_masks_t = torch.tensor(exit_masks, dtype=torch.bool, device=states.device)
        sniper_masks_t = torch.tensor(sniper_masks, dtype=torch.bool, device=states.device)

        # ── Strike evaluation (Raw) ──
        strike_logits = self._apply_action_mask(strike_logits, strike_masks_t)
        strike_dist = Categorical(logits=strike_logits)
        strike_acts_t = strike_acts_t.clamp(0, NUM_STRIKE_ACTIONS - 1)
        strike_log_probs = strike_dist.log_prob(strike_acts_t)
        strike_entropy = strike_dist.entropy()

        # ── Exit evaluation (Raw) ──
        exit_logits = self._apply_action_mask(exit_logits, exit_masks_t)
        exit_dist = Categorical(logits=exit_logits)
        exit_acts_t = exit_acts_t.clamp(0, NUM_EXIT_ACTIONS - 1)
        exit_log_probs = exit_dist.log_prob(exit_acts_t)
        exit_entropy = exit_dist.entropy()

        # ── Sniper evaluation ──
        sniper_logits = self._apply_action_mask(sniper_logits, sniper_masks_t)
        sniper_dist = Categorical(logits=sniper_logits)
        sniper_acts_t = sniper_acts_t.clamp(0, NUM_SNIPER_ACTIONS - 1)
        sniper_log_probs = sniper_dist.log_prob(sniper_acts_t)
        sniper_entropy = sniper_dist.entropy()

        # ── Select per-sample ──
        # Priority: strike > sniper > exit
        log_probs = torch.where(is_strike, strike_log_probs,
                     torch.where(is_sniper, sniper_log_probs, exit_log_probs))
        entropy = torch.where(is_strike, strike_entropy,
                   torch.where(is_sniper, sniper_entropy, exit_entropy))

        return log_probs, entropy, values, gating_probs

    def save(self, filepath: str, update_step: int = 0):
        """Save agent weights and metadata."""
        torch.save({
            "model_state_dict": self.state_dict(),
            "config": {
                "state_dim": self.state_dim,
                "hidden_dims": RL_CONFIG["hidden_dims"],
                "update_step": update_step,
                "total_updates": RL_CONFIG.get("total_updates", 500),
            }
        }, filepath)
        print(f"[RL] Agent saved to {filepath} (Step: {update_step})")

    @classmethod
    def load(cls, filepath: str, device: torch.device = None):
        """Load agent from checkpoint. Uses strict=False for backward compatibility."""
        if device is None:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        checkpoint = torch.load(filepath, map_location=device, weights_only=False)
        config = checkpoint["config"]
        # Use the checkpoint state dim for backward compatibility. Backtest
        # pads/trims states to agent.state_dim, while fresh training uses
        # RL_CONFIG["state_dim"] via the constructor default.
        agent = cls(state_dim=config.get("state_dim", RL_CONFIG["state_dim"]), hidden_dims=config["hidden_dims"])
        # strict=False: pre-sniper checkpoints won't have sniper_head weights
        agent.load_state_dict(checkpoint["model_state_dict"], strict=False)
        agent.to(device)
        
        # Restore metadata
        agent.update_step = config.get("update_step", 0)
        agent.total_updates = config.get("total_updates", RL_CONFIG.get("total_updates", 500))
        return agent
