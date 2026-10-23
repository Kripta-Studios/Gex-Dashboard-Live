# Lanzador de auditoría mensual 2025, intento 02

Fecha: 2026-10-24. Alcance: ejecutar una sola vez el auditor independiente V2 después de revisar y publicar sus autoridades. Este documento no acredita una ejecución ni un PASS real.

El intento 01 permanece cerrado con salida 1. Su auditor falló antes de auditar 2025 al convertir una ruta ausente a `Path`. El intento 02 conserva y verifica los hashes de su script, process, exit, failure, stderr, admission, attempt y revisión de lanzamiento. Exige el exit 1 por el handle retenido y la ausencia del output 01; no reemplaza ni reutiliza esos artefactos.

El productor mensual, sus once dependencias, modelos, calendario, ventanas, costes, políticas y selección permanecen iguales. Se exige el contrato `7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f`, la cadena del monitor del productor PID 11852 y su exit 0, y el completion de validación ya observado. Los hashes reales de esos cierres están fijados en el código. La admisión rehashea los 6.084 checkpoints preservados, los finales, exactamente 24 modelos completos, doce meses con predictions/economics/daily cerrados, freeze y report 2025. Conserva el modo seleccionado, incluido null. No usa métricas parciales para decidir el experimento.

La autoridad nueva se recibe únicamente mediante `--v2-review-sha256`, sin default. Debe ser el SHA256 externo de `MONTHLY_WALK_FORWARD_INDEX_AUDIT_V2_REVIEW_20261024.json` ya revisado y publicado. Se valida su status `PASS_MONTHLY_INDEX_V2_AUDITOR_IMPLEMENTATION_REVIEW`, los hashes de auditor/tests/spec V2 y sus referencias exactas al auditor, review y contrato originales. No se obtiene una autorización calculando el hash de cualquier archivo local. Hasta disponer de esa autoridad externa real, no se puede iniciar el intento.

El child ejecuta `audit_monthly_walk_forward_index_v2.py` con `--monthly-root`, `--source-audit`, `--implementation-review`, `--implementation-review-sha256` y `--output`. El único output permitido es `D:/GexResearchArtifacts/level_oracle_20261018/monthly_walk_forward_validation_audit_20261024_02`, que debe estar ausente antes del lanzamiento. No hay flags de stage, entrenamiento, selección o test 2026.

El supervisor solo puede ejecutarse desde el root externo canónico `monthly_validation_audit_launch_20261024_02`. La copia del repositorio es para publicación y revisión. Un lock operativo separado excluye otro supervisor; el claim `watch_started.json` de creación exclusiva impide adoptar o repetir un intento. El lock científico existente se mantiene abierto `r+b`, sin escribir sus bytes, durante admisión y auditoría. Su hash se comprueba fuera de la región bloqueada antes y después. El auditor no adquiere ese lock.

El gate exige al menos 2.000.000.000 bytes de RAM libre y de margen de commit. Se comprueba antes de la admisión y de nuevo antes de `Popen`, con observaciones externas inmutables. El script inicial y sus fixtures/spec se rehashean antes de admitir, lanzar y cerrar; se copian junto con el auditor y las autoridades a `executed_code`.

Se conserva el handle de `Popen` hasta obtener la salida real. El recibo fija PID, creación leída del mismo handle, comando, exit code y duración. El máximo RSS se presenta como observado mediante muestreo de un segundo, sin afirmar que sea el pico exacto de toda la ejecución. Un child rápido conserva identidad verificable mediante su handle, aunque ya haya terminado.

Solo se publica completion tras salida 0, `audit.json` con el status económico original, hash del auditor V2 y binding completo de 12 meses, 24 fits y 750 ticker-días, seguido de rehash de lo admitido. El PASS es condicional a los scores sellados: no repite fit ni inferencia y no autoriza promoción. Cualquier fallo preserva los recibos y termina sin retry. No contiene transición automática a 2026.

Invocación prevista, pendiente del review real y la revisión final del root:

```powershell
& 'C:/Program Files/Python314/python.exe' -u 'D:/GexResearchArtifacts/level_oracle_20261018/monthly_validation_audit_launch_20261024_02/launch_when_validation_complete.py' --watch --v2-review-sha256 '<SHA256 externo real del review V2 publicado>'
```

`--check-static --v2-review-sha256 ...` verifica autoridades sin iniciar espera o child. Ningún placeholder del ejemplo es un pin aceptable.
