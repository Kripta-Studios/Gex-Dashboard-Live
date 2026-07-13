# H-GREEK2WALL-DIRECT-ALL-V1 source clarification

Status: frozen outcome-free clarification before reading any direct
`/option/history/greeks/all` value. It does not change the twelve preflight
sessions, authorize labels, or authorize a full download.

## Clock semantics

The native option `timestamp` returned by the direct all-Greeks endpoint is the
primary causal clock. A vintage first-order file that lacks `timestamp` may use
`underlying_timestamp` only for diagnostic key/parity coverage. Such a session
must be explicitly marked `underlying_timestamp_proxy`; it is never native,
never makes a native-clock gate pass, and the proxy cannot become a feature.
No native option time may be inferred from it.

### Frozen twelve-source census

This census was computed without direct-Greek values or outcomes. `OI null ts`
includes a missing timestamp column as one null per row. Late rows are after
10:19 ET; all late rows in the frozen census have OI zero.

| Ticker | Date | Greek rows | Greek clock | OI rows | OI null ts | OI late | OI late positive | OI negative | OI duplicate rows |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPXW | 20220801 | 127466 | native | 324 | 27 | 0 | 0 | 0 | 0 |
| SPXW | 20230103 | 112608 | native | 288 | 2 | 0 | 0 | 0 | 0 |
| SPXW | 20240102 | 129812 | underlying proxy | 332 | 332 | 0 | 0 | 0 | 0 |
| SPXW | 20250102 | 165002 | underlying proxy | 412 | 412 | 0 | 0 | 0 | 0 |
| QQQ | 20220801 | 92276 | native | 236 | 0 | 12 | 0 | 0 | 0 |
| QQQ | 20230103 | 73508 | native | 186 | 0 | 0 | 0 | 0 | 0 |
| QQQ | 20240102 | 128248 | underlying proxy | 328 | 328 | 0 | 0 | 0 | 0 |
| QQQ | 20250102 | 108698 | native | 278 | 0 | 0 | 0 | 0 | 0 |
| SPY | 20220801 | 119646 | native | 306 | 2 | 24 | 0 | 0 | 0 |
| SPY | 20230103 | 95404 | native | 242 | 0 | 0 | 0 | 0 | 0 |
| SPY | 20240102 | 84456 | underlying proxy | 216 | 216 | 0 | 0 | 0 | 0 |
| SPY | 20250102 | 86802 | underlying proxy | 222 | 222 | 0 | 0 | 0 | 0 |

All twelve OI files have zero null/non-finite OI values, zero negative values
and zero duplicate contract-key rows. Their deficiencies are clock availability,
not silently repairable values.

## Open-interest semantics

Canonical OI is one observation per exact contract. Identity/date mismatches,
negative values and duplicate contract keys reject the source. Null or
non-finite OI values are missing observations and retain an exact missing
reason. A null OI timestamp means availability is unknown and therefore the OI
is unavailable. A valid late timestamp is preserved: the observation is
unavailable for every direct row before that timestamp and available at and
after it. It is never globally or retrospectively backfilled.

Zero, positive, null-value, null-clock, missing-contract and late-unavailable
counts are reported per direct row and contract without affecting the direct
unit-Greek formula diagnostics. The direct endpoint remains the primary source
of native timestamp and Greek values.

## Direct OI expansion is not authorized by V1

`/v3/option/history/open_interest` would be the preferred primary reconstruction
for sessions whose local OI has no native timestamp and would preserve late
availability for 2022 QQQ/SPY contracts. The original V1 predeclaration,
however, authorizes only `/greeks/all`. Adding twelve direct-OI requests is a
new captured source and requires a separate pre-outcome amendment, request
contract, raw/seal schema and provenance freeze. This clarification does not
silently authorize or implement those requests. Until such an amendment is
frozen, local OI is vintage parity only and missing or late observations remain
unavailable under the rules above.
