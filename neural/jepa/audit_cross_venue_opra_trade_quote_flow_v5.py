"""Independently audit the outcome-free OPRA V5 data gate from raw bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_GATE_ROOT = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_opra_trade_quote_flow_v5_data_gate_2023_2025_v1"
)
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_opra_trade_quote_flow_v5_data_gate_audit_2023_2025_v1"
)
SENSORS = ("QQQ", "SPY")
YEARS = ("2023", "2024", "2025")
EXPECTED_CAPTURES = 1_504
WINDOWS = {
    "full": ("09:30:00", "10:35:00"),
    "w15": ("10:20:00", "10:35:00"),
    "w5": ("10:30:00", "10:35:00"),
}
BASE_FEATURES = (
    "directional_premium_imbalance",
    "directional_contract_imbalance",
    "directional_print_imbalance",
    "call_put_premium_imbalance",
    "call_put_contract_imbalance",
    "call_put_print_imbalance",
    "log_total_contracts",
    "log_total_premium",
)
FEATURE_COLUMNS = tuple(
    f"{window}_{feature}" for window in WINDOWS for feature in BASE_FEATURES
)
HALF_DAYS = frozenset(
    {
        "20230703",
        "20231124",
        "20240703",
        "20241129",
        "20241224",
        "20250703",
        "20251128",
        "20251224",
    }
)
MIN_EVENT_COVERAGE = 0.90
MIN_MONTHLY_EVENTS = 13
MIN_FIRMABLE_COVERAGE = 0.80
MAX_MODAL_FRACTION = 0.995
TRADE_COLUMNS = (
    "symbol",
    "expiration",
    "trade_date",
    "strike",
    "right",
    "trade_timestamp",
    "quote_timestamp",
    "sequence",
    "condition",
    "size",
    "exchange",
    "price",
    "bid_size",
    "bid_exchange",
    "bid",
    "bid_condition",
    "ask_size",
    "ask_exchange",
    "ask",
    "ask_condition",
)
RESPONSE_COLUMNS = tuple(column for column in TRADE_COLUMNS if column != "trade_date")
DUPLICATE_KEY = (
    "symbol",
    "expiration",
    "strike",
    "right",
    "trade_timestamp",
    "sequence",
    "exchange",
    "price",
    "size",
)
CODE_CLOSURE = (
    "neural/jepa/capture_cross_venue_opra_trade_quote_flow_v5.py",
    "neural/jepa/build_cross_venue_opra_trade_quote_flow_v5.py",
    "neural/jepa/audit_cross_venue_opra_trade_quote_flow_v5.py",
    "neural/jepa/wall_surface_flow_environment.py",
    "research_papers/JEPA/CROSS_VENUE_OPRA_TRADE_QUOTE_FLOW_V5_PREDECLARATION.md",
    "research_papers/JEPA/CAUSAL_SOURCE_INVENTORY_20260725.md",
    "research_papers/JEPA/requirements-cross-venue-opra-trade-quote-flow-v5.txt",
)


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def committed_state() -> tuple[str, dict[str, str]]:
    hashes: dict[str, str] = {}
    for relative in CODE_CLOSURE:
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", relative],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if dirty:
            raise AssertionError(f"V5 auditor requires clean code: {relative}")
        hashes[relative] = sha256_file(PROJECT_ROOT / relative)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    origin = subprocess.run(
        ["git", "rev-parse", "origin/main"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != origin:
        raise AssertionError("V5 auditor requires HEAD == origin/main")
    return head, hashes


def _parse_raw(raw: bytes, *, sensor: str, trade_date: str) -> pd.DataFrame:
    values: list[dict[str, Any]] = []
    for number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AssertionError(f"audit invalid NDJSON line {number}") from exc
        if not isinstance(value, dict):
            raise AssertionError("audit NDJSON row is not an object")
        values.append(value)
    frame = pd.DataFrame(values)
    missing = sorted(set(RESPONSE_COLUMNS).difference(frame.columns))
    if not values or missing:
        raise AssertionError(f"audit invalid raw shape: rows={len(values)} missing={missing}")
    out = frame.loc[:, RESPONSE_COLUMNS].copy()
    out.insert(2, "trade_date", trade_date)
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out["expiration"] = (
        out["expiration"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    )
    out["right"] = (
        out["right"].astype(str).str.upper().replace({"CALL": "C", "PUT": "P"})
    )
    for column in ("trade_timestamp", "quote_timestamp"):
        out[column] = pd.to_datetime(out[column], errors="coerce", format="mixed")
        if getattr(out[column].dt, "tz", None) is not None:
            raise AssertionError("audit found non-native timezone")
    integer_columns = (
        "sequence",
        "condition",
        "size",
        "exchange",
        "bid_size",
        "bid_exchange",
        "bid_condition",
        "ask_size",
        "ask_exchange",
        "ask_condition",
    )
    numeric_columns = ("strike", "price", "bid", "ask")
    for column in integer_columns:
        out[column] = pd.to_numeric(out[column], errors="coerce").astype("Int64")
    for column in numeric_columns:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    start = pd.Timestamp(
        f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} 09:30:00"
    )
    end = pd.Timestamp(
        f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} 10:35:00"
    )
    numeric = out.loc[:, numeric_columns].to_numpy(dtype=float)
    if (
        out.isna().any().any()
        or not out["symbol"].eq(sensor).all()
        or not out["expiration"].eq(trade_date).all()
        or not out["right"].isin(["C", "P"]).all()
        or not out["trade_timestamp"].ge(start).all()
        or not out["trade_timestamp"].lt(end).all()
        or not out["quote_timestamp"].lt(out["trade_timestamp"]).all()
        or not np.isfinite(numeric).all()
        or (numeric[:, 0] <= 0).any()
        or out.duplicated(list(DUPLICATE_KEY)).any()
    ):
        raise AssertionError("audit raw validation failed")
    return out.sort_values(
        ["trade_timestamp", "sequence", "right", "strike", "exchange"],
        kind="stable",
    ).reset_index(drop=True)


def _print_side(frame: pd.DataFrame) -> np.ndarray:
    price = frame["price"].to_numpy(dtype=float)
    bid = frame["bid"].to_numpy(dtype=float)
    ask = frame["ask"].to_numpy(dtype=float)
    midpoint = (bid + ask) / 2.0
    side = np.zeros(len(frame), dtype=np.int8)
    side[price >= ask] = 1
    side[price <= bid] = -1
    inside = (price > bid) & (price < ask)
    side[inside & (price > midpoint)] = 1
    side[inside & (price < midpoint)] = -1
    return side


def _features_for_window(frame: pd.DataFrame) -> tuple[dict[str, float], bool]:
    empty = {feature: math.nan for feature in BASE_FEATURES}
    if frame.empty or set(frame["right"].unique()) != {"C", "P"}:
        return empty, False
    premium = (
        frame["price"].to_numpy(dtype=float)
        * frame["size"].to_numpy(dtype=float)
        * 100.0
    )
    size = frame["size"].to_numpy(dtype=float)
    side = frame["print_side"].to_numpy(dtype=float)
    call = frame["right"].eq("C").to_numpy()
    put = ~call
    total_premium = float(premium.sum())
    total_size = float(size.sum())
    n_prints = len(frame)
    if total_premium <= 0 or total_size <= 0 or n_prints <= 0:
        return empty, False
    call_premium = float(premium[call].sum())
    put_premium = float(premium[put].sum())
    call_size = float(size[call].sum())
    put_size = float(size[put].sum())
    result = {
        "directional_premium_imbalance": float(
            ((side[call] * premium[call]).sum() - (side[put] * premium[put]).sum())
            / total_premium
        ),
        "directional_contract_imbalance": float(
            ((side[call] * size[call]).sum() - (side[put] * size[put]).sum())
            / total_size
        ),
        "directional_print_imbalance": float(
            (side[call].sum() - side[put].sum()) / n_prints
        ),
        "call_put_premium_imbalance": float(
            (call_premium - put_premium) / total_premium
        ),
        "call_put_contract_imbalance": float(
            (call_size - put_size) / total_size
        ),
        "call_put_print_imbalance": float(
            (int(call.sum()) - int(put.sum())) / n_prints
        ),
        "log_total_contracts": float(np.log1p(total_size)),
        "log_total_premium": float(np.log1p(total_premium)),
    }
    return result, bool(np.isfinite(list(result.values())).all())


def recompute_session(
    trades: pd.DataFrame, *, sensor: str, trade_date: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    accepted = trades["condition"].isin([0, 18])
    valid = (
        accepted
        & trades["size"].gt(0)
        & trades["price"].gt(0)
        & trades["bid"].gt(0)
        & trades["ask"].gt(trades["bid"])
        & trades["quote_timestamp"].lt(trades["trade_timestamp"])
        & trades["right"].isin(["C", "P"])
    )
    alpha = trades.loc[valid].copy()
    alpha["print_side"] = _print_side(alpha)
    alpha["premium_dollars"] = (
        alpha["price"].astype(float) * alpha["size"].astype(float) * 100.0
    )
    feature = {
        "sensor": sensor,
        "trade_date": trade_date,
        "year": trade_date[:4],
        "month": trade_date[:6],
        "calendar_half_day": trade_date in HALF_DAYS,
    }
    window_valid: list[bool] = []
    for name, (start_clock, end_clock) in WINDOWS.items():
        start = pd.Timestamp(
            f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} {start_clock}"
        )
        end = pd.Timestamp(
            f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} {end_clock}"
        )
        window = alpha[
            alpha["trade_timestamp"].ge(start)
            & alpha["trade_timestamp"].lt(end)
        ]
        values, passed = _features_for_window(window)
        feature.update({f"{name}_{key}": value for key, value in values.items()})
        window_valid.append(passed)
    finite = np.isfinite(
        np.asarray([feature[column] for column in FEATURE_COLUMNS], dtype=float)
    ).all()
    feature["event_valid"] = bool(all(window_valid) and finite)
    premium = float(alpha["premium_dollars"].sum())
    contracts = float(alpha["size"].sum())
    firmable = alpha["print_side"].ne(0)
    age = (
        trades["trade_timestamp"] - trades["quote_timestamp"]
    ).dt.total_seconds() * 1000.0
    audit = {
        "sensor": sensor,
        "trade_date": trade_date,
        "year": trade_date[:4],
        "month": trade_date[:6],
        "rows_total": int(len(trades)),
        "rows_condition_accepted": int(accepted.sum()),
        "rows_alpha_valid": int(len(alpha)),
        "rows_condition_excluded": int((~accepted).sum()),
        "rows_locked_crossed_or_nonpositive_quote": int(
            ((trades["bid"] <= 0) | (trades["ask"] <= trades["bid"])).sum()
        ),
        "rows_nonpositive_trade": int(
            ((trades["size"] <= 0) | (trades["price"] <= 0)).sum()
        ),
        "rows_midpoint_unfirmable": int((alpha["print_side"] == 0).sum()),
        "alpha_premium": premium,
        "alpha_contracts": contracts,
        "firmable_premium": float(alpha.loc[firmable, "premium_dollars"].sum()),
        "firmable_contracts": float(alpha.loc[firmable, "size"].sum()),
        "quote_age_ms_max": float(age.max()),
        "quote_age_ms_median": float(age.median()),
        "full_valid": window_valid[0],
        "w15_valid": window_valid[1],
        "w5_valid": window_valid[2],
        "event_valid": feature["event_valid"],
        "outcome_clock_accessed": False,
        "outcome_2026_accessed": False,
    }
    return feature, audit


def recompute_gate(
    features: pd.DataFrame, audit: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    annual_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    for sensor in SENSORS:
        for year in YEARS:
            subset = features[
                features["sensor"].eq(sensor) & features["year"].eq(year)
            ]
            quality = audit[
                audit["sensor"].eq(sensor) & audit["year"].eq(year)
            ]
            valid = subset[subset["event_valid"].astype(bool)]
            coverage = len(valid) / len(subset) if len(subset) else 0.0
            premium = float(quality["alpha_premium"].sum())
            contracts = float(quality["alpha_contracts"].sum())
            firm_premium = (
                float(quality["firmable_premium"].sum()) / premium
                if premium > 0
                else 0.0
            )
            firm_contracts = (
                float(quality["firmable_contracts"].sum()) / contracts
                if contracts > 0
                else 0.0
            )
            annual_rows.append(
                {
                    "sensor": sensor,
                    "year": year,
                    "sessions": int(len(subset)),
                    "valid_events": int(len(valid)),
                    "event_coverage": coverage,
                    "firmable_premium_coverage": firm_premium,
                    "firmable_contract_coverage": firm_contracts,
                    "coverage_pass": coverage >= MIN_EVENT_COVERAGE,
                    "firmable_premium_pass": firm_premium >= MIN_FIRMABLE_COVERAGE,
                    "firmable_contract_pass": firm_contracts >= MIN_FIRMABLE_COVERAGE,
                }
            )
            for column in FEATURE_COLUMNS:
                values = valid[column].dropna()
                distinct = int(values.nunique(dropna=True))
                modal = (
                    float(values.value_counts(dropna=False).max() / len(values))
                    if len(values)
                    else 1.0
                )
                feature_rows.append(
                    {
                        "sensor": sensor,
                        "year": year,
                        "feature": column,
                        "distinct_values": distinct,
                        "modal_fraction": modal,
                        "finite": bool(np.isfinite(values.to_numpy(dtype=float)).all()),
                        "distinct_pass": distinct >= 2,
                        "modal_pass": modal < MAX_MODAL_FRACTION,
                    }
                )
    month_rows = []
    for (sensor, month), subset in features.groupby(
        ["sensor", "month"], observed=True, sort=True
    ):
        count = int(subset["event_valid"].astype(bool).sum())
        month_rows.append(
            {
                "sensor": sensor,
                "month": month,
                "sessions": int(len(subset)),
                "valid_events": count,
                "minimum_pass": count >= MIN_MONTHLY_EVENTS,
            }
        )
    annual = pd.DataFrame(annual_rows)
    monthly = pd.DataFrame(month_rows)
    feature_quality = pd.DataFrame(feature_rows)
    annual_pass = bool(
        len(annual) == 6
        and annual[
            ["coverage_pass", "firmable_premium_pass", "firmable_contract_pass"]
        ].to_numpy(dtype=bool).all()
    )
    monthly_pass = bool(len(monthly) == 72 and monthly["minimum_pass"].all())
    feature_pass = bool(
        len(feature_quality) == 6 * len(FEATURE_COLUMNS)
        and feature_quality[
            ["finite", "distinct_pass", "modal_pass"]
        ].to_numpy(dtype=bool).all()
    )
    passed = annual_pass and monthly_pass and feature_pass
    summary = {
        "schema": "cross_venue_opra_trade_quote_flow_v5_data_gate_summary_v1",
        "status": "PASS_OUTCOME_FREE_DATA_GATE" if passed else "FAILED_OUTCOME_FREE_DATA_GATE",
        "passed": passed,
        "market_values_accessed": True,
        "outcome_clock_accessed": False,
        "outcome_2026_accessed": False,
        "production_modified": False,
        "captures": int(len(features)),
        "valid_events": int(features["event_valid"].astype(bool).sum()),
        "annual_gate_pass": annual_pass,
        "monthly_gate_pass": monthly_pass,
        "feature_gate_pass": feature_pass,
        "minimum_event_coverage": MIN_EVENT_COVERAGE,
        "minimum_monthly_events": MIN_MONTHLY_EVENTS,
        "minimum_firmable_coverage": MIN_FIRMABLE_COVERAGE,
        "maximum_modal_fraction_exclusive": MAX_MODAL_FRACTION,
        "feature_count": len(FEATURE_COLUMNS),
        "half_days_audit_only_for_later_economics": sorted(HALF_DAYS),
    }
    return annual, monthly, feature_quality, summary


def _assert_frame_close(
    expected: pd.DataFrame,
    observed: pd.DataFrame,
    *,
    keys: tuple[str, ...],
    numeric: tuple[str, ...],
    boolean: tuple[str, ...],
) -> None:
    left = expected.sort_values(list(keys), kind="stable").reset_index(drop=True)
    right = observed.sort_values(list(keys), kind="stable").reset_index(drop=True)
    if len(left) != len(right):
        raise AssertionError("independent frame cardinality differs")
    for column in keys:
        if not left[column].astype(str).equals(right[column].astype(str)):
            raise AssertionError(f"independent key differs: {column}")
    for column in numeric:
        if not np.allclose(
            pd.to_numeric(left[column]).to_numpy(dtype=float),
            pd.to_numeric(right[column]).to_numpy(dtype=float),
            rtol=0.0,
            atol=1e-12,
            equal_nan=True,
        ):
            raise AssertionError(f"independent numeric field differs: {column}")
    for column in boolean:
        if not left[column].astype(bool).equals(right[column].astype(bool)):
            raise AssertionError(f"independent boolean field differs: {column}")


def audit_gate(gate_root: Path) -> dict[str, Any]:
    manifest_path = gate_root / "manifest.json"
    seal_path = gate_root / "seal.json"
    if not (manifest_path.is_file() and seal_path.is_file()):
        raise FileNotFoundError("V5 data gate evidence is incomplete")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    if (
        sha256_file(manifest_path) != seal.get("manifest_sha256")
        or seal.get("outcome_clock_accessed") is not False
        or seal.get("outcome_2026_accessed") is not False
        or seal.get("production_modified") is not False
    ):
        raise AssertionError("V5 data gate seal is invalid")
    for name, digest in manifest["artifact_hashes"].items():
        if sha256_file(gate_root / name) != digest:
            raise AssertionError(f"V5 gate artifact hash changed: {name}")
    sources = pd.read_csv(
        gate_root / "source_inventory.csv",
        dtype={"trade_date": str, "expiration": str},
    )
    if len(sources) != EXPECTED_CAPTURES or sources["trade_date"].str.startswith(
        "2026"
    ).any():
        raise AssertionError("V5 audit source inventory changed")
    feature_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    rehash_rows: list[dict[str, Any]] = []
    for record in sources.sort_values(["sensor", "trade_date"], kind="stable").to_dict(
        "records"
    ):
        raw_path = Path(record["raw_path"])
        parquet_path = Path(record["parquet_path"])
        manifest_source_path = Path(record["manifest_path"])
        observed = {
            "raw_sha256": sha256_file(raw_path),
            "parquet_sha256": sha256_file(parquet_path),
            "manifest_sha256": sha256_file(manifest_source_path),
        }
        if any(observed[key] != record[key] for key in observed):
            raise AssertionError("V5 independent source rehash mismatch")
        sensor = str(record["sensor"])
        trade_date = str(record["trade_date"])
        rebuilt = _parse_raw(
            raw_path.read_bytes(), sensor=sensor, trade_date=trade_date
        )
        pd.testing.assert_frame_equal(
            pd.read_parquet(parquet_path), rebuilt, check_dtype=True
        )
        feature, audit = recompute_session(
            rebuilt, sensor=sensor, trade_date=trade_date
        )
        feature_rows.append(feature)
        audit_rows.append(audit)
        rehash_rows.append(
            {
                "capture_id": record["capture_id"],
                "sensor": sensor,
                "trade_date": trade_date,
                **observed,
                "rows": int(len(rebuilt)),
            }
        )
    features = pd.DataFrame(feature_rows)
    audits = pd.DataFrame(audit_rows)
    stored_features = pd.read_csv(
        gate_root / "feature_view.csv", dtype={"trade_date": str}
    )
    stored_audits = pd.read_csv(
        gate_root / "session_audit.csv", dtype={"trade_date": str}
    )
    _assert_frame_close(
        features,
        stored_features,
        keys=("sensor", "trade_date", "year", "month"),
        numeric=FEATURE_COLUMNS,
        boolean=("calendar_half_day", "event_valid"),
    )
    audit_numeric = tuple(
        column
        for column in audits.columns
        if column
        not in {
            "sensor",
            "trade_date",
            "year",
            "month",
            "full_valid",
            "w15_valid",
            "w5_valid",
            "event_valid",
            "outcome_clock_accessed",
            "outcome_2026_accessed",
        }
    )
    _assert_frame_close(
        audits,
        stored_audits,
        keys=("sensor", "trade_date", "year", "month"),
        numeric=audit_numeric,
        boolean=(
            "full_valid",
            "w15_valid",
            "w5_valid",
            "event_valid",
            "outcome_clock_accessed",
            "outcome_2026_accessed",
        ),
    )
    annual, monthly, quality, summary = recompute_gate(features, audits)
    stored_summary = json.loads((gate_root / "gate_summary.json").read_text())
    if summary != stored_summary:
        raise AssertionError("V5 independent gate summary differs")
    _assert_frame_close(
        annual,
        pd.read_csv(gate_root / "sensor_year_quality.csv", dtype={"year": str}),
        keys=("sensor", "year"),
        numeric=(
            "sessions",
            "valid_events",
            "event_coverage",
            "firmable_premium_coverage",
            "firmable_contract_coverage",
        ),
        boolean=(
            "coverage_pass",
            "firmable_premium_pass",
            "firmable_contract_pass",
        ),
    )
    _assert_frame_close(
        monthly,
        pd.read_csv(gate_root / "sensor_month_coverage.csv", dtype={"month": str}),
        keys=("sensor", "month"),
        numeric=("sessions", "valid_events"),
        boolean=("minimum_pass",),
    )
    _assert_frame_close(
        quality,
        pd.read_csv(gate_root / "feature_quality.csv", dtype={"year": str}),
        keys=("sensor", "year", "feature"),
        numeric=("distinct_values", "modal_fraction"),
        boolean=("finite", "distinct_pass", "modal_pass"),
    )
    return {
        "features": features,
        "audits": audits,
        "annual": annual,
        "monthly": monthly,
        "quality": quality,
        "rehash": pd.DataFrame(rehash_rows),
        "gate_summary": summary,
        "gate_manifest_sha256": sha256_file(manifest_path),
        "gate_seal_sha256": sha256_file(seal_path),
    }


def write_audit(
    output: Path,
    *,
    result: dict[str, Any],
    git_commit: str,
    code_hashes: dict[str, str],
) -> dict[str, Any]:
    staging = output.with_name(output.name + ".staging")
    if output.exists() or staging.exists():
        raise FileExistsError(f"immutable V5 audit output exists: {output}")
    staging.mkdir(parents=True)
    frames = {
        "recomputed_feature_view.csv": result["features"],
        "recomputed_session_audit.csv": result["audits"],
        "recomputed_sensor_year_quality.csv": result["annual"],
        "recomputed_sensor_month_coverage.csv": result["monthly"],
        "recomputed_feature_quality.csv": result["quality"],
        "source_rehash.csv": result["rehash"],
    }
    for name, frame in frames.items():
        frame.to_csv(staging / name, index=False, lineterminator="\n")
    hashes = {name: sha256_file(staging / name) for name in frames}
    summary = {
        "schema": "cross_venue_opra_trade_quote_flow_v5_data_gate_audit_v1",
        "status": "PASS_INDEPENDENT_OUTCOME_FREE_DATA_GATE_AUDIT",
        "audited_gate_status": result["gate_summary"]["status"],
        "audited_gate_passed": result["gate_summary"]["passed"],
        "outcome_clock_accessed": False,
        "outcome_2026_accessed": False,
        "production_modified": False,
        "git_commit": git_commit,
        "code_hashes": code_hashes,
        "sources_rehashed": int(len(result["rehash"])),
        "source_hash_mismatches": 0,
        "features_recomputed": int(len(result["features"])),
        "gate_manifest_sha256": result["gate_manifest_sha256"],
        "gate_seal_sha256": result["gate_seal_sha256"],
        "artifact_hashes": hashes,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    summary_path = staging / "audit_summary.json"
    summary_path.write_bytes(canonical_bytes(summary))
    seal = {
        "schema": "cross_venue_opra_trade_quote_flow_v5_data_gate_audit_seal_v1",
        "status": summary["status"],
        "audited_gate_status": summary["audited_gate_status"],
        "outcome_clock_accessed": False,
        "outcome_2026_accessed": False,
        "production_modified": False,
        "audit_summary_sha256": sha256_file(summary_path),
        "source_rehash_sha256": hashes["source_rehash.csv"],
        "recomputed_feature_view_sha256": hashes["recomputed_feature_view.csv"],
    }
    (staging / "seal.json").write_bytes(canonical_bytes(seal))
    staging.rename(output)
    return {**summary, **seal}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-root", type=Path, default=DEFAULT_GATE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    git_commit, code_hashes = committed_state()
    result = audit_gate(args.gate_root.resolve())
    summary = write_audit(
        args.output_root.resolve(),
        result=result,
        git_commit=git_commit,
        code_hashes=code_hashes,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
