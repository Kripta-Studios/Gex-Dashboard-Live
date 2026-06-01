# tabular_v1 JEPA Result Summary

Gate A failed: Temporal Tabular JEPA v1 did not add alpha to the current GBT pipeline.

## Strict-WF Results

| Run | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline GBT | 3,545 | 49.6% | 1.305 | +367,372 | -17,217 |
| GBT + JEPA | 3,448 | 48.9% | 1.232 | +276,393 | -37,328 |
| JEPA-only probe | 3,949 | 44.9% | 0.962 | -58,716 | -99,570 |
| GBT + JEPA permuted | 3,518 | 48.8% | 1.233 | +280,949 | -33,286 |

## Interpretation

- GBT + JEPA lost -0.073 PF and about -90,979 PnL versus baseline.
- JEPA-only was unprofitable, so this latent state does not contain enough standalone tradable signal.
- Permuting the JEPA feature group did not degrade the candidate, which argues against robust JEPA alpha.
- LightGBM did use JEPA features: 7.9% to 10.0% of feature importance by ticker. The features were not ignored; they were not helpful.
- JEPA latent health was below plan threshold: best saved validation effective-rank ratio was about 0.33.

## Decision

Do not promote `tabular_v1`.

Do not start the neural predictor or RL-replacement phase from this checkpoint. A future JEPA attempt should first fix latent health and rerun Gate A.

