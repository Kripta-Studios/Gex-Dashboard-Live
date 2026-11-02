# D documentary candidate02 review

Fresh reviewer: /root/d_document_review02, pinned Sol/high, behaviorally read-only.
Verdict: FIX-FIRST, documentary scope only. No data, fixture, implementation or runtime approval.
Subject: 36,597 bytes, SHA-256 8eaa816be7de30669e87bac2b8639a13a70d31e6e99be315a96d9bf54042fdd5.
Exact candidate preserved beside this note as d_addendum_candidate02.md.

1. overlap_rank_json needs nullable event date/time for unconfirmed NOT_COMPETING rows.
2. Define the complete ledger matrix for WAIT, risk-budget NO_FILL, observed fill and missing exit. Missing exit requires both bid and bid time null. Specify no-fill trigger/time/accounting/flags/states and precedence OPEN_POSITION versus CAPITAL_BLOCKED.
3. Use one chronological queue, timestamp first; EXIT before ENTRY only at equal timestamps. Never process later exits before earlier entries.
4. In-window coverage must count all confirmations, including superseded ones, matching outside-window counts and the exhaustive four-way plan partition.
5. Define exact units/equations for distinct-intent and ledger-row coverage counters; reconcile four ledger rows per intent.

Reviewer verified all six benchmark pins and local authorities without decoding ledgers. D-only continuous 100000 USD book, no July reset or inherited position, EXIT-month 8/8, three arms and pending B/C limits were coherent. No architecture change requested.
Host permission profile danger-full-access/disabled; behavioral read-only review, no Python, tests, API, process or Git mutations.
