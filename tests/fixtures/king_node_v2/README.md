# KING NODE v2 fixtures

`golden_input.json` is a deterministic, documented arithmetic example for the
pure v2 core, with 47 strikes spaced by 5 points and both rights at every strike.
It is not a market replay and is deliberately separate from the
hash-pinned workbook static reference. The expected assertions record only
fields whose source values are present and validated; no missing/stale workbook
cache is used as an oracle.

October expectations use analytic Black-Scholes with r=.043, q=.012,
CALL IV for both legs, six hours to the source's 20:00 UTC expiration,
and SCALE=.001. Totals sum the individually rounded dollar exposures.
The independent-equation test recomputes gamma, GEX and zomma without importing
the source Greek implementation. Matrix assertions deliberately distinguish
raw HIGH IV from the map-first Low IV classification. These fixtures do not
claim full Microsoft Excel recalculation or historical/live market parity.
