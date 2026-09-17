# Sources and clocks
Rules DATA-001/002, TIME-001..005 and unchanged V1 formulas bind.
Allowed roots: D:/ThetaData/data_underlying_derived/{SPXW,SPY,QQQ} and
D:/ThetaData/data_options/{SPXW,SPY,QQQ}/{greeks,iv,ohlc,oi}.
Options filenames distinguish expiration then trade date. Inventory all names and
footers; construction 20220801..20260630 only. No future payoff checks in gate.
Capture scripts are read as text, never imported. Do not read credentials.

Local scripts script4_underlying_from_options.py and download_spot.py aggregate
underlying_price using timestamp preferentially over underlying_timestamp, floor
to minute, then first/max/min/last/count. They can repair partial rows and bfill/
ffill full gaps; download_spot additionally filters nonpositive prices first.
Current script text alone cannot certify the historical generator or replacement
time. A per-file generation/repair record or reproducible bound is required.
Store SPXW_INITIAL_ZERO_BAR sidecar, replaced fields, original zero/invalid evidence,
replacement timestamp/bound, effective availability and evidence hash. No other repair.

OI must have unique contractual keys and documented prior-close availability.
Timezone America/New_York is a historical source interpretation, not proof of live parity.
Calendar is XNYS4.12, immutable schedule hash; half sessions joint exclusion.
Coverage retains initial sessions, half days, missing sources, quality exclusions,
admitted dates, expected/built event counts by month. No outcome-driven exclusion.
