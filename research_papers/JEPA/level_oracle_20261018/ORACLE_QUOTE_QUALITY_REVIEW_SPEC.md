# Oracle quote-quality control review specification

This is a read-only code-and-evidence review. It opens no new raw values and does
not change, filter, or rerun the oracle. Its purpose is to distinguish the quote
checks actually enforced by the frozen cache, engine, and independent audit from
economic-plausibility checks that were never implemented.

The review must bind `build_cache.py`, `level_engine.py`, `audit_engine.py`, the
protocol, and the authoritative full audit JSON by SHA-256. It must classify at
least these controls:

1. finite, positive/nonnegative, noncrossed bid/ask and raw-fill equality;
2. stored clock choice, paired-clock comparison, and the separate 0--60 second
   age check applied to the underlying spot;
3. option value versus intrinsic value;
4. same-strike put-call parity;
5. option-quote age, update recency, or unchanged-quote-run staleness;
6. spread-width and cross-strike/calendar arbitrage plausibility.

Synthetic fixtures must show that basic validity does not imply intrinsic,
parity, or staleness coverage, and that a hypothetical source containing those
controls is classified separately. The output is diagnostic evidence only. It
must not propose post-outcome filtering of trades and must retain the declared
proxy-clock, OI receipt, live-parity, and promotion limitations.

