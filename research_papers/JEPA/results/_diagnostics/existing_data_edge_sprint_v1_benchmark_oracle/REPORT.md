# Existing-data benchmark and oracle audit V1

## Published benchmark reproduction (existing January--May 2026 trades only)

Exact stored-metric reproduction: `True`; maximum absolute difference `7.105427357601002e-15`.

| ticker | trades | win_rate | profit_factor | pnl_return | minimum_monthly_trades | positive_month_rate | max_drawdown | call_rate | abstention_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SPXW | 107 | 0.429907 | 0.83152 | -5.81639 | 10 | 0.4 | -9.65604 | 0.224299 | 0.97471 |
| QQQ | 94 | 0.446809 | 0.983707 | -0.492363 | 15 | 0.4 | -6.54991 | 0.276596 | 0.973655 |
| SPY | 123 | 0.439024 | 0.919499 | -2.97866 | 19 | 0.4 | -6.69592 | 0.170732 | 0.970058 |

The reference stream has zero overlap/cooldown violations and all holds are 30--180 minutes. It is not the fixed scheduler-cap contract: its frozen search allowed SPY max-day 2, and 30 SPY days used a second trade. The cap-normalized diagnostic is:

| ticker | trades | win_rate | profit_factor | pnl_return | minimum_monthly_trades | positive_month_rate | max_drawdown | call_rate | abstention_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SPXW | 107 | 0.429907 | 0.83152 | -5.81639 | 10 | 0.4 | -9.65604 | 0.224299 |  |
| QQQ | 94 | 0.446809 | 0.983707 | -0.492363 | 15 | 0.4 | -6.54991 | 0.276596 |  |
| SPY | 93 | 0.451613 | 0.971936 | -0.773071 | 14 | 0.4 | -4.46959 | 0.204301 |  |

Full month metrics are in `benchmark_monthly.csv`.

## 2023 development-only oracle decomposition

Causal control: existing Pairwise-V1 C0 heads; fixed opportunity threshold 0.50; side is the larger CALL/PUT win probability. No 2024/2025 row was materialized and no oracle value selected a setting.

| strategy | ticker | trades | win_rate | profit_factor | pnl_return | minimum_monthly_trades | positive_month_rate | max_drawdown | call_rate | abstention_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| causal_opportunity_causal_side | SPXW | 560 | 0.410714 | 0.827748 | -34.5332 | 53 | 0.333333 | -50.2178 | 0.655357 | 0.91911 |
| causal_opportunity_causal_side | QQQ | 353 | 0.439093 | 0.793536 | -25.3257 | 32 | 0.444444 | -30.0003 | 0.566572 | 0.942788 |
| causal_opportunity_causal_side | SPY | 187 | 0.454545 | 0.861804 | -7.75614 | 19 | 0.555556 | -16.4301 | 0.518717 | 0.973 |
| causal_opportunity_oracle_side | SPXW | 549 | 0.8051 | 5.83818 | 259.035 | 52 | 1 | -2.90278 | 0.497268 | 0.920699 |
| causal_opportunity_oracle_side | QQQ | 353 | 0.878187 | 9.81103 | 172.607 | 32 | 1 | -1.2536 | 0.560907 | 0.942788 |
| causal_opportunity_oracle_side | SPY | 187 | 0.823529 | 8.31523 | 74.296 | 19 | 1 | -1.02522 | 0.529412 | 0.973 |
| oracle_opportunity_causal_side | SPXW | 537 | 1 | inf | 501.725 | 44 | 1 | 0 | 0.620112 | 0.922432 |
| oracle_opportunity_causal_side | QQQ | 343 | 1 | inf | 351.872 | 33 | 1 | 0 | 0.562682 | 0.944408 |
| oracle_opportunity_causal_side | SPY | 185 | 1 | inf | 237.818 | 19 | 1 | 0 | 0.589189 | 0.973289 |
| oracle_opportunity_oracle_side | SPXW | 671 | 1 | inf | 732.039 | 65 | 1 | 0 | 0.503726 | 0.903077 |
| oracle_opportunity_oracle_side | QQQ | 367 | 1 | inf | 458.728 | 37 | 1 | 0 | 0.514986 | 0.940519 |
| oracle_opportunity_oracle_side | SPY | 187 | 1 | inf | 297.831 | 19 | 1 | 0 | 0.459893 | 0.973 |
| always_call | SPXW | 636 | 0.429245 | 0.801751 | -44.1484 | 59 | 0 | -45.6128 | 1 | 0.908132 |
| always_call | QQQ | 369 | 0.485095 | 0.935575 | -7.33041 | 38 | 0.222222 | -12.3357 | 1 | 0.940194 |
| always_call | SPY | 187 | 0.465241 | 0.790166 | -12.2743 | 19 | 0.444444 | -13.0889 | 1 | 0.973 |
| always_put | SPXW | 666 | 0.382883 | 0.757165 | -59.2993 | 66 | 0.111111 | -65.271 | 0 | 0.903799 |
| always_put | QQQ | 368 | 0.402174 | 0.726814 | -36.0889 | 37 | 0.111111 | -41.8316 | 0 | 0.940357 |
| always_put | SPY | 187 | 0.42246 | 0.722505 | -17.034 | 19 | 0.333333 | -22.9777 | 0 | 0.973 |
| random_side_seed_20260714 | SPXW | 645 | 0.437209 | 0.906054 | -20.5237 | 63 | 0.555556 | -34.806 | 0.505426 | 0.906832 |
| random_side_seed_20260714 | QQQ | 368 | 0.453804 | 0.779241 | -26.8188 | 37 | 0.222222 | -37.5906 | 0.467391 | 0.940357 |
| random_side_seed_20260714 | SPY | 187 | 0.411765 | 0.735252 | -16.4702 | 19 | 0.222222 | -17.54 | 0.518717 | 0.973 |
| oracle_opportunity_oracle_side_no_scheduler | SPXW | 5483 | 1 | inf | 4080.64 | 514 | 1 | 0 | 0.530367 | 0.208002 |
| oracle_opportunity_oracle_side_no_scheduler | QQQ | 5133 | 1 | inf | 3466.59 | 450 | 1 | 0 | 0.553283 | 0.168071 |
| oracle_opportunity_oracle_side_no_scheduler | SPY | 5709 | 1 | inf | 3839.93 | 548 | 1 | 0 | 0.532493 | 0.175715 |

Attribution:

```json
{
  "side_error_headroom_r_on_causal_opportunities": 573.5528037681438,
  "opportunity_error_headroom_r_with_causal_side": 1159.0300395783952,
  "joint_oracle_headroom_r": 1556.213897619398,
  "scheduler_drag_upper_bound_r": 9898.564139466569,
  "execution_drag": {
    "status": "UNAVAILABLE_FROM_EXISTING_LABELS",
    "reason": "The sealed modeling parquet contains ask-entry/bid-exit returns but no matched midpoint-exit path label. Reconstructing a no-spread counterfactual would require a forbidden new path/source."
  },
  "interpretation_guard": "All oracle quantities use future executable outcomes and are non-promotable."
}
```

Execution drag is not identifiable from the existing ask-to-bid label alone; it is reported as unavailable, not estimated. All oracle rows are diagnostic and non-promotable.
