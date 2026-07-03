"""
Trading Bot - level-stability signal + structural 0DTE option profiles.

Data source:
    rt_data/{YYYYMMDD}/ produced by services/realtime_feed.py.

Live contract:
    - Direction signal: production level-stability ensemble rules fit only on
      months prior to the deployment month. The legacy JEPA 180m model is an
      explicit fallback only.
    - Entry cadence: 5-minute feature rows, matching the training/backtest sample cadence.
    - Entry window: feature rows through 14:30 ET, with EOD cleanup at the close.
    - Strike selection: production structural option profiles over 0.10..0.70
      delta candidates. OptionValue/fixed-delta are diagnostics/fallback only.
    - Exit: legacy structural path uses hard stop -60%, trail from +50% with
      25% giveback, emergency TP +1000%, max hold 180m, EOD cleanup.
      Event-option scorer positions use their validated option exit contract
      from the production policy, including any minimum hold, max hold, stop,
      and take-profit settings.
    - Cooldown: per-policy in event-option scorer mode; 180m in the legacy
      level-stability/structural path.
    - Optional event-option risk guard: policy-configured daily loss-streak
      pauses use only prior completed-day realized PnL per ticker.

This script is an alert/tracker bot. It does not submit broker orders. When
`--paper-order-intents` is passed, it also writes broker-shaped paper order
intents to disk for downstream validation.
"""

from __future__ import annotations

import argparse
import csv
import __main__ as main_module
import json
import logging
import math
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "neural"))

from neural.jepa.event_option_component_live import EventOptionComponentRegistry
from neural.jepa.jepa_180m_signal import Jepa180mSignalModel
from neural.jepa.level_stability_live import LevelStabilityLiveSignal

try:
    from neural.jepa.event_option_live_scorer import score_event_option_live_candidates

    EVENT_OPTION_SCORER_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - live dependency guard
    score_event_option_live_candidates = None
    EVENT_OPTION_SCORER_IMPORT_ERROR = exc

try:
    import torch
    from neural.jepa.train_option_value_jepa import (
        FeatureScaler,
        OptionValueConfig,
        OptionValueJEPA,
        add_selector_score_bases,
    )

    OPTION_VALUE_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - live dependency guard
    torch = None
    FeatureScaler = None
    OptionValueConfig = None
    OptionValueJEPA = None
    add_selector_score_bases = None
    OPTION_VALUE_IMPORT_ERROR = exc

load_dotenv()

ET = ZoneInfo("America/New_York")

TICKERS = ["SPX", "QQQ", "SPY"]
OPTIONS_SYMBOLS = {"SPX": "SPXW", "QQQ": "QQQ", "SPY": "SPY"}
RIGHT_FOR_DIRECTION = {"LONG": "CALL", "SHORT": "PUT"}

DEFAULT_SIGNAL_MODEL_DIR = PROJECT_ROOT / "neural" / "models" / "jepa" / "jepa_production_final_180m"
DEFAULT_LEVEL_SIGNAL_PATH = (
    PROJECT_ROOT / "neural" / "models" / "jepa" / "jepa_production_level_stability" / "level_stability_signal.json"
)
DEFAULT_OPTION_VALUE_MODEL_DIR = PROJECT_ROOT / "neural" / "models" / "jepa" / "jepa_production_final_option_value"
DEFAULT_STRUCTURAL_PROFILE_PATH = (
    PROJECT_ROOT / "neural" / "models" / "jepa" / "jepa_production_structural_options" / "structural_option_profiles.json"
)
DEFAULT_EVENT_OPTION_POLICY_PATH = (
    PROJECT_ROOT / "neural" / "models" / "jepa" / "jepa_production_event_options" / "event_option_policy.json"
)
DEFAULT_EVENT_OPTION_COMPONENT_REGISTRY_PATH = (
    PROJECT_ROOT / "neural" / "models" / "jepa" / "jepa_production_event_options" / "component_registry.json"
)
DEFAULT_RT_DATA_DIR = PROJECT_ROOT / "rt_data"
DEFAULT_TRADES_DIR = PROJECT_ROOT / "trades_jepa"

MODEL_MODE = "base_jepa"
DELTA_TARGET = 0.70
RISK_CAPITAL = 5000.0
CONTRACT_MULTIPLIER = 100.0
HARD_STOP_PCT = -0.60
TAKE_PROFIT_PCT = 10.00
TRAIL_ACTIVATION_PCT = 0.50
TRAIL_DRAWDOWN_PCT = 0.25
MAX_HOLD_MINUTES = 180
EVENT_OPTION_TAKE_PROFIT_PCT = 0.75
EVENT_OPTION_STOP_LOSS_PCT = -0.50
EVENT_OPTION_MAX_HOLD_MINUTES = 180
EVENT_OPTION_MIN_HOLD_MINUTES = 20
COOLDOWN_MINUTES = 180
EARLIEST_ENTRY_TIME = dt_time(10, 0)
LATEST_ENTRY_TIME = dt_time(14, 30)
MAX_FEED_SNAPSHOT_AGE_SECONDS = 150
MAX_MODEL_FEATURE_AGE_SECONDS = 390
LOOP_INTERVAL_SECONDS = 65
CRITICAL_LIVE_CONTEXT_FEATURES = [
    "vix_5d_mean",
    "vix_5d_std",
    "atr_5d_norm",
]
EOD_CLEANUP_TIME = dt_time(16, 0)
FIXED_POLICY_NAME = "base_jepa_180m_fixed_delta_0.70_trail050_025_cutoff1430"
OPTION_VALUE_POLICY_NAME = "base_jepa_180m_option_value_blended_trail050_025_cutoff1430"
STRUCTURAL_POLICY_NAME = "level_stability_ensemble_nested_structural_profiles_risk5000"
OPTION_VALUE_SCORE_BASE = "ovjepa_pred_rule_best_mean"
OPTION_VALUE_DELTA_BONUS = 2.0
OPTION_VALUE_MIN_DELTA_ABS = 0.0
OPTION_VALUE_DELTA_TARGETS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70]

DISCORD_WEBHOOKS = [
    url
    for url in [os.getenv("DISCORD_WEBHOOK_URL"), os.getenv("DISCORD_WEBHOOK_URL_2")]
    if url
]
DISCORD_ROLE_ID = os.getenv("DISCORD_ROLE_ID", "1464601287411634226")
DISCORD_ROLE_PING = os.getenv("DISCORD_ROLE_PING", f"<@&{DISCORD_ROLE_ID}>").strip()
PAPER_ORDER_SCHEMA_VERSION = 1
TRADE_LOG_FIELDS = [
    "date",
    "entry_time",
    "exit_time",
    "ticker",
    "direction",
    "right",
    "strike",
    "delta",
    "entry_premium",
    "exit_premium",
    "contracts",
    "pnl_pct",
    "pnl_dollars",
    "hold_minutes",
    "exit_reason",
    "peak_pnl_pct",
    "trough_pnl_pct",
    "option_snapshot_suffix",
    "exit_contract",
    "source_model",
]


def _now_et() -> datetime:
    return datetime.now(ET)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else default
    except Exception:
        return default


def _normalize_right(value: Any) -> str:
    text = str(value).upper()
    if text in {"C", "CALL"}:
        return "CALL"
    if text in {"P", "PUT"}:
        return "PUT"
    return text


def _format_expiration(value: Any) -> str:
    text = "".join(ch for ch in str(value) if ch.isdigit())
    return text[:8] if len(text) >= 8 else text


def _format_expiration_for_tracker(value: Any) -> str:
    exp = _format_expiration(value)
    try:
        return datetime.strptime(exp, "%Y%m%d").strftime("%m/%d/%y")
    except Exception:
        return ""


def _ceil_cent(value: float) -> float:
    return math.ceil(max(float(value), 0.0) * 100.0 - 1e-9) / 100.0


def _floor_cent(value: float) -> float:
    return math.floor(max(float(value), 0.0) * 100.0 + 1e-9) / 100.0


def _post_discord(payload: dict[str, Any]) -> None:
    for webhook in DISCORD_WEBHOOKS:
        try:
            requests.post(webhook, json=payload, timeout=10)
        except Exception as exc:
            logging.getLogger(__name__).warning("Discord send failed: %s", exc)


def _send_discord(message: str, ping: bool = True) -> None:
    if not DISCORD_WEBHOOKS:
        return
    content = str(message).lstrip()
    if DISCORD_ROLE_PING and content.startswith(DISCORD_ROLE_PING):
        content = content[len(DISCORD_ROLE_PING) :].lstrip()

    if ping and DISCORD_ROLE_PING:
        ping_payload: dict[str, Any] = {"content": DISCORD_ROLE_PING}
        if DISCORD_ROLE_ID:
            ping_payload["allowed_mentions"] = {"roles": [DISCORD_ROLE_ID]}
        _post_discord(ping_payload)

    if content:
        _post_discord({"content": content})


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        out = float(value)
        return out if math.isfinite(out) else None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, (str, int, bool)):
        return value
    return str(value)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":")) + "\n")


@dataclass
class JepaOptionPosition:
    ticker: str
    direction: str
    right: str
    strike: float
    delta: float
    expiration: str
    entry_time: str
    entry_spot: float
    entry_premium: float
    raw_entry_premium: float
    entry_spread_pct: float
    contracts: int
    confidence: float
    jepa_prob_up: float
    long_threshold: float
    short_threshold: float
    selector_policy: str = FIXED_POLICY_NAME
    peak_pnl_pct: float = 0.0
    trough_pnl_pct: float = 0.0

    @classmethod
    def from_dict(cls, payload: dict) -> "JepaOptionPosition":
        return cls(
            ticker=str(payload["ticker"]),
            direction=str(payload["direction"]),
            right=str(payload["right"]),
            strike=float(payload["strike"]),
            delta=float(payload["delta"]),
            expiration=str(payload.get("expiration", "")),
            entry_time=str(payload["entry_time"]),
            entry_spot=float(payload["entry_spot"]),
            entry_premium=float(payload["entry_premium"]),
            raw_entry_premium=float(payload.get("raw_entry_premium", payload.get("entry_premium", 0.0))),
            entry_spread_pct=float(payload.get("entry_spread_pct", 0.0)),
            contracts=int(payload["contracts"]),
            confidence=float(payload.get("confidence", 0.0)),
            jepa_prob_up=float(payload.get("jepa_prob_up", 0.5)),
            long_threshold=float(payload.get("long_threshold", 0.0)),
            short_threshold=float(payload.get("short_threshold", 0.0)),
            selector_policy=str(payload.get("selector_policy", FIXED_POLICY_NAME)),
            peak_pnl_pct=float(payload.get("peak_pnl_pct", 0.0)),
            trough_pnl_pct=float(payload.get("trough_pnl_pct", 0.0)),
        )

    @property
    def entry_dt(self) -> datetime:
        return datetime.fromisoformat(self.entry_time)


class OptionValueLiveSelector:
    @staticmethod
    def _coerce_scalers(raw_scalers: dict) -> dict:
        scalers = {}
        for name, scaler in raw_scalers.items():
            if hasattr(scaler, "transform"):
                scalers[name] = scaler
            elif isinstance(scaler, dict) and {"features", "median", "scale"}.issubset(scaler):
                scalers[name] = FeatureScaler(
                    features=list(scaler["features"]),
                    median={str(k): float(v) for k, v in dict(scaler["median"]).items()},
                    scale={str(k): float(v) for k, v in dict(scaler["scale"]).items()},
                )
            else:
                raise TypeError(f"Unsupported OptionValue scaler payload for {name}: {type(scaler).__name__}")
        return scalers

    def __init__(self, model_dir: Path, device: str = "auto") -> None:
        if OPTION_VALUE_IMPORT_ERROR is not None:
            raise RuntimeError(f"OptionValue imports unavailable: {OPTION_VALUE_IMPORT_ERROR}")
        self.model_dir = Path(model_dir)
        model_path = self.model_dir / "option_value_jepa.pt"
        scalers_path = self.model_dir / "option_value_jepa_scalers.joblib"
        if not model_path.exists():
            raise FileNotFoundError(model_path)
        if not scalers_path.exists():
            raise FileNotFoundError(scalers_path)

        if device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        checkpoint = torch.load(model_path, map_location="cpu")
        config = OptionValueConfig(**checkpoint["config"])
        self.model = OptionValueJEPA(config).to(self.device)
        self.model.load_state_dict(checkpoint["model_state"])
        self.model.eval()
        if FeatureScaler is not None and not hasattr(main_module, "FeatureScaler"):
            setattr(main_module, "FeatureScaler", FeatureScaler)
        self.scalers = self._coerce_scalers(joblib.load(scalers_path))

    def predict(self, candidates: pd.DataFrame) -> pd.DataFrame:
        if candidates.empty:
            return candidates.copy()
        out = candidates.copy()
        market = torch.from_numpy(self.scalers["market"].transform(out)).to(self.device)
        option = torch.from_numpy(self.scalers["option"].transform(out)).to(self.device)
        horizon = torch.ones((len(out), 1), dtype=torch.float32, device=self.device)
        with torch.no_grad():
            pred = self.model.forward_entry(market, option, horizon).detach().cpu().numpy()
        out["ovjepa_pred_hold180"] = pred[:, 0]
        out["ovjepa_pred_rule"] = pred[:, 1]
        out["ovjepa_pred_best"] = pred[:, 2]
        return add_selector_score_bases(out)

    def select(self, candidates: pd.DataFrame) -> pd.Series | None:
        pred = self.predict(candidates)
        if pred.empty or OPTION_VALUE_SCORE_BASE not in pred.columns:
            return None
        work = pred.copy()
        if OPTION_VALUE_MIN_DELTA_ABS > 0.0:
            work = work[work["actual_delta_abs"].astype(float) >= OPTION_VALUE_MIN_DELTA_ABS].copy()
        if work.empty:
            return None
        work["_selector_score"] = (
            work[OPTION_VALUE_SCORE_BASE].astype(float)
            + OPTION_VALUE_DELTA_BONUS * work["actual_delta_abs"].astype(float)
        )
        return work.sort_values("_selector_score").iloc[-1]


@dataclass(frozen=True)
class StructuralOptionProfile:
    ticker: str
    delta_target: float
    max_minutes_to_close: float
    feature: str
    op: str
    threshold: float
    name: str = ""


class StructuralOptionProfileSelector:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        payload = _read_json(self.path, {})
        raw_profiles = payload.get("profiles", payload)
        if not isinstance(raw_profiles, dict) or not raw_profiles:
            raise ValueError(f"No structural option profiles found in {self.path}")
        self.policy = str(payload.get("policy", STRUCTURAL_POLICY_NAME))
        self.profiles: dict[str, StructuralOptionProfile] = {}
        for ticker, item in raw_profiles.items():
            if not isinstance(item, dict):
                continue
            profile = StructuralOptionProfile(
                ticker=str(item.get("ticker", ticker)).upper(),
                delta_target=float(item["delta_target"]),
                max_minutes_to_close=float(item.get("max_minutes_to_close", 9999.0)),
                feature=str(item.get("feature", "none")),
                op=str(item.get("op", "<=")),
                threshold=float(item.get("threshold", 0.0)),
                name=str(item.get("name", "")),
            )
            self.profiles[profile.ticker] = profile
        if not self.profiles:
            raise ValueError(f"No valid structural option profiles found in {self.path}")

    def select(self, ticker: str, candidates: pd.DataFrame) -> pd.Series | None:
        profile = self.profiles.get(str(ticker).upper())
        if profile is None or candidates.empty:
            return None
        work = candidates[np.isclose(pd.to_numeric(candidates["delta_target"], errors="coerce"), profile.delta_target)].copy()
        if work.empty:
            return None
        if profile.max_minutes_to_close < 9999:
            work = work[pd.to_numeric(work["minutes_to_close"], errors="coerce") <= profile.max_minutes_to_close].copy()
        if profile.feature != "none":
            if profile.feature not in work.columns:
                logging.warning("[%s] structural profile feature missing: %s", ticker, profile.feature)
                return None
            values = pd.to_numeric(work[profile.feature], errors="coerce")
            if profile.op in {"<=", "le"}:
                work = work[values <= profile.threshold].copy()
            elif profile.op in {">=", "ge"}:
                work = work[values >= profile.threshold].copy()
            else:
                raise ValueError(f"Unsupported structural profile op={profile.op}")
        if work.empty:
            return None
        work["_delta_dist"] = (pd.to_numeric(work["actual_delta_abs"], errors="coerce") - profile.delta_target).abs()
        work = work.dropna(subset=["_delta_dist", "strike"]).sort_values(["_delta_dist", "strike"])
        if work.empty:
            return None
        selected = work.iloc[0].copy()
        selected["structural_profile"] = profile.name or self._profile_name(profile)
        selected["structural_policy"] = self.policy
        return selected

    @staticmethod
    def _profile_name(profile: StructuralOptionProfile) -> str:
        time_part = "alltime" if profile.max_minutes_to_close >= 9999 else f"mtc_le_{profile.max_minutes_to_close:.0f}"
        return f"{profile.ticker}_d{profile.delta_target:.2f}_{time_part}_{profile.feature}_{profile.op}_{profile.threshold:.5g}"


class JepaFixedDeltaBot:
    def __init__(
        self,
        model_dir: Path,
        level_signal_path: Path | None,
        require_level_signal: bool,
        allow_signal_model_fallback: bool,
        option_value_model_dir: Path | None,
        option_value_device: str,
        structural_profile_path: Path | None,
        require_structural_profile: bool,
        event_option_policy_path: Path | None,
        require_event_option_policy: bool,
        event_option_component_registry_path: Path | None,
        require_event_option_component_registry: bool,
        require_event_option_live_ready: bool,
        enable_event_option_scorer: bool,
        strict_event_option_features: bool,
        allow_selector_fallback: bool,
        rt_data_dir: Path,
        trades_dir: Path,
        tickers: list[str],
        dry_run: bool = False,
        paper_order_intents: bool = False,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.rt_data_dir = Path(rt_data_dir)
        self.trades_dir = Path(trades_dir)
        self.tickers = [str(t).upper() for t in tickers]
        self.dry_run = bool(dry_run)
        self.paper_order_intents = bool(paper_order_intents)
        self.allow_selector_fallback = bool(allow_selector_fallback)
        self.allow_signal_model_fallback = bool(allow_signal_model_fallback)
        self.require_event_option_live_ready = bool(require_event_option_live_ready)
        self.event_option_scorer_enabled = bool(enable_event_option_scorer)
        self.strict_event_option_features = bool(strict_event_option_features)
        self.positions_path = self.trades_dir / "open_positions_jepa.json"
        self.cooldowns_path = self.trades_dir / "cooldowns_jepa.json"
        self.evaluated_features_path = self.trades_dir / "evaluated_features_jepa.json"
        self.event_option_state_path = self.trades_dir / "event_option_runtime_state.json"
        self.paper_order_intents_path = self.trades_dir / "paper_order_intents_jepa.jsonl"
        self.event_option_candidate_audit_path = self.trades_dir / "event_option_candidate_audit_jepa.jsonl"
        self.trade_log_path = self.trades_dir / "trades_jepa.csv"
        self.positions: dict[str, JepaOptionPosition] = self._load_positions()
        self.cooldowns: dict[str, str] = _read_json(self.cooldowns_path, {})
        self.evaluated_feature_timestamps: dict[str, str] = _read_json(self.evaluated_features_path, {})
        self.event_option_state: dict[str, Any] = self._load_event_option_state()
        self._event_option_candidate_cache_key = ""
        self._event_option_candidate_cache: pd.DataFrame = pd.DataFrame()
        self._event_option_candidate_cache_issues: list[str] = []
        self.level_signal = self._load_level_signal(level_signal_path, require_level_signal)
        needs_legacy_signal = (not self.event_option_scorer_enabled) and (
            self.level_signal is None or self.allow_signal_model_fallback
        )
        self.signal_model = (
            self._load_legacy_signal_model(required=self.level_signal is None)
            if needs_legacy_signal
            else None
        )
        self.structural_selector = self._load_structural_selector(structural_profile_path, require_structural_profile)
        self.event_option_policy = self._load_event_option_policy(
            event_option_policy_path,
            require_event_option_policy or self.require_event_option_live_ready,
            self.require_event_option_live_ready,
        )
        self.event_option_components = self._load_event_option_component_registry(
            event_option_component_registry_path,
            require_event_option_component_registry or self.require_event_option_live_ready,
            self.require_event_option_live_ready,
        )
        self.earliest_entry_time = self._resolve_earliest_entry_time()
        self.latest_entry_time = self._resolve_latest_entry_time()
        if self.require_event_option_live_ready and self.event_option_components is not None:
            entry_start_minute = int(self.earliest_entry_time.hour) * 60 + int(self.earliest_entry_time.minute)
            self.event_option_components.assert_live_observable_features(
                entry_start_minute_et=entry_start_minute
            )
        self.option_value_selector = self._load_option_value_selector(option_value_model_dir, option_value_device)
        if self.event_option_scorer_enabled:
            if EVENT_OPTION_SCORER_IMPORT_ERROR is not None:
                raise RuntimeError(f"Event-option live scorer import failed: {EVENT_OPTION_SCORER_IMPORT_ERROR}")
            if self.event_option_policy is None:
                raise RuntimeError("Event-option scorer enabled but policy is unavailable")
            if self.event_option_components is None:
                raise RuntimeError("Event-option scorer enabled but component registry is unavailable")
        if self.event_option_policy is not None and self.event_option_components is not None:
            missing = self.event_option_components.missing_for_full_live_equivalence
            if missing:
                logging.warning(
                    "Event-option policy is not marked full live-ready (missing_live_equivalence=%d). "
                    "If --enable-event-option-scorer is used, it is a guarded runtime replay path until "
                    "strict replay equivalence is completed.",
                    len(missing),
                )

    def _load_level_signal(self, signal_path: Path | None, required: bool) -> LevelStabilityLiveSignal | None:
        if signal_path is None:
            if required:
                raise FileNotFoundError("Level-stability signal path is required but disabled")
            logging.info("Level-stability live signal disabled")
            return None
        path = Path(signal_path)
        if not path.exists():
            if required:
                raise FileNotFoundError(path)
            logging.warning("Level-stability signal not found (%s); legacy signal fallback may be used", path)
            return None
        selector = LevelStabilityLiveSignal(path)
        logging.info("Loaded level-stability signal policy=%s path=%s", selector.policy, path)
        return selector

    def _load_legacy_signal_model(self, required: bool) -> Jepa180mSignalModel | None:
        try:
            model = Jepa180mSignalModel(self.model_dir, mode=MODEL_MODE, tickers=self.tickers)
            logging.info("Loaded legacy JEPA 180m signal model model_dir=%s", self.model_dir)
            return model
        except Exception as exc:
            if required:
                raise
            logging.warning("Legacy JEPA 180m signal model unavailable (%s)", exc)
            return None

    def _load_structural_selector(
        self,
        profile_path: Path | None,
        required: bool,
    ) -> StructuralOptionProfileSelector | None:
        if profile_path is None:
            if required:
                raise FileNotFoundError("Structural profile path is required but disabled")
            logging.info("Structural option selector disabled")
            return None
        path = Path(profile_path)
        if not path.exists():
            if required:
                raise FileNotFoundError(path)
            logging.warning("Structural option profile not found (%s); falling back to legacy selectors", path)
            return None
        selector = StructuralOptionProfileSelector(path)
        logging.info("Loaded structural option selector policy=%s path=%s", selector.policy, path)
        return selector

    def _load_event_option_policy(
        self,
        policy_path: Path | None,
        required: bool,
        require_live_ready: bool,
    ) -> dict[str, Any] | None:
        if policy_path is None:
            if required:
                raise FileNotFoundError("Event-option policy path is required but disabled")
            logging.info("Event-option production policy disabled")
            return None
        path = Path(policy_path)
        if not path.exists():
            if required:
                raise FileNotFoundError(path)
            logging.warning("Event-option production policy not found (%s)", path)
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Event-option policy must be a JSON object: {path}")
        if require_live_ready:
            status = str(payload.get("status", "")).lower()
            if "research" in status or "incomplete" in status:
                raise ValueError(f"Event-option policy is not live-ready: {payload.get('status', '')}")
        logging.info(
            "Loaded event-option production policy=%s deploy_month=%s status=%s path=%s",
            payload.get("policy", ""),
            payload.get("deploy_month", ""),
            payload.get("status", ""),
            path,
        )
        return payload

    def _load_event_option_component_registry(
        self,
        registry_path: Path | None,
        required: bool,
        require_live_ready: bool,
    ) -> EventOptionComponentRegistry | None:
        if registry_path is None:
            if required:
                raise FileNotFoundError("Event-option component registry path is required but disabled")
            logging.info("Event-option component registry disabled")
            return None
        path = Path(registry_path)
        if not path.exists():
            if required:
                raise FileNotFoundError(path)
            logging.warning("Event-option component registry not found (%s)", path)
            return None
        registry = EventOptionComponentRegistry.from_path(
            path,
            project_root=PROJECT_ROOT,
            require_complete_live_equivalence=bool(require_live_ready),
        )
        summary = registry.summary()
        missing = summary.get("missing_for_full_live_equivalence", [])
        invalidated = summary.get("invalidated_components", [])
        logging.info(
            "Loaded event-option component registry status=%s deploy_month=%s completed_through=%s components=%d missing_live_equivalence=%d invalidated=%d path=%s",
            summary.get("status", ""),
            summary.get("deploy_month", ""),
            summary.get("completed_data_through_month", ""),
            int(summary.get("component_count", 0)),
            len(missing) if isinstance(missing, list) else 0,
            len(invalidated) if isinstance(invalidated, list) else 0,
            path,
        )
        return registry

    def _resolve_earliest_entry_time(self) -> dt_time:
        policy = self.event_option_policy or {}
        live_contract = policy.get("live_contract") if isinstance(policy.get("live_contract"), dict) else {}
        raw = str(live_contract.get("entry_time_min_et", "")).strip()
        if raw:
            try:
                hour, minute = raw[:5].split(":")
                return dt_time(int(hour), int(minute))
            except Exception:
                logging.warning("Invalid event-option entry_time_min_et=%s; using default %s", raw, EARLIEST_ENTRY_TIME)
        return EARLIEST_ENTRY_TIME
    def _resolve_latest_entry_time(self) -> dt_time:
        policy = self.event_option_policy or {}
        live_contract = policy.get("live_contract") if isinstance(policy.get("live_contract"), dict) else {}
        raw = str(live_contract.get("entry_time_max_et", "")).strip()
        missing_live_equivalence = (
            self.event_option_components.missing_for_full_live_equivalence
            if self.event_option_components is not None
            else []
        )
        if missing_live_equivalence:
            if raw and raw != LATEST_ENTRY_TIME.strftime("%H:%M"):
                logging.warning(
                    "Ignoring event-option cutoff %s because component registry is not a complete live scorer; using %s",
                    raw,
                    LATEST_ENTRY_TIME.strftime("%H:%M"),
                )
            return LATEST_ENTRY_TIME
        if raw:
            try:
                hour, minute = raw[:5].split(":")
                return dt_time(int(hour), int(minute))
            except Exception:
                logging.warning("Invalid event-option entry_time_max_et=%s; using default %s", raw, LATEST_ENTRY_TIME)
        return LATEST_ENTRY_TIME

    def _load_option_value_selector(self, model_dir: Path | None, device: str) -> OptionValueLiveSelector | None:
        if model_dir is None:
            logging.info("OptionValue live selector disabled; using fixed delta %.2f", DELTA_TARGET)
            return None
        try:
            selector = OptionValueLiveSelector(Path(model_dir), device=device)
            logging.info(
                "Loaded OptionValue live selector model_dir=%s score=%s + %.2f*abs_delta",
                model_dir,
                OPTION_VALUE_SCORE_BASE,
                OPTION_VALUE_DELTA_BONUS,
            )
            return selector
        except Exception as exc:
            logging.warning("OptionValue selector unavailable (%s); falling back to fixed delta %.2f", exc, DELTA_TARGET)
            return None

    def _load_positions(self) -> dict[str, JepaOptionPosition]:
        payload = _read_json(self.positions_path, {})
        out = {}
        for ticker, item in payload.items():
            try:
                out[str(ticker)] = JepaOptionPosition.from_dict(item)
            except Exception:
                logging.exception("Failed to load JEPA position for %s", ticker)
        return out

    def _save_positions(self) -> None:
        _write_json(self.positions_path, {k: asdict(v) for k, v in self.positions.items()})

    def _save_cooldowns(self) -> None:
        _write_json(self.cooldowns_path, self.cooldowns)

    def _save_evaluated_features(self) -> None:
        _write_json(self.evaluated_features_path, self.evaluated_feature_timestamps)

    def _load_event_option_state(self) -> dict[str, Any]:
        payload = _read_json(self.event_option_state_path, {})
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("entries", [])
        payload.setdefault("candidate_ids", [])
        return payload

    def _save_event_option_state(self) -> None:
        entries = self.event_option_state.get("entries", [])
        if isinstance(entries, list) and len(entries) > 5000:
            self.event_option_state["entries"] = entries[-5000:]
        _write_json(self.event_option_state_path, self.event_option_state)

    def _record_event_option_candidate_audit(
        self,
        *,
        event: str,
        now: datetime,
        ticker: str = "",
        feature_id: str = "",
        candidates: pd.DataFrame | None = None,
        issues: list[str] | None = None,
        selected_row: pd.Series | dict[str, Any] | None = None,
        reason: str = "",
    ) -> None:
        try:
            payload: dict[str, Any] = {
                "schema_version": 1,
                "event": str(event),
                "recorded_at": now.isoformat(),
                "ticker": str(ticker).upper() if ticker else "",
                "feature_id": str(feature_id),
                "reason": str(reason),
                "issues": list(issues or []),
            }
            if candidates is not None:
                payload["candidate_count"] = int(len(candidates))
                payload["candidates"] = candidates.to_dict("records")
            if selected_row is not None:
                payload["selected_candidate"] = (
                    selected_row.to_dict() if isinstance(selected_row, pd.Series) else dict(selected_row)
                )
            _append_jsonl(self.event_option_candidate_audit_path, payload)
        except Exception as exc:
            logging.warning("Event-option candidate audit write failed: %s", exc)

    def _current_day_dir(self) -> Path:
        return self.rt_data_dir / _now_et().strftime("%Y%m%d")

    @staticmethod
    def _feature_row_id(row: pd.DataFrame) -> str:
        if row.empty:
            return ""
        latest = row.iloc[-1]
        timestamp = latest.get("timestamp")
        if pd.notna(timestamp):
            return str(timestamp)
        date_value = latest.get("date", "")
        minute = latest.get("minutes_since_open", "")
        return f"{date_value}:{minute}"

    @staticmethod
    def _feature_entry_time(row: pd.DataFrame) -> dt_time | None:
        if row.empty:
            return None
        latest = row.iloc[-1]
        value = latest.get("time")
        if pd.notna(value):
            try:
                hour, minute = str(value)[:5].split(":")
                return dt_time(int(hour), int(minute))
            except Exception:
                pass
        minute_value = _safe_float(latest.get("minutes_since_open", float("nan")), float("nan"))
        if math.isfinite(minute_value):
            total_minutes = 9 * 60 + 30 + int(round(minute_value))
            return dt_time(total_minutes // 60, total_minutes % 60)
        return None

    def _mark_feature_evaluated(self, ticker: str, feature_id: str) -> None:
        if not feature_id:
            return
        self.evaluated_feature_timestamps[ticker] = feature_id
        self._save_evaluated_features()

    def _read_parquet(self, filename: str, max_age: int = MAX_FEED_SNAPSHOT_AGE_SECONDS) -> pd.DataFrame:
        path = self._current_day_dir() / filename
        if not path.exists():
            return pd.DataFrame()
        age = time.time() - path.stat().st_mtime
        if age > max_age:
            logging.warning("[Feed] stale %s age=%.0fs", filename, age)
            return pd.DataFrame()
        try:
            return pd.read_parquet(path)
        except Exception:
            logging.exception("[Feed] could not read %s", path)
            return pd.DataFrame()

    def _latest_feature_row(self, ticker: str) -> pd.DataFrame:
        df = self._read_parquet(
            f"ml_features_{ticker}_latest.parquet",
            max_age=MAX_MODEL_FEATURE_AGE_SECONDS,
        )
        if df.empty:
            return pd.DataFrame()
        if "xjepa_context_valid" not in df.columns:
            logging.info("[%s] no xjepa_context_valid column yet", ticker)
            return pd.DataFrame()
        row = df.tail(1).copy()
        if float(row["xjepa_context_valid"].iloc[0]) <= 0.0:
            logging.info("[%s] JEPA context not valid yet; needs 24 five-minute rows", ticker)
            return pd.DataFrame()

        # Safety guard: xjepa_context_valid only proves the JEPA sequence has
        # enough same-day 5-minute rows.  It does not prove the base live
        # context features match the OOS/production-training feature contract.
        # Do not open entries if the feed has not populated the historical
        # context features that the model used in training.  This guard only
        # affects entries; exits/position management are handled elsewhere.
        if "live_feature_context_valid" not in row.columns:
            logging.info("[%s] live_feature_context_valid missing; skipping entry", ticker)
            return pd.DataFrame()
        if _safe_float(row["live_feature_context_valid"].iloc[0], 0.0) <= 0.0:
            bad = []
            for col in CRITICAL_LIVE_CONTEXT_FEATURES:
                if col not in row.columns or _safe_float(row[col].iloc[0], 0.0) <= 0.0:
                    bad.append(col)
            logging.info(
                "[%s] live feature context not valid; skipping entry bad=%s",
                ticker,
                bad or ["live_feature_context_valid"],
            )
            return pd.DataFrame()

        bad = [
            col for col in CRITICAL_LIVE_CONTEXT_FEATURES
            if col not in row.columns or _safe_float(row[col].iloc[0], 0.0) <= 0.0
        ]
        if bad:
            logging.info("[%s] zero/invalid critical live features; skipping entry bad=%s", ticker, bad)
            return pd.DataFrame()
        return row

    def _latest_spot(self, ticker: str) -> float:
        df = self._read_parquet(f"spot_{ticker}_latest.parquet")
        if df.empty or "close" not in df.columns:
            return 0.0
        return _safe_float(df["close"].iloc[-1])

    def _latest_option_snapshot(self, ticker: str, suffix: str = "0dte") -> pd.DataFrame:
        symbol = OPTIONS_SYMBOLS.get(ticker, ticker)
        suffix = str(suffix or "0dte")
        df = self._read_parquet(f"{symbol}_greeks_{suffix}_latest.parquet")
        if df.empty:
            return df
        if "underlying_timestamp" in df.columns:
            dt = pd.to_datetime(df["underlying_timestamp"], format="mixed", errors="coerce")
            latest = dt.max()
            if pd.notna(latest):
                df = df[dt == latest].copy()
        if "right" in df.columns:
            df["right_norm"] = df["right"].map(_normalize_right)
        return df

    def _latest_ohlc_snapshot(self, ticker: str, suffix: str = "0dte") -> pd.DataFrame:
        symbol = OPTIONS_SYMBOLS.get(ticker, ticker)
        suffix = str(suffix or "0dte")
        df = self._read_parquet(f"{symbol}_ohlc_{suffix}_latest.parquet")
        if df.empty:
            return df
        time_col = "timestamp" if "timestamp" in df.columns else "underlying_timestamp" if "underlying_timestamp" in df.columns else ""
        if time_col:
            dt = pd.to_datetime(df[time_col], format="mixed", errors="coerce")
            latest = dt.max()
            if pd.notna(latest):
                df = df[dt == latest].copy()
        if "right" in df.columns:
            df["right_norm"] = df["right"].map(_normalize_right)
        return df

    @staticmethod
    def _row_price(row: pd.Series) -> float:
        bid = _safe_float(row.get("bid", 0.0))
        ask = _safe_float(row.get("ask", 0.0))
        if bid > 0 or ask > 0:
            return (bid + ask) / 2.0
        for col in ["mid_price", "mark", "close", "last", "price"]:
            value = _safe_float(row.get(col, 0.0))
            if value > 0:
                return value
        return 0.0

    def _option_price_from_ohlc(self, ticker: str, strike: float, right: str, suffix: str = "0dte") -> float:
        df = self._latest_ohlc_snapshot(ticker, suffix=suffix)
        if df.empty or "strike" not in df.columns or "right_norm" not in df.columns:
            return 0.0
        work = df[(df["right_norm"] == right) & (np.isclose(pd.to_numeric(df["strike"], errors="coerce"), strike))]
        if work.empty:
            return 0.0
        return self._row_price(work.iloc[-1])

    def _select_fixed_delta_option(self, ticker: str, direction: str) -> dict | None:
        right = RIGHT_FOR_DIRECTION[direction]
        df = self._latest_option_snapshot(ticker)
        if df.empty or "delta" not in df.columns or "strike" not in df.columns or "right_norm" not in df.columns:
            return None
        work = df[df["right_norm"] == right].copy()
        if work.empty:
            return None
        work["delta_abs"] = pd.to_numeric(work["delta"], errors="coerce").abs()
        work = work[work["delta_abs"] > 0.01].copy()
        if "bid" in work.columns:
            work = work[pd.to_numeric(work["bid"], errors="coerce") > 0].copy()
        if work.empty:
            return None
        work["delta_dist"] = (work["delta_abs"] - DELTA_TARGET).abs()
        work = work.dropna(subset=["delta_dist", "strike"]).sort_values(["delta_dist", "strike"])
        if work.empty:
            return None

        for _, row in work.head(8).iterrows():
            strike = _safe_float(row.get("strike", 0.0))
            if strike <= 0:
                continue
            premium = self._row_price(row)
            if premium <= 0:
                premium = self._option_price_from_ohlc(ticker, strike, right)
            if premium <= 0:
                continue
            return {
                "ticker": ticker,
                "right": right,
                "strike": strike,
                "delta": _safe_float(row.get("delta", 0.0)),
                "premium": premium,
                "expiration": _format_expiration(row.get("expiration", "")),
                "selector_policy": FIXED_POLICY_NAME,
            }
        return None

    def _select_delta_option(
        self,
        ticker: str,
        *,
        right: str,
        delta_target: float,
        suffix: str,
        features: pd.DataFrame | None = None,
        selector_policy: str,
        selector_score: float = 0.0,
    ) -> dict | None:
        right = _normalize_right(right)
        suffix = str(suffix or "0dte")
        df = self._latest_option_snapshot(ticker, suffix=suffix)
        if df.empty or "delta" not in df.columns or "strike" not in df.columns or "right_norm" not in df.columns:
            return None
        work = df[df["right_norm"] == right].copy()
        if work.empty:
            return None
        work["delta_abs"] = pd.to_numeric(work["delta"], errors="coerce").abs()
        work = work[work["delta_abs"] > 0.01].copy()
        if "bid" in work.columns:
            work = work[pd.to_numeric(work["bid"], errors="coerce") > 0].copy()
        if work.empty:
            return None
        work["delta_dist"] = (work["delta_abs"] - float(delta_target)).abs()
        work = work.dropna(subset=["delta_dist", "strike"]).sort_values(["delta_dist", "strike"])
        for _, row in work.head(8).iterrows():
            strike = _safe_float(row.get("strike", 0.0))
            if strike <= 0:
                continue
            raw_premium = self._row_price(row)
            if raw_premium <= 0:
                raw_premium = self._option_price_from_ohlc(ticker, strike, right, suffix=suffix)
            if raw_premium <= 0:
                continue
            actual_delta = _safe_float(row.get("delta", 0.0))
            feature_frame = features if features is not None else pd.DataFrame()
            model_entry_spread_pct = self._entry_spread_pct(abs(actual_delta), feature_frame)
            entry_premium = raw_premium * (1.0 + model_entry_spread_pct)
            ask_premium = _safe_float(row.get("ask", 0.0), 0.0)
            if ask_premium > 0.0:
                entry_premium = max(entry_premium, ask_premium)
            entry_spread_pct = entry_premium / max(raw_premium, 1e-9) - 1.0
            return {
                "ticker": ticker,
                "right": right,
                "strike": strike,
                "delta": actual_delta,
                "premium": raw_premium,
                "entry_premium": entry_premium,
                "raw_entry_premium": raw_premium,
                "entry_spread_pct": entry_spread_pct,
                "expiration": _format_expiration(row.get("expiration", "")),
                "selector_policy": selector_policy,
                "selector_score": float(selector_score),
                "option_snapshot_suffix": suffix,
            }
        return None

    def _option_value_candidates(self, ticker: str, direction: str, features: pd.DataFrame) -> pd.DataFrame:
        if features.empty:
            return pd.DataFrame()
        right = RIGHT_FOR_DIRECTION[direction]
        df = self._latest_option_snapshot(ticker)
        if df.empty or "delta" not in df.columns or "strike" not in df.columns or "right_norm" not in df.columns:
            return pd.DataFrame()
        work = df[df["right_norm"] == right].copy()
        if work.empty:
            return pd.DataFrame()
        work["delta_abs"] = pd.to_numeric(work["delta"], errors="coerce").abs()
        work = work[work["delta_abs"] > 0.01].copy()
        if "bid" in work.columns:
            work = work[pd.to_numeric(work["bid"], errors="coerce") > 0].copy()
        if work.empty:
            return pd.DataFrame()

        feature_row = features.iloc[-1].to_dict()
        spot = self._latest_spot(ticker)
        if spot <= 0:
            spot = _safe_float(feature_row.get("spot_price", 0.0), 0.0)
        now = _now_et()
        date_value = str(feature_row.get("date", now.strftime("%Y%m%d")))
        time_value = str(feature_row.get("time", now.strftime("%H:%M")))
        minutes_since_open = _safe_float(feature_row.get("minutes_since_open", 0.0), 0.0)
        minutes_to_close = max(0.0, 390.0 - minutes_since_open)
        rows: list[dict[str, Any]] = []
        for delta_target in OPTION_VALUE_DELTA_TARGETS:
            target_work = work.copy()
            target_work["delta_dist"] = (target_work["delta_abs"] - float(delta_target)).abs()
            target_work = target_work.dropna(subset=["delta_dist", "strike"]).sort_values(["delta_dist", "strike"])
            for _, chain_row in target_work.head(8).iterrows():
                strike = _safe_float(chain_row.get("strike", 0.0))
                if strike <= 0:
                    continue
                raw_premium = self._row_price(chain_row)
                if raw_premium <= 0:
                    raw_premium = self._option_price_from_ohlc(ticker, strike, right)
                if raw_premium <= 0:
                    continue
                actual_delta = _safe_float(chain_row.get("delta", 0.0))
                actual_delta_abs = abs(actual_delta)
                entry_spread_pct = self._entry_spread_pct(actual_delta_abs, features)
                entry_premium = raw_premium * (1.0 + entry_spread_pct)
                contracts = self._contracts(entry_premium)
                if contracts <= 0:
                    continue
                actual_iv = _safe_float(
                    chain_row.get("implied_vol", chain_row.get("implied_volatility", chain_row.get("iv", 0.15))),
                    0.15,
                )
                actual_theta = _safe_float(chain_row.get("theta", 0.0), 0.0)
                actual_gamma = _safe_float(chain_row.get("gamma", 0.0), 0.0)
                candidate = dict(feature_row)
                candidate.update(
                    {
                        "ticker": ticker,
                        "date": date_value,
                        "month": date_value[:6],
                        "time": time_value[:5],
                        "side": direction,
                        "minutes_to_close": minutes_to_close,
                        "ticker_SPX": 1.0 if ticker == "SPX" else 0.0,
                        "ticker_QQQ": 1.0 if ticker == "QQQ" else 0.0,
                        "ticker_SPY": 1.0 if ticker == "SPY" else 0.0,
                        "side_LONG": 1.0 if direction == "LONG" else 0.0,
                        "side_SHORT": 1.0 if direction == "SHORT" else 0.0,
                        "spot_price": spot,
                        "delta_target": float(delta_target),
                        "actual_strike": strike,
                        "strike": strike,
                        "right": right,
                        "expiration": _format_expiration(chain_row.get("expiration", "")),
                        "contracts": int(contracts),
                        "entry_cost_dollars": entry_premium * CONTRACT_MULTIPLIER * contracts,
                        "actual_delta": actual_delta,
                        "actual_delta_abs": actual_delta_abs,
                        "entry_premium": entry_premium,
                        "raw_entry_premium": raw_premium,
                        "premium": raw_premium,
                        "entry_spread_pct": entry_spread_pct,
                        "premium_to_spot_bps": entry_premium / max(spot, 1e-9) * 10000.0,
                        "strike_distance_pts": strike - spot,
                        "strike_distance_bps": (strike - spot) / max(spot, 1e-9) * 10000.0,
                        "actual_iv": actual_iv,
                        "actual_theta": actual_theta,
                        "actual_gamma": actual_gamma,
                        "theta_over_premium": actual_theta / max(entry_premium, 1e-9),
                        "gamma_notional": actual_gamma * spot * CONTRACT_MULTIPLIER * contracts,
                    }
                )
                rows.append(candidate)
                break
        return pd.DataFrame(rows)

    def _select_option_value_option(self, ticker: str, direction: str, features: pd.DataFrame) -> dict | None:
        if self.option_value_selector is None:
            return None
        candidates = self._option_value_candidates(ticker, direction, features)
        selected = self.option_value_selector.select(candidates)
        if selected is None:
            return None
        return {
            "ticker": ticker,
            "right": str(selected["right"]),
            "strike": float(selected["strike"]),
            "delta": float(selected["actual_delta"]),
            "premium": float(selected["raw_entry_premium"]),
            "entry_premium": float(selected["entry_premium"]),
            "raw_entry_premium": float(selected["raw_entry_premium"]),
            "entry_spread_pct": float(selected["entry_spread_pct"]),
            "expiration": str(selected.get("expiration", "")),
            "selector_policy": OPTION_VALUE_POLICY_NAME,
            "selector_score": _safe_float(selected.get("_selector_score", 0.0), 0.0),
            "ovjepa_pred_hold180": _safe_float(selected.get("ovjepa_pred_hold180", 0.0), 0.0),
            "ovjepa_pred_rule": _safe_float(selected.get("ovjepa_pred_rule", 0.0), 0.0),
            "ovjepa_pred_best": _safe_float(selected.get("ovjepa_pred_best", 0.0), 0.0),
        }

    def _select_structural_profile_option(self, ticker: str, direction: str, features: pd.DataFrame) -> dict | None:
        if self.structural_selector is None:
            return None
        candidates = self._option_value_candidates(ticker, direction, features)
        selected = self.structural_selector.select(ticker, candidates)
        if selected is None:
            return None
        profile_name = str(selected.get("structural_profile", ""))
        return {
            "ticker": ticker,
            "right": str(selected["right"]),
            "strike": float(selected["strike"]),
            "delta": float(selected["actual_delta"]),
            "premium": float(selected["raw_entry_premium"]),
            "entry_premium": float(selected["entry_premium"]),
            "raw_entry_premium": float(selected["raw_entry_premium"]),
            "entry_spread_pct": float(selected["entry_spread_pct"]),
            "expiration": str(selected.get("expiration", "")),
            "selector_policy": f"{selected.get('structural_policy', STRUCTURAL_POLICY_NAME)}:{profile_name}",
            "selector_score": 0.0,
            "structural_profile": profile_name,
        }

    def _latest_event_option_snapshots(self) -> pd.DataFrame:
        return self._read_parquet("event_option_snapshots_latest.parquet", max_age=MAX_MODEL_FEATURE_AGE_SECONDS)

    @staticmethod
    def _event_feature_row_id(candidates: pd.DataFrame, ticker: str) -> str:
        if candidates.empty:
            return ""
        work = candidates[candidates.get("bot_ticker", pd.Series(dtype=str)).astype(str).str.upper().eq(str(ticker).upper())]
        if work.empty:
            return ""
        latest = work.sort_values([col for col in ["timestamp", "time", "expiry_mode"] if col in work.columns]).tail(1).iloc[-1]
        timestamp = str(latest.get("timestamp", ""))
        if timestamp:
            return timestamp
        return f"{latest.get('date', latest.get('trade_date', ''))}:{latest.get('time', '')}"

    def _score_event_option_candidates(self) -> tuple[pd.DataFrame, list[str]]:
        if not self.event_option_scorer_enabled or self.event_option_components is None:
            return pd.DataFrame(), []
        snapshot_path = self._current_day_dir() / "event_option_snapshots_latest.parquet"
        if snapshot_path.exists():
            cache_key = f"{snapshot_path}:{snapshot_path.stat().st_mtime_ns}"
            if cache_key == self._event_option_candidate_cache_key:
                return self._event_option_candidate_cache.copy(), list(self._event_option_candidate_cache_issues)
        else:
            cache_key = ""
        snapshots = self._latest_event_option_snapshots()
        if snapshots.empty:
            return pd.DataFrame(), ["event_option_snapshots_latest.parquet unavailable"]
        assert score_event_option_live_candidates is not None
        candidates, issues, _enriched = score_event_option_live_candidates(
            self.event_option_components,
            snapshots,
            strict_features=self.strict_event_option_features,
        )
        self._event_option_candidate_cache_key = cache_key
        self._event_option_candidate_cache = candidates.copy()
        self._event_option_candidate_cache_issues = list(issues)
        self._record_event_option_candidate_audit(
            event="score_snapshot",
            now=_now_et(),
            candidates=candidates,
            issues=list(issues),
            reason=f"snapshot_cache_key={cache_key}",
        )
        return candidates, issues

    def _event_state_entries(self) -> list[dict[str, Any]]:
        entries = self.event_option_state.get("entries", [])
        return entries if isinstance(entries, list) else []

    def _event_candidate_seen(self, candidate_id: str) -> bool:
        seen = self.event_option_state.get("candidate_ids", [])
        return str(candidate_id) in set(str(item) for item in seen if item)

    def _event_daily_entry_count(self, policy_ticker: str, date_value: str) -> int:
        policy_ticker = str(policy_ticker).upper()
        return sum(
            1
            for item in self._event_state_entries()
            if str(item.get("policy_ticker", "")).upper() == policy_ticker
            and str(item.get("date", "")) == str(date_value)
        )

    def _event_monthly_entry_count(self, policy_ticker: str, month_value: str) -> int:
        policy_ticker = str(policy_ticker).upper()
        month_value = str(month_value)
        return sum(
            1
            for item in self._event_state_entries()
            if str(item.get("policy_ticker", "")).upper() == policy_ticker
            and str(item.get("date", "")).startswith(month_value)
        )

    def _event_last_entry_dt(self, policy_ticker: str, date_value: str) -> datetime | None:
        values: list[datetime] = []
        policy_ticker = str(policy_ticker).upper()
        for item in self._event_state_entries():
            if str(item.get("policy_ticker", "")).upper() != policy_ticker:
                continue
            if str(item.get("date", "")) != str(date_value):
                continue
            try:
                values.append(datetime.fromisoformat(str(item.get("entry_time", ""))))
            except Exception:
                continue
        return max(values) if values else None

    @staticmethod
    def _read_trade_log_csv(path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame(columns=TRADE_LOG_FIELDS)
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
        except Exception:
            logging.exception("Could not read trade log %s", path)
            return pd.DataFrame(columns=TRADE_LOG_FIELDS)
        if not rows:
            return pd.DataFrame(columns=TRADE_LOG_FIELDS)
        header = [str(col).strip() for col in rows[0]]
        missing_fields = [field for field in TRADE_LOG_FIELDS if field not in header]
        records: list[dict[str, Any]] = []
        for values in rows[1:]:
            if not values or not any(str(value).strip() for value in values):
                continue
            record = {field: "" for field in TRADE_LOG_FIELDS}
            for idx, value in enumerate(values[: len(header)]):
                if idx < len(header) and header[idx] in record:
                    record[header[idx]] = value
            extra_values = values[len(header) :]
            for field, value in zip(missing_fields, extra_values):
                record[field] = value
            records.append(record)
        return pd.DataFrame(records, columns=TRADE_LOG_FIELDS)

    def _event_trade_log(self) -> pd.DataFrame:
        return self._read_trade_log_csv(self.trade_log_path)

    @staticmethod
    def _required_count_by_date(month_value: str, date_value: str, target: int) -> int:
        try:
            start = pd.Timestamp(year=int(str(month_value)[:4]), month=int(str(month_value)[4:6]), day=1)
        except Exception:
            return int(target)
        end = start + pd.offsets.MonthEnd(0)
        days = pd.bdate_range(start, end)
        current = pd.to_datetime(str(date_value), format="%Y%m%d", errors="coerce")
        if pd.isna(current):
            return 1
        elapsed = int((days <= current).sum())
        return int(math.ceil(float(target) * float(max(1, elapsed)) / float(max(1, len(days)))))

    @staticmethod
    def _log_exit_dt(frame: pd.DataFrame) -> pd.Series:
        if frame.empty or "date" not in frame.columns or "exit_time" not in frame.columns:
            return pd.Series(pd.NaT, index=frame.index)
        return pd.to_datetime(
            frame["date"].astype(str) + " " + frame["exit_time"].astype(str).str.slice(0, 5),
            format="%Y%m%d %H:%M",
            errors="coerce",
        )

    def _event_known_log_rows(self, *, policy_ticker: str, date_value: str, now: datetime) -> pd.DataFrame:
        log = self._event_trade_log()
        if log.empty or "source_model" not in log.columns or "pnl_dollars" not in log.columns:
            return pd.DataFrame()
        source = log["source_model"].astype(str)
        work = log[
            source.str.contains(f"event_option:{str(policy_ticker).upper()}:", regex=False)
            & (log["date"].astype(str) == str(date_value))
        ].copy()
        if work.empty:
            return work
        work["_exit_dt"] = self._log_exit_dt(work)
        current = pd.Timestamp(now.replace(tzinfo=None))
        work = work[work["_exit_dt"].notna() & (work["_exit_dt"] <= current)].copy()
        sort_cols = [col for col in ["_exit_dt", "entry_time"] if col in work.columns]
        return work.sort_values(sort_cols, kind="stable") if sort_cols else work

    def _event_daily_loss_guard_config(self) -> dict[str, Any]:
        payload = self.event_option_policy if isinstance(self.event_option_policy, dict) else {}
        guards = payload.get("runtime_risk_guards") if isinstance(payload.get("runtime_risk_guards"), dict) else {}
        cfg = guards.get("daily_loss_streak_pause") if isinstance(guards.get("daily_loss_streak_pause"), dict) else {}
        if not bool(cfg.get("enabled", False)):
            return {"enabled": False}
        return {
            "enabled": True,
            "trigger_losses": max(1, int(_safe_float(cfg.get("trigger_losses", 4), 4))),
            "pause_days": max(1, int(_safe_float(cfg.get("pause_days", 1), 1))),
            "loss_threshold_return": _safe_float(cfg.get("loss_threshold_return", 0.0), 0.0),
            "risk_capital": max(1.0, _safe_float(cfg.get("risk_capital_dollars", RISK_CAPITAL), RISK_CAPITAL)),
        }

    def _event_daily_loss_guard_skips(self) -> list[dict[str, Any]]:
        skips = self.event_option_state.get("daily_loss_guard_skips", [])
        return skips if isinstance(skips, list) else []

    def _event_daily_loss_guard_skip_dates(self, policy_ticker: str, before_or_equal_date: str) -> set[str]:
        ticker = str(policy_ticker).upper()
        cutoff = str(before_or_equal_date)
        return {
            str(item.get("date", ""))
            for item in self._event_daily_loss_guard_skips()
            if str(item.get("policy_ticker", "")).upper() == ticker
            and str(item.get("date", "")) <= cutoff
        }

    def _record_event_daily_loss_guard_skip(
        self,
        *,
        policy_ticker: str,
        date_value: str,
        now: datetime,
        reason: str,
        config: dict[str, Any],
    ) -> None:
        ticker = str(policy_ticker).upper()
        date_text = str(date_value)
        skips = self._event_daily_loss_guard_skips()
        if any(str(item.get("policy_ticker", "")).upper() == ticker and str(item.get("date", "")) == date_text for item in skips):
            return
        skips.append(
            {
                "policy_ticker": ticker,
                "date": date_text,
                "recorded_at": now.isoformat(),
                "reason": reason,
                "trigger_losses": int(config.get("trigger_losses", 0)),
                "pause_days": int(config.get("pause_days", 0)),
                "loss_threshold_return": float(config.get("loss_threshold_return", 0.0)),
            }
        )
        self.event_option_state["daily_loss_guard_skips"] = skips[-5000:]
        self._save_event_option_state()

    def _event_completed_daily_returns(self, policy_ticker: str, before_date: str, risk_capital: float) -> dict[str, float]:
        log = self._event_trade_log()
        if log.empty or "source_model" not in log.columns or "pnl_dollars" not in log.columns or "date" not in log.columns:
            return {}
        ticker = str(policy_ticker).upper()
        source = log["source_model"].astype(str)
        work = log[
            source.str.contains(f"event_option:{ticker}:", regex=False)
            & (log["date"].astype(str) < str(before_date))
        ].copy()
        if work.empty:
            return {}
        work["pnl_return"] = pd.to_numeric(work["pnl_dollars"], errors="coerce").fillna(0.0) / float(risk_capital)
        return {str(date): float(value) for date, value in work.groupby(work["date"].astype(str))["pnl_return"].sum().items()}

    def _event_daily_loss_guard_blocked(self, policy_ticker: str, date_value: str, now: datetime) -> tuple[bool, str]:
        cfg = self._event_daily_loss_guard_config()
        if not bool(cfg.get("enabled", False)):
            return False, ""
        ticker = str(policy_ticker).upper()
        date_text = str(date_value)
        skip_dates = self._event_daily_loss_guard_skip_dates(ticker, date_text)
        if date_text in skip_dates:
            return True, "daily_loss_streak_pause_already_active"
        daily_returns = self._event_completed_daily_returns(ticker, date_text, float(cfg["risk_capital"]))
        pause_remaining = 0
        loss_streak = 0
        for day in sorted(set(daily_returns).union({day for day in skip_dates if day < date_text})):
            if pause_remaining > 0:
                if day in skip_dates:
                    pause_remaining -= 1
                    continue
                pause_remaining = 0
            if day not in daily_returns:
                continue
            day_return = float(daily_returns[day])
            if day_return < float(cfg["loss_threshold_return"]):
                loss_streak += 1
            elif day_return > 0.0:
                loss_streak = 0
            if loss_streak >= int(cfg["trigger_losses"]):
                pause_remaining = int(cfg["pause_days"])
                loss_streak = 0
        if pause_remaining <= 0:
            return False, ""
        reason = f"daily_loss_streak_pause_t{int(cfg['trigger_losses'])}_p{int(cfg['pause_days'])}"
        self._record_event_daily_loss_guard_skip(
            policy_ticker=ticker,
            date_value=date_text,
            now=now,
            reason=reason,
            config=cfg,
        )
        return True, reason

    @staticmethod
    def _event_action_from_log(work: pd.DataFrame) -> pd.Series:
        if "right" in work.columns:
            right = work["right"].astype(str).str.upper()
            return right.where(right.isin(["CALL", "PUT"]), "")
        if "direction" in work.columns:
            return work["direction"].astype(str).str.upper().map({"LONG": "CALL", "SHORT": "PUT"}).fillna("")
        return pd.Series("", index=work.index)

    def _qqq_prior_completed_day_base_mtd(self, date_value: str) -> float:
        log = self._event_trade_log()
        if log.empty or "source_model" not in log.columns or "pnl_dollars" not in log.columns:
            return 0.0
        month = str(date_value)[:6]
        source = log["source_model"].astype(str)
        work = log[
            source.str.contains("event_option:QQQ:", regex=False)
            & (log["date"].astype(str).str[:6] == month)
            & (log["date"].astype(str) < str(date_value))
            & (source.str.contains(":meta_s1:", regex=False) | source.str.contains(":current:", regex=False))
        ].copy()
        if work.empty:
            return 0.0
        return float(pd.to_numeric(work["pnl_dollars"], errors="coerce").fillna(0.0).sum() / RISK_CAPITAL)

    def _spxw_fallback_side_daily_return(self, date_value: str, action: str, now: datetime) -> float:
        work = self._event_known_log_rows(policy_ticker="SPXW", date_value=date_value, now=now)
        if work.empty:
            return 0.0
        source = work["source_model"].astype(str)
        work = work[source.str.contains(":base_fallback:", regex=False)].copy()
        actions = self._event_action_from_log(work)
        work = work[actions.astype(str).str.upper().eq(str(action).upper())].copy()
        if work.empty:
            return 0.0
        return float(pd.to_numeric(work["pnl_dollars"], errors="coerce").fillna(0.0).sum() / RISK_CAPITAL)

    def _qqq_current_circuit_halted(self, row: pd.Series, date_value: str, now: datetime) -> tuple[bool, str]:
        mtd_source = str(row.get("mtd_source", "")).lower()
        source_variant = str(row.get("source_variant", "")).lower()
        if mtd_source != "current" and source_variant != "current":
            return False, ""
        cfg: dict[str, Any] = {
            "config": "streak1_daylossoff_lossesoff",
            "stop_after_loss_streak": 1,
            "daily_loss_limit": -999.0,
            "total_loss_limit": 999,
            "min_trades_before_halt": 0,
        }
        side_specific = True
        if self.event_option_components is not None and "QQQ.current_intraday_circuit" in self.event_option_components.components:
            try:
                cfg = self.event_option_components.intraday_circuit_config("QQQ.current_intraday_circuit", ticker="QQQ")
                side_specific = bool(self.event_option_components.component("QQQ.current_intraday_circuit").metadata.get("side_specific", True))
            except Exception:
                logging.exception("Could not load QQQ current intraday circuit config; using deploy defaults")
        work = self._event_known_log_rows(policy_ticker="QQQ", date_value=date_value, now=now)
        if work.empty:
            return False, ""
        source = work["source_model"].astype(str)
        work = work[
            source.str.contains("event_option:QQQ:current:", regex=False)
            | source.str.contains("event_option:QQQ:online:current:", regex=False)
        ].copy()
        if work.empty:
            return False, ""
        if side_specific:
            candidate_action = str(row.get("action", "")).upper()
            actions = self._event_action_from_log(work)
            work = work[actions.astype(str).str.upper().eq(candidate_action)].copy()
        if work.empty:
            return False, ""
        returns = pd.to_numeric(work["pnl_dollars"], errors="coerce").fillna(0.0) / RISK_CAPITAL
        known_day_return = 0.0
        loss_streak = 0
        total_losses = 0
        taken = 0
        for ret in returns:
            known_day_return += float(ret)
            taken += 1
            if float(ret) < 0.0:
                loss_streak += 1
                total_losses += 1
            elif float(ret) > 0.0:
                loss_streak = 0
            triggered = (
                loss_streak >= int(cfg.get("stop_after_loss_streak", 999))
                or known_day_return <= float(cfg.get("daily_loss_limit", -999.0))
                or total_losses >= int(cfg.get("total_loss_limit", 999))
            )
            if triggered and taken >= int(cfg.get("min_trades_before_halt", 0)):
                return True, f"qqq_current_circuit_{cfg.get('config', 'halted')}"
        return False, ""

    @staticmethod
    def _event_int(row: pd.Series, name: str, default: int) -> int:
        try:
            value = int(float(row.get(name, default)))
            return value if value > 0 else int(default)
        except Exception:
            return int(default)

    def _event_candidate_allowed(self, row: pd.Series, now: datetime) -> tuple[bool, str]:
        candidate_id = str(row.get("event_candidate_id", ""))
        if candidate_id and self._event_candidate_seen(candidate_id):
            return False, "duplicate_candidate"
        policy_ticker = str(row.get("policy_ticker", row.get("ticker", ""))).upper()
        date_value = str(row.get("date", row.get("trade_date", now.strftime("%Y%m%d"))))
        blocked, reason = self._event_daily_loss_guard_blocked(policy_ticker, date_value, now)
        if blocked:
            return False, reason
        max_day = self._event_int(row, "policy_max_day", 999)
        if max_day < 999 and self._event_daily_entry_count(policy_ticker, date_value) >= max_day:
            return False, f"policy_max_day_{max_day}_reached"
        cooldown = self._event_int(row, "policy_cooldown_minutes", 0)
        last_dt = self._event_last_entry_dt(policy_ticker, date_value)
        if cooldown > 0 and last_dt is not None:
            elapsed = (now - last_dt).total_seconds() / 60.0
            if elapsed < cooldown:
                return False, f"policy_cooldown_{cooldown}m"
        monthly_role = str(row.get("monthly_backfill_role", "")).lower()
        if monthly_role == "fallback":
            month_value = str(row.get("month", str(date_value)[:6]))
            target = self._event_int(row, "backfill_min_month_trades", 18)
            selected_count = self._event_monthly_entry_count(policy_ticker, month_value)
            required = self._required_count_by_date(month_value, date_value, target)
            if selected_count >= required:
                return False, f"monthly_backfill_inactive_count_{selected_count}_required_{required}"
        if policy_ticker == "QQQ" and str(row.get("mtd_source", "")).lower() == "online":
            threshold = _safe_float(row.get("mtd_rescue_trigger_threshold_return", 1.0), 1.0)
            prior_mtd = self._qqq_prior_completed_day_base_mtd(date_value)
            if prior_mtd > threshold:
                return False, f"qqq_mtd_rescue_inactive_prior_mtd_{prior_mtd:.3f}"
        if policy_ticker == "QQQ":
            halted, reason = self._qqq_current_circuit_halted(row, date_value, now)
            if halted:
                return False, reason
        if policy_ticker == "SPXW" and str(row.get("spxw_backfill_role", "")).lower() == "fallback":
            month_value = str(row.get("month", str(date_value)[:6]))
            target = self._event_int(row, "backfill_min_month_trades", 18)
            selected_count = self._event_monthly_entry_count(policy_ticker, month_value)
            required = self._required_count_by_date(month_value, date_value, target)
            if selected_count >= required:
                return False, f"spxw_backfill_inactive_count_{selected_count}_required_{required}"
            action = str(row.get("action", "")).upper()
            if self._spxw_fallback_side_daily_return(date_value, action, now) <= -1.5:
                return False, "spxw_base_side_daily_loss_limit"
        return True, "allowed"

    def _record_event_option_entry(self, row: pd.Series, now: datetime, option: dict) -> None:
        candidate_id = str(row.get("event_candidate_id", ""))
        raw_mtd = row.get("mtd_source", "")
        mtd_source = str(raw_mtd) if pd.notna(raw_mtd) and str(raw_mtd).lower() != "nan" else "base"
        ids = self.event_option_state.get("candidate_ids", [])
        if not isinstance(ids, list):
            ids = []
        if candidate_id:
            ids.append(candidate_id)
        self.event_option_state["candidate_ids"] = ids[-5000:]
        entries = self.event_option_state.get("entries", [])
        if not isinstance(entries, list):
            entries = []
        entries.append(
            {
                "entry_time": now.isoformat(),
                "date": str(row.get("date", row.get("trade_date", now.strftime("%Y%m%d")))),
                "time": str(row.get("time", now.strftime("%H:%M"))),
                "policy_ticker": str(row.get("policy_ticker", "")),
                "bot_ticker": str(row.get("bot_ticker", option.get("ticker", ""))),
                "event_candidate_id": candidate_id,
                "event_option_policy_source": str(row.get("event_option_policy_source", "")),
                "mtd_source": mtd_source,
                "source_variant": str(row.get("source_variant", "")),
                "spxw_backfill_role": str(row.get("spxw_backfill_role", "")),
                "monthly_backfill_role": str(row.get("monthly_backfill_role", "")),
                "backfill_policy_component": str(row.get("backfill_policy_component", "")),
                "source_stream": str(row.get("source_stream", "")),
                "expiry_mode": str(row.get("expiry_mode", "")),
                "event_delta_bucket": str(row.get("event_delta_bucket", "")),
                "action": str(row.get("action", "")),
                "score": _safe_float(row.get("score", 0.0), 0.0),
            }
        )
        self.event_option_state["entries"] = entries
        self._save_event_option_state()

    def _select_event_option_candidate(self, ticker: str, candidates: pd.DataFrame, now: datetime) -> pd.Series | None:
        if candidates.empty or "bot_ticker" not in candidates.columns:
            return None
        work = candidates[candidates["bot_ticker"].astype(str).str.upper().eq(str(ticker).upper())].copy()
        if work.empty:
            return None
        if "time" in work.columns:
            parsed = pd.to_datetime(work["time"].astype(str).str[:5], format="%H:%M", errors="coerce").dt.time
            work = work[(parsed.isna()) | ((parsed >= self.earliest_entry_time) & (parsed <= self.latest_entry_time))].copy()
        if work.empty:
            return None
        if {"date", "time"}.issubset(work.columns):
            latest_key = work.sort_values(["date", "time"], kind="stable").tail(1)[["date", "time"]].iloc[0]
            work = work[
                work["date"].astype(str).eq(str(latest_key["date"]))
                & work["time"].astype(str).eq(str(latest_key["time"]))
            ].copy()
        sort_cols = [col for col in ["source_priority", "score"] if col in work.columns]
        ascending = [True if col == "source_priority" else False for col in sort_cols]
        if sort_cols:
            work = work.sort_values(sort_cols, ascending=ascending, kind="stable")
        feature_id = self._event_feature_row_id(work, ticker)
        for _, row in work.iterrows():
            allowed, reason = self._event_candidate_allowed(row, now)
            if allowed:
                self._record_event_option_candidate_audit(
                    event="candidate_selected",
                    now=now,
                    ticker=ticker,
                    feature_id=feature_id,
                    candidates=work,
                    selected_row=row,
                    reason=reason,
                )
                return row
            self._record_event_option_candidate_audit(
                event="candidate_skipped",
                now=now,
                ticker=ticker,
                feature_id=feature_id,
                selected_row=row,
                reason=reason,
            )
            logging.info("[%s] event-option candidate skipped: %s", ticker, reason)
        self._record_event_option_candidate_audit(
            event="no_allowed_candidate",
            now=now,
            ticker=ticker,
            feature_id=feature_id,
            candidates=work,
            reason="all_candidates_rejected",
        )
        return None

    def _select_event_option_option(self, ticker: str, row: pd.Series, features: pd.DataFrame | None = None) -> dict | None:
        action = _normalize_right(row.get("action", ""))
        if action not in {"CALL", "PUT"}:
            return None
        policy_ticker = str(row.get("policy_ticker", ticker)).upper()
        source = str(row.get("event_option_policy_source", "event_option"))
        raw_mtd = row.get("mtd_source", "")
        mtd_source = str(raw_mtd) if pd.notna(raw_mtd) and str(raw_mtd).lower() != "nan" else "base"
        source_variant = str(row.get("source_variant", "") or "source")
        expiry_mode = str(row.get("expiry_mode", ""))
        bucket = str(row.get("event_delta_bucket", ""))
        selector_policy = f"event_option:{policy_ticker}:{mtd_source}:{source_variant}:{expiry_mode}:{bucket}:{source}"
        return self._select_delta_option(
            ticker,
            right=action,
            delta_target=_safe_float(row.get("event_delta_target", DELTA_TARGET), DELTA_TARGET),
            suffix=str(row.get("option_snapshot_suffix", "0dte") or "0dte"),
            features=features,
            selector_policy=selector_policy,
            selector_score=_safe_float(row.get("score", 0.0), 0.0),
        )

    def _predict_entry_signal(self, ticker: str, features: pd.DataFrame) -> pd.Series | None:
        if self.level_signal is not None:
            pred = self.level_signal.predict_frame(ticker, features)
            if pred is not None:
                return pred
            if not self.allow_signal_model_fallback:
                return None
            logging.info("[%s] no level-stability signal; checking legacy JEPA fallback", ticker)
        if self.signal_model is None:
            return None
        return self.signal_model.predict_frame(features).iloc[-1]

    @staticmethod
    def _is_event_option_position(pos: JepaOptionPosition) -> bool:
        return str(pos.selector_policy).startswith("event_option:")

    @staticmethod
    def _option_snapshot_suffix_for_position(pos: JepaOptionPosition) -> str:
        policy = str(pos.selector_policy)
        if ":front_weekly:" in policy:
            return "weekly"
        if ":zero_dte:" in policy:
            return "0dte"
        return "0dte"

    def _event_option_exit_contract(self) -> tuple[float, float, int, int]:
        payload = self.event_option_policy if isinstance(self.event_option_policy, dict) else {}
        label_contract = {}
        live_contract = {}
        if isinstance(payload.get("validated_label_exit_contract"), dict):
            label_contract = payload["validated_label_exit_contract"]
        if isinstance(payload.get("live_contract"), dict):
            raw_live_exit = payload["live_contract"].get("event_option_exit_contract")
            if isinstance(raw_live_exit, dict):
                live_contract = raw_live_exit
        take_profit = _safe_float(
            live_contract.get("take_profit_pct", label_contract.get("option_take_profit_pct", EVENT_OPTION_TAKE_PROFIT_PCT)),
            EVENT_OPTION_TAKE_PROFIT_PCT,
        )
        stop_loss = -abs(
            _safe_float(
                live_contract.get(
                    "stop_loss_pct",
                    label_contract.get("option_stop_loss_pct", abs(EVENT_OPTION_STOP_LOSS_PCT)),
                ),
                abs(EVENT_OPTION_STOP_LOSS_PCT),
            )
        )
        max_hold = int(
            _safe_float(
                live_contract.get("max_hold_minutes", label_contract.get("horizon_minutes", EVENT_OPTION_MAX_HOLD_MINUTES)),
                EVENT_OPTION_MAX_HOLD_MINUTES,
            )
        )
        min_hold = int(
            _safe_float(
                live_contract.get("min_hold_minutes", label_contract.get("min_hold_minutes", EVENT_OPTION_MIN_HOLD_MINUTES)),
                EVENT_OPTION_MIN_HOLD_MINUTES,
            )
        )
        return take_profit, stop_loss, max_hold, max(0, min_hold)

    def _event_option_exit_contract_name(self) -> str:
        take_profit, stop_loss, max_hold, min_hold = self._event_option_exit_contract()
        trailing_enabled, trail_activation, trail_drawdown = self._event_option_trailing_contract()
        trail = (
            f"_trail{trail_activation:.0%}_{trail_drawdown:.0%}"
            if trailing_enabled
            else "_trailoff"
        )
        return f"event_option_tp{take_profit:.0%}_sl{abs(stop_loss):.0%}{trail}_min{min_hold}m_max{max_hold}m"

    def _event_option_trailing_contract(self) -> tuple[bool, float, float]:
        payload = self.event_option_policy if isinstance(self.event_option_policy, dict) else {}
        live_contract = payload.get("live_contract") if isinstance(payload.get("live_contract"), dict) else {}
        raw_exit = (
            live_contract.get("event_option_exit_contract")
            if isinstance(live_contract.get("event_option_exit_contract"), dict)
            else {}
        )
        trailing_enabled = bool(raw_exit.get("trailing_enabled", False))
        activation = _safe_float(
            raw_exit.get("trailing_activation_pct", live_contract.get("trailing_stop_activate_pct", TRAIL_ACTIVATION_PCT)),
            TRAIL_ACTIVATION_PCT,
        )
        drawdown = _safe_float(
            raw_exit.get("trailing_drawdown_pct", live_contract.get("trailing_stop_giveback_pct", TRAIL_DRAWDOWN_PCT)),
            TRAIL_DRAWDOWN_PCT,
        )
        return trailing_enabled, max(0.0, activation), max(0.0, drawdown)

    def _current_option_premium(self, pos: JepaOptionPosition) -> float:
        suffix = self._option_snapshot_suffix_for_position(pos)
        df = self._latest_option_snapshot(pos.ticker, suffix=suffix)
        if not df.empty and "strike" in df.columns and "right_norm" in df.columns:
            work = df[(df["right_norm"] == pos.right) & (np.isclose(pd.to_numeric(df["strike"], errors="coerce"), pos.strike))]
            if not work.empty:
                price = self._row_price(work.iloc[-1])
                if price > 0:
                    return price
        return self._option_price_from_ohlc(pos.ticker, pos.strike, pos.right, suffix=suffix)

    def _contracts(self, premium: float) -> int:
        cost = premium * CONTRACT_MULTIPLIER
        if cost <= 0:
            return 0
        return max(1, int(RISK_CAPITAL // cost))

    def _record_paper_order_intent(
        self,
        pos: JepaOptionPosition,
        *,
        now: datetime,
        side: str,
        limit_price: float,
        reason: str,
    ) -> None:
        if not self.paper_order_intents:
            return
        side = str(side).upper()
        if side == "BUY_TO_OPEN":
            rounded_limit = _ceil_cent(float(limit_price))
            debit = rounded_limit * CONTRACT_MULTIPLIER * int(pos.contracts)
            credit = 0.0
        elif side == "SELL_TO_CLOSE":
            rounded_limit = max(0.01, _floor_cent(float(limit_price)))
            debit = 0.0
            credit = rounded_limit * CONTRACT_MULTIPLIER * int(pos.contracts)
        else:
            raise ValueError(f"Unsupported paper order side {side}")
        root = OPTIONS_SYMBOLS.get(pos.ticker, pos.ticker)
        right_short = "C" if pos.right == "CALL" else "P"
        order_id = (
            f"{now.strftime('%Y%m%dT%H%M%S')}_{pos.ticker}_{side}_"
            f"{pos.expiration}_{pos.strike:.2f}{right_short}"
        )
        payload = {
            "schema_version": PAPER_ORDER_SCHEMA_VERSION,
            "order_id": order_id,
            "generated_at": now.isoformat(),
            "mode": "paper_order_intent",
            "broker_submission": False,
            "paper_status": "paper_filled_by_tracker",
            "reason": str(reason),
            "ticker": pos.ticker,
            "option_contract": {
                "root": root,
                "expiration": _format_expiration(pos.expiration),
                "right": pos.right,
                "strike": float(pos.strike),
            },
            "order": {
                "side": side,
                "quantity": int(pos.contracts),
                "order_type": "LIMIT",
                "limit_price": float(rounded_limit),
                "time_in_force": "DAY",
                "asset_class": "OPTION",
            },
            "risk": {
                "risk_capital": RISK_CAPITAL,
                "contract_multiplier": CONTRACT_MULTIPLIER,
                "max_debit": float(debit),
                "estimated_credit": float(credit),
            },
            "position": {
                "entry_time": pos.entry_time,
                "entry_premium": float(pos.entry_premium),
                "raw_entry_premium": float(pos.raw_entry_premium),
                "entry_spread_pct": float(pos.entry_spread_pct),
                "entry_spot": float(pos.entry_spot),
                "delta": float(pos.delta),
                "selector_policy": pos.selector_policy,
            },
            "not_covered": [
                "broker API acceptance",
                "exchange queue position",
                "partial fills",
                "live order acknowledgement latency",
            ],
        }
        self.trades_dir.mkdir(parents=True, exist_ok=True)
        with self.paper_order_intents_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
        logging.info("[%s] PAPER ORDER %s qty=%d limit=%.2f reason=%s", pos.ticker, side, pos.contracts, rounded_limit, reason)

    @staticmethod
    def _entry_spread_pct(abs_delta: float, features: pd.DataFrame) -> float:
        abs_delta = abs(float(abs_delta))
        if abs_delta < 0.30:
            spread = 0.03
        elif abs_delta > 0.60:
            spread = 0.01
        else:
            spread = 0.015
        gamma_speed = 0.0
        if not features.empty and "gamma_speed" in features.columns:
            gamma_speed = _safe_float(features.iloc[-1].get("gamma_speed", 0.0), 0.0)
        return float(spread) * (1.0 + 0.5 * abs(gamma_speed))

    def _cooldown_active(self, ticker: str, now: datetime) -> bool:
        value = self.cooldowns.get(ticker)
        if not value:
            return False
        try:
            last = datetime.fromisoformat(value)
        except Exception:
            return False
        elapsed = (now - last).total_seconds() / 60.0
        return elapsed < COOLDOWN_MINUTES

    def _record_cooldown(self, ticker: str, now: datetime) -> None:
        self.cooldowns[ticker] = now.isoformat()
        self._save_cooldowns()

    def _normalize_trade_log_file(self) -> None:
        if not self.trade_log_path.exists():
            return
        try:
            with self.trade_log_path.open(newline="", encoding="utf-8") as handle:
                current_header = next(csv.reader(handle), [])
        except Exception:
            logging.exception("Could not inspect trade log header")
            return
        if [str(col).strip() for col in current_header] == TRADE_LOG_FIELDS:
            return
        frame = self._read_trade_log_csv(self.trade_log_path)
        backup = self.trade_log_path.with_name(
            f"{self.trade_log_path.stem}.schema_mismatch_{_now_et().strftime('%Y%m%dT%H%M%S')}.csv"
        )
        try:
            self.trade_log_path.replace(backup)
            with self.trade_log_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=TRADE_LOG_FIELDS, extrasaction="ignore")
                writer.writeheader()
                for record in frame.to_dict("records"):
                    writer.writerow({field: record.get(field, "") for field in TRADE_LOG_FIELDS})
            logging.warning("Normalized mixed-schema trade log %s; backup=%s", self.trade_log_path, backup)
        except Exception:
            logging.exception("Could not normalize trade log %s", self.trade_log_path)

    def _append_trade_log(self, row: dict) -> None:
        self.trades_dir.mkdir(parents=True, exist_ok=True)
        self._normalize_trade_log_file()
        exists = self.trade_log_path.exists()
        with self.trade_log_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=TRADE_LOG_FIELDS, extrasaction="ignore")
            if not exists:
                writer.writeheader()
            writer.writerow({field: row.get(field, "") for field in TRADE_LOG_FIELDS})

    def _discord_open(self, pos: JepaOptionPosition) -> None:
        right_short = "C" if pos.right == "CALL" else "P"
        exp_fmt = _format_expiration_for_tracker(pos.expiration)
        tracker = f"BTO {pos.ticker} {exp_fmt} {pos.strike:.0f}{right_short} @ M"
        _send_discord(tracker)
        if self._is_event_option_position(pos):
            tp, sl, max_hold, min_hold = self._event_option_exit_contract()
            trailing_enabled, trail_activation, trail_drawdown = self._event_option_trailing_contract()
            trail_line = (
                f" trail={trail_activation:.0%}/{trail_drawdown:.0%}"
                if trailing_enabled
                else ""
            )
            exit_line = f"stop={sl:.0%}{trail_line} tp={tp:.0%} min_hold={min_hold}m max_hold={max_hold}m"
        else:
            exit_line = (
                f"stop={HARD_STOP_PCT:.0%} trail={TRAIL_ACTIVATION_PCT:.0%}/"
                f"{TRAIL_DRAWDOWN_PCT:.0%} tp={TAKE_PROFIT_PCT:.0%} max_hold={MAX_HOLD_MINUTES}m"
            )
        _send_discord(
            f"**[BOT] OPEN {pos.direction} {pos.ticker} {pos.strike:.0f}{right_short}**\n"
            f"prob_up={pos.jepa_prob_up:.3f} conf={pos.confidence:.0%} "
            f"delta={pos.delta:.2f} premium=${pos.entry_premium:.2f} contracts={pos.contracts}\n"
            f"{exit_line} entry_window={self.earliest_entry_time.strftime('%H:%M')}-{self.latest_entry_time.strftime('%H:%M')}\n"
            f"policy={pos.selector_policy}",
            ping=False,
        )

    def _discord_close(self, pos: JepaOptionPosition, pnl_pct: float, pnl_dollars: float, hold_min: float, reason: str) -> None:
        right_short = "C" if pos.right == "CALL" else "P"
        exp_fmt = _format_expiration_for_tracker(pos.expiration)
        tracker = f"STC {pos.ticker} {exp_fmt} {pos.strike:.0f}{right_short} @ M"
        _send_discord(tracker)
        _send_discord(
            f"**[BOT] CLOSE {pos.ticker} {pos.strike:.0f}{right_short} {reason}**\n"
            f"pnl={pnl_pct:+.1%} (${pnl_dollars:+.2f}) hold={hold_min:.0f}m",
            ping=False,
        )

    def _close_position(self, ticker: str, premium: float, reason: str, now: datetime) -> None:
        pos = self.positions.pop(ticker)
        pnl_pct = premium / max(pos.entry_premium, 1e-9) - 1.0
        pnl_dollars = pnl_pct * pos.entry_premium * CONTRACT_MULTIPLIER * pos.contracts
        hold_min = (now - pos.entry_dt).total_seconds() / 60.0
        self._save_positions()
        self._append_trade_log(
            {
                "date": now.strftime("%Y%m%d"),
                "entry_time": pos.entry_dt.strftime("%H:%M"),
                "exit_time": now.strftime("%H:%M"),
                "ticker": ticker,
                "direction": pos.direction,
                "right": pos.right,
                "strike": pos.strike,
                "delta": pos.delta,
                "entry_premium": pos.entry_premium,
                "exit_premium": premium,
                "contracts": pos.contracts,
                "pnl_pct": pnl_pct,
                "pnl_dollars": pnl_dollars,
                "hold_minutes": hold_min,
                "exit_reason": reason,
                "peak_pnl_pct": pos.peak_pnl_pct,
                "trough_pnl_pct": pos.trough_pnl_pct,
                "option_snapshot_suffix": self._option_snapshot_suffix_for_position(pos),
                "exit_contract": self._event_option_exit_contract_name()
                if self._is_event_option_position(pos)
                else "legacy_hard60_trail50_25_tp1000_max180",
                "source_model": pos.selector_policy,
            }
        )
        logging.info("[%s] CLOSE %s pnl=%+.1f%% $%+.2f hold=%.0fm", ticker, reason, pnl_pct * 100.0, pnl_dollars, hold_min)
        self._record_paper_order_intent(pos, now=now, side="SELL_TO_CLOSE", limit_price=premium, reason=reason)
        self._discord_close(pos, pnl_pct, pnl_dollars, hold_min, reason)

    def _check_exit(self, ticker: str, now: datetime) -> None:
        pos = self.positions.get(ticker)
        if pos is None:
            return
        premium = self._current_option_premium(pos)
        if premium <= 0:
            logging.warning("[%s] open position but current premium unavailable", ticker)
            return
        pnl_pct = premium / max(pos.entry_premium, 1e-9) - 1.0
        pos.peak_pnl_pct = max(pos.peak_pnl_pct, pnl_pct)
        pos.trough_pnl_pct = min(pos.trough_pnl_pct, pnl_pct)
        hold_min = (now - pos.entry_dt).total_seconds() / 60.0
        self._save_positions()

        if self._is_event_option_position(pos):
            take_profit, stop_loss, max_hold, min_hold = self._event_option_exit_contract()
            trailing_enabled, trail_activation, trail_drawdown = self._event_option_trailing_contract()
            if hold_min >= max_hold:
                self._close_position(ticker, premium, f"event_option_max_hold_{max_hold}m", now)
            elif now.time() >= EOD_CLEANUP_TIME:
                self._close_position(ticker, premium, "event_option_eod_cleanup", now)
            elif hold_min < min_hold:
                logging.info(
                    "[%s] HOLD event-option min_hold_active pnl=%+.1f%% peak=%+.1f%% trough=%+.1f%% hold=%.0fm min_hold=%dm",
                    ticker,
                    pnl_pct * 100.0,
                    pos.peak_pnl_pct * 100.0,
                    pos.trough_pnl_pct * 100.0,
                    hold_min,
                    min_hold,
                )
            elif pnl_pct <= stop_loss:
                self._close_position(ticker, premium, f"event_option_stop_loss_{abs(stop_loss):.0%}", now)
            elif (
                trailing_enabled
                and pos.peak_pnl_pct >= trail_activation
                and pnl_pct <= pos.peak_pnl_pct - trail_drawdown
            ):
                self._close_position(
                    ticker,
                    premium,
                    f"event_option_trail_stop_{trail_activation:.0%}_{trail_drawdown:.0%}_giveback",
                    now,
                )
            elif pnl_pct >= take_profit:
                self._close_position(ticker, premium, f"event_option_take_profit_{take_profit:.0%}", now)
            else:
                logging.info(
                    "[%s] HOLD event-option pnl=%+.1f%% peak=%+.1f%% trough=%+.1f%% hold=%.0fm min_hold=%dm",
                    ticker,
                    pnl_pct * 100.0,
                    pos.peak_pnl_pct * 100.0,
                    pos.trough_pnl_pct * 100.0,
                    hold_min,
                    min_hold,
                )
        elif pnl_pct <= HARD_STOP_PCT:
            self._close_position(ticker, premium, "hard_stop_-60pct", now)
        elif pos.peak_pnl_pct >= TRAIL_ACTIVATION_PCT and pnl_pct <= pos.peak_pnl_pct - TRAIL_DRAWDOWN_PCT:
            self._close_position(ticker, premium, "trail_stop_50pct_25pct_giveback", now)
        elif pnl_pct >= TAKE_PROFIT_PCT:
            self._close_position(ticker, premium, "take_profit_1000pct", now)
        elif hold_min >= MAX_HOLD_MINUTES:
            self._close_position(ticker, premium, "max_hold_180m", now)
        elif now.time() >= EOD_CLEANUP_TIME:
            self._close_position(ticker, premium, "eod_cleanup", now)
        else:
            giveback = pos.peak_pnl_pct - pnl_pct
            logging.info(
                "[%s] HOLD option pnl=%+.1f%% peak=%+.1f%% giveback=%.1f%% hold=%.0fm",
                ticker,
                pnl_pct * 100.0,
                pos.peak_pnl_pct * 100.0,
                giveback * 100.0,
                hold_min,
            )

    def _check_event_option_entry(self, ticker: str, now: datetime) -> None:
        if now.time() < self.earliest_entry_time:
            logging.info(
                "[%s] before event-option entry window %s-%s",
                ticker,
                self.earliest_entry_time.strftime("%H:%M"),
                self.latest_entry_time.strftime("%H:%M"),
            )
            return
        if now.time() > self.latest_entry_time:
            logging.info(
                "[%s] past event-option entry window %s-%s",
                ticker,
                self.earliest_entry_time.strftime("%H:%M"),
                self.latest_entry_time.strftime("%H:%M"),
            )
            return
        candidates, issues = self._score_event_option_candidates()
        for issue in issues[:5]:
            logging.info("[%s] event-option scorer issue: %s", ticker, issue)
        feature_id = self._event_feature_row_id(candidates, ticker)
        eval_key = f"event:{ticker}"
        if feature_id and self.evaluated_feature_timestamps.get(eval_key) == feature_id:
            return
        if not feature_id:
            self._mark_feature_evaluated(eval_key, now.isoformat(timespec="minutes"))
            return
        row = self._select_event_option_candidate(ticker, candidates, now)
        if row is None:
            self._record_event_option_candidate_audit(
                event="no_entry_candidate",
                now=now,
                ticker=ticker,
                feature_id=feature_id,
                candidates=candidates,
                reason="no_candidate_after_filters",
            )
            logging.info("[%s] no event-option entry candidate", ticker)
            self._mark_feature_evaluated(eval_key, feature_id)
            return
        option = self._select_event_option_option(ticker, row)
        if option is None:
            self._record_event_option_candidate_audit(
                event="entry_rejected",
                now=now,
                ticker=ticker,
                feature_id=feature_id,
                selected_row=row,
                reason="no_matching_option_contract",
            )
            logging.warning("[%s] event-option candidate but no matching option contract available", ticker)
            self._mark_feature_evaluated(eval_key, feature_id)
            return
        raw_entry_premium = float(option.get("raw_entry_premium", option["premium"]))
        entry_spread_pct = float(option.get("entry_spread_pct", self._entry_spread_pct(abs(float(option["delta"])), pd.DataFrame())))
        entry_premium = float(option.get("entry_premium", raw_entry_premium * (1.0 + entry_spread_pct)))
        contracts = self._contracts(entry_premium)
        if contracts <= 0:
            self._record_event_option_candidate_audit(
                event="entry_rejected",
                now=now,
                ticker=ticker,
                feature_id=feature_id,
                selected_row=row,
                reason="premium_too_high_or_invalid",
            )
            logging.warning("[%s] event-option candidate but premium too high/invalid", ticker)
            self._mark_feature_evaluated(eval_key, feature_id)
            return
        direction = "LONG" if str(row.get("action", "")).upper() == "CALL" else "SHORT"
        spot = self._latest_spot(ticker)
        score = _safe_float(row.get("score", 0.0), 0.0)
        pred_call = _safe_float(row.get("pred_call_return", 0.5), 0.5)
        pred_put = _safe_float(row.get("pred_put_return", 0.5), 0.5)
        pos = JepaOptionPosition(
            ticker=ticker,
            direction=direction,
            right=option["right"],
            strike=float(option["strike"]),
            delta=float(option["delta"]),
            expiration=str(option["expiration"]),
            entry_time=now.isoformat(),
            entry_spot=float(spot),
            entry_premium=float(entry_premium),
            raw_entry_premium=float(raw_entry_premium),
            entry_spread_pct=float(entry_spread_pct),
            contracts=int(contracts),
            confidence=max(0.0, min(1.0, abs(score))),
            jepa_prob_up=pred_call if direction == "LONG" else 1.0 - pred_put,
            long_threshold=pred_call,
            short_threshold=pred_put,
            selector_policy=str(option.get("selector_policy", FIXED_POLICY_NAME)),
        )
        self.positions[ticker] = pos
        self._record_event_option_entry(row, now, option)
        self._save_positions()
        self._mark_feature_evaluated(eval_key, feature_id)
        logging.info(
            "[%s] OPEN event-option %s strike=%.0f delta=%.2f expiry=%s premium=%.2f contracts=%d score=%.4f policy=%s",
            ticker,
            direction,
            pos.strike,
            pos.delta,
            str(row.get("expiry_mode", "")),
            pos.entry_premium,
            pos.contracts,
            score,
            pos.selector_policy,
        )
        self._record_paper_order_intent(pos, now=now, side="BUY_TO_OPEN", limit_price=pos.entry_premium, reason="event_option_entry")
        self._discord_open(pos)
        time.sleep(3)

    def _check_entry(self, ticker: str, now: datetime) -> None:
        if ticker in self.positions:
            return
        if now.time() >= EOD_CLEANUP_TIME:
            return
        if self.event_option_scorer_enabled:
            self._check_event_option_entry(ticker, now)
            return
        if self._cooldown_active(ticker, now):
            logging.info("[%s] cooldown active", ticker)
            return

        features = self._latest_feature_row(ticker)
        if features.empty:
            return
        feature_id = self._feature_row_id(features)
        if self.evaluated_feature_timestamps.get(ticker) == feature_id:
            return
        feature_time = self._feature_entry_time(features)
        if feature_time is not None and feature_time > self.latest_entry_time:
            logging.info("[%s] feature row %s past live entry window", ticker, feature_time.strftime("%H:%M"))
            self._mark_feature_evaluated(ticker, feature_id)
            return
        pred = self._predict_entry_signal(ticker, features)
        if pred is None:
            logging.info("[%s] no production entry signal", ticker)
            self._mark_feature_evaluated(ticker, feature_id)
            return
        direction_int = int(pred.get("jepa180_direction", 0))
        if direction_int == 0:
            logging.info("[%s] no entry signal prob_up=%.3f", ticker, _safe_float(pred.get("jepa180_prob_up", 0.5)))
            self._mark_feature_evaluated(ticker, feature_id)
            return
        direction = "LONG" if direction_int > 0 else "SHORT"
        option = None
        legacy_selector_mode = self.structural_selector is None
        if self.structural_selector is not None:
            option = self._select_structural_profile_option(ticker, direction, features)
            if option is None and not self.allow_selector_fallback:
                logging.info("[%s] JEPA signal skipped by structural option profile", ticker)
                self._mark_feature_evaluated(ticker, feature_id)
                return
        if option is None:
            option = self._select_option_value_option(ticker, direction, features)
        if option is None and (legacy_selector_mode or self.allow_selector_fallback):
            option = self._select_fixed_delta_option(ticker, direction)
        if option is None:
            logging.warning("[%s] JEPA signal but no valid 0DTE option candidate available", ticker)
            self._mark_feature_evaluated(ticker, feature_id)
            return
        raw_entry_premium = float(option.get("raw_entry_premium", option["premium"]))
        entry_spread_pct = float(
            option.get("entry_spread_pct", self._entry_spread_pct(abs(float(option["delta"])), features))
        )
        entry_premium = float(option.get("entry_premium", raw_entry_premium * (1.0 + entry_spread_pct)))
        contracts = self._contracts(entry_premium)
        if contracts <= 0:
            logging.warning("[%s] JEPA signal but premium too high/invalid", ticker)
            return
        spot = self._latest_spot(ticker)
        pos = JepaOptionPosition(
            ticker=ticker,
            direction=direction,
            right=option["right"],
            strike=float(option["strike"]),
            delta=float(option["delta"]),
            expiration=str(option["expiration"]),
            entry_time=now.isoformat(),
            entry_spot=float(spot),
            entry_premium=float(entry_premium),
            raw_entry_premium=float(raw_entry_premium),
            entry_spread_pct=float(entry_spread_pct),
            contracts=int(contracts),
            confidence=_safe_float(pred.get("jepa180_confidence", 0.0)),
            jepa_prob_up=_safe_float(pred.get("jepa180_prob_up", 0.5)),
            long_threshold=_safe_float(pred.get("jepa180_long_threshold", 0.0)),
            short_threshold=_safe_float(pred.get("jepa180_short_threshold", 0.0)),
            selector_policy=str(option.get("selector_policy", FIXED_POLICY_NAME)),
        )
        self.positions[ticker] = pos
        self._record_cooldown(ticker, now)
        self._save_positions()
        self._mark_feature_evaluated(ticker, feature_id)
        logging.info(
            "[%s] OPEN %s strike=%.0f delta=%.2f premium=%.2f contracts=%d prob_up=%.3f conf=%.0f%% policy=%s",
            ticker,
            direction,
            pos.strike,
            pos.delta,
            pos.entry_premium,
            pos.contracts,
            pos.jepa_prob_up,
            pos.confidence * 100.0,
            pos.selector_policy,
        )
        self._record_paper_order_intent(pos, now=now, side="BUY_TO_OPEN", limit_price=pos.entry_premium, reason="legacy_entry")
        self._discord_open(pos)
        time.sleep(3)

    def run_once(self) -> None:
        now = _now_et()
        for ticker in self.tickers:
            self._check_exit(ticker, now)
        for ticker in self.tickers:
            self._check_entry(ticker, now)

    def is_market_hours(self) -> bool:
        now = _now_et()
        return now.replace(hour=9, minute=30, second=0, microsecond=0) <= now <= now.replace(
            hour=16, minute=0, second=0, microsecond=0
        )

    def run(self, force: bool = False) -> None:
        legacy_signal = "enabled" if self.signal_model is not None else "disabled"
        event_policy_name = (
            str(self.event_option_policy.get("policy", "none"))
            if isinstance(self.event_option_policy, dict)
            else "none"
        )
        event_component_status = (
            f"{self.event_option_components.status}:{len(self.event_option_components.components)}"
            if self.event_option_components is not None
            else "none"
        )
        event_exit = "none"
        if isinstance(self.event_option_policy, dict):
            tp, sl, max_hold, min_hold = self._event_option_exit_contract()
            trailing_enabled, trail_activation, trail_drawdown = self._event_option_trailing_contract()
            trail = (
                f"/trail={trail_activation:.0%}/{trail_drawdown:.0%}"
                if trailing_enabled
                else "/trail=off"
            )
            event_exit = f"stop={sl:.0%}/tp={tp:.0%}{trail}/min_hold={min_hold}m/max_hold={max_hold}m"
        logging.info(
            "Starting JEPA live bot signal=%s selector=%s event_scorer=%s event_policy=%s event_components=%s event_exit=%s legacy_signal=%s rt_data=%s risk=%.0f entry_window=%s-%s legacy_stop=%.0f%% trail=%.0f%%/%.0f%% legacy_tp=%.0f%%",
            (
                self.level_signal.policy
                if self.level_signal is not None
                else f"legacy:{MODEL_MODE}" if self.signal_model is not None else "none"
            ),
            (
                self.structural_selector.policy
                if self.structural_selector is not None
                else OPTION_VALUE_POLICY_NAME if self.option_value_selector is not None else FIXED_POLICY_NAME
            ),
            "enabled" if self.event_option_scorer_enabled else "disabled",
            event_policy_name,
            event_component_status,
            event_exit,
            legacy_signal,
            self.rt_data_dir,
            RISK_CAPITAL,
            self.earliest_entry_time.strftime("%H:%M"),
            self.latest_entry_time.strftime("%H:%M"),
            HARD_STOP_PCT * 100.0,
            TRAIL_ACTIVATION_PCT * 100.0,
            TRAIL_DRAWDOWN_PCT * 100.0,
            TAKE_PROFIT_PCT * 100.0,
        )
        if self.paper_order_intents:
            logging.info("Paper order intents enabled: writing %s; no broker submission is performed", self.paper_order_intents_path)
        while True:
            if force or self.is_market_hours() or self.positions:
                self.run_once()
            else:
                logging.info("Outside market hours; sleeping")
            if self.dry_run:
                break
            time.sleep(LOOP_INTERVAL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Live level-stability + structural option bot")
    parser.add_argument("--model-dir", default=str(DEFAULT_SIGNAL_MODEL_DIR))
    parser.add_argument("--level-signal-path", default=str(DEFAULT_LEVEL_SIGNAL_PATH))
    parser.add_argument("--disable-level-signal", action="store_true", help="Disable production level-stability signal")
    parser.add_argument("--require-level-signal", action="store_true", help="Fail startup if level-stability signal is missing")
    parser.add_argument("--allow-signal-model-fallback", action="store_true", help="Allow legacy JEPA 180m signal fallback")
    parser.add_argument("--option-value-model-dir", default=str(DEFAULT_OPTION_VALUE_MODEL_DIR))
    parser.add_argument("--option-value-device", default="auto", help="OptionValue device: auto, cpu, cuda")
    parser.add_argument("--disable-option-value", action="store_true", help="Use fixed 0.70 delta even if OptionValue is available")
    parser.add_argument("--structural-profile-path", default=str(DEFAULT_STRUCTURAL_PROFILE_PATH))
    parser.add_argument("--disable-structural-profile", action="store_true", help="Disable production structural option profiles")
    parser.add_argument("--require-structural-profile", action="store_true", help="Fail startup if structural option profiles are missing")
    parser.add_argument("--event-option-policy-path", default=str(DEFAULT_EVENT_OPTION_POLICY_PATH))
    parser.add_argument("--disable-event-option-policy", action="store_true", help="Disable production event-option policy metadata")
    parser.add_argument("--require-event-option-policy", action="store_true", help="Fail startup if event-option production policy is missing")
    parser.add_argument("--event-option-component-registry-path", default=str(DEFAULT_EVENT_OPTION_COMPONENT_REGISTRY_PATH))
    parser.add_argument(
        "--disable-event-option-component-registry",
        action="store_true",
        help="Disable event-option component registry validation",
    )
    parser.add_argument(
        "--require-event-option-component-registry",
        action="store_true",
        help="Fail startup if event-option component registry is missing or invalid",
    )
    parser.add_argument(
        "--require-event-option-live-ready",
        action="store_true",
        help="Fail startup if the event-option policy/registry are still marked research-only or runtime-incomplete",
    )
    parser.add_argument(
        "--enable-event-option-scorer",
        action="store_true",
        help="Use exported event-option component scorer for entries instead of level-stability/structural entries",
    )
    parser.add_argument(
        "--strict-event-option-features",
        action="store_true",
        help="Fail event-option scoring when any registered live feature is missing",
    )
    parser.add_argument("--allow-selector-fallback", action="store_true", help="Allow OptionValue/fixed fallback when a structural profile skips a signal")
    parser.add_argument("--rt-data-dir", default=str(DEFAULT_RT_DATA_DIR))
    parser.add_argument("--trades-dir", default=str(DEFAULT_TRADES_DIR))
    parser.add_argument("--tickers", nargs="+", default=TICKERS)
    parser.add_argument(
        "--paper-order-intents",
        action="store_true",
        help="Write broker-shaped paper order intents to trades_dir without submitting broker orders",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--force", action="store_true", help="Run outside market hours for diagnostics")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    trades_dir = Path(args.trades_dir)
    trades_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(trades_dir / "tradingbot_jepa.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    bot = JepaFixedDeltaBot(
        model_dir=Path(args.model_dir),
        level_signal_path=None if args.disable_level_signal else Path(args.level_signal_path),
        require_level_signal=bool(args.require_level_signal),
        allow_signal_model_fallback=bool(args.allow_signal_model_fallback),
        option_value_model_dir=None if args.disable_option_value else Path(args.option_value_model_dir),
        option_value_device=args.option_value_device,
        structural_profile_path=None if args.disable_structural_profile else Path(args.structural_profile_path),
        require_structural_profile=bool(args.require_structural_profile),
        event_option_policy_path=None if args.disable_event_option_policy else Path(args.event_option_policy_path),
        require_event_option_policy=bool(args.require_event_option_policy),
        event_option_component_registry_path=(
            None
            if args.disable_event_option_component_registry
            else Path(args.event_option_component_registry_path)
        ),
        require_event_option_component_registry=bool(args.require_event_option_component_registry),
        require_event_option_live_ready=bool(args.require_event_option_live_ready),
        enable_event_option_scorer=bool(args.enable_event_option_scorer),
        strict_event_option_features=bool(args.strict_event_option_features),
        allow_selector_fallback=bool(args.allow_selector_fallback),
        rt_data_dir=Path(args.rt_data_dir),
        trades_dir=trades_dir,
        tickers=args.tickers,
        dry_run=args.dry_run,
        paper_order_intents=bool(args.paper_order_intents),
    )
    bot.run(force=args.force)


if __name__ == "__main__":
    main()

