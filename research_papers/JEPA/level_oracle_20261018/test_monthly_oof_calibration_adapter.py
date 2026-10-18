"""Synthetic files only; no monthly output or market calibration is consumed."""

from datetime import date
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import monthly_oof_calibration_adapter as adapter


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture(tmp_path, *, bad_cutoff=False, missing_member=False):
    root, session = tmp_path / "monthly", tmp_path / "session"
    root.mkdir(parents=True)
    session.mkdir(parents=True)
    import exchange_calendars as xc

    calendar = xc.get_calendar("XNYS").schedule.loc["2023-01-03":"2026-06-30"]
    rows = []
    for ticker in adapter.core.TICKERS:
        for stamp, row in calendar.iterrows():
            day = stamp.strftime("%Y%m%d")
            missing = ticker in ("SPY", "QQQ") and day in (
                "20260401",
                "20260409",
                "20260415",
            )
            rows.append(
                dict(
                    ticker=ticker,
                    date=day,
                    status="MISSING_SOURCE" if missing else "COMPLETE",
                    close_i=int((row.close - row.open).total_seconds() / 60),
                    day_root=str(session / ticker / day),
                    actions_sha256="a" * 64,
                    labels_sha256="b" * 64,
                )
            )
    actions = pd.DataFrame(dict(action_id=[2, 1], state_i=[60, 61]))
    labels = pd.DataFrame(
        dict(action_id=[2, 1], status=["NO_FILL", "FILLED"], net_base=[0.0, 5.0])
    )
    dayroot = session / "SPY" / "20250102"
    dayroot.mkdir(parents=True)
    actions.to_parquet(dayroot / "actions.parquet", index=False)
    labels.to_parquet(dayroot / "labels.parquet", index=False)
    for row in rows:
        if (row["ticker"], row["date"]) == ("SPY", "20250102"):
            row["actions_sha256"] = adapter.core.file_sha(dayroot / "actions.parquet")
            row["labels_sha256"] = adapter.core.file_sha(dayroot / "labels.parquet")
    pd.DataFrame(rows).to_parquet(session / "index.parquet", index=False)
    indexsha = adapter.core.file_sha(session / "index.parquet")
    source_audit = tmp_path / "session_audit.json"
    write_json(
        source_audit,
        dict(
            status="PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT",
            binding=dict(
                engine_root=str(session),
                index_sha256=indexsha,
                available_days=2619,
                missing_days=6,
            ),
        ),
    )
    config = dict(n_estimators=200)
    write_json(
        root / "run_contract.json",
        dict(
            version="MONTHLY_NET_WALK_FORWARD_V1",
            features=1954,
            threshold_usd=0,
            engine_root=str(session),
            source_audit=dict(sha256=adapter.core.file_sha(source_audit)),
            config=config,
        ),
    )
    binding = adapter.core.file_sha(root / "run_contract.json")

    def marker(name, paths, extra=None):
        write_json(
            root / (name + ".complete.json"),
            dict(
                status="COMPLETE",
                binding=binding,
                files={
                    str(p.relative_to(root)): adapter.core.file_sha(p) for p in paths
                },
                extra=extra or {},
            ),
        )

    fold = adapter.schedule.Fold(
        "expanding", date(2025, 1, 1), date(2023, 1, 1), date(2025, 1, 1)
    )
    key = fold.fit_key
    info = root / ("fits/" + key + "/inputs.json")
    write_json(
        info,
        dict(
            fit_key=key,
            train_start="2023-01-01",
            train_stop_exclusive="2025-02-01" if bad_cutoff else "2025-01-01",
            config=config,
            rows=2,
            scales=dict(SPY=81.0, SPXW=680.0, QQQ=88.0),
        ),
    )
    marker("fits/" + key + "/inputs", [info])
    model = root / ("models/" + key + ".txt")
    model.parent.mkdir(parents=True)
    model.write_bytes(b"synthetic model bytes, never inferred")
    started = root / ("models/" + key + ".fit_started.json")
    write_json(started, dict(binding=binding, config=config, shape=[2, 1954]))
    marker("models/" + key, [model, started])
    predname = "predictions/202501/" + key + "/SPY/20250102"
    prediction = root / (predname + ".npz")
    prediction.parent.mkdir(parents=True)
    np.savez(
        prediction,
        action_id=np.array([2, 1]),
        state_i=np.array([60, 61]),
        scores=np.array([2.0, 1.0]),
        model_sha256=np.array(adapter.core.file_sha(model)),
        scale=np.array(81.0),
    )
    marker(predname, [] if missing_member else [prediction])
    marker("months/202501/predictions", [prediction], dict(labels_read=False))
    daily = root / "months/202501/daily.json"
    write_json(daily, {"not_parsed_economics": 123})
    marker(
        "months/202501/daily", [daily, root / "months/202501/predictions.complete.json"]
    )
    verified = {
        str(p.resolve()): adapter.core.file_sha(p)
        for p in root.rglob("*")
        if p.is_file()
    }
    verified.update(
        {
            str(source_audit.resolve()): adapter.core.file_sha(source_audit),
            str((session / "index.parquet").resolve()): indexsha,
        }
    )
    audit = tmp_path / "monthly_audit.json"
    write_json(
        audit,
        dict(
            status=adapter.STATUS,
            binding=dict(
                monthly_root=str(root),
                session_root=str(session),
                run_contract_sha256=binding,
                session_audit_sha256=adapter.core.file_sha(source_audit),
                index_sha256=indexsha,
                completed_months=["202501"],
            ),
            verified_files=dict(artifacts=verified),
        ),
    )
    source = adapter.MonthlyInputs(
        root, audit, adapter.core.file_sha(audit), session, source_audit
    )
    return source, audit, prediction


def test_authenticated_projection_selection_before_labels_and_no_fill(tmp_path):
    source, _, _ = fixture(tmp_path)
    selected = source.select_day("expanding", "SPY", "20250102", tmp_path / "output")
    assert Path(selected["selection_path"]).exists()
    assert not any(p.endswith("labels.parquet") for p in source.used)
    record = source.realize_past_day(selected, "202601")
    assert (
        record["rows"][0]["status"] == "NO_FILL" and record["rows"][0]["net_base"] == 0
    )
    assert record["outcome_available_at"] == "2025-01-02T16:01:00-05:00"
    assert any(p.endswith("labels.parquet") for p in source.used)
    source.recheck()
    with pytest.raises(ValueError, match="Only past"):
        source.realize_past_day(selected, "202501")


def test_claimed_cutoff_and_omitted_marker_member_rejected(tmp_path):
    source, _, _ = fixture(tmp_path / "cutoff", bad_cutoff=True)
    with pytest.raises(ValueError, match="window differs"):
        source.select_day("expanding", "SPY", "20250102", tmp_path / "out1")
    source, _, _ = fixture(tmp_path / "member", missing_member=True)
    with pytest.raises(ValueError, match="omits consumed"):
        source.select_day("expanding", "SPY", "20250102", tmp_path / "out2")


def test_audit_and_prediction_mutations_and_incomplete_history(tmp_path):
    source, audit, prediction = fixture(tmp_path)
    with pytest.raises(ValueError, match="coverage incomplete"):
        adapter.prepare_correction(source, "202601", tmp_path / "out")
    prediction.write_bytes(b"changed but producer filenames unchanged")
    with pytest.raises(ValueError, match="Changed audited"):
        source.select_day("expanding", "SPY", "20250102", tmp_path / "out")
    audit.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="Consumed source changed"):
        source.recheck()


def test_verified_hash_conflict_relative_path_and_overwrite_rejected(tmp_path):
    path = str((tmp_path / "file").resolve())
    with pytest.raises(ValueError, match="Conflicting"):
        adapter.flatten_verified(dict(a={path: "a" * 64}, b={path: "b" * 64}))
    with pytest.raises(ValueError, match="absolute"):
        adapter.flatten_verified(dict(a={"relative": "a" * 64}))
    output = tmp_path / "published.json"
    digest = adapter.publish_or_verify(output, dict(expected=1))
    assert adapter.publish_or_verify(output, dict(expected=1)) == digest
    with pytest.raises(ValueError, match="hash differs"):
        adapter.publish_or_verify(output, dict(expected=2))


class ToySource:
    """Small orchestration double, not an alternative source-admission route."""

    def __init__(self, tmp_path):
        self.root = tmp_path / "monthly"
        self.session_root = tmp_path / "session"
        self.authority_sha = "a" * 64
        self.completed_months = {f"2025{m:02d}" for m in range(1, 13)} | {"202601"}
        self.labels = []
        self.used = {}

    def month_rows(self, month):
        return pd.DataFrame(
            index=pd.MultiIndex.from_tuples(
                [(t, month + "02") for t in adapter.core.TICKERS],
                names=["ticker", "date"],
            )
        )

    def fit(self, procedure, month):
        return dict(
            scales=dict(SPY=81.0, SPXW=680.0, QQQ=88.0),
            fit_stop_at="2025-01-01T00:00:00-05:00",
        )

    def select_day(self, procedure, ticker, stamp, output):
        selected = adapter.core.maximum_selection(
            procedure=procedure,
            ticker=ticker,
            day=stamp,
            close_i=390,
            fit_stop_at=self.fit(procedure, stamp[:6])["fit_stop_at"],
            model_sha256="a" * 64,
            prediction_sha256="b" * 64,
            actions=[dict(action_id=1, state_i=60, score_usd=2.0)],
        )
        path = Path(output) / procedure / "selections" / ticker / (stamp + ".json")
        digest = adapter.publish_or_verify(path, selected)
        return dict(
            procedure=procedure,
            ticker=ticker,
            day=stamp,
            source_status="COMPLETE",
            selection_path=str(path),
            selection_sha256=digest,
        )

    def realize_past_day(self, selected, target_month):
        assert selected["day"][:6] < target_month
        self.labels.append(selected["day"])
        selection = adapter.core.load_seal(
            selected["selection_path"], selected["selection_sha256"]
        )
        return adapter.core.realized_maxima(
            selected["selection_path"],
            selected["selection_sha256"],
            lambda: [dict(action_id=1, status="FILLED", net_base=1.0)],
            labels_sha256="c" * 64,
            outcome_available_at=(
                adapter.core.session_close(selection) + adapter.timedelta(minutes=1)
            ).isoformat(),
            availability_semantics="SYNTHETIC_EOD_NOT_RECEIPT",
        )

    def recheck(self):
        pass


def test_prepare_three_separate_calibrators_never_target_labels_resume_exact(tmp_path):
    source = ToySource(tmp_path)
    output = tmp_path / "calibration"
    result = adapter.prepare_correction(source, "202601", output)
    assert len(source.labels) == 108 and all(
        d.startswith("2025") for d in source.labels
    )
    assert (
        not result["target_labels_read"]
        and not result["base_models_refitted"]
        and result["winner_selected"] is None
    )
    for mode in adapter.core.PROCEDURES:
        record = result["procedures"][mode]
        assert (
            len(record["history_calendar"]) == 36
            and len(record["target_calendar"]) == 3
        )
        saved = json.loads(Path(record["target_calendar"][0]["score_path"]).read_text())
        assert saved["rows"][0]["corrected_score_usd"] == 1.0
    assert adapter.prepare_correction(source, "202601", output) == result
    score = Path(result["procedures"]["static"]["target_calendar"][0]["score_path"])
    mutated = json.loads(score.read_text())
    mutated["ticker"] = "WRONG"
    score.write_text(json.dumps(mutated), encoding="utf-8")
    with pytest.raises(ValueError, match="hash differs"):
        adapter.prepare_correction(source, "202601", output)


def test_exclusive_writer_and_changed_implementation_resume(tmp_path, monkeypatch):
    output = tmp_path / "calibration"
    with adapter.output_lock(output):
        with pytest.raises(OSError):
            with adapter.output_lock(output):
                pytest.fail("second writer must not enter")
    source = ToySource(tmp_path)
    adapter.prepare_correction(source, "202601", output)
    calls = len(source.labels)
    original = adapter.dependency_hashes
    monkeypatch.setattr(
        adapter,
        "dependency_hashes",
        lambda: {**original(), "oof_maximum_calibration.py": "0" * 64},
    )
    with pytest.raises(ValueError, match="hash differs"):
        adapter.prepare_correction(source, "202601", output)
    assert len(source.labels) == calls


def test_invalid_month_rejected_before_any_output_write(tmp_path):
    source = ToySource(tmp_path)
    output = tmp_path / "not_created"
    for month in ("../escape", "202501", "202607"):
        with pytest.raises(ValueError):
            adapter.prepare_correction(source, month, output)
        assert not output.exists()
