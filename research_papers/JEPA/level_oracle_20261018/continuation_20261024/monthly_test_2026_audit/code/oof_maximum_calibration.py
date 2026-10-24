"""Outcome-free max selection and past-only offset estimation; no market runner.

Every action score must come from a model whose exclusive fit cutoff precedes
the scored month. Actual artifacts/provenance must be pinned by a caller before
using this utility. No in-sample reconstruction, oracle labels or threshold fit.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
import json
import math
from numbers import Integral
import os
from pathlib import Path
import uuid
from zoneinfo import ZoneInfo

VERSION = "PREQUENTIAL_MAXIMUM_OFFSET_V1"
PROCEDURES = ("static", "expanding", "rolling12")
TICKERS = ("SPXW", "SPY", "QQQ")
NY = ZoneInfo("America/New_York")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def content_sha(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def hash_value(value):
    require(
        isinstance(value, str)
        and len(value) == 64
        and set(value) <= set("0123456789abcdef"),
        "Expected lowercase SHA256",
    )
    return value


def instant(text):
    parsed = datetime.fromisoformat(text)
    require(
        parsed.tzinfo is not None and parsed.utcoffset() is not None,
        "Explicit timezone required",
    )
    return parsed


def month_start(month):
    require(
        isinstance(month, str) and len(month) == 6 and month.isdigit(),
        "YYYYMM required",
    )
    return datetime(int(month[:4]), int(month[4:]), 1, tzinfo=NY)


def session_date(text):
    require(
        isinstance(text, str) and len(text) == 8 and text.isdigit(), "YYYYMMDD required"
    )
    parsed = datetime.strptime(text, "%Y%m%d").date()
    require(parsed.strftime("%Y%m%d") == text, "Invalid session date")
    return parsed


def finite(value):
    require(
        not isinstance(value, bool) and math.isfinite(value),
        "Finite numeric value required",
    )
    return float(value)


def integer(value):
    require(
        isinstance(value, Integral) and not isinstance(value, bool),
        "Integer identity required",
    )
    return int(value)


def session_close(selection):
    """Physical NYSE horizon, not a claim about actual data receipt latency."""
    day = session_date(selection["day"])
    require(selection["close_i"] in (210, 390), "Unknown session clock")
    return datetime(day.year, day.month, day.day, 9, 30, tzinfo=NY) + timedelta(
        minutes=selection["close_i"]
    )


def maximum_selection(
    *,
    procedure,
    ticker,
    day,
    close_i,
    fit_stop_at,
    model_sha256,
    prediction_sha256,
    actions,
):
    """Select using only offered action IDs/clocks/scores, including negative maxima.

    fit_stop_at is the EXCLUSIVE historical training cutoff, not wall-clock model
    creation time. Prediction artifact hashing/OOF fit provenance is the caller's
    obligation; a bare claimed cutoff is not an independent source audit.
    """
    require(
        procedure in PROCEDURES and ticker in TICKERS, "Unknown base procedure/ticker"
    )
    session_date(day)
    require(close_i in (210, 390), "Unknown session clock")
    cutoff = instant(fit_stop_at)
    require(cutoff <= month_start(day[:6]), "In-sample or future base fit cutoff")
    hash_value(model_sha256)
    hash_value(prediction_sha256)
    offered, identities = {}, set()
    for row in actions:
        require(
            set(row) == {"action_id", "state_i", "score_usd"},
            "Only causal offered score columns accepted",
        )
        ident, state, score = (
            integer(row["action_id"]),
            integer(row["state_i"]),
            finite(row["score_usd"]),
        )
        require(ident not in identities, "Duplicate offered action")
        require(60 <= state <= close_i - 15, "Action beyond session decision horizon")
        identities.add(ident)
        offered.setdefault(state, []).append((ident, score))
    selected = []
    for state in sorted(offered):
        ordered = sorted(offered[state], key=lambda pair: (-pair[1], pair[0]))
        selected.append(
            dict(
                state_i=state,
                action_id=ordered[0][0],
                score_usd=ordered[0][1],
                offered_actions=len(ordered),
                second_score_usd=ordered[1][1] if len(ordered) > 1 else None,
            )
        )
    return dict(
        version=VERSION,
        procedure=procedure,
        ticker=ticker,
        day=day,
        close_i=close_i,
        fit_stop_at=fit_stop_at,
        model_sha256=model_sha256,
        prediction_sha256=prediction_sha256,
        selected=selected,
        outcomes_read=False,
    )


def publish(path, payload):
    """Immutable atomic artifact; caller can retain its SHA before any label read."""
    path = Path(path)
    require(not path.exists(), "Never overwrite a sealed artifact")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial-" + uuid.uuid4().hex)
    with temporary.open("xb") as handle:
        handle.write(canonical_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return file_sha(path)


def load_seal(path, expected_sha):
    require(file_sha(path) == hash_value(expected_sha), "Sealed artifact hash differs")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def realized_maxima(
    selection_path,
    expected_sha,
    label_loader,
    *,
    labels_sha256,
    outcome_available_at,
    availability_semantics,
):
    """Invoke the outcome loader only after verifying a published causal selection.

    Loader returns action_id/status/net_base rows. It must itself verify the
    externally pinned labels_sha256. Historical availability is explicit and is
    not confused with this replay's filesystem creation/read timestamps.
    """
    selection = load_seal(selection_path, expected_sha)
    require(
        selection["version"] == VERSION and selection["outcomes_read"] is False,
        "Not an outcome-free selection",
    )
    hash_value(labels_sha256)
    available = instant(outcome_available_at)
    require(
        isinstance(availability_semantics, str)
        and bool(availability_semantics.strip()),
        "Availability semantics required",
    )
    require(
        available > session_close(selection),
        "Outcome availability must be strictly after the session close",
    )
    labels = {}
    for row in label_loader():
        require(
            set(row) == {"action_id", "status", "net_base"},
            "Explicit label projection required",
        )
        ident, net = integer(row["action_id"]), finite(row["net_base"])
        require(
            ident not in labels and row["status"] in ("FILLED", "NO_FILL"),
            "Invalid label identity/status",
        )
        require(row["status"] != "NO_FILL" or net == 0, "NO_FILL must have zero net")
        labels[ident] = dict(status=row["status"], net_base=net)
    rows = []
    for chosen in selection["selected"]:
        require(chosen["action_id"] in labels, "Selected action has no bound outcome")
        rows.append({**chosen, **labels[chosen["action_id"]]})
    load_seal(selection_path, expected_sha)
    return dict(
        selection=selection,
        selection_sha256=expected_sha,
        labels_sha256=labels_sha256,
        outcome_available_at=outcome_available_at,
        availability_semantics=availability_semantics,
        rows=rows,
    )


def estimate_offsets(
    realized_days, *, procedure, target_month, common_scales, scales_train_stop_at
):
    """Three parameters, one per ticker; equal weight per day and offered state.

    This function is called only on completed prequential records from months
    earlier than target_month. No thresholds or model procedure are selected.
    """
    boundary = month_start(target_month)
    require(
        procedure in PROCEDURES and "202601" <= target_month <= "202606",
        "Declared development months2026H1 only",
    )
    require(
        set(common_scales) == set(TICKERS)
        and all(finite(value) > 0 for value in common_scales.values()),
        "Three positive TRAIN scales required",
    )
    require(
        instant(scales_train_stop_at) <= month_start("202501"),
        "Common scale must precede2025 OOF history",
    )
    grouped, identities, records = {ticker: [] for ticker in TICKERS}, set(), []
    no_offer_days = {ticker: 0 for ticker in TICKERS}
    for day in realized_days:
        selection = day["selection"]
        require(
            content_sha(selection) == hash_value(day["selection_sha256"]),
            "Unsealed or changed selection payload",
        )
        require(
            selection["version"] == VERSION
            and selection["outcomes_read"] is False
            and selection["procedure"] == procedure,
            "Mixed or invalid base procedures",
        )
        ticker, stamp = selection["ticker"], session_date(selection["day"])
        require(
            ticker in TICKERS and date(2025, 1, 1) <= stamp < boundary.date(),
            "Same/future-month or pre2025 calibration row",
        )
        require(
            instant(selection["fit_stop_at"]) <= month_start(selection["day"][:6]),
            "In-sample base prediction",
        )
        require(
            instant(day["outcome_available_at"]) < boundary,
            "Outcome not available strictly before calibration month",
        )
        require(
            instant(day["outcome_available_at"]) > session_close(selection),
            "Outcome availability must be strictly after the session close",
        )
        require(
            bool(day["availability_semantics"].strip()),
            "Availability semantics missing",
        )
        for field in ("model_sha256", "prediction_sha256"):
            hash_value(selection[field])
        hash_value(day["labels_sha256"])
        key = (ticker, stamp)
        require(key not in identities, "Duplicate calibration day")
        identities.add(key)
        require(
            len(day["rows"]) == len(selection["selected"]),
            "Selected-state coverage changed",
        )
        residuals, means = [], []
        for chosen, row in zip(selection["selected"], day["rows"]):
            require(
                all(row[field] == value for field, value in chosen.items()),
                "Max action/state/score changed after labels",
            )
            net = finite(row["net_base"])
            require(
                row["status"] in ("FILLED", "NO_FILL")
                and (row["status"] != "NO_FILL" or net == 0),
                "Invalid fill target",
            )
            residuals.append(net - finite(row["score_usd"]))
            means.append(net)
        if residuals:
            grouped[ticker].append(
                dict(
                    states=len(residuals),
                    mean_residual=math.fsum(residuals) / len(residuals),
                    mean_realized=math.fsum(means) / len(means),
                )
            )
        else:
            no_offer_days[ticker] += 1
        records.append(
            dict(
                ticker=ticker,
                day=selection["day"],
                record_sha256=content_sha(day),
                selection_sha256=day["selection_sha256"],
                model_sha256=selection["model_sha256"],
                prediction_sha256=selection["prediction_sha256"],
                labels_sha256=day["labels_sha256"],
                outcome_available_at=day["outcome_available_at"],
            )
        )
    offsets, diagnostics = {}, {}
    for ticker in TICKERS:
        days = grouped[ticker]
        require(bool(days), "No past OOF maxima for ticker " + ticker)
        offset = math.fsum(row["mean_residual"] for row in days) / len(days)
        offsets[ticker] = offset
        diagnostics[ticker] = dict(
            days_with_offers=len(days),
            days_without_offers=no_offer_days[ticker],
            selected_states=sum(row["states"] for row in days),
            offset_usd=offset,
            offset_risk_units=offset / common_scales[ticker],
        )
    return dict(
        version=VERSION,
        procedure=procedure,
        target_month=target_month,
        offsets_usd=offsets,
        common_scales={ticker: float(common_scales[ticker]) for ticker in TICKERS},
        scales_train_stop_at=scales_train_stop_at,
        diagnostics=diagnostics,
        training_records=sorted(records, key=lambda row: (row["day"], row["ticker"])),
        weighting="EQUAL_TICKER_DAY_THEN_OFFERED_STATE",
        threshold=0,
        ranking_changed=False,
        depends_on_has_filled=False,
        year2025_role="CALIBRATOR_TRAIN_NOT_VALIDATION",
        year2026_role="SEEN_DEVELOPMENT_PAST_MONTH_UPDATES_ONLY",
        winner_selected=None,
    )


def apply_offsets_and_seal(
    path, *, calibration_path, calibration_sha256, selection_path, selection_sha256
):
    """No outcomes accepted; publish corrected scores before future label access."""
    calibration = load_seal(calibration_path, calibration_sha256)
    selection = load_seal(selection_path, selection_sha256)
    require(calibration["version"] == selection["version"] == VERSION, "Wrong version")
    require(
        selection["procedure"] == calibration["procedure"]
        and selection["day"][:6] == calibration["target_month"],
        "Wrong procedure/month application",
    )
    require(
        selection["outcomes_read"] is False
        and calibration["threshold"] == 0
        and calibration["ranking_changed"] is False,
        "Policy changed",
    )
    offset = finite(calibration["offsets_usd"][selection["ticker"]])
    rows = [
        {**row, "corrected_score_usd": finite(row["score_usd"]) + offset}
        for row in selection["selected"]
    ]
    result = dict(
        version=VERSION,
        procedure=selection["procedure"],
        ticker=selection["ticker"],
        day=selection["day"],
        calibration_sha256=calibration_sha256,
        selection_sha256=selection_sha256,
        rows=rows,
        threshold=0,
        ranking_changed=False,
        outcomes_read=False,
    )
    return publish(path, result)


def labels_after_score_seal(score_path, score_sha256, label_loader):
    payload = load_seal(score_path, score_sha256)
    require(
        payload["version"] == VERSION and payload["outcomes_read"] is False,
        "Score seal missing",
    )
    result = label_loader()
    load_seal(score_path, score_sha256)
    return result
