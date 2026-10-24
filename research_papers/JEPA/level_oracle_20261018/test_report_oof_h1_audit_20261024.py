"""Artificial audit JSON fixtures only; never reads market artifacts."""

import copy
import json
from pathlib import Path

import pytest

import report_oof_h1_audit_20261024 as report


def observed(values):
    result = {"trades": len(values)}
    for field, adjustment in (("net_base", 0), ("net_adverse", -2)):
        vals = [x + adjustment for x in values]
        gains = sum(x for x in vals if x > 0)
        losses = -sum(x for x in vals if x < 0)
        result.update(
            {
                field: sum(vals),
                field + "_gross_gains": gains,
                field + "_gross_losses": losses,
                field + "_profit_factor": gains / losses if losses else None,
                field + "_pf_infinite": gains > 0 and losses == 0,
            }
        )
    return result


def cover(days):
    complete = [r for r in days if r["source_status"] == "COMPLETE"]
    missing = len(days) - len(complete)
    zero = sum(d["trades"] == 0 for d in complete)
    return {
        "expected_days": len(days),
        "available_days": len(complete),
        "missing_days": missing,
        "available_days_without_fill": zero,
        "observable_daily_pass": bool(complete) and zero == 0,
        "universal_daily_pass": bool(complete) and not missing and zero == 0,
        "universal_daily_status": "NO_EVALUABLE"
        if missing
        else ("FAIL" if zero else "PASS"),
    }


@pytest.fixture
def audit():
    months = []
    all_values = {(p, t): [] for p in report.POLICIES for t in report.TICKERS}
    all_days = {p: [] for p in report.POLICIES}
    # Deliberately artificial dates: 123 dates total, not an exchange calendar claim.
    for month, count in zip(report.MONTHS, (21, 19, 22, 21, 20, 20)):
        policies = {}
        for policy in report.POLICIES:
            daily, values = [], {t: [] for t in report.TICKERS}
            for ticker in report.TICKERS:
                for day in range(1, count + 1):
                    date = month + f"{day:02d}"
                    row = dict(ticker=ticker, date=date)
                    if (ticker, date) in report.MISSING:
                        row.update(
                            source_status="MISSING_SOURCE",
                            trades=None,
                            net_base=None,
                            net_adverse=None,
                        )
                    else:
                        offered = [] if day == 2 else [5 if day % 2 else -3]
                        values[ticker].extend(offered)
                        row.update(source_status="COMPLETE", **observed(offered))
                    daily.append(row)
            policies[policy] = dict(
                daily=daily,
                observed=observed(sum(values.values(), [])),
                coverage=cover(daily),
                by_ticker={
                    t: dict(
                        observed=observed(values[t]),
                        coverage=cover([d for d in daily if d["ticker"] == t]),
                    )
                    for t in report.TICKERS
                },
            )
            for ticker in report.TICKERS:
                all_values[policy, ticker].extend(values[ticker])
            all_days[policy].extend(daily)
        months.append(dict(target_month=month, policies=policies))
    policies = {}
    for policy in report.POLICIES:
        policies[policy] = dict(
            coverage=cover(all_days[policy]), economic_gate_status="FAIL", by_ticker={}
        )
        for ticker in report.TICKERS:
            policies[policy]["by_ticker"][ticker] = dict(
                observed=observed(all_values[policy, ticker]),
                coverage=cover([d for d in all_days[policy] if d["ticker"] == ticker]),
                positive_months=sum(
                    m["policies"][policy]["by_ticker"][ticker]["observed"]["net_base"]
                    > 0
                    for m in months
                ),
                economic_gate_status="FAIL",
            )
    return dict(
        status="PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_FULL_H1",
        scope="OOF_OFFSETS_AND_ECONOMIC_EXECUTION_GIVEN_AUDITED_BASE_SCORES",
        binding=dict(audited_months=list(report.MONTHS)),
        winner_selected=None,
        development_seen=True,
        base_fit_reproduced=False,
        base_inference_reproduced=False,
        raw_quote_replay=False,
        technical_ready=False,
        promotion_approved=False,
        months=months,
        policies=policies,
    )


def test_all_series_and_missing(audit):
    data = report.tables(audit)
    assert len(data["monthly"]) == 108 and len(data["periods"]) == 18
    april = next(
        r for r in data["monthly"] if r["month"] == "202604" and r["ticker"] == "QQQ"
    )
    assert april["missing_dates"] == ["20260401", "20260409", "20260415"]
    assert april["coverage"]["missing_days"] == 3
    assert april["coverage"]["available_days_without_fill"] == 1
    assert april["coverage"]["universal_daily_status"] == "NO_EVALUABLE"


@pytest.mark.parametrize(
    "key,value",
    [
        ("status", "PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_DECLARED_MONTHS"),
        ("scope", "OTHER"),
        ("winner_selected", "static"),
        ("development_seen", False),
        ("base_fit_reproduced", True),
        ("base_inference_reproduced", True),
        ("raw_quote_replay", True),
        ("technical_ready", True),
        ("promotion_approved", True),
        ("technical_ready", 0),
    ],
)
def test_reject_authority(audit, key, value):
    audit[key] = value
    with pytest.raises(ValueError):
        report.tables(audit)


@pytest.mark.parametrize(
    "kind",
    [
        "month",
        "policy",
        "ticker",
        "duplicate",
        "missing_zero",
        "unexpected_missing",
        "total",
        "pf",
        "coverage",
        "nonfinite",
    ],
)
def test_reject_incoherence(audit, kind):
    p = audit["months"][0]["policies"]["static__control"]
    if kind == "month":
        audit["months"].pop()
    elif kind == "policy":
        del p["by_ticker"]["SPY"]
        del audit["policies"]["rolling12__corrected"]
    elif kind == "ticker":
        del p["by_ticker"]["SPY"]
    elif kind == "duplicate":
        p["daily"].append(copy.deepcopy(p["daily"][0]))
    elif kind == "missing_zero":
        row = next(
            r
            for r in audit["months"][3]["policies"]["static__control"]["daily"]
            if r["source_status"] == "MISSING_SOURCE"
        )
        row["net_base"] = 0
    elif kind == "unexpected_missing":
        p["daily"][0]["source_status"] = "MISSING_SOURCE"
    elif kind == "total":
        audit["policies"]["static__control"]["by_ticker"]["SPY"]["observed"][
            "net_base"
        ] += 1
    elif kind == "pf":
        p["observed"]["net_base_profit_factor"] = 900
    elif kind == "coverage":
        p["coverage"]["missing_days"] = 1
    elif kind == "nonfinite":
        p["daily"][0]["net_base"] = float("nan")
    with pytest.raises(ValueError):
        report.tables(audit)


def test_pf_null_and_infinite():
    for values in ([], [5], [-3]):
        report.metrics(observed(values))
    broken = observed([5])
    broken["net_base_profit_factor"] = float("inf")
    with pytest.raises(ValueError):
        report.metrics(broken)


def test_export_and_source_guards(audit, tmp_path):
    source = tmp_path / "source" / "audit.json"
    source.parent.mkdir()
    source.write_text(json.dumps(audit), encoding="utf-8")
    digest = report.sha(source)
    with pytest.raises(ValueError):
        report.run(source, "0" * 64, tmp_path / "wrong")
    with pytest.raises(ValueError):
        report.run(source, digest, source.parent / "inside")
    assert not (tmp_path / "wrong").exists() and not (source.parent / "inside").exists()
    output = tmp_path / "report"
    report.run(source, digest, output)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["monthly_rows"] == 108 and manifest["h1_rows"] == 18
    assert set(manifest["files"]) == {
        "tables.json",
        "monthly_net_usd.png",
        "monthly_net_usd.svg",
    }
    for name, info in manifest["files"].items():
        assert report.sha(output / name) == info["sha256"]
    assert report.sha(source) == digest
    with pytest.raises(ValueError):
        report.run(source, digest, output)


def test_changed_source_no_success(audit, tmp_path, monkeypatch):
    source = tmp_path / "audit.json"
    source.write_text(json.dumps(audit), encoding="utf-8")
    output = tmp_path.parent / (tmp_path.name + "_changed_output")
    monkeypatch.setattr(
        report, "figure", lambda data, out: source.write_text("{}", encoding="utf-8")
    )
    with pytest.raises(ValueError):
        report.run(source, report.sha(source), output)
    assert not (output / "manifest.json").exists()


def test_changed_code_no_success(audit, tmp_path, monkeypatch):
    source = tmp_path / "audit.json"
    source.write_text(json.dumps(audit), encoding="utf-8")
    output = tmp_path.parent / (tmp_path.name + "_changed_code_output")
    original_sha = report.sha
    changed = []

    def observed_sha(path):
        if changed and Path(path).resolve() == Path(report.__file__).resolve():
            return "0" * 64
        return original_sha(path)

    monkeypatch.setattr(report, "sha", observed_sha)
    monkeypatch.setattr(report, "figure", lambda data, out: changed.append(True))
    with pytest.raises(ValueError, match="Reporter code changed"):
        report.run(source, original_sha(source), output)
    assert not (output / "manifest.json").exists()
