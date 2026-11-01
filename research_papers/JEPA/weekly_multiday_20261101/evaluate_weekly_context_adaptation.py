"""Causal monthly/weekly walk-forward adaptation for weekly H2 CONTEXT182.

The module is deliberately separate from every closed H1/Q3 experiment.  It
fits fresh logistic regressions only from an explicit point-in-time plan and
keeps the original frozen CONTEXT182 state as the guarded incumbent.  Real
execution is fail-closed behind the audited June/July bridge authorities.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import warnings
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import numpy as np
from sklearn.linear_model import LogisticRegression


WEEK = Path(__file__).resolve().parent
BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
OUTPUT = BASE / "h2_context_adaptation_01"
BRIDGE = BASE / "h2_boundary_bridge_01"
BRIDGE_AUDIT = BASE / "h2_boundary_bridge_audit_01"

CONTRACT = WEEK / "ADAPTATION_WALKFORWARD_CONTRACT_20261101.md"
CONTRACT_SHA256 = "608dae37c21c19277a36dbcc1eeaa36da0135385a080618d461a4e240855cc61"
CONTEXT_HELPER = WEEK / "evaluate_weekly_context_models.py"
CONTEXT_HELPER_SHA256 = "bdc6534f059ade7acc58f23952a88ed2068c7a712518b04f438945a583a07a2f"
EVALUATOR_HELPER = WEEK / "evaluate_weekly_h2_ev_v2.py"
EVALUATOR_HELPER_SHA256 = "8a9e75855d542a12662e5c812583f2ef86042f5c3ae1bbbad73c16042e063476"
REPLAY_HELPER = WEEK / "replay_equal_risk_frozen.py"
REPLAY_HELPER_SHA256 = "e4f42a9fa65120939cf5e131911c8f2990a9cd33d21ae036fa98d9eb816d5b9d"

ROOTS = {
    "dataset_h1": BASE / "h2_dataset_v2_01",
    "dataset_q3": BASE / "h2_dataset_v2_extension_2026q3_partial_01",
    "context_h1": BASE / "h2_context_1030_01",
    "context_q3": BASE / "h2_context_q3_1030_01",
    "comparison_h1": BASE / "h2_context_model_comparison_01",
    "comparison_q3": BASE / "h2_context_model_comparison_q3_01",
    "frozen_ev": BASE / "h2_ev_v2_01",
}
AUTHORITY_SHA256 = {
    "dataset_h1": "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8",
    "dataset_q3": "b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b",
    "context_h1": "77aaf00d60accc071ff1f58ec099cee72bc3a4150f89e4ad41a601821a74a38a",
    "context_q3": "1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66",
    "comparison_h1": "662ac63eaa2895beff4363b9e94a97cd7adc91aac3558139bdd919d8fbf2861a",
    "comparison_q3": "dcdc8b0bef5a508f40b322ba632109d4afaff689a3d0d36514f30d8618531e66",
    "frozen_ev": "54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96",
}
FROZEN_MODEL_SHA256 = "68712c7c326d2337a34f8401579ddc52a4dab0e3f505c8c4ff2f1b1d51c03fb4"
FROZEN_MEANS_SHA256 = "a8dc329233ce431b282c500e27cf91ac91d845cbb6a1fc752cee36026aef3f90"
H1_AUDIT_SHA256 = "bb661fe916f65ed6ee40dd3cf684650a8d318447005a7f224edec6a4b814b3eb"
Q3_CONTEXT_AUDIT_SHA256 = "ae90d005b6fa9a3a1a708fdfafd3361bdef9146312ddda324d103a139cd18633"
Q3_COMPARISON_AUDIT_SHA256 = "ef6a325b8f4defc579aa568ebd9dc980ede750e106a8ef4578b025d999215f69"

TICKERS = ("SPY", "QQQ", "SPXW")
RIGHTS = ("CALL", "PUT")
COSTS = ("base", "adverse")
POLICIES = ("FROZEN_CONTEXT182", "MONTHLY_RAW", "WEEKLY_RAW", "MONTHLY_GUARDED", "WEEKLY_GUARDED")
FIRST_EVAL, LAST_EVAL = "20260102", "20260917"
NY = ZoneInfo("America/New_York")
EXPECTED_SESSION_COUNT = 930
EXPECTED_EVAL_SESSION_COUNT = 178
EXPECTED_PHYSICAL_FITS = 42
EXPECTED_MONTHLY = 9
EXPECTED_WEEKLY = 38
EXPECTED_COINCIDENT = 5


class AdaptationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AdaptationError(message)


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
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def verify(path: Path, expected: dict[str, Any], label: str) -> None:
    actual = pin(path)
    require(actual["bytes"] == expected.get("bytes") and actual["sha256"] == expected.get("sha256"), f"pin {label}")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(plain(path, str(path)).read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    with plain(path, str(path)).open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL {path}:{number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"JSONL object {path}:{number}")
            values.append(value)
    return values


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def import_pinned(path: Path, expected_sha256: str, name: str) -> Any:
    path = plain(path, name)
    require(path.is_file() and sha256_file(path) == expected_sha256, f"{name} authority")
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"{name} import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(sha256_file(path) == expected_sha256, f"{name} changed during import")
    return module


def asof(date: str) -> datetime:
    return datetime.strptime(date, "%Y%m%d").replace(tzinfo=NY)


def available(row: dict[str, Any]) -> datetime:
    value = row.get("_available", row.get("label_available_at"))
    if isinstance(value, datetime):
        result = value
    else:
        require(isinstance(value, str), "label availability")
        result = datetime.fromisoformat(value)
    require(result.tzinfo is not None, "aware label availability")
    return result


def calendar_dates(coverage: dict[str, Any]) -> list[str]:
    rows = coverage.get("calendar")
    require(isinstance(rows, list), "coverage calendar")
    identities = {(item.get("ticker"), item.get("date")) for item in rows}
    dates = sorted({date for ticker, date in identities if ticker in TICKERS and isinstance(date, str)})
    require(identities == {(ticker, date) for ticker in TICKERS for date in dates}, "complete ticker calendar")
    return dates


def merge_coverages(h1: dict[str, Any], q3: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    calendars = [*h1.get("calendar", []), *q3.get("calendar", [])]
    require(len({(x["ticker"], x["date"]) for x in calendars}) == len(calendars), "calendar collision")
    base_rows = [*h1.get("rows", []), *q3.get("rows", [])]
    index = {(x["ticker"], x["entry_date"]): dict(x) for x in base_rows}
    require(len(index) == len(base_rows), "coverage collision")
    bridge_rows = overlay.get("rows")
    require(isinstance(bridge_rows, list) and len(bridge_rows) == 6, "bridge six coverage rows")
    expected = {(ticker, date) for ticker in TICKERS for date in ("20260629", "20260630")}
    require({(x.get("ticker"), x.get("entry_date")) for x in bridge_rows} == expected, "bridge exact scope")
    for item in bridge_rows:
        key = (item["ticker"], item["entry_date"])
        require(index[key].get("status") == "HORIZON_OUTSIDE_CALENDAR", "bridge replaces horizon only")
        index[key] = dict(item)
    merged = {"schema": "weekly_h2_coverage_adaptation_union_v1", "calendar": calendars, "rows": list(index.values())}
    dates = calendar_dates(merged)
    require(len(dates) == EXPECTED_SESSION_COUNT and len(calendars) == EXPECTED_SESSION_COUNT * 3, "union calendar scope")
    return merged


def validate_bridge_overlay(overlay: dict[str, Any], bridge_rows: list[dict[str, Any]]) -> None:
    require(overlay.get("schema") == "weekly_h2_boundary_bridge_coverage_overlay_v1", "bridge overlay schema")
    expected = {(ticker, date) for ticker in TICKERS for date in ("20260629", "20260630")}
    require({(item.get("ticker"), item.get("entry_date")) for item in overlay.get("replacement_keys", [])} == expected, "bridge replacement keys")
    candidate_tickers = {row["ticker"] for row in bridge_rows}
    require(all(row["entry_date"] == "20260629" and row["exit_date"] == "20260701" for row in bridge_rows), "bridge candidate scope")
    for item in overlay.get("rows", []):
        if item.get("entry_date") == "20260629":
            expected_status = "CANDIDATES_BUILT" if item.get("ticker") in candidate_tickers else "NO_DECISION_CANDIDATE"
            require(item.get("status") == expected_status and item.get("exit_date") == "20260701", "June29 bridge coverage")
        elif item.get("entry_date") == "20260630":
            require(item.get("status") == "NO_SERIES" and item.get("exit_date") == "20260702", "June30 bridge coverage")
        else:
            raise AdaptationError("bridge overlay date")


def creation_dates(sessions: list[str]) -> dict[str, list[str]]:
    evaluation = [day for day in sessions if FIRST_EVAL <= day <= LAST_EVAL]
    require(len(evaluation) == EXPECTED_EVAL_SESSION_COUNT, "evaluation sessions")
    monthly: list[str] = []
    weekly: list[str] = []
    for day in evaluation:
        if not monthly or monthly[-1][:6] != day[:6]:
            monthly.append(day)
        iso = datetime.strptime(day, "%Y%m%d").date().isocalendar()[:2]
        if not weekly or datetime.strptime(weekly[-1], "%Y%m%d").date().isocalendar()[:2] != iso:
            weekly.append(day)
    require(len(monthly) == EXPECTED_MONTHLY and len(weekly) == EXPECTED_WEEKLY, "creation counts")
    require(len(set(monthly) & set(weekly)) == EXPECTED_COINCIDENT, "coincident creation count")
    require(len(set(monthly) | set(weekly)) == EXPECTED_PHYSICAL_FITS, "physical fit count")
    return {"MONTHLY": monthly, "WEEKLY": weekly, "PHYSICAL": sorted(set(monthly) | set(weekly))}


def build_fit_plans(rows: list[dict[str, Any]], sessions: list[str]) -> list[dict[str, Any]]:
    schedules = creation_dates(sessions)
    index = {day: offset for offset, day in enumerate(sessions)}
    plans: list[dict[str, Any]] = []
    for day in schedules["PHYSICAL"]:
        i = index[day]
        require(i >= 65, f"63-session CAL unavailable {day}")
        cal_sessions = sessions[i - 65:i - 2]
        require(len(cal_sessions) == 63, "CAL session width")
        cal_start, cutoff = cal_sessions[0], asof(day)
        train_cutoff = asof(cal_start)
        train = [row for row in rows if row["entry_date"] < cal_start and available(row) < train_cutoff]
        purged = [row for row in rows if row["entry_date"] < cal_start and available(row) >= train_cutoff]
        cal = [row for row in rows if row["entry_date"] in set(cal_sessions) and available(row) < cutoff]
        require(train and len({int(row["scenario"]) for row in train}) >= 2, f"TRAIN class support {day}")
        require(cal, f"CAL empty {day}")
        require(all(available(row) < train_cutoff for row in train), "TRAIN future label")
        require(all(row["entry_date"] in set(cal_sessions) and available(row) < cutoff for row in cal), "CAL future label")
        frequencies = [name for name in ("MONTHLY", "WEEKLY") if day in schedules[name]]
        plans.append({
            "state_id": f"CONTEXT182_{day}", "creation_date": day,
            "asof": cutoff.isoformat(), "frequencies": frequencies,
            "cal_sessions": cal_sessions, "cal_start": cal_start, "cal_end": cal_sessions[-1],
            "train_ids": sorted(row["candidate_id"] for row in train),
            "cal_ids": sorted(row["candidate_id"] for row in cal),
            "purged_train_ids": sorted(row["candidate_id"] for row in purged),
            "train_label_available_max": max(available(row) for row in train).isoformat(),
            "cal_label_available_max": max(available(row) for row in cal).isoformat(),
        })
    require(len(plans) == EXPECTED_PHYSICAL_FITS, "exact fit plans")
    return plans


def train_rows(plan: dict[str, Any], by_id: dict[str, dict[str, Any]], key: str) -> list[dict[str, Any]]:
    values = [by_id[candidate_id] for candidate_id in plan[key]]
    require(len(values) == len(plan[key]), f"plan IDs {key}")
    return values


def fit_state(plan: dict[str, Any], by_id: dict[str, dict[str, Any]], context_helper: Any, evaluator: Any) -> dict[str, Any]:
    train = train_rows(plan, by_id, "train_ids")
    cal = train_rows(plan, by_id, "cal_ids")
    names = context_helper.context_names(by_id["__feature_names__"])
    transformer = context_helper.GenericTrainTransformer(names).fit(np.asarray([row["_x_context"] for row in train], dtype=float))
    # sklearn 1.8 warns for explicit penalty="l2" during its penalty migration;
    # omitting it with l1_ratio=0.0 is the documented effective L2 objective.
    model = LogisticRegression(C=1.0, l1_ratio=0.0, solver="lbfgs", max_iter=2000, random_state=0, warm_start=False)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        model.fit(transformer.transform(np.asarray([row["_x_context"] for row in train], dtype=float)), np.asarray([row["scenario"] for row in train], dtype=int))
    require(not captured, f"fit warning {plan['state_id']}: {[str(x.message) for x in captured]}")
    support = np.bincount(np.asarray([row["scenario"] for row in train], dtype=int), minlength=5)
    prior = support.astype(float) / len(train)
    means = evaluator.conditional_means(train)
    cal_model = evaluator.full_probabilities(model, transformer.transform(np.asarray([row["_x_context"] for row in cal], dtype=float)))
    alpha, grid = evaluator.choose_calibration(cal_model, np.asarray([row["scenario"] for row in cal], dtype=int), prior)
    return {
        **plan, "feature_order": names,
        "transform": transformer.as_dict(),
        "model": {"type": "LogisticRegression", "sklearn_version": importlib.metadata.version("scikit-learn"), "C": 1.0, "penalty": "l2", "constructor_penalty_omitted": True, "l1_ratio": 0.0, "solver": "lbfgs", "max_iter": 2000, "random_state": 0, "warm_start": False, "class_weight": None, "classes_present": model.classes_.astype(int).tolist(), "classes_full": list(range(5)), "coefficient": model.coef_.tolist(), "intercept": model.intercept_.tolist(), "fit_scope": "TRAIN_ONLY", "fit_warnings": []},
        "prior": prior.tolist(), "prior_support": support.tolist(), "conditional_means": means,
        "calibration": {"formula": "(1-alpha)*p_model+alpha*p_train_prior", "selected_alpha": alpha, "scores": grid},
        "_runtime": {"transformer": transformer, "model": model},
    }


def apply_saved_transform(matrix: np.ndarray, saved: dict[str, Any], names: list[str]) -> np.ndarray:
    require(saved.get("feature_order") == names, "transform feature order")
    medians = np.asarray(saved["medians"], dtype=float)
    require(matrix.shape[1] == len(medians), "transform width")
    filled = np.where(np.isnan(matrix), medians, matrix)
    indicators = np.isnan(matrix[:, np.asarray(saved["missing_indicator_source_indices"], dtype=int)]).astype(float)
    expanded = np.column_stack([filled, indicators])
    mean, scale = np.asarray(saved["scaler_mean"], dtype=float), np.asarray(saved["scaler_scale"], dtype=float)
    require(expanded.shape[1] == len(mean) == len(scale) and np.all(scale > 0), "scaler shape")
    return (expanded - mean) / scale


def saved_probabilities(matrix: np.ndarray, state: dict[str, Any]) -> np.ndarray:
    transformed = apply_saved_transform(matrix, state["transform"], state["feature_order"])
    model = state["model"]
    coefficient = np.asarray(model["coefficient"], dtype=float)
    intercept = np.asarray(model["intercept"], dtype=float)
    classes = [int(label) for label in model["classes_present"]]
    require(len(classes) >= 2 and len(classes) == len(set(classes)) and all(0 <= label < 5 for label in classes), "model classes")
    if len(classes) == 2:
        require(coefficient.shape == (1, transformed.shape[1]) and intercept.shape == (1,), "binary coefficient shape")
        logits = transformed @ coefficient[0] + intercept[0]
        positive = np.empty_like(logits)
        mask = logits >= 0
        positive[mask] = 1.0 / (1.0 + np.exp(-logits[mask]))
        exponential = np.exp(logits[~mask])
        positive[~mask] = exponential / (1.0 + exponential)
        partial = np.column_stack([1.0 - positive, positive])
    else:
        require(coefficient.shape == (len(classes), transformed.shape[1]) and intercept.shape == (len(classes),), "multiclass coefficient shape")
        logits = transformed @ coefficient.T + intercept
        logits -= logits.max(axis=1, keepdims=True)
        partial = np.exp(logits)
        partial /= partial.sum(axis=1, keepdims=True)
    output = np.zeros((len(matrix), 5), dtype=float)
    for column, label in enumerate(classes):
        output[:, label] = partial[:, column]
    return output


def score_state(state: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    matrix = np.asarray([row["_x_context"] for row in rows], dtype=float)
    runtime = state.get("_runtime")
    if runtime:
        partial = np.zeros((len(rows), 5), dtype=float)
        raw = runtime["model"].predict_proba(runtime["transformer"].transform(matrix))
        for column, label in enumerate(runtime["model"].classes_.astype(int)):
            partial[:, label] = raw[:, column]
    else:
        partial = saved_probabilities(matrix, state)
    alpha = float(state["calibration"]["selected_alpha"])
    prior = np.asarray(state["prior"], dtype=float)
    calibrated = (1 - alpha) * partial + alpha * prior
    output: list[dict[str, Any]] = []
    for row, p_model, p_cal in zip(rows, partial, calibrated, strict=True):
        key = f"{row['ticker']}:{row['right']}"
        item = {"candidate_id": row["candidate_id"], "entry_date": row["entry_date"], "ticker": row["ticker"], "right": row["right"], "model_id": state["state_id"], "p_model": p_model.tolist(), "p_cal": p_cal.tolist()}
        for cost in COSTS:
            means = np.asarray([state["conditional_means"]["cells"][cost][key][str(label)]["mean_y"] for label in range(5)])
            item[f"ev_{cost}"] = float(row["decision_ask"]) * 100 * float(np.dot(p_cal, means))
        output.append(item)
    return output


def attach_scores(rows: list[dict[str, Any]], scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index = {item["candidate_id"]: item for item in scores}
    require(len(index) == len(scores), "score IDs")
    result: list[dict[str, Any]] = []
    for row in rows:
        score = index.get(row["candidate_id"])
        require(score is not None, "missing score")
        value = dict(row)
        value["_ev_base"], value["_ev_adverse"] = score["ev_base"], score["ev_adverse"]
        value["_model_id"] = score["model_id"]
        result.append(value)
    return result


def logloss(rows: list[dict[str, Any]], scores: list[dict[str, Any]]) -> float:
    index = {item["candidate_id"]: item for item in scores}
    require(rows and set(index) == {row["candidate_id"] for row in rows}, "logloss same gate rows")
    return float(-np.mean([math.log(max(float(index[row["candidate_id"]]["p_cal"][int(row["scenario"])]), 1e-12)) for row in rows]))


def challenge_status(challenger_loss: float, incumbent_loss: float, challenger_net: float, incumbent_net: float, *, same_incumbent: bool, gate_rows: int) -> str:
    if gate_rows == 0:
        return "REJECTED_NO_GATE_ROWS"
    if not same_incumbent:
        return "STALE_CHALLENGER_REJECTED"
    if challenger_loss <= incumbent_loss and challenger_net >= incumbent_net:
        return "PROMOTED"
    return "REJECTED"


def proposal_gate(created: str, sessions: list[str]) -> list[str]:
    i = sessions.index(created)
    return sessions[i:i + 21]


def maturity_date(gate_sessions: list[str], sessions: list[str]) -> str | None:
    if len(gate_sessions) < 21:
        return None
    require(len(gate_sessions) == 21, "shadow at most 21 sessions")
    final = sessions.index(gate_sessions[-1])
    # H2 exits on final+2 at 10:35; strict D00 makes the following session first usable.
    return sessions[final + 3] if final + 3 < len(sessions) else None


def gate_labels_mature(rows: list[dict[str, Any]], gate_sessions: list[str], resolution_day: str) -> bool:
    gate = set(gate_sessions)
    return all(available(row) < asof(resolution_day) for row in rows if row["entry_date"] in gate)


def strip_runtime(state: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if key != "_runtime"}


def enrich_ledger(ledger: list[dict[str, Any]], policy: str, model_by_candidate: dict[str, str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for event in ledger:
        value = dict(event)
        value["policy"] = policy
        candidate_id = value.get("candidate_id")
        value["model_id"] = model_by_candidate.get(candidate_id) if candidate_id else None
        if value["event"] in {"ENTRY", "EXIT"}:
            require(value["model_id"] is not None, "position model trace")
        output.append(value)
    return output


def _manifest_pin(manifest: dict[str, Any], section: str, name: str) -> dict[str, Any]:
    value = manifest.get(section, {}).get(name)
    require(isinstance(value, dict) and set(value) >= {"bytes", "sha256"}, f"manifest {section}/{name}")
    return value


def manifest_payload(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    for section in ("outputs", "files"):
        value = manifest.get(section, {}).get(name)
        if isinstance(value, dict) and set(value) >= {"bytes", "sha256"}:
            return value
    raise AdaptationError(f"manifest payload {name}")


def normalize_candidate(raw: dict[str, Any], evaluator: Any) -> dict[str, Any]:
    require(set(raw) == evaluator.CANDIDATE_FIELDS, "candidate fields differ from contract")
    row = dict(raw)
    require(row["ticker"] in TICKERS and row["right"] in RIGHTS, "candidate identity")
    require(row["entry_date"] < row["exit_date"] < row["expiration"], "candidate calendar order")
    require(row["candidate_id"] == f"{row['ticker']}:{row['entry_date']}:{row['expiration']}:{row['right']}", "candidate ID")
    require(isinstance(row["features"], dict) and tuple(row["features"]) == evaluator.FEATURES, "candidate feature schema")
    values: list[float] = []
    for name in evaluator.FEATURES:
        value = row["features"][name]
        if value is None:
            require(name in evaluator.OPTIONAL, f"nonoptional feature {name}")
            values.append(math.nan)
        else:
            require(isinstance(value, (int, float)) and math.isfinite(float(value)), f"finite feature {name}")
            values.append(float(value))
    require(row["status"] in evaluator.STATUSES, "candidate status")
    require(math.isclose(float(row["decision_ask"]), values[10], abs_tol=1e-9, rel_tol=0), "decision ask feature")
    when = datetime.fromisoformat(row["label_available_at"])
    require(when.tzinfo is not None, "candidate availability aware")
    if row["status"] == "NO_FILL":
        require(row["scenario"] == 0 and when.strftime("%Y%m%d") == row["entry_date"], "NO_FILL semantics")
        require(row["entry_ask"] is None and row["exit_bid"] is None and not row["payoff_is_lower_bound"], "NO_FILL quote semantics")
        require(all(math.isclose(float(row[name]), 0.0, abs_tol=1e-9, rel_tol=0) for name in ("net_base", "net_adverse", "entry_debit_base", "entry_debit_adverse")), "NO_FILL economics")
    elif row["status"] == "OBSERVED_EXIT":
        require(row["scenario"] == evaluator.scenario_for(float(row["entry_ask"]), float(row["exit_bid"])), "observed scenario")
        require(when.strftime("%Y%m%d") == row["exit_date"] and not row["payoff_is_lower_bound"], "observed availability")
    else:
        require(row["scenario"] == 1 and row["exit_bid"] is None and row["payoff_is_lower_bound"], "missing exit lower bound")
        require(when.strftime("%Y%m%d") == row["exit_date"], "missing exit availability")
    if row["status"] != "NO_FILL":
        ask = float(row["entry_ask"])
        bid = 0.0 if row["exit_bid"] is None else float(row["exit_bid"])
        for cost, slip in (("base", 0.01), ("adverse", 0.02)):
            require(math.isclose(float(row[f"entry_debit_{cost}"]), evaluator.entry_debit(ask, slip), abs_tol=1e-9, rel_tol=0), f"{cost} entry debit")
            require(math.isclose(float(row[f"net_{cost}"]), evaluator.net_usd(ask, bid, slip), abs_tol=1e-9, rel_tol=0), f"{cost} net")
    row["_x"], row["_available"], row["_model_label_eligible"] = values, when, True
    return row


CONTEXT_FEATURE18 = (
    "ticker_SPY", "ticker_QQQ", "ticker_SPXW", "right_call", "dte", "weekday", "spot", "strike",
    "moneyness", "bid", "ask", "spread_relative", "delta", "implied_vol", "gamma", "theta", "vega", "rho",
)


def load_context_union(context_helper: Any, rows: list[dict[str, Any]], manifests: dict[str, dict[str, Any]], consumed: dict[Path, dict[str, Any]]) -> list[str]:
    context_rows: list[dict[str, Any]] = []
    names: list[str] | None = None
    for key in ("context_h1", "context_q3"):
        path = ROOTS[key] / "context.jsonl"
        expected = manifest_payload(manifests[key], "context.jsonl")
        verify(path, expected, key)
        consumed[path] = expected
        context_rows.extend(read_jsonl(path))
        current = manifests[key].get("feature_names")
        require(isinstance(current, list) and len(current) == 81, "context feature names")
        names = current if names is None else names
        require(current == names, "context feature names agree")
    identity = {(item["ticker"], item["date"]): item for item in context_rows}
    require(len(identity) == len(context_rows) == 2790, "context union identities")
    coverage = {"rows": [{"ticker": ticker, "date": date} for ticker, date in identity]}
    context_helper.join_context(rows, context_rows, coverage, names)
    return names


def frozen_state(feature_names: list[str], manifests: dict[str, dict[str, Any]], consumed: dict[Path, dict[str, Any]]) -> dict[str, Any]:
    comparison, frozen = ROOTS["comparison_h1"], ROOTS["frozen_ev"]
    paths = {
        "transform": comparison / "context182_transform.json", "model": comparison / "context182_model.json",
        "calibration": comparison / "context182_calibration.json", "frozen_model": frozen / "model.json",
        "means": frozen / "conditional_means.json",
    }
    for name in ("transform", "model", "calibration"):
        expected = manifest_payload(manifests["comparison_h1"], paths[name].name)
        verify(paths[name], expected, f"frozen context {name}")
        consumed[paths[name]] = expected
    for name in ("frozen_model", "means"):
        expected = manifest_payload(manifests["frozen_ev"], paths[name].name)
        verify(paths[name], expected, name)
        consumed[paths[name]] = expected
    require(sha256_file(paths["frozen_model"]) == FROZEN_MODEL_SHA256 and sha256_file(paths["means"]) == FROZEN_MEANS_SHA256, "frozen prior/means authority")
    prior_model = read_json(paths["frozen_model"])
    return {
        "state_id": "FROZEN_CONTEXT182_H1", "creation_date": None,
        "feature_order": [*CONTEXT_FEATURE18, *[f"context:{x}" for x in feature_names], *[f"side_context:{x}" for x in feature_names], "source_available", "state_valid"],
        "transform": read_json(paths["transform"]), "model": read_json(paths["model"]),
        "calibration": read_json(paths["calibration"]), "prior": prior_model["train_prior"],
        "conditional_means": read_json(paths["means"]),
    }


def gate_replay(
    proposal_id: str, role: str, state: dict[str, Any], rows: list[dict[str, Any]], gate_sessions: list[str],
    coverage: dict[str, Any], sessions: list[str], replay: Any,
) -> dict[str, Any]:
    gate_set = set(gate_sessions)
    gate_rows = [row for row in rows if row["entry_date"] in gate_set]
    require(state.get("creation_date") is None or all(state["creation_date"] <= row["entry_date"] for row in gate_rows), "state predates shadow rows")
    scores = score_state(state, gate_rows)
    if not gate_rows:
        return {"proposal_id": proposal_id, "role": role, "sessions": gate_sessions, "candidate_ids": [], "logloss": None, "net_adverse": 0.0, "adverse_metrics": None, "ledger_events": {"base": [], "adverse": []}}
    start = sessions.index(gate_sessions[0])
    final_entry = sessions.index(gate_sessions[-1])
    require(final_entry + 2 < len(sessions), "gate H2 exit calendar")
    end = final_entry + 2
    books = replay.replay_pair(attach_scores(gate_rows, scores), coverage, sessions[start:end + 1], gate_sessions[-1], "EV_TOP1_H2")
    metrics = replay.book_metrics(books["adverse"])
    return {
        "proposal_id": proposal_id, "role": role, "sessions": gate_sessions,
        "candidate_ids": sorted(row["candidate_id"] for row in gate_rows), "logloss": logloss(gate_rows, scores),
        "net_adverse": metrics["net_usd"], "adverse_metrics": metrics, "ledger_events": books,
    }


def simulate_guard(
    cadence: str, creation: list[str], states: dict[str, dict[str, Any]], frozen: dict[str, Any],
    rows: list[dict[str, Any]], coverage: dict[str, Any], sessions: list[str], eval_sessions: list[str], replay: Any,
) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    active = frozen["state_id"]
    active_by_day: dict[str, str] = {}
    proposals: list[dict[str, Any]] = []
    gate_results: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []
    state_index = {frozen["state_id"]: frozen, **states}
    by_resolution: dict[str, list[dict[str, Any]]] = {}
    for created in creation:
        gate = proposal_gate(created, sessions)
        mature = maturity_date(gate, sessions)
        proposal = {
            "proposal_id": f"{cadence}_{created}", "cadence": cadence, "created_date": created,
            "challenger_id": f"CONTEXT182_{created}", "incumbent_snapshot_id": None,
            "gate_sessions": gate, "maturity_date": mature, "status": "OPEN", "resolved_at": None,
            "effective_at": None, "comparison": None,
        }
        proposals.append(proposal)
        if mature is not None:
            by_resolution.setdefault(mature, []).append(proposal)
    proposal_by_created = {item["created_date"]: item for item in proposals}
    for day in eval_sessions:
        before = active
        resolved_today: list[str] = []
        for proposal in sorted(by_resolution.get(day, []), key=lambda item: item["created_date"]):
            require(gate_labels_mature(rows, proposal["gate_sessions"], day), "proposal labels mature before resolution as-of")
            challenger = state_index[proposal["challenger_id"]]
            incumbent = state_index[proposal["incumbent_snapshot_id"]]
            challenger_gate = gate_replay(proposal["proposal_id"], "CHALLENGER", challenger, rows, proposal["gate_sessions"], coverage, sessions, replay)
            incumbent_gate = gate_replay(proposal["proposal_id"], "INCUMBENT_SNAPSHOT", incumbent, rows, proposal["gate_sessions"], coverage, sessions, replay)
            gate_results.extend([challenger_gate, incumbent_gate])
            status = challenge_status(
                challenger_gate["logloss"] if challenger_gate["logloss"] is not None else math.inf,
                incumbent_gate["logloss"] if incumbent_gate["logloss"] is not None else math.inf,
                challenger_gate["net_adverse"], incumbent_gate["net_adverse"],
                same_incumbent=active == proposal["incumbent_snapshot_id"], gate_rows=len(challenger_gate["candidate_ids"]),
            )
            proposal["status"], proposal["resolved_at"] = status, day
            proposal["comparison"] = {
                "challenger_logloss": challenger_gate["logloss"], "incumbent_logloss": incumbent_gate["logloss"],
                "challenger_net_adverse": challenger_gate["net_adverse"], "incumbent_net_adverse": incumbent_gate["net_adverse"],
            }
            if status == "PROMOTED":
                active = proposal["challenger_id"]
                proposal["effective_at"] = day
            resolved_today.append(proposal["proposal_id"])
        if day in proposal_by_created:
            proposal_by_created[day]["incumbent_snapshot_id"] = active
        active_by_day[day] = active
        timeline.append({
            "date": day, "policy": f"{cadence}_GUARDED", "phase_order": "RESOLVE_CREATE_ACTIVATE_SCORE_EXECUTE",
            "active_model_before": before, "active_model_after": active,
            "created_proposal_id": proposal_by_created.get(day, {}).get("proposal_id"),
            "resolved_proposal_ids": resolved_today,
        })
    for proposal in proposals:
        if proposal["status"] == "OPEN":
            proposal["status"] = "PENDING_BEYOND_DECISION_CUTOFF"
    return active_by_day, proposals, gate_results, timeline


def generic_metrics(rows: list[dict[str, Any]], scores: list[dict[str, Any]], selected: set[str]) -> dict[str, Any]:
    index = {item["candidate_id"]: item for item in scores}
    output: dict[str, Any] = {}
    for observed_only in (False, True):
        for selected_only in (False, True):
            values = [row for row in rows if (not observed_only or not row["payoff_is_lower_bound"]) and (not selected_only or row["candidate_id"] in selected)]
            key = ("selected" if selected_only else "all") + ("_observed_only" if observed_only else "")
            if not values:
                output[key] = {"n": 0, "logloss": None, "brier": None, "reliability": [], "ev": {cost: {"bias": None, "mae": None} for cost in COSTS}}
                continue
            probabilities = np.asarray([index[row["candidate_id"]]["p_cal"] for row in values])
            labels = np.asarray([row["scenario"] for row in values], dtype=int)
            targets = np.eye(5)[labels]
            ev = {}
            for cost in COSTS:
                errors = np.asarray([index[row["candidate_id"]][f"ev_{cost}"] - row[f"net_{cost}"] for row in values])
                ev[cost] = {"bias": float(errors.mean()), "mae": float(np.abs(errors).mean())}
            reliability = []
            for label in range(5):
                for bin_index in range(10):
                    low, high = bin_index / 10, (bin_index + 1) / 10
                    mask = (probabilities[:, label] >= low) & ((probabilities[:, label] < high) | ((bin_index == 9) & (probabilities[:, label] <= high)))
                    if mask.any():
                        reliability.append({"class": label, "bin_low": low, "bin_high": high, "n": int(mask.sum()), "predicted": float(probabilities[mask, label].mean()), "observed": float((labels[mask] == label).mean())})
            output[key] = {"n": len(values), "logloss": float(-np.log(np.clip(probabilities[np.arange(len(labels)), labels], 1e-12, 1)).mean()), "brier": float(np.square(probabilities-targets).sum(axis=1).mean()), "reliability": reliability, "ev": ev}
    return output


def economic_details(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    exits = [event for event in ledger if event["event"] == "EXIT"]
    monthly = {f"2026{month:02d}": 0.0 for month in range(1, 10)}
    monthly_entry = {f"2026{month:02d}": 0.0 for month in range(1, 10)}
    blocks_exit = {"H1_2026": 0.0, "Q3_PARTIAL_2026": 0.0}
    blocks_entry = {"H1_2026": 0.0, "Q3_PARTIAL_2026": 0.0}
    sides = {right: 0.0 for right in RIGHTS}
    for event in exits:
        value = float(event["net_usd"])
        monthly[event["date"][:6]] += value
        monthly_entry[event["entry_date"][:6]] += value
        blocks_exit["H1_2026" if event["date"] <= "20260630" else "Q3_PARTIAL_2026"] += value
        blocks_entry["H1_2026" if event["entry_date"] <= "20260630" else "Q3_PARTIAL_2026"] += value
        sides[event["right"]] += value
    largest = max(exits, key=lambda event: abs(float(event["net_usd"])), default=None)
    net = math.fsum(float(event["net_usd"]) for event in exits)
    largest_month = max(monthly.items(), key=lambda item: abs(item[1]))[0]
    return {
        "monthly_net_including_zeros": monthly, "monthly_convention": "exit_date_realization",
        "monthly_net_by_entry_cohort_including_zeros": monthly_entry,
        "block_net_by_exit_realization": blocks_exit, "block_net_by_entry_cohort": blocks_entry, "side_net": sides,
        "event_counts": dict(sorted(Counter(event["event"] for event in ledger).items())),
        "selected_missing_or_lower_bound": sum(event.get("status") in {"MISSING_EXIT_SOURCE", "MISSING_EXIT_QUOTE"} for event in exits),
        "largest_trade": None if largest is None else {key: largest.get(key) for key in ("candidate_id", "date", "ticker", "right", "model_id", "net_usd")},
        "largest_month_by_absolute_net": largest_month,
        "net_without_largest_trade": net if largest is None else net - float(largest["net_usd"]),
        "net_without_largest_month": net - monthly[largest_month],
    }


def admit_sources(bridge_manifest: dict[str, Any], bridge_audit: dict[str, Any], evaluator: Any) -> dict[str, Any]:
    manifest_path, audit_path = BRIDGE / "manifest.json", BRIDGE_AUDIT / "audit.json"
    consumed: dict[Path, dict[str, Any]] = {manifest_path: pin(manifest_path), audit_path: pin(audit_path)}
    test_path = WEEK / "test_evaluate_weekly_context_adaptation.py"
    external = {"contract": pin(CONTRACT), "context_helper": pin(CONTEXT_HELPER), "evaluator_helper": pin(EVALUATOR_HELPER), "replay_helper": pin(REPLAY_HELPER), "producer": pin(Path(__file__)), "tests": pin(test_path), "bridge_manifest": pin(manifest_path), "bridge_audit": pin(audit_path)}
    manifests: dict[str, dict[str, Any]] = {}
    for name, root in ROOTS.items():
        path = plain(root / "manifest.json", f"{name} manifest")
        require(sha256_file(path) == AUTHORITY_SHA256[name], f"{name} manifest SHA")
        manifests[name] = read_json(path)
        consumed[path], external[name] = pin(path), pin(path)
    audits = {
        "context_q3_audit": (BASE / "h2_context_q3_1030_audit_01" / "audit.json", Q3_CONTEXT_AUDIT_SHA256),
        "comparison_h1_audit": (BASE / "h2_context_model_comparison_audit_01" / "audit.json", H1_AUDIT_SHA256),
        "comparison_q3_audit": (BASE / "h2_context_model_comparison_q3_audit_01" / "audit.json", Q3_COMPARISON_AUDIT_SHA256),
    }
    for name, (path, expected_sha) in audits.items():
        path = plain(path, name)
        require(sha256_file(path) == expected_sha, f"{name} SHA")
        consumed[path], external[name] = pin(path), pin(path)
    rows: list[dict[str, Any]] = []
    coverages: dict[str, dict[str, Any]] = {}
    for name in ("dataset_h1", "dataset_q3"):
        root, manifest = ROOTS[name], manifests[name]
        candidate_path, coverage_path = root / "candidates.jsonl", root / "coverage.json"
        for path in (candidate_path, coverage_path):
            expected = manifest_payload(manifest, path.name)
            verify(path, expected, f"{name}/{path.name}")
            consumed[path] = expected
        rows.extend(normalize_candidate(item, evaluator) for item in read_jsonl(candidate_path))
        coverages[name] = read_json(coverage_path)
    bridge_candidates, overlay_path = BRIDGE / "candidates.jsonl", BRIDGE / "coverage_overlay.json"
    for path in (bridge_candidates, overlay_path):
        expected = manifest_payload(bridge_manifest, path.name)
        verify(path, expected, f"bridge/{path.name}")
        consumed[path] = expected
    bridge_rows = [normalize_candidate(item, evaluator) for item in read_jsonl(bridge_candidates)]
    require(bridge_manifest.get("new_candidate_id_count") == len(bridge_rows), "bridge candidate count binding")
    rows.extend(bridge_rows)
    require(len({row["candidate_id"] for row in rows}) == len(rows) == 3234 + len(bridge_rows), "candidate union IDs")
    overlay = read_json(overlay_path)
    validate_bridge_overlay(overlay, bridge_rows)
    coverage = merge_coverages(coverages["dataset_h1"], coverages["dataset_q3"], overlay)
    return {"rows": rows, "bridge_rows": bridge_rows, "coverage": coverage, "manifests": manifests, "consumed": consumed, "external": external, "bridge_audit": bridge_audit}


def verify_frozen_common(frozen: dict[str, Any], rows: list[dict[str, Any]], manifests: dict[str, dict[str, Any]], consumed: dict[Path, dict[str, Any]]) -> None:
    expected_scores: dict[str, dict[str, Any]] = {}
    for key, filename in (("comparison_h1", "candidate_scores_context_comparison.jsonl"), ("comparison_q3", "candidate_scores_context_q3.jsonl")):
        path = ROOTS[key] / filename
        expected = manifest_payload(manifests[key], filename)
        verify(path, expected, f"{key} frozen scores")
        consumed[path] = expected
        expected_scores.update({item["candidate_id"]: item for item in read_jsonl(path)})
    common = [row for row in rows if row["candidate_id"] in expected_scores]
    require(len(common) == 3234, "frozen common candidates")
    for item in score_state(frozen, common):
        expected = expected_scores[item["candidate_id"]]
        require(np.allclose(item["p_cal"], expected["p_context182"], atol=1e-12, rtol=0), "frozen probability reproduction")
        require(math.isclose(item["ev_base"], expected["ev_context182_base"], abs_tol=1e-10, rel_tol=0), "frozen base EV reproduction")
        require(math.isclose(item["ev_adverse"], expected["ev_context182_adverse"], abs_tol=1e-10, rel_tol=0), "frozen adverse EV reproduction")


def execute_admitted(bridge_manifest: dict[str, Any], bridge_audit: dict[str, Any], context_helper: Any, evaluator: Any, replay: Any, output: Path) -> dict[str, Any]:
    admitted = admit_sources(bridge_manifest, bridge_audit, evaluator)
    rows, bridge_rows, coverage = admitted["rows"], admitted["bridge_rows"], admitted["coverage"]
    manifests, consumed, external = admitted["manifests"], admitted["consumed"], admitted["external"]
    sessions = calendar_dates(coverage)
    eval_sessions = [day for day in sessions if FIRST_EVAL <= day <= LAST_EVAL]
    feature_names = load_context_union(context_helper, rows, manifests, consumed)
    by_id = {row["candidate_id"]: row for row in rows}
    by_id["__feature_names__"] = feature_names  # type: ignore[assignment]
    plans = build_fit_plans(rows, sessions)
    states = {plan["state_id"]: fit_state(plan, by_id, context_helper, evaluator) for plan in plans}
    require(len(states) == EXPECTED_PHYSICAL_FITS, "42 physical fits")
    # Published coefficients, not transient estimator objects, are the scoring authority.
    for state in states.values():
        probe = [by_id[candidate_id] for candidate_id in state["cal_ids"][: min(7, len(state["cal_ids"]))]]
        runtime = score_state(state, probe)
        saved = score_state(strip_runtime(state), probe)
        for left, right in zip(runtime, saved, strict=True):
            require(np.allclose(left["p_model"], right["p_model"], atol=1e-12, rtol=0), "runtime/saved probability parity")
            require(math.isclose(left["ev_adverse"], right["ev_adverse"], abs_tol=1e-10, rel_tol=0), "runtime/saved EV parity")
    states = {key: strip_runtime(value) for key, value in states.items()}
    frozen = frozen_state(feature_names, manifests, consumed)
    verify_frozen_common(frozen, rows, manifests, consumed)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "fit_plans.json", {"schema": "weekly_context_adaptation_fit_plans_v1", "count": len(plans), "plans": plans})
    write_jsonl(output / "states.jsonl", [states[key] for key in sorted(states)])
    return finish_evaluation(rows, bridge_rows, coverage, sessions, eval_sessions, states, frozen, plans, replay, consumed, external, output)


def finish_evaluation(
    rows: list[dict[str, Any]], bridge_rows: list[dict[str, Any]], coverage: dict[str, Any], sessions: list[str],
    eval_sessions: list[str], states: dict[str, dict[str, Any]], frozen: dict[str, Any], plans: list[dict[str, Any]],
    replay: Any, consumed: dict[Path, dict[str, Any]], external: dict[str, dict[str, Any]], output: Path,
) -> dict[str, Any]:
    schedules = creation_dates(sessions)
    eval_rows = [row for row in rows if FIRST_EVAL <= row["entry_date"] <= LAST_EVAL]
    monthly_guard, monthly_proposals, monthly_gates, monthly_timeline = simulate_guard("MONTHLY", schedules["MONTHLY"], states, frozen, eval_rows, coverage, sessions, eval_sessions, replay)
    weekly_guard, weekly_proposals, weekly_gates, weekly_timeline = simulate_guard("WEEKLY", schedules["WEEKLY"], states, frozen, eval_rows, coverage, sessions, eval_sessions, replay)
    proposals, gate_results = [*monthly_proposals, *weekly_proposals], [*monthly_gates, *weekly_gates]

    def latest(day: str, cadence: str) -> str:
        choices = [value for value in schedules[cadence] if value <= day]
        require(bool(choices), f"active {cadence} state")
        return f"CONTEXT182_{choices[-1]}"

    active_maps = {
        "FROZEN_CONTEXT182": {day: frozen["state_id"] for day in eval_sessions},
        "MONTHLY_RAW": {day: latest(day, "MONTHLY") for day in eval_sessions},
        "WEEKLY_RAW": {day: latest(day, "WEEKLY") for day in eval_sessions},
        "MONTHLY_GUARDED": monthly_guard, "WEEKLY_GUARDED": weekly_guard,
    }
    state_index = {frozen["state_id"]: frozen, **states}
    rows_by_date = {day: [row for row in eval_rows if row["entry_date"] == day] for day in eval_sessions}
    policy_scores: dict[str, list[dict[str, Any]]] = {}
    score_rows: list[dict[str, Any]] = []
    timeline = [*monthly_timeline, *weekly_timeline]
    bridge_ids = {row["candidate_id"] for row in bridge_rows}
    for policy in POLICIES:
        values: list[dict[str, Any]] = []
        for day in eval_sessions:
            state_id = active_maps[policy][day]
            for item in score_state(state_index[state_id], rows_by_date[day]):
                source = next(row for row in rows_by_date[day] if row["candidate_id"] == item["candidate_id"])
                values.append({"policy": policy, **item, "scenario": source["scenario"], "payoff_is_lower_bound": source["payoff_is_lower_bound"], "is_bridge": item["candidate_id"] in bridge_ids})
        policy_scores[policy] = values
        score_rows.extend(values)
        if policy in {"FROZEN_CONTEXT182", "MONTHLY_RAW", "WEEKLY_RAW"}:
            previous = frozen["state_id"] if policy == "FROZEN_CONTEXT182" else "NO_ACTIVE_MODEL"
            for day in eval_sessions:
                current = active_maps[policy][day]
                timeline.append({"date": day, "policy": policy, "phase_order": "RESOLVE_CREATE_ACTIVATE_SCORE_EXECUTE", "active_model_before": previous, "active_model_after": current, "created_proposal_id": None, "resolved_proposal_ids": []})
                previous = current

    shadow_rows: list[dict[str, Any]] = []
    for proposal in proposals:
        incumbent = proposal["incumbent_snapshot_id"]
        require(incumbent in state_index, "proposal incumbent snapshot")
        gate_set = set(proposal["gate_sessions"])
        gate_rows = [row for row in eval_rows if row["entry_date"] in gate_set]
        for role, state_id in (("CHALLENGER", proposal["challenger_id"]), ("INCUMBENT_SNAPSHOT", incumbent)):
            require(state_index[state_id].get("creation_date") is None or all(state_index[state_id]["creation_date"] <= row["entry_date"] for row in gate_rows), "shadow state available by entry")
            shadow_rows.extend({"proposal_id": proposal["proposal_id"], "role": role, **item} for item in score_state(state_index[state_id], gate_rows))

    books: dict[str, dict[str, list[dict[str, Any]]]] = {}
    metrics: dict[str, Any] = {}
    for policy in POLICIES:
        raw_books = replay.replay_pair(attach_scores(eval_rows, policy_scores[policy]), coverage, eval_sessions, "20260915", "EV_TOP1_H2")
        model_map = {item["candidate_id"]: item["model_id"] for item in policy_scores[policy]}
        books[policy] = {cost: enrich_ledger(raw_books[cost], policy, model_map) for cost in COSTS}
        selected_events = {"ENTRY", "NO_FILL", "CAPITAL_BLOCKED"}
        selected = {event["candidate_id"] for event in books[policy]["adverse"] if event["event"] in selected_events and "candidate_id" in event}
        require(selected == {event["candidate_id"] for event in books[policy]["base"] if event["event"] in selected_events and "candidate_id" in event}, "paired policy decisions")
        filled = {event["candidate_id"] for event in books[policy]["adverse"] if event["event"] == "ENTRY"}
        metrics[policy] = {"economics": {cost: {**replay.book_metrics(books[policy][cost]), "details": economic_details(books[policy][cost])} for cost in COSTS}, "probability_ev": generic_metrics(eval_rows, policy_scores[policy], selected), "selected_ids": sorted(selected), "filled_ids": sorted(filled)}
    frozen_net = metrics["FROZEN_CONTEXT182"]["economics"]["adverse"]["net_usd"]
    for policy in POLICIES:
        metrics[policy]["adverse_net_minus_frozen"] = metrics[policy]["economics"]["adverse"]["net_usd"] - frozen_net
    guard_diagnostics: dict[str, Any] = {}
    for cadence, active, items in (("MONTHLY", monthly_guard, monthly_proposals), ("WEEKLY", weekly_guard, weekly_proposals)):
        promoted = [item for item in items if item["status"] == "PROMOTED"]
        final_model = active[eval_sessions[-1]]
        active_start = next(day for day in eval_sessions if active[day] == final_model)
        transfer = []
        guarded_policy = f"{cadence}_GUARDED"
        for promotion_index, item in enumerate(promoted):
            start = item["effective_at"]
            next_start = promoted[promotion_index + 1]["effective_at"] if promotion_index + 1 < len(promoted) else None
            period_sessions = [day for day in eval_sessions if day >= start and (next_start is None or day < next_start)]
            period_set = set(period_sessions)
            period_rows = [row for row in eval_rows if row["entry_date"] in period_set]
            period_ids = {row["candidate_id"] for row in period_rows}
            period_scores = [score for score in policy_scores[guarded_policy] if score["candidate_id"] in period_ids]
            period_events = [event for event in books[guarded_policy]["adverse"] if event.get("model_id") == item["challenger_id"]]
            period_selected = {event["candidate_id"] for event in period_events if event["event"] in {"ENTRY", "NO_FILL", "CAPITAL_BLOCKED"} and "candidate_id" in event}
            exits = [event for event in period_events if event["event"] == "EXIT"]
            monthly_net = {month: math.fsum(float(event["net_usd"]) for event in exits if event["entry_date"][:6] == month) for month in sorted({day[:6] for day in period_sessions})}
            block_net = {"H1_2026": math.fsum(float(event["net_usd"]) for event in exits if event["entry_date"] <= "20260630"), "Q3_PARTIAL_2026": math.fsum(float(event["net_usd"]) for event in exits if event["entry_date"] >= "20260701")}
            transfer.append({
                "model_id": item["challenger_id"], "effective_at": start,
                "period_end_inclusive": period_sessions[-1], "sessions": len(period_sessions),
                "candidates": len(period_rows), "trades": len(exits),
                "probability_ev": generic_metrics(period_rows, period_scores, period_selected),
                "main_book_adverse_exit_net": math.fsum(float(event["net_usd"]) for event in exits),
                "monthly_net_by_entry_cohort_including_zeros": monthly_net, "block_net_by_entry_cohort": block_net,
            })
        guard_diagnostics[cadence] = {
            "final_active_model": final_model, "promotions": len(promoted),
            "rejections": sum(item["status"] == "REJECTED" for item in items),
            "stale": sum(item["status"] == "STALE_CHALLENGER_REJECTED" for item in items),
            "pending": sum(item["status"] == "PENDING_BEYOND_DECISION_CUTOFF" for item in items),
            "active_model_age_sessions": eval_sessions.index(eval_sessions[-1]) - eval_sessions.index(active_start) + 1,
            "sessions_since_last_acceptance": len(eval_sessions) if not promoted else eval_sessions.index(eval_sessions[-1]) - eval_sessions.index(promoted[-1]["effective_at"]),
            "observed_post_activation_transfer": transfer,
        }
    raw_minus_guarded = {}
    for cadence in ("MONTHLY", "WEEKLY"):
        raw, guarded = metrics[f"{cadence}_RAW"], metrics[f"{cadence}_GUARDED"]
        raw_minus_guarded[cadence] = {
            "adverse_net_usd": raw["economics"]["adverse"]["net_usd"] - guarded["economics"]["adverse"]["net_usd"],
            "all_logloss": raw["probability_ev"]["all"]["logloss"] - guarded["probability_ev"]["all"]["logloss"],
            "all_adverse_ev_mae": raw["probability_ev"]["all"]["ev"]["adverse"]["mae"] - guarded["probability_ev"]["all"]["ev"]["adverse"]["mae"],
        }
    summary = {
        "schema": "weekly_context_adaptation_summary_v1", "status": "COMPLETE_SEEN_DEVELOPMENT_NOT_PROMOTED",
        "scope": {"sessions": len(eval_sessions), "candidates": len(eval_rows), "bridge_candidates": len(bridge_rows), "physical_fits": len(states), "monthly_creations": len(schedules["MONTHLY"]), "weekly_creations": len(schedules["WEEKLY"])},
        "policies": metrics, "raw_minus_guarded": raw_minus_guarded,
        "proposal_status_counts": dict(sorted(Counter(item["status"] for item in proposals).items())), "guard_diagnostics": guard_diagnostics,
        "flags": {"development_seen": True, "promotion_approved": False, "technical_ready": False, "raw_read": False, "api_read": False, "future_labels_used": False, "frozen_refit": False},
    }
    emit_outputs(output, score_rows, timeline, proposals, shadow_rows, gate_results, books, summary, consumed, external)
    return summary


def emit_outputs(
    output: Path, scores: list[dict[str, Any]], timeline: list[dict[str, Any]], proposals: list[dict[str, Any]],
    shadows: list[dict[str, Any]], gates: list[dict[str, Any]], books: dict[str, dict[str, list[dict[str, Any]]]],
    summary: dict[str, Any], consumed: dict[Path, dict[str, Any]], external: dict[str, dict[str, Any]],
) -> None:
    write_jsonl(output / "candidate_scores.jsonl", scores)
    write_jsonl(output / "policy_timeline.jsonl", sorted(timeline, key=lambda item: (item["date"], item["policy"])))
    write_jsonl(output / "proposals.jsonl", proposals)
    write_jsonl(output / "shadow_predictions.jsonl", shadows)
    write_jsonl(output / "gate_replays.jsonl", gates)
    for policy in POLICIES:
        for cost in COSTS:
            write_jsonl(output / f"ledger_{policy.lower()}_{cost}.jsonl", books[policy][cost])
    write_json(output / "summary.json", summary)
    for path, expected in consumed.items():
        verify(path, expected, f"closing {path}")
    for name, expected in external.items():
        verify(Path(expected["path"]), expected, f"closing authority {name}")
    outputs = {path.name: {key: value for key, value in pin(path).items() if key != "path"} for path in sorted(output.iterdir())}
    implementation = {"producer": external["producer"], "tests": external["tests"]}
    manifest_path = output / "manifest.json"
    write_json(manifest_path, {
        "schema": "weekly_context_adaptation_walkforward_v1", "status": "PASS_SEEN_DEVELOPMENT_GIVEN_BRIDGE_AND_FROZEN_AUTHORITIES",
        "external_authorities": external,
        "consumed_payloads": {str(path): {"path": str(path), "bytes": expected["bytes"], "sha256": expected["sha256"]} for path, expected in consumed.items()},
        "implementation": implementation, "outputs": outputs,
        "flags": {"raw_read": False, "api_read": False, "broker_read": False, "production_changed": False, "future_labels_used": False, "models_fit": True, "frozen_fit": False, "seen_development": True, "promotion_approved": False},
    })
    for path, expected in consumed.items():
        verify(path, expected, f"postwrite {path}")
    for name, expected in external.items():
        verify(Path(expected["path"]), expected, f"postwrite authority {name}")
    require(manifest_path.is_file(), "manifest persisted")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reviewed weekly H2 CONTEXT182 walk-forward adaptation")
    parser.add_argument("--execute-reviewed-adaptation", action="store_true")
    parser.add_argument("--bridge-manifest-sha256", required=True)
    parser.add_argument("--bridge-audit-sha256", required=True)
    args = parser.parse_args()
    if not args.execute_reviewed_adaptation:
        parser.error("execution requires --execute-reviewed-adaptation")
    require(len(args.bridge_manifest_sha256) == len(args.bridge_audit_sha256) == 64, "external SHA-256 arguments")
    run(args.bridge_manifest_sha256.lower(), args.bridge_audit_sha256.lower())
    return 0


def run(bridge_manifest_sha256: str, bridge_audit_sha256: str, output: Path = OUTPUT) -> dict[str, Any]:
    """Execute the reviewed walk-forward once against sealed authorities."""
    require(sha256_file(CONTRACT) == CONTRACT_SHA256, "contract authority")
    context_helper = import_pinned(CONTEXT_HELPER, CONTEXT_HELPER_SHA256, "adaptation_context_helper")
    evaluator = import_pinned(EVALUATOR_HELPER, EVALUATOR_HELPER_SHA256, "adaptation_evaluator_helper")
    replay = import_pinned(REPLAY_HELPER, REPLAY_HELPER_SHA256, "adaptation_replay_helper")
    output = plain(output, "output", exists=False)
    require(not output.exists(), "immutable output exists")
    manifest_path = plain(BRIDGE / "manifest.json", "bridge manifest")
    audit_path = plain(BRIDGE_AUDIT / "audit.json", "bridge audit")
    require(sha256_file(manifest_path) == bridge_manifest_sha256, "bridge manifest SHA")
    require(sha256_file(audit_path) == bridge_audit_sha256, "bridge audit SHA")
    bridge_manifest, bridge_audit = read_json(manifest_path), read_json(audit_path)
    require(bridge_manifest.get("schema") == "weekly_h2_boundary_bridge_manifest_v1", "bridge schema")
    require(bridge_manifest.get("status") == "COMPLETE_WEEKLY_H2_BOUNDARY_BRIDGE_NOT_EVALUATED", "bridge status")
    require(bridge_manifest.get("split") == "H1_Q3_BOUNDARY_2026_SEEN_DEVELOPMENT" and bridge_manifest.get("old_candidate_id_count") == 3234, "bridge declared scope")
    require(bridge_manifest.get("flags") == {"fit_performed": False, "economic_evaluation_performed": False, "promotion_approved": False, "originals_modified": False, "development_seen": True, "not_oos": True}, "bridge flags")
    require(bridge_audit.get("schema") == "weekly_h2_boundary_bridge_audit_v1", "bridge audit schema")
    require(bridge_audit.get("status") == "PASS_INDEPENDENT_BOUNDARY_BRIDGE_GIVEN_FROZEN_BUILDERS", "bridge audit status")
    binding = bridge_audit.get("inputs", {}).get("producer_manifest")
    expected_binding = pin(manifest_path)
    require(isinstance(binding, dict) and all(binding.get(key) == expected_binding[key] for key in ("path", "bytes", "sha256")), "bridge audit binds producer")
    return execute_admitted(bridge_manifest, bridge_audit, context_helper, evaluator, replay, output)


if __name__ == "__main__":
    raise SystemExit(main())
