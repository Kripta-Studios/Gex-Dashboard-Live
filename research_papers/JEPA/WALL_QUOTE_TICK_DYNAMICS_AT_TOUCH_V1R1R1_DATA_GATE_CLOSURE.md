# WALL_QUOTE_TICK_DYNAMICS_AT_TOUCH_V1R1R1 data-gate closure

Status: `CLOSED_DATA_GATE` without opening outcomes, labels, models, option
payoff or 2026. Repository checkpoint: `d2c23ec`.

## Authoritative build

Immutable target:
`tmp/wall_quote_tick_dynamics_at_touch_202208_202512_v1r1r1`.

- rows: 10,683;
- columns: 67;
- dataset SHA256:
  `2a7147ccaa60bb41419a3c1b100e1857a701249c970dc276a602f10147fb265a`;
- source inventory SHA256:
  `a65f4435820f504529f5684055c50db8428b095f837238e0f8ffe86291673398`;
- status: `REJECTED_DATA_GATE`;
- `coverage_pass=true`;
- minimum annual both-valid: `0.8942084942084942`;
- minimum ticker both-valid: `0.9072749691738594`;
- `distinctness_pass=false`.

The sealed capture remains valid. The earlier builder failure in which
`set_index` removed `event_id` was fixed fail-closed in commit `85de313` and is
not causal to this rejection.

## Frozen failure

The predeclaration requires every dynamic feature to have at least two finite,
distinct states in every ticker-year. Exactly 18 ticker-year-feature cells fail:

- SPXW 2022, 2023, 2024 and 2025: all four CALL/PUT bid/ask exchange-change
  fractions are constant zero (16 cells);
- SPXW 2025: CALL and PUT
  `unambiguous_state_change_fraction` are constant one (2 cells).

Coverage therefore passes, but the frozen measurement block is degenerate in
SPXW. By the predeclared contract, this failure closes H-QDYN1 without labels.
No feature may be removed, redefined or selected after this result; no ticker,
year, subgroup, model or threshold rescue is permitted.

## Consequence

No frozen runner, physical F0/F1 evaluation, label join, payoff model or
economic claim is authorized for H-QDYN1. There is no H-QDYN PF, WR or PnL.
The next independent action is the already predeclared 12-session
H-GREEK2WALL direct higher-order-Greeks feasibility preflight.
