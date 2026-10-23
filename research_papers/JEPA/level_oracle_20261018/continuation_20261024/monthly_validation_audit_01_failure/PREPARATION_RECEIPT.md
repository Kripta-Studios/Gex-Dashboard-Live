# Preparación del supervisor de auditoría 2025

Fecha: 2026-10-23. Estado: preparado y probado; **supervisor y auditor real no iniciados**.

El script `launch_when_validation_complete.py` espera el cierre del productor de validación PID 11852, creación `1792784053.9282398`. Su SHA256 es `ccbecce5e10f03de302dbe19a448a1db138ed807b9c18bca266e43c377d10866`.

El script exige la cadena sellada `process_monitor_binding.json` → `monitor_open.json` → `monitored_exit.json`, salida cero observada por el handle retenido y `completion.json` del overlay de validación. Verifica las doce autoridades fijadas, las once dependencias científicas y sus snapshots, el contrato original, los checkpoints anteriores y finales, exactamente 24 modelos completos, doce meses cerrados y el freeze de selección, incluso si `selected_mode` es null. La ausencia de un PID no acredita una salida correcta. No modifica el productor, sus parámetros ni los modelos.

Hay un lock operativo independiente y un claim de ejecución de creación exclusiva. Durante la admisión y auditoría se mantiene el lock científico existente abierto `r+b`, sin escribir sus bytes; el hash se comprueba antes y después, fuera de la región bloqueada. La inspección del auditor congelado confirmó que no adquiere ni lee ese lock. El supervisor rechaza evidencia económica de 2026 y cierres globales de test.

El SHA inicial del propio supervisor queda fijado en `watch_started.json`. Se exige el mismo hash antes de admitir, después de copiar snapshots, antes de `Popen` y antes de publicar completion. Una fixture de mutación verifica el rechazo de cambios del script durante la espera.

El gate exige al menos 2.000.000.000 bytes tanto de RAM libre como de margen de commit, y se repite después de las verificaciones, antes de lanzar el hijo. Se ejecuta una sola vez el auditor original con `--monthly-root`, `--source-audit`, `--implementation-review` y `--output`. No hay retry. El output previsto, todavía inexistente, es `D:/GexResearchArtifacts/level_oracle_20261018/monthly_walk_forward_validation_audit_20261023_01`.

El supervisor retiene el handle de `Popen`, obtiene de él la creación del hijo y espera su exit code. Los recibos incluyen duración y máximo RSS observado mediante muestreo de un segundo, sin presentarlo como pico exacto de toda la vida del proceso. Solo publica su completion tras salida cero, `audit.json` con PASS y alcance completo de 2025, y un rehash de la evidencia admitida. El PASS sigue siendo condicional a los scores sellados: no implica refit, repetición de inferencia ni promoción.

Validación de preparación:

- `test_launcher.py`: **19 passed en 0,21 s**, exit 0. SHA256 `4f54e41bb5e9e1d25986f25c450fd89f9e72156ed06f7b1d6b48146ae3cb55be`.
- Fixtures de umbral exacto, recibos exclusivos, cadena de exit, fallo de monitor, locks y conservación de bytes, espera de recursos y alcance del comando. Un proceso Python vacío prueba la consulta de creación por handle después de una salida rápida; no ejecuta mercado.
- `py_compile`: PASS.
- `--check-static`: PASS; solo lecturas de hashes, autoridades y bindings.
- No existen `watch_started.json`, `attempt.json` o el output de auditoría. No se modificó ningún archivo del repositorio para preparar este supervisor.

Comando de ejecución reservado al root tras revisar el script:

```powershell
& 'C:/Program Files/Python314/python.exe' -u 'D:/GexResearchArtifacts/level_oracle_20261018/monthly_validation_audit_launch_20261023_01/launch_when_validation_complete.py' --watch
```
