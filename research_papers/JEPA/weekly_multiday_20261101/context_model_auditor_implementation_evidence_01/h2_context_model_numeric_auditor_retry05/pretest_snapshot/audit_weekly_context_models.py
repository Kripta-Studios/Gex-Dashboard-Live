from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import random
import statistics
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any

import numpy as np


CONTRACT = Path(__file__).with_name("CONTEXT_MODEL_COMPARISON_CONTRACT_20261101.md")
CONTRACT_SHA256 = "8a535acd67ae36e6854ccf3aa02ab0f4f699c08be91bbeae5e17f7925e670ca4"
PRODUCER_SHA256 = "bdc6534f059ade7acc58f23952a88ed2068c7a712518b04f438945a583a07a2f"
DATASET_MANIFEST_SHA256 = (
    "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8"
)
FROZEN_EVAL_MANIFEST_SHA256 = (
    "54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96"
)
CONTEXT_MANIFEST_SHA256 = (
    "77aaf00d60accc071ff1f58ec099cee72bc3a4150f89e4ad41a601821a74a38a"
)
RISK_MANIFEST_SHA256 = (
    "50fa6b7a02aad9d122dc0bfdd84f8c01f9a5f468bafc7f175eed39aa3ea9418d"
)
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
DATASET_ROOT = BASE / "h2_dataset_v2_01"
FROZEN_EVAL_ROOT = BASE / "h2_ev_v2_01"
CONTEXT_ROOT = BASE / "h2_context_1030_01"
RISK_ROOT = BASE / "h2_equal_risk_frozen_01"
DEFAULT_OUTPUT = BASE / "h2_context_model_comparison_audit_01"
TICKERS = ("SPY", "QQQ", "SPXW")
RIGHTS = ("CALL", "PUT")
WEEKDAYS = tuple(range(5))
FEATURE18 = (
    "ticker_SPY",
    "ticker_QQQ",
    "ticker_SPXW",
    "right_call",
    "dte",
    "weekday",
    "spot",
    "strike",
    "moneyness",
    "bid",
    "ask",
    "spread_relative",
    "delta",
    "implied_vol",
    "gamma",
    "theta",
    "vega",
    "rho",
)
MODELS = ("BASE18_FROZEN", "CATEGORY30", "CONTEXT182")
COSTS = ("base", "adverse")
STARTING_CASH = 100_000.0
BUDGET_CENTS = 500_000
COMMISSION = 1.30
PRODUCER_NAME = "evaluate_weekly_context_models.py"
EVALUATOR_NAME = "evaluate_weekly_h2_ev_v2.py"
EVALUATOR_SHA256 = "8a9e75855d542a12662e5c812583f2ef86042f5c3ae1bbbad73c16042e063476"
REPLAY_NAME = "replay_equal_risk_frozen.py"
REPLAY_SHA256 = "e4f42a9fa65120939cf5e131911c8f2990a9cd33d21ae036fa98d9eb816d5b9d"
EXPECTED_OUTPUTS = {
    "category30_transform.json",
    "category30_model.json",
    "category30_calibration.json",
    "context182_transform.json",
    "context182_model.json",
    "context182_calibration.json",
    "candidate_scores_context_comparison.jsonl",
    *{
        f"ledger_{model.lower()}_eval_{cost}.jsonl"
        for model in MODELS
        for cost in COSTS
    },
    "summary.json",
}


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plain_path(path: Path, label: str, *, regular_file: bool = False) -> Path:
    """Reject links/reparse points before resolving any producer-supplied path."""
    absolute = Path(os.path.abspath(path))
    require(absolute.exists(), f"missing {label}")
    current = absolute
    while True:
        attributes = getattr(current.lstat(), "st_file_attributes", 0)
        require(
            not current.is_symlink() and not attributes & 0x400,
            f"link/reparse {label}",
        )
        if current.parent == current:
            break
        current = current.parent
    if regular_file:
        require(absolute.is_file(), f"regular file {label}")
    return absolute


def file_pin(path: Path) -> dict[str, Any]:
    path = plain_path(path, str(path), regular_file=True)
    return {"bytes": path.stat().st_size, "sha256": sha256_file(path)}


def verify_file_pin(path: Path, expected: dict[str, Any], label: str) -> dict[str, Any]:
    require(
        isinstance(expected, dict) and set(expected) >= {"bytes", "sha256"},
        f"pin shape {label}",
    )
    actual = file_pin(plain_path(path, label, regular_file=True))
    require(
        actual == {"bytes": expected["bytes"], "sha256": expected["sha256"]},
        f"pin {label}",
    )
    return actual


def read_json_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(plain_path(path, label, regular_file=True).read_text("utf-8"))
    require(isinstance(value, dict), f"JSON object {label}")
    return value


def read_jsonl_objects(path: Path, label: str) -> list[dict[str, Any]]:
    rows = []
    path = plain_path(path, label, regular_file=True)
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL {label}:{number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"JSON object {label}:{number}")
            rows.append(value)
    return rows


def admit_comparison_package(
    *,
    comparison_root: Path,
    comparison_manifest_sha256: str,
    external_manifest_paths: dict[str, Path],
    expected_external_sha256: dict[str, str],
    producer_path: Path,
    producer_sha256: str,
) -> dict[str, Any]:
    """Metadata-first admission; no score, transform, or outcome is parsed."""
    require(sha256_file(CONTRACT) == CONTRACT_SHA256, "contract pin")
    root = plain_path(comparison_root, "comparison root")
    require(root.is_dir(), "comparison root directory")
    manifest_path = plain_path(
        root / "manifest.json", "comparison manifest", regular_file=True
    )
    manifest_pin = file_pin(manifest_path)
    require(
        manifest_pin["sha256"] == comparison_manifest_sha256,
        "comparison manifest authority",
    )
    require(
        set(external_manifest_paths) == set(expected_external_sha256),
        "external manifest authority set",
    )
    external_pins = {}
    for name, path in external_manifest_paths.items():
        actual = file_pin(
            plain_path(path, f"external manifest {name}", regular_file=True)
        )
        require(
            actual["sha256"] == expected_external_sha256[name],
            f"external manifest authority {name}",
        )
        external_pins[name] = {"path": str(path), **actual}
    producer = file_pin(
        plain_path(producer_path, "comparison producer", regular_file=True)
    )
    require(producer["sha256"] == producer_sha256, "comparison producer authority")
    manifest = read_json_object(manifest_path, "comparison manifest")
    require(
        manifest.get("schema") == "weekly_h2_context_model_comparison_manifest_v1",
        "comparison manifest schema",
    )
    require(
        manifest.get("external_manifests") == expected_external_sha256,
        "external manifest binding",
    )
    expected_implementation = {
        PRODUCER_NAME: producer_sha256,
        EVALUATOR_NAME: EVALUATOR_SHA256,
        REPLAY_NAME: REPLAY_SHA256,
        CONTRACT.name: CONTRACT_SHA256,
    }
    require(
        manifest.get("implementation") == expected_implementation,
        "implementation binding",
    )
    outputs = manifest.get("outputs")
    require(
        isinstance(outputs, dict) and set(outputs) == EXPECTED_OUTPUTS, "output set"
    )
    output_pins = {
        name: verify_file_pin(root / name, expected, f"output {name}")
        for name, expected in outputs.items()
    }
    consumed = manifest.get("consumed_payloads")
    require(isinstance(consumed, dict) and consumed, "consumed payload binding")
    consumed_pins = {}
    for raw_path, expected in consumed.items():
        require(isinstance(raw_path, str) and raw_path, "consumed payload path")
        path = Path(raw_path)
        consumed_pins[raw_path] = verify_file_pin(
            path, expected, f"consumed payload {raw_path}"
        )
    return {
        "root": str(root),
        "manifest": manifest,
        "manifest_pin": manifest_pin,
        "external_pins": external_pins,
        "producer": {"path": str(producer_path), **producer},
        "output_pins": output_pins,
        "consumed_pins": consumed_pins,
    }


def revalidate_comparison_package(admission: dict[str, Any]) -> None:
    """Closing rehash of every authority and payload admitted before values."""
    root = plain_path(Path(admission["root"]), "comparison root")
    verify_file_pin(
        root / "manifest.json", admission["manifest_pin"], "closing manifest"
    )
    verify_file_pin(
        Path(admission["producer"]["path"]),
        {
            "bytes": admission["producer"]["bytes"],
            "sha256": admission["producer"]["sha256"],
        },
        "closing producer",
    )
    for name, value in admission["external_pins"].items():
        verify_file_pin(
            Path(value["path"]),
            {"bytes": value["bytes"], "sha256": value["sha256"]},
            f"closing external {name}",
        )
    for name, expected in admission["output_pins"].items():
        verify_file_pin(root / name, expected, f"closing output {name}")
    for raw_path, expected in admission["consumed_pins"].items():
        verify_file_pin(Path(raw_path), expected, f"closing consumed {raw_path}")


def category_names() -> list[str]:
    return [
        f"{ticker}:{right}:weekday{weekday}"
        for ticker in TICKERS
        for right in RIGHTS
        for weekday in WEEKDAYS
    ]


def category30(row: dict[str, Any]) -> list[float]:
    weekday = int(row["features"]["weekday"])
    require(
        row["ticker"] in TICKERS and row["right"] in RIGHTS and weekday in WEEKDAYS,
        "category identity",
    )
    index = (
        TICKERS.index(row["ticker"]) * 2 + RIGHTS.index(row["right"])
    ) * 5 + weekday
    output = [0.0] * 30
    output[index] = 1.0
    return output


def context_names(feature_names: list[str]) -> list[str]:
    require(
        len(feature_names) == 81 and len(set(feature_names)) == 81,
        "context feature names",
    )
    return [
        *FEATURE18,
        *[f"context:{name}" for name in feature_names],
        *[f"side_context:{name}" for name in feature_names],
        "source_available",
        "state_valid",
    ]


def context182(row: dict[str, Any], context: dict[str, Any]) -> list[float]:
    status, valid = context.get("status"), context.get("state_valid")
    if status == "CONTEXT_MISSING_SOURCE":
        require(
            valid is None and context.get("context_81") is None,
            "missing context semantics",
        )
        vector, flags = [0.0] * 81, [0.0, 0.0]
    else:
        require(
            status == "CONTEXT_AVAILABLE" and isinstance(valid, bool),
            "available context semantics",
        )
        raw = context.get("context_81")
        require(isinstance(raw, list) and len(raw) == 81, "context shape")
        require(
            all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
                for value in raw
            ),
            "context finite",
        )
        vector = [float(value) for value in raw] if valid else [0.0] * 81
        flags = [1.0, float(valid)]
    original = []
    for name in FEATURE18:
        value = row["features"][name]
        original.append(math.nan if value is None else float(value))
    sign = 1.0 if row["right"] == "CALL" else -1.0
    output = [*original, *vector, *[sign * value for value in vector], *flags]
    require(len(output) == 182, "CONTEXT182 width")
    return output


def join_context(
    candidates: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
) -> None:
    context_index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in context_rows:
        key = (row.get("ticker"), row.get("date"))
        require(
            key[0] in TICKERS and isinstance(key[1], str) and key not in context_index,
            "duplicate/bad context key",
        )
        context_index[key] = row
    coverage_index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in coverage_rows:
        key = (row.get("ticker"), row.get("date"))
        require(key not in coverage_index, "duplicate context coverage key")
        coverage_index[key] = row
    require(
        set(context_index) == set(coverage_index), "context/coverage identity mismatch"
    )
    for candidate in candidates:
        key = (candidate["ticker"], candidate["entry_date"])
        require(key in context_index, "candidate lacks context")
        context = context_index[key]
        candidate["_x_category"] = category30(candidate)
        candidate["_x_context"] = context182(candidate, context)
        candidate["_context_status"] = context["status"]
        candidate["_context_state_valid"] = context["state_valid"]


def split_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    output = {"TRAIN": [], "CAL": [], "EVAL": []}
    for row in rows:
        day = row["entry_date"]
        available = datetime.fromisoformat(row["label_available_at"])
        if "20230103" <= day <= "20241231":
            split, cutoff = "TRAIN", datetime.fromisoformat("2025-01-01T00:00:00-05:00")
        elif "20250101" <= day <= "20251231":
            split, cutoff = "CAL", datetime.fromisoformat("2026-01-01T00:00:00-05:00")
        elif "20260101" <= day <= "20260630":
            split, cutoff = "EVAL", None
        else:
            raise AuditError("candidate outside fixed splits")
        row["_split"] = split
        row["_model_label_eligible"] = cutoff is None or available < cutoff
        output[split].append(row)
    return output


def probability_metrics(
    rows: list[dict[str, Any]],
    model: str,
    *,
    selected_ids: set[str] | None = None,
    observed_only: bool = False,
) -> dict[str, Any]:
    values = [
        row
        for row in rows
        if row["_model_label_eligible"]
        and (selected_ids is None or row["candidate_id"] in selected_ids)
        and (not observed_only or not row["payoff_is_lower_bound"])
    ]
    if not values:
        return {"n": 0, "log_loss": None, "brier": None, "reliability": []}
    probabilities = np.asarray([row[f"_p_{model}"] for row in values], dtype=float)
    labels = np.asarray([row["scenario"] for row in values], dtype=int)
    targets = np.eye(5)[labels]
    reliability = []
    for label in range(5):
        for index in range(10):
            low, high = index / 10, (index + 1) / 10
            mask = (
                (probabilities[:, label] >= low) & (probabilities[:, label] <= high)
                if index == 9
                else (probabilities[:, label] >= low) & (probabilities[:, label] < high)
            )
            if mask.any():
                reliability.append(
                    {
                        "class": label,
                        "bin_low": low,
                        "bin_high": high,
                        "n": int(mask.sum()),
                        "predicted": float(probabilities[mask, label].mean()),
                        "observed": float((labels[mask] == label).mean()),
                    }
                )
    return {
        "n": len(values),
        "log_loss": log_loss(labels, probabilities),
        "brier": float(np.square(probabilities - targets).sum(axis=1).mean()),
        "reliability": reliability,
    }


def ev_metrics(
    rows: list[dict[str, Any]],
    model: str,
    *,
    selected_ids: set[str] | None = None,
    observed_only: bool = False,
) -> dict[str, Any]:
    values = [
        row
        for row in rows
        if row["_model_label_eligible"]
        and (selected_ids is None or row["candidate_id"] in selected_ids)
        and (not observed_only or not row["payoff_is_lower_bound"])
    ]
    output: dict[str, Any] = {}
    for cost in COSTS:
        errors = [
            float(row[f"_ev_{model}_{cost}"]) - float(row[f"net_{cost}"])
            for row in values
        ]
        output[cost] = {
            "n": len(errors),
            "bias": math.fsum(errors) / len(errors) if errors else None,
            "mae": math.fsum(abs(value) for value in errors) / len(errors)
            if errors
            else None,
        }
    return output


def _raw_matrix(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    values = np.asarray([row[key] for row in rows], dtype=float)
    require(values.ndim == 2 and len(values) > 0, "matrix shape")
    return values


def independently_recompute_transform(train: np.ndarray) -> dict[str, Any]:
    require(train.ndim == 2 and len(train) > 0, "TRAIN matrix")
    missing = np.isnan(train)
    medians = []
    for index in range(train.shape[1]):
        observed = train[~missing[:, index], index]
        medians.append(float(np.median(observed)) if len(observed) else 0.0)
    median_array = np.asarray(medians)
    imputed = np.where(missing, median_array, train)
    indices = np.flatnonzero(missing.any(axis=0)).astype(int).tolist()
    transformed = (
        np.concatenate([imputed, missing[:, indices].astype(float)], axis=1)
        if indices
        else imputed
    )
    mean = transformed.mean(axis=0)
    variance = transformed.var(axis=0)
    # StandardScaler detects constants on the variance, using the theoretical
    # float64 two-pass error bound from Chan, Golub and LeVeque.  A decimal
    # constant such as 0.1 can otherwise retain a non-zero residual std.
    epsilon = np.finfo(np.float64).eps
    sample_count = transformed.shape[0]
    upper_bound = sample_count * epsilon * variance + np.square(
        sample_count * mean * epsilon
    )
    scale = np.sqrt(variance)
    scale[variance <= upper_bound] = 1.0
    return {
        "medians": median_array,
        "indicator_indices": indices,
        "mean": mean,
        "scale": scale,
    }


def validate_transform(
    train: np.ndarray, feature_names: list[str], saved: dict[str, Any]
) -> None:
    require(saved.get("feature_order") == feature_names, "transform feature order")
    require(saved.get("fit_scope") == "TRAIN_ONLY", "transform fit scope")
    require(
        saved.get("imputer")
        == {"strategy": "median", "add_indicator": True, "keep_empty_features": True},
        "imputer config",
    )
    independent = independently_recompute_transform(train)
    indices = independent["indicator_indices"]
    require(
        saved.get("missing_indicator_source_indices") == indices,
        "missing indicator indices",
    )
    expected_indicator_names = [f"{feature_names[index]}__missing" for index in indices]
    require(
        saved.get("missing_indicator_order") == expected_indicator_names,
        "missing indicator order",
    )
    for key, expected in (
        ("medians", independent["medians"]),
        ("scaler_mean", independent["mean"]),
        ("scaler_scale", independent["scale"]),
    ):
        actual = np.asarray(saved.get(key), dtype=float)
        require(
            actual.shape == expected.shape
            and np.allclose(actual, expected, atol=1e-12, rtol=1e-12),
            f"saved transform {key}",
        )


def apply_saved_transform(values: np.ndarray, saved: dict[str, Any]) -> np.ndarray:
    medians = np.asarray(saved["medians"], dtype=float)
    indices = list(saved["missing_indicator_source_indices"])
    require(
        values.ndim == 2 and values.shape[1] == len(medians), "transform input width"
    )
    missing = np.isnan(values)
    imputed = np.where(missing, medians, values)
    expanded = (
        np.concatenate([imputed, missing[:, indices].astype(float)], axis=1)
        if indices
        else imputed
    )
    mean, scale = (
        np.asarray(saved["scaler_mean"], dtype=float),
        np.asarray(saved["scaler_scale"], dtype=float),
    )
    require(
        expanded.shape[1] == len(mean) == len(scale)
        and np.all(np.isfinite(scale))
        and np.all(scale > 0),
        "scaler schema",
    )
    return (expanded - mean) / scale


def restored_probabilities(
    values: np.ndarray, saved_model: dict[str, Any]
) -> np.ndarray:
    require(
        saved_model.get("type") == "LogisticRegression"
        and saved_model.get("fit_scope") == "TRAIN_ONLY",
        "model schema",
    )
    require(
        saved_model.get("C") == 1.0
        and saved_model.get("solver") == "lbfgs"
        and saved_model.get("max_iter") == 2000
        and saved_model.get("random_state") == 0,
        "model parameters",
    )
    require(
        saved_model.get("classes_full") == list(range(5))
        and isinstance(saved_model.get("sklearn_version"), str)
        and bool(saved_model["sklearn_version"])
        and isinstance(saved_model.get("fit_warnings"), list)
        and all(isinstance(value, str) for value in saved_model["fit_warnings"]),
        "model metadata",
    )
    classes = [int(value) for value in saved_model["classes_present"]]
    require(
        classes == sorted(set(classes)) and all(0 <= value < 5 for value in classes),
        "model classes",
    )
    coefficient = np.asarray(saved_model["coefficient"], dtype=float)
    intercept = np.asarray(saved_model["intercept"], dtype=float)
    require(
        coefficient.shape == (len(classes), values.shape[1])
        and intercept.shape == (len(classes),),
        "coefficient shape",
    )
    logits = values @ coefficient.T + intercept
    logits -= logits.max(axis=1, keepdims=True)
    partial = np.exp(logits)
    partial /= partial.sum(axis=1, keepdims=True)
    output = np.zeros((len(values), 5), dtype=float)
    output[:, classes] = partial
    return output


def log_loss(labels: np.ndarray, probabilities: np.ndarray) -> float:
    return float(
        -np.log(
            np.clip(probabilities[np.arange(len(labels)), labels], 1e-12, 1.0)
        ).mean()
    )


def validate_calibration(
    model_prob: np.ndarray, labels: np.ndarray, prior: np.ndarray, saved: dict[str, Any]
) -> np.ndarray:
    expected_grid = []
    for step in range(11):
        alpha = step / 10
        mixed = (1 - alpha) * model_prob + alpha * prior
        expected_grid.append({"alpha": alpha, "log_loss": log_loss(labels, mixed)})
    actual_grid = saved.get("scores")
    require(
        isinstance(actual_grid, list) and len(actual_grid) == 11, "calibration grid"
    )
    for actual, expected in zip(actual_grid, expected_grid, strict=True):
        require(
            actual.get("alpha") == expected["alpha"]
            and math.isclose(
                float(actual.get("log_loss")), expected["log_loss"], abs_tol=1e-12
            ),
            "calibration grid value",
        )
    best = min(expected_grid, key=lambda item: (item["log_loss"], item["alpha"]))
    require(saved.get("selected_alpha") == best["alpha"], "selected alpha")
    alpha = float(best["alpha"])
    return (1 - alpha) * model_prob + alpha * prior


def ev_values(
    rows: list[dict[str, Any]],
    probabilities: np.ndarray,
    means: dict[str, Any],
    cost: str,
) -> np.ndarray:
    output = []
    for row, probability in zip(rows, probabilities, strict=True):
        cell = means["cells"][cost][f"{row['ticker']}:{row['right']}"]
        conditional = np.asarray(
            [cell[str(label)]["mean_y"] for label in range(5)], dtype=float
        )
        output.append(
            float(row["decision_ask"]) * 100 * float(np.dot(probability, conditional))
        )
    return np.asarray(output)


def unit_risk_cents(ask: Any) -> int:
    value = (Decimal(str(ask)) + Decimal("0.02")) * Decimal(10_000) + Decimal(260)
    cents = int(value.to_integral_value(rounding=ROUND_CEILING))
    require(cents > 0, "unit risk")
    return cents


def direct_select(rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    if not rows:
        return None, "NO_SERIES"
    best = max(float(row["_ev_adverse"]) for row in rows)
    matches = [row for row in rows if float(row["_ev_adverse"]) == best]
    if best <= 0:
        return None, "EV_NOT_POSITIVE"
    return (matches[0], "EV_TOP1") if len(matches) == 1 else (None, "EV_TIE_WAIT")


def replay_risk(
    rows: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
    sessions: list[str],
    last_entry: str,
) -> dict[str, list[dict[str, Any]]]:
    by_identity: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_identity[(row["entry_date"], row["ticker"])].append(row)
    coverage = {(row["ticker"], row["entry_date"]): row for row in coverage_rows}
    opened: dict[str, tuple[dict[str, Any], int, int, int]] = {}
    cash = {cost: STARTING_CASH for cost in COSTS}
    reserved = {cost: 0.0 for cost in COSTS}
    exit_fees = {cost: 0.0 for cost in COSTS}
    ledgers = {cost: [] for cost in COSTS}
    for day in sessions:
        for ticker in TICKERS:
            if ticker not in opened or opened[ticker][0]["exit_date"] != day:
                continue
            row, quantity, decision_risk, entry_risk = opened.pop(ticker)
            bid = 0.0 if row["exit_bid"] is None else float(row["exit_bid"])
            for cost, slippage in (("base", 0.01), ("adverse", 0.02)):
                principal = quantity * (float(row["entry_ask"]) + slippage) * 100
                credit = quantity * (max(bid - slippage, 0.0) * 100 - COMMISSION)
                cash[cost] += credit
                reserved[cost] -= principal
                exit_fees[cost] -= quantity * COMMISSION
                net = quantity * float(row[f"net_{cost}"])
                require(
                    math.isclose(
                        credit - quantity * float(row[f"entry_debit_{cost}"]),
                        net,
                        abs_tol=1e-6,
                    ),
                    "quantity net reconciliation",
                )
                ledgers[cost].append(
                    {
                        "event": "EXIT",
                        "date": day,
                        "ticker": ticker,
                        "cost": cost,
                        "candidate_id": row["candidate_id"],
                        "right": row["right"],
                        "status": row["status"],
                        "entry_date": row["entry_date"],
                        "quantity": quantity,
                        "decision_unit_risk_cents": decision_risk,
                        "entry_unit_risk_cents": entry_risk,
                        "net_usd": net,
                        "cash": cash[cost],
                        "premium_reserved": reserved[cost],
                        "exit_fee_obligation": exit_fees[cost],
                        "equity_realized": cash[cost] + reserved[cost],
                        "realized_delta": net + quantity * COMMISSION,
                        "principal": principal,
                    }
                )
        for ticker in TICKERS:
            if day > last_entry:
                continue
            candidates = by_identity.get((day, ticker), [])
            if ticker in opened:
                for cost in COSTS:
                    ledgers[cost].append(
                        {
                            "event": "WAIT",
                            "date": day,
                            "ticker": ticker,
                            "cost": cost,
                            "reason": "OPEN_POSITION",
                        }
                    )
                continue
            if not candidates:
                item = coverage[(ticker, day)]
                for cost in COSTS:
                    ledgers[cost].append(
                        {
                            "event": "NO_OPPORTUNITY",
                            "date": day,
                            "ticker": ticker,
                            "cost": cost,
                            "reason": item.get("reason") or item["status"],
                        }
                    )
                continue
            selected, reason = direct_select(candidates)
            if selected is None:
                for cost in COSTS:
                    ledgers[cost].append(
                        {
                            "event": "WAIT",
                            "date": day,
                            "ticker": ticker,
                            "cost": cost,
                            "reason": reason,
                        }
                    )
                continue
            decision_risk = unit_risk_cents(selected["decision_ask"])
            quantity = BUDGET_CENTS // decision_risk
            common = {
                "candidate_id": selected["candidate_id"],
                "quantity": quantity,
                "decision_unit_risk_cents": decision_risk,
            }
            if quantity < 1 or selected["status"] == "NO_FILL":
                why = "DECISION_RISK_BUDGET" if quantity < 1 else "ENTRY_QUOTE"
                for cost in COSTS:
                    ledgers[cost].append(
                        {
                            "event": "NO_FILL",
                            "date": day,
                            "ticker": ticker,
                            "cost": cost,
                            "reason": why,
                            **common,
                        }
                    )
                continue
            entry_risk = unit_risk_cents(selected["entry_ask"])
            common["entry_unit_risk_cents"] = entry_risk
            if quantity * entry_risk > BUDGET_CENTS:
                for cost in COSTS:
                    ledgers[cost].append(
                        {
                            "event": "NO_FILL",
                            "date": day,
                            "ticker": ticker,
                            "cost": cost,
                            "reason": "ENTRY_RISK_BUDGET",
                            **common,
                        }
                    )
                continue
            debit = {
                cost: quantity * float(selected[f"entry_debit_{cost}"])
                for cost in COSTS
            }
            new_exit_fee = quantity * COMMISSION
            if not all(
                cash[cost] - exit_fees[cost] >= debit[cost] + new_exit_fee
                for cost in COSTS
            ):
                for cost in COSTS:
                    ledgers[cost].append(
                        {
                            "event": "CAPITAL_BLOCKED",
                            "date": day,
                            "ticker": ticker,
                            "cost": cost,
                            "reason": "CAPITAL",
                            **common,
                        }
                    )
                continue
            opened[ticker] = (selected, quantity, decision_risk, entry_risk)
            for cost, slippage in (("base", 0.01), ("adverse", 0.02)):
                cash[cost] -= debit[cost]
                principal = quantity * (float(selected["entry_ask"]) + slippage) * 100
                reserved[cost] += principal
                exit_fees[cost] += new_exit_fee
                ledgers[cost].append(
                    {
                        "event": "ENTRY",
                        "date": day,
                        "ticker": ticker,
                        "cost": cost,
                        "candidate_id": selected["candidate_id"],
                        "right": selected["right"],
                        "exit_date": selected["exit_date"],
                        "selection_reason": reason,
                        "quantity": quantity,
                        "decision_unit_risk_cents": decision_risk,
                        "decision_budget_used_cents": quantity * decision_risk,
                        "entry_unit_risk_cents": entry_risk,
                        "entry_budget_used_cents": quantity * entry_risk,
                        "ev_base": selected["_ev_base"],
                        "ev_adverse": selected["_ev_adverse"],
                        "cash": cash[cost],
                        "premium_reserved": reserved[cost],
                        "exit_fee_obligation": exit_fees[cost],
                        "equity_realized": cash[cost] + reserved[cost],
                        "realized_delta": -quantity * COMMISSION,
                        "principal": principal,
                    }
                )
    require(not opened, "positions remain open")
    for cost in COSTS:
        require(
            abs(reserved[cost]) <= 1e-7 and abs(exit_fees[cost]) <= 1e-7,
            "reserves close",
        )
        net = math.fsum(
            row["net_usd"] for row in ledgers[cost] if row["event"] == "EXIT"
        )
        require(
            math.isclose(cash[cost], STARTING_CASH + net, abs_tol=1e-6),
            "cash reconciliation",
        )
    return ledgers


def selected_ids(ledger: list[dict[str, Any]]) -> set[str]:
    return {
        row["candidate_id"]
        for row in ledger
        if row["event"] in {"ENTRY", "NO_FILL", "CAPITAL_BLOCKED"}
        and "candidate_id" in row
    }


def book_metrics(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    exits = [row for row in ledger if row["event"] == "EXIT"]
    entries = [row for row in ledger if row["event"] == "ENTRY"]
    values = [float(row["net_usd"]) for row in exits]
    gains = math.fsum(value for value in values if value > 0)
    losses = -math.fsum(value for value in values if value < 0)
    equity, peak, drawdown = STARTING_CASH, STARTING_CASH, 0.0
    months: dict[str, float] = defaultdict(float)
    tickers = {ticker: 0.0 for ticker in TICKERS}
    for row in ledger:
        if row["event"] in {"ENTRY", "EXIT"}:
            equity += float(row["realized_delta"])
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        if row["event"] == "EXIT":
            months[row["date"][:6]] += float(row["net_usd"])
            tickers[row["ticker"]] += float(row["net_usd"])
    quantities = [int(row["quantity"]) for row in entries]
    return {
        "trades": len(exits),
        "net_usd": math.fsum(values),
        "profit_factor": gains / losses
        if losses
        else (None if gains == 0 else "Infinity"),
        "realized_max_drawdown_usd": drawdown,
        "months_observed": len(months),
        "positive_months": sum(value > 0 for value in months.values()),
        "monthly_net_usd": dict(sorted(months.items())),
        "ticker_net_usd": tickers,
        "quantity_total": sum(quantities),
        "quantity_max": max(quantities) if quantities else None,
        "quantity_median": statistics.median(quantities) if quantities else None,
        "max_premium_reserved": max(
            (float(row.get("premium_reserved", 0)) for row in ledger), default=0.0
        ),
        "max_decision_budget_used_cents": max(
            (int(row.get("decision_budget_used_cents", 0)) for row in entries),
            default=0,
        ),
        "max_entry_budget_used_cents": max(
            (int(row.get("entry_budget_used_cents", 0)) for row in entries), default=0
        ),
        "no_fill_by_reason": {
            reason: sum(
                row["event"] == "NO_FILL" and row["reason"] == reason for row in ledger
            )
            for reason in ("DECISION_RISK_BUDGET", "ENTRY_RISK_BUDGET", "ENTRY_QUOTE")
        },
        "capital_blocked": sum(row["event"] == "CAPITAL_BLOCKED" for row in ledger),
        "wait": sum(row["event"] == "WAIT" for row in ledger),
        "no_opportunity": sum(row["event"] == "NO_OPPORTUNITY" for row in ledger),
        "missing_exit": sum(
            row.get("status") in {"MISSING_EXIT_QUOTE", "MISSING_EXIT_SOURCE"}
            for row in exits
        ),
        "capacity_assumption": "full fill at stored quote; no volume or partial-fill simulation",
    }


def percentile_type7(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def paired_bootstrap(
    rows: list[dict[str, Any]],
    sessions: list[str],
    *,
    resamples: int = 10_000,
    seed: int = 20_261_101,
    block: int = 5,
    expected_eligible: int | None = None,
) -> dict[str, Any]:
    require(
        len(sessions) == len(set(sessions)) and sessions == sorted(sessions),
        "session order/uniqueness",
    )
    by_day = {day: [0.0, 0] for day in sessions}
    eligible = [row for row in rows if row["_model_label_eligible"]]
    if expected_eligible is not None:
        require(
            len(eligible) == expected_eligible, "bootstrap eligible candidate count"
        )
    for row in eligible:
        require(row["entry_date"] in by_day, "EVAL row outside session calendar")
        label = int(row["scenario"])
        base = -math.log(max(float(row["_p_BASE18_FROZEN"][label]), 1e-12))
        context = -math.log(max(float(row["_p_CONTEXT182"][label]), 1e-12))
        value = base - context
        by_day[row["entry_date"]][0] += value
        by_day[row["entry_date"]][1] += 1
    generator, size, statistics_ = random.Random(seed), len(sessions), []
    require(size > 0, "no sessions")
    for _ in range(resamples):
        indices = []
        for _ in range(math.ceil(size / block)):
            start = generator.randrange(size)
            indices.extend((start + offset) % size for offset in range(block))
        numerator = math.fsum(by_day[sessions[index]][0] for index in indices[:size])
        denominator = sum(by_day[sessions[index]][1] for index in indices[:size])
        require(denominator > 0, "bootstrap zero denominator")
        statistics_.append(numerator / denominator)
    denominator = sum(value[1] for value in by_day.values())
    contributions = [
        {
            "date": day,
            "loss_sum_base_minus_context": by_day[day][0],
            "candidate_count": by_day[day][1],
        }
        for day in sessions
    ]
    return {
        "seed": seed,
        "block_sessions": block,
        "resamples": resamples,
        "sessions": size,
        "estimate": math.fsum(value[0] for value in by_day.values()) / denominator,
        "percentile_type7_2_5": percentile_type7(statistics_, 0.025),
        "percentile_type7_97_5": percentile_type7(statistics_, 0.975),
        "paired_daily_contributions": contributions,
        "interpretation": "exploratory post-development interval; no p-value or independent validation claim",
    }


def audit_saved_model(
    rows: list[dict[str, Any]],
    model_name: str,
    matrix_key: str,
    feature_names: list[str],
    transform: dict[str, Any],
    model: dict[str, Any],
    calibration: dict[str, Any],
    prior: np.ndarray,
    means: dict[str, Any],
) -> None:
    train = [
        row for row in rows if row["_split"] == "TRAIN" and row["_model_label_eligible"]
    ]
    cal = [
        row for row in rows if row["_split"] == "CAL" and row["_model_label_eligible"]
    ]
    validate_transform(_raw_matrix(train, matrix_key), feature_names, transform)
    all_values = apply_saved_transform(_raw_matrix(rows, matrix_key), transform)
    model_probability = restored_probabilities(all_values, model)
    cal_objects = {id(row) for row in cal}
    cal_indices = [index for index, row in enumerate(rows) if id(row) in cal_objects]
    calibrated_cal = validate_calibration(
        model_probability[cal_indices],
        np.asarray([row["scenario"] for row in cal], dtype=int),
        prior,
        calibration,
    )
    alpha = float(calibration["selected_alpha"])
    probability = (1 - alpha) * model_probability + alpha * prior
    require(
        np.allclose(probability[cal_indices], calibrated_cal, atol=1e-12, rtol=1e-12),
        "CAL probability",
    )
    for index, row in enumerate(rows):
        row[f"_p_{model_name}"] = probability[index].tolist()
    for cost in COSTS:
        values = ev_values(rows, probability, means, cost)
        for row, value in zip(rows, values, strict=True):
            row[f"_ev_{model_name}_{cost}"] = float(value)


def compare_scores(
    rows: list[dict[str, Any]],
    producer_scores: list[dict[str, Any]],
    frozen_scores: list[dict[str, Any]],
) -> None:
    producer = {row["candidate_id"]: row for row in producer_scores}
    frozen = {row["candidate_id"]: row for row in frozen_scores}
    require(
        len(producer) == len(producer_scores)
        and len(frozen) == len(frozen_scores)
        and len(producer) == len(rows) == len(frozen),
        "score universe",
    )
    expected_score_keys = {
        "candidate_id",
        "split",
        "scenario",
        "payoff_is_lower_bound",
        "context_status",
        "context_state_valid",
        *{f"p_{model.lower()}" for model in MODELS},
        *{f"ev_{model.lower()}_{cost}" for model in MODELS for cost in COSTS},
    }
    for row in rows:
        candidate_id = row["candidate_id"]
        actual, base = producer[candidate_id], frozen[candidate_id]
        require(
            set(actual) == expected_score_keys
            and actual["split"] == row["_split"]
            and actual["scenario"] == row["scenario"]
            and actual["payoff_is_lower_bound"] == row["payoff_is_lower_bound"]
            and actual["context_status"] == row["_context_status"]
            and actual["context_state_valid"] == row["_context_state_valid"],
            "score split/label",
        )
        require(
            base.get("scenario") == row["scenario"]
            and base.get("label_eligible") == row["_model_label_eligible"],
            "frozen score eligibility/label",
        )
        row["_p_BASE18_FROZEN"] = [float(value) for value in base["p_cal"]]
        for cost in COSTS:
            row[f"_ev_BASE18_FROZEN_{cost}"] = float(base[f"ev_{cost}"])
        for model in MODELS:
            expected_probability = row[f"_p_{model}"]
            expected_key = f"p_{model.lower()}"
            require(
                np.allclose(
                    np.asarray(actual[expected_key]),
                    np.asarray(expected_probability),
                    atol=1e-12,
                    rtol=1e-12,
                ),
                f"probability {model}",
            )
            for cost in COSTS:
                require(
                    math.isclose(
                        float(actual[f"ev_{model.lower()}_{cost}"]),
                        float(row[f"_ev_{model}_{cost}"]),
                        abs_tol=1e-9,
                    ),
                    f"EV {model} {cost}",
                )


def assert_equivalent(
    actual: Any,
    expected: Any,
    label: str,
    *,
    absolute_tolerance: float = 1e-9,
) -> None:
    """Compare an independently rebuilt object with a producer object."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict), f"{label} type")
        require(set(actual) == set(expected), f"{label} keys")
        for key in expected:
            assert_equivalent(
                actual[key],
                expected[key],
                f"{label}.{key}",
                absolute_tolerance=absolute_tolerance,
            )
        return
    if isinstance(expected, list):
        require(
            isinstance(actual, list) and len(actual) == len(expected), f"{label} list"
        )
        for index, value in enumerate(expected):
            assert_equivalent(
                actual[index],
                value,
                f"{label}[{index}]",
                absolute_tolerance=absolute_tolerance,
            )
        return
    if (
        isinstance(expected, (int, float))
        and not isinstance(expected, bool)
        and isinstance(actual, (int, float))
        and not isinstance(actual, bool)
    ):
        require(
            math.isclose(
                float(actual),
                float(expected),
                rel_tol=1e-12,
                abs_tol=absolute_tolerance,
            ),
            f"{label} numeric",
        )
        return
    require(actual == expected, f"{label} value")


def _prepare_replay_rows(
    rows: list[dict[str, Any]], model: str
) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        value = dict(row)
        value["_ev_base"] = row[f"_ev_{model}_base"]
        value["_ev_adverse"] = row[f"_ev_{model}_adverse"]
        output.append(value)
    return output


def independently_rebuild_summary(
    rows: list[dict[str, Any]],
    splits: dict[str, list[dict[str, Any]]],
    books: dict[str, dict[str, list[dict[str, Any]]]],
    sessions: list[str],
    *,
    bootstrap_resamples: int = 10_000,
    expected_eval_eligible: int | None = None,
) -> dict[str, Any]:
    eval_rows = splits["EVAL"]
    selected = {}
    for model in MODELS:
        selected[model] = selected_ids(books[model]["adverse"])
        require(
            selected[model] == selected_ids(books[model]["base"]),
            f"shared decisions {model}",
        )
    metrics = {}
    for model in MODELS:
        model_selected = selected[model]
        metrics[model] = {
            "probability_all": probability_metrics(eval_rows, model),
            "probability_observed_only": probability_metrics(
                eval_rows, model, observed_only=True
            ),
            "probability_selected": probability_metrics(
                eval_rows, model, selected_ids=model_selected
            ),
            "probability_selected_observed_only": probability_metrics(
                eval_rows,
                model,
                selected_ids=model_selected,
                observed_only=True,
            ),
            "ev_all": ev_metrics(eval_rows, model),
            "ev_selected": ev_metrics(eval_rows, model, selected_ids=model_selected),
            "ev_observed_only": ev_metrics(eval_rows, model, observed_only=True),
            "ev_selected_observed_only": ev_metrics(
                eval_rows,
                model,
                selected_ids=model_selected,
                observed_only=True,
            ),
            "lower_bound": {
                "all": sum(row["payoff_is_lower_bound"] for row in eval_rows),
                "selected": sum(
                    row["candidate_id"] in model_selected
                    and row["payoff_is_lower_bound"]
                    for row in eval_rows
                ),
            },
            "descriptive_by_split": {
                name: {
                    "probability": probability_metrics(values, model),
                    "probability_observed_only": probability_metrics(
                        values, model, observed_only=True
                    ),
                    "ev": ev_metrics(values, model),
                    "ev_observed_only": ev_metrics(values, model, observed_only=True),
                }
                for name, values in splits.items()
            },
            "economics": {cost: book_metrics(books[model][cost]) for cost in COSTS},
        }
    return {
        "split_counts": {name: len(values) for name, values in splits.items()},
        "eligible_counts": {
            name: sum(row["_model_label_eligible"] for row in values)
            for name, values in splits.items()
        },
        "models": metrics,
        "paired_logloss_base_minus_context": paired_bootstrap(
            eval_rows,
            sessions,
            resamples=bootstrap_resamples,
            expected_eligible=expected_eval_eligible,
        ),
    }


def audit_numeric_bundle(
    *,
    candidates: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
    context_coverage_rows: list[dict[str, Any]],
    context_feature_names: list[str],
    frozen_scores: list[dict[str, Any]],
    frozen_model: dict[str, Any],
    means: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    producer_scores: list[dict[str, Any]],
    producer_ledgers: dict[str, dict[str, list[dict[str, Any]]]],
    frozen_baseline_ledgers: dict[str, list[dict[str, Any]]],
    coverage_rows: list[dict[str, Any]],
    sessions: list[str],
    last_entry: str,
    producer_summary: dict[str, Any],
    expected_controls: dict[str, Any] | None = None,
    expected_counts: dict[str, int] | None = None,
    bootstrap_resamples: int = 10_000,
) -> dict[str, Any]:
    """Audit a fully artificial or already admitted compact numeric bundle.

    The function performs no fit and imports neither the producer nor its feature
    builder/replay. File admission is intentionally a separate outer layer.
    """
    rows = copy.deepcopy(candidates)
    require(
        len({row["candidate_id"] for row in rows}) == len(rows),
        "duplicate candidate ID",
    )
    require(
        len(context_feature_names) == 81 and len(set(context_feature_names)) == 81,
        "context feature names",
    )
    join_context(rows, context_rows, context_coverage_rows)
    splits = split_rows(rows)
    if expected_counts is not None:
        require(len(rows) == expected_counts["total"], "candidate count")
        for name in ("TRAIN", "CAL", "EVAL"):
            require(
                sum(row["_model_label_eligible"] for row in splits[name])
                == expected_counts[name],
                f"eligible {name} count",
            )
    train = [row for row in splits["TRAIN"] if row["_model_label_eligible"]]
    require(train, "no eligible TRAIN rows")
    support = np.bincount(
        np.asarray([row["scenario"] for row in train], dtype=int), minlength=5
    )
    prior = support.astype(float) / len(train)
    require(
        np.array_equal(prior, np.asarray(frozen_model["train_prior"], dtype=float)),
        "frozen TRAIN prior/support",
    )
    expected_artifacts = {"CATEGORY30", "CONTEXT182"}
    require(set(artifacts) == expected_artifacts, "new artifact set")
    for model, matrix_key, names in (
        ("CATEGORY30", "_x_category", category_names()),
        ("CONTEXT182", "_x_context", context_names(context_feature_names)),
    ):
        values = artifacts[model]
        require(
            set(values) >= {"transform", "model", "calibration"},
            f"artifact shape {model}",
        )
        audit_saved_model(
            rows,
            model,
            matrix_key,
            names,
            values["transform"],
            values["model"],
            values["calibration"],
            prior,
            means,
        )
    compare_scores(rows, producer_scores, frozen_scores)
    eval_rows = splits["EVAL"]
    books = {
        model: replay_risk(
            _prepare_replay_rows(eval_rows, model),
            coverage_rows,
            sessions,
            last_entry,
        )
        for model in MODELS
    }
    require(set(producer_ledgers) == set(MODELS), "producer ledger models")
    for model in MODELS:
        require(set(producer_ledgers[model]) == set(COSTS), "producer ledger costs")
        for cost in COSTS:
            assert_equivalent(
                books[model][cost],
                producer_ledgers[model][cost],
                f"ledger.{model}.{cost}",
            )
    require(set(frozen_baseline_ledgers) == set(COSTS), "frozen baseline costs")
    for cost in COSTS:
        assert_equivalent(
            books["BASE18_FROZEN"][cost],
            frozen_baseline_ledgers[cost],
            f"frozen baseline.{cost}",
        )
    rebuilt = independently_rebuild_summary(
        rows,
        splits,
        books,
        sessions,
        bootstrap_resamples=bootstrap_resamples,
        expected_eval_eligible=(
            expected_counts["EVAL"] if expected_counts is not None else None
        ),
    )
    for key in (
        "split_counts",
        "eligible_counts",
        "models",
        "paired_logloss_base_minus_context",
    ):
        assert_equivalent(rebuilt[key], producer_summary[key], f"summary.{key}")
    require(producer_summary.get("fit_count") == 2, "fit count")
    require(
        producer_summary.get("new_fits") == ["CATEGORY30", "CONTEXT182"]
        and producer_summary.get("base18_refit") is False,
        "fit declarations",
    )
    require(
        producer_summary.get("schema") == "weekly_h2_context_model_comparison_v1"
        and producer_summary.get("status") == "COMPLETE_SEEN_DEVELOPMENT_DESCRIPTIVE",
        "summary schema/status",
    )
    require(
        producer_summary.get("flags")
        == {
            "development_seen": True,
            "promotion_approved": False,
            "technical_ready": False,
            "q3_used": False,
            "raw_or_api_used": False,
        },
        "summary flags",
    )
    if expected_controls is not None:
        assert_equivalent(
            expected_controls, producer_summary.get("controls"), "summary.controls"
        )
    return {
        "status": "PASS_INDEPENDENT_NUMERIC_AUDIT_FIXTURES_ONLY",
        **rebuilt,
    }


def execute_reviewed_audit(
    *,
    comparison_root: Path,
    comparison_manifest_sha256: str,
    auditor_sha256: str,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    """Execute only after the comparison package has a reviewed final manifest."""
    require(auditor_sha256 == sha256_file(Path(__file__)), "auditor authority")
    external_paths = {
        "dataset": DATASET_ROOT / "manifest.json",
        "frozen_eval": FROZEN_EVAL_ROOT / "manifest.json",
        "context": CONTEXT_ROOT / "manifest.json",
        "risk": RISK_ROOT / "manifest.json",
    }
    external_sha256 = {
        "dataset": DATASET_MANIFEST_SHA256,
        "frozen_eval": FROZEN_EVAL_MANIFEST_SHA256,
        "context": CONTEXT_MANIFEST_SHA256,
        "risk": RISK_MANIFEST_SHA256,
    }
    admission = admit_comparison_package(
        comparison_root=comparison_root,
        comparison_manifest_sha256=comparison_manifest_sha256,
        external_manifest_paths=external_paths,
        expected_external_sha256=external_sha256,
        producer_path=Path(__file__).with_name(PRODUCER_NAME),
        producer_sha256=PRODUCER_SHA256,
    )
    expected_consumed = {
        DATASET_ROOT / "manifest.json",
        DATASET_ROOT / "candidates.jsonl",
        DATASET_ROOT / "coverage.json",
        FROZEN_EVAL_ROOT / "manifest.json",
        FROZEN_EVAL_ROOT / "candidate_scores.jsonl",
        FROZEN_EVAL_ROOT / "model.json",
        FROZEN_EVAL_ROOT / "conditional_means.json",
        CONTEXT_ROOT / "manifest.json",
        CONTEXT_ROOT / "context.jsonl",
        CONTEXT_ROOT / "coverage.json",
        RISK_ROOT / "manifest.json",
        RISK_ROOT / "ledger_equal_risk_h1_eval_ev_top1_h2_base.jsonl",
        RISK_ROOT / "ledger_equal_risk_h1_eval_ev_top1_h2_adverse.jsonl",
        RISK_ROOT / "summary.json",
    }
    admitted_consumed = {
        Path(os.path.abspath(path)) for path in admission["consumed_pins"]
    }
    require(
        admitted_consumed
        == {Path(os.path.abspath(path)) for path in expected_consumed},
        "consumed payload authority set",
    )
    comparison_root = plain_path(comparison_root, "comparison root")
    candidates = read_jsonl_objects(
        DATASET_ROOT / "candidates.jsonl", "dataset candidates"
    )
    coverage = read_json_object(DATASET_ROOT / "coverage.json", "dataset coverage")
    context = read_jsonl_objects(CONTEXT_ROOT / "context.jsonl", "context rows")
    context_coverage = read_json_object(
        CONTEXT_ROOT / "coverage.json", "context coverage"
    )
    require(
        context_coverage.get("schema") == "weekly_context_1030_coverage_v1",
        "context coverage schema",
    )
    frozen_scores = read_jsonl_objects(
        FROZEN_EVAL_ROOT / "candidate_scores.jsonl", "frozen scores"
    )
    frozen_model = read_json_object(FROZEN_EVAL_ROOT / "model.json", "frozen model")
    means = read_json_object(
        FROZEN_EVAL_ROOT / "conditional_means.json", "frozen means"
    )
    artifacts = {
        model: {
            kind: read_json_object(
                comparison_root / f"{model.lower()}_{kind}.json",
                f"{model} {kind}",
            )
            for kind in ("transform", "model", "calibration")
        }
        for model in ("CATEGORY30", "CONTEXT182")
    }
    producer_scores = read_jsonl_objects(
        comparison_root / "candidate_scores_context_comparison.jsonl",
        "producer comparison scores",
    )
    producer_ledgers = {
        model: {
            cost: read_jsonl_objects(
                comparison_root / f"ledger_{model.lower()}_eval_{cost}.jsonl",
                f"producer ledger {model} {cost}",
            )
            for cost in COSTS
        }
        for model in MODELS
    }
    baseline = {
        cost: read_jsonl_objects(
            RISK_ROOT / f"ledger_equal_risk_h1_eval_ev_top1_h2_{cost}.jsonl",
            f"frozen baseline {cost}",
        )
        for cost in COSTS
    }
    producer_summary = read_json_object(
        comparison_root / "summary.json", "producer summary"
    )
    risk_summary = read_json_object(RISK_ROOT / "summary.json", "risk summary")
    expected_controls = {
        "source": "frozen equal-risk replay",
        "books": {
            policy: risk_summary["blocks"]["H1_EVAL"][policy]
            for policy in ("ALWAYS_CALL_H2", "ALWAYS_PUT_H2", "ALWAYS_ABSTAIN")
        },
    }
    h1_calendar = [
        row for row in coverage["calendar"] if "20260101" <= row["date"] <= "20260630"
    ]
    sessions_by_ticker = {
        ticker: [row["date"] for row in h1_calendar if row["ticker"] == ticker]
        for ticker in TICKERS
    }
    sessions = sessions_by_ticker["SPY"]
    require(
        sessions == sorted(set(sessions))
        and all(sessions_by_ticker[ticker] == sessions for ticker in TICKERS),
        "common H1 calendar",
    )
    h1_coverage = [
        row for row in coverage["rows"] if "20260101" <= row["entry_date"] <= "20260630"
    ]
    numeric = audit_numeric_bundle(
        candidates=candidates,
        context_rows=context,
        context_coverage_rows=context_coverage["rows"],
        context_feature_names=context_coverage["feature_names"],
        frozen_scores=frozen_scores,
        frozen_model=frozen_model,
        means=means,
        artifacts=artifacts,
        producer_scores=producer_scores,
        producer_ledgers=producer_ledgers,
        frozen_baseline_ledgers=baseline,
        coverage_rows=h1_coverage,
        sessions=sessions,
        last_entry="20260630",
        producer_summary=producer_summary,
        expected_controls=expected_controls,
        expected_counts={"total": 3054, "TRAIN": 1752, "CAL": 870, "EVAL": 426},
    )
    revalidate_comparison_package(admission)
    parent = plain_path(output_dir.parent, "audit output parent")
    output_dir = parent / output_dir.name
    require(not output_dir.exists(), "immutable audit output exists")
    output_dir.mkdir()
    result = {
        **numeric,
        "status": "PASS_INDEPENDENT_NUMERIC_AUDIT_SEEN_DEVELOPMENT",
        "comparison_manifest": admission["manifest_pin"],
        "producer": admission["producer"],
        "external_manifests": admission["external_pins"],
        "flags": {
            "fit_performed": False,
            "producer_imported": False,
            "raw_or_api_used": False,
            "development_seen": True,
            "promotion_approved": False,
            "technical_ready": False,
        },
    }
    result_path = output_dir / "audit.json"
    with result_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
    revalidate_comparison_package(admission)
    manifest = {
        "schema": "weekly_h2_context_model_comparison_numeric_audit_manifest_v1",
        "status": result["status"],
        "inputs": {
            "comparison_manifest": admission["manifest_pin"],
            "external_manifests": admission["external_pins"],
        },
        "implementation": {
            Path(__file__).name: auditor_sha256,
            CONTRACT.name: CONTRACT_SHA256,
            PRODUCER_NAME: PRODUCER_SHA256,
        },
        "files": {"audit.json": file_pin(result_path)},
        "flags": result["flags"],
    }
    manifest_path = output_dir / "manifest.json"
    with manifest_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
    revalidate_comparison_package(admission)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Independent numeric audit for weekly context models"
    )
    parser.add_argument("--execute-reviewed-audit", action="store_true")
    parser.add_argument("--comparison-root", required=True)
    parser.add_argument("--comparison-manifest-sha256", required=True)
    parser.add_argument("--auditor-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    if not args.execute_reviewed_audit:
        parser.error("execution requires --execute-reviewed-audit")
    require(sha256_file(CONTRACT) == CONTRACT_SHA256, "contract pin")
    require(len(args.comparison_manifest_sha256) == 64, "comparison manifest SHA-256")
    require(len(args.auditor_sha256) == 64, "auditor SHA-256")
    execute_reviewed_audit(
        comparison_root=Path(args.comparison_root),
        comparison_manifest_sha256=args.comparison_manifest_sha256.lower(),
        auditor_sha256=args.auditor_sha256.lower(),
        output_dir=Path(args.output_dir),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
