# Preparación mensual: identidades y pesos

El único comando ejecutado fue `run_monthly_walk_forward.py --stage prepare`, en el root nuevo `D:/GexResearchArtifacts/level_oracle_20261018/monthly_walk_forward_v1`. Terminó con código 0 en **370,887 segundos**. Se usó un proceso y las variables de hilos BLAS/OMP se fijaron a 1. No se iniciaron fases de entrenamiento, validación o test.

Se verificaron antes de ejecutar los once hashes de dependencias frente a la revisión independiente `MONTHLY_WALK_FORWARD_IMPLEMENTATION_REVIEW.json` (`0af3b22302c4eea2da0671bf7fa7f1f8dc3a775ccc7a372e23f0de082a32cdc7`). El runner ejecutado fue `47a4df8b019d9d297ca1ee9b89fff63406409659336dbd7b0e4d7af01ed348bb`; la auditoría del dataset fue `678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9`, con sus bindings de índice, contratos y completion verificados.

| Resultado | Conteo |
|---|---:|
| Calendario esperado | 2625 ticker-días |
| Días disponibles muestreados | 2619 |
| Sesiones completas / cortas | 2595 / 24 |
| Fuentes ausentes, NO_EVALUABLE | 6 |
| Población de acciones ofrecidas | 15445024 |
| Identidades seleccionadas | 332472 |

La preparación proyectó exclusivamente `action_id,state_i` de las acciones. No leyó labels, retornos, ventajas, matrices ni arrays de features. Las bandas vacías de las sesiones cortas se conservaron sin redistribuir su cupo. Los IDs sólo identifican filas; no son features numéricas.

La comprobación posterior `verify_monthly_prepare.py` revisó todos los archivos de muestras y sus markers: SHA, binding, pertenencia exacta de archivos, identidades canónicas, orden por hash dentro de banda, conteos, límites temporales y pesos. La masa de peso por día es 1, con error máximo `4.440892098500626e-16`. No volvió a leer las acciones no seleccionadas: la reconstrucción de la selección sobre la población completa corresponde al runner ejecutado. Confirmó que no existen modelos, predicciones, matrices, chunks, informes económicos ni freeze de validación en el nuevo root.

Evidencia externa: `D:/GexResearchArtifacts/level_oracle_20261018/monthly_walk_forward_v1_prepare_verification.json`, SHA **654aa7239feeedfe5c9aa40d2c8c38db67fa6e867152f5aae7156c415ef32ab0**. Binding del run: `7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f`. Los logs hermanos `monthly_walk_forward_v1_prepare.stdout.log` y `.stderr.log` conservan el resultado y stderr vacío. El script verificador pasó Ruff; su ejecución terminó en 4,80 segundos.

PID 34584 terminado. Durante el run se observaron aproximadamente 1,04 GB de memoria privada y un pico de working set de 678551552 bytes; son observaciones del proceso, no medidas del consumo total del sistema. La preparación no acredita rentabilidad ni satisface por sí misma el requisito de operar cada día. Las seis ausencias de fuente permanecen sin evaluar. No se ha lanzado ninguna fase mensual adicional.
