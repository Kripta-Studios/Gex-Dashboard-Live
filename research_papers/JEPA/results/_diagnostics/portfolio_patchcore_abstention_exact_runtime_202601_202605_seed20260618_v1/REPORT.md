# Portfolio PatchCore abstention v1

Nested walk-forward exacto d25 SPXW/d35 QQQ-SPY sobre `202601..202605`; junio de 2026 permaneció sellado. Control y PatchCore compartieron el mismo payoff head determinista, scores, acciones, folds y seeds. PatchCore solo pudo abstener por distancia a un coreset k-center train-only.

## Resultado

- Control: 15/15 policies `invalid_validation`, 0 trades OOS.
- PatchCore: 15/15 policies `invalid_validation`, 0 trades OOS.
- Candidate grid control: 210 filas; 0 cumplen PF/WR/volumen/meses positivos simultáneamente.
- Candidate grid PatchCore: 1.470 filas; 0 cumplen las cuatro gates.
- Distancia-error OOS: Spearman positivo en 10/15 celdas, mediana `0,098982`.
- Provenance y runtime replay: PASS.

PatchCore incrementó el número de candidatos que individualmente superaban volumen, pero no creó una combinación estable de edge y cobertura. Los únicos near-miss de tres gates fueron SPY/202604 y fallaron volumen mensual (3–4 trades en el peor mes interno). QQQ y SPXW permanecieron muy por debajo de PF/WR.

## Decisión

`distance_diagnostic_supported=true`, pero `patchcore_meets_full_downstream_gate=false`, `continue_from_patchcore=false` y `production_live_ready=false`.

No se autoriza barrer tamaño de coreset, métricas o quantiles, ni relajar gates. El resultado indica que la distancia es útil como diagnóstico de drift/error, no como rescate de este payoff head.

## Nota de diagnóstico

El runner v1 inicializó el mejor score inválido en `-1e18`. En SPY, sumar menos de aproximadamente 64 trades podía redondear al mismo float y dejar métricas de la mejor policy inválida en cero. Esto no podía seleccionar ni desplegar la policy y no alteró decisiones o trades. El código v1r1 usa `-inf` y añade un test; `candidate_validation.csv` conserva todas las métricas autoritativas de la corrida original.
