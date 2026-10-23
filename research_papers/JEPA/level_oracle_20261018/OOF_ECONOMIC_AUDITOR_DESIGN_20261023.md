# Diseño del auditor económico independiente OOF

Fecha: 23 de octubre de 2026. Estado: **DESIGN_ONLY; implementación y ejecución pendientes**.
Este documento responde al encargo de diseñar la auditoría que falta. No modifica
productores, revisiones anteriores, parámetros, modelos ni fuentes. No autoriza
calibración real ni evaluación de mercado. El coordinador decidirá la implementación.

## Alcance y autoridades

El auditor propuesto debe verificar dos capas: la construcción de máximos y offsets
del adaptador, y la ejecución económica completa de las seis políticas. Verificar
sólo los hashes del adaptador no prueba que el offset se haya calculado correctamente.
Tampoco basta reproducir los trades del control: la corrección cambia los estados
visitados y puede operar donde el control esperó.

Las autoridades metodológicas vigentes son
[PREQUENTIAL_MAX_CALIBRATION_DESIGN](PREQUENTIAL_MAX_CALIBRATION_DESIGN.md),
[OOF_MAXIMUM_CALIBRATION_INTEGRATION](OOF_MAXIMUM_CALIBRATION_INTEGRATION.md),
[MONTHLY_OOF_CALIBRATION_ADAPTER_SPEC](MONTHLY_OOF_CALIBRATION_ADAPTER_SPEC.md) y
[OOF_CALIBRATED_POLICY_EVALUATION_SPEC](OOF_CALIBRATED_POLICY_EVALUATION_SPEC.md).
La revisión del 18 de octubre conservaba un rerun pendiente. El coordinador informa
ahora de 23 fixtures pasadas; este documento no las reejecuta ni convierte ese
resultado técnico en autorización de mercado.

Se conservan `static`, `expanding`, `rolling12`, cada uno con `__control` y
`__corrected`; umbral estricto cero USD y ningún ganador seleccionado. El calibrador
siempre usa historial expanding desde enero de 2025, también para el modelo base
rolling12. No hay búsqueda de ventanas, umbrales, bins, épocas o tickers.

El auditor nuevo no importará `monthly_oof_calibration_adapter.py`,
`evaluate_oof_calibrated_policy.py` ni `oof_maximum_calibration.py` para calcular
máximos, offsets, replay o métricas. Reconstruirá esas operaciones por separado.
Puede reutilizar utilidades de lectura/hash o primitivas de otro auditor
independiente si sus bytes y alcance quedan fijados antes de ejecutar. No hará
refit, reinferencia base/GPU ni reconstrucción de features o quotes raw.

## Admisión antes de reconstruir

El futuro llamador fijará externamente el SHA de la auditoría mensual de outputs;
no lo calculará de un archivo arbitrario para autoautorizarse. Se exige status
`PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES`, no una revisión
de implementación. Su binding debe contener `monthly_root`,
`run_contract_sha256`, `session_root`, `session_audit_sha256`, `index_sha256` y
`completed_months`. Los mapas agrupados `verified_files` se aplanan con rutas
absolutas normalizadas, rechazando aliases con hashes distintos.

Para auditar el mes objetivo m deben estar auditados todos los meses desde
202501 hasta m, inclusive: los anteriores aportan calibración y m aporta las
predicciones/controles base. Para cerrar H1 completo se necesitan los 18 meses
202501–202606. Un auditor mensual limitado a 2025 no habilita esta comparación.
La interfaz deberá contrastarse con el auditor mensual 2026 definitivo cuando
éste se cierre; no se supone que una implementación todavía pendiente sea PASS.

Se fijarán también el SHA externo del cierre de corrección de cada mes, los
hashes del productor/review OOF y las raíces de salida. Se revalidará la auditoría
SessionClock y su índice; fuentes y outputs serán sólo lectura. Una raíz de audit
nueva, separada de las tres raíces consumidas, conservará todo fallo.

## Artefactos que se deben consumir y vincular

`M` designa el root mensual, `S` SessionClock, `C` el root del adaptador y `E_m`
una salida de replay para el mes m. `p` es procedimiento y `t/d` ticker/fecha.

| Capa | Artefactos obligatorios |
|---|---|
| Fuente | Auditoría SessionClock; `S/index.parquet`, contratos y completion ligados a ella; actions/labels del `day_root` indicado por el índice |
| Mensual | Auditoría externa; `M/run_contract.json`; `fits/<fit_key>/inputs.json` y `.complete.json`; `models/<fit_key>.txt`, `.fit_started.json`, `.complete.json` |
| Predicciones base | `M/predictions/m/<fit_key>/t/d.npz` y `.complete.json`; `M/months/m/predictions.complete.json`; `daily.json`, `daily.complete.json` |
| Control económico | `M/ledgers/m/p/t/d_attempts.parquet`, `d_ledger.parquet` y `d.complete.json` |
| Adaptador | `C/implementation.json`, `m.run_contract.json`, `m.inputs.json`, `m.complete.json` |
| Máximos/historia | `C/p/selections/t/d.json`; `C/p/realized/t/d.json` para días anteriores disponibles |
| Corrección | `C/p/m/calibration.json`; `C/p/m/scores/t/d.json` para días objetivo disponibles |
| Replay | `E_m/run_contract.json`, `all_scores_and_controls.json`, `baseline/p/selections/t/d.json`, `days/<policy>/t/d.json`, `summary.json`, `completion.json` |

La pertenencia debe ser efectiva, no un bucle que sólo valide lo que un mapa
decidió incluir. Cada archivo mensual consumido y sus markers debe figurar en
`verified_files` y en el marker correspondiente. Cada marker exige status
COMPLETE y binding al contrato mensual. Se comprueban miembros requeridos aunque
el mapa se haya vaciado; no se permite escapar de `M` mediante rutas relativas.

Actions/labels se vinculan directamente a los SHA del índice auditado. El adaptador
no exige duplicarlos en el mapa mensual, por lo que el auditor respetará esa
distinción y registrará su autoridad de índice. Deben estar en los mapas finales
de inputs efectivamente consumidos cuando corresponda. `m.inputs.json`,
`all_scores_and_controls.json` y `completion.json` se cruzan con los archivos
requeridos por sus inventarios, incluidos modelos, predicciones, controles,
selections, calibraciones y scores. Un hash válido de un subconjunto no basta.

## Máximos OOF y cortes del modelo base

Para cada predicción se reconstruye la ventana del procedimiento:

- static: `[20230101, 20250101)` y el mismo fit que expanding de enero de 2025.
- expanding: `[20230101, inicio_del_mes_predicho)`.
- rolling12: los doce meses completos anteriores al mes predicho.

Se comparan `fit_key`, inicio, corte exclusivo, config, 1954 columnas,
`fit_started` y escala TRAIN con las autoridades mensuales. La prueba de fechas
efectivas de filas/labels TRAIN pertenece al auditor mensual y debe estar en su
alcance; una fecha declarada en JSON no sustituye esa prueba. Los NPZ contienen
`action_id`, `state_i`, `scores`, `model_sha256`, `scale`: los scores ya son USD
y no se multiplican nuevamente por la escala.

Se contrastan IDs/relojes y orden con todas las ofertas del día. Por cada estado
ofrecido se reconstruye el máximo usando sólo score descendente y action_id
ascendente. Se verifican ganador, score, número de ofertas y segundo score
(null si sólo hay una). Se conservan máximos negativos, NO_FILL posterior y
estados que ninguna política visitó. Los días disponibles sin ofertas tienen
selección vacía, permanecen en inventario y no generan un label artificial.

Las selecciones se cotejan completas y por hash canónico con los archivos
originales del adaptador y las copias baseline del replay. No se consultan labels
para decidir ganador, empate, inclusión de estado o elegibilidad histórica.

## Reconstrucción del offset sin futuro

Para m se usan exactamente los días de meses anteriores desde 202501. Enero de
2026 usa 2025; febrero puede añadir enero de 2026; nunca el propio mes objetivo.
La disponibilidad contractual es cierre NYSE + un minuto: 16:01 NY en completa
y 13:01 NY en corta, con DST. Debe ser estrictamente anterior al inicio de m.
Es un supuesto de disponibilidad, no recepción observada ni fecha de escritura.

Cada registro realized se reconstruye uniendo exclusivamente el máximo ya
fijado con `action_id/status/net_base` del label sellado. NO_FILL tiene neto cero;
no se sustituye por otra acción. Se verifican el payload selection, su hash,
hash de labels, modelo, predicción, hora y semántica de disponibilidad.

Para procedimiento p y ticker t, el offset es:

```text
residual_d = fsum(net_base_del_máximo_s - score_usd_del_máximo_s) / estados_con_ofertas_d
offset_p,t,m = fsum(residual_d) / días_históricos_disponibles_con_ofertas
```

Cada día pesa igual y cada estado ofrecido pesa igual dentro de su día. No se
pondera por número de contratos, trades, filas de entrenamiento o beneficio.
Missing y días sin ofertas permanecen identificados; no entran como residuo cero.
Si un ticker no tiene máximos históricos suficientes para calcular siquiera su
media, el contrato actual falla; no se inventa un fallback. Se reconstruyen
`training_records`, sus hashes, `days_with_offers`, `days_without_offers`,
`selected_states`, `offsets_usd` y `offset_risk_units`.

Las escalas comunes proceden del static/expanding enero de 2025, ajustado sólo
con 2023–24; sólo presentan el offset en unidades de riesgo. El offset y su
aplicación económica siguen siendo USD. La reconstrucción usará `math.fsum` y
las mismas divisiones especificadas; se exigirá igualdad float64 de offsets y
scores corregidos, sin relajar tolerancias tras observar mercado.

Para cada máximo objetivo se comprueba `corrected_score_usd = score_usd + offset`.
Se conserva el action_id seleccionado originalmente: no se vuelve a ordenar
acciones tras sumar, evitando incluso cambios de desempate por redondeo. El offset
no depende de `has_filled`, no añade penalización terminal ni fuerza entradas.

## Replay y contabilidad independientes

Antes del replay corregido se reconstruye el control con los máximos originales
y los attempts/ledgers mensuales ya auditados. Se comparan fila a fila identidad,
estado, score float64, `has_filled_before`, fill, salida y payoffs; scores y netos
de esta proyección conservan bytes float64. Todos los controles del mes deben
pasar y todos los scores quedar sellados antes del acceso nuevo a labels objetivo.
Que los controles mensuales ya contengan esos resultados históricos se declara;
no pasan a ser datos no vistos ni participan en el cálculo del offset de m.

El auditor recorre cada día desde estado 60, reconstruyendo también decisions:

- Estado sin oferta o máximo <=0: WAIT y siguiente minuto.
- Máximo >0: se compromete esa acción antes de consultar su label.
- NO_FILL: netos cero, salida registrada state+1, siguiente minuto y h intacto;
  no se rescata otra acción del mismo estado.
- FILLED: salida entre state+2 y close_i−5, siguiente decisión exit+1 y h=1.

Decisiones hasta close_i−15, con close_i 210/390. Una operación bloquea las
decisiones intermedias. Control y corregida recorren sus propias trayectorias;
no se reutiliza h ni el conjunto de trades del control para la corregida.
Se cotejan decisions, attempts y ledger completos en cada JSON diario.

Los payoffs se autentican contra labels auditados. El auditor comprobará también
la contabilidad ya declarada desde entry_ask/exit_bid sellados: multiplicador 100,
slippage 0,01 por lado base y 0,02 adverso, bid ajustado limitado a cero y comisión
total 2,60 USD. Es una verificación de labels, sin volver a cobrar al replay.
No reconstruye geometría de barreras ni consulta quotes raw. Costes y agregados
económicos pueden usar la tolerancia absoluta 1e−8 ya utilizada por los auditores
de esta familia; IDs, calendario, estados, scores y offsets no usan esa tolerancia.

## Calendario, informes y gates

Se reconstruye el calendario completo desde el índice y la convención XNYS
auditados: historial 2025 de 750 ticker-días, incluidos nueve cortos; objetivo
2026H1 de 369, con 363 disponibles y seis faltantes SPY/QQQ en 20260401/09/15.
Cada inventario de procedimiento debe contener todas las claves esperadas y su
status. En historial posterior, los faltantes de abril siguen presentes aunque
no aporten residuos. No se deriva el calendario de los trades observados.

Missing produce `trajectory=null`, trades/netos null y NO_EVALUABLE. Un día
disponible sin fill produce cero operaciones/neto observado cero. Se comprueban
las dos coberturas por separado: observable y universal; ningún missing puede
convertirse en PASS universal o en una pérdida inventada.

El productor actual calcula economía pooled mensual y del periodo; el resumen
de periodo `by_ticker` contiene **cobertura, no economía por ticker**. El auditor
reconstruirá los campos que existen y añadirá su propio informe descriptivo por
política/ticker/mes a partir de los JSON diarios, sin atribuirlo retroactivamente
al productor. PF se obtiene de ganancias/pérdidas agregadas, nunca promediando PF
mensuales. Cero pérdidas se expresa con PF null y flag infinito sólo si hay ganancias.

Para el objetivo científico se conservarán los criterios ya fijados en PROTOCOL:
neto base y adverso >0, PF base >=1,20, >=60 operaciones por ticker en H1 y >=3/6
meses positivos simultáneamente, además de la exigencia posterior de fill diario.
Se reportarán como comprobaciones separadas de las seis políticas fijas, sin
seleccionar ganador ni rescatar ticker/mes. No llamar PASS económico a una mejora
pooled que incumple un ticker. Una auditoría PASS acredita reproducción, no esos
gates. La cobertura universal con las seis ausencias sigue NO_EVALUABLE.

2025 es TRAIN del calibrador, no validación integral del sistema corregido.
2026 sigue SEEN_DEVELOPMENT. Un informe de un mes no representa H1 completo;
el cierre del periodo requiere exactamente seis meses y las seis políticas.
`winner_selected=null`, `technical_ready=false`, `promotion_approved=false`.

## Sellos, fallos y salida mínima del auditor

La revisión previa fijará código, specs, primitivas, hashes externos y raíces.
Se comprobará la secuencia documental selección→realized→calibración→scores→
`all_scores_and_controls`→trayectorias→completion, distinguiendo reutilización
de selecciones históricas de la creación de nuevas selecciones. Los mtimes sólo
corroboran ese registro; no prueban accesos de memoria ni recepción de mercado.
No se impondrá una cronología imposible al reutilizar registros históricos ya
sellados. Las fuentes heredadas no necesitan haber sido escritas en 2025.

Se verifican al inicio y al final todos los miembros realmente consumidos,
incluyendo los manifests/markers originales. El código del auditor se sella
antes de leer y se rehashea al cerrar. Un root incompleto, contrato ausente,
mezcla de autoridades, omisión de mes o mutación produce fallo conservado,
nunca PASS parcial. La publicación será exclusiva y atómica con fsync.

Salida propuesta: `audit.json` con status específico de mes o de periodo completo,
scope `OOF_OFFSETS_AND_ECONOMIC_EXECUTION_GIVEN_AUDITED_BASE_SCORES`, bindings de
auditorías/cierres, meses realmente auditados, conteos de máximos/días/ofertas,
offsets reconstruidos, seis informes, gates separados, diferencias y mapa de
archivos verificados. Debe declarar `base_fit_reproduced=false`,
`base_inference_reproduced=false`, `raw_quote_replay=false` y los límites de arriba.
Los nombres finales de status/CLI se fijarán en la especificación de implementación.

## Fixtures que debe superar la implementación

1. Máximos negativos, empates, segunda oferta, día vacío y NO_FILL; no filtrar por
   trades realizados ni reemplazar el máximo con el mejor payoff.
2. Ventanas de los tres procedimientos, static compartido, escala equivocada,
   cutoff futuro, DST, corto 13:01 y disponibilidad exactamente en el límite.
3. Media por día/estado distinta de media por fila; missing y día sin ofertas;
   historia incompleta, duplicada, mezclada entre procedimientos o del propio mes.
4. Omisión individual de modelos, NPZ, markers, selections, realized, controles y
   fuentes en mapas; aliases contradictorios; cambio de bytes después de admisión.
5. Offset positivo/negativo que cambia estados visitados; WAIT, h, NO_FILL,
   solapamiento, estado límite corto, pérdida, exit_bid cero y costes adversos.
6. Cadena de control exacta, incluido signed-zero/dtype cuando proviene de NPZ;
   rechazo antes de labels nuevos si falla un control o el sello mensual de scores.
7. Calendario completo con seis missing, null frente a cero, umbral exactamente
   cero, agregación por ticker y PF desde ganancias/pérdidas; gates sin selección.
8. Integración sintética de admisión→offset→replay→informe y fallos de publicación:
   ningún PASS con productor incompleto, root previo preservado y rehash final.

Las fixtures actuales del adaptador/replay son evidencia útil de sus contratos,
no sustituyen las pruebas independientes. No se ejecutan mercados para desarrollar
el auditor; los lanzamientos futuros respetarán el mínimo operativo de 2 GB libres
de RAM y commit y la coordinación de recursos.

## Bytes inspeccionados para este diseño

| Archivo | SHA256 |
|---|---|
| `monthly_oof_calibration_adapter.py` | `7b80cff43e3887a92e0f89be6daa863a670ccd72d22a0f4aeabd032a39479364` |
| `evaluate_oof_calibrated_policy.py` | `eeaad06f5b862a3153f29e7eab579b19a35e182ab506cf1f59e65631e187e716` |
| `oof_maximum_calibration.py` | `19e922dd65855c4cd7e2ec9d482d477a328245bcf642eeeb7771985f247e20b5` |

No se han leído valores de mercado, ejecutado calibración/fit/replay ni modificado
esos archivos para redactar este diseño.
