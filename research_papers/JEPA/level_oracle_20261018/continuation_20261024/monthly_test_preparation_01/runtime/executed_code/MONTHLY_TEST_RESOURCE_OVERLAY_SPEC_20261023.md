# Wrapper operativo de test mensual 2026: gate2GB y admisión previa

Fecha2026-10-23. Código nuevo, sin ejecución de mercado. La continuación general
está autorizada; el coordinador mantendrá cargas pesadas secuenciales y no
ejecutará este entrypoint hasta cerrar/auditar2025 y publicar revisiones exactas
de implementación y runtime. No se cambian el productor, overlayvalidation,
auditor2025, modelos, CONFIG, ventanas, costes, features, políticas o selección.

## Cambio operativo único

`run_monthly_test_resource_overlay.py` llama al `main()` congelado de
`run_monthly_walk_forward.py` con su CLI original de fuentes/revisión/salida y
**`--stage test`**. No expone stage como opción ni acepta defaultall. Sustituye
únicamente `train_causal_rollout.wait_resources` durante esa llamada; restaura
la función y sys.argv enfinally, incluso tras excepciones. Cada observación
comprueba exactamente2.000.000.000bytes libres de RAM y decommit; si falta alguno,
espera30segundos y registra otra observación inmutable. El límite es decimal.
No es una cota de memoria máxima ni modifica el algoritmo de los12fits nuevos.

El contrato científico sigue fijado en
`7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f`, con las mismas
once dependencias y snapshots. El modo elegido con2025 se conserva incluso si
esnull. Los12fits nuevos son expanding/rolling12 enero–junio2026; static reutiliza
su modelo2023–24. La función original mantiene las verificaciones completas y
reutiliza modelos terminados. El wrapper no hace fit, selección o inferencia
por una ruta alternativa ni abre labels directamente.

## Autoridades antes de iniciar test

Revisión de implementación nueva:
`status=PASS_MONTHLY_TEST_RESOURCE_OVERLAY_REVIEW`, con todos los campos exactos
de `review_expectations()`: hashes de los tres archivos nuevos, once dependencias
originales, contrato, threshold, scope=test y scientific_inputs_changed=false.

Revisión de runtime nueva:
`status=PASS_MONTHLY_TEST_RESOURCE_RUNTIME_REVIEW`, scope=test,
scientific_root absoluto, hash de la revisión anterior, review_expectations
exactos, contrato original, allowed_read_roots absolutos acotados y mode initial
o resume. Cada autoridad se expresa como `{path, sha256}`. No se admite una raíz
de volumen como lectura genérica. El hash de audit2025 también llega por CLI,
independiente del contenido del archivo que pretende autorizarse.

Su bloque `validation` liga:

- `audit`: auditoría independiente2025 completa, statusGIVEN_SEALED_SCORES,
  doce meses exactos,24ventanas,750ticker-días y reconstrucción de selección/informe.
- `freeze`: selección/null exacta, perteneciente al inventario de esa auditoría.
- `runtime_root`, `runtime_launch`, `runtime_completion`: cierre del overlay de
  validation, con dependencia científica intacta, miembros y checkpoints.
- `process_binding`, `monitor_open`, `monitored_exit`, `monitor_code` y, cuando
  el binding normalizó un recibo previo, `source_launch`: cadena de observación
  del proceso real, fijada por hash y revisada antes deejecutar.

Se rehashea todo verified_files de la auditoría2025, se verifican las raíces y
bindings de fuentes/índice/contrato y se exige cada cierre mensual, report2025 y
los24modelos con fit_started/completion y payload sellados. Un textoPASS suelto,
una revisión de código o un PID ausente no sustituyen esa autoridad.

Si el binding contiene source_launch_receipt_sha256 o el flag de normalización,
source_launch es obligatorio, tanto envalidation como en intentostest previos.
Un source_launch sin su hash en el binding también falla. No basta omitir el
miembro para eludir la cadena de procedencia normalizada.

El recibo de proceso debe tener status
`PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE`, exit_code0 de tipoentero, y coincidir
enPID/creation_time y process_receipt_sha256 con process_monitor_binding y
monitor_open. Este último debe acreditar `PROCESS_HANDLE_RETAINED`, el comando
del wrappervalidation y el hash del monitor. La completionvalidation debe ser
anterior a la observación de salida. El PID previo debe seguir ausente; un PID
reutilizado provoca rechazo conservador, nunca se termina otro proceso.

La cadena real actualmente prevista está en
`D:/GexResearchArtifacts/level_oracle_20261018/monthly_resume_20261023_01_logs`:
`process_monitor_binding.json`, `monitor_open.json` y futuro `monitored_exit.json`.
El original `process.json` de PowerShell no tiene por qué incluir creation_time
o command: su identidad se conserva porhash en el binding normalizado. La
revisiónruntime debe fijar los hashes reales una vez existan todos los cierres;
este documento no fabrica un recibo de salida mientrasvalidation sigueviva.
El wrapper autentica la observación registrada por el monitor revisado; no
pretende reabrir un handle histórico que ya fue cerrado.

## Exclusión de productores y preservación

Un lock operativo del SO, fuera del root científico, serializa todos los
wrappers test. Duranteadmisión se toma un probe exclusivo del run.lock original
abriendo el archivo existente sin escribir susbytes; se compara su hash.
Se libera antes de llamar main, que conserva su propio lock original. Si otro
productor gana la carrera entre ambos, el main congelado falla antes de iniciar
trabajo; nunca se ejecutan dos productores con el mismo lock simultáneamente.
No se borra un lock porPID ni se detienen procesos para obtenerlo.

Se registra el inventario de todos los complete markers, modelos, fit_started,
snapshots y contrato previos, y se exige igualdad al terminar. La auditoría2025
añade autenticación de sus payloads; el resumeoriginal verifica las matrices,
chunks yfuentes. El wrapper no se atribuye una auditoría económica independiente.
Todo fit_started debe tener modelo/completionválido; uno incompleto se preserva
y bloquea el relanzamiento automático, incluso con una revisiónruntime nueva.

En modeinitial deben existir exactamente los24modelosvalidation y ninguna
evidencia propia de test2026. Esto significa ventanasTRAIN con corte2026 en
fits/models, predicciones/meses/ledgers2026, report2026, completionglobal y
day_chunks2026 con targets/netlabels. No incluye el índice/calendario completo,
day_samples2026 ni feature_inputs2026 outcome-free legítimos. La presencia de
2026 en metadatos no es por sí misma motivo de rechazo.

En moderesume, además de los24modelosvalidation, se permite un subconjunto
completo de las12ventanas nuevas sólo cuando expected_completed_test_fit_keys
y expected_test_evidence coinciden exactamente con el inventario actual y la
revisión liga prior_test_attempts. Cada intento anterior debe tener launchtest
del mismo contrato/audit2025 y su cadena de salida porhandle. Un exitnonzero de
test anterior puede ser compatible con recuperación entre fits; su argvcompleto,
scope y once dependencias científicas deben seguir siendo los originales.
Jamás permite
adoptar un fitincompleto. El runtime se escribe siempre en un directorio nuevo.
Una fase test con completion.complete.json ya terminada se deriva al auditor,
no se ejecuta de nuevo. Los recibos de intentos previos no se sobrescriben.

## Publicación y cierre

```text
run_monthly_test_resource_overlay.py
  --runtime-root <directorio nuevo externo>
  --implementation-review <review exacta de wrapper/fixtures/spec>
  --runtime-review <binding previo con autoridades reales>
  --expected-validation-audit-sha256 <SHA externamente fijado>
```

Fuentes y outputcientífico son los mismos devalidation; runtime_root no puede
solaparlos ni solapar el código. Snapshots dewrapper/fixtures/spec ycopias de
las dos revisiones se publican conflush/fsync yrename antes de main. launch.json
conserva argvtest,PID,recursos,autoridades ycheckpointsprevios. Observaciones de
gate, failure.json o completion.json quedan enese root externo. Las autorías se
rehashean antes del cierre. Un fallo de admisión no inicia main ni abre labels.

La completion del wrapper exige36modeloscompletos, seis meses2026 cerrados,
report2026, completionoriginal18meses/36fits, selected_modeintacto yhashes de
ambos informes. Describe retorno normal del productor dentro del wrapper;
el código de salida final del proceso debe observarse aparte porhandle.
El siguiente auditor2026 permanece independiente y condicionado a scores
sellados. No hay promoción ni evidencia prospectiva:2026 sigue siendodesarrollo.

## Fixtures

Sólo datos/recibos sintéticos y main doble: bordesdecimales de amboscontadores,
restauraciónnormal/excepcional, argvsolotest, dependencia/reviewalterada,
audit2025incompleto, hash externo incorrecto, freeze/null, cadena dehandle yPID
reutilizado,24modelos exactos, fitincompleto, primeraadmisión conpreparación
outcome-free2026, rechazo de outcome/fit2026previo, resume con checkpointcompleto
yrecibo legítimo, conservación de hashes, raíz nueva, bloqueo concurrente y
carrera al reacquirir el lock del runner. No se ajustaLightGBM ni se leen datos
de mercado. La revisión independiente yel runtimereal se emiten después de
las pruebas y del cierre real2025, respectivamente.
