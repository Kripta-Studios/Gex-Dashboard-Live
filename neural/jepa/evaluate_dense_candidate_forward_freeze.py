from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.apply_event_monthly_volume_backfill import apply_backfill
from neural.jepa.event_option_component_live import EventOptionComponentRegistry
from neural.jepa.evaluate_xinput_level_filter import month_range
from neural.jepa.walkforward_event_option_gate import metrics


DEFAULT_DATA = Path(
    "research_papers/JEPA/results/"
    "event_option_dataset_spxw_spy_qqq_zero_dte_dense15_2022_2026_v1_physics/event_option_dataset.parquet"
)
DEFAULT_REGISTRY = Path("neural/models/jepa/jepa_production_event_options_dense15_strict_uniform_candidate/component_registry.json")
DEFAULT_POLICY = Path("neural/models/jepa/jepa_production_event_options_dense15_strict_uniform_candidate/event_option_policy.json")
DEFAULT_RAW_THETADATA_COVERAGE = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "thetadata_0dte_raw_coverage_spxw_spy_qqq/raw_coverage.json"
)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def derive_entry_minute(frame: pd.DataFrame) -> pd.Series:
    if "minute" in frame.columns:
        return pd.to_numeric(frame["minute"], errors="coerce").fillna(0).astype(int)
    parsed = pd.to_datetime(frame["time"].astype(str).str[:5], format="%H:%M", errors="coerce")
    return (parsed.dt.hour * 60 + parsed.dt.minute).fillna(0).astype(int)


def last_business_date_for_month(month: str) -> pd.Timestamp:
    start = pd.Timestamp(year=int(month[:4]), month=int(month[4:6]), day=1)
    return pd.bdate_range(start, start + pd.offsets.MonthEnd(0))[-1]


def is_completed_month(month: str, dates: pd.Series) -> bool:
    valid = dates.astype(str).replace("nan", np.nan).dropna()
    if valid.empty:
        return False
    last_seen = pd.to_datetime(valid.max(), format="%Y%m%d", errors="coerce")
    if pd.isna(last_seen):
        return False
    last_business = last_business_date_for_month(month)
    return bool(last_seen.normalize() >= last_business.normalize())


def discover_month_availability(frame: pd.DataFrame, start_month: str, end_month: str | None) -> list[dict[str, Any]]:
    availability: list[dict[str, Any]] = []
    grouped = frame.groupby("month", sort=True)["date"]
    for month, dates in grouped:
        month = str(month)
        if month < start_month:
            continue
        if end_month and month > end_month:
            continue
        valid = dates.astype(str).replace("nan", np.nan).dropna()
        if valid.empty:
            continue
        first_seen = pd.to_datetime(valid.min(), format="%Y%m%d", errors="coerce")
        last_seen = pd.to_datetime(valid.max(), format="%Y%m%d", errors="coerce")
        if pd.isna(first_seen) or pd.isna(last_seen):
            continue
        last_business = last_business_date_for_month(month)
        completed = bool(last_seen.normalize() >= last_business.normalize())
        availability.append(
            {
                "month": month,
                "completed": completed,
                "partial": not completed,
                "first_available_date": first_seen.strftime("%Y%m%d"),
                "latest_available_date": last_seen.strftime("%Y%m%d"),
                "last_business_date": last_business.strftime("%Y%m%d"),
                "unique_trade_dates": int(valid.nunique()),
                "rows": int(len(valid)),
            }
        )
    return availability


def apply_raw_thetadata_coverage(
    availability: list[dict[str, Any]],
    raw_coverage_path: Path | None,
    start_month: str,
    end_month: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if raw_coverage_path is None or not raw_coverage_path.exists():
        return availability, {
            "available": False,
            "path": str(raw_coverage_path) if raw_coverage_path else None,
            "official_forward_evidence": False,
            "issues": [f"missing {raw_coverage_path}"] if raw_coverage_path else ["no raw coverage path supplied"],
        }

    payload = read_json(raw_coverage_path)
    combined = payload.get("combined") if isinstance(payload.get("combined"), dict) else {}
    try:
        schema_version = int(payload.get("schema_version", 0) or 0)
    except (TypeError, ValueError):
        schema_version = 0
    raw_issues: list[str] = []
    if schema_version < 2:
        raw_issues.append("raw coverage schema_version < 2; expected true 0DTE audit with expiration==date")
    if bool(payload.get("official_forward_evidence", False)):
        raw_issues.append("raw coverage is marked official forward evidence")
    raw_months = combined.get("months") if isinstance(combined.get("months"), dict) else {}
    raw_filtered = (
        {
            str(month): row
            for month, row in raw_months.items()
            if str(month) >= str(start_month) and (not end_month or str(month) <= str(end_month)) and isinstance(row, dict)
        }
        if schema_version >= 2
        else {}
    )
    by_month = {str(item["month"]): dict(item) for item in availability}
    for month, item in by_month.items():
        raw = raw_filtered.get(month)
        dataset_completed = bool(item.get("completed"))
        item["dataset_completed"] = dataset_completed
        item["completion_basis"] = "event_dataset"
        if raw is None:
            item["raw_thetadata_available"] = False
            item["raw_thetadata_completed"] = False
            item["completed"] = False
            item["partial"] = True
            item["completion_basis"] = "event_dataset_and_raw_thetadata_missing"
            continue
        raw_completed = bool(raw.get("completed"))
        item["raw_thetadata_available"] = True
        item["raw_thetadata_completed"] = raw_completed
        item["raw_thetadata_latest_common_date"] = raw.get("latest_common_date")
        item["raw_thetadata_last_business_date"] = raw.get("last_business_date")
        item["completion_basis"] = "event_dataset_and_raw_thetadata"
        item["completed"] = bool(dataset_completed and raw_completed)
        item["partial"] = not bool(item["completed"])
    raw_completed_missing = [
        month
        for month, row in raw_filtered.items()
        if bool(row.get("completed")) and month not in by_month
    ]
    summary = {
        "available": True,
        "path": str(raw_coverage_path),
        "official_forward_evidence": bool(payload.get("official_forward_evidence", False)),
        "schema_version": schema_version,
        "true_zero_dte_filter": bool(schema_version >= 2),
        "latest_common_date_all_tickers": combined.get("latest_common_date_all_tickers"),
        "completed_months_at_or_after_start": [
            month for month, row in raw_filtered.items() if bool(row.get("completed"))
        ],
        "partial_months_at_or_after_start": [
            month for month, row in raw_filtered.items() if not bool(row.get("completed"))
        ],
        "completed_months_missing_from_event_dataset": raw_completed_missing,
        "issues": raw_issues,
    }
    return [by_month[str(item["month"])] for item in availability], summary


def discover_completed_months(frame: pd.DataFrame, start_month: str, end_month: str | None) -> list[str]:
    return [item["month"] for item in discover_month_availability(frame, start_month, end_month) if item["completed"]]


def data_date_bounds(frame: pd.DataFrame) -> dict[str, str | None]:
    valid = frame["date"].astype(str).replace("nan", np.nan).dropna()
    if valid.empty:
        return {
            "data_first_available_date": None,
            "data_latest_available_date": None,
            "data_first_available_month": None,
            "data_latest_available_month": None,
        }
    first_date = str(valid.min())
    latest_date = str(valid.max())
    return {
        "data_first_available_date": first_date,
        "data_latest_available_date": latest_date,
        "data_first_available_month": first_date[:6],
        "data_latest_available_month": latest_date[:6],
    }


def prepare_data(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame = frame.copy()
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    if "trade_date" in frame.columns:
        frame["date"] = frame["trade_date"].astype(str)
    elif "date" in frame.columns:
        frame["date"] = frame["date"].astype(str)
    else:
        raise ValueError(f"{path} missing trade_date/date")
    frame["month"] = frame["date"].str[:6]
    if "expiry_mode" in frame.columns:
        frame = frame[frame["expiry_mode"].astype(str).eq("zero_dte")].copy()
    frame["entry_minute"] = derive_entry_minute(frame)
    if "test_month" not in frame.columns:
        frame["test_month"] = frame["month"]
    return frame.reset_index(drop=True)


def realized_returns(frame: pd.DataFrame, delta_bucket: int, clip_return: float) -> tuple[pd.Series, pd.Series]:
    label = f"d{int(delta_bucket):02d}"
    call = pd.to_numeric(frame[f"call_{label}_opt_exit_ret"], errors="coerce")
    put = pd.to_numeric(frame[f"put_{label}_opt_exit_ret"], errors="coerce")
    if float(clip_return) > 0.0:
        call = call.clip(-float(clip_return), float(clip_return))
        put = put.clip(-float(clip_return), float(clip_return))
    return call, put


def score_component(
    registry: EventOptionComponentRegistry,
    component_name: str,
    frame: pd.DataFrame,
    *,
    source_stream: str,
    source_priority: int,
    monthly_role: str,
    strict: bool,
) -> pd.DataFrame:
    component = registry.component(component_name)
    meta = component.metadata
    entry = component.registry_entry
    tickers = [str(t).upper() for t in meta.get("tickers", [])] or [component_name.split(".", 1)[0].upper()]
    work = frame[frame["ticker"].astype(str).str.upper().isin(tickers)].copy()
    if work.empty:
        return work
    scored = registry.score_event_option_gate_component(component_name, work, strict=strict)
    scored = scored[scored["event_gate_pass"].astype(bool)].copy()
    if scored.empty:
        return scored
    delta_bucket = int(entry.get("delta_bucket", meta.get("args", {}).get("delta_bucket", 25)))
    clip_return = float((meta.get("args") or {}).get("clip_return", 2.0))
    call_return, put_return = realized_returns(scored, delta_bucket, clip_return)
    valid = np.isfinite(call_return) & np.isfinite(put_return)
    scored = scored[valid].copy()
    call_return = call_return[valid]
    put_return = put_return[valid]
    scored["call_return"] = call_return.astype(float).values
    scored["put_return"] = put_return.astype(float).values
    scored["realized_return"] = np.where(
        scored["action"].astype(str).str.upper().eq("CALL"),
        scored["call_return"].astype(float),
        scored["put_return"].astype(float),
    )
    scored["source_stream"] = str(source_stream)
    scored["source_priority"] = int(source_priority)
    scored["source_component"] = str(component_name)
    scored["monthly_backfill_role"] = str(monthly_role)
    scored["event_delta_bucket"] = f"d{delta_bucket:02d}"
    scored["event_delta_target"] = float(delta_bucket) / 100.0
    scored["option_snapshot_suffix"] = "0dte"
    scored["policy_ticker"] = scored["ticker"].astype(str).str.upper()
    scored["bot_ticker"] = scored["policy_ticker"].replace({"SPXW": "SPX"})
    scored["_source_order"] = np.arange(len(scored), dtype=np.int64)
    return scored.reset_index(drop=True)


def evaluate_forward(frame: pd.DataFrame, registry: EventOptionComponentRegistry, policy: dict[str, Any], months: list[str], strict: bool) -> pd.DataFrame:
    if not months:
        return pd.DataFrame()
    work = frame[frame["month"].astype(str).isin(set(months))].copy()
    policy_components = policy.get("policy_components", {})
    parts: list[pd.DataFrame] = []
    for ticker in ["SPXW", "SPY", "QQQ"]:
        spec = policy_components.get(ticker, {})
        primary_name = str(spec.get("primary_component", f"{ticker}.strict_d25_win"))
        fallback_name = str(spec.get("fallback_component", f"{ticker}.d50_forcedmax3"))
        monthly_name = str(spec.get("monthly_backfill_policy", f"{ticker}.monthly_backfill18"))
        monthly_policy = registry.monthly_volume_backfill_policy(monthly_name)
        primary = score_component(
            registry,
            primary_name,
            work,
            source_stream=str(monthly_policy.get("primary_name", "win_valthr_strict_d25")),
            source_priority=0,
            monthly_role="primary",
            strict=strict,
        )
        fallback = score_component(
            registry,
            fallback_name,
            work,
            source_stream=str(monthly_policy.get("fallback_name", "forcedmax3_d50")),
            source_priority=1,
            monthly_role="fallback",
            strict=strict,
        )
        args = SimpleNamespace(
            start_month=min(months),
            end_month=max(months),
            primary_name=str(monthly_policy.get("primary_name", "win_valthr_strict_d25")),
            fallback_name=str(monthly_policy.get("fallback_name", "forcedmax3_d50")),
            min_month_trades=int(monthly_policy.get("min_month_trades", 18)),
            auto_partial_month_target=False,
            partial_month_observed_floor=0,
            backfill_only_partial_months=False,
            max_day=int(monthly_policy.get("max_day", 3)),
            cooldown_minutes=int(monthly_policy.get("cooldown_minutes", 30)),
            min_entry_minute=0,
            risk_capital=5000.0,
        )
        selected = apply_backfill(primary, fallback, args)
        if not selected.empty:
            selected["backfill_policy_component"] = monthly_name
            parts.append(selected)
    out = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    if not out.empty:
        out = out.sort_values(["date", "entry_minute", "ticker", "source_stream"], kind="stable").reset_index(drop=True)
    return out


def gate_payload(trades: pd.DataFrame, months: list[str], args: argparse.Namespace) -> dict[str, Any]:
    overall = metrics(trades, months)
    by_ticker = {ticker: metrics(part, months) for ticker, part in trades.groupby("ticker", sort=True)} if not trades.empty else {}
    checks: dict[str, Any] = {}
    for ticker in ["SPXW", "SPY", "QQQ"]:
        row = by_ticker.get(ticker, {})
        checks[ticker] = {
            "win_rate_ok": float(row.get("win_rate", 0.0)) >= float(args.min_win_rate),
            "profit_factor_ok": float(row.get("profit_factor", 0.0)) >= float(args.min_profit_factor),
            "min_month_trades_ok": int(row.get("min_month_trades", 0)) >= int(args.min_month_trades),
            "pnl_ok": float(row.get("pnl_return", 0.0)) > 0.0,
            "metrics": row,
        }
        checks[ticker]["passed"] = bool(all(value for key, value in checks[ticker].items() if key.endswith("_ok")))
    return {
        "passed": bool(checks and all(item["passed"] for item in checks.values())),
        "overall": overall,
        "by_ticker": by_ticker,
        "checks": checks,
    }


def write_summary(output_dir: Path, payload: dict[str, Any]) -> None:
    available = payload.get("available_months_at_or_after_start", [])
    completed = payload.get("completed_months_at_or_after_start", [])
    partial = payload.get("partial_months_at_or_after_start", [])
    raw_coverage = payload.get("raw_thetadata_coverage", {})
    lines = [
        "# Dense Candidate Forward-Freeze Evaluation",
        "",
        f"- Status: {payload['status']}",
        f"- Official forward mode: {payload['official_forward_mode']}",
        f"- Months: {', '.join(payload.get('months', [])) or '(none)'}",
        f"- Available months at/after start: {', '.join(available) or '(none)'}",
        f"- Completed months at/after start: {', '.join(completed) or '(none)'}",
        f"- Partial months at/after start: {', '.join(partial) or '(none)'}",
        f"- Latest available date: {payload.get('latest_available_date') or '(none)'}",
        f"- Dataset latest available date: {payload.get('data_latest_available_date') or '(none)'}",
        f"- Raw ThetaData coverage used: {raw_coverage.get('available', False)}",
        f"- Raw completed months at/after start: {', '.join(raw_coverage.get('completed_months_at_or_after_start', [])) or '(none)'}",
        f"- Raw partial months at/after start: {', '.join(raw_coverage.get('partial_months_at_or_after_start', [])) or '(none)'}",
        f"- Passed gates: {payload.get('gate_result', {}).get('passed', False)}",
        "",
    ]
    if payload["status"] == "pending_no_completed_forward_months":
        lines.append(
            "No completed months at or after the start month were available. "
            "The start month is included automatically once complete; no performance claim is made while it is partial or absent."
        )
    else:
        if payload["status"] == "evaluated_partial_forward_diagnostic":
            lines += [
                "Partial forward months were explicitly included for diagnostics only. "
                "This run is not official forward evidence and must not be used as a production claim.",
                "",
            ]
        lines += [
            "## By Ticker",
            "",
            "| Ticker | Passed | Trades | WR | PF | Min Trades/Month | PnL Return |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for ticker, item in payload.get("gate_result", {}).get("checks", {}).items():
            row = item.get("metrics", {})
            lines.append(
                f"| {ticker} | {item.get('passed', False)} | {int(row.get('trades', 0))} | "
                f"{float(row.get('win_rate', 0.0)):.2%} | {float(row.get('profit_factor', 0.0)):.3f} | "
                f"{int(row.get('min_month_trades', 0))} | {float(row.get('pnl_return', 0.0)):.3f} |"
            )
    (output_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the frozen dense event-option candidate on future completed months.")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-month", default="202607")
    parser.add_argument("--end-month", default="")
    parser.add_argument("--raw-thetadata-coverage", default=str(DEFAULT_RAW_THETADATA_COVERAGE))
    parser.add_argument("--ignore-raw-thetadata-coverage", action="store_true")
    parser.add_argument("--allow-pre-freeze-diagnostic", action="store_true")
    parser.add_argument(
        "--include-partial-months",
        action="store_true",
        help="Include incomplete months for diagnostic cable tests only; never official forward evidence.",
    )
    parser.add_argument("--strict-features", action="store_true")
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = prepare_data(Path(args.data))
    bounds = data_date_bounds(frame)
    policy = read_json(Path(args.policy))
    freeze_month = str(policy.get("research_selection", {}).get("frozen_before_month", "202607"))
    if str(args.start_month) < freeze_month and not bool(args.allow_pre_freeze_diagnostic):
        raise RuntimeError(
            f"--start-month {args.start_month} is before freeze month {freeze_month}; "
            "pass --allow-pre-freeze-diagnostic only for cable tests."
        )
    end_month = str(args.end_month).strip() or None
    availability = discover_month_availability(frame, str(args.start_month), end_month)
    raw_coverage_path = None if bool(args.ignore_raw_thetadata_coverage) else Path(args.raw_thetadata_coverage)
    availability, raw_coverage = apply_raw_thetadata_coverage(
        availability,
        raw_coverage_path,
        str(args.start_month),
        end_month,
    )
    available_months = [item["month"] for item in availability]
    completed_months = [item["month"] for item in availability if item["completed"]]
    partial_months = [item["month"] for item in availability if item["partial"]]
    months = available_months if bool(args.include_partial_months) else completed_months
    selected_partial_months = [month for month in months if month in set(partial_months)]
    diagnostic_partial_forward = bool(selected_partial_months)
    official_forward_mode = (
        str(args.start_month) >= freeze_month
        and not bool(args.allow_pre_freeze_diagnostic)
        and not diagnostic_partial_forward
    )
    registry = EventOptionComponentRegistry.from_path(Path(args.registry), project_root=PROJECT_ROOT)
    status = (
        "pending_no_completed_forward_months"
        if not months
        else "evaluated_partial_forward_diagnostic"
        if diagnostic_partial_forward
        else "evaluated"
    )
    trades = evaluate_forward(frame, registry, policy, months, bool(args.strict_features)) if months else pd.DataFrame()
    if not trades.empty:
        trades.to_csv(output_dir / "forward_freeze_trades.csv", index=False)
    gate_result = gate_payload(trades, months, args) if months else {"passed": False, "overall": {}, "by_ticker": {}, "checks": {}}
    payload = {
        "schema_version": 1,
        "evaluation": "dense_candidate_forward_freeze",
        "status": status,
        "official_forward_mode": bool(official_forward_mode),
        "diagnostic_pre_freeze": bool(args.allow_pre_freeze_diagnostic),
        "diagnostic_partial_forward": bool(diagnostic_partial_forward),
        "freeze_month": freeze_month,
        "start_month": str(args.start_month),
        "end_month": end_month,
        "months": months,
        "selected_partial_months": selected_partial_months,
        "available_months_at_or_after_start": available_months,
        "completed_months_at_or_after_start": completed_months,
        "partial_months_at_or_after_start": partial_months,
        "month_availability": availability,
        "raw_thetadata_coverage": raw_coverage,
        "latest_available_date": max((item["latest_available_date"] for item in availability), default=None),
        "latest_available_month": max(available_months) if available_months else None,
        **bounds,
        "data": str(args.data),
        "registry": str(args.registry),
        "policy": str(args.policy),
        "gate_result": gate_result,
        "note": (
            "No completed forward months were available at or after start_month; the start month is included once complete. No performance claim is made."
            if status == "pending_no_completed_forward_months"
            else "Partial forward months were included by explicit diagnostic flag; this is not official forward evidence."
            if diagnostic_partial_forward
            else "Diagnostic pre-freeze runs must not be cited as forward evidence."
            if args.allow_pre_freeze_diagnostic
            else "Official forward-freeze evaluation."
        ),
    }
    (output_dir / "forward_freeze_evaluation.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    if status == "pending_no_completed_forward_months" or bool(args.allow_pre_freeze_diagnostic) or diagnostic_partial_forward:
        return 0
    return 0 if gate_result.get("passed", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
