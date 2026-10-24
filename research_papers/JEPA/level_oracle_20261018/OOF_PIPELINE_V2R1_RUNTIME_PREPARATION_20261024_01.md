# Preparación operativa OOF V2R1

24 de octubre de 2026. Materiales para revisión externa y publicación conjunta.
No se ha invocado preflight real R1, `Request`, `MonthlyInputs`, calibración,
replay ni auditor durante esta preparación. Los flags requeridos por el esquema
no sustituyen publicación, revisión ni GO de root para una ejecución real.

| Artefacto | SHA256 |
|---|---|
| [Request R1](OOF_PIPELINE_V2R1_RUNTIME_REQUEST_20261024_01.json) | `37f2018c7145d3b82cba2e34fbff9ae3008e33f32b004c5580e433157f38ef15` |
| [Binding R1](OOF_PIPELINE_V2R1_LAUNCH_RUNTIME_BINDING_20261024_01.json) | `9e4949227dfd8b0aa3e72a35271b081413dbd9dee482b79c98911ea25478813c` |
| [Review del supervisor](OOF_TRANSITIVE_SOURCE_V2R1_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json) | `2782b686947c9ddd5f723ad2b279802d21f3adbbee79aa76a6cd6e8bce551a78` |

Se verificaron los 48 archivos exactos de la review del supervisor, los 18
miembros de runtime de la review wrapper `7431a6df…c222c9` y los seis recibos
compactos upstream. El binding fija 55 miembros publicados, más su propio
archivo comprobado externamente para evitar circularidad. No se exige un
estado Git global limpio. Los siete roots acotados de lectura y los pins de
audit mensual `87bfea58…569fd4e` y SessionClock `678eb21b…5a2f3b9` permanecen.
No se admite BASE, ThetaData o engine_v1 por prefijo.

Nueve destinos nuevos estaban ausentes al preparar estos materiales. Prefijo
común: `D:/GexResearchArtifacts/level_oracle_20261018/`.

| Uso | Directorio |
|---|---|
| Control pipeline | `oof_pipeline_runtime_20261024_v2r1_01` |
| Corrección compartida | `monthly_oof_correction_20261024_v2r1_01` |
| Replay enero | `oof_calibrated_policy_202601_20261024_v2r1_01` |
| Replay febrero | `oof_calibrated_policy_202602_20261024_v2r1_01` |
| Replay marzo | `oof_calibrated_policy_202603_20261024_v2r1_01` |
| Replay abril | `oof_calibrated_policy_202604_20261024_v2r1_01` |
| Replay mayo | `oof_calibrated_policy_202605_20261024_v2r1_01` |
| Replay junio | `oof_calibrated_policy_202606_20261024_v2r1_01` |
| Logs retenidos | `oof_pipeline_launch_20261024_v2r1_01` |

El futuro intento comienza por corrección de enero desde cero, sin resume ni
adopción de partials OOF01 o V2. No cambian periodos, modelos, políticas,
selección, costes, cutoffs ni scheduler. Las seis ausencias conservan ambos SHA
nulos y sus rutas nominales son ignoradas, sin incorporarlas a I o resolverlas.

El preflight real posterior a publicación deberá producir el resumen del mapa
que ya construye: 2.226 sidecars COMPLETE, 126 de junio exclusivos del índice,
seis ausencias y 1.542 referencias externas esperadas del diagnóstico de enero.
Estas cifras son reconciliación esperada de metadata, no una medición nueva de
esta preparación ni un gate económico. Aquí no se releyó el índice ni ningún
sidecar. El fallo del preflight V2 permanece inmutable.

La CLI futura es `launch_oof_pipeline_v2r1_20261024.py`, con los paths/SHA de
esta tabla, `--implementation-review-sha256` igual al de la review del supervisor
y el commit completo que root publique y verifique. Default sólo admite metadata;
`--execute-reviewed-pipeline` requiere GO separado y conserva un único hijo,
locks, gate de recursos, handle retenido y drenaje. No se fija un commit futuro
ficticio ni se ejecuta la CLI desde esta preparación. Un eventual cierre del
pipeline seguiría pendiente de auditoría económica independiente.

Una lectura auxiliar inicial de JSON omitió `encoding="utf-8"` y falló con
cp1252 antes de escribir la request; se corrigió esa lectura de preparación.
No fue un preflight ni se creó ningún destino de runtime. El código sellado y
los intentos sintéticos no cambiaron por ello.
