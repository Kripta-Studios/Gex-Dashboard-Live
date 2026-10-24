# Inicio del child de test mensual 2026

El launcher inició una sola vez el child PID **34680** a las **00:33:36.480821 UTC del 24-oct-2026**, después del preflight operativo y del gate de recursos. La creación `1792802016.462489` coincide exactamente entre el handle retenido y la observación de psutil; comando, preflight, binding y monitor coinciden. El launcher padre es PID 56000, creación `1792800312.1211853`.

Este recibo documenta el inicio de la **admisión interna del child**. A las **00:35:50.304005 UTC**, el runtime `monthly_test_resource_overlay_20261024_01` aún no existía; seguían los 24 modelos completos de validación, sin ningún `fit_started` con corte 2026, directorio mensual 2026 o report 2026. No acredita entrenamiento test, resultado económico, salida del proceso ni completion.

El lanzamiento usa la publicación `02cb4f7404abab0564c567d17eeaccd887b22a24`, el review runtime externo `1c6072a871d7d4cbcabc7e82dbbbbdb28d5767ff083571638f956d92250b557b` y la auditoría 2025 `ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc`. El [preflight](continuation_20261024/monthly_test_start_01/preflight.json) conserva el status `PASS_MONTHLY_TEST_OPERATIONAL_PREFLIGHT_ONLY_NOT_EXECUTED` y vincula 38.589 archivos. El child se inició posteriormente; ese status no se reescribe.

El [gate previo a Popen](continuation_20261024/monthly_test_start_01/admission.json), observado a las 00:33:36.461523 UTC, registra 7.254.020.096 bytes de RAM disponible y 5.455.089.664 bytes de margen de commit. Ambos superan el mínimo fijo de 2.000.000.000 bytes. El código del child conserva SHA256 `f2b0490cdec916f98c09fc77a6533d0eab8c4f2711331753f7d5c998d81253c1`; el monitor, `3e77bda56dabd8287b04ae9a47b4dcd45d5967a01a31514e933cbb44b6f4c08d`.

Se archivaron únicamente cuatro recibos inmutables, **7.393.712 bytes** en total. El [manifest](continuation_20261024/monthly_test_start_01/MANIFEST.json) registra originales, copias, tamaños y SHA256; ambas versiones se rehashearon y coinciden:

| Recibo | Bytes | Función |
| --- | ---: | --- |
| [preflight.json](continuation_20261024/monthly_test_start_01/preflight.json) | 7.391.018 | Autoridades y comando previo a ejecución. |
| [process_binding.json](continuation_20261024/monthly_test_start_01/process_binding.json) | 1.212 | Identidad del child y hash del preflight. |
| [monitor_open.json](continuation_20261024/monthly_test_start_01/monitor_open.json) | 1.266 | Handle retenido, comando e identidad; hash del binding. |
| [admission.json](continuation_20261024/monthly_test_start_01/admission.json) | 216 | Recursos inmediatamente anteriores a Popen. |

SHA256 del manifest: `a2afcb3701e7a86c001ca4810dd55cf4b7a5edcc0d8f352cadab5d9efaf8d2a5`. Los originales siguen en `D:/GexResearchArtifacts/level_oracle_20261018/monthly_test_launch_20261024_01`. No se copiaron stdout/stderr mutables ni se abrieron métricas parciales de 2026. La observación continúa; cualquier salida y cierre científico necesitarán sus recibos propios.
