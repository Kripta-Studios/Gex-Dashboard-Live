# Zone benchmark result â€” exploratory development

Completed one fixed 2023–2024 train / 2025 validation / 2026 H1 test experiment. This is previously seen development history, not untouched outer or live evidence.

| Representation | Test trades | Base net USD | Adverse net USD | Base PF | Win rate |
|---|---:|---:|---:|---:|---:|
| price | 644 | -18796.40 | -20084.40 | 0.799 | 37.73% |
| authentic | 693 | -34135.80 | -35521.80 | 0.685 | 38.38% |
| placebo | 836 | -36986.60 | -38658.60 | 0.701 | 36.84% |

Per-ticker test results:

| Representation | Ticker | Trades | Base net USD | Adverse net USD | Base PF |
|---|---|---:|---:|---:|---:|
| price | SPXW | 309 | -16246.40 | -16864.40 | 0.7993062487029222 |
| price | SPY | 133 | -623.80 | -889.80 | 0.8653920849337535 |
| price | QQQ | 202 | -1926.20 | -2330.20 | 0.7567376423934736 |
| authentic | SPXW | 340 | -32309.00 | -32989.00 | 0.6625698954153619 |
| authentic | SPY | 152 | -737.20 | -1041.20 | 0.8477677280799572 |
| authentic | QQQ | 201 | -1089.60 | -1491.60 | 0.8590682153296942 |
| placebo | SPXW | 374 | -33945.40 | -34693.40 | 0.684685822779636 |
| placebo | SPY | 200 | -814.00 | -1214.00 | 0.8638841510317375 |
| placebo | QQQ | 262 | -2227.20 | -2751.20 | 0.7793496998157284 |

Frozen-policy entry delay sensitivity (no refitting or threshold selection):

| Delay minutes | Representation | Trades | Base net USD | Adverse net USD | Base PF |
|---:|---|---:|---:|---:|---:|
| 2 | price | 644 | -18337.40 | -19625.40 | 0.8069889587083059 |
| 2 | authentic | 693 | -33419.80 | -34804.80 | 0.6938019724328505 |
| 2 | placebo | 836 | -41098.60 | -42770.60 | 0.6764694768860663 |
| 5 | price | 643 | -4871.80 | -6156.80 | 0.9447348479692174 |
| 5 | authentic | 692 | -36146.20 | -37529.20 | 0.6608773644914878 |
| 5 | placebo | 835 | -43714.00 | -45383.00 | 0.6465156146394323 |

Paired circular five-session block bootstrap comparisons (2000 resamples):

{
  "authentic_minus_price": {
    "observed_net_difference": -15339.4,
    "paired_circular_5session_block_bootstrap_95ci_total_usd": [
      -47934.744999999995,
      14428.264999999921
    ],
    "days": 123,
    "block_sessions": 5,
    "resamples": 2000
  },
  "authentic_minus_placebo": {
    "observed_net_difference": 2850.799999999998,
    "paired_circular_5session_block_bootstrap_95ci_total_usd": [
      -18561.585000000006,
      23178.894999999993
    ],
    "days": 123,
    "block_sessions": 5,
    "resamples": 2000
  }
}

Full month/ticker coverage, validation selection, source hashes, models and ledgers are preserved under D:\GexResearchArtifacts\restart_20261018\wide_zone_benchmark.

Limitations: sampled spot extrema are not OHLC; the stored underlying_timestamp is an explicitly assumed quote clock when native timestamp is absent, not observed arrival time; OI without timestamp assumes prior-close availability at 09:30, unverified for this vintage; per-file and per-event clock flags and missing OI masks are retained. Entry-delay sensitivities do not certify feature arrival. BS gamma is a formula proxy with r=q=0, not measured dealer inventory; missing entries are excluded after fixed contract selection, missing exits liquidate at zero; the bounded independent audit below passed, while prospective shadow remains unstarted. No profitability or promotion claim follows from this trial.

Actual-run source coverage and clocks:

Processed 2,595 paired ticker-days and 25,950 events (51,900 fixed CALL/PUT candidates), from 5,190 hashed source files. The complete expected calendar has 867 full sessions per ticker: 248 in 2023, 249 in 2024, 247 in 2025, and 123 in 2026 H1. Eight early-close dates were excluded by the exchange calendar before values. SPXW has all 867 pairs; SPY and QQQ each have 864.

The six missing Greek files are SPY and QQQ on 2026-04-01, 2026-04-09 and 2026-04-15. Their OI files exist, but no event was fabricated; these expected days remain in coverage and the zero-trade daily calendar.

| Source | Native timestamp files | Stored underlying timestamp proxy | Assumed prior-close OI at 09:30 |
|---|---:|---:|---:|
| Greeks | 1,096 | 1,499 | 0 |
| OI | 1,096 | 0 | 1,499 |

Across every paired-clock Greek file actually used (1,096 files; 141,978,747 rows), timestamp and underlying_timestamp match exactly: zero mismatched rows. This directly strengthens the local equivalence evidence. The 1,499 files without native timestamp still use the explicitly declared research proxy; historical receipt is not observed. OI availability remains assumed for the 1,499 missing-clock files, with per-file and per-event flags.

Identity, duplicate-key and schema exclusion counts are zero. Masked invalid spot rows: 394,606; invalid quote rows: 806,027; inconsistent spot minutes: zero; invalid OI rows: zero. Event-contract missing OI observations: 63,850, retained through count/fraction masks. Event-contract invalid IV observations: 2,505,450, excluded from the gamma proxy; this is a repeated event-row diagnostic, not a count of distinct contracts.

Primary label construction across train/validation/test reports 7 missing entries and 12 missing exits (zero-liquidation rule). Delay 2 test labels have 3 missing entries and 4 missing exits; delay 5 has 3 missing entries and zero missing exits. These are candidate-label counts, not necessarily selected-ledger trades.

Validation selection was already unprofitable for every arm. The fixed count gate requires at least 10 trades per ticker; it does not impose positive validation PnL. Therefore the predeclared comparison retained the least-negative qualifying threshold, and this must not be read as permission to trade.

| Arm | Frozen threshold USD | Validation trades | Validation base net USD | Validation adverse net USD | Validation PF |
|---|---:|---:|---:|---:|---:|
| price | 10 | 1268 | -53118.80 | -55654.80 | 0.727273 |
| authentic | 10 | 1262 | -33711.20 | -36235.20 | 0.824900 |
| placebo | 5 | 1511 | -52389.60 | -55411.60 | 0.754092 |

All predeclared validation choices (base net USD):

| Arm | Threshold 0 | Threshold 5 | Threshold 10 |
|---|---:|---:|---:|
| price | -66081.20 | -67851.00 | -53118.80 |
| authentic | -40087.20 | -34307.20 | -33711.20 |
| placebo | -53956.00 | -52389.60 | -59764.40 |

Six real models were frozen at 2026-10-18T15:19:39.257129+00:00 before test payoff construction. Execution took 2201.303 seconds. Final rehash: 5,190 sources, zero mismatches. Summary SHA256: e014cab7dca88c41fa0ff494d0736261ec9aa3c5eb6dbc47ba8d225ee780041f.

Every pooled primary and entry-delay sensitivity is negative. Authentic zones do not demonstrate an advantage over either control: both paired confidence intervals include zero. The proper conclusion is failure of this fixed model/representation/policy on the declared development split, not proof that approximate visual reactions at IB/Fibonacci/OI zones can never exist. The price arm includes the shared nonspatial Greek/OI context; it is not an ablation of all option information.

Independent audit completed with PASS_INDEPENDENT_WIDE_EXPLORATORY_BENCHMARK_AUDIT. The producer code, source files, models, predictions, thresholds and specification remain unchanged.

Independent audit evidence: [audit.json](D:/GexResearchArtifacts/restart_20261018/wide_zone_benchmark_audit/audit.json), with method and limits in [WIDE_BENCHMARK_REVIEW.md](WIDE_BENCHMARK_REVIEW.md).

The separate auditor rehashed all 5,190 sources with zero mismatches; independently refitted all six models and reproduced 155,700 predictions exactly; checked 66,420 accounting rows; reconstructed 6,214 primary ledger rows and 4,343 latency ledger rows; checked 3,733 selected raw test rows and corresponding OI missing masks, including 62 selected fallback-clock days; and reconstructed the 123-session test calendar and both paired bootstrap comparisons. The primary ledger row count includes validation plus test across all three arms, not 6,214 unique test trades.

This is a bounded independent implementation/accounting audit, not full reconstruction of every raw feature. Historical quote receipt, prior-close OI receipt, live parity and untouched outer status remain unverified. technical_ready=false and promotion_approved=false. The economic result remains a failure of this fixed exploratory experiment despite the successful audit.
