# Supervisor único del auditor mensual H1 V2

24 de octubre de 2026. Preparación operativa; no se ejecuta auditoría real ni se
crean autoridades con valores futuros. El productor, auditores científicos,
wrappers y launchers anteriores permanecen congelados. Este supervisor no llama
`TestAudit`, `verify_authorities`, entrenamiento, inferencia o replay en admisión.

## Archivos y autoridades

Nuevos: `launch_monthly_test_index_v2_audit_20261024.py`, sus pruebas y esta spec.
La revisión independiente requerida será
`MONTHLY_TEST_INDEX_V2_AUDIT_LAUNCH_REVIEW_20261024.json`, status
`PASS_MONTHLY_TEST_INDEX_V2_AUDIT_LAUNCH_IMPLEMENTATION_REVIEW`, decision CLEAR,
scope IMPLEMENTATION_ONLY y runtime_authorized=false. Su `files` debe ser el
mapa exacto de los tres archivos nuevos, las trece dependencias de la extensión,
las once dependencias científicas y el cierre de imports locales de los helpers.
Los helpers congelados se importan sólo después de verificar y publicar sus
bytes. Se rehashean inmediatamente después del import tardío.

Se suministran por CLI SHA externos del runtime y de la revisión del supervisor,
además de un commit Git completo de cuarenta hexadecimales. Los objetos Git de
código, reviews consumidas y runtime deben coincidir exactamente; root verifica
la publicación remota separadamente. El runtime no contiene su propio hash:
se añade externamente a la comprobación Git para evitar un pin circular.

El runtime conserva el esquema de la extensión y sus trece dependencies,
status `PASS_MONTHLY_TEST_INDEX_V2_AUDIT_RUNTIME_REVIEW`, scope compuesto y binding
de contrato, índice, fuente, freeze null, revisión493806... y auditor2025ba9f....
Las raíces permitidas deben ser concretas, existentes y acotadas; se rechaza
la raíz de volumen y BASE completo. Ningún futuro SHA de cierre test se calcula
para autoautorizarlo: debe figurar en el runtime revisado externamente.

Añade `launch_binding` con status `REVIEWED_MONTHLY_TEST_INDEX_V2_AUDIT_ONE_SHOT`,
`output_root`, `logs_root`, `supervisor_review={path,sha256}` y `published_files`.
Este último mapa usa rutas absolutas y comprende código e imports, revisiones
de supervisor/auditor/productor y runtime productor; excluye el propio runtime
auditor, cuyo SHA llega por CLI. Outputs nuevos, ausentes y disjuntos entre sí,
de las autoridades y de todas las raíces de lectura.

## Cierre del productor exigido

El bloque `producer` contiene `runtime_root`, `command`, `process_chain`,
`process_members`, `runtime_completion` y `runtime_review`. Cada autoridad es
un objeto exacto `{path,sha256}`. `process_members` contiene exactamente
process_binding, monitor_open, monitored_exit, monitor_code y runtime_launch;
source_launch sólo se admite como miembro adicional explícito y se valida
mediante la primitiva congelada cuando corresponde a normalización.

Se exige PROCESS_CHAIN_RECORDED y coincidencia exacta de sus miembros. Se usa
`verify_process_chain(..., validation=False)` y además se exige **exit_code=0**:
esa primitiva sola también permite cierres no cero para otras recuperaciones.
PID, creación, comando, monitor publicado y launch deben pertenecer al mismo
proceso. La desaparición del PID nunca sustituye un exit observado por handle.

La completion debe ser COMPLETE_MONTHLY_TEST_RESOURCE_OVERLAY, con el mismo
contrato, auditor2025, runtime productor revisado1c6072..., selección null y
scientific_inputs_changed=false. Launch < completion <= exit. El runtime
productor debe mantener sus expectativas de código, review49a359..., fuente,
freeze y raíces originales. Se comprueban sus cinco snapshots, el inventario
runtime exacto, igualdad de los checkpoints preservados y el inventario final
de checkpoints sin omisiones. Las veinticuatro ventanas originales deben estar
preservadas con los mismos bytes.

Se validan sólo JSON, markers y hashes de miembros, sin interpretar scores o
labels: treinta y seis modelos/start/completion exactos; inputs cerrados;
dieciocho meses con daily/economics/predictions; tres fit_keys y labels_read=false
en cada mes H1; informes2025/2026, freeze y completion científica18meses/36ventanas.
Cada miembro de marker se resuelve dentro de la raíz, sin traversal o colisiones,
y se vuelve a comprobar containment justo antes de consumirlo. La comprobación
económica completa queda reservada al único hijo auditor.

## Exclusión, proceso y resultado

El modo por defecto verifica y muestra el recibo, sin crear outputs ni lockfiles.
Usa el lock científico existente `run.lock` sin cambiar bytes. Ejecución explícita
añade un lock operativo fijo `BASE/monthly_test_index_v2_audit.lock` y mantiene
`run.lock` durante admisión, auditoría y validación de salida. La creación atómica
de logs es el claim durable: jamás se borra, reutiliza o reintenta automáticamente.

Antes de Popen se repiten pins, publicación y cierre. Tras abrir logs y completar
todo trabajo pesado, se miden RAM y commit Windows y se exige cada uno >=
2.000.000.000 bytes. No hay escritura, sleep o polling entre ese gate y Popen.
Comando fijo: Python actual, auditor V2 y sus siete argumentos revisados, sin
opciones para cambiar ciencia. Hijo oculto, stdin cerrado y OMP/BLAS a un hilo.

Se reutilizan RetainedProcess/drain del launcher publicado. La inicialización
del handle y toda publicación posterior a Popen están protegidas: un error
conserva el fallo y espera al hijo, sin abandonarlo ni fabricar exit0. Se registran
identidad por GetProcessTimes, exit por GetExitCodeProcess, recursos muestreados,
stdout/stderr y errores. Sin muestras, picos nulos y sample_count=0. El gate no
reserva memoria durante toda la ejecución.

`monitor_seconds` mide desde la inicialización del monitor posterior a Popen;
no es la duración completa del hijo. RSS/private son máximos de las muestras,
no picos exactos. process.json fija código del monitor, runtime, review externa,
commit y SHA del preflight. exit.json fija además el SHA exacto de process.json,
`observed_utc` e identidad del handle. Se rehashean los recibos al cerrar.

Sólo tras exit0 se exige audit.json válido: status/scope compuestos, binding
202501..202606, prior2025ba9f... heredado, seis meses nuevos/doce fits/trece modelos/
36ventanas,369/363/6 y las seis identidades ausentes exactas, selección null y
flags de reconstrucción completos. Se verifican exactamente quince snapshots:
trece dependencias y dos autoridades. El inventario heredado2025 debe estar
incluido sin alteración. La completion operativa fija entonces el SHA real de
audit.json y launch.json, preflight, process y exit. launch.json debe coincidir
exactamente en scope/dependencies/snapshots y hashes runtime/prior; se rechaza
cualquier failure.json coexistente del auditor. La completion incluye también
review externa/runtime/commit. Un exit0 sin resultado nunca es PASS. Un fallo posterior conserva
el recibo del exit real y publica failure.json, sin completion.

## CLI prevista y pruebas

```text
python launch_monthly_test_index_v2_audit_20261024.py --runtime-review <RUNTIME_REVISADO> --runtime-review-sha256 <SHA_EXTERNO> --supervisor-review-sha256 <SHA_REVIEW_EXTERNO> --publication-commit <COMMIT40>
```

El flag separado `--execute-reviewed-audit` habilita un único Popen tras admisión.
No se ejecuta durante implementación. Fixtures pequeñas cubren gates, pins,
publicación, closures de 36 modelos de texto/18 meses, cadena sintética mediante
helper congelado, errores y claim. Un hijo real exclusivamente `python -c pass`
comprueba handle después de salida; nunca se usa auditor real como fixture.
Este supervisor no inicia OOF, no elige modo y no acredita rentabilidad.
