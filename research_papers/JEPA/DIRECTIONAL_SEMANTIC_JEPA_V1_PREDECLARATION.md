# DIRECTIONAL_SEMANTIC_JEPA_V1 — predeclaración

## Pregunta y límite anti-bucle

¿Existe una señal causal sobre la dirección del subyacente a tres horas que
pueda sobrevivir sin theta de opciones? V1 es una única prueba price-first. Lee
los OHLC de un minuto ya existentes en memoria y escribe modelos, predicciones y
ledgers; no crea otro dataset de features ni explora horas, horizontes,
thresholds o arquitecturas después de abrir 2026.

Este resultado es una gate de señal spot, no un backtest ejecutable de futuros.
Un PASS exigiría después datos bid/ask de ES/NQ/MES/MNQ y un contrato de sizing,
roll, margen y fills separado. No se convertirá un close/open spot en fill de
futuros por afirmación.

## Fuentes y universo

Fuentes únicas:

```text
D:/ThetaData/data_underlying_derived/{QQQ,SPXW,SPY}/YYYY/MM/*.parquet
```

Cada fichero debe tener `symbol,date,timestamp,open,high,low,close,tick_count`,
timestamps únicos de minuto y envelope OHLC válido. Las tres series deben tener
la misma sesión y las claves requeridas. Inventario outcome-free observado:

- 2022-08-01..2025-12-31: 859 sesiones por ticker;
- 2026-01-01..2026-07-15: 133 por ticker;
- enero–junio 2026: 20/19/22/21/20/21 sesiones;
- julio MTD hasta 15 de julio: 10 sesiones.

Las medias jornadas de EE.UU. se excluyen mediante una lista congelada porque
10:36+180m cruza el cierre RTH de 13:00. No se deducen por el outcome ni se usa
el print sintético posterior a cierre.

SPY 2023-06-05 queda excluido junto con QQQ/SPXW para conservar el panel
cross-market: el audit underlying previo ya había probado tres barras 09:54–
09:56 con envelope inválido. Eran out-of-scope para H-FLOW desde 10:19, pero sí
entran en esta secuencia 09:30–10:35; no se imputan ni se bfill.

## Reloj, fill y label

- Features observables hasta el cierre de la barra 10:35 ET.
- Entrada spot-proxy: `open` exacto 10:36.
- Salida spot-proxy: `open` exacto 13:36.
- Hold exacto: 180 minutos.
- Una posición por ticker/día; por construcción no hay overlap.
- `gross_bps = side * log(exit_open / entry_open) * 10.000`.
- `net_bps = gross_bps - 1,0`.
- Win si `net_bps > 0`.

No se usa close 10:35 como fill, EOD truncation, as-of, forward-fill, TP/SL ni
outcome intrabar. El coste de 1 bp es una fricción spot conservadora pero no
sustituye un replay de futuros.

## Features técnicas causales

Por ticker y para los tres mercados como contexto:

- retornos log 1/5/15/30/60m y desde apertura;
- RV de retornos 5/15/30/60m;
- rango, cuerpo y posición de cierre 5/15/30/60m;
- gap desde el close RTH previo;
- rango/retorno/posición de cierre de la sesión previa;
- Initial Balance fijo 09:30–10:29, distancia a high/low, rango y posición;
- distancias a las ocho extensiones fijas 1,272/1,618/2,0/2,618 arriba/abajo;
- dispersión cross-market y contexto horario/día de semana.

El IB nunca se consume antes de terminar 10:29. Las extensiones Fibonacci son
transformaciones fijas, no se elige la que mejor funcionó ese día.

## JEPA semántico congelado

Entrada multivariada: 66 minutos 09:30–10:35 de los tres tickers, con seis
canales por ticker: retorno 1m, rango, cuerpo, close-location, distancia a open
y `log1p(tick_count)`. La normalización robusta se ajusta solo al pasado.

Encoder GRU compartido (`hidden=64`, `latent=24`) y teacher EMA. El predictor
estima el embedding teacher de ventanas que terminan a +15, +60 y +180m.
Las ventanas de pretraining terminan cada 15 minutos entre 10:35 y 12:50; el
último target +180m termina 15:50 y nunca cruza la sesión.
Durante train el student recibe simultáneamente:

- máscara temporal coherente de un bloque continuo de 6–18 minutos;
- dropout de un ticker completo en 25% de las muestras;
- dropout aleatorio de canales en 10%.

Cuatro canales de máscara distinguen corrupción de un cero económico real. El
teacher ve la secuencia intacta. Loss primaria SmoothL1 en espacio latente más
regularización de varianza/covarianza para evitar colapso. No hay label de
dirección, `target` 0DTE ni PnL en el pretraining.

Selección de época: train 2022-08..2024, validación 2025, máximo 25 épocas,
seed 20260716. Tras elegir `best_epoch`, se reentrena desde cero exactamente ese
número de épocas con todo 2022-08..2025. Ese encoder queda congelado para 2026.

## Downstream residual y perfiles

Para cada ticker/mes se entrena solo con días anteriores al primer día del mes.
Una Ridge estandarizada predice el retorno desde persistencia/tendencia. Dos
modelos LightGBM Huber fijos aprenden el residual:

1. `TECH_RESIDUAL`: features técnicas;
2. `SEMANTIC_RESIDUAL`: técnicas + latent JEPA, cambio latent 10:30→10:35 y
   seis resúmenes de desplazamiento/coseno predicho.

Controles no seleccionables: `ALWAYS_LONG` y `PERSISTENCE_RIDGE`. Parámetros
LightGBM fijos: 240 árboles, learning rate 0,025, 7 leaves, depth 3,
min-child-samples 40, subsample/colsample 0,8, seed congelada. La side es el
signo del retorno predicho; no hay abstención ni threshold.

## Desarrollo cerrado y selección

Fase `development` produce predicciones walk-forward de enero–diciembre 2025.
2026 no se lee. Por ticker se elige entre los dos perfiles residuales con orden
determinista:

1. más meses 2025 con `net_bps > 0`;
2. mayor percentil 25 del net mensual;
3. mayor PF agregado;
4. `profile_id` lexicográfico.

La selección, hashes de fuentes/código/modelo y métricas compactas deben quedar
committed antes de ejecutar `evaluation`. No se exige que 2025 pase la gate: es
desarrollo y la prueba decisiva es el holdout 2026.

## Evaluación one-shot 2026

La fase `evaluation` verifica el manifest de desarrollo y abre una vez
2026-01-01..2026-07-15. El perfil por ticker no puede cambiar. El downstream se
reentrena al inicio de cada mes con todos los meses ya completados; nunca usa el
mes evaluado. El encoder permanece congelado en 2025.

Gate por ticker sobre meses completos enero–junio:

- WR agregado `>45%`;
- PF agregado `>1,20`;
- más de 12 trades en cada mes;
- `net_bps > 0` en cada mes.

Julio se informa como `202607_MTD`. Con solo diez sesiones y una decisión diaria
no puede pasar aún la frecuencia mensual; esto no se rescata añadiendo entradas
post-outcome. Al terminar julio, el mismo artefacto puede extender el ledger sin
reselección.

Un fracaso cierra V1. No se rescatan tickers, meses, seeds, máscaras, costes,
horas, horizons, perfiles ni subsets después de ver 2026.
