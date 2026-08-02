# KING NODE v2 fixtures

`golden_input.json` is a deterministic, documented arithmetic example for the
pure v2 core. It is not a market replay and is deliberately separate from the
hash-pinned workbook static reference. The expected assertions record only
fields whose source values are present and validated; no missing/stale workbook
cache is used as an oracle.
