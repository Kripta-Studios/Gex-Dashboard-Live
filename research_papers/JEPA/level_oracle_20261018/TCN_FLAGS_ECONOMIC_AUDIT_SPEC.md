# Auditoría económica independiente TCN flags64

Estado: **PRE-RESULTADO**. Este contrato y sus fixtures se publican mientras el
fit de cuatro épocas sigue activo, antes de las predicciones y de la economía
2025/2026 del experimento. El auditor no importará `run_tcn_flags.py`,
`train_models.py`, `run_policy.py`, `level_engine.py` ni sus métricas.

El alcance es ejecución económica **dadas predicciones selladas**. No refittea,
no reproduce inferencia GPU y no acredita que el cambio de normalización sea la
única diferencia del tensor. Vinculará identity, snapshot ejecutado, plan,
modelo, normalizadores, training completion, full oracle audit, auditoría del
control original, freeze y completion por SHA256.

Antes de la primera predicción se publicó un wrapper de compatibilidad para que
la inferencia variante repita exactamente el orden `unique/inverse`, batches y
multiplicación float32→asignación float64 del helper original. El auditor exigirá
su binding previo, inclusión en freeze y certificado final; no reproduce esa
inferencia GPU ni la presenta como validación independiente del score.

## Predicciones y scheduler

En validación2025 y test2026H1 exigirá exactamente un NPZ por ticker-día
disponible, con `action_ids`, `control`, `variant`; cada sidecar diario y el
manifest deben sellarlo. `control` será exactamente `tcn_teacher` del NPZ
original auditado, con los mismos action IDs. Scores finitos.

Reconstruirá sin código productor las seis políticas
`control__0/5/10` y `variant__0/5/10`: máximo score por estado, empate por menor
action_id, umbral estricto, NO_FILL avanza un minuto sin rescate y FILLED avanza
a `exit_i+1`. Comparará los seis shards diarios, attempts y ledgers agregados,
ausencia de solapamiento, métricas pooled/ticker/mes y ambos costes.

## Cobertura, selección y freeze

Reconstruirá cada tabla `daily_coverage` sobre el calendario completo. Una
fuente disponible sin FILLED incumple; una ausente es `NO_EVALUABLE`, permanece
en la tabla y falla cobertura sin afirmar que el mercado no tuvo oportunidad.

La selección2025 considera sólo políticas con al menos un FILLED en cada
ticker-día y cobertura total. Entre ellas maximiza la suma de neto base por
ticker dividido por escala train; empate estable control, luego variante y
threshold menor. CASH no participa. Si no hay candidata,
`selected_policy=null` y se congela `diagnostic_best_not_approved` sin aprobarlo.
El freeze y todos sus hashes deben preceder test.

Para la política seleccionada, si existe, el auditor reconstruirá el gate por
ticker (netos base/adverso positivos, PF base≥1,2, al menos60 trades y3 meses
positivos), junto con cobertura/mínimo diario test. Si no existe selección,
exigirá el fallo explícito sin evaluar un diagnóstico como ganador. También
reproducirá las tres diferencias variante−control al mismo threshold.

Un PASS demostrará integridad de scheduler y reporting dados los scores. 2026
es desarrollo visto; no demuestra edge causal, recepción, fills live,
`technical_ready` ni promoción.
