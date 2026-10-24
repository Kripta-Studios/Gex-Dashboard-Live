# Extensión H1 2026 sobre el lector de índice V2

24 de octubre de 2026. Corrección técnica nueva; no cambia el experimento mensual.
Se preservan `audit_monthly_walk_forward_test.py`, sus pruebas y la
[especificación original](MONTHLY_TEST_AUDIT_EXTENSION_SPEC_20261023.md), así como
el auditor base original y sus autoridades. No se ejecuta mercado ni se emite
una revisión de runtime al preparar esta extensión.

## Motivo y alcance exacto

El lector original del auditor base construía `Path(value)` para las cuatro
rutas de features de todas las filas. Las seis filas MISSING_SOURCE del índice
sellado tienen rutas nulas: esa conversión falla antes de poder conservarlas
como no evaluables. La fixture original de la extensión les asignaba rutas de
relleno, por lo que no reproducía este formato real. No se corrige el índice ni
se inventan fuentes para superar el error.

`audit_monthly_walk_forward_test_index_v2.py` copia la extensión original y cambia
únicamente el import del auditor independiente, `dependencies()`, el nombre de
esta especificación y los identificadores de revisión de implementación/runtime.
Importa `audit_monthly_walk_forward_index_v2` con su API original. Ninguna función
económica, selector, corte temporal, scheduler, agregación, tolerancia o control
de cierres cambia en esta extensión. Una prueba compara el AST completo salvo
esa lista explícita de cambios; también fija los hashes de la extensión y las
pruebas originales.

El lector V2 conserva `SourceDay.feature_paths` como cuatro `Path` para COMPLETE
y `None` para MISSING_SOURCE. Su
[especificación](MONTHLY_WALK_FORWARD_INDEX_AUDIT_V2_SPEC_20261024.md) regula la
validación del índice: COMPLETE con rutas y hashes válidos; las seis ausencias
con cuatro rutas nulas, hashes features/actions/labels nulos y
`evaluation_status=NO_EVALUABLE`. La extensión continúa leyendo sidecars,
predicciones y ledgers sólo para días disponibles, como ya hacía su núcleo.

## Autoridad nueva, economía conservada

La revisión de implementación requerida es
`PASS_MONTHLY_TEST_INDEX_V2_AUDITOR_IMPLEMENTATION_REVIEW`; la revisión de runtime
separada es `PASS_MONTHLY_TEST_INDEX_V2_AUDIT_RUNTIME_REVIEW`. El contenido de
`dependencies()` debe coincidir exactamente en ambas. Incluye trece archivos:
los nuevos auditores base/extensión con sus pruebas y especificaciones; los dos
auditores originales con sus pruebas y contratos/especificaciones; y la revisión
original del auditor base. La revisión original queda preservada como evidencia,
sin conceder autoridad automática a los nuevos bytes.

La CLI conserva los siete argumentos de la extensión original: `--monthly-root`,
`--source-audit`, `--validation-audit`, `--expected-validation-audit-sha256`,
`--implementation-review`, `--runtime-review` y `--output`. El hash de cierre
2025 se suministra externamente. Siguen exigidos su inventario rehasheado, doce
meses, 24 ventanas, 750 ticker-días, selección e informe reconstruidos. Este
documento no sustituye ese cierre ni autoriza crear un runtime con evidencia
incompleta.

Permanecen: seis meses H1; doce fits nuevos expanding/rolling12; trece modelos
usados contando static heredado; 36 ventanas totales; freeze previo a test;
`selected_mode` incluso null; tres fit_keys por mes; IDs/dtypes/scores exactos;
modelos completos antes del sello de predicción; reconstrucción de muestras,
targets, pesos y matrices; fuentes acotadas; salida nueva con bloqueo; snapshots
y rehash final. No se importan productor, selector, entrenador ni LightGBM.

H1 conserva 369 ticker-días, 363 disponibles y seis ausencias. Sus ceros diarios
son representación estructural, nunca PnL observado. El informe mantiene
`missing_day_economics=null`, `NO_EVALUABLE_MISSING_SOURCE` y requisito diario
insatisfecho sobre el calendario universal. No se fabrican predicciones, intentos
o ledgers para las seis ausencias. No cambian los costes ni las reglas de entrada
y salida.

## Verificación sintética prevista

La nueva fixture completa conserva el calendario de 2.625 identidades, una
acción artificial por día disponible, modelos de texto y autoridad 2025
explícitamente sintética. Añade los campos de hash/evaluation_status del índice
y genera realmente cuatro rutas y seis hashes nulos en sus seis MISSING_SOURCE.
La reconstrucción de seis meses y doce fits debe terminar con 369/363/6, sin
añadir economía missing. El modo expanding artificial suma 363 USD base;
static/rolling12 no operan y la selección heredada permanece null.

Se conserva la prueba con `MonthlyInputs` real para comprobar el contrato de
salida compuesto. Se añade reproducción del fallo original `Path(None)` y
comprobación de que el constructor V2 devuelve `feature_paths=None` en las seis
ausencias. Las pruebas previas de cortes, fuentes, metadata, dtypes, calendario,
freeze, output y scheduler se copian sin cambiar su propósito. Se exige al menos
2.000.000.000 bytes disponibles de RAM y commit antes de pruebas completas.

El status económico compuesto y sus campos siguen siendo compatibles:
`PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES`, scope
`VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1`. Un futuro PASS hereda la auditoría
2025; no afirma reconstruirla por segunda vez. Tampoco acredita refit, inferencia
repetida, recepción histórica, features reconstruidas desde raw, paridad live o
rentabilidad prospectiva. No se modifican wrappers, launchers, OOF ni modelos.
