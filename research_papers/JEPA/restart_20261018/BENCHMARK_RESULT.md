# Zone benchmark result — exploratory development

Completed one fixed 2023 train/validation/test experiment. This is previously seen development history, not untouched outer or live evidence.

This trial did not produce a profitable policy. Every representation lost money
on every ticker over the full test quarter. The authentic zones did not improve
the pooled result over the shared price/Greek control or shifted placebo, and
the paired confidence intervals include zero. This bounds one implementation;
it does not establish that all approximate visual reactions to levels are useless.

Six LightGBM regressors were fitted once: CALL and PUT for each representation.
The price control includes the same nonspatial Greek/OI aggregates as the two
zone representations. Validation was already negative for every selected policy:
price -$10,242.00, authentic -$8,505.40, placebo -$11,174.60. The fixed validation
rule selected thresholds $10/$10/$5 respectively after the trade-count gate;
it did not require positive validation PnL. Testing these policies provides a
fixed comparison, not a reason to deploy them.

The completed run used 744 ticker-days, 1,488 source files and six models, and
took 1,449.845 seconds. All source hashes matched at completion. Two earlier
attempts ended during feature construction before any model fit or test payoff:
the serial attempt was stopped for performance, and parallel v2 suffered an
unexplained worker termination. Both roots and their failure records remain.
An independent review confirmed the technical restarts preserved the per-day
values and formulas; the completed v3 uses two workers and daily checkpoints.

| Representation | Test trades | Base net USD | Adverse net USD | Base PF | Win rate |
|---|---:|---:|---:|---:|---:|
| price | 429 | -9963.40 | -10820.40 | 0.713 | 34.03% |
| authentic | 433 | -13123.80 | -13988.80 | 0.624 | 33.49% |
| placebo | 509 | -10533.40 | -11549.40 | 0.697 | 35.95% |

Per-ticker test results:

| Representation | Ticker | Trades | Base net USD | Adverse net USD | Base PF |
|---|---|---:|---:|---:|---:|
| price | SPXW | 188 | -7524.80 | -7900.80 | 0.741221946337807 |
| price | SPY | 119 | -662.40 | -900.40 | 0.7319954685224149 |
| price | QQQ | 122 | -1776.20 | -2019.20 | 0.430887536046139 |
| authentic | SPXW | 199 | -10635.40 | -11033.40 | 0.6391011632484089 |
| authentic | SPY | 126 | -994.60 | -1246.60 | 0.6239413188142773 |
| authentic | QQQ | 108 | -1493.80 | -1708.80 | 0.4626232103028996 |
| placebo | SPXW | 202 | -7929.20 | -8333.20 | 0.7191871542607824 |
| placebo | SPY | 158 | -737.80 | -1052.80 | 0.7502538758377904 |
| placebo | QQQ | 149 | -1866.40 | -2163.40 | 0.4749634297288173 |

All test ticker/month cells, base net USD (trade count in parentheses):

| Ticker | Month | Price/Greek control | Authentic zones | Shifted placebo |
|---|---|---:|---:|---:|
| SPXW | 2023-10 | -4215.80 (73) | +254.20 (73) | -2469.20 (77) |
| SPXW | 2023-11 | -1062.20 (57) | -4631.00 (60) | -2387.40 (69) |
| SPXW | 2023-12 | -2246.80 (58) | -6258.60 (66) | -3072.60 (56) |
| SPY | 2023-10 | -78.80 (53) | -266.40 (49) | -631.20 (67) |
| SPY | 2023-11 | -321.20 (27) | -486.00 (35) | -148.60 (41) |
| SPY | 2023-12 | -262.40 (39) | -242.20 (42) | +42.00 (50) |
| QQQ | 2023-10 | -747.80 (53) | -900.20 (52) | -865.80 (63) |
| QQQ | 2023-11 | -344.00 (30) | -117.60 (21) | -359.80 (38) |
| QQQ | 2023-12 | -684.40 (39) | -476.00 (35) | -640.80 (48) |

Paired circular five-session block bootstrap comparisons (2000 resamples):

{
  "authentic_minus_price": {
    "observed_net_difference": -3160.3999999999983,
    "paired_circular_5session_block_bootstrap_95ci_total_usd": [
      -12256.909999999998,
      5434.815000000001
    ],
    "days": 62,
    "block_sessions": 5,
    "resamples": 2000
  },
  "authentic_minus_placebo": {
    "observed_net_difference": -2590.4000000000005,
    "paired_circular_5session_block_bootstrap_95ci_total_usd": [
      -9997.554999999998,
      5914.294999999989
    ],
    "days": 62,
    "block_sessions": 5,
    "resamples": 2000
  }
}

Full month/ticker coverage, validation selection, source hashes, models and ledgers are preserved under D:\GexResearchArtifacts\restart_20261018\zone_benchmark_parallel_v3.

Independent audit: **PASS**. The [audit evidence](D:/GexResearchArtifacts/restart_20261018/zone_benchmark_parallel_v3/independent_audit_01/audit.json)
rehashes all 1,488 sources with zero mismatches, independently refits all six
models, reproduces 44,640 predictions and all selected thresholds, and reconstructs
2,676 validation/test ledger rows. It checks accounting for 14,880 action labels,
raw nearest-delta selection and same-contract fills for 793 unique selected test
event/side contracts, and both bootstrap comparisons on the complete 62-day
calendar. All reported economics reproduce. Summary SHA256:
`8131c315ebbcfbfde6e7853f7cfd1f174ff5c781c7ca581a147da4a9c8bcf863`.

Limitations: this audit does not independently reconstruct every raw feature,
original data arrival, or live fills. Sampled spot extrema are not OHLC;
historical quote/underlying timestamps are not observed arrival times; OI
previous-close semantics are unverified for this vintage; BS gamma is a formula
proxy with r=q=0, not measured dealer inventory. Missing entries are excluded
after fixed contract selection; missing exits liquidate at zero. No prospective
shadow is completed. No profitability or promotion claim follows from this trial.
