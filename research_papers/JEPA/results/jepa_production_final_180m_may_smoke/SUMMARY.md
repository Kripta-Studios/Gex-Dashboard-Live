# JEPA 180m Standalone Backtest

Data: `.\training_data\training_data_spx_qqq_spy_production_20261230_jepa_xinput_v3_production.parquet`
Model dir: `.\neural\models\jepa\jepa_production_final_180m`
Mode: `base_jepa`
Rows scored: 1,120
Execution: fixed `180`m hold, cooldown `180`m, cost `1.0` bps, notional `$100,000`.

## Overall

| Scope | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 56 | 82.1% | 18.088 | 23.89 | +13,377 | -288 | 64.3% |

## Per Ticker

| Ticker | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 18 | 94.4% | 65.931 | 34.46 | +6,203 | -96 | 66.7% |
| SPX | 20 | 80.0% | 29.946 | 20.05 | +4,010 | -78 | 70.0% |
| SPY | 18 | 72.2% | 6.765 | 17.58 | +3,164 | -288 | 55.6% |

## Cost Sensitivity

| Cost | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 bps | 56 | 82.1% | 18.088 | 23.89 | +13,377 | -288 | 64.3% |
| 3 bps | 56 | 80.4% | 13.390 | 21.89 | +12,257 | -308 | 64.3% |
| 5 bps | 56 | 78.6% | 10.104 | 19.89 | +11,137 | -328 | 64.3% |
| 10 bps | 56 | 69.6% | 5.332 | 14.89 | +8,337 | -384 | 64.3% |

## Model Thresholds

```json
{
  "SPX": {
    "feature_count": 222,
    "thresholds": {
      "long_threshold": 0.6,
      "short_threshold": 0.4,
      "val_score": 5102.570696529841,
      "val_trades": 63,
      "val_win_rate": 0.6031746031746031,
      "val_avg_net_bps": 8.626607722535809,
      "val_median_net_bps": 10.233892882187568,
      "val_total_net_bps": 543.476286519756,
      "val_profit_factor": 1.8306485397320502,
      "val_pnl_dollars": 5434.762865197559,
      "val_max_drawdown": -1328.7686746708696,
      "val_long_rate": 0.36507936507936506
    },
    "meta": {
      "mode": "base_jepa",
      "ticker": "SPX",
      "production_train": true,
      "oos_valid": false,
      "warning": "Final production artifact trained on all eligible rows; metrics are model-history diagnostics, not OOS validation.",
      "train_end_date": "20261230",
      "min_data_date": "20220801",
      "max_data_date": "20260529",
      "feature_count": 222,
      "horizon_steps": 36,
      "horizon_minutes": 180,
      "cost_bps": 1.0,
      "cooldown_steps": 36,
      "notional": 100000.0,
      "threshold_validation_months": [
        "202603",
        "202604",
        "202605"
      ]
    }
  },
  "QQQ": {
    "feature_count": 222,
    "thresholds": {
      "long_threshold": 0.57,
      "short_threshold": 0.43000000000000005,
      "val_score": 7026.408723870724,
      "val_trades": 56,
      "val_win_rate": 0.6071428571428571,
      "val_avg_net_bps": 13.03508898752455,
      "val_median_net_bps": 17.83435730978711,
      "val_total_net_bps": 729.9649833013748,
      "val_profit_factor": 2.023556806855101,
      "val_pnl_dollars": 7299.649833013749,
      "val_max_drawdown": -1092.9644365720992,
      "val_long_rate": 0.5178571428571429
    },
    "meta": {
      "mode": "base_jepa",
      "ticker": "QQQ",
      "production_train": true,
      "oos_valid": false,
      "warning": "Final production artifact trained on all eligible rows; metrics are model-history diagnostics, not OOS validation.",
      "train_end_date": "20261230",
      "min_data_date": "20220801",
      "max_data_date": "20260529",
      "feature_count": 222,
      "horizon_steps": 36,
      "horizon_minutes": 180,
      "cost_bps": 1.0,
      "cooldown_steps": 36,
      "notional": 100000.0,
      "threshold_validation_months": [
        "202603",
        "202604",
        "202605"
      ]
    }
  },
  "SPY": {
    "feature_count": 222,
    "thresholds": {
      "long_threshold": 0.57,
      "short_threshold": 0.43000000000000005,
      "val_score": 10047.637193252678,
      "val_trades": 57,
      "val_win_rate": 0.7192982456140351,
      "val_avg_net_bps": 18.050403670622924,
      "val_median_net_bps": 15.291674756157004,
      "val_total_net_bps": 1028.8730092255066,
      "val_profit_factor": 4.215051870051538,
      "val_pnl_dollars": 10288.730092255066,
      "val_max_drawdown": -964.3715960095521,
      "val_long_rate": 0.5087719298245614
    },
    "meta": {
      "mode": "base_jepa",
      "ticker": "SPY",
      "production_train": true,
      "oos_valid": false,
      "warning": "Final production artifact trained on all eligible rows; metrics are model-history diagnostics, not OOS validation.",
      "train_end_date": "20261230",
      "min_data_date": "20220801",
      "max_data_date": "20260529",
      "feature_count": 222,
      "horizon_steps": 36,
      "horizon_minutes": 180,
      "cost_bps": 1.0,
      "cooldown_steps": 36,
      "notional": 100000.0,
      "threshold_validation_months": [
        "202603",
        "202604",
        "202605"
      ]
    }
  }
}
```

## Cooldown Note

- The default cooldown is 180m because the label and execution horizon are 180m.
- This prevents stacking many overlapping 5-minute entries that mostly bet on the same future window.
- The value is configurable with `--cooldown-minutes` for sensitivity testing.
