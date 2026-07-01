from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULT_DIR = (
    PROJECT_ROOT
    / "research_papers"
    / "JEPA"
    / "results"
    / "event_option_candidate_spxw_outer_s1_qqq_outer_call50_spy_srchist_relmomtopk2_2026janmay_risk5000"
)
DEFAULT_PARTIAL_RESULT_DIR = (
    PROJECT_ROOT
    / "research_papers"
    / "JEPA"
    / "results"
    / "event_option_candidate_spxw_outer_s1_qqq_outer_call50_spy_srchist_relmomtopk2_2026janjun_partial_risk5000"
)
DEFAULT_FREEZE_DIR = (
    PROJECT_ROOT
    / "research_papers"
    / "JEPA"
    / "results"
    / "event_option_forward_freeze_spxw_outer_s1_qqq_outer_call50_spy_srchist_relmomtopk2_202607"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "neural" / "models" / "jepa" / "jepa_production_event_options"
DEFAULT_RAW_THETADATA_COVERAGE = (
    PROJECT_ROOT
    / "research_papers"
    / "JEPA"
    / "results"
    / "_diagnostics"
    / "thetadata_0dte_raw_coverage_spxw_spy_qqq"
    / "raw_coverage.json"
)


def month_range(start_month: str, end_month: str) -> list[str]:
    start_y, start_m = int(str(start_month)[:4]), int(str(start_month)[4:6])
    end_y, end_m = int(str(end_month)[:4]), int(str(end_month)[4:6])
    out: list[str] = []
    y, m = start_y, start_m
    while (y, m) <= (end_y, end_m):
        out.append(f"{y:04d}{m:02d}")
        m += 1
        if m > 12:
            y += 1
            m = 1
    return out


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def summarize_entries(trades_path: Path) -> dict[str, Any]:
    if not trades_path.exists():
        raise FileNotFoundError(trades_path)
    cols = [
        "ticker",
        "test_month",
        "action",
        "entry_minute",
        "minute",
        "time",
        "deploy_config",
        "source_stream",
        "source_file",
        "stream_selector_source",
        "selector_source",
        "source_variant",
        "selected_profile",
        "delta_target",
        "actual_delta_abs",
        "action_abs_delta",
        "realized_return",
    ]
    trades = pd.read_csv(trades_path, usecols=lambda c: c in cols)
    if trades.empty:
        raise RuntimeError(f"No trades in {trades_path}")
    minute = pd.to_numeric(trades.get("entry_minute"), errors="coerce")
    if "minute" in trades.columns:
        minute = minute.fillna(pd.to_numeric(trades["minute"], errors="coerce"))
    trades["_entry_minute_resolved"] = minute

    out: dict[str, Any] = {}
    for ticker, part in trades.groupby("ticker", sort=True):
        month_counts = {
            str(month): int(count)
            for month, count in part.groupby(part["test_month"].astype(str)).size().sort_index().items()
        }
        ticker_payload: dict[str, Any] = {
            "months": month_counts,
            "entry_minute_min": int(part["_entry_minute_resolved"].min()),
            "entry_minute_max": int(part["_entry_minute_resolved"].max()),
            "time_min": str(part["time"].min()) if "time" in part.columns else "",
            "time_max": str(part["time"].max()) if "time" in part.columns else "",
            "actions": part["action"].astype(str).value_counts().sort_index().astype(int).to_dict()
            if "action" in part.columns
            else {},
        }
        for col in [
            "source_stream",
            "stream_selector_source",
            "selector_source",
            "source_variant",
            "selected_profile",
            "delta_target",
            "action_abs_delta",
            "deploy_config",
        ]:
            if col in part.columns:
                values = part[col].dropna()
                if not values.empty:
                    ticker_payload[col] = values.astype(str).value_counts().head(20).astype(int).to_dict()
        out[str(ticker)] = ticker_payload
    return out


def assert_completed_month_gates(metrics: dict[str, Any], args: argparse.Namespace) -> None:
    by_ticker = metrics.get("by_ticker")
    if not isinstance(by_ticker, dict):
        raise ValueError("metrics.json missing by_ticker")
    missing = [ticker for ticker in args.required_tickers if ticker not in by_ticker]
    if missing:
        raise ValueError(f"metrics.json missing required tickers: {missing}")
    failures: list[str] = []
    for ticker in args.required_tickers:
        row = by_ticker[ticker]
        wr = float(row.get("win_rate", 0.0))
        pf = float(row.get("profit_factor", 0.0))
        min_month = int(row.get("min_month_trades", 0))
        pos_rate = float(row.get("positive_month_rate", 0.0))
        pnl = float(row.get("pnl_return", 0.0))
        if wr < float(args.min_win_rate):
            failures.append(f"{ticker}: win_rate {wr:.4f} < {args.min_win_rate}")
        if pf < float(args.min_profit_factor):
            failures.append(f"{ticker}: profit_factor {pf:.4f} < {args.min_profit_factor}")
        if min_month < int(args.min_month_trades):
            failures.append(f"{ticker}: min_month_trades {min_month} < {args.min_month_trades}")
        if pos_rate < 1.0:
            failures.append(f"{ticker}: positive_month_rate {pos_rate:.4f} < 1.0")
        if pnl <= 0.0:
            failures.append(f"{ticker}: pnl_return {pnl:.4f} <= 0")
    if failures:
        raise RuntimeError("Completed-month gates failed:\n- " + "\n- ".join(failures))


def assert_raw_completed_months(months: list[str], raw_coverage_path: Path, tickers: list[str]) -> dict[str, Any]:
    raw = read_json(raw_coverage_path)
    issues: list[str] = []
    schema_version = int(raw.get("schema_version", 0) or 0)
    if schema_version < 2:
        issues.append("raw coverage schema_version < 2; expected true 0DTE coverage audit")
    raw_tickers = {str(ticker).upper() for ticker in raw.get("tickers", [])}
    missing_tickers = [ticker for ticker in tickers if str(ticker).upper() not in raw_tickers]
    if missing_tickers:
        issues.append(f"raw coverage missing required tickers: {missing_tickers}")
    combined = raw.get("combined") if isinstance(raw.get("combined"), dict) else raw
    completed = {str(month) for month in combined.get("completed_months", [])}
    missing_months = [month for month in months if str(month) not in completed]
    if missing_months:
        issues.append(
            "completed_month_validation includes months not completed in raw all-ticker 0DTE coverage: "
            + f"{missing_months}; raw_latest_common_date={combined.get('latest_common_date_all_tickers')}; "
            + f"raw_partial_months={combined.get('partial_months', [])}"
        )
    for ticker in tickers:
        ticker_options = (raw.get("options") or {}).get(str(ticker).upper(), {})
        if not isinstance(ticker_options, dict):
            issues.append(f"{ticker}: raw coverage options section missing")
            continue
        if "zero_dte_option_files" not in ticker_options or "non_zero_dte_option_files" not in ticker_options:
            issues.append(f"{ticker}: raw coverage lacks 0DTE/non-0DTE file counters")
    if issues:
        raise RuntimeError("Raw ThetaData completed-month guard failed:\n- " + "\n- ".join(issues))
    return {
        "path": str(raw_coverage_path),
        "schema_version": schema_version,
        "true_zero_dte_filter": True,
        "latest_common_date_all_tickers": combined.get("latest_common_date_all_tickers"),
        "completed_months": sorted(completed),
        "partial_months": [str(month) for month in combined.get("partial_months", [])],
    }


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the frozen event-option research candidate as a production policy artifact.")
    parser.add_argument("--result-dir", default=str(DEFAULT_RESULT_DIR))
    parser.add_argument("--partial-result-dir", default=str(DEFAULT_PARTIAL_RESULT_DIR))
    parser.add_argument("--freeze-dir", default=str(DEFAULT_FREEZE_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--deploy-month", default="202607")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--required-tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--policy-name", default="", help="Optional exact policy id. Defaults to the historical script policy name.")
    parser.add_argument("--completed-start-month", default="202601")
    parser.add_argument("--completed-end-month", default="202605")
    parser.add_argument("--raw-thetadata-coverage", default=str(DEFAULT_RAW_THETADATA_COVERAGE))
    parser.add_argument(
        "--ignore-raw-thetadata-coverage",
        action="store_true",
        help="Legacy escape hatch. Normal exports must prove completed months are completed in true 0DTE raw coverage.",
    )
    parser.add_argument("--partial-start-month", default="202601")
    parser.add_argument("--partial-end-month", default="202606")
    parser.add_argument("--partial-note", action="append", default=[])
    parser.add_argument(
        "--runtime-replay-summary",
        default="",
        help="Optional runtime replay summary JSON to embed as live-equivalence evidence.",
    )
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    partial_result_dir = Path(args.partial_result_dir)
    freeze_dir = Path(args.freeze_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics = read_json(result_dir / "metrics.json")
    partial_metrics = read_json(partial_result_dir / "metrics.json")
    freeze_manifest = read_json(freeze_dir / "research_selection_manifest.json")
    assert_completed_month_gates(metrics, args)
    completed_months = month_range(str(args.completed_start_month), str(args.completed_end_month))
    partial_months = month_range(str(args.partial_start_month), str(args.partial_end_month))
    raw_coverage_summary: dict[str, Any] | None = None
    if not bool(args.ignore_raw_thetadata_coverage):
        raw_coverage_summary = assert_raw_completed_months(
            completed_months,
            Path(args.raw_thetadata_coverage),
            [str(ticker).upper() for ticker in args.required_tickers],
        )

    policy = {
        "schema_version": 1,
        "policy": str(args.policy_name).strip() or f"event_option_srchist_relmomtopk2_prod_{args.deploy_month}",
        "deploy_month": str(args.deploy_month),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "forward_only_frozen_research_candidate",
        "risk_capital_dollars": float(args.risk_capital),
        "live_contract": {
            "tickers": ["SPX", "SPY", "QQQ"],
            "options_symbols": {"SPX": "SPXW", "SPY": "SPY", "QQQ": "QQQ"},
            "entry_sample_minutes": 5,
            "entry_minute_min": 630,
            "entry_minute_max": 945,
            "entry_time_min_et": "10:30",
            "entry_time_max_et": "15:45",
            "cooldown_minutes": 30,
            "hard_stop_pct": -0.60,
            "trailing_stop_activate_pct": 0.50,
            "trailing_stop_giveback_pct": 0.25,
            "emergency_take_profit_pct": 10.0,
            "candidate_dataset_builder": "neural/jepa/build_event_option_dataset.py",
            "required_live_artifact": "neural/models/jepa/jepa_production_event_options/event_option_policy.json",
        },
        "validated_label_exit_contract": {
            "source": "neural/jepa/build_event_option_dataset.py",
            "horizon_minutes": 180,
            "option_take_profit_pct": 0.5,
            "option_stop_loss_pct": 0.3,
            "live_equivalence_note": (
                "Walk-forward metrics are based on the +50%/-30%/180m option path label contract. "
                "Live execution must use the same exit contract unless separately revalidated."
            ),
        },
        "completed_month_validation": {
            "result_dir": str(result_dir),
            "months": completed_months,
            "raw_thetadata_coverage": raw_coverage_summary,
            "gates": {
                "min_win_rate": float(args.min_win_rate),
                "min_profit_factor": float(args.min_profit_factor),
                "min_month_trades": int(args.min_month_trades),
                "require_positive_months": True,
                "require_curve_health": True,
            },
            "overall": metrics.get("overall", {}),
            "by_ticker": metrics.get("by_ticker", {}),
            "integrity": metrics.get("integrity", {}),
            "entry_summary": summarize_entries(result_dir / "combined_trades.csv"),
        },
        "partial_month_diagnostic": {
            "result_dir": str(partial_result_dir),
            "months": partial_months,
            "overall": partial_metrics.get("overall", {}),
            "by_ticker": partial_metrics.get("by_ticker", {}),
            "integrity": partial_metrics.get("integrity", {}),
            "entry_summary": summarize_entries(partial_result_dir / "combined_trades.csv"),
            "known_noncanonical": list(args.partial_note),
        },
        "freeze_manifest": freeze_manifest,
        "research_caveat": (
            "This policy is a frozen forward-only event-option research candidate. "
            "It passed completed-month causal walk-forward gates, but the source family "
            "was discovered during research and must be judged live from deploy_month onward."
        ),
    }
    if str(args.runtime_replay_summary).strip():
        replay_path = Path(args.runtime_replay_summary)
        replay_summary = read_json(replay_path)
        policy["live_contract"]["runtime_policy_replay"] = str(replay_path)
        policy["live_equivalence"] = {
            "runtime_policy_replay": {
                "summary_path": str(replay_path),
                "stateful_replay_passed": bool(replay_summary.get("stateful_replay_passed", False)),
                "strict_live_ready_passed": bool(replay_summary.get("strict_live_ready_passed", False)),
                "comparisons": replay_summary.get("comparisons", []),
                "input_hashes": replay_summary.get("input_hashes", {}),
                "note": replay_summary.get("note", ""),
            }
        }
    (output_dir / "event_option_policy.json").write_text(json.dumps(policy, indent=2, allow_nan=True), encoding="utf-8")
    copy_if_exists(freeze_dir / "research_selection_manifest.json", output_dir / "research_selection_manifest.json")
    copy_if_exists(result_dir / "metrics.json", output_dir / "completed_month_metrics.json")
    copy_if_exists(partial_result_dir / "metrics.json", output_dir / "partial_month_metrics.json")
    copy_if_exists(result_dir / "curve_health" / "curve_health.json", output_dir / "completed_month_curve_health.json")
    copy_if_exists(result_dir / "curve_health" / "ticker_cumulative_net_pnl.png", output_dir / "ticker_cumulative_net_pnl.png")
    if str(args.runtime_replay_summary).strip():
        copy_if_exists(Path(args.runtime_replay_summary), output_dir / "runtime_policy_replay_summary.json")

    lines = [
        "# Event-Option Production Policy",
        "",
        f"- Policy: `{policy['policy']}`",
        f"- Deploy month: `{policy['deploy_month']}`",
        f"- Risk capital: `${float(args.risk_capital):,.0f}`",
        "- Status: forward-only frozen research candidate",
    ]
    replay = policy.get("live_equivalence", {}).get("runtime_policy_replay")
    if isinstance(replay, dict):
        lines.append(f"- Runtime replay passed: {bool(replay.get('stateful_replay_passed', False))}")
        lines.append(f"- Strict live-ready passed: {bool(replay.get('strict_live_ready_passed', False))}")
    lines.extend(
        [
            "",
            "## Completed-Month Validation",
            "",
        ]
    )
    for ticker, row in policy["completed_month_validation"]["by_ticker"].items():
        lines.append(
            f"- {ticker}: trades={row.get('trades')}, WR={float(row.get('win_rate', 0.0)):.2%}, "
            f"PF={float(row.get('profit_factor', 0.0)):.3f}, "
            f"PnL=${float(row.get('pnl_return', 0.0)) * float(args.risk_capital):,.0f}, "
            f"min_month_trades={row.get('min_month_trades')}, "
            f"positive_month_rate={row.get('positive_month_rate')}"
        )
    lines.extend(
        [
            "",
            "## Caveat",
            "",
            policy["research_caveat"],
            "",
            "The event-option policy uses entries through 15:45 ET. Do not run it with the older 14:30 cutoff without a separate walk-forward validation.",
            "",
        ]
    )
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
