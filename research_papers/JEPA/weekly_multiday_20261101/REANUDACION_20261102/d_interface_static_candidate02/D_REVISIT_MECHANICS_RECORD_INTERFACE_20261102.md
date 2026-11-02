# D revisit mechanics: in-memory record interface

Status: `SYNTHETIC_MECHANICS_ONLY`. This standard-library, caller-owned record
interface exists for artificial fixtures only. It performs no I/O, adapter,
Arrow work, binding, benchmark-C read/copy/calculation, or real replay closure.
Artificial output is never `D_REVISIT_REPLAY_CLOSED`, never a real
`SEEN_DEVELOPMENT` PASS, and never profitability evidence.

`evaluate_revisit_mechanics(plans, anchors, spots, quotes, *, config)` accepts
only normalized Python mappings/sequences and returns `status`, `events`,
`ledger`, `plan_coverage`, and `counts`.

## Scalar, byte, and fixed-policy rules

Dates are ASCII ISO `YYYY-MM-DD`. Every `*_local_ns` is a signed built-in `int`
(never bool) representing NY-naive civil nanoseconds; the interface performs no
timezone conversion or numeric coercion. Source floats are caller-provided,
finite built-in `float` values and are never rounded or rescaled. IDs hash
UTF-8, no-BOM, no-final-LF canonical JSON (`sort_keys=True`, separators
`(',', ':')`, `ensure_ascii=False`, `allow_nan=False`); JSON placed in trace/evidence fields uses the
same byte rule. An unknown key, wrong built-in type, duplicate identity/time, or
out-of-order sequence rejects rather than being guessed or reordered.

The policy is fixed: entry evaluation calendar `2026-01-02` through
`2026-09-17` inclusive, initial cash decimal `100000`, ticker order `SPY,QQQ,SPXW`, and exactly four
books `A_BASE,A_ADVERSE,B_BASE,B_ADVERSE`. There is no selectable arm, cash,
entry calendar, search, fit, EV filter, or benchmark input. Historical plan D,
D1, and H2 dates are not restricted to that entry range: they remain available
for all-event coverage and can terminally be outside, inside, or mixed. Tests may call the
documented book boundary helper directly, but a replay always uses this recipe.

## Input mappings

Sequences are sorted: plans by `(calendar_ordinal,plan_id)`, anchors by
`(plan_id,cluster_ordinal,anchor_id)`, spots by `(ticker,time_local_ns)`, and
quotes by `(decision_id,time_local_ns)`.

A plan has exactly: `calendar_ordinal,plan_id,ticker,trade_date,expiry_date,
call_decision_id,put_decision_id,horizon_end_local_ns,d_1030_local_ns,
d_session_date,d1_session_date,h2_session_date,d_session_kind,d1_session_kind,
h2_session_kind,
d_rth_open_local_ns,d_rth_close_local_ns,d1_rth_open_local_ns,
d1_rth_close_local_ns,h2_rth_open_local_ns,h2_rth_close_local_ns,
expected_rth_minutes,b_plan_pin,b_value_pin,c_anchor_pin,c_geometry_pin,
fixed_risk_contract_pin,geometry_status,geometry_partition`. The three session
dates are distinct admitted dates in chronological order. The six endpoints and
ordered `expected_rth_minutes` is the exact de-duplicated minute-start grid:
every built-in-int member lies in one of the admitted session bounds and none is
after H2. It identifies D/D1/H2, SHORT days, weekends, a
missing session, and a missing minute without inferring a calendar from spots.
`d_1030_local_ns` is not a selectable range: it must equal
`d_rth_open_local_ns + 3_600_000_000_000` (9:30 plus sixty NY-naive minutes).
`geometry_partition` must be the exact module-derived result of
`geometry_status` and supplied anchors, never an unconstrained caller label:
`C_MISSING_SOURCE,C_INVALID_IB,C_INVALID_STATE60,NO_CONFLUENT_ANCHOR`, or
`ELIGIBLE_ANCHOR_SET`.

`geometry_status` is exactly one of `MISSING_SOURCE`, `INVALID_IB`,
`INVALID_STATE60`, or `AVAILABLE_GEOMETRY`. An anchor has exactly
`plan_id,anchor_id,cluster_ordinal,center,band,source_mask,
anchor_available_at_local_ns,valid_geometry,components,c_anchor_pin,
c_geometry_pin`; both anchor pins must equal their plan pins. `components` is a
nonempty ordered list of mappings with exactly the key `kind`, each value exactly
`FIB` or `WALL`; the C component order and multiplicity are preserved. An anchor
is confluent only when its list contains at least one of each kind. A FIB-only or
WALL-only anchor is retained as nonconfluent coverage and may still be a valid
target; no normalization manufactures confluence and `source_mask` does not
infer it. A spot has exactly `ticker,time_local_ns,trade_date,spot,valid_rth`.
When `valid_rth=true`, `spot` is a finite built-in float strictly greater than
zero; when false, `spot` is exactly null. It is an observed missing/invalid
minute, not a price, and no ambiguous `session_break` key exists. A quote has exactly
`decision_id,time_local_ns,ask,bid`; null, negative, zero-ask, and crossed
finite pairs are retained in coverage. A non-finite value is malformed input and
rejects. A pair is price-valid only when both values are non-null and satisfy
`ask > 0` and `0 <= bid <= ask`; zero bid is valid, while null, negative, zero
ask, non-finite, or crossed pairs are invalid for both entry and exit. Null is
never transformed to zero. `config` exactly has `evaluation_start_date` and
`evaluation_end_date`, both required to equal the fixed policy dates; it binds
the entry envelope and cannot alter it. It never rejects a historical plan,
sample, or confirmation solely for being outside that interval: such confirmed
events remain in events and plan coverage with the published outside/in-window
partition, but cannot create an economic intent.

Each plan provides separate byte-exact provenance strings:
`b_plan_pin`, `b_value_pin`, `c_anchor_pin`, `c_geometry_pin`, and
`fixed_risk_contract_pin`. The first four are exactly 64 lowercase hexadecimal
characters; the fixed-risk pin is exactly
`9c387e9bea74ba65777808b5ac5e5fccfdc2437645e7b301c15eab2d33bbeb7b`.
Anchor provenance must agree with the C pins. No output infers, aliases, or
collapses these pins.

The three session bounds validate a fixed policy rather than select it. Every
admitted session opens at 09:30 NY-naive and closes exactly at 13:00 when its
kind is `SHORT`, otherwise at 16:00 when its kind is `FULL`. The normalized
plan consequently also carries `d_session_kind,d1_session_kind,h2_session_kind`,
each exactly `SHORT` or `FULL`. `horizon_end_local_ns` is not an RTH close:
it is exactly 10:35 NY-naive on H2, so it is strictly before either permitted
H2 close. `d_1030_local_ns` is exactly one civil hour after D open. Callers
cannot alter any of these policy times.

`expected_rth_minutes` is the complete ordered, duplicate-free built-in-int
minute-start grid for full D and D1 RTH plus H2 09:30 through the inclusive
10:35 horizon; it contains no H2-after-horizon value. It distinguishes a
missing session from a missing minute and SHORT/regular coverage without
inferring a calendar from samples.
Observations before D 10:30 are validation context only: they cannot arm,
transition, produce coverage evidence, or affect an output count. Anchor
availability further clips the eligible support. Quotes outside D/D1/H2 RTH
reject; quotes after H2 are ignored for that plan; an overnight quote never
fills or exits.

## H2 and output mappings

H2 is the original plan `horizon_end_local_ns`: 10:35:00 NY-naive on its third
session, not RTH close. Samples or quotes after H2 are ignored completely: they
cannot alter an event, trace, coverage, label, or admission. Zone triggers,
two-minute confirmation, and first entry ask require time strictly before H2.
An otherwise first confirmation or first ask exactly at H2 is `TOO_LATE` with no
intent. Exit bids for B may occur at H2. Before a fill, the first stop/target
strictly after confirmation and strictly before H2 immediately yields
`PRE_FILL_TRIGGER_CANCELLED`, even absent a later ask; a simultaneous trigger
defeats an ask. A confirmation may begin no earlier than the admitted
`d_1030_local_ns` and its anchor's availability; there is no caller-selected
entry range. State-specific no-event terminals stay
distinct (`NO_VISIT`, `NO_DEPARTURE`, `CROSS_THROUGH`, `NO_REVISIT`, and only
then `NO_CONFIRMATION`); future samples never rewrite their H2 maturity.

`events` is chronological by `(calendar_ordinal,plan_id,anchor_id)` and has
exactly the 39 normative addendum fields. Its only provenance fields are
`b_plan_pin` and `c_anchor_pin`; `b_value_pin`, `c_geometry_pin`, and the
replay-contract pin are deliberately not event fields.
Each non-null output `*_time`, `*_at`, `*_local_ns`, `label_available_at`, and
ledger `horizon_end` is a signed built-in-int NY-naive ns; nullable normative
timestamp fields are null exactly where the addendum marks them nullable. Every
non-null output date is ASCII ISO date. There are no datetime objects or
unit-less epoch floats. Candidate ordering keys are
`(confirmation_time_local_ns,cluster_ordinal,anchor_id)` within a physical
ticker/day; a duplicate key rejects instead of appending plan ID as an invented
tiebreaker.
The trace is a canonical JSON array of `seq,kind,time_local_ns,spot_f64,side,
state_before,state_after,reason` records. `revisit_id,event_id,intent_id` hash
the addendum’s canonical payloads.

`ledger` is chronological by `(event_session_date,ticker,arm,cost,ledger_id)`.
Every common intent produces A/B × BASE/ADVERSE records with exactly the 47
normative ledger fields; its provenance fields are exactly `b_value_pin`,
`c_geometry_pin`, and `replay_contract_pin`. Decimal values are canonical
strings. `plan_coverage` has exactly the 19 normative fields, one per plan and
no fabricated anchor; its provenance fields are exactly `b_plan_pin` and
`c_geometry_pin`.

`counts` contains exactly these numeric coverage keys from addendum section 7:
`plan_rows,plan_coverage_rows,plans_c_missing_geometry,plans_c_invalid_geometry,
plans_no_confluent_anchor,plans_with_eligible_anchor,plans_no_confirmed_event,
plans_with_only_outside_evaluation_events,plans_with_only_in_evaluation_events,
plans_with_mixed_evaluation_events,eligible_revisit_rows,
ineligible_nonconfluence_rows,revisit_rows,confirmed_rows,no_visit_rows,
no_departure_rows,cross_through_rows,no_revisit_rows,no_confirmation_rows,
no_target_rows,superseded_first_event_rows,pre_fill_trigger_cancelled_rows,
no_entry_quote_rows,too_late_rows,not_evaluable_rows,common_intent_rows,
admitted_intent_rows,wait_rows,event_risk_budget_rows,capital_blocked_rows,
open_position_rows,no_fill_rows,filled_rows,missing_exit_rows,ambiguous_rows,
a_base_ledger_rows,a_adverse_ledger_rows,b_base_ledger_rows,b_adverse_ledger_rows`.
Each is a non-negative built-in int (never bool) derivable from the supplied
plans/anchors and returned in-memory events, ledger, and plan coverage. Intent
units are distinct IDs for `common_intent_rows`, `admitted_intent_rows`,
`wait_rows`, `event_risk_budget_rows`, `capital_blocked_rows`, and
`open_position_rows`; `no_fill_rows`, `filled_rows`, `missing_exit_rows`,
`ambiguous_rows`, and the four arm counts are ledger rows. Each arm count equals
`common_intent_rows`; their sum is four times it; the established admission and
fill equations therefore remain checkable without a global population.

It deliberately excludes only numeric `geometry_state_rows`,
`geometry_level_rows`, and `c_benchmark_rows`, which need global C or benchmark
adaptation. It also excludes all non-numeric coverage fields (`status`,
`data_scope`, `benchmark_policy_status`, and the boolean closure/adoption flags).
It never invents a 1620-plan or 2790-identity total.

## Exact Python projection and identities

The call accepts built-in `list` collections of built-in `dict` records and a
built-in `dict` config. Its return is a built-in dict with exactly the five keys
listed above: `status` is the literal string `SYNTHETIC_MECHANICS_ONLY`, `events`,
`ledger`, and `plan_coverage` are lists of dicts in their specified order, and
`counts` is a dict with the exact 39 keys above. Empty collections remain empty
lists, not null. Supplied plans are nonempty; the other input lists may be empty.
No test helper is part of the public protocol.

The addendum's exact column sets, enums and nullability apply to each output.
Arrow `int16/int32/int64` project to exact built-in int within the corresponding
signed range; bool is never an int. Counts and ordinals are nonnegative. Arrow
bool projects to exact bool, utf8 to exact str, date32 to a valid ASCII Gregorian
ISO date string, float64 to an exact finite built-in float, and timestamp[ns] to
signed int64 NY-naive nanoseconds. Only columns explicitly nullable may be None.
Canonical Decimal strings and JSON strings remain strings, never numeric floats
or nested structures substituted for those fields.

Input `calendar_ordinal` is nonnegative int32; `cluster_ordinal` and `source_mask`
are nonnegative int16. Input IDs are nonempty strings, tickers use the three
literal values, and all date and ns fields follow the projection above. Centers
and bands are positive finite floats. `valid_geometry` is exact bool and must be
true for every supplied anchor: C supplies valid levels, never fabricated levels
for invalid geometry. Component kinds and their list/dict shapes are as above.
All pin strings obey their explicit SHA rules. The output ledger
`replay_contract_pin` equals the input `fixed_risk_contract_pin`.

`plan_id` is unique and is in one-to-one correspondence with `(ticker,trade_date)`;
`trade_date == d_session_date`. Each date agrees with its civil ns endpoints.
CALL and PUT decision IDs differ and each belongs to exactly one plan/right.
Anchors have unique `(plan_id,anchor_id)` and `(plan_id,cluster_ordinal)` keys,
reference an existing plan, and match its C pins. Their availability is the
ENTRY_FROZEN D10:30 instant. Spots have unique `(ticker,time_local_ns)` keys and
their `trade_date` matches that ns civil date. Quotes have unique
`(decision_id,time_local_ns)` keys and their decision ID references a plan/right.
Conflicting bounds or kinds for the same physical ticker/session are rejected.
No implicit reordering, deduplication, ID substitution or nearest-time join occurs.

## Geometry population and causal spot coverage

MISSING_SOURCE, INVALID_IB and INVALID_STATE60 plans have no supplied anchors
and map, respectively, to C_MISSING_SOURCE, C_INVALID_IB and C_INVALID_STATE60.
An AVAILABLE_GEOMETRY plan maps to ELIGIBLE_ANCHOR_SET if at least one supplied
anchor contains both FIB and WALL, otherwise to NO_CONFLUENT_ANCHOR. Empty
AVAILABLE_GEOMETRY anchor sets are retained in the latter partition.
There is exactly one event per valid confluent anchor and none per nonconfluent
anchor. Every supplied anchor remains in `c_anchor_count`; nonconfluent anchors
remain available to the target rule. Missing/invalid geometry never fabricates
a revisit record. Every plan has exactly one plan-coverage record.

For an event, the eligible spot grid is its plan's expected RTH minute grid
clipped to max(D10:30,anchor availability) through H inclusive. Only the matching
ticker, admitted session identity and exact grid minute may move its state.
Other spot observations cannot transition, confirm, trigger, or alter coverage.
Absent grid rows and rows with valid_rth=false both mean missing valid evidence;
neither supplies a price. Session identity and a literal 60,000,000,000 ns
difference, as well as valid samples on both minutes, are required for a
two-minute confirmation. Grid adjacency across an overnight is insufficient.
At H the ordinary observed FSM transition is retained for coverage; a complete
two-minute confirmation there is TOO_LATE. One outside sample at H cannot confirm.
Economic asks and post-fill zone triggers remain strictly before H.

Coverage is an as-of diagnostic, not a feature obtained from later observations:
`spot_coverage_status` considers eligible grid minutes only through that event's
`label_available_at`, capped at H. This operational clarification preserves the
frozen label maturity without consulting subsequent missing/valid observations.
For that nonempty prefix, MISSING_SESSION takes precedence when any represented
admitted session has zero valid grid samples; otherwise MISSING_MINUTE applies
if any required grid minute lacks valid evidence, and COMPLETE otherwise.
NOT_EVALUABLE is reserved for an empty eligible prefix, not a substitute for a
missing session. Invalid or missing observations never remove the event.

Quote shape/type/identity validation is global. For each known decision's plan,
quotes after H have no semantic effect, including quotes outside that plan's
three sessions. Within its support through H, an out-of-RTH quote rejects;
no overnight quote may fill or exit. This refines the earlier shorthand
"quotes outside D/D1/H2 RTH reject": it never makes a post-H quote reopen a
completed event. Price-invalid observations within support are retained as
observations but cannot price an entry or exit.

The cardinal counts use the same populations: `eligible_revisit_rows` equals
the number of valid confluent supplied anchors and equals `revisit_rows`;
`ineligible_nonconfluence_rows` is the number of other supplied valid anchors.
The four geometry plan counters count their partitions, combining INVALID_IB
and INVALID_STATE60 in `plans_c_invalid_geometry`. The four event-window plan
counters use all confirmations and their actual session dates, regardless of
supersession: none, only outside, only inside, or mixed. They sum to plan_rows.
All terminal event counters count the matching terminal_reason. All remaining
intent/ledger counters retain the addendum's exact units and equations.

## Cross-through, rearm, and scalar event fields

The trace retains every attempted sequence. The single row's scalar fields
describe its current/final attempt, or its terminal confirmed attempt. A
CROSS_THROUGH invalidates the attempt and writes its observed trace transition
to INIT; that crossing sample cannot also arm. Until a later eligible sample
actually rearms, preserve the invalidated attempt's observed `armed_side`,
`visit_time`, `departure_time`, `departure_side`, and `revisit_time` (each remains
null if that stage was never reached). Confirmation and all subsequent fields
remain null; final event_status and terminal_reason are CROSS_THROUGH.

At a later rearm, set the new armed_side and ARMED event status. Reset visit,
departure (including departure_side), revisit, confirmation, event/session ID,
decision/right, stop, target, entry and intent fields to null. The old trace is
not reset. The new attempt then populates its own fields in causal order. An
intermediate-band sample does not rearm; GAP_CROSSING preserves the prior state
and never rearms. On H without confirmation, a pending unrearmed cross remains
CROSS_THROUGH; otherwise INIT/ARMED means NO_VISIT, VISITED means NO_DEPARTURE,
DEPARTED means NO_REVISIT, and REVISITED/CONFIRM_ONE means NO_CONFIRMATION.
Those absence labels mature at H. A confirmed pair is terminal and cannot rearm.

These projections are pre-outcome clarifications of the frozen state machine
and its causal metadata. They add no trade rule, threshold, arm or fitted choice.

An independent auditor reconstructs from this public interface, the frozen
contracts and its own implementation. Its author must not read or import the
producer implementation/tests, and must not share its transition or accounting
helpers. Shared public record schemas and literal contracts are permitted.
