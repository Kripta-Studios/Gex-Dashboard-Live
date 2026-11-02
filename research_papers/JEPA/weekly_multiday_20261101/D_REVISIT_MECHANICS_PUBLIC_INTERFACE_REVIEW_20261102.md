# D public record interface: documentary review

Status: CLEAR_DOCUMENTARY_D_MECHANICS_RECORD_INTERFACE.
Subject: D_REVISIT_MECHANICS_RECORD_INTERFACE_20261102.md, 19358 bytes,
SHA-256 662147864f8cf446b39fc07e17f8ef7650ffd920dea75bc75d6411b791ddcc1d.

Fresh independent reviewer `/root/d_mechanics_public_interface_review` returned
SHIP for this exact final pin after reading the entire public interface against
the frozen D draft, operational addendum, parallel preparation amendment and
causal-terminal clarification. It did not inspect producer implementation or
tests, execute code, read data, or interact with B06.

The interface fixes the normalized Python records, exact types/nullability and
identity relations, historical-plan coverage with a fixed economic entry window,
FIB/WALL eligibility and retained nonconfluent targets, plan-local RTH/H2 support,
exact 39/47/19 output projections and 39 derivable numeric counts. It preserves
separate provenance, canonical IDs/JSON and the independent-author boundary.

Two explicit pre-outcome metadata clarifications were reviewed: event spot
coverage uses only its causal label-time prefix; scalar fields represent the
current/final attempted sequence while trace retains all cross-through and
rearm attempts. Ordinary FSM observations at H remain coverage, with a completed
two-minute confirmation at H TOO_LATE for entry. No threshold, horizon, arm,
cost, fit, EV filter, selected month/ticker or economic result changed.

Rejected documentary candidates remain preserved:

- `REANUDACION_20261102/d_interface_static_candidate01/`, 11385 bytes,
  f83a50bc3a1ee824b5655e5e05a829ad2f03e03eb50955af880df1275b3f7d25:
  FIX_FIRST for incomplete return/type/FK/geometry/coverage/count projections,
  independent-author restriction and scalar rearm semantics.
- `REANUDACION_20261102/d_interface_static_candidate02/`, 19150 bytes,
  53774a60aeade8a5d438394aba3b5047ede1624b1c60c34a2710a86bb53f831b:
  FIX_FIRST for unjustified positive-center restriction, contradictory strict-H
  confirmation sentence, omitted ledger_id in canonical-ID list and incomplete
  explicit bool/grid-list projection. The final four corrections were rechecked.

The separate first producer candidate failed its own static review; see
D_REVISIT_MECHANICS_STATIC_FAILURE01_20261102.md and its immutable code/test
copies. No candidate has run a synthetic suite or a real replay. The complete
producer is being corrected by `/root/d_mechanics_producer_complete`; the old
author has relinquished its files. `/root/d_independent_mechanics_auditor` has
read only allowed public contracts and awaits this interface's exact publication
before authoring its separate implementation. It must never read/import producer
code/tests or share their transition/accounting helpers.

This documentary acceptance enables that parallel synthetic implementation after
publication. It does not close either implementation, authorize a formal suite,
admit B/C data or authorize real D. Those gates remain unchanged. Review was
behaviorally read-only under the host's broad filesystem permissions.

Goal active; selected_policy=null; promotion_approved=false; no new PnL.
