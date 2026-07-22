# CROSS_VENUE_CALENDAR_RR_LEADER_V4 — full-history logistic

**Congelada:** 2026-07-22 Europe/Madrid, después de cerrar y auditar V3 outer
2025, antes de inspeccionar features u outcomes 2026.

## Naturaleza post-outcome

V4 nace después de observar V1 2024, V2/V3 development y V3 outer 2025. Por
tanto, todo 2023–2025 es development contaminado para V4. El primer outer que
podría aportar evidencia nueva es 2026. Esta predeclaración no autoriza abrirlo:
antes deben completarse y versionarse development 2025 reproducible, auditoría
independiente, data gate 2026 outcome-free y manifest frozen 2026.

La exploración ya observada comparó V3, ventanas online de hit/magnitud,
logistic pooled/per-ticker, refit mensual/trimestral, filtro de confianza,
logistic ponderado y ridge de retorno. Es selección de development, no OOS. La
hipótesis elegida es la más simple que pasó la gate incremental 2025 en los tres
tickers sin reducir frecuencia: el mismo logistic pooled V2R1, sin filtros,
reentrenado con 2023+2024 completos.

## Identidad de datos y mapping

- QQQ ← QQQ;
- SPY ← SPY;
- SPXW ← SPY;
- `calendar_rr_pressure` y siete features option-sensor observables 10:30→10:35;
- cash open-only 10:00–10:35, seis métricas por QQQ/SPY y SPXW solo activo para
  target SPXW;
- entry open10:36, exit open13:36, hold180, coste primario1bp y sensibilidad2/3;
- una posición por ticker/día, sin overlap.

Inputs development congelados:

| Input | SHA-256 |
| --- | --- |
| V2R1 development dataset 2023–2024 | `459979c11ad5b7ba1ed44ef3add42142d0eab40982882bc52031982e22778f0b` |
| V3 outer 2025 trades | `a45a6eb4af6010ece49f4dc0b42c0e21f3442765a13578f2874d8e2a8a6e73f5` |
| V3 outer 2025 summary | `99346b5b041b127b35d79a0ba1e0a176335ae5c4057d3518b29b03605ca21dd5` |
| V1R1 feature view 2024–2025 | `fd2953bd9bc918b95079d494663cf7ca2fc9dfe141604b8e8803cc2bf605d268` |
| V1R1 source inventory | `b63ca25185627528b1bc22ad937dcb834dbb4846d03b451aa395a62003d4c56c` |
| V2R1 evaluator | `1bdc768ca4a72d99be1394d18107750abb228024fc56555ebe4d7b13c5c89d2a` |

Los cuatro `Greek∩IV` repairs siguen limitados exactamente a los IDs V1R1 de
2024–2025. No se extiende esa excepción a 2026: cualquier quinta discrepancia o
desigualdad Greek/IV nueva falla cerrado; no hay intersection, nearest, fill ni
revisión current-provider para construir features 2026.

## Modelo V4 fijo

Un solo `Pipeline(SimpleImputer(median), StandardScaler(), LogisticRegression)`
pooled con `penalty=l2`, `C=0.1`, `solver=liblinear`, `max_iter=2000`,
`random_state=0`. Las 29 columnas y su orden son exactamente V2R1:
ocho option-sensor, seis cash QQQ, seis cash SPY, seis cash SPXW y tres one-hot
ticker. Target `direct_win = sign(signal_pressure) * return_10:36→13:36 > 0`.
Predicción >=0,5 conserva el signo; <0,5 lo invierte.

No hay sample weights, regression target, confidence threshold, abstención,
calibración, ticker model, ensembles, window, refit mensual, feature selection,
grid ni tuning. Sensibilidades2/3bps no seleccionan.

## Development reproducible 2025

El evaluator entrena una vez con las 1.482 filas V2R1 2023–2024 y predice los
735 eventos 2025 ya sellados. Revalida todos los inputs y las 738 fuentes cash
tempranas; solo lee 10:00–10:35 para features y reutiliza outcomes 2025 ya
versionados. Debe reportar todos los meses y costes, no hardcodear el resultado.

Gate incremental por ticker: PF>1, WR>45%, neto>0 y >12 trades cada mes. Solo
este gate permite preparar datos 2026 outcome-free. Gate objetivo no se rebaja:
PF>1,20, WR>45%, >12 y PnL positivo en todos los meses. El diagnóstico ya visto
espera PF QQQ/SPXW/SPY 1,204351/1,247945/1,346342 y 7/8/8 meses positivos;
estas cifras deben reproducirse y auditarse, pero no son evidencia OOS.

## Entrenamiento final y outer 2026

Solo tras PASS incremental development auditado y un data gate 2026 sin outcomes,
el freezer final puede entrenar exactamente el mismo modelo con 2.217 filas
2023–2025, congelar scaler/imputer/coeficientes, events y source hashes 2026.
No refit durante 2026. Enero–junio completados constituyen el outer; julio MTD
es shadow y no selecciona. Cada ticker debe alcanzar PF>1,20, WR>45%, >12
trades en cada mes completado y PnL positivo en todos; junio debe ser positivo
y julio MTD seguir positivo para avanzar.

## Opciones y producción

Un PASS cash 2026 no basta para live. Antes se exige payoff de opción ask→bid,
no-overlap, paridad backtest/live y paquete nuevo `production_live_ready`. La
primera integración, si alguna vez se autoriza, sigue paper-only. Durante V4 no
modificar `services/`, `bots/`, `systemd/` ni los paquetes live actuales.
