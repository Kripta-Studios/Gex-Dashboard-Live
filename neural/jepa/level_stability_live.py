from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


UP_LEVEL_COLS = [
    "price_vs_ib_high",
    "dist_fib_127_up",
    "dist_fib_161_up",
    "dist_fib_200_up",
    "dist_to_max_gamma",
    "dist_to_max_dgex",
]
DOWN_LEVEL_COLS = [
    "price_vs_ib_low",
    "dist_fib_127_dn",
    "dist_fib_161_dn",
    "dist_fib_200_dn",
    "dist_to_min_gamma",
    "dist_to_min_vanna",
    "dist_to_min_dgex",
]
GATE_COLS = [
    "near_ib_high",
    "near_ib_low",
    "above_ib",
    "below_ib",
    "bouncing_from_support",
    "rejecting_resistance",
    "trend_grind_up",
    "trend_flush_down",
    "is_touching_fib",
    "wall_at_fib",
    "is_touching_max_gamma",
    "is_touching_min_gamma",
]
REQUIRED_LEVEL_COLUMNS = sorted(set([*UP_LEVEL_COLS, *DOWN_LEVEL_COLS, *GATE_COLS, "time", "minutes_since_open"]))


@dataclass(frozen=True)
class LevelSignalConfig:
    gate: str
    min_target_bps: float
    max_target_bps: float
    stop_bps: float
    start_minute: int
    name: str = ""

    @property
    def config_name(self) -> str:
        if self.name:
            return self.name
        return (
            f"{self.gate}_t{self.min_target_bps:.0f}-{self.max_target_bps:.0f}"
            f"_s{self.stop_bps:.0f}_m{self.start_minute}"
        )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else default
    except Exception:
        return default


def _is_true(row: pd.Series, column: str) -> bool:
    return _safe_float(row.get(column, 0.0), 0.0) > 0.0


def _absolute_minute(row: pd.Series) -> int:
    minute = _safe_float(row.get("minute", float("nan")), float("nan"))
    if math.isfinite(minute) and minute >= 300:
        return int(round(minute))
    since_open = _safe_float(row.get("minutes_since_open", float("nan")), float("nan"))
    if math.isfinite(since_open):
        return 570 + int(round(since_open))
    text = str(row.get("time", ""))
    try:
        hour, minute_text = text[:5].split(":")
        return int(hour) * 60 + int(minute_text)
    except Exception:
        return 0


def _gate_matches(row: pd.Series, gate: str, side: str) -> bool:
    near_hi = _is_true(row, "near_ib_high")
    near_lo = _is_true(row, "near_ib_low")
    above = _is_true(row, "above_ib")
    below = _is_true(row, "below_ib")
    bounce = _is_true(row, "bouncing_from_support")
    reject = _is_true(row, "rejecting_resistance")
    trend_up = _is_true(row, "trend_grind_up")
    trend_down = _is_true(row, "trend_flush_down")
    touch_fib = _is_true(row, "is_touching_fib")
    wall_fib = _is_true(row, "wall_at_fib")
    touch_max_gamma = _is_true(row, "is_touching_max_gamma")
    touch_min_gamma = _is_true(row, "is_touching_min_gamma")

    if gate == "ib_reversal":
        return (near_lo or below or bounce) if side == "LONG" else (near_hi or above or reject)
    if gate == "breakout":
        return (near_hi or above or trend_up) if side == "LONG" else (near_lo or below or trend_down)
    if gate == "sr_combo":
        return (near_lo or bounce or touch_min_gamma) if side == "LONG" else (near_hi or reject or touch_max_gamma)
    if gate == "fib_wall":
        return touch_fib or wall_fib
    return True


def _target_bps(row: pd.Series, config: LevelSignalConfig, side: str) -> float:
    values: list[float] = []
    columns = UP_LEVEL_COLS if side == "LONG" else DOWN_LEVEL_COLS
    for column in columns:
        raw = _safe_float(row.get(column, float("nan")), float("nan"))
        if not math.isfinite(raw):
            continue
        target = -raw if side == "LONG" else raw
        if float(config.min_target_bps) < target <= float(config.max_target_bps):
            values.append(float(target))
    return float(min(values)) if values else float("nan")


def config_from_payload(payload: dict[str, Any]) -> LevelSignalConfig:
    return LevelSignalConfig(
        gate=str(payload["gate"]),
        min_target_bps=float(payload["min_target_bps"]),
        max_target_bps=float(payload["max_target_bps"]),
        stop_bps=float(payload["stop_bps"]),
        start_minute=int(payload["start_minute"]),
        name=str(payload.get("name", "")),
    )


def config_to_payload(config: Any) -> dict[str, Any]:
    return {
        "name": str(getattr(config, "name", "")),
        "gate": str(getattr(config, "gate")),
        "min_target_bps": float(getattr(config, "min_target_bps")),
        "max_target_bps": float(getattr(config, "max_target_bps")),
        "stop_bps": float(getattr(config, "stop_bps")),
        "start_minute": int(getattr(config, "start_minute")),
    }


class LevelStabilityLiveSignal:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.policy = str(payload.get("policy", "level_stability_ensemble"))
        self.deploy_month = str(payload.get("deploy_month", ""))
        self.cooldown_minutes = int(payload.get("cooldown_minutes", 30))
        self.required_columns = list(payload.get("required_columns", REQUIRED_LEVEL_COLUMNS))
        raw_tickers = payload.get("tickers", {})
        if not isinstance(raw_tickers, dict) or not raw_tickers:
            raise ValueError(f"No ticker policies found in {self.path}")

        self.tickers: dict[str, dict[str, Any]] = {}
        for ticker, item in raw_tickers.items():
            if not isinstance(item, dict):
                continue
            self.tickers[str(ticker).upper()] = {
                **item,
                "top_long_configs": [config_from_payload(cfg) for cfg in item.get("top_long_configs", [])],
                "top_short_configs": [config_from_payload(cfg) for cfg in item.get("top_short_configs", [])],
            }
        if not self.tickers:
            raise ValueError(f"No valid ticker policies found in {self.path}")

    def _config_signal(self, row: pd.Series, config: LevelSignalConfig, side: str, rank: int) -> dict[str, Any] | None:
        if _absolute_minute(row) < int(config.start_minute):
            return None
        if not _gate_matches(row, config.gate, side):
            return None
        target = _target_bps(row, config, side)
        if not math.isfinite(target):
            return None
        return {
            "side": side,
            "direction": 1 if side == "LONG" else -1,
            "target_bps": float(target),
            "stop_bps": float(config.stop_bps),
            "config": config.config_name,
            "ensemble_rank": int(rank),
        }

    def predict_row(self, ticker: str, row: pd.Series) -> dict[str, Any] | None:
        policy = self.tickers.get(str(ticker).upper())
        if policy is None:
            return None
        candidates: list[dict[str, Any]] = []
        for side, key in (("LONG", "top_long_configs"), ("SHORT", "top_short_configs")):
            for rank, config in enumerate(policy.get(key, [])):
                signal = self._config_signal(row, config, side, rank)
                if signal is not None:
                    candidates.append(signal)
        if not candidates:
            return None

        side_order = {"LONG": 0, "SHORT": 1}
        selected = sorted(
            candidates,
            key=lambda item: (float(item["target_bps"]), side_order.get(str(item["side"]), 9), int(item["ensemble_rank"])),
        )[0]
        confidence = float(np.clip(float(selected["target_bps"]) / 100.0, 0.05, 0.95))
        direction = int(selected["direction"])
        return {
            "jepa180_prob_up": confidence if direction > 0 else 1.0 - confidence,
            "jepa180_pred_bps": float(selected["target_bps"]) if direction > 0 else -float(selected["target_bps"]),
            "jepa180_long_threshold": 0.0,
            "jepa180_short_threshold": 0.0,
            "jepa180_confidence": confidence,
            "jepa180_edge": confidence,
            "jepa180_direction": direction,
            "jepa180_signal": True,
            "level_target_bps": float(selected["target_bps"]),
            "level_stop_bps": float(selected["stop_bps"]),
            "level_config": str(selected["config"]),
            "level_signal_policy": self.policy,
            "level_ensemble_config": str(policy.get("ensemble_config", "")),
        }

    def predict_frame(self, ticker: str, frame: pd.DataFrame) -> pd.Series | None:
        if frame.empty:
            return None
        prediction = self.predict_row(ticker, frame.iloc[-1])
        return pd.Series(prediction) if prediction is not None else None
