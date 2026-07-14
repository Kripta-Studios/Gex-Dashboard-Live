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
| H-TPOVALUE1 | migración de valor TPO/POC/VAH/VAL | `ACTIVE` | predeclarada; desarrollo 2022-2023 pendiente |

Solo `H-TPOVALUE1` está autorizada para ejecución en este checkpoint. Ninguna
fuente nueva ni captura histórica está autorizada.
