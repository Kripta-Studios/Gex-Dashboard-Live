# Especificación del auditor mensual H1 2026 dado scores sellados

Fecha2026-10-23. Implementación nueva de la frontera descrita en
`MONTHLY_TEST_AUDIT_EXTENSION_DESIGN_20261023.md`, conservado como diseño previo.
No se modifican productor, auditor2025 ni contratos anteriores. No hay ejecución
de mercado ni PASS económico de esta extensión al publicar este archivo.
La continuación general está autorizada por el usuario; el coordinador secuencia
cargas pesadas y exige cerrar/auditar2025 antes de preparar runtime2026.

## Autoridades y admisión

`audit_monthly_walk_forward_test.py` reutiliza exclusivamente el auditor2025
independiente para muestras/targets/matrices, scheduler y economía. No importa
el productor mensual, su calendario/selector, LightGBM ni entrenadores. Los seis
archivos de `dependencies()` incluyen ambos auditores, sus fixtures y sus dos
contratos; una revisión nueva fija exactamente esos hashes con status
`PASS_MONTHLY_TEST_AUDITOR_IMPLEMENTATION_REVIEW`.

La revisión de runtime, status `PASS_MONTHLY_TEST_AUDIT_RUNTIME_REVIEW`, contiene
`scope=VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1`, las mismas dependencies y
`allowed_read_roots`: directorios absolutos acotados que cubren únicamente las
autoridades, el código y la evidencia científica referenciada. No se admiten
raíces de volumen. Su binding contiene rutas monthly_root, source_audit,
validation_audit, session_root y SHA256 de auditoría2025, revisión de
implementación, contrato científico, auditoría de fuente, índice y freeze2025.
El SHA2025 también se pasa externamente por CLI; no se deriva del input para
autoautorizarlo. El contrato de mercado original sigue siendo
`7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f`;
fixtures usan autoridades sintéticas separadas, nunca ese root real.

La admisión exige2025 auditado con doce meses,24ventanas,750ticker-días,
reconstrucción de selección/informe y su inventario de archivos. Rehashea todo
ese inventario y exige inclusión explícita de contrato, fuente/índice, freeze,
report2025, cierres mensuales y metadata/modelos de las24ventanas. Rutas no
absolutas, traversal, hashes contradictorios o referencias fuera de las raíces
revisadas fallan antes de labels nuevos. Se valida el contrato de fuente y los
once snapshots originales con las primitivas independientes existentes.

## Reconstrucción nueva

Enero–junio2026 conserva static TRAIN2023–24 y agrega seis fits expanding desde
20230101 hasta el primer día del mes evaluado, exclusivo, y seis rolling12 desde
ese mes del año anterior hasta el mismo corte. Static se hereda de2025 con sus
bytes, metadata y escalas; no se reconstruye ni refittea de nuevo. Se comprueban
12fits nuevos,13modelos utilizadosH1,36ventanas totales y tres fit_keys por mes.

Cada fit nuevo debe comenzar después del freeze2025 y cerrar después de su
fit_started. Sus muestras por identidad, pesos IPW, unión con labels, escalas
TRAIN, targets, orden de chunks y matriz1954 se reconstruyen independientemente.
Los díasTRAIN pertenecen a [inicio,corte); los relojes de labels se comprueban
dentro de cada sesión, sin overnight, mediante el auditor independiente.
La comparación de valores de features es chunks↔matriz; los archivos fuente
se autentican por hash, sin reconstruir los chunks desde esos arrays ni desde
raw. No se verifica de nuevo la semántica de disponibilidad de las features
fuente. Los scores deben ser vectores finitos float64; IDs/estados conservan
dtype entero, orden y valores de las acciones. Modelo y escala TRAIN escalares
deben coincidir exactamente. El modelo completo precede al cierre del NPZ y
éste al sello mensual conjunto. No se reinfiere el modelo.

Antes de nuevos labels se exige el cierre completo de seis meses, los tres
fit_keys de cada sello de predicciones, ambos informes y completion18meses/
36ventanas. El auditor reproduce después scheduler, attempts, ledgers, registros
diarios, economía mensual e informe2026. Todos los scores de cada mes deben estar
sellados antes de sus ledgers y después del freeze2025. Sólo score>0, empate
menoraction_id, WAIT/NO_FILL+1 y FILLED hastaexit+1. No hay fills forzados, costes
adicionales, tuning ni selección2026. El selected_mode2025, incluido null,
permanece idéntico y se contrasta en el cierre/report2026.

El índice debe conservar2625identidades,2619disponibles;2025tiene750disponibles.
H1contiene369identidades,123por ticker,363disponibles y6ausentes exactamente
según ese índice sellado, sin cierres cortos en evaluación. Sesiones cortas
close_i210 sí pueden entrar en TRAIN y son parte de fixtures. Los ceros
estructurales de MISSING_SOURCE en daily.json se reproducen sin tratarlos como
PnL observado. Sólo COMPLETE contribuye a economía/actividad;
missing_day_economics=null y cobertura universalNO_EVALUABLE_MISSING_SOURCE.

## CLI y resultado

```text
audit_monthly_walk_forward_test.py
  --monthly-root <root original>
  --source-audit <audit SessionClock>
  --validation-audit <audit2025 completo>
  --expected-validation-audit-sha256 <hash externo>
  --implementation-review <review exacta nueva>
  --runtime-review <binding externo de fuentes/código/raíces>
  --output <root nuevo e inexistente>
```

Un verificador central aplica las raíces de lectura a toda referencia, incluidos
los paths dentro de feature_inputs; no basta validar los paths del índice.
El output no puede solapar root científico, código, dataset ni day_root referenciado. Se crea una raíz
nueva con bloqueo del sistema operativo, snapshots fsync de dependencias y
launch.json previo a reconstrucción, y copias de las dos revisiones nuevas.
Un intento interrumpido se preserva y no
se adopta silenciosamente. Se publica failure.json si falla la reconstrucción;
no se publica PASS parcial. La admisión fallida antes de abrir la raíz no genera
un resultado económico. Todos los inputs leídos, snapshots y código se
rehashean antes del cierre.

El cierre compuesto usa el status existente
`PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES` y el scope
explícito2025+H12026. Contiene binding con completed_months202501..202606,
prior_validation_audit con ruta/SHA y declaración de reconstrucción heredada,
verified_files con unión sin conflictos de evidencia2025/2026, y audited con
conteos/identidades/checks nuevos. La autoridad2025 se rehashea, no se presenta
como una segunda reconstrucción. El contrato de campos permite que
MonthlyInputs real admita predicciones y ledgers de ambos periodos; el próximo
runtimeOOF debe fijar externamente el hash del cierre compuesto.

Este PASS no autoriza promoción ni demuestra rentabilidad futura. No refittea,
reinfiere, reconstruye rawquotes ni acredita recepción/live.2026 sigue siendo
desarrollo visto; los timestamps de artefactos acreditan orden de sellos de
replay, no publicación histórica. El calibrador y su replay económico conservan
su propia frontera de implementación, runtime y auditoría.

## Verificación exclusivamente sintética

La fixture completa usa el calendario de2625identidades y una acción artificial
por día disponible, modelos de texto sintético nunca inferidos y una autoridad
2025 sintética fijada externamente. Reconstruye todos los seis meses/12fits de
la extensión, preserva null, incluye los seis ausentes y consume el cierre con
MonthlyInputs real para enero/junio2026 y una predicción heredada2025. No afirma
haber ejecutado la auditoría2025 dentro de esa fixture.

Se añaden pruebas negativas de cortes, autoridad/hash, selección/cierres,
identidad de modelo/score, calendario, scheduler, fuentes tardíamente alteradas,
salida parcial/concurrencia y ausencia de imports del productor. Las pruebas se
ejecutan sólo con >=2.000.000.000bytes libres de RAM y commit enWindows. La
revisión independiente debe inspeccionar bytes finales y resultados de fixtures
antes de emitir revisión de implementación. Este documento no es ese recibo.
