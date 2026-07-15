# WEEKLY_MULTIDAY_ORACLE_V1 — predeclaración de viabilidad

## Propósito y límite anti-bucle

Este experimento no entrena un modelo ni construye un dataset de features. Es un
único audit compacto para decidir si merece la pena abrir **una** traducción
weekly multi-día. Si el techo executable descrito aquí falla, la familia se
cierra sin generar datasets ni probar horizontes, deltas, expiraciones, stops o
subgrupos alternativos.

## Universo congelado

- Tickers: `SPXW`, `QQQ`, `SPY`.
- Ventana: `2022-01-01..2025-12-31`; 2026 permanece cerrado.
- Fuente: parquets históricos `greeks` ya presentes bajo
  `D:/ThetaData/data_options/{ticker}/greeks`.
- Expiración: `front_weekly`, con `0 < DTE <= 7`, y presencia exacta de la misma
  expiración tanto en entrada como dos sesiones RTH posteriores.
- Reloj de entrada: quote exacta de `10:35 ET`. Esto permite que el Initial
  Balance fijo `09:30..10:29` esté completo sin usar información futura.
- Reloj de salida: quote exacta de `10:35 ET` dos sesiones RTH después.

## Contrato y ejecución

En cada entrada se congela por separado un CALL y un PUT:

1. `right` exacto y delta con signo correcto;
2. mínimo `abs(abs(delta) - 0.50)`;
3. desempate por menor spread relativo y después strike;
4. `ask > 0`, `bid >= 0`, `bid <= ask` y campos finitos;
5. entrada al `ask` y salida al `bid` del mismo
   `(ticker, expiration, strike, right)`.

No se permite nearest-strike en salida, mid-price, OHLC, relleno temporal,
rollover, stop sintético ni sustitución de contrato. El retorno es
`(exit_bid - entry_ask) / entry_ask`; por tanto incluye el spread de ida y
vuelta observable y todo el theta/vega/gap de las dos noches.

## Oracles declarados

- `DAILY_OVERLAP_ORACLE`: elige retrospectivamente el mejor de CALL/PUT en cada
  oportunidad. Es solo un techo no desplegable y puede solapar posiciones.
- `NON_OVERLAP_ORACLE`: misma elección futura de side, pero procesa la salida
  antes de nuevas entradas a la misma hora y rechaza entradas mientras haya una
  posición abierta por ticker. Es el techo económico relevante.
- `ALWAYS_CALL` y `ALWAYS_PUT`: controles descriptivos, no seleccionables.

No se prueban más horizontes, delta buckets, clocks, filtros VIX, reglas
IB/Fibonacci ni variantes de salida en este audit.

## Gates congeladas de continuidad

La vía solo puede avanzar a una única política causal si, para cada ticker:

- cobertura executable CALL+PUT >= 90% de las oportunidades físicas;
- el `NON_OVERLAP_ORACLE` tiene en **cada** mes observado:
  `PF > 1.30`, `WR > 50%`, PnL en R positivo y al menos 6 trades;
- concentración de los cinco mejores trades <= 35% del gross profit por
  ticker y en agregado.

El mínimo de 6 no sustituye silenciosamente la meta histórica de 18. Con un
hold exacto de dos sesiones y `reject_while_open`, 18 trades/mes por ticker es
matemáticamente incompatible; el audit reportará la capacidad real. Una futura
promoción weekly necesitará un contrato económico propio aprobado antes de
abrir sus outcomes.

## Decisión posterior única

Si todas las gates pasan, se podrá predeclarar **una** política causal de
tendencia/volatilidad que use solamente información observable en `10:35`:
Initial Balance completo y niveles Fibonacci fijos, tendencia multi-horizonte,
VIX causal y estado de delta/IV/theta/vega de entrada. Habrá como máximo un
dataset reproducible y un desarrollo cronológico. Si el oracle falla, no se
abre ese paso.
