from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

if __package__:
    from .evaluate_xinput_level_filter import month_range
    from .walkforward_adajepa_downstream import prepare_raw
    from .walkforward_event_option_portfolio_var_jepa import (
        TICKERS,
        build_provenance,
        ensure_output_dirs,
        run_fold,
        sha256_file,
        summary_metrics,
        write_json,
    )
    from .walkforward_phys_td_horizon_downstream import build_action_frame, join_exact_h1_rows
else:
    from evaluate_xinput_level_filter import month_range
    from walkforward_adajepa_downstream import prepare_raw
    from walkforward_event_option_portfolio_var_jepa import (
        TICKERS,
        build_provenance,
        ensure_output_dirs,
        run_fold,
        sha256_file,
        summary_metrics,
        write_json,
    )
    from walkforward_phys_td_horizon_downstream import build_action_frame, join_exact_h1_rows


SPOT_SKIP_SOURCE = ("ret_5m_bps", "ret_15m_bps", "ret_30m_bps")
SPOT_SKIP_FEATURES = tuple(f"direct_spot_momentum_{value.split('_')[1]}_bps" for value in SPOT_SKIP_SOURCE)


def build_arm_frames(joined: pd.DataFrame) -> dict[str, tuple[pd.DataFrame, list[str]]]:
    base, control_features = build_action_frame(joined, 1)
    variant = base.copy()
    for source, destination in zip(SPOT_SKIP_SOURCE, SPOT_SKIP_FEATURES):
        if source not in variant.columns:
            raise RuntimeError(f"missing live spot skip feature: {source}")
        variant[destination] = pd.to_numeric(variant[source], errors="raise")
    if variant[list(SPOT_SKIP_FEATURES)].isna().any().any():
        raise RuntimeError("spot skip contains missing values")
    variant_features = [*control_features, *SPOT_SKIP_FEATURES]
    forbidden = ("target", "future", "pnl", "outcome", "exit")
    leaked = [feature for feature in variant_features if any(token in feature.lower() for token in forbidden)]
    if leaked:
        raise RuntimeError(f"outcome-like spot skip features: {leaked}")
    return {"control": (base, control_features), "spot_skip": (variant, variant_features)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Nested Phys-TD h1 control vs direct spot-momentum skip.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--spaces-dir", required=True)
    parser.add_argument("--horizon-manifest", required=True)
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
    parser.add_argument("--kl-weight", type=float, default=1.0)
    parser.add_argument("--kl-anneal-epochs", type=int, default=20)
    parser.add_argument("--threshold-grid", nargs="+", type=float, default=[-1e9, -0.1, -0.05, 0, 0.05, 0.1, 0.15, 0.2])
    parser.add_argument("--threshold-quantiles", nargs="+", type=float, default=[0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    parser.add_argument("--min-val-trades", type=int, default=54)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-val-pf", type=float, default=1.3)
    parser.add_argument("--min-val-win-rate", type=float, default=0.5)
    parser.add_argument("--min-val-positive-month-rate", type=float, default=1.0)
    parser.add_argument("--min-call-rate", type=float, default=0.0)
    parser.add_argument("--max-call-rate", type=float, default=1.0)
    parser.add_argument("--daily-win-weight", type=float, default=0.25)
    parser.add_argument("--top5-share-penalty", type=float, default=0.1)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    parser.add_argument("--seed", type=int, default=20260618)
    parser.add_argument("--deterministic", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    arm_dirs = {arm: output_dir / arm for arm in ("control", "spot_skip")}
    for directory in arm_dirs.values():
        ensure_output_dirs(directory)
    raw_path = Path(args.data)
    raw = prepare_raw(pd.read_parquet(raw_path))
    missing_skip = [column for column in SPOT_SKIP_SOURCE if column not in raw.columns]
    if missing_skip:
        raise RuntimeError(f"raw data missing declared spot skip: {missing_skip}")
    spaces_path = Path(args.spaces_dir) / "manifest.json"
    spaces = json.loads(spaces_path.read_text(encoding="utf-8-sig"))
    horizon_manifest_path = Path(args.horizon_manifest)
    horizon_manifest = json.loads(horizon_manifest_path.read_text(encoding="utf-8-sig"))
    horizon_by_month = {str(row["test_month"]): row for row in horizon_manifest}
    months = month_range(args.start_month, args.end_month)
    if [str(row["test_month"]) for row in spaces] != months or sorted(horizon_by_month) != months:
        raise RuntimeError("space/horizon/test fold months differ")
    all_trades: dict[str, list[pd.DataFrame]] = {arm: [] for arm in arm_dirs}
    all_folds: dict[str, list[dict[str, Any]]] = {arm: [] for arm in arm_dirs}
    all_diagnostics: dict[str, list[dict[str, Any]]] = {arm: [] for arm in arm_dirs}
    all_grids: dict[str, list[pd.DataFrame]] = {arm: [] for arm in arm_dirs}
    input_audit: list[dict[str, Any]] = []

    for fold in spaces:
        month = str(fold["test_month"])
        horizon_fold = horizon_by_month[month]
        horizon_path = Path(horizon_fold["features_path"])
        transition_path = Path(fold["transitions_path"])
        if sha256_file(horizon_path) != str(horizon_fold["features_sha256"]).upper():
            raise RuntimeError(f"horizon feature hash mismatch for {month}")
        if sha256_file(transition_path) != str(fold["transitions_sha256"]).upper():
            raise RuntimeError(f"h1 transition hash mismatch for {month}")
        joined, audit = join_exact_h1_rows(
            raw[raw["month"].le(month)], pd.read_parquet(horizon_path), pd.read_parquet(transition_path)
        )
        frames = build_arm_frames(joined)
        keys = ["ticker", "date", "minute", "action", "target_return", "exit_minutes"]
        if not frames["control"][0][keys].equals(frames["spot_skip"][0][keys]):
            raise RuntimeError("control/spot skip rows or labels differ")
        input_audit.append(
            {
                "test_month": month,
                "encoder_sha256": fold["encoder_sha256"],
                "h1_transitions_sha256": fold["transitions_sha256"],
                "horizon_features_sha256": horizon_fold["features_sha256"],
                "spot_skip_features": ",".join(SPOT_SKIP_SOURCE),
                **audit,
            }
        )
        for arm, directory in arm_dirs.items():
            frame, features = frames[arm]
            trades, folds, diagnostics, grids = run_fold(
                frame, features, "deterministic", month, directory, args
            )
            for row in folds:
                row["arm"] = arm
                row["direct_spot_skip"] = arm == "spot_skip"
            if not trades.empty:
                trades = trades.copy()
                trades["arm"] = arm
                all_trades[arm].append(trades)
            all_folds[arm].extend(folds)
            all_diagnostics[arm].extend(diagnostics)
            if not grids.empty:
                grids["arm"] = arm
                all_grids[arm].append(grids)
        print(f"[PHYS_TD_SPOT_SKIP] month={month} rows={audit['rows']}", flush=True)

    summaries: dict[str, Any] = {}
    for arm, directory in arm_dirs.items():
        folds = pd.DataFrame(all_folds[arm]).sort_values(["ticker", "month"]).reset_index(drop=True)
        trades = pd.concat(all_trades[arm], ignore_index=True) if all_trades[arm] else pd.DataFrame(columns=["ticker", "month"])
        folds.to_csv(directory / "selected_folds.csv", index=False)
        trades.to_csv(directory / "trades.csv", index=False)
        pd.DataFrame(all_diagnostics[arm]).to_csv(directory / "representation_ticker_month.csv", index=False)
        if all_grids[arm]:
            pd.concat(all_grids[arm], ignore_index=True).to_csv(directory / "candidate_validation.csv", index=False)
        provenance = build_provenance(folds, months, directory, "deterministic")
        write_json(directory / "policy_selection_provenance.json", provenance)
        if not provenance["passed"]:
            raise RuntimeError(f"provenance failed for {arm}")
        summaries[arm] = summary_metrics(trades, months, arm)
    pd.DataFrame(input_audit).to_csv(output_dir / "spot_skip_input_audit.csv", index=False)
    decision = {
        "spot_skip_meets_full_ticker_gate": all(
            float(summaries["spot_skip"]["tickers"][ticker]["profit_factor"]) >= 1.3
            and float(summaries["spot_skip"]["tickers"][ticker]["win_rate"]) >= 0.5
            and int(summaries["spot_skip"]["tickers"][ticker]["min_month_trades"]) >= 18
            and float(summaries["spot_skip"]["tickers"][ticker]["positive_month_rate"]) >= 1.0
            for ticker in TICKERS
        ),
        "production_live_ready": False,
    }
    write_json(
        output_dir / "summary.json",
        {
            "schema_version": 1,
            "single_factor": "direct_live_spot_momentum_skip_5m_15m_30m",
            "spot_skip_source_features": list(SPOT_SKIP_SOURCE),
            "data_sha256": sha256_file(raw_path),
            "spaces_manifest_sha256": sha256_file(spaces_path),
            "horizon_manifest_sha256": sha256_file(horizon_manifest_path),
            "args": vars(args),
            "arms": summaries,
            "decision": decision,
            "june_2026_sealed": True,
            "same_rows_labels_contract_folds_seeds_budget": True,
        },
    )
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
