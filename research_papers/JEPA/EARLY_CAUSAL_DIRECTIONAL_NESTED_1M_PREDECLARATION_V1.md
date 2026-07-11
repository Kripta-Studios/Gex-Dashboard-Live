# Predeclaración v1 — mecanismo direccional nested sobre snapshots 1m

## Motivo e hipótesis

La vista early causal 1m ya existe y demostró que añadir timestamps no arregla por sí solo la señal. La auditoría inversa del static-union mostró además que el fallo es dirección/drift, no frecuencia. Esta prueba no reconstruye datos ni cambia arquitectura: pregunta si la dirección CALL/PUT puede estabilizarse con momentum spot backward-looking, seleccionando el mecanismo exclusivamente en inner validation.

## Datos congelados

- Parquet 1m executable-quote ya materializado: `tmp/event_option_dataset_execquote_causal1000_noib_early_1m_202201_202605_v2_physics/event_option_dataset.parquet`.
- 80.964 filas, SPXW/QQQ/SPY, 10:00–10:25 ET, enero2022–mayo2026; junio no está físicamente presente.
- No se ejecuta builder ni enhancer. Entrada ask, salida bid, stop -60%, TP +1000%, trailing 50%/25%, hold 30–180m y OI obligatorio permanecen congelados.
- Features live-observable; antes de 10:30 se excluyen IB/Fib/nearest y outcomes. `ret_5m_bps` y `ret_15m_bps` usan únicamente precios anteriores o iguales al timestamp.

## Espacio económico predeclarado

Los buckets no se buscan entre tickers: SPXW queda en d25 y QQQ/SPY en d35. Dentro de cada ticker se permite seleccionar solo:

- objetivo de calidad `return` o `win`;
- dirección del propio modelo;
- spot 5m trend o counter-trend;
- spot 15m trend o counter-trend.

En los modos spot, el signo del retorno determina CALL/PUT y el score usado para el threshold es la predicción del modelo para ese lado concreto. Las filas sin el retorno observable requerido se descartan; no hay fallback silencioso.

## Nested walk-forward

- Tests externos de desarrollo: `202601..202605`; junio sigue sellado.
- Para cada test se entrena con meses anteriores a los tres meses inner inmediatamente precedentes.
- Perfil, dirección, threshold y cap se seleccionan solo con esos tres meses inner.
- Seed `20260618`, LightGBM CPU 28 hilos, mismo presupuesto para todos los mecanismos.
- Cupos/cooldowns live: SPXW 4/0m, QQQ 2/30m, SPY 1/0m; una sola posición abierta por ticker.
- Gates inner y evaluación final por ticker: PF>=1,3, WR>=50%, >=18 trades en cada mes, PnL positivo en todos los meses y cada hold>=30m.
- Si ningún candidato cumple las gates inner, el fold abstiene. La abstención conserva su cronología en provenance.

El arm solo contará como candidato para un holdout final si los tres tickers cumplen simultáneamente las gates en los cinco meses externos. Aun así no modifica producción ni autoriza deploy automático; un fallo cierra esta familia sin retocar meses OOS.

## Artefactos

Runner: `run_early_causal_directional_nested_1m_v1.ps1`.

Resultado reservado: `research_papers/JEPA/results/_diagnostics/early_causal_directional_nested_1m_202601_202605_seed20260618_v1/`.

## Hashes congelados

```text
physics parquet 804BF0CC98576351126926C2B6A3C0DB1A195E9A6D51CB6306F49B3377B7CBE9
build summary   5F333D0B75BC3978CB82D8A26A38A2A0BF0C96E11E366CFDE1F274541B9DAF52
selector        5143742008C84BAED9E1FFB69739E01422ACD92B1D626CB769E691BB1DE014EC
auditor         C5B47C9FA31926C02CD41C9E1FB3615B94101A9B39C6E755072F144C29C95E5D
selector tests  93E8B17D9C35D5ABDEB4DF5AEDD034C17D8B151060DCD2BB7FFA0D01D6073317
causality tests 23076B9481411D0CB0941197B0B8F6AE01C0BBCEB593577AC9CC42AA5266546B
runner          5078D78634255B2B99D388BD3FFE67A6F4EBA9490DB9EC45397B3590BE529B45
```
