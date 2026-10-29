# OOF V2R1: continuación operativa tras la parada del usuario

Estado: **PROPUESTA DOCUMENTAL, PENDIENTE DE EVIDENCIA COMPLETA Y REVISIÓN**.
Fecha: 2026-10-29. Este documento no es un recibo de admisión, ejecución,
cierre o auditoría. La reanudación solicitada por el usuario permite preparar,
revisar y publicar la adaptación operativa sin pedir otra autorización. Su uso
real exige los artefactos y comprobaciones concretos descritos aquí.

## Decisión y alcance

Conservar exactamente `run_oof_calibrated_pipeline_v2r1.py` y su request
científico original. Un supervisor nuevo invocará su opción existente `--resume`
una vez, después de admitir expresamente el prefijo de ocho fases cerrado entre
enero y abril. Sólo podrán ejecutarse las fases 08–11: correction/replay de mayo
y correction/replay de junio, en ese orden. El auditor será un proceso posterior
con otro request/binding revisado y publicado, tras los doce cierres y el exit0
real de esta continuación.

No cambiar modelos, scores base, calendario, tres modos, offset, threshold0,
costes, métodos de calibración o selección. No refit, nuevas familias, APIs,
descargas, bróker, VPS o producción. `SEEN_DEVELOPMENT`, selección nula,
`technical_ready=false` y `promotion_approved=false` siguen vigentes.
La lectura histórica necesaria para la calibración de mayo/junio conserva la
semántica congelada; no equivale a repetir las fases cerradas de enero–abril.

## Evidencia inspeccionada y límite de esta propuesta

Se leyeron los tres módulos operativos, los productores y auditor científicos,
el request/binding originales, metadatos del prefijo y los recibos de parada,
sin importar módulos, ejecutar fases ni interpretar métricas económicas.
Los siguientes SHA256 se verificaron sobre los archivos presentes:

| Miembro | SHA256 |
| --- | --- |
| `run_oof_calibrated_pipeline_v2r1.py` | `87512b315d69c75c948c68a671939a9423f53abaa6cf2649d5faee7acd22b15a` |
| `launch_oof_pipeline_v2r1_20261024.py` | `e53084c70f99e4410814066a757e8f455dbb91bece8838fcd73417ce4614dce2` |
| `launch_oof_economic_audit_v2r1_20261024.py` | `93ad3efcc124099ea2a8e4f8c64995671e1922e5ce1974c9f07b3fa02cd3ce1a` |
| Request científico `OOF_PIPELINE_V2R1_RUNTIME_REQUEST_20261024_01.json` | `37f2018c7145d3b82cba2e34fbff9ae3008e33f32b004c5580e433157f38ef15` |
| Binding original `OOF_PIPELINE_V2R1_LAUNCH_RUNTIME_BINDING_20261024_01.json` | `9e4949227dfd8b0aa3e72a35271b081413dbd9dee482b79c98911ea25478813c` |
| `oof_pipeline_runtime_20261024_v2r1_01/receipts/07.json` | `e5dfb3505d3e8e621d91e6ef46dcffd89380a3aa62f13cbc1a37b3816747110e` |
| Observer original `user_stop.json` | `fa8690ceee3f55f06107cf8802db8abab27171707246d6a57bed3d2f1c5b287a` |
| Observer original `post_stop_verification.json` | `021be4945dbee80dac1caf08f073e097c33595353c22e7e83fb4dad433644032` |

En lo sucesivo B significa `D:/GexResearchArtifacts/level_oracle_20261018`.
El árbol de control actual contiene request, contract, starts00–07 y receipts00–07:
18 archivos, sin completion ni failures. El receipt07 declara 8.726 outputs y
262.686.724 bytes acumulados; esos números son metadatos, no una verificación
del contenido de todos los outputs por este documento.
El proceso original PID28256 conserva exit15 observado por handle retenido y
un `failure.json` en **su carpeta de logs**, con el error de exit distinto de cero.
Estos hechos no se convertirán en exit0 ni en cierre completo.

El wrapper ya incluye `completed_prefix()`, `correction_closure()`,
`replay_closure()`, `inventory()` y `pipeline(..., resume=True)`. Valida la cadena,
las fuentes consumidas y todos los outputs del prefijo antes de recorrer
`phases()[count:]`. No admite stages parciales u outputs huérfanos. El launcher
original no sirve para continuar: `output_roots()` exige nueve destinos ausentes
y `command()` no añade `--resume`.

## Rutas y preservación

Las rutas científicas del request original permanecen exactas. El pipeline y
correction compartida reciben únicamente adiciones futuras; enero–abril y los
archivos ya existentes permanecen byte por byte. Los replay roots de mayo y junio,
ya declarados por el request, deben seguir ausentes antes del lanzamiento.
No copiar el árbol a otra ruta para ejecutarlo: sus recibos e inventarios contienen
rutas absolutas cuya reescritura invalidaría la evidencia.

Crear únicamente destinos operativos nuevos y disjuntos:

- `B/oof_user_stop_continuation_evidence_20261029_01`: snapshot inmutable previo,
  inventarios y recibos de verificación; debe existir y estar sellado antes del uso.
- `B/oof_pipeline_user_stop_continuation_launch_20261029_01`: logs/recibos nuevos;
  debe estar ausente hasta el único lanzamiento.
- `B/oof_pipeline_user_stop_continuation_observer_20261029_01`: observaciones nuevas,
  con publicaciones exclusivas; no escribir dentro del observer del 24 de octubre.
- Futuro auditor: `B/oof_economic_audit_user_stop_continuation_20261029_01` y
  `B/oof_economic_audit_user_stop_continuation_launch_20261029_01`, ambos ausentes.

El snapshot copiará request/binding, los 18 controles del prefijo, ocho cierres,
cuatro replay run_contract, cuatro correction inputs/run_contract y el
implementation compartido, todos los archivos de logs originales y los recibos
del observer original. Guardará el inventario final original completo, tamaños,
mapa de controles y parejas original/copia/SHA256. Una copia compacta equivalente
se archivará en `continuation_20261029/oof_user_stop_continuation_snapshot/` del
repositorio antes del binding real. Todos los originales/copias se rehashearán.
Los 8.726 payloads permanecen locales por referencia, con verificación streaming
de sus hashes; no se les atribuirá una copia inexistente.

Los bytes de los cinco `.lock` de raíz existentes (correction y replay de
enero, febrero, marzo y abril) también se copian, preservan y pinnean
separadamente del inventario científico, que los excluye por diseño. Comprobar
su membresía exacta y sus hashes antes y después de la continuación. No borrar
locks para simular disponibilidad; usar la adquisición real del lock del SO.
No añadir metadatos nuevos dentro del árbol de control original.

## Admisión concreta del prefijo y de las fuentes

La nueva autoridad operativa fijará exactamente el request/binding científico
original, primer preflight/process/exit/failure, parada y verificación posterior,
manifest del snapshot, fuente de autorización del 29 de octubre, ocho fases
adoptadas, tail SHA, source admission SHA y los cuatro stages pendientes.
No reutilizar el indicador `runtime_authorized=true` antiguo como autorización
operativa suficiente para esta continuación.

El preflight nuevo será de metadatos y hashes; no invocará productores ni abrirá
parquets económicos para analizarlos. Debe comprobar:

1. Pins y membresía exacta de las 18 dependencias científicas originales,
   revisiones originales, nueva implementación/revisión y contrato publicado.
   Las seis dependencias del adapter y ocho del evaluator mantienen sus mapas.
2. La autoridad mensual compuesta, session audit, índice y su cadena de proceso
   conservan sus pins y 18 meses. Reusar `upstream()` del launcher original para
   su admisión mensual, con el binding original como argumento.
3. Recalcular la unión exacta metadata mensual + índice con
   `request_admission()`. Exigir igualdad con
   `ec2f728baf2ab28adaaf3855847d74bf6354ac587d440afb83b50278e5ca3234`, registrado
   por el primer preflight y contract. Mantener R1: en `MISSING_SOURCE`, ambos
   SHA nulos y `continue`, sin abrir sus day_root nominales. Los 2.226 sidecars,
   126 index-only junio y seis ausencias son reconciliación de la autoridad, no
   nuevos criterios científicos. No ampliar raíces a B o a D:/ThetaData.
4. Cadena exacta original de ocho starts/receipts, request SHA, phase, previous SHA,
   start SHA, flags y closure SHA; count debe ser exactamente8, tail el pin
   anterior y meses completos exactamente enero–abril. Reconciliar adiciones y
   byte accounting por fase. El árbol de control debe ser exactamente esos18
   miembros, sin failures, partial, completion, start08 o cualquier huérfano.
5. Correction/replay closures tienen sus estados, meses, dependencias, contratos,
   flags, inputs SHA y enlaces a correction exactos. Validar los mapas de fuentes
   en correction inputs y replay completion: paths/SHA/admisión, conflictos y
   aliases. Los payloads se verifican como bytes; no se interpretan calibration,
   selection, summary, intentos o ledgers para aceptar o descartar meses.
6. El mapa acumulado de receipt07 debe igualar exactamente el árbol de outputs
   presente excluyendo sólo locks de raíz previstos; rehashear todos sus miembros.
   En los mapas de fuentes consumidas, admitir sólo raíces originales o el mapa
   transitivo exact-path→SHA; rechazar alias, symlink/junction/reparse/hardlink y
   cualquier fuente no admitida. No aceptar hashes recién calculados como autoridad
   sustitutiva de un pin original distinto.
7. Los dos roots de replay pendientes y los logs nuevos están ausentes. Todo
   destino es absoluto, acotado y disjunto de fuentes/evidencia protegida.
   Las únicas raíces existentes con escritura permitida son pipeline y correction,
   para adiciones ya previstas por el wrapper.
8. Preservar el primer exit15/failure y correlacionar la parada con PID/comando.
   Process↔exit retenidos deben coincidir exactamente. La creation del observer
   usa otra representación: fijar tolerancia absoluta máxima `1e-6` segundos
   frente al handle; no exigir igualdad textual ni admitir una tolerancia abierta.
   Cada start00–07 debe caer entre la creación original obtenida del handle y
   su exit retenido, en orden de fases. El timestamp del recibo del observer no
   sustituye el tiempo de creación del proceso original.
   Nueva observación debe confirmar ausencia de procesos competidores; ausencia
   de PID por sí sola no acredita ningún cierre.

El child congelado vuelve a ejecutar `Request.recheck()` y `completed_prefix()`
antes de cualquier fase nueva, incluida la validación semántica de los cierres
que ya implementa. Esa comprobación no reemplaza la adopción externa y publicada
de este prefijo exacto. Una diferencia en cualquier etapa aborta y conserva todo;
no reparar el original ni adoptar otro prefijo automáticamente.

## Implementación mínima nueva

Crear `launch_oof_pipeline_user_stop_continuation_20261029.py` y
`test_launch_oof_pipeline_user_stop_continuation_20261029.py`. No crear otra versión
del wrapper ni cambiar archivos anteriores. Funciones nuevas previstas:

- `implementation_files()` y `validate_authority()`: mapas exactos de los nuevos
  miembros más dependencias originales y revisiones; no aceptar conjuntos abiertos.
- `destinations()` y `validate_stopped_launch()`: separar destinos existentes de
  los ausentes, validar snapshot/cadena de parada y toda la evidencia antigua.
- `validate_adopted_prefix()`: aplicar las ocho reglas anteriores y devolver
  baseline de controles, inputs, outputs y tail, sin producer calls.
- `command()`: executable fijado, `-u`, wrapper original, `--request` original,
  `--request-sha256` original y finalmente **`--resume`**; no otros flags.
- `preflight()`: DEFAULT sólo admisión, con `executed=false`; enlazar el nuevo
  request operativo, binding, review SHA, commit publicado y baseline completo.
- `monitor()`: handle Popen retenido, PID/creation reales, command exacto y
  autoridad del **nuevo** monitor; stdout/stderr exclusivos y exit observado.
- `launch()`: locks, rechecks, un Popen, monitor, validación final y preservación.

Reutilización permitida por llamadas explícitas a módulos originales pineados:
`dependency_sets()`, `implementation_files()`, `publication()`, `upstream()`,
`request_admission()`, `protect_transitive_outputs()`, `output_mapping()`,
`tree_files()` y, al cierre, `validate_pipeline()` del launcher original.
`ops.Evidence`, gate/observation y `helper.RetainedProcess`/publicación/drain/lock
también pueden reutilizarse con sus pins. Verificar pins antes y después de importar.
No monkeypatch, reasignación de globals, shim de roots o invocación de CLIs antiguas.
No llamar al antiguo `preflight()`, `output_roots()`, `launch()` o `monitor()`:
sus precondiciones o `__file__` atribuyen la ejecución al supervisor original.

Usar el mismo `oof_pipeline_launch.lock` para el supervisor y
`oof_pipeline_runtime.lock` para el wrapper. El supervisor puede comprobar
disponibilidad del runtime lock bajo su lock operativo y liberarlo antes del
Popen; no retener el lock que debe adquirir el child. Preservar el gate2GB RAM y
commit inmediatamente antes del child y los gates por fase del wrapper.
Windows sin optimización, threads1 y CREATE_NO_WINDOW permanecen. La restricción
del usuario a CPU0 se impone antes de cualquier trabajo científico del child:
establecer y comprobar la afinidad `[0]` del proceso supervisor antes de Popen,
conservarla durante la creación y verificar documentalmente y mediante un child
artificial que Windows transmite esa afinidad desde el padre. El recibo de
admisión registra afinidad del padre, mecanismo de herencia y pins de esa prueba.
El monitor verifica y registra también la afinidad `[0]` del child como control
adicional; asignarla después de Popen no satisface la condición previa. Si CPU0
no está disponible o falla la imposición/verificación previa, no crear el child.

Dentro del lock operativo, revalidar publicación, fuentes, stop/snapshot y prefijo
antes del Popen; consumir exactamente la orden predeclarada. Crear los logs nuevos
con `mkdir(exist_ok=False)` bajo ese mismo lock como marca durable de uso único,
antes de Popen. Conservar esa carpeta ante cualquier fallo, incluso si no llegó
a crearse el child; DEFAULT o un segundo intento no pueden tratarla como fresca.
Una vez creado el
child, cualquier excepción lo drena y publica failure sólo en logs nuevos.
No retry automático. Cada start08–11 debe caer entre la nueva creación obtenida
del handle y el nuevo exit retenido, en orden de fases; el cierre previo permanece
asociado al primer proceso. No usar el momento de emisión del observer o del
recibo de monitor como sustituto de la creación retenida.

Tras exit0 retenido, llamar al `validate_pipeline()` original: requiere los12
cierres,27 controles exactos y todos los hashes finales. Rehashear además todo el
baseline de enero–abril, todos los logs/stop originales y las copias del snapshot;
el mapa baseline debe ser subconjunto exacto del inventario final, sin diferencias.
El completion nuevo vincula las dos cadenas, la adopción y los cuatro nuevos
receipts, con `auditor_executed=false` y los flags científicos conservados.

## Compatibilidad de la auditoría posterior

El auditor científico `audit_oof_calibrated_policy.py` acepta su request V1 FULL_H1
con seis parejas closure SHA y las rutas originales; no necesita cambios.
Su supervisor V2R1 sí exige una sola cadena exit0 y el command sin `--resume`.
No simular esa cadena ni sustituir el failure original.

Crear `launch_oof_economic_audit_user_stop_continuation_20261029.py` y su test
homónimo. Adaptar exclusivamente `review_files()`/mapas de autoridad,
`upstream()`, schemas/status/bindings y destinos al contrato de continuación.
Mantener validaciones científicas, doce fases,27 controles, request FULL_H1,
source-admission SHA, process handles, gates y locks del supervisor anterior.
La nueva admisión debe exigir ambas cadenas: el primer lanzamiento cerrado con
exit15/failure exactos y parada del usuario, más continuación revisada con exit0,
prefijo adoptado y wrapper original `--resume`. La excepción por fallo se limita
al archivo original path+SHA+contexto; cualquier failure nuevo o desconocido
impide auditar. No convertirla en permiso genérico para ignorar fallos.

Los nuevos request/binding económicos concretos se producen sólo después de
completion real; contienen los12 SHA, proceso/exit0, snapshot, review y publicación.
La implementación puede probarse antes con fixtures artificiales. No ejecutar
auditoría parcial ni automática durante la continuación. El reporte futuro sólo
puede consumir un audit FULL_H1 cerrado y pineado.

## Pruebas y secuencia de publicación

La suite nueva utilizará árboles artificiales. Debe cubrir al menos:

1. Prefijo válido de ocho fases y command exacto; DEFAULT no crea outputs ni child.
2. Count7/9, hueco, receipt/start mutado, tail/request equivocado, flags inválidos,
   completion prematuro, partial, orphan o start08: rechazo antes de Popen.
3. Output o input alterado/omitido/extra, snapshot/copia distinto, mapa transitivo
   cambiado, conflictos de SHA, rutas enlazadas/alias/hardlink y missing no nulo.
4. Fecha/PID/comando de parada incompatible; tolerancia del observer dentro/fuera
   del límite; primer exit0 fingido o failure extranjero: rechazo.
5. Roots de mayo/junio o logs existentes, salida solapada y permisos de escritura
   fuera de las dos raíces existentes y las nuevas declaradas: rechazo.
6. Lock ocupado, gate insuficiente, review incompleto, commit/pins diferentes,
   mutación entre preflight y Popen: ningún lanzamiento. Un child artificial
   debe observar CPU0 desde su primera instrucción y threads1 en el entorno;
   afinidad previa fallida o CPU0 no disponible impiden Popen. Cambiar cualquiera
   de los cinco locks preservados antes/después provoca rechazo.
7. Harness integral con productores artificiales: `--resume` invoca sólo las
   cuatro fases pendientes, cada una una vez, conserva todo el baseline y produce
   una cadena final12; no llamar productores reales o fit/inferencia económica.
8. Child exit no cero, handle no conservado, receipt de otro PID/creation, fallo
   durante publicación/monitor y drift posterior: sin completion válido ni retry.
9. Final12 válido aceptado por el validador original; pérdida/mutación de cualquier
   output/control previo y cualquier failure nuevo: rechazo.
10. Auditor operativo sintético acepta sólo las dos cadenas explícitas y FULL_H1;
    rechaza ausencia de adopción, command sin resume, falsificación de exit0,
    cierre11/12, source map distinto y permisos genéricos para ignorar failure.

Orden de trabajo: evidencia/snapshot y revisión documental independiente;
publicación del contrato; implementación nueva y fixtures; revisión independiente
de código/tests; publicación de implementación, pruebas y reviews; request
`OOF_USER_STOP_CONTINUATION_REQUEST_20261029_01.json` y binding
`OOF_USER_STOP_CONTINUATION_RUNTIME_BINDING_20261029_01.json` concretos, revisados
y publicados; DEFAULT de admisión; inspección del resultado; único lanzamiento
con `--execute-reviewed-continuation`; cierre y verificación del baseline;
request/binding económico nuevo revisado/publicado; única auditoría separada.

Review de implementación propuesto:
`OOF_USER_STOP_CONTINUATION_IMPLEMENTATION_REVIEW_20261029.json`.
El runtime request fija `expected_completed_phases=8`, los ocho phase refs y
`remaining_phases=[[202605,correction],[202605,replay],[202606,correction],
[202606,replay]]` como strings JSON reales, además de todas las referencias
anteriores. Los resultados de pruebas se informarán por intento/versiones; no
sumar ejecuciones diferentes como una suite única. Una discrepancia preserva el
estado para revisión y no habilita una reparación o una continuación distinta.
