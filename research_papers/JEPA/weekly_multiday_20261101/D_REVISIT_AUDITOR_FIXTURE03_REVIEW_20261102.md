# D auditor fixture03: strict validation before record ordering

Source status: CLEAR_STATIC_PRE_SUITE_D_REVISIT_AUDITOR.
Harness status: CLEAR_D_REVISIT_AUDITOR_FIXTURE_HARNESS.

Fixture02 is FAILED/CLOSED, not partially adopted. From published6d2fdf23,
compile and Ruff exited0; pytest reported4 failed,19 passed,163 subtests passed
in5.03 seconds. Root retained session3001 exit1/chunk437171. Pytest PID70520,
creation1793659187.4956417, exit1793659197.3643808, effective/child exit1,
CPU0, metadata_error=null, changed_pins=[], retry=false. No PASS receipt exists.

Four malformed ledger sort keys (ticker/event_session_date/arm/cost) raised
TypeError before their type validators could raise AuditError. The independent
author moved all three existing event/ledger/coverage ordering comparisons
after the strict row validators and FK-map checks. No check was removed and
no reconstruction, accounting or valid-record ordering rule changed.
Source reviewer `/root/d_auditor_mechanics_static_review02` returned SHIP after
the exact relocation and confirmed each sort key is typed before comparison.
The existing complete regression suite remains unchanged.

Current pins:

- auditor68119 bytes, c6c77b1e12b166796c06335621b606b03006617e3dc0a374a2bc2d489ec554d7;
- tests36144 bytes, bde8e0427bf59d365edeb466daf46cfdb85bb67b02bf0c4aac9a662d944da64b;
- harness0315505 bytes, 1e7f283c5011bf5be84acb8b62dd841043e55da364966f712cb3347183144544.

Independent closure reviewer `/root/d_accounting_harness_review` verified the
failed02 retained children/gates, all11 original pins/snapshots against published
6d2fdf23, and22 archive payloads/275963 bytes. Archive02 manifest
e0c98f31a0c7f1af7c171f7771d34cde371e8faa9ba89847a376b99adea446fb and receipt
69f94ead2784a602333a8980ff586cc42ec87dc2cf0bd498a61ada88f080cba4 are exact.
All13 repository projections in REANUDACION_20261102/d_auditor_fixtures02 match
retained originals. Receipt declares partial_adoption=false and no market PnL.

The harness reviewer also returned SHIP for03: the exact02->03 delta is two
root literals and the auditor hash. Current source/tests match full pins and
both03 roots are absent;01/02 and their archives remain intact. All fixed-branch
remote/Git-byte admission, combined dual-review markers/full current pins and
self-hash, plain-path checks, CPU0/TEN1/CUDA=-1, official2GB gates, hidden retained
children, source snapshots, closing-pin checks and no retries are unchanged.

After byte-exact publication, run once under
weekly_zone_revisit_auditor_fixtures_03 and
weekly_zone_revisit_auditor_fixtures_observer_03. Compile/Ruff only auditor,
its tests and harness; pytest only the independent auditor test file. This
material validation correction requires a new complete result; failed02
subresults do not establish acceptance. No closed producer/accounting suite or
integration test is repeated. Reviews used no import, compile, lint, tests,
data reads or runtime execution. No real B/C/D data or market PnL is admitted.
Goal active; selected_policy=null; promotion_approved=false.
