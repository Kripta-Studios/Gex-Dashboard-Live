from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

if __package__:
    from .analyze_event_phys_td_flat_modal import (
        DEFAULT_MONTHS,
        acceptance_gate,
        artifact_hashes,
        daily_bootstrap,
        json_safe,
        metric_rows,
        paired_summary,
        parse_months,
        representation_by_cell,
        sha256_file,
        validate_walkforward_contract,
        write_json,
    )
else:
    from analyze_event_phys_td_flat_modal import (
        DEFAULT_MONTHS,
        acceptance_gate,
        artifact_hashes,
        daily_bootstrap,
        json_safe,
        metric_rows,
        paired_summary,
        parse_months,
        representation_by_cell,
        sha256_file,
        validate_walkforward_contract,
        write_json,
    )


ARMS = ("history_2025", "history_2022")
EXPECTED_OOF_MONTHS = (
    "202505",
    "202506",
    "202507",
    "202508",
    "202509",
    "202510",
    "202511",
    "202512",
    "202601",
    "202602",
    "202603",
    "202604",
    "202605",
)


def compare_encoder_configs(recent_meta: dict, long_meta: dict) -> dict[str, Any]:
    recent_args = dict(recent_meta["args"])
    long_args = dict(long_meta["args"])
    allowed = {"data", "output_dir"}
    differences = {
        key: {"history_2025": recent_args.get(key), "history_2022": long_args.get(key)}
        for key in sorted(set(recent_args) | set(long_args))
        if recent_args.get(key) != long_args.get(key)
    }
    unexpected = sorted(set(differences) - allowed)
    if unexpected:
        raise RuntimeError(f"history encoder configs differ outside the declared factor: {unexpected}")
    if set(differences) != allowed:
        raise RuntimeError(f"history encoder configs do not expose exactly the declared path differences: {differences}")
    if recent_meta.get("feature_cols") != long_meta.get("feature_cols"):
        raise RuntimeError("history encoder feature allowlists differ")
    required = {
        "encoder_input_mode": "flat",
        "start_month": "202505",
        "end_month": "202605",
        "data_cutoff_month": "202605",
        "seed": 20260618,
        "deterministic": True,
        "device": "cuda",
        "epochs": 8,
        "batch_size": 1024,
        "context_len": 6,
        "horizons": "1,3,6,12",
        "entry_start_minute_et": 630,
        "entry_end_minute_et": 870,
        "entry_grid_anchor_minute_et": 600,
        "expected_step_minutes": 5,
        "live_observable_features_only": True,
    }
    for arm, meta in (("history_2025", recent_meta), ("history_2022", long_meta)):
        bad = {key: meta["args"].get(key) for key, expected in required.items() if meta["args"].get(key) != expected}
        if bad or str(meta.get("effective_data_cutoff_month")) != "202605":
            raise RuntimeError(f"{arm} violates the frozen encoder contract: {bad}")
    return {
        "declared_factor": "encoder_training_history_start",
        "differences": differences,
        "identical_feature_count": len(recent_meta["feature_cols"]),
        "same_architecture_seed_and_epoch_budget": True,
    }


def load_train_comparison(paths: dict[str, Path]) -> pd.DataFrame:
    frames = []
    for arm in ARMS:
        frame = pd.read_csv(paths[f"{arm}_encoder"] / "fold_configs.csv", dtype={"month": str})
        if frame["month"].tolist() != list(EXPECTED_OOF_MONTHS):
            raise RuntimeError(f"{arm} OOF fold coverage mismatch")
        keep = [
            "month",
            "seed",
            "train_start_month",
            "train_end_month",
            "train_rows",
            "train_months",
            "train_windows",
            "test_rows",
            "feature_count",
            "context_valid_rate",
            "train_pred",
            "train_total",
            "train_z_effective_rank_ratio",
            "train_z_max_pc_var_ratio",
        ]
        frames.append(frame[keep].add_prefix(f"{arm}_").rename(columns={f"{arm}_month": "month"}))
    merged = frames[0].merge(frames[1], on="month", validate="one_to_one").sort_values("month")
    if not (
        pd.to_numeric(merged["history_2025_seed"], errors="raise").astype(int)
        == pd.to_numeric(merged["history_2022_seed"], errors="raise").astype(int)
    ).all():
        raise RuntimeError("paired history folds use different seeds")
    if set(merged["history_2025_train_start_month"].astype(str)) != {"202501"}:
        raise RuntimeError("recent arm does not start in 202501")
    if set(merged["history_2022_train_start_month"].astype(str)) != {"202201"}:
        raise RuntimeError("long-history arm does not start in 202201")
    return merged


def history_paired_summary(recent: pd.Series, long: pd.Series, *, alternative: str) -> dict[str, Any]:
    raw = paired_summary(recent, long, alternative=alternative)
    return {
        "alternative_for_history_2022": raw["alternative_for_modal"],
        "cells": raw["cells"],
        "median_difference_history_2022_minus_history_2025": raw["median_difference_modal_minus_flat"],
        "history_2022_wins": raw["modal_wins"],
        "history_2022_losses": raw["modal_losses"],
        "ties": raw["ties"],
        "wilcoxon_p": raw["wilcoxon_p"],
        "sign_two_sided_p": raw["sign_two_sided_p"],
    }


def paired_tests(train: pd.DataFrame, representation: pd.DataFrame, selected: pd.DataFrame) -> dict[str, dict[str, Any]]:
    tests = {
        "train_prediction_loss_lower": history_paired_summary(
            train["history_2025_train_pred"], train["history_2022_train_pred"], alternative="less"
        )
    }
    wide = representation.pivot(index=["ticker", "month"], columns="arm")
    for column, alternative in (
        ("effective_rank_ratio", "greater"),
        ("max_pc_var_ratio", "less"),
        ("prediction_to_persistence_ratio_mean", "less"),
        ("prediction_to_persistence_ratio_median", "less"),
        ("prediction_beats_persistence_rate", "greater"),
    ):
        tests[f"representation_{column}"] = history_paired_summary(
            wide[column]["history_2025"], wide[column]["history_2022"], alternative=alternative
        )
    selected = selected.copy()
    metric_cols = ("test_profit_factor", "test_pnl_return", "test_win_rate", "test_max_drawdown")
    for column in metric_cols:
        selected[column] = pd.to_numeric(selected[column], errors="coerce").fillna(0.0)
    selected_wide = selected.pivot(index=["ticker", "month"], columns="arm")
    for column in metric_cols:
        tests[f"downstream_{column}"] = history_paired_summary(
            selected_wide[column]["history_2025"], selected_wide[column]["history_2022"], alternative="greater"
        )
    return tests


def render_report(summary: dict, metrics_frame: pd.DataFrame, tests: dict) -> str:
    overall = metrics_frame[metrics_frame["scope"] == "overall"].set_index("arm")
    ticker = metrics_frame[metrics_frame["scope"] == "ticker"]
    lines = [
        "# Phys-TD-JEPA flat — historia 2022 vs 2025",
        "",
        "## Decisión",
        "",
        summary["decision"]["reason"],
        "",
        "Junio de 2026 permaneció físicamente ausente. La comparación usa executable_quote ask→bid y nested walk-forward runtime-equivalente.",
        "",
        "## Métricas agregadas",
        "",
        "| Arm | Trades | WR | PF | PnL (R) | Max DD | Gate ticker×mes |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for arm in ARMS:
        row = overall.loc[arm]
        gate = summary["acceptance_gates"][arm]
        lines.append(
            f"| {arm} | {int(row.trades)} | {row.win_rate:.3%} | {row.profit_factor:.3f} | "
            f"{row.pnl_return:+.3f} | {row.max_drawdown:.3f} | {gate['passed_cells']}/{gate['total_cells']} |"
        )
    lines.extend(["", "## Por ticker", "", "| Arm | Ticker | Trades | WR | PF | PnL (R) | Min trades/mes | Meses positivos |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for row in ticker.itertuples(index=False):
        lines.append(
            f"| {row.arm} | {row.ticker} | {int(row.trades)} | {row.win_rate:.3%} | {row.profit_factor:.3f} | "
            f"{row.pnl_return:+.3f} | {int(row.min_month_trades)} | {row.positive_month_rate:.0%} |"
        )
    lines.extend(["", "## Evidencia pareada", "", "| Métrica | Wins 2022 | p Wilcoxon | Mediana 2022-2025 |", "| --- | ---: | ---: | ---: |"])
    for name in (
        "representation_prediction_to_persistence_ratio_mean",
        "representation_prediction_beats_persistence_rate",
        "downstream_test_profit_factor",
        "downstream_test_pnl_return",
    ):
        test = tests[name]
        lines.append(
            f"| {name} | {test['history_2022_wins']}/{test['cells']} | {test['wilcoxon_p']:.6f} | "
            f"{test['median_difference_history_2022_minus_history_2025']:+.6f} |"
        )
    bootstrap = summary["daily_pnl_bootstrap"]
    lines.extend(
        [
            "",
            f"Bootstrap diario 2022-2025: observado {bootstrap['observed_pnl_difference_history_2022_minus_history_2025']:+.3f}R, "
            f"IC95% [{bootstrap['ci95'][0]:+.3f}, {bootstrap['ci95'][1]:+.3f}], "
            f"P(diff>0)={bootstrap['probability_difference_positive']:.3f}.",
            "",
            "La decisión exige mejora simultánea de representación y downstream; el PnL agregado por sí solo no selecciona el arm.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare flat Phys-TD-JEPA encoders trained from 2025 versus 2022.")
    parser.add_argument("--recent-encoder-dir", required=True)
    parser.add_argument("--long-encoder-dir", required=True)
    parser.add_argument("--recent-walkforward-dir", required=True)
    parser.add_argument("--long-walkforward-dir", required=True)
    parser.add_argument("--experiment-config", required=True)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--evaluation-months", nargs="+", default=list(DEFAULT_MONTHS))
    parser.add_argument("--bootstrap-seed", type=int, default=20260711)
    parser.add_argument("--bootstrap-resamples", type=int, default=10_000)
    args = parser.parse_args()

    months = parse_months(args.evaluation_months)
    if months != list(DEFAULT_MONTHS):
        raise RuntimeError("history comparison is frozen to 202601..202605")
    paths = {
        "history_2025_encoder": Path(args.recent_encoder_dir),
        "history_2022_encoder": Path(args.long_encoder_dir),
        "history_2025_walkforward": Path(args.recent_walkforward_dir),
        "history_2022_walkforward": Path(args.long_walkforward_dir),
        "experiment_config": Path(args.experiment_config),
        "runner": Path(args.runner),
    }
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite analysis output: {output_dir}")
    output_dir.mkdir(parents=True)

    experiment = json.loads(paths["experiment_config"].read_text(encoding="utf-8"))
    if experiment.get("declared_factor") != "encoder_training_history_start" or not experiment.get("june_2026_sealed"):
        raise RuntimeError("invalid or unsealed experiment declaration")
    for arm in ARMS:
        data = Path(experiment["arms"][arm]["data_path"])
        if sha256_file(data) != experiment["arms"][arm]["data_sha256"]:
            raise RuntimeError(f"{arm} dataset hash mismatch")
        paths[f"{arm}_data"] = data

    metas = {arm: json.loads((paths[f"{arm}_encoder"] / "metadata.json").read_text(encoding="utf-8")) for arm in ARMS}
    config_comparison = compare_encoder_configs(metas["history_2025"], metas["history_2022"])
    write_json(output_dir / "config_comparison.json", config_comparison)
    train = load_train_comparison(paths)
    train.to_csv(output_dir / "train_fold_comparison.csv", index=False)

    representation = pd.concat(
        [
            representation_by_cell(paths[f"{arm}_encoder"] / "oof_event_phys_td_jepa_features.parquet", months, arm)
            for arm in ARMS
        ],
        ignore_index=True,
    )
    representation.to_csv(output_dir / "representation_ticker_month.csv", index=False)

    selected_frames = []
    trade_frames: dict[str, pd.DataFrame] = {}
    provenance: dict[str, dict] = {}
    metric_frames = []
    for arm in ARMS:
        selected, trades, arm_provenance = validate_walkforward_contract(paths[f"{arm}_walkforward"], months, arm)
        selected_frames.append(selected.assign(arm=arm))
        trade_frames[arm] = trades
        provenance[arm] = arm_provenance
        metric_frames.append(metric_rows(trades, months, arm))
    selected_all = pd.concat(selected_frames, ignore_index=True)
    selected_all.to_csv(output_dir / "downstream_selected_folds.csv", index=False)
    metrics_all = pd.concat(metric_frames, ignore_index=True)
    metrics_all.to_csv(output_dir / "downstream_metrics.csv", index=False)

    tests = paired_tests(train, representation, selected_all)
    write_json(output_dir / "paired_tests.json", tests)
    raw_bootstrap = daily_bootstrap(
        trade_frames["history_2025"], trade_frames["history_2022"], args.bootstrap_seed, args.bootstrap_resamples
    )
    bootstrap = {
        **{key: value for key, value in raw_bootstrap.items() if key != "observed_pnl_difference_modal_minus_flat"},
        "observed_pnl_difference_history_2022_minus_history_2025": raw_bootstrap[
            "observed_pnl_difference_modal_minus_flat"
        ],
    }
    gates = {arm: acceptance_gate(metrics_all, arm) for arm in ARMS}

    ratio = tests["representation_prediction_to_persistence_ratio_mean"]
    beats = tests["representation_prediction_beats_persistence_rate"]
    pf = tests["downstream_test_profit_factor"]
    pnl = tests["downstream_test_pnl_return"]
    representation_support = ratio["history_2022_wins"] >= 8 and ratio["wilcoxon_p"] < 0.05 and beats[
        "history_2022_wins"
    ] >= 8 and beats["wilcoxon_p"] < 0.05
    downstream_support = (
        pf["history_2022_wins"] >= 8
        and pf["wilcoxon_p"] < 0.05
        and pnl["history_2022_wins"] >= 8
        and pnl["wilcoxon_p"] < 0.05
        and bootstrap["ci95"][0] > 0.0
    )
    reproducible_improvement = bool(representation_support and downstream_support)
    candidate_passes = bool(gates["history_2022"]["passed"])
    decision = {
        "history_2022_improves_reproducibly": reproducible_improvement,
        "history_2022_passes_all_gates": candidate_passes,
        "continue_from_history_2022": bool(reproducible_improvement),
        "representation_support": bool(representation_support),
        "downstream_support": bool(downstream_support),
        "reason": (
            "History 2022 improves representation and downstream reproducibly and may justify one predeclared follow-up."
            if reproducible_improvement
            else "History 2022 does not improve representation and downstream simultaneously; reject this history extension."
        ),
    }

    input_files = {
        "experiment_config": paths["experiment_config"],
        "runner": paths["runner"],
    }
    for arm in ARMS:
        input_files.update(
            {
                f"{arm}_data": paths[f"{arm}_data"],
                f"{arm}_encoder_metadata": paths[f"{arm}_encoder"] / "metadata.json",
                f"{arm}_encoder_fold_configs": paths[f"{arm}_encoder"] / "fold_configs.csv",
                f"{arm}_encoder_oof_features": paths[f"{arm}_encoder"] / "oof_event_phys_td_jepa_features.parquet",
                f"{arm}_selected_folds": paths[f"{arm}_walkforward"] / "selected_folds.csv",
                f"{arm}_trades": paths[f"{arm}_walkforward"] / "event_option_profile_trades.csv",
                f"{arm}_provenance": paths[f"{arm}_walkforward"] / "policy_selection_provenance.json",
            }
        )
    hashes = artifact_hashes(input_files)
    write_json(output_dir / "input_artifact_hashes.json", hashes)
    summary = {
        "schema_version": 1,
        "declared_factor": "encoder_training_history_start",
        "evaluation_months": months,
        "seed": 20260618,
        "bootstrap_seed": args.bootstrap_seed,
        "dataset_contract": "executable_quote_ask_to_bid",
        "config_comparison": config_comparison,
        "provenance_passed": {arm: bool(provenance[arm]["passed"]) for arm in ARMS},
        "acceptance_gates": gates,
        "daily_pnl_bootstrap": bootstrap,
        "decision": decision,
    }
    write_json(output_dir / "summary.json", summary)
    (output_dir / "REPORT.md").write_text(render_report(summary, metrics_all, tests), encoding="utf-8")
    print(json.dumps(json_safe(summary), indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
