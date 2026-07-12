# SUMMARY-update — ledger científico compacto

**Corte:** 12 de julio de 2026

**Objetivo:** policy 0DTE causal y live-equivalente para SPXW, QQQ y SPY.

**Gates por ticker:** PF `>=1,3`, WR `>=50%`, `>=18` trades/mes, todos los meses
positivos y cada hold `>=30m`.

**Junio 2026:** sellado. **Producción:** intacta.

Este documento conserva resultados y decisiones. La operación live y los pasos de
reanudación están en `CODEX-HANDOFF.md`; la literatura está resumida en
`SUMMARY-articles.md`.

## 1. Evidencia base

### Dataset causal executable-quote

- ThetaData 0DTE con entrada ask y salida bid.
- Rejilla principal 10:35–14:30/5m; vista early 1m separada ya construida.
- Stop -60%, TP 1000%, trailing 50%/25%, hold 30–180m.
- Cupos/cooldowns y una posición por ticker equivalentes a runtime.
- Dataset wall/pairwise sellado hasta 2025:
  `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`.

Baseline nested causal enero–mayo2026:

| Scope | Trades | WR | PF | PnL R | Min mes | Meses + |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Overall | 324 | 43,83% | 0,909 | -9,287 | 48 | 40% |
| QQQ | 94 | 44,68% | 0,984 | -0,492 | 15 | 40% |
| SPXW | 107 | 42,99% | 0,832 | -5,816 | 10 | 40% |
| SPY | 123 | 43,90% | 0,919 | -2,979 | 19 | 40% |

## 2. Por qué el paquete productivo no es el nuevo baseline científico

El static-union live sigue operativo, pero thresholds/reglas fueron elegidos sobre
enero–junio2026, los mismos meses usados para reportar su rentabilidad. La auditoría
pre-2026 entrenó hasta septiembre y aplicó reglas fijas a oct–dic2025:

| Ticker | Trades | WR | PF | Min mes | Meses + |
| --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | 75 | 41,33% | 1,158 | 21 | 2/3 |
| SPXW | 64 | 43,75% | 1,686 | 19 | 2/3 |
| SPY | 125 | 34,40% | 0,794 | 26 | 0/3 |

El volumen existe; fallan dirección y estabilidad.

## 3. Experimentos de representación cerrados

| Prueba | Resultado | Decisión |
| --- | --- | --- |
| Flat runtime | 481 trades, PF 0,900, -15,094R | Rechazado |
| Modal runtime | 491, PF 0,858, -21,989R | No MJEPA intra/cross-modal |
| Historia 2025 | 495, PF 0,863, -20,174R | Control |
| Historia 2022 | 440, PF 0,764, -31,476R | Mejor OOF, peor economía |
| Portfolio Var-JEPA | 0 configs, incertidumbre-error mediana -0,180 | Cerrado |
| PatchCore | correlación error 10/15; 0/1.470 configs | Drift solamente |
| AdaJEPA shadow | error latente mejora 15/15 y 277/281 días | Downstream requerido |
| AdaJEPA downstream | 0/210 configs, 30 abstain | No live |
| h1→h6 | 0/210; h6 peor MAE/RMSE/dirección | No otros horizontes |
| Spot skip | 0/210 en ambos arms | No más bloques por tanteo |

Conclusión: mejores embeddings no trasladaron edge al payoff.

## 4. Reconstrucción del mecanismo executable

### Objetivo, IB temprano y cadencia

- GBT return abstuvo 15/15; GBT win operó dos folds SPY negativos.
- El PnL dense15 legacy estaba concentrado antes de 10:30, pero usaba IB completo
  09:30–10:30, hasta 30 minutos futuros.
- Vista early causal sin IB: 5m solo SPXW, 39 trades, PF 1,109; QQQ/SPY abstain.
- Cadencia 1m añadió 62.280 filas con paridad exacta. SPXW enero: 20 trades,
  WR 40%, PF 1,220; después drift y abstención. QQQ/SPY 0/5.
- Selector direccional 1m: 60 trades, WR 36,67%, PF 0,976, -0,572R.

Conclusión: más candidatos no arreglan la dirección.

### Gates de régimen

IV skew/spread/abs-return/IB range mejoraron folds aislados. Ejemplo: SPXW febrero
R1, 9 trades, PF 1,452. Ningún arm mantuvo las gates todos los meses. Replay C0 y
thresholds auditados con equivalencia exacta.

## 5. Pairwise opportunity/side

Vista 2022–2025, 97.625 filas, 99 celdas científicas.

- P1 vs C0: balanced-accuracy wins `57/99`, mediana `+0,004`, `p=0,117`;
  Spearman positivo `58/99`, mediana `0,0303`.
- Oracle side no causal: PF `4,55..11,73`, WR `73,5..86,7%`; headroom existe.
- Always CALL/PUT y momentum/contrarian pierden.

Bug corregido: `opt_exit_minutes` era duración, pero se restaba el minuto de
entrada. Tras corregir:

| Arm | Scope | Trades | WR | PF | PnL R |
| --- | --- | ---: | ---: | ---: | ---: |
| C0 V1r1 | SPY | 61 | 45,90% | 0,998 | -0,040 |
| P1 V1r1 | SPY | 23 | 34,78% | 0,427 | -4,930 |

SPXW/QQQ abstienen. Frecuencia inner pasa en 85–97% de configs P1; PF/WR son el
cuello.

Cambios aislados posteriores:

- magnitude-weighted: 48/99 BA wins, PF 0,430;
- physics/context 154 features: 55/99; QQQ PF 0,409, SPY 0,810;
- estas 154 features no incluían distancias a Greek walls ni IB previos.

## 6. Wall interaction executable V1/V1r1

Se unieron las labels ask→bid con `training_data_spx_qqq_spy.parquet`:

- 86.729 filas útiles `202208..202512`;
- join uno-a-uno y spot exactamente igual;
- feature input hash `5f908e11090ea6566e3eadeba0a436ab5d01cf99955d6acc5050eae264fe13b5`;
- sin 2026.

### V1

Regla fija `magnet/rejection/acceptance` con max/min gamma, zero gamma, max/min
DGEX, IB/Fibonacci actual y D1–D5.

| Ticker | Trades | WR | PF | PnL R | Min mes | Meses + |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPXW | 1.564 | 40,54% | 0,865 | -75,366 | 52 | 37,50% |
| QQQ | 903 | 44,41% | 0,832 | -49,816 | 30 | 33,33% |
| SPY | 496 | 44,76% | 0,899 | -15,422 | 17 | 45,83% |

El control de proximidad también pierde: PF `0,872/0,903/0,935`.

### V1r1

La atribución demostró que solo 29–37% de los rejection habían cruzado el nivel.
V1r1 exige pierce real y regreso al lado defendido:

| Ticker | Trades | WR | PF | PnL R | Min mes | Meses + |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPXW | 1.557 | 42,32% | 0,910 | -48,846 | 52 | 29,17% |
| QQQ | 894 | 44,18% | 0,845 | -45,816 | 30 | 33,33% |
| SPY | 496 | 47,58% | 1,008 | +1,118 | 17 | 54,17% |

Diagnóstico, no policy seleccionable:

- acceptance CALL: ~58–63% de acierto spot a 30m en varias muestras, PF opción ~1;
- resistance-rejection PUT: SPY PF 1,536; SPXW/QQQ ~1,09;
- magnet CALL: QQQ PF 2,230/42 trades, SPY PF 1,307/25;
- señal insuficiente para 18 trades mensuales y estabilidad completa.

No retunar subfamilias/horas/direcciones sobre este output.

Commit autoritativo: `b4b22d4`.

## 7. Causa actual

Las 182 features live describen distancia y algunos flags, pero no el estado real
del wall:

- falta DEX por strike y wall CALL/PUT de delta;
- falta magnitud de cada wall;
- falta concentración y diferencia top1/top2;
- falta persistencia/edad/migración;
- se mezclan soporte, resistencia, magnet y acelerador sin medir régimen.

Una ubicación sin fuerza no prueba la hipótesis económica.

## 8. Trabajo activo: wall-state GEX/DEX

Predeclaración:

```text
research_papers/JEPA/WALL_STATE_GEX_DEX_DATASET_PREDECLARATION_V1.md
```

Primitivas implementadas:

```text
neural/jepa/wall_state_features.py
```

Primitivas y builder por sesión ya implementados: `15 passed` en la suite wall.
Se cubren duplicados OI, orden determinista, separación de walls, persistencia
causal, cutoff future/2026, join de OI, selección de preflight y auditoría de
cobertura y entrada CLI directa. El preflight ThetaData real pasó: 144/144 filas,
cero errores, cobertura de eventos 100% en los tres tickers, spot máximo a
0,000572 bps y delta walls materialmente distintos de gamma.

Build completo aprobado: 135.120 × 148, 2.815 sesiones, SHA `94e311e0...df8ef`.
Cobertura de las 95.424 claves executable 100% por ticker y spot máximo
0,000572 bps. Se excluyó QQQ 2023-12-27 por strikes Greeks `.78` frente a OI
entero, sin imputación ni eventos perdidos. Un primer build descubrió y corrigió
uso futuro de quotes `:30` al redondearlos a minuto; ahora solo usa `HH:MM:00`.

Diseño congelado de separabilidad física V1: cuatro walls
CALL/PUT gamma/delta, magnet/rejection/break a 30/60/120/180m, D0 vs S1 vs S2
state+IB, holdouts 2024/2025 y gates fijas sobre 48 celdas por arm.

Resultado ejecutado: REJECTED. 26.090 candidatos, 48/48 celdas válidas. S1 gana
17/48 (mediana ΔAUC -0,00154); S2 gana 22/48 (mediana -0,000077; p=0,567), AP
19/48 y log-loss 17/48. Magnet hit ya es separable por distancia (D0 mediana AUC
0,805), pero rejection/break queda 0,511/0,519/0,516 para D0/S1/S2. Mínimo
mensual resuelto 30m QQQ/SPXW/SPY 6/0/0; 60m 14/4/5. No se autoriza payoff.

Nueva fuente predeclarada, aún no ejecutada: flow-at-touch con bar de opción
completado `[t-1,t)`, sign proxy close-vs-mid, agregación 1/5/15m full-surface y
30 bps alrededor del wall. Feasibility de volumen capturado 96,98–99,58%. F1 debe
superar F0 en 16/24 celdas y mantener >=18 resoluciones mensuales a 30/60m.

Debe producir, solo con snapshot actual:

- CALL/PUT gamma wall;
- CALL/PUT delta wall;
- max/min net GEX, DEX y DGEX;
- strike, distancia, magnitud signed-log, concentración, HHI, effective strikes,
  dominancia y separación;
- same/move/magnitude-change a 5/15/30m y edad causal del wall.

Manifest fuente: `5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88`.
Cutoff físico: `<=20251231`. Build por sesión con hasta 16 workers.

Después del data gate se predeclaran labels físicos del subyacente
`magnet_hit/true_rejection/accepted_break` a 30/60/120/180m. Solo si wall state
supera distance-only en los tres tickers se autoriza un payoff head ask→bid.

## 9. Invariantes

- No outcomes, future highs/lows o labels como features.
- No abrir junio de 2026.
- No modificar paquete productivo/systemd durante research.
- No relajar gates por ticker.
- No seleccionar con el mismo mes reportado como OOS.
- Versionar predeclaración, tests, resultados compactos y handoff con commits
  explícitos; no añadir artefactos untracked ajenos.

## 10. Wall-surface flow V1R1: implementación y bloqueo de procedencia

V1R1 quedó implementado y predeclarado antes de outcomes. Introduce un único
bloque F1 de volumen/count/close-notional quote-relative en ventanas completadas
1/5/15m, comparado con F0 distance/approach/RV/time. La evaluación física sigue
siendo rejection versus accepted break; no se ha conectado option payoff.

La suite relevante pasa `55 passed`. Se corrigieron half-days, cierre RTH de
labels, fechas de fuente, duplicados, alias, episodios, pierce verdadero,
denominadores/missingness y lock exacto de Python/dependencias. Preflight real:
8 × 173, 3/3 sesiones, cero errores.

El censo de 325.753.830 filas Greek descubrió 1.441/2.519 sesiones sin timestamp
nativo. Es una falla de procedencia, no evidencia contra el mecanismo. El data
gate ahora las bloquea. El endpoint nativo de quotes permite backfill falsable y
aporta bid_size/ask_size; se implementó sidecar inmutable con raw/JAR/source
hashes, cobertura 100% de keys históricas y extras auditadas sin incorporación.
No se autoriza label runner hasta congelar dataset+runner manifest.

La auditoría del productor underlying confirmó 1s→floor-minute y un reparador
con `bfill` para filas totalmente nulas. Los ficheros históricos carecen de hash
de productor/contrato fuente; por ello se añadió gate de contenido completo.
Preflight: 0 grids RTH incompletos, OHLC/tick_count válidos y spot máximo
0,000519 bps. La limitación de linaje se conserva, no se oculta.
El audit completo pasó 2.519/2.519; registró tres ceros 09:54–09:56 de SPY
2023-06-05 fuera del primer timestamp consumible 10:19, sin imputar ni excluir.

El backfill terminó con `PASS_NATIVE_TIMESTAMP_BACKFILL`: 1.441 sesiones,
125.557.990 filas, cero missing keys/errores, 500 keys extra, 5.720 crossed y
2.915 revisiones bid/ask en 24 sesiones. Índice SHA
`0abe0ac2f9dcccec4574ee10e4f10ef2904000c80a0cf5fb8f5a90ef333f754a`.

Estado científico: `H-FLOW1 = NATIVE_CLOCK_SEALED_DATA_GATE_PENDING`,
`H-QSIZE1 = AVAILABLE_NOT_TESTED`.
No hay rentabilidad nueva que reportar; 2026 y producción siguen intactos.

Backfill counterexamples: crossed quotes son raw válido pero no-signable; precios
revisados por el proveedor no sustituyen el histórico. QQQ 2024-03-11 conserva
65.500/65.500 keys de clock y solo 77 bid/ask distintos. El builder combina clock
sidecar con bid/ask Greek originales; `timestamp_key_set_exact` y
`stored_bid_ask_exact` quedan separados.
QQQ 2025-08-28 mostró 250 keys nativas extra pero cubrió las 50.750 históricas;
extras se auditan y no amplían el universo F1.

El primer full-gate attempt detectó un bug pre-outcome al aplicar `_truthy` a
escalares CSV aunque su contrato era vectorizado. El fix queda cubierto por un
test de attach real y el gate verifica además booleanos estrictos del seal,
consistencia del JAR, capturas positivas y hashes de raw/session manifests.

El segundo attempt detectó dos defectos pre-outcome. El bridge usaba todo el día
Greek contra un sidecar limitado al research window; se corrigió con grid
programado exacto y test de truncamiento inicial. Después de descontar sus 1.441
errores quedan QQQ/SPY 2022-12-30. QQQ mezcla `underlying_price` de t-1 con quote
de t (máximo 19,688 bps); SPY difiere 0,01 punto. No se autoriza tolerancia,
exclusión ni label runner hasta reconstruir y auditar un spot/wall consistente.

V1R2 predeclara esa reconstrucción sin outcomes. El censo reproducible confirmó
2.518 sesiones/120.864 wall rows, con solo QQQ/SPY 2022-12-30 híbridas y cero
unresolved (census SHA `24d86299...ff832`, commit `5c037ee`).
No se sustituye solo spot: se recapturan S/IV/delta first-order 1s coherentes para
los 671 contratos Greek∩OI positivo (285/386), 48 timestamps exactos cada uno.
Bid/ask debe permanecer idéntico al histórico; cualquier revision bloquea. Los
builders dejan la suite relevante en `76 passed`.

La captura ya selló 671/671 y 32.208 exact rows con cero errores y diferencia
máxima `0.0` en spot/bid/ask. Raw: 671 respuestas/4,013 GiB; index SHA
`7e5475f3...2100a`, provenance condicional. Falta construir/commitear las 96
wall rows y controles causales, luego repetir el full gate.

El builder de bundle ya está implementado: valida todo el sidecar, reconstruye
96 walls y el grid físico completo de 96 controles. El event view contiene solo
47 keys objetivo (27/20; SHA `41dae9ad...5201`), así que el patch/overlay se
restringe a esas 47 y no añade 49 decisiones inexistentes. Pendiente relanzar y
congelar los tres hashes.

Bundle real PASS: 96 walls SHA `69a3d330...487d`, 47 controls SHA
`937aa95e...051e`, manifest `47dffb25...aec5a`; spot parity `0.0`, non-target
changed `0`.
La integración aplica el bundle antes de seleccionar touches y exige los tres
SHA frozen; ninguna key nueva entra al event view.

Frecuencia estructural: 10.078 timestamps first-touch. QQQ máximo 14/9/9 en
202208–10 y SPY <18 en 16/41 meses incluso antes de cooldown/no-overlap; SPXW
min=30. H-FLOW debe ser señal prioritaria con fallback causal o ampliarse mediante
un protocolo nuevo, nunca presentarse solo como policy que cumple 18/mes.

Full V1R2 attempt: 2.519/2.519, cero source errors y todos los gates salvo uno.
QQQ 2022 `role_break_pressure_w1m` posee 6 estados no degenerados, pero el código
pedía 10. Antes de labels se congeló una aclaración objetiva: >=2 estados,
zero<99,5%, missing=0. No se cambian features/candidatos ni se usa PnL; el output
REJECTED se conserva y el relanzamiento usa target nuevo.

V1R2R1 ya superó el data gate completo desde `a13d589`: 2.519 sesiones,
10.683 filas, 173 columnas, cero errores, dataset SHA
`6d27fdeb44422daa95aa79f777044e68276a2fe374c9bd847cd475d9dccfdb5b` y
source inventory SHA `2a305a2910f83c42a3c32b455d9b3a93907c7d762c5168d0946f9ce1eae306e8`.
Los compactos están congelados en `_diagnostics`; el dataset grande queda en
`tmp`. Siguiente hito: commit del runner manifest y una sola evaluación física
F0/F1. Todavía no se ha observado outcome ni rentabilidad H-FLOW.

El one-shot ya se ejecutó desde el runner congelado y H-FLOW1 queda cerrado:
4/24 celdas favorables, mediana ΔAUC `-0,029209`, p unilateral `0,984375` y
cero wins primarios 30/60m en QQQ, SPXW y SPY. QQQ 0/8, SPXW 3/8, SPY 1/8.
`physical_mechanism_pass=false` y `advance_to_option_payoff=false`; no se permite
entrenar payoff ni retunar subgrupos. La próxima búsqueda debe introducir una
medición nueva ya separada del bloque: quote size/depth, IV/skew deformation o
una fuente futures/vol-complex causal.

La auditoría posterior seleccionó H-IVSURF1 sin outcomes: QSIZE está incompleto
(1.441/2.519), ES/NQ/VIX1D/VVIX ausentes y VIX no tiene paridad histórica/live.
H-IVSURF1 mide cambios fixed-strike de nivel/skew/curvatura a 1/5/15m y excluye
H-FLOW/static skew. Predeclaración `52c169c`, código `9719ec2`.

El build autoritativo pasó: 10.683x54, SHA
`9d9404fd721df927c30ce4d6edeee800f528df81cf14639c23da1dc4008bc2b3`,
minimum ticker-year valid 90,319%, minimum ticker 96,673%, 2.519 fuentes y todos
los gates causales/coverage/distinctness/control PASS. Falta frozen runner y el
one-shot físico LR/LGBM; todavía no hay rentabilidad nueva.

El one-shot H-IVSURF1 falló: LR 12/24, mediana ΔAUC -0,001203, p 0,890625;
LightGBM 9/24, mediana -0,005822. QQQ/SPXW fallan; SPY pasa solo LR pero no la
sensibilidad, por lo que no puede seleccionarse post-hoc. No se autorizó payoff
y no existe rentabilidad nueva. Próxima medición nueva: H-QSIZE1; completar
1.078 sesiones para llegar a 2.519/2.519 antes de labels.

El backfill QSIZE ya completó 1.078/1.078 sesiones y 81.824.260 rows. El data
gate V1 fue rechazado sin outcomes: coverage mínimo ticker-año 98,477% y control
PASS, pero seis celdas de cambios de `local_signable_fraction` son constantes
cero. No se entrenó ningún modelo ni se calculó PnL.

Esto descubrió un bug semántico pre-outcome: signable fraction es calidad, aunque
V1 aún la incluía entre las 40 mediciones. V1R1 la mueve a audit-only; quedan 32
features de qimb/depth/relative-qimb, con mínimo 158 valores distintos por
ticker-año. La reparación no cambia datos, clocks, contratos, labels, folds ni
gates y conserva p secuencial `<0,0167`. Próximo paso: rebuild V1R1, freeze y
one-shot físico. Rentabilidad nueva: aún no demostrada.

V1R1 ya pasó el data gate: 10.683x76, SHA dataset `f4ed7b23...6c49`, cobertura
mínima ticker-año 98,477%, distinctness/control/exact-key PASS y cero errores.
Falta únicamente commitear el sello, congelar runner y abrir el one-shot físico.
