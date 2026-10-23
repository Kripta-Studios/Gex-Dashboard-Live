# Auditor mensual 2025 V2: admisión de ausencias explícitas en el índice

24 de octubre de 2026. Corrección técnica nueva, no rerun ni autorización de
mercado. Se conserva el intento01 fallido, el auditor original y su review.

El child 6840 salió con 1 antes de audit_validation: el constructor recorría todo
el índice y aplicaba Path(None) a features_path de QQQ 20260401, aunque evaluaba 2025.
Sólo se inspeccionaron schema, identidad, status, reloj, paths y hashes del índice;
no se abrieron features, acciones, labels, modelos ni outcomes reales.

Índice `D:/GexResearchArtifacts/level_oracle_20261018/session_clock_dataset_v1/index.parquet`,
SHA256 `7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4`:
2.625 filas, 2.619 COMPLETE y seis MISSING_SOURCE, QQQ/SPY en 20260401/09/15.
Las seis conservan day_root y close_i 390, evaluation_status=NO_EVALUABLE,
cuatro feature paths nulos y seis hashes de acciones/labels/features nulos.
COMPLETE tiene los cuatro paths y seis hashes presentes; evaluation_status es null.
Stderr preservado en `monthly_validation_audit_launch_20261023_01/stderr.log`, SHA
`f36e54b7e9bf94f8e4adc9b95068a013f5f9ea1b94db376a5b83d602be72b3c1`.

## Cambio acotado

Nuevo módulo `audit_monthly_walk_forward_index_v2.py`, copia independiente sin
imports del productor. Conserva todas las filas, orden, identidades y conteos.
No filtra 2026 para auditar 2025, no crea paths para ausentes ni imputa cero observado.

SourceDay conserva API y añade null explícito: feature_paths=None y hashes de
acciones/labels=None para las seis ausencias. Para COMPLETE exige cuatro paths
absolutos no vacíos, los seis SHA256 válidos y evaluation_status null. Ausentes
exigen identidad fija, NO_EVALUABLE y todos esos campos nulos. Day_root sigue
siendo el valor declarado, sin inventarlo ni exigir que exista una fuente ausente.
Status desconocido, cobertura distinta o COMPLETE incompleto fallan antes de
leer payloads. source_frame rechaza ausentes antes de hash/lectura.

Sampling, ventanas, matrices, scheduler, costes, economía, selección/freeze,
reportes, ceros estructurales antiguos y NO_EVALUABLE mantienen AST idénticos.
Las únicas diferencias funcionales son admisión del índice, su guard de lectura
y la identidad/review de la nueva versión. Fixtures reproducen los nulos reales
en un índice sintético completo y prohíben acceso a payloads en constructor o
filas ausentes; no se usan mercados para probar el arreglo.

## Identidad y CLI

Review propia `MONTHLY_WALK_FORWARD_INDEX_AUDIT_V2_REVIEW_20261024.json`, status
PASS_MONTHLY_INDEX_V2_AUDITOR_IMPLEMENTATION_REVIEW. La review exige decision=CLEAR,
scope=IMPLEMENTATION_ONLY y runtime_authorized=false. Los campos auditor_sha256,
tests_sha256 y contract_sha256 corresponden a V2, su test y esta spec. Exige además
original_auditor_sha256, original_review_sha256 y original_contract_sha256 iguales
a los pins siguientes; rehashea los originales y los incluye en verified_files.

| Original preservado | SHA256 |
|---|---|
| audit_monthly_walk_forward.py | `e4a3be1c19b7f0af1226e71255c81116bd71a6a300aef36f61c688deb908df1f` |
| MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDITOR_REVIEW.json | `db323959e6a894d6d6fb51bde764af0c96db0cb0bba2f1711bbe0807425d10ca` |
| MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDIT_CONTRACT.md | `cabdd117fc4dc713fbca085a48e38ac8c8f609555f42f10a05321c01623ff8e7` |

CLI original más `--implementation-review-sha256 <SHA externo>` obligatorio,
verificado antes de crear MonthlyAudit. Output siempre nuevo. STATUS y esquema
económico del audit.json se conservan; audit_script_sha256 identifica V2, y
verified_files.root contiene review V2 y linaje. Ningún PASS real se declara aquí.

## Integración pendiente

El wrapper y lanzador test 2026 consumen la auditoría por STATUS/binding/inventarios
y hash externo; no importan el auditor base. Una revisión de runtime real debe
fijar la salida V2 después de ejecución revisada/publicada y exit real.

`audit_monthly_walk_forward_test.py` sí importa el original y su TestAudit llama
al constructor defectuoso; un PASS 2025 V2 no corrige ese consumidor congelado.
Se necesita extensión nueva con import de V2, review/spec/dependencias propias y
fixtures con nulos reales. Root la coordina por separado; no se modifica el
archivo original ni se remapean módulos ocultamente. Los auditores OOF consumen
la autoridad mensual compuesta por hash, sin importar este constructor.

El alcance sigue siendo auditoría económica dada scores sellados, sin refit ni
reinferencia. 2025/2026 son desarrollo visto; promoción y technical_ready false.
