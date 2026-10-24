# Ejecución única supervisada del auditor OOF FULL_H1

24 de octubre de 2026. Propuesta operativa, `DESIGN_ONLY`, no autoridad runtime.
El pipeline OOF está ejecutándose bajo su supervisor publicado. Sus cierres,
salida por handle y doce hashes mensuales siguen pendientes en este documento.
No se ejecutó admisión, MonthlyInputs, auditoría ni benchmark al prepararlo.

## Alcance y CLI congelados

Se propone un nuevo `launch_oof_economic_audit_20261024.py`, sus fixtures pequeñas
y una review independiente. No cambia el auditor ni ningún productor/policy.
El único hijo científico sería Python actual, `-u`,
`audit_oof_calibrated_policy.py --request <JSON> --request-sha256 <SHA externo>
--output <root nuevo>`. El supervisor no ofrece MONTHS, resume ni retry:
exige `FULL_H1`, enero–junio 2026 ordenados y los tres modos/seis políticas fijos.

Auditor rehasheado:
`e7481fbe944a9ffadcf637e7a4b69cd8d636cdf50ae295426191db9d76b5d44b`.
Review independiente congelada `OOF_ECONOMIC_AUDITOR_IMPLEMENTATION_REVIEW_20261023.json`:
`cf7a0659b495ad9bab484839d71c1f4377fb25c5c9df60d772cf0b7667c4d653`.
Los 13 archivos de sus tres mapas binding se fijarán íntegros, además de la
review misma. Los 17 pins del pipeline cerrado son otra autoridad, no sustituyen
esa revisión. Adaptador/replay consumen respectivamente seis/ocho dependencias.
La review científica exige su status/scope e implementación íntegra; no tiene
campo decision y su runtime_authorized=false describe sólo revisión de software.

El auditor reconstruye máximos de todas las ofertas, residuos, offsets,
controles bitexact y trayectorias propias de las seis políticas a partir de
scores y labels sellados. Revisa costes desde ask/bid ya sellados. No importa
productores, refittea, infiere con modelos ni reproduce quotes raw. Su PASS
significa reproducción económica condicionada a scores auditados, no rentabilidad
ni promoción. 2025 es TRAIN del calibrador; 2026 es desarrollo visto.

## Admisión externa antes de crear el hijo

La request científica conservará exactamente el esquema del auditor: version
`OOF_ECONOMIC_AUDIT_REQUEST_V1`, scope FULL_H1, raíces mensual/SessionClock,
auditorías base, correction_root y seis objetos month/correction_completion_sha256/
evaluation_root/evaluation_completion_sha256. No se añaden controles económicos.
monthly_audit y session_audit son strings de rutas, con monthly_audit_sha256
separado; no son los objetos path/sha256 de la request del pipeline.
La propuesta adjunta mantiene esos doce SHA a null; no es una request ejecutable.

Un binding operativo distinto fijará request SHA externo, review del auditor,
review del nuevo supervisor, commit publicado, código/imports y raíces permitidas.
Recibirá la identidad completa de request/binding/reviews del pipeline ya publicado
y los SHA reales de preflight/process/exit/completion del supervisor OOF,
completion del pipeline, último receipt y doce cierres mensuales. Hasta observarlos
no se emite binding PASS. No se inventan hashes ni se deduce una autorización del
contenido de un archivo arbitrario.

Se comprueba sólo metadata de estas autoridades: status exactos, identidad
PID entero positivo/creation finita positiva no bool, exit_code de tipo int igual
a cero, comando publicado exacto, SHA encadenados, tiempos UTC conscientes y orden
process <= exit <= completion supervisora. El pipeline debe declarar
`PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT`; su supervisor,
`COMPLETE_OOF_PIPELINE_SUPERVISION_PENDING_INDEPENDENT_AUDIT`. Se exige
auditor_executed=false, winner null y technical_ready/promotion false donde
corresponda, sin failure/partial coexistentes.

Los doce starts/receipts y sus cierres se contrastan con los miembros compactos
de la completion supervisora, request17 y último receipt. La request nueva debe
reproducir los seis pares de SHA y las mismas raíces/monthly audit que esa cadena.
El schema upstream real usa process_files (preflight/process/exit) y
pipeline_closure (compact_files/output_count/output_inventory_sha256), no el
closure_files del supervisor mensual anterior.
No se llama validate_pipeline, Request, MonthlyInputs, audit, Monthly ni helpers
de reconstrucción. No se vuelve a recorrer el inventario de payloads OOF ni
verified_files de fuentes en el padre: el hijo auditor ya hace ese trabajo.

Se comprueba publicación exacta de todos los archivos consumidos de código/reviews,
la request y el binding; el binding se incorpora externamente para evitar autopin.
Root verificará remoto antes del uso. Rehash de autoridades compactas y código
antes/después de imports tardíos y al cierre, conservando los pins originales.

## Proceso, recursos y preservación

Dos destinos propuestos, todavía no creados:
`BASE/oof_economic_audit_full_h1_20261024_01` y
`BASE/oof_economic_audit_launch_20261024_01`, con
BASE=`D:/GexResearchArtifacts/level_oracle_20261018`.
Ambos deben ser nuevos, normalizados, disjuntos entre sí y de todas las fuentes,
autoridades, código y locks; se rechazan links/junctions/ancestros redirigidos.
El auditor crea su propio output; el padre reclama atómicamente logs como claim
durable de una sola ejecución, nunca borrado. Lock operativo propio propuesto
`BASE/oof_economic_audit_launch.lock`, distinto de los locks pipeline/producción.
El cierre real upstream se exige antes de adquirirlo; no se toca el proceso activo.
Después se propone adquirir también `BASE/oof_pipeline_runtime.lock` durante
el hijo y validación final para excluir otro productor: el auditor congelado no
adquiere ese lock, por lo que no existe el deadlock del launcher productor. El
orden fijo será lock propio y luego global; si no están libres se aborta, sin retry.

Se reutilizarán primitivas operativas ya revisadas donde eviten duplicación,
sin invocar CLIs ni preflight anteriores. El helper mensual tiene SHA
`3e77bda56dabd8287b04ae9a47b4dcd45d5967a01a31514e933cbb44b6f4c08d`;
el supervisor OOF de referencia, SHA
`e93ff7db48c86a6d569e70d18f845ec48575ba2cb226bbed981c28a58245e9a8`.
La lectura estática confirma helper mensual -> overlay -> run_monthly_walk_forward.
No se importará ciencia productora sólo para observar RAM/procesos: se aislarán
las pocas primitivas necesarias en el nuevo archivo, manteniendo su procedencia
y fixtures. El mapa exacto de esa clausura y de la nueva
review queda pendiente de bytes estables; no se inventa un total de dependencias.

Justo antes de Popen se medirá Windows RAM disponible y commit libre, ambos
>=2.000.000.000 bytes, sin escritura ni trabajo pesado intermedio. Hijo oculto,
stdin cerrado, stdout/stderr nuevos, OMP/BLAS un hilo, sin argumentos libres.
Se retiene el Popen original y su handle hasta GetExitCodeProcess; identidad por
GetProcessTimes. Todo código posterior a Popen, incluida inicialización del
monitor/publicación, queda protegido con drain en finally, sin dejar huérfanos
por excepciones manejables. No se promete supervivencia ante muerte forzada del OS.

process.json liga comando/PID/creation, código, request, binding, review, commit y
SHA del preflight anterior a Popen. exit.json liga también el SHA de process,
exit real, observed_utc y errores de observación. Métricas: monitor_seconds,
sample_count, máximos RSS/private muestreados y mínimos de recursos observados;
sin muestras los máximos son null. No se presentan como duración total o pico exacto.

Sólo exit cero y audit.json válido permiten completion. Se exige
`PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_FULL_H1`, scope
`OOF_OFFSETS_AND_ECONOMIC_EXECUTION_GIVEN_AUDITED_BASE_SCORES`, seis meses,
request/monthly_audit/correction_root exactos, controles de interpretación
winner null/base_fit_reproduced false/base_inference_reproduced false/
raw_quote_replay false/development_seen true/technical_ready false/promotion false,
y ausencia de audit_failure.json/failure/partials. El padre valida estructura y
bindings, no decide gates de rentabilidad ni recalcula economía. Fija el SHA del
audit completo por streaming y miembros requeridos de verified_files, sin rehash
de sus payloads. El auditor no produce launch.json ni execution_snapshots: los
snapshots/launch operativos serán propios del supervisor, sin atribuirlos al hijo.
Completion supervisora liga audit, preflight, process y exit.
Si falla validación después de exit0, se conserva ese exit y failure, sin completion.

## Coste previsto desde el código, no medido

`audit_month` vuelve a reconstruir historia por modo para cada mes objetivo;
Seal cachea hashes, no DataFrames/NPZ ni máximos. Con H_m igual a ticker-días
disponibles desde enero2025 hasta el mes anterior, hay exactamente
3*sum(H_m) llamadas históricas a selection y 3*363=1.089 selecciones objetivo.
Sólo la repetición de los 750 días de 2025 aporta 3*6*750=13.500 llamadas
históricas; se añaden los prefijos de 2026. No son días únicos ni fits.
Se reconstruyen 6*363=2.178 trayectorias observables y se conservan
6*6=36 filas de cobertura ausente, además de la comprobación previa de controles.

Cada selección lee actions y NPZ; la historia lee labels y JSON de selección/
realized; cada objetivo vuelve a leer actions/labels y controles. Los mapas de
fuentes se autentican, los hashes consumidos se cachean y seal.recheck vuelve a
leer cada archivo único al final. La E/S total incluye por ello lecturas de
payload repetidas y al menos dos lecturas de hash por archivo consumido, no sólo
el tamaño del resultado. RAM contiene registros históricos de un modo, selecciones
del mes y reportes/ledgers acumulados; no monta la matriz de entrenamiento.
No hay estimación fiable de minutos/GiB sin inventarios finales y tamaños. El
gate de 2 GB es admisión, no cota máxima de RSS. Se medirán tiempos/recursos reales
durante la única ejecución, sin un benchmark ni replay previo.

## Secuencia pendiente

Review de este diseño y publicación previa; implementación acotada y fixtures
metadata/texto con hijos Python inocuos; captura de pins/comando/gate antes de
tests, conservación de cada intento y review independiente. Fixtures: admisión
completa, FULL_H1/12cierres, pins/publicación, exit bool/no cero/UTC/identidad,
links/raíces, gate inmediato, oneclaim, errores postPopen con drain, mutación del
preflight original y auditor PASS/failure coexistente. No suite científica nueva.
Sólo tras cierre real OOF se materializan request/binding concretos, se revisan y
publican. Root decide y lanza una vez. Este diseño no autoriza ejecución ni cambia
umbrales, costes, datos, políticas o entrenamiento.
