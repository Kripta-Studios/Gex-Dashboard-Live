# JEPA 180m Standalone Backtest

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet`
Model dir: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\neural\models\jepa\jepa_full_pipeline_180m_frozen_march`
Mode: `base_jepa`
Rows scored: 56,160
Execution: fixed `180`m hold, cooldown `180`m, cost `1.0` bps, notional `$100,000`.

## Overall

| Scope | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 2794 | 89.7% | 24.290 | 31.38 | +876,623 | -1,777 | 55.7% |

## Per Ticker

| Ticker | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 924 | 88.0% | 18.602 | 36.22 | +334,651 | -1,522 | 56.0% |
| SPX | 947 | 92.6% | 48.116 | 29.93 | +283,470 | -735 | 55.9% |
| SPY | 923 | 88.5% | 21.498 | 28.01 | +258,503 | -1,777 | 55.3% |

## Cost Sensitivity

| Cost | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 bps | 2794 | 89.7% | 24.290 | 31.38 | +876,623 | -1,777 | 55.7% |
| 3 bps | 2794 | 86.6% | 19.578 | 29.38 | +820,743 | -1,837 | 55.7% |
| 5 bps | 2794 | 83.9% | 15.581 | 27.38 | +764,863 | -1,897 | 55.7% |
| 10 bps | 2794 | 73.5% | 8.664 | 22.38 | +625,163 | -2,086 | 55.7% |

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
