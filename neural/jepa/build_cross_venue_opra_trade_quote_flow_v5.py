"""Build the outcome-free V5 feature view and fail-closed data gate."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa import (  # noqa: E402
    capture_cross_venue_opra_trade_quote_flow_v5 as capture,
)
from neural.jepa.wall_surface_flow_environment import sha256_file  # noqa: E402

DEFAULT_CAPTURE_ROOT = capture.DEFAULT_OUTPUT
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_opra_trade_quote_flow_v5_data_gate_2023_2025_v1"
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
MIN_EVENT_COVERAGE = 0.90
MIN_MONTHLY_EVENTS = 13
MIN_FIRMABLE_COVERAGE = 0.80
MAX_MODAL_FRACTION = 0.995


def _side(frame: pd.DataFrame) -> np.ndarray:
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


def _window_features(frame: pd.DataFrame) -> tuple[dict[str, float], bool]:
    values = {feature: math.nan for feature in BASE_FEATURES}
    if frame.empty or set(frame["right"].unique()) != {"C", "P"}:
        return values, False
    premium = frame["price"].to_numpy(dtype=float) * frame["size"].to_numpy(
        dtype=float
    ) * 100.0
    size = frame["size"].to_numpy(dtype=float)
    side = frame["print_side"].to_numpy(dtype=float)
    call = frame["right"].eq("C").to_numpy()
    put = ~call
    total_premium = float(premium.sum())
    total_size = float(size.sum())
    total_prints = int(len(frame))
    if total_premium <= 0 or total_size <= 0 or total_prints <= 0:
        return values, False
    call_premium = float(premium[call].sum())
    put_premium = float(premium[put].sum())
    call_size = float(size[call].sum())
    put_size = float(size[put].sum())
    call_prints = int(call.sum())
    put_prints = int(put.sum())
    values = {
        "directional_premium_imbalance": float(
            ((side[call] * premium[call]).sum() - (side[put] * premium[put]).sum())
            / total_premium
        ),
        "directional_contract_imbalance": float(
            ((side[call] * size[call]).sum() - (side[put] * size[put]).sum())
            / total_size
        ),
        "directional_print_imbalance": float(
            (side[call].sum() - side[put].sum()) / total_prints
        ),
        "call_put_premium_imbalance": float(
            (call_premium - put_premium) / total_premium
        ),
        "call_put_contract_imbalance": float(
            (call_size - put_size) / total_size
        ),
        "call_put_print_imbalance": float(
            (call_prints - put_prints) / total_prints
        ),
        "log_total_contracts": float(np.log1p(total_size)),
        "log_total_premium": float(np.log1p(total_premium)),
    }
    return values, bool(np.isfinite(list(values.values())).all())


def compute_session_features(
    trades: pd.DataFrame, *, sensor: str, trade_date: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    required = set(capture.TRADE_COLUMNS)
    missing = sorted(required.difference(trades.columns))
    if missing:
        raise KeyError(f"stored V5 trades lack fields: {missing}")
    if not trades["symbol"].eq(sensor).all():
        raise AssertionError("stored V5 symbol changed")
    accepted_condition = trades["condition"].isin([0, 18])
    base_valid = (
        accepted_condition
        & trades["size"].gt(0)
        & trades["price"].gt(0)
        & trades["bid"].gt(0)
        & trades["ask"].gt(trades["bid"])
        & trades["quote_timestamp"].lt(trades["trade_timestamp"])
        & trades["right"].isin(["C", "P"])
    )
    alpha = trades.loc[base_valid].copy()
    alpha["print_side"] = _side(alpha)
    alpha["premium_dollars"] = (
        alpha["price"].astype(float) * alpha["size"].astype(float) * 100.0
    )
    features: dict[str, Any] = {
        "sensor": sensor,
        "trade_date": trade_date,
        "year": trade_date[:4],
        "month": trade_date[:6],
        "calendar_half_day": trade_date in HALF_DAYS,
    }
    window_valid: dict[str, bool] = {}
    for name, (start_clock, end_clock) in WINDOWS.items():
        start = pd.Timestamp(
            f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} {start_clock}"
        )
        end = pd.Timestamp(
            f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} {end_clock}"
        )
        window = alpha.loc[
            alpha["trade_timestamp"].ge(start)
            & alpha["trade_timestamp"].lt(end)
        ]
        values, valid = _window_features(window)
        window_valid[name] = valid
        features.update({f"{name}_{key}": value for key, value in values.items()})
    feature_array = np.asarray(
        [features[column] for column in FEATURE_COLUMNS], dtype=float
    )
    event_valid = bool(all(window_valid.values()) and np.isfinite(feature_array).all())
    total_alpha_premium = float(alpha["premium_dollars"].sum())
    total_alpha_contracts = float(alpha["size"].sum())
    firmable = alpha["print_side"].ne(0)
    quote_age_ms = (
        trades["trade_timestamp"] - trades["quote_timestamp"]
    ).dt.total_seconds() * 1000.0
    audit = {
        "sensor": sensor,
        "trade_date": trade_date,
        "year": trade_date[:4],
        "month": trade_date[:6],
        "rows_total": int(len(trades)),
        "rows_condition_accepted": int(accepted_condition.sum()),
        "rows_alpha_valid": int(len(alpha)),
        "rows_condition_excluded": int((~accepted_condition).sum()),
        "rows_locked_crossed_or_nonpositive_quote": int(
            ((trades["bid"] <= 0) | (trades["ask"] <= trades["bid"])).sum()
        ),
        "rows_nonpositive_trade": int(
            ((trades["size"] <= 0) | (trades["price"] <= 0)).sum()
        ),
        "rows_midpoint_unfirmable": int((alpha["print_side"] == 0).sum()),
        "alpha_premium": total_alpha_premium,
        "alpha_contracts": total_alpha_contracts,
        "firmable_premium": float(alpha.loc[firmable, "premium_dollars"].sum()),
        "firmable_contracts": float(alpha.loc[firmable, "size"].sum()),
        "quote_age_ms_max": float(quote_age_ms.max()),
        "quote_age_ms_median": float(quote_age_ms.median()),
        "full_valid": window_valid["full"],
        "w15_valid": window_valid["w15"],
        "w5_valid": window_valid["w5"],
        "event_valid": event_valid,
        "outcome_clock_accessed": False,
        "outcome_2026_accessed": False,
    }
    features["event_valid"] = event_valid
    return features, audit


def validate_capture(capture_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    seal_path = capture_root / "_seal/seal.json"
    index_path = capture_root / "_seal/capture_index.csv"
    if not (seal_path.is_file() and index_path.is_file()):
        raise FileNotFoundError("V5 source capture is not sealed")
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    if (
        seal.get("status") != "PASS_OUTCOME_FREE_SOURCE_CAPTURE"
        or seal.get("outcome_clock_accessed") is not False
        or seal.get("outcome_2026_accessed") is not False
        or seal.get("production_modified") is not False
        or int(seal.get("captures", -1)) != capture.EXPECTED_CAPTURES
        or sha256_file(index_path) != seal.get("capture_index_sha256")
    ):
        raise AssertionError("V5 source capture seal is invalid")
    index = pd.read_csv(index_path, dtype={"trade_date": str, "expiration": str})
    if (
        len(index) != capture.EXPECTED_CAPTURES
        or index["capture_id"].duplicated().any()
        or index["trade_date"].str.startswith("2026").any()
    ):
        raise AssertionError("V5 source capture index changed")
    return index, seal


def build_from_capture(
    capture_root: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    root = Path(capture_root).resolve()
    index, capture_seal = validate_capture(root)
    feature_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    for record in index.sort_values(["sensor", "trade_date"], kind="stable").to_dict(
        "records"
    ):
        directory = root / str(record["sensor"]) / str(record["trade_date"])
        raw_path = directory / "response.ndjson"
        parquet_path = directory / "trades.parquet"
        manifest_path = directory / "manifest.json"
        if not (raw_path.is_file() and parquet_path.is_file() and manifest_path.is_file()):
            raise FileNotFoundError(f"missing sealed V5 source: {directory}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            sha256_file(raw_path) != record["raw_sha256"]
            or sha256_file(parquet_path) != record["parquet_sha256"]
            or sha256_file(manifest_path) != record["manifest_sha256"]
            or manifest.get("outcome_clock_accessed") is not False
            or manifest.get("outcome_2026_accessed") is not False
        ):
            raise AssertionError(f"sealed V5 source hash/flags changed: {directory}")
        spec = {
            "sensor": str(record["sensor"]),
            "trade_date": str(record["trade_date"]),
            "expiration": str(record["expiration"]),
        }
        rebuilt = capture.normalize_trade_quote(raw_path.read_bytes(), spec)
        stored = pd.read_parquet(parquet_path)
        pd.testing.assert_frame_equal(stored, rebuilt, check_dtype=True)
        features, audit = compute_session_features(
            rebuilt, sensor=spec["sensor"], trade_date=spec["trade_date"]
        )
        feature_rows.append(features)
        audit_rows.append(audit)
        source_rows.append(
            {
                **record,
                "raw_path": str(raw_path),
                "parquet_path": str(parquet_path),
                "manifest_path": str(manifest_path),
            }
        )
    features = pd.DataFrame(feature_rows).sort_values(
        ["sensor", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    audit = pd.DataFrame(audit_rows).sort_values(
        ["sensor", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    sources = pd.DataFrame(source_rows).sort_values(
        ["sensor", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if len(features) != capture.EXPECTED_CAPTURES:
        raise AssertionError("V5 feature cardinality changed")
    return features, audit, sources, capture_seal


def evaluate_gate(
    features: pd.DataFrame, audit: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    annual_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    for sensor in capture.SENSORS:
        for year in capture.YEARS:
            subset = features[
                features["sensor"].eq(sensor) & features["year"].eq(year)
            ]
            quality = audit[
                audit["sensor"].eq(sensor) & audit["year"].eq(year)
            ]
            valid = subset[subset["event_valid"].astype(bool)]
            coverage = len(valid) / len(subset) if len(subset) else 0.0
            alpha_premium = float(quality["alpha_premium"].sum())
            alpha_contracts = float(quality["alpha_contracts"].sum())
            firmable_premium = (
                float(quality["firmable_premium"].sum()) / alpha_premium
                if alpha_premium > 0
                else 0.0
            )
            firmable_contracts = (
                float(quality["firmable_contracts"].sum()) / alpha_contracts
                if alpha_contracts > 0
                else 0.0
            )
            annual_rows.append(
                {
                    "sensor": sensor,
                    "year": year,
                    "sessions": int(len(subset)),
                    "valid_events": int(len(valid)),
                    "event_coverage": coverage,
                    "firmable_premium_coverage": firmable_premium,
                    "firmable_contract_coverage": firmable_contracts,
                    "coverage_pass": coverage >= MIN_EVENT_COVERAGE,
                    "firmable_premium_pass": firmable_premium
                    >= MIN_FIRMABLE_COVERAGE,
                    "firmable_contract_pass": firmable_contracts
                    >= MIN_FIRMABLE_COVERAGE,
                }
            )
            for feature in FEATURE_COLUMNS:
                values = valid[feature].dropna()
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
                        "feature": feature,
                        "distinct_values": distinct,
                        "modal_fraction": modal,
                        "finite": bool(np.isfinite(values.to_numpy(dtype=float)).all()),
                        "distinct_pass": distinct >= 2,
                        "modal_pass": modal < MAX_MODAL_FRACTION,
                    }
                )
    for (sensor, month), subset in features.groupby(
        ["sensor", "month"], observed=True, sort=True
    ):
        valid_events = int(subset["event_valid"].astype(bool).sum())
        monthly_rows.append(
            {
                "sensor": sensor,
                "month": month,
                "sessions": int(len(subset)),
                "valid_events": valid_events,
                "minimum_pass": valid_events >= MIN_MONTHLY_EVENTS,
            }
        )
    annual = pd.DataFrame(annual_rows)
    monthly = pd.DataFrame(monthly_rows)
    feature_quality = pd.DataFrame(feature_rows)
    expected_months = len(capture.SENSORS) * len(capture.YEARS) * 12
    annual_pass = bool(
        len(annual) == len(capture.SENSORS) * len(capture.YEARS)
        and annual[
            ["coverage_pass", "firmable_premium_pass", "firmable_contract_pass"]
        ].to_numpy(dtype=bool).all()
    )
    monthly_pass = bool(
        len(monthly) == expected_months and monthly["minimum_pass"].all()
    )
    feature_pass = bool(
        len(feature_quality)
        == len(capture.SENSORS) * len(capture.YEARS) * len(FEATURE_COLUMNS)
        and feature_quality[
            ["finite", "distinct_pass", "modal_pass"]
        ].to_numpy(dtype=bool).all()
    )
    passed = annual_pass and monthly_pass and feature_pass
    gate = {
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
    return annual, monthly, feature_quality, gate


def write_gate(
    output: Path,
    *,
    features: pd.DataFrame,
    audit: pd.DataFrame,
    sources: pd.DataFrame,
    capture_seal: dict[str, Any],
    annual: pd.DataFrame,
    monthly: pd.DataFrame,
    feature_quality: pd.DataFrame,
    gate: dict[str, Any],
    git_commit: str,
    code_hashes: dict[str, str],
) -> dict[str, Any]:
    staging = output.with_name(output.name + ".staging")
    if output.exists() or staging.exists():
        raise FileExistsError(f"immutable V5 data gate output exists: {output}")
    staging.mkdir(parents=True)
    frames = {
        "feature_view.csv": features,
        "session_audit.csv": audit,
        "source_inventory.csv": sources,
        "sensor_year_quality.csv": annual,
        "sensor_month_coverage.csv": monthly,
        "feature_quality.csv": feature_quality,
    }
    for name, frame in frames.items():
        frame.to_csv(staging / name, index=False, lineterminator="\n")
    (staging / "gate_summary.json").write_bytes(capture.canonical_bytes(gate))
    artifact_hashes = {
        name: sha256_file(staging / name)
        for name in (*frames.keys(), "gate_summary.json")
    }
    manifest = {
        "schema": "cross_venue_opra_trade_quote_flow_v5_data_gate_manifest_v1",
        "status": gate["status"],
        "passed": gate["passed"],
        "market_values_accessed": True,
        "outcome_clock_accessed": False,
        "outcome_2026_accessed": False,
        "production_modified": False,
        "git_commit": git_commit,
        "code_hashes": code_hashes,
        "capture_git_commit": capture_seal["git_commit"],
        "capture_index_sha256": capture_seal["capture_index_sha256"],
        "capture_rows": capture_seal["rows"],
        "capture_raw_bytes": capture_seal["raw_bytes"],
        "artifact_hashes": artifact_hashes,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = staging / "manifest.json"
    manifest_path.write_bytes(capture.canonical_bytes(manifest))
    seal = {
        "schema": "cross_venue_opra_trade_quote_flow_v5_data_gate_seal_v1",
        "status": gate["status"],
        "passed": gate["passed"],
        "outcome_clock_accessed": False,
        "outcome_2026_accessed": False,
        "production_modified": False,
        "manifest_sha256": sha256_file(manifest_path),
        "feature_view_sha256": artifact_hashes["feature_view.csv"],
        "source_inventory_sha256": artifact_hashes["source_inventory.csv"],
        "gate_summary_sha256": artifact_hashes["gate_summary.json"],
    }
    (staging / "seal.json").write_bytes(capture.canonical_bytes(seal))
    staging.rename(output)
    return seal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", type=Path, default=DEFAULT_CAPTURE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    git_commit, code_hashes = capture.committed_code_state()
    features, audit, sources, capture_seal = build_from_capture(args.capture_root)
    annual, monthly, feature_quality, gate = evaluate_gate(features, audit)
    seal = write_gate(
        args.output_root.resolve(),
        features=features,
        audit=audit,
        sources=sources,
        capture_seal=capture_seal,
        annual=annual,
        monthly=monthly,
        feature_quality=feature_quality,
        gate=gate,
        git_commit=git_commit,
        code_hashes=code_hashes,
    )
    print(json.dumps({**gate, **seal}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
