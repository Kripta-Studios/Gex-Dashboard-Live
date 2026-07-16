#!/usr/bin/env python3
"""Development-only pooled spot direction from the sealed option-surface frame."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import lightgbm as lgb
import numpy as np
import pandas as pd

from neural.jepa import evaluate_directional_semantic_jepa_v1 as base
from neural.jepa import walkforward_event_option_gate as gate


PREDECLARATION = (
    base.REPO_ROOT
    / "research_papers/JEPA/DIRECTIONAL_OPTION_SURFACE_SPOT_V1_PREDECLARATION.md"
)
DEFAULT_EVENT_DATA = (
    base.REPO_ROOT
    / "tmp/event_option_dataset_execquote_causal1030_202201_202605_v1_physics/"
    "event_option_dataset.parquet"
)
EXPECTED_EVENT_SHA256 = "11e26aaddd91fd441222d552e0362c1d4c2c4489a08d7a6de66479d6eb454fb1"
DEFAULT_OUTPUT = (
    base.REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "directional_option_surface_spot_v1_development_202201_202512"
)
DECISION_TIMES = ("10:35", "11:40", "12:45", "13:50")
PRICE_PROFILE = "PRICE_LEVEL_CONTROL"
SURFACE_PROFILE = "OPTION_SURFACE"
PROFILES = (PRICE_PROFILE, SURFACE_PROFILE)
SURFACE_PREFIXES = ("call_", "put_", "phys_", "ctx_")
COST_BPS = 1.0
SEED = 20260716


def load_event_frame(path: Path) -> pd.DataFrame:
    if base.sha256_file(path).lower() != EXPECTED_EVENT_SHA256:
        raise AssertionError("sealed event dataset hash changed")
    frame = pd.read_parquet(path)
    if len(frame) != 108_156 or len(frame.columns) != 371:
        raise AssertionError("sealed event dataset shape changed")
    if set(frame["expiry_mode"].astype(str)) != {"zero_dte"}:
        raise AssertionError("event dataset is not uniformly zero_dte")
    if set(frame["option_price_mode"].astype(str)) != {"executable_quote"}:
        raise AssertionError("event dataset is not uniformly executable_quote")
    frame["trade_date"] = frame["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    frame = frame[
        (frame["trade_date"] <= "20251231")
        & frame["time"].astype(str).isin(DECISION_TIMES)
        & ~frame["trade_date"].isin(set(base.INVALID_SOURCE_DAYS) | set(base.HALF_DAYS))
    ].copy()
    if frame.duplicated(["ticker", "trade_date", "time"]).any():
        raise AssertionError("duplicate event decision")
    counts = frame.groupby(["trade_date", "time"])["ticker"].nunique()
    common = counts[counts.eq(3)].index
    frame = frame.set_index(["trade_date", "time"]).loc[common].reset_index()
    if frame.groupby(["trade_date", "time"])["ticker"].nunique().ne(3).any():
        raise AssertionError("incomplete common option decision")
    return frame.sort_values(["trade_date", "time", "ticker"], kind="stable").reset_index(drop=True)


def build_live_feature_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    args = SimpleNamespace(
        feature_include_prefixes=[],
        feature_exclude_prefixes=[],
        live_observable_features_only=True,
        entry_time_min_et="10:30",
    )
    work, all_features = gate.build_features(frame, args)
    for feature in all_features:
        low = feature.lower()
        if any(pattern in low for pattern in gate.LEAKY_PATTERNS):
            raise AssertionError(f"leaky feature selected: {feature}")
    price_features = [
        feature for feature in all_features if not feature.lower().startswith(SURFACE_PREFIXES)
    ]
    if not price_features or len(all_features) <= len(price_features):
        raise AssertionError("invalid surface feature partition")
    work[all_features] = work[all_features].replace([np.inf, -np.inf], np.nan)
    return work, price_features, all_features


def add_spot_labels(
    frame: pd.DataFrame, underlying_root: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    inventory = base.discover_source_files(underlying_root, "20251231")
    paths = {
        (str(row.ticker), str(row.trade_date)): str(row.path)
        for row in inventory.itertuples(index=False)
    }
    output = frame.copy()
    output["future_return_bps_v1"] = np.nan
    output["entry_spot_v1"] = np.nan
    output["exit_spot_v1"] = np.nan
    source_by_report = {"QQQ": "QQQ", "SPXW": "SPXW", "SPY": "SPY"}
    for (ticker, day), positions in output.groupby(["ticker", "trade_date"], sort=False).groups.items():
        source = source_by_report[str(ticker)]
        path = paths.get((source, str(day)))
        if path is None:
            continue
        bars = base.validate_bar_frame(pd.read_parquet(path), source, str(day))
        for position in positions:
            decision = pd.Timestamp(f"{str(day)[:4]}-{str(day)[4:6]}-{str(day)[6:]} {output.at[position, 'time']}")
            entry_ts = decision + pd.Timedelta(minutes=1)
            exit_ts = decision + pd.Timedelta(minutes=61)
            if entry_ts not in bars.index or exit_ts not in bars.index:
                continue
            entry = float(bars.loc[entry_ts, "open"])
            exit_price = float(bars.loc[exit_ts, "open"])
            output.at[position, "entry_spot_v1"] = entry
            output.at[position, "exit_spot_v1"] = exit_price
            output.at[position, "future_return_bps_v1"] = float(math.log(exit_price / entry) * 10000.0)
    complete = output.groupby(["trade_date", "time"])["future_return_bps_v1"].apply(
        lambda values: len(values) == 3 and np.isfinite(values).all()
    )
    common = complete[complete].index
    output = output.set_index(["trade_date", "time"]).loc[common].reset_index()
    if output["future_return_bps_v1"].isna().any():
        raise AssertionError("non-finite spot label after common intersection")
    return output, inventory


def magnitude_weights(values: pd.Series) -> np.ndarray:
    magnitude = np.clip(np.abs(values.to_numpy(dtype=np.float64)), 5.0, 100.0)
    median = float(np.median(magnitude))
    if not np.isfinite(median) or median <= 0.0:
        raise AssertionError("invalid spot magnitude weights")
    return magnitude / median


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> np.ndarray:
    labels = (train["future_return_bps_v1"].to_numpy(dtype=np.float64) > 0.0).astype(int)
    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=240,
        learning_rate=0.025,
        num_leaves=15,
        max_depth=4,
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
    model.fit(train[features], labels, sample_weight=magnitude_weights(train["future_return_bps_v1"]))
    return model.predict_proba(test[features])[:, 1].astype(np.float64)


def run_walkforward(
    frame: pd.DataFrame, months: list[str], price_features: list[str], all_features: list[str]
) -> pd.DataFrame:
    outputs = []
    frame = frame.copy()
    frame["month"] = frame["trade_date"].str[:6]
    for month in months:
        train = frame[frame["month"] < month]
        test = frame[frame["month"].eq(month)]
        if len(train) < 3_000 or test.empty:
            raise AssertionError(f"{month}: insufficient surface history")
        for profile_id, features in ((PRICE_PROFILE, price_features), (SURFACE_PROFILE, all_features)):
            probability = fit_predict(train, test, features)
            trades = test[
                ["ticker", "trade_date", "month", "time", "entry_spot_v1", "exit_spot_v1", "future_return_bps_v1"]
            ].copy()
            trades["ticker"] = trades["ticker"].map(base.REPORT_TICKER)
            trades["profile_id"] = profile_id
            trades["probability_up"] = probability
            trades["side"] = np.where(probability >= 0.5, "LONG", "SHORT")
            trades["net_bps"] = np.where(
                probability >= 0.5,
                trades["future_return_bps_v1"],
                -trades["future_return_bps_v1"],
            ) - COST_BPS
            outputs.append(trades)
    return pd.concat(outputs, ignore_index=True).sort_values(
        ["ticker", "trade_date", "time", "profile_id"], kind="stable"
    ).reset_index(drop=True)


def monthly_metrics(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (ticker, profile_id, month), group in trades.groupby(["ticker", "profile_id", "month"], sort=True):
        rows.append({"ticker": ticker, "profile_id": profile_id, "month": month, **base.summarize_trades(group)})
    return pd.DataFrame(rows)


def select_profile(trades: pd.DataFrame) -> tuple[str, pd.DataFrame, bool]:
    monthly = monthly_metrics(trades)
    rows = []
    profile_ticker_metrics: dict[str, list[dict]] = {}
    for profile_id in PROFILES:
        by_ticker = []
        for ticker in sorted(trades["ticker"].unique()):
            ticker_trades = trades[(trades["ticker"].eq(ticker)) & trades["profile_id"].eq(profile_id)]
            ticker_monthly = monthly[(monthly["ticker"].eq(ticker)) & monthly["profile_id"].eq(profile_id)]
            summary = base.summarize_trades(ticker_trades)
            by_ticker.append(
                {
                    "ticker": ticker,
                    **summary,
                    "positive_months": int((ticker_monthly["net_bps"] > 0.0).sum()),
                    "min_month_trades": int(ticker_monthly["trades"].min()),
                    "monthly_q25": float(ticker_monthly["net_bps"].quantile(0.25)),
                }
            )
        profile_ticker_metrics[profile_id] = by_ticker
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
    selected = str(ranking.iloc[0]["profile_id"])
    selected_rows = profile_ticker_metrics[selected]
    advance = selected == SURFACE_PROFILE and all(
        item["profit_factor"] > 1.10
        and item["win_rate"] > 0.45
        and item["positive_months"] >= 8
        and item["min_month_trades"] > 12
        for item in selected_rows
    )
    return selected, ranking, advance


def run(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable surface development output exists: {output}")
    raw = load_event_frame(Path(args.event_data))
    features, price_features, all_features = build_live_feature_frame(raw)
    labeled, underlying_inventory = add_spot_labels(features, Path(args.underlying_root))
    months = [f"2025{month:02d}" for month in range(1, 13)]
    trades = run_walkforward(labeled, months, price_features, all_features)
    selected, ranking, advance = select_profile(trades)
    monthly = monthly_metrics(trades)
    metrics = {
        "schema": "directional_option_surface_spot_v1_development_metrics",
        "status": "PASS_DEVELOPMENT_GATE" if advance else "CLOSED_DEVELOPMENT_NO_EDGE",
        "created_at_utc": base.utc_now(),
        "event_dataset_sha256": EXPECTED_EVENT_SHA256,
        "common_decisions": int(labeled[["trade_date", "time"]].drop_duplicates().shape[0]),
        "labeled_rows": int(len(labeled)),
        "price_feature_count": len(price_features),
        "surface_feature_count": len(all_features),
        "selected_profile": selected,
        "advance_to_2026_evaluation": advance,
        "holdout_2026_opened": False,
        "production_modified": False,
    }
    output.mkdir(parents=True, exist_ok=False)
    trades.to_parquet(output / "development_trade_ledger.parquet", index=False)
    monthly.to_csv(output / "development_monthly_metrics.csv", index=False)
    ranking.to_csv(output / "profile_ranking.csv", index=False)
    underlying_inventory.to_csv(output / "underlying_source_inventory.csv", index=False, lineterminator="\n")
    (output / "price_features.json").write_text(json.dumps(price_features, indent=2), encoding="utf-8")
    (output / "surface_features.json").write_text(json.dumps(all_features, indent=2), encoding="utf-8")
    provenance = {
        "schema": "directional_option_surface_spot_v1_provenance",
        "predeclaration_sha256": base.sha256_file(PREDECLARATION),
        "runner_sha256": base.sha256_file(__file__),
        "event_dataset_sha256": EXPECTED_EVENT_SHA256,
        "underlying_inventory_rows": int(len(underlying_inventory)),
        "underlying_inventory_sha256": hashlib.sha256(
            underlying_inventory.to_csv(index=False, lineterminator="\n").encode("utf-8")
        ).hexdigest(),
        "new_feature_dataset_created": False,
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-data", default=str(DEFAULT_EVENT_DATA))
    parser.add_argument("--underlying-root", default=str(base.DEFAULT_DATA_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
