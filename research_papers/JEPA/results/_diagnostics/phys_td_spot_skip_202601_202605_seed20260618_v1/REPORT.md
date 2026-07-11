# Phys-TD direct spot skip v1 — informe final

## Contrato

- Control: `z_t + pred_h1`.
- Variante: mismo head y filas más `ret_5m_bps`, `ret_15m_bps` y `ret_30m_bps` backward-looking.
- Test externo: `202601..202605`; tres meses internos anteriores a cada test.
- Gates internas por ticker: PF `>=1,3`, WR `>=50%`, mínimo `18` trades en cada mes y todos los meses positivos.
- Contrato de ejecución: d25 SPXW, d35 QQQ/SPY, ask→bid, hold mínimo 30m, cupos/cooldowns runtime; junio de 2026 sellado.

## Integridad

- Runner completado una sola vez; `11 passed` y CUDA determinista sobre RTX 5070 Ti.
- Filas por fold: `20.361`, `21.470`, `22.850`, `24.403`, `26.038`.
- Hashes de dataset, espacios coherentes y manifest h1 coinciden con la predeclaración.
- Replay runtime PASS en ambos arms; no quedan procesos.

## Resultado

Ambos arms produjeron `0/210` candidatos internos válidos, `15/15` folds en abstención y `0` trades OOS. El skip directo no mejora la representación de payoff: gana MAE en `5/15` celdas (mediana delta `+0,002683`, p unilateral `0,9156`), RMSE en `1/15` (`+0,016080`, p `0,9998`) y accuracy direccional en `8/15` (`+0,004266`, p `0,7193`).

El patrón de fallo es económico, no de volumen bruto: muchos candidatos superan 18 trades/mes, pero QQQ/SPXW quedan mayoritariamente por debajo de WR/PF y sin persistencia mensual. SPY llega a 18 solo en folds tempranos y también falla PF/WR. Por tanto, concatenar más bloques de features o cambiar otra arquitectura sin aislar el mecanismo no está justificado.

## Decisión

`spot_skip_meets_full_ticker_gate=false` y `production_live_ready=false`. No retunar este skip ni encadenar skew/flow/levels/cross-asset por tanteo. La siguiente investigación debe volver al mecanismo supervisado/union/backfill que ya mostró edge histórico, reconstruirlo con labels executable-quote y contrato exacto, y localizar qué parte (objetivo win/return, delta bucket, backfill, selector o guard causal) explica la diferencia. No tocar producción ni abrir junio.
