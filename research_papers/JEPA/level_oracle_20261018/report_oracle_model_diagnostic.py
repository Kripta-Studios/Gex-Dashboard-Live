"""Descriptive reporting only; never fits, selects, or changes policies."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def render(root, destination, phase="all"):
    rows, paths, signals, timing, calibration = [], [], [], [], []
    phases = (("validation", 741),) if phase == "validation" else (("validation", 741), ("train", 96))
    for split, expected in phases:
        folder = root / split
        completion = read(folder / "completion.json") if (folder / "completion.json").exists() else None
        if completion is not None and completion["days"] != expected:
            raise ValueError("Wrong phase coverage")
        markers = sorted(folder.glob("*.complete.json"))
        if len(markers) != expected:
            raise ValueError("Wrong checkpoint count")
        frames, timing_frames, phase_counts = [], [], []
        for marker in markers:
            record = read(marker)
            if record["identity"] != digest(root / "identity.json"):
                raise ValueError("Diagnostic identity differs")
            phase_counts.extend(record["action_counts"])
            for name, wanted in record["artifacts"].items():
                path = Path(name)
                if digest(path) != wanted:
                    raise ValueError(f"Changed diagnostic output: {path}")
                if path.suffix == ".parquet" and not path.stem.endswith("_timing"):
                    frames.append(pd.read_parquet(path))
                elif path.suffix == ".parquet":
                    timing_frames.append(pd.read_parquet(path))
        full = pd.concat(frames, ignore_index=True)
        phase_paths = []
        for (model, ticker), group in full.groupby(["model", "ticker"]):
            for policy in ("model", "oracle"):
                executed = group.loc[group[policy + "_free"] & group[policy + "_filled"]]
                target = executed[policy + "_target_distance_ib"]
                stop = executed[policy + "_stop_distance_ib"]
                ratio = target / stop.where(stop > 0)
                score = executed.model_score if policy == "model" else None
                phase_paths.append(dict(
                    split=split, model=model, ticker=ticker, policy=policy,
                    trades=len(executed), net_base=float(executed[policy + "_net"].sum()),
                    traded_days=executed.date.nunique(), available_days=group.date.nunique(),
                ))
                calibration.append(dict(
                    split=split, model=model, ticker=ticker, policy=policy,
                    trades=len(executed),
                    mean_score_usd=float(score.mean()) if score is not None else None,
                    sum_score_usd=float(score.sum()) if score is not None else None,
                    mean_net_usd=float(executed[policy + "_net"].mean()),
                    sum_net_usd=float(executed[policy + "_net"].sum()),
                    mean_prediction_error_usd=float((score - executed.model_net).mean()) if score is not None else None,
                    target_distance_ib_median=float(target.median()),
                    stop_distance_ib_median=float(stop.median()),
                    target_stop_ratio_median=float(ratio.median()),
                    ratio_undefined_count=int(ratio.isna().sum()),
                    hold_minutes_median=float(executed[policy + "_hold_minutes"].median()),
                ))
            for cohort in ("model_free", "oracle_free"):
                available = group.loc[group[cohort] & group.has_actions]
                both = available.loc[
                    (available.model_action_id >= 0)
                    & (available.oracle_action_id >= 0)
                ]
                rows.append(
                    dict(
                        split=split,
                        model=model,
                        ticker=ticker,
                        cohort=cohort,
                        offered_states=len(available),
                        both_trade_states=len(both),
                        same_direction_fraction=both.same_direction.astype(float).mean(),
                        same_contract_fraction=both.same_contract.astype(float).mean(),
                        same_target_fraction=both.same_target.astype(float).mean(),
                        oracle_rank_median=available.oracle_score_rank.median(),
                        model_wait_oracle_trade=int(
                            (available.category == "MODEL_WAIT_ORACLE_TRADE").sum()
                        ),
                        model_trade_oracle_wait=int(
                            (available.category == "MODEL_TRADE_ORACLE_WAIT").sum()
                        ),
                        different_action=int(
                            (available.category == "DIFFERENT_ACTION").sum()
                        ),
                        same_action=int((available.category == "SAME_ACTION").sum()),
                        blocked_oracle_states=int(available.blocked_oracle_trade.sum()),
                        model_target_distance_ib=both.model_target_distance_ib.median(),
                        oracle_target_distance_ib=both.oracle_target_distance_ib.median(),
                        model_stop_distance_ib=both.model_stop_distance_ib.median(),
                        oracle_stop_distance_ib=both.oracle_stop_distance_ib.median(),
                        model_abs_delta=both.model_selected_delta.abs().median(),
                        oracle_abs_delta=both.oracle_selected_delta.abs().median(),
                        model_hold_minutes=both.model_hold_minutes.median(),
                        oracle_hold_minutes=both.oracle_hold_minutes.median(),
                    )
                )
        paths.append(pd.DataFrame(phase_paths))
        signals.append(pd.DataFrame(phase_counts))
        timing_frame = pd.concat(timing_frames, ignore_index=True)
        for field in ("original_fill", "shifted_fill"):
            timing_frame[field] = timing_frame[field].map(lambda value: pd.NA if pd.isna(value) else bool(value)).astype("boolean")
        timing.append(timing_frame.groupby(
            ["model", "ticker", "shift_minutes", "status", "original_fill", "shifted_fill"],
            dropna=False,
        ).agg(rows=("state_i", "size"), mean_net_difference=("net_difference", "mean"),
              median_net_difference=("net_difference", "median")).reset_index().assign(split=split))
    cohorts = pd.DataFrame(rows)
    calibration_frame = pd.DataFrame(calibration)
    path_frame = pd.concat(paths, ignore_index=True)
    signal_frame = pd.concat(signals, ignore_index=True).groupby(
        ["split", "model", "ticker"], as_index=False
    ).sum(numeric_only=True).drop(columns="date", errors="ignore")
    for field in (
        "net_positive", "dp_advantage_positive", "net_positive_dp_nonpositive",
        "prediction_positive", "positive_net_rejected_by_score",
    ):
        signal_frame[field + "_fraction"] = signal_frame[field] / signal_frame.actions
    destination.parent.mkdir(parents=True, exist_ok=True)
    cohorts.to_csv(destination.with_name(destination.stem + "_cohorts.csv"), index=False)
    signal_frame.to_csv(destination.with_name(destination.stem + "_signals.csv"), index=False)
    calibration_frame.to_csv(destination.with_name(destination.stem + "_calibration.csv"), index=False)
    pd.concat(timing, ignore_index=True).to_csv(
        destination.with_name(destination.stem + "_timing.csv"), index=False
    )
    lines = [
        "# Diagnóstico modelo–oracle: decisiones y límites", "",
        "Comparación descriptiva de dos modelos congelados, sin nuevos fits: control net0 "
        "y net+episodios0. Validación comprende los 741 ticker-días completos de 2025; "
        + ("TRAIN queda pendiente en este informe parcial. La muestra prevista contiene " if phase == "validation" else "TRAIN contiene ")
        + "96 ticker-días elegidos por hash antes de inferir. TRAIN fue "
        "expuesto parcialmente durante ajuste; VAL está fuera del ajuste pero sigue "
        "siendo desarrollo observado. No se ha seleccionado una corrección con este informe.", "",
        "El oracle maximiza el futuro realizado. Sus beneficios, decisiones y valores "
        "de continuación son una referencia con información privilegiada; no acreditan "
        "una expectativa causal alcanzable. La discrepancia no identifica por sí sola "
        "un fallo técnico o una relación de mercado aprendible.", "",
        "## Trayectorias ejecutadas", "",
        "| Periodo | Modelo | Ticker | Trayectoria | Trades | Días con trade/observados | Neto base USD |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for row in path_frame.itertuples():
        lines.append(
            f"| {row.split} | {row.model} | {row.ticker} | {row.policy} | "
            f"{row.trades} | {row.traded_days}/{row.available_days} | {row.net_base:.2f} |"
        )
    lines += [
        "", "## Mismo estado y mismas acciones ofrecidas", "",
        "Los porcentajes de acuerdo usan sólo estados en que ambos selectores eligen "
        "una acción; TRADE indica decisión, no necesariamente fill. Las cohortes "
        "model_free y oracle_free se calculan por separado. En oracle_free, la decisión "
        "del modelo puede ser una comparación hipotética mientras mantiene una posición.", "",
        "| Periodo | Modelo | Ticker | Cohorte | Estados ambos TRADE | Mismo lado | Mismo contrato | Mismo target | Rango mediano oracle por score |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in cohorts.itertuples():
        lines.append(
            f"| {row.split} | {row.model} | {row.ticker} | {row.cohort} | "
            f"{row.both_trade_states} | {row.same_direction_fraction:.1%} | "
            f"{row.same_contract_fraction:.1%} | {row.same_target_fraction:.1%} | "
            f"{row.oracle_rank_median:.1f} |"
        )
    lines += [
        "", "## Scores y operaciones realmente ejecutadas", "",
        "Sólo trades con free y filled en su propia trayectoria. Los scores son "
        "estimaciones de neto individual USD; su suma no es una garantía de retorno. "
        "En oracle se muestran barreras y duración de su trayectoria realizada, "
        "sin atribuirle una predicción causal. Ratios con distancia de stop cero "
        "quedan indefinidos y contados en el CSV, no rellenados. Target/stop es "
        "un ratio geométrico entre centros de niveles respecto a spot; no equivale "
        "al ratio de beneficio/riesgo monetario de la opción.", "",
        "| Periodo | Modelo | Ticker | Trayectoria | Score medio USD | Neto medio USD | Score suma USD | Neto suma USD | Target/stop mediano | Hold mediano |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in calibration_frame.itertuples():
        score_mean = f"{row.mean_score_usd:.2f}" if pd.notna(row.mean_score_usd) else "NA"
        score_sum = f"{row.sum_score_usd:.2f}" if pd.notna(row.sum_score_usd) else "NA"
        lines.append(
            f"| {row.split} | {row.model} | {row.ticker} | {row.policy} | "
            f"{score_mean} | {row.mean_net_usd:.2f} | {score_sum} | {row.sum_net_usd:.2f} | "
            f"{row.target_stop_ratio_median:.3f} | {row.hold_minutes_median:.1f} |"
        )
    lines += [
        "", "## Interpretación de las diferencias", "",
        "Las tablas decision_categories.csv separan WAIT, entradas y cambios de acción. "
        "Para cada día se verificó que la suma de regret V−Q en los estados libres "
        "del modelo coincide con oracle neto menos modelo neto. Su descomposición "
        "inmediata y de continuación evita atribuir todo a la dirección del trade. "
        "El término de continuación sigue usando el futuro privilegiado del oracle.", "",
        "Los estados oracle bloqueados por una posición del modelo se cuentan, pero "
        "sus oportunidades superpuestas no se suman como beneficio recuperable. "
        "Las comparaciones ±1/2/5 minutos requieren contrato, target, stop y banda "
        "idénticos. Las filas no comparables se mantienen; se separan estados de fill. "
        "Estas variaciones temporales son hindsight, no políticas evaluadas o mejoras seleccionadas.", "",
        "Los CSV adjuntos conservan distancias target/stop en unidades IB, delta, "
        "duración posterior y fracciones de labels/predicciones positivas. Los primeros "
        "ejemplos cronológicos por categoría se eligieron por fecha, nunca por beneficio. "
        "Los inputs causales anteriores a la entrada pueden describir una acción; "
        "no convierten la elección retrospectiva del oracle en una justificación causal.", "",
        "## Integridad", "",
        f"Identidad SHA256: `{digest(root / 'identity.json')}`.",
        (f"Summary final SHA256: `{digest(root / 'summary.json')}`." if (root / "summary.json").exists()
         else "El cierre global todavía no está disponible; este informe verifica los checkpoints diarios del alcance indicado."),
        "Se verificaron los hashes de todos los outputs diarios utilizados por este informe. "
        "El productor verificó alineación de IDs, trayectorias oracle, ausencia de regret "
        "negativo material y descomposición/telescoping por día. Esto no sustituye una "
        "auditoría independiente completa del diagnóstico ni prueba paridad histórica/live.", "",
        "El primer intento preservó741díasVAL completos y falló sólo al serializar dos "
        "flags booleanos del agregado temporal. La continuación revisada normalizó "
        "únicamente su representación nullable, conservando valores, filas, cálculos "
        "y productor original. El registro está en technical_repairs/timing_nullable_boolean_v1.", "",
    ]
    destination.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--phase", choices=("all", "validation"), default="all")
    args = parser.parse_args()
    render(args.root.resolve(), args.destination.resolve(), args.phase)
