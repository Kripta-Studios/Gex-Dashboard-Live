# Weekly H2: primera comparación causal de coste neto

Contrato científico fijado antes de nuevos outcomes. Preparación de código y
fixtures autorizada por la orden weekly del usuario. Ejecución real sólo tras
cierre del piloto, revisión del código y publicación de estos bytes. No requiere
otra elección del usuario. El borrador amplio anterior queda como alternativa
documental no ejecutada; esta primera comparación reduce el alcance a holding
fijo para medir si prolongar la duración ayuda económicamente.

## Universo, calendario y datos

SPY/QQQ/SPXW, compras de CALL o PUT, un contrato de multiplicador 100. Sesiones
20230103–20260630 del índice local `session_clock_dataset_v1/index.parquet`, SHA
`7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4`.
Se usan ticker/date/close_i para calendario; un status ausente de la familia
0DTE no convierte automáticamente en ausente una fuente weekly. Cada fecha
oficial permanece en cobertura. No se deriva H2 del siguiente archivo existente.

H2 = segunda sesión oficial posterior a la entrada, salida exacta 10:35 ET,
estrictamente anterior al vencimiento. Si H2 sale del periodo/calendario sellado,
la entrada es `HORIZON_OUTSIDE_CALENDAR`, sin operación ni label. Expiración
admisible de 1–8 días naturales, conocida por nombre y verificada dentro del
archivo. Si hay varias, menor expiración que permita H2; no se consulta existencia
de archivos futuros para elegir. Ausencia de expiración elegible es `NO_SERIES`,
separada de WAIT. No se usan 0DTE como contratos de entrada.

Sólo Greeks de D:/ThetaData/data_options/{ticker}/greeks/{year}/{month}, nombres
nominales exactos. Inventario de fuentes y calendario con SHA antes de valores,
hash antes/después por archivo, rutas sin enlaces/reparse y proyección explícita.
Mantener todos los estados y manifest final; no sobrescribir ni adoptar parciales.
Clocks nativos y proxy siguen el contrato del piloto; no se demuestra recepción
live. Los resultados sólo tienen validez bajo esa convención de snapshots.

## Oferta causal y features

Decisión 10:30 ET; ejecución ask exacto 10:35, desfase fijo de cinco minutos.
Snapshot nativo presente inválido nunca cae al proxy. No nearest, forward fill,
rollover, strikes sustitutos o selección por datos de salida. Se elige por lado
a 10:30: quote numérica finita 0<=bid<=ask, ask>0, spot>0, delta con signo correcto
y abs(delta)<=1; distancia mínima a abs(delta)=0,50, empate menor spread relativo,
después strike ascendente. Prima de decisión <=49,95 USD por opción (una opción
costará menos de 5.000 USD incluyendo los supuestos de costes).

X contiene exclusivamente números de 10:30, en orden fijo:
`ticker_SPY,ticker_QQQ,ticker_SPXW,right_call,dte,weekday,spot,strike,moneyness,
bid,ask,spread_relative,delta,implied_vol,gamma,theta,vega,rho`.
`moneyness=strike/spot-1`; spread_relative=(ask-bid)/ask. Greeks opcionales
inválidas/ausentes se guardan null; imputación mediana y sus indicadores se
ajustan sólo en TRAIN. Identidad, clocks y todos los campos futuros son metadata
o labels, nunca entran en X. No se incorporan IB/walls ni stops en esta prueba
de duración fija; no se afirma haber probado todas las estrategias weekly.

El mismo contrato seleccionado intenta compra a 10:35. Quote ausente/inválida
o ask>49,95 da `NO_FILL`, PnL cero y sin capital reservado; no se elimina la oferta
del dataset. La decisión no usa esa quote. No hay reintento ni nueva selección.

## Salida, gaps y costes

Salida bid exacto 10:35 en H2 del mismo ticker/expiration/strike/right. Registrar
separados `OBSERVED_EXIT`, `MISSING_EXIT_QUOTE` y `MISSING_EXIT_SOURCE`.
Ambas ausencias retienen la operación: valor cero como límite inferior conservador
de la opción larga, no precio observado ni fill real. No se eliminan pérdidas.
Esas filas permanecen también en TRAIN/CAL con la cota conservadora y bandera
`payoff_is_lower_bound=true`, para no omitir del EV el riesgo de falta de salida.
Su bin es pérdida grande (r=-1 bajo liquidación cero); no se afirma que sea un
retorno observado. El modelo estima escenarios de esta contabilidad conservadora.
Separar métricas de outcomes observados y cotas, reportar proporción por split y
escenario. No presentar una muestra incompleta como PnL íntegramente observado.
Reserva liberada a H2 por convención conservadora.

Costes de investigación heredados, no cotización de bróker:
`net_s=(max(exit_bid-s,0)-entry_ask-s)*100-2.60`, s=0,01 base y 0,02 adverso.
Spread ask→bid incluido. Cada lado tiene comisión asumida 1,30 USD. Sin ejercicio,
settlement, venta corta ni roll; las posiciones elegibles cierran antes de expiry.

## Escenarios, ajuste y EV

Cinco clases fijas: `NO_FILL`, y para fills con salida observada cuatro bins de
retorno bruto `r=(exit_bid-entry_ask)/entry_ask`: r<-0,25;
-0,25<=r<0; 0<=r<0,25; r>=0,25. NO_FILL tiene neto cero.
Labels disponibles a 10:35 del H2 para fills, 10:35 entrada para NO_FILL.

TRAIN 2023–2024, CAL 2025, EVAL H1 2026; todos SEEN_DEVELOPMENT. Un label sólo
entra si su availability es estrictamente anterior al siguiente corte. No
normalización ni selección de features con CAL/EVAL. CAL sólo calibra probabilidades;
no selecciona threshold, modelo, lado, horizonte ni ticker. No refit después de CAL.

Una regresión logística multinomial L2 fija C=1, max_iter=2000, random_state=0,
scaling TRAIN, sin class weighting ni búsqueda de hiperparámetros. Clase ausente
en TRAIN queda probabilidad cero explícita; menos de dos clases hace el modelo
NO_EVALUABLE. Una clase nueva en CAL/EVAL se informa; probabilidad recortada 1e-12
sólo para log loss numérica, no para operar. Calibración por mezcla única
`p_cal=(1-alpha)*p_model+alpha*p_train_prior`, alpha en grid fijo
{0,0.1,...,1}, mínimo log loss CAL, empate menor alpha. Prior empírico TRAIN;
no cambia soporte de clases. Guardar los once scores CAL.

Para cada clase y ticker/right, estimar en TRAIN la media de
`y_s=net_s/(decision_ask*100)`. Shrinkage fijo 20 observaciones hacia media global
TRAIN de esa clase; NO_FILL=0. Si clase ausente, media0 y probabilidad0. Esta
aproximación condicional se declara y su error se evalúa; no confundir probabilidad
de ganancia con EV. `EV_s=decision_ask*100*sum(p_cal*mean_y_s)`.

Política única: mayor EV adverso entre CALL y PUT, sólo si estrictamente>0;
empate exacto WAIT. No umbral elegido con EVAL. Medir calibración también sobre
las ofertas seleccionadas por top1, porque calibración pooled no la garantiza.

## Replay y medición

Cartera hipotética inicial 100.000 USD por bloque TRAIN/CAL/EVAL, con libros
independientes. EVAL arranca sin posiciones ni cash procedente de decisiones
retrospectivas TRAIN/CAL. Los bloques descriptivos pueden cerrar sus últimas
entradas H2 después de su fecha final, atribuidas al bloque de entrada; esas
posiciones nunca se trasladan al siguiente libro. Una posición por ticker,
máximo tres.
Prioridad fija SPY,QQQ,SPXW si capital insuficiente. A 10:30 ticker abierto puede
planificar entrada sólo si su salida programada es ese mismo día a10:35. A10:35
se procesan salidas antes de entradas. Reservar débito y comisión de entrada;
sin reinvertir capital aún comprometido. Si débito real supera cash, la falta de
capital se registra `CAPITAL_BLOCKED`, motivo exclusivo del replay,
no clase NO_FILL de quotes ni fila adicional de ajuste/calibración. Registrar
decisiones, fills, cash y capital reservado. Para cada coste s por separado:
principal=(entry_ask+s)*100; entrada cash-=principal+1,30 y reserved+=principal;
salida cash+=max(exit_bid-s,0)*100-1,30 y reserved-=principal. Equity realizada
cash+reserved valora lo abierto a coste, sin MTM; al cierre debe coincidir
100.000+sum(net_s). No confundir bloqueo de cartera con liquidez de una quote.

Controles: ALWAYS_CALL_H2, ALWAYS_PUT_H2 y ALWAYS_ABSTAIN con mismo calendario,
selector, datos, costes, capital y scheduler. No seleccionar el mejor control.
Informar TRAIN/CAL descriptivos separados y EVAL principal; ambos costes.

Reportar netUSD, PF, trades, meses positivos, no-fills, WAIT, missing sources,
missing exits, máximo capital reservado, duración, exposición overnight y
drawdown de equity REALIZADA (no MTM). No llamar a éste drawdown total: falta
valorar posiciones abiertas entre snapshots. Reportar por ticker y conjunto,
con ledger completo y cobertura; no rescatar grupos a posteriori. Probabilidades:
log loss, Brier y reliability en bins fijos de 0,1; EV predicho frente a realizado
y sesgo para candidatos y selección top1. Cualquier positivo es evidencia de
desarrollo bajo supuestos, no validación live ni autorización de promoción.

## Interfaz de implementación y ejecución

Builder independiente `build_weekly_h2_dataset.py`: inventario metadata y pasada
de extracción; resultados en raíz nueva local. Proyectar y filtrar Arrow antes
de convertir filas Python. Sólo snapshots10:30/10:35; validar identidad/clock de
las filas utilizadas, duplicados fatales. Fuente de salida requerida se incluye
nominalmente aun si ausente. Candidates JSONL una fila por oferta con `candidate_id`,
`ticker`, `entry_date`, `exit_date`, `expiration`, `strike`, `right`, `features`
(dict exacto anterior), `decision_ask`, `entry_ask`, `exit_bid`, `status`,
`label_available_at`, `scenario` (0=NO_FILL,1..4 bins; 1 para cota de salida ausente),
`net_base`, `net_adverse`, `entry_debit_base`, `entry_debit_adverse`, y pins fuente.
Incluir `payoff_is_lower_bound` true exclusivamente para MISSING_EXIT_*.
Coverage JSON incluye todas las sesiones, sus ofertas y razones de ausencia.

Modelo/replay separado `evaluate_weekly_h2_ev.py`, sin acceso D:/ThetaData; consume
dataset y manifest pineados, guarda transformer/modelo/calibración/scores/ledgers
y resumen. Pruebas sintéticas causales, de calendario y contabilidad; revisión
independiente antes de runtime. CPU0/un hilo, RAM y commit libres>=2GB. Código
preparado mientras corre el piloto no es autorización de outcomes anticipados.

Revisión documental independiente previa a outcomes: la primera versión
ee72ad37 recibió FIX_FIRST por omitir las salidas ausentes del modelo de EV y
confundir bloqueo de capital con NO_FILL. Esta versión conserva las cotas en
TRAIN/CAL/EVAL, separa CAPITAL_BLOCKED y fija las ecuaciones de contabilidad.
No se abrió ningún outcome para decidir esta corrección.

La inspección inicial del evaluador detectó además que un replay continuo de
TRAIN/CAL/EVAL trasladaría a EVAL cash o posiciones decididos retrospectivamente
en los bloques descriptivos. Se explicitan libros independientes antes de cualquier
runtime real. Ningún saldo o posición de TRAIN/CAL entra en EVAL.
