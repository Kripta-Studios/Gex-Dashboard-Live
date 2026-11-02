# D accounting helper: final static review before its first suite

Status: CLEAR_STATIC_PRE_SUITE_D_REVISIT_ACCOUNTING.

Fresh read-only reviewer `/root/d_accounting_static_review02` returned SHIP:

- weekly_zone_revisit_accounting.py, 18783 bytes,
  9bcc4f834745806289550d2119f7d35ad0281c2fe151ac36c87be24aa72594fb;
- test_weekly_zone_revisit_accounting.py, 11857 bytes,
  4bc5d0d282cb2ed11b31a5c3f325962cb75de7698bad7afbc42cd66df7348c07.

The reviewer checked the full helper/tests against draft4ea0, addendumc567,
causal-terminalde8f, preparationd5a6, interface662147 and preserved failure
review85b9ac35. Four continuous books share quantity, entry and admission with
qty0/open-position/capital precedence; B lockout persists until H. The queue
uses timestamp-first EXIT before equal-time ENTRY and SPY/QQQ/SPXW execution
priority; only final row output uses lexicographic ticker ordering.

Static inspection confirmed the precision1000/Inexact Decimal context, reserve
principal and fee expense, negative missing-bid exit commission, strict A/B
quote clocks, zero/null distinction, 47 ledger fields and provenance. Tests
include independent hand-calculated values, cost differences, replay-level
capital exhaustion, lockout/tie precedence, three tickers, Decimal isolation
and complete monetary snapshots. The rejected first candidate is preserved.

The helper is standard-library/in-memory only; it has no I/O, network, subprocess,
NumPy, PyArrow or dependency on the FSM producer or independent auditor. The
independent auditor author must not read/import this helper or its tests.

No imports, compile, lint, pytest or real values were executed in this review.
The first formal suite still needs a separately reviewed observed harness,
byte-exact publication, contemporary official resource gates, retained children,
snapshots, closing pins and immutable failure handling. There is no fixture PASS
or economic result yet. Goal active; selected_policy=null; promotion_approved=false.
