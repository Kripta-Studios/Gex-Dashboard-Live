# KING-GEX-MANAGE30-V1 — elección causal de gestión en +30m

Estado: `FROZEN_BEFORE_NEW_PATH_LABEL_BUILD`. Esta hipótesis nace después de
observar los resultados de desarrollo 2023 de KING-GEX-SLOPE1 y
KING-GEX-EXIT1. Por tanto, 2023 es desarrollo y nunca se presentará como OOS.
2024/2025/2026 permanecen cerrados hasta las gates descritas aquí.

## Hallazgo que motiva la familia

La mejor gestión fija de KING-GEX-EXIT1 fue D1/S30: PF 0,925, WR 35,96% y
-30,131R. Elegir ex post B00 o S30 en cada oportunidad tampoco basta: con
scheduler exacto D1 da PF 1,190, WR 43,60% y solo 13/36 ticker-meses.

En cambio, el oracle D1 que elige una de las 16 gestiones congeladas da 1.337
trades, PF 2,357, WR 54,67% y +324,783R; pasa 32/36 celdas bajo la gate actual
PF>1,30, WR>45%, trades>12 y PnL>0. Este oracle no es operable. Solo demuestra
que el estado de gestión tiene un techo económico suficiente para justificar
un intento causal.

El legacy `walkforward_option_path_exit_model.py` no valida esta hipótesis. En
otro universo y contrato, con holds 5/15/30, selección de delta y ejecución no
equivalente, terminó en 1.690 trades, PF 0,811, WR 33,85% y -89.652 dólares.
No se reutilizan sus resultados, thresholds ni calibraciones.

## Pregunta y semántica de decisión

Se mantiene exactamente la oportunidad K1 y la dirección global
`D1_INVERTED`. A la entrada se compra al ask el contrato ya congelado: SPXW d25
y QQQ/SPY d35. No hay elección de strike, delta, lado ni oportunidad nueva.

Todas las gestiones tienen min hold 30m. El estado se observa en la primera
quote exacta del mismo contrato con elapsed entre 30 y 31 minutos. Hasta ese
instante ninguna gestión puede haber salido; peak/MFE/MAE se calculan solo con
quotes observadas hasta esa quote. Entonces se escoge una acción y queda fija:

- las 16 configuraciones de `KING_GEX_EXIT1_EXECUTABLE_PREDECLARATION.md`;
- `E30`, salida inmediata al bid de la quote de decisión.

Elegir una configuración a +30 es equivalente a haberla fijado antes de su
primer trigger, porque se conserva la misma secuencia pre-30 y el mismo peak.
Desde la decisión se mantiene prioridad stop -> trail -> peak/TP, forced mark,
horizonte y bid real del runner sellado. Si falta quote válida en [30,31], la
oportunidad usa B00 con `decision_state_available=0`; no se inventa as-of ni se
elimina usando su outcome.

## Universo y particiones

El censo outcome-free actual contiene 49.400 oportunidades K1 entre 2022-01 y
2025-12: QQQ 15.475, SPXW 17.033 y SPY 16.892. Sus 2.721 sesiones/ticker tienen
Greeks, OI y OHLC locales presentes. La gate física debe revalidar contrato y
quote exactos, no confiar solo en existencia de ficheros.

- entrenamiento inicial: 2022-01..12;
- desarrollo: doce folds 2023, cada mes entrenado solo con meses anteriores;
- outer: 24 folds 2024-01..2025-12, una sola vez y solo tras PASS desarrollo;
- confirmación condicionada: 2026 mes a mes, solo tras PASS outer;
- fit live posterior: para operar un mes M se permite todo mes completado <M.

Nunca se entrena con el mes que se reporta. Los modelos son por ticker, pero el
brazo de features, algoritmo e hiperparámetros son globales. No se selecciona
una política por mes, signo GEX, right o subgrupo.

## Features causales congeladas

Todos los campos se calculan en entrada o hasta la quote de decisión. Se
prohíben outcome, return/exit final, max/min posterior, motivo de salida,
configuración oracle o cualquier quote posterior.

`M0_PATH` contiene:

- ticker, entry minute, right fijo y parámetros numéricos de la acción;
- net GEX y pendiente 45m de la regla K1, momentum 15m y spot de entrada;
- strike/distancia, bid, ask, spread, delta, IV, theta, vega y OI de entrada;
- bid/ask/spread, delta, IV, theta y vega del mismo contrato en +30m;
- retorno ejecutable actual bid/entry ask, MFE, MAE, drawdown desde peak;
- marks a 5/15/30m cuando existe quote exacta, slopes 5-15 y 15-30, número de
  quotes válidas y fracción de retornos positivos hasta la decisión;
- spot return 1/5/15/30m, retorno spot desde entrada y volatilidad realizada
  intrapath, todos desde `underlying_price` observable de las mismas quotes;
- minutos a cierre y día de semana codificado seno/coseno.

`M1_SYNTH_GREEKS` añade, en entrada y decisión, exposiciones de la cadena 0DTE
calculadas con las funciones compartidas y OI diario causal:

- net gamma, vanna, charm, DGEX, zomma, delta, vega y vomma en signed-log;
- cambio signed-log entrada->decisión;
- strikes max/min gamma, vanna, DGEX, zomma, vega y vomma como distancia a spot,
  y su migración entrada->decisión.

Estas variables se marcan `SYNTHETIC_MODEL_DERIVED`. No son `/greeks/all`
nativas ni inventario dealer; OI no revela comprador/vendedor. Se usa el tiempo
a 16:00 exacto de `services.compute_features.calculate_exact_t`, IV 0<IV<2 y
OI>0. No entran sizes ni campos de calidad como alpha.

## Target y modelo

Cada evento genera 17 contrafactuales exactos. El target de una acción es
`clip(return_action - return_B00, -2, +2)`. B00 tiene ventaja cero por
construcción. Todas las acciones de un evento permanecen en el mismo fold y
reciben peso 1/17.

Modelo fijo por ticker y brazo: `LightGBM LGBMRegressor`, objective `huber`,
`n_estimators=300`, `learning_rate=0.03`, `num_leaves=15`,
`min_child_samples=100`, `subsample=0.85`, `colsample_bytree=0.80`,
`reg_lambda=10`, seed `20260715`, determinista y sin early stopping sobre el
mes evaluado. Medianas y cualquier encoding se ajustan solo en train.

En inferencia se elige la acción con mayor ventaja predicha solo si es >0; en
caso contrario B00. Ties: B00 primero y después ID alfabético. No hay threshold,
calibración, grid ni selección mensual.

## Scheduler, gates y selección

Después de asignar una acción a cada oportunidad se rehace el scheduler común:
SPXW 4/0m, QQQ 2/30m, SPY 1/0m, `reject_while_open`, entry ask, exit bid y holds
30..180m.

Una policy pasa desarrollo solo si en cada uno de los 36 ticker-meses cumple
simultáneamente:

- PF >1,30;
- WR >45%;
- trades >12;
- PnL >0;
- min hold >=30m;
- top-5 trades <=20% y top-5 días <=30% por ticker y pooled.

Se evalúan exactamente M0 y M1. Si solo una pasa, se congela. Si ambas pasan,
se elige por peor PF mensual, peor WR, PF pooled y nombre alfabético. Si ninguna
pasa, la familia cierra sin outer; no se rescatan features, tickers, meses,
acciones, thresholds o hiperparámetros. Outer debe pasar sus 72 celdas con la
misma policy para autorizar 2026.

## Checkpoints y freeze

- source checkpoint por ticker/sesión: hashes raw, keys, features y 17 outcomes;
- dataset manifest-last por partición y hashes de inventario/código/protocolo;
- fold checkpoint por ticker/mes/brazo: train cutoff, modelo, predicciones,
  trades, scheduler y métricas;
- un relanzamiento solo reutiliza si identidad, rows, bytes y SHA coinciden;
- resultados parciales nunca autorizan cambiar el protocolo ni abrir outer.

La aproximación sigue el principio de estimar valor de continuación de
Longstaff-Schwartz y fitted value iteration, pero aquí la acción se reduce a un
menú contrafactual fijo en +30m:

- https://escholarship.org/uc/item/43n1k4jb
- https://jmlr.org/papers/volume6/ernst05a/ernst05a.pdf
