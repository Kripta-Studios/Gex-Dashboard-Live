from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NEURAL_ROOT = PROJECT_ROOT / "neural"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(NEURAL_ROOT) not in sys.path:
    sys.path.insert(0, str(NEURAL_ROOT))

import neural.jepa.train_option_value_jepa as ov
from neural.jepa.evaluate_180m_direction import fmt_float, fmt_money, fmt_pct
from neural.jepa.train_backtest_option_policy import (
    candidate_trades_from_selection,
    fixed_delta_policy,
    normalize_date,
    oracle_policy,
    trade_metrics,
)


LOG_PATH: Path | None = None


def log(message: str) -> None:
    print(message, flush=True)
    if LOG_PATH is not None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(message + os.linesep)


def metrics_row(label: str, metrics: dict) -> str:
    return (
        f"| {label} | {metrics.get('trades', 0)} | {fmt_pct(metrics.get('win_rate', float('nan')))} | "
        f"{fmt_float(metrics.get('profit_factor', float('nan')))} | "
        f"{fmt_money(metrics.get('pnl_dollars', 0.0))} | "
        f"{fmt_money(metrics.get('max_drawdown', 0.0))} | "
        f"{fmt_money(metrics.get('avg_pnl', 0.0))} | "
        f"{fmt_float(metrics.get('avg_hold_minutes', float('nan')), 1)} | "
        f"{fmt_float(metrics.get('avg_delta_abs', float('nan')), 3)} |"
    )


def payload(trades: pd.DataFrame) -> dict:
    return {
        "overall": trade_metrics(trades),
        "per_ticker": {str(k): trade_metrics(v) for k, v in trades.groupby("ticker", sort=True)} if not trades.empty else {},
        "trades": trades,
    }


def fold_months(candidates: pd.DataFrame, min_train_months: int, start_month: str | None, end_month: str | None) -> list[str]:
    months = sorted(candidates["month"].astype(str).unique().tolist())
    if len(months) <= int(min_train_months):
        return []
    out = months[int(min_train_months) :]
    if start_month:
        out = [m for m in out if m >= str(start_month)]
    if end_month:
        out = [m for m in out if m <= str(end_month)]
    return out


def maybe_sample_dynamic(dynamic_frame: pd.DataFrame, max_rows: int, seed: int) -> pd.DataFrame:
    if int(max_rows) <= 0 or len(dynamic_frame) <= int(max_rows):
        return dynamic_frame
    return dynamic_frame.sample(n=int(max_rows), random_state=int(seed)).reset_index(drop=True)


def evaluate_fold(
    model: ov.OptionValueJEPA,
    scalers: dict,
    train_candidates: pd.DataFrame,
    test_candidates: pd.DataFrame,
    state_test: pd.DataFrame,
    market_features: list[str],
    option_features: list[str],
    dynamic_features: list[str],
    args,
    test_month: str,
) -> dict[str, pd.DataFrame]:
    test_pred = ov.predict_entry(model, scalers, test_candidates, args)
    selected_best = ov.select_best(test_pred, "ovjepa_pred_best")
    selected_rule = ov.select_best(test_pred, "ovjepa_pred_rule")
    selected_hold = ov.select_best(test_pred, "ovjepa_pred_hold180")
    selected_fixed_070 = ov.select_fixed_delta(test_pred, 0.70)

    fixed_070 = fixed_delta_policy(test_candidates, 0.70, "rule", "fixed_delta_0.70_hard")
    fixed_070_exit = ov.simulate_learned_exit(
        selected_fixed_070,
        state_test,
        model,
        scalers,
        market_features,
        option_features,
        dynamic_features,
        args,
        float(args.exit_margin),
        "fixed_delta_0.70_learned_exit_5m",
    )
    ov_best_hard = candidate_trades_from_selection(selected_best, "rule", "option_value_best_select_hard")
    ov_rule_hard = candidate_trades_from_selection(selected_rule, "rule", "option_value_rule_select_hard")
    ov_hold_hard = candidate_trades_from_selection(selected_hold, "rule", "option_value_hold180_select_hard")
    ov_best_exit = ov.simulate_learned_exit(
        selected_best,
        state_test,
        model,
        scalers,
        market_features,
        option_features,
        dynamic_features,
        args,
        float(args.exit_margin),
        "option_value_best_select_learned_exit_5m",
    )
    oracle_rule = oracle_policy(test_candidates, "rule_pnl_dollars", "rule", "oracle_best_delta_hard")
    oracle_exit = oracle_policy(test_candidates, "oracle_pnl_dollars", "oracle", "oracle_best_delta_oracle_exit")

    policy_trades = {
        "fixed_delta_0.70_hard": fixed_070,
        "fixed_delta_0.70_learned_exit_5m": fixed_070_exit,
        "option_value_hold180_select_hard": ov_hold_hard,
        "option_value_rule_select_hard": ov_rule_hard,
        "option_value_best_select_hard": ov_best_hard,
        "option_value_best_select_learned_exit_5m": ov_best_exit,
        "oracle_best_delta_hard": oracle_rule,
        "oracle_best_delta_oracle_exit": oracle_exit,
    }
    for trades in policy_trades.values():
        if not trades.empty:
            trades["fold_month"] = test_month
            trades["train_candidates"] = int(len(train_candidates))
    return policy_trades


def write_summary(output_dir: Path, args, metadata: dict, policy_results: dict[str, dict], fold_metrics: pd.DataFrame) -> None:
    lines = [
        "# OptionValueJEPA Walk-Forward Since 2022",
        "",
        f"Candidate labels: `{args.candidate_labels}`",
        f"Train start: `{normalize_date(args.train_start_date)}`",
        f"Min train months: `{args.min_train_months}`",
        f"Epochs per fold: `{args.epochs}`",
        f"Dynamic target: `{getattr(args, 'dynamic_target', 'future_best')}`",
        f"Exit margin: `{args.exit_margin}`",
        "",
        "## Overall Walk-Forward Results",
        "",
        "| Policy | Trades | WR | PF | PnL | Max DD | Avg PnL | Avg Hold | Avg Delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for policy, item in policy_results.items():
        lines.append(metrics_row(policy, item["overall"]))

    lines += [
        "",
        "## Fold Metrics",
        "",
        "| Month | Policy | Trades | WR | PF | PnL | Max DD |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in fold_metrics.iterrows():
        lines.append(
            f"| {row['fold_month']} | {row['policy']} | {int(row['trades'])} | "
            f"{fmt_pct(float(row['win_rate']))} | {fmt_float(float(row['profit_factor']))} | "
            f"{fmt_money(float(row['pnl_dollars']))} | {fmt_money(float(row['max_drawdown']))} |"
        )

    lines += [
        "",
        "## Config",
        "",
        "```json",
        json.dumps(metadata, indent=2, allow_nan=True),
        "```",
        "",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Monthly walk-forward for OptionValueJEPA.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--train-start-date", default="20220801")
    parser.add_argument("--min-train-months", type=int, default=12)
    parser.add_argument("--start-month", default="")
    parser.add_argument("--end-month", default="")
    parser.add_argument("--max-folds", type=int, default=0)
    parser.add_argument("--risk-capital", type=float, default=1000.0)
    parser.add_argument("--max-hold-minutes", type=int, default=180)
    parser.add_argument("--hard-stop-pct", type=float, default=-0.60)
    parser.add_argument("--min-exit-hold-minutes", type=int, default=15)
    parser.add_argument("--exit-margin", type=float, default=-0.30)
    parser.add_argument("--greeks-cache-size", type=int, default=60)
    parser.add_argument("--progress-every", type=int, default=20)
    parser.add_argument("--state-chunk-groups", type=int, default=20)
    parser.add_argument("--rebuild-state-rows", action="store_true")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--hidden-dim", type=int, default=96)
    parser.add_argument("--market-z-dim", type=int, default=24)
    parser.add_argument("--option-z-dim", type=int, default=12)
    parser.add_argument("--dynamic-z-dim", type=int, default=12)
    parser.add_argument("--dropout", type=float, default=0.12)
    parser.add_argument("--lr", type=float, default=8e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--dynamic-loss-weight", type=float, default=0.75)
    parser.add_argument(
        "--dynamic-target",
        choices=sorted(ov.DYNAMIC_TARGET_COLUMNS),
        default="future_best",
        help="Continuation target used by the dynamic exit head.",
    )
    parser.add_argument("--entry-batch-size", type=int, default=1024)
    parser.add_argument("--dynamic-batch-size", type=int, default=8192)
    parser.add_argument("--predict-batch-size", type=int, default=4096)
    parser.add_argument("--max-dynamic-train-rows", type=int, default=260000)
    parser.add_argument("--min-val-trades", type=int, default=12)
    parser.add_argument("--seed", type=int, default=7227)
    parser.add_argument("--device", default="")
    parser.add_argument("--log-every-epochs", type=int, default=4)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    global LOG_PATH
    LOG_PATH = output_dir / "run.log"
    if LOG_PATH.exists():
        LOG_PATH.unlink()
    ov.LOG_PATH = LOG_PATH

    np.random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    candidates = ov.clean_date_columns(pd.read_parquet(args.candidate_labels))
    candidates = candidates[candidates["date"].astype(str) >= normalize_date(args.train_start_date)].copy()
    if candidates.empty:
        raise RuntimeError("No candidates after train-start-date.")

    state_rows = ov.load_or_build_state_rows(candidates, output_dir, args)
    market_features, option_features, dynamic_features = ov.infer_feature_sets(candidates)
    dynamic_features = [f for f in dynamic_features if f in state_rows.columns]
    months = fold_months(
        candidates,
        int(args.min_train_months),
        args.start_month or None,
        args.end_month or None,
    )
    if int(args.max_folds) > 0:
        months = months[: int(args.max_folds)]
    if not months:
        raise RuntimeError("No walk-forward months selected.")

    log(f"[OVJEPA_WF] months={months[0]}..{months[-1]} folds={len(months)}")
    all_policy_trades: dict[str, list[pd.DataFrame]] = {}
    fold_rows: list[dict] = []
    start_time = time.time()

    for fold_idx, test_month in enumerate(months, start=1):
        fold_seed = int(args.seed) + fold_idx
        np.random.seed(fold_seed)
        torch.manual_seed(fold_seed)
        train_candidates = candidates[candidates["month"].astype(str) < test_month].copy()
        test_candidates = candidates[candidates["month"].astype(str) == test_month].copy()
        if train_candidates.empty or test_candidates.empty:
            continue
        train_ids = set(train_candidates["candidate_id"].astype(int))
        test_ids = set(test_candidates["candidate_id"].astype(int))
        state_train = state_rows[state_rows["candidate_id"].astype(int).isin(train_ids)].copy()
        state_test = state_rows[state_rows["candidate_id"].astype(int).isin(test_ids)].copy()
        dyn_train = ov.make_dynamic_frame(state_train, train_candidates, market_features, option_features)
        dyn_train = maybe_sample_dynamic(dyn_train, int(args.max_dynamic_train_rows), fold_seed)
        if dyn_train.empty or state_test.empty:
            log(f"[OVJEPA_WF] skipping {test_month}: empty dynamic/test state rows")
            continue
        log(
            f"[OVJEPA_WF] fold={fold_idx}/{len(months)} month={test_month} "
            f"train_candidates={len(train_candidates):,} test_candidates={len(test_candidates):,} "
            f"dyn_train={len(dyn_train):,}"
        )
        model, scalers = ov.train_model(
            train_candidates,
            dyn_train,
            market_features,
            option_features,
            dynamic_features,
            args,
        )
        policy_trades = evaluate_fold(
            model,
            scalers,
            train_candidates,
            test_candidates,
            state_test,
            market_features,
            option_features,
            dynamic_features,
            args,
            test_month,
        )
        for policy, trades in policy_trades.items():
            all_policy_trades.setdefault(policy, []).append(trades)
            metrics = trade_metrics(trades)
            fold_rows.append({"fold_month": test_month, "policy": policy, **metrics})
        elapsed = time.time() - start_time
        best_metrics = trade_metrics(policy_trades["option_value_best_select_hard"])
        fixed_metrics = trade_metrics(policy_trades["fixed_delta_0.70_hard"])
        log(
            f"[OVJEPA_WF] done month={test_month} elapsed={elapsed/60:.1f}m "
            f"fixed_pnl={fixed_metrics['pnl_dollars']:.0f} ov_pnl={best_metrics['pnl_dollars']:.0f}"
        )

    policy_results = {}
    for policy, parts in all_policy_trades.items():
        trades = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        trades.to_csv(output_dir / f"{policy}_wf_trades.csv", index=False)
        policy_results[policy] = payload(trades)
    fold_metrics = pd.DataFrame(fold_rows)
    fold_metrics.to_csv(output_dir / "fold_metrics.csv", index=False)

    metadata = {
        "args": vars(args),
        "candidate_rows": int(len(candidates)),
        "state_rows": int(len(state_rows)),
        "folds": months,
        "market_feature_count": len(market_features),
        "option_feature_count": len(option_features),
        "dynamic_feature_count": len(dynamic_features),
        "policy_metrics": {
            policy: {"overall": item["overall"], "per_ticker": item["per_ticker"]}
            for policy, item in policy_results.items()
        },
    }
    (output_dir / "metrics.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(output_dir, args, metadata, policy_results, fold_metrics)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
