# SUMMARY-update.md — Continuación verificable del trabajo de `SUMMARY.md`

**Inicio de esta continuación:** 10 de julio de 2026
**Objetivo:** cerrar los pendientes de `SUMMARY.md` y determinar, con evidencia causal y reproducible, si existe un paquete JEPA apto para live.

> Esta bitácora se actualiza durante el trabajo. Solo se marca como completado lo reproducido en esta sesión. No implica despliegue, commit ni push salvo que se indique expresamente.

## 1. Baseline verificado antes de nuevos cambios

### Estado del worktree

- `HEAD = 153f1a7` y `origin/main = 153f1a7`.
- El worktree ya contenía numerosos cambios tracked y artefactos untracked descritos en `SUMMARY.md`; se preservan como trabajo previo del usuario.
- `SUMMARY-update.md` estaba vacío al comenzar.

### Error de collection del selector: resuelto en el estado actual

Comando ejecutado:

```powershell
python -m pytest -q tests/test_build_event_option_dataset.py tests/test_event_option_live_causality.py tests/test_event_option_non_overlap.py tests/test_event_option_production_validator.py tests/test_jepa_bot_execution.py
```

Resultado reproducido:

```text
Python 3.14.2
41 passed in 12.14s
```

Conclusión: el pendiente de `SUMMARY.md` relativo al error de collection ya no bloquea el trabajo. Todavía no se ha validado aquí la suite completa del repositorio ni la validez estadística del paquete.

## 2. Dataset causal `executable_quote`: auditoría inicial

Artefactos inspeccionados:

```text
tmp/event_option_dataset_execquote_causal1030_202501_202606_v3/event_option_dataset.parquet
tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet
tmp/event_option_dataset_execquote_causal1030_202501_202606_v3/filtered_manifest.csv
```

Hashes SHA-256 reproducidos:

```text
68AE45C89D521F71431261DEEA9BCC7E465FEB294D17BF122AFBDDBB30A4C8F8  dataset base
E6A19EFBA1EDB055C733AAB4967843F7A4B5F1D2C8238A7A243FC5BBC2251903  dataset physics
```

Comprobaciones del dataset physics:

- 44.169 filas y 371 columnas almacenadas.
- Periodo `20250102..20260630`; tickers `QQQ`, `SPXW`, `SPY`.
- 1.113 sesiones/filas de manifest: QQQ 370, SPXW 373, SPY 370.
- 100% `expiry_mode=zero_dte` y 100% `option_price_mode=executable_quote`.
- Minutos `630..870` (10:30–14:30 ET), todos congruentes con la rejilla de 5 minutos.
- Cero filas previas a 10:30, cero claves duplicadas y cero infinitos numéricos.
- En los buckets d15/d25/d35/d50/d65/d80, CALL y PUT tienen disponibilidad, strike, retorno ejecutable y duración finitos en las 44.169 filas.
- Los seis directorios ThetaData declarados existen localmente.

Conclusión provisional: el parquet es apto para comenzar entrenamiento causal. Falta todavía reproducir su build, congelar hashes de las fuentes y verificar los artefactos de entrenamiento.

## 3. Paquete legacy actual: fallo reproducido

Se ejecutó el validador endurecido sobre el paquete actual tanto con la gate canónica (`WR 0,45`, `PF 1,3`, mínimo 12) como con la gate estricta (`WR 0,50`, `PF 1,3`, mínimo 18). Ambas ejecuciones fallaron.

Bloqueos reproducidos:

- falta `policy_selection_provenance` causal;
- los `select_months` de todos los componentes solapan enero–junio de 2026;
- labels legacy, no `executable_quote` ask→bid;
- falta `position_overlap_policy=reject_while_open`;
- 55 entradas solapadas incompatibles con live;
- `SPY.min_month_trades = 14`, por debajo del objetivo estricto `>18`.

El paquete actual continúa siendo `BLOCKED_FOR_PRODUCTION`; no se modificará ni se desplegará mientras se construye una alternativa separada.

## 4. Selector nested: trazabilidad y equivalencia live completadas

Archivo modificado:

```text
neural/jepa/walkforward_event_option_profile_selector.py
```

Cambios:

- admite cooldown por ticker mediante `--ticker-cooldown-minutes`;
- admite una rejilla predeclarada de cupos diarios por ticker mediante `--ticker-max-day-grids`;
- registra `training_months`, `selection_months` y cooldown efectivo en cada fold;
- congela el modelo CALL/PUT, medianas, features, perfil y threshold/cupo **antes** de puntuar el mes externo;
- calcula SHA-256 del pickle y del manifest de cada policy ticker/mes;
- genera un artefacto combinado por mes sin métricas OOS;
- genera `policy_selection_provenance.json` en formato `nested_walk_forward`, utilizable por el validador.

Tests añadidos en:

```text
tests/test_event_option_live_causality.py
```

Validación ejecutada:

```text
py_compile: PASS
26 passed in 1.40s
```

La ejecución de 26 tests incluye causality/live, no-solapamiento, validador de producción y las nuevas pruebas de overrides y hashes. Falta ejecutar la suite focalizada completa tras los siguientes cambios.

### Backend y optimización necesaria para completar el walk-forward

Se probaron CPU, GPU OpenCL FP32 y GPU OpenCL FP64 sobre el mismo perfil real, sin usar el mes externo para tomar la decisión. Los tres produjeron exactamente:

```text
val_score = 7.450371570491814
deploy_config = thr0.160_maxday1
```

Tiempos antes de optimizar:

```text
GPU FP32  26.247 s
GPU FP64  26.839 s
CPU       23.949 s
```

`cProfile` mostró que 64,986 de 66,368 segundos se consumían en `walkforward_event_option_gate.deploy()`: cada configuración convertía repetidamente las 373 columnas a namedtuples.

Archivo optimizado:

```text
neural/jepa/walkforward_event_option_gate.py
```

`deploy()` ahora simula cooldown/posición/cupo con arrays de `minute` y `exit_minutes`, conserva posiciones y materializa las filas completas una sola vez. La semántica no cambió.

Resultado posterior sobre el mismo perfil:

```text
1.410 s
val_score = 7.450371570491814
deploy_config = thr0.160_maxday1
```

Validación posterior:

```text
py_compile: PASS
26 passed in 1.39s
```

Las corridas completas previas fueron interrumpidas antes de producir ningún fold porque la sobre-suscripción CPU/GPU no aportaba aceleración. Se cerraron explícitamente los procesos Python huérfanos antes de reiniciar.

## 5. Nested walk-forward exploratorio enero–mayo: completado y rechazado

Directorio:

```text
research_papers/JEPA/results/_diagnostics/event_option_execquote_causal1030_nested_exploratory_202601_202605_v1/
```

La corrida terminó los 15 folds externos (`3 tickers × 5 meses`). Cada ticker/mes tiene pickle, manifest y SHA-256 congelados antes de puntuar el mes. El artefacto combinado:

```text
policy_selection_provenance.json
```

declara `mode=nested_walk_forward`, cubre `202601..202605` y termina con `passed=true` para causalidad/provenance.

### Bug de resume encontrado y corregido

Al reanudar 13 folds, pandas infería `date` como entero en el CSV histórico y los nuevos folds la aportaban como string. La mezcla rompía `metrics().sort_index()` después de guardar QQQ/abril.

Correcciones:

- `load_checkpoint()` fuerza tipos string para ticker/date/month/test_month;
- `metrics()` normaliza `date` y `month` antes de agrupar;
- regresión añadida con fechas/meses de tipos mixtos.

Validación:

```text
27 passed in 1.56s
```

### Resultado OOS exploratorio

| Scope | Trades | WR | PF | PnL (R) | Min trades/mes | Meses positivos |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Overall | 324 | 43,827% | 0,909 | -9,287 | 48 | 40% |
| QQQ | 94 | 44,681% | 0,984 | -0,492 | 15 | 40% |
| SPXW | 107 | 42,991% | 0,832 | -5,816 | 10 | 40% |
| SPY | 123 | 43,902% | 0,919 | -2,979 | 19 | 40% |

Dictamen: **rechazado**. Ningún ticker cumple WR > 50%, PF > 1,3 ni positividad mensual completa. SPXW y QQQ tampoco cumplen el volumen mínimo. El deterioro confirma que el edge legacy no sobrevive simultáneamente a ask→bid, no-solapamiento, features live-observables y selección nested.

Junio de 2026 no se abrió ni se usó para cambiar esta conclusión. No se exportará una policy live de este baseline.

## 6. Primer bloque de auditoría académica

Se creó y se mantiene:

```text
SUMMARY-articles.md
```

Tres subagentes completaron la correspondencia entre los 29 trabajos JEPA/world-model aportados y el código/resultados del repo, usando fuentes primarias y evidencia local. Hallazgos principales:

- el repo ya tiene predicción latente multihorizonte, SIGReg/VISReg/VICReg, teacher EMA, prototipos, surprise, OOD-kNN y un encoder por modalidades;
- ninguna de esas ramas tiene evidencia `executable_quote` suficiente para promoción;
- todas las corridas Phys-TD auditadas utilizaron `encoder_input_mode=flat`, así que el encoder semántico modal existe pero nunca se probó;
- VISReg está implementado, pero su prueba legacy cambió varios factores y terminó negativa;
- faltan masking semántico denso, objetivos cross-modal fieles, Gram anchoring, jerarquía lenta/rápida real, posterior variacional e incertidumbre calibrada;
- la dinámica del mercado debe seguir siendo actionless; la acción solo debe condicionar un head separado de cartera/payoff y contrato.

Se predeclaró una secuencia de experimentos causal: Phys-TD/MJEPA modal, semantic masking, H-Market-JEPA/Fast-LeWM, Portfolio Var-JEPA, surprise+coreset y AdaJEPA solo en shadow. Junio de 2026 continúa sellado. Antes de entrenar se corregirán en el trainer la exclusión física del holdout, la allowlist de features live y la continuidad exacta de cinco minutos.

## 7. Trazabilidad Git

Primer commit técnico creado:

```text
2f20055 fix: enforce causal executable event-option pipeline
```

Incluye las correcciones de causalidad/live, selector nested, hashes/provenance, optimización del simulador y tests focalizados. No incluye los JSON del paquete legacy —sigue bloqueado— ni datasets/resultados grandes.

El commit documental se creó como:

```text
940a043 docs: record causal audit and JEPA research status
```

Los commits `2f20055` y `940a043` fueron subidos correctamente a `origin/main` (`153f1a7..940a043`).

## 8. Trainer Phys-TD-JEPA endurecido antes de usar GPU

Archivo:

```text
neural/jepa/walkforward_event_phys_td_jepa_oof.py
```

Se detectaron y corrigieron tres riesgos que invalidaban una comparación SOTA:

1. El selector numérico del trainer aceptaba cinco features intradía que el snapshot live no puede reconstruir (`phys_event_seq_in_day`, `phys_event_frac_in_day`, `phys_minutes_since_first_event`, `phys_spot_ret_from_first_event_bps`, `phys_same_day_event_count`). Ahora usa el mismo contrato `live_observable_feature_issues_for_columns` que selección/live.
2. Las secuencias agrupaban filas adyacentes aunque entre ellas faltasen uno o más buckets. Ahora se dividen en tramos con diferencia exacta de cinco minutos, tanto para targets de training como para contextos y surprise OOF.
3. El parquet consolidado podía conservar meses posteriores al rango OOF. Ahora `--data-cutoff-month` se aplica antes de cualquier fit/export y, en OOF, debe coincidir exactamente con `--end-month`; para esta investigación es `202605`.

También se fija y registra la rejilla 10:30–14:30 ET, anchor 10:00 y paso cinco minutos. Se añadieron cinco regresiones en:

```text
tests/test_event_phys_td_jepa_causality.py
```

Validación:

```text
17 passed in 3.06s
50 passed in 2.95s  (suite focalizada completa, incluyendo los cinco tests nuevos)
```

El primer intento de esta suite encontró un `PermissionError` al crear `tmp_path` bajo `%LOCALAPPDATA%`; al ejecutar con `--basetemp C:\tmp\pytest-jepa-causal-20260710a` pasaron los 17 tests. No fue un fallo funcional.

Auditoría del dataset después del filtro:

```text
filas hasta 202605:             41.883
features numéricas causales:       282
features reproducibles live:       277
features rechazadas:                 5
segmentos contiguos:             2.660
ventanas h<=60m:                19.685
ventanas h<=120m:               10.728
ventanas h<=180m:                3.638
```

La primera ablación queda predeclarada con horizontes 5/15/30/60m y mismo presupuesto para `flat` y `modal`. Junio sigue físicamente excluido.
