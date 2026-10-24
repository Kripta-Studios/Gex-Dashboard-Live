# OOF intento 01: diagnóstico de referencias transitivas rechazadas

24 de octubre de 2026. **Diagnóstico de metadatos, sin cambios de código,
rerun o resume.** El intento permanece fallido. La primera corrección de enero
produjo su cierre local, pero el wrapper falló antes de sellar su recibo de
fase y antes del primer replay. Un cierre del productor no equivale al cierre
del pipeline ni a una auditoría económica OOF.

## Causa exacta

El traceback preservado en
`D:/GexResearchArtifacts/level_oracle_20261018/oof_pipeline_launch_20261024_01/stderr.log`
termina en `correction_closure → verify_map(inputs['files']) → Request.allowed_file`,
con `ValueError: Input outside declared roots`. El
[wrapper](run_oof_calibrated_pipeline.py) limita allowed_file a HERE, monthly,
session, correction y seis evaluation roots, además de la request y dos
autoridades exactas. El root de originales `engine_v1` no pertenece a ellos.

El [adaptador](monthly_oof_calibration_adapter.py), en source_table,
líneas 311–323, obtiene day_root y actions_sha256/labels_sha256 del índice
auditado, rehashea el sidecar consumido y lo añade a source.used. Esa ruta no
llama a MonthlyInputs.verify para exigir membresía del sidecar en verified_files:
su autoridad es el índice. En cambio, otros artefactos mensuales sí pasan por
verify. La discrepancia entre estas dos admisiones explica el rechazo técnico.

Primera ruta rechazada:
`D:/GexResearchArtifacts/level_oracle_20261018/engine_v1/QQQ/20250102/actions.parquet`,
SHA `0808dccf59748aa5c79d875804cc6bd680ab7d6bb63436a12e28c708eaa0d09a`.
La siguiente referencia a labels de esa sesión también queda fuera. Se
compararon rutas y hashes declarados; no se abrieron esos parquets.

## Censo observado

`202601.inputs.json` contiene 6.473 miembros en files y dos en run_authorities.
Exactamente 1.542 miembros de files quedan fuera de allowed_file, todos bajo
engine_v1; ninguna run_authority queda fuera.

| Referencias rechazadas | Cantidad |
|---|---:|
| actions.parquet de 2025, sesiones completas | 741 |
| labels.parquet de 2025, sesiones completas | 741 |
| actions.parquet de enero de 2026 | 60 |
| labels.parquet de enero de 2026 | 0 |
| Total | 1.542 |

Cada ticker tiene 267 actions y 247 labels rechazados: 514 rutas. Las nueve
sesiones cortas de 2025 —QQQ/SPXW/SPY en 20250703, 20251128 y 20251224—
aportan otras nueve actions y nueve labels dentro de session_clock_dataset_v1,
por lo que esas 18 referencias ya pasan el gate. Así, la historia de 750
ticker-días de 2025 se conserva como 741 completos y nueve cortos; no falta
ninguna fila por este diagnóstico. No aparecen paths de labels de 2026 en
el mapa de fuentes de esta corrección de enero.

Las 1.542 rutas rechazadas coinciden en path y SHA con verified_files.fit_inputs
de la auditoría mensual compuesta; 1.356 aparecen también en
inherited_validation. Esas categorías se solapan y no se suman.

La comprobación adicional de metadatos detectó una limitación del arreglo
basado sólo en ese mapa mensual: **126 sidecars de junio de 2026, 63 actions
y 63 labels, no figuran en verified_files**, aunque están identificados por
el índice pineado. Donde ambos mapas se intersectan no hay conflictos de SHA.
El alcance COMPLETE enero de 2025–junio de 2026 contiene 1.104 ticker-días
full y nueve short, con dos referencias por día: 2.226 sidecars. Añadir sólo
los miembros actuales del mapa mensual arreglaría enero pero dejaría junio
fuera; no se ejecutó ese supuesto arreglo para comprobarlo.

El audit SessionClock no tiene un campo verified_files. Su binding liga el
índice. Los engine_root y feature_root del contrato mensual son ambos el
session_root: añadir sólo esos roots tampoco admite engine_v1.

## Arreglo mínimo propuesto y fixture

La propuesta es una allowlist exacta path→SHA derivada de las autoridades
externas ya pineadas: mapa mensual más actions/labels de filas COMPLETE del
índice ligado por ambos auditores, dentro del alcance temporal necesario.
No se amplía BASE ni se autoriza cualquier archivo por estar bajo engine_v1.
El mapa generado por la corrección fallida sirve de diagnóstico, nunca de
autoridad o semilla de esa allowlist.

La implementación futura debe cotejar el SHA esperado del mapa consumido
contra esa autoridad exacta, rechazar conflictos/aliases/escapes o cambios
de identidad, conservar la protección de outputs y mantener separados los
miembros generados por el pipeline. El permiso de ruta no debe abrir labels
fuera de la fase/corte causal ya fijados ni modificar productores o matemática.

Fixture mínima necesaria: una referencia externa de actions y otra de labels
admitidas únicamente por el índice, ausentes del mapa mensual, junto a una
referencia full también presente en ambos mapas y otra short dentro del root.
Debe reproducir el rechazo anterior y validar la admisión exacta, además de
rechazar path desconocido, SHA distinto, conflicto de autoridades, alias/link
que cambie destino y fuente ausente convertida en path. Debe comprobar que el
intento parcial se conserva y no se adopta por mera existencia de su cierre.
Todo sería sintético, sin nuevo cálculo económico de mercado.

La propuesta se concreta por separado en el
[diseño V2 en estado DRAFT](OOF_TRANSITIVE_SOURCE_V2_DESIGN_20261024.md),
pendiente de su revisión y publicación antes de las fixtures V2.

## Evidencia y límites de esta lectura

El [recibo compacto del censo](continuation_20261024/oof_transitive_source_diagnosis/census_from_observed_metadata.json)
se materializó desde resultados de herramientas ya observados; escribirlo
no repitió las lecturas ni el censo. El índice se proyectó exclusivamente a
estas siete columnas: ticker, date, status, close_i, day_root,
actions_sha256 y labels_sha256. Su hash se verificó antes y después.
Se mantuvieron las 2.625 filas globales y 2.619 COMPLETE.

Gate Windows previo al import de PyArrow para ese censo: RAM disponible
8.522.563.584 bytes y commit libre 6.451.486.720 bytes, mínimo decimal
2.000.000.000 por recurso. No se importó pipeline ni MonthlyInputs. No se
abrieron matrices, modelos, scores, valores de calibración o sidecars de
acciones/labels; sólo código, metadatos de índice y campos de ruta/hash/control.

| Autoridad comprobada durante el diagnóstico | SHA256 |
|---|---|
| OOF_PIPELINE_RUNTIME_REQUEST_20261024_01.json | `9399f791e0dc34d62c272ba4bd2fc150fdd4c1c2608ca036718c8adb0c82cd71` |
| monthly_oof_correction_20261024_01/202601.inputs.json | `0fa3225d89ab8b15a59e851a3e387561b59f246b6ccb5bfdfe8eb5f5cb40c36d` |
| monthly_walk_forward_test_audit_20261024_01/audit.json | `87bfea586be13e02fd7fd0fe59c819195c62a430f34c867f9ec661812569fd4e` |
| session_clock_dataset_v1/index.parquet | `7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4` |

Los tres paths locales de datos de esa tabla están bajo
`D:/GexResearchArtifacts/level_oracle_20261018/`. El pin del cierre de corrección,
`3202375ba50fc0bcb8a621ae753a7b4861c15e4708a6c86c784c9315c242a602`,
fue comunicado por root; no se rehasheó ni se abrió su contenido para este
diagnóstico. Los logs de fallo y recibos de ejecución permanecen en
[la raíz del intento 01](D:/GexResearchArtifacts/level_oracle_20261018/oof_pipeline_launch_20261024_01/).

Este documento no autoriza implementación o ejecución V2, no evalúa la calidad
económica de una corrección parcial y no permite retry/resume automático.
El intento 01 sigue fallido y su evidencia debe permanecer inmutable.
