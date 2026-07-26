# CROSS_VENUE_CALENDAR_RR_LEADER_V4R2 — fallo económico outer 2026

Fecha: 2026-07-26. Autoridad terminal de la familia V4/V4R1/V4R2.

## Ejecución causal

El runner se congeló y versionó antes de outcomes en `e826eb1e`, con modelo
logistic final fit sobre 2.217 filas 2023–2025, 394 eventos/predicciones y
manifest SHA
`f90dbcf6bb42610b32b9d05508a36b052f1c2730d7743ff48215ff2368b345e6`.
El outer abrió una sola vez los opens 10:36/13:36 de esos eventos, sin refit,
filtro, cambio de threshold, selección por mes/ticker ni nueva exclusión.

Status: `FAILED_OUTER_2026_NOT_PROMOTABLE`.

El auditor independiente terminó
`PASS_INDEPENDENT_V4R2_OUTER_2026_AUDIT`: rehasheó 394 fuentes con mismatch0,
refitteó exactamente el modelo, reprodujo el vector de predicciones, ledger,
costes, métricas y gates. Evaluation summary SHA
`8de7e8865b57d0ed36fd7a065bb8b87a9dac7e02d0a0db2d7c051e4f223f12b2`.

## Enero–junio cerrado, coste 1 bp

| Ticker | Trades | WR | PF | Neto bps | Mín/mes | Meses positivos |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 118 | 52,542% | 0,969729 | -86,880 | 18 | 2/6 |
| SPXW | 119 | 50,420% | 0,950957 | -97,917 | 18 | 2/6 |
| SPY | 119 | 49,580% | 0,955718 | -87,839 | 18 | 2/6 |

La frecuencia y WR agregado pasan, pero PF, neto y seis meses positivos fallan
en los tres tickers.

## Junio cerrado y julio MTD

Junio fue positivo en los tres, pero no cumple el gate completo:

| Ticker | Trades | WR | PF | Neto bps |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 20 | 55,000% | 1,155180 | +102,173 |
| SPXW | 21 | 47,619% | 1,102093 | +41,479 |
| SPY | 21 | 52,381% | 1,376810 | +134,489 |

Julio MTD hasta el 24:

| Ticker | Trades | WR | PF | Neto bps |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 12 | 66,667% | 3,453066 | +341,973 |
| SPXW | 13 | 38,462% | 0,807139 | -39,351 |
| SPY | 13 | 30,769% | 0,496072 | -123,162 |

QQQ julio tiene además solo 12 eventos por la exclusión outcome-free y no es
un mes completo. SPXW/SPY son negativos, por lo que el shadow July gate falla.

## Consecuencia

`advance_to_physical_payoff=false`. No se valida ask→bid, no-overlap,
hold30–180m ni `reject_while_open`; no se prepara despliegue, retraining, VPS,
paper intents, live ni systemd.

V4/V4R1/V4R2 queda cerrada e inmutable. 2026 ya es outcome visto para cualquier
familia posterior y no puede reutilizarse como outer promocional. Una policy
nueva necesitaría una hipótesis/fuente predeclarada y un periodo futuro aún no
visto para demostrar promoción; no se puede obtener causalmente retuneando
junio/julio después de este resultado.
