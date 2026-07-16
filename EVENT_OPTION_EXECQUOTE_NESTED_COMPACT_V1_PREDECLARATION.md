# EVENT_OPTION_EXECQUOTE_NESTED_COMPACT_V1

> **Nota de estado posterior, 2026-07-16:** este protocolo congelado ya fue
> ejecutado y cerró `CLOSED_NO_EDGE`. La nota no cambia retrospectivamente
> inputs, folds, grids ni gates. El resultado y las pruebas económicamente
> distintas posteriores se registran en la adenda final y en
> `EVENT_OPTION_EXECQUOTE_NESTED_COMPACT_V1_CLOSURE.md`.

## Purpose

This is the last authorized model-family test on the existing long-option 0DTE
event dataset. It does not build or enrich another dataset. It reuses the sealed
`executable_quote` view and tests one compact nested walk-forward selector.

The economic gate is applied independently to QQQ, SPXW and SPY:

- profit factor `>= 1.20`;
- win rate `>= 0.45`;
- at least 13 trades in every completed month (the user's `> 12` requirement);
- positive PnL in every completed month;
- entry at ask and every mark/exit at bid;
- hold between 30 and 180 minutes;
- chronological `reject_while_open` scheduling, with no overlapping position.

Passing the aggregate gate while one month fails is a rejection.

## Frozen inputs

- Dataset:
  `tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet`
- Dataset SHA-256:
  `e6a19efba1edb055c733aab4967843f7a4b5f1d2c8238a7a243fc5bbc2251903`
- Rows: `44,169`
- Date range: `2025-01-02` through `2026-06-30`
- Price contract: `option_price_mode=executable_quote`, entry ask, path/exit bid
- Exit contract: stop `-60%`, trailing activation `+50%`, drawdown `25%`,
  take-profit `+1000%`, min hold `30m`, max hold `180m`
- Runner:
  `neural/jepa/walkforward_event_option_profile_selector.py`
- Runner SHA-256:
  `082c19e34fa9158c4d7ca62f9511b32318f7936c2c3d1d9d50b04e045337c9d3`

The first launch stopped before folds/outcomes because the runner contained a
hard-coded historical June seal. The committed runner keeps `202605` as the
fail-closed default and requires the explicit cutoff in the frozen command.

## Frozen folds and model family

Outer months are exactly `202601` through `202606`. For every outer month and
ticker, the immediately preceding six completed months are inner validation;
all earlier available months are training. No outer row can choose a profile,
direction, regime gate, threshold or daily cap.

Profiles are limited to the live-contract deltas:

- SPXW: target-only 0DTE d25 return and win heads;
- QQQ: target-only 0DTE d35 return and win heads;
- SPY: target-only 0DTE d35 return and win heads.

The five causal direction mechanisms are fixed before the run:

- model CALL/PUT comparison;
- 5-minute spot trend;
- 5-minute spot counter-trend;
- 15-minute spot trend;
- 15-minute spot counter-trend.

The only optional abstention regimes are train-percentile gates over three
current-time fields: `ib_range_bps`, `phys_d35_iv_mean`, and
`phys_d35_iv_skew_put_minus_call`. Threshold percentiles and direction are the
runner's frozen `20/40/60/80` and `above/below` candidates. No VIX proxy is
invented because the historical/live VIX contract is not equivalent.

LightGBM and threshold grids remain exactly those in the command below. Live
feature checks are mandatory and the entry window starts at 10:30 ET, after the
09:30-10:29 initial balance is complete. Cooldowns are SPXW 0m, QQQ 30m and SPY
0m. Daily-cap candidates are 1, 2 and 4; overlap rejection still has priority.

## Frozen command

```powershell
python neural/jepa/walkforward_event_option_profile_selector.py `
  --data tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet `
  --output-dir research_papers/JEPA/results/_diagnostics/event_option_execquote_nested_compact_v1_202601_202606 `
  --tickers SPXW SPY QQQ `
  --train-universe SPXW SPY QQQ `
  --profile-kind production_zero_dte `
  --profile-allowlist target_zero_dte_d25_return target_zero_dte_d25_win target_zero_dte_d35_return target_zero_dte_d35_win `
  --ticker-profile-allowlists SPXW=target_zero_dte_d25_return,target_zero_dte_d25_win QQQ=target_zero_dte_d35_return,target_zero_dte_d35_win SPY=target_zero_dte_d35_return,target_zero_dte_d35_win `
  --start-month 202601 --end-month 202606 --physical-data-cutoff-month 202606 --val-months 6 `
  --clip-return 2.0 --min-train-rows 500 --min-val-rows 30 `
  --min-val-trades 78 --min-month-trades 13 `
  --min-val-pf 1.20 --min-val-win-rate 0.45 --min-val-positive-month-rate 1.0 `
  --min-call-rate 0.0 --max-call-rate 1.0 `
  --cooldown-minutes 0 --ticker-cooldown-minutes SPXW=0 QQQ=30 SPY=0 `
  --objective regression_l1 --n-estimators 240 --learning-rate 0.035 `
  --num-leaves 31 --min-child-samples 80 --subsample 0.85 `
  --colsample-bytree 0.85 --reg-lambda 5.0 --lgb-jobs 4 `
  --profile-workers 4 `
  --direction-modes model spot_5m_trend spot_5m_counter spot_15m_trend spot_15m_counter `
  --regime-gate-features ib_range_bps phys_d35_iv_mean phys_d35_iv_skew_put_minus_call `
  --regime-gate-direction any `
  --live-observable-features-only --entry-time-min-et 10:30 `
  --return-threshold-grid -0.10 -0.05 0.0 0.05 0.10 0.15 0.20 `
  --return-threshold-quantiles 0.4 0.5 0.6 0.7 0.8 0.9 `
  --win-threshold-grid 0.35 0.40 0.45 0.50 0.55 0.60 0.65 0.70 0.75 `
  --win-threshold-quantiles 0.4 0.5 0.6 0.7 0.8 0.9 `
  --max-day-grid 1 2 4 `
  --ticker-max-day-grids SPXW=1,2,4 QQQ=1,2,4 SPY=1,2,4 `
  --risk-capital 5000 --seed 20260716 --no-resume
```

## Stop rule and interpretation

There is no post-run rescue by ticker, month, delta, direction, regime,
threshold, time window or feature subset. Failure closes this 0DTE long-option
family and the next economic test must use a genuinely different payoff, not a
new feature dataset.

January-June 2026 outcomes have already been inspected elsewhere in this repo,
so this run can demonstrate row-level chronological integrity but is not a
pristine untouched holdout at the research-program level. The first prospective
period after this freeze is July 2026. On 2026-07-16 only July MTD can be
evaluated; the full-month frequency/PnL gate cannot be claimed before the month
is complete.

## Post-run addendum — historical record only

The frozen command completed and produced `CLOSED_NO_EDGE`: pooled 338 trades,
WR 37.870%, PF 0.798224 and -24.9112R. Per ticker PF was 0.804 QQQ, 0.794 SPXW
and 0.797 SPY; four of 18 outer cells abstained. Exact chronology, ask-entry,
bid-mark/exit, 30–180m hold, daily caps and same-ticker non-overlap were audited.

The predeclared next family, symmetric defined-risk short premium, did not yield
an economic result: fixed-horizon V2 proved 13 non-executable exact four-leg
exits within the first 100 of 1,506 sessions and therefore failed its data gate.
Long CALL+PUT, explicit Globex direction and direct IB/Fibonacci execution were
also tested as independent mechanisms and closed. Their results are summarized
in the closure addendum and root hand-off documents.

This section records subsequent state only. It must never be used to claim that
the original grid, selector or stop rule was predeclared with knowledge of those
later outcomes.

## Research continuation note — 2026-07-17

The compact V1 protocol and `CLOSED_NO_EDGE` verdict remain immutable. A new
pre-outcome family, `CROSS_SESSION_RELATIVE_VALUE_V1`, is now active only because
it is economically independent: spot relative-value rather than long-option
0DTE selection. It uses no compact-V1 feature, profile, threshold, option label
or 2026 outcome. Its sole authorized phase is a 2022–2023 ledger-only
development replay; this note does not retroactively alter the compact V1 stop
rule.
