# JEPA 180m Standalone Backtest

Data: `training_data\training_data_spx_qqq_spy_jepa_xinput_v3.parquet`
Model dir: `neural\models\jepa\jepa_180m_frozen_march`
Mode: `base_jepa`
Rows scored: 2,200
Execution: fixed `180`m hold, cooldown `60`m, cost `1.0` bps, notional `$100,000`.

## Overall

| Scope | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 178 | 64.0% | 1.889 | 7.83 | +13,931 | -2,166 | 61.8% |

## Per Ticker

| Ticker | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 70 | 61.4% | 1.494 | 6.05 | +4,234 | -2,166 | 62.9% |
| SPX | 51 | 66.7% | 3.802 | 13.11 | +6,684 | -716 | 60.8% |
| SPY | 57 | 64.9% | 1.641 | 5.29 | +3,013 | -1,433 | 61.4% |

## Cost Sensitivity

| Cost | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 bps | 178 | 64.0% | 1.889 | 7.83 | +13,931 | -2,166 | 61.8% |
| 3 bps | 178 | 61.8% | 1.611 | 5.83 | +10,371 | -2,365 | 61.8% |
| 5 bps | 178 | 60.7% | 1.371 | 3.83 | +6,811 | -2,905 | 61.8% |
| 10 bps | 178 | 53.4% | 0.906 | -1.17 | -2,089 | -4,255 | 61.8% |

## Model Thresholds

```json
{
  "SPX": {
    "feature_count": 222,
    "thresholds": {
      "long_threshold": 0.7,
      "short_threshold": 0.30000000000000004,
      "val_score": 9066.796155890974,
      "val_trades": 56,
      "val_win_rate": 0.6428571428571429,
      "val_avg_net_bps": 16.998134836126017,
      "val_median_net_bps": 14.419209700507919,
      "val_total_net_bps": 951.895550823057,
      "val_profit_factor": 3.343484412526987,
      "val_pnl_dollars": 9518.955508230569,
      "val_max_drawdown": -1808.6374093583818,
      "val_long_rate": 0.4107142857142857
    },
    "meta": {
      "mode": "base_jepa",
      "ticker": "SPX",
      "train_end_date": "20260331",
      "test_start_date": "20260401",
      "test_end_date": null,
      "feature_count": 222,
      "horizon_steps": 36,
      "horizon_minutes": 180,
      "cost_bps": 1.0,
      "cooldown_steps": 36,
      "notional": 100000.0
    }
  },
  "QQQ": {
    "feature_count": 222,
    "thresholds": {
      "long_threshold": 0.52,
      "short_threshold": 0.48,
      "val_score": 5529.586662946473,
      "val_trades": 61,
      "val_win_rate": 0.5573770491803278,
      "val_avg_net_bps": 9.550396062265362,
      "val_median_net_bps": 13.975727468296007,
      "val_total_net_bps": 582.5741597981871,
      "val_profit_factor": 1.785218341255456,
      "val_pnl_dollars": 5825.741597981871,
      "val_max_drawdown": -1184.6197401415923,
      "val_long_rate": 0.3442622950819672
    },
    "meta": {
      "mode": "base_jepa",
      "ticker": "QQQ",
      "train_end_date": "20260331",
      "test_start_date": "20260401",
      "test_end_date": null,
      "feature_count": 222,
      "horizon_steps": 36,
      "horizon_minutes": 180,
      "cost_bps": 1.0,
      "cooldown_steps": 36,
      "notional": 100000.0
    }
  },
  "SPY": {
    "feature_count": 222,
    "thresholds": {
      "long_threshold": 0.62,
      "short_threshold": 0.38,
      "val_score": 5496.12803263825,
      "val_trades": 60,
      "val_win_rate": 0.5666666666666667,
      "val_avg_net_bps": 10.135999957080552,
      "val_median_net_bps": 7.4761759696194705,
      "val_total_net_bps": 608.1599974248331,
      "val_profit_factor": 2.0988164102953806,
      "val_pnl_dollars": 6081.599974248329,
      "val_max_drawdown": -2341.8877664403144,
      "val_long_rate": 0.36666666666666664
    },
    "meta": {
      "mode": "base_jepa",
      "ticker": "SPY",
      "train_end_date": "20260331",
      "test_start_date": "20260401",
      "test_end_date": null,
      "feature_count": 222,
      "horizon_steps": 36,
      "horizon_minutes": 180,
      "cost_bps": 1.0,
      "cooldown_steps": 36,
      "notional": 100000.0
    }
  }
}
```

## Cooldown Note

- The default cooldown is 180m because the label and execution horizon are 180m.
- This prevents stacking many overlapping 5-minute entries that mostly bet on the same future window.
- The value is configurable with `--cooldown-minutes` for sensitivity testing.
