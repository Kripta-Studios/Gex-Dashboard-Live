# Registro de familias económicas causales

Estado autoritativo del sprint persistente. Una familia cerrada no puede
reabrirse, retunearse ni renombrarse sobre los mismos outcomes. El outer V4R2
abrió 2026 una sola vez y ese periodo queda consumido; producción permanece
intacta.

Estados permitidos: `QUEUED`, `ACTIVE`, `FAILED_CAUSALITY`,
`FAILED_FREQUENCY`, `FAILED_ECONOMIC`, `BLOCKED_DATA`, `PROMOTABLE`, `CLOSED`.

| Familia | Mecanismo | Estado | Evidencia / razón |
| --- | --- | --- | --- |
| Baseline executable nested y objetivos return/win | controles y objetivos genéricos | `FAILED_ECONOMIC` | PF/WR mensuales no pasan |
| Early cadence/directional/regime | frecuencia, momentum y gates de régimen | `FAILED_ECONOMIC` | mejoras aisladas, sin estabilidad mensual |
| Pairwise P1 y magnitude/physics variants | lado CALL/PUT por diferencias de cadena | `FAILED_ECONOMIC` | lado cercano a azar; payoff falla |
| Wall interaction executable V1/V1R1 | magnet/rejection/acceptance en walls e IB/Fib | `FAILED_ECONOMIC` | señal parcial sin frecuencia/estabilidad común |
| H-FLOW1 | flow firmado cerca de wall | `CLOSED` | physical gate negativo; sin payoff |
| H-IVSURF1 | deformación de superficie IV | `CLOSED` | physical gate negativo; sin payoff |
| H-QSIZE1R1 | presión snapshot NBBO size | `CLOSED` | physical gate negativo; sin payoff |
| H-QDYN1R1R1 | dinámica tick en Greek walls | `FAILED_CAUSALITY` | data gate de distinctness rechazado |
| H-IBQDYN1 | dinámica tick en IB/Fibonacci | `CLOSED` | physical gate cerrado; sin replay económico |
| H-GREEK2WALL direct | higher Greeks nativos | `BLOCKED_DATA` | licencia Professional ausente |
| EXISTING_DATA_EXECUTABLE_UTILITY_V1 | unión causal existente, hurdle/Huber | `FAILED_ECONOMIC` | E1 144/144 abstain; E0 solo 3/72 cells operan |
| CROSS_MARKET_TRANSMISSION_V1 | transmisión beta-neutral y lead/lag exacta | `FAILED_CAUSALITY` | master contiene paths post-cierre en medias jornadas; build abortó antes de outcomes |
| CROSS_MARKET_TRANSMISSION_V1R1 | misma hipótesis, exclusión calendar-only de medias jornadas no certificables | `BLOCKED_DATA` | lead/lag indefinido en sesión normal; no epsilon/remoción post-gate |
| H-TPOVALUE1 | migración de valor TPO/POC/VAH/VAL | `FAILED_ECONOMIC` | primera celda X1 SPXW 202304: 0/42 grids inner pasan; PF pooled del near-miss 0,922 y PnL -1,831R |
| KING-GEX-SLOPE1 | signo net-GEX y pendiente 45m alineada como régimen momentum/reversión | `FAILED_ECONOMIC` | K1 PF 0,804/WR 42,22% y 2/36 celdas; K0 también pierde |
| KING-GEX-EXIT1 | gestión fija de stops/trails/horizontes | `FAILED_ECONOMIC` | 0/32 policies elegibles; ninguna alcanza PF 1,0 |
| KING-GEX-MANAGE30-V1 | selección causal de gestión a +30m | `FAILED_ECONOMIC` | M0/M1 PF 0,905/0,901; outer cerrado |
| EVENT_OPTION_EXECQUOTE_NESTED_COMPACT_V1 | selector compacto long-option 0DTE ask-to-bid | `FAILED_ECONOMIC` | PF 0,794–0,804 y WR 35,5–39,7% por ticker |
| DIRECTIONAL_GLOBEX_CROSS_ASSET_V1 y adaptaciones | dirección cash con siete continuos Globex | `FAILED_ECONOMIC` | near-miss 2025 revierte a PF <0,90 en 2026; adaptaciones no pasan desarrollo |
| Payoffs alternativos long-vol/short-premium/IB | payoff no direccional o reglas IB/Fib | `CLOSED` | long-vol e IB pierden; short premium falla gates de ejecución exacta |
| CROSS_SESSION_RELATIVE_VALUE_V1 | reversión QQQ-SPY de divergencia cross-session con SPXW como ancla | `FAILED_ECONOMIC` | 496 trades, PF 0,627/WR 41,53%/-2.349 bps; 2/24 meses PASS |
| OPENING_RELATIVE_MOMENTUM_V1 | continuación QQQ-SPY del impulso relativo cash 09:30–10:34 | `FAILED_ECONOMIC` | 497 trades, PF 0,831/WR 50,91%/-927,7 bps; 4/24 meses PASS |
| OPTION_PARITY_PRESSURE_V1 | cambio 5m del synthetic forward CALL/PUT 0DTE frente al spot | `FAILED_ECONOMIC` | 730 trades, PF0,875/WR48,63%/-1.689bps; 10/36 celdas, outer cerrado |
| EXACT_EXPIRY_OI_DELTA_V1 | cambio OI del mismo contrato antes de expiry | `FAILED_FREQUENCY` | 156 pares/36 meses, mínimo4 eventos/mes; sin outcomes |
| CALENDAR_RISK_REVERSAL_PRESSURE_V1 | Δ5m del RR25 0DTE menos next-expiry | `FAILED_ECONOMIC` | partial edge: pooled PF1,058/+730bps; QQQ/SPY>1, SPXW0,912; 12/36 cells |
| CROSS_VENUE_CALENDAR_RR_LEADER_V1/V3 | mapping QQQ←QQQ, SPY←SPY, SPXW←SPY con signo fijo/mensual | `FAILED_ECONOMIC` | V1 outer2024 PF0,867/0,699/0,693; V3 outer2025 PF0,655/1,036/1,040; 2026 cerrado |
| CROSS_VENUE_CALENDAR_RR_LEADER_V4/V4R1/V4R2 | logistic pooled final fit 2023–2025 con retries y cuatro exclusiones outcome-free | `FAILED_ECONOMIC` | outer2026 H1 PF0,970/0,951/0,956, neto negativo y 2/6 meses positivos; julio MTD solo QQQ positivo; auditor independiente PASS |
| CROSS_VENUE post-V4 cash-only | summaries/spot/cross-cash/shallow trees/raw35x1m | `FAILED_ECONOMIC` | ningún candidato pasa los seis bloques ticker-año 2024–2025; no V5 ni acceso 2026 |
| CROSS_VENUE_OPRA_TRADE_QUOTE_FLOW_V5 | desequilibrio de prints OPRA 0DTE ejecutados frente al NBBO estrictamente anterior | `BLOCKED_DATA` | source gate: 1.364/1.504, 140 invalid/duplicate, enero2024=0/21 ambos; auditor PASS rehash/reparse1.364, mismatch0; sin features/outcomes |
| EXTERNAL_OPRA_SOURCE_INTAKE | admisión de tape/NBBO OPRA histórico-live antes de cualquier familia económica | `BLOCKED_DATA` | Massive Advanced es candidato documental; falta credencial y shadow live↔REST de cinco sesiones; divergencia de timestamps/correcciones falla cerrado; no V8/modelo |
| CROSS_VENUE_CALENDAR_RR_LEADER_V6 | continuación no lineal depth2 sobre las 29 features V4 selladas | `CLOSED` | cerrada sin implementación, predicción ni métrica al priorizar el V4 inmutable |
| CROSS_VENUE_CALENDAR_RR_LEADER_V7 | logistic pooled rolling12 con refit al inicio de mes | `FAILED_ECONOMIC` | H1 PF0,812/1,080/1,032 y 1/2/3 meses positivos; junio falla SPXW/SPY y julio MTD falla SPXW/SPY; auditor PASS |

No hay una policy promocionable ni familia cross-venue activa. V7 falla incluso
al incorporar 2026 pasado en walk-forward mensual y no restaura virginidad a
2026. Payoff físico y producción/live/systemd permanecen cerrados. Autoridades
terminales: `CROSS_VENUE_CALENDAR_RR_LEADER_V4R2_OUTER_2026_FAILURE.md` y
`CROSS_VENUE_CALENDAR_RR_LEADER_V7_ROLLING12_MONTHLY_LOGISTIC_FAILURE.md`.
El inventario post-V7 `CAUSAL_SOURCE_POST_V7_INVENTORY_20260726.md` confirma
dependencia externa; no se crea V8 con fuentes/outcomes ya cerrados.
