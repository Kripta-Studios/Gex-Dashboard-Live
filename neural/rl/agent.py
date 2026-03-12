"""
PPO Agent — Shared-Backbone with Triple Action Heads

Architecture:
    State(173) → Backbone(256→256→128) → Strike Head(7) + Exit Head(2)
                                        + Sniper Head(8) + Value Head(1)

The Strike Head is only active at trade entry (immediate mode).
The Sniper Head is active during PRE_ENTRY phase (WAIT=0, ENTER+strike=1-7).
The Exit Head is active every minute while a position is open.
The Value Head (critic) is shared across all action types.
"""

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
        state_dim = state_dim or RL_CONFIG["state_dim"]
        hidden_dims = hidden_dims or RL_CONFIG["hidden_dims"]

        # ── Shared backbone ──
        layers = []
        prev = state_dim
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

        # ── Sizing head (continuous dimension fraction, entry only) ──
        self.sizing_head = nn.Sequential(
            nn.Linear(last_dim, 64),
            nn.GELU(),
            nn.Linear(64, 2)  # mu, log_std
        )

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
                nn.init.orthogonal_(m.weight, gain=0.5)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, state: torch.Tensor, action_type: str = "exit"):
        """
        Forward pass through backbone + appropriate head.

        Args:
            state: (batch, state_dim) tensor
            action_type: "strike" (entry), "exit" (holding), or "sniper_entry" (pre-entry)

        Returns:
            logits: action logits from the appropriate head
            size_params: sizing head output (only for strike), None otherwise
            value:  critic state value estimate
        """
        features = self.backbone(state)
        value = self.value_head(features).squeeze(-1)

        if action_type == "strike":
            logits = self.strike_head(features)
            size_params = self.sizing_head(features)
            return logits, size_params, value
        elif action_type == "sniper_entry":
            logits = self.sniper_head(features)
            return logits, None, value
        else:
            logits = self.exit_head(features)
            return logits, None, value

    def get_action(self, state: torch.Tensor, action_type: str,
                   deterministic: bool = False):
        """
        Sample an action from the policy or take argmax.

        Returns: (action, log_prob, value) — all tensors.
        """
        logits, size_params, value = self.forward(state, action_type)

        if action_type == "strike":
            # Discrete Strike
            if deterministic:
                # Use temperature scaling T=0.5 to sharpen distribution but preserve sampling
                dist = Categorical(logits=logits / 0.5)
                action_strike = dist.sample()
            else:
                dist = Categorical(logits=logits)
                action_strike = dist.sample()
            log_prob_strike = dist.log_prob(action_strike)
            
            # Continuous Size
            mu, log_std = size_params[:, 0], size_params[:, 1]
            std = torch.exp(torch.clamp(log_std, -20, 2))
            from torch.distributions import Normal
            size_dist = Normal(mu, std)
            
            if deterministic:
                action_size_raw = mu
            else:
                action_size_raw = size_dist.sample()
            log_prob_size_raw = size_dist.log_prob(action_size_raw)
            
            # Sigmoid bounded fraction
            action_size = torch.sigmoid(action_size_raw)
            derivative = torch.clamp(action_size * (1.0 - action_size), min=1e-8)
            log_prob_size = log_prob_size_raw - torch.log(derivative)
            
            action = {"strike": action_strike.item(), "size": action_size.item()}
            log_prob = log_prob_strike + log_prob_size

        elif action_type == "sniper_entry":
            # Discrete Sniper: WAIT(0) or ENTER with strike(1-7)
            if deterministic:
                dist = Categorical(logits=logits / 0.5)
                action = dist.sample()
            else:
                dist = Categorical(logits=logits)
                action = dist.sample()
            log_prob = dist.log_prob(action)
            action = action.item()

        else:
            # Discrete Exit
            if deterministic:
                dist = Categorical(logits=logits / 0.5)
                action = dist.sample()
            else:
                dist = Categorical(logits=logits)
                action = dist.sample()
            log_prob = dist.log_prob(action)
            action = action.item()

        return action, log_prob, value

    def evaluate_actions(self, states: torch.Tensor, actions: list,
                         action_types: list):
        """
        Evaluate log_probs and entropy for a batch of (state, action) pairs.
        actions is a list: dicts if 'strike', ints if 'exit' or 'sniper_entry'.
        """
        features = self.backbone(states)
        values = self.value_head(features).squeeze(-1)

        strike_logits = self.strike_head(features)
        size_params = self.sizing_head(features)
        exit_logits = self.exit_head(features)
        sniper_logits = self.sniper_head(features)

        # Classify each sample
        is_strike_list = []
        is_sniper_list = []
        strike_acts = []
        size_acts_final = []
        exit_acts = []
        sniper_acts = []

        for i, at in enumerate(action_types):
            if at == "strike":
                is_strike_list.append(True)
                is_sniper_list.append(False)
                strike_acts.append(actions[i]["strike"])
                size_acts_final.append(actions[i]["size"])
                exit_acts.append(0)
                sniper_acts.append(0)
            elif at == "sniper_entry":
                is_strike_list.append(False)
                is_sniper_list.append(True)
                strike_acts.append(0)
                size_acts_final.append(0.5)
                exit_acts.append(0)
                sniper_acts.append(actions[i])
            else:
                is_strike_list.append(False)
                is_sniper_list.append(False)
                strike_acts.append(0)
                size_acts_final.append(0.5)
                exit_acts.append(actions[i])
                sniper_acts.append(0)

        is_strike = torch.tensor(is_strike_list, dtype=torch.bool, device=states.device)
        is_sniper = torch.tensor(is_sniper_list, dtype=torch.bool, device=states.device)
        strike_acts_t = torch.tensor(strike_acts, dtype=torch.long, device=states.device)
        exit_acts_t = torch.tensor(exit_acts, dtype=torch.long, device=states.device)
        sniper_acts_t = torch.tensor(sniper_acts, dtype=torch.long, device=states.device)
        size_acts_final_t = torch.tensor(size_acts_final, dtype=torch.float32, device=states.device)

        # ── Strike evaluation ──
        strike_dist = Categorical(logits=strike_logits)
        strike_acts_t = strike_acts_t.clamp(0, NUM_STRIKE_ACTIONS - 1)
        strike_log_probs = strike_dist.log_prob(strike_acts_t)
        strike_entropy = strike_dist.entropy()

        # Size evaluation
        mu, log_std = size_params[:, 0], size_params[:, 1]
        std = torch.exp(torch.clamp(log_std, -20, 2))
        from torch.distributions import Normal
        size_dist = Normal(mu, std)

        safe_y = torch.clamp(size_acts_final_t, min=1e-6, max=1.0-1e-6)
        x_raw = torch.log(safe_y / (1.0 - safe_y))
        size_log_probs_raw = size_dist.log_prob(x_raw)
        derivative = safe_y * (1.0 - safe_y)
        size_log_probs = size_log_probs_raw - torch.log(derivative)
        size_entropy = size_dist.entropy()

        total_strike_log_probs = strike_log_probs + size_log_probs
        total_strike_entropy = strike_entropy + size_entropy

        # ── Exit evaluation ──
        exit_dist = Categorical(logits=exit_logits)
        exit_acts_t = exit_acts_t.clamp(0, NUM_EXIT_ACTIONS - 1)
        exit_log_probs = exit_dist.log_prob(exit_acts_t)
        exit_entropy = exit_dist.entropy()

        # ── Sniper evaluation ──
        sniper_dist = Categorical(logits=sniper_logits)
        sniper_acts_t = sniper_acts_t.clamp(0, NUM_SNIPER_ACTIONS - 1)
        sniper_log_probs = sniper_dist.log_prob(sniper_acts_t)
        sniper_entropy = sniper_dist.entropy()

        # ── Select per-sample ──
        # Priority: strike > sniper > exit
        log_probs = torch.where(is_strike, total_strike_log_probs,
                     torch.where(is_sniper, sniper_log_probs, exit_log_probs))
        entropy = torch.where(is_strike, total_strike_entropy,
                   torch.where(is_sniper, sniper_entropy, exit_entropy))

        return log_probs, entropy, values

    def save(self, filepath: str):
        """Save agent weights."""
        torch.save({
            "model_state_dict": self.state_dict(),
            "config": {
                "state_dim": RL_CONFIG["state_dim"],
                "hidden_dims": RL_CONFIG["hidden_dims"],
            }
        }, filepath)
        print(f"[RL] Agent saved to {filepath}")

    @classmethod
    def load(cls, filepath: str, device: torch.device = None):
        """Load agent from checkpoint. Uses strict=False for backward compatibility."""
        if device is None:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        checkpoint = torch.load(filepath, map_location=device, weights_only=False)
        config = checkpoint["config"]
        # Use current state_dim (which may be 173 with sniper) rather than checkpoint's
        agent = cls(state_dim=RL_CONFIG["state_dim"], hidden_dims=config["hidden_dims"])
        # strict=False: pre-sniper checkpoints won't have sniper_head weights
        agent.load_state_dict(checkpoint["model_state_dict"], strict=False)
        agent.to(device)
        return agent
