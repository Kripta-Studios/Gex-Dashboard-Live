#!/usr/bin/env python3
"""Causal pooled cash-direction walk-forward with sealed Globex features."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

import lightgbm as lgb
import numpy as np
import pandas as pd

from neural.jepa import capture_yahoo_futures_60m_v1 as capture
from neural.jepa import evaluate_directional_breadth_transmission_v1 as panel
from neural.jepa import evaluate_directional_semantic_jepa_v1 as base


PREDECLARATION = (
    base.REPO_ROOT
    / "research_papers/JEPA/DIRECTIONAL_GLOBEX_CROSS_ASSET_V1_PREDECLARATION.md"
)
CAPTURE_SEAL = (
    base.REPO_ROOT / "research_papers/JEPA/results/_diagnostics/"
    "yahoo_futures_60m_capture_20240717_20260715_v1/capture_seal.json"
)
DEFAULT_FUTURES_ROOT = capture.DEFAULT_OUTPUT
DEFAULT_DEVELOPMENT_OUTPUT = (
    base.REPO_ROOT / "research_papers/JEPA/results/_diagnostics/"
    "directional_globex_cross_asset_v1_development_202407_202512"
)
DEFAULT_EVALUATION_OUTPUT = (
    base.REPO_ROOT / "research_papers/JEPA/results/_diagnostics/"
    "directional_globex_cross_asset_v1_evaluation_202601_20260715"
)

CONTROL_PROFILE = "POOLED_BREADTH_CONTROL"
GLOBEX_PROFILE = "POOLED_GLOBEX_CROSS_ASSET"
SELECTABLE_PROFILES = (CONTROL_PROFILE, GLOBEX_PROFILE)
TICKER_FEATURES = ("ticker_qqq", "ticker_spx", "ticker_spy")
LATEST_START = {"W1": "09:00", "W2": "12:00"}
SEGMENTS = {
    "overnight": ("18:00", "09:00", -1),
    "asia": ("20:00", "03:00", -1),
    "europe": ("03:00", "09:00", 0),
    "premarket": ("07:00", "09:00", 0),
}
SYMBOL_PREFIX = {
    "ES=F": "es",
    "NQ=F": "nq",
    "YM=F": "ym",
    "RTY=F": "rty",
    "ZN=F": "zn",
    "GC=F": "gc",
    "CL=F": "cl",
}
COST_BPS = 1.0
SEED = 20260716


def _et_timestamp(day: str, clock: str, day_offset: int = 0) -> pd.Timestamp:
    date = pd.Timestamp(day) + pd.Timedelta(days=day_offset)
    return pd.Timestamp(f"{date:%Y-%m-%d} {clock}", tz="America/New_York")


def _source_rows_by_symbol(document: dict) -> dict[str, dict]:
    rows = document.get("sources") or []
    mapping = {str(row.get("symbol")): row for row in rows}
    if set(mapping) != set(capture.SYMBOLS) or len(rows) != len(mapping):
        raise AssertionError("futures manifest symbol contract changed")
    return mapping


def load_futures_bundle(
    root: Path,
) -> tuple[dict[str, pd.DataFrame], dict, pd.DataFrame]:
    seal = json.loads(CAPTURE_SEAL.read_text(encoding="utf-8"))
    manifest_path = root / "manifest.json"
    if base.sha256_file(manifest_path) != seal.get("manifest_sha256"):
        raise AssertionError("futures capture manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("status") != "PASS_YAHOO_FUTURES_CAPTURE"
        or manifest.get("period1") != capture.PERIOD1
        or manifest.get("period2") != capture.PERIOD2
        or manifest.get("symbols") != list(capture.SYMBOLS)
    ):
        raise AssertionError("invalid futures capture manifest")
    manifest_rows = _source_rows_by_symbol(manifest)
    seal_rows = _source_rows_by_symbol(seal)
    frames: dict[str, pd.DataFrame] = {}
    inventory_rows = []
    for symbol in capture.SYMBOLS:
        manifest_row = manifest_rows[symbol]
        seal_row = seal_rows[symbol]
        if any(
            manifest_row.get(key) != seal_row.get(key)
            for key in ("filename", "bytes", "sha256", "rows", "frozen_rows")
        ):
            raise AssertionError(f"{symbol}: capture seal mismatch")
        path = root / str(manifest_row["filename"])
        payload = path.read_bytes()
        if len(payload) != int(manifest_row["bytes"]):
            raise AssertionError(f"{symbol}: raw size mismatch")
        if capture.sha256_bytes(payload) != manifest_row["sha256"]:
            raise AssertionError(f"{symbol}: raw hash mismatch")
        audit = capture.validate_payload(payload, symbol)
        for key in (
            "rows",
            "frozen_rows",
            "complete_ohlc_rows",
            "outside_frozen_rows",
        ):
            if audit[key] != manifest_row[key]:
                raise AssertionError(f"{symbol}: raw audit mismatch for {key}")
        result = json.loads(payload)["chart"]["result"][0]
        quote = result["indicators"]["quote"][0]
        frame = pd.DataFrame(
            {
                "timestamp_epoch": result["timestamp"],
                "open": quote["open"],
                "high": quote["high"],
                "low": quote["low"],
                "close": quote["close"],
                "volume": quote["volume"],
            }
        )
        frame = frame.loc[
            frame["timestamp_epoch"].ge(capture.PERIOD1)
            & frame["timestamp_epoch"].lt(capture.PERIOD2)
        ].copy()
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        complete = np.isfinite(frame[["open", "high", "low", "close", "volume"]]).all(
            axis=1
        )
        complete &= frame["volume"].ge(0.0)
        frame = frame.loc[complete].copy()
        frame["timestamp"] = pd.to_datetime(
            frame["timestamp_epoch"], unit="s", utc=True
        ).dt.tz_convert("America/New_York")
        frame = frame.set_index("timestamp").sort_index()
        if frame.index.has_duplicates:
            raise AssertionError(f"{symbol}: duplicate complete timestamp")
        frames[symbol] = frame[["open", "high", "low", "close", "volume"]]
        inventory_rows.append(
            {
                "symbol": symbol,
                "path": str(path.resolve()),
                "size_bytes": path.stat().st_size,
                "sha256": manifest_row["sha256"],
                "complete_rows_with_volume": int(len(frame)),
            }
        )
    common = frames[capture.SYMBOLS[0]].index
    for symbol in capture.SYMBOLS[1:]:
        common = common.intersection(frames[symbol].index, sort=False)
    common = common.sort_values()
    if len(common) < 10_000:
        raise AssertionError("insufficient joint complete futures timestamps")
    frames = {symbol: frame.loc[common].copy() for symbol, frame in frames.items()}
    inventory = (
        pd.DataFrame(inventory_rows).sort_values("symbol").reset_index(drop=True)
    )
    return frames, manifest, inventory


def _clipped_return(start: float, end: float) -> float:
    raw = math.log(end / start) * 10_000.0
    return float(np.clip(raw, -300.0, 300.0))


def _exact_rows(
    frame: pd.DataFrame, timestamps: Iterable[pd.Timestamp]
) -> pd.DataFrame | None:
    requested = list(timestamps)
    if any(timestamp not in frame.index for timestamp in requested):
        return None
    return frame.loc[requested]


def extract_futures_features(
    frames: dict[str, pd.DataFrame], day: str, window_id: str
) -> tuple[dict[str, float] | None, str | None]:
    if set(frames) != set(capture.SYMBOLS):
        raise AssertionError("incomplete futures frame mapping")
    cutoff = _et_timestamp(day, LATEST_START[window_id])
    recent_times = [cutoff - pd.Timedelta(hours=offset) for offset in range(6, -1, -1)]
    values: dict[str, float] = {}
    six_hour_returns: dict[str, float] = {}
    for symbol in capture.SYMBOLS:
        frame = frames[symbol]
        recent = _exact_rows(frame, recent_times)
        if recent is None:
            return None, f"{symbol}:missing_recent_hour"
        rolling = frame.loc[frame.index <= cutoff].tail(20)
        if len(rolling) != 20:
            return None, f"{symbol}:missing_volume_history"
        prefix = SYMBOL_PREFIX[symbol]
        for horizon in (1, 3, 6):
            window = recent.iloc[-horizon:]
            values[f"{prefix}_ret_{horizon}h"] = _clipped_return(
                float(window["open"].iloc[0]), float(window["close"].iloc[-1])
            )
            if horizon == 1:
                continue
            intrabar = (
                np.log(
                    window["close"].to_numpy(dtype=np.float64)
                    / window["open"].to_numpy(dtype=np.float64)
                )
                * 10_000.0
            )
            values[f"{prefix}_range_{horizon}h"] = float(
                (float(window["high"].max()) - float(window["low"].min()))
                / float(window["close"].iloc[-1])
                * 10_000.0
            )
            values[f"{prefix}_rv_{horizon}h"] = float(
                np.sqrt(np.square(np.clip(intrabar, -300.0, 300.0)).sum())
            )
        for name, (start_clock, end_clock, start_offset) in SEGMENTS.items():
            start = _et_timestamp(day, start_clock, start_offset)
            end = _et_timestamp(day, end_clock)
            rows = _exact_rows(frame, (start, end))
            if rows is None:
                return None, f"{symbol}:missing_{name}_endpoint"
            values[f"{prefix}_{name}_return"] = _clipped_return(
                float(rows["open"].iloc[0]), float(rows["open"].iloc[1])
            )
        latest_volume = float(recent["volume"].iloc[-1])
        median_volume = float(rolling["volume"].median())
        values[f"{prefix}_volume_1h"] = float(np.log1p(latest_volume))
        values[f"{prefix}_volume_ratio_20"] = float(
            latest_volume / max(median_volume, 1.0)
        )
        close_to_close = (
            np.diff(np.log(recent["close"].to_numpy(dtype=np.float64))) * 10_000.0
        )
        open_to_close = (
            np.log(
                recent["close"].to_numpy(dtype=np.float64)
                / recent["open"].to_numpy(dtype=np.float64)
            )
            * 10_000.0
        )
        values[f"{prefix}_roll_jump_gt_200bps"] = float(
            np.max(np.abs(np.concatenate((close_to_close, open_to_close)))) > 200.0
        )
        six_hour_returns[symbol] = values[f"{prefix}_ret_6h"]
    spreads = {
        "spread_es_nq_6h": six_hour_returns["ES=F"] - six_hour_returns["NQ=F"],
        "spread_es_rty_6h": six_hour_returns["ES=F"] - six_hour_returns["RTY=F"],
        "spread_es_zn_6h": six_hour_returns["ES=F"] - six_hour_returns["ZN=F"],
        "spread_gc_zn_6h": six_hour_returns["GC=F"] - six_hour_returns["ZN=F"],
        "spread_cl_zn_6h": six_hour_returns["CL=F"] - six_hour_returns["ZN=F"],
    }
    values.update(spreads)
    if not np.isfinite(np.asarray(list(values.values()), dtype=np.float64)).all():
        raise AssertionError(f"{day} {window_id}: non-finite futures feature")
    return values, None


def build_joint_daily_frame(
    sessions: dict[str, dict[str, pd.DataFrame]],
    futures_frames: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, list[str], list[str], dict]:
    cash, target_features, breadth_features = panel.build_daily_frame(sessions)
    for feature in TICKER_FEATURES:
        ticker = feature.removeprefix("ticker_").upper()
        cash[feature] = cash["ticker"].eq(ticker).astype(float)
    cash_features = target_features + breadth_features + list(TICKER_FEATURES)
    keys = (
        cash[["trade_date", "window_id"]]
        .drop_duplicates()
        .sort_values(["trade_date", "window_id"], kind="stable")
    )
    futures_rows = []
    drop_reasons: dict[str, int] = {}
    futures_features: list[str] | None = None
    for key in keys.itertuples(index=False):
        values, reason = extract_futures_features(
            futures_frames, str(key.trade_date), str(key.window_id)
        )
        if values is None:
            drop_reasons[str(reason)] = drop_reasons.get(str(reason), 0) + 1
            continue
        names = list(values)
        if futures_features is None:
            futures_features = names
        elif names != futures_features:
            raise AssertionError("futures feature order changed")
        futures_rows.append(
            {
                "trade_date": str(key.trade_date),
                "window_id": str(key.window_id),
                **values,
            }
        )
    if not futures_rows or futures_features is None:
        raise AssertionError("no joint futures decisions")
    futures_daily = pd.DataFrame(futures_rows)
    daily = cash.merge(
        futures_daily,
        on=["trade_date", "window_id"],
        how="inner",
        validate="many_to_one",
    ).sort_values(["trade_date", "window_id", "ticker"], kind="stable")
    daily = daily.reset_index(drop=True)
    features = cash_features + futures_features
    if (
        daily[features].isna().any().any()
        or not np.isfinite(daily[features]).all().all()
    ):
        raise AssertionError("joint features contain non-finite values")
    counts = daily.groupby(["trade_date", "window_id"]).size()
    if not counts.eq(len(panel.TARGETS)).all():
        raise AssertionError("a futures gap was not dropped for all target tickers")
    coverage = {
        "candidate_common_cash_decisions": int(len(keys)),
        "eligible_joint_decisions": int(len(futures_daily)),
        "dropped_joint_decisions": int(len(keys) - len(futures_daily)),
        "drop_reasons": dict(sorted(drop_reasons.items())),
        "eligible_rows_all_targets": int(len(daily)),
    }
    return daily, cash_features, futures_features, coverage


def fit_predict(
    train: pd.DataFrame, test: pd.DataFrame, feature_names: list[str]
) -> np.ndarray:
    labels = (train["future_return_bps"].to_numpy(dtype=np.float64) > 0.0).astype(int)
    if len(np.unique(labels)) != 2:
        raise AssertionError("Globex pooled fold lacks both directions")
    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=240,
        learning_rate=0.025,
        num_leaves=15,
        max_depth=4,
        min_child_samples=60,
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
        train[feature_names],
        labels,
        sample_weight=panel.magnitude_weights(train["future_return_bps"]),
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
    output["gross_bps"] = np.where(
        probability >= 0.5, output["future_return_bps"], -output["future_return_bps"]
    )
    output["net_bps"] = output["gross_bps"] - COST_BPS
    return output


def run_walkforward(
    daily: pd.DataFrame,
    months: list[str],
    cash_features: list[str],
    futures_features: list[str],
    selected_profile: str | None = None,
) -> pd.DataFrame:
    profiles = [selected_profile] if selected_profile else list(SELECTABLE_PROFILES)
    outputs = []
    for month in months:
        train = daily.loc[daily["month"] < month].copy()
        test = daily.loc[daily["month"].eq(month)].copy()
        if test.empty:
            raise AssertionError(f"{month}: no joint Globex test decisions")
        if len(train) < 500:
            raise AssertionError(f"{month}: insufficient joint chronological history")
        for profile_id in profiles:
            features = (
                cash_features
                if profile_id == CONTROL_PROFILE
                else cash_features + futures_features
            )
            probability = fit_predict(train, test, features)
            outputs.append(predictions_to_trades(test, probability, str(profile_id)))
    return (
        pd.concat(outputs, ignore_index=True)
        .sort_values(["ticker", "trade_date", "window_id", "profile_id"], kind="stable")
        .reset_index(drop=True)
    )


def monthly_metrics(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (ticker, profile_id, month), group in trades.groupby(
        ["ticker", "profile_id", "month"], sort=True
    ):
        rows.append(
            {
                "ticker": ticker,
                "profile_id": profile_id,
                "month": month,
                **base.summarize_trades(group),
            }
        )
    return pd.DataFrame(rows)


def select_global_profile(trades: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    monthly = monthly_metrics(trades)
    rows = []
    for profile_id in SELECTABLE_PROFILES:
        by_ticker = []
        for ticker in sorted(trades["ticker"].unique()):
            ticker_monthly = monthly.loc[
                monthly["ticker"].eq(ticker) & monthly["profile_id"].eq(profile_id)
            ]
            ticker_trades = trades.loc[
                trades["ticker"].eq(ticker) & trades["profile_id"].eq(profile_id)
            ]
            if len(ticker_monthly) != 12 or int(ticker_monthly["trades"].min()) <= 12:
                raise AssertionError("incomplete Globex development coverage")
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
                "worst_positive_months": min(
                    item["positive_months"] for item in by_ticker
                ),
                "total_positive_months": sum(
                    item["positive_months"] for item in by_ticker
                ),
                "worst_profit_factor": min(item["profit_factor"] for item in by_ticker),
                "worst_monthly_q25": min(item["monthly_q25"] for item in by_ticker),
            }
        )
    ranking = (
        pd.DataFrame(rows)
        .sort_values(
            [
                "worst_positive_months",
                "total_positive_months",
                "worst_profit_factor",
                "worst_monthly_q25",
                "profile_id",
            ],
            ascending=[False, False, False, False, True],
            kind="stable",
        )
        .reset_index(drop=True)
    )
    ranking["rank"] = np.arange(1, len(ranking) + 1)
    ranking["selected"] = ranking["rank"].eq(1)
    return str(ranking.iloc[0]["profile_id"]), ranking


def development_gate(trades: pd.DataFrame, selected_profile: str) -> dict:
    monthly = monthly_metrics(trades.loc[trades["profile_id"].eq(selected_profile)])
    ticker_metrics = {}
    for ticker in sorted(trades["ticker"].unique()):
        ticker_trades = trades.loc[
            trades["ticker"].eq(ticker) & trades["profile_id"].eq(selected_profile)
        ]
        ticker_monthly = monthly.loc[monthly["ticker"].eq(ticker)]
        summary = base.summarize_trades(ticker_trades)
        positive_months = int((ticker_monthly["net_bps"] > 0.0).sum())
        minimum = int(ticker_monthly["trades"].min())
        passed = (
            summary["profit_factor"] > 1.10
            and summary["win_rate"] > 0.45
            and positive_months >= 8
            and minimum > 12
        )
        ticker_metrics[ticker] = {
            **summary,
            "positive_months": positive_months,
            "min_month_trades": minimum,
            "gate_pass": passed,
        }
    advance = selected_profile == GLOBEX_PROFILE and all(
        item["gate_pass"] for item in ticker_metrics.values()
    )
    return {"ticker_metrics": ticker_metrics, "advance_to_2026": advance}


def evaluation_gate(trades: pd.DataFrame, months: list[str]) -> dict:
    monthly = monthly_metrics(trades)
    ticker_metrics = {}
    for ticker in sorted(trades["ticker"].unique()):
        ticker_trades = trades.loc[trades["ticker"].eq(ticker)]
        ticker_monthly = monthly.loc[monthly["ticker"].eq(ticker)]
        if sorted(ticker_monthly["month"].tolist()) != months:
            raise AssertionError(f"{ticker}: incomplete 2026-Jul evaluation coverage")
        summary = base.summarize_trades(ticker_trades)
        positive_months = int((ticker_monthly["net_bps"] > 0.0).sum())
        minimum = int(ticker_monthly["trades"].min())
        passed = (
            summary["profit_factor"] > 1.20
            and summary["win_rate"] > 0.45
            and positive_months == len(months)
            and minimum > 12
        )
        ticker_metrics[ticker] = {
            **summary,
            "positive_months": positive_months,
            "evaluated_months": len(months),
            "min_month_trades": minimum,
            "gate_pass": passed,
        }
    return {
        "ticker_metrics": ticker_metrics,
        "joint_gate_pass": all(item["gate_pass"] for item in ticker_metrics.values()),
    }


def _common_provenance(
    cash_inventory: pd.DataFrame, futures_inventory: pd.DataFrame
) -> dict:
    return {
        "schema": "directional_globex_cross_asset_v1_provenance",
        "created_at_utc": base.utc_now(),
        "predeclaration_sha256": base.sha256_file(PREDECLARATION),
        "runner_sha256": base.sha256_file(__file__),
        "panel_runner_sha256": base.sha256_file(Path(panel.__file__)),
        "capture_runner_sha256": base.sha256_file(Path(capture.__file__)),
        "capture_seal_sha256": base.sha256_file(CAPTURE_SEAL),
        "capture_manifest_sha256": json.loads(CAPTURE_SEAL.read_text(encoding="utf-8"))[
            "manifest_sha256"
        ],
        "cash_inventory_rows": int(len(cash_inventory)),
        "cash_inventory_sha256": panel.inventory_digest(cash_inventory),
        "futures_inventory": futures_inventory.to_dict("records"),
        "futures_source_kind": "Yahoo continuous futures 60m research proxy",
        "new_feature_dataset_created": False,
        "holdout_2026_used_for_selection": False,
        "production_modified": False,
    }


def run_development(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable Globex development output exists: {output}")
    cash_inventory = panel.discover_source_files(
        Path(args.data_root), base.DEVELOPMENT_END
    )
    usable = panel.eligible_inventory(cash_inventory)
    if usable["trade_date"].nunique() != 829:
        raise AssertionError("Globex development cash-session census changed")
    sessions = panel.load_sessions(usable)
    futures_frames, _, futures_inventory = load_futures_bundle(Path(args.futures_root))
    daily, cash_features, futures_features, coverage = build_joint_daily_frame(
        sessions, futures_frames
    )
    months = [f"2025{month:02d}" for month in range(1, 13)]
    trades = run_walkforward(daily, months, cash_features, futures_features)
    selected_profile, ranking = select_global_profile(trades)
    gate = development_gate(trades, selected_profile)
    monthly = monthly_metrics(trades)
    metrics = {
        "schema": "directional_globex_cross_asset_v1_development_metrics",
        "status": (
            "PASS_DEVELOPMENT_SELECTION"
            if gate["advance_to_2026"]
            else "CLOSED_DEVELOPMENT_GATE"
        ),
        "created_at_utc": base.utc_now(),
        "scope": {"start_date": "20240717", "end_date": base.DEVELOPMENT_END},
        "selected_profile": selected_profile,
        "cash_feature_count": len(cash_features),
        "futures_feature_count": len(futures_features),
        "daily_rows": int(len(daily)),
        "coverage": coverage,
        **gate,
        "holdout_2026_used_for_training_or_selection": False,
        "adaptive_design_after_prior_2026_diagnostics": True,
        "production_modified": False,
    }
    provenance = _common_provenance(cash_inventory, futures_inventory)
    output.mkdir(parents=True, exist_ok=False)
    cash_inventory.to_csv(
        output / "cash_source_inventory.csv", index=False, lineterminator="\n"
    )
    futures_inventory.to_csv(
        output / "futures_source_inventory.csv", index=False, lineterminator="\n"
    )
    trades.to_parquet(output / "development_trade_ledger.parquet", index=False)
    monthly.to_csv(output / "development_monthly_metrics.csv", index=False)
    ranking.to_csv(output / "profile_ranking.csv", index=False)
    (output / "cash_features.json").write_text(
        json.dumps(cash_features, indent=2), encoding="utf-8"
    )
    (output / "futures_features.json").write_text(
        json.dumps(futures_features, indent=2), encoding="utf-8"
    )
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    metrics["provenance_sha256"] = base.sha256_file(output / "provenance.json")
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
    return metrics


def _load_development(development_dir: Path) -> tuple[dict, dict, list[str], list[str]]:
    metrics = json.loads((development_dir / "metrics.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (development_dir / "provenance.json").read_text(encoding="utf-8")
    )
    if (
        metrics.get("status") != "PASS_DEVELOPMENT_SELECTION"
        or not metrics.get("advance_to_2026")
        or metrics.get("selected_profile") != GLOBEX_PROFILE
    ):
        raise AssertionError("Globex development did not authorize 2026 evaluation")
    checks = {
        "predeclaration_sha256": base.sha256_file(PREDECLARATION),
        "runner_sha256": base.sha256_file(__file__),
        "panel_runner_sha256": base.sha256_file(Path(panel.__file__)),
        "capture_runner_sha256": base.sha256_file(Path(capture.__file__)),
        "capture_seal_sha256": base.sha256_file(CAPTURE_SEAL),
    }
    for key, expected in checks.items():
        if provenance.get(key) != expected:
            raise AssertionError(f"frozen Globex provenance changed: {key}")
    cash_features = json.loads(
        (development_dir / "cash_features.json").read_text(encoding="utf-8")
    )
    futures_features = json.loads(
        (development_dir / "futures_features.json").read_text(encoding="utf-8")
    )
    return metrics, provenance, cash_features, futures_features


def _verify_development_cash_sources(
    inventory: pd.DataFrame, development_dir: Path, provenance: dict
) -> None:
    frozen = pd.read_csv(
        development_dir / "cash_source_inventory.csv", dtype={"trade_date": str}
    )
    current = inventory.loc[
        inventory["trade_date"] <= base.DEVELOPMENT_END
    ].reset_index(drop=True)
    columns = ["ticker", "trade_date", "path", "size_bytes", "sha256"]
    if not frozen[columns].astype(str).equals(current[columns].astype(str)):
        raise AssertionError("pre-2026 Globex cash inventory changed")
    if provenance.get("cash_inventory_sha256") != panel.inventory_digest(current):
        raise AssertionError("pre-2026 Globex cash inventory digest changed")


def run_evaluation(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable Globex evaluation output exists: {output}")
    development_dir = Path(args.development_dir)
    development, frozen_provenance, cash_features, futures_features = _load_development(
        development_dir
    )
    cash_inventory = panel.discover_source_files(
        Path(args.data_root), base.EVALUATION_END
    )
    _verify_development_cash_sources(cash_inventory, development_dir, frozen_provenance)
    usable = panel.eligible_inventory(cash_inventory)
    if usable["trade_date"].nunique() != 962:
        raise AssertionError("Globex evaluation cash-session census changed")
    sessions = panel.load_sessions(usable)
    futures_frames, _, futures_inventory = load_futures_bundle(Path(args.futures_root))
    daily, observed_cash, observed_futures, coverage = build_joint_daily_frame(
        sessions, futures_frames
    )
    if observed_cash != cash_features or observed_futures != futures_features:
        raise AssertionError("Globex evaluation feature contract changed")
    months = [f"2026{month:02d}" for month in range(1, 8)]
    trades = run_walkforward(
        daily,
        months,
        cash_features,
        futures_features,
        selected_profile=str(development["selected_profile"]),
    )
    gate = evaluation_gate(trades, months)
    monthly = monthly_metrics(trades)
    metrics = {
        "schema": "directional_globex_cross_asset_v1_evaluation_metrics",
        "status": "PASS_2026_JUL_GATE"
        if gate["joint_gate_pass"]
        else "CLOSED_2026_JUL_GATE",
        "created_at_utc": base.utc_now(),
        "scope": {
            "start_date": "20260101",
            "end_date": base.EVALUATION_END,
            "months": months,
            "july_status": "MTD_THROUGH_20260715",
        },
        "selected_profile": development["selected_profile"],
        "coverage": coverage,
        "execution": {
            "windows": panel.WINDOWS,
            "cost_bps": COST_BPS,
            "maximum_concurrent_positions": 1,
            "fill_kind": "underlying_open_spot_proxy_not_futures_fill",
        },
        **gate,
        "confirmatory_evidence": False,
        "production_modified": False,
    }
    provenance = _common_provenance(cash_inventory, futures_inventory)
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
    cash_inventory.to_csv(
        output / "cash_source_inventory.csv", index=False, lineterminator="\n"
    )
    futures_inventory.to_csv(
        output / "futures_source_inventory.csv", index=False, lineterminator="\n"
    )
    trades.to_parquet(output / "trade_ledger.parquet", index=False)
    monthly.to_csv(output / "monthly_metrics.csv", index=False)
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
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
    parser.add_argument("--futures-root", default=str(DEFAULT_FUTURES_ROOT))
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
