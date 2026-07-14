# EXISTING_DATA_EXECUTABLE_UTILITY_V1 — informe económico final

## Veredicto

La unión causal de datos existentes no produjo una policy ejecutable. E1
abstuvo en los 144 ticker-month-model cells: ningún par de percentiles pasó PF,
WR, frecuencia, PnL y hold en los tres meses inner. E0 encontró cuatro cells
con configuración inner elegible, pero solo uno pasó el gate en outer. No hay
stress ni apertura de 2026 porque el contrato base falló.

`NO_EDGE_IN_EXISTING_DATA`

## Benchmark ask-to-bid reproducido

La reproducción de las trades publicadas fue exacta hasta `7,1e-15`.

| Ticker | Trades | WR | PF | PnL (R) | Min/mes | Meses + | Hold | Max DD (R) | CALL/PUT | Abstención |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: |
| QQQ | 94 | 44,68% | 0,983707 | -0,492 | 15 | 40% | 30–180m | 6,550 | 27,66%/72,34% | 97,37% |
| SPXW | 107 | 42,99% | 0,831520 | -5,816 | 10 | 40% | 30–180m | 9,656 | 22,43%/77,57% | 97,47% |
| SPY | 123 | 43,90% | 0,919499 | -2,979 | 19 | 40% | 30–180m | 6,696 | 17,07%/82,93% | 97,01% |

El benchmark publicado usaba SPY cap=2. El replay diagnóstico con el contrato
vigente cap=1 deja SPY en 93 trades, WR 45,16%, PF 0,971936, PnL -0,773R,
drawdown 4,470R y mínimo mensual 14. No se ocultó esta discrepancia.

Las 15 métricas ticker-month están en
`existing_data_edge_sprint_v1_benchmark_oracle/benchmark_monthly.csv`; las 324
trades reproducidas están en `benchmark_trades_reproduced.csv`.

## Descomposición oracle, solo diagnóstico 2023

| Estrategia | PF SPXW | PF QQQ | PF SPY | PnL pooled (R) |
| --- | ---: | ---: | ---: | ---: |
| Oportunidad causal + lado causal | 0,828 | 0,794 | 0,862 | -67,615 |
| Oportunidad causal + lado oracle | 5,838 | 9,811 | 8,315 | +505,938 |
| Oportunidad oracle + lado causal | ∞ | ∞ | ∞ | +1.091,415 |
| Oportunidad oracle + lado oracle | ∞ | ∞ | ∞ | +1.488,598 |

Always CALL, always PUT y random seed fijo perdieron en los tres tickers.
Headroom pooled: +573,553R por lado, +1.159,030R por oportunidad y +1.556,214R
con ambos oracles. El upper bound de scheduler drag fue +9.898,564R. Execution
drag queda `UNAVAILABLE_FROM_EXISTING_LABELS`: no existe un payoff midpoint/
no-spread emparejado y no se fabricó uno. Ningún oracle se usó para seleccionar
features, modelos o thresholds.

## Inventario causal y allowlists

| Bloque | Clasificación | Decisión |
| --- | --- | --- |
| Pairwise base E0 | `EXACT_JOIN_AVAILABLE` | 30 campos completos |
| Pairwise physics/context current-time | `EXACT_JOIN_AVAILABLE` | bloque completo |
| Legacy live feature surface | `EXACT_JOIN_AVAILABLE` | bloque completo; null real en 8.695 filas iniciales |
| Wall-state GEX/DEX/DGEX | `EXACT_JOIN_AVAILABLE` | bloque completo; un flag de geometría |
| H-IBQDYN1 F1 | `NOT_APPLICABLE_BY_CAUSAL_GEOMETRY` | 16.926 keys exactas; un flag de geometría |
| H-FLOW1 | `UNSAFE_JOIN` | omitido; one-to-many sin wall identity |
| H-IVSURF1 | `UNSAFE_JOIN` | omitido; one-to-many sin wall identity |
| H-QSIZE1R1 | `UNSAFE_JOIN` | omitido; one-to-many sin wall identity |
| H-QDYN1 | `UNSAFE_JOIN` | omitido; data gate rechazada |
| H-GREEK2WALL | `SOURCE_MISSING` | omitido; entitlement ausente |
| Option path summaries | `EXACT_JOIN_AVAILABLE` | target/diagnóstico, nunca alpha |

E0 tiene 30 nombres ordenados, SHA
`b68b6c2e17b333597281a7d7fa27237b1f1e2640deb8952867d25eced26cbe38`.
E1 tiene 527, SHA
`e15469c0d1dce8176afd5c7fd48af4c477f830b4fc58651fb982f89fb8986abc`.
Los nombres completos están en el manifest frozen y
`join_feature_inventory_v1.json`. La vista outcome-free preservó 97.625/97.625
keys, SHA `52bac061216dd8aac7423449c442577882484aad0c4220bddaabc14544faad36`.
No hubo as-of, nearest-strike, floor-time, zero-fill ni nueva fuente.

Dos filas SPXW 2022-02-22 tienen PUT target ausente. Permanecieron en el
universo, no se rellenaron y solo se omitieron del head PUT durante training.
Todos los inner/outer tuvieron ambos lados ejecutables.

## Modelos, folds y policy

Primario: hurdle LightGBM por lado con `P(return>0)`, gain condicional y loss
absoluta condicional; utilidad `p*gain-(1-p)*loss`. Alternativo: regresión Huber
directa e independiente de retorno completo CALL/PUT. Ambos usaron los mismos
300 árboles Pairwise, seeds deterministas, imputación train-only y ningún
tuning. Specs SHA:

- hurdle: `f5593225ef09e0f53b9b2de587fd01ae5d5378ace6d78f3185b407bea4f76796`;
- Huber: `528a02bc36fb1a14aa60efe052095a52a23cd60ed56002d2007e8de51ef7de8f`.

Cada outer mensual 2024-01..2025-12 entrenó con toda la historia anterior a
los tres inner meses inmediatos. Los 42 pares utility percentile
50/60/70/80/85/90/95 × margin 0/10/20/30/40/50 se calcularon con predictions
de train. Un par tenía que pasar PF>=1,30, WR>=50%, trades>=18, PnL>0 y hold
>=30m en cada inner. Cero pares implica `ABSTAIN_OUTER`.

La auditoría confirmó 288 folds, 12.096 filas inner-grid, orden cronológico,
ranking congelado, payoff del lado ask-to-bid, caps, cooldown, no-overlap y
recomputación de las 288 métricas outer.

## Thresholds que llegaron a outer

Solo E0 tuvo un grid inner elegible.

| Outer | Ticker | Modelo | Utility pct/value | Margin pct/value | Grids pass |
| --- | --- | --- | --- | --- | ---: |
| 2024-03 | SPXW | hurdle | 85 / 0,332648 | 30 / 0,181083 | 10 |
| 2024-09 | QQQ | hurdle | 60 / 0,137315 | 20 / 0,131362 | 4 |
| 2025-02 | SPY | hurdle | 50 / 0,071848 | 20 / 0,113740 | 6 |
| 2025-02 | SPY | Huber | 50 / 0,038166 | 20 / 0,108054 | 3 |

E1 tuvo cero passing grids en hurdle y Huber en los 72 ticker-month folds de
cada modelo. Las 288 decisiones y valores exactos están en
`fold_selections.csv`; todas las alternativas inner están en `inner_grid.csv`.

## Resultados outer 2024–2025

| Arm/modelo | Trades | WR | PF | PnL (R) | Cells trade/72 | Cells gate pass | Min trades/mes | Meses + | Max DD | CALL/PUT | Abstención | Top-5 trades/días |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| E0 hurdle | 68 | 54,41% | 1,464809 | +8,342 | 3 | 1 | 0 | 4,17% | 3,381 | 54,41%/45,59% | 99,19% | 32,55%/35,82% |
| E0 Huber | 19 | 31,58% | 0,589376 | -3,156 | 1 | 0 | 0 | 0% | 3,466 | 21,05%/78,95% | 99,52% | 92,86%/92,86% |
| E1 hurdle | 0 | 0% | 0 | 0 | 0 | 0 | 0 | 0% | 0 | — | 100% | 0%/0% |
| E1 Huber | 0 | 0% | 0 | 0 | 0 | 0 | 0 | 0% | 0 | — | 100% | 0%/0% |

Los únicos cuatro cells no-abstain fueron:

| Outer | Ticker | Arm/modelo | Trades | WR | PF | PnL | Hold | Gate |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 2024-03 | SPXW | E0 hurdle | 17 | 58,82% | 1,404104 | +1,761R | 30–150m | FAIL trades |
| 2024-09 | QQQ | E0 hurdle | 33 | 57,58% | 1,516428 | +4,080R | 30–158m | PASS |
| 2025-02 | SPY | E0 hurdle | 18 | 44,44% | 1,439609 | +2,501R | 30–180m | FAIL WR |
| 2025-02 | SPY | E0 Huber | 19 | 31,58% | 0,589376 | -3,156R | 30–180m | FAIL WR/PF/PnL |

Los otros 284 cells son `ABSTAIN_OUTER`, con trades=0, PF=0, WR=0 y PnL=0.
Por tanto el worst-month PF es 0, worst-month PnL es -3,156R para E0 Huber y
0R para los demás por abstención; el mínimo mensual es 0 en los cuatro
portfolios. Solo QQQ 2024-09/E0 hurdle pasó todas las gates, insuficiente para
una policy de tres tickers y 24 meses.

Las 288 filas mensuales completas están en `monthly_metrics.csv`. Las 87 trades
outer, con timestamp, lado, utilidad, retorno, hold y thresholds, están en
`outer_trades.csv`. No se suprimió ningún mes fallido.

## Stress, 2026 y cierre

El stress 5%/10% de spread, exit 5%/10% y tick adicional no estaba autorizado:
ninguna policy E1 pasó el contrato base. Ejecutarlo habría sido un rescate
posterior. Enero-mayo 2026 no se abrió, junio 2026 sigue sellado y producción no
cambió.

La evidencia disponible apunta a que hace falta información externa realmente
nueva, no otra transformación del mismo dataset: aggressor-side trades directos,
depth/order-book completo, order flow ES/NQ, higher Greeks directos con licencia
Professional o proxies de inventory dealer recolectados prospectivamente.

`NO_EDGE_IN_EXISTING_DATA`
