# D trace: interruption of a confirmation streak

Status: PREOUTCOME_CANDIDATE_REQUIRES_REVIEW_AND_PUBLICATION.
This note is read with interface 19358B/662147864f8cf446b39fc07e17f8ef7650ffd920dea75bc75d6411b791ddcc1d,
the frozen D draft/addendum and causal-terminal clarification. No D suite or
real replay has run. Original authorities remain immutable.

The existing two-minute confirmation rule requires physically consecutive valid
RTH observations outside 2b on the stored departure side. A valid observation
inside the band or in the intermediate region breaks a CONFIRM_ONE streak.
Calling this a missing minute would falsely describe an observed price; calling
it the first REVISIT would also be wrong. The existing trace vocabulary lacks a
faithful record for this already required transition.

After independent review and publication, extend only the trace enums by:

- kind `CONFIRMATION_RESET`;
- reason `NON_CONFIRMING_OBSERVATION`.

For a valid inner/intermediate observation after CONFIRM_ONE, append exactly one
such record at its observed timestamp, with its actual float.hex() spot, stored
departure side, state_before CONFIRM_ONE_SIDE and state_after REVISITED_SIDE.
Clear the confirmation streak; keep the attempt's original revisit timestamp.
The same observation cannot start another confirmation minute.

An outer observation on the opposite side after REVISIT or CONFIRM_ONE is
CROSS_THROUGH, as required explicitly by draft section4.7. That specific rule
takes precedence over the general no-interior-sample gap description. A
GAP_CROSSING may preserve INIT, ARMED or DEPARTED; it never preserves an opposite
observation as part of a confirmation streak. No new threshold or entry/exit
rule is introduced, and a crossing sample still cannot rearm.

Missing expected grid evidence while CONFIRM_ONE appends MISSING_MINUTE with
reason MISSING_RTH_MINUTE, null spot and state_after REVISITED_SIDE, then clears
the streak. At an admitted session boundary, an active CONFIRM_ONE is reset
before the new session's first grid sample; append SESSION_BREAK at that first
grid time, null spot, reason SESSION_BOUNDARY, and state_after REVISITED_SIDE.
The current sample may then start the first new confirmation minute if valid
and on the stored side. No extra missing transition is emitted if the boundary
already reset the streak. Session boundaries do not invent movement or rearm.

Terminal annotations are appended after the observed confirmation trace only
for enum kinds NO_TARGET, SUPERSEDED_FIRST_EVENT, PRE_FILL_TRIGGER_CANCELLED,
NO_ENTRY_QUOTE and TOO_LATE. They use state_before CONFIRMED and state_after
TERMINAL, stored departure side and the terminal's causal label time. Their
reasons are respectively TARGET_ABSENT, DAY_PRIORITY, TRIGGER_PRE_FILL,
ASK_ABSENT and TERMINAL_CLOCK. Their spot is null except for pre-fill
cancellation, which records the actual triggering observed spot. This fixes
the JSON projection only; target/trigger decisions still reconstruct from the
admitted observed samples. OUTSIDE_EVALUATION_WINDOW and the later economic
WAIT/NO_FILL/FILLED states add no invented trace kind; their event/ledger fields
carry the frozen reasons and label times. The trace is serialized after these
annotations, with consecutive zero-based seq values.

No market values, fitting, parameter selection or economic results informed this
clarification. It is shared public protocol, not shared producer/auditor code.
Both implementations require reviewed fixtures for interrupted streaks, opposite
crossing, session boundaries and terminal trace evidence before acceptance.
All real B/C/D admission and resource gates remain unchanged.
