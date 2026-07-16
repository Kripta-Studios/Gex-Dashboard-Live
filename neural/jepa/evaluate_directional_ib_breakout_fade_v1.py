#!/usr/bin/env python3
"""Frozen causal Initial-Balance breakout/fade walk-forward experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from neural.jepa import evaluate_directional_breadth_transmission_v1 as breadth
from neural.jepa import evaluate_directional_semantic_jepa_v1 as base


PREDECLARATION = (
    base.REPO_ROOT
    / "research_papers/JEPA/DIRECTIONAL_IB_BREAKOUT_FADE_V1_PREDECLARATION.md"
)
DEFAULT_DEVELOPMENT_OUTPUT = (
    base.REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "directional_ib_breakout_fade_v1_development_202208_202512"
)
DEFAULT_EVALUATION_OUTPUT = (
    base.REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "directional_ib_breakout_fade_v1_evaluation_202601_20260715"
)

TARGETS = breadth.TARGETS
ALL_TICKERS = breadth.ALL_TICKERS
REPORT_TICKER = breadth.REPORT_TICKER
PROFILE_ID = "IB_MODE_LGBM"
SEED = 20260716
COST_BPS = 1.0
MIN_TARGET_HOLD_MINUTES = 30
BREAKOUT_STOP_R = 0.236
BREAKOUT_TARGET_R = 0.618
FADE_STOP_R = 0.272
FADE_TARGET_R = 0.500

WINDOWS = {
    "W1": {
        "signal_start": "10:30",
        "signal_end": "12:28",
        "force_exit": "12:59",
    },
    "W2": {
        "signal_start": "13:00",
        "signal_end": "15:28",
        "force_exit": "15:59",
    },
}


def _timestamp(day: str, clock: str) -> pd.Timestamp:
    return pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {clock}")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _clock_range(day: str, start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(_timestamp(day, start), _timestamp(day, end), freq="min")


def _ib_state(frame: pd.DataFrame, day: str) -> dict[str, float]:
    ib = frame.loc[_timestamp(day, "09:30") : _timestamp(day, "10:29")]
    if len(ib) != 60:
        raise AssertionError(f"{day}: Initial Balance is not exactly 60 bars")
    high = float(ib["high"].max())
    low = float(ib["low"].min())
    open_price = float(ib["open"].iloc[0])
    close = float(ib["close"].iloc[-1])
    width = high - low
    if not (low > 0.0 and width > 0.0):
        raise AssertionError(f"{day}: invalid Initial Balance")
    return {
        "open": open_price,
        "high": high,
        "low": low,
        "mid": (high + low) / 2.0,
        "close": close,
        "width": width,
        "width_bps": width / close * 10000.0,
        "return_bps": math.log(close / open_price) * 10000.0,
        "tick_median": float(np.median(ib["tick_count"].to_numpy(dtype=np.float64))),
    }


def find_event(
    frame: pd.DataFrame,
    day: str,
    window_id: str,
    state: dict[str, float],
) -> tuple[pd.Timestamp, int] | None:
    contract = WINDOWS[window_id]
    for timestamp in _clock_range(day, contract["signal_start"], contract["signal_end"]):
        close = float(frame.loc[timestamp, "close"])
        if close > state["high"]:
            return timestamp, 1
        if close < state["low"]:
            return timestamp, -1
    return None


def _return_bps(close: np.ndarray, position: int, horizon: int) -> float:
    if position < horizon:
        raise AssertionError("insufficient completed history")
    return float(math.log(close[position] / close[position - horizon]) * 10000.0)


def _rv_bps(close: np.ndarray, position: int, horizon: int) -> float:
    if position < horizon:
        raise AssertionError("insufficient completed history")
    changes = np.diff(np.log(close[position - horizon : position + 1])) * 10000.0
    return float(np.sqrt(np.square(changes).sum()))


def build_features(
    frames: dict[str, pd.DataFrame],
    states: dict[str, dict[str, float]],
    target: str,
    decision: pd.Timestamp,
    trigger: int,
    window_id: str,
) -> tuple[dict[str, float], list[str]]:
    values: dict[str, float] = {
        "trigger_up": float(trigger > 0),
        "window_w2": float(window_id == "W2"),
        "decision_minute": float((decision.hour * 60 + decision.minute - 570) / 390.0),
        "dow_sin": float(math.sin(2.0 * math.pi * decision.dayofweek / 5.0)),
        "dow_cos": float(math.cos(2.0 * math.pi * decision.dayofweek / 5.0)),
    }
    aligned_1m: list[float] = []
    aligned_5m: list[float] = []
    aligned_15m: list[float] = []
    aligned_ib: list[float] = []
    above: list[float] = []
    below: list[float] = []

    for ticker in ALL_TICKERS:
        frame = frames[ticker]
        state = states[ticker]
        position = int(frame.index.get_loc(decision))
        close_array = frame["close"].to_numpy(dtype=np.float64)
        current = float(close_array[position])
        prefix = ticker.lower()
        returns = {h: _return_bps(close_array, position, h) for h in (1, 5, 15, 30)}
        aligned = {h: float(trigger * returns[h]) for h in returns}
        for horizon in (1, 5, 15, 30):
            values[f"{prefix}_aligned_ret_{horizon}m"] = aligned[horizon]
        values[f"{prefix}_aligned_ib_ret"] = float(trigger * state["return_bps"])
        values[f"{prefix}_ib_width_bps"] = float(state["width_bps"])
        values[f"{prefix}_aligned_since_ib"] = float(
            trigger * math.log(current / state["close"]) * 10000.0
        )
        location = (current - state["low"]) / state["width"]
        values[f"{prefix}_aligned_ib_location"] = float(
            location if trigger > 0 else 1.0 - location
        )
        aligned_1m.append(aligned[1])
        aligned_5m.append(aligned[5])
        aligned_15m.append(aligned[15])
        aligned_ib.append(trigger * state["return_bps"])
        above.append(float(current > state["high"]))
        below.append(float(current < state["low"]))

    target_frame = frames[target]
    target_state = states[target]
    target_position = int(target_frame.index.get_loc(decision))
    target_close = float(target_frame.iloc[target_position]["close"])
    boundary = target_state["high"] if trigger > 0 else target_state["low"]
    values.update(
        {
            "target_break_excess_r": float(trigger * (target_close - boundary) / target_state["width"]),
            "target_rv_5m": _rv_bps(
                target_frame["close"].to_numpy(dtype=np.float64), target_position, 5
            ),
            "target_rv_15m": _rv_bps(
                target_frame["close"].to_numpy(dtype=np.float64), target_position, 15
            ),
            "target_rv_30m": _rv_bps(
                target_frame["close"].to_numpy(dtype=np.float64), target_position, 30
            ),
            "target_tick_ratio_ib": float(
                math.log1p(float(target_frame.iloc[target_position]["tick_count"]))
                - math.log1p(target_state["tick_median"])
            ),
            "panel_aligned_ret_1m_mean": float(np.mean(aligned_1m)),
            "panel_aligned_ret_5m_mean": float(np.mean(aligned_5m)),
            "panel_aligned_ret_15m_mean": float(np.mean(aligned_15m)),
            "panel_aligned_ib_mean": float(np.mean(aligned_ib)),
            "panel_aligned_positive_1m": float(np.mean(np.asarray(aligned_1m) > 0.0)),
            "panel_aligned_positive_5m": float(np.mean(np.asarray(aligned_5m) > 0.0)),
            "panel_aligned_positive_15m": float(np.mean(np.asarray(aligned_15m) > 0.0)),
            "panel_break_confirm_fraction": float(
                np.mean(above) if trigger > 0 else np.mean(below)
            ),
            "panel_opposite_break_fraction": float(
                np.mean(below) if trigger > 0 else np.mean(above)
            ),
        }
    )
    feature_names = list(values)
    array = np.asarray([values[name] for name in feature_names], dtype=np.float64)
    if not np.isfinite(array).all():
        raise AssertionError("IB event features contain non-finite values")
    return values, feature_names


def simulate_trade(
    frame: pd.DataFrame,
    entry_timestamp: pd.Timestamp,
    force_timestamp: pd.Timestamp,
    side: int,
    ib_width: float,
    mode: str,
) -> dict[str, object]:
    if mode == "BREAKOUT":
        stop_multiple, target_multiple = BREAKOUT_STOP_R, BREAKOUT_TARGET_R
    elif mode == "FADE":
        stop_multiple, target_multiple = FADE_STOP_R, FADE_TARGET_R
    else:
        raise ValueError(f"unknown IB mode: {mode}")
    entry = float(frame.loc[entry_timestamp, "open"])
    stop = entry - side * stop_multiple * ib_width
    target = entry + side * target_multiple * ib_width
    exit_price = float(frame.loc[force_timestamp, "close"])
    exit_timestamp = force_timestamp
    exit_reason = "FORCE"

    for timestamp, bar in frame.loc[entry_timestamp:force_timestamp].iterrows():
        elapsed = int((timestamp - entry_timestamp).total_seconds() // 60)
        open_price = float(bar["open"])
        high = float(bar["high"])
        low = float(bar["low"])
        if side > 0:
            if open_price <= stop:
                exit_price, exit_timestamp, exit_reason = open_price, timestamp, "STOP_GAP"
                break
            stop_hit = low <= stop
            target_hit = elapsed >= MIN_TARGET_HOLD_MINUTES and high >= target
        else:
            if open_price >= stop:
                exit_price, exit_timestamp, exit_reason = open_price, timestamp, "STOP_GAP"
                break
            stop_hit = high >= stop
            target_hit = elapsed >= MIN_TARGET_HOLD_MINUTES and low <= target
        if stop_hit:
            exit_price, exit_timestamp, exit_reason = stop, timestamp, "STOP"
            break
        if target_hit:
            exit_price, exit_timestamp, exit_reason = target, timestamp, "TARGET"
            break
    gross = float(side * math.log(exit_price / entry) * 10000.0)
    return {
        "side_value": int(side),
        "side": "LONG" if side > 0 else "SHORT",
        "entry_spot": entry,
        "exit_spot": exit_price,
        "stop_spot": stop,
        "target_spot": target,
        "entry_time": entry_timestamp.strftime("%H:%M"),
        "exit_time": exit_timestamp.strftime("%H:%M"),
        "hold_minutes": int((exit_timestamp - entry_timestamp).total_seconds() // 60),
        "exit_reason": exit_reason,
        "gross_bps": gross,
        "net_bps": gross - COST_BPS,
    }


def build_event_frame(
    sessions: dict[str, dict[str, pd.DataFrame]],
) -> tuple[pd.DataFrame, list[str]]:
    rows: list[dict[str, object]] = []
    feature_names: list[str] | None = None
    for day, frames in sessions.items():
        if day in base.HALF_DAYS:
            continue
        states = {ticker: _ib_state(frames[ticker], day) for ticker in ALL_TICKERS}
        for target in TARGETS:
            for window_id, contract in WINDOWS.items():
                event = find_event(frames[target], day, window_id, states[target])
                if event is None:
                    continue
                decision, trigger = event
                values, observed_names = build_features(
                    frames, states, target, decision, trigger, window_id
                )
                if feature_names is None:
                    feature_names = observed_names
                elif feature_names != observed_names:
                    raise AssertionError("IB feature order changed")
                entry_timestamp = decision + pd.Timedelta(minutes=1)
                force_timestamp = _timestamp(day, contract["force_exit"])
                breakout = simulate_trade(
                    frames[target],
                    entry_timestamp,
                    force_timestamp,
                    trigger,
                    states[target]["width"],
                    "BREAKOUT",
                )
                fade = simulate_trade(
                    frames[target],
                    entry_timestamp,
                    force_timestamp,
                    -trigger,
                    states[target]["width"],
                    "FADE",
                )
                rows.append(
                    {
                        "ticker": REPORT_TICKER[target],
                        "source_ticker": target,
                        "trade_date": day,
                        "month": day[:6],
                        "window_id": window_id,
                        "decision_time": decision.strftime("%H:%M"),
                        "trigger": trigger,
                        "ib_high": states[target]["high"],
                        "ib_low": states[target]["low"],
                        "ib_width": states[target]["width"],
                        **values,
                        **{f"breakout_{key}": value for key, value in breakout.items()},
                        **{f"fade_{key}": value for key, value in fade.items()},
                        "breakout_better": int(
                            float(breakout["net_bps"]) > float(fade["net_bps"])
                        ),
                    }
                )
    if not rows or feature_names is None:
        raise AssertionError("IB event frame is empty")
    output = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date", "window_id"], kind="stable"
    ).reset_index(drop=True)
    if output.duplicated(["ticker", "trade_date", "window_id"]).any():
        raise AssertionError("duplicate IB event")
    if output[feature_names].isna().any().any() or not np.isfinite(
        output[feature_names]
    ).all().all():
        raise AssertionError("invalid IB model matrix")
    return output, feature_names


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> np.ndarray:
    labels = train["breakout_better"].to_numpy(dtype=np.int64)
    if len(np.unique(labels)) != 2:
        raise AssertionError("IB training fold lacks both mode labels")
    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=180,
        learning_rate=0.025,
        num_leaves=7,
        max_depth=3,
        min_child_samples=50,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        reg_alpha=0.05,
        reg_lambda=0.5,
        random_state=SEED,
        n_jobs=8,
        deterministic=True,
        force_col_wise=True,
        verbosity=-1,
    )
    model.fit(train[features], labels)
    return model.predict_proba(test[features])[:, 1].astype(np.float64)


def predictions_to_trades(test: pd.DataFrame, probability: np.ndarray) -> pd.DataFrame:
    output_rows: list[dict[str, object]] = []
    for row, prob in zip(test.to_dict("records"), probability, strict=True):
        mode = "BREAKOUT" if prob >= 0.5 else "FADE"
        prefix = mode.lower()
        output_rows.append(
            {
                "ticker": row["ticker"],
                "source_ticker": row["source_ticker"],
                "trade_date": row["trade_date"],
                "month": row["month"],
                "window_id": row["window_id"],
                "decision_time": row["decision_time"],
                "profile_id": PROFILE_ID,
                "probability_breakout": float(prob),
                "mode": mode,
                "trigger": int(row["trigger"]),
                "side": row[f"{prefix}_side"],
                "entry_time": row[f"{prefix}_entry_time"],
                "exit_time": row[f"{prefix}_exit_time"],
                "hold_minutes": int(row[f"{prefix}_hold_minutes"]),
                "entry_spot": float(row[f"{prefix}_entry_spot"]),
                "exit_spot": float(row[f"{prefix}_exit_spot"]),
                "stop_spot": float(row[f"{prefix}_stop_spot"]),
                "target_spot": float(row[f"{prefix}_target_spot"]),
                "exit_reason": row[f"{prefix}_exit_reason"],
                "gross_bps": float(row[f"{prefix}_gross_bps"]),
                "net_bps": float(row[f"{prefix}_net_bps"]),
            }
        )
    return pd.DataFrame(output_rows)


def run_walkforward(events: pd.DataFrame, months: list[str], features: list[str]) -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    for ticker in sorted(events["ticker"].unique()):
        ticker_events = events.loc[events["ticker"].eq(ticker)].copy()
        for month in months:
            train = ticker_events.loc[ticker_events["month"] < month].copy()
            test = ticker_events.loc[ticker_events["month"].eq(month)].copy()
            if test.empty:
                continue
            if len(train) < 400:
                raise AssertionError(f"{ticker} {month}: insufficient IB training events")
            probability = fit_predict(train, test, features)
            outputs.append(predictions_to_trades(test, probability))
    if not outputs:
        raise AssertionError("IB walk-forward produced no trades")
    return pd.concat(outputs, ignore_index=True).sort_values(
        ["ticker", "trade_date", "window_id"], kind="stable"
    ).reset_index(drop=True)


def monthly_metrics(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (ticker, month), group in trades.groupby(["ticker", "month"], sort=True):
        rows.append(
            {"ticker": ticker, "profile_id": PROFILE_ID, "month": month, **base.summarize_trades(group)}
        )
    return pd.DataFrame(rows)


def evaluate_gate(trades: pd.DataFrame, months: list[str], development: bool) -> dict:
    monthly = monthly_metrics(trades)
    ticker_metrics: dict[str, dict[str, object]] = {}
    for ticker in ("QQQ", "SPX", "SPY"):
        subset = trades.loc[trades["ticker"].eq(ticker)]
        ticker_monthly = monthly.loc[monthly["ticker"].eq(ticker)].sort_values("month")
        if ticker_monthly["month"].tolist() != months:
            raise AssertionError(f"{ticker}: incomplete IB monthly ledger")
        summary = base.summarize_trades(subset)
        positives = int((ticker_monthly["net_bps"] > 0.0).sum())
        minimum = int(ticker_monthly["trades"].min())
        if development:
            passed = (
                summary["profit_factor"] > 1.10
                and summary["win_rate"] > 0.45
                and minimum > 12
                and positives >= 8
            )
        else:
            passed = (
                summary["profit_factor"] > 1.20
                and summary["win_rate"] > 0.45
                and minimum > 12
                and positives == len(months)
            )
        ticker_metrics[ticker] = {
            **summary,
            "min_month_trades": minimum,
            "positive_months": positives,
            "evaluated_months": len(months),
            "gate_pass": bool(passed),
        }
    return {
        "ticker_metrics": ticker_metrics,
        "joint_gate_pass": all(bool(item["gate_pass"]) for item in ticker_metrics.values()),
    }


def _inventory_digest(inventory: pd.DataFrame) -> str:
    columns = ["ticker", "trade_date", "path", "size_bytes", "sha256"]
    return _sha256_text(inventory[columns].to_csv(index=False, lineterminator="\n"))


def common_provenance(inventory: pd.DataFrame) -> dict[str, object]:
    return {
        "schema": "directional_ib_breakout_fade_v1_provenance",
        "created_at_utc": base.utc_now(),
        "predeclaration_path": str(PREDECLARATION.relative_to(base.REPO_ROOT)),
        "predeclaration_sha256": base.sha256_file(PREDECLARATION),
        "runner_path": str(Path(__file__).resolve().relative_to(base.REPO_ROOT)),
        "runner_sha256": base.sha256_file(__file__),
        "breadth_parent_sha256": base.sha256_file(Path(breadth.__file__)),
        "semantic_parent_sha256": base.sha256_file(Path(base.__file__)),
        "source_inventory_rows": int(len(inventory)),
        "source_inventory_sha256": _inventory_digest(inventory),
        "new_dataset_created": False,
        "adaptive_after_prior_2026_diagnostics": True,
        "production_modified": False,
    }


def _execution_contract() -> dict[str, object]:
    return {
        "windows": WINDOWS,
        "ib_clock": "09:30-10:29",
        "breakout_stop_r": BREAKOUT_STOP_R,
        "breakout_target_r": BREAKOUT_TARGET_R,
        "fade_stop_r": FADE_STOP_R,
        "fade_target_r": FADE_TARGET_R,
        "minimum_target_hold_minutes": MIN_TARGET_HOLD_MINUTES,
        "cost_bps": COST_BPS,
        "same_bar_priority": "STOP_FIRST",
        "fill_kind": "underlying_spot_proxy_not_futures_fill",
    }


def run_development(args: argparse.Namespace) -> dict[str, object]:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable IB development output exists: {output}")
    inventory = breadth.discover_source_files(Path(args.data_root), base.DEVELOPMENT_END)
    counts = inventory.groupby("ticker").size().to_dict()
    usable = breadth.eligible_inventory(inventory)
    if usable["trade_date"].nunique() != 829:
        raise AssertionError("IB development common-session count changed")
    sessions = breadth.load_sessions(usable)
    events, features = build_event_frame(sessions)
    months = [f"2025{month:02d}" for month in range(1, 13)]
    trades = run_walkforward(events, months, features)
    gate = evaluate_gate(trades, months, development=True)
    monthly = monthly_metrics(trades)
    metrics: dict[str, object] = {
        "schema": "directional_ib_breakout_fade_v1_development_metrics",
        "status": "PASS_DEVELOPMENT_GATE" if gate["joint_gate_pass"] else "CLOSED_DEVELOPMENT_GATE",
        "created_at_utc": base.utc_now(),
        "scope": {"start_date": base.START_DATE, "end_date": base.DEVELOPMENT_END, "months": months},
        "source_sessions_by_ticker": counts,
        "eligible_common_sessions": 829,
        "event_rows": int(len(events)),
        "feature_count": len(features),
        "execution": _execution_contract(),
        "holdout_2026_used_for_training_or_selection": False,
        **gate,
        "production_modified": False,
    }
    output.mkdir(parents=True, exist_ok=False)
    inventory.to_csv(output / "source_inventory.csv", index=False, lineterminator="\n")
    trades.to_parquet(output / "development_trade_ledger.parquet", index=False)
    monthly.to_csv(output / "development_monthly_metrics.csv", index=False)
    (output / "features.json").write_text(json.dumps(features, indent=2), encoding="utf-8")
    provenance = common_provenance(inventory)
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    metrics["provenance_sha256"] = base.sha256_file(output / "provenance.json")
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
    return metrics


def _load_development(development_dir: Path) -> tuple[dict, dict, list[str]]:
    metrics = json.loads((development_dir / "metrics.json").read_text(encoding="utf-8"))
    provenance = json.loads((development_dir / "provenance.json").read_text(encoding="utf-8"))
    if metrics.get("status") != "PASS_DEVELOPMENT_GATE":
        raise AssertionError("IB development did not pass; 2026 remains closed")
    if provenance.get("predeclaration_sha256") != base.sha256_file(PREDECLARATION):
        raise AssertionError("IB predeclaration changed")
    if provenance.get("runner_sha256") != base.sha256_file(__file__):
        raise AssertionError("IB runner changed")
    if provenance.get("breadth_parent_sha256") != base.sha256_file(Path(breadth.__file__)):
        raise AssertionError("IB breadth parent changed")
    if provenance.get("semantic_parent_sha256") != base.sha256_file(Path(base.__file__)):
        raise AssertionError("IB semantic parent changed")
    features = json.loads((development_dir / "features.json").read_text(encoding="utf-8"))
    return metrics, provenance, features


def run_evaluation(args: argparse.Namespace) -> dict[str, object]:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable IB evaluation output exists: {output}")
    development_dir = Path(args.development_dir)
    development, frozen_provenance, features = _load_development(development_dir)
    inventory = breadth.discover_source_files(Path(args.data_root), base.EVALUATION_END)
    frozen_inventory = pd.read_csv(
        development_dir / "source_inventory.csv", dtype={"trade_date": str}
    )
    current_development = inventory.loc[
        inventory["trade_date"] <= base.DEVELOPMENT_END
    ].reset_index(drop=True)
    columns = ["ticker", "trade_date", "path", "size_bytes", "sha256"]
    if not frozen_inventory[columns].astype(str).equals(current_development[columns].astype(str)):
        raise AssertionError("IB pre-2026 inventory changed")
    if frozen_provenance.get("source_inventory_sha256") != _inventory_digest(current_development):
        raise AssertionError("IB pre-2026 source digest changed")
    usable = breadth.eligible_inventory(inventory)
    if usable["trade_date"].nunique() != 962:
        raise AssertionError("IB evaluation common-session count changed")
    sessions = breadth.load_sessions(usable)
    events, observed_features = build_event_frame(sessions)
    if observed_features != features:
        raise AssertionError("IB evaluation feature contract changed")
    months = [f"2026{month:02d}" for month in range(1, 8)]
    trades = run_walkforward(events, months, features)
    gate = evaluate_gate(trades, months, development=False)
    monthly = monthly_metrics(trades)
    metrics: dict[str, object] = {
        "schema": "directional_ib_breakout_fade_v1_evaluation_metrics",
        "status": "ADAPTIVE_DIAGNOSTIC_GATE_PASS" if gate["joint_gate_pass"] else "CLOSED_ADAPTIVE_DIAGNOSTIC_GATE",
        "created_at_utc": base.utc_now(),
        "scope": {"start_date": "20260101", "end_date": base.EVALUATION_END, "months": months, "july_status": "MTD_THROUGH_20260715"},
        "development_metrics_sha256": base.sha256_file(development_dir / "metrics.json"),
        "eligible_common_sessions": 962,
        "event_rows": int(len(events)),
        "feature_count": len(features),
        "execution": _execution_contract(),
        **gate,
        "confirmatory_evidence": False,
        "production_modified": False,
    }
    output.mkdir(parents=True, exist_ok=False)
    inventory.to_csv(output / "source_inventory.csv", index=False, lineterminator="\n")
    trades.to_parquet(output / "trade_ledger.parquet", index=False)
    monthly.to_csv(output / "monthly_metrics.csv", index=False)
    provenance = common_provenance(inventory)
    provenance["development_provenance_sha256"] = base.sha256_file(
        development_dir / "provenance.json"
    )
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    metrics["provenance_sha256"] = base.sha256_file(output / "provenance.json")
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("development", "evaluation"), required=True)
    parser.add_argument("--data-root", default=str(base.DEFAULT_DATA_ROOT))
    parser.add_argument("--development-dir", default=str(DEFAULT_DEVELOPMENT_OUTPUT))
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    if not args.output:
        args.output = str(
            DEFAULT_DEVELOPMENT_OUTPUT if args.phase == "development" else DEFAULT_EVALUATION_OUTPUT
        )
    return args


def main() -> int:
    args = parse_args()
    if args.phase == "development":
        run_development(args)
    else:
        run_evaluation(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
