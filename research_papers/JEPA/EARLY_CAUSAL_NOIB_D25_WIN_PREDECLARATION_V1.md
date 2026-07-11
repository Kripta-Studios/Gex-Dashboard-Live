# Predeclaración v1 — early causal no-IB d25 win

## Causa que se corrige

El stream dense15 legacy obtiene todo su PnL de `10:00..10:29`, pero sus niveles Initial Balance/Fibonacci y el filtro `near_level_only` usan la ventana completa `09:30..10:30`. Eso introduce hasta 30 minutos futuros. La prueba no intenta conservar esa información: pregunta si existe edge temprano después de eliminar físicamente la selección y features no observables.

## Dataset nuevo

- ThetaData 2022–mayo 2026, manifest SHA `88BE8A2...2974A`.
- Solo `10:00..10:25`, rejilla de cinco minutos, SPXW/QQQ/SPY 0DTE.
- `near_level_only=false`; ninguna fila se selecciona por IB/Fib/nearest level.
- Entrada ask y salida bid, trailing 50%/25%, stop -60%, cap +1000%, hold 30–180m.
- OI obligatorio y features físicas/cross actuales.
- El selector usa `entry_time_min_et=10:00` y la allowlist live elimina todo IB/Fib/nearest/context-IB y estado intradía no reproducible. Outcome, future y columnas `_opt_*` no pueden ser features.
- Junio de 2026 no se construye ni se lee.

## Modelo y walk-forward

Un único perfil fijo por ticker: `target_zero_dte_d25_win`. Se elige d25 porque es el primary del único mecanismo legacy cuya franja temprana fue rentable; no se prueban deltas adicionales, return arm, backfill ni guard.

| Ticker | Cap/día | Cooldown |
| --- | ---: | ---: |
| SPXW | 4 | 0m |
| QQQ | 2 | 30m |
| SPY | 1 | 0m |

LightGBM y thresholds son los ya congelados; 28 hilos CPU. Train acumulativo desde 2022, tres meses inner y tests `202601..202605`. La validación interna y el éxito final exigen PF>=1,3, WR>=50%, mínimo 18 trades en cada mes, todos los meses positivos y hold>=30m.

## Decisión

- Si los tres tickers cumplen, el siguiente paso será implementar un snapshot early separado y auditable en shadow; no modificar producción todavía.
- Si solo algún ticker cumple, se conserva como mecanismo por ticker y se investiga los otros desde sus fallos inner, sin mezclar deltas post hoc.
- Si ninguno cumple, se concluye que el edge early dependía del leakage IB/Fib o del payoff legacy; no se reintroducirán esos niveles y se buscará otro mecanismo causal.
- Abstención no cuenta como éxito y junio continúa sellado.

## Ejecución

Runner: `run_early_causal_noib_d25_win_v1.ps1`. Construcción con 24 workers; LightGBM con 28 hilos. Outputs nuevos en `tmp/event_option_dataset_execquote_causal1000_noib_early_202201_202605_v1*` y `.../early_causal_noib_d25_win_202601_202605_seed20260618_v1`.

Hashes congelados:

```text
manifest  88BE8A2FF44C18FB57FCA360D31DEF574DDBB0419A792FC88349942711D2974A
builder   6E89AAFED8A2BB66AA8EE80DF70644ECA189D0CE1D8C56F3812895430DAC4307
enhancer  3E420DB49315AFD9363C45B9F0FEFFA38732EFC116889D3D69B4417A94D2CB36
selector  95279496D6C0A1820522AB2244F70EEEEEA916300486AE87BD7A76D628B8C2AA
auditor   E058C1FD6B99092C99367842339EB5B0CA6AC8E03718F962D9249E9E5475F446
test      F854F789F7C82F2B3D8AF0119EF17E91CFD8A5B6423BF923A0B1FFECE870F272
runner    3F88EA458BBDA2130B87DF527AA08CC708A80F52F46828FA7556A4A87104A715
```
