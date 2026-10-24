# Supervisor OOF V2: resultado de implementación sintética

24 de octubre de 2026. `SYNTHETIC_ONLY`, sin pipeline real, fit o lectura de
valores de mercado. Implementación y fixtures bajo el contrato publicado en
`4b2ab2a1931684f7127ad0728498d4ac60157e81`; wrapper y review independiente
publicados posteriormente en `54a2b40cd12fd281392fcab1a364f02ebfdf3124`.

Bytes finales:

- `launch_oof_pipeline_v2_20261024.py`:
  `26de981666975ffc3a6c75aa30d7279a133361786a0a6df475ed57017ebae411`.
- `test_launch_oof_pipeline_v2_20261024.py`:
  `5eb34bef30fc51d44d30dff27bfa918e960d9080be91a9b32487ee5aa6643a2f`.

El supervisor liga por SHA la
[review del wrapper](OOF_TRANSITIVE_SOURCE_V2_RUNTIME_IMPLEMENTATION_REVIEW_20261024.json)
`ca8f11ef9781a1f6996132032b8c7a09bf6f559970c66e0067bffab9507848f5`:
18 dependencias operativas, cuatro pins científicos y conjuntos de seis/ocho
dependencias de corrección/replay sin cambios. Rechaza reviews de otro scope o
que autoricen runtime como si fueran sólo implementación.

Los ocho helpers de admisión metadata son AST idénticos a los del wrapper V2.
Preflight, lanzamiento y cierre ligan `source_admission_sha256`; los outputs y
logs se protegen frente a las fuentes transitivas antes de crear el destino.
El preflight añade un resumen derivado del mapa ya leído: total indexado,
miembros exclusivos del índice en junio, missing de la autoridad y count/digest
del subconjunto externo esperado de la corrección de enero. Es reconciliación
metadata con el diagnóstico previo, sin gate económico ni lectura de partials01.
No se ejecutó ese preflight sobre fuentes reales en estas pruebas.

| Intento | Resultado | Tiempo pytest | Cambio posterior |
|---|---|---:|---|
| 01 | 40 PASS, 1 FAIL; exit 1 | 62,28 s | El probe heredado de imports sólo permitía OPS y rechazó `pyarrow`, requerido para leer las siete columnas metadata del índice. |
| 02 | 41 PASS; exit 0 | 57,10 s | Sin cambios posteriores. |

Entre ambos intentos sólo cambió la aserción del test: permite OPS y pyarrow,
conservando la prohibición de imports científicos desde preflight. El código
del supervisor fue idéntico. El segundo pase completo ya estaba iniciado cuando
root indicó que bastaba el focal fallido; se dejó terminar sin más repeticiones.
Ruff pasó en ambos y los pins propios/originales permanecieron intactos.

Las fixtures crean un índice Parquet artificial y archivos de texto como
sidecars, sin interpretarlos como mercado. Cubren junio index-only, logs que
invaden una fuente externa, sustitución de inode con bytes iguales entre
preflight y lanzamiento, revalidación de metadata y doce recibos de fase.
El supervisor no ejecuta ciencia en esa fixture: el cierre de doce fases se
construye artificialmente. Las doce fases con productores congelados y frontera
de fuente artificial corresponden al
[resultado separado del wrapper](OOF_TRANSITIVE_SOURCE_V2_RUNTIME_IMPLEMENTATION_RESULT_20261024.md).

Se lanzan únicamente hijos sintéticos vacíos para verificar gate, lock distinto,
handle retenido, exit real y drenaje ante error posterior a Popen. Otros negativos
conservan evidencia ante autoridad/pin/version incorrectos, mutación de cierres,
huérfanos, junction y low commit. No se llama automáticamente al auditor.

Cada intento fijó comando, pins y gate RAM/commit >=2.000.000.000 bytes antes
de ejecutar, CPU 1 y un thread por librería. No se atribuye a estas pruebas un
pico de memoria o rendimiento de mercado. Los payloads artificiales permanecen
locales en los `pytest_tmp` de
`D:/GexResearchArtifacts/level_oracle_20261018/oof_transitive_v2_supervisor_synthetic_20261024_01`
y `..._02`, según sus recibos de admisión.

El [archivo compacto](continuation_20261024/oof_transitive_v2_supervisor_synthetic/MANIFEST.json)
contiene 36 copias exactas / 364.371 bytes de recibos, logs, snapshots y launcher,
sin payloads sintéticos. Manifest SHA
`8331e85f1223f94949cb702d499126a092834c6829068ae5494bdf3a0caf6c3b`.
Los dos intentos, incluido el fallo, se preservan. Este resultado de autor no
sustituye revisión independiente, publicación o admisión de runtime y no permite
resume, adopción o reutilización de la corrección parcial 01.
