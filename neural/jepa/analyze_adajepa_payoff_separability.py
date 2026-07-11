from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import torch

if __package__:
    from .evaluate_adajepa_shadow_adapter import latent_columns
    from .evaluate_xinput_level_filter import month_add
    from .walkforward_adajepa_downstream import build_action_frame, join_live_features, prepare_raw
    from .walkforward_event_option_portfolio_var_jepa import (
        DAILY_CAPS,
        DELTA_BY_TICKER,
        TICKERS,
        DeterministicPayoffHead,
        Preprocessor,
        choose_action,
        predict_actions,
        sha256_file,
    )
else:
    from evaluate_adajepa_shadow_adapter import latent_columns
    from evaluate_xinput_level_filter import month_add
    from walkforward_adajepa_downstream import build_action_frame, join_live_features, prepare_raw
    from walkforward_event_option_portfolio_var_jepa import (
        DAILY_CAPS,
        DELTA_BY_TICKER,
        TICKERS,
        DeterministicPayoffHead,
        Preprocessor,
        choose_action,
        predict_actions,
        sha256_file,
    )


def _fast_day_features(
    day: pd.DataFrame,
    *,
    learning_rate: float,
    grad_clip: float,
    max_parameter_norm: float,
) -> pd.DataFrame:
    ordered = day.sort_values(["timestamp", "target_timestamp"], kind="stable").reset_index(drop=True)
    z_cols = latent_columns(ordered, "z_t_")
    pred_cols = latent_columns(ordered, "pred_z_")
    target_cols = latent_columns(ordered, "target_z_")
    z = ordered[z_cols].to_numpy(dtype=np.float32)
    base = ordered[pred_cols].to_numpy(dtype=np.float32)
    target = ordered[target_cols].to_numpy(dtype=np.float32)
    motion = base - z
    adapted = np.empty_like(base)
    norms = np.empty(len(ordered), dtype=np.float32)
    rollbacks = np.zeros(len(ordered), dtype=np.int64)
    scale = np.zeros(len(z_cols), dtype=np.float32)
    bias = np.zeros(len(z_cols), dtype=np.float32)
    rollback_count = 0
    available = pd.to_datetime(ordered["target_available_after_timestamp"]).to_numpy()
    timestamps = pd.to_datetime(ordered["timestamp"]).to_numpy()
    for index in range(len(ordered)):
        if index:
            if available[index - 1] > timestamps[index]:
                raise RuntimeError("attempted fast adaptation before target became observable")
            previous_scale = scale.copy()
            previous_bias = bias.copy()
            previous_prediction = base[index - 1] + scale * motion[index - 1] + bias
            residual = previous_prediction - target[index - 1]
            grad_scale = (2.0 / len(z_cols)) * residual * motion[index - 1]
            grad_bias = (2.0 / len(z_cols)) * residual
            total_grad_norm = float(np.sqrt(np.square(grad_scale).sum() + np.square(grad_bias).sum()))
            clip_coefficient = min(1.0, float(grad_clip) / (total_grad_norm + 1e-6))
            scale = scale - np.float32(learning_rate * clip_coefficient) * grad_scale
            bias = bias - np.float32(learning_rate * clip_coefficient) * grad_bias
            parameter_norm = float(np.sqrt(np.square(scale).sum() + np.square(bias).sum()))
            if not math.isfinite(parameter_norm) or parameter_norm > float(max_parameter_norm):
                scale = previous_scale
                bias = previous_bias
                rollback_count += 1
        adapted[index] = base[index] + scale * motion[index] + bias
        norms[index] = np.sqrt(np.square(scale).sum() + np.square(bias).sum())
        rollbacks[index] = rollback_count
    output = ordered[
        ["ticker", "trade_date", "expiration", "expiry_mode", "timestamp", "time", "minute"]
    ].copy()
    output["updates_before_prediction"] = np.arange(len(output), dtype=np.int64)
    output["rollbacks_before_prediction"] = rollbacks
    output["adapter_parameter_norm"] = norms
    arrays = np.concatenate([z, motion, adapted - z], axis=1)
    vector_cols = [
        *[f"ada_z_{index:02d}" for index in range(len(z_cols))],
        *[f"ada_frozen_dz_{index:02d}" for index in range(len(z_cols))],
        *[f"ada_adapted_dz_{index:02d}" for index in range(len(z_cols))],
    ]
    return pd.concat([output.reset_index(drop=True), pd.DataFrame(arrays, columns=vector_cols)], axis=1)


def fast_export_live_adapter_features(
    frame: pd.DataFrame,
    *,
    learning_rate: float,
    grad_clip: float,
    max_parameter_norm: float,
) -> pd.DataFrame:
    work = frame.copy()
    work["trade_date"] = work["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    if int(work["trade_date"].astype(int).max()) >= 20260601:
        raise ValueError("June 2026 seal violated")
    outputs = [
        _fast_day_features(
            day,
            learning_rate=learning_rate,
            grad_clip=grad_clip,
            max_parameter_norm=max_parameter_norm,
        )
        for _, day in work.groupby(["ticker", "trade_date"], sort=True)
    ]
    if not outputs:
        return pd.DataFrame()
    result = pd.concat(outputs, ignore_index=True)
    vector_cols = sorted(column for column in result if column.startswith("ada_"))
    causal_cols = [column for column in result if column not in vector_cols]
    return result[[*causal_cols, *vector_cols]].copy()


def load_model_artifact(path: Path, expected_sha256: str) -> tuple[DeterministicPayoffHead, Preprocessor, int]:
    actual_hash = sha256_file(path)
    if actual_hash != str(expected_sha256).upper():
        raise RuntimeError(f"model hash mismatch for {path}: {actual_hash} != {expected_sha256}")
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    if payload.get("arm") != "deterministic":
        raise RuntimeError(f"unexpected payoff artifact arm: {payload.get('arm')}")
    config = payload["model_config"]
    model = DeterministicPayoffHead(
        input_dim=int(config["input_dim"]),
        hidden_dim=int(config["hidden_dim"]),
        latent_dim=int(config["latent_dim"]),
        dropout=float(config["dropout"]),
    )
    model.load_state_dict(payload["state_dict"], strict=True)
    model.eval()
    raw = payload["preprocessor"]
    preprocessor = Preprocessor(
        features=list(raw["features"]),
        medians=np.asarray(raw["medians"], dtype=np.float32),
        means=np.asarray(raw["means"], dtype=np.float32),
        scales=np.asarray(raw["scales"], dtype=np.float32),
    )
    return model, preprocessor, int(config["latent_dim"])


def exact_label_actions(raw: pd.DataFrame) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for ticker in TICKERS:
        delta = DELTA_BY_TICKER[ticker]
        source = raw[raw["ticker"].eq(ticker)].copy()
        availability = np.ones(len(source), dtype=bool)
        for side in ("call", "put"):
            availability &= pd.to_numeric(source[f"{side}_d{delta}_available"], errors="coerce").eq(1).to_numpy()
        source = source.loc[availability].copy()
        for side in ("call", "put"):
            part = source[["ticker", "date", "month", "minute"]].copy()
            part["action"] = side.upper()
            part["target_return"] = pd.to_numeric(
                source[f"{side}_d{delta}_opt_exit_ret"], errors="raise"
            ).to_numpy()
            part["exit_minutes"] = pd.to_numeric(
                source[f"{side}_d{delta}_opt_exit_minutes"], errors="raise"
            ).to_numpy()
            pieces.append(part)
    result = pd.concat(pieces, ignore_index=True)
    if float(result["exit_minutes"].min()) < 30.0:
        raise RuntimeError("label audit encountered a hold below 30 minutes")
    return result


def profit_factor(values: pd.Series | np.ndarray) -> float:
    array = np.asarray(values, dtype=float)
    gains = float(array[array > 0.0].sum())
    losses = float(-array[array < 0.0].sum())
    if losses == 0.0:
        return float("inf") if gains > 0.0 else float("nan")
    return gains / losses


def _return_metrics(values: pd.Series | np.ndarray, prefix: str) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    return {
        f"{prefix}_mean_return": float(array.mean()),
        f"{prefix}_win_rate": float((array > 0.0).mean()),
        f"{prefix}_profit_factor": float(profit_factor(array)),
    }


def decompose_ticker_month(
    scored_actions: pd.DataFrame,
    ticker: str,
    month: str,
    constant_action: str,
    arm: str,
) -> dict[str, Any]:
    actions = scored_actions[scored_actions["ticker"].eq(ticker)].copy()
    if actions.empty or actions.groupby("event_id").size().ne(2).any():
        raise RuntimeError(f"incomplete action pairs for {ticker}/{month}/{arm}")
    chosen = choose_action(actions).set_index("event_id")
    actual = actions.pivot(index="event_id", columns="action", values="target_return")
    predicted = actions.pivot(index="event_id", columns="action", values="pred_return")
    actual = actual.loc[chosen.index]
    predicted = predicted.loc[chosen.index]
    oracle_action = np.where(actual["CALL"].to_numpy() >= actual["PUT"].to_numpy(), "CALL", "PUT")
    oracle_return = actual.max(axis=1).to_numpy(dtype=float)
    chosen_return = chosen["realized_return"].to_numpy(dtype=float)
    constant_return = actual[str(constant_action)].to_numpy(dtype=float)
    chosen_score = chosen["score"].to_numpy(dtype=float)
    action_actual = actions["target_return"].to_numpy(dtype=float)
    action_predicted = actions["pred_return"].to_numpy(dtype=float)
    score_return_spearman = pd.Series(chosen_score).corr(pd.Series(chosen_return), method="spearman")
    return {
        "arm": arm,
        "ticker": ticker,
        "month": month,
        "events": int(len(chosen)),
        "daily_cap": int(DAILY_CAPS[ticker]),
        "constant_train_action": str(constant_action),
        "head_side_accuracy": float((chosen["action"].to_numpy() == oracle_action).mean()),
        "constant_side_accuracy": float((np.repeat(str(constant_action), len(chosen)) == oracle_action).mean()),
        "mean_side_regret": float(np.mean(oracle_return - chosen_return)),
        "median_side_regret": float(np.median(oracle_return - chosen_return)),
        "action_mae": float(np.mean(np.abs(action_predicted - np.clip(action_actual, -2.0, 2.0)))),
        "action_rmse": float(np.sqrt(np.mean(np.square(action_predicted - np.clip(action_actual, -2.0, 2.0))))),
        "chosen_score_return_spearman": float(score_return_spearman) if pd.notna(score_return_spearman) else float("nan"),
        "exactly_one_side_positive_rate": float(((actual > 0.0).sum(axis=1) == 1).mean()),
        "both_sides_positive_rate": float(((actual > 0.0).sum(axis=1) == 2).mean()),
        "neither_side_positive_rate": float(((actual > 0.0).sum(axis=1) == 0).mean()),
        **_return_metrics(chosen_return, "head"),
        **_return_metrics(constant_return, "constant"),
        **_return_metrics(oracle_return, "oracle_side"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit exact-bucket payoff side separability without policy selection.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--spaces-dir", required=True)
    parser.add_argument("--downstream-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--adapter-learning-rate", type=float, default=0.05)
    parser.add_argument("--adapter-grad-clip", type=float, default=1.0)
    parser.add_argument("--adapter-max-parameter-norm", type=float, default=0.5)
    parser.add_argument("--infer-batch-size", type=int, default=4096)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    data_path = Path(args.data)
    spaces_dir = Path(args.spaces_dir)
    downstream_dir = Path(args.downstream_dir)
    raw = prepare_raw(pd.read_parquet(data_path))
    labels = exact_label_actions(raw)
    manifest_path = spaces_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    folds_by_arm = {
        arm: pd.read_csv(downstream_dir / arm / "selected_folds.csv") for arm in ("frozen", "adapted")
    }
    records: list[dict[str, Any]] = []
    artifact_rows: list[dict[str, Any]] = []
    for fold in manifest:
        month = str(fold["test_month"])
        if month > "202605":
            raise RuntimeError("June 2026 seal violated by manifest")
        test_transitions = pd.read_parquet(fold["transitions_path"])
        test_transitions["trade_date"] = test_transitions["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
        test_transitions = test_transitions[test_transitions["trade_date"].str[:6].eq(month)].copy()
        live = fast_export_live_adapter_features(
            test_transitions,
            learning_rate=args.adapter_learning_rate,
            grad_clip=args.adapter_grad_clip,
            max_parameter_norm=args.adapter_max_parameter_norm,
        )
        joined = join_live_features(raw[raw["month"].eq(month)], live)
        first_validation_month = month_add(month, -3)
        train_labels = labels[labels["month"].astype(str) < first_validation_month]
        constant_actions = (
            train_labels.groupby(["ticker", "action"])["target_return"].mean().unstack("action").idxmax(axis=1).to_dict()
        )
        for arm in ("frozen", "adapted"):
            action_frame, _ = build_action_frame(joined, arm)
            fold_rows = folds_by_arm[arm]
            month_rows = fold_rows[fold_rows["month"].astype(str).eq(month)]
            if len(month_rows) != len(TICKERS):
                raise RuntimeError(f"missing fold metadata for {arm}/{month}")
            hashes = month_rows["model_artifact_sha256"].astype(str).unique()
            if len(hashes) != 1:
                raise RuntimeError(f"non-shared model hashes for {arm}/{month}")
            model_path = downstream_dir / arm / "fold_model_artifacts" / f"payoff_head_{month}.pt"
            model, preprocessor, latent_dim = load_model_artifact(model_path, hashes[0])
            scored_actions, _ = predict_actions(
                model,
                preprocessor,
                action_frame,
                SimpleNamespace(device="cpu", infer_batch_size=args.infer_batch_size, latent_dim=latent_dim),
            )
            for ticker in TICKERS:
                records.append(
                    decompose_ticker_month(
                        scored_actions,
                        ticker=ticker,
                        month=month,
                        constant_action=str(constant_actions[ticker]),
                        arm=arm,
                    )
                )
            artifact_rows.append(
                {
                    "arm": arm,
                    "month": month,
                    "model_path": str(model_path),
                    "model_sha256": hashes[0],
                    "test_transition_sha256": fold["transitions_sha256"],
                    "test_rows": int(len(test_transitions)),
                }
            )
        print(f"[PAYOFF_SEPARABILITY] month={month} rows={len(test_transitions)}", flush=True)
    cells = pd.DataFrame(records).sort_values(["arm", "ticker", "month"]).reset_index(drop=True)
    artifacts = pd.DataFrame(artifact_rows).sort_values(["arm", "month"]).reset_index(drop=True)
    arm_summary: dict[str, Any] = {}
    for arm, part in cells.groupby("arm"):
        arm_summary[str(arm)] = {
            "cells": int(len(part)),
            "median_head_side_accuracy": float(part["head_side_accuracy"].median()),
            "head_beats_constant_side_cells": int((part["head_side_accuracy"] > part["constant_side_accuracy"]).sum()),
            "median_head_minus_constant_mean_return": float(
                (part["head_mean_return"] - part["constant_mean_return"]).median()
            ),
            "head_mean_return_beats_constant_cells": int((part["head_mean_return"] > part["constant_mean_return"]).sum()),
            "median_oracle_side_headroom": float((part["oracle_side_mean_return"] - part["head_mean_return"]).median()),
            "median_score_return_spearman": float(part["chosen_score_return_spearman"].median()),
            "median_exactly_one_side_positive_rate": float(part["exactly_one_side_positive_rate"].median()),
        }
    frozen = cells[cells["arm"].eq("frozen")].sort_values(["ticker", "month"]).reset_index(drop=True)
    adapted = cells[cells["arm"].eq("adapted")].sort_values(["ticker", "month"]).reset_index(drop=True)
    if not frozen[["ticker", "month", "events"]].equals(adapted[["ticker", "month", "events"]]):
        raise RuntimeError("frozen/adapted diagnostic cells are not paired")
    summary = {
        "schema_version": 1,
        "diagnostic_only_no_policy_selection": True,
        "data_sha256": sha256_file(data_path),
        "spaces_manifest_sha256": sha256_file(manifest_path),
        "downstream_summary_sha256": sha256_file(downstream_dir / "summary.json"),
        "arms": arm_summary,
        "adapted_minus_frozen": {
            "median_side_accuracy": float((adapted["head_side_accuracy"] - frozen["head_side_accuracy"]).median()),
            "side_accuracy_wins": int((adapted["head_side_accuracy"] > frozen["head_side_accuracy"]).sum()),
            "median_mean_return": float((adapted["head_mean_return"] - frozen["head_mean_return"]).median()),
            "mean_return_wins": int((adapted["head_mean_return"] > frozen["head_mean_return"]).sum()),
            "median_score_return_spearman": float(
                (adapted["chosen_score_return_spearman"] - frozen["chosen_score_return_spearman"]).median()
            ),
        },
        "args": vars(args),
        "june_2026_sealed": True,
        "production_live_ready": False,
    }
    cells.to_csv(output_dir / "ticker_month_decomposition.csv", index=False)
    artifacts.to_csv(output_dir / "artifact_manifest.csv", index=False)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8"
    )
    print(json.dumps(summary["adapted_minus_frozen"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
