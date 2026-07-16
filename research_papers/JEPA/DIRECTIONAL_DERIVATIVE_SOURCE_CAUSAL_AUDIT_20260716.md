# Auditoría causal de la fuente derivada direccional — 2026-07-16

Estado: `REJECTED_AS_MODEL_INPUT_WITHOUT_REBUILD`

## Alcance

Auditoría outcome-free y de solo lectura de:

```text
D:/ThetaData/data_training_input/INPUT_{SPXW,QQQ,SPY}_*.parquet
D:/ThetaData/mega_data_factory.py
D:/ThetaData/stats.py
D:/ThetaData/data_options/{SPXW,QQQ,SPY}/greeks
services/compute_features.py
services/realtime_feed.py
```

No se generó otro dataset, no se ajustó un modelo y no se abrió un label o PnL.

## Inventario observado

- 535 ficheros preparados por ticker, 2024-01-02..2026-02-19.
- 534 sesiones tienen barra 10:35; 2026-02-19 termina a las 09:37.
- Los ficheros raw de griegas llegan hasta 2026-07-15.
- En 2026 existen 0DTE raw para 20/19/22/21/20/21 sesiones de enero a junio en
  SPXW; QQQ/SPY tienen 18 en abril frente a 21 sesiones del panel underlying.
- Las once variables 0DTE auditadas a las 10:35 son finitas y no constantes en
  las 534 sesiones completas. No hay degeneración numérica trivial.

## Timestamp nativo en raw 0DTE

| Ticker | 2022 con/sin | 2023 con/sin | 2024 con/sin | 2025 con/sin | 2026 con/sin hasta 07-15 |
| --- | ---: | ---: | ---: | ---: | ---: |
| SPXW | 220/0 | 250/0 | 0/252 | 0/250 | 103/30 |
| QQQ | 170/0 | 250/0 | 20/232 | 45/205 | 112/15 |
| SPY | 170/0 | 250/0 | 0/252 | 0/250 | 97/30 |

En muestras donde existen `timestamp` y `underlying_timestamp`, la diferencia
es exactamente cero en todas las filas. No se usa ese hallazgo para rellenar las
sesiones donde falta `timestamp`: hacerlo violaría el contrato causal vigente.

## Fallos de contrato

1. El productor agrupa por `underlying_timestamp`, no por timestamp nativo de la
   opción.
2. Aplica `ffill().bfill().fillna(0)` a todas las columnas derivadas. Aunque una
   sesión concreta tenga snapshot exacto 10:35, el artefacto permite leakage y no
   registra qué filas fueron rellenadas.
3. Captura cualquier excepción y devuelve silencio; no existe manifest de
   errores, cobertura exacta ni provenance por sesión.
4. `wk` significa segunda expiración disponible y varía entre 1 y 8 días. En 111
   viernes completos por ticker las columnas ni siquiera existen; solo 423/535
   artefactos tienen `wk_net_gamma` finito a las 10:35.
5. Offline solo calcula gamma/vanna/charm y algunos niveles. Live calcula además
   dgex, zomma, delta, vega, vomma y usa filtros/agregaciones diferentes. No hay
   equivalencia offline/live.

## Conclusión

La fuente contiene variación económica potencial, pero el agregado preparado no
puede decidir si esa variación tiene alpha porque falla antes la causalidad y la
paridad. No debe añadirse al JEPA ni utilizarse para argumentar que «faltan
griegas». Una reconstrucción futura tendría que partir de claves/timestamps
nativos sellados, expiraciones explícitas y la misma función del runtime. Hasta
entonces, ampliar la red con estas columnas solo añade una vía de leakage.
