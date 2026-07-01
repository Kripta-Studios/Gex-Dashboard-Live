from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.event_option_component_live import (  # noqa: E402
    EventOptionComponentRegistry,
    _as_medians,
    _prepare_feature_frame,
)
from neural.jepa.event_option_live_scorer import score_event_option_live_candidates  # noqa: E402

DEFAULT_PACKAGE = Path(
    "neural/models/jepa/jepa_production_event_options_backfill19_spy_no_scorethr_wf2026_fullmayjun"
)
DEFAULT_REGISTRY = DEFAULT_PACKAGE / "component_registry.json"
DEFAULT_REFERENCE = DEFAULT_PACKAGE / "deploy_combined_select_trades.csv"
DEFAULT_XINPUT = Path("neural/models/jepa/xinput_v3_production/normalizers.json")


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else default
    except Exception:
        return default


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        out = float(value)
        return out if math.isfinite(out) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value


def _series_stats(values: pd.Series) -> dict[str, float | None]:
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if numeric.empty:
        return {"n": 0, "median": None, "q01": None, "q25": None, "q75": None, "q99": None, "iqr": None, "mean": None, "std": None}
    q = numeric.quantile([0.01, 0.25, 0.5, 0.75, 0.99])
    return {
        "n": int(len(numeric)),
        "median": float(q.loc[0.5]),
        "q01": float(q.loc[0.01]),
        "q25": float(q.loc[0.25]),
        "q75": float(q.loc[0.75]),
        "q99": float(q.loc[0.99]),
        "iqr": float(q.loc[0.75] - q.loc[0.25]),
        "mean": float(numeric.mean()),
        "std": float(numeric.std(ddof=0)),
    }


def _robust_z(value: float, stats: dict[str, float | None]) -> float | None:
    median = stats.get("median")
    iqr = stats.get("iqr")
    std = stats.get("std")
    scale = None
    if iqr is not None and abs(float(iqr)) > 1e-12:
        scale = float(iqr) / 1.349
    elif std is not None and abs(float(std)) > 1e-12:
        scale = float(std)
    if median is None or scale is None:
        return None
    return float((value - float(median)) / scale)


def _top_feature_drifts(
    live_x: pd.DataFrame,
    reference_x: pd.DataFrame,
    *,
    max_rows: int = 15,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    missing_reference = 0
    zero_scale_changed = 0
    nonfinite_live = 0
    for col in live_x.columns:
        live_values = pd.to_numeric(live_x[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        finite_live = live_values.dropna()
        if len(finite_live) != len(live_values):
            nonfinite_live += int(len(live_values) - len(finite_live))
        if finite_live.empty:
            rows.append({"feature": col, "flag": "live_nonfinite", "live_value": None})
            continue
        live_value = float(finite_live.iloc[-1])
        if col not in reference_x.columns:
            missing_reference += 1
            rows.append({"feature": col, "flag": "missing_reference", "live_value": live_value})
            continue
        stats = _series_stats(reference_x[col])
        if not stats.get("n"):
            missing_reference += 1
            rows.append({"feature": col, "flag": "empty_reference", "live_value": live_value})
            continue
        rz = _robust_z(live_value, stats)
        q01 = stats.get("q01")
        q99 = stats.get("q99")
        outside_1_99 = q01 is not None and q99 is not None and (live_value < float(q01) or live_value > float(q99))
        if rz is None:
            median = stats.get("median")
            changed = median is not None and abs(live_value - float(median)) > 1e-9
            if changed:
                zero_scale_changed += 1
            rows.append(
                {
                    "feature": col,
                    "live_value": live_value,
                    "reference_median": median,
                    "reference_iqr": stats.get("iqr"),
                    "robust_z": None,
                    "outside_reference_p01_p99": outside_1_99,
                    "zero_scale_changed": changed,
                }
            )
            continue
        rows.append(
            {
                "feature": col,
                "live_value": live_value,
                "reference_median": stats.get("median"),
                "reference_q01": q01,
                "reference_q99": q99,
                "reference_iqr": stats.get("iqr"),
                "robust_z": rz,
                "abs_robust_z": abs(rz),
                "outside_reference_p01_p99": outside_1_99,
            }
        )
    sorted_rows = sorted(rows, key=lambda r: float(r.get("abs_robust_z") or 0.0), reverse=True)
    summary = {
        "feature_count": int(len(live_x.columns)),
        "missing_reference_features": int(missing_reference),
        "zero_scale_changed_features": int(zero_scale_changed),
        "nonfinite_live_values": int(nonfinite_live),
        "features_abs_robust_z_gt_6": int(sum(1 for r in rows if float(r.get("abs_robust_z") or 0.0) > 6.0)),
        "features_abs_robust_z_gt_10": int(sum(1 for r in rows if float(r.get("abs_robust_z") or 0.0) > 10.0)),
        "features_outside_reference_p01_p99": int(sum(1 for r in rows if r.get("outside_reference_p01_p99"))),
        "max_abs_robust_z": float(max([float(r.get("abs_robust_z") or 0.0) for r in rows] or [0.0])),
    }
    return sorted_rows[:max_rows], summary


def audit_event_option(
    *,
    registry_path: Path,
    live_snapshots_path: Path,
    reference_path: Path,
    strict_features: bool,
) -> dict[str, Any]:
    registry = EventOptionComponentRegistry.from_path(
        registry_path,
        project_root=PROJECT_ROOT,
        require_complete_live_equivalence=True,
    )
    live_snapshots = pd.read_parquet(live_snapshots_path)
    reference = pd.read_csv(reference_path, low_memory=False)
    score_candidates, score_issues, enriched = score_event_option_live_candidates(
        registry,
        live_snapshots,
        strict_features=strict_features,
    )
    component_rows: list[dict[str, Any]] = []
    for name, component in sorted(registry.components.items()):
        if component.kind != "event_option_gate_direction_model":
            continue
        payload = component.model_payload()
        feature_cols = [str(col) for col in payload.get("feature_cols", component.metadata.get("feature_cols", []))]
        medians = _as_medians(payload.get("medians", component.metadata.get("feature_medians", {})))
        tickers = [str(t).upper() for t in component.registry_entry.get("tickers", component.metadata.get("tickers", []))]
        ticker = tickers[0] if tickers else str(name).split(".", 1)[0].upper()
        live_part = live_snapshots[live_snapshots["ticker"].astype(str).str.upper().eq(ticker)].copy()
        if "expiry_mode" in live_part.columns:
            live_part = live_part[live_part["expiry_mode"].astype(str).eq("zero_dte")].copy()
        ref_part = reference[reference["ticker"].astype(str).str.upper().eq(ticker)].copy()
        if "expiry_mode" in ref_part.columns:
            ref_part = ref_part[ref_part["expiry_mode"].astype(str).eq("zero_dte")].copy()
        source_name = str(component.registry_entry.get("source_name", component.metadata.get("source_name", "")))
        ref_filter = "ticker_zero_dte"
        if source_name and "source_stream" in ref_part.columns:
            candidate_ref = ref_part[ref_part["source_stream"].astype(str).eq(source_name)].copy()
            if len(candidate_ref) >= 20:
                ref_part = candidate_ref
                ref_filter = f"ticker_zero_dte_source_stream={source_name}"
        if live_part.empty or ref_part.empty:
            component_rows.append(
                {
                    "component": name,
                    "ticker": ticker,
                    "live_rows": int(len(live_part)),
                    "reference_rows": int(len(ref_part)),
                    "status": "insufficient_rows",
                }
            )
            continue
        live_x, live_missing = _prepare_feature_frame(live_part, feature_cols, medians, strict=False)
        ref_x, ref_missing = _prepare_feature_frame(ref_part, feature_cols, medians, strict=False)
        top, summary = _top_feature_drifts(live_x, ref_x)
        status = "ok"
        if live_missing and strict_features:
            status = "missing_live_features"
        elif summary["nonfinite_live_values"]:
            status = "nonfinite_live_values"
        elif summary["features_abs_robust_z_gt_10"] > max(3, int(0.05 * len(feature_cols))):
            status = "massive_distribution_shift"
        elif summary["features_abs_robust_z_gt_10"] > 0 or summary["features_abs_robust_z_gt_6"] > max(5, int(0.10 * len(feature_cols))):
            status = "review_feature_drift"
        component_rows.append(
            {
                "component": name,
                "ticker": ticker,
                "source_name": source_name,
                "reference_filter": ref_filter,
                "live_rows": int(len(live_part)),
                "reference_rows": int(len(ref_part)),
                "feature_cols": int(len(feature_cols)),
                "missing_live_feature_count": int(len(live_missing)),
                "missing_reference_feature_count": int(len(ref_missing)),
                "status": status,
                "summary": summary,
                "top_feature_drifts": top,
            }
        )
    bad_statuses = {"insufficient_rows", "missing_live_features", "nonfinite_live_values", "massive_distribution_shift"}
    return {
        "live_snapshots_path": str(live_snapshots_path),
        "reference_path": str(reference_path),
        "snapshot_rows": int(len(live_snapshots)),
        "snapshot_tickers": sorted(live_snapshots.get("ticker", pd.Series(dtype=str)).astype(str).str.upper().unique().tolist()),
        "snapshot_expiry_modes": live_snapshots.get("expiry_mode", pd.Series(dtype=str)).astype(str).value_counts().to_dict(),
        "scored_candidate_rows": int(len(score_candidates)),
        "scored_candidate_tickers": sorted(score_candidates.get("ticker", pd.Series(dtype=str)).astype(str).str.upper().unique().tolist()) if not score_candidates.empty else [],
        "score_issues": list(score_issues),
        "component_audits": component_rows,
        "passed": bool(not score_issues and all(row.get("status") not in bad_statuses for row in component_rows)),
    }


def audit_xinput_features(*, day_dir: Path, normalizers_path: Path) -> dict[str, Any]:
    normalizers = json.loads(normalizers_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for path in sorted(day_dir.glob("ml_features_*_latest.parquet")):
        name = path.name
        if name.startswith("ml_features_1m_"):
            continue
        ticker = name.removeprefix("ml_features_").removesuffix("_latest.parquet")
        df = pd.read_parquet(path)
        if df.empty:
            rows.append({"ticker": ticker, "path": str(path), "status": "empty"})
            continue
        latest = df.tail(1).copy()
        ticker_payload: dict[str, Any] = {
            "ticker": ticker,
            "path": str(path),
            "rows": int(len(df)),
            "timestamp": str(latest.iloc[-1].get("timestamp", "")),
            "live_feature_context_valid": _safe_float(latest.iloc[-1].get("live_feature_context_valid"), None),
            "xjepa_context_valid": _safe_float(latest.iloc[-1].get("xjepa_context_valid"), None),
            "groups": {},
        }
        group_statuses = []
        for group_name, cfg in normalizers.items():
            features = [str(col) for col in cfg.get("feature_names", [])]
            med = pd.Series(cfg.get("median", []), index=features, dtype=float)
            iqr = pd.Series(cfg.get("iqr", []), index=features, dtype=float).replace(0.0, np.nan)
            missing = [col for col in features if col not in latest.columns]
            values = latest.reindex(columns=features).apply(pd.to_numeric, errors="coerce").iloc[-1]
            robust = ((values - med) / iqr).replace([np.inf, -np.inf], np.nan)
            top = [
                {
                    "feature": str(col),
                    "value": _safe_float(values.get(col), None),
                    "median": _safe_float(med.get(col), None),
                    "iqr": _safe_float(iqr.get(col), None),
                    "robust_iqr_z": _safe_float(robust.get(col), None),
                    "abs_robust_iqr_z": abs(float(robust.get(col))) if pd.notna(robust.get(col)) else None,
                }
                for col in robust.abs().sort_values(ascending=False).head(12).index
            ]
            missing_values = int(values.isna().sum())
            over_clip = int((robust.abs() > float(cfg.get("clip", 10.0))).sum())
            over_6 = int((robust.abs() > 6.0).sum())
            status = "ok"
            if missing:
                status = "missing_features"
            elif missing_values:
                status = "nan_values"
            elif over_clip:
                status = "beyond_training_clip"
            elif over_6:
                status = "review_feature_drift"
            group_statuses.append(status)
            ticker_payload["groups"][group_name] = {
                "feature_count": int(len(features)),
                "missing_feature_count": int(len(missing)),
                "missing_features_preview": missing[:20],
                "nan_value_count": missing_values,
                "features_abs_robust_iqr_z_gt_6": over_6,
                "features_abs_robust_iqr_z_gt_clip": over_clip,
                "max_abs_robust_iqr_z": _safe_float(robust.abs().max(), 0.0),
                "clip": _safe_float(cfg.get("clip", 10.0), 10.0),
                "status": status,
                "top_feature_drifts": top,
            }
        ticker_payload["status"] = "ok" if all(s in {"ok", "review_feature_drift"} for s in group_statuses) else "failed"
        rows.append(ticker_payload)
    return {
        "day_dir": str(day_dir),
        "normalizers_path": str(normalizers_path),
        "ticker_audits": rows,
        "passed": bool(rows and all(row.get("status") == "ok" for row in rows)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit live event-option and XInputJEPA feature drift against production references.")
    parser.add_argument("--day-dir", default="rt_data/20260701")
    parser.add_argument("--live-snapshots", default="")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--reference", default=str(DEFAULT_REFERENCE))
    parser.add_argument("--xinput-normalizers", default=str(DEFAULT_XINPUT))
    parser.add_argument("--output", default="")
    parser.add_argument("--strict-features", action="store_true")
    args = parser.parse_args()

    day_dir = Path(args.day_dir)
    live_snapshots = Path(args.live_snapshots) if args.live_snapshots else day_dir / "event_option_snapshots_latest.parquet"
    output = Path(args.output) if args.output else day_dir / "live_feature_drift_audit.json"
    event_audit = audit_event_option(
        registry_path=Path(args.registry),
        live_snapshots_path=live_snapshots,
        reference_path=Path(args.reference),
        strict_features=bool(args.strict_features),
    )
    xinput_audit = audit_xinput_features(day_dir=day_dir, normalizers_path=Path(args.xinput_normalizers))
    production_passed = bool(event_audit.get("passed"))
    payload = {
        "schema_version": 1,
        "production_passed": production_passed,
        "diagnostic_xinput_jepa_passed": bool(xinput_audit.get("passed")),
        "event_option": event_audit,
        "xinput_jepa": xinput_audit,
        "passed": production_passed,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(_json_safe(payload), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(_json_safe({
        "output": str(output),
        "passed": payload["passed"],
        "production_passed": payload["production_passed"],
        "event_option_passed": event_audit.get("passed"),
        "diagnostic_xinput_jepa_passed": xinput_audit.get("passed"),
        "scored_candidate_rows": event_audit.get("scored_candidate_rows"),
        "event_score_issues": event_audit.get("score_issues"),
        "event_component_statuses": {row["component"]: row["status"] for row in event_audit.get("component_audits", [])},
        "xinput_statuses": {row["ticker"]: row["status"] for row in xinput_audit.get("ticker_audits", [])},
    }), indent=2, allow_nan=False))
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
