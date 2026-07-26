# SUMMARY.md — Continuidad de la investigación de rentabilidad

## V4R1 abre una vía causal a 2026 — 2026-07-26

Por autorización nueva del usuario, los cinco fallos Greek/IV de junio pueden
reconsultarse una vez sin sobrescribir fuentes; si siguen inválidos, se excluye
solo el sensor-fecha por una regla outcome-free sellada. El V4 entrenado
2023–2024 no se retunea. El inventario actual alcanza 133 fechas comunes hasta
2026-07-24; julio contiene 13 sesiones y será MTD. Capturador, gate y auditor se
versionan antes de la API; freeze se versiona antes de opens10:36/13:36.

## V6 continúa V4 sin fuente nueva — 2026-07-26

El usuario autoriza usar solo los artefactos V4 existentes bajo su licencia
Options Standard básica. V6 queda predeclarada como una única prueba no lineal:
mismas 29 features, mapping, eventos, clocks y costes; HistGB depth2 fijo en
lugar del logistic. 2024 y 2025 siguen siendo development visto. Debe pasar
PF>1,20, WR>45%, neto>0, mínimo13/mes y 12/12 meses positivos en QQQ/SPXW/SPY
en ambos años antes de congelar y abrir 2026 una sola vez. No hay descarga,
selección de junio/julio, reparación Greek/IV ni cambio live.

## V5 cerrada en source gate — 2026-07-26

La captura outcome-free procesó 1.504 requests y conservó 1.364 completos; 140
respuestas fallaron el validator como inválidas o duplicadas. Enero2024 queda
sin una sola fuente válida en QQQ y SPY. No existe capture seal y no se abrió
feature view, open económico ni outcome. V5 es `BLOCKED_DATA`; no se permite
requery/dedup/exclusión ni evaluar el subconjunto. Auditor independiente PASS:
rehash/reparse1.364, mismatch0, unaccounted0 y mínimo mensual0; summary/seal
`39b417e0...fc77`/`20f322c5...0297`. La continuidad queda formalmente bloqueada
por dependencia externa hasta aportar tape histórico y live equivalentes.

## V5 predeclarada sin acceso a datos — 2026-07-25

La fase preejecución ya tiene capturador atómico/resumible, builder del gate y
auditor raw independiente. El universo exact-0DTE por metadatos contiene 752
fechas comunes QQQ/SPY (250/252/250) y 1.504 captures; SHA de fechas
`e7786a1a...b8f9`. Suite cross-venue113, Ruff y compile pasan. El único request
real fue el estado del Terminal (`CONNECTED`); aún no se llamó `trade_quote` ni
se leyó ningún valor. Debe versionarse este código antes de capturar y después
versionarse gate+auditor antes de opens10:36/13:36.

El inventario outcome-free halló una fuente causal nueva con contrato
histórico/live bajo ThetaData Standard: prints OPRA 0DTE ejecutados de QQQ/SPY
emparejados con el NBBO estrictamente anterior. Es distinta del OHLC flow y de
la dinámica de quotes ya cerrados. No se arrancó Terminal ni se consultó un
endpoint, precio, feature, open económico u outcome.

V5 fija QQQ←QQQ, SPY←SPY, SPXW←SPY, tres ventanas hasta 10:35, 24 features de
prints/premium/contratos y un solo logistic pooled L2 C0,1. 2024 y 2025 son
development walk-forward ya visto y solo avanzan si los tres tickers pasan en
ambos años PF>1,20, WR>45%, neto>0, mínimo13/mes y PnL positivo 12/12 meses.
Primero se versionan predeclaración e inventario; luego gate y auditor
outcome-free. 2026, payoff físico y producción permanecen cerrados.

## Resumen causal autoritativo — 2026-07-25

Ninguna familia cumple aún simultáneamente, por ticker, PF>1,20, WR>45%,
mínimo13 trades en cada mes y PnL positivo todos los meses. Las instrucciones
pendientes de secciones antiguas ya fueron ejecutadas y son solo historial.

Resultados a 1bp, orden QQQ/SPXW/SPY:

| Año y papel | PF | WR | Neto bps | Mín/mes | Meses positivos |
| --- | --- | --- | --- | --- | --- |
| 2023 design mapping, no OOS | 1,173476 / 1,071604 / 1,072835 | 51,822 / 50,000 / 50,403% | +812,500 / +268,657 / +273,999 | 19 / 19 / 19 | 7 / 5 / 5 |
| 2024 outer V1 auditado | 0,866939 / 0,698912 / 0,693382 | 48,594 / 39,271 / 40,081% | -662,668 / -1.220,988 / -1.246,477 | 19 / 18 / 18 | 6 / 5 / 5 |
| 2024 V3 development visto | 1,231750 / 1,395967 / 1,408300 | 51,406 / 55,870 / 56,680% | +964,402 / +1.124,966 / +1.153,375 | 19 / 18 / 18 | 8 / 8 / 8 |
| 2025 outer V3 auditado | 0,655469 / 1,035567 / 1,039777 | 50,607 / 53,689 / 53,689% | -2.381,476 / +163,026 / +182,456 | 18 / 17 / 17 | 5 / 6 / 6 |
| 2025 V4 development visto | 1,204351 / 1,247945 / 1,346342 | 51,8219 / 52,0492 / 53,2787% | +1.060,279 / +1.030,091 / +1.381,556 | 18 / 17 / 17 | 7 / 8 / 8 |

V4 es el mejor resultado agregado y su auditor reprodujo exactamente modelo,
dataset, ledger y gates, pero fue diseñado tras ver 2025 y falla estabilidad
mensual. No existe resultado económico V4 de 2026: el censo outcome-free cerró
por cinco IDs Greek/IV nuevos (92 Greek-only y 516 IV-only). No se puede ampliar
la excepción de cuatro repairs, intersectar, excluir fechas ni recapturar.

El reemplazo cash-only tampoco pasa conjuntamente 2024 y 2025. Por tanto el
siguiente avance real requiere una fuente causal nueva, disponible tanto en el
histórico como en live. Una familia nueva usará 2023–2025 solo como development
walk-forward y deberá quedar predeclarada, gateada, auditada y congelada antes
de abrir 2026. Mantener QQQ←QQQ, SPY←SPY y SPXW←SPY. No paper/live hasta
validar además ask→bid, no-overlap, hold30–180m y `reject_while_open`.

## Resultado causal V3 — 2025 no generaliza

Tras el manifest committed `91584706`, el one-shot secuencial 2025 ejecutó 735
trades y cerró 2026. QQQ obtuvo WR50,607% pero PF0,655469 y -2.381,476bps;
SPXW/SPY quedaron en PF1,035567/1,039777 y +163,026/+182,456bps. Los tres
conservaron capacidad mensual (mínimo18/17/17), pero solo tuvieron 5/6/6 meses
positivos. Ninguno alcanza simultáneamente PF>1,20 y 12/12 meses positivos.

La auditoría independiente rehasheó las 735 fuentes sin diferencias y reprodujo
la cadena mensual y todos los retornos/costes/gates. V3 queda cerrada; 2026 no
fue consultado. Una familia posterior debe tratar 2023–2025 como development y
congelarse de nuevo antes del primer outer 2026.

Checkpoint exacto a preservar, coste1bp: QQQ PF1,204351, WR51,8219%,
+1.060,279bps, min18 y 7/12 meses positivos; SPXW PF1,247945, WR52,0492%,
+1.030,091bps, min17 y 8/12; SPY PF1,346342, WR53,2787%, +1.381,556bps,
min17 y 8/12. Es el mejor resultado de development, no una validación OOS.

El evaluator reproducible y su auditor independiente se publicaron en
`b421acd3` y ya pasaron. Fijan 1.482 filas train, 735 predicciones y 738 fuentes
tempranas sin mismatch; el auditor reproduce exactamente modelo, dataset,
ledger y gates. Summary auditada `a2beced1...21b`. Ningún path 2026 fue abierto;
el PASS incremental solo autoriza preparar su data gate outcome-free.

Ese data gate no puede construirse. El censo vintage 2026 encontró cinco nuevas
discrepancias Greek/IV en 508 capturas: 92 filas Greek-only y 516 IV-only,
todas en fronts QQQ/SPY del 24–26 de junio. La excepción `Greek∩IV` estaba
cerrada a cuatro IDs históricos; por ello V4 falla antes de captura y 2026 no se
abre. No se descartaron fechas ni se consultaron retornos para tomar la decisión.

La alternativa cash-only tampoco transporta. La mejor secuencia de 35 retornos
minuto logra PF QQQ1,169 en 2024 y SPXW/SPY1,480/1,483 en 2025, pero los bloques
opuestos quedan bajo1. Separar modelos por sensor conserva el mismo cambio de
régimen. Resúmenes cash, spot5m y dos modelos shallow también fallan. No existe
V5 promovible ni motivo causal para abrir 2026.

## Vía V4 predeclarada

La exploración posterior encuentra una mejora agregada real al reentrenar el
logistic pooled V2R1 con 2023+2024 completos: sobre el 2025 ya visto obtiene PF
1,204/1,248/1,346 y PnL +1.060/+1.030/+1.382bps para QQQ/SPXW/SPY, con WR>51%
y frecuencia mínima18/17/17. No alcanza estabilidad mensual: 7/8/8 meses son
positivos. Ventanas online, confidence filtering y targets ponderados/ridge no
mejoran conjuntamente 2024, 2025 y capacidad.

V4 congela el modelo pooled original sin filtros ni refit. Como nació tras ver
2025, todo 2023–2025 es development; 2026 sigue intacto y solo podrá abrirse
después de development reproducible, auditoría, data gate outcome-free y freeze.

## Hipótesis V2 congelada antes del nuevo estado cash

La exploración sobre los artefactos ya abiertos descarta un clasificador ancho
de superficie y conserva una hipótesis mínima: aprender directo/inverso. V2
fija logistic L2 C0,1 con estado option-sensor y opens cash causales hasta
10:35. Entrena 2023 para H1-2024 y 2023+H1 para H2-2024. Todo 2024 es
development contaminado; 2025 permanece primer outer. El contrato debe quedar
committed antes de leer esos nuevos clocks.

El evaluator correspondiente ya está implementado sin ejecutar: rehashea cada
underlying, hace pushdown de 66 opens exactos, materializa 29 columnas y sella
los dos modelos/logs. Pasa 74 tests cross-venue y checks estáticos. Debe quedar
committed/pushed antes del único development run; 2025 sigue cerrado.

El primer run se cerró antes de fuentes cash por una colisión de columna entre
ledger y sensor. El fix mantiene la presión sellada bajo namespace de auditoría
y deja la feature del modelo inequívoca; 75 tests pasan. No hubo nuevo dato ni
output económico antes del fix committed.

El segundo intento también cerró pre-cash: dos ceros QQQ ya eran no-trades en
el ledger 2023. La aclaración congela sus IDs y los elimina solo del fit porque
el target directo/inverso es indefinido; 2024 tiene cero casos y no cambia.
Una tercera key falla cerrado. 2025 continúa intacto.

El primer censo cash encontró un único defecto entre 1.487 fuentes: dos opens
cero de SPY 20230605 antes de 10:00. V2R1 no imputa ni excluye la fecha; mueve
uniformemente todos los cash blocks a 10:00–10:35 y conserva seis métricas con
horizontes35m/15m/5m. No hubo fit ni resultado antes de congelar el cambio.

V2R1 completó después y falla cinco de seis ticker-bloques. Solo SPY H2 es
positivo (PF1,123/+228,5bps); QQQ PF0,667/0,738, SPXW0,928/0,992 y SPY H1
0,772. La frecuencia pasa, la orientación aprendida no. 2025 queda cerrado.
Auditor de refit/source rehash implementado y probado antes de ejecución.

La auditoría real también pasa: recompone los 743 trades y rehashea 1.487
fuentes sin diferencias. No cambia el cierre; V2R1 queda archivada como ejemplo
de complejidad que no generaliza y 2025 permanece sin outcomes.

La siguiente familia reduce a un bit mensual: majority hit directo del mes
anterior decide conservar/invertir el signo durante todo el siguiente. V3 se
declara post-outcome; 2024 solo development y 2025 primer outer intacto. No se
puede consultar 2025 hasta evaluator, auditor y freeze committed.

V3 development y su auditor independiente ya están sellados en `627f3b20`.
El runner outer2025, su freezer outcome-free y un auditor independiente se han
implementado antes de outcomes: fijan el estado diciembre2024, los eventos y
fuentes 2025, los counts mensuales y todos los hashes de código/input. Pasan 100
tests cross-venue/native-clock y checks estáticos; código publicado en
`5fe51e70`. El freeze real enumeró 735 eventos, con mínimo17/mes, y fijó enero
`INVERSE` desde 25/56 hits de diciembre2024. Manifest SHA
`f45e7f1b...646ed`, sin outcomes. Falta publicar el manifest; solo entonces
puede abrirse 2025 una vez.

## Resultado causal nuevo — V1 falla outer 2024

El runner congelado en `b53dcaa3` ejecutó su único 2024: pooled 743 trades,
WR42,665%, PF0,761071 y -3.130,133bps. QQQ/SPXW/SPY quedaron respectivamente
en PF0,866939/0,698912/0,693382 y PnL -662,668/-1.220,988/-1.246,477bps; la
frecuencia mínima fue 19/18/18, pero solo hubo 6/5/5 meses positivos. Ningún
ticker pasa el gate incremental; 2025 y 2026 no se abren para V1.

La auditoría independiente pasa tras corregir en `95609e21` una comparación de
hashes CSV post-round-trip: 743 fuentes sin cambios y economía/gates exactos.
V1 queda cerrado. La investigación posterior puede usar 2023–2024 como
development temporal, pero reserva 2025 como primer outer intacto y 2026 como
holdout; no hay autorización live.

## Estado posterior — data gate V1R1 auditado

El full audit composite se versionó en `90ffd155`. El builder outcome-free se
ejecutó una sola vez después y pasó: 1.506 filas, 1.504 válidas locales, 1.502
válidas tras mapping y 1.478 eventos económicos; 16.566 fuentes revalidadas,
coverage mínima99,206%, 237 estados mínimos y 17 eventos mensuales mínimos.
Feature view SHA `d4335ad8...566062`, manifest SHA `492f51c8...0452e`.

La auditoría independiente también pasó, con cero diferencias de hash/size,
paridad exacta SPY→SPXW y todas las gates recomputadas. Summary SHA
`7700b087...e85dac`. Ningún outcome, valor underlying, 2026 o producción fue
abierto. La próxima acción no es evaluar: primero versionar estos dos compactos,
después congelar y versionar el runner outer2024 desde HEAD limpio.

El primer precheck del freezer identificó una ruta antigua al compacto V1. Se
corrige únicamente ese nombre para consumir el directorio V1R1 versionado y se
prueba antes de congelar; no cambia ningún elemento científico del runner.

La ruta se corrigió y publicó en `811e729f` con 66 tests cross-venue. El freezer
ya generó `PREEXECUTION_FROZEN`: 743 eventos 2024, 743 fuentes, manifest SHA
`339c0793...126b72c` y ningún acceso a outcomes. Falta commit/push del manifest;
el outer no se ejecuta antes de ese límite.

## Estado nuevo — 2026-07-22

La captura masiva V1 se conserva inmutable con 3.008/3.012 unidades y cuatro
diferencias Greek/IV outcome-free. El overlay V1R1 ya pasó 4/4 desde
`0b7cc6dd`: 2.828 keys compartidas, ocho unilaterales audit-only, missing0,
revised0 y crossed0. Seal SHA `81ded7dd...bd9d`; sus compactos están
versionados en `53872c39`. Esto repara la fuente, no demuestra alpha.

El sellador composite ya está implementado, probado y ejecutado.
Revalida offline las 3.008 capturas V1 y las cuatro V1R1 desde sus roots
separados, fija endpoint/request/provenance/runtime y crea un índice lógico
3.012/3.012 sin copiar raw ni leer underlying, labels o outcomes. Suite
repairs+composite `13 passed`; suite cross-venue `63 passed`; Ruff y pycompile
PASS. El primer run desde `a352d544` falló cerrado antes de escribir output por
una diferencia exclusiva de índice DataFrame en el CSV audit-only, no de
valores ni hashes. El validator ya normaliza ese índice y revalida los cuatro
repairs reales. El fix se publicó en `963f91c9` y el reintento terminó PASS:
3.012 captures/1.506 sesiones, 7.246.230 rows, 2.415.402 shared keys, ocho
unilaterales audit-only y missing0. Seal SHA `5b97ebc5...cf84f`; contract/index/
summary `68714d77...8c046`/`e5a669b7...3a0e`/`41deb014...df65`. No se leyó
outcome ni 2026. Compactos listos para versionar.

El bloqueo siguiente es explícito: el auditor full y el builder actuales todavía
presuponen un único root y Greek=IV para las 3.012 unidades. Tras sellar y
versionar el composite hay que adaptarlos al índice multi-root y permitir la
intersección solo en los cuatro IDs congelados. Hasta entonces no ejecutar data
gate ni abrir outer 2024. No existe PF nuevo ni resultado 2024–2026; producción
sigue intacta.

La compatibilidad se congela en una aclaración nueva antes de outcomes: valida
los hashes exactos del composite, resuelve cada capture por root/generación,
mantiene Greek=IV en las 3.008 V1 y acepta los ocho unilaterales exactos solo
como audit de los cuatro repairs. No cambia ninguna regla económica. Tras
commit/push se implementan auditor/builder y se vuelven a publicar antes de
ejecutarlos.

La implementación composite-aware ya está terminada preejecución. Auditor y
builder validan los blobs exactos, revalidan cada generación con su contrato,
usan el root sellado por role y alinean modalidades con conteos congelados. Una
prueba contra el composite real y una regresión Greek/IV demuestran que V1 no
acepta discrepancias y V1R1 elimina solo las unilaterales declaradas. Focal
15/15, cross-venue 65/65, checks clean. Falta commit/push y el full audit real;
el data gate aún no se ejecuta.

El full audit real ya es PASS: revalidó 3.012 captures, 1.506 sesiones, 6.024
fuentes vintage y 1,370 GB raw; shared2.415.402, exclusivas2+6 y missing0. El
revalidation digest coincide exactamente con el índice composite. Todos los
flags outcome/underlying/2026/producción son false. Falta versionar/commit/push
esta evidencia; después puede ejecutarse una vez el data gate outcome-free.

## Respuesta concreta sobre junio y julio de 2026

La arquitectura activa `CROSS_VENUE_CALENDAR_RR_LEADER_V1` todavía no tiene
resultado 2026. Su sidecar 2024–2025 iba por 424/3.012 captures, cero errores,
en PID42112 a las 03:09 del 17/07. La secuencia congelada obliga a evaluar 2024
y 2025 antes de abrir 2026; por tanto hoy no puede llamarse rentable en junio o
julio.

Entre las arquitecturas ya cerradas, `DIRECTIONAL_VOL_COMPLEX_V1` fue positiva
en junio para los tres: QQQ 21 trades, WR57,14%, PF1,249, +161,459bps; SPX cash
proxy 21, 61,90%, 1,779, +237,701; SPY 21, 61,90%, 1,764, +233,476. Julio MTD
hasta el 15 fue positivo, pero con solo 10 trades y PF1,133/1,098/1,888; QQQ y
SPX fallan PF1,20 y todos fallan >=13 trades. La policy completa tampoco pasa:
Jan–Jun PF1,039/0,993/0,898 y solo 3/4/3 meses positivos. No es desplegable y
SPX cash no prueba ejecución SPXW ask→bid.

Se implementó antes de outcomes un auditor independiente para el futuro outer
2024 cross-venue. Recalcula trades, costes1/2/3bps, meses/tickers/gates, hashes
de fuentes e identidad SPY→SPXW; suite cross-venue `50 passed`. Sigue inactivo
hasta completar seal→data gate→frozen runner→one-shot 2024.

## Regla nueva de promoción live — 2026-07-17

El usuario pide implementar la arquitectura rentable en los entornos
`systemd/realtime_feed.service` y `systemd/ai_bot.service`, incluyendo los
wrappers Python necesarios, solo si supera la validación causal de 2026 con
énfasis en junio y julio. Esto no es autorización para desplegar el diagnóstico
2023. Primero deben pasar 2024, 2025 y después 2026 con la gate por ticker
PF>=1,20, WR>=45%, >=13 trades/mes completado, PnL positivo cada mes, ask→bid,
hold30–180m y no-overlap. Junio debe pasar cerrado; julio 2026, incompleto a
17/07, solo puede exigirse positivo MTD/shadow sin usarlo para selección.

Si se satisfacen las gates, integrar con paridad exacta offline/live, artefacto
`production_live_ready`, pruebas del scheduler y arranque de ambos servicios.
La primera promoción mantiene `paper_order_intents=true`; al cerrar la labor se
entregan comandos VPS reproducibles. Hasta entonces producción queda intacta.

## Contrato del próximo data gate

Antes de abrir 2024 se congeló el data gate cross-venue: exige full seal
3.012/3.012 y reconstrucción offline de cada captura. El sidecar nativo solo
prueba timestamps/keys 10:30 y 10:35; los valores de delta, IV, bid y ask siguen
siendo los vintage. El join SPY→SPXW es de la misma fecha y no permite as-of,
thresholds ni variantes. Cobertura y distinctness se evalúan por ticker-año y
la frecuencia >12 por ticker-mes. No se leen opens de outcome.

El builder que implementa ese contrato ya está probado: falla sin full seal,
rehash/reconstruye las 3.012 capturas, conserva valores vintage, carga solo los
dos spots predecisión y genera el mapping exact-date. La suite relacionada pasa
34/34. Aún no se ejecutó el data gate real y por tanto no existe resultado OOS.

El ensayo posterior 2024 también queda predeclarado: una sola dirección diaria,
open 10:36→13:36, 180m y coste 1bp. La gate PF>1 solo permite avanzar a 2025;
la promoción continúa exigiendo PF>1,20 y todos los meses positivos por ticker.
No se ha generado el frozen manifest ni leído retorno 2024.

Evaluator y freezer ya implementan ese contrato y pasan la suite combinada
45/45. El acceso futuro al underlying se limita a los dos rows exactos de entry
y exit y revalida el source hash. Siguen inactivos hasta que full capture y data
gate estén sellados/committed.

La auditoría del stack live concluye `NOT_LIVE_READY` para esta familia: el
vencimiento back, la IV y la memoria t0→t1 no coinciden con research. El bot
actual tampoco representa una única decisión diaria cross-venue. No se cambia
producción hasta validar dirección y después una traducción ejecutable de
opciones; la integración inicial seguirá siendo paper-only.

También está preparado el auditor del full sidecar: exige seal PASS, reconstruye
cada captura y revalida todas las fuentes antes de permitir el data gate. La
suite completa relacionada pasa 48/48. Todavía no se ejecutó porque el sidecar
sigue parcial.

Un segundo auditor valida el data gate futuro sin outcomes: rehashea las 16.566
fuentes, recompone las gates y demuestra que SPXW usa la presión SPY de la misma
fecha. La suite relacionada asciende a 53/53; aún no se ejecuta sobre datos.

Captura completa 2024–2025 activa en PID42112: universo3.012, workers2,
checkpoint334 y cero errores. Es solo sidecar de reloj; no existe aún PF OOS.

El capturador completo está listo y probado: 3.012 unidades atómicas, resumibles
solo si revalidan raw/source keys, y seal 100% obligatorio. `16 passed`; aún no
se ejecutó ni se abrió rentabilidad 2024.

Corrección de capacidad: el universo completo real son 1.506 sesiones/3.012
capturas, no 1.503/3.006. La diferencia de 0,2% no cambia viabilidad (8,11M
filas/1,43GiB), pero queda congelada antes del full para evitar exclusiones.

El preflight de reloj cross-venue pasa: 24/24 capturas y 64.632 filas con
coverage exacta, sin extras, revisiones o crossed. El full 2024–2025 proyecta
8,10M filas y 1,43GiB, viable. Esto desbloquea el backfill causal que permitirá
la primera validación 2024 del mapping SPY→SPXW; aún no hay nuevo PF OOS.

La reparación de seal ya tiene modo offline tested (`11 passed`): fija el código
de captura original, reconstruye los 24 parquets y no toca red. Debe commit/push
antes de validar el staging y crear el PASS agregado.

La captura native-clock terminó materialmente 24/24 con key coverage perfecta y
cero revisiones, pero no está sellada: el timeout del wrapper rompió stdout antes
del resumen final. Staging queda inmutable, sin `errors.json` y sin outcomes. Se
predeclara un sealer offline ligado a `167118b0`; nunca se recapturan respuestas.

El sidecar preflight de la nueva arquitectura ya está implementado, no
ejecutado. Congela cuatro fechas por ticker en 2024–2025, 24 expiraciones
front/back, clocks 10:30/10:35 y coverage completa contra Greek/IV vintage.
Revisiones actuales no sustituyen prices; extras se archivan. Suite `9 passed`.
Primero commit/push; después un único capture outcome-free desde remoto CONNECTED.

## Nueva vía: liderazgo calendar-RR SPY→SPXW

El audit pareado explica el PF0,912 de SPXW aunque se mueva como SPY: retorno
corr0,999733 y mismo signo246/246, pero pressure corr0,580247 y solo148/246
acciones iguales. En días iguales ambos PF≈1,022; en desacuerdo SPXW0,753 y
SPY1,170. Usar el sensor SPY fijo para el payoff SPXW habría dado en 2023
PF1,071604, WR50%, +268,657bps y min19. Junto a QQQ1,173 y SPY1,073, los tres
superan PF1 agregado por primera vez, aunque solo 7/5/5 meses son positivos.

Esto genera `CROSS_VENUE_CALENDAR_RR_LEADER_V1`, no demuestra rentabilidad:
2023 ya está visto. Mapping sin variantes QQQ←QQQ/SPY←SPY/SPXW←SPY; 2024
será primera validación, 2025 queda para secuencia frozen y 2026 holdout. Antes
se exige sidecar nativo front/back 2024–2025; preflight solo 12 sesiones. La gate
de promoción PF>1,20/WR>45%/>12/todos meses positivos no cambia.

Breadth calendar-RR de 14 componentes falla min3/mes, IWM min12; NDX/NDXP no
tienen Greeks y SPX no tiene fechas 0DTE+back. Cierres outcome-free versionados.
El base pooled PF1,058 a 1bp cae a PF0,999/-9,31bps con 2bps.

Calendar-RR avanza el agregado desde PF<1 a PF1,058 y +729,69bps; QQQ y SPY
también superan PF1. SPXW queda PF0,912 y solo pasan 12/36 meses. Resultado
auditado y familia cerrada por estabilidad; no se abrió 2024–2026.

Calendar-RR tiene ya manifest frozen `f00a7ef0...35f79` sobre `79dfe416`, aún
sin outcomes. El siguiente paso es versionar el manifest y ejecutar exactamente
una vez el ledger 2023; no hay permiso para abrir otros años.

El runner económico calendar-RR ya está implementado pero no ejecutado. Su suite
12/12 pasa y no expone scope/policy mutable. Debe quedar committed, generar otro
manifest frozen y commitearlo antes del único outcome read 2023.

Calendar risk reversal ya supera su gate físico 2023: 747/750 eventos, mínimo
99,2% coverage y 19 eventos mensuales, señal no degenerada. La auditoría
independiente reprodujo fórmulas y 3.750 hashes. Aún no existe PF/WR/PnL; el
runner económico debe escribirse y congelarse antes de abrir retornos.

La implementación outcome-free de calendar RR ya valida inventario, timestamps
nativos, Greek/IV exactos y selección fija 25d. Hay 750 sesiones 2023, mínimo19
por ticker-mes, y el smoke real pasa. Suite `8 passed`; el full data gate solo
puede ejecutarse después de commit/push.

El siguiente mecanismo activo es calendar-skew, no una variante de parity. El
cambio OI exacto se descartó por frecuencia (mínimo4/mes). La nueva hipótesis
congela `Δ5m[(CALL25-PUT25)_0DTE-(CALL25-PUT25)_next]`, exact native clocks y
contratos persistentes t0→t1. Solo se autoriza data gate 2023 sin outcomes;
2024–2026 siguen cerrados.

La familia parity queda cerrada en desarrollo 2023: 730 trades, PF0,874751,
WR48,630%, -1.689,310bps y solo 10/36 meses PASS. Ningún ticker supera PF1 y
todos pierden gross. Auditoría independiente PASS sobre 744 fuentes. Outer
2024–2025 y holdout 2026 no se abrieron; no se permite rescate post-hoc.

El runner parity ya tiene manifest preejecución SHA `f3819d88...26972` sobre
`5cc1c936`, con 744 eventos 2023 y todos los parámetros/hashes sellados. Aún no
se ejecutó. El manifest debe quedar committed/pushed antes del outcome one-shot.

El runner determinista de desarrollo 2023 ya está implementado y probado
pre-outcome (`13 passed`, Ruff clean). Rechaza rutas 2024+, parámetros de scope
mutables y ejecución sin manifest committed. Aún no ha leído precios futuros:
primero debe quedar commit/push y después sellarse su manifest de freeze.

## Checkpoint actual — OPTION_PARITY_PRESSURE_V1

El relanzamiento V1R1 pasó el data gate completo: 2.256/2.256 sesiones
2023–2025, cero errores, mínimo 18 eventos por mes, cobertura anual total y
señal no degenerada. El parquet físico 2.256x28 tiene SHA
`45bca098...d5100`; se revalidaron 5.953 fuentes. Esto no es evidencia
económica: no se han leído retornos ni 2026. La única etapa autorizada es
congelar y ejecutar el ledger fijo sobre desarrollo 2023.

**Actualizado:** 2026-07-17 00:30 Europe/Madrid

**Rama:** `main`

**Base de ejecución más reciente:** `5e2dc677`

**Experimento activo:** ninguno; último cierre `CROSS_SESSION_RELATIVE_VALUE_V1`

> Las secciones MANAGE30 de este documento conservan la cronología histórica,
> pero ya no describen trabajo activo. El checkpoint autoritativo actual está
> en la sección 25.

## 1. Estado ejecutivo

No existe una policy nueva que haya demostrado rentabilidad causal bajo la gate
vigente. Los PF altos de los oracles usan futuro y no son operables. MANAGE30,
weeklies, long-option 0DTE nested, short premium, long-vol dual-leg, dirección
cash/Globex y ejecución directa IB/Fibonacci ya tienen resultado negativo o gate
de datos cerrada. Producción no fue modificada.

Gate histórica MANAGE30, ya evaluada y cerrada, para cada una de las 36 celdas
ticker-mes de 2023:

- PF estrictamente mayor que 1,30;
- WR estrictamente mayor que 45%;
- más de 12 trades;
- PnL positivo;
- hold mínimo de 30m;
- concentración top-5 trades <=20% y top-5 días <=30%.

Una métrica pooled atractiva no compensa meses sin trades o perdedores. Nunca se
entrena con el mismo mes que luego se reporta.

## 2. Evidencia económica vigente

| Evidencia | Trades | WR | PF | PnL/R | Gate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Benchmark limpio QQQ | 94 | 44,68% | 0,984 | negativo | FAIL |
| Benchmark limpio SPXW | 107 | 42,99% | 0,832 | negativo | FAIL |
| Benchmark limpio SPY | 123 | 43,90% | 0,919 | negativo | FAIL |
| KING K0 nivel 2023 | 1.443 | 43,10% | 0,810 | -94,144R | FAIL |
| KING K1 nivel+pendiente | 1.324 | 42,22% | 0,804 | -89,845R | 2/36 |
| KING invertido B00 | 1.304 | 43,02% | 0,850 | -67,677R | 1/36 |
| Mejor exit fijo D1/S30 | 1.496 | 35,96% | 0,925 | -30,131R | FAIL |
| Oracle B00/S30 no causal | 1.429 | 43,60% | 1,190 | +65,326R | 13/36 |
| Oracle 16 exits no causal | 1.337 | 54,67% | 2,357 | +324,783R | 32/36 |

Los oracles son techos retrospectivos, no políticas. No atribuir PF2,357 al
modelo ni al sistema live.

## 3. Utilidad real de las referencias King

\`live_king_node.py\` sí sirvió: permitió fijar el universo de oportunidades,
dirección y contrato y traducirlo a un replay executable. La regla simple
\`GEX negativo=momentum / GEX positivo=reversión\`, incluso condicionada por
pendiente 45m, no orienta establemente: el right elegido supera al contrario solo
49,02%. Invertir todo también pierde.

\`MASTER_KING_NODE_RECORD_V5.xlsx\` aún no está auditado celda a celda. La skill
de spreadsheets está disponible, pero su dependencia obligatoria
\`load_workspace_dependencies/@oai/artifact-tool\` no está expuesta en esta
sesión. La propia skill prohíbe buscar rutas, instalar o sustituirla por otra
librería. No modificar ni git-add el workbook. Cuando el loader exista, la
auditoría será read-only y cualquier hallazgo será una hipótesis nueva; no puede
retocar MANAGE30 después de congelar su protocolo.

## 4. Familias cerradas relevantes

### Existing-data E1

E1 ya usó 527 features de entrada: higher Greeks sintéticas, cambios/ratios,
walls, IB/Fibonacci, precio, OI y volumen. Sus 144 celdas de modelos económicos
abstuvieron porque ningún grid pasó tres meses inner. Repetir las mismas
variables en entry está cerrado; observar su evolución post-entry es otra
pregunta.

### KING-GEX-SLOPE1

K0 y K1 perdieron. Frecuencia y concentración pasaron; falló alpha direccional.
No rescatar por CALL-only, PUT-only, ticker, signo, threshold o mes.

### KING-GEX-EXIT1

Se sellaron 36 source checkpoints, 425.152 contrafactuales, 32 policies y 1.152
celdas auditadas. Ninguna salida fija alcanzó PF1. Stops estrechos reducen cola
pero destruyen recuperaciones; trails tempranos aumentan WR recortando winners.
No ejecutar otro sweep de stops/trails.

Evidencia:
\`research_papers/JEPA/results/_diagnostics/king_gex_exit1_executable_development_2023_v1r1/\`

### Hipótesis físicas

H-FLOW1, H-IVSURF1, H-QSIZE1R1 y H-IBQDYN1 fallaron gates físicas congeladas.
H-QDYN1 cerró en data gate y H-GREEK2WALL quedó bloqueado por entitlement
STANDARD. No rescatar tickers/horizontes post-hoc ni atribuirles PF.

## 5. Hipótesis histórica MANAGE30 — cerrada

La entrada queda fija en dirección \`D1_INVERTED\`, mismo contrato 0DTE
(SPXW d25, QQQ/SPY d35) y ask. La decisión ocurre en la primera quote exacta del
mismo contrato con elapsed 30..31m. Si falta, conserva B00; nunca se usa as-of.

Acciones: las 16 gestiones EXIT1 más \`E30\`, salida inmediata al bid de decisión.

\`M0_PATH\` contiene estado observable hasta +30: retorno actual, MFE, MAE,
drawdown, marks 5/15/30m, slopes, número de quotes, spot returns/RV, spread,
delta, IV, theta, vega, strike y reloj.

\`M1_SYNTH_GREEKS\` añade cambios entrada->+30 de gamma, vanna, charm, DGEX,
zomma, delta, vega y vomma y migración de walls. Siempre marcar
\`SYNTHETIC_MODEL_DERIVED\`: OI unsigned no prueba inventario dealer y estas
variables no son \`/greeks/all\` nativas.

Cada evento produce 17 filas de acción. Target:

\`clip(return_action - return_B00, -2, +2)\`

Modelo fijo: LightGBM Huber por ticker. B00 se fuerza a predicción cero; solo se
cambia por una ventaja predicha >0. Se modela valor contextual, no una etiqueta
oracle plana.

## 6. Walk-forward y traducción live

Cronología de desarrollo:

\`\`\`text
train 2022              -> predice enero 2023
train 2022 + enero      -> predice febrero 2023
...
train hasta noviembre   -> predice diciembre 2023
\`\`\`

Son 72 folds: 12 meses x 3 tickers x M0/M1. Tras puntuar cada oportunidad se
rehace el scheduler cronológico; el hold elegido determina qué entradas
posteriores quedan bloqueadas.

Solo un PASS 36/36 congela un brazo antes de abrir una única evaluación
2024-2025. Si outer pasa, 2026 se evalúa mes a mes: para un mes M solo se
entrena con meses completados <M. Entrenar con todo 2022-2026 y reportar 2026
sería leakage.

Un futuro paquete live debe sellar modelos por ticker, medianas train-only,
orden/allowlist de features, 17 acciones, cutoff, hashes de código/protocolo,
caps/cooldown y state machine stop/trail/horizonte. Snapshots live grabados deben
reproducir exactamente features, acción y salida offline antes de promoción.

## 7. Commits y contratos congelados

Commits relevantes:

- \`649932b3\`: cierre/auditoría KING-GEX-EXIT1.
- \`2529cad5\`: predeclaración MANAGE30.
- \`a8ff2651\`: builder reanudable train/dev.
- \`ed5d7d17\`: aclaración pre-outcome de ventana/join.
- \`b8fa50c8\`: evaluador walk-forward reanudable y tests.

Documentos:

- \`research_papers/JEPA/KING_GEX_MANAGE30_V1_PREDECLARATION.md\`
- SHA \`b534cd8857833285010dccc0ae440f89a4ca8235dd4d2e7c99dd17a731d74948\`
- \`research_papers/JEPA/KING_GEX_MANAGE30_V1_DATA_GATE_CLARIFICATION.md\`
- SHA \`931fc27d74b05760abf9c8a8907fe64ba5d0d046bfb8f64cf16a5d4b16229e46\`

El primer target \`train_dev_202201_202312_v1\` queda rechazado antes de paths y
labels. No reutilizarlo.

Target válido reanudable:

\`tmp/king_gex_manage30_v1/train_dev_202201_202312_v1r1\`

Checkpoint 2026-07-15 16:47: 843 manifests de sesión, cero errores reportados y
proceso activo. El PID es efímero; verificar command line antes de asumir estado.
No lanzar duplicado.

Comando de resume, solo si el original murió:

\`\`\`powershell
python neural/jepa/build_king_gex_manage30_v1.py \`
  --output-dir tmp/king_gex_manage30_v1/train_dev_202201_202312_v1r1 \`
  --workers 4
\`\`\`

Debe terminar con 22.273 rows únicas, B00 finito/hold30..180 y
\`SUMMARY.json status=PASS_DATA_GATE\`. Auditar \`decision_coverage\` y
\`synth_complete_coverage\` antes del modelo.

Runner:

\`\`\`powershell
python neural/jepa/evaluate_king_gex_manage30_v1.py \`
  --dataset tmp/king_gex_manage30_v1/train_dev_202201_202312_v1r1/king_gex_manage30_train_dev.parquet \`
  --dataset-summary tmp/king_gex_manage30_v1/train_dev_202201_202312_v1r1/SUMMARY.json \`
  --output-dir research_papers/JEPA/results/_diagnostics/king_gex_manage30_development_2023_v1 \`
  --lgb-jobs 4
\`\`\`

El runner pasó 22 tests combinados builder/runner/EXIT1, Ruff y py_compile antes
del commit. Cada fold persiste modelo, medianas, predicciones, trades, métricas y
manifest-last con hashes; un relaunch solo reutiliza identidad byte-exacta.

## 8. Secuencia histórica ya completada

1. Comprobar si el builder V1R1 existente sigue vivo; esperar, no duplicar.
2. Auditar el data gate, 22.273 keys, paridad B00 y coberturas M0/M1.
3. Commit/push de compactos del seal y los cinco handoffs; no versionar el parquet
   grande salvo política explícita.
4. Ejecutar una vez los 72 folds 2023 al target inmutable.
5. Recalcular independientemente scheduler, métricas mensuales y concentración.
6. Si ninguna policy pasa 36/36, cerrar MANAGE30 y no abrir 2024-2026.
7. Si una pasa, commit/push y congelar runner outer antes de leer 2024-2025.
8. Cuando se exponga el loader oficial, auditar el Excel King read-only como
   fuente separada de ideas futuras; no usar una librería alternativa.

## 9. Límite científico

El oracle 16-exits pasa 32/36, no 36/36. Además maximiza retorno por evento, no
valor de cartera ajustado por cuánto tiempo bloquea oportunidades. V1 prueba la
pregunta congelada más simple. Si falla, una V2 requeriría predeclaración nueva
para valor ajustado por duración/oportunidad o una policy secuencial/Q-function;
no se permite convertir ese concepto en rescate post-hoc.

La evidencia auditable son protocolos, código, checkpoints, tests y métricas
persistidas; no razonamiento privado ni un PF sin provenance.

## 10. Checkpoint posterior — snapshot exacto V1R2

El build V1R1 terminó fail-closed tras 1.265/1.267 sesiones, antes del dataset y
de cualquier modelo. QQQ 2022-06-17 contiene quotes a `hh:mm:00` y
`hh:mm:30`; agrupar por minuto permitía que una entrada a `hh:mm:00` eligiera la
quote futura `hh:mm:30` y que M1 mezclara superficies de ambos timestamps. El
master causal usa snapshots exactos. V1R1 queda
`REJECTED_CAUSAL_SNAPSHOT_SEMANTICS` completo.

La segunda sesión reveló una única señal train-only no ejecutable:
`SPXW/20220222/680/PUT`. El master ya tenía strike y outcome ausentes. La
aclaración V1R2, frozen/pushed en `9a8e0b41`, exige `quote_dt == timestamp`,
prohíbe floor/as-of/nearest y registra esa única rejection. Censo fuente 22.273;
dataset executable esperado 22.272. SHA de aclaración:
`35e09f5a2679e2ce807a9439dcf9fa051c3e629fa95003975e02d5f39e39a844`.

Implementación y tests pushed en `a996f260`: QQQ reproduce 6/6 eventos; SPXW
produce 30/31 exactos; `24 passed`, Ruff/compile clean. Target V1R2 activo:

`tmp/king_gex_manage30_v1/train_dev_202201_202312_v1r2`

No lanzar duplicado. Si muere, relanzar el builder anterior cambiando solo el
suffix a `v1r2`. Aún no existe `PASS_DATA_GATE` ni PF/WR/PnL M0/M1.

---

## Archivo histórico conservado — auditoría 2026-07-10

El handoff anterior completo se conserva literalmente a continuación. Los checkpoints fechados arriba lo sustituyen cuando el estado haya cambiado.

# SUMMARY.md — Auditoría causal, backtest/live y estado de correcciones JEPA

**Fecha del registro auditado:** 10 de julio de 2026
**Proyecto:** `Gex-Dashboard-Live`
**Ámbito principal:** sistema JEPA de opciones para `SPXW`/SPX, `SPY` y `QQQ`, incluyendo generación de dataset, entrenamiento, walk-forward, selección de policy, paquete de producción, feed en tiempo real y ejecución del bot.

> **Aviso de alcance:** este resumen se ha reconstruido a partir del registro de trabajo suministrado. El registro termina con trabajo todavía en curso y contiene algunas salidas truncadas. Por tanto, “implementado” significa **modificado en el worktree observado**, no necesariamente commiteado, pusheado, desplegado ni validado después de la última edición.

---

## 1. Estado ejecutivo

### Estado actual del paquete

**NO debe considerarse listo para producción ni causalmente certificado.**

El paquete ubicado en:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/
```

se declara internamente como:

```text
status = production_live_ready
policy_profile = causal1030_intersection_guarded_v1
```

pero el validador endurecido lo rechaza. Los bloqueos confirmados al final del registro son:

1. La policy fue seleccionada reutilizando enero–junio de 2026, los mismos meses presentados como evidencia.
2. El artefacto histórico contiene **55 entradas solapadas** que el runtime live habría rechazado por existir una posición abierta.
3. `SPY` queda con **14 operaciones en su peor mes**, por debajo del requisito estricto de más de 18 operaciones mensuales.
4. Las métricas publicadas proceden de labels legacy que no reproducen correctamente la entrada al `ask` y la salida/stop/trailing mediante `bid`.
5. La reconstrucción causal ask→bid comenzó y produjo un nuevo dataset temporal, pero no se completó en el registro una selección anidada walk-forward ni una nueva promoción de policy.
6. Las últimas modificaciones del selector de perfiles introdujeron un error de colección de tests que no consta como resuelto.

### Conclusión operativa

La policy anterior puede tratarse como **candidata forward para julio de 2026**, porque seleccionar con datos cerrados hasta junio para operar julio es conceptualmente admisible. Lo que no puede afirmarse es que enero–junio sean validación OOS de esa misma policy ni que sus métricas legacy representen la ejecución live.

---

## 2. Identidad real de la policy y documentación desfasada

### Hallazgo

La documentación no describía de forma consistente la policy realmente activa.

Archivos que todavía hacían referencia a la policy anterior `balanced`:

```text
AGENTS.md
README.md
docs/README.md
docs/ARCHITECTURE.tex
docs/DEPLOYMENT_GUIDE.tex
```

Artefactos y commits posteriores apuntaban a:

```text
event_option_frozen2025_causal1030_intersection_guarded_v1_202607
causal1030_intersection_guarded_v1
```

Archivos de producción inspeccionados:

```text
systemd/ai_bot.service
systemd/realtime_feed.service
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json
```

### Riesgo

Una documentación que afirma que se ejecuta `balanced` mientras el servicio carga `causal1030` dificulta:

- reproducir el entrenamiento;
- saber qué ventana horaria y filtros usa live;
- asociar métricas con el paquete correcto;
- detectar divergencias entre el runbook, systemd y los JSON desplegados.

### Implementado

Se verificó que el perfil real del registry era:

```text
causal1030_intersection_guarded_v1
```

### Pendiente

Actualizar de forma coherente:

```text
AGENTS.md
README.md
docs/README.md
docs/ARCHITECTURE.tex
docs/DEPLOYMENT_GUIDE.tex
docs/CODEX_LIVE_SENTINEL_RUNBOOK.md
```

y generar esos documentos desde una única fuente de verdad del paquete, evitando nombres hardcodeados.

---

## 3. Sobreajuste de selección y falsa validación OOS

### Severidad

**P0 — invalida la certificación estadística actual.**

### Hallazgo

La policy final fue elegida con un escáner que probó aproximadamente **1,13 millones de configuraciones por ticker** sobre enero–junio de 2026. Esos mismos meses se mostraban después como validación de la policy.

Archivo del escáner localizado:

```text
tmp/scan_causal1030_intersection.py
```

Resultados afectados:

```text
research_papers/JEPA/results/event_option_mh30trail_causal1030_static_union_deploy202607_intersection_guarded_v1/
research_papers/JEPA/results/event_option_mh30trail_causal1030_static_union_deploy202607_intersection_guarded_v1_walkforward/
```

Metadatos afectados:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json
```

En el registry se observaron componentes con:

```text
select_months = 202601..202606
deploy_month = 202607
```

### Por qué es un problema

Que los modelos base se entrenen solo con 2025 no basta. También son parámetros ajustados:

- threshold;
- dirección CALL/PUT/BOTH;
- ventana de entrada;
- máximo de operaciones;
- cooldown;
- filtros de proximidad;
- guards de riesgo;
- combinación/intersección de componentes.

Si esos elementos se eligen mirando enero–junio, esos meses pasan a ser **selection data**, no OOS.

### Implementado

En:

```text
neural/jepa/validate_event_option_production_package.py
```

se añadieron comprobaciones para:

- exigir `policy_selection_provenance`;
- diferenciar `fixed_pre_oos` y `nested_walk_forward`;
- rechazar intersecciones entre `selection_months` y meses reportados;
- revisar `select_months` de cada componente del registry;
- exigir que cada fold anidado use únicamente meses anteriores;
- exigir hashes/artefactos congelados por fold;
- no aceptar como evidencia OOS un replay de una policy elegida con ese mismo periodo.

Tests añadidos:

```text
tests/test_event_option_production_validator.py
```

Casos cubiertos:

- rechazo de una policy fija que reutiliza el mes evaluado;
- aceptación de folds anidados con fuentes estrictamente anteriores;
- detección de solapamientos entre selección y evaluación.

### Pendiente

Ejecutar una validación realmente causal:

1. Para cada mes `M`, entrenar con meses `< M`.
2. Seleccionar hiperparámetros/configuración solo con meses `< M`.
3. Congelar la policy del fold antes de evaluar `M`.
4. Guardar hash y metadatos de cada policy mensual.
5. Concatenar únicamente los trades OOS de cada fold.
6. No volver a elegir la policy final mirando el conjunto de meses reportado.

Julio de 2026 debe quedar completamente intacto si se usa como primer forward live.

---

## 4. Operaciones solapadas: backtest incompatible con live

### Severidad

**P0 — cambia directamente PnL, volumen y meses positivos.**

### Hallazgo

El backtest/materialización permitía abrir una nueva operación del mismo ticker antes de cerrar la anterior. El bot live mantiene una única posición por ticker y rechaza nuevas entradas mientras está abierta.

Artefacto auditado:

```text
research_papers/JEPA/results/event_option_mh30trail_causal1030_static_union_deploy202607_intersection_guarded_v1/combined_trades.csv
```

Resultado cuantitativo:

```text
Trades publicados:           416
Entradas solapadas:            55
Trades reproducibles en live: 361
```

Al imponer la restricción real:

- `SPY` llegó a **10 operaciones** en el peor mes en uno de los replays;
- abril de 2026 pasó a aproximadamente **−1,999 R**;
- el validador final recomputó un mínimo mensual de `SPY = 14`, todavía por debajo del requisito `>18`.

### Archivos implicados

```text
neural/jepa/materialize_event_static_union.py
neural/jepa/apply_event_static_union_cooldown.py
neural/jepa/scan_event_static_union_configs.py
neural/jepa/walkforward_event_option_gate.py
backtest/backtest_gbt_parquet.py
bots/tradingbot_wrapper_jepa.py
```

### Implementado

En:

```text
neural/jepa/validate_event_option_production_package.py
```

se añadió una auditoría de intervalos:

```text
entry_minute -> entry_minute + exit_minutes
```

para contar cualquier entrada del mismo ticker y día que caiga antes del cierre de la posición anterior.

También se exige:

```text
live_contract.position_overlap_policy = reject_while_open
```

Test específico:

```text
tests/test_event_option_non_overlap.py
```

y test adicional del validador:

```text
tests/test_event_option_production_validator.py
```

### Pendiente

- Aplicar la misma función de no-solapamiento **durante la selección**, no solo al validar el CSV final.
- Regenerar todos los resultados.
- Reoptimizar los límites diarios y cooldown sobre el stream no solapado.
- Confirmar por ticker y mes:
  - PnL > 0;
  - WR > 50%;
  - PF > 1,3;
  - operaciones mensuales > 18.

La policy legacy no supera actualmente estas condiciones al reproducir el runtime.

---

## 5. Rejilla temporal: entrenamiento cada 5 minutos, live casi cada minuto

### Severidad

**P1 alta — cambia qué entrada consume el cupo y bloquea señales posteriores.**

### Hallazgo

El dataset/backtest se generaba en una rejilla de cinco minutos, pero live aceptaba candidatos en casi cualquier minuto.

Auditoría de candidatos live:

```text
Candidatos seleccionados: 876
Fuera de la rejilla:       706
En la rejilla:             170
```

Es decir, aproximadamente cuatro de cada cinco candidatos live no pertenecían al universo temporal de entrenamiento.

Con holds de 30–180 minutos y una sola posición, una entrada a `10:31` puede bloquear la entrada entrenada de `10:35`. El hold mínimo no hace irrelevante la divergencia; la amplifica.

### Archivos implicados

```text
neural/jepa/event_option_live_scorer.py
neural/jepa/event_option_live_snapshot.py
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/runtime_policy_replay_summary.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/components/QQQ_static_union_balanced/QQQ_static_union_balanced.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/components/SPXW_static_union_balanced/SPXW_static_union_balanced.json
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/components/SPY_static_union_balanced/SPY_static_union_balanced.json
```

### Implementado

Se añadió al filtro live:

```json
"entry_sample_minutes": 5,
"entry_sample_anchor_minute_et": "10:00",
"requires_complete_initial_balance": true
```

En:

```text
neural/jepa/event_option_live_scorer.py
```

`apply_candidate_universe_filter()` ahora:

- valida la cadencia;
- valida el anchor;
- rechaza si falta la columna `minute`;
- acepta únicamente minutos congruentes con la rejilla;
- falla cerrado si falta `initial_balance_complete`.

Test:

```text
tests/test_event_option_live_causality.py
```

### Pendiente

- Regenerar los artefactos de métricas con este filtro aplicado desde el principio.
- Evitar editar manualmente los JSON legacy; exportar un paquete nuevo desde una configuración versionada.
- Verificar en logs live que no aparece ninguna entrada off-grid.

---

## 6. Quotes de un segundo, deduplicación y merges muchos-a-muchos

### Severidad

**P1 alta — podía mezclar contratos y segundos distintos.**

### Hallazgo

En:

```text
neural/jepa/event_option_live_snapshot.py
```

los timestamps se truncaban al minuto antes de escoger una cross-section sincronizada. Esto convertía todos los segundos del minuto en la misma clave y podía generar:

- duplicados por `(strike, right)`;
- merges muchos-a-muchos con OHLC;
- selección de una quote obsoleta o parcial;
- mezcla de Greeks, bid/ask y volumen de segundos distintos.

### Implementado

En:

```text
neural/jepa/event_option_live_snapshot.py
```

se modificó:

- `_parse_datetime()` para preservar segundos;
- `_prepare_chain()` para elegir una sola cross-section completa;
- deduplicación por `(strike, right)`;
- merge OHLC agregado y validado como `one_to_one`;
- rechazo de snapshots incompletos;
- control de antigüedad y tolerancia futura;
- selección posterior del anchor exacto `HH:MM:00` para igualar el histórico.

En:

```text
services/realtime_feed.py
```

la ventana de ThetaData se ancla ahora al minuto exacto:

```text
snapshot_end = now_et.replace(second=0, microsecond=0)
```

en lugar de terminar en el segundo actual.

Tests:

```text
tests/test_event_option_live_causality.py
```

cubren:

- cross-section completa;
- ausencia de duplicados;
- no utilización del snapshot parcial posterior;
- timestamp exacto del minuto.

### Pendiente

- Ejecutar replay sobre varios días reales de `rt_data/`.
- Añadir métricas de runtime:
  - número de contratos por snapshot;
  - porcentaje de completitud;
  - edad;
  - duplicados descartados;
  - motivo de rechazo.

---

## 7. Lookahead intraminuto de hasta 59 segundos

### Severidad

**P1 media — no fue el mayor problema, pero cambia señales.**

### Hallazgo

El histórico asociaba Greeks/spot de inicio de minuto con el `close` completo de ese mismo minuto. Ese `close` no es observable en el instante de decisión y puede incorporar hasta 59 segundos de futuro.

Archivos implicados:

```text
neural/jepa/build_event_option_dataset.py
neural/jepa/event_option_live_snapshot.py
services/realtime_feed.py
```

### Medición realizada

La ablación reportó:

```text
Desplazamiento mediano del spot:       1,98 bps
Cambio de signo de ret_5m:            14,75% de los puntos
Cambio del gate de proximidad:         3,89% de los puntos
Sesgo direccional sistemático:         no observado
```

Conclusión: no parece explicar por sí solo todo el edge, pero sí cambia materialmente el universo de señales.

### Implementado

En:

```text
neural/jepa/build_event_option_dataset.py
```

para `option_price_mode="executable_quote"`:

- se usa `underlying_price` de la snapshot de Greeks;
- se usa el último bar subyacente ya completado para volumen;
- el OHLC de opciones se desplaza un minuto porque ThetaData etiqueta las barras por apertura;
- se evita usar el close del minuto todavía abierto.

En:

```text
neural/jepa/event_option_live_snapshot.py
```

live se ancla a `HH:MM:00`.

### Pendiente

- Reentrenar por completo con el dataset causal.
- Comparar señales legacy frente a causal, por ticker y mes.
- Documentar la ablación en un artefacto versionado.

---

## 8. Labels de opciones no ejecutables: `opt_close/high/low` frente a ask→bid

### Severidad

**P0 — el mayor deterioro de métricas observado.**

### Hallazgo

El backtest legacy:

- entraba mediante `opt_close`;
- no pagaba correctamente el `ask`;
- evaluaba stops/trailing con OHLC;
- no reproducía la ruta de bids ejecutables;
- podía tratar highs/lows de trades como si fueran precios realizables.

El runtime live:

- compra aproximadamente al `ask`;
- marca y sale al `bid`.

### Medición realizada

```text
Half-spread de entrada mediano: 0,775%
Half-spread p90:                1,389%
```

Cambiar solo entrada de `opt_close` a `ask`, manteniendo salidas legacy:

```text
PF total: 1,749 -> 1,596
```

La estrategia todavía quedaba por encima de 1,3 en los tres tickers bajo esa aproximación.

Pero al reproducir:

- entrada al ask;
- stop/trailing/salida con bids observados;

el replay cayó a:

```text
WR:                41,35%
PF:                 0,871
Retorno agregado: −18,19
Legacy agregado:  +77,54
```

Por tanto, el principal problema no era el spread aislado, sino la ruta de precios utilizada por el label.

### Archivos implicados

```text
neural/jepa/build_event_option_dataset.py
neural/jepa/walkforward_event_option_gate.py
neural/jepa/walkforward_event_option_profile_selector.py
bots/tradingbot_wrapper_jepa.py
services/realtime_feed.py
```

### Implementado

En:

```text
neural/jepa/build_event_option_dataset.py
```

se añadió/extendió:

- `option_price_mode` con modos `legacy_ohlc` y `executable_quote`;
- entrada usando ask;
- salida y stops mediante bid;
- aceptación de bid cero como pérdida total válida;
- `conservative_no_quote_label()`:
  - si no existe quote posterior ejecutable, fuerza retorno `−1.0`;
  - respeta el menor entre horizonte y cierre de mercado;
- inserción de un bid cero al final si la ruta se corta antes de la salida forzada;
- uso de `underlying_price` observable;
- uso de la barra anterior completada;
- columnas de disponibilidad del contrato;
- columna exacta de strike seleccionada.

En:

```text
neural/jepa/walkforward_event_option_gate.py
neural/jepa/walkforward_event_option_profile_selector.py
```

se añadió:

- validación de disponibilidad observable de CALL y PUT;
- error explícito si faltan columnas necesarias en datasets ejecutables;
- outcomes conservadores finitos;
- clipping solo en el target de regresión, no en el PnL usado para métricas.

En:

```text
bots/tradingbot_wrapper_jepa.py
```

se corrigió:

- bid cero como mark real, no como quote ausente;
- `NaN` para ausencia/ambigüedad de quote;
- no cerrar prematuramente por un dato ausente;
- cierre real por stop si el bid observable es cero.

Tests:

```text
tests/test_build_event_option_dataset.py
tests/test_jepa_bot_execution.py
```

### Pendiente

- Completar entrenamiento y nested walk-forward sobre `executable_quote`.
- Comparar los labels generados con ejecuciones paper reales.
- Modelar slippage adicional si se usan market orders.
- No promover ningún artefacto legacy como evidencia de rentabilidad live.

---

## 9. Contrato exacto: el bot podía ejecutar otro strike distinto del evaluado

### Severidad

**P1 alta — backtest y live podían referirse a contratos diferentes.**

### Hallazgo

La fila del modelo identificaba un contrato por delta, pero el bot volvía a seleccionar por delta al ejecutar. En empates o cambios rápidos podía elegir un strike distinto del usado para features y label.

Archivos implicados:

```text
neural/jepa/build_event_option_dataset.py
bots/tradingbot_wrapper_jepa.py
```

### Implementado

En el dataset se añadieron:

```text
call_dXX_strike
put_dXX_strike
```

En el bot:

- `_select_delta_option()` admite `strike_target`;
- el candidato live debe contener el strike seleccionado;
- si falta o es inválido, se rechaza;
- el bot ejecuta el strike exacto de la snapshot evaluada.

Test:

```text
tests/test_jepa_bot_execution.py
```

verifica que un empate de delta no sustituya el strike seleccionado.

### Pendiente

Añadir también al contrato verificable:

- símbolo OCC exacto;
- expiración;
- right;
- timestamp de quote;
- hash o identificador de snapshot.

---

## 10. Expiración incorrecta y snapshots de otro día

### Severidad

**P1 alta — una posición 0DTE podía valorarse con otro vencimiento o datos stale.**

### Hallazgo

Se detectaron riesgos de:

- posición persistida sin expiración;
- búsqueda ambigua de la quote;
- uso del snapshot más reciente aunque fuera de otra fecha;
- uso de initial balance del día anterior.

Archivos implicados:

```text
bots/tradingbot_wrapper_jepa.py
neural/jepa/event_option_live_snapshot.py
```

### Implementado

En el bot:

- se exige expiración para valorar la posición;
- si falta, se devuelve `NaN` y se rechaza la valoración ambigua;
- se filtran snapshots por la fecha ET actual;
- se filtra por expiración exacta;
- no se reutilizan filas stale de otra sesión.

En snapshot:

- el historial spot se restringe al mismo día de la snapshot;
- `_latest_spot_at()` ya no cae hacia una observación futura;
- se rechaza initial balance proveniente del día anterior;
- se aplican límites de edad de snapshot.

Tests:

```text
tests/test_event_option_live_causality.py
tests/test_jepa_bot_execution.py
```

### Pendiente

- Migrar o invalidar posiciones persistidas antiguas que no contengan expiración.
- Añadir versión de esquema al estado persistido.
- Incluir un procedimiento explícito de recuperación tras reinicio.

---

## 11. Initial Balance incompleto y fallback sintético

### Hallazgo

El snapshot live podía construir features aunque faltaran minutos de `09:30–10:29`, e incluso crear un fallback sintético a partir del spot actual.

Esto hacía que features de IB parecieran disponibles sin que el rango inicial estuviera completo.

Archivo:

```text
neural/jepa/event_option_live_snapshot.py
```

### Implementado

Se añadió:

```text
_initial_balance_complete()
```

que exige los 60 minutos `570..629`.

`build_snapshot_row()` ahora:

- devuelve `None` si el IB no está completo;
- deja de crear un historial sintético de una sola fila;
- publica `initial_balance_complete = 1` solo cuando el contrato se cumple.

El scorer falla cerrado si la columna requerida falta.

Tests:

```text
tests/test_event_option_live_causality.py
```

### Pendiente

Incluir en logs el minuto concreto ausente y diferenciar:

- feed todavía inicializando;
- hueco de datos;
- día de sesión reducida;
- mercado cerrado.

---

## 12. Contexto cross-index incorrecto: `front_weekly` frente a `zero_dte`

### Hallazgo

Al construir contexto cross-index live, la ordenación podía seleccionar `front_weekly` por orden léxico, mientras el entrenamiento usaba contexto del dataset `zero_dte`.

Archivo:

```text
neural/jepa/event_option_live_snapshot.py
```

### Implementado

Cuando hay filas `zero_dte`, se priorizan para el contexto de:

```text
SPXW
SPY
QQQ
```

Test:

```text
tests/test_event_option_live_causality.py
```

### Pendiente

Hacer explícito en la policy qué expiry mode alimenta cada contexto, en vez de depender de una prioridad implícita.

---

## 13. Feature de volumen incompatible entre histórico y live

### Hallazgo

Histórico usaba:

```text
tick_count
```

mientras live almacenaba la misma magnitud causal bajo:

```text
volume
```

Esto dejaba `underlying_volume = 0` en live.

Archivo:

```text
neural/jepa/event_option_live_snapshot.py
```

### Implementado

`_standardize_spot_frame()` mapea:

```text
volume -> tick_count
```

cuando `tick_count` no existe.

Además, para el instante de decisión se usa el volumen del último minuto completado.

Test:

```text
tests/test_event_option_live_causality.py
```

Resultado observado en replay de snapshot:

```text
underlying_volume = 60.0
```

### Pendiente

Renombrar la columna en origen o publicar un schema explícito para no depender de alias.

---

## 14. Features intradía no observables o inconsistentes en live

### Hallazgo

El selector de perfiles podía incluir features cuyo valor offline no estaba disponible o no era equivalente en el minuto de decisión live.

Archivos:

```text
neural/jepa/event_option_component_live.py
neural/jepa/walkforward_event_option_profile_selector.py
```

### Implementado

En:

```text
neural/jepa/walkforward_event_option_profile_selector.py
```

se añadió:

- filtro `live_observable_features_only=True`;
- `entry_start_minute_et`;
- exclusión por prefijos;
- consulta a `live_observable_feature_issues_for_columns()`;
- almacenamiento de `features_by_profile` en resultados;
- nuevo universo `production_zero_dte`;
- filtro mínimo de `positive_month_rate`.

En:

```text
neural/jepa/event_option_component_live.py
```

se dejó de eliminar completamente filas con NaN legítimos. Ahora:

- schema drift o columnas ausentes siguen siendo error;
- NaN ordinarios se imputan con las medianas congeladas del entrenamiento;
- se registra `imputed_rows` en vez de alterar silenciosamente el universo.

### Problema pendiente importante

Después de estas modificaciones se añadió un test en:

```text
tests/test_event_option_live_causality.py
```

pero su ejecución terminó dos veces con:

```text
ERROR during collection
```

Se intentó corregir el import dual paquete/script en:

```text
neural/jepa/walkforward_event_option_profile_selector.py
```

pero el registro no muestra una ejecución posterior exitosa.

Por tanto, esta parte debe considerarse **implementación incompleta/no validada**.

---

## 15. Validador demasiado permisivo y autocertificación por JSON

### Severidad

**P0 de proceso — permitía marcar como live-ready un paquete incompatible.**

### Hallazgo

El validador anterior:

- confiaba demasiado en métricas precalculadas dentro de JSON;
- aceptaba gates más laxas, como alrededor de 45% WR y 12 trades;
- no recalculaba todas las métricas desde trades;
- no auditaba selección temporal;
- no auditaba rejilla de entrada;
- no auditaba solapamientos;
- no exigía labels ejecutables.

Archivo:

```text
neural/jepa/validate_event_option_production_package.py
```

### Implementado

El validador ahora:

- carga el artefacto de trades;
- recalcula trades, WR, PF, PnL, mínimo mensual y tasa de meses positivos;
- incluye meses sin trades como conteo cero;
- restringe el cálculo a los meses declarados;
- compara las métricas recalculadas con las publicadas;
- exige como mínimo:
  - `WR >= 0.50`;
  - `PF >= 1.30`;
  - `min_month_trades > 18`;
  - `positive_month_rate = 1.0`;
- detecta entradas off-grid;
- detecta solapamientos;
- valida selección OOS;
- valida `executable_quote`;
- valida duración y columnas necesarias;
- rechaza artefactos vacíos o no recomputables.

Resultado sobre el paquete actual:

```text
FAIL
- SPY min_month_trades = 14
- 55 overlapping same-ticker entries
- selección solapada con meses reportados
- labels no ejecutables
```

Tests:

```text
tests/test_event_option_production_validator.py
```

### Pendiente

- Integrar el validador en `ExecStartPre=` de systemd o en el pipeline de despliegue.
- Impedir que un JSON conserve `production_live_ready` si la validación falla.
- Firmar/hashar los artefactos que el validador recomputa.
- Añadir una opción que escriba un informe JSON/Markdown de bloqueo.

---

## 16. Semántica del capital de riesgo de 5.000 USD

### Hallazgo inicial

Se señaló que el bot podía abrir un contrato cuyo débito superara 5.000 USD.

Archivo:

```text
bots/tradingbot_wrapper_jepa.py
```

### Decisión de diseño adoptada

Se reinterpretó `risk_capital_dollars` como **objetivo de sizing**, no como techo absoluto. Debido a que un contrato es indivisible, se permite al menos uno aunque su coste supere el objetivo.

Implementación:

```text
_contracts() -> max(1, floor(risk_capital / contract_cost))
```

si coste y capital son positivos.

La documentación interna del bot se ajustó para decir que un contrato indivisible puede exceder el target.

### Pendiente

La policy debe declarar de forma inequívoca uno de estos modos:

```text
hard_debit_cap
sizing_target_allow_one_contract
```

No debe inferirse por comentarios del código.

---

## 17. Rebuild causal generado, pero no promovido

### Dataset temporal generado

Se ejecutó:

```text
neural/jepa/build_event_option_dataset.py
```

con:

```text
option_price_mode = executable_quote
tickers = SPXW SPY QQQ
expiry_modes = zero_dte
periodo = 2025-01-01 .. 2026-06-30
manifest rows = 1.113
```

Salida temporal:

```text
tmp/event_option_dataset_execquote_causal1030_202501_202606_v3/event_option_dataset.parquet
```

Después se enriqueció con:

```text
neural/jepa/enhance_event_option_dataset_physics.py
```

Salida:

```text
tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet
tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/SUMMARY.json
```

Comprobaciones registradas:

```text
shape = (44169, 239)
duplicate key rows = 0
sha256 = 68ae45c89d521f71431261deea9bcc7e465feb294d17bf122afbddbb30a4c8f8
date_max = 20260630
```

### Estado

El dataset causal parece haberse construido y enriquecido, pero permanece bajo `tmp/`.

### Pendiente

- Verificar exhaustivamente todas las sesiones.
- Guardar manifiesto de fuentes y hashes.
- Mover a una ruta versionada de `research_papers/JEPA/results/_diagnostics/`.
- Ejecutar selección anidada.
- Generar trades OOS.
- Ejecutar validador estricto.
- Exportar un paquete nuevo; no sobrescribir silenciosamente el legacy.
- Comparar live replay con el nuevo dataset.

---

## 18. Tests y validaciones ejecutadas

### Ejecuciones exitosas observadas

En distintos puntos del registro:

```text
6 passed
7 passed
16 passed
16 passed
35/35 nuevas pruebas
40 passed
```

Suite de 40 tests:

```text
tests/test_build_event_option_dataset.py
tests/test_event_option_live_causality.py
tests/test_event_option_non_overlap.py
tests/test_event_option_production_validator.py
tests/test_jepa_bot_execution.py
```

También pasó `py_compile` para:

```text
services/realtime_feed.py
bots/tradingbot_wrapper_jepa.py
neural/jepa/build_event_option_dataset.py
neural/jepa/event_option_live_snapshot.py
neural/jepa/event_option_live_scorer.py
neural/jepa/validate_event_option_production_package.py
neural/jepa/walkforward_event_option_gate.py
```

### Último estado de tests

Después de añadir la exclusión de features no observables al selector:

```text
tests/test_event_option_live_causality.py
```

falló durante collection dos veces.

Por tanto:

- el bloque anterior estaba verde;
- el estado final del worktree **no estaba completamente verde**;
- falta capturar y corregir el traceback final.

### Tests nuevos relevantes

```text
tests/test_event_option_live_causality.py
tests/test_event_option_production_validator.py
tests/test_build_event_option_dataset.py
tests/test_jepa_bot_execution.py
tests/test_event_option_non_overlap.py
```

---

## 19. Estado de Git y versionado

### Commits existentes antes de las correcciones

```text
66731f6 Deploy causal 10:30 JEPA event option policy
4ad505c Add causal policy verification artifacts
153f1a7 Update live sentinel runbook for causal policy
```

Al reiniciarse la sesión posterior:

```text
HEAD = 153f1a7
origin/main = 153f1a7
```

### Estado observado

Había numerosos archivos tracked modificados y varios artefactos untracked, entre ellos:

```text
bots/tradingbot_wrapper_jepa.py
services/realtime_feed.py
backtest/backtest_gbt_parquet.py
neural/jepa/build_event_option_dataset.py
neural/jepa/event_option_live_snapshot.py
neural/jepa/event_option_live_scorer.py
neural/jepa/event_option_component_live.py
neural/jepa/validate_event_option_production_package.py
neural/jepa/walkforward_event_option_gate.py
neural/jepa/walkforward_event_option_profile_selector.py
neural/jepa/apply_event_static_union_cooldown.py
tests/test_event_option_live_causality.py
tests/test_event_option_production_validator.py
tests/test_build_event_option_dataset.py
tests/test_event_option_non_overlap.py
tests/test_jepa_bot_execution.py
tmp/
```

### Conclusión

El registro **no muestra ningún `git commit` ni `git push` posterior a estas correcciones**.

### Pendiente

Separar en commits revisables:

1. `fix: align live snapshot timestamps and 5m sampling`
2. `fix: enforce exact option contract and expiration`
3. `fix: add executable ask-to-bid labels`
4. `fix: enforce no-overlap in backtest and validation`
5. `fix: require causal policy-selection provenance`
6. `test: add JEPA live/backtest regression suite`
7. `data: add causal dataset manifest and hashes`
8. `model: add nested walk-forward production candidate`
9. `docs: synchronize production policy and runbooks`

No hacer push de datasets grandes o `tmp/` sin revisar `.gitignore` y tamaño.

---

## 20. Prioridad recomendada para continuar

### P0 — antes de cualquier despliegue

1. Corregir el error de collection introducido en el selector.
2. Ejecutar la suite completa.
3. Congelar y versionar el dataset `executable_quote`.
4. Implementar selección nested walk-forward.
5. Aplicar no-solapamiento durante selección y evaluación.
6. Validar todos los meses con gates estrictas.
7. Exportar un paquete nuevo con nombre distinto.
8. Ejecutar el validador estricto y un replay equivalente a live.
9. Solo entonces cambiar systemd.

### P1 — robustez live

1. Añadir telemetría de snapshots incompletos/stale/off-grid.
2. Versionar el estado persistido de posiciones.
3. Validar símbolos, expiración, strike y right exactos.
4. Añadir smoke test de arranque equivalente a systemd.
5. Verificar rutas y permisos del usuario del servicio.

### P2 — documentación y proceso

1. Actualizar documentación desfasada.
2. Generar documentación desde el manifest de producción.
3. Hacer commits atómicos y push.
4. Crear un checklist de promoción y rollback.

---

## 21. Criterios de aceptación del siguiente paquete

El siguiente paquete solo debe marcarse `production_live_ready` si cumple simultáneamente:

### Causalidad

- Cada mes se evalúa con modelo y policy congelados antes de ese mes.
- Ningún mes evaluado aparece en train, selection o tuning de su fold.
- Features observables en el minuto de decisión.
- No se usan barras todavía abiertas.
- Entrada y salida usan precios ejecutables.

### Equivalencia live

- Rejilla de cinco minutos idéntica.
- Una sola posición por ticker.
- Mismos límites diarios y cooldown.
- Mismo contrato exacto.
- Misma expiración.
- Misma semántica de bid cero y quote ausente.
- Mismo tratamiento de missing values.

### Métricas por ticker

Para cada uno de:

```text
SPXW
SPY
QQQ
```

y para cada mes OOS:

```text
PnL mensual > 0
Win rate > 50%
Profit factor > 1,3
Trades mensuales > 18
```

### Artefactos

- Dataset y manifest con SHA-256.
- Configuración por fold.
- Hash de policy por fold.
- Trades OOS concatenados.
- Métricas recomputables desde CSV/Parquet.
- Validador estricto en PASS.
- Tests completos en PASS.
- Commit y tag de release.
- Runbook y rollback actualizados.

---

## 22. Dictamen final

La auditoría encontró problemas reales y cuantitativamente relevantes. El mayor no fue el pequeño spread ni el desfase medio de spot, sino la combinación de:

1. selección de policy sobre el mismo periodo reportado;
2. operaciones solapadas imposibles en live;
3. labels basados en OHLC que no reproducían bids ejecutables;
4. universo temporal live distinto del entrenamiento;
5. contrato exacto y expiración no completamente fijados;
6. validador que permitía autocertificación.

Una parte sustancial de las defensas ya fue implementada en el worktree y cubierta por tests. También se generó un dataset causal ask→bid temporal. Sin embargo, al final del registro faltaban:

- resolver el último error de tests;
- completar el nested walk-forward;
- obtener métricas que satisfagan los objetivos;
- exportar una policy nueva;
- validar systemd;
- hacer commit y push.

**Estado recomendado: `BLOCKED_FOR_PRODUCTION`.**

---

## 23. Cierre KING-GEX-MANAGE30-V1 — 2026-07-16

V1R2 terminó `PASS_DATA_GATE`: 22.273 source, 22.272 executable, 1.267
sesiones, 186 columnas, cobertura decision/M1 100% y dataset SHA
`2c7ff0485c5f5c8b99fea6c6209c1e56dcb37ee479a684f3a7dc3cff67df000b`.
El fix de inferencia causal quedó pushed en `8587bc7e`: la disponibilidad de
acciones ya no consulta outcomes; B00 siempre existe y las demás requieren
estado observable +30m.

El one-shot walk-forward 2023 cerró `FAILED_ECONOMIC_DEVELOPMENT` sin abrir
2024–2026. M0: 1.478 trades, WR38,90%, PF0,905, -34,942R y 3/36 celdas. M1:
1.502, WR39,08%, PF0,901, -36,299R y 5/36; además falla concentración SPY.
Ningún brazo elegible. No abrir outer, neural net, otro target ni rescate
post-hoc 0DTE.

## 24. Cierre WEEKLY-MULTIDAY-ORACLE-V1 — 2026-07-16

Para evitar una cadena de datasets se congeló un único audit sin features ni
modelo en commit `cf536c53`: delta 0,50, entrada 10:35 ask, mismo contrato,
salida bid dos sesiones después y scheduler no-overlap. Histórico 2022–2025:
2.364 oportunidades físicas y 2.361 executable; cobertura PASS.

El `NON_OVERLAP_ORACLE` futuro muestra headroom direccional pero queda
`CLOSED_ORACLE_GATE`: QQQ 416 trades/WR71,88%/PF12,277/+248,521R; SPXW
417/73,62%/13,960/+257,564R; SPY 417/74,10%/13,876/+254,866R. PF y PnL pasan
todos los meses, pero 16/144 ticker-meses tienen WR <=50% y la capacidad es
solo 8–10 trades/mes. Con hold de dos sesiones y `reject_while_open`, 18
trades/mes es matemáticamente imposible.

Los controles desplegables no demuestran edge: always-CALL PF1,042–1,056 y
WR40,63–41,73%; always-PUT PF0,771–0,808. El spread de entrada mediano sí baja
a 0,46–0,82%, pero theta de dos noches equivale aproximadamente al 26–31% de
la prima y CALL/PUT pierden simultáneamente en ~26,6–27,1% de oportunidades.
Toda la rentabilidad grande exige resolver dirección futura. Según la gate
predeclarada no se abre dataset/modelo weekly ni se barren horizontes/deltas.

Producción y 2026 permanecen intactos. Estado: no existe hoy una policy causal
rentable/promovible bajo las metas estrictas; la investigación queda cerrada,
no “activa”, hasta que el usuario cambie prospectivamente frecuencia/WR o
autorice una hipótesis realmente nueva.

## 25. Checkpoint autoritativo posterior — 2026-07-16

### Gate vigente y validez de 2026

La solicitud económica más reciente exige por ticker PF>1,20, WR>45%, más de
12 trades en cada mes y PnL mensual positivo, cubriendo enero–15 julio 2026.
Enero–julio ya fue consultado por varias familias adaptativas y no constituye un
holdout prístino. Un PASS futuro necesitaría shadow/prospectivo; no autorizaría
por sí solo producción.

### Futuros Globex: near-miss que no generaliza

Se capturaron y sellaron, sin tocar live, siete continuos Yahoo 60m entre
2024-07-17 y 2026-07-15: ES, NQ, YM, RTY, ZN, GC y CL. Manifest SHA
`dad8dc52...dcb7`, seal `eaa56342`. `VX=F` devolvió 404 y el proveedor limita
60m a 730 días. El panel final exige simultáneamente esos siete futuros y los
15 cash tickers; los faltantes se eliminan para todos.

V1 fue prometedor solo en desarrollo 2025:

| Ticker | Trades | WR | PF | Meses + | Mín/mes |
| --- | ---: | ---: | ---: | ---: | ---: |
| QQQ | 412 | 52,18% | 1,200 | 9/12 | 22 |
| SPX | 412 | 51,21% | 1,206 | 9/12 | 22 |
| SPY | 412 | 51,21% | 1,210 | 9/12 | 22 |

El freeze se preservó antes del one-shot 2026, donde falló:

| Ticker | Trades | WR | PF | PnL bps | Meses + | Mín/mes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 251 | 46,61% | 0,873 | -804,11 | 2/7 | 20 |
| SPX | 251 | 47,81% | 0,899 | -455,04 | 3/7 | 20 |
| SPY | 251 | 47,81% | 0,888 | -502,84 | 3/7 | 20 |

Tres intentos adaptativos quedaron cerrados antes de 2026: online linear V2 PF
0,980/0,976/0,996; expert Hedge V3 1,140/1,137/1,098 pero solo 5/6/5 meses
positivos; meta-Hedge V4 1,161/0,933/0,965 y 4/5/5. Esto falsifica estabilidad,
no la mera existencia de algún mes o regla rentable.

### Payoffs alternativos y ejecución técnica

`SHORT_PREMIUM_FIXED_HORIZON_V2` no llegó a economía. A 100/1.506 sesiones,
4.271 candidatos incluían 13 salidas exactas no ejecutables en QQQ 2024-02-06.
Como el protocolo prohibía omitir una estructura resoluble en entrada, queda
`REJECTED_DATA_GATE` sin PF/WR/PnL.

`DUAL_LEG_EVENT_VOLATILITY_V1` compró CALL+PUT 0DTE equal-dollar con ask->bid,
haircut y scheduler global no-overlap. En 2025 produjo 613 trades/ticker y
falló: PF QQQ/SPX/SPY 0,629/0,661/0,605, WR 35,07/33,28/36,22%, solo 2/2/1
meses positivos. No se abrió 2026.

`DIRECTIONAL_IB_BREAKOUT_FADE_V1` usó el panel común de 15 tickers, IB exacto
09:30–10:29, dos ventanas, entrada al open siguiente, stop-first y escala Fib.
En 2025 dio PF 0,779/0,785/0,819, WR 31,28/32,41/31,94%, aunque conservó
24–25 trades mínimos por mes. Tampoco abrió 2026.

### Diagnóstico científico acumulado

JEPA sí sufría colapso espectral parcial, pero arreglarlo no creó alpha: el
factorized innovation JEPA con VISReg alcanzó rango efectivo z 53,54% y dz
42,67% y siguió con PF<1 en QQQ/SPX/SPY. Breadth, superficie de opciones,
futuros, reglas online y Fib tampoco estabilizaron meses. El problema observado
no es solo decay de opciones; la dirección causal cambia de régimen y las
features actuales no contienen una ventaja estable suficiente.

Estado: `NO_PROFITABLE_CAUSAL_POLICY`. Producción/paper-intents intactos. No
hay experimento activo. No continuar con variantes post-hoc de estas familias ni
con datasets repetidos. Una hipótesis futura debe ser económicamente independiente
o usar una fuente broker-grade nueva y predeclarada con paridad live.

## 26. Checkpoint autoritativo — 2026-07-17

`main` y `origin/main` parten sincronizados de `d02b1ad9`; el worktree tracked
estaba limpio. Los untracked antiguos del usuario se preservan y no forman parte
de la nueva investigación. `ECONOMIC_FAMILY_REGISTRY.md` estaba desfasado al
marcar King activo y queda reconciliado con sus cierres económicos.

Nueva familia activa: `CROSS_SESSION_RELATIVE_VALUE_V1`, predeclarada antes de
abrir outcomes. Es un test spot ledger-only, no otro dataset ni una policy 0DTE:

```text
shock_i = log(close_i(10:34) / prior_RTH_close_i) * 10.000
relative_shock = shock_QQQ - 0,5 * (shock_SPY + shock_SPXW)
relative_shock > 0 -> short QQQ / long SPY
relative_shock < 0 -> long QQQ / short SPY
entry/exit = open 10:36 / open 13:36
cost = 1 bp por pata; hold = 180m
```

Fuente outcome-free: 1.003 Parquets por ticker en 2022–2025, schema exacto
underlying 1m. Se excluyen por calendario las medias jornadas y por defecto de
fuente conocido el 2023-06-05; no se excluye ningún retorno. No hay beta fit,
z-score, threshold, grid, modelo o abstención.

La única fase autorizada es implementar/testar el ledger y ejecutar desarrollo
2022–2023. Gate por cada mes del spread: PF>1,20, WR>45%, >12 trades, PnL>0 y
cero fallos de reloj/overlap. Solo un PASS permitiría congelar antes de abrir
2024–2025. Todo 2026, opciones y producción siguen cerrados. Un fallo cierra V1
sin invertir la regla ni retocar ancla/reloj/coste.

Runner pre-outcome implementado en
`neural/jepa/evaluate_cross_session_relative_value_v1.py`. No expone `end-date`:
el cutoff 2023 está hardcoded, rehashea las fuentes y escribe atómicamente solo
inventario, ledger, meses, controles y manifest. Cinco tests sintéticos cubren
no-futuro de 10:35, payoff/coste, prior close half-day, exclusiones y meses cero.
Commit/push del código es obligatorio antes del desarrollo real.

`CROSS_SESSION_RELATIVE_VALUE_V1_DATA_GATE_CLARIFICATION.md` fija el tratamiento
de 2023-06-05: sin trade, sin imputar las tres barras SPY inválidas, pero usando
solo el close 16:00 válido como prior close del 06-06. El loader exige que no
exista ninguna anomalía adicional. La aclaración queda hasheada en el manifest.

## 27. Cierre CROSS_SESSION_RELATIVE_VALUE_V1

El único ledger development 2022–2023 terminó `FAILED_ECONOMIC_DEVELOPMENT`:

| Trades | WR | PF | PnL bps | Mín/mes | Meses + | Meses PASS |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 496 | 41,532% | 0,627276 | -2.349,329 | 19 | 5/24 | 2/24 |

La auditoría independiente reprodujo métricas, 180m exactos, coste 2 bps, cero
overlaps y cero fechas posteriores a 2023. Solo octubre 2022 y junio 2023 pasan
todas las gates. Momentum opuesto fue PF1,075/+365,329 bps, pero estaba
congelado como control, no pasa PF1,20 y no puede rescatar la familia.

No se abrió 2024–2026 ni se tocaron opciones/producción. Cierre detallado:
`research_papers/JEPA/CROSS_SESSION_RELATIVE_VALUE_V1_CLOSURE.md`. El programa
queda `NO_PROFITABLE_CAUSAL_POLICY` y sin familia activa; no retunar esta
divergencia con beta, z-score, thresholds o ML.

## 28. Nueva familia activa — OPENING_RELATIVE_MOMENTUM_V1

La meta completa por ticker sigue intacta. Como paso incremental se prueba una
señal relative-value nueva, no el signo inverso del cross-session cerrado:

```text
opening_i = log(close_i(10:34) / open_i(09:30)) * 10.000
impulse = opening_QQQ - 0,5*(opening_SPY + opening_SPXW)
impulse > 0 -> long QQQ / short SPY
impulse < 0 -> short QQQ / long SPY
entry/exit 10:36/13:36, hold180, cost2bps
```

No previous close, gap, beta, z-score, threshold, ML ni abstención. Desarrollo
2022–2023. `INCREMENTAL_EDGE_ONLY` registra PF agregado>1 sin rebajar la gate;
solo PF>1,20/WR>45%/>12/PnL>0 en cada uno de 24 meses abre un freeze outer.
2024–2026 y producción permanecen cerrados.

Implementación pre-outcome: `evaluate_opening_relative_momentum_v1.py` y tests
sintéticos. El runner hereda solo validación/source hashing del ledger cerrado,
calcula una señal distinta, fija cutoff 2023 y persiste estados incrementales
sin autorizarlos como PASS. Debe commit/push antes del desarrollo real.

Primer launch: stop pre-source/pre-output por import directo del paquete. El
target no existe. Se añade bootstrap de repo root y regresión subprocess CLI;
no se reutiliza ningún resultado ni cambia el protocolo.

## 29. Cierre OPENING_RELATIVE_MOMENTUM_V1

El desarrollo único 2022–2023 terminó `NO_AGGREGATE_EDGE`:

| Trades | WR | PF | PnL bps | Mín/mes | Meses + | Meses PASS |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 497 | 50,905% | 0,831462 | -927,689 | 19 | 7/24 | 4/24 |

La auditoría independiente reprodujo métricas, reloj 10:36→13:36, hold180,
coste2bps, exclusiones, cero overlaps y cero filas posteriores a 2023. Los
controles mean-reversion y long-QQQ/short-SPY fijo también pierden: PF0,813 y
PF0,924. Cierre detallado en
`research_papers/JEPA/OPENING_RELATIVE_MOMENTUM_V1_CLOSURE.md`.

No se abre outer ni se selecciona signo/mes/threshold/stop. El hallazgo útil es
que WR agregado supera 50% pero PF queda bajo uno: una hipótesis nueva debe
explicar causalmente la asimetría de pérdidas. Estado actual:
`NO_PROFITABLE_CAUSAL_POLICY`, ninguna familia activa y producción intacta.

## 30. Predeclaración OPTION_PARITY_PRESSURE_V1

La siguiente medición es independiente de precio-only, IV/skew y walls. Para
cada ticker empareja CALL/PUT 0DTE del mismo strike a 10:30 y 10:35, conserva
strikes comunes dentro de 100bps y calcula el cambio de
`(K+Cmid-Pmid-spot)` normalizado por el spread conjunto. El signo de la mediana
cross-strike será la única acción futura; no hay modelo, threshold o grid.

La fase actual es exclusivamente data gate 2022–2023. Bid/ask permanecen los
del Greek vintage; el sidecar nativo solo aporta timestamp/keys y el spot procede
del underlying derivado exacto. PASS exige >=3 strikes, >=90% coverage por
ticker-año, >12 eventos mensuales y no-degeneración. No se puede abrir ningún
retorno, 2024–2026 o producción hasta commit del gate y runner posterior.

Amendment pre-outcome autorizado: 2022 se elimina completo porque febrero solo
tiene 12 vencimientos 0DTE, capacidad incompatible con `>12`. La secuencia pasa
a data gate 2023–2025, desarrollo 2023, outer 2024–2025 y holdout 2026 únicamente
después de dos PASS/freezes. No cambian señal, reloj, coste ni gates.

El censo reproducible de capacidad queda `PASS_FREQUENCY_CAPACITY`: 752 fuentes
exact-0DTE por ticker, 2.256 total y mínimo18 sesiones elegibles en cada mes de
2023–2025. No leyó quotes ni outcomes. El data gate de la variable física sigue
pendiente; aún no existe rentabilidad `OPTION_PARITY_PRESSURE_V1`.

El primer data-gate no llegó a evaluar coverage: 104 sesiones quedaron vacías
por comparar strings sin `.000` contra timestamps con milisegundos. Una lectura
datetime confirmó 10:30/10:35 exactos. V1 se preserva REJECTED; la aclaración
permite solo ambas codificaciones equivalentes y ordena relaunch V1R1 tras
commit. No cambia ninguna feature/gate ni abre outcomes.
