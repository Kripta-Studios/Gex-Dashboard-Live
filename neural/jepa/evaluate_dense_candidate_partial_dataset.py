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
from neural.jepa.walkforward_event_option_gate import metrics
from neural.jepa.evaluate_xinput_level_filter import month_range


DEFAULT_REGISTRY = Path(
    "neural/models/jepa/jepa_production_event_options_dense15_strict_uniform_candidate/component_registry.json"
)


def load_frame(paths: list[str], months: set[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise FileNotFoundError(path)
        frame = pd.read_parquet(path)
        if "trade_date" not in frame.columns:
            raise ValueError(f"{path} missing trade_date")
        frame["date"] = frame["trade_date"].astype(str)
        frame["month"] = frame["date"].str.slice(0, 6)
        frame = frame[frame["month"].isin(months)].copy()
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    keys = [col for col in ["ticker", "date", "time", "expiry_mode"] if col in out.columns]
    if keys:
        out = out.drop_duplicates(keys, keep="last").reset_index(drop=True)
    return out


def policy_names(registry: EventOptionComponentRegistry) -> list[str]:
    expected = ["SPXW.monthly_backfill18", "SPY.monthly_backfill18", "QQQ.monthly_backfill18"]
    return [name for name in expected if name in registry.components]


def realized_returns(scored: pd.DataFrame, delta_bucket: int) -> pd.Series:
    bucket = f"d{int(delta_bucket):02d}"
    call_col = f"call_{bucket}_opt_exit_ret"
    put_col = f"put_{bucket}_opt_exit_ret"
    if call_col not in scored.columns or put_col not in scored.columns:
        raise ValueError(f"Missing realized-return columns for {bucket}: {call_col}/{put_col}")
    call_ret = pd.to_numeric(scored[call_col], errors="coerce")
    put_ret = pd.to_numeric(scored[put_col], errors="coerce")
    is_call = scored["action"].astype(str).str.upper().eq("CALL")
    return pd.Series(np.where(is_call, call_ret, put_ret), index=scored.index, dtype=float)


def score_component(
    registry: EventOptionComponentRegistry,
    data: pd.DataFrame,
    *,
    policy: dict[str, Any],
    role: str,
    strict: bool,
    source_order_start: int,
) -> pd.DataFrame:
    ticker = str(policy["ticker"]).upper()
    if role == "primary":
        component = str(policy["primary_component"])
        source = str(policy["primary_name"])
        delta_bucket = int(policy.get("primary_delta_bucket", 25))
        priority = 0
    else:
        component = str(policy["fallback_component"])
        source = str(policy["fallback_name"])
        delta_bucket = int(policy.get("fallback_delta_bucket", 50))
        priority = 1

    subset = data[data["ticker"].astype(str).str.upper().eq(ticker)].copy()
    if subset.empty:
        return pd.DataFrame()
    scored = registry.score_gate_source(
        component,
        subset,
        source_variant=source,
        source_priority=priority,
        strict=strict,
        only_pass=True,
    )
    if scored.empty:
        return scored
    payload = registry.component(component).model_payload()
    metadata = payload.get("metadata", registry.component(component).metadata)
    deploy_config = metadata.get("deploy_config") if isinstance(metadata.get("deploy_config"), dict) else {}
    component_max_day = int(deploy_config.get("max_trades_per_day", 999))
    scored = registry.materialize_max_day_cooldown(
        scored,
        max_day=component_max_day,
        cooldown_minutes=int(policy.get("cooldown_minutes", 30)),
    )
    if scored.empty:
        return scored
    scored = scored.copy()
    scored["ticker"] = scored["ticker"].astype(str).str.upper()
    scored["date"] = scored["date"].astype(str)
    scored["month"] = scored["date"].str.slice(0, 6)
    scored["test_month"] = scored["month"]
    scored["time"] = scored["time"].astype(str)
    scored["entry_minute"] = pd.to_numeric(scored["minute"], errors="coerce").fillna(0).astype(int)
    scored["action"] = scored["action"].astype(str).str.upper()
    scored["realized_return"] = realized_returns(scored, delta_bucket)
    scored = scored[scored["realized_return"].notna()].copy()
    scored["source_stream"] = source
    scored["monthly_backfill_role"] = role
    scored["backfill_policy_component"] = str(policy.get("policy", ""))
    scored["policy_ticker"] = ticker
    scored["bot_ticker"] = "SPX" if ticker == "SPXW" else ticker
    scored["event_delta_bucket"] = f"d{delta_bucket:02d}"
    scored["event_delta_target"] = float(delta_bucket) / 100.0
    scored["policy_max_day"] = int(policy.get("max_day", 3))
    scored["policy_cooldown_minutes"] = int(policy.get("cooldown_minutes", 30))
    scored["_source_order"] = np.arange(source_order_start, source_order_start + len(scored), dtype=np.int64)
    return scored


def summarize(output_dir: Path, trades: pd.DataFrame, primary: pd.DataFrame, fallback: pd.DataFrame, args: argparse.Namespace) -> None:
    months = month_range(str(args.start_month), str(args.end_month))
    payload = {
        "diagnostic": "dense_candidate_partial_dataset",
        "official_forward_evidence": False,
        "reason_not_official": "Partial month diagnostic; month is not complete.",
        "months": months,
        "data": args.data,
        "registry": str(args.registry),
        "primary_candidate_rows": int(len(primary)),
        "fallback_candidate_rows": int(len(fallback)),
        "selected_rows": int(len(trades)),
        "overall": metrics(trades, months),
        "by_ticker": {
            ticker: metrics(part, months)
            for ticker, part in trades.groupby("ticker", sort=True)
        }
        if not trades.empty
        else {},
        "by_source": {
            source: metrics(part, months)
            for source, part in trades.groupby("source_stream", sort=True)
        }
        if not trades.empty
        else {},
        "args": vars(args),
    }
    (output_dir / "partial_evaluation.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Dense Candidate Partial Dataset Evaluation",
        "",
        "Diagnostic only. This applies the frozen dense15 candidate deploy components to an incomplete month and must not be cited as official forward evidence.",
        "",
        f"- Official forward evidence: `{payload['official_forward_evidence']}`",
        f"- Months: `{','.join(months)}`",
        f"- Primary candidate rows: `{len(primary)}`",
        f"- Fallback candidate rows: `{len(fallback)}`",
        f"- Selected rows: `{len(trades)}`",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(payload["overall"], indent=2, allow_nan=True),
        "```",
        "",
        "## By Ticker",
        "",
        "```json",
        json.dumps(payload["by_ticker"], indent=2, allow_nan=True),
        "```",
        "",
        "## By Source",
        "",
        "```json",
        json.dumps(payload["by_source"], indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the frozen dense15 candidate to an incomplete diagnostic dataset.")
    parser.add_argument("--data", nargs="+", required=True)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-month", default="202606")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--strict", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    months = set(month_range(str(args.start_month), str(args.end_month)))
    data = load_frame([str(item) for item in args.data], months)
    if data.empty:
        raise RuntimeError("No rows after month filtering")

    registry = EventOptionComponentRegistry.from_path(Path(args.registry))
    primary_parts: list[pd.DataFrame] = []
    fallback_parts: list[pd.DataFrame] = []
    order = 0
    policies = []
    for name in policy_names(registry):
        policy = registry.monthly_volume_backfill_policy(name)
        policies.append(policy)
        primary = score_component(registry, data, policy=policy, role="primary", strict=bool(args.strict), source_order_start=order)
        order += len(primary)
        fallback = score_component(registry, data, policy=policy, role="fallback", strict=bool(args.strict), source_order_start=order)
        order += len(fallback)
        primary_parts.append(primary)
        fallback_parts.append(fallback)

    primary = pd.concat([p for p in primary_parts if not p.empty], ignore_index=True, sort=False) if primary_parts else pd.DataFrame()
    fallback = pd.concat([p for p in fallback_parts if not p.empty], ignore_index=True, sort=False) if fallback_parts else pd.DataFrame()

    backfill_args = SimpleNamespace(
        start_month=str(args.start_month),
        end_month=str(args.end_month),
        min_month_trades=int(args.min_month_trades),
        auto_partial_month_target=False,
        partial_month_observed_floor=0,
        backfill_only_partial_months=False,
        max_day=3,
        cooldown_minutes=30,
        primary_name="win_valthr_strict_d25",
        fallback_name="forcedmax3_d50",
        risk_capital=float(args.risk_capital),
    )
    selected = apply_backfill(primary, fallback, backfill_args)
    if not selected.empty:
        selected["pnl"] = pd.to_numeric(selected["realized_return"], errors="coerce").fillna(0.0) * float(args.risk_capital)
    primary.to_csv(output_dir / "primary_candidates.csv", index=False)
    fallback.to_csv(output_dir / "fallback_candidates.csv", index=False)
    selected.to_csv(output_dir / "combined_trades.csv", index=False)
    (output_dir / "policies.json").write_text(json.dumps(policies, indent=2, allow_nan=True), encoding="utf-8")
    summarize(output_dir, selected, primary, fallback, args)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
