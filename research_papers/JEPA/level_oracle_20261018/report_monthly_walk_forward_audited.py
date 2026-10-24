"""Descriptive tables from a completed, externally pinned monthly audit only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
import pandas as pd

STATUS = "PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES"
COMPOSITE = "VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1"
MODES = ("static", "expanding", "rolling12")
TICKERS = ("SPXW", "SPY", "QQQ")
MONTHS25 = tuple(f"2025{m:02d}" for m in range(1, 13))
MONTHS26 = tuple(f"2026{m:02d}" for m in range(1, 7))
MISSING = {(t, d) for t in ("QQQ", "SPY") for d in ("20260401", "20260409", "20260415")}
ECON_COLUMNS = ["ticker", "date", "exit_i", "net_base", "net_adverse", "hold_minutes", "reason"]


def require(ok, message):
    if not bool(ok):
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value):
    require(isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value), "Invalid SHA256")
    return value


def absolute(value):
    path = Path(value)
    require(path.is_absolute(), "Absolute path required")
    return path.resolve()


def read_json(path):
    def invalid(value):
        raise ValueError("Nonfinite JSON constant: " + value)
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=invalid)


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def flatten(groups):
    require(isinstance(groups, dict) and groups, "Missing audited inventory")
    result = {}
    for group in groups.values():
        require(isinstance(group, dict), "Invalid inventory category")
        for value, expected in group.items():
            path = str(absolute(value))
            require(path not in result or result[path] == expected, "Conflicting inventory hash")
            result[path] = digest(expected)
    return result


class Inputs:
    def __init__(self):
        self.consumed = {}
        self.identities = {}

    def check(self, path, expected):
        logical = Path(path).absolute()
        resolved = logical.resolve()
        key = str(logical)
        require(key not in self.identities or self.identities[key] == str(resolved),
                "Source path target changed")
        require(str(resolved) not in self.consumed or self.consumed[str(resolved)] == expected,
                "Conflicting consumed hash")
        require(sha(resolved) == digest(expected), "Source SHA mismatch: " + str(resolved))
        self.identities[key] = str(resolved)
        self.consumed[str(resolved)] = expected
        return resolved

    def recheck(self):
        for logical, resolved in self.identities.items():
            require(str(Path(logical).resolve()) == resolved, "Source path target changed")
        for path, expected in self.consumed.items():
            require(sha(path) == expected, "Source changed after consumption: " + path)


def equal(actual, expected, context):
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), context + ": keys differ")
        for key in expected:
            equal(actual[key], expected[key], context + "/" + key)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), context + ": list differs")
        for left, right in zip(actual, expected):
            equal(left, right, context)
    elif isinstance(expected, float):
        require(type(actual) in (int, float) and math.isfinite(actual)
                and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-8), context + ": value differs")
    else:
        require(type(actual) is type(expected) and actual == expected, context + ": value differs")


def economic_summary(frame):
    result = {"trades": len(frame)}
    for field in ("net_base", "net_adverse"):
        values = frame[field].to_numpy(float)
        require(np.isfinite(values).all(), "Nonfinite ledger reward")
        gains, losses = float(values[values > 0].sum()), float(-values[values < 0].sum())
        curve = np.r_[0.0, np.cumsum(values)]
        result.update({field: float(values.sum()), field + "_pf": gains / losses if losses else None,
                       field + "_pf_infinite": gains > 0 and losses == 0,
                       field + "_win_rate": float((values > 0).mean()) if len(values) else None,
                       field + "_max_drawdown": float(np.max(np.maximum.accumulate(curve) - curve))})
    require(not len(frame) or np.isfinite(frame.hold_minutes.to_numpy(float)).all(), "Nonfinite holding")
    result["holding_minutes"] = {
        key: float(getattr(frame.hold_minutes, key)()) if len(frame) else None
        for key in ("min", "median", "max")}
    result["exit_reasons"] = {
        reason: {"trades": int((frame.reason == reason).sum()),
                 "net_base": float(frame.loc[frame.reason == reason, "net_base"].sum()),
                 "net_adverse": float(frame.loc[frame.reason == reason, "net_adverse"].sum())}
        for reason in ("TARGET", "STOP", "EOD")} if len(frame) else {}
    return result


def summarize(rows, ledger):
    available = [r for r in rows if r["source_status"] == "COMPLETE"]
    missing = len(rows) - len(available)
    active = sum(r["trades"] > 0 for r in available)
    zero = len(available) - active
    economy = economic_summary(ledger)
    equal(economy["trades"], sum(r["trades"] for r in available), "Period trades")
    for field in ("net_base", "net_adverse"):
        equal(economy[field], float(sum(r[field] for r in available)), "Period " + field)
    return dict(expected_ticker_days=len(rows), available_ticker_days=len(available),
                missing_no_evaluable=missing, available_days_with_fill=active,
                available_days_without_fill=zero, observable_daily_pass=bool(available) and zero == 0,
                full_calendar_daily_status=("NO_EVALUABLE_MISSING_SOURCE" if missing else
                    "PASS" if available and zero == 0 else "FAIL_OBSERVED_ZERO"),
                daily_requirement_satisfied=bool(available) and missing == 0 and zero == 0,
                available_economics=economy,
                net_base_per_available_day=economy["net_base"] / len(available) if available else None,
                missing_day_economics=None)


def validate_audit(audit):
    require(audit.get("status") == STATUS, "Completed monthly audit PASS required")
    require(audit.get("development_seen") is True and audit.get("promotion_approved") is False,
            "Research scope flags differ")
    binding, audited = audit["binding"], audit["audited"]
    months = tuple(binding["completed_months"])
    require(months in (MONTHS25, MONTHS25 + MONTHS26), "Exact audited months required")
    require(audited.get("modes") == list(MODES)
            and audited.get("scheduler_ledgers_economics_reconstructed") is True, "Audited modes/economics differ")
    if months == MONTHS25:
        counts = dict(months=12, unique_fit_windows=24, calendar_ticker_days=750)
        require(audit.get("scope") in (None, "VALIDATION_2025")
                and audited.get("months") == 12
                and audited.get("validation_selection_reconstructed") is True
                and audited.get("validation_period_report_reconstructed") is True,
                "Validation scope/reconstruction differs")
    else:
        counts = dict(new_months=6, new_unique_fit_windows=12, total_unique_fit_windows=36,
                      models_used_test=13, calendar_ticker_days=369,
                      available_ticker_days=363, missing_no_evaluable=6)
        require(audit.get("scope") == COMPOSITE and audited.get("new_months") == 6
                and audited.get("selection_reused_without_test_reselection") is True
                and audited.get("test_period_report_reconstructed") is True, "Composite scope differs")
        require(audited.get("missing_identities") == sorted([list(k) for k in MISSING]),
                "Audited missing identities differ")
    require(all(type(audited.get(key)) is int and audited[key] == value for key, value in counts.items()),
            "Audited scope counts differ")
    return months


def calendar(index, months):
    index = index.copy()
    index["date"] = index.date.astype(str)
    require(len(index) == 2625 and (index.status == "COMPLETE").sum() == 2619
            and set(index.ticker) == set(TICKERS)
            and index.status.isin(["COMPLETE", "MISSING_SOURCE"]).all()
            and index.date.str.fullmatch(r"\d{8}").all()
            and not index.duplicated(["ticker", "date"]).any(), "Global index coverage differs")
    missing = set(zip(index.loc[index.status == "MISSING_SOURCE", "ticker"],
                      index.loc[index.status == "MISSING_SOURCE", "date"]))
    require(missing == MISSING, "Missing identities differ")
    for year, expected in (("2025", 750), ("2026", 369)):
        subset = index[index.date.str.startswith(year)]
        require(len(subset) == expected and set(subset.date.str[:6]) == set(MONTHS25 if year == "2025" else MONTHS26),
                "Period calendar differs")
        require(all((subset.ticker == ticker).sum() == expected // 3 for ticker in TICKERS),
                "Ticker calendar count differs")
        dates = [set(subset.loc[subset.ticker == ticker, "date"]) for ticker in TICKERS]
        require(dates[0] == dates[1] == dates[2], "Ticker calendars differ")
    selected = index[index.date.str[:6].isin(months)]
    return {(r.ticker, r.date): r.status for r in selected.itertuples()}


class Reporter:
    def __init__(self, root, audit_path, audit_sha):
        self.inputs = Inputs()
        self.root = absolute(root)
        audit_path = self.inputs.check(absolute(audit_path), audit_sha)
        self.audit = read_json(audit_path)
        self.months = validate_audit(self.audit)
        self.binding = self.audit["binding"]
        require(absolute(self.binding["monthly_root"]) == self.root, "Monthly root differs")
        self.inventory = flatten(self.audit["verified_files"])
        if self.months != MONTHS25:
            prior = self.audit["prior_validation_audit"]
            require(prior.get("scope") == "VALIDATION_2025" and prior.get("inventory_rehashed") is True
                    and prior.get("reconstruction_inherited_not_repeated") is True, "Prior scope differs")
            prior_path = self.consume(absolute(prior["path"]), prior["sha256"])
            old = read_json(prior_path)
            require(validate_audit(old) == MONTHS25, "Prior months differ")
            for key in ("monthly_root", "session_root", "run_contract_sha256", "session_audit_sha256", "index_sha256"):
                require(old["binding"][key] == self.binding[key], "Prior binding differs: " + key)
            require(all(self.inventory.get(p) == h for p, h in flatten(old["verified_files"]).items()),
                    "Prior inventory not contained in composite")
        contract_path = self.consume(self.root / "run_contract.json", self.binding["run_contract_sha256"])
        self.contract = read_json(contract_path)
        require(self.contract.get("version") == "MONTHLY_NET_WALK_FORWARD_V1"
                and self.contract.get("seed") == 20261018 and self.contract.get("features") == 1954,
                "Monthly contract differs")
        source = self.contract["source_audit"]
        require(source["sha256"] == self.binding["session_audit_sha256"], "Source audit binding differs")
        source_audit = read_json(self.consume(absolute(source["path"]), source["sha256"]))
        require(source_audit.get("status") == "PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT"
                and source_audit["binding"] == source["binding"], "Source audit authority differs")
        sb = source_audit["binding"]
        session = absolute(self.binding["session_root"])
        require(absolute(sb["engine_root"]) == session and sb["index_sha256"] == self.binding["index_sha256"],
                "Session root/index differs")
        engine = absolute(self.contract["engine_root"])
        feature = absolute(self.contract["feature_root"])
        require(engine == session and feature == absolute(sb["feature_root"]),
                "Contract/source roots differ")
        self.protected_roots = {self.root, session, engine, feature}
        require(all(p != Path(p.anchor) for p in self.protected_roots), "Disk root prohibited")
        index_path = self.consume(session / "index.parquet", self.binding["index_sha256"])
        self.expected = calendar(pd.read_parquet(index_path, columns=["ticker", "date", "status"]), self.months)
        self.freeze = self.json_member("validation_freeze")
        selected = self.freeze.get("selected_mode")
        require(selected is None or selected in MODES, "Unknown frozen mode")
        require(self.freeze.get("status") == ("FAIL_NO_DAILY_COMPLIANT_MODE" if selected is None else "SELECTED_RESEARCH_MODE")
                and self.freeze.get("approved") is False
                and self.freeze.get("outcomes_2026_used_for_mode_selection") is False,
                "Freeze scope differs")
        self.authority = dict(path=str(audit_path), sha256=audit_sha, binding=self.binding,
                              scope="VALIDATION_2025" if self.months == MONTHS25 else COMPOSITE)

    def consume(self, path, expected=None):
        path = Path(path)
        target = str(path.resolve())
        require(target in self.inventory, "File absent from audited inventory: " + target)
        pinned = self.inventory[target]
        require(expected is None or pinned == expected, "Inventory binding differs")
        return self.inputs.check(path, pinned)

    def member(self, name, suffix):
        marker = self.root / (name + ".complete.json")
        require(marker.resolve().is_relative_to(self.root), "Marker escapes monthly root")
        record = read_json(self.consume(marker))
        require(record.get("status") == "COMPLETE" and record.get("binding") == self.binding["run_contract_sha256"]
                and bool(record.get("files")), "Incomplete artifact seal")
        members = {}
        for relative, expected in record["files"].items():
            require(not Path(relative).is_absolute(), "Absolute seal member")
            target = (self.root / relative).resolve()
            require(target.is_relative_to(self.root) and self.inventory.get(str(target)) == digest(expected),
                    "Seal escapes root or audited inventory")
            require(str(target) not in members, "Duplicate normalized seal member")
            members[str(target)] = expected
        path = self.root / (name + suffix)
        require(str(path.resolve()) in members, "Required artifact absent from seal")
        return self.consume(path, members[str(path.resolve())])

    def json_member(self, name):
        return read_json(self.member(name, ".json"))

    def collect(self):
        daily_out, monthly, periods, attempts_all, ledgers_all = [], [], [], [], []
        daily_by_mode = {mode: [] for mode in MODES}
        for stamp in self.months:
            daily = self.json_member("months/" + stamp + "/daily")
            economics = self.json_member("months/" + stamp + "/economics")
            require(set(daily) == set(MODES) and set(economics) == set(MODES), "Monthly modes differ")
            expected = {k: v for k, v in self.expected.items() if k[1].startswith(stamp)}
            require(expected and set(k[0] for k in expected) == set(TICKERS), "Empty ticker month")
            for mode in MODES:
                rows = daily[mode]
                keys = [(r["ticker"], r["date"]) for r in rows]
                require(len(keys) == len(set(keys)) and set(keys) == set(expected), "Daily calendar differs")
                month_frames, month_attempts = [], []
                for row in rows:
                    key = row["ticker"], row["date"]
                    require(row["source_status"] == expected[key], "Daily source status differs")
                    out = dict(mode=mode, **row)
                    if row["source_status"] == "MISSING_SOURCE":
                        require(row["trades"] == 0 and row["net_base"] == 0 and row["net_adverse"] == 0,
                                "Missing structural economics differ")
                        out.update(evaluation_status="NO_EVALUABLE", trades=None, net_base=None,
                                   net_adverse=None, attempts=None, no_fill_attempts=None)
                    else:
                        name = f"ledgers/{stamp}/{mode}/{key[0]}/{key[1]}"
                        attempts = pd.read_parquet(self.member(name, "_attempts.parquet"))
                        ledger = pd.read_parquet(self.member(name, "_ledger.parquet"))
                        for frame in (attempts, ledger):
                            require(set(ECON_COLUMNS + ["mode", "status", "action_id"]).issubset(frame.columns),
                                    "Ledger schema differs")
                            require((frame.ticker == key[0]).all() and (frame.date.astype(str) == key[1]).all()
                                    and (frame["mode"] == mode).all() and not frame.action_id.duplicated().any(),
                                    "Ledger identity differs")
                        require(attempts.status.isin(["FILLED", "NO_FILL"]).all()
                                and (ledger.status == "FILLED").all(), "Attempt/ledger status differs")
                        pd.testing.assert_frame_equal(attempts.loc[attempts.status == "FILLED"].reset_index(drop=True),
                                                      ledger.reset_index(drop=True), check_exact=True)
                        require(ledger.reason.isin(["TARGET", "STOP", "EOD"]).all(), "Unknown exit reason")
                        equal(row["trades"], len(ledger), "Daily trades")
                        for field in ("net_base", "net_adverse"):
                            equal(row[field], float(ledger[field].sum()), "Daily " + field)
                        no_fill = int((attempts.status == "NO_FILL").sum())
                        out.update(evaluation_status="EVALUABLE", attempts=len(attempts), no_fill_attempts=no_fill)
                        month_frames.append(ledger)
                        month_attempts.append(attempts)
                    daily_out.append(out)
                full = ordered(month_frames)
                at = pd.concat(month_attempts, ignore_index=True) if month_attempts else pd.DataFrame()
                expected_econ = dict(overall=economic_summary(full), tickers={
                    ticker: economic_summary(full.loc[full.ticker == ticker]) for ticker in TICKERS})
                equal(economics[mode], expected_econ, "Monthly economics")
                monthly.extend(table_rows(stamp, mode, rows, full, at))
                daily_by_mode[mode].extend(rows)
                attempts_all.extend(month_attempts)
                ledgers_all.extend(month_frames)
        all_ledger = ordered(ledgers_all, modes=True)
        all_attempts = pd.concat(attempts_all, ignore_index=True) if attempts_all else pd.DataFrame()
        for year in ([2025] if self.months == MONTHS25 else [2025, 2026]):
            expected_modes = {}
            for mode in MODES:
                rows = [r for r in daily_by_mode[mode] if r["date"].startswith(str(year))]
                full = ordered([all_ledger.loc[(all_ledger["mode"] == mode)
                    & all_ledger.date.astype(str).str.startswith(str(year))]])
                at = all_attempts.loc[(all_attempts["mode"] == mode)
                    & all_attempts.date.astype(str).str.startswith(str(year))]
                expected_modes[mode] = dict(overall=summarize(rows, full), tickers={ticker: summarize(
                    [r for r in rows if r["ticker"] == ticker], full.loc[full.ticker == ticker]) for ticker in TICKERS})
                periods.extend(table_rows("2025" if year == 2025 else "2026H1", mode, rows, full, at))
            expected_report = dict(year=year, modes=expected_modes, selected_mode=self.freeze["selected_mode"],
                selection_period=2025, development_seen=True, promotion_approved=False,
                missing_sources_are_not_observed_losses=True)
            equal(self.json_member(f"reports/{year}"), expected_report, "Period report")
        self.inputs.recheck()
        return monthly, periods, sorted(daily_out, key=lambda r: (r["mode"], r["date"], r["ticker"])), all_attempts, all_ledger


def ordered(frames, modes=False):
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=ECON_COLUMNS)
    return frame.sort_values((["mode"] if modes else []) + ["date", "exit_i", "ticker"], kind="stable").reset_index(drop=True)


def table_rows(period, mode, rows, ledger, attempts):
    result = []
    for ticker in (*TICKERS, "ALL"):
        selected = rows if ticker == "ALL" else [r for r in rows if r["ticker"] == ticker]
        frame = ledger if ticker == "ALL" else ledger.loc[ledger.ticker == ticker]
        at = attempts if ticker == "ALL" or not len(attempts) else attempts.loc[attempts.ticker == ticker]
        record = summarize(selected, frame)
        if not record["available_ticker_days"]:
            record["available_economics"] = None
        record.update(period=period, mode=mode, ticker=ticker,
                      attempts=len(at) if record["available_ticker_days"] else None,
                      no_fill_attempts=int((at.status == "NO_FILL").sum()) if len(at) else
                      (0 if record["available_ticker_days"] else None))
        result.append(record)
    return result


def flat_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, dict):
            for subkey, subvalue in flat_row(value).items():
                result[key + "." + subkey] = subvalue
        else:
            result[key] = value
    return result


def write_csv(path, rows):
    rows = [flat_row(row) for row in rows]
    columns = sorted(set().union(*(row.keys() for row in rows)))
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run(root, audit, audit_sha256, out):
    reporter_sha = sha(__file__)
    root, out = absolute(root), Path(out).absolute()
    require(not out.exists() and not out.resolve().is_relative_to(root), "Fresh output outside monthly root required")
    reporter = Reporter(root, audit, audit_sha256)
    require(not any(out.resolve().is_relative_to(p) for p in reporter.protected_roots),
            "Output inside protected source root prohibited")
    out.mkdir(parents=True, exist_ok=False)
    try:
        monthly, periods, daily, attempts, ledger = reporter.collect()
        summary = dict(status="DESCRIPTIVE_TABLES_REQUIRE_COMPLETE_OUTPUT_MANIFEST",
            completion_authority="output_manifest.json", authority=reporter.authority,
            months=list(reporter.months), modes=list(MODES), tickers=list(TICKERS),
            selected_mode_cited=reporter.freeze["selected_mode"], monthly=monthly, periods=periods,
            development_seen=True, promotion_approved=False,
            costs=dict(currency="USD", multiplier=100, commission_per_side=1.30,
                       base_slippage_per_side=0.01, adverse_slippage_per_side=0.02,
                       source="Audited net columns; no quote/label reconstruction"),
            limitations=["Descriptive reconciliation only; no fit, inference or scheduler audit repeated.",
                "Conditional on the completed audit and sealed score vectors; all periods are seen development.",
                "Only consumed artifacts are rehashed before and after; other audited inventory entries are references.",
                "Missing-source daily economics are null; no-fill available days are observed zeros.",
                "Pooled ALL is descriptive, not a new gate or selection. No prospective/live evidence."])
        write_json(out / "summary.json", summary)
        write_csv(out / "monthly.csv", monthly)
        write_csv(out / "periods.csv", periods)
        write_csv(out / "daily.csv", daily)
        attempts.to_parquet(out / "attempts.parquet", index=False)
        ledger.to_parquet(out / "ledger.parquet", index=False)
        reporter.inputs.recheck()
        write_json(out / "source_inventory.json", dict(consumed_rehashed_before_after=reporter.inputs.consumed,
            audited_references_not_all_rehashed=reporter.inventory))
        outputs = {p.name: dict(sha256=sha(p), bytes=p.stat().st_size) for p in sorted(out.iterdir())}
        reporter.inputs.recheck()
        require(sha(__file__) == reporter_sha, "Reporter code changed during run")
        write_json(out / "output_manifest.json", dict(status="COMPLETE", files=outputs,
            reporter_sha256=reporter_sha, audit_sha256=audit_sha256,
            monthly_rows=len(monthly), period_rows=len(periods), daily_rows=len(daily),
            attempt_rows=len(attempts), ledger_rows=len(ledger)))
        return summary
    except BaseException as exc:
        write_json(out / "failure.json", dict(status="FAILED_OR_INTERRUPTED_PRESERVED", error=repr(exc)))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monthly-root", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--audit-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.monthly_root, args.audit, args.audit_sha256, args.out)
    print(json.dumps({"status": result["status"], "months": result["months"]}))


if __name__ == "__main__":
    main()
