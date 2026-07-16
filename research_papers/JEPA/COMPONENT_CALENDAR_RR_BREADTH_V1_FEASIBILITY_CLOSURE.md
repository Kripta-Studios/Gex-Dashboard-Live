# COMPONENT_CALENDAR_RR_BREADTH_V1 — cierre de factibilidad

## Veredicto

`FAILED_FREQUENCY` antes de quotes, outcomes o modelos.

Se auditó si la presión calendar-RR podía convertirse en una fuente de
amplitud independiente usando opciones de componentes grandes y otros ETF. El
censo leyó exclusivamente nombres de parquets Greek 2023–2025 y sus schemas. Una
sesión era elegible solo si el mismo trade date contenía tanto el vencimiento
0DTE exacto como al menos un vencimiento posterior. No se leyó ningún valor de
quote, IV, retorno o PnL.

## Capacidad observada

| Universo | Símbolos | Sesiones elegibles por símbolo | Mínimo mensual |
| --- | --- | ---: | ---: |
| Componentes/ETF semanales | AAPL, AMZN, GOOGL, META, MSFT, NFLX, NVDA, TSLA, TLT, GLD, SLV, HOOD, PLTR, UNH | 120 | 3 |
| IWM | IWM | 630 | 12 |

Los catorce componentes comparten esencialmente las mismas fechas semanales:
una cesta simultánea de breadth tendría como máximo 120 observaciones en 36
meses, con tres o cuatro observaciones mensuales. IWM es más frecuente, pero su
mínimo es exactamente 12 en febrero 2023, abril 2023 y febrero 2024; no cumple
el requisito estricto de más de 12 trades en cada mes. IWM solo tampoco sería
una medida de amplitud de componentes.

Todos los schemas 2023 muestreados contienen `timestamp`, `bid`, `ask` y
`delta`; el bloqueo no es de campos, sino de capacidad matemática. No se permite
forward-fill de una observación semanal para fabricar decisiones diarias, unir
expiraciones distintas ni contar varias policies sobre la misma observación.

## Evidencia reproducible

- Ventana inventariada: `20230101..20251231`.
- Ficheros Greek parseados: `20.002`.
- IDs símbolo-fecha elegibles: `2.310`.
- SHA-256 del inventario ordenado
  `symbol|expiry|trade_date|relative_path`:
  `edc928fba580a84f8bdb44d477f212b2d43467eb06d5a8f4ddd74e9df2d7bdc6`.
- SHA-256 de IDs elegibles ordenados `symbol|trade_date`:
  `5d48d297203286925602682393141ae1a32bd1261b94fc71453c93a34eba8872`.

Esta familia queda cerrada sin feature view, runner ni rentabilidad. No cambia
el edge parcial de calendar-RR en QQQ/SPY y no autoriza seleccionar semanalmente
solo meses favorables.
