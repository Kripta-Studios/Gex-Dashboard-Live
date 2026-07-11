# Phys-TD-JEPA flat vs modal — comparación causal runtime-equivalente

## Decisión

**Avanzar a objetivos intra/cross-modal: NO.**

Modal no demuestra simultáneamente una mejora reproducible de representación y downstream; se detiene la cola intra/cross-modal.

Junio de 2026 no fue leído ni puntuado por esta evaluación; los inputs downstream terminan en 20260529.

## Contrato

- Dataset executable_quote: entrada ask, trayectoria/salida bid.
- Rejilla 10:30–14:30 ET cada cinco minutos.
- Hold mínimo realizado: 30 minutos.
- SPXW: 4 trades/día, cooldown 0m; QQQ: 2/30m; SPY: 1/0m.
- Nested walk-forward 202601–202605; seed 20260618 y mismo presupuesto.
- SHA-256 parquet flat sellado: `65CCD607A77AF65C71469A74EF76D71F40B56E6BCDD3DEE408E673A5FA59ECEB`.
- SHA-256 parquet modal sellado: `FC99717F6C8B801C09C9F1B4F39FA1E9860505FDA2E112A9706746298CF0DD64`.

## Métricas agregadas

| Arm | Trades | WR | PF | PnL (R) | Max DD | Gate ticker×mes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| flat | 481 | 43.867% | 0.900 | -15.094 | -26.009 | 1/15 |
| modal | 491 | 42.974% | 0.858 | -21.989 | -31.039 | 0/15 |

## Por ticker

| Arm | Ticker | Trades | WR | PF | PnL (R) | Min trades/mes | Meses positivos |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| flat | QQQ | 166 | 46.386% | 1.000 | -0.010 | 28 | 60% |
| flat | SPXW | 217 | 41.014% | 0.813 | -14.249 | 17 | 60% |
| flat | SPY | 98 | 45.918% | 0.969 | -0.835 | 17 | 40% |
| modal | QQQ | 184 | 43.478% | 0.828 | -9.946 | 29 | 0% |
| modal | SPXW | 228 | 42.544% | 0.822 | -12.724 | 32 | 40% |
| modal | SPY | 79 | 43.038% | 1.027 | +0.681 | 0 | 60% |

## Pruebas pareadas clave

| Métrica | Wins modal | p Wilcoxon | Mediana modal-flat |
| --- | ---: | ---: | ---: |
| representation_prediction_to_persistence_ratio_mean | 2/15 | 0.999237 | +0.106555 |
| representation_prediction_beats_persistence_rate | 0/15 | 1.000000 | -0.202263 |
| downstream_test_profit_factor | 7/15 | 0.834869 | -0.027757 |
| downstream_test_pnl_return | 7/15 | 0.640137 | -0.347987 |

Bootstrap diario modal-flat: observado -6.895R, IC95% [-31.537, +17.109], P(diff>0)=0.292.

Las tablas completas por fold y ticker×mes están en los CSV del mismo directorio.
