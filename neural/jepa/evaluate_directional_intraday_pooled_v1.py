#!/usr/bin/env python3
"""Pooled all-ticker directional walk-forward over six non-overlapping windows."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from neural.jepa import evaluate_directional_breadth_transmission_v1 as panel
from neural.jepa import evaluate_directional_semantic_jepa_v1 as base


PREDECLARATION = (
    base.REPO_ROOT
    / "research_papers/JEPA/DIRECTIONAL_INTRADAY_POOLED_V1_PREDECLARATION.md"
)
DEFAULT_DEVELOPMENT_OUTPUT = (
    base.REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "directional_intraday_pooled_v1_development_202208_202512"
)
DEFAULT_EVALUATION_OUTPUT = (
    base.REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "directional_intraday_pooled_v1_evaluation_202601_20260715"
)

WINDOWS = {
    "H1": {"decision_time": "10:00", "entry_time": "10:01", "exit_time": "11:01", "hold_minutes": 60},
    "H2": {"decision_time": "11:01", "entry_time": "11:02", "exit_time": "12:02", "hold_minutes": 60},
    "H3": {"decision_time": "12:02", "entry_time": "12:03", "exit_time": "13:03", "hold_minutes": 60},
    "H4": {"decision_time": "13:03", "entry_time": "13:04", "exit_time": "14:04", "hold_minutes": 60},
    "H5": {"decision_time": "14:04", "entry_time": "14:05", "exit_time": "15:05", "hold_minutes": 60},
    "H6": {"decision_time": "15:05", "entry_time": "15:06", "exit_time": "15:59", "hold_minutes": 53},
}
TARGET_PROFILE = "POOLED_TARGET_ONLY"
BREADTH_PROFILE = "POOLED_BREADTH_TRANSMISSION"
SELECTABLE_PROFILES = (TARGET_PROFILE, BREADTH_PROFILE)
TICKER_FEATURES = ("ticker_qqq", "ticker_spx", "ticker_spy")
COST_BPS = 1.0
SEED = 20260716


def build_row(
    day: str,
    frames: dict[str, pd.DataFrame],
    previous_day: str,
    previous_frames: dict[str, pd.DataFrame],
    target: str,
    window_id: str,
) -> tuple[dict, list[str], list[str]]:
    contract = WINDOWS[window_id]
    target_metrics = panel._intraday_metrics(frames[target], day, contract["decision_time"])
    report_ticker = panel.REPORT_TICKER[target]
    row: dict[str, object] = {
        "ticker": report_ticker,
        "source_ticker": target,
        "trade_date": day,
        "month": day[:6],
        "window_id": window_id,
        **contract,
    }
    target_values = panel._prefixed(target_metrics, "target")
    row.update(target_values)
    target_features = list(target_values)

    previous = previous_frames[target]
    previous_open = float(panel._clock_row(previous, previous_day, "09:30")["open"])
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
        "window_progress": float(list(WINDOWS).index(window_id) / (len(WINDOWS) - 1)),
        "dow_sin": float(math.sin(2.0 * math.pi * pd.Timestamp(day).dayofweek / 5.0)),
        "dow_cos": float(math.cos(2.0 * math.pi * pd.Timestamp(day).dayofweek / 5.0)),
        "ticker_qqq": float(report_ticker == "QQQ"),
        "ticker_spx": float(report_ticker == "SPX"),
        "ticker_spy": float(report_ticker == "SPY"),
    }
    row.update(previous_values)
    target_features.extend(previous_values)

    component_metrics: dict[str, dict[str, float]] = {}
    breadth_features: list[str] = []
    for component in panel.COMPONENTS:
        values = panel._intraday_metrics(frames[component], day, contract["decision_time"])
        component_metrics[component] = values
        prefixed = panel._prefixed(values, component.lower())
        row.update(prefixed)
        breadth_features.extend(prefixed)

    return_names = [f"ret_{horizon}m" for horizon in panel.HORIZONS] + ["ret_since_open"]
    for return_name in return_names:
        tech = np.asarray(
            [component_metrics[ticker][return_name] for ticker in panel.TECH_COMPONENTS],
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

    entry = float(panel._clock_row(frames[target], day, contract["entry_time"])["open"])
    exit_price = float(panel._clock_row(frames[target], day, contract["exit_time"])["open"])
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
        for target in panel.TARGETS:
            for window_id in WINDOWS:
                row, target_names, breadth_names = build_row(
                    day, sessions[day], previous_day, sessions[previous_day], target, window_id
                )
                if target_features is None:
                    target_features, breadth_features = target_names, breadth_names
                elif target_features != target_names or breadth_features != breadth_names:
                    raise AssertionError("pooled feature order changed")
                rows.append(row)
    frame = pd.DataFrame(rows).sort_values(
        ["trade_date", "window_id", "ticker"], kind="stable"
    ).reset_index(drop=True)
    if frame.empty or target_features is None or breadth_features is None:
        raise AssertionError("pooled daily frame is empty")
    features = target_features + breadth_features
    if frame[features].isna().any().any() or not np.isfinite(frame[features]).all().all():
        raise AssertionError("pooled features contain non-finite values")
    if frame.duplicated(["ticker", "trade_date", "window_id"]).any():
        raise AssertionError("duplicate pooled decision")
    return frame, target_features, breadth_features


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> np.ndarray:
    labels = (train["future_return_bps"].to_numpy(dtype=np.float64) > 0.0).astype(int)
    if len(np.unique(labels)) != 2:
        raise AssertionError("pooled fold lacks both directions")
    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=240,
        learning_rate=0.025,
        num_leaves=7,
        max_depth=3,
        min_child_samples=80,
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
        train[features],
        labels,
        sample_weight=panel.magnitude_weights(train["future_return_bps"]),
    )
    return model.predict_proba(test[features])[:, 1].astype(np.float64)


def predictions_to_trades(
    test: pd.DataFrame, probability: np.ndarray, profile_id: str
) -> pd.DataFrame:
    columns = [
        "ticker", "source_ticker", "trade_date", "month", "window_id",
        "decision_time", "entry_time", "exit_time", "hold_minutes", "entry_spot",
        "exit_spot", "future_return_bps",
    ]
    output = test[columns].copy()
    output["profile_id"] = profile_id
    output["probability_up"] = probability
    output["side"] = np.where(probability >= 0.5, "LONG", "SHORT")
    output["gross_bps"] = np.where(
        probability >= 0.5, output["future_return_bps"], -output["future_return_bps"]
    )
    output["net_bps"] = output["gross_bps"] - COST_BPS
    return output


def run_walkforward(
    daily: pd.DataFrame,
    months: list[str],
    target_features: list[str],
    breadth_features: list[str],
    selected_profile: str | None = None,
) -> pd.DataFrame:
    outputs = []
    profiles = [selected_profile] if selected_profile else list(SELECTABLE_PROFILES)
    for month in months:
        train = daily.loc[daily["month"] < month].copy()
        test = daily.loc[daily["month"].eq(month)].copy()
        if test.empty:
            continue
        if len(train) < 8000:
            raise AssertionError(f"{month}: insufficient pooled history")
        for profile_id in profiles:
            features = (
                target_features
                if profile_id == TARGET_PROFILE
                else target_features + breadth_features
            )
            probability = fit_predict(train, test, features)
            outputs.append(predictions_to_trades(test, probability, profile_id))
    if not outputs:
        raise AssertionError("pooled walk-forward produced no trades")
    return pd.concat(outputs, ignore_index=True).sort_values(
        ["ticker", "trade_date", "window_id", "profile_id"], kind="stable"
    ).reset_index(drop=True)


def monthly_metrics(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (ticker, profile_id, month), group in trades.groupby(
        ["ticker", "profile_id", "month"], sort=True
    ):
        rows.append(
            {"ticker": ticker, "profile_id": profile_id, "month": month, **base.summarize_trades(group)}
        )
    return pd.DataFrame(rows)


def select_global_profile(trades: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    monthly = monthly_metrics(trades)
    rows = []
    for profile_id in SELECTABLE_PROFILES:
        profile_monthly = monthly.loc[monthly["profile_id"].eq(profile_id)]
        by_ticker = []
        for ticker in sorted(trades["ticker"].unique()):
            ticker_monthly = profile_monthly.loc[profile_monthly["ticker"].eq(ticker)]
            ticker_trades = trades.loc[
                trades["ticker"].eq(ticker) & trades["profile_id"].eq(profile_id)
            ]
            if len(ticker_monthly) != 12 or int(ticker_monthly["trades"].min()) <= 12:
                raise AssertionError("incomplete pooled development coverage")
            by_ticker.append(
                {
                    "positive_months": int((ticker_monthly["net_bps"] > 0.0).sum()),
                    "profit_factor": base.profit_factor(ticker_trades["net_bps"]),
                    "monthly_q25": float(ticker_monthly["net_bps"].quantile(0.25)),
                }
            )
        rows.append(
            {
                "profile_id": profile_id,
                "worst_positive_months": min(item["positive_months"] for item in by_ticker),
                "total_positive_months": sum(item["positive_months"] for item in by_ticker),
                "worst_profit_factor": min(item["profit_factor"] for item in by_ticker),
                "worst_monthly_q25": min(item["monthly_q25"] for item in by_ticker),
            }
        )
    ranking = pd.DataFrame(rows).sort_values(
        ["worst_positive_months", "total_positive_months", "worst_profit_factor", "worst_monthly_q25", "profile_id"],
        ascending=[False, False, False, False, True],
        kind="stable",
    ).reset_index(drop=True)
    ranking["rank"] = np.arange(1, len(ranking) + 1)
    ranking["selected"] = ranking["rank"].eq(1)
    return str(ranking.iloc[0]["profile_id"]), ranking


def evaluate_gate(trades: pd.DataFrame, months: list[str]) -> dict:
    monthly = monthly_metrics(trades)
    ticker_metrics = {}
    for ticker in sorted(trades["ticker"].unique()):
        ticker_trades = trades.loc[trades["ticker"].eq(ticker)]
        ticker_monthly = monthly.loc[monthly["ticker"].eq(ticker)]
        if len(ticker_monthly) != len(months):
            raise AssertionError(f"{ticker}: incomplete pooled evaluation months")
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
        "schema": "directional_intraday_pooled_v1_provenance",
        "created_at_utc": base.utc_now(),
        "predeclaration_path": str(PREDECLARATION.relative_to(base.REPO_ROOT)),
        "predeclaration_sha256": base.sha256_file(PREDECLARATION),
        "runner_path": str(Path(__file__).resolve().relative_to(base.REPO_ROOT)),
        "runner_sha256": base.sha256_file(__file__),
        "panel_runner_sha256": base.sha256_file(Path(panel.__file__)),
        "source_inventory_rows": int(len(inventory)),
        "source_inventory_sha256": panel.inventory_digest(inventory),
        "new_dataset_created": False,
        "adaptive_after_prior_2026_diagnostics": True,
        "production_modified": False,
    }


def run_development(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable pooled development output exists: {output}")
    inventory = panel.discover_source_files(Path(args.data_root), base.DEVELOPMENT_END)
    usable = panel.eligible_inventory(inventory)
    if usable["trade_date"].nunique() != 829:
        raise AssertionError("pooled development eligible-session count changed")
    sessions = panel.load_sessions(usable)
    daily, target_features, breadth_features = build_daily_frame(sessions)
    months = [f"2025{month:02d}" for month in range(1, 13)]
    trades = run_walkforward(daily, months, target_features, breadth_features)
    selected_profile, ranking = select_global_profile(trades)
    monthly = monthly_metrics(trades)
    provenance = common_provenance(inventory)
    metrics = {
        "schema": "directional_intraday_pooled_v1_development_metrics",
        "status": "PASS_DEVELOPMENT_FREEZE",
        "created_at_utc": base.utc_now(),
        "scope": {"start_date": base.START_DATE, "end_date": base.DEVELOPMENT_END},
        "eligible_common_sessions": 829,
        "daily_rows": int(len(daily)),
        "target_feature_count": len(target_features),
        "breadth_feature_count": len(breadth_features),
        "selected_profile": selected_profile,
        "holdout_2026_used_for_training_or_selection": False,
        "adaptive_design_after_prior_2026_diagnostics": True,
        "production_modified": False,
    }
    output.mkdir(parents=True, exist_ok=False)
    inventory.to_csv(output / "source_inventory.csv", index=False, lineterminator="\n")
    trades.to_parquet(output / "development_trade_ledger.parquet", index=False)
    monthly.to_csv(output / "development_monthly_metrics.csv", index=False)
    ranking.to_csv(output / "profile_ranking.csv", index=False)
    (output / "target_features.json").write_text(json.dumps(target_features, indent=2), encoding="utf-8")
    (output / "breadth_features.json").write_text(json.dumps(breadth_features, indent=2), encoding="utf-8")
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
    provenance = json.loads((development_dir / "provenance.json").read_text(encoding="utf-8"))
    if metrics.get("status") != "PASS_DEVELOPMENT_FREEZE":
        raise AssertionError("invalid pooled development freeze")
    if provenance.get("predeclaration_sha256") != base.sha256_file(PREDECLARATION):
        raise AssertionError("pooled predeclaration changed")
    if provenance.get("runner_sha256") != base.sha256_file(__file__):
        raise AssertionError("pooled runner changed")
    if provenance.get("panel_runner_sha256") != base.sha256_file(Path(panel.__file__)):
        raise AssertionError("pooled panel runner changed")
    target_features = json.loads((development_dir / "target_features.json").read_text(encoding="utf-8"))
    breadth_features = json.loads((development_dir / "breadth_features.json").read_text(encoding="utf-8"))
    return metrics, provenance, target_features, breadth_features


def verify_development_sources(
    inventory: pd.DataFrame, development_dir: Path, provenance: dict
) -> None:
    frozen = pd.read_csv(development_dir / "source_inventory.csv", dtype={"trade_date": str})
    current = inventory.loc[inventory["trade_date"] <= base.DEVELOPMENT_END].reset_index(drop=True)
    columns = ["ticker", "trade_date", "path", "size_bytes", "sha256"]
    if not frozen[columns].astype(str).equals(current[columns].astype(str)):
        raise AssertionError("pre-2026 pooled source inventory changed")
    if provenance.get("source_inventory_sha256") != panel.inventory_digest(current):
        raise AssertionError("pre-2026 pooled source digest changed")


def run_evaluation(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable pooled evaluation output exists: {output}")
    development_dir = Path(args.development_dir)
    development, frozen_provenance, target_features, breadth_features = load_development(development_dir)
    inventory = panel.discover_source_files(Path(args.data_root), base.EVALUATION_END)
    verify_development_sources(inventory, development_dir, frozen_provenance)
    usable = panel.eligible_inventory(inventory)
    if usable["trade_date"].nunique() != 962:
        raise AssertionError("pooled evaluation eligible-session count changed")
    sessions = panel.load_sessions(usable)
    daily, observed_target, observed_breadth = build_daily_frame(sessions)
    if observed_target != target_features or observed_breadth != breadth_features:
        raise AssertionError("pooled evaluation feature contract changed")
    months = [f"2026{month:02d}" for month in range(1, 8)]
    selected_profile = str(development["selected_profile"])
    trades = run_walkforward(
        daily, months, target_features, breadth_features, selected_profile=selected_profile
    )
    gate = evaluate_gate(trades, months)
    monthly = monthly_metrics(trades)
    metrics = {
        "schema": "directional_intraday_pooled_v1_evaluation_metrics",
        "status": "ADAPTIVE_DIAGNOSTIC_GATE_PASS" if gate["joint_gate_pass"] else "CLOSED_ADAPTIVE_DIAGNOSTIC_GATE",
        "created_at_utc": base.utc_now(),
        "scope": {"start_date": "20260101", "end_date": base.EVALUATION_END, "months": months, "july_status": "MTD_THROUGH_20260715"},
        "selected_profile": selected_profile,
        "eligible_common_sessions": 962,
        "execution": {"windows": WINDOWS, "cost_bps": COST_BPS, "maximum_concurrent_positions": 1, "fill_kind": "underlying_open_spot_proxy_not_futures_fill"},
        **gate,
        "confirmatory_evidence": False,
        "production_modified": False,
    }
    provenance = common_provenance(inventory)
    provenance.update(
        {
            "development_metrics_sha256": base.sha256_file(development_dir / "metrics.json"),
            "development_provenance_sha256": base.sha256_file(development_dir / "provenance.json"),
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
        args.output = str(DEFAULT_DEVELOPMENT_OUTPUT if args.phase == "development" else DEFAULT_EVALUATION_OUTPUT)
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
