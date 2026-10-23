# Auditor mensual 2025: primer intento fallido por una ruta nula

24 de octubre de 2026, fecha local Europe/Madrid. El auditor se ejecutó el
23 de octubre a las 23:17 UTC. Estado: **FAILED_PRESERVED_NO_RETRY**.
El proceso terminó con **exit 1**, observado mediante su handle retenido,
después de **1,872662 segundos**. No produjo `audit.json` ni un PASS económico.
Se conserva el intento completo y no se ha repetido el auditor para elaborar
este informe.

El fallo ocurre en el constructor del auditor original al convertir
`features_path=None` a `Path`, antes de entrar en `audit_validation()`.
La fuente identifica esa fila como `MISSING_SOURCE`: el error técnico no
demuestra que falte una fuente que el índice hubiese declarado disponible,
ni valida o invalida la rentabilidad de los modelos.

## Productor y auditor son cierres distintos

El productor de validación, PID 11852, terminó previamente con **exit 0**,
observado a **2026-10-23 23:15:39.501243 UTC** mediante su handle retenido.
El recibo registra creación Unix 1792784053.9282398 y 13285,573091 segundos desde
el lanzamiento. Se conserva una copia exacta de
[monitored_exit.json](continuation_20261024/monthly_validation_audit_01_failure/producer_validation_exit/monitored_exit.json)
y del recibo de proceso que liga. Esa salida correcta del productor no sustituye
una auditoría independiente de sus resultados.

La admisión del supervisor registra 24 modelos completos y 12 meses cerrados,
`selected_mode=null` y `promotion_approved=false`. Son campos de ese recibo de
admisión; este trabajo no recalcula selección, modelos, predicciones o métricas.
El cierre económico mensual sigue pendiente de una auditoría satisfactoria.

## Ejecución y recursos del intento 01

Raíz original de recibos:
`D:/GexResearchArtifacts/level_oracle_20261018/monthly_validation_audit_launch_20261023_01`.
El supervisor PID 43976 había empezado su espera a 20:43:21 UTC. Conserva su
comando, revisión operativa y snapshots; su documentación de preparación
anterior al lanzamiento se archiva como historia, no como estado actual.

| Observación del hijo auditor | Valor |
|---|---|
| Inicio | 2026-10-23 23:17:19.907414 UTC |
| PID | 6840 |
| Creación Unix | 1792797439.9007168 |
| Identidad | `GetProcessTimes` sobre el handle retenido de `Popen` |
| Fin observado | 2026-10-23 23:17:21.762803 UTC |
| Exit code real | 1 |
| Duración desde lanzamiento | 1,8726620998932049 s |
| Muestras de memoria | 2, intervalo 1 s |
| Máximo RSS muestreado | 114.708.480 bytes |

El gate de admisión exigía 2.000.000.000 bytes libres tanto de RAM como de commit.
La última lectura, a 23:17:19.890130 UTC, registró **8.705.490.944 bytes de RAM** y
**6.724.714.496 bytes de commit**. Una lectura anterior, a 23:15:52.791952 UTC,
registró 8.811.872.256 y 7.631.122.432 bytes respectivamente. Son observaciones de
admisión, no una reserva permanente. El máximo RSS indicado es sólo el máximo
de dos muestras; no se presenta como pico exacto de toda la vida del proceso.

El [recibo de proceso](continuation_20261024/monthly_validation_audit_01_failure/process.json)
preserva la CLI exacta: auditor `audit_monthly_walk_forward.py`, raíz
`monthly_walk_forward_v1`, auditoría fuente SessionClock, revisión original
`MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDITOR_REVIEW.json` y salida nueva
`monthly_walk_forward_validation_audit_20261023_01`. No se cambió ningún argumento
científico durante el intento. El directorio de salida económica no llegó a
crearse; el programa lo crea después de terminar `audit_validation()`.

El supervisor emitió después `failure.json` con
`ValueError('Independent auditor exited nonzero; no retry')`. El error del
supervisor conserva la salida fallida del hijo; no es otro intento del auditor.

## Traceback y diagnóstico acotado

El [stderr original](continuation_20261024/monthly_validation_audit_01_failure/stderr.log)
se conserva byte por byte. Resumen de la traza con rutas abreviadas sólo aquí:

```text
audit_monthly_walk_forward.py:845  main()
audit_monthly_walk_forward.py:835  MonthlyAudit(...).audit_validation()
audit_monthly_walk_forward.py:401  Path(row.features_path).resolve()
pathlib/__init__.py:150            raise TypeError(...)
TypeError: argument should be a str or an os.PathLike object where __fspath__ returns a str, not 'NoneType'
```

Se revisó el orden del constructor en el código ejecutado. Antes del fallo,
el auditor ya había:

1. Leído la revisión de implementación y comprobado los hashes de auditor,
   fixtures y contrato de auditoría.
2. Leído el contrato mensual y rehasheado sus once snapshots de código.
3. Leído la auditoría SessionClock y comprobado sus vínculos con contrato,
   índice, completion de dataset y contrato de features.
4. Leído `index.parquet`, convertido las fechas, comprobado identidad sin
   duplicados y cobertura 2625 filas / 2619 COMPLETE.
5. Empezado a construir los descriptores `SourceDay` recorriendo el índice
   completo, incluidos los casos 2026, antes de auditar la validación 2025.

No es correcto afirmar que el auditor «no leyó nada». Sí leyó y rehasheó
autoridades, contratos, código e índice de rutas/hashes/calendario. La traza
y el orden del código sitúan el fallo antes de `audit_validation()`, de las
lecturas de `source_frame`, de la reconstrucción de muestras y de scheduler/
contabilidad de esta auditoría. No se atribuye a este intento una reconstrucción
completada de scores, economía o modelos. El supervisor tuvo su propia fase
de admisión anterior, cuyo mapa de archivos se conserva por separado.

Para identificar la causa, este diagnóstico acotado leyó sólo código, recibos
y nueve columnas de metadata del índice: ticker, fecha, estado, cierre,
day_root y las cuatro rutas de features. No abrió los archivos señalados por
esas rutas ni leyó matrices, modelos, acciones, labels, cotizaciones o métricas.
Se verificó el SHA del índice contra la auditoría fuente antes y después de la
proyección.

| Metadata | Valor |
|---|---|
| Índice | `D:/GexResearchArtifacts/level_oracle_20261018/session_clock_dataset_v1/index.parquet` |
| SHA256 del índice | `7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4` |
| Filas totales / COMPLETE | 2625 / 2619 |
| Primer `features_path` nulo en orden físico | fila 2439, índice empezando en 0 |
| Identidad de esa fila | QQQ, 20260401, `MISSING_SOURCE`, close_i 390 |
| `day_root` | No nulo |
| Las cuatro rutas de features | Nulas |

Los otros cinco casos nulos son SPY 20260401, QQQ/SPY 20260409 y QQQ/SPY 20260415,
en las filas 2441, 2454, 2456, 2466 y 2468 del mismo orden físico. Son las seis
ausencias ya declaradas en el índice. El constructor intenta construir
`Path(None)` para la primera de ellas aunque la tarea económica solicitada sea
validación 2025. No se eliminó ninguna fila del calendario, no se rellenó una
ruta y no se reinterpretó el missing como un dato disponible.

La [evidencia de metadata](continuation_20261024/monthly_validation_audit_01_failure/metadata_diagnostic.json)
conserva las columnas proyectadas, posiciones, campos nulos, rutas fuente y
hashes. Su SHA256 es
`8480dac51f4c8dc9e983e286b5e05963f8c3fa7c68ab4fd2a94feedb552d8036`.

## Conservación exacta

Se archivaron 24 archivos originales, **4.090.379 bytes** en total, bajo
`continuation_20261024/monthly_validation_audit_01_failure`. Incluyen proceso,
exit, failure, stdout/stderr, snapshots ejecutados, supervisor y revisión,
watch/arranque, recursos, pruebas y preparación, más el exit separado del
productor y su recibo de proceso. `admission.json` mide 3.947.211 bytes y también
se incluye: su mapa de 19.202 archivos admitidos queda preservado sin copiar
las matrices ni los modelos a los que se refiere.

Originales y copias se rehashearon, sin diferencias. Se excluyeron únicamente
`__pycache__` y el archivo de lock operativo, con motivo registrado: no son
autoridades científicas ni prueba de un proceso vivo. La existencia residual
de un lock no sustituye los recibos de salida. La metadata diagnóstica es un
artefacto derivado nuevo, identificado como tal, y no reemplaza al índice.

El diff de publicación conserva una advertencia de línea vacía al final del
snapshot `executed_code/test_audit_monthly_walk_forward.py`. Esa línea ya está
en el original sellado y se mantiene para conservar sus bytes y SHA; el resto
del alcance pasa la comprobación de whitespace. No se presenta el diff completo
como libre de advertencias.

| Evidencia conservada | SHA256 |
|---|---|
| `admission.json` | `1fcdf8659eb5d6da26ddc485922b972cce8a4c2ca228187b22246becd5fea8e8` |
| `process.json` | `1255df01d0984278459ab711d317ecc57c4cb6470b8277a0ebb0a5056d6e58df` |
| `exit.json` | `d5e4fdf711e6965a56b8c60100788c2143aecbc7da450a93efe74736b9eadccb` |
| `failure.json` | `51cba5dd88423cdd2a9fdb05fa3c705f1944f21e8308144e386d76c2faaac019` |
| `stderr.log` | `f36e54b7e9bf94f8e4adc9b95068a013f5f9ea1b94db376a5b83d602be72b3c1` |
| Auditor original ejecutado | `e4a3be1c19b7f0af1226e71255c81116bd71a6a300aef36f61c688deb908df1f` |
| Revisión científica original | `db323959e6a894d6d6fb51bde764af0c96db0cb0bba2f1711bbe0807425d10ca` |
| Exit separado del productor | `918964c6474df52067db5fb6eecb1c07339cb9bca262e8cab560f22ba3b00e93` |

El [manifest del archivo](continuation_20261024/monthly_validation_audit_01_failure/manifest.json)
lista todas las rutas originales, tamaños y SHA256. Hash del manifest:
`21938d4d82b35ebf98f403995ec00cf27213e1163bbdb323092a0d17649192bd`.
El supervisor original tiene SHA
`ccbecce5e10f03de302dbe19a448a1db138ed807b9c18bca266e43c377d10866`;
sus snapshots se conservan sin modificación.

## Estado que permanece

**Productor de validación: exit 0. Auditor mensual 01: exit 1, sin PASS y sin retry.**
No se abrió aquí una evaluación económica nueva, no se modificaron fuentes,
modelos, producer, revisión original ni parámetros. No hay promoción autorizada.
La corrección técnica V2 se prepara en una línea separada y necesitará revisión
y publicación antes de una ejecución distinta, coordinada por root. Cualquier
resultado posterior conservará este primer fallo, sin reclasificarlo como éxito.
