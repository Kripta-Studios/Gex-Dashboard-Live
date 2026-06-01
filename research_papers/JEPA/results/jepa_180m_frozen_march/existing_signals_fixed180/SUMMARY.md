# Existing Signals Under Fixed 180m Hold

Data: `training_data\training_data_spx_qqq_spy_jepa_xinput_v3.parquet`
Backtest: fixed 180m hold, cooldown `36` samples, cost `1.0` bps, notional `$100,000`.

| Signal | Input Trades | Fixed-180 Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_gbt | 213 | 30 | 46.7% | 1.239 | 3.03 | +909 | -2,065 | 56.7% |
| gbt_xjepa_targetstop | 227 | 29 | 55.2% | 0.982 | -0.21 | -62 | -1,183 | 58.6% |
| xjepa_only_targetstop | 249 | 41 | 43.9% | 0.745 | -3.32 | -1,360 | -2,205 | 63.4% |

## Cost Sensitivity

| Cost | Signal | Trades | WR | PF | Avg bps | PnL | Max DD |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 bps | baseline_gbt | 30 | 46.7% | 1.239 | 3.03 | +909 | -2,065 |
| 1 bps | gbt_xjepa_targetstop | 29 | 55.2% | 0.982 | -0.21 | -62 | -1,183 |
| 1 bps | xjepa_only_targetstop | 41 | 43.9% | 0.745 | -3.32 | -1,360 | -2,205 |
| 3 bps | baseline_gbt | 30 | 43.3% | 1.075 | 1.03 | +309 | -2,225 |
| 3 bps | gbt_xjepa_targetstop | 29 | 55.2% | 0.823 | -2.21 | -642 | -1,303 |
| 3 bps | xjepa_only_targetstop | 41 | 43.9% | 0.623 | -5.32 | -2,180 | -2,692 |
| 5 bps | baseline_gbt | 30 | 40.0% | 0.935 | -0.97 | -291 | -2,385 |
| 5 bps | gbt_xjepa_targetstop | 29 | 48.3% | 0.687 | -4.21 | -1,222 | -1,541 |
| 5 bps | xjepa_only_targetstop | 41 | 41.5% | 0.520 | -7.32 | -3,000 | -3,358 |
| 10 bps | baseline_gbt | 30 | 33.3% | 0.672 | -5.97 | -1,791 | -2,785 |
| 10 bps | gbt_xjepa_targetstop | 29 | 31.0% | 0.437 | -9.21 | -2,672 | -2,860 |
| 10 bps | xjepa_only_targetstop | 41 | 31.7% | 0.336 | -12.32 | -5,050 | -5,308 |
