"""Render the audited DAILY-vs-controls result; never fit, infer, or replay."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


BASE = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101")
DEFAULT_PRODUCER = BASE / "h2_daily_adaptation_01"
DEFAULT_OUTPUT = BASE / "h2_daily_adaptation_report_01"
REPORT_NAME = "DAILY_ADAPTATION_RESULT_20261101.md"
PNG_NAME = "daily_adaptation_monthly.png"
SVG_NAME = "daily_adaptation_monthly.svg"
RECEIPT_NAME = "report_receipt.json"

POLICIES = ("FROZEN_CONTEXT182", "MONTHLY_RAW", "WEEKLY_RAW", "DAILY_RAW")
COMPARISON_BASELINES = ("WEEKLY_RAW", "MONTHLY_RAW")
COSTS = ("base", "adverse")
MONTHS = tuple(f"2026{month:02d}" for month in range(1, 10))
COMPLETE_MONTHS = MONTHS[:8]
VIEWS = ("all", "all_observed_only", "selected", "selected_observed_only")
THREAD_VARS = (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS",
    "TBB_NUM_THREADS", "NUMBA_NUM_THREADS",
)
PRODUCER_FLAGS = {
    "models_fit": True, "reused_states_fit": False, "seen_development": True,
    "raw_read": False, "api_read": False, "broker_read": False,
    "future_labels_used": False, "guarded_used": False, "ev_filter_used": False,
    "selection_made": False, "technical_ready": False,
    "promotion_approved": False, "production_changed": False,
}
AUDIT_FLAGS = {
    "fit_performed": False, "inference_from_saved_weights": True,
    "raw_read": False, "api_read": False, "broker_read": False,
    "producer_imported": False, "production_changed": False,
    "promotion_approved": False, "seen_development": True,
}


class DailyReportError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DailyReportError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def plain(path: Path, label: str, *, exists: bool = True, regular: bool = False) -> Path:
    absolute = Path(os.path.abspath(path))
    if exists:
        require(absolute.exists(), f"missing {label}")
    current = absolute if absolute.exists() else absolute.parent
    while True:
        if current.exists():
            attrs = getattr(current.lstat(), "st_file_attributes", 0)
            require(not current.is_symlink() and not attrs & 0x400, f"link/reparse {label}")
        if current.parent == current:
            break
        current = current.parent
    if regular:
        require(absolute.is_file(), f"regular file {label}")
    return absolute


def pin(path: Path) -> dict[str, Any]:
    path = plain(path, str(path), regular=True)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL {path}:{number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"JSONL object {path}:{number}")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def finite(value: Any, label: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"numeric {label}")
    result = float(value)
    require(math.isfinite(result), f"finite {label}")
    return result


def close(actual: Any, expected: Any, label: str, tolerance: float = 1e-6) -> None:
    require(abs(finite(actual, label) - finite(expected, label)) <= tolerance, label)


def format_es(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        require(value == "Infinity", "numeric string")
        return "Infinito"
    number = finite(value, "formatted value")
    text = f"{number:,.{decimals}f}"
    return text.replace(",", "#").replace(".", ",").replace("#", ".")


def monthly(book: dict[str, Any]) -> dict[str, float]:
    details = book.get("details")
    require(isinstance(details, dict), "book details")
    values = details.get("monthly_net_including_zeros")
    require(isinstance(values, dict) and list(values) == list(MONTHS), "nine monthly values")
    return {month: finite(values[month], f"month {month}") for month in MONTHS}


def runtime_gate() -> dict[str, Any]:
    for name in THREAD_VARS:
        require(os.environ.get(name) == "1", f"{name}=1 required")
    import psutil

    process = psutil.Process()
    require(process.cpu_affinity() == [0], "CPU affinity must be exactly [0]")

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    require(bool(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))), "memory gate unavailable")
    require(status.ullAvailPhys >= 2_000_000_000 and status.ullAvailPageFile >= 2_000_000_000, "RAM/free commit gate")
    return {
        "cpu_affinity": [0], "available_ram": status.ullAvailPhys,
        "free_commit": status.ullAvailPageFile,
        "thread_environment": {name: os.environ[name] for name in THREAD_VARS},
    }


def expected_output_names() -> set[str]:
    core = {
        "daily_fit_plans.json", "daily_schedule.json", "daily_states_new.jsonl",
        "fit_journal.jsonl", "candidate_scores.jsonl", "state_diagnostics.jsonl",
        "daily_vs_weekly.jsonl", "summary.json",
    }
    ledgers = {f"ledger_{policy.lower()}_{cost}.jsonl" for policy in POLICIES for cost in COSTS}
    states = {f"fit_state_CONTEXT182_{day}.json" for day in ()}  # names validated by prefix/count below
    return core | ledgers | states


def admit(
    producer_root: Path, producer_sha: str, audit_path: Path, audit_sha: str,
    audit_exit_path: Path, audit_exit_sha: str, reporter_sha: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    require(all(isinstance(value, str) and len(value) == 64 for value in (producer_sha, audit_sha, audit_exit_sha, reporter_sha)), "SHA-256 CLI")
    reporter = plain(Path(__file__), "reporter", regular=True)
    require(sha256_file(reporter) == reporter_sha.lower(), "reporter self pin")
    producer_root = plain(producer_root, "producer root")
    manifest_path = plain(producer_root / "manifest.json", "producer manifest", regular=True)
    audit_path = plain(audit_path, "audit JSON", regular=True)
    audit_exit_path = plain(audit_exit_path, "audit exit", regular=True)
    require(sha256_file(manifest_path) == producer_sha.lower(), "producer manifest SHA")
    require(sha256_file(audit_path) == audit_sha.lower(), "audit SHA")
    require(sha256_file(audit_exit_path) == audit_exit_sha.lower(), "audit exit SHA")
    manifest, audit, audit_exit = read_json(manifest_path), read_json(audit_path), read_json(audit_exit_path)
    require(set(manifest) == {"schema", "status", "inputs", "outputs", "flags"}, "manifest schema")
    require(manifest["schema"] == "weekly_daily_adaptation_manifest_v1", "manifest name")
    require(manifest["status"] == "COMPLETE_SEEN_DEVELOPMENT_NOT_PROMOTED", "manifest status")
    require(manifest["flags"] == PRODUCER_FLAGS, "manifest flags")
    require(audit.get("schema") == "weekly_daily_adaptation_audit_v1", "audit schema")
    require(audit.get("status") == "PASS_INDEPENDENT_DAILY_ADAPTATION_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT", "audit PASS")
    require(audit.get("flags") == AUDIT_FLAGS, "audit flags")
    require(audit_exit.get("exit_code") == 0, "audit exit0")
    manifest_pin = pin(manifest_path)
    require(audit.get("inputs", {}).get("producer_manifest") == manifest_pin, "audit producer binding")
    producer_exit_pin = audit.get("inputs", {}).get("producer_exit")
    expected_producer_exit = BASE / "h2_daily_adaptation_observer_01" / "exit.json"
    require(isinstance(producer_exit_pin, dict) and set(producer_exit_pin) == {"path", "bytes", "sha256"}, "audit producer exit pin")
    require(Path(producer_exit_pin["path"]) == expected_producer_exit, "producer exit path")
    require(pin(expected_producer_exit) == producer_exit_pin, "producer exit immutable")
    require(read_json(expected_producer_exit).get("exit_code") == 0, "producer exit0")

    outputs = manifest.get("outputs")
    require(isinstance(outputs, dict) and len(outputs) == 152, "152 producer outputs")
    required = expected_output_names()
    require(required <= set(outputs), "required output names")
    state_names = {name for name in outputs if name.startswith("fit_state_CONTEXT182_") and name.endswith(".json")}
    require(len(state_names) == 136 and set(outputs) == required | state_names, "output closure 136 states")
    snapshots = {
        "reporter": pin(reporter), "producer_manifest": manifest_pin,
        "audit": pin(audit_path), "audit_exit": pin(audit_exit_path),
    }
    for name, expected in audit.get("inputs", {}).items():
        require(isinstance(expected, dict) and set(expected) == {"path", "bytes", "sha256"}, f"audit input pin {name}")
        actual = pin(Path(expected["path"]))
        require(actual == expected, f"audit input immutable {name}")
        snapshots[f"audit_input:{name}"] = actual
    for name, expected in outputs.items():
        require(isinstance(expected, dict) and set(expected) == {"bytes", "sha256"}, f"producer pin {name}")
        path = plain(producer_root / Path(name), f"producer output {name}", regular=True)
        require(producer_root in path.parents, f"output escape {name}")
        actual = pin(path)
        require(actual["bytes"] == expected["bytes"] and actual["sha256"] == expected["sha256"], f"producer output pin {name}")
        snapshots[f"producer:{name}"] = actual
    return manifest, audit, snapshots


def validate_summary(summary: dict[str, Any]) -> None:
    require(set(summary) == {"schema", "status", "scope", "states", "policies", "comparisons", "criterion", "diagnostics", "flags"}, "summary keys")
    require(summary["schema"] == "weekly_daily_adaptation_summary_v1", "summary schema")
    require(summary["status"] == "COMPLETE_SEEN_DEVELOPMENT_NOT_PROMOTED", "summary status")
    require(summary["flags"] == PRODUCER_FLAGS, "summary flags")
    require(summary["scope"] == {"sessions": 178, "candidate_universe": 612, "policies": list(POLICIES), "scores": 2448, "books": 8}, "summary scope")
    require(summary["states"] == {"daily": 178, "reused": 42, "new": 136, "terminal_unused": 2}, "state counts")
    require(set(summary["policies"]) == set(POLICIES), "summary policies")
    criterion = summary["criterion"]
    require(criterion["months"] == list(COMPLETE_MONTHS) and criterion["selected_policy"] is None and criterion["promotion_approved"] is False, "criterion closure")
    for policy in POLICIES:
        item = summary["policies"][policy]
        require(set(item) == {"economics", "probability_ev", "selected_ids", "filled_ids", "adverse_net_minus_frozen"}, f"policy schema {policy}")
        require(set(item["economics"]) == set(COSTS) and set(item["probability_ev"]) == set(VIEWS), f"policy metrics {policy}")
        for cost in COSTS:
            book = item["economics"][cost]
            values = monthly(book)
            require(len(values) == 9, "monthly completeness")
            for key in ("net_usd", "realized_max_drawdown_usd", "trades", "quantity_total"):
                finite(book[key], f"book {policy}/{cost}/{key}")
            require(book["trades"] >= 0 and book["quantity_total"] >= 0, "book nonnegative counts")
            for key in ("wait", "capital_blocked", "no_opportunity", "missing_exit"):
                require(isinstance(book[key], int) and book[key] >= 0, f"book count {policy}/{cost}/{key}")
            require(isinstance(book["no_fill_by_reason"], dict) and all(isinstance(value, int) and value >= 0 for value in book["no_fill_by_reason"].values()), f"no fill reasons {policy}/{cost}")
            details = book["details"]
            for key in ("block_net_by_exit_realization", "block_net_by_entry_cohort"):
                block = details[key]
                require(set(block) == {"H1_2026", "Q3_PARTIAL_2026"}, f"block keys {policy}/{cost}/{key}")
                for value in block.values():
                    finite(value, f"block value {policy}/{cost}/{key}")
            require(details["largest_month_by_absolute_net"] in MONTHS, f"largest month {policy}/{cost}")
            if details["largest_trade"] is not None:
                finite(details["largest_trade"]["net_usd"], f"largest trade {policy}/{cost}")
            require(set(book["ticker_net_usd"]) == {"SPY", "QQQ", "SPXW"}, f"ticker concentration {policy}/{cost}")
            require(set(details["side_net"]) == {"CALL", "PUT"}, f"side concentration {policy}/{cost}")
            for value in (*book["ticker_net_usd"].values(), *details["side_net"].values()):
                finite(value, f"concentration value {policy}/{cost}")
            finite(details["net_without_largest_trade"], f"without largest trade {policy}/{cost}")
            finite(details["net_without_largest_month"], f"without largest month {policy}/{cost}")
        for view in VIEWS:
            metric = item["probability_ev"][view]
            require(set(metric) >= {"n", "logloss", "brier", "reliability", "ev"}, f"probability schema {policy}/{view}")
            require(set(metric["ev"]) == set(COSTS), f"EV costs {policy}/{view}")
    daily_months = monthly(summary["policies"]["DAILY_RAW"]["economics"]["adverse"])
    require(criterion["daily_passes_8_of_8"] is all(daily_months[month] > 0 for month in COMPLETE_MONTHS), "daily criterion")
    require(set(summary["comparisons"]) == set(COMPARISON_BASELINES), "comparison baselines")
    daily = summary["policies"]["DAILY_RAW"]["economics"]
    for baseline in COMPARISON_BASELINES:
        comparison = summary["comparisons"][baseline]
        require(set(comparison) == set(COSTS), f"comparison costs {baseline}")
        for cost in COSTS:
            value = comparison[cost]
            require(set(value) == {"total_net_usd", "monthly_net_usd"}, f"comparison schema {baseline}/{cost}")
            require(list(value["monthly_net_usd"]) == list(MONTHS), f"comparison months {baseline}/{cost}")
            control = summary["policies"][baseline]["economics"][cost]
            close(value["total_net_usd"], daily[cost]["net_usd"] - control["net_usd"], f"comparison total {baseline}/{cost}")
            daily_months, control_months = monthly(daily[cost]), monthly(control)
            for month in MONTHS:
                close(value["monthly_net_usd"][month], daily_months[month] - control_months[month], f"comparison month {baseline}/{cost}/{month}")
    diagnostics = summary["diagnostics"]
    require(set(diagnostics) == {"state_rows", "candidate_rows", "top1_changed"}, "diagnostic summary schema")
    require(diagnostics["state_rows"] == 178 and diagnostics["candidate_rows"] == 612, "diagnostic row counts")
    require(isinstance(diagnostics["top1_changed"], int) and 0 <= diagnostics["top1_changed"] <= 612, "top1 changed count")


def validate_schedule(producer_root: Path, summary: dict[str, Any]) -> dict[str, int]:
    schedule = read_json(producer_root / "daily_schedule.json")
    require(schedule.get("schema") == "weekly_daily_adaptation_schedule_v1" and schedule.get("count") == 178, "schedule header")
    require(set(schedule) == {"schema", "count", "reused_source", "rows"}, "schedule top schema")
    reused_source = schedule["reused_source"]
    require(isinstance(reused_source, dict) and set(reused_source) == {"path", "bytes", "sha256"}, "reused source pin")
    require(Path(reused_source["path"]) == BASE / "h2_context_adaptation_01" / "states.jsonl", "reused source path")
    require(pin(Path(reused_source["path"])) == reused_source, "reused source immutable")
    rows = schedule.get("rows")
    require(isinstance(rows, list) and len(rows) == 178, "schedule rows")
    require(len({row["date"] for row in rows}) == 178, "schedule dates")
    reused = sum(row.get("source") == "REUSED" for row in rows)
    new = sum(row.get("source") == "NEW" for row in rows)
    terminal = sum(bool(row.get("terminal_unused_for_scoring")) for row in rows)
    require((reused, new, terminal) == (42, 136, 2), "schedule counts")
    require(all(set(row) == {"date", "state_id", "source", "source_row", "used_for_scoring", "terminal_unused_for_scoring"} for row in rows), "schedule row schema")
    for row in rows:
        if row["source"] == "REUSED":
            require(isinstance(row["source_row"], int) and row["source_row"] >= 0, "reused source row")
        else:
            require(row["source_row"] is None, "new source row")
        require(row["terminal_unused_for_scoring"] is (row["date"] in {"20260916", "20260917"}), "terminal identity")
        require(row["used_for_scoring"] is (not row["terminal_unused_for_scoring"]), "scoring identity")
    plans = read_json(producer_root / "daily_fit_plans.json")
    require(plans.get("schema") == "weekly_daily_adaptation_fit_plans_v1" and plans.get("count") == 178 and len(plans.get("plans", [])) == 178, "fit plans")
    states = read_jsonl(producer_root / "daily_states_new.jsonl")
    require(len(states) == 136 and len({row["state_id"] for row in states}) == 136, "new state rows")
    new_ids = {row["state_id"] for row in rows if row["source"] == "NEW"}
    require({row["state_id"] for row in states} == new_ids, "new state identity")
    expected_state_files = {f"fit_state_{state_id}.json" for state_id in new_ids}
    actual_state_files = {path.name for path in producer_root.glob("fit_state_CONTEXT182_*.json")}
    require(actual_state_files == expected_state_files, "fit state file identity")
    for state in states:
        require(read_json(producer_root / f"fit_state_{state['state_id']}.json") == state, f"fit state payload {state['state_id']}")
    journal = read_jsonl(producer_root / "fit_journal.jsonl")
    require(len(journal) == 272 and sum(row.get("event") == "FIT_START" for row in journal) == 136 and sum(row.get("event") == "FIT_COMPLETE" for row in journal) == 136, "fit journal")
    state_diag = read_jsonl(producer_root / "state_diagnostics.jsonl")
    require(len(state_diag) == 178, "state diagnostics")
    require(sum(row.get("source") == "REUSED" for row in state_diag) == 42 and sum(row.get("source") == "NEW" for row in state_diag) == 136, "state diagnostic sources")
    require(sum(bool(row.get("terminal_unused_for_scoring")) for row in state_diag) == 2, "state diagnostic terminals")
    require(sum(int(row.get("score_count", -1)) for row in state_diag) == 612, "state diagnostic score count")
    candidate_diag = read_jsonl(producer_root / "daily_vs_weekly.jsonl")
    require(len(candidate_diag) == 612 and len({row.get("candidate_id") for row in candidate_diag}) == 612, "candidate diagnostics")
    top1_changed = sum(bool(row.get("top1_changed")) for row in candidate_diag)
    require(top1_changed == summary["diagnostics"]["top1_changed"], "top1 diagnostic reconciliation")
    return {
        "sessions": 178, "reused": reused, "new": new,
        "terminal_unused": terminal, "journal_events": len(journal),
        "state_diagnostic_rows": len(state_diag), "candidate_diagnostic_rows": len(candidate_diag),
        "top1_changed": top1_changed,
    }


def validate_ledgers(producer_root: Path, summary: dict[str, Any]) -> dict[str, dict[str, int]]:
    output = {}
    for policy in POLICIES:
        for cost in COSTS:
            rows = read_jsonl(producer_root / f"ledger_{policy.lower()}_{cost}.jsonl")
            events = {name: sum(row.get("event") == name for row in rows) for name in ("ENTRY", "EXIT", "WAIT", "NO_FILL", "CAPITAL_BLOCKED", "NO_OPPORTUNITY")}
            require(events["ENTRY"] == events["EXIT"], f"ENTRY/EXIT {policy}/{cost}")
            exits = [row for row in rows if row.get("event") == "EXIT"]
            book = summary["policies"][policy]["economics"][cost]
            require(book["trades"] == len(exits), f"trade count {policy}/{cost}")
            close(book["net_usd"], math.fsum(finite(row["net_usd"], "EXIT net") for row in exits), f"net {policy}/{cost}")
            book_months = monthly(book)
            for month in MONTHS:
                actual = math.fsum(finite(row["net_usd"], "monthly EXIT") for row in exits if row["date"][:6] == month)
                close(book_months[month], actual, f"month {policy}/{cost}/{month}")
            output[f"{policy}:{cost}"] = events
    return output


def probability_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for policy in POLICIES:
        for view in VIEWS:
            metric = summary["policies"][policy]["probability_ev"][view]
            row = {
                "policy": policy, "view": view, "n": metric["n"],
                "logloss": metric["logloss"], "brier": metric["brier"],
            }
            for cost in COSTS:
                row[f"{cost}_bias"] = metric["ev"][cost]["bias"]
                row[f"{cost}_mae"] = metric["ev"][cost]["mae"]
            rows.append(row)
    return rows


def report_text(summary: dict[str, Any], schedule: dict[str, int], authority: dict[str, str], event_counts: dict[str, dict[str, int]]) -> str:
    lines = [
        "# Resultado descriptivo de adaptación diaria", "",
        "Este informe describe artefactos reconstruidos por auditoría independiente. No reentrena, no infiere, no repite libros y no selecciona una frecuencia ganadora. Todo 2026 permanece **SEEN_DEVELOPMENT**; `technical_ready=false` y `promotion_approved=false`.", "",
        "## Autoridad", "",
        f"- Manifest productor: `{authority['producer']}`.",
        f"- Auditoría independiente: `{authority['audit']}`.",
        f"- Exit auditor: `{authority['audit_exit']}` (`exit_code=0`).", "",
        "## Estados y agenda", "",
        f"Agenda: {schedule['sessions']} sesiones; {schedule['reused']} estados reutilizados sin fit, {schedule['new']} fits nuevos y {schedule['terminal_unused']} estados terminales sin scoring. Journal: {schedule['journal_events']} eventos. Diagnóstico: {schedule['state_diagnostic_rows']} estados y {schedule['candidate_diagnostic_rows']} candidatos; top-1 distinto DAILY/WEEKLY en {schedule['top1_changed']} candidatos. Las filas de candidato no son días ni experimentos independientes.", "",
        "## Economía total", "",
        "| Política | Coste | Neto USD | PF | DD realizado | Trades | Cantidad | ENTRY | EXIT | Positivos Ene-Ago | Sep parcial |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for policy in POLICIES:
        for cost in COSTS:
            book = summary["policies"][policy]["economics"][cost]
            values = monthly(book)
            events = event_counts[f"{policy}:{cost}"]
            positives = sum(values[month] > 0 for month in COMPLETE_MONTHS)
            lines.append(
                f"| {policy} | {cost} | {format_es(book['net_usd'])} | {format_es(book['profit_factor'], 3)} | "
                f"{format_es(book['realized_max_drawdown_usd'])} | {book['trades']} | {book['quantity_total']} | {events['ENTRY']} | {events['EXIT']} | {positives}/8 | {format_es(values['202609'])} |"
            )
    daily_pass = summary["criterion"]["daily_passes_8_of_8"]
    lines += ["", f"Criterio DAILY 8/8: **{'PASS' if daily_pass else 'FAIL'}**. Cero o un mes sin trades no cuenta como positivo; septiembre es parcial.", "", "## Los 72 valores mensuales", ""]
    for cost in COSTS:
        lines += [f"### {cost}", "", "| Mes EXIT | FROZEN | MONTHLY | WEEKLY | DAILY |", "|---|---:|---:|---:|---:|"]
        values = {policy: monthly(summary["policies"][policy]["economics"][cost]) for policy in POLICIES}
        for month in MONTHS:
            suffix = " (parcial)" if month == "202609" else ""
            lines.append(f"| {month}{suffix} | {format_es(values['FROZEN_CONTEXT182'][month])} | {format_es(values['MONTHLY_RAW'][month])} | {format_es(values['WEEKLY_RAW'][month])} | {format_es(values['DAILY_RAW'][month])} |")
        lines.append("")
    lines += [
        "## H1/Q3: realización EXIT frente a cohorte ENTRY", "",
        "| Política | Coste | H1 EXIT | Q3 parcial EXIT | H1 ENTRY | Q3 parcial ENTRY |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for policy in POLICIES:
        for cost in COSTS:
            details = summary["policies"][policy]["economics"][cost]["details"]
            exit_block = details["block_net_by_exit_realization"]
            entry_block = details["block_net_by_entry_cohort"]
            lines.append(
                f"| {policy} | {cost} | {format_es(exit_block['H1_2026'])} | {format_es(exit_block['Q3_PARTIAL_2026'])} | "
                f"{format_es(entry_block['H1_2026'])} | {format_es(entry_block['Q3_PARTIAL_2026'])} |"
            )
    lines += [
        "", "## Ejecución, cotas y concentración", "",
        "| Política | Coste | WAIT | NO_FILL | Capital | Sin oportunidad | Cotas | Mayor trade | Mes más concentrado | Neto del mes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for policy in POLICIES:
        for cost in COSTS:
            book = summary["policies"][policy]["economics"][cost]
            details = book["details"]
            no_fill = sum(book["no_fill_by_reason"].values())
            largest_trade = 0.0 if details["largest_trade"] is None else details["largest_trade"]["net_usd"]
            largest_month = details["largest_month_by_absolute_net"]
            lines.append(
                f"| {policy} | {cost} | {book['wait']} | {no_fill} | {book['capital_blocked']} | {book['no_opportunity']} | {book['missing_exit']} | "
                f"{format_es(largest_trade)} | {largest_month} | {format_es(monthly(book)[largest_month])} |"
            )
    lines += [
        "", "## Concentración por ticker y lado", "",
        "| Política | Coste | SPY | QQQ | SPXW | CALL | PUT | Neto sin mayor trade | Neto sin mayor mes |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for policy in POLICIES:
        for cost in COSTS:
            book = summary["policies"][policy]["economics"][cost]
            details = book["details"]
            tickers, sides = book["ticker_net_usd"], details["side_net"]
            lines.append(
                f"| {policy} | {cost} | {format_es(tickers['SPY'])} | {format_es(tickers['QQQ'])} | {format_es(tickers['SPXW'])} | "
                f"{format_es(sides['CALL'])} | {format_es(sides['PUT'])} | {format_es(details['net_without_largest_trade'])} | {format_es(details['net_without_largest_month'])} |"
            )
    lines += [
        "## DAILY menos controles", "",
        "| Control | Coste | Ene | Feb | Mar | Abr | May | Jun | Jul | Ago | Sep parcial | Total |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for baseline in COMPARISON_BASELINES:
        for cost in COSTS:
            comparison = summary["comparisons"][baseline][cost]
            deltas = [format_es(comparison["monthly_net_usd"][month]) for month in MONTHS]
            lines.append(
                f"| {baseline} | {cost} | {' | '.join(deltas)} | "
                f"{format_es(comparison['total_net_usd'])} |"
            )
    lines += ["", "Las diferencias son descriptivas: una mejora agregada no sustituye el requisito 8/8 y no crea una política nueva.", "", "## Probabilidad y EV", "", "| Política | Vista | n | Logloss | Brier | Bias EV base | MAE EV base | Bias EV adverse | MAE EV adverse |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in probability_rows(summary):
        lines.append(
            f"| {row['policy']} | {row['view']} | {row['n']} | {format_es(row['logloss'], 4)} | {format_es(row['brier'], 4)} | "
            f"{format_es(row['base_bias'])} | {format_es(row['base_mae'])} | {format_es(row['adverse_bias'])} | {format_es(row['adverse_mae'])} |"
        )
    lines += ["", "## Límites", "", "- Los 178 estados diarios están muy solapados y no son 178 experimentos independientes.", "- Los 42 estados de control se reutilizan; sólo 136 corresponden a fits nuevos.", "- Los PnL se realizan por EXIT; septiembre es parcial y los estados Sep16/17 no puntúan candidatos.", "- Ningún resultado retrospectivo garantiza rentabilidad futura ni autoriza selección, promoción o uso operativo.", "", f"![Comparación mensual por coste]({PNG_NAME})", ""]
    return "\n".join(lines)


def make_figure(summary: dict[str, Any], output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    import numpy as np

    colors = ("#52677D", "#2A9D8F", "#E9A23B", "#D85B45")
    x = np.arange(len(MONTHS))
    width = 0.19
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True, constrained_layout=True)
    for axis, cost in zip(axes, COSTS, strict=True):
        for index, (policy, color) in enumerate(zip(POLICIES, colors, strict=True)):
            values = monthly(summary["policies"][policy]["economics"][cost])
            bars = axis.bar(x + (index - 1.5) * width, [values[month] for month in MONTHS], width, label=policy, color=color)
            bars[-1].set_hatch("//")
        axis.axhline(0, color="#20262E", linewidth=0.9)
        axis.grid(axis="y", alpha=0.22)
        axis.set_title(cost.upper(), loc="left", fontweight="bold")
        axis.set_ylabel("Neto USD")
        axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _position: format_es(value, 0)))
    axes[0].legend(frameon=False, ncol=4, fontsize=9, loc="upper right")
    axes[-1].set_xticks(x, [month[-2:] for month in MONTHS])
    axes[-1].set_xlabel("Mes de realización EXIT; 09 rayado = parcial hasta el 17")
    fig.suptitle("Adaptación DAILY frente a controles", fontsize=15, fontweight="bold")
    fig.savefig(output / PNG_NAME, dpi=180, facecolor="white")
    fig.savefig(output / SVG_NAME, facecolor="white")
    plt.close(fig)


def revalidate(snapshots: dict[str, dict[str, Any]]) -> None:
    for label, expected in snapshots.items():
        require(pin(Path(expected["path"])) == expected, f"closing immutability {label}")


def run(args: argparse.Namespace) -> dict[str, Any]:
    gate = runtime_gate()
    producer_root = plain(args.producer_root, "producer root")
    output = plain(args.output, "report output", exists=False)
    require(not output.exists() and output.parent == BASE, "exclusive report output")
    require(output != producer_root and output not in producer_root.parents and producer_root not in output.parents, "separate roots")
    _manifest, _audit, snapshots = admit(
        producer_root, args.producer_manifest_sha256, args.audit_json, args.audit_sha256,
        args.audit_exit_json, args.audit_exit_sha256, args.reporter_sha256,
    )
    summary = read_json(producer_root / "summary.json")
    validate_summary(summary)
    schedule = validate_schedule(producer_root, summary)
    event_counts = validate_ledgers(producer_root, summary)
    revalidate(snapshots)
    output.mkdir(parents=False, exist_ok=False)
    authority = {
        "producer": snapshots["producer_manifest"]["sha256"],
        "audit": snapshots["audit"]["sha256"],
        "audit_exit": snapshots["audit_exit"]["sha256"],
    }
    (output / REPORT_NAME).write_text(report_text(summary, schedule, authority, event_counts), encoding="utf-8", newline="\n")
    make_figure(summary, output)
    revalidate(snapshots)
    outputs = {name: pin(output / name) for name in (REPORT_NAME, PNG_NAME, SVG_NAME)}
    receipt = {
        "schema": "weekly_daily_adaptation_report_receipt_v1",
        "status": "COMPLETE_DESCRIPTIVE_REPORT_GIVEN_INDEPENDENT_AUDIT_PASS",
        "inputs": snapshots, "outputs": outputs, "schedule": schedule,
        "ledger_event_counts": event_counts, "runtime_gate": gate,
        "flags": {
            "fit_run": False, "inference_run": False, "replay_run": False,
            "raw_read": False, "api_read": False, "broker_read": False,
            "seen_development": True, "technical_ready": False,
            "promotion_approved": False, "winner_selected": False,
        },
    }
    write_json(output / RECEIPT_NAME, receipt)
    revalidate(snapshots)
    return receipt


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--execute-reviewed-report", action="store_true")
    value.add_argument("--producer-root", type=Path, default=DEFAULT_PRODUCER)
    value.add_argument("--producer-manifest-sha256", required=True)
    value.add_argument("--audit-json", type=Path, required=True)
    value.add_argument("--audit-sha256", required=True)
    value.add_argument("--audit-exit-json", type=Path, required=True)
    value.add_argument("--audit-exit-sha256", required=True)
    value.add_argument("--reporter-sha256", required=True)
    value.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.execute_reviewed_report:
        parser.error("execution requires --execute-reviewed-report")
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
