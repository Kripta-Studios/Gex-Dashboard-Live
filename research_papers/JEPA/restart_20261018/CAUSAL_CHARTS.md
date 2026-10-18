# Seis gráficos de zonas disponibles antes de decidir

Fecha: 2026-10-18. Se fijaron los días 2023-01-03 y 2026-01-02 y los tickers SPXW, SPY y QQQ antes de renderizar. No se eligió ningún gráfico por rentabilidad o comportamiento posterior; no se calcularon retornos ni se abrieron precios posteriores al corte.

Generador: `create_causal_chart.py`. PNGs y manifest:

```text
D:/GexResearchArtifacts/restart_20261018/causal_charts/{ticker}_{day}_causal_1235.png
D:/GexResearchArtifacts/restart_20261018/causal_charts/manifest.json
```

Ejemplo donde ambos máximos OI quedan dentro de la escala del panel: `QQQ_20260102_causal_1235.png`. Es una ilustración de la representación, no una operación propuesta ni evidencia de edge.

## Qué muestran

- Dos paneles con velas **muestreadas** de 5 y 15 minutos; solo bins completos hasta 12:30, construidos con muestras desde 09:30 hasta 12:29.
- IB **muestreado** de 09:30..10:29; 0=IB low y 1=IB high. Ratios fijos adicionales −0,618, −0,272, 1,272 y 1,618. Las líneas IB/Fibonacci comienzan a las 10:30, cuando se conoce ese rango, y se proyectan como niveles conocidos.
- El strike de mayor OI positivo de cada lado CALL/PUT (empate: menor strike), sin consultar movimientos futuros. Banda suave de anchura ±0,10 veces el IB: CALL morado, PUT ámbar. El subtítulo conserva ambos strikes aunque alguno quede fuera de la escala. No se elige otro strike para hacer más atractivo el ejemplo.
- Decisión marcada a las 12:35, corte de features a las 12:34 y espacio derecho sin precios futuros. La última observación de precio mostrada es 12:29; así las velas están completas antes de decidir incluso con un minuto de demora asumida.

El manifest conserva hashes SHA256 de las fuentes, proyección de filas, reloj utilizado, cortes, datos faltantes, IB y máximos OI. El hashing lee bytes sin interpretar precios posteriores; la lectura de valores de Greeks está filtrada por reloj a [09:30,12:30). No se leen bid/ask, labels, salidas o métricas económicas para estos gráficos.

## Qué no debe inferirse del dibujo

Estos OHLC no son extremos intraminuto completos ni velas oficiales de un feed de spot. Los valores inválidos y discrepancias entre contratos quedan NaN; no se rellenan. SPXW tiene 59/60 muestras de IB en ambos días por apertura cero; SPY/QQQ tienen 60/60. El pie informa la cobertura y la vela parcial lleva hatch.

OI es concentración por strike, no posición neta de dealers ni gamma observada. Los datos OI con timestamp se restringen a registros <=12:34. Los archivos sin reloj usan la convención de disponibilidad 09:30 asumida, indicada en el pie; no es recepción histórica observada. Los snapshots Greek usan timestamp nativo cuando está presente y underlying_timestamp como reloj asumido cuando falta, también indicado.

Ver que un precio se acerca, cruza o vuelve a un nivel en la parte conocida no permite afirmar que el nivel prediga el futuro. Esa pregunta corresponde a los controles cronológicos del benchmark de zonas frente a precio solo y placebo. Los gráficos ilustran los inputs causales disponibles y los conceptos de geometría, proximidad y bandas; **el GBT actual no consume estas imágenes ni el tensor completo de velas dibujado**. Su entrada contiene resúmenes numéricos, lags de retornos, últimas velas 5/15m y campos de niveles. La imagen no es una reproducción literal de ese vector ni prueba que el modelo perciba toda la estructura visual.

Se inspeccionaron visualmente los PNG de SPY 2026-01-02, SPXW 2023-01-03 y QQQ 2026-01-02: paneles, velas, ejes, niveles y pies legibles. Las seis salidas se generaron sin incidencias.
