# Revisión independiente del auditor Common Greek V2

23 de octubre de 2026. **CLEAR — PASS_COMMON_GREEK_COMPARISON_PATH_AUDIT_V2_IMPLEMENTATION_REVIEW**.
Alcance **IMPLEMENTATION_ONLY**; `runtime_authorized=false`,
`technical_ready=false`, `promotion_approved=false`.

Revisor: `/root/oof_reviewer`; autor: `/root/scientific_review`. Se leyeron el
auditor original completo, su especificación económica y el diff final V2.
No se modificaron código/reviews anteriores, productor o artefactos de mercado;
no se lanzó un auditor real, fit o inferencia ni se abrieron nuevos scores/labels
de mercado durante esta revisión.

## Qué cambia y qué se conserva

V2 identifica las claves relativas con separadores `/`, `\` o mixtos de forma
explícita. Lo aplica al baseline, markers ordinarios y markers de modelos. No
reescribe ni cambia el hash del manifest sellado. Sources absolutos y TRAIN
provenance conservan su tratamiento anterior.

Se rechazan rutas absolutas, UNC/rooted o drive-relative, ADS, segmentos vacíos,
dot/dotdot, caracteres y nombres reservados de Windows, sufijos punto/espacio,
escapes resueltos y colisiones por separador, casefold o destino resuelto. Una
colisión falla incluso con hashes iguales; no se fusionan miembros. Las ausencias
y cambios de hash siguen fallando.

Las funciones originales, salvo `main` y `verify_marker`, y las constantes
`POLICIES`, `EDGES` y `MISSING` conservan AST idénticos. El `main` final coincide
con una lista exacta de sustituciones de rutas. La lectura del diff confirma
que no cambian scheduler, políticas, métricas, tolerancias, costes, calendarios,
threshold, ranking o selección. V2 no importa implementación económica del
productor y mantiene la CLI y autoridades científicas anteriores.

## Hallazgo resuelto

**G2-PATH-001:** la primera V2 comprobaba contención al normalizar, pero una ruta
podía resolverse fuera del root después y antes de su consumo. El revisor lo
reprodujo con una redirección sintética de `Path.resolve`, usando bytes sellados
iguales dentro y fuera del root. El gate de esa reproducción fue RAM
7.980.756.992 y commit 5.369.024.512 bytes.

La versión final usa `resolved_manifest_target` tanto al normalizar como justo
al consumir baseline, markers y modelos. Devuelve la ruta resuelta y comprobada,
que se liga al memo y al rehash final. Las dos fixtures negativas de redirección
rechazan antes del digest del destino exterior. No quedan hallazgos bloqueantes.

## Verificación independiente

El revisor ejecutó **42 PASS, 7 deselected, 0,37 s**, con los argumentos:

```text
-q -p no:cacheprovider research_papers/JEPA/level_oracle_20261018/test_audit_common_greek_comparison_paths_v2.py -k "not legacy_fixtures"
```

Se comprobó el gate antes de `pytest.main`: RAM **7.991.095.296 bytes** y commit
**5.681.618.944 bytes**, ambos superiores a 2.000.000.000. Los casos cubren NPZ
sintéticos Windows/POSIX/mixtos, bytes float64/signed-zero, rutas peligrosas,
colisiones incluso con igual SHA, escapes iniciales y al consumir, miembros
ausentes, hashes mutados y preservación AST/diff.

El [recibo del autor](COMMON_GREEK_COMPARISON_PATH_AUDIT_V2_IMPLEMENTATION_RESULT_20261023.md),
SHA `88378005acbfc3e189f4d5a038bfe061314878fd5b0a01ff106680af53d441b7`,
informa **49 PASS, 1,13 s**, incluyendo siete fixtures anteriores ejecutadas
contra V2, y Ruff/compile PASS. Gate informado: RAM 7.904.841.728 y commit
6.235.291.648 bytes. Su pase inicial fue 47/1,11 s antes del guard al consumo.
El revisor **no repitió esas siete fixtures ni atribuye a su ejecución los
49 casos del autor**. No se repitieron pruebas para redactar este recibo.

## Bytes fijados

| Archivo | SHA256 |
|---|---|
| `audit_common_greek_comparison_paths_v2.py` | `2d4fc43456c4cd6fe45b378fae3580481a98e814c2eefa42b8eb1dec63f049d3` |
| `test_audit_common_greek_comparison_paths_v2.py` | `f537b0b8677c51798ac9d4aaa65aa7921ac29d4960535fad4e3a6b23d66a9c89` |
| `COMMON_GREEK_COMPARISON_PATH_AUDIT_V2_SPEC_20261023.md` | `9f9143f08eff87c612d896b3e9178333914b191c81a624814f2f0a081bda3f5b` |
| Auditor original preservado | `3898ef3c8ae634a65a2a136c75f2e14a46d5ac6fcad4bcc28bdb77742f3dca70` |
| Tests originales | `a73b878ddf53fd017df21accc3cbf6f6209ae8a3731374eb26b8c9ac85da81b4` |
| Spec económica original | `baf41bf4fae2fa6fe9618e2ed5eb69d827b00bf52ce6696ea122a4e46f29ec73` |

El [recibo JSON](COMMON_GREEK_COMPARISON_PATH_AUDIT_V2_REVIEW_20261023.json)
contiene nombres exactos y mapas de hashes para el gate externo del launcher.

## Intento 01 y frontera de ejecución

Se conserva el [fallo técnico del intento 01](COMMON_GREEK_AUDIT_01_TECHNICAL_FAILURE_20261023.md),
SHA `70b2b510db36edaef558c1bd44bfadb975020bfd8edcfb15ad6f322fb36380b4`.
Su manifest archivado tiene SHA
`7e0be74f4ef7874c7ff0cf383ced85d68a67412c9ddeee20c7dc847459a65e5b` y su
`exit.json`, `75cc7aceaf19475ee6c8701f21391651f31e8ec13ca61d791e597c6422770233`.
La diferencia entre la clave POSIX buscada y la clave Windows existente fue
documentada por `common_greek_resume`. El fallo textual no demuestra ausencia
física del score. El intento terminó exit 1 sin PASS económico y conserva esa
clasificación, independientemente de lo que ocurra después con V2.

Este CLEAR permite publicar la corrección revisada. Un futuro intento 02 requiere
publicación previa, launcher revisado con hashes externos, el `--review`
científico original intacto, raíz de salida/logs nueva y gate operativo de RAM y
commit. Root coordina esa ejecución por separado; este documento no la lanza ni
la autoriza automáticamente. No se alteran manifests, scores, modelos o políticas.

Un futuro PASS de V2 tendrá el alcance original: ejecución económica reconstruida
dado scores sellados, sin reproducir entrenamiento o inferencia. Esta revisión
no aporta un resultado económico real. 2025/2026 siguen siendo desarrollo visto;
`winner_selected=null` y promoción false.
