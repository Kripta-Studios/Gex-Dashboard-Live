# Verificación sintética OOF del 23 de octubre de 2026

Estado: **PASS_SYNTHETIC_OOF_FIXTURE_RERUN**, 23 pruebas aprobadas, exit0.
Se completa el rerun independiente pendiente de la
[revisión del 18 de octubre](OOF_CALIBRATED_POLICY_INDEPENDENT_REVIEW.md).
Esa revisión y su JSON conservan sus bytes, estado y autorización originales;
este informe añade evidencia posterior y no los sustituye.

## Alcance y ejecución

Por la nueva orden de continuar la investigación local y usar subagentes, el
agente `common_greek_resume` ejecutó solamente las fixtures del adaptador y del
evaluador OOF. Leyó previamente ambas especificaciones, la revisión independiente
y los documentos de integración/diseño. Las pruebas construyen sus fuentes y
artefactos sintéticos en `tmp_path`; no consumen el mercado de `D:/ThetaData`,
modelos reales ni resultados mensuales reales.

Antes de importar pytest se consultó `GlobalMemoryStatusEx` mediante `ctypes` y
se exigieron al menos 2.000.000.000 bytes disponibles tanto de RAM como de commit.
Lectura del **2026-10-23 19:26:31.452913 UTC**:

| Recurso | Bytes disponibles |
|---|---:|
| RAM | 4.037.578.752 |
| Commit | 7.494.029.312 |

El gate pasó. Son lecturas de admisión, no picos ni mínimos durante la ejecución.
Se verificaron antes y después los ocho hashes de la revisión independiente:
**8/8 exactos**, sin cambios de implementación, tests o autoridades.

Entorno observado: Windows, Python **3.14.2**, ejecutable
`C:/Program Files/Python314/python.exe`. El proceso pytest recibió
`OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1` y `MKL_NUM_THREADS=1`.
Desde la raíz del repositorio se ejecutó:

```powershell
python -m pytest -q research_papers/JEPA/level_oracle_20261018/test_monthly_oof_calibration_adapter.py research_papers/JEPA/level_oracle_20261018/test_evaluate_oof_calibrated_policy.py
```

Salida final:

```text
23 passed in 28.73s
exit_code: 0
finished_utc: 2026-10-23T19:27:03.140112+00:00
```

Se ejecutaron las siete fixtures del adaptador y los dieciséis casos del
evaluador, incluyendo los casos parametrizados. No fue necesario corregir código
ni añadir tests. El resultado cubre las comprobaciones sintéticas de autoridad,
cortes temporales, sellado anterior a labels, recuperación, rechazo de cambios,
máximos negativos, WAIT/NO_FILL, calendario, medias sesiones y conservación de
estados visitados. Incluye la fixture que rechaza adoptar outputs existentes
cuando falta el contrato inicial.

## Identidad de los archivos comprobados

La revisión JSON tiene SHA256
`d1546c66df26fadf80052c43ae901f9e79056e91ccd389ac91844240910e6930`.

| Archivo | SHA256 antes y después |
|---|---|
| `evaluate_oof_calibrated_policy.py` | `eeaad06f5b862a3153f29e7eab579b19a35e182ab506cf1f59e65631e187e716` |
| `monthly_oof_calibration_adapter.py` | `7b80cff43e3887a92e0f89be6daa863a670ccd72d22a0f4aeabd032a39479364` |
| `oof_maximum_calibration.py` | `19e922dd65855c4cd7e2ec9d482d477a328245bcf642eeeb7771985f247e20b5` |
| `test_evaluate_oof_calibrated_policy.py` | `89516c51a5f467154549ce6d4b8b0a8dcec5482e58952dc89dbaa05a986c122b` |
| `test_monthly_oof_calibration_adapter.py` | `32e04b1444c73ac1a0bf87b819b6542ba4d96775202acb82514a147085d3739a` |
| `OOF_CALIBRATED_POLICY_EVALUATION_SPEC.md` | `7f88f18569d86ea936d0afdc4a485e461ccdf6c09d74feb835a026bee7caf3bc` |
| `MONTHLY_OOF_CALIBRATION_ADAPTER_SPEC.md` | `6bd989a6332fd21f751dc48ef084c5eba0f83b1f86f957f2a71127ef869bcb4e` |
| `OOF_CALIBRATED_POLICY_INDEPENDENT_REVIEW.md` | `4c9ac81da946414ee9d71f71a07798b214ca4862ce8319ca247bd9c9f08fdb61` |

## Límites y dependencias que permanecen

Este PASS acredita exclusivamente estas pruebas sintéticas. No hubo entrenamiento,
inferencia de modelos de mercado, calibración real, replay económico real, acceso
API, captura ni cambio de producción. No constituye auditoría de los outputs
mensuales ni evidencia de rentabilidad temporal.

`runtime_authorized=false` permanece intacto en la revisión original. Antes de
una ejecución OOF real siguen pendientes las autoridades de outputs mensuales
completos/auditados, el alcance autorizado de los fits base de 2026, la revisión
operativa y el auditor económico independiente de la comparación OOF. Este
informe no satisface esas dependencias ni ejecuta la continuación del mensual.
2025 sigue siendo entrenamiento del calibrador y 2026 desarrollo previamente
visto; no se reclama un holdout histórico intacto o promoción.
