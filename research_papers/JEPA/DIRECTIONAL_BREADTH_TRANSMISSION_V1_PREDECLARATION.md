# DIRECTIONAL_BREADTH_TRANSMISSION_V1 — predeclaración

## Hipótesis y límite anti-bucle

La dirección de QQQ/SPX/SPY puede depender del liderazgo temprano de megacaps,
amplitud small-cap y transmisión de tipos, información ausente del JEPA
price-only. V1 hace una única prueba sobre fuentes locales existentes y no crea
otro dataset. No usa opciones, Greeks, VIX, labels intrabar ni thresholds.

El diseño es adaptativo porque ya se han visto outcomes 2026 de otras familias.
Un PASS es evidencia diagnóstica y exige después replay de futuros; no autoriza
live por sí solo.

## Panel outcome-free congelado

Fuente:

```text
D:/ThetaData/data_underlying_derived/{QQQ,SPXW,SPY,AAPL,AMZN,GOOGL,META,MSFT,NFLX,NVDA,TSLA,IWM,TLT,GLD,SLV}
```

AAPL/AMZN/GOOGL/META/MSFT/NFLX/NVDA/TSLA representan liderazgo y amplitud
mega-cap; IWM amplitud broad/risk-on; TLT el canal de tipos; GLD/SLV metales y
aversión/inflación. Se usa la intersección exacta de fechas de los quince
tickers: si falta un fichero, se omite ese día para todos, nunca se imputa.

El censo outcome-free congelado excluye 28 sesiones por semanas fuente ausentes:
GOOGL 2022-08-15..19; AMZN/GOOGL 2022-09-12..16; TSLA 2023-03-13..17; GLD
2024-05-13..17; META 2025-03-17 y 2025-09-08..09; NFLX 2025-11-17..21. También
se excluyen para todo el panel 2023-06-05 —SPY/GLD/SLV inválidos— y 2024-06-03
—SLV inválido—. El resultado es 962/992 sesiones comunes hasta 2026-07-15.
VIX no entra porque ya fue probado como familia separada. Medias jornadas se
excluyen completas porque la segunda ventana no cabe antes del cierre.

## Dos ventanas fijas sin overlap

| Ventana | Features hasta | Entrada | Salida | Hold |
| --- | --- | --- | --- | ---: |
| W1 | close 10:00 | open 10:01 | open 13:01 | 180m |
| W2 | close 13:01 | open 13:02 | open 15:59 | 177m |

Se cobra 1 bp por trade. Hay dos decisiones por sesión y cero overlap. Julio MTD
hasta 2026-07-15 tiene 20 oportunidades por ticker, por lo que la frecuencia
del objetivo es matemáticamente evaluable.

## Features

Todo se calcula en memoria con barras cerradas hasta el decision timestamp:

- target: retornos 1/5/15/30m y desde apertura; RV/rango/cuerpo/location
  5/15/30m; sesión previa, ventana y día de semana;
- por los doce componentes/cross-assets: los mismos retornos y estados intradía;
- breadth de las ocho acciones: media, mediana, dispersión, mínimo, máximo y
  fracción positiva para 1/5/15/30m y desde apertura;
- divergencias target menos breadth, target menos IWM y target más TLT.

No hay IB/Fibonacci, as-of, ffill, bfill o selección de componentes.

## Modelo y walk-forward

Dos perfiles únicos:

1. `TARGET_ONLY`: solo target/calendario/ventana;
2. `BREADTH_TRANSMISSION`: TARGET_ONLY + panel/breadth.

Modelo fijo por ticker y mes: LightGBM binary, 240 árboles, learning rate 0,025,
7 hojas, profundidad 3, min-child 40, regularización fija. El label de training
es el signo del retorno futuro. Cada observación pesa
`clip(abs(return_bps),5,150) / mediana_train`, para atacar el fallo observado de
acertar el signo pero perder en movimientos grandes. Side LONG si p>=0,5, SHORT
en otro caso; no hay abstención.

Desarrollo walk-forward 2025 elige perfil por ticker usando, en orden: meses
positivos, q25 mensual, PF y nombre. La selección y hashes se versionan antes de
abrir la asociación breadth→outcome en 2026.

## Gate 2026 incluida julio MTD

Sobre enero–julio MTD, por ticker:

- WR agregado >45%;
- PF agregado >1,20;
- más de 12 trades en cada uno de los siete meses;
- net bps positivo en cada mes.

No se rescata por ventana, componente, ticker, mes, peso, seed o threshold. Un
fallo cierra esta familia de breadth para este contrato.
