# Independent wide benchmark review — 2026-10-18

Status: PREEXECUTION_REVIEW_COMPLETE_EXPLORATORY_RUN_READY.

The reviewer owns this report and `audit_wide_zone_benchmark.py` only. The
producer, specification and local source files were read without modification.
No economic output from the native 2023 benchmark or this wide benchmark was
opened during this preexecution review.

## Scope and fixed interpretation

The experiment is a bounded, seen-development comparison. It trains on
2023–2024, selects one threshold per representation on calendar 2025 and tests
January–June 2026. Price/common context, authentic soft Fibonacci/OI/gamma-proxy
zones and a daily hashed spatial placebo use identical event candidates and
fixed CALL/PUT model budgets. D+2 and D+5 are execution-delay sensitivities of
the same frozen policy; they are not new models, new selections or evidence of
feature receipt latency.

The stored `underlying_timestamp` fallback is admissible here only as the
declared research clock proxy. The paired-file probe supports exact equality in
the inspected sample but does not establish historical receipt time. Likewise,
timestamp-free OI is explicitly treated as assumed prior-close information
available at 09:30. This is not an observed delivery time or live-parity claim.

## Preevaluation checks

1. The XNYS calendar is constructed independently of source availability.
   Early closes are excluded before values, while all expected full sessions,
   including all 123 test sessions, remain in coverage and daily zero reporting.
2. The six-worker day pool uses input-order `map`; results, source metadata and
   artifacts therefore merge in deterministic ticker/date order. Each worker
   limits Arrow to one CPU. The six LightGBM fits remain sequential and CPU2.
3. Greek clocks prefer native `timestamp`. Absence invokes the stored
   `underlying_timestamp` without rounding. Per-file clock source and paired
   mismatches, plus per-event Greek/OI clock flags, are retained. Exact minute
   grid, date, symbol, expiration, right, positive strike and unique
   contract/time identities are enforced.
4. Timestamp-free OI is placed at 09:30 under the named unverified prior-close
   assumption. Native OI remains subject to `timestamp <= feature_time`.
   Missing contracts contribute zero weight while their count and fraction stay
   in the shared feature set.
5. IB uses only 09:30–10:29 stored minute observations and requires 57/60. The
   selected contract is fixed at D-1 by nearest absolute delta 0.50. Future
   entry availability cannot substitute another side or contract; absent entry
   skips the chosen action and absent exit liquidates at zero plus costs.
6. Training ends before 2025, validation ends before 2026, and test payoffs are
   absent from the pretest label artifact. Models, feature/candidate artifacts,
   source manifest, predictions and thresholds are hashed before any test label
   construction. D+2/D+5 replace only entry/exit timestamps and rerun no-overlap
   scheduling with the frozen prediction, action and threshold.
7. The primary bootstrap is paired on the complete expected 2026 H1 full-session
   calendar with common seeded circular five-session blocks. Missing-source and
   no-trade days remain explicit zeros.

Synthetic review completed with 16 passing tests before the final full-day
proxy-clock fixture was added; Ruff and Python compilation also passed. No
execution-blocking causal, identity, scheduling or accounting defect was found.

## Independent postrun audit

`audit_wide_zone_benchmark.py` imports no producer calculation. It verifies all
artifact and source seals; independently refits the six fixed models and requires
exact saved predictions; reconstructs validation threshold selection, all three
latency schedulers, Decimal accounting, ledgers, ticker/month cells, complete-day
daily totals and both seeded bootstrap comparisons. It also checks selected raw
test contracts and fills using native or fallback clocks and independently
reconstructs OI cutoff/missingness for selected test events.

The audit deliberately does not claim a full independent rebuild of every raw
feature. It cannot verify historical receipt, prior-close delivery time, market
fills, dealer inventory, live parity or future profitability. Any economic result
remains exploratory development with `technical_ready=false` and
`promotion_approved=false`.

## Postrun audit result

Status: PASS_INDEPENDENT_WIDE_EXPLORATORY_BENCHMARK_AUDIT.

The independent run completed at 2026-10-18T15:32:07Z under
`D:/GexResearchArtifacts/restart_20261018/wide_zone_benchmark_audit`. It rehashed
5,190 source files with zero mismatch and reproduced all six model fits and saved
prediction vectors exactly. It reconstructed 66,420 accounting rows, 6,214
primary validation/test ledger rows, 4,343 D+2/D+5 ledger rows, all ticker/month
metrics, the 123-session test calendar and both seeded paired bootstraps. Direct
raw checks covered 3,733 selected test rows and their OI missingness masks,
including 62 selected proxy-clock days. Summary SHA256 is
`e014cab7dca88c41fa0ff494d0736261ec9aa3c5eb6dbc47ba8d225ee780041f`.

The source manifest is internally consistent: 2,595 Greek and 2,595 OI files.
Of the Greek files, 1,096 carry both stored clocks across 141,978,747 rows with
zero reported mismatch; 1,499 use the declared underlying-clock proxy. OI has
the matching 1,096 native-clock and 1,499 assumed-prior-close split. The full
calendar retains six missing Greek sessions as zero-activity coverage cells:
SPY and QQQ on 2026-04-01, 2026-04-09 and 2026-04-15. Their orphan OI files were
not consumed or placed in the source manifest.

All three primary 2026 test arms are economically negative: price has 644 trades,
-$18,796.40 base net and PF 0.7990; authentic has 693 trades, -$34,135.80 and
PF 0.6849; placebo has 836 trades, -$36,986.60 and PF 0.7011. Authentic remains
negative at D+2 (-$33,419.80, PF 0.6938) and D+5 (-$36,146.20, PF 0.6609).
The fixed comparison therefore supplies no profitable arm and no promotion case.

There is one interpretation qualification rather than an audit mismatch. Every
threshold met the validation count gate, but every validation net was negative.
The fixed ranking still selected thresholds 10/10/5 for price/authentic/placebo,
because the declared `NO_TRADE` state applies only when no threshold qualifies.
A literal zero-trade benchmark dominates every selected validation policy. This
does not invalidate protocol reconstruction, but it prevents describing the
frozen choices as favorable relative to abstention.
