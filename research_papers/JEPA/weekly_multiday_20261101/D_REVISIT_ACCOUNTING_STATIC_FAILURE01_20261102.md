# D accounting helper: first static candidate rejected before suite

Status: FIX_FIRST_STATIC_ONLY. No execution occurred.

Independent reviewer `/root/d_accounting_static_review01` reviewed the helper
and tests against public D accounting/clock/interface authorities. It read no
FSM producer or independently authored auditor. Preserved copies:

- REANUDACION_20261102/d_accounting_static_candidate01/weekly_zone_revisit_accounting.py,
  18798 bytes, 913aaff1b1635c2e67390b9c8ca3de21a6d4f2ce5b87ab391101cd4e40a1217f;
- the same directory's test_weekly_zone_revisit_accounting.py,
  6046 bytes, 6493c6bcd8694444aa0acd81cc2a1764b2e60949ee437e854600163593d2e44e.

The implementation was statically coherent for four continuous books, common
admission, conservative B lockout, chronological exits, strict A/B quote clocks,
principal reserve, fees and 47-field ledgers. It is not accepted yet: the first
test incorrectly expects cash104483.8 for both costs; adverse should104389.8.
Seven tests also omit material replay-level capital/precedence/tie, Decimal,
full balance/schema and boundary cases. Root additionally requires the emitted
ledger's ticker-string field ordering; execution queue ticker priority remains
SPY/QQQ/SPXW. The author is correcting this bounded output order and fixtures.

This new helper isolates producer accounting only. The independent auditor must
not read or import it or its tests. No source values, runtime, PnL or formal
fixture result exists. The failed candidate copies remain immutable.
