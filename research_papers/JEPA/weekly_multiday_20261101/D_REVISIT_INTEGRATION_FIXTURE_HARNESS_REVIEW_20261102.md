# D mechanics: first observed cross-implementation agreement suite

Status: CLEAR_D_REVISIT_INTEGRATION_FIXTURE_HARNESS.

Fresh read-only reviewer `/root/d_integration_harness_review` returned SHIP.
Root separately inspected the complete new harness. Exact current pins:

- harness21933 bytes, f64f9653b80b70ce2a4fc411ba9fcba467b17758799093002435988d333253ad;
- producer38317 bytes, 6c8677453d08699825c4c5cc2439af6eb0f48e7433dab6dea7d812c8c07c34a7;
- auditor68119 bytes, c6c77b1e12b166796c06335621b606b03006617e3dc0a374a2bc2d489ec554d7;
- accounting18783 bytes, 9bcc4f834745806289550d2119f7d35ad0281c2fe151ac36c87be24aa72594fb;
- integration tests10675 bytes, ee549203a778545ac0ed07546135a67526b1b65fe92bb758caaad38b914c8ead.

All19 frozen dependencies match full bytes/SHA, plain-file metadata and published
Git bytes: four code/test files, official resource helper, six normative docs,
four reviews and four component receipt/retained-exit projections. The producer
has closed23 tests/32 subtests, accounting10 tests, and the independently authored
auditor19 tests/167 subtests. All component closures were independently reviewed;
their prior failed attempts remain preserved and are not adopted.

The harness enforces fixed research branch and remote HEAD equality, exact Git
bytes, absolute plain files/ancestor reparse/single-link checks, all four public
review markers, current code/test hashes and this separate review marker/self
hash. It admits both component receipts before root creation: exact schema and
PASS_CLOSED, zero compile/Ruff/pytest codes, matching current implementation
pins, and paired retained exits with zero code, null metadata error, empty
changed pins and retry=false. External observer paths recorded in receipts are
not opened. CPU0/TEN1/CUDA=-1, official2GB RAM/free-commit/disk gates before roots
and each child, retained hidden children, source snapshots, closing pins and
no retries remain enforced. Both intended roots were absent at review.

After byte-exact publication, run once in
weekly_zone_revisit_integration_fixtures_01 and
weekly_zone_revisit_integration_fixtures_observer_01 under the established D base.
Compile/Ruff only the integration test and this harness, then pytest only the
integration test. Closed component suites are not repeated. Closure schema is
d_revisit_integration_fixture_closure_v1. Any failed attempt must be preserved
and closed, with no automatic retry or root reuse.

The five artificial agreement cases exercise baseline CALL costs, PUT missing-bid
fees, B-only lockout after A exits, no-trade/historical coverage, and corrupted
observed output rejection. Each requires the independent auditor to reconstruct
the producer's complete public records; this has not yet been executed or passed.
Harness author/reviewer did not read the independent algorithms; only public
contracts, metadata and full file hashes were used. The independent auditor
author did not read these integration fixtures while implementing its code.

No Python import, compile, lint, tests, real data, benchmark or D adapter was
executed in this review. A passing joint suite would validate synthetic agreement
only. Real B/C/D admission and the complete economic comparison remain required.
Goal active; selected_policy=null; promotion_approved=false.
