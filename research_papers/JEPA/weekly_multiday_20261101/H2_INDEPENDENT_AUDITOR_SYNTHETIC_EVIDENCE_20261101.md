# Auditor H2 independiente: recibo sintético post hoc

## Alcance del recibo

Este documento se escribió después de los comandos observados para fijar la
evidencia ya producida. No es un log directo ni afirma haber existido antes de
las pruebas. No se repitió ninguna prueba para crear este recibo y no se abrió
el dataset H2 V2 real ni el output económico real.

Snapshot de workspace al archivar:

- `HEAD=31b609c5c34c5ea9fd17ff4ca0592d36a732e56f`.
- `audit_weekly_h2_ev_v2_independent.py`: 42.532 bytes, mtime UTC
  `2026-11-01T14:22:41.4403546Z`, SHA256
  `59bceca9b1c2c730946e3f506bc1ac20017fd8a04d4758475fd272071e0688db`.
- `test_audit_weekly_h2_ev_v2_independent.py`: 5.077 bytes, mtime UTC
  `2026-11-01T14:23:06.8905786Z`, SHA256
  `cbed9669a4a6ce36151eae82afbff497b61d2a7622533594af5caefc1007355c`.
- Ambos archivos estaban sin seguimiento (`??`) en este snapshot.

## Gate y ejecución sintética final observada

Variables de un hilo declaradas antes de pytest:

```text
OMP_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1
MKL_NUM_THREADS=1
NUMEXPR_NUM_THREADS=1
```

El wrapper Python fijó `psutil.Process().cpu_affinity([0])`, comprobó RAM
disponible mínima de 2.000.000.000 bytes y luego llamó a pytest sólo sobre el
archivo nuevo. Salida observada:

```text
CPU_AFFINITY [0] AVAILABLE_RAM 13175324672
.....                                                                    [100%]
5 passed in 1.22s
```

El quinto test construyó un paquete sintético completo mediante el evaluador V2
y exigió que la implementación independiente reconstruyera los once alphas, las
probabilidades, los medios con shrinkage 20, los scores, los 24 ledgers y sus
agregados. No fue una ejecución sobre datos reales.

## Comprobaciones estáticas posteriores observadas

Después del PASS se ejecutaron, sin modificar los archivos entre estas
comprobaciones y el cálculo de hashes:

```text
python -m py_compile <auditor> <tests>
python -m ruff check <auditor> <tests>
git diff --check -- <auditor> <tests>
```

Resultados observados:

- `py_compile`: exit 0, stdout/stderr vacíos.
- Ruff: exit 0, stdout `All checks passed!`, stderr vacío.
- `git diff --check`: exit 0, stdout/stderr vacíos.

## Incidente de harness conservado

El primer intento de añadir el test integral terminó con `4 passed, 1 failed`:
el helper sintético intentó escribir `dataset/candidates.jsonl` antes de crear
el directorio temporal `dataset`. Sólo se añadió `dataset.mkdir()` al test; el
código del auditor no cambió por ese fallo. La ejecución siguiente fue el PASS
de cinco pruebas transcrito arriba.

## Logs directos

No se redirigieron stdout/stderr a archivos durante estos comandos. Por tanto no
existen logs directos que puedan copiarse o rehashearse; las salidas anteriores
son una transcripción post hoc de resultados observados en la sesión. Los hashes
de código y tests, tamaños, mtimes y commit se obtuvieron después sólo mediante
lecturas, sin repetir pytest ni Ruff.
