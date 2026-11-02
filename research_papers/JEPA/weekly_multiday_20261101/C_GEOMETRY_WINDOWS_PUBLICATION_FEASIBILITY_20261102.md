# C geometry: Windows publication feasibility

Status: DOCUMENTARY_CANDIDATE_NON_EXECUTABLE_PENDING_B_CLOSURE.
This note resolves a proposed implementation choice, not C execution authority.
C contract c2857254 and operational draft88f76551 remain unchanged. No Windows
primitive was executed, no C code/fixture was created and no arrays were opened.
Root and /root/value_paths_builder investigated the documented API behavior.

## Proposed mechanism and bounded guarantee

Use one `MoveFileExW(staging, final, MOVEFILE_WRITE_THROUGH)` namespace operation.
Microsoft documents same-drive directory moves and demonstrates this flag with
a destination that does not yet exist. Its flag documentation describes a
write-through move and explicitly guarantees flushing for copy/delete moves;
that latter case must not be confused with a general crash-atomic transaction.
Only flag0x8 is proposed; replacement, cross-volume copy and reboot scheduling
are excluded. Sources: [MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw)
and [Moving Directories](https://learn.microsoft.com/en-us/windows/win32/fileio/moving-directories).

The implementation must check a nonzero return for success. Read GetLastError
only on zero return; a stale nonzero last-error after success is not a failure.
No fallback move/copy or second attempt is permitted.

Before the move, flush each regular output through a writable file handle and
check `FlushFileBuffers`, then close it and verify its bytes/hash. Flush the
external journal after every record, including PUBLISH_ROOT/START and COMPLETE.
Microsoft requires GENERIC_WRITE for this file flush. Do not substitute a
directory handle or an administrative whole-volume flush. Source:
[FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers).

This proposal claims checked file flushes and one checked namespace operation.
It does not establish a transaction that survives every power loss, ordering
across volumes or control over physical device caches. Hardware caching is
outside the guarantee documented for application file buffering. Source:
[File Buffering](https://learn.microsoft.com/en-us/windows/win32/fileio/file-buffering).

Consequently the final C contract must state this bounded guarantee explicitly.
The old draft phrase single atomic rename cannot be promoted into a stronger
power-loss guarantee on the strength of these documents or a passing fixture.
Research admissibility depends on complete retained evidence and independent
rehashing, not directory presence alone.

## Required path and publication protocol

The designated C runtime root, staging, final and observer must resolve to
absolute local paths within the explicitly admitted runtime directory. Staging
and final are siblings. Their existing parents and the observer must resolve
to the same actual volume identifier; the future binding will use the documented
GetVolumePathNameW/GetVolumeNameForVolumeMountPointW pair and reject resolution
errors, remote shares, volume mismatch and all reparse/alias paths. The final
must be absent at startup and again immediately before move; publication must
not replace an existing file or directory. These are proposed safeguards, not
claims that source data were checked by this documentary review.

Before mutation, reject unsupported platform/API availability or an unresolved
binding. Runtime API failures remain possible after preflight and are fatal;
preflight does not prove future disk success. All input admission, scientific
reconstruction, output checks, hashes and resource gates finish before the
commit operation. Capture staging physical identity before publication.

After a durable PUBLISH_ROOT/START, perform the single move. A zero return
records failure if the journal remains writable and returns nonzero; no retry,
deletion or assumption that nothing happened. Inspect actual paths only to
describe preserved failure evidence. A nonzero return is followed only by
publication closure: verify final path/identity/member set and expected hashes,
then write and flush PUBLISH_ROOT/COMPLETE. These post-move checks may fail and
must never be represented as scientific recomputation or a successful commit.
The final operative contract must explicitly replace the draft's overly broad
all-fallible-checks-before-commit wording with this split.

The retained launcher exit receipt is a separate observer artifact and must
also be flushed. Any failure/interruption after move and before COMPLETE or
retained exit0 leaves the final, if present, UNADOPTABLE_INCOMPLETE_PUBLICATION.
Do not delete, reuse, resume or infer success. Admission requires consistent
final files, COMPLETE journal, retained exit0, then independent C audit and
review. Crash/power-loss behavior is not inferred from process-interruption
tests; unverified or contradictory artifacts remain inadmissible.

## Future verification obligations, not permission to run now

After B full PASS and the final C contract/review/publication, test the actual
Windows adapter on fresh synthetic paths in the designated volume, plus failure
injection for unavailable APIs, wrong volume, destination already present,
file/journal flush failure, move failure and interruption after move. Preserve
all failures. Assert no overwrite, no fallback and no adoption without terminal
evidence. These checks cannot certify hardware power-loss durability.

No model, threshold, geometry formula, population or economic rule changes.
C implementation and fixtures remain prohibited until B closure and the final
operative contract. Goal active; selection=null, promotion_approved=false.
