"""Read-only reporting of the frozen learner; never chooses a policy from test."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TICKERS = ("SPXW", "SPY", "QQQ")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def number(value):
    return "—" if value is None else f"{value:,.2f}"


def daily_uncertainty(daily):
    """Fixed descriptive bootstrap, shared calendar blocks across all tickers."""
    values = daily.loc[:, TICKERS].to_numpy(dtype=float)
    n = len(values)
    if n == 0 or not np.isfinite(values).all():
        raise ValueError("A finite full daily calendar is required")
    rng = np.random.default_rng(20261018)
    starts = rng.integers(0, n, size=(10_000, (n + 4) // 5))
    indices = ((starts[:, :, None] + np.arange(5)) % n).reshape(10_000, -1)[:, :n]
    totals = values[indices].sum(axis=1)
    intervals = np.quantile(totals, [0.025, 0.975], axis=0)
    return {
        "method": "circular blocks of 5 trading days, shared across tickers",
        "draws": 10_000,
        "seed": 20261018,
        "days": n,
        "scope": "descriptive conditional on the frozen selected policy; not selection-adjusted or prospective",
        "selection_or_gate_changed": False,
        "tickers": {
            ticker: {
                "net_usd": float(values[:, i].sum()),
                "bootstrap_total_95_low": float(intervals[0, i]),
                "bootstrap_total_95_high": float(intervals[1, i]),
            }
            for i, ticker in enumerate(TICKERS)
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-root", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--learner-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result_path = args.learner_root / "summary.json"
    result = read_json(result_path)
    audit = read_json(args.audit)
    if result["status"] != "COMPLETED_CAUSAL_LEARNER_DEVELOPMENT":
        raise ValueError("Learner incomplete")
    if audit["status"] != "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT":
        raise ValueError("Full oracle audit is not PASS")
    if Path(audit["engine_root"]).resolve() != args.engine_root.resolve():
        raise ValueError("Audit belongs to another engine dataset")
    if digest(args.engine_root / "index.parquet") != audit["index_sha256"]:
        raise ValueError("Oracle index differs from the audited index")
    freeze = read_json(args.learner_root / "freeze.json")
    selected = result["selected_policy"]["policy"]
    # The policy name comes exclusively from validation selection, never test ranking.
    if freeze["selected_policy"]["policy"] != selected:
        raise ValueError("Final selection differs from pre-test freeze")
    index = pd.read_parquet(args.engine_root / "index.parquet")
    index["date"] = index["date"].astype(str)
    test_index = index.loc[index.date.between("20260101", "20260630")]
    calendar = pd.read_csv(
        args.learner_root / "expected_full_calendar.csv", dtype={"date": str}
    ).date
    calendar = calendar.loc[calendar.between("20260101", "20260630")]
    oracle = (
        test_index.groupby(["date", "ticker"])
        .net_base.sum()
        .unstack(fill_value=0)
        .reindex(index=calendar, columns=TICKERS, fill_value=0)
        .fillna(0)
    )
    tests = read_json(args.learner_root / "test" / "summary.json")
    daily = {}
    for policy, summary in tests.items():
        path = args.learner_root / "test" / f"{policy}_daily_net.csv"
        frame = pd.read_csv(path, dtype={"date": str}).set_index("date")
        frame = frame.reindex(index=calendar, columns=TICKERS)
        if frame.isna().any().any():
            raise ValueError("Incomplete daily candidate calendar")
        for ticker in TICKERS:
            if not math.isclose(
                frame[ticker].sum(),
                summary["tickers"][ticker]["base_net_usd"],
                rel_tol=0,
                abs_tol=1e-6,
            ):
                raise ValueError("Daily ledger and summary disagree")
        daily[policy] = frame
    chosen = (
        pd.DataFrame(0.0, index=calendar, columns=TICKERS)
        if selected == "CASH"
        else daily[selected]
    )
    args.output.mkdir(parents=True, exist_ok=False)
    uncertainty = daily_uncertainty(chosen)
    (args.output / "daily_uncertainty.json").write_text(
        json.dumps(uncertainty, indent=2), encoding="utf-8"
    )
    dates = pd.to_datetime(calendar, format="%Y%m%d")
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), sharex=True)
    for col, ticker in enumerate(TICKERS):
        ax = axes[0, col]
        for policy, frame in daily.items():
            if policy != selected:
                ax.plot(
                    dates, frame[ticker].cumsum(), color="#a8afb9", alpha=0.48, lw=0.8
                )
        ax.plot(
            dates,
            chosen[ticker].cumsum(),
            color="#176b87",
            lw=2.5,
            label=f"Seleccionada: {selected}",
        )
        ax.axhline(0, color="#444", lw=0.7)
        ax.set_title(f"{ticker} · política causal congelada")
        ax.set_ylabel("PnL neto acumulado, USD")
        ax.grid(alpha=0.18)
        ax.legend(fontsize=7, loc="best")
        ax = axes[1, col]
        ax.plot(dates, oracle[ticker].cumsum(), color="#b86418", lw=2)
        ax.set_title(f"{ticker} · ORACLE CON FUTURO")
        ax.set_ylabel("Techo retrospectivo, USD")
        ax.grid(alpha=0.18)
        ax.tick_params(axis="x", rotation=30)
    fig.suptitle(
        "Enero–junio 2026 · desarrollo ya explorado · un contrato por operación",
        fontsize=14,
    )
    fig.text(
        0.5,
        0.015,
        "Gris: candidatos diagnósticos; no sustituyen la elección de 2025. "
        "Ejes verticales independientes. El oracle no es operable.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(args.output / "causal_vs_oracle.png", dpi=160)
    plt.close(fig)
    lines = [
        "# Resultado de aprendizaje por niveles",
        "",
        f"Política seleccionada únicamente con 2025: **{selected}**.",
        f"Gate de desarrollo: **{result['provisional_gate']['passes']}**.",
        "",
        "El oracle utiliza el futuro. La evaluación causal de enero–junio2026 "
        "es desarrollo ya explorado, no una validación prospectiva. "
        "Los resultados son dólares por operaciones de un contrato; no rentabilidad "
        "porcentual de una cuenta financiada.",
        "",
        "| Ticker | Trades | Neto base USD | Neto adverso USD | PF base | Máx. drawdown realizado USD |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for ticker in TICKERS:
        if selected == "CASH":
            lines.append(f"| {ticker} | 0 | 0.00 | 0.00 | — | 0.00 |")
        else:
            row = result["selected_test"]["tickers"][ticker]
            pf = "∞" if row["base_pf_infinite"] else number(row["base_pf"])
            lines.append(
                f"| {ticker} | {row['trades']} | {number(row['base_net_usd'])} | "
                f"{number(row['adverse_net_usd'])} | {pf} | "
                f"{number(row['base_max_drawdown_usd'])} |"
            )
    if selected == "CASH":
        lines.extend(
            ["", "CASH no cumple el objetivo de encontrar un aprendiz rentable."]
        )
    lines.extend(
        [
            "",
            "| Ticker | Intervalo bootstrap95% del neto USD |",
            "|---|---:|",
        ]
    )
    for ticker in TICKERS:
        item = uncertainty["tickers"][ticker]
        lines.append(
            f"| {ticker} | [{number(item['bootstrap_total_95_low'])}, "
            f"{number(item['bootstrap_total_95_high'])}] |"
        )
    lines.extend(
        [
            "",
            "Intervalos descriptivos:10.000 remuestreos en bloques circulares "
            "de5 sesiones, alineados entre instrumentos y con semilla fija. "
            "Son condicionales a la política elegida, no corrigen la selección ni "
            "el uso previo del histórico y no cambian el gate. "
            "Un intervalo que incluye cero no distingue beneficio de pérdida "
            "bajo este remuestreo.",
        ]
    )
    lines.extend(
        [
            "",
            "![Curvas causales y oracle](causal_vs_oracle.png)",
            "",
            "Las líneas grises muestran todos los candidatos congelados de forma "
            "diagnóstica. No se elige el mejor resultado del periodo de evaluación. "
            "Las duraciones y salidas TARGET/STOP/EOD constan en el summary del aprendiz.",
        ]
    )
    (args.output / "RESULT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sources = [
        result_path,
        args.audit,
        args.engine_root / "index.parquet",
        args.learner_root / "freeze.json",
        args.learner_root / "test" / "summary.json",
    ]
    manifest = {
        "sources": {str(p.resolve()): digest(p) for p in sources},
        "report_code_sha256": digest(Path(__file__)),
        "selected_policy": selected,
        "selection_changed": False,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
