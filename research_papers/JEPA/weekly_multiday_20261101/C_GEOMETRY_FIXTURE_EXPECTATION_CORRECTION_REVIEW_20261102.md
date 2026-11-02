# C geometry: fixture expectation corrections after C02

Date: 2026-11-02. Status: `CLEAR_FOCAL_REPIN_FINAL`.

C02 ran from remotely verified commit `9c58829188d4959f5a3831507c2526525287a88c` (40 exact files, root24d065). Compile and Ruff passed. Pytest child60216 exited1 at `2026-11-02T16:56:54.372823+00:00`; root retained session21282 exit1 (`be71a1`). Result: 65 passed, four failed, one collection/setup error in 7.14 seconds. This is not a passing suite. Original logs and snapshots are preserved in `weekly_zone_geometry_1030_fixtures_02` and its failure archive02.

The corrections change only the two test modules; producer ebe7c898 and auditor f2d17a78 remain unchanged. Root checked the failures against the published schemas and pinned engines. Independent reviewer `/root/daily_auditor_review` cleared the exact final deltas:

- `source_mask` expects the contracted Arrow int16 type and actual bit values.
- Gamma tests use the actual CALL/PUT_BS_GAMMA_PROXY names and require all six positive components. Both sessions now share an identical spot prefix and therefore the same spot1030/IB; tau is explicitly 330 versus 150 minutes, and each side/strike gamma pair must differ.
- OI uses the actual CALL_OI name/mask and asserts three strike-ordered walls and equal synthetic weights.
- Coverage asserts the contract's exact 18-field keyset, replacing an erroneous count of 21.
- A helper named test_authority_units is renamed authority_units_for so pytest does not collect it as a test requiring a nonexistent fixture.

Final test pins:

- `test_build_weekly_zone_geometry_1030.py`: 35,739 bytes, SHA-256 `ec6aebc5c74d8dcc62e3a10a6ee2d4e722b1e6f58f84c4f56436abbd294dbcd5`.
- `test_audit_weekly_zone_geometry_1030.py`: 55,343 bytes, SHA-256 `e010c83e6891cf600b5ee6cee16cc5e2eb9a269b6bbd27270ffc3cdaa0f53848`.

No runtime rules or economic selection changed. The earlier intermediate 4c92d203 test pin is superseded. No tests were rerun during review. Root authorizes one fresh synthetic suite under a repinned, reviewed and published harness03 with contemporary gates; preserve both failed attempts. Real C and economic evaluation remain unauthorized until their existing prerequisites close.
