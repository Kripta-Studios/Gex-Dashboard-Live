# DIRECTIONAL_GLOBEX_CROSS_ASSET_V1 — predeclaración

Fecha de congelación: 2026-07-16. Esta es una fuente nueva, posterior al cierre
de price-only, breadth, VIX y superficie 0DTE.

## Hipótesis

La sesión Globex y la transmisión entre futuros de índices, tipos, oro y crudo
pueden contener información causal que no aparece en las barras RTH de
QQQ/SPXW/SPY. El objetivo es predecir el signo del subyacente cash y evitar el
theta de opciones; no se usan labels de opciones.

## Fuente raw congelada

Yahoo Chart API, futuros continuos 60m, periodo exacto `[2024-07-17 00:00 UTC,
2026-07-16 00:00 UTC)`:

- `ES=F`, `NQ=F`, `YM=F`, `RTY=F`;
- `ZN=F`, `GC=F`, `CL=F`.

`VX=F` devolvió HTTP 404 en el preflight y se excluye antes de outcomes. La
captura preservará bytes HTTP exactos, URL, SHA-256, timestamps, metadatos y
arrays OHLCV. Será inmutable y se almacenará fuera del repo en
`D:/ThetaData/futures_yahoo_60m_20240717_20260715_v1`.

Limitación: son continuos de investigación, no contratos/fills broker-grade.
Los retornos horarios se recortan a ±300 bps y se añade flag de salto >200 bps
para reducir contaminación de roll. Esta prueba no autoriza trading de futuros.

## Panel y tratamiento de faltantes

Se usan todos los futuros disponibles anteriores y el panel cash de 15 tickers
ya sellado: QQQ/SPXW/SPY, AAPL, AMZN, GOOGL, META, MSFT, NFLX, NVDA, TSLA,
IWM, TLT, GLD y SLV.

Para cada decisión, se exige disponibilidad exacta en los siete futuros y en
los 15 tickers cash. Si falta una barra, día o semana en cualquiera, esa decisión
se elimina para todos. No hay forward fill entre sesiones, as-of posterior,
imputación ni descarga selectiva por outcome.

## Reloj y ejecución

- W1: features cash hasta close 10:00; futuros solo con barra horaria cuyo inicio
  es anterior a 10:00; entrada open cash 10:01; salida open 13:01; 180m.
- W2: features cash hasta close 13:01; última barra futura permitida 12:00;
  entrada 13:02; salida 15:59; 177m.
- Coste: 1 bp por trade; cero solape; dos decisiones por sesión.
- Julio MTD tiene capacidad matemática de 20 trades por ticker.

Features futures fijas por símbolo: retornos 1/3/6h, overnight 18:00→09:00,
Asia 20:00→03:00, Europa 03:00→09:00, premarket 07:00→09:00, rango/RV 3/6h,
volumen 1h y ratio contra mediana de 20 barras, más spreads ES-NQ, ES-RTY,
ES-ZN, oro-bonos y crudo-bonos. Todos los segmentos usan solo barras completadas.

## Modelos y selección

Un LightGBM pooled para QQQ/SPX/SPY por fold mensual, con one-hot ticker:

- `POOLED_BREADTH_CONTROL`: las 327 features cash ya definidas en el runner
  pooled/breadth.
- `POOLED_GLOBEX_CROSS_ASSET`: control + features de los siete futuros.

Hiperparámetros fijos: binary, 240 árboles, learning rate 0,025, 15 hojas,
depth 4, min child 60, subsample/colsample 0,8, L1 0,05, L2 0,5; pesos por
magnitud futura recortada a [5,150] bps; `p>=0,5` LONG. Sin abstención,
threshold, stop, TP ni selección de ventana.

Walk-forward 2025 entrena cada mes solo con fechas anteriores. Un único perfil
global se ordena por peor número de meses positivos, total de meses positivos,
peor PF, peor cuartil mensual y nombre. Solo avanza a 2026 si GLOBEX es elegido
y, para cada ticker, PF>1,10, WR>45%, >=8/12 meses positivos y >12 trades/mes.

Si avanza, runner/selección/hashes se commitean antes del único one-shot
enero–julio MTD 2026. Gate final por ticker: WR>45%, PF>1,20, >12 trades en
cada mes y PnL positivo en los siete meses. La evaluación es adaptativa porque
otros resultados 2026 ya son conocidos; no es evidencia confirmatoria.
