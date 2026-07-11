# Phys-TD-JEPA flat — historia 2022 vs 2025

## Decisión

History 2022 does not improve representation and downstream simultaneously; reject this history extension.

Junio de 2026 permaneció físicamente ausente. La comparación usa executable_quote ask→bid y nested walk-forward runtime-equivalente.

## Métricas agregadas

| Arm | Trades | WR | PF | PnL (R) | Max DD | Gate ticker×mes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| history_2025 | 495 | 45.051% | 0.863 | -20.174 | -27.180 | 4/15 |
| history_2022 | 440 | 42.273% | 0.764 | -31.476 | -34.403 | 1/15 |

## Por ticker

| Arm | Ticker | Trades | WR | PF | PnL (R) | Min trades/mes | Meses positivos |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| history_2025 | QQQ | 161 | 46.584% | 0.893 | -4.819 | 22 | 40% |
| history_2025 | SPXW | 235 | 40.851% | 0.711 | -22.935 | 32 | 0% |
| history_2025 | SPY | 99 | 52.525% | 1.336 | +7.580 | 18 | 80% |
| history_2022 | QQQ | 163 | 45.399% | 0.764 | -10.638 | 26 | 0% |
| history_2022 | SPXW | 180 | 42.778% | 0.696 | -16.542 | 29 | 0% |
| history_2022 | SPY | 97 | 36.082% | 0.874 | -4.296 | 18 | 60% |

## Evidencia pareada

| Métrica | Wins 2022 | p Wilcoxon | Mediana 2022-2025 |
| --- | ---: | ---: | ---: |
| representation_prediction_to_persistence_ratio_mean | 13/15 | 0.000580 | -0.079128 |
| representation_prediction_beats_persistence_rate | 11/15 | 0.003357 | +0.079734 |
| downstream_test_profit_factor | 6/15 | 0.952698 | -0.020046 |
| downstream_test_pnl_return | 7/15 | 0.772858 | -0.235047 |

Bootstrap diario 2022-2025: observado -11.302R, IC95% [-44.087, +20.825], P(diff>0)=0.248.

La decisión exige mejora simultánea de representación y downstream; el PnL agregado por sí solo no selecciona el arm.
