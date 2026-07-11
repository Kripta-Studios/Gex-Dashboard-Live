# Predeclaración — Portfolio Var-JEPA v1

**Congelada:** 2026-07-11 CEST, antes de ejecutar el nested walk-forward completo.

## Pregunta y factor único

¿Añadir un prior y posterior Gaussianos diagonales, reparametrización y KL annealed al mismo head MLP de payoff mejora de forma reproducible su representación OOS frente al head determinista?

- Control: `DeterministicPayoffHead`, MSE sobre retorno executable_quote recortado a `[-2, 2]`.
- Variante: `VariationalPayoffHead`, prior `p(z|x)`, posterior `q(z|x,y)`, reparametrización, reconstrucción y `KL(q||p)` con annealing 20 épocas.
- El encoder Phys-TD-JEPA flat OOF permanece congelado, actionless y no se reentrena.
- El head recibe el latente flat, contrato observable exacto, CALL/PUT, ticker, minuto y bucket. `HOLD` es abstención por threshold congelado en inner validation; no se crea una etiqueta HOLD con outcome futuro.
- La incertidumbre solo se exporta como diagnóstico. No entra en thresholds, selección ni sizing en v1.

La variante añade exclusivamente la maquinaria probabilística necesaria: 55.233 parámetros frente a 32.401 del control. Backbone, decoder, features, datos, orden de minibatches, epochs, batch, optimizador, folds y seeds son iguales.

## Datos y contrato sellado

- Dataset: `.../ptdj_ablation_flat_history_2025_h1_3_6_12_causal_202505_202605_v1/event_option_dataset.parquet`.
- SHA-256: `39203C83F47A60AFB2AB7951201CBEB3B9098F4238169F0D716649571667DA2F`.
- Tras contrato: 22.037 eventos, 44.074 filas CALL/PUT y 85 features; QQQ 6.659, SPXW 7.696, SPY 7.682.
- Fechas: `20250501..20260529`; junio de 2026 está físicamente ausente.
- Solo 0DTE `executable_quote`, entrada ask y trayectoria/salida bid.
- Rejilla 10:30–14:30 ET cada cinco minutos; latentes procedentes de secuencias contiguas del encoder flat OOF.
- Buckets: SPXW d25; QQQ/SPY d35.
- Una posición por ticker, hold mínimo 30m, cupos diarios SPXW/QQQ/SPY `4/2/1`, cooldown `0/30/0` minutos.

## Nested walk-forward y presupuesto

- Meses externos: `202601..202605`; junio no se abre.
- Por cada mes externo: train anterior a los tres meses de validación; los tres meses inmediatamente anteriores seleccionan threshold; test se puntúa después de persistir modelo y policy con hashes.
- Seed base emparejada: `20260618`; seed de fold `base + YYYYMM`, idéntica en ambos arms.
- CUDA determinista, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, RTX 5070 Ti 12 GB.
- 40 épocas, batch 512, infer batch 4096, hidden 128, latent 16, dropout 0,1, AdamW lr 0,001, weight decay 1e-6, clip grad 1,0.
- KL weight 1,0 y annealing lineal 20 épocas, solo para la variante.
- Una única rejilla pequeña y predeclarada de thresholds absolutos/quantiles; no hay búsqueda de arquitectura ni barrido hasta hallar PnL positivo.
- Inner gates por ticker: PF >=1,3; WR >=50%; >=18 trades en cada mes; 100% meses positivos. Si ningún threshold cumple, la policy se congela en abstención.

## Criterio de decisión

La arquitectura no se elegirá por PnL agregado. El analizador emparejará las 15 celdas ticker×mes y validará paridad de datos, argumentos, folds, seeds, cupos, cooldowns y hashes.

Se autoriza una segunda ablación independiente de abstención por incertidumbre solo si v1 obtiene simultáneamente:

1. menor MAE y RMSE OOS en al menos 10/15 celdas, mediana favorable y Wilcoxon unilateral `p<0,05` en ambas;
2. Spearman incertidumbre-error positivo en al menos 10/15 celdas y mediana positiva.

Se reportarán además PF, WR, trades, PnL y meses positivos por ticker/mes. El gate final sigue siendo, por ticker: PF >=1,3, WR >=50%, >=18 trades/mes y todos los meses positivos. Ningún resultado de v1 se marcará `production_live_ready`.

## Hashes congelados

| Artefacto | SHA-256 |
| --- | --- |
| Trainer/evaluador | `21C011C6F66906E90B128E091794FC92497739568DC10F34EBB6F9175B45F0A1` |
| Analizador pareado | `A5635C14FF39A66C4573A80F1C75165A30D50273F66887B25D8316606D9C35B2` |
| Test trainer | `C95108CBFAB1B2AC70B2C758D30F41FA34FBD05AA1E33944E79D6426A6D1DEE9` |
| Test analizador | `168C7784C06B2E6DBF78CD8DBBF9AA69EAFDD426ADD84742B7E25DF45B47422F` |
| Runner | `DAB6FA8F37D1EEF0AA2B1068BFDC6C964E083B99C6A8E0C4B887C44723106561` |
| Dataset | `39203C83F47A60AFB2AB7951201CBEB3B9098F4238169F0D716649571667DA2F` |

Tests focalizados previos a congelar: `9 passed in 2.13s`; `py_compile` y `git diff --check` PASS. Un smoke de un fold determinista/una época completó en CUDA sin alterar ninguna salida predeclarada.
