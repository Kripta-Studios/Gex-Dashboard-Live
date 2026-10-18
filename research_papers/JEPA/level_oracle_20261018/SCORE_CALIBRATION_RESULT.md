# Calibración descriptiva de scores guardados

No se ha ajustado ningún modelo, generado nuevas predicciones ni cambiado la selección. Todos los resultados son desarrollo histórico ya visto.

Se evalúan **todas las acciones ofrecidas**, no trades ejecutados. Las filas comparten estados y trayectorias; sus millones de valores no son millones de observaciones independientes. No se calculan significaciones iid ni bootstrap por acción.

Score y target se dividen por la misma escala de riesgo congelada de entrenamiento. El sesgo es predicción menos target. `gbt_advantage` se contrasta con ventaja DP privilegiada; sus métricas no representan calibración de retorno esperado.

| Periodo | Ticker | Modelo / target | Acciones | Media score | Media target | Sesgo | RMSE | R² | Score > 0 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| validation | SPXW | gbt_net / net_base | 1,581,790 | -0.02215 | -0.07541 | 0.05326 | 1.24329 | -0.0204 | 27.73% |
| validation | SPXW | gbt_advantage / dp_advantage | 1,581,790 | -1.69218 | -2.05346 | 0.36129 | 2.57294 | 0.3034 | 0.00% |
| validation | SPXW | tcn_teacher / net_base | 1,581,790 | -0.05560 | -0.07541 | 0.01981 | 1.22725 | 0.0058 | 1.01% |
| validation | SPY | gbt_net / net_base | 1,442,783 | -0.08499 | -0.12528 | 0.04029 | 1.08746 | -0.0250 | 11.53% |
| validation | SPY | gbt_advantage / dp_advantage | 1,442,783 | -1.53012 | -1.80671 | 0.27659 | 2.39996 | 0.2728 | 0.00% |
| validation | SPY | tcn_teacher / net_base | 1,442,783 | -0.08503 | -0.12528 | 0.04026 | 1.07229 | 0.0034 | 0.36% |
| validation | QQQ | gbt_net / net_base | 1,548,580 | -0.06972 | -0.12889 | 0.05916 | 1.08267 | -0.0467 | 16.89% |
| validation | QQQ | gbt_advantage / dp_advantage | 1,548,580 | -1.72035 | -1.87389 | 0.15353 | 2.21996 | 0.2820 | 0.00% |
| validation | QQQ | tcn_teacher / net_base | 1,548,580 | -0.09026 | -0.12889 | 0.03863 | 1.05662 | 0.0031 | 0.00% |
| test | SPXW | gbt_net / net_base | 853,617 | -0.00814 | -0.06184 | 0.05370 | 1.27459 | -0.0232 | 31.53% |
| test | SPXW | gbt_advantage / dp_advantage | 853,617 | -1.74880 | -2.32776 | 0.57897 | 2.68339 | 0.2617 | 0.00% |
| test | SPXW | tcn_teacher / net_base | 853,617 | -0.05301 | -0.06184 | 0.00884 | 1.25984 | 0.0003 | 0.25% |
| test | SPY | gbt_net / net_base | 734,531 | -0.05020 | -0.10904 | 0.05884 | 1.12854 | -0.0187 | 21.36% |
| test | SPY | gbt_advantage / dp_advantage | 734,531 | -1.42272 | -1.97585 | 0.55313 | 2.24691 | 0.2104 | 0.00% |
| test | SPY | tcn_teacher / net_base | 734,531 | -0.07978 | -0.10904 | 0.02925 | 1.11860 | -0.0009 | 0.00% |
| test | QQQ | gbt_net / net_base | 818,542 | -0.04622 | -0.11422 | 0.06800 | 1.28289 | -0.0098 | 25.10% |
| test | QQQ | gbt_advantage / dp_advantage | 818,542 | -1.90962 | -2.37205 | 0.46243 | 2.59688 | 0.2326 | 0.00% |
| test | QQQ | tcn_teacher / net_base | 818,542 | -0.08519 | -0.11422 | 0.02903 | 1.27709 | -0.0007 | 0.01% |

Los ocho bins fijados antes de abrir scores son `[-inf,-.1,-.05,-.02,0,.02,.05,.1,inf]`, cerrados a izquierda y abiertos a derecha. `bins.csv` conserva n/media score/media target de los 144 grupos-bin, incluidos bins vacíos. Un cero pertenece a `[0,.02)` pero no cuenta como score positivo.

Un RMSE bajo no demuestra rentabilidad de la política. Un sesgo positivo no demuestra que restar una constante mejore su economía. Este diagnóstico no selecciona bins, filtros, modelos o umbrales; la política congelada y sus resultados ejecutados se evalúan por separado.

Escalas USD congeladas: `{'SPXW': 680.0, 'SPY': 81.0, 'QQQ': 88.0}`. Salida: `D:\GexResearchArtifacts\level_oracle_20261018\score_calibration_v1`.

Se verificaron completion del motor, índice auditado, binding de freeze, normalizers y manifests, hashes de cada NPZ y de los sidecars consumidos, y el orden exacto de action_ids. Esto no refittea modelos ni sustituye la auditoría independiente de ejecución de los aprendices.

Estado de auditoría independiente de aprendices al arrancar: `UNVERIFIED_AT_DIAGNOSTIC_RUN`. Si no se proporcionó un audit PASS con binding comprobado, el estado es UNVERIFIED y no se afirma validación independiente. Código SHA `67f7aa51b8cff2331153e69d5c1aa52808d653dc480930a4b0e2c85269b1f4f4`; especificación SHA `24c0915cac71734b8e3fe2d8da55680f5199977f6b4d92a7dcf3a9bdb7d67255`.

## Interpretación y separación de resultados

Los 1.104 ticker-días contienen 6.979.843 acciones distintas de día/identidad: 4.573.153 en 2025 y 2.406.690 en 2026H1. Cada modelo se compara con ese mismo universo. No se multiplican esos tamaños por tres para afirmar observaciones adicionales. Las escalas de riesgo son 680 USD en SPXW, 81 en SPY y 88 en QQQ.

**GBT neto:** R² es negativo en los seis grupos, de −0,0467 a −0,0098. En este diagnóstico eso significa un error cuadrático mayor que el predictor constante igual a la media realizada de cada grupo, que es una referencia descriptiva retrospectiva, no una política causal. En 2026, el sesgo medio positivo equivale a +36,52/+4,77/+5,98 USD por acción en SPXW/SPY/QQQ. Tener scores positivos en 31,53%/21,36%/25,10% de las acciones no demuestra que exista esa proporción de oportunidades rentables. Tampoco hay un orden estable entre score y media realizada de todos los bins: por ejemplo, el bin superior de SPXW cambia de media target −0,1542 en 2025 a +0,0308 en 2026. Esta observación no selecciona el bin de 2026 ni prueba una inversión rentable de la señal.

**TCN con teacher:** R² permanece muy cerca de cero (2025: 0,0031–0,0058; 2026: −0,0009–0,0003). Predominan scores negativos. Hay 16.054/5.246/60 scores positivos en 2025 y 2.114/0/88 en 2026 para SPXW/SPY/QQQ, respectivamente. La tabla redondea porcentajes pequeños a 0,00%; los CSV preservan los conteos exactos. La predicción económica se concentra alrededor de pérdidas pequeñas; estos agregados no permiten atribuir la causa a capacidad de red, pérdida, representación o ausencia de señal. Un error global bajo puede coexistir con un mal orden de las escasas acciones seleccionadas.

**GBT de ventaja DP:** R² es mayor (2025: 0,2728–0,3034; 2026: 0,2104–0,2617), pero está midiendo otro target: ventaja frente a WAIT bajo continuación privilegiada del oracle. No es retorno esperado. Los scores positivos son solo 19/22/36 en 2025 y 0/15/14 en 2026. Por tanto, explicar parte de la variación entre muchas ventajas muy negativas no demuestra capacidad para identificar la cola positiva que decidiría una entrada. Las medias y R² por acción tampoco miden por sí solos la calidad del ranking dentro de cada estado; no se ha calculado una métrica nueva de ranking ni ajustado nada con ella.

La selección predefinida en validación eligió `gbt_advantage__10`: dos trades en 2025, +40,80 USD base y +36,80 adverso. En 2026 esa política ejecutó cero trades y produjo cero USD. El diagnóstico de calibración es coherente con la escasez de scores de ventaja positivos, pero no sustituye el scheduler ni acredita rentabilidad por abstenerse. Los resultados ejecutados de las otras políticas son diagnósticos separados. Por ejemplo, el TCN a umbral 5 obtuvo +2.490,60 USD base con 19 trades en 2026, pero no fue la política seleccionada en 2025; escogerlo ahora sería selección retrospectiva. No se propone cambiar el umbral, invertir señal, recalibrar o rescatar un ticker/bin.

## Procedencia y verificación

La ejecución empezó después de `learners_v1/summary.json` COMPLETED y `learners_v1_runtime_v2/completion.json` COMPLETE con exit_code 0. Solo consumió predicciones y sidecars ya publicados; no cargó modelos ni ejecutó inferencia. Se comprobaron 1.104 NPZ contra manifests y cobertura exacta, 3.312 hashes de acciones/labels/advantages contra el índice del motor y sus IDs. Los fixtures focales son 7 PASS; compile y Ruff del módulo y tests PASS. La revisión independiente de código de wide_audit motivó comprobaciones explícitas de archivos extra, raíz auditada y binding de auditoría.

Salida sellada: `D:/GexResearchArtifacts/level_oracle_20261018/score_calibration_v1`. Summary SHA `7bd7ef4bc9c88ba0c9ec28d2f43cd9ff07acf0bd64c4c69c49c0a4c87fb4df6f`; groups.csv SHA `357481b0c85143674d0f6ab0a69ac8e0d6dfac024b21171568a99315f14cb654`; bins.csv SHA `aff8eeb0591437601c64f4e5be92a4b2e04485be42f17460bdf20ea676f2d133`. Código y spec ejecutados están copiados en esa raíz. La auditoría económica de los aprendices estaba pendiente al calcular; la constancia posterior de la sección siguiente enlaza el PASS con binding exacto y conserva los agregados originales.


## Constancia posterior de auditoría

La auditoría económica independiente terminó con `PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT`, alcance `ECONOMIC_EXECUTION_GIVEN_SEALED_PREDICTIONS`. Se verificaron los mismos hashes de summary, freeze, manifests de validación/test, índice y completion del motor, y la misma raíz de aprendices. Audit: `D:/GexResearchArtifacts/level_oracle_20261018/learners_v1_economic_audit/audit.json`, SHA `238e6f0974025edf076d4023f134878340141271547e45e618026042539945bd`. Constancia: `score_calibration_v1/audit_binding.json`.

Los agregados originales conservan `UNVERIFIED_AT_DIAGNOSTIC_RUN` porque la auditoría aún no había terminado al arrancar. No se recalculó ninguna métrica ni se alteró la selección. Este PASS reconstruye ejecución económica condicionada a predicciones selladas; no reproduce entrenamiento, inferencia neuronal o tensor de features, ni garantiza paridad live.
