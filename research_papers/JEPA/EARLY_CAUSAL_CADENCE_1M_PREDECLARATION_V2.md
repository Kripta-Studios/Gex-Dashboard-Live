# Predeclaración v2 — cadencia early causal 5m frente a 1m

## Pregunta aislada

El feed live guarda snapshots cada minuto, mientras que la policy vigente filtra entradas cada cinco minutos. El control causal 5m early no-IB falló. Esta prueba cambia un único factor operativo: materializar y permitir candidatos en cada minuto de `10:00..10:25` en lugar de solo `00/05/10/15/20/25`.

No se cambia arquitectura, perfil, objetivo, buckets, features permitidas, quotes, exits, caps, cooldowns, folds, thresholds, seed ni gates. No modifica la policy live.

## No duplicación y paridad

- No existe otro dataset local `early_1m` antes del lanzamiento.
- Los resultados `clean_live1000` previos usan parquets `dense15` 2025–2026 con labels/exits legacy e IB completo; no responden esta pregunta.
- Control congelado: `tmp/event_option_dataset_execquote_causal1000_noib_early_202201_202605_v1/event_option_dataset.parquet`, SHA `5E916EFA...BBEF49`.
- Antes de entrenar, `audit_early_cadence_pair.py` exigirá que las filas de minutos múltiplos de cinco del candidato 1m reproduzcan exactamente las claves y columnas base del control. Las filas intermedias deben ser una expansión, no un reemplazo.
- El auditor causal recibe `--expected-step-minutes 1` y comprueba también que el build declaró `bar_minutes=1`.

## Contrato congelado

- ThetaData 2022–mayo2026; junio 2026 no se construye ni se lee.
- SPXW/QQQ/SPY 0DTE, 10:00–10:25 ET cada minuto.
- `near_level_only=false`; el selector prefix-only excluye IB/Fib/nearest/context-IB antes de 10:30.
- Entrada ask, salida bid, stop -60%, TP +1000%, trailing 50%/25%, hold 30–180m y OI obligatorio.
- Perfil único `target_zero_dte_d25_win` para cada ticker.
- Caps/cooldowns SPXW `4/0m`, QQQ `2/30m`, SPY `1/0m`.
- Train acumulativo desde 2022, tres meses inner, OOS `202601..202605`, seed `20260618`.
- Ryzen: build 24 workers, LightGBM 28 hilos. La RTX no se usa porque el benchmark previo de este GBT favoreció CPU; sigue reservada para modelos que realmente se beneficien de CUDA.

## Gates y decisión

Cada ticker debe alcanzar simultáneamente PF>=1,3, WR>=50%, al menos 18 trades en cada uno de los cinco meses, PnL positivo en todos y hold observado >=30m. Abstención o meses sin trades son fallo.

- Si 1m cumple en los tres tickers, se congela para un replay/shadow separado; producción no cambia todavía.
- Si mejora solo un ticker, se conserva como hipótesis por ticker y se diagnostican los demás sin mezclar reglas post hoc.
- Si falla, no se barrerán cadencias 2m/3m/4m ni ventanas usando OOS; se investigará el motivo económico del fallo.

## Ejecución y hashes

Runner: `run_early_causal_noib_d25_win_1m_v2.ps1`. Outputs nuevos `tmp/event_option_dataset_execquote_causal1000_noib_early_1m_202201_202605_v2*` y `.../early_causal_noib_d25_win_1m_202601_202605_seed20260618_v2/`.

```text
manifest       88BE8A2FF44C18FB57FCA360D31DEF574DDBB0419A792FC88349942711D2974A
builder        6E89AAFED8A2BB66AA8EE80DF70644ECA189D0CE1D8C56F3812895430DAC4307
enhancer       3E420DB49315AFD9363C45B9F0FEFFA38732EFC116889D3D69B4417A94D2CB36
selector       95279496D6C0A1820522AB2244F70EEEEEA916300486AE87BD7A76D628B8C2AA
causal auditor C5B47C9FA31926C02CD41C9E1FB3615B94101A9B39C6E755072F144C29C95E5D
pair auditor   8269A4FB745B5ABB7DCEDBF4AE13721D429E5CBCDB946A8D6F9619FC6AF4E396
selector test  461ED65AFB1851D21A9955003D324C3DA57441AFF936743E1A238EA4D413C9F2
pair test      2A1801421A3754B973469B408F87C0E4E312094E482544B839F9FD7EAB767487
runner         288BBF082FD2AB6DA57E0A768BA9F4344488DD3BB37264D4218F524232D7B87D
```
