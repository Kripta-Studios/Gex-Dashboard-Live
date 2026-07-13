# H-IBQDYN1 HTTP 472 no-data amendment

Status: frozen after the outcome-free full-capture source pass and before any
H-IBQDYN1 physical label, option payoff, model score or 2026 row was opened.
This amendment repairs source representation only; it does not change the event
universe, contracts, tick window, features, coverage gates or models.

## Observed source result

The first immutable pass attempted all 33,704 frozen contracts. It produced
33,700 complete raw/parquet/manifest directories and no staging directory. The
only four failures are the two rights of two events, all at 2023-10-25 10:35 ET
and with the original `[10:34:28.000,10:34:57.999]` tick window:

| Contract id | Ticker | Event id | Right | Strike |
| --- | --- | --- | --- | ---: |
| `ead903c57890cd8a477a2ac0` | SPXW | `60d8c2b0bec9c102a94d851b` | CALL | 4230 |
| `0832f62f2c76c32275bc5f36` | SPXW | `60d8c2b0bec9c102a94d851b` | PUT | 4185 |
| `311e42908cc0dc01befb5660` | SPY | `f4a0e57699fbd8b67cee8937` | CALL | 421 |
| `1785ce6e2835a5fa7abca84d` | SPY | `f4a0e57699fbd8b67cee8937` | PUT | 418 |

The first-attempt error JSON is 1,538 bytes with SHA-256
`e4dc58192b18944778fe819a397d03c9e4e5fb2a29870b7de63ca1b500859af7`.
The sorted four-contract-id inventory SHA-256 is
`4a44551fde020af61174b9e70162122441b6c5736f3e274b988f6f66104238a7`.

After the pass, MDDS was still `CONNECTED` and an exact retry of every request
again returned HTTP 472 with the 30-byte body `No data found for your request`
(SHA-256
`101a4aa84466574e08fbb09d1405a816323a4674fd107dc28f3f0d29e3e3708c`).
ThetaData v3 defines 472 as `NO_DATA`, not a permission, parameter or connection
failure: <https://docs.thetadata.us/Articles/Data-And-Requests/Making-Requests.html>.

## Frozen representation

The original full-capture contract already permits `rows == 0`, records
`zero_row_contracts`, and the later data gate uses explicit both-valid coverage
below 100%. Only the request layer incorrectly raised 472 before it could
materialize a valid empty-window artifact.

A V1R1 source repair may therefore materialize only the four contracts above,
and only after the exact request again returns status 472, the exact body hash,
the same request parameters and `CONNECTED` source provenance. For each one it
must store:

- the byte-exact text response and HTTP headers/status;
- an empty parquet with the frozen tick schema and no fabricated quote row;
- a versioned no-data manifest with raw/parquet/code/runtime hashes;
- an index row with `rows=0` and explicit `capture_kind=HTTP_472_NO_DATA`.

The existing 33,700 contract directories are immutable and must retain their
original capture-code hashes. The V1R1 sealer must revalidate all their raw,
parquet and manifest hashes before publishing a 33,704-row index. It must also
prove exactly four zero-row contracts, exactly the inventory above, zero
unresolved errors and zero staging directories.

If any of the four exact requests returns HTTP 200, its real response must be
captured normally instead. Any other missing contract, status, body, strike,
right, date or window rejects the seal. No nearest strike, wider time interval,
as-of quote, synthetic row or provider substitution is permitted.

## Downstream treatment

The two affected events remain in the 16,926-row dataset and remain listing-
eligible. Their tick block is both-right invalid, all 20 alpha fields are
missing, and they count against the frozen coverage denominators. They cannot
enter the physical complete-case mask or become a missingness signal. The
80% ticker-year, 85% ticker, distinctness and identical-complete-case gates are
unchanged.

This amendment authorizes no label, F0/F1 result, payoff, PF, WR, PnL, 2026
access or production change.
