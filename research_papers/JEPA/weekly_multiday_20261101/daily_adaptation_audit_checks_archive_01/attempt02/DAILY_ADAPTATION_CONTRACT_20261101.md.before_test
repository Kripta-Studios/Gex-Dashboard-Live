# Frecuencia diaria frente a mensual y semanal

El turno anterior produjo evidencia nueva: el filtro EV se cerró con auditoría
independiente y falló el criterio mensual en sus tres variantes. Esta prueba
responde a la pregunta del usuario sobre reentrenar diariamente. Compara sólo
la frecuencia; no modifica los experimentos cerrados ni retoca el filtro fallido.
Todo2026 ya es SEEN_DEVELOPMENT. No es un holdout nuevo ni una garantía futura.

## Familia, calendario y autoridad

Cuatro políticas fijas: FROZEN_CONTEXT182, MONTHLY_RAW, WEEKLY_RAW, DAILY_RAW.
No GUARDED, filtro EV, recencia, ventana nueva, ticker elegido o búsqueda de
umbrales. Mismos612candidatos por política,2448scores y ocho libros base/adverse.
Historia20230103–20260917;178sesiones de evaluación20260102–20260917, entradas
hasta20260915. CAL y TRAIN usan el calendario común completo930sesiones.

DAILY crea un estado por cada una de las178sesiones, independientemente de
que exista oportunidad. Hay42fechas ya entrenadas:4MONTHLY exclusivas,
33WEEKLY exclusivas y5compartidas. Se reutilizan esos42estados sin fit ni
mutación y se ajustan136 nuevos. Sep16/17 son estados terminales sin candidatos
ni efecto económico; se etiquetan terminal_unused_for_scoring=true. Otras
sesiones sin candidatos también conservan su estado. No omitir fechas por PnL.

Base local D:/GexResearchArtifacts/weekly_multiday_20261101. Autoridades cerradas:

- h2_context_adaptation_01/manifest.json:
  e8cf5cd4a001cd98cdf29e54cf47bbdf3c34d6652abf34ef7c71fffa0bd97f23.
- h2_context_adaptation_audit_04/audit.json:
  9a487fba18504ae4faff2c1dba17d1c000eb237436a09a7fe22747e328cb307a.
- h2_context_adaptation_audit_observer_04/exit.json:
  5d59d1a3978d8d9aa31c7c3fab567d1ae7e901494aa8efb12377ca65f91de420, exit0.
- states.jsonl d9313b329b4543aecd1aaad39116aa13eff3efad271e9931916caa91feeac475;
  fit_plans.json c120c8de05dfb98b85e6ad942a2f7400baac0297e0bd80d0d2c2f05194a0e6fb;
  candidate_scores.jsonl9acae826edba3b712fb67b448d5711778c0af99bb027800d3a6626ddc4b02a4f;
  summary.json1ad1dbca873d255b431a2e097be169b0ad91913b728fbe2a2478f2d30212049f.
- Puente auditado: h2_boundary_bridge_01/manifest.json
  9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86;
  h2_boundary_bridge_audit_01/audit.json
  83c9ade0b6b7205484dd275df8593107238f94468d8564f7351e9481a475033c.
- Criterio USER_MONTHLY_PROFITABILITY_ACCEPTANCE_20261101.md
  806f7728a2ad434bc08929d3715f307455bd37862ae4c19a2cd2cc1d64a5ee5b.

Admisión valida schema/status/flags del manifest adaptación y audit04, enlace
audit.inputs.producer_manifest exacto por path/17599bytes/SHA y exit0. Las fuentes
de candidatos/cobertura/contexto H1/Q3, puente, frozen y sus auditorías son las
mismas autoridades transitivas declaradas por adaptación. Cada payload que se
abra debe figurar por ruta exacta/bytes/SHA en esas autoridades, antes y después.
Se consumen también los seis ledgers de los tres controles y los cuatro archivos
adaptación nombrados arriba. Nada de raw D:/ThetaData, API o nuevas extracciones.
Unión3240candidatos únicos,2790ticker-fechas y puente exacto junio29/30; seis IDs
nuevos del29 con salida julio1 y tres NO_SERIES del30. Sin nueva exclusión.

## Ajuste causal idéntico

As-of de creaciónD: D00:00 America/New_York. Se supone fit disponible antes de
decisión10:30; no se acredita latencia live. Si D tiene índicei en calendario:

```text
CAL_sessions = full_calendar[i-65:i-2]       # 63 sesiones exactas
TRAIN = entry_date < CAL_start AND label_available_at < CAL_start00NY
PURGED = entry_date < CAL_start AND label_available_at >= CAL_start00NY
CAL = entry_date in CAL_sessions AND label_available_at < D00NY
```

IDs ordenados canónicamente, TRAIN/CAL/purgados y máximos de madurez guardados.
NO_FILL y cotas mantienen semántica upstream; no rellenar etiquetas/quotes.
Al menos dos clases TRAIN y CAL no vacío. TRAIN expansivo desde20230103,
sin recency ni warm start. CAL no entra en imputer/scaler, prior o medias.

Receta exacta del productor congelado d03494bf: CONTEXT182 (18+81+81×side_sign+2flags),
misma unión de contexto10:30 y flags de ausencia/invalidez; mediana+indicadores
y StandardScaler sólo TRAIN. LogisticRegression L2 efectiva,C1,lbfgs,
max_iter2000,random_state0,warm_startfalse,class_weightNone,l1_ratio0, omitiendo
penalty en sklearn1.8 tal como el helper sellado. Misma versión instalada y
receta que los42estados; divergencia de versión o cualquier warning aborta,
sin cambiar parámetros ni repetir automáticamente. Guardar versión/coeficientes/
interceptos/clases/transform, prior/support y medias normalizadas por
decision_ask×100, célula ticker/right/clase con shrink20 a media global de clase.

Alpha en0,.1,…,1 minimiza loglossCAL, empate alpha menor; mezcla
(1-alpha)p_model+alpha*priorTRAIN. No reentrenar después de CAL. EV por contrato
en ambos costes con medias TRAIN. Los coeficientes siguen sin aprender de las
63sesiones recientes reservadas para CAL; aumentar frecuencia no elimina ese
retraso. El full refit conserva historia, pero no acredita estabilidad ni ausencia
de regresión económica. No se añade EWC o una arquitectura neuronal.

## Reutilización y predicciones

Se construye externamente un plan para cadaD. En las42fechas coincidentes, todos
los campos científicos del plan deben igualar el plan sellado; sólo la etiqueta
frequencies de la agenda DAILY vive fuera del objeto original. Los estados
originales conservan sus frequencies/coeficientes/transform/prior/medias/alpha.
Se referencia el archivo fuente pineado y la fila/ID, no se reserializa como
si fuera un nuevo ajuste. Los136planes nuevos usan mismas claves PLAN_KEYS y
frequencies=['DAILY']; state_id='CONTEXT182_'+D. Agenda178 y newstates136 separadas.

Productor en fechas coincidentes copia p_model/p_cal/EV/model_id del score
upstream del mismo estado y candidato; si mensual y semanal comparten ese
estado, ambos valores deben ser exactamente iguales. No reinferencia de esos
42estados por el productor. Fecha sin candidato registra score_count0. Para
cada nuevo estado se comprueba paridad runtime/pesos guardados en los primeros
siete IDs CAL (o todos si hay menos); evaluación usa sólo pesos guardados.
DAILY score deD siempre procede del estadoD; no elegir estados por rendimiento.

Los1836scores de los tres controles se conservan, con sus filas fuente exactas;
los612scores DAILY añaden policyDAILY_RAW y flags originales. Los seis libros
control se copian byte a byte desde upstream, sin nuevo replay o selección
por productor. El auditor sí reconstruye los ocho libros independientemente.
Se calculan métricas de todos por reglas idénticas; controles deben reconciliar
contra summary upstream además de contra sus ledgers copiados.

## Trading y criterio

DAILY inicia100000USD una vez, cartera continua hasta17septiembre. Top1 EV
adverse estrictamente>0 por ticker, empateWAIT; sin rerank/threshold nuevo.
Cantidad decidida10:30 por riesgo5000USD adverso (prima+ambascomisiones),
entrada10:35 con guard sinresize, H2 a10:35, una posición/ticker y máximo3.
Orden SPY/QQQ/SPXW, salidas antes de entradas, sin reset al reentrenar o cambiar
mes/H1/Q3. Posición abierta mantiene salida/cantidad/model_id de entrada.
Fees1.30porlado, slip.01base/.02adverse, affordability conjunta base/adverse,
missingbid0 como cota y fullfill supuesto. Nada de volumen/MTM nuevo.

DAILY debe ganar neto adverse estrictamente>0 por fecha EXIT en CADA mes
completo enero–agosto (8/8); cero/sin trades falla. Septiembre parcial aparte.
No se exige que un control pase para evaluarDAILY. Mejorar frente al semanal,
tener agregado positivo o reducirDD no sustituye8/8. Ninguna frecuencia se
promociona por comparación retrospectiva; todo2026SEEN, selecciónnull.

Reportar cuatro políticas×dos costes:9meses con ceros, H1/Q3 por EXIT y cohortes
ENTRY separadas, total/PF/DDrealizado/trades/qty/capital/no-fill/WAIT/cotas,
tickers/lados, mayortrade/mes y restas descriptivas de concentración. Comparación
DAILY−WEEKLY y DAILY−MONTHLY por mes/total, no nuevas políticas. Probabilidad/EV
ALL y SELECTED, todos/sin cotas, misma logloss/Brier/reliability/bias/MAE upstream.
Diagnóstico por estado: nTRAIN/CAL/purgados, soporte clases, prior y alpha;
por candidato común diferencia p/EV DAILY−WEEKLY y si cambia top1, sólo descriptivo.
No usar este diagnóstico para filtrar, cambiar frecuencia o seleccionar estados.
Estados diarios solapados no son178experimentos independientes.

## Código, evidencia y ejecución

Código nuevo evaluate_weekly_daily_adaptation.py. Helper productor adaptación
d03494bf68e281bc7c9e68f385aa111567eac4206cf5b44133e17bb480ed5df8
puede importarse por SHA, sin mutar globals, usando sólo admit_sources,
calendar_dates,load_context_union,fit_state,score_state,strip_runtime,
attach_scores,enrich_ledger,generic_metrics,economic_details y sus dependencias
puras. Nunca llamar creation_dates/build_fit_plans,simulate_guard,execute_admitted,
finish_evaluation,run/main. Metadatos del helper se declaran como dependencia,
no se confunden con la identidad del productor nuevo.
Dependencias científicas directas:

- evaluate_weekly_context_models.py bdc6534f059ade7acc58f23952a88ed2068c7a712518b04f438945a583a07a2f.
- evaluate_weekly_h2_ev_v2.py 8a9e75855d542a12662e5c812583f2ef86042f5c3ae1bbbad73c16042e063476.
- replay_equal_risk_frozen.py e4f42a9fa65120939cf5e131911c8f2990a9cd33d21ae036fa98d9eb816d5b9d.

Outputs mínimos: daily_fit_plans.json178, daily_schedule.json178 consource
REUSED/NEW/state_id/used_for_scoring/terminalflag, daily_states_new.jsonl136,
candidate_scores.jsonl2448, ocholedgers, summary.json ymanifest. Cada nuevofit
registra inicio/cierre UTC,asof,gate yhash de estado en journal; persistir estados
completos durante ejecución para observar progreso. Un parcial es evidencia,
no autoriza resume/adopción. Si fallo, conservar y parar; cero retry automático.
Los42reused no producen fit_start/fit_complete. Cierre exige136fits terminados,
178mapping,612scoresDAILY, todos los inputs idénticos y exit0 retenido.

Auditor separado audit_weekly_daily_adaptation.py no importa productor daily ni
helper científico d034. Puede usar funciones puras de auditorV4
0723696ae01dcc86af7c2af8e8fdc2e3b281ba913987a65d95bd4703c959aa9c
(derive_split,validate_saved_state,score_state,restored_probabilities_adaptation,
conditional_means,extended_book_metrics y utilidades de pin/fechas) y helper
audit_weekly_context_models.py3eb6b9795ad260971435259858f86d3c00111bcc141973faf986411d4a68ad99.
No mains ni globals modificados. Reconstruye splits/transform/prior/medias/
alpha de178estados, valida42reused por archivo/ID exacto y136new, inferencia
desde pesos y2448scores, ocho libros/métricas. Sin refit ni raw. PASS significa
reconstrucción dados pesos guardados, no repetición de entrenamiento sklearn.

Tolerancias: probabilidades/transform/medias1e-12, EVfila1e-8USD, agregados y
ledger1e-6USD,rtol0; IDs/enums/clases/cantidades/selección/calendario exactos.
La selección no usa epsilon. Fuentes/code/deps regulares sin symlink/reparse,
allowlists cerradas de rutas y hashes; rehash tras todos los outputs escritos.

Fixtures:178/42/136,terminal2,63CAL+gap2/madurez estricta/purga, futuros no
cambian pasado, nofit de42reusados/no mutación, coincidencia scores, paridad
pesos/binario, ledgercontinuo/posiciónabierta/puente, meses0 ycriterio8/8,
duplicados/tamper/path escape y conteo real de llamadas fit. Publicar este
contrato/review antes de fixtures; código/tests/review ybinding real antes
del único run. Auditor real sólo tras cierre/exit0productor ybinding nuevo.

Raíces nuevas h2_daily_adaptation_01, h2_daily_adaptation_observer_01,
h2_daily_adaptation_audit_01 y h2_daily_adaptation_audit_observer_01 bajoBASE.
CPUafinidad exacta[0], ocho variables1 y gateoficial RAM/free_commit>=2e9 antes
de cada nuevofit y runtime/pruebas; guardar observación antes del gate incluso
si rechaza. Helper3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046
en level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py.
Procesos ocultos,argslist,logs yexit porhandle retenido; no basta receipt de
artefactos. Sólo investigación local, sin API/producción/bróker/VPS.
Goal activo, technical_ready=false,promotion_approved=false.
