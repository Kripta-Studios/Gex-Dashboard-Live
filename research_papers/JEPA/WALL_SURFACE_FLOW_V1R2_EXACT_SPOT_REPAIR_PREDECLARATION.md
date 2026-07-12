# WALL_SURFACE_FLOW V1R2 — exact-spot repair predeclaration

Status: predeclared before any H-FLOW1 physical label, model score, option payoff
or PnL was built or inspected. Production and every 2026 input remain untouched.

## 1. Why V1R2 is necessary

The V1R1 full data gate rejected its input before labels. After fixing the
full-session-versus-research-window native-clock bridge, exactly two source
sessions still fail the frozen 0.001 bps candidate/underlying parity gate:

| Ticker/date | Wall rows | Rows not aligned to open(t) | Max difference |
| --- | ---: | ---: | ---: |
| QQQ 2022-12-30 | 48 | 45 | 19.688021 bps |
| SPY 2022-12-30 | 48 | 46 | 14.194464 bps |

The reproducible census must cover 2,518 available wall sessions and 120,864
wall rows. It applies one frozen rule to every session: compare all wall spots
against exact derived `open(t)` and `open(t-1m)` at tolerance 0.001 bps, then
classify `exact_t`, `hybrid_spot_tm1` or `unresolved`. Expected pre-outcome
counts are 2,516/2/0 and must be persisted with source/code/runtime hashes. Every
other session aligns to the exact derived-underlying open at the timestamp.
Both exceptional sessions instead align exactly to `open(t-1m)` for all 48 wall
rows. This rule was discovered without outcomes and was not selected from PnL.

QQQ proves that the vendor row is hybrid, not globally shifted. At 13:00 for
the 264 CALL, the stored/current 1m row has option bid/ask 1.02/1.05 from 13:00,
but `underlying_price=264.12` from 12:59. The exact 1s row at 13:00 has the same
bid/ask and `underlying_price=264.64`; its IV/delta also differ materially. It is
therefore forbidden to shift the complete 1m row, relax the bps tolerance, copy
only a new spot into the old IV, or exclude either session.

## 2. Frozen repair scope

Only these sessions may be repaired:

```text
QQQ 20221230
SPY 20221230
```

The contract universe is the intersection of the stored 0DTE Greek contract
keys with strictly positive stored OI keys for the same session:

```text
QQQ: 285 contracts
SPY: 386 contracts
total: 671 contracts
contract-key SHA256: 57c99891a37fcde939df4a88de7f45a7dffd5be544c8730046bae45e109846c0
```

Contracts added by a later provider revision may not enter. A stored positive-OI
contract missing from the exact 1s capture is a hard failure. Zero/non-finite IV
at an exact timestamp remains subject to the already frozen wall-state row filter;
it may not be imputed.

## 3. Exact causal capture

For every frozen contract, query the local, process-bound Theta Terminal endpoint:

```text
/option/history/greeks/first_order
symbol={QQQ|SPY}
expiration=20221230
strike={frozen strike}
right={C|P}
date=20221230
interval=1s
format=json
```

The builder must use `Accept-Encoding: identity`, archive the exact HTTP bytes,
hash the active Terminal JAR/Java process and runtime, and write immutable raw,
normalized and per-contract manifest artifacts. It is resumable but may seal
only 671/671 contracts with zero errors.

Only exact rows stamped at the 48 scheduled decision timestamps
`10:35,10:40,...,14:30` may enter the repair. Each contract must have exactly
one row at every timestamp, `timestamp == underlying_timestamp`, exact
symbol/expiration/strike/right identity, and no duplicate key. The full raw
response may contain other times, but those rows cannot enter a feature or wall.

For every retained row, `underlying_price` must match the already content-hashed
1s-derived underlying `open(t)` within 0.001 bps. Bid/ask must match the frozen
1m Greek at the same exact contract/timestamp within `1e-9`; any mismatch blocks
the repair because H-FLOW still uses the frozen quote/OHLC vintage. The repaired
wall calculation uses exact-1s `underlying_price` and `implied_vol` together from
the same row and never mixes repaired spot with hybrid 1m IV/delta.

Feasibility samples covering lowest strike, highest strike and maximum-OI
contract in each ticker returned 23,401 1s rows per contract, all 48 exact
timestamps and zero spot difference versus derived open(t). Deep contracts can
have zero IV in 47/48 timestamps; the existing nonpositive-IV exclusion applies.

## 4. Rebuilt artifacts

After the raw sidecar seals:

1. join its exact-1s rows to the original positive OI table;
2. call the existing `compute_wall_states` and `add_wall_persistence` functions;
3. produce exactly 48 replacement wall rows per ticker with the existing schema;
4. build exactly 48 replacement event-control rows per ticker from the same
   derived-underlying `open(t)`;
5. calculate 1/5/15/30-minute returns only from `open(t)` and
   `open(t-lag)`, both observable no later than the decision timestamp;
6. require repaired wall spot and repaired control spot to be exactly equal;
7. overlay only the two frozen session key sets, with no row additions/deletions
   elsewhere, and re-run candidate selection from scratch.

The original wall/event files remain immutable and hashed. The overlay, event
control patch, raw sidecar index and repair manifest are separate artifacts.
Their full hashes must be committed before another full surface-flow build.

## 5. Fail-closed gates

The repair is rejected if any of the following occurs:

- target scope differs from the two named sessions;
- contract count/hash differs from 285/386/671 and the frozen SHA;
- a raw response, session manifest, source Greek/OI/underlying or JAR hash changes;
- exact timestamp coverage differs from 48/48 for any contract;
- an exact row uses a timestamp after its decision;
- timestamp and underlying_timestamp differ;
- exact-1s spot differs from derived open(t) by more than 0.001 bps;
- exact-1s bid/ask differs from the frozen 1m contract row by more than `1e-9`;
- an old 1m spot, IV or delta is mixed into a repaired exposure row;
- repaired wall/control keys are not exactly 96/96;
- any non-target wall/event row changes;
- 2026, physical labels, option outcomes or PnL are read;
- the builder, runtime lock or frozen artifacts are dirty/uncommitted.

The current-provider reconstruction makes historical provenance
`CONDITIONAL`, never `PASS`. Even a successful physical result cannot be called
authoritative or promoted until a live feature-parity/shadow source exists.

## 6. Next execution order

```text
commit this predeclaration + builder/tests
capture and seal 671 exact-1s contracts
commit compact seal/index
build and commit 96 wall + 96 control repair rows and manifest
amend the surface-flow builder to require the frozen repair hashes
run the complete 2,519-session data gate again
freeze and commit the runner manifest
only then build physical labels once
```
