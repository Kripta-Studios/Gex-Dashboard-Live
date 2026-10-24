"""Pinned descriptive arithmetic over the closed 2025 reporter; no market replay."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = Path("D:/GexResearchArtifacts/level_oracle_20261018/") / (
    "monthly_validation_2025_consolidated_report_20261024_01"
)
OUT = HERE / "continuation_20261024/monthly_validation_2025_interpretation"
MANIFEST_SHA = "66108b5eb4e678569dcc82a46ebaa92f569a3601e160a2ab1ac781725313db0f"
EXIT_SHA = "4f4987abc7ca1c4a10d08bbba3af6dcbec92fc5033411049bc33d441930852ef"
AUDIT_SHA = "ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc"
MODES = ("static", "expanding", "rolling12")
TICKERS = ("SPXW", "SPY", "QQQ", "ALL")
MONTHS = tuple(str(202500 + month) for month in range(1, 13))
ECO = "available_economics."


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def close(left: float, right: float) -> None:
    require(math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-7),
            f"Reconciliation failed: {left} != {right}")


def run() -> None:
    manifest_path = SOURCE / "output_manifest.json"
    exit_path = SOURCE.with_name(SOURCE.name + "_logs") / "exit.json"
    require(sha(manifest_path) == MANIFEST_SHA, "Manifest pin")
    require(sha(exit_path) == EXIT_SHA, "Exit pin")
    manifest = json.loads(manifest_path.read_text())
    exit_record = json.loads(exit_path.read_text())
    require(manifest["status"] == "COMPLETE", "Reporter incomplete")
    require(manifest["audit_sha256"] == AUDIT_SHA, "Audit pin")
    require(exit_record["exit_code"] == 0 and exit_record["monitor_error"] is None,
            "Reporter failed")
    require(exit_record["audit_unchanged"] and exit_record["pins_unchanged"],
            "Reporter pins changed")
    inputs = {str(manifest_path): MANIFEST_SHA, str(exit_path): EXIT_SHA}
    for name in ("summary.json", "daily.csv", "monthly.csv", "periods.csv"):
        path = SOURCE / name
        expected = manifest["files"][name]
        require(path.stat().st_size == expected["bytes"], f"Size: {name}")
        require(sha(path) == expected["sha256"], f"Hash: {name}")
        inputs[str(path)] = expected["sha256"]
    summary = json.loads((SOURCE / "summary.json").read_text())
    require(summary["authority"]["scope"] == "VALIDATION_2025", "Scope")
    require(summary["selected_mode_cited"] is None, "Selection is not null")
    require(summary["development_seen"] and not summary["promotion_approved"],
            "Development boundary")

    def rows(name: str) -> list[dict[str, str]]:
        with (SOURCE / name).open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    monthly, annual, daily = rows("monthly.csv"), rows("periods.csv"), rows("daily.csv")
    require(len(monthly) == 144 and len(annual) == 12 and len(daily) == 2250,
            "Row counts")
    require({(r["mode"], r["ticker"], r["period"]) for r in monthly}
            == {(m, t, p) for m in MODES for t in TICKERS for p in MONTHS},
            "Monthly keys")
    require({(r["mode"], r["ticker"], r["period"]) for r in annual}
            == {(m, t, "2025") for m in MODES for t in TICKERS}, "Annual keys")
    calendars = []
    for mode in MODES:
        selected = [r for r in daily if r["mode"] == mode]
        keys = {(r["ticker"], r["date"]) for r in selected}
        require(len(keys) == len(selected) == 750, "Unique daily calendar")
        require(all(r["date"].startswith("2025") and r["source_status"] == "COMPLETE"
                    and r["evaluation_status"] == "EVALUABLE" for r in selected),
                "Daily availability")
        calendars.append(keys)
    require(calendars[0] == calendars[1] == calendars[2], "Different calendars")
    results = []
    for mode in MODES:
        for ticker in TICKERS:
            row = next(r for r in annual if (r["mode"], r["ticker"]) == (mode, ticker))
            months = sorted((r for r in monthly if (r["mode"], r["ticker"])
                             == (mode, ticker)), key=lambda r: r["period"])
            days = [r for r in daily if r["mode"] == mode
                    and (ticker == "ALL" or r["ticker"] == ticker)]
            require(int(row["available_ticker_days"]) == len(days)
                    == int(row["expected_ticker_days"]), "Annual calendar")
            require(int(row["missing_no_evaluable"]) == 0, "Missing 2025 day")
            for field in ("trades", "net_base", "net_adverse"):
                total = float(row[ECO + field])
                close(sum(float(r[ECO + field]) for r in months), total)
                close(sum(float(r[field]) for r in days), total)
            for field in ("attempts", "no_fill_attempts"):
                close(sum(float(r[field]) for r in days), float(row[field]))
                close(sum(float(r[field]) for r in months), float(row[field]))
            zeros = sum(int(r["trades"]) == 0 for r in days)
            require(zeros == int(row["available_days_without_fill"]), "Zero-fill days")
            require(int(row["attempts"]) == int(row[ECO + "trades"])
                    + int(row["no_fill_attempts"]), "Attempt decomposition")
            nets = [float(r[ECO + "net_base"]) for r in months]
            gains = sorted((n for n in nets if n > 0), reverse=True)
            losses = sorted((-n for n in nets if n < 0), reverse=True)
            net, adverse = float(row[ECO + "net_base"]), float(row[ECO + "net_adverse"])
            trades, attempts = int(row[ECO + "trades"]), int(row["attempts"])
            results.append({
                "mode": mode, "ticker": ticker, "trades": trades, "attempts": attempts,
                "net_base": net, "net_adverse": adverse,
                "base_pf": float(row[ECO + "net_base_pf"]),
                "base_win_rate": float(row[ECO + "net_base_win_rate"]),
                "net_base_per_trade": net / trades,
                "adverse_increment_usd": net - adverse,
                "zero_fill_days": zeros, "available_ticker_days": len(days),
                "zero_fill_day_fraction": zeros / len(days),
                "no_fill_attempts": int(row["no_fill_attempts"]),
                "no_fill_attempt_fraction": int(row["no_fill_attempts"]) / attempts,
                "positive_months": len(gains), "negative_months": len(losses),
                "zero_months": sum(n == 0 for n in nets),
                "positive_month_net_sum": sum(gains),
                "negative_month_net_magnitude": sum(losses),
                "top3_negative_month_share": sum(losses[:3]) / sum(losses),
                "top3_positive_month_share": sum(gains[:3]) / sum(gains) if gains else None,
                "best_month": months[nets.index(max(nets))]["period"],
                "best_month_net": max(nets),
                "worst_month": months[nets.index(min(nets))]["period"],
                "worst_month_net": min(nets),
                "months": [{"month": r["period"], "net_base": float(r[ECO + "net_base"]),
                            "net_adverse": float(r[ECO + "net_adverse"]),
                            "trades": int(r[ECO + "trades"]),
                            "zero_fill_days": int(r["available_days_without_fill"])}
                           for r in months],
            })
    for path, expected in inputs.items():
        require(sha(Path(path)) == expected, f"Input changed: {path}")
    OUT.mkdir(parents=True, exist_ok=False)
    result = {
        "status": "PASS_DESCRIPTIVE_RECONCILIATION_2025_ONLY",
        "scope": "Arithmetic on closed reporter; not an economic audit or a new policy",
        "inputs": inputs, "script_sha256": sha(Path(__file__)),
        "selected_mode_cited": None, "development_seen": True,
        "promotion_approved": False, "groups": results,
        "concentration_definition": (
            "Sums and top-three shares of positive/negative monthly NET buckets, "
            "not gross winning/losing trades. Same calculation for all twelve groups."
        ),
        "not_read": ["raw", "arrays", "models", "scores", "2026 outcomes", "ledger parquet"],
    }
    output = OUT / "descriptive_reconciliation.json"
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                 indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "path": str(output), "sha256": sha(output)}))


if __name__ == "__main__":
    run()
