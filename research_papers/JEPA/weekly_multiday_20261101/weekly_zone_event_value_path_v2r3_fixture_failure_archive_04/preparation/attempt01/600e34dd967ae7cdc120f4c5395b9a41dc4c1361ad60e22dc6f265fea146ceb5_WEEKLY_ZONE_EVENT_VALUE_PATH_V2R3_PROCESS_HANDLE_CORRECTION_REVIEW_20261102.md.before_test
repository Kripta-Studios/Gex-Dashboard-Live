# R3 fixture03: retained process-handle observation correction

Date: 2026-11-02. Status: `CLEAR_STATIC_DELTA_PENDING_FINAL_REBIND`.

Fixture02 failed because its short-lived compile child had exited before a psutil lookup by PID. The retained wait returned0, but creation/affinity metadata were unavailable, so the harness correctly rejected the stage. Failure02 and its original harness remain immutable.

The new fixture03 harness changes the observer to use the existing retained Popen process handle. `GetProcessTimes` supplies creation/exit/kernel/user times without reopening by PID; `GetProcessAffinityMask` queries that same handle. The Popen object and handle remain alive through wait and post-wait verification. FILETIME conversion uses 100-nanosecond ticks and the Windows-to-Unix epoch offset. No process is rediscovered by name or PID, no extra worker is introduced and no metadata error is ignored.

Reviewer `/root/daily_report_package` examined the Win32 API bindings and corrected temporal checks. Root read the final functions. Creation time must be present and finite; kernel/user CPU times must be finite and nonnegative; any reported exit must be finite and no earlier than creation. After retained wait, exit time is mandatory and creation must match the original snapshot. API failures, identity drift or affinity other than CPU0 remain fatal and are preserved with the actual child exit.

Reviewed code candidate before final review-pin substitution: 30,334 bytes, SHA-256 `73624cd25a81fb6ad08f592b3a3f2c92a46b4f99de4aa0155d42163e07e3fa9f`. Only the self-independent review pin is pending at that checkpoint; a final mechanical review must verify the completed harness bytes before publication.

The first compile command in the fresh formal suite will directly exercise the corrected short-lived-child path, followed by Ruff and the existing tests only if metadata and exit are accepted. This static review claims no executed Win32 probe or test. All scientific code, test expectations, 2 GB gates, CPU/thread settings, list-argument commands and dependency checks remain unchanged. A fresh fixture03 root is required; no retry loop or failed-root reuse is permitted.

Root authorizes that single fresh formal fixture attempt after final rebind/review, byte-exact publication and contemporary gates. No real B06 run is authorized. Official API references are recorded in the harness comments; these support process-handle semantics, not any trading result.
