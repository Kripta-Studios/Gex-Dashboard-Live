# CROSS_VENUE_CALENDAR_RR_LEADER_V7 rolling12 — fallo development

**Fecha:** 2026-07-26 Europe/Madrid. Predeclaración publicada en `6ee8fc2f`;
evaluator y auditor publicados en `d462f4d7` antes de la única ejecución.

## Resultado

Estado: `FAILED_DEVELOPMENT_NOT_STABLE`. Se refittearon siete logistic pooled,
uno al comienzo de cada mes, usando exclusivamente los doce meses completos
anteriores. Febrero–julio incorporan outcomes 2026 pasados sin usar ninguna fila
del mes test o posterior. Se conservaron los 394 eventos V4R2, mapping,
features, threshold, clocks y coste1bp.

H1 enero–junio:

| Ticker | Trades | WR | PF | Neto bps | Mínimo/mes | Meses positivos | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| QQQ | 118 | 50,847% | 0,812462 | -585,329 | 18 | 1/6 | FAIL |
| SPXW | 119 | 51,261% | 1,079783 | +149,347 | 18 | 2/6 | FAIL |
| SPY | 119 | 49,580% | 1,031988 | +61,076 | 18 | 3/6 | FAIL |

Junio cerrado:

| Ticker | Trades | WR | PF | Neto bps |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 20 | 65,000% | 2,094680 | +500,526 |
| SPXW | 21 | 42,857% | 0,967857 | -13,983 |
| SPY | 21 | 42,857% | 1,075389 | +30,970 |

Julio MTD hasta el 24:

| Ticker | Trades | WR | PF | Neto bps | Health |
| --- | ---: | ---: | ---: | ---: | --- |
| QQQ | 12 | 66,667% | 1,824663 | +181,239 | PASS económico; frecuencia MTD12 |
| SPXW | 13 | 46,154% | 0,638485 | -80,915 | FAIL |
| SPY | 13 | 46,154% | 0,634536 | -80,860 | FAIL |

## Comparación con V4R2 fijo

En H1, rolling12 mejora SPXW/SPY desde -97,917/-87,839bps a
+149,347/+61,076bps, pero PF permanece muy por debajo de 1,20 y no arregla la
estabilidad mensual. QQQ empeora desde -86,880 a -585,329bps. En todos los
eventos disponibles, V7 cambia 49/42/43 orientaciones QQQ/SPXW/SPY; la accuracy
solo cambia 53,846→53,077%, 50,000→51,515% y 50,758→51,515%. El target
binario acierta algo más en SPXW/SPY, pero no controla la magnitud de los
errores, que domina PF y PnL.

## Auditoría

`PASS_INDEPENDENT_V7_DEVELOPMENT_AUDIT`: siete modelos refitteados, siete
vectores de probabilidad exactos, 394 filas de ledger, input/output mismatch0 y
gates reproducidos. SHA del evaluation summary:
`260e05df141fa4d891c697f51ffac3517a018bb0532f0d05a3e3deebdb1894fe`.

## Decisión

V7 queda `FAILED_ECONOMIC`. Reentrenar mensualmente con 2026 pasado no produce
una policy rentable en todos los tickers/meses. No se prueban retrospectivamente
otras ventanas, targets, thresholds, horas o selecciones sobre el mismo 2026.

`promotable=false`, `physical_option_payoff_opened=false` y
`production_modified=false`. Para una siguiente prueba promocionable hace falta
un mecanismo predeclarado distinto y un periodo futuro intacto; 2026 no puede
reciclarse como outer.
