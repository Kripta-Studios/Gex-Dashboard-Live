# Registro de familias económicas causales

Estado autoritativo del sprint persistente. Una familia cerrada no puede
reabrirse, retunearse ni renombrarse sobre los mismos outcomes. Junio de 2026
permanece sellado y producción permanece intacta.

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
| KING-GEX-SLOPE1 | pendiente net-GEX/sign flip y tensión de volatilidad inspirada por King Node | `QUEUED` | solo idea; requiere predeclaración outcome-free y fuente histórica causal antes de cualquier outcome |

No hay familia activa tras el cierre H-TPOVALUE1. La única rotación permitida
es auditar outcome-free la factibilidad de `KING-GEX-SLOPE1`; no descargar ni
abrir outcomes hasta predeclarar una definición causal que no copie los defectos
runtime de `live_king_node.py` ni use calibraciones 2026.
