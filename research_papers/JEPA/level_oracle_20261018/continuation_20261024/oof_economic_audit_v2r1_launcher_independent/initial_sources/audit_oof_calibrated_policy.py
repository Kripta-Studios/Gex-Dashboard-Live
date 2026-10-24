"""Independent OOF offset and economic replay audit; no producer imports or fits."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from numbers import Integral, Real
import os
from pathlib import Path
import struct
import traceback
from zoneinfo import ZoneInfo

import exchange_calendars as xc
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
NY = ZoneInfo("America/New_York")
MODES = ("static", "expanding", "rolling12")
TICKERS = ("SPXW", "SPY", "QQQ")
VERSION = "PREQUENTIAL_MAXIMUM_OFFSET_V1"
MONTHLY_STATUS = "PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES"
MONTHS = tuple(f"2026{i:02d}" for i in range(1, 7))
MISSING = {(t, d) for t in ("SPY", "QQQ") for d in ("20260401", "20260409", "20260415")}
FIELDS = (
    "action_id",
    "state_i",
    "score",
    "has_filled_before",
    "status",
    "exit_i",
    "net_base",
    "net_adverse",
)
POLICIES = tuple(m + s for m in MODES for s in ("__control", "__corrected"))
ADAPTER_NAMES = (
    "monthly_oof_calibration_adapter.py",
    "oof_maximum_calibration.py",
    "rolling_monthly_schedule.py",
    "MONTHLY_OOF_CALIBRATION_ADAPTER_SPEC.md",
    "PREQUENTIAL_MAX_CALIBRATION_DESIGN.md",
    "OOF_MAXIMUM_CALIBRATION_INTEGRATION.md",
)
EVALUATOR_NAMES = (
    *ADAPTER_NAMES,
    "evaluate_oof_calibrated_policy.py",
    "OOF_CALIBRATED_POLICY_EVALUATION_SPEC.md",
)
PRODUCER_PINS = {
    "monthly_oof_calibration_adapter.py": "7b80cff43e3887a92e0f89be6daa863a670ccd72d22a0f4aeabd032a39479364",
    "evaluate_oof_calibrated_policy.py": "eeaad06f5b862a3153f29e7eab579b19a35e182ab506cf1f59e65631e187e716",
    "oof_maximum_calibration.py": "19e922dd65855c4cd7e2ec9d482d477a328245bcf642eeeb7771985f247e20b5",
}


def require(condition, message):
    if not bool(condition):
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def payload_sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def digest_value(value):
    require(
        isinstance(value, str)
        and len(value) == 64
        and set(value) <= set("0123456789abcdef"),
        "Invalid SHA256",
    )
    return value


def number(value):
    require(
        isinstance(value, Real)
        and not isinstance(value, (bool, np.bool_))
        and math.isfinite(value),
        "Finite numeric value required",
    )
    return float(value)


def integer(value):
    require(
        isinstance(value, Integral) and not isinstance(value, (bool, np.bool_)),
        "Integer identity required",
    )
    return int(value)


def month_start(value):
    require(
        isinstance(value, str) and len(value) == 6 and value.isdigit(),
        "YYYYMM month required",
    )
    result = datetime(int(value[:4]), int(value[4:]), 1, tzinfo=NY)
    require(result.strftime("%Y%m") == value, "Invalid month")
    return result


def prior_months(month):
    boundary = month_start(month)
    result, year, value = [], 2025, 1
    while datetime(year, value, 1, tzinfo=NY) < boundary:
        result.append(f"{year}{value:02d}")
        year, value = (year + 1, 1) if value == 12 else (year, value + 1)
    return result


def close_time(day, close_i):
    require(close_i in (210, 390), "Session close")
    stamp = datetime.strptime(day, "%Y%m%d")
    return stamp.replace(hour=9, minute=30, tzinfo=NY) + timedelta(minutes=close_i)


def aware(value):
    result = datetime.fromisoformat(value)
    require(
        result.tzinfo is not None and result.utcoffset() is not None,
        "Timezone required",
    )
    return result


def same(actual, expected, context, *, exact=True):
    if exact:
        require(canonical(actual) == canonical(expected), context + " exact payload")
        return
    if isinstance(expected, dict):
        require(
            isinstance(actual, dict) and set(actual) == set(expected), context + " keys"
        )
        for key in expected:
            same(actual[key], expected[key], context + "." + key, exact=False)
    elif isinstance(expected, list):
        require(
            isinstance(actual, list) and len(actual) == len(expected),
            context + " length",
        )
        for left, right in zip(actual, expected):
            same(left, right, context, exact=False)
    elif isinstance(expected, bool) or expected is None:
        require(actual is expected, context)
    elif isinstance(expected, Real):
        require(
            isinstance(actual, Real) and not isinstance(actual, bool),
            context + " numeric type",
        )
        require(
            math.isclose(number(actual), number(expected), rel_tol=0, abs_tol=1e-8),
            context + " numeric",
        )
    else:
        require(actual == expected, context)


def exact_rows(actual, expected):
    require(len(actual) == len(expected), "Control row count")
    for left, right in zip(actual, expected):
        for name in FIELDS:
            if name in ("score", "net_base", "net_adverse"):
                ok = struct.pack("!d", number(left[name])) == struct.pack(
                    "!d", number(right[name])
                )
            else:
                ok = left[name] == right[name]
            require(ok, "Control differs: " + name)


class Seal:
    def __init__(self):
        self.files, self.maps = {}, {}

    def normalize(self, mapping):
        ident = id(mapping)
        if ident not in self.maps:
            result = {}
            require(isinstance(mapping, dict), "Evidence map required")
            for name, value in mapping.items():
                path = Path(name)
                require(path.is_absolute(), "Absolute evidence path required")
                key = str(path.resolve())
                digest_value(value)
                require(
                    key not in result or result[key] == value,
                    "Conflicting path aliases",
                )
                result[key] = value
            self.maps[ident] = (mapping, result)
        return self.maps[ident][1]

    def verify(self, path, expected=None):
        key = str(Path(path).resolve())
        observed = self.files.get(key)
        if observed is None:
            observed = sha(key)
        require(
            expected is None or observed == digest_value(expected),
            "Evidence hash: " + key,
        )
        self.files[key] = observed
        return observed

    def member(self, mapping, path):
        key = str(Path(path).resolve())
        values = self.normalize(mapping)
        require(key in values, "Missing consumed member: " + key)
        return self.verify(key, values[key])

    def mapping(self, mapping):
        for name, value in self.normalize(mapping).items():
            self.verify(name, value)

    def read(self, path, expected=None):
        self.verify(path, expected)
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def payload(self, path, expected, digest=None):
        actual = self.read(path, digest)
        same(actual, expected, str(path))
        return actual

    def recheck(self):
        for path, expected in self.files.items():
            require(sha(path) == expected, "Evidence changed during audit: " + path)


def flatten(groups, seal):
    require(
        isinstance(groups, dict) and bool(groups), "Grouped monthly authority required"
    )
    result = {}
    for group in groups.values():
        for path, value in seal.normalize(group).items():
            require(
                path not in result or result[path] == value,
                "Conflicting monthly groups",
            )
            result[path] = value
    return result


def before(left, right):
    require(
        Path(left).stat().st_mtime <= Path(right).stat().st_mtime + 0.002,
        "Artifact order: " + str(left) + " -> " + str(right),
    )


def validate_calendar(index):
    require(
        len(index) == 2625 and not index.duplicated(["ticker", "date"]).any(),
        "Source calendar count/duplicate",
    )
    schedule = xc.get_calendar("XNYS").schedule.loc["2023-01-03":"2026-06-30"]
    expected = {
        (ticker, d.strftime("%Y%m%d")): int((r.close - r.open).total_seconds() / 60)
        for d, r in schedule.iterrows()
        for ticker in TICKERS
    }
    require(
        set(zip(index.ticker, index.date)) == set(expected), "NYSE calendar membership"
    )
    missing = set()
    for row in index.itertuples(index=False):
        require(row.close_i == expected[row.ticker, row.date], "NYSE session clock")
        require(row.status in ("COMPLETE", "MISSING_SOURCE"), "Unknown source status")
        if row.status == "MISSING_SOURCE":
            missing.add((row.ticker, row.date))
    require(missing == MISSING, "Fixed missing source identities")
    require(
        int(index.date.str.startswith("2025").sum()) == 750
        and int(index.date.str.startswith("2026").sum()) == 369,
        "750/369 calendar",
    )


def fit_window(mode, month):
    require(mode in MODES, "Unknown mode")
    target = month_start(month)
    start = datetime(2023, 1, 1, tzinfo=NY)
    stop = datetime(2025, 1, 1, tzinfo=NY) if mode == "static" else target
    if mode == "rolling12":
        start = target.replace(year=target.year - 1)
    return start, stop, f"train_{start:%Y%m%d}_{stop:%Y%m%d}_exclusive"


class Monthly:
    def __init__(self, request, seal):
        self.seal, self.used = seal, {}
        self.root, self.session = (
            Path(request["monthly_root"]).resolve(),
            Path(request["session_root"]).resolve(),
        )
        self.audit_path = Path(request["monthly_audit"]).resolve()
        self.audit_sha = digest_value(request["monthly_audit_sha256"])
        audit = seal.read(self.audit_path, self.audit_sha)
        require(
            audit["status"] == MONTHLY_STATUS,
            "Independent monthly outputs audit required",
        )
        binding = audit["binding"]
        require(
            Path(binding["monthly_root"]).resolve() == self.root
            and Path(binding["session_root"]).resolve() == self.session,
            "Monthly authority roots",
        )
        self.allowed = flatten(audit["verified_files"], seal)
        self.completed = binding["completed_months"]
        require(
            len(self.completed) == len(set(self.completed)), "Duplicate audited months"
        )
        self.binding = binding["run_contract_sha256"]
        self.contract = self.read(self.root / "run_contract.json", self.binding)
        require(
            self.contract["version"] == "MONTHLY_NET_WALK_FORWARD_V1"
            and self.contract["features"] == 1954
            and self.contract["threshold_usd"] == 0,
            "Monthly scientific contract",
        )
        require(
            Path(self.contract["engine_root"]).resolve() == self.session,
            "Monthly source root",
        )
        audit_path = Path(request["session_audit"]).resolve()
        source_audit = self.read(audit_path, binding["session_audit_sha256"])
        require(
            source_audit["status"] == "PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT",
            "SessionClock authority",
        )
        sb = source_audit["binding"]
        require(
            Path(sb["engine_root"]).resolve() == self.session
            and Path(sb["feature_root"]).resolve() == self.session,
            "SessionClock roots",
        )
        require(
            sb["index_sha256"] == binding["index_sha256"]
            and (sb["available_days"], sb["missing_days"]) == (2619, 6),
            "Source audit coverage",
        )
        require(
            self.contract["source_audit"]["sha256"] == binding["session_audit_sha256"],
            "Contract/source audit mismatch",
        )
        for name, field in (
            ("index.parquet", "index_sha256"),
            ("completion.json", "completion_sha256"),
            ("dataset_contract.json", "dataset_contract_sha256"),
            ("feature_contract.json", "feature_contract_sha256"),
        ):
            seal.verify(self.session / name, sb[field])
        self.verify(self.session / "index.parquet", binding["index_sha256"])
        index = pd.read_parquet(self.session / "index.parquet")
        index["date"] = index.date.astype(str)
        validate_calendar(index)
        self.index = index.set_index(["ticker", "date"], verify_integrity=True)
        self.used[str(self.audit_path)] = self.audit_sha
        self.base_used = dict(self.used)

    def verify(self, path, expected=None):
        value = self.seal.member(self.allowed, path)
        require(expected is None or value == expected, "Monthly authority disagreement")
        self.used[str(Path(path).resolve())] = value
        return value

    def read(self, path, expected=None):
        return self.seal.read(path, self.verify(path, expected))

    def marker(self, name, members):
        value = self.read(self.root / (name + ".complete.json"))
        require(
            value["status"] == "COMPLETE" and value["binding"] == self.binding,
            "Monthly marker contract",
        )
        mapping = {}
        for name, digest in value["files"].items():
            path = (self.root / name).resolve()
            require(path.is_relative_to(self.root), "Escaping monthly marker")
            mapping[str(path)] = digest
        for path in members:
            digest = self.seal.member(mapping, path)
            self.verify(path, digest)
        return value

    def rows(self, month):
        require(month in self.completed, "Month not independently audited")
        prefix = "months/" + month
        record = self.marker(prefix + "/predictions", [])
        require(
            record["extra"]["labels_read"] is False, "Monthly predictions after labels"
        )
        self.marker(
            prefix + "/daily",
            [
                self.root / (prefix + "/daily.json"),
                self.root / (prefix + "/predictions.complete.json"),
            ],
        )
        return self.index.loc[
            self.index.index.get_level_values("date").str.startswith(month)
        ]

    def fit(self, mode, month):
        start, stop, key = fit_window(mode, month)
        name = "fits/" + key + "/inputs"
        path = self.root / (name + ".json")
        self.marker(name, [path])
        info = self.read(path)
        require(
            info["fit_key"] == key
            and info["train_start"] == start.date().isoformat()
            and info["train_stop_exclusive"] == stop.date().isoformat(),
            "Base fold cutoff/window",
        )
        require(info["config"] == self.contract["config"], "Base fit config")
        name = "models/" + key
        model, started = (
            self.root / (name + ".txt"),
            self.root / (name + ".fit_started.json"),
        )
        self.marker(name, [model, started])
        beginning = self.read(started)
        require(
            beginning["binding"] == self.binding
            and beginning["config"] == info["config"]
            and beginning["shape"] == [info["rows"], 1954],
            "Base fit signature",
        )
        require(
            set(info["scales"]) == set(TICKERS)
            and all(number(v) > 0 for v in info["scales"].values()),
            "TRAIN scales",
        )
        result = dict(
            fit_key=key,
            model_sha256=self.verify(model),
            fit_stop_at=stop.isoformat(),
            scales=info["scales"],
        )
        return result

    def table(self, ticker, day, kind):
        require(kind in ("actions", "labels"), "Disallowed source")
        row = self.index.loc[ticker, day]
        require(row.status == "COMPLETE", "Cannot read missing day")
        path, digest = Path(row.day_root) / (kind + ".parquet"), row[kind + "_sha256"]
        self.seal.verify(path, digest)
        self.used[str(path.resolve())] = digest
        result = pd.read_parquet(path)
        return result

    def selection(self, mode, ticker, day):
        row = self.index.loc[ticker, day]
        fit = self.fit(mode, day[:6])
        prefix = f"predictions/{day[:6]}/{fit['fit_key']}/{ticker}/{day}"
        path = self.root / (prefix + ".npz")
        self.marker(prefix, [path])
        self.marker("months/" + day[:6] + "/predictions", [path])
        actions = self.table(ticker, day, "actions")
        with np.load(path, allow_pickle=False) as data:
            require(
                set(data.files)
                == {"action_id", "state_i", "scores", "model_sha256", "scale"},
                "Monthly NPZ schema",
            )
            ids, states, scores = data["action_id"], data["state_i"], data["scores"]
            require(
                scores.dtype == np.dtype("float64")
                and scores.shape == ids.shape == states.shape == (len(actions),),
                "Monthly prediction dtype/shape",
            )
            require(
                str(data["model_sha256"]) == fit["model_sha256"]
                and float(data["scale"]) == fit["scales"][ticker],
                "Monthly model/scale",
            )
            require(
                np.array_equal(ids, actions.action_id)
                and np.array_equal(states, actions.state_i),
                "Monthly prediction/action order",
            )
            selected = maxima(ids, states, scores, int(row.close_i))
        return dict(
            version=VERSION,
            procedure=mode,
            ticker=ticker,
            day=day,
            close_i=int(row.close_i),
            fit_stop_at=fit["fit_stop_at"],
            model_sha256=fit["model_sha256"],
            prediction_sha256=self.verify(path),
            selected=selected,
            outcomes_read=False,
        )

    def controls(self, mode, ticker, day):
        prefix = f"ledgers/{day[:6]}/{mode}/{ticker}/{day}"
        paths = [
            self.root / (prefix + suffix + ".parquet")
            for suffix in ("_attempts", "_ledger")
        ]
        self.marker(prefix, paths)
        result = []
        for path in paths:
            frame = pd.read_parquet(path, columns=list(FIELDS))
            require(
                all(
                    frame[name].dtype == np.dtype("float64")
                    for name in ("score", "net_base", "net_adverse")
                ),
                "Monthly control float64 schema",
            )
            result.append(frame.to_dict("records"))
        return result


def maxima(ids, states, scores, close_i):
    require(close_i in (210, 390), "Session clock")
    ids, states, scores = np.asarray(ids), np.asarray(states), np.asarray(scores)
    require(
        ids.ndim == 1 and ids.shape == states.shape == scores.shape,
        "Score vector shape",
    )
    require(len(set(ids.tolist())) == len(ids), "Duplicate offered action")
    groups = {}
    for ident, state, score in zip(ids, states, scores):
        ident, state, score = integer(ident), integer(state), number(score)
        require(60 <= state <= close_i - 15, "Offer beyond close")
        groups.setdefault(state, []).append((ident, score))
    result = []
    for state in sorted(groups):
        ranked = sorted(groups[state], key=lambda value: (-value[1], value[0]))
        result.append(
            dict(
                state_i=state,
                action_id=ranked[0][0],
                score_usd=ranked[0][1],
                offered_actions=len(ranked),
                second_score_usd=ranked[1][1] if len(ranked) > 1 else None,
            )
        )
    return result


def realized(selection, labels, label_sha):
    require(not labels.action_id.duplicated().any(), "Duplicate labels")
    lookup = labels.set_index("action_id")
    rows = []
    for chosen in selection["selected"]:
        require(chosen["action_id"] in lookup.index, "Missing maximum label")
        label = lookup.loc[chosen["action_id"]]
        net = number(label.net_base)
        require(
            label.status in ("FILLED", "NO_FILL")
            and (label.status != "NO_FILL" or net == 0),
            "Invalid calibration outcome",
        )
        rows.append({**chosen, "status": label.status, "net_base": net})
    return dict(
        selection=selection,
        selection_sha256=payload_sha(selection),
        labels_sha256=label_sha,
        outcome_available_at=(
            close_time(selection["day"], selection["close_i"]) + timedelta(minutes=1)
        ).isoformat(),
        availability_semantics="DECLARED_NYSE_CLOSE_PLUS_ONE_MINUTE_NOT_OBSERVED_RECEIPT",
        rows=rows,
    )


def calibration(records, mode, month, common):
    grouped = {t: [] for t in TICKERS}
    no_offers = dict.fromkeys(TICKERS, 0)
    training, keys = [], set()
    for record in records:
        selection = record["selection"]
        ticker, day = selection["ticker"], selection["day"]
        require(
            selection["procedure"] == mode
            and ticker in TICKERS
            and "20250101" <= day < month + "01",
            "Calibration procedure/history",
        )
        require((ticker, day) not in keys, "Duplicate calibration day")
        keys.add((ticker, day))
        require(
            aware(selection["fit_stop_at"]) <= month_start(day[:6]),
            "In-sample base fit",
        )
        require(
            close_time(day, selection["close_i"])
            < aware(record["outcome_available_at"])
            < month_start(month),
            "Outcome availability boundary",
        )
        require(
            record["availability_semantics"]
            == "DECLARED_NYSE_CLOSE_PLUS_ONE_MINUTE_NOT_OBSERVED_RECEIPT",
            "Availability semantics",
        )
        require(
            record["selection_sha256"] == payload_sha(selection)
            and len(record["rows"]) == len(selection["selected"]),
            "Realized selection binding",
        )
        residuals = []
        for chosen, row in zip(selection["selected"], record["rows"]):
            same({key: row[key] for key in chosen}, chosen, "Maximum after labels")
            net = number(row["net_base"])
            require(
                row["status"] in ("FILLED", "NO_FILL")
                and (row["status"] != "NO_FILL" or net == 0),
                "Calibration status",
            )
            residuals.append(net - number(chosen["score_usd"]))
        if residuals:
            grouped[ticker].append(
                (len(residuals), math.fsum(residuals) / len(residuals))
            )
        else:
            no_offers[ticker] += 1
        training.append(
            dict(
                ticker=ticker,
                day=day,
                record_sha256=payload_sha(record),
                selection_sha256=record["selection_sha256"],
                model_sha256=selection["model_sha256"],
                prediction_sha256=selection["prediction_sha256"],
                labels_sha256=record["labels_sha256"],
                outcome_available_at=record["outcome_available_at"],
            )
        )
    require(
        aware(common["fit_stop_at"]) <= month_start("202501"), "Future common scale"
    )
    offsets, diagnostics = {}, {}
    for ticker in TICKERS:
        values = grouped[ticker]
        require(
            bool(values) and number(common["scales"][ticker]) > 0,
            "No past maxima/TRAIN scale",
        )
        offset = math.fsum(v[1] for v in values) / len(values)
        offsets[ticker] = offset
        diagnostics[ticker] = dict(
            days_with_offers=len(values),
            days_without_offers=no_offers[ticker],
            selected_states=sum(v[0] for v in values),
            offset_usd=offset,
            offset_risk_units=offset / common["scales"][ticker],
        )
    return dict(
        version=VERSION,
        procedure=mode,
        target_month=month,
        offsets_usd=offsets,
        common_scales={t: float(common["scales"][t]) for t in TICKERS},
        scales_train_stop_at=common["fit_stop_at"],
        diagnostics=diagnostics,
        training_records=sorted(training, key=lambda row: (row["day"], row["ticker"])),
        weighting="EQUAL_TICKER_DAY_THEN_OFFERED_STATE",
        threshold=0,
        ranking_changed=False,
        depends_on_has_filled=False,
        year2025_role="CALIBRATOR_TRAIN_NOT_VALIDATION",
        year2026_role="SEEN_DEVELOPMENT_PAST_MONTH_UPDATES_ONLY",
        winner_selected=None,
    )


def replay(rows, close_i, labels, corrected=False):
    require(close_i in (210, 390), "Replay session clock")
    choice, identities = {}, set()
    for row in rows:
        state, ident = integer(row["state_i"]), integer(row["action_id"])
        require(
            60 <= state <= close_i - 15
            and state not in choice
            and ident not in identities,
            "Duplicate/invalid maximum",
        )
        choice[state] = (
            ident,
            number(row["corrected_score_usd" if corrected else "score_usd"]),
        )
        identities.add(ident)
    attempts, decisions, minute, filled = [], [], 60, 0
    while minute <= close_i - 15:
        if minute not in choice or choice[minute][1] <= 0:
            decisions.append(
                dict(state_i=minute, decision="WAIT", has_filled_before=filled)
            )
            minute += 1
            continue
        ident, score = choice[minute]
        require(ident in labels, "Selected outcome absent")
        label = labels[ident]
        require(integer(label["action_id"]) == ident, "Outcome identity")
        status, end = label["status"], integer(label["exit_i"])
        base, adverse = number(label["net_base"]), number(label["net_adverse"])
        require(status in ("FILLED", "NO_FILL"), "Fill status")
        if status == "FILLED":
            require(minute + 2 <= end <= close_i - 5, "Filled exit clock")
        else:
            require(end == minute + 1 and base == adverse == 0, "NO_FILL contract")
        attempts.append(
            dict(
                action_id=ident,
                state_i=minute,
                score=score,
                has_filled_before=filled,
                status=status,
                exit_i=end,
                net_base=base,
                net_adverse=adverse,
            )
        )
        decisions.append(
            dict(
                state_i=minute,
                decision=status,
                action_id=ident,
                has_filled_before=filled,
            )
        )
        filled = int(filled or status == "FILLED")
        minute = end + 1 if status == "FILLED" else minute + 1
    return dict(
        attempts=attempts,
        ledger=[v for v in attempts if v["status"] == "FILLED"],
        decisions=decisions,
    )


def check_costs(actions, labels, close_i):
    require(
        not actions.action_id.duplicated().any()
        and not labels.action_id.duplicated().any(),
        "Duplicate action/label",
    )
    require(set(actions.action_id) == set(labels.action_id), "Action/label universe")
    states = actions.set_index("action_id").state_i
    require(
        actions.state_i.between(60, close_i - 15).all()
        and (actions.entry_i == actions.state_i + 1).all(),
        "Action entry clock",
    )
    for row in labels.itertuples(index=False):
        require(row.status in ("FILLED", "NO_FILL"), "Label status")
        state = int(states.loc[row.action_id])
        if row.status == "NO_FILL":
            require(
                row.exit_i == state + 1 and row.net_base == row.net_adverse == 0,
                "NO_FILL label",
            )
            continue
        require(
            state + 2 <= row.exit_i <= close_i - 5
            and row.hold_minutes == row.exit_i - state - 1,
            "Payoff clock",
        )
        require(
            row.reason in ("TARGET", "STOP", "EOD")
            and number(row.entry_ask) > 0
            and number(row.exit_bid) >= 0,
            "Quote/reason",
        )
        for field, slip in (("net_base", 0.01), ("net_adverse", 0.02)):
            net = (max(row.exit_bid - slip, 0) - row.entry_ask - slip) * 100 - 2.60
            require(
                math.isclose(net, number(getattr(row, field)), rel_tol=0, abs_tol=1e-8),
                "Net cost reconstruction",
            )


def metrics(ledger):
    result = dict(trades=len(ledger))
    for field in ("net_base", "net_adverse"):
        values = [number(row[field]) for row in ledger]
        gains, losses = (
            sum(v for v in values if v > 0),
            -sum(v for v in values if v < 0),
        )
        result.update(
            {
                field: sum(values),
                field + "_gross_gains": gains,
                field + "_gross_losses": losses,
                field + "_profit_factor": gains / losses if losses else None,
                field + "_pf_infinite": bool(gains > 0 and losses == 0),
            }
        )
    return result


def coverage(daily):
    require(
        daily and len({(r["ticker"], r["date"]) for r in daily}) == len(daily),
        "Calendar empty/duplicate",
    )
    require(
        all(r["source_status"] in ("COMPLETE", "MISSING_SOURCE") for r in daily),
        "Coverage source status",
    )
    available = [r for r in daily if r["source_status"] == "COMPLETE"]
    missing = [r for r in daily if r["source_status"] == "MISSING_SOURCE"]
    require(
        all(
            all(r[f] is None for f in ("trades", "net_base", "net_adverse"))
            for r in missing
        ),
        "Missing metrics must remain null",
    )
    zero = sum(r["trades"] == 0 for r in available)
    return dict(
        expected_days=len(daily),
        available_days=len(available),
        missing_days=len(missing),
        available_days_without_fill=zero,
        observable_daily_pass=bool(available) and zero == 0,
        universal_daily_pass=bool(available) and not missing and zero == 0,
        universal_daily_status="NO_EVALUABLE"
        if missing
        else ("PASS" if not zero else "FAIL"),
    )


def inventory(entries, expected, mode, target=False):
    require(len(entries) == len(expected), "Inventory length")
    result = {}
    for entry in entries:
        key = (entry["ticker"], entry["day"])
        require(
            key not in result and key in expected and entry["procedure"] == mode,
            "Inventory identity",
        )
        require(entry["source_status"] == expected[key], "Inventory source status")
        if entry["source_status"] == "MISSING_SOURCE":
            require(
                entry.get("selection_path") is None
                and "selection_sha256" not in entry
                and "score_path" not in entry,
                "Fabricated missing scores",
            )
        else:
            digest_value(entry["selection_sha256"])
            if target:
                digest_value(entry["score_sha256"])
        result[key] = entry
    return result


def score_payload(selection, offset, calibration_sha):
    return dict(
        version=VERSION,
        procedure=selection["procedure"],
        ticker=selection["ticker"],
        day=selection["day"],
        calibration_sha256=calibration_sha,
        selection_sha256=payload_sha(selection),
        rows=[
            {**row, "corrected_score_usd": number(row["score_usd"]) + offset}
            for row in selection["selected"]
        ],
        threshold=0,
        ranking_changed=False,
        outcomes_read=False,
    )


def expected_map(rows):
    return {(t, d): r.status for (t, d), r in rows.iterrows()}


def audit_month(source, correction, month, evaluation, correction_sha, evaluation_sha):
    seal = source.seal
    require(month in MONTHS, "Undeclared target month")
    require(
        set(prior_months(month) + [month]).issubset(source.completed),
        "Incomplete prior/target audited months",
    )
    adapter_code = {name: seal.verify(HERE / name) for name in ADAPTER_NAMES}
    evaluation_code = {name: seal.verify(HERE / name) for name in EVALUATOR_NAMES}
    closure_path = correction / (month + ".complete.json")
    closure = seal.read(closure_path, correction_sha)
    require(
        closure["status"] == "COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS"
        and closure["target_month"] == month,
        "Correction completion",
    )
    require(
        closure["monthly_audit_sha256"] == source.audit_sha
        and closure["target_labels_read"] is False
        and closure["base_models_refitted"] is False
        and closure["winner_selected"] is None
        and closure["development_seen"] is True,
        "Correction scope",
    )
    same(closure["dependencies"], adapter_code, "Adapter dependencies")
    require(set(closure["procedures"]) == set(MODES), "Three correction procedures")
    implementation = correction / "implementation.json"
    seal.payload(
        implementation,
        dict(
            dependencies=adapter_code,
            monthly_root=str(source.root),
            session_root=str(source.session),
            version=VERSION,
            calibrator_window="EXPANDING_FROM_202501",
            threshold=0,
            winner_selected=None,
        ),
    )
    run_path = correction / (month + ".run_contract.json")
    seal.payload(
        run_path,
        dict(
            target_month=month,
            monthly_audit_sha256=source.audit_sha,
            implementation_sha256=seal.verify(implementation),
        ),
    )
    inputs = seal.read(correction / (month + ".inputs.json"), closure["inputs_sha256"])
    same(inputs["dependencies"], adapter_code, "Correction input dependencies")
    require(
        inputs["monthly_audit_sha256"] == source.audit_sha, "Correction input authority"
    )
    for name in ("files", "run_authorities"):
        seal.mapping(inputs[name])
    for path in (implementation, run_path):
        seal.member(inputs["run_authorities"], path)
    complete = seal.read(evaluation / "completion.json", evaluation_sha)
    require(
        complete["status"] == "COMPLETE_FIXED_OOF_POLICY_MONTH"
        and complete["target_month"] == month
        and complete["winner_selected"] is None,
        "Replay completion",
    )
    same(complete["dependencies"], evaluation_code, "Replay dependencies")
    seal.mapping(complete["files"])
    seal.mapping(complete["monthly_files"])
    for path in evaluation.rglob("*"):
        if path.is_file() and path.name not in ("completion.json", ".lock"):
            seal.member(complete["files"], path)
    evaluation_contract = evaluation / "run_contract.json"
    seal.payload(
        evaluation_contract,
        dict(
            version="OOF_POLICY_REPLAY_V1",
            dependencies=evaluation_code,
            monthly_audit_sha256=source.audit_sha,
            correction_completion_sha256=correction_sha,
            target_month=month,
            threshold=0,
            winner_selected=None,
        ),
    )
    score_seal_path = evaluation / "all_scores_and_controls.json"
    score_seal = seal.read(score_seal_path)
    require(score_seal["target_labels_read"] is False, "Month score seal after labels")
    same(score_seal["dependencies"], evaluation_code, "Score seal dependencies")
    seal.mapping(score_seal["files"])
    seal.mapping(score_seal["monthly_files"])
    source.used = dict(source.base_used)
    target_rows = source.rows(month)
    replay_used = dict(source.used)
    expected_target = expected_map(target_rows)
    history_rows = pd.concat([source.rows(m) for m in prior_months(month)])
    expected_history = expected_map(history_rows)
    common = source.fit("static", "202501")
    correction_used = dict(source.used)
    prepared, controls, offsets = {}, {}, {}
    history_count = 0
    for mode in MODES:
        item = closure["procedures"][mode]
        historical = inventory(item["history_calendar"], expected_history, mode)
        records = []
        for (ticker, day), entry in historical.items():
            if entry["source_status"] == "MISSING_SOURCE":
                continue
            source.used = {}
            selected = source.selection(mode, ticker, day)
            selection_path = correction / mode / "selections" / ticker / (day + ".json")
            seal.payload(selection_path, selected, entry["selection_sha256"])
            labels = source.table(ticker, day, "labels")
            record = realized(
                selected, labels, source.index.loc[(ticker, day)].labels_sha256
            )
            path = correction / mode / "realized" / ticker / (day + ".json")
            seal.payload(path, record)
            before(selection_path, path)
            require(
                aware(record["outcome_available_at"]) < month_start(month),
                "Future calibration labels",
            )
            records.append(record)
            correction_used.update(source.used)
        rebuilt = calibration(records, mode, month, common)
        calibration_path = correction / mode / month / "calibration.json"
        seal.payload(calibration_path, rebuilt, item["calibration_sha256"])
        before(implementation, calibration_path)
        before(run_path, calibration_path)
        for entry in historical.values():
            if entry["source_status"] == "COMPLETE":
                before(
                    correction
                    / mode
                    / "realized"
                    / entry["ticker"]
                    / (entry["day"] + ".json"),
                    calibration_path,
                )
        offsets[mode] = rebuilt["offsets_usd"]
        history_count += sum(len(record["rows"]) for record in records)
        del records
        target = inventory(item["target_calendar"], expected_target, mode, target=True)
        for (ticker, day), entry in target.items():
            key = (mode, ticker, day)
            if entry["source_status"] == "MISSING_SOURCE":
                prepared[key] = None
                continue
            source.used = {}
            selected = source.selection(mode, ticker, day)
            correction_used.update(source.used)
            replay_used.update(source.used)
            selection_path = correction / mode / "selections" / ticker / (day + ".json")
            require(
                Path(entry["selection_path"]).resolve() == selection_path.resolve(),
                "Target selection path",
            )
            seal.payload(selection_path, selected, entry["selection_sha256"])
            baseline = (
                evaluation / "baseline" / mode / "selections" / ticker / (day + ".json")
            )
            seal.payload(baseline, selected, entry["selection_sha256"])
            corrected = score_payload(
                selected, rebuilt["offsets_usd"][ticker], item["calibration_sha256"]
            )
            score_path = correction / mode / month / "scores" / ticker / (day + ".json")
            require(
                Path(entry["score_path"]).resolve() == score_path.resolve(),
                "Corrected score path",
            )
            seal.payload(score_path, corrected, entry["score_sha256"])
            for path in (baseline, score_path, calibration_path):
                seal.member(score_seal["files"], path)
                seal.member(complete["files"], path)
            before(selection_path, score_path)
            before(calibration_path, score_path)
            before(score_path, score_seal_path)
            source.used = {}
            attempts, ledger = source.controls(mode, ticker, day)
            replay_used.update(source.used)
            require(
                len({v["action_id"] for v in attempts}) == len(attempts),
                "Duplicate control attempt",
            )
            control = replay(
                selected["selected"],
                selected["close_i"],
                {v["action_id"]: v for v in attempts},
            )
            exact_rows(control["attempts"], attempts)
            exact_rows(control["ledger"], ledger)
            controls[key] = control
            prepared[key] = (selected, corrected)
    require(
        score_seal["controls_verified"] == len(controls),
        "All controls before new labels",
    )
    # Required consumed inputs, not merely the keys a manifest elected to include.
    for path, digest in correction_used.items():
        seal.member(inputs["files"], path)
        seal.member(score_seal["files"], path)
        seal.member(complete["files"], path)
        require(seal.files[path] == digest, "Consumed correction source disagreement")
    for path in seal.normalize(inputs["run_authorities"]):
        seal.member(score_seal["files"], path)
        seal.member(complete["files"], path)
    for path, digest in replay_used.items():
        seal.member(score_seal["monthly_files"], path)
        seal.member(complete["monthly_files"], path)
        require(seal.files[path] == digest, "Consumed source disagreement")
    source.used = {}
    daily = {p: [] for p in POLICIES}
    ledgers = {p: [] for p in POLICIES}
    by_ticker = {p: {t: [] for t in TICKERS} for p in POLICIES}
    for (mode, ticker, day), pair in prepared.items():
        trajectories = {}
        if pair is not None:
            selection, corrected = pair
            actions = source.table(ticker, day, "actions")
            labels = source.table(ticker, day, "labels")
            check_costs(actions, labels, selection["close_i"])
            lookup = {int(r["action_id"]): r for r in labels.to_dict("records")}
            for suffix, rows, is_corrected in (
                ("__control", selection["selected"], False),
                ("__corrected", corrected["rows"], True),
            ):
                trajectories[suffix] = replay(
                    rows, selection["close_i"], lookup, is_corrected
                )
            exact_rows(
                trajectories["__control"]["attempts"],
                controls[mode, ticker, day]["attempts"],
            )
        for suffix in ("__control", "__corrected"):
            policy = mode + suffix
            row = dict(
                ticker=ticker,
                date=day,
                source_status="COMPLETE" if pair is not None else "MISSING_SOURCE",
            )
            trajectory = trajectories.get(suffix)
            if trajectory is None:
                row.update(trades=None, net_base=None, net_adverse=None)
            else:
                row.update(metrics(trajectory["ledger"]))
                ledgers[policy].extend(trajectory["ledger"])
                by_ticker[policy][ticker].extend(trajectory["ledger"])
            daily[policy].append(row)
            path = evaluation / "days" / policy / ticker / (day + ".json")
            saved = seal.read(path)
            same(saved["daily"], row, "Daily metrics", exact=False)
            same(saved["trajectory"], trajectory, "Daily trajectory")
            before(score_seal_path, path)
    summary = dict(
        status="COMPLETE_FIXED_OOF_POLICY_MONTH",
        target_month=month,
        policies={
            p: dict(
                coverage=coverage(daily[p]),
                observed=metrics(ledgers[p]),
                daily=daily[p],
            )
            for p in POLICIES
        },
        winner_selected=None,
        refitted=False,
        development_seen=True,
        year2025_role="CALIBRATOR_TRAIN_NOT_VALIDATION",
        full_period_complete=False,
    )
    same(
        seal.read(evaluation / "summary.json"), summary, "Monthly summary", exact=False
    )
    for path in (
        closure_path,
        correction / (month + ".inputs.json"),
        evaluation_contract,
        score_seal_path,
        evaluation / "summary.json",
    ):
        seal.member(complete["files"], path)
    for path in source.used:
        seal.member(complete["monthly_files"], path)
    return dict(
        target_month=month,
        offsets_usd=offsets,
        historical_maxima=history_count,
        controls_verified=len(controls),
        policies={
            p: dict(
                **summary["policies"][p],
                by_ticker={
                    t: dict(
                        observed=metrics(by_ticker[p][t]),
                        coverage=coverage([r for r in daily[p] if r["ticker"] == t]),
                    )
                    for t in TICKERS
                },
            )
            for p in POLICIES
        },
    )


def combined_reports(months):
    reports = {}
    full = {r["target_month"] for r in months} == set(MONTHS) and len(months) == 6
    for policy in POLICIES:
        daily = [d for r in months for d in r["policies"][policy]["daily"]]
        by_ticker = {}
        for ticker in TICKERS:
            pieces = [
                r["policies"][policy]["by_ticker"][ticker]["observed"] for r in months
            ]
            totals = dict(trades=sum(r["trades"] for r in pieces))
            for field in ("net_base", "net_adverse"):
                for suffix in ("", "_gross_gains", "_gross_losses"):
                    totals[field + suffix] = sum(r[field + suffix] for r in pieces)
                gain, loss = (
                    totals[field + "_gross_gains"],
                    totals[field + "_gross_losses"],
                )
                totals[field + "_profit_factor"] = gain / loss if loss else None
                totals[field + "_pf_infinite"] = bool(gain > 0 and loss == 0)
            positive = sum(r["net_base"] > 0 for r in pieces)
            pf = totals["net_base_profit_factor"]
            economic = (
                totals["net_base"] > 0
                and totals["net_adverse"] > 0
                and (totals["net_base_pf_infinite"] or (pf is not None and pf >= 1.2))
                and totals["trades"] >= 60
                and positive >= 3
            )
            by_ticker[ticker] = dict(
                observed=totals,
                coverage=coverage([d for d in daily if d["ticker"] == ticker]),
                positive_months=positive,
                economic_gate_status=("PASS" if economic else "FAIL")
                if full
                else "NOT_EVALUATED_INCOMPLETE_H1",
            )
        reports[policy] = dict(
            coverage=coverage(daily),
            by_ticker=by_ticker,
            economic_gate_status=(
                "PASS"
                if all(r["economic_gate_status"] == "PASS" for r in by_ticker.values())
                else "FAIL"
            )
            if full
            else "NOT_EVALUATED_INCOMPLETE_H1",
        )
    return reports


def audit(request_path, request_sha):
    seal = Seal()
    request = seal.read(request_path, digest_value(request_sha))
    require(
        request["version"] == "OOF_ECONOMIC_AUDIT_REQUEST_V1", "Audit request version"
    )
    items = request["months"]
    names = [item["month"] for item in items]
    require(
        names == sorted(set(names)) and names and set(names) <= set(MONTHS),
        "Audit month request",
    )
    require(request["scope"] in ("MONTHS", "FULL_H1"), "Audit scope")
    require(
        request["scope"] != "FULL_H1" or names == list(MONTHS),
        "Six months required for full audit",
    )
    for name, digest in PRODUCER_PINS.items():
        seal.verify(HERE / name, digest)
    for name in (
        "audit_oof_calibrated_policy.py",
        "test_audit_oof_calibrated_policy.py",
        "OOF_ECONOMIC_AUDITOR_SPEC_20261023.md",
        "OOF_ECONOMIC_AUDITOR_DESIGN_20261023.md",
    ):
        seal.verify(HERE / name)
    source = Monthly(request, seal)
    correction = Path(request["correction_root"]).resolve()
    protected = [source.root, source.session, correction]
    roots = [Path(item["evaluation_root"]).resolve() for item in items]
    require(len(set(roots)) == len(roots), "Distinct replay roots required")
    for root in roots:
        require(
            all(
                not root.is_relative_to(p) and not p.is_relative_to(root)
                for p in protected
            ),
            "Overlapping replay roots",
        )
    reports = []
    for item, root in zip(items, roots):
        # A fresh consumed-input view prevents earlier audited target labels being
        # mistaken for the next producer's pre-label input membership requirements.
        source.used = dict(source.base_used)
        reports.append(
            audit_month(
                source,
                correction,
                item["month"],
                root,
                digest_value(item["correction_completion_sha256"]),
                digest_value(item["evaluation_completion_sha256"]),
            )
        )
    seal.recheck()
    return dict(
        status="PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_FULL_H1"
        if names == list(MONTHS)
        else "PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_DECLARED_MONTHS",
        scope="OOF_OFFSETS_AND_ECONOMIC_EXECUTION_GIVEN_AUDITED_BASE_SCORES",
        binding=dict(
            request_sha256=request_sha,
            monthly_audit_sha256=source.audit_sha,
            audited_months=names,
            correction_root=str(correction),
        ),
        months=reports,
        policies=combined_reports(reports),
        verified_files=seal.files,
        winner_selected=None,
        base_fit_reproduced=False,
        base_inference_reproduced=False,
        raw_quote_replay=False,
        development_seen=True,
        technical_ready=False,
        promotion_approved=False,
        finished_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def publish(path, value):
    temporary = path.with_suffix(path.suffix + ".partial")
    require(not path.exists() and not temporary.exists(), "Preserve audit artifacts")
    with temporary.open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def resource_gate():
    import ctypes
    import psutil

    available = psutil.virtual_memory().available
    if os.name == "nt":

        class Status(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (n, ctypes.c_ulonglong)
                for n in (
                    "total_phys",
                    "avail_phys",
                    "total_page",
                    "avail_page",
                    "total_virtual",
                    "avail_virtual",
                    "avail_extended",
                )
            ]

        status = Status()
        status.length = ctypes.sizeof(Status)
        require(
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)),
            "Memory status failure",
        )
        commit = status.avail_page
    else:
        commit = available + psutil.swap_memory().free
    require(min(available, commit) >= 2_000_000_000, "At least 2GB RAM/commit required")
    return dict(available_ram_bytes=available, available_commit_bytes=commit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    resources = resource_gate()
    require(
        sha(args.request) == digest_value(args.request_sha256), "External request hash"
    )
    request = json.loads(args.request.read_text(encoding="utf-8"))
    output = args.output.resolve()
    protected = [
        HERE,
        Path(request["monthly_root"]).resolve(),
        Path(request["session_root"]).resolve(),
        Path(request["correction_root"]).resolve(),
        *[Path(v["evaluation_root"]).resolve() for v in request["months"]],
    ]
    require(
        all(
            not output.is_relative_to(p) and not p.is_relative_to(output)
            for p in protected
        ),
        "Separate audit output required",
    )
    output.mkdir(parents=True, exist_ok=False)
    try:
        result = audit(args.request, args.request_sha256)
        result["admission_resources"] = resources
        publish(output / "audit.json", result)
        print(
            json.dumps(
                dict(
                    status=result["status"], months=result["binding"]["audited_months"]
                )
            ),
            flush=True,
        )
    except BaseException:
        publish(
            output / "audit_failure.json",
            dict(
                status="FAILED_OR_INTERRUPTED_PRESERVED",
                traceback=traceback.format_exc(),
            ),
        )
        raise


if __name__ == "__main__":
    main()
