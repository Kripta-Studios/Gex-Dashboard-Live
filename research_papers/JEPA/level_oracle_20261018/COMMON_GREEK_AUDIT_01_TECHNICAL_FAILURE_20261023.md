# Comparación 424: productor completo y primer auditor fallido

2026-10-23. Estado del intento de auditoría 01:
**FAILED_TECHNICAL_BASELINE_MANIFEST_PATH_LOOKUP**. El productor terminó con
`COMPLETE_FIXED_COMMON_GREEK_COMPARISON`, pero este intento no produjo un PASS
económico. No se ejecutó el reporte mensual descriptivo y no se lanzó un retry.

## Productor preservado

El launcher del productor terminó con exit 0, después de **4715,295044 segundos**.
Se observaron los cierres de 2025 y 2026 y después el cierre global. Se comprobó
la identidad del freeze y los siete miembros principales de ese cierre;
la comprobación no sustituye la auditoría económica y de fuentes completa.
El modelo 424 ya existía: esta ejecución no realizó ningún fit.

Raíz local: `D:/GexResearchArtifacts/level_oracle_20261018/common_greek_comparison_v1`.

| Artefacto | SHA256 |
|---|---|
| `completion.json` | `40cfdf576885eecd10785946687e5cf87cce228c1483e3ddd43cbd911207c824` |
| `comparison.complete.json` | `ad916c5695e165693c9843d206329732dde1d9149fc8ee0f9354818caf399d6d` |
| `freeze.json` | `b2609c562a319004a3517575def64305f11dce9521daeec347e45901be37ec08` |
| `period2025.json` | `b69569c62db5072e4bfb11b905b32d738c7f104159a57bb7c573ee38ef143de9` |
| `period2026.json` | `a3ed43d019a692e844e0ea45318c9c8d58c15787e313cc1a881a2f5a17776f80` |

Los informes de periodo se rehashearon como bytes; esta supervisión no abrió
sus métricas para tomar decisiones ni seleccionar políticas. Productor, scores,
modelos, reglas y archivos de cierre permanecen intactos. Este documento no
publica una conclusión económica derivada de un auditor incompleto.

El recibo del productor, `common_greek_comparison_v1_launch/exit.json`, registra
pico RSS **296.677.376 bytes**, pico privado **277.389.312 bytes**, mínimo libre
observado de RAM **2.315.599.872 bytes** y de commit **91.951.104 bytes**, con
muestreo de un segundo. El gate de 2 GB se aplica a la admisión del lanzamiento;
no reserva memoria ni garantiza un mínimo permanente durante la ejecución.
El mínimo de commit se conserva explícitamente. No se infiere de él su causa,
pérdida de datos, ni un fallo del productor, que terminó con exit 0.

## Intento independiente 01

Tras coordinación con root y nueva comprobación de recursos, se lanzó una sola
vez el auditor publicado `audit_common_greek_comparison.py`, sin modificarlo.

- Inicio: **2026-10-23 20:47:42.061087 UTC**.
- PID 43828; creación Unix 1792788462.056281; wrapper PID 50536.
- Python: `C:/Program Files/Python314/python.exe`, sin `-O`.
- `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`.
- Salida solicitada nueva: `common_greek_comparison_v1_economic_audit_01`.
- Logs y recibos externos a esa salida: `common_greek_comparison_v1_economic_audit_01_logs`.
- Fin: **2026-10-23 20:48:31.089325 UTC**; **exit 1**, **49,033950 segundos**.
- No existe `common_greek_comparison_v1_economic_audit_01/audit.json` tras el intento.

El comando exacto, rutas y proceso están conservados en
[process.json](continuation_20261023/common_greek_audit_01_failure/process.json).
Los pins comprobados al lanzar incluían:

| Autoridad | SHA256 |
|---|---|
| Auditor original | `3898ef3c8ae634a65a2a136c75f2e14a46d5ac6fcad4bcc28bdb77742f3dca70` |
| Review de implementación 424 | `6270e38baa5fded3fd0a12d5b16b7969347e3a43b6c1cc068b95783c7efbb540` |
| Completion del productor | `40cfdf576885eecd10785946687e5cf87cce228c1483e3ddd43cbd911207c824` |
| Marker global del productor | `ad916c5695e165693c9843d206329732dde1d9149fc8ee0f9354818caf399d6d` |

Los demás vínculos de modelos, SessionClock, comparación compacta y revisión
siguen siendo comprobaciones obligatorias del auditor. No se reemplazó ninguna
autoridad por un hash obtenido de una fuente modificada.

Recursos registrados en el intento 01:

| Medida | Bytes |
|---|---:|
| RAM libre en admisión | 10.750.095.360 |
| Commit libre en admisión | 13.964.713.984 |
| Gate mínimo de ambas | 2.000.000.000 |
| Pico RSS muestreado | 131.469.312 |
| Pico privado muestreado | 105.488.384 |
| RAM libre mínima muestreada | 10.545.180.672 |
| Commit libre mínimo muestreado | 13.777.760.256 |

Son observaciones cada segundo, no cotas de máximos o mínimos entre muestras.

## Fallo y causa técnica identificada

El [stderr original](continuation_20261023/common_greek_audit_01_failure/stderr.log)
se conserva byte por byte. Traza, con la ruta abreviada únicamente en esta copia
legible del documento:

```text
Traceback (most recent call last):
  File ".../audit_common_greek_comparison.py", line 487, in <module>
    main()
  File ".../audit_common_greek_comparison.py", line 361, in main
    require(baseline_rel in baseline_manifest["files"], "Baseline score absent")
  File ".../audit_common_greek_comparison.py", line 27, in require
    raise AssertionError(message)
AssertionError: Baseline score absent
```

La consulta directa a `baseline_manifest["files"]` usa una clave construida con
separadores POSIX, mientras el manifest sellado contiene separadores Windows:

```text
Clave buscada:    predictions/QQQ/20250102.npz
Clave existente: predictions\QQQ\20250102.npz
```

Se comprobó esa diferencia leyendo sólo las claves del manifest y el código.
El fallo de pertenencia textual no demuestra que falte el archivo de scores.
La función `verify_marker` del auditor ya normaliza otras búsquedas y rechaza
colisiones; la búsqueda directa del baseline de las líneas 361–363 quedó fuera
de esa normalización. No se modificó el manifest para hacer pasar la comprobación.

El auditor ya había leído el `daily_json` del primer día, que contiene resultados
del productor, y cargado su NPZ de scores. Falló antes de leer `labels.parquet`
y ejecutar `schedule` para ese día; no completó la reconstrucción económica
de 1119 ticker-días. Esta descripción no afirma que
el proceso fallido fuera exclusivamente una lectura de schemas ni que hubiera
validado los resultados. No hubo refit, reinferencia ni cambios de política.

## Conservación y continuación

Se copiaron exactamente cinco archivos pequeños, **3845 bytes** en total, a
`continuation_20261023/common_greek_audit_01_failure`. Se rehashearon originales
y copias, sin discrepancias. El archivo no colisiona con las otras líneas de
la continuación ni modifica la evidencia de la parada del 18 de octubre.

| Archivo conservado | SHA256 |
|---|---|
| `admission.json` | `4c4c28e7d304a076f095ce9d34acec32ffa8bbafe7d310e1a3a91b0d4c8decf3` |
| `process.json` | `cdc103a175ed4f2c68b22ae7101b36eff214a12fea338e039e927b12d579ebd4` |
| `exit.json` | `75cc7aceaf19475ee6c8701f21391651f31e8ec13ca61d791e597c6422770233` |
| `stderr.log` | `7beab18b4505afdf6eb605d7f6d5ca1d8e59ba2f3573eeddacd07b8247d907b0` |
| `stdout.log` vacío | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

El [manifest del archivo](continuation_20261023/common_greek_audit_01_failure/manifest.json)
tiene SHA256 `7e0be74f4ef7874c7ff0cf383ced85d68a67412c9ddeee20c7dc847459a65e5b`.

El auditor original permanece inmutable. Una corrección requiere una versión
nueva, fixtures de rutas/membership, revisión independiente y publicación antes
de una ejecución distinta con salida y logs nuevos. No es un retry automático
ni autorización para cambiar productor, predicciones, costes o gates. Root
coordina esa secuencia por separado. El intento 01 conserva su fallo y no será
reclasificado como PASS por el resultado de una versión posterior.

Estado al emitir este informe: **productor completo; auditor 01 fallido; auditoría
económica 424 pendiente; reporte descriptivo no ejecutado; promoción false**.
