# H-TPOVALUE1 development early stop

Estado: `FAILED_ECONOMIC_DEVELOPMENT_EARLY_STOP`.

El desarrollo nested empezó por la primera celda congelada, SPXW outer
2023-04, con inner 2023-01..03 y train hasta 2022-12-30. X0 y X1 terminaron
`ABSTAIN_OUTER`: 0/42 grids pasaron simultáneamente los tres meses. Como X1
debía aprobar cada ticker-mes, esta primera celda basta para hacer imposible el
PASS de desarrollo; el proceso se detuvo tras 2/54 folds completos.

En X1, 0/42 grids pasaron enero, 0/42 febrero y 6/42 marzo. El near-miss con
utility percentile 70 y margin percentile 50 obtuvo 68 trades inner, PF pooled
`0,9217180330` y PnL `-1,8312322783R`:

| Mes | Trades | WR | PF | PnL R | Hold mínimo |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2023-01 | 18 | 44,44% | 0,529 | -3,228 | 30m |
| 2023-02 | 24 | 33,33% | 0,759 | -2,366 | 30m |
| 2023-03 | 26 | 61,54% | 1,560 | +3,763 | 30m |

No se abrió outer para esa celda porque la selección inner abstuvo. No se
abrieron QQQ/SPY, los outer restantes, 2024/2025 ni 2026. Producción permanece
intacta. No se permite rescatar TPO cambiando grid, meses, ticker o features.

Provenance principal:

- `RUN_CHECKPOINT.json` SHA
  `cd158193378bbdc4dee8c4fa49b80fa5acf80e8d8cf893909b43b286e653a6d0`.
- X0 fold manifest SHA
  `c299fb4ef2970c1f974fafbba54322ae212a560d6e3da2d8d2f60d05e46e26e7`.
- X1 fold manifest SHA
  `249acb75643c7e18e7b195b66ba584f83d9a58a96db2bdcb2592e065ec8bbb6d`.
- X1 inner grid SHA
  `12e02c447aa54093f14546f085eff949c0e5a2aff36dd7aa539cdd6c4e96f075`.
