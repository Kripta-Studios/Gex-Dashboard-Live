# Prospective readiness — prepared, not activated
Local eligibility registry only. Production consumers are unchanged.
Policy identity/hash, schema/feature/decision hashes and approval are mandatory.
Intent is distinct from simulated fill and broker-confirmed execution.
Required event fields: market_timestamp,received_at,feature_started_at,
feature_completed_at,decision_at,intent_at,quote_age_ms,processing_latency_ms,
policy_sha256,feature_sha256,decision_reason,broker_submission=false.
Log abstentions/rejections/errors and compare historical/live clock and feature
parity on a separately authorized future complete month with prior freeze.
August/September exposure UNKNOWN; local presence proves neither viewed nor unseen.
October is merely a possible future candidate, never guaranteed or validated here.

Future account interface must specify initial capital, integer quantities, cash,
per-contract commissions, joint exposure, capital rejections, loss limits,
marking rules, prospective horizon and precision. No capital or real limits
are chosen here; one-contract PnL is not account validation.
