# Cross-venue post-V4 — diagnóstico cash-only

**Fecha:** 2026-07-22 Europe/Madrid. Exploración post-outcome limitada a los
eventos ya abiertos 2023–2025. No se leyó ninguna feature, open10:36/13:36,
label u outcome 2026.

## Motivo

V4 pasó development 2025, pero el gate vintage 2026 falló por cinco nuevas
discrepancias Greek/IV que no pueden repararse ni intersectarse. Se evaluó si
una familia estrictamente underlying/cash hasta 10:35 podía conservar el edge
sin consumir Greek/IV. Mapping: QQQ←QQQ, SPY←SPY y SPXW←SPY.

Todos los candidatos usaron coste1bp, entry10:36→exit13:36, hold180, una
operación por ticker/día y los folds causales originales: train2023→H1-2024,
train2023+H1→H2-2024 y train2023+2024→2025. No hubo grid de thresholds,
abstención, exclusión de fechas ni lectura 2026.

## Resultados principales

PF anual por QQQ/SPXW/SPY:

| Modelo | 2024 | 2025 |
| --- | --- | --- |
| Logistic, seis resúmenes cash del sensor | 0,900 / 0,983 / 0,989 | 1,017 / 0,952 / 0,955 |
| Logistic, sensor cash + spot5m | 0,896 / 0,983 / 0,989 | 1,017 / 0,952 / 0,955 |
| Logistic, QQQ+SPY cross-cash + spot5m | 0,914 / 0,981 / 0,989 | 0,931 / 0,983 / 0,991 |
| Logistic, 18 cash + spot5m | 0,988 / 0,936 / 1,042 | 0,881 / 0,978 / 1,023 |
| HistGradientBoosting shallow, sensor cash | 1,012 / 0,915 / 0,914 | 0,960 / 1,100 / 1,102 |
| RandomForest shallow, sensor cash | 0,888 / 1,085 / 1,095 | 0,914 / 0,882 / 0,894 |
| Logistic pooled, secuencia cruda de 35 retornos1m | 1,169 / 0,903 / 0,916 | 0,985 / 1,480 / 1,483 |
| Logistic separado por sensor, 35 retornos1m | 1,023 / 0,868 / 0,874 | 0,992 / 1,398 / 1,397 |

La secuencia cruda encuentra un edge grande para SPY/SPXW en 2025, pero pierde
en ambos durante 2024. QQQ hace lo contrario o queda neutral. Ningún candidato
cumple PF>1, WR>45%, neto>0 y min13 en los seis bloques ticker-año; ninguno se
acerca a PF>1,20 y meses positivos completos en ambos años.

## Decisión

`CLOSED_NO_STABLE_CASH_ONLY_EDGE`. No se crea V5, no se selecciona por ticker o
año, no se invierte post hoc y no se abre 2026. El edge V4 depende de información
option-surface que el contrato de claves 2026 no permite materializar. Un camino
posterior necesita una fuente predeclarada distinta y causal; no puede relajar
la whitelist Greek∩IV ni rescatar solo el bloque SPY/SPXW 2025.
