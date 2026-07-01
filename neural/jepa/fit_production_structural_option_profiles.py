from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.search_option_structural_profiles import (  # noqa: E402
    build_profiles,
    normalize_candidates,
    score,
)
from neural.jepa.walkforward_structural_option_profiles import (  # noqa: E402
    empty_metrics,
    metrics_from_mask,
    prepare_frame,
    profile_mask,
)


FULL_FEATURES = [
    "level_target_bps",
    "net_delta",
    "vix_spot",
    "actual_iv",
    "actual_theta",
    "entry_spread_pct",
    "premium_to_spot_bps",
    "rsi",
    "net_gamma",
    "wk_net_delta",
    "gamma_0dte_vs_wk",
    "delta_0dte_vs_wk",
    "dist_to_min_gamma",
    "dist_to_max_gamma",
    "dist_to_zero_gamma",
]

TICKER_POLICIES = {
    "SPX": {"features": ["net_delta"], "inner_val_months": 3, "threshold_source": "core"},
    "SPY": {"features": FULL_FEATURES, "inner_val_months": 3, "threshold_source": "core"},
    "QQQ": {"features": FULL_FEATURES, "inner_val_months": 0, "threshold_source": "train"},
}


def split_prior_months(train_months: list[str], inner_val_months: int) -> tuple[list[str], list[str]]:
    val_count = max(0, int(inner_val_months))
    if val_count <= 0 or len(train_months) <= val_count:
        return list(train_months), []
    return list(train_months[:-val_count]), list(train_months[-val_count:])


def profile_name(profile) -> str:
    time_part = "alltime" if float(profile.max_minutes_to_close) >= 9999 else f"mtc_le_{float(profile.max_minutes_to_close):.0f}"
    if profile.feature == "none":
        return f"{profile.ticker}_d{float(profile.delta_target):.2f}_{time_part}_nofilter"
    threshold = f"{float(profile.threshold):.5g}".replace("-", "m").replace(".", "p")
    return f"{profile.ticker}_d{float(profile.delta_target):.2f}_{time_part}_{profile.feature}_{profile.op}_{threshold}"


def deploy_month_default() -> str:
    return datetime.now().strftime("%Y%m")


def write_summary(out_dir: Path, payload: dict) -> None:
    lines = [
        "# Production Structural Option Profiles",
        "",
        "These profiles are selected only from candidate-label months before `deploy_month` and, when set, at or before `max_train_month`.",
        "",
        f"- Policy: `{payload['policy']}`",
        f"- Deploy month: `{payload['generated_from']['deploy_month']}`",
        f"- Max train month: `{payload['generated_from'].get('max_train_month') or 'deploy_month-1'}`",
        f"- Risk capital: `${float(payload['risk_capital_dollars']):,.0f}`",
        "",
        "## Profiles",
        "",
        "| Ticker | Profile | Delta | Max MTC | Feature | Op | Threshold | Train PF | Core PF | Inner Val PF |",
        "| --- | --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for ticker, profile in payload["profiles"].items():
        selection = profile.get("selection", {})
        inner_val_pf = selection.get("inner_val_profit_factor")
        inner_val_text = "n/a" if inner_val_pf is None else f"{float(inner_val_pf):.3f}"
        lines.append(
            f"| {ticker} | {profile['name']} | {float(profile['delta_target']):.2f} | "
            f"{float(profile['max_minutes_to_close']):.0f} | {profile['feature']} | {profile['op']} | "
            f"{float(profile['threshold']):.5g} | {float(selection.get('train_profit_factor', float('nan'))):.3f} | "
            f"{float(selection.get('core_profit_factor', float('nan'))):.3f} | {inner_val_text} |"
        )
    lines += [
        "",
        "## JSON",
        "",
        "```json",
        json.dumps(payload, indent=2, allow_nan=True),
        "```",
        "",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def fit_ticker(candidates: pd.DataFrame, ticker: str, deploy_month: str, args: argparse.Namespace) -> tuple[dict, pd.DataFrame]:
    policy = TICKER_POLICIES[ticker]
    max_train_month = str(args.max_train_month).strip()
    excluded_train_months = {str(month)[:6] for month in args.exclude_train_months}
    train_months = sorted(
        m for m in candidates["month"].astype(str).unique().tolist()
        if str(args.train_start_month) <= m < str(deploy_month)
        and (not max_train_month or m <= max_train_month)
        and m not in excluded_train_months
    )
    if len(train_months) < int(args.min_train_months):
        raise RuntimeError(f"{ticker}: only {len(train_months)} train months before {deploy_month}")

    core_months, val_months = split_prior_months(train_months, int(policy["inner_val_months"]))
    tdf = candidates[candidates["ticker"].eq(ticker)].copy()
    train = tdf[tdf["month"].isin(train_months)].copy()
    core = tdf[tdf["month"].isin(core_months)].copy()
    val = tdf[tdf["month"].isin(val_months)].copy()
    if train.empty or core.empty:
        raise RuntimeError(f"{ticker}: empty train/core frame")

    policy_args = SimpleNamespace(
        delta_targets=args.delta_targets,
        max_minutes_to_close=args.max_minutes_to_close,
        features=list(policy["features"]),
        quantiles=args.quantiles,
        min_month_trades=args.min_month_trades,
        min_train_pf=args.min_train_pf,
        min_long_rate=args.min_long_rate,
        max_long_rate=args.max_long_rate,
    )
    profile_source = core if val_months and policy["threshold_source"] == "core" else train
    profiles = build_profiles(profile_source, ticker, policy_args)
    train_prepared = prepare_frame(train, policy_args)
    core_prepared = prepare_frame(core, policy_args)
    val_prepared = prepare_frame(val, policy_args)

    rows: list[dict] = []
    for profile in profiles:
        train_metrics = metrics_from_mask(train_prepared, profile_mask(train_prepared, profile), train_months)
        train_score = score(train_metrics, args.min_month_trades, args.min_train_pf, args.min_long_rate, args.max_long_rate)
        core_metrics = metrics_from_mask(core_prepared, profile_mask(core_prepared, profile), core_months)
        core_score = score(core_metrics, args.min_month_trades, args.min_train_pf, args.min_long_rate, args.max_long_rate)
        if val_months:
            val_metrics = metrics_from_mask(val_prepared, profile_mask(val_prepared, profile), val_months)
            val_score = score(val_metrics, args.min_month_trades, args.min_train_pf, args.min_long_rate, args.max_long_rate)
            profile_score = min(core_score, val_score) + float(args.train_score_weight) * train_score
        else:
            val_metrics = empty_metrics()
            profile_score = train_score
        rows.append({
            **asdict(profile),
            "name": profile_name(profile),
            "score": float(profile_score),
            **{f"core_{k}": v for k, v in core_metrics.items()},
            **{f"inner_val_{k}": v for k, v in val_metrics.items()},
            **{f"train_{k}": v for k, v in train_metrics.items()},
        })

    ranking = pd.DataFrame(rows).sort_values(["score", "train_profit_factor", "train_pnl_dollars"], ascending=False)
    if ranking.empty:
        raise RuntimeError(f"{ticker}: no profile candidates")
    best = ranking.iloc[0].to_dict()
    if float(best["score"]) <= -1e17:
        raise RuntimeError(f"{ticker}: no deployable profile passed prior constraints")
    profile = {
        "ticker": ticker,
        "name": str(best["name"]),
        "delta_target": float(best["delta_target"]),
        "max_minutes_to_close": float(best["max_minutes_to_close"]),
        "feature": str(best["feature"]),
        "op": str(best["op"]),
        "threshold": float(best["threshold"]) if pd.notna(best["threshold"]) else 0.0,
        "selection": {
            "train_months": train_months,
            "excluded_train_months": sorted(excluded_train_months),
            "core_months": core_months,
            "inner_val_months": val_months,
            "threshold_source": policy["threshold_source"],
            "features": list(policy["features"]),
            "score": float(best["score"]),
            "train_profit_factor": float(best["train_profit_factor"]),
            "core_profit_factor": float(best["core_profit_factor"]),
            "inner_val_profit_factor": float(best["inner_val_profit_factor"]) if pd.notna(best["inner_val_profit_factor"]) else None,
        },
    }
    return profile, ranking


def main() -> int:
    parser = argparse.ArgumentParser(description="Fit production structural option profiles from prior candidate labels.")
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--train-start-month", default="202507")
    parser.add_argument("--deploy-month", default=deploy_month_default())
    parser.add_argument(
        "--max-train-month",
        default="",
        help="Optional YYYYMM cap for candidate-label training/validation months. Use for incomplete pre-deploy months.",
    )
    parser.add_argument(
        "--exclude-train-months",
        nargs="*",
        default=[],
        help="YYYYMM months to exclude from production train/validation rows, for raw-partial months before deploy.",
    )
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--min-train-months", type=int, default=6)
    parser.add_argument("--delta-targets", nargs="+", type=float, default=[0.40, 0.50, 0.60, 0.70])
    parser.add_argument("--max-minutes-to-close", nargs="+", type=float, default=[60, 90, 120, 140, 180, 9999])
    parser.add_argument("--quantiles", nargs="+", type=float, default=[0.15, 0.25, 0.35, 0.50, 0.65, 0.75, 0.85])
    parser.add_argument("--min-month-trades", type=int, default=15)
    parser.add_argument("--min-train-pf", type=float, default=1.05)
    parser.add_argument("--train-score-weight", type=float, default=0.15)
    parser.add_argument("--min-long-rate", type=float, default=0.20)
    parser.add_argument("--max-long-rate", type=float, default=0.80)
    args = parser.parse_args()
    args.max_train_month = str(args.max_train_month).strip()
    if args.max_train_month and args.max_train_month >= str(args.deploy_month):
        raise ValueError("--max-train-month must be earlier than --deploy-month")

    tickers = [t.upper() for t in args.tickers]
    candidates = normalize_candidates(Path(args.candidate_labels), tickers)
    profiles: dict[str, dict] = {}
    rankings: list[pd.DataFrame] = []
    for ticker in tickers:
        profile, ranking = fit_ticker(candidates, ticker, str(args.deploy_month), args)
        profiles[ticker] = profile
        ranking["ticker"] = ticker
        rankings.append(ranking)
        print(f"[FIT_STRUCT_PROD] {ticker} deploy={args.deploy_month} profile={profile['name']}")

    payload = {
        "version": 1,
        "policy": "level_stability_ensemble_nested_structural_profiles_risk5000",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "generated_from": {
            "candidate_labels": str(Path(args.candidate_labels)),
            "deploy_month": str(args.deploy_month),
            "max_train_month": str(args.max_train_month).strip(),
            "excluded_train_months": [str(month)[:6] for month in args.exclude_train_months],
            "selection_rule": (
                "Each deploy profile is selected using only months before deploy_month "
                "and at or before max_train_month when provided, excluding raw-partial months."
            ),
        },
        "risk_capital_dollars": float(args.risk_capital),
        "profiles": profiles,
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    if str(args.output_dir).strip():
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        pd.concat(rankings, ignore_index=True).to_csv(out_dir / "production_structural_profile_candidates.csv", index=False)
        (out_dir / "structural_option_profiles.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
        write_summary(out_dir, payload)
    print(output_json.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
