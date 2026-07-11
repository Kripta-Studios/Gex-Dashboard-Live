# WALL_SURFACE_FLOW_AT_TOUCH_V1

Status: predeclared before constructing at-touch outcomes or inspecting their
association with option-surface flow.

## Motivation

Wall-state V1 proved that distance/approach predicts magnet hits, but daily-OI
strength and IB/Fibonacci confluence do not predict rejection versus accepted
break. Daily OI lacks intraday dealer inventory sign. This experiment introduces
one genuinely new source: completed option-bar activity and quote-relative price
pressure near the wall. It does not change model architecture.

The local source is not a raw trade-aggressor feed. “Signed flow” below is an
explicit proxy and must not be described as observed buyer/seller initiation.

## Sealed inputs and causal alignment

- Wall state SHA-256 `94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef`.
- Executable keys SHA-256 `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`.
- ThetaData manifest SHA-256
  `5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88`.
- Dates `20220801..20251231`; SPXW/QQQ/SPY; exact decisions
  `10:35..14:30/5m`; 2026 is rejected.
- For a decision at `t`, option OHLC timestamp `t-1` is the completed bar
  `[t-1,t)`. Its close/volume/count are observable at `t`.
- The signing quote is the exact Greeks bid/ask snapshot at the bar start. No
  `HH:MM:30` quote, current unfinished bar, future quote or backfill is allowed.

Feasibility audit on one frozen central session per ticker:

| Ticker | Valid quote coverage on active-volume rows | Active volume captured |
| --- | ---: | ---: |
| SPXW | 90.10% | 96.98% |
| QQQ | 95.44% | 97.32% |
| SPY | 91.33% | 99.58% |

## Frozen proxy features

For each contract/bar with positive volume, positive close and valid bid/ask:

- `trade_sign_proxy = +1` if bar close is above the bar-start mid, `-1` if below,
  and `0` on equality;
- signed volume = sign × volume;
- signed premium = sign × volume × close × 100;
- quote coverage and unsigned volume/count/premium are retained so missingness or
  liquidity cannot masquerade as direction.

Aggregate strictly backward windows of 1, 5 and 15 completed minutes:

- whole-surface CALL and PUT unsigned/signed volume, count and premium;
- normalized CALL-minus-PUT directional pressure;
- candidate-right pressure at strikes within 30 bps of the current wall;
- local buy/sell ratio, signed/unsigned premium ratio and quote coverage;
- role-oriented break pressure: CALL buying is positive at resistance and PUT
  buying is positive at support.

The 30-bps local radius is fixed before outcomes and covers the wall strike plus
adjacent standard strikes across all three underlyings. No radius sweep is allowed.

## At-touch universe and labels

The four identities/roles remain CALL gamma resistance, PUT gamma support, CALL
delta resistance and PUT delta support. A row is eligible when absolute current
distance to its wall is at most 15 bps. Unlike the rejected approach experiment,
this asks what happens once price is already interacting with the level.

At horizons 30/60/120/180m, require an exact same-session close:

- rejection = close at least 5 bps on the role's defended side;
- accepted break = close at least 5 bps beyond the wall;
- neutral rows inside ±5 bps have no resolved label;
- `resolved_rejection=1` for rejection and 0 for accepted break.

Future OHLC is label-only. No future high/low, option outcome or payoff is a
feature.

## Arms, folds and model

- `F0`: identity one-hot, role, minute sin/cos, current signed/absolute distance,
  backward spot returns 5/15/30m and distance change.
- `F1`: F0 plus the frozen surface-flow proxy features above.

Use the same frozen LightGBM parameters as physical V1: 300 trees, LR 0.03, 15
leaves, minimum child 100, feature/bagging 0.8, L2 1, deterministic seed 20260711
and 28 CPU threads. Class weights are train-only.

Expanding holdouts:

- train through 2023, test calendar 2024;
- train through 2024, test calendar 2025.

There are 24 cells per arm: 3 tickers × 2 folds × 4 horizons. No hyperparameter,
threshold, radius, identity or horizon is selected from test results.

## Fixed gate

F1 advances only if all hold:

1. F1 ROC-AUC beats F0 in at least 16/24 cells, median delta >=+0.010 and paired
   one-sided Wilcoxon p<0.05; missing/degenerate cells are losses.
2. Each ticker wins at least 5/8 cells, has positive median delta and median F1
   AUC >=0.55.
3. For primary 30/60m, each ticker wins at least 3/4 cells, has positive median
   delta and median F1 AUC >=0.55.
4. Every outer month/ticker at 30m and 60m has >=18 resolved rows and both classes.
5. F1 does not lose both average precision and log loss in a majority of cells.

Pass authorizes one separately predeclared ask-to-bid payoff experiment. It is not
a production promotion because this remains adaptive discovery on 2022–2025.
Failure closes the available local wall/flow source absent raw signed trades or a
genuinely new holdout. Production and June 2026 remain untouched.
