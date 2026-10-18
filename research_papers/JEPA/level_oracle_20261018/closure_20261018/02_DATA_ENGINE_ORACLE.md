# Fuentes locales, causalidad y oracle

## Inventario y lectura

La investigación se reinició revisando el repositorio y las descargas existentes en `D:/ThetaData`. No se usó una suscripción, API, Theta Terminal, nueva captura de mercado, bróker ni VPS. La documentación primaria de métodos se consultó por web; eso es distinto de descargar mercado.

El censo encontró366555 archivos,260.373GiB y235018 parquets, con37 schemas y cero errores al leer footers. Un inventario de schemas acredita estructura, no calidad universal de valores. Había3332 archivos Greek0DTE:1091QQQ,1091SPY y1150SPXW. En2023/2024/2025 los tres tienen250/252/250 fechas por ticker;2026 llega hasta septiembre en el inventario, aunque las evaluaciones descritas se limitan a junio.

Los lectores de referencia y las rutas se explican en [DATA_INVENTORY](../../restart_20261018/DATA_INVENTORY.md), [SOURCE_FEASIBILITY](../../restart_20261018/SOURCE_FEASIBILITY.md) y [CLOCK_EQUIVALENCE](../../restart_20261018/CLOCK_EQUIVALENCE.md). `data_options` es la fuente principal. No se adoptó como verdad causal el spot reparado de `data_underlying_derived`: se reconstruyó spot compartido desde Greek, con comprobaciones de consistencia, edad y máscaras.

### Los dos timestamps

El usuario señaló correctamente que los archivos2024–2026 no debían descartarse sólo por no tener un campo llamado `timestamp`. La inspección inicial comparó1889312filas en15archivos con ambos relojes y encontró igualdad exacta. La construcción ampliada comparó141978747filas en1096archivos con ambos campos, también sin diferencias. Otros1499 archivos del experimento completo usaron `underlying_timestamp` almacenado.

Esta evidencia respalda la convención de lectura de este experimento. **No prueba el instante de recepción live de las cotizaciones.** Cada fuente conserva el tipo de reloj. OI sin timestamp requiere el supuesto de información del cierre previo disponible a09:30NY; no se presenta como recepción observada. Las filas inválidas y OI desconocido se conservan mediante máscaras, sin rellenar el futuro.

### Calendario

El oracle original y los primeros modelos usaron2595ticker-días completos de2601esperados. Después se incorporó un motor explícito `SessionClock` con24ticker-días cortos:2619disponibles de2625esperados. Seis ausencias corresponden a SPY/QQQ en1,9y15deabril2026. Las ausencias son NO_EVALUABLE; no se confunden con cero PnL ni se excluyen silenciosamente del denominador.

| Alcance | TRAIN2023–24 | Validación2025 | Desarrollo2026H1 |
|---|---:|---:|---:|
| Sesiones completas disponibles | 1491 | 741 | 363 |
| Añadidas cortas | 15 | 9 | 0 |
| Calendario esperado con cortas | 1506 | 750 | 369 |

Los modelos originalmente ajustados sobre1491días no se vuelven a presentar como si hubieran incorporado los15cortos TRAIN. La comparación compacta y la futura424 sí incluyen los9cortos de validación; el mensual preparó todos los días disponibles.

## Motor económico de niveles

El primer benchmark exploratorio usaba salidas a30minutos. Se conservó como antecedente y fue sustituido para la petición de niveles. **El motor oracle/aprendices posterior no tiene un hold fijo de30minutos.**

1. IB=min/max de los60 snapshots09:30–10:29NY; exige al menos57válidos y rango positivo. Sólo se decide desde10:30. Son extremos muestreados, no extremos de cada transacción intraminuto.
2. Fibonacci: `L(r)=IB_low+r*(IB_high-IB_low)`, con ratios `[-1,-.618,-.272,0,.236,.382,.5,.618,.786,1,1.272,1.618,2]`. Cero=low y uno=high.
3. Se añaden top3strikes CALL y PUT por OI y por proxy gamma×OI. Gamma se calcula desde IV con Black–Scholes,r=q=0 y horizonte de cierre declarado. No se conoce inventario firmado de dealers.
4. Banda aproximada `b=max(.05*IB_range,.0001*spot)`. Se agrupan niveles sólo si el diámetro total del grupo≤2b; no se encadenan niveles lejanos por vecinos.
5. Entrada ofrecida cuando spot cae en una zona. Cada CALL/PUT puede escoger un objetivo conocido en su dirección, separado>2b y≤3IB; el stop es el nivel opuesto más cercano separado>2b. Objetivo/stop/banda quedan congelados; niveles intermedios no provocan salida.
6. Contrato cercano a abs(delta).35/.50/.65; desempate por strike, deduplicación y misma información para oracle/aprendiz. No se reemplaza por otro contrato tras ver el fill.
7. Decisión en i, compra al ask de i+1. Trigger observado con spot válido, venta al bid del minuto siguiente; prioridad stop si coinciden. Posición única por ticker. Tras fill, próxima decisión en exit+1; tras NO_FILL, siguiente minuto.
8. Cierre obligatorio15:55 en sesión completa y12:55 en corta. Últimas decisiones15:45/12:45. Falta de quote de salida programada se trata a cero, conservando la operación.
9. Un contrato,multiplicador100,comisión1.30USD/lado,slippage.01/lado base y.02adverso. No hay intereses, capital compuesto ni cálculo de retorno de cuenta.

Las paredes se definen por concentración observable de contratos. Interpretarlas como imanes o soportes es una hipótesis a contrastar: el motor no prueba que causen rebotes por ofrecer acciones cerca de ellas.

## Qué ve un modelo causal

`features.py` produce81variables base,20tokens de45canales y20mapas de5×64posiciones, además de máscaras. Son12velas5m y8velas15m, ancladas a09:30 y terminadas antes del estado. Incluyen OHLC muestreado, cuerpo, mechas, posición relativa al IB, contexto de griegas/OI y mapas Fib/OIcall/OIput/gammacall/gammaput. Los campos espaciales usan gaussianas de anchura.08IB y se normalizan por la propia vela, no por máximos del día futuro.

A10:30 sólo hay cuatro velas15m anteriores desde apertura: las otras cuatro se enmascaran. Las coordenadas antiguas pueden expresarse usando el IB completo porque éste ya es conocido al decidir≥10:30. Ningún modelo recibe precio de salida, duración futura, beneficio, contrato elegido por oracle o continuación realizada como entrada. Esos valores sólo son etiquetas TRAIN en sidecars separados.

La unión de contratos de todo el día es un índice técnico, no una fuente de conteos futuros. Los denominadores y acciones se limitan a identidades conocidas hasta el corte. Las pruebas alteran datos futuros y añaden contratos tardíos para comprobar invariancia del prefijo.

## Oracle DP y comportamiento observado

El oracle enumera las mismas acciones causales, después conoce sus resultados futuros y resuelve `V(i)=max(V(i+1),net(a)+V(exit(a)+1))`, con WAIT primero en empates. Puede escoger objetivos lejanos y liberar la posición para otra oportunidad. No se reduce a escoger la mejor operación aislada.

Auditoría completa: `PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT`, SHA256 `cbbe61d0a3fa7619447b7301d4c4b2fd52c487e11450d4904efee381fc3bf22d`. El universo original contiene15395840acciones y36019trades; neto9190416.60USD base y9118378.60adverso. En base todos los trades elegidos ganan, mínimo.40USD; en adverso371pierden porque se aplica el coste mayor a la misma trayectoria base.

Esto es esperable por construcción: WAIT permite evitar cualquier neto negativo viendo el futuro. Su100%deacierto y PFsin pérdidas no estiman una tasa de acierto alcanzable. La desigualdad entre esperanza del máximo retrospectivo y máximo de esperanzas causales explica parte de la brecha.

El [análisis de comportamiento](../ORACLE_BEHAVIOR.md) encontró:

- Entre70.4–72.4% de alternativas del mismo estado escogido pierde dinero.
- Entre42.2–45.8% de elecciones no maximiza el PnL aislado, por coordinación temporal.
- Medianas de hold7–9minutos; no una duración impuesta.
- Frecuente elección de delta alta; el objetivo en USD absolutos no iguala capital entre contratos.
- Sólo aproximadamente39–45% de fills sigue cerca de la zona: la decisión sí estaba dentro, pero el fill es un minuto después. No se ocultó esa diferencia.
- El predominio de rechazo geométrico o de Fibonacci depende también del conjunto de acciones programadas; no demuestra causalidad económica de esos niveles.

Las gráficas de sesiones fijadas y perfiles se conservan como ilustración retrospectiva. No fueron un filtro posthoc para seleccionar los días ganadores de una política causal.
