# DIRECTIONAL_INTRADAY_POOLED_V1 — predeclaración

Fecha de congelación: 2026-07-16. Esta hipótesis se abre después de cerrar
`DIRECTIONAL_BREADTH_TRANSMISSION_V1`; por ello cualquier resultado 2026 será
diagnóstico adaptativo, no evidencia confirmatoria.

## Hipótesis

El fallo del hold fijo de aproximadamente tres horas puede deberse a cambio de
régimen dentro de la propia posición. Un modelo común para QQQ, SPX y SPY puede
tener más muestra y una señal direccional más estable en tramos de 53–60 minutos.
No se añade ninguna fuente ni se crea otro dataset.

## Universo y calendario

Se usan exactamente los 15 tickers del panel congelado anterior:

`QQQ, SPXW, SPY, AAPL, AMZN, GOOGL, META, MSFT, NFLX, NVDA, TSLA, IWM, TLT,
GLD, SLV`.

La unidad de calendario es la intersección exacta. Si una fecha falta o es
inválida para un solo ticker, se elimina para todos. No hay imputación, as-of ni
descarga adicional. Las 30 fechas excluidas y los hashes de fuentes deben ser
idénticos a `DIRECTIONAL_BREADTH_TRANSMISSION_V1`.

## Decisiones y ejecución

| Ventana | Features hasta | Entrada | Salida | Hold |
| --- | --- | --- | --- | ---: |
| H1 | 10:00 close | 10:01 open | 11:01 open | 60m |
| H2 | 11:01 close | 11:02 open | 12:02 open | 60m |
| H3 | 12:02 close | 12:03 open | 13:03 open | 60m |
| H4 | 13:03 close | 13:04 open | 14:04 open | 60m |
| H5 | 14:04 close | 14:05 open | 15:05 open | 60m |
| H6 | 15:05 close | 15:06 open | 15:59 open | 53m |

No hay solape. Se resta 1 bp por operación. Los fills son proxy spot del
underlying y no fills certificados de ES/NQ/MES/MNQ. Las medias jornadas se
excluyen porque no contienen el contrato horario completo.

## Features y modelos

Se reconstruyen en memoria las mismas features causales de retornos, RV,
rango, cuerpo, localización, sesión previa, componentes individuales, breadth
de ocho tecnológicas y divergencias contra IWM/TLT. Se añaden solamente tres
one-hot de ticker para el fit pooled.

Hay dos perfiles predeclarados:

- `POOLED_TARGET_ONLY`: target + reloj + ticker.
- `POOLED_BREADTH_TRANSMISSION`: target + reloj + ticker + panel completo.

Ambos usan un único LightGBM pooled por fold mensual, clasificación binaria del
signo y pesos por magnitud absoluta futura recortada a [5,150] bps. Hiperparámetros:
240 árboles, learning rate 0,025, 7 hojas, depth 3, min child 80, subsample 0,8,
colsample 0,8, L1 0,05 y L2 0,5. `p>=0,5` es LONG; el resto SHORT. No hay
abstención, threshold sweep, stop, take-profit ni selección de ventana.

## Desarrollo y freeze

El walk-forward 2025 entrena cada mes solo con fechas anteriores. Se elige un
único perfil global para los tres tickers ordenando, en este orden:

1. peor número de meses positivos entre tickers;
2. total de meses positivos;
3. peor PF agregado entre tickers;
4. peor cuartil mensual de PnL;
5. nombre del perfil.

La evaluación 2026 no puede arrancar hasta que runner, predeclaración, selección
y source inventory de desarrollo estén committed. No se puede cambiar el perfil
por ticker después de ver 2026.

## Gate 2026

Para cada QQQ, SPX y SPY, sobre enero–junio y julio MTD hasta 2026-07-15:

- WR >45%;
- PF >1,20;
- más de 12 trades en cada mes;
- PnL neto positivo en los siete meses.

Los tres tickers deben pasar simultáneamente. Un fallo cierra V1 sin rescatar
horas, tickers, umbrales o subgrupos post-hoc y sin modificar producción.

## Preflights cerrados antes de V1

- Router exponencial sobre target/breadth y sus inversos: no supera PF estable
  en SPX/SPY durante 2025.
- Malla conservadora de 72 stop/TP: mejor PF mínimo 0,965.
- Gap nocturno long/momentum/reversal: PF aproximado 0,89–1,08 y varios meses
  negativos. No se promueven ni se evaluarán sobre 2026.
