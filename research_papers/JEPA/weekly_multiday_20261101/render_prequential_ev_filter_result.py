"""Render the audited prequential EV-filter result without replaying science."""

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
DEFAULT_PRODUCER = BASE / "prequential_ev_filter_01"
DEFAULT_OUTPUT = BASE / "prequential_ev_filter_report_01"
REPORT_NAME = "PREQUENTIAL_EV_FILTER_RESULT_20261101.md"
PNG_NAME = "prequential_ev_filter_monthly.png"
SVG_NAME = "prequential_ev_filter_monthly.svg"
RECEIPT_NAME = "report_receipt.json"

PARENTS = ("FROZEN_CONTEXT182", "MONTHLY_RAW", "WEEKLY_RAW")
VARIANTS = ("CONTROL", "FILTER")
COSTS = ("base", "adverse")
MONTHS = tuple(f"2026{month:02d}" for month in range(1, 10))
COMPLETE_MONTHS = MONTHS[:8]
VIEWS = ("conservative_all", "without_lower_bounds")
UNIVERSES = ("INTENTIONS", "ACCEPTED", "PRUNED")
THREAD_VARS = (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS",
    "TBB_NUM_THREADS", "NUMBA_NUM_THREADS",
)
SUMMARY_FLAGS = {
    "models_fit": False, "inference_run": False, "raw_read": False,
    "api_read": False, "broker_read": False, "future_labels_used": False,
    "scores_changed": False, "replay_run": True, "seen_development": True,
    "technical_ready": False, "promotion_approved": False,
    "production_changed": False,
}
AUDIT_FLAGS = {
    "fit_performed": False, "inference_run": False, "raw_read": False,
    "api_read": False, "broker_read": False, "producer_imported": False,
    "production_changed": False, "promotion_approved": False,
    "seen_development": True,
}
AUDIT_INPUTS = {
    "auditor", "contract", "independent_helper", "producer_manifest",
    "producer_exit", "upstream_manifest", "upstream_audit", "upstream_exit",
    "diagnostic", "acceptance",
}


class ReportError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReportError(message)


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
    output = []
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL {path}:{number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"JSONL object {path}:{number}")
            output.append(value)
    return output


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def finite(value: Any, label: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"numeric {label}")
    output = float(value)
    require(math.isfinite(output), f"finite {label}")
    return output


def close(actual: Any, expected: Any, label: str, tolerance: float = 1e-6) -> None:
    require(abs(finite(actual, label) - finite(expected, label)) <= tolerance, label)


def expected_outputs() -> set[str]:
    ledgers = {
        f"ledger_{parent.lower()}_{variant.lower()}_{cost}.jsonl"
        for parent in PARENTS for variant in VARIANTS for cost in COSTS
    }
    return {"intentions.jsonl", "decision_states.jsonl", "ev_diagnostics.jsonl", "summary.json", *ledgers}


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
    require(status.ullAvailPhys >= 2_000_000_000, "RAM gate")
    require(status.ullAvailPageFile >= 2_000_000_000, "free commit gate")
    return {
        "cpu_affinity": process.cpu_affinity(), "available_ram": status.ullAvailPhys,
        "free_commit": status.ullAvailPageFile, "thread_environment": {name: os.environ[name] for name in THREAD_VARS},
    }


def admit(
    producer_root: Path, producer_sha: str, audit_path: Path, audit_sha: str,
    audit_exit_path: Path, audit_exit_sha: str, reporter_sha: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    require(all(len(value) == 64 for value in (producer_sha, audit_sha, audit_exit_sha, reporter_sha)), "SHA-256 CLI")
    reporter_path = plain(Path(__file__), "reporter", regular=True)
    require(sha256_file(reporter_path) == reporter_sha.lower(), "reporter self pin")
    producer_root = plain(producer_root, "producer root")
    manifest_path = plain(producer_root / "manifest.json", "producer manifest", regular=True)
    audit_path = plain(audit_path, "audit JSON", regular=True)
    audit_exit_path = plain(audit_exit_path, "audit exit", regular=True)
    require(sha256_file(manifest_path) == producer_sha.lower(), "producer manifest SHA")
    require(sha256_file(audit_path) == audit_sha.lower(), "audit SHA")
    require(sha256_file(audit_exit_path) == audit_exit_sha.lower(), "audit exit SHA")

    manifest, audit, audit_exit = read_json(manifest_path), read_json(audit_path), read_json(audit_exit_path)
    require(manifest.get("schema") == "weekly_prequential_ev_filter_manifest_v1", "producer manifest schema")
    require(manifest.get("status") == "COMPLETE_SEEN_DEVELOPMENT_NOT_PROMOTED", "producer manifest status")
    require(manifest.get("flags") == SUMMARY_FLAGS, "producer manifest flags")
    require(set(audit) == {"schema", "status", "inputs", "flags", "numeric", "producer", "limitations"}, "audit top schema")
    require(audit.get("schema") == "weekly_prequential_ev_filter_audit_v1", "audit schema")
    require(audit.get("status") == "PASS_INDEPENDENT_PREQUENTIAL_EV_FILTER_RECONSTRUCTION", "audit PASS")
    require(audit.get("flags") == AUDIT_FLAGS, "audit flags")
    require(audit_exit.get("exit_code") == 0, "audit exit0")
    manifest_pin = pin(manifest_path)
    audit_inputs = audit.get("inputs")
    require(isinstance(audit_inputs, dict) and set(audit_inputs) == AUDIT_INPUTS, "audit input closure")
    require(audit_inputs["producer_manifest"] == manifest_pin, "audit/producer binding")
    require(set(manifest.get("outputs", {})) == expected_outputs(), "producer output closure")

    snapshots = {
        "reporter": pin(reporter_path), "producer_manifest": manifest_pin,
        "audit": pin(audit_path), "audit_exit": pin(audit_exit_path),
    }
    for name, expected in audit_inputs.items():
        require(isinstance(expected, dict) and set(expected) == {"path", "bytes", "sha256"}, f"audit input pin {name}")
        actual = pin(Path(expected["path"]))
        require(actual == expected, f"audit input immutable {name}")
        snapshots[f"audit_input:{name}"] = actual
    for name, expected in manifest["outputs"].items():
        require(isinstance(expected, dict) and set(expected) == {"bytes", "sha256"}, f"output pin shape {name}")
        path = plain(producer_root / name, f"producer output {name}", regular=True)
        actual = pin(path)
        require(actual["bytes"] == expected["bytes"] and actual["sha256"] == expected["sha256"], f"output pin {name}")
        snapshots[f"producer:{name}"] = actual
    return manifest, audit, audit_exit, snapshots


def validate_summary(summary: dict[str, Any]) -> None:
    require(set(summary) == {"schema", "status", "scope", "intentions", "policies", "filter_minus_control", "criterion", "flags"}, "summary keys")
    require(summary["schema"] == "weekly_prequential_ev_filter_summary_v1", "summary schema")
    require(summary["status"] == "COMPLETE_SEEN_DEVELOPMENT_NOT_PROMOTED", "summary status")
    require(summary["flags"] == SUMMARY_FLAGS, "summary flags")
    scope = summary["scope"]
    require(scope["parents"] == list(PARENTS), "summary parents")
    policies = [f"{parent}_{variant}" for parent in PARENTS for variant in VARIANTS]
    require(scope["policies"] == policies and set(summary["policies"]) == set(policies), "summary policies")
    require(summary["criterion"]["months"] == list(COMPLETE_MONTHS), "criterion months")
    require(summary["criterion"]["promotion_approved"] is False, "criterion promotion")
    require(set(summary["intentions"]) == set(PARENTS), "intention parents")
    require(set(summary["filter_minus_control"]) == set(PARENTS), "delta parents")
    for parent in PARENTS:
        item = summary["intentions"][parent]
        require(set(item) == {"intentions", "accepted", "pruned", "activation_entry_date", "activation_n", "decision_reasons"}, f"intention schema {parent}")
        require(item["intentions"] == item["accepted"] + item["pruned"], f"intention closure {parent}")
        require(all(isinstance(item[key], int) and item[key] >= 0 for key in ("intentions", "accepted", "pruned")), f"intention counts {parent}")
        require(isinstance(item["decision_reasons"], dict), f"decision reasons {parent}")
        for variant in VARIANTS:
            policy = summary["policies"][f"{parent}_{variant}"]
            require(set(policy) == {"books", "eight_of_eight_positive_adverse"}, "policy schema")
            require(set(policy["books"]) == set(COSTS), "book costs")
            adverse = policy["books"]["adverse"]
            monthly = adverse["monthly_net_including_zeros"]
            require(list(monthly) == list(MONTHS), "monthly order")
            calculated = all(finite(monthly[month], month) > 0 for month in COMPLETE_MONTHS)
            require(policy["eight_of_eight_positive_adverse"] is calculated, "8/8 criterion")
        for cost in COSTS:
            expected = summary["policies"][f"{parent}_FILTER"]["books"][cost]["net_usd"] - summary["policies"][f"{parent}_CONTROL"]["books"][cost]["net_usd"]
            close(summary["filter_minus_control"][parent][cost], expected, f"delta {parent}/{cost}")


def validate_diagnostics(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    fields = {
        "parent", "universe", "view", "partition", "value", "n", "mean_ev_raw",
        "mean_ev_gate", "mean_net", "bias_raw", "mae_raw", "bias_gate", "mae_gate", "lower_bound_n",
    }
    require(len(rows) == 216 and all(set(row) == fields for row in rows), "diagnostic schema/count")
    identities = {(row["parent"], row["universe"], row["view"], row["partition"], row["value"]) for row in rows}
    require(len(identities) == len(rows), "diagnostic uniqueness")
    totals: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        require(row["parent"] in PARENTS and row["universe"] in UNIVERSES and row["view"] in VIEWS, "diagnostic enums")
        require(row["partition"] in {"TOTAL", "ENTRY_BLOCK", "ENTRY_MONTH"}, "diagnostic partition")
        require(isinstance(row["n"], int) and isinstance(row["lower_bound_n"], int) and 0 <= row["lower_bound_n"] <= row["n"], "diagnostic counts")
        metrics = ("mean_ev_raw", "mean_ev_gate", "mean_net", "bias_raw", "mae_raw", "bias_gate", "mae_gate")
        if row["n"] == 0:
            require(all(row[name] is None for name in metrics), "empty diagnostic metrics")
        else:
            for name in metrics:
                finite(row[name], name)
            require(row["mae_raw"] >= 0 and row["mae_gate"] >= 0, "diagnostic MAE")
        if row["partition"] == "TOTAL":
            require(row["value"] == "ALL", "TOTAL value")
            totals[(row["parent"], row["universe"], row["view"])] = row
    require(len(totals) == 18, "diagnostic TOTAL closure")
    return totals


def validate_ledgers(producer_root: Path, summary: dict[str, Any]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for parent in PARENTS:
        for variant in VARIANTS:
            policy = f"{parent}_{variant}"
            for cost in COSTS:
                name = f"ledger_{parent.lower()}_{variant.lower()}_{cost}.jsonl"
                rows = read_jsonl(producer_root / name)
                events = {event: sum(row.get("event") == event for row in rows) for event in ("ENTRY", "EXIT", "WAIT", "NO_FILL", "CAPITAL_BLOCKED", "NO_OPPORTUNITY")}
                require(events["ENTRY"] == events["EXIT"], f"ENTRY/EXIT pairing {policy}/{cost}")
                exits = [row for row in rows if row.get("event") == "EXIT"]
                net = math.fsum(finite(row.get("net_usd"), "EXIT net") for row in exits)
                book = summary["policies"][policy]["books"][cost]
                close(book["net_usd"], net, f"ledger net {policy}/{cost}")
                require(book["trades"] == len(exits), f"ledger trades {policy}/{cost}")
                for month in MONTHS:
                    value = math.fsum(finite(row["net_usd"], "monthly EXIT") for row in exits if row["date"][:6] == month)
                    close(book["monthly_net_including_zeros"][month], value, f"ledger month {policy}/{cost}/{month}")
                counts[f"{policy}:{cost}"] = events
    return counts


def money(value: Any) -> str:
    return f"{finite(value, 'money'):,.2f}"


def pf(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        require(value == "Infinity", "profit factor string")
        return value
    return f"{finite(value, 'PF'):.3f}"


def make_report(
    summary: dict[str, Any], totals: dict[tuple[str, str, str], dict[str, Any]],
    authority: dict[str, str], ledger_counts: dict[str, dict[str, int]],
) -> str:
    lines = [
        "# Resultado descriptivo del filtro EV prequential", "",
        "Este informe describe exclusivamente artefactos reconstruidos por la auditoría independiente. No reentrena modelos, no repite el replay y no selecciona una frecuencia ganadora. Todo 2026 permanece **SEEN_DEVELOPMENT**; `technical_ready=false` y `promotion_approved=false`.", "",
        "## Autoridad", "",
        f"- Manifest productor: `{authority['producer']}`.",
        f"- Auditoría independiente: `{authority['audit']}` (`PASS_INDEPENDENT_PREQUENTIAL_EV_FILTER_RECONSTRUCTION`).",
        f"- Exit auditor: `{authority['audit_exit']}` (`exit_code=0`).", "",
        "## Economía adverse por política", "",
        "| Política | Neto USD | 8/8 Ene-Ago | Meses positivos | Sep parcial | PF | DD realizado | ENTRY | EXIT |",
        "|---|---:|:---:|---:|---:|---:|---:|---:|---:|",
    ]
    for parent in PARENTS:
        for variant in VARIANTS:
            policy_name = f"{parent}_{variant}"
            policy = summary["policies"][policy_name]
            book = policy["books"]["adverse"]
            events = ledger_counts[f"{policy_name}:adverse"]
            positive = sum(book["monthly_net_including_zeros"][month] > 0 for month in COMPLETE_MONTHS)
            lines.append(
                f"| {policy_name} | {money(book['net_usd'])} | {'Sí' if policy['eight_of_eight_positive_adverse'] else 'No'} | {positive}/8 | "
                f"{money(book['monthly_net_including_zeros']['202609'])} | {pf(book['profit_factor'])} | {money(book['realized_max_drawdown_usd'])} | {events['ENTRY']} | {events['EXIT']} |"
            )
    lines += ["", "El requisito necesario se aplica por cada FILTER: los ocho meses completos deben ser estrictamente positivos. Septiembre es parcial y no integra el criterio.", "", "## Meses adverse: CONTROL frente a FILTER", ""]
    for parent in PARENTS:
        lines += [f"### {parent}", "", "| Mes EXIT | CONTROL | FILTER | FILTER−CONTROL |", "|---|---:|---:|---:|"]
        control = summary["policies"][f"{parent}_CONTROL"]["books"]["adverse"]["monthly_net_including_zeros"]
        filtered = summary["policies"][f"{parent}_FILTER"]["books"]["adverse"]["monthly_net_including_zeros"]
        for month in MONTHS:
            suffix = " (parcial)" if month == "202609" else ""
            lines.append(f"| {month}{suffix} | {money(control[month])} | {money(filtered[month])} | {money(filtered[month] - control[month])} |")
        lines.append("")
    lines += ["## Activación y abstención", "", "| Padre | Intenciones | Aceptadas | Podadas | Activación | n activación |", "|---|---:|---:|---:|---|---:|"]
    for parent in PARENTS:
        item = summary["intentions"][parent]
        lines.append(f"| {parent} | {item['intentions']} | {item['accepted']} | {item['pruned']} | {item['activation_entry_date'] or 'null'} | {item['activation_n'] if item['activation_n'] is not None else 'null'} |")
    lines += ["", "El buffer 1.645 es heurístico: no es un intervalo de confianza ni un coste ejecutado. El filtro no cambia ranking o lado y sólo puede podar una intención raw positiva.", "", "## Diagnóstico EV por contrato", "", "Filas `TOTAL`; `N` es payoff potencial por contrato, incluso para intenciones no ejecutadas. Nunca se interpreta como PnL de cartera.", "", "| Padre | Universo | Vista | n | LB | EV raw | EV gate | N | Bias raw | MAE raw | Bias gate | MAE gate |", "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for parent in PARENTS:
        for universe in UNIVERSES:
            for view in VIEWS:
                row = totals[(parent, universe, view)]
                def metric(name: str) -> str:
                    return "null" if row[name] is None else money(row[name])
                lines.append(f"| {parent} | {universe} | {view} | {row['n']} | {row['lower_bound_n']} | {metric('mean_ev_raw')} | {metric('mean_ev_gate')} | {metric('mean_net')} | {metric('bias_raw')} | {metric('mae_raw')} | {metric('bias_gate')} | {metric('mae_gate')} |")
    lines += ["", "## Lectura y límites", "", "- `ENTRY` y `EXIT` se reconciliaron por separado; sólo `EXIT.net_usd` es PnL realizado.", "- Una intención FILTER aceptada pertenece al top-1 raw positivo, pero sus fills no tienen por qué ser subconjunto de CONTROL porque los libros desarrollan estados distintos.", "- `without_lower_bounds` es descriptivo y no genera decisiones alternativas.", "- Ningún resultado de este informe autoriza selección, promoción o uso operativo.", "", f"![Neto mensual adverse]({PNG_NAME})", ""]
    return "\n".join(lines)


def make_figure(summary: dict[str, Any], output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    x = np.arange(len(MONTHS))
    labels = [month[-2:] for month in MONTHS]
    fig, axes = plt.subplots(3, 1, figsize=(12, 11), sharex=True, constrained_layout=True)
    colors = {"CONTROL": "#61758A", "FILTER": "#E36B3D"}
    for axis, parent in zip(axes, PARENTS, strict=True):
        control = summary["policies"][f"{parent}_CONTROL"]["books"]["adverse"]["monthly_net_including_zeros"]
        filtered = summary["policies"][f"{parent}_FILTER"]["books"]["adverse"]["monthly_net_including_zeros"]
        left = axis.bar(x - 0.19, [control[month] for month in MONTHS], 0.38, label="CONTROL", color=colors["CONTROL"])
        right = axis.bar(x + 0.19, [filtered[month] for month in MONTHS], 0.38, label="FILTER", color=colors["FILTER"])
        left[-1].set_hatch("//")
        right[-1].set_hatch("//")
        axis.axhline(0, color="#20262E", linewidth=0.9)
        axis.grid(axis="y", alpha=0.22)
        axis.set_title(parent, loc="left", fontsize=11, fontweight="bold")
        axis.set_ylabel("Neto adverse (USD)")
    axes[0].legend(frameon=False, ncol=2, loc="upper right")
    axes[-1].set_xticks(x, labels)
    axes[-1].set_xlabel("Mes de realización EXIT en 2026; 09 rayado = parcial hasta el 17")
    fig.suptitle("Filtro EV prequential: CONTROL vs FILTER", fontsize=15, fontweight="bold")
    fig.savefig(output / PNG_NAME, dpi=180, facecolor="white")
    fig.savefig(output / SVG_NAME, facecolor="white")
    plt.close(fig)


def revalidate(snapshots: dict[str, dict[str, Any]]) -> None:
    for label, expected in snapshots.items():
        actual = pin(Path(expected["path"]))
        require(actual == expected, f"closing immutability {label}")


def run(args: argparse.Namespace) -> dict[str, Any]:
    gate = runtime_gate()
    output = plain(args.output, "report output", exists=False)
    require(not output.exists(), "report output already exists")
    producer_root = plain(args.producer_root, "producer root")
    require(output != producer_root and producer_root not in output.parents and output not in producer_root.parents, "separate report root")
    manifest, audit, audit_exit, snapshots = admit(
        producer_root, args.producer_manifest_sha256, args.audit_json, args.audit_sha256,
        args.audit_exit_json, args.audit_exit_sha256, args.reporter_sha256,
    )
    summary = read_json(producer_root / "summary.json")
    validate_summary(summary)
    diagnostics = read_jsonl(producer_root / "ev_diagnostics.jsonl")
    totals = validate_diagnostics(diagnostics)
    ledger_counts = validate_ledgers(producer_root, summary)
    revalidate(snapshots)
    output.mkdir(parents=False, exist_ok=False)
    authority = {
        "producer": snapshots["producer_manifest"]["sha256"],
        "audit": snapshots["audit"]["sha256"],
        "audit_exit": snapshots["audit_exit"]["sha256"],
    }
    (output / REPORT_NAME).write_text(make_report(summary, totals, authority, ledger_counts), encoding="utf-8", newline="\n")
    make_figure(summary, output)
    revalidate(snapshots)
    outputs = {name: pin(output / name) for name in (REPORT_NAME, PNG_NAME, SVG_NAME)}
    receipt = {
        "schema": "weekly_prequential_ev_filter_report_receipt_v1",
        "status": "COMPLETE_DESCRIPTIVE_REPORT_GIVEN_INDEPENDENT_AUDIT_PASS",
        "inputs": snapshots, "outputs": outputs, "ledger_event_counts": ledger_counts,
        "runtime_gate": gate,
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
        parser().error("execution requires --execute-reviewed-report")
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
