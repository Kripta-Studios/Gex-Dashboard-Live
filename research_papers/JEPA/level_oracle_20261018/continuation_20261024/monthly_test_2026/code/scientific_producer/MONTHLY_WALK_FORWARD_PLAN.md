# Comparación mensual de actualización: diseño sin fits

2026-10-18. Pedido del usuario: entrenar con meses anteriores y evaluar el mes
siguiente. Se han implementado calendario/validadores puros y un runner nuevo,
`run_monthly_walk_forward.py`, con fixtures de modelos dobles. No se ha ejecutado
sobre datos de mercado ni se han cambiado los experimentos en curso.

Se compararán tres modos con el mismo LightGBM net de1954 features, config
original de200 árboles, semilla fija y umbral0 USD: static entrena2023–2024;
expanding empieza2023 y termina antes del mes evaluado; rolling12 usa los doce
meses completos anteriores. Evaluación mensual enero2025–junio2026:54 ledgers
modo-mes,36 fits únicos (18 expanding+18 rolling). Static reutiliza exactamente
el fit expanding de enero2025, incluyendo muestra, escala y normalización.

Sólo se admiten filas de sesiones dentro de [train_start,train_stop), con outcome
cerrado estrictamente antes de train_stop y del comienzo del mes objetivo.
Entrada/salida intradía, sin overnight; las features estaban disponibles al
decidir. El validador comprueba relojes suministrados, no certifica por sí solo
el significado de timestamps raw. Las fuentes/códigos se enlazarán a los hashes
del motor y features revisados, sin importar matrices legacy de procedencia
incierta. No se usarán closes diarios futuros, backfill ni índices de contratos
que sólo se hicieron visibles después de la decisión.

Muestreo original de identidad: hasta32 ofertas por cada una de cuatro franjas
fijas79min, máximo128/día, hash causal sin trayectoria oracle. En sesiones
cortas sólo tienen ofertas las franjas que alcanzan su last_state; conservar
sus límites y calcular IPW con poblaciones reales. Objetivo de muestra:
igual peso ticker-día y uniforme entre ofertas del día, con pesos globales
media1 para el fit. Sin estado h ni duplicación por h: este control es el net
original1954. Todos los candidatos causales se puntúan al evaluar, no sólo la
muestra de entrenamiento.

Escalas por ticker: mediana ponderada del premium100*ask positivo de las filas
FILLED muestreadas del TRAIN correspondiente, pesos IPW sin outcomes de los
meses evaluados. Target net/escala; scores de evaluación multiplicados por la
misma escala. Static conserva las escalas de2023–24; expanding/rolling las
recalculan con su TRAIN. Esto aísla la regla de refit con su calibración
predefinida; no es una comparación de cambio de pesos con escala constante.

Scheduler idéntico: mayor score estrictamente>0, empate action_id menor;
NO_FILL avanza1min sin rescate, FILLED bloquea hasta exit+1. Target/stop de
niveles congelados, demora1min, bid/ask y costes originales; ningún hold fijo.
No force-first ni CASH seleccionable. Usar h sólo para contabilizar el requisito
diario, no como nueva feature de este control.

Las sesiones cortas son parte del universo:15 ticker-días adicionales en TRAIN
2023–24 y9 en validación2025;0 en H12026. Se requiere su auditoría y el motor
separado con close_i210, decisiones60..195 y liquidación205. Sesiones normales
deben conservarse exactamente. El calendario completo esperado es2625
ticker-días, incluidos6 missing2026 que permanecen no evaluables. No lanzar
sobre universo recortado y luego afirmar cumplimiento universal.

Selección única de modo utilizando los doce meses2025 concatenados: sólo es
elegible si cada ticker-día esperado tiene >=1 fill. Entre elegibles, ranking
por la media de net/escalaCOMUN de cada ticker-día; la escala común por ticker
procede exclusivamente del TRAIN2023–24 de static/expanding enero2025, idéntica
para todos los modos y meses. Las escalas de target/predicción siguen siendo
las propias de cada fit; cambiar la mediana rolling no cambia el ranking. Empates:
static,expanding,rolling12. Si ninguno cumple, selected_mode=null; no rescatar
con2026. Rentabilidad económica por ticker y costes adversos se informa aparte
y no se convierte en una afirmación favorable sólo por cumplir frecuencia.
El informe distingue los750 ticker-días de validación de los369 esperados en
H12026:363 disponibles y6 sin fuente. Para cada modo y ticker presenta neto,
PF, WR, actividad y duración exclusivamente observados, junto al denominador
completo y los días disponibles sin fill. Los6 ausentes hacen el requisito
universal NO_EVALUABLE; no constituyen pérdidas observadas ni demuestran falta
de rentabilidad. No se atribuye PnL cero real a esos días. El modo se decide
únicamente con2025, aunque los informes2026 describan los tres modos fijados.

Antes de abrir resultados2026, congelar selección/null y las tres reglas de
actualización. Los refits expanding/rolling posteriores pueden incorporar meses
2026 ya cerrados según esa regla; eso es walk-forward causal, no reselección
del modo. Cada fit, escala, IDs de muestra y predicciones quedan sellados antes
de sus outcomes de evaluación. Un freeze histórico lógico no es un timestamp
de escritura2025: en replay se registra cutoff de información más orden real
de artefactos, sin inventar publicación pasada. Todo2026 ya visto sigue siendo
desarrollo; no existe outer prospectivo nuevo por cambiar el split.

Recuperación prevista por fit completo y ledger mensual sellado, sin refit de
modelos completados. Un solo fit a la vez, recursos disponibles comprobados,
sin interferir con los tres experimentos actuales. El runner guarda muestras
de identidad y chunks por día, matrices por ventana, targets/escalas, modelo,
scores y ledgers. Antes de abrir outcomes de cada mes sella las predicciones
de TODOS los modos de ese mes. Usa cuatro threads y espera12GiB RAM disponible
y16GiB de commit libre antes de cada fit; comprueba espacio de staging de matriz.
Los ficheros parciales derivados se preservan y reconstruyen. Un GBT interrumpido
después de fit_started no se reentrena automáticamente ni se presenta como
completo: no hay checkpoint intrafit y requiere recuperación técnica separada.

El loader admite rutas directas a arrays/parquets full originales y metadata
unificada nueva, sin copiar los arrays. Exige auditoría independiente del
dataset full+short, feature_contract sellado, universo2625 y exactamente6
missing; los cuatro archivos de features se contrastan con sus hashes del
índice auditado antes de la primera lectura, y se sellan también en los
checkpoints mensuales de predicción y resultados. Una sustitución coherente
de arrays y metadata anterior al primer uso o posterior a completar el mes
se rechaza. Un run real requiere review exacta del código
y nueva instrucción del coordinador tras el diagnóstico actual. CLI por defecto
`--stage prepare` no abre labels ni entrena; validation/test/all requieren
`PASS_MONTHLY_WALK_FORWARD_IMPLEMENTATION_REVIEW` con dependencies exactas.
