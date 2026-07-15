"""Expanding walk-forward development evaluator for KING-GEX-MANAGE30-V1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from neural.jepa.audit_existing_data_edge_join_inventory_v1 import ROOT, sha256_file
from neural.jepa.build_king_gex_manage30_v1 import (
    ACTION_IDS,
    DATA_GATE_CLARIFICATION,
    DATA_GATE_CLARIFICATION_SHA256,
    EXPECTED_EXECUTABLE_CANDIDATES,
    EXPECTED_SOURCE_CANDIDATES,
    FROZEN_ENTRY_REJECTIONS,
    M0_FEATURES,
    M1_FEATURES,
    PREDECLARATION,
    PREDECLARATION_SHA256,
    SNAPSHOT_CLARIFICATION,
    SNAPSHOT_CLARIFICATION_SHA256,
)
from neural.jepa.evaluate_king_gex_exit_v1 import EXIT_CONFIGS
from neural.jepa.evaluate_king_gex_slope_v1 import (
    KEY,
    MAX_TOP5_DAY_GROSS_PROFIT_SHARE,
    MAX_TOP5_TRADE_GROSS_PROFIT_SHARE,
    _concentration,
    economic_metrics,
)
from neural.jepa.existing_data_edge_scheduler_v1 import (
    SCHEDULER,
    _assert_scheduler_output,
    replay_live_equivalent,
)


EXPERIMENT = "KING_GEX_MANAGE30_V1"
ARMS = ("M0_PATH", "M1_SYNTH_GREEKS")
FEATURES_BY_ARM = {"M0_PATH": M0_FEATURES, "M1_SYNTH_GREEKS": M1_FEATURES}
DEVELOPMENT_MONTHS = tuple(f"2023{month:02d}" for month in range(1, 13))
RUN_SCHEMA = "king_gex_manage30_evaluation_run_v1"
FOLD_SCHEMA = "king_gex_manage30_fold_checkpoint_v1"
TARGET_CLIP = 2.0
SEED = 20260715
MODEL_PARAMS = {
    "objective": "huber",
    "n_estimators": 300,
    "learning_rate": 0.03,
    "num_leaves": 15,
    "min_child_samples": 100,
    "subsample": 0.85,
    "colsample_bytree": 0.80,
    "reg_lambda": 10.0,
    "random_state": SEED,
    "deterministic": True,
    "force_col_wise": True,
    "verbosity": -1,
}
USER_GATES = {
    "profit_factor_strictly_greater": 1.30,
    "win_rate_strictly_greater": 0.45,
    "trades_strictly_greater": 12,
    "pnl_strictly_greater": 0.0,
    "minimum_hold_at_least": 30.0,
}
ACTION_FEATURES = (
    "manage_stop_loss",
    "manage_trail_activation",
    "manage_trail_drawdown",
    "manage_horizon_minutes",
    "manage_is_e30",
)


def _action_specs() -> dict[str, dict[str, float]]:
    specs = {
        str(config["config_id"]): {
            "manage_stop_loss": float(config["stop_loss"]),
            "manage_trail_activation": float(config["trail_activation"]),
            "manage_trail_drawdown": float(config["trail_drawdown"]),
            "manage_horizon_minutes": float(config["horizon_minutes"]),
            "manage_is_e30": 0.0,
        }
        for config in EXIT_CONFIGS
    }
    specs["E30"] = {
        "manage_stop_loss": 0.0,
        "manage_trail_activation": 0.0,
        "manage_trail_drawdown": 0.0,
        "manage_horizon_minutes": 30.0,
        "manage_is_e30": 1.0,
    }
    if tuple([str(config["config_id"]) for config in EXIT_CONFIGS] + ["E30"]) != ACTION_IDS:
        raise AssertionError("management action order changed")
    return specs


ACTION_SPECS = _action_specs()


def _canonical_sha(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def _atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def _atomic_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def _json_finite(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_finite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_finite(item) for item in value]
    if isinstance(value, tuple):
        return [_json_finite(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(float(value)) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def protocol() -> dict[str, Any]:
    return {
        "schema": "king_gex_manage30_evaluation_protocol_v1",
        "experiment": EXPERIMENT,
        "arms": list(ARMS),
        "features": {arm: list(features) for arm, features in FEATURES_BY_ARM.items()},
        "action_features": list(ACTION_FEATURES),
        "actions": list(ACTION_IDS),
        "target": "clip(return_action-return_B00,-2,+2)",
        "B00_prediction": 0.0,
        "switch_rule": "argmax predicted advantage only when >0; otherwise B00",
        "action_availability": (
            "B00 always; non-B00 only when decision_state_available=1; "
            "inference never reads outcome columns"
        ),
        "model": MODEL_PARAMS,
        "initial_train": "202201..202212",
        "development_months": list(DEVELOPMENT_MONTHS),
        "scheduler": SCHEDULER,
        "gates": USER_GATES,
        "concentration": {
            "top5_trade_max": MAX_TOP5_TRADE_GROSS_PROFIT_SHARE,
            "top5_day_max": MAX_TOP5_DAY_GROSS_PROFIT_SHARE,
        },
        "snapshot_clarification_sha256": SNAPSHOT_CLARIFICATION_SHA256,
        "outer_2024_2025_opened": False,
        "holdout_2026_opened": False,
    }


def protocol_sha256() -> str:
    return _canonical_sha(protocol())


def _code_hashes() -> dict[str, str]:
    paths = (
        "neural/jepa/evaluate_king_gex_manage30_v1.py",
        "neural/jepa/build_king_gex_manage30_v1.py",
        "neural/jepa/existing_data_edge_scheduler_v1.py",
        "neural/jepa/evaluate_king_gex_slope_v1.py",
    )
    return {path: sha256_file(ROOT / path) for path in paths}


def _load_dataset(dataset_path: Path, summary_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    if sha256_file(PREDECLARATION) != PREDECLARATION_SHA256:
        raise AssertionError("MANAGE30 predeclaration changed")
    if sha256_file(DATA_GATE_CLARIFICATION) != DATA_GATE_CLARIFICATION_SHA256:
        raise AssertionError("MANAGE30 clarification changed")
    if sha256_file(SNAPSHOT_CLARIFICATION) != SNAPSHOT_CLARIFICATION_SHA256:
        raise AssertionError("MANAGE30 snapshot clarification changed")
    build_checkpoint_path = dataset_path.parent / "RUN_CHECKPOINT.json"
    if not build_checkpoint_path.is_file():
        raise AssertionError("MANAGE30 dataset has no build run checkpoint")
    build_checkpoint = json.loads(build_checkpoint_path.read_text(encoding="utf-8"))
    expected_build_fields = {
        "expected_source_candidates": EXPECTED_SOURCE_CANDIDATES,
        "expected_executable_candidates": EXPECTED_EXECUTABLE_CANDIDATES,
        "frozen_entry_rejections": list(FROZEN_ENTRY_REJECTIONS),
        "predeclaration_sha256": PREDECLARATION_SHA256,
        "data_gate_clarification_sha256": DATA_GATE_CLARIFICATION_SHA256,
        "snapshot_clarification_sha256": SNAPSHOT_CLARIFICATION_SHA256,
        "outer_2024_2025_opened": False,
        "holdout_2026_opened": False,
    }
    for key, expected in expected_build_fields.items():
        if build_checkpoint.get(key) != expected:
            raise AssertionError(f"MANAGE30 build checkpoint mismatch: {key}")
    code_hashes = build_checkpoint.get("code_hashes")
    if not isinstance(code_hashes, dict) or not code_hashes:
        raise AssertionError("MANAGE30 build checkpoint has no code hashes")
    for relative_path, expected_sha in code_hashes.items():
        if sha256_file(ROOT / str(relative_path)) != str(expected_sha):
            raise AssertionError(f"MANAGE30 build dependency changed: {relative_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("status") != "PASS_DATA_GATE":
        raise AssertionError("MANAGE30 dataset has not passed its data gate")
    expected_sha = str(summary.get("dataset", {}).get("sha256", ""))
    if not expected_sha or sha256_file(dataset_path) != expected_sha:
        raise AssertionError("MANAGE30 dataset hash differs from data-gate summary")
    if summary.get("outer_2024_2025_opened") is not False or summary.get("holdout_2026_opened") is not False:
        raise AssertionError("development dataset claims an outer period was opened")
    if int(summary.get("source_candidate_rows", -1)) != EXPECTED_SOURCE_CANDIDATES:
        raise AssertionError("MANAGE30 source candidate census differs from freeze")
    if int(summary.get("entry_rejected_rows", -1)) != len(FROZEN_ENTRY_REJECTIONS):
        raise AssertionError("MANAGE30 entry rejection count differs from freeze")
    if summary.get("entry_rejections") != list(FROZEN_ENTRY_REJECTIONS):
        raise AssertionError("MANAGE30 entry rejection identity differs from freeze")
    frame = pd.read_parquet(dataset_path)
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["trade_date"] = frame["trade_date"].astype(str).str.replace("-", "", regex=False).str[:8]
    frame["month"] = frame["trade_date"].str[:6]
    frame["minute"] = pd.to_numeric(frame["minute"], errors="raise").astype(int)
    if frame.duplicated(KEY).any():
        raise AssertionError("MANAGE30 dataset keys are not unique")
    if len(frame) != EXPECTED_EXECUTABLE_CANDIDATES or len(frame) != int(summary.get("rows", -1)):
        raise AssertionError("MANAGE30 dataset row count differs from summary")
    if frame["trade_date"].str[:4].astype(int).gt(2023).any():
        raise AssertionError("development evaluator opened outer data")
    required = set(KEY) | {"action", "decision_state_available"} | set(M1_FEATURES)
    for action in ACTION_IDS:
        required.update(
            {
                f"outcome_{action}_realized_return",
                f"outcome_{action}_exit_minutes",
                f"outcome_{action}_status",
                f"outcome_{action}_exit_reason",
            }
        )
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise KeyError(f"MANAGE30 dataset missing columns: {missing}")
    return frame.sort_values(KEY, kind="stable").reset_index(drop=True), summary


def _run_identity(dataset_path: Path, summary_path: Path) -> dict[str, Any]:
    return {
        "schema": RUN_SCHEMA,
        "experiment": EXPERIMENT,
        "protocol_sha256": protocol_sha256(),
        "predeclaration_sha256": PREDECLARATION_SHA256,
        "data_gate_clarification_sha256": DATA_GATE_CLARIFICATION_SHA256,
        "snapshot_clarification_sha256": SNAPSHOT_CLARIFICATION_SHA256,
        "dataset_sha256": sha256_file(dataset_path),
        "dataset_summary_sha256": sha256_file(summary_path),
        "build_run_checkpoint_sha256": sha256_file(
            dataset_path.parent / "RUN_CHECKPOINT.json"
        ),
        "code_hashes": _code_hashes(),
        "outer_2024_2025_opened": False,
        "holdout_2026_opened": False,
    }


def _ensure_run_checkpoint(
    output_dir: Path, dataset_path: Path, summary_path: Path
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "RUN_CHECKPOINT.json"
    expected = _run_identity(dataset_path, summary_path)
    if path.exists():
        stored = json.loads(path.read_text(encoding="utf-8"))
        if stored != expected:
            raise AssertionError("evaluation run identity changed; use a new target")
        return stored
    unexpected = [item.name for item in output_dir.iterdir() if not item.name.startswith(".")]
    if unexpected:
        raise AssertionError("evaluation target exists without a run checkpoint")
    _atomic_json(path, expected)
    return expected


def _expand_actions(
    events: pd.DataFrame,
    features: tuple[str, ...],
    *,
    include_target: bool,
) -> pd.DataFrame:
    baseline: pd.Series | None = None
    if include_target:
        baseline = pd.to_numeric(events["outcome_B00_realized_return"], errors="coerce")
        if not np.isfinite(baseline.to_numpy(dtype=float)).all():
            raise AssertionError("B00 target is missing/non-finite")
    frames: list[pd.DataFrame] = []
    base_columns = [*KEY, "decision_state_available", *features]
    base_columns = list(dict.fromkeys(base_columns))
    decision_available = events["decision_state_available"].astype(int).eq(1).to_numpy()
    for action in ACTION_IDS:
        part = events[base_columns].copy()
        available = np.ones(len(events), dtype=bool)
        realized: pd.Series | None = None
        if include_target:
            realized = pd.to_numeric(
                events[f"outcome_{action}_realized_return"], errors="coerce"
            )
            available &= np.isfinite(realized.to_numpy(dtype=float))
        if action != "B00":
            available &= decision_available
        if not available.any():
            continue
        part = part.loc[available].copy()
        part["manage_action"] = action
        for name, value in ACTION_SPECS[action].items():
            part[name] = float(value)
        if include_target:
            if realized is None or baseline is None:
                raise AssertionError("training action expansion lacks targets")
            advantage = realized.loc[available].to_numpy(dtype=float) - baseline.loc[available].to_numpy(dtype=float)
            part["target_advantage"] = np.clip(advantage, -TARGET_CLIP, TARGET_CLIP)
            part["sample_weight"] = 1.0 / float(len(ACTION_IDS))
        frames.append(part)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values([*KEY, "manage_action"], kind="stable").reset_index(drop=True)


def _fit_model(
    train_events: pd.DataFrame,
    features: tuple[str, ...],
    lgb_jobs: int,
) -> tuple[lgb.LGBMRegressor, pd.Series]:
    expanded = _expand_actions(train_events, features, include_target=True)
    model_features = [*features, *ACTION_FEATURES]
    medians = (
        expanded[model_features]
        .replace([np.inf, -np.inf], np.nan)
        .median(numeric_only=True)
        .reindex(model_features)
        .fillna(0.0)
    )
    x = expanded[model_features].replace([np.inf, -np.inf], np.nan).fillna(medians)
    y = expanded["target_advantage"].astype(float)
    weights = expanded["sample_weight"].astype(float)
    params = {**MODEL_PARAMS, "n_jobs": max(1, int(lgb_jobs))}
    model = lgb.LGBMRegressor(**params)
    model.fit(x, y, sample_weight=weights)
    return model, medians


def _score_events(
    events: pd.DataFrame,
    features: tuple[str, ...],
    model: lgb.LGBMRegressor,
    medians: pd.Series,
) -> pd.DataFrame:
    expanded = _expand_actions(events, features, include_target=False)
    model_features = [*features, *ACTION_FEATURES]
    x = expanded[model_features].replace([np.inf, -np.inf], np.nan).fillna(medians)
    expanded["predicted_advantage"] = model.predict(x).astype(float)
    expanded.loc[expanded["manage_action"].eq("B00"), "predicted_advantage"] = 0.0
    priority = {"B00": 0, **{name: index + 1 for index, name in enumerate(sorted(set(ACTION_IDS) - {"B00"}))}}
    expanded["action_priority"] = expanded["manage_action"].map(priority).astype(int)
    ranked = expanded.sort_values(
        [*KEY, "predicted_advantage", "action_priority"],
        ascending=[True, True, True, False, True],
        kind="stable",
    )
    selected = ranked.drop_duplicates(KEY, keep="first").copy()
    selected.loc[selected["predicted_advantage"].le(0.0), "manage_action"] = "B00"
    selected.loc[selected["predicted_advantage"].le(0.0), "predicted_advantage"] = 0.0
    result = events.merge(
        selected[[*KEY, "manage_action", "predicted_advantage"]],
        on=KEY,
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if not result["_merge"].eq("both").all():
        raise AssertionError("a test event lacks a management prediction")
    missing_state = result["decision_state_available"].astype(int).eq(0)
    result.loc[missing_state, "manage_action"] = "B00"
    result.loc[missing_state, "predicted_advantage"] = 0.0
    return result.drop(columns="_merge")


def _attach_selected_outcome(scored: pd.DataFrame) -> pd.DataFrame:
    out = scored.copy()
    out["realized_return"] = np.nan
    out["exit_minutes"] = np.nan
    out["status"] = np.nan
    out["exit_reason"] = ""
    for action in ACTION_IDS:
        mask = out["manage_action"].eq(action)
        if not mask.any():
            continue
        out.loc[mask, "realized_return"] = pd.to_numeric(
            out.loc[mask, f"outcome_{action}_realized_return"], errors="coerce"
        )
        out.loc[mask, "exit_minutes"] = pd.to_numeric(
            out.loc[mask, f"outcome_{action}_exit_minutes"], errors="coerce"
        )
        out.loc[mask, "status"] = pd.to_numeric(
            out.loc[mask, f"outcome_{action}_status"], errors="coerce"
        )
        out.loc[mask, "exit_reason"] = out.loc[
            mask, f"outcome_{action}_exit_reason"
        ].astype(str)
    values = out[["realized_return", "exit_minutes"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise AssertionError("selected management outcome is missing/non-finite")
    if not out["exit_minutes"].between(30.0, 180.0).all():
        raise AssertionError("selected management outcome violates 30..180 hold")
    out["score"] = 1.0
    out["date"] = out["trade_date"]
    return out


def user_gate_pass(metric: dict[str, float | int]) -> bool:
    return bool(
        float(metric["profit_factor"]) > USER_GATES["profit_factor_strictly_greater"]
        and float(metric["win_rate"]) > USER_GATES["win_rate_strictly_greater"]
        and int(metric["trades"]) > USER_GATES["trades_strictly_greater"]
        and float(metric["pnl"]) > USER_GATES["pnl_strictly_greater"]
        and float(metric["minimum_hold"]) >= USER_GATES["minimum_hold_at_least"]
    )


def _fold_identity(
    base: dict[str, Any], month: str, ticker: str, arm: str, train: pd.DataFrame
) -> dict[str, Any]:
    return {
        **base,
        "schema": FOLD_SCHEMA,
        "month": month,
        "ticker": ticker,
        "arm": arm,
        "features": list(FEATURES_BY_ARM[arm]),
        "train_date_max": str(train["trade_date"].max()),
        "train_rows": len(train),
        "train_keys_sha256": _canonical_sha(train[KEY].to_dict("records")),
    }


def _write_fold_checkpoint(
    directory: Path,
    identity: dict[str, Any],
    model: lgb.LGBMRegressor,
    medians: pd.Series,
    predictions: pd.DataFrame,
    trades: pd.DataFrame,
    metrics: pd.DataFrame,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    manifest_path.unlink(missing_ok=True)
    model_path = directory / "model.txt"
    _atomic_text(model_path, model.booster_.model_to_string())
    medians_path = directory / "medians.json"
    _atomic_json(medians_path, {str(key): float(value) for key, value in medians.items()})
    outputs = {
        "predictions.parquet": predictions,
        "trades.csv": trades,
        "metrics.csv": metrics,
    }
    for name, frame in outputs.items():
        path = directory / name
        if name.endswith(".parquet"):
            _atomic_parquet(path, frame)
        else:
            _atomic_csv(path, frame)
    files: dict[str, Any] = {}
    for name in ("model.txt", "medians.json", *outputs):
        path = directory / name
        rows = len(outputs[name]) if name in outputs else None
        files[name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            **({"rows": rows} if rows is not None else {}),
        }
    _atomic_json(
        manifest_path,
        {**identity, "status": "COMPLETE", "atomic_manifest_last": True, "files": files},
    )


def _read_fold_checkpoint(
    directory: Path, identity: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None:
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if {key: manifest.get(key) for key in identity} != identity:
        raise AssertionError("fold checkpoint identity changed; use a new target")
    if manifest.get("status") != "COMPLETE" or manifest.get("atomic_manifest_last") is not True:
        return None
    for name, spec in manifest.get("files", {}).items():
        path = directory / name
        if (
            not path.is_file()
            or int(spec.get("bytes", -1)) != path.stat().st_size
            or spec.get("sha256") != sha256_file(path)
        ):
            return None
    predictions = pd.read_parquet(directory / "predictions.parquet")
    trades = pd.read_csv(directory / "trades.csv")
    metrics = pd.read_csv(directory / "metrics.csv")
    for name, frame in (("predictions.parquet", predictions), ("trades.csv", trades), ("metrics.csv", metrics)):
        if len(frame) != int(manifest["files"][name].get("rows", -1)):
            return None
    return predictions, trades, metrics


def _run_fold(
    data: pd.DataFrame,
    month: str,
    ticker: str,
    arm: str,
    lgb_jobs: int,
) -> tuple[lgb.LGBMRegressor, pd.Series, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = data.loc[(data["ticker"].eq(ticker)) & (data["month"].lt(month))].copy()
    test = data.loc[(data["ticker"].eq(ticker)) & (data["month"].eq(month))].copy()
    if train.empty or test.empty:
        raise AssertionError(f"empty train/test fold: {ticker} {month}")
    if not train["trade_date"].lt(month + "01").all() or not test["month"].eq(month).all():
        raise AssertionError("fold chronology failed")
    features = FEATURES_BY_ARM[arm]
    model, medians = _fit_model(train, features, lgb_jobs)
    predictions = _score_events(test, features, model, medians)
    candidates = _attach_selected_outcome(predictions)
    trades = replay_live_equivalent(candidates)
    _assert_scheduler_output(trades)
    trades["month"] = month
    trades["arm"] = arm
    metric = economic_metrics(trades)
    metrics = pd.DataFrame(
        [
            {
                "month": month,
                "ticker": ticker,
                "arm": arm,
                "train_events": len(train),
                "test_events": len(test),
                "scheduler_rejections": len(test) - len(trades),
                **metric,
                "positive_month": bool(float(metric["pnl"]) > 0.0),
                "gate_pass": user_gate_pass(metric),
            }
        ]
    )
    prediction_columns = [
        *KEY,
        "month",
        "action",
        "manage_action",
        "predicted_advantage",
        "decision_state_available",
        "realized_return",
        "exit_minutes",
        "status",
        "exit_reason",
    ]
    return model, medians, candidates[prediction_columns], trades, metrics


def evaluate(
    dataset_path: Path,
    summary_path: Path,
    output_dir: Path,
    lgb_jobs: int,
) -> dict[str, Any]:
    data, data_summary = _load_dataset(dataset_path, summary_path)
    base = _ensure_run_checkpoint(output_dir, dataset_path, summary_path)
    prediction_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    metric_frames: list[pd.DataFrame] = []
    built = 0
    reused = 0
    total = len(DEVELOPMENT_MONTHS) * len(SCHEDULER) * len(ARMS)
    index = 0
    for month in DEVELOPMENT_MONTHS:
        for ticker in ("SPXW", "QQQ", "SPY"):
            train = data.loc[(data["ticker"].eq(ticker)) & (data["month"].lt(month))]
            for arm in ARMS:
                index += 1
                identity = _fold_identity(base, month, ticker, arm, train)
                directory = output_dir / "fold_checkpoints" / month / ticker / arm
                cached = _read_fold_checkpoint(directory, identity)
                if cached is None:
                    model, medians, predictions, trades, metrics = _run_fold(
                        data, month, ticker, arm, lgb_jobs
                    )
                    _write_fold_checkpoint(
                        directory, identity, model, medians, predictions, trades, metrics
                    )
                    built += 1
                    status = "built"
                else:
                    predictions, trades, metrics = cached
                    reused += 1
                    status = "reused"
                prediction_frames.append(predictions)
                trade_frames.append(trades)
                metric_frames.append(metrics)
                print(
                    f"[fold {index}/{total}] {month} {ticker} {arm} "
                    f"checkpoint={status} PF={float(metrics.iloc[0]['profit_factor']):.3f} "
                    f"WR={float(metrics.iloc[0]['win_rate']):.3f}",
                    flush=True,
                )
    predictions = pd.concat(prediction_frames, ignore_index=True)
    trades = pd.concat(trade_frames, ignore_index=True)
    monthly = pd.concat(metric_frames, ignore_index=True)
    monthly["gate_pass"] = monthly["gate_pass"].astype(str).str.lower().eq("true")
    monthly["positive_month"] = monthly["positive_month"].astype(str).str.lower().eq("true")
    summaries: list[dict[str, Any]] = []
    concentration_rows: list[dict[str, Any]] = []
    eligible: list[str] = []
    for arm in ARMS:
        cells = monthly.loc[monthly["arm"].eq(arm)]
        arm_trades = trades.loc[trades["arm"].eq(arm)]
        concentration_pass = True
        for scope, part in [("POOLED", arm_trades)] + [
            (ticker, arm_trades.loc[arm_trades["ticker"].eq(ticker)])
            for ticker in ("SPXW", "QQQ", "SPY")
        ]:
            top_trades, top_days = _concentration(part)
            passed = bool(
                top_trades <= MAX_TOP5_TRADE_GROSS_PROFIT_SHARE
                and top_days <= MAX_TOP5_DAY_GROSS_PROFIT_SHARE
            )
            concentration_pass &= passed
            concentration_rows.append(
                {
                    "arm": arm,
                    "scope": scope,
                    "trades": len(part),
                    "top5_trade_gross_profit_share": top_trades,
                    "top5_day_gross_profit_share": top_days,
                    "concentration_pass": passed,
                }
            )
        pooled = economic_metrics(arm_trades)
        arm_eligible = bool(len(cells) == 36 and cells["gate_pass"].all() and concentration_pass)
        if arm_eligible:
            eligible.append(arm)
        summaries.append(
            {
                "arm": arm,
                **pooled,
                "passing_cells": int(cells["gate_pass"].sum()),
                "minimum_monthly_trades": int(cells["trades"].min()),
                "worst_month_pf": float(cells["profit_factor"].min()),
                "worst_month_wr": float(cells["win_rate"].min()),
                "worst_month_pnl": float(cells["pnl"].min()),
                "positive_month_rate": float(cells["positive_month"].mean()),
                "concentration_pass": concentration_pass,
                "eligible_36_of_36": arm_eligible,
            }
        )
    policy_summary = pd.DataFrame(summaries)
    concentration = pd.DataFrame(concentration_rows)
    selected: str | None = None
    if eligible:
        ranked = policy_summary.loc[policy_summary["arm"].isin(eligible)].sort_values(
            ["worst_month_pf", "worst_month_wr", "profit_factor", "arm"],
            ascending=[False, False, False, True],
            kind="stable",
        )
        selected = str(ranked.iloc[0]["arm"])
    outputs = {
        "predictions.parquet": predictions,
        "trades.csv": trades,
        "monthly_metrics.csv": monthly,
        "policy_summary.csv": policy_summary,
        "concentration.csv": concentration,
    }
    for name, frame in outputs.items():
        path = output_dir / name
        if name.endswith(".parquet"):
            _atomic_parquet(path, frame)
        else:
            _atomic_csv(path, frame)
    files = {
        name: {
            "rows": len(frame),
            "bytes": (output_dir / name).stat().st_size,
            "sha256": sha256_file(output_dir / name),
        }
        for name, frame in outputs.items()
    }
    result = {
        "schema": "king_gex_manage30_development_results_v1",
        "experiment": EXPERIMENT,
        "status": "PASS_DEVELOPMENT" if selected is not None else "FAILED_ECONOMIC_DEVELOPMENT",
        "selected": selected,
        "eligible_arms": eligible,
        "fold_checkpoints": {"total": total, "built_this_run": built, "reused_this_run": reused},
        "dataset_sha256": str(data_summary["dataset"]["sha256"]),
        "protocol_sha256": protocol_sha256(),
        "files": files,
        "outer_2024_2025_opened": False,
        "holdout_2026_opened": False,
        "production_modified": False,
    }
    _atomic_json(output_dir / "SUMMARY.json", _json_finite(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--dataset-summary", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--lgb-jobs", type=int, default=4)
    args = parser.parse_args()
    result = evaluate(
        Path(args.dataset),
        Path(args.dataset_summary),
        Path(args.output_dir),
        max(1, int(args.lgb_jobs)),
    )
    print(json.dumps(_json_finite(result), indent=2, sort_keys=True, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
