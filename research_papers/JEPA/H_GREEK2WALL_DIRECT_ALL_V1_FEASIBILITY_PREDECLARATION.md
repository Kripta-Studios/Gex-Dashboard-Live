# H-GREEK2WALL-DIRECT-ALL-V1 feasibility predeclaration

Status: outcome-free data-feasibility protocol. It authorizes only the 12-session
preflight below after H-QDYN capture no longer contends for the local Terminal.
It does not authorize labels, PnL, a full historical download or model fitting.

## New measurement and question

ThetaData v3 exposes timestamped second/third-order Greeks directly through
`/v3/option/history/greeks/all`. The narrow question is whether intraday
deformation and migration of the per-strike vanna, charm, vomma and zomma
profiles near an approached gamma/delta wall provide causal information beyond
distance, approach velocity, realized volatility and time of day.

Static second-order wall distance, global totals, generic physics expansion and
IB/Fibonacci confluence remain closed. Veta, speed, color, ultima and other
returned fields are audit-only and cannot enter this first block.

Official provider semantics used by this protocol:

- Open interest is normally published around 06:30 ET and represents the end
  of the previous trading day:
  `https://docs.thetadata.us/operations/option_history_open_interest.html`.
- Direct all-Greeks history includes native option timestamp, bid/ask,
  first/second/third-order Greeks, IV and underlying timestamp/price:
  `https://docs.thetadata.us/operations/option_history_greeks_all.html`.

OI is therefore causally available for decisions after 10:20 ET, but it is not
dealer-position sign. OI-times-Greek is a mathematical profile only.

## Frozen 12-session preflight

Select the lexicographically first canonical session in the sealed research
range for each ticker-year, before reading any direct-Greek value:

| Ticker | 2022 | 2023 | 2024 | 2025 |
| --- | --- | --- | --- | --- |
| SPXW | 20220801 | 20230103 | 20240102 | 20250102 |
| QQQ | 20220801 | 20230103 | 20240102 | 20250102 |
| SPY | 20220801 | 20230103 | 20240102 | 20250102 |

For each session request the complete 0DTE chain, both rights, `interval=1m`,
`start_time=10:19:00.000`, `end_time=14:30:00.000`, `version=latest`, through
the local Terminal and active serving JAR. Preserve raw response bytes and a
normalized parquet in an immutable per-session directory.

## Outcome-free gates

The preflight must record and hash request parameters, raw bytes, normalized
parquet, response schema, local process/JAR/runtime and source inventories. It
must report, without outcome association:

- exact symbol, expiration, trade date, strike, right and native timestamp;
- duplicate-key and contract-substitution counts;
- timestamp grid, first/last update and any timestamp after the request clock;
- rows and raw/parquet GiB per session and projected 2,519-session cost;
- finite, zero, sign and distinct-value profiles for gamma, vanna, charm,
  vomma and zomma by ticker-year;
- bid/ask/IV/underlying parity against sealed vintage first-order keys without
  replacing vintage values;
- positive prior-day OI join coverage and missing-contract reasons;
- direct-versus-local formula rank/sign/scale diagnostics, never a selector.

Reject the full build if any required field is absent, timestamps cannot be
made exact, wildcard contracts substitute the universe, or projected cost is
not operationally acceptable. Provider historical values are classified
`CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION`, not vintage truth.

## Future block if and only if feasibility passes

The later one-factor F1 block may contain only fixed per-family local
slope/curvature, max/min wall migration at 1/5/15m, same-strike persistence and
local-share/top1-top2 dominance changes for vanna/charm/vomma/zomma. F0 remains
distance, approach, realized volatility and time of day. All sign conventions,
OI multiplication, 16:00 versus 16:15 expiration clock and live endpoint parity
must be frozen before labels. No family/ticker/wall may be selected after an
outer result.
