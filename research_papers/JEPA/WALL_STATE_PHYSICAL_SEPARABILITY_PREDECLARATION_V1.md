# WALL_STATE_PHYSICAL_SEPARABILITY_V1

Status: predeclared before building future-path labels or inspecting any wall-state
outcome association.

## Question

Does current-time GEX/DEX wall strength, concentration, persistence/migration and
IB/Fibonacci confluence predict whether an approaching price is attracted to the
wall and, after a pierce, rejects or accepts it? This is the physical mechanism
gate required before any executable option-payoff model.

## Sealed inputs

- Wall state: `tmp/wall_state_gex_dex_202201_202512_v1/wall_state.parquet`,
  SHA-256 `94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef`.
- Executable event keys/current IB and Fibonacci distances:
  `tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet`,
  SHA-256 `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`.
- Prior-day IB distances: `training_data/training_data_spx_qqq_spy.parquet`;
  only keys, spot and `dist_ib_high_D1..D5`/`dist_ib_low_D1..D5` may be read.
- Future labels: one-minute OHLC from the `underlying_path` in source manifest
  SHA-256 `5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88`.
- Dates used: `20220801..20251231`. Any 2026 row is a hard failure.
- Tickers: SPXW, QQQ and SPY. Decision grid: exact `10:35..14:30/5m`.

Option returns, bids, asks, labels, exits, future features and June 2026 are not
read by the physical experiment.

## Wall candidates and roles

Four identities are tested without post-run selection:

| Identity | Frozen role |
| --- | --- |
| CALL gamma wall | resistance |
| PUT gamma wall | support |
| CALL delta wall | resistance |
| PUT delta wall | support |

At timestamp `t`, a candidate must be on the defended side, 15–80 bps from the
current wall, at least 3 bps closer than 15 minutes earlier, and have 15-minute
spot momentum toward the wall. The prior spot is observable at `t`; the wall is
the current wall. No candidate rule uses a future path.

## Future-path labels

Horizons are fixed at 30, 60, 120 and 180 minutes. The future path is strictly
`(t, t+h]`, requires an exact close at `t+h`, and never crosses a session.

- `magnet_hit_h`: future high/low intersects the wall's ±15 bps touch band.
- `pierced_h`: support has future low at/below the wall; resistance has future
  high at/above it.
- `true_rejection_h`: pierced and the exact horizon close is at least 5 bps back
  on the defended side.
- `accepted_break_h`: pierced and the exact horizon close is at least 5 bps on
  the opposite side.
- `resolved_rejection_h`: defined only when exactly one of true rejection or
  accepted break holds; 1 means rejection and 0 means accepted break.

The two prediction tasks are `magnet_hit_h` on all candidates and
`resolved_rejection_h` on resolved candidates. Labels are never model features.

## Frozen feature arms

All models are trained separately per ticker/target/horizon/fold.

- `D0 distance-only`: identity/role one-hot, minute sine/cosine, current signed
  and absolute wall distance, approach amount and backward spot returns 5/15/30m.
- `S1 wall-state`: D0 plus the candidate wall's magnitude, concentration,
  dominance, family HHI/effective strikes/total, age, same/move/magnitude-change
  5/15/30m, CALL/PUT balance, wall separation and net GEX/DEX/DGEX totals.
- `S2 wall-state+IB`: S1 plus count/minimum distance of current IB High/Low,
  current 1.272/1.618/2.0 extensions and prior D1–D5 IB/Fibonacci extensions
  within 15 bps of the wall, split into same-role and all-level confluence.

No generic physics/context block, absolute spot, option Greeks by delta bucket,
outcome, row selection score or post-run feature pruning is allowed.

## Model and causal folds

LightGBM binary classifier with frozen parameters: 300 trees, learning rate 0.03,
15 leaves, minimum child 100, feature/bagging fractions 0.8, bagging frequency 1,
L1 0, L2 1, deterministic/force-col-wise, seed 20260711 and 28 CPU threads.
Class weights are inverse-frequency values computed on training rows only.

Expanding annual holdouts:

- fold 2024: train through 2023-12-31, test 2024-01-01..2024-12-31;
- fold 2025: train through 2024-12-31, test 2025-01-01..2025-12-31.

There is no threshold or hyperparameter selection. Metrics are ROC-AUC, average
precision and log loss. Monthly sample/class counts are reported.

## Fixed decision gate

There are 48 planned cells per arm: 3 tickers × 2 folds × 2 targets × 4 horizons.
A missing/one-class cell remains in the denominator and is a loss.

`S2` advances to an option-payoff experiment only if all conditions hold:

1. ROC-AUC exceeds D0 in at least 32/48 cells, median delta is at least +0.010,
   and one-sided paired Wilcoxon p-value is below 0.05.
2. Each ticker wins at least 9/16 cells, has positive median delta and median S2
   ROC-AUC at least 0.55.
3. On the primary 30/60-minute subset, each ticker has at least 6/8 valid cells,
   positive median delta and median S2 ROC-AUC at least 0.55.
4. Every evaluated outer month/ticker has at least 18 labeled samples for both
   tasks at 30 and 60 minutes and both classes are present.
5. S2 average precision and log loss do not both deteriorate versus D0 in a
   majority of cells.

S1 is an attribution arm, not an alternative that may be selected after seeing
S2. Failure of any S2 gate rejects the current wall-state mechanism and forbids a
payoff model on this discovery period. Passing permits one separately predeclared
ask-to-bid payoff experiment but is not a production promotion.

Production services/package remain unchanged. June 2026 remains sealed.
