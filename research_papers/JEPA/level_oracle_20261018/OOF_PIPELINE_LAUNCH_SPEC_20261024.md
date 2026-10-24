# Supervisor externo único del pipeline OOF congelado

24 de octubre de 2026. Especificación operativa outcome-free. Archivos nuevos:
`launch_oof_pipeline_20261024.py` y `test_launch_oof_pipeline_20261024.py`.
El wrapper OOF, sus productores, auditor, contratos y políticas permanecen
congelados. No se crea request final ni se permite OOF antes del cierre mensual
compuesto y exit real. Root publicará esta spec revisada antes de fixtures nuevas.

Se consultó el inventario: existen wrapper, spec, diseño y review OOF, pero no
un supervisor OOF con handle retenido ni un preparador de request anterior.
El nuevo [borrador documental](OOF_PIPELINE_RUNTIME_REQUEST_DRAFT_20261024_01.json)
es no autorizante: 17 pins actuales, doce fases y hashes futuros null. No se
importaron módulos OOF, Request, MonthlyInputs ni se ejecutó un preflight al
prepararlo. No se abrieron métricas del auditor mensual en curso.

## Autoridades externas y publicación

La CLI recibirá `--request`, `--request-sha256`, `--runtime-binding`,
`--runtime-binding-sha256`, `--implementation-review-sha256` y
`--publication-commit` completo de 40 hexadecimales. Por defecto sólo valida
metadata y muestra recibo, sin crear outputs, logs ni lockfiles. Un flag separado
`--execute-reviewed-pipeline` permite un único Popen. No hay opción resume.

Request científica exactamente compatible con el wrapper: versión
OOF_PIPELINE_RUNTIME_REQUEST_V1, status REVIEWED_OOF_PIPELINE_RUNTIME_REQUEST,
runtime_authorized=true, meses enero–junio 2026, lock global fijo, raíces fuente,
dos auditorías con SHA externo y ocho raíces nuevas de output. La igualdad de
los 17 miembros de `code` se obtiene de la review OOF publicada y se contrasta
con las dependencias declaradas en el código congelado, sin importarlo. Los
cuatro pins literales de adapter/calibrador/replay/auditor permanecen obligatorios.

La review OOF existente es
`OOF_PIPELINE_RUNTIME_IMPLEMENTATION_REVIEW_20261023.json`, SHA
`c35541a487c87512cb678cc511006a8729fbf233a00b639e4dcc60a3fdee68d6`.
El wrapper tiene SHA
`26967e10c6b81cd5b84d7939bf6d0c81037934165daa91847d7ffd25de16ff57`.
La nueva review será `OOF_PIPELINE_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json`,
status PASS_OOF_PIPELINE_LAUNCH_IMPLEMENTATION_REVIEW, decision CLEAR,
scope IMPLEMENTATION_ONLY, runtime_authorized=false y mapa exacto de archivos.
Ese mapa incluye código/tests/spec nuevos, 17 dependencias y cierre de imports
locales de helpers usados. Los 17 pins de la request y el cierre de imports del
supervisor son conjuntos distintos y no se confunden.

Binding operativo externo, status PASS_OOF_PIPELINE_LAUNCH_RUNTIME_BINDING,
con request `{path,sha256}`, review nueva `{path,sha256}`, `logs_root` nuevo,
`published_files` y autoridades mensuales de proceso/supervisión. Su SHA llega
externamente; nunca se deduce para autoaprobar el archivo. `published_files`
incluye código/imports, reviews consumidas, request y autoridades de código
consumidas. El propio binding se añade externamente al chequeo Git para evitar
circularidad. Root verifica publicación remota; el programa compara cada objeto
Git con sus bytes locales. Rehash antes y después de imports tardíos.

## Admisión de metadata, sin duplicar reconstrucción científica

El supervisor no instancia Request ni MonthlyInputs, y no llama pipeline,
completed_prefix, correction_closure, calibración, replay o auditor. Lee JSON
de autoridades y hashes; las fuentes económicas quedan a cargo del único hijo.
La admisión exige:

- Audit mensual compuesto con status
  PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES, scope
  VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1, 18 meses exactos, 36 ventanas,
  seis meses nuevos, doce fits nuevos, trece modelos usados y 369/363/6.
  Conserva selección null, herencia2025, contrato, índice y fuente; quince
  snapshots de código/autoridades y launch ligados por hashes. Ningún failure
  coexistente. No se abren métricas o reportes económicos.
- Supervisor mensual completado, exit_code=0 por handle retenido, mismo PID,
  creation_time y comando entre process/exit/preflight. Su completion liga
  exactamente preflight, process, exit, launch y audit; rehash de esos cinco
  recibos. process y exit fijan código, runtime, review y commit. Los pins del
  runtime y reviews mensuales ya publicados deben concordar con esos recibos.
  No se infiere exit por ausencia del PID.
- Auditoría SessionClock fijada por SHA y status/binding compatibles con la
  request mensual; contrato e índice iguales. La preflight OOF valida estas
  autoridades compactas, sin recorrer o rehashear todos los payloads heredados.
- Ocho outputs nuevos: pipeline, corrección compartida y seis replay roots.
  Logs de supervisor también nuevos. Todos disjuntos entre sí, de código,
  fuentes, autoridades y locks. Se rechazan symlinks/escapes y alias normalizados.
  Las autoridades y recibos deben quedar dentro de raíces permitidas explícitas.

Los hashes de audit compuesto, process/exit/completion mensuales y request
final siguen pendientes hasta observación real y revisión. No se fijan en esta
spec. Un fallo de cualquier condición conserva evidencia y no lanza un hijo.

## Exclusión y proceso

El padre usa sólo un lock operativo distinto, fijo:
`BASE/oof_pipeline_launch.lock`. **No mantiene** `oof_pipeline_runtime.lock`
durante el hijo: el pipeline debe adquirir su propio lock global. Esta separación
evita deadlock y conserva exclusión interna para cualquier request/root.
No se modifica ningún lock científico. El directorio nuevo de logs, creado
atómicamente, constituye claim durable y nunca se borra o reutiliza.

Tras repetir admisión, pins y publicación, el padre abre stdout/stderr, mide
Windows RAM disponible y commit libre, exige ambos >=2.000.000.000 bytes y
llama inmediatamente a Popen sin escribir, esperar o realizar trabajo pesado
entre gate y lanzamiento. Comando fijo: Python actual, `-u`, wrapper OOF
congelado, `--request` y `--request-sha256`. Sin args extra, resume, shell o
retry automático. Hijo oculto, stdin cerrado y OMP/BLAS a un hilo.

Se reutilizan sólo RetainedProcess/drain del launcher mensual publicado,
con sus bytes/imports fijados y revisados. No se invoca su CLI o monitor fijado
al wrapper mensual. La inicialización del handle y toda escritura posterior a
Popen quedan dentro de try/finally; cualquier fallo drena al hijo conservando
evidencia, sin abandonarlo ni inventar exit. GetProcessTimes observa identidad
y GetExitCodeProcess observa salida desde el Popen original retenido.

process.json fija comando, PID/creation, código supervisor, request, binding,
review, commit y SHA del preflight capturado **antes** de Popen. exit.json fija
además SHA de process.json y observed_utc. El pin original del preflight se
conserva hasta completion; no se recalcula para adoptar una mutación. Se
registran sample_count, RSS/private muestreados, mínimos de recursos y errores.
Sin muestras los máximos son null. `monitor_seconds` mide sólo el monitor,
posterior a Popen; no se presenta como duración completa del proceso ni pico exacto.

## Cierre operativo del pipeline

Un exit cero solo no basta. Sin llamar helpers de reconstrucción científica,
se valida metadata y hashes del cierre:

1. Copia request.json exacta y contract.json exacto, versión OOF_PIPELINE_V1,
   request SHA, code17 y correction_layout=SHARED_CUMULATIVE.
2. Exactamente doce starts y doce receipts, índices00..11 y fases
   enero correction/replay, febrero correction/replay, …, junio correction/replay.
   SHA anterior comienza null; cada receipt fija request, fase, start y cierre.
   No fallos, parciales, huérfanos o archivos de control adicionales.
3. Seis cierres de corrección y seis completion de replay con hashes iguales
   a recibos. Status/mes/dependencies, target_labels_read=false y no refit/ganador
   en corrección; replay liga por contrato el SHA de su corrección y audit mensual.
   Las dependencias son los subconjuntos congelados de seis y ocho miembros.
4. Inventarios de outputs acumulativos sin pérdida o cambio de miembros
   anteriores, paths resueltos sólo bajo corrección/replays, sin aliases o escapes.
   El árbol final coincide exactamente con el último inventario salvo locks de
   raíz. Se rehashean esos outputs mediante streaming sin parsear scores,
   labels o reportes; no se repite el rehash masivo de fuentes del pipeline.
5. completion.json exacta: status PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT,
   request SHA, último receipt SHA, seis pares de hashes de cierres,
   winner_selected=null, technical_ready=false, promotion_approved=false,
   auditor_executed=false. Nunca se eleva este cierre a PASS económico.

Después se rehashean autoridades y recibos de proceso/cierre, y el supervisor
publica su completion con esos SHA, exit real y bindings externos. Un fallo
después del exit conserva exit.json y emite failure, sin completion supervisora.
La request del auditor económico OOF se prepara, revisa y publica posteriormente
como acción separada; este supervisor no la genera ni ejecuta.

## Fixtures y secuencia de revisión

Fixtures pequeñas usan JSON artificiales y payloads de texto, nunca MonthlyInputs
o productores reales. Cubren admisión positiva completa, pins externos y publicación,
17deps vs cierre de imports, upstream exit no cero/mutaciones/cronología,
roots/aliases, ocho destinos nuevos, locks sin deadlock, gate inmediato, claim
no reutilizable, drain ante fallo de init/publicación, cierre12fases y negativos
de cadena/inventario/control/closure. Un hijo Python vacío permite verificar
handle y exit real, incluidos fallo tardío y preservación. No hay prueba integral
de datos de mercado ni del pipeline científico; no consume matrices compartidas.

Se capturan código/tests/spec, comandos y recursos antes de pytest en raíz local
nueva, se conservan todos los intentos y se rehashea al final. Scientific pipeline
y sus 17 dependencias permanecen idénticos. Revisión independiente por oof_reviewer,
publicación antes de uso real y autorización final de root después del audit
compuesto. Esta implementación no abre otra familia ni elige política por resultados.
