# Preparación de request y binding OOF V2

24 de octubre de 2026. Artefactos preparados para revisión externa y publicación;
no se ha invocado preflight real, `Request`, `MonthlyInputs`, calibración, replay
o auditor. Los flags exigidos por el esquema no sustituyen revisión, publicación
remota ni GO explícito de root para el lanzamiento.

- [Request V2](OOF_PIPELINE_V2_RUNTIME_REQUEST_20261024_01.json), SHA
  `d92bec82c03dfdf62b0bd0a5a4c5a134a16155ab18af2b82dace2ddc7d859e88`.
- [Binding operativo V2](OOF_PIPELINE_V2_LAUNCH_RUNTIME_BINDING_20261024_01.json), SHA
  `29e7eb540bf42fc358a0a4e82111e7d2be59c18c92992fb1b24013a0eceb98b1`.
- [Review del supervisor](OOF_TRANSITIVE_SOURCE_V2_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json), SHA
  `8c6e4b570df7a12d27da6ed19c9f142382fa4bb054fcfacdd5dd5334ac7fbfd2`.

Se verificaron los 48 archivos de esa review contra sus SHA. La request usa el
mapa exacto de 18 dependencias de la review wrapper `ca8f11ef…7848f5`; el binding
contiene 55 miembros publicados exigidos por el supervisor, además del propio
binding que se comprueba externamente para evitar circularidad. No exige un
`git status` global limpio ni incluye trabajo ajeno.

El audit mensual compuesto sigue siendo `87bfea58…569fd4e` y SessionClock
`678eb21b…5a2f3b9`. Los seis recibos upstream de proceso/auditoría/supervisión
conservan sus pins y se rehashearon como archivos compactos. El índice permanece
ligado por ambas autoridades; aquí no se volvió a leer su metadata ni payloads.
No se modificaron periodos, modos, políticas, costes o selección.

Todas las raíces siguientes estaban ausentes al preparar los JSON, y son
disjuntas entre sí. Prefijo común local:
`D:/GexResearchArtifacts/level_oracle_20261018/`.

| Propósito | Raíz nueva |
|---|---|
| Control/recibos pipeline | `oof_pipeline_runtime_20261024_v2_01` |
| Corrección compartida | `monthly_oof_correction_20261024_v2_01` |
| Replay enero | `oof_calibrated_policy_202601_20261024_v2_01` |
| Replay febrero | `oof_calibrated_policy_202602_20261024_v2_01` |
| Replay marzo | `oof_calibrated_policy_202603_20261024_v2_01` |
| Replay abril | `oof_calibrated_policy_202604_20261024_v2_01` |
| Replay mayo | `oof_calibrated_policy_202605_20261024_v2_01` |
| Replay junio | `oof_calibrated_policy_202606_20261024_v2_01` |
| Logs del supervisor | `oof_pipeline_launch_20261024_v2_01` |

El intento empezaría por corrección de enero desde cero. No hay `--resume`,
adopción ni reutilización de partials01. Las siete raíces acotadas de lectura
operativa permanecen como antes; no se añade permiso por prefijo para BASE,
ThetaData o engine_v1. La ampliación de sidecars corresponde al mapa exacto
verificado por V2, no a esas raíces operativas.

Después de publicar código/reviews/request/binding y verificar el commit remoto,
el preflight debe producir su resumen del mismo mapa que ya construye: 2.226
sidecars de índice, 126 de junio exclusivos del índice, seis missing de la
autoridad y el subconjunto externo esperado de enero que corresponde a las
1.542 referencias del diagnóstico previo. Son cifras esperadas por metadata,
no una medición nueva en esta preparación ni un gate económico. No se leerán
partials01 para construir la admisión ni se hará otro censo de sidecars.

La CLI futura usa `launch_oof_pipeline_v2_20261024.py`, estos paths/SHA,
`--implementation-review-sha256 8c6e4b570df7a12d27da6ed19c9f142382fa4bb054fcfacdd5dd5334ac7fbfd2`
y el commit completo que root
publique/verifique. Por defecto sólo realiza preflight; el flag independiente
`--execute-reviewed-pipeline` requiere GO de root y permite un único hijo con
handle retenido. No se fija un commit futuro ficticio ni se ejecuta ese comando
desde esta preparación. El cierre seguiría pendiente de auditoría económica
independiente, con promoción false.
