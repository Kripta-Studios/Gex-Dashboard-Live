# C geometry producer launcher: plan and retained-wrapper contract

Status: `NON_EXECUTABLE_PENDING_FINAL_B_CLOSURE_AND_C_BINDING_REVIEW`.

This contract defines a future, single C producer wrapper. It creates no plan,
binding, runtime root, fixture result, geometry, event, label, selection, EV,
PnL, or promotion. It does not change the closed C04 69-pass suite or the
closed R3 136-pass suite. B06 is an independent live process and this contract
does not inspect, signal, restart, or otherwise interact with it.

## Invocation and immutable runtime roots

The one wrapper command is:

```powershell
& 'C:/Program Files/Python314/python.exe' -X utf8 -u `
  'research_papers/JEPA/weekly_multiday_20261101/launch_weekly_zone_geometry_1030_producer_20261102.py' `
  --plan-json '<published-plan.json>' --plan-sha256 '<64-lowercase-hex>'
```

The plan is a separately hashed and Git-published repository member. Its own
identity is the CLI SHA-256 plus Git-byte check; it does not self-pin, avoiding
an impossible hash cycle. The plan pins this launcher. The subsequent C runtime
binding review may pin both the binding and launcher; the plan pins that review.

All three roots must be absent before the initial gate:

```
D:/GexResearchArtifacts/weekly_multiday_20261101/weekly_zone_geometry_1030_01
D:/GexResearchArtifacts/weekly_multiday_20261101/weekly_zone_geometry_1030_observer_01
D:/GexResearchArtifacts/weekly_multiday_20261101/weekly_zone_geometry_1030_launcher_observer_01
```

The child receives exactly `--binding-json`, `--binding-sha256`, `--output-dir`,
`--observer-dir`, and `--journal` as defined by the published C binding. Its
journal is `weekly_zone_geometry_1030_observer_01/journal.jsonl`; its stdout
and stderr remain in the separate launcher observer root.

## Exact plan schema

The compact JSON object has exactly these top-level keys:

```
schema, status, branch, data_scope, repository_pins, b_final,
runtime_binding, runtime_roots
```

Its exact literals are
`schema="c_geometry_1030_producer_launch_plan_v1"`,
`status="PASS_FINAL_C_GEOMETRY_PRODUCER_LAUNCH_PLAN"`,
`branch="research/multiscale-v1r1-net-usd"`, and
`data_scope="SEEN_DEVELOPMENT"`. No string, key, nested value, or path may
contain `PENDING` (case-insensitive).

`runtime_roots` is exactly:

```json
{
  "output_dir":"D:\\GexResearchArtifacts\\weekly_multiday_20261101\\weekly_zone_geometry_1030_01",
  "observer_dir":"D:\\GexResearchArtifacts\\weekly_multiday_20261101\\weekly_zone_geometry_1030_observer_01",
  "launcher_observer_dir":"D:\\GexResearchArtifacts\\weekly_multiday_20261101\\weekly_zone_geometry_1030_launcher_observer_01",
  "journal":"D:\\GexResearchArtifacts\\weekly_multiday_20261101\\weekly_zone_geometry_1030_observer_01\\journal.jsonl"
}
```

Every normal file pin is exactly `{path,bytes,sha256}`, with an absolute Windows
path, non-negative integer bytes, and lowercase 64-hex SHA-256. Pins must be
plain regular files with no symlink, reparse ancestor, hardlink, or physical
alias. Repeated roles for the same nominal file are allowed only with the exact
same pin. The only B bundle duplicate is `authority_inputs.unified_calendar`
equal to `calendar.raw_file_pin`; it is one physical file, not an alias.

`repository_pins` has exactly these roles:

```
launcher, runtime_binding, runtime_binding_review, launcher_contract,
launcher_tests, wrapper_fixture_receipt, wrapper_fixture_exit, c_final_review,
c_producer, c_producer_tests, c_auditor, c_auditor_tests,
c_admission_contract, c_operational_draft, c_binding_feasibility,
c_windows_feasibility, c_parallel_amendment, c_parallel_review, level_engine,
session_level_engine, session_clock, session_cache, build_cache,
resource_helper, b_final_bundle, b_final_review
```

This is the full published provenance surface: known C implementation, tests,
contracts, pure engines, official helper, final C implementation review, formal
wrapper fixture PASS receipt/exit, B final bundle/review, future binding/review,
and the wrapper itself. The launcher verifies branch, local HEAD equals remote
HEAD, each repository member’s pin, and exact Git bytes before any runtime root.

`c_producer` is immutable: exactly `build_weekly_zone_geometry_1030.py`,
73,030 bytes, SHA-256
`ebe7c8984e2e7eb3806193e7c891dbbb0d0449b19e13e0657d0b68cdbe0d1b01`.
`c_final_review` is also frozen: exactly
`C_GEOMETRY_FINAL_IMPLEMENTATION_REVIEW_20261102.md`, 2,160 bytes, SHA-256
`3e306e8bebc95686fd2e6dd4fa3496d834fdf9b07882f4b15922fedc7f679fc7`, and
must contain `CLEAR_FINAL_IMPLEMENTATION_LIMITED_C_GEOMETRY_PREPARATION`.
The later binding review must contain its binding SHA-256 plus the exact
launcher, launcher-tests, and launcher-contract SHA-256 values. The external
fixture review instead must contain `CLEAR_STATIC_PRE_SUITE_C_PRODUCER_WRAPPER`
plus those same three source hashes; separating the reviews avoids a cycle.

The helper role is additionally frozen outside the plan: it must be exactly
`research_papers/JEPA/level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py`,
31,463 bytes, SHA-256
`3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046`.
The wrapper configures CPU0/TEN1/CUDA=-1 before reading the plan or any
provenance, verifies that exact helper before executing it, and rejects a
plan-supplied alternate helper.

`b_final` is exactly `{bundle,review}` and duplicates the corresponding
repository pins. `runtime_binding` is exactly `{binding,review}` and duplicates
the corresponding repository pins. The B review must contain literal
`CLEAR_FINAL_B_CLOSURE` and the B bundle SHA-256. The C binding review must
contain literal `CLEAR_FINAL_C_RUNTIME_BINDING` and the binding SHA-256. These
are narrow review attestations, not a substitute for the independent C auditor.

The formal fixture receipt is a compact JSON object with exactly
`schema,status,launcher,tests,compile_exit_code,ruff_exit_code,pytest_exit_code,pytest_exit`.
Its literals are `schema="c_geometry_1030_producer_launcher_fixture_closure_v1"`
and `status="PASS_CLOSED"`; launcher/tests pins must equal the plan roles, all
three exit codes must be integer zero, and `pytest_exit` must equal the pinned
`wrapper_fixture_exit`. That retained JSON exit has exactly
`exit_code,pid,creation_epoch,metadata_error,changed_pins,retry`; it requires
exit 0, positive PID, finite numeric creation epoch, `metadata_error=null`,
`changed_pins=[]`, and `retry=false`. A malformed or non-PASS receipt rejects
before a runtime root or child process.

## B and C closure admission

Before any gate or root, the wrapper parses the final B bundle. It requires the
real v1 B bundle schema/status, all 47 pin occurrences/46 files, exact flag set
(only raw option values, Parquet footers, and spot cache arrays true;
`selected_policy=null`), producer and auditor effective exit 0 and child exit
0, empty changed pins, null metadata error, no retry, and exact process
pid/creation identities. It validates metadata and hashes of declared bundle
members only: producer manifest `COMPLETE_OUTCOME_FREE_VALUE_PATHS`, exact
projected output pins, authority/flag/calendar envelope crosslinks; audit and
audit-manifest `PASS` schemas, their producer/audit/authority/flag/calendar
crosslinks; and no-error paired producer/auditor journal units with terminal
`CLOSING_REHASH` / `WRITE_AUDIT_OUTPUT` completion. It never reopens options raw
files, cache NPZ, market data, or a failed/partial B root.

The wrapper then parses the C binding rather than trusting a status string. It
requires the exact C runtime binding schema/status, no pending value, plan-equal
B bundle/review and resource-helper/producer pins, exact runtime roots, and the
reviewed non-replacing `MoveFileExW` policy. The producer performs its own full
binding validation again in the child.

No current plan is supplied by this change. Actual B bundle/review/binding paths,
bytes, and hashes remain unresolved until B06 completes, is independently
audited, bundled, reviewed, and published.

## Process, gate, and mirror policy

The wrapper configures CPU affinity mask 1 and the ten thread variables to `1`,
with `CUDA_VISIBLE_DEVICES=-1` before plan/provenance I/O. It obtains the frozen
official helper and requires RAM available, free commit, and free D: disk each at least
2,000,000,000 bytes before creating *any* root, and again immediately before
the one `Popen`. There is no wait, threshold relaxation, retry, cleanup, output
overwrite, or per-unit C resource amendment.

Only after the first gate does it create the launcher observer. It records its
exact child command and captures the child PID, retained-handle creation time,
and affinity at launch. Metadata errors never skip the one retained-handle
`wait`. The child is launched with `CREATE_NO_WINDOW`, stdin detached, and
wrapper-owned hidden stdout/stderr files.

After wait, the wrapper rehashes every authoritative plan and final-B closure
pin. Any changed pin, metadata error, invalid retained handle, child nonzero,
or mirror error makes the wrapper effective exit nonzero. It does not adopt a
partial child root.

The C producer alone creates its observer. If that observer exists after launch
and is plain/non-reparse, the wrapper exclusively writes parent-observed
`process.json` and final `exit.json` mirrors there; it never creates the child
observer after failed launch and never overwrites a child file. The final C
existing C auditor validates the mirrored child closure. Separately, the final
root pre-C-audit admission must require wrapper `exit.json` exit 0 plus the
byte-exact child-observer mirrors, and pin that evidence in its closure review.
The existing auditor is not modified by this wrapper work. Therefore a mirror
success cannot make an otherwise failed wrapper appear successful.

## Focused synthetic wrapper fixtures

The separate fixture file covers only wrapper behavior with temporary files and
a harmless short Python child: pending/invalid plan before mutation, published
path/hash and physical-alias rejection, initial gate before roots, exact child
command, fast retained-handle/nonzero/metadata closure, and mirror conflict plus
effective-exit behavior. It must not read real B/C/raw data, import producer or
auditor modules, run geometry, or repeat C04/R3 suites. A root review and Git
publication are required before that fixture is formally run.
