# Checklist de auditoria mensual H1 2026 V2 y transicion OOF

24 de octubre de 2026. DOCUMENTO NO EJECUTABLE. No contiene runtime PASS nuevo,
request OOF ni autorizacion de lanzamiento. Los hashes futuros quedan pendientes.
No se ejecutaron constructores de auditoria, admit/preflight, fits o replay al
prepararlo. No modifica ningun codigo o autoridad congelados.

## Infraestructura inspeccionada

La extension `audit_monthly_walk_forward_test_index_v2.py` ya tiene CLI/run,
output nuevo con lock, snapshots de 13 dependencias y dos autoridades, rehash
final y publicacion atomica. Su constructor verifica cierres y abre acciones y
scores: NO debe llamarse como supuesto chequeo de solo metadata.

La extension no observa el proceso productor, no verifica su exit/completion
operativos y no implementa gate RAM/commit. Tampoco recibe SHA externo de su
runtime review: comprueba contenido y lo fija durante el run. El supervisor
externo debe aportar esas garantias antes de llamar a la CLI.

`launch_monthly_test_20261023.py` esta fijado al wrapper productor test. Sus
primitivas RetainedProcess, monitor, drain_child y publicacion de recibos son
referencia reutilizable; su comando/preflight no son un launcher de auditoria.
El supervisor historico audit2025_02, en
`D:/GexResearchArtifacts/level_oracle_20261018/monthly_validation_audit_launch_20261024_02/launch_when_validation_complete.py`,
esta fijado a validation, al auditor base y al fallo01. No invocarlo ni editarlo
para H1. Root autorizo una adaptacion nueva con spec, fixtures y revision propia;
se consulta a tcn_completion para implementacion separada de esta revision.

## Autoridades ya disponibles

BASE significa `D:/GexResearchArtifacts/level_oracle_20261018`.
CODE significa el directorio de este documento en el repositorio.

| Autoridad | SHA256 actual |
|---|---|
| BASE/monthly_walk_forward_validation_audit_20261024_02/audit.json | `ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc` |
| BASE/session_clock_dataset_v1_audit/audit.json | `678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9` |
| BASE/session_clock_dataset_v1/index.parquet | `7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4` |
| BASE/monthly_walk_forward_v1/run_contract.json | `7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f` |
| BASE/monthly_walk_forward_v1/validation_freeze.json | `df9a490d310d86a040e0ca9e6ad5b07c64d3474b9c71ce83e445309511fa9237` |
| CODE/MONTHLY_TEST_INDEX_AUDIT_V2_REVIEW_20261024.json | `493806fbc25a50a3333b4d2e65f3bd041bd30b30d5a10203d8c188c0520ee2b3` |
| CODE/MONTHLY_TEST_RESOURCE_RUNTIME_REVIEW_20261024_01.json | `1c6072a871d7d4cbcabc7e82dbbbbdb28d5767ff083571638f956d92250b557b` |
| CODE/MONTHLY_TEST_RESOURCE_RUNTIME_REVIEW_20261024_01_INDEPENDENT.json | `ffe3d876704c77b1bf10e2c9dc091087adec283937337ccb523ac5585b5321d0` |
| CODE/run_oof_calibrated_pipeline.py | `26967e10c6b81cd5b84d7939bf6d0c81037934165daa91847d7ffd25de16ff57` |
| CODE/OOF_PIPELINE_RUNTIME_IMPLEMENTATION_REVIEW_20261023.json | `c35541a487c87512cb678cc511006a8729fbf233a00b639e4dcc60a3fdee68d6` |

El freeze es FAIL_NO_DAILY_COMPLIANT_MODE, selected_mode=null, approved=false.
Debe conservarse incluso si aparecen resultados favorables de algun modo H1.
El audit2025 acredita 12 meses/24 ventanas/750 ticker-dias dados scores sellados;
no se sustituye por una review de implementacion.

## Cierre test que aun debe observarse y fijarse

Las rutas previstas ya estan fijadas por el runtime de test: runtime
BASE/monthly_test_resource_overlay_20261024_01 y logs
BASE/monthly_test_launch_20261024_01. Esta nota NO afirma que esten completos.

1. Obtener `process_binding.json`, `monitor_open.json`, `monitored_exit.json`
   y `process_chain.json` de logs, junto a `launch.json` del runtime. Fijar SHA
   de cada archivo y del monitor publicado. PID, creation_time, command y SHA
   de process_binding deben concordar; exit_code debe ser 0 observado por el
   handle retenido, nunca inferido por desaparicion del PID.
2. Usar la validacion congelada `verify_process_chain(..., validation=False)`
   para identidad/comando/etapa y comprobar ADEMAS exit_code==0: esa funcion
   permite exit no cero en test para otros casos de resume. Exigir estado
   PROCESS_CHAIN_RECORDED y pertenencia exacta de sus miembros. Si hubiera una
   normalizacion, exigir tambien source_launch y su SHA; no fabricarla.
3. Exigir runtime `completion.json`, status
   COMPLETE_MONTHLY_TEST_RESOURCE_OVERLAY. Verificar contrato7250..., audit2025
   ba9f..., runtime_review1c60..., selected_mode=null, scientific_inputs_changed=false,
   cronologia launch < completion <= exit, runtime_members exactos y rehasheados,
   snapshots, preserved_checkpoints intactos y final_checkpoints completos.
   Un process_chain con exit0 no certifica ese cierre por si solo.
4. Exigir cierre cientifico mensual: 36 ventanas totales, 18 meses, report_hashes
   2025/2026, modos fijos, selected_mode=null, development_seen=true y promotion=false.
   Requerir completion.json y su .complete.json; meses enero-junio con daily,
   economics y predictions cerrados; report2026 cerrado. Mantener todos los
   cierres2025 y los 12 nuevos modelos completos con sus inputs y fit_started.
5. Registrar archivos y hashes reales en la NUEVA autoridad de runtime del
   auditor y en el binding del supervisor. Revisor independiente y publicacion
   de bytes exactos antes de cualquier proceso. Ningun SHA futuro se deduce o
   autoadmite simplemente porque haya aparecido un archivo en la ruta esperada.

## Plantilla documental del runtime del auditor V2

La siguiente tabla describe el esquema; no es un JSON consumible. Solo despues
del cierre anterior se podra redactar y revisar una autoridad real.

| Campo requerido por la extension | Valor o fuente |
|---|---|
| status | PASS_MONTHLY_TEST_INDEX_V2_AUDIT_RUNTIME_REVIEW, solo tras revision real |
| scope | VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1 |
| dependencies | Mapa exacto de 13 archivos fijado mas abajo y por la review493806... |
| binding.monthly_root | BASE/monthly_walk_forward_v1, ruta absoluta normalizada |
| binding.source_audit | BASE/session_clock_dataset_v1_audit/audit.json |
| binding.validation_audit | BASE/monthly_walk_forward_validation_audit_20261024_02/audit.json |
| binding.validation_audit_sha256 | ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc |
| binding.implementation_review_sha256 | 493806fbc25a50a3333b4d2e65f3bd041bd30b30d5a10203d8c188c0520ee2b3 |
| binding.run_contract_sha256 | 7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f |
| binding.source_audit_sha256 | 678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9 |
| binding.index_sha256 | 7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4 |
| binding.session_root | BASE/session_clock_dataset_v1 |
| binding.validation_freeze_sha256 | df9a490d310d86a040e0ca9e6ad5b07c64d3474b9c71ce83e445309511fa9237 |
| allowed_read_roots | Directorios existentes concretos que cubran autoridades y todos los inputs heredados/nuevos |

Normalizar strings con Path.resolve en Windows; el gate compara algunos strings
exactamente. Las raices cientificas necesarias incluyen monthly_walk_forward_v1,
session_clock_dataset_v1, session_clock_dataset_v1_audit, engine_v1 y features_v1,
ademas de CODE y salida audit2025. Anadir solo los directorios de recibos que el
supervisor realmente consuma. No usar raiz de volumen ni BASE entero como atajo.

Campos de cierre/exit del productor, supervisor, output/logs y hashes externos
adicionales deben estar vinculados por el supervisor nuevo. Son garantias externas:
no atribuir su validacion a verify_authorities de la extension, que no los consume.

## Dependencias exactas de la extension

| Archivo | SHA256 |
|---|---|
| MONTHLY_TEST_AUDIT_EXTENSION_SPEC_20261023.md | `b895e0ee57ee8d911b4d732e1f46b07c2d9e13c296f09888ce47372815f5182d` |
| MONTHLY_TEST_INDEX_AUDIT_V2_SPEC_20261024.md | `5513996a6284c175dd26496ccee645d23f721d097896123280309cc0be327e29` |
| MONTHLY_WALK_FORWARD_INDEX_AUDIT_V2_SPEC_20261024.md | `06f0fcd6ac5d60a8e503d5f9df86102683e441d7b00d0a5968142384f4a821f4` |
| MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDITOR_REVIEW.json | `db323959e6a894d6d6fb51bde764af0c96db0cb0bba2f1711bbe0807425d10ca` |
| MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDIT_CONTRACT.md | `cabdd117fc4dc713fbca085a48e38ac8c8f609555f42f10a05321c01623ff8e7` |
| audit_monthly_walk_forward.py | `e4a3be1c19b7f0af1226e71255c81116bd71a6a300aef36f61c688deb908df1f` |
| audit_monthly_walk_forward_index_v2.py | `f01a962fcf50a2cc2bb49fd4d3eb597eb07cda47f8d2697b8046ccb9b5721ed3` |
| audit_monthly_walk_forward_test.py | `ec0ddb99840d5bf380eb7f407de3e1a5bcbdfa352d79ad5d75e24a05750db57b` |
| audit_monthly_walk_forward_test_index_v2.py | `feea3954b231b18f18384696959d7cdbbcaf4d513dbf3fc4fee8596136483421` |
| test_audit_monthly_walk_forward.py | `8c47e89951506553bfb1295c6e390501828b8fe6f77bcae5d566e98c2039ef87` |
| test_audit_monthly_walk_forward_index_v2.py | `f986885706e78a9ecdac5f126502906d7f7637b513fb2f3a8ee16f765ea1c88d` |
| test_audit_monthly_walk_forward_test.py | `b3cc6d8225812154da2e4d2c644e426a19f7177d520b9d564826e3a3e4790a00` |
| test_audit_monthly_walk_forward_test_index_v2.py | `54a5ab7133705d528774c1ee458989a8acff60dfdef94a69aefd3b6662587194` |

## Condiciones del nuevo supervisor y salida

Antes de Popen: review independiente del supervisor, SHA externo de esa review
y runtime, codigo/tests/spec/dependencias publicados con commit completo40hex,
verificacion de objetos Git exactos y publicacion remota por root. Debe fijar el
comando de los siete argumentos de la extension, sin opciones para cambiar
reglas economicas: monthly-root, source-audit, validation-audit,
expected-validation-audit-sha256, implementation-review, runtime-review, output.

El output auditor y los logs del supervisor deben ser nuevos, disjuntos de
fuentes/codigo/autoridades y entre si, y quedar fijados antes de ejecutar.
One-claim durable y exclusion operativa; no reutilizar parciales ni reintentar.
Usar lock cientifico para impedir mutaciones del productor durante admision/run,
conservando bytes de locks existentes. Gate inmediato antes de Popen:
RAM disponible y commit libre >=2.000.000.000 bytes; no reutilizar una medida
antigua ni insertar trabajo pesado entre gate y lanzamiento.

Retener el handle Popen original hasta salida observada. Un fallo de observacion
o publicacion no debe abandonar un hijo vivo: drain sin retry, sin fabricar exit0.
Preservar start, admission, command, process identity, recursos, stdout/stderr,
exit real y fallo si lo hay. Ninguna completion de supervisor antes de exit0 y
validacion/hash de audit.json. El audit.json faltante nunca equivale a PASS.

Salida necesaria para OOF: status
PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES y scope compuesto;
completed_months exactamente202501..202606; prior_validation_audit apunta al
ba9f... real y hereda su reconstruccion; 6 meses nuevos/12 fits nuevos/13 modelos
usados/36 ventanas totales; 369 ticker-dias/363 disponibles/6 NO_EVALUABLE.
Auditor script SHA feea3954..., dependencies13, snapshots de codigo/autoridades,
verified_files union completo y rehash final. Fijar SHA externo de ese audit.json
SOLO despues de su cierre real y revisar antes del siguiente request.

## Secuencia posterior OOF

El wrapper OOF YA esta implementado/revisado: la descripcion de wrapper pendiente
en OOF_RUNTIME_SEQUENCE_DESIGN_20261023.md es historia previa, complementada por
OOF_PIPELINE_RUNTIME_SPEC_20261023.md y su review. No implementar otra secuencia.

Tras auditor compuesto real + exit0 y revision/publicacion, preparar aparte una
request OOF_PIPELINE_RUNTIME_REQUEST_V1 con status REVIEWED_OOF_PIPELINE_RUNTIME_REQUEST,
runtime_authorized=true revisado, seis meses fijos, mapa completo dependencies()
actual y pins literales de productores/auditor, roots monthly/session, autoridades
monthly_audit/session_audit con SHA, pipeline_root nuevo, correction_root compartido
y seis evaluation_roots nuevos disjuntos. Lock global fijo
BASE/oof_pipeline_runtime.lock. Aqui no se crea esa request.

El wrapper aplica gate2e9 antes de admision y cada fase, crea MonthlyInputs nuevo
para cada calibracion/replay y mes, y ejecuta doce fases seriales: correccion,
recibo sellado, replay con SHA de correccion. Historial solo de meses anteriores,
labels disponibles cierreNYSE+1min antes del mes objetivo. Conserva seis politicas,
no selecciona ganador y no refittea. Seis cierres de correccion y seis de replay
quedan ligados por recibos y SHA; no se autoautoriza un auditor al terminar.

Su completion es PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT. Resume solo mediante
mismo request/hash y prefijo integro revalidado; inicio sin recibo, huerfano, parcial
o mutacion fallan preservados. No borrar locks ni adoptar outputs por ausencia PID.

Solo entonces preparar/revisar/publicar request economica OOF separada FULL_H1,
version OOF_ECONOMIC_AUDIT_REQUEST_V1, audit mensual compuesto externo, raiz
correccion compartida y seis pares de SHA correction_completion/evaluation_completion,
mas output auditor nuevo. El auditor independiente comprueba las seis trayectorias,
controles, costes y gates por ticker sin elegir politica. PASS de reproduccion no
es PASS de rentabilidad. Mantener development_seen, technical_ready=false y
promotion_approved=false; sin produccion, API ni afirmacion prospectiva.
