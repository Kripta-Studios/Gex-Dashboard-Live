"""Frozen physical evaluation for ``WALL_SURFACE_FLOW_AT_TOUCH_V1R1``.

This runner predicts true rejection versus accepted break at first, unambiguous
wall-touch episodes.  It does not read option payoffs or execute a trading
policy.  All configuration and input hashes must match a committed
pre-execution freeze manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, wilcoxon
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.surface_flow_features import (  # noqa: E402
    CONTROL_FEATURES,
    END_DATE,
    FLOW_FEATURES,
    KEY_COLUMNS,
    WALL_SPECS,
    assert_surface_flow_schema,
    underlying_market_close_minute,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402


HORIZONS = (30, 60, 120, 180)
BUFFER_BPS = 5.0
SEED = 20260711
BOOTSTRAP_REPLICATES = 1000
MAX_WORKERS = 16
EXPECTED_SESSION_COUNT = 2519
EXPECTED_SESSION_KEY_SHA256 = "ac7200fd96f2ef9afc2f9f09eff18804497a2f975a7454cccf5ed1c935653057"
EXPECTED_DATA_INPUT_HASHES = {
    "walls": "94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef",
    "events": "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408",
    "manifest": "5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88",
}
ENVIRONMENT_LOCK = PROJECT_ROOT / "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
FOLDS = (
    {"fold": "2024", "train_end": "20231231", "test_start": "20240101", "test_end": "20241231"},
    {"fold": "2025", "train_end": "20241231", "test_start": "20250101", "test_end": "20251231"},
)
MODEL_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "n_estimators": 300,
    "learning_rate": 0.03,
    "num_leaves": 15,
    "min_child_samples": 100,
    "colsample_bytree": 0.8,
    "subsample": 0.8,
    "subsample_freq": 1,
    "reg_alpha": 0.0,
    "reg_lambda": 1.0,
    "random_state": SEED,
    "n_jobs": 28,
    "deterministic": True,
    "force_col_wise": True,
    "verbosity": -1,
}
LABEL_SPEC = {
    "touch_universe_bps": 15.0,
    "terminal_buffer_bps": BUFFER_BPS,
    "current_beyond_counts_as_pierced": True,
    "future_bar_starts": "t <= s < t+h",
    "terminal_price": "close of exact bar starting t+h-1m",
    "same_session_horizon": "t+h <= underlying RTH close (16:00 regular, 13:00 frozen half days)",
    "true_rejection": "pierced and terminal >=5bps on defended side",
    "accepted_break": "pierced and terminal >=5bps beyond wall",
    "neutral": "unresolved",
}
GATE_SPEC = {
    "planned_paired_cells": 24,
    "minimum_auc_wins": 16,
    "minimum_median_auc_delta": 0.010,
    "maximum_wilcoxon_one_sided_p": 0.05,
    "paired_test_unit": "ticker_fold_median_across_horizons",
    "ticker_minimum_wins": 5,
    "ticker_minimum_median_f1_auc": 0.55,
    "primary_horizons": [30, 60],
    "ticker_primary_minimum_wins": 3,
    "minimum_monthly_resolved_episodes": 18,
    "maximum_joint_ap_logloss_losses": 12,
}


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_list(values: list[str] | tuple[str, ...]) -> str:
    payload = json.dumps(list(values), separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def current_git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def assert_committed_runner() -> str:
    tracked = (
        "neural/jepa/evaluate_wall_surface_flow_at_touch_v1.py",
        "neural/jepa/surface_flow_features.py",
        "neural/jepa/wall_surface_flow_environment.py",
        "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt",
    )
    for relative in tracked:
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", relative],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if dirty:
            raise AssertionError(f"frozen runner must be committed and clean: {relative}: {dirty}")
    return current_git_commit()


def assert_tracked_clean(path: Path, label: str) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError as exc:
        raise AssertionError(f"{label} must be a committed repository artifact: {resolved}") from exc
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", relative],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise AssertionError(f"{label} must be committed and clean: {dirty}")
    return relative


def verify_status_evidence(freeze: dict[str, Any], status_field: str, evidence_field: str) -> None:
    if str(freeze.get(status_field, "BLOCKED")) != "PASS":
        return
    evidence = freeze.get(evidence_field)
    if not isinstance(evidence, dict) or not evidence.get("path") or not evidence.get("sha256"):
        raise AssertionError(f"{status_field}=PASS requires committed hashed {evidence_field}")
    path = PROJECT_ROOT / str(evidence["path"])
    assert_tracked_clean(path, evidence_field)
    if sha256_file(path) != str(evidence["sha256"]):
        raise AssertionError(f"{evidence_field} hash mismatch")


def model_feature_names(arm: str) -> list[str]:
    if arm not in {"F0", "F1"}:
        raise ValueError(f"unknown arm {arm}")
    names = list(CONTROL_FEATURES)
    if arm == "F1":
        names.extend(FLOW_FEATURES)
    names.extend([f"identity_{identity}" for identity in sorted(WALL_SPECS)])
    return names


def verify_freeze(
    freeze_path: Path,
    *,
    flow_path: Path,
    source_hashes_path: Path,
    data_manifest_path: Path,
) -> dict[str, Any]:
    assert_tracked_clean(freeze_path, "frozen manifest")
    assert_tracked_clean(data_manifest_path, "data manifest")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    if freeze.get("schema") != "wall_surface_flow_at_touch_frozen_runner_v1r1":
        raise AssertionError("wrong or missing frozen runner schema")
    expected_inputs = freeze.get("inputs", {})
    observed = {
        "flow_dataset": sha256_file(flow_path),
        "source_file_hashes": sha256_file(source_hashes_path),
        "data_manifest": sha256_file(data_manifest_path),
    }
    expected = {name: str(expected_inputs.get(name, {}).get("sha256", "")) for name in observed}
    if observed != expected:
        raise AssertionError(f"frozen evaluation input hash mismatch: observed={observed} expected={expected}")
    if str(freeze.get("runner_sha256", "")) != sha256_file(__file__):
        raise AssertionError("frozen runner code hash mismatch")
    feature_module = Path(__file__).with_name("surface_flow_features.py")
    if str(freeze.get("feature_module_sha256", "")) != sha256_file(feature_module):
        raise AssertionError("frozen feature module hash mismatch")
    if str(freeze.get("runtime_lock_sha256", "")) != runtime["lock_sha256"]:
        raise AssertionError("frozen runtime lock hash mismatch")
    if freeze.get("runtime_environment") != runtime["environment"]:
        raise AssertionError("frozen runtime environment differs from active environment")
    if str(freeze.get("runtime_environment_sha256", "")) != runtime["environment_sha256"]:
        raise AssertionError("frozen runtime environment hash mismatch")
    if freeze.get("model_params") != MODEL_PARAMS:
        raise AssertionError("frozen model parameters differ from runner")
    if freeze.get("label_spec") != LABEL_SPEC:
        raise AssertionError("frozen label semantics differ from runner")
    if freeze.get("gate_spec") != GATE_SPEC:
        raise AssertionError("frozen gate differs from runner")
    expected_feature_hashes = {
        "F0": hash_list(model_feature_names("F0")),
        "F1": hash_list(model_feature_names("F1")),
    }
    if freeze.get("model_feature_hashes") != expected_feature_hashes:
        raise AssertionError("frozen feature allowlist hash mismatch")
    verify_status_evidence(freeze, "historical_timestamp_provenance_status", "timestamp_provenance_evidence")
    verify_status_evidence(freeze, "live_feature_parity_status", "live_parity_evidence")
    data_manifest = json.loads(data_manifest_path.read_text(encoding="utf-8"))
    if data_manifest.get("status") != "PASS_DATA_GATE":
        raise AssertionError(f"flow data gate is not PASS_DATA_GATE: {data_manifest.get('status')}")
    if str(data_manifest.get("dataset_sha256")) != observed["flow_dataset"]:
        raise AssertionError("flow data manifest does not identify the supplied dataset")
    if str(data_manifest.get("source_file_hashes_sha256")) != observed["source_file_hashes"]:
        raise AssertionError("source hash inventory differs from the data build manifest")
    if data_manifest.get("input_hashes") != EXPECTED_DATA_INPUT_HASHES:
        raise AssertionError("data manifest does not use the frozen wall/event/source inputs")
    if int(data_manifest.get("full_session_universe_count", -1)) != EXPECTED_SESSION_COUNT:
        raise AssertionError("data manifest session count mismatch")
    if str(data_manifest.get("full_session_key_sha256")) != EXPECTED_SESSION_KEY_SHA256:
        raise AssertionError("data manifest session-key hash mismatch")
    if str(data_manifest.get("feature_module_sha256")) != sha256_file(feature_module):
        raise AssertionError("data manifest feature module differs from frozen runner")
    if str(data_manifest.get("runtime_lock_sha256", "")) != runtime["lock_sha256"]:
        raise AssertionError("data manifest runtime lock hash mismatch")
    if data_manifest.get("runtime_environment") != runtime["environment"]:
        raise AssertionError("data manifest runtime environment mismatch")
    if str(data_manifest.get("runtime_environment_sha256", "")) != runtime["environment_sha256"]:
        raise AssertionError("data manifest runtime environment hash mismatch")
    if str(data_manifest.get("control_feature_hash")) != hash_list(CONTROL_FEATURES):
        raise AssertionError("data manifest control allowlist hash mismatch")
    if str(data_manifest.get("flow_feature_hash")) != hash_list(FLOW_FEATURES):
        raise AssertionError("data manifest flow allowlist hash mismatch")
    if not bool((data_manifest.get("data_gate") or {}).get("passed", False)):
        raise AssertionError("data manifest embeds a failed data gate")
    return freeze


def _read_underlying_exact(path: str | Path, *, expected_trade_date: str | None = None) -> pd.DataFrame:
    required = ["timestamp", "open", "high", "low", "close"]
    frame = pd.read_parquet(path, columns=required)
    frame["bar_start"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame = frame.dropna(subset=["bar_start"]).copy()
    expected_date = str(expected_trade_date or "").replace("-", "")[:8]
    if expected_date and not frame["bar_start"].dt.strftime("%Y%m%d").eq(expected_date).all():
        raise AssertionError(f"underlying timestamps do not belong to {expected_date}: {path}")
    boundary = frame["bar_start"].dt.second.eq(0) & frame["bar_start"].dt.microsecond.eq(0)
    if not bool(boundary.all()):
        raise AssertionError(f"underlying source has non-minute-boundary timestamps: {path}")
    if frame.duplicated(["bar_start"]).any():
        raise AssertionError(f"underlying source has duplicate minute keys: {path}")
    for column in ("open", "high", "low", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if not np.isfinite(frame[["open", "high", "low", "close"]].to_numpy(dtype=float)).all():
        raise AssertionError(f"underlying source contains non-finite OHLC: {path}")
    if (frame[["open", "high", "low", "close"]] <= 0.0).any().any():
        raise AssertionError(f"underlying source contains nonpositive OHLC: {path}")
    envelope = frame["high"].ge(frame[["open", "close"]].max(axis=1)) & frame["low"].le(
        frame[["open", "close"]].min(axis=1)
    )
    if not bool(envelope.all()):
        raise AssertionError(f"underlying source violates OHLC envelope: {path}")
    return frame.sort_values("bar_start", kind="stable").reset_index(drop=True)


def assert_source_inventory(frame: pd.DataFrame) -> None:
    required = {
        "ticker", "trade_date", "source_kind", "path", "bytes", "rows", "schema_sha256",
        "sha256", "timestamp_min", "timestamp_max", "interval_values", "symbol_values",
        "expiration_values", "trade_date_values", "right_values", "distinct_strikes",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise AssertionError(f"source inventory missing columns: {missing}")
    work = frame.copy()
    work["ticker"] = work["ticker"].astype(str).str.upper()
    work["trade_date"] = work["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    if work.duplicated(["ticker", "trade_date", "source_kind"]).any():
        raise AssertionError("source inventory has duplicate session/kind keys")
    if len(work) != EXPECTED_SESSION_COUNT * 3:
        raise AssertionError(f"source inventory row count mismatch: {len(work)}")
    kinds = work.groupby(["ticker", "trade_date"], observed=True)["source_kind"].agg(
        lambda values: set(values.astype(str))
    )
    if len(kinds) != EXPECTED_SESSION_COUNT or not kinds.map(lambda values: values == {"greeks", "ohlc", "underlying"}).all():
        raise AssertionError("source inventory does not contain exactly three required sources per session")
    sessions = work[["ticker", "trade_date"]].drop_duplicates().sort_values(["ticker", "trade_date"], kind="stable")
    payload = "".join(f"{row.ticker},{row.trade_date}\n" for row in sessions.itertuples(index=False)).encode("utf-8")
    if hashlib.sha256(payload).hexdigest() != EXPECTED_SESSION_KEY_SHA256:
        raise AssertionError("source inventory session-key hash mismatch")
    if work["trade_date"].str.startswith("2026").any():
        raise AssertionError("source inventory contains forbidden 2026 rows")
    if not work["sha256"].astype(str).str.fullmatch(r"[0-9a-f]{64}").all():
        raise AssertionError("source inventory contains malformed SHA-256 values")


def label_candidate_session(candidates: pd.DataFrame, underlying: pd.DataFrame) -> pd.DataFrame:
    """Attach future-only physical labels with exact bar-open horizon semantics."""

    out = candidates.copy()
    bars = underlying.set_index("bar_start", drop=False)
    for horizon in HORIZONS:
        for name in ("pierced", "true_rejection", "accepted_break", "resolved_rejection", "terminal_distance_bps"):
            out[f"{name}_{horizon}m"] = np.nan
        out[f"path_complete_{horizon}m"] = 0
    for index, row in out.iterrows():
        start = pd.Timestamp(row["decision_dt"])
        trade_date = str(row["trade_date"]).replace("-", "")[:8]
        if start.strftime("%Y%m%d") != trade_date:
            raise AssertionError(f"candidate decision timestamp/date mismatch at row {index}")
        session_close = start.normalize() + pd.Timedelta(
            minutes=underlying_market_close_minute(trade_date)
        )
        wall = float(row["candidate_wall_strike"])
        spot = float(row["spot"])
        role = str(row["wall_role"])
        if role not in {"support", "resistance"} or not np.isfinite(wall) or not np.isfinite(spot) or spot <= 0.0:
            raise AssertionError(f"invalid candidate geometry at row {index}")
        current_pierced = bool(spot <= wall) if role == "support" else bool(spot >= wall)
        for horizon in HORIZONS:
            end = start + pd.Timedelta(minutes=horizon)
            if end > session_close:
                continue
            expected = pd.date_range(start, end - pd.Timedelta(minutes=1), freq="1min")
            path = bars.reindex(expected)
            if len(path) != horizon or path["bar_start"].isna().any():
                continue
            out.at[index, f"path_complete_{horizon}m"] = 1
            future_low = float(path["low"].min())
            future_high = float(path["high"].max())
            terminal_close = float(path.iloc[-1]["close"])
            future_pierced = bool(future_low <= wall) if role == "support" else bool(future_high >= wall)
            pierced = bool(current_pierced or future_pierced)
            terminal_distance = (terminal_close - wall) / spot * 10_000.0
            defended = terminal_distance >= BUFFER_BPS if role == "support" else terminal_distance <= -BUFFER_BPS
            beyond = terminal_distance <= -BUFFER_BPS if role == "support" else terminal_distance >= BUFFER_BPS
            rejection = bool(pierced and defended)
            accepted = bool(pierced and beyond)
            resolved = bool(rejection ^ accepted)
            out.at[index, f"pierced_{horizon}m"] = float(pierced)
            out.at[index, f"true_rejection_{horizon}m"] = float(rejection)
            out.at[index, f"accepted_break_{horizon}m"] = float(accepted)
            out.at[index, f"terminal_distance_bps_{horizon}m"] = float(terminal_distance)
            if resolved:
                out.at[index, f"resolved_rejection_{horizon}m"] = float(rejection)
    return out


def _load_label_session(
    candidates: pd.DataFrame,
    source: dict[str, Any],
) -> pd.DataFrame:
    path = Path(str(source["path"]))
    expected_hash = str(source["sha256"])
    if sha256_file(path) != expected_hash:
        raise AssertionError(f"underlying source hash mismatch: {path}")
    underlying = _read_underlying_exact(path, expected_trade_date=str(source["trade_date"]))
    if sha256_file(path) != expected_hash:
        raise AssertionError(f"underlying source changed while labeling: {path}")
    return label_candidate_session(candidates, underlying)


def add_future_labels(
    candidates: pd.DataFrame,
    source_hashes: pd.DataFrame,
    workers: int,
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    if not 1 <= int(workers) <= MAX_WORKERS:
        raise ValueError(f"workers must be within 1..{MAX_WORKERS}")
    sources = source_hashes[source_hashes["source_kind"].astype(str).eq("underlying")].copy()
    sources["ticker"] = sources["ticker"].astype(str).str.upper()
    sources["trade_date"] = sources["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    if sources.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("underlying source inventory has duplicate session keys")
    source_map = {
        (str(row.ticker), str(row.trade_date)): row._asdict()
        for row in sources.itertuples(index=False)
    }
    tasks: list[tuple[pd.DataFrame, dict[str, Any]]] = []
    errors: list[dict[str, str]] = []
    for key, part in candidates.groupby(["ticker", "trade_date"], observed=True, sort=True):
        source = source_map.get((str(key[0]), str(key[1])))
        if source is None:
            errors.append({"ticker": str(key[0]), "trade_date": str(key[1]), "error": "missing underlying source hash"})
        else:
            tasks.append((part.copy(), source))
    frames: list[pd.DataFrame] = []
    if workers == 1:
        for part, source in tasks:
            try:
                frames.append(_load_label_session(part, source))
            except Exception as exc:
                errors.append(
                    {
                        "ticker": str(part.iloc[0]["ticker"]),
                        "trade_date": str(part.iloc[0]["trade_date"]),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_load_label_session, part, source): part for part, source in tasks}
            for index, future in enumerate(as_completed(futures), start=1):
                part = futures[future]
                try:
                    frames.append(future.result())
                except Exception as exc:
                    errors.append(
                        {
                            "ticker": str(part.iloc[0]["ticker"]),
                            "trade_date": str(part.iloc[0]["trade_date"]),
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                if index % 100 == 0 or index == len(futures):
                    print(f"[SURFACE_FLOW:LABEL] sessions={index}/{len(futures)} errors={len(errors)}", flush=True)
    labeled = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not labeled.empty:
        labeled = labeled.sort_values(list(KEY_COLUMNS), kind="stable").reset_index(drop=True)
    return labeled, errors


def model_matrix(frame: pd.DataFrame, arm: str) -> pd.DataFrame:
    base = list(CONTROL_FEATURES) + (list(FLOW_FEATURES) if arm == "F1" else [])
    matrix = frame[base].apply(pd.to_numeric, errors="coerce").reset_index(drop=True)
    identities = frame["wall_identity"].astype(str).str.split("+")
    for identity in sorted(WALL_SPECS):
        matrix[f"identity_{identity}"] = identities.map(lambda values: float(identity in values)).to_numpy()
    return matrix[model_feature_names(arm)]


def calibration_table(y: np.ndarray, probability: np.ndarray, bins: int = 10) -> tuple[float, list[dict[str, Any]]]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    assignments = np.minimum(np.digitize(probability, edges[1:-1], right=False), bins - 1)
    rows: list[dict[str, Any]] = []
    ece = 0.0
    for index in range(bins):
        mask = assignments == index
        count = int(mask.sum())
        mean_probability = float(probability[mask].mean()) if count else None
        event_rate = float(y[mask].mean()) if count else None
        if count:
            ece += count / len(y) * abs(float(mean_probability) - float(event_rate))
        rows.append(
            {
                "bin": index,
                "lower": float(edges[index]),
                "upper": float(edges[index + 1]),
                "count": count,
                "mean_probability": mean_probability,
                "event_rate": event_rate,
            }
        )
    return float(ece), rows


def probability_metrics(y: np.ndarray, probability: np.ndarray) -> tuple[dict[str, float], list[dict[str, Any]]]:
    ece, calibration = calibration_table(y, probability)
    correlation = spearmanr(probability, y).statistic
    return (
        {
            "roc_auc": float(roc_auc_score(y, probability)),
            "average_precision": float(average_precision_score(y, probability)),
            "balanced_accuracy_05": float(balanced_accuracy_score(y, probability >= 0.5)),
            "brier": float(brier_score_loss(y, probability)),
            "log_loss": float(log_loss(y, probability, labels=[0, 1])),
            "spearman": float(correlation) if np.isfinite(correlation) else 0.0,
            "ece_10": ece,
        },
        calibration,
    )


def fit_arm(
    train: pd.DataFrame,
    test: pd.DataFrame,
    target: str,
    arm: str,
    model_path: Path,
) -> tuple[dict[str, Any], np.ndarray | None, list[dict[str, Any]]]:
    y_train = train[target].astype(int).to_numpy()
    y_test = test[target].astype(int).to_numpy()
    result: dict[str, Any] = {
        "arm": arm,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_positive_rate": float(y_train.mean()) if len(y_train) else None,
        "test_positive_rate": float(y_test.mean()) if len(y_test) else None,
        "valid": False,
    }
    if len(train) == 0 or len(test) == 0 or len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
        return result, None, []
    positive = max(int((y_train == 1).sum()), 1)
    negative = max(int((y_train == 0).sum()), 1)
    weights = np.where(y_train == 1, len(y_train) / (2.0 * positive), len(y_train) / (2.0 * negative))
    model = lgb.LGBMClassifier(**MODEL_PARAMS)
    model.fit(model_matrix(train, arm), y_train, sample_weight=weights)
    probability = model.predict_proba(model_matrix(test, arm))[:, 1]
    metrics, calibration = probability_metrics(y_test, probability)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(model_path))
    result.update(
        {
            "valid": True,
            **metrics,
            "model_path": str(model_path),
            "model_sha256": sha256_file(model_path),
            "model_feature_hash": hash_list(model_feature_names(arm)),
        }
    )
    return result, probability, calibration


def paired_day_bootstrap(
    test: pd.DataFrame,
    y: np.ndarray,
    probability_f0: np.ndarray,
    probability_f1: np.ndarray,
    *,
    seed: int,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    dates = test["trade_date"].astype(str).to_numpy()
    unique_days = np.unique(dates)
    day_indices = {day: np.flatnonzero(dates == day) for day in unique_days}
    rng = np.random.default_rng(seed)
    deltas: list[float] = []
    for _ in range(replicates):
        sampled_days = rng.choice(unique_days, size=len(unique_days), replace=True)
        indices = np.concatenate([day_indices[str(day)] for day in sampled_days])
        sampled_y = y[indices]
        if len(np.unique(sampled_y)) < 2:
            continue
        deltas.append(
            float(roc_auc_score(sampled_y, probability_f1[indices]) - roc_auc_score(sampled_y, probability_f0[indices]))
        )
    values = np.asarray(deltas, dtype=float)
    return {
        "bootstrap_requested": int(replicates),
        "bootstrap_valid": int(len(values)),
        "bootstrap_auc_delta_p025": float(np.quantile(values, 0.025)) if len(values) else None,
        "bootstrap_auc_delta_median": float(np.median(values)) if len(values) else None,
        "bootstrap_auc_delta_p975": float(np.quantile(values, 0.975)) if len(values) else None,
        "bootstrap_favorable_share": float((values > 0.0).mean()) if len(values) else None,
    }


def expected_months(year: str) -> list[str]:
    return [f"{year}{month:02d}" for month in range(1, 13)]


def monthly_coverage(test_base: pd.DataFrame, target: str, fold: str, ticker: str, horizon: int) -> list[dict[str, Any]]:
    work = test_base[pd.to_numeric(test_base[target], errors="coerce").notna()].copy()
    work["month"] = work["trade_date"].astype(str).str[:6]
    rows: list[dict[str, Any]] = []
    for month in expected_months(fold):
        part = work[work["month"].eq(month)]
        rows.append(
            {
                "fold": fold,
                "ticker": ticker,
                "horizon": horizon,
                "month": month,
                "resolved_episodes": int(len(part)),
                "classes": int(part[target].nunique(dropna=True)) if len(part) else 0,
                "both_classes": bool(len(part) and part[target].nunique(dropna=True) == 2),
            }
        )
    return rows


def evaluate_cells(
    labeled: pd.DataFrame,
    model_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cell_rows: list[dict[str, Any]] = []
    paired_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    calibration_rows: list[dict[str, Any]] = []
    model_rows: list[dict[str, Any]] = []
    ticker_offsets = {"SPXW": 1000, "QQQ": 2000, "SPY": 3000}
    for fold_spec in FOLDS:
        fold = str(fold_spec["fold"])
        for ticker in ("SPXW", "QQQ", "SPY"):
            ticker_frame = labeled[labeled["ticker"].eq(ticker)]
            train_base = ticker_frame[ticker_frame["trade_date"].le(fold_spec["train_end"])]
            test_base = ticker_frame[ticker_frame["trade_date"].between(fold_spec["test_start"], fold_spec["test_end"])]
            for horizon in HORIZONS:
                target = f"resolved_rejection_{horizon}m"
                train = train_base[pd.to_numeric(train_base[target], errors="coerce").notna()].copy()
                test = test_base[pd.to_numeric(test_base[target], errors="coerce").notna()].copy()
                monthly_rows.extend(monthly_coverage(test_base, target, fold, ticker, horizon))
                cell_id = f"{fold}_{ticker}_{horizon}m"
                arm_results: dict[str, dict[str, Any]] = {}
                probabilities: dict[str, np.ndarray | None] = {}
                for arm in ("F0", "F1"):
                    model_path = model_dir / f"{cell_id}_{arm}.txt"
                    metrics, probability, calibration = fit_arm(train, test, target, arm, model_path)
                    row = {"cell_id": cell_id, "fold": fold, "ticker": ticker, "horizon": horizon, "target": target, **metrics}
                    cell_rows.append(row)
                    arm_results[arm] = row
                    probabilities[arm] = probability
                    if metrics.get("valid"):
                        model_rows.append(
                            {
                                "cell_id": cell_id,
                                "arm": arm,
                                "path": str(model_path),
                                "sha256": metrics["model_sha256"],
                                "feature_hash": metrics["model_feature_hash"],
                                "seed": SEED,
                            }
                        )
                    for bin_row in calibration:
                        calibration_rows.append({"cell_id": cell_id, "fold": fold, "ticker": ticker, "horizon": horizon, "arm": arm, **bin_row})
                valid_pair = bool(arm_results["F0"].get("valid") and arm_results["F1"].get("valid"))
                paired: dict[str, Any] = {
                    "cell_id": cell_id,
                    "fold": fold,
                    "ticker": ticker,
                    "horizon": horizon,
                    "valid_pair": valid_pair,
                    "auc_delta": None,
                    "average_precision_delta": None,
                    "log_loss_delta": None,
                    "brier_delta": None,
                    "balanced_accuracy_delta": None,
                    "spearman_delta": None,
                    "ece_delta": None,
                }
                if valid_pair:
                    f0, f1 = arm_results["F0"], arm_results["F1"]
                    paired.update(
                        {
                            "auc_delta": float(f1["roc_auc"] - f0["roc_auc"]),
                            "average_precision_delta": float(f1["average_precision"] - f0["average_precision"]),
                            "log_loss_delta": float(f1["log_loss"] - f0["log_loss"]),
                            "brier_delta": float(f1["brier"] - f0["brier"]),
                            "balanced_accuracy_delta": float(f1["balanced_accuracy_05"] - f0["balanced_accuracy_05"]),
                            "spearman_delta": float(f1["spearman"] - f0["spearman"]),
                            "ece_delta": float(f1["ece_10"] - f0["ece_10"]),
                        }
                    )
                    bootstrap_seed = SEED + int(fold) + ticker_offsets[ticker] + horizon
                    paired.update(
                        paired_day_bootstrap(
                            test,
                            test[target].astype(int).to_numpy(),
                            probabilities["F0"],  # type: ignore[arg-type]
                            probabilities["F1"],  # type: ignore[arg-type]
                            seed=bootstrap_seed,
                        )
                    )
                    predictions = test[[*KEY_COLUMNS, "episode_id", "wall_role", "candidate_wall_strike"]].copy()
                    predictions["fold"] = fold
                    predictions["horizon"] = horizon
                    predictions["target"] = test[target].astype(int).to_numpy()
                    predictions["probability_f0"] = probabilities["F0"]
                    predictions["probability_f1"] = probabilities["F1"]
                    prediction_frames.append(predictions)
                paired_rows.append(paired)
                print(f"[SURFACE_FLOW:MODEL] {cell_id} valid={valid_pair} delta={paired['auc_delta']}", flush=True)
    return (
        pd.DataFrame(cell_rows),
        pd.DataFrame(paired_rows),
        pd.DataFrame(monthly_rows),
        pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame(),
        pd.DataFrame(calibration_rows),
        pd.DataFrame(model_rows),
    )


def summarize_gate(
    cells: pd.DataFrame,
    paired: pd.DataFrame,
    monthly: pd.DataFrame,
    *,
    provenance_status: str,
    live_parity_status: str,
) -> dict[str, Any]:
    valid = paired["valid_pair"].astype(bool)
    deltas = pd.to_numeric(paired.loc[valid, "auc_delta"], errors="coerce").dropna()
    cluster_deltas = (
        paired.loc[valid]
        .assign(auc_delta_numeric=pd.to_numeric(paired.loc[valid, "auc_delta"], errors="coerce"))
        .groupby(["ticker", "fold"], observed=True, sort=True)["auc_delta_numeric"]
        .median()
        .dropna()
    )
    if len(deltas) == 24 and len(cluster_deltas) == 6 and not np.allclose(cluster_deltas, 0.0):
        pvalue = float(wilcoxon(cluster_deltas, alternative="greater").pvalue)
    else:
        pvalue = 1.0
    wins = int((pd.to_numeric(paired["auc_delta"], errors="coerce") > 0.0).sum())
    aggregate_pass = bool(
        int(valid.sum()) == GATE_SPEC["planned_paired_cells"]
        and wins >= GATE_SPEC["minimum_auc_wins"]
        and float(deltas.median()) >= GATE_SPEC["minimum_median_auc_delta"]
        and pvalue < GATE_SPEC["maximum_wilcoxon_one_sided_p"]
    )
    ticker_summary: dict[str, Any] = {}
    ticker_pass = True
    f1_cells = cells[cells["arm"].eq("F1")].set_index("cell_id")
    for ticker, part in paired.groupby("ticker", observed=True, sort=True):
        ticker_valid = part[part["valid_pair"]]
        primary = ticker_valid[ticker_valid["horizon"].isin(GATE_SPEC["primary_horizons"])]
        f1_auc = pd.to_numeric(f1_cells.loc[ticker_valid["cell_id"], "roc_auc"], errors="coerce") if len(ticker_valid) else pd.Series(dtype=float)
        primary_f1_auc = pd.to_numeric(f1_cells.loc[primary["cell_id"], "roc_auc"], errors="coerce") if len(primary) else pd.Series(dtype=float)
        data = {
            "valid_cells": int(len(ticker_valid)),
            "wins": int((pd.to_numeric(ticker_valid["auc_delta"], errors="coerce") > 0.0).sum()),
            "median_auc_delta": float(pd.to_numeric(ticker_valid["auc_delta"], errors="coerce").median()) if len(ticker_valid) else None,
            "median_f1_auc": float(f1_auc.median()) if len(f1_auc) else None,
            "primary_valid_cells": int(len(primary)),
            "primary_wins": int((pd.to_numeric(primary["auc_delta"], errors="coerce") > 0.0).sum()),
            "primary_median_auc_delta": float(pd.to_numeric(primary["auc_delta"], errors="coerce").median()) if len(primary) else None,
            "primary_median_f1_auc": float(primary_f1_auc.median()) if len(primary_f1_auc) else None,
        }
        data["passed"] = bool(
            data["valid_cells"] == 8
            and data["wins"] >= GATE_SPEC["ticker_minimum_wins"]
            and data["median_auc_delta"] is not None and data["median_auc_delta"] > 0.0
            and data["median_f1_auc"] is not None and data["median_f1_auc"] >= GATE_SPEC["ticker_minimum_median_f1_auc"]
            and data["primary_valid_cells"] == 4
            and data["primary_wins"] >= GATE_SPEC["ticker_primary_minimum_wins"]
            and data["primary_median_auc_delta"] is not None and data["primary_median_auc_delta"] > 0.0
            and data["primary_median_f1_auc"] is not None and data["primary_median_f1_auc"] >= GATE_SPEC["ticker_minimum_median_f1_auc"]
        )
        ticker_pass &= data["passed"]
        ticker_summary[str(ticker)] = data
    primary_months = monthly[monthly["horizon"].isin(GATE_SPEC["primary_horizons"])]
    frequency_pass = bool(
        len(primary_months) == 3 * 2 * 2 * 12
        and primary_months["resolved_episodes"].ge(GATE_SPEC["minimum_monthly_resolved_episodes"]).all()
        and primary_months["both_classes"].all()
    )
    ap_delta = pd.to_numeric(paired["average_precision_delta"], errors="coerce")
    ll_delta = pd.to_numeric(paired["log_loss_delta"], errors="coerce")
    joint_losses = int((~valid | ((ap_delta < 0.0) & (ll_delta > 0.0))).sum())
    calibration_pass = bool(joint_losses <= GATE_SPEC["maximum_joint_ap_logloss_losses"])
    physical_pass = bool(aggregate_pass and ticker_pass and frequency_pass and calibration_pass)
    provenance_pass = provenance_status == "PASS"
    live_parity_pass = live_parity_status == "PASS"
    return {
        "planned_paired_cells": 24,
        "valid_paired_cells": int(valid.sum()),
        "favorable_outer_cells": wins,
        "favorable_outer_cell_rate": float(wins / 24.0),
        "median_auc_delta": float(deltas.median()) if len(deltas) else None,
        "wilcoxon_one_sided_p": pvalue,
        "wilcoxon_cluster_count": int(len(cluster_deltas)),
        "wilcoxon_test_unit": GATE_SPEC["paired_test_unit"],
        "joint_average_precision_logloss_losses": joint_losses,
        "aggregate_pass": aggregate_pass,
        "ticker_pass": bool(ticker_pass),
        "frequency_pass": frequency_pass,
        "calibration_pass": calibration_pass,
        "ticker_summary": ticker_summary,
        "physical_mechanism_pass": physical_pass,
        "historical_timestamp_provenance_status": provenance_status,
        "live_feature_parity_status": live_parity_status,
        "authoritative_physical_success": bool(physical_pass and provenance_pass),
        "advance_to_option_payoff": bool(physical_pass and provenance_pass and live_parity_pass),
        "production_live_ready": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flow", required=True)
    parser.add_argument("--source-hashes", required=True)
    parser.add_argument("--data-manifest", required=True)
    parser.add_argument("--frozen-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(f"immutable evaluation output already exists: {output_dir}")
    staging = output_dir.with_name(f"{output_dir.name}.staging")
    if staging.exists():
        raise FileExistsError(f"evaluation staging directory exists; inspect manually: {staging}")
    commit = assert_committed_runner()
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    freeze = verify_freeze(
        Path(args.frozen_manifest),
        flow_path=Path(args.flow),
        source_hashes_path=Path(args.source_hashes),
        data_manifest_path=Path(args.data_manifest),
    )
    flow = pd.read_parquet(args.flow)
    assert_surface_flow_schema(flow)
    if flow["trade_date"].astype(str).str.startswith("2026").any() or str(flow["trade_date"].max()) > END_DATE:
        raise AssertionError("2026 or post-cutoff data entered frozen physical evaluation")
    source_hashes = pd.read_csv(args.source_hashes, dtype={"trade_date": str})
    assert_source_inventory(source_hashes)
    staging.mkdir(parents=True, exist_ok=False)
    labeled, label_errors = add_future_labels(flow, source_hashes, int(args.workers))
    if label_errors:
        raise AssertionError(f"physical label build errors: {label_errors[:10]}")
    if len(labeled) != len(flow) or labeled.duplicated(list(KEY_COLUMNS)).any():
        raise AssertionError(f"labeled candidate parity failed: {len(labeled)}/{len(flow)}")
    labels_path = staging / "labeled_physical_episodes.parquet"
    labeled.to_parquet(labels_path, index=False)
    model_dir = staging / "models"
    cells, paired, monthly, predictions, calibration, models = evaluate_cells(labeled, model_dir)
    if "model_path" in cells:
        cells["model_path"] = cells["model_path"].map(
            lambda value: f"models/{Path(str(value)).name}" if pd.notna(value) and str(value) else value
        )
    if "path" in models:
        models["path"] = models["path"].map(lambda value: f"models/{Path(str(value)).name}")
    summary = summarize_gate(
        cells,
        paired,
        monthly,
        provenance_status=str(freeze.get("historical_timestamp_provenance_status", "BLOCKED")),
        live_parity_status=str(freeze.get("live_feature_parity_status", "BLOCKED")),
    )
    paths = {
        "labeled_physical_episodes": labels_path,
        "cells": staging / "cells.csv",
        "paired_cells": staging / "paired_cells.csv",
        "monthly_coverage": staging / "monthly_coverage.csv",
        "predictions": staging / "predictions.parquet",
        "calibration": staging / "calibration.csv",
        "model_hashes": staging / "model_hashes.csv",
        "summary": staging / "summary.json",
    }
    cells.to_csv(paths["cells"], index=False)
    paired.to_csv(paths["paired_cells"], index=False)
    monthly.to_csv(paths["monthly_coverage"], index=False)
    predictions.to_parquet(paths["predictions"], index=False)
    calibration.to_csv(paths["calibration"], index=False)
    models.to_csv(paths["model_hashes"], index=False)
    paths["summary"].write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    manifest = {
        "schema": "wall_surface_flow_at_touch_physical_evaluation_v1r1",
        "git_commit": commit,
        "production_modified": False,
        "holdout_2026_used": False,
        "frozen_manifest_sha256": sha256_file(args.frozen_manifest),
        "runner_sha256": sha256_file(__file__),
        "feature_module_sha256": sha256_file(Path(__file__).with_name("surface_flow_features.py")),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment": runtime["environment"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "flow_dataset_sha256": sha256_file(args.flow),
        "source_file_hashes_sha256": sha256_file(args.source_hashes),
        "labeled_rows": int(len(labeled)),
        "labeled_rows_by_ticker": labeled.groupby("ticker", observed=True).size().astype(int).to_dict(),
        "label_errors": label_errors,
        "artifact_hashes": {name: sha256_file(path) for name, path in paths.items()},
        "model_count": int(len(models)),
        "model_set_sha256": hash_list(models["sha256"].astype(str).tolist()) if len(models) else None,
        "seed": SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "summary": summary,
    }
    manifest_path = staging / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    staging.rename(output_dir)
    print(json.dumps(manifest, indent=2, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
