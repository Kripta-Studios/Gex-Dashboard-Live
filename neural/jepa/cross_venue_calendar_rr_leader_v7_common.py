"""Frozen contracts for the post-outcome V7 rolling-12 development test."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from neural.jepa import (
    cross_venue_calendar_rr_leader_v4r2_2026_outer_common as v4r2,
)
from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v4 as v4


PROJECT_ROOT = v4r2.PROJECT_ROOT
TICKERS = tuple(v4r2.TICKERS)
MONTHS = tuple(v4r2.MONTHS)
CLOSED_MONTHS = tuple(v4r2.CLOSED_MONTHS)
JULY_MTD = v4r2.JULY_MTD
FEATURE_COLUMNS = tuple(v4r2.FEATURE_COLUMNS)
SENSOR_MAP = dict(v4r2.SENSOR_MAP)
COSTS_BPS = tuple(v4r2.COSTS_BPS)

PREDECLARATION = PROJECT_ROOT / (
    "research_papers/JEPA/"
    "CROSS_VENUE_CALENDAR_RR_LEADER_V7_ROLLING12_MONTHLY_LOGISTIC_"
    "PREDECLARATION.md"
)
FEATURE_VIEW = v4r2.DATA_GATE_DIR / "feature_view.parquet"
OUTER_TRADES = v4r2.OUTER_DIR / "trades.csv"
OUTER_SUMMARY = v4r2.OUTER_DIR / "SUMMARY.json"
OUTER_AUDIT = v4r2.OUTER_AUDIT_DIR / "audit_summary.json"
OUTPUT_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v7_rolling12_monthly_development_2026_v1"
)
AUDIT_DIR = OUTPUT_DIR.with_name(f"{OUTPUT_DIR.name}_audit")

INPUT_HASHES = {
    v4r2.V2_TRAINING: (
        "459979c11ad5b7ba1ed44ef3add42142d0eab40982882bc52031982e22778f0b"
    ),
    v4r2.V4_DEVELOPMENT_DIR / "development_dataset.parquet": (
        "87413fb1c605c221aa8f225ad9877ccbdb6d5eca45877f4fa97a5b60d321d04b"
    ),
    FEATURE_VIEW: (
        "904a28560cf5bc6c86afa28c833e9aaf7f84dbb417aac745a134fb65df8ecbff"
    ),
    OUTER_TRADES: (
        "3db6f767282c308c7c87f3d0d74e29890e9809cdbe3621edee66f2562780e19c"
    ),
    OUTER_SUMMARY: (
        "8de7e8865b57d0ed36fd7a065bb8b87a9dac7e02d0a0db2d7c051e4f223f12b2"
    ),
    OUTER_AUDIT: (
        "30e0690f93386e16ce1662c367c8ba3aef2b7f8b5824f180a7d2f52d80195bcd"
    ),
    PREDECLARATION: (
        "d89cda15d624588b7d2258332a656792587d682326587cf454ea45e70d4c4a7b"
    ),
}

EXPECTED_FOLDS: dict[str, dict[str, Any]] = {
    "202601": {"start": "202501", "end": "202512", "train": (247, 244, 244), "test": (20, 20, 20)},
    "202602": {"start": "202502", "end": "202601", "train": (247, 244, 244), "test": (19, 19, 19)},
    "202603": {"start": "202503", "end": "202602", "train": (247, 246, 246), "test": (21, 21, 21)},
    "202604": {"start": "202504", "end": "202603", "train": (247, 246, 246), "test": (18, 18, 18)},
    "202605": {"start": "202505", "end": "202604", "train": (244, 244, 244), "test": (20, 20, 20)},
    "202606": {"start": "202506", "end": "202605", "train": (243, 243, 243), "test": (20, 21, 21)},
    "202607": {"start": "202507", "end": "202606", "train": (243, 244, 244), "test": (12, 13, 13)},
}

RUNNER_CODE_PATHS = (
    Path("neural/jepa/cross_venue_calendar_rr_leader_v7_common.py"),
    Path("neural/jepa/evaluate_cross_venue_calendar_rr_leader_v7.py"),
    Path("neural/jepa/audit_cross_venue_calendar_rr_leader_v7.py"),
)


def validate_inputs() -> None:
    for path, expected in INPUT_HASHES.items():
        if not path.is_file() or v4r2.sha256_file(path) != expected:
            raise AssertionError(f"V7 input hash changed: {path}")
    outer = json.loads(OUTER_SUMMARY.read_text(encoding="utf-8"))
    audit = json.loads(OUTER_AUDIT.read_text(encoding="utf-8"))
    if (
        outer.get("status") != "FAILED_OUTER_2026_NOT_PROMOTABLE"
        or outer.get("executed_trades") != 394
        or outer.get("outer_2026_opened") is not True
        or outer.get("physical_option_payoff_opened") is not False
        or outer.get("production_modified") is not False
        or audit.get("status") != "PASS_INDEPENDENT_V4R2_OUTER_2026_AUDIT"
        or audit.get("eligible_events") != 394
        or audit.get("source_mismatches") != 0
    ):
        raise AssertionError("V7 requires the exact audited V4R2 failure")


def load_history() -> pd.DataFrame:
    frame = v4r2.load_final_training().copy()
    if len(frame) != 2_217:
        raise AssertionError("V7 historical training identity changed")
    return frame


def load_labeled_2026() -> pd.DataFrame:
    features = v4r2.load_feature_view()
    outcomes = pd.read_csv(
        OUTER_TRADES,
        dtype={"ticker": str, "trade_date": str, "month": str},
    )
    required = {
        "ticker",
        "trade_date",
        "month",
        "sensor_ticker",
        "signal_pressure",
        "base_side",
        "entry_open",
        "exit_open",
        "underlying_return_bps",
        "base_gross_bps",
    }
    if required.difference(outcomes.columns):
        raise AssertionError("V7 outer outcome schema changed")
    outcomes = outcomes[
        [
            "ticker",
            "trade_date",
            "month",
            "sensor_ticker",
            "signal_pressure",
            "base_side",
            "entry_open",
            "exit_open",
            "underlying_return_bps",
            "base_gross_bps",
        ]
    ].copy()
    merged = features.merge(
        outcomes,
        on=["ticker", "trade_date", "month", "sensor_ticker"],
        how="inner",
        validate="one_to_one",
        suffixes=("", "_outer"),
    )
    merged["direct_win"] = merged["base_gross_bps"].gt(0.0).astype(np.int64)
    expected_side = np.sign(merged["signal_pressure"]).astype(np.int64)
    if (
        len(merged) != 394
        or merged.duplicated(["ticker", "trade_date"]).any()
        or not np.allclose(
            merged["signal_pressure"].to_numpy(dtype=float),
            merged["signal_pressure_outer"].to_numpy(dtype=float),
            rtol=0.0,
            atol=1e-15,
        )
        or not merged["base_side"].astype(np.int64).eq(expected_side).all()
        or not merged["sensor_ticker"].eq(merged["ticker"].map(SENSOR_MAP)).all()
        or not np.isfinite(
            merged[
                [
                    *FEATURE_COLUMNS,
                    "entry_open",
                    "exit_open",
                    "underlying_return_bps",
                    "base_gross_bps",
                ]
            ].to_numpy(dtype=float)
        ).all()
        or not merged["entry_open"].gt(0.0).all()
        or not merged["exit_open"].gt(0.0).all()
    ):
        raise AssertionError("V7 2026 label join failed")
    return merged.sort_values(["ticker", "trade_date"], kind="stable").reset_index(
        drop=True
    )


def fold_bounds(month: str) -> tuple[str, str]:
    if month not in EXPECTED_FOLDS:
        raise ValueError(f"unsupported V7 month: {month}")
    period = pd.Period(month, freq="M")
    return (period - 12).strftime("%Y%m"), (period - 1).strftime("%Y%m")


def combined_training(history: pd.DataFrame, labeled_2026: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "ticker",
        "trade_date",
        "month",
        "base_gross_bps",
        "direct_win",
        *FEATURE_COLUMNS,
    ]
    combined = pd.concat(
        [history[columns], labeled_2026[columns]], ignore_index=True
    ).sort_values(["trade_date", "ticker"], kind="stable").reset_index(drop=True)
    if combined.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("V7 combined training has duplicate events")
    return combined


def training_for_month(combined: pd.DataFrame, month: str) -> pd.DataFrame:
    start, end = fold_bounds(month)
    train = combined.loc[combined["month"].between(start, end)].copy()
    counts = tuple(
        int(value)
        for value in train.groupby("ticker").size().reindex(TICKERS, fill_value=0)
    )
    expected = EXPECTED_FOLDS[month]
    if (
        start != expected["start"]
        or end != expected["end"]
        or counts != expected["train"]
        or len(train) != sum(expected["train"])
        or not train["month"].lt(month).all()
        or not np.isfinite(train[list(FEATURE_COLUMNS)].to_numpy(dtype=float)).all()
        or not train["direct_win"].isin([0, 1]).all()
        or not train["base_gross_bps"].gt(0.0).eq(train["direct_win"].eq(1)).all()
    ):
        raise AssertionError(f"V7 causal training fold changed: {month}")
    return train.sort_values(["trade_date", "ticker"], kind="stable").reset_index(
        drop=True
    )


def testing_for_month(labeled_2026: pd.DataFrame, month: str) -> pd.DataFrame:
    test = labeled_2026.loc[labeled_2026["month"].eq(month)].copy()
    counts = tuple(
        int(value)
        for value in test.groupby("ticker").size().reindex(TICKERS, fill_value=0)
    )
    if counts != EXPECTED_FOLDS[month]["test"]:
        raise AssertionError(f"V7 test fold changed: {month}")
    return test.sort_values(["ticker", "trade_date"], kind="stable").reset_index(
        drop=True
    )


def serialize_model(model: Any, training: pd.DataFrame, month: str) -> dict[str, Any]:
    start, end = fold_bounds(month)
    payload = v4.serialize_model(model, training)
    payload.update(
        {
            "schema": "cross_venue_calendar_rr_leader_v7_monthly_model_v1",
            "test_month": month,
            "train_month_start": start,
            "train_month_end": end,
            "training_recomputed_sha256": v4r2.dataframe_digest(
                training[["ticker", "trade_date", *FEATURE_COLUMNS, "direct_win"]]
            ),
        }
    )
    return payload


def code_hashes() -> dict[str, str]:
    return {
        path.as_posix(): v4r2.sha256_file(PROJECT_ROOT / path)
        for path in RUNNER_CODE_PATHS
    }


def input_hashes_relative() -> dict[str, str]:
    return {
        str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): expected
        for path, expected in INPUT_HASHES.items()
    }
