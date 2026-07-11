# CODEX-HANDOFF.md — Estado para continuación por otro agente

## Contrato de éxito y recursos — no rebajar

El objetivo de investigación es obtener una policy causal, reproducible y live-equivalente para **cada uno** de `SPXW`, `QQQ` y `SPY` 0DTE. Debe demostrar en walk-forward: `PF >= 1,3`, `WR >= 50%`, al menos `18 trades` en **cada mes**, `PnL > 0` en **todos** los meses evaluados y hold realizado mínimo `>= 30 minutos`. No basta PF/PnL agregado ni cumplir solo dos tickers. Junio de 2026 permanece sellado y no se modifica el paquete de producción mientras se investiga.

Datos históricos locales 2022–2026 disponibles para train/inner-validation causal:

```text
D:/ThetaData/data_options/SPXW
D:/ThetaData/data_options/QQQ
D:/ThetaData/data_options/SPY
D:/ThetaData/data_underlying_derived/SPXW
D:/ThetaData/data_underlying_derived/QQQ
D:/ThetaData/data_underlying_derived/SPY
```

Hardware local: RTX 5070 Ti con 12 GB VRAM, Ryzen 9 con 32 hilos y 32 GB RAM. Usar CUDA determinista y batches ajustados a VRAM para entrenamiento/inferencia; paralelizar carga y transformaciones CPU sin crear corridas duplicadas.

### Ratificación del contrato por el usuario — aplicar en todo train/selección/evaluación

Las gates son **individuales y simultáneas** para cada ticker; un agregado rentable no compensa el fallo de otro ticker ni de un mes:

| Ticker | Hold de cada trade | PF walk-forward | WR walk-forward | Frecuencia | Estabilidad mensual |
| --- | ---: | ---: | ---: | ---: | --- |
| SPXW | `>=30m` | `>=1,3` | `>=50%` | `>=18 trades` en cada mes | `PnL > 0` en todos los meses evaluados |
| QQQ | `>=30m` | `>=1,3` | `>=50%` | `>=18 trades` en cada mes | `PnL > 0` en todos los meses evaluados |
| SPY | `>=30m` | `>=1,3` | `>=50%` | `>=18 trades` en cada mes | `PnL > 0` en todos los meses evaluados |

Para construir datasets, entrenar y evaluar hay opciones y spot 2022–2026 en `D:/ThetaData/data_options` y `D:/ThetaData/data_underlying_derived`. Mantener splits temporales causales: disponer de 2026 en disco no permite usar el mes externo para elegir features, mecanismos, thresholds o policies.

Cadencia confirmada en código: el live **recopila snapshots cada minuto** (`DEFAULT_POLL_INTERVAL_SECONDS=60` y `ml_features_1m_*`). La policy actual decide en rejilla de 5m (`MODEL_SAMPLE_MINUTES=5`, `entry_sample_minutes=5`). El dataset 1m ya fue creado y auditado en la iteración anterior; no reconstruirlo ni confundir adquisición 1m con decisiones 5m.

## Checkpoint cerrado — directional nested 1m ejecutado y rechazado

- Corrida única 117,9 s, `24 passed`, auditorías y provenance PASS; reutilizó el parquet 1m de 80.964 filas, sin build ni junio.
- Solo enero tuvo policies inner válidas. SPXW d25-win/model: 20 trades, WR `40%`, PF `1,220`, `+1,700R`. QQQ d35-return/model: 20, WR `30%`, PF `0,987`, `-0,103R`. SPY d35-win/spot5-trend: 20, WR `40%`, PF `0,721`, `-2,169R`.
- Febrero–mayo abstienen los tres: al incorporar enero al inner, ninguna combinación cumple gates. Overall 60 trades, WR `36,67%`, PF `0,976`, `-0,572R`; hold mínimo 30m.
- No rescatar SPXW d25-return/spot5-counter aunque también pasara inner oct–dic: perdió la selección antes de enero. Elegirlo ahora sería OOS tuning.
- La dirección spot 5m/15m simple no estabiliza el edge; frecuencia tampoco es el límite. No barrer signos/horizontes sobre estos meses.
- Informe `.../early_causal_directional_nested_1m_202601_202605_seed20260618_v1/REPORT.md`; audit SHA `740A3305...D821`.
- La corrección de provenance conserva cronología de folds abstain y no cambió trades/PnL. Próximo trabajo: hipótesis económica distinta o cobertura full-session causal 1m, predeclarada; producción intacta.

## Actualización 2026-07-11 — Pairwise V1: preflight final implementado, todavía no ejecutado

- **Dataset sellado (2022-2025):** Parquet generado en `tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet` con 97,625 filas. La lectura excluye 2026 (SHA-256: `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`).
- **Feature Allowlist Definitiva (30 features):** Excluidos `dte_days`, `spot` y `underlying_volume`. Excluidos cambios de OI (`oi_diff_chg_*`). Las diferencias CALL-PUT y sus lags a 5m/15m/25m se calculan con ordenación de minutos y shifts agrupados por `(ticker, trade_date, bucket)` para prevenir leakage. Feature Hash único: `fa2057653ed0327b7f84a165c25f6e6d31e31b3b05c5591593e9c0bd3056d50e`.
- **C0 Redefinido:** Baseline in-protocol absoluto entrenado nested por fold. Heads de `call_win_label = int(call_return > 0)` y `put_win_label = int(put_return > 0)`. Evalúa con grid idéntica a P1 (`trade_threshold = 0.1..0.9`, `side_margin = 0.0..0.30`) y la misma política (`trade_score = max(p_call, p_put)`, `side_gap = abs(p_call - p_put)`).
- **LightGBM & Seeds Completados:** Congelados todos los parámetros (`deterministic=True`, `force_col_wise=True`, `verbose=-1`, `subsample=0.8`, `subsample_freq=1`). Semillas deterministicas calculadas sin `hash()` por base + offset (`+1` C0 CALL, `+2` C0 PUT, `+3` P1 OPP, `+4` P1 SIDE).
- **Preflight corregido:** `run_pairwise_opportunity_side_v1.ps1` exige exactamente un modo explícito (`-PreflightOnly` o `-Execute`), separa outputs, exige commit tracked limpio y `HEAD == origin/main`, bloquea si existe el output real y recalcula todos los hashes. `-PreflightOnly` retorna antes de `run_fold`, declara `models_trained=0` y `full_run_executed=false`.
- **Métricas científicas corregidas antes de entrenar:** C0 usa `p_call_win-p_put_win`; P1 usa `2*p_call-1`. Accuracy, balanced accuracy, ROC-AUC y Spearman comparten una máscara outer finita e independiente de policy. Las celdas `SCIENTIFIC_CELL_DEGENERATE` permanecen en el denominador fijo de 99 y cuentan como no favorables.
- **Tests reales:** `27 passed` en el checkpoint previo al commit, incluidos dry-run que falla si se llama a training, modo explícito, paths separados, hash de features, máscara común, celdas degeneradas, independencia model/policy, minuto 635 y LR sin trades. `py_compile`, parser PowerShell y `git diff --check` pasan.
- **Cómputo:** los 99 folds científicos se ejecutan secuencialmente; cada LightGBM usa 28 hilos del Ryzen. Esto aprovecha el Ryzen de 32 hilos sin cambiar la hipótesis. La RTX no se fuerza porque este LightGBM tabular pequeño ya mostró menor coste en CPU y el backend GPU no forma parte del protocolo congelado.
- **Estado honesto en este checkpoint:** el preflight final aún no se ha ejecutado desde commit limpio y la corrida completa tampoco. Los hashes antiguos `cacf...`/`448c...` son provisionales; el manifiesto generado por el próximo `-PreflightOnly` será la autoridad.
- **Autorización posterior del usuario:** tras cerrar/pushear el preflight, ejecutar el protocolo pairwise congelado y diagnosticar el resultado económico. No abrir 2026, no tocar producción y no diseñar otra arquitectura antes de leer esta prueba.

### Resultado ejecutado — REJECTED, no retunar V1

- Preflight autoritativo en commit limpio `0d420fca54885f1b215ff4efec5e65bfe1aa8fab`: PASS, dataset 97.625 filas `20220103..20251231`, 27 tests, 0 modelos, output real ausente. Evidencia publicada después en `e8b6e8f`.
- `-Execute` terminó una sola vez en 346,5 s usando 28 hilos LightGBM, 99/99 celdas y exit code 0; stderr contiene únicamente FutureWarning de la Logistic diagnóstica. No hubo GPU/fallback/proceso duplicado.
- Ciencia: 99 válidas, 0 degeneradas. P1 gana balanced accuracy en 57/99 (`57,58%`, requerido >=60%), mediana delta `+0,0040`, Wilcoxon `p=0,1171`; Spearman P1 positivo en 58/99 (`58,59%`), mediana `+0,0303`. Median delta anual sí es positiva en 2023/24/25, pero el gate conjunto falla.
- Por ticker, mediana delta BA P1−C0: QQQ `-0,0091`, SPXW `+0,0053`, SPY `+0,0104`; mediana BA P1 `0,492/0,506/0,518`. La elección de lado sigue prácticamente al azar y empeora QQQ.
- Economía: C0 `0/99` y P1 `0/99` configs inner válidas; ambos abstienen en todos los outer. Trades `0`, pooled PF `undefined`, no `infinity`. Esto no es rentabilidad cero: es inanición total de selección.
- Diagnóstico no causal posterior: always-CALL/PUT y momentum/contrarian 30m son negativos en los tres años/tickers, mientras oracle-side alcanza PF `4,55..11,73`, WR `73,5..86,7%`, mínimo mensual >=19 y todos los meses positivos. Hay headroom grande, pero las 30 features/labels de V1 no extraen la dirección.
- Próximo paso no es otra arquitectura: auditar las 63 configs inner de cada fold y descomponer qué gate falla; después predeclarar como único factor un objetivo de lado alineado con magnitud económica (regresión directa de `side_advantage` frente a clasificación binaria), conservando oportunidad, features, folds y scheduler. V1 no debe retunarse.

## Actualización 2026-07-11 15:45 CEST — Regime Gate Ablation V1 reproducible y auditado; C0 internal equivalence PASS

- Auditoría de reproducibilidad finalizada en 10 s; test PASS; paridad del control C0 confirmada.
- **C0 internal equivalence: PASS**. Se corrió un replay exacto de C0 (sin gates de régimen) bajo idénticos parámetros y allowlists. La coincidencia trade-a-trade y mes-a-mes es absoluta (trades hash normalizado: `9a59c1f7...7ab` en ambos casos). Esto confirma equivalencia interna pero no necesariamente paridad histórica con el broad-profile legacy debido a diferencias metodológicas previas.
- **Resolución de thresholds: MATCH**. El threshold de `0.015249997` no fue serializado ni aplicado en R1 QQQ 202602. La reconstrucción matemática sobre los datos de entrenamiento filtrados por disponibilidad de contratos e outcomes finitos (`finite_labels & observable`) arroja exactamente `0.012700021`, coincidiendo al 100% con la lógica del selector in-memory de V1. Todos los folds no abstencionistas audited se clasifican como `THRESHOLD_MATCH`.
- **Serialización corregida**: Se actualizó `freeze_fold_policy_artifact` para persistir los metadatos completos de `regime_gate` (feature, direction, quantile, threshold), el commit hash de git y el hash del dataset en `fold_policy.json`. Se escribieron unit tests para validar esta persistencia, cutoffs temporales de IB Range (R4: exclusión de `minute <= 630`), y filtrado de candidatos substitution.
- **Métricas de Scheduler Contrafactual**: Para QQQ 202602 R1, el scheduler ejecutó 21 trades admitidos (PF `1.444`, PnL `+2.956R`, WR `60.9%`) y rechazó 1 trade (PF `infinito/no definido por ausencia de pérdidas` debido a un solo trade ganador, PnL `+0.596R`). Esto valida que el scheduler no sufrió fugas causales.
- **Dictamen**: Se ratifica el estado exploratorio de R1. Al no alcanzar el mínimo de 18 trades mensuales requeridos por el contrato para todos los meses y tickers evaluados, **ninguna política cumple el contrato de producción**.
- **Acción metodológica**: Se archivan los resultados de la auditoría en `research_papers/JEPA/results/_diagnostics/regime_gate_ablation_v1_reproducibility_audit/` con el manifiesto `audit_manifest.json` y la tabla completa de 75 folds (`all_75_folds.csv`). Se versionan los scripts y tests con commit determinista.

## Actualización 2026-07-11 14:15 CEST — rentabilidad static-union atribuida a selección 2026

- Auditoría inversa terminó en 8,8 s, test PASS, tres modelos 28 hilos, solo train ene–sep2025 y audit oct–dic2025.
- QQQ: 75 trades, WR `41,33%`, PF `1,158`, min21, 2/3 meses positivos. SPXW: 64, WR `43,75%`, PF `1,686`, min19, 2/3 positivos. SPY: 125, WR `34,40%`, PF `0,794`, min26, 0/3 positivos.
- Diciembre: QQQ PF `0,664`/WR `23,81%`; SPXW PF `0,712`/WR `40,91%`. SPY pierde los tres meses. Volumen no es el problema.
- Conclusión: los filtros/thresholds seleccionados en 2026 no eran estables pre-2026. No tratar las métricas productivas 2026 como OOS del nuevo objetivo.
- Informe `.../pre2026_frozen_static_mechanism_reverse_audit_202510_202512_v1/REPORT.md`; audit SHA `4A3C950E...ABC53`.
- Siguiente trabajo: selección verdaderamente nested de mecanismos económicos en ventanas anteriores, seguida de meses posteriores no usados. No retocar reglas para diciembre ni volver a arquitecturas.

## Actualización 2026-07-11 14:05 CEST — baseline rentable no es OOS de selección; auditoría pre-2026 preparada

- Metadata confirma: modelos frozen entrenan `202501..202512`, pero thresholds y reglas static-union declaran selección `202601..202606`. Sus PF/WR fuertes son in-sample de selección para esas reglas, no holdout causal.
- Solo existe un dataset 1m local: el creado en la prueba anterior. Reutilizables exactos: early5m y causal1030 5m; no reconstruir.
- Predeclarada auditoría inversa barata: entrenar componentes enero–septiembre2025 y aplicar literalmente reglas actuales a octubre–diciembre2025. No usa 2026, pero tampoco borra el hindsight con que se eligieron las reglas; PASS sería estabilidad, no promoción.
- Script `audit_pre2026_frozen_static_mechanism.py`, runner `run_pre2026_frozen_static_mechanism_audit_v1.ps1`, predeclaración `PRE2026_FROZEN_STATIC_MECHANISM_REVERSE_AUDIT_V1.md`; `9 passed`, compile/parse PASS.
- Siguiente: commit/push antes de ejecutar una sola instancia. No tocar producción.

## Actualización 2026-07-11 13:45 CEST — 1m terminado y rechazado; no faltaban candidatos

- Corrida única completa, 30 tests, 159 chunks, auditor de paridad y causal PASS, sin stderr/procesos residuales.
- Dataset 1m: 80.964 filas; añade 62.280 filas y reproduce exactamente las 18.684 comunes/239 columnas base (`max diff=0`). No es duplicado de `clean1000`.
- Resultado: SPXW 1/5 folds, 20 trades, WR `40%`, PF `1,220`, `+1,700R`, min mes 0; QQQ/SPY 0/5 y 0 trades. Rechazado, junio/live intactos.
- Causa: inestabilidad, no volumen. SPXW valida oct–dic con PF `2,535`, WR `56,45%`, 62 trades y todos meses positivos, pero enero OOS cae a PF `1,220`/WR `40%`; al entrar enero en inner, deja de haber policy. QQQ/SPY nunca pasan las gates inner.
- El control 5m fue mejor en cobertura (2 folds/39 trades SPXW), aunque también inválido. No barrer 2m/3m/4m ni minutos OOS.
- Informe `.../early_causal_noib_d25_win_1m_202601_202605_seed20260618_v2/REPORT.md`; base SHA `66018CEE...CBD6`, physics `804BF0CC...CBE9`.
- Bug solo diagnóstico localizado: empates float en `-1e18` dejaban vacía la métrica del mejor candidato inválido. Fix `(score,trades)` + test después de la corrida; no cambia selección/trades y no autoriza relanzar primary.
- Antes del siguiente build, buscar cualquier parquet `bar_minutes=1` existente por metadata. El siguiente mecanismo no debe ser otra cadencia; estudiar cobertura de sesión/bucket solo con selección inner predeclarada, sin usar OOS para escoger.

## Actualización 2026-07-11 13:20 CEST — ablación de cadencia 1m predeclarada, no ejecutada

- No se encontró ningún dataset early executable 1m reutilizable. Solo existen el base/physics 5m creados en esta sesión y los `clean1000/dense15` legacy ya descartados como equivalentes.
- Nuevo arm cambia solo `bar_minutes 5→1` en 10:00–10:25. Mantiene d25-win, quotes/exits, allowlist sin IB, caps/cooldowns, folds, thresholds, seed y gates.
- Auditor pareado nuevo exige antes de entrenar que el subconjunto 1m en minutos múltiplos de cinco sea idéntico al control base; auditor causal ahora parametriza y verifica la cadencia declarada.
- Predeclaración `EARLY_CAUSAL_CADENCE_1M_PREDECLARATION_V2.md`; runner `run_early_causal_noib_d25_win_1m_v2.ps1`; `9 passed`, compile/parse PASS. Hash runner `288BBF08...B87D`.
- Próximo: commit/push **antes** de lanzar, comprobar que outputs no existen y ejecutar una sola instancia. Producción y junio siguen intactos.

## Actualización 2026-07-11 13:05 CEST — feed 1m, policy 5m; control early terminado y rechazado

- **No confundir cadencias:** `services/realtime_feed.py` consulta cada 60 s y el bot itera cada ~65 s. Hay snapshots minuto a minuto. Sin embargo, el contrato productivo vigente filtra entradas con `candidate_universe_filter.entry_sample_minutes=5` y el feed declara `MODEL_SAMPLE_MINUTES=5`. Por eso el build early usó 5m: reproduce la rejilla de decisiones de la policy actual, no la frecuencia de adquisición.
- No asumir que "live minuto a minuto" implica que la policy puntúa entradas cada minuto. Si se investiga una policy 1m, debe ser un arm nuevo, predeclarado y comparado contra este control 5m; no cambiar producción silenciosamente.
- El dataset nuevo **no duplica** los `clean_live1000` de ayer. Esos resultados apuntan a `...zero_dte_dense15...` de 2025–2026, conservan labels/salidas legacy y el IB diario completo. El nuevo parquet tiene 18.684 filas, 2022–mayo2026, 10:00–10:25, `near_level_only=false`, entrada ask/salida bid, trailing 50%/25%, stop -60%, TP 1000%, hold 30–180m y allowlist sin IB/Fib/nearest. SHA dataset `5E916EFA...BBEF49`. No reconstruirlo otra vez.
- El control 5m terminó y queda rechazado: SPXW seleccionó solo enero/febrero (39 trades totales, WR `43,59%`, PF `1,109`, `+1,394R`, min mensual 0, 20% meses positivos); QQQ y SPY abstuvieron `5/5`. `production_live_ready=false`, junio sellado, producción intacta.
- Artefacto pequeño: `research_papers/JEPA/results/_diagnostics/early_causal_noib_d25_win_202601_202605_seed20260618_v1/`; hashes metrics/selected/trades `3E8A6348...E2BA9` / `A02B3CB7...310CB` / `9EA5BE00...CC74`.
- Siguiente prueba admisible por la corrección del usuario: aislar **cadencia de candidatos 5m→1m** sobre el mismo contrato early prefix-only. Debe construir/reutilizar todos los minutos 10:00–10:25, mantener labels/features/modelo/gates y comparar selección OOS. No reutilizar resultados `clean1000` como si fueran este control exacto.

## Actualización 2026-07-11 12:50 CEST — early causal no-IB listo para construir/ejecutar

- Predeclarado un único test del mecanismo temprano: d25 win por ticker, 10:00–10:25, ask→bid/hold30, sin backfill/guard/otros deltas.
- Dataset nuevo desde ThetaData 2022–mayo2026: `near_level_only=false`; el modelo excluye por contrato todas las columnas IB/Fib/nearest/context-IB y outcomes. Así no reutiliza el leakage que explicó el legacy.
- Auditor nuevo verifica ventana, hash, executable quotes, allowlist live, meses y hold/gates finales. Runner usa 24 workers en build y 28 hilos LightGBM.
- Predeclaración `EARLY_CAUSAL_NOIB_D25_WIN_PREDECLARATION_V1.md`; hashes completos congelados; `27 passed`, compile y parse PASS.
- Próximo: commit/push, reauditar procesos/outputs y lanzar una sola instancia. No tocar snapshot/live aunque el arm pase; cualquier integración sería shadow posterior.

## Actualización 2026-07-11 12:35 CEST — objetivo cerrado; edge legacy era pre-10:30 y no causal

- Una sola ejecución completó 30 folds de entrenamiento en ~2 minutos usando 28 hilos. El analizador falló después por `NaN` en folds abstain; fix + test, sin relanzar modelos.
- Return: `0/15` folds seleccionados. Win: SPXW/QQQ `0/10`; SPY solo `2/5`, con 42 OOS trades, WR `28,57%`, PF `0,602`, `-6,167R`, meses no operados y hold mínimo 30m. Ambos arms rechazados.
- Causa localizada mediante traducción del stream dense15 legacy: 233/305 trades Jan-May entraban antes de 10:30. Esa franja produjo legacy `+14,7R/+14,4R/+11,4R` en QQQ/SPXW/SPY; después de 10:30 los tres fueron negativos (`-1,2/-0,9/-1,1R`) incluso con labels favorables.
- El edge temprano no es promocionable: `build_event_option_dataset._session_levels` usa IB 09:30–10:30 completo, `near_level_only` selecciona con esos niveles y live snapshot rehúsa construir hasta completar IB. Usarlo a 10:00 filtra 30m futuros.
- Próxima corrección: dataset separado 10:00–10:25 con `near_level_only=false` y allowlist que excluya todo IB/Fib/nearest-level/context-IB. Primero demostrar que las filas/features son prefix-only; después GBT win exacto. No tocar snapshot/live ni producción.

## Actualización 2026-07-11 12:20 CEST — objetivo exacto return vs win listo

- Se aisló el primer mecanismo, no arquitectura: mismo GBT/features/filas/bucket/selector, cambiando solo regresión de retorno ejecutable frente a probabilidad de win.
- Datos exactos 2022–2025 para train, tres meses inner y test `202601..202605`; buckets SPXW d25 y QQQ/SPY d35; caps/cooldowns `4/2/1` y `0/30/0`; gates completas y junio sellado.
- El selector admite ahora `--profile-allowlist` exacta para evitar la confusión de escoger entre 24 perfiles. Analizador verifica cronología, hold>=30m y gates por ticker/mes.
- Predeclaración `EXACT_OBJECTIVE_RETURN_VS_WIN_PREDECLARATION_V1.md`; hashes selector/analyzer/test/runner `95279496...C2AA` / `47FDEDAC...FB75` / `EA4F3A99...E3B3` / `14818994...F010`; `27 passed`, compile/parse PASS.
- Runner usa 28 hilos Ryzen para LightGBM (medición previa: OpenCL era más lento). Próximo paso: commit/push, comprobar que no hay procesos ni output y ejecutar una sola instancia bajo `pwsh`.

## Actualización 2026-07-11 12:10 CEST — spot skip rechazado; pivot a mecanismo rentable

- La corrida que quedó activa antes de la interrupción terminó correctamente: `11 passed`, CUDA determinista, cinco folds y sin procesos residuales.
- Control y spot skip: `0/210` candidatos válidos, `15/15` abstain y `0` trades OOS. Spot gana solo `5/15` MAE, `1/15` RMSE y `8/15` accuracy; medianas `+0,002683/+0,016080/+0,004266`, sin evidencia favorable.
- No probar más arquitecturas o bloques por tanteo. El fallo económico no es falta de candidatos: QQQ/SPXW suelen superar volumen, pero fallan PF/WR/persistencia; SPY además roza el mínimo.
- Pista recuperada del histórico: la familia dense15/GBT + d25/d50 backfill + guard causal sí alcanzó las gates observadas en una ventana anterior, pero su evidencia legacy no es promocionable por labels simplificados, solapes/lineage y falta de equivalencia executable-quote. El trabajo correcto es reconstruir y descomponer ese mecanismo sobre datos exactos 2022–2025, no inventar otra arquitectura.
- Informe: `.../phys_td_spot_skip_202601_202605_seed20260618_v1/REPORT.md`. Próximo paso: congelar una ablación de mecanismo `return head exacto` vs `win-probability exacta`, manteniendo universo/bucket/selector, y después aislar backfill/guard solo si el objetivo recupera señal inner-OOS.

## Actualización 2026-07-11 07:45 CEST — spot skip listo para ejecutar

- Auditoría sin labels/outcomes: `ret_5m_bps/ret_15m_bps/ret_30m_bps` son backward-looking (`minute <= current-lookback`), 36.796/36.796 finitas, variables, incluidas en los 277 features y reproducibles live.
- Nuevo `walkforward_phys_td_spot_skip.py`: control z+h1 vs mismo frame/head más bloque directo 5/15/30m. Un solo factor; no skew/flow/levels/cross/h6/Ada/loss.
- Predeclaración `PHYS_TD_SPOT_SKIP_PREDECLARATION_V1.md`; script/test/runner hashes `EC4B6837...06B9` / `00A28EBD...C6A` / `3DCE5DAD...E173`; `11 passed`.
- Próximo paso: commit/push, verificar procesos/GPU/output y lanzar una sola instancia de `run_phys_td_spot_skip_v1.ps1` bajo `pwsh`, no Windows PowerShell. No cambiar bloque/gates según resultados.

## Actualización 2026-07-11 07:30 CEST — h6 cerrado y rechazado

- Ejecución real `pwsh` completó 5/5 folds h1+h6. El intento previo `powershell.exe` falló en preflight antes de outputs (`Get-FileHash`/Unicode), no duplicó experimento. No quedan procesos.
- Paridad de inputs perfecta: filas 20.361/21.470/22.850/24.403/26.038, max diff z/h1 `0/0`; provenance/runtime PASS, junio sellado.
- Resultado: h1 0/210 y h6 0/210 candidates válidos; 15/15 abstain cada arm; 0 OOS trades. h6 MAE/RMSE/accuracy wins `7/6/5` de 15, medianas `+0,011543/+0,009697/-0,018998`; claramente no mejora.
- SPY h6 near-miss: fold202602 falla PF (`1,119`); fold202603 falla min mensual (`17`). No combinar ni retunar. No h3/h12/multi/Ada-h6.
- Report `.../phys_td_h1_vs_h6_downstream_202601_202605_seed20260618_v1/REPORT.md`; summary/horizon manifest `44003060...D632` / `F21336B1...1BDE`.
- Próximo paso: publicar solo metadata/grids/histories pequeños, excluir 5 parquets horizon + 10 `.pt`. Después auditar nombres/semántica de las 277 features live para predefinir un skip direccional pequeño; no correlacionar contra test ni feature mining.

## Actualización 2026-07-11 07:15 CEST — h1 vs h6 listo para ejecutar

- Implementados `export_event_phys_td_current_horizons.py` y `walkforward_phys_td_horizon_downstream.py`, tests y runner. Factor único: reemplazar motion h1=5m por h6=30m; mismo z, filas h1, labels, head, folds, seeds, presupuesto y gates.
- Export h6 es current-time y no usa target futuro. Downstream obliga paridad z/h1 <=1e-6 antes de entrenar. Smoke enero: 1.684 rows current, 1.608 h1 join, diferencias `0/0`.
- Predeclaración `PHYS_TD_H1_VS_H6_PREDECLARATION_V1.md`; hashes exporter/downstream/runner `884E743E...5BAF` / `0ECFEA37...7F52` / `559CEFB8...D061`; `13 passed`, compile/parse PASS.
- Runner usa RTX 5070 Ti/CUDA determinista para export y diez heads; Ryzen 16 threads para carga. Output nuevo `phys_td_current_h1_h6_features...` + `phys_td_h1_vs_h6_downstream...`; no existen aún.
- Siguiente paso: commit/push, comprobar procesos/GPU y lanzar una sola instancia de `run_phys_td_h1_vs_h6_v1.ps1`. No variar hashes/gates, no h3/h12, no Ada, no abrir junio ni tocar live/systemd.

## Actualización 2026-07-11 07:00 CEST — separabilidad cerrada; siguiente factor h6

- Runner terminó una sola vez en 6,7 s; no quedan procesos. Inputs/checkpoints/hash/junio PASS. Salida `.../adajepa_payoff_separability_202601_202605_v1/`.
- Frozen/adapted: side wins vs constante `7/15` y `8/15`; medianas Δ `-0,01349/+0,01877`. Score-retorno positivo `7/15` y `9/15`; medianas `-0,00684/+0,01505`. Fallan ambas reglas predeclaradas; no probar ranking/calibration loss.
- Por ticker adapted sigue negativo: PF medio QQQ/SPXW/SPY `0,813/0,828/0,891`, WR `41,02%/39,18%/43,72%`. Oracle no causal es fuerte y 71,95% de eventos tienen un solo side positivo: label headroom no equivale a predictibilidad.
- Report `.../REPORT.md`; hashes summary/cells/manifest `984EFF37...A21B` / `A6EA9C62...8F4E` / `31CDEA81...A06`.
- Mecanismo nuevo: downstream solo recibe motion h1=5m para holds 30–180m. Checkpoints flat contienen `horizons=[1,3,6,12]`; h6 alinea exactamente con mínimo 30m.
- Primer paso pendiente: publicar cierre; después implementar/exportar predicción h6 sobre exactamente las mismas filas h1 y predeclarar h1 vs h6 con mismo z/head/folds/seeds/budget/gates. No incluir adapter, no probar h3/h12, no abrir junio ni tocar live/systemd.

## Actualización 2026-07-11 06:50 CEST — separabilidad payoff lista para ejecutar

- Nuevo analizador `analyze_adajepa_payoff_separability.py`: carga/verifica los diez checkpoints downstream y mide side, baseline constante train-only, oracle-side, regret y score-retorno en test `202601..202605`; no selecciona policy.
- Predeclaración `ADAJEPA_PAYOFF_SEPARABILITY_PREDECLARATION_V1.md`; script SHA `B2B8CB0C...A1C3`, test SHA `60C27B4E...436A`, runner SHA `4638FB1E...A708`; `7 passed`, compile/parse PASS.
- Fast adapter float32 tiene paridad con Torch. Se usa CPU/16 hilos porque esta secuencia de operaciones de 32 dimensiones sufría overhead de kernels diminutos en GPU; entrenamientos futuros seguirán usando la RTX 5070 Ti.
- Gates diagnósticas congeladas: side head > constante en >=10/15; event score Spearman positivo en >=10/15 y mediana >0,10. Solo su patrón decide qué objetivo aislado podría probarse después.
- Próximo paso exacto: commit/push de esta predeclaración, reauditar procesos y ejecutar una única instancia de `run_adajepa_payoff_separability_v1.ps1`. No cambiar métricas/reglas después de leer resultados y no relanzar el downstream.

## Actualización 2026-07-11 06:40 CEST — AdaJEPA downstream cerrado y rechazado

- `run_adajepa_downstream_v1.ps1` terminó una sola instancia, 5/5 folds frozen y 5/5 adapted (~675 s). No queda Python/CUDA/pytest activo; no relanzar.
- Contrato íntegro: fuente SHA `AB144DBA...F720`, manifest `F398B110...F7B8`, exact d25/d35, ask→bid, hold>=30m, caps/cooldowns `4/2/1` y `0/30/0`, seeds `20463219..20463223`, CUDA determinista y junio sellado. Provenance/runtime PASS en ambos arms.
- Resultado económico: 0/210 candidatos válidos por arm, 15/15 policies `ABSTAIN_NO_VALID_THRESHOLD` por arm y 0 trades OOS. No interpretar el cero como rentabilidad. `adapted_meets_full_ticker_gate=false`, `production_live_ready=false`.
- Diagnóstico: adapted mejora MAE 13/15 (mediana `-0,005331`, `p=0,006226`) y directional accuracy 10/15, pero RMSE solo 7/15 (mediana `+0,003113`, `p=0,680664`). No hay traducción estable a payoff/policy.
- Informe `research_papers/JEPA/results/_diagnostics/adajepa_downstream_frozen_vs_adapted_202601_202605_v1/REPORT.md`; summary SHA `9B7007DA7C25469FFF1971487D91E9435D7694475501D130F0753C00FD41BC0D`. Candidate grids frozen/adapted SHA `B3F43A30...D0F4` / `9118579D...813`.
- Bug solo diagnóstico: los empates inválidos `-1e18` podían dejar métricas vacías en `selected_folds.csv`; candidate grid era correcto. Se añadió `best_seen` y test (`12 passed`), sin reentrenar ni alterar policies/trades.
- No reabrir modal/MJEPA/SMM, historia 2022, Var, PatchCore ni retunar AdaJEPA. El primer paso real es una auditoría no selectiva de separabilidad/oracle sobre labels exactos y descomponer error de side CALL/PUT frente a calibración/colas. Después, y solo con un mecanismo identificado, predeclarar una ablación de un factor del objetivo del payoff head con todo lo demás congelado.

## Actualización 2026-07-11 06:25 CEST — downstream AdaJEPA listo para lanzar

- Nuevo `walkforward_adajepa_downstream.py`: reusa trainer/selector/provenance Var auditado; control `z+frozen_dz`, variante `z+adapted_dz`, mismas 79 features estructurales/contrato, filas y labels.
- Export live allowlist contiene solo current-time z/dz/estado adapter; test cambia target futuro y prueba invariancia de features anteriores. No target/error/outcome en model features.
- Exact d25/d35, 30m, una posición, caps/cooldowns runtime, strict inner gates, folds/seeds/40epochs/batch512 simétricos.
- Predeclaración `ADAJEPA_DOWNSTREAM_PREDECLARATION_V1.md`; runner SHA `27180A2B70EE516F62A036D48119A17EAD29172C58419FEAB15C6D39B00E6EF5`; tests `11 passed`.
- Próximo paso: commit/push y ejecutar una sola instancia. No cambiar LR/head/gates según resultado.

## Actualización 2026-07-11 06:10 CEST — AdaJEPA shadow pasa representación

- 7.285 filas OOS, 281 ticker-días, 15 celdas. Adapter gana 15/15, mediana RMSE diff `-0,0021206`, Wilcoxon `p=3,0518e-05`; 277/281 días, mediana `-0,0023479`, `p=9,1398e-48`.
- QQQ/SPXW/SPY daily wins `88/90`, `96/97`, `93/94`. 0 rollbacks, norma máxima `0,0212977`, reset diario/orden causal PASS.
- Resultado en `.../adajepa_shadow_adapter_202601_202605_lr005_v1/`; summary SHA `60F9DE6BD629974C8FDCB1282EA41259ABF68818E3FE3A3F48CD8056F4FB16DD`.
- Decisión: `advance_to_separate_downstream_ablation=true`, pero `production_live_ready=false`. Próximo paso: exportar features current-time frozen/adapted (nunca target_z) y comparar el mismo payoff head exacto d25/d35 con mismos folds/seeds/presupuesto.

## Actualización 2026-07-11 06:00 CEST — AdaJEPA shadow listo para lanzar

- Evaluador `evaluate_adajepa_shadow_adapter.py`: control pred_z frozen vs adapter diagonal 64 params; init cero/reset ticker-día; update de transición anterior solo cuando target ya observable; LR.05, 1 paso, clip1, norm cap.5/rollback.
- Tests causales: cambiar target futuro no cambia predicciones anteriores; primera predicción diaria siempre 0 updates/norma0; junio bloqueado por capa anterior. Suite combinada `19 passed`.
- Predeclaración `research_papers/JEPA/ADAJEPA_SHADOW_ADAPTER_PREDECLARATION_V1.md`; runner SHA `5EA632B8AF4089B80F6FA4AE56D2F5F5F431722AF5FC07800368D80E3B701736`.
- Próximo paso: commit/push código/test/runner/predeclaración, comprobar procesos y ejecutar una sola instancia. No variar LR/norma tras resultados y no ejecutar downstream salvo gate representacional.

## Actualización 2026-07-11 05:45 CEST — exportador frozen-space listo

- `walkforward_event_phys_td_jepa_oof.py` ahora expone `export_observed_transition_features`: emite `z_t`, `pred_z_*`, `target_z_*`, timestamp actual/target y disponibilidad explícita, solo sobre contextos contiguos dentro de sesión.
- Nuevo CLI `neural/jepa/export_event_phys_td_shadow_transitions.py`: carga checkpoint exportado, state/config/normalizer, valida cutoff causal y fuente executable_quote, sella junio y escribe parquet+metadata con hashes.
- Tests: igualdad `target_z(t)=z_t(t+1)` dentro del mismo espacio, gaps no puenteados, target exactamente +5m, cutoff probado y junio rechazado. Resultado `17 passed in 2.12s`; compile PASS.
- Siguiente paso exacto: hashear/commitear este bloque; luego predeclarar un runner de cinco folds que llame al trainer con `--skip-oof --export-deploy-model`, train_end `202509/202510/202511/202512/202601` para tests `202601..202605`, y aplique el nuevo exportador a `202501..test`.
- Runner ya predeclarado: `run_adajepa_coherent_spaces_v1.ps1`, SHA `0900B63B997B6136D09DB665187920262C89C23FCE4EFEA6478218674839E3BE`; contrato en `research_papers/JEPA/ADAJEPA_COHERENT_SPACES_PREDECLARATION_V1.md`. Próximo paso ahora: commit/push, comprobar procesos/GPU y ejecutar una sola instancia.
- Build completado: cinco encoders flat, train_end `202509/10/11/12/202601`, test rows `1608/1109/1380/1553/1635`, +5m exacto y tres tickers. Manifest SHA `F398B1105C848C45D9BEAE0C156646B8B17207BEA5D08660BB359C099337F7B8`. Versionar 31 ficheros pequeños (~572 KB); excluir 5 `.pt` + 5 parquets (~102 MB).

## Actualización 2026-07-11 05:25 CEST — AdaJEPA shadow bloqueado hasta re-encoding coherente

- Se auditó paper/código tras cerrar PatchCore. AdaJEPA debe actualizar predictor con una transición ya observada, nunca PnL, y permanecer shadow con reset/rollback.
- No adaptar directamente `event_option_dataset.parquet`: los `ptdj_z_*` OOF de cada mes vienen de encoders mensuales distintos; no comparten necesariamente coordenadas. El parquet tampoco contiene `pred_z_h1_*` y el trainer OOF no guardó checkpoints de fold.
- El trainer sí soporta `--export-deploy-model` y guarda state_dict/config/normalizer. Primer paso exacto: añadir un aplicador offline causal de ese checkpoint que exporte `z_t`, `pred_z_h1` y target `z_{t+1}` sobre secuencias contiguas; testear paridad con `export_month_features`/live component.
- Después generar cinco paquetes: encoder entrenado solo antes de la ventana interna de cada test `202601..202605`, mismo seed/presupuesto flat; re-encodear train/inner/test de ese fold en un único espacio. Junio no se lee.
- Solo entonces predeclarar frozen predictor vs predictor+adapter pequeño, un gradiente tras cada transición observada, reset diario, límites de norma y rollback. Primer criterio es error latente OOS por ticker/día, no PnL; downstream será una ablación separada si mejora reproduciblemente.
- Commits publicados de esta sesión: `de3e320` predecl Var, `7730eb7` cierre Var, `06930ed` predecl PatchCore, `c9eb092` cierre PatchCore. Ningún paquete se promovió ni se tocó systemd/live.

## Actualización 2026-07-11 05:15 CEST — PatchCore cerrado y rechazado

- Predeclaración subido en `06930ed`. Runner completó 5 modelos compartidos, 15 coresets, 30 policies y provenance/runtime PASS en 65 s. No quedan procesos activos.
- Control: 15/15 `invalid_validation`, 0 trades. PatchCore: 15/15 `invalid_validation`, 0 trades. Candidate rows 210/1.470; ninguna cumple simultáneamente PF1,3, WR50%, 18 trades/mes y todos los meses positivos.
- Distancia-error: 10/15 Spearman positivos, mediana `0,098982`; es diagnóstico útil pero no edge. Solo cuatro near-miss PatchCore de tres gates, todos SPY/202604 y con mínimo 3–4 trades/mes.
- Decisión: `continue_from_patchcore=false`, `patchcore_meets_full_downstream_gate=false`, `production_live_ready=false`. No probar más coreset sizes, distancias o quantiles.
- Resultado: `.../portfolio_patchcore_abstention_exact_runtime_202601_202605_seed20260618_v1/`; summary SHA `F9E9C27BA96043534DD153EA91905273B274B931038780E6CC5A1798AC5D56F7`; provenance `8B08554B3F9F250C620A7CFD77999EA95FF86B78001038D45F98188063592E3D`.
- Bug diagnóstico post-run: sentinel `-1e18` podía no conservar la mejor métrica inválida SPY con <64 trades por redondeo. No afecta validez/policy/trades. v1r1 usa `-inf`; 10 tests PASS. Candidate grid original es autoritativo.
- Próximo paso: publicar solo artefactos pequeños (excluir 5 `.pt` y 15 `.npz`). Después, si se continúa estrictamente la cola, predeclarar AdaJEPA solo shadow: bloque pequeño, transiciones observadas, sin PnL futuro, reset diario y sin tocar live/systemd. No reabrir Var/PatchCore/modal.

## Actualización 2026-07-11 05:05 CEST — PatchCore v1 listo para checkpoint/lanzamiento

- Se detectó que `...flat_history_2025...walkforward_runtime_contract_v1` seleccionó buckets d50/d65/d80 en varios folds. Sus cupos/cooldowns sí eran runtime, pero no el bucket; no usar esas policies como control exacto. La comparación history 2022/2025 sigue siendo simétrica, pero no es candidata live.
- Nuevo script `neural/jepa/walkforward_event_option_patchcore_abstention.py`: comparte un solo payoff head determinista exacto d25/d35 entre control/PatchCore; coreset k-center train-only, 128 centros/ticker, 70 latentes flat actionless, distancia 1-NN. PatchCore solo filtra; no modifica acción ni score.
- Selección: mismos thresholds que control × siete quantiles de distancia predeclarados. Gates internas PF1,3/WR50%/18 trades por mes/todos los meses positivos. Folds `202601..202605`, seed `20260618+YYYYMM`, CUDA determinista, 40 epochs, batch512, junio sellado.
- Hashes: script `2649D8ED77A7A43F07BE0E67FC47B51FC5ADF6F5E9FC9D304DA4C09A693D29E9`; runner `A0F653D8FDAF735641816A93A2D177DE42323488570B4FC75C8F17D584510795`; dataset `39203C83F47A60AFB2AB7951201CBEB3B9098F4238169F0D716649571667DA2F`. Tests focalizados `9 passed`.
- Próximo paso: commitear/pushear script/test/runner/predeclaración/handoffs; reauditar procesos y ejecutar una sola instancia de `run_portfolio_patchcore_abstention_v1.ps1`. No cambiar coreset size/quantiles después de ver resultados.

## Actualización 2026-07-11 04:47 CEST — Portfolio Var-JEPA v1 cerrado y rechazado

- Checkpoint de predeclaración subido en `de3e320`. El runner único completó deterministic y variational: cinco modelos mensuales/arm, 15 policies/arm, 15/15 folds con `invalid_validation` honesto, provenance PASS y runtime replay PASS. Ya no queda ningún proceso Python/CUDA de esta corrida.
- El análisis v1 falló después de terminar train por comparar las claves equivalentes `trades_per_month` y `min_month_trades`. Se verificó que el directorio fallido estaba vacío, se corrigió solo el analizador/test, se congelaron hashes de metadata/folds/diagnósticos y `run_portfolio_var_jepa_analysis_v1r1.ps1` reanudó únicamente el análisis. No se reentrenó ni reseleccionó nada.
- Resultado representacional Var-control: MAE 9/15 wins, mediana `-0,013979`, Wilcoxon unilateral `p=0,488983`; RMSE 9/15, `-0,004596`, `p=0,380768`; directional accuracy 7/15. Effective rank Var perdió 15/15, mediana `-0,156054`. Incertidumbre-error: 1/15 Spearman positivo, mediana `-0,180431`.
- El KL final Var fue `0,00264..0,00476`, reconstruction `0,265..0,275` frente a MSE control `0,213..0,235`; no hay soporte para la representación probabilística. No probar KL weights ni uncertainty filtering a partir de este resultado.
- Candidate validation: 210 filas por arm, 0 cumplen las cuatro gates. Control: PF 10/210, WR 22/210, volumen 73/210, todos los meses positivos 2/210 por separado. Var: 9/210, 19/210, 94/210 y 4/210. Como ningún threshold fue válido, ambos arms congelaron abstain y tuvieron 0 trades OOS; no relajar gates post hoc.
- Decisión: `representation_improved_reproducibly=false`, `uncertainty_diagnostic_supported=false`, `advance_to_uncertainty_abstention_ablation=false`, `variational_meets_full_downstream_gate=false`, `production_live_ready=false`.
- Informe final: `research_papers/JEPA/results/_diagnostics/portfolio_var_jepa_deterministic_vs_variational_analysis_202601_202605_seed20260618_v1/`; summary SHA `F2C333634F55829049DAD50C4406368439058F70E931A74291E20B85839CC5D8`, report SHA `26692AA45139CC05E0963D1C43A890EF6581E07AC9E4EE3EEFB8E633DD989BCC`, paired cells SHA `7A8AB35A64B499DECF13B8D7E5EDBB9BE27CC3FEA1774220D9A9F0E8E7018FA2`.
- Siguiente paso exacto: cerrar este resultado con artefactos pequeños y push; luego predeclarar el punto 5, Surprise + PatchCore de abstención, sobre flat/control congelado. Coreset solo con train, threshold solo inner validation, distancia/surprise solo abstiene. No volver a Var, modal/MJEPA/SMM, no abrir junio y no tocar systemd/live.

## Actualización 2026-07-11 04:40 CEST — Portfolio Var-JEPA v1 listo para ejecutar

- Se auditó el script/test sin registrar dejado por la automatización anterior y se completó el contrato antes de cualquier corrida completa. No quedan procesos Python/pytest/training activos. El smoke CUDA de enero/una época terminó y solo escribió en `tmp/portfolio_var_jepa_fold_smoke_20260711b`; no reutilizarlo como evidencia.
- Nuevos artefactos: `neural/jepa/walkforward_event_option_portfolio_var_jepa.py`, `neural/jepa/analyze_event_option_portfolio_var_jepa.py`, sus dos tests, `run_portfolio_var_jepa_ablation_v1.ps1` y `research_papers/JEPA/PORTFOLIO_VAR_JEPA_PREDECLARATION_V1.md`.
- Factor único: control payoff latent determinista frente al mismo backbone/decoder con prior/posterior Gaussianos, reparametrización y KL annealed. Encoder flat OOF congelado/actionless; incertidumbre solo diagnóstica. `HOLD` es abstención por threshold inner-validation, no una label construida con futuro.
- Dataset SHA-256 `39203C83F47A60AFB2AB7951201CBEB3B9098F4238169F0D716649571667DA2F`: 22.037 eventos, 44.074 filas CALL/PUT, 85 features, `20250501..20260529`; 0DTE executable_quote ask→bid, junio físicamente ausente.
- Folds/presupuesto: test `202601..202605`, tres meses internos, base seed común `20260618`, folds `base+YYYYMM`, CUDA determinista, 40 épocas, batch 512. Gates de validación: PF 1,3, WR 50%, 18 trades por mes y todos los meses positivos; threshold inválido implica abstain.
- Runtime auditado por código: d25 SPXW/d35 QQQ-SPY, cupos `4/2/1`, cooldowns `0/30/0`, hold >=30m y una sola posición/ticker. El analizador verifica hashes/provenance y paridad de seeds/folds.
- Hashes: runner `DAB6FA8F37D1EEF0AA2B1068BFDC6C964E083B99C6A8E0C4B887C44723106561`; trainer `21C011C6F66906E90B128E091794FC92497739568DC10F34EBB6F9175B45F0A1`; analizador `A5635C14FF39A66C4573A80F1C75165A30D50273F66887B25D8316606D9C35B2`.
- Verificación: tests focalizados `9 passed in 2.13s`, `py_compile` y `git diff --check` PASS. No se tocó systemd, policy live ni cambios legacy.
- Próximo paso exacto después de commitear/pushear esta predeclaración: comprobar procesos/GPU otra vez y ejecutar **una sola instancia** de `run_portfolio_var_jepa_ablation_v1.ps1`. No modificar código, hashes, seeds o gates después del lanzamiento. Después, conservar solo artefactos pequeños y actualizar los tres handoffs con resultado por ticker/mes.

## Actualización 2026-07-11 04:14 CEST — ablación de historia cerrada y rechazada

- El runner predeclarado `run_flat_history_ablation_v1.ps1` terminó ambos arms y salió normalmente con el mensaje `Flat history ablation completed for both arms.`; stdout SHA-256 `A254625E41F90B73321F291C625CA91A7611E0EF3D5DB425C2B7EDADC62CE917`, stderr vacío. Ya no quedan trainer, selector, pytest ni proceso Python de esta ablación.
- Ambos arms completaron 13/13 folds OOF `202505..202605`, join 29.046/29.046, 15/15 folds nested `202601..202605` y provenance PASS. Usaron arquitectura flat, CUDA determinista, 8 épocas, batch 1024, 277 features live, seed base `20260618` y seed de fold `base+YYYYMM`.
- Factor único confirmado por el analizador: inicio de historia `202501` frente a `202201`; solo difieren `data` y `output_dir`. Dataset largo SHA-256 `11E26AADDD91FD441222D552E0362C1D4C2C4489A08D7A6DE66479D6EB454FB1`; control reciente `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720`.
- Control `history_2025`: 495 trades, WR `45,051%`, PF `0,863`, `-20,174R`, DD `-27,180R`; QQQ/SPXW/SPY PF `0,893/0,711/1,336`, PnL `-4,819/-22,935/+7,580R`; 4/15 celdas ticker×mes pasan todos los gates.
- Arm `history_2022`: 440 trades, WR `42,273%`, PF `0,764`, `-31,476R`, DD `-34,403R`; QQQ/SPXW/SPY PF `0,764/0,696/0,874`, PnL `-10,638/-16,542/-4,296R`; 1/15 celdas pasa.
- Meses overall `history_2022`: enero PF `0,514`/`-18,133R`; febrero `0,981`/`-0,417R`; marzo `0,682`/`-8,107R`; abril `1,002`/`+0,048R`; mayo `0,808`/`-4,868R`. El CSV versionable contiene las 15 celdas ticker×mes de cada arm.
- La historia larga sí mejora representación OOF: 13/15 wins en ratio error/persistencia (mediana `-0,07913`, Wilcoxon `p=0,000580`) y 11/15 en tasa de batir persistencia (mediana `+0,07973`, `p=0,003357`). No mejora downstream: PF 6/15 wins (`p=0,9527`), PnL 7/15 (`p=0,7729`); bootstrap diario 2022−2025 `-11,302R`, IC95% `[-44,087,+20,825]`, `P(diff>0)=0,248`.
- Decisión congelada: `continue_from_history_2022=false`. La mejora representacional no se traduce en edge; se rechaza la extensión y no se reabre modal/MJEPA/SMM. Ningún arm cumple gates y ninguno es candidato de promoción.
- Contrato revalidado por código: solo `executable_quote`, ask→bid, 0DTE, rejilla 10:30–14:30 ET/5m, hold mínimo 30m, una posición por ticker, cero solapamientos, cupos `SPXW=4/QQQ=2/SPY=1`, cooldowns `0/30/0`. Junio no aparece en datos, OOF, selección ni trades; fecha máxima del dataset `20260529`.
- Informe autocontenido: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_history_2022_vs_2025_runtime_contract_analysis_202601_202605_v1/`. Hash `summary.json`: `A1AFC66158674F239DA027C614C83566817563F19DB32F1A6CAF57A13530BB1`; `REPORT.md`: `AFBA779FF33F9814A7147B7D9D43B0B787B1C0E9ED5CE36ADEA24621BA1BD99D`.
- Verificación final: `py_compile` PASS y `70 passed in 4.88s` en la suite focalizada, incluido el analizador de historia.
- Cierre versionado y subido a `origin/main` en `8da7a7a` (`analysis: close flat history ablation`); contiene solo el informe pequeño y los handoffs, no datasets/checkpoints/trades masivos.
- Primer paso seguro siguiente: predeclarar —sin ejecutar una búsqueda masiva— el primer factor independiente del punto 4 de la cola (`Portfolio Var-JEPA`). Debe mantener congelado el market encoder flat/control y aislar la incertidumbre/abstención del payoff head; no usar PnL agregado como criterio ni abrir junio.

## Actualización 2026-07-11 03:23 CEST — ablación flat-history activa, no duplicar

- `fd712e2` y los tres commits técnicos anteriores están subidos a `origin/main`.
- El primer launch perdió su PowerShell padre por timeout, pero el trainer control PID `23084` siguió sano y terminó 13/13 folds. No se borró ni reinició la salida.
- Runner reanudado de forma persistente con `-EncodedCommand`: PID `25112`; stdout `tmp/flat_history_ablation_v1_resume2.stdout.log`, stderr homónimo. El intento de quoting fallido previo queda preservado en logs `...resume.*.log` y no tocó artefactos.
- Control `history_2025` completado: 13 folds OOF, 29.046 filas de features, join 29.046/29.046 y 15/15 folds nested con provenance PASS. Overall: 495 trades, WR `45,05%`, PF `0,863`, `-20,174R`; QQQ PF `0,893`, SPXW `0,711`, SPY `1,336`. Solo abril fue positivo overall; control rechazado.
- `history_2022` terminó 13/13 folds OOF con las mismas seeds mensuales, 29.046 filas y join 29.046/29.046. Su nested selector PID `37752` está activo en `...history_2022..._walkforward_runtime_contract_v1`, 2×12 hilos. No lanzar otro runner/selector mientras PID `25112` siga activo.
- Analizador pareado versionado y subido en `507af59`; test focalizado `3 passed`. Exige representación + downstream, no PnL agregado aislado.
- Junio sigue sellado; no se tocó systemd ni ninguna policy.

## Actualización 2026-07-11 03:15 CEST — dataset auditado y ablación lista para lanzar

- El runner de dataset terminó sin procesos huérfanos: 159/159 chunks, 108.156 filas base/physics, 371 columnas physics y fecha máxima `20260529`.
- SHA-256 base: `DED31E49D70EC2525194497994E26FD6A6DD4BF502F7775EA547826B0FB879BF`; physics completo: `11E26AADDD91FD441222D552E0362C1D4C2C4489A08D7A6DE66479D6EB454FB1`.
- Vista physics reciente común al downstream (`202501..202605`): 36.796 filas, SHA-256 `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720`.
- Auditoría: solo `zero_dte`/`executable_quote`, 0 duplicados, 0 infinitos, 0 filas off-grid, 277 features live en ambos arms, junio físicamente ausente. Dos filas SPXW del `20220222` marcan PUT no disponible; ThetaData confirma 162 strikes PUT pero bid/ask cero en esos timestamps. El selector las excluye por disponibilidad observable; no se imputaron ni borraron.
- Se fijaron 13 folds OOF idénticos `202505..202605`; evaluación nested `202601..202605`; flat, seed base `20260618`, seeds por fold `base+YYYYMM`, CUDA determinista, 8 épocas, batch 1024 y mismo contrato runtime.
- Commits nuevos: `6de6aa6` (masking/targets y CUDA determinista), `bf42cd9` (liberación de memoria del selector), `670b2e3` (seed independiente por fold/resume reproducible).
- Suite focalizada completa antes de predeclarar: `66 passed in 4.64s`; test Phys-TD posterior a fold seeds: `14 passed in 2.38s`.
- Predeclaración: `research_papers/JEPA/results/_diagnostics/flat_history_ablation_predeclared_202201_202605_v1/`. Runner: `run_flat_history_ablation_v1.ps1`, SHA-256 `A8DC76553B0573E8594939A60A81AB80C50C64B3DB42510834320EE8EDA1F63D`, parse PASS.
- Próximo paso exacto: commitear/pushear runner+predeclaración+handoffs; después comprobar de nuevo procesos/GPU y lanzar una sola vez el runner. No lanzar SMM/modal ni abrir junio.

## Actualización 2026-07-11 02:53 CEST — build histórico activo, no duplicar

- Se leyeron completos `SUMMARY-update.md`, `SUMMARY-articles.md`, `SUMMARY.md` y este handoff antes de ejecutar trabajo experimental.
- Git auditado: `HEAD=73f1080`, `main` alineado con `origin/main`; se preservan los diffs y artefactos heredados del usuario/agentes previos. Los commits `ce796d9` y `73f1080` ya contienen la predeclaración del dataset histórico y el join Phys-TD explícito.
- Los logs más recientes de `C:\CodexAutomation\logs` son las corridas del 10 de julio terminadas con error de capacidad del modelo; no contienen un entrenamiento posterior oculto.
- La comparación `flat` frente a `modal` está cerrada: ambos arms completaron 13 folds OOF y el downstream nested runtime-equivalente de enero–mayo de 2026. Flat obtuvo PF `0,8996`/PnL `-15,094R`; modal PF `0,8579`/PnL `-21,989R`. Modal perdió también en representación OOF y permanece `advance_to_cross_modal=false`.
- No se debe reanudar SMM/MJEPA modal, VISReg, proto o Gram. El primer paso pendiente real es la ablación de historia del encoder flat.
- Build causal histórico activo y verificado, iniciado por `run_flat_history_dataset_build_v1.ps1`: PowerShell PID `45348`, Python padre PID `6764`, hasta 24 workers. Comando sellado `20220101..20260531`, `option_price_mode=executable_quote`, ask→bid, trailing `50%/25%`, stop `60%`, TP `1000%`, hold mínimo `30m`, horizonte `180m`, rejilla `630..870`/5m y OI obligatorio.
- Hash del runner activo: `DE5E71AC6690BDDEEF497213E1657F4D3B15DCC9A3FC17CC86064CF941737F17`, coincidente con la predeclaración. A las 02:52 había 60 chunks parquet+JSON bajo `tmp/event_option_dataset_execquote_causal1030_202201_202605_v1/`; no lanzar otro build ni tocar esa salida.
- GPU sin entrenamiento CUDA: unos `2.363 MiB` libres; el build actual es CPU. Tras terminar, el runner creará el parquet consolidado y `..._v1_physics`; auditar ambos hashes, filas, meses/tickers, continuidad y ausencia física de junio antes de definir/lanzar los dos arms de training.
- No se tocó systemd, ninguna policy legacy ni ningún estado `production_live_ready`.

**Fecha:** 2026-07-10T21:55 CEST (actualización incremental; colas v1 detenidas)
**HEAD:** `cc5665f docs: record results of flat vs modal causal ablation` (`origin/main` en el mismo commit)
**Estado de esta continuación:** auditoría inicial completada sin duplicar ni interrumpir las corridas heredadas.

## Actualización 2026-07-11 02:04 CEST — selector flat runtime-equivalente activo

- Se repitió la auditoría completa de handoffs, Git, logs y procesos.
- No había Python/CUDA/pytest activo al comenzar. Se encontraron artefactos creados después del handoff: SMM v2r1 parcial (solo folds `202505..202507`) y colas v1 parciales/contaminadas. No se reanudaron.
- `flat` y `modal` originales están completos: 13 folds OOF y 15 folds nested OOS por arm, provenance `passed=true`.
- Hallazgo P0 nuevo: el selector downstream original usó cooldown 30m para SPXW/SPY/QQQ y cupos variables. No equivale al runtime `SPXW=4/0m`, `QQQ=2/30m`, `SPY=1/0m`.
- Las métricas históricas flat/modal no deben usarse como comparación live-equivalente hasta terminar los nuevos selectores.
- Se crearon dos parquets derivados bajo `tmp/`, físicamente sellados hasta `20260529`, con 41.883 filas, 538 columnas, ask→bid `executable_quote` y rejilla 10:30–14:30/5m.
- Hash flat sellado: `65CCD607A77AF65C71469A74EF76D71F40B56E6BCDD3DEE408E673A5FA59ECEB`.
- Hash modal sellado: `FC99717F6C8B801C09C9F1B4F39FA1E9860505FDA2E112A9706746298CF0DD64`.
- Proceso activo que no debe duplicarse: PID `8636`, selector flat sobre salida nueva `ptdj_ablation_flat_h1_3_6_12_causal_202501_202605_v1_walkforward_runtime_contract_v2`.
- Comando contractual: `--ticker-cooldown-minutes SPXW=0 QQQ=30 SPY=0 --ticker-max-day-grids SPXW=4 QQQ=2 SPY=1 --lgb-device-type cpu --seed 20260618 --no-resume`.
- Primer checkpoint observado: `SPXW/202601`.
- Próximo paso seguro: esperar a que PID `8636` termine; verificar 15 folds/hashes/provenance y solo entonces lanzar modal en otra ruta nueva con idénticos argumentos.
- Junio de 2026 sigue sellado. No se modificó systemd, no se promovió ningún paquete y no se tocó la policy legacy.

### Actualización incremental 2026-07-11 02:20 CEST

- Flat runtime-equivalente terminó 15/15 folds en `ptdj_ablation_flat_h1_3_6_12_causal_202501_202605_v1_walkforward_runtime_contract_v2`.
- Validación independiente: provenance PASS, 481 trades, `min(exit_minutes)=30`, mes máximo `202605`, sin off-grid, cupos excedidos ni solapamientos.
- Overall flat: WR `43,867%`, PF `0,8996`, PnL `-15,094R`, Max DD `-26,009R`.
- QQQ: 166 trades, PF `0,9998`, PnL `-0,010R`, mínimo mensual 28, 60% meses positivos.
- SPXW: 217 trades, PF `0,8127`, PnL `-14,249R`, mínimo mensual 17, 60% meses positivos.
- SPY: 98 trades, PF `0,9695`, PnL `-0,835R`, mínimo mensual 17, 40% meses positivos.
- Flat queda rechazado por PF/WR, volumen en SPXW/SPY y meses negativos.
- Modal runtime-equivalente está activo en PID `38064`, salida `ptdj_ablation_modal_h1_3_6_12_causal_202501_202605_v1_walkforward_runtime_contract_v2`, con los mismos argumentos, CPU/8 workers y seed `20260618`.
- No lanzar otro modal mientras PID `38064` esté activo. Tras terminar: validar contrato, ejecutar `analyze_event_phys_td_flat_modal.py`, persistir el informe/hashes y decidir si se detiene MJEPA.

## Actualización final 2026-07-11 02:35 CEST — flat/modal cerrado

- No quedan procesos Python, pytest ni entrenamientos de esta comparación.
- Flat runtime-equivalente: 481 trades, WR `43,867%`, PF `0,8996`, `-15,094R`, DD `-26,009R`, 1/15 celdas ticker×mes pasa todos los gates.
- Modal runtime-equivalente: 491 trades, WR `42,974%`, PF `0,8579`, `-21,989R`, DD `-31,039R`, 0/15 celdas pasa; `SPY/202601` fue abstain.
- Ambos provenance mensuales terminaron `passed=true`; contrato de ejecución validado, incluyendo hold mínimo observado 30m y ausencia de solapamientos.
- Representación OOF rechaza modal: 2/15 wins en ratio error/persistencia y 0/15 en tasa de batir persistencia.
- Downstream pareado rechaza modal: 7/15 wins en PF y 7/15 en PnL; bootstrap diario `-6,895R`, IC95% `[-31,537,+17,109]`.
- Decisión congelada: `advance_to_cross_modal=false`. No reanudar SMM v1, v2r1, proto, VISReg o Gram; no avanzar a H-Market-JEPA desde esta rama modal.
- Informe autocontenido: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_vs_modal_runtime_contract_analysis_202601_202605_v2/`.
- Hash `summary.json`: `EB1D233E3FD65FE3384ADAD736117CD48766E6A953E85489DACDAAB5017D1C5C`.
- Hash `REPORT.md`: `F7ACE4AA90594F6C7C06CEE7A216118B9303A1EB3157BA8A592FF97B106A4502`.
- Hash parquet flat sellado: `65CCD607A77AF65C71469A74EF76D71F40B56E6BCDD3DEE408E673A5FA59ECEB`.
- Hash parquet modal sellado: `FC99717F6C8B801C09C9F1B4F39FA1E9860505FDA2E112A9706746298CF0DD64`.
- Tests: `py_compile` PASS; suite focalizada completa `64 passed in 3.88s`; test del analizador posterior `6 passed in 0.94s`.
- Commits ya subidos durante la sesión: `d947b5b`, `f55550c`, `e863129`, `279e399`, `943fc40`.
- Commits finales también subidos: `13b9660` (manifests sellados en el analizador), `98311d3` (informe y handoffs) y `b5bb1c1` (ocho JSON/CSV pequeños con métricas, hashes y folds; añadidos explícitamente porque `_diagnostics` los ignora por defecto).
- No se tocó systemd, no se marcó ningún paquete live-ready, no se promovió/restauró legacy y junio de 2026 permaneció sellado.

### Primer paso seguro para la siguiente continuación

1. Confirmar Git/logs/procesos y leer este handoff completo.
2. No relanzar flat/modal ni ninguna cola SMM: la decisión ya está cerrada.
3. Auditar cobertura, consistencia y hashes de ThetaData 2022–2024 para opciones y spot, sin abrir junio.
4. Si los labels executable_quote son homogéneos, predeclarar una única ablación de historia para el encoder flat: train desde 2022 frente a train desde 2025, igual arquitectura/seed/presupuesto y selector nested runtime-equivalente.
5. No ejecutar hasta versionar el manifest, estimar coste y fijar folds. Usar CUDA/32 hilos solo de forma simétrica en ambos arms.

## Actualización 2026-07-11 02:43 CEST — historia 2022 predeclarada

- Objetivo activo: continuar hasta un candidato rentable, sin ampliar gates ni abrir junio.
- Hardware: RTX 5070 Ti Laptop 12.227 MiB, Ryzen 9/32 hilos, 32 GB RAM. La GPU mostraba ~2,2 GB libres al auditar; comprobar de nuevo antes de CUDA.
- Manifest nuevo sellado a mayo: `research_papers/JEPA/results/_diagnostics/thetadata_manifest_spxw_spy_qqq_202201_202605_sealed_v1/`.
- Manifest: 6.425/6.425 filas completas, 3.116 zero_dte, fechas `20220103..20260529`, cero claves 0DTE duplicadas.
- Hash manifest: `88BE8A2FF44C18FB57FCA360D31DEF574DDBB0419A792FC88349942711D2974A`; hash summary: `5075E530CC8BBDF5613028B42071EFBFF21DCB73F586735AC483640339A14B19`.
- Zero-dte por año QQQ: `170/250/252/250/99`; SPXW: `220/250/252/250/102`; SPY: `170/250/252/250/99` para 2022/2023/2024/2025/ene–may 2026.
- Runner creado: `run_flat_history_dataset_build_v1.ps1`; parse PowerShell PASS.
- Hash runner final: `DE5E71AC6690BDDEEF497213E1657F4D3B15DCC9A3FC17CC86064CF941737F17`; tests del builder: `9 passed in 0.42s`.
- Hash builder: `6E89AAFED8A2BB66AA8EE80DF70644ECA189D0CE1D8C56F3812895430DAC4307`.
- Hash enhancer: `3E420DB49315AFD9363C45B9F0FEFFA38732EFC116889D3D69B4417A94D2CB36`.
- Próximo paso: commitear/pushear manifest+runner+docs, ejecutar el build causal reanudable y auditar filas/hashes antes de entrenar.

### Objetivo cuantitativo obligatorio

Para cada ticker (`SPXW`, `QQQ`, `SPY`) y no solo en agregado, cualquier candidato debe cumplir en el walk-forward:

- hold por trade `>=30m`;
- PF `>=1,30`;
- WR `>=50%`;
- trades por mes `>=18`;
- PnL mensual positivo en todos los meses de evaluación.

Hay datos históricos de opciones y spot de 2022 a 2026 bajo `D:/ThetaData/data_options` y `D:/ThetaData/data_underlying_derived`. Deben usarse solo con ventanas causales y hashes/manifests reproducibles. Junio de 2026 permanece sellado hasta que exista un único protocolo congelado.

## Auditoría de reanudación de 2026-07-10 21:31 CEST

- Se leyeron completos `SUMMARY-update.md`, `SUMMARY-articles.md`, `SUMMARY.md` y este handoff.
- Se inspeccionaron `git status`, `git log`, todos los diffs tracked, los artefactos untracked relevantes y los logs recientes de `C:\CodexAutomation\logs`.
- `flat` y `modal` están realmente completos; el primer paso pendiente es la cola SMM predeclarada.
- La baseline SMM y su nested selector están completos. `sigreg_off` terminó 39/39 folds a las 21:38:51 y el wrapper avanzó a entrenamiento `visreg`.
- Proceso padre: PID `58028`, `powershell -Command "$env:PYTHONPATH=\".\"; .\run_smm_ablations.ps1"`, iniciado a las 20:29:13.
- Proceso activo: PID `18384`, trainer `...smm_visreg... --lambda-visreg 0.1 --device cuda --seed 20260618`, iniciado a las 21:38:51.
- No hay otro entrenamiento/evaluador JEPA activo. El PID `66384` corresponde al wrapper de esta ejecución programada de Codex, no a un experimento.
- Junio de 2026 continúa sellado: el trainer registra `effective_data_cutoff_month=202605`; el selector termina en `202605`.
- Hallazgo metodológico: `modal` histórico se ejecutó en CPU, mientras SMM baseline usa CUDA y activa simultáneamente `mask_modal_prob=0.15` y `mask_temporal_prob=0.15`. Por ello, la comparación directa modal→SMM es exploratoria y no una ablación limpia de un único factor. Las comparaciones SMM baseline→`sigreg_off`/`visreg`/`proto`/`gram` sí parten de la misma baseline CUDA y cambian un regularizador por arm.
- Hallazgo de ventana: `flat/modal` reportan únicamente `202601..202605`; los selectores SMM se lanzaron con `--start-month 202505`. La tabla SMM original mezclaba ventanas. Recomputación comparable: baseline SMM 341 trades, WR 41,35%, PF 0,778, -24,177R; `sigreg_off` 422 trades, WR 40,52%, PF 0,851, -20,951R. Ambos rechazados.
- Los provenance extendidos de baseline y `sigreg_off` tienen `passed=false`: faltan policies/hashes para los tres tickers en 202511. Los 15 folds enero–mayo sí tienen hashes completos. Pendiente ejecutar selectores separados con `--start-month 202601 --end-month 202605` sobre cada dataset ya enriquecido.
- Semántica auditada: `proto` no activa EMA (`use_ema_teacher=false`); `gram` es consistencia relacional Gram predicción–target, no anchoring contra teacher congelado; SMM baseline no añadió el predictor JEPA, que ya estaba en `modal`.
- Fallo P0 experimental: el encoder v1 enmascaraba también `target_z` futuro porque se llamaba en modo train. Baseline/`sigreg_off`/`visreg` SMM v1 no prueban masking solo en prefijo y quedan invalidados para atribución.
- Se detuvo PID `51972` (selector visreg) tras 8/39 folds y el wrapper `58028` salió. Automatizaciones paralelas del IDE relanzaron el selector `sigreg_off` sobre la misma ruta; se detuvieron PID `5268`/`28468` y `66588`/`30300` tras verificar comandos. El directorio `_walkforward` de `sigreg_off` quedó sobrescrito parcialmente con una fila.
- Corrección aplicada: `apply_mask=False` explícito para target con/sin teacher, masking preservado en contexto, validación de probabilidades. Suite focalizada: 58/58 PASS.
- No se ha tocado systemd, no se ha restaurado/promovido la policy legacy y no se ha abierto junio.

## Estado del experimento

### Ablación predeclarada: `flat` vs `modal` encoder (SUMMARY-articles.md §6, punto 1)

**Estado:** COMPLETADO. Ambos arms (`flat` y `modal`) completaron extracción OOF y evaluación OOS con nested walk-forward.

**Diseño experimental:**
- **Factor único cambiado:** `--encoder-input-mode flat` vs `--encoder-input-mode modal`
- **Dataset:** `tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet` (44.169 filas, 371 cols)
- **SHA-256 dataset:** `E6A19EFBA1EDB055C733AAB4967843F7A4B5F1D2C8238A7A243FC5BBC2251903`
- **Seed:** `20260618` (default del trainer)
- **Horizons:** `1,3,6,12` (equivalentes a 5/15/30/60 minutos)
- **OOF range:** `--start-month 202501 --end-month 202605`
- **Data cutoff:** `202605` (junio excluido físicamente)
- **Features live-observable:** `--live-observable-features-only`
- **Contiguidad 5min:** `--expected-step-minutes 5`
- **Rejilla 10:30–14:30 ET:** `--entry-start-minute-et 630 --entry-end-minute-et 870`

**Arms:**
1. `flat`: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_h1_3_6_12_causal_202501_202605_v1/`
2. `modal`: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_modal_h1_3_6_12_causal_202501_202605_v1/`

### Comandos ejecutados

#### 1. Tests focalizados (50 passed)

```powershell
python -m pytest -q tests/test_build_event_option_dataset.py tests/test_event_option_live_causality.py tests/test_event_option_non_overlap.py tests/test_event_option_production_validator.py tests/test_jepa_bot_execution.py tests/test_event_phys_td_jepa_causality.py --basetemp C:\tmp\pytest-jepa-causal-20260710b
```

### Arm 1: `flat` (COMPLETADO)

Comando ejecutado con `--encoder-input-mode flat`.
Output: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_h1_3_6_12_causal_202501_202605_v1/`
Folds generados: 13 folds OOF (mayo 2025 – mayo 2026).
Filas OOF: 33.380.

### Arm 2: `modal` (COMPLETADO)

Comando:

```powershell
python neural/jepa/walkforward_event_phys_td_jepa_oof.py \
  --data "tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet" \
  --output-dir "research_papers/JEPA/results/_diagnostics/ptdj_ablation_modal_h1_3_6_12_causal_202501_202605_v1" \
  --tickers SPXW SPY QQQ --expiry-modes zero_dte \
  --start-month 202501 --end-month 202605 \
  --horizons 1,3,6,12 --encoder-input-mode modal \
  --live-observable-features-only \
  --entry-start-minute-et 630 --entry-end-minute-et 870 \
  --entry-grid-anchor-minute-et 600 --expected-step-minutes 5 \
  --seed 20260618 --device cpu --epochs 8 --batch-size 1024 \
  --context-len 6 --z-dim 32 --phys-dim 12 --delta-dim 16 \
  --hidden-dim 128 --num-layers 2
```

Output: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_modal_h1_3_6_12_causal_202501_202605_v1/`

#### 2. Verificación de la continuación

```powershell
python -m py_compile neural/jepa/walkforward_event_phys_td_jepa_oof.py neural/jepa/append_xinput_oof_to_event_option_dataset.py
python -m pytest -q tests/test_build_event_option_dataset.py tests/test_event_option_live_causality.py tests/test_event_option_non_overlap.py tests/test_event_option_production_validator.py tests/test_jepa_bot_execution.py tests/test_event_phys_td_jepa_causality.py --basetemp C:\tmp\pytest-jepa-causal-20260710c
```

Resultado: `50 passed in 10.44s`.

#### 3. Recomputación de métricas SMM

Se leyó cada `event_option_profile_trades.csv` con `dtype={'date': str, 'month': str, 'ticker': str}` y se llamó a:

```python
from neural.jepa.walkforward_event_option_gate import metrics
metrics(frame, expected_months=['202601', '202602', '202603', '202604', '202605'])
```

Se recomputaron scopes overall/ticker/mes/ticker-mes para baseline SMM y `sigreg_off`, además de la vista extendida `202505..202605`. No se leyó ni se puntuó junio.

### Procesos activos

- Ningún proceso Python/entrenamiento/evaluador JEPA activo tras detener las colas v1 verificadas.

### Artefactos y checkpoints

- Dataset: `tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet`
- Exploratory nested WF (rechazado): `research_papers/JEPA/results/_diagnostics/event_option_execquote_causal1030_nested_exploratory_202601_202605_v1/`
- SMM baseline encoder/features: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_smm_baseline_h1_3_6_12_causal_202501_202605_v1/`
- SMM baseline selector extendido: mismo path con sufijo `_walkforward/`; 39 folds, 202511 sin policy en los tres tickers.
- SMM `sigreg_off` encoder/features: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_smm_sigreg_off_h1_3_6_12_causal_202501_202605_v1/`
- SMM `sigreg_off` selector extendido: mismo path con sufijo `_walkforward/`; 39 folds, 202511 sin policy en los tres tickers.
- SMM `visreg` activo: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_smm_visreg_h1_3_6_12_causal_202501_202605_v1/`.

### Hashes y seeds

| Artefacto | SHA-256 |
| --- | --- |
| Dataset base | `68AE45C89D521F71431261DEEA9BCC7E465FEB294D17BF122AFBDDBB30A4C8F8` |
| Dataset physics | `E6A19EFBA1EDB055C733AAB4967843F7A4B5F1D2C8238A7A243FC5BBC2251903` |
| Trainer cargado por la cola | `74DA6ECD9DEAB88719296A7DF37C1364B1CE4FDA041E3F7DFB4F3EE37FDFFCB7` |
| Appender cargado por la cola | `DAAB0C1D9F6E42067D090996EBBB6CB256195177398FB45EBB3E496A8D8F2914` |
| `run_smm_ablations.ps1` | `229F7F0333A4E47B49A468A164353485246040F44A0DAF12B7E39F1393FE9D1F` |
| SMM baseline metadata | `2E659A9712B29765B1C18F45651146DDAC53D3C9F627EAB20EAB345F61602A8F` |
| SMM baseline fold configs | `653A2B0880D48D94D9F375834E42AD67AEF3616ACC37B7FC91DFE96EEBC03C7E` |
| SMM baseline OOF features | `9B1AD00835CAB570EDEF1FF46B632AD51FB184F6749939303E3B1C88E1636E0A` |
| SMM baseline joined dataset | `A81D5F2F2CB010C1F729B6777B12EEDCA101B854A67286756903BE07F9DE7FA2` |
| SMM baseline extended trades | `C89FD11A2480E3DEEDE697968B9F4D9C3BC38F144B52FDE0B33F7398AAC2B82A` |
| SMM baseline extended metrics | `E829085A01720DFB7D895D5EB4EF5C57BC621BB47928B4FC83157CA0B8D06E10` |
| SMM baseline selected folds | `E6D7DDE5883E78E40524CED2266A5E12A8A5CF995AE952147E2FAAE842F5EA33` |
| SMM baseline provenance | `4B252477B3D767CC64281E17D58AB2C419DF33E69CC169673AD88EB0AF5CA1B9` |
| `sigreg_off` metadata | `424C21F3A8A299F8A7B1E841568B352EA636CAF2D88FADF3CD6465F6FF16E9F7` |
| `sigreg_off` fold configs | `873DC69F2356D2479B33BA2C607C634C07CE6E67587BE5B93AF61F6582961D23` |
| `sigreg_off` OOF features | `0F9B2EE2243B489A96A636C3850D43E7E68E054E3EF741BB0F56517C337BFA16` |
| `sigreg_off` joined dataset | `9A04B13D83B6ED1844B86F7E030F5D52FD06A1D2F5F6028E0A9BD85D728D2E30` |
| `sigreg_off` extended trades (snapshot previo; ruta sobrescrita después) | `267454B20F09F8E489D800DA96FA7BD1A1D9CF54A44005C9BE7611C17B313566` |
| `sigreg_off` extended metrics (snapshot previo; ruta sobrescrita después) | `6B3BD5439F125805B18A12BB659E1E9236AE6C1C12A24F4828D23AD5DC3A25D8` |
| `sigreg_off` selected folds (snapshot previo; ruta sobrescrita después) | `B82B1C5E061B92F1BBFCC6D89C3C1F46428947C9B19C63830299DA534D8A35EF` |
| `sigreg_off` provenance (snapshot previo; ruta sobrescrita después) | `3A1BF938CB07076EC33D62945CBFF2F80D28D48EE3542221EAF84EB15FADFD9B` |
| Seed | `20260618` |

Hashes v2 antes de lanzar:

| Artefacto | SHA-256 |
| --- | --- |
| Trainer prefix-only corregido | `8196D9391AE32CE157C5162C5901E99BF346C79AFB7FCBF0EBFCD591973F8F03` |
| Runner modal-mask-only v2r1 | `4236E47E52F7D203847EC74B46089E7D649AE7821D4E5D50C7C6D25D72157BEC` |
| Test Phys-TD/SMM | `DD2DE9A1576B33B0EAB1E2D600B4D0B6C250E2294845A0B72D7B65C4A6A78A29` |
| Test appender | `D779ED90FFE3F36F882ACE8D188CD4B3EC5BD181917EBC7A4E12BCB14FB7E1DD` |

### Tests ejecutados

```text
50 passed in 4.92s (2026-07-10T19:17 CEST)
50 passed in 10.44s (2026-07-10T21:39 CEST; py_compile previo PASS)
8 passed in 2.20s (tests Phys-TD/SMM, después de corregir un fixture que omitía `output_dim`)
53 passed in 3.79s (suite focalizada completa posterior, basetemp `C:\tmp\pytest-jepa-causal-20260710d`)
1 passed in 0.52s (`tests/test_append_xinput_oof_to_event_option_dataset.py`)
13 passed in 1.99s (target masking corregido + appender)
58 passed in 3.91s (suite focalizada completa tras corrección, basetemp `C:\tmp\pytest-jepa-causal-20260710e`)
```

Suite:
```text
tests/test_build_event_option_dataset.py
tests/test_event_option_live_causality.py
tests/test_event_option_non_overlap.py
tests/test_event_option_production_validator.py
tests/test_jepa_bot_execution.py
tests/test_event_phys_td_jepa_causality.py
```

### Métricas disponibles

- Baseline nested exploratorio Jan–May rechazado: Overall PF 0,909, WR 43,8%
- SMM baseline Jan–May: 341 trades, WR 41,35%, PF 0,778, `-24,177R`, Max DD `-27,33%`; rechazada.
- SMM `sigreg_off` Jan–May: 422 trades, WR 40,52%, PF 0,851, `-20,951R`, Max DD `-33,31%`; rechazada.
- Vista extendida baseline: 908 trades, PF 0,739, `-79,727R`, mínimo mensual 0; no comparable directamente con `flat/modal`.
- Vista extendida `sigreg_off`: 1.025 trades, PF 0,743, `-90,675R`, mínimo mensual 0.
- Legacy package: BLOCKED_FOR_PRODUCTION

### Fallos encontrados

- La comparación SMM publicada usó métricas `202505..202605` contra `flat/modal` `202601..202605`; corregido en los resúmenes.
- La comparación modal→SMM cambió dos máscaras y CPU→CUDA; no es atribución causal de un factor.
- `policy_selection_provenance.json` de baseline/`sigreg_off` extendidos marca `passed=false` por tres folds sin policy en 202511. Los folds enero–mayo están completos, pero requieren un selector de ventana correcta para provenance autocontenido.
- El primer intento de los tests SMM nuevos dio 2 fallos porque el fixture no pasaba `output_dim` a `ModalSequenceEncoder`; corregido en el test, sin cambiar código experimental. Resultado posterior 8/8 PASS.
- SMM v1 enmascaraba targets futuros; colas invalidadas y detenidas.
- `run_smm_ablations_202601.ps1` habría mezclado versiones de código y usa `--output` inválido en el appender de `proto/gram`.
- La automatización paralela sobrescribió parcialmente el selector `sigreg_off`; no asumir que sus hashes snapshot siguen presentes en disco.
- Primer launch v2 falló antes de cualquier fold porque el timeout corto cerró stdout (`OSError 22`); directorio `..._v2/` conserva solo metadata/nombres. Reintento debe usar `..._v2r1/`.

### Cambios sin commit

```text
M CODEX-HANDOFF.md
M SUMMARY-update.md
M SUMMARY-articles.md
M neural/jepa/append_xinput_oof_to_event_option_dataset.py
M neural/jepa/walkforward_event_phys_td_jepa_oof.py
M tests/test_event_phys_td_jepa_causality.py
?? tests/test_append_xinput_oof_to_event_option_dataset.py
M backtest/backtest_gbt_parquet.py  (solo line-ending)
M neural/models/jepa/.../event_option_policy.json  (entry_sample_minutes/anchor additions)
M neural/models/jepa/.../component_registry.json  (newline at end)
M neural/models/jepa/.../QQQ_static_union_balanced.json  (newline)
M neural/models/jepa/.../SPXW_static_union_balanced.json  (newline)
M neural/models/jepa/.../SPY_static_union_balanced.json  (newline)
M neural/models/jepa/.../runtime_policy_replay_summary.json  (newline)
?? run_smm_ablations.ps1
?? run_smm_ablations_202601.ps1
?? run_smm_modal_mask_only_v2.ps1
?? artefactos diagnósticos flat/modal/SMM y `tmp/` (grandes; no añadir sin selección explícita)
```

### Actualización 2026-07-11 15:35 CEST — Ablación de Gates de Régimen Completada
- **Corrida Única Completada (task-254):** Ejecución limpia de los 5 arms (C0, R1, R2, R3, R4) sobre la vista del dataset físicamente sellada `tmp/event_option_dataset_execquote_causal1030_202501_202605_regime_v1.parquet` (SHA-256: `a1970d2cbd7ef8f96a8b2d9fc092f4b323513c03895e73c2058f39b11c7cbef5`).
- **Control C0:** Confirmado. En febrero de 2026, C0 seleccionó la configuración base `none` (no gate) para QQQ (21 trades, PF = 1.416, PnL = +2.771R) y SPY (19 trades, PF = 1.344, PnL = +2.207R), absteniendo en el resto de folds.
- **R1 (IV Skew):** Rescató el fold `SPXW 202602` con el gate `rg_phys_d25_iv_skew_put_minus_call_below_q20pct` (9 trades, PF = 1.452, +1.170R). También mejoró `QQQ 202602` (PF = 1.444 vs 1.416 en C0) usando `rg_phys_d35_iv_skew_put_minus_call_above_q20pct`.
- **R2 (Spread - Primary):** Seleccionó un spread gate `below` para `SPY 202602` (PF = 1.486 vs 1.344 en C0) y `SPY 202603` (PF = 1.185), pero sufrió drift en `QQQ 202604` (PF = 0.968).
- **R3 (Abs Return) & R4 (IB Range):** Estructuralmente viables (10:30 filter causó <3% candidate loss), pero inestables OOS (QQQ Feb 2026 R3 PF = 0.746, R4 PF = 0.587).
- **Conclusión General:** Ningún arm supera el contrato completo. Se confirman drift y near-misses por baja frecuencia.
- **Informe Detallado:** `C:\Users\Álvaro Schwiedop\.gemini\antigravity-ide\brain\248f0f85-3bd2-48b9-a7cc-576d373827d5\ablation_report.md`.

### Último commit
```text
cc5665f docs: record results of flat vs modal causal ablation
f7ce2c6 research: implement regime-conditioned gate ablation v1
```

### Junio de 2026

Completamente sellado. El `--data-cutoff-month 202605` / `--end-month 202605` excluye junio del dataset y del OOF.

### Primera acción del siguiente agente

1. Leer el `ablation_report.md` en el directorio de artefactos para entender las dinámicas y desgloses mensuales de cada arm.
2. Analizar por qué la señal de dirección CALL/PUT sigue sufriendo de drift inestable (el control C0 abstiene casi siempre, y los gates seleccionados en inner no garantizan PF > 1.0 en todos los meses outer).
3. No lanzar ejecuciones sin predeclaración escrita con hash exacto.
4. No alterar producción, no modificar los servicios de VPS systemd y mantener junio sellado.
