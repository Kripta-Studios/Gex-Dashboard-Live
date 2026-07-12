# Native quote timestamp provenance audit — 2026-07-12

Status: outcome-free Stage 1 audit.  No option payoff, future physical label,
PnL or 2026 market row was read.  Production was not modified.

## Frozen census

Scope: SPXW, QQQ and SPY exact 0DTE sessions from 2022-08-01 through
2025-12-31, using canonical manifest SHA-256
`5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88`.

| Ticker/year | Native sessions | Fallback sessions | Native rows | Fallback rows |
| --- | ---: | ---: | ---: | ---: |
| SPXW 2022 | 107 | 0 | 16,454,062 | 0 |
| SPXW 2023 | 250 | 0 | 36,011,882 | 0 |
| SPXW 2024 | 0 | 252 | 0 | 43,820,152 |
| SPXW 2025 | 0 | 250 | 0 | 49,053,687 |
| QQQ 2022 | 78 | 0 | 7,434,474 | 0 |
| QQQ 2023 | 250 | 0 | 23,975,338 | 0 |
| QQQ 2024 | 20 | 232 | 2,238,084 | 25,624,576 |
| QQQ 2025 | 45 | 205 | 5,477,910 | 22,581,423 |
| SPY 2022 | 78 | 0 | 9,376,962 | 0 |
| SPY 2023 | 250 | 0 | 27,394,242 | 0 |
| SPY 2024 | 0 | 252 | 0 | 26,205,602 |
| SPY 2025 | 0 | 250 | 0 | 30,105,436 |
| **Total** | **1,078** | **1,441** | **128,362,954** | **197,390,876** |

All native rows have exact `timestamp == underlying_timestamp`.  All fallback
files use a regular 1m grid, but regularity does not prove the missing option
clock.  The 1,441-session fallback-key SHA-256 is
`4d4335005bb1ad29dd9f59a873a8902edcf17f1eb64c006792b29b57dea9a579`.

ThetaData documents OHLC timestamps as bar starts and documents option quote
`timestamp` separately from `underlying_timestamp`: [OHLC schema](https://docs.thetadata.us/operations_python/option_history_ohlc.html),
[historical quote](https://docs.thetadata.us/operations/option_history_quote.html),
[first-order Greeks](https://docs.thetadata.us/operations/option_history_greeks_first_order.html).
Therefore the missing clock cannot be filled by assumption.

## Recovery feasibility, not universal proof

Six complete fallback Greek chains were re-queried with explicit `interval=1m`
(SPXW/QQQ/SPY 2024-01-02 plus representative 2025 sessions).  Across 715,530
rows, current API `timestamp == underlying_timestamp` and the 10:20–14:29 stored
bid/ask/spot values matched exactly, except 332 SPXW 09:30 quotes outside the
research window that the provider now backfilled.  Historical revision is thus
observable and raw-response sealing is mandatory.

Three direct `/option/history/quote` wildcard-chain checks produced 216,000
research-window rows with exact key/bid/ask equality against stored Greeks and
non-null `bid_size`/`ask_size`.  This establishes a falsifiable recovery path,
not permission to extrapolate to all fallback sessions.

## Authoritative recovery gate

`neural/jepa/build_wall_native_quote_sidecar.py` must run from committed clean
code against a local frozen Theta Terminal.  For every fallback session it:

1. requests exact 0DTE wildcard CALL/PUT quotes at `interval=1m`;
2. captures the actual raw HTTP response bytes and headers;
3. hashes the Terminal JAR, builder, runtime, raw response, normalized Parquet
   and stored Greek source;
4. rejects non-minute/wrong-day/duplicate/invalid rows;
5. requires whole-key-set equality and exact native timestamp/bid/ask equality
   against the stored Greek research window;
6. writes immutable per-session artifacts and seals only at 1,441/1,441 PASS.

Until that seal exists, H-FLOW1 historical timestamp provenance is
`CONDITIONAL`, `PASS_DATA_GATE` is forbidden and no physical outcome runner may
claim authoritative success.  Sizes are archived for H-QSIZE1 but cannot enter
the already-frozen H-FLOW1 allowlist.

Half-day physical decisions and labels use the underlying 13:00 close.  QQQ/SPY
option trading to 13:15 is recorded as a distinct clock, consistent with Cboe's
[2024 holiday notice](https://cdn.cboe.com/resources/schedule_update/2024/Cboe-Holiday-Reminder-Modified-Trading-Hours-on-Wednesday-July-3-and-Thursday-July-4-2024.pdf).
