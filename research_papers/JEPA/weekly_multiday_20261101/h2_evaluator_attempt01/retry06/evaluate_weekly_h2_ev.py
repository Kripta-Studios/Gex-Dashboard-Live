from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import stat
from typing import Any, Iterable
import warnings
from zoneinfo import ZoneInfo

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

CONTRACT = Path(__file__).with_name("ECONOMIC_H2_CONTRACT.md")
CONTRACT_SHA256 = "245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5"
BUILDER_SHA256 = "eb0cba11d9e865909ee518efe825527e127d90c52b47339fa8e0b3fa699a1e67"
SOURCE_PILOT_SHA256 = "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878"
CALENDAR_SHA256 = "7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4"
FEATURES = (
    "ticker_SPY", "ticker_QQQ", "ticker_SPXW", "right_call", "dte", "weekday",
    "spot", "strike", "moneyness", "bid", "ask", "spread_relative", "delta",
    "implied_vol", "gamma", "theta", "vega", "rho",
)
OPTIONAL = {"implied_vol", "gamma", "theta", "vega", "rho"}
TICKERS = ("SPY", "QQQ", "SPXW")
RIGHTS = ("CALL", "PUT")
STATUSES = {"NO_FILL", "OBSERVED_EXIT", "MISSING_EXIT_QUOTE", "MISSING_EXIT_SOURCE"}
CANDIDATE_FIELDS = {
    "candidate_id", "ticker", "entry_date", "exit_date", "expiration", "strike",
    "right", "features", "decision_ask", "entry_ask", "exit_bid", "status",
    "label_available_at", "scenario", "net_base", "net_adverse",
    "entry_debit_base", "entry_debit_adverse", "payoff_is_lower_bound", "source_pins",
}
SOURCE_PIN_FIELDS = {
    "calendar_sha256", "entry_path", "entry_sha256", "exit_path", "exit_sha256",
    "clock_basis_entry", "clock_basis_exit",
}
ALPHAS = tuple(round(index / 10, 1) for index in range(11))
STARTING_CASH = 100_000.0
NY = ZoneInfo("America/New_York")


class EvaluationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvaluationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_plain_path(path: Path, name: str) -> Path:
    absolute = Path(os.path.abspath(path))
    current = absolute
    while True:
        try:
            info = current.lstat()
        except FileNotFoundError:
            info = None
        if info is not None:
            is_reparse = bool(getattr(info, "st_file_attributes", 0) & 0x400)
            require(not stat.S_ISLNK(info.st_mode) and not is_reparse, f"{name} or ancestor is link/reparse")
        if current.parent == current:
            break
        current = current.parent
    require(not str(absolute).lower().startswith("d:\\thetadata\\"), f"{name} cannot be inside D:/ThetaData")
    return absolute


def finite_number(value: Any, name: str, *, nullable: bool = False) -> float | None:
    if value is None and nullable:
        return None
    require(not isinstance(value, bool) and isinstance(value, (int, float)), f"{name} not numeric")
    number = float(value)
    require(math.isfinite(number), f"{name} not finite")
    return number


def close(actual: Any, expected: float, name: str, tolerance: float = 1e-8) -> None:
    value = finite_number(actual, name)
    require(abs(float(value) - expected) <= tolerance, f"{name} mismatch")


def parse_day(value: Any, name: str) -> str:
    require(isinstance(value, str) and len(value) == 8 and value.isdigit(), f"{name} format")
    datetime.strptime(value, "%Y%m%d")
    return value


def parse_available(value: Any, name: str) -> datetime | None:
    if value is None:
        return None
    require(isinstance(value, str), f"{name} format")
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, f"{name} must have offset")
    local = parsed.astimezone(NY)
    require(
        parsed.utcoffset() == local.utcoffset()
        and parsed.hour == 10 and parsed.minute == 35 and parsed.second == 0 and parsed.microsecond == 0,
        f"{name} must be exact 10:35 America/New_York",
    )
    return parsed


def net_usd(entry_ask: float, exit_bid: float, slip: float) -> float:
    return (max(exit_bid - slip, 0.0) - entry_ask - slip) * 100.0 - 2.60


def entry_debit(entry_ask: float, slip: float) -> float:
    return (entry_ask + slip) * 100.0 + 1.30


def scenario_for(entry_ask: float, exit_bid: float) -> int:
    value = (exit_bid - entry_ask) / entry_ask
    return 1 if value < -0.25 else 2 if value < 0 else 3 if value < 0.25 else 4


def validate_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    require(set(raw) == CANDIDATE_FIELDS, "candidate fields differ from contract")
    row = dict(raw)
    ticker, right = row["ticker"], row["right"]
    require(ticker in TICKERS and right in RIGHTS, "candidate ticker/right")
    entry = parse_day(row["entry_date"], "entry_date")
    exit_date = parse_day(row["exit_date"], "exit_date")
    expiration = parse_day(row["expiration"], "expiration")
    entry_dt = datetime.strptime(entry, "%Y%m%d")
    expiration_dt = datetime.strptime(expiration, "%Y%m%d")
    require(entry < exit_date < expiration, "candidate calendar ordering")
    require(row["candidate_id"] == f"{ticker}:{entry}:{expiration}:{right}", "candidate_id mismatch")
    features = row["features"]
    require(isinstance(features, dict) and tuple(features) == FEATURES, "feature order/schema")
    values = []
    for name in FEATURES:
        value = finite_number(features[name], f"feature {name}", nullable=name in OPTIONAL)
        values.append(np.nan if value is None else float(value))
    require(values[:3] == [float(ticker == item) for item in TICKERS], "ticker one-hot mismatch")
    require(values[3] == float(right == "CALL"), "right feature mismatch")
    require(values[4] == (expiration_dt - entry_dt).days and 1 <= values[4] <= 8, "DTE mismatch")
    require(values[5] == entry_dt.weekday(), "weekday mismatch")
    require(values[6] > 0 and values[7] > 0, "spot/strike invalid")
    close(values[8], values[7] / values[6] - 1, "moneyness")
    require(0 <= values[9] <= values[10] and 0 < values[10] <= 49.95, "decision quote invalid")
    close(values[11], (values[10] - values[9]) / values[10], "spread_relative")
    require(-1 <= values[12] <= 1 and ((right == "CALL" and values[12] > 0) or (right == "PUT" and values[12] < 0)), "delta invalid")
    close(row["decision_ask"], values[10], "decision_ask")
    close(row["strike"], values[7], "strike")
    require(row["status"] in STATUSES, "candidate status")
    pins = row["source_pins"]
    require(isinstance(pins, dict) and set(pins) == SOURCE_PIN_FIELDS, "source pin schema")
    require(pins["calendar_sha256"] == CALENDAR_SHA256, "source calendar pin")
    available = parse_available(row["label_available_at"], "label_available_at")
    if row["status"] == "NO_FILL":
        require(row["scenario"] == 0 and available is not None, "NO_FILL label")
        require(available.strftime("%Y%m%d") == entry, "NO_FILL availability date")
        require(row["payoff_is_lower_bound"] is False, "NO_FILL lower-bound flag")
        require(row["entry_ask"] is None and row["exit_bid"] is None, "NO_FILL quotes")
        for field in ("net_base", "net_adverse", "entry_debit_base", "entry_debit_adverse"):
            close(row[field], 0.0, field)
    else:
        ask = float(finite_number(row["entry_ask"], "entry_ask"))
        require(0 < ask <= 49.95, "filled entry ask")
        close(row["entry_debit_base"], entry_debit(ask, 0.01), "entry_debit_base")
        close(row["entry_debit_adverse"], entry_debit(ask, 0.02), "entry_debit_adverse")
        if row["status"] == "OBSERVED_EXIT":
            bid = float(finite_number(row["exit_bid"], "exit_bid"))
            require(bid >= 0 and available is not None, "observed exit")
            require(row["scenario"] == scenario_for(ask, bid), "observed scenario")
            require(available.strftime("%Y%m%d") == exit_date, "observed availability date")
            require(row["payoff_is_lower_bound"] is False, "observed lower-bound flag")
        else:
            require(row["scenario"] == 1 and available is not None and row["exit_bid"] is None, "missing exit label")
            require(available.strftime("%Y%m%d") == exit_date, "missing availability date")
            require(row["payoff_is_lower_bound"] is True, "missing exit lower-bound flag")
            bid = 0.0
        close(row["net_base"], net_usd(ask, bid, 0.01), "net_base")
        close(row["net_adverse"], net_usd(ask, bid, 0.02), "net_adverse")
    row["_x"], row["_available"] = values, available
    return row


def _manifest_pin(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    files = manifest.get("files")
    require(isinstance(files, dict) and isinstance(files.get(name), dict), f"manifest missing {name}")
    pin = files[name]
    require(set(pin) >= {"bytes", "sha256", "rows"}, f"manifest pin schema {name}")
    return pin


def load_inputs(candidates_path: Path, coverage_path: Path, manifest_path: Path, manifest_sha256: str) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    candidates_path, coverage_path, manifest_path = (
        assert_plain_path(path, name) for path, name in (
            (candidates_path, "candidates"), (coverage_path, "coverage"), (manifest_path, "manifest")
        )
    )
    require(candidates_path.parent == coverage_path.parent == manifest_path.parent, "inputs must share one dataset root")
    for path in (candidates_path, coverage_path, manifest_path):
        require(path.is_file() and not path.is_symlink(), f"invalid input path: {path}")
    require(len(manifest_sha256) == 64 and sha256_file(manifest_path) == manifest_sha256, "external manifest SHA-256 mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("schema") == "weekly_h2_dataset_manifest_v1", "manifest schema")
    require(manifest.get("status") == "COMPLETE_WEEKLY_H2_DATASET_NOT_EVALUATED", "manifest status")
    require(isinstance(manifest.get("calendar"), dict) and manifest["calendar"].get("sha256") == CALENDAR_SHA256, "manifest calendar pin")
    flags = manifest.get("flags")
    require(isinstance(flags, dict), "manifest flags")
    for name in ("fit_performed", "economic_evaluation_performed", "promotion_approved"):
        require(flags.get(name) is False, f"manifest flag {name}")
    implementation_pins = manifest.get("implementation_pins")
    require(
        isinstance(implementation_pins, dict)
        and set(implementation_pins) == {"build_weekly_h2_dataset.py", "weekly_multiday_source_pilot.py", "ECONOMIC_H2_CONTRACT.md"},
        "dataset implementation pins",
    )
    require(sha256_file(CONTRACT) == CONTRACT_SHA256, "local economic contract pin")
    require(
        implementation_pins == {
            "build_weekly_h2_dataset.py": BUILDER_SHA256,
            "weekly_multiday_source_pilot.py": SOURCE_PILOT_SHA256,
            "ECONOMIC_H2_CONTRACT.md": CONTRACT_SHA256,
        },
        "dataset implementation pin values",
    )
    inventory_pin = _manifest_pin(manifest, "inventory.json")
    inventory_path = assert_plain_path(manifest_path.parent / "inventory.json", "inventory")
    require(
        inventory_path.is_file() and inventory_pin["sha256"] == sha256_file(inventory_path)
        and inventory_pin["bytes"] == inventory_path.stat().st_size
        and manifest.get("inventory_bound_sha256") == inventory_pin["sha256"],
        "inventory binding",
    )
    for name, path in (("candidates.jsonl", candidates_path), ("coverage.json", coverage_path)):
        pin = _manifest_pin(manifest, name)
        require(pin["bytes"] == path.stat().st_size and pin["sha256"] == sha256_file(path), f"manifest hash mismatch {name}")
    rows, ids = [], set()
    with candidates_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank candidate line {line_number}")
            row = validate_candidate(json.loads(line))
            require(row["candidate_id"] not in ids, "duplicate candidate_id")
            ids.add(row["candidate_id"])
            rows.append(row)
    require(_manifest_pin(manifest, "candidates.jsonl")["rows"] == len(rows), "candidate row count")
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    require(
        coverage.get("schema") == "weekly_h2_coverage_v1"
        and isinstance(coverage.get("rows"), list) and isinstance(coverage.get("calendar"), list),
        "coverage schema",
    )
    calendar_by_ticker: dict[str, list[str]] = {ticker: [] for ticker in TICKERS}
    calendar_ids = set()
    for item in coverage["calendar"]:
        require(isinstance(item, dict) and item.get("ticker") in TICKERS, "coverage calendar row")
        day = parse_day(item.get("date"), "calendar date")
        require(item.get("close_i") in {210, 390}, "calendar close_i")
        identity = (item["ticker"], day)
        require(identity not in calendar_ids, "duplicate calendar identity")
        calendar_ids.add(identity)
        calendar_by_ticker[item["ticker"]].append(day)
    for ticker in TICKERS:
        calendar_by_ticker[ticker].sort()
    coverage_ids: list[str] = []
    coverage_identity = set()
    candidate_index = {row["candidate_id"]: row for row in rows}
    for item in coverage["rows"]:
        require(isinstance(item, dict) and isinstance(item.get("candidate_ids"), list), "coverage row")
        ticker = item.get("ticker")
        entry_date = parse_day(item.get("entry_date"), "coverage entry_date")
        identity = (ticker, entry_date)
        require(ticker in TICKERS and identity not in coverage_identity, "duplicate/invalid coverage identity")
        coverage_identity.add(identity)
        require(identity in calendar_ids, "coverage identity outside calendar")
        sessions = calendar_by_ticker[ticker]
        index = sessions.index(entry_date)
        expected_exit = sessions[index + 2] if index + 2 < len(sessions) else None
        require(item.get("exit_date") == expected_exit, "coverage H2 is not second official session")
        if expected_exit is None:
            require(item.get("status") == "HORIZON_OUTSIDE_CALENDAR" and not item["candidate_ids"], "outside-calendar coverage semantics")
        rights = []
        for candidate_id in item["candidate_ids"]:
            require(candidate_id in candidate_index, "coverage references unknown candidate")
            candidate = candidate_index[candidate_id]
            require(candidate["ticker"] == ticker and candidate["entry_date"] == entry_date, "candidate coverage identity")
            require(candidate["exit_date"] == expected_exit and candidate["expiration"] == item.get("expiration"), "candidate coverage H2/expiration")
            rights.append(candidate["right"])
        require(len(rights) == len(set(rights)), "duplicate right per coverage session")
        coverage_ids.extend(item["candidate_ids"])
    require(coverage_identity == calendar_ids, "coverage does not contain every ticker/session")
    require(len(coverage_ids) == len(set(coverage_ids)) and set(coverage_ids) == ids, "coverage candidate universe")
    require(_manifest_pin(manifest, "coverage.json")["rows"] == len(coverage["rows"]), "coverage row count")
    return rows, coverage, manifest


class StableTrainTransformer:
    def __init__(self) -> None:
        self.imputer = SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)
        self.scaler = StandardScaler()

    def fit(self, values: np.ndarray) -> "StableTrainTransformer":
        require(values.ndim == 2 and values.shape[1] == len(FEATURES) and len(values) > 0, "transformer TRAIN shape")
        self.scaler.fit(self.imputer.fit_transform(values))
        return self

    def transform(self, values: np.ndarray) -> np.ndarray:
        require(hasattr(self.imputer, "statistics_"), "transformer not fitted")
        return self.scaler.transform(self.imputer.transform(values))

    def as_dict(self) -> dict[str, Any]:
        require(hasattr(self.imputer, "statistics_"), "transformer not fitted")
        indicator_indices = self.imputer.indicator_.features_.astype(int).tolist()
        return {
            "feature_order": list(FEATURES),
            "missing_indicator_order": [f"{FEATURES[index]}__missing" for index in indicator_indices],
            "missing_indicator_source_indices": indicator_indices,
            "medians": self.imputer.statistics_.tolist(), "scaler_mean": self.scaler.mean_.tolist(),
            "scaler_scale": self.scaler.scale_.tolist(), "fit_scope": "TRAIN_ONLY",
            "imputer": {"strategy": "median", "add_indicator": True, "keep_empty_features": True},
        }


def split_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {"TRAIN": [], "CAL": [], "EVAL": []}
    for row in rows:
        date = row["entry_date"]
        if "20230103" <= date <= "20241231":
            split, cutoff = "TRAIN", datetime.fromisoformat("2025-01-01T00:00:00-05:00")
        elif "20250101" <= date <= "20251231":
            split, cutoff = "CAL", datetime.fromisoformat("2026-01-01T00:00:00-05:00")
        elif "20260101" <= date <= "20260630":
            split, cutoff = "EVAL", None
        else:
            raise EvaluationError("candidate outside fixed temporal splits")
        row["_split"] = split
        row["_model_label_eligible"] = bool(
            row["_available"] is not None
            and (cutoff is None or row["_available"] < cutoff)
        )
        result[split].append(row)
    return result


def full_probabilities(model: LogisticRegression, values: np.ndarray) -> np.ndarray:
    partial = model.predict_proba(values)
    output = np.zeros((len(values), 5), dtype=float)
    for source, label in enumerate(model.classes_.astype(int)):
        output[:, label] = partial[:, source]
    return output


def log_loss_fixed(labels: np.ndarray, probabilities: np.ndarray) -> float:
    clipped = np.clip(probabilities[np.arange(len(labels)), labels], 1e-12, 1.0)
    return float(-np.log(clipped).mean())


def choose_calibration(model_prob: np.ndarray, labels: np.ndarray, prior: np.ndarray) -> tuple[float, list[dict[str, float]]]:
    require(len(labels) > 0, "CAL has no eligible labels")
    grid = []
    for alpha in ALPHAS:
        mixed = (1 - alpha) * model_prob + alpha * prior
        grid.append({"alpha": alpha, "log_loss": log_loss_fixed(labels, mixed)})
    best = min(grid, key=lambda item: (item["log_loss"], item["alpha"]))
    return float(best["alpha"]), grid


def conditional_means(train: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in train if row["_model_label_eligible"]]
    output: dict[str, Any] = {"shrinkage": 20, "global": {}, "cells": {}}
    for cost in ("base", "adverse"):
        by_class: dict[int, list[float]] = defaultdict(list)
        cells: dict[tuple[int, str, str], list[float]] = defaultdict(list)
        for row in eligible:
            label = int(row["scenario"])
            value = float(row[f"net_{cost}"]) / (float(row["decision_ask"]) * 100)
            by_class[label].append(value)
            cells[(label, row["ticker"], row["right"])].append(value)
        global_means = {str(label): (float(np.mean(by_class[label])) if by_class[label] else 0.0) for label in range(5)}
        output["global"][cost], output["cells"][cost] = global_means, {}
        for ticker in TICKERS:
            for right in RIGHTS:
                key = f"{ticker}:{right}"
                output["cells"][cost][key] = {}
                for label in range(5):
                    values = cells[(label, ticker, right)]
                    mean = (sum(values) + 20 * global_means[str(label)]) / (len(values) + 20)
                    output["cells"][cost][key][str(label)] = {"n": len(values), "mean_y": float(mean)}
    return output


def score_rows(rows: list[dict[str, Any]], transformer: StableTrainTransformer, model: LogisticRegression, alpha: float, prior: np.ndarray, means: dict[str, Any]) -> None:
    matrix = np.asarray([row["_x"] for row in rows], dtype=float)
    probabilities = full_probabilities(model, transformer.transform(matrix))
    calibrated = (1 - alpha) * probabilities + alpha * prior
    for row, p_model, p_cal in zip(rows, probabilities, calibrated, strict=True):
        row["_p_model"], row["_p_cal"] = p_model.tolist(), p_cal.tolist()
        key = f"{row['ticker']}:{row['right']}"
        for cost in ("base", "adverse"):
            conditional = np.asarray([means["cells"][cost][key][str(label)]["mean_y"] for label in range(5)])
            row[f"_ev_{cost}"] = float(row["decision_ask"]) * 100 * float(np.dot(p_cal, conditional))


def probability_metrics(rows: list[dict[str, Any]], *, observed_only: bool = False) -> dict[str, Any]:
    labeled = [
        row for row in rows if row["_model_label_eligible"]
        and (not observed_only or not row["payoff_is_lower_bound"])
    ]
    if not labeled:
        return {"n": 0, "log_loss": None, "brier": None, "reliability": []}
    labels = np.asarray([row["scenario"] for row in labeled], dtype=int)
    probabilities = np.asarray([row["_p_cal"] for row in labeled], dtype=float)
    targets = np.eye(5)[labels]
    reliability = []
    for label in range(5):
        for index in range(10):
            low, high = index / 10, (index + 1) / 10
            mask = (probabilities[:, label] >= low) & (
                (probabilities[:, label] < high) | ((index == 9) & (probabilities[:, label] <= high))
            )
            if mask.any():
                reliability.append({
                    "class": label, "bin_low": low, "bin_high": high,
                    "n": int(mask.sum()), "predicted": float(probabilities[mask, label].mean()),
                    "observed": float((labels[mask] == label).mean()),
                })
    return {
        "n": len(labeled), "log_loss": log_loss_fixed(labels, probabilities),
        "brier": float(np.square(probabilities - targets).sum(axis=1).mean()),
        "reliability": reliability,
    }


def ev_accuracy(rows: list[dict[str, Any]], *, observed_only: bool = False) -> dict[str, Any]:
    labeled = [
        row for row in rows if row["_model_label_eligible"]
        and (not observed_only or not row["payoff_is_lower_bound"])
    ]
    output = {}
    for cost in ("base", "adverse"):
        if not labeled:
            output[cost] = {"n": 0, "bias": None, "mae": None}
        else:
            errors = np.asarray([row[f"_ev_{cost}"] - float(row[f"net_{cost}"]) for row in labeled])
            output[cost] = {"n": len(labeled), "bias": float(errors.mean()), "mae": float(np.abs(errors).mean())}
    return output


def select_candidate(candidates: list[dict[str, Any]], policy: str) -> tuple[dict[str, Any] | None, str]:
    if policy == "ALWAYS_ABSTAIN":
        return None, "ABSTAIN"
    if policy in {"ALWAYS_CALL_H2", "ALWAYS_PUT_H2"}:
        right = "CALL" if policy == "ALWAYS_CALL_H2" else "PUT"
        matches = [row for row in candidates if row["right"] == right]
        require(len(matches) <= 1, "multiple fixed-side candidates")
        return (matches[0], "FIXED_CONTROL") if matches else (None, "NO_SERIES")
    require(policy == "EV_TOP1_H2", "unknown policy")
    if not candidates:
        return None, "NO_SERIES"
    best_value = max(row["_ev_adverse"] for row in candidates)
    best = [row for row in candidates if row["_ev_adverse"] == best_value]
    if best_value <= 0:
        return None, "EV_NOT_POSITIVE"
    if len(best) != 1:
        return None, "EV_TIE_WAIT"
    return best[0], "EV_TOP1"


def replay(rows: list[dict[str, Any]], coverage: dict[str, Any], policy: str, book_split: str) -> list[dict[str, Any]]:
    bounds = {"TRAIN": ("20230103", "20241231"), "CAL": ("20250101", "20251231"), "EVAL": ("20260101", "20260630")}
    require(book_split in bounds and all(row["_split"] == book_split for row in rows), "replay book scope")
    start_date, last_entry_date = bounds[book_split]
    by_date_ticker: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date_ticker[(row["entry_date"], row["ticker"])].append(row)
    last_exit_date = max((row["exit_date"] for row in rows), default=last_entry_date)
    dates = sorted({
        item["entry_date"] for item in coverage["rows"]
        if start_date <= item["entry_date"] <= max(last_entry_date, last_exit_date)
    })
    open_positions: dict[str, dict[str, Any]] = {}
    cash = {"base": STARTING_CASH, "adverse": STARTING_CASH}
    reserved = {"base": 0.0, "adverse": 0.0}
    ledger: list[dict[str, Any]] = []
    for date in dates:
        # The contract requires exits before entries at the same 10:35 clock.
        for ticker in TICKERS:
            if ticker in open_positions and open_positions[ticker]["exit_date"] == date:
                row = open_positions.pop(ticker)
                for cost in ("base", "adverse"):
                    slip = 0.01 if cost == "base" else 0.02
                    principal = (float(row["entry_ask"]) + slip) * 100
                    exit_bid = 0.0 if row["exit_bid"] is None else float(row["exit_bid"])
                    cash[cost] += max(exit_bid - slip, 0.0) * 100 - 1.30
                    reserved[cost] -= principal
                ledger.append({
                    "event": "EXIT", "date": date, "ticker": ticker,
                    "candidate_id": row["candidate_id"], "status": row["status"],
                    "split": row["_split"], "right": row["right"],
                    "net_base": row["net_base"], "net_adverse": row["net_adverse"],
                    "cash_base": cash["base"], "cash_adverse": cash["adverse"],
                    "reserved_base": reserved["base"], "reserved_adverse": reserved["adverse"],
                    "equity_base": cash["base"] + reserved["base"],
                    "equity_adverse": cash["adverse"] + reserved["adverse"],
                    "realized_delta_base": float(row["net_base"]) + 1.30,
                    "realized_delta_adverse": float(row["net_adverse"]) + 1.30,
                    "principal_base": (float(row["entry_ask"]) + 0.01) * 100,
                    "principal_adverse": (float(row["entry_ask"]) + 0.02) * 100,
                })
        for ticker in TICKERS:  # fixed capital priority SPY, QQQ, SPXW
            if date > last_entry_date:
                continue
            candidates = by_date_ticker.get((date, ticker), [])
            if ticker in open_positions:
                ledger.append({"event": "WAIT", "date": date, "ticker": ticker, "split": book_split, "reason": "OPEN_POSITION"})
                continue
            selected, reason = select_candidate(candidates, policy)
            if selected is None:
                ledger.append({"event": "WAIT", "date": date, "ticker": ticker, "split": book_split, "reason": reason})
                continue
            if selected["status"] == "NO_FILL":
                ledger.append({"event": "NO_FILL", "date": date, "ticker": ticker, "candidate_id": selected["candidate_id"], "split": selected["_split"], "reason": "ENTRY_QUOTE"})
                continue
            if len(open_positions) >= 3:
                ledger.append({"event": "CAPITAL_BLOCKED", "date": date, "ticker": ticker, "candidate_id": selected["candidate_id"], "split": selected["_split"], "reason": "POSITION_LIMIT"})
                continue
            if any(cash[cost] < float(selected[f"entry_debit_{cost}"]) for cost in ("base", "adverse")):
                ledger.append({"event": "CAPITAL_BLOCKED", "date": date, "ticker": ticker, "candidate_id": selected["candidate_id"], "split": selected["_split"], "reason": "CAPITAL"})
                continue
            for cost in ("base", "adverse"):
                debit = float(selected[f"entry_debit_{cost}"])
                cash[cost] -= debit
                slip = 0.01 if cost == "base" else 0.02
                reserved[cost] += (float(selected["entry_ask"]) + slip) * 100
            open_positions[ticker] = selected
            ledger.append({
                "event": "ENTRY", "date": date, "ticker": ticker,
                "candidate_id": selected["candidate_id"], "right": selected["right"],
                "split": selected["_split"],
                "exit_date": selected["exit_date"], "selection_reason": reason,
                "ev_base": selected.get("_ev_base"), "ev_adverse": selected.get("_ev_adverse"),
                "cash_base": cash["base"], "cash_adverse": cash["adverse"],
                "reserved_base": reserved["base"], "reserved_adverse": reserved["adverse"],
                "equity_base": cash["base"] + reserved["base"],
                "equity_adverse": cash["adverse"] + reserved["adverse"],
                "realized_delta_base": -1.30, "realized_delta_adverse": -1.30,
                "principal_base": (float(selected["entry_ask"]) + 0.01) * 100,
                "principal_adverse": (float(selected["entry_ask"]) + 0.02) * 100,
            })
    require(not open_positions, "positions remain open after coverage calendar")
    require(all(abs(value) <= 1e-7 for value in reserved.values()), "reserved capital not released")
    for cost in ("base", "adverse"):
        total_net = sum(float(row[f"net_{cost}"]) for row in ledger if row["event"] == "EXIT")
        require(abs(cash[cost] - (STARTING_CASH + total_net)) <= 1e-6, f"cash reconciliation {cost}")
    return ledger


def economic_metrics(ledger: list[dict[str, Any]], split: str | None = None, ticker: str | None = None) -> dict[str, Any]:
    exits = [
        row for row in ledger if row["event"] == "EXIT"
        and (split is None or row.get("split") == split)
        and (ticker is None or row["ticker"] == ticker)
    ]
    no_fills = [row for row in ledger if row["event"] == "NO_FILL" and (split is None or row.get("split") == split) and (ticker is None or row["ticker"] == ticker)]
    result: dict[str, Any] = {
        "trades": len(exits), "no_fill": len(no_fills),
        "capital_blocked": sum(
            row["event"] == "CAPITAL_BLOCKED" and (split is None or row.get("split") == split)
            and (ticker is None or row["ticker"] == ticker) for row in ledger
        ),
        "wait": sum(
            row["event"] == "WAIT" and (split is None or row.get("split") == split)
            and (ticker is None or row["ticker"] == ticker) for row in ledger
        ),
        "missing_exit": sum(row.get("status") in {"MISSING_EXIT_QUOTE", "MISSING_EXIT_SOURCE"} for row in exits),
        "overnight_exposure_sessions": len(exits) * 2,
    }
    for cost in ("base", "adverse"):
        values = np.asarray([row[f"net_{cost}"] for row in exits], dtype=float)
        gains = float(values[values > 0].sum()) if len(values) else 0.0
        losses = float(-values[values < 0].sum()) if len(values) else 0.0
        relevant_events = [
            row for row in ledger if row["event"] in {"ENTRY", "EXIT"}
            and (split is None or row.get("split") == split)
            and (ticker is None or row["ticker"] == ticker)
        ]
        equity = np.concatenate((
            [STARTING_CASH],
            STARTING_CASH + np.cumsum([float(row[f"realized_delta_{cost}"]) for row in relevant_events]),
        ))
        drawdown = np.maximum.accumulate(equity) - equity
        result[cost] = {
            "net_usd": float(values.sum()),
            "profit_factor": gains / losses if losses else (None if gains == 0 else "Infinity"),
            "realized_max_drawdown_usd": float(drawdown.max()),
        }
        months: dict[str, float] = defaultdict(float)
        for row in exits:
            months[row["date"][:6]] += float(row[f"net_{cost}"])
        result[cost]["positive_months"] = sum(value > 0 for value in months.values())
        result[cost]["months_observed"] = len(months)
        running_reserved = 0.0
        max_reserved = 0.0
        for row in relevant_events:
            principal = float(row[f"principal_{cost}"])
            running_reserved += principal if row["event"] == "ENTRY" else -principal
            require(running_reserved >= -1e-7, "reserved capital below zero")
            max_reserved = max(max_reserved, running_reserved)
        result[f"max_reserved_{cost}"] = max_reserved
    return result


def economics_report(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "pooled": economic_metrics(ledger),
        "tickers": {ticker: economic_metrics(ledger, ticker=ticker) for ticker in TICKERS},
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def run(candidates_path: Path, coverage_path: Path, manifest_path: Path, manifest_sha256: str, output: Path) -> dict[str, Any]:
    candidates_path = assert_plain_path(candidates_path, "candidates")
    coverage_path = assert_plain_path(coverage_path, "coverage")
    manifest_path = assert_plain_path(manifest_path, "manifest")
    output = assert_plain_path(output, "output")
    require(not output.exists(), "output already exists")
    rows, coverage, input_manifest = load_inputs(candidates_path, coverage_path, manifest_path, manifest_sha256)
    splits = split_rows(rows)
    train = [row for row in splits["TRAIN"] if row["_model_label_eligible"]]
    cal = [row for row in splits["CAL"] if row["_model_label_eligible"]]
    labels_train = np.asarray([row["scenario"] for row in train], dtype=int)
    require(len(set(labels_train.tolist())) >= 2, "TRAIN has fewer than two classes")
    require(len(cal) > 0, "CAL has no eligible labels")
    transformer = StableTrainTransformer().fit(np.asarray([row["_x"] for row in train], dtype=float))
    model = LogisticRegression(C=1.0, max_iter=2000, random_state=0, solver="lbfgs")
    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        model.fit(transformer.transform(np.asarray([row["_x"] for row in train], dtype=float)), labels_train)
    fit_warnings = [f"{item.category.__name__}: {item.message}" for item in captured_warnings]
    for item in captured_warnings:
        warnings.warn(str(item.message), item.category, stacklevel=2)
    prior = np.bincount(labels_train, minlength=5).astype(float) / len(labels_train)
    cal_matrix = transformer.transform(np.asarray([row["_x"] for row in cal], dtype=float))
    alpha, grid = choose_calibration(
        full_probabilities(model, cal_matrix), np.asarray([row["scenario"] for row in cal], dtype=int), prior
    )
    means = conditional_means(splits["TRAIN"])
    score_rows(rows, transformer, model, alpha, prior, means)
    policies = ("EV_TOP1_H2", "ALWAYS_CALL_H2", "ALWAYS_PUT_H2", "ALWAYS_ABSTAIN")
    ledgers = {
        policy: {name: replay(values, coverage, policy, name) for name, values in splits.items()}
        for policy in policies
    }
    selected_ids = {
        row["candidate_id"] for ledger in ledgers["EV_TOP1_H2"].values() for row in ledger
        if row["event"] in {"ENTRY", "NO_FILL", "CAPITAL_BLOCKED"} and "candidate_id" in row
    }
    selected_rows = [row for row in rows if row["candidate_id"] in selected_ids]
    coverage_reasons: dict[str, int] = defaultdict(int)
    for item in coverage["rows"]:
        coverage_reasons[str(item.get("reason", item.get("status", "<UNKNOWN>")))] += 1
    label_support = {}
    for name, values in splits.items():
        label_support[name] = {
            "conservative_all": {
                str(label): sum(row["_model_label_eligible"] and row["scenario"] == label for row in values)
                for label in range(5)
            },
            "observed_only": {
                str(label): sum(
                    row["_model_label_eligible"] and not row["payoff_is_lower_bound"] and row["scenario"] == label
                    for row in values
                ) for label in range(5)
            },
            "lower_bound": sum(row["_model_label_eligible"] and row["payoff_is_lower_bound"] for row in values),
        }
    summary = {
        "schema": "weekly_h2_ev_evaluation_v1",
        "status": "COMPLETE_SEEN_DEVELOPMENT_WEEKLY_H2_EVALUATION",
        "development_seen": True, "promotion_approved": False, "technical_ready": False,
        "split_counts": {name: len(values) for name, values in splits.items()},
        "eligible_label_counts": {name: sum(row["_model_label_eligible"] for row in values) for name, values in splits.items()},
        "probability_metrics_conservative": {name: probability_metrics(values) for name, values in splits.items()},
        "probability_metrics_observed_only": {name: probability_metrics(values, observed_only=True) for name, values in splits.items()},
        "ev_metrics_conservative": {name: ev_accuracy(values) for name, values in splits.items()},
        "ev_metrics_observed_only": {name: ev_accuracy(values, observed_only=True) for name, values in splits.items()},
        "label_support": label_support,
        "selected_top1_probability_metrics": {
            name: probability_metrics([row for row in selected_rows if row["_split"] == name]) for name in splits
        },
        "selected_top1_probability_metrics_observed_only": {
            name: probability_metrics([row for row in selected_rows if row["_split"] == name], observed_only=True) for name in splits
        },
        "selected_top1_ev_metrics": {
            name: ev_accuracy([row for row in selected_rows if row["_split"] == name]) for name in splits
        },
        "selected_top1_ev_metrics_observed_only": {
            name: ev_accuracy([row for row in selected_rows if row["_split"] == name], observed_only=True) for name in splits
        },
        "economics": {
            policy: {name: economics_report(ledger) for name, ledger in books.items()}
            for policy, books in ledgers.items()
        },
        "coverage_reason_counts": dict(sorted(coverage_reasons.items())),
        "evaluation_primary": "EVAL_20260101_20260630", "train_cal_descriptive_only": True,
    }
    model_json = {
        "type": "LogisticRegression", "sklearn_version": importlib.metadata.version("scikit-learn"),
        "C": 1.0, "max_iter": 2000, "random_state": 0, "solver": "lbfgs",
        "classes_present": model.classes_.astype(int).tolist(), "classes_full": list(range(5)),
        "coefficient": model.coef_.tolist(), "intercept": model.intercept_.tolist(),
        "train_prior": prior.tolist(), "fit_scope": "TRAIN_ONLY", "fit_warnings": fit_warnings,
    }
    scores = [{
        "candidate_id": row["candidate_id"], "split": row["_split"],
        "p_model": row["_p_model"], "p_cal": row["_p_cal"],
        "ev_base": row["_ev_base"], "ev_adverse": row["_ev_adverse"],
        "label_eligible": row["_model_label_eligible"], "scenario": row["scenario"], "status": row["status"],
        "payoff_is_lower_bound": row["payoff_is_lower_bound"],
    } for row in rows]

    for name, path in (("candidates.jsonl", candidates_path), ("coverage.json", coverage_path)):
        pin = _manifest_pin(input_manifest, name)
        require(path.stat().st_size == pin["bytes"] and sha256_file(path) == pin["sha256"], f"input changed before publication: {name}")
    require(sha256_file(manifest_path) == manifest_sha256, "manifest changed before publication")
    inventory_path = manifest_path.parent / "inventory.json"
    require(sha256_file(inventory_path) == _manifest_pin(input_manifest, "inventory.json")["sha256"], "inventory changed before publication")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "transform.json", transformer.as_dict())
    write_json(output / "model.json", model_json)
    write_json(output / "calibration_grid.json", {"formula": "(1-alpha)*p_model+alpha*p_train_prior", "selected_alpha": alpha, "scores": grid})
    write_json(output / "conditional_means.json", means)
    write_jsonl(output / "candidate_scores.jsonl", scores)
    for policy, books in ledgers.items():
        for name, ledger in books.items():
            write_jsonl(output / f"ledger_{policy.lower()}_{name.lower()}.jsonl", ledger)
    write_json(output / "summary.json", summary)
    outputs = {}
    for path in sorted(output.iterdir()):
        outputs[path.name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    write_json(output / "manifest.json", {
        "schema": "weekly_h2_ev_manifest_v1",
        "inputs": {
            "candidates.jsonl": {"bytes": candidates_path.stat().st_size, "sha256": sha256_file(candidates_path)},
            "coverage.json": {"bytes": coverage_path.stat().st_size, "sha256": sha256_file(coverage_path)},
            "inventory.json": {
                "bytes": (manifest_path.parent / "inventory.json").stat().st_size,
                "sha256": sha256_file(manifest_path.parent / "inventory.json"),
            },
            "manifest.json": {"bytes": manifest_path.stat().st_size, "sha256": sha256_file(manifest_path)},
            "external_manifest_sha256": manifest_sha256,
            "input_manifest_schema": input_manifest["schema"],
        },
        "implementation_pins": {"evaluate_weekly_h2_ev.py": sha256_file(Path(__file__)), "ECONOMIC_H2_CONTRACT.md": CONTRACT_SHA256},
        "calendar_sha256": CALENDAR_SHA256,
        "source_pins_retained_in_input_candidates": True,
        "outputs": outputs,
        "flags": {"development_seen": True, "production_modified": False, "broker_or_api_used": False, "promotion_approved": False},
    })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the frozen weekly H2 candidate dataset.")
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--coverage", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.candidates, args.coverage, args.manifest, args.manifest_sha256, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
