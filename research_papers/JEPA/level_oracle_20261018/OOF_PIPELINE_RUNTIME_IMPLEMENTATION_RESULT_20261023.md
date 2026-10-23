# Wrapper OOF: recibo de implementación

23 de octubre de 2026. Se añadieron `run_oof_calibrated_pipeline.py`,
`test_run_oof_calibrated_pipeline.py` y `OOF_PIPELINE_RUNTIME_SPEC_20261023.md`.
Este recibo registra trabajo del implementador; no es revisión independiente
ni autorización para ejecutar mercados.

El wrapper exige una request revisada con SHA externo, autoridades mensuales y
SessionClock, código fijado y raíces disjuntas. Mantiene una raíz de corrección
compartida compatible con el auditor H1, inventarios acumulativos exactos, lock
global de secuencia y una instancia nueva de MonthlyInputs por fase. El resume
sólo acepta fases completas con recibos y cierres revalidados. Un parcial o cierre
sin recibo queda preservado y bloquea el avance. No invoca el auditor final;
su cierre es `PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT`.

## Validación del implementador

| Pase | Resultado | Alcance de los bytes probados |
|---|---|---|
| Inicial | 19 PASS, 72,52 s | Antes de las correcciones W1, W2 y W3 |
| Tras correcciones | 22 PASS, 70,28 s | W1, W2 y W3 y sus pruebas negativas |
| Final | **22 PASS, 86,26 s** | Bytes finales, cronómetro completo y especificación de CLI/request |

El gate del pase final midió **8.952.373.248 bytes de RAM disponible** y
**11.352.576.000 bytes de commit libre**, ambos por encima de 2.000.000.000 bytes.
Ruff, formato y compilación: PASS. La suite se invocó mediante un wrapper Python
que llamó primero a `resource_gate()` y después a:

```python
pytest.main([
    "-q", "-p", "no:cacheprovider",
    "research_papers/JEPA/level_oracle_20261018/test_run_oof_calibrated_pipeline.py",
])
```

También se ejecutaron `python -m ruff format`, `python -m ruff check` y
`python -m py_compile` sobre los dos archivos Python nuevos. Las fixtures usan
productores congelados sobre evidencia sintética pequeña, con la frontera de
fuentes sustituida explícitamente. Incluyen seis meses, parada entre fases,
resume, mutaciones, locks, hashes, recursos y conservación de fallos. No son una
evaluación histórica ni un benchmark representativo de su duración o memoria.

## Hallazgos de revisión corregidos

- **W1:** se añadieron RSS observado al inicio y final de fase, bytes de outputs
  nuevos y bytes acumulativos. No se mide ni afirma un pico de RSS. Los bytes son
  payload de archivos de salida, no E/S física; excluyen locks y recibos/logs.
  La duración incluye la admisión MonthlyInputs, el productor y la comprobación
  de cierre; no incluye admisión inicial ni rehash del prefijo durante resume.
- **W2:** un completion global sólo es admisible tras los doce recibos y con
  payload exacto. La fixture inserta un cierre prematuro tras el primer recibo
  y exige rechazo sin crear otra fuente ni ejecutar una fase nueva. También
  rechaza un cierre global alterado después de las doce fases.
- **W3:** cada realized histórico se verifica contra el SHA de training_records
  en la calibración sellada, incluyendo sus bindings de identidad, selección,
  modelo, predicción, labels y disponibilidad. La prueba inyecta una mutación
  después del cierre del productor y antes del recibo; el wrapper falla antes
  del replay y rechaza adoptar ese parcial en resume.

El revisor `/root/oof_reviewer` comunicó CLEAR técnico independiente para los
hashes de abajo. Su mensaje reportó **4 PASS, 18 deselected, 7,88 s**, con gate de
RAM **7.882.018.816 bytes** y commit **11.287.461.888 bytes**, además de negativos
operativos propios. No duplicó la integral de seis meses. Esa evidencia es del
revisor, distinta de los tres pases del autor; su documento de revisión conserva
la autoridad y el detalle independientes. No se editaron código, tests o spec
estabilizados al escribir este recibo.

## SHA256 finales

| Archivo nuevo | SHA256 |
|---|---|
| run_oof_calibrated_pipeline.py | `26967e10c6b81cd5b84d7939bf6d0c81037934165daa91847d7ffd25de16ff57` |
| test_run_oof_calibrated_pipeline.py | `4daf9d662a63b125f2d451ea463558a00b35ebbd7a7c85d1c1b9145dfe6bf33e` |
| OOF_PIPELINE_RUNTIME_SPEC_20261023.md | `9b8d40296d515c28953b6b994c552560f159f6b8be57f0177487dbff05987909` |

Los cuatro originales se rehashearon y siguen intactos:

| Archivo original | SHA256 |
|---|---|
| monthly_oof_calibration_adapter.py | `7b80cff43e3887a92e0f89be6daa863a670ccd72d22a0f4aeabd032a39479364` |
| oof_maximum_calibration.py | `19e922dd65855c4cd7e2ec9d482d477a328245bcf642eeeb7771985f247e20b5` |
| evaluate_oof_calibrated_policy.py | `eeaad06f5b862a3153f29e7eab579b19a35e182ab506cf1f59e65631e187e716` |
| audit_oof_calibrated_policy.py | `e7481fbe944a9ffadcf637e7a4b69cd8d636cdf50ae295426191db9d76b5d44b` |

No hubo ejecución real, fit, calibración real, auditoría económica real ni cambios
en producción. El implementador no hizo commit. La futura ejecución espera su
request revisada y publicada y las autoridades económicas previas completas.
2026 sigue siendo desarrollo visto; `winner_selected=null`,
`technical_ready=false` y `promotion_approved=false`.
