# Continuación: requisitos abiertos y siguiente evidencia

## Checkpoint 1 de noviembre, 16:05 UTC

PROGRESS: riesgo comparable y contexto causal están cerrados. El riesgo de
5.000 USD por entrada reveló H1 −14.931 USD y Q3 +9.872,80 USD para BASE18.
Dos nuevos modelos predeclarados se ajustaron una sola vez: CATEGORY30 da
−32.666,20 USD y CONTEXT182 +41.871 USD adversos H1. Este último empeora la
métrica primaria probabilística (logloss1,247644 frente a1,204875), gana sólo
3/6meses y sinabril suma−2.508,20 USD. No selección ni promoción.

Productor manifest662ac63e y auditor independiente bb661fe9 cerrados exit0;
reconstrucción TRAIN/transform/inferencia/calibración/EV/seis libros PASS
dado parámetros, sin refit ni raw. NO RELANZAR. Véase
[resultado completo](CONTEXT_MODEL_RESULT_20261101.md).

Siguiente trabajo autorizado: preparar contrato y wrapper de contexto Q3,
inventariar/pinear fuentes exactas antes de valores, construir sólo state60
sin acciones/labels/oracle, y comparar contra funciones congeladas. La lectura
estructural encontró318/330fuentes:153Greek y165OI con reloj nativo, sin
demostrar aún calidad de valores o state_valid. Conservar12Greeks ausentes.
Después aplicar los tres modelos congelados al mismo Q3parcial, mismos costes,
riesgo y abstención, sin refit/recalibración ni seleccionar sólo el positivo.

Q3 ya visto sigue SEEN_DEVELOPMENT; no se presenta como holdout limpio. La
hipótesis contextual no pasa su criterio probabilístico primario y su economía
necesita contraste temporal. El objetivo completo IB/Fibonacci/walls sigue
abierto; la duración fija H2 no implementa entradas por toque ni salidas por
zonas. No nuevos procesos activos de esta etapa, goal activo y promociónfalse.

## Historia de la etapa anterior

Clasificación del turno anterior: PROGRESS. Cerró dataset, modelo y backtest
weekly H2, reconstrucción independiente y trazabilidad de la mayor operación.
El goal general permanece activo; un backtest positivo no lo completa.

Evidencia vigente inspeccionada de nuevo: OOF_FULL_H1_RESULT_20261101.md,
H2_WEEKLY_RESULT_20261101.md y audit d9f1602c. El OOF 0DTE de enero a junio
está completo y sus seis políticas pierden en agregado. Weekly H2 da +11486USD
adversos, pero el resultado depende de SPXW/abril/una operación. No hay todavía
rentabilidad temporal robusta ni equivalencia operable del oracle retrospectivo.

La instrucción posterior del usuario amplía la investigación a weekly multi-day
con probabilidades/EV y permite no operar. El baseline H2 no incorpora aún
Fibonacci IB ni walls. Esa parte del objetivo original sigue abierta; no se
redefine como completada por el experimento de duración fija.

Dos siguientes acciones dentro del alcance autorizado:

1. Sensibilidad descriptiva del libro H1 ya sellado: costes, retorno por prima
   comprometida, concentración y remuestreo temporal exploratorio. Mismos trades;
   sin selección, nuevo ajuste ni afirmación de cartera ejecutable normalizada.
2. Aplicar exactamente el mismo estado estadístico a julio1–septiembre17 de2026.
   No fit, recalibración, cambio de costes/threshold, rescate de ticker o carry H1.
   Periodo parcial, 55 sesiones; última entrada H2 septiembre15. Conservar las
   ausencias SPY/QQQ, sin reducir el calendario a fechas disponibles.

El censo de nombres encontró 55 fechas SPXW y 49 SPY/QQQ; seis ausencias de
series weekly SPY/QQQ: julio1/7/10/16, agosto26 y septiembre1. Es cobertura
nominal, no quotes ni fills. La exposición previa de julio está documentada en
results/_diagnostics/directional_semantic_jepa_v1_evaluation_202601_20260715/SUMMARY.md;
el linaje agosto/septiembre no acredita datos vírgenes. Se etiqueta toda la
continuación Q3_PARTIAL_2026_SEEN_DEVELOPMENT, nunca holdout limpio.

Calendario nuevo JSON/Parquet de165filas: ac9bd256/e16ef041, reconciliados.
Fuentes oficiales de fechas: https://www.cboe.com/about/hours/us-options y
https://nasdaqtrader.com/Trader.aspx?id=Calendar, consultadas1noviembre.
Cierres julio3 y septiembre7, sin sesiones cortas en el tramo. close_i390 es
referencia SessionClock del subyacente, no afirmación sobre hora de cierre de
cada opción. No se descargan datos de mercado ni se usa una API de mercado.

No hay procesos anteriores que reanudar ni replay de H1. Las nuevas ejecuciones
usan raíces independientes y sus bindings antes de valores. Producción/bróker/
VPS y cambios ajenos intactos. technical_ready/promotion_approved=false.

## Cierre de esta etapa, 1 de noviembre a las 15:15 UTC aproximadamente

Las dos acciones anteriores están completas. Diagnóstico H1 publicado y
reconciliado; extensión Q3 cerrada con +6966,20USD adversos/28operaciones.
Auditor independiente ff62f16e reproduce180scores y8libros sinfit, sobre pesos
congelados. Comprobación puntual de la mayor operación PASS04424cf8 desde
dosparquets. Los75tradesH1 y28Q3 son todosCALL; el positivoQ3 depende otra vez
de una ganancia mayor que el neto total. No hay robustez acreditada ni selección.

Siguiente frontera científica: fijar un protocolo de riesgo monetario comparable
y variables causales de escenarios que permita contrastar la concentración,
incluyendo IB/Fibonacci/walls donde haya snapshots con reloj admisible.
Es una dirección pendiente de contrato, no una familia ya ejecutada ni una
promoción de SPXW. No alterar los experimentos cerrados ni reutilizar2026 como
holdout limpio. El objetivo general permanece activo y no se marca completo.
