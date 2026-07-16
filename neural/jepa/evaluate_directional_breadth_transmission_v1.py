#!/usr/bin/env python3
"""Two-window directional breadth transmission walk-forward diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import lightgbm as lgb
import numpy as np
import pandas as pd

from neural.jepa import evaluate_directional_semantic_jepa_v1 as base


PREDECLARATION = (
    base.REPO_ROOT
    / "research_papers/JEPA/DIRECTIONAL_BREADTH_TRANSMISSION_V1_PREDECLARATION.md"
)
DEFAULT_DEVELOPMENT_OUTPUT = (
    base.REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "directional_breadth_transmission_v1_development_202208_202512"
)
DEFAULT_EVALUATION_OUTPUT = (
    base.REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "directional_breadth_transmission_v1_evaluation_202601_20260715"
)

TARGETS = base.SOURCE_TICKERS
COMPONENTS = (
    "AAPL",
    "AMZN",
    "GOOGL",
    "META",
    "MSFT",
    "NFLX",
    "NVDA",
    "TSLA",
    "IWM",
    "TLT",
    "GLD",
    "SLV",
)
TECH_COMPONENTS = (
    "AAPL",
    "AMZN",
    "GOOGL",
    "META",
    "MSFT",
    "NFLX",
    "NVDA",
    "TSLA",
)
ALL_TICKERS = TARGETS + COMPONENTS
REPORT_TICKER = base.REPORT_TICKER
HORIZONS = (1, 5, 15, 30)
COST_BPS = 1.0
SEED = 20260716

WINDOWS = {
    "W1": {
        "decision_time": "10:00",
        "entry_time": "10:01",
        "exit_time": "13:01",
        "hold_minutes": 180,
    },
    "W2": {
        "decision_time": "13:01",
        "entry_time": "13:02",
        "exit_time": "15:59",
        "hold_minutes": 177,
    },
}
TARGET_PROFILE = "TARGET_ONLY"
BREADTH_PROFILE = "BREADTH_TRANSMISSION"
SELECTABLE_PROFILES = (TARGET_PROFILE, BREADTH_PROFILE)

EXPECTED_MISSING_BY_TICKER = {
    "AMZN": frozenset({"20220912", "20220913", "20220914", "20220915", "20220916"}),
    "GOOGL": frozenset(
        {
            "20220815",
            "20220816",
            "20220817",
            "20220818",
            "20220819",
            "20220912",
            "20220913",
            "20220914",
            "20220915",
            "20220916",
        }
    ),
    "META": frozenset({"20250317", "20250908", "20250909"}),
    "NFLX": frozenset({"20251117", "20251118", "20251119", "20251120", "20251121"}),
    "TSLA": frozenset({"20230313", "20230314", "20230315", "20230316", "20230317"}),
    "GLD": frozenset({"20240513", "20240514", "20240515", "20240516", "20240517"}),
}
SOURCE_MISSING_DAYS = frozenset().union(*EXPECTED_MISSING_BY_TICKER.values())
PANEL_INVALID_DAYS = frozenset(set(base.INVALID_SOURCE_DAYS) | {"20240603"})
PANEL_EXCLUDED_DAYS = SOURCE_MISSING_DAYS | PANEL_INVALID_DAYS


def canonical_date(value: object) -> str:
    return base.canonical_date(value)


def discover_source_files(root: Path, end_date: str) -> pd.DataFrame:
    rows: list[dict] = []
    for ticker in ALL_TICKERS:
        for path in sorted((root / ticker).glob("*/*/*.parquet")):
            day = canonical_date(path.stem)
            if base.START_DATE <= day <= end_date:
                rows.append(
                    {
                        "ticker": ticker,
                        "trade_date": day,
                        "path": str(path.resolve()),
                        "size_bytes": path.stat().st_size,
                        "sha256": base.sha256_file(path),
                    }
                )
    inventory = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    target_dates = set(
        inventory.loc[inventory["ticker"].eq(TARGETS[0]), "trade_date"].astype(str)
    )
    for ticker in ALL_TICKERS:
        dates = set(
            inventory.loc[inventory["ticker"].eq(ticker), "trade_date"].astype(str)
        )
        expected_missing = {
            day
            for day in EXPECTED_MISSING_BY_TICKER.get(ticker, frozenset())
            if base.START_DATE <= day <= end_date
        }
        if target_dates - dates != expected_missing or dates - target_dates:
            raise AssertionError(f"breadth source missing-day contract changed for {ticker}")
    if not target_dates or inventory.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("invalid breadth source inventory")
    return inventory


def eligible_inventory(inventory: pd.DataFrame) -> pd.DataFrame:
    target_dates = set(
        inventory.loc[inventory["ticker"].eq(TARGETS[0]), "trade_date"].astype(str)
    )
    eligible_dates = sorted(target_dates.difference(PANEL_EXCLUDED_DAYS))
    eligible = inventory.loc[inventory["trade_date"].isin(eligible_dates)].copy()
    counts = eligible.groupby("ticker").size().to_dict()
    if counts != {ticker: len(eligible_dates) for ticker in ALL_TICKERS}:
        raise AssertionError(f"breadth eligible intersection changed: {counts}")
    return eligible.reset_index(drop=True)


def inventory_digest(inventory: pd.DataFrame) -> str:
    columns = ["ticker", "trade_date", "path", "size_bytes", "sha256"]
    payload = inventory[columns].to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_sessions(inventory: pd.DataFrame) -> dict[str, dict[str, pd.DataFrame]]:
    sessions: dict[str, dict[str, pd.DataFrame]] = {}
    for row in inventory.itertuples(index=False):
        frame = pd.read_parquet(row.path)
        validated = base.validate_bar_frame(frame, str(row.ticker), str(row.trade_date))
        sessions.setdefault(str(row.trade_date), {})[str(row.ticker)] = validated
    for day, frames in sessions.items():
        if set(frames) != set(ALL_TICKERS):
            raise AssertionError(f"{day}: incomplete breadth panel")
        reference = frames[ALL_TICKERS[0]]["timestamp"].tolist()
        for ticker in ALL_TICKERS[1:]:
            if frames[ticker]["timestamp"].tolist() != reference:
                raise AssertionError(f"{day}: breadth timestamp mismatch for {ticker}")
    return dict(sorted(sessions.items()))


def _clock_row(frame: pd.DataFrame, day: str, clock: str) -> pd.Series:
    timestamp = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {clock}")
    return frame.loc[timestamp]


def _intraday_metrics(frame: pd.DataFrame, day: str, decision_time: str) -> dict[str, float]:
    decision = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {decision_time}")
    position = int(frame.index.get_loc(decision))
    close = frame["close"].to_numpy(dtype=np.float64)
    output: dict[str, float] = {}
    for horizon in HORIZONS:
        if position < horizon:
            raise AssertionError(f"{day} {decision_time}: insufficient {horizon}m history")
        transition = np.diff(np.log(close[position - horizon : position + 1])) * 10000.0
        window = frame.iloc[position - horizon + 1 : position + 1]
        last = float(close[position])
        high = float(window["high"].max())
        low = float(window["low"].min())
        first_open = float(window["open"].iloc[0])
        output[f"ret_{horizon}m"] = float(transition.sum())
        output[f"rv_{horizon}m"] = float(np.sqrt(np.square(transition).sum()))
        output[f"range_{horizon}m"] = float((high - low) / last * 10000.0)
        output[f"body_{horizon}m"] = float(math.log(last / first_open) * 10000.0)
        output[f"location_{horizon}m"] = (
            float((last - low) / (high - low) - 0.5) if high > low else 0.0
        )
    open_price = float(_clock_row(frame, day, "09:30")["open"])
    decision_close = float(_clock_row(frame, day, decision_time)["close"])
    output["ret_since_open"] = float(math.log(decision_close / open_price) * 10000.0)
    return output


def _prefixed(values: dict[str, float], prefix: str) -> dict[str, float]:
    return {f"{prefix}_{name}": value for name, value in values.items()}


def build_row(
    day: str,
    frames: dict[str, pd.DataFrame],
    previous_day: str,
    previous_frames: dict[str, pd.DataFrame],
    target: str,
    window_id: str,
) -> tuple[dict, list[str], list[str]]:
    contract = WINDOWS[window_id]
    target_metrics = _intraday_metrics(frames[target], day, contract["decision_time"])
    row: dict[str, object] = {
        "ticker": REPORT_TICKER[target],
        "source_ticker": target,
        "trade_date": day,
        "month": day[:6],
        "window_id": window_id,
        "decision_time": contract["decision_time"],
        "entry_time": contract["entry_time"],
        "exit_time": contract["exit_time"],
        "hold_minutes": contract["hold_minutes"],
    }
    target_values = _prefixed(target_metrics, "target")
    row.update(target_values)
    target_features = list(target_values)

    previous = previous_frames[target]
    previous_open = float(_clock_row(previous, previous_day, "09:30")["open"])
    previous_close = base.session_close(previous, previous_day)
    previous_high = float(previous["high"].max())
    previous_low = float(previous["low"].min())
    previous_values = {
        "target_previous_return": float(math.log(previous_close / previous_open) * 10000.0),
        "target_previous_range": float((previous_high - previous_low) / previous_close * 10000.0),
        "target_previous_location": (
            float((previous_close - previous_low) / (previous_high - previous_low) - 0.5)
            if previous_high > previous_low
            else 0.0
        ),
        "window_w2": float(window_id == "W2"),
        "dow_sin": float(math.sin(2.0 * math.pi * pd.Timestamp(day).dayofweek / 5.0)),
        "dow_cos": float(math.cos(2.0 * math.pi * pd.Timestamp(day).dayofweek / 5.0)),
    }
    row.update(previous_values)
    target_features.extend(previous_values)

    component_metrics: dict[str, dict[str, float]] = {}
    breadth_features: list[str] = []
    for component in COMPONENTS:
        values = _intraday_metrics(frames[component], day, contract["decision_time"])
        component_metrics[component] = values
        prefixed = _prefixed(values, component.lower())
        row.update(prefixed)
        breadth_features.extend(prefixed)

    return_names = [f"ret_{horizon}m" for horizon in HORIZONS] + ["ret_since_open"]
    for return_name in return_names:
        tech = np.asarray(
            [component_metrics[ticker][return_name] for ticker in TECH_COMPONENTS],
            dtype=np.float64,
        )
        suffix = return_name.removeprefix("ret_")
        aggregates = {
            f"tech_mean_{suffix}": float(tech.mean()),
            f"tech_median_{suffix}": float(np.median(tech)),
            f"tech_std_{suffix}": float(tech.std(ddof=0)),
            f"tech_min_{suffix}": float(tech.min()),
            f"tech_max_{suffix}": float(tech.max()),
            f"tech_positive_fraction_{suffix}": float(np.mean(tech > 0.0)),
            f"target_minus_tech_{suffix}": float(target_metrics[return_name] - tech.mean()),
            f"target_minus_iwm_{suffix}": float(
                target_metrics[return_name] - component_metrics["IWM"][return_name]
            ),
            f"target_plus_tlt_{suffix}": float(
                target_metrics[return_name] + component_metrics["TLT"][return_name]
            ),
        }
        row.update(aggregates)
        breadth_features.extend(aggregates)

    entry = float(_clock_row(frames[target], day, contract["entry_time"])["open"])
    exit_price = float(_clock_row(frames[target], day, contract["exit_time"])["open"])
    row["entry_spot"] = entry
    row["exit_spot"] = exit_price
    row["future_return_bps"] = float(math.log(exit_price / entry) * 10000.0)
    return row, target_features, breadth_features


def build_daily_frame(
    sessions: dict[str, dict[str, pd.DataFrame]],
) -> tuple[pd.DataFrame, list[str], list[str]]:
    dates = sorted(sessions)
    rows: list[dict] = []
    target_features: list[str] | None = None
    breadth_features: list[str] | None = None
    for index, day in enumerate(dates):
        if index == 0 or day in base.HALF_DAYS:
            continue
        previous_day = dates[index - 1]
        for target in TARGETS:
            for window_id in WINDOWS:
                row, target_names, breadth_names = build_row(
                    day,
                    sessions[day],
                    previous_day,
                    sessions[previous_day],
                    target,
                    window_id,
                )
                if target_features is None:
                    target_features = target_names
                    breadth_features = breadth_names
                elif target_features != target_names or breadth_features != breadth_names:
                    raise AssertionError("breadth feature order changed")
                rows.append(row)
    frame = pd.DataFrame(rows).sort_values(
        ["ticker", "trade_date", "window_id"], kind="stable"
    ).reset_index(drop=True)
    if frame.empty or target_features is None or breadth_features is None:
        raise AssertionError("breadth daily frame is empty")
    features = target_features + breadth_features
    if frame[features].isna().any().any() or not np.isfinite(frame[features]).all().all():
        raise AssertionError("breadth features contain non-finite values")
    if frame.duplicated(["ticker", "trade_date", "window_id"]).any():
        raise AssertionError("duplicate breadth decision")
    return frame, target_features, breadth_features


def magnitude_weights(future_return_bps: Iterable[float]) -> np.ndarray:
    magnitude = np.clip(np.abs(np.asarray(list(future_return_bps), dtype=np.float64)), 5.0, 150.0)
    median = float(np.median(magnitude))
    if not np.isfinite(median) or median <= 0.0:
        raise AssertionError("invalid training return magnitude")
    return magnitude / median


def fit_predict(
    train: pd.DataFrame, test: pd.DataFrame, feature_names: list[str]
) -> np.ndarray:
    labels = (train["future_return_bps"].to_numpy(dtype=np.float64) > 0.0).astype(int)
    if len(np.unique(labels)) != 2:
        raise AssertionError("breadth training fold lacks both directions")
    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=240,
        learning_rate=0.025,
        num_leaves=7,
        max_depth=3,
        min_child_samples=40,
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
    model.fit(
        train[feature_names], labels, sample_weight=magnitude_weights(train["future_return_bps"])
    )
    return model.predict_proba(test[feature_names])[:, 1].astype(np.float64)


def predictions_to_trades(
    test: pd.DataFrame, probability: np.ndarray, profile_id: str
) -> pd.DataFrame:
    columns = [
        "ticker",
        "source_ticker",
        "trade_date",
        "month",
        "window_id",
        "decision_time",
        "entry_time",
        "exit_time",
        "hold_minutes",
        "entry_spot",
        "exit_spot",
        "future_return_bps",
    ]
    output = test[columns].copy()
    output["profile_id"] = profile_id
    output["probability_up"] = probability
    output["side"] = np.where(probability >= 0.5, "LONG", "SHORT")
    signed = np.where(
        probability >= 0.5,
        output["future_return_bps"],
        -output["future_return_bps"],
    )
    output["gross_bps"] = signed
    output["net_bps"] = signed - COST_BPS
    return output


def run_walkforward(
    daily: pd.DataFrame,
    months: list[str],
    target_features: list[str],
    breadth_features: list[str],
    selected: dict[str, str] | None = None,
) -> pd.DataFrame:
    outputs = []
    for ticker in sorted(daily["ticker"].unique()):
        ticker_frame = daily.loc[daily["ticker"].eq(ticker)].copy()
        profiles = [selected[ticker]] if selected is not None else list(SELECTABLE_PROFILES)
        for month in months:
            train = ticker_frame.loc[ticker_frame["month"] < month].copy()
            test = ticker_frame.loc[ticker_frame["month"].eq(month)].copy()
            if test.empty:
                continue
            if len(train) < 800:
                raise AssertionError(f"{ticker} {month}: insufficient breadth history")
            for profile in profiles:
                features = (
                    target_features
                    if profile == TARGET_PROFILE
                    else target_features + breadth_features
                )
                probability = fit_predict(train, test, features)
                outputs.append(predictions_to_trades(test, probability, profile))
    if not outputs:
        raise AssertionError("breadth walk-forward produced no trades")
    return pd.concat(outputs, ignore_index=True).sort_values(
        ["ticker", "trade_date", "window_id", "profile_id"], kind="stable"
    ).reset_index(drop=True)


def monthly_metrics(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (ticker, profile, month), group in trades.groupby(
        ["ticker", "profile_id", "month"], sort=True
    ):
        rows.append(
            {
                "ticker": ticker,
                "profile_id": profile,
                "month": month,
                **base.summarize_trades(group),
            }
        )
    return pd.DataFrame(rows)


def select_profiles(trades: pd.DataFrame) -> tuple[dict[str, str], pd.DataFrame]:
    monthly = monthly_metrics(trades)
    selections: dict[str, str] = {}
    rows = []
    for ticker in sorted(monthly["ticker"].unique()):
        candidates = []
        for profile in SELECTABLE_PROFILES:
            ticker_monthly = monthly.loc[
                monthly["ticker"].eq(ticker) & monthly["profile_id"].eq(profile)
            ].sort_values("month")
            ticker_trades = trades.loc[
                trades["ticker"].eq(ticker) & trades["profile_id"].eq(profile)
            ]
            if len(ticker_monthly) != 12 or int(ticker_monthly["trades"].min()) <= 12:
                raise AssertionError("incomplete breadth development coverage")
            candidate = {
                "ticker": ticker,
                "profile_id": profile,
                "positive_months": int((ticker_monthly["net_bps"] > 0.0).sum()),
                "monthly_net_q25": float(ticker_monthly["net_bps"].quantile(0.25)),
                "aggregate_profit_factor": base.profit_factor(ticker_trades["net_bps"]),
                "aggregate_win_rate": float((ticker_trades["net_bps"] > 0.0).mean()),
                "aggregate_net_bps": float(ticker_trades["net_bps"].sum()),
                "min_month_trades": int(ticker_monthly["trades"].min()),
            }
            candidates.append(candidate)
        candidates.sort(
            key=lambda row: (
                -row["positive_months"],
                -row["monthly_net_q25"],
                -row["aggregate_profit_factor"],
                row["profile_id"],
            )
        )
        for rank, candidate in enumerate(candidates, start=1):
            candidate["rank"] = rank
            candidate["selected"] = rank == 1
            rows.append(candidate)
        selections[ticker] = candidates[0]["profile_id"]
    return selections, pd.DataFrame(rows)


def evaluate_gate(trades: pd.DataFrame, months: list[str]) -> dict:
    monthly = monthly_metrics(trades)
    ticker_metrics = {}
    for ticker in sorted(trades["ticker"].unique()):
        ticker_trades = trades.loc[
            trades["ticker"].eq(ticker) & trades["month"].isin(months)
        ]
        ticker_monthly = monthly.loc[
            monthly["ticker"].eq(ticker) & monthly["month"].isin(months)
        ]
        if len(ticker_monthly) != len(months):
            raise AssertionError(f"{ticker}: incomplete breadth evaluation months")
        summary = base.summarize_trades(ticker_trades)
        minimum = int(ticker_monthly["trades"].min())
        positives = int((ticker_monthly["net_bps"] > 0.0).sum())
        passed = (
            summary["win_rate"] > 0.45
            and summary["profit_factor"] > 1.20
            and minimum > 12
            and positives == len(months)
        )
        ticker_metrics[ticker] = {
            **summary,
            "min_month_trades": minimum,
            "positive_months": positives,
            "evaluated_months": len(months),
            "gate_pass": passed,
        }
    return {
        "ticker_metrics": ticker_metrics,
        "joint_gate_pass": all(item["gate_pass"] for item in ticker_metrics.values()),
    }


def common_provenance(inventory: pd.DataFrame) -> dict:
    return {
        "schema": "directional_breadth_transmission_v1_provenance",
        "created_at_utc": base.utc_now(),
        "predeclaration_path": str(PREDECLARATION.relative_to(base.REPO_ROOT)),
        "predeclaration_sha256": base.sha256_file(PREDECLARATION),
        "runner_path": str(Path(__file__).resolve().relative_to(base.REPO_ROOT)),
        "runner_sha256": base.sha256_file(__file__),
        "parent_runner_sha256": base.sha256_file(Path(base.__file__)),
        "source_inventory_rows": int(len(inventory)),
        "source_inventory_sha256": inventory_digest(inventory),
        "new_dataset_created": False,
        "adaptive_after_prior_2026_diagnostics": True,
        "production_modified": False,
    }


def run_development(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable breadth development output exists: {output}")
    inventory = discover_source_files(Path(args.data_root), base.DEVELOPMENT_END)
    counts = inventory.groupby("ticker").size().to_dict()
    if any(counts.get(ticker) != 859 for ticker in TARGETS):
        raise AssertionError(f"breadth development census mismatch: {counts}")
    usable = eligible_inventory(inventory)
    if usable["trade_date"].nunique() != 829:
        raise AssertionError("breadth development eligible-session count changed")
    sessions = load_sessions(usable)
    daily, target_features, breadth_features = build_daily_frame(sessions)
    months = [f"2025{month:02d}" for month in range(1, 13)]
    trades = run_walkforward(daily, months, target_features, breadth_features)
    selections, ranking = select_profiles(trades)
    monthly = monthly_metrics(trades)
    provenance = common_provenance(inventory)
    metrics = {
        "schema": "directional_breadth_transmission_v1_development_metrics",
        "status": "PASS_DEVELOPMENT_FREEZE",
        "created_at_utc": base.utc_now(),
        "scope": {"start_date": base.START_DATE, "end_date": base.DEVELOPMENT_END},
        "source_sessions_by_ticker": counts,
        "eligible_common_sessions": 829,
        "daily_rows": int(len(daily)),
        "target_feature_count": len(target_features),
        "breadth_feature_count": len(breadth_features),
        "selected_profiles": selections,
        "holdout_2026_used_for_training_or_selection": False,
        "adaptive_design_after_prior_2026_diagnostics": True,
        "production_modified": False,
    }
    output.mkdir(parents=True, exist_ok=False)
    inventory.to_csv(output / "source_inventory.csv", index=False, lineterminator="\n")
    trades.to_parquet(output / "development_trade_ledger.parquet", index=False)
    monthly.to_csv(output / "development_monthly_metrics.csv", index=False)
    ranking.to_csv(output / "profile_ranking.csv", index=False)
    (output / "target_features.json").write_text(
        json.dumps(target_features, indent=2), encoding="utf-8"
    )
    (output / "breadth_features.json").write_text(
        json.dumps(breadth_features, indent=2), encoding="utf-8"
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


def load_development(development_dir: Path) -> tuple[dict, dict, list[str], list[str]]:
    metrics = json.loads((development_dir / "metrics.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (development_dir / "provenance.json").read_text(encoding="utf-8")
    )
    if metrics.get("status") != "PASS_DEVELOPMENT_FREEZE":
        raise AssertionError("invalid breadth development freeze")
    if provenance.get("predeclaration_sha256") != base.sha256_file(PREDECLARATION):
        raise AssertionError("breadth predeclaration changed")
    if provenance.get("runner_sha256") != base.sha256_file(__file__):
        raise AssertionError("breadth runner changed")
    if provenance.get("parent_runner_sha256") != base.sha256_file(Path(base.__file__)):
        raise AssertionError("breadth parent runner changed")
    target_features = json.loads(
        (development_dir / "target_features.json").read_text(encoding="utf-8")
    )
    breadth_features = json.loads(
        (development_dir / "breadth_features.json").read_text(encoding="utf-8")
    )
    return metrics, provenance, target_features, breadth_features


def verify_development_sources(
    inventory: pd.DataFrame, development_dir: Path, provenance: dict
) -> None:
    frozen = pd.read_csv(development_dir / "source_inventory.csv", dtype={"trade_date": str})
    current = inventory.loc[inventory["trade_date"] <= base.DEVELOPMENT_END].reset_index(
        drop=True
    )
    columns = ["ticker", "trade_date", "path", "size_bytes", "sha256"]
    if not frozen[columns].astype(str).equals(current[columns].astype(str)):
        raise AssertionError("pre-2026 breadth source inventory changed")
    if provenance.get("source_inventory_sha256") != inventory_digest(current):
        raise AssertionError("pre-2026 breadth source digest changed")


def run_evaluation(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable breadth evaluation output exists: {output}")
    development_dir = Path(args.development_dir)
    development, frozen_provenance, target_features, breadth_features = load_development(
        development_dir
    )
    inventory = discover_source_files(Path(args.data_root), base.EVALUATION_END)
    counts = inventory.groupby("ticker").size().to_dict()
    if any(counts.get(ticker) != 992 for ticker in TARGETS):
        raise AssertionError(f"breadth evaluation census mismatch: {counts}")
    verify_development_sources(inventory, development_dir, frozen_provenance)
    usable = eligible_inventory(inventory)
    if usable["trade_date"].nunique() != 962:
        raise AssertionError("breadth evaluation eligible-session count changed")
    sessions = load_sessions(usable)
    daily, observed_target, observed_breadth = build_daily_frame(sessions)
    if observed_target != target_features or observed_breadth != breadth_features:
        raise AssertionError("breadth evaluation feature contract changed")
    months = [f"2026{month:02d}" for month in range(1, 8)]
    selected = {
        str(key): str(value) for key, value in development["selected_profiles"].items()
    }
    trades = run_walkforward(
        daily, months, target_features, breadth_features, selected=selected
    )
    gate = evaluate_gate(trades, months)
    monthly = monthly_metrics(trades)
    metrics = {
        "schema": "directional_breadth_transmission_v1_evaluation_metrics",
        "status": (
            "ADAPTIVE_DIAGNOSTIC_GATE_PASS"
            if gate["joint_gate_pass"]
            else "CLOSED_ADAPTIVE_DIAGNOSTIC_GATE"
        ),
        "created_at_utc": base.utc_now(),
        "scope": {
            "start_date": "20260101",
            "end_date": base.EVALUATION_END,
            "months": months,
            "july_status": "MTD_THROUGH_20260715",
        },
        "selected_profiles": selected,
        "source_sessions_by_ticker": counts,
        "eligible_common_sessions": 962,
        "execution": {
            "windows": WINDOWS,
            "cost_bps": COST_BPS,
            "maximum_concurrent_positions": 1,
            "fill_kind": "underlying_open_spot_proxy_not_futures_fill",
        },
        **gate,
        "confirmatory_evidence": False,
        "production_modified": False,
    }
    provenance = common_provenance(inventory)
    provenance.update(
        {
            "development_metrics_sha256": base.sha256_file(
                development_dir / "metrics.json"
            ),
            "development_provenance_sha256": base.sha256_file(
                development_dir / "provenance.json"
            ),
        }
    )
    output.mkdir(parents=True, exist_ok=False)
    inventory.to_csv(output / "source_inventory.csv", index=False, lineterminator="\n")
    trades.to_parquet(output / "trade_ledger.parquet", index=False)
    monthly.to_csv(output / "monthly_metrics.csv", index=False)
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
            DEFAULT_DEVELOPMENT_OUTPUT
            if args.phase == "development"
            else DEFAULT_EVALUATION_OUTPUT
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
