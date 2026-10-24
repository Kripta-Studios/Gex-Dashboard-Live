# Wrapper OOF V2: resultado de implementación sintética

24 de octubre de 2026. Alcance `SYNTHETIC_ONLY`; no ejecución económica real,
refit ni lectura de valores de mercado. Contrato publicado en
`4b2ab2a1931684f7127ad0728498d4ac60157e81` antes de las pruebas.

Bytes finales:

- `run_oof_calibrated_pipeline_v2.py`:
  `213eb744b8e295688622955187227df66a56f9121252bd765b7054324e4cceae`.
- `test_run_oof_calibrated_pipeline_v2.py`:
  `ac1a1e43f7bcc553c7f06af67f0efe6203f515eb0fdc9d2db7c2c0bbf7c5f2d3`.

La ampliación usa metadata mensual e índice auditado, pertenencia exacta y SHA
externo. Los inputs consumidos conservan su declaración original para rechazar
aliases de separadores/case. Identidad física y hardlinks se comprueban sobre
sidecars indexados y archivos consumidos, sin stat/rehash de todo el inventario
histórico. El contrato operativo V2 registra el digest de admisión; productores
y contratos económicos originales permanecen intactos.

| Intento | Resultado | Tiempo pytest | Cambio posterior |
|---|---|---:|---|
| 01 | 38 PASS, 1 FAIL; exit 1 | 104,06 s | Corregida aserción del test: labels de replay están en `monthly_files`, no en `files`. Se corrigió además la normalización prematura del nombre consumido y se añadió negativo de separador. |
| 02 | 40 PASS; exit 0 | 96,29 s | Wrapper congelado; sólo se añadió una fixture de identidad al archivo de tests. |
| 03 | 1 PASS, 40 deselected; exit 0 | 2,16 s | Fixture nueva de reemplazo de un sidecar indexado por bytes iguales e inode distinto; `Request.recheck` falla. Sin cambios posteriores. |

Ruff pasó en los tres intentos. El intento 02 ejercita doce fases con los
productores congelados y una frontera `MonthlyInputs` artificial, sin constructor
de fuentes de mercado ni trainer. Los sidecars full se copian a un engine sibling;
junio se excluye del mapa mensual y se admite desde el índice. Se verifica
actions TARGET en corrección, ausencia de labels TARGET allí y uso posterior de
labels en replay. El registro `used` de cada instancia se actualiza antes de la
lectura de su tabla sintética. Las pruebas adicionales cubren short/missing,
conflictos, aliases, links, protección de outputs y preservación de parciales.

El wrapper no cambió entre los intentos 02 y 03. Los 40 casos del intento 02
se ejecutaron con test SHA
`8f2ee61bcc649a4752f8aa27c5907b3e91b44871a40ead5c6a3d81eb4ae4dfd8`;
el test final añade exclusivamente el caso del intento 03. No se presenta como
una sola ejecución de 41 tests sobre los bytes finales.

Cada intento guardó comando, pins y gate antes de ejecutar: CPU 1,
RAM/commit >=2.000.000.000 bytes. Los 17 miembros del conjunto operativo V1
original se verificaron antes/después y permanecieron intactos. Los cuatro
pins científicos y las dependencias de seis/ocho miembros no cambiaron.
Las fuentes sintéticas quedaron locales bajo
`D:/GexResearchArtifacts/level_oracle_20261018/oof_transitive_v2_wrapper_synthetic_20261024_01`,
`..._02` y `..._03`; `admission.json` fija el `--basetemp` de cada intento.

El [archivo compacto](continuation_20261024/oof_transitive_v2_wrapper_synthetic/MANIFEST.json)
contiene 42 copias exactas / 296.418 bytes, incluidos snapshots de código/tests,
recibos, logs y los launchers operativos, sin payloads sintéticos. Manifest SHA
`25f5c570abec28b63ba2842c9ad5879297e302626c0a20d5a4b7fc9c39c07c64`.
Los bytes de los launchers 01/02 se recuperaron mediante inversión exacta de sus
ediciones y coincidieron con el SHA registrado antes de cada ejecución; el
manifest distingue esa recuperación de las copias preedición de código/tests.

Revisión independiente de admisión: 17 focales PASS en 4,28 s, 24 deselected,
con bytes finales intactos. La
[review wrapper](OOF_TRANSITIVE_SOURCE_V2_RUNTIME_IMPLEMENTATION_REVIEW_20261024.json),
SHA `ca8f11ef9781a1f6996132032b8c7a09bf6f559970c66e0067bffab9507848f5`,
es `CLEAR / IMPLEMENTATION_ONLY`, runtime false. La
[revisión de invariancia](OOF_TRANSITIVE_SOURCE_V2_SCIENTIFIC_INVARIANCE_REVIEW_20261024.json),
SHA `47dc8ecaf527a94fc227dd5e42c99c6ea4e7fa7cb5e354c32bc417ae0aab0fe5`,
confirma 22 nodos originales AST idénticos y cambios de pipeline limitados a
versiones/digest de metadata. El supervisor V2 y su revisión son el siguiente
componente; esta evidencia no autoriza un runtime real ni reutilizar el intento 01.
