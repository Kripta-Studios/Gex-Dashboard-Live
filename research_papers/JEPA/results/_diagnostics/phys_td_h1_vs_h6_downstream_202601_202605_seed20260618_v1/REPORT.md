# Phys-TD h1 vs h6 downstream v1 — informe final

## Dictamen

h6=30m queda rechazado. Ninguno de los 210 candidatos internos de h1 ni h6 cumple simultáneamente las gates selladas; las 15 policies por arm congelaron abstain y ambos arms tienen 0 trades OOS. `h6_meets_full_ticker_gate=false`, `production_live_ready=false`.

No se probarán h3, h12, combinaciones multi-horizon ni adaptación h6 a partir de este resultado.

## Integridad del factor único

- Cinco checkpoints flat idénticos, entrenados previamente con horizontes `1/3/6/12`.
- 20.361/21.470/22.850/24.403/26.038 filas por fold, idénticas h1/h6.
- Paridad contra el export h1 previo: diferencia máxima z `0,0` y predicción h1 `0,0` en los cinco folds.
- Mismos labels, contratos d25/d35, ask→bid, hold>=30m, head, 40 épocas, seeds, folds, thresholds, caps/cooldowns y presupuesto.
- Provenance y runtime replay PASS en ambos arms; junio ausente; no hubo OOM/fallback.

El control h1 reproduce los conteos y extremos económicos del downstream frozen previo. Algunos pesos/checkpoints no son byte-idénticos porque el nuevo frame deriva `pred-z` desde el parquet con una ruta aritmética diferente de float32/float64; la desviación máxima de pesos fue ~`2,2e-6` en dos folds. h1 y h6 sí comparten exactamente la misma ruta y presupuesto dentro de esta ablación, por lo que la comparación del horizonte permanece simétrica.

## Candidate validation

| Arm | Ticker | PF>=1,3 | WR>=50% | Volumen >=54 | Mínimo mensual >=18 | Todos meses positivos | Gate conjunto |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| h1 | QQQ | 2 | 1 | 62 | 54 | 0 | 0/70 |
| h1 | SPXW | 1 | 0 | 65 | 64 | 0 | 0/70 |
| h1 | SPY | 0 | 0 | 47 | 15 | 0 | 0/70 |
| h6 | QQQ | 0 | 1 | 63 | 49 | 0 | 0/70 |
| h6 | SPXW | 1 | 0 | 65 | 59 | 0 | 0/70 |
| h6 | SPY | 12 | 6 | 42 | 12 | 2 | 0/70 |

h6 mejora algunos candidatos SPY, pero los únicos dos near-miss de cuatro gates fallan una condición distinta:

- fold `202602`, threshold abierto: 60 trades, mínimo18, WR50%, todos los meses positivos, pero PF `1,119`;
- fold `202603`, threshold abierto: PF `1,559`, WR52,54%, todos los meses positivos, pero mínimo mensual17.

No existe un threshold/fold que combine ambos resultados y no se puede mezclar retrospectivamente.

## Diagnóstico OOS del head

| Métrica h6−h1 | Wins h6 | Mediana | Wilcoxon unilateral |
| --- | ---: | ---: | ---: |
| MAE | 7/15 | `+0,011543` | `p=0,8961` |
| RMSE | 6/15 | `+0,009697` | `p=0,8738` |
| Directional accuracy | 5/15 | `-0,018998` | `p=0,9723` |
| MAE / media train | 7/15 | `+0,018869` | `p=0,8961` |

h6 empeora representación/predicción de payoff globalmente, aunque crea un nicho SPY inestable. No cumple la condición de avance por ticker y mes.

## Hashes

| Artefacto | SHA-256 |
| --- | --- |
| `summary.json` | `440030606DB3943D95491E68B620032B7B1585C7F0488B0BE399B87517EFD632` |
| horizon manifest | `F21336B1941508E382B6097CE44CEA9863253F07E5899374A5B9CC59BD361BDE` |
| input parity audit | `8664953FDA91325196D2BEA8973169242F49994E6B8FBB417FCC7DFC48BA7A62` |
| h1 candidate grid | `CAA1CB901A356AEF36E3397290831A6691A80CEB202847038C06962C6AF3B31B` |
| h6 candidate grid | `E283553F60AC94BF60A71DEC79D7FA1CE04F72008DEDE115412A70419719FE1E` |
| h1 diagnostics | `3F8EFDCF8A3AE29A92CC6B505E6F8C431099738BB9E2A333142342628F249AF0` |
| h6 diagnostics | `873CB4E69096A202BCBC6241EEB986FEE8F714B9AA6BFAF4BD752A1D8A7E60D7` |
| h1 provenance | `F6BA9440F897C61486E6351FFDD9EB496A289429BD166CD3522BDBEE9203D09C` |
| h6 provenance | `B64F80445351FAA22478B1D17D20DD9D23BEAB630503E615EE955A897CA1E0BD` |

Los cinco parquets de horizonte y diez checkpoints payoff se preservan localmente para auditoría y no se versionan.

## Siguiente paso seguro

El encoder comprimido z+motion no separa side de forma suficiente en h1 ni h6. Antes de otra corrida se auditará únicamente el schema live observable ya congelado para definir, con mecanismo económico, una allowlist pequeña de señales direccionales actuales/pasadas (por ejemplo retornos spot rezagados y skew/superficie observable) como posible skip connection al mismo head. No se seleccionarán features por correlación OOS ni se ejecutará un sweep.
