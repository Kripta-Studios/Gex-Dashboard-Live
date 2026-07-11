# WALL_INTERACTION_EXECQUOTE_V1R1

Status: executed once; semantic correction verified; economic result rejected.

V1 used `touch in the last 15m + current defended side + momentum away` for a
rejection. Its post-run attribution proved that only 29–37% of scheduled
rejections had ever crossed the level. This does not implement the frozen phrase
"back on the defended side" and confounds proximity with rejection.

V1r1 changes one factor only:

- support rejection additionally requires at least one of the prior 5/10/15m
  closes at or below the current support level;
- resistance rejection additionally requires at least one of those closes at or
  above the current resistance level.

The current wall is held fixed when comparing prior spot, so a moving Greek-wall
identity cannot fabricate the pierce. Magnet and acceptance definitions, level
universe, thresholds, option buckets, outcomes, dates, caps, cooldowns, hold and
one-position replay remain byte-for-byte the V1 logic. Inputs and hashes remain:

- events `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`;
- features `5f908e11090ea6566e3eadeba0a436ab5d01cf99955d6acc5050eae264fe13b5`.

The same full gates apply over `202401..202512`. This replay is adaptive failure
diagnosis on reused data and cannot promote a policy. No other event direction,
threshold, level family, time window or regime may change. June 2026 and
production remain untouched.

## Result

V1r1 improved SPXW and SPY materially but did not pass:

| Ticker | Trades | WR | PF | PnL (R) | Min month | Positive months |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPXW | 1,557 | 42.32% | 0.910 | -48.846 | 52 | 29.17% |
| QQQ | 894 | 44.18% | 0.845 | -45.816 | 30 | 33.33% |
| SPY | 496 | 47.58% | 1.008 | +1.118 | 17 | 54.17% |

The correction is real but insufficient. In V1r1, resistance-rejection PUT is
the only repeated profitable event family for SPY (65 trades, WR 60.0%, PF
1.536) and is only marginal for SPXW/QQQ (PF 1.095/1.083). Magnet CALL is
profitable for QQQ (42 trades, PF 2.230) and SPY (25, PF 1.307), but far below
the monthly volume contract. These are post-run diagnoses, not selectable arms.

Underlying-path attribution explains the remaining failure. Acceptance CALL has
roughly 58–63% directional accuracy at 30m for the scheduled V1 samples, while
acceptance PUT is below 50% and loses executable option PnL. Rejection without a
true pierce was noise; even after correction, the current feature contract lacks
wall strength, wall persistence/movement and per-strike delta wall identity.

Do not tune V1r1 thresholds, event subsets, hours or ticker-specific directions
on this output. The next defensible source build must materialize current-time
wall **state**, not just distance: per-strike gamma and delta exposure magnitude,
call/put wall identity, concentration, persistence/migration, and confluence with
current/prior IB/Fibonacci. First validate magnet/reject/accept labels on the
underlying at 30–180m; only then fit the executable option payoff/side head.
