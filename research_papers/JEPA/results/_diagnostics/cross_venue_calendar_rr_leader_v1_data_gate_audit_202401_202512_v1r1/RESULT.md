# CROSS_VENUE_CALENDAR_RR_LEADER_V1 independent data-gate audit V1R1

Status: `PASS_INDEPENDENT_DATA_GATE_AUDIT`

Executed once after the outcome-free data gate from commit
`90ffd155292801230d9a20bdb0dc15be03deb34f`.

- rows / captures: 1,506 / 3,012
- source inventory rows: 16,566
- source hash mismatches: 0
- source size mismatches: 0
- mapping parity: PASS
- feature view SHA-256:
  `d4335ad85e3242f45dad3708f2a6f571ad8b2f820fa3c66d1cf2e7003a566062`
- mapping parity SHA-256:
  `b19cb9ebf9240e824bd056887ef5cfe519b2d6a1f917d937d84070162375f8ac`
- source inventory audit SHA-256:
  `6d3180f1694c37a5108e441f112754901360444bf43c5068ec38e19af0308194`
- audit summary SHA-256:
  `7700b0878f6400a14a66d60141fd5a6b164de3b84ce1a2974b6d72ba5be85dac`

The audit independently recomputed coverage, distinctness, monthly frequency
and exact-date SPY-to-SPXW mapping. It read no underlying values and no
outcomes. Outer 2024/2025, holdout 2026 and production remain unopened.
