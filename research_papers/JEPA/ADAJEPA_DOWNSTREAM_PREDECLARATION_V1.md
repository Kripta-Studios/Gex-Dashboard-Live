# Predeclaración — AdaJEPA downstream frozen vs adapted v1

**Congelada antes de ejecutar:** 2026-07-11 CEST.

## Factor único

Ambos arms usan el mismo encoder coherente por fold, `z_t`, contratos exactos, MLP payoff, optimizer, folds, seeds, epochs, thresholds y runtime replay. Control recibe `frozen_pred_z-z_t`; variante recibe `adapted_pred_z-z_t`. Las filas, labels y holds son idénticos.

Features adaptadas se calculan antes de observar el target actual; solo incorporan updates de transiciones anteriores. `target_z`, errores, PnL futuro y outcome quedan físicamente fuera de la allowlist.

## Contrato

- Fuente physics SHA `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720`.
- Espacios manifest SHA `F398B1105C848C45D9BEAE0C156646B8B17207BEA5D08660BB359C099337F7B8`.
- SPXW d25, QQQ/SPY d35; executable_quote ask→bid; hold >=30m.
- Una posición/ticker; cupos 4/2/1 y cooldown 0/30/0.
- Rejilla causal disponible dentro de 10:30–14:30 ET/5m; contextos contiguos.
- Nested test `202601..202605`, tres meses internos; junio sellado.
- Heads hidden128/latent16, 40 epochs, batch512, seed `20260618+YYYYMM`, CUDA determinista.
- Gates internas/finales por ticker: PF>=1,3, WR>=50%, >=18 trades por mes y todos los meses positivos.

Si ningún threshold cumple inner gates, el fold hace abstain. No se relajarán gates ni se buscará PnL positivo post hoc. Adapted solo pasa si cumple el gate completo por los tres tickers; nunca se selecciona por PnL agregado. `production_live_ready=false`.

## Hashes

| Artefacto | SHA-256 |
| --- | --- |
| Downstream | `B2ADE83D1EC72E5DF9EC2560682A29A81DD91C91FEDA4D2054A3565F4FF2886C` |
| Export adapter features | `692146DD9F9A9189D97F69476B7C7EAD3782871EEEA16E849C4DF43E9EF18BB1` |
| Payoff helper | `21C011C6F66906E90B128E091794FC92497739568DC10F34EBB6F9175B45F0A1` |
| Runner | `27180A2B70EE516F62A036D48119A17EAD29172C58419FEAB15C6D39B00E6EF5` |

Tests focalizados `11 passed`; parse, compile y diff-check PASS.

## Resultado final

La corrida única terminó 5/5 folds por arm. Provenance/runtime pasan y junio permanece sellado, pero `frozen` y `adapted` obtuvieron `0/210` thresholds válidos: las 15 policies de cada arm hicieron abstain y no existen trades OOS. Adapted mejoró MAE en 13/15 celdas (mediana `-0,005331`, `p=0,006226`), pero RMSE solo 7/15 (mediana `+0,003113`, `p=0,680664`) y no satisfizo las gates económicas.

Decisión: `adapted_meets_full_ticker_gate=false`, `production_live_ready=false`. No retunar esta variante. Informe y hashes en `results/_diagnostics/adajepa_downstream_frozen_vs_adapted_202601_202605_v1/REPORT.md`.
