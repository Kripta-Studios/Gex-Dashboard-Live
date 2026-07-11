from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

if __package__:
    from .evaluate_xinput_level_filter import month_add, month_range
    from .walkforward_event_option_gate import DeployConfig, build_fold_grid, deploy, metrics, score_metrics
    from .walkforward_event_option_portfolio_var_jepa import (
        COOLDOWNS,
        DAILY_CAPS,
        DELTA_BY_TICKER,
        TICKERS,
        audit_runtime_replay,
        build_action_frame,
        choose_action,
        load_base_frame,
        month_seed,
        predict_actions,
        save_model_artifact,
        sha256_file,
        train_model,
        write_json,
    )
else:
    from evaluate_xinput_level_filter import month_add, month_range
    from walkforward_event_option_gate import DeployConfig, build_fold_grid, deploy, metrics, score_metrics
    from walkforward_event_option_portfolio_var_jepa import (
        COOLDOWNS,
        DAILY_CAPS,
        DELTA_BY_TICKER,
        TICKERS,
        audit_runtime_replay,
        build_action_frame,
        choose_action,
        load_base_frame,
        month_seed,
        predict_actions,
        save_model_artifact,
        sha256_file,
        train_model,
        write_json,
    )


@dataclass
class PatchCoreBank:
    features: list[str]
    means: np.ndarray
    scales: np.ndarray
    centers: np.ndarray
    source_indices: np.ndarray

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        values = frame[self.features].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=np.float32, copy=True)
        values[~np.isfinite(values)] = 0.0
        return ((values - self.means) / self.scales).astype(np.float32, copy=False)

    def distances(self, frame: pd.DataFrame, chunk_size: int = 4096) -> np.ndarray:
        values = self.transform(frame)
        output = np.empty(len(values), dtype=np.float32)
        for start in range(0, len(values), int(chunk_size)):
            part = values[start : start + int(chunk_size)]
            squared = ((part[:, None, :] - self.centers[None, :, :]) ** 2).sum(axis=-1)
            output[start : start + len(part)] = np.sqrt(squared.min(axis=1))
        return output


def fit_patchcore_bank(frame: pd.DataFrame, features: list[str], coreset_size: int) -> PatchCoreBank:
    if frame.empty:
        raise ValueError("cannot fit PatchCore bank on an empty frame")
    raw = frame[features].replace([np.inf, -np.inf], np.nan).astype(float)
    means = raw.mean(axis=0).fillna(0.0).to_numpy(dtype=np.float32)
    filled = raw.fillna(pd.Series(means, index=features)).fillna(0.0)
    scales = filled.std(axis=0, ddof=0).replace(0.0, 1.0).fillna(1.0).to_numpy(dtype=np.float32)
    values = ((filled.to_numpy(dtype=np.float32) - means) / scales).astype(np.float32, copy=False)
    size = min(max(int(coreset_size), 1), len(values))
    first = int(np.argmax((values**2).sum(axis=1)))
    chosen = [first]
    min_squared = ((values - values[first]) ** 2).sum(axis=1)
    min_squared[first] = -1.0
    while len(chosen) < size:
        index = int(np.argmax(min_squared))
        if min_squared[index] < 0.0:
            break
        chosen.append(index)
        candidate = ((values - values[index]) ** 2).sum(axis=1)
        min_squared = np.minimum(min_squared, candidate)
        min_squared[np.asarray(chosen, dtype=int)] = -1.0
    indices = np.asarray(chosen, dtype=np.int64)
    return PatchCoreBank(list(features), means, scales, values[indices].copy(), indices)


def save_patchcore_bank(path: Path, bank: PatchCoreBank) -> str:
    np.savez_compressed(
        path,
        features=np.asarray(bank.features, dtype=str),
        means=bank.means,
        scales=bank.scales,
        centers=bank.centers,
        source_indices=bank.source_indices,
    )
    return sha256_file(path)


def add_patchcore_distance(
    scored: pd.DataFrame, banks: dict[str, PatchCoreBank]
) -> pd.DataFrame:
    output = scored.copy()
    output["patchcore_distance"] = np.nan
    for ticker, bank in banks.items():
        mask = output["ticker"].eq(ticker)
        if mask.any():
            output.loc[mask, "patchcore_distance"] = bank.distances(output.loc[mask])
    if not np.isfinite(pd.to_numeric(output["patchcore_distance"], errors="coerce")).all():
        raise RuntimeError("non-finite PatchCore distance")
    return output


def selection_value(row: dict[str, Any], args: argparse.Namespace) -> float:
    value = score_metrics(
        row,
        int(args.min_val_trades),
        int(args.min_month_trades),
        float(args.min_val_pf),
        float(args.min_val_win_rate),
        float(args.min_call_rate),
        float(args.max_call_rate),
    )
    positive = float(row.get("positive_month_rate", float("nan")))
    if value > -1e17 and (not np.isfinite(positive) or positive < float(args.min_val_positive_month_rate)):
        return -1e18 + int(row.get("trades", 0))
    if value > -1e17:
        daily_win_rate = float(row.get("daily_win_rate", float("nan")))
        if np.isfinite(daily_win_rate):
            value += float(args.daily_win_weight) * daily_win_rate
        top5_share = float(row.get("top5_share_of_pnl", float("nan")))
        if np.isfinite(top5_share):
            value -= float(args.top5_share_penalty) * max(top5_share - 1.0, 0.0)
    return float(value)


def select_policy(
    scored: pd.DataFrame,
    ticker: str,
    val_months: list[str],
    args: argparse.Namespace,
    *,
    use_patchcore: bool,
) -> tuple[DeployConfig | None, float | None, dict[str, Any], pd.DataFrame]:
    part = scored[scored["ticker"].eq(ticker)].copy()
    grid_args = argparse.Namespace(
        threshold_grid=[float(value) for value in args.threshold_grid],
        threshold_quantiles=[float(value) for value in args.threshold_quantiles],
        max_day_grid=[int(DAILY_CAPS[ticker])],
    )
    configs = build_fold_grid(part, grid_args)
    distance_caps: list[float | None] = [None]
    if use_patchcore:
        values = pd.to_numeric(part["patchcore_distance"], errors="raise").to_numpy(dtype=float)
        distance_caps = sorted(set(float(np.quantile(values, q)) for q in args.distance_quantiles))
    best_cfg: DeployConfig | None = None
    best_cap: float | None = None
    best_metrics = metrics(pd.DataFrame(), val_months)
    # Start below the invalid-policy sentinel. At magnitudes near 1e18, adding
    # fewer than ~64 trades can round back to exactly -1e18 in float64; using
    # -inf preserves the best invalid diagnostics without ever deploying it.
    best_score = -float("inf")
    rows: list[dict[str, Any]] = []
    for cfg in configs:
        for cap in distance_caps:
            candidates = part if cap is None else part[part["patchcore_distance"].le(float(cap))]
            trades = deploy(candidates, cfg, int(COOLDOWNS[ticker]))
            row = metrics(trades, val_months)
            value = selection_value(row, args)
            rows.append(
                {
                    "arm": "patchcore" if use_patchcore else "control",
                    "ticker": ticker,
                    "deploy_config": cfg.name,
                    "distance_cap": cap,
                    "score": value,
                    **row,
                }
            )
            if value > best_score:
                best_cfg, best_cap, best_metrics, best_score = cfg, cap, row, value
    if best_score <= -1e17:
        best_cfg = None
        best_cap = None
    return best_cfg, best_cap, best_metrics, pd.DataFrame(rows)


def apply_policy(
    scored: pd.DataFrame,
    ticker: str,
    cfg: DeployConfig | None,
    distance_cap: float | None,
) -> pd.DataFrame:
    part = scored[scored["ticker"].eq(ticker)].copy()
    if cfg is None:
        return part.iloc[0:0].copy()
    if distance_cap is not None:
        part = part[part["patchcore_distance"].le(float(distance_cap))].copy()
    return deploy(part, cfg, int(COOLDOWNS[ticker]))


def diagnostic_row(scored: pd.DataFrame, ticker: str, month: str) -> dict[str, Any]:
    part = scored[scored["ticker"].eq(ticker)]
    distance = pd.to_numeric(part["patchcore_distance"], errors="coerce")
    error = (pd.to_numeric(part["score"], errors="coerce") - pd.to_numeric(part["realized_return"], errors="coerce").clip(-2, 2)).abs()
    correlation = distance.corr(error, method="spearman") if distance.nunique() > 1 and error.nunique() > 1 else float("nan")
    return {
        "ticker": ticker,
        "month": month,
        "rows": int(len(part)),
        "distance_mean": float(distance.mean()),
        "distance_p95": float(distance.quantile(0.95)),
        "distance_error_spearman": float(correlation),
    }


def full_gate(summary: dict[str, Any]) -> bool:
    for ticker in TICKERS:
        row = summary["tickers"][ticker]
        if not (
            float(row["profit_factor"]) >= 1.3
            and float(row["win_rate"]) >= 0.5
            and int(row["min_month_trades"]) >= 18
            and float(row["positive_month_rate"]) >= 1.0
        ):
            return False
    return True


def summarize(trades: pd.DataFrame, months: list[str], arm: str) -> dict[str, Any]:
    result = {
        "arm": arm,
        "overall": metrics(trades, months),
        "tickers": {ticker: metrics(trades[trades["ticker"].eq(ticker)], months) for ticker in TICKERS},
        "months": {month: metrics(trades[trades["month"].astype(str).eq(month)], [month]) for month in months},
        "runtime_replay_audit": audit_runtime_replay(trades),
    }
    result["meets_full_ticker_gate"] = full_gate(result)
    return result


def build_provenance(folds: pd.DataFrame, months: list[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    passed = len(folds) == len(months) * len(TICKERS) * 2
    for row in folds.to_dict("records"):
        paths = {
            "model": (Path(row["model_artifact_path"]), row["model_artifact_sha256"]),
            "coreset": (Path(row["coreset_path"]), row["coreset_sha256"]),
            "policy": (Path(row["policy_artifact_path"]), row["policy_artifact_sha256"]),
        }
        hashes_ok = all(path.is_file() and sha256_file(path) == expected for path, expected in paths.values())
        training = [value for value in str(row["training_months"]).split(",") if value]
        selection = [value for value in str(row["selection_months"]).split(",") if value]
        causal = bool(training and selection) and all(value < str(row["month"]) for value in training + selection)
        row_ok = bool(hashes_ok and causal)
        passed &= row_ok
        rows.append({"arm": row["arm"], "ticker": row["ticker"], "month": row["month"], "hashes_ok": hashes_ok, "causal": causal, "passed": row_ok})
    return {"schema_version": 1, "passed": bool(passed), "expected_rows": 30, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Nested PatchCore abstention over a shared exact-bucket deterministic payoff head.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-train-rows", type=int, default=5000)
    parser.add_argument("--clip-return", type=float, default=2.0)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--latent-dim", type=int, default=16)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--infer-batch-size", type=int, default=4096)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.000001)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--coreset-size", type=int, default=128)
    parser.add_argument("--distance-quantiles", nargs="+", type=float, default=[0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 1.0])
    parser.add_argument("--threshold-grid", nargs="+", type=float, default=[-1e9, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20])
    parser.add_argument("--threshold-quantiles", nargs="+", type=float, default=[0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    parser.add_argument("--min-val-trades", type=int, default=54)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-val-pf", type=float, default=1.3)
    parser.add_argument("--min-val-win-rate", type=float, default=0.5)
    parser.add_argument("--min-val-positive-month-rate", type=float, default=1.0)
    parser.add_argument("--min-call-rate", type=float, default=0.0)
    parser.add_argument("--max-call-rate", type=float, default=1.0)
    parser.add_argument("--daily-win-weight", type=float, default=0.25)
    parser.add_argument("--top5-share-penalty", type=float, default=0.10)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    parser.add_argument("--seed", type=int, default=20260618)
    parser.add_argument("--deterministic", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    for child in ("fold_model_artifacts", "fold_coreset_artifacts", "fold_policy_artifacts", "fold_training_history"):
        (output_dir / child).mkdir()
    data_path = Path(args.data)
    base, latent_features = load_base_frame(data_path)
    actions, model_features = build_action_frame(base, latent_features)
    months = month_range(args.start_month, args.end_month)
    if months != ["202601", "202602", "202603", "202604", "202605"]:
        raise RuntimeError("evaluation months must remain 202601..202605")
    metadata = {
        "schema_version": 1,
        "args": vars(args),
        "data_path": str(data_path),
        "data_sha256": sha256_file(data_path),
        "date_min": str(base["date"].min()),
        "date_max": str(base["date"].max()),
        "base_rows": int(len(base)),
        "action_rows": int(len(actions)),
        "market_features": latent_features,
        "model_features": model_features,
        "single_factor": "train_only_patchcore_distance_abstention",
        "direction_and_score_changed_by_patchcore": False,
        "dataset_contract": "executable_quote_ask_to_bid",
        "delta_by_ticker": DELTA_BY_TICKER,
        "daily_caps": DAILY_CAPS,
        "cooldowns": COOLDOWNS,
        "june_2026_sealed": True,
        "production_live_ready": False,
    }
    write_json(output_dir / "metadata.json", metadata)

    trades_by_arm: dict[str, list[pd.DataFrame]] = {"control": [], "patchcore": []}
    fold_rows: list[dict[str, Any]] = []
    grid_rows: list[pd.DataFrame] = []
    diagnostics: list[dict[str, Any]] = []
    for month in months:
        val_months = [month_add(month, -offset) for offset in range(args.val_months, 0, -1)]
        first_val = val_months[0]
        train = actions[actions["month"].astype(str) < first_val].copy()
        val = actions[actions["month"].astype(str).isin(val_months)].copy()
        test = actions[actions["month"].astype(str).eq(month)].copy()
        seed = month_seed(args.seed, month)
        model, preprocessor, history = train_model(train, model_features, "deterministic", seed, args)
        model_path = output_dir / "fold_model_artifacts" / f"payoff_head_{month}.pt"
        model_hash = save_model_artifact(model_path, model, preprocessor, "deterministic", month, seed, args)
        write_json(output_dir / "fold_training_history" / f"training_{month}.json", history)

        train_events = train.drop_duplicates("event_id", keep="first")
        banks: dict[str, PatchCoreBank] = {}
        bank_fields: dict[str, dict[str, Any]] = {}
        for ticker in TICKERS:
            bank = fit_patchcore_bank(train_events[train_events["ticker"].eq(ticker)], latent_features, args.coreset_size)
            bank_path = output_dir / "fold_coreset_artifacts" / f"patchcore_{ticker}_{month}.npz"
            bank_hash = save_patchcore_bank(bank_path, bank)
            banks[ticker] = bank
            bank_fields[ticker] = {"coreset_path": str(bank_path), "coreset_sha256": bank_hash, "coreset_rows": len(bank.centers)}

        val_actions, _ = predict_actions(model, preprocessor, val, args)
        val_scored = add_patchcore_distance(choose_action(val_actions), banks)
        policies: dict[tuple[str, str], tuple[DeployConfig | None, float | None]] = {}
        policy_fields: dict[tuple[str, str], dict[str, Any]] = {}
        for ticker in TICKERS:
            for arm in ("control", "patchcore"):
                cfg, cap, val_metrics, grid = select_policy(val_scored, ticker, val_months, args, use_patchcore=arm == "patchcore")
                grid["month"] = month
                grid_rows.append(grid)
                policies[(arm, ticker)] = (cfg, cap)
                payload = {
                    "schema_version": 1,
                    "arm": arm,
                    "ticker": ticker,
                    "evaluation_month": month,
                    "training_months": sorted(train["month"].astype(str).unique()),
                    "selection_months": val_months,
                    "seed": seed,
                    "model_artifact_path": str(model_path),
                    "model_artifact_sha256": model_hash,
                    **bank_fields[ticker],
                    "deploy_config": cfg.name if cfg else "ABSTAIN_NO_VALID_POLICY",
                    "distance_cap": cap,
                    "distance_only_abstains": True,
                    "policy_frozen_before_evaluation": True,
                }
                policy_path = output_dir / "fold_policy_artifacts" / f"policy_{arm}_{ticker}_{month}.json"
                write_json(policy_path, payload)
                policy_fields[(arm, ticker)] = {
                    "policy_artifact_path": str(policy_path),
                    "policy_artifact_sha256": sha256_file(policy_path),
                    "val_metrics": val_metrics,
                }

        test_actions, _ = predict_actions(model, preprocessor, test, args)
        test_scored = add_patchcore_distance(choose_action(test_actions), banks)
        for ticker in TICKERS:
            diagnostics.append(diagnostic_row(test_scored, ticker, month))
            for arm in ("control", "patchcore"):
                cfg, cap = policies[(arm, ticker)]
                trades = apply_policy(test_scored, ticker, cfg, cap)
                if not trades.empty:
                    trades = trades.copy()
                    trades["arm"] = arm
                    trades["test_month"] = month
                    trades["delta_bucket"] = DELTA_BY_TICKER[ticker]
                    trades_by_arm[arm].append(trades)
                test_metrics = metrics(trades, [month])
                fields = policy_fields[(arm, ticker)]
                fold_rows.append(
                    {
                        "arm": arm,
                        "ticker": ticker,
                        "month": month,
                        "status": "ok" if cfg else "invalid_validation",
                        "selected": cfg is not None,
                        "deploy_config": cfg.name if cfg else "ABSTAIN_NO_VALID_POLICY",
                        "distance_cap": cap,
                        "training_months": ",".join(sorted(train["month"].astype(str).unique())),
                        "selection_months": ",".join(val_months),
                        "seed": seed,
                        "delta_bucket": DELTA_BY_TICKER[ticker],
                        "daily_cap": DAILY_CAPS[ticker],
                        "cooldown_minutes": COOLDOWNS[ticker],
                        "model_artifact_path": str(model_path),
                        "model_artifact_sha256": model_hash,
                        **bank_fields[ticker],
                        "policy_artifact_path": fields["policy_artifact_path"],
                        "policy_artifact_sha256": fields["policy_artifact_sha256"],
                        **{f"val_{key}": value for key, value in fields["val_metrics"].items()},
                        **{f"test_{key}": value for key, value in test_metrics.items()},
                    }
                )
        print(f"[PATCHCORE] month={month} folds={len(fold_rows)}/30", flush=True)

    combined: dict[str, pd.DataFrame] = {}
    summaries: dict[str, Any] = {}
    for arm in ("control", "patchcore"):
        frame = pd.concat(trades_by_arm[arm], ignore_index=True) if trades_by_arm[arm] else actions.iloc[0:0].copy()
        combined[arm] = frame
        frame.to_csv(output_dir / f"trades_{arm}.csv", index=False)
        summaries[arm] = summarize(frame, months, arm)
        if not summaries[arm]["runtime_replay_audit"]["passed"]:
            raise RuntimeError(f"runtime audit failed for {arm}")
    diagnostic_frame = pd.DataFrame(diagnostics)
    finite_corr = pd.to_numeric(diagnostic_frame["distance_error_spearman"], errors="coerce").dropna()
    distance_supported = bool(len(finite_corr) == 15 and (finite_corr > 0).sum() >= 10 and finite_corr.median() > 0)
    decision = {
        "distance_diagnostic_supported": distance_supported,
        "patchcore_meets_full_downstream_gate": bool(summaries["patchcore"]["meets_full_ticker_gate"]),
        "continue_from_patchcore": bool(distance_supported and summaries["patchcore"]["meets_full_ticker_gate"]),
        "production_live_ready": False,
    }
    folds_frame = pd.DataFrame(fold_rows).sort_values(["arm", "ticker", "month"]).reset_index(drop=True)
    folds_frame.to_csv(output_dir / "selected_folds.csv", index=False)
    provenance = build_provenance(folds_frame, months)
    write_json(output_dir / "policy_selection_provenance.json", provenance)
    if not provenance["passed"]:
        raise RuntimeError("PatchCore policy selection provenance failed")
    pd.concat(grid_rows, ignore_index=True).to_csv(output_dir / "candidate_validation.csv", index=False)
    diagnostic_frame.sort_values(["ticker", "month"]).to_csv(output_dir / "distance_diagnostics.csv", index=False)
    write_json(output_dir / "summary.json", {"arms": summaries, "distance_diagnostic": {"positive_cells": int((finite_corr > 0).sum()), "finite_cells": int(len(finite_corr)), "median_spearman": float(finite_corr.median())}, "decision": decision})
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
