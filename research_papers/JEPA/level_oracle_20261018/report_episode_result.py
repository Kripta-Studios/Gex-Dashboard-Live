"""Render completed episode results without fitting or changing any policy."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render(root, destination):
    out = root / "episode_learners_v1"
    summary = read(out / "summary.json")
    if summary["status"] != "COMPLETED_EPISODE_LEARNER_DEVELOPMENT":
        raise ValueError("Producer not complete")
    complete = read(out / "completion.complete.json")
    summary_path = str((out / "summary.json").resolve())
    if complete["artifacts"][summary_path] != digest(out / "summary.json"):
        raise ValueError("Final summary hash differs")
    repair = read(out / "technical_repairs/source_path_v1/completion.json")
    if repair["refits"] != 0 or repair["summary_sha256"] != digest(
        out / "summary.json"
    ):
        raise ValueError("Technical continuation binding differs")
    freeze = read(out / "freeze.json")
    selected = summary["selected_policy"]
    diagnostic = summary["diagnostic_policy"]
    lines = [
        "# GBT con episodios causales: resultado de desarrollo",
        "",
        f"Estado de selección: `{summary['selection_status']}`. "
        f"Política seleccionada: `{selected['policy'] if selected else 'ninguna'}`. "
        f"Diagnóstico congelado: `{diagnostic['policy'] if diagnostic else 'ninguno'}`.",
        f"Gate combinado: **{summary['combined_gate_passes']}**; promoción: false.",
        "",
        "Una variante, un fit de 200 árboles, muestra original de 270.377 acciones. "
        "Las primeras 1.954 columnas son bit a bit idénticas al control; se añaden "
        "35 valores de episodios y 35 máscaras. El control reutiliza modelo y scores "
        "verificados, sin refit. Train 2023–2024; selección 2025; contraste enero–junio "
        "2026 ya visto. Es investigación post-resultados, sin outer intacto.",
        "",
        "El modelo elige cuándo entrar dentro del universo causal de zonas. No se "
        "fuerza una entrada: cada día disponible sin ejecución incumple el requisito. "
        "Las fuentes ausentes permanecen NO_EVALUABLE y fallan cobertura por separado. "
        "Las salidas siguen target/stop por niveles o EOD, sin hold fijo.",
        "",
        "El gate diario se calcula sobre el universo congelado de sesiones completas. "
        "El requisito universal de operar cada día bursátil queda NO_ACREDITADO: "
        "las medias sesiones están fuera de ese universo y existen seis ticker-días "
        "test sin fuente. Esta limitación no cambia retrospectivamente la selección "
        "2025 ni los resultados del experimento.",
        "",
        "Alcance calendario: se excluyen dos medias sesiones en 2023, tres en 2024 "
        "y tres en 2025: 24 ticker-días en total. Validación contiene 741 ticker-días "
        "frente a los 750 del calendario NYSE completo. H1 2026 no tiene medias "
        "sesiones: 369 ticker-días esperados, 363 disponibles y seis NO_EVALUABLE. "
        "La existencia de candidatos raw para medias sesiones no los incorpora "
        "retroactivamente a este experimento.",
        "",
        "El primer runtime terminó tras el fit por cuatro joins erróneos de rutas "
        "de metadatos, antes de publicar nuevas predicciones o abrir labels de "
        "validación. Un wrapper separado y revisado corrigió sólo esas rutas. "
        "El código original, fallo y modelo permanecen preservados; continuación "
        "con constructor de fit prohibido y cero refits verificados.",
        "",
    ]
    rows = []
    for period in ("validation", "test"):
        reports = read(out / period / "summary.json")
        lines += [
            f"## {period}",
            "",
            "| Política | Días disponibles sin fill | No evaluables | Viable |",
            "|---|---:|---:|---|",
        ]
        for policy, report in reports.items():
            compliance = report["daily_compliance"]
            lines.append(
                f"| {policy} | {compliance['days_without_fill']} | {compliance['no_evaluable_ticker_days']} | {compliance['viable']} |"
            )
        lines += [
            "",
            "| Política | Ticker | Trades | Días sin fill / disponibles | No evaluables | Neto base USD | Neto adverso USD | PF base | Meses positivos | Hold min/med/max |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
        for policy, report in reports.items():
            daily = pd.read_csv(out / period / (policy + "_daily_compliance.csv"))
            for ticker, metrics in report["tickers"].items():
                ticker_days = daily.loc[daily.ticker == ticker]
                available = ticker_days.source_status == "EVALUABLE"
                empty_days = int((ticker_days.loc[available, "fills"] < 1).sum())
                available_days = int(available.sum())
                missing_days = int((~available).sum())
                positive = sum(
                    m["base_net_usd"] > 0 for m in report["months"][ticker].values()
                )
                hold = metrics["holding_minutes"]
                holding = "/".join(str(hold.get(k)) for k in ("min", "median", "max"))
                row = dict(
                    period=period,
                    policy=policy,
                    ticker=ticker,
                    positive_months=positive,
                    days_without_fill=empty_days,
                    available_days=available_days,
                    no_evaluable_days=missing_days,
                    **metrics,
                )
                rows.append(row)
                pf = (
                    "inf"
                    if metrics["base_pf_infinite"]
                    else "NA"
                    if metrics["base_pf"] is None
                    else f"{metrics['base_pf']:.3f}"
                )
                lines.append(
                    f"| {policy} | {ticker} | {metrics['trades']} | {empty_days}/{available_days} | {missing_days} | {metrics['base_net_usd']:.2f} | {metrics['adverse_net_usd']:.2f} | {pf} | {positive}/{len(report['months'][ticker])} | {holding} |"
                )
        lines += [
            "",
            "| Política | Ticker | Salida | Trades | Neto base USD | Neto adverso USD |",
            "|---|---|---|---:|---:|---:|",
        ]
        for policy, report in reports.items():
            for ticker, metrics in report["tickers"].items():
                for reason, values in metrics["exit_reasons"].items():
                    lines.append(
                        f"| {policy} | {ticker} | {reason} | {values['trades']} | {values['base_net_usd']:.2f} | {values['adverse_net_usd']:.2f} |"
                    )
        lines.append("")
    lines += [
        "## Comparaciones pareadas H1 2026",
        "",
        "Diferencias variante menos control; bootstrap de 10.000 muestras de fechas completas. "
        "La suma normalizada usa escalas train fijas SPXW680/SPY81/QQQ88 USD. "
        "La referencia cero es contabilidad, no una política seleccionable.",
        "",
        "| Comparación | Coste | Diferencia normalizada | IC95 normalizado |",
        "|---|---|---:|---|",
    ]
    for name, result in read(out / "paired_comparisons.json").items():
        for scenario in ("base", "adverse"):
            item = result[scenario]
            ci = item["ci95_tickers_then_normalized"]
            lines.append(
                f"| {name} | {scenario} | {item['normalized_difference']:.3f} | [{ci[0][-1]:.3f}, {ci[1][-1]:.3f}] |"
            )
    lines += [
        "",
        "## Integridad y alcance",
        "",
        f"Summary SHA256: `{digest(out / 'summary.json')}`.",
        f"Freeze SHA256: `{digest(out / 'freeze.json')}`.",
        f"Freeze antes de labels nuevos de test: `{not freeze['new_test_labels_opened']}`.",
        "",
        "La auditoría económica independiente se informa por su artefacto propio. "
        "Estos resultados no prueban recepción histórica observada, paridad live ni rentabilidad futura. "
        "El fracaso de esta variante tampoco demuestra que todo uso de niveles carezca de edge: "
        "acota esta representación, objetivo, muestra y reglas de ejecución. "
        "No hubo cambios de parámetros por resultados, nuevas descargas, órdenes o producción.",
        "",
    ]
    destination.write_text("\n".join(lines), encoding="utf-8")
    pd.json_normalize(rows).to_csv(destination.with_suffix(".csv"), index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    render(args.root.resolve(), args.destination.resolve())
