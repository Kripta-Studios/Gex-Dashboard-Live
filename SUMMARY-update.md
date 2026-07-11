# SUMMARY-update.md — Continuación verificable del trabajo de `SUMMARY.md`

**Inicio de esta continuación:** 10 de julio de 2026
**Objetivo:** cerrar los pendientes de `SUMMARY.md` y determinar, con evidencia causal y reproducible, si existe un paquete JEPA apto para live.

> Esta bitácora se actualiza durante el trabajo. Solo se marca como completado lo reproducido en esta sesión. No implica despliegue, commit ni push salvo que se indique expresamente.

## Actualización 2026-07-11 04:14 CEST — resultado final de `history_2022` vs `history_2025`

La ablación predeclarada terminó completa y sin errores: 13 folds OOF y 15 folds nested por arm, provenance PASS, mismos folds/seeds/presupuesto y un solo factor cambiado (`encoder_training_history_start`). El runner salió normalmente y no quedan procesos de entrenamiento o evaluación activos.

| Arm | Trades | WR | PF | PnL (R) | Max DD | Gates ticker×mes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `history_2025` | 495 | 45,051% | 0,863 | -20,174 | -27,180 | 4/15 |
| `history_2022` | 440 | 42,273% | 0,764 | -31,476 | -34,403 | 1/15 |

| Arm | Ticker | Trades | PF | PnL (R) | Mínimo trades/mes | Meses positivos |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `history_2025` | QQQ | 161 | 0,893 | -4,819 | 22 | 40% |
| `history_2025` | SPXW | 235 | 0,711 | -22,935 | 32 | 0% |
| `history_2025` | SPY | 99 | 1,336 | +7,580 | 18 | 80% |
| `history_2022` | QQQ | 163 | 0,764 | -10,638 | 26 | 0% |
| `history_2022` | SPXW | 180 | 0,696 | -16,542 | 29 | 0% |
| `history_2022` | SPY | 97 | 0,874 | -4,296 | 18 | 60% |

Meses overall de la historia larga: enero `PF 0,514/-18,133R`, febrero `0,981/-0,417R`, marzo `0,682/-8,107R`, abril `1,002/+0,048R` y mayo `0,808/-4,868R`.

Evidencia pareada: la historia larga mejora el ratio OOF error/persistencia en 13/15 celdas (Wilcoxon `p=0,000580`) y la tasa de batir persistencia en 11/15 (`p=0,003357`), pero no el downstream: PF 6/15 (`p=0,9527`) y PnL 7/15 (`p=0,7729`). Bootstrap diario: diferencia `-11,302R`, IC95% `[-44,087,+20,825]`, probabilidad positiva `0,248`.

Decisión: `continue_from_history_2022=false`. La mejora de representación no se reproduce en el objetivo downstream; ambos arms quedan rechazados y no se promueve ninguno. El informe contiene métricas por fold, mes y ticker, seeds y hashes en `research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_history_2022_vs_2025_runtime_contract_analysis_202601_202605_v1/` (`summary.json` SHA-256 `A1AFC66158674F239DA027C614C83566817563F19DB32F1A6CAF57A13530BB1`).

Se revalidaron executable_quote ask→bid, 0DTE, features live, secuencias contiguas, rejilla 10:30–14:30/5m, hold >=30m, cupos/cooldowns runtime y ausencia de solapamientos. Junio de 2026 sigue físicamente sellado. `py_compile` PASS; suite focalizada final: `70 passed in 4.88s`.

## Criterio canónico de investigación y promoción

Toda variante debe entrenarse, seleccionarse y evaluarse buscando simultáneamente, **para cada ticker** (`SPXW`, `QQQ`, `SPY`):

- hold realizado de al menos 30 minutos por trade;
- profit factor `>= 1,30`;
- win rate `>= 50%`;
- al menos 18 trades en cada mes evaluado;
- PnL positivo en todos los meses del walk-forward.

Las fuentes históricas disponibles son `D:/ThetaData/data_options` y `D:/ThetaData/data_underlying_derived`, con opciones y spot entre 2022 y 2026. Ese histórico puede ampliar el train/inner-validation solo mediante folds causales; junio de 2026 continúa completamente sellado durante esta investigación y nunca puede entrar en train, selección de arquitectura o thresholds.

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
- `SPY.min_month_trades = 14`, por debajo del objetivo vigente de al menos 18.

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

## 9. Ablación causal `flat` vs `modal`: inicio

### Validación previa

```text
50 passed in 4.92s  (suite focalizada completa, incluyendo tests de causalidad)
```

No hay procesos Python activos del agente anterior. Git HEAD = `0458ff4`. Sin cambios sin commit relevantes para la ablación.

### Diseño experimental

- **Factor único:** `--encoder-input-mode` (`flat` vs `modal`)
- **Dataset:** `tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet` (44.169 filas, 371 cols)
- **SHA-256 dataset:** `E6A19EFBA1EDB055C733AAB4967843F7A4B5F1D2C8238A7A243FC5BBC2251903`
- **Seed:** `20260618`
- **Horizontes:** `1,3,6,12` (5/15/30/60 minutos)
- **OOF:** `--start-month 202501 --end-month 202605` (17 folds: May 2025 – May 2026)
- **Data cutoff:** `202605` (junio excluido)
- **Features:** live-observable only (277 de 282)
- **Contiguidad:** 5 minutos
- **Rejilla:** 10:30–14:30 ET
- Mismos hiperparámetros en ambos arms: `z_dim=32, phys_dim=12, delta_dim=16, hidden_dim=128, num_layers=2, epochs=8, batch_size=1024, context_len=6, dropout=0.10`

### Arm 1: `flat` (COMPLETADO)

Comando:

```powershell
python neural/jepa/walkforward_event_phys_td_jepa_oof.py \
  --data "tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet" \
  --output-dir "research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_h1_3_6_12_causal_202501_202605_v1" \
  --tickers SPXW SPY QQQ --expiry-modes zero_dte \
  --start-month 202501 --end-month 202605 \
  --horizons 1,3,6,12 --encoder-input-mode flat \
  --live-observable-features-only \
  --entry-start-minute-et 630 --entry-end-minute-et 870 \
  --entry-grid-anchor-minute-et 600 --expected-step-minutes 5 \
  --seed 20260618 --device cpu --epochs 8 --batch-size 1024 \
  --context-len 6 --z-dim 32 --phys-dim 12 --delta-dim 16 \
  --hidden-dim 128 --num-layers 2
```

OOF Features extraídas exitosamente.
Evaluación OOS con nested walk-forward `walkforward_event_option_profile_selector.py` completada en `ptdj_ablation_flat_h1_3_6_12_causal_202501_202605_v1_walkforward`.

### Arm 2: `modal` (COMPLETADO)

Mismo comando que Arm 1, reemplazando `--encoder-input-mode flat` por `--encoder-input-mode modal`.
OOF Features extraídas exitosamente.
Evaluación OOS con nested walk-forward completada en `ptdj_ablation_modal_h1_3_6_12_causal_202501_202605_v1_walkforward`.

### Resultados de la ablación OOS (Nested Walk-forward Enero-Mayo 2026)

| Experimento | Trades | WR | PF | PnL (R) | Max DD | QQQ PF | SPXW PF | SPY PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline Exploratorio | 324 | 43,8% | 0,909 | -9,28 | - | 0,984 | 0,832 | 0,919 |
| **Arm 1: Flat** | 643 | 43,7% | 0,860 | -28,94 | -39,8% | 0,876 | 0,839 | 0,867 |
| **Arm 2: Modal** | 575 | 43,0% | 0,910 | -16,09 | -26,8% | 0,731 | 0,901 | 1,133 |

**Conclusión:** 
El encoder `modal` supera a `flat` en Profit Factor global (0,910 vs 0,860) y reduce el Max Drawdown (-26,8% vs -39,8%). A nivel de ticker, `modal` mejora significativamente SPY (1,133 vs 0,867) y SPXW (0,901 vs 0,839), pero degrada severamente QQQ (0,731 vs 0,876).
Sin embargo, **ninguno de los dos supera la gate de producción** requerida para promoción a live (PF > 1,3 y WR > 50% en general). Junio de 2026 permanece completamente sellado y no se ha exportado política productiva.

## 10. Semantic-Masked Market JEPA (SMM)

Una vez confirmada la superioridad del encoder modal, se procedió con la cola de experimentación SMM (Semantic-Masked Market JEPA).

### SMM-Baseline (COMPLETADO)

Se integraron el enmascaramiento semántico (15% modal, 15% temporal) y la predicción en el espacio latente (`z`) manteniendo los mismos hiperparámetros y dataset:

- `--mask-modal-prob 0.15 --mask-temporal-prob 0.15`
- `lambda-sigreg 0.05` (por defecto)
- `lambda-vicreg 0.10` (por defecto)

**Resultados OOS de SMM-Baseline (corregidos a enero–mayo de 2026):**
| Experimento | Trades | WR | PF | PnL (R) | Max DD | QQQ PF | SPXW PF | SPY PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Arm 2: Modal** (Solo Encoder) | 575 | 43,0% | 0,910 | -16,09 | -26,8% | 0,731 | 0,901 | 1,133 |
| **SMM-Baseline** | 341 | 41,35% | 0,778 | -24,177 | -27,33% | 0,833 | 0,730 | 0,793 |

**Conclusión SMM-Baseline:**
SMM baseline queda rechazada: empeora PF y PnL frente a `modal`, no supera ninguna gate y solo febrero fue positivo. No obstante, el deterioro correcto en la ventana comparable es PF `0,910→0,778` y Max DD `-26,84%→-27,33%`; las cifras anteriores de PF `0,739`, `-79,727R` y DD `-82,71%` corresponden al rango extendido mayo de 2025–mayo de 2026 y no eran comparables con la tabla `flat/modal`.

### Cola de Ablaciones SMM (EN PROCESO)

Para determinar qué factor de la pérdida JEPA está degradando la representación, se han lanzado 4 ablaciones automatizadas, cambiando un regularizador a la vez respecto al SMM-Baseline:
1. `sigreg_off`: Desactivar SIGReg (`--lambda-sigreg 0.0`)
2. `visreg`: Activar VISReg (`--lambda-visreg 0.1`)
3. `proto`: Activar Prototipos / EMA (`--lambda-proto 1.0`)
4. `gram`: Activar Gram Anchoring (`--lambda-gram 0.1`)

*(El proceso automatizado de extracción, cruce y evaluación OOS sigue corriendo en background.)*

### Auditoría de reanudación (2026-07-10 21:37 CEST)

Se comprobó el estado contra procesos y artefactos, no solo contra el handoff:

- `flat` y `modal` están completos; no hay que repetirlos.
- SMM baseline y su nested walk-forward están completos.
- PID `58028` mantiene la cola secuencial. `sigreg_off` terminó sus 39 folds a las 21:38:51; el wrapper inició `visreg` en PID `18384` a las 21:38:51.
- `proto` y `gram` aún no habían creado directorios de salida.
- Junio sigue físicamente excluido (`effective_data_cutoff_month=202605`, selector `end_month=202605`).

La comparación publicada entre `modal` y SMM baseline debe considerarse exploratoria, no una ablación limpia: además de activar conjuntamente máscara modal y temporal al 15%, cambió el backend de CPU a CUDA. Las cuatro comparaciones internas de la cola parten de la misma baseline SMM CUDA y modifican un único peso de regularización cada una. No se atribuirá causalmente el deterioro al masking hasta ejecutar controles de un solo factor con backend fijo.

Se encontró además que el script SMM usa `--start-month 202505` en el selector, mientras `flat/modal` se evaluaron en `202601..202605`. Las métricas extendidas siguen siendo útiles como diagnóstico y son homogéneas dentro de la cola, pero no pueden ocupar la tabla exploratoria de cinco meses. Los trades se recomputaron con `walkforward_event_option_gate.metrics()` y `expected_months=202601..202605`.

Resultado reproducido de `sigreg_off` en enero–mayo:

| Scope | Trades | WR | PF | PnL (R) | Max DD | Min trades/mes | Meses positivos |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Overall | 422 | 40,52% | 0,851 | -20,951 | -33,31% | 57 | 20% |
| QQQ | 132 | 41,67% | 0,840 | -6,300 | -12,12% | 18 | 20% |
| SPXW | 161 | 37,89% | 0,857 | -8,367 | -18,55% | 20 | 20% |
| SPY | 129 | 42,64% | 0,855 | -6,284 | -12,81% | 18 | 20% |

Desactivar SIGReg mejora PF frente a la SMM baseline comparable (`0,851` frente a `0,778`), pero sigue por debajo de `modal` (`0,910`), pierde `20,951R`, tiene cuatro de cinco meses negativos y queda rechazado. En el rango extendido produjo 1.025 trades, WR 38,63%, PF 0,743, `-90,675R`, DD `-96,02%` y mínimo mensual cero.

#### Métricas reproducidas por mes y ticker (`202601..202605`)

Notación de cada celda: `trades / WR / PF / PnL(R)`. Todas las cifras se recomputaron desde el CSV de trades con la misma función `metrics()`; no provienen de copiar la tabla documental previa.

| Ticker/mes | Flat | Modal | SMM baseline | SMM sigreg_off |
| --- | --- | --- | --- | --- |
| QQQ 202601 | 73 / 42,47% / 0,778 / -5,595 | 37 / 32,43% / 0,759 / -3,421 | 20 / 35,00% / 0,768 / -1,459 | 31 / 32,26% / 0,805 / -2,386 |
| QQQ 202602 | 29 / 44,83% / 1,164 / +1,195 | 48 / 29,17% / 0,784 / -4,291 | 17 / 41,18% / 0,971 / -0,161 | 35 / 40,00% / 0,716 / -2,741 |
| QQQ 202603 | 35 / 42,86% / 0,596 / -4,749 | 43 / 46,51% / 0,836 / -1,772 | 19 / 31,58% / 0,399 / -3,626 | 28 / 35,71% / 0,509 / -4,062 |
| QQQ 202604 | 29 / 48,28% / 1,594 / +4,513 | 26 / 38,46% / 0,551 / -4,396 | 18 / 50,00% / 1,718 / +3,530 | 18 / 61,11% / 1,900 / +3,366 |
| QQQ 202605 | 40 / 47,50% / 0,730 / -3,368 | 20 / 40,00% / 0,602 / -2,541 | 20 / 40,00% / 0,491 / -3,117 | 20 / 50,00% / 0,913 / -0,478 |
| SPXW 202601 | 47 / 51,06% / 1,180 / +2,233 | 50 / 54,00% / 1,152 / +1,885 | 53 / 49,06% / 0,738 / -4,054 | 48 / 27,08% / 0,871 / -2,755 |
| SPXW 202602 | 63 / 41,27% / 1,002 / +0,034 | 66 / 43,94% / 1,133 / +2,811 | 18 / 50,00% / 1,237 / +1,353 | 50 / 34,00% / 0,658 / -6,937 |
| SPXW 202603 | 42 / 45,24% / 0,780 / -2,227 | 43 / 48,84% / 0,863 / -1,244 | 22 / 40,91% / 0,767 / -1,344 | 22 / 45,45% / 0,902 / -0,439 |
| SPXW 202604 | 33 / 33,33% / 0,531 / -6,147 | 25 / 40,00% / 0,712 / -2,458 | 24 / 33,33% / 0,678 / -2,723 | 21 / 57,14% / 1,828 / +4,370 |
| SPXW 202605 | 36 / 36,11% / 0,623 / -5,524 | 37 / 32,43% / 0,500 / -7,554 | 20 / 35,00% / 0,384 / -4,981 | 20 / 45,00% / 0,621 / -2,605 |
| SPY 202601 | 40 / 47,50% / 1,055 / +0,595 | 39 / 41,03% / 0,837 / -1,740 | 20 / 40,00% / 0,845 / -0,995 | 39 / 48,72% / 0,911 / -1,103 |
| SPY 202602 | 35 / 40,00% / 0,790 / -2,751 | 53 / 54,72% / 1,501 / +6,634 | 32 / 34,38% / 0,915 / -1,130 | 19 / 47,37% / 1,505 / +2,861 |
| SPY 202603 | 80 / 47,50% / 1,129 / +3,144 | 38 / 42,11% / 1,156 / +1,892 | 22 / 54,55% / 0,935 / -0,279 | 33 / 45,45% / 0,978 / -0,222 |
| SPY 202604 | 37 / 43,24% / 0,618 / -4,658 | 25 / 48,00% / 0,759 / -1,692 | 18 / 44,44% / 0,822 / -0,988 | 18 / 22,22% / 0,181 / -6,319 |
| SPY 202605 | 24 / 37,50% / 0,394 / -5,635 | 25 / 44,00% / 1,204 / +1,801 | 18 / 33,33% / 0,401 / -4,205 | 20 / 40,00% / 0,796 / -1,501 |

| Mes overall | Flat | Modal | SMM baseline | SMM sigreg_off |
| --- | --- | --- | --- | --- |
| 202601 | 160 / 46,25% / 0,943 / -2,768 | 126 / 43,65% / 0,912 / -3,276 | 93 / 44,09% / 0,769 / -6,508 | 118 / 35,59% / 0,864 / -6,244 |
| 202602 | 127 / 41,73% / 0,964 / -1,521 | 167 / 43,11% / 1,095 / +5,153 | 67 / 40,30% / 1,003 / +0,062 | 104 / 38,46% / 0,809 / -6,817 |
| 202603 | 157 / 45,86% / 0,917 / -3,832 | 124 / 45,97% / 0,965 / -1,125 | 63 / 42,86% / 0,674 / -5,249 | 83 / 42,17% / 0,794 / -4,724 |
| 202604 | 99 / 41,41% / 0,809 / -6,292 | 76 / 42,11% / 0,663 / -8,545 | 60 / 41,67% / 0,990 / -0,181 | 57 / 47,37% / 1,085 / +1,417 |
| 202605 | 100 / 41,00% / 0,601 / -14,527 | 82 / 37,80% / 0,727 / -8,294 | 58 / 36,21% / 0,420 / -12,302 | 60 / 45,00% / 0,767 / -4,584 |

Los artefactos extendidos de baseline y `sigreg_off` contienen 39 filas de fold, pero `policy_selection_provenance.json` termina `passed=false` porque los tres tickers no seleccionaron policy en `202511`; los 15 folds `202601..202605` sí tienen hashes completos. Se debe regenerar el selector con `--start-month 202601` para obtener un artefacto de provenance autocontenido y comparable, sin reentrenar el encoder ni usar junio.

Auditoría semántica de los arms todavía en cola:

- `proto` ejecuta únicamente `--lambda-proto 1.0`; no pasa `--use-ema-teacher`. Por tanto se documentará como pérdida de prototipos con target stop-gradient del mismo modelo, no como “Prototipos / EMA”. Activar EMA además sería un segundo factor y requeriría otro arm predeclarado.
- `gram` ejecuta `--lambda-gram 0.1`, pero la implementación compara la Gram de `pred_z` con la Gram de `target_z` del mismo fold. No existe un encoder de referencia preentrenado y congelado; se documentará como **Gram relational consistency**, no como Gram anchoring fiel a DINOv3.
- `modal` y SMM baseline ya compartían predicción latente multihorizonte, `lambda_state`, `lambda_dyn`, SIGReg y VICReg. El cambio real de SMM baseline fue masking modal+temporal y backend, no “añadir predicción JEPA”.

Validación de código durante la corrida, sin modificar el trainer cargado por el wrapper:

```text
python -m py_compile neural/jepa/walkforward_event_phys_td_jepa_oof.py neural/jepa/append_xinput_oof_to_event_option_dataset.py
50 passed in 10.44s
```

Se añadieron regresiones unitarias para los dos modos de masking (probabilidad 1 en train, desactivados en eval) y para la pérdida de consistencia Gram (cero con geometría idéntica, positiva y con gradiente finito al diferir). El primer intento descubrió que el fixture omitía el argumento obligatorio `output_dim`; se corrigió solo el test, sin tocar el trainer activo. Resultado final: `8 passed in 2.20s` para `tests/test_event_phys_td_jepa_causality.py`.

Suite focalizada completa posterior: `53 passed in 3.79s` con `--basetemp C:\tmp\pytest-jepa-causal-20260710d`.

También se añadió `tests/test_append_xinput_oof_to_event_option_dataset.py`, que reproduce el join `SPXW` por identidad, la fecha `trade_date`, el prefijo configurable `ptdj_`, la imputación cero de una fila no emparejada y la exclusión de columnas de otro prefijo. Resultado: `1 passed in 0.52s`.

### Invalidez semántica detectada y cola detenida

El masking heredado también se aplicaba al target futuro: con `use_ema_teacher=false`, `train_epoch()` llamaba `model.encode_state(targets)` mientras el encoder seguía en modo train, y `ModalSequenceEncoder.forward()` enmascaraba cualquier entrada en modo train. Esto contradice el protocolo predeclarado de enmascarar **solo el prefijo observado**. Por ello, SMM baseline, `sigreg_off` y la extracción `visreg` v1 quedan como diagnósticos inválidos para atribución SMM, aunque mantengan causalidad temporal de datos.

Se detuvo de forma verificada el selector `visreg` PID `51972` a las 21:50, con 8/39 folds extendidos preservados hasta `SPXW/202512`; el wrapper PID `58028` salió. Una automatización paralela del IDE lanzó después `run_smm_ablations_202601.ps1` y relanzó dos veces el selector `sigreg_off` sobre el mismo directorio con `--no-resume`; se detuvieron PID `5268`/`28468` y PID `66588`/`30300`. Ese relanzamiento dejó el `_walkforward` de `sigreg_off` parcial (una fila `SPXW/202601`) y, por tanto, los hashes finales extendidos registrados antes ya no describen los archivos actuales en esa ruta.

El segundo script tampoco era reproducible como cola: habría mezclado encoders v1 con targets enmascarados y encoders posteriores cargando código corregido, y su appender de `proto/gram` usaba el argumento inexistente `--output`.

Corrección aislada implementada:

- `ModalSequenceEncoder.forward(..., apply_mask=False)` permite codificar targets sin máscara aun con el modelo en train;
- `train_epoch()` y `evaluate_model()` fuerzan `apply_mask=False` para todos los targets, con y sin teacher;
- los contextos observados conservan masking en train;
- probabilidades fuera de `[0,1]` fallan cerrado.

Validación posterior: `13 passed in 1.99s` para tests Phys-TD/SMM+appender y `58 passed in 3.91s` para la suite focalizada completa (`C:\tmp\pytest-jepa-causal-20260710e`).

El siguiente arm válido queda predeclarado antes de lanzarse: mantener el control `modal` CPU existente y cambiar solo `mask_modal_prob: 0→0.15`, con `mask_temporal_prob=0`, seed `20260618`, mismo dataset/hash, hiperparámetros, OOF hasta `202605` y selector únicamente `202601..202605`. Se escribirá en destinos nuevos `v2`; no se reutilizarán los directorios v1 contaminados.

Runner reproducible: `run_smm_modal_mask_only_v2.ps1` (SHA-256 final prelaunch `4236E47E52F7D203847EC74B46089E7D649AE7821D4E5D50C7C6D25D72157BEC`). Verifica primero el hash del dataset, falla si las salidas ya existen y ejecuta extracción→join→selector. Hash del trainer corregido: `8196D9391AE32CE157C5162C5901E99BF346C79AFB7FCBF0EBFCD591973F8F03`; hash del appender: `DAAB0C1D9F6E42067D090996EBBB6CB256195177398FB45EBB3E496A8D8F2914`.

Un primer lanzamiento con timeout de shell de un segundo cerró el pipe de stdout antes de entrenar y provocó `OSError: [Errno 22] Invalid argument` al imprimir el primer fold omitido. Solo dejó `metadata.json` y `jepa_feature_names.json` en el directorio `..._v2/`; se preserva como fallo. El reintento reproducible usa destino nuevo `..._v2r1/`, mismos factores y hash de código, sin reutilizar ningún checkpoint.

## 11. Reanudación de 2026-07-11: contrato runtime en la comparación flat/modal

La auditoría de reanudación confirmó que los dos encoders originales terminaron completamente:

- 13 folds OOF por arm (`202505..202605`);
- 15 folds nested OOS por arm (`3 tickers × 202601..202605`);
- `policy_selection_provenance.json` con `passed=true` en ambos arms;
- junio no aparece en ningún fold OOF, de selección ni de evaluación.

Sin embargo, el downstream original no era equivalente al runtime actual. Tanto `flat` como `modal` usaron `cooldown_minutes=30` para los tres tickers y permitieron que el selector eligiera cupos `2/4/all`. El contrato obligatorio es:

| Ticker | Cupo diario | Cooldown |
| --- | ---: | ---: |
| SPXW | 4 | 0m |
| QQQ | 2 | 30m |
| SPY | 1 | 0m |

Por ello, las métricas agregadas publicadas previamente (`flat PF=0,860`, `modal PF=0,910`) quedan como diagnóstico histórico, no como comparación downstream runtime-equivalente.

Se generaron dos parquets derivados físicamente sellados en mayo, sin filas de junio:

```text
tmp/event_option_dataset_execquote_causal1030_202501_202605_v3_physics_flat_features_sealed_v1/event_option_dataset.parquet
SHA-256 65CCD607A77AF65C71469A74EF76D71F40B56E6BCDD3DEE408E673A5FA59ECEB

tmp/event_option_dataset_execquote_causal1030_202501_202605_v3_physics_modal_features_sealed_v1/event_option_dataset.parquet
SHA-256 FC99717F6C8B801C09C9F1B4F39FA1E9860505FDA2E112A9706746298CF0DD64
```

Ambos contienen 41.883 filas, 538 columnas, `option_price_mode=executable_quote`, fechas `20250102..20260529` y rejilla exacta `630..870` con anchor 600 y paso 5 minutos.

Se lanzó el selector flat en una salida nueva, con seed y presupuesto iguales y únicamente el contrato común corregido:

```text
research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_h1_3_6_12_causal_202501_202605_v1_walkforward_runtime_contract_v2/
```

Argumentos distintivos: `--start-month 202601 --end-month 202605`, `--ticker-cooldown-minutes SPXW=0 QQQ=30 SPY=0`, `--ticker-max-day-grids SPXW=4 QQQ=2 SPY=1`, `--lgb-device-type cpu`, `--seed 20260618`, `--no-resume`. PID observado: `8636`. El primer checkpoint guardó `SPXW/202601`; la corrida continúa activa y no debe duplicarse.

En paralelo se reconstruyó la comparación de representación original. La evidencia provisional —todavía pendiente de persistirse como artefacto versionado— no apoya avanzar a MJEPA intra/cross-modal: en los 15 bloques ticker×mes de enero–mayo, `modal` mejoró el ratio medio error/persistencia solo en 2/15 y nunca mejoró la tasa de observaciones que baten persistencia. La decisión final esperará al downstream runtime-equivalente y a un informe reproducible con hashes.

### Selector flat runtime-equivalente: completado

La primera envoltura cerró stdout después del primer fold, pero el checkpoint quedó íntegro. Se reanudó la misma ruta sin `--no-resume`, conservando `SPXW/202601` y calculando solo los 14 folds pendientes. Resultado verificado:

```text
15/15 folds seleccionados
policy_selection_provenance.passed = true
trades = 481
WR = 43,867%
PF = 0,8996
PnL = -15,094R
Max DD = -26,009R
min exit_minutes = 30
max evaluation month = 202605
```

| Ticker | Trades | WR | PF | PnL (R) | Min trades/mes | Meses positivos |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 166 | 46,386% | 1,000 | -0,010 | 28 | 60% |
| SPXW | 217 | 41,014% | 0,813 | -14,249 | 17 | 60% |
| SPY | 98 | 45,918% | 0,969 | -0,835 | 17 | 40% |

Flat queda rechazado: ningún ticker alcanza PF 1,3 y WR 50%; SPXW/SPY tampoco alcanzan 18 trades en su peor mes y no todos los meses son positivos.

El selector modal runtime-equivalente se lanzó después de cerrar flat, en salida nueva `...modal..._walkforward_runtime_contract_v2/`, con PID `38064` y exactamente los mismos argumentos/seed/backend. No debe duplicarse mientras siga activo.

## 12. Comparación flat vs modal runtime-equivalente: cerrada y modal rechazado

Modal terminó los 15 folds externos; 14 seleccionaron policy y `SPY/202601` produjo `ABSTAIN_NO_VALID_PROFILE`. La policy mensual combinada conserva provenance nested `passed=true`. El contrato fue validado sobre los trades: ask→bid `executable_quote`, hold mínimo observado 30m, rejilla 10:30–14:30/5m, cupos/cooldowns runtime, una posición por ticker, sin solapamientos y mes máximo `202605`.

Artefacto autocontenido y versionable:

```text
research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_vs_modal_runtime_contract_analysis_202601_202605_v2/
```

Hashes principales:

```text
summary.json                         EB1D233E3FD65FE3384ADAD736117CD48766E6A953E85489DACDAAB5017D1C5C
REPORT.md                            F7ACE4AA90594F6C7C06CEE7A216118B9303A1EB3157BA8A592FF97B106A4502
paired_tests.json                    2E58FA51C9E8739AA702EF4DD6B1B587A05FA4F62630C0F398D2D4A4C5EACAF9
downstream_metrics.csv               0471CC0EA1D1C89E71024F288892C2CA98C8E50285FB33ECB364F53FD1FED284
representation_ticker_month.csv      C1520F4F970217002D36594ABA163D0CD6CD5DC9C6E98B937B5FDF86C0177AA9
```

### Resultado downstream

| Arm | Trades | WR | PF | PnL (R) | Max DD | Celdas ticker×mes que pasan |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Flat | 481 | 43,867% | 0,900 | -15,094 | -26,009 | 1/15 |
| Modal | 491 | 42,974% | 0,858 | -21,989 | -31,039 | 0/15 |

| Arm/ticker | Trades | WR | PF | PnL (R) | Min trades/mes | Meses positivos |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Flat QQQ | 166 | 46,386% | 1,000 | -0,010 | 28 | 60% |
| Flat SPXW | 217 | 41,014% | 0,813 | -14,249 | 17 | 60% |
| Flat SPY | 98 | 45,918% | 0,969 | -0,835 | 17 | 40% |
| Modal QQQ | 184 | 43,478% | 0,828 | -9,946 | 29 | 0% |
| Modal SPXW | 228 | 42,544% | 0,822 | -12,724 | 32 | 40% |
| Modal SPY | 79 | 43,038% | 1,027 | +0,681 | 0 | 60% |

### Representación y evidencia pareada

- Modal reduce la loss de training en 12/13 folds (`p=0,000854`), pero no generaliza mejor.
- Ratio error de predicción/persistencia: modal mejora solo 2/15 celdas; mediana modal-flat `+0,1066`, `p=0,999237` en la dirección deseada.
- Tasa de observaciones que baten persistencia: modal mejora 0/15; mediana `-0,2023`, `p=1,0` en la dirección deseada.
- PF downstream: modal gana 7/15, mediana `-0,0278`, `p=0,834869`.
- PnL downstream: modal gana 7/15, mediana `-0,348R`, `p=0,640137`.
- Bootstrap diario modal-flat, seed `20260711`, 10.000 muestras: `-6,895R`, IC95% `[-31,537,+17,109]`, `P(diff>0)=0,2917`.

Dictamen: **no avanzar a objetivos MJEPA intra-modal/cross-modal**. Modal empeora representación OOF y downstream y no cumple ninguna celda ticker×mes. Las colas SMM parciales no deben reanudarse.

Validación final: `py_compile` PASS y `64 passed in 3.88s` en la suite focalizada completa. No se modificó systemd, no se promovió ninguna policy y junio no se abrió.

El siguiente experimento admisible debe volver al baseline flat y cambiar un solo factor. Dado el histórico 2022–2026 disponible, el primer paso futuro es auditar cobertura/hashes 2022–2024 y predeclarar una ablación `train desde 2022` frente a `train desde 2025`, con igual arquitectura, seeds y presupuesto, inner selection causal y evaluación enero–mayo de 2026. No ejecutar esa ablación hasta congelar el manifest y confirmar labels executable_quote reproducibles para todo el rango.

## 13. Inicio de la ablación de historia flat: auditoría ThetaData 2022–2026

Hardware disponible y contrato de cómputo:

```text
GPU: NVIDIA GeForce RTX 5070 Ti Laptop, 12.227 MiB VRAM
CPU: Ryzen 9, 32 hilos
RAM: 32 GB
```

CUDA y el paralelismo CPU se usarán de forma simétrica entre arms. En la auditoría inicial la GPU tenía unos 2,2 GB libres por procesos gráficos, por lo que antes de entrenar se exige un preflight de memoria; no se cambiará un solo arm a CPU por un OOM.

Se generó un manifest físicamente limitado a `20220101..20260531`:

```text
research_papers/JEPA/results/_diagnostics/thetadata_manifest_spxw_spy_qqq_202201_202605_sealed_v1/
rows = 6.425
complete_rows = 6.425
date_min = 20220103
date_max = 20260529
zero_dte rows = 3.116
duplicate zero_dte keys = 0
manifest SHA-256 = 88BE8A2FF44C18FB57FCA360D31DEF574DDBB0419A792FC88349942711D2974A
summary SHA-256 = 5075E530CC8BBDF5613028B42071EFBFF21DCB73F586735AC483640339A14B19
```

Sesiones 0DTE completas:

| Ticker | 2022 | 2023 | 2024 | 2025 | Ene–may 2026 |
| --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | 170 | 250 | 252 | 250 | 99 |
| SPXW | 220 | 250 | 252 | 250 | 102 |
| SPY | 170 | 250 | 252 | 250 | 99 |

Las menores cifras 0DTE de 2022 no son rutas incompletas: cada fila del manifest tiene Greeks, IV, OHLC, OI y spot, y existen 250 filas front-weekly por ticker ese año. Se tratará como cambio histórico del calendario de expiraciones, no se imputarán sesiones 0DTE inexistentes.

Runner predeclarado: `run_flat_history_dataset_build_v1.ps1`. Verifica hashes del manifest, builder y enhancer, falla ante salidas existentes salvo reanudación explícita, usa 24 workers conocidos como seguros para 32 GB RAM y replica exactamente el contrato causal previo: executable_quote ask→bid, trailing 50%/25%, stop 60%, TP 1000%, hold mínimo 30m, horizonte 180m, rejilla 10:30–14:30/5m, OI obligatorio y cutoff mayo 2026.

## 14. Dataset histórico construido y ablación flat-history congelada

El build terminó 159/159 chunks y produjo 108.156 filas `20220103..20260529`. Hash base `DED31E49D70EC2525194497994E26FD6A6DD4BF502F7775EA547826B0FB879BF`; hash physics `11E26AADDD91FD441222D552E0362C1D4C2C4489A08D7A6DE66479D6EB454FB1`. La vista común `202501..202605` contiene 36.796 filas y hash `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720`.

Auditoría independiente: 0 duplicados, 0 infinitos, 0 off-grid, solo `zero_dte`/`executable_quote`, 277 features live idénticas y junio ausente. Dos snapshots SPXW de `20220222` tienen PUT no observable porque ThetaData publica bid/ask cero para todos los strikes; se conservan con availability cero y el selector las excluye causalmente.

La ablación cambia solo el inicio físico del train flat (`202201` frente a `202501`). Ambos arms exportarán los mismos 13 folds `202505..202605`, con seed base `20260618`, seed independiente por fold, CUDA determinista, 8 épocas, batch 1024, horizontes `1/3/6/12` y nested selector runtime-equivalente `202601..202605`. Runner predeclarado `run_flat_history_ablation_v1.ps1`, hash `A8DC76553B0573E8594939A60A81AB80C50C64B3DB42510834320EE8EDA1F63D`. En el momento de congelar este contrato el entrenamiento aún no se había lanzado.

### Ejecución activa 2026-07-11 03:26 CEST

El primer PowerShell perdió su padre por timeout, pero el trainer control continuó y terminó sus 13 folds; no se duplicó ni se eliminó la salida. El runner se reanudó con `-Resume` mediante `-EncodedCommand` y logs persistentes en `tmp/`. PID padre `25112`; selector control PID `57784`. El control generó 29.046 filas OOF, join completo 29.046/29.046 y lleva 3/15 folds nested guardados. Tras completarlo, el mismo runner lanzará el arm 2022. No ejecutar otra instancia.

El control terminó 15/15 folds con provenance PASS: 495 trades, WR `45,05%`, PF `0,863`, `-20,174R`, DD `-27,180R`; QQQ PF `0,893`, SPXW `0,711`, SPY `1,336`. Solo abril fue positivo overall y SPY fue el único ticker agregado rentable, por lo que `history_2025` queda rechazado. El runner ya inició `history_2022` y conserva stderr vacío.

`history_2022` terminó después sus 13 folds OOF y el join 29.046/29.046 con las mismas seeds por mes. Su selector nested está activo en PID `37752`. Se añadió y subió el analizador `analyze_event_phys_td_history.py` (`507af59`), que valida el factor único, seeds, representación, contrato runtime, métricas ticker×mes, pruebas pareadas y bootstrap; no permite decidir por PnL agregado aislado.
