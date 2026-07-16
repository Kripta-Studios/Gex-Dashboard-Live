# DIRECTIONAL_BREADTH_TRANSMISSION_V1 — cierre 2026

## Veredicto

`CLOSED_ADAPTIVE_DIAGNOSTIC_GATE`. El panel causal conjunto de 15 tickers no
supera la gate económica en QQQ, SPX ni SPY. La familia queda cerrada sin
seleccionar ventanas, meses, tickers o umbrales después del resultado.

No se creó un dataset nuevo: se revalidaron los parquets locales y se calculó el
panel en memoria. Se usó la intersección exacta de fechas de todos los tickers.
Si faltaba o era inválida una sesión en cualquier componente, esa fecha se
eliminó para los 15 tickers. Quedaron 962 sesiones comunes hasta 2026-07-15.

## Contrato evaluado

- Perfil `BREADTH_TRANSMISSION` elegido para los tres tickers únicamente con el
  walk-forward de desarrollo de 2025.
- Dos posiciones direccionales no solapadas por sesión: 10:01–13:01 y
  13:02–15:59.
- Coste fijo de 1 bp por operación.
- Julio es MTD hasta 2026-07-15.
- Los precios son proxy spot del underlying, no fills certificados de futuros.
- Es un diagnóstico adaptativo porque ya se habían observado otros resultados
  de 2026; no es evidencia confirmatoria ni autoriza producción.

## Resultado agregado

| Ticker | Trades | WR | PF | PnL neto | Meses positivos | Mínimo trades/mes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 266 | 48,87% | 0,956 | -282,16 bps | 3/7 | 20 |
| SPX | 266 | 48,87% | 0,964 | -162,50 bps | 3/7 | 20 |
| SPY | 266 | 50,38% | 1,049 | +214,75 bps | 3/7 | 20 |

La frecuencia pasa holgadamente, pero la rentabilidad y la estabilidad mensual
fallan. Por tanto, el problema observado no puede atribuirse al theta de 0DTE:
la señal direccional spot de aproximadamente tres horas tampoco domina.

## Diagnóstico por ventana

En desarrollo 2025 la segunda ventana era la contribución favorable; en 2026
la relación cambió. En la evaluación, W1 produjo +304/+310 bps en QQQ/SPY pero
W2 perdió -586/-96 bps, mientras SPX perdió en ambas. Esta inversión impide
rescatar una ventana post-hoc y apunta a inestabilidad de régimen, no a falta de
cobertura del panel.

Los artefactos autoritativos son `metrics.json`, `monthly_metrics.csv`,
`trade_ledger.parquet`, `source_inventory.csv` y `provenance.json` en este
directorio.
