# H-IBQDYN1 feature-semantics clarification

Status: frozen after the outcome-free 24-contract tick preflight capture but
before computing any H-IBQDYN1 feature value, label, model or payoff. It does
not change the 20-field allowlist, event universe, clock or economic gates.

The predeclaration made conditions and exchange-change rates audit-only. To
prevent them entering implicitly through intensity, the alpha state is
`(bid,ask,bid_size,ask_size)` and consecutive identical alpha states are
collapsed even when their timestamp/condition/exchange changes. A report that
changes only condition or exchange is quality evidence and not an alpha update.
Raw rows and full raw-state duplicates remain separately audited.

For each right over `[t-32s,t-2s)`:

- `log_update_count = log1p(number of consecutive alpha-state updates)`;
- acceleration is
  `log((updates_last_10s+1)/(updates_prior_20s/2+1))`;
- an ordered pair requires strictly increasing timestamps, each timestamp
  appearing exactly once in the raw right, finite positive non-crossed prices,
  nonnegative sizes and finite exchanges;
- signed mid pressure is `(mid_up-mid_down)/(mid_up+mid_down+1)`;
- signed spread-narrowing pressure is
  `(spread_narrow-spread_widen)/(spread_narrow+spread_widen+1)`;
- bid/ask replenishment or withdrawal counts only when that side's price and
  exchange are unchanged; alpha stores `log1p(count)`.

The four contrasts are CALL minus PUT for log update count, signed mid pressure,
bid replenishment balance `(inc-dec)/(inc+dec+1)`, and ask withdrawal balance
`(dec-inc)/(dec+inc+1)`. No missing indicator is an alpha field.

A right is preflight-valid with at least 20 distinct alpha states and at least
five ordered pairs. Before authorizing a full capture, all 12 frozen events must
have both rights valid, all 20 alpha values finite, and every alpha field must
have at least two finite values globally and within each ticker's four-year
sample. This is an outcome-free anti-degeneracy gate, not evidence of alpha.
