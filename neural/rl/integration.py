"""
Integrated Trading System — MLP Signals + RL Execution

Production integration: MLP generates signals, RL agent executes.
Call `on_new_minute()` every minute with fresh market data.
"""

import numpy as np
import pandas as pd
import torch
from typing import Optional

from neural.hybrid_model import FEATURE_COLUMNS
from neural.rl.config import RL_CONFIG, HARD_EXITS, STRIKE_BUCKETS, SNIPER_STATE_DIM, MLP_CONTEXT_DIM
from .config import (
    MARKET_FEATURE_DIM,
    POSITION_STATE_DIM, get_half_spread,
)
from .agent import PPOAgent


class IntegratedTradingSystem:
    """
    Production integration: MLP signals, RL executes.

    Flow per minute:
    1. Normalize features → MLP forward pass → check signal
    2. If new signal + no position → RL strike head → resolve strike → BUY
    3. If position open → RL exit head → EXIT or HOLD (hard exits override)
    """

    def __init__(self, mlp_model, mlp_normalizer, rl_agent: PPOAgent,
                 feature_columns: list, device: torch.device = None):
        """
        Args:
            mlp_model:       Trained model (HybridTradingModel or GBTEnsemble)
            mlp_normalizer:  Trained FeatureNormalizer (frozen)
            rl_agent:        Trained PPOAgent
            feature_columns: FEATURE_COLUMNS list from hybrid_model.py
            device:          torch device
        """
        self.mlp = mlp_model
        self.normalizer = mlp_normalizer
        self.rl = rl_agent
        self.feature_columns = feature_columns
        self.device = device or torch.device(
            "cuda" if torch.cuda.is_available() else "cpu")

        # Freeze model — GBT models don't have PyTorch parameters
        self.mlp.eval()
        if hasattr(self.mlp, 'parameters'):
            params = list(self.mlp.parameters())
            if params:  # Only freeze if there are actual parameters
                for param in params:
                    param.requires_grad = False
                self.mlp.to(self.device)
        self.rl.eval()
        self.rl.to(self.device)

        # Position tracking
        self.open_position: Optional[dict] = None
        self._mae = 0.0
        self._prev_pnl_pct = 0.0
        self._prev_pnl_pct = 0.0
        self._entry_mlp_context = np.zeros(MLP_CONTEXT_DIM, dtype=np.float32)

    def on_new_minute(self, market_features: np.ndarray, options_data: dict,
                      spot: float, timestamp: pd.Timestamp) -> dict:
        """
        Called every minute with fresh market data.

        Args:
            market_features: raw feature vector (len=163), NOT yet normalized
            options_data:    dict of available strikes:
                             {"calls": {strike: {price, delta, iv, theta, gamma}},
                              "puts":  {strike: {price, delta, iv, theta, gamma}}}
            spot:            current SPX spot price
            timestamp:       current market timestamp
            force_rl:        if True, skip MLP HOLD gate and let RL decide
                             (used when GBM HOLD is saturated)

        Returns: dict with keys:
            'action':     'BUY_CALL' | 'BUY_PUT' | 'EXIT' | 'HOLD' | 'NO_SIGNAL'
            'strike':     float or None
            'delta':      float or None
            'confidence': float
            'details':    dict with additional info
        """
        # 1. Normalize market features
        features_norm = self.normalizer.transform(
            market_features.reshape(1, -1)
        )[0]

        # 2. MLP/GBT forward pass
        is_gbt = hasattr(self.mlp, 'predict_proba') and not isinstance(self.mlp, torch.nn.Module)
        
        if is_gbt:
            # GBT Inference
            probs = self.mlp.predict_proba(features_norm.reshape(1, -1))[0]
            time_to_target = 0.5 # GBM doesn't predict time
            log_sigma = 0.5
        else:
            # PyTorch Inference
            with torch.no_grad():
                x = torch.FloatTensor(features_norm).unsqueeze(0).to(self.device)
                output = self.mlp(x)

                if isinstance(output, tuple):
                    logits, time_pred = output[:2]
                elif isinstance(output, dict):
                    logits = output.get("logits", output.get("class_logits"))
                    time_pred = output.get("time_to_target", None)
                else:
                    logits = output
                    time_pred = None

                probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]

            if time_pred is not None and getattr(time_pred, 'numel', lambda: len(time_pred))() >= 2:
                try:
                    tt = time_pred[0, 0].item() if hasattr(time_pred[0, 0], 'item') else float(time_pred[0, 0])
                    ls = time_pred[0, 1].item() if hasattr(time_pred[0, 1], 'item') else float(time_pred[0, 1])
                    time_to_target = float(tt / 180.0)
                    log_sigma = float(ls)
                except:
                    time_to_target = 0.5
                    log_sigma = 0.5
            else:
                time_to_target = 0.5
                log_sigma = 0.5

        prediction = int(np.argmax(probs))
        confidence = float(np.max(probs))

        # Direction mapping: 0=SHORT, 1=HOLD, 2=LONG
        direction_map = {0: "SHORT", 1: "HOLD", 2: "LONG"}
        direction = direction_map.get(prediction, "HOLD")

        # 3. No signal if HOLD or low confidence
        if direction == "HOLD" or confidence < RL_CONFIG["min_confidence"]:
            if self.open_position is not None:
                return self._handle_exit(features_norm, options_data, spot, timestamp)
            return self._no_signal(confidence)

        # 4. If no open position → consider entry
        if self.open_position is None:
            return self._handle_entry(
                features_norm, options_data, spot, timestamp,
                direction, confidence, time_to_target, log_sigma)

        # 5. If position IS open → handle exit decision
        return self._handle_exit(features_norm, options_data, spot, timestamp)

    def _no_signal(self, confidence: float) -> dict:
        return {
            "action": "NO_SIGNAL",
            "strike": None, "delta": None,
            "confidence": confidence,
            "details": {},
        }

    def _handle_entry(self, features_norm: np.ndarray, options_data: dict,
                      spot: float, timestamp: pd.Timestamp,
                      direction: str, confidence: float,
                      time_to_target: float, log_sigma: float) -> dict:
        """Use RL Strike Head to choose a delta bucket and resolve strike."""
        # Build state vector
        state = self._build_state(features_norm, position_active=False,
                                  confidence=confidence,
                                  time_to_target=time_to_target,
                                  log_sigma=log_sigma)

        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            action, _, _ = self.rl.get_action(
                state_tensor, action_type="strike", deterministic=True)

        # action is now a plain int (strike bucket index)
        strike_action = action
        
        bucket = STRIKE_BUCKETS.get(strike_action, STRIKE_BUCKETS[4])
        delta_target = bucket["delta_target"]
        right = "CALL" if direction == "LONG" else "PUT"

        # Resolve actual strike from options_data
        strike_info = self._resolve_strike(options_data, delta_target, right)

        if strike_info is None:
            return {
                "action": "NO_SIGNAL",
                "strike": None, "delta": None,
                "confidence": confidence,
                "details": {"reason": "no_strike_available"},
            }

        # Apply spread cost
        half_spread = get_half_spread(abs(strike_info["entry_delta"]))
        effective_entry = strike_info["entry_price"] * (1.0 + half_spread)

        # Open position
        self.open_position = {
            "strike": strike_info["strike"],
            "right": right,
            "direction": direction,
            "entry_price": effective_entry,
            "raw_entry_price": strike_info["entry_price"],
            "entry_iv": strike_info["entry_iv"],
            "entry_delta": strike_info["entry_delta"],
            "entry_theta": strike_info["entry_theta"],
            "entry_gamma": strike_info["entry_gamma"],
            "entry_time": timestamp,
            "strike_action": strike_action,
        }
        self._mae = 0.0
        self._prev_pnl_pct = 0.0
        self._entry_mlp_context = np.array(
            [confidence, time_to_target, 0.0, log_sigma], dtype=np.float32)

        action_str = f"BUY_{right}"
        return {
            "action": action_str,
            "strike": strike_info["strike"],
            "delta": strike_info["entry_delta"],
            "confidence": confidence,
            "details": {
                "bucket": bucket["label"],
                "delta_target": delta_target,
                "entry_price": effective_entry,
                "spread_cost": half_spread,
            },
        }

    def _handle_exit(self, features_norm: np.ndarray, options_data: dict,
                     spot: float, timestamp: pd.Timestamp) -> dict:
        """Use RL Exit Head to decide HOLD or EXIT. Hard exits override."""
        pos = self.open_position
        right_key = "calls" if pos["right"] == "CALL" else "puts"

        # Get current option price + live greeks
        options = options_data.get(right_key, {})
        current_price = self._lookup_price(options, pos["strike"])
        if current_price is None:
            current_price = pos["raw_entry_price"]

        # Fetch live delta, theta and IV for the position's strike
        live_delta, live_theta, live_iv = self._lookup_greeks(options, pos["strike"])

        entry_price = pos["entry_price"]
        pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0.0
        pnl_pct = float(np.clip(pnl_pct, -1.0, 5.0))
        self._mae = min(self._mae, pnl_pct)

        hold_minutes = (timestamp - pos["entry_time"]).total_seconds() / 60.0
        hold_time_norm = hold_minutes / HARD_EXITS["max_hold_minutes"]

        minutes_to_close = max(0, RL_CONFIG["session_length_minutes"]
                               - ((timestamp.hour * 60 + timestamp.minute) - 570))

        # ── Hard exit checks ──
        if pnl_pct <= HARD_EXITS["max_loss_pct"]:
            return self._close_position("HARD_STOP", pnl_pct)
        if pnl_pct >= HARD_EXITS["max_profit_pct"]:
            return self._close_position("HARD_TAKE_PROFIT", pnl_pct)
        if minutes_to_close <= HARD_EXITS["minutes_to_close"]:
            return self._close_position("HARD_TIME_CLOSE", pnl_pct)
        if hold_minutes >= HARD_EXITS["max_hold_minutes"]:
            return self._close_position("HARD_MAX_HOLD", pnl_pct)

        # ── RL Exit Head ──
        state = self._build_state(
            features_norm, position_active=True,
            pnl_pct=pnl_pct, hold_time_norm=hold_time_norm,
            current_delta=abs(live_delta),
            current_theta=live_theta, current_iv=live_iv,
            mae=self._mae)

        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            action, _, _ = self.rl.get_action(
                state_tensor, action_type="exit", deterministic=True)
        action_val = action.item() if hasattr(action, 'item') else int(action)
        if action_val == 1:  # EXIT
            # Enforce min_hold curriculum constraint, just like in training/backtest
            phase3_config = RL_CONFIG.get("hold_min_minutes_curriculum", {}).get(3, {})
            min_hold = phase3_config.get("min_hold", 30)
            
            emergency_stop = RL_CONFIG.get("emergency_stop_pct", -0.30)
            is_emergency = pnl_pct <= emergency_stop
            
            if hold_minutes >= min_hold or is_emergency:
                return self._close_position("AGENT_EXIT", pnl_pct)

        # HOLD
        self._prev_pnl_pct = pnl_pct
        return {
            "action": "HOLD",
            "strike": pos["strike"],
            "delta": pos["entry_delta"],
            "confidence": self._entry_mlp_context[0],
            "details": {
                "pnl_pct": pnl_pct,
                "hold_minutes": hold_minutes,
                "mae": self._mae,
            },
        }

    def _close_position(self, reason: str, pnl_pct: float) -> dict:
        """Close position and reset state."""
        pos = self.open_position
        result = {
            "action": "EXIT",
            "strike": pos["strike"],
            "delta": pos["entry_delta"],
            "confidence": self._entry_mlp_context[0],
            "details": {
                "exit_reason": reason,
                "final_pnl_pct": pnl_pct,
                "direction": pos["direction"],
                "strike_bucket": STRIKE_BUCKETS.get(
                    pos["strike_action"], {}).get("label", "unknown"),
            },
        }
        self.open_position = None
        self._mae = 0.0
        self._prev_pnl_pct = 0.0
        return result

    def _build_state(self, features_norm: np.ndarray,
                     position_active: bool = False,
                     confidence: float = 0.60,
                     time_to_target: float = 0.5,
                     log_sigma: float = 0.5,
                     pnl_pct: float = 0.0,
                     hold_time_norm: float = 0.0,
                     current_delta: float = 0.0,
                     current_theta: float = -0.05,
                     current_iv: float = 0.15,
                     mae: float = 0.0) -> np.ndarray:
        """Build the full state vector (173 or 175-dim with sniper)."""
        # Market features (already normalized)
        market = np.zeros(MARKET_FEATURE_DIM, dtype=np.float32)
        n = min(len(features_norm), MARKET_FEATURE_DIM)
        market[:n] = features_norm[:n]

        # Position state — live greeks from options chain
        pos_state = np.zeros(POSITION_STATE_DIM, dtype=np.float32)
        if position_active:
            iv_ratio = current_iv / 0.15 if current_iv > 0 else 1.0
            pos_state[0] = np.clip(pnl_pct, -1.0, 5.0)
            pos_state[1] = np.clip(hold_time_norm, 0.0, 1.0)
            pos_state[2] = current_delta
            pos_state[3] = current_theta      # live theta from options chain
            pos_state[4] = np.clip(iv_ratio, 0.5, 3.0)  # live IV ratio
            pos_state[5] = np.clip(mae, -1.0, 0.0)

        # MLP context
        if position_active:
            mlp_ctx = self._entry_mlp_context
        else:
            mlp_ctx = np.array([confidence, time_to_target, 0.0, log_sigma], dtype=np.float32)

        base_state = np.concatenate([market, pos_state, mlp_ctx])

        # Append sniper state if sniper mode is active (173 → 175)
        if RL_CONFIG.get("use_sniper_mode", False):
            sniper_state = np.zeros(SNIPER_STATE_DIM, dtype=np.float32)
            return np.concatenate([base_state, sniper_state])

        return base_state

    def _resolve_strike(self, options_data: dict, delta_target: float,
                        right: str) -> dict:
        """Resolve actual strike from available options."""
        key = "calls" if right == "CALL" else "puts"
        options = options_data.get(key, {})
        if not options:
            return None

        best_strike = None
        best_diff = float("inf")
        for strike, data in options.items():
            delta = abs(data.get("delta", 0))
            diff = abs(delta - delta_target)
            if diff < best_diff:
                best_diff = diff
                best_strike = strike
                best_data = data

        if best_strike is None:
            return None

        return {
            "strike": float(best_strike),
            "entry_price": float(best_data.get("price", 0)),
            "entry_iv": float(best_data.get("iv", 0.15)),
            "entry_delta": float(best_data.get("delta", delta_target)),
            "entry_theta": float(best_data.get("theta", 0)),
            "entry_gamma": float(best_data.get("gamma", 0)),
        }

    def _lookup_greeks(self, options: dict, strike: float) -> tuple:
        """Look up live theta and IV for a specific strike, with nearest-strike fallback.

        Returns:
            (delta, theta, iv) — floats with sensible defaults if not found.
        """
        default_delta = 0.5
        default_theta = -0.05
        default_iv = 0.15

        data = None
        if strike in options:
            data = options[strike]
        elif options:
            nearest = min(options.keys(), key=lambda s: abs(float(s) - strike))
            data = options[nearest]

        if data is not None:
            delta = float(data.get("delta", default_delta))
            theta = float(data.get("theta", default_theta))
            iv = float(data.get("iv", default_iv))
            # Sanity: theta should be negative for long options
            if theta > 0:
                theta = -abs(theta)
            # IV sanity: should be between 0.01 and 5.0
            if iv <= 0 or iv > 5.0:
                iv = default_iv
            return delta, theta, iv

        return default_delta, default_theta, default_iv

    def _lookup_price(self, options: dict, strike: float) -> float:
        """Look up price for a specific strike, with nearest-strike fallback."""
        if strike in options:
            return float(options[strike].get("price", 0))

        if not options:
            return None

        nearest = min(options.keys(), key=lambda s: abs(float(s) - strike))
        return float(options[nearest].get("price", 0))
