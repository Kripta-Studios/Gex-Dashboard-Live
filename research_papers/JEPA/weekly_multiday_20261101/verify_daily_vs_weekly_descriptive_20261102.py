"""Read-only arithmetic verification of the closed DAILY adaptation ledgers."""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics


for _name in (
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS",
    "NUMBA_NUM_THREADS", "TBB_NUM_THREADS",
):
    os.environ[_name] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
WB = Path("D:/GexResearchArtifacts/weekly_multiday_20261101")
SOURCE = WB / "h2_daily_adaptation_01"
OUTPUT = WB / "daily_vs_weekly_descriptive_verification_04"
REPORT = WB / "h2_daily_adaptation_report_01/DAILY_ADAPTATION_RESULT_20261101.md"
HELPER = REPO / "research_papers/JEPA/level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py"
MONTHS = tuple(f"2026{month:02d}" for month in range(1, 10))
TOL = 1e-8

PINS = {
    HELPER: "3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046",
    SOURCE / "summary.json": "6774831265818d979455eab0d42ba1711fec39f5f50137caf80027f06d12293c",
    SOURCE / "daily_vs_weekly.jsonl": "8f949ac8adb7fdfe8b21e45da62a49df37bb1db2d691426bbb424af613d746ed",
    SOURCE / "ledger_daily_raw_adverse.jsonl": "5be07e66d6b28df0c8bf38f790929acf5e53393166df0cdddd8741269b1a39e3",
    SOURCE / "ledger_daily_raw_base.jsonl": "53e0dfec52b476eee6158f6b0308828f92e1239fa790a94f7dec7f434aa5e1e7",
    SOURCE / "ledger_frozen_context182_adverse.jsonl": "17ba6ce12c9b531ab88693ebea70987b9a46d8a35aa7d73cc2344ae7ed6ffce2",
    SOURCE / "ledger_frozen_context182_base.jsonl": "b08f1e2b56051d86b71326e927cd44f0e0e4928a4dbf4edf2b51c75d6920b692",
    SOURCE / "ledger_monthly_raw_adverse.jsonl": "87024b9b3cf7274fe25d3639858132cd9b76f4dc64c9b3c21198abb98410995f",
    SOURCE / "ledger_monthly_raw_base.jsonl": "e5b784381566a2cd23e8e3f7629f04a25fbf194926c21a7710c05825a483c4da",
    SOURCE / "ledger_weekly_raw_adverse.jsonl": "3029a1e7fdcfd1de435dcfc91210df25fa2a32d437ab77d1dfebb0be6f20fa58",
    SOURCE / "ledger_weekly_raw_base.jsonl": "0a57a116abb7eda55bee04a1fc21b95b823951468a35f65758a1d3553383a22d",
    WB / "h2_daily_adaptation_audit_02/audit.json": "383edce65b16b316dcf71f2197a716d71501495f704040e858cea9354511b2b9",
    WB / "h2_daily_adaptation_audit_observer_02/exit.json": "6c9e236906de004c9da015021424e690b1dc8d1ed06514533fdcbfc4c3a524e8",
    REPORT: "c4d11bfbb690693b3d4452a185164c84f50a9fbc444551b3ff56e28797b38216",
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def close(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= TOL


def affinity_cpu0() -> dict:
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
    kernel.SetProcessAffinityMask.restype = ctypes.c_int
    kernel.GetProcessAffinityMask.argtypes = (
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t))
    kernel.GetProcessAffinityMask.restype = ctypes.c_int
    handle = kernel.GetCurrentProcess()
    require(bool(kernel.SetProcessAffinityMask(handle, 1)), "Could not set CPU affinity to CPU 0")
    process_mask = ctypes.c_size_t()
    system_mask = ctypes.c_size_t()
    require(bool(kernel.GetProcessAffinityMask(handle, ctypes.byref(process_mask), ctypes.byref(system_mask))),
            "Could not read CPU affinity")
    require(process_mask.value == 1, "CPU affinity is not exactly CPU 0")
    return {"process_mask": process_mask.value, "cpu_indices": [0]}


def load_helper():
    spec = importlib.util.spec_from_file_location("official_resource_helper_descriptive", HELPER)
    require(spec is not None and spec.loader is not None, "Cannot load official resource helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ledger_metrics(rows: list[dict]) -> dict:
    exits = [row for row in rows if row.get("event") == "EXIT"]
    entries = [row for row in rows if row.get("event") == "ENTRY"]
    counts: dict[str, int] = {}
    for row in rows:
        event = row["event"]
        counts[event] = counts.get(event, 0) + 1
    monthly = {month: 0.0 for month in MONTHS}
    ticker: dict[str, float] = {}
    side: dict[str, float] = {}
    equity_values = [float(row["equity_realized"]) for row in rows if "equity_realized" in row]
    peak = equity_values[0]
    drawdown = 0.0
    for equity in equity_values:
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    for row in exits:
        net = float(row["net_usd"])
        monthly[row["date"][:6]] += net
        ticker[row["ticker"]] = ticker.get(row["ticker"], 0.0) + net
        side[row["right"]] = side.get(row["right"], 0.0) + net
    wins = sum(float(row["net_usd"]) for row in exits if float(row["net_usd"]) > 0)
    losses = sum(float(row["net_usd"]) for row in exits if float(row["net_usd"]) < 0)
    quantities = [int(row["quantity"]) for row in entries]
    no_fill: dict[str, int] = {}
    for row in rows:
        if row.get("event") == "NO_FILL":
            reason = row.get("reason") or row.get("status") or row.get("selection_reason")
            no_fill[str(reason)] = no_fill.get(str(reason), 0) + 1
    largest = max(exits, key=lambda row: float(row["net_usd"]))
    largest_month = max(MONTHS, key=lambda month: abs(monthly[month]))
    return {
        "event_counts": counts,
        "net_usd": sum(float(row["net_usd"]) for row in exits),
        "trades": len(exits),
        "quantity_total": sum(quantities),
        "quantity_max": max(quantities),
        "quantity_median": statistics.median(quantities),
        "profit_factor": wins / abs(losses),
        "realized_max_drawdown_usd": drawdown,
        "monthly_net_usd": monthly,
        "positive_months": sum(value > 0 for value in monthly.values()),
        "ticker_net_usd": ticker,
        "side_net": side,
        "wait": counts.get("WAIT", 0),
        "no_opportunity": counts.get("NO_OPPORTUNITY", 0),
        "no_fill_by_reason": no_fill,
        "largest_trade": {key: largest.get(key) for key in
                          ("candidate_id", "date", "model_id", "net_usd", "right", "ticker")},
        "largest_month_by_absolute_net": largest_month,
        "net_without_largest_trade": sum(float(row["net_usd"]) for row in exits) - float(largest["net_usd"]),
        "net_without_largest_month": sum(monthly.values()) - monthly[largest_month],
    }


def verify_metrics(actual: dict, expected: dict, name: str) -> int:
    scalar = ("net_usd", "trades", "quantity_total", "quantity_max", "quantity_median",
              "profit_factor", "realized_max_drawdown_usd", "positive_months", "wait", "no_opportunity")
    for key in scalar:
        require(close(actual[key], expected[key]), f"{name}: {key} differs")
    for key in ("ticker_net_usd",):
        require(set(actual[key]) == set(expected[key]), f"{name}: {key} keys differ")
        for member, value in actual[key].items():
            require(close(value, expected[key][member]), f"{name}: {key}.{member} differs")
    details = expected["details"]
    expected_monthly = details["monthly_net_including_zeros"]
    require(set(actual["monthly_net_usd"]) == set(expected_monthly), f"{name}: monthly keys differ")
    for member, value in actual["monthly_net_usd"].items():
        require(close(value, expected_monthly[member]), f"{name}: monthly {member} differs")
    require(actual["event_counts"] == details["event_counts"], f"{name}: event counts differ")
    require(set(actual["side_net"]) == set(details["side_net"]), f"{name}: side keys differ")
    for member, value in actual["side_net"].items():
        require(close(value, details["side_net"][member]), f"{name}: side {member} differs")
    require(actual["largest_month_by_absolute_net"] == details["largest_month_by_absolute_net"],
            f"{name}: largest month differs")
    require(actual["largest_trade"]["candidate_id"] == details["largest_trade"]["candidate_id"],
            f"{name}: largest trade differs")
    require(close(actual["net_without_largest_trade"], details["net_without_largest_trade"]),
            f"{name}: net without largest trade differs")
    require(close(actual["net_without_largest_month"], details["net_without_largest_month"]),
            f"{name}: net without largest month differs")
    return len(actual["monthly_net_usd"])


def by_event(rows: list[dict], event: str) -> dict[str, dict]:
    return {row["candidate_id"]: row for row in rows if row.get("event") == event}


def report_monthly_values() -> dict[str, dict[str, dict[str, float]]]:
    text = REPORT.read_text(encoding="utf-8")
    section = text.split("## Los 72 valores mensuales", 1)[1].split("## H1/Q3", 1)[0]
    result: dict[str, dict[str, dict[str, float]]] = {}
    columns = ("FROZEN_CONTEXT182", "MONTHLY_RAW", "WEEKLY_RAW", "DAILY_RAW")
    for cost in ("base", "adverse"):
        cost_text = section.split(f"### {cost}", 1)[1]
        if cost == "base":
            cost_text = cost_text.split("### adverse", 1)[0]
        values = {policy: {} for policy in columns}
        for line in cost_text.splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) != 5 or not cells[0].startswith("2026"):
                continue
            month = cells[0].split()[0]
            for policy, cell in zip(columns, cells[1:]):
                values[policy][month] = float(cell.replace(".", "").replace(",", "."))
        require(all(len(values[policy]) == 9 for policy in columns), f"Report {cost} monthly table incomplete")
        result[cost] = values
    return result


def diagnostic_difference_summary(rows: list[dict]) -> dict:
    def vector_stats(key: str) -> dict:
        l1 = [sum(abs(float(value)) for value in row[key]) for row in rows]
        maximum = [max(abs(float(value)) for value in row[key]) for row in rows]
        return {
            "mean_l1": statistics.mean(l1),
            "median_l1": statistics.median(l1),
            "max_l1": max(l1),
            "mean_max_component": statistics.mean(maximum),
            "max_component": max(maximum),
            "rows_max_component_le_0_01": sum(value <= 0.01 for value in maximum),
        }

    def scalar_stats(key: str) -> dict:
        absolute = [abs(float(row[key])) for row in rows]
        return {
            "mean_absolute": statistics.mean(absolute),
            "median_absolute": statistics.median(absolute),
            "max_absolute": max(absolute),
            "rows_absolute_le_25": sum(value <= 25 for value in absolute),
        }

    return {
        "p_model_diff": vector_stats("p_model_diff"),
        "p_cal_diff": vector_stats("p_cal_diff"),
        "ev_base_diff": scalar_stats("ev_base_diff"),
        "ev_adverse_diff": scalar_stats("ev_adverse_diff"),
        "distinct_daily_weekly_model_ids": sum(
            row["daily_model_id"] != row["weekly_model_id"] for row in rows),
        "daily_top1": sum(bool(row["daily_top1"]) for row in rows),
        "weekly_top1": sum(bool(row["weekly_top1"]) for row in rows),
        "top1_changed": sum(bool(row["top1_changed"]) for row in rows),
    }


def main() -> None:
    require(not OUTPUT.exists(), "Output root already exists")
    for path, expected in PINS.items():
        require(path.is_file() and sha(path) == expected, f"Pinned input differs: {path}")
    OUTPUT.mkdir(parents=True)
    affinity = affinity_cpu0()
    helper = load_helper()
    observation = helper.observation()
    resource = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "official_helper": str(HELPER),
        "official_helper_sha256": PINS[HELPER],
        "minimum_free_bytes": helper.MIN_FREE,
        "observation": observation,
        "affinity": affinity,
        "thread_environment": {name: os.environ[name] for name in (
            "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS", "NUMBA_NUM_THREADS", "TBB_NUM_THREADS",
            "CUDA_VISIBLE_DEVICES")},
    }
    (OUTPUT / "resource_observation.json").write_text(
        json.dumps(resource, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    helper.gate(observation)

    summary = read_json(SOURCE / "summary.json")
    policies = {
        "FROZEN_CONTEXT182": "frozen_context182",
        "MONTHLY_RAW": "monthly_raw",
        "WEEKLY_RAW": "weekly_raw",
        "DAILY_RAW": "daily_raw",
    }
    reconstructed: dict[str, dict] = {}
    monthly_checks = 0
    ledger_rows: dict[tuple[str, str], list[dict]] = {}
    for policy, leaf in policies.items():
        reconstructed[policy] = {}
        for cost in ("base", "adverse"):
            rows = read_jsonl(SOURCE / f"ledger_{leaf}_{cost}.jsonl")
            ledger_rows[(policy, cost)] = rows
            metrics = ledger_metrics(rows)
            monthly_checks += verify_metrics(metrics, summary["policies"][policy]["economics"][cost],
                                              f"{policy}/{cost}")
            reconstructed[policy][cost] = metrics
    require(monthly_checks == 72, "Expected exactly 72 independently checked monthly values")
    report_values = report_monthly_values()
    report_monthly_checks = 0
    for cost in ("base", "adverse"):
        for policy in policies:
            for month in MONTHS:
                require(close(report_values[cost][policy][month], reconstructed[policy][cost]["monthly_net_usd"][month]),
                        f"Report monthly value differs: {policy}/{cost}/{month}")
                report_monthly_checks += 1
    require(report_monthly_checks == 72, "Expected exactly 72 report monthly checks")

    differences: dict[str, dict] = {}
    for cost in ("base", "adverse"):
        weekly_entries = by_event(ledger_rows[("WEEKLY_RAW", cost)], "ENTRY")
        daily_entries = by_event(ledger_rows[("DAILY_RAW", cost)], "ENTRY")
        weekly_exits = by_event(ledger_rows[("WEEKLY_RAW", cost)], "EXIT")
        daily_exits = by_event(ledger_rows[("DAILY_RAW", cost)], "EXIT")
        common_entries = set(weekly_entries) & set(daily_entries)
        require(all(weekly_entries[c]["quantity"] == daily_entries[c]["quantity"] for c in common_entries),
                f"{cost}: common fill quantities differ")
        weekly_only = sorted(set(weekly_entries) - set(daily_entries))
        daily_only = sorted(set(daily_entries) - set(weekly_entries))
        require(len(weekly_only) == len(daily_only) == 1, f"{cost}: expected one replaced fill")
        old_id, new_id = weekly_only[0], daily_only[0]
        differences[cost] = {
            "weekly_only": {"entry": weekly_entries[old_id], "exit": weekly_exits[old_id]},
            "daily_only": {"entry": daily_entries[new_id], "exit": daily_exits[new_id]},
            "common_filled_ids": len(common_entries),
            "weekly_trades": len(weekly_exits),
            "daily_trades": len(daily_exits),
            "net_delta_daily_minus_weekly": reconstructed["DAILY_RAW"][cost]["net_usd"]
                                                   - reconstructed["WEEKLY_RAW"][cost]["net_usd"],
            "monthly_delta_daily_minus_weekly": {
                month: reconstructed["DAILY_RAW"][cost]["monthly_net_usd"][month]
                       - reconstructed["WEEKLY_RAW"][cost]["monthly_net_usd"][month]
                for month in MONTHS
            },
        }
        require(close(differences[cost]["net_delta_daily_minus_weekly"], -200.0),
                f"{cost}: expected total delta -200")
        require(all(close(value, -200.0 if month == "202607" else 0.0)
                    for month, value in differences[cost]["monthly_delta_daily_minus_weekly"].items()),
                f"{cost}: monthly delta pattern differs")

    diagnostics = read_jsonl(SOURCE / "daily_vs_weekly.jsonl")
    changed = [row for row in diagnostics if row.get("top1_changed")]
    diagnostic_differences = diagnostic_difference_summary(diagnostics)
    require(len(diagnostics) == 612 and len(changed) == 2, "Diagnostic counts differ")
    weekly_fills = set(by_event(ledger_rows[("WEEKLY_RAW", "adverse")], "ENTRY"))
    daily_fills = set(by_event(ledger_rows[("DAILY_RAW", "adverse")], "ENTRY"))
    changed_with_fill = []
    for row in changed:
        changed_with_fill.append({
            **row,
            "weekly_filled": row["candidate_id"] in weekly_fills,
            "daily_filled": row["candidate_id"] in daily_fills,
        })
    require(sum(row["weekly_filled"] or row["daily_filled"] for row in changed_with_fill) == 1,
            "Expected exactly one changed-rank candidate to correspond to a fill")

    for path, expected in PINS.items():
        require(sha(path) == expected, f"Input mutated during verification: {path}")
    receipt = {
        "status": "PASS_READ_ONLY_DAILY_VS_WEEKLY_DESCRIPTIVE_VERIFICATION",
        "scope": "closed ledgers only; no replay, fit, inference, selection, or causal claim",
        "utc": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "ledgers": 8,
            "monthly_values": monthly_checks,
            "report_monthly_values": report_monthly_checks,
            "diagnostic_rows": len(diagnostics),
            "top1_changed": len(changed),
            "top1_changed_corresponding_to_any_fill": 1,
        },
        "reconstructed": reconstructed,
        "daily_vs_weekly": differences,
        "top1_changed_rows": changed_with_fill,
        "diagnostic_difference_distribution": diagnostic_differences,
        "selected_probability_ev": {
            policy: summary["policies"][policy]["probability_ev"]["selected"]
            for policy in ("WEEKLY_RAW", "DAILY_RAW")
        },
        "pins_before_and_after": {str(path): expected for path, expected in PINS.items()},
        "resource_observation": resource,
    }
    receipt_path = OUTPUT / "verification.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": receipt["status"],
        "verification": str(receipt_path),
        "verification_sha256": sha(receipt_path),
        "resource_sha256": sha(OUTPUT / "resource_observation.json"),
        "checks": receipt["checks"],
        "daily_adverse_net": reconstructed["DAILY_RAW"]["adverse"]["net_usd"],
        "weekly_adverse_net": reconstructed["WEEKLY_RAW"]["adverse"]["net_usd"],
        "adverse_delta": differences["adverse"]["net_delta_daily_minus_weekly"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
