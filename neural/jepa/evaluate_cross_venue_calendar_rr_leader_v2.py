#!/usr/bin/env python3
"""Evaluate the frozen 2023-2024 development protocol for cross-venue V2."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow
import pyarrow.parquet as pq
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa.build_calendar_risk_reversal_pressure_v1 import (  # noqa: E402
    canonical_date,
    tracked_clean,
)


PROJECT_ROOT = SCRIPT_REPO_ROOT
TICKERS = ("QQQ", "SPXW", "SPY")
SENSOR_MAP = {"QQQ": "QQQ", "SPXW": "SPY", "SPY": "SPY"}
MIN_WIN_RATE = 0.45
INCREMENTAL_MIN_PF = 1.0
OBJECTIVE_MIN_PF = 1.20
MIN_MONTH_TRADES_EXCLUSIVE = 12
COSTS_BPS = (1.0, 2.0, 3.0)
MODEL_C = 0.1
MODEL_THRESHOLD = 0.5
EARLY_START = "09:30:00"
EARLY_END = "10:35:00"
EARLY_CLOCK_COUNT = 66
EARLY_RETURN_COUNT = 65

PREDECLARATION = PROJECT_ROOT / (
    "research_papers/JEPA/"
    "CROSS_VENUE_CALENDAR_RR_LEADER_V2_TEMPORAL_ORIENTATION_PREDECLARATION.md"
)
DATA_2023 = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "calendar_risk_reversal_pressure_v1_202301_202312_v1_data_gate"
)
RESULT_2023 = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "calendar_risk_reversal_pressure_v1_development_202301_202312_v1"
)
DATA_2024 = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v1_data_gate_202401_202512_v1r1"
)
RESULT_2024 = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v1_outer_2024_v1"
)
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v2_development_202301_202412_v1"
)

INPUTS = {
    DATA_2023 / "calendar_rr_features.parquet": (
        "de0ec4b3251505b763dff3dc8baee2f3462ca7a5833d70ed6db014b03112858b"
    ),
    DATA_2023 / "source_inventory.csv": (
        "6f81e4f8cc102f63c60e23c04d0c13d7a5be4af535c745f2dc5ec2646a2184d8"
    ),
    RESULT_2023 / "trades.csv": (
        "9c5178045e4172e6bfaf6d7bf30eb07a6ae68ff66a3bb8b738965de1e0d0fa66"
    ),
    DATA_2024 / "cross_venue_calendar_rr_features.parquet": (
        "fd2953bd9bc918b95079d494663cf7ca2fc9dfe141604b8e8803cc2bf605d268"
    ),
    DATA_2024 / "source_inventory.csv": (
        "b63ca25185627528b1bc22ad937dcb834dbb4846d03b451aa395a62003d4c56c"
    ),
    RESULT_2024 / "trades.csv": (
        "d989f586749738b75bb3c62c69d189d0e6e29b3106d060a1332c956af2917aa4"
    ),
}

OPTION_FEATURES = (
    "signal_pressure",
    "abs_signal_pressure",
    "calendar_rr_t0",
    "front_rr_t0",
    "back_rr_t0",
    "front_rr_change",
    "back_rr_change",
    "option_spot_return_5m_bps",
)
CASH_METRICS = (
    "return_0930_1035_bps",
    "return_1000_1035_bps",
    "return_1030_1035_bps",
    "open_return_std_bps",
    "open_range_bps",
    "positive_open_return_fraction",
)
FEATURE_COLUMNS = (
    *OPTION_FEATURES,
    *(f"qqq_{name}" for name in CASH_METRICS),
    *(f"spy_{name}" for name in CASH_METRICS),
    *(f"spxw_{name}" for name in CASH_METRICS),
    "ticker_QQQ",
    "ticker_SPXW",
    "ticker_SPY",
)
if len(FEATURE_COLUMNS) != 29:
    raise AssertionError("V2 feature vector must contain exactly 29 columns")

BLOCKS = {
    "DEV_A": {
        "train_start": "202301",
        "train_end": "202312",
        "test_start": "202401",
        "test_end": "202406",
    },
    "DEV_B": {
        "train_start": "202301",
        "train_end": "202406",
        "test_start": "202407",
        "test_end": "202412",
    },
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_digest(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def current_git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def verify_inputs() -> None:
    tracked_clean(Path(__file__).resolve(), "V2 evaluator")
    tracked_clean(PREDECLARATION, "V2 predeclaration")
    for path, expected in INPUTS.items():
        if not path.is_file() or sha256_file(path) != expected:
            raise AssertionError(f"V2 frozen input changed: {path}")
    versions = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pyarrow": pyarrow.__version__,
        "scikit_learn": sklearn.__version__,
    }
    expected = {
        "python": "3.14.2",
        "numpy": "2.3.5",
        "pandas": "3.0.0",
        "pyarrow": "23.0.1",
        "scikit_learn": "1.8.0",
    }
    if versions != expected:
        raise AssertionError(f"V2 frozen runtime changed: {versions}")


def _canonical_feature_view(frame: pd.DataFrame, valid_column: str) -> pd.DataFrame:
    required = {
        "ticker",
        "trade_date",
        valid_column,
        "calendar_rr_pressure",
        "calendar_rr_t0",
        "front_rr_t0",
        "front_rr_t1",
        "back_rr_t0",
        "back_rr_t1",
        "spot_t0",
        "spot_t1",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError(f"V2 option view lacks fields: {missing}")
    output = frame.loc[frame[valid_column]].copy()
    output["ticker"] = output["ticker"].astype(str).str.upper().str.strip()
    output["trade_date"] = output["trade_date"].map(canonical_date)
    numeric = tuple(required.difference({"ticker", "trade_date", valid_column}))
    for column in numeric:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    if (
        output.duplicated(["ticker", "trade_date"]).any()
        or not set(output["ticker"]).issubset(set(TICKERS))
        or not np.isfinite(output[list(numeric)].to_numpy(dtype=float)).all()
        or not output["spot_t0"].gt(0.0).all()
        or not output["spot_t1"].gt(0.0).all()
    ):
        raise AssertionError("V2 option view violates frozen identity")
    return output


def load_option_features() -> pd.DataFrame:
    frame_2023 = pd.read_parquet(DATA_2023 / "calendar_rr_features.parquet")
    frame_2023 = _canonical_feature_view(frame_2023, "feature_valid")
    frame_2023 = frame_2023.loc[frame_2023["trade_date"].str.startswith("2023")]
    frame_2024 = pd.read_parquet(
        DATA_2024 / "cross_venue_calendar_rr_features.parquet",
        filters=[("year", "==", "2024")],
    )
    frame_2024 = _canonical_feature_view(frame_2024, "local_feature_valid")
    if not frame_2024["trade_date"].str.startswith("2024").all():
        raise AssertionError("V2 materialized a non-2024 V1R1 feature row")
    output = pd.concat([frame_2023, frame_2024], ignore_index=True)
    output["signal_pressure"] = output["calendar_rr_pressure"]
    output["abs_signal_pressure"] = output["signal_pressure"].abs()
    output["front_rr_change"] = output["front_rr_t1"] - output["front_rr_t0"]
    output["back_rr_change"] = output["back_rr_t1"] - output["back_rr_t0"]
    output["option_spot_return_5m_bps"] = (
        np.log(output["spot_t1"] / output["spot_t0"]) * 10_000.0
    )
    return output[["ticker", "trade_date", *OPTION_FEATURES]].copy()


def _read_ledger(path: Path, year: str) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"trade_date": str, "month": str})
    required = {"ticker", "trade_date", "month", "underlying_return_bps"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError(f"V2 sealed ledger lacks fields: {missing}")
    frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    frame["trade_date"] = frame["trade_date"].map(canonical_date)
    frame["month"] = frame["trade_date"].str[:6]
    frame["underlying_return_bps"] = pd.to_numeric(
        frame["underlying_return_bps"], errors="coerce"
    )
    frame["sealed_signal_pressure"] = (
        pd.to_numeric(frame["signal_pressure"], errors="raise")
        if "signal_pressure" in frame.columns
        else np.nan
    )
    if (
        frame.empty
        or frame.duplicated(["ticker", "trade_date"]).any()
        or set(frame["ticker"]) != set(TICKERS)
        or not frame["trade_date"].str.startswith(year).all()
        or not np.isfinite(frame["underlying_return_bps"].to_numpy()).all()
    ):
        raise AssertionError(f"V2 sealed {year} ledger identity failed")
    return frame[
        [
            "ticker",
            "trade_date",
            "month",
            "underlying_return_bps",
            "sealed_signal_pressure",
        ]
    ].copy()


def load_development_rows(option_features: pd.DataFrame) -> pd.DataFrame:
    ledger_2023 = _read_ledger(RESULT_2023 / "trades.csv", "2023")
    ledger_2024 = _read_ledger(RESULT_2024 / "trades.csv", "2024")
    ledger = pd.concat([ledger_2023, ledger_2024], ignore_index=True)
    ledger["sensor_ticker"] = ledger["ticker"].map(SENSOR_MAP)
    sensor = option_features.rename(columns={"ticker": "sensor_ticker"})
    output = ledger.merge(
        sensor,
        on=["sensor_ticker", "trade_date"],
        how="left",
        validate="many_to_one",
    )
    if output[list(OPTION_FEATURES)].isna().any().any():
        raise AssertionError("V2 exact-date option sensor mapping is incomplete")
    base_side = np.sign(output["signal_pressure"]).astype(np.int64)
    if not np.isin(base_side, [-1, 1]).all():
        raise AssertionError("V2 signal pressure contains a zero action")
    output["base_side"] = base_side
    output["base_gross_bps"] = (
        output["base_side"] * output["underlying_return_bps"]
    )
    output["direct_win"] = (output["base_gross_bps"] > 0.0).astype(np.int64)

    stored_2024 = ledger_2024[
        ["ticker", "trade_date", "sealed_signal_pressure"]
    ].copy()
    check = output.loc[output["trade_date"].str.startswith("2024")].merge(
        stored_2024,
        on=["ticker", "trade_date"],
        validate="one_to_one",
    )
    if not np.allclose(
        check["signal_pressure"],
        check["sealed_signal_pressure"],
        rtol=0.0,
        atol=1e-12,
    ):
        raise AssertionError("V2 does not reproduce the sealed V1 2024 mapping")
    return output.sort_values(["trade_date", "ticker"], kind="stable").reset_index(
        drop=True
    )


def load_underlying_inventory() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year, path in (
        ("2023", DATA_2023 / "source_inventory.csv"),
        ("2024", DATA_2024 / "source_inventory.csv"),
    ):
        frame = pd.read_csv(path, dtype={"trade_date": str, "sha256": str})
        required = {"ticker", "trade_date", "kind", "path", "size_bytes", "sha256"}
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise KeyError(f"V2 source inventory lacks fields: {missing}")
        frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
        frame["trade_date"] = frame["trade_date"].map(canonical_date)
        selected = frame.loc[
            frame["kind"].astype(str).eq("underlying")
            & frame["trade_date"].str.startswith(year)
        ].copy()
        selected["size_bytes"] = pd.to_numeric(
            selected["size_bytes"], errors="raise"
        ).astype(np.int64)
        frames.append(selected)
    output = pd.concat(frames, ignore_index=True)
    if output.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("V2 underlying inventory keys are not unique")
    return output


def early_cash_features_from_opens(opens: Iterable[float]) -> dict[str, float]:
    values = np.asarray(list(opens), dtype=np.float64)
    if (
        values.shape != (EARLY_CLOCK_COUNT,)
        or not np.isfinite(values).all()
        or (values <= 0.0).any()
    ):
        raise AssertionError("V2 early cash opens are invalid")
    returns = np.diff(np.log(values)) * 10_000.0
    if returns.shape != (EARLY_RETURN_COUNT,):
        raise AssertionError("V2 early cash return count changed")
    return {
        "return_0930_1035_bps": float(math.log(values[-1] / values[0]) * 10_000.0),
        "return_1000_1035_bps": float(math.log(values[-1] / values[30]) * 10_000.0),
        "return_1030_1035_bps": float(math.log(values[-1] / values[60]) * 10_000.0),
        "open_return_std_bps": float(np.std(returns, ddof=0)),
        "open_range_bps": float(math.log(values.max() / values.min()) * 10_000.0),
        "positive_open_return_fraction": float(np.mean(returns > 0.0)),
    }


def _early_timestamp_values(day: str) -> tuple[list[pd.Timestamp], list[str]]:
    date = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    expected = list(
        pd.date_range(f"{date} {EARLY_START}", f"{date} {EARLY_END}", freq="min")
    )
    values: list[str] = []
    for timestamp in expected:
        base_t = timestamp.strftime("%Y-%m-%dT%H:%M:%S")
        base_space = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        values.extend((base_t, f"{base_t}.000", base_space, f"{base_space}.000"))
    return expected, values


def read_early_cash_source(record: Any) -> tuple[tuple[str, str], dict[str, float], dict[str, Any]]:
    ticker = str(record.ticker)
    day = str(record.trade_date)
    path = Path(str(record.path))
    if not path.is_file() or path.stat().st_size != int(record.size_bytes):
        raise AssertionError(f"V2 underlying source missing/size changed: {path}")
    actual_hash = sha256_file(path)
    if actual_hash != str(record.sha256):
        raise AssertionError(f"V2 underlying source hash changed: {path}")
    required = {"symbol", "date", "timestamp", "open"}
    if not required.issubset(set(pq.read_schema(path).names)):
        raise KeyError(f"V2 underlying schema changed: {path}")
    expected, values = _early_timestamp_values(day)
    frame = pd.read_parquet(
        path,
        columns=["symbol", "date", "timestamp", "open"],
        filters=[("timestamp", "in", values)],
    )
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    frame["date"] = frame["date"].map(canonical_date)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame["open"] = pd.to_numeric(frame["open"], errors="coerce")
    frame = frame.sort_values("timestamp", kind="stable")
    if (
        len(frame) != EARLY_CLOCK_COUNT
        or frame.isna().any().any()
        or not frame["symbol"].eq(ticker).all()
        or not frame["date"].eq(day).all()
        or frame["timestamp"].duplicated().any()
        or list(frame["timestamp"]) != expected
    ):
        raise AssertionError(f"V2 exact early clocks failed: {path}")
    features = early_cash_features_from_opens(frame["open"].to_numpy())
    audit = {
        "ticker": ticker,
        "trade_date": day,
        "path": str(path),
        "size_bytes": int(record.size_bytes),
        "sha256": actual_hash,
        "rows_read": EARLY_CLOCK_COUNT,
        "first_clock": EARLY_START,
        "last_clock": EARLY_END,
    }
    return (ticker, day), features, audit


def load_early_cash_cache(
    rows: pd.DataFrame, inventory: pd.DataFrame, workers: int
) -> tuple[dict[tuple[str, str], dict[str, float]], pd.DataFrame]:
    needed: set[tuple[str, str]] = set()
    for record in rows.itertuples(index=False):
        needed.add(("QQQ", str(record.trade_date)))
        needed.add(("SPY", str(record.trade_date)))
        if str(record.ticker) == "SPXW":
            needed.add(("SPXW", str(record.trade_date)))
    selected = inventory.loc[
        inventory.apply(lambda row: (row["ticker"], row["trade_date"]) in needed, axis=1)
    ].copy()
    actual_keys = set(zip(selected["ticker"], selected["trade_date"], strict=True))
    if actual_keys != needed:
        missing = sorted(needed.difference(actual_keys))
        raise AssertionError(f"V2 underlying inventory coverage failed: {missing[:5]}")
    cache: dict[tuple[str, str], dict[str, float]] = {}
    audits: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(read_early_cash_source, record): record
            for record in selected.itertuples(index=False)
        }
        for future in as_completed(futures):
            key, features, audit = future.result()
            cache[key] = features
            audits.append(audit)
    if set(cache) != needed:
        raise AssertionError("V2 early cash cache is incomplete")
    audit_frame = pd.DataFrame(audits).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    return cache, audit_frame


def attach_cash_features(
    rows: pd.DataFrame, cache: dict[tuple[str, str], dict[str, float]]
) -> pd.DataFrame:
    output = rows.copy()
    for prefix in ("qqq", "spy", "spxw"):
        for name in CASH_METRICS:
            output[f"{prefix}_{name}"] = 0.0
    for index, record in output.iterrows():
        day = str(record["trade_date"])
        for ticker, prefix in (("QQQ", "qqq"), ("SPY", "spy")):
            for name, value in cache[(ticker, day)].items():
                output.at[index, f"{prefix}_{name}"] = value
        if str(record["ticker"]) == "SPXW":
            for name, value in cache[("SPXW", day)].items():
                output.at[index, f"spxw_{name}"] = value
    for ticker in TICKERS:
        output[f"ticker_{ticker}"] = output["ticker"].eq(ticker).astype(float)
    if (
        not np.isfinite(output[list(FEATURE_COLUMNS)].to_numpy(dtype=float)).all()
        or output[list(FEATURE_COLUMNS)].isna().any().any()
    ):
        raise AssertionError("V2 model matrix contains invalid values")
    return output


def make_model() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    penalty="l2",
                    C=MODEL_C,
                    solver="liblinear",
                    fit_intercept=True,
                    class_weight=None,
                    max_iter=2000,
                    random_state=0,
                ),
            ),
        ]
    )


def _serialize_model(model: Pipeline, block: str, train: pd.DataFrame) -> dict[str, Any]:
    imputer: SimpleImputer = model.named_steps["imputer"]
    scaler: StandardScaler = model.named_steps["scaler"]
    classifier: LogisticRegression = model.named_steps["classifier"]
    return {
        "block": block,
        "feature_columns": list(FEATURE_COLUMNS),
        "train_rows": int(len(train)),
        "train_start": str(train["trade_date"].min()),
        "train_end": str(train["trade_date"].max()),
        "imputer_statistics": imputer.statistics_.tolist(),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "coefficient": classifier.coef_[0].tolist(),
        "intercept": classifier.intercept_.tolist(),
        "classes": classifier.classes_.tolist(),
        "n_iter": classifier.n_iter_.tolist(),
    }


def fit_predict_blocks(rows: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    trades: list[pd.DataFrame] = []
    models: dict[str, Any] = {}
    for block, scope in BLOCKS.items():
        train = rows.loc[
            rows["month"].between(scope["train_start"], scope["train_end"])
        ].copy()
        test = rows.loc[
            rows["month"].between(scope["test_start"], scope["test_end"])
        ].copy()
        if train.empty or test.empty:
            raise AssertionError(f"V2 block {block} is empty")
        model = make_model()
        model.fit(train[list(FEATURE_COLUMNS)], train["direct_win"])
        probability = model.predict_proba(test[list(FEATURE_COLUMNS)])[:, 1]
        orientation = np.where(probability >= MODEL_THRESHOLD, 1, -1).astype(np.int64)
        output = test[
            [
                "ticker",
                "trade_date",
                "month",
                "sensor_ticker",
                "signal_pressure",
                "base_side",
                "underlying_return_bps",
                "base_gross_bps",
                "direct_win",
            ]
        ].copy()
        output.insert(0, "block", block)
        output["direct_probability"] = probability
        output["orientation"] = orientation
        output["side"] = output["base_side"] * output["orientation"]
        output["gross_bps"] = output["side"] * output["underlying_return_bps"]
        for cost in COSTS_BPS:
            output[f"net_bps_{int(cost)}bp"] = output["gross_bps"] - cost
        output["net_bps"] = output["net_bps_1bp"]
        trades.append(output)
        models[block] = _serialize_model(model, block, train)
    ledger = pd.concat(trades, ignore_index=True).sort_values(
        ["block", "ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if len(ledger) != int(rows["trade_date"].str.startswith("2024").sum()):
        raise AssertionError("V2 development prediction coverage changed")
    return ledger, models


def profit_factor(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    gains = float(array[array > 0.0].sum())
    losses = float(-array[array < 0.0].sum())
    if losses == 0.0:
        return 1.0e12 if gains > 0.0 else 0.0
    return gains / losses


def summarize_monthly(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for block, scope in BLOCKS.items():
        months = pd.period_range(
            pd.Period(scope["test_start"], freq="M"),
            pd.Period(scope["test_end"], freq="M"),
            freq="M",
        ).strftime("%Y%m")
        for ticker in TICKERS:
            ticker_rows = ledger.loc[
                ledger["block"].eq(block) & ledger["ticker"].eq(ticker)
            ]
            for month in months:
                selected = ticker_rows.loc[ticker_rows["month"].eq(month)]
                net = selected["net_bps"].to_numpy(dtype=float)
                rows.append(
                    {
                        "block": block,
                        "ticker": ticker,
                        "month": month,
                        "trades": int(len(net)),
                        "win_rate": float(np.mean(net > 0.0)) if len(net) else 0.0,
                        "profit_factor": profit_factor(net),
                        "net_bps": float(net.sum()),
                        "frequency_pass": int(len(net)) > MIN_MONTH_TRADES_EXCLUSIVE,
                        "pnl_positive": bool(net.sum() > 0.0),
                    }
                )
    output = pd.DataFrame(rows)
    if len(output) != 36:
        raise AssertionError("V2 development must contain 36 ticker-month cells")
    return output


def summarize_blocks(ledger: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for block in BLOCKS:
        for ticker in TICKERS:
            selected = ledger.loc[
                ledger["block"].eq(block) & ledger["ticker"].eq(ticker)
            ]
            cells = monthly.loc[
                monthly["block"].eq(block) & monthly["ticker"].eq(ticker)
            ]
            net = selected["net_bps"].to_numpy(dtype=float)
            pf = profit_factor(net)
            win_rate = float(np.mean(net > 0.0))
            pnl = float(net.sum())
            minimum = int(cells["trades"].min())
            positive_months = int(cells["pnl_positive"].sum())
            rows.append(
                {
                    "block": block,
                    "ticker": ticker,
                    "trades": int(len(net)),
                    "win_rate": win_rate,
                    "profit_factor": pf,
                    "net_bps": pnl,
                    "min_month_trades": minimum,
                    "positive_months": positive_months,
                    "incremental_gate_pass": bool(
                        pf > INCREMENTAL_MIN_PF
                        and win_rate > MIN_WIN_RATE
                        and pnl > 0.0
                        and minimum > MIN_MONTH_TRADES_EXCLUSIVE
                    ),
                    "objective_gate_pass": bool(
                        pf > OBJECTIVE_MIN_PF
                        and win_rate > MIN_WIN_RATE
                        and minimum > MIN_MONTH_TRADES_EXCLUSIVE
                        and positive_months == 6
                    ),
                }
            )
    return pd.DataFrame(rows)


def summarize_sensitivity(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for block in BLOCKS:
        block_rows = ledger.loc[ledger["block"].eq(block)]
        for scope in (*TICKERS, "POOLED"):
            selected = (
                block_rows
                if scope == "POOLED"
                else block_rows.loc[block_rows["ticker"].eq(scope)]
            )
            for cost in COSTS_BPS:
                net = selected[f"net_bps_{int(cost)}bp"].to_numpy(dtype=float)
                rows.append(
                    {
                        "block": block,
                        "scope": scope,
                        "cost_bps": cost,
                        "trades": int(len(net)),
                        "win_rate": float(np.mean(net > 0.0)),
                        "profit_factor": profit_factor(net),
                        "net_bps": float(net.sum()),
                    }
                )
    return pd.DataFrame(rows)


def render_summary(summary: dict[str, Any], blocks: pd.DataFrame) -> str:
    lines = [
        "# CROSS_VENUE_CALENDAR_RR_LEADER_V2 — development 2023–2024",
        "",
        f"Status: `{summary['status']}`",
        "",
    ]
    for row in blocks.itertuples(index=False):
        lines.append(
            f"- {row.block} {row.ticker}: {row.trades} trades, "
            f"WR {row.win_rate:.3%}, PF {row.profit_factor:.6f}, "
            f"PnL {row.net_bps:+.3f} bps, positive months "
            f"{row.positive_months}/6."
        )
    lines.extend(
        [
            "",
            f"Advance to frozen 2025: `{summary['advance_to_2025_freeze']}`.",
            "2025, 2026 and production were not opened.",
            "",
        ]
    )
    return "\n".join(lines)


def run(output_dir: Path, workers: int) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V2 output already exists: {output_dir}")
    if workers < 1:
        raise ValueError("workers must be positive")
    verify_inputs()
    option_features = load_option_features()
    development = load_development_rows(option_features)
    inventory = load_underlying_inventory()
    cache, source_audit = load_early_cash_cache(development, inventory, workers)
    development = attach_cash_features(development, cache)
    ledger, models = fit_predict_blocks(development)
    monthly = summarize_monthly(ledger)
    block_summary = summarize_blocks(ledger, monthly)
    sensitivity = summarize_sensitivity(ledger)
    advance = bool(block_summary["incremental_gate_pass"].all())
    objective = bool(block_summary["objective_gate_pass"].all())
    if advance and objective:
        status = "PASS_DEVELOPMENT_OBJECTIVE_2025_NOT_FROZEN"
    elif advance:
        status = "PASS_DEVELOPMENT_INCREMENTAL_2025_NOT_FROZEN"
    elif bool(block_summary["incremental_gate_pass"].any()):
        status = "PARTIAL_DEVELOPMENT_EDGE_2025_CLOSED"
    else:
        status = "NO_DEVELOPMENT_EDGE_2025_CLOSED"

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        development_output = development[
            [
                "ticker",
                "trade_date",
                "month",
                "sensor_ticker",
                *FEATURE_COLUMNS,
                "base_side",
                "underlying_return_bps",
                "base_gross_bps",
                "direct_win",
            ]
        ].copy()
        development_output.to_parquet(staging / "development_dataset.parquet", index=False)
        source_audit.to_csv(staging / "source_audit.csv", index=False, lineterminator="\n")
        ledger.to_csv(staging / "trades.csv", index=False, lineterminator="\n")
        monthly.to_csv(staging / "monthly_metrics.csv", index=False, lineterminator="\n")
        block_summary.to_csv(staging / "block_ticker_summary.csv", index=False, lineterminator="\n")
        sensitivity.to_csv(staging / "cost_sensitivity.csv", index=False, lineterminator="\n")
        (staging / "models.json").write_text(
            json.dumps(models, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        output_names = (
            "development_dataset.parquet",
            "source_audit.csv",
            "trades.csv",
            "monthly_metrics.csv",
            "block_ticker_summary.csv",
            "cost_sensitivity.csv",
            "models.json",
        )
        summary: dict[str, Any] = {
            "schema": "cross_venue_calendar_rr_leader_v2_development_v1",
            "status": status,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "execution_commit": current_git_commit(),
            "predeclaration_sha256": sha256_file(PREDECLARATION),
            "evaluator_sha256": sha256_file(Path(__file__).resolve()),
            "input_sha256": {
                str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): expected
                for path, expected in INPUTS.items()
            },
            "mapping": SENSOR_MAP,
            "feature_columns": list(FEATURE_COLUMNS),
            "feature_count": len(FEATURE_COLUMNS),
            "blocks": BLOCKS,
            "model": {
                "kind": "pooled_logistic_direct_orientation",
                "penalty": "l2",
                "C": MODEL_C,
                "solver": "liblinear",
                "threshold": MODEL_THRESHOLD,
                "class_weight": None,
                "random_state": 0,
            },
            "cash_clock": {
                "column": "open",
                "first": EARLY_START,
                "last": EARLY_END,
                "rows_per_source": EARLY_CLOCK_COUNT,
                "outcome_clock_read_by_cash_builder": False,
            },
            "runtime": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "pyarrow": pyarrow.__version__,
                "scikit_learn": sklearn.__version__,
            },
            "train_rows_2023": int(development["month"].str.startswith("2023").sum()),
            "development_trades_2024": int(len(ledger)),
            "source_rows_revalidated": int(len(source_audit)),
            "source_hash_mismatches": 0,
            "source_size_mismatches": 0,
            "block_ticker": block_summary.to_dict(orient="records"),
            "advance_to_2025_freeze": advance,
            "objective_gate_pass": objective,
            "outer_2025_opened": False,
            "holdout_2026_opened": False,
            "production_modified": False,
            "live_or_systemd_modified": False,
            "output_sha256": {
                name: sha256_file(staging / name) for name in output_names
            },
            "development_dataset_sha256": dataframe_digest(development_output),
            "trades_recomputed_sha256": dataframe_digest(ledger),
            "monthly_recomputed_sha256": dataframe_digest(monthly),
            "block_summary_recomputed_sha256": dataframe_digest(block_summary),
            "cost_sensitivity_recomputed_sha256": dataframe_digest(sensitivity),
        }
        (staging / "SUMMARY.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "SUMMARY.md").write_text(
            render_summary(summary, block_summary), encoding="utf-8", newline="\n"
        )
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(args.output_dir.resolve(), args.workers)
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
