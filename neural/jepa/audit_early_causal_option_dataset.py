from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from .event_option_component_live import live_observable_feature_issues_for_columns
    from .walkforward_event_option_gate import metrics
    from .walkforward_event_option_profile_selector import ProfileConfig, prepare_profile
else:
    from event_option_component_live import live_observable_feature_issues_for_columns
    from walkforward_event_option_gate import metrics
    from walkforward_event_option_profile_selector import ProfileConfig, prepare_profile


MONTHS = ["202601", "202602", "202603", "202604", "202605"]
TICKERS = ("SPXW", "QQQ", "SPY")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def minute_grid_issues(minutes: pd.Series, expected_step_minutes: int) -> list[str]:
    issues: list[str] = []
    if expected_step_minutes <= 0:
        return ["expected_step_minutes must be positive"]
    numeric = pd.to_numeric(minutes, errors="coerce")
    if not numeric.between(600, 625).all() or not numeric.mod(expected_step_minutes).eq(0).all():
        issues.append(
            "rows are outside the predeclared 10:00-10:25 "
            f"{expected_step_minutes}-minute grid"
        )
    return issues


def audit_dataset(path: Path, *, expected_step_minutes: int = 5) -> tuple[dict, list[str]]:
    frame = pd.read_parquet(path)
    issues: list[str] = []
    minutes = pd.to_numeric(frame["minute"], errors="coerce")
    months = frame["trade_date"].astype(str).str[:6]
    if frame.empty:
        issues.append("dataset is empty")
    issues.extend(minute_grid_issues(minutes, expected_step_minutes))
    if months.max() > "202605" or months.min() < "202201":
        issues.append(f"unexpected month range {months.min()}..{months.max()}")
    if not frame["option_price_mode"].astype(str).eq("executable_quote").all():
        issues.append("option_price_mode is not uniformly executable_quote")
    profile = ProfileConfig(
        name="target_zero_dte_d25_win",
        delta_bucket=25,
        label_mode="win",
        expiry_modes=("zero_dte",),
        train_scope="target",
    )
    prepared = prepare_profile(
        frame,
        profile,
        clip_return=2.0,
        live_observable_features_only=True,
        entry_start_minute_et=600,
    )
    live_issues = live_observable_feature_issues_for_columns(
        "early_causal_d25_win",
        prepared.feature_cols,
        entry_start_minute_et=600,
    )
    issues.extend(live_issues)
    forbidden = [
        col for col in prepared.feature_cols
        if any(token in col.lower() for token in ("future", "_opt_", "spot_long", "spot_short", "spot_best"))
    ]
    if forbidden:
        issues.append(f"outcome/future features survived: {forbidden[:12]}")
    payload = {
        "path": str(path),
        "sha256": sha256(path),
        "rows": int(len(frame)),
        "tickers": sorted(frame["ticker"].astype(str).unique()),
        "month_min": str(months.min()),
        "month_max": str(months.max()),
        "minute_min": int(minutes.min()),
        "minute_max": int(minutes.max()),
        "expected_step_minutes": int(expected_step_minutes),
        "feature_count": int(len(prepared.feature_cols)),
        "feature_cols": prepared.feature_cols,
        "live_feature_issues": live_issues,
        "passed": not issues,
    }
    return payload, issues


def audit_result(result_dir: Path) -> tuple[dict, list[str]]:
    trade_path = result_dir / "event_option_profile_trades.csv"
    fold_path = result_dir / "selected_folds.csv"
    trades = pd.read_csv(trade_path) if trade_path.exists() and trade_path.stat().st_size > 0 else pd.DataFrame()
    folds = pd.read_csv(fold_path, dtype={"month": str})
    issues: list[str] = []
    per_ticker: dict = {}
    for ticker in TICKERS:
        part = trades[trades["ticker"].astype(str).eq(ticker)].copy() if not trades.empty else pd.DataFrame()
        summary = metrics(part, expected_months=MONTHS)
        holds = pd.to_numeric(part.get("exit_minutes", pd.Series(dtype=float)), errors="coerce")
        hold_ok = bool(not part.empty and holds.notna().all() and holds.ge(30).all())
        full_gate = bool(
            int(summary["min_month_trades"]) >= 18
            and float(summary["win_rate"]) >= 0.50
            and float(summary["profit_factor"]) >= 1.30
            and float(summary["positive_month_rate"]) >= 1.0
            and hold_ok
        )
        summary["min_hold_minutes"] = float(holds.min()) if not holds.empty else None
        summary["all_holds_at_least_30m"] = hold_ok
        summary["passes_full_gate"] = full_gate
        summary["selected_folds"] = int(
            folds[folds["ticker"].astype(str).eq(ticker)].get("selected", False).astype(bool).sum()
        )
        per_ticker[ticker] = summary
    if any(str(value).startswith("202606") for value in folds.astype(str).to_numpy().ravel()):
        issues.append("June 2026 found in fold artifacts")
    return {
        "result_dir": str(result_dir),
        "tickers": per_ticker,
        "meets_full_ticker_gate": all(per_ticker[t]["passes_full_gate"] for t in TICKERS),
        "production_live_ready": False,
    }, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the causal pre-IB executable dataset and optional result.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--build-summary", required=True)
    parser.add_argument("--result-dir")
    parser.add_argument("--expected-step-minutes", type=int, default=5)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    build_summary = json.loads(Path(args.build_summary).read_text(encoding="utf-8"))
    dataset, issues = audit_dataset(
        Path(args.data),
        expected_step_minutes=args.expected_step_minutes,
    )
    build_step = int(build_summary.get("args", {}).get("bar_minutes", -1))
    if build_step != args.expected_step_minutes:
        issues.append(
            f"build bar_minutes={build_step} does not match expected_step_minutes="
            f"{args.expected_step_minutes}"
        )
    if bool(build_summary.get("args", {}).get("near_level_only", True)):
        issues.append("build used near_level_only before IB completion")
    payload = {
        "schema_version": 1,
        "audit": "early_causal_executable_no_ib",
        "dataset": dataset,
        "build_near_level_only": build_summary.get("args", {}).get("near_level_only"),
        "build_bar_minutes": build_step,
        "june_2026_sealed": True,
        "production_unchanged": True,
    }
    if args.result_dir:
        result, result_issues = audit_result(Path(args.result_dir))
        payload["result"] = result
        issues.extend(result_issues)
    payload["issues"] = issues
    payload["passed"] = not issues
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    print(json.dumps({"passed": payload["passed"], "issues": issues, "decision": payload.get("result", {})}, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
