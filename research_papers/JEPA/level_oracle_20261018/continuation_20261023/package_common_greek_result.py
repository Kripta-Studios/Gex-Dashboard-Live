"""Preserve audited comparison outputs; descriptive tables, no fit or selection."""

from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json

import pandas as pd

HERE = Path(__file__).resolve().parent
CODE = HERE.parent
ROOT = Path("D:/GexResearchArtifacts/level_oracle_20261018")
SOURCE = ROOT / "common_greek_comparison_v1"
OUT = HERE / "common_greek_result"
AUDIT_SHA = "45caae6c11cdce9306284367e7742d9dbe17e03a8afeb52eff447b3408758a0d"
REPORT_SHA = "6086af9fba7d5a7423a36eda120c9873415a9c3f3f5b61d9fea0bfa3ab47183c"
GLOBAL_SHA = "ad916c5695e165693c9843d206329732dde1d9149fc8ee0f9354818caf399d6d"
POLICIES = ("cue_net__0", "common_greek_net__0")


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def json_read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, record):
    with Path(path).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def write_csv(path, rows):
    with Path(path).open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    monthly_path = CODE / "COMMON_GREEK_COMPARISON_MONTHLY_20261023.csv"
    annual_path = CODE / "COMMON_GREEK_COMPARISON_ANNUAL_20261023.csv"
    require(not OUT.exists() and not monthly_path.exists() and not annual_path.exists(),
            "Fresh archival and table outputs required")
    consumed = {}

    def consume(path, expected=None):
        path = Path(path).resolve()
        observed = sha(path)
        require(expected is None or observed == expected, "Source hash changed: " + str(path))
        require(str(path) not in consumed or consumed[str(path)] == observed, "Conflicting source")
        consumed[str(path)] = observed
        return path

    audit_path = consume(ROOT / "common_greek_comparison_v1_economic_audit_02/audit.json", AUDIT_SHA)
    report_path = consume(ROOT / "common_greek_comparison_v1_monthly_report_20261023_01/summary.json", REPORT_SHA)
    global_path = consume(SOURCE / "comparison.complete.json", GLOBAL_SHA)
    audit, report, complete = json_read(audit_path), json_read(report_path), json_read(global_path)
    require(audit["status"] == "PASS_INDEPENDENT_COMMON_GREEK_COMPARISON_ECONOMIC_AUDIT",
            "Independent audit required")
    require(report["status"] == "COMPLETE_DESCRIPTIVE_MONTHLY_REPORT"
            and len(report["months"]) == 108, "Complete descriptive report required")
    members = {Path(name).as_posix(): value for name, value in complete["files"].items()}
    require(len(members) == len(complete["files"]), "Global membership collision")
    selected_pins = {str((SOURCE / name).resolve()): expected for name, expected in members.items()}
    selected_pins[str(global_path)] = GLOBAL_SHA
    selected_pins[str((SOURCE / "training_provenance.json").resolve())] = audit["binding"]["training_provenance_sha256"]
    for directory, prefix in (("market_cue_control_v1", "cue"),
                              ("common_greek_control_resource_v1", "greek")):
        model_root = ROOT / directory
        for name, field in (("run_contract.json", prefix + "_contract_sha256"),
                            ("model.complete.json", prefix + "_model_completion_sha256")):
            source = consume(model_root / name, audit["binding"][field])
            selected_pins[str(source)] = audit["binding"][field]
        marker = json_read(model_root / "model.complete.json")
        for name, expected in marker["files"].items():
            selected_pins[str((model_root / name).resolve())] = expected
    monthly = []
    for row in report["months"]:
        item = {key: row[key] for key in (
            "policy", "ticker", "month", "expected_days", "available_days", "missing_days",
            "observed_days_without_fill", "observable_daily_pass", "universal_daily_status",
            "observed_positive_days", "available_daily_close_drawdown_usd",
            "best_available_day_usd", "worst_available_day_usd")}
        for scenario in ("base", "adverse"):
            item.update({scenario + "_" + key: value for key, value in row[scenario].items()})
        item["no_fill_dates"] = json.dumps(row["no_fill_dates"])
        item["missing_dates"] = json.dumps(row["missing_dates"])
        monthly.append(item)
    require(len({(row["policy"], row["ticker"], row["month"]) for row in monthly}) == 108,
            "Duplicate monthly identity")
    annual = []
    for year in (2025, 2026):
        period = json_read(consume(SOURCE / f"period{year}.json", audit["binding"][f"period{year}_sha256"]))
        for policy in POLICIES:
            for ticker in ("ALL", "QQQ", "SPXW", "SPY"):
                values = period["policies"][policy][ticker]
                rows = [row for row in monthly if row["policy"] == policy
                        and row["month"].startswith(str(year))
                        and (ticker == "ALL" or row["ticker"] == ticker)]
                economics = values["available_economics"]
                for scenario in ("base", "adverse"):
                    require(abs(sum(row[scenario + "_net_usd"] for row in rows)
                                - economics["net_" + scenario]) <= 1e-7, "Monthly/annual net differs")
                months = sorted({row["month"] for row in rows})
                counts = {scenario: sum(sum(row[scenario + "_net_usd"] for row in rows
                                           if row["month"] == month) > 0 for month in months)
                          for scenario in ("base", "adverse")}
                item = {"year": year, "policy": policy, "ticker": ticker,
                        **economics, **{key: value for key, value in values["coverage"].items()
                                        if not key.endswith("_keys")},
                        "months": len(months), "positive_months_base": counts["base"],
                        "positive_months_adverse": counts["adverse"]}
                applicable = year == 2026 and ticker != "ALL"
                pf = economics["net_base_profit_factor"]
                gates = {"base_net_positive": economics["net_base"] > 0,
                         "adverse_net_positive": economics["net_adverse"] > 0,
                         "base_pf_at_least_1_20": bool(economics["net_base_pf_infinite"]
                                                       or (pf is not None and pf >= 1.2)),
                         "trades_at_least_60": economics["trades"] >= 60,
                         "positive_base_months_at_least_3": counts["base"] >= 3}
                item.update({"gate_" + key: value if applicable else None for key, value in gates.items()})
                item["economic_gate_status"] = ("PASS" if all(gates.values()) else "FAIL") if applicable else "NOT_APPLICABLE"
                item["joint_observable_status"] = (
                    "PASS" if all(gates.values()) and values["coverage"]["observable_daily_pass"] else "FAIL"
                ) if applicable else "NOT_APPLICABLE"
                annual.append(item)
    require(len(annual) == 16, "Annual table count")
    OUT.mkdir()
    write_csv(monthly_path, monthly)
    write_csv(annual_path, annual)

    daily, frames = [], []
    day_members = sorted(name for name in members if name.startswith("days/")
                         and name.endswith(".json") and not name.endswith(".complete.json"))
    require(len(day_members) == 1119, "Full daily calendar required")
    for relative in day_members:
        record = json_read(consume(SOURCE / relative, members[relative]))
        require(set(record) == set(POLICIES), "Daily policy identity")
        for policy in POLICIES:
            row = record[policy]
            scalar = {key: value for key, value in row.items() if key != "calibration"}
            scalar = {"policy": policy, **scalar,
                      "observed_net_base": row["net_base"] if row["source_status"] == "COMPLETE" else None,
                      "observed_net_adverse": row["net_adverse"] if row["source_status"] == "COMPLETE" else None}
            daily.append(scalar)
            attempts_relative = f"days/{row['ticker']}/{row['date']}.{policy}.parquet"
            require(attempts_relative in members, "Attempts absent from global seal")
            frame = pd.read_parquet(consume(SOURCE / attempts_relative, members[attempts_relative]))
            require(len(frame) == row["attempts"], "Daily attempt count differs")
            require(int((frame.status == "FILLED").sum()) == row["trades"], "Daily fill count differs")
            frame.insert(0, "date", row["date"])
            frame.insert(0, "ticker", row["ticker"])
            frame.insert(0, "policy", policy)
            if len(frame):
                frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    combined_path = OUT / "all_attempts.parquet"
    combined.to_parquet(combined_path, index=False)
    pd.testing.assert_frame_equal(combined, pd.read_parquet(combined_path), check_exact=True)
    write_csv(OUT / "daily_coverage_and_economics.csv", daily)
    require(len(daily) == 2238, "Full daily policy calendar required")

    selected = ["common_greek_comparison_v1/" + name for name in (
        "freeze.json", "completion.json", "comparison.complete.json", "period2025.json",
        "period2025.complete.json", "period2026.json", "period2026.complete.json",
        "test_freeze.json", "training_provenance.json")]
    selected += ["common_greek_control_resource_v1/" + name for name in (
        "common_greek_net.txt", "model.complete.json", "run_contract.json", "export.complete.json", "fit_started.json")]
    selected += ["market_cue_control_v1/" + name for name in (
        "cue_net.txt", "model.complete.json", "run_contract.json", "matrix.complete.json", "fit_started.json")]
    selected += ["common_greek_comparison_v1_economic_audit_02/audit.json",
                 "common_greek_comparison_v1_monthly_report_20261023_01/summary.json",
                 "common_greek_audit_02_root_preflight_20261023.json"]
    for folder in ("common_greek_comparison_v1_launch", "common_greek_comparison_v1_economic_audit_02_logs",
                   "common_greek_comparison_v1_monthly_report_20261023_01_logs"):
        selected += [str(path.relative_to(ROOT)).replace("\\", "/")
                     for path in sorted((ROOT / folder).iterdir()) if path.is_file()]
    archived = []
    for relative in selected:
        resolved = (ROOT / relative).resolve()
        source = consume(resolved, selected_pins.get(str(resolved)))
        record = {"source": str(source), "size_bytes": source.stat().st_size,
                  "sha256": consumed[str(source)]}
        if source.stat().st_size > 100_000_000:
            record.update(status="LOCAL_ONLY_OVER_100MB", archived=None)
        else:
            target = OUT / "evidence" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(source.read_bytes())
            require(sha(target) == record["sha256"], "Archived copy mismatch")
            record.update(status="COPIED_EXACT", archived=target.relative_to(OUT).as_posix())
        archived.append(record)
    for path, expected in consumed.items():
        require(sha(path) == expected, "Consumed source changed at archive close")
    derived = [monthly_path, annual_path, OUT / "daily_coverage_and_economics.csv", combined_path]
    manifest = {"status": "COMPLETE_COMMON_GREEK_DESCRIPTIVE_ARCHIVE", "created_utc": datetime.now(timezone.utc).isoformat(),
                "audit_sha256": AUDIT_SHA, "report_sha256": REPORT_SHA,
                "packager_sha256": sha(__file__), "copied_artifacts": archived,
                "consumed_sources": consumed,
                "derived_artifacts": [{"path": str(path.resolve()), "size_bytes": path.stat().st_size,
                                       "sha256": sha(path)} for path in derived],
                "monthly_rows": len(monthly), "annual_rows": len(annual), "daily_policy_rows": len(daily),
                "attempts_rows": len(combined), "filled_rows": int((combined.status == "FILLED").sum()),
                "nofill_rows": int((combined.status == "NO_FILL").sum()),
                "large_original_arrays_remain_local": True, "source_rehash": "PASS",
                "all_attempts_parquet_exact_readback": True, "new_fits": 0, "new_predictions": 0,
                "selection": False, "promotion_approved": False}
    write_json(OUT / "manifest.json", manifest)
    print(json.dumps({key: manifest[key] for key in ("status", "monthly_rows", "annual_rows", "daily_policy_rows", "attempts_rows", "filled_rows", "nofill_rows")}, indent=2))
    print("manifest_sha256", sha(OUT / "manifest.json"))


if __name__ == "__main__":
    main()
