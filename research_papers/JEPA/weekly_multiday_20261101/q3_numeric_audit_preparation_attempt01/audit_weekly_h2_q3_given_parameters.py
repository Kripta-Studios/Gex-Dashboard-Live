"""Independent numeric audit for the frozen-parameter H2 Q3 continuation.

This module never imports the production scorer and never estimates parameters.
Real execution requires externally supplied, closed manifest hashes.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression


POLICIES = ("EV_TOP1_H2", "ALWAYS_CALL_H2", "ALWAYS_PUT_H2", "ALWAYS_ABSTAIN")
COSTS = ("base", "adverse")
TICKERS = ("SPY", "QQQ", "SPXW")
STARTING_CASH = 100_000.0
COMMISSION = 1.30
SPLIT = "Q3_PARTIAL_2026_SEEN_DEVELOPMENT"
SCORE_FILE = "candidate_scores_extension.jsonl"
SUMMARY_FILE = "summary_extension.json"
FROZEN_FILES = ("model.json", "transform.json", "conditional_means.json", "calibration_grid.json")


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


def plain(path: Path, label: str, *, exists: bool = True) -> Path:
    path = Path(os.path.abspath(path))
    if exists:
        require(path.exists(), f"missing {label}")
    current = path if path.exists() else path.parent
    while True:
        if current.exists():
            attrs = getattr(current.lstat(), "st_file_attributes", 0)
            require(not current.is_symlink() and not attrs & 0x400, f"link/reparse {label}")
        if current.parent == current:
            break
        current = current.parent
    return path


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL {path}:{number}")
            row = json.loads(line)
            require(isinstance(row, dict), f"object required {path}:{number}")
            rows.append(row)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def verify(path: Path, pin: dict[str, Any], label: str) -> None:
    require(path.is_file() and path.stat().st_size == pin["bytes"] and sha256_file(path) == pin["sha256"], f"pin {label}")


def restore_logistic(model_json: dict[str, Any]) -> LogisticRegression:
    require(model_json.get("type") == "LogisticRegression", "model type")
    classes = np.asarray(model_json["classes_present"], dtype=np.int64)
    coefficient = np.asarray(model_json["coefficient"], dtype=np.float64)
    intercept = np.asarray(model_json["intercept"], dtype=np.float64)
    require(coefficient.ndim == 2 and intercept.shape == (len(classes),), "model dimensions")
    model = LogisticRegression(
        C=float(model_json["C"]), max_iter=int(model_json["max_iter"]),
        random_state=int(model_json["random_state"]), solver=str(model_json["solver"]),
    )
    model.classes_ = classes
    model.coef_ = coefficient
    model.intercept_ = intercept
    model.n_features_in_ = coefficient.shape[1]
    model.n_iter_ = np.zeros(len(classes), dtype=np.int32)
    return model


def transform_matrix(candidates: list[dict[str, Any]], artifact: dict[str, Any]) -> np.ndarray:
    order = artifact["feature_order"]
    medians = np.asarray(artifact["medians"], dtype=np.float64)
    indicators = [int(value) for value in artifact["missing_indicator_source_indices"]]
    mean = np.asarray(artifact["scaler_mean"], dtype=np.float64)
    scale = np.asarray(artifact["scaler_scale"], dtype=np.float64)
    require(len(order) == len(medians) and np.all(scale > 0), "transform dimensions/scale")
    output = []
    for row in candidates:
        features = row.get("features")
        require(isinstance(features, dict) and list(features) == order, "feature order")
        raw = [features[name] for name in order]
        expanded = [medians[index] if value is None else float(value) for index, value in enumerate(raw)]
        expanded.extend(float(raw[index] is None) for index in indicators)
        require(len(expanded) == len(mean) == len(scale), "expanded dimension")
        output.append([(value - mean[index]) / scale[index] for index, value in enumerate(expanded)])
    return np.asarray(output, dtype=np.float64)


def independent_scores(
    candidates: list[dict[str, Any]], model_json: dict[str, Any], transform_json: dict[str, Any],
    calibration: dict[str, Any], means: dict[str, Any],
) -> list[dict[str, Any]]:
    matrix = transform_matrix(candidates, transform_json)
    model = restore_logistic(model_json)
    require(matrix.shape[1] == model.n_features_in_, "n_features_in_ mismatch")
    partial = model.predict_proba(matrix)
    classes = model.classes_.astype(int)
    require(set(classes) <= set(range(5)), "model class")
    p_model = np.zeros((len(candidates), 5), dtype=np.float64)
    for source, label in enumerate(classes):
        p_model[:, label] = partial[:, source]
    alpha = float(calibration["selected_alpha"])
    prior = np.asarray(model_json["train_prior"], dtype=np.float64)
    require(prior.shape == (5,) and math.isclose(float(prior.sum()), 1.0, abs_tol=1e-12), "train prior")
    p_cal = (1 - alpha) * p_model + alpha * prior
    output = []
    for index, row in enumerate(candidates):
        key = f"{row['ticker']}:{row['right']}"
        ev = {}
        for cost in COSTS:
            conditional = np.asarray([means["cells"][cost][key][str(label)]["mean_y"] for label in range(5)])
            ev[cost] = float(row["decision_ask"]) * 100 * float(p_cal[index] @ conditional)
        output.append({
            "candidate_id": row["candidate_id"], "split": SPLIT,
            "p_model": p_model[index].tolist(), "p_cal": p_cal[index].tolist(),
            "ev_base": ev["base"], "ev_adverse": ev["adverse"],
            "scenario": row["scenario"], "status": row["status"],
            "payoff_is_lower_bound": row["payoff_is_lower_bound"],
        })
    return output


def compare_scores(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> None:
    require(len(expected) == len(actual), "score count")
    actual_by_id = {row["candidate_id"]: row for row in actual}
    require(len(actual_by_id) == len(actual), "duplicate actual score")
    for row in expected:
        other = actual_by_id.get(row["candidate_id"])
        require(other is not None and set(other) == set(row), "score identity/schema")
        for name in ("split", "scenario", "status", "payoff_is_lower_bound"):
            require(other[name] == row[name], f"score {name}")
        for name in ("ev_base", "ev_adverse"):
            require(math.isclose(float(other[name]), float(row[name]), abs_tol=1e-8), f"score {name}")
        for name in ("p_model", "p_cal"):
            require(np.allclose(np.asarray(other[name]), np.asarray(row[name]), atol=1e-10, rtol=0), f"score {name}")


def sessions_and_last_entry(coverage: dict[str, Any], dataset_manifest: dict[str, Any]) -> tuple[list[str], str]:
    dates = {ticker: [] for ticker in TICKERS}
    for row in coverage["calendar"]:
        dates[row["ticker"]].append(row["date"])
    reference = dates["SPY"]
    require(reference == sorted(set(reference)) and all(dates[ticker] == reference for ticker in TICKERS), "common calendar")
    last_entry = dataset_manifest["calendar_pin"]["last_eligible_entry"]
    require(last_entry in reference, "last entry")
    return reference, last_entry


def choose(candidates: list[dict[str, Any]], policy: str) -> tuple[dict[str, Any] | None, str]:
    if policy == "ALWAYS_ABSTAIN":
        return None, "ABSTAIN"
    if policy in {"ALWAYS_CALL_H2", "ALWAYS_PUT_H2"}:
        right = "CALL" if policy == "ALWAYS_CALL_H2" else "PUT"
        matches = [row for row in candidates if row["right"] == right]
        require(len(matches) <= 1, "multiple fixed side")
        return (matches[0], "FIXED_CONTROL") if matches else (None, "NO_SERIES")
    require(policy == "EV_TOP1_H2", "policy")
    if not candidates:
        return None, "NO_SERIES"
    best = max(row["_ev_adverse"] for row in candidates)
    matches = [row for row in candidates if row["_ev_adverse"] == best]
    if best <= 0:
        return None, "EV_NOT_POSITIVE"
    return (matches[0], "EV_TOP1") if len(matches) == 1 else (None, "EV_TIE_WAIT")


def independent_replay(
    rows: list[dict[str, Any]], coverage: dict[str, Any], sessions: list[str], last_entry: str,
    policy: str, cost: str,
) -> list[dict[str, Any]]:
    slip = 0.01 if cost == "base" else 0.02
    by_identity: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_identity[(row["entry_date"], row["ticker"])].append(row)
    cover = {(row["ticker"], row["entry_date"]): row for row in coverage["rows"]}
    opened, cash, reserved, ledger = {}, STARTING_CASH, 0.0, []
    for day in sessions:
        for ticker in TICKERS:
            if ticker in opened and opened[ticker]["exit_date"] == day:
                row = opened.pop(ticker)
                principal = (float(row["entry_ask"]) + slip) * 100
                bid = 0.0 if row["exit_bid"] is None else float(row["exit_bid"])
                cash += max(bid - slip, 0.0) * 100 - COMMISSION
                reserved -= principal
                ledger.append({
                    "event": "EXIT", "date": day, "ticker": ticker, "candidate_id": row["candidate_id"],
                    "status": row["status"], "split": SPLIT, "right": row["right"], "cost": cost,
                    "entry_date": row["entry_date"], "duration_calendar_days": row["duration_calendar_days"],
                    "net_usd": row[f"net_{cost}"], "cash": cash, "reserved": reserved, "equity": cash + reserved,
                    "realized_delta": row[f"net_{cost}"] + COMMISSION, "principal": principal,
                })
        for ticker in TICKERS:
            if day > last_entry:
                continue
            candidates = by_identity.get((day, ticker), [])
            if ticker in opened:
                ledger.append({"event": "WAIT", "date": day, "ticker": ticker, "split": SPLIT, "cost": cost, "reason": "OPEN_POSITION"})
                continue
            if not candidates:
                item = cover[(ticker, day)]
                ledger.append({"event": "NO_OPPORTUNITY", "date": day, "ticker": ticker, "split": SPLIT, "cost": cost, "reason": item.get("reason") or item["status"]})
                continue
            if policy in {"ALWAYS_CALL_H2", "ALWAYS_PUT_H2"}:
                side = "CALL" if policy == "ALWAYS_CALL_H2" else "PUT"
                if not any(row["right"] == side for row in candidates):
                    ledger.append({"event": "NO_OPPORTUNITY", "date": day, "ticker": ticker, "split": SPLIT, "cost": cost, "reason": f"{side}_SIDE_UNAVAILABLE"})
                    continue
            selected, reason = choose(candidates, policy)
            if selected is None:
                ledger.append({"event": "WAIT", "date": day, "ticker": ticker, "split": SPLIT, "cost": cost, "reason": reason})
                continue
            if selected["status"] == "NO_FILL":
                ledger.append({"event": "NO_FILL", "date": day, "ticker": ticker, "candidate_id": selected["candidate_id"], "split": SPLIT, "cost": cost, "reason": "ENTRY_QUOTE"})
                continue
            debit = float(selected[f"entry_debit_{cost}"])
            if cash < debit:
                ledger.append({"event": "CAPITAL_BLOCKED", "date": day, "ticker": ticker, "candidate_id": selected["candidate_id"], "split": SPLIT, "cost": cost, "reason": "CAPITAL"})
                continue
            cash -= debit
            principal = (float(selected["entry_ask"]) + slip) * 100
            reserved += principal
            opened[ticker] = selected
            ledger.append({
                "event": "ENTRY", "date": day, "ticker": ticker, "candidate_id": selected["candidate_id"],
                "right": selected["right"], "split": SPLIT, "cost": cost, "exit_date": selected["exit_date"],
                "selection_reason": reason, "ev_base": selected["_ev_base"], "ev_adverse": selected["_ev_adverse"],
                "cash": cash, "reserved": reserved, "equity": cash + reserved,
                "realized_delta": -COMMISSION, "principal": principal,
            })
    require(not opened and abs(reserved) <= 1e-7, "book close")
    require(math.isclose(cash, STARTING_CASH + math.fsum(row["net_usd"] for row in ledger if row["event"] == "EXIT"), abs_tol=1e-6), "cash")
    return ledger


def compare_ledgers(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> None:
    require(len(expected) == len(actual), "ledger length")
    for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
        require(set(left) == set(right), f"ledger schema {index}")
        for key, value in left.items():
            other = right[key]
            if isinstance(value, (float, int)) and not isinstance(value, bool):
                require(math.isclose(float(value), float(other), abs_tol=1e-8), f"ledger numeric {index}:{key}")
            else:
                require(value == other, f"ledger value {index}:{key}")


def ledger_metrics(ledger: list[dict[str, Any]], ticker: str | None = None) -> dict[str, Any]:
    rows = [row for row in ledger if ticker is None or row["ticker"] == ticker]
    exits = [row for row in rows if row["event"] == "EXIT"]
    values = [float(row["net_usd"]) for row in exits]
    gains, losses = math.fsum(value for value in values if value > 0), -math.fsum(value for value in values if value < 0)
    equity, peak, drawdown = STARTING_CASH, STARTING_CASH, 0.0
    for row in rows:
        if row["event"] in {"ENTRY", "EXIT"}:
            equity += float(row["realized_delta"])
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
    months: dict[str, float] = defaultdict(float)
    for row in exits:
        months[row["date"][:6]] += float(row["net_usd"])
    return {
        "trades": len(exits), "net_usd": math.fsum(values),
        "profit_factor": gains / losses if losses else (None if gains == 0 else "Infinity"),
        "realized_max_drawdown_usd": drawdown, "months_observed": len(months),
        "positive_months": sum(value > 0 for value in months.values()), "monthly_net_usd": dict(sorted(months.items())),
    }


def compare_summary_metrics(computed: dict[str, Any], summary: dict[str, Any], policy: str, cost: str) -> None:
    expected = summary["economics"][policy][cost]
    for scope, ticker in (("pooled", None), *((ticker, ticker) for ticker in TICKERS)):
        actual = ledger_metrics(computed[policy][cost], ticker)
        reference = expected["pooled"] if ticker is None else expected["tickers"][ticker]
        for key in ("trades", "months_observed", "positive_months"):
            require(actual[key] == reference[key], f"summary {policy}/{cost}/{scope}/{key}")
        for key in ("net_usd", "realized_max_drawdown_usd"):
            require(math.isclose(actual[key], float(reference[key]), abs_tol=1e-6), f"summary {policy}/{cost}/{scope}/{key}")
        require(actual["profit_factor"] == reference["profit_factor"] or math.isclose(float(actual["profit_factor"]), float(reference["profit_factor"]), abs_tol=1e-12), f"summary PF {policy}/{cost}/{scope}")
        require(math.isclose(math.fsum(actual["monthly_net_usd"].values()), actual["net_usd"], abs_tol=1e-8), "monthly reconciliation")


def augment_candidates(candidates: list[dict[str, Any]], scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    score_by_id = {row["candidate_id"]: row for row in scores}
    require(len(score_by_id) == len(scores), "duplicate score")
    output = []
    for row in candidates:
        score = score_by_id.get(row["candidate_id"])
        require(score is not None, "candidate score missing")
        copy = dict(row)
        copy["_ev_base"], copy["_ev_adverse"] = float(score["ev_base"]), float(score["ev_adverse"])
        from datetime import datetime
        copy["duration_calendar_days"] = (datetime.strptime(copy["exit_date"], "%Y%m%d") - datetime.strptime(copy["entry_date"], "%Y%m%d")).days
        output.append(copy)
    return output


def execute(
    dataset_root: Path, dataset_manifest_sha256: str, scorer_root: Path, scorer_manifest_sha256: str,
    frozen_root: Path, frozen_manifest_sha256: str, output: Path,
) -> dict[str, Any]:
    roots = [plain(dataset_root, "dataset"), plain(scorer_root, "scorer"), plain(frozen_root, "frozen")]
    output = plain(output, "output", exists=False)
    require(not output.exists(), "output exists")
    manifests = []
    for root, expected, label in zip(roots, (dataset_manifest_sha256, scorer_manifest_sha256, frozen_manifest_sha256), ("dataset", "scorer", "frozen"), strict=True):
        path = root / "manifest.json"
        require(sha256_file(path) == expected, f"external manifest {label}")
        manifests.append(read_json(path))
    dataset_manifest, scorer_manifest, frozen_manifest = manifests
    candidates_path, coverage_path = roots[0] / "candidates.jsonl", roots[0] / "coverage.json"
    verify(candidates_path, dataset_manifest["files"]["candidates.jsonl"], "candidates")
    verify(coverage_path, dataset_manifest["files"]["coverage.json"], "coverage")
    for name in FROZEN_FILES:
        verify(roots[2] / name, frozen_manifest["outputs"][name], name)
    verify(roots[1] / SCORE_FILE, scorer_manifest["outputs"][SCORE_FILE], SCORE_FILE)
    verify(roots[1] / SUMMARY_FILE, scorer_manifest["outputs"][SUMMARY_FILE], SUMMARY_FILE)
    candidates, coverage = read_jsonl(candidates_path), read_json(coverage_path)
    artifacts = {name: read_json(roots[2] / name) for name in FROZEN_FILES}
    independent = independent_scores(candidates, artifacts["model.json"], artifacts["transform.json"], artifacts["calibration_grid.json"], artifacts["conditional_means.json"])
    saved_scores = read_jsonl(roots[1] / SCORE_FILE)
    compare_scores(independent, saved_scores)
    rows = augment_candidates(candidates, independent)
    sessions, last_entry = sessions_and_last_entry(coverage, dataset_manifest)
    ledgers: dict[str, dict[str, list[dict[str, Any]]]] = {policy: {} for policy in POLICIES}
    for policy in POLICIES:
        for cost in COSTS:
            name = f"ledger_{policy.lower()}_q3_partial_2026_seen_development_{cost}.jsonl"
            verify(roots[1] / name, scorer_manifest["outputs"][name], name)
            expected = independent_replay(rows, coverage, sessions, last_entry, policy, cost)
            compare_ledgers(expected, read_jsonl(roots[1] / name))
            ledgers[policy][cost] = expected
    summary = read_json(roots[1] / SUMMARY_FILE)
    for policy in POLICIES:
        for cost in COSTS:
            compare_summary_metrics(ledgers, summary, policy, cost)
    report = {
        "schema": "weekly_h2_q3_given_parameters_numeric_audit_v1",
        "status": "PASS_NUMERIC_REPRODUCTION_GIVEN_FROZEN_PARAMETERS",
        "score_rows": len(independent), "books": 8,
        "checks": {
            "sklearn_parameters_restored_without_fit": True, "manual_transform": True,
            "predict_proba": True, "calibration_and_ev": True, "ledger_sequence_and_cash": True,
            "monthly_and_summary_reconciliation": True,
        },
        "flags": {"refit_performed": False, "selection_changed": False, "promotion_approved": False},
    }
    # Rehash compact authorities before publishing.
    for root, expected, label in zip(roots, (dataset_manifest_sha256, scorer_manifest_sha256, frozen_manifest_sha256), ("dataset", "scorer", "frozen"), strict=True):
        require(sha256_file(root / "manifest.json") == expected, f"closing manifest {label}")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "audit.json", report)
    write_json(output / "manifest.json", {
        "schema": "weekly_h2_q3_given_parameters_numeric_audit_manifest_v1",
        "inputs": {"dataset_manifest_sha256": dataset_manifest_sha256, "scorer_manifest_sha256": scorer_manifest_sha256, "frozen_manifest_sha256": frozen_manifest_sha256},
        "implementation": {"audit_weekly_h2_q3_given_parameters.py": sha256_file(Path(__file__))},
        "outputs": {"audit.json": {"bytes": (output / "audit.json").stat().st_size, "sha256": sha256_file(output / "audit.json")}},
        "flags": report["flags"],
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent Q3 frozen-parameter numeric audit")
    parser.add_argument("--execute-reviewed-audit", action="store_true")
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--dataset-manifest-sha256", required=True)
    parser.add_argument("--scorer-root", required=True, type=Path)
    parser.add_argument("--scorer-manifest-sha256", required=True)
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--frozen-manifest-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.execute_reviewed_audit:
        parser.error("execution requires --execute-reviewed-audit after Q3 closure")
    execute(args.dataset_root, args.dataset_manifest_sha256, args.scorer_root, args.scorer_manifest_sha256, args.frozen_root, args.frozen_manifest_sha256, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
