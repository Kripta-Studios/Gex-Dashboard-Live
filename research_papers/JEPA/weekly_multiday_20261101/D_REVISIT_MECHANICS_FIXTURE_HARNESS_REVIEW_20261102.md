# D producer mechanics: first synthetic fixture harness

Status: CLEAR_D_REVISIT_MECHANICS_FIXTURE_HARNESS.

Fresh reviewer `/root/d_mechanics_harness_review` returned SHIP for the bounded
clone of the closed accounting harness. Root independently inspected its diff.
Exact source pins are:

- launch_d_revisit_mechanics_fixtures01_20261102.py, 16460 bytes,
  f8c4991bfcc7fc40589b562f2761d058cc7fda57f15582323b003cae3ea86797;
- weekly_zone_revisit_mechanics.py, 38277 bytes,
  4dd7831194be70805028e4c5646d763f907767ad77095d24b5746314afb0f313;
- test_weekly_zone_revisit_mechanics.py, 23950 bytes,
  c8386a3060677e2c6b96a4570f4e2bb08a6fadb533025fcd7b98f98cd94c98ba;
- weekly_zone_revisit_accounting.py, 18783 bytes,
  9bcc4f834745806289550d2119f7d35ad0281c2fe151ac36c87be24aa72594fb.

All11 frozen inputs, including six normative documents, producer static review
and official resource helper, match their complete byte/SHA pins. The harness
admits this separate review by its supplied full SHA and requires the marker
and producer/test/accounting/harness hashes above. Fixed branch and remote HEAD
equality, Git byte equality, plain-file path checks, CPU0/TEN1/CUDA=-1 before
pin I/O, official2GB RAM/free-commit/disk gates, exclusive fresh roots, hidden
retained children, snapshots, closing pins and no retries remain enforced.

After byte-exact publication, scope is the first mechanics-producer-only
synthetic suite: compile and Ruff the producer, its tests, accounting dependency
and harness, then pytest only test_weekly_zone_revisit_mechanics.py. The closed
accounting suite is not repeated. Artifact roots are
weekly_zone_revisit_mechanics_fixtures_01 and
weekly_zone_revisit_mechanics_fixtures_observer_01 under the established D base.

No independent auditor code, B/C runtime, ThetaData or real replay is referenced.
The review executed no import, compile, lint or test. Failure must remain closed
and preserved; no automatic retry or root reuse is allowed. A passing suite
would be synthetic implementation evidence, not audited market PnL. Goal active;
selected_policy=null; promotion_approved=false.
