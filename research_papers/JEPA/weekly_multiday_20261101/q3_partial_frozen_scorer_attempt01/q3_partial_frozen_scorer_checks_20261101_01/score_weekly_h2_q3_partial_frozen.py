"""Frozen H2 scorer for the authorized 2026 Q3 partial extension.

No estimator or calibrator is constructed here.  The only statistical state is
loaded from the externally pinned, completed H1 evaluation package.
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
POLICIES = ("EV_TOP1_H2", "ALWAYS_CALL_H2", "ALWAYS_PUT_H2", "ALWAYS_ABSTAIN")
COSTS = ("base", "adverse")
SPLIT = "Q3_PARTIAL_2026_SEEN_DEVELOPMENT"
FIRST_DATE = "20260701"
LAST_DATE = "20260917"
LAST_ENTRY = "20260915"
STARTING_CASH = 100_000.0
CONTRACT_SHA256 = "9c7917e1ab9b89e361027b7f41c5d12399b64d72ac41b7b629998a8ed8681417"
WRAPPER_SHA256 = "8d49f31cb411db68c05dd1aa1964665e0795e3959b895ac462bafcb03484dc5e"
BUILDER_SHA256 = "ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945"
SOURCE_PILOT_SHA256 = "ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878"
H2_CONTRACT_SHA256 = "245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5"
CLOCK_AMENDMENT_SHA256 = (
    "9210c6e50094e5745f80c5e03f577f6bd673263f84d3c3ef764ad76b22ca56eb"
)
EVALUATOR_SHA256 = "8a9e75855d542a12662e5c812583f2ef86042f5c3ae1bbbad73c16042e063476"
H1_DATASET_MANIFEST_SHA256 = (
    "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8"
)
CALENDAR_JSON_SHA256 = (
    "ac9bd2569d91e9bd9b0475d6f5e2d5400b2816cc1d1d0d9ec98c69e4dbe2e72b"
)
CALENDAR_PARQUET_SHA256 = (
    "e16ef041efadc0f6914585540e19e9c04fcb05f1597952137e4f5bcf06de8c78"
)
CALENDAR_MANIFEST_SHA256 = (
    "5a530747f2c97704869d87c04d09bba3cc00125f38a8a78454c2d459a2ea502c"
)
H1_EVALUATION_MANIFEST_SHA256 = (
    "54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96"
)
FROZEN = {
    "model.json": "68712c7c326d2337a34f8401579ddc52a4dab0e3f505c8c4ff2f1b1d51c03fb4",
    "transform.json": "db4be1e1863ab825117fac6278023fe0b5036ba1454d44243266a5eeb3f9736b",
    "conditional_means.json": "a8dc329233ce431b282c500e27cf91ac91d845cbb6a1fc752cee36026aef3f90",
    "calibration_grid.json": "0b587bedbabc1cb405c203f11910e5ed10d7ea025e529a98f4ebf2daa1049ed4",
}
CANDIDATE_FIELDS = {
    "candidate_id",
    "ticker",
    "entry_date",
    "exit_date",
    "expiration",
    "strike",
    "right",
    "features",
    "decision_ask",
    "entry_ask",
    "exit_bid",
    "status",
    "label_available_at",
    "scenario",
    "net_base",
    "net_adverse",
    "entry_debit_base",
    "entry_debit_adverse",
    "payoff_is_lower_bound",
    "source_pins",
}
SESSIONS = tuple(
    "20260701 20260702 20260706 20260707 20260708 20260709 20260710 "
    "20260713 20260714 20260715 20260716 20260717 20260720 20260721 "
    "20260722 20260723 20260724 20260727 20260728 20260729 20260730 "
    "20260731 20260803 20260804 20260805 20260806 20260807 20260810 "
    "20260811 20260812 20260813 20260814 20260817 20260818 20260819 "
    "20260820 20260821 20260824 20260825 20260826 20260827 20260828 "
    "20260831 20260901 20260902 20260903 20260904 20260908 20260909 "
    "20260910 20260911 20260914 20260915 20260916 20260917".split()
)


class ScoringError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScoringError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL line {number}")
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")


def finite(value: Any, name: str) -> float:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{name} numeric",
    )
    result = float(value)
    require(math.isfinite(result), f"{name} finite")
    return result


def plain_existing(path: Path, name: str) -> Path:
    absolute = Path(os.path.abspath(path))
    require(absolute.is_dir(), f"{name} directory")
    current = absolute
    while True:
        info = current.lstat()
        reparse = bool(getattr(info, "st_file_attributes", 0) & 0x400)
        require(not stat.S_ISLNK(info.st_mode) and not reparse, f"{name} link/reparse")
        if current.parent == current:
            break
        current = current.parent
    require(not str(absolute).lower().startswith("d:\\thetadata\\"), f"{name} DTheta")
    return absolute


def plain_output(path: Path, inputs: tuple[Path, ...]) -> Path:
    absolute = Path(os.path.abspath(path))
    require(not absolute.exists(), "output exists")
    require(
        all(
            not absolute.is_relative_to(root) and not root.is_relative_to(absolute)
            for root in inputs
        ),
        "output nested",
    )
    require(
        not str(absolute).lower().startswith("d:\\thetadata\\"),
        "output DTheta",
    )
    current = absolute.parent
    while True:
        info = current.lstat()
        reparse = bool(getattr(info, "st_file_attributes", 0) & 0x400)
        require(not stat.S_ISLNK(info.st_mode) and not reparse, "output link/reparse")
        if current.parent == current:
            break
        current = current.parent
    return absolute


def snapshot(root: Path, names: set[str]) -> dict[str, tuple[int, str]]:
    return {
        name: ((root / name).stat().st_size, sha256_file(root / name))
        for name in sorted(names)
    }


def load_frozen(root: Path, manifest_sha256: str) -> dict[str, Any]:
    manifest_path = root / "manifest.json"
    require(manifest_sha256 == H1_EVALUATION_MANIFEST_SHA256, "H1 manifest authority")
    require(sha256_file(manifest_path) == manifest_sha256, "H1 manifest hash")
    manifest = read_json(manifest_path)
    require(manifest.get("schema") == "weekly_h2_ev_manifest_v1", "H1 manifest schema")
    for name, digest in FROZEN.items():
        path = root / name
        require(
            path.is_file() and sha256_file(path) == digest, f"frozen artifact {name}"
        )
        pin = manifest.get("outputs", {}).get(name)
        require(
            pin == {"bytes": path.stat().st_size, "sha256": digest},
            f"H1 manifest pin {name}",
        )
    transform, model = (
        read_json(root / "transform.json"),
        read_json(root / "model.json"),
    )
    means, grid = (
        read_json(root / "conditional_means.json"),
        read_json(root / "calibration_grid.json"),
    )
    require(
        transform.get("fit_scope") == model.get("fit_scope") == "TRAIN_ONLY",
        "frozen fit scope",
    )
    require(transform.get("feature_order") == list(FEATURES), "frozen feature order")
    require(
        len(transform.get("medians", [])) == 18
        and len(transform.get("scaler_mean", [])) == 19
        and len(transform.get("scaler_scale", [])) == 19,
        "frozen transform dimensions",
    )
    require(
        model.get("classes_full") == list(range(5))
        and model.get("classes_present") == list(range(5)),
        "frozen classes",
    )
    require(
        len(model.get("coefficient", [])) == 5
        and all(len(row) == 19 for row in model["coefficient"])
        and len(model.get("intercept", [])) == 5
        and len(model.get("train_prior", [])) == 5
        and abs(math.fsum(model["train_prior"]) - 1.0) <= 1e-12,
        "frozen model dimensions",
    )
    require(
        len(transform.get("missing_indicator_source_indices", [])) == 1
        and transform.get("missing_indicator_order")
        == [f"{FEATURES[transform['missing_indicator_source_indices'][0]]}__missing"]
        and all(
            finite(value, "frozen scale") > 0 for value in transform["scaler_scale"]
        ),
        "frozen missing indicator/scales",
    )
    require(
        grid.get("selected_alpha") == 0.3 and len(grid.get("scores", [])) == 11,
        "frozen alpha/grid",
    )
    require(means.get("shrinkage") == 20, "frozen shrinkage")
    return {
        "transform": transform,
        "model": model,
        "means": means,
        "alpha": 0.3,
        "manifest": manifest,
    }


def transform(values: list[float | None], state: dict[str, Any]) -> list[float]:
    indices = state["missing_indicator_source_indices"]
    medians = state["medians"]
    expanded = [
        medians[i] if value is None else value for i, value in enumerate(values)
    ] + [float(values[i] is None) for i in indices]
    require(len(expanded) == 19, "transformed dimension")
    return [
        (value - state["scaler_mean"][i]) / state["scaler_scale"][i]
        for i, value in enumerate(expanded)
    ]


def probabilities(values: list[float], model: dict[str, Any]) -> list[float]:
    logits = [
        math.fsum(weight * value for weight, value in zip(row, values, strict=True))
        + model["intercept"][i]
        for i, row in enumerate(model["coefficient"])
    ]
    maximum = max(logits)
    weights = [math.exp(value - maximum) for value in logits]
    total = math.fsum(weights)
    return [value / total for value in weights]


def feature_values(row: dict[str, Any]) -> list[float | None]:
    features = row.get("features")
    require(
        isinstance(features, dict) and tuple(features) == FEATURES, "candidate features"
    )
    return [
        None if features[name] is None else finite(features[name], name)
        for name in FEATURES
    ]


def close(actual: Any, expected: float, name: str) -> None:
    require(abs(finite(actual, name) - expected) <= 1e-8, f"{name} mismatch")


def validate_candidate(row: dict[str, Any]) -> None:
    require(set(row) == CANDIDATE_FIELDS, "candidate fields")
    values = feature_values(row)
    entry = datetime.strptime(row["entry_date"], "%Y%m%d")
    expiration = datetime.strptime(row["expiration"], "%Y%m%d")
    require(
        values[:3] == [float(row["ticker"] == ticker) for ticker in TICKERS]
        and values[3] == float(row["right"] == "CALL"),
        "candidate one-hot",
    )
    require(
        values[4] == (expiration - entry).days
        and 1 <= values[4] <= 8
        and values[5] == entry.weekday(),
        "candidate date features",
    )
    require(values[6] > 0 and values[7] > 0, "spot/strike")
    close(values[8], values[7] / values[6] - 1, "moneyness")
    require(0 <= values[9] <= values[10] and 0 < values[10] <= 49.95, "decision quote")
    close(values[11], (values[10] - values[9]) / values[10], "spread")
    require(
        -1 <= values[12] <= 1
        and (
            (row["right"] == "CALL" and values[12] > 0)
            or (row["right"] == "PUT" and values[12] < 0)
        ),
        "delta",
    )
    close(row["decision_ask"], values[10], "decision ask")
    close(row["strike"], values[7], "strike")
    status = row["status"]
    require(
        status
        in {"NO_FILL", "OBSERVED_EXIT", "MISSING_EXIT_QUOTE", "MISSING_EXIT_SOURCE"},
        "status",
    )
    if status == "NO_FILL":
        require(
            row["scenario"] == 0
            and row["entry_ask"] is None
            and row["exit_bid"] is None
            and row["payoff_is_lower_bound"] is False,
            "NO_FILL",
        )
        for name in (
            "net_base",
            "net_adverse",
            "entry_debit_base",
            "entry_debit_adverse",
        ):
            close(row[name], 0.0, name)
        return
    ask = finite(row["entry_ask"], "entry ask")
    require(0 < ask <= 49.95, "entry ask")
    close(row["entry_debit_base"], (ask + 0.01) * 100 + 1.30, "base debit")
    close(row["entry_debit_adverse"], (ask + 0.02) * 100 + 1.30, "adverse debit")
    if status == "OBSERVED_EXIT":
        bid = finite(row["exit_bid"], "exit bid")
        require(bid >= 0 and row["payoff_is_lower_bound"] is False, "observed exit")
        raw = (bid - ask) / ask
        scenario = 1 if raw < -0.25 else 2 if raw < 0 else 3 if raw < 0.25 else 4
        require(row["scenario"] == scenario, "scenario")
    else:
        require(
            row["exit_bid"] is None
            and row["scenario"] == 1
            and row["payoff_is_lower_bound"] is True,
            "lower bound",
        )
        bid = 0.0
    for cost, slip in (("base", 0.01), ("adverse", 0.02)):
        close(
            row[f"net_{cost}"],
            (max(bid - slip, 0) - ask - slip) * 100 - 2.60,
            f"net {cost}",
        )


def score_rows(
    rows: list[dict[str, Any]], frozen: dict[str, Any]
) -> list[dict[str, Any]]:
    output = []
    alpha = frozen["alpha"]
    prior = frozen["model"]["train_prior"]
    for row in rows:
        p_model = probabilities(
            transform(feature_values(row), frozen["transform"]), frozen["model"]
        )
        p_cal = [
            (1 - alpha) * p + alpha * q for p, q in zip(p_model, prior, strict=True)
        ]
        key = f"{row['ticker']}:{row['right']}"
        ev = {}
        for cost in COSTS:
            conditional = [
                frozen["means"]["cells"][cost][key][str(label)]["mean_y"]
                for label in range(5)
            ]
            ev[cost] = (
                row["decision_ask"]
                * 100
                * math.fsum(p * y for p, y in zip(p_cal, conditional, strict=True))
            )
        row["_p_model"], row["_p_cal"], row["_ev_base"], row["_ev_adverse"] = (
            p_model,
            p_cal,
            ev["base"],
            ev["adverse"],
        )
        output.append(
            {
                "candidate_id": row["candidate_id"],
                "split": SPLIT,
                "p_model": p_model,
                "p_cal": p_cal,
                "ev_base": ev["base"],
                "ev_adverse": ev["adverse"],
                "scenario": row["scenario"],
                "status": row["status"],
                "payoff_is_lower_bound": row["payoff_is_lower_bound"],
            }
        )
    return output


def load_dataset(
    root: Path, manifest_sha256: str
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    names = {
        "inventory.json",
        "inventory_manifest.json",
        "candidates.jsonl",
        "coverage.json",
        "manifest.json",
    }
    require(
        {path.name for path in root.iterdir() if path.is_file()} == names,
        "dataset file closure",
    )
    manifest_path = root / "manifest.json"
    require(sha256_file(manifest_path) == manifest_sha256, "dataset manifest hash")
    manifest = read_json(manifest_path)
    require(
        manifest.get("schema") == "weekly_h2_q3_partial_dataset_manifest_v1",
        "dataset schema",
    )
    require(
        manifest.get("status") == "COMPLETE_WEEKLY_H2_Q3_PARTIAL_DATASET_NOT_EVALUATED",
        "dataset status",
    )
    require(manifest.get("split") == SPLIT, "dataset split")
    require(
        manifest.get("flags")
        == {
            "no_fit": True,
            "no_refit": True,
            "no_recalibration": True,
            "no_selection": True,
            "not_oos": True,
            "not_promotion": True,
            "not_technical_readiness": True,
        },
        "dataset flags",
    )
    require(
        set(manifest.get("files", {})) == names - {"manifest.json"},
        "dataset pins closure",
    )
    for name, pin in manifest["files"].items():
        path = root / name
        require(
            set(pin) == {"bytes", "sha256"}
            and pin["bytes"] == path.stat().st_size
            and pin["sha256"] == sha256_file(path),
            f"dataset pin {name}",
        )
    calendar_pin = manifest.get("calendar_pin", {})
    require(
        {
            key: calendar_pin.get(key)
            for key in (
                "session_count",
                "ticker_count",
                "row_count",
                "first_date",
                "last_date",
                "last_eligible_entry",
            )
        }
        == {
            "session_count": 55,
            "ticker_count": 3,
            "row_count": 165,
            "first_date": FIRST_DATE,
            "last_date": LAST_DATE,
            "last_eligible_entry": LAST_ENTRY,
        },
        "calendar pin scope",
    )
    pins = manifest.get("implementation_pins", {})
    required_hashes = {
        CONTRACT_SHA256,
        WRAPPER_SHA256,
        BUILDER_SHA256,
        SOURCE_PILOT_SHA256,
        H2_CONTRACT_SHA256,
        CLOCK_AMENDMENT_SHA256,
        EVALUATOR_SHA256,
        H1_DATASET_MANIFEST_SHA256,
        CALENDAR_JSON_SHA256,
        CALENDAR_PARQUET_SHA256,
        CALENDAR_MANIFEST_SHA256,
        *FROZEN.values(),
        H1_EVALUATION_MANIFEST_SHA256,
    }
    require(
        required_hashes == {value for value in pins.values() if isinstance(value, str)},
        "implementation frozen pins",
    )
    inventory = read_json(root / "inventory.json")
    require(
        inventory.get("schema") == "weekly_h2_q3_partial_inventory_v1",
        "inventory schema",
    )
    coverage = read_json(root / "coverage.json")
    require(
        coverage.get("schema") == "weekly_h2_q3_partial_coverage_v1", "coverage schema"
    )
    calendar = coverage.get("calendar")
    require(
        isinstance(calendar, list) and len(calendar) == 165, "coverage calendar count"
    )
    identities = {(item["ticker"], item["date"]) for item in calendar}
    require(
        identities == {(ticker, date) for date in SESSIONS for ticker in TICKERS}
        and all(item.get("close_i") == 390 for item in calendar),
        "coverage calendar identities",
    )
    cover_rows = coverage.get("rows")
    require(
        isinstance(cover_rows, list) and len(cover_rows) == 165, "coverage row count"
    )
    cover_index = {(item["ticker"], item["entry_date"]): item for item in cover_rows}
    require(set(cover_index) == identities, "coverage row identities")
    for ticker in TICKERS:
        for date in ("20260916", "20260917"):
            item = cover_index[(ticker, date)]
            require(
                item.get("status") == "HORIZON_OUTSIDE_CALENDAR"
                and item.get("candidate_ids") == [],
                "terminal coverage",
            )
    rows = read_jsonl(root / "candidates.jsonl")
    ids = set()
    for row in rows:
        candidate_id = row.get("candidate_id")
        require(
            isinstance(candidate_id, str) and candidate_id not in ids,
            "candidate identity unique",
        )
        ids.add(candidate_id)
        require(
            row.get("ticker") in TICKERS and row.get("right") in RIGHTS,
            "candidate ticker/right",
        )
        require(
            FIRST_DATE <= row.get("entry_date", "") <= LAST_ENTRY, "candidate date leak"
        )
        validate_candidate(row)
        require(
            row["entry_date"] < row["exit_date"] < row["expiration"]
            and row["exit_date"] in SESSIONS,
            "candidate H2 ordering",
        )
        require(
            row["exit_date"] == SESSIONS[SESSIONS.index(row["entry_date"]) + 2],
            "candidate is not official H2",
        )
        require(
            candidate_id
            == f"{row['ticker']}:{row['entry_date']}:{row['expiration']}:{row['right']}",
            "candidate ID",
        )
        feature_values(row)
    coverage_ids = [
        candidate_id
        for item in cover_rows
        for candidate_id in item.get("candidate_ids", [])
    ]
    require(
        len(coverage_ids) == len(set(coverage_ids)) and set(coverage_ids) == ids,
        "coverage candidate universe",
    )
    return rows, coverage, manifest


def choose(
    candidates: list[dict[str, Any]], policy: str
) -> tuple[dict[str, Any] | None, str]:
    if policy == "ALWAYS_ABSTAIN":
        return None, "ABSTAIN"
    if policy in {"ALWAYS_CALL_H2", "ALWAYS_PUT_H2"}:
        right = "CALL" if policy == "ALWAYS_CALL_H2" else "PUT"
        matches = [row for row in candidates if row["right"] == right]
        require(len(matches) <= 1, "multiple fixed-side candidates")
        return (matches[0], "FIXED_CONTROL") if matches else (None, "NO_SERIES")
    require(policy == "EV_TOP1_H2", "policy")
    if not candidates:
        return None, "NO_SERIES"
    best = max(row["_ev_adverse"] for row in candidates)
    matches = [row for row in candidates if row["_ev_adverse"] == best]
    if best <= 0:
        return None, "EV_NOT_POSITIVE"
    if len(matches) != 1:
        return None, "EV_TIE_WAIT"
    return matches[0], "EV_TOP1"


def replay(
    rows: list[dict[str, Any]], coverage: dict[str, Any], policy: str, cost: str
) -> list[dict[str, Any]]:
    slip = 0.01 if cost == "base" else 0.02
    by_identity: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_identity[(row["entry_date"], row["ticker"])].append(row)
    cover = {(item["ticker"], item["entry_date"]): item for item in coverage["rows"]}
    opened: dict[str, dict[str, Any]] = {}
    cash = STARTING_CASH
    reserved = 0.0
    ledger = []
    for date in SESSIONS:
        for ticker in TICKERS:
            if ticker in opened and opened[ticker]["exit_date"] == date:
                row = opened.pop(ticker)
                principal = (row["entry_ask"] + slip) * 100
                bid = 0.0 if row["exit_bid"] is None else row["exit_bid"]
                cash += max(bid - slip, 0.0) * 100 - 1.30
                reserved -= principal
                ledger.append(
                    {
                        "event": "EXIT",
                        "date": date,
                        "ticker": ticker,
                        "candidate_id": row["candidate_id"],
                        "status": row["status"],
                        "split": SPLIT,
                        "right": row["right"],
                        "cost": cost,
                        "entry_date": row["entry_date"],
                        "duration_calendar_days": (
                            datetime.strptime(date, "%Y%m%d")
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
            if date > LAST_ENTRY:
                continue
            candidates = by_identity.get((date, ticker), [])
            if ticker in opened:
                ledger.append(
                    {
                        "event": "WAIT",
                        "date": date,
                        "ticker": ticker,
                        "split": SPLIT,
                        "cost": cost,
                        "reason": "OPEN_POSITION",
                    }
                )
                continue
            if not candidates:
                item = cover[(ticker, date)]
                ledger.append(
                    {
                        "event": "NO_OPPORTUNITY",
                        "date": date,
                        "ticker": ticker,
                        "split": SPLIT,
                        "cost": cost,
                        "reason": item.get("reason") or item["status"],
                    }
                )
                continue
            if policy in {"ALWAYS_CALL_H2", "ALWAYS_PUT_H2"}:
                required = "CALL" if policy == "ALWAYS_CALL_H2" else "PUT"
                if not any(row["right"] == required for row in candidates):
                    ledger.append(
                        {
                            "event": "NO_OPPORTUNITY",
                            "date": date,
                            "ticker": ticker,
                            "split": SPLIT,
                            "cost": cost,
                            "reason": f"{required}_SIDE_UNAVAILABLE",
                        }
                    )
                    continue
            selected, reason = choose(candidates, policy)
            if selected is None:
                ledger.append(
                    {
                        "event": "WAIT",
                        "date": date,
                        "ticker": ticker,
                        "split": SPLIT,
                        "cost": cost,
                        "reason": reason,
                    }
                )
                continue
            if selected["status"] == "NO_FILL":
                ledger.append(
                    {
                        "event": "NO_FILL",
                        "date": date,
                        "ticker": ticker,
                        "candidate_id": selected["candidate_id"],
                        "split": SPLIT,
                        "cost": cost,
                        "reason": "ENTRY_QUOTE",
                    }
                )
                continue
            debit = selected[f"entry_debit_{cost}"]
            if cash < debit:
                ledger.append(
                    {
                        "event": "CAPITAL_BLOCKED",
                        "date": date,
                        "ticker": ticker,
                        "candidate_id": selected["candidate_id"],
                        "split": SPLIT,
                        "cost": cost,
                        "reason": "CAPITAL",
                    }
                )
                continue
            cash -= debit
            principal = (selected["entry_ask"] + slip) * 100
            reserved += principal
            opened[ticker] = selected
            ledger.append(
                {
                    "event": "ENTRY",
                    "date": date,
                    "ticker": ticker,
                    "candidate_id": selected["candidate_id"],
                    "right": selected["right"],
                    "split": SPLIT,
                    "cost": cost,
                    "exit_date": selected["exit_date"],
                    "selection_reason": reason,
                    "ev_base": selected["_ev_base"],
                    "ev_adverse": selected["_ev_adverse"],
                    "cash": cash,
                    "reserved": reserved,
                    "equity": cash + reserved,
                    "realized_delta": -1.30,
                    "principal": principal,
                }
            )
    require(not opened and abs(reserved) <= 1e-7, "book close")
    require(
        abs(
            cash
            - (
                STARTING_CASH
                + math.fsum(row["net_usd"] for row in ledger if row["event"] == "EXIT")
            )
        )
        <= 1e-6,
        "cash reconciliation",
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
        require(running_reserved >= -1e-7, "reserved below zero")
        max_reserved = max(max_reserved, running_reserved)
    months: dict[str, float] = defaultdict(float)
    for row in exits:
        months[row["date"][:6]] += row["net_usd"]
    durations = [row["duration_calendar_days"] for row in exits]
    return {
        "trades": len(exits),
        "no_fill": sum(row["event"] == "NO_FILL" for row in relevant),
        "capital_blocked": sum(row["event"] == "CAPITAL_BLOCKED" for row in relevant),
        "wait": sum(row["event"] == "WAIT" for row in relevant),
        "no_opportunity": sum(row["event"] == "NO_OPPORTUNITY" for row in relevant),
        "missing_exit": sum(
            row.get("status") in {"MISSING_EXIT_QUOTE", "MISSING_EXIT_SOURCE"}
            for row in exits
        ),
        "missing_exit_quote": sum(
            row.get("status") == "MISSING_EXIT_QUOTE" for row in exits
        ),
        "missing_exit_source": sum(
            row.get("status") == "MISSING_EXIT_SOURCE" for row in exits
        ),
        "net_usd": math.fsum(values),
        "profit_factor": gains / losses
        if losses
        else (None if gains == 0 else "Infinity"),
        "fresh_starting_cash": STARTING_CASH,
        "final_cash": STARTING_CASH + math.fsum(values),
        "overnight_exposure_sessions": 2 * len(exits),
        "realized_max_drawdown_usd": drawdown,
        "positive_months": sum(value > 0 for value in months.values()),
        "months_observed": len(months),
        "duration_calendar_days_mean": math.fsum(durations) / len(durations)
        if durations
        else None,
        "duration_calendar_days_min": min(durations) if durations else None,
        "duration_calendar_days_max": max(durations) if durations else None,
        "max_reserved": max_reserved,
    }


def run(
    dataset_root: Path,
    dataset_manifest_sha256: str,
    frozen_root: Path,
    frozen_manifest_sha256: str,
    output: Path,
) -> dict[str, Any]:
    require(
        sha256_file(
            Path(__file__).with_name("WEEKLY_H2_2026Q3_PARTIAL_EXTENSION_CONTRACT.md")
        )
        == CONTRACT_SHA256,
        "local extension contract pin",
    )
    dataset_root = plain_existing(dataset_root, "dataset")
    frozen_root = plain_existing(frozen_root, "frozen evaluation")
    require(
        dataset_root != frozen_root
        and not dataset_root.is_relative_to(frozen_root)
        and not frozen_root.is_relative_to(dataset_root),
        "input roots nested",
    )
    output = plain_output(output, (dataset_root, frozen_root))
    dataset_names = {
        "inventory.json",
        "inventory_manifest.json",
        "candidates.jsonl",
        "coverage.json",
        "manifest.json",
    }
    frozen_names = {"manifest.json", *FROZEN}
    initial_dataset = snapshot(dataset_root, dataset_names)
    initial_frozen = snapshot(frozen_root, frozen_names)
    rows, coverage, dataset_manifest = load_dataset(
        dataset_root, dataset_manifest_sha256
    )
    frozen = load_frozen(frozen_root, frozen_manifest_sha256)
    scores = score_rows(rows, frozen)
    ledgers = {}
    economics = {}
    for policy in POLICIES:
        ledgers[policy] = {}
        economics[policy] = {}
        for cost in COSTS:
            ledger = replay(rows, coverage, policy, cost)
            ledgers[policy][cost] = ledger
            economics[policy][cost] = {
                "pooled": metrics(ledger),
                "tickers": {ticker: metrics(ledger, ticker) for ticker in TICKERS},
            }
    divergences = {}
    for policy in POLICIES:
        base_ids = {
            row["candidate_id"]
            for row in ledgers[policy]["base"]
            if row["event"] == "ENTRY"
        }
        adverse_ids = {
            row["candidate_id"]
            for row in ledgers[policy]["adverse"]
            if row["event"] == "ENTRY"
        }
        divergences[policy] = {
            "base_entries": len(base_ids),
            "adverse_entries": len(adverse_ids),
            "base_only": sorted(base_ids - adverse_ids),
            "adverse_only": sorted(adverse_ids - base_ids),
        }
    summary = {
        "schema": "weekly_h2_q3_partial_frozen_scoring_v1",
        "status": "COMPLETE_EXTENSION_PARTIAL_SEEN_DEVELOPMENT",
        "split": SPLIT,
        "scope": "forward continuation / SEEN_DEVELOPMENT mixed",
        "entry_range": [FIRST_DATE, LAST_ENTRY],
        "calendar_range": [FIRST_DATE, LAST_DATE],
        "candidate_count": len(rows),
        "score_count": len(scores),
        "economics": economics,
        "book_divergences": divergences,
        "fresh_book_usd": STARTING_CASH,
        "fit_performed": False,
        "refit_performed": False,
        "recalibration_performed": False,
        "selection_performed": False,
        "technical_ready": False,
        "promotion_approved": False,
    }
    require(
        snapshot(dataset_root, dataset_names) == initial_dataset,
        "dataset changed before publication",
    )
    require(
        snapshot(frozen_root, frozen_names) == initial_frozen,
        "frozen artifacts changed before publication",
    )
    output.mkdir(parents=True)
    write_jsonl(output / "candidate_scores_extension.jsonl", scores)
    for policy, books in ledgers.items():
        for cost, ledger in books.items():
            write_jsonl(
                output
                / f"ledger_{policy.lower()}_q3_partial_2026_seen_development_{cost}.jsonl",
                ledger,
            )
    write_json(output / "summary_extension.json", summary)
    outputs = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(output.iterdir())
    }
    write_json(
        output / "manifest.json",
        {
            "schema": "weekly_h2_q3_partial_frozen_scoring_manifest_v1",
            "status": "COMPLETE_EXTENSION_PARTIAL_SEEN_DEVELOPMENT",
            "inputs": {
                "dataset_manifest": {
                    "bytes": (dataset_root / "manifest.json").stat().st_size,
                    "sha256": dataset_manifest_sha256,
                    "schema": dataset_manifest["schema"],
                },
                "frozen_evaluation_manifest": {
                    "bytes": (frozen_root / "manifest.json").stat().st_size,
                    "sha256": frozen_manifest_sha256,
                    "schema": frozen["manifest"]["schema"],
                },
                "frozen_artifacts": {
                    name: {
                        "bytes": (frozen_root / name).stat().st_size,
                        "sha256": digest,
                    }
                    for name, digest in FROZEN.items()
                },
            },
            "implementation_pins": {
                "score_weekly_h2_q3_partial_frozen.py": sha256_file(Path(__file__)),
                "WEEKLY_H2_2026Q3_PARTIAL_EXTENSION_CONTRACT.md": CONTRACT_SHA256,
            },
            "outputs": outputs,
            "flags": {
                "fit_performed": False,
                "refit_performed": False,
                "recalibration_performed": False,
                "selection_performed": False,
                "not_oos": True,
                "technical_ready": False,
                "promotion_approved": False,
            },
        },
    )
    require(
        snapshot(dataset_root, dataset_names) == initial_dataset,
        "dataset changed during writes",
    )
    require(
        snapshot(frozen_root, frozen_names) == initial_frozen,
        "frozen artifacts changed during writes",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score the fixed Q3 partial extension with frozen H1 state."
    )
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--dataset-manifest-sha256", required=True)
    parser.add_argument("--frozen-evaluation-root", required=True, type=Path)
    parser.add_argument("--frozen-evaluation-manifest-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(
        args.dataset_root,
        args.dataset_manifest_sha256.lower(),
        args.frozen_evaluation_root,
        args.frozen_evaluation_manifest_sha256.lower(),
        args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
