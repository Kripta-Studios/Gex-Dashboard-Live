# FLAGS64 frente a row-mixed: calendario completo de evaluación

Estado: preparación previa a inferencia row-mixed; 18 de octubre de 2026.
Este diseño sustituye únicamente la evaluación todavía no ejecutada de
`evaluate_tcn_row_mixed.py` (741 días de validación). No modifica sus bytes ni
el entrenamiento de cuatro épocas. Todos los resultados históricos son
DEVELOPMENT_SEEN. No se incorpora información de los resultados row-mixed para
elegir este calendario.

La nueva entrada `evaluate_tcn_row_mixed_calendar.py` requiere el cuarto epoch
COMPLETO, modelos/snapshots/normalizadores vinculados, revisión de implementación
y PASS del dataset SessionClock SHA
`678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9`.
No tiene función fit ni recalcula estadísticas TRAIN.

Validación 2025: las 250 sesiones NYSE × tres tickers = **750** días, incluidos
20250703, 20251128 y 20251224 × SPXW/SPY/QQQ. Test enero–junio2026: **369** días
esperados, 363 disponibles y las seis ausencias SPY/QQQ de 20260401/09/15.
No hay sesiones cortas en ese test. El gate universal exige FILLED diario en
todo el calendario esperado; las ausencias son NO_EVALUABLE, no éxitos.

Cada día usa el reloj auditado explícito: close_i=390 o210; estados60..375 o
60..195; liquidación máxima385 o205. Los tensores conservan tiempo físico/390,
tiempo restante contra el cierre real, 20 barras, todos los mapas/máscaras y las
33 action features originales. El lector SessionClock ya auditado valida los
cuatro archivos de features por su índice. Un adaptador añade sólo la interfaz
necesaria al `CheckedStore` FLAGS64; no cambia un valor ni normalizador.

El control de las 1.104 sesiones completas disponibles se copia exactamente de
`tcn_flags_v1`: clave `variant`, dtype y bytes numéricos preservados; mismos
action_ids, sidecars, manifests y auditor económico FLAGS64. No se sustituye por
el TCN anterior ni se recalculan esas predicciones. Para los nueve días cortos
se realiza **inferencia nueva del modelo FLAGS64 de cuarta época**, con sus
normalizadores originales y `inference_exact` (unique/inverse, batches originales,
multiplicación float32 antes de asignación float64). La procedencia distingue
`AUDITED_FULL_COPY` de `NEW_SHORT_INFERENCE`.

La variante utiliza únicamente el cuarto epoch row-mixed sellado; misma
inferencia exacta y mismos inputs que el control corto. Los scores diarios se
publican y sellan antes de abrir labels de ese día. Reanudación verifica scores,
inputs, modelos y fuentes; no cambia scores ni adopta un NPZ huérfano.

Se conservan literalmente las seis políticas control/variant × umbral{0,5,10}
USD, comparación estricta `>`, ranking causal, desempate action_id, exclusión
de solapamientos, NO_FILL sin reemplazo de acción en ese minuto, costes/salidas
del motor y selector `select_validation` congelado. El scheduler original sólo
consume acciones ofrecidas; una validación adicional rechaza estados posteriores
al límite del reloj y fills posteriores a su EOD, evitando que su tolerancia
original de385 admita accidentalmente un cierre corto incorrecto.

Se evalúa íntegramente2025 antes de seleccionar. Entre candidatas con cobertura
diaria total se maximiza suma por ticker de PnL base dividido por escala TRAIN;
desempate control primero y umbral menor. Si ninguna cumple: selected_policy=null,
las seis quedan congeladas para diagnóstico. Freeze nuevo ligado a modelos,
calendario750, fuentes, predicciones2025 y código **antes** de abrir scores test
originales o producir cualquier score/ledger test de esta nueva entrada. Se
informan las seis políticas, comparación pareada al mismo umbral y selección
congelada. Ninguna reselección por test, ticker, mes o época.

Salida separada `tcn_row_mixed_calendar_v1_evaluation`; el root viejo741 permanece
sin ejecución. El nombre de archivo heredado `expected_full_calendar.csv` dentro
del root nuevo contiene aquí **todas** las fechas y se acompaña de
`session_calendar.json` con close_i y alcance explícito. Es compatibilidad de
interfaz; el contenido y el freeze son los del calendario completo.

Fixtures sintéticos requieren: cierre210/390, rechazo de acciones/exits fuera
de sesión, identidad exacta de scores full y recuperación, short nuevo sellado
antes de labels, shape/máscaras intactos, selector750, freeze antes test/null,
mutaciones y cierre/resume sin inferencia repetida. No ejecutar estos tests ni
inferencia con menos de2.000.000.000 bytes reales libres de RAM/commit; CPU4 y
capacidad de caché de un día. No nuevas métricas ni lectura de pesos row-mixed
antes de `training_complete.json` de época4 y revisión del runner.
