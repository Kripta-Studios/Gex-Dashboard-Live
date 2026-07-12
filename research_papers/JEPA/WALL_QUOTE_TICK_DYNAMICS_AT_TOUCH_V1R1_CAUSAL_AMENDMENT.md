# WALL_QUOTE_TICK_DYNAMICS_AT_TOUCH_V1R1 causal amendment

Status: frozen before any H-QDYN1 label join, model fit, physical result or
payoff result. This amendment supersedes the subscription-eligibility proof in
V1; the 9,833 count and its hash are withdrawn and may not be used.

## Why V1 was stopped

The V1 code proved that the eventual wall strike at decision time `t` was
within 150 bps of one of four walls observable at `t-5m`. It did not prove that
the exact 0DTE CALL and PUT contracts at that strike were already listed in the
subscription universe at `t-5m`. Selecting that strike retrospectively at `t`
could therefore read a contract that a live subscriber could not have buffered.

The capture started from commit `9c42be5` and was terminated during the
outcome-free download after this adversarial finding. The partial directory
`D:/ThetaData/wall_quote_tick_dynamics_at_touch_202208_202512_v1` is
`REJECTED_CAUSAL_ALLOWLIST` and must never be resumed, sealed, joined to labels
or used for feature/model work.

## Exact listing proof

V1R1 retains the frozen wall-proximity rule and adds an independent exact
contract-listing condition. For every one of the 10,683 frozen candidates:

1. Let `s = t-5m`.
2. Read only the sealed native quote snapshot for the same ticker/session at
   exact timestamp `s` from the union of the 1,441-session native sidecar and
   the 1,078-session complement sidecar.
3. Require `symbol=ticker`, `expiration=trade_date`, `strike` exactly equal to
   `candidate_wall_strike`, and the presence of both rights `C` and `P` at `s`.
4. Presence proves listing only. Bid, ask, size, signability and any later state
   must not affect eligibility.
5. `causal_subscription_eligible_v1r1` is true only when both the original
   wall-proximity rule and this exact both-right listing rule pass.

No nearest-strike mapping, timestamp as-of join, rounding, forward fill or
provider query at `t` is allowed. Sessions whose native snapshot does not cover
`s` remain explicitly ineligible. In particular, early candidates whose `s`
precedes the frozen research grid cannot be inferred from a later snapshot.

The proof builder must revalidate the two sidecar seals, all 2,519 session index
keys and hashes, every session quote parquet hash, the frozen candidate hash and
wall-state hash. It emits exactly 10,683 unique event rows, source-session
inventory, exact failure reasons and a canonical manifest. Counts and hashes
are descriptive data-feasibility facts only; they will be frozen in a separate
seal checkpoint before a replacement tick capture.

## Replacement capture requirements

The replacement capture must use a new immutable V1R1 output directory and
must require the frozen listing-proof hash. Before any PASS seal it must:

- revalidate every raw response, normalized parquet and event manifest;
- bind the full local Terminal process evidence, command line, active serving
  JAR hash, local address/port and base URL;
- test exact inclusion of `t-32s`, exact exclusion of `t-2s`, and rejection of
  all timestamps before the window;
- classify missing/duplicated contract blocks and missing rights explicitly;
- recover or quarantine abandoned staging directories without overwriting an
  immutable completed event.

The 28 frozen dynamic features, physical folds and sequential `p<0.0125` gate
remain unchanged. Live parity remains blocked. No outcome may be opened merely
to decide whether this stricter eligibility is convenient.
