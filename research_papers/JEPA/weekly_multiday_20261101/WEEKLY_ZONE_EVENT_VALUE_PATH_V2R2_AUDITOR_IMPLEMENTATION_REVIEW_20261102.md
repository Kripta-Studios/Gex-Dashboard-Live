# Revisión estática del auditor WEEKLY ZONE EVENT VALUE PATH V2R2 — 2 de noviembre de 2026

Estado: `CLEAR_STATIC_PRE_SUITE_NOT_EXECUTED`.

## Alcance congelado

- Auditor: `audit_weekly_zone_event_value_paths_v2r2.py`, 116851 bytes, SHA-256 `414d80331301c82404f81e366a63682b029f4f51cc7c0d659e370d6c20886d83`.
- Pruebas: `test_audit_weekly_zone_event_value_paths_v2r2.py`, 51396 bytes, SHA-256 `d02eba1fa017b46e0c22727b13153db6a36e08ed7bd99ff89f1397d232fa6eb4`.
- Enmienda de proyección: `WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_PROJECTION_AMENDMENT_20261102.md`, 5938 bytes, SHA-256 `22be603919cc93b3d6c7342a7e373e62939f58b8b69efec98dc1e5f136ee260b`.
- Revisión documental: `WEEKLY_ZONE_EVENT_VALUE_PATH_V2R2_PROJECTION_REVIEW_20261102.md`, 1721 bytes, SHA-256 `8cc822668fabb5f51cfc0f114ff8dab7c932af69247eae6f346ab4c7604e1abb`.
- Base V2R1 preservada: auditor `ef2bdd340c3e87ce9edd7d9b45b256ece02208646fa7fe095f167b24127a8122`; pruebas `f291c190833dfe3eff4ccd086e3fe323374f21f582ab9c97aaaa45fca79fe82b`.

## Dictamen

La corrección coincide con la enmienda y permanece acotada. V2R2 usa raíces exclusivas `audit_04`/`observer_04`, fija la identidad de sus pruebas y valida el pin byte-exacto de la enmienda R2 antes de recorrer las 29 autoridades. Conserva la corrección de admisión R1, las 29 autoridades científicas y las diez identidades de implementación.

El nuevo helper puro `historical_projection_signature` recorre exclusivamente las cinco columnas de identidad y las doce de valor en orden contractual, incluye sólo columnas físicamente presentes, conserva los tipos Arrow reales y rechaza nombres proyectados físicamente duplicados. No ordena por el esquema físico, no compara conjuntos, no usa fallback de esquema completo ni reutiliza la proyección de lectura por lotes.

La única comparación científica modificada está en la rama histórica de `reconstruct_sources`: tras `validate_option_schema`, bytes, SHA, filas y footer, compara el descriptor histórico pineado contra la nueva proyección. La firma completa de Parquet, `scan_option_source`, primeras autoridades, selección, relojes, trayectorias, spot, esquemas y cierres quedan sin cambios. El gate final continúa exigiendo 2784 fuentes, 2768 presentes y 2765 históricas.

La comparación estática R1→R2 conserva todas las funciones R1, añade sólo `historical_projection_signature` y modifica sólo `admit_pins` y `reconstruct_sources`. No aparecen imports del productor ni del módulo spot.

La suite conserva las pruebas R1 y contiene 51 funciones, equivalentes a 104 casos tras expandir estáticamente las parametrizaciones. Añade tres prefijos Parquet sintéticos reales —native large_string16, proxy large_string15 y native string16— que deben alcanzar exactamente el gate final `source population`; seis mutaciones negativas; una prueba unitaria directa que exige rechazar un nombre canónico físicamente duplicado; la reconciliación metadata-only de 2765 descriptores en 1454/1203/108; y límites AST frente a R1, V2 y V1. Los prefijos sólo redirigen `SOURCE_ROOT`, usan hashes, footers, guards y helper oficial reales, y no sustituyen las funciones comparadas.

## Límites y siguiente paso

Se rehashearon estáticamente código, pruebas, enmienda y revisión; las raíces `audit_04` y `observer_04` estaban ausentes. Esta revisión no importó módulos ni ejecutó compile, Ruff, pytest, Parquet, auditoría o datos raw. No acredita PASS numérico, resultado económico ni promoción. Autoriza únicamente preparar y revisar una suite formal única con launcher publicado y pineado, recursos oficiales, CPU0, diez variables de hilos fijadas, CUDA desactivado y conservación íntegra de evidencia.
