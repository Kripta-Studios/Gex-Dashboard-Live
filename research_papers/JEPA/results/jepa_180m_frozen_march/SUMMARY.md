# Frozen Base+JEPA 180m Candidate

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_jepa_xinput_v3.parquet`
Rows after exact 180m label construction: 56,140 from 221,753
Train cutoff: `20260331`
Test start: `20260401`
Label: `spot_price(t+180m) > spot_price(t)`
Backtest: fixed 180m hold, cooldown `36` samples, base cost `1.0` bps, notional `$100,000`.

## Prediction Metrics

| Mode | Rows | Future Up | Pred Up | AUC | Acc | Bal Acc | Spearman Ret | Top Q Ret bps | Bottom Q Ret bps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 2200 | 63.1% | 60.6% | 0.622 | 62.0% | 60.0% | 0.178 | 10.83 | -0.60 |
| jepa_only | 2200 | 63.1% | 51.5% | 0.572 | 55.5% | 55.5% | 0.121 | 12.32 | 3.49 |
| base_jepa | 2200 | 63.1% | 55.9% | 0.630 | 61.5% | 60.6% | 0.216 | 13.87 | -0.16 |

## Fixed-Hold 180m Backtest

| Mode | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 80 | 58.8% | 1.389 | 4.40 | +3,522 | -1,640 | 65.0% |
| jepa_only | 109 | 58.7% | 1.326 | 3.81 | +4,157 | -3,270 | 53.2% |
| base_jepa | 104 | 68.3% | 1.936 | 8.70 | +9,044 | -1,522 | 64.4% |

## Cost Sensitivity

| Cost | Mode | Trades | WR | PF | Avg bps | PnL | Max DD |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 bps | base | 80 | 58.8% | 1.389 | 4.40 | +3,522 | -1,640 |
| 1 bps | jepa_only | 109 | 58.7% | 1.326 | 3.81 | +4,157 | -3,270 |
| 1 bps | base_jepa | 104 | 68.3% | 1.936 | 8.70 | +9,044 | -1,522 |
| 3 bps | base | 80 | 56.2% | 1.198 | 2.40 | +1,922 | -1,920 |
| 3 bps | jepa_only | 109 | 58.7% | 1.145 | 1.81 | +1,977 | -3,490 |
| 3 bps | base_jepa | 104 | 65.4% | 1.673 | 6.70 | +6,964 | -1,562 |
| 5 bps | base | 80 | 55.0% | 1.031 | 0.40 | +322 | -2,441 |
| 5 bps | jepa_only | 109 | 57.8% | 0.986 | -0.19 | -203 | -3,753 |
| 5 bps | base_jepa | 104 | 64.4% | 1.441 | 4.70 | +4,884 | -1,625 |
| 10 bps | base | 80 | 48.8% | 0.704 | -4.60 | -3,678 | -5,099 |
| 10 bps | jepa_only | 109 | 49.5% | 0.670 | -5.19 | -5,653 | -5,636 |
| 10 bps | base_jepa | 104 | 55.8% | 0.976 | -0.30 | -316 | -2,086 |

## Existing Signal Comparison

Report: `research_papers/JEPA/results/jepa_180m_frozen_march/existing_signals_fixed180/SUMMARY.md`

This comparison takes the existing Apr/May OOS target/stop entry signals and reprices them under the same fixed 180m hold proxy, enforcing the same 36-sample cooldown.

| Signal | Input Trades | Fixed-180 Trades | WR | PF | Avg bps | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Current baseline GBT entries | 213 | 30 | 46.7% | 1.239 | 3.03 | +909 | -2,065 |
| Previous GBT+XInputJEPA target/stop entries | 227 | 29 | 55.2% | 0.982 | -0.21 | -62 | -1,183 |
| Previous XInputJEPA-only target/stop entries | 249 | 41 | 43.9% | 0.745 | -3.32 | -1,360 | -2,205 |
| Frozen base_jepa 180m model | n/a | 104 | 68.3% | 1.936 | 8.70 | +9,044 | -1,522 |

The current GBT target/stop entries are not optimized for fixed 180m terminal direction. Under that payoff proxy, the frozen `base_jepa` 180m model is the stronger entry candidate.

## Decision

- This is the strict frozen-candidate test: all Apr/May predictions use models trained only through the cutoff.
- `future_return_180m` is used only for labels/backtest outcome and is excluded from features.
- `base_jepa` beats `base` here and also beats the current target/stop GBT entries when those entries are repriced under the same fixed-180m proxy.
- This is now a credible replacement candidate for the 180m entry model, pending integration/backtest with the exact production execution rules.
