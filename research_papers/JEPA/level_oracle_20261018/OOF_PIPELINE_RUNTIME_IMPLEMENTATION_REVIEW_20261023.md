# Revisión independiente del wrapper OOF

23 de octubre de 2026. **CLEAR — PASS_OOF_PIPELINE_RUNTIME_IMPLEMENTATION_REVIEW**.
Alcance **IMPLEMENTATION_ONLY**; `runtime_authorized=false`,
`technical_ready=false`, `promotion_approved=false`.

Revisor: `/root/oof_reviewer`; autor: `/root/scientific_review`. Se inspeccionaron
el flujo real de admisión, fases, cierres, inventarios y reanudación, las APIs de
los productores congelados y su compatibilidad con el auditor H1. El revisor no
modificó código o especificaciones existentes ni ejecutó mercado, fit, inferencia
base o auditoría económica real.

## Hallazgos resueltos

- **W1 — recursos y bytes:** faltaba RSS y el único campo de bytes volvía a contar
  outputs anteriores. Ahora constan RSS observado al inicio/final, sin afirmar
  pico, y bytes nuevos/acumulativos separados. Son bytes de payload; no E/S física.
  La duración incluye admisión MonthlyInputs, productor y comprobación del cierre.
- **W2 — cierre prematuro:** un `completion.json` existente podía admitir un
  prefijo incompleto y permitir fases nuevas antes de fallar. Ahora sólo se admite
  con doce recibos y payload final exacto, comprobado antes de avanzar.
- **W3 — realized histórico:** antes se comprobaba existencia, pero no el hash
  ya fijado en `calibration.training_records`. Ahora se verifican SHA e identidad,
  selección, modelo, predicción, labels y disponibilidad antes del recibo que
  habilita el replay.

Los tres hallazgos están resueltos en los hashes de abajo. No quedan hallazgos
bloqueantes identificados.

## Verificación propia y del autor

El revisor ejecutó **4 pytest PASS, 18 deselected, 7,88 s**, tras un gate real de
RAM **7.882.018.816 bytes** y commit **11.287.461.888 bytes**. Se llamó a
`resource_gate()` y después a `pytest.main` con estos argumentos:

```text
-q research_papers/JEPA/level_oracle_20261018/test_run_oof_calibrated_pipeline.py -k "crash_after_producer or resource_rejection or no_final_auditor"
```

Cubren interrupción después del cierre del productor, mutación de realized antes
del recibo, rechazo de recursos antes de escribir y ausencia de invocación del
auditor final. Los dos casos de fallo posterior al productor también comprueban
que no se adopta una salida sin recibo mediante resume.

En un run sintético adicional de **sólo la corrección de enero**, el revisor
comprobó que un completion prematuro se rechaza sin crear otra fuente ni fase;
que un segundo lock global falla; y que se rechazan siete errores de request:
SHA externo, hash de código, root solapado, lock sustituido, meses incompletos,
SHA mensual y ruta relativa. También verificó RSS positivo y bytes nuevos iguales
al acumulado en la primera fase. El gate previo midió RAM **7.962.210.304 bytes**
y commit **12.144.541.696 bytes**. Estas comprobaciones ad hoc son separadas de
los cuatro casos de pytest; usaron una frontera de fuentes explícitamente sintética.

El [recibo del autor](OOF_PIPELINE_RUNTIME_IMPLEMENTATION_RESULT_20261023.md),
SHA `445127f5e0c8fef84118b1b5dce70d564828e42eb1fb6e8f833b2ed9b87b332a`,
informa **22 PASS, 86,26 s** para los bytes finales, con gate RAM
8.952.373.248 y commit 11.352.576.000 bytes, y Ruff/formato/compile PASS. Sus
pases anteriores fueron 19/72,52 s antes de los fixes y 22/70,28 s antes del ajuste
final de cronómetro/spec. **El revisor no repitió la integral de seis meses ni la
suite completa de 22**; su evidencia está atribuida al autor, no al revisor.
No se repitieron tests para redactar este recibo final.

## Flujo revisado

La request liga externamente código y autoridades. Se exige autoridad mensual
compuesta 202501–202606, junto a SessionClock, contrato e índice concordantes.
La raíz de corrección compartida conserva un inventario acumulativo compatible
con el auditor FULL_H1; las seis raíces de replay y la raíz de recibos son
disjuntas. Cada fase instancia MonthlyInputs de nuevo, evitando que `source.used`
herede lecturas de labels del replay anterior.

Un lock global fijo cubre la secuencia, además de los locks de productores.
Los recibos encadenados sólo se publican después de comprobar cierres, hashes,
inputs y outputs. El replay recibe el SHA del cierre de corrección ligado a su
recibo. Resume exige un prefijo completo y revalidado; no adopta inicios sin
recibo, parciales, cierres huérfanos o archivos mutados. Los fallos se conservan.
El wrapper no ejecuta el auditor ni selecciona una política; su cierre sólo
declara `PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT`.

## Bytes finales y dependencias

| Archivo revisado | SHA256 |
|---|---|
| `run_oof_calibrated_pipeline.py` | `26967e10c6b81cd5b84d7939bf6d0c81037934165daa91847d7ffd25de16ff57` |
| `test_run_oof_calibrated_pipeline.py` | `4daf9d662a63b125f2d451ea463558a00b35ebbd7a7c85d1c1b9145dfe6bf33e` |
| `OOF_PIPELINE_RUNTIME_SPEC_20261023.md` | `9b8d40296d515c28953b6b994c552560f159f6b8be57f0177487dbff05987909` |

Los cuatro pins originales se rehashearon y permanecen intactos:

| Archivo congelado | SHA256 |
|---|---|
| `monthly_oof_calibration_adapter.py` | `7b80cff43e3887a92e0f89be6daa863a670ccd72d22a0f4aeabd032a39479364` |
| `oof_maximum_calibration.py` | `19e922dd65855c4cd7e2ec9d482d477a328245bcf642eeeb7771985f247e20b5` |
| `evaluate_oof_calibrated_policy.py` | `eeaad06f5b862a3153f29e7eab579b19a35e182ab506cf1f59e65631e187e716` |
| `audit_oof_calibrated_policy.py` | `e7481fbe944a9ffadcf637e7a4b69cd8d636cdf50ae295426191db9d76b5d44b` |

El [recibo JSON](OOF_PIPELINE_RUNTIME_IMPLEMENTATION_REVIEW_20261023.json) fija
el mapa completo de **17 dependencias**, idéntico a `dependencies()` del wrapper:
incluye calendario, diseño runtime, autoridades metodológicas, auditor/tests/spec
y revisión independiente anterior. El recibo del autor se fija aparte como
evidencia documental; no se añade a los 17 miembros del contrato runtime.

## Dependencias pendientes

Este CLEAR permite publicar la implementación revisada. La ejecución real sigue
pendiente de cierres mensuales completos y auditoría externa compuesta de los
18 meses, y de la request runtime revisada/publicada con su SHA externo, mapa
exacto y raíces nuevas. La decisión de ejecución corresponde al coordinador,
respetando el gate mínimo de 2 GB de RAM y commit antes de cada fase y la
coordinación con los trabajos pesados.

Después de una futura ejecución del wrapper, la auditoría económica requerirá
su propia request y hashes externos revisados/publicados. Este recibo no los
genera ni los autoriza. 2025 es TRAIN del calibrador; 2026 sigue SEEN_DEVELOPMENT.
Rentabilidad causal NOT_DEMONSTRATED; `winner_selected=null`. No se autoriza
producción ni promoción.
