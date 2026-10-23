# Auditor Common Greek V2: recibo de implementación

23 de octubre de 2026. Se añadieron el auditor
`audit_common_greek_comparison_paths_v2.py`, sus fixtures y
`COMMON_GREEK_COMPARISON_PATH_AUDIT_V2_SPEC_20261023.md`. El auditor original,
productor, artefactos y fallo del intento01 permanecen intactos.

El diagnóstico comunicado por `common_greek_resume` identifica una diferencia
de separadores: el lookup del baseline usaba `predictions/QQQ/20250102.npz`,
mientras que su manifest sellado contenía `predictions\QQQ\20250102.npz`.
V2 normaliza de forma explícita las claves relativas del baseline, marcadores
ordinarios y marcadores de modelo. No reescribe ni reseña el manifiesto fuente.
Los mapas de fuentes absolutas y la admisión anterior conservan su tratamiento.

Se rechazan escapes, rutas absolutas/UNC/drive-relative, ADS, segmentos ambiguos,
nombres reservados Windows y colisiones de separador, casefold o destino resuelto,
incluso con el mismo SHA. Los miembros ausentes o hashes distintos siguen fallando.
No cambian políticas, scheduler, métricas, tolerancias, costes o calendarios.

## Pruebas del implementador

| Pase | Resultado | Alcance |
|---|---|---|
| Inicial | 47 PASS, 1,11 s | Normalización, rechazos de rutas y siete fixtures anteriores |
| Final | **49 PASS, 1,13 s** | Añade dos negativos de escape entre normalización y consumo |

Gate previo al pase final: **7.904.841.728 bytes de RAM disponible** y
**6.235.291.648 bytes de commit libre**, ambos superiores a 2.000.000.000 bytes.
Ruff y compilación: PASS. Se invocó pytest con `-q -p no:cacheprovider` sobre
`test_audit_common_greek_comparison_paths_v2.py`, desde un wrapper Python que
comprobó primero RAM/commit mediante `GlobalMemoryStatusEx`.

Las siete fixtures anteriores se ejecutan contra las funciones V2. Las nuevas
incluyen NPZ sintético con claves Windows/POSIX/mixtas y bytes float64 con signed
zero, rutas peligrosas, colisiones, omisiones y mutaciones. Una comprobación AST
exige identidad de todas las funciones originales salvo main y verify_marker;
main se compara además contra una lista exacta de sustituciones de rutas.
Constantes y funciones económicas mantienen AST idénticos.

La revisión pidió reforzar la frontera entre normalización y consumo: una
redirección de symlink/junction podía cambiar el destino después de construir el
mapa. V2 resuelve y comprueba contención de nuevo justo al consumir baseline,
marcadores y modelos; devuelve la ruta resuelta, que queda ligada al memo para
rehash final. Las dos fixtures nuevas simulan esa redirección y exigen rechazo
antes de calcular el digest del destino exterior.

El revisor `/root/oof_reviewer` comunicó CLEAR independiente para los bytes
finales, con **42 PASS, 7 deselected, 0,37 s** (`-k not legacy_fixtures`). Su gate
fue RAM **7.991.095.296 bytes** y commit **5.681.618.944 bytes**. Esa comprobación
es del revisor, distinta de las 49 pruebas del autor; su recibo independiente
conserva la autoridad y detalle de revisión. No se editaron auditor, tests o spec
estabilizados al escribir este documento.

## SHA256 finales

| Archivo | SHA256 |
|---|---|
| audit_common_greek_comparison_paths_v2.py | `2d4fc43456c4cd6fe45b378fae3580481a98e814c2eefa42b8eb1dec63f049d3` |
| test_audit_common_greek_comparison_paths_v2.py | `f537b0b8677c51798ac9d4aaa65aa7921ac29d4960535fad4e3a6b23d66a9c89` |
| COMMON_GREEK_COMPARISON_PATH_AUDIT_V2_SPEC_20261023.md | `9f9143f08eff87c612d896b3e9178333914b191c81a624814f2f0a081bda3f5b` |
| audit_common_greek_comparison.py, original preservado | `3898ef3c8ae634a65a2a136c75f2e14a46d5ac6fcad4bcc28bdb77742f3dca70` |

Sólo fixtures sintéticas: no hubo run real, nueva lectura de outcomes de mercado,
fit, inferencia, cambio de producción ni commit del implementador. Este recibo
no es PASS económico ni autorización de ejecución. Cualquier intento02 necesita
publicación y revisión previas y una raíz de salida nueva, conservando intento01.
