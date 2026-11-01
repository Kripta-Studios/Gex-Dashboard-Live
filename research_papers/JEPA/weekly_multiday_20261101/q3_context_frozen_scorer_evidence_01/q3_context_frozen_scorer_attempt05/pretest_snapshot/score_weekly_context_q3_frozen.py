"""Frozen Q3 scoring for BASE18, CATEGORY30 and CONTEXT182.

This module restores already-fitted parameters. It contains no estimator and
performs no fit or calibration. Real execution is fail-closed behind explicit
context-manifest and context-audit authorities.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import statistics
from typing import Any, Iterable

import numpy as np


WEEK = Path(__file__).resolve().parent
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
OUTPUT = BASE / "h2_context_model_comparison_q3_01"
CONTEXT_ROOT = BASE / "h2_context_q3_1030_01"
CONTEXT_AUDIT_ROOT = BASE / "h2_context_q3_1030_audit_01"
H1_CONTEXT_AUDIT = BASE / "h2_context_model_comparison_audit_01" / "audit.json"
DATASET_ROOT = BASE / "h2_dataset_v2_extension_2026q3_partial_01"
BASE18_ROOT = BASE / "h2_ev_frozen_extension_2026q3_partial_01"
MODEL_ROOT = BASE / "h2_context_model_comparison_01"
FROZEN_ROOT = BASE / "h2_ev_v2_01"
RISK_ROOT = BASE / "h2_equal_risk_frozen_01"

CONTRACT = WEEK / "Q3_FROZEN_CONTEXT_COMPARISON_CONTRACT_20261101.md"
CONTRACT_SHA256 = "e9867bfc5acc5922288e81542e250de7707cfd20f472087b24700ef69764802a"
REPLAY = WEEK / "replay_equal_risk_frozen.py"
REPLAY_SHA256 = "e4f42a9fa65120939cf5e131911c8f2990a9cd33d21ae036fa98d9eb816d5b9d"

DATASET_MANIFEST_SHA256 = "b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b"
BASE18_MANIFEST_SHA256 = "7bd50a5a1fe5214df2c4281e785313f0fb016ca73d725d682788dcb78b283d8e"
MODEL_MANIFEST_SHA256 = "662ac63eaa2895beff4363b9e94a97cd7adc91aac3558139bdd919d8fbf2861a"
FROZEN_MANIFEST_SHA256 = "54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96"
RISK_MANIFEST_SHA256 = "50fa6b7a02aad9d122dc0bfdd84f8c01f9a5f468bafc7f175eed39aa3ea9418d"
H1_CONTEXT_AUDIT_SHA256 = "bb661fe916f65ed6ee40dd3cf684650a8d318447005a7f224edec6a4b814b3eb"
BASE18_SCORES_SHA256 = "9458c8dfa75983784af0e7514feec1ded43a42adadecfb07c0406aee3f284ca6"
MEANS_SHA256 = "a8dc329233ce431b282c500e27cf91ac91d845cbb6a1fc752cee36026aef3f90"
FROZEN_MODEL_SHA256 = "68712c7c326d2337a34f8401579ddc52a4dab0e3f505c8c4ff2f1b1d51c03fb4"

ARTIFACT_SHA256 = {
    "category30_model.json": "e927fe4e2e9b796c2f41f0cdb36a713fd72101b5bbbb8c8131c2be7f84224b5c",
    "category30_transform.json": "dbbab2c4a774e43e69269a5b0b9c7ed06f61b105b8cc96196464f83ba740584d",
    "category30_calibration.json": "1201fbd5dbbc6d6e4aae6149ee5349e2773a7bb659cb45a51cea44e7d9fd9ba1",
    "context182_model.json": "7a9dafc2a8c30c83ef2177057ceeb6fa33636f2943821cee83172b703cc17037",
    "context182_transform.json": "82b31bc61ad94f462b724a49d1cfd6793aebfc361afd3111e5c27dc1d16539c0",
    "context182_calibration.json": "5a9dc85fba737b0e2921968c711ce14780da2b3aa7a27f87bd025cf0954bc14c",
}

FEATURE18 = (
    "ticker_SPY", "ticker_QQQ", "ticker_SPXW", "right_call", "dte", "weekday",
    "spot", "strike", "moneyness", "bid", "ask", "spread_relative", "delta",
    "implied_vol", "gamma", "theta", "vega", "rho",
)
TICKERS = ("SPY", "QQQ", "SPXW")
RIGHTS = ("CALL", "PUT")
MODELS = ("BASE18_FROZEN", "CATEGORY30", "CONTEXT182")
COSTS = ("base", "adverse")
SPLIT = "Q3_PARTIAL_2026_SEEN_DEVELOPMENT"
FIRST_DATE, LAST_DATE, LAST_ENTRY = "20260701", "20260917", "20260915"


class FrozenScoringError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FrozenScoringError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def plain(path: Path, label: str, *, exists: bool = True) -> Path:
    absolute = Path(os.path.abspath(path))
    if exists:
        require(absolute.exists(), f"missing {label}")
    current = absolute if absolute.exists() else absolute.parent
    while True:
        if current.exists():
            attrs = getattr(current.lstat(), "st_file_attributes", 0)
            require(not current.is_symlink() and not attrs & 0x400, f"link/reparse {label}")
        if current.parent == current:
            break
        current = current.parent
    return absolute


def pin(path: Path) -> dict[str, Any]:
    path = plain(path, str(path))
    require(path.is_file(), f"regular file {path}")
    return {"bytes": path.stat().st_size, "sha256": sha256_file(path)}


def verify(path: Path, expected: dict[str, Any], label: str) -> None:
    require(isinstance(expected, dict) and set(expected) >= {"bytes", "sha256"}, f"pin shape {label}")
    require(pin(path) == {"bytes": expected["bytes"], "sha256": expected["sha256"]}, f"pin {label}")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(plain(path, str(path)).read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with plain(path, str(path)).open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL {path}:{number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"JSON object {path}:{number}")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def import_replay() -> Any:
    replay_path = plain(REPLAY, "replay implementation")
    require(replay_path.is_file() and sha256_file(replay_path) == REPLAY_SHA256, "replay authority")
    spec = importlib.util.spec_from_file_location("weekly_context_q3_replay_pure", replay_path)
    require(spec is not None and spec.loader is not None, "replay import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(sha256_file(replay_path) == REPLAY_SHA256, "replay changed during import")
    return module


def category_names() -> list[str]:
    return [f"{ticker}:{right}:weekday{weekday}" for ticker in TICKERS for right in RIGHTS for weekday in range(5)]


def category30(row: dict[str, Any]) -> list[float]:
    weekday = int(row["features"]["weekday"])
    require(row["ticker"] in TICKERS and row["right"] in RIGHTS and weekday in range(5), "category identity")
    index = (TICKERS.index(row["ticker"]) * 2 + RIGHTS.index(row["right"])) * 5 + weekday
    values = [0.0] * 30
    values[index] = 1.0
    return values


def context_names(feature_names: list[str]) -> list[str]:
    require(len(feature_names) == len(set(feature_names)) == 81, "context feature names")
    return [*FEATURE18, *[f"context:{name}" for name in feature_names], *[f"side_context:{name}" for name in feature_names], "source_available", "state_valid"]


def context182(row: dict[str, Any], context: dict[str, Any]) -> list[float]:
    status, valid, raw = context.get("status"), context.get("state_valid"), context.get("context_81")
    if status == "CONTEXT_MISSING_SOURCE":
        require(valid is None and raw is None, "missing context semantics")
        vector, flags = [0.0] * 81, [0.0, 0.0]
    else:
        require(status == "CONTEXT_AVAILABLE" and isinstance(valid, bool), "available context semantics")
        require(isinstance(raw, list) and len(raw) == 81, "context shape")
        require(all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) for value in raw), "context finite")
        vector, flags = ([float(value) for value in raw] if valid else [0.0] * 81), [1.0, float(valid)]
    original = [math.nan if row["features"][name] is None else float(row["features"][name]) for name in FEATURE18]
    sign = 1.0 if row["right"] == "CALL" else -1.0
    values = [*original, *vector, *[sign * value for value in vector], *flags]
    require(len(values) == 182, "CONTEXT182 width")
    return values


def join_context(rows: list[dict[str, Any]], context_rows: list[dict[str, Any]], coverage: dict[str, Any]) -> list[str]:
    names = coverage.get("feature_names")
    require(isinstance(names, list) and len(names) == len(set(names)) == 81, "context names")
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for item in context_rows:
        key = (item.get("ticker"), item.get("date"))
        require(key[0] in TICKERS and isinstance(key[1], str) and key not in index, "context identity")
        index[key] = item
    coverage_rows = coverage.get("rows", [])
    cover = {(item.get("ticker"), item.get("date")) for item in coverage_rows}
    require(len(coverage_rows) == len(cover) == len(index) == 165 and set(index) == cover, "context coverage identities")
    for row in rows:
        item = index.get((row["ticker"], row["entry_date"]))
        require(item is not None, "candidate lacks context")
        row["_x_category"] = category30(row)
        row["_x_context"] = context182(row, item)
        row["_context_status"] = item["status"]
        row["_context_state_valid"] = item["state_valid"]
    return names


def apply_transform(matrix: np.ndarray, saved: dict[str, Any], feature_names: list[str]) -> np.ndarray:
    require(saved.get("feature_order") == feature_names and saved.get("fit_scope") == "TRAIN_ONLY", "transform identity")
    medians = np.asarray(saved.get("medians"), dtype=float)
    indicators = saved.get("missing_indicator_source_indices")
    require(matrix.ndim == 2 and matrix.shape[1] == len(medians) == len(feature_names), "transform width")
    require(isinstance(indicators, list) and all(isinstance(index, int) and 0 <= index < matrix.shape[1] for index in indicators), "indicator indices")
    missing = np.isnan(matrix)
    imputed = np.where(missing, medians, matrix)
    expanded = np.concatenate([imputed, missing[:, indicators].astype(float)], axis=1) if indicators else imputed
    mean, scale = np.asarray(saved.get("scaler_mean"), dtype=float), np.asarray(saved.get("scaler_scale"), dtype=float)
    require(expanded.shape[1] == len(mean) == len(scale) and np.all(np.isfinite(mean)) and np.all(np.isfinite(scale)) and np.all(scale > 0), "scaler")
    return (expanded - mean) / scale


def restored_probabilities(matrix: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    require(model.get("type") == "LogisticRegression" and model.get("fit_scope") == "TRAIN_ONLY", "model identity")
    require(model.get("C") == 1.0 and model.get("solver") == "lbfgs" and model.get("max_iter") == 2000 and model.get("random_state") == 0, "model config")
    classes = [int(value) for value in model.get("classes_present", [])]
    require(classes == sorted(set(classes)) and model.get("classes_full") == list(range(5)), "model classes")
    coefficient, intercept = np.asarray(model.get("coefficient"), dtype=float), np.asarray(model.get("intercept"), dtype=float)
    require(coefficient.shape == (len(classes), matrix.shape[1]) and intercept.shape == (len(classes),), "model coefficient shape")
    logits = matrix @ coefficient.T + intercept
    logits -= logits.max(axis=1, keepdims=True)
    partial = np.exp(logits)
    partial /= partial.sum(axis=1, keepdims=True)
    output = np.zeros((len(matrix), 5), dtype=float)
    output[:, classes] = partial
    return output


def score_restored(rows: list[dict[str, Any]], model_name: str, matrix_key: str, names: list[str], artifacts: dict[str, dict[str, Any]], prior: np.ndarray, means: dict[str, Any]) -> None:
    values = np.asarray([row[matrix_key] for row in rows], dtype=float)
    transformed = apply_transform(values, artifacts["transform"], names)
    p_model = restored_probabilities(transformed, artifacts["model"])
    alpha = float(artifacts["calibration"].get("selected_alpha"))
    expected_alpha = 0.3 if model_name == "CATEGORY30" else 0.6
    require(alpha == expected_alpha and artifacts["calibration"].get("formula") == "(1-alpha)*p_model+alpha*p_train_prior", "frozen alpha")
    probability = (1 - alpha) * p_model + alpha * prior
    for row, probabilities in zip(rows, probability, strict=True):
        row[f"_p_{model_name}"] = probabilities.tolist()
        key = f"{row['ticker']}:{row['right']}"
        for cost in COSTS:
            conditional = np.asarray([means["cells"][cost][key][str(label)]["mean_y"] for label in range(5)], dtype=float)
            row[f"_ev_{model_name}_{cost}"] = float(row["decision_ask"]) * 100 * float(np.dot(probabilities, conditional))


def probability_metrics(rows: list[dict[str, Any]], model: str, *, selected: set[str] | None = None, observed_only: bool = False) -> dict[str, Any]:
    values = [row for row in rows if (selected is None or row["candidate_id"] in selected) and (not observed_only or not row["payoff_is_lower_bound"])]
    if not values:
        return {"n": 0, "log_loss": None, "brier": None, "reliability": []}
    probabilities = np.asarray([row[f"_p_{model}"] for row in values], dtype=float)
    labels = np.asarray([row["scenario"] for row in values], dtype=int)
    targets = np.eye(5)[labels]
    reliability = []
    for label in range(5):
        for index in range(10):
            low, high = index / 10, (index + 1) / 10
            mask = (probabilities[:, label] >= low) & ((probabilities[:, label] < high) | ((index == 9) & (probabilities[:, label] <= high)))
            if mask.any():
                reliability.append({"class": label, "bin_low": low, "bin_high": high, "n": int(mask.sum()), "predicted": float(probabilities[mask, label].mean()), "observed": float((labels[mask] == label).mean())})
    loss = -np.log(np.clip(probabilities[np.arange(len(labels)), labels], 1e-12, 1.0))
    return {"n": len(values), "log_loss": float(loss.mean()), "brier": float(np.square(probabilities - targets).sum(axis=1).mean()), "reliability": reliability}


def ev_metrics(rows: list[dict[str, Any]], model: str, *, selected: set[str] | None = None, observed_only: bool = False) -> dict[str, Any]:
    values = [row for row in rows if (selected is None or row["candidate_id"] in selected) and (not observed_only or not row["payoff_is_lower_bound"])]
    return {cost: {"n": len(values), "bias": statistics.fmean(float(row[f"_ev_{model}_{cost}"]) - float(row[f"net_{cost}"]) for row in values) if values else None, "mae": statistics.fmean(abs(float(row[f"_ev_{model}_{cost}"]) - float(row[f"net_{cost}"])) for row in values) if values else None} for cost in COSTS}


def selected_ids(ledger: list[dict[str, Any]]) -> set[str]:
    return {row["candidate_id"] for row in ledger if row["event"] in {"ENTRY", "NO_FILL", "CAPITAL_BLOCKED"} and "candidate_id" in row}


def extended_book_metrics(replay: Any, ledger: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = replay.book_metrics(ledger)
    exits = [row for row in ledger if row["event"] == "EXIT"]
    right_net = {right: math.fsum(float(row["net_usd"]) for row in exits if row["right"] == right) for right in RIGHTS}
    largest = max(exits, key=lambda row: float(row["net_usd"]), default=None)
    monthly = metrics["monthly_net_usd"]
    largest_month = max(monthly, key=monthly.get, default=None)
    metrics["right_net_usd"] = right_net
    metrics["largest_trade_by_net_usd"] = None if largest is None else {
        "candidate_id": largest["candidate_id"], "ticker": largest["ticker"], "right": largest["right"],
        "net_usd": float(largest["net_usd"]), "net_without_trade_usd": metrics["net_usd"] - float(largest["net_usd"]),
        "interpretation": "mechanical concentration subtraction; not an alternative policy",
    }
    metrics["largest_month_by_net_usd"] = None if largest_month is None else {
        "month": largest_month, "net_usd": monthly[largest_month],
        "net_without_month_usd": metrics["net_usd"] - monthly[largest_month],
        "interpretation": "mechanical concentration subtraction; not an alternative policy",
    }
    return metrics


def paired_bootstrap(rows: list[dict[str, Any]], sessions: list[str], *, resamples: int = 10_000) -> dict[str, Any]:
    require(len(rows) == 180 and len(sessions) == len(set(sessions)) == 55 and sessions == sorted(sessions), "bootstrap scope")
    by_day = {day: [0.0, 0] for day in sessions}
    for row in rows:
        label = int(row["scenario"])
        base = max(float(row["_p_BASE18_FROZEN"][label]), 1e-12)
        context = max(float(row["_p_CONTEXT182"][label]), 1e-12)
        by_day[row["entry_date"]][0] += -math.log(base) + math.log(context)
        by_day[row["entry_date"]][1] += 1
    generator, values = random.Random(20_261_101), []
    for _ in range(resamples):
        indices: list[int] = []
        for _ in range(11):
            start = generator.randrange(55)
            indices.extend((start + offset) % 55 for offset in range(5))
        numerator = math.fsum(by_day[sessions[index]][0] for index in indices)
        denominator = sum(by_day[sessions[index]][1] for index in indices)
        require(denominator > 0, "bootstrap denominator")
        values.append(numerator / denominator)
    ordered = sorted(values)
    def percentile(p: float) -> float:
        position = (len(ordered) - 1) * p
        low, high = math.floor(position), math.ceil(position)
        return ordered[low] + (position - low) * (ordered[high] - ordered[low])
    denominator = sum(value[1] for value in by_day.values())
    return {"seed": 20_261_101, "block_sessions": 5, "resamples": resamples, "sessions": 55, "estimate": math.fsum(value[0] for value in by_day.values()) / denominator, "percentile_type7_2_5": percentile(0.025), "percentile_type7_97_5": percentile(0.975), "paired_daily_contributions": [{"date": day, "loss_sum_base_minus_context": by_day[day][0], "candidate_count": by_day[day][1]} for day in sessions], "interpretation": "exploratory post-development interval; no p-value or independent validation claim"}


def prepare_rows(rows: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        value = dict(row)
        value["_ev_base"], value["_ev_adverse"] = row[f"_ev_{model}_base"], row[f"_ev_{model}_adverse"]
        output.append(value)
    return output


def snapshot_authorities(context_manifest_sha256: str, context_audit_sha256: str) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    paths = {
        "dataset": DATASET_ROOT / "manifest.json", "base18": BASE18_ROOT / "manifest.json",
        "models": MODEL_ROOT / "manifest.json", "frozen": FROZEN_ROOT / "manifest.json",
        "risk": RISK_ROOT / "manifest.json", "context": CONTEXT_ROOT / "manifest.json",
        "context_audit": CONTEXT_AUDIT_ROOT / "audit.json",
        "h1_context_audit": H1_CONTEXT_AUDIT,
    }
    expected = {"dataset": DATASET_MANIFEST_SHA256, "base18": BASE18_MANIFEST_SHA256, "models": MODEL_MANIFEST_SHA256, "frozen": FROZEN_MANIFEST_SHA256, "risk": RISK_MANIFEST_SHA256, "context": context_manifest_sha256, "context_audit": context_audit_sha256, "h1_context_audit": H1_CONTEXT_AUDIT_SHA256}
    snapshots = {name: {"path": str(path), **pin(path)} for name, path in paths.items()}
    require(all(snapshots[name]["sha256"] == expected[name] for name in paths), "external authority")
    return snapshots, {name: {"bytes": value["bytes"], "sha256": value["sha256"]} for name, value in snapshots.items()}


def revalidate(snapshots: dict[str, dict[str, Any]], payloads: dict[Path, dict[str, Any]]) -> None:
    for name, value in snapshots.items():
        verify(Path(value["path"]), value, f"closing authority {name}")
    for path, value in payloads.items():
        verify(path, value, f"closing payload {path.name}")


def validate_context_audit(audit: dict[str, Any], context_manifest_pin: dict[str, Any], expected_path: Path | None = None) -> None:
    require(audit.get("schema") == "weekly_context_q3_1030_independent_audit_v1", "context audit schema")
    require(audit.get("status") == "PASS_INDEPENDENT_CONTEXT_Q3_1030_GIVEN_FROZEN_FUNCTIONS", "context audit status")
    flags = audit.get("flags", {})
    require(flags.get("fit_performed") is False and flags.get("outcomes_read") is False and flags.get("models_fit") is False, "context audit flags")
    producer = audit.get("inputs", {}).get("producer_manifest")
    require(isinstance(producer, dict) and producer.get("sha256") == context_manifest_pin["sha256"] and producer.get("bytes") == context_manifest_pin["bytes"], "context audit producer-manifest binding")
    if expected_path is not None:
        require(Path(os.path.abspath(producer.get("path", ""))) == Path(os.path.abspath(expected_path)), "context audit producer-manifest path")


def execute(context_manifest_sha256: str, context_audit_sha256: str, output: Path = OUTPUT) -> dict[str, Any]:
    require(sha256_file(CONTRACT) == CONTRACT_SHA256, "contract authority")
    output = plain(output, "output", exists=False)
    require(not output.exists(), "immutable output exists")
    replay = import_replay()
    snapshots, _ = snapshot_authorities(context_manifest_sha256, context_audit_sha256)
    dataset_manifest, base18_manifest, model_manifest, risk_manifest = (read_json(path) for path in (DATASET_ROOT / "manifest.json", BASE18_ROOT / "manifest.json", MODEL_ROOT / "manifest.json", RISK_ROOT / "manifest.json"))
    context_manifest, context_audit = read_json(CONTEXT_ROOT / "manifest.json"), read_json(CONTEXT_AUDIT_ROOT / "audit.json")
    require(context_manifest.get("schema") == "weekly_context_q3_1030_manifest_v1" and context_manifest.get("status") == "COMPLETE_CAUSAL_CONTEXT_Q3_1030_NOT_JOINED_NOT_EVALUATED", "context manifest identity")
    require(context_manifest.get("state_i") == 60 and context_manifest.get("counts", {}).get("identities") == 165 and context_manifest.get("counts", {}).get("available") == 153 and context_manifest.get("counts", {}).get("missing") == 12, "context counts")
    require(context_manifest.get("flags") == {"actions_read": False, "development_seen": True, "labels_read": False, "models_fit": False, "oracle_read": False, "outcomes_read": False, "promotion_approved": False}, "context flags")
    validate_context_audit(context_audit, {"bytes": snapshots["context"]["bytes"], "sha256": snapshots["context"]["sha256"]}, CONTEXT_ROOT / "manifest.json")

    paths = {
        DATASET_ROOT / "candidates.jsonl": dataset_manifest["files"]["candidates.jsonl"],
        DATASET_ROOT / "coverage.json": dataset_manifest["files"]["coverage.json"],
        BASE18_ROOT / "candidate_scores_extension.jsonl": base18_manifest["outputs"]["candidate_scores_extension.jsonl"],
        CONTEXT_ROOT / "context.jsonl": context_manifest["files"]["context.jsonl"],
        CONTEXT_ROOT / "coverage.json": context_manifest["files"]["coverage.json"],
        FROZEN_ROOT / "model.json": {"bytes": (FROZEN_ROOT / "model.json").stat().st_size, "sha256": FROZEN_MODEL_SHA256},
        FROZEN_ROOT / "conditional_means.json": {"bytes": (FROZEN_ROOT / "conditional_means.json").stat().st_size, "sha256": MEANS_SHA256},
        RISK_ROOT / "summary.json": risk_manifest["outputs"]["summary.json"],
    }
    for name, expected_sha in ARTIFACT_SHA256.items():
        paths[MODEL_ROOT / name] = {"bytes": (MODEL_ROOT / name).stat().st_size, "sha256": expected_sha}
    baseline_paths = {cost: RISK_ROOT / f"ledger_equal_risk_q3_partial_ev_top1_h2_{cost}.jsonl" for cost in COSTS}
    paths.update({path: risk_manifest["outputs"][path.name] for path in baseline_paths.values()})
    for path, expected in paths.items():
        verify(path, expected, f"admit {path.name}")

    candidates, coverage = read_jsonl(DATASET_ROOT / "candidates.jsonl"), read_json(DATASET_ROOT / "coverage.json")
    require(len(candidates) == 180 and len({row["candidate_id"] for row in candidates}) == 180, "candidate universe")
    require(all(row.get("entry_date", "") >= FIRST_DATE and row.get("entry_date", "") <= LAST_ENTRY for row in candidates), "candidate dates")
    context_coverage = read_json(CONTEXT_ROOT / "coverage.json")
    require(context_coverage.get("schema") == "weekly_context_q3_1030_coverage_v1" and context_manifest.get("feature_names") == context_coverage.get("feature_names"), "context coverage")
    feature_names = join_context(candidates, read_jsonl(CONTEXT_ROOT / "context.jsonl"), context_coverage)

    base_scores = read_jsonl(BASE18_ROOT / "candidate_scores_extension.jsonl")
    require(sha256_file(BASE18_ROOT / "candidate_scores_extension.jsonl") == BASE18_SCORES_SHA256, "BASE18 scores")
    score_index = {row["candidate_id"]: row for row in base_scores}
    require(len(score_index) == len(base_scores) == 180, "BASE18 IDs")
    for row in candidates:
        score = score_index.get(row["candidate_id"])
        require(score is not None and score.get("split") == SPLIT and score.get("scenario") == row["scenario"] and score.get("payoff_is_lower_bound") == row["payoff_is_lower_bound"], "BASE18 score identity")
        row["_p_BASE18_FROZEN"] = [float(value) for value in score["p_cal"]]
        for cost in COSTS:
            row[f"_ev_BASE18_FROZEN_{cost}"] = float(score[f"ev_{cost}"])

    frozen_model, means = read_json(FROZEN_ROOT / "model.json"), read_json(FROZEN_ROOT / "conditional_means.json")
    prior = np.asarray(frozen_model.get("train_prior"), dtype=float)
    require(prior.shape == (5,) and math.isclose(float(prior.sum()), 1.0, abs_tol=1e-12), "frozen prior")
    artifacts = {model: {kind: read_json(MODEL_ROOT / f"{model.lower()}_{kind}.json") for kind in ("transform", "model", "calibration")} for model in ("CATEGORY30", "CONTEXT182")}
    for row in candidates:
        row["_x_category"] = category30(row)
    score_restored(candidates, "CATEGORY30", "_x_category", category_names(), artifacts["CATEGORY30"], prior, means)
    score_restored(candidates, "CONTEXT182", "_x_context", context_names(feature_names), artifacts["CONTEXT182"], prior, means)

    q3_coverage, sessions = replay.filtered_calendar(coverage, FIRST_DATE, LAST_DATE)
    require(len(sessions) == 55, "session count")
    books = {model: replay.replay_pair(prepare_rows(candidates, model), q3_coverage, sessions, LAST_ENTRY, "EV_TOP1_H2") for model in MODELS}
    baseline = {cost: read_jsonl(path) for cost, path in baseline_paths.items()}
    require(all(books["BASE18_FROZEN"][cost] == baseline[cost] for cost in COSTS), "BASE18 ledger identity")
    selected = {model: selected_ids(books[model]["adverse"]) for model in MODELS}
    require(all(selected[model] == selected_ids(books[model]["base"]) for model in MODELS), "shared decisions")
    metrics = {}
    for model in MODELS:
        own = selected[model]
        metrics[model] = {
            "probability_all": probability_metrics(candidates, model),
            "probability_observed_only": probability_metrics(candidates, model, observed_only=True),
            "probability_selected": probability_metrics(candidates, model, selected=own),
            "probability_selected_observed_only": probability_metrics(candidates, model, selected=own, observed_only=True),
            "ev_all": ev_metrics(candidates, model), "ev_observed_only": ev_metrics(candidates, model, observed_only=True),
            "ev_selected": ev_metrics(candidates, model, selected=own), "ev_selected_observed_only": ev_metrics(candidates, model, selected=own, observed_only=True),
            "lower_bound": {"all": sum(row["payoff_is_lower_bound"] for row in candidates), "selected": sum(row["candidate_id"] in own and row["payoff_is_lower_bound"] for row in candidates)},
            "economics": {cost: extended_book_metrics(replay, books[model][cost]) for cost in COSTS},
        }
    risk_summary = read_json(RISK_ROOT / "summary.json")
    summary = {
        "schema": "weekly_h2_context_model_comparison_q3_v1", "status": "COMPLETE_Q3_PARTIAL_2026_SEEN_DEVELOPMENT",
        "candidate_count": 180, "session_count": 55, "models": metrics,
        "context_counts": {"available": sum(row["_context_status"] == "CONTEXT_AVAILABLE" for row in candidates), "missing": sum(row["_context_status"] == "CONTEXT_MISSING_SOURCE" for row in candidates), "state_valid_true": sum(row["_context_state_valid"] is True for row in candidates), "state_valid_false": sum(row["_context_state_valid"] is False for row in candidates)},
        "paired_logloss_base_minus_context": paired_bootstrap(candidates, sessions),
        "fit_count": 0, "refit": False, "recalibration": False,
        "controls": {"source": "frozen equal-risk replay", "books": {policy: risk_summary["blocks"]["Q3_PARTIAL"][policy] for policy in ("ALWAYS_CALL_H2", "ALWAYS_PUT_H2", "ALWAYS_ABSTAIN")}},
        "flags": {"development_seen": True, "fit_performed": False, "promotion_approved": False, "q3_used": True, "raw_or_api_used": False, "recalibration_performed": False, "technical_ready": False},
    }
    revalidate(snapshots, paths)
    output.mkdir(parents=True, exist_ok=False)
    score_rows = [{"candidate_id": row["candidate_id"], "split": SPLIT, "scenario": row["scenario"], "payoff_is_lower_bound": row["payoff_is_lower_bound"], "context_status": row["_context_status"], "context_state_valid": row["_context_state_valid"], **{f"p_{model.lower()}": row[f"_p_{model}"] for model in MODELS}, **{f"ev_{model.lower()}_{cost}": row[f"_ev_{model}_{cost}"] for model in MODELS for cost in COSTS}} for row in candidates]
    write_jsonl(output / "candidate_scores_context_q3.jsonl", score_rows)
    for model in MODELS:
        for cost in COSTS:
            write_jsonl(output / f"ledger_{model.lower()}_q3_{cost}.jsonl", books[model][cost])
    write_json(output / "summary.json", summary)
    revalidate(snapshots, paths)
    outputs = {path.name: pin(path) for path in sorted(output.iterdir())}
    write_json(output / "manifest.json", {"schema": "weekly_h2_context_model_comparison_q3_manifest_v1", "status": summary["status"], "external_authorities": {name: {"bytes": value["bytes"], "sha256": value["sha256"]} for name, value in snapshots.items()}, "consumed_payloads": {str(path): value for path, value in paths.items()}, "implementation": {Path(__file__).name: sha256_file(Path(__file__)), CONTRACT.name: CONTRACT_SHA256, REPLAY.name: REPLAY_SHA256}, "outputs": outputs, "flags": summary["flags"]})
    revalidate(snapshots, paths)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen Q3 comparison of weekly context models")
    parser.add_argument("--execute-reviewed-scoring", action="store_true")
    parser.add_argument("--context-manifest-sha256", required=True)
    parser.add_argument("--context-audit-sha256", required=True)
    parser.add_argument("--scorer-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    if not args.execute_reviewed_scoring:
        parser.error("execution requires --execute-reviewed-scoring")
    require(args.scorer_sha256.lower() == sha256_file(Path(__file__)), "scorer authority")
    require(all(len(value) == 64 for value in (args.context_manifest_sha256, args.context_audit_sha256, args.scorer_sha256)), "SHA-256 arguments")
    execute(args.context_manifest_sha256.lower(), args.context_audit_sha256.lower(), Path(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
