"""Render the fixed descriptive calibration tables; no selection or fits."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    if summary["status"] != "COMPLETE_DESCRIPTIVE_MAX_SCORE_CALIBRATION":
        raise ValueError("Diagnostic incomplete")
    for name, wanted in summary["artifacts"].items():
        if sha(root / name) != wanted:
            raise ValueError("Diagnostic output changed")
    metrics = pd.read_csv(root / "summary_metrics.csv")
    differences = pd.read_csv(root / "paired_differences.csv")
    lines = [
        "# Calibración general y selección por máximo", "",
        "Diagnóstico descriptivo cerrado sobre TRAIN96 y VAL741 ya vistos; dos modelos "
        "congelados, cero fits e inferencias nuevas. No cambia políticas ni el resultado "
        "económico anterior. Se verificaron scores/IDs/estado y traza de ejecución.", "",
        "Cada día pesa igual; dentro de cada día pesan igual sus acciones, sus estados "
        "con candidatos o sus trades ejecutados, según cohorte. Los días sin unidades "
        "se cuentan y tienen media indefinida. Las medias de ejecución no coinciden "
        "necesariamente con la media por trade del diagnóstico anterior, que daba "
        "igual peso a cada trade. NO_FILL aporta neto0 en todasacciones/argmax.", "",
        "Argmax se calcula por estado antes de umbral y sin restricciones por posición; "
        "incluye máximos negativos y conserva NO_FILL. No constituye una cartera "
        "ejecutable. La cohorte de trades ejecutados sí condiciona a ejecución "
        "observada y disponibilidad del scheduler. Error es score menos neto.", "",
    ]
    train_all = metrics.loc[(metrics.split == "train") & (metrics.cohort == "all_actions")]
    val_all = metrics.loc[(metrics.split == "validation") & (metrics.cohort == "all_actions")]
    val_argmax = metrics.loc[(metrics.split == "validation") & (metrics.cohort == "argmax_before_threshold")]
    val_change = differences.loc[(differences.split == "validation") &
        (differences.comparison == "argmax_before_threshold_MINUS_all_actions")]
    lines += [
        "La correlación en todas las acciones va de "
        f"{train_all.correlation.min():.3f} a {train_all.correlation.max():.3f} en TRAIN, "
        f"y de {val_all.correlation.min():.3f} a {val_all.correlation.max():.3f} en VAL. "
        f"Tras argmax, la correlación VAL va de {val_argmax.correlation.min():.3f} "
        f"a {val_argmax.correlation.max():.3f}. En {int((val_change.error_difference > 0).sum())} "
        f"de {len(val_change)} combinaciones ticker/modelo, elegir el máximo aumenta "
        "el error medio frente a todas las acciones. Hay por tanto degradación "
        "general observada y una amplificación al seleccionar máximos; no se "
        "reduce descriptivamente a un único desplazamiento constante de calibración. "
        "Esto es compatible con pérdida de generalización y optimismo de selección, "
        "sin demostrar el mecanismo causal ni que corregir uno baste para rentabilidad.", "",
    ]
    for split in ("train", "validation"):
        lines += [f"## {split}", "",
            "| Modelo | Ticker | Cohorte | Días con unidades/esperados | Unidades | Score medio USD | Neto medio USD | Error USD | MAE | RMSE | Correlación |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for row in metrics.loc[metrics.split == split].itertuples():
            lines.append(f"| {row.model} | {row.ticker} | {row.cohort} | {row.nonempty_days}/{row.expected_days} | "
                f"{row.units} | {row.predicted_mean_usd:.3f} | {row.realized_mean_usd:.3f} | {row.mean_error_usd:.3f} | "
                f"{row.mae_usd:.3f} | {row.rmse_usd:.3f} | {row.correlation:.4f} |")
        lines += [""]
    lines += ["## Contrastes fijados", "",
        "Diferencia entre medias diarias usando sólo días con ambas cohortes definidas. "
        "No confundir el aumento de error condicionado al máximo con una causa "
        "demostrada o con una reparación seleccionada.", "",
        "| Periodo | Modelo | Ticker | Contraste | Días comunes | Δscore USD | Δneto USD | Δerror USD |",
        "|---|---|---|---|---:|---:|---:|---:|"]
    for row in differences.itertuples():
        lines.append(f"| {row.split} | {row.model} | {row.ticker} | {row.comparison} | {row.paired_days} | "
            f"{row.pred_difference:.3f} | {row.real_difference:.3f} | {row.error_difference:.3f} |")
    lines += ["", "## Integridad y límites", "",
        f"Summary SHA256 `{sha(root / 'summary.json')}`; fuentes verificadas `{summary['source_count']}`; "
        f"duración `{summary['wall_seconds']:.3f}s`.", "",
        "Los CSV conservan conteos FILLED/NO_FILL, días vacíos, momentos diarios y "
        "contrastes MAE/error². La correlación se obtiene de momentos ponderados "
        "conjuntos, no del promedio de correlaciones diarias. TRAIN comparte exposición "
        "al ajuste y no es un holdout. VAL sigue siendo desarrollo visto. Cambios "
        "de calibración general, composición, selección del máximo y generalización "
        "son explicaciones compatibles; este diseño observacional no separa sus "
        "causas ni acredita rentabilidad futura.", ""]
    args.destination.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
