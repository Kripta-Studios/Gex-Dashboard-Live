"""
Integrated Trading System — MLP Signals + RL Execution

Production integration: MLP generates signals, RL agent executes.
Call `on_new_minute()` every minute with fresh market data.
"""

import numpy as np
import pandas as pd
import torch
import os
import pickle
from typing import Optional, List, Dict
from collections import deque

from neural.hybrid_model import FEATURE_COLUMNS
from neural.rl.config import RL_CONFIG, HARD_EXITS, STRIKE_BUCKETS, SNIPER_STATE_DIM, MLP_CONTEXT_DIM
from .utils import get_delta_bucket, get_iv_bucket, get_pnl_bucket
from .config import (
    MARKET_FEATURE_DIM, DYNAMIC_MARKET_DIM,
    POSITION_STATE_DIM, get_half_spread,
)
from .agent import PPOAgent
from neural.signal_policy import is_actionable_signal, should_exit_on_reversal


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

        # Freeze models
        self.mlp.eval()
        if hasattr(self.mlp, 'parameters'):
            params = list(self.mlp.parameters())
            if params:
                for param in params:
                    param.requires_grad = False
                self.mlp.to(self.device)
        self.rl.eval()
        self.rl.to(self.device)

        # Position tracking
        self.open_position: Optional[dict] = None
        self._mae = 0.0
        self._prev_pnl_pct = 0.0
        self._max_unrealized_pnl = 0.0
        self._trailing_drawdown = 0.0
        self._entry_mlp_context = np.zeros(MLP_CONTEXT_DIM, dtype=np.float32)
        
        # Curriculum/Constraints
        self.min_strike_bucket = 0
        
        # Internal history for dynamic features
        self._spot_history = deque(maxlen=25)
        self._option_price_history = deque(maxlen=10)
        
        # Spot references
        self._signal_spot = 0.0          
        self._entry_atm_iv = 0.15        
        self._position_entry_spot = 0.0  
        
        self._signal_direction = "HOLD"
        self._signal_confidence = 0.0
        
        self._dynamic_market_state = np.zeros(8, dtype=np.float32)
        
        # Load recovery stats
        self._recovery_lookup = {}
        # Correct path from neural/rl/ to project root: ../../rl_data/recovery_stats.pkl
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        stats_path = os.path.abspath(os.path.join(current_file_dir, "../../rl_data/recovery_stats.pkl"))
        
        if os.path.exists(stats_path):
            try:
                with open(stats_path, "rb") as f:
                    self._recovery_lookup = pickle.load(f)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"[ITS] Error loading recovery_stats: {e}")

    def on_new_minute(self, market_features: np.ndarray, options_data: dict,
                      spot: float, timestamp: pd.Timestamp,
                      has_real_position: bool = None) -> dict:
        """Called every minute with fresh market data."""
        # 0. Sync position state
        if has_real_position is not None and not has_real_position and self.open_position is not None:
            self._reset_position_state()

        # 1. Update histories
        self._spot_history.append(spot)
        self._update_dynamic_features(options_data, spot, timestamp)

        # 2. MLP Inference
        market_features = np.asarray(market_features, dtype=np.float32)
        is_gbt = hasattr(self.mlp, 'predict_proba') and not isinstance(self.mlp, torch.nn.Module)
        
        if is_gbt:
            probs = self.mlp.predict_proba(market_features.reshape(1, -1))[0]
            time_to_target = 0.5
            log_sigma = 0.5
        else:
            features_norm = self.normalizer.transform(market_features.reshape(1, -1))[0]
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
                
                if time_pred is not None:
                    time_to_target = float(time_pred[0, 0].cpu().numpy()) / 180.0
                    log_sigma = float(time_pred[0, 1].cpu().numpy())
                else:
                    time_to_target, log_sigma = 0.5, 0.5

        prediction = int(np.argmax(probs))
        confidence = float(np.max(probs))
        direction = {0: "SHORT", 1: "HOLD", 2: "LONG"}.get(prediction, "HOLD")
        
        # 3. Handle signal tracking
        if self.open_position is None:
            if is_actionable_signal(direction, confidence, base_confidence=RL_CONFIG["min_confidence"]):
                if self._signal_direction == "HOLD":
                    self._signal_spot = spot
                    self._entry_atm_iv = self._get_atm_iv(options_data, spot)
                self._signal_direction = direction
                self._signal_confidence = confidence
            else:
                self._signal_direction = "HOLD"
                self._signal_confidence = 0.0
                self._signal_spot = 0.0

        # 4. Routing
        if not is_actionable_signal(direction, confidence, base_confidence=RL_CONFIG["min_confidence"]):
            if self.open_position is not None:
                return self._handle_exit(market_features, options_data, spot, timestamp, direction, confidence)
            return self._no_signal(confidence)

        if self.open_position is None:
            return self._handle_entry(market_features, options_data, spot, timestamp, 
                                     direction, confidence, time_to_target, log_sigma)

        return self._handle_exit(market_features, options_data, spot, timestamp, direction, confidence)

    def _update_dynamic_features(self, options_data: dict, spot: float, timestamp: pd.Timestamp):
        """Compute the 8 dynamic market features (mirrors environment.py)."""
        dynamic = np.zeros(8, dtype=np.float32)
        if spot <= 0:
            self._dynamic_market_state = dynamic
            return

        # [0] Spot change from signal detection
        if self._signal_spot > 0:
            spot_change = (spot - self._signal_spot) / self._signal_spot
            dynamic[0] = np.clip(spot_change * 100, -2.0, 2.0)

        # [1] Spot velocity last 5m
        if len(self._spot_history) >= 6:
            v = (spot - self._spot_history[-6]) / (self._signal_spot if self._signal_spot > 0 else spot)
            dynamic[1] = np.clip(v * 100, -1.0, 1.0)

        # [2] ATM IV change
        all_opts = {**options_data.get("calls", {}), **options_data.get("puts", {})}
        if all_opts:
            atm_s = min(all_opts.keys(), key=lambda s: abs(float(s) - spot))
            curr_iv = float(all_opts[atm_s].get("iv", self._entry_atm_iv))
            dynamic[2] = np.clip((curr_iv - self._entry_atm_iv) / max(self._entry_atm_iv, 0.01), -1, 1)
            # [3] ATM Gamma
            dynamic[3] = np.clip(float(all_opts[atm_s].get("gamma", 0)) * spot * 0.01, -2, 2)

        # [4] Spot vs entry price
        if self.open_position and self._position_entry_spot > 0:
            sv_entry = (spot - self._position_entry_spot) / self._position_entry_spot
            if self.open_position["direction"] == "SHORT": sv_entry = -sv_entry
            dynamic[4] = np.clip(sv_entry * 100, -3.0, 3.0)

        # [5] Time to close
        try:
            close_t = timestamp.replace(hour=16, minute=0, second=0, microsecond=0)
            mins_left = max(0, (close_t - timestamp).total_seconds() / 60.0)
            dynamic[5] = np.clip(mins_left / 390.0, 0.0, 1.0)
        except: dynamic[5] = 0.5

        # [6] Option momentum
        if self.open_position:
            opts = options_data.get("calls" if self.open_position["right"] == "CALL" else "puts", {})
            price = float(opts.get(self.open_position["strike"], {}).get("price", 0.01))
            self._option_price_history.append(price)
            if len(self._option_price_history) >= 4:
                p3 = self._option_price_history[-4]
                dynamic[6] = np.clip((price - p3) / p3, -1, 1) if p3 > 0 else 0

        # [7] Trend
        if len(self._spot_history) >= 3:
            hist = list(self._spot_history)[-20:]
            diffs = np.diff(hist)
            up, dn = np.sum(diffs > 0), np.sum(diffs < 0)
            dynamic[7] = (up - dn) / (up + dn) if (up + dn) > 0 else 0

        self._dynamic_market_state = dynamic

    def _handle_entry(self, market_features: np.ndarray, options_data: dict,
                      spot: float, timestamp: pd.Timestamp,
                      direction: str, confidence: float,
                      time_to_target: float, log_sigma: float) -> dict:
        """Choose strike and open position."""
        self._entry_market_features = np.asarray(market_features, dtype=np.float32).copy()
        self._entry_mlp_context = np.array([confidence, time_to_target, 0.0, log_sigma], dtype=np.float32)

        state = self._build_state(market_features, False, confidence, time_to_target, log_sigma)
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            action, _, _ = self.rl.get_action(state_tensor, "strike", True)
        
        strike_action = int(action)
        if hasattr(self, 'min_strike_bucket'):
            strike_action = max(self.min_strike_bucket, strike_action)
            
        bucket = STRIKE_BUCKETS.get(strike_action, STRIKE_BUCKETS[4])
        right = "CALL" if direction == "LONG" else "PUT"
        strike_info = self._resolve_strike(options_data, bucket["delta_target"], right)

        if strike_info is None: return self._no_signal(confidence)

        half_spread = get_half_spread(abs(strike_info["entry_delta"]))
        self.open_position = {
            **strike_info, "right": right, "direction": direction,
            "entry_price": strike_info["entry_price"] * (1.0 + half_spread),
            "raw_entry_price": strike_info["entry_price"],
            "entry_time": timestamp, "strike_action": strike_action
        }
        self._mae, self._prev_pnl_pct, self._max_unrealized_pnl, self._trailing_drawdown = 0.0, 0.0, 0.0, 0.0
        self._position_entry_spot = spot
        self._option_price_history.clear()
        self._option_price_history.append(self.open_position["entry_price"])

        return {
            "action": f"BUY_{right}", "strike": strike_info["strike"],
            "delta": strike_info["entry_delta"], "confidence": confidence,
            "details": {"strike_action": strike_action, "delta_target": bucket["delta_target"]}
        }

    def _handle_exit(self, market_features: np.ndarray, options_data: dict,
                     spot: float, timestamp: pd.Timestamp,
                     curr_dir: str, curr_conf: float) -> dict:
        """Check for exits."""
        pos = self.open_position
        opts = options_data.get("calls" if pos["right"] == "CALL" else "puts", {})
        price = self._lookup_price(opts, pos["strike"]) or pos["raw_entry_price"]
        l_delta, l_theta, l_iv = self._lookup_greeks(opts, pos["strike"])

        pnl = (price - pos["entry_price"]) / pos["entry_price"]
        pnl = float(np.clip(pnl, -1.0, 5.0))
        self._mae = min(self._mae, pnl)
        self._max_unrealized_pnl = max(self._max_unrealized_pnl, pnl)
        self._trailing_drawdown = self._max_unrealized_pnl - pnl
        hold_m = (timestamp - pos["entry_time"]).total_seconds() / 60.0
        
        # Hard Exits
        if pnl <= HARD_EXITS["max_loss_pct"]: return self._close_position("HARD_STOP", pnl)
        if pnl >= HARD_EXITS["max_profit_pct"]: return self._close_position("HARD_TAKE_PROFIT", pnl)
        
        # Signal Reversal
        if hold_m >= HARD_EXITS.get("min_hold_minutes", 0):
            now_et = timestamp # Assumed ET
            m_open = max(0, (now_et.hour * 60 + now_et.minute) - 570)
            if should_exit_on_reversal(pos["direction"], curr_dir, curr_conf, m_open):
                return self._close_position("SIGNAL_REVERSAL", pnl)

        # RL Exit
        state = self._build_state(market_features, True, pnl_pct=pnl, 
                                 hold_time_norm=hold_m/HARD_EXITS["max_hold_minutes"],
                                 current_delta=abs(l_delta), current_theta=l_theta, 
                                 current_iv=l_iv, entry_iv=pos["entry_iv"], 
                                 entry_price=pos["entry_price"], mae=self._mae, 
                                 trailing_drawdown=self._trailing_drawdown)
        
        with torch.no_grad():
            action, _, _ = self.rl.get_action(torch.FloatTensor(state).unsqueeze(0).to(self.device), "exit", True)
        
        if int(action) == 1 and hold_m >= HARD_EXITS.get("min_hold_minutes", 0):
            return self._close_position("AGENT_EXIT", pnl)

        self._prev_pnl_pct = pnl
        return {"action": "HOLD", "strike": pos["strike"], "delta": pos["entry_delta"], 
                "confidence": self._entry_mlp_context[0], "details": {"pnl_pct": pnl, "hold_m": hold_m}}

    def _close_position(self, reason: str, pnl: float) -> dict:
        pos = self.open_position
        res = {"action": "EXIT", "strike": pos["strike"], "delta": pos["entry_delta"],
               "confidence": self._entry_mlp_context[0], 
               "details": {"exit_reason": reason, "final_pnl": pnl}}
        self._reset_position_state()
        return res

    def _reset_position_state(self):
        self.open_position = None
        self._mae, self._prev_pnl_pct, self._max_unrealized_pnl, self._trailing_drawdown = 0.0, 0.0, 0.0, 0.0
        self._signal_spot, self._position_entry_spot, self._signal_direction = 0.0, 0.0, "HOLD"
        self._signal_confidence, self._entry_market_features = 0.0, None
        self._entry_atm_iv = 0.15
        self._spot_history.clear()
        self._option_price_history.clear()
        self._dynamic_market_state = np.zeros(8, dtype=np.float32)

    def _build_state(self, market_features: np.ndarray, position_active: bool,
                      confidence: float = 0.6, time_to_target: float = 0.5,
                      log_sigma: float = 0.5, pnl_pct: float = 0.0,
                      hold_time_norm: float = 0.0, current_delta: float = 0.5,
                      current_theta: float = -0.05, current_iv: float = 0.15,
                      entry_iv: float = 0.15, entry_price: float = 1.0,
                      mae: float = 0.0, trailing_drawdown: float = 0.0) -> np.ndarray:
        source = self._entry_market_features if position_active and self._entry_market_features is not None else market_features
        market = np.zeros(MARKET_FEATURE_DIM, dtype=np.float32)
        n = min(len(source), MARKET_FEATURE_DIM)
        market[:n] = source[:n]
        
        pos_state = np.zeros(POSITION_STATE_DIM, dtype=np.float32)
        if position_active:
            pos_state[0] = np.clip(pnl_pct, -1, 5)
            pos_state[1] = np.clip(hold_time_norm, 0, 1)
            pos_state[2] = abs(current_delta)
            db, ib, pb = get_delta_bucket(pos_state[2]), get_iv_bucket(current_iv), get_pnl_bucket(pnl_pct)
            pos_state[3] = float(self._recovery_lookup.get((db, ib, pb), 0.3))
            pos_state[4] = np.clip(current_iv / 0.15 if current_iv > 0 else 1.0, 0.5, 3.0)
            pos_state[5] = np.clip(mae, -1, 0)
            if POSITION_STATE_DIM > 6: pos_state[6] = np.clip(trailing_drawdown, 0, 2)

        mlp_ctx = self._entry_mlp_context if position_active else np.array([confidence, time_to_target, 0.0, log_sigma], dtype=np.float32)
        return np.concatenate([market, self._dynamic_market_state, pos_state, mlp_ctx]).astype(np.float32)

    def _get_atm_iv(self, options_data: dict, spot: float) -> float:
        all_opts = {**options_data.get("calls", {}), **options_data.get("puts", {})}
        if not all_opts: return 0.15
        atm_s = min(all_opts.keys(), key=lambda s: abs(float(s) - spot))
        return float(all_opts[atm_s].get("iv", 0.15))

    def _resolve_strike(self, options_data: dict, delta_target: float, right: str) -> Optional[dict]:
        opts = options_data.get("calls" if right == "CALL" else "puts", {})
        if not opts: return None
        best_s = min(opts.keys(), key=lambda s: abs(abs(opts[s].get("delta", 0)) - delta_target))
        d = opts[best_s]
        return {"strike": float(best_s), "entry_price": float(d.get("price", 0)), 
                "entry_iv": float(d.get("iv", 0.15)), "entry_delta": float(d.get("delta", 0)),
                "entry_theta": float(d.get("theta", 0)), "entry_gamma": float(d.get("gamma", 0))}

    def _lookup_price(self, options: dict, strike: float) -> Optional[float]:
        if not options: return None
        s = strike if strike in options else min(options.keys(), key=lambda x: abs(float(x) - strike))
        return float(options[s].get("price", 0))

    def _lookup_greeks(self, options: dict, strike: float) -> tuple:
        if not options: return 0.5, -0.05, 0.15
        s = strike if strike in options else min(options.keys(), key=lambda x: abs(float(x) - strike))
        d = options[s]
        return float(d.get("delta", 0.5)), -abs(float(d.get("theta", -0.05))), float(d.get("iv", 0.15))

    def restore_state(self, pos_data: dict, conf: float, tt: float, ls: float):
        self.open_position = {
            "ticker": pos_data.get("ticker"), "strike": pos_data.get("strike"),
            "right": pos_data.get("right"), "direction": pos_data.get("direction"),
            "entry_price": pos_data.get("entry_premium"), "raw_entry_price": pos_data.get("entry_premium"),
            "entry_iv": pos_data.get("entry_atm_iv", 0.15), "entry_delta": pos_data.get("delta", 0.5),
            "entry_time": pd.to_datetime(pos_data.get("entry_time")), "strike_action": pos_data.get("bucket_index", 4)
        }
        self._entry_mlp_context = np.array([conf, tt, 0.0, ls], dtype=np.float32)
        self._signal_direction, self._signal_confidence = pos_data.get("direction", "HOLD"), conf
        self._signal_spot = pos_data.get("signal_spot", 0.0)
        self._position_entry_spot = pos_data.get("position_entry_spot", self._signal_spot)
        self._entry_atm_iv = pos_data.get("entry_atm_iv", 0.15)
        self._entry_market_features = np.asarray(pos_data.get("entry_market_features"), dtype=np.float32) if pos_data.get("entry_market_features") else None
        self._mae, self._max_unrealized_pnl, self._prev_pnl_pct = pos_data.get("mae", 0.0), pos_data.get("max_unrealized_pnl", 0.0), pos_data.get("prev_pnl_pct", 0.0)

    def _no_signal(self, conf: float) -> dict:
        return {"action": "NO_SIGNAL", "strike": None, "delta": None, "confidence": conf, "details": {"reason": "GBM_HOLD"}}
