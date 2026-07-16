# DIRECTIONAL_OPTION_SURFACE_SPOT_V1 — predeclaración de desarrollo

Fecha de congelación: 2026-07-16. La familia price-only ya está cerrada. Esta
hipótesis pregunta si la superficie causal de opciones contiene direccionalidad
del subyacente aunque comprar opciones no sea rentable por spread/theta.

## Fuente reutilizada

No se construye un dataset de features. El desarrollo lee el parquet executable
quote ya existente:

`tmp/event_option_dataset_execquote_causal1030_202201_202605_v1_physics/event_option_dataset.parquet`

- SHA-256: `11e26aaddd91fd441222d552e0362c1d4c2c4489a08d7a6de66479d6eb454fb1`.
- 108.156 filas, 371 columnas, `zero_dte` y `executable_quote` uniformes.
- Se permiten únicamente features que el filtro live-observable existente
  acepta. Se excluyen todas las columnas `future`, `spot_long`, `spot_short`,
  `spot_best` y cualquier outcome `_opt_*`.

Las etiquetas se calculan en memoria desde `data_underlying_derived`; no se
persisten como otro parquet.

## Universo, calendario y reloj

- Tickers: `QQQ`, `SPXW` (reportado como SPX) y `SPY`.
- Desarrollo: datos hasta 2025-12-31; 2026 permanece cerrado.
- Relojes: 10:35, 11:40, 12:45 y 13:50 ET.
- Features observables hasta el snapshot `t`; entrada al open underlying `t+1m`;
  salida al open `t+61m`; hold exacto 60m y coste 1 bp.
- Las ventanas no solapan.
- Para cada `(fecha,reloj)`, si falta un snapshot o una barra exacta en cualquiera
  de los tres tickers, se elimina esa decisión para los tres. No hay as-of,
  nearest minute, imputación ni exclusión post-outcome.
- Medias jornadas y la sesión inválida conocida 2023-06-05 se excluyen para todos.

El preflight encontró 2.109 decisiones comunes entre 2022–2025 y 36–60 por mes
en 2025, por encima de la frecuencia requerida.

## Perfiles y modelo

Se ajusta un único LightGBM pooled por mes y perfil, usando los tres tickers:

- `PRICE_LEVEL_CONTROL`: columnas live-observable que no empiezan por
  `call_`, `put_`, `phys_` o `ctx_`.
- `OPTION_SURFACE`: todas las columnas live-observable, incluidas selección por
  delta, IV, theta, vega, OI, volumen, spreads, deformaciones y contexto
  cross-index causal ya auditado.

Hiperparámetros fijos: binary, 240 árboles, learning rate 0,025, 15 hojas,
depth 4, min child 80, subsample/colsample 0,8, L1 0,05, L2 0,5. Los ejemplos
se pesan por magnitud futura recortada a [5,100] bps. `p>=0,5` es LONG; no hay
abstención, threshold, stop, TP ni selección de reloj.

## Selección de desarrollo

Walk-forward mensual 2025, entrenando siempre solo con meses anteriores. Se
elige un único perfil global por:

1. peor número de meses positivos entre tickers;
2. total de meses positivos;
3. peor PF agregado;
4. peor cuartil mensual de PnL;
5. nombre.

Solo se autoriza diseñar/fijar la evaluación 2026–julio si el perfil de
superficie supera al control y alcanza simultáneamente en desarrollo, por cada
ticker: PF >1,10, WR >45%, al menos 8/12 meses positivos y más de 12 trades por
mes. Si falla, V1 se cierra sin abrir 2026 ni rescatar features/relojes.

Una eventual evaluación seguirá siendo adaptativa por los resultados 2026 ya
conocidos de otras familias, y no evidencia de futures fills ni autorización de
producción.
