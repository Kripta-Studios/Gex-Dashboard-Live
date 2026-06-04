# JEPA 180m Standalone Backtest

Data: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\training_data\training_data_spx_qqq_spy_jepa_xinput_v3_pipeline.parquet`
Model dir: `C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\neural\models\jepa\jepa_full_pipeline_180m_frozen_march`
Mode: `base_jepa`
Rows scored: 6,600
Execution: `max 180m` hold truncated to the last same-day row, cooldown `180`m, cost `1.0` bps, notional `$100,000`.

## Overall

| Scope | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 179 | 54.2% | 1.405 | 3.78 | +6,767 | -2,255 | 49.7% |

## Per Ticker

| Ticker | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 51 | 52.9% | 1.157 | 1.95 | +995 | -2,255 | 54.9% |
| SPX | 52 | 61.5% | 2.721 | 9.27 | +4,818 | -1,062 | 46.2% |
| SPY | 76 | 50.0% | 1.126 | 1.25 | +954 | -1,671 | 48.7% |

## Cost Sensitivity

| Cost | Trades | WR | PF | Avg bps | PnL | Max DD | Long Rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 bps | 179 | 54.2% | 1.405 | 3.78 | +6,767 | -2,255 | 49.7% |
| 3 bps | 179 | 52.0% | 1.173 | 1.78 | +3,187 | -2,715 | 49.7% |
| 5 bps | 179 | 50.3% | 0.980 | -0.22 | -393 | -3,194 | 49.7% |
| 10 bps | 179 | 43.6% | 0.624 | -5.22 | -9,343 | -9,583 | 49.7% |

## Model Thresholds

```json
{
  "SPX": {
    "feature_count": 222,
    "thresholds": {
      "long_threshold": 0.7,
      "short_threshold": 0.30000000000000004,
      "val_score": 4784.072928676833,
      "val_trades": 69,
      "val_win_rate": 0.5797101449275363,
      "val_avg_net_bps": 8.194041555956858,
      "val_median_net_bps": 7.59761003520032,
      "val_total_net_bps": 565.3888673610231,
      "val_profit_factor": 1.7284521941804214,
      "val_pnl_dollars": 5653.888673610232,
      "val_max_drawdown": -3479.2629797335967,
      "val_long_rate": 0.2463768115942029
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
      "truncate_eod_horizon": true,
      "cost_bps": 1.0,
      "cooldown_steps": 36,
      "notional": 100000.0
    }
  },
  "QQQ": {
    "feature_count": 222,
    "thresholds": {
      "long_threshold": 0.65,
      "short_threshold": 0.35,
      "val_score": 6649.165564465349,
      "val_trades": 96,
      "val_win_rate": 0.5625,
      "val_avg_net_bps": 7.5068397233512805,
      "val_median_net_bps": 4.667438747726794,
      "val_total_net_bps": 720.6566134417229,
      "val_profit_factor": 1.696265106010272,
      "val_pnl_dollars": 7206.566134417231,
      "val_max_drawdown": -2229.6022798075282,
      "val_long_rate": 0.2708333333333333
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
      "truncate_eod_horizon": true,
      "cost_bps": 1.0,
      "cooldown_steps": 36,
      "notional": 100000.0
    }
  },
  "SPY": {
    "feature_count": 222,
    "thresholds": {
      "long_threshold": 0.55,
      "short_threshold": 0.44999999999999996,
      "val_score": 5985.81241435946,
      "val_trades": 122,
      "val_win_rate": 0.5409836065573771,
      "val_avg_net_bps": 5.379368354689219,
      "val_median_net_bps": 4.183534519825894,
      "val_total_net_bps": 656.2829392720847,
      "val_profit_factor": 1.5585835656098903,
      "val_pnl_dollars": 6562.829392720846,
      "val_max_drawdown": -2308.067913445546,
      "val_long_rate": 0.32786885245901637
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
      "truncate_eod_horizon": true,
      "cost_bps": 1.0,
      "cooldown_steps": 36,
      "notional": 100000.0
    }
  }
}
```

## Cooldown Note

- The default cooldown is 180m because the maximum label/execution horizon is 180m.
- In EOD-truncated mode, late entries use the last same-day row as the terminal outcome.
- This prevents stacking many overlapping 5-minute entries that mostly bet on the same future window.
- The value is configurable with `--cooldown-minutes` for sensitivity testing.
