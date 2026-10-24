# Adaptación explícita del supervisor económico a OOF V2

24 de octubre de 2026. `DESIGN_ONLY`, `runtime_authorized=false`. Este contrato
autoriza sólo preparación documental. Implementación y fixtures necesitan
revisión, publicación y GO posterior de root. No existe todavía un cierre OOF V2
admitido por este documento. OOF01 conserva su fallo y sus artefactos.

## Archivos nuevos y originales preservados

Se propone añadir únicamente `launch_oof_economic_audit_v2_20261024.py` y
`test_launch_oof_economic_audit_v2_20261024.py`, adaptando explícitamente el
supervisor económico publicado en `3342e27de4f8c327b707f7bb82fd907e88c6e9aa`.
El original `launch_oof_economic_audit_20261024.py`, SHA
`17c1604419d0008be94f6922eb87f397143f8c04c87d01c3546ae66b5a643e1e`, sus tests,
review y diseño permanecen inmutables. Su review tiene SHA
`765b3a0f448ebe808281e491ad8710753ec0d1ac9b8cf942b0128c4c48c8e019`.
No se convierte el original en un selector V1/V2 ni se relaja su igualdad de 17.

El único cambio funcional permitido es admitir la identidad operativa V2 y
comprobar su digest de procedencia: nombres/versiones, mapas exactos de código,
reviews/pins, comando upstream y contrato de admisión. Se conserva el monitor,
los locks, gate, claim, publicación, snapshots, drain, checks de cierre y fixes
A1–A6. No hay refactor general, helpers científicos ni framework nuevo.

## Autoridades concretas ya disponibles

| Autoridad | SHA256 |
|---|---|
| Wrapper `run_oof_calibrated_pipeline_v2.py` | `213eb744b8e295688622955187227df66a56f9121252bd765b7054324e4cceae` |
| Review wrapper `OOF_TRANSITIVE_SOURCE_V2_RUNTIME_IMPLEMENTATION_REVIEW_20261024.json` | `ca8f11ef9781a1f6996132032b8c7a09bf6f559970c66e0067bffab9507848f5` |
| Review científica estática `OOF_TRANSITIVE_SOURCE_V2_SCIENTIFIC_INVARIANCE_REVIEW_20261024.json` | `47dc8ecaf527a94fc227dd5e42c99c6ea4e7fa7cb5e354c32bc417ae0aab0fe5` |
| Contrato V2 `OOF_TRANSITIVE_SOURCE_V2_IMPLEMENTATION_CONTRACT_20261024.md` | `85c8bd20107e6a2ee6cf0d6e00bb8d16a7d6b5d1c6bce5839f542266e4c17a8c` |
| Auditor científico `audit_oof_calibrated_policy.py` | `e7481fbe944a9ffadcf637e7a4b69cd8d636cdf50ae295426191db9d76b5d44b` |
| Review del auditor `OOF_ECONOMIC_AUDITOR_IMPLEMENTATION_REVIEW_20261023.json` | `cf7a0659b495ad9bab484839d71c1f4377fb25c5c9df60d772cf0b7667c4d653` |

Los 18 miembros de `binding.runtime_dependency_map` de la review del wrapper
son la autoridad exacta del nuevo `source.code`: no basta len=18 ni pertenencia
a un conjunto mayor. Se mantienen los cuatro pins científicos y los conjuntos
de seis/ocho dependencias de corrección/replay. Los 13 pins de la review del
auditor siguen siendo otro conjunto independiente y obligatorio.

El supervisor upstream nuevo es `launch_oof_pipeline_v2_20261024.py`. Su review
prevista es `OOF_TRANSITIVE_SOURCE_V2_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json`,
status `PASS_OOF_TRANSITIVE_SOURCE_V2_LAUNCH_IMPLEMENTATION_REVIEW`, decision CLEAR,
scope IMPLEMENTATION_ONLY y runtime_authorized=false. Sus SHA finales y su mapa
de archivos siguen pendientes. No se usa como autoridad su candidato ni un pin
de ceros. Se fijarán externamente después de sus fixtures y revisión.

## Diferencias de admisión respecto del supervisor económico original

1. La request del **pipeline upstream** debe ser exactamente
   `OOF_PIPELINE_RUNTIME_REQUEST_V2`, con los 18 pins anteriores. Su binding debe
   tener status `PASS_OOF_TRANSITIVE_SOURCE_V2_LAUNCH_RUNTIME_BINDING` y ligar su
   review nueva publicada. El comando retenido apunta al wrapper V2 exacto.
2. El contrato del pipeline es `OOF_PIPELINE_V2` y añade
   `source_admission_sha256`. El preflight upstream conserva
   `PASS_OOF_LAUNCH_PREFLIGHT_NOT_EXECUTED` y contiene ese mismo campo.
3. La completion supervisora upstream conserva
   `COMPLETE_OOF_PIPELINE_SUPERVISION_PENDING_INDEPENDENT_AUDIT` y sus
   `process_files`. Su `pipeline_closure` conserva compact_files/output_count/
   output_inventory_sha256 y añade source_admission_sha256. Se exige SHA64 válido
   e igualdad exacta entre preflight, contract y pipeline_closure, además del pin
   externo concreto de ese digest en el binding del nuevo supervisor económico.
4. La completion científica del pipeline sigue siendo
   `PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT`; **no** se le inventa un campo
   source_admission. Continúan los 45 miembros compactos, los 27 archivos de
   control, doce starts/receipts, seis pares de cierres y sus cadenas exactas.

Esta igualdad liga la admisión ya observada por el productor/supervisor V2;
no reconstruye por segunda vez A∪I. El padre del auditor no importa V2 ni llama
transitive_admission, validate_pipeline, Request, MonthlyInputs o reconstrucción.
No abre índice parquet, sidecars, arrays o métricas, ni rehashea el inventario
completo de payloads. Sólo lee/rehashea código, autoridades y recibos compactos,
y el JSON final del auditor para validar su cierre, igual que el original.

Las revisiones y todos los miembros efectivos se incluyen en publicación exacta.
La nueva review del supervisor económico fijará un mapa explícito, obtenido de
los 13 pins científicos, 18 del wrapper, cierre declarado del supervisor upstream
V2, tres archivos nuevos y autoridades/procedencia consumidas. No se inventa ahora
un recuento final ni se acepta un superconjunto sin revisión. Los originales se
fijan como procedencia; no se importan. La igualdad de mapas y el rehash después
de imports tardíos permanecen. El binding propio se añade externamente al chequeo
Git para evitar autopin circular.

## Request económica y ejecución sin cambios científicos

La request del **auditor** sigue siendo `OOF_ECONOMIC_AUDIT_REQUEST_V1`, scope
FULL_H1, enero–junio2026. No se añade source_admission a ese esquema congelado.
monthly_audit y session_audit siguen siendo strings, con monthly_audit_sha256
separado. Correction_root, seis evaluation_root y doce SHA de cierres se obtienen
únicamente del cierre V2 real. Nunca se adoptan cierres/roots de OOF01.

Se conservan la CLI del auditor y sus bytes. El supervisor nuevo recibirá los
mismos argumentos operativos externos que el original y sólo ejecutará con
`--execute-reviewed-audit`. Default: validación compacta sin crear destinos.
La review nueva prevista será
`OOF_ECONOMIC_AUDIT_V2_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json`, status
`PASS_OOF_ECONOMIC_AUDIT_V2_LAUNCH_IMPLEMENTATION_REVIEW`, CLEAR,
IMPLEMENTATION_ONLY y runtime_authorized=false. El binding operativo previsto
tendrá status `PASS_OOF_ECONOMIC_AUDIT_V2_LAUNCH_RUNTIME_BINDING`.

Destinos propuestos, sin crear:
`BASE/oof_economic_audit_full_h1_v2_20261024_01` y
`BASE/oof_economic_audit_launch_v2_20261024_01`, con
BASE=`D:/GexResearchArtifacts/level_oracle_20261018`.
Se mantienen frescura, disjunción, raíces acotadas, checks de links/junctions,
claim durable y locks no bloqueantes en orden: oof_economic_audit_launch.lock
y oof_pipeline_runtime.lock. El auditor no toma el segundo; el padre lo conserva
durante el hijo y cierre. Primero se exige finalización real upstream por handle,
identidad/comando/UTC/SHA encadenados, exit int0 y ausencia de failures/partials.

Se mantiene RAM y commit Windows >=2.000.000.000 bytes inmediatamente antes de
Popen, un hilo OMP/BLAS, hijo oculto, handle retenido y drain en finally. No retry,
resume, hijos huérfanos por excepciones manejables ni auditor automático desde
el pipeline. Los snapshots propios se verifican también después de validate_audit,
antes de completion. Un fallo tardío conserva exit real y failure sin completion.
La completion supervisora propia mantendrá su estructura, con status explícito
`COMPLETE_OOF_ECONOMIC_AUDIT_V2_SUPERVISION` y los nuevos pins operativos.

El PASS científico requerido sigue siendo
`PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_FULL_H1`, con request/audit mensual/correction
exactos, seis meses, seis políticas y flags originales. No cambian thresholds,
costes, cutoffs, scheduler, inferencia, modelos ni gates. El PASS reproduce
cálculos condicionados a scores base auditados; no acredita rentabilidad ni
promoción. 2025 sigue siendo TRAIN y 2026 desarrollo visto.

## Secuencia y evidencia futura

El [borrador nuevo](OOF_ECONOMIC_AUDIT_V2_RUNTIME_DRAFT_20261024_01.json) separa
autoridades disponibles de SHA/roots upstream pendientes, todos estos a null.
No es una request ejecutable ni aprobación de lanzamiento.

Tras review/publicación y GO de root: copia nueva acotada, diff/AST operativo y
fixtures pequeñas de metadata/texto e hijos inocuos. Deben rechazar V1, sustitución
de uno de los 18 pins por otro miembro, review upstream ausente/provisional,
contrato V1, digest de admisión ausente/distinto entre cualquiera de los tres
recibos y pin externo, cierres parciales/OOF01, y mutación tardía de snapshots.
El positivo usará esquema V2 completo, sin fixtures científicas adicionales ni
benchmark real. Se registran pins/comando/gate antes de cada intento; fallos y
versiones se preservan. Revisión independiente de implementación antes de uso.

Sólo tras cierre real V2 y review se materializan request y binding concretos,
se publican y root decide una única ejecución. Este contrato no satisface esos
pasos ni autoriza adelantarlos. Los diseños, intentos y autoridades anteriores
permanecen inmutables.
