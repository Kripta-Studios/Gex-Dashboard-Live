"""Synthetic faults for the independent full/short calendar auditor."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import audit_tcn_row_mixed_calendar as audit


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def seal(paths):
    return {str(path.resolve()): audit.sha(path) for path in paths}


def action_labels(close=210):
    actions = pd.DataFrame(
        {"action_id": [1, 2], "state_i": [60, close - 15], "entry_i": [61, close - 14]}
    )
    labels = pd.DataFrame(
        {
            "action_id": [1, 2],
            "status": ["FILLED", "NO_FILL"],
            "exit_i": [close - 5, close - 14],
            "reason": ["EOD", "NO_FILL"],
            "entry_ask": [1.0, np.nan],
            "exit_bid": [1.2, np.nan],
            "hold_minutes": [close - 66, 0],
            "net_base": [15.4, 0.0],
            "net_adverse": [13.4, 0.0],
        }
    )
    return actions, labels


@pytest.mark.parametrize("close", [210, 390])
def test_explicit_session_and_cost_reconstruction(close):
    actions, labels = action_labels(close)
    audit.validate_day(actions, labels, close)
    labels.loc[0, "exit_i"] = close - 4
    with pytest.raises(AssertionError, match="Exit outside"):
        audit.validate_day(actions, labels, close)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("net_base", 16.4, "Net cost"),
        ("hold_minutes", 999, "Hold clock"),
        ("reason", "FREE_EXIT", "Exit reason"),
        ("entry_ask", 0.0, "Executable quote"),
    ],
)
def test_payoff_contract_faults(field, value, match):
    actions, labels = action_labels()
    labels.loc[0, field] = value
    with pytest.raises(AssertionError, match=match):
        audit.validate_day(actions, labels, 210)


def test_missing_day_never_becomes_cash_success():
    frame = pd.DataFrame({"ticker": ["SPXW", "SPY"], "date": ["20260401"] * 2})
    gate, coverage = audit.independent.daily_gate(
        frame, ["20260401"], {("SPXW", "20260401")}
    )
    assert gate["no_evaluable_days"] == 2 and gate["passes"] is False
    assert set(coverage.loc[coverage.status == "NO_EVALUABLE", "ticker"]) == {
        "SPY",
        "QQQ",
    }


@pytest.mark.parametrize("right", [np.array([0.0]), np.array([-0.0], np.float32)])
def test_float_identity_preserves_signed_zero_and_dtype(right):
    with pytest.raises(AssertionError, match="byte identity"):
        audit.exact(np.array([-0.0]), right, "control")


def test_membership_and_end_rehash_are_both_required(tmp_path):
    path = tmp_path / "source"
    path.write_bytes(b"sealed")
    evidence = audit.Seal()
    with pytest.raises(AssertionError, match="Unbound consumed"):
        evidence.member({}, path)
    evidence.member(seal([path]), path)
    path.write_bytes(b"mutated after initial hash")
    with pytest.raises(AssertionError, match="changed during"):
        evidence.recheck()


def calendar_fixture():
    schedule = audit.xc.get_calendar("XNYS").schedule.loc["2025-01-01":"2026-06-30"]
    rows = []
    for day, item in schedule.iterrows():
        for ticker in audit.independent.TICKERS:
            date = day.strftime("%Y%m%d")
            rows.append(
                dict(
                    ticker=ticker,
                    date=date,
                    close_i=int((item.close - item.open).total_seconds() / 60),
                    status="MISSING_SOURCE"
                    if (ticker, date) in audit.MISSING
                    else "COMPLETE",
                )
            )
    index = pd.DataFrame(rows)
    record = {}
    for period, lower, upper, expected, available in audit.PERIODS:
        part = index.loc[(index.date >= lower) & (index.date < upper)]
        record[period] = dict(
            expected=expected,
            available=available,
            days=[
                dict(
                    ticker=r.ticker,
                    date=r.date,
                    status=r.status,
                    clock=dict(
                        close_i=r.close_i,
                        n_slots=r.close_i + 1,
                        first_state=60,
                        last_state=r.close_i - 15,
                        eod_i=r.close_i - 5,
                        time_unit_minutes=390,
                    ),
                )
                for r in part.itertuples(index=False)
            ],
        )
    return index, record


def test_calendar_full_750_369_including_short_and_missing():
    index, record = calendar_fixture()
    assert len(audit.validate_calendar(index, record)) == 373
    assert len(index.loc[index.close_i == 210]) == 9
    index.loc[index.status == "MISSING_SOURCE", "status"] = "COMPLETE"
    with pytest.raises(AssertionError, match="Fixed missing"):
        audit.validate_calendar(index, record)


def test_calendar_cannot_drop_short_or_duplicate_days():
    index, record = calendar_fixture()
    with pytest.raises(AssertionError, match="NYSE calendar universe"):
        audit.validate_calendar(index.loc[index.close_i != 210], record)
    with pytest.raises(AssertionError, match="Duplicate calendar"):
        audit.validate_calendar(pd.concat([index, index.iloc[:1]]), record)


def test_freeze_precedes_every_test_artifact(tmp_path):
    freeze_file = write(tmp_path / "freeze.json", {})
    test = write(tmp_path / "control_calendar/test/day.json", {})
    os.utime(freeze_file, (1000, 1000))
    os.utime(test, (1001, 1001))
    freeze = dict(
        test_evaluated=False,
        expected_validation_days=750,
        files={},
        frozen_at_utc=datetime.fromtimestamp(1000, timezone.utc).isoformat(),
    )
    audit.require_chronology(tmp_path, freeze)
    os.utime(test, (999, 999))
    with pytest.raises(AssertionError, match="predates freeze"):
        audit.require_chronology(tmp_path, freeze)


def control_fixture(tmp_path, short=False):
    root, flags = tmp_path / "run", tmp_path / "flags"
    day = "20250703" if short else "20250102"
    name = "SPY_" + day
    period = "validation"
    day_root = tmp_path / "sources" / "SPY" / day
    day_root.mkdir(parents=True)
    actions, labels = action_labels(210 if short else 390)
    actions.to_parquet(day_root / "actions.parquet", index=False)
    labels.to_parquet(day_root / "labels.parquet", index=False)
    row = dict(
        ticker="SPY",
        date=day,
        close_i=210 if short else 390,
        status="COMPLETE",
        day_root=str(day_root),
        actions_sha256=audit.sha(day_root / "actions.parquet"),
        labels_sha256=audit.sha(day_root / "labels.parquet"),
    )
    paths = [day_root / "actions.parquet", day_root / "labels.parquet"]
    for field, hash_field in (
        ("features_path", "features_sha256"),
        ("features_meta_path", "features_meta_sha256"),
        ("action_features_path", "action_features_sha256"),
        ("action_features_meta_path", "action_features_meta_sha256"),
    ):
        path = day_root / field
        path.write_bytes(b"synthetic features")
        paths.append(path)
        row[field], row[hash_field] = str(path), audit.sha(path)
    external = seal(paths)
    feature_files = seal(paths[2:])
    for filename in ("tcn_control.pt", "tcn_variant.pt", "normalizers.json"):
        write(root / filename, {})
    calendar_root = root / "control_calendar" / period
    calendar_root.mkdir(parents=True)
    calendar_npz = calendar_root / (name + ".npz")
    scores, ids = np.array([-0.0, 6.0]), actions.action_id.to_numpy()
    np.savez(calendar_npz, action_ids=ids, tcn_teacher=scores)
    target = root / period
    target.mkdir()
    final = target / (name + ".npz")
    np.savez(final, action_ids=ids, control=scores, variant=scores + 1)
    if short:
        marker = write(
            calendar_npz.with_suffix(".prediction.json"),
            dict(
                files=seal(
                    [
                        calendar_npz,
                        root / "tcn_control.pt",
                        root / "normalizers.json",
                        day_root / "actions.parquet",
                    ]
                ),
                feature_files=feature_files,
                clock=dict(close_i=210),
                labels_read=False,
            ),
        )
        lineage = dict(
            kind="NEW_SHORT_INFERENCE",
            prediction_seal=str(marker),
            prediction_seal_sha256=audit.sha(marker),
        )
        adapter = dict(days={}, source_files={})
    else:
        original = flags / period / (name + ".npz")
        original.parent.mkdir(parents=True)
        np.savez(original, action_ids=ids, variant=scores)
        sidecar = write(
            original.with_suffix(".json"),
            dict(files=seal([original]), feature_files={}, oracle_files={}),
        )
        manifest = write(
            flags / period / "prediction_manifest.json",
            {sidecar.name: audit.sha(sidecar)},
        )
        adapted = root / "control_adapter" / period / original.name
        adapted.parent.mkdir(parents=True)
        np.savez(adapted, action_ids=ids, tcn_teacher=scores)
        lineage = dict(
            kind="AUDITED_FULL_COPY",
            source=str(adapted),
            source_sha256=audit.sha(adapted),
        )
        adapter = dict(
            days={original.name: {}}, source_files=seal([original, sidecar, manifest])
        )
        external.update(seal([original, sidecar, manifest]))
    write(root / "control_adapter" / period / "adapter_lineage.json", adapter)
    write(
        calendar_root / "prediction_hashes.json",
        {calendar_npz.name: audit.sha(calendar_npz)},
    )
    write(calendar_root / "lineage.json", {calendar_npz.name: lineage})
    prediction = write(
        final.with_suffix(".prediction.json"),
        dict(
            files=seal([final, calendar_npz, root / "tcn_variant.pt"]),
            feature_files=feature_files,
        ),
    )
    shards = []
    for ident in audit.independent.policies():
        shard = target / (name + "_" + ident + ".parquet")
        pd.DataFrame().to_parquet(shard)
        shards.append(shard)
    write(
        final.with_suffix(".json"),
        dict(files=seal([prediction, *shards]), feature_files={}, oracle_files={}),
    )
    return root, flags, pd.DataFrame([row]), external


@pytest.mark.parametrize("short", [False, True])
def test_control_chain_and_consumed_index_members(tmp_path, short):
    root, flags, index, external = control_fixture(tmp_path, short)
    result = audit.verify_period_inputs(
        root, flags, index, "validation", "20250101", "20260101", audit.Seal(), external
    )
    assert result["new_short_control_days"] == int(short)
    removed = str((Path(index.iloc[0].day_root) / "labels.parquet").resolve())
    del external[removed]
    with pytest.raises(AssertionError, match="Unbound consumed"):
        audit.verify_period_inputs(
            root,
            flags,
            index,
            "validation",
            "20250101",
            "20260101",
            audit.Seal(),
            external,
        )


def test_control_final_cannot_change_numerically_equal_signed_zero(tmp_path):
    root, flags, index, external = control_fixture(tmp_path)
    final = root / "validation/SPY_20250102.npz"
    with np.load(final) as data:
        ids, control, variant = (
            data[name].copy() for name in ("action_ids", "control", "variant")
        )
    control[0] = 0.0
    np.savez(final, action_ids=ids, control=control, variant=variant)
    with pytest.raises(AssertionError, match="byte identity"):
        audit.verify_control_day(
            root,
            flags,
            "validation",
            SimpleNamespace(**index.iloc[0].to_dict()),
            audit.Seal(),
            external,
        )


def test_short_new_inference_must_precede_labels(tmp_path):
    root, flags, index, external = control_fixture(tmp_path, short=True)
    marker = root / "control_calendar/validation/SPY_20250703.prediction.json"
    record = audit.read(marker)
    record["labels_read"] = True
    write(marker, record)
    lineage_path = marker.parent / "lineage.json"
    lineage = audit.read(lineage_path)
    lineage["SPY_20250703.npz"]["prediction_seal_sha256"] = audit.sha(marker)
    write(lineage_path, lineage)
    with pytest.raises(AssertionError, match="before labels"):
        audit.verify_control_day(
            root,
            flags,
            "validation",
            SimpleNamespace(**index.iloc[0].to_dict()),
            audit.Seal(),
            external,
        )


def test_atomic_publication_preserves_existing_report(tmp_path):
    path = tmp_path / "audit.json"
    audit.publish(path, {"status": "synthetic"})
    digest = audit.sha(path)
    with pytest.raises(AssertionError, match="Preserve existing"):
        audit.publish(path, {"status": "changed"})
    assert audit.sha(path) == digest


def test_full_control_requires_manifest_and_sidecar_members_even_when_adapter_omits(
    tmp_path,
):
    root, flags, index, external = control_fixture(tmp_path)
    manifest = flags / "validation/prediction_manifest.json"
    sidecar = flags / "validation/SPY_20250102.json"
    lineage_path = root / "control_adapter/validation/adapter_lineage.json"
    lineage = audit.read(lineage_path)
    for path in (manifest, sidecar):
        del external[str(path.resolve())]
        del lineage["source_files"][str(path.resolve())]
    write(lineage_path, lineage)
    with pytest.raises(AssertionError, match="Unbound consumed"):
        audit.verify_period_inputs(
            root,
            flags,
            index,
            "validation",
            "20250101",
            "20260101",
            audit.Seal(),
            external,
        )


@pytest.mark.parametrize("short", [False, True])
@pytest.mark.parametrize(
    "field",
    [
        "features_path",
        "features_meta_path",
        "action_features_path",
        "action_features_meta_path",
    ],
)
def test_prediction_seal_requires_every_feature_member(tmp_path, short, field):
    root, flags, index, external = control_fixture(tmp_path, short)
    row = SimpleNamespace(**index.iloc[0].to_dict())
    folder = root / "control_calendar/validation" if short else root / "validation"
    marker = folder / ("SPY_" + row.date + ".prediction.json")
    record = audit.read(marker)
    del record["feature_files"][str(Path(getattr(row, field)).resolve())]
    write(marker, record)
    if short:
        lineage_path = folder / "lineage.json"
        lineage = audit.read(lineage_path)
        lineage["SPY_" + row.date + ".npz"]["prediction_seal_sha256"] = audit.sha(
            marker
        )
        write(lineage_path, lineage)
    with pytest.raises(AssertionError, match="Unbound consumed"):
        audit.verify_control_day(root, flags, "validation", row, audit.Seal(), external)


def incomplete_admission(tmp_path, monkeypatch):
    root, flags, session = (tmp_path / name for name in ("run", "flags", "session"))
    for path in (
        root / "identity.json",
        root / "freeze.json",
        root / "source_inputs.json",
    ):
        write(path, {"files": {}})
    write(root / "completion.json", {"status": "INCOMPLETE", "files": {}})
    review = write(tmp_path / "review.json", {})
    session_binding = dict(engine_root=str(session))
    for filename, key in (
        ("index.parquet", "index_sha256"),
        ("dataset_contract.json", "dataset_contract_sha256"),
        ("completion.json", "completion_sha256"),
        ("feature_contract.json", "feature_contract_sha256"),
    ):
        path = write(session / filename, {"synthetic": True})
        session_binding[key] = audit.sha(path)
    session_audit = write(
        tmp_path / "session_audit.json",
        dict(
            status="PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT",
            binding=session_binding,
        ),
    )
    control_binding = dict(root=str(flags))
    for filename, key in (
        ("summary.json", "summary_sha256"),
        ("completion.json", "completion_sha256"),
        ("freeze.json", "freeze_sha256"),
        ("validation/prediction_manifest.json", "validation_manifest_sha256"),
        ("test/prediction_manifest.json", "test_manifest_sha256"),
    ):
        path = write(flags / filename, {"files": {}})
        control_binding[key] = audit.sha(path)
    control_audit = write(
        tmp_path / "control_audit.json",
        dict(
            status="PASS_INDEPENDENT_TCN_FLAGS_ECONOMIC_AUDIT", binding=control_binding
        ),
    )
    monkeypatch.setattr(audit, "SESSION_AUDIT_SHA", audit.sha(session_audit))
    monkeypatch.setattr(audit, "FLAGS_AUDIT_SHA", audit.sha(control_audit))
    return SimpleNamespace(
        root=root,
        flags_root=flags,
        session_root=session,
        review=review,
        control_audit=control_audit,
        session_audit=session_audit,
        output=tmp_path / "audit_output",
    )


def test_main_admission_rejects_incomplete_before_economics_and_preserves_failure(
    tmp_path, monkeypatch
):
    args = incomplete_admission(tmp_path, monkeypatch)
    monkeypatch.setattr(
        audit.independent,
        "audit_period",
        lambda *a, **k: pytest.fail("Economics read before producer completion"),
    )
    cli = ["audit_tcn_row_mixed_calendar.py"]
    for name, value in vars(args).items():
        cli.extend(["--" + name.replace("_", "-"), str(value)])
    monkeypatch.setattr(sys, "argv", cli)
    with pytest.raises(AssertionError, match="Incomplete producer"):
        audit.main()
    assert not (args.output / "audit.json").exists()
    failure = args.output / "audit_failure.json"
    assert audit.read(failure)["status"] == "AUDIT_FAILED"
    before = audit.sha(failure)
    with pytest.raises(FileExistsError):
        audit.main()
    assert audit.sha(failure) == before


@pytest.mark.parametrize("short", [False, True])
def test_synthetic_control_to_economic_reconstruction_and_final_summary(
    tmp_path, short
):
    root, flags, index, external = control_fixture(tmp_path, short)
    row = index.iloc[0]
    period = root / "validation"
    stem = "SPY_" + row.date
    actions, labels = action_labels(int(row.close_i))
    summaries = {}
    shards = []
    for arm in ("control", "variant"):
        scores = np.array([-0.0, 6.0]) if arm == "control" else np.array([1.0, 7.0])
        for threshold in (0, 5, 10):
            ident = f"{arm}__{threshold}"
            chosen = (
                []
                if threshold == 10
                else ([0] if arm == "variant" and threshold == 0 else [1])
            )
            # Explicit tiny trajectory: variant0 fills first and remains open until EOD;
            # other active policies attempt the second action, which cannot fill.
            attempted = actions.iloc[chosen].merge(labels.iloc[chosen], on="action_id")
            attempted["score"] = scores[chosen]
            attempted["ticker"], attempted["date"], attempted["policy"] = (
                "SPY",
                row.date,
                ident,
            )
            ledger = attempted.loc[attempted.status == "FILLED"].copy()
            shard = period / f"{stem}_{ident}.parquet"
            attempted.to_parquet(shard, index=False)
            shards.append(shard)
            attempted.to_parquet(period / f"{ident}_attempts.parquet", index=False)
            ledger.to_parquet(period / f"{ident}_ledger.parquet", index=False)
            gate, coverage = audit.independent.daily_gate(
                ledger, [row.date], {("SPY", row.date)}
            )
            coverage.to_parquet(period / f"{ident}_daily_coverage.parquet", index=False)
            summaries[ident] = {
                "daily_gate": gate,
                **audit.independent.summarize(ledger, [row.date[:6]]),
            }
    final = period / (stem + ".npz")
    marker = final.with_suffix(".prediction.json")
    daily = write(
        final.with_suffix(".json"),
        dict(
            files=seal([final, marker, *shards]),
            feature_files={},
            oracle_files=seal(
                [
                    Path(row.day_root) / "actions.parquet",
                    Path(row.day_root) / "labels.parquet",
                ]
            ),
        ),
    )
    write(period / "prediction_manifest.json", {daily.name: audit.sha(daily)})
    write(period / "summary.json", summaries)
    audit.verify_period_inputs(
        root, flags, index, "validation", "20250101", "20260101", audit.Seal(), external
    )
    rebuilt, counts = audit.independent.audit_period(
        root,
        root / "control_calendar",
        index,
        pd.Series([row.date]),
        "validation",
        "20250101",
        "20260101",
    )
    assert counts["prediction_files"] == 1 and counts["ledger_trades"] == 1
    assert rebuilt["variant__0"]["pooled"]["base_net_usd"] == pytest.approx(15.4)
    selection = audit.independent.select_validation(
        rebuilt, {t: 1.0 for t in audit.independent.TICKERS}
    )
    assert selection["selected_policy"] is None  # Two expected tickers are absent.
    freeze = write(root / "freeze.json", {"selection": selection})
    paired = {
        str(t): {
            cost + "_delta_usd": 15.4
            if cost == "base" and t == 0
            else 13.4
            if cost == "adverse" and t == 0
            else 0.0
            for cost in ("base", "adverse")
        }
        for t in (0, 5, 10)
    }
    write(
        root / "summary.json",
        dict(
            status="COMPLETE",
            development_seen=True,
            promotion_approved=False,
            control="FLAGS64",
            variant="row_mixed",
            freeze_sha256=audit.sha(freeze),
            selection=selection,
            selected_test=None,
            gate=dict(passes=False, reason="NO_VALIDATION_DAILY_COMPLIANT_POLICY"),
            test=rebuilt,
            paired_same_threshold_test=paired,
        ),
    )
    gate, _ = audit.final_summary(root, selection, rebuilt)
    assert gate["passes"] is False
    audit.publish(
        tmp_path / "synthetic_closure.json",
        dict(status="SYNTHETIC_ONLY", gate=gate, counts=counts),
    )
