# Revisión estática del auditor WEEKLY ZONE EVENT VALUE PATH V2R1 — 2 de noviembre de 2026

Estado: `CLEAR_STATIC_PRE_SUITE_NOT_EXECUTED`.

## Alcance congelado

- Auditor: `audit_weekly_zone_event_value_paths_v2r1.py`, 115418 bytes, SHA-256 `ef2bdd340c3e87ce9edd7d9b45b256ece02208646fa7fe095f167b24127a8122`.
- Pruebas: `test_audit_weekly_zone_event_value_paths_v2r1.py`, 41783 bytes, SHA-256 `f291c190833dfe3eff4ccd086e3fe323374f21f582ab9c97aaaa45fca79fe82b`.
- Enmienda de admisión: `WEEKLY_ZONE_EVENT_VALUE_PATH_V2R1_AUDIT_ADMISSION_AMENDMENT_20261102.md`, 4291 bytes, SHA-256 `2afce2d91e35393aad91e9dd65d6b9d9b6e156c0307ffd0f67823254032943d3`.
- Revisión de la enmienda: `WEEKLY_ZONE_EVENT_VALUE_PATH_V2R1_ADMISSION_REVIEW_20261102.md`, 1584 bytes, SHA-256 `886c0a83e25a65d8d63aef3ef26b530da984d224613d04139b590b78ac787a17`.
- Base V2 preservada: auditor `1ad942249d2eb160b2e8fe1ed902e577f9617dc4c11575e297cf5262f5aa61f2`; pruebas `e7f7c6e7cd7f9b93a1763b969205478da87182247b1d284d7c9fd5b980112bf7`.

## Dictamen

La corrección es acotada y coincide con la enmienda. V2R1 cambia las raíces exclusivas a `audit_03`/`observer_03`, fija la identidad de sus pruebas y exige el pin byte-exacto de la enmienda antes de recorrer o parsear las 29 autoridades. Las 29 autoridades y las diez claves de implementación permanecen iguales a V2.

El nuevo `validate_stage_a_receipt` admite únicamente la autoridad real de Stage A: cuatro cadenas exactas, las nueve comprobaciones con conjunto de claves y tipos estrictos, y los seis campos obligatorios del recibo de salida con valores y tipos exactos. Por tanto rechaza el anterior atajo incorrecto `status == "PASS"`, además de deriva de esquema, ámbito, conteos, tipos booleano/entero y evidencia de proceso.

La comparación estática V2→V2R1 deja todas las funciones V2 presentes, añade sólo `validate_stage_a_receipt` y modifica sólo `admit_pins`. No aparecen imports del productor ni del módulo spot. La integración de prueba de `admit_pins` está limitada a las 29 autoridades compactas y no abre raw, candidates, outcomes, Parquet ni NPZ.

La suite contiene 45 funciones de prueba y 91 casos tras expandir estáticamente sus parametrizaciones: 70 casos heredados y 21 casos V2R1. Cubre el recibo real afirmativo, 17 mutaciones de identidad/checks/exit, la admisión metadata-only real y los límites AST tanto frente a V2 como frente al auditor original.

## Límites y siguiente paso

Esta revisión no importó módulos, no ejecutó compile, Ruff, pytest, auditoría, productor ni lectura de valores. No acredita PASS numérico, resultado económico ni promoción. Autoriza únicamente preparar y revisar una suite formal única, con launcher publicado y pineado, recursos oficiales, CPU0, variables de hilos fijadas y raíces nuevas ausentes.
