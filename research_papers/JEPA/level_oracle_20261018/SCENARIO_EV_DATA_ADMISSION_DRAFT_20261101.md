# Borrador de admisión de datos para escenarios y EV

**Estado: DRAFT_NONEXECUTABLE.** 1 de noviembre de 2026. Este texto no autoriza
lectura de outcomes, entrenamiento, evaluación, selección, arquitectura, umbral
ni lanzamiento. El OOF en curso y su protocolo permanecen inmutables; cualquier
familia posterior espera su cierre y auditoría FULL_H1.

## Propósito y autoridad reutilizada

El consumidor futuro estimaría, para cada oferta causal `(X_t,a)`, probabilidades
de cuatro resultados excluyentes `NO_FILL/TARGET/STOP/EOD` y el retorno neto
condicional dentro de cada resultado. El EV por oferta es
`sum_s P(s|X_t,a) E[R_neto|s,X_t,a]`, separado para costes base y adversos.
TARGET no implica retorno positivo y los costes ya presentes en `net_base` y
`net_adverse` no se vuelven a cobrar.

La dirección y la abstención autorizada proceden de
`EXPECTED_VALUE_SCENARIO_DIRECTION_20261101.md`: WAIT es una decisión, no una
quinta etiqueta; un día disponible sin fill es legítimo, una fuente ausente es
`NO_EVALUABLE`, y esperar siempre no acredita una ventaja. `PROTOCOL.md` conserva
el universo SPXW/SPY/QQQ, la causalidad, las acciones ofrecidas y la economía.
Este borrador reutiliza los bytes auditados sólo dentro de su alcance declarado;
no atribuye una nueva auditoría de raw, features, labels full ni economía.

## Fuentes admitibles y separación causal

1. La autoridad de calendario/admisión será el índice del dataset SessionClock,
   ligado a su `dataset_contract.json`, `feature_contract.json`, `completion.json`
   y auditoría independiente. `build_session_dataset.py:421-485` fija calendario,
   índice/auditor full originales, 2.625 identidades, 2.619 disponibles, seis
   ausentes y 24 cortas; `:553-571` exige 2.619 `COMPLETE` y seis
   `MISSING_SOURCE`. No se infiere cobertura por presencia de carpetas.
2. Por ticker-día `COMPLETE`, la parte causal se limita a `states.parquet`,
   `levels.parquet`, `actions.parquet`, `features.npz/json`,
   `action_features.npz/json` y sus hashes/bindings. Los outcomes se mantienen
   separados hasta sellar soporte, orden, splits y transformaciones causales.
3. Sólo después de ese sello se admite `labels.parquet` como sidecar futuro.
   `run_engine_dataset.py:338-346` separa `states/levels/actions` de
   `labels/advantages/oracle_ledger/oracle_value`; para esta familia no se
   admiten advantages, elección del oracle, ledger ni value como inputs.
4. El contrato full reutilizado debe conservar sus hashes/auditoría original.
   Las 24 cortas pueden reutilizar sólo el alcance reconstruido y auditado por
   `audit_session_clock_dataset.py:186-239`; no se presenta como recomputación
   de toda la economía full.

Después de ese sello, una transformación del **target TRAIN** sí puede consumir
sólo outcomes del split TRAIN, con regla predeclarada y parámetros ajustados allí.
Sus parámetros quedan congelados antes de validación/evaluación. Esto no permite
que outcomes definan soporte, features, muestreo de identidades o transforms de X.

## Esquema lógico mínimo por oferta

Clave de día: `ticker: string{SPXW,SPY,QQQ}`, `date: YYYYMMDD`, `close_i: int`,
`status: {COMPLETE,MISSING_SOURCE}` y hashes de índice, contratos y archivos
consumidos. `evaluation_status=NO_EVALUABLE` sólo está persistido para ausentes;
`EVALUABLE` sería una normalización derivada de `COMPLETE`, no un valor fuente.
La clave de oferta es `(ticker,date,action_id)`; `action_id`
es único dentro del día, no una feature ni una clave global suficiente.

Tabla causal de oferta: columnas exactas de `level_engine.py:38-55`:
`action_id,state_i,entry_i,contract_i,right,strike,selected_delta,delta_bucket,`
`target_level_id,target_center,target_source_mask,stop_level_id,stop_center,`
`stop_source_mask,band,entry_level_id`. Debe cumplirse `entry_i=state_i+1`.
`contract_i`, IDs de nivel y de acción son identidades/alineación, nunca inputs
aprendidos salvo los campos expresamente incluidos en el whitelist causal A33.

Features de estado: B81, `tokens[20,45]`, `maps[20,5,64]`,
`token_mask[20]`, `bar_mask[20]`, `map_mask[20,5]` float32 fraccional,
`bar_end_i[20]` y `state_valid`, según `FEATURES.md` y `features.py:313-322`.
Todos los `bar_end_i < state_i`; una historia válida no se borra porque el estado
actual sea inválido. No convertir `map_mask` a booleano ni copiar restricciones
de los grafos toy. A33 proviene del whitelist publicado; `action_features` debe
alinearse exactamente con `actions.action_id` (`build_session_dataset.py:346-369`).

Sidecar de resultado: columnas exactas de `level_engine.py:56-69`:
`action_id,status,trigger_i,exit_i,reason,entry_ask,exit_bid,missing_exit,`
`missing_spot_count,net_base,net_adverse,hold_minutes`. Etiqueta de escenario:

| Condición auditada | `scenario` | retorno |
| --- | --- | --- |
| `status=NO_FILL`, `reason=NO_FILL` | `NO_FILL` | ambos netos exactamente 0 |
| `status=FILLED`, `reason=TARGET` | `TARGET` | netos observados, no premio fijo |
| `status=FILLED`, `reason=STOP` | `STOP` | netos observados |
| `status=FILLED`, `reason=EOD` | `EOD` | netos observados |

`level_engine.py:488-540` define NO_FILL por quote de entrada inválida y conserva
FILLED con salida ausente, bid conservador cero y `missing_exit=true`. STOP tiene
prioridad sobre TARGET en el primer snapshot válido (`:454-477`). Ningún campo
de este sidecar puede determinar soporte, features, muestreo o normalización de
inputs X. Las transformaciones del target sólo-TRAIN siguen la excepción
explícita indicada arriba, después del sello y antes de evaluación.

## Reloj, universo y ausencias

`session_clock.py:6-46` fija full `close_i=390`, estados `60..375`, EOD `385`, y
short `close_i=210`, estados `60..195`, EOD `205`; el cierre de una acción llena
avanza a `exit_i+1`, mientras WAIT y NO_FILL avanzan a `t+1`. El campo heredado
`time_unit_minutes=390` de `as_dict()` no debe interpretarse como duración de una
sesión corta; `n_slots=211` y los límites derivados gobiernan su soporte.

Cada día `COMPLETE` aporta todos sus estados programados y todas sus ofertas,
incluido un día con cero ofertas: éste sigue siendo evaluable como WAIT. Cada
`MISSING_SOURCE` conserva `NO_EVALUABLE` (`build_session_dataset.py:502-510`) y
no genera estados, ofertas, labels cero ni sesión WAIT artificial. Full y short
se informan por separado y conjuntamente sin truncar short ni rellenarlo hasta375.

## Joins, orden y validación cerrada

- Exigir unicidad de `(ticker,date)` en el índice y de
  `(ticker,date,action_id)` en ofertas, A33 y labels; duplicados fallan cerrado.
- Exigir igualdad exacta de conjuntos de IDs entre oferta, A33 y label, no sólo
  longitudes. `level_engine.py:543-562` ya exige universo y merge1:1 de acciones
  y labels. La feature B81/tokens/maps se une por `(ticker,date,state_i)`.
- Conservar orden canónico explícito: días `(date,ticker)` según índice sellado;
  estados crecientes; dentro del estado `action_id` creciente. Reordenar para IO
  es válido sólo si se restaura y verifica la clave, nunca por posición física.
- Verificar shapes, dtypes, finitud donde el schema la exige, hashes antes y
  después de lectura, schemas y
  bindings de procedencia; rechazar archivo faltante, hash distinto, ID extra,
  reloj imposible, clase desconocida o causal/future sidecars mezclados.
  Las quotes NaN de un NO_FILL son parte de su schema; no imputarlas ni exigir
  por accidente finitud de esos campos posteriores.
- Verificar exactamente una clase por oferta, `P_s` finitas en `[0,1]` y suma1
  en evaluación futura; retornos condicionales y EV se calculan por ambos costes.

## TRAIN muestreado frente a evaluación

La población científica es **todas** las ofertas de todos los días disponibles.
TRAIN podría usar un subconjunto seleccionado sin outcomes sólo bajo un contrato
posterior que fije población objetivo, regla de inclusión y pesos de diseño. El
sampler heredado `rollout_sampling.py:13-16,87-142` selecciona como máximo32 por
cuatro bandas full y pondera `M_db/(M_d*k_db)`: estima una población uniforme por
acción dentro de ticker-día, no una población uniforme por estado.

No se adopta automáticamente: `_validate_sample` exige día no vacío
(`rollout_sampling.py:161-191`) y el sampler no recibe ni valida `close_i`.
Sí acepta estados short60..195 porque son subconjunto de60..375: usa las primeras
bandas y deja las restantes vacías, sin inventar slots. Lo pendiente es validar
explícitamente el reloj por día y decidir el tratamiento de días sin ofertas.

La selección por top SHA es determinista una vez fijadas las identidades; `k/M`
no es una aleatorización observada. Sus pesos son pesos de diseño para el objetivo
declarado, no prueba automática de insesgadez estadística. No reconstruyen
logits/softmax ni ocupaciones de ofertas omitidas. Un modelo por acción no
necesita full-softmax para estimar `P(s|X,a)`, pero tampoco puede presentar el
subconjunto como soporte completo. La unidad de incertidumbre sigue siendo la
sesión/bloque, aunque el loss de TRAIN se compute por filas ponderadas.

Validación/test y replay económico leen y puntúan **todas** las ofertas, además
de reportar por separado las seleccionadas. Métricas probabilísticas se agrupan
por sesión/bloque, no por filas como observaciones independientes. Se conservan
todas las pérdidas, clases, meses, tickers, cortas, días cero-fill y abstención.

## Coste de oportunidad y alcance del EV

El EV anterior es por oferta frente a CASH inmediato. No equivale al valor de
una política: una FILLED bloquea hasta `exit_i+1` y puede impedir ofertas futuras;
WAIT conserva oportunidades. La evaluación futura debe reproducir el scheduler
causal sobre todas las ofertas y comparar ledger/política contra WAIT/CASH. Debe
reportar por separado EV por oferta, EV de ofertas elegidas y PnL secuencial.
No se introduce un V-oracle, continuación clarividente ni coste de oportunidad
estimado desde outcomes futuros como feature.

## Checklist previo a cualquier ejecución futura

1. OOF cerrado, exit real y auditoría FULL_H1 interpretada.
2. Contrato, binding y GO operativos concretos revisados bajo la autorización
   vigente; este borrador no los crea ni activa.
3. Pines de índice, contratos, auditorías, schemas y todos los archivos admitidos.
4. Censo metadata-only de días, estados, ofertas, vacíos, full/short y ausentes.
5. Fixtures de duplicado, ID omitido/extra, orden alterado, hash distinto,
   NO_FILL, salida ausente, STOP/TARGET simultáneos y EOD full/short.
6. Fixtures de máscaras fraccionales e historia válida con estado inválido;
   perturbación de sidecars futuros deja soporte/features bit a bit iguales.
7. Si hay muestreo TRAIN: regla de inclusión, pesos de diseño, soporte
   short/vacío y estimando predeclarados; evaluación siempre exhaustiva.
8. Splits temporales, reglas de freeze, transforms de target sólo-TRAIN,
   calibración probabilística/económica, riesgos y presupuesto predeclarados.
9. Auditor independiente reconstruye joins, etiquetas y replay desde fuentes
   selladas dentro del alcance declarado; ninguna selección posthoc por ticker.

## Decisiones todavía pendientes

Quedan sin fijar: arquitectura, loss/regla de scoring, parametrización de retorno
condicional o distribución, tratamiento estadístico de clases raras, calibrador,
muestreo TRAIN, pesos, capacidad, semillas, thresholds, regla de abstención,
control directo comparable, splits futuros y criterio económico. Tampoco se ha
decidido una política secuencial ni si basta el EV inmediato. Estas decisiones
requieren contrato revisado posterior al audit OOF; este borrador no es un GO.
