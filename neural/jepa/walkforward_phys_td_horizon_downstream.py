from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

if __package__:
    from .evaluate_xinput_level_filter import month_range
    from .walkforward_adajepa_downstream import prepare_raw
    from .walkforward_event_option_portfolio_var_jepa import (
        CONTRACT_SUFFIXES,
        DELTA_BY_TICKER,
        TICKERS,
        build_provenance,
        ensure_output_dirs,
        run_fold,
        sha256_file,
        summary_metrics,
        write_json,
    )
else:
    from evaluate_xinput_level_filter import month_range
    from walkforward_adajepa_downstream import prepare_raw
    from walkforward_event_option_portfolio_var_jepa import (
        CONTRACT_SUFFIXES,
        DELTA_BY_TICKER,
        TICKERS,
        build_provenance,
        ensure_output_dirs,
        run_fold,
        sha256_file,
        summary_metrics,
        write_json,
    )


def join_exact_h1_rows(
    raw: pd.DataFrame,
    horizon_features: pd.DataFrame,
    h1_transitions: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float | int]]:
    keys = ["ticker", "date", "minute"]
    features = horizon_features.copy()
    features["date"] = features["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    transitions = h1_transitions.copy()
    transitions["date"] = transitions["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    for name, frame in (("horizon", features), ("h1", transitions)):
        if frame.duplicated(keys).any():
            raise RuntimeError(f"{name} features contain duplicate exact keys")
    feature_cols = [column for column in features if column.startswith("horizon_")]
    aligned = transitions[keys].merge(
        features[[*keys, *feature_cols]], on=keys, how="left", validate="one_to_one"
    )
    if aligned[feature_cols].isna().any(axis=1).any():
        raise RuntimeError("horizon export is missing an h1 transition row")
    z_diffs = []
    h1_diffs = []
    transition_lookup = transitions.set_index(keys)
    aligned_lookup = aligned.set_index(keys)
    for dimension in range(32):
        z_diffs.append(
            np.abs(
                aligned_lookup[f"horizon_z_{dimension:02d}"].to_numpy(dtype=float)
                - transition_lookup.loc[aligned_lookup.index, f"z_t_{dimension:02d}"].to_numpy(dtype=float)
            )
        )
        h1_diffs.append(
            np.abs(
                aligned_lookup[f"horizon_pred_h1_{dimension:02d}"].to_numpy(dtype=float)
                - transition_lookup.loc[aligned_lookup.index, f"pred_z_{dimension:02d}"].to_numpy(dtype=float)
            )
        )
    max_z_diff = float(np.max(np.concatenate(z_diffs)))
    max_h1_diff = float(np.max(np.concatenate(h1_diffs)))
    if max_z_diff > 1e-6 or max_h1_diff > 1e-6:
        raise RuntimeError(f"h1 feature parity failed: z={max_z_diff}, prediction={max_h1_diff}")
    joined = raw.merge(aligned, on=keys, how="inner", validate="one_to_one")
    if len(joined) != len(aligned):
        raise RuntimeError(f"raw exact join lost rows: aligned={len(aligned)}, joined={len(joined)}")
    return joined, {
        "rows": int(len(joined)),
        "max_z_parity_abs_diff": max_z_diff,
        "max_h1_prediction_parity_abs_diff": max_h1_diff,
    }


def build_action_frame(frame: pd.DataFrame, horizon: int) -> tuple[pd.DataFrame, list[str]]:
    if int(horizon) not in {1, 6}:
        raise ValueError(f"unexpected downstream horizon: {horizon}")
    pieces: list[pd.DataFrame] = []
    for ticker in TICKERS:
        delta = DELTA_BY_TICKER[ticker]
        source = frame[frame["ticker"].eq(ticker)].copy()
        availability = np.ones(len(source), dtype=bool)
        for side in ("call", "put"):
            availability &= pd.to_numeric(source[f"{side}_d{delta}_available"], errors="coerce").eq(1).to_numpy()
        source = source.loc[availability].copy()
        for side in ("call", "put"):
            part = source.copy()
            derived: dict[str, Any] = {
                "action": np.repeat(side.upper(), len(part)),
                "action_call": np.repeat(float(side == "call"), len(part)),
                "target_return": pd.to_numeric(part[f"{side}_d{delta}_opt_exit_ret"], errors="raise").to_numpy(),
                "exit_minutes": pd.to_numeric(part[f"{side}_d{delta}_opt_exit_minutes"], errors="raise").to_numpy(),
            }
            for dimension in range(32):
                z = pd.to_numeric(part[f"horizon_z_{dimension:02d}"], errors="raise").to_numpy()
                prediction = pd.to_numeric(
                    part[f"horizon_pred_h{int(horizon)}_{dimension:02d}"], errors="raise"
                ).to_numpy()
                derived[f"rep_z_{dimension:02d}"] = z
                derived[f"rep_dz_{dimension:02d}"] = prediction - z
            for suffix in CONTRACT_SUFFIXES:
                values = pd.to_numeric(part[f"{side}_d{delta}_{suffix}"], errors="coerce")
                if suffix in {"oi", "volume"}:
                    values = np.log1p(values.clip(lower=0.0))
                derived[f"contract_{suffix}"] = values.to_numpy()
            pieces.append(pd.concat([part.reset_index(drop=True), pd.DataFrame(derived)], axis=1))
    output = pd.concat(pieces, ignore_index=True)
    if float(pd.to_numeric(output["exit_minutes"], errors="raise").min()) < 30.0:
        raise ValueError("horizon downstream label violates minimum 30-minute hold")
    output["event_id"] = pd.factorize(
        output["ticker"].astype(str) + ":" + output["date"].astype(str) + ":" + output["minute"].astype(str)
    )[0]
    output["minute_fraction"] = (pd.to_numeric(output["minute"]) - 630.0) / 240.0
    output["delta_fraction"] = pd.to_numeric(output["ticker"].map(DELTA_BY_TICKER)) / 100.0
    for ticker in TICKERS:
        output[f"ticker_{ticker}"] = output["ticker"].eq(ticker).astype(float)
    features = [
        *[f"rep_z_{dimension:02d}" for dimension in range(32)],
        *[f"rep_dz_{dimension:02d}" for dimension in range(32)],
        *[f"contract_{suffix}" for suffix in CONTRACT_SUFFIXES],
        "action_call",
        "minute_fraction",
        "delta_fraction",
        *[f"ticker_{ticker}" for ticker in TICKERS],
    ]
    forbidden = ("target", "error", "future", "pnl", "return", "outcome", "exit")
    leaked = [feature for feature in features if any(token in feature.lower() for token in forbidden)]
    if leaked:
        raise RuntimeError(f"outcome-like horizon features: {leaked}")
    return output.sort_values(["month", "ticker", "date", "minute", "action"]).reset_index(drop=True), features


def main() -> int:
    parser = argparse.ArgumentParser(description="Nested Phys-TD h1-vs-h6 payoff comparison.")
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
    arm_dirs = {arm: output_dir / arm for arm in ("h1", "h6")}
    for directory in arm_dirs.values():
        ensure_output_dirs(directory)
    raw_path = Path(args.data)
    raw = prepare_raw(pd.read_parquet(raw_path))
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
            raw[raw["month"].le(month)],
            pd.read_parquet(horizon_path),
            pd.read_parquet(transition_path),
        )
        frames = {arm: build_action_frame(joined, int(arm[1:])) for arm in arm_dirs}
        keys = ["ticker", "date", "minute", "action", "target_return", "exit_minutes"]
        if not frames["h1"][0][keys].equals(frames["h6"][0][keys]):
            raise RuntimeError("h1/h6 rows or labels differ")
        input_audit.append(
            {
                "test_month": month,
                "encoder_sha256": fold["encoder_sha256"],
                "h1_transitions_sha256": fold["transitions_sha256"],
                "horizon_features_sha256": horizon_fold["features_sha256"],
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
                row["prediction_horizon_steps"] = int(arm[1:])
            if not trades.empty:
                trades = trades.copy()
                trades["arm"] = arm
                all_trades[arm].append(trades)
            all_folds[arm].extend(folds)
            all_diagnostics[arm].extend(diagnostics)
            if not grids.empty:
                grids["arm"] = arm
                all_grids[arm].append(grids)
        print(f"[PHYS_TD_HORIZON] month={month} rows={audit['rows']}", flush=True)

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
    pd.DataFrame(input_audit).to_csv(output_dir / "horizon_input_audit.csv", index=False)
    decision = {
        "h6_meets_full_ticker_gate": all(
            float(summaries["h6"]["tickers"][ticker]["profit_factor"]) >= 1.3
            and float(summaries["h6"]["tickers"][ticker]["win_rate"]) >= 0.5
            and int(summaries["h6"]["tickers"][ticker]["min_month_trades"]) >= 18
            and float(summaries["h6"]["tickers"][ticker]["positive_month_rate"]) >= 1.0
            for ticker in TICKERS
        ),
        "production_live_ready": False,
    }
    write_json(
        output_dir / "summary.json",
        {
            "schema_version": 1,
            "single_factor": "prediction_horizon_h1_5m_vs_h6_30m",
            "data_sha256": sha256_file(raw_path),
            "spaces_manifest_sha256": sha256_file(spaces_path),
            "horizon_manifest_sha256": sha256_file(horizon_manifest_path),
            "args": vars(args),
            "arms": summaries,
            "decision": decision,
            "june_2026_sealed": True,
            "same_rows_labels_contract_head_folds_seeds_budget": True,
        },
    )
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
