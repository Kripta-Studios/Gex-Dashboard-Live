# Walk-Forward XInputJEPA OOF

Each fold trains only on months before the validation block and exports features for the held-out test month.

- OOF feature rows: `27887`
- Completed folds: `18`

## Fold Configs

```csv
ticker,month,val_months,fit_rows,val_rows,test_rows,train_windows,val_windows,best_epoch,best_score,context_valid_rate,val_total,val_acc,val_trade_precision,val_rank_ratio,val_vis,val_straight
SPX,202601,"202510,202511,202512",62726,5056,1580,30172,2432,1,0.599721185863018,0.9367088675498962,0.5516132116317749,0.38075658679008484,0.3421908915042877,0.30756810307502747,0.39650100469589233,2.0230917930603027
SPX,202602,"202511,202512,202601",64543,4819,1501,31046,2318,1,0.5522322356700897,0.9367088675498962,0.5049404501914978,0.32053494453430176,0.290214478969574,0.3108328580856323,0.3756384253501892,2.0998635292053223
SPX,202603,"202512,202601,202602",66044,4819,1738,31768,2318,1,0.6185232028365135,0.9367088675498962,0.5594477653503418,0.38654011487960815,0.4252336323261261,0.2636982500553131,0.3891071081161499,2.0744049549102783
SPX,202604,"202601,202602,202603",67782,4819,1659,32604,2318,1,0.6470425203442574,0.9367088675498962,0.591509997844696,0.33045729994773865,0.32029950618743896,0.27786991000175476,0.49300217628479004,2.104884624481201
SPX,202605,"202602,202603,202604",69362,4898,1580,33364,2356,1,0.6672063954174519,0.9367088675498962,0.6010118722915649,0.367572158575058,0.3652445375919342,0.23522190749645233,0.43865543603897095,2.1070704460144043
SPX,202606,"202603,202604,202605",70863,4977,1659,34086,2394,1,0.6421921253204346,0.9367088675498962,0.5800118446350098,0.4181286692619324,0.42147552967071533,0.2512788772583008,0.33477115631103516,2.1001856327056885
SPY,202601,"202510,202511,202512",60356,5056,1580,29032,2432,1,0.6746579147875309,0.9367088675498962,0.6029391288757324,0.34703946113586426,0.3325917720794678,0.2131248563528061,0.4110097587108612,1.9547349214553833
SPY,202602,"202511,202512,202601",62173,4819,1501,29906,2318,3,0.6852636337280273,0.9367088675498962,0.6249635219573975,0.40897324681282043,0.38793694972991943,0.25879955291748047,0.2584522068500519,1.924467921257019
SPY,202603,"202512,202601,202602",63674,4819,1738,30628,2318,1,0.6547102443873882,0.9367088675498962,0.5886791944503784,0.40379637479782104,0.3942006230354309,0.23587580025196075,0.3560602366924286,1.9736642837524414
SPY,202604,"202601,202602,202603",65412,4819,1343,31464,2318,1,0.6693361215293407,0.9367088675498962,0.5983439683914185,0.3658326268196106,0.30405405163764954,0.21603138744831085,0.41848257184028625,2.038478374481201
SPY,202605,"202602,202603,202604",66992,4582,1422,32224,2204,1,0.6428559646010399,0.9367088675498962,0.5919545888900757,0.35435572266578674,0.3239145278930664,0.2963944971561432,0.4211862087249756,1.987431526184082
SPY,202606,"202603,202604,202605",68493,4503,1501,32946,2166,1,0.6591992303729057,0.9367088675498962,0.5906709432601929,0.3951985239982605,0.37452229857444763,0.22588685154914856,0.38768190145492554,2.0108983516693115
QQQ,202601,"202510,202511,202512",60356,5056,1580,29032,2432,1,0.6494352854788303,0.9367088675498962,0.5849956274032593,0.31990131735801697,0.2678571343421936,0.24224136769771576,0.366620272397995,1.9688583612442017
QQQ,202602,"202511,202512,202601",62173,4819,1501,29906,2318,1,0.6605693027377129,0.9367088675498962,0.5985105037689209,0.37920621037483215,0.3674911558628082,0.25176480412483215,0.37495917081832886,1.990826964378357
QQQ,202603,"202512,202601,202602",63674,4819,1738,30628,2318,1,0.5949305593967438,0.9367088675498962,0.5434272289276123,0.40767902135849,0.35175344347953796,0.2939866781234741,0.34728676080703735,2.028034210205078
QQQ,202604,"202601,202602,202603",65412,4819,1343,31464,2318,1,0.6115998849272728,0.9367088675498962,0.5589644312858582,0.27178603410720825,0.23313219845294952,0.28945818543434143,0.4027886390686035,2.037229299545288
QQQ,202605,"202602,202603,202604",66992,4582,1422,32224,2204,1,0.6872816272079945,0.9367088675498962,0.6138204336166382,0.31170597672462463,0.23844419419765472,0.2061552256345749,0.4033862352371216,2.0545654296875
QQQ,202606,"202603,202604,202605",68493,4503,1501,32946,2166,1,0.7168405279517174,0.9367088675498962,0.6402835249900818,0.3337950110435486,0.312953382730484,0.19377198815345764,0.3468673825263977,2.0134356021881104

```

## Config

```json
{
  "args": {
    "data": "training_data/training_data_spx_qqq_spy.parquet",
    "output_dir": "research_papers/JEPA/results/_diagnostics/visreg_xinput_oof_baseline_202601_202606_v1",
    "tickers": [
      "SPX",
      "SPY",
      "QQQ"
    ],
    "start_month": "202601",
    "end_month": "202606",
    "val_months": 3,
    "context_len": 6,
    "horizons": "1,3,6,12,24,36",
    "z_dim": 16,
    "u_dim": 12,
    "hidden_dim": 96,
    "num_layers": 2,
    "dropout": 0.15,
    "lambda_sigreg": 0.15,
    "lambda_visreg": 0.0,
    "lambda_vicreg": 0.2,
    "lambda_straightening": 0.0,
    "straightening_speed_weight": 0.0,
    "lambda_ce": 0.15,
    "epochs": 3,
    "batch_size": 4096,
    "infer_batch_size": 8192,
    "lr": 0.0007,
    "weight_decay": 0.02,
    "clip": 10.0,
    "sigreg_projections": 64,
    "visreg_slices": 64,
    "visreg_center_weight": 1.0,
    "visreg_scale_weight": 1.0,
    "visreg_shape_weight": 1.0,
    "vicreg_min_std": 0.75,
    "balanced_sampler": false,
    "seed": 20260616,
    "device": "cuda",
    "num_workers": 8,
    "save_fold_models": false,
    "no_resume": true
  },
  "split": {
    "state_features": [
      "net_gamma",
      "net_vanna",
      "net_charm",
      "net_dgex",
      "net_zomma",
      "net_delta",
      "gamma_regime",
      "vanna_bullish",
      "charm_bullish",
      "dgex_sticky",
      "zomma_stabilizing",
      "dist_to_max_gamma",
      "dist_to_min_gamma",
      "dist_to_min_vanna",
      "dist_to_zero_gamma",
      "dist_to_max_dgex",
      "dist_to_min_dgex",
      "near_min_vanna",
      "wk_net_gamma",
      "wk_net_vanna",
      "wk_net_charm",
      "wk_net_dgex",
      "wk_net_zomma",
      "wk_net_delta",
      "wk_net_vega",
      "wk_net_vomma",
      "wk_gamma_regime",
      "wk_vanna_bullish",
      "wk_dgex_sticky",
      "wk_zomma_stabilizing",
      "gamma_0dte_vs_wk",
      "vanna_0dte_vs_wk",
      "dgex_0dte_vs_wk",
      "delta_0dte_vs_wk",
      "charm_0dte_vs_wk",
      "zomma_0dte_vs_wk",
      "vega_0dte_vs_wk",
      "vomma_0dte_vs_wk",
      "vix_5d_mean",
      "atr_5d_norm",
      "price_vs_ib_high",
      "price_vs_ib_low",
      "ib_range_pct",
      "near_ib_high",
      "near_ib_low",
      "above_ib",
      "below_ib",
      "in_ib_range",
      "dist_fib_127_up",
      "dist_fib_161_up",
      "dist_fib_200_up",
      "dist_fib_127_dn",
      "dist_fib_161_dn",
      "dist_fib_200_dn",
      "atm_iv",
      "vix_spot",
      "vix_gamma",
      "vix_regime",
      "rsi",
      "gamma_vanna_ratio",
      "dgex_gamma_ratio",
      "charm_vanna_ratio",
      "delta_gamma_ratio",
      "vega_gamma_ratio",
      "vomma_vega_ratio",
      "price_vs_dgex_magnet",
      "net_vega",
      "net_vomma",
      "vega_elevated",
      "dist_to_max_vega",
      "dist_to_min_vega",
      "dist_to_max_vomma",
      "dist_to_min_vomma",
      "confluence_ib_high_max_gamma",
      "confluence_ib_low_min_gamma",
      "confluence_ib_high_max_vega",
      "confluence_ib_low_max_dgex",
      "confluence_fib127_bull_max_gamma",
      "confluence_fib161_bull_max_vega",
      "confluence_fib127_bear_min_gamma",
      "confluence_fib161_bear_max_vomma",
      "confluence_fib161_bull_max_vomma",
      "confluence_fib127_bear_min_vomma",
      "confluence_fib127_bull_max_dgex",
      "confluence_fib127_bear_min_dgex",
      "confluence_fib161_bull_max_dgex",
      "confluence_fib161_bear_min_dgex",
      "rvol_iv_log",
      "dist_ib_high_D1",
      "dist_ib_low_D1",
      "prev_close_vs_ib_D1",
      "dist_ib_high_D2",
      "dist_ib_low_D2",
      "prev_close_vs_ib_D2",
      "dist_ib_high_D3",
      "dist_ib_low_D3",
      "prev_close_vs_ib_D3",
      "dist_ib_high_D4",
      "dist_ib_low_D4",
      "prev_close_vs_ib_D4",
      "dist_ib_high_D5",
      "dist_ib_low_D5",
      "prev_close_vs_ib_D5",
      "time_sin",
      "time_cos",
      "minutes_to_close_norm",
      "dow_sin",
      "dow_cos",
      "ib_range_percentile",
      "gap_pct",
      "gap_direction",
      "overnight_vs_ib_ratio",
      "days_to_opex_norm",
      "is_opex_week",
      "is_quarterly_opex_week",
      "gamma_phase_sin",
      "gamma_phase_cos",
      "gamma_amplitude_ratio",
      "delta_filtered_pcr",
      "confluence_d1ibh_max_gamma",
      "confluence_d1ibl_min_gamma",
      "confluence_d1ibh_max_dgex",
      "confluence_d1ibl_min_dgex",
      "confluence_d1ibh_max_vomma",
      "confluence_d1ibh_ibh_today",
      "confluence_d1ibl_ibl_today",
      "speed_x_near_ib_high",
      "speed_x_near_ib_low",
      "charm_accel_x_near_ib_high",
      "charm_accel_x_near_ib_low",
      "wonham_trend_prob",
      "nearest_level_dist",
      "level_cluster_density",
      "rejection_bullish",
      "rejection_bearish",
      "trend_grind_up",
      "trend_flush_down",
      "bouncing_from_support",
      "rejecting_resistance",
      "wall_at_fib",
      "wall_at_ib",
      "is_touching_fib",
      "is_touching_max_gamma",
      "is_touching_min_gamma",
      "is_touching_max_dgex",
      "nearest_level_id",
      "nearest_level_dist_bps",
      "gamma_x_near_fib_up",
      "gamma_x_near_fib_dn",
      "gamma_x_near_ib",
      "delta_x_near_fib_up",
      "delta_x_near_fib_dn",
      "delta_x_near_ib_high",
      "delta_x_near_ib_low",
      "vanna_x_near_fib_up",
      "vanna_x_near_fib_dn",
      "vanna_x_near_ib"
    ],
    "input_features": [
      "gamma_change",
      "vanna_change",
      "dgex_change",
      "delta_change",
      "vega_change",
      "vomma_change",
      "spot_change",
      "gamma_momentum",
      "signal_persistence_5m",
      "momentum_5m_bps",
      "ret_1m_vol_adj",
      "ret_5m_vol_adj",
      "ret_15m_vol_adj",
      "tlt_ret_1m",
      "tlt_ret_5m",
      "tlt_ret_15m",
      "gamma_speed",
      "charm_accel_weighted",
      "gamma_phase_delta",
      "pcr_derivative_5m",
      "rvol_trend",
      "rvol_regime",
      "iv_zscore",
      "iv_percentile",
      "vix_5d_std"
    ]
  },
  "feature_count": 182
}
```