# Corrección causal del EV después de elegir la oportunidad

La comparación de frecuencias y el diagnóstico EV están cerrados. Ningún modelo
cumple beneficio adverso positivo en los ocho meses completos. Este experimento
prueba si aprender del error de las oportunidades elegidas permite abstenerse
mejor. Nace después de ver esos resultados: todo 2026 sigue SEEN_DEVELOPMENT.
No es un nuevo holdout, una garantía mensual futura ni una autorización operativa.

## Hipótesis y familia cerrada

Tres padres predeclarados: FROZEN_CONTEXT182, MONTHLY_RAW y WEEKLY_RAW. Para cada
uno se comparan CONTROL (scores originales) y FILTER (una única regla inferior).
Son seis políticas y doce libros base/adverse. Los modelos GUARDED previos ya
prueban otra intervención, la aceptación de challengers; no se combinan con esta
segunda intervención. No se selecciona una frecuencia ganadora ni se busca una
ventana, umbral, coeficiente, ticker, lado o mes después del resultado.

Se reutilizan las predicciones temporales ya auditadas de 2026, sin inferencia
nueva ni refit de los 42 estados. La corrección aprende secuencialmente de esos
scores y de etiquetas posteriores maduras. No se usan los scores de TRAIN/CAL
anteriores a 2026 como si fueran predicciones fuera de ajuste. El inicio sin
historia se conserva explícitamente; enero nunca se excluye del criterio.

## Fuentes, universo y reloj

Base local: D:/GexResearchArtifacts/weekly_multiday_20261101. Autoridades:

- h2_context_adaptation_01/manifest.json:
  e8cf5cd4a001cd98cdf29e54cf47bbdf3c34d6652abf34ef7c71fffa0bd97f23.
- h2_context_adaptation_audit_04/audit.json:
  9a487fba18504ae4faff2c1dba17d1c000eb237436a09a7fe22747e328cb307a.
- h2_context_adaptation_audit_observer_04/exit.json:
  5d59d1a3978d8d9aa31c7c3fab567d1ae7e901494aa8efb12377ca65f91de420;
  exit0 retenido, reconstrucción dados pesos guardados, no repetición del fit.
- Diagnóstico posterior EV_COMPONENT_DIAGNOSTIC_RESULT_20261101.md:
  980611e26c3badf945d95d9669b53b5f9e99ac11d462629e88a3259969d0832c.
- Criterio USER_MONTHLY_PROFITABILITY_ACCEPTANCE_20261101.md:
  806f7728a2ad434bc08929d3715f307455bd37862ae4c19a2cd2cc1d64a5ee5b.

Lista acotada de payloads, pins obtenidos del manifest upstream: candidates.jsonl
de h2_dataset_v2_01, h2_dataset_v2_extension_2026q3_partial_01 y h2_boundary_bridge_01;
coverage.json de los dos primeros y coverage_overlay.json del puente; candidate_scores.jsonl,
summary.json y los seis ledgers CONTROL de h2_context_adaptation_01. No se siguen
source_pins hacia datos raw, no se leen matrices/contexto/pesos ni nuevas fuentes.
Se verifican los pins antes y después. El binding fija código, tests y reviews.

Admisión transitiva explícita: manifest schema weekly_context_adaptation_walkforward_v1,
status PASS_SEEN_DEVELOPMENT_GIVEN_BRIDGE_AND_FROZEN_AUTHORITIES; flags exactos
models_fit/seen_development=true y api_read/broker_read/frozen_fit/future_labels_used/
production_changed/promotion_approved/raw_read=false. Auditor schema
weekly_context_adaptation_audit_v1, status
PASS_INDEPENDENT_NUMERIC_RECONSTRUCTION_GIVEN_SAVED_WEIGHTS_NOT_REFIT; flags exactos
saved_weights_used/seen_development=true y api_read/broker_read/fit_performed/
producer_imported/production_changed/promotion_approved/raw_read=false. Su
inputs.producer_manifest debe coincidir path/17599bytes/SHA con manifest admitido;
exit debe contener exit_code0. El hash de un documento no sustituye estos vínculos.

Unión original 3240 candidatos únicos, cobertura930sesiones/2790ticker-fechas;
el puente sustituye exactamente las seis filas junio29/30 por tres candidatos
CALL/PUT del29 (seis IDs), salidas julio1, y tres NO_SERIES del30. Evaluación:
178sesiones enero2–septiembre17; 612 candidatos por padre, entradas hasta
septiembre15 y salidas hasta17. Los 3060 scores upstream de cinco políticas se
validan por identidad; sólo1836 de los tres padres declarados se usan aquí.
Schema exacto de score: candidate_id,entry_date,ev_adverse,ev_base,is_bridge,
model_id,p_cal,p_model,payoff_is_lower_bound,policy,right,scenario,ticker.
Unicidad (policy,candidate_id), exactamente612 por cada una de las cinco
políticas upstream y mismos IDs comunes; identidad/fecha/lado/scenario/flag
coinciden con candidato. Probabilidades finitas, longitud5 y suma1 dentro1e-10.
Reemplazos bridge exactos (SPY/QQQ/SPXW)×(20260629/20260630), originales
HORIZON_OUTSIDE_CALENDAR: junio29 CANDIDATES_BUILT/exit20260701 y junio30
NO_SERIES/exit20260702; seis IDs del29 y ningún ID nuevo del30.

Cada padre y cada ticker/fecha forman un grupo de elección. A las10:30NY se
elige el máximo EV adverse original entre CALL/PUT disponibles. Si no hay
candidato: NO_OPPORTUNITY; si máximo<=0: WAIT; si empate exacto: WAIT. Sólo un
máximo único y positivo crea una intención y un ejemplo potencial de corrección.
La pertenencia depende exclusivamente de scores disponibles al decidir, antes
de posiciones abiertas, capital, cantidad, cotización10:35 o filtro nuevo.
No se cambia de lado cuando el filtro rechaza el máximo.

Cada día D, el historial H_p(D) contiene TODAS las intenciones anteriores del
mismo padre, con label_available_at estrictamente anterior a D00:00 NY. Se
ordena por entry_date,ticker,candidate_id. El historial es expansivo desde
enero2; no reinicia al cambiar modelo, mes o semana. Las intenciones contemporáneas
no entran aunque NO_FILL tenga madurez rápida. El corte de medianoche es
deliberadamente más estricto que el reloj de decisión10:30.

NO_FILL del candidato aporta N=0 una vez maduro. Los estados de ausencia de
salida aportan el proxy conservador neto con bid0 y flag lower_bound. Las
intenciones rechazadas por este filtro, posiciones abiertas, riesgo o capital
siguen aportando su payoff potencial cuando madura. Ninguna se elimina según
el resultado ni según si tuvo fill. No se usa el ledger para elegir H_p(D).

## Regla única, unidades y arranque

Por intención histórica j: A_j=decision_ask_j*100>0, EV_j=EV adverse original
por contrato, N_j=net_adverse por contrato incluidos los costes ya fijados.
Residuo normalizado r_j=(N_j-EV_j)/A_j. Se agrupan tickers/lados después de
normalizar por prima de decisión; no se suma PnL de distintas cantidades.

```text
n = len(H_p(D))
si n<20: correction=0; buffer=0; EV_gate=EV_raw; estado=WARMUP_RAW
si n>=20:
  mean = sum(r_j)/n
  s = sqrt(sum((r_j-mean)^2)/(n-1))
  w = n/(n+20)
  correction = min(0, w*mean)
  buffer = 1.645*w*s/sqrt(n)
  EV_gate = EV_raw + A_current*(correction-buffer)
```

Usar math.fsum en sumas canónicas. Constantes20/20/1.645 fijas, sin búsqueda.
Exigir A,EV,N,r finitos y A>0; estadísticos finitos, correction<=0,buffer>=0 y
EV_gate<=EV_raw antes de comparaciones exactas. Un valor inválido detiene el run.
El primer20 es el mínimo de observaciones para activar la regla; el segundo20
es regularización hacia corrección0, consistente con el soporte convencional
ya empleado en medias del modelo. Son elecciones de diseño, no óptimos probados.
No clipping, pesos de recencia, particiones por ticker/lado ni cambio de escala.

FILTER acepta la intención si EV_raw>0 y EV_gate>0, sin epsilon. EV_gate nunca
supera EV_raw. El buffer es heurístico; NO es un límite de confianza válido al
95%: los residuos pueden depender entre sí, variar de régimen y ser asimétricos.
EV_gate es un score conservador de admisión, no una nueva probabilidad calibrada
ni necesariamente una estimación insesgada de EV. Los p_model/p_cal no cambian.

Una intención aceptada conserva ranking, lado, quantity por riesgo y salidaH2.
El libro FILTER puede ejecutar una intención que CONTROL no ejecutó por tener
otra posición abierta; por ello sólo se exige FILTER-intenciones aceptadas
subconjunto de raw-top1-positivo, NO que sus fills sean subconjunto de CONTROL.
No afirmar que el efecto equivale únicamente a restar trades del libro anterior.

## Ejecución y comparación

Seis cuentas independientes de100000USD al2enero, sin reinicios hasta17septiembre.
Cada cuenta produce base y adverse con admisión conjunta original. Risk5000USD,
quantity10:30, guard10:35 sinresize, una posición/ticker, máximo3 total, salidas
antes de entradas, H2 fijo, prioridad SPY/QQQ/SPXW. Comisiones1.30/lado y
slippage.01base/.02adverse. Mismo tratamiento de faltantes y capacidad fullfill.
El filtro sólo interviene en la admisión del top1; ejecución/caja se mantienen.
Los EVbase/adverse guardados en ENTRY deben conservarse como pronósticos raw;
guardar EV_gate en campo separado. No presentar el buffer como coste ejecutado.

Productor puede importar únicamente funciones puras de replay_equal_risk_frozen.py
e4f42a9fa65120939cf5e131911c8f2990a9cd33d21ae036fa98d9eb816d5b9d,
sin mutar globals ni llamar main/execute. Adaptador puede marcar intención
rechazada con score interno0 para que el replay haga WAIT, y todos los candidatos
no máximos con0; conservar el score raw y motivo aparte. Si máximo<=0/empate,
mantener la razón original. Reconciliar los seis libros CONTROL con los seis
ledgers upstream tras quitar únicamente campos de política/model_id añadidos:
identidades/eventos/cantidades exactos, economía abs_tol1e-6, rtol0.
El helper se importa sólo tras verificar archivo regular sin links/reparse,
pin antes/después del import y al cierre. Si el adaptador usa un score privado
para decidir, postprocesa determinísticamente cada ENTRY: restaura ev_base y
ev_adverse raw del ID guardado y añade ev_gate separado; no cambia otro campo
económico. Auditor verifica score de decisión y campos raw independientemente.
El cierre rehashea todas las autoridades/inputs después de escribir outputs;
raíz de salida nueva y exclusiva, sin adoptar ni sobrescribir parciales.

Criterio necesario por FILTER: neto adverse por fecha canónica EXIT estrictamente
positivo en CADA mes completo enero–agosto (8/8). Un mes0 o sin trades falla.
Septiembre parcial separado. No excluir arranque, cotas, malos meses o tickers
del criterio. Ningún brazo cumple sólo por mejorar el agregado, PF o drawdown.
Cumplir8/8 no demuestra futuro ni aprueba promoción.

Reportar para los seis libros×dos costes los nueve meses con ceros, total,
H1/Q3 por EXIT, PF, DDrealizado (no MTM), trades, cantidades, capital/reservas,
WAIT/no-fill/bloqueos/cotas y concentración mayortrade/mes. Comparar FILTER
menos CONTROL por padre. Registrar fecha y n de activación, intenciones total,
retenidas/podadas y razones, historia/prefijo usado por decisión.

ErrorEV raw y gate: descriptivo por padre, TOTAL/H1/Q3/mes de ENTRADA y universos
intenciones/aceptadas/podadas, conservative_all/without_lower_bounds. La vista
sin cotas conserva NO_FILL y sólo describe: jamás alimenta una decisión distinta.
Reportar n/meanEV/meanN/bias/MAE y flags. N de intención no ejecutada es payoff
potencial por contrato, no beneficio de cartera. No exigir que MAE del gate
mejore porque incluye descuento de riesgo, no sólo corrección del promedio.

## Evidencia, pruebas y cierre

Guardar intenciones con scores raw/model_id/A/madurez; estados diarios con IDs
de historia, n/mean/s/w/correction/buffer/estado y decisiones EV_gate; doce
ledgers, summary y manifest con entradas y salidas exactas. IDs/enums/fechas/
pertenencia exactos; tolerancia1e-10 normalizados,1e-8USDscores,1e-6USDagregados,
rtol0. Fórmulas no usan tolerancias de selección. Vacíos: conteos/sumas0,
medias/MAE null. Todos los archivos nuevos, originales inmutables.

Fixtures significativos: cutoff estricto/etiqueta futura no cambia decisiones
pasadas; top1/empates/EV0; residuo normalizado entre primas; n19/20 y s0;
descenso sólo y sin rerank; aprendizaje de intenciones no ejecutadas; lowerbounds
y NO_FILL; posiciones que cambian por abstenerse; continuidad junio/julio y caja;
mutación de pins/duplicados/IDs/días fuera de cobertura. Pruebas artificiales
sólo después de contrato/review publicados. Código/tests/review y binding
publicados antes de un único runtime, con fallo preservado y sin retry automático.

Auditor separado no importa el nuevo productor ni su replay helper: reconstruye
intenciones, historia madura, fórmula, decisiones, libro y métricas con lectura
de fuentes selladas. Puede usar funciones puras del auditor económico anterior
audit_weekly_context_models.py
3eb6b9795ad260971435259858f86d3c00111bcc141973faf986411d4a68ad99,
si las declara por nombre y pin. Sin refit, inferencia ni raw marketdata. Binding
real sólo tras exit0/cierre del productor. PASS significa reconstrucción numérica
de esta política; el criterio económico se informa por separado.

Nuevos outputs prequential_ev_filter_01 y observer prequential_ev_filter_observer_01;
auditor prequential_ev_filter_audit_01 y observer independiente bajo la mismaBASE.
CPU afinidad exacta[0], ocho variables de hilo1, gate oficial RAM/free_commit>=2e9
antes de pruebas/runtime; procesos ocultos con logs y exit por handle retenido.
Helper oficial launch_monthly_test_index_v2_audit_20261024.py
3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046.
NoAPI, producción, bróker oVPS; goal activo, technical_ready/promotionfalse.
