# Actualización mensual y semanal con protección prospectiva contra regresión

El usuario autoriza expresamente el1noviembre2026 investigar si reentrenar y
ajustar cada mes o semana mantiene rentabilidad y cómo evitar olvido/regresión.
Esta familia responde a esa instrucción. Los experimentos previos permanecen
cerrados. Q3 congelado ya se vio y falló: todo este ensayo es SEEN_DEVELOPMENT,
no un holdout nuevo, ni una promesa de rentabilidad futura.

## Hipótesis y universo

Comparar cinco políticas sobre exactamente los mismos candidatos weeklyH2:
FROZEN_CONTEXT182, MONTHLY_RAW, WEEKLY_RAW, MONTHLY_GUARDED, WEEKLY_GUARDED.
No otras arquitecturas, ventanas, umbrales de trading o selección por ticker.
Toda política admite WAIT. Representación182 y ejecución H2 permanecen iguales.

Historia local20230103–20260917. Evaluación20260102–20260917,178sesiones;
decisión10:30NY, entrada10:35, salida10:35 de la segunda sesión posterior.
La unión de calendarios H1/Q3 contiene930sesiones/2790ticker-fechas. Los
datasets previos aportan3054+180candidatos; su unión no basta: las seis filas
junio29/30×SPY/QQQ/SPXW estaban HORIZON_OUTSIDE_CALENDAR por corte deH1.
Antes del run se exige puente separado, revisado y auditado, que reconstruya
sólo esas seis filas con salidasjulio1/2 y reglas originales. Conservar los
originales y reconciliar sustitución exacta, sin excluir oportunidades por
resultado. El puente fijará sus pins/counts reales en binding posterior.
Septiembre16/17 siguen como final fuera de horizonte, explícitos para todos.
El contexto0DTE de junio29/30 ya está en el paquete H1; no nueva extracciónB81.

Autoridades selladas bajo D:/GexResearchArtifacts/weekly_multiday_20261101:

- h2_dataset_v2_01/manifest.json bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8;
  h2_dataset_v2_extension_2026q3_partial_01/manifest.json b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b.
- h2_context_1030_01/manifest.json 77aaf00d60accc071ff1f58ec099cee72bc3a4150f89e4ad41a601821a74a38a;
  h2_context_q3_1030_01/manifest.json 1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66;
  contextauditQ3 ae90d005b6fa9a3a1a708fdfafd3361bdef9146312ddda324d103a139cd18633.
- h2_context_model_comparison_01/manifest.json 662ac63eaa2895beff4363b9e94a97cd7adc91aac3558139bdd919d8fbf2861a;
  auditH1 bb661fe916f65ed6ee40dd3cf684650a8d318447005a7f224edec6a4b814b3eb.
- h2_context_model_comparison_q3_01/manifest.json dcdc8b0bef5a508f40b322ba632109d4afaff689a3d0d36514f30d8618531e66;
  auditQ3 ef6a325b8f4defc579aa568ebd9dc980ede750e106a8ef4578b025d999215f69.
- Prior/medias frozen del paquete h2_ev_v2_01: manifest54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96,
  model68712c7c326d2337a34f8401579ddc52a4dab0e3f505c8c4ff2f1b1d51c03fb4,
  conditional_means a8dc329233ce431b282c500e27cf91ac91d845cbb6a1fc752cee36026aef3f90.

Contexto: join exacto ticker/entry_date, sin filtrar missing/invalid. B81 válido
se conserva; invalid→ceros/flags1,0; missing→ceros/flags0,0. Orden182 exacto
18+81+81×side_sign+2flags, conforme contrato contextual8a535acd.

## Reloj de creación y ajuste

Fechas mensuales: primera sesión del mes dentro del bloque (9).
Fechas semanales: primera sesión de cada ISO año/semana dentro del bloque (38),
incluido arranque20260102. Coinciden5fechas:0102,0202,0302,0601,0803.
Crear42estados físicos únicos; ambas frecuencias referencian el mismo estado
si comparten fecha. No duplicar fits para obtener otra semilla o resultado.

As-of lógico de cada creación D: D00:00 America/New_York. Se supone que el fit
termina antes de10:30; el ensayo no acredita latencia real de entrenamiento.
El motor debe ordenar información por reloj simulado aunque los ficheros
históricos contengan todo el periodo. No alimentar outcomes futuros al fit.

CAL: últimas63sesiones oficiales de entrada cuyo H2 termina en una sesión
anterior aD. Se determina por calendario común, no por existencia de trades,
cotización o rendimiento. Si D está en índice i, CAL=calendario[i−65:i−2].
TRAIN: todas las entradas desde20230103 anteriores al primer día deCAL, y
label_available_at estrictamente anterior a CAL_start00:00NY. Así se purgan
labels cuyo H2 invade CAL. CAL admite sólo su rango exacto y labels anteriores
aD00:00NY. Nunca usar entry_date como sustituto de madurez. NO_FILL conserva
su label disponible enentrada; missing exit conserva cota y reloj de salida.

Fresh LogisticRegression L2,C1,lbfgs,max_iter2000,random_state0,warm_startfalse,
sin class weighting ni búsqueda. Imputer mediana+indicadores, columnas vacías
conservadas y StandardScaler sólo TRAIN. Persistir IDs/fechas/madurez deTRAIN,
CAL y purgados, transform, coef/intercept/classes, versiones ywarnings.
Al menos2clasesTRAIN yCAL no vacío; fallo técnico/convergencia se preserva y
no autoriza cambiar ventana,C,semilla o repetir automáticamente el fit.

TRAIN expansivo conserva historia antigua: no ventana móvil, muestreo o pesos
de recencia. Reestimar prior5clases y medias condicionales TRAIN en cada estado,
con misma normalización net_cost/(decision_ask×100) y shrinkage20 por
ticker/lado/clase hacia media global por clase. Ningún datoCAL/GATE en medias.
Alpha={0,.1,…,1} minimiza loglossCAL, empate alpha menor; mezcla
(1−alpha)p_model+alpha×priorTRAIN. No volver a ajustar después deCAL.
EV=decision_ask×100×sum(p_cal×mean_yTRAIN) por coste. Trading top1 EVadverso>0,
empate→WAIT; no elegir por quantity×EV.

Es full refit con historia retenida, no actualización neuronal secuencial.
Esto evita desechar deliberadamente ejemplos antiguos, pero no garantiza
retención de habilidades ni mejor resultado futuro. El gate siguiente prueba
regresión observable sin tocar pesos/umbrales a posteriori.

## RAW y protección con observación futura

RAW activa cada estado nuevo para decisiones de su fecha de creación en
adelante. FROZEN usa CONTEXT182 H1 original con su transform/prior/medias/alpha.
Verificar scores congelados sobre candidatos comunes contra sus autoridades;
los del puente se infieren con esos mismos parámetros. La cartera congelada
se recalcula continuamente sobre universo unido: no sumar los libros H1/Q3
que antes empezaban cada uno con100000 ni exigir identidad de aquellos ledgers.

Cada GUARDED empieza con FROZEN. En cada fecha de su frecuencia crea proposal
con challenger nuevo y snapshot exacto del incumbent vigente. Cada proposal
predice en shadow durante21sesiones de entrada, empezando el mismoD (i:i+21),
con features sólo disponibles a10:30 de cada día. Guardar scores de ambos en
las mismas filas; no elegir ofertas o días según outcomes. Shadows solapados
permitidos, sin escoger al mejor. No reentrenar un proposal mientras se observa.

Resolver sólo al comienzo de una sesión D posterior al final de sus21sesiones
y con todos sus labels/salidas H2 disponibles estrictamente antes deD00:00NY.
El replay aislado de cada comparador usa sólo entradas deesas21sesiones,
extiende calendario hasta sus salidas,100000USD nuevos, riesgo5000 ycostes
originales. No usar el estado de cash/posiciones de la cartera principal.

Si incumbent actual difiere del snapshot, STALE_CHALLENGER_REJECTED; no
reevaluarlo contra otro champion con datos ya usados. Si sigue idéntico,
PROMOTED sólo cuando ambas desigualdades se cumplen sobre las mismas filas:

```text
logloss_challenger <= logloss_incumbent_snapshot
net_adverse_challenger >= net_adverse_incumbent_snapshot
```

Igualdad acepta, sinepsilon de selección; tolerancias sólo para auditoría
numérica posterior. Si gate vacío, REJECTED_NO_GATE_ROWS; si alguna condición
falla, REJECTED y conservar bytes del incumbent. No incluir cal como gate.
Ante varios proposals maduros, resolver por creación ascendente; cada
promoción afecta la comprobación de staleness de los siguientes. Políticas
mensual/semanal guardadas son independientes. No optimizar la duración21.

Orden diario: resolver proposals anteriores → crear único fit si procede →
activar RAW/crear nuevos proposals con incumbent actualizado → score10:30 →
ejecución económica10:35 con salidas antes deentradas. Una promoción nunca
reescribe decisiones anteriores ni cambia una posición abierta.

Los proposals sin21sesiones completas o sin madurez antes del último as-of
20260917T00:00NY quedan PENDING_BEYOND_DECISION_CUTOFF. Aunque una salida
madure a10:35 del17septiembre, no puede afectar su decisión10:30 ni una sesión
futura no incluida. Persistir cola final; no aprobarlos como si fueran observados.

## Carteras y evaluación de estabilidad

Cinco políticas×base/adverse=10libros principales,100000USD iniciales una sola
vez el2enero, capital/posiciones continuos hasta17septiembre. No reset enmes,
semana o1julio. La entrada guarda model_id y la salida conserva esa identidad.
Riesgo5000USD adverso porentrada (prima+ambascomisiones), quantity10:30, guard
10:35 sinresize, una posición/ticker y máximo3globales. Comisiones1,30/lado,
slippage.01base/.02adverse; admisión de ambos libros común como replay congelado.

Principal: neto adverso continuo por política y diferencias contraFROZEN;
no elegir una frecuencia ganadora para promoción. Reportar cada mes (incluye
ceros y septiembre parcial), H1/Q3 como contribuciones al mismo libro, PF,
DDrealizado, trades, capital/bloqueos/cantidades, WAIT/no-fill, missing/cotas,
tickers/lados, mayortrade/mes yrestas mecánicas deconcentración. No presentar
estas restas como políticas. Toda afirmación deestabilidad debe mostrar ambos
bloques y la dispersión mensual, no sólo el total. No inventar garantía futura.

Probabilidades: logloss/Brier/reliability yEV bias/MAE, global/común yselected
separados, todos/sin cotas. Reportar diferencias RAW−GUARDED porfrecuencia,
promociones/rechazos/stale/pending, antigüedad del modelo activo ytiempo sin
aceptación; un gate que nuncaacepta no demuestra que sus challengers mejoren.
Medir transferencia observada: desempeño fuera del gate después deactivar,
sin excluir periodos negativos ni volver a elegir champions con ese resultado.
No nuevo p-value o test de significancia sobre periodos ya vistos.

## Implementación, auditoría y límites

Código nuevo y raíces nuevas, originales inmutables. Productor puede importar
funciones puras verificadas de evaluate_weekly_context_models.py
bdc6534f059ade7acc58f23952a88ed2068c7a712518b04f438945a583a07a2f,
evaluate_weekly_h2_ev_v2.py
8a9e75855d542a12662e5c812583f2ef86042f5c3ae1bbbad73c16042e063476,
replay_equal_risk_frozen.py
e4f42a9fa65120939cf5e131911c8f2990a9cd33d21ae036fa98d9eb816d5b9d.
No mutar globals, usar mains o splits fijos de helpers. Snapshot/pins de
autoridades/payloads/código al admitir y al cierre. Publicar contrato/review
antes de fixtures; código/tests/review ybinding real antes del único run.
Output h2_context_adaptation_01, observer h2_context_adaptation_observer_01.

Auditor separado no importa productor ni refit: reconstruye splits/madurez,
transformTRAIN, prior/medias/alpha, inferencia desdecoeficientes guardados,
scores/timeline/proposals/gates/10libros/métricas. Puede usar helpers del auditorH1
3eb6b9795ad260971435259858f86d3c00111bcc141973faf986411d4a68ad99,
no usados por productor. PASS acredita reconstrucción dados pesos, no repetir
entrenamiento o validar raw. Binding tras cierre+exit0 del productor.

Fixtures: fronteras exactas demadurez, purgaTRAIN/CAL,63/21sesiones, calendarios,
clases/missing, mutación futura sin efecto pasado,42fits/compartición, cero fit
en frozen, condiciondoble/ties/stale/pending/orden, promoción con posición
abierta, caja continua, puentejunio y no resetjulio, inferencia/medias/alpha,
mutaciones/symlinks/pins yarchivo de fallos. No tests que sólo reflejen código.

CPU0,seisvariableshilos1,gateRAM/commitlibre>=2GB antes deheavywork, procesos
ocultos/logs/handle retenido ysinretryautomático. Sólo D:/ThetaData yartefactos
locales; sin marketAPI, producción, bróker oVPS. Goal activo,promociónfalse.

Referencias de método (sin datos de mercado externos): documentación oficial
de [LogisticRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html)
y [prevención de leakage](https://scikit-learn.org/stable/common_pitfalls.html).
El olvido neuronal secuencial descrito por
[Kirkpatrick et al.2017](https://doi.org/10.1073/pnas.1611835114) es distinto de
nuestro full refit; no se implementa EWC o un método neuronal por analogía.
