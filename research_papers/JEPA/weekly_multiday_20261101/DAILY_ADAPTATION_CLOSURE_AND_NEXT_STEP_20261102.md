# Cierre DAILY y siguiente pregunta de investigación

El reentrenamiento diario no mejoró la estabilidad en esta receta. Comparación
continua del2-ene al17-sep2026, capital inicial100.000USD, riesgo máximo5.000USD
por entrada, idénticas reglas H2 y costes adversos:

| Política | Neto USD | Meses positivos ene–ago | Drawdown realizado USD |
|---|---:|---:|---:|
| Congelada | −20.204,20 | 3/8 | 77.701,60 |
| Mensual | −12.625,40 | 2/8 | 68.767,90 |
| Semanal | +2.693,80 | 3/8 | 46.860,80 |
| Diaria | +2.493,80 | 3/8 | 47.060,80 |

Septiembre es parcial y negativo en las cuatro. DAILY pierde200USD respecto a
WEEKLY, íntegramente julio;83trades y482contratos cada una. Ochenta y dos fills
son comunes y un CALL SPXW se sustituye por otro:−2466,60 frente a−2666,60USD.
No hay candidato que cumpla8/8, selected_policy=null y promociónfalse.
El neto diario sin mayor trade sería−9739USD y sin abril−34582,20USD; son
restas descriptivas, no políticas alternativas ni motivos para rescatar grupos.

## Qué se ha aprendido

136fits nuevos más42estados reutilizados cubren178sesiones. Auditor independiente
reconstruyó2448scores y ocho libros dados los pesos guardados, sin refit.
Actualizar diariamente cambió poco las decisiones: dos filas de612 cambian
top1 y sólo una afecta un fill, con efecto posterior en disponibilidad de posición.
Esto no prueba que la frecuencia nunca importe; muestra que aquí no resuelve
el deterioro de esta familia. Los estados comparten gran parte de TRAIN/CAL.

La receta entrena desde cero con TRAIN expansivo y conserva el pasado;
CAL63 maduro queda separado de los coeficientes. Reentrenar a diario no incorpora
esos63días recientes a TRAIN. No se hizo un experimento que aislara olvido
catastrófico, y retener historial tampoco garantiza adaptación a cambios.

En los mismos612candidatos, logloss ALL baja ligeramente1,2638→1,2627; no se
traduce en mejora económica. En las intenciones seleccionadas el bias EV adverso
sube148,59→149,89USD/contrato y MAE1024,58→1033,20. Estos grupos tienen105/104
filas y no son una comparación causal apareada. Las medias globales de error
ocultan el problema en las oportunidades seleccionadas. El filtro EV previo
ya falló y no se retocan ahora sus umbrales ni se eligen meses/tickers favorables.

## Cierre técnico y presentación

Productor136fits cerrado7decb3e2/exit54021b95; auditorV2 PID24780 exit0 a
10:02:44.028522UTC, audit383edce6/manifestddda352f/exit6c9e2369. Se preserva
fallo01 de admisión. No relanzar ningún proceso científico cerrado.

Renderer d0672f7d ejecutado una vez desdeaee0f71c3258784644c99a95f78708223d133d89;
PID3164/creation1793613947.5536065, exit0 retenido10:05:51.318782UTC.
Exit21baccf8ba67d21e6b5e81262ef1b630cc5fdaeef9237d1366a07a1e10446523.
Receipt48c865c08cbfd262357f78c16a7cf4b7177015bde139f7312fd8b435bad23684.
MDc4d11bfb/PNG5f7eb780/SVGca02587f. Root inspeccionó PNG: paneles y etiquetas
legibles, septiembre rayado parcial. Revisor `/root/daily_producer_review`:
CLEAR_REPORT_RUNTIME_CLOSURE,163snapshots y tres outputs exactos;14launchpins,
CPU0/diez variables1, gate15,256GB RAM/30,703GBcommit, metadata null/changed[].

Trece copias exactas/461339bytes en daily_adaptation_report_closure_archive_01
y archivos de lectura en este directorio; receipt7d2be286f2972b2c346e3bde6db9443c5c6238e5875abc75492d416e72e6f045.
Verificación adicional de ocho libros/72meses y72celdas del informe sin diferencias,
revisada CLEAR_WITH_PROVENANCE_LIMITATION. Sus intentos técnicos iniciales carecen
de logs/exits/snapshots completos: véase DAILY_ADAPTATION_DESCRIPTIVE_REVIEW y
PROVENANCE. Es apoyo descriptivo, no autoridad científica adicional.

## Siguiente paso: admisión de eventos de zonas, todavía sin experimento nuevo

El siguiente trabajo concreto es comprobar qué trayectorias locales permiten
probabilidades de alcanzar una zona objetivo antes de una zona de invalidación
y del límite temporal, y cotizar entradas/salidas del mismo contrato weekly.
El contexto IB/walls actual sólo describe10:30: no equivale a haber probado
entradas por toque Fibonacci ni salidas dinámicas por walls. El H2 actual
mantiene decisión10:30, entrada10:35 y salida10:35 dos sesiones después.

La exploración de `/root/next_stage_metadata` inspeccionó únicamente nombres de
directorios y archivos inmediatos en nueve raíces:
D:/ThetaData/data_options/{SPY,QQQ,SPXW}/{greeks,ohlc,oi}/2026.
Los meses disponibles terminan en09 y la segunda fecha de los nombres de los
parquets de septiembre termina en20260917 en las nueve. No encontró un periodo
local posterior en estas raíces; no es un censo de todoD: ni demuestra que otros
datasets no existan. Cualquier prueba inmediata con este conjunto seguirá siendo
SEEN_DEVELOPMENT, sin acreditarla como validación futura independiente.

Se corrigió una propuesta inicial del explorador: option/history/ohlc contiene
barras de OPCIONES y no da high/low del subyacente. No se usará para afirmar
que SPY/QQQ/SPX tocó una zona. El código local build_cache.py obtiene un spot por
minuto desde underlying_timestamp/underlying_price de Greeks, finito positivo,
edad0–60s y consenso entre filas válidas del minuto, sin relleno. Esto son
muestras observadas; no prueba máximos/mínimos intraminuto ni un toque continuo.

La admisión siguiente debe fijar identidad, reloj, cobertura/minutos ausentes y
reglas de evento observables antes de consultar resultados; después definir
zonas desde IB09:30–10:29 disponible, desempates, entrada posterior al evento,
quotes exactas del contrato, stop/objetivo/tiempo y política WAIT. Un salto entre
muestras no autoriza inventar el precio de fill de un toque. Conservar riesgo y
costes comparables. Este documento sólo señala la pregunta y prerequisitos;
no fija parámetros elegidos por PnL ni habilita fit/replay sin contrato revisado.

Goal general activo. No hay modelo rentable estable acreditado; los resultados
de esta comparación quedan cerrados. Producción, API, bróker y VPS intactos.
