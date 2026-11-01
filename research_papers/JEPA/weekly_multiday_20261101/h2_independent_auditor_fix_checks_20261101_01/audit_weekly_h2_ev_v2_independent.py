"""Independent, no-refit audit of the frozen weekly H2 V2 evaluation package.

This module deliberately does not import the producer/evaluator.  It consumes only
the two compact package roots and externally supplied manifest hashes.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Any


FEATURES = (
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
TICKERS = ("SPY", "QQQ", "SPXW")
RIGHTS = ("CALL", "PUT")
SPLITS = ("TRAIN", "CAL", "EVAL")
COSTS = ("base", "adverse")
POLICIES = ("EV_TOP1_H2", "ALWAYS_CALL_H2", "ALWAYS_PUT_H2", "ALWAYS_ABSTAIN")
ALPHAS = tuple(index / 10 for index in range(11))
STARTING_CASH = 100_000.0
CALENDAR_SHA256 = "7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4"
CONTRACT_SHA256 = "245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5"
AMENDMENT_SHA256 = "9210c6e50094e5745f80c5e03f577f6bd673263f84d3c3ef764ad76b22ca56eb"
EVALUATOR_SHA256 = "8a9e75855d542a12662e5c812583f2ef86042f5c3ae1bbbad73c16042e063476"
BUILDER_SHA256 = "ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945"
SOURCE_PILOT_SHA256 = "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878"


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


def plain_root(path: Path, name: str) -> Path:
    absolute = Path(os.path.abspath(path))
    require(absolute.is_dir(), f"{name} is not a directory")
    current = absolute
    while True:
        info = current.lstat()
        is_reparse = bool(getattr(info, "st_file_attributes", 0) & 0x400)
        require(
            not stat.S_ISLNK(info.st_mode) and not is_reparse,
            f"{name} contains link/reparse ancestry",
        )
        if current.parent == current:
            break
        current = current.parent
    require(
        not str(absolute).lower().startswith("d:\\thetadata\\"),
        f"{name} cannot be D:/ThetaData",
    )
    return absolute


def plain_output(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    require(not absolute.exists(), "audit output already exists")
    current = absolute.parent
    while True:
        info = current.lstat()
        is_reparse = bool(getattr(info, "st_file_attributes", 0) & 0x400)
        require(
            not stat.S_ISLNK(info.st_mode) and not is_reparse,
            "output ancestor is link/reparse",
        )
        if current.parent == current:
            break
        current = current.parent
    require(
        not str(absolute).lower().startswith("d:\\thetadata\\"),
        "output cannot be D:/ThetaData",
    )
    return absolute


def require_separate_roots(dataset: Path, evaluation: Path, output: Path) -> None:
    roots = (dataset, evaluation, output)
    require(len(set(roots)) == 3, "dataset/evaluation/output roots must differ")
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            require(
                not left.is_relative_to(right) and not right.is_relative_to(left),
                "dataset/evaluation/output roots cannot be nested",
            )


def file_closure(root: Path, expected: set[str], name: str) -> None:
    children = list(root.iterdir())
    actual = {path.name for path in children if path.is_file()}
    require(actual == expected, f"{name} file closure")
    require(all(not path.is_dir() for path in children), f"{name} must be flat")
    for path in children:
        info = path.lstat()
        is_reparse = bool(getattr(info, "st_file_attributes", 0) & 0x400)
        require(
            not stat.S_ISLNK(info.st_mode) and not is_reparse,
            f"{name} member is link/reparse",
        )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL line {path.name}:{line_number}")
            value = json.loads(line)
            require(
                isinstance(value, dict),
                f"non-object JSONL line {path.name}:{line_number}",
            )
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def finite(value: Any, name: str) -> float:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{name} not numeric",
    )
    result = float(value)
    require(math.isfinite(result), f"{name} not finite")
    return result


def close(actual: Any, expected: float, name: str, tolerance: float = 1e-7) -> None:
    require(abs(finite(actual, name) - expected) <= tolerance, f"{name} mismatch")


def compare(actual: Any, expected: Any, name: str, tolerance: float = 1e-7) -> None:
    if (
        isinstance(actual, (int, float))
        and not isinstance(actual, bool)
        and isinstance(expected, (int, float))
        and not isinstance(expected, bool)
    ):
        close(actual, float(expected), name, tolerance)
    elif isinstance(expected, dict):
        require(
            isinstance(actual, dict) and set(actual) == set(expected), f"{name} keys"
        )
        for key in expected:
            compare(actual[key], expected[key], f"{name}.{key}", tolerance)
    elif isinstance(expected, list):
        require(
            isinstance(actual, list) and len(actual) == len(expected), f"{name} length"
        )
        for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
            compare(left, right, f"{name}[{index}]", tolerance)
    else:
        require(type(actual) is type(expected) and actual == expected, f"{name} value")


def split_for(day: str) -> str:
    if "20230103" <= day <= "20241231":
        return "TRAIN"
    if "20250101" <= day <= "20251231":
        return "CAL"
    if "20260101" <= day <= "20260630":
        return "EVAL"
    raise AuditError("candidate outside fixed split")


def eligible(row: dict[str, Any]) -> bool:
    available = row.get("label_available_at")
    if available is None:
        return False
    stamp = datetime.fromisoformat(available)
    require(stamp.tzinfo is not None, "label_available_at offset")
    split = split_for(row["entry_date"])
    cutoff = {
        "TRAIN": "2025-01-01T00:00:00-05:00",
        "CAL": "2026-01-01T00:00:00-05:00",
        "EVAL": None,
    }[split]
    return cutoff is None or stamp < datetime.fromisoformat(cutoff)


def feature_vector(row: dict[str, Any]) -> list[float | None]:
    features = row.get("features")
    require(
        isinstance(features, dict) and tuple(features) == FEATURES,
        "candidate feature order",
    )
    output = []
    for name in FEATURES:
        value = features[name]
        if value is None:
            require(
                name in {"implied_vol", "gamma", "theta", "vega", "rho"},
                f"required feature null: {name}",
            )
            output.append(None)
        else:
            output.append(finite(value, f"feature {name}"))
    return output


def validate_candidate_economics(row: dict[str, Any]) -> None:
    ticker, right = row.get("ticker"), row.get("right")
    require(ticker in TICKERS and right in RIGHTS, "candidate ticker/right")
    require(
        row.get("candidate_id")
        == f"{ticker}:{row.get('entry_date')}:{row.get('expiration')}:{right}",
        "candidate identity",
    )
    require(row["entry_date"] < row["exit_date"] < row["expiration"], "candidate dates")
    status = row.get("status")
    require(
        status
        in {"NO_FILL", "OBSERVED_EXIT", "MISSING_EXIT_QUOTE", "MISSING_EXIT_SOURCE"},
        "candidate status",
    )
    if status == "NO_FILL":
        require(
            row.get("scenario") == 0
            and row.get("entry_ask") is None
            and row.get("exit_bid") is None
            and row.get("payoff_is_lower_bound") is False,
            "NO_FILL semantics",
        )
        for field in (
            "net_base",
            "net_adverse",
            "entry_debit_base",
            "entry_debit_adverse",
        ):
            close(row[field], 0.0, field)
        return
    ask = finite(row.get("entry_ask"), "entry ask")
    require(0 < ask <= 49.95, "entry ask bound")
    close(row["entry_debit_base"], (ask + 0.01) * 100 + 1.30, "entry debit base")
    close(row["entry_debit_adverse"], (ask + 0.02) * 100 + 1.30, "entry debit adverse")
    if status == "OBSERVED_EXIT":
        bid = finite(row.get("exit_bid"), "exit bid")
        require(bid >= 0 and row.get("payoff_is_lower_bound") is False, "observed exit")
        raw_return = (bid - ask) / ask
        scenario = (
            1
            if raw_return < -0.25
            else 2
            if raw_return < 0
            else 3
            if raw_return < 0.25
            else 4
        )
        require(row.get("scenario") == scenario, "observed scenario")
    else:
        require(
            row.get("exit_bid") is None
            and row.get("scenario") == 1
            and row.get("payoff_is_lower_bound") is True,
            "missing-exit lower bound",
        )
        bid = 0.0
    for cost, slip in (("base", 0.01), ("adverse", 0.02)):
        expected = (max(bid - slip, 0.0) - ask - slip) * 100 - 2.60
        close(row[f"net_{cost}"], expected, f"net {cost}")


def transform_one(values: list[float | None], transform: dict[str, Any]) -> list[float]:
    require(transform.get("feature_order") == list(FEATURES), "transform feature order")
    indices = transform["missing_indicator_source_indices"]
    require(
        transform["missing_indicator_order"]
        == [f"{FEATURES[index]}__missing" for index in indices],
        "indicator order",
    )
    medians = transform["medians"]
    require(len(medians) == len(FEATURES), "median dimension")
    imputed = [
        finite(medians[i], f"median {i}") if value is None else value
        for i, value in enumerate(values)
    ]
    expanded = imputed + [float(values[index] is None) for index in indices]
    means, scales = transform["scaler_mean"], transform["scaler_scale"]
    require(len(expanded) == len(means) == len(scales), "scaler dimension")
    return [
        (value - finite(means[i], f"scaler mean {i}"))
        / finite(scales[i], f"scaler scale {i}")
        for i, value in enumerate(expanded)
    ]


def median(values: list[float]) -> float:
    require(bool(values), "median requires values")
    ordered = sorted(values)
    middle = len(ordered) // 2
    return (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2
    )


def reconstruct_transform(train_rows: list[dict[str, Any]]) -> dict[str, Any]:
    require(bool(train_rows), "empty TRAIN transform scope")
    matrix = [row["_x"] for row in train_rows]
    medians = []
    indicator_indices = []
    for index in range(len(FEATURES)):
        observed = [row[index] for row in matrix if row[index] is not None]
        medians.append(median(observed) if observed else 0.0)
        if len(observed) != len(matrix):
            indicator_indices.append(index)
    expanded = []
    for row in matrix:
        expanded.append(
            [
                medians[index] if value is None else value
                for index, value in enumerate(row)
            ]
            + [float(row[index] is None) for index in indicator_indices]
        )
    dimension = len(expanded[0])
    means = [
        math.fsum(row[index] for row in expanded) / len(expanded)
        for index in range(dimension)
    ]
    scales = []
    for index, mean in enumerate(means):
        variance = math.fsum((row[index] - mean) ** 2 for row in expanded) / len(
            expanded
        )
        scale = math.sqrt(variance)
        scales.append(1.0 if scale == 0 else scale)
    return {
        "feature_order": list(FEATURES),
        "missing_indicator_order": [
            f"{FEATURES[index]}__missing" for index in indicator_indices
        ],
        "missing_indicator_source_indices": indicator_indices,
        "medians": medians,
        "scaler_mean": means,
        "scaler_scale": scales,
        "fit_scope": "TRAIN_ONLY",
        "imputer": {
            "strategy": "median",
            "add_indicator": True,
            "keep_empty_features": True,
        },
    }


def probabilities(values: list[float], model: dict[str, Any]) -> list[float]:
    classes = model["classes_present"]
    coefficients, intercepts = model["coefficient"], model["intercept"]
    require(
        model.get("classes_full") == list(range(5)) and len(classes) >= 2,
        "model classes",
    )
    logits = [
        math.fsum(coef[i] * values[i] for i in range(len(values))) + intercept
        for coef, intercept in zip(coefficients, intercepts, strict=True)
    ]
    if len(classes) == 2:
        require(len(logits) == 1, "binary logistic shape")
        positive = (
            1.0 / (1.0 + math.exp(-logits[0]))
            if logits[0] >= 0
            else math.exp(logits[0]) / (1.0 + math.exp(logits[0]))
        )
        partial = (1.0 - positive, positive)
    else:
        require(len(logits) == len(classes), "multiclass logistic shape")
        maximum = max(logits)
        weights = [math.exp(value - maximum) for value in logits]
        denominator = math.fsum(weights)
        partial = [value / denominator for value in weights]
    output = [0.0] * 5
    for label, value in zip(classes, partial, strict=True):
        output[int(label)] = value
    close(math.fsum(output), 1.0, "model probability sum")
    return output


def log_loss(rows: list[dict[str, Any]], probability_key: str) -> float:
    require(rows, "empty log-loss rows")
    return -math.fsum(
        math.log(max(1e-12, min(1.0, row[probability_key][int(row["scenario"])])))
        for row in rows
    ) / len(rows)


def reconstruct_means(rows: list[dict[str, Any]]) -> dict[str, Any]:
    train = [row for row in rows if row["_split"] == "TRAIN" and row["_eligible"]]
    output: dict[str, Any] = {"shrinkage": 20, "global": {}, "cells": {}}
    for cost in COSTS:
        by_class = {label: [] for label in range(5)}
        cells = {
            (label, ticker, right): []
            for label in range(5)
            for ticker in TICKERS
            for right in RIGHTS
        }
        for row in train:
            label = int(row["scenario"])
            y = finite(row[f"net_{cost}"], "net") / (
                finite(row["decision_ask"], "decision ask") * 100
            )
            by_class[label].append(y)
            cells[(label, row["ticker"], row["right"])].append(y)
        global_means = {
            str(label): (
                math.fsum(by_class[label]) / len(by_class[label])
                if by_class[label]
                else 0.0
            )
            for label in range(5)
        }
        output["global"][cost] = global_means
        output["cells"][cost] = {}
        for ticker in TICKERS:
            for right in RIGHTS:
                key = f"{ticker}:{right}"
                output["cells"][cost][key] = {}
                for label in range(5):
                    values = cells[(label, ticker, right)]
                    mean = (math.fsum(values) + 20 * global_means[str(label)]) / (
                        len(values) + 20
                    )
                    output["cells"][cost][key][str(label)] = {
                        "n": len(values),
                        "mean_y": mean,
                    }
    return output


def select(
    candidates: list[dict[str, Any]], policy: str
) -> tuple[dict[str, Any] | None, str]:
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
    maximum = max(row["_ev_adverse"] for row in candidates)
    best = [row for row in candidates if row["_ev_adverse"] == maximum]
    if maximum <= 0:
        return None, "EV_NOT_POSITIVE"
    if len(best) != 1:
        return None, "EV_TIE_WAIT"
    return best[0], "EV_TOP1"


def replay(
    rows: list[dict[str, Any]],
    coverage: dict[str, Any],
    policy: str,
    split: str,
    cost: str,
) -> list[dict[str, Any]]:
    bounds = {
        "TRAIN": ("20230103", "20241231"),
        "CAL": ("20250101", "20251231"),
        "EVAL": ("20260101", "20260630"),
    }
    start, last_entry = bounds[split]
    slip = 0.01 if cost == "base" else 0.02
    by_identity: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_identity[(row["entry_date"], row["ticker"])].append(row)
    coverage_index = {
        (item["ticker"], item["entry_date"]): item for item in coverage["rows"]
    }
    last_exit = max((row["exit_date"] for row in rows), default=last_entry)
    dates = sorted(
        {
            item["entry_date"]
            for item in coverage["rows"]
            if start <= item["entry_date"] <= max(last_entry, last_exit)
        }
    )
    opened: dict[str, dict[str, Any]] = {}
    cash = STARTING_CASH
    reserved = 0.0
    ledger = []
    for day in dates:
        for ticker in TICKERS:
            if ticker in opened and opened[ticker]["exit_date"] == day:
                row = opened.pop(ticker)
                principal = (row["entry_ask"] + slip) * 100
                bid = 0.0 if row["exit_bid"] is None else row["exit_bid"]
                cash += max(bid - slip, 0.0) * 100 - 1.30
                reserved -= principal
                ledger.append(
                    {
                        "event": "EXIT",
                        "date": day,
                        "ticker": ticker,
                        "candidate_id": row["candidate_id"],
                        "status": row["status"],
                        "split": split,
                        "right": row["right"],
                        "cost": cost,
                        "entry_date": row["entry_date"],
                        "duration_calendar_days": (
                            datetime.strptime(day, "%Y%m%d")
                            - datetime.strptime(row["entry_date"], "%Y%m%d")
                        ).days,
                        "net_usd": row[f"net_{cost}"],
                        "cash": cash,
                        "reserved": reserved,
                        "equity": cash + reserved,
                        "realized_delta": row[f"net_{cost}"] + 1.30,
                        "principal": principal,
                    }
                )
        for ticker in TICKERS:
            if day > last_entry:
                continue
            candidates = by_identity.get((day, ticker), [])
            if ticker in opened:
                ledger.append(
                    {
                        "event": "WAIT",
                        "date": day,
                        "ticker": ticker,
                        "split": split,
                        "cost": cost,
                        "reason": "OPEN_POSITION",
                    }
                )
                continue
            cover = coverage_index[(ticker, day)]
            if not candidates:
                ledger.append(
                    {
                        "event": "NO_OPPORTUNITY",
                        "date": day,
                        "ticker": ticker,
                        "split": split,
                        "cost": cost,
                        "reason": cover.get("reason") or cover["status"],
                    }
                )
                continue
            if policy in {"ALWAYS_CALL_H2", "ALWAYS_PUT_H2"}:
                required = "CALL" if policy == "ALWAYS_CALL_H2" else "PUT"
                if not any(row["right"] == required for row in candidates):
                    ledger.append(
                        {
                            "event": "NO_OPPORTUNITY",
                            "date": day,
                            "ticker": ticker,
                            "split": split,
                            "cost": cost,
                            "reason": f"{required}_SIDE_UNAVAILABLE",
                        }
                    )
                    continue
            chosen, reason = select(candidates, policy)
            if chosen is None:
                ledger.append(
                    {
                        "event": "WAIT",
                        "date": day,
                        "ticker": ticker,
                        "split": split,
                        "cost": cost,
                        "reason": reason,
                    }
                )
                continue
            if chosen["status"] == "NO_FILL":
                ledger.append(
                    {
                        "event": "NO_FILL",
                        "date": day,
                        "ticker": ticker,
                        "candidate_id": chosen["candidate_id"],
                        "split": split,
                        "cost": cost,
                        "reason": "ENTRY_QUOTE",
                    }
                )
                continue
            if len(opened) >= 3:
                ledger.append(
                    {
                        "event": "CAPITAL_BLOCKED",
                        "date": day,
                        "ticker": ticker,
                        "candidate_id": chosen["candidate_id"],
                        "split": split,
                        "cost": cost,
                        "reason": "POSITION_LIMIT",
                    }
                )
                continue
            debit = chosen[f"entry_debit_{cost}"]
            if cash < debit:
                ledger.append(
                    {
                        "event": "CAPITAL_BLOCKED",
                        "date": day,
                        "ticker": ticker,
                        "candidate_id": chosen["candidate_id"],
                        "split": split,
                        "cost": cost,
                        "reason": "CAPITAL",
                    }
                )
                continue
            cash -= debit
            principal = (chosen["entry_ask"] + slip) * 100
            reserved += principal
            opened[ticker] = chosen
            ledger.append(
                {
                    "event": "ENTRY",
                    "date": day,
                    "ticker": ticker,
                    "candidate_id": chosen["candidate_id"],
                    "right": chosen["right"],
                    "split": split,
                    "cost": cost,
                    "exit_date": chosen["exit_date"],
                    "selection_reason": reason,
                    "ev_base": chosen["_ev_base"],
                    "ev_adverse": chosen["_ev_adverse"],
                    "cash": cash,
                    "reserved": reserved,
                    "equity": cash + reserved,
                    "realized_delta": -1.30,
                    "principal": principal,
                }
            )
    require(not opened and abs(reserved) <= 1e-7, "open positions/reserved at close")
    close(
        cash,
        STARTING_CASH
        + math.fsum(row["net_usd"] for row in ledger if row["event"] == "EXIT"),
        "final cash",
        1e-6,
    )
    return ledger


def metrics(ledger: list[dict[str, Any]], ticker: str | None = None) -> dict[str, Any]:
    relevant = [row for row in ledger if ticker is None or row["ticker"] == ticker]
    exits = [row for row in relevant if row["event"] == "EXIT"]
    values = [row["net_usd"] for row in exits]
    gains = math.fsum(value for value in values if value > 0)
    losses = -math.fsum(value for value in values if value < 0)
    events = [row for row in relevant if row["event"] in {"ENTRY", "EXIT"}]
    equity = STARTING_CASH
    peak = equity
    drawdown = 0.0
    running_reserved = 0.0
    max_reserved = 0.0
    for row in events:
        equity += row["realized_delta"]
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
        running_reserved += (
            row["principal"] if row["event"] == "ENTRY" else -row["principal"]
        )
        require(running_reserved >= -1e-7, "negative reconstructed reserved")
        max_reserved = max(max_reserved, running_reserved)
    months: dict[str, float] = defaultdict(float)
    for row in exits:
        months[row["date"][:6]] += row["net_usd"]
    durations = [row["duration_calendar_days"] for row in exits]
    return {
        "trades": len(exits),
        "no_fill": sum(r["event"] == "NO_FILL" for r in relevant),
        "capital_blocked": sum(r["event"] == "CAPITAL_BLOCKED" for r in relevant),
        "wait": sum(r["event"] == "WAIT" for r in relevant),
        "no_opportunity": sum(r["event"] == "NO_OPPORTUNITY" for r in relevant),
        "missing_exit": sum(
            r.get("status") in {"MISSING_EXIT_QUOTE", "MISSING_EXIT_SOURCE"}
            for r in exits
        ),
        "missing_exit_quote": sum(
            r.get("status") == "MISSING_EXIT_QUOTE" for r in exits
        ),
        "missing_exit_source": sum(
            r.get("status") == "MISSING_EXIT_SOURCE" for r in exits
        ),
        "overnight_exposure_sessions": 2 * len(exits),
        "net_usd": math.fsum(values),
        "profit_factor": gains / losses
        if losses
        else (None if gains == 0 else "Infinity"),
        "realized_max_drawdown_usd": drawdown,
        "positive_months": sum(v > 0 for v in months.values()),
        "months_observed": len(months),
        "duration_calendar_days_mean": math.fsum(durations) / len(durations)
        if durations
        else None,
        "duration_calendar_days_min": min(durations) if durations else None,
        "duration_calendar_days_max": max(durations) if durations else None,
        "max_reserved": max_reserved,
    }


def probability_metrics(
    rows: list[dict[str, Any]], *, observed_only: bool = False
) -> dict[str, Any]:
    labeled = [
        row
        for row in rows
        if row["_eligible"] and (not observed_only or not row["payoff_is_lower_bound"])
    ]
    if not labeled:
        return {"n": 0, "log_loss": None, "brier": None, "reliability": []}
    reliability = []
    for label in range(5):
        for index in range(10):
            low, high = index / 10, (index + 1) / 10
            selected = [
                row
                for row in labeled
                if row["_p_cal"][label] >= low
                and (
                    row["_p_cal"][label] < high
                    or (index == 9 and row["_p_cal"][label] <= high)
                )
            ]
            if selected:
                reliability.append(
                    {
                        "class": label,
                        "bin_low": low,
                        "bin_high": high,
                        "n": len(selected),
                        "predicted": math.fsum(row["_p_cal"][label] for row in selected)
                        / len(selected),
                        "observed": sum(row["scenario"] == label for row in selected)
                        / len(selected),
                    }
                )
    brier = math.fsum(
        math.fsum(
            (probability - float(label == row["scenario"])) ** 2
            for label, probability in enumerate(row["_p_cal"])
        )
        for row in labeled
    ) / len(labeled)
    return {
        "n": len(labeled),
        "log_loss": log_loss(labeled, "_p_cal"),
        "brier": brier,
        "reliability": reliability,
    }


def ev_metrics(
    rows: list[dict[str, Any]], *, observed_only: bool = False
) -> dict[str, Any]:
    labeled = [
        row
        for row in rows
        if row["_eligible"] and (not observed_only or not row["payoff_is_lower_bound"])
    ]
    output = {}
    for cost in COSTS:
        if not labeled:
            output[cost] = {"n": 0, "bias": None, "mae": None}
            continue
        errors = [row[f"_ev_{cost}"] - row[f"net_{cost}"] for row in labeled]
        output[cost] = {
            "n": len(labeled),
            "bias": math.fsum(errors) / len(errors),
            "mae": math.fsum(abs(value) for value in errors) / len(errors),
        }
    return output


def label_support(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    output = {}
    for split, rows in rows_by_split.items():
        eligible_rows = [row for row in rows if row["_eligible"]]
        output[split] = {
            "conservative_all": {
                str(label): sum(row["scenario"] == label for row in eligible_rows)
                for label in range(5)
            },
            "observed_only": {
                str(label): sum(
                    not row["payoff_is_lower_bound"] and row["scenario"] == label
                    for row in eligible_rows
                )
                for label in range(5)
            },
            "lower_bound": sum(row["payoff_is_lower_bound"] for row in eligible_rows),
            "lower_bound_by_scenario": {
                str(label): sum(
                    row["payoff_is_lower_bound"] and row["scenario"] == label
                    for row in eligible_rows
                )
                for label in range(5)
            },
            "lower_bound_proportion": (
                sum(row["payoff_is_lower_bound"] for row in eligible_rows)
                / len(eligible_rows)
                if eligible_rows
                else None
            ),
        }
    return output


def verify_manifest_files(root: Path, manifest: dict[str, Any], section: str) -> None:
    pins = manifest[section]
    for name, pin in pins.items():
        path = root / name
        require(path.is_file() and path.parent == root, f"missing compact file {name}")
        require(
            path.stat().st_size == pin["bytes"] and sha256_file(path) == pin["sha256"],
            f"compact hash mismatch {name}",
        )


def snapshot_files(root: Path, names: set[str]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "bytes": (root / name).stat().st_size,
            "sha256": sha256_file(root / name),
        }
        for name in sorted(names)
    }


def run(
    dataset_root: Path,
    evaluation_root: Path,
    dataset_manifest_sha256: str,
    evaluation_manifest_sha256: str,
    output: Path,
) -> dict[str, Any]:
    dataset_root = plain_root(dataset_root, "dataset root")
    evaluation_root = plain_root(evaluation_root, "evaluation root")
    output = plain_output(output)
    require_separate_roots(dataset_root, evaluation_root, output)
    dataset_manifest_path = dataset_root / "manifest.json"
    evaluation_manifest_path = evaluation_root / "manifest.json"
    dataset_names = {
        "candidates.jsonl",
        "coverage.json",
        "inventory.json",
        "manifest.json",
    }
    evaluation_names = {
        "manifest.json",
        "transform.json",
        "model.json",
        "calibration_grid.json",
        "conditional_means.json",
        "candidate_scores.jsonl",
        "summary.json",
        *{
            f"ledger_{policy.lower()}_{split.lower()}_{cost}.jsonl"
            for policy in POLICIES
            for split in SPLITS
            for cost in COSTS
        },
    }
    file_closure(dataset_root, dataset_names, "dataset")
    file_closure(evaluation_root, evaluation_names, "evaluation")
    initial_dataset_snapshot = snapshot_files(dataset_root, dataset_names)
    initial_evaluation_snapshot = snapshot_files(evaluation_root, evaluation_names)
    require(
        sha256_file(dataset_manifest_path) == dataset_manifest_sha256,
        "dataset external manifest hash",
    )
    require(
        sha256_file(evaluation_manifest_path) == evaluation_manifest_sha256,
        "evaluation external manifest hash",
    )
    dm, em = read_json(dataset_manifest_path), read_json(evaluation_manifest_path)
    require(
        dm.get("schema") == "weekly_h2_dataset_manifest_v2", "dataset manifest schema"
    )
    require(
        dm.get("status") == "COMPLETE_WEEKLY_H2_DATASET_NOT_EVALUATED",
        "dataset manifest status",
    )
    require(
        isinstance(dm.get("calendar"), dict)
        and dm["calendar"].get("sha256") == CALENDAR_SHA256,
        "dataset calendar pin",
    )
    dataset_flags = dm.get("flags")
    require(isinstance(dataset_flags, dict), "dataset flags")
    for name in (
        "fit_performed",
        "economic_evaluation_performed",
        "promotion_approved",
        "production_modified",
    ):
        require(dataset_flags.get(name) is False, f"dataset flag {name}")
    dataset_implementation = {
        "build_weekly_h2_dataset_v2.py": BUILDER_SHA256,
        "weekly_multiday_source_pilot.py": SOURCE_PILOT_SHA256,
        "ECONOMIC_H2_CONTRACT.md": CONTRACT_SHA256,
        "H2_CLOCK_FILTER_V2_AMENDMENT.md": AMENDMENT_SHA256,
    }
    require(
        dm.get("implementation_pins") == dataset_implementation,
        "dataset implementation pins",
    )
    require(
        em.get("schema") == "weekly_h2_ev_manifest_v1", "evaluation manifest schema"
    )
    require(em.get("calendar_sha256") == CALENDAR_SHA256, "evaluation calendar pin")
    require(
        em.get("source_pins_retained_in_input_candidates") is True,
        "source pin retention",
    )
    evaluation_flags = em.get("flags")
    require(
        evaluation_flags
        == {
            "development_seen": True,
            "production_modified": False,
            "broker_or_api_used": False,
            "promotion_approved": False,
        },
        "evaluation manifest flags",
    )
    pins = em.get("implementation_pins", {})
    require(
        pins
        == {
            "evaluate_weekly_h2_ev_v2.py": EVALUATOR_SHA256,
            "ECONOMIC_H2_CONTRACT.md": CONTRACT_SHA256,
            "H2_CLOCK_FILTER_V2_AMENDMENT.md": AMENDMENT_SHA256,
        },
        "evaluation implementation pins",
    )
    expected_outputs = evaluation_names - {"manifest.json"}
    require(set(em.get("outputs", {})) == expected_outputs, "evaluation output closure")
    require(
        set(dm.get("files", {}))
        == {"candidates.jsonl", "coverage.json", "inventory.json"},
        "dataset output closure",
    )
    verify_manifest_files(dataset_root, dm, "files")
    verify_manifest_files(evaluation_root, em, "outputs")
    inputs = em["inputs"]
    require(
        set(inputs)
        == {
            "candidates.jsonl",
            "coverage.json",
            "inventory.json",
            "manifest.json",
            "external_manifest_sha256",
            "input_manifest_schema",
        },
        "evaluation input closure",
    )
    require(
        inputs["manifest.json"]["sha256"]
        == dataset_manifest_sha256
        == inputs["external_manifest_sha256"],
        "cross-manifest pin",
    )
    require(
        inputs["manifest.json"]["bytes"] == dataset_manifest_path.stat().st_size,
        "dataset manifest byte pin",
    )
    require(
        inputs.get("input_manifest_schema") == "weekly_h2_dataset_manifest_v2",
        "evaluation input manifest schema",
    )
    for name in ("candidates.jsonl", "coverage.json", "inventory.json"):
        require(
            inputs[name]
            == {key: dm["files"][name][key] for key in ("bytes", "sha256")},
            f"cross-package input pin {name}",
        )
    rows = read_jsonl(dataset_root / "candidates.jsonl")
    coverage = read_json(dataset_root / "coverage.json")
    inventory = read_json(dataset_root / "inventory.json")
    require(
        inventory.get("schema") == "weekly_h2_source_inventory_v2_clock_filter",
        "inventory schema",
    )
    require(inventory.get("pins") == dataset_implementation, "inventory pins")
    require(
        dm.get("inventory_bound_sha256") == dm["files"]["inventory.json"]["sha256"],
        "inventory binding",
    )
    require(
        coverage.get("schema") == "weekly_h2_coverage_v2"
        and isinstance(coverage.get("rows"), list)
        and isinstance(coverage.get("calendar"), list)
        and isinstance(coverage.get("clock_files"), list),
        "coverage schema",
    )
    require(
        dm["files"]["candidates.jsonl"].get("rows") == len(rows)
        and dm["files"]["coverage.json"].get("rows") == len(coverage["rows"]),
        "dataset row pins",
    )
    require(
        len({row["candidate_id"] for row in rows}) == len(rows), "duplicate candidates"
    )
    for row in rows:
        validate_candidate_economics(row)
        row["_split"] = split_for(row["entry_date"])
        row["_eligible"] = eligible(row)
        row["_x"] = feature_vector(row)
    coverage_ids = [
        candidate_id
        for item in coverage["rows"]
        for candidate_id in item["candidate_ids"]
    ]
    require(
        len(coverage_ids) == len(set(coverage_ids))
        and set(coverage_ids) == {row["candidate_id"] for row in rows},
        "coverage/candidate universe",
    )
    transform, model = (
        read_json(evaluation_root / "transform.json"),
        read_json(evaluation_root / "model.json"),
    )
    require(
        transform.get("fit_scope") == model.get("fit_scope") == "TRAIN_ONLY",
        "fit scope",
    )
    require(
        model.get("type") == "LogisticRegression"
        and model.get("C") == 1.0
        and model.get("max_iter") == 2000
        and model.get("random_state") == 0
        and model.get("solver") == "lbfgs",
        "model specification",
    )
    train = [row for row in rows if row["_split"] == "TRAIN" and row["_eligible"]]
    compare(transform, reconstruct_transform(train), "TRAIN transform", 1e-10)
    labels = [int(row["scenario"]) for row in train]
    train_classes = sorted(set(labels))
    require(len(train_classes) >= 2, "TRAIN has fewer than two classes")
    require(
        model.get("classes_present") == train_classes
        and model.get("classes_full") == list(range(5)),
        "model class support",
    )
    prior = [labels.count(label) / len(labels) for label in range(5)]
    compare(model["train_prior"], prior, "train prior")
    for row in rows:
        row["_p_model"] = probabilities(transform_one(row["_x"], transform), model)
    cal = [row for row in rows if row["_split"] == "CAL" and row["_eligible"]]
    require(cal, "CAL empty")
    calibration = read_json(evaluation_root / "calibration_grid.json")
    grid = []
    for alpha in ALPHAS:
        for row in cal:
            row["_mix"] = [
                (1 - alpha) * p + alpha * q
                for p, q in zip(row["_p_model"], prior, strict=True)
            ]
        grid.append({"alpha": alpha, "log_loss": log_loss(cal, "_mix")})
    alpha = min(grid, key=lambda item: (item["log_loss"], item["alpha"]))["alpha"]
    compare(
        calibration,
        {
            "formula": "(1-alpha)*p_model+alpha*p_train_prior",
            "selected_alpha": alpha,
            "scores": grid,
        },
        "calibration grid",
    )
    means = reconstruct_means(rows)
    compare(
        read_json(evaluation_root / "conditional_means.json"),
        means,
        "conditional means",
    )
    for row in rows:
        row["_p_cal"] = [
            (1 - alpha) * p + alpha * q
            for p, q in zip(row["_p_model"], prior, strict=True)
        ]
        key = f"{row['ticker']}:{row['right']}"
        for cost in COSTS:
            conditional = [
                means["cells"][cost][key][str(label)]["mean_y"] for label in range(5)
            ]
            row[f"_ev_{cost}"] = (
                row["decision_ask"]
                * 100
                * math.fsum(
                    p * y for p, y in zip(row["_p_cal"], conditional, strict=True)
                )
            )
    score_rows = read_jsonl(evaluation_root / "candidate_scores.jsonl")
    require(len(score_rows) == len(rows), "score row count")
    for row, score in zip(rows, score_rows, strict=True):
        expected = {
            "candidate_id": row["candidate_id"],
            "split": row["_split"],
            "p_model": row["_p_model"],
            "p_cal": row["_p_cal"],
            "ev_base": row["_ev_base"],
            "ev_adverse": row["_ev_adverse"],
            "label_eligible": row["_eligible"],
            "scenario": row["scenario"],
            "status": row["status"],
            "payoff_is_lower_bound": row["payoff_is_lower_bound"],
        }
        compare(score, expected, f"score {row['candidate_id']}")
    summary = read_json(evaluation_root / "summary.json")
    expected_economics = {}
    all_ledgers: dict[str, dict[str, dict[str, list[dict[str, Any]]]]] = {}
    ledger_checks = 0
    for policy in POLICIES:
        expected_economics[policy] = {}
        all_ledgers[policy] = {}
        for split in SPLITS:
            expected_economics[policy][split] = {}
            all_ledgers[policy][split] = {}
            split_rows = [row for row in rows if row["_split"] == split]
            for cost in COSTS:
                expected_ledger = replay(split_rows, coverage, policy, split, cost)
                all_ledgers[policy][split][cost] = expected_ledger
                name = f"ledger_{policy.lower()}_{split.lower()}_{cost}.jsonl"
                actual_ledger = read_jsonl(evaluation_root / name)
                compare(actual_ledger, expected_ledger, name, 1e-6)
                ledger_checks += 1
                expected_economics[policy][split][cost] = {
                    "pooled": metrics(expected_ledger),
                    "tickers": {
                        ticker: metrics(expected_ledger, ticker) for ticker in TICKERS
                    },
                }
    compare(summary["economics"], expected_economics, "summary economics", 1e-6)
    rows_by_split = {
        split: [row for row in rows if row["_split"] == split] for split in SPLITS
    }
    expected_support = label_support(rows_by_split)
    compare(
        summary["split_counts"],
        {split: len(values) for split, values in rows_by_split.items()},
        "summary split counts",
    )
    compare(
        summary["eligible_label_counts"],
        {
            split: sum(row["_eligible"] for row in values)
            for split, values in rows_by_split.items()
        },
        "summary eligible counts",
    )
    compare(summary["label_support"], expected_support, "summary label support")
    train_support = expected_support["TRAIN"]["conservative_all"]
    expected_unseen = {
        split: [
            label
            for label in range(5)
            if train_support[str(label)] == 0
            and expected_support[split]["conservative_all"][str(label)] > 0
        ]
        for split in ("CAL", "EVAL")
    }
    compare(
        summary["unseen_classes_with_zero_train_support"],
        expected_unseen,
        "summary unseen classes",
    )
    for observed_only, suffix in ((False, "conservative"), (True, "observed_only")):
        compare(
            summary[f"probability_metrics_{suffix}"],
            {
                split: probability_metrics(values, observed_only=observed_only)
                for split, values in rows_by_split.items()
            },
            f"summary probability {suffix}",
        )
        compare(
            summary[f"ev_metrics_{suffix}"],
            {
                split: ev_metrics(values, observed_only=observed_only)
                for split, values in rows_by_split.items()
            },
            f"summary EV {suffix}",
        )
    selected_ids = {
        event["candidate_id"]
        for books in all_ledgers["EV_TOP1_H2"].values()
        for ledger in books.values()
        for event in ledger
        if event["event"] in {"ENTRY", "NO_FILL", "CAPITAL_BLOCKED"}
        and "candidate_id" in event
    }
    selected_by_split = {
        split: [
            row for row in rows_by_split[split] if row["candidate_id"] in selected_ids
        ]
        for split in SPLITS
    }
    for observed_only, probability_key, ev_key in (
        (False, "selected_top1_probability_metrics", "selected_top1_ev_metrics"),
        (
            True,
            "selected_top1_probability_metrics_observed_only",
            "selected_top1_ev_metrics_observed_only",
        ),
    ):
        compare(
            summary[probability_key],
            {
                split: probability_metrics(values, observed_only=observed_only)
                for split, values in selected_by_split.items()
            },
            probability_key,
        )
        compare(
            summary[ev_key],
            {
                split: ev_metrics(values, observed_only=observed_only)
                for split, values in selected_by_split.items()
            },
            ev_key,
        )
    expected_divergences = {}
    for policy in POLICIES:
        expected_divergences[policy] = {}
        for split in SPLITS:
            base_ids = {
                row["candidate_id"]
                for row in all_ledgers[policy][split]["base"]
                if row["event"] == "ENTRY"
            }
            adverse_ids = {
                row["candidate_id"]
                for row in all_ledgers[policy][split]["adverse"]
                if row["event"] == "ENTRY"
            }
            expected_divergences[policy][split] = {
                "base_entries": len(base_ids),
                "adverse_entries": len(adverse_ids),
                "base_only": sorted(base_ids - adverse_ids),
                "adverse_only": sorted(adverse_ids - base_ids),
            }
    compare(summary["book_divergences"], expected_divergences, "book divergences")
    coverage_counts: dict[str, int] = defaultdict(int)
    coverage_by_split = {split: {ticker: {} for ticker in TICKERS} for split in SPLITS}
    for item in coverage["rows"]:
        split = split_for(item["entry_date"])
        reason = str(item.get("reason") or item.get("status", "<UNKNOWN>"))
        coverage_counts[reason] += 1
        ticker_counts = coverage_by_split[split][item["ticker"]]
        ticker_counts[reason] = ticker_counts.get(reason, 0) + 1
    compare(
        summary["coverage_reason_counts"],
        dict(sorted(coverage_counts.items())),
        "coverage reason counts",
    )
    compare(
        summary["coverage_by_split_ticker_reason"],
        coverage_by_split,
        "coverage by split/ticker",
    )
    require(
        summary.get("evaluation_primary") == "EVAL_20260101_20260630"
        and summary.get("train_cal_descriptive_only") is True,
        "summary scope",
    )
    require(
        summary.get("development_seen") is True
        and summary.get("promotion_approved") is False
        and summary.get("technical_ready") is False,
        "summary flags",
    )
    result = {
        "status": "PASS_INDEPENDENT_WEEKLY_H2_V2_ECONOMIC_AUDIT",
        "dataset_manifest_sha256": dataset_manifest_sha256,
        "evaluation_manifest_sha256": evaluation_manifest_sha256,
        "candidate_rows": len(rows),
        "calibration_scores_reconstructed": len(grid),
        "selected_alpha": alpha,
        "scores_reconstructed": len(score_rows),
        "ledgers_reconstructed": ledger_checks,
        "economics_reconciled": True,
        "fit_performed": False,
        "dtheta_accessed": False,
        "development_seen": True,
        "technical_ready": False,
        "promotion_approved": False,
        "source_scope": "compact dataset/evaluation roots only; no source parquet replay",
    }
    file_closure(dataset_root, dataset_names, "dataset pre-publication")
    file_closure(evaluation_root, evaluation_names, "evaluation pre-publication")
    require(
        snapshot_files(dataset_root, dataset_names) == initial_dataset_snapshot,
        "dataset changed before audit publication",
    )
    require(
        snapshot_files(evaluation_root, evaluation_names)
        == initial_evaluation_snapshot,
        "evaluation changed before audit publication",
    )
    verify_manifest_files(dataset_root, dm, "files")
    verify_manifest_files(evaluation_root, em, "outputs")
    require(not output.exists(), "audit output exists")
    output.mkdir(parents=True)
    write_json(output / "audit.json", result)
    write_json(
        output / "manifest.json",
        {
            "schema": "weekly_h2_independent_audit_manifest_v1",
            "inputs": {
                "dataset_manifest_sha256": dataset_manifest_sha256,
                "evaluation_manifest_sha256": evaluation_manifest_sha256,
            },
            "files": {
                "audit.json": {
                    "bytes": (output / "audit.json").stat().st_size,
                    "sha256": sha256_file(output / "audit.json"),
                }
            },
            "implementation": {
                "audit_weekly_h2_ev_v2_independent.py": sha256_file(Path(__file__))
            },
            "flags": {
                "fit_performed": False,
                "dtheta_accessed": False,
                "promotion_approved": False,
            },
        },
    )
    file_closure(dataset_root, dataset_names, "dataset closing")
    file_closure(evaluation_root, evaluation_names, "evaluation closing")
    require(
        snapshot_files(dataset_root, dataset_names) == initial_dataset_snapshot,
        "dataset changed during audit",
    )
    require(
        snapshot_files(evaluation_root, evaluation_names)
        == initial_evaluation_snapshot,
        "evaluation changed during audit",
    )
    require(
        sha256_file(dataset_manifest_path) == dataset_manifest_sha256
        and sha256_file(evaluation_manifest_path) == evaluation_manifest_sha256,
        "external manifests changed during audit",
    )
    verify_manifest_files(dataset_root, dm, "files")
    verify_manifest_files(evaluation_root, em, "outputs")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Independently audit the compact weekly H2 V2 package without refitting."
    )
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--evaluation-root", required=True, type=Path)
    parser.add_argument("--dataset-manifest-sha256", required=True)
    parser.add_argument("--evaluation-manifest-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(
        args.dataset_root,
        args.evaluation_root,
        args.dataset_manifest_sha256.lower(),
        args.evaluation_manifest_sha256.lower(),
        args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
