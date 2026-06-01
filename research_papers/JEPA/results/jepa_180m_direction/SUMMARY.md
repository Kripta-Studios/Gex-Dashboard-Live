# JEPA 180m Direction Experiment

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_jepa_xinput_v3.parquet`
Rows after exact 180m label construction: 56,140 from 221,753
Label: `spot_price(t+180m) > spot_price(t)`
Test months: `202604 to last`
OOS split: dates >= `20260401`
Backtest: fixed 180m hold, cooldown `36` samples, cost `1.0` bps, notional `$100,000` per trade.

## Prediction Metrics

| Mode | Rows | Future Up | Pred Up | AUC | Acc | Bal Acc | Spearman Ret | Top Q Ret bps | Bottom Q Ret bps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base overall | 2200 | 63.1% | 64.2% | 0.617 | 62.1% | 59.0% | 0.167 | 11.03 | 1.38 |
| base OOS | 2200 | 63.1% | 64.2% | 0.617 | 62.1% | 59.0% | 0.167 | 11.03 | 1.38 |
| jepa_only overall | 2200 | 63.1% | 52.7% | 0.577 | 55.2% | 54.9% | 0.125 | 12.84 | 1.73 |
| jepa_only OOS | 2200 | 63.1% | 52.7% | 0.577 | 55.2% | 54.9% | 0.125 | 12.84 | 1.73 |
| base_jepa overall | 2200 | 63.1% | 54.1% | 0.623 | 60.2% | 59.8% | 0.200 | 14.97 | 0.20 |
| base_jepa OOS | 2200 | 63.1% | 54.1% | 0.623 | 60.2% | 59.8% | 0.200 | 14.97 | 0.20 |

## Fixed-Hold 180m Backtest

| Mode | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base overall | 87 | 57.5% | 1.591 | 6.43 | +5,596 | -1,404 | 62.1% |
| base OOS | 87 | 57.5% | 1.591 | 6.43 | +5,596 | -1,404 | 62.1% |
| jepa_only overall | 106 | 57.5% | 1.378 | 4.27 | +4,523 | -2,855 | 56.6% |
| jepa_only OOS | 106 | 57.5% | 1.378 | 4.27 | +4,523 | -2,855 | 56.6% |
| base_jepa overall | 106 | 65.1% | 1.886 | 8.21 | +8,707 | -1,539 | 59.4% |
| base_jepa OOS | 106 | 65.1% | 1.886 | 8.21 | +8,707 | -1,539 | 59.4% |

## Per-Ticker OOS Notes

- `base_jepa` QQQ: 32 trades, WR 71.9%, PF 2.084, PnL +3,416.
- `base_jepa` SPX: 40 trades, WR 62.5%, PF 1.949, PnL +3,237.
- `base_jepa` SPY: 34 trades, WR 61.8%, PF 1.629, PnL +2,054.
- Base features had higher QQQ AUC, but `base_jepa` produced the strongest aggregate fixed-hold result and better SPX/SPY ranking quality.

## Cost Sensitivity

Existing trade selection was tuned at 1 bps cost. This table reapplies higher costs to the same OOS trades.

| Cost | Mode | Trades | WR | PF | Avg bps | PnL | Max DD |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 bps | base | 87 | 57.5% | 1.591 | 6.43 | +5,596 | -1,404 |
| 1 bps | jepa_only | 106 | 57.5% | 1.378 | 4.27 | +4,523 | -2,855 |
| 1 bps | base_jepa | 106 | 65.1% | 1.886 | 8.21 | +8,707 | -1,379 |
| 5 bps | base | 87 | 54.0% | 1.192 | 2.43 | +2,116 | -1,984 |
| 5 bps | jepa_only | 106 | 53.8% | 1.021 | 0.27 | +283 | -3,386 |
| 5 bps | base_jepa | 106 | 62.3% | 1.393 | 4.21 | +4,467 | -1,541 |
| 10 bps | base | 87 | 49.4% | 0.830 | -2.57 | -2,234 | -3,884 |
| 10 bps | jepa_only | 106 | 49.1% | 0.694 | -4.73 | -5,017 | -5,341 |
| 10 bps | base_jepa | 106 | 54.7% | 0.938 | -0.79 | -833 | -2,065 |

## Interpretation

- This is a terminal 180m direction experiment, not the original target/stop 0DTE label.
- The future return is used only as the label and backtest outcome; feature columns explicitly exclude future/target columns.
- OOS metrics are the important decision point because previous XInputJEPA evidence was unstable in Apr/May 2026.
- In this OOS test, `base_jepa` beats the base feature model on AUC, Spearman-to-return, top-vs-bottom score separation, win rate, PF, and fixed-hold PnL.
- This supports a separate JEPA-180m module, but not production deployment yet: the edge survives 5 bps cost, fails around 10 bps, and still needs a longer rolling OOS/full-history pass plus a real options premium backtest.

Follow-up stricter frozen-candidate test: `research_papers/JEPA/results/jepa_180m_frozen_march/SUMMARY.md`

- Models trained only through 2026-03-31 and tested from 2026-04-01.
- `base_jepa` remained best: AUC 0.630, PF 1.936, PnL +9,044 at $100k notional and 1 bps cost.
- This confirms the monthly-retrained result was not merely caused by using April data for May.
