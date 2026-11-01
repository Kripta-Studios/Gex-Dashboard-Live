# Continuación: requisitos abiertos y siguiente evidencia

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
