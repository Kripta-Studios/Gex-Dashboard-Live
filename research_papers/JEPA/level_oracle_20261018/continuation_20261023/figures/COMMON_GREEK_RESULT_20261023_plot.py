"""Render all fixed-policy monthly base net values from the closed audited report."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
import numpy as np  # noqa: E402

REPORT_SHA = "6086af9fba7d5a7423a36eda120c9873415a9c3f3f5b61d9fea0bfa3ab47183c"
AUDIT_SHA = "45caae6c11cdce9306284367e7742d9dbe17e03a8afeb52eff447b3408758a0d"
POLICIES = ("cue_net__0", "common_greek_net__0")
TICKERS = ("QQQ", "SPY", "SPXW")
MONTHS = tuple(f"2025{month:02d}" for month in range(1, 13)) + tuple(
    f"2026{month:02d}" for month in range(1, 7)
)
PREFIX = "COMMON_GREEK_RESULT_20261023"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def render(summary, audit_path, output):
    summary, audit_path, output = map(lambda p: Path(p).resolve(), (summary, audit_path, output))
    require(sha(summary) == REPORT_SHA, "Closed report pin mismatch")
    require(sha(audit_path) == AUDIT_SHA, "Independent audit pin mismatch")
    report = json.loads(summary.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    require(audit["status"] == "PASS_INDEPENDENT_COMMON_GREEK_COMPARISON_ECONOMIC_AUDIT",
            "Independent economic audit is not PASS")
    require(report["status"] == "COMPLETE_DESCRIPTIVE_MONTHLY_REPORT", "Report is incomplete")
    require(report["policy_selection"] is False and report["development_seen"] is True
            and report["new_fits"] == report["new_predictions"] == 0
            and report["promotion_approved"] is False, "Descriptive scope differs")
    require(report["sources"].get(str(audit_path)) == AUDIT_SHA, "Report/audit binding differs")
    rows = report["months"]
    indexed = {(row["policy"], row["ticker"], row["month"]): row for row in rows}
    expected = {(policy, ticker, month) for policy in POLICIES for ticker in TICKERS for month in MONTHS}
    require(len(rows) == len(indexed) == 108 and set(indexed) == expected,
            "Need exactly both policies, three tickers and all eighteen months")
    plotted = []
    for policy, ticker, month in sorted(expected):
        row = indexed[(policy, ticker, month)]
        missing = ["20260401", "20260409", "20260415"] if month == "202604" and ticker in ("QQQ", "SPY") else []
        require(sorted(row["missing_dates"]) == missing and row["missing_days"] == len(missing),
                "Missing-calendar annotation differs")
        require(row["expected_days"] == row["available_days"] + len(missing), "Coverage mismatch")
        require(np.isfinite(row["base"]["net_usd"]), "Nonfinite base net")
        plotted.append({key: row[key] for key in ("policy", "ticker", "month", "expected_days",
                                                 "available_days", "missing_days", "missing_dates")}
                       | {"net_base_usd": row["base"]["net_usd"]})
    output.mkdir(parents=True, exist_ok=True)
    paths = {kind: output / f"{PREFIX}_{name}" for kind, name in (
        ("png", "monthly_net_base.png"), ("svg", "monthly_net_base.svg"),
        ("provenance", "provenance.json"))}
    require(all(not path.exists() for path in paths.values()), "Immutable figure outputs already exist")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "svg.hashsalt": PREFIX, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.titleweight": "bold"})
    colors = ("#0072B2", "#D55E00")
    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    fig.subplots_adjust(left=0.095, right=0.98, top=0.82, bottom=0.17, hspace=0.3)
    fig.suptitle("Common Greek · neto mensual con costes base", x=0.095, y=0.97,
                 ha="left", fontsize=21, fontweight="bold")
    fig.text(0.095, 0.925, "Dos políticas fijas · 18 meses × 3 tickers · SEEN_DEVELOPMENT",
             fontsize=13, color="#333333")
    legend = [Patch(facecolor=colors[0], label="152 features · cue_net__0"),
              Patch(facecolor=colors[1], label="424 features · common_greek_net__0")]
    fig.legend(handles=legend, loc="upper left", bbox_to_anchor=(0.09, 0.90),
               frameon=False, ncol=2, fontsize=11)
    x = np.arange(len(MONTHS))
    for ax, ticker in zip(axes, TICKERS, strict=True):
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#dce0e3", linewidth=0.7)
        ax.axhline(0, color="#333333", linewidth=0.9)
        ax.axvline(11.5, color="#666666", linestyle=(0, (4, 3)), linewidth=1)
        if ticker in ("QQQ", "SPY"):
            ax.axvspan(14.55, 15.45, facecolor="#F6E7BC", alpha=0.65, zorder=0)
            ax.text(15, 1.02, "Abr 2026*", transform=ax.get_xaxis_transform(),
                    ha="center", fontsize=9, color="#71530A")
        for index, policy in enumerate(POLICIES):
            values = [indexed[(policy, ticker, month)]["base"]["net_usd"] for month in MONTHS]
            ax.bar(x + (-0.2 if index == 0 else 0.2), values, width=0.36,
                   color=colors[index], zorder=3)
        ax.set_title(ticker, loc="left", pad=7, fontsize=13)
        ax.set_ylabel("Neto base (USD)")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value:,.0f}".replace(",", " ")))
        ax.margins(y=0.16)
        ax.set_xlim(-0.7, 17.7)
    labels = [f"{name}\n25" for name in ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")]
    labels += [f"{name}\n26" for name in ("Ene", "Feb", "Mar", "Abr", "May", "Jun")]
    axes[-1].set_xticks(x, labels)
    axes[-1].tick_params(axis="x", length=0, pad=8)
    fig.text(0.095, 0.09,
             "* Abril 2026: faltan QQQ y SPY en los días 1, 9 y 15 (6 ticker-días). "
             "Se muestran sólo netos observados; no se imputan ceros.", fontsize=10)
    fig.text(0.095, 0.063,
             "Escala Y distinta por ticker. Cada barra es el neto mensual de una política fija; "
             "no son retornos de cuenta ni evidencia prospectiva.", fontsize=10, color="#444444")
    fig.text(0.095, 0.036,
             "Fuente: reporte descriptivo cerrado + auditoría económica independiente 02. "
             "Sin selección de política, ticker o mes.", fontsize=9, color="#555555")
    fig.savefig(paths["png"], dpi=180, facecolor="white", metadata={"Software": PREFIX})
    fig.savefig(paths["svg"], facecolor="white", metadata={"Date": None, "Creator": PREFIX})
    plt.close(fig)
    require(sha(summary) == REPORT_SHA and sha(audit_path) == AUDIT_SHA, "Consumed inputs changed")
    record = dict(scope="DESCRIPTIVE_FIXED_POLICY_MONTHLY_BASE_NET_SEEN_DEVELOPMENT",
                  inputs={str(summary): REPORT_SHA, str(audit_path): AUDIT_SHA},
                  script={str(Path(__file__).resolve()): sha(__file__)},
                  versions=dict(python=platform.python_version(), matplotlib=matplotlib.__version__,
                                numpy=np.__version__),
                  rows=plotted, bars=108, selection=False, new_models=0, new_replays=0,
                  missing_days_imputed=False, y_scales="independent by ticker; common to both policies",
                  outputs={str(paths[k]): sha(paths[k]) for k in ("png", "svg")})
    paths["provenance"].write_text(json.dumps(record, indent=2, sort_keys=True, allow_nan=False),
                                  encoding="utf-8")
    print(json.dumps({str(path): sha(path) for path in paths.values()}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--audit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    render(args.summary, args.audit, args.output)
