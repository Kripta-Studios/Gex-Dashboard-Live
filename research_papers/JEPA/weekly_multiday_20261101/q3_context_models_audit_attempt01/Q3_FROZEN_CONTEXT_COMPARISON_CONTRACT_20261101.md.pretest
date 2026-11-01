# Contraste temporal Q3 de los tres modelos congelados

Este contrato se fija antes de scores contextuales Q3. H1 ya está visto: el
contexto mejoró el neto pero empeoró logloss. No se cambia esa conclusión ni
se selecciona CONTEXT182 por ser el positivo. Evaluar BASE18_FROZEN, CATEGORY30
y CONTEXT182 sobre exactamente el mismo universo Q3 y publicar los tres.

## Inputs y estado estadístico

Raíz base D:/GexResearchArtifacts/weekly_multiday_20261101.
Q3 dataset h2_dataset_v2_extension_2026q3_partial_01, manifest
b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b:
180 candidatos,165ticker-fechas y55sesiones20260701–20260917; última entrada
20260915. Calendar JSONac9bd256 yParquete16ef041, manifest5a530747, completos
según el contrato de extensión contextual87753994. Preservar todas las
ausencias y cotas existentes, sin cambiar identidades/labels/quotes/payoffs.

BASE18 reutiliza scores Q3 ya auditados del paquete
h2_ev_frozen_extension_2026q3_partial_01, manifest
7bd50a5a1fe5214df2c4281e785313f0fb016ca73d725d682788dcb78b283d8e;
candidate_scores.jsonl9458c8dfa75983784af0e7514feec1ded43a42adadecfb07c0406aee3f284ca6.
No volver a ajustar ni inferir BASE18. Sus dos libros deben ser idénticos a
los Q3 del paquete h2_equal_risk_frozen_01, manifest
50fa6b7a02aad9d122dc0bfdd84f8c01f9a5f468bafc7f175eed39aa3ea9418d.
Los controles ALWAYS_CALL/PUT/ABSTAIN se citan desde ese paquete, sin reejecutar.

Dos nuevos modelos ya congelados en h2_context_model_comparison_01, manifest
662ac63eaa2895beff4363b9e94a97cd7adc91aac3558139bdd919d8fbf2861a:

| Archivo | SHA256 |
|---|---|
| category30_model.json | e927fe4e2e9b796c2f41f0cdb36a713fd72101b5bbbb8c8131c2be7f84224b5c |
| category30_transform.json | dbbab2c4a774e43e69269a5b0b9c7ed06f61b105b8cc96196464f83ba740584d |
| category30_calibration.json | 1201fbd5dbbc6d6e4aae6149ee5349e2773a7bb659cb45a51cea44e7d9fd9ba1 |
| context182_model.json | 7a9dafc2a8c30c83ef2177057ceeb6fa33636f2943821cee83172b703cc17037 |
| context182_transform.json | 82b31bc61ad94f462b724a49d1cfd6793aebfc361afd3111e5c27dc1d16539c0 |
| context182_calibration.json | 5a9dc85fba737b0e2921968c711ce14780da2b3aa7a27f87bd025cf0954bc14c |

Audit H1 del paquete h2_context_model_comparison_audit_01:
bb661fe916f65ed6ee40dd3cf684650a8d318447005a7f224edec6a4b814b3eb.
Prior ymedias del paquete original
D:/GexResearchArtifacts/weekly_multiday_20261101/h2_ev_v2_01:
model.json68712c7c326d2337a34f8401579ddc52a4dab0e3f505c8c4ff2f1b1d51c03fb4;
conditional_means.jsona8dc329233ce431b282c500e27cf91ac91d845cbb6a1fc752cee36026aef3f90;
manifest.json54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96.
No reestimar prior, medias, imputer o scaler.

Contexto nuevo h2_context_q3_1030_01: exigir manifest externo concreto,
cierre del productor y auditoría de contexto completos. Sus pins aún no
existen y se fijarán en binding posterior publicado antes del único scoring.
No leer raw ni matrices completas: sólo context.jsonl ycoverage conB81/máscaras.

## Inferencia y decisiones

Join exacto many-to-one por ticker/entry_date, sin filtrar candidatos por
state_valid o datos ausentes. CATEGORY30 usa las mismas30celdas; CONTEXT182
usa18+81+81signadas+2flags, con regla congelada available-invalid→cero81/flags1,0,
missing→cero81/flags0,0, available-valid→vector81/flags1,1. No cambiarorden/nombres.

Aplicar mediana TRAIN y los indicadores guardados; escalar con mean/scale
guardados. Inferencia multinomial desde coef/intercept/clases guardados;
ninguna llamada fit o calibración, sin construir optimizador. Mezclar con prior
alphaCATEGORY0,3 yalphaCONTEXT0,6 ya guardados. EV por contrato = decision_ask×100
por suma deprobabilidades×mean_yTRAIN para cada ticker/lado/clase/coste.

Mantener selección top1 por EV adverso unitario>0 y empate→WAIT. No rankear
por cantidad×EV. Replay con riesgo máximo5000USD, comisiones1,30por lado y
slippage0,01base/0,02adverse, qty fijada10:30 y guard10:35, capital100000USD,
unaposición/ticker, máximotresglobales ysin carryH1. Cada modelo ycoste empieza
con100000USD frescos. Dentro de cada modelo los dos costes comparten candidato,
cantidad, identidadtemporal yeventos ENTRY/NO_FILL/CAPITAL_BLOCKED: la admisión
adverse de5000gobierna ambos, con prueba de efectivo/comisiones de ambos libros
según replaycongelado; no divergir ni redimensionar a10:35.
Salidas H2 y missing conservadores intactos.
Tresmodelos×doscostes=seislibros. BASE18 debe reproducir exactamente los dos
librosQ3 de riesgo congelado antes de publicar cierre.

Se permite importar funciones puras pineadas de evaluate_weekly_context_models.py
bdc6534f059ade7acc58f23952a88ed2068c7a712518b04f438945a583a07a2f
para representación/métricas y replay_equal_risk_frozen.py
e4f42a9fa65120939cf5e131911c8f2990a9cd33d21ae036fa98d9eb816d5b9d
para replay/estadísticos, sin main, mutación de globals o fit. La inferencia
guardada se implementará explícitamente sin usar el auditor como productor.

## Comparaciones y cierre

Métrica primaria sigue siendo logloss global en180candidatos, diferencia
pareada BASE18 menos CONTEXT182. Reportar también CATEGORY30, Brier/reliability,
EV bias/MAE, all/observed-only/selected/selected-observed, cotas yconteos; no
equiparar selected de modelos diferentes a una comparación en filas comunes.
No se añaden gates de selección. Economía: neto,PF,DDrealizado,mes,ticker,lado,
cantidades, abstenciones/no-fill/capitalblocked/ausencias, concentración mayor
operación y mes (restas descriptivas, no políticas). H1 yQ3 separados.

Mismo bootstrap exploratorio logloss:55sesiones,incluyendo ceros, bloques
circulares5,10000remuestras,random.Random(20261101),11inicios uniformes por
remuestra,percentiles type7. Todos180candidatos elegibles; denominador0 falla,
sin nueva semilla. No p-value, holdout limpio o afirmación prospectiva.

Snapshot inmediato de manifests y payloads al admitir, rehash cierre/postwrite;
fuentes/autoridades deben estar cerradas y publicadas. Outputnuevo
h2_context_model_comparison_q3_01, sin overwrite/resume. Scorer, fixtures y
review antes de único run conCPU0/hilo1/gateRAMcommit2GB/logs/exitretenido.
Auditor numérico independiente posterior: restaurar mismos parámetros sinfit,
matrices/probabilidades/EV/seislibros/métricas, sin importar scorer. Reutilizar
funciones independientes del auditorH13eb6b979 sólo si no son usadas por scorer.

Q3_PARTIAL_2026_SEEN_DEVELOPMENT: fechas ya vistas, sin selección/promoción.
Ni positivo ni negativo completan por sí solos el goal general; entradas por
toque Fibonacci y salidas por walls permanecen fuera de esta prueba H2.
Sólo datos locales, sin API ni producción/bróker/VPS.
