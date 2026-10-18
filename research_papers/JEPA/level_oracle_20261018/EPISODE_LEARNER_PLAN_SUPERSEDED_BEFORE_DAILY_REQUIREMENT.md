# Aprendiz de episodios V1 — plan definitivo anterior al nuevo fit

Fecha: 2026-10-18. Autorización del usuario para continuar investigación local.
Este experimento se define **después** de conocer el resultado de los tres
aprendices anteriores; enero–junio2026 es SEEN_DEVELOPMENT. No representa un
holdout intacto ni una nueva fuente. Una sola variante y un solo fit nuevo.

## Intervención congelada

Control `gbt_net` existente en `learners_v1`; variante `gbt_net_episode` añade
exactamente35 valores de `episode_features.FEATURE_NAMES`, seguidos de sus35
máscaras0/1. Mismos1954 canales originales y70 nuevos, total2024. Ningún ID,
ordinal, traza, label, duración futura o resultado se convierte en feature.

Se reutiliza `training_sample.parquet` completo,270377 filas en el mismo orden,
con `sample_i`, targets `net_base`, ticker y pesos intactos. Los primeros1954
float32 de cada fila se copian de `learners_v1/train_x.npy` y se verifican por
igualdad de bits, incluidos NaN. El bloque de episodio se une por
`(ticker,date,state_i)` con lookup explícito:35 valores float64→float32 finitos y
35 máscaras bool→float32. Un valor almacenado0 con máscara falsa sigue ausente.
No se filtran estados, acciones o tickers según episodio abierto.

Fit2023–2024, validación2025, evaluaciónenero–junio2026. Escalas train originales:
SPXW680/SPY81/QQQ88 USD. Target net_base/escala, pesos originales, score convertido
a USD. GBT L2,200 árboles,31 hojas, profundidad6, mínimo100 filas por hoja,
learning_rate0,04, reg_lambda10, max_bin63, seed20261018, deterministic=True,
force_col_wise=True, n_jobs4. La configuración se carga del GBT original sellado.
Sin GPU, early stopping, calibrador, clipping, nuevas semillas o refit control.

## Autoridad y causalidad

El original, su auditoría económica PASS, el motor y su auditoría FULL, el build
de episodios PASS y sus contratos/índices se vinculan por SHA256 antes del fit.
Se exigen2595 sesiones disponibles y6 ausencias originales. Los packs episodios
se verifican contra hash por día, schema, nombres, estado60..375 y bindings de
`states.parquet`/`levels.parquet` del índice auditado. El FeatureStore original
mantiene whitelist, máscaras y hashes de inputs originales en inferencia.
Ninguna fuente raw se modifica y no hay API.

El control usa los scores NPZ originales verificados contra sus manifests. Además,
su modelo existente debe reproducir exactamente el vector `gbt_net` de cada día,
con mismos features y escala. Una discrepancia detiene la ejecución; no se ajusta
ni sustituye el control. Su ejecución se recalcula sobre el mismo motor/labels,
para obtener ledgers comparables en ambos brazos.

Contratos, acciones, target/stop, universo, latencia, costes y scheduler permanecen
iguales. Una posición por ticker; fill→exit_i+1, no-fill→state_i+1; no reemplazo
de acción por falta de quote. No hay hold fijo: salida target/stop/EOD del motor.

## Selección y contraste

Siete políticas: CASH y `gbt_net__0/5/10`, `gbt_net_episode__0/5/10`. Máximo score
entre ofertas, umbral estricto, WAIT cero y desempate por action_id como antes.
Ranking2025: suma del neto base por ticker dividido por su escala train.
CASH gana empate a0; después control antes de variante y umbral menor.

Congelar tabla de siete opciones, ganador único, mejor opción de cada brazo
frente a CASH, modelo, fuentes y predicciones/outputs de validación antes de
abrir los nuevos labels test. El test original ya es conocido; no se reutiliza
para selección. Si gana CASH, el resultado no acredita un modelo rentable.

Reportar ambos costes, intentos/fills/no-fills, PF/indefinición, meses positivos,
drawdown realizado, TARGET/STOP/EOD y hold mínimo/mediana/máximo por ticker.
Comparaciones emparejadas de diferencia por ticker-día y mes, con calendario
completo y ceros: variante−control al mismo umbral0/5/10; mejor variante−mejor
control; cada mejor brazo−CASH; ganador conjunto−CASH. Los mejores brazos se
eligen sólo2025 e incluyen CASH como alternativa. No rescate por ticker/mes.

Para esas siete comparaciones se calculan intervalos percentiles95% con10000
resamples de fechas completas de test, seed20261018; en cada resample se toman
conjuntamente los tres tickers de una fecha para conservar su dependencia diaria.
Reportar diferencias USD y normalizadas por escala, base/adverso. Son intervalos
descriptivos condicionados a estos modelos y a desarrollo visto, no corrección
por selección adaptativa ni garantía futura.

Dos conclusiones separadas: mejora de neto normalizado total del mejor brazo
variante respecto al mejor control bajo ambos costes, y gate conjunto del ganador.
Gate original sin cambios: en cada ticker neto base/adverso>0, PFbase≥1,2,
≥60trades,≥3/6meses positivos. La variante no puede promocionarse por una mejora
relativa que siga perdiendo o por un ticker favorable.

Diagnósticos secundarios: sesgo, MAE/RMSE/R² de retorno sobre todas las acciones
y sobre acciones ejecutadas, por brazo/ticker/periodo. No se usan para selección
ni para ajustar umbrales/calibradores. La población de acciones no equivale a
la distribución de decisiones que visita el scheduler.

## Ejecución, interrupciones y evidencia

Root nuevo `D:/GexResearchArtifacts/level_oracle_20261018/episode_learners_v1` y
runtime hermano. Productor separado `train_episode_model.py`; originales intactos.
Plan/código/dependencias y autoridades se copian/sellan antes de construir matriz
y antes del fit. Revisión técnica independiente y fixtures antes del único ajuste.

Bloqueo exclusivo OS por root. Etapas matriz, modelo, validación, freeze, test y
cierre con manifests atómicos que vinculan inputs/outputs. Guardado mediante
temporal único, fsync, hash y rename; archivo publicado sin manifest completo
permanece parcial y se conserva antes de repetir esa etapa. Una etapa completa
con hash distinto falla cerrado. No hay checkpoint intra-GBT: sólo podría
repetirse un fit cuya finalización no haya quedado publicada. El modelo completo
nunca se refittea por una interrupción posterior.

Predicciones por día con par NPZ/manifest completo y verificado permiten repetir
evaluación con los mismos modelos sin volver a inferir días completos. Resúmenes
y ledgers parciales se preservan. Freeze válido conserva selección; freeze perdido
o corrupto con test iniciado falla cerrado. No recuperación automática de NaN,
cambio de fuentes, fallo causal o resultado económico desfavorable. `--resume`
requiere misma raíz/código/plan/autoridad y ninguna ejecución viva.

El informe distingue fit ejecutado, economía, auditoría y límites. Ningún PASS
histórico acredita recibo live, suscripción, fills reales o promoción. No git,
API, bróker, producción ni servicios durante este experimento.
