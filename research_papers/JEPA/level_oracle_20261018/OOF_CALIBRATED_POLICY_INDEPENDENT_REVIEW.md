# Revisión independiente del adaptador y replay OOF

Estado: revisión estática sin hallazgos de código abiertos; rerun independiente
de pytest pendiente por memoria disponible inferior a2.000.000.000 bytes.
Esta revisión no autoriza ni acredita ejecución económica.

Se leyeron completos `monthly_oof_calibration_adapter.py`,
`evaluate_oof_calibrated_policy.py`, utilidad OOF, specs y fixtures, y se contrastó
el scheduler y formato de scores/ledgers con el runner mensual original.
No se abrió ningún dato de mercado, modelo o resultado real; no hubo fit,
inferencia, ejecución del adaptador ni detención de procesos.

La admisión exige un hash externo de auditoría mensual independiente y pertenencia
de los artefactos consumidos a su inventario. Los cortes exclusivos se contrastan
con los folds static/expanding/rolling12. El calibrador usa únicamente meses
cerrados anteriores al objetivo, con disponibilidad declarada cierreNYSE+1min;
esto no demuestra recepción histórica observada.2025 es entrenamiento del
calibrador y2026 desarrollo visto. Ningún procedimiento se elige por sus resultados.

Los máximos incluyen todos los estados ofrecidos, también scores negativos.
La selección estable ocurre antes de cargar labels; el offset es constante por
ticker/procedimiento/mes y mantiene el ranking. El evaluador reproduce primero
todos los controles con igualdad de bytes float64 para scores/payoffs y exactitud
de identidad/relojes/fill. Después sella autoridad y scores antes de cargar nuevos
labels. La política corregida recorre estados desde el inicio, incluyendo aquellos
que no visitó el control; no filtra únicamente trades anteriores. WAIT y NO_FILL
avanzan un minuto, sin alternativa del mismo estado; FILLED reanuda en exit+1 y
activa has_filled. Los límites usan close_i explícito210/390.

El calendario se conserva desde el índice auditado; el periodo completo exige
369 ticker-días,363 disponibles y6 missing. Missing mantiene métricas null y
NO_EVALUABLE, separado de un día observable sin operación. Los agregados por
ticker actuales informan cobertura; no se debe atribuirles una comprobación
económica por ticker que todavía no implementan.

Hallazgo corregido durante revisión: el evaluador podía adoptar una raíz con
outputs previos si faltaba su contrato inicial. Ahora, bajo el lock, una raíz sin
run_contract.json debe contener únicamente .lock; el rechazo precede a lectura
de controles/labels. El productor añadió una fixture que elimina contrato y
all_scores de una ejecución sintética previa y exige fallo antes de esas lecturas.
El adaptador ya aplicaba la misma regla para implementation.json.

Persistencia: lock exclusivo del sistema operativo, publicación temporal con
flush/fsync y rename, outputs inmutables, igualdad exacta al reanudar, dependencias
ligadas antes de labels y rehash final. La reanudación recalcula/verifica estados;
no es una promesa de recuperación de cualquier archivo perdido. Los contratos
ausentes o alterados fallan cerrado.

Ruff y compilación fueron comprobados independientemente y pasan. El productor
había informado7 fixtures del adaptador y15 del evaluador antes del ajuste; esos
resultados no se presentan como rerun independiente. Hay ahora16 fixtures del
evaluador y7 del adaptador por ejecutar al recuperar memoria. Las lecturas locales
de RAM durante esta revisión fueron aproximadamente0,86–1,16GB, por debajo del
umbral operativo pedido. No se repitieron fixtures con pandas/Arrow ni mercados.

Los hashes exactos finales están en
`OOF_CALIBRATED_POLICY_INDEPENDENT_REVIEW.json`. Antes de un runtime real siguen
pendientes la auditoría mensual de los outputs consumidos, la revisión de runtime
y el auditor económico independiente de esta comparación, además del rerun focal.
