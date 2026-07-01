from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
JEPA_DIR = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(JEPA_DIR) not in sys.path:
    sys.path.insert(0, str(JEPA_DIR))

from neural.jepa.level_stability_live import REQUIRED_LEVEL_COLUMNS, config_to_payload  # noqa: E402
from walkforward_level_stability_ensemble import (  # noqa: E402
    build_ensemble_grid,
    build_fold_caches,
    side_rankings,
)
from walkforward_level_side_config_signal import config_grid, load_frame, score_metrics  # noqa: E402
from evaluate_xinput_level_filter import metrics  # noqa: E402


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "neural" / "models" / "jepa" / "jepa_production_level_stability"


def current_deploy_month() -> str:
    now = datetime.now()
    return f"{now.year:04d}{now.month:02d}"


def selected_configs(ranking: list[dict], count: int) -> list:
    valid = [row for row in ranking if float(row.get("score", -1e18)) > -1e17]
    source = valid if valid else ranking
    return [row["config"] for row in source[: max(1, int(count))]]


def fit_ticker(frame: pd.DataFrame, ticker: str, args: argparse.Namespace) -> dict:
    ticker = str(ticker).upper()
    grid = config_grid(args)
    ensemble_grid = build_ensemble_grid(args)
    tdf = frame[frame["ticker"].astype(str).str.upper().eq(ticker)].sort_values(["date", "minute"]).copy()
    prior_mask = tdf["month"].astype(str) < str(args.deploy_month)
    if str(args.max_train_month).strip():
        prior_mask &= tdf["month"].astype(str) <= str(args.max_train_month).strip()
    excluded_train_months = {str(month)[:6] for month in args.exclude_train_months}
    if excluded_train_months:
        prior_mask &= ~tdf["month"].astype(str).isin(excluded_train_months)
    prior = tdf[prior_mask].copy()
    if prior.empty:
        raise ValueError(
            f"{ticker}: no prior rows before deploy_month={args.deploy_month} "
            f"max_train_month={args.max_train_month!r}"
        )

    val_months = sorted(prior["month"].astype(str).unique())[-int(args.val_months):]
    train = prior[~prior["month"].astype(str).isin(val_months)].copy()
    val = prior[prior["month"].astype(str).isin(val_months)].copy()
    train_months = sorted(train["month"].astype(str).unique())
    if len(val_months) < int(args.val_months) or len(train_months) < int(args.min_train_months):
        raise ValueError(
            f"{ticker}: insufficient history train_months={len(train_months)} "
            f"val_months={len(val_months)} deploy_month={args.deploy_month}"
        )

    _, train_cache = build_fold_caches(train, grid, args)
    _, val_cache = build_fold_caches(val, grid, args)
    rankings = side_rankings(train_cache, val_cache, grid, train_months, val_months, args)

    best_cfg = ensemble_grid[0]
    best_score = -1e18
    best_metrics: dict = {}
    for cfg in ensemble_grid:
        from walkforward_level_stability_ensemble import assemble_trades

        val_trades = assemble_trades(val_cache, rankings, cfg, args)
        row = metrics(val_trades, val_months)
        score = score_metrics(row, int(args.min_val_trades), int(args.min_month_trades))
        if score > best_score:
            best_cfg = cfg
            best_score = score
            best_metrics = row

    if best_score <= -1e17 and not bool(args.allow_invalid_val_deploy):
        raise ValueError(f"{ticker}: validation rejected production deployment score={best_score:.1f}")

    long_configs = selected_configs(rankings["LONG"], best_cfg.long_count)
    short_configs = selected_configs(rankings["SHORT"], best_cfg.short_count)
    return {
        "ticker": ticker,
        "deploy_month": str(args.deploy_month),
        "max_train_month": str(args.max_train_month).strip(),
        "excluded_train_months": sorted(excluded_train_months),
        "train_months": train_months,
        "val_months": val_months,
        "ensemble_config": best_cfg.name,
        "ensemble": asdict(best_cfg),
        "top_long_configs": [config_to_payload(config) for config in long_configs],
        "top_short_configs": [config_to_payload(config) for config in short_configs],
        "top_long_score": float(rankings["LONG"][0]["score"]) if rankings["LONG"] else float("nan"),
        "top_short_score": float(rankings["SHORT"][0]["score"]) if rankings["SHORT"] else float("nan"),
        "val_score": float(best_score),
        "val_metrics": best_metrics,
    }


def write_summary(output_dir: Path, payload: dict) -> None:
    lines = [
        "# Production Level-Stability Signal",
        "",
        "This artifact is fit only on months prior to `deploy_month` and, when set, at or before `max_train_month`.",
        "",
        f"- Policy: `{payload['policy']}`",
        f"- Deploy month: `{payload['deploy_month']}`",
        f"- Max train month: `{payload.get('max_train_month') or 'deploy_month-1'}`",
        f"- Train start date: `{payload['train_start_date']}`",
        "",
        "## Tickers",
        "",
        "| Ticker | Ensemble | Val Months | Val Trades | Val PF | Val PnL | Long Configs | Short Configs |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for ticker, item in payload["tickers"].items():
        val = item.get("val_metrics", {})
        lines.append(
            f"| {ticker} | {item.get('ensemble_config', '')} | {','.join(item.get('val_months', []))} | "
            f"{int(val.get('trades', 0))} | {float(val.get('profit_factor', float('nan'))):.3f} | "
            f"{float(val.get('pnl_dollars', 0.0)):,.0f} | "
            f"{len(item.get('top_long_configs', []))} | {len(item.get('top_short_configs', []))} |"
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
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fit production level-stability signal artifact from prior months only.")
    parser.add_argument("--data", default=str(PROJECT_ROOT / "training_data" / "training_data_spx_qqq_spy.parquet"))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--deploy-month", default=current_deploy_month())
    parser.add_argument(
        "--max-train-month",
        default="",
        help="Optional YYYYMM cap for training/validation rows. Useful when months before deploy_month are partial.",
    )
    parser.add_argument(
        "--exclude-train-months",
        nargs="*",
        default=[],
        help="YYYYMM months to exclude from production train/validation rows, for raw-partial months before deploy.",
    )
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--train-start-date", default="20250101")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-train-months", type=int, default=3)
    parser.add_argument("--min-train-side-trades", type=int, default=30)
    parser.add_argument("--min-train-side-month-trades", type=int, default=5)
    parser.add_argument("--min-val-side-trades", type=int, default=18)
    parser.add_argument("--min-val-side-month-trades", type=int, default=3)
    parser.add_argument("--min-val-trades", type=int, default=45)
    parser.add_argument("--min-month-trades", type=int, default=15)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--horizon-steps", type=int, default=36)
    parser.add_argument("--notional", type=float, default=100000.0)
    parser.add_argument("--gates", nargs="+", default=["fib_wall", "sr_combo", "ib_reversal"])
    parser.add_argument("--min-target-bps", nargs="+", type=float, default=[15.0, 25.0])
    parser.add_argument("--max-target-bps", nargs="+", type=float, default=[100.0, 150.0, 250.0])
    parser.add_argument("--stop-bps", nargs="+", type=float, default=[20.0, 30.0])
    parser.add_argument("--start-minutes", nargs="+", type=int, default=[570, 630])
    parser.add_argument("--ensemble-counts", nargs="+", type=int, default=[1, 2, 3, 5, 8])
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[999, 12, 8, 4])
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--allow-invalid-val-deploy", action="store_true")
    args = parser.parse_args()

    args.deploy_month = str(args.deploy_month)
    args.max_train_month = str(args.max_train_month).strip()
    if args.max_train_month and args.max_train_month >= args.deploy_month:
        raise ValueError("--max-train-month must be earlier than --deploy-month")
    args.start_month = args.deploy_month
    args.end_month = args.deploy_month
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = load_frame(args.data, args)
    tickers = [str(t).upper() for t in args.tickers]

    results: dict[str, dict] = {}
    if int(args.workers) > 1:
        with ThreadPoolExecutor(max_workers=int(args.workers)) as executor:
            futures = {executor.submit(fit_ticker, frame, ticker, args): ticker for ticker in tickers}
            for future in as_completed(futures):
                ticker = futures[future]
                results[ticker] = future.result()
                print(f"[PROD_LEVEL_SIGNAL] {ticker} {results[ticker]['ensemble_config']}", flush=True)
    else:
        for ticker in tickers:
            results[ticker] = fit_ticker(frame, ticker, args)
            print(f"[PROD_LEVEL_SIGNAL] {ticker} {results[ticker]['ensemble_config']}", flush=True)

    payload = {
        "policy": f"level_stability_ensemble_prod_{args.deploy_month}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "deploy_month": args.deploy_month,
        "max_train_month": args.max_train_month,
        "train_start_date": str(args.train_start_date),
        "signal_family": "level_stability_ensemble",
        "cooldown_minutes": int(args.cooldown_minutes),
        "horizon_steps": int(args.horizon_steps),
        "notional": float(args.notional),
        "required_columns": REQUIRED_LEVEL_COLUMNS,
        "args": vars(args),
        "tickers": {ticker: results[ticker] for ticker in tickers},
    }
    (out_dir / "level_stability_signal.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(out_dir, payload)
    print((out_dir / "SUMMARY.md").read_text(encoding="utf-8"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
