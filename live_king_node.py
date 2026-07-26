# live_king_node.py  —  V5 layout, dealer exposures (GEX / DEX / VEX, dollar-scaled)
#   A Strike | B Gamma(gross) | C GEX | D Zomma | E Dex | F Vex | G Vomma | H Vega | I Speed
# Smoothing (rolling average) + level lock (hysteresis) keep the display stable.
# Ctrl+C to stop. Reads data only; never trades.

import os
import csv
import math
import datetime
import time
from collections import deque
import xlwings as xw
from ib_async import IB, Index, Option, ContFuture

# ---- settings ----
PORT     = 4001
WORKBOOK = r"C:\AMD\Aimee\Trading\Indicators\IBRK King Node Data\MASTER_KING_NODE_RECORD_V5.xlsx"
SHEET    = "King Node Model"
LE_SHEET = "Level Engine"

REFRESH  = 30
SMOOTH_N = 3             # readings to average before writing (3 x 30s = 90s smoothing window)
LOCK_HOLD = 3            # a challenger must beat a locked level this many cycles in a row to replace it
                         #   higher = stickier levels; lower = quicker to change
STRIKES_EACH_SIDE = 23
INDEX_TYPE  = 2          # 2 = frozen: live during market hours, last value after close (keep at 2)
OPTION_TYPE = 1          # 1 = live (OPRA active); 3 = delayed; 4 = delayed-frozen (weekend testing)
RATE = 0.043
DIV  = 0.012
SCALE = 0.001
VEGA_PER  = 0.01
FIRST_DATA_ROW = 29

GEX_SIGN = 1
DEX_SIGN = 1
VEX_SIGN = 1
CHARM_SIGN = 1          # flip to -1 if the live charm Pos/Neg reads inverted vs Matrix CharmPos/CharmNeg
RUN_OUTSIDE_HOURS = True

# ---- vomma peak monitor ----
VOMMA_NEAR = 25          # +/- points around spot to sum near-spot |vomma| each cycle
VOMMA_HIST = 8           # readings kept / shown in the monitor (8 x 30s = 4 min)
VOMMA_ROLL = 0.05        # LONG trigger: near-spot vomma falls this far off its recent peak (0.05 = 5%) -> vol exhausting -> bounce
VOMMA_RISE = 0.05        # SHORT trigger: near-spot vomma rises this far off its recent trough (0.05 = 5%) -> vol re-accelerating -> rejection
VOMMA_GATE = True        # if True, a trigger only stands when price is at a matching vol level (LONG at VOMMA BID support / SHORT at VOMMA CAP resistance)
VOMMA_GATE_NEAR = 10     # how close (pts) spot must be to that level for the trigger to stand
VOMMA_HOLD = 60          # once a LONG/SHORT trigger fires, keep it on screen at least this many seconds (anti-blink)
# ---- move velocity monitor ----
SPOT_HIST  = 8           # spot readings kept / shown (8 x 30s = 4 min)
VEL_WINDOW = 3           # intervals (~90s) used for the rolling pts/min reading

# ---- archive data-quality ----
SPIKE_PTS = 15           # tag event="SPIKE?" when spot jumps more than this many points in one
                         #   archived cycle. One-sided breadcrumb for backtests; does NOT alter the
                         #   written price (never masks a real move). Raise toward 20-25 to flag
                         #   fewer fast-but-real moves; the two-sided despike in the backtest decides.
# ============================================================================
# ---- TECHNICAL ANALYSIS / AMT overlay (ES feed)  —  STAGE 1: feed + panel ----
# ----------------------------------------------------------------------------
# Stage 1 streams ES via tick-by-tick AllLast, seeds the session from history at
# startup so values match a TradingView draw on the first cycle, and writes a
# read-only REFERENCE PANEL onto the 'Technical Analysis' sheet (columns I:K,
# clear of the A:G spec text). It computes: live ES, daily VWAP (18:00 ET anchor),
# weekly VWAP (Sun 18:00 ET anchor), overnight H/L, the 60-min IB + its Fib
# extensions, and the developing RTH volume profile (POC / VAH / VAL).
# NOT YET wired into the Greek tables or confluence — that is Stage 2 (box-gate).
# Prior-day POC/VA = Stage 1b; HVN/LVN/Balance flag = Stage 3.  Reads only; never trades.
TA_ENABLED        = True             # master switch for the whole ES/TA block
TA_SHEET          = "Technical Analysis"
TA_PANEL_ROW      = 4                # panel header row; values fill downward
TA_PANEL_COL      = 9                # 9 = column I (spec text lives in A:G, so this is clear)
ES_EXCHANGE       = "CME"
ES_TICK           = 0.25             # ES min tick; structural levels are MROUNDed to this
PROFILE_BIN       = 1.0             # ES points per volume-profile bucket (POC/VA resolution)
VALUE_AREA        = 0.70             # fraction of session volume inside the value area
IB_MINUTES        = 60               # Initial Balance window length (09:30-10:30 ET)
IB_OPEN_ET        = (9, 30)          # RTH open / IB start / overnight lock
SESSION_OPEN_ET   = (18, 0)          # Globex open: daily VWAP + overnight anchor
RTH_CLOSE_ET      = (16, 0)          # RTH close (profile session end)
FIB_MULT          = (0.27, 0.618, 1.0)   # extension distances (x IB range) beyond each IB edge
TA_SEED_HISTORY   = True             # seed VWAP/profile/ON/IB from 1-min bars at startup
TA_SEED_DURATION  = "5 D"            # history window (covers Sun 18:00 -> now for weekly VWAP)

# ---- ES 5-minute moving averages (200 / 400 period) ----
# 200 and 400 bars on the 5-MINUTE ES chart -- i.e. ~16.7h and ~33.3h of clock time,
# NOT 200/400 calendar days. Seeded from 5-min history at startup, then advanced live
# off the same tick stream the profile already consumes: each 5-min bucket's last trade
# becomes that bar's close, and the forming bar's running last completes the window.
# ETH by default (useRTH=False), which is how a continuous ES chart draws it -- set
# SMA_USE_RTH = True if your chart is set to RTH-only, as the two give different levels.
# OBSERVATION ONLY: displayed on the TA panel and archived. Nothing reads these into a
# signal, the reaction table, or confluence. Any such wiring is a separate change.
SMA_ENABLED       = True
SMA_PERIODS       = (200, 400)       # bars, on the 5-min timeframe
SMA_BAR_MIN       = 5                # bar size in minutes
SMA_SEED_DURATION = "10 D"           # ~2,760 ETH 5-min bars; 400 needs only ~34h
SMA_USE_RTH       = False            # False = 24h ES session (chart default for futures)
# ---- archive settings ----
# Each completed refresh() is appended to a per-day CSV in this folder, created
# next to this script. One row per strike per cycle; cycle-level fields (spot,
# vols, Pos/Neg flags, locked R/S levels) are repeated on each of that cycle's
# strike rows so every snapshot is self-contained and reload needs no joins.
ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archive-data")
ARCHIVE_HEADER = [
    "timestamp", "spot", "vix", "vvix", "vix1d",
    "flag_gamma", "flag_zomma", "flag_dex", "flag_vex", "flag_vega", "flag_vomma", "flag_speed", "flag_charm",
    "r1", "r2", "r3", "r4", "r5", "r6",
    "s1", "s2", "s3", "s4", "s5", "s6",
    "row_idx", "strike", "gamma", "gex", "zomma", "dex", "vex", "vomma", "vega", "speed",
    "confl", "abs_gamma",
    # ---- raw per-strike inputs (unsmoothed, exactly as read from IBKR this cycle) ----
    # Logged alongside the smoothed computed Greeks so a backtest can reconstruct the
    # surface from source rather than inferring it. call_iv is the IV the live engine
    # actually feeds into BOTH legs of greeks() (see the strike loop); put_iv is captured
    # for reference and for skew work, and is NOT yet used in any Greek calculation.
    "call_iv", "put_iv", "call_oi", "put_oi",
    # ---- ES 5-min SMAs (cycle-level; repeated on each strike row like spot/vix) ----
    # Appended at the END rather than beside `spot` so every pre-existing column keeps
    # its original index and replay/seed code that reads by position still works.
    "es_sma200_5m", "es_sma400_5m",
    # ---- skew monitor (cycle-level, vol points) ----
    "put_skew", "call_skew", "risk_rev",
    # ---- ATM IV + its direction (cycle-level, repeated on every strike row) ----
    # atm_iv     : ATM CALL IV interpolated at spot -- the vol that moves gamma/zomma
    #              (greeks() feeds the CALL IV into BOTH legs).
    # atm_iv_dir : Up/Down/Flat from the same two-half engine that feeds
    #              'Level Engine'!B3 -> D5.
    # MUST sit immediately before "event" -- that is where _out appends them.
    "atm_iv", "atm_iv_dir",
    # ---- ranking internals, per strike (Level Engine AR / BB) ----
    # ar_score : the strength score the top-6 locked lists are sorted on.
    # rank_tag : the resulting tag -- "R1".."R6" / "S1".."S6" / "" if it ranked nowhere.
    # Added 2026-07-13 because the max-gamma node flips in and out of the locked list 53x
    # a session and neither cause could be diagnosed offline without these.
    "ar_score", "rank_tag",
    # ---- qualification + absorption internals, per strike (Level Engine) ----
    # Added 2026-07-17 to settle offline why a level that clears surface-OR / size /
    # confl / membership still fails to surface -- specifically the max-pos-GEX
    # "green wall in a sea of red" (e.g. 7500 on 2026-07-17) being vetoed by shelf/edge
    # absorption rather than by rank or chop. Read back from the computed Level Engine.
    #   cu_qual     : resQual(R)  CU9 0/1 -- did this level qualify as resistance at all.
    #   cv_qual     : supQual(S)  CV9 0/1 -- did this level qualify as support at all.
    #   bk_absorbed : BK9 -- absorbed by a stronger reversal-flagged adjacent level.
    #   dh_absorbed : DH9 -- absorbed into a gamma-shelf/edge that spans the strike.
    #   dc_shelf    : DC9 -- gamma-shelf candidate flag (the shelf DH tests against).
    #   cz_dedge    : CZ9 -- DEX drop-off edge flag.
    # Appended immediately before "event" so every pre-existing column keeps its index
    # and replay/seed code that reads by position still works.
    "cu_qual", "cv_qual", "bk_absorbed", "dh_absorbed", "dc_shelf", "cz_dedge",
    # ---- shelf/wall lock band, cycle-level (added 2026-07-24) ----
    # The CT (resistance) / CW (support) hysteresis band that can substitute the
    # reaction-table level for its near edge. Logged to backtest how often, and in
    # which regime, that substitution fires. ct_lo/ct_hi = MIN/MAX(CT3,CT4); likewise
    # CW. Blank when that side's band is unarmed (CT2/CW2 = 0, engine writes None).
    # Repeated on every strike row like the other cycle-level fields.
    "ct_lo", "ct_hi", "cw_lo", "cw_hi",
    # ---- per-strike state flags (added 2026-07-25) ----
    # revflag = Level Engine AN (reversal), ax_vomma = AX (vomma/fragile trigger),
    # ay_accel = AY (accelerant), dt_nvanna = DT (near-field vanna cluster). These drive the CU/BT qualification gates; without
    # them archived, "why was this level not listed" is unanswerable after the fact.
    "revflag", "ax_vomma", "ay_accel", "dt_nvanna",
    "event",
]
# ------------------

SQRT2PI = math.sqrt(2 * math.pi)
def npdf(x): return math.exp(-0.5 * x * x) / SQRT2PI
def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def greeks(S, K, T, sigma, right, r=RATE, q=DIV):
    if T <= 0 or sigma <= 0 or S <= 0:
        return None
    srt = sigma * math.sqrt(T)
    d1  = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / srt
    d2  = d1 - srt
    pdf = npdf(d1); dq = math.exp(-q * T)
    gamma = dq * pdf / (S * srt)
    vega  = S * dq * pdf * math.sqrt(T)
    vanna = -dq * pdf * d2 / sigma
    vomma = vega * d1 * d2 / sigma
    zomma = gamma * (d1 * d2 - 1) / sigma
    speed = -gamma / S * (d1 / srt + 1)
    delta = dq * ncdf(d1) if right == 'C' else -dq * ncdf(-d1)
    charm_common = dq * pdf * (2 * (r - q) * T - d2 * srt) / (2 * T * srt)
    charm = (q * dq * ncdf(d1) - charm_common) if right == 'C' else (-q * dq * ncdf(-d1) - charm_common)
    return dict(delta=delta, gamma=gamma, vega=vega, vanna=vanna,
                vomma=vomma, zomma=zomma, speed=speed, charm=charm)


def best_price(t):
    v = t.last
    if v is not None and not math.isnan(v):
        return v
    mp = t.marketPrice()
    if mp is not None and not math.isnan(mp) and not (t.close is not None and mp == t.close):
        return mp
    return math.nan


def get_ticker(ib, contract, wait_seconds=20):
    ib.qualifyContracts(contract)
    t = ib.reqMktData(contract)
    for _ in range(wait_seconds * 2):
        ib.sleep(0.5)
        if not math.isnan(best_price(t)):
            break
    return t


def oi(x):
    return x if (x is not None and not math.isnan(x) and x > 0) else 0


def has_greeks(t):
    g = t.modelGreeks
    return bool(g and g.impliedVol and not math.isnan(g.impliedVol))


def iv_of(t):
    """Implied vol off a ticker, or "" if the feed has not populated it.
       Mirrors oi(): never raises, never returns NaN. Archive-only helper --
       nothing in the Greek path calls this."""
    try:
        g = t.modelGreeks
        if g and g.impliedVol and not math.isnan(g.impliedVol) and g.impliedVol > 0:
            return g.impliedVol
    except Exception:
        pass
    return ""


def market_open():
    now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)
    if now.weekday() >= 5:
        return False
    return (now.hour, now.minute) >= (9, 30) and (now.hour, now.minute) <= (16, 0)


# ---- archive snapshot ----
_next_event = ""   # one-shot marker ("RECONNECT") stamped on the next archived cycle
_last_arch_spot = None   # last archived spot, reference for the single-cycle SPIKE? flag

_ARCH_ROLL_WARNED = {}      # path -> True, so the roll notice prints once, not every cycle


def archive_snapshot(ts, spot, vix, vvix, vix1d, flags_row, charm_flag, locked_R, locked_S, table_rows,
                     qual_by_strike=None, raw_by_strike=None, es_sma200=None, es_sma400=None,
                     put_skew=None, call_skew=None, risk_rev=None,
                     atm_iv=None, atm_iv_dir=None,
                     ct_lo=None, ct_hi=None, cw_lo=None, cw_hi=None,
                     state_by_strike=None):
    """Append one completed cycle to today's CSV in ARCHIVE_DIR (one row per strike).
       Cycle-level fields are repeated on every strike row so each snapshot is
       fully self-contained. Failure here never interrupts the live loop."""
    global _next_event, _last_arch_spot
    def lvl(lst, i):
        return lst[i] if i < len(lst) else ""

    meta = ([ts, spot, vix, vvix, vix1d] + list(flags_row) + [charm_flag] +
            [lvl(locked_R, i) for i in range(6)] +
            [lvl(locked_S, i) for i in range(6)])
    event = _next_event
    _next_event = ""
    # ---- single-cycle spot-spike flag (one-sided breadcrumb, not a fix) ----
    # If spot jumps more than SPIKE_PTS from the last archived cycle and this cycle
    # is not already a RECENTER/RECONNECT marker, tag event="SPIKE?" so a backtest
    # can find suspect prints instantly. The written spot is NOT changed; the
    # two-sided despike in the backtest makes the final isolated-vs-real call.
    _spot_ok = isinstance(spot, (int, float)) and not (isinstance(spot, float) and math.isnan(spot))
    if _spot_ok:
        if not event and _last_arch_spot is not None and abs(spot - _last_arch_spot) > SPIKE_PTS:
            event = "SPIKE?"
        _last_arch_spot = spot
    try:
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        path = os.path.join(ARCHIVE_DIR, f"king_node_archive_{ts[:10]}.csv")
        # ---- on-disk header check ----------------------------------------------
        # The arity guard below only compares _out to ARCHIVE_HEADER, both in memory.
        # It cannot see the header already on disk. If the schema has changed since this
        # day's file was opened (a column added), appending would silently produce a
        # ragged CSV. So: read the real header. If it does not match, roll to __v2 (then
        # __v3, ...) and say so loudly. The old file is left untouched and the engine
        # keeps running -- never corrupt data, never stop trading mid-session.
        if os.path.exists(path):
            try:
                with open(path, "r", newline="") as _f:
                    _disk = next(csv.reader(_f), [])
            except Exception:
                _disk = []
            if _disk and _disk != list(ARCHIVE_HEADER):
                _n = 2
                while True:
                    _alt = os.path.join(ARCHIVE_DIR,
                                        f"king_node_archive_{ts[:10]}__v{_n}.csv")
                    if not os.path.exists(_alt):
                        break
                    try:
                        with open(_alt, "r", newline="") as _f:
                            if next(csv.reader(_f), []) == list(ARCHIVE_HEADER):
                                break          # an existing roll already matches -> use it
                    except Exception:
                        pass
                    _n += 1
                if not _ARCH_ROLL_WARNED.get(path):
                    print("   ! ARCHIVE SCHEMA CHANGED "
                          f"({len(_disk)} cols on disk vs {len(ARCHIVE_HEADER)} in code)")
                    print(f"   ! rolling to {os.path.basename(_alt)} — "
                          f"{os.path.basename(path)} left intact")
                    _ARCH_ROLL_WARNED[path] = True
                path = _alt
        new_file = not os.path.exists(path)
        with open(path, "a", newline="") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(ARCHIVE_HEADER)
            qmap = qual_by_strike or {}
            rmap = raw_by_strike or {}
            _checked = False
            for idx, row in enumerate(table_rows):
                # row = [strike, gamma, gex, zomma, dex, vex, vomma, vega, speed]
                _k = round(row[0]) if isinstance(row[0], (int, float)) else row[0]
                (_confl, _absg, _ar, _rk,
                 _cu, _cv, _bk, _dh, _dc, _cz) = qmap.get(
                     _k, ("", "", "", "", "", "", "", "", "", ""))
                _civ, _piv, _coi, _poi = rmap.get(_k, ("", "", "", ""))
                _sv = (state_by_strike or {}).get(round(float(row[0])), (None, None, None, None))
                _out = (meta + [idx] + list(row) +
                        [_confl, _absg, _civ, _piv, _coi, _poi,
                         es_sma200 if es_sma200 is not None else "",
                         es_sma400 if es_sma400 is not None else "",
                         round(put_skew, 2)  if put_skew  is not None else "",
                         round(call_skew, 2) if call_skew is not None else "",
                         round(risk_rev, 2)  if risk_rev  is not None else "",
                         round(atm_iv, 6) if atm_iv is not None else "",
                         atm_iv_dir if atm_iv_dir is not None else "",
                         _ar, _rk,
                         _cu, _cv, _bk, _dh, _dc, _cz,
                         ct_lo if ct_lo is not None else "",
                         ct_hi if ct_hi is not None else "",
                         cw_lo if cw_lo is not None else "",
                         cw_hi if cw_hi is not None else "",
                         _sv[0] if _sv[0] is not None else "",
                         _sv[1] if _sv[1] is not None else "",
                         _sv[2] if _sv[2] is not None else "",
                         _sv[3] if _sv[3] is not None else "",
                         event])
                if not _checked:
                    # Cheap once-per-cycle guard. A column added to ARCHIVE_HEADER without a
                    # matching value here would otherwise shift every later field silently --
                    # the CSV still parses, it is just wrong. Fail loudly instead.
                    if len(_out) != len(ARCHIVE_HEADER):
                        raise ValueError(f"archive row has {len(_out)} fields, "
                                         f"ARCHIVE_HEADER has {len(ARCHIVE_HEADER)}")
                    _checked = True
                w.writerow(_out)
    except Exception as e:
        print(f"   ! archive write failed: {e}")


# ---- level lock (hysteresis) ----
def apply_lock(locked, pend, raw, spot, side):
    """Keep prior levels stable; a challenger must persist LOCK_HOLD cycles to replace one.
       Release immediately when price reaches the primary level (R1/S1)."""
    # price reached the primary level -> re-adopt the fresh raw list at once
    if locked:
        if side == 'R' and spot >= locked[0]:
            return list(raw[:6]), {}
        if side == 'S' and spot <= locked[0]:
            return list(raw[:6]), {}
    if not locked:
        return list(raw[:6]), {}

    new_locked = list(locked)
    n = min(6, max(len(raw), len(locked)))
    for i in range(n):
        raw_i = raw[i] if i < len(raw) else None
        cur   = new_locked[i] if i < len(new_locked) else None
        if raw_i is None:
            continue                      # raw missing here -> keep what's locked
        if raw_i == cur:
            pend.pop(i, None)             # matches -> reset any pending challenge
            continue
        c = pend.get(i)
        if c and c[0] == raw_i:
            c[1] += 1
            if c[1] >= LOCK_HOLD:         # challenger held long enough -> promote
                if i < len(new_locked):
                    new_locked[i] = raw_i
                else:
                    new_locked.append(raw_i)
                pend.pop(i, None)
        else:
            pend[i] = [raw_i, 1]          # new challenger -> start its counter

    # release stale levels: any locked level no longer in the raw top-6 at all
    # (fell off entirely, not merely out-ranked) is replaced immediately by the
    # best available raw level that isn't already locked. Keeps the 3-cycle hold
    # for ordinary re-ordering, but stops dropped-off levels lingering.
    raw_top = [x for x in raw[:6] if x is not None]
    for i in range(len(new_locked)):
        if new_locked[i] is not None and new_locked[i] not in raw_top:
            replacement = next((x for x in raw_top if x not in new_locked), None)
            if replacement is not None:
                new_locked[i] = replacement
                pend.pop(i, None)
    return new_locked, pend


def dedup_levels(locked, raw):
    """Remove duplicate strikes from a locked list, preserving order, then backfill
       from the raw list so the list still holds up to 6 distinct levels."""
    out = []
    for x in locked:
        if x is not None and x not in out:
            out.append(x)
    for x in raw:
        if len(out) >= 6:
            break
        if x is not None and x not in out:
            out.append(x)
    return out


def vomma_status(hist, roll, rise):
    """Classify the near-spot vomma series and emit a LONG or SHORT signal.
    The most recent turning point decides the phase:
      peaked most recently   -> falling phase -> LONG trigger on roll-over (vol exhausting -> bounce, use at VOMMA BID support)
      troughed most recently -> rising  phase -> SHORT trigger on turn-up  (vol re-accelerating -> rejection, use at VOMMA CAP resistance)
    Returns (status_text, signal, ref_value, pct); signal in {'long','short','none'}.
    """
    if len(hist) < 3:
        return 'warming up', 'none', (hist[-1] if hist else 0), 0.0
    peak = max(hist); trough = min(hist); latest = hist[-1]
    peak_idx   = len(hist) - 1 - hist[::-1].index(peak)        # last occurrence of the peak
    trough_idx = len(hist) - 1 - hist[::-1].index(trough)      # last occurrence of the trough
    if peak_idx >= trough_idx:
        # vomma topped most recently -> now falling -> long context
        if peak_idx == len(hist) - 1:
            return 'RISING / AT PEAK', 'none', peak, 0.0
        pct = (peak - latest) / peak if peak > 0 else 0.0
        if pct >= roll:
            return f'ROLLED OVER -{pct*100:.0f}% - LONG trigger', 'long', peak, pct
        return 'peaked - watching', 'none', peak, pct
    else:
        # vomma bottomed most recently -> now rising -> short context
        if trough_idx == len(hist) - 1:
            return 'FALLING / AT TROUGH', 'none', trough, 0.0
        pct = (latest - trough) / trough if trough > 0 else 0.0
        if pct >= rise:
            return f'TURNED UP +{pct*100:.0f}% - SHORT trigger', 'short', trough, pct
        return 'troughed - watching', 'none', trough, pct


# ============================================================================
# ---- ES / Technical-Analysis engine (Stage 1) -----------------------------
# ----------------------------------------------------------------------------
# All time logic is ET wall-clock (EDT, UTC-4) to match the rest of the script.
# NOTE: this is summer (EDT). In winter the offset is UTC-5; the -4 here mirrors
#       the existing market_open() convention and should be changed together with it.

def et_now():
    """Current time as a naive ET (EDT) datetime."""
    return (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(hours=4)).replace(tzinfo=None)


def to_et(t):
    """Coerce an IBKR timestamp (epoch int or tz-aware/naive datetime) to naive ET."""
    if isinstance(t, (int, float)):
        t = datetime.datetime.fromtimestamp(t, datetime.timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return (t.astimezone(datetime.timezone.utc)
            - datetime.timedelta(hours=4)).replace(tzinfo=None)


def mround_tick(x):
    """Round to the nearest ES tick (0.25) for tradeable structural levels."""
    if x is None:
        return None
    return round(x / ES_TICK) * ES_TICK


class ESProfile:
    """Accumulates the ES stream (live ticks + seed bars) into the AMT/TA levels.

    Sessions, in ET:
      * Globex day  : starts 18:00 ET -> daily VWAP + overnight anchor
      * Overnight    : 18:00 ET -> 09:30 ET next day (H/L, freezes at the open)
      * Initial Bal. : 09:30 -> 10:30 ET (H/L, locks + fires the Fib calc at 10:30)
      * RTH profile  : 09:30 -> 16:00 ET (price-binned volume -> POC / VAH / VAL)
      * Week         : starts Sunday 18:00 ET -> weekly VWAP
    """

    def __init__(self):
        self.last = None
        self.day_anchor = None          # datetime: 18:00 ET that opened the current Globex day
        self.wk_anchor = None           # datetime: Sunday 18:00 ET that opened the week
        self.day_pv = 0.0; self.day_v = 0.0
        self.wk_pv = 0.0;  self.wk_v = 0.0
        self.on_hi = None; self.on_lo = None; self.on_locked = False
        self.ib_hi = None; self.ib_lo = None; self.ib_locked = False
        self.ib_mid = None
        self.fib_up = [None, None, None]
        self.fib_dn = [None, None, None]
        self.bins = {}                  # developing RTH profile: {bin_index: volume}

    # -- anchor maths (all on naive ET datetimes) --
    @staticmethod
    def _day_anchor_dt(et):
        cand = et.replace(hour=SESSION_OPEN_ET[0], minute=SESSION_OPEN_ET[1],
                          second=0, microsecond=0)
        if cand > et:                                    # before 18:00 -> session opened yesterday
            cand -= datetime.timedelta(days=1)
        return cand

    @staticmethod
    def _week_anchor_dt(et):
        days_since_sun = (et.weekday() - 6) % 7          # Sun=0, Mon=1, ... Sat=6
        cand = (et - datetime.timedelta(days=days_since_sun)).replace(
            hour=SESSION_OPEN_ET[0], minute=SESSION_OPEN_ET[1], second=0, microsecond=0)
        if cand > et:                                    # before Sun 18:00 -> last week's open
            cand -= datetime.timedelta(days=7)
        return cand

    def _bounds(self):
        """Return (overnight_end / RTH_open, IB_end, RTH_close) for the current day."""
        on_end = (self.day_anchor + datetime.timedelta(days=1)).replace(
            hour=IB_OPEN_ET[0], minute=IB_OPEN_ET[1], second=0, microsecond=0)
        ib_end = on_end + datetime.timedelta(minutes=IB_MINUTES)
        rth_end = on_end.replace(hour=RTH_CLOSE_ET[0], minute=RTH_CLOSE_ET[1])
        return on_end, ib_end, rth_end

    def _roll(self, et):
        """Reset the per-session accumulators when an anchor advances."""
        da = self._day_anchor_dt(et)
        if self.day_anchor != da:
            self.day_anchor = da
            self.day_pv = self.day_v = 0.0
            self.on_hi = self.on_lo = None; self.on_locked = False
            self.ib_hi = self.ib_lo = None; self.ib_locked = False
            self.ib_mid = None
            self.fib_up = [None, None, None]; self.fib_dn = [None, None, None]
            self.bins = {}
        wa = self._week_anchor_dt(et)
        if self.wk_anchor != wa:
            self.wk_anchor = wa
            self.wk_pv = self.wk_v = 0.0

    def _compute_fib(self):
        if self.ib_hi is None or self.ib_lo is None:
            return
        rng = self.ib_hi - self.ib_lo
        self.ib_mid = (self.ib_hi + self.ib_lo) / 2.0
        self.fib_up = [self.ib_hi + m * rng for m in FIB_MULT]   # above IB high  (-0.27 / -0.618 / -1)
        self.fib_dn = [self.ib_lo - m * rng for m in FIB_MULT]   # below IB low   (1.27 / 1.618 / 2)

    # -- ingest one live tick (point price) --
    def add(self, et, price, size):
        if price is None or price <= 0:
            return
        self._roll(et)
        self.last = price
        on_end, ib_end, rth_end = self._bounds()
        self.day_pv += price * size; self.day_v += size
        self.wk_pv += price * size;  self.wk_v += size
        if not self.on_locked:
            if et < on_end:
                self.on_hi = price if self.on_hi is None else max(self.on_hi, price)
                self.on_lo = price if self.on_lo is None else min(self.on_lo, price)
            else:
                self.on_locked = True                    # RTH opened -> overnight H/L freeze
        if on_end <= et < ib_end:
            self.ib_hi = price if self.ib_hi is None else max(self.ib_hi, price)
            self.ib_lo = price if self.ib_lo is None else min(self.ib_lo, price)
        elif et >= ib_end and not self.ib_locked and self.ib_hi is not None:
            self.ib_locked = True; self._compute_fib()   # 10:00 ET -> lock IB, fire Fib
        if on_end <= et < rth_end and size > 0:
            idx = int(round(price / PROFILE_BIN))
            self.bins[idx] = self.bins.get(idx, 0.0) + size

    # -- ingest one seed bar (1-min OHLCV); spreads volume across H..L --
    def add_bar(self, et, o, h, l, c, vol):
        if h is None or l is None:
            return
        self._roll(et)
        self.last = c
        on_end, ib_end, rth_end = self._bounds()
        tp = (h + l + c) / 3.0                            # typical price (TradingView VWAP basis)
        if vol and vol > 0:
            self.day_pv += tp * vol; self.day_v += vol
            self.wk_pv += tp * vol;  self.wk_v += vol
        if not self.on_locked:
            if et < on_end:
                self.on_hi = h if self.on_hi is None else max(self.on_hi, h)
                self.on_lo = l if self.on_lo is None else min(self.on_lo, l)
            else:
                self.on_locked = True
        if on_end <= et < ib_end:
            self.ib_hi = h if self.ib_hi is None else max(self.ib_hi, h)
            self.ib_lo = l if self.ib_lo is None else min(self.ib_lo, l)
        elif et >= ib_end and not self.ib_locked and self.ib_hi is not None:
            self.ib_locked = True; self._compute_fib()
        if on_end <= et < rth_end and vol and vol > 0:
            lo_i = int(round(l / PROFILE_BIN)); hi_i = int(round(h / PROFILE_BIN))
            n = max(1, hi_i - lo_i + 1); share = vol / n
            for i in range(lo_i, hi_i + 1):
                self.bins[i] = self.bins.get(i, 0.0) + share

    # -- derived levels --
    def daily_vwap(self):
        return self.day_pv / self.day_v if self.day_v else None

    def weekly_vwap(self):
        return self.wk_pv / self.wk_v if self.wk_v else None

    def poc_va(self):
        """Point of Control + value-area edges from the developing RTH profile."""
        if not self.bins:
            return None, None, None
        idxs = sorted(self.bins)
        vols = self.bins
        total = sum(vols.values())
        poc_idx = max(vols, key=vols.get)
        p = idxs.index(poc_idx)
        lo = hi = p
        acc = vols[idxs[p]]
        target = total * VALUE_AREA
        while acc < target and (lo > 0 or hi < len(idxs) - 1):
            up_v = vols[idxs[hi + 1]] if hi < len(idxs) - 1 else -1.0
            dn_v = vols[idxs[lo - 1]] if lo > 0 else -1.0
            if up_v >= dn_v:
                hi += 1; acc += vols[idxs[hi]]
            else:
                lo -= 1; acc += vols[idxs[lo]]
        return (poc_idx * PROFILE_BIN, idxs[hi] * PROFILE_BIN, idxs[lo] * PROFILE_BIN)


def ta_write_panel(sht_ta, esp, sma=None):
    """Write the read-only ES reference panel to columns I:K of the TA sheet.
       Labels + statuses are rewritten each cycle so the panel self-builds even
       on a sheet that has never seen it before. Stage-2/3 rows show placeholders.
       The two SMA rows at the bottom are read-only observation, like the rest."""
    if sht_ta is None or esp is None:
        return
    dv = esp.daily_vwap(); wv = esp.weekly_vwap()
    poc, vah, val = esp.poc_va()

    def stat_ib(v):
        return 'locked' if esp.ib_locked else ('forming' if v is not None else '—')

    on_stat = 'settled @open' if esp.on_locked else 'developing'
    fib_stat = 'locked' if esp.ib_locked else '—'
    # (label, value, kind, status)   kind: 'p2'=2dp price line, 'tk'=tick-rounded level
    rows = [
        ('Live ES (last)',  esp.last,      'p2', 'live'),
        ('Daily VWAP',      dv,            'p2', 'developing'),
        ('Weekly VWAP',     wv,            'p2', 'developing'),
        ('Overnight High',  esp.on_hi,     'tk', on_stat),
        ('Overnight Low',   esp.on_lo,     'tk', on_stat),
        ('IB High',         esp.ib_hi,     'tk', stat_ib(esp.ib_hi)),
        ('IB Low',          esp.ib_lo,     'tk', stat_ib(esp.ib_lo)),
        ('IB Mid',          esp.ib_mid,    'tk', stat_ib(esp.ib_mid)),
        ('Fib up -0.27',    esp.fib_up[0], 'tk', fib_stat),
        ('Fib up -0.618',   esp.fib_up[1], 'tk', fib_stat),
        ('Fib up -1.0',     esp.fib_up[2], 'tk', fib_stat),
        ('Fib dn 1.27',     esp.fib_dn[0], 'tk', fib_stat),
        ('Fib dn 1.618',    esp.fib_dn[1], 'tk', fib_stat),
        ('Fib dn 2.0',      esp.fib_dn[2], 'tk', fib_stat),
        ('POC (dev)',       poc,           'tk', 'developing'),
        ('VAH (dev)',       vah,           'tk', 'developing'),
        ('VAL (dev)',       val,           'tk', 'developing'),
        ('Prior POC',       None,          'tk', 'Stage 1b'),
        ('Prior VAH',       None,          'tk', 'Stage 1b'),
        ('Prior VAL',       None,          'tk', 'Stage 1b'),
        ('Balance flag',    None,          'tx', 'Stage 3'),
        ('HVN',             None,          'tk', 'Stage 3'),
        ('LVN',             None,          'tk', 'Stage 3'),
    ]

    # ---- ES 5-min moving averages ----
    _s200 = _s400 = None
    if sma is not None:
        _s200, _s400 = sma.levels()

    def _sma_stat(v):
        if v is None:
            return f'filling ({sma.bars_held() if sma else 0} bars)'
        if not isinstance(esp.last, (int, float)):
            return f'{SMA_BAR_MIN}m bars'
        d = esp.last - v
        return f"ES {'above' if d >= 0 else 'below'} by {abs(d):,.2f}"

    rows += [
        (f'ES SMA{SMA_PERIODS[0]} ({SMA_BAR_MIN}m)', _s200, 'p2', _sma_stat(_s200)),
        (f'ES SMA{SMA_PERIODS[1]} ({SMA_BAR_MIN}m)', _s400, 'p2', _sma_stat(_s400)),
    ]

    block = [['LIVE TA REFERENCE (ES)', '', 'upd ' + et_now().strftime('%H:%M:%S')]]
    for label, v, kind, status in rows:
        if v is None:
            out = '—'
        elif kind == 'p2':
            out = round(v, 2)
        else:
            out = mround_tick(v)
        block.append([label, out, status])
    try:
        sht_ta.range((TA_PANEL_ROW, TA_PANEL_COL)).value = block
    except Exception as e:
        print(f"   ! TA panel write failed: {e}")


class ESSma:
    """200 / 400-period simple moving averages on 5-minute ES bars.

       Holds a rolling window of CLOSED 5-min bar closes plus the forming bar's
       running last. The SMA is therefore (N-1 closed closes + live price) / N --
       exactly what a chart shows, moving tick by tick within the forming bar and
       stepping when the bar closes.

       Bars are bucketed on ET wall-clock (:00, :05, :10 ...). update() is
       idempotent and safe to call from both the tick handler and the 30s cycle;
       whichever fires first advances the bucket. Never raises."""

    def __init__(self, periods=SMA_PERIODS, bar_min=SMA_BAR_MIN):
        self.periods = tuple(periods)
        self.m = bar_min
        self.closes = deque(maxlen=max(self.periods) + 10)   # closed 5-min closes, oldest -> newest
        self.cur_bucket = None      # ET datetime of the forming bar
        self.cur_last = None        # running last trade inside the forming bar
        self.seeded = False

    def _bucket(self, et):
        return et.replace(minute=(et.minute // self.m) * self.m, second=0, microsecond=0)

    def seed(self, bars, now_et):
        """Load historical 5-min bars, oldest -> newest. Any bar in the CURRENT bucket
           is treated as the forming bar rather than a close, so nothing double-counts
           when live ticks take over."""
        now_b = self._bucket(now_et)
        for b in bars:
            try:
                c = float(b.close)
                if math.isnan(c):
                    continue
            except Exception:
                continue
            bb = self._bucket(to_et(b.date))
            if bb < now_b:
                self.closes.append(c)
            else:
                self.cur_bucket, self.cur_last = now_b, c
        if self.cur_bucket is None:
            self.cur_bucket = now_b
        self.seeded = True
        return len(self.closes)

    def update(self, et, price):
        """Fold one trade (or one cycle's last) into the forming bar; roll on boundary."""
        if price is None:
            return
        try:
            p = float(price)
            if math.isnan(p) or p <= 0:
                return
        except Exception:
            return
        b = self._bucket(et)
        if self.cur_bucket is None:
            self.cur_bucket, self.cur_last = b, p
            return
        if b > self.cur_bucket:
            if self.cur_last is not None:
                self.closes.append(self.cur_last)      # the bar that just closed
            self.cur_bucket = b
        self.cur_last = p

    def sma(self, n):
        """SMA over n bars, or None until there is enough history."""
        if self.cur_last is None or len(self.closes) < n - 1:
            return None
        window = list(self.closes)[-(n - 1):] + [self.cur_last]
        return round(sum(window) / n, 2)

    def levels(self):
        return self.sma(self.periods[0]), self.sma(self.periods[1])

    def bars_held(self):
        return len(self.closes)


_es_sma = ESSma() if (TA_ENABLED and SMA_ENABLED) else None


def on_es_tick(ticker):
    """Tick-by-tick AllLast handler: fold each trade into the ES profile.
       Fires during ib.sleep() in the main loop; refresh() snapshots the result."""
    for tb in list(ticker.tickByTicks):
        try:
            _es_profile.add(to_et(tb.time), float(tb.price), float(tb.size or 0))
        except Exception:
            pass
        if _es_sma is not None:
            try:
                _es_sma.update(to_et(tb.time), float(tb.price))
            except Exception:
                pass
    ticker.tickByTicks.clear()


_es_profile = ESProfile() if TA_ENABLED else None
_es_contract = None
_sht_ta = None

_locked_R, _locked_S = [], []
_pend_R, _pend_S = {}, {}

# ---- Net GEX intraday monitor (slope + flip + vol-bid tension) ----
# Tracks whole-book Net GEX across the session so the dashboard can show its
# TRAJECTORY, not just its current level. Motivated by the 2026-06-29 review:
# Net GEX going -3.2M -> +8.1M while VIX1D bid and VVIX faded was the mechanism
# behind the melt-up, but it was invisible in real time from the level alone.
#   #1 slope : trailing change over GEX_SLOPE_WIN cycles, normalised per 15 min
#   #2 flip  : sign-cross of Net GEX + minutes since it happened
#   #3 flag  : neutral heads-up when GEX rising + VIX1D up + VVIX not up co-occur
#              (OBSERVATION ONLY -- the archive showed this does NOT predict
#               direction: it fired on both the 06-29 melt-up and the 06-25 bear
#               grind. It flags the tension is present; direction is read off the
#               regime/phenomenon as always.)
GEX_SLOPE_WIN = 90        # cycles in the slope window (~45 min at 30s refresh)

# ---- VIX1D session extremes (VOL BOTTOM / VOL TOP flags -> KNM AB13 / AB14) ----
# VOL BOTTOM: VIX1D >= +10% off its running session low AND still bidding (dir Up).
# VOL TOP: the high must itself be a confirmed bid (>= +10% above the low that
# preceded it -- suppresses the mechanical morning decay off the opening print),
# then VIX1D >= 10% off that high AND fading (dir Down). Both validated on the
# 11-day archive (naive -10%-off-high fired at the open on 7 of 11 days; the
# prominence gate fired 0 times on decay/grind days, 4/4 on genuine topped bids).
# OBSERVATION ONLY -- the 11-day test showed vol turning points do NOT give a
# directional lean (bottoms preceded spot DOWN 10/11, tops spot UP 9/11);
# direction is read off the pin/regime as always.
VOLB_PCT  = 10.0          # %% off running low to flag VOL BOTTOM
VOLT_PCT  = 10.0          # %% fade off the high to flag VOL TOP
VOLT_PROM = 10.0          # the high must be >= this %% above the prior low (a real bid)
_v1d_lo = _v1d_hi = None  # running session extremes
_v1d_lo_t = _v1d_hi_t = ""
_v1d_hi_prom = 0.0        # how much of a bid built the current high (%% above prior low)
GEX_SEED_HISTORY = True   # rebuild the buffer from today's archive CSV at startup
_gex_hist   = deque(maxlen=GEX_SLOPE_WIN + 1)   # (epoch_secs, net_gex) per cycle
_gex_open5  = None        # NET GEX at RTH open+5 (09:35 ET); baseline for the Master 'vs open+5' readout
_gex_sign   = 0           # last committed sign: +1 pos, -1 neg, 0 unset
_gex_per15  = None        # published slope, net GEX change per 15 min (None until the window fills)
_gex_flip_t = None        # epoch secs of the most recent sign flip (None = none yet)

# resistance-warning hysteresis (amber/watch border hold) — state persists across cycles
_warn_tier  = 0           # latched tier: 0 off, 1 WATCH, 2 AMBER/CONFIRMED
_warn_below = 0           # consecutive cycles the drivers have sat below the latched tier

# neg-γ UNSAFE per-row raspberry hysteresis (6 reaction rows: R1-R3, S1-S3) — state persists across cycles
_negg_active = [False] * 6
_negg_below  = [0] * 6

# ---- shelf/wall hysteresis lock ----
# The CM/CN detector recomputes a fresh shelf/wall each cycle; this damps the
# flicker the same way apply_lock damps R/S levels. A new, changed, or vanished
# shelf/wall must persist SW_LOCK_HOLD cycles in a row before the locked copy
# (CT/CW on the Level Engine, which the table, column R and the Q/A band now read)
# is allowed to change.
SW_LOCK_HOLD = 3
_swR_lock = None; _swR_pend = None     # (edge, far, type) tuple or None ; (challenger, count) or None
_swS_lock = None; _swS_pend = None

def apply_sw_lock(locked, pend, raw):
    """raw/locked: (edge, far, type) tuple or None. A change only takes effect once
       a challenger has held SW_LOCK_HOLD cycles in a row; otherwise the lock holds."""
    if raw == locked:
        return locked, None                 # unchanged -> clear any pending challenge
    if pend is not None and pend[0] == raw:
        n = pend[1] + 1
        if n >= SW_LOCK_HOLD:
            return raw, None                # challenger held long enough -> adopt
        return locked, (raw, n)
    return locked, (raw, 1)                  # new challenger -> start its counter


# ---- Net GEX intraday monitor ----
# Folds the current whole-book Net GEX into the rolling history, then returns one
# formatted summary line for the dashboard: normalised 45-min slope, sign-flip +
# age, and (observation-only) a vol-bid tension flag. Never a trade trigger.
def gex_monitor(net_gex, now_secs, vix1d_up, vvix_up):
    """net_gex   : current whole-book Net GEX (sum of per-strike GEX)
       now_secs  : time.time() epoch seconds for this cycle
       vix1d_up  : bool, Front-End Bidding active (King Node Model P6 == 'Up')
       vvix_up   : bool, VVIX rising (King Node Model P5 == 'Up')
       Returns a display string, e.g.
         'GEX SLOPE  ▲ +3.8M/15m  ·  flipped POS 43m ago  ·  ⚠ vol-bid tension' """
    global _gex_sign, _gex_flip_t, _gex_per15
    _gex_hist.append((now_secs, net_gex))

    # --- #2 flip: commit sign, stamp the cross ---
    cur_sign = 1 if net_gex > 0 else (-1 if net_gex < 0 else _gex_sign)
    if cur_sign != 0 and cur_sign != _gex_sign:
        if _gex_sign != 0:                      # a genuine cross (not the first read)
            _gex_flip_t = now_secs
        _gex_sign = cur_sign

    # --- #1 slope: change over the window, normalised to per-15-min ---
    slope_txt = "GEX SLOPE  … building"
    rising = False
    if len(_gex_hist) >= 2:
        t0, g0 = _gex_hist[0]
        dt_min = max((now_secs - t0) / 60.0, 0.5)     # elapsed minutes in the buffer
        dgex   = net_gex - g0
        per15  = dgex / dt_min * 15.0                  # normalised change / 15 min
        rising = per15 > 0
        _gex_per15 = per15                        # published for vol_tension(); None = still building
        arrow  = "▲" if per15 > 0 else ("▼" if per15 < 0 else "▬")
        slope_txt = f"GEX SLOPE  {arrow} {per15/1e6:+.1f}M/15m"

    # --- #2 flip text ---
    if _gex_flip_t is not None:
        mins = int((now_secs - _gex_flip_t) / 60)
        flip_txt = f"flipped {'POS' if _gex_sign > 0 else 'NEG'} {mins}m ago"
    else:
        flip_txt = f"{'POS' if _gex_sign > 0 else 'NEG'} held all session" if _gex_sign else "—"

    # --- #3 vol-bid tension flag (observation only; no direction implied) ---
    line = f"{slope_txt}  ·  {flip_txt}"
    if rising and vix1d_up and not vvix_up:
        line += "  ·  ⚠ vol-bid tension"
    return line


# ---- Vol Tension (Master Dashboard line 18, via King Node Model AB17) ----
# Combines the two readings that routinely disagree -- the FRONT-END vol bid (VIX1D/VIX
# ratio + direction) and the BROADER SURFACE (put/call skew shape) -- with the gamma
# regime and the pace of its drift, and resolves them to one phenomenon label.
#
# The divergence is the normal state, not a fault: VIX1D can spike on a single near-term
# hedge while the whole skew surface relaxes. Reading them side by side asks the trader to
# arbitrate every cycle. This line does the arbitration and states what to EXPECT.
#
# OBSERVATION ONLY -- never a trade trigger, and never gates any other cell. It is a
# summary of readings the dashboard already shows, so it can add no information the
# engine did not already have.
#
# PACE IS NORMALISED, NOT ABSOLUTE. 0.2M/15m on a 17M book and 0.2M/15m on a 4M book are
# different animals, so pace is |slope| as a percentage of |Net GEX|. The three bands
# below are UNCALIBRATED starting values chosen to put 2026-07-23 (~1.2%/15m) in SLOW.
# They are display thresholds only; calibrate on the archive before reading anything
# into the ACCELERATING label specifically.
VT_SLOW_PCT  = 1.5     # < this = SLOW      (% of |Net GEX| per 15 min)
VT_FAST_PCT  = 4.0     # > this = FAST
VT_FLIP_MIN  = 30      # a sign flip this recent outranks every other label
VT_SHOCK_RAT = 0.90    # VIX1D/VIX at or above this, with a steep put skew, = dislocation
VT_MAXLEN    = 133     # F18 spills F->N = 133.8 chars; past N it escapes the box wall


def vol_tension(net_gex, ratio, v1d_up):
    """net_gex : whole-book Net GEX this cycle
       ratio   : VIX1D / VIX  (None if either leg is missing)
       v1d_up  : bool, VIX1D direction is Up (King Node Model P6)
       Returns 'VOL TENSION  LABEL  -  condition  -  expect', or a building//no-data line.
       Never raises: every unreadable input degrades the line rather than the label."""
    try:
        if not net_gex:
            return "VOL TENSION  \u2026 no Net GEX this cycle"
        if _gex_per15 is None:
            return "VOL TENSION  \u2026 building (slope window not full)"

        neg   = net_gex < 0
        pace  = abs(_gex_per15) / abs(net_gex) * 100.0
        band  = "SLOW" if pace < VT_SLOW_PCT else ("FAST" if pace > VT_FAST_PCT else "MOD")
        # deepening = the book is moving FURTHER into its current regime
        deepening = (_gex_per15 < 0) if neg else (_gex_per15 > 0)

        bid   = bool(v1d_up) or (ratio is not None and ratio > 0.75)
        steep = bool(_skew_state.get("steep"))
        ps_up = _skew_state.get("ps_dir") == "Up"
        ps_dn = _skew_state.get("ps_dir") == "Down"

        flip_age = None
        if _gex_flip_t is not None:
            flip_age = (time.time() - _gex_flip_t) / 60.0

        # ---- label: first match wins, most disruptive first ----
        if flip_age is not None and flip_age <= VT_FLIP_MIN:
            label  = "REGIME FLIP"
            expect = "levels not re-anchored \u2014 stand down"
        elif ratio is not None and ratio >= VT_SHOCK_RAT and steep:
            label  = "VOL SHOCK"
            expect = "levels unreliable \u2014 size down"
        elif neg and deepening and band == "FAST" and (bid or ps_up):
            label  = "ACCELERATING NEG GAMMA"
            expect = "trend day, cascade risk \u2014 do not fade"
        elif neg and not deepening and band != "SLOW":
            label  = "NEG GAMMA UNWINDING"
            expect = "supports firming \u2014 bounces carry"
        elif neg:
            label  = "SLOW NEG GAMMA"
            expect = "amplified, no cascade fuel \u2014 fade extremes"
        elif deepening and band != "SLOW":
            label  = "POS GAMMA BUILDING"
            expect = "resistance leaks \u2014 dips shallow"
        elif not deepening and band != "SLOW" and bid:
            label  = "POS GAMMA ERODING"
            expect = "pin decaying \u2014 breakout risk"
        else:
            label  = "SLOW POS GAMMA"
            expect = "levels hold \u2014 mean reversion"

        # ---- condition: the readings that produced the label ----
        # Budget: F18 spills F->N, which is 133.8 chars wide at the sheet font. Past N the
        # text escapes the readout box's right wall, so the line is built to fit and hard
        # capped at VT_MAXLEN rather than trimmed at the old 155 (which truncated the
        # `expect` clause -- the one part of the line that is actually actionable).
        cond = [f"{net_gex/1e6:+.1f}M",
                f"{'deepening' if deepening else 'easing'} "
                + (f"{pace:.1f}%/15m" if pace < 99.9 else ">99%/15m"),
                f"{'bid' if bid else 'quiet'}" + (f" {ratio:.2f}" if ratio is not None else ""),
                "skew " + ("steep" if steep else
                           "steepening" if ps_up else
                           "easing" if ps_dn else "neutral")]
        # LABEL and EXPECT are never sacrificed to length. If the line does not fit,
        # shed CONDITION items from the right (skew, then the ratio, then pace) -- they
        # are all readable elsewhere on the dashboard, whereas `expect` is the only part
        # of this row that says what to do, and the old fixed [:155] trim ate exactly that.
        def _fmt(items):
            return (f"VOL TENSION  {label}  \u00b7  " + " \u00b7 ".join(items)
                    + f"  \u00b7  {expect}") if items else \
                   f"VOL TENSION  {label}  \u00b7  {expect}"
        line = _fmt(cond)
        while len(line) > VT_MAXLEN and cond:
            cond.pop()
            line = _fmt(cond)
        return line[:VT_MAXLEN]
    except Exception as e:
        return f"VOL TENSION  \u2014 error ({e})"[:155]


def seed_gex_history():
    """Rebuild the Net GEX buffer + flip state from today's archive CSV at startup,
       the same way the ES panel seeds from history. Without this, after a restart or
       recentre the monitor shows '… building' until ~45 min of live cycles re-accumulate.

       Reads today's king_node_archive_<date>.csv, sums per-strike GEX within each
       timestamp to get that cycle's whole-book Net GEX, keeps the last GEX_SLOPE_WIN+1
       cycles, and replays them through the same sign-flip logic so the flip timestamp
       and slope are correct on the very first live cycle. Failure never blocks startup;
       the monitor just falls back to accumulating live."""
    global _gex_sign, _gex_flip_t
    path = os.path.join(ARCHIVE_DIR, f"king_node_archive_{datetime.date.today():%Y-%m-%d}.csv")
    if not os.path.exists(path):
        return 0
    # collapse to one Net GEX per timestamp, in file order (+ any event marker on that cycle)
    per_cycle = {}       # ts_str -> summed gex
    events    = {}       # ts_str -> event marker ("RECENTER"/"RECONNECT") if stamped
    v1d_by_ts = {}       # ts_str -> vix1d (for reseeding the session extremes)
    order = []           # ts_str in first-seen order
    try:
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                ts = row.get("timestamp"); g = row.get("gex")
                if not ts or g in (None, ""):
                    continue
                try:
                    gv = float(g)
                except ValueError:
                    continue
                if ts not in per_cycle:
                    per_cycle[ts] = 0.0; order.append(ts)
                per_cycle[ts] += gv
                ev = (row.get("event") or "").strip()
                if ev:
                    events[ts] = ev
                v1 = row.get("vix1d")
                if ts not in v1d_by_ts and v1 not in (None, ""):
                    try:
                        v1d_by_ts[ts] = float(v1)
                    except ValueError:
                        pass
    except Exception as e:
        print(f"   ! GEX history seed read failed ({e}); will accumulate live only")
        return 0

    # Replay the whole day: sign/flip track every cycle (they persist across window
    # changes, exactly like live), while the slope deque clears at every
    # RECENTER/RECONNECT marker so it never spans a strike-window jump. The deque's
    # maxlen keeps only the last GEX_SLOPE_WIN+1 cycles regardless.
    seeded = 0
    for ts in order:
        try:
            secs = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            continue
        if ts in events:
            _gex_hist.clear()                  # new strike window starts at this cycle
        ng = round(per_cycle[ts])
        _gex_hist.append((secs, ng))
        cur = 1 if ng > 0 else (-1 if ng < 0 else _gex_sign)
        if cur != 0 and cur != _gex_sign:
            if _gex_sign != 0:
                _gex_flip_t = secs
            _gex_sign = cur
        seeded += 1

    # replay the VIX1D session extremes so VOL BOTTOM / VOL TOP survive a restart
    global _v1d_lo, _v1d_hi, _v1d_lo_t, _v1d_hi_t, _v1d_hi_prom
    for ts in order:
        v1 = v1d_by_ts.get(ts)
        if v1 is None:
            continue
        hm = ts[11:16]
        if _v1d_lo is None or v1 < _v1d_lo:
            _v1d_lo, _v1d_lo_t = v1, hm
        if _v1d_hi is None or v1 > _v1d_hi:
            _v1d_hi, _v1d_hi_t = v1, hm
            _v1d_hi_prom = (_v1d_hi - _v1d_lo) / _v1d_lo * 100 if _v1d_lo else 0.0

    # ---- NET GEX at RTH open+5 (09:35 ET) -> restart-robust baseline (King Node Model AB15) ----
    global _gex_open5
    _off = datetime.datetime.now() - et_now()          # local clock minus ET, maps archive ts -> ET
    for ts in order:
        try:
            _et = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") - _off
        except ValueError:
            continue
        if (_et.hour, _et.minute) >= (9, 35) and _et.hour < 16:
            _gex_open5 = round(per_cycle[ts]); break
    return len(_gex_hist)


# ---- resistance-warning hysteresis (amber/watch border hold) ----
# State (tier latch + counter) lives here, not in the sheet, because a CF rule can't
# count cycles. Reads its hold count from the Level Engine (CT12); writes a 0/1/2
# tier to CT14 that F16 and the Master AM32 border resolver read:
#   2 = AMBER / CONFIRMED  (VIX1D rising AND VVIX confirms)
#   1 = WATCH              (VIX1D rising, VVIX not confirming - likely noise)
#   0 = off
def apply_warn_hysteresis(vix1d_up, vvix_up, hold):
    """Tier for the Front-End Bidding border. Latches at the highest tier reached;
       when the drivers drop below the latched tier, holds `hold` cycles before
       decaying to the current level, so AMBER doesn't flicker to WATCH on a single
       soft VVIX print. A re-trigger during the hold resets the counter."""
    global _warn_tier, _warn_below
    cur = 2 if (vix1d_up and vvix_up) else (1 if vix1d_up else 0)
    if cur >= _warn_tier:
        _warn_tier = cur; _warn_below = 0      # at/above latched tier -> follow, reset hold
    else:                                       # drivers dropped below the latched tier
        _warn_below += 1
        if _warn_below >= hold:                 # held long enough -> decay to current
            _warn_tier = cur; _warn_below = 0
    return _warn_tier


# ---- roll+reclaim observation marker (data-accumulation only; NOT a trade trigger) ----
# Lights a one-shot 0/1 flag at Level Engine!CT26 when price RECLAIMS a broken support
# AND vix1d/vix has rolled off a recent peak. Latches OBS_HOLD cycles so the blue
# 'observe' border on the Next Support rows stays visible. State lives here because a CF
# rule can't remember broken levels or prior vol direction. Logic matches roll_reclaim.py:
# breaks are judged on the PRIOR cycle's support list (a level can drop off the list the
# instant price pierces it), and a reclaim must hold OBS_CONFIRM cycles above the level.
OBS_BRK = 3            # pts below a locked support to count it broken
OBS_RCL = 1           # pts back above to count a reclaim
OBS_CONFIRM = 2       # consecutive cycles above the level to confirm a reclaim
OBS_HOLD = 6          # cycles to hold the blue observe border on
OBS_ROLL_WIN = 6      # vix1d/vix history depth for peak-and-roll
_obs_broken = {}      # support level -> True once spot traded <= K-OBS_BRK
_obs_armed  = True    # one-shot gate; re-arms when a NEW lower support breaks
_obs_latch  = 0       # blue-border display latch (cycles remaining)
_obs_ratio  = deque(maxlen=OBS_ROLL_WIN + 2)   # recent vix1d/vix readings

# ---- VIX / VVIX direction engine (regime IV classifier: Coiled Spring High/Low) ----
# Two-half mean comparison over a rolling window: mean(recent half) vs mean(older half).
# Robust to single-print spikes. Direction feeds King Node Model P4 (VIX) / P5 (VVIX),
# which drive the Coiled Spring High/Low/MIXED read on dashboard line 5.
IVDIR_WIN      = 50        # rolling window in cycles (~25 min at 30s) -- adjustable dial
IVDIR_DB_VIX   = 0.10      # deadband (vol pts): move must exceed this or reads "Flat"
IVDIR_DB_VVIX  = 0.25      # VVIX is noisier -> wider deadband
IVDIR_DB_V1D   = 0.10      # VIX1D deadband (same scale as VIX)

# ---- SKEW MONITOR (observation only) ----------------------------------------
# Shape of the 0DTE IV curve, read straight off the raw per-leg IVs the chain
# already gives us. Nothing here touches the Greek math -- greeks() still feeds the
# CALL's IV into both legs (line ~1626), unchanged. This reads call IV and put IV
# independently and only DESCRIBES the curve.
#
#   PUT SKEW  (PS) = IV_put(spot - OFF)  - IV_atm     > 0 = puts bid over ATM (normal SPX)
#   CALL SKEW (CS) = IV_call(spot + OFF) - IV_atm     > 0 = calls bid over ATM (speculative)
#   RISK REV  (RR) = CS - PS                          the single headline number
#
# A 5%-OTM put does not exist in any tradeable sense at 0DTE, so the offset is in
# POINTS, not percent. 25pt default (~0.33% at SPX 7550) sits in the liquid band.
# Direction uses the same two-half deadband engine as VIX/VVIX/VIX1D (P4/P5/P6).
#
# OBSERVATION ONLY. Not wired to confluence, the reaction table, or any signal.
# The interpretive text is conventional market reasoning and is NOT validated on
# this project's archive -- the skew study was never run. Read it as description.
SKEW_ENABLED   = True
SKEW_OFF       = 25.0      # pts either side of spot for the skew wings
SKEW_WIN       = 50        # rolling window in cycles (~25 min at 30s)
SKEW_DB        = 0.10      # deadband in VOL POINTS (measured |two-half diff| median ~0.20vp)
SKEW_STEEP_PCT = 0.66      # PS in the top third of today's range = "steep"

# ---- TIME-OF-DAY BASELINE  (REQUIRED before the interpretive states will show) ----
# MEASURED, Jan 2 0DTE chain:
#     corr(put skew,  minutes-to-expiry) = -0.79
#     corr(call skew, minutes-to-expiry) = -0.91
#     corr(risk rev,  minutes-to-expiry) = -0.68
# The whole smile blows out mechanically as T->0 (ATM IV collapses faster than the
# wings). RR does NOT cancel it -- the wings move by different amounts. So the RAW
# direction of any skew measure is dominated by the CLOCK, not by demand. This is the
# same time-decay artifact that makes zomma useless, and a naive skew monitor walks
# straight into it: on Jan 2 "RISING CALL SKEW" would have been lit 71% of the session.
#
# SKEW_BASE maps ET half-hour -> expected (put_skew, call_skew) in vol points. The
# monitor subtracts it and reads the direction of the RESIDUAL. Populate it by running
# calibrate_skew.py over the parquet archive (a one-off calibration, not a study).
#
# While it is empty the LEVELS and ARROWS still display -- they are honest raw readings
# -- but the interpretive states are SUPPRESSED, because uncalibrated they would be
# reporting time-to-expiry dressed up as market sentiment.
SKEW_BASE      = {"09:30": (2.15, -1.58), "10:00": (2.21, -1.41), "10:30": (2.29, -1.29), "11:00": (2.48, -1.23), "11:30": (2.48, -1.11), "12:00": (2.66, -0.85), "12:30": (2.85, -0.62), "13:00": (3.01, -0.30), "13:30": (3.26, 0.32), "14:00": (3.77, 0.78), "14:30": (4.46, 1.45), "15:00": (4.55, 2.20), "15:30": (4.11, 3.12)}
# ^ calibrated on 116 clean 0DTE sessions (Jan 2 - Jun 18 2026), median per ET half-hour.
#   Interpolated between anchors at runtime; clamped outside 09:30-15:30.
#   Recalibrate if SKEW_OFF changes, or from the live CSVs once enough sessions accumulate.

_ps_hist       = deque(maxlen=SKEW_WIN)
_cs_hist       = deque(maxlen=SKEW_WIN)
_ps_lo = _ps_hi = None     # session extremes for the steep/flat band
_skew_state = {}           # published curve state for vol_tension(); {} = not readable this cycle

_vixdir_hist   = deque(maxlen=IVDIR_WIN)
_vvixdir_hist  = deque(maxlen=IVDIR_WIN)
_v1ddir_hist   = deque(maxlen=IVDIR_WIN)

# ---- ATM IV direction (feeds 'Level Engine'!B3 -> D5) ------------------------
# D5's old auto-fallback read the VIX1D/VIX term-structure LEVEL as if it were a
# direction, so it printed "DOWN" every cycle of every session (VIX1D < VIX is the
# normal state). Measured on 2026-07-13: real direction was Up 46% / Down 43% /
# Flat 11%, i.e. D5 was wrong 57% of the time -- while feeding ~200 cells including
# the level-admission gates (CU9/CV9), the strength score (AR9) and the zomma trend.
#
# The correct driver is the ATM CALL IV: greeks() feeds the call's impliedVol into
# BOTH legs, so that is literally the vol that moves gamma and zomma. VIX1D is a
# different instrument and disagreed with it today.
#
# Deadband 0.001 = 0.1 vol points, the same scale as IVDIR_DB_VIX (0.10 on a
# vol-point series); strike IV is quoted as a decimal, so 0.10 vol pts = 0.001.
IVDIR_DB_ATM   = 0.001
_atmiv_hist    = deque(maxlen=IVDIR_WIN)

def _two_half_dir(hist, deadband):
    """Up / Down / Flat from mean(recent half) - mean(older half), with a deadband.
       Returns 'Flat' until the window is at least ~half full (needs both halves)."""
    n = len(hist)
    if n < 4:
        return "Flat"
    half = n // 2
    older  = list(hist)[:half]
    recent = list(hist)[half:]
    if not older or not recent:
        return "Flat"
    diff = (sum(recent)/len(recent)) - (sum(older)/len(older))
    if diff >=  deadband: return "Up"
    if diff <= -deadband: return "Down"
    return "Flat"


def _interp_iv(pairs, target):
    """Linear-interpolate IV at `target` strike from [(strike, iv), ...]. None if it
       cannot be bracketed -- never extrapolates off the end of the quoted chain."""
    pts = sorted((k, v) for k, v in pairs if isinstance(v, (int, float)) and v > 0)
    if len(pts) < 2 or target < pts[0][0] or target > pts[-1][0]:
        return None
    for i in range(1, len(pts)):
        if pts[i][0] >= target:
            (k0, v0), (k1, v1) = pts[i-1], pts[i]
            if k1 == k0:
                return v1
            return v0 + (v1 - v0) * (target - k0) / (k1 - k0)
    return None


def skew_monitor(raw_by_strike, spot):
    """Read the shape of the 0DTE IV curve. Returns (ps, cs, rr, state, put_txt, call_txt)
       with values in VOL POINTS (x100). Any piece that cannot be computed comes back
       None and the display says so rather than guessing. Never raises."""
    global _ps_lo, _ps_hi, _skew_state
    _skew_state = {}                              # cleared each cycle; only a full read refills it
    try:
        calls = [(k, v[0]) for k, v in raw_by_strike.items() if isinstance(v[0], (int, float))]
        puts  = [(k, v[1]) for k, v in raw_by_strike.items() if isinstance(v[1], (int, float))]
        if len(puts) < 3:
            # put IV never arrived from the feed -> say so, do not fake it
            return None, None, None, "SKEW  — no put IV from feed", "n/a", "n/a"

        atm_c = _interp_iv(calls, spot)
        atm_p = _interp_iv(puts,  spot)
        atm = (atm_c + atm_p) / 2 if (atm_c and atm_p) else (atm_c or atm_p)
        iv_p = _interp_iv(puts,  spot - SKEW_OFF)
        iv_c = _interp_iv(calls, spot + SKEW_OFF)
        if not atm:
            return None, None, None, "SKEW  — building", "…", "…"

        ps = (iv_p - atm) * 100 if iv_p else None      # vol points, RAW (displayed)
        cs = (iv_c - atm) * 100 if iv_c else None
        rr = (cs - ps) if (ps is not None and cs is not None) else None
        arrow = lambda d: "▲" if d == "Up" else ("▼" if d == "Down" else "▬")

        # ---- de-trend FIRST. Everything downstream runs on the RESIDUAL. ----
        # The raw wings drift up all session as the 0DTE smile blows out (T->0). The
        # calibrated SKEW_BASE (Jan-Jun 2026, 116 sessions) says put skew runs +2.15 at
        # 09:30 and +4.55 by 15:00; the call wing crosses zero around 13:30. So BOTH the
        # direction AND the "steep" level must be judged against the residual -- an earlier
        # cut de-trended only the direction and left `steep` on the raw series, which made
        # STEEP PUT SKEW little more than an afternoon clock alarm (top-of-range is almost
        # always late in the day when the series drifts monotonically upward).
        #
        # Values SHOWN to the user stay RAW (ps/cs/rr) -- they are the real curve. Only
        # the STATE machine runs on the residual.
        if not SKEW_BASE:
            head = ("SKEW  PUT " + (f"{ps:+.1f}" if ps is not None else "n/a")
                    + "vp · CALL " + (f"{cs:+.1f}" if cs is not None else "n/a")
                    + "vp" + (f" · RR {rr:+.1f}vp" if rr is not None else "")
                    + "   — states OFF (SKEW_BASE not calibrated)")
            return ps, cs, rr, head, (f"{ps:+.1f}vp" if ps is not None else "n/a"), \
                                     (f"{cs:+.1f}vp" if cs is not None else "n/a")

        # SKEW_BASE is anchored on half-hour slots, but the smile drifts CONTINUOUSLY --
        # a step function leaves the correction stale by the end of each slot, worst in the
        # final 30 min when the blow-out accelerates. Interpolate between anchors instead.
        # Outside the calibrated window (pre-09:30 / the 16:00 close) we CLAMP to the nearest
        # anchor rather than fall back to (0,0): zero would mean NO de-trending at exactly
        # the moment the raw wings are widest, which would light every state at once.
        _now = et_now()
        _mins = _now.hour * 60 + _now.minute
        _anch = sorted((int(k[:2]) * 60 + int(k[3:]), v) for k, v in SKEW_BASE.items())
        if _mins <= _anch[0][0]:
            _b = _anch[0][1]
        elif _mins >= _anch[-1][0]:
            _b = _anch[-1][1]
        else:
            for _i in range(1, len(_anch)):
                if _anch[_i][0] >= _mins:
                    (_t0, _v0), (_t1, _v1) = _anch[_i - 1], _anch[_i]
                    _w = (_mins - _t0) / (_t1 - _t0)
                    _b = (_v0[0] + (_v1[0] - _v0[0]) * _w,
                          _v0[1] + (_v1[1] - _v0[1]) * _w)
                    break
        ps_r = (ps - _b[0]) if ps is not None else None
        cs_r = (cs - _b[1]) if cs is not None else None

        if ps_r is not None:
            _ps_hist.append(ps_r)
            _ps_lo = ps_r if _ps_lo is None else min(_ps_lo, ps_r)
            _ps_hi = ps_r if _ps_hi is None else max(_ps_hi, ps_r)
        if cs_r is not None:
            _cs_hist.append(cs_r)

        ps_dir = _two_half_dir(_ps_hist, SKEW_DB) if ps_r is not None else "Flat"
        cs_dir = _two_half_dir(_cs_hist, SKEW_DB) if cs_r is not None else "Flat"

        # "steep" = the residual sits in the top third of today's RESIDUAL range, i.e.
        # unusually put-bid FOR THIS TIME OF DAY. Never the raw level.
        steep = False
        if ps_r is not None and _ps_hi is not None and _ps_lo is not None and (_ps_hi - _ps_lo) > 0.2:
            steep = (ps_r - _ps_lo) / (_ps_hi - _ps_lo) >= SKEW_STEEP_PCT

        # ---- state machine: EVERY combination must produce a truthful line ----
        # An earlier cut had a hole -- a rising-but-not-yet-steep put skew fell through
        # both branches and printed "FLAT SKEW", which was simply false. The put leg now
        # always resolves to exactly one of four states, and the call leg is additive.
        #
        # 'steep' is a LEVEL condition (top third of today's own range); direction is a
        # SEPARATE reading. A falling skew is the more actionable observation, so Down
        # takes precedence over a still-elevated level.
        if ps is None:
            put_state = "PUT SKEW — n/a"
        elif ps_dir == "Down":
            put_state = "FLATTENING PUT SKEW — hedging demand easing"
        elif steep:
            put_state = "STEEP PUT SKEW — strong demand for downside protection"
        elif ps_dir == "Up":
            put_state = "STEEPENING PUT SKEW — hedging demand building"
        else:
            put_state = "PUT SKEW NEUTRAL"

        head = "SKEW  " + put_state
        if cs_dir == "Up":
            head += "  ·  RISING CALL SKEW — upside demand building"
        if rr is not None:
            head += f"   (RR {rr:+.1f}vp)"
        _skew_state = {"ps_dir": ps_dir, "cs_dir": cs_dir, "steep": steep, "rr": rr}
        put_txt  = f"{ps:+.1f}vp {arrow(ps_dir)}" if ps is not None else "n/a"
        call_txt = f"{cs:+.1f}vp {arrow(cs_dir)}" if cs is not None else "n/a"
        return ps, cs, rr, head, put_txt, call_txt
    except Exception as e:
        return None, None, None, f"SKEW  — error ({e})", "n/a", "n/a"
_obs_prev_S = []      # prior cycle's locked supports (breaks judged on these)
_obs_spot   = deque(maxlen=OBS_CONFIRM)        # recent spots (reclaim confirm)

def _vol_rolled():
    """True if vix1d/vix made a local peak in the recent window and has since turned down."""
    h = list(_obs_ratio)
    if len(h) < 3:
        return False
    pk = max(h)
    return h[-1] < pk and h.index(pk) <= len(h) - 2

def apply_roll_reclaim(spot, locked_S, vix1d, vix):
    """One-shot observation flag: reclaim of a broken support co-occurring with a vol roll.
       Pure observation for live accumulation -- never a trade trigger."""
    global _obs_armed, _obs_latch, _obs_prev_S, _obs_broken
    try:
        if vix and vix1d and float(vix) > 0:
            _obs_ratio.append(float(vix1d) / float(vix))
    except (TypeError, ValueError):
        pass
    _obs_spot.append(spot)
    prev = [s for s in _obs_prev_S if isinstance(s, (int, float))]
    cur  = [s for s in (locked_S or []) if isinstance(s, (int, float))]
    for K in prev:                                       # breaks judged on prior cycle
        if spot <= K - OBS_BRK:
            _obs_broken[K] = True
    recl = next((K for K in sorted(_obs_broken) if spot >= K + OBS_RCL), None)
    if recl is not None and _obs_armed:
        held = len(_obs_spot) >= OBS_CONFIRM and all(s >= recl + OBS_RCL for s in _obs_spot)
        if held:
            if _vol_rolled():
                _obs_latch = OBS_HOLD
            _obs_armed = False
            _obs_broken = {k: v for k, v in _obs_broken.items() if k < recl}
    if not _obs_armed:                                   # re-arm on a fresh lower break
        for K in prev:
            if spot <= K - OBS_BRK and K not in _obs_broken:
                _obs_armed = True
    _obs_prev_S = cur
    if _obs_latch > 0:
        _obs_latch -= 1
        return 1
    return 0



def apply_negg_hysteresis(idx, unsafe, hold):
    """1 while reaction-row `idx`'s raspberry neg-gamma border should show, else 0.
       Arms while that row reads UNSAFE; when UNSAFE clears, holds `hold` cycles before
       dropping; a re-trigger during the hold resets the counter. Mirrors apply_warn_hysteresis,
       one latch+counter per reaction row (R1-R3, S1-S3). Hold count is shared (CT12)."""
    global _negg_active, _negg_below
    if unsafe:
        _negg_active[idx] = True;  _negg_below[idx] = 0   # active (or re-armed) -> show, reset hold
    elif _negg_active[idx]:                                # UNSAFE dropped while latched
        _negg_below[idx] += 1
        if _negg_below[idx] >= hold:                       # held long enough -> clear
            _negg_active[idx] = False; _negg_below[idx] = 0
    return 1 if _negg_active[idx] else 0


# ---- R/S side hysteresis ----
# A level keeps its resistance/support role until price CLOSES past its BOX EDGE
# by the threshold (Level Engine BG9, default 5 pts). A resistance box [L, L+5]
# stays 'R' until spot > L+5+thr (top of box + thr); a support box [L-5, L] stays
# 'S' until spot < L-5-thr (bottom of box - thr). Un-boxed levels flip at L+/-thr.
# Inside that band the level holds its prior side instead of flipping the instant
# spot ticks across it. The locked lists feed the AG side formula, which mirrors
# them, so display + lock + threshold all stay in agreement.
_rs_side = {}            # strike -> 'R' / 'S'

def apply_rs_hysteresis(raw_R, raw_S, spot, thresh, box_flags):
    cands = []
    for L in list(raw_R) + list(raw_S):
        if L not in cands:
            cands.append(L)
    for L in cands:
        half = 5 if box_flags.get(L) == 1 else 0   # flip from the TOP/BOTTOM of the box, not the bare strike
        if spot > L + half + thresh:
            _rs_side[L] = 'S'                       # price closed >thr above the box top -> support
        elif spot < L - half - thresh:
            _rs_side[L] = 'R'                       # price closed >thr below the box bottom -> resistance
        else:
            _rs_side.setdefault(L, 'R' if L > spot else 'S')   # deadband: keep prior side
    # hard invariant: once price is genuinely through the bare strike, side must follow.
    # The box/thr deadband above is for anti-flap while price is still on the correct side;
    # it must never leave support above spot or resistance below spot.
    for L in cands:
        if   _rs_side.get(L) == 'S' and spot < L: _rs_side[L] = 'R'
        elif _rs_side.get(L) == 'R' and spot > L: _rs_side[L] = 'S'
    hR = [L for L in cands if _rs_side.get(L) == 'R']
    hS = [L for L in cands if _rs_side.get(L) == 'S']
    return hR, hS


def _apply_chop_yield(spot):
    """Chop routes the reaction table to the held dEdge (AB18/AB19), overriding the
       Level Engine's locked R1/S1. That override must not step on a NEARER locked
       level: on 2026-07-13 it replaced a locked R1 of 7560 (|gamma| 2.05M, confl 6,
       REVERSAL) with a 2-cycle transient dEdge.

       If the nearest locked level on a side is closer to spot than that side's held
       dEdge, clear the edge cell for this cycle. AZ42/AZ49 then fall back to their
       normal nearest-level path and the locked level renders with its box, rank and
       REVERSAL flag intact. The dEdge still wins whenever it is genuinely nearer.

       Must run AFTER the level lock has written W9:W14 / W18:W23."""
    try:
        for cell, locked in (('AB18', _locked_R), ('AB19', _locked_S)):
            edge = sht[cell].value
            if not isinstance(edge, (int, float)):
                continue
            near = [L for L in locked if isinstance(L, (int, float))]
            if not near:
                continue
            nearest = min(near, key=lambda L: abs(L - spot))
            if abs(nearest - spot) < abs(edge - spot):
                sht[cell].value = None            # locked level is nearer -> it wins
    except Exception as e:
        print(f"   ! chop yield skipped ({e})")


# ============ ONE-TIME SETUP ============
ib = IB()
print(f"Connecting on port {PORT} ...")
ib.connect('127.0.0.1', PORT, clientId=1)

ib.reqMarketDataType(INDEX_TYPE)
spx     = get_ticker(ib, Index('SPX',   'CBOE', 'USD'))
vix_t   = get_ticker(ib, Index('VIX',   'CBOE', 'USD'))
vvix_t  = get_ticker(ib, Index('VVIX',  'CBOE', 'USD'))
vix1d_t = get_ticker(ib, Index('VIX1D', 'CBOE', 'USD'))

# ---- seed the vol-direction windows (P4/P5/P6) from 1-min history ----
# Without this, all three direction reads sit on "Flat" for up to ~25 min
# (IVDIR_WIN cycles) after any restart. 1-min closes are coarser than the 30s
# cycle but the two-half mean only needs the shape. Failure never blocks startup.
for _sym, _tk, _dq in (('VIX', vix_t, _vixdir_hist),
                       ('VVIX', vvix_t, _vvixdir_hist),
                       ('VIX1D', vix1d_t, _v1ddir_hist)):
    try:
        _hb = ib.reqHistoricalData(_tk.contract, '', '1800 S', '1 min',
                                   'TRADES', useRTH=False, formatDate=2)
        for _b in _hb:
            _dq.append(float(_b.close))
        print(f"Seeded {_sym} direction window: {len(_hb)} bars")
    except Exception as _e:
        print(f"   ! {_sym} direction seed failed ({_e}); will accumulate live")

spot0 = best_price(spx)
print(f"SPX spot: {spot0}")
if math.isnan(spot0):
    print("Spot blank - check Gateway is logged in (green), then re-run.")
    ib.disconnect(); input("Enter to close..."); raise SystemExit

chains = ib.reqSecDefOptParams('SPX', '', 'IND', spx.contract.conId)
chain = [c for c in chains if c.tradingClass == 'SPXW'][0]
exchange = chain.exchange
today = datetime.date.today().strftime('%Y%m%d')
expiry = sorted(e for e in chain.expirations if e >= today)[0]
strikes_all = sorted(chain.strikes)
RECENTER_PTS = STRIKES_EACH_SIDE * 5 * 0.5

ib.reqMarketDataType(OPTION_TYPE)
ib.sleep(1)

_buf = deque(maxlen=SMOOTH_N)            # rolling buffer for value smoothing
_vomma_hist  = deque(maxlen=VOMMA_HIST)  # near-spot |vomma| history (peak / roll-over detection)
_vomma_times = deque(maxlen=VOMMA_HIST)
_vomma_latch = {'text': None, 'until': 0.0}   # holds a fired trigger on display for VOMMA_HOLD secs
_spot_hist = deque(maxlen=SPOT_HIST)     # raw spot history (move velocity / acceleration)
_spot_dt   = deque(maxlen=SPOT_HIST)


def build_window(spot):
    center = min(strikes_all, key=lambda s: abs(s - spot))
    i = strikes_all.index(center)
    n = STRIKES_EACH_SIDE
    lo = max(0, i - n); hi = lo + (2 * n + 1)
    if hi > len(strikes_all):
        hi = len(strikes_all); lo = max(0, hi - (2 * n + 1))
    sd = sorted(strikes_all[lo:hi], reverse=True)
    cons = {}
    for k in sd:
        for r_ in ('C', 'P'):
            cons[(k, r_)] = Option('SPX', expiry, k, r_, exchange, tradingClass='SPXW')
    ib.qualifyContracts(*cons.values())
    # Pace requests in batches to avoid IBKR pacing violations (94 simultaneous
    # requests causes silent drops; 20 per batch with 1s gap stays well under the limit)
    tkk = {}
    items = list(cons.items())
    BATCH = 20
    for i in range(0, len(items), BATCH):
        for key, c in items[i:i + BATCH]:
            tkk[key] = ib.reqMktData(c, '101', False, False)
        ib.sleep(1)
    return {'center': center, 'strikes': sd, 'cons': cons, 'tk': tkk}


def cancel_window(state):
    for c in state['cons'].values():
        ib.cancelMktData(c)


warm = Option('SPX', expiry, min(strikes_all, key=lambda s: abs(s - spot0)), 'C', exchange, tradingClass='SPXW')
ib.qualifyContracts(warm); ib.reqMktData(warm); ib.sleep(2)

state = build_window(spot0)
print(f"Expiry {expiry}, {len(state['strikes'])} strikes around {state['center']:.0f}")
print("Waiting for first data ...")
ib.sleep(10)

_wbname = os.path.basename(WORKBOOK)
try:
    wb = xw.books[_wbname]
except Exception:
    wb = xw.Book(WORKBOOK)
sht    = wb.sheets[SHEET]

# ---- robust recalc: force a full recompute that ignores the calc chain -------------
# Plain Application.Calculate (xlwings wb.app.calculate) only recomputes cells the calc
# chain marks dirty. On this workbook that chain intermittently fails to re-flag display
# cells such as King Node Model!S42 when their AL input changes strike, leaving a stale
# blank -- the '.r1'/'.s3' orphan (strike missing while metrics still render). CalculateFull
# recomputes every formula regardless of the chain; CalculateFullRebuild also rebuilds the
# dependency tree (run once at startup to repair a chain left corrupt by the previous save).
def _recalc_full():
    try:
        wb.app.api.CalculateFull()
    except Exception:
        try:
            wb.app.calculate()          # fallback: at least the dirty-set recalc
        except Exception:
            pass

def _recalc_rebuild():
    try:
        wb.app.api.CalculateFullRebuild()
    except Exception:
        _recalc_full()

# One-time chain repair on connect: the previous session's Save rewrites calcChain.xml and
# clears fullCalcOnLoad, so the freshly opened book can carry stale caches. Rebuild once
# here so the baseline is clean before the first write cycle.
try:
    _recalc_rebuild()
except Exception:
    pass

# ---- dEdge chop-box edge hysteresis (held resistance/support -> KNM AB18/AB19) ----
# Parallels the replay: in a DEX-peaks chop, route the reaction table (AL42/AL49) to the
# nearest DEX drop-off edge (Level Engine dEdge/CZ) instead of the GEX wall, with a BG9
# (5-pt) hold so an edge under test doesn't flicker out. State persists across cycles.
_dedge_res_hold = None
_dedge_sup_hold = None
_dedge_chop_off = 0
CHOP_STATE_HOLD = 3        # keep routing this many cycles after chop flickers off

# A raw dEdge that differs from the held one is only a CHALLENGER: it must repeat
# for LOCK_HOLD consecutive cycles before it takes over. Without this the raw edge
# overwrote the hold every cycle -- on 2026-07-13 that let a 2-cycle 7565 displace
# 7560, which was the dEdge for 36 cycles and the locked R1. [strike, count] or None.
_dedge_res_pend = None
_dedge_sup_pend = None


def _challenge(hold, pend, raw):
    """LOCK_HOLD-style challenger gate for a single held dEdge.
       Returns (new_hold, new_pend). `raw` is this cycle's detected edge (or None)."""
    if raw is None:
        return hold, pend                     # no detection -> caller's blind-hold logic
    if hold is None:
        return raw, None                      # nothing held yet -> adopt immediately
    if raw == hold:
        return hold, None                     # incumbent re-confirmed -> clear challenge
    if pend is not None and pend[0] == raw:
        pend[1] += 1
        if pend[1] >= LOCK_HOLD:              # challenger held long enough -> promote
            return raw, None
        return hold, pend
    return hold, [raw, 1]                     # new challenger -> start its counter


def _nearest_dedge(above, spot, band):
    """Nearest strike flagged dEdge (Level Engine CZ=1) on the requested side of spot,
       within `band` pts. Reads the just-calculated CZ/AA columns."""
    aa = sht_le.range('AA9:AA55').value
    cz = sht_le.range('CZ9:CZ55').value
    best = None
    for a, z in zip(aa, cz):
        if not isinstance(a, (int, float)) or z != 1:
            continue
        if abs(a - spot) > band:
            continue
        if above and a <= spot:
            continue
        if (not above) and a >= spot:
            continue
        if best is None or abs(a - spot) < abs(best - spot):
            best = a
    return best


def _nearest_raw_dropoff(above, spot, band):
    """Fallback edge for when dEdge (CZ) flags nothing on a side during chop. Uses the
       SAME drop fraction and |DEX| floor as dEdge (Level Engine BG42/BG43), but measures
       the drop-off purely OUTWARD from spot rather than outward from the DEX middle
       (BG28). Because BG28 = argmax(|DEX|) can pin to a wall, dEdge goes blind on the
       support side; this recovers the genuine DEX drop-off edges there. Returns a strike
       (on the requested side, within band) or None."""
    aa = sht_le.range('AA9:AA55').value      # strikes, descending (row 9 = highest)
    ae = sht_le.range('AE9:AE55').value      # DEX per strike
    try:
        floor = sht_le['BG43'].value or 100000
        frac  = sht_le['BG42'].value or 0.5
    except Exception:
        floor, frac = 100000, 0.5
    n = len(aa)
    best = None
    for i in range(n):
        a = aa[i]
        if not isinstance(a, (int, float)) or abs(a - spot) > band:
            continue
        if above and a <= spot:
            continue
        if (not above) and a >= spot:
            continue
        d = ae[i]
        if not isinstance(d, (int, float)) or abs(d) < floor:
            continue
        j = i - 1 if above else i + 1        # outward neighbour (higher strike above / lower below)
        if j < 0 or j >= n:
            continue
        dn = ae[j]
        if not isinstance(dn, (int, float)):
            continue
        if abs(dn) < (1.0 - frac) * abs(d):  # DEX collapses > frac outward -> this strike is the edge
            if best is None or abs(a - spot) < abs(best - spot):
                best = a
    return best


# ---- oEdge: outermost DEX drop-off box in NEG-gamma (separate rule; does not touch dEdge) ----
# Finds the outermost non-wall DEX drop-off cluster within the near-window, on the side away
# from spot, and flags every strike in that cluster (capped at OEDGE_MAX_WIDTH pts). Written to
# Level Engine DS9:DS55 BEFORE the first calculate so revFlag (AN) classifies it as REVERSAL and
# the greek string tags it "oEdge". NEG-gamma only -- stays dormant in Pos so it can't disturb the
# Pos-gamma routing. Uses the same |DEX| floor / drop fraction as dEdge (BG42/BG43); walls are
# excluded as |DEX| >= OEDGE_WALL_MULT x the near-spot median so it lands on the plateau floor,
# not the wall.
OEDGE_MAX_WIDTH = 15.0     # cap the reported box width (pts) so a long DEX run can't run away
OEDGE_WALL_MULT = 3.0      # |DEX| >= this x near-median counts as a wall (excluded)


def _write_oedge():
    """Compute the neg-gamma outer DEX box and write the per-strike flag to DS9:DS55.
       Clears the column (all 0) in Pos-gamma or on any error."""
    import statistics
    try:
        aa = sht_le.range('AA9:AA55').value
        ae = sht_le.range('AE9:AE55').value      # DEX per strike
        spot = sht['B4'].value
        regime = sht['A8'].value
        band = sht_le['BG7'].value or 50
        floor = sht_le['BG43'].value or 100000
        frac = sht_le['BG42'].value or 0.5
        flags = [0] * len(aa)
        if not (isinstance(spot, (int, float)) and isinstance(regime, str) and regime == 'Neg'):
            sht_le.range('DS9:DS55').value = [[0] for _ in aa]
            return
        K = [a if isinstance(a, (int, float)) else None for a in aa]
        D = [d if isinstance(d, (int, float)) else None for d in ae]
        near = [abs(D[i]) for i in range(len(K)) if K[i] is not None and D[i] is not None and abs(K[i] - spot) <= band]
        med = statistics.median(near) if near else 1.0
        wall_th = OEDGE_WALL_MULT * med
        n = len(K)

        def is_wall(i):
            return D[i] is not None and abs(D[i]) >= wall_th

        # collect non-wall DEX drop-offs below spot (support side in a neg-gamma break)
        drops = []
        for i in range(n):
            a = K[i]
            if a is None or D[i] is None or abs(a - spot) > band or a >= spot:
                continue
            if is_wall(i) or abs(D[i]) < floor:
                continue
            j = i + 1                              # outward (lower) neighbour
            if j >= n or K[j] is None or D[j] is None or is_wall(j):
                continue
            if abs(D[j]) < (1.0 - frac) * abs(D[i]):
                drops.append((a, i))
        if drops:
            outer, oi = max(drops, key=lambda t: abs(t[0] - spot))
            idx = {K[m]: m for m in range(n) if K[m] is not None}
            cur = outer
            while True:                            # cluster inward while sustained + capped
                nxt = cur + 5
                if (nxt in idx and D[idx[nxt]] is not None and abs(D[idx[nxt]]) >= floor
                        and not is_wall(idx[nxt]) and abs(nxt - outer) <= OEDGE_MAX_WIDTH):
                    cur = nxt
                else:
                    break
            lo, hi = min(outer, cur), max(outer, cur)
            for m in range(n):
                if K[m] is not None and lo <= K[m] <= hi:
                    flags[m] = 1
        sht_le.range('DS9:DS55').value = [[f] for f in flags]
    except Exception as e:
        print(f"   ! oEdge skipped ({e})")


# ---- nVanna: near-field vanna cluster (fat Vega + extreme Vex within NVAN_NEAR pts) — NEG-gamma only ----
# Marks the near-spot vol-driven bounce/reject zone the far-tail gravity points miss (they require
# >40 pts). Neg-gamma only. Writes the per-strike flag to Level Engine DT9:DT55 before the first
# calculate. Observation flag: does NOT feed revFlag/REVERSAL. Surfaces as the ☄ glyph on the chart,
# the ☄ vol-bounce tag in the reaction Reversal/Type when the level is in the table, and the
# NEAR-VANNA table on the dashboard. Validated: flags the bounce floor at 7/7 neg-gamma lows.
NVAN_NEAR = 40.0          # near-window (pts) — complements the >40pt gravity-point rule, no overlap
NVAN_VEGA_TOPN = 3        # must be top-N by Vega within the near window
NVAN_VEX_TOPN = 5         # AND top-N by |Vex| within the near window
NVAN_MAX_WIDTH = 15.0     # cluster/box width cap (pts)


def _write_nvanna():
    """Compute the neg-gamma near-vanna zones (support below spot, resistance above) and write the
       per-strike flag to DT9:DT55. Clears to 0 in Pos-gamma or on error."""
    try:
        aa = sht_le.range('AA9:AA55').value
        vega = sht_le.range('BL9:BL55').value     # Vegamir
        vex = sht_le.range('AD9:AD55').value      # vex
        spot = sht['B4'].value
        regime = sht['A8'].value
        flags = [0] * len(aa)
        if not (isinstance(spot, (int, float)) and isinstance(regime, str) and regime == 'Neg'):
            sht_le.range('DT9:DT55').value = [[0] for _ in aa]
            return
        near = [i for i in range(len(aa))
                if isinstance(aa[i], (int, float)) and abs(aa[i] - spot) <= NVAN_NEAR
                and isinstance(vega[i], (int, float)) and isinstance(vex[i], (int, float))]
        if len(near) >= 3:
            top_vega = set(sorted(near, key=lambda i: -abs(vega[i]))[:NVAN_VEGA_TOPN])
            top_vex = set(sorted(near, key=lambda i: -abs(vex[i]))[:NVAN_VEX_TOPN])
            qual = [i for i in near if i in top_vega and i in top_vex]
            for below in (True, False):               # support (below spot) and resistance (above)
                side = [i for i in qual if (aa[i] < spot) == below]
                if not side:
                    continue
                anchor = min(side, key=lambda i: abs(aa[i] - spot))
                for i in side:
                    if abs(aa[i] - aa[anchor]) <= NVAN_MAX_WIDTH:
                        flags[i] = 1
        sht_le.range('DT9:DT55').value = [[f] for f in flags]
    except Exception as e:
        print(f"   ! nVanna skipped ({e})")


def _apply_dedge_hold(spot):
    """Pick nearest dEdge each side, apply BG9 edge hold + a CHOP_STATE_HOLD-cycle chop-state
       hold, write held edges to AB18/AB19. Keeps the routing steady through brief S52 flicker
       while price sits in the box; releases on a clean directional break (spot beyond a held edge by > BG9) or after chop
       stays off CHOP_STATE_HOLD cycles; a pullback off the level holds it."""
    global _dedge_res_hold, _dedge_sup_hold, _dedge_chop_off
    global _dedge_res_pend, _dedge_sup_pend
    try:
        bg9 = sht_le['BG9'].value or 5
        band = sht_le['BG7'].value or 50
        chop = bool(sht['S52'].value) or (isinstance(sht['S38'].value, str) and 'Choppy' in sht['S38'].value)

        if not chop:
            if _dedge_res_hold is None and _dedge_sup_hold is None:
                _dedge_chop_off = 0
            else:
                _dedge_chop_off += 1
                if _dedge_chop_off >= CHOP_STATE_HOLD:
                    _dedge_res_hold = _dedge_sup_hold = None
                    _dedge_res_pend = _dedge_sup_pend = None
                    _dedge_chop_off = 0
                else:
                    if _dedge_res_hold is not None and spot - _dedge_res_hold > bg9:
                        _dedge_res_hold = None
                    if _dedge_sup_hold is not None and _dedge_sup_hold - spot > bg9:
                        _dedge_sup_hold = None
            if _dedge_res_hold is not None and _dedge_res_hold <= spot:
                _dedge_res_hold = None
            if _dedge_sup_hold is not None and _dedge_sup_hold >= spot:
                _dedge_sup_hold = None
            sht['AB18'].value = _dedge_res_hold if _dedge_res_hold is not None else None
            sht['AB19'].value = _dedge_sup_hold if _dedge_sup_hold is not None else None
            return

        _dedge_chop_off = 0
        raw_res = _nearest_dedge(True, spot, band)
        raw_sup = _nearest_dedge(False, spot, band)
        if raw_res is None:                              # dEdge blind on this side -> raw DEX drop-off
            raw_res = _nearest_raw_dropoff(True, spot, band)
        if raw_sup is None:
            raw_sup = _nearest_raw_dropoff(False, spot, band)
        # a changed edge is a CHALLENGER: it must hold LOCK_HOLD cycles to take over
        if raw_res is not None:
            _dedge_res_hold, _dedge_res_pend = _challenge(_dedge_res_hold, _dedge_res_pend, raw_res)
        elif _dedge_res_hold is not None and spot - _dedge_res_hold > bg9:
            _dedge_res_hold = None
            _dedge_res_pend = None
        if raw_sup is not None:
            _dedge_sup_hold, _dedge_sup_pend = _challenge(_dedge_sup_hold, _dedge_sup_pend, raw_sup)
        elif _dedge_sup_hold is not None and _dedge_sup_hold - spot > bg9:
            _dedge_sup_hold = None
            _dedge_sup_pend = None
        # side sanity: resistance must sit above spot, support below spot -- a held
        # edge that price has crossed to the wrong side is void, hold window notwithstanding.
        if _dedge_res_hold is not None and _dedge_res_hold <= spot:
            _dedge_res_hold = None
        if _dedge_sup_hold is not None and _dedge_sup_hold >= spot:
            _dedge_sup_hold = None
        sht['AB18'].value = _dedge_res_hold if _dedge_res_hold is not None else None
        sht['AB19'].value = _dedge_sup_hold if _dedge_sup_hold is not None else None
    except Exception as e:
        print(f"   ! dEdge hold skipped ({e})")
sht_le = wb.sheets[LE_SHEET]
sht_gd = wb.sheets["GEX Depth"]
try:
    sht_md = wb.sheets["Master Dashboard"]      # neg-gamma UNSAFE cells live here (K32:K34, K37:K39)
except Exception:
    sht_md = None

# ---- Master Dashboard layout probe (STRUCTURAL -- does not depend on any typed label) ----
# A blank row inserted under Vol regime (row 17) pushes every Master Dashboard row from 17
# down by ONE -- including the neg-gamma UNSAFE cells this engine reads (K32:K34 / K37:K39).
# Reading the wrong rows would silently map the raspberry alerts to the WRONG reaction rows:
# no error, just wrong borders on wrong levels. So the offset is DETECTED, never assumed.
#
# The anchor is the "Signs" label in column E -- row 18 in the original layout. It is part of
# the sheet's own structure, so this works whether or not anyone remembered to type a label
# in E17. (The row insert itself must be done in EXCEL, never by script: 177 formulas,
# 39 merges, 38 CF ranges and 13 cross-sheet refs shift, and Excel rewrites them all.)
# FAIL CLOSED. The previous cut defaulted a failed probe to offset 0, which set
# MD_SKEW_CELL = "E22". E22 was an empty framed spacer when that fallback was written;
# after the Skew and Vol Tension row inserts it holds the NET GEX formula, so a single
# missed anchor would have silently overwritten a live formula with a skew string. There
# is no safe default: if the layout cannot be read, the engine writes NOTHING to the
# Master Dashboard and says so loudly. No borders is recoverable; wrong borders on the
# wrong levels is not.
#
# Two independent anchors, each resolving only what it owns:
#   "Signs" -> the neg-gamma UNSAFE row offset (K32:K34 / K37:K39 in the original layout)
#   "Skew"  -> the skew line's own row, read directly rather than inferred from the
#             offset, so a row inserted ABOVE Skew can no longer misroute it.
# Vol Tension needs no anchor at all: F18 is a FORMULA reading 'King Node Model'!AB17,
# so that line is immune to every layout change by construction.
MD_LAYOUT_OK  = False
MD_ROW_OFFSET = 0
MD_SKEW_CELL  = None
if sht_md is not None:
    try:
        _labels = {}
        for _r in range(10, 34):
            _t = str(sht_md[f"E{_r}"].value or "").strip().lower()
            if _t and _t not in _labels:
                _labels[_t] = _r
        _signs = _labels.get("signs")
        _skew  = _labels.get("skew")
        if _signs is None:
            print("   ! MD probe: 'Signs' anchor NOT FOUND - all Master Dashboard writes DISABLED")
        elif not 18 <= _signs <= 26:
            print(f"   ! MD probe: 'Signs' at implausible row {_signs} "
                  f"- all Master Dashboard writes DISABLED")
        else:
            MD_ROW_OFFSET = _signs - 18          # 0 = original, +1 Skew, +2 Vol Tension, ...
            MD_SKEW_CELL  = f"F{_skew}" if _skew else None
            MD_LAYOUT_OK  = True
            print(f"Master Dashboard: layout OK (offset +{MD_ROW_OFFSET}) -> "
                  f"skew to {MD_SKEW_CELL or 'no Skew row (skipped)'}, "
                  f"vol tension via KNM AB17 -> F18 formula")
    except Exception as e:
        print(f"   ! MD layout probe FAILED ({e}) - all Master Dashboard writes DISABLED")
MD_NEGG_CELLS = (tuple("K" + str(r + MD_ROW_OFFSET) for r in (32, 33, 34, 37, 38, 39))
                 if MD_LAYOUT_OK else ())
last_row = FIRST_DATA_ROW + len(state['strikes']) - 1
sht[f'B{FIRST_DATA_ROW}:I{last_row}'].number_format = '#,##0'
# NOTE: column J is no longer cleared here. It now holds the FLIP-marker formula
#       =IF(AND(ISNUMBER($D$26),$A29=$D$26),"FLIP","") which must survive between runs.

# ---- ES / Technical-Analysis setup (Stage 1) ----
# Tick-by-tick AllLast needs LIVE futures data (CME real-time). With delayed-only
# futures the seed still works but the live tick stream will be empty.
if TA_ENABLED:
    try:
        _sht_ta = wb.sheets[TA_SHEET]
    except Exception:
        _sht_ta = None
        print(f"   ! sheet '{TA_SHEET}' not found - TA panel disabled (feed still runs)")

    _es_contract = ContFuture('ES', ES_EXCHANGE)
    ib.qualifyContracts(_es_contract)
    _es_label = getattr(_es_contract, 'localSymbol', '') or _es_contract.lastTradeDateOrContractMonth
    print(f"ES front month: {_es_label}")

    if TA_SEED_HISTORY:
        print(f"Seeding ES history ({TA_SEED_DURATION}, 1 min) for VWAP / overnight / IB / profile ...")
        try:
            _bars = ib.reqHistoricalData(_es_contract, '', TA_SEED_DURATION, '1 min',
                                         'TRADES', useRTH=False, formatDate=2)
            for _b in _bars:
                _es_profile.add_bar(to_et(_b.date), _b.open, _b.high, _b.low,
                                    _b.close, float(_b.volume or 0))
            print(f"   seeded {len(_bars)} bars  "
                  f"(dVWAP {_es_profile.daily_vwap()}, ON {_es_profile.on_hi}/{_es_profile.on_lo})")
        except Exception as e:
            print(f"   ! ES history seed failed ({e}); will accumulate live only")

    # ---- seed the 200/400 SMA window from 5-minute ES history ----
    if _es_sma is not None:
        _rth = 'RTH' if SMA_USE_RTH else 'ETH'
        print(f"Seeding ES {SMA_BAR_MIN}-min SMA window ({SMA_SEED_DURATION}, {_rth}) ...")
        try:
            _sb = ib.reqHistoricalData(_es_contract, '', SMA_SEED_DURATION,
                                       f'{SMA_BAR_MIN} mins', 'TRADES',
                                       useRTH=SMA_USE_RTH, formatDate=2)
            _n = _es_sma.seed(_sb, et_now())
            _need = max(SMA_PERIODS) - 1
            _s2, _s4 = _es_sma.levels()
            if _n < _need:
                print(f"   ! only {_n} closed bars ({_need} needed for the "
                      f"{max(SMA_PERIODS)}) - longer SMA stays blank until it fills")
            print(f"   seeded {_n} closed {SMA_BAR_MIN}-min bars  "
                  f"(SMA{SMA_PERIODS[0]} {_s2}, SMA{SMA_PERIODS[1]} {_s4})")
        except Exception as e:
            print(f"   ! ES SMA seed failed ({e}); SMAs will accumulate live only")

    try:
        _es_ticker = ib.reqTickByTickData(_es_contract, 'AllLast', 0, False)
        _es_ticker.updateEvent += on_es_tick
        print("ES tick-by-tick AllLast subscribed.")
    except Exception as e:
        print(f"   ! ES tick-by-tick subscribe failed ({e}); panel will use seed only")


def _read_levels(rng):
    """Read a vertical range of raw level strikes; return clean list (blanks removed)."""
    vals = sht_le[rng].value
    if not isinstance(vals, (list, tuple)):
        vals = [vals]
    return [round(v) for v in vals if isinstance(v, (int, float))]


def move_velocity(hist, dts, window):
    """Rolling spot velocity (pts/min) over `window` intervals, plus an
       accelerating / decelerating read (recent half vs prior half, by
       magnitude). Returns (vel_ppm, accel_text, ready)."""
    n = len(hist)
    if n < 2:
        return None, '\u2014', False
    k = min(window, n - 1)
    dt_min = (dts[-1] - dts[-1 - k]).total_seconds() / 60.0
    vel = (hist[-1] - hist[-1 - k]) / dt_min if dt_min > 0 else 0.0
    if n >= 5:
        dt1 = (dts[-1] - dts[-3]).total_seconds() / 60.0
        dt0 = (dts[-3] - dts[-5]).total_seconds() / 60.0
        v1 = (hist[-1] - hist[-3]) / dt1 if dt1 > 0 else 0.0
        v0 = (hist[-3] - hist[-5]) / dt0 if dt0 > 0 else 0.0
        if abs(v1) > abs(v0) * 1.15:
            accel = 'ACCELERATING'
        elif abs(v1) < abs(v0) * 0.85:
            accel = 'DECELERATING'
        else:
            accel = 'STEADY'
    else:
        accel = 'warming up'
    return vel, accel, True


def refresh():
    global _locked_R, _locked_S, _pend_R, _pend_S
    global _swR_lock, _swR_pend, _swS_lock, _swS_pend
    spot = best_price(spx)
    if not math.isnan(spot):
        sht['B4'].value = spot
    for cell, t in (('B5', vix_t), ('D5', vvix_t), ('F5', vix1d_t)):
        v = best_price(t)
        if not math.isnan(v):
            sht[cell].value = v

    # ---- VIX / VVIX / VIX1D direction (two-half mean over rolling window) -> P4 / P5 / P6 ----
    _vx = sht['B5'].value
    _vv = sht['D5'].value
    _v1 = sht['F5'].value
    if isinstance(_vx, (int, float)) and not (isinstance(_vx, float) and math.isnan(_vx)):
        _vixdir_hist.append(float(_vx))
    if isinstance(_vv, (int, float)) and not (isinstance(_vv, float) and math.isnan(_vv)):
        _vvixdir_hist.append(float(_vv))
    if isinstance(_v1, (int, float)) and not (isinstance(_v1, float) and math.isnan(_v1)):
        _v1ddir_hist.append(float(_v1))
    sht['P4'].value = _two_half_dir(_vixdir_hist, IVDIR_DB_VIX)
    sht['P5'].value = _two_half_dir(_vvixdir_hist, IVDIR_DB_VVIX)
    _v1d_dir = _two_half_dir(_v1ddir_hist, IVDIR_DB_V1D)
    sht['P6'].value = _v1d_dir

    # ---- VIX1D session extremes -> VOL BOTTOM (AB13) / VOL TOP (AB14) flags ----
    global _v1d_lo, _v1d_hi, _v1d_lo_t, _v1d_hi_t, _v1d_hi_prom
    if isinstance(_v1, (int, float)) and not (isinstance(_v1, float) and math.isnan(_v1)):
        _now_hm = datetime.datetime.now().strftime("%H:%M")
        if _v1d_lo is None or _v1 < _v1d_lo:
            _v1d_lo, _v1d_lo_t = float(_v1), _now_hm
        if _v1d_hi is None or _v1 > _v1d_hi:
            _v1d_hi, _v1d_hi_t = float(_v1), _now_hm
            _v1d_hi_prom = (_v1d_hi - _v1d_lo) / _v1d_lo * 100 if _v1d_lo else 0.0
        _pct_lo = (_v1 - _v1d_lo) / _v1d_lo * 100 if _v1d_lo else 0.0
        _fade   = (_v1d_hi - _v1) / _v1d_hi * 100 if _v1d_hi else 0.0
        # "+69% off LoD" reads ambiguously -- it means vol has RISEN 69% ABOVE its low,
        # i.e. the front end is bidding. Spelt out so VOL BOTTOM and VOL TOP cannot be
        # mixed up: BOTTOM = rising off the low, TOP = falling from the high.
        sht['AB13'].value = (f"VOL BOTTOM \u2014 vol RISING, +{_pct_lo:.0f}% up off LoD "
                             f"{_v1d_lo:.2f} ({_v1d_lo_t})"
                             if (_pct_lo >= VOLB_PCT and _v1d_dir == "Up") else "")
        sht['AB14'].value = (f"\u25bd VOL TOP \u2014 vol FALLING, -{_fade:.0f}% down off HoD "
                             f"{_v1d_hi:.2f} ({_v1d_hi_t}), front-end fading"
                             if (_v1d_hi_prom >= VOLT_PROM and _fade >= VOLT_PCT and _v1d_dir == "Down") else "")
    # ---- ES 5-min SMAs: nudge the forming bar from the cycle in case the tick
    #      stream is thin (delayed futures), then read the levels for panel + archive.
    _es_s200 = _es_s400 = None
    if _es_sma is not None:
        try:
            _es_sma.update(et_now(), _es_profile.last if _es_profile else None)
            _es_s200, _es_s400 = _es_sma.levels()
        except Exception as e:
            print(f"   ! ES SMA update skipped ({e})")

    if TA_ENABLED:
        ta_write_panel(_sht_ta, _es_profile, _es_sma)   # ES reference panel + SMA rows
    if math.isnan(spot):
        return 'no spot - kept last values'

    # ---- move velocity monitor: rolling pts/min + acceleration ----
    _now = datetime.datetime.now()
    _spot_hist.append(spot)
    _spot_dt.append(_now)
    _vel, _acc, _vok = move_velocity(list(_spot_hist), list(_spot_dt), VEL_WINDOW)
    if _vok and _vel is not None:
        sht_gd['C68'].value = round(_vel, 1)
        sht_gd['D68'].value = ('\u25b2 rising' if _vel > 0.05 else
                               '\u25bc falling' if _vel < -0.05 else '\u2013 flat')
        sht_gd['C69'].value = _acc
    else:
        sht_gd['C68'].value = 'warming up'
    _sp = list(zip(_spot_dt, _spot_hist))[::-1]            # newest first
    _blk = []
    for _j in range(SPOT_HIST):
        if _j < len(_sp):
            _t, _s = _sp[_j]
            _d = round(_s - _sp[_j + 1][1], 1) if _j + 1 < len(_sp) else None
            _blk.append([_t.strftime('%H:%M:%S'), round(_s, 2), _d])
        else:
            _blk.append([None, None, None])
    sht_gd['B74'].value = _blk

    strikes = state['strikes']; tk = state['tk']
    got = sum(1 for k in strikes if has_greeks(tk[(k, 'C')]))
    if got < 5:
        return 'options not in yet - table left unchanged'

    exp_dt = datetime.datetime.strptime(expiry, '%Y%m%d').replace(hour=20, tzinfo=datetime.timezone.utc)
    T = max((exp_dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds(), 0) / (365 * 24 * 3600)
    M = 100 * SCALE
    table = []
    # ---- raw per-strike inputs, captured for the archive only ----
    # These values already exist in this loop and were previously discarded. Nothing
    # downstream reads this dict except archive_snapshot(); the Greek math, the Excel
    # writes and every signal path are untouched. Keyed by round(strike) to match
    # qual_by_strike and the archiver's row lookup.
    raw_by_strike = {}
    net = dict(Gamma=0, Zomma=0, Dex=0, Vex=0, Vega=0, Vomma=0, Speed=0, Charm=0)
    for k in strikes:
        ct, pt = tk[(k, 'C')], tk[(k, 'P')]
        g = ct.modelGreeks
        if not has_greeks(ct):
            # No call greeks this cycle -> Greeks archive as 0 (unchanged behaviour), but
            # OI and any put IV that DID arrive are still worth keeping.
            raw_by_strike[round(k)] = (iv_of(ct), iv_of(pt),
                                       oi(ct.callOpenInterest), oi(pt.putOpenInterest))
            table.append([k, 0, 0, 0, 0, 0, 0, 0, 0]); continue
        iv = g.impliedVol
        cg = greeks(spot, k, T, iv, 'C'); pg = greeks(spot, k, T, iv, 'P')
        coi, poi = oi(ct.callOpenInterest), oi(pt.putOpenInterest)
        # iv is the CALL's IV and is fed to both legs above -- that is existing behaviour
        # and is deliberately NOT changed here. put_iv is captured raw for the record.
        raw_by_strike[round(k)] = (iv, iv_of(pt), coi, poi)
        toi = coi + poi; oi_net = coi - poi
        gex = GEX_SIGN * cg['gamma'] * oi_net * M * spot * spot * 0.01
        dex = DEX_SIGN * (cg['delta'] * coi + pg['delta'] * poi) * M * spot
        vex = VEX_SIGN * cg['vanna'] * oi_net * M * spot
        table.append([
            k,
            cg['gamma'] * toi * M * spot * spot * 0.01,
            gex,
            cg['zomma'] * oi_net * M * spot * spot * 0.01,
            dex,
            vex,
            cg['vomma'] * VEGA_PER * toi * M,
            cg['vega']  * VEGA_PER * toi * M,
            cg['speed'] * oi_net * M * spot * spot * 0.0025,
        ])
        net['Gamma'] += cg['gamma'] * oi_net
        net['Zomma'] += cg['zomma'] * oi_net
        net['Dex']   += cg['delta'] * coi + pg['delta'] * poi
        net['Vex']   += cg['vanna'] * oi_net
        net['Vega']  += cg['vega']  * toi
        net['Vomma'] += cg['vomma'] * toi
        net['Speed'] += cg['speed'] * oi_net
        net['Charm'] += cg['charm'] * coi + pg['charm'] * poi

    # (moved here: raw_by_strike is only populated by the per-strike loop above;
    #  calling skew_monitor before it raised UnboundLocalError every cycle)
    # ---- SKEW MONITOR -> King Node Model O11/P11, O12/P12, AB16 ----
    # Written at runtime like AB12 (GEX SLOPE): the engine supplies BOTH the labels and
    # the values, so the workbook file itself needs no edit and no formula. Observation
    # only -- nothing downstream reads these cells.
    _atm_iv = _atm_iv_dir = None
    # ---- ATM IV direction -> 'Level Engine'!B3 (D5 reads it; C5 override still wins) ----
    # Same two-half rolling engine as VIX/VVIX/VIX1D (P4/P5/P6). Uses the ATM CALL IV
    # because greeks() feeds the call's IV into both legs -- that is the vol that moves
    # gamma and zomma. Writes nothing if the chain cannot bracket spot, in which case D5
    # falls back to "FLAT" and zomma goes Dormant rather than guessing.
    try:
        _calls = [(k, v[0]) for k, v in raw_by_strike.items()
                  if isinstance(v[0], (int, float)) and v[0] > 0]
        _atm_iv = _interp_iv(_calls, spot)
        if _atm_iv:
            _atmiv_hist.append(float(_atm_iv))
            _atm_iv_dir = _two_half_dir(_atmiv_hist, IVDIR_DB_ATM)
            sht_le['B3'].value = _atm_iv_dir
    except Exception as e:
        print(f"   ! ATM IV direction skipped ({e})")

    _ps = _cs = _rr = None
    if SKEW_ENABLED:
        try:
            _ps, _cs, _rr, _sk_head, _sk_put, _sk_call = skew_monitor(raw_by_strike, spot)
            sht['O11'].value = 'Put skew:'
            sht['P11'].value = _sk_put
            sht['O12'].value = 'Call skew:'
            sht['P12'].value = _sk_call
            sht['AB16'].value = _sk_head
            # ---- Master Dashboard row 22 ----
            # E22 is an EMPTY, ALREADY-FRAMED spacer row inside the readout box (E22 carries
            # the table's left wall, N22 the right), sitting directly under the GEX SLOPE
            # line at E21:N21 -- the same engine-written-text pattern. Writing E22 lets the
            # string spill E->N (~160 chars of room; the longest skew line is ~120), so it
            # renders as a native row of the table with NO merge, NO border edit and NO
            # change to the workbook file itself.
            #
            # NOT row 16: F16 is already merged F16:N16 for the Vol regime line, whose own
            # output runs to ~80 chars. Splitting it F:J / K:O would truncate BOTH lines
            # (K:O holds ~75 chars, the skew line needs 120) and would require unmerging a
            # live merge -- the exact operation that has silently corrupted this workbook.
            if sht_md is not None and MD_LAYOUT_OK and MD_SKEW_CELL:
                sht_md[MD_SKEW_CELL].value = _sk_head[:155]
        except Exception as e:
            print(f"   ! skew monitor skipped ({e})")

    # ---- smoothing: average the last SMOOTH_N readings ----
    _buf.append(table)
    n_buf = len(_buf)
    smoothed = [
        [table[i][0]] +
        [round(sum(_buf[b][i][c] for b in range(n_buf)) / n_buf) for c in range(1, 9)]
        for i in range(len(table))
    ]
    sht[f'A{FIRST_DATA_ROW}'].value = smoothed

    # ---- Net GEX intraday monitor -> King Node Model AB12 (Master Dashboard E21 GEX SLOPE row reads it) ----
    # smoothed row = [strike, gamma, gex, zomma, dex, vex, vomma, vega, speed]; index 2 = GEX.
    net_gex_now = sum(smoothed[i][2] for i in range(len(smoothed))
                      if isinstance(smoothed[i][2], (int, float)))
    _v1d_up = (sht['P6'].value == "Up")          # Front-End Bidding (VIX1D dir)
    _vvx_up = (sht['P5'].value == "Up")          # VVIX dir (confirmation)
    sht['AB12'].value = gex_monitor(net_gex_now, time.time(), _v1d_up, _vvx_up)

    # ---- Vol Tension -> King Node Model AB17 (Master Dashboard F18 reads it) ----
    # MUST run after gex_monitor (publishes _gex_per15) and after skew_monitor
    # (publishes _skew_state). Writes AB17 only -- F18 is a formula, so this line
    # needs no Master Dashboard handle and no row offset.
    try:
        _vt_ratio = None
        _vix, _v1d = sht['B5'].value, sht['F5'].value
        if isinstance(_vix, (int, float)) and isinstance(_v1d, (int, float)) and _vix:
            _vt_ratio = float(_v1d) / float(_vix)
        sht['AB17'].value = vol_tension(net_gex_now, _vt_ratio, _v1d_up)
    except Exception as e:
        print(f"   ! vol tension skipped ({e})")

    # ---- NET GEX @ open+5 (09:35 ET) baseline -> King Node Model AB15 (Master line 20 'vs open+5') ----
    global _gex_open5
    if _gex_open5 is None:
        _et5 = et_now()
        if (_et5.hour, _et5.minute) >= (9, 35) and _et5.hour < 16:
            _gex_open5 = net_gex_now
    if _gex_open5 is not None:
        sht['AB15'].value = _gex_open5

    # ---- vomma peak monitor: sum near-spot |vomma|, flag peak / roll-over ----
    # smoothed row = [strike, gamma, gex, zomma, dex, vex, vomma, vega, speed]; index 6 = vomma.
    near_vomma = sum(abs(smoothed[i][6]) for i in range(len(smoothed))
                     if isinstance(smoothed[i][6], (int, float))
                     and abs(smoothed[i][0] - spot) <= VOMMA_NEAR)
    _vomma_hist.append(near_vomma)
    _vomma_times.append(datetime.datetime.now().strftime('%H:%M:%S'))
    vstat, vsig, vref, vpct = vomma_status(list(_vomma_hist), VOMMA_ROLL, VOMMA_RISE)
    sht_gd['C54'].value = vstat
    sht_gd['C55'].value = round(vref)
    sht_gd['E55'].value = round(vpct * 100, 1)
    rows = list(zip(_vomma_times, _vomma_hist))[::-1]            # newest first
    block = []
    for j in range(VOMMA_HIST):
        if j < len(rows):
            t, v = rows[j]
            d = round(v - rows[j + 1][1]) if j + 1 < len(rows) else None
            block.append([t, round(v), d])
        else:
            block.append([None, None, None])
    sht_gd['B58'].value = block

    flag = {'Gamma': GEX_SIGN, 'Dex': DEX_SIGN, 'Vex': VEX_SIGN}
    order = ['Gamma', 'Zomma', 'Dex', 'Vex', 'Vega', 'Vomma', 'Speed']
    flags_row = [('Pos' if net[gk] * flag.get(gk, 1) >= 0 else 'Neg') for gk in order]
    sht['A8:G8'].value = [flags_row]
    charm_flag = 'Pos' if net['Charm'] * CHARM_SIGN >= 0 else 'Neg'
    sht['H8'].value = charm_flag                         # net charm sign -> Matrix CharmPos(Q)/CharmNeg(P) overlay
    _write_oedge()
    _write_nvanna()                              # neg-gamma near-vanna zones -> DT9:DT55 (fat Vega + extreme Vex)
    # ---- level lock: recalc, read raw levels, apply hysteresis, write locked to W ----
    _recalc_full()                                       # full recalc (chain-independent): V (raw levels) + F (vol states) fresh

    _apply_dedge_hold(spot)                              # route reaction table to DEX edges in chop (BG9 hold)

    # ---- vomma gate: a trigger only stands if price is at the matching vol-reinforced level ----
    if VOMMA_GATE and vsig in ('long', 'short'):
        def _lead_num(x):
            if isinstance(x, (int, float)):
                return float(x)
            if isinstance(x, str):
                try:
                    return float(x.strip().split(' ')[0].replace(',', ''))
                except ValueError:
                    return None
            return None
        def _at_level(states_rng, levels_rng, tag):
            states = sht_le.range(states_rng).value
            levels = sht_le.range(levels_rng).value
            for st, lv in zip(states, levels):
                ln = _lead_num(lv)
                if isinstance(st, str) and tag in st and ln is not None and abs(ln - spot) <= VOMMA_GATE_NEAR:
                    return True
            return False
        if vsig == 'long' and not _at_level('F18:F23', 'A18:A23', 'VOMMA BID'):
            sht_gd['C54'].value = vstat.replace('LONG trigger', 'gated \u2014 no VOMMA BID level')
        elif vsig == 'short' and not _at_level('F9:F14', 'A9:A14', 'VOMMA CAP'):
            sht_gd['C54'].value = vstat.replace('SHORT trigger', 'gated \u2014 no VOMMA CAP level')

    # ---- trigger latch: hold a fired LONG/SHORT on screen >= VOMMA_HOLD secs so it can't blink past ----
    now_m = time.monotonic()
    final_c54 = sht_gd['C54'].value or ''
    if ('LONG trigger' in final_c54) or ('SHORT trigger' in final_c54):
        _vomma_latch['text'] = final_c54                  # fresh, un-gated trigger -> (re)start the hold
        _vomma_latch['until'] = now_m + VOMMA_HOLD
    elif _vomma_latch['text'] and now_m < _vomma_latch['until']:
        secs = int(round(_vomma_latch['until'] - now_m))  # still holding -> keep it visible + countdown
        sht_gd['C54'].value = f"{_vomma_latch['text']}  \u00b7 held {secs}s"
    else:
        _vomma_latch['text'] = None                       # hold expired -> let live status show

    raw_R = _read_levels('V9:V14')                       # raw R1..R6
    raw_S = _read_levels('V18:V23')                      # raw S1..S6
    thr = sht_le['BG9'].value                            # R/S flip threshold (pts)
    thr = thr if isinstance(thr, (int, float)) else 5
    strikes_col = sht_le.range('AA9:AA55').value         # strike per row
    # per-strike state flags for the archive (read-only; blank on failure)
    try:
        _an_col = sht_le.range('AN9:AN55').value
        _ax_col = sht_le.range('AX9:AX55').value
        _ay_col = sht_le.range('AY9:AY55').value
        _dt_col = sht_le.range('DT9:DT55').value
        _state_by_strike = {}
        for _s, _an, _ax, _ay, _dt in zip(strikes_col, _an_col, _ax_col, _ay_col, _dt_col):
            if isinstance(_s, (int, float)):
                _state_by_strike[round(float(_s))] = (_an, _ax, _ay, _dt)
    except Exception as e:
        _state_by_strike = {}
        print(f"   ! state-flag read failed ({e}); revflag/ax_vomma/ay_accel archive blank")
    box_col     = sht_le.range('AN9:AN55').value         # box flag (1 = boxed) per row
    box_flags = {}
    for s, b in zip(strikes_col, box_col):
        if isinstance(s, (int, float)):
            box_flags[float(s)] = 1 if b == 1 else 0

    # ---- first-touch tracker (feeds Level Engine EI9:EI55; CU9 zomma-veto exemption) ----
    # A resistance strike K's FIRST TOUCH completes when spot has reached K and then
    # pulled back to K-10 (hysteresis mirrors roll_reclaim's break tolerance). EI=1 before
    # and during that first test, 0 forever after (per engine session). Support side not
    # tracked yet (exemption is resistance-only). Read-only degradation: if this column
    # is never written, EI is blank and the CU9 exemption simply never fires.
    global _ft_state
    try:
        _ft_state
    except NameError:
        _ft_state = {}          # strike -> {'in': bool, 'done': bool}
    _ei_col = []
    for _s in strikes_col:
        if isinstance(_s, (int, float)):
            _k = float(_s)
            _st = _ft_state.setdefault(_k, {'in': False, 'done': False})
            if not _st['done']:
                if spot >= _k:
                    _st['in'] = True
                elif _st['in'] and spot <= _k - 10.0:
                    _st['done'] = True; _st['in'] = False
            _ei_col.append([0 if _st['done'] else 1])
        else:
            _ei_col.append([None])
    sht_le['EI9:EI55'].value = _ei_col
    raw_R, raw_S = apply_rs_hysteresis(raw_R, raw_S, spot, thr, box_flags)  # hold each level's side until price clears its box edge by thr
    _locked_R, _pend_R = apply_lock(_locked_R, _pend_R, raw_R, spot, 'R')
    _locked_S, _pend_S = apply_lock(_locked_S, _pend_S, raw_S, spot, 'S')
    _locked_R = dedup_levels(_locked_R, raw_R)           # no strike may occupy two slots
    _locked_S = dedup_levels(_locked_S, raw_S)
    sht_le['W9:W14'].value  = [[(_locked_R[i] if i < len(_locked_R) else None)] for i in range(6)]
    sht_le['W18:W23'].value = [[(_locked_S[i] if i < len(_locked_S) else None)] for i in range(6)]

    _apply_chop_yield(spot)      # dEdge must not override a NEARER locked level

    # ---- shelf/wall hysteresis: read the raw CM/CN detection, damp it, write the
    #      locked copy to CT/CW (which the table, column R and the Q/A band read) ----
    def _read_sw(d, e, fr, t):
        dv = sht_le[d].value; ev = sht_le[e].value
        frv = sht_le[fr].value; tv = sht_le[t].value
        if dv == 1 and isinstance(ev, (int, float)) and isinstance(frv, (int, float)):
            return (round(ev), round(frv), tv if isinstance(tv, str) else "")
        return None
    rawR = _read_sw('CM2', 'CM3', 'CM4', 'CM9')
    rawS = _read_sw('CN2', 'CN3', 'CN4', 'CN9')
    _swR_lock, _swR_pend = apply_sw_lock(_swR_lock, _swR_pend, rawR)
    _swS_lock, _swS_pend = apply_sw_lock(_swS_lock, _swS_pend, rawS)
    if _swR_lock:
        sht_le['CT3'].value = _swR_lock[0]; sht_le['CT4'].value = _swR_lock[1]; sht_le['CT9'].value = _swR_lock[2]
    else:
        sht_le['CT3'].value = None; sht_le['CT4'].value = None; sht_le['CT9'].value = None
    if _swS_lock:
        sht_le['CW3'].value = _swS_lock[0]; sht_le['CW4'].value = _swS_lock[1]; sht_le['CW9'].value = _swS_lock[2]
    else:
        sht_le['CW3'].value = None; sht_le['CW4'].value = None; sht_le['CW9'].value = None

    # ---- Front-End Bidding resistance-warning hysteresis -> Level Engine CT14 (Master border reads it) ----
    wh = sht_le['CT12'].value                            # hold cycles (user-set)
    wh = int(wh) if isinstance(wh, (int, float)) and wh >= 1 else SW_LOCK_HOLD
    _w_v1u = (sht['P6'].value == "Up")                   # Front-End Bidding active (VIX1D dir, Line 16)
    _w_vvu = (sht['P5'].value == "Up")                   # VVIX confirmation
    sht_le['CT14'].value = apply_warn_hysteresis(_w_v1u, _w_vvu, wh)

    # ---- roll+reclaim observation marker -> Level Engine!CT26 (Master support blue border) ----
    try:
        sht_le['CT26'].value = apply_roll_reclaim(spot, _locked_S, sht['F5'].value, sht['B5'].value)
    except Exception:
        pass

    _recalc_full()                                       # full recalc (chain-independent): refresh displays that read W + CT/CW

    # ---- Neg-gamma UNSAFE per-row raspberry hysteresis -> Level Engine CT19:CT24 (Master resolver reads them) ----
    # Shares the hold count wh (from CT12) with the amber border; holds each reaction row's raspberry
    # alert wh cycles after UNSAFE clears so the danger border doesn't flicker. Counters live in Python
    # globals (no extra sheet cells). Read after calculate() so the L neg-gamma formulas are fresh; the
    # raw-UNSAFE term in the resolver covers the current cycle, the held flag carries the persistence.
    if sht_md is not None and MD_LAYOUT_OK:
        for _i, _lc in enumerate(MD_NEGG_CELLS):
            _unsafe = 'UNSAFE' in str(sht_md[_lc].value or '')
            sht_le['CT' + str(19 + _i)].value = apply_negg_hysteresis(_i, _unsafe, wh)

    sht['K26'].value = 'Updated ' + datetime.datetime.now().strftime('%H:%M:%S')

    # ---- archive this completed cycle to CSV ----
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    vv = sht['B5:F5'].value                              # [B5, C5, D5, E5, F5] -> vix, _, vvix, _, vix1d
    if isinstance(vv, (list, tuple)) and len(vv) >= 5:
        vix_v, vvix_v, vix1d_v = vv[0], vv[2], vv[4]
    else:
        vix_v = vvix_v = vix1d_v = None
    # per-strike CV floors (AM=confl, AC=|gamma|) keyed by strike, so a backtest can
    # reconstruct why a near level did / did not qualify (supQual needs confl>=3 and the
    # confl/|gamma| floors). Read-only; failure never blocks the archive write.
    qual_by_strike = {}
    try:
        _aa = sht_le.range('AA9:AA55').value
        _am = sht_le.range('AM9:AM55').value
        _ac = sht_le.range('AC9:AC55').value
        # AR = strength score the top-6 ranking sorts on; BB = the resulting rank tag.
        # Archived so "why did level X drop out of the locked list at HH:MM" is answerable
        # offline. Without them the max-gamma node's 53 in/out flips a session cannot be
        # diagnosed without a full replay.
        _ar = sht_le.range('AR9:AR55').value
        _bb = sht_le.range('BB9:BB55').value
        # qualification outcome + absorption-veto inputs (added 2026-07-17). Read back
        # from the computed Level Engine so a backtest can see, per strike per cycle,
        # whether a level qualified (CU/CV) and which veto (BK / DH via DC / CZ) fired.
        _cu = sht_le.range('CU9:CU55').value     # resQual(R) 0/1
        _cv = sht_le.range('CV9:CV55').value     # supQual(S) 0/1
        _bk = sht_le.range('BK9:BK55').value     # absorbed by stronger reversal neighbour
        _dh = sht_le.range('DH9:DH55').value     # absorbed into shelf/edge
        _dc = sht_le.range('DC9:DC55').value     # gamma-shelf candidate
        _cz = sht_le.range('CZ9:CZ55').value     # dEdge
        def _v(x): return x if x is not None else ""
        for _k, _cf, _ag, _rs, _rt, _cuv, _cvv, _bkv, _dhv, _dcv, _czv in zip(
                _aa, _am, _ac, _ar, _bb, _cu, _cv, _bk, _dh, _dc, _cz):
            if isinstance(_k, (int, float)):
                qual_by_strike[round(_k)] = (_v(_cf), _v(_ag), _v(_rs), _v(_rt),
                                             _v(_cuv), _v(_cvv), _v(_bkv),
                                             _v(_dhv), _v(_dcv), _v(_czv))
    except Exception as e:
        print(f"   ! qual map read failed ({e}); confl/abs_gamma/ar_score/rank_tag/"
              f"cu_qual/cv_qual/bk/dh/dc/cz will archive blank")
    # shelf/wall lock band (cycle-level): the locked CT/CW copies the reaction table
    # substitutes from. Read-only; a failure here archives the band blank, never blocks
    # the write. min/max so lo<=hi regardless of which of CT3/CT4 holds the near edge.
    _ct_lo = _ct_hi = _cw_lo = _cw_hi = ""
    try:
        _ct3 = sht_le['CT3'].value; _ct4 = sht_le['CT4'].value
        _cw3 = sht_le['CW3'].value; _cw4 = sht_le['CW4'].value
        if isinstance(_ct3, (int, float)) and isinstance(_ct4, (int, float)):
            _ct_lo, _ct_hi = min(_ct3, _ct4), max(_ct3, _ct4)
        if isinstance(_cw3, (int, float)) and isinstance(_cw4, (int, float)):
            _cw_lo, _cw_hi = min(_cw3, _cw4), max(_cw3, _cw4)
    except Exception as e:
        print(f"   ! shelf/wall band read failed ({e}); ct_lo/ct_hi/cw_lo/cw_hi will archive blank")

    archive_snapshot(ts, spot, vix_v, vvix_v, vix1d_v, flags_row, charm_flag,
                     _locked_R, _locked_S, smoothed, qual_by_strike, raw_by_strike,
                     _es_s200, _es_s400, _ps, _cs, _rr,
                     _atm_iv, _atm_iv_dir,
                     _ct_lo, _ct_hi, _cw_lo, _cw_hi,
                     _state_by_strike)

    sht['K26'].value = 'Updated ' + ts[11:]
    smooth_label = f'avg {n_buf}/{SMOOTH_N}' if n_buf < SMOOTH_N else f'avg {SMOOTH_N}'
    r1 = _locked_R[0] if _locked_R else '-'
    s1 = _locked_S[0] if _locked_S else '-'
    return f'updated ({smooth_label}) R1 {r1} / S1 {s1} ({got}/{len(strikes)} strikes)'


def reconnect(wait_between=20):
    """Re-establish the Gateway session and resubscribe everything after a drop.
       Called by the main loop whenever the connection is lost or a cycle errors.
       Returns True on success; never raises. The next archived cycle after a
       successful reconnect is stamped event=RECONNECT so the replay can show the
       feed gap."""
    global spx, vix_t, vvix_t, vix1d_t, state, _es_ticker, _next_event
    try:
        ib.disconnect()
    except Exception:
        pass
    time.sleep(wait_between)
    try:
        ib.connect('127.0.0.1', PORT, clientId=1)
        ib.reqMarketDataType(INDEX_TYPE)
        spx     = get_ticker(ib, Index('SPX',   'CBOE', 'USD'))
        vix_t   = get_ticker(ib, Index('VIX',   'CBOE', 'USD'))
        vvix_t  = get_ticker(ib, Index('VVIX',  'CBOE', 'USD'))
        vix1d_t = get_ticker(ib, Index('VIX1D', 'CBOE', 'USD'))
        s = best_price(spx)
        if math.isnan(s):
            print("   ! reconnected but no SPX price yet")
            return False
        state = build_window(s)                 # old subscriptions died with the session
        _buf.clear()                            # smoothing restarts on the fresh window
        _gex_hist.clear()                       # slope restarts on the new window (sign/flip persist)
        if TA_ENABLED and _es_contract is not None:
            try:
                _es_ticker = ib.reqTickByTickData(_es_contract, 'AllLast', 0, False)
                _es_ticker.updateEvent += on_es_tick
            except Exception as e:
                print(f"   ! ES resubscribe failed ({e}); TA panel will use seed only")
        _next_event = "RECONNECT"               # stamp the first cycle after the gap
        return True
    except Exception as e:
        print(f"   ! reconnect failed: {e}")
        return False


if GEX_SEED_HISTORY:
    _ng_seeded = seed_gex_history()
    if _ng_seeded:
        _flip = (f"flipped {'POS' if _gex_sign > 0 else 'NEG'}"
                 if _gex_flip_t is not None
                 else f"{'POS' if _gex_sign > 0 else 'NEG'} held")
        print(f"Seeded Net GEX history: {_ng_seeded} cycles from today's archive ({_flip}).")
    else:
        print("Net GEX history: no archive yet today; will accumulate live.")

print(f"\nLive. {REFRESH}s refresh, {SMOOTH_N}-reading smooth, {LOCK_HOLD}-cycle level lock. Ctrl+C to stop.\n")
print(f"Archiving snapshots to: {ARCHIVE_DIR}\n")
try:
    while True:
        try:
            if not ib.isConnected():
                raise ConnectionError("gateway connection lost")
            if RUN_OUTSIDE_HOURS or market_open():
                spot = best_price(spx)
                if not math.isnan(spot) and abs(spot - state['center']) >= RECENTER_PTS:
                    cancel_window(state)
                    state = build_window(spot)
                    _buf.clear()
                    _vomma_hist.clear(); _vomma_times.clear()
                    _vomma_latch.update(text=None, until=0.0)
                    _spot_hist.clear(); _spot_dt.clear()
                    _locked_R, _locked_S = [], []        # reset lock on recentre (new strikes)
                    _pend_R, _pend_S = {}, {}
                    _swR_lock, _swS_lock = None, None     # reset shelf/wall lock on recentre
                    _swR_pend, _swS_pend = None, None
                    _rs_side.clear()
                    _gex_hist.clear()                     # slope restarts on the new window
                    _next_event = "RECENTER"              # (sign/flip state persists) - stamp archive
                    ib.sleep(8)
                    print(f"   re-centred to {state['center']:.0f}  (buffers + lock cleared)")
                status = refresh()
                print(f"{datetime.datetime.now().strftime('%H:%M:%S')}  {status}")
            else:
                print(f"{datetime.datetime.now().strftime('%H:%M:%S')}  market closed - idling")
            ib.sleep(REFRESH)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            # Gateway auto-restart, network blip, or any transient feed error:
            # keep the dashboard alive, reconnect, and stamp the gap in the archive.
            print(f"{datetime.datetime.now().strftime('%H:%M:%S')}  ! feed error: {e} — reconnecting ...")
            while not reconnect():
                print("   retrying in 30s ... (Ctrl+C to stop)")
                time.sleep(30)
            print(f"   reconnected — resuming (window recentred to {state['center']:.0f})")
except KeyboardInterrupt:
    print("\nStopping ...")
finally:
    ib.disconnect()
    print("Disconnected.")
