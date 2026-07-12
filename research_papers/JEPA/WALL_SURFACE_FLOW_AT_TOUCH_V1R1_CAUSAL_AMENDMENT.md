# WALL_SURFACE_FLOW_AT_TOUCH_V1R1 — causal amendment and executable freeze

Status: predeclared before building or inspecting wall-flow outcomes.  This
document supersedes V1 where they differ.  It is a correction of causal and
identification defects, not a response to model performance.

## 1. Why V1 could not be executed

Independent audits found five blocking ambiguities:

1. V1 called a defended terminal close a rejection without requiring an actual
   pierce, recreating the already-closed wall V1 bug.
2. Derived-underlying timestamps are bar opens.  The old label code excluded
   `[t,t+1m)` and included `[t+h,t+h+1m)`, shifting the label one minute forward.
3. Gamma/delta aliases and repeated 5-minute touches counted the same physical
   interaction multiple times.  Some strikes were simultaneously tagged support
   and resistance.
4. V1 did not freeze ratio denominators, missingness conventions or an exact
   feature allowlist.
5. The current live stack cannot retain the full 15-minute surface and exact
   bar-start quote.  Historical feasibility does not imply live parity.

No outcome, physical label, option return, PnL or 2026 value was inspected while
making these corrections.

## 2. Frozen source universe and provenance

Inputs remain:

- wall-state SHA-256
  `94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef`;
- executable decision view SHA-256
  `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`;
- ThetaData manifest SHA-256
  `5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88`;
- dates `20220801..20251231`; 2,519 exact 0DTE sessions; session-key SHA-256
  `ac7200fd96f2ef9afc2f9f09eff18804497a2f975a7454cccf5ed1c935653057`;
- exact decisions `10:35..14:30 ET`, five-minute grid on regular sessions.  On
  the nine frozen half days (`20221125`, `20230703`, `20231124`, `20240703`,
  `20241129`, `20241224`, `20250703`, `20251128`, `20251224`) physical decisions
  end at `12:55 ET`.  The executable event view, not the denser wall grid, is
  the denominator.

The executable event spot is canonical.  Its wall-snapshot copy must agree
within `0.001 bps` (only float serialization; observed maximum was
`0.000572 bps`) or the build fails.  All touch distances and local radii use the
canonical executable spot.

The builder must content-hash every Greeks, OHLC and underlying Parquet used and
record bytes, rows, schema hash, timestamp range, interval, symbol, expiration,
trade date, rights and distinct strikes.  It must verify the hash again after
reading, reject duplicate normalized keys, reject non-1m option inputs, require
`expiration == trade_date`, and reject all 2026 rows.  An authoritative output
directory is immutable and written by atomic staging/rename.

Derived-underlying files additionally require exact symbol/date metadata,
minute-boundary unique timestamps, every regular-session minute through the
physical close, and positive finite OHLC/envelope/tick count from 10:19 onward
(the first timestamp any frozen F0/label can consume).
Candidate spot must match the exact underlying bar open within 0.001 bps.  The
external historical producer version is not embedded in old Parquets; current
producer hashes and its floor/zero-repair caveat are frozen in the provenance
audit rather than silently treated as a committed build lineage.
The full structural audit passed 2,519/2,519 usable sessions and records three
invalid pre-10:19 rows without repair or data-driven session exclusion.

ThetaData OHLC timestamp `s` is the bar open and the bar contains trades in
`[s,s+1m)`.  Quote/Greeks `timestamp` is preferred.  Older files lacking it may
use `underlying_timestamp` only as an explicitly tagged reconstructed interval
grid; this is a provenance limitation, not an observed option quote timestamp.
Every native dual-timestamp row must agree exactly or the build fails.  The
authoritative data gate requires zero unverified fallback sessions.

The frozen census found native option `timestamp` in 1,078/2,519 sessions and
128,362,954/325,753,830 Greek rows.  The remaining 1,441 sessions are not
authorized by regular-grid inference.  They must be recovered from the native
`/option/history/quote` endpoint by
`neural/jepa/build_wall_native_quote_sidecar.py`, with a frozen local Terminal,
raw response hashes and exact whole-key-set equality against stored
`underlying_timestamp` in the research window. Reconsulted bid/ask revisions
are counted but never replace the original hashed Greek bid/ask used by F1.
Only a sealed 1,441/1,441 timestamp-key PASS may replace the fallback clock. Quote sizes are archived but
are excluded from H-FLOW1; they define a separate future H-QSIZE1 experiment.
Every stored Greek key must be covered. Native keys added by a current provider
revision are counted and archived but never expand the frozen historical
contract universe.

Two clocks remain distinct.  The physical underlying RTH close is 16:00 on
regular days and 13:00 on the listed half days for all tickers.  Expiring SPXW
options close at the same time; QQQ/SPY options close at 16:15/13:15.  Physical
decisions and labels use the earlier underlying close.  These half-day option
hours follow Cboe's published holiday notices, not a volume-derived heuristic.

## 3. Frozen physical episode universe

At each executable decision and for CALL/PUT gamma/delta walls:

- compute signed distance `(spot - wall) / spot * 10,000`;
- require absolute distance `<=15 bps`;
- collapse gamma and delta identities when the same role has the same strike at
  the same decision; represent the identity as a multi-hot set;
- if the same strike is simultaneously support and resistance at the same
  decision, exclude both as role-ambiguous;
- within ticker/session/role/strike, contiguous five-minute at-touch rows form
  one episode;
- retain only the first row of each episode.  Monthly coverage counts resolved
  first-touch episodes, never raw identity rows or repeated bars.

These rules are symmetric and global; no ticker-specific exclusions exist.

## 4. Frozen completed-bar construction

For every raw option OHLC row:

- `raw_active = volume > 0`;
- `priced = raw_active AND finite(close) AND close > 0`;
- `valid_quote = finite(bid,ask) AND bid > 0 AND ask > 0 AND ask >= bid`;
- `signable = priced AND valid_quote`;
- `trade_sign_proxy = sign(close - (bid+ask)/2)` for signable rows, otherwise 0;
- unsigned `volume` and `count` retain every raw-active row; missing count becomes
  zero and lowers count-coverage;
- `close_notional = volume * close * 100` only for priced rows, otherwise zero;
- signed volume/count/close-notional equal sign times the unsigned quantity only
  for signable rows, otherwise zero.

`close_notional` is a bar-close notional proxy.  It is not VWAP, actual paid
premium or observed aggressor flow.  V1R1 may not describe it as any of those.

For decision `t`, windows are summed after row-level construction:

- 1m: bar starts `[t-1m,t)`;
- 5m: `[t-5m,t)`;
- 15m: `[t-15m,t)`.

No per-bar ratio is averaged.  Ratios are formed after summing the full window;
a zero/nonpositive denominator produces exactly zero.

Source-grid coverage is schedule-aware: regular sessions require every exact
minute `10:20..14:29` (250 boundaries), while the nine half days require
`10:20..12:54` (155).  Greek/OHLC/underlying timestamps must belong to the exact
declared session date; matching metadata alone is insufficient.

For CALL and PUT separately, whole-surface features are unsigned/signed volume,
count and close-notional plus row-, volume-, price-, signable- and count-coverage.
Combined formulas are:

```text
directional_pressure =
  (CALL_signed_close_notional - PUT_signed_close_notional)
  / (CALL_close_notional + PUT_close_notional)

volume_imbalance = (CALL_volume - PUT_volume) / total_volume
count_imbalance = (CALL_count - PUT_count) / total_count
close_notional_imbalance =
  (CALL_close_notional - PUT_close_notional) / total_close_notional
```

Local rows use the candidate's right and strikes within inclusive 30 bps of the
current wall, measured against current spot.  Local features use the same sums
and coverage.  Exact ratios are:

```text
buy_sell_close_notional_log_ratio = log1p(buy_close_notional) - log1p(sell_close_notional)
signed_close_notional_ratio = signed_close_notional / close_notional
role_break_pressure = signed_close_notional_ratio
```

CALL buying at resistance and PUT buying at support both point in the role's
break direction, so no data-dependent sign flip is used.  Persistence flags are
one only when the nonzero signs agree for 1m/5m or 5m/15m.

The executable allowlists are generated by
`neural/jepa/surface_flow_features.py`; their ordered SHA-256 hashes must be
stored in the data and frozen-runner manifests.

## 5. Frozen control F0

F0 contains only:

- minute sine/cosine;
- resistance role flag and multi-hot wall identity;
- current signed/absolute distance;
- causal spot return at 1/5/15/30m and absolute 1m return;
- completed-bar realized volatility at 5m and 15m;
- distance change and absolute-distance approach at 5/15/30m.

Realized volatility is the population standard deviation of five or fifteen
one-minute log returns constructed from `N+1` underlying closes whose bar starts
end at `t-1m`.  Current incomplete underlying bar `t` is excluded.

F1 is exactly F0 plus the single surface-flow block in section 4.  No wall-state
strength, IB, IV deformation, payoff, future or outcome column is eligible.

## 6. Corrected future-only labels

For each horizon `h in {30,60,120,180}`:

- require every exact underlying bar start `s` with `t <= s < t+h`;
- pierce uses highs/lows from those bars;
- terminal price is the close of the exact bar starting `t+h-1m`;
- bar `t` is included and bar `t+h` is excluded;
- a candidate already beyond the wall at exact decision spot counts as already
  pierced;
- `true_rejection = pierced AND terminal >=5 bps on defended side`;
- `accepted_break = pierced AND terminal >=5 bps beyond wall`;
- neutral or non-pierced rows have no resolved target;
- `resolved_rejection=1` only for true rejection and 0 only for accepted break.
- require `t+h` no later than the underlying RTH close (16:00 regular, 13:00
  half day); vendor extended/stale bars never complete a horizon.

Future high/low/close is label-only and never enters F0/F1.

## 7. Frozen model, folds and diagnostics

Use LightGBM binary classification with 300 trees, LR 0.03, 15 leaves, minimum
child 100, feature/bagging fraction 0.8, L2 1, deterministic seed 20260711 and
28 threads.  Class weights are calculated on training rows only.

Expanding outer folds remain:

- train through 2023, test calendar 2024;
- train through 2024, test calendar 2025.

There are exactly 24 paired cells: 3 tickers x 2 folds x 4 horizons.  Every cell
reports ROC-AUC, average precision, balanced accuracy at fixed 0.5, Brier,
log-loss, Spearman and ten-bin ECE/calibration.  F1-F0 AUC receives a deterministic
1,000-replicate paired ticker-day block bootstrap; episodes are unique before
bootstrap.  Missing or degenerate cells are losses.

## 8. Frozen gate

Physical-mechanism success requires all:

1. 24/24 valid pairs; at least 16 AUC wins; median delta `>=+0.010`.  Because
   four horizons reuse the same episodes, first take the median delta inside
   each ticker-fold cluster and apply the one-sided paired Wilcoxon to the six
   cluster medians; require `p<0.05`.
2. Each ticker wins at least 5/8, has positive median delta and median F1 AUC
   `>=0.55`.
3. At 30/60m each ticker wins at least 3/4, has positive median delta and median
   F1 AUC `>=0.55`.
4. Every outer ticker-month at 30m and 60m has at least 18 resolved first-touch
   episodes and both classes.  Abstention/missing months fail.
5. F1 may jointly lose both average precision and log-loss in at most 12/24
   cells.

The historical data gate additionally requires all 2,519 frozen sessions, 12
ticker-year cells, quote row coverage >=75%, quote volume >=90%, priced volume
>=99%, signable volume >=90%, nondegenerate core flow features and zero missing
values in the frozen F0/F1 allowlists.  Every one of the 2,519 sessions must
also expose its complete schedule-aware option/Greek grid, positive raw option
activity and a native or fully sidecar-verified quote timestamp; annual
aggregation cannot hide a truncated, reconstructed or empty session.

Python, platform, NumPy, pandas, PyArrow, LightGBM, SciPy and scikit-learn are
frozen by `requirements-wall-surface-flow-v1r1.txt`.  Builder, freeze generator
and evaluator fail if the lock hash or exact runtime fingerprint differs.

## 9. Promotion blockers independent of model score

The current live files do not reproduce this feature block: option requests omit
explicit `interval=1m`, files overwrite short windows, the bar-start quote is
discarded, full surface is ATR-filtered and live walls do not share the frozen
wall module.  Therefore:

- a physical score can be recorded only with its historical timestamp-provenance
  status;
- no option-payoff experiment is authorized while provenance is conditional;
- no production or shadow claim is authorized until an append-only sidecar
  collector passes bit-identical offline/live replay with explicit interval,
  full chain, exact expiration keys, immutable scheduled `t`, bar-start quotes,
  15-minute retention and feature-availability timestamps;
- any later option entry must occur after actual feature availability, never
  retrospectively at scheduled `t`.

Production files and the sealed 2026 holdout remain untouched.
