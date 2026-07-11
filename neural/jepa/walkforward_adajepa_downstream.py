from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

if __package__:
    from .evaluate_adajepa_shadow_adapter import export_live_adapter_features
    from .evaluate_xinput_level_filter import month_range
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
    from evaluate_adajepa_shadow_adapter import export_live_adapter_features
    from evaluate_xinput_level_filter import month_range
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


def prepare_raw(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    work["ticker"] = work["ticker"].astype(str).str.upper()
    work["date"] = work["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    work["month"] = work["date"].str[:6]
    if int(work["date"].astype(int).max()) >= 20260601:
        raise ValueError("June 2026 seal violated")
    if set(work["ticker"]) != set(TICKERS):
        raise ValueError("unexpected tickers")
    if set(work["option_price_mode"].astype(str)) != {"executable_quote"}:
        raise ValueError("source is not executable_quote")
    if set(work["expiry_mode"].astype(str)) != {"zero_dte"} or set(pd.to_numeric(work["dte_days"])) != {0}:
        raise ValueError("source is not exclusively zero_dte")
    minute = pd.to_numeric(work["minute"], errors="raise").astype(int)
    if minute.min() < 630 or minute.max() > 870 or not ((minute - 600) % 5 == 0).all():
        raise ValueError("source violates entry grid")
    if work.duplicated(["ticker", "date", "minute"]).any():
        raise ValueError("raw source has duplicate ticker/date/minute rows")
    return work


def join_live_features(raw: pd.DataFrame, live_features: pd.DataFrame) -> pd.DataFrame:
    features = live_features.copy()
    features["date"] = features["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    if features.duplicated(["ticker", "date", "minute"]).any():
        raise ValueError("AdaJEPA live features contain duplicate keys")
    feature_cols = [column for column in features.columns if column.startswith("ada_")]
    joined = raw.merge(
        features[["ticker", "date", "minute", *feature_cols]],
        on=["ticker", "date", "minute"],
        how="inner",
        validate="one_to_one",
    )
    if joined.empty:
        raise ValueError("AdaJEPA live feature join is empty")
    return joined


def build_action_frame(frame: pd.DataFrame, representation_arm: str) -> tuple[pd.DataFrame, list[str]]:
    if representation_arm not in {"frozen", "adapted"}:
        raise ValueError(f"unexpected representation arm: {representation_arm}")
    z_source = [f"ada_z_{index:02d}" for index in range(32)]
    dz_source = [f"ada_{representation_arm}_dz_{index:02d}" for index in range(32)]
    pieces = []
    for ticker in TICKERS:
        delta = DELTA_BY_TICKER[ticker]
        source = frame[frame["ticker"].eq(ticker)].copy()
        availability = np.ones(len(source), dtype=bool)
        for side in ("call", "put"):
            availability &= pd.to_numeric(source[f"{side}_d{delta}_available"], errors="coerce").eq(1).to_numpy()
        source = source.loc[availability].copy()
        for side in ("call", "put"):
            part = source.copy()
            part["action"] = side.upper()
            part["action_call"] = float(side == "call")
            part["target_return"] = pd.to_numeric(part[f"{side}_d{delta}_opt_exit_ret"], errors="raise")
            part["exit_minutes"] = pd.to_numeric(part[f"{side}_d{delta}_opt_exit_minutes"], errors="raise")
            for index, column in enumerate(z_source):
                part[f"rep_z_{index:02d}"] = pd.to_numeric(part[column], errors="raise")
            for index, column in enumerate(dz_source):
                part[f"rep_dz_{index:02d}"] = pd.to_numeric(part[column], errors="raise")
            for suffix in CONTRACT_SUFFIXES:
                values = pd.to_numeric(part[f"{side}_d{delta}_{suffix}"], errors="coerce")
                if suffix in {"oi", "volume"}:
                    values = np.log1p(values.clip(lower=0))
                part[f"contract_{suffix}"] = values
            pieces.append(part)
    output = pd.concat(pieces, ignore_index=True)
    if float(pd.to_numeric(output["exit_minutes"], errors="raise").min()) < 30.0:
        raise ValueError("downstream label violates minimum 30-minute hold")
    output["event_id"] = pd.factorize(
        output["ticker"].astype(str) + ":" + output["date"].astype(str) + ":" + output["minute"].astype(str)
    )[0]
    output["minute_fraction"] = (pd.to_numeric(output["minute"]) - 630.0) / 240.0
    output["delta_fraction"] = pd.to_numeric(output["ticker"].map(DELTA_BY_TICKER)) / 100.0
    for ticker in TICKERS:
        output[f"ticker_{ticker}"] = output["ticker"].eq(ticker).astype(float)
    features = [
        *[f"rep_z_{index:02d}" for index in range(32)],
        *[f"rep_dz_{index:02d}" for index in range(32)],
        *[f"contract_{suffix}" for suffix in CONTRACT_SUFFIXES],
        "action_call",
        "minute_fraction",
        "delta_fraction",
        *[f"ticker_{ticker}" for ticker in TICKERS],
    ]
    forbidden = ("target", "error", "future", "pnl", "return", "outcome", "exit")
    leaked = [column for column in features if any(token in column.lower() for token in forbidden)]
    if leaked:
        raise RuntimeError(f"outcome-like downstream features: {leaked}")
    return output.sort_values(["month", "ticker", "date", "minute", "action"]).reset_index(drop=True), features


def main() -> int:
    parser = argparse.ArgumentParser(description="Nested frozen-vs-adapted AdaJEPA downstream payoff comparison.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--spaces-dir", required=True)
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
    parser.add_argument("--adapter-learning-rate", type=float, default=0.05)
    parser.add_argument("--adapter-grad-clip", type=float, default=1.0)
    parser.add_argument("--adapter-max-parameter-norm", type=float, default=0.5)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    parser.add_argument("--seed", type=int, default=20260618)
    parser.add_argument("--deterministic", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    arm_dirs = {arm: output_dir / arm for arm in ("frozen", "adapted")}
    for directory in arm_dirs.values():
        ensure_output_dirs(directory)
    raw_path = Path(args.data)
    raw = prepare_raw(pd.read_parquet(raw_path))
    manifest_path = Path(args.spaces_dir) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    months = month_range(args.start_month, args.end_month)
    all_trades: dict[str, list[pd.DataFrame]] = {arm: [] for arm in arm_dirs}
    all_folds: dict[str, list[dict[str, Any]]] = {arm: [] for arm in arm_dirs}
    all_diagnostics: dict[str, list[dict[str, Any]]] = {arm: [] for arm in arm_dirs}
    all_grids: dict[str, list[pd.DataFrame]] = {arm: [] for arm in arm_dirs}

    for fold in manifest:
        month = str(fold["test_month"])
        transitions = pd.read_parquet(fold["transitions_path"])
        live = export_live_adapter_features(
            transitions,
            learning_rate=args.adapter_learning_rate,
            grad_clip=args.adapter_grad_clip,
            max_parameter_norm=args.adapter_max_parameter_norm,
            device=args.device,
        )
        joined = join_live_features(raw[raw["month"].le(month)], live)
        frames = {arm: build_action_frame(joined, arm) for arm in arm_dirs}
        frozen_keys = frames["frozen"][0][["ticker", "date", "minute", "action", "target_return", "exit_minutes"]]
        adapted_keys = frames["adapted"][0][["ticker", "date", "minute", "action", "target_return", "exit_minutes"]]
        if not frozen_keys.equals(adapted_keys):
            raise RuntimeError("frozen/adapted downstream rows or labels differ")
        for arm in arm_dirs:
            frame, features = frames[arm]
            trades, folds, diagnostics, grids = run_fold(
                frame, features, "deterministic", month, arm_dirs[arm], args
            )
            for row in folds:
                row["representation_arm"] = arm
                row["arm"] = arm
            if not trades.empty:
                trades = trades.copy()
                trades["arm"] = arm
                all_trades[arm].append(trades)
            all_folds[arm].extend(folds)
            all_diagnostics[arm].extend(diagnostics)
            if not grids.empty:
                grids["representation_arm"] = arm
                all_grids[arm].append(grids)
        print(f"[ADAJEPA_DOWNSTREAM] month={month}", flush=True)

    summaries = {}
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
    decision = {
        "adapted_meets_full_ticker_gate": all(
            float(summaries["adapted"]["tickers"][ticker]["profit_factor"]) >= 1.3
            and float(summaries["adapted"]["tickers"][ticker]["win_rate"]) >= 0.5
            and int(summaries["adapted"]["tickers"][ticker]["min_month_trades"]) >= 18
            and float(summaries["adapted"]["tickers"][ticker]["positive_month_rate"]) >= 1.0
            for ticker in TICKERS
        ),
        "production_live_ready": False,
    }
    write_json(
        output_dir / "summary.json",
        {
            "schema_version": 1,
            "single_factor": "frozen_dz_vs_causally_adapted_dz",
            "data_sha256": sha256_file(raw_path),
            "spaces_manifest_sha256": sha256_file(manifest_path),
            "args": vars(args),
            "arms": summaries,
            "decision": decision,
            "june_2026_sealed": True,
            "target_z_used_as_feature": False,
        },
    )
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
