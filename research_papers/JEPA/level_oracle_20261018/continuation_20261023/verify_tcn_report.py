"""Independently reconcile every exported report row to archived ledgers/coverage."""
from pathlib import Path
import csv
import hashlib
import json
import math
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent
ROOT = HERE / "evidence/tcn_row_mixed_calendar_v1_evaluation"


def main():
    manifest = json.loads((HERE / "tcn_evidence_manifest.json").read_bytes())
    for item in manifest["files"]:
        assert hashlib.sha256((HERE / item["copy"]).read_bytes()).hexdigest() == item["sha256"]
    counts, inputs = {}, {}
    for suffix, expected in (("monthly", 324), ("policy_ticker", 36), ("pooled", 12)):
        path = REPORT / f"TCN_ROW_MIXED_CALENDAR_RESULT_20261023_{suffix}.csv"
        inputs[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
        rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
        assert len(rows) == expected
        seen = set()
        for row in rows:
            key = (row["period"], row["policy"], row.get("ticker"), row.get("month"))
            assert key not in seen
            seen.add(key)
            period = "validation" if row["period"] == "2025" else "test"
            policy = row["policy"]
            def selected(item):
                return (("ticker" not in row or item["ticker"] == row["ticker"])
                        and ("month" not in row or item["date"][:6] == row["month"]))
            ledger = [r for r in pq.read_table(ROOT / period / f"{policy}_ledger.parquet").to_pylist()
                      if selected(r)]
            daily = [r for r in pq.read_table(ROOT / period / f"{policy}_daily_coverage.parquet").to_pylist()
                     if selected(r)]
            assert int(row["trades"]) == len(ledger)
            observable = [r for r in daily if r["status"] == "OBSERVABLE"]
            fills = sum(r["filled"] > 0 for r in observable)
            for name, value in dict(expected_days=len(daily), observable_days=len(observable),
                                    days_with_fill=fills, observable_days_without_fill=len(observable)-fills,
                                    missing_days=len(daily)-len(observable)).items():
                assert int(row[name]) == value, (key, name)
            for cost in ("base", "adverse"):
                values = [r[f"net_{cost}"] for r in ledger]
                net = math.fsum(values)
                assert math.isclose(float(row[f"{cost}_net_usd"]), net, abs_tol=1e-7), key
                gains = math.fsum(v for v in values if v > 0)
                losses = -math.fsum(v for v in values if v < 0)
                pf = gains / losses if losses else None
                if pf is None:
                    assert row[f"{cost}_pf"] == "", key
                else:
                    assert math.isclose(float(row[f"{cost}_pf"]), pf, abs_tol=1e-10), key
                assert (row[f"{cost}_pf_infinite"] == "True") == (gains > 0 and losses == 0)
            if "positive_months" in row:
                positive = sum(math.fsum(r["net_base"] for r in ledger if r["date"][:6] == month) > 0
                               for month in sorted({r["date"][:6] for r in daily}))
                assert int(row["positive_months"]) == positive
                if row["period"] == "2026H1":
                    economic = (float(row["base_net_usd"]) > 0 and float(row["adverse_net_usd"]) > 0
                                and row["base_pf"] != "" and float(row["base_pf"]) >= 1.2
                                and len(ledger) >= 60 and positive >= 3)
                    assert (row["h1_economic_criterion_pass"] == "True") == economic
                assert (row["daily_criterion_pass"] == "True") == (fills == len(daily))
        counts[suffix] = len(rows)
    result = dict(status="PASS_REPORT_CSV_RECONCILIATION_TO_ARCHIVED_LEDGERS", rows=counts,
                  csv_sha256=inputs, archived_files_rehashed=len(manifest["files"]),
                  scope="Report reconciliation only; no market replay or new inference")
    target = HERE / "tcn_report_verification.json"
    content = (json.dumps(result, indent=2) + "\n").encode()
    if target.exists():
        assert target.read_bytes() == content
    else:
        target.write_bytes(content)
    print(json.dumps({k: v for k, v in result.items() if k != "csv_sha256"}))


if __name__ == "__main__":
    main()
