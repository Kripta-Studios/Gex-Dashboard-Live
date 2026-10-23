"""Synthetic independent-audit faults; producer imports generate fixtures only."""

from datetime import timedelta
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

import audit_oof_calibrated_policy as audit


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(audit.canonical(value))
    return path


def example(day="20250102", ticker="SPY", scores=(-2.0, -1.0)):
    return dict(
        version=audit.VERSION,
        procedure="static",
        ticker=ticker,
        day=day,
        close_i=390,
        fit_stop_at="2025-01-01T00:00:00-05:00",
        model_sha256="a" * 64,
        prediction_sha256="b" * 64,
        selected=audit.maxima(
            list(range(1, len(scores) + 1)),
            list(range(60, 60 + len(scores))),
            scores,
            390,
        ),
        outcomes_read=False,
    )


def labels_for(selection, residual=2.0):
    return pd.DataFrame(
        [
            dict(
                action_id=r["action_id"],
                status="FILLED",
                net_base=r["score_usd"] + residual,
            )
            for r in selection["selected"]
        ]
    )


def common():
    return dict(
        scales={t: 10.0 for t in audit.TICKERS}, fit_stop_at="2025-01-01T00:00:00-05:00"
    )


def records():
    return [
        audit.realized(s, labels_for(s), "c" * 64)
        for s in [example(ticker=t) for t in audit.TICKERS]
    ]


def test_maxima_preserves_negative_tie_second_and_empty():
    result = audit.maxima([4, 2, 7], [60, 60, 61], [-1.0, -1.0, -5.0], 210)
    assert result == [
        dict(
            state_i=60,
            action_id=2,
            score_usd=-1.0,
            offered_actions=2,
            second_score_usd=-1.0,
        ),
        dict(
            state_i=61,
            action_id=7,
            score_usd=-5.0,
            offered_actions=1,
            second_score_usd=None,
        ),
    ]
    assert audit.maxima([], [], [], 210) == []
    with pytest.raises(ValueError, match="beyond close"):
        audit.maxima([1], [196], [2.0], 210)


def test_offset_equal_day_then_state_not_action_rows():
    values = records()
    extra = example("20250203", scores=(0.0,))
    extra["selected"] = extra["selected"][:1]
    values.append(audit.realized(extra, labels_for(extra, 10), "d" * 64))
    got = audit.calibration(values, "static", "202601", common())
    assert got["offsets_usd"]["SPY"] == 6.0
    assert got["diagnostics"]["SPY"]["selected_states"] == 3


@pytest.mark.parametrize(
    "fault", ["future", "availability", "mixed", "duplicate", "cutoff", "changed_max"]
)
def test_calibration_causal_faults(fault):
    values = records()
    if fault == "future":
        values[0]["selection"]["day"] = "20260102"
    elif fault == "availability":
        values[0]["outcome_available_at"] = audit.month_start("202601").isoformat()
    elif fault == "mixed":
        values[0]["selection"]["procedure"] = "rolling12"
    elif fault == "duplicate":
        values.append(values[0])
    elif fault == "cutoff":
        values[0]["selection"]["fit_stop_at"] = "2025-02-01T00:00:00-05:00"
    else:
        values[0]["rows"][0]["action_id"] = 999
    with pytest.raises(ValueError):
        audit.calibration(values, "static", "202601", common())


def test_empty_days_and_nofill_do_not_disappear():
    values = records()
    empty = example("20250203")
    empty["selected"] = []
    values.append(
        audit.realized(
            empty, pd.DataFrame(columns=["action_id", "status", "net_base"]), "d" * 64
        )
    )
    nofill = example("20250303", scores=(-2.0, -1.0))
    labels = labels_for(nofill)
    labels["status"], labels["net_base"] = "NO_FILL", 0.0
    values.append(audit.realized(nofill, labels, "e" * 64))
    result = audit.calibration(values, "static", "202601", common())
    assert result["diagnostics"]["SPY"]["days_without_offers"] == 1
    assert result["offsets_usd"]["SPY"] == 1.75


def test_dst_and_short_availability():
    assert audit.close_time("20250703", 210).isoformat() == "2025-07-03T13:00:00-04:00"
    assert audit.close_time("20250102", 390).isoformat() == "2025-01-02T16:00:00-05:00"
    assert audit.fit_window("rolling12", "202602")[0].strftime("%Y%m%d") == "20250201"
    assert (
        audit.fit_window("static", "202606")[2]
        == audit.fit_window("expanding", "202501")[2]
    )


def test_replay_changed_states_h_nofill_and_threshold():
    choices = [
        dict(action_id=i, state_i=s, score_usd=x, corrected_score_usd=x + 2)
        for i, s, x in [(1, 60, -1.0), (2, 61, 1.0), (3, 62, 4.0), (4, 66, 0.0)]
    ]
    labels = {
        i: dict(
            action_id=i,
            status=status,
            exit_i=end,
            net_base=b,
            net_adverse=b - 2 if status == "FILLED" else 0.0,
        )
        for i, status, end, b in [
            (1, "NO_FILL", 61, 0.0),
            (2, "FILLED", 65, -3.0),
            (3, "FILLED", 64, 5.0),
            (4, "FILLED", 68, 1.0),
        ]
    }
    control = audit.replay(choices, 210, labels)
    changed = audit.replay(choices, 210, labels, True)
    assert [r["action_id"] for r in control["attempts"]] == [2]
    assert [r["action_id"] for r in changed["attempts"]] == [1, 2, 4]
    assert [r["has_filled_before"] for r in changed["attempts"]] == [0, 0, 1]
    assert changed["decisions"][0]["decision"] == "NO_FILL"
    labels[4]["exit_i"] = 206
    with pytest.raises(ValueError, match="exit clock"):
        audit.replay(choices, 210, labels, True)


def test_exact_control_keeps_signed_zero():
    left = dict(
        action_id=1,
        state_i=60,
        score=-0.0,
        has_filled_before=0,
        status="NO_FILL",
        exit_i=61,
        net_base=0.0,
        net_adverse=0.0,
    )
    audit.exact_rows([left], [dict(left)])
    with pytest.raises(ValueError, match="score"):
        audit.exact_rows([left], [dict(left, score=0.0)])


def test_seal_required_members_aliases_mutation_and_publication(tmp_path):
    path = write(tmp_path / "source.json", {"v": 1})
    seal = audit.Seal()
    with pytest.raises(ValueError, match="Missing consumed"):
        seal.member({}, path)
    with pytest.raises(ValueError, match="Absolute"):
        seal.normalize({"relative": audit.sha(path)})
    seal.member({str(path): audit.sha(path)}, path)
    write(path, {"v": 2})
    with pytest.raises(ValueError, match="changed during"):
        seal.recheck()
    with pytest.raises(ValueError, match="Preserve"):
        audit.publish(path, {"v": 3})


def full_calendar():
    schedule = audit.xc.get_calendar("XNYS").schedule.loc["2023-01-03":"2026-06-30"]
    return pd.DataFrame(
        [
            dict(
                ticker=t,
                date=d.strftime("%Y%m%d"),
                close_i=int((r.close - r.open).total_seconds() / 60),
                status="MISSING_SOURCE"
                if (t, d.strftime("%Y%m%d")) in audit.MISSING
                else "COMPLETE",
            )
            for d, r in schedule.iterrows()
            for t in audit.TICKERS
        ]
    )


def test_complete_calendar_missing_is_not_cash():
    frame = full_calendar()
    audit.validate_calendar(frame)
    frame.loc[frame.status == "MISSING_SOURCE", "status"] = "COMPLETE"
    with pytest.raises(ValueError, match="missing"):
        audit.validate_calendar(frame)
    daily = [
        dict(
            ticker="SPY",
            date="20260401",
            source_status="MISSING_SOURCE",
            trades=None,
            net_base=None,
            net_adverse=None,
        ),
        dict(
            ticker="QQQ",
            date="20260401",
            source_status="COMPLETE",
            trades=0,
            net_base=0,
            net_adverse=0,
        ),
    ]
    result = audit.coverage(daily)
    assert (
        result["universal_daily_status"] == "NO_EVALUABLE"
        and result["available_days_without_fill"] == 1
    )
    daily[0]["net_base"] = 0
    with pytest.raises(ValueError, match="null"):
        audit.coverage(daily)


class TinySource:
    """Synthetic I/O boundary; real frozen producer APIs write tiny fixture outputs."""

    def __init__(self, root):
        self.root = (root / "monthly").resolve()
        self.session_root = self.session = (root / "session").resolve()
        self.audit_path = write(
            root / "monthly_audit.json", {"synthetic": True}
        ).resolve()
        self.authority_sha = self.audit_sha = audit.sha(self.audit_path)
        self.completed_months = self.completed = set(
            audit.prior_months("202601") + ["202601"]
        )
        self.used = {str(self.audit_path): self.audit_sha}
        self.base_used = dict(self.used)
        self.seal = audit.Seal()
        self.allowed = {}
        items = []
        for month in sorted(self.completed):
            stamp = month + "02"
            for ticker in audit.TICKERS:
                path = self.session / ticker / stamp
                path.mkdir(parents=True)
                actions, labels = self.frames()
                actions.to_parquet(path / "actions.parquet", index=False)
                labels.to_parquet(path / "labels.parquet", index=False)
                items.append(
                    dict(
                        ticker=ticker,
                        date=stamp,
                        status="COMPLETE",
                        close_i=210 if month == "202507" else 390,
                        day_root=str(path),
                        actions_sha256=audit.sha(path / "actions.parquet"),
                        labels_sha256=audit.sha(path / "labels.parquet"),
                    )
                )
        self.index = pd.DataFrame(items).set_index(["ticker", "date"])
        # Controls are written with the frozen producer, never the auditor's replay.
        import evaluate_oof_calibrated_policy as producer

        for mode in audit.MODES:
            for ticker in audit.TICKERS:
                stamp = "20260102"
                selected = self.selection(mode, ticker, stamp)
                labels = self.table(ticker, stamp, "labels")
                lookup = {r["action_id"]: r for r in labels.to_dict("records")}
                result = producer.replay(
                    selected["selected"], selected["close_i"], lambda i: lookup[i]
                )
                prefix = self.root / "ledgers" / "202601" / mode / ticker / stamp
                prefix.parent.mkdir(parents=True, exist_ok=True)
                for suffix, values in (
                    ("_attempts", result["attempts"]),
                    ("_ledger", result["ledger"]),
                ):
                    destination = Path(str(prefix) + suffix + ".parquet")
                    pd.DataFrame(values, columns=audit.FIELDS).to_parquet(
                        destination, index=False
                    )
                    self.allowed[str(destination)] = audit.sha(destination)
        self.used = dict(self.base_used)

    @staticmethod
    def frames():
        actions = pd.DataFrame(
            dict(action_id=[1, 2, 3], state_i=[60, 61, 63], entry_i=[61, 62, 64])
        )
        labels = pd.DataFrame(
            dict(
                action_id=[1, 2, 3],
                status=["FILLED", "NO_FILL", "FILLED"],
                exit_i=[62, 62, 65],
                net_base=[-5.6, 0.0, 15.4],
                net_adverse=[-7.6, 0.0, 13.4],
                entry_ask=[1.0, np.nan, 1.0],
                exit_bid=[0.99, np.nan, 1.2],
                reason=["STOP", "NO_FILL", "TARGET"],
                hold_minutes=[1, 0, 1],
            )
        )
        return actions, labels

    def rows(self, month):
        return self.month_rows(month)

    def month_rows(self, month):
        return self.index.loc[
            self.index.index.get_level_values("date").str.startswith(month)
        ]

    def fit(self, mode, month):
        _, stop, key = audit.fit_window(mode, month)
        return dict(
            fit_key=key,
            fit_stop_at=stop.isoformat(),
            model_sha256="a" * 64,
            scales={t: 10.0 for t in audit.TICKERS},
        )

    def table(self, ticker, day, kind):
        value = self.index.loc[(ticker, day)]
        path = Path(value.day_root) / (kind + ".parquet")
        self.used[str(path)] = value[kind + "_sha256"]
        self.seal.verify(path, value[kind + "_sha256"])
        return pd.read_parquet(path)

    def source_table(self, ticker, day, kind, columns):
        return self.table(ticker, day, kind)[columns], self.index.loc[(ticker, day)][
            kind + "_sha256"
        ]

    def selection(self, mode, ticker, day):
        # This boundary supplies the same base scores to each implementation.
        self.table(ticker, day, "actions")
        close = int(self.index.loc[(ticker, day)].close_i)
        return dict(
            version=audit.VERSION,
            procedure=mode,
            ticker=ticker,
            day=day,
            close_i=close,
            fit_stop_at=self.fit(mode, day[:6])["fit_stop_at"],
            model_sha256="a" * 64,
            prediction_sha256="b" * 64,
            selected=audit.maxima([1, 2, 3], [60, 61, 63], [1.0, 2.0, -1.0], close),
            outcomes_read=False,
        )

    def select_day(self, mode, ticker, day, output):
        import monthly_oof_calibration_adapter as adapter

        # Generate the producer maximum independently of the audit implementation.
        self.table(ticker, day, "actions")
        selected = adapter.core.maximum_selection(
            procedure=mode,
            ticker=ticker,
            day=day,
            close_i=int(self.index.loc[(ticker, day)].close_i),
            fit_stop_at=self.fit(mode, day[:6])["fit_stop_at"],
            model_sha256="a" * 64,
            prediction_sha256="b" * 64,
            actions=[
                dict(action_id=i, state_i=s, score_usd=v)
                for i, s, v in [(1, 60, 1.0), (2, 61, 2.0), (3, 63, -1.0)]
            ],
        )
        path = Path(output) / mode / "selections" / ticker / (day + ".json")
        digest = adapter.publish_or_verify(path, selected)
        return dict(
            procedure=mode,
            ticker=ticker,
            day=day,
            source_status="COMPLETE",
            selection_path=str(path),
            selection_sha256=digest,
        )

    def realize_past_day(self, entry, target_month):
        import monthly_oof_calibration_adapter as adapter

        selection = adapter.core.load_seal(
            entry["selection_path"], entry["selection_sha256"]
        )
        labels, digest = self.source_table(
            entry["ticker"], entry["day"], "labels", ["action_id", "status", "net_base"]
        )
        return adapter.core.realized_maxima(
            entry["selection_path"],
            entry["selection_sha256"],
            lambda: labels.to_dict("records"),
            labels_sha256=digest,
            outcome_available_at=(
                adapter.core.session_close(selection) + timedelta(minutes=1)
            ).isoformat(),
            availability_semantics="DECLARED_NYSE_CLOSE_PLUS_ONE_MINUTE_NOT_OBSERVED_RECEIPT",
        )

    def verify(self, path):
        path = str(Path(path).resolve())
        assert audit.sha(path) == self.allowed[path]
        self.used[path] = self.allowed[path]

    def marker(self, name, paths):
        for path in paths:
            self.verify(path)

    def controls(self, mode, ticker, day):
        prefix = self.root / "ledgers" / day[:6] / mode / ticker / day
        result = []
        for suffix in ("_attempts", "_ledger"):
            path = Path(str(prefix) + suffix + ".parquet")
            self.verify(path)
            result.append(pd.read_parquet(path).to_dict("records"))
        return result

    def recheck(self):
        for path, digest in self.used.items():
            assert audit.sha(path) == digest


@pytest.fixture(scope="module")
def integrated_fixture(tmp_path_factory):
    import monthly_oof_calibration_adapter as adapter
    import evaluate_oof_calibrated_policy as evaluator

    root = tmp_path_factory.mktemp("oof_synthetic_integration")
    source = TinySource(root)
    correction, evaluation = root / "correction", root / "evaluation"
    adapter.prepare_correction(source, "202601", correction)
    source.used = dict(source.base_used)
    evaluator.evaluate_month(
        source,
        correction,
        "202601",
        evaluation,
        correction_completion_sha256=audit.sha(correction / "202601.complete.json"),
    )
    source.used = dict(source.base_used)
    source.seal = audit.Seal()
    result = audit.audit_month(
        source,
        correction,
        "202601",
        evaluation,
        audit.sha(correction / "202601.complete.json"),
        audit.sha(evaluation / "completion.json"),
    )
    return root, source, correction, evaluation, result


def test_integrated_adapter_offsets_replay_and_no_policy_selection(integrated_fixture):
    _, source, _, _, result = integrated_fixture
    source.seal.recheck()
    assert result["controls_verified"] == 9
    assert set(result["policies"]) == set(audit.POLICIES)
    assert result["historical_maxima"] == 324
    # Offset is the mean of [-6.6,-2,16.4], with no outcome-dependent selection.
    assert result["offsets_usd"]["static"]["SPY"] == pytest.approx(2.6)
    assert result["policies"]["static__control"]["observed"][
        "net_base"
    ] == pytest.approx(-16.8)
    assert result["policies"]["static__corrected"]["observed"][
        "net_base"
    ] == pytest.approx(29.4)
    report = audit.combined_reports([result])
    assert (
        report["static__corrected"]["economic_gate_status"]
        == "NOT_EVALUATED_INCOMPLETE_H1"
    )


def test_integrated_request_closure_and_incomplete_scope(
    tmp_path, monkeypatch, integrated_fixture
):
    _, source, correction, evaluation, _ = integrated_fixture
    source.seal = audit.Seal()
    request = dict(
        version="OOF_ECONOMIC_AUDIT_REQUEST_V1",
        scope="MONTHS",
        monthly_root=str(source.root),
        monthly_audit=str(source.audit_path),
        monthly_audit_sha256=source.audit_sha,
        session_root=str(source.session),
        session_audit=str(source.audit_path),
        correction_root=str(correction),
        months=[
            dict(
                month="202601",
                correction_completion_sha256=audit.sha(
                    correction / "202601.complete.json"
                ),
                evaluation_root=str(evaluation),
                evaluation_completion_sha256=audit.sha(evaluation / "completion.json"),
            )
        ],
    )
    path = write(tmp_path / "request.json", request)

    def boundary(_request, seal):
        source.seal = seal
        return source

    monkeypatch.setattr(audit, "Monthly", boundary)
    result = audit.audit(path, audit.sha(path))
    assert result["status"] == "PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_DECLARED_MONTHS"
    assert result["winner_selected"] is None and not result["promotion_approved"]
    request["scope"] = "FULL_H1"
    write(path, request)
    with pytest.raises(ValueError, match="Six months"):
        audit.audit(path, audit.sha(path))


def test_main_wrong_external_hash_has_no_success(tmp_path, monkeypatch):
    path = write(tmp_path / "request.json", {"version": "wrong"})
    monkeypatch.setattr(audit, "resource_gate", lambda: {"synthetic": True})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit",
            "--request",
            str(path),
            "--request-sha256",
            "0" * 64,
            "--output",
            str(tmp_path / "out"),
        ],
    )
    with pytest.raises(ValueError, match="External request"):
        audit.main()
    assert not (tmp_path / "out/audit.json").exists()


def test_monthly_constructor_rejects_wrong_authority_before_sources(tmp_path):
    path = write(tmp_path / "authority.json", {"status": "IMPLEMENTATION_REVIEW_ONLY"})
    request = dict(
        monthly_root=str(tmp_path / "monthly"),
        session_root=str(tmp_path / "session"),
        monthly_audit=str(path),
        monthly_audit_sha256=audit.sha(path),
    )
    with pytest.raises(ValueError, match="outputs audit"):
        audit.Monthly(request, audit.Seal())


def test_source_module_has_no_producer_imports():
    import ast

    tree = ast.parse(Path(audit.__file__).read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(v.name for v in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module)
    assert not set(imports) & set(
        name.removesuffix(".py") for name in audit.PRODUCER_PINS
    )


@contextmanager
def restored(path):
    contents, stat = path.read_bytes(), path.stat()
    try:
        yield
    finally:
        path.write_bytes(contents)
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))


@pytest.mark.parametrize(
    "fault",
    ["input_omission", "offset", "future_record", "score_omission", "control_omission"],
)
def test_integrated_closed_artifact_faults(integrated_fixture, fault):
    _, source, correction, evaluation, _ = integrated_fixture
    complete_path = evaluation / "completion.json"
    if fault in ("score_omission", "control_omission"):
        record = json.loads(complete_path.read_text())
        group = "files" if fault == "score_omission" else "monthly_files"
        needle = "/scores/" if fault == "score_omission" else "_attempts.parquet"
        omitted = next(
            name for name in record[group] if needle in name.replace("\\", "/")
        )
        del record[group][omitted]
        with restored(complete_path):
            write(complete_path, record)
            source.seal = audit.Seal()
            with pytest.raises(ValueError, match="Missing consumed"):
                audit.audit_month(
                    source,
                    correction,
                    "202601",
                    evaluation,
                    audit.sha(correction / "202601.complete.json"),
                    audit.sha(complete_path),
                )
    else:
        path = (
            correction / "202601.inputs.json"
            if fault == "input_omission"
            else (
                correction / "static/202601/calibration.json"
                if fault == "offset"
                else correction / "static/realized/SPY/20250102.json"
            )
        )
        record = json.loads(path.read_text())
        if fault == "input_omission":
            del record["files"][
                next(
                    name for name in record["files"] if name.endswith("labels.parquet")
                )
            ]
        elif fault == "offset":
            record["offsets_usd"]["SPY"] += 1
        else:
            record["outcome_available_at"] = "2026-01-01T00:00:00-05:00"
        with restored(path):
            write(path, record)
            source.seal = audit.Seal()
            with pytest.raises(ValueError):
                audit.audit_month(
                    source,
                    correction,
                    "202601",
                    evaluation,
                    audit.sha(correction / "202601.complete.json"),
                    audit.sha(complete_path),
                )


def strict_monthly_fixture(tmp_path, fault):
    # Existing fixture creates a complete 2625-row source index but only one day's
    # tiny arrays. Extend its source authority fields, without reading market data.
    from test_monthly_oof_calibration_adapter import fixture

    producer_source, authority_path, prediction = fixture(
        tmp_path, bad_cutoff=fault == "cutoff", missing_member=fault == "member"
    )
    root, session = producer_source.root, producer_source.session_root
    source_path = tmp_path / "session_audit.json"
    source_audit = json.loads(source_path.read_text())
    source_audit["binding"]["feature_root"] = str(session)
    for filename, key in (
        ("completion.json", "completion_sha256"),
        ("dataset_contract.json", "dataset_contract_sha256"),
        ("feature_contract.json", "feature_contract_sha256"),
    ):
        path = write(session / filename, {"synthetic": True})
        source_audit["binding"][key] = audit.sha(path)
    write(source_path, source_audit)
    contract_path = root / "run_contract.json"
    contract = json.loads(contract_path.read_text())
    contract["source_audit"]["sha256"] = audit.sha(source_path)
    write(contract_path, contract)
    binding = audit.sha(contract_path)
    for path in root.rglob("*.fit_started.json"):
        record = json.loads(path.read_text())
        record["binding"] = binding
        write(path, record)
    if fault in ("scale", "dtype", "shape"):
        with np.load(prediction) as data:
            values = {name: data[name] for name in data.files}
        if fault == "scale":
            values["scale"] = np.array(999.0)
        elif fault == "dtype":
            values["scores"] = values["scores"].astype(np.float32)
        else:
            values["scores"] = values["scores"].reshape(-1, 1)
        np.savez(prediction, **values)
    for _ in range(3):
        for path in root.rglob("*.complete.json"):
            record = json.loads(path.read_text())
            record["binding"] = binding
            record["files"] = {name: audit.sha(root / name) for name in record["files"]}
            write(path, record)
    authority = json.loads(authority_path.read_text())
    authority["binding"]["run_contract_sha256"] = binding
    authority["binding"]["session_audit_sha256"] = audit.sha(source_path)
    authority["verified_files"] = {
        "artifacts": {
            str(p.resolve()): audit.sha(p) for p in root.rglob("*") if p.is_file()
        }
    }
    authority["verified_files"]["sources"] = {
        str(source_path.resolve()): audit.sha(source_path),
        str((session / "index.parquet").resolve()): audit.sha(
            session / "index.parquet"
        ),
    }
    write(authority_path, authority)
    return dict(
        monthly_root=str(root),
        session_root=str(session),
        monthly_audit=str(authority_path),
        monthly_audit_sha256=audit.sha(authority_path),
        session_audit=str(source_path),
    )


@pytest.mark.parametrize("fault", [None, "cutoff", "member", "scale", "dtype", "shape"])
def test_real_monthly_admission_and_projection_schema(tmp_path, fault):
    request = strict_monthly_fixture(tmp_path, fault)
    source = audit.Monthly(request, audit.Seal())
    source.rows("202501")
    if fault:
        with pytest.raises(ValueError):
            source.selection("static", "SPY", "20250102")
    else:
        selected = source.selection("static", "SPY", "20250102")
        assert [r["action_id"] for r in selected["selected"]] == [2, 1]
        assert not any(name.endswith("labels.parquet") for name in source.used)
        source.seal.recheck()


def test_full_period_gate_is_per_ticker_not_pooled():
    months = []
    for month in audit.MONTHS:
        policies = {}
        for policy in audit.POLICIES:
            daily = []
            tickers = {}
            for ticker in audit.TICKERS:
                net = -1.0 if ticker == "QQQ" else 100.0
                ledger = [
                    {"net_base": net, "net_adverse": net - 1.0} for _ in range(10)
                ]
                row = dict(
                    ticker=ticker,
                    date=month + "02",
                    source_status="COMPLETE",
                    **audit.metrics(ledger),
                )
                daily.append(row)
                tickers[ticker] = {"observed": audit.metrics(ledger)}
            policies[policy] = {"daily": daily, "by_ticker": tickers}
        months.append({"target_month": month, "policies": policies})
    result = audit.combined_reports(months)
    assert result["static__control"]["economic_gate_status"] == "FAIL"
    assert (
        result["static__control"]["by_ticker"]["SPY"]["economic_gate_status"] == "PASS"
    )
    assert (
        result["static__control"]["by_ticker"]["QQQ"]["economic_gate_status"] == "FAIL"
    )


@pytest.mark.parametrize("fault", [None, "score", "net_base", "net_adverse"])
def test_real_monthly_control_float64_schema(tmp_path, fault):
    request = strict_monthly_fixture(tmp_path, None)
    root = Path(request["monthly_root"])
    prefix = root / "ledgers/202501/static/SPY/20250102"
    prefix.parent.mkdir(parents=True)
    frame = pd.DataFrame(
        [
            dict(
                action_id=1,
                state_i=60,
                score=1.0,
                has_filled_before=0,
                status="FILLED",
                exit_i=62,
                net_base=2.0,
                net_adverse=0.0,
            )
        ]
    )
    if fault:
        frame[fault] = frame[fault].astype(np.float32)
    files = {}
    for suffix in ("_attempts.parquet", "_ledger.parquet"):
        path = Path(str(prefix) + suffix)
        frame.to_parquet(path, index=False)
        files[str(path.relative_to(root))] = audit.sha(path)
    write(
        Path(str(prefix) + ".complete.json"),
        dict(
            status="COMPLETE",
            binding=audit.sha(root / "run_contract.json"),
            files=files,
        ),
    )
    authority_path = Path(request["monthly_audit"])
    authority = json.loads(authority_path.read_text())
    authority["verified_files"]["artifacts"].update(
        {str(p.resolve()): audit.sha(p) for p in prefix.parent.iterdir()}
    )
    write(authority_path, authority)
    request["monthly_audit_sha256"] = audit.sha(authority_path)
    source = audit.Monthly(request, audit.Seal())
    if fault:
        with pytest.raises(ValueError, match="float64"):
            source.controls("static", "SPY", "20250102")
    else:
        attempts, ledger = source.controls("static", "SPY", "20250102")
        assert attempts == ledger == frame.to_dict("records")
