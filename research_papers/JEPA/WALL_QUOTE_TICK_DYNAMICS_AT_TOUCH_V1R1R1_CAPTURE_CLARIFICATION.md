# H-QDYN1 V1R1R1 capture clarification

Status: frozen before any H-QDYN label join, model fit, physical result or
payoff result. This clarification narrows implementation semantics without
changing the 28-feature allowlist, folds, models or statistical gates.

The V1R1 capture was stopped during its outcome-free download after adversarial
code review. Its partial directory
`D:/ThetaData/wall_quote_tick_dynamics_at_touch_202208_202512_v1r1` is
`REJECTED_CAPTURE_SEMANTICS` and must not be resumed, sealed or joined.

V1R1R1 freezes these corrections:

1. Raw zero, crossed, negative and non-finite quote fields are preserved in the
   normalized parquet. Only identity, timestamp window and response-order
   violations reject the raw capture. Feature transitions continue to require
   finite positive bid, non-crossed ask, nonnegative sizes and finite exchanges.
2. A size-only transition requires at least one displayed size to change while
   bid price, ask price, bid exchange and ask exchange all remain unchanged.
3. Bid/ask conditions remain part of exact-row deduplication, so a condition
   report is an update. Conditions are quality-preserved but are excluded from
   state-change, price-change, size-only and exchange-change measurements; they
   therefore cannot become an implicit alpha feature.
4. Exact contract equality means literal normalized numeric strike equality.
   The prior `1e-9` tolerance is withdrawn for both the `t-5m` listing proof and
   the tick-response contract check. Rebuild and reseal the listing proof before
   any replacement capture, even if its eligible event set remains unchanged.

The replacement must use a new V1R1R1 directory, bind the rebuilt proof hashes,
pass focused boundary/non-finite/near-strike/size-only tests, and revalidate all
event files before a seal. No outcome may be inspected to decide these rules.
