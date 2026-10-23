from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import evaluate_tcn_row_mixed_calendar as module
from session_clock import SessionClock
from test_evaluate_tcn_row_mixed import make_control


@pytest.mark.parametrize("close", [210, 390])
def test_explicit_clock_rejects_late_actions_and_exits(close):
    clock = SessionClock(close)
    actions = pd.DataFrame({"action_id": [1, 2], "state_i": [60, clock.last_state]})
    labels = pd.DataFrame(
        {
            "action_id": [1, 2],
            "status": ["FILLED", "NO_FILL"],
            "exit_i": [clock.eod_i, -1],
        }
    )
    module.validate_actions(actions, clock)
    module.validate_labels(labels, clock)
    actions.loc[1, "state_i"] += 1
    with pytest.raises(ValueError, match="session clock"):
        module.validate_actions(actions, clock)
    labels.loc[0, "exit_i"] += 1
    with pytest.raises(ValueError, match="session EOD"):
        module.validate_labels(labels, clock)


def test_exact_score_dtype_bits_and_mutation(tmp_path):
    path = tmp_path / "scores.npz"
    ids = np.array([4, 1], np.int64)
    scores = np.array([-0.0, np.nextafter(1.0, 2.0)], np.float64)
    module.save_scores(path, ids, scores)
    before = module.flags.sha(path)
    module.save_scores(path, ids, scores)
    assert module.flags.sha(path) == before
    with np.load(path) as data:
        assert data["tcn_teacher"].tobytes() == scores.tobytes()
    with pytest.raises(ValueError, match="differs"):
        module.save_scores(path, ids, scores.astype(np.float32))


@pytest.mark.parametrize("mutation", ["dtype", "signed_zero", "ids_dtype"])
def test_full_control_byte_contract_rejects_numerically_equal_copy(tmp_path, mutation):
    source, copied = tmp_path / "original.npz", tmp_path / "copied.npz"
    ids, scores = np.array([1, 2], np.int64), np.array([-0.0, 1.0], np.float64)
    np.savez_compressed(source, action_ids=ids, variant=scores)
    module.save_scores(copied, ids, scores)
    module.verify_full_copy(source, copied)
    if mutation == "dtype":
        scores = scores.astype(np.float32)
    elif mutation == "signed_zero":
        scores[0] = 0.0
    else:
        ids = ids.astype(np.int32)
    np.savez_compressed(copied, action_ids=ids, tcn_teacher=scores)
    with pytest.raises(ValueError, match="byte-exact"):
        module.verify_full_copy(source, copied)


def test_test_control_rejected_before_freeze(tmp_path):
    control, out, _, _, _ = make_control(tmp_path, "test")
    with pytest.raises(ValueError, match="before validation freeze"):
        module.calendar_control(
            SimpleNamespace(flags_root=control), out, "test", [],
            None, None, None, {}, {}, "cpu",
        )


def make_short(tmp_path):
    directory = tmp_path / "SPY" / "20250703"
    directory.mkdir(parents=True)
    actions = pd.DataFrame({"action_id": [11, 12], "state_i": [194, 195]})
    actions.to_parquet(directory / "actions.parquet", index=False)
    return SimpleNamespace(
        ticker="SPY", date="20250703", key="SPY/20250703", oracle=directory, close_i=210
    )


def test_control_full_copy_and_new_short_seal_resume(tmp_path, monkeypatch):
    control, out, source, ids, full_scores = make_control(tmp_path)
    short = make_short(tmp_path)
    full = SimpleNamespace(ticker="SPY", date="20250102", close_i=390)
    for name in ("tcn_control.pt", "normalizers.json"):
        (out / name).write_bytes(b"synthetic authority")
    calls = []
    store = SimpleNamespace(
        hashes={},
        seal=SimpleNamespace(check=lambda day, filename: calls.append(filename)),
    )
    inferred = np.array([-0.0, 7.0])
    monkeypatch.setattr(module.compat, "inference_exact", lambda *args: inferred.copy())
    args = SimpleNamespace(flags_root=control)
    result = module.calendar_control(
        args, out, "validation", [full, short], None, None, store, {}, {"SPY": 1}, "cpu"
    )
    with np.load(result / "validation" / source.name) as data:
        assert data["tcn_teacher"].tobytes() == full_scores.tobytes()
        np.testing.assert_array_equal(data["action_ids"], ids)
    marker = result / "validation/SPY_20250703.prediction.json"
    assert module.flags.read_json(marker)["labels_read"] is False
    assert calls == ["actions.parquet"]
    monkeypatch.setattr(
        module.compat,
        "inference_exact",
        lambda *args: pytest.fail("No repeat inference"),
    )
    module.calendar_control(
        args, out, "validation", [full, short], None, None, store, {}, {"SPY": 1}, "cpu"
    )
    np.savez_compressed(
        result / "validation/SPY_20250703.npz", action_ids=ids, tcn_teacher=full_scores
    )
    with pytest.raises(ValueError, match="Changed bound source"):
        module.calendar_control(
            args,
            out,
            "validation",
            [full, short],
            None,
            None,
            store,
            {},
            {"SPY": 1},
            "cpu",
        )


def test_store_adapter_keeps_pack_identity(tmp_path, monkeypatch):
    feature = tmp_path / "features.npz"
    feature.write_bytes(b"synthetic")
    pack = {
        "tokens": np.arange(40).reshape(2, 20),
        "token_mask": np.ones((2, 20, 2), bool),
    }
    store = object.__new__(module.CalendarStore)
    store.days = {"SPY/20250703": SimpleNamespace(feature_paths=[feature])}
    store.hashes = {}
    store.source = SimpleNamespace(
        hashes={str(feature.resolve()): module.flags.sha(feature)}
    )
    monkeypatch.setattr(module.readers.Features, "get", lambda self, key: pack)
    result = store.get("SPY/20250703")
    assert result is pack
    assert result["token_mask"].shape == (2, 20, 2)
    assert store.hashes == store.source.hashes


def test_calendar_all750_and_missing6_without_outcomes():
    import exchange_calendars as xc

    schedule = xc.get_calendar("XNYS").schedule.loc["2025-01-01":"2026-06-30"]
    days = {}
    for stamp, row in schedule.iterrows():
        date = stamp.strftime("%Y%m%d")
        close = int((row.close - row.open).total_seconds() / 60)
        for ticker in module.flags.TICKERS:
            missing = ticker in ("SPY", "QQQ") and date in (
                "20260401",
                "20260409",
                "20260415",
            )
            days[ticker + "/" + date] = SimpleNamespace(
                ticker=ticker,
                date=date,
                close_i=close,
                status="MISSING_SOURCE" if missing else "COMPLETE",
            )
    result = module.calendar_record(SimpleNamespace(days=days))
    assert result["validation"]["expected"] == result["validation"]["available"] == 750
    assert result["test"]["expected"] == 369 and result["test"]["available"] == 363
    days.pop("SPY/20250703")
    with pytest.raises(ValueError, match="coverage"):
        module.calendar_record(SimpleNamespace(days=days))


def test_no_model_before_training_complete(tmp_path):
    with pytest.raises(FileNotFoundError):
        module.require_epoch_four(tmp_path)


def test_fourth_epoch_boundary_and_history_are_required(tmp_path):
    import shutil
    from pathlib import Path

    binding = dict(epochs=4, variant="row_mixed_original_batch_sizes", files={})
    checkpoint = tmp_path / "tcn_epoch04.pt"
    checkpoint.write_bytes(b"synthetic checkpoint")
    (tmp_path / "tcn_variant.pt").write_bytes(b"synthetic final")
    shutil.copyfile(
        Path(module.__file__).with_name("run_tcn_row_mixed.py"),
        tmp_path / "run_tcn_row_mixed.executed.py",
    )
    metadata = dict(
        epoch=4,
        complete_epoch_boundary=True,
        binding=binding,
        sha256=module.flags.sha(checkpoint),
    )
    module.flags.atomic_json(checkpoint.with_suffix(".json"), metadata)
    module.flags.atomic_json(
        tmp_path / "latest_checkpoint.json",
        dict(
            file=checkpoint.name,
            metadata_sha256=module.flags.sha(checkpoint.with_suffix(".json")),
            sha256=metadata["sha256"],
            epoch=4,
        ),
    )
    record = dict(
        binding=binding,
        history=[dict(epoch=i, updates=1491) for i in range(1, 5)],
        model_sha256=module.flags.sha(tmp_path / "tcn_variant.pt"),
    )
    path = tmp_path / "training_complete.json"
    module.flags.atomic_json(path, record)
    assert module.require_epoch_four(tmp_path) == record
    record["history"][-1]["epoch"] = 3
    module.flags.atomic_json(path, record, replace=True)
    with pytest.raises(ValueError, match="Four completed epochs"):
        module.require_epoch_four(tmp_path)
    record["history"][-1]["epoch"] = 4
    module.flags.atomic_json(path, record, replace=True)
    checkpoint.write_bytes(b"changed checkpoint")
    with pytest.raises(ValueError, match="boundary"):
        module.require_epoch_four(tmp_path)


def test_inference_patch_restored_on_error():
    original = module.flags.inference
    with pytest.raises(RuntimeError):
        with module.exact_inference():
            assert module.flags.inference is module.compat.inference_exact
            raise RuntimeError("synthetic")
    assert module.flags.inference is original


@pytest.mark.parametrize("mutation", ["prediction", "external_short_feature"])
def test_synthetic_e2e_short_full_freeze_null_and_resume(tmp_path, monkeypatch, mutation):
    import run_policy

    control, out, _, _, _ = make_control(tmp_path)
    make_control(tmp_path, "test")
    short = make_short(tmp_path)
    days = [short]
    for date in ("20250102", "20260102"):
        directory = tmp_path / "SPY" / date
        directory.mkdir(parents=True)
        pd.DataFrame({"action_id": [8, 3], "state_i": [60, 61]}).to_parquet(
            directory / "actions.parquet", index=False
        )
        days.append(
            SimpleNamespace(
                ticker="SPY",
                date=date,
                key="SPY/" + date,
                oracle=directory,
                close_i=390,
            )
        )
    for day in days:
        actions = pd.read_parquet(day.oracle / "actions.parquet")
        pd.DataFrame(
            {
                "action_id": actions.action_id,
                "status": ["FILLED", "NO_FILL"],
                "exit_i": [int(actions.state_i.iloc[0]) + 2, -1],
                "net_base": [1.0, 0.0],
                "net_adverse": [0.5, 0.0],
            }
        ).to_parquet(day.oracle / "labels.parquet", index=False)
        day.status = "COMPLETE"
    (out / "expected_full_calendar.csv").write_text(
        "date\n20250102\n20250703\n20260102\n"
    )
    for name in ("tcn_control.pt", "tcn_variant.pt"):
        (out / name).write_bytes(b"synthetic model")
    module.flags.atomic_json(out / "identity.json", {"synthetic": True})
    module.flags.atomic_json(out / "feature_schema.json", {})
    module.flags.atomic_json(
        out / "normalizers.json",
        {"features": {}, "risk_scales_usd": {t: 1.0 for t in module.flags.TICKERS}},
    )
    events = []

    def check(day, filename):
        period = "validation" if day.date < "20260101" else "test"
        if period == "test":
            assert (out / "freeze.json").exists()
        if filename == "labels.parquet":
            assert (
                out / period / (day.ticker + "_" + day.date + ".prediction.json")
            ).exists()
        events.append((day.key, filename))

    seal = SimpleNamespace(
        days={day.key: day for day in days},
        hashes={},
        check=check,
        recheck=lambda: None,
    )
    external = tmp_path / "short_feature.npz"
    external.write_bytes(b"synthetic external short feature")
    store = SimpleNamespace(
        seal=seal, hashes={str(external): module.flags.sha(external)}
    )
    identity = {"files": {}, "learner_root": str(tmp_path / "learner")}
    monkeypatch.setattr(
        module, "bind", lambda args: (identity, {"binding": {"device": "cpu"}}, seal)
    )
    monkeypatch.setattr(module, "CalendarStore", lambda *args: store)
    monkeypatch.setattr(module.flags, "CheckedStore", lambda value, schema: value)
    monkeypatch.setattr(
        module, "load_model", lambda *args: SimpleNamespace(eval=lambda: None)
    )
    monkeypatch.setattr(
        module.compat, "inference_exact", lambda *args: np.full(len(args[4]), 11.0)
    )
    engine = SimpleNamespace(
        FIRST_STATE=60,
        ledger_summary=lambda frame: {},
        PolicyResult=lambda attempts, ledger, summary: SimpleNamespace(
            attempts=attempts, ledger=ledger
        ),
    )
    original = SimpleNamespace(
        import_sibling=lambda name: run_policy if name == "run_policy" else engine,
        economic_metrics=lambda frame: {
            "base_net_usd": float(frame.net_base.sum()),
            "adverse_net_usd": float(frame.net_adverse.sum()),
        },
        economic_gate=lambda *args: pytest.fail("Missing tickers means selected null"),
    )
    monkeypatch.setattr(module.flags, "load_original", lambda root: original)
    args = SimpleNamespace(output=out, flags_root=control)
    module.evaluate(args)
    summary = module.flags.read_json(out / "summary.json")
    assert summary["selection"]["selected_policy"] is None
    assert set(summary["test"]) == set(module.flags.POLICIES)
    assert summary["test"]["variant__0"]["daily_gate"]["expected_days"] == 3
    freeze = module.flags.read_json(out / "freeze.json")
    assert freeze["expected_validation_days"] == 750
    assert all("/test/" not in name.replace("\\", "/") for name in freeze["files"])
    assert any(name == "labels.parquet" for _, name in events)
    completion_hash = module.flags.sha(out / "completion.json")
    monkeypatch.setattr(
        module,
        "load_model",
        lambda *args: pytest.fail("Complete resume never loads models"),
    )
    module.evaluate(args)
    assert module.flags.sha(out / "completion.json") == completion_hash
    assert str(external) in module.flags.read_json(out / "source_inputs.json")["files"]
    changed = external if mutation == "external_short_feature" else (
        out / "validation/SPY_20250703.npz"
    )
    changed.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Changed bound source"):
        module.evaluate(args)
