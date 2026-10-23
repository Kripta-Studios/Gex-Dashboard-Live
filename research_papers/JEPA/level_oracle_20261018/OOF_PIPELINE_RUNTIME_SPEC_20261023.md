# Wrapper OOF: contrato operativo previo a implementación

2026-10-23. Implementa el diseño publicado `5c63dc2c`; no autoriza runtime real.
Sólo archivos nuevos; productores y auditor económico permanecen congelados.

Se fija **una raíz de corrección compartida** para los seis meses, compatible
con la request FULL_H1 del auditor existente. Raíces separadas por mes producirían
los mismos cálculos pero no esa interfaz. Cada recibo liga el inventario acumulativo
exacto de outputs; las fases posteriores sólo añaden archivos de sus cierres.
Un resume compara el árbol presente contra el último recibo, rechaza huérfanos y
vuelve a verificar todos los cierres previos. No altera cálculos para simplificar I/O.

La CLI será `--request <JSON> --request-sha256 <SHA externo> [--resume]`.
Request versión OOF_PIPELINE_RUNTIME_REQUEST_V1, status REVIEWED_OOF_PIPELINE_RUNTIME_REQUEST,
runtime_authorized=true, months exactamente 202601..202606, código completo con
hashes externos, rutas absolutas monthly_root/session_root, monthly_audit y
session_audit con SHA, pipeline_root/correction_root y seis evaluation_roots.
El request se revisa/publica externamente antes de ejecución; construirlo o calcular
su hash no es autorización. Debe usar el lock global fijo del wrapper, no uno elegible.
Los outputs son disjuntos de fuentes/código/autoridades y entre sí.

El wrapper admite la auditoría mensual compuesta antes de operar. Exige calendario
auditado 202501..202606 y binding de roots, fuente, índice y contrato; no usa una
revisión de código como auditoría de outputs. Código y autoridades se rehashean
antes/después de cada fase. Cada fase crea un MonthlyInputs nuevo; source.used
no se hereda entre calibración, replay o meses.

Un lock global cubre toda la secuencia además de locks de cada productor. Se exige
RAM y commit libres >=2.000.000.000 bytes antes de admisión y de cada fase. Gate
fallido aborta conservando evidencia, sin espera/retry automático. Meses seriales:
corrección -> recibo de cierre -> replay con ese SHA -> recibo. Corrección usa sólo
meses anteriores; replay conserva seis políticas fijas y jamás llama al auditor.

Cada fase tiene inicio inmutable antes de ejecutarse y recibo sólo después de
verificar cierre, dependencias, inputs y todos sus outputs. Recibos encadenan SHA
previo y contienen inventario acumulado. Resume explícito acepta únicamente fases
completas con recibo verificable y contenidos exactos; un inicio sin recibo, cierre
sin recibo, parcial, archivo extra o mutación falla preservado. Nunca adopta salidas
huérfanas ni borra locks por PID. Un fallo entre fases puede reanudarse sólo si no
hay fase parcial y todo el prefijo completo se revalida. El cierre exitoso es
PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT, nunca PASS económico.

Se conservan request/contrato, inicios, recibos, fallo y cierre; no se sobrescriben.
El cierre lista SHA de corrección/replay por mes para que el coordinador prepare
y publique separadamente la request del auditor. No emite aprobación ni autoejecuta
auditor con un SHA futuro calculado localmente. Technical_ready y promoción false.

Las pruebas serán sintéticas: ciclo con productores reales y frontera fuente
sintética, locks, hashes/roots, instancias frescas, recursos, inventario compartido,
huérfanos, interrupciones, fallos y resume de prefijos completos. No mercado ni fit.
El rendimiento de esas fixtures no estima duración o memoria histórica.

Los recibos registran duración, RSS observado al inicio/final de fase (no pico),
new_output_bytes de los archivos añadidos y cumulative_output_bytes de todos los
outputs. Son bytes de payload, no I/O físico; excluyen locks y recibos/logs del
pipeline. Un completion global sólo se admite con12recibos completos y payload
exacto reconstruido antes de cualquier nueva fase; nunca legitima un prefijo.
Cada realized histórico se verifica contra record_sha256 de training_records
del calibration sellado, con identidad/selección/modelo/predicción/labels y
disponibilidad concordantes, antes de emitir el recibo que habilita replay.

## Interfaz exacta

```powershell
python research_papers/JEPA/level_oracle_20261018/run_oof_calibrated_pipeline.py --request <ruta-absoluta.json> --request-sha256 <SHA-externo-revisado>
# Sólo para un prefijo íntegro revalidable:
python research_papers/JEPA/level_oracle_20261018/run_oof_calibrated_pipeline.py --request <misma-ruta.json> --request-sha256 <mismo-SHA> --resume
```

Campos de request, sin valores de runtime reales en esta especificación:

```json
{
  "version": "OOF_PIPELINE_RUNTIME_REQUEST_V1",
  "status": "REVIEWED_OOF_PIPELINE_RUNTIME_REQUEST",
  "runtime_authorized": true,
  "months": ["202601", "202602", "202603", "202604", "202605", "202606"],
  "coordination_lock": "D:/GexResearchArtifacts/level_oracle_20261018/oof_pipeline_runtime.lock",
  "code": {"<cada miembro exacto de dependencies()>": "<SHA256 publicado y revisado>"},
  "monthly_root": "<ruta absoluta>",
  "session_root": "<ruta absoluta>",
  "monthly_audit": {"path": "<ruta absoluta>", "sha256": "<SHA externo>"},
  "session_audit": {"path": "<ruta absoluta>", "sha256": "<SHA externo>"},
  "pipeline_root": "<raíz nueva de recibos>",
  "correction_root": "<raíz nueva compartida>",
  "evaluation_roots": {
    "202601": "<raíz nueva enero>", "202602": "<raíz nueva febrero>",
    "202603": "<raíz nueva marzo>", "202604": "<raíz nueva abril>",
    "202605": "<raíz nueva mayo>", "202606": "<raíz nueva junio>"
  }
}
```

`dependencies()` enumera las ocho dependencias del replay y los nueve miembros
EXTRA_CODE del wrapper, eliminando duplicados; la request debe contener el mapa
completo exacto. Incluye wrapper/tests/spec, diseño runtime, auditor/tests/spec/diseño
y revisión independiente del auditor. Además se exigen los cuatro pins literales
de los tres productores y el auditor, sin opción CLI de sustituirlos.

El lock global es único aunque cambien los roots de la request. Pipeline_root
contiene request.json (bytes exactos originales), contract.json, starts/00..11.json,
receipts/00..11.json, failures/<timestamp_ns>.json y completion.json final.
La duración de fase incluye publicación del inicio, admisión MonthlyInputs,
productor y verificación del cierre, hasta preparar el recibo. No mide el tiempo
de admisión inicial ni el rehash de todo el prefijo realizado durante resume.
