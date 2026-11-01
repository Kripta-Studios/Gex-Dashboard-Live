from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


DATASET_ROOT = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101\h2_dataset_v2_01")
EVAL_ROOT = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101\h2_ev_v2_01")
OUTPUT_ROOT = Path(r"D:\GexResearchArtifacts\weekly_multiday_20261101\h2_descriptive_report_v2_01")
DATASET_MANIFEST_SHA256 = "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8"
EVAL_MANIFEST_SHA256 = "54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96"
STARTING_CASH = 100_000.0
MONTHS = [f"2026{month:02d}" for month in range(1, 7)]
POLICIES = {
    "EV_TOP1_H2": ("EV top-1", "#0b6e4f"),
    "ALWAYS_CALL_H2": ("Siempre CALL", "#2176ae"),
    "ALWAYS_PUT_H2": ("Siempre PUT", "#d1495b"),
    "ALWAYS_ABSTAIN": ("Siempre WAIT", "#6c757d"),
}
TICKERS = ("SPY", "QQQ", "SPXW")


class ReportError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReportError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL line {path}:{line_number}")
            row = json.loads(line)
            require(isinstance(row, dict), f"JSONL object required {path}:{line_number}")
            rows.append(row)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def close(actual: float, expected: float, label: str, tolerance: float = 1e-6) -> None:
    require(math.isclose(actual, expected, abs_tol=tolerance, rel_tol=0), f"reconciliation failed: {label}")


def load_pinned_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    dataset_manifest_path = DATASET_ROOT / "manifest.json"
    eval_manifest_path = EVAL_ROOT / "manifest.json"
    require(sha256_file(dataset_manifest_path) == DATASET_MANIFEST_SHA256, "dataset manifest pin")
    require(sha256_file(eval_manifest_path) == EVAL_MANIFEST_SHA256, "evaluation manifest pin")
    dataset_manifest, eval_manifest = read_json(dataset_manifest_path), read_json(eval_manifest_path)
    require(dataset_manifest.get("schema") == "weekly_h2_dataset_manifest_v2", "dataset manifest schema")
    require(eval_manifest.get("schema") == "weekly_h2_ev_manifest_v1", "evaluation manifest schema")
    require(eval_manifest["inputs"]["external_manifest_sha256"] == DATASET_MANIFEST_SHA256, "cross-manifest pin")
    require(eval_manifest["inputs"]["manifest.json"]["sha256"] == DATASET_MANIFEST_SHA256, "dataset input pin")
    summary_path = EVAL_ROOT / "summary.json"
    summary_pin = eval_manifest["outputs"]["summary.json"]
    require(summary_path.stat().st_size == summary_pin["bytes"] and sha256_file(summary_path) == summary_pin["sha256"], "summary pin")
    summary = read_json(summary_path)
    require(summary.get("schema") == "weekly_h2_ev_evaluation_v1", "summary schema")
    require(summary.get("development_seen") is True and summary.get("promotion_approved") is False, "summary flags")
    ledgers = {}
    for policy in POLICIES:
        name = f"ledger_{policy.lower()}_eval_adverse.jsonl"
        path = EVAL_ROOT / name
        pin = eval_manifest["outputs"][name]
        require(path.stat().st_size == pin["bytes"] and sha256_file(path) == pin["sha256"], f"ledger pin {policy}")
        ledgers[policy] = read_jsonl(path)
    return dataset_manifest, eval_manifest, ledgers, summary


def ledger_metrics(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    exits = [row for row in ledger if row.get("event") == "EXIT"]
    entries = [row for row in ledger if row.get("event") == "ENTRY"]
    waits = [row for row in ledger if row.get("event") == "WAIT"]
    relevant = [row for row in ledger if row.get("event") in {"ENTRY", "EXIT"}]
    realized = STARTING_CASH
    equity_dates = [datetime(2026, 1, 1)]
    equity_values = [realized]
    for row in relevant:
        realized += float(row["realized_delta"])
        equity_dates.append(datetime.strptime(row["date"], "%Y%m%d"))
        equity_values.append(realized)
    values = np.asarray([float(row["net_usd"]) for row in exits], dtype=float)
    gains = float(values[values > 0].sum()) if len(values) else 0.0
    losses = float(-values[values < 0].sum()) if len(values) else 0.0
    curve = np.asarray(equity_values, dtype=float)
    drawdown = float((np.maximum.accumulate(curve) - curve).max())
    monthly = {month: 0.0 for month in MONTHS}
    tickers = {ticker: 0.0 for ticker in TICKERS}
    for row in exits:
        monthly[row["date"][:6]] += float(row["net_usd"])
        tickers[row["ticker"]] += float(row["net_usd"])
    missing_quote = sum(row["status"] == "MISSING_EXIT_QUOTE" for row in exits)
    missing_source = sum(row["status"] == "MISSING_EXIT_SOURCE" for row in exits)
    largest_gain = max(exits, key=lambda row: float(row["net_usd"]), default=None)
    return {
        "trades": len(exits),
        "net_usd": float(values.sum()),
        "profit_factor": gains / losses if losses else (None if gains == 0 else "Infinity"),
        "realized_max_drawdown_usd": drawdown,
        "monthly_net_usd": monthly,
        "positive_months": sum(value > 0 for value in monthly.values()),
        "ticker_net_usd": tickers,
        "missing_exit_quote": missing_quote,
        "missing_exit_source": missing_source,
        "missing_exit_total": missing_quote + missing_source,
        "entry_date_count": len({row["date"] for row in entries}),
        "wait_open_position": sum(row.get("reason") == "OPEN_POSITION" for row in waits),
        "wait_ev_not_positive": sum(row.get("reason") == "EV_NOT_POSITIVE" for row in waits),
        "concentration": None if largest_gain is None else {
            "largest_gain_usd": float(largest_gain["net_usd"]),
            "candidate_id": largest_gain["candidate_id"],
            "exit_date": largest_gain["date"],
            "ticker": largest_gain["ticker"],
            "right": largest_gain["right"],
            "net_without_largest_gain_usd": float(values.sum()) - float(largest_gain["net_usd"]),
            "interpretation": "sensitivity_only_not_an_alternative_policy",
        },
        "equity_dates": [value.strftime("%Y-%m-%d") for value in equity_dates],
        "equity_realized_usd": equity_values,
    }


def reconcile(summary: dict[str, Any], computed: dict[str, dict[str, Any]]) -> None:
    for policy, values in computed.items():
        expected = summary["economics"][policy]["EVAL"]["adverse"]["pooled"]
        require(values["trades"] == expected["trades"], f"trades {policy}")
        close(values["net_usd"], float(expected["net_usd"]), f"net {policy}")
        close(values["realized_max_drawdown_usd"], float(expected["realized_max_drawdown_usd"]), f"drawdown {policy}")
        require(values["profit_factor"] == expected["profit_factor"] or (
            isinstance(values["profit_factor"], float) and isinstance(expected["profit_factor"], float)
            and math.isclose(values["profit_factor"], expected["profit_factor"], abs_tol=1e-12)
        ), f"profit factor {policy}")
        require(values["missing_exit_quote"] == expected["missing_exit_quote"], f"missing quote {policy}")
        require(values["missing_exit_source"] == expected["missing_exit_source"], f"missing source {policy}")
        require(values["positive_months"] == expected["positive_months"], f"positive months {policy}")
        close(sum(values["monthly_net_usd"].values()), values["net_usd"], f"monthly total {policy}")
        for ticker in TICKERS:
            ticker_expected = summary["economics"][policy]["EVAL"]["adverse"]["tickers"][ticker]
            close(values["ticker_net_usd"][ticker], float(ticker_expected["net_usd"]), f"ticker {policy} {ticker}")
        close(sum(values["ticker_net_usd"].values()), values["net_usd"], f"ticker total {policy}")


def fmt_usd(value: float) -> str:
    return f"{value:,.1f} $".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pf(value: float | str | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        return "∞"
    return f"{value:.2f}"


def render_figure(computed: dict[str, dict[str, Any]], output: Path) -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig = plt.figure(figsize=(18, 11.5), facecolor="#f6f7f9")
    grid = fig.add_gridspec(2, 1, height_ratios=[1.08, 1], hspace=0.32)
    ax_equity = fig.add_subplot(grid[0])
    lower = grid[1].subgridspec(1, 3, width_ratios=[1.45, 0.78, 1.4], wspace=0.28)
    ax_month = fig.add_subplot(lower[0, 0])
    ax_ticker = fig.add_subplot(lower[0, 1])
    ax_table = fig.add_subplot(lower[0, 2])
    for axis in (ax_equity, ax_month, ax_ticker, ax_table):
        axis.set_facecolor("white")

    for policy, (label, color) in POLICIES.items():
        dates = [datetime.fromisoformat(value) for value in computed[policy]["equity_dates"]]
        ax_equity.step(dates, computed[policy]["equity_realized_usd"], where="post", label=label, color=color, linewidth=2)
    ax_equity.axhline(STARTING_CASH, color="#222", linewidth=0.8, alpha=0.5)
    ax_equity.set_title("Equity realizada — EVAL H1 2026, coste adverso", loc="left", weight="bold")
    ax_equity.set_ylabel("USD (capital inicial 100.000 $)")
    ax_equity.grid(axis="y", alpha=0.18)
    ax_equity.legend(ncol=4, loc="upper left", frameon=False)

    x = np.arange(len(MONTHS))
    width = 0.19
    for index, (policy, (label, color)) in enumerate(POLICIES.items()):
        values = [computed[policy]["monthly_net_usd"][month] for month in MONTHS]
        ax_month.bar(x + (index - 1.5) * width, values, width, label=label, color=color)
    ax_month.axhline(0, color="#222", linewidth=0.8)
    ax_month.set_xticks(x, ["Ene", "Feb", "Mar", "Abr", "May", "Jun"])
    ax_month.set_title("Neto mensual — seis meses", loc="left", weight="bold")
    ax_month.set_ylabel("USD")
    ax_month.grid(axis="y", alpha=0.18)

    ev_tickers = computed["EV_TOP1_H2"]["ticker_net_usd"]
    ticker_colors = ["#d1495b" if ev_tickers[ticker] < 0 else "#0b6e4f" for ticker in TICKERS]
    bars = ax_ticker.bar(TICKERS, [ev_tickers[ticker] for ticker in TICKERS], color=ticker_colors)
    ax_ticker.axhline(0, color="#222", linewidth=0.8)
    ax_ticker.set_title("Contribución EV por ticker", loc="left", weight="bold")
    ax_ticker.set_ylabel("USD")
    ax_ticker.grid(axis="y", alpha=0.18)
    ax_ticker.bar_label(bars, labels=[fmt_usd(ev_tickers[ticker]) for ticker in TICKERS], padding=3, fontsize=8)

    ax_table.axis("off")
    columns = ["Política", "Neto", "PF", "Trades", "DD realizado"]
    rows = []
    for policy, (label, _) in POLICIES.items():
        item = computed[policy]
        rows.append([label, fmt_usd(item["net_usd"]), fmt_pf(item["profit_factor"]), str(item["trades"]), fmt_usd(item["realized_max_drawdown_usd"])])
    table = ax_table.table(
        cellText=rows, colLabels=columns, cellLoc="center", colLoc="center", loc="center",
        colWidths=[0.25, 0.19, 0.11, 0.13, 0.25],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.2)
    table.scale(1.05, 1.75)
    for (row, _), cell in table.get_celld().items():
        cell.set_edgecolor("#d9dde3")
        if row == 0:
            cell.set_facecolor("#243447")
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#ffffff" if row % 2 else "#eef2f5")
    ax_table.set_title("Resumen económico EVAL adverso", loc="left", weight="bold", pad=12)

    concentration = computed["EV_TOP1_H2"]["concentration"]
    ax_table.text(
        0.0, 0.04,
        f"Concentración EV: mayor ganancia {fmt_usd(concentration['largest_gain_usd'])} "
        f"({concentration['ticker']} {concentration['right']}, salida {concentration['exit_date']}); "
        f"sin ella: {fmt_usd(concentration['net_without_largest_gain_usd'])}.",
        transform=ax_table.transAxes, fontsize=8.2, color="#a33", va="bottom", wrap=True,
    )

    missing_total = computed["EV_TOP1_H2"]["missing_exit_total"]
    fig.suptitle("WEEKLY H2 V2 — reporte descriptivo, sin selección", x=0.06, y=0.975, ha="left", fontsize=18, weight="bold")
    fig.text(0.06, 0.943, "H1 2026 es desarrollo visto (SEEN_DEVELOPMENT). Resultado no auditado independientemente ni apto para promoción.", ha="left", color="#a33", fontsize=10.5)
    fig.text(
        0.06, 0.018,
        f"Coste adverso. Equity y drawdown sólo realizados (sin mark-to-market). Missing exits EV: {missing_total}; se valoran como pérdida total y son cotas inferiores, no observaciones de mercado. "
        "Beneficio concentrado en abril y en una operación SPXW; el desglose/sensibilidad no autoriza rescate ni política alternativa.",
        ha="left", fontsize=9, color="#343a40",
    )
    fig.savefig(output / "weekly_h2_v2_descriptive.png", dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(output / "weekly_h2_v2_descriptive.svg", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> int:
    require(not OUTPUT_ROOT.exists(), f"immutable output exists: {OUTPUT_ROOT}")
    dataset_manifest, eval_manifest, ledgers, summary = load_pinned_inputs()
    computed = {policy: ledger_metrics(ledger) for policy, ledger in ledgers.items()}
    reconcile(summary, computed)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=False)
    render_figure(computed, OUTPUT_ROOT)
    table = {
        "schema": "weekly_h2_v2_descriptive_table_v1",
        "status": "DESCRIPTIVE_SEEN_DEVELOPMENT_NOT_INDEPENDENTLY_AUDITED",
        "scope": {"split": "EVAL_20260101_20260630", "cost": "adverse", "starting_cash_usd": STARTING_CASH},
        "policies": computed,
        "notes": {
            "drawdown": "realized_only_not_mark_to_market",
            "missing_exits": "total_loss_lower_bounds_not_observed_market_exits",
            "ticker_contribution": "descriptive_only_no_ticker_rescue_or_selection",
            "promotion_approved": False,
        },
    }
    write_json(OUTPUT_ROOT / "report_table.json", table)
    # Rehash all authorities after rendering, before publishing the report manifest.
    require(sha256_file(DATASET_ROOT / "manifest.json") == DATASET_MANIFEST_SHA256, "dataset manifest changed during report")
    require(sha256_file(EVAL_ROOT / "manifest.json") == EVAL_MANIFEST_SHA256, "evaluation manifest changed during report")
    for policy in POLICIES:
        name = f"ledger_{policy.lower()}_eval_adverse.jsonl"
        require(sha256_file(EVAL_ROOT / name) == eval_manifest["outputs"][name]["sha256"], f"ledger changed {policy}")
    require(sha256_file(EVAL_ROOT / "summary.json") == eval_manifest["outputs"]["summary.json"]["sha256"], "summary changed")
    outputs = {}
    for path in sorted(OUTPUT_ROOT.iterdir()):
        outputs[path.name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    manifest = {
        "schema": "weekly_h2_v2_descriptive_report_manifest_v1",
        "status": "COMPLETE_DESCRIPTIVE_REPORT_NOT_INDEPENDENTLY_AUDITED",
        "inputs": {
            "dataset_manifest": {"path": str(DATASET_ROOT / "manifest.json"), "sha256": DATASET_MANIFEST_SHA256},
            "evaluation_manifest": {"path": str(EVAL_ROOT / "manifest.json"), "sha256": EVAL_MANIFEST_SHA256},
            "summary.json": eval_manifest["outputs"]["summary.json"],
            "eval_adverse_ledgers": {
                policy: eval_manifest["outputs"][f"ledger_{policy.lower()}_eval_adverse.jsonl"] for policy in POLICIES
            },
            "dataset_status": dataset_manifest["status"],
        },
        "implementation": {"report_weekly_h2_v2.py": sha256_file(Path(__file__))},
        "reconciliations": {
            "ledger_vs_summary": True,
            "monthly_sum_vs_net": True,
            "ticker_sum_vs_net": True,
            "cash_basis": "realized_only_starting_100000",
        },
        "outputs": outputs,
        "flags": {"descriptive_only": True, "development_seen": True, "independently_audited": False, "promotion_approved": False},
    }
    write_json(OUTPUT_ROOT / "manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
