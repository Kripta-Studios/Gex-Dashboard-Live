# WALL_IV_SURFACE_DEFORMATION_AT_TOUCH_V1

Status: predeclared after closing `H-FLOW1` and before constructing any H-IVSURF1
feature dataset, joining physical outcomes, fitting a model, or inspecting any
association between this block and a future label or option payoff.

## Scientific question

Does causal fixed-contract deformation of the 0DTE midpoint-IV surface near a
Greek wall add stable information, beyond distance, approach, realized
volatility and time of day, about true rejection versus accepted break?

This is not a retry of static IV skew. The tested measurement is the change in
local surface level, slope and curvature on an identical strike set over the
previous 1, 5 and 15 minutes. `H-FLOW1` volume/count/close-notional features are
excluded. Static IV/skew gates, wall location alone and architecture changes
remain closed.

## Sealed universe and inputs

- Tickers: `SPXW`, `QQQ`, `SPY`.
- Dates: `20220801..20251231`; any 2026 row is a hard error.
- Candidate universe: the already sealed first, unambiguous wall-touch rows in
  `wall_surface_flow_at_touch_202208_202512_v1r2r1`, dataset SHA-256
  `6d27fdeb44422daa95aa79f777044e68276a2fe374c9bd847cd475d9dccfdb5b`.
  It contributes only keys, wall geometry and the 18 frozen F0 controls. All 139
  failed H-FLOW features are dropped before building H-IVSURF1.
- Canonical source manifest:
  `tmp/event_option_dataset_execquote_causal1030_202201_202605_v1/filtered_manifest.csv`,
  SHA-256 `5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88`.
- Greek wall surface SHA-256
  `94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef`.
- Event view SHA-256
  `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`.
- The native timestamp sidecar and exact-Greek repair bundle remain indivisible
  sealed dependencies. Their existing hashes must be copied into the new data
  manifest and revalidated; current-provider reconstruction keeps historical
  provenance `CONDITIONAL`.

Stage-1 found first-order midpoint IV in all 2,519 sessions. The separate IV
endpoint also exists but is not part of H-IVSURF1. Bid/ask-IV width is reserved
for a future independently frozen block and cannot rescue this experiment.

## Exact causal clock

The historical first-order Greek row must have an option timestamp exactly equal
to the requested snapshot clock. A missing native timestamp may be restored only
through the sealed exact-key quote-clock sidecar; `underlying_timestamp` alone is
never accepted as proof. No floor/asof join is allowed.

At decision time `t`, H-IVSURF1 uses snapshots stamped no later than `t` and
compares `t` with `t-1m`, `t-5m` and `t-15m`. ThetaData defines an interval quote
as the last quote at the interval timestamp, rather than a future completed bar.
Live/shadow promotion additionally requires recording `feature_available_at` and
proving that the `t` snapshot was received before scoring and before the entry
ask. If this ordering cannot be reproduced, the historical/live contract must be
shifted wholesale to the latest previously received snapshot before any holdout;
it may not be changed after seeing H-IVSURF1 results.

## Frozen contract and validity rules

For each candidate, anchor the current wall `W_t`, current spot `S_t`, current
0DTE expiration and current wall-relative radius. For each right separately:

1. normalize `CALL/PUT`, exact strike and exact minute;
2. intersect with the frozen Greek contract universe; source extras never expand
   the experiment;
3. keep only the identical expiration/right/strike keys present at all four
   clocks `t,t-1,t-5,t-15`;
4. require finite `0 < implied_vol < 2`, `bid > 0`, `ask >= bid`, finite
   `iv_error` and `abs(iv_error) <= 0.10` at every clock;
5. restrict the shared set using current observables only:
   `abs(K-W_t)/S_t <= 150 bps`;
6. require at least five shared strikes per right, including at least two below
   and two above `W_t`.

No delta remapping, nearest-strike replacement, temporal interpolation, forward
fill, zero fill, contract substitution or outcome-dependent filtering is allowed.
Invalid geometry retains the original candidate row with NaN surface features,
explicit validity flags and strike counts. Candidates cannot be silently removed
or turned into abstentions to improve monthly results.

QQQ 2025-08-28 CALL 650 and SPXW 2025-02-25 CALL 6045 are known IV-source extra
contracts. They are counterexamples in the gate and may never enter the frozen
Greek universe. QQQ/SPY 2022-12-30 must use the exact-Greek repair source rather
than the internally inconsistent stored first-order surface.

## Frozen surface construction

For each right and clock, fit equal-weight least squares on the identical shared
strike set:

```text
x = log(K / W_t) / 0.015
IV_tau(K) = a_tau + b_tau*x + c_tau*x^2
```

The H-IVSURF1 allowlist contains, for each `h in {1,5,15}` and
`right in {CALL,PUT}`:

```text
surface_{right}_level_change_{h}m     = a_t - a_{t-h}
surface_{right}_skew_change_{h}m      = b_t - b_{t-h}
surface_{right}_curvature_change_{h}m = 2*(c_t - c_{t-h})
```

It also contains only these quality fields:

```text
surface_call_valid
surface_put_valid
surface_both_valid
surface_call_shared_strikes
surface_put_shared_strikes
```

Current static coefficients, H-FLOW features, bid/ask size, bid/ask IV,
second/third-order vendor Greeks and option payoffs are excluded.

## Outcome-free data gate

Before any label join:

- all 2,519 sessions and exact source hashes must pass;
- duplicate normalized contract/minute keys are forbidden;
- exact timestamp and source-key intersection must pass;
- the two known IV-source extras must not change cardinality;
- no 2026 source or row may be read;
- feature schema, formulas, allowlist and missingness are frozen;
- coverage/missingness/distinctness are reported by ticker/year/month;
- no ticker-year may have `surface_both_valid < 70%`;
- every ticker must have overall `surface_both_valid >= 80%`;
- every fitted numeric feature must have at least two finite distinct values in
  each ticker-year where the block is valid;
- no future label, payoff, quote path or PnL may be read by the builder.

Failure closes H-IVSURF1 without outcomes. No radius, IV-error, strike-count or
lag rescue is allowed.

## Frozen physical experiment

Labels, horizons, F0 controls, wall identity encoding, chronological folds,
bootstrap-by-ticker-day and monthly coverage accounting remain identical to the
frozen H-FLOW1 evaluator:

- train through 2023, outer 2024;
- train through 2024, outer 2025;
- horizons 30/60/120/180m;
- future underlying prices are labels only.

Primary model: deterministic L2 Logistic Regression with train-only median
imputation, missing indicators and train-only standardization. F0 and F1 differ
only by the frozen H-IVSURF1 allowlist. `C=1.0`, `max_iter=5000`, seed
`20260712`. LightGBM with the already frozen H-FLOW1 parameters is a sensitivity
arm only and cannot rescue a failed Logistic Regression primary.

Because H-IVSURF1 is the second sequential wall-touch information block opened on
these outer years, its paired one-sided Wilcoxon threshold is tightened to
`p < 0.025`. Promotion additionally requires all original gates:

- 24/24 valid paired cells;
- at least 16/24 positive outer ΔAUC cells;
- median ΔAUC at least `+0.010`;
- each ticker at least 5/8 wins, positive median ΔAUC and median F1 AUC >=0.55;
- each ticker at least 3/4 wins in 30/60m with positive primary median ΔAUC;
- adequate monthly resolved-event coverage with both classes;
- no more than 12 joint AP/log-loss losses;
- LightGBM sensitivity must have positive median ΔAUC and at least 13/24 wins.

Outer results select nothing. No ticker-specific directions, subsets, thresholds,
months, lags or surface coefficients may be chosen afterward.

## Economic boundary

No option payoff model is authorized unless the Logistic Regression primary
passes every physical gate. A physical pass remains exploratory/conditional,
not a holdout or production result. Only then may a separately frozen economic
runner use ask entry, bid exit, 30-180m live exit semantics, no overlap and the
4/2/1 caps with QQQ 30m cooldown. The H-IVSURF1 touch stream alone is already
known to lack 18 possible trades in some QQQ/SPY months, so any final policy
would require a predeclared causal fallback and a single scheduler applied to the
union. No currently frozen fallback has demonstrated the required edge.
