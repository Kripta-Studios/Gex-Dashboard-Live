"""Frozen contracts shared by the causal V4R2 outer-2026 runner."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v2 as v2
from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v4 as v4
from neural.jepa.build_calendar_risk_reversal_pressure_v1 import canonical_date


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TICKERS = v2.TICKERS
FEATURE_COLUMNS = v2.FEATURE_COLUMNS
SENSOR_MAP = v2.SENSOR_MAP
COSTS_BPS = v2.COSTS_BPS
MONTHS = tuple(f"2026{month:02d}" for month in range(1, 8))
CLOSED_MONTHS = MONTHS[:6]
JULY_MTD = "202607"

V2_TRAINING = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v2_development_202301_202412_v1/"
    "development_dataset.parquet"
)
V4_DEVELOPMENT_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v4_development_2025_v1"
)
DATA_GATE_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v4r2_data_gate_202601_20260724_v1"
)
DATA_GATE_AUDIT_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v4r2_data_gate_202601_20260724_v1_audit"
)
FROZEN_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v4r2_outer_2026_frozen_v1"
)
FROZEN_MANIFEST = FROZEN_DIR / "manifest.json"
OUTER_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v4r2_outer_2026_v1"
)
OUTER_AUDIT_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v4r2_outer_2026_v1_audit"
)

INPUT_HASHES = {
    V2_TRAINING: "459979c11ad5b7ba1ed44ef3add42142d0eab40982882bc52031982e22778f0b",
    V4_DEVELOPMENT_DIR / "development_dataset.parquet": (
        "87413fb1c605c221aa8f225ad9877ccbdb6d5eca45877f4fa97a5b60d321d04b"
    ),
    V4_DEVELOPMENT_DIR / "SUMMARY.json": (
        "a2beced1f021e156b53deaed3932dafc0af18f18f582d0b9af5db1a0762bd21b"
    ),
    DATA_GATE_DIR / "SUMMARY.json": (
        "16988ecc24dbbf882d74f387b3a926a649cd7c5a266126f894ea3e8b1bed1aa3"
    ),
    DATA_GATE_DIR / "feature_view.parquet": (
        "904a28560cf5bc6c86afa28c833e9aaf7f84dbb417aac745a134fb65df8ecbff"
    ),
    DATA_GATE_DIR / "cash_source_audit.csv": (
        "75218958663b1dfa200bdd5ad5ecbb3d8e19b1337441e6ec22509405459e3079"
    ),
    DATA_GATE_AUDIT_DIR / "audit_summary.json": (
        "e65d23deee5e4e084a09d27e863e34906b3971dc0d9a68254f70d13e93c84cda"
    ),
    PROJECT_ROOT
    / "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_LEADER_V4_FULL_HISTORY_LOGISTIC_PREDECLARATION.md": (
        "0c1a18b745072fb5265e83209e9267a41aa0387024f988831835bdc7272e5062"
    ),
    PROJECT_ROOT
    / "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_LEADER_V4R1_2026_SOURCE_RETRY_EXCLUSION_PREDECLARATION.md": (
        "7c4c500111774e3d7e72af840ff2660ec77518ab9c9eb0623f128ebc21bcee6b"
    ),
    PROJECT_ROOT
    / "research_papers/JEPA/CROSS_VENUE_CALENDAR_RR_LEADER_V4R2_2026_OUTCOME_FREE_FIXED_EXCLUSIONS_PREDECLARATION.md": (
        "bf2fed43b1d58bd8e9bc0ba4bb4ab4a26b92ae66f4b3ec7c4845f34d27260fbf"
    ),
    Path(v2.__file__).resolve(): (
        "1bdc768ca4a72d99be1394d18107750abb228024fc56555ebe4d7b13c5c89d2a"
    ),
}

RUNNER_CODE_PATHS = (
    Path("neural/jepa/cross_venue_calendar_rr_leader_v4r2_2026_outer_common.py"),
    Path("neural/jepa/freeze_cross_venue_calendar_rr_leader_v4r2_2026.py"),
    Path("neural/jepa/evaluate_cross_venue_calendar_rr_leader_v4r2_2026.py"),
    Path("neural/jepa/audit_cross_venue_calendar_rr_leader_v4r2_2026.py"),
)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_digest(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def ordered_hash(values: Iterable[str]) -> str:
    payload = "\n".join(values).encode("utf-8")
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


def tracked_worktree_clean() -> None:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if completed.stdout.strip():
        raise AssertionError("V4R2 outer requires a clean tracked worktree")


def validate_frozen_inputs() -> None:
    for path, expected in INPUT_HASHES.items():
        if not path.is_file() or sha256_file(path) != expected:
            raise AssertionError(f"V4R2 frozen input changed: {path}")
    gate = json.loads((DATA_GATE_DIR / "SUMMARY.json").read_text(encoding="utf-8"))
    audit = json.loads(
        (DATA_GATE_AUDIT_DIR / "audit_summary.json").read_text(encoding="utf-8")
    )
    if (
        gate.get("status") != "PASS_OUTCOME_FREE_DATA_GATE"
        or gate.get("target_feature_rows") != 394
        or gate.get("feature_count") != 29
        or gate.get("open_1036_read") is not False
        or gate.get("open_1336_read") is not False
        or gate.get("outcome_2026_accessed") is not False
        or audit.get("status")
        != "PASS_INDEPENDENT_OUTCOME_FREE_DATA_GATE_AUDIT"
        or audit.get("target_feature_rows") != 394
        or audit.get("outcome_2026_accessed") is not False
    ):
        raise AssertionError("V4R2 outcome-free gate authority changed")


def _normalize_training(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    required = {
        "ticker",
        "trade_date",
        "month",
        "base_gross_bps",
        "direct_win",
        *FEATURE_COLUMNS,
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError(f"V4R2 training lacks fields: {missing}")
    frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    frame["trade_date"] = frame["trade_date"].map(canonical_date)
    frame["month"] = frame["trade_date"].str[:6]
    return frame


def load_final_training() -> pd.DataFrame:
    first = _normalize_training(pd.read_parquet(V2_TRAINING))
    second = _normalize_training(
        pd.read_parquet(V4_DEVELOPMENT_DIR / "development_dataset.parquet")
    )
    frame = pd.concat([first, second], ignore_index=True).sort_values(
        ["trade_date", "ticker"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(first) != 1_482
        or len(second) != 735
        or len(frame) != 2_217
        or frame.duplicated(["ticker", "trade_date"]).any()
        or set(frame["ticker"]) != set(TICKERS)
        or not frame["trade_date"].between("20230101", "20251231").all()
        or not np.isfinite(frame[list(FEATURE_COLUMNS)].to_numpy(dtype=float)).all()
        or not frame["direct_win"].isin([0, 1]).all()
        or not frame["base_gross_bps"].gt(0.0).eq(frame["direct_win"].eq(1)).all()
    ):
        raise AssertionError("V4R2 final training identity changed")
    return frame


def load_feature_view() -> pd.DataFrame:
    frame = pd.read_parquet(DATA_GATE_DIR / "feature_view.parquet").copy()
    frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    frame["sensor_ticker"] = (
        frame["sensor_ticker"].astype(str).str.upper().str.strip()
    )
    frame["trade_date"] = frame["trade_date"].map(canonical_date)
    frame["month"] = frame["trade_date"].str[:6]
    if (
        len(frame) != 394
        or frame.duplicated(["ticker", "trade_date"]).any()
        or set(frame["ticker"]) != set(TICKERS)
        or not frame["trade_date"].between("20260101", "20260724").all()
        or not frame["sensor_ticker"].eq(frame["ticker"].map(SENSOR_MAP)).all()
        or not np.isfinite(frame[list(FEATURE_COLUMNS)].to_numpy(dtype=float)).all()
        or frame["signal_pressure"].eq(0.0).any()
    ):
        raise AssertionError("V4R2 2026 feature view changed")
    return frame.sort_values(["ticker", "trade_date"], kind="stable").reset_index(
        drop=True
    )


def load_event_sources(features: pd.DataFrame) -> pd.DataFrame:
    sources = pd.read_csv(
        DATA_GATE_DIR / "cash_source_audit.csv",
        dtype={"ticker": str, "trade_date": str, "sha256": str},
    )
    sources["ticker"] = sources["ticker"].str.upper().str.strip()
    sources["trade_date"] = sources["trade_date"].map(canonical_date)
    sources = sources.rename(
        columns={"path": "source_path", "size_bytes": "source_size_bytes", "sha256": "source_sha256"}
    )
    selected = features.merge(
        sources[
            ["ticker", "trade_date", "source_path", "source_size_bytes", "source_sha256"]
        ],
        on=["ticker", "trade_date"],
        how="left",
        validate="one_to_one",
    )
    if (
        selected[["source_path", "source_size_bytes", "source_sha256"]]
        .isna()
        .any()
        .any()
    ):
        raise AssertionError("V4R2 event source mapping failed")
    selected["source_size_bytes"] = pd.to_numeric(
        selected["source_size_bytes"], errors="raise"
    ).astype(np.int64)
    return selected


def serialize_model(model: Any, training: pd.DataFrame) -> dict[str, Any]:
    payload = v4.serialize_model(model, training)
    payload["schema"] = "cross_venue_calendar_rr_leader_v4r2_final_model_v1"
    payload["training_recomputed_sha256"] = dataframe_digest(
        training[["ticker", "trade_date", *FEATURE_COLUMNS, "direct_win"]]
    )
    return payload


def profit_factor(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    gains = float(array[array > 0.0].sum())
    losses = float(-array[array < 0.0].sum())
    if losses == 0.0:
        return 1.0e12 if gains > 0.0 else 0.0
    return gains / losses
