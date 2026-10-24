"""Artificial contracts, index metadata and ledgers; no market inputs."""

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

import report_monthly_walk_forward_audited as report


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False), encoding="utf-8")


def toy_economics(frame):
    result = {"trades": len(frame)}
    for field in ("net_base", "net_adverse"):
        values = list(frame[field])
        profit = sum(v for v in values if v > 0)
        loss = -sum(v for v in values if v < 0)
        peak = total = dd = 0.0
        for value in values:
            total += value
            peak = max(peak, total)
            dd = max(dd, peak - total)
        result.update({field: float(sum(values)), field + "_pf": profit / loss if loss else None,
            field + "_pf_infinite": profit > 0 and loss == 0,
            field + "_win_rate": sum(v > 0 for v in values) / len(values) if values else None,
            field + "_max_drawdown": dd})
    result["holding_minutes"] = {k: float(getattr(frame.hold_minutes, k)()) if len(frame) else None
                                 for k in ("min", "median", "max")}
    result["exit_reasons"] = {reason: {"trades": int((frame.reason == reason).sum()),
        "net_base": float(frame.loc[frame.reason == reason, "net_base"].sum()),
        "net_adverse": float(frame.loc[frame.reason == reason, "net_adverse"].sum())}
        for reason in ("TARGET", "STOP", "EOD")} if len(frame) else {}
    return result


def toy_coverage(rows, frame):
    valid = [r for r in rows if r["source_status"] == "COMPLETE"]
    missing = len(rows) - len(valid)
    active = sum(r["trades"] > 0 for r in valid)
    zero = len(valid) - active
    economy = toy_economics(frame)
    return dict(expected_ticker_days=len(rows), available_ticker_days=len(valid),
        missing_no_evaluable=missing, available_days_with_fill=active, available_days_without_fill=zero,
        observable_daily_pass=bool(valid) and zero == 0,
        full_calendar_daily_status="NO_EVALUABLE_MISSING_SOURCE" if missing else
            "PASS" if valid and not zero else "FAIL_OBSERVED_ZERO",
        daily_requirement_satisfied=bool(valid) and not missing and not zero,
        available_economics=economy,
        net_base_per_available_day=economy["net_base"] / len(valid) if valid else None,
        missing_day_economics=None)


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    base = tmp_path_factory.mktemp("monthly_synthetic")
    root, session, feature = base / "monthly", base / "sessions", base / "features"
    root.mkdir()
    session.mkdir()
    feature.mkdir()
    dates = (list(pd.bdate_range("2023-01-02", periods=502).strftime("%Y%m%d"))
             + list(pd.bdate_range("2025-01-02", periods=250).strftime("%Y%m%d"))
             + list(pd.bdate_range("2026-01-02", periods=123).strftime("%Y%m%d")))
    index = pd.DataFrame([dict(ticker=t, date=d, status="MISSING_SOURCE" if (t, d) in report.MISSING else "COMPLETE")
                          for d in dates for t in report.TICKERS])
    index.to_parquet(session / "index.parquet", index=False)
    inventory = {str((session / "index.parquet").resolve()): report.sha(session / "index.parquet")}

    def pin(path):
        inventory[str(path.resolve())] = report.sha(path)

    source = base / "source_audit.json"
    sb = dict(engine_root=str(session.resolve()), feature_root=str(feature.resolve()),
              index_sha256=report.sha(session / "index.parquet"))
    save(source, dict(status="PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT", binding=sb))
    pin(source)
    contract = dict(version="MONTHLY_NET_WALK_FORWARD_V1", seed=20261018, features=1954,
                    engine_root=str(session.resolve()), feature_root=str(feature.resolve()),
                    source_audit=dict(path=str(source.resolve()), sha256=report.sha(source), binding=sb))
    save(root / "run_contract.json", contract)
    pin(root / "run_contract.json")
    contract_sha = report.sha(root / "run_contract.json")

    def seal(name, files):
        for path in files:
            pin(path)
        marker = root / (name + ".complete.json")
        save(marker, dict(status="COMPLETE", binding=contract_sha,
            files={p.relative_to(root).as_posix(): report.sha(p) for p in files}))
        pin(marker)

    def sealed_json(name, value):
        path = root / (name + ".json")
        save(path, value)
        seal(name, [path])

    sealed_json("validation_freeze", dict(status="FAIL_NO_DAILY_COMPLIANT_MODE", selected_mode=None,
                                         approved=False, outcomes_2026_used_for_mode_selection=False))
    year_rows = {year: {m: [] for m in report.MODES} for year in (2025, 2026)}
    year_ledgers = {year: {m: [] for m in report.MODES} for year in (2025, 2026)}
    for month in report.MONTHS25 + report.MONTHS26:
        daily, economic = {}, {}
        for mode_i, mode in enumerate(report.MODES):
            rows, frames = [], []
            for day in index[index.date.str.startswith(month)].itertuples():
                row = dict(ticker=day.ticker, date=day.date, source_status=day.status,
                           trades=0, net_base=0.0, net_adverse=0.0)
                if day.status == "COMPLETE":
                    prefix = f"ledgers/{month}/{mode}/{day.ticker}/{day.date}"
                    base_record = dict(ticker=day.ticker, date=day.date, mode=mode, action_id=0,
                        exit_i=80, hold_minutes=19, reason="TARGET", status="FILLED",
                        net_base=5.0 + mode_i, net_adverse=3.0 + mode_i,
                        fit_key="SYNTHETIC_ONLY")
                    # Available no-fill days are distinct from missing-source days.
                    if day.date.endswith("02"):
                        records = [{**base_record, "status": "NO_FILL", "net_base": 0.0, "net_adverse": 0.0}]
                    else:
                        records = [base_record, {**base_record, "action_id": 1, "exit_i": 110,
                            "reason": "STOP", "net_base": -2.0, "net_adverse": -4.0}]
                    attempts = pd.DataFrame(records)
                    ledger = attempts[attempts.status == "FILLED"].copy()
                    ap, lp = root / (prefix + "_attempts.parquet"), root / (prefix + "_ledger.parquet")
                    ap.parent.mkdir(parents=True, exist_ok=True)
                    attempts.to_parquet(ap, index=False)
                    ledger.to_parquet(lp, index=False)
                    seal(prefix, [ap, lp])
                    row.update(trades=len(ledger), net_base=float(ledger.net_base.sum()),
                               net_adverse=float(ledger.net_adverse.sum()))
                    frames.append(ledger)
                rows.append(row)
            full = pd.concat(frames, ignore_index=True).sort_values(["date", "exit_i", "ticker"], kind="stable")
            daily[mode] = rows
            economic[mode] = dict(overall=toy_economics(full), tickers={t: toy_economics(full[full.ticker == t])
                                                                     for t in report.TICKERS})
            year_rows[int(month[:4])][mode].extend(rows)
            year_ledgers[int(month[:4])][mode].append(full)
        sealed_json(f"months/{month}/daily", daily)
        sealed_json(f"months/{month}/economics", economic)
    for year in (2025, 2026):
        modes = {}
        for mode in report.MODES:
            full = pd.concat(year_ledgers[year][mode], ignore_index=True).sort_values(["date", "exit_i", "ticker"], kind="stable")
            rows = year_rows[year][mode]
            modes[mode] = dict(overall=toy_coverage(rows, full), tickers={t: toy_coverage(
                [r for r in rows if r["ticker"] == t], full[full.ticker == t]) for t in report.TICKERS})
        sealed_json(f"reports/{year}", dict(year=year, modes=modes, selected_mode=None, selection_period=2025,
            development_seen=True, promotion_approved=False, missing_sources_are_not_observed_losses=True))
    binding = dict(monthly_root=str(root.resolve()), session_root=str(session.resolve()),
        run_contract_sha256=contract_sha, session_audit_sha256=report.sha(source),
        index_sha256=report.sha(session / "index.parquet"), completed_months=list(report.MONTHS25))
    validation = dict(status=report.STATUS, binding=binding, verified_files={"fixture": dict(inventory)},
        audited=dict(months=12, modes=list(report.MODES), scheduler_ledgers_economics_reconstructed=True,
            unique_fit_windows=24, calendar_ticker_days=750,
            validation_selection_reconstructed=True, validation_period_report_reconstructed=True),
        development_seen=True, promotion_approved=False)
    prior = base / "validation_audit.json"
    save(prior, validation)
    pin(prior)
    composite = dict(status=report.STATUS, scope=report.COMPOSITE,
        binding={**binding, "completed_months": list(report.MONTHS25 + report.MONTHS26)},
        prior_validation_audit=dict(path=str(prior.resolve()), sha256=report.sha(prior), scope="VALIDATION_2025",
            inventory_rehashed=True, reconstruction_inherited_not_repeated=True),
        verified_files={"fixture": dict(inventory)},
        audited=dict(new_months=6, modes=list(report.MODES), scheduler_ledgers_economics_reconstructed=True,
            new_unique_fit_windows=12, total_unique_fit_windows=36, models_used_test=13,
            calendar_ticker_days=369, available_ticker_days=363, missing_no_evaluable=6,
            missing_identities=sorted([list(k) for k in report.MISSING]),
            selection_reused_without_test_reselection=True, test_period_report_reconstructed=True),
        development_seen=True, promotion_approved=False)
    audit = base / "composite_audit.json"
    save(audit, composite)
    return dict(base=base, root=root, session=session, feature=feature, prior=prior, audit=audit, index=index)


@pytest.mark.parametrize("name,months,monthly,periods,daily", [
    ("prior", 12, 144, 12, 2250), ("audit", 18, 216, 24, 3357)])
def test_complete_scopes(synthetic, tmp_path, name, months, monthly, periods, daily):
    audit = synthetic[name]
    out = tmp_path / "report"
    result = report.run(synthetic["root"], audit, report.sha(audit), out)
    manifest = report.read_json(out / "output_manifest.json")
    assert manifest["status"] == "COMPLETE"
    assert len(result["months"]) == months
    assert manifest["monthly_rows"] == monthly
    assert manifest["period_rows"] == periods
    assert manifest["daily_rows"] == daily
    assert result["selected_mode_cited"] is None
    assert {r["mode"] for r in result["monthly"]} == set(report.MODES)
    assert {r["ticker"] for r in result["monthly"]} == set(report.TICKERS) | {"ALL"}
    frame = pd.read_csv(out / "daily.csv")
    missing = frame[frame.source_status == "MISSING_SOURCE"]
    assert len(missing) == (0 if months == 12 else 18)
    assert missing[["trades", "net_base", "net_adverse", "attempts", "no_fill_attempts"]].isna().all().all()
    available_zero = frame[(frame.source_status == "COMPLETE") & (frame.trades == 0)]
    assert len(available_zero) and (available_zero.net_base == 0).all()
    assert (available_zero.no_fill_attempts == 1).all()
    assert all(report.sha(out / path) == record["sha256"] for path, record in manifest["files"].items())


def test_external_sha_before_parse(synthetic, tmp_path):
    with pytest.raises(ValueError, match="SHA mismatch"):
        report.run(synthetic["root"], synthetic["audit"], "0" * 64, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("mutation", ["status", "months", "modes", "scope", "root", "prior_binding", "prior_inventory"])
def test_reject_authority_changes(synthetic, tmp_path, mutation):
    obj = report.read_json(synthetic["audit"])
    if mutation == "status":
        obj["status"] = "RUNNING"
    elif mutation == "months":
        obj["binding"]["completed_months"].pop()
    elif mutation == "modes":
        obj["audited"]["modes"].pop()
    elif mutation == "scope":
        obj["scope"] = "PARTIAL"
    elif mutation == "root":
        obj["binding"]["monthly_root"] = str(tmp_path.resolve())
    elif mutation == "prior_binding":
        obj["binding"]["index_sha256"] = "0" * 64
    else:
        obj["verified_files"]["fixture"].pop(str((synthetic["root"] / "reports/2025.json").resolve()))
    audit = tmp_path / "bad.json"
    save(audit, obj)
    with pytest.raises(ValueError):
        report.Reporter(synthetic["root"], audit, report.sha(audit))


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "status", "economics", "missing_zero", "mode"])
def test_reject_descriptive_mismatch(synthetic, monkeypatch, mutation):
    reporter = report.Reporter(synthetic["root"], synthetic["audit"], report.sha(synthetic["audit"]))
    original = reporter.json_member

    def altered(name):
        value = copy.deepcopy(original(name))
        if name == "months/202501/daily":
            if mutation == "duplicate":
                value["static"].append(value["static"][0])
            elif mutation == "missing":
                value["expanding"].pop()
            elif mutation == "status":
                value["static"][0]["source_status"] = "MISSING_SOURCE"
            elif mutation == "mode":
                value.pop("rolling12")
        if name == "months/202501/economics" and mutation == "economics":
            value["static"]["overall"]["net_base"] += 1
        if name == "months/202604/daily" and mutation == "missing_zero":
            next(r for r in value["static"] if r["source_status"] == "MISSING_SOURCE")["net_base"] = 1.0
        return value

    monkeypatch.setattr(reporter, "json_member", altered)
    with pytest.raises(ValueError):
        reporter.collect()


def test_calendar_rejects_missing_identity(synthetic):
    index = synthetic["index"].copy()
    index.loc[(index.ticker == "QQQ") & (index.date == "20260401"), "status"] = "COMPLETE"
    with pytest.raises(ValueError):
        report.calendar(index, report.MONTHS25 + report.MONTHS26)


def test_hash_mutation_after_read(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"before")
    tracker = report.Inputs()
    tracker.check(source, report.sha(source))
    source.write_bytes(b"after")
    with pytest.raises(ValueError, match="changed after"):
        tracker.recheck()


def test_pf_and_drawdown_contract():
    frame = pd.DataFrame(dict(ticker=["QQQ"] * 3, date=["20250103"] * 3,
        exit_i=[100, 80, 90], net_base=[4.0, 5.0, -8.0], net_adverse=[2.0, 3.0, -10.0],
        hold_minutes=[4, 2, 3], reason=["TARGET", "TARGET", "STOP"]))
    economy = report.economic_summary(report.ordered([frame]))
    assert economy["net_base_max_drawdown"] == 8.0
    assert economy["net_base_pf"] == 9 / 8
    assert economy["net_adverse_max_drawdown"] == 10.0
    positive = report.economic_summary(frame[frame.net_base > 0])
    assert positive["net_base_pf"] is None and positive["net_base_pf_infinite"] is True
    empty = report.economic_summary(frame.iloc[:0])
    assert empty["net_base_pf"] is None and empty["net_base_pf_infinite"] is False
    assert empty["net_base_win_rate"] is None
    missing = report.table_rows("202604", "static", [dict(ticker="QQQ", date="20260401",
        source_status="MISSING_SOURCE", trades=0, net_base=0.0, net_adverse=0.0)], frame.iloc[:0], pd.DataFrame())
    assert next(r for r in missing if r["ticker"] == "QQQ")["available_economics"] is None


def test_fresh_output_and_failed_run_preserved(synthetic, tmp_path, monkeypatch):
    existing = tmp_path / "exists"
    existing.mkdir()
    with pytest.raises(ValueError, match="Fresh output"):
        report.run(synthetic["root"], synthetic["prior"], report.sha(synthetic["prior"]), existing)
    def fail(_self):
        raise ValueError("synthetic failure")
    monkeypatch.setattr(report.Reporter, "collect", fail)
    out = tmp_path / "failed"
    with pytest.raises(ValueError, match="synthetic failure"):
        report.run(synthetic["root"], synthetic["prior"], report.sha(synthetic["prior"]), out)
    assert report.read_json(out / "failure.json")["status"] == "FAILED_OR_INTERRUPTED_PRESERVED"
    assert not (out / "output_manifest.json").exists()


def test_inventory_conflict_and_escaped_seal(synthetic, monkeypatch):
    path = str(synthetic["audit"].resolve())
    with pytest.raises(ValueError, match="Conflicting"):
        report.flatten({"a": {path: "0" * 64}, "b": {path: "1" * 64}})
    reporter = report.Reporter(synthetic["root"], synthetic["prior"], report.sha(synthetic["prior"]))
    original = report.read_json
    def escaped(path):
        value = original(path)
        if Path(path).name == "daily.complete.json":
            value["files"]["../escape"] = "0" * 64
        return value
    monkeypatch.setattr(report, "read_json", escaped)
    with pytest.raises(ValueError, match="Seal escapes"):
        reporter.json_member("months/202501/daily")


def test_late_failure_has_no_success_manifest(tmp_path, monkeypatch):
    class FakeInputs:
        def recheck(self):
            raise ValueError("synthetic late source change")

    class FakeReporter:
        def __init__(self, *_args):
            self.binding = {"session_root": str((tmp_path / "session").resolve())}
            self.protected_roots = {(tmp_path / "session").resolve()}
            self.authority = {"synthetic_only": True}
            self.months = report.MONTHS25
            self.freeze = {"selected_mode": None}
            self.inputs = FakeInputs()

        def collect(self):
            return ([{"synthetic": True}], [{"synthetic": True}], [{"synthetic": True}],
                    pd.DataFrame({"synthetic": [1]}), pd.DataFrame({"synthetic": [1]}))

    monkeypatch.setattr(report, "Reporter", FakeReporter)
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="late source change"):
        report.run((tmp_path / "monthly").resolve(), tmp_path / "audit", "0" * 64, out)
    assert report.read_json(out / "summary.json")["status"] == "DESCRIPTIVE_TABLES_REQUIRE_COMPLETE_OUTPUT_MANIFEST"
    assert (out / "failure.json").is_file()
    assert not (out / "output_manifest.json").exists()


def test_json_rejects_nonfinite(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"net": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="Nonfinite JSON"):
        report.read_json(path)


def test_csv_json_deterministic(tmp_path):
    rows = [{"mode": "static", "pf": None, "economics": {"net": 0.0, "pf_infinite": False}}]
    for name in ("first", "second"):
        report.write_json(tmp_path / (name + ".json"), rows)
        report.write_csv(tmp_path / (name + ".csv"), rows)
    for suffix in (".json", ".csv"):
        assert (tmp_path / ("first" + suffix)).read_bytes() == (tmp_path / ("second" + suffix)).read_bytes()


@pytest.mark.parametrize("scope,field", [
    ("prior", "months"), ("prior", "unique_fit_windows"), ("prior", "calendar_ticker_days"),
    ("audit", "new_months"), ("audit", "new_unique_fit_windows"),
    ("audit", "total_unique_fit_windows"), ("audit", "models_used_test"),
    ("audit", "calendar_ticker_days"), ("audit", "available_ticker_days"),
    ("audit", "missing_no_evaluable"), ("audit", "missing_identities")])
@pytest.mark.parametrize("mutation", ["absent", "wrong"])
def test_scope_counts_required(synthetic, scope, field, mutation):
    audit = report.read_json(synthetic[scope])
    if mutation == "absent":
        audit["audited"].pop(field)
    elif field == "missing_identities":
        audit["audited"][field].pop()
    else:
        audit["audited"][field] += 1
    with pytest.raises(ValueError):
        report.validate_audit(audit)


@pytest.mark.parametrize("root_name", ["session", "feature"])
def test_source_roots_protected(synthetic, root_name):
    out = synthetic[root_name] / "forbidden_report"
    with pytest.raises(ValueError, match="protected source root"):
        report.run(synthetic["root"], synthetic["prior"], report.sha(synthetic["prior"]), out)
    assert not out.exists()
