# Evidencia observable para explicar decisiones alrededor de niveles

Diseño y extractor separados, 2026-10-18. No modifica motores, ofertas, filtros,
modelos o entrenamientos existentes. Complementa MARKET_CUE_EVALUATION_PLAN.md.
Una descripción plausible de una operación que el oracle eligió con futuro no
demuestra que esa descripción permita elegirla antes de conocer el resultado.

## Implementación actual

`market_cues.extract_market_cues(*, state_i, base[81], tokens[20,45],
token_mask[20], bar_mask[20], bar_end_i[20], action[33])` acepta una decisión y una
acción ofrecida. No acepta labels, PnL, identidad del oracle, contrato o salida.
Devuelve `metrics[name]={value,valid,missing_reason}`, `evidence_tags` y límites
explícitos. Los datos ausentes son null; no se convierten en evidencia neutra.

Se aprovechan exactamente las features causales actuales:

| Concepto | Evidencia y alcance |
|---|---|
| Posición y recorrido | Spot en coordenadas IB, cambios1/5/15m con máscara, distancia a objetivo/stop y banda. `target_stop_ratio` es geometría de spot, nunca ratio de beneficios monetarios. |
| Niveles | Trece Fib fijos y top3 actuales de OI/gamma por lado. Distancia al componente visible más cercano y número de tipos de fuente dentro de banda. No reconstruye exactamente los clusters del motor ni conoce toda la distribución de strikes. |
| Vela | Últimas velas5m/15m completamente cerradas, cuerpo, rango y mechas; cobertura spot exactamente1. No sustituye una vela parcial o ausente por una más antigua. |
| Opción | Bid/ask relativos a spot, spread/ask, delta/IV/theta/vega con flags individuales. Un cero de Greek válido se conserva. No hay gamma del contrato en A33: se informa ausente, sin recalcular Black–Scholes. |
| Distribución | OI observado CALL/PUT, cuota PUT del total observado, concentración top3 y gamma proxy unsigned. OI desconocido no es cero. Loggamma0 puede ser cero real o NaN reemplazado: se informa ambiguo. |
| Cambio de distribución | Logmasa actual menos media de logmasa de la última vela cerrada5m/15m, sólo con cobertura completa comparable. No es variación aritmética de masa ni flujo observado. |

La representación histórica de tokens no conserva coordenadas top-wall por
minuto: no se inventa un desplazamiento histórico de walls. Los cambios de OI o
gamma también pueden reflejar variaciones del universo visible, IV, spot y tiempo
restante; no identifican compras/ventas, migración de inventario ni hedging.

## Reglas descriptivas fijas, anteriores a cualquier comparación nueva

Sea d=+1 para CALL, −1 para PUT; L es el componente visible más próximo al spot
en la decisión y b la banda ya ofrecida. Todos los cálculos son en unidades IB.

1. **Proximidad/confluencia:** distancia a L≤b; confluencia cuando coinciden banda
   Fib y al menos una banda wall visible. CALL-OI y CALL-gamma del mismo strike
   son tipos correlacionados, no dos pruebas independientes.
2. **Geometría de rechazo:** tres velas5m cerradas completas. El cambio entre los
   dos cierres anteriores va contra d; la última vela intersecta [L−b,L+b], cierra
   del lado d, tiene cuerpo a favor y mecha del lado de aproximación. Spot actual
   no retrocede respecto a ese cierre en dirección d. Son condiciones de signo
   y banda existente; no hay umbrales elegidos por rentabilidad.
3. **Geometría de aceptación/retest:** dos cierres5m consecutivos del lado d de L,
   última vela intersectando su banda y cuerpo a favor; última15m con cuerpo a
   favor. Puede coexistir con rechazo: no se fuerza una clasificación exclusiva.
4. **Contexto y coste:** reportar las anteriores junto a concentración/masa
   unsigned, cambios de logmasa, delta, IV y spread/premium. No asignar dirección
   por el signo del put/call OI ni interpretar concentración como soporte probado.

L es conocido **en la decisión**, no necesariamente cuando se formaron las
velas. Se expone `anchor_asof_decision=true` y
`historical_anchor_availability_verified=false`; las etiquetas dicen geometría
relativa al ancla actual. Para las velas anteriores a10:30 tampoco estaba fijado
el IB completo. No llamar a estas etiquetas una reacción a un nivel que ya se
conocía entonces. Verificar persistencia histórica del nivel sería fase separada.

## Ilustración fija y comparación emparejada posterior

El runner `run_market_cue_diagnostic.py` fija SPY20250102, sesión previamente
elegida para ilustraciones, y control `gbt_net__0` original; no escoge días/trades
según resultados. Requiere binding explícito de hashes procedentes de las
autoridades ya publicadas. Primero procesa **todas** las acciones ofrecidas y
sella `all_candidate_cues.jsonl` y `features_seal.json`. Después abre únicamente
columnas de identidad de los ledgers oracle/control para
`membership_overlay.json`; no lee sus columnas PnL. Conserva timestamps NYSE y
UTC de la decisión, no del fill. Esta sesión no cuantifica predictibilidad.

Binding CLI: `kind=PREENTRY_CUE_INPUT_BINDING_V1`, ticker/date fijos,
`model_policy=gbt_net__0`, cache_npz_sha256/cache_meta_sha256 y
`provenance={authority_absolute_path:sha256}`. `files[name]={path,sha256}` para
features/features_metadata/action_features/action_metadata/feature_contract/
actions/oracle_ledger/model_ledger. Los cuatro hashes de features deben extraerse
de la autoridad original del learner, no baselinarse desde bytes actuales sin
comparación; actions y oracle_ledger se ligan al índice/auditor del motor.
El binding se prepara antes de este diagnóstico. El runner valida todos sus
hashes; no certifica por sí mismo que quien preparó la autoridad fuera correcto.

Un estudio posterior debe usar tres controles, definidos antes de abrir labels:

- **Selección de contrato/objetivo:** candidatos no seleccionados del mismo
  ticker, día, minuto, lado y bucket delta; evita atribuir al target una diferencia
  que procede de mercado distinto. Presentar también todas las alternativas del
  estado, no sólo las parecidas al ganador.
- **Selección de timing:** todos los estados ofrecidos, incluidos los no visitados
  por el oracle; emparejar por ticker, franja15m, lado, bucket delta, mes, cobertura
  y contexto de IV/rango IB. Los límites de bins se fijan exclusivamente en TRAIN.
  No emparejar por outcome, duración futura, fill futuro ni por el propio cue que
  se está evaluando. Si falta pareja, informarlo sin descartes silenciosos.
- **Modelo causal:** comparar sus decisiones con oracle y controles sobre las
  mismas ofertas y estados, distinguiendo estados visitados de contrafactuales.
  Descripciones dentro de estados elegidos por oracle siguen condicionadas por
  selección con futuro, aunque las alternativas tengan mejores medias.

Las unidades de incertidumbre son sesiones, no miles de targets correlacionados.
Ponderar cada ticker-día y cada estado antes de acciones; mostrar cobertura,
frecuencia base de cada cue, coincidencias oracle/control y resultados de todas
las acciones cuando se autorice su lectura. Emparejar no prueba causalidad.

TRAIN2023–24 sirve para fijar representación/binning y desarrollar hipótesis;
validación temporal2025 para una comparación congelada. Los cortes semestrales
de TRAIN permiten comprobar estabilidad sin recurrir a2026. Todo2026 ya visto
es desarrollo; no se usa para rescatar reglas. Incorporar sesiones cortas de la
nueva familia auditada; los seis missing2026 son no evaluables, no pérdidas.

## Oracle restringido y modelo posterior: propuesta, no ejecución

Una comparación acotada puede conservar tres techos: oracle original; oracle
con máscara rechazo; oracle con máscara aceptación/retest. La máscara se calcula
y sella para **todas** las ofertas antes de leer cualquier outcome. El DP sólo
optimiza dentro de esa máscara; no elige retrospectivamente el mejor cue por
operación. Comparar retención de ofertas/días y de PnL del techo no prueba edge
causal: sigue conociendo el futuro. Las restricciones pueden dejar días sin
trade. El requisito>=1fill por ticker-día se sigue verificando; no forzar entradas
sin cue ni excluir esos días para fabricar cumplimiento.

Esto es una propuesta posterior, no filtros aprobados: primero comparar la
geometría continua (distancias, mechas, cambios y bandas) y su cobertura. Las
etiquetas binarias actuales resumen esa geometría; ni una mecha estrictamente
positiva ni coincidencia con una línea exacta pasan a ser gates económicos por
defecto. Cualquier futura regla de zona aproximada se fijaría por separado antes
de su DP, sin escoger la tolerancia que explique mejor sus ganadores.

Una alternativa posterior interpretable es conceptos observables→probabilidades
de target/stop/EOD, duración y distribución de payoff, comparada con net-GBT y
controles sin esos conceptos. La familia de concept-bottleneck permite intermedios
inspeccionables; su publicación no demuestra eficacia financiera ni causalidad.
[Koh et al., ICML2020](https://proceedings.mlr.press/v119/koh20a.html).

## Límites de medición

OI cuenta contratos abiertos, no inventario firmado de dealers. Con timestamp se
usa sólo información disponible al corte; sin reloj se conserva el supuesto de
disponibilidad09:30 del dato anterior. timestamp/underlying_timestamp y la demora
de1min son relojes de investigación, no recepción live acreditada. El spot y las
velas proceden de snapshots por minuto; no prueban máximos intraminuto, orden de
toques ni ejecuciones dentro de la vela. La entrada real ocurre al ask siguiente.

Gamma agregada es Black–Scholes×OI unsigned del productor, con horizonte proxy
al cierreNYSE, r=q=0. No convertir PUT en gamma negativa. Cboe distingue magnitud
de signo y explica que exposición neta exige información de compra/venta y
posición que este dataset no observa.
[Cboe, 8-sep-2023](https://www.cboe.com/insights/posts/volatility-insights-evaluating-the-market-impact-of-spx-0-dte-options/).

Las Greeks describen sensibilidades teóricas, no una descomposición exacta del
beneficio. Aquí theta/vega conservan unidades almacenadas normalizadas por spot;
no se calculan erosión monetaria, delta-gamma PnL ni shocks de volatilidad hasta
verificar unidades y convenciones de la fuente.
[OIC, Understanding Options Greeks](https://prd-web.optionseducation.org/advancedconcepts/understanding-options-greeks).
