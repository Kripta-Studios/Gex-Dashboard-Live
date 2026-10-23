"""Synthetic evidence only; no market values, fitting or inference.

The complete fixture has the real calendar cardinality but one artificial action
per available day. Its 2025 authority is explicitly synthetic/trusted; the six
new months and twelve fit inputs are reconstructed by the auditor under test.
"""

import ast
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import audit_monthly_walk_forward_test as audit


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def synthetic_economics(count):
    result = dict(trades=count)
    for field, value in (("net_base", 1.0), ("net_adverse", -1.0)):
        result.update({field: value * count,
            field + "_pf": 0.0 if count and value < 0 else None,
            field + "_pf_infinite": bool(count and value > 0),
            field + "_win_rate": (float(value > 0) if count else None),
            field + "_max_drawdown": float(count) if value < 0 else 0.0})
    result["holding_minutes"] = dict.fromkeys(("min", "median", "max"), 1.0 if count else None)
    result["exit_reasons"] = {
        key: dict(trades=count if key == "TARGET" else 0,
                  net_base=float(count) if key == "TARGET" else 0.0,
                  net_adverse=-float(count) if key == "TARGET" else 0.0)
        for key in ("TARGET", "STOP", "EOD")
    } if count else {}
    return result


def synthetic_summary(rows, active):
    available = sum(row["status"] == "COMPLETE" for row in rows)
    missing = len(rows) - available
    trades = available if active else 0
    return dict(expected_ticker_days=len(rows), available_ticker_days=available,
        missing_no_evaluable=missing, available_days_with_fill=trades,
        available_days_without_fill=available - trades,
        observable_daily_pass=bool(available) and active,
        full_calendar_daily_status=("NO_EVALUABLE_MISSING_SOURCE" if missing else
                                    "PASS" if available and active else "FAIL_OBSERVED_ZERO"),
        daily_requirement_satisfied=bool(available) and missing == 0 and active,
        available_economics=synthetic_economics(trades),
        net_base_per_available_day=float(active) if available else None,
        missing_day_economics=None)


def make_fixture(base):
    import exchange_calendars as xc

    root, session = base / "monthly", base / "session"
    root.mkdir(parents=True)
    session.mkdir()
    clock = datetime(2026, 10, 23, 10, tzinfo=timezone.utc)
    source = session / "synthetic_source"
    source.mkdir()
    actions = pd.DataFrame(dict(action_id=np.array([0], dtype=np.int64),
                                state_i=np.array([60], dtype=np.int64)))
    labels = pd.DataFrame(dict(action_id=np.array([0], dtype=np.int64), status=["FILLED"],
        exit_i=np.array([62], dtype=np.int64), entry_ask=[1.0], net_base=[1.0],
        net_adverse=[-1.0], hold_minutes=np.array([1], dtype=np.int64), reason=["TARGET"]))
    actions.to_parquet(source / "actions.parquet", index=False)
    labels.to_parquet(source / "labels.parquet", index=False)
    feature_names = ("features.npy", "features_meta.json", "action_features.npy", "action_features_meta.json")
    for name in feature_names:
        (source / name).write_bytes(b"synthetic feature bytes already sealed by source fixture")
    feature_paths = [source / name for name in feature_names]
    feature_hashes = {str(p): audit.sha(p) for p in feature_paths}
    action_hash, label_hash = audit.sha(source / "actions.parquet"), audit.sha(source / "labels.parquet")
    schedule = xc.get_calendar("XNYS").schedule.loc["2023-01-03":"2026-06-30"]
    rows = []
    for ticker in audit.TICKERS:
        for stamp, item in schedule.iterrows():
            day = stamp.strftime("%Y%m%d")
            missing = ticker in ("SPY", "QQQ") and day in ("20260401", "20260409", "20260415")
            row = dict(ticker=ticker, date=day, status="MISSING_SOURCE" if missing else "COMPLETE",
                close_i=int((item.close - item.open).total_seconds() / 60), day_root=str(source),
                actions_sha256=action_hash, labels_sha256=label_hash)
            row.update(dict(zip(("features_path", "features_meta_path", "action_features_path",
                                 "action_features_meta_path"), map(str, feature_paths))))
            rows.append(row)
    assert len(rows) == 2625
    pd.DataFrame(rows).to_parquet(session / "index.parquet", index=False)
    for name in ("dataset_contract.json", "completion.json", "feature_contract.json"):
        write_json(session / name, {"synthetic_fixture": name})
    sb = dict(engine_root=str(session), feature_root=str(session),
        index_sha256=audit.sha(session / "index.parquet"),
        dataset_contract_sha256=audit.sha(session / "dataset_contract.json"),
        completion_sha256=audit.sha(session / "completion.json"),
        feature_contract_sha256=audit.sha(session / "feature_contract.json"),
        available_days=2619, missing_days=6)
    source_audit = base / "source_audit.json"
    write_json(source_audit, dict(status="PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT", binding=sb))
    config = dict(n_estimators=200, random_state=20261018)
    scientific_dependencies = {}
    for name in audit.independent.DEPENDENCIES:
        path = root / "executed_code" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(("synthetic reviewed scientific snapshot " + name).encode())
        scientific_dependencies[name] = audit.sha(path)
    contract = dict(version="MONTHLY_NET_WALK_FORWARD_V1", seed=20261018,
        features=1954, threshold_usd=0, config=config, engine_root=str(session),
        feature_root=str(session), dependencies=scientific_dependencies,
        source_audit=dict(path=str(source_audit), sha256=audit.sha(source_audit), binding=sb,
            coverage={"synthetic": True}, feature_contract_sha256=sb["feature_contract_sha256"]))
    write_json(root / "run_contract.json", contract)
    binding = audit.sha(root / "run_contract.json")
    hashes = {}

    def digest(path):
        if str(path) not in hashes:
            hashes[str(path)] = audit.sha(path)
        return hashes[str(path)]

    def marker(name, paths, extra=None, minute=-10):
        path = root / (name + ".complete.json")
        write_json(path, dict(status="COMPLETE", binding=binding,
            files={str(p.relative_to(root)): digest(p) for p in paths}, extra=extra or {},
            completed_utc=(clock + timedelta(minutes=minute)).isoformat()))
        return path

    def json_artifact(name, payload, minute=-10):
        path = root / (name + ".json")
        write_json(path, payload)
        return path, marker(name, [path], minute=minute)

    xrow = np.ones((1, 1954), dtype=np.float32)
    day_inputs = {}
    for row in rows:
        if row["status"] != "COMPLETE":
            continue
        daykey = row["ticker"] + "/" + row["date"]
        feature, fm = json_artifact("feature_inputs/" + daykey, feature_hashes)
        paths = [source / "actions.parquet", source / "labels.parquet", *feature_paths, feature, fm]
        # June does not enter any of the twelve TRAIN windows.
        if row["date"] < "20260601":
            identity = hashlib.sha256(json.dumps([20261018, row["ticker"], row["date"], 60, 0],
                separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
            sample = root / ("day_samples/" + daykey + ".npz")
            sample.parent.mkdir(parents=True, exist_ok=True)
            np.savez(sample, action_id=np.array([0], dtype=np.int64), state_i=np.array([60], dtype=np.int64),
                band_i=np.array([0], dtype=np.int64), identity_sha256=np.array([identity], dtype="U64"),
                weight=np.array([1.0]), population_by_band=np.array([1, 0, 0, 0], dtype=np.int64),
                selected_by_band=np.array([1, 0, 0, 0], dtype=np.int64))
            sm = marker("day_samples/" + daykey, [sample])
            chunk = root / ("day_chunks/" + daykey + ".npz")
            chunk.parent.mkdir(parents=True, exist_ok=True)
            np.savez(chunk, action_id=np.array([0], dtype=np.int64), x=xrow, net=np.array([1.0]),
                premium=np.array([100.0]), filled=np.array([True]), weight=np.array([1.0]))
            cm = marker("day_chunks/" + daykey, [chunk])
            paths.extend([sample, sm, chunk, cm])
        day_inputs[daykey] = {str(p): digest(p) for p in paths}
    all_fits = {audit.independent.window(mode, date(year, month, 1))
                for year, months in ((2025, range(1, 13)), (2026, range(1, 7)))
                for month in months for mode in audit.MODES}
    fit_info = {}
    for start, stop, key in sorted(all_fits):
        training = sorted([r for r in rows if r["status"] == "COMPLETE"
            and start.strftime("%Y%m%d") <= r["date"] < stop.strftime("%Y%m%d")],
            key=lambda r: (r["ticker"], r["date"]))
        count = len(training)
        info = dict(fit_key=key, train_start=start.isoformat(), train_stop_exclusive=stop.isoformat(),
            config=config, rows=count, ticker_days=count, scales=dict.fromkeys(audit.TICKERS, 100.0))
        new_fit = stop.year == 2026
        minute = stop.month * 10 + 1 if new_fit else -20
        info["input_hashes"] = {}
        if new_fit:
            for row in training:
                info["input_hashes"].update(day_inputs[row["ticker"] + "/" + row["date"]])
            folder = root / "fits" / key
            folder.mkdir(parents=True)
            matrix_path, targets_path = folder / "matrix.npy", folder / "targets.npz"
            np.save(matrix_path, np.ones((count, 1954), dtype=np.float32))
            target, weight = np.full(count, 0.01), np.ones(count)
            np.savez(targets_path, target=target, weight=weight, net=np.ones(count),
                     ticker=np.asarray([r["ticker"] for r in training]))
            marker("fits/" + key + "/matrix", [matrix_path], minute=minute - 1)
            marker("fits/" + key + "/targets", [targets_path], minute=minute - 1)
        model = root / "models" / (key + ".txt")
        model.parent.mkdir(exist_ok=True)
        model.write_text("synthetic model; never fit or inferred; " + key, encoding="utf-8")
        started = model.with_suffix(".fit_started.json")
        start_record = dict(binding=binding, config=config, shape=[count, 1954],
            started_utc=(clock + timedelta(minutes=minute)).isoformat())
        if new_fit:
            start_record.update(matrix_sha256=digest(matrix_path),
                target_sha256=hashlib.sha256(target.tobytes()).hexdigest(),
                weight_sha256=hashlib.sha256(weight.tobytes()).hexdigest())
        write_json(started, start_record)
        marker("models/" + key, [model, started], minute=minute + 1)
        json_artifact("fits/" + key + "/inputs", info, minute=minute - 1)
        fit_info[key] = info
    static_key = audit.independent.window("static", date(2026, 1, 1))[2]
    prior_paths = [root / "run_contract.json", source_audit, session / "index.parquet"]
    prior_paths.extend((root / "executed_code").iterdir())
    for start, stop, key in all_fits:
        if stop.year < 2026:
            prior_paths.extend([root / f"models/{key}{suffix}"
                                for suffix in (".txt", ".fit_started.json", ".complete.json")])
            prior_paths.extend([root / f"fits/{key}/inputs{suffix}"
                                for suffix in (".json", ".complete.json")])
    for stamp in audit.MONTHS_2025:
        monthrows = [r for r in rows if r["date"].startswith(stamp)]
        daily = {mode: [dict(ticker=r["ticker"], date=r["date"], source_status=r["status"],
                            trades=0, net_base=0.0, net_adverse=0.0) for r in monthrows]
                 for mode in audit.MODES}
        dp, dm = json_artifact(f"months/{stamp}/daily", daily)
        ep, em = json_artifact(f"months/{stamp}/economics", {"synthetic_prior": True})
        pm = marker(f"months/{stamp}/predictions", [dp], dict(labels_read=False))
        prior_paths.extend([dp, dm, ep, em, pm])
    freeze = dict(status="FAIL_NO_DAILY_COMPLIANT_MODE", selected_mode=None, approved=False,
        common_scales=dict.fromkeys(audit.TICKERS, 100.0), selection_period="2025",
        common_scale_fit=static_key, choices=[], tie_break=list(audit.MODES),
        validation_input_hashes={str(root / f"months/{m}/daily.json"):
            digest(root / f"months/{m}/daily.json") for m in audit.MONTHS_2025},
        update_rule="FROZEN_CALENDAR_STATIC_EXPANDING_ROLLING12", outcomes_2026_used_for_mode_selection=False)
    prior_paths.extend(json_artifact("validation_freeze", freeze, minute=0))
    prior_paths.extend(json_artifact("reports/2025", dict(synthetic_prior=True, selected_mode=None)))
    # One authenticated 2025 prediction is enough to check real adapter reuse of
    # the trusted prior inventory; the fixture does not pretend to re-audit 2025.
    pname = "predictions/202501/" + static_key + "/SPY/20250102"
    pp = root / (pname + ".npz")
    pp.parent.mkdir(parents=True)
    np.savez(pp, action_id=np.array([0]), state_i=np.array([60]), scores=np.array([-1.0]),
        model_sha256=np.array(digest(root / f"models/{static_key}.txt")), scale=np.array(100.0))
    prior_paths.extend([pp, marker(pname, [pp])])
    # Put this prediction in the historical all-mode seal for adapter access.
    historical_pm = marker("months/202501/predictions", [pp], dict(labels_read=False))
    hashes.pop(str(historical_pm), None)
    historical_dm = marker("months/202501/daily", [root / "months/202501/daily.json", historical_pm])
    hashes.pop(str(historical_dm), None)
    all_records = {mode: [] for mode in audit.MODES}
    for stamp in audit.MONTHS_2026:
        month = int(stamp[4:])
        fits = {mode: audit.independent.window(mode, date(2026, month, 1))[2] for mode in audit.MODES}
        monthrows = sorted([r for r in rows if r["date"].startswith(stamp)],
                           key=lambda r: (r["ticker"], r["date"]))
        members, source_manifests = [], []
        for key in fits.values():
            members.extend([root / f"models/{key}.txt", root / f"models/{key}.complete.json",
                            root / f"fits/{key}/inputs.json", root / f"fits/{key}/inputs.complete.json"])
        for row in monthrows:
            if row["status"] != "COMPLETE":
                continue
            daykey = row["ticker"] + "/" + row["date"]
            members.extend([root / f"feature_inputs/{daykey}.json", root / f"feature_inputs/{daykey}.complete.json"])
            source_manifests.append("feature_inputs/" + daykey + ".json")
            for mode, key in fits.items():
                name = f"predictions/{stamp}/{key}/{daykey}"
                path = root / (name + ".npz")
                path.parent.mkdir(parents=True, exist_ok=True)
                np.savez(path, action_id=np.array([0], dtype=np.int64), state_i=np.array([60], dtype=np.int64),
                    scores=np.array([1.0 if mode == "expanding" else -1.0]),
                    model_sha256=np.array(digest(root / f"models/{key}.txt")), scale=np.array(100.0))
                marker(name, [path], minute=month * 10 + 3)
                members.append(path)
        pm = marker(f"months/{stamp}/predictions", members,
            dict(fit_keys=sorted(fits.values()), labels_read=False, source_manifests=sorted(source_manifests)),
            minute=month * 10 + 4)
        daily, daily_members = {}, [pm, *members]
        for mode, key in fits.items():
            daily[mode] = []
            for row in monthrows:
                available, active = row["status"] == "COMPLETE", mode == "expanding"
                count = int(available and active)
                daily[mode].append(dict(ticker=row["ticker"], date=row["date"], source_status=row["status"],
                    trades=count, net_base=float(count), net_adverse=-float(count)))
                if not available:
                    continue
                frame = actions.merge(labels, on="action_id", validate="one_to_one")
                if not active:
                    frame = frame.iloc[[]].copy()
                frame["score"] = np.full(len(frame), 1.0 if active else -1.0)
                frame["has_filled_before"] = [0] if active else []
                frame["ticker"], frame["date"], frame["mode"], frame["fit_key"] = row["ticker"], row["date"], mode, key
                prefix = f"ledgers/{stamp}/{mode}/{row['ticker']}/{row['date']}"
                ap, lp = root / (prefix + "_attempts.parquet"), root / (prefix + "_ledger.parquet")
                ap.parent.mkdir(parents=True, exist_ok=True)
                frame.to_parquet(ap, index=False)
                frame.to_parquet(lp, index=False)
                prediction = root / f"predictions/{stamp}/{key}/{row['ticker']}/{row['date']}.npz"
                lm = marker(prefix, [ap, lp], dict(prediction_sha256=digest(prediction)), minute=month * 10 + 5)
                daily_members.extend([ap, lp, lm])
            all_records[mode].extend(daily[mode])
        economics = {mode: dict(overall=synthetic_economics(sum(r["status"] == "COMPLETE" for r in monthrows)
                                                         if mode == "expanding" else 0),
            tickers={ticker: synthetic_economics(sum(r["ticker"] == ticker and r["status"] == "COMPLETE"
                                                    for r in monthrows) if mode == "expanding" else 0)
                     for ticker in audit.TICKERS}) for mode in audit.MODES}
        ep, em = json_artifact(f"months/{stamp}/economics", economics, minute=month * 10 + 6)
        dp = root / f"months/{stamp}/daily.json"
        write_json(dp, daily)
        marker(f"months/{stamp}/daily", [dp, ep, em, *daily_members], minute=month * 10 + 7)
    testrows = [r for r in rows if r["date"].startswith("2026")]
    report = dict(year=2026, modes={mode: dict(overall=synthetic_summary(testrows, mode == "expanding"),
        tickers={ticker: synthetic_summary([r for r in testrows if r["ticker"] == ticker], mode == "expanding")
                 for ticker in audit.TICKERS}) for mode in audit.MODES}, selected_mode=None,
        selection_period=2025, development_seen=True, promotion_approved=False,
        missing_sources_are_not_observed_losses=True)
    json_artifact("reports/2026", report, minute=70)
    json_artifact("completion", dict(status="COMPLETE", modes=list(audit.MODES), evaluated_months=18,
        unique_fit_windows=36, selected_mode=None, development_seen=True, promotion_approved=False,
        report_hashes={str(y): digest(root / f"reports/{y}.json") for y in (2025, 2026)}), minute=71)
    prior = base / "validation_audit.json"
    write_json(prior, dict(status=audit.STATUS,
        binding=dict(monthly_root=str(root), run_contract_sha256=binding, session_root=str(session),
            session_audit_sha256=digest(source_audit), index_sha256=sb["index_sha256"],
            completed_months=list(audit.MONTHS_2025)),
        audited=dict(months=12, unique_fit_windows=24, calendar_ticker_days=750, modes=list(audit.MODES),
            validation_selection_reconstructed=True, validation_period_report_reconstructed=True),
        verified_files=dict(artifacts={str(p): audit.sha(p) for p in prior_paths})))
    review, runtime = base / "review.json", base / "runtime.json"
    write_json(review, dict(status=audit.REVIEW_STATUS, dependencies=audit.dependencies()))
    write_json(runtime, dict(status=audit.RUNTIME_STATUS, scope=audit.SCOPE,
        dependencies=audit.dependencies(), allowed_read_roots=[str(base), str(audit.HERE)],
        binding=dict(monthly_root=str(root), source_audit=str(source_audit), validation_audit=str(prior),
            validation_audit_sha256=audit.sha(prior), implementation_review_sha256=audit.sha(review),
            run_contract_sha256=binding, source_audit_sha256=digest(source_audit),
            index_sha256=sb["index_sha256"], session_root=str(session),
            validation_freeze_sha256=digest(root / "validation_freeze.json"))))
    return SimpleNamespace(monthly_root=root, source_audit=source_audit, validation_audit=prior,
        expected_validation_audit_sha256=audit.sha(prior), implementation_review=review,
        runtime_review=runtime, output=base / "audit_output", session=session, rows=rows)


@pytest.fixture(scope="module")
def complete_fixture(tmp_path_factory):
    # The parent coordinates runs. This gate makes the fixture itself fail closed
    # if physical RAM or commit headroom falls below the agreed decimal 2 GB.
    import psutil
    import ctypes

    if __import__("os").name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        *[(name, ctypes.c_ulonglong) for name in
                          ("total_phys", "avail_phys", "total_page", "avail_page", "total_virtual",
                           "avail_virtual", "avail_extended")]]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        assert status.avail_page >= 2_000_000_000, "Need 2 GB free commit for synthetic tests"
    assert psutil.virtual_memory().available >= 2_000_000_000, "Need 2 GB free RAM for synthetic tests"
    return make_fixture(tmp_path_factory.mktemp("monthly_test_synthetic"))


def constructor(args):
    return audit.TestAudit(args.monthly_root, args.source_audit, args.validation_audit,
        args.expected_validation_audit_sha256, args.implementation_review, args.runtime_review)


@contextmanager
def replaced(path, payload):
    original = path.read_bytes()
    try:
        if isinstance(payload, dict):
            write_json(path, payload)
        else:
            path.write_bytes(payload)
        yield
    finally:
        path.write_bytes(original)


def test_complete_synthetic_closure_and_real_monthly_adapter(complete_fixture, tmp_path):
    args = complete_fixture
    result = audit.run(args)
    assert result["status"] == audit.STATUS
    assert result["binding"]["completed_months"] == list(audit.MONTHS_2025 + audit.MONTHS_2026)
    assert result["audited"]["new_unique_fit_windows"] == 12
    assert result["audited"]["models_used_test"] == 13
    assert result["audited"]["selected_mode"] is None
    assert len(result["audited"]["missing_identities"]) == 6
    report = audit.read_json(args.monthly_root / "reports/2026.json")
    assert report["modes"]["expanding"]["overall"]["available_economics"]["net_base"] == 363.0
    assert report["modes"]["expanding"]["overall"]["missing_day_economics"] is None
    import monthly_oof_calibration_adapter as adapter

    output = args.output / "audit.json"
    source = adapter.MonthlyInputs(args.monthly_root, output, audit.sha(output), args.session, args.source_audit)
    for mode in audit.MODES:
        for day in ("20260102", "20260601"):
            selected = source.select_day(mode, "SPY", day, tmp_path / (mode + day))
            assert Path(selected["selection_path"]).exists()
    old = source.select_day("static", "SPY", "20250102", tmp_path / "prior")
    assert Path(old["selection_path"]).exists()
    source.recheck()
    with pytest.raises(ValueError, match="new audit output"):
        audit.run(args)


def test_no_producer_or_model_stack_imports():
    for module in (audit, audit.independent):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        assert not names & {"run_monthly_walk_forward", "rolling_monthly_schedule",
                            "monthly_policy_selection", "lightgbm", "train_models"}


def test_six_windows_and_three_model_keys():
    keys = set()
    for month in range(1, 7):
        target = date(2026, month, 1)
        per_month = {audit.independent.window(mode, target)[2] for mode in audit.MODES}
        assert len(per_month) == 3
        assert audit.independent.window("rolling12", target)[:2] == (date(2025, month, 1), target)
        assert audit.independent.window("expanding", target)[:2] == (date(2023, 1, 1), target)
        keys.update(per_month)
    assert len(keys) == 13


def test_prior_audit_hash_rejected_before_labels(complete_fixture, monkeypatch):
    args = complete_fixture
    monkeypatch.setattr(audit.independent.MonthlyAudit, "source_frame",
        lambda *a, **k: pytest.fail("No label/source read before authority admission"))
    wrong = SimpleNamespace(**vars(args))
    wrong.expected_validation_audit_sha256 = "0" * 64
    with pytest.raises(ValueError, match="Runtime authority"):
        constructor(wrong)


def test_prior_mutation_and_missing_mode_evidence(complete_fixture):
    args = complete_fixture
    path = args.monthly_root / "validation_freeze.json"
    with replaced(path, b"changed"):
        with pytest.raises(ValueError, match="Hash mismatch"):
            constructor(args)


def test_conflicting_hashes_and_outside_root():
    path = str(Path(__file__).resolve())
    with pytest.raises(ValueError, match="Conflicting"):
        audit.flatten_verified({"a": {path: "a" * 64}, "b": {path: "b" * 64}})
    with pytest.raises(ValueError, match="Absolute"):
        audit.flatten_verified({"a": {"relative.txt": "a" * 64}})
    assert not audit.within(Path(__file__).resolve().parent.parent, [Path(__file__).resolve().parent])


def test_scheduler_ties_no_fill_blocking_and_short_session():
    actions = pd.DataFrame(dict(action_id=[1, 0, 2, 3, 4], state_i=[60, 60, 61, 63, 195]))
    labels = pd.DataFrame(dict(action_id=[1, 0, 2, 3, 4], status=["FILLED", "NO_FILL", "FILLED", "FILLED", "FILLED"],
        exit_i=[62, 61, 64, 65, 205], entry_ask=[1.0] * 5, net_base=[1.0, 0.0, -1.0, 2.0, 3.0],
        net_adverse=[-1.0, 0.0, -3.0, 0.0, 1.0], hold_minutes=[1, 0, 2, 1, 9], reason=["TARGET"] * 5))
    attempts, ledger = audit.independent.schedule(210, actions, labels, np.ones(5))
    assert attempts.action_id.tolist() == [0, 2, 4]
    assert attempts.has_filled_before.tolist() == [0, 0, 1]
    assert ledger.action_id.tolist() == [2, 4]
    assert ledger.net_base.sum() == 2
    assert audit.independent.schedule(210, actions, labels, np.zeros(5))[0].empty
    labels.loc[4, "exit_i"] = 206
    with pytest.raises(ValueError, match="outside session"):
        audit.independent.schedule(210, actions, labels, np.ones(5))


def test_snapshot_mutation_fails_final_recheck(tmp_path):
    path = tmp_path / "evidence"
    path.write_bytes(b"before")
    verifier = audit.independent.Verifier()
    verifier.file("test", path)
    path.write_bytes(b"after")
    with pytest.raises(ValueError, match="changed during audit"):
        verifier.recheck()


def test_new_output_lock_preserves_interrupted_directory(tmp_path):
    output = tmp_path / "new"
    with pytest.raises(RuntimeError):
        with audit.exclusive_output(output):
            raise RuntimeError("synthetic interruption")
    assert (output / ".lock").exists()
    with pytest.raises(FileExistsError):
        with audit.exclusive_output(output):
            pytest.fail("Existing output adopted")


def test_reject_test_window_cutoff_before_source_reads():
    subject = object.__new__(audit.TestAudit)
    with pytest.raises(ValueError, match="Only the twelve"):
        subject.audit_fit("arbitrary", date(2023, 1, 1), date(2025, 12, 1))
    with pytest.raises(ValueError, match="Wrong test fit window"):
        subject.audit_fit("train_20230101_20260201_exclusive", date(2023, 1, 1), date(2026, 3, 1))


def test_feature_manifest_paths_are_bounded_before_read(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.npy"
    outside.write_bytes(b"not allowed")
    verifier = audit.BoundedVerifier([allowed])
    manifest = {str(outside): audit.sha(outside)}
    monkeypatch.setattr(audit.independent, "sha", lambda p: pytest.fail("Outside bytes were read"))
    for path, digest in manifest.items():
        with pytest.raises(ValueError, match="outside declared read roots"):
            verifier.file("prediction_manifests", path, digest)


def prediction_fixture():
    actions = pd.DataFrame(dict(action_id=np.array([2, 1], dtype=np.int64),
                                state_i=np.array([60, 61], dtype=np.int64)))
    pred = dict(action_id=np.array([2, 1], dtype=np.int64), state_i=np.array([60, 61], dtype=np.int64),
                scores=np.array([1.0, -1.0], dtype=np.float64),
                model_sha256=np.array("a" * 64), scale=np.array(100.0))
    return actions, pred


@pytest.mark.parametrize("change,message", [
    (lambda p: p.update(scores=p["scores"].astype(np.float32)), "finite float64"),
    (lambda p: p.update(scores=np.array([np.nan, 1.0])), "finite float64"),
    (lambda p: p.update(scores=p["scores"].reshape(1, 2)), "finite float64"),
    (lambda p: p.update(action_id=p["action_id"][::-1]), "identity/clock"),
    (lambda p: p.update(state_i=p["state_i"].astype(np.int32)), "identity/clock"),
    (lambda p: p.update(model_sha256=np.array("b" * 64)), "model differs"),
    (lambda p: p.update(scale=np.array(101.0)), "scale differs"),
    (lambda p: p.update(scale=np.array([100.0])), "scale differs"),
    (lambda p: p.update(extra=np.array(1)), "field schema"),
])
def test_prediction_schema_faults(change, message):
    actions, pred = prediction_fixture()
    audit.check_prediction(pred, actions, "a" * 64, 100.0)
    change(pred)
    with pytest.raises(ValueError, match=message):
        audit.check_prediction(pred, actions, "a" * 64, 100.0)


def test_resigned_float32_npz_still_fails_schema(tmp_path):
    actions, pred = prediction_fixture()
    pred["scores"] = pred["scores"].astype(np.float32)
    path = tmp_path / "pred.npz"
    np.savez(path, **pred)
    write_json(tmp_path / "pred.complete.json", dict(status="COMPLETE", binding="synthetic",
        files={"pred.npz": audit.sha(path)}, extra={}, completed_utc="2026-10-23T10:00:00+00:00"))
    evidence = audit.independent.Evidence(tmp_path, audit.independent.Verifier(), "synthetic")
    evidence.member("pred", path)
    with pytest.raises(ValueError, match="float64"):
        audit.check_prediction(audit.independent.load_npz(path), actions, "a" * 64, 100.0)


def small_preflight(root):
    root.mkdir()
    clock = datetime(2026, 10, 23, 10, tzinfo=timezone.utc)
    subject = object.__new__(audit.TestAudit)
    subject.root, subject.contract_hash = root, "a" * 64
    subject.v = audit.independent.Verifier()
    subject.evidence = audit.independent.Evidence(root, subject.v, subject.contract_hash)
    subject.freeze_time, subject.freeze, subject.days = clock, {"selected_mode": None}, {}

    def seal(name, paths, minute, extra=None):
        path = root / (name + ".complete.json")
        write_json(path, dict(status="COMPLETE", binding=subject.contract_hash,
            files={str(p.relative_to(root)): audit.sha(p) for p in paths}, extra=extra or {},
            completed_utc=(clock + timedelta(minutes=minute)).isoformat()))

    for stamp in audit.MONTHS_2026:
        keys = sorted(audit.independent.window(mode, date(2026, int(stamp[4:]), 1))[2]
                      for mode in audit.MODES)
        members = []
        for key in keys:
            model = root / f"models/{key}.txt"
            started = root / f"models/{key}.fit_started.json"
            if not model.exists():
                model.parent.mkdir(exist_ok=True)
                model.write_bytes(b"synthetic sealed model")
                write_json(started, {"synthetic": True})
                seal("models/" + key, [model, started], 1)
                info = root / f"fits/{key}/inputs.json"
                write_json(info, dict(scales=dict.fromkeys(audit.TICKERS, 100.0)))
                seal(f"fits/{key}/inputs", [info], 1)
            members.append(model)
        for kind in ("daily", "economics"):
            path = root / f"months/{stamp}/{kind}.json"
            write_json(path, {"synthetic": True})
            seal(f"months/{stamp}/{kind}", [path], 12)
        seal(f"months/{stamp}/predictions", members, 10,
             dict(fit_keys=keys, labels_read=False))
    for year in (2025, 2026):
        path = root / f"reports/{year}.json"
        write_json(path, {"synthetic": year})
        seal(f"reports/{year}", [path], 13)
    path = root / "completion.json"
    write_json(path, dict(status="COMPLETE", modes=list(audit.MODES), evaluated_months=18,
        unique_fit_windows=36, selected_mode=None, development_seen=True, promotion_approved=False,
        report_hashes={str(y): audit.sha(root / f"reports/{y}.json") for y in (2025, 2026)}))
    seal("completion", [path], 14)
    return subject, seal


@pytest.mark.parametrize("fault,message", [
    ("omit_static", "All three fit identities"),
    ("late_freeze", "precede validation freeze"),
    ("late_model", "Model completed after"),
    ("incomplete", "Incomplete or changed full"),
    ("selected_null_changed", "Incomplete or changed full"),
])
def test_preflight_closure_faults(tmp_path, fault, message):
    subject, seal = small_preflight(tmp_path / "monthly")
    if fault == "omit_static":
        path = subject.root / "months/202601/predictions.complete.json"
        value = audit.read_json(path)
        value["extra"]["fit_keys"] = value["extra"]["fit_keys"][1:]
        write_json(path, value)
    elif fault == "late_freeze":
        subject.freeze_time += timedelta(days=1)
    elif fault == "late_model":
        key = audit.independent.window("static", date(2026, 1, 1))[2]
        seal("models/" + key, [subject.root / f"models/{key}.txt",
                               subject.root / f"models/{key}.fit_started.json"], 20)
    else:
        path = subject.root / "completion.json"
        value = audit.read_json(path)
        value["unique_fit_windows" if fault == "incomplete" else "selected_mode"] = (
            35 if fault == "incomplete" else "expanding")
        write_json(path, value)
        seal("completion", [path], 14)
    with pytest.raises(ValueError, match=message):
        subject.preflight_closure()


def test_preflight_valid_null_closure(tmp_path):
    subject, _ = small_preflight(tmp_path / "monthly")
    subject.preflight_closure()
    assert subject.freeze["selected_mode"] is None


@pytest.mark.parametrize("fault", ["drop_day", "missing_as_complete", "short_test_day"])
def test_calendar_faults_fail_closed(tmp_path, fault):
    import exchange_calendars as xc

    calendar = xc.get_calendar("XNYS").schedule.loc["2023-01-03":"2026-06-30"]
    rows = []
    for ticker in audit.TICKERS:
        for stamp, item in calendar.iterrows():
            day = stamp.strftime("%Y%m%d")
            missing = ticker in ("SPY", "QQQ") and day in ("20260401", "20260409", "20260415")
            rows.append(dict(ticker=ticker, date=day, status="MISSING_SOURCE" if missing else "COMPLETE",
                             close_i=int((item.close - item.open).total_seconds() / 60)))
    subject = object.__new__(audit.TestAudit)
    subject.days, subject.allowed_read_roots = {}, (tmp_path,)
    frame = pd.DataFrame(rows)
    if fault == "drop_day":
        frame = frame.loc[~((frame.ticker == "SPY") & (frame.date == "20260102"))]
    elif fault == "missing_as_complete":
        frame.loc[(frame.ticker == "SPY") & (frame.date == "20260401"), "status"] = "COMPLETE"
    else:
        frame.loc[(frame.ticker == "SPY") & (frame.date == "20260102"), "close_i"] = 210
    subject.index = frame.set_index(["ticker", "date"])
    with pytest.raises(ValueError, match="H1 source coverage"):
        subject.check_calendar()
