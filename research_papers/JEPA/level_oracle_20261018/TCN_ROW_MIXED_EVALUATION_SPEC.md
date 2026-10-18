# Evaluación fija FLAGS64 frente a batches mezclados

Estado: preevaluación; no autoriza iniciar fit mientras falten recursos coordinados.
Fecha: 2026-10-18. Es una continuación postresultado, sólo DEVELOPMENT_SEEN.

El contraste primario es FLAGS64 (control) frente al TCN row-mixed (variante).
El TCN original sólo sirve como contexto histórico. La única intervención de
entrenamiento es la mezcla de filas entre días, conservando muestra, entradas,
normalizadores FLAGS64, arquitectura, pesos IPW, loss, AdamW, tamaños de los
1.491 batches por época, cuatro épocas y 5.964 updates. No se selecciona época.
El diseño TRAIN y sus checkpoints se detallan en TCN_ROW_MIXED_DESIGN_DRAFT.md.

La evaluación usa sólo el modelo final de época cuatro, con su hash y autoridad
de entrenamiento completa. Reutiliza la inferencia exacta del wrapper FLAGS64
97836bb5a9a0364cf24888f55db0c1784268ed64575b71c4c76e1c03141d9aaf:
estados unique/inverse, mismo orden de batches y multiplicación float32 antes de
asignar float64. No se cambia el runner de entrenamiento congelado.

El control son las predicciones `variant` selladas de tcn_flags_v1, auditadas por
PASS_INDEPENDENT_TCN_FLAGS_ECONOMIC_AUDIT (audit SHA
9911ed97caf16f18802366dd14cb30ddeef68bdbfe05a28f3dc6711dccadb53f).
Un adaptador explícito por período conserva action_ids y copia esos scores a la
clave histórica `tcn_teacher` que espera evaluate_period del runner FLAGS64.
Esto no es una inferencia ni un control TCN original: cada conversión vincula
NPZ de origen, sidecar diario, manifest, valores exactos y mapping de claves.
El adaptador test sólo se construye después de freeze validación. Los artefactos
originales, modelos, caché y fuentes se mantienen inmutables.

Se ofrecen exactamente seis políticas: control/variant × umbral {0,5,10} USD,
comparación estricta >. Misma selección causal de acción, no-overlap, costes
ask→bid, slippage base/adverso, NO_FILL y salidas por nivel/stop/EOD del motor
auditado. No hay force-first ni mínimo de duración añadido.

Validación: 2025. Se exige al menos un FILLED por ticker y día del calendario
de sesiones completas congelado. Ranking entre candidatos que cumplen: suma
de PnL base por ticker dividida por su escala de riesgo TRAIN; empate: control
antes de variante y umbral menor. Si ninguno cumple, selected_policy=null y
diagnostic_best_not_approved registra sólo el mejor descriptivo. CASH no aprueba
la exigencia diaria. Se registra best_per_arm_2025, sin rescate por test.

Test: enero–junio 2026, únicamente después de congelar selección, modelos,
predicciones de validación, adaptador control y hashes de fuentes/código/spec.
Se informan las seis políticas, comparaciones pareadas al mismo umbral y la
selección congelada; el test no elige control, umbral, ticker, época ni modelo.
El gate económico final se conserva del runner FLAGS64 y se combina con el
gate diario. Todo es desarrollo observado, nunca outer intacto o promoción.

Cobertura: validación 741 ticker-días completos (9 cortos excluidos); test 369
esperados, 363 observables y 6 NO_EVALUABLE. Ausencias fallan el gate total y se
reporta por separado la frecuencia observable. El universo entero excluye 24
ticker-días de cierre corto, por tanto no acredita operar todos los días NYSE.
PnL en USD por un contrato, sin inferir rentabilidad de capital financiado.

Raíz de evaluación separada del cache/fit: tcn_row_mixed_v1_evaluation. Snapshots
y identity vinculados antes de primera validación; locks exclusivos, scores y
shards diarios recuperables sin overwrite, test sin freeze falla cerrado.
Completion y certificado sólo después de rehash de autoridad/outputs.
Auditor independiente: ejecución económica dadas predicciones selladas, seis
políticas, control FLAGS exacto, conversión, calendario, selección y bindings.
No se presenta esta auditoría como refit ni reproducción GPU.
