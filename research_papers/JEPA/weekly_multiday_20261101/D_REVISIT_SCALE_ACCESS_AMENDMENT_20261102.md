# D: acceso acotado para la escala del replay futuro

Estado: DOCUMENTARY_CANDIDATE_REQUIRES_REVIEW_AND_PUBLICATION.
Fecha: 2 de noviembre de 2026. Preparación exclusivamente sintética.

La integración D cerró ocho pruebas artificiales con acuerdo de productor y
auditor independiente. No acredita rendimiento con millones de observaciones.
La revisión estática posterior encontró una causa material para preparar una
versión nueva: scan reconstruye todos los spots del ticker por anchor, cobertura
vuelve a recorrerlos por evento y la búsqueda de triggers/salidas recorre el
histórico completo. Se crean además colecciones auxiliares completas para
validación e índices duplicados. El coste de esos accesos crece como
sum(E_t*S_t), donde E_t es el número de eventos y S_t los spots de cada ticker.

Los conteos declarados por B02 son 1620 planes, 3240 decisiones, 1086570 spots
y 3606310 observaciones de opción. Se usan aquí sólo para motivar la revisión
de escala: B06 sigue activo, los valores B no están admitidos y no se abre
ninguno de esos payloads. No se ha observado OOM ni medido el tiempo de D real;
el número de anchors confluyentes y la distribución real siguen pendientes.

El autor independiente del auditor detectó por separado que _valid_quotes
recorre Q quotes globales por consulta de entrada y por cada una de las cuatro
salidas. Su coste es O((W+4I)*Q), para W winners e I intents admitidos. También
identificó copias de grids por FSM, filtrado global de eventos por plan y
filtrado de ledger por intent. No leyó productor ni helper para este análisis.
Los índices por decisión/plan/intent y la reutilización de grids originales
quedan dentro de esta corrección; el algoritmo de target/distancia y la cola
contable se conservan sin reescritura, pues no son el cuello principal.

Esta enmienda mantiene la autorización de preparación pura de
D_REVISIT_PARALLEL_MECHANICS_PREPARATION_AMENDMENT_20261102.md,
7109B/d5a6be66d4a47ad4a4eca4957bccf96049838eabe1b176904c3d16f04ef37f7f.
Tras revisión independiente y publicación exacta permite sólo las nuevas
versiones y fixtures descritos abajo. No cambia el orden B completo, C real,
admisión final y adaptación D real. No autoriza lector, Arrow, benchmark,
binding, raíz de dataset o simulación económica real antes de sus gates.

## Versiones cerradas que se conservan

No editar ni relanzar sus suites como parte de esta preparación:

- weekly_zone_revisit_mechanics.py,38317B,
  6c8677453d08699825c4c5cc2439af6eb0f48e7433dab6dea7d812c8c07c34a7;
- weekly_zone_revisit_accounting.py,18783B,
  9bcc4f834745806289550d2119f7d35ad0281c2fe151ac36c87be24aa72594fb;
- audit_weekly_zone_revisit_mechanics.py,68119B,
  c6c77b1e12b166796c06335621b606b03006617e3dc0a374a2bc2d489ec554d7;
- sus tests, harnesses, cierres y fallos; integración ee549203 y su cierre
  D_REVISIT_INTEGRATION_FINAL_REVIEW_20261102.md.

La versión original queda como referencia de equivalencia para inputs
artificiales nuevos y pequeños. Invocar sus APIs en esas comparaciones no
repite sus suites cerradas ni admite valores reales.

## Cambio permitido

Nuevos archivos separados: weekly_zone_revisit_mechanics_v2.py,
weekly_zone_revisit_accounting_v2.py, audit_weekly_zone_revisit_mechanics_v2.py
y sus tests nuevos de equivalencia/escala. Un productor con helper y un auditor
independiente mantienen las mismas APIs públicas y tipos exactos, el esquema
de registros, órdenes y errores de dominio. La clase de error de cada módulo
nuevo puede ser propia; un input rechazado por V1 no puede pasar a aceptarse,
ni escapar como TypeError/KeyError incidental. No se exigen textos idénticos
de errores, salvo que formen parte de registros públicos.

Los cambios deben limitarse a acceso e índices, evitando una reescritura del
FSM o de la contabilidad. Se permiten índices inmutables por ticker/time y
decisión/time, búsqueda de rangos y ventanas por plan reutilizadas entre sus
anchors, validación ordenada sin listas/sets redundantes y agrupación por plan
para cobertura. Se valida toda la entrada original antes de usar ventanas;
no se oculta una fila malformada porque quede fuera de la ventana económica.
Las filas posteriores aH2 conservan exactamente la validación y la irrelevancia
semántica ya contratadas. Cualquier filtrado de acceso es interno y conserva
ausencias, falsos valid_rth, clocks, terminales y provenance originales.

No hay nueva API de lectura ni import-time work. Los módulos siguen siendo
stdlib/in-memory, sin NumPy/PyArrow, archivos, red, procesos ni datos reales.
El autor del auditor sólo lee sus propias versiones, tests y contratos públicos;
no lee/importa productor, helper contable ni sus tests. Sus índices se diseñan
independientemente y no comparte funciones de reconstrucción científica.

## Orden científico y económico que no se puede particionar

El escaneo local puede organizarse por plan/anchor. Después se reúnen todos
los eventos antes de elegir el primer candidato por ticker/día físico, con
los mismos desempates y sin rescatar otro candidato si falla el primero.

La cartera usa un único merge cronológico global y cuatro libros continuos
A/B por BASE/ADVERSE desde 2026-01-02 hasta2026-09-17, capital100000,
sin reset por plan, ticker, mes, bloque o julio. Los exits preceden a entries
sólo cuando empatan en timestamp; siguen intactos el orden SPY/QQQ/SPXW,
los otros desempates, capital/fees pendientes y lockout común B hastaH2.
Una salida temprana A no admite una operación que B todavía no puede tomar.

Se conservan sin modificación todas las reglas de los seis documentos
normativos pineados por el harness de integración01: mecánica original,
addendum operativo, preparación paralela, aclaración terminal causal,
interfaz pública y aclaración de trazas. No cambian ENTRY_FROZEN, confluencia,
bandas, confirmación, gaps, invalidez/rearme, target/stop, selección weekly,
quotes estrictamente posteriores, pre-cancelación, missing bid ni H2.
Se conservan float.hex, IDs, JSON canónico, trazas, clocks y labels, Decimal
precision1000/Inexact, única risk ceil, riesgo500000 cents, slippage0.01/0.02,
fees1.30, misma entrada/cantidad A/B y conteos completos.

## Evidencia necesaria antes de sustituir la referencia

Cada nueva implementación requiere revisión estática del diff respecto a su
V1 exacta y publicación antes de fixtures observados en raíces nuevas. Las
pruebas nuevas comparan registros completos, tipos y floats exactos contra
su referencia V1, con inputs artificiales y sin reutilizar resultados reales.
El productor no usa al auditor como implementación; el auditor reconstruye
independientemente. La integración V2 conjunta será posterior a ambos cierres.

La matriz focal incluye quotes de otras decisiones y suficientes observaciones
ajenas al plan para ejercer
los rangos, ausencias dentro de la ventana, límites D10:30/H2, postH2, inválidos
fuera de la ventana, cross/rearme/gaps, sesiones cortas, candidatos de planes
solapados en el mismo ticker/día, salida A temprana con B aún abierto, capital
compartido entre tickers, empate exit/entry y exits pendientes entre bloques.
Las particiones usadas sólo para acceso no pueden cambiar un byte del resultado.
La validación conserva rechazo de duplicados, desorden y tipos malformados.

No se ejecuta una nueva batería general de experimentos ni se escogen variantes
por PnL. La comparación focal existe por la causa material de escala. C69,
R3136 y las suites originales D permanecen cerradas. Cualquier fallo nuevo
se preserva con su identidad; no retry automático ni adopción de parciales.

La evidencia estática de complejidad no se presentará como una medición de
tiempo/RSS. Una medición sintética de escala necesita un protocolo separado
con tamaños y presupuesto de memoria predeclarados, instrumentación revisada,
publicación y gates contemporáneos; no se lanzan millones de dicts mientras
B06 esté activo por el solo permiso de esta enmienda. La aceptación de V2
requiere equivalencia focal y eliminación verificable de los accesos globales
por evento, sin prometer capacidad real antes de medirla.

Todo hijo formal conserva CPU0, diez variables de hilos1, CUDA=-1, gates
oficiales RAM/free_commit/disco>=2GB, logs, handles retenidos, PID/creation,
exit efectivo, snapshots y rehash de cierre. No se mata ningún proceso ajeno,
no se rebajan umbrales y no se modifica B06 activo ni sus fuentes pineadas.

La comparación económica requerida sigue siendo A revisita/salida por zonas,
B misma entrada/qty/salidaH2 y C original10:35/H2 descriptivo, ocho meses
completos enero-agosto y septiembre parcial separado. Esta preparación no
produce PnL real, no selecciona política ni prueba rentabilidad futura.
Goal activo; selected_policy=null; promotion_approved=false.
