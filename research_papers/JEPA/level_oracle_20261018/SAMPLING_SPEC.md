# Causal rollout sampling — fixed before implementation

2026-10-18. This component selects training identities without reading labels,
execution status, returns, teacher scores or oracle columns. No market sampling
run is authorized by this document. The parent reviews the pure implementation
and fixtures before a separate one-worker identity-only export.

The sole per-day inputs are ticker, session date, and aligned action_id/state_i
integer arrays from causal actions. Allowed tickers are QQQ, SPXW and SPY;
dates are exact valid YYYYMMDD strings. IDs are unique nonnegative int64 within
the day; states are 60..375. Reject malformed, duplicate or lossy identities.
IDs are joins and sampling keys only, never model features.

Seed is fixed at 20261018 by the method. Canonical hash input is UTF-8 JSON of
the array `[seed,ticker,date,state_i,action_id]`, with separators comma/colon,
no spaces, no newline and integers rendered as decimal JSON integers. Rank by
SHA256 digest, then the complete tuple identity lexicographically. Input row
ordering cannot affect selection or output ordering.

Four fixed inclusive state bands are [60,138], [139,217], [218,296], [297,375].
Keep the lowest min(32,M_db) hashes per band; never transfer unused capacity.
Persist all four population/selected counts, including empty bands. Return
selected rows in band order and then hash/identity order. A completely empty
day returns an empty sample and four zeros; fitting rejects such days rather
than silently omitting their target population mass.

Unique-action weight is `M_db / (M_d * k_db)`, float64, with no division for
empty bands. Every nonempty day has weight sum one within floating-point
rounding. This targets uniform ticker-day mass and uniform offered actions
within a day, not uniform decision states. It corrects the within-band
sampling probability and does not filter NO_FILL or losing actions.

Teacher input days must be 2023 H1 and retain unique selected actions without
an h column. Final input days must be 2023 H2 or 2024; duplicate each selected
row adjacently as h=0, h=1, each with half its unique weight. These h values
are agent-state counterfactuals, not claims about an actual trading path.
Fit rows are ordered by ticker/date followed by the within-day sample order.
Reject duplicate ticker-days and role/period mismatches. Preserve unnormalized
weights and separately multiply all weights by N/number_of_days for global
mean one. Control and residual consume the exact same final row/weight pack.

The sampler may inspect the complete day's causal offer identities to form
an offline training subsample and compute its inclusion weights. Consequently
adding later offered actions can change earlier selected identities or weights.
This is outcome-free training subsampling, not a real-time decision feature or
a promise of prefix-invariant sampling. It never changes the causal features
of any retained state. Future labels cannot affect membership or weights.

Fixtures cover golden canonical serialization/hash, deterministic and row-order
invariant selection, fixed capacity with empty/small bands, identity validation,
input immutability, explicit no-outcome API, outcome perturbation through the
causal projection, day/IPW mass and mean-one weights, teacher/final calendar,
no teacher duplication and exact final paired half-weights. No source prices,
outcomes or model are needed for these tests.
