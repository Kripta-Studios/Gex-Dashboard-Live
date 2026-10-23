# Diseño de auditoría mensual de desarrollo 2026

Fecha: 2026-10-23. Estado: **DISEÑO; SIN IMPLEMENTACIÓN NI EJECUCIÓN DE MERCADO**.
El usuario ha reanudado la investigación local y solicitado subagentes. Esa
instrucción autoriza continuar el trabajo pendiente, sin pedir permiso de nuevo
por cada etapa ya comprendida en el objetivo. Este documento prepara una
dependencia del trabajo OOF; no cambia el runner, contratos, reglas, modelos ni
resultados anteriores. La frontera pendiente es técnica: cerrar/auditar2025 y
publicar/revisar esta extensión y su runtime antes de ejecutar2026. El diseño
no sustituye esas comprobaciones. La continuación operativa de validación2025
conserva su wrapper y sus autoridades originales; el coordinador mantiene las
cargas pesadas secuenciales.

## Frontera que falta

`audit_monthly_walk_forward.py` termina en `audit_validation()`, reconstruye
enero–diciembre 2025 y rechaza otros años en `audit_period_report`. Su PASS
condicional a scores sellados no cubre enero–junio 2026. El adaptador
`monthly_oof_calibration_adapter.MonthlyInputs` exige autoridad mensual para
los meses pasados y para las predicciones del mes objetivo. Completar y auditar
2025 no basta para calibrar o evaluar 2026.

Se propone un auditor nuevo, `audit_monthly_walk_forward_test.py`, con su propia
especificación final, fixtures y revisión exacta antes de ejecutarlo. El nombre
`test` describe la partición del runner: todo 2026 sigue siendo
**SEEN_DEVELOPMENT**, nunca un holdout histórico intacto.

El alcance será reconstrucción independiente de muestras, matrices, targets,
pesos, calendario, scheduler y economía **dado los scores sellados**. No incluirá
refit LightGBM, reinferencia, reconstrucción de cotizaciones raw ni acreditación
de recepción histórica/live. Esas comprobaciones requieren otra auditoría
explícita; no se atribuyen a esta extensión.

## Dependencias de admisión

Antes de leer nuevos labels o métricas 2026, el auditor deberá exigir:

1. Auditoría de validación 2025 completa con status
   `PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES`, hash esperado
   fijado externamente en una revisión de runtime; doce meses exactos
   `202501`–`202512`, 24 ventanas únicas y 750 ticker-días.
2. Identidad del mismo `monthly_root`, contrato científico, raíz SessionClock,
   auditoría de fuente e índice. El contrato mensual actual es
   `7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f`.
   Su universo es 2625 ticker-días; 2619 disponibles y seis ausentes.
3. `validation_freeze.json` y su marker pertenecientes al inventario auditado
   2025, con hash igual al esperado. Mantener `selected_mode` incluso cuando
   sea `null`, así como las escalas comunes, las tres reglas de actualización,
   el desempate y los hashes de los doce registros diarios 2025.
4. Cierre completo de los seis meses 2026, `reports/2026` y `completion`, con sus
   markers válidos. Un mes aislado o una ejecución parcial no recibe PASS del
   semestre. El alcance no es un auditor incremental de mercado.
5. Revisión independiente exacta del auditor nuevo, fixtures y especificación;
   productor, sus once snapshots científicos y contrato permanecen inmutables.
   Registrar las autoridades operativas usadas para ejecutar la etapa test,
   sin convertir un overlay de recursos en auditoría científica.

La admisión rehashea el inventario de la auditoría 2025, rechaza rutas fuera de
las raíces declaradas y hashes contradictorios. No acepta únicamente el texto
PASS ni calcula el hash esperado del archivo recibido para autoautorizarlo.
El freeze debe preceder en el orden de artefactos a los nuevos fit_started y
predicciones 2026. Los relojes de publicación del replay no se presentan como
timestamps de publicación en 2025 o recepción real del mercado.

## Calendario y ventanas

Se reconstruyen estas ventanas mediante aritmética de calendario independiente,
sin importar `rolling_monthly_schedule.py` del productor:

| Mes evaluado | Expanding TRAIN [inicio, fin) | Rolling12 TRAIN [inicio, fin) |
|---|---|---|
| 202601 | [20230101, 20260101) | [20250101, 20260101) |
| 202602 | [20230101, 20260201) | [20250201, 20260201) |
| 202603 | [20230101, 20260301) | [20250301, 20260301) |
| 202604 | [20230101, 20260401) | [20250401, 20260401) |
| 202605 | [20230101, 20260501) | [20250501, 20260501) |
| 202606 | [20230101, 20260601) | [20250601, 20260601) |

Static reutiliza exactamente `train_20230101_20250101_exclusive`, ya auditado;
no se ajusta otra vez. Hay **12 fits nuevos**, 13 identidades de modelo utilizadas
en H1 incluyendo static, 18 ledgers lógicos modo-mes y 36 fits únicos en toda la
investigación mensual. Cada mes 2026 sella **tres fit_keys distintos**, no sólo
los dos nuevos de ese mes. El manifest conjunto debe incluir también static.

Cada fila TRAIN debe pertenecer a [inicio, fin); su outcome debe cerrar antes
del corte exclusivo y su feature estar disponible al decidir. Para febrero en
adelante se admiten meses 2026 ya cerrados sólo según estas ventanas fijas.
Se reconstruyen la muestra por identidad, IPW, escalas TRAIN por ticker,
targets net/escala, pesos y firmas de matriz con las mismas reglas originales.
Los 1954 canales y CONFIG siguen congelados; h no pasa a ser feature nueva.
Las sesiones cortas que entren en TRAIN conservan close_i=210. No hay sesiones
cortas de evaluación H1 2026, pero las fixtures deben cubrir esa semántica.

## Artefactos que se contrastarán

Todas las rutas siguientes son relativas a `monthly_walk_forward_v1`. Su lectura
exige pertenencia al marker/índice correspondiente y rehash antes y después.

| Artefacto | Comprobación requerida |
|---|---|
| `run_contract.json`, `executed_code/*` | Identidad del contrato y las once dependencias científicas |
| `fits/<fit_key>/inputs.json` y marker | Ventana, CONFIG, escalas, orden y mapa completo de inputs |
| `fits/<fit_key>/*` y `day_samples/*`, `day_chunks/*` | Reconstrucción de muestra, targets, IPW y firmas de la matriz |
| `models/<fit_key>.txt`, `.fit_started.json`, `.complete.json` | Modelo completo, hashes, dimensiones y orden temporal; no refit implícito |
| `feature_inputs/<ticker>/<date>.json` y marker | Procedencia de todos los arrays de features usados |
| `predictions/YYYYMM/<fit_key>/<ticker>/<date>.npz` y marker | IDs y estados exactos, orden, scores finitos float64, modelo y escala TRAIN |
| `months/YYYYMM/predictions.complete.json` | Los tres fits, todas las sesiones disponibles y sus manifests sellados antes de los ledgers |
| `ledgers/YYYYMM/<mode>/<ticker>/<date>_attempts.parquet` y `_ledger.parquet`, marker común | Reproducción independiente exacta de intentos, fills, estados, scores y payoffs |
| `months/YYYYMM/daily.json`, `economics.json` y markers | Calendario completo, agregados y pertenencia del cierre de dependencias |
| `reports/2025.json`, `reports/2026.json` y markers | 2025 inmutable; reconstrucción2026 por ticker y conjunta |
| `validation_freeze.json` y marker | Selección2025 inmutable, incluyendo null, sin reselección2026 |
| `completion.json` y marker | 18 meses, 36 ventanas, selected_mode y hashes exactos de ambos informes |

Las identidades de los seis ausentes se derivan del índice SessionClock sellado,
no se infieren a partir de trades ni se sustituyen por una lista ajustada al
resultado. Actions/labels se autentican contra ese índice antes y después de
cada lectura. Se distinguen los hashes del payload y de cada marker: ninguno
sustituye al otro.

## Reconstrucción del scheduler y economía

El auditor nuevo no importa el scheduler, selección ni resúmenes económicos
del productor. Puede reutilizar primitivas del auditor independiente anterior
si sus bytes quedan fijados en la revisión nueva y sus fixtures siguen pasando;
no delegará la reproducción al runner evaluado. No invocará `monthly.main()`
ni clases que produzcan modelos o predicciones.

Reconstruye desde todos los scores ofertados: score estrictamente mayor que
cero, máximo por estado y desempate por menor action_id. WAIT avanza un minuto;
NO_FILL registra el intento, devuelve cero y avanza un minuto sin rescatar otra
acción del mismo estado. FILLED bloquea hasta exit_i+1 y cambia
has_filled_before sólo tras el fill. Estados60..close_i-15; salida física entre
state_i+2 y close_i-5. Se contrastan identidad contractual y timestamps ya
contenidos en los sidecars, base/adverso, duración, motivo y ausencia de solapes.
No se cobran otra vez los costes de labels ni se fuerzan entradas diarias.

El universo esperado H1 es **369 ticker-días, 363 disponibles y seis ausentes**,
exactamente123 esperados por ticker. Los disponibles por ticker se derivan del
índice. Hay un registro por identidad y modo, también en días sin ofertas/fill.
No se suman los tres modos como cartera.

El productor actual conserva ceros estructurales en `daily.json` para filas
`MISSING_SOURCE`. El auditor debe verificar esa serialización sin reinterpretarla
como PnL observado: sólo los COMPLETE contribuyen a economía y actividad,
`missing_day_economics=null`, y el requisito universal queda
`NO_EVALUABLE_MISSING_SOURCE`. No reescribir esos registros para hacerlos parecer
nuevos retornos nulos. Un día disponible sin fill es un caso distinto.

Si el freeze contiene `selected_mode=null`, los tres modos pueden describirse
según el plan, pero no hay ganador, política promocionada ni selección nueva a
partir de2026. Reconstruir neto, PF, WR, costes adversos, actividad y duración
por mes/ticker/modo y el agregado exacto del informe; no añadir gates posthoc.

## Interfaz y cierre propuestos

CLI futura, aún inexistente:

```text
audit_monthly_walk_forward_test.py
  --monthly-root <root original>
  --source-audit <audit SessionClock>
  --validation-audit <audit2025 completo>
  --expected-validation-audit-sha256 <hash fijado externamente>
  --implementation-review <review nueva del auditor>
  --runtime-review <binding previo de autoridades y raíces>
  --output <root nuevo e inexistente>
```

El cierre compositivo para el adapter conservará el status
`PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES`, con
`scope=VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1` explícito. Incluirá:

- `binding`: monthly_root, run_contract_sha256, session_root,
  session_audit_sha256, index_sha256 y completed_months exactos202501..202606.
- `prior_validation_audit`: ruta, SHA, scope original y declaración de que
  su inventario fue rehasheado; la reconstrucción2025 se hereda de esa autoridad.
- `verified_files`: unión sin conflictos del inventario2025 y archivos2026
  realmente verificados, incluyendo contratos, fuentes/índice, inputs, modelos,
  NPZ y markers, attempts/ledgers y sus markers. La unión no incorpora artefactos
  sólo por estar presentes en disco. El adapter exige rutas absolutas canónicas.
- `audited`: seis meses nuevos, doce fits nuevos, trece modelos utilizadosH1,
  36 ventanas totales, cobertura369/363/6 y checks concretos de orden/replay.
- `limitations`: sin refit/reinferencia/raw-replay, reloj histórico asumido,
  desarrollo visto y `promotion_approved=false`.

El status compartido sólo será admisible tras probar compatibilidad real con
`MonthlyInputs`: no se alterará el adapter para saltarse su autoridad. Su próximo
runtime fijará el hash de este cierre compuesto de forma externa. La auditoría
de mercados2026 no ejecuta el calibrador ni acredita sus políticas corregidas.

Publicación atómica con fsync, salida nueva, bloqueo exclusivo y snapshots del
auditor/revisión antes de ejecutar. Rehash final de todas las autoridades y
inputs consumidos; cualquier cambio o falta impide PASS. No sobrescribir un
fallo ni completar un root antiguo con evidencia distinta.

## Fixtures obligatorias antes de implementación aprobada

1. Seis meses/18 folds con los cortes anteriores, doce fits nuevos y static
   reutilizado; rechazo de TRAIN en el propio mes o cierre de label en el corte.
2. Static omitido del manifest2026, modelo equivocado, escala prestada de otro
   fit, CONFIG/ancho cambiado o started sin complete: todos fallan.
3. Freeze ausente/tardío/alterado, `null` legítimo conservado y cualquier intento
   de seleccionar con2026 rechazado.
4. Predicciones selladas para todos los fits/días antes del primer ledger;
   NPZ alterado, IDs reordenados, score NaN o marker sin miembro requerido.
5. Scheduler independiente con empates, scores cero/negativos, WAIT, NO_FILL,
   fill seguido de bloqueo, liquidación y límites de sesión corta.
6. Calendario369/363/6, seis identidades fijas del índice, duplicados, ausente
   omitido, ausente convertido a COMPLETE, cero estructural y cero sin fill.
7. Informe por ticker y agregado, PF sin pérdidas, ledger vacío, neto/adverso,
   selección null y ausencia de doble cobro o suma de modos.
8. Autoridad2025 con hash equivocado, mes faltante, rutas fuera de raíz, inventario
   contradictorio o archivo cambiado tras lectura; rechazo antes de labels2026.
9. Cierre18meses/36fits y ambos report_hashes; un semestre parcial no pasa.
10. Cierre compuesto consumible por MonthlyInputs para enero y junio2026,
    preservando los inputs2025; falta de NPZ/ledger/marker en verified_files falla.
11. Rehash final, salida preexistente, interrupción y concurrencia: sin PASS
    parcial ni sobrescritura de evidencia anterior.

Estos fixtures serán sintéticos y no consumen mercado. La revisión nueva debe
inspeccionar independencia efectiva y bytes finales. Después se podrá cerrar
la frontera técnica; la ejecución real seguirá dependiendo de los cierres y
autoridades anteriores, no de una estimación de resultados favorables ni de
solicitar otra vez la autorización general ya dada por el usuario.
