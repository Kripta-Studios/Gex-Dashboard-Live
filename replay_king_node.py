# replay_king_node.py  —  play an archived King Node session back through the dashboard
#
#   SYNCED against live_king_node.py (2026-07-31 master). live_king_node.py remains the
#   master file: when the two disagree, live wins and this file gets re-synced.
#
#   2026-07-31 sync — ported the two ENGINE-WRITTEN cells replay had no equivalent for.
#   Both are written by Python, never by a sheet formula, so updating the workbook alone
#   does not supply them:
#     A. nGex-wall box arm-and-hold latch -> Level Engine EQ1 (apply_box_latch).
#     B. PROX no-skip admission flag      -> Level Engine EN9:EN55 (_write_prox).
#   Neither is a real-time flicker smoother, so neither is reduced to raw passthrough:
#   an instantaneous box fires on zero cycles by construction, and without EN no level
#   is ever admitted on proximity. Latch state is cleared on any non-sequential move
#   (seek / step-back) and on a RECONNECT cycle.
#
#   Earlier note (2026-07-20 sync). live_king_node.py remains the
#   master file: when the two disagree, live wins and this file gets re-synced. This sync
#   ported three live behaviours the replay had fallen behind on:
#     1. dEdge challenger hysteresis (_challenge + LOCK_HOLD): a changed chop-box edge must
#        persist LOCK_HOLD cycles before it replaces the held edge (was instant adoption).
#     2. Master Dashboard layout probe (MD_ROW_OFFSET / MD_NEGG_CELLS): the neg-gamma
#        UNSAFE cells are detected structurally, not hardcoded to K32..K39.
#     3. Skew monitor display (O11/O12/P11/P12, KNM AB16, Master skew line): replays the
#        archived put_skew/call_skew/risk_rev through live's exact de-trend state machine,
#        precomputed over the day so jumps and back-steps stay deterministic.
#
#   Reads a king_node_archive_YYYY-MM-DD.csv (written by live_king_node.py) and pushes
#   each saved snapshot into the SAME sheets the live feed writes, so the Dashboard
#   replays exactly as it looked on the day. Never connects to IBKR. Reads data only.
#
#   HOW TO RUN
#     1. Open MASTER_KING_NODE_RECORD_V5_REPLAY.xlsx in Excel (a COPY of the master,
#        NOT the file the live feed drives). This keeps replay off the live dashboard.
#     2. Run:  python replay_king_node.py
#     3. Pick a day if more than one archive exists.
#
#   This drives a SEPARATE copy of the workbook (see WORKBOOK below), so it is safe to
#   run while live_king_node.py is recording: the live feed keeps writing the master
#   file and appending its CSV archive, and replay never connects to IBKR or touches
#   that archive (it only reads it). The two never collide.
#
#   CONTROLS (press while it's running; the keys are live, no Enter needed)
#     SPACE .... pause / resume
#     f  or  ->  faster   (steps up through 0.25 .. 16x)
#     s  or  <-  slower
#     n .......  step forward one cycle   (works while paused)
#     b .......  step back one cycle      (works while paused)
#     j / k ...  jump forward / back 20 MINUTES of session time
#     J / K ...  jump forward / back 1 HOUR of session time
#                (time-based: cycle spacing varies, so a cycle-count jump moved a
#                 different amount of clock time each press. These move what they say.)
#     r .......  restart from the first cycle
#     q  or Esc  quit (leaves the last cycle on screen)
#
#   Speed is bounded at the top end by how fast Excel can recalc each snapshot;
#   16x simply means "go as fast as the sheet allows".

import os
import re
import csv
import math
import sys
import glob
import time
import datetime
from collections import deque
import bisect
import threading
import xlwings as xw

# ---- workbook / files ----
WORKBOOK = r"C:\AMD\Aimee\Trading\Indicators\IBRK King Node Data\MASTER_KING_NODE_RECORD_V5_REPLAY.xlsx"
SHEET, LE_SHEET, GD_SHEET = "King Node Model", "Level Engine", "GEX Depth"
ARCHIVE_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archive-data")
ARCHIVE_FILE = ""        # "" = newest in ARCHIVE_DIR (or prompt if several). Else a filename or full path.

# ---- playback ----
BASE_DELAY      = 1.0                              # seconds per cycle at 1x
SPEEDS          = [0.25, 0.5, 1, 2, 4, 8, 16, 32, 64]
START_SPEED_IDX = 2                               # 1x
# ---- jump keys are TIME-based, not cycle-count based --------------------------
# The old JUMP = 20 skipped 20 CYCLES. Cycles land ~33s apart, so "j" actually moved
# ~11 minutes of session while the banner said "+20" -- easy to read as 20 minutes.
# Worse, cycle spacing is not constant (feed gaps, reconnects, thin prints), so a
# fixed cycle count meant a different amount of clock time on every jump.
# These are minutes of SESSION TIME; _seek_minutes() finds the nearest cycle to
# (current timestamp +/- N minutes), so a jump always moves what it says it moves.
JUMP_MIN        = 20                               # j / k  ->  +/- 20 minutes
JUMP_HOUR_MIN   = 60                               # J / K  ->  +/- 1 hour

# ---- monitor constants (kept identical to live_king_node.py) ----
FIRST_DATA_ROW  = 29
VOMMA_NEAR      = 25
VOMMA_HIST      = 8
VOMMA_ROLL      = 0.05
VOMMA_RISE      = 0.05
VOMMA_GATE      = True
VOMMA_GATE_NEAR = 10
SPOT_HIST       = 8
SPOT_DIR_DB     = 0.05
VEL_WINDOW      = 3

# ---- DEX cushion / break-risk tracker (constants identical to live_king_node.py) ----
DEX_SLOPE_WIN  = 5        # cycles in the slope window (~5 x 30s = 2.5 min)
DEX_FLAT_BAND  = 0.04     # |frac change| below this reads as flat
DEX_FRAC_FRAG  = 0.40     # frac below this = fragile band (neg-gamma break trigger)
DEX_PEAK_FLOOR = 38000    # min cushion (|dex| peak) before a level can be graded
DEX_BRK_HOLD   = 3        # cycles a break-risk verdict must persist before it flips

# ---- vol-direction engine (mirrors live P4/P5/P6) ----
IVDIR_WIN     = 50        # rolling window in cycles (~25 min at 30s)
IVDIR_DB_VIX  = 0.10      # deadband (vol pts)
IVDIR_DB_VVIX = 0.25      # VVIX is noisier -> wider deadband
IVDIR_DB_V1D  = 0.10      # VIX1D deadband (same scale as VIX)
IVDIR_DB_ATM  = 0.001     # ATM strike-IV deadband. Strike IV is a DECIMAL (0.16),
                          # so 0.001 = 0.1 vol pts -- same scale as IVDIR_DB_VIX.
                          # Must match live, or replay diverges from the day.

# ---- Net GEX intraday monitor (mirrors live gex_monitor -> King Node Model AB12) ----
GEX_SLOPE_WIN  = 90       # cycles in the slope window (~45 min at 30s)
# Deadbands for the compression reading on the GEX SLOPE line. Must match
# live_king_node.py exactly or the two engines will disagree on the wording.
IV_FLAT_PP15   = 0.05     # pp/15m; below this ATM IV counts as flat, not moving
GEX_FLAT_M15   = 0.25e6   # Net GEX per 15m, same purpose
WARN_HOLD_DFLT = 3        # CT14 hold fallback = live's SW_LOCK_HOLD

# ---- SKEW MONITOR (observation only; mirrors live O11/O12/P11/P12 + KNM AB16 + MD skew line) ----
# Live computes put/call skew from the raw per-leg IVs each cycle and ARCHIVES the three
# numbers (put_skew / call_skew / risk_rev, vol points). Replay treats the archived numbers
# as authoritative (they are exactly what live computed on the day) and falls back to
# recomputing from the archived per-strike call_iv/put_iv only when those columns predate
# the skew feature. The interpretive STATE (residual direction / steep) is not archived, so
# it is re-run here with live's exact machine, keyed to each cycle's ET clock.
SKEW_ENABLED   = True
SKEW_OFF       = 25.0      # pts either side of spot for the skew wings (must match live)
SKEW_WIN       = 50        # rolling window in cycles (~25 min at 30s)
SKEW_DB        = 0.10      # deadband in VOL POINTS
SKEW_STEEP_PCT = 0.66      # PS residual in the top third of today's range = "steep"
SKEW_BASE      = {"09:30": (2.15, -1.58), "10:00": (2.21, -1.41), "10:30": (2.29, -1.29), "11:00": (2.48, -1.23), "11:30": (2.48, -1.11), "12:00": (2.66, -0.85), "12:30": (2.85, -0.62), "13:00": (3.01, -0.30), "13:30": (3.26, 0.32), "14:00": (3.77, 0.78), "14:30": (4.46, 1.45), "15:00": (4.55, 2.20), "15:30": (4.11, 3.12)}
# ^ same 116-session calibration live uses. Archive timestamps are IRISH local; live's
#   anchors are ET; cycle ET = irish_to_et(archived) (DST-correct, see CLOCKS).
#   This mirrors live's own hardcoded EDT convention (see live et_now()); change together.

# ---- VIX1D session extremes (VOL BOTTOM / VOL TOP -> KNM AB13 / AB14, mirrors live) ----
VOLB_PCT  = 10.0          # % off running low to flag VOL BOTTOM
VOLT_PCT  = 10.0          # % fade off the high to flag VOL TOP
VOLT_PROM = 10.0          # the high must be >= this % above the prior low (a real bid)


# ============ CLOCKS (2026-09-29) ============
# US/Eastern and Irish summer time computed from their published rules, so the clock-change
# weeks come out right without any extra package (Windows Python ships no time-zone data).
#   US Eastern: EDT (UTC-4) from the 2nd Sunday in March 02:00 local to the 1st Sunday in
#               November 02:00 local, else EST (UTC-5).
#   Ireland:    IST (UTC+1) from the last Sunday in March 01:00 UTC to the last Sunday in
#               October 01:00 UTC, else GMT (UTC+0).
# Before this every ET conversion was a fixed UTC-4 (live) / Irish-5h (replay), which is
# 1 h out from 25 Oct (replay) and from 1 Nov (live) until March.
def _nth_sunday(year, month, n):
    d = datetime.datetime(year, month, 1)
    d += datetime.timedelta(days=(6 - d.weekday()) % 7)
    return d + datetime.timedelta(weeks=n - 1)


def _last_sunday(year, month):
    d = datetime.datetime(year + (month == 12), (month % 12) + 1, 1) - datetime.timedelta(days=1)
    return d - datetime.timedelta(days=(d.weekday() + 1) % 7)


def et_offset_hours(utc_naive):
    """-4 (EDT) or -5 (EST) for a naive UTC datetime."""
    y = utc_naive.year
    start = _nth_sunday(y, 3, 2) + datetime.timedelta(hours=7)    # 02:00 EST = 07:00 UTC
    end = _nth_sunday(y, 11, 1) + datetime.timedelta(hours=6)     # 02:00 EDT = 06:00 UTC
    return -4 if start <= utc_naive < end else -5


def utc_to_et(utc_naive):
    return utc_naive + datetime.timedelta(hours=et_offset_hours(utc_naive))


def irish_to_et(local_naive):
    """Archive timestamps are Irish local wall-clock -> naive ET."""
    y = local_naive.year
    start = _last_sunday(y, 3) + datetime.timedelta(hours=1)      # 01:00 UTC
    end = _last_sunday(y, 10) + datetime.timedelta(hours=1)       # 01:00 UTC
    guess = local_naive - datetime.timedelta(hours=1)             # as if IST
    utc = guess if start <= guess < end else local_naive
    return utc_to_et(utc)


def _two_half_dir(hist, deadband):
    """Up / Down / Flat from mean(recent half) - mean(older half), with a deadband.
       Identical to live's engine so replayed directions match live on the same data."""
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


# ============ stateful reads, copied verbatim from the live feed ============
class DexTracker:
    """Per-strike DEX cushion tracker; feeds the break-risk router. Identical to
       live_king_node.py. In replay it is run once forward over the whole session
       and the result cached per cycle (see _precompute_dex), so stepping back,
       jumping and restarting stay correct."""
    def __init__(self):
        self.day = None
        self.peak = {}; self.sign = {}; self.hist = {}
        self.brk = {}; self.pend = {}            # held flag ; (challenger, count)

    def roll_day(self, et_date):
        if self.day != et_date:
            self.day = et_date
            self.peak.clear(); self.sign.clear(); self.hist.clear()
            self.brk.clear(); self.pend.clear()

    def update(self, strike, dex, neg_gamma):
        """Feed this cycle's smoothed dex for a strike -> (frac, slope, peak, brk)."""
        a = abs(dex)
        pk = self.peak.get(strike, 0.0)
        if a > pk:
            self.peak[strike] = pk = a
            self.sign[strike] = 1 if dex >= 0 else -1
        s = self.sign.get(strike, 1 if dex >= 0 else -1)
        oriented = dex * s
        frac = (oriented / pk) if pk > 0 else 0.0
        dq = self.hist.setdefault(strike, deque(maxlen=DEX_SLOPE_WIN))
        old = dq[0] if dq else oriented           # value ~DEX_SLOPE_WIN cycles ago
        dq.append(oriented)
        chg = (oriented - old) / (pk if pk > 0 else 1.0)
        slope = 1 if chg > DEX_FLAT_BAND else (-1 if chg < -DEX_FLAT_BAND else 0)
        raw = 0
        if pk >= DEX_PEAK_FLOOR and (frac < 0 or (neg_gamma and slope < 0 and frac < DEX_FRAC_FRAG)):
            raw = 1
        held = self.brk.get(strike, 0)
        if raw == held:
            self.pend.pop(strike, None)
        else:
            ch, n = self.pend.get(strike, (raw, 0))
            n = n + 1 if ch == raw else 1
            if n >= DEX_BRK_HOLD:
                held = raw; self.pend.pop(strike, None)
            else:
                self.pend[strike] = (raw, n)
        self.brk[strike] = held
        return round(frac, 3), slope, round(pk), held


def _interp_iv(pairs, target):
    """Linear-interpolate IV at `target` strike from [(strike, iv), ...]. None if it
       cannot be bracketed -- never extrapolates off the end of the quoted chain.
       Copied verbatim from live_king_node.py so both engines agree cycle for cycle."""
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


def _precompute_dex(cycles):
    """Run the tracker forward once, exactly as the live feed saw the day, and cache
       [frac, slope, peak, brk] per ladder row per cycle into c['dex_rows']. The order
       matches each cycle's ladder (descending strike), i.e. ladder[i] -> Level Engine
       row 9+i, the same alignment the live feed writes."""
    tr = DexTracker()
    for c in cycles:
        neg = (c['flags'][0] == 'Neg') or c.get('frag') in (1, 1.0)   # 2026-10-09: fragile = negative
        rows = []
        for r in c['ladder']:
            k = r[0]; dx = r[4] if isinstance(r[4], (int, float)) else 0
            fr, sl, pk, bk = tr.update(k, dx, neg)
            rows.append([fr, sl, pk, bk])
        c['dex_rows'] = rows


# ---- DEX DRAIN (2026-09-30, Giggles) -> 'Level Engine'!JT9:JT55 -------------------
# Positive gamma only. A strike within DRAIN_PTS of spot whose |DEX| has fallen to
# DRAIN_FRAC or less of its own peak over the last DRAIN_WIN cycles (peak >= DRAIN_MIN)
# is losing its cushion. Feeds the UNSAFE reason DEXDRAIN (Level Engine HP/HQ ->
# Master Dashboard DC). Built after 7710 on 2026-09-30: DEX -255K -> -86K over five
# minutes, then broken. UNTESTED as a rule. Rough check over 55 archived sessions:
# flagged levels broke within 15 min ~29% of the time vs ~21% for other near-spot
# levels (10-cycle window) -- more likely to break, not likely to break.
# 2026-09-30 (later, Giggles): REPLACED by drain + WEAK VEX (|vex| < DRAIN_VEX). Drain with
# strong VEX broke LESS often than baseline (15% vs 19%); drain + weak VEX broke 39% (n=200).
# Weak-OR-opposed vanna was tested and rejected (29%, n=358: opposed cases diluted it).
DRAIN_WIN  = 10         # cycles of history for the peak (~7 min)
DRAIN_FRAC = 0.5        # current |DEX| at or below this fraction of the peak
DRAIN_MIN  = 150000     # the peak must be at least this big to count
DRAIN_PTS  = 10         # only strikes within this many points of spot
DRAIN_VEX  = 100000     # VEX at the strike must be weaker than this (|vex|)


# 2026-10-01 (Giggles): HYSTERESIS. The raw test sat on its own 50% line and the rolling
# peak "moved the goalposts" (an old high rolling out of the window lifted the ratio and
# cleared the warning with no real DEX recovery - 7700 on 2026-10-01 ~14:45). Now:
#   ON  : raw test true for DRAIN_HOLD cycles in a row; the reference peak is then FROZEN.
#   OFF : |DEX| back to >= DRAIN_FRAC_OFF x the frozen peak, or |VEX| >= DRAIN_VEX_OFF,
#         for DRAIN_HOLD cycles in a row; immediately if the strike leaves the DRAIN_PTS
#         zone or the regime leaves positive gamma.
DRAIN_FRAC_OFF = 0.65   # clears only once |DEX| recovers to this share of the frozen peak
DRAIN_VEX_OFF  = 120000 # ... or |VEX| strengthens to this
DRAIN_HOLD     = 2      # cycles in a row needed to switch on, and to switch off


def drain_step(state, q, kk, a, vx, s, pos):
    """One cycle for one strike. state: dict kk -> {'on','ref','n_on','n_off'};
       q: that strike's |DEX| history deque (already appended). Returns 0/1."""
    st = state.setdefault(kk, {'on': False, 'ref': None, 'n_on': 0, 'n_off': 0})
    in_zone = pos and isinstance(s, (int, float)) and abs(s - kk) <= DRAIN_PTS
    if st['on']:
        if not in_zone or a is None:
            st.update(on=False, ref=None, n_on=0, n_off=0)
            return 0
        rec = (a >= DRAIN_FRAC_OFF * st['ref']) or (isinstance(vx, (int, float)) and abs(vx) >= DRAIN_VEX_OFF)
        st['n_off'] = st['n_off'] + 1 if rec else 0
        if st['n_off'] >= DRAIN_HOLD:
            st.update(on=False, ref=None, n_on=0, n_off=0)
            return 0
        return 1
    raw = False
    pk = max(q) if q else None
    if in_zone and a is not None and pk is not None:
        raw = (pk >= DRAIN_MIN and a <= DRAIN_FRAC * pk
               and isinstance(vx, (int, float)) and abs(vx) < DRAIN_VEX)
    st['n_on'] = st['n_on'] + 1 if raw else 0
    if st['n_on'] >= DRAIN_HOLD:
        st.update(on=True, ref=pk, n_on=0, n_off=0)
        return 1
    return 0


def _precompute_drain(cycles):
    """One forward pass; c['drain'] = 0/1 per ladder row (ladder[i] -> Level Engine
       row 9+i). Deterministic per index, so seeks and restarts stay correct.
       2026-10-01: on/off hysteresis with a frozen reference peak (drain_step)."""
    hist, state = {}, {}
    for c in cycles:
        pos = (c['flags'][0] == 'Pos')
        s = c['spot']
        rows = []
        for r in c['ladder']:
            k, dx, vx = r[0], r[4], r[5]
            if not isinstance(k, (int, float)):
                rows.append(0)
                continue
            kk = round(float(k))
            a = abs(dx) if isinstance(dx, (int, float)) else None
            q = hist.setdefault(kk, deque(maxlen=DRAIN_WIN + 1))
            if a is not None:
                q.append(a)
            rows.append(drain_step(state, q, kk, a, vx, s, pos))
        c['drain'] = rows


def _write_drain(c):
    try:
        v = list(c.get('drain') or [])
        v = (v + [0] * 47)[:47]
        sht_le.range('JT9:JT55').value = [[x] for x in v]
    except Exception as e:
        print(f"   ! DEX drain write skipped ({e})")


def _precompute_vol_gex(cycles, warn_hold):
    """One forward pass, exactly as live saw the day, caching per cycle:
         c['vix_dir'] / c['vvix_dir'] / c['v1d_dir']  -- two-half directions (P4/P5/P6)
         c['net_gex']                                  -- whole-book Net GEX (sum ladder gex)
         c['gex_sign'], c['gex_flip_dt']               -- sign + most recent flip time
         c['warn']                                     -- CT14 Front-End warn latch (0/1)
       Cached up front (like _precompute_dex) so stepping back, jumping and
       restarting stay correct. Same logic as live's incremental engines, so both
       produce identical output on the same archive."""
    vixq, vvixq, v1dq = (deque(maxlen=IVDIR_WIN) for _ in range(3))
    atmq = deque(maxlen=IVDIR_WIN)      # ATM call-IV history -> 'Level Engine'!B3 -> D5
    gex_sign, gex_flip_dt = 0, None
    warn_tier, warn_below = 0, 0
    v_lo = v_hi = None; v_lo_t = v_hi_t = ""; v_hi_prom = 0.0
    for c in cycles:
        # --- vol directions (mirrors live's per-cycle deque append + two-half read) ---
        for v, q in ((c['vix'], vixq), (c['vvix'], vvixq), (c['vix1d'], v1dq)):
            if isinstance(v, (int, float)):
                q.append(float(v))
        c['vix_dir']  = _two_half_dir(vixq,  IVDIR_DB_VIX)
        c['vvix_dir'] = _two_half_dir(vvixq, IVDIR_DB_VVIX)
        c['v1d_dir']  = _two_half_dir(v1dq,  IVDIR_DB_V1D)

        # --- ATM IV direction -> B3 -> D5 (mirrors live exactly) ---------------------
        # Prefer the archived atm_iv_dir: that is what live wrote on the day. Fall back to
        # recomputing from call_iv so older archives still replay. If neither is available
        # the cycle gets "", B3 is left alone, and D5 falls back to C5 / "FLAT".
        _atm = _interp_iv(c.get('ivs') or [], c['spot'])
        if c.get('atm_iv_dir_csv'):
            c['atm_iv_dir'] = c['atm_iv_dir_csv']
        else:
            if _atm:
                atmq.append(float(_atm))
            c['atm_iv_dir'] = _two_half_dir(atmq, IVDIR_DB_ATM) if atmq else ""
        # ATM IV VALUE -> Level Engine C3. Archived value is authoritative (it is what
        # live wrote on the day); fall back to the interpolated call-IV on old archives.
        _av = c.get('atm_iv_csv')
        c['atm_iv'] = float(_av) if isinstance(_av, (int, float)) and _av else (
                      float(_atm) if _atm else None)


        # --- whole-book Net GEX + sign flip (mirrors live gex_monitor's flip logic) ---
        ng = sum(r[2] for r in c['ladder'] if isinstance(r[2], (int, float)))
        c['net_gex'] = ng
        cur = 1 if ng > 0 else (-1 if ng < 0 else gex_sign)
        if cur != 0 and cur != gex_sign:
            if gex_sign != 0:                      # a genuine cross (not the first read)
                gex_flip_dt = c['dt']
            gex_sign = cur
        c['gex_sign'], c['gex_flip_dt'] = gex_sign, gex_flip_dt

        # --- Front-End warn tier latch (mirrors live apply_warn_hysteresis -> CT14) ---
        #   2 = AMBER/CONFIRMED (VIX1D + VVIX both up), 1 = WATCH (VIX1D only), 0 = off.
        #   Latches at the highest tier reached; decays to the current level after
        #   warn_hold cycles below it, so AMBER doesn't flicker on a soft VVIX print.
        cur = 2 if (c['v1d_dir'] == 'Up' and c['vvix_dir'] == 'Up') else \
              (1 if c['v1d_dir'] == 'Up' else 0)
        if cur >= warn_tier:
            warn_tier, warn_below = cur, 0
        else:
            warn_below += 1
            if warn_below >= warn_hold:
                warn_tier, warn_below = cur, 0
        c['warn'] = warn_tier

        # --- VIX1D session extremes -> VOL BOTTOM / VOL TOP texts (mirrors live) ---
        c['volb_txt'] = ""; c['volt_txt'] = ""
        v1 = c['vix1d']
        if isinstance(v1, (int, float)):
            hm = c['dt'].strftime("%H:%M")
            if v_lo is None or v1 < v_lo:
                v_lo, v_lo_t = float(v1), hm
            if v_hi is None or v1 > v_hi:
                v_hi, v_hi_t = float(v1), hm
                v_hi_prom = (v_hi - v_lo) / v_lo * 100 if v_lo else 0.0
            pct_lo = (v1 - v_lo) / v_lo * 100 if v_lo else 0.0
            fade   = (v_hi - v1) / v_hi * 100 if v_hi else 0.0
            if pct_lo >= VOLB_PCT and c['v1d_dir'] == "Up":
                c['volb_txt'] = f"VOL BOTTOM +{pct_lo:.0f}% off LoD {v_lo:.2f} ({v_lo_t})"
            if v_hi_prom >= VOLT_PROM and fade >= VOLT_PCT and c['v1d_dir'] == "Down":
                c['volt_txt'] = f"▽ VOL TOP — VIX1D -{fade:.0f}% off HoD {v_hi:.2f} ({v_hi_t}), front-end fading"


def _precompute_skew(cycles):
    """Run live's skew state machine forward once over the whole day and cache
       (head, put_txt, call_txt) on every cycle, so jumping / stepping back replays
       deterministically. ps/cs/rr come from the archive when present (authoritative);
       otherwise they are recomputed from the archived per-strike call/put IVs with
       live's exact wing math. The residual/direction machine is copied verbatim from
       live_king_node.py skew_monitor(); only the clock differs: live reads et_now(),
       replay derives ET from each cycle's archived timestamp (Irish local - 5h)."""
    if not SKEW_ENABLED:
        for c in cycles:
            c['sk_head'] = c['sk_put'] = c['sk_call'] = None
            c['sk_spans'] = []
            c['sk_steep'] = False
            c['sk_psdir'] = "Flat"
        return
    from collections import deque as _dq
    ps_hist = _dq(maxlen=SKEW_WIN)
    cs_hist = _dq(maxlen=SKEW_WIN)
    ps_lo = ps_hi = None
    cs_lo = cs_hi = None      # call-side extremes (STEEP CALL SKEW), 2026-09-24
    arrow = lambda d: "\u25b2" if d == "Up" else ("\u25bc" if d == "Down" else "\u25ac")
    anch = sorted((int(k[:2]) * 60 + int(k[3:]), v) for k, v in SKEW_BASE.items())
    for c in cycles:
        sp = c['spot']
        ps, cs, rr = c.get('ps_csv'), c.get('cs_csv'), c.get('rr_csv')
        if ps is None and cs is None:
            # pre-skew archive -> recompute raw wings exactly as live does
            calls, puts = c.get('ivs') or [], c.get('pivs') or []
            if len(puts) < 3 or not isinstance(sp, (int, float)):
                c['sk_head'], c['sk_put'], c['sk_call'] = "SKEW  \u2014 no put IV in archive", "n/a", "n/a"
                c['sk_spans'] = []
                continue
            atm_c = _interp_iv(calls, sp)
            atm_p = _interp_iv(puts,  sp)
            atm = (atm_c + atm_p) / 2 if (atm_c and atm_p) else (atm_c or atm_p)
            iv_p = _interp_iv(puts,  sp - SKEW_OFF)
            iv_c = _interp_iv(calls, sp + SKEW_OFF)
            if not atm:
                c['sk_head'], c['sk_put'], c['sk_call'] = "SKEW  \u2014 building", "\u2026", "\u2026"
                c['sk_spans'] = []
                continue
            ps = (iv_p - atm) * 100 if iv_p else None
            cs = (iv_c - atm) * 100 if iv_c else None
            rr = (cs - ps) if (ps is not None and cs is not None) else None
        if ps is None and cs is None:
            c['sk_head'], c['sk_put'], c['sk_call'] = "SKEW  \u2014 n/a", "n/a", "n/a"
            c['sk_spans'] = []
            continue
        if not SKEW_BASE:
            head = ("SKEW  PUT " + (f"{ps:+.1f}" if ps is not None else "n/a")
                    + "vp \u00b7 CALL " + (f"{cs:+.1f}" if cs is not None else "n/a")
                    + "vp" + (f" \u00b7 RR {rr:+.1f}vp" if rr is not None else "")
                    + "   \u2014 states OFF (SKEW_BASE not calibrated)")
            c['sk_head'] = head
            c['sk_spans'] = []
            c['sk_put']  = f"{ps:+.1f}vp" if ps is not None else "n/a"
            c['sk_call'] = f"{cs:+.1f}vp" if cs is not None else "n/a"
            continue
        # baseline interpolation on the CYCLE's ET clock (archived Irish local - 5h)
        _et = irish_to_et(c['dt'])
        _mins = _et.hour * 60 + _et.minute
        if _mins <= anch[0][0]:
            _b = anch[0][1]
        elif _mins >= anch[-1][0]:
            _b = anch[-1][1]
        else:
            for _i in range(1, len(anch)):
                if anch[_i][0] >= _mins:
                    (_t0, _v0), (_t1, _v1) = anch[_i - 1], anch[_i]
                    _w = (_mins - _t0) / (_t1 - _t0)
                    _b = (_v0[0] + (_v1[0] - _v0[0]) * _w,
                          _v0[1] + (_v1[1] - _v0[1]) * _w)
                    break
        ps_r = (ps - _b[0]) if ps is not None else None
        cs_r = (cs - _b[1]) if cs is not None else None
        if ps_r is not None:
            ps_hist.append(ps_r)
            ps_lo = ps_r if ps_lo is None else min(ps_lo, ps_r)
            ps_hi = ps_r if ps_hi is None else max(ps_hi, ps_r)
        if cs_r is not None:
            cs_hist.append(cs_r)
            cs_lo = cs_r if cs_lo is None else min(cs_lo, cs_r)
            cs_hi = cs_r if cs_hi is None else max(cs_hi, cs_r)
        ps_dir = _two_half_dir(ps_hist, SKEW_DB) if ps_r is not None else "Flat"
        cs_dir = _two_half_dir(cs_hist, SKEW_DB) if cs_r is not None else "Flat"
        steep = False
        if ps_r is not None and ps_hi is not None and ps_lo is not None and (ps_hi - ps_lo) > 0.2:
            steep = (ps_r - ps_lo) / (ps_hi - ps_lo) >= SKEW_STEEP_PCT
        # 2026-09-24 FIX: STEEP CALL SKEW could never fire. The branch was gated on
        # `not steep`, and `steep` is the PUT-side test, so the inner `if steep` was always
        # False. The call side now has its own steepness test (call_steep: the call residual
        # in the top SKEW_STEEP_PCT of today's call residual range), mirroring the put test.
        call_steep = False
        if cs_r is not None and cs_hi is not None and cs_lo is not None and (cs_hi - cs_lo) > 0.2:
            call_steep = (cs_r - cs_lo) / (cs_hi - cs_lo) >= SKEW_STEEP_PCT
        # ---- single-sided state machine (mirrors live_king_node.py 2026-09-17) ----
        # One side only, never both. Call replaces put ONLY when put is neutral and
        # call is rising; otherwise put wins and call is suppressed entirely.
        SKEW_RED    = (0xC2, 0x21, 0x18)   # C22118 raspberry red (R,G,B -- was stored reversed and rendered blue until 2026-09-19)
        SKEW_GREEN  = (0x00, 0xB0, 0x50)   # 00B050 green (R,G,B)
        SKEW_ORANGE = (0xFF, 0xA5, 0x00)   # FFA500 orange (R,G,B -- was stored reversed and rendered light blue until 2026-09-19)
        if ps is None:
            skew_label = "PUT SKEW \u2014 n/a"
            skew_rgb   = None
        elif cs_dir == "Up" and ps_dir not in ("Down", "Up") and not steep:
            skew_label = "STEEP CALL SKEW \u2014 upside demand building" if call_steep else \
                         "CALL SKEW \u2014 upside demand building"
            skew_rgb   = SKEW_GREEN
        elif ps_dir == "Down":
            skew_label = "FLATTENING PUT SKEW \u2014 hedging demand easing"
            skew_rgb   = SKEW_ORANGE          # 2026-09-24, Giggles: easing demand is not bearish
        elif steep:
            skew_label = "STEEP PUT SKEW \u2014 strong demand for downside protection"
            skew_rgb   = SKEW_RED
        elif ps_dir == "Up":
            skew_label = "STEEPENING PUT SKEW \u2014 hedging demand building"
            skew_rgb   = SKEW_RED
        else:
            skew_label = "PUT SKEW NEUTRAL"
            skew_rgb   = SKEW_ORANGE
        head = "SKEW  " + skew_label
        if rr is not None:
            head += f"   (RR {rr:+.1f}vp)"
        sk_spans = []
        if skew_rgb is not None:
            _lbl_start = len("SKEW  ") + 1
            _lbl_len   = len(skew_label)
            sk_spans = [(_lbl_start, _lbl_len, skew_rgb)]
        c['sk_head'] = head
        c['sk_spans'] = sk_spans
        c['sk_put']  = f"{ps:+.1f}vp {arrow(ps_dir)}" if ps is not None else "n/a"
        c['sk_call'] = f"{cs:+.1f}vp {arrow(cs_dir)}" if cs is not None else "n/a"
        # cached for vol_tension() -- live reads these off _skew_state
        c['sk_steep'] = bool(steep)
        c['sk_psdir'] = ps_dir


def gex_monitor_line(cycles, idx):
    """Display string for King Node Model AB12 at cycle idx (drives the Master
       Dashboard GEX SLOPE row). Windowed over the archive, so seeks stay correct;
       string format matches live's gex_monitor exactly. The slope window restarts
       at any RECENTER/RECONNECT marker (live clears its deque there) so the slope
       never spans a strike-window jump; sign/flip persist across markers, as live's do."""
    c = cycles[idx]
    win = cycles[max(0, idx - GEX_SLOPE_WIN): idx + 1]
    for j in range(len(win) - 1, 0, -1):       # newest marker wins; win[0] needs no cut
        if win[j].get('event'):
            win = win[j:]                       # marker cycle starts the new window
            break
    slope_txt = "GEX SLOPE  … building"
    rising = False
    c['gex_per15'] = None
    if len(win) >= 2:
        t0, g0 = win[0]['dt'], win[0]['net_gex']
        dt_min = max((c['dt'] - t0).total_seconds() / 60.0, 0.5)
        per15  = (c['net_gex'] - g0) / dt_min * 15.0
        rising = per15 > 0
        c['gex_per15'] = per15
        arrow  = "▲" if per15 > 0 else ("▼" if per15 < 0 else "▬")
        slope_txt = f"GEX SLOPE  {arrow} {per15/1e6:+.1f}M/15m"
    if c['gex_flip_dt'] is not None:
        mins = int((c['dt'] - c['gex_flip_dt']).total_seconds() / 60)
        flip_txt = f"flipped {'POS' if c['gex_sign'] > 0 else 'NEG'} {mins}m ago"
    else:
        flip_txt = (f"{'POS' if c['gex_sign'] > 0 else 'NEG'} held all session"
                    if c['gex_sign'] else "—")
    line = f"{slope_txt}  ·  {flip_txt}"
    if rising and c['v1d_dir'] == 'Up' and c['vvix_dir'] != 'Up':
        line += "  ·  ⚠ vol-bid tension"

    # --- compression reading: GEX rate vs ATM IV rate, in plain English -----------
    # Mirrors live_king_node.gex_monitor() #4 exactly. Live keeps a timestamped ATM IV
    # deque; here the archive already holds atm_iv per cycle, so the same window the
    # slope uses (win, after any RECENTER cut) supplies both rates. Measuring the two
    # over the SAME window is the whole point of the pairing.
    # OBSERVATION ONLY. States what the two rates are doing together; implies no
    # direction -- growing cushion with fading fear is COMPRESSION, not a breakout.
    _ivw = [w for w in win if isinstance(w.get('atm_iv'), (int, float)) and w['atm_iv']]
    if len(_ivw) >= 2 and c['gex_per15'] is not None:
        _iv0 = _ivw[0]['atm_iv'] * 100.0
        _ivn = _ivw[-1]['atm_iv'] * 100.0
        _dtm = max((c['dt'] - _ivw[0]['dt']).total_seconds() / 60.0, 0.5)
        _iv15 = (_ivn - _iv0) / _dtm * 15.0
        _arrow = ("▲" if _iv15 > IV_FLAT_PP15
                  else "▼" if _iv15 < -IV_FLAT_PP15 else "▬")
        line += f"  ·  ATM IV {_ivn:.1f}% {_arrow} {_iv15:+.2f}pp/15m"

        _g_up = c['gex_per15'] > GEX_FLAT_M15
        _g_dn = c['gex_per15'] < -GEX_FLAT_M15
        _i_up = _iv15 > IV_FLAT_PP15
        _i_dn = _iv15 < -IV_FLAT_PP15
        if _g_up and _i_dn:
            _read = "CUSHION GROWING, FEAR FADING — dips get bought back to the node"
        elif _g_up and _i_up:
            _read = "CUSHION GROWING BUT FEAR RISING — the two disagree, stand down"
        elif _g_dn and _i_dn:
            _read = "CUSHION SHRINKING, FEAR FADING — drift, nothing pressing"
        elif _g_dn and _i_up:
            _read = "CUSHION SHRINKING, FEAR RISING — support thins as it is tested"
        else:
            _read = "CUSHION AND FEAR BOTH STEADY — no compression read"
        line += f"  ·  {_read}"
    return line


# ---- VOL TENSION (King Node Model AB17 -> Master Dashboard line 18) ----
# Copied verbatim from live_king_node.py vol_tension(); only the inputs differ.
# Live reads module globals (_gex_per15, _gex_flip_t, _skew_state); replay passes the
# per-cycle cached equivalents so both engines produce the identical string.
VT_SLOW_PCT  = 1.5     # < this = SLOW      (% of |Net GEX| per 15 min)
VT_FAST_PCT  = 4.0     # > this = FAST
VT_FLIP_MIN  = 30      # a sign flip this recent outranks every other label
VT_SHOCK_RAT = 0.90    # VIX1D/VIX at or above this, with a steep put skew, = dislocation
VT_MAXLEN    = 133     # F18 spills F->N = 133.8 chars; past N it escapes the box wall


def vol_tension(net_gex, ratio, v1d_up, per15, flip_age, steep, ps_dir):
    """net_gex  : whole-book Net GEX this cycle
       ratio    : VIX1D / VIX  (None if either leg is missing)
       v1d_up   : bool, VIX1D direction is Up (King Node Model P6)
       per15    : Net GEX slope per 15 min (None until the window is full)
       flip_age : minutes since the last Net GEX sign flip (None if never flipped)
       steep    : bool, steep put skew this cycle
       ps_dir   : 'Up' / 'Down' / 'Flat', put-skew residual direction
       Returns 'VOL TENSION  LABEL  -  condition  -  expect', or a building//no-data line."""
    try:
        if not net_gex:
            return "VOL TENSION  \u2026 no Net GEX this cycle"
        if per15 is None:
            return "VOL TENSION  \u2026 building (slope window not full)"

        neg   = net_gex < 0
        pace  = abs(per15) / abs(net_gex) * 100.0
        band  = "SLOW" if pace < VT_SLOW_PCT else ("FAST" if pace > VT_FAST_PCT else "MOD")
        deepening = (per15 < 0) if neg else (per15 > 0)

        bid   = bool(v1d_up) or (ratio is not None and ratio > 0.75)
        ps_up = ps_dir == "Up"
        ps_dn = ps_dir == "Down"

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

        cond = [f"{net_gex/1e6:+.1f}M",
                f"{'deepening' if deepening else 'easing'} "
                + (f"{pace:.1f}%/15m" if pace < 99.9 else ">99%/15m"),
                f"{'bid' if bid else 'quiet'}" + (f" {ratio:.2f}" if ratio is not None else ""),
                "skew " + ("steep" if steep else
                           "steepening" if ps_up else
                           "easing" if ps_dn else "neutral")]

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


# ---- GEX SLOPE TAPE (mirrors live's tape_line -> Master Dashboard, line under GEX SLOPE) ----
# Same three encodings as live: colour = sign, glyph = magnitude tiered against the
# whole session so far, suffix = change vs the previous bucket. Constants and glyph
# ladder are copied from live_king_node.py and must stay in step with it.
TAPE_BUCKET_SECS = 300
TAPE_SHOW        = 24
TAPE_FLAT_PCT    = 10.0
TAPE_TICK        = 6
TAPE_GLYPHS      = "▁▃▅▇█"
TAPE_SEP         = "│"
TAPE_GAP         = "╎"
TAPE_LIVE        = "◄"
TAPE_POS_UP  = (0x15, 0x80, 0x3D)   # dark green   — positive, growing
TAPE_POS_DN  = (0x4A, 0xDE, 0x80)   # light green  — positive, fading
TAPE_NEG_UP  = (0x6D, 0x28, 0xD9)   # dark purple  — negative, growing
TAPE_NEG_DN  = (0xC4, 0xB5, 0xFD)   # light purple — negative, fading
TAPE_FLAT    = (0xFF, 0xD9, 0xA0)   # peach — flat
TAPE_MARK    = (0x80, 0x80, 0x80)
TAPE_GAP_RGB = (0xB4, 0x53, 0x09)


def build_tape(cycles):
    """Precompute (text, spans) for every cycle index. Walks forward once, so the
       tiering at index i sees ONLY buckets at or before i -- no lookahead, exactly
       what live has available at that moment. Seeks stay correct because every index
       carries its own finished line."""
    out, order, vals, gaps = [], [], {}, set()
    for idx, c in enumerate(cycles):
        win = cycles[max(0, idx - GEX_SLOPE_WIN): idx + 1]
        for j in range(len(win) - 1, 0, -1):
            if win[j].get('event'):
                win = win[j:]
                break
        bkt = int(c['dt'].timestamp() // TAPE_BUCKET_SECS)
        if c.get('event'):
            gaps.add(bkt)                       # slope window restarted in this bucket
        if len(win) >= 2:
            dt_min = max((c['dt'] - win[0]['dt']).total_seconds() / 60.0, 0.5)
            per15  = (c['net_gex'] - win[0]['net_gex']) / dt_min * 15.0
            if bkt not in vals:
                order.append(bkt)
            vals[bkt] = per15
        if not order:
            out.append(("GEX TAPE  … building", []))
            continue
        mags = sorted(abs(vals[k]) for k in order)
        n = len(mags)
        edges = [mags[min(int(q * n), n - 1)] for q in (0.2, 0.4, 0.6, 0.8)]
        head = f"GEX TAPE  max {edges[3] / 1e6:.1f}M  "
        first = max(0, len(order) - TAPE_SHOW)
        toks = []
        for i in range(first, len(order)):
            b = order[i]
            if b in gaps and i > first:
                toks.append((TAPE_GAP, TAPE_GAP_RGB))
            elif i > first and (i - first) % TAPE_TICK == 0:
                toks.append((TAPE_SEP, TAPE_MARK))
            v = vals[b]
            m = abs(v)
            tier = sum(1 for e in edges if m > e)
            prev = vals[order[i - 1]] if i > 0 else None
            if v == 0 or prev is None or prev == 0:
                rgb = TAPE_FLAT
            else:
                d = (m - abs(prev)) / abs(prev) * 100.0
                if d > TAPE_FLAT_PCT:
                    rgb = TAPE_POS_UP if v > 0 else TAPE_NEG_UP
                elif d < -TAPE_FLAT_PCT:
                    rgb = TAPE_POS_DN if v > 0 else TAPE_NEG_DN
                else:
                    rgb = TAPE_FLAT
            toks.append((TAPE_GLYPHS[tier], rgb))
        toks.append((TAPE_LIVE, TAPE_MARK))
        text  = head + " ".join(ch for ch, _ in toks)
        base  = len(head) + 1
        out.append((text, [(base + 2 * k, 1, rgb) for k, (_, rgb) in enumerate(toks)]))
    return out


def _tape_targets(rng):
    """Distinct COM objects worth trying, in preference order. The merge anchor matters
       because Characters() addresses the top-left cell of a merged range."""
    base = getattr(rng, "api", rng)
    out = [("range", base)]
    try:
        import win32com.client.gencache as _g
        out.append(("range/gencache", _g.EnsureDispatch(base)))
    except Exception:
        pass
    try:
        anchor = base.MergeArea.Cells(1, 1)
        out.append(("anchor", anchor))
        try:
            import win32com.client.gencache as _g
            out.append(("anchor/gencache", _g.EnsureDispatch(anchor)))
        except Exception:
            pass
    except Exception:
        pass
    return out


def _tape_chars(api, start, length):
    """Return the Characters sub-range for [start, length] on a cell.

       2026-08-03, settled by chain isolation: Range.Characters is a PARAMETERIZED
       PROPERTY, and every pywin32 binding -- the xlwings wrapper, raw CDispatch, and
       gencache early binding alike -- exposes it as a plain no-argument property. So
       `api.Characters` hands back the Characters object for the WHOLE cell, and calling
       that is what raised 'Characters object is not callable' / 'Member not found'.
       There is no attribute spelling that fixes this.

       The arguments have to go through the property GET itself, which means invoking the
       dispid directly. That is what IDispatch::Invoke with DISPATCH_PROPERTYGET does, and
       it is the only path that reaches the two-argument form."""
    import pythoncom, win32com.client
    ole = getattr(api, "_oleobj_", None)
    if ole is None:
        raise AttributeError("object exposes no _oleobj_; cannot invoke Characters")
    dispid = ole.GetIDsOfNames(0, "Characters")
    raw = ole.Invoke(dispid, 0, pythoncom.DISPATCH_PROPERTYGET, 1, start, length)
    return win32com.client.Dispatch(raw)


_tape_probed = False


def tape_paint(rng, spans):
    """Colour each token in place. Characters() is 1-based; COM packs the colour B-G-R,
       not R-G-B. Reports which path worked on the first successful run, and reads a
       character back to confirm the colour actually stuck -- a silent failure here is
       worse than a loud one, because the line still looks plausible, just monochrome."""
    global _tape_probed
    if not spans:
        return
    last = None
    for name, api in _tape_targets(rng):
        try:
            for start, length, (r, g, b) in spans:
                _tape_chars(api, start, length).Font.Color = r + (g << 8) + (b << 16)
            st, _, (r0, g0, b0) = spans[0]
            want = r0 + (g0 << 8) + (b0 << 16)
            try:
                got = _tape_chars(api, st, 1).Font.Color
            except Exception:
                got = want          # cannot verify; assume the writes above landed
            if got != want:
                print(f"   ! TAPE COLOUR DID NOT STICK via {name}: char {st} reads {got}, "
                      f"expected {want} -- the line will render monochrome")
            elif not _tape_probed:
                _tape_probed = True
                print(f"   TAPE COLOUR ok via {name}")
            return
        except Exception as e:
            last = f"{name}: {type(e).__name__}: {e}"
    print(f"   ! TAPE COLOUR FAILED on every path -- last {last}")


# ---- Vol Tension line -> Master Dashboard, written as a VALUE and part-coloured ----
# 2026-09-19. F18 used to be a formula reading King Node Model AB17. Excel discards
# character formatting on a formula result, so the only way to colour one phrase of the
# line is to write the text itself into the cell -- the same reason the GEX TAPE line is
# a value. AB17 is still written every cycle as before; this is an additional write.
# The target is resolved from the row's own "Vol Tension" label (never a hardcoded row)
# and is disabled if it still holds a formula, so a misresolved row can never destroy one.
VT_BLUE_PHRASE = "resistance leaks \u2014 dips shallow"
VT_GREEN_PHRASE = "supports firming \u2014 bounces carry"   # 2026-09-24, Giggles: green
VT_GREEN_RGB    = (0x00, 0xB0, 0x50)   # 00B050 -- the Skew line green
VT_BLUE_RGB    = (0x18, 0x21, 0xC2)  # 1821C2 blue (R,G,B) -- the shade row 17 showed while its
                                     # red was stored reversed; kept as the Vol Tension blue
MD_VT_CELL     = None                # resolved by the Master Dashboard probe
_vt_base_color = None                # the cell's own font colour, captured at probe time
_vt_last       = None                # last text written; repaint only on change


def vt_write(rng, text):
    """Write the Vol Tension line and colour VT_BLUE_PHRASE blue when it is present.
       The whole cell is first reset to its base colour: Excel can carry the previous
       run's character colour onto new text, which would leave stale blue behind when
       the label changes."""
    global _vt_last
    if text == _vt_last:
        return
    rng.value = text
    try:
        if _vt_base_color is not None:
            getattr(rng, "api", rng).Font.Color = _vt_base_color
        for _ph, (r, g, b) in ((VT_BLUE_PHRASE, VT_BLUE_RGB), (VT_GREEN_PHRASE, VT_GREEN_RGB)):
            i = text.find(_ph) if isinstance(text, str) else -1
            if i < 0:
                continue
            col = r + (g << 8) + (b << 16)
            last = None
            for name, api in _tape_targets(rng):
                try:
                    _tape_chars(api, i + 1, len(_ph)).Font.Color = col
                    last = None
                    break
                except Exception as e:
                    last = f"{name}: {type(e).__name__}: {e}"
            if last:
                print(f"   ! vol tension colour FAILED on every path -- last {last}")
    except Exception as e:
        print(f"   ! vol tension colour skipped ({e})")
    _vt_last = text


# ---- stale dashboard-line sweep (2026-09-22) ----------------------------------
# Every one of these lines is written as a VALUE into whatever row its label sits on.
# When a row is inserted above the block (the "Testing Results" row at 11 on this date),
# the labels move and the engine follows them -- but the cell it used to write to keeps
# the last string it ever received, for good. The dashboard then shows two copies of the
# same line, an old one and a live one, disagreeing (a stale "SKEW ... RR -0.0vp" sat on
# the Vol regime row while the real skew line ran one row below). Nothing reads these
# cells back, so it never errored.
# Each line carries its own tag, so after the probe resolves the targets, any cell in the
# dashboard block carrying a tag that is NOT that tag's resolved target is blanked once
# at startup. Self-healing: the next row insert cleans up after itself on the first cycle.

# ---- MELT-UP WATCH (Master Dashboard 'Melt-up' row) + FLOW lines (2026-09-24) ----
# Built at Giggles's direction. DISPLAY + ARCHIVE ONLY: nothing reads these back, no
# level, UNSAFE warning or reaction-table slot depends on them. UNTESTED -- grade the
# archived mu_n / mu_cond / flow_c15 / flow_p15 before any of it drives anything.
#
# 2026-10-01 (Giggles): the four conditions below were REPLACED by three -- tape up, GEX
# slope positive, Min VEX strike moving up, then (later that day) Low IV regime and VIX1D/VIX
# not falling -- see meltup_line(). mu_n is now 0-5 and mu_cond five characters (tape / slope /
# Min VEX / IV Low / VIX1D-VIX); archives before 2026-10-01 used four conditions (0-4).
# MELT-UP WATCH answers one question: is the TAPE melting up while the GAMMA structure
# says it should not? It only renders in negative gamma or fragile positive gamma (in
# plain positive gamma the regime rows already read melt-up). Former four conditions:
#   price     spot up >= MU_PX_PTS over MU_PX_WIN, and ES above its 5-min 200 SMA
#             (ES part ignored when the ES feed has no SMA yet)
#   vol       ATM IV AND VIX1D/VIX both lower than MU_VOL_WIN ago (vol being sold)
#   flow      15-min call volume > 15-min put volume
#   structure GEX slope turned up, or spot within MU_NEAR_PTS of zero gamma or the flip
# Shown at >= MU_SHOW_N of 4. The count and the condition vector are archived every
# cycle regardless of regime, so the rule can be graded in both.
#
# FLOW: per-strike option volume summed across the strike window.
#   15m     : volume traded in the last FLOW_WIN (sum of per-cycle deltas)
#   session : cumulative session volume on the strikes currently in the window
#   1h      : the last hour as four 15-minute C/P ratios, oldest -> newest, each
#             coloured green (calls leading), orange (balanced), red (puts leading)
#             -- the Skew line shades. Added 2026-09-24 at Giggles's direction.
# The history is seeded from today's archive at startup (seed_flow_history), so a
# restart shows the 15m / 1h readings at once instead of "building".
MU_PX_PTS   = 10.0          # spot rise (pts) over MU_PX_WIN that counts as "tape up"
MU_PX_WIN   = 30 * 60       # seconds
MU_VOL_WIN  = 15 * 60       # seconds
MU_IV_DB    = 0.0005        # ATM IV must be lower by at least this (0.05 vol pts)
MU_RATIO_DB = 0.005         # VIX1D/VIX must be lower by at least this
MU_NEAR_PTS = 10.0          # "structure catching up" distance to zero gamma / flip
MU_SHOW_N   = 5             # render only when all 5 hold (2026-10-01)
MU_MV_WIN   = 15 * 60       # Min VEX strike compared with its value this long ago (2026-10-01)
FLOW_WIN    = 15 * 60       # seconds
FLOW_LEAD   = 1.2           # C/P >= this = CALLS leading; <= 1/this = PUTS leading
MU_COVER    = 0.8           # a window counts once history covers this share of it
FLOW_H1_N   = 4             # 15-minute blocks on the 1h line
FLOW_GREEN  = (0x00, 0xB0, 0x50)   # 00B050 -- Skew line green
FLOW_ORANGE = (0xFF, 0xA5, 0x00)   # FFA500 -- Skew line orange
FLOW_RED    = (0xC2, 0x21, 0x18)   # C22118 -- Skew line raspberry red
FLOW_BASE   = (0x59, 0x59, 0x59)   # 595959 -- the flow rows' own font colour
_flow_painted = {}                 # row key -> last (text, spans) painted; repaint on change

_mu_spot  = deque(maxlen=6000)    # (secs, spot)
_mu_iv    = deque(maxlen=6000)    # (secs, atm_iv)
_mu_ratio = deque(maxlen=6000)    # (secs, vix1d/vix)
_mu_minvex = deque(maxlen=6000)   # (secs, Min VEX strike) -- 2026-10-01
_flow_d   = deque(maxlen=6000)    # (secs, calls_traded, puts_traded) per cycle
_mu_day   = None
# 2026-10-07 (Giggles): FLOW SHIFT replaces the five-condition melt-up watch -- the last flip of the
# 15-min call/put ratio from <= MU_FLIP_LO to >= MU_FLIP_HI (15-min block ending now vs the block before)
MU_FLIP_LO   = 1.0
MU_FLIP_HI   = 1.2
MU_FLIP_HOLD = 15 * 60       # show the shift for this long after it fires
_mu_flip = {'t': None, 'frm': None, 'to': None}


def mu_reset():
    """Clear the melt-up / flow history (new session, or replay seek)."""
    global _mu_day
    for _q in (_mu_spot, _mu_iv, _mu_ratio, _mu_minvex, _flow_d):
        _q.clear()
    _mu_day = None
    _mu_flip.update(t=None, frm=None, to=None)
    try:
        _ivt.update(day=None, hi=None, hi_t=None, cnt=0, lo=None, rb=0)
        _ivf.clear()
        _ivf_st.update(raw=None, cnt=0, held="")
    except NameError:
        pass


def _mu_ago(hist, now, win):
    """Value from roughly `win` seconds ago: the most recent sample at or before now - win
       (2026-09-25: was the oldest sample inside the window, which failed whenever cycles
       were long relative to the window). None until history reaches back that far, or if
       that sample is more than 3 windows old."""
    ref = None
    for _t, _v in hist:
        if _t <= now - win:
            ref = (_t, _v)
        else:
            break
    if ref is None or (now - ref[0]) > 3 * win:
        return None
    return ref[1]


def mu_step(now, spot, atm_iv, vix1d, vix, calls_d, puts_d, calls_cum, puts_cum, minvex=None):
    """Fold one cycle into the history and return the history-based readings.
       Pure function of its inputs plus the history, so replay can rebuild it exactly
       from the archive. `now` is epoch seconds (live: wall clock, replay: archive)."""
    global _mu_day
    _day = int(now // 86400)
    if _mu_day is not None and _day != _mu_day:
        mu_reset()
    _mu_day = _day
    _num = lambda x: isinstance(x, (int, float)) and x == x
    if _num(spot):
        _mu_spot.append((now, float(spot)))
    if _num(atm_iv) and atm_iv > 0:
        _mu_iv.append((now, float(atm_iv)))
    if _num(vix1d) and _num(vix) and vix > 0:
        _mu_ratio.append((now, float(vix1d) / float(vix)))
    if _num(minvex):
        _mu_minvex.append((now, float(minvex)))
    _flow_d.append((now, float(calls_d) if _num(calls_d) else 0.0,
                    float(puts_d) if _num(puts_d) else 0.0))
    pre = {'px': None, 'iv_dn': None, 'ratio_dn': None, 'ratio_nf': None,
           'c15': None, 'p15': None, 'flow_min': 0.0,
           'cs': calls_cum if _num(calls_cum) else None,
           'ps': puts_cum if _num(puts_cum) else None}
    _s0 = _mu_ago(_mu_spot, now, MU_PX_WIN)
    if _s0 is not None and _mu_spot:
        pre['px'] = _mu_spot[-1][1] - _s0
    pre['mv'] = _mu_minvex[-1][1] if _mu_minvex else None
    pre['mv0'] = _mu_ago(_mu_minvex, now, MU_MV_WIN)
    pre['mv_up'] = (None if (pre['mv0'] is None or pre['mv'] is None) else pre['mv'] > pre['mv0'])
    _i0 = _mu_ago(_mu_iv, now, MU_VOL_WIN)
    if _i0 is not None and _mu_iv:
        pre['iv_dn'] = (_mu_iv[-1][1] <= _i0 - MU_IV_DB)
    _r0 = _mu_ago(_mu_ratio, now, MU_VOL_WIN)
    if _r0 is not None and _mu_ratio:
        pre['ratio_dn'] = (_mu_ratio[-1][1] <= _r0 - MU_RATIO_DB)
        pre['ratio_nf'] = (_mu_ratio[-1][1] >= _r0)       # 2026-10-01: VIX1D/VIX not falling over 15 min
    # 1h: FLOW_H1_N consecutive 15-minute blocks ending now, oldest first. A block
    # is None until the history reaches back to (nearly) its start.
    pre['h1'] = []
    _t_first = _flow_d[0][0] if _flow_d else now
    for _b in range(FLOW_H1_N - 1, -1, -1):
        _hi = now - _b * FLOW_WIN
        _lo = _hi - FLOW_WIN
        if _t_first > _lo + (1 - MU_COVER) * FLOW_WIN:
            pre['h1'].append(None)
            continue
        _bw = [(c, p) for (t, c, p) in _flow_d if _lo < t <= _hi]
        pre['h1'].append((sum(c for c, _ in _bw), sum(p for _, p in _bw)))
    _w = [(t, c, p) for (t, c, p) in _flow_d if t > now - FLOW_WIN]
    if _w:
        pre['flow_min'] = (now - _flow_d[0][0]) / 60.0 if _flow_d else 0.0
        if (now - _flow_d[0][0]) >= MU_COVER * FLOW_WIN:
            pre['c15'] = sum(c for _, c, _ in _w)
            pre['p15'] = sum(p for _, _, p in _w)
    # 2026-10-07: FLOW SHIFT -- C/P of the 15-min block ending now vs the block before it (h1[-1], h1[-2])
    pre['now'] = now
    pre['cp'] = pre['cp_prev'] = None
    try:
        if pre['h1'] and pre['h1'][-1] and pre['h1'][-1][1] > 0:
            pre['cp'] = pre['h1'][-1][0] / pre['h1'][-1][1]
        if len(pre['h1']) >= 2 and pre['h1'][-2] and pre['h1'][-2][1] > 0:
            pre['cp_prev'] = pre['h1'][-2][0] / pre['h1'][-2][1]
        if (pre['cp'] is not None and pre['cp_prev'] is not None
                and pre['cp'] >= MU_FLIP_HI and pre['cp_prev'] <= MU_FLIP_LO):
            _mu_flip.update(t=now, frm=pre['cp_prev'], to=pre['cp'])
    except Exception:
        pass
    pre['flip_t'], pre['flip_from'], pre['flip_to'] = _mu_flip['t'], _mu_flip['frm'], _mu_flip['to']
    return pre


def _mu_fk(x):
    """12345 -> '12.3k', 1234567 -> '1.23M'."""
    x = float(x)
    if x >= 1e6:
        return f"{x / 1e6:.2f}M"
    if x >= 1e3:
        return f"{x / 1e3:.1f}k"
    return f"{x:.0f}"


def _cp_read(c, p):
    """(text, span) for one C/P reading. span = (start_0based, length, rgb) covering
       "C/P x.xx  ·  <lead>" (or the lead alone when there are no puts), coloured
       green / orange / red like the Skew line; None when there is nothing to colour."""
    if not p and not c:
        return "no volume on the feed", None
    if not p:
        head = f"calls {_mu_fk(c)}  /  puts 0  \u00b7  "
        tail = "CALLS leading"
        return head + tail, (len(head), len(tail), FLOW_GREEN)
    r = c / p
    if r >= FLOW_LEAD:
        lead, col = "CALLS leading", FLOW_GREEN
    elif r <= 1.0 / FLOW_LEAD:
        lead, col = "PUTS leading", FLOW_RED
    else:
        lead, col = "balanced", FLOW_ORANGE
    head = f"calls {_mu_fk(c)}  /  puts {_mu_fk(p)}  \u00b7  "
    tail = f"C/P {r:.2f}  \u00b7  {lead}"
    return head + tail, (len(head), len(tail), col)


def flow_lines(pre):
    """((15-minute text, spans), (session text, spans)) for the two FLOW rows.
       spans = [(start_1based, length, rgb)], the C/P reading coloured (2026-09-24)."""
    def _mk(prefix, body_span):
        body, sp = body_span
        return prefix + body, ([(len(prefix) + sp[0] + 1, sp[1], sp[2])] if sp else [])
    if pre['c15'] is None:
        l15 = (f"FLOW 15m  \u00b7  building ({pre['flow_min']:.0f} of {FLOW_WIN // 60} min)", [])
    else:
        l15 = _mk("FLOW 15m  \u00b7  ", _cp_read(pre['c15'], pre['p15']))
    if pre['cs'] is None and pre['ps'] is None:
        ls = ("FLOW session  \u00b7  no volume on the feed", [])
    else:
        ls = _mk("FLOW session  \u00b7  ", _cp_read(pre['cs'] or 0.0, pre['ps'] or 0.0))
    return l15, ls


def flow_h1_line(pre):
    """(text, spans) for the 1h row. spans = [(start_1based, length, (r, g, b))],
       one per ratio, coloured by who is leading."""
    head = "FLOW 1h  \u00b7  15m blocks, oldest \u2192 newest  \u25b8  "
    txt, spans = head, []
    for i, blk in enumerate(pre.get('h1') or [None] * FLOW_H1_N):
        if i:
            txt += "   "
        if blk is None:
            txt += "\u2026"
            continue
        c, p = blk
        if not c and not p:
            txt += "\u2014"
            continue
        if not p:
            tok, col = "calls", FLOW_GREEN
        else:
            r = c / p
            tok = f"{r:.2f}"
            col = (FLOW_GREEN if r >= FLOW_LEAD else
                   FLOW_RED if r <= 1.0 / FLOW_LEAD else FLOW_ORANGE)
        spans.append((len(txt) + 1, len(tok), col))
        txt += tok
    return txt, spans


def flow_paint(key, rng, txt, spans):
    """Write one FLOW row and colour its spans. The whole cell is reset to the row's
       own colour first so a reading that changes band never keeps its old colour.
       Repaints only when that row's rendered line changes."""
    if _flow_painted.get(key) == (txt, spans):
        return
    rng.value = txt
    try:
        r, g, b = FLOW_BASE
        getattr(rng, "api", rng).Font.Color = r + (g << 8) + (b << 16)
        for st, ln, (r, g, b) in spans:
            last = None
            for name, api in _tape_targets(rng):
                try:
                    _tape_chars(api, st, ln).Font.Color = r + (g << 8) + (b << 16)
                    last = None
                    break
                except Exception as e:
                    last = f"{name}: {type(e).__name__}: {e}"
            if last:
                print(f"   ! flow colour FAILED on every path -- last {last}")
                break
    except Exception as e:
        print(f"   ! flow colour skipped ({e})")
    _flow_painted[key] = (txt, spans)


def flow_h1_write(rng, txt, spans):
    flow_paint("h1", rng, txt, spans)


def meltup_line(pre, spot, es_last, es_s200, gex_per15, zero_g, flip, regime, fragile,
                phenom=None, iv_regime=None):
    """(display text, count, condition string) for the Melt-up check row.
       2026-10-07 (Giggles): the five-condition MELT-UP WATCH (tape / GEX slope / Min VEX up / IV Low /
       VIX1D-VIX, neg or fragile gamma, Phenomenon naming a melt-up) is REMOVED and replaced by the
       FLOW SHIFT: the 15-min call/put ratio flipping from <= MU_FLIP_LO to >= MU_FLIP_HI (15-min block
       ending now vs the block before). Shown for MU_FLIP_HOLD after it fires, in every regime.
       Archive (9 sessions with flow, 2026-09-24 on): 16 shifts, 81% up after 60 min, +2.8 pts
       (baseline 55%, +1.8); call-heavy flow on its own 57%; adding GEX slope or vol roll removed
       the edge (51-53%). Small sample -- UNTESTED. Archive: mu_n = 1 while shown / 0 / "" (no
       history), mu_cond = "prev>now" C/P. Other arguments kept for the call sites, unused."""
    _num = lambda x: isinstance(x, (int, float)) and x == x
    cp, cpp = pre.get('cp'), pre.get('cp_prev')
    ft, now = pre.get('flip_t'), pre.get('now')
    cond = (f"{cpp:.2f}>{cp:.2f}" if _num(cp) and _num(cpp) else "-")
    if not (_num(cp) and _num(cpp)):
        _h = float(pre.get('flow_min') or 0.0)
        return (f"FLOW SHIFT  \u00b7  not yet measurable \u2014 {_h:.0f} of 30 min of flow history"), "", cond
    if _num(ft) and _num(now) and 0 <= now - ft <= MU_FLIP_HOLD:
        _m = (now - ft) / 60.0
        return (f"FLOW SHIFT \u2191 CALLS  \u00b7  C/P {pre['flip_from']:.2f} \u2192 {pre['flip_to']:.2f}  \u00b7  "
                f"{_m:.0f} min ago  \u00b7  archive: 81% up next hour (n=16, small sample)"), 1, cond
    return (f"FLOW SHIFT  \u00b7  off  \u00b7  C/P {cpp:.2f} \u2192 {cp:.2f}  \u00b7  fires when C/P jumps from "
            f"\u2264 {MU_FLIP_LO:.2f} to \u2265 {MU_FLIP_HI:.2f} within 15 min"), 0, cond


# ---- IV-TOP alert (2026-09-24, Giggles) -> 'Level Engine'!BG78 (flag) / BG79 (the high) ----
# ATM IV set a SESSION high within the last IVTOP_WIN and now sits >= IVTOP_DROP below it,
# for IVTOP_HOLD consecutive cycles (one noisy cycle cannot arm it). Resets on a new session
# high. Read by Level Engine IW (clears the "Vanna SELL, IV still rising" UNSAFE) and IX (the
# green border on a vanna-SELL support once vol has peaked). UNTESTED as a rule: the
# pre-registered test behind it was 13 cases.
IVTOP_DROP = 0.003          # 0.3 vol pts (atm_iv is a fraction)
IVTOP_WIN  = 30 * 60        # the high must be this recent, seconds
IVTOP_HOLD = 2              # consecutive cycles
_ivt = {"day": None, "hi": None, "hi_t": None, "cnt": 0, "lo": None, "rb": 0}


def iv_top_step(now, atm_iv):
    """(flag 0/1, reference high) for this cycle. `now` is epoch seconds.

       2026-09-27 REBOUND RELEASE (Giggles): the alert used to measure only the distance
       below the high, so after IV bottomed and climbed again it kept saying "vol has
       peaked" until the 30-min window from the high ran out (2026-09-23: high 12.90 at
       14:47:39, low 11.88 at 15:01:42, IV back to 12.40 by 15:03:44 and still flagged).
       Now: track the lowest IV since the reference high; once IV rebounds IVTOP_DROP off
       that low for IVTOP_HOLD consecutive cycles, the rebound becomes the new reference
       high (flag off). A later drop of IVTOP_DROP from it, within IVTOP_WIN, fires again."""
    day = int(now // 86400)
    if _ivt["day"] != day:
        _ivt.update(day=day, hi=None, hi_t=None, cnt=0, lo=None, rb=0)
    if not (isinstance(atm_iv, (int, float)) and atm_iv == atm_iv and atm_iv > 0):
        return (1 if _ivt["cnt"] >= IVTOP_HOLD else 0), _ivt["hi"]
    iv = float(atm_iv)
    if _ivt["hi"] is None or iv > _ivt["hi"]:
        _ivt.update(hi=iv, hi_t=now, cnt=0, lo=iv, rb=0)
    else:
        _ivt["lo"] = iv if _ivt.get("lo") is None else min(_ivt["lo"], iv)
    if _ivt["lo"] <= _ivt["hi"] - IVTOP_DROP and iv >= _ivt["lo"] + IVTOP_DROP:
        _ivt["rb"] = _ivt.get("rb", 0) + 1
        if _ivt["rb"] >= IVTOP_HOLD:
            _ivt.update(hi=iv, hi_t=now, cnt=0, lo=iv, rb=0)
    else:
        _ivt["rb"] = 0
    cond = (now - _ivt["hi_t"]) <= IVTOP_WIN and iv <= _ivt["hi"] - IVTOP_DROP
    _ivt["cnt"] = _ivt["cnt"] + 1 if cond else 0
    return (1 if _ivt["cnt"] >= IVTOP_HOLD else 0), _ivt["hi"]


# ---- FAST ATM IV direction (2026-09-24, Giggles) -> 'Level Engine'!BG80 ---------------------
# The vanna reading (Level Engine IY -> reaction-table Vanna column J) and the "Vanna SELL, IV
# still rising" UNSAFE (IW) use THIS direction instead of the slow two-half ATM IV direction
# (D5), which averages ~25 minutes and lagged a retest by ~20 minutes (7740 on 2026-09-23:
# ATM IV fell 12.6% -> 11.9% into the retest while D5 still read UP, so the column showed BUY
# on a level that sold). Change in ATM IV over the last IVFAST_WIN, dead zone IVFAST_DB.
# Blank until the window is covered; the sheet then falls back to D5. Archived (atm_iv_fast).
# 2026-09-24 (later): also drives the VOL-BOUNCE pairing (Level Engine GV vannaOK and EX, the
# neg-gamma Min VEX reversal flag), at Giggles's direction, with a 2-cycle hold. Untested:
# the pre-registered slow-vs-fast test had 1 qualifying support touch in 36 sessions.
IVFAST_WIN = 5 * 60         # seconds
IVFAST_DB  = 0.001          # 0.1 vol pts (atm_iv is a fraction)
_ivf = deque(maxlen=2000)   # (secs, atm_iv)
IVFAST_HOLD = 2             # consecutive cycles a new reading must hold
_ivf_st = {"raw": None, "cnt": 0, "held": ""}


def iv_fast_step(now, atm_iv):
    """'UP' / 'DOWN' / 'FLAT', or '' while the window is building."""
    if _ivf and int(_ivf[-1][0] // 86400) != int(now // 86400):
        _ivf.clear()
        _ivf_st.update(raw=None, cnt=0, held="")
    if isinstance(atm_iv, (int, float)) and atm_iv == atm_iv and atm_iv > 0:
        _ivf.append((now, float(atm_iv)))
    if not _ivf:
        return ""
    # 2026-09-25 FIX: anchor on the most recent sample AT OR BEFORE now - IVFAST_WIN. The old
    # test took the oldest sample INSIDE the window and needed it >= 4 min old, so once engine
    # cycles slowed past ~75 s (they now run ~45-110 s) the newest in-window sample was
    # routinely < 4 min old, the window never "covered" and BG80 stayed blank for good.
    old = None
    for t, v in _ivf:
        if t <= now - IVFAST_WIN:
            old = (t, v)
        else:
            break
    if old is None or (now - old[0]) > 3 * IVFAST_WIN:
        _ivf_st.update(raw=None, cnt=0, held="")
        return ""
    d = _ivf[-1][1] - old[1]
    raw = "UP" if d >= IVFAST_DB else ("DOWN" if d <= -IVFAST_DB else "FLAT")
    # 2026-09-24: IVFAST_HOLD-cycle hold. The same reading also drives the vol-bounce
    # pairing, which clears every UNSAFE warning on a Ⓥ level, so one noisy cycle must not
    # switch it. Until a reading has held, the previous held value stands.
    if raw == _ivf_st["raw"]:
        _ivf_st["cnt"] += 1
    else:
        _ivf_st.update(raw=raw, cnt=1)
    if _ivf_st["cnt"] >= IVFAST_HOLD:
        _ivf_st["held"] = raw
    return _ivf_st["held"]

MD_LINE_TAGS = ("SKEW ", "VOL TENSION ", "GEX TAPE ", "GEX SLOPE ", "SPOT UP", "SPOT DOWN",
                "SQUEEZE ", "CHARM ", "MELT-UP WATCH", "FLOW ")
# 2026-09-25: was "MELT-UP" -- that also matched the E9 LABEL "Melt-up check", so the startup
# sweep deleted the label on every restart and the melt-up line switched itself off.


def _clear_stale_md_lines(sht_md, targets, rows=range(5, 40), cols=("E", "F")):
    """Blank tagged engine lines left behind on rows the labels have moved off."""
    keep = {str(t).upper() for t in targets if t}
    n = 0
    try:
        for _r in rows:
            for _c in cols:
                _ref = f"{_c}{_r}"
                if _ref.upper() in keep:
                    continue
                try:
                    if str(sht_md[_ref].formula or "").startswith("="):
                        continue          # never touch a formula cell
                    _v = sht_md[_ref].value
                except Exception:
                    continue
                if isinstance(_v, str) and _v.strip().upper().startswith(MD_LINE_TAGS):
                    sht_md[_ref].value = None
                    n += 1
        if n:
            print(f"Master Dashboard: cleared {n} stale engine line(s) left on rows the "
                  f"labels have moved off")
    except Exception as e:
        print(f"   ! stale-line sweep skipped ({e})")


def _vt_resolve(sht_md, rows):
    """Find the 'Vol Tension' label in column E and return the F cell beside it, or None.
       Refuses a target that still holds a formula."""
    global _vt_base_color
    for _r in rows:
        if str(sht_md[f"E{_r}"].value or "").strip().lower() == "vol tension":
            _c = f"F{_r}"
            try:
                if str(sht_md[_c].formula or "").startswith("="):
                    print(f"   ! MD probe: {_c} still holds a FORMULA - vol tension "
                          f"colour DISABLED (AB17 still written)")
                    return None
                _vt_base_color = sht_md[_c].api.Font.Color
            except Exception:
                pass
            return _c
    print("   ! MD probe: 'Vol Tension' label not found - vol tension colour DISABLED")
    return None


def vomma_status(hist, roll, rise):
    if len(hist) < 3:
        return 'warming up', 'none', (hist[-1] if hist else 0), 0.0
    peak = max(hist); trough = min(hist); latest = hist[-1]
    peak_idx   = len(hist) - 1 - hist[::-1].index(peak)
    trough_idx = len(hist) - 1 - hist[::-1].index(trough)
    if peak_idx >= trough_idx:
        if peak_idx == len(hist) - 1:
            return 'RISING / AT PEAK', 'none', peak, 0.0
        pct = (peak - latest) / peak if peak > 0 else 0.0
        if pct >= roll:
            return f'ROLLED OVER -{pct*100:.0f}% - LONG trigger', 'long', peak, pct
        return 'peaked - watching', 'none', peak, pct
    else:
        if trough_idx == len(hist) - 1:
            return 'FALLING / AT TROUGH', 'none', trough, 0.0
        pct = (latest - trough) / trough if trough > 0 else 0.0
        if pct >= rise:
            return f'TURNED UP +{pct*100:.0f}% - SHORT trigger', 'short', trough, pct
        return 'troughed - watching', 'none', trough, pct


def move_velocity(hist, dts, window):
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


# ============ load + reshape the archive ============
def _fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _inum(x):
    try:
        return int(round(float(x)))
    except (TypeError, ValueError):
        return 0


def load_cycles(path):
    """Group the one-row-per-strike CSV back into ordered cycles."""
    cycles = []
    cur_ts, cur = None, None
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            ts = row['timestamp']
            if ts != cur_ts:
                if cur:
                    cycles.append(cur)
                cur_ts = ts
                cur = {
                    'ts':   ts,
                    'dt':   datetime.datetime.strptime(ts, '%Y-%m-%d %H:%M:%S'),
                    'spot': _fnum(row['spot']),
                    'vix':  _fnum(row['vix']), 'vvix': _fnum(row['vvix']), 'vix1d': _fnum(row['vix1d']),
                    'flags': [row['flag_gamma'], row['flag_zomma'], row['flag_dex'],
                              row['flag_vex'], row['flag_vega'], row['flag_vomma'], row['flag_speed']],
                    'charm_flag': row.get('flag_charm', ''),
                    'R': [_fnum(row.get(f'r{i}')) for i in range(1, 7)],
                    'S': [_fnum(row.get(f's{i}')) for i in range(1, 7)],
                    'event': (row.get('event') or '').strip(),
                    # atm_iv_dir exists only on v49+ archives (__v2 onward). If present it is
                    # what live actually wrote -> authoritative, reproduces the day exactly.
                    'atm_iv_dir_csv': (row.get('atm_iv_dir') or '').strip(),
                    # archived atm_iv value (v49+). Live writes it to Level Engine C3.
                    'atm_iv_csv': _fnum(row.get('atm_iv')),
                    # archived skew numbers (v51+ archives). What live actually computed
                    # on the day -> authoritative for the replayed skew display.
                    'ps_csv': _fnum(row.get('put_skew')),
                    'cs_csv': _fnum(row.get('call_skew')),
                    'rr_csv': _fnum(row.get('risk_rev')),
                    'ivs': [],          # [(strike, call_iv)] -> ATM IV when no atm_iv_dir col
                    'pivs': [],         # [(strike, put_iv)]  -> skew fallback on old archives
                    'ladder': [],
                    'oi': [],           # [(row_idx, [call_oi, put_oi])] -> KNM K/L
                    'vol_by_strike': {},   # {strike: vol_delta} -> Level Engine FQ (2026-09-09 port)
                    # 2026-09-24 melt-up / flow inputs. ES last + 5-min SMA200 are
                    # cycle-level. Archives written 2026-09-23 onward (before the live fix of
                    # 2026-09-24) carry regime_key..es_val each shifted one column right, which
                    # shows as a '|'-delimited regime key sitting in es_val: read the ES last
                    # from the rt_boxrow column in that case.
                    'es_last': _fnum(row.get('rt_boxrow') if '|' in (row.get('es_val') or '')
                                     else row.get('es_last')),
                    'es_s200': _fnum(row.get('es_sma200_5m')),
                    'fl_cd': 0.0, 'fl_pd': 0.0, 'fl_cc': None, 'fl_pc': None,
                    # 2026-09-29 vanna latch inputs (per strike) + fast IV direction + regime
                    'vx': {}, 'rv': {}, 'qt': {},
                    # 2026-10-02 merged vanna override: per-strike DEX + archived backer tokens
                    'dx': {}, 'gx': {}, 'co': {}, 'po': {},
                    'ivfast': (row.get('atm_iv_fast') or '').strip().upper(),
                    'gneg': (row.get('flag_gamma') or '').strip() == 'Neg',
                    # 2026-10-01: archived Spot Up / Vol Up state (svx_dir > 0) -> arrival-vanna switch-back
                    'svx': _fnum(row.get('svx_dir')),
                    # 2026-10-01: archived fragile hold as live published it to BG76 (frag_pos).
                    # 'frag_has' False = archive predates the column -> rebuilt by _precompute_fragile.
                    'frag_has': 'frag_pos' in row,
                    'frag': _fnum(row.get('frag_pos')),
                }
            _k, _civ = _fnum(row['strike']), _fnum(row.get('call_iv'))
            if isinstance(_k, (int, float)) and isinstance(_civ, (int, float)) and _civ > 0:
                cur['ivs'].append((_k, _civ))
            _piv = _fnum(row.get('put_iv'))
            if isinstance(_k, (int, float)) and isinstance(_piv, (int, float)) and _piv > 0:
                cur['pivs'].append((_k, _piv))
            for _fk, _col in (('fl_cd', 'call_vol_d'), ('fl_pd', 'put_vol_d'),
                              ('fl_cc', 'call_vol'), ('fl_pc', 'put_vol')):
                _fv = _fnum(row.get(_col))
                # 2026-09-29: skip feed sentinels archived as volume (e.g. 4,294,967,295) -- mirrors live
                if isinstance(_fv, (int, float)) and _fv == _fv and 0 <= _fv < (1e6 if _col.endswith('_d') else 1e8):
                    cur[_fk] = (cur[_fk] or 0.0) + _fv
            if isinstance(_k, (int, float)):
                cur['vx'][round(float(_k))] = _fnum(row.get('vex'))
                cur['rv'][round(float(_k))] = 1 if _fnum(row.get('revflag')) == 1 else 0
                cur['qt'][round(float(_k))] = (row.get('qual_tag') or '').strip()
                cur['dx'][round(float(_k))] = _fnum(row.get('dex'))
                cur['gx'][round(float(_k))] = _fnum(row.get('gex'))
                _st_ = _inum(row.get('oi_stall')) if 'oi_stall' in row else 0
                cur['co'][round(float(_k))] = None if _st_ else _fnum(row.get('call_oi'))
                cur['po'][round(float(_k))] = None if _st_ else _fnum(row.get('put_oi'))
            _vd = _fnum(row.get('vol_delta'))
            if isinstance(_k, (int, float)) and isinstance(_vd, (int, float)):
                cur['vol_by_strike'][round(float(_k))] = _vd
            cur['ladder'].append((
                _inum(row['row_idx']),
                [_fnum(row['strike']), _inum(row['gamma']), _inum(row['gex']), _inum(row['zomma']),
                 _inum(row['dex']), _inum(row['vex']), _inum(row['vomma']), _inum(row['vega']), _inum(row['speed'])],
            ))
            # ---- per-strike OPEN INTEREST (sync 2026-08-08, mirrors live) ----
            # live writes King Node Model K/L every cycle; the Master Dashboard
            # wall-composition panel reads them. Kept in a parallel list rather than
            # appended to the ladder row so the A:I block written to the sheet keeps
            # its exact 9-column arity -- the ladder write is positional.
            # A strike the archive marked oi_stall carries frozen numbers, so it is
            # blanked here for the same reason live blanks it: stale OI must never
            # render as live.
            _stall = _inum(row.get('oi_stall')) if 'oi_stall' in row else 0
            cur['oi'].append((
                _inum(row['row_idx']),
                [None, None] if _stall else
                [_fnum(row.get('call_oi')), _fnum(row.get('put_oi'))],
            ))
        if cur:
            cycles.append(cur)

    for c in cycles:
        c['ladder'].sort(key=lambda x: x[0])               # restore top-to-bottom (descending strike) order
        c['ladder'] = [v for _, v in c['ladder']]
        c['oi'].sort(key=lambda x: x[0])
        c['oi'] = [v for _, v in c['oi']]
        sp = c['spot']
        c['near_vomma'] = sum(abs(r[6]) for r in c['ladder']
                              if isinstance(r[6], (int, float)) and isinstance(r[0], (int, float))
                              and abs(r[0] - sp) <= VOMMA_NEAR)

    # gap duration on each reconnect cycle = time since the previous archived cycle
    for i, c in enumerate(cycles):
        c['gap_secs'] = None
        if c.get('event') == 'RECONNECT' and i > 0:
            c['gap_secs'] = (c['dt'] - cycles[i - 1]['dt']).total_seconds()
    return cycles


# ============ PRIOR-DAY SPX PROFILE (30-min TPO) ============
# 2026-09-29 (Giggles): yesterday's POC / VAH / VAL as a standard 30-minute TPO profile on
# SPX (RTH 09:30-16:00 ET, 1-pt rows, 70% value area, two-row expansion). SPX has no traded
# volume, so this is time-at-price, not volume -- it reproduced Giggles's 09-28 levels
# (7699 / 7717 / 7686) to within 1 pt from the 09-28 archive snapshots. Live builds it from
# 1-min SPX bars; replay from the previous day's archive. Display only -- nothing reads it.
PRIOR_TPO_ENABLED = True
TPO_BRACKET_MIN   = 30          # minutes per TPO period
TPO_ROW_PTS       = 1.0         # price row height (SPX pts)
TPO_VALUE_AREA    = 0.70        # value-area share of TPOs
MD_PRIOR_ROW      = 77          # Master Dashboard: F77:F79 = POC / VAH / VAL, H77:H79 = session
_prior_tpo = {'date': None, 'poc': None, 'vah': None, 'val': None, 'for_day': None, 'tried': 0.0}


def tpo_levels(brackets, row=TPO_ROW_PTS, va=TPO_VALUE_AREA):
    """brackets: iterable of (high, low), one per TPO period. Returns (poc, vah, val)."""
    counts = {}
    for hi, lo in brackets:
        if hi is None or lo is None:
            continue
        for i in range(int(math.floor(lo / row)), int(math.floor(hi / row)) + 1):
            counts[i] = counts.get(i, 0) + 1
    if not counts:
        return None, None, None
    ks = sorted(counts); mid = (ks[0] + ks[-1]) / 2.0
    poc = max(ks, key=lambda k: (counts[k], -abs(k - mid)))
    total = sum(counts.values()); lo = hi = poc; acc = counts[poc]
    while acc < va * total and (lo > ks[0] or hi < ks[-1]):
        up = (counts.get(hi + 1, 0) + counts.get(hi + 2, 0)) if hi < ks[-1] else -1
        dn = (counts.get(lo - 1, 0) + counts.get(lo - 2, 0)) if lo > ks[0] else -1
        if up >= dn:
            acc += counts.get(hi + 1, 0) + counts.get(hi + 2, 0); hi = min(hi + 2, ks[-1])
        else:
            acc += counts.get(lo - 1, 0) + counts.get(lo - 2, 0); lo = max(lo - 2, ks[0])
    return poc * row, hi * row, lo * row


def tpo_brackets(points):
    """points: iterable of (et_datetime, high, low). Groups RTH prints into 30-min periods."""
    br = {}
    for t, h, l in points:
        m = (t.hour * 60 + t.minute) - (9 * 60 + 30)
        if m < 0 or m >= 390 or h is None or l is None:
            continue
        k = m // TPO_BRACKET_MIN
        if k in br:
            br[k] = (max(br[k][0], h), min(br[k][1], l))
        else:
            br[k] = (h, l)
    return list(br.values())


def prior_tpo_write(sht_md):
    """Master Dashboard F77:F79 (POC / VAH / VAL) and H77:H79 (session). Never raises."""
    if sht_md is None:
        return
    try:
        p = _prior_tpo
        vals = [[p['poc']], [p['vah']], [p['val']]]
        tag = (p['date'].strftime('%a %d %b') if p['date'] else '--')
        sht_md.range(f'F{MD_PRIOR_ROW}:F{MD_PRIOR_ROW + 2}').value = vals
        sht_md.range(f'H{MD_PRIOR_ROW}:H{MD_PRIOR_ROW + 2}').value = [[tag]] * 3
    except Exception as e:
        print(f"   ! prior-day profile write skipped ({e})")


def prior_tpo_from_archive(path):
    """Replay: yesterday's SPX TPO profile from the previous archived session (spot
       snapshots, ~40s apart -- within about 1 pt of the 1-min-bar version live uses)."""
    def _dkey(fp):
        stem = os.path.splitext(os.path.basename(fp))[0].split("king_node_archive_")[-1].split("__")[0]
        d = stem.replace("-", "")
        return d if (len(d) == 8 and d.isdigit()) else None
    try:
        cur = _dkey(path)
        files = sorted(glob.glob(os.path.join(ARCHIVE_DIR, "king_node_archive_*.csv")))
        prev = [f for f in files if _dkey(f) and cur and _dkey(f) < cur]
        if not prev:
            print("Prior-day SPX TPO: no earlier archive in the folder")
            return
        day = max(_dkey(f) for f in prev)
        pts = {}
        for f in (x for x in prev if _dkey(x) == day):
            for enc in ("utf-8", "cp1252"):
                try:
                    with open(f, newline="", encoding=enc) as fh:
                        for r in csv.DictReader(fh):
                            ts = r.get("timestamp"); sp = r.get("spot")
                            if ts and sp and ts not in pts:
                                try:
                                    pts[ts] = float(sp)
                                except ValueError:
                                    pass
                    break
                except UnicodeDecodeError:
                    continue
        seq = []
        for ts, sp in pts.items():
            try:
                t = irish_to_et(datetime.datetime.fromisoformat(ts[:19]))   # archive local -> ET
            except ValueError:
                continue
            seq.append((t, sp, sp))
        poc, vah, val = tpo_levels(tpo_brackets(seq))
        _prior_tpo.update(date=datetime.date(int(day[:4]), int(day[4:6]), int(day[6:])),
                          poc=poc, vah=vah, val=val)
        print(f"Prior-day SPX TPO ({day}, from archive): POC {poc}  VAH {vah}  VAL {val}")
    except Exception as e:
        print(f"   ! prior-day SPX TPO skipped ({e})")


def pick_file():
    if ARCHIVE_FILE:
        return ARCHIVE_FILE if os.path.isabs(ARCHIVE_FILE) else os.path.join(ARCHIVE_DIR, ARCHIVE_FILE)
    files = sorted(glob.glob(os.path.join(ARCHIVE_DIR, "king_node_archive_*.csv")))
    if not files:
        print(f"No archive CSVs found in {ARCHIVE_DIR}")
        sys.exit(1)
    if len(files) == 1:
        return files[0]
    print("Archived sessions:")
    for n, f in enumerate(files):
        print(f"  [{n}] {os.path.basename(f)}")

    # Read the selection straight from the console. Plain input() can return early
    # on Windows when a stray newline is sitting in the buffer (that is what made it
    # auto-pick the newest); reading via msvcrt and draining first avoids that.
    sel = ""
    try:
        import msvcrt
        while msvcrt.kbhit():                       # drain any buffered keystrokes
            msvcrt.getch()
        sys.stdout.write("Pick a number then Enter (Enter alone = newest): ")
        sys.stdout.flush()
        while True:
            ch = msvcrt.getch()
            if ch in (b'\x00', b'\xe0'):            # arrow / function key -> swallow 2nd byte
                msvcrt.getch(); continue
            if ch in (b'\r', b'\n'):                # Enter -> done
                sys.stdout.write("\n"); sys.stdout.flush(); break
            if ch == b'\x08':                       # backspace
                if sel:
                    sel = sel[:-1]; sys.stdout.write("\b \b"); sys.stdout.flush()
                continue
            try:
                d = ch.decode()
            except Exception:
                continue
            if d.isdigit():
                sel += d; sys.stdout.write(d); sys.stdout.flush()
    except ImportError:                             # non-Windows fallback
        sel = input("Pick a number (Enter = newest): ")

    sel = sel.strip()
    if sel == "":
        return files[-1]
    try:
        i = int(sel)
        if 0 <= i < len(files):
            return files[i]
    except ValueError:
        pass
    print(f"  '{sel}' isn't in the list - using newest.")
    return files[-1]


# ============ keyboard (non-blocking, Windows) ============
try:
    import msvcrt
    _HAVE_KB = True
except ImportError:
    _HAVE_KB = False


def get_key():
    if not _HAVE_KB or not msvcrt.kbhit():
        return None
    ch = msvcrt.getch()
    if ch in (b'\x00', b'\xe0'):                        # arrow / function-key prefix
        ch2 = msvcrt.getch()
        return {'H': 'up', 'P': 'down', 'K': 'left', 'M': 'right'}.get(ch2.decode(errors='ignore'))
    try:
        # Case PRESERVED. j/k = 20-min jump, J/K = 1-hour jump -- .lower() here used to
        # collapse them into one key, so the hour jump could never fire. Every other key
        # is compared case-insensitively in the loop, so nothing else changes.
        return ch.decode(errors='ignore')
    except Exception:
        return None


# ============ workbook ============
_wbname = os.path.basename(WORKBOOK)
try:
    wb = xw.books[_wbname]
except Exception:
    wb = xw.Book(WORKBOOK)
sht    = wb.sheets[SHEET]
sht_le = wb.sheets[LE_SHEET]

# ---- dEdge chop-box edge hysteresis (held resistance/support -> KNM AB18/AB19) ----
_dedge_res_hold = None     # last held resistance edge (a strike, or None)
_dedge_sup_hold = None     # last held support edge
_dedge_res_pend = None     # challenger [strike, cycles-held] for the resistance edge
_dedge_sup_pend = None     # challenger for the support edge
_dedge_chop_off = 0        # consecutive cycles chop has read False while edges are held
CHOP_STATE_HOLD = 3        # keep routing this many cycles after chop flickers off (matches SW_LOCK_HOLD)
LOCK_HOLD = 3              # a challenger must beat a held edge this many cycles in a row (matches live)
LOCK_RELEASE = 3           # ported from live: a locked level must be ABSENT from the raw top-6 this
                           # many cycles before eviction (2026-07-30 latch fix)

# ---- level-side pipeline, PORTED VERBATIM FROM live_king_node.py -------------
# Replay used to write the archived r1..r6/s1..s6 slots straight into W9:W23.
# That made replay's side a passthrough of whatever the archive captured, so an
# old archive replayed with a stale side and, worse, a replay-saved workbook could
# be saved over a live one and inject that stale side. Replay now RE-DERIVES side
# each cycle from the workbook's own raw split (V) through the SAME hysteresis and
# lock live runs, so the two engines agree cycle-for-cycle. The flip/edge rule is
# UNCHANGED -- apply_rs_hysteresis below is live's, copied without edit.
_rs_side = {}              # strike -> 'R'/'S' : side deadband memory (ported)
_locked_R, _locked_S = [], []   # held R/S slot lists, cross-cycle (ported)
_pend_R, _pend_S = {}, {}        # challenger / absence counters (ported)


def apply_lock(locked, pend, raw, spot, side, thr=3.0, rev=None):
    """Keep prior levels stable; a challenger must persist LOCK_HOLD cycles to replace one.
       Release immediately when price reaches the primary level (R1/S1)."""
    # price reached the primary level -> re-adopt the fresh raw list at once
    # 2026-09-28 (Giggles, 7685 on 2026-09-28): "reached" now means CROSSED BY MORE THAN thr
    # (BG9, 3 pts). It used to re-adopt the raw list the instant spot touched R1/S1, so the
    # level vanished from the reaction table at the moment of the test.
    if locked:
        if (side == 'R' and spot > locked[0] + thr) or (side == 'S' and spot < locked[0] - thr):
            # 2026-10-04 (Giggles, 7615 on 2026-10-01 16:09:55): re-adopting the raw list used to drop
            # every other locked level at once -- a reversal-flagged level ranked 7th that cycle
            # vanished and came back the next. Reversal-flagged locked levels still on this side now
            # carry over and leave only after a 2nd consecutive cycle outside the raw top-6.
            new = list(raw[:6])
            np_ = {}
            if rev:
                for lv in locked[1:]:
                    if lv is None or lv in new or round(lv) not in rev:
                        continue
                    if not ((side == 'S' and lv <= spot + thr) or (side == 'R' and lv >= spot - thr)):
                        continue
                    if len(new) >= 6:
                        new[-1] = lv
                    else:
                        new.append(lv)
                    np_[('gone', lv)] = max(LOCK_RELEASE - 1, 0)
            return new, np_
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
        if isinstance(cur, (int, float)) and isinstance(spot, (int, float)) and abs(spot - cur) <= thr:
            pend.pop(i, None)             # 2026-09-28: a level being tested (spot inside its deadband) keeps its slot
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

    # release stale levels -- HOLD-TO-CLEAR (2026-07-30). A locked level absent
    # from the raw top-6 is no longer evicted instantly: it must stay absent
    # LOCK_RELEASE consecutive cycles first. Instant eviction was the flicker
    # source on 2026-07-29 (7405 in/out of the locked list on alternate cycles
    # through the 15:05 setup): LOCK_HOLD damps re-ORDERING of slots, but raw
    # top-6 MEMBERSHIP churn was undamped in both directions. Entry stays as it
    # was (Family B: instant-on / hold-to-clear). Absence counters live in
    # `pend` under ('gone', strike) tuple keys so they reset through the same
    # re-adopt paths that reset the slot challengers; tuple keys can never
    # collide with the integer slot keys.
    raw_top = [x for x in raw[:6] if x is not None]
    # 2026-10-04 (Giggles, 7615 on 2026-10-01 16:10:40 replay): FAST ENTRY for reversal-flagged
    # levels. A reversal-flagged strike in the raw top-6 but not locked takes, at once, the slot of
    # a locked level that has already dropped OUT of the raw top-6 (a stale slot) -- it no longer
    # waits LOCK_HOLD / LOCK_RELEASE cycles behind a level that is no longer ranked. With no stale
    # slot the normal challenger rules apply.
    if rev:
        for x in raw_top:
            if x in new_locked or round(x) not in rev:
                continue
            stale = [j for j, lv in enumerate(new_locked)
                     if lv is not None and lv not in raw_top
                     and not (isinstance(spot, (int, float)) and abs(spot - lv) <= thr)]
            if not stale:
                break
            j = max(stale, key=lambda q: abs(new_locked[q] - spot) if isinstance(spot, (int, float)) else q)
            pend.pop(('gone', new_locked[j]), None)
            new_locked[j] = x
            pend.pop(j, None)
    for i in range(len(new_locked)):
        lv = new_locked[i]
        if lv is None:
            continue
        if lv not in raw_top:
            gk = ('gone', lv)
            # 2026-09-28 (Giggles): a locked level is never evicted while spot is inside its
            # deadband (within thr = BG9 of the strike). On 2026-09-28 7685 was locked R1 as
            # price came up to it but ranked 7th in the raw list, so hold-to-clear evicted it at
            # 16:09:37 with spot 2 pts below -- it left the table exactly when it was tested.
            if isinstance(spot, (int, float)) and abs(spot - lv) <= thr:
                pend.pop(gk, None)
                continue
            pend[gk] = pend.get(gk, 0) + 1
            if pend[gk] >= LOCK_RELEASE:
                replacement = next((x for x in raw_top if x not in new_locked), None)
                if replacement is not None:
                    new_locked[i] = replacement
                    pend.pop(i, None)
                pend.pop(gk, None)
        else:
            pend.pop(('gone', lv), None)
    return new_locked, pend


def force_minvex_R(locked_R, locked_S, spot):
    """2026-09-23. The Min VEX strike is always a resistance when it sits above spot with
       NEGATIVE VEX in High IV (dealer-signed: negative VEX sells into a rally once IV falls,
       which is what a retest brings). Side is engine-owned ([23]/[25]), so it is forced into
       the locked resistance list HERE, never in the sheet. Inserted in price order, list
       trimmed to 6 (farthest dropped); removed from the support list if it was there.
       Any failure leaves both lists untouched."""
    try:
        mv = sht['F24'].value
        if not isinstance(mv, (int, float)) or not isinstance(spot, (int, float)) or mv <= spot:
            return locked_R, locked_S
        if str(sht_le['F4'].value).strip().lower() != 'high':
            return locked_R, locked_S
        aa = sht_le.range('AA9:AA55').value
        ad = sht_le.range('AD9:AD55').value
        vx = next((v for s, v in zip(aa, ad) if isinstance(s, (int, float)) and round(s) == round(mv)), None)
        if not isinstance(vx, (int, float)) or vx >= 0:
            return locked_R, locked_S
        # 2026-09-24: not while dealer vanna is BUYING. Negative dealer VEX sells into a retest
        # only once IV FALLS; with ATM IV rising (fast direction, BG80 -- the same reading the
        # reaction-table Vanna column shows) the same VEX buys, so the level must not be forced
        # to resistance (7705 on 2026-09-24: forced R while the Vanna column read BUY).
        _dir = str(sht_le['BG80'].value or sht_le['D5'].value or '').strip().upper()
        if _dir == 'UP':
            return locked_R, locked_S
        k = round(mv)
        S = [x for x in locked_S if not (isinstance(x, (int, float)) and round(x) == k)]
        R = list(locked_R)
        if not any(isinstance(x, (int, float)) and round(x) == k for x in R):
            i = next((j for j, x in enumerate(R) if isinstance(x, (int, float)) and x > mv), len(R))
            R.insert(i, mv)
            R = R[:6]
        return R, S
    except Exception as e:
        print(f"   ! Min VEX resistance lock skipped ({e})")
        return locked_R, locked_S


MINVEX_S_BAND = 2.5   # pts: Min VEX may be forced to SUPPORT when spot is at most this far BELOW it (or above it)


def force_minvex_S(locked_R, locked_S, spot):
    """2026-09-24 (Giggles). Mirror of force_minvex_R: when dealer vanna at the Min VEX strike is
       BUYING -- on the FAST ATM IV direction (Level Engine BG80, falling back to D5), the same
       reading the reaction-table Vanna column shows: negative dealer VEX with IV rising, or
       positive with IV falling -- the strike is forced into the locked SUPPORT list whenever
       spot is above it or no more than MINVEX_S_BAND below it. Removed from the resistance list;
       inserted in price order (nearest first), list trimmed to 6. No IV-level condition.
       Any failure leaves both lists untouched. UNTESTED."""
    try:
        mv = sht['F24'].value
        if not isinstance(mv, (int, float)) or not isinstance(spot, (int, float)):
            return locked_R, locked_S
        if spot < mv - MINVEX_S_BAND:
            return locked_R, locked_S
        aa = sht_le.range('AA9:AA55').value
        ad = sht_le.range('AD9:AD55').value
        vx = next((v for s, v in zip(aa, ad) if isinstance(s, (int, float)) and round(s) == round(mv)), None)
        if not isinstance(vx, (int, float)) or vx == 0:
            return locked_R, locked_S
        _dir = str(sht_le['BG80'].value or sht_le['D5'].value or '').strip().upper()
        buying = (vx < 0 and _dir == 'UP') or (vx > 0 and _dir == 'DOWN')
        if not buying:
            return locked_R, locked_S
        k = round(mv)
        R = [x for x in locked_R if not (isinstance(x, (int, float)) and round(x) == k)]
        S = list(locked_S)
        if not any(isinstance(x, (int, float)) and round(x) == k for x in S):
            i = next((j for j, x in enumerate(S) if isinstance(x, (int, float)) and x < mv), len(S))
            S.insert(i, mv)
            S = S[:6]
        return R, S
    except Exception as e:
        print(f"   ! Min VEX support lock skipped ({e})")
        return locked_R, locked_S


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


# ---- QUICK RECLAIM (2026-10-05, Giggles; POSITIVE gamma only, not fragile) ----------------------
# After 7750 on 2026-10-05: a 3.4-pt dip at 15:34 flipped the 7750 support to resistance, price reclaimed
# it at 15:37 and it sat as r1 (UNSAFE) until 15:50 because the deadband needs > BG9 pts the other way.
# Rule: when a level flips side by crossing its box edge by > thr, and within QR window (BG112 minutes,
# default 5) spot is back on the ORIGINAL side by >= BG110 pts (default 0.5) of the bare strike for BG111
# cycles in a row (default 3), the level returns to its original side at once (and to the front of that
# side's locked list). Archive check (75 sessions, exploratory): 52 reclaims, clean 42.3% vs 24.6% first
# touches, broke 32.7% vs 45.5%. UNTESTED as a rule.
QR_ENABLED = True
_qr_flip = {}          # strike -> {'from': 'R'|'S', 't': seconds, 'n': cycles back on the original side}
_qr_reclaimed = {}     # strike -> original side, filled on the cycle a reclaim fires (read by the caller)


def apply_rs_hysteresis(raw_R, raw_S, spot, thresh, box_flags, now=None, pos=False, qr=None):
    cands = []
    for L in list(raw_R) + list(raw_S):
        if L not in cands:
            cands.append(L)
    for L in cands:
        half = 5 if box_flags.get(L) == 1 else 0   # flip from the TOP/BOTTOM of the box, not the bare strike
        _prev = _rs_side.get(L)
        if spot > L + half + thresh:
            _rs_side[L] = 'S'                       # price closed >thr above the box top -> support
        elif spot < L - half - thresh:
            _rs_side[L] = 'R'                       # price closed >thr below the box bottom -> resistance
        else:
            _rs_side.setdefault(L, 'R' if L > spot else 'S')   # deadband: keep prior side
        if QR_ENABLED and now is not None and _prev is not None and _rs_side[L] != _prev:
            _qr_flip[L] = {'from': _prev, 't': now, 'n': 0}  # fresh > thr flip: start the reclaim watch
    # 2026-10-05 quick reclaim (see QR_ENABLED above)
    _qr_reclaimed.clear()
    if QR_ENABLED and now is not None and pos and qr:
        _mg, _nc, _win = qr
        for L in list(_qr_flip):
            f = _qr_flip[L]
            if now < f['t'] or now - f['t'] > _win or _rs_side.get(L) == f['from']:
                del _qr_flip[L]                      # window over, time ran backwards (seek), or already back
                continue
            _back = (spot >= L + _mg) if f['from'] == 'S' else (spot <= L - _mg)
            f['n'] = f['n'] + 1 if _back else 0
            if f['n'] >= _nc:
                _rs_side[L] = f['from']
                _qr_reclaimed[L] = f['from']
                del _qr_flip[L]
        if _qr_reclaimed:
            cands += [L for L in _qr_reclaimed if L not in cands]
    elif QR_ENABLED and not pos:
        _qr_flip.clear()
    # (removed 2026-07-26) hard invariant that snapped side the instant spot crossed the
    # bare strike. It defeated the BG9 deadband entirely -- 2026-07-24 14:55:20, spot
    # 7399.40, support 7400 flipped to resistance on a 0.6pt poke. Side changes are now
    # governed solely by the deadband above: box edge +/- BG9 (default 3 pts).
    # ---- slot ranking (2026-09-02) -------------------------------------------
    # Rank each side by how far spot is from the level's OWN flip boundary, not by
    # signed distance from spot. The two mechanisms used to disagree: the deadband
    # above holds a level as resistance until spot clears its box top by thresh,
    # while proximity ranking demoted it the instant spot ticked past the strike.
    # The level then fell out of slots 1-3, vanished from the reaction table and
    # lost its ladder shading while still locked as resistance (7660 at spot
    # 7661.01, locked R slot 4). Ranking on the boundary keeps a touched-but-
    # unbroken level at the front, where price actually is, and leaves every level
    # outside its band ordered exactly as before.
    def _edge(L, side):
        half = 5 if box_flags.get(L) == 1 else 0
        return (L + half + thresh) - spot if side == 'R' else spot - (L - half - thresh)

    hR = sorted((L for L in cands if _rs_side.get(L) == 'R'), key=lambda L: _edge(L, 'R'))
    hS = sorted((L for L in cands if _rs_side.get(L) == 'S'), key=lambda L: _edge(L, 'S'))
    return hR, hS



def qr_settings(sht_le):
    """(margin pts, cycles, window seconds) from Level Engine BG110:BG112; defaults 0.5 / 3 / 5 min."""
    def _n(a, d):
        try:
            v = sht_le[a].value
            return v if isinstance(v, (int, float)) else d
        except Exception:
            return d
    return (_n('BG110', 0.5), max(1, int(_n('BG111', 3))), 60.0 * _n('BG112', 5))


def qr_apply(locked_R, locked_S, pend_R, pend_S):
    """Move each just-reclaimed strike to the FRONT of its original side's locked list and off the other."""
    for L, frm in _qr_reclaimed.items():
        same = lambda x: isinstance(x, (int, float)) and round(x) == round(L)
        if frm == 'S':
            locked_R = [x for x in locked_R if not same(x)]
            locked_S = ([L] + [x for x in locked_S if not same(x)])[:6]
            pend_S = {}; pend_R = {}
        else:
            locked_S = [x for x in locked_S if not same(x)]
            locked_R = ([L] + [x for x in locked_R if not same(x)])[:6]
            pend_R = {}; pend_S = {}
    return locked_R, locked_S, pend_R, pend_S

def _read_levels(rng):
    """Read a vertical range of raw level strikes; return clean list (blanks removed)."""
    vals = sht_le[rng].value
    if not isinstance(vals, (list, tuple)):
        vals = [vals]
    return [round(v) for v in vals if isinstance(v, (int, float))]



def _challenge(hold, pend, raw):
    """LOCK_HOLD-style challenger gate for a single held dEdge.
       Returns (new_hold, new_pend). `raw` is this cycle's detected edge (or None).
       Copied verbatim from live_king_node.py so replayed routing matches live."""
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
       within `band` pts. Reads the just-calculated CZ/AA columns. Returns a strike or None."""
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
OEDGE_WALL_MULT = 3.0


def _oedge_neg_peak(m, K, ab, ac):
    """Negative-GEX gamma peak: |gamma| strictly above both neighbouring strikes and GEX < 0."""
    try:
        if m - 1 < 0 or m + 1 >= len(K) or K[m - 1] is None or K[m + 1] is None:
            return False
        g, gu, gd, x = ac[m], ac[m - 1], ac[m + 1], ab[m]
        if not all(isinstance(v, (int, float)) for v in (g, gu, gd, x)):
            return False
        return x < 0 and abs(g) > abs(gu) and abs(g) > abs(gd)
    except Exception:
        return False      # |DEX| >= this x near-median counts as a wall (excluded)



# ---- cluster admission hysteresis -> Level Engine HA9:HA55 ---------------------
# 2026-09-18. The cluster floor used to be a hard on/off test in the sheet
# (FW = FU >= floor). With the positive-gamma floor at 1.0M, a strike sitting near
# the line -- 7640 at 1,022,017 against 7645 at 973,539 on 2026-09-17 -- flips the
# whole band in and out on a 2-3% gamma move, and the reaction table follows.
# A sheet formula cannot damp that: it has no memory of the previous cycle. So the
# state lives here, like apply_lock / apply_sw_lock: a strike must clear the ADMIT
# level to enter, and then holds its place until it falls under the lower DROP
# level. The sheet reads this flag and only falls back to the plain floor test when
# the column is blank (engine not running, or a pristine workbook).
CLUST_ADMIT_POS, CLUST_DROP_POS = 1_000_000, 900_000
CLUST_ADMIT_NEG, CLUST_DROP_NEG =   300_000, 270_000
_clust_admit = {}          # strike -> bool, persists across cycles


# ---- gamma-wall hold -> Level Engine IT9:IT55 (read by GY) ------------------------------
# 2026-09-23. GY (gWall: |gamma| >= FA7 x both neighbours) was a hard line. 7750 sat on it
# against 7745 -- ratio 1.714 at 14:52:19, 1.697 at 14:53:01 -- and the tag flipped from
# gWall to the next geometry down on a 1% move. Held here like the cluster admission: a strike
# becomes a wall at FA7 (1.7x) and keeps it until it falls below BG77 (1.6x) against either
# neighbour. On any failure IT is blanked and GY falls back to the raw test.
_gwall_state = {}          # strike -> bool, persists across cycles


def _write_gwall_hold():
    global _gwall_state
    try:
        aa = sht_le.range('AA9:AA55').value
        ac = sht_le.range('AC9:AC55').value
        enter, leave = 1.7, 1.6
        try:
            v = sht_le['FA7'].value
            if isinstance(v, (int, float)): enter = v
            v = sht_le['BG77'].value
            if isinstance(v, (int, float)): leave = v
        except Exception:
            pass
        out = []
        for i, s in enumerate(aa):
            g = ac[i]
            up = ac[i - 1] if i > 0 else None
            dn = ac[i + 1] if i + 1 < len(ac) else None
            if not all(isinstance(x, (int, float)) for x in (s, g, up, dn)):
                out.append([0]); continue
            k = round(float(s))
            thr = leave if _gwall_state.get(k, False) else enter
            now = abs(g) >= thr * abs(up) and abs(g) >= thr * abs(dn)
            _gwall_state[k] = now
            out.append([1 if now else 0])
        sht_le['IT9:IT55'].value = out
    except Exception as e:
        try:
            sht_le['IT9:IT55'].value = [[None]] * 47
        except Exception:
            pass
        print(f"   ! gWall hold write failed ({e}); IT blank -> GY uses the raw test")


def _write_cluster_admit():
    """Per-strike cluster admission with hysteresis; writes 1/0 to HA9:HA55.
       On any failure the column is left alone and the sheet falls back to the
       plain floor test, so a failure here degrades to the old behaviour."""
    global _clust_admit
    try:
        aa = sht_le.range('AA9:AA55').value
        ac = sht_le.range('AC9:AC55').value          # |gamma| per strike (FU mirrors this)
        regime = sht['A8'].value
        hi, lo = ((CLUST_ADMIT_POS, CLUST_DROP_POS) if regime == 'Pos'
                  else (CLUST_ADMIT_NEG, CLUST_DROP_NEG))
        out = []
        for s, g in zip(aa, ac):
            if not isinstance(s, (int, float)) or not isinstance(g, (int, float)):
                out.append([None]); continue
            k = round(float(s)); mag = abs(g)
            was = _clust_admit.get(k, False)
            now = (mag >= lo) if was else (mag >= hi)   # admit at hi, hold until below lo
            _clust_admit[k] = now
            out.append([1 if now else 0])
        sht_le['HA9:HA55'].value = out
    except Exception as e:
        print(f"   ! cluster admit write failed ({e}); HA left blank -> sheet uses the plain floor")


# ---- edge / trough two-cycle hold -> Level Engine HU9:HU55 / HV9:HV55 -----------
# 2026-09-19. On 2026-09-17 20:43-20:57, 7645 flipped between gamma-shelf Edge and
# Trough five times in 14 minutes as gamma climbed 4M -> 7M, and Trough makes a level
# UNSAFE -- so the warning blinked on and off on the exact level price was testing.
# A sheet formula has no memory of the previous cycle, so the state lives here, the
# same pattern as the cluster admission hold (HA):
#   HS = edgeRaw, HT = troughRaw   (sheet formulas, this cycle's shape)
#   HU = edgeHeld, HV = troughHeld (written here)
#   GZ / HL = held if present, else raw -- every existing reader is unchanged.
# Each strike's shape is Edge / Trough / neither. A NEW shape is published only after
# it has been seen on SHAPE_HOLD_CYCLES consecutive cycles; until then the previous
# shape stands. First sight of a strike publishes raw immediately. A strike that
# leaves AA9:AA55 is forgotten. On any failure HU/HV are blanked, so the sheet falls
# back to the raw shape -- a failure degrades to the old behaviour, never to a stale one.
SHAPE_HOLD_CYCLES = 3        # 2026-09-19: 2 -> 3; a 2-cycle Trough still blinked the UNSAFE warning at the 17 Sep close
_shape_hold = {}           # strike -> [published, candidate, consecutive count]


def _write_shape_hold():
    try:
        aa = sht_le.range('AA9:AA55').value
        hs = sht_le.range('HS9:HS55').value
        ht = sht_le.range('HT9:HT55').value
        seen, hu, hv = set(), [], []
        for s, e, t in zip(aa, hs, ht):
            if not isinstance(s, (int, float)):
                hu.append([None]); hv.append([None]); continue
            k = round(float(s)); seen.add(k)
            raw = 'E' if e == 1 else ('T' if t == 1 else 'N')
            st = _shape_hold.get(k)
            if st is None:
                st = [raw, None, 0]
            elif raw == st[0]:
                st[1], st[2] = None, 0
            else:
                if raw == st[1]:
                    st[2] += 1
                else:
                    st[1], st[2] = raw, 1
                if st[2] >= SHAPE_HOLD_CYCLES:
                    st = [raw, None, 0]
            _shape_hold[k] = st
            hu.append([1 if st[0] == 'E' else 0])
            hv.append([1 if st[0] == 'T' else 0])
        for k in list(_shape_hold):
            if k not in seen:
                del _shape_hold[k]
        sht_le['HU9:HU55'].value = hu
        sht_le['HV9:HV55'].value = hv
    except Exception as e:
        try:
            sht_le['HU9:HV55'].value = None
        except Exception:
            pass
        print(f"   ! shape hold write failed ({e}); HU/HV blank -> sheet uses the raw edge/trough")


# ---- DEX peak hold -> Level Engine BG53 (read by BG28) -----------------------------
# 2026-09-20. BG28 (dominant DEX strike = largest |DEX| within 35 pts of spot) moves
# with spot. On 2026-09-17 it switched 50 times between 7600/7610/7650/7675, and 14 of
# the 22 flips of the 7630 dEdge cliff happened on a peak jump: with the peak at 7650,
# 7630 is suddenly BELOW the peak, judged against the other neighbour and on the other
# side, so the side-aware cliff switched off, then back on when the peak returned.
# Same pattern as the level lock: a new peak is published only after it has led for
# PEAK_HOLD_CYCLES consecutive cycles. First sight publishes immediately. The raw peak
# is computed here from King Node Model A29:A75 / E29:E75 / B4 exactly as BG28 does
# (first strike with the max |DEX| within 35 pts). On any failure BG53 is blanked and
# BG28 falls back to its own raw array formula. Optional margin (Level Engine BG54,
# default 0): a challenger must also exceed the held peak's |DEX| by that fraction while the
# held peak is still inside the window; a held peak that leaves the window is replaced at once.
PEAK_HOLD_CYCLES = 3
PEAK_WINDOW_PTS  = 35
_peak_pub = None
_peak_cand = None
_peak_cnt = 0


def _write_peak_hold():
    global _peak_pub, _peak_cand, _peak_cnt
    try:
        aa = sht.range('A29:A75').value
        ee = sht.range('E29:E75').value
        sp = sht['B4'].value
        mg = sht_le['BG54'].value
        mg = float(mg) if isinstance(mg, (int, float)) and mg >= 0 else 0.0
        dex_at = {}
        raw, best = None, None
        if isinstance(sp, (int, float)):
            for a_, e_ in zip(aa, ee):
                if isinstance(a_, (int, float)) and isinstance(e_, (int, float)) \
                        and abs(a_ - sp) <= PEAK_WINDOW_PTS:
                    dex_at[round(float(a_))] = abs(e_)
                    if best is None or abs(e_) > best:
                        best, raw = abs(e_), round(float(a_))
        if raw is not None:
            if _peak_pub is None:
                _peak_pub, _peak_cand, _peak_cnt = raw, None, 0
            elif raw == _peak_pub:
                _peak_cand, _peak_cnt = None, 0
            elif _peak_pub in dex_at and dex_at[raw] < dex_at[_peak_pub] * (1.0 + mg):
                _peak_cand, _peak_cnt = None, 0     # challenger not clearly bigger (BG54 margin)
            else:
                if raw == _peak_cand:
                    _peak_cnt += 1
                else:
                    _peak_cand, _peak_cnt = raw, 1
                if _peak_cnt >= PEAK_HOLD_CYCLES:
                    _peak_pub, _peak_cand, _peak_cnt = raw, None, 0
        sht_le['BG53'].value = _peak_pub
    except Exception as e:
        try:
            sht_le['BG53'].value = None
        except Exception:
            pass
        print(f"   ! peak hold write failed ({e}); BG53 blank -> BG28 uses the raw peak")


# ---- dEdge cliff collapse hold -> Level Engine HZ9:HZ55 ----------------------------
# 2026-09-20. On 2026-09-17 the DEX collapse behind 7630 sat between 45% and 55% for 58%
# of the session against the 50% cliff threshold (BG42) and crossed it 8 times. Every
# crossing flipped the dEdge backer, the reversal flag, the cliff box and the tag
# together, so the level's confluence changed 69 times and it blinked in and out.
#   HY = cliffFrac  (sheet formula, this cycle's collapse fraction vs the inner neighbour)
#   HZ = cliffHeld  (written here, 1/0)
#   CZ reads HZ when it is a number, else falls back to HY >= BG42 -- the collapse test
#   is the ONLY part held; side, distance, shelf adjacency, DEX floor and the gate stay live.
# Instant-on at >= BG42. Once on, it is released only after CLIFF_RELEASE_HOLD
# consecutive cycles below BG42, or at once if the fraction falls below BG52 (0.40) or
# stops being computable. A strike that leaves AA9:AA55 is forgotten. On any failure
# HZ is blanked, so the sheet falls back to the raw test -- never to a stale hold.
CLIFF_RELEASE_HOLD = 3
_cliff_hold = {}          # strike -> [held 0/1, consecutive cycles below the on-threshold]


def _write_cliff_hold():
    try:
        aa = sht_le.range('AA9:AA55').value
        fr = sht_le.range('HY9:HY55').value
        on = sht_le['BG42'].value
        rel = sht_le['BG52'].value
        on = float(on) if isinstance(on, (int, float)) else 0.5
        rel = float(rel) if isinstance(rel, (int, float)) else 0.4
        seen, hz = set(), []
        for s, f in zip(aa, fr):
            if not isinstance(s, (int, float)):
                hz.append([None]); continue
            k = round(float(s)); seen.add(k)
            st = _cliff_hold.get(k, [0, 0])
            num = isinstance(f, (int, float))
            if num and f >= on:
                st = [1, 0]
            elif st[0] == 1:
                if (not num) or f < rel:
                    st = [0, 0]
                else:
                    st[1] += 1
                    if st[1] >= CLIFF_RELEASE_HOLD:
                        st = [0, 0]
            else:
                st = [0, 0]
            _cliff_hold[k] = st
            hz.append([st[0]])
        for k in list(_cliff_hold):
            if k not in seen:
                del _cliff_hold[k]
        sht_le['HZ9:HZ55'].value = hz
    except Exception as e:
        try:
            sht_le['HZ9:HZ55'].value = None
        except Exception:
            pass
        print(f"   ! cliff hold write failed ({e}); HZ blank -> sheet uses the raw collapse test")


# ---- chop-zone stack heavy-strike hold -> Level Engine IO9:IO55 (gamma) / IP9:IP55 (zomma) ----
# 2026-09-22. A strike is "heavy" when |gamma| (or |zomma|) >= BG59 x the largest in the
# +-BG58 window around spot; 4+ heavy strikes in a row form a stack whose interior is the
# chop zone. A strike sitting on the BG59 line drops in and out of the stack cycle to
# cycle, and the UNSAFE warning follows. A sheet formula has no memory, so -- like the
# cluster admission hold (HA) -- the state lives here: a strike becomes heavy at BG59 and
# stays heavy until it falls under BG65 (the lower stay-heavy fraction). IH / IK read
# these when present and fall back to the plain BG59 test when blank, so a failure here
# degrades to the unheld behaviour, never to a stale one.
STACK_WIN_DFLT, STACK_ADMIT_DFLT, STACK_DROP_DFLT = 25.0, 0.5, 0.45
_stack_heavy = {'g': {}, 'z': {}}     # series -> {strike: bool}


def _write_stack_hold():
    global _stack_heavy
    try:
        def _num(v, d):
            return float(v) if isinstance(v, (int, float)) else d
        aa = sht_le.range('AA9:AA55').value
        spot = sht['B4'].value
        win = _num(sht_le['BG58'].value, STACK_WIN_DFLT)
        adm = _num(sht_le['BG59'].value, STACK_ADMIT_DFLT)
        drp = min(_num(sht_le['BG65'].value, STACK_DROP_DFLT), adm)
        if not isinstance(spot, (int, float)):
            raise ValueError("no spot")
        for key, rng, cell in (('g', 'AC9:AC55', 'IO9:IO55'), ('z', 'AF9:AF55', 'IP9:IP55')):
            vals = sht_le.range(rng).value
            inwin = [isinstance(s, (int, float)) and isinstance(v, (int, float)) and abs(s - spot) <= win
                     for s, v in zip(aa, vals)]
            peak = max([abs(v) for v, w in zip(vals, inwin) if w] or [0.0])
            st = _stack_heavy[key]
            out = []
            for s, v, w in zip(aa, vals, inwin):
                if not isinstance(s, (int, float)):
                    out.append([None]); continue
                k = round(float(s))
                if not w or peak <= 0:
                    st[k] = False; out.append([0]); continue
                was = st.get(k, False)
                now = abs(v) >= (drp if was else adm) * peak
                st[k] = now
                out.append([1 if now else 0])
            sht_le[cell].value = out
    except Exception as e:
        try:
            sht_le['IO9:IO55'].value = [[None]] * 47
            sht_le['IP9:IP55'].value = [[None]] * 47
        except Exception:
            pass
        print(f"   ! stack hold skipped ({e}); IO/IP blank -> sheet uses the plain heavy test")


def _write_oedge():
    """Compute the neg-gamma outer DEX boxes and write the per-strike flag to DS9:DS55.
       2026-09-22: side-aware + resistance mirror.
         Support box    -- drop-off where the next LOWER strike's |DEX| falls by >= frac;
                           outermost below spot, walk UP toward spot.
         Resistance box -- mirror: next HIGHER strike's |DEX| falls by >= frac; outermost
                           above spot, walk DOWN toward spot.
       Side comes from the LOCKED lists, not raw spot: a strike locked on the other side is
       never eligible (candidate or box member -- the inward walk stops at it), and a strike
       locked on this side is eligible even when spot has crossed it inside the deadband.
       Clears the column (all 0) in Pos-gamma or on any error."""
    import statistics
    try:
        aa = sht_le.range('AA9:AA55').value
        ae = sht_le.range('AE9:AE55').value      # DEX per strike
        ab = sht_le.range('AB9:AB55').value      # GEX per strike (2026-10-04 peak test)
        ac = sht_le.range('AC9:AC55').value      # |gamma| per strike (2026-10-04 peak test)
        spot = sht['B4'].value
        regime = sht['A8'].value
        band = sht_le['BG7'].value or 50
        floor = sht_le['BG43'].value or 100000
        frac = sht_le['BG42'].value or 0.5
        flags = [0] * len(aa)
        if not (isinstance(spot, (int, float)) and isinstance(regime, str) and (regime == 'Neg' or sht_le['BG72'].value in (1, 1.0, True))):   # 2026-10-09: fragile = negative
            sht_le.range('DS9:DS55').value = [[0] for _ in aa]
            return
        K = [a if isinstance(a, (int, float)) else None for a in aa]
        D = [d if isinstance(d, (int, float)) else None for d in ae]
        near = [abs(D[i]) for i in range(len(K)) if K[i] is not None and D[i] is not None and abs(K[i] - spot) <= band]
        med = statistics.median(near) if near else 1.0
        wall_th = OEDGE_WALL_MULT * med
        n = len(K)
        idx = {K[m]: m for m in range(n) if K[m] is not None}
        lockR = {round(float(x)) for x in (_locked_R or []) if isinstance(x, (int, float))}
        lockS = {round(float(x)) for x in (_locked_S or []) if isinstance(x, (int, float))}

        def is_wall(i):
            return D[i] is not None and abs(D[i]) >= wall_th

        def eligible(a, side):
            k = round(a)
            if side == 'S':
                return k not in lockR and (a < spot or k in lockS)
            return k not in lockS and (a > spot or k in lockR)

        # ladder is DESCENDING: i+1 is the next lower strike, i-1 the next higher
        for side, outward, inward in (('S', 1, 5), ('R', -1, -5)):
            drops = []
            for i in range(n):
                a = K[i]
                if a is None or D[i] is None or abs(a - spot) > band or not eligible(a, side):
                    continue
                if is_wall(i) or abs(D[i]) < floor:
                    continue
                j = i + outward
                if j < 0 or j >= n or K[j] is None or D[j] is None or is_wall(j):
                    continue
                if abs(D[j]) < (1.0 - frac) * abs(D[i]):
                    drops.append(a)
            if not drops:
                continue
            outer = max(drops, key=lambda a: abs(a - spot))
            cur = outer
            while True:                            # cluster inward while sustained + capped
                nxt = cur + inward
                if (nxt in idx and D[idx[nxt]] is not None and abs(D[idx[nxt]]) >= floor
                        and not is_wall(idx[nxt]) and eligible(nxt, side)
                        and abs(nxt - outer) <= OEDGE_MAX_WIDTH):
                    cur = nxt
                else:
                    break
            lo, hi = min(outer, cur), max(outer, cur)
            for m in range(n):
                if K[m] is not None and lo <= K[m] <= hi:
                    # 2026-10-04 (Giggles; PRE-REGISTERED, UNTESTED): the edge strike always carries
                    # oEdge; a strike INSIDE the block does not when it is a negative-GEX gamma peak
                    # (|gamma| above both neighbours, GEX < 0) -- in negative gamma a peak accelerates
                    # price through it. 2026-10-01: 7625 (peak, inside the 7640 block) failed; 7615
                    # (trough, inside the 7600 block) held at the day's low.
                    if K[m] != outer and _oedge_neg_peak(m, K, ab, ac):
                        continue
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


# ---- vSharp: DEX quality tag on the SUPPORT side of an nVanna zone (added 2026-08-18) ----
# DISPLAY ONLY. Renders as a "+" appended to the existing Ⓥ glyph. Nothing reads it back:
# no qualification gate, no slot ranker, no routing branch and no reversal marker consumes it.
#
# nVanna answers "is there a vol-reaction zone here". It does not distinguish a support the
# dealer book can hold from one the book is positioned to sell into. Net DEX does: heavily
# negative DEX at a support means dealer delta is short into the bounce.
#
# Median-relative rather than an absolute cut, deliberately. greeks() feeds the CALL IV into
# both legs, so every strike's DEX in a cycle carries the same directional approximation
# error; a median split inside the cycle cancels it, a fixed threshold would inherit it.
#
# SUPPORT SIDE ONLY. The resistance mirror is not built. The mechanism argued for is
# "dealers cannot fight the bounce", which is asymmetric, and there is no sample to test a
# mirror on.
#
# NOT VALIDATED. Across the 14 archived days carrying dt_nvanna there are 4 to 20 touch
# events depending on the touch definition, and the sharp / not-sharp split changes sign
# across those definitions. Largest cell is 6 events. This ships to be watched and archived,
# not traded, and it must not acquire a consumer without a frozen pre-registration first.
VSHARP_MIN_WINDOW = 3     # need at least this many near-window strikes to take a median


def _vsharp(aa, spot, flags):
    """1 where a BELOW-spot nVanna strike carries net DEX at or above the median net DEX of
       the near window; 0 everywhere else, including every above-spot flag. Never raises."""
    out = [0] * len(aa)
    try:
        dex = sht_le.range('AE9:AE55').value          # AE = dex, per strike
        win = sorted(dex[i] for i in range(len(aa))
                     if isinstance(aa[i], (int, float)) and abs(aa[i] - spot) <= NVAN_NEAR
                     and isinstance(dex[i], (int, float)))
        if len(win) < VSHARP_MIN_WINDOW:
            return out
        n = len(win)
        med = win[n // 2] if n % 2 else (win[n // 2 - 1] + win[n // 2]) / 2.0
        for i in range(len(aa)):
            if (flags[i] == 1
                    and isinstance(aa[i], (int, float)) and aa[i] < spot
                    and isinstance(dex[i], (int, float)) and dex[i] >= med):
                out[i] = 1
    except Exception as e:
        print(f"   ! vSharp skipped ({e})")
    return out


def _write_nvanna():
    """Compute the neg-gamma near-vanna zones (support below spot, resistance above) and write the
       per-strike flag to DT9:DT55, and the support-side vSharp DEX tag to ET9:ET55.
       Both clear to 0 in Pos-gamma or on error."""
    try:
        aa = sht_le.range('AA9:AA55').value
        vega = sht_le.range('BL9:BL55').value     # Vegamir
        vex = sht_le.range('AD9:AD55').value      # vex
        spot = sht['B4'].value
        regime = sht['A8'].value
        flags = [0] * len(aa)
        if not (isinstance(spot, (int, float)) and isinstance(regime, str) and (regime == 'Neg' or sht_le['BG72'].value in (1, 1.0, True))):   # 2026-10-09: fragile = negative
            sht_le.range('DT9:DT55').value = [[0] for _ in aa]
            sht_le.range('ET9:ET55').value = [[0] for _ in aa]
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
        sht_le.range('ET9:ET55').value = [[s] for s in _vsharp(aa, spot, flags)]
    except Exception as e:
        print(f"   ! nVanna skipped ({e})")


def _apply_dedge_hold(spot):
    """Pick nearest dEdge each side, apply BG9 (5-pt) edge hold + a CHOP_STATE_HOLD-cycle
       chop-state hold, write held edges to AB18/AB19. The chop-state hold keeps the routing
       for a few cycles when the S52 net-Dex flag flickers off mid-box (spot still inside);
       it fully releases only after chop stays off CHOP_STATE_HOLD cycles. A clean directional
       break (spot > a resistance edge + BG9, or < a support edge - BG9) releases that edge
       immediately, even mid-hold; a pullback off the level does NOT release it."""
    global _dedge_res_hold, _dedge_sup_hold, _dedge_chop_off
    global _dedge_res_pend, _dedge_sup_pend
    try:
        bg9 = sht_le['BG9'].value or 5
        band = sht_le['BG7'].value or 50
        chop = bool(sht['S52'].value) or (isinstance(sht['S38'].value, str) and 'Choppy' in sht['S38'].value)

        if not chop:
            # chop flag off: hold the existing routing for a few cycles (flicker guard),
            # but still honour a clean break beyond BG9 on either held edge.
            if (_dedge_res_hold is None and _dedge_sup_hold is None):
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

        _dedge_chop_off = 0                         # chop on -> reset the off-counter
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
sht_gd = wb.sheets[GD_SHEET]
try:
    sht_md = wb.sheets["Master Dashboard"]      # neg-gamma UNSAFE cells live here (K32:K34, K37:K39)
except Exception:
    sht_md = None

# ---- Master Dashboard layout probe (STRUCTURAL -- does not depend on any typed label) ----
# Copied verbatim from live_king_node.py: a blank row inserted under Vol regime (row 17)
# pushes every Master Dashboard row from 17 down by one, including the neg-gamma UNSAFE
# cells this engine reads. The offset is DETECTED via the 'Signs' anchor, never assumed,
# so replay maps the raspberry borders to the same rows live does on the same workbook.
MD_ROW_OFFSET = 0
MD_SKEW_CELL  = None           # 2026-09-24: FAIL CLOSED, as live. The old "E22" fallback is
                               # a live formula row after the 2026-09-24 inserts; no Skew
                               # label now means no skew write at all.
MD_TAPE_CELL  = None           # resolved structurally below; None = tape line disabled
if sht_md is not None:
    try:
        # 2026-09-22: scan widened to 10..56 and the offset cap raised, to match live.
        # A row inserted at 11 ("Testing Results") put Signs at 22, i.e. offset +4, which
        # the old cap (>3) rejected and forced back to 0 -- silently misrouting the skew
        # write while live resolved the same workbook correctly.
        _found = None
        _lab0 = {}
        for _r in range(10, 56):
            _t = str(sht_md[f"E{_r}"].value or "").strip().lower()
            if _t and _t not in _lab0:
                _lab0[_t] = _r
        _found = _lab0.get("signs")
        if _found is None:
            print("   ! MD probe: 'Signs' anchor not found - assuming ORIGINAL layout")
        else:
            MD_ROW_OFFSET = _found - 18          # 0 = original, +1 Skew, +2 Vol Tension, ...
            if MD_ROW_OFFSET < 0 or MD_ROW_OFFSET > 8:
                print(f"   ! MD probe: implausible offset {MD_ROW_OFFSET} - forcing 0")
                MD_ROW_OFFSET = 0
        # ---- GEX SLOPE TAPE row (mirrors live's probe) ----
        # No label of its own, so it is anchored one row under GEX SLOPE. Written as a
        # VALUE (character colour cannot survive a formula), so a misresolved row would
        # destroy a formula permanently: both the anchor text and an empty-of-formula
        # target must check out, else the line is disabled.
        try:
            _gs = next((_r for _r in range(16, 32)
                        if str(sht_md[f"E{_r}"].value or "").strip()
                             .lower().startswith("gex slope")), None)
            if _gs is None:
                print("   ! MD probe: 'GEX SLOPE' anchor not found - tape line DISABLED")
            elif str(sht_md[f"E{_gs + 1}"].formula or "").startswith("="):
                print(f"   ! MD probe: E{_gs + 1} holds a formula - tape line DISABLED")
            else:
                MD_TAPE_CELL = f"E{_gs + 1}"
                print(f"Master Dashboard: tape line -> {MD_TAPE_CELL}")
        except Exception as _e:
            print(f"   ! MD probe: tape row unresolved ({_e}) - tape line DISABLED")
        MD_VT_CELL = _vt_resolve(sht_md, range(10, 40))
        if MD_VT_CELL:
            print(f"Master Dashboard: vol tension -> {MD_VT_CELL}")
        if _lab0.get("skew"):
            MD_SKEW_CELL = f"F{_lab0['skew']}"      # by its own label, as live does
        _clear_stale_md_lines(sht_md, (MD_SKEW_CELL, MD_VT_CELL,
                                       globals().get("MD_TAPE_CELL"),
                                       globals().get("MD_CUSHION_CELL"),
                                       globals().get("MD_SPOTVOL_CELL"),
                                       globals().get("MD_SQUEEZE_CELL")))
        if MD_ROW_OFFSET >= 1:
            print(f"Master Dashboard: Skew row present (offset +{MD_ROW_OFFSET}) "
                  f"-> skew to F17, neg-gamma shifted")
        else:
            print("Master Dashboard: original layout -> skew to E22, neg-gamma unshifted")
    except Exception as e:
        print(f"   ! MD layout probe failed ({e}); assuming original layout")
# ---- Neg-gamma UNSAFE reads (synced with live 2026-08-05) --------------------
# Was "K" + Signs-offset. Two silent faults, both fixed here:
#   column -- Neg-gamma moved back to L (K is Zomma). The read resolved fine and
#             simply never matched "UNSAFE", so the raspberry border stopped
#             appearing rather than erroring.
#   row    -- the Signs anchor sits ABOVE the reaction block, so rows inserted
#             between the two shift the block without shifting the anchor.
# Anchored to the block's own labels, with a header check before it is trusted.
MD_NEGG_CELLS = ()
MD_SPOTVOL_CELL = None
MD_SQUEEZE_CELL = None
MD_VSPLIT_CELL = None
MD_FLOW_CELLS  = ()
MD_MELTUP_CELL = None
MD_FLOW1H_CELL = None
if sht_md is not None:
    try:
        _lab = {}
        for _r in range(10, 56):
            _t = str(sht_md[f"E{_r}"].value or "").strip().lower()
            if _t and _t not in _lab:
                _lab[_t] = _r
        _res = next((_r for _t, _r in _lab.items() if _t.startswith("next resistance")), None)
        _sup = next((_r for _t, _r in _lab.items() if _t.startswith("next support")), None)
        if _res is None or _sup is None or not (0 < _sup - _res <= 12):
            print("   ! MD probe: reaction-block labels unresolved - neg-gamma reads DISABLED")
        else:
            # 2026-09-17  L -> CJ, mirroring live. Read the exempt-aware 0/1 paint flag
            # (unsafe AND not exempt) instead of scraping column L for the substring
            # "UNSAFE". The old text scan ignored the exemption, so replay painted a
            # raspberry border on levels live correctly suppresses -- the two engines
            # disagreed on every exempt level. CJ is now the single paint definition,
            # identical to live.
            MD_NEGG_CELLS = tuple("CJ" + str(_res + _o) for _o in (4, 5, 6)) + \
                            tuple("CJ" + str(_sup + _o) for _o in (4, 5, 6))
            # Guard: every resolved paint cell must read 0/1. A misresolved row lands on
            # a blank or on text, which this catches (mirrors live's guard).
            _bad = [_c for _c in MD_NEGG_CELLS if sht_md[_c].value not in (0, 1, 0.0, 1.0)]
            if _bad:
                print(f"   ! MD probe: {', '.join(_bad)} do not read 0/1 "
                      f"- neg-gamma reads DISABLED")
                MD_NEGG_CELLS = ()
            # Spot-vol / squeeze / vol-split targets. The first two were HARDCODED
            # at E25/E26 until 2026-08-14; a row inserted at 19 pushed every line
            # below down one, so the probe-resolved GEX TAPE landed on E25 while the
            # hardcoded spot-vol write stayed there too -- two writers, one cell,
            # flickering every cycle. Resolved off the Signs anchor now, like the
            # rest. Vol split is located by its own label.
            # Anchored to the GEX SLOPE row, NOT to arithmetic off Signs. The old
            # hardcoded E25/E26 were written when two rows had already been inserted
            # above them, so "25 + offset" double-counts and lands two rows low --
            # on 2026-08-14 that resolved to E28/E29, and E29 holds the MAX GEX
            # formula. These three lines are one contiguous block under GEX SLOPE:
            # tape, spot-vol, squeeze. Deriving them from that anchor cannot drift.
            _gsr = next((_r for _t, _r in _lab.items()
                         if _t.startswith("gex slope")), None)
            if _gsr is not None:
                MD_SPOTVOL_CELL = f"E{_gsr + 2}"
                MD_SQUEEZE_CELL = f"E{_gsr + 3}"
            # FLOW rows (2026-09-24), mirrors live: gex slope +4 / +5.
            if _gsr is not None:
                _fl = []
                for _fc in (f"E{_gsr + 4}", f"E{_gsr + 5}"):
                    try:
                        _fl.append(None if str(sht_md[_fc].formula or "").startswith("=")
                                   else _fc)
                    except Exception:
                        _fl.append(None)
                MD_FLOW_CELLS = tuple(_fl)
                try:
                    if not str(sht_md[f"E{_gsr + 6}"].formula or "").startswith("="):
                        MD_FLOW1H_CELL = f"E{_gsr + 6}"
                except Exception:
                    pass
            # MELT-UP row (2026-09-24), mirrors live: own 'Melt-up' label in E4:E20.
            for _r in range(4, 21):
                if str(sht_md[f"E{_r}"].value or "").strip().lower().startswith("melt-up"):
                    if not str(sht_md[f"F{_r}"].formula or "").startswith("="):
                        MD_MELTUP_CELL = f"F{_r}"
                    break
            print(f"Master Dashboard: melt-up -> {MD_MELTUP_CELL or 'DISABLED'}, "
                  f"flow -> {', '.join(c for c in MD_FLOW_CELLS if c) or 'DISABLED'}, "
                  f"flow 1h -> {MD_FLOW1H_CELL or 'DISABLED'}")
            _vsr = _lab.get("vol split")
            MD_VSPLIT_CELL = f"F{_vsr}" if _vsr else None
            for _nm, _c in (("spot-vol", "MD_SPOTVOL_CELL"), ("squeeze", "MD_SQUEEZE_CELL"),
                            ("vol split", "MD_VSPLIT_CELL")):
                _t = globals().get(_c)
                if _t:
                    try:
                        if str(sht_md[_t].formula or "").startswith("="):
                            print(f"   ! MD probe: {_t} holds a FORMULA - {_nm} write DISABLED")
                            globals()[_c] = None
                    except Exception:
                        globals()[_c] = None
            print(f"Master Dashboard: spot-vol -> {MD_SPOTVOL_CELL}, "
                  f"squeeze -> {MD_SQUEEZE_CELL}, vol split -> {MD_VSPLIT_CELL}")
            print(f"Master Dashboard: neg-gamma reads -> {', '.join(MD_NEGG_CELLS)}")
    except Exception as _e:
        print(f"   ! MD probe: neg-gamma reads unresolved ({_e}) - DISABLED")

_archive_path = pick_file()
if PRIOR_TPO_ENABLED:
    prior_tpo_from_archive(_archive_path)
cycles = load_cycles(_archive_path)
_precompute_dex(cycles)                 # cache DEX break-risk columns for every cycle
_precompute_drain(cycles)               # DEX drain + weak VEX UNSAFE flag per cycle (-> JT)
_wh = sht_le['CT12'].value              # CT14 hold cycles (user-set, same cell live reads)
_wh = int(_wh) if isinstance(_wh, (int, float)) and _wh >= 1 else WARN_HOLD_DFLT
_precompute_vol_gex(cycles, _wh)        # cache P4/P5/P6 dirs, Net GEX flip + CT14 latch
_precompute_skew(cycles)                # cache skew head/put/call text per cycle (live's machine)
N = len(cycles)

# ---- NET GEX at RTH open+5 (5 min after the session's first archived cycle) -> AB15 baseline ----
_open5_idx = None
if cycles:
    _t0 = cycles[0]['dt']
    for _i, _c in enumerate(cycles):
        if (_c['dt'] - _t0).total_seconds() >= 300:
            _open5_idx = _i; break
MAX_LADDER = max(len(c['ladder']) for c in cycles)
sht[f'B{FIRST_DATA_ROW}:I{FIRST_DATA_ROW + MAX_LADDER - 1}'].number_format = '#,##0'


# ============ roll+reclaim observation marker (replay) ============
# Mirrors live_king_node.py's apply_roll_reclaim exactly, recomputed from the start of
# the file up to the current cycle each render, so the blue 'observe' border on the Next
# Support rows is correct whether you play straight through or scrub/seek. Breaks are
# judged on the PRIOR cycle's supports (a level can drop off the list as price pierces
# it) and a reclaim must hold OBS_CONFIRM cycles. Observation only -- never a trigger.
OBS_BRK = 3            # pts below a locked support to count it broken
OBS_RCL = 1           # pts back above to count a reclaim
OBS_CONFIRM = 2       # consecutive cycles above to confirm a reclaim
OBS_BRK_CONFIRM = 2   # 2026-09-29 (Giggles): consecutive cycles >= OBS_BRK below to confirm a
                      # break -- a one-cycle poke no longer counts (09-28 15:14:49: 7705 "broke"
                      # on a single 7700.05 print, next cycle 7702.02, and fired blue at 15:24)
OBS_HOLD = 6          # cycles to hold the blue observe border on
OBS_ROLL_WIN = 6      # vix1d/vix history depth for peak-and-roll
_obs_broken = {}; _obs_armed = True; _obs_latch = 0
_obs_ratio = []; _obs_prev_S = []; _obs_spot = []
_obs_pend = {}         # K -> consecutive cycles spot has been >= OBS_BRK below K

def _obs_reset():
    global _obs_broken, _obs_armed, _obs_latch, _obs_ratio, _obs_prev_S, _obs_spot, _obs_pend
    _obs_broken = {}; _obs_armed = True; _obs_latch = 0
    _obs_ratio = []; _obs_prev_S = []; _obs_spot = []; _obs_pend = {}

def _obs_step(spot, locked_S, vix1d, vix):
    global _obs_armed, _obs_latch, _obs_prev_S, _obs_broken, _obs_pend
    try:
        if vix and vix1d and float(vix) > 0:
            _obs_ratio.append(float(vix1d) / float(vix))
            if len(_obs_ratio) > OBS_ROLL_WIN + 2:
                del _obs_ratio[0]
    except (TypeError, ValueError):
        pass
    _obs_spot.append(spot)
    if len(_obs_spot) > OBS_CONFIRM:
        del _obs_spot[0]
    rolled = False
    if len(_obs_ratio) >= 3:
        pk = max(_obs_ratio)
        rolled = _obs_ratio[-1] < pk and _obs_ratio.index(pk) <= len(_obs_ratio) - 2
    prev = [s for s in _obs_prev_S if isinstance(s, (int, float))]
    cur  = [s for s in (locked_S or []) if isinstance(s, (int, float))]
    # a break needs OBS_BRK_CONFIRM consecutive cycles at least OBS_BRK below the level.
    # The level must be a support on the cycle the breach starts (it may drop off the
    # list once pierced, so a pending breach is followed even after it leaves).
    for K in list(_obs_pend):
        if spot > K - OBS_BRK:
            del _obs_pend[K]
    for K in set(prev) | set(_obs_pend):
        if spot <= K - OBS_BRK and K not in _obs_broken:
            _obs_pend[K] = _obs_pend.get(K, 0) + 1
            if _obs_pend[K] >= OBS_BRK_CONFIRM:
                _obs_broken[K] = True
                del _obs_pend[K]
    recl = next((K for K in sorted(_obs_broken) if spot >= K + OBS_RCL), None)
    if recl is not None and _obs_armed:
        held = len(_obs_spot) >= OBS_CONFIRM and all(s >= recl + OBS_RCL for s in _obs_spot)
        if held:
            if rolled:
                _obs_latch = OBS_HOLD
            _obs_armed = False
            _obs_broken = {k: v for k, v in _obs_broken.items() if k < recl}
    if not _obs_armed:
        for K in prev:
            if spot <= K - OBS_BRK and K not in _obs_broken:
                _obs_armed = True
    _obs_prev_S = cur
    if _obs_latch > 0:
        _obs_latch -= 1
        return 1
    return 0

# ============ VANNA OVERRIDE LATCH (2026-09-29, Giggles) ============
# Neg / fragile gamma, reversal-flagged levels on the locked R / S lists. Aligned vanna
# (SELL on a resistance, BUY on a support) at >= BG91 (DOM: BG92) ARMS the latch; it then
# HOLDS through flat, shrinking or small-opposed vanna (the at-the-strike flicker) and is
# RELEASED when the level is broken by more than BG9 pts, when vanna turns opposed at
# >= BG94, when the level leaves the list / loses its reversal flag / the regime leaves
# neg-fragile, or at a new session. The engine writes the result to Level Engine JR; the
# workbook's aligned-vanna override (JI) reads it. Vanna direction: 2026-10-01 (Giggles) the
# ARRIVAL reading, mirroring Level Engine JV (vanna_dir_arrival); was the IY current reading.
VLATCH_ENABLED = True


def vanna_dir(vex, ivfast):
    if not isinstance(vex, (int, float)) or str(ivfast or "").upper() not in ("UP", "DOWN"):
        return "-"
    if str(ivfast).upper() == "UP":
        return "SELL" if vex > 0 else "BUY"
    return "BUY" if vex > 0 else "SELL"


def vanna_dir_arrival(L, side, vex, ivfast, spot, ivtop, near_pts, svuv):
    """2026-10-01 (Giggles): dealer vanna expected ON ARRIVAL -- mirrors Level Engine JV.
       Only called in neg / fragile gamma. Resistance assumes IV FALLS on the rally to it,
       support assumes IV RISES on the drop to it. Falls back to the current reading
       (vanna_dir) on an IV top, within near_pts of spot, and on resistances while
       Spot Up / Vol Up is on."""
    if (ivtop in (1, 1.0, True) or not isinstance(vex, (int, float)) or vex == 0
            or not isinstance(spot, (int, float)) or abs(L - spot) <= near_pts
            or (side == 'R' and svuv in (1, 1.0, True))):
        return vanna_dir(vex, ivfast)
    if side == 'R':
        return "BUY" if vex > 0 else "SELL"
    return "SELL" if vex > 0 else "BUY"


# 2026-10-02 (Giggles): MERGED override, SIMPLIFIED later the same day. ARMS after `ncyc`
# consecutive cycles of: reversal flag + aligned arrival vanna (SELL on a resistance, BUY on a
# support) at >= noise (BG94) + DEX at the strike aligned (negative on a resistance, positive on a
# support) at >= dex_floor (BG100). RELEASES at once on a break of >= brk pts, opposed vanna >= opp
# (BG94), a lost reversal flag, the regime leaving neg/fragile, or a new session; after `ncyc`
# consecutive cycles of flat / weak / misaligned vanna, misaligned DEX, or the level off the locked
# lists. Re-arm needs the full ncyc again. The size thresholds (150K / 120K) and the DEX-backer
# token list are gone. "Vanna flat at the level" (Level Engine JY) is a separate workbook UNSAFE.


def _dex_aligned(side, dex, floor):
    if not isinstance(dex, (int, float)):
        return False
    return dex <= -floor if side == 'R' else dex >= floor


def vlatch_step(latch, st, spot, locked_R, locked_S, vex_by, rev_by, dex_by, ivfast, regime_ok,
                noise, opp, brk, dex_floor, ncyc, ivtop=0, near_pts=5, svuv=0, callwalls=None):
    """One cycle. latch: set of (strike, 'R'|'S'); st: {key: {'on','weak','nob','off'}} counters.
       Mutates and returns latch."""
    listed = {(round(k), 'R') for k in (locked_R or []) if isinstance(k, (int, float))}
    listed |= {(round(k), 'S') for k in (locked_S or []) if isinstance(k, (int, float))}
    if not regime_ok or not isinstance(spot, (int, float)):
        latch.clear(); st.clear()
        return latch
    for key in list(st):                                  # arm counters only survive while listed
        if key not in latch and key not in listed:
            del st[key]
    for key in list(latch):                               # off the table: release after ncyc cycles
        if key in listed:
            continue
        L, side = key
        c = st.setdefault(key, {'on': 0, 'weak': 0, 'nob': 0, 'off': 0})
        c['off'] += 1
        if rev_by.get(L) != 1 or c['off'] >= ncyc:
            latch.discard(key); st.pop(key, None)
    for key in listed:
        L, side = key
        c = st.setdefault(key, {'on': 0, 'weak': 0, 'nob': 0, 'off': 0})
        rev = rev_by.get(L) == 1
        v = vex_by.get(L)
        d = vanna_dir_arrival(L, side, v, ivfast, spot, ivtop, near_pts, svuv)
        size = abs(v) if isinstance(v, (int, float)) else 0.0
        aligned = ((side == 'S' and d == 'BUY') or (side == 'R' and d == 'SELL')) and size >= noise
        opposed = ((side == 'S' and d == 'SELL') or (side == 'R' and d == 'BUY')) and size >= opp
        dexok = _dex_aligned(side, dex_by.get(L), dex_floor)
        # 2026-10-02 (Giggles): on a CALL-WALL resistance (largest positive GEX + call-heavy,
        # Level Engine JZ) positive DEX is the expected sign and counts as aligned.
        if not dexok and side == 'R' and callwalls and L in callwalls:
            _d = dex_by.get(L)
            dexok = isinstance(_d, (int, float)) and _d >= dex_floor
        broke = (spot >= L + brk) if side == 'R' else (spot <= L - brk)
        if key in latch:
            c['off'] = 0
            if (not rev) or broke or opposed:
                latch.discard(key); st.pop(key, None)
                continue
            c['weak'] = 0 if aligned else c['weak'] + 1
            c['nob'] = 0 if dexok else c['nob'] + 1
            if c['weak'] >= ncyc or c['nob'] >= ncyc:
                latch.discard(key); st.pop(key, None)
        else:
            entry = rev and aligned and dexok and not broke
            c['on'] = c['on'] + 1 if entry else 0
            if c['on'] >= ncyc:
                latch.add(key)
                st[key] = {'on': 0, 'weak': 0, 'nob': 0, 'off': 0}
    return latch


def _vl_num(x, d):
    return x if isinstance(x, (int, float)) else d


def vlatch_write(sht_le, latch):
    """Level Engine JR9:JR55 = 1 where (strike, side) is latched. Never raises."""
    try:
        ks = sht_le.range('AA9:AA55').value
        sd = sht_le.range('AG9:AG55').value
        sht_le.range('JR9:JR55').value = [[1 if (isinstance(k, (int, float)) and (round(k), g) in latch) else 0]
                                          for k, g in zip(ks, sd)]
    except Exception as e:
        print(f"   ! vanna latch write skipped ({e})")

def obs_flag_at(idx):
    """Seek-safe: replay cycles[0..idx] through the marker, return the flag at idx."""
    _obs_reset()
    flag = 0
    for j in range(idx + 1):
        cc = cycles[j]
        flag = _obs_step(cc['spot'], cc['S'], cc.get('vix1d'), cc.get('vix'))
    return flag


# ============ nGex-wall box: arm-and-hold latch (ported from live 2026-07-31) ============
# The raw box node lives in Level Engine EO2 and is computed by the workbook from the
# W18:W20 locked supports this file already writes, so it is available in replay.
# EXCEPTION to the replay raw-passthrough policy: passthrough is used where live's hold
# is only a real-time flicker smoother. This latch is NOT a smoother -- the support gate
# switches off the moment price arrives, so the raw node is absent on exactly the cycles
# the box is meant to cover, and an instantaneous EQ1 would reproduce zero box firings.
# The hold IS the rule, so it is ported whole. Same constants as live.
BOX_FLOOR_PTS    = 5.0
BOX_MIGRATE_HOLD = 3
_box_node = None
_box_pend = None

def apply_box_latch(raw_node, spot, bg9):
    """Latched nGex-wall box node. Returns the held strike, or None when unarmed.
         raw_node None   -> HOLD whatever is latched (this is the qualification flicker)
         confirmed break -> clear (setup failed; the cut has already been signalled)
         different node  -> migrate only after BOX_MIGRATE_HOLD consecutive cycles"""
    global _box_node, _box_pend
    thr = bg9 if isinstance(bg9, (int, float)) and bg9 > 0 else 3.0
    if _box_node is not None and isinstance(spot, (int, float)):
        if spot < _box_node - BOX_FLOOR_PTS - thr:
            _box_node = None; _box_pend = None
            return None
    if raw_node is None:
        return _box_node                                   # HOLD
    if _box_node is None:
        _box_node = raw_node; _box_pend = None
    elif raw_node == _box_node:
        _box_pend = None
    elif _box_pend is not None and _box_pend[0] == raw_node:
        if _box_pend[1] + 1 >= BOX_MIGRATE_HOLD:
            _box_node = raw_node; _box_pend = None
        else:
            _box_pend = (raw_node, _box_pend[1] + 1)
    else:
        _box_pend = (raw_node, 1)
    return _box_node


# ============ PER-STRIKE VOLUME DELTA (ported from live 2026-09-09) ============
# Replay reads volume from the archived vol_delta column rather than recomputing it:
# the archive already holds the per-cycle delta the live engine measured, and there is
# no cumulative volume in the replay input to difference against. Ported so the two
# engines stay in step -- the live one WRITES FQ, this one MIRRORS it from the archive.
# OBSERVATION ONLY, nothing reads it back.


def _write_vol_delta(vol_by_strike):
    """Mirror archived per-cycle volume into Level Engine FQ9:FQ55."""
    try:
        _aa = sht_le.range('AA9:AA55').value
        sht_le['FQ9:FQ55'].value = [
            [(vol_by_strike or {}).get(round(float(_s)))
             if isinstance(_s, (int, float)) else None] for _s in _aa]
    except Exception as e:
        print(f"   ! vol delta mirror failed ({e}); FQ left as-is")


# ============ QUALIFICATION HOLD (ported from live 2026-09-09) ============
# Writes Level Engine FN9:FN55. Ported whole and unchanged from live: the hold is
# per-strike state that persists across cycles, so a replay without it reproduces
# DIFFERENT reaction tables from the same archive -- the exact divergence the PROX
# port comment warns about. Price-based release on the BG9 deadband; hard exclusions
# are re-tested by the workbook on FN, never here.
_qual_hold = {}
_qual_miss = {}


def apply_qual_hold(qual_by_strike, spot, thresh, confl_floor=None):
    """1 while a level's qualification is HELD past a failing soft test.
       Arms on CU=1 ('R') or CV=1 ('S'); releases when spot clears the level by
       more than `thresh` on that side, or when confluence collapses to
       floor - QUAL_COLLAPSE_MARGIN for QUAL_COLLAPSE_HOLD consecutive cycles
       (ported from live 2026-09-11). Returns {strike: side} for held strikes
       whose own CU/CV is 0.  qmap tuples are (cu, cv, confl)."""
    global _qual_hold, _qual_miss
    if not isinstance(spot, (int, float)) or not isinstance(thresh, (int, float)):
        return {}
    for k, q in (qual_by_strike or {}).items():
        cu, cv = q[0], q[1]
        if cu in (1, 1.0):
            _qual_hold[k] = 'R'
        elif cv in (1, 1.0):
            _qual_hold[k] = 'S'
    for k in list(_qual_hold):
        if k not in (qual_by_strike or {}):
            _qual_hold.pop(k, None); _qual_miss.pop(k, None); continue
        side = _qual_hold[k]
        if side == 'R' and spot > k + thresh:
            _qual_hold.pop(k, None); _qual_miss.pop(k, None); continue
        elif side == 'S' and spot < k - thresh:
            _qual_hold.pop(k, None); _qual_miss.pop(k, None); continue
        if isinstance(confl_floor, (int, float)):
            _q = qual_by_strike.get(k) or ()
            _cf = _q[2] if len(_q) > 2 else ""
            if isinstance(_cf, (int, float)) and _cf <= confl_floor - QUAL_COLLAPSE_MARGIN:
                _qual_miss[k] = _qual_miss.get(k, 0) + 1
                if _qual_miss[k] >= QUAL_COLLAPSE_HOLD:
                    _qual_hold.pop(k, None); _qual_miss.pop(k, None)
            else:
                _qual_miss.pop(k, None)
    out = {}
    for k, side in _qual_hold.items():
        q = qual_by_strike.get(k)
        if not q:
            continue
        if (q[0] if side == 'R' else q[1]) not in (1, 1.0):
            out[k] = side
    return out


QUAL_HOLD_ENABLED = False   # 2026-09-27 PARITY: live has no qualification hold (see below)

def _write_qual_hold(spot):
    """Read CU/CV for this cycle, update the hold, write FN9:FN55.
       Read-only degradation: on any failure FN is left as-is (= no hold).

       2026-09-27 PARITY FIX: DISABLED. live_king_node.py has no qualification hold and
       never writes FN, so this replay-only hold made replay's reaction table differ from
       live's. It also cancelled itself: a held FN=1 makes CU=1, the hold then drops every
       strike whose CU is 1, so FN is rewritten 0 and CU falls back to 0 after the recalc.
       On 2026-09-23 14:46:09 that transient CU=1 on 7750 blocked the PROX admission live
       made, and 7750 ended the cycle with neither a slot nor the proxy flag. With the hold
       off, FN is written 0 on every strike so the sheet's hold route is inert, as in live."""
    if not QUAL_HOLD_ENABLED:
        try:
            _aa = sht_le.range('AA9:AA55').value
            sht_le['FN9:FN55'].value = [[0 if isinstance(_s, (int, float)) else None] for _s in _aa]
        except Exception as e:
            print(f"   ! qual hold clear failed ({e}); FN left as-is")
        return {}
    try:
        _aa = sht_le.range('AA9:AA55').value
        _cu = sht_le.range('CU9:CU55').value
        _cv = sht_le.range('CV9:CV55').value
        _am = sht_le.range('AM9:AM55').value
        _thr = sht_le['BG9'].value
        _qfloor = sht_le['BG20'].value
        qmap = {}
        for _k, _cuv, _cvv, _amv in zip(_aa, _cu, _cv, _am):
            if isinstance(_k, (int, float)):
                qmap[round(_k)] = (_cuv, _cvv, _amv)
        held = apply_qual_hold(qmap, spot, _thr if isinstance(_thr, (int, float)) else 3,
                               _qfloor if isinstance(_qfloor, (int, float)) else None)
        sht_le['FN9:FN55'].value = [
            [1 if (isinstance(_s, (int, float)) and round(float(_s)) in held) else
             (0 if isinstance(_s, (int, float)) else None)] for _s in _aa]
        return held
    except Exception as e:
        print(f"   ! qual hold failed ({e}); FN left as-is")
        return {}


# ============ shelf-edge backer latch (ported from live 2026-09-13) ============
# Instant-on, release after GL4 consecutive failing cycles. Part of the rule, not a
# smoother, so replay must reproduce it or confluence will not match live.
_gex_shelf_hold, _gex_shelf_miss = set(), {}
_zom_shelf_hold, _zom_shelf_miss = set(), {}

def _write_shelf_latch(sht_le):
    try:
        _aa = sht_le.range('AA9:AA55').value
        _bd = sht_le.range('BD9:BD55').value
        _be = sht_le.range('BE9:BE55').value
        _n  = sht_le['GL4'].value
        _n  = int(_n) if isinstance(_n, (int, float)) and _n >= 1 else 3
        go, gp = [], []
        for _k, _b, _e in zip(_aa, _bd, _be):
            if not isinstance(_k, (int, float)):
                go.append([None]); gp.append([None]); continue
            kk = round(_k)
            for flag, hold, miss, col in ((_b, _gex_shelf_hold, _gex_shelf_miss, go),
                                          (_e, _zom_shelf_hold, _zom_shelf_miss, gp)):
                if flag in (1, 1.0):
                    hold.add(kk); miss[kk] = 0
                elif kk in hold:
                    miss[kk] = miss.get(kk, 0) + 1
                    if miss[kk] >= _n:
                        hold.discard(kk); miss.pop(kk, None)
                col.append([1 if kk in hold else 0])
        sht_le['GO9:GO55'].value = go
        sht_le['GP9:GP55'].value = gp
    except Exception as e:
        print(f"   ! shelf-edge latch skipped ({e})")


# ============ gamma-rank backer latch (ported from live 2026-09-13) ============
# Enter at rank <= GL2, release only at rank > GL3. Ported whole: the latch is part
# of the rule, not a smoother, so replay must reproduce it or the confluence counts
# will not match live on any boundary strike.
_grank_hold = set()

def _write_grank(sht_le):
    try:
        _aa = sht_le.range('AA9:AA55').value
        _ah = sht_le.range('AH9:AH55').value
        _en = sht_le['GL2'].value
        _rl = sht_le['GL3'].value
        _en = _en if isinstance(_en, (int, float)) else 3
        _rl = _rl if isinstance(_rl, (int, float)) else 5
        col = []
        for _k, _rk in zip(_aa, _ah):
            if not isinstance(_k, (int, float)):
                col.append([None]); continue
            kk = round(_k)
            if isinstance(_rk, (int, float)):
                if _rk <= _en:
                    _grank_hold.add(kk)
                elif _rk > _rl:
                    _grank_hold.discard(kk)
            else:
                _grank_hold.discard(kk)
            col.append([1 if kk in _grank_hold else 0])
        sht_le['GK9:GK55'].value = col
    except Exception as e:
        print(f"   ! gamma-rank latch skipped ({e})")


# ============ PROX no-skip admission (ported from live 2026-07-30) ============
# Writes Level Engine EN9:EN55. Same reason as the box latch: this flag is written by
# the engine, never by a sheet formula, so without it replay can never admit a level on
# proximity and any reaction row that came from that route on the day is missing.
# Its hold is instant-on / hold-to-clear (part of the rule, not a smoother) so it is
# ported whole, unchanged from live.
QUAL_COLLAPSE_MARGIN = 2   # ported from live 2026-09-11
QUAL_COLLAPSE_HOLD   = 3   # ported from live 2026-09-11
PROX_MIN_GAP   = 10
PROX_MISS_HOLD = 3
_prox_strike, _prox_miss = None, 0

# ---- PROX DEBUG (2026-09-27) -- observation only, changes no decision ----
# Every cycle whose time (HH:MM) falls inside [PROX_DEBUG_FROM, PROX_DEBUG_TO] appends a
# full trace of the PROX decision to PROX_DEBUG_LOG: the inputs exactly as the engine READ
# them (after the first recalc, before EN is written), each candidate's pass/fail reason,
# the latch before/after, and any exception with its traceback. Set PROX_DEBUG_FROM = ""
# to switch it off.
PROX_DEBUG_FROM = "14:35"
PROX_DEBUG_TO   = "14:50"
PROX_DEBUG_LOG  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prox_debug.log")

def _prox_dbg_on(ts):
    hm = (ts or "")[11:16]
    return bool(PROX_DEBUG_FROM) and bool(hm) and PROX_DEBUG_FROM <= hm <= PROX_DEBUG_TO

def _prox_dbg(lines):
    try:
        with open(PROX_DEBUG_LOG, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except Exception:
        pass

def _write_prox(spot, reg_neg, locked_R, ts=None):
    """Nearest locked-list resistance the structural gate skipped past -> EN=1.
       Read-only degradation: on any failure EN is left as-is."""
    global _prox_strike, _prox_miss
    _dbg = _prox_dbg_on(ts)
    _dl = []
    if _dbg:
        _dl.append("=" * 78)
        _dl.append(f"{ts}  spot={spot}  reg_neg={reg_neg}  locked_R(archive)={locked_R}")
        _dl.append(f"  latch BEFORE: strike={_prox_strike} miss={_prox_miss}")
    try:
        _aa = sht_le.range('AA9:AA55').value
        _am = sht_le.range('AM9:AM55').value     # confluence
        _ac = sht_le.range('AC9:AC55').value     # |gamma|
        _bk = sht_le.range('BK9:BK55').value     # absorbed by stronger neighbour
        _dh = sht_le.range('DH9:DH55').value     # absorbed into shelf/edge
        _cu = sht_le.range('CU9:CU55').value     # resQual(R) -- structural qualification
        _bt = sht_le.range('BT9:BT55').value     # resistance reaction slot (displayed)
        _fn = sht_le.range('FN9:FN55').value if _dbg else None   # qualHold (debug only)
        _bg7  = sht_le['BG7'].value
        _bg19 = sht_le['BG19'].value
        _bg20 = sht_le['BG20'].value
        qmap = {}
        for _k, _cf, _ag, _bkv, _dhv, _cuv, _btv in zip(_aa, _am, _ac, _bk, _dh, _cu, _bt):
            if isinstance(_k, (int, float)):
                qmap[round(_k)] = (_cf, _ag, _bkv, _dhv, _cuv, _btv)
        _lockset = {round(float(x)) for x in (locked_R or []) if isinstance(x, (int, float))}

        def _pnum(x):
            return float(x) if isinstance(x, (int, float)) else None

        def _prox_valid(k):
            q = qmap.get(k)
            if q is None or not isinstance(spot, (int, float)):
                return False
            _cfq, _agq = _pnum(q[0]), _pnum(q[1])
            _bkq, _dhq = _pnum(q[2]), _pnum(q[3])
            if not (reg_neg and k in _lockset and k > spot):
                return False
            if not (isinstance(_bg7, (int, float)) and (k - spot) <= _bg7):
                return False
            if _cfq is None or _agq is None or not isinstance(_bg19, (int, float)) \
                    or not isinstance(_bg20, (int, float)):
                return False
            if _cfq < _bg20 or _agq <= _bg19:
                return False
            if _bkq == 1 or _dhq == 1:
                return False
            return True

        def _prox_cu(k):
            # 2026-09-27 PARITY FIX: back to CU (q[4], structural qualification), which is
            # what live tests. The 2026-09-11 switch to the resistance slot (BT, q[5]) was
            # never made in live, and it made the flag cancel itself: the cycle after PROX
            # admits a strike, that strike holds a slot BECAUSE of EN, the slot test reads
            # it as "already displayed", the latch hard-clears, and the row drops out
            # (2026-09-23 14:47:39, 7750). It also blocked entry whenever a strike held a
            # slot at read time without qualifying structurally.
            q = qmap.get(k)
            return bool(q) and _pnum(q[4]) == 1

        if _dbg:
            _dl.append(f"  BG7(window)={_bg7}  BG19(gamma floor)={_bg19}  BG20(min backers)={_bg20}"
                       f"  MIN_GAP={PROX_MIN_GAP}  lockset={sorted(_lockset)}")
            _dl.append("  strike  backers   |gamma|      BK DH  slot  CU FN  locked  -> result")
            for _k in sorted(qmap):
                if not (isinstance(spot, (int, float)) and spot < _k <= spot + (_bg7 or 50)):
                    continue
                q = qmap[_k]
                _cfq, _agq = _pnum(q[0]), _pnum(q[1])
                if not reg_neg:
                    _why = "FAIL regime not Neg"
                elif _k not in _lockset:
                    _why = "FAIL not on locked R list"
                elif _cfq is None or _agq is None:
                    _why = "FAIL backers/gamma not numeric"
                elif _cfq < (_bg20 if isinstance(_bg20, (int, float)) else 99):
                    _why = "FAIL backers < BG20"
                elif _agq <= (_bg19 if isinstance(_bg19, (int, float)) else 1e18):
                    _why = "FAIL gamma <= floor"
                elif _pnum(q[2]) == 1 or _pnum(q[3]) == 1:
                    _why = "FAIL absorbed (BK/DH)"
                elif _prox_cu(_k):
                    _why = "valid, but QUALIFIES STRUCTURALLY (CU=1) -> not a candidate"
                else:
                    _why = "CANDIDATE"
                try:
                    _fnv = _fn[list(round(x) if isinstance(x, (int, float)) else None
                                    for x in _aa).index(_k)]
                except Exception:
                    _fnv = "?"
                _dl.append(f"  {_k:>6}  {q[0]!s:>7}  {q[1]!s:>12}  {q[2]!s:>3} {q[3]!s:>2}  {q[5]!s:>4}"
                           f"  {q[4]!s:>3} {_fnv!s:>3}"
                           f"  {('yes' if _k in _lockset else 'no'):>6}  -> {_why}")
        _struct = [k for k, q in qmap.items()
                   if _pnum(q[5]) is not None and isinstance(spot, (int, float))
                   and k > spot
                   and (_prox_strike is None or k != round(_prox_strike))]
        _near_disp = min(_struct) if _struct else None
        _cands = sorted(k for k in qmap if _prox_valid(k) and not _prox_cu(k))
        _cstar = _cands[0] if _cands else None
        if _prox_strike is not None:
            _kcur = round(_prox_strike)
            if _prox_cu(_kcur):
                _prox_strike, _prox_miss = None, 0
            elif (not reg_neg
                  or not (isinstance(spot, (int, float)) and _kcur > spot)
                  or _kcur not in _lockset):
                _prox_strike, _prox_miss = None, 0
            elif not _prox_valid(_kcur):
                _prox_miss += 1
                if _prox_miss >= PROX_MISS_HOLD:
                    _prox_strike, _prox_miss = None, 0
            else:
                _prox_miss = 0
        if _dbg:
            _dl.append(f"  nearest DISPLAYED resistance above spot (excl. latched) = {_near_disp}")
            _dl.append(f"  best candidate = {_cstar}"
                       + (f"  gap = {_near_disp - _cstar}" if _cstar is not None and _near_disp is not None else ""))
            if _cstar is None:
                _dl.append("  ENTRY: no -- no candidate")
            elif _near_disp is None:
                _dl.append("  ENTRY: no -- no displayed resistance above spot to measure the gap against")
            elif not _cstar < _near_disp:
                _dl.append("  ENTRY: no -- candidate is not below the nearest displayed resistance")
            elif (_near_disp - _cstar) < PROX_MIN_GAP:
                _dl.append(f"  ENTRY: no -- gap {_near_disp - _cstar} < {PROX_MIN_GAP}")
            elif _prox_strike is not None and not _cstar < round(_prox_strike):
                _dl.append(f"  ENTRY: no -- latch already held on {_prox_strike} (candidate not nearer)")
            else:
                _dl.append("  ENTRY: YES")
        if (_cstar is not None and _near_disp is not None
                and _cstar < _near_disp
                and (_near_disp - _cstar) >= PROX_MIN_GAP
                and (_prox_strike is None or _cstar < round(_prox_strike))):
            _prox_strike, _prox_miss = float(_cstar), 0
        _en_col = []
        for _s in _aa:
            if isinstance(_s, (int, float)):
                _en_col.append([1 if (_prox_strike is not None
                                      and round(float(_s)) == round(_prox_strike))
                                else 0])
            else:
                _en_col.append([None])
        sht_le['EN9:EN55'].value = _en_col
        if _dbg:
            _dl.append(f"  latch AFTER: strike={_prox_strike} miss={_prox_miss}"
                       f"  -> EN written for {[s_ for s_, e_ in zip(_aa, _en_col) if e_ == [1]]}")
    except Exception as e:
        print(f"   ! PROX admission failed ({e}); EN column left as-is")
        if _dbg:
            import traceback
            _dl.append(f"  !! EXCEPTION -- EN LEFT AS-IS FROM LAST CYCLE: {e!r}")
            _dl.extend("  " + ln for ln in traceback.format_exc().splitlines())
    if _dbg:
        _prox_dbg(_dl)


# ============ V2: precomputed frame data + perf instrumentation ============
# Everything in this section is PURE PYTHON and deterministic in `cycles`, so caching it
# produces byte-identical values to computing it per frame -- it only removes the O(N)
# rescan that used to run on every single render. Nothing that depends on a recalculated
# sheet value is cached (it cannot be: those values only exist after Excel recalcs the
# writes this frame just made).

print("  pre-computing frame data ...", end="", flush=True)
_t0_pre = time.perf_counter()

# GEX SLOPE line (KNM AB12) -- pure function of cycles[idx] and its window.
_GEX_LINE = [gex_monitor_line(cycles, i) for i in range(N)]

# ---- fragile positive-gamma hold -> Level Engine BG76 (read by BG72) ---------------------
# 2026-09-23. BG72 (fragile pos-gamma: net GEX < BG71, or net + 15-min slope < 0) was a
# plain sheet test and switched every cycle the inputs crossed a line -- 7.4 switches per
# session across 64 archived sessions. The state is held HERE: it turns ON after BG75
# consecutive cycles meeting the entry test, and OFF only after BG75 consecutive cycles with
# net GEX >= BG73 AND net + slope >= BG74. Any non-positive regime resets it. Precomputed over
# the whole session so seeks and back-steps stay deterministic. BG72 falls back to the raw
# test when BG76 is blank (engine not running, or a pristine workbook).
def _frag_params():
    d = {'BG71': 1_000_000, 'BG73': 2_000_000, 'BG74': 1_000_000, 'BG75': 2}
    for k in d:
        try:
            v = sht_le[k].value
            if isinstance(v, (int, float)):
                d[k] = v
        except Exception:
            pass
    return d['BG71'], d['BG73'], d['BG74'], max(1, int(d['BG75']))


def _precompute_fragile(cycles):
    enter_floor, exit_floor, exit_proj, need = _frag_params()
    out, st, cnt = [], False, 0
    for c in cycles:
        try:
            pos = (c['flags'][0] == 'Pos')
        except Exception:
            pos = False
        net = c.get('net_gex')
        if not pos or not isinstance(net, (int, float)):
            # 2026-09-24 FIX: a non-positive cycle now ARMS the fragile state instead of
            # clearing it. Positive gamma that has just come out of negative gamma is fragile
            # by definition until the EXIT test proves otherwise. Clearing it here meant the
            # first BG75 positive cycles after every Neg->Pos flicker read "not fragile" even
            # with net GEX near zero (7750 on 2026-09-23 14:43: net +76K, slope -2.5M/15m,
            # shown SAFE because the regime had read Neg one cycle earlier).
            st, cnt = True, 0
            # 2026-09-24 FIX 2: publish the ARMED state (1), not 0. BG72 already returns 0
            # whenever the workbook's own regime (KNM A8) is not Pos, so a 1 here is harmless
            # in true negative gamma -- but the archived flag this hold keys on can disagree
            # with the workbook's A8 on the flip cycle (2026-09-23 14:42:53: archive Neg,
            # workbook Pos, net GEX +76K). Publishing 0 then forced BG72 to "not fragile" and
            # 7750 read SAFE/green. Missing net GEX in positive gamma still publishes blank.
            out.append(1 if not pos else None)
            continue
        p15 = c.get('gex_per15')
        proj = net + (p15 if isinstance(p15, (int, float)) else 0.0)
        if not st:
            cnt = cnt + 1 if (net < enter_floor or proj < 0) else 0
            if cnt >= need:
                st, cnt = True, 0
        else:
            cnt = cnt + 1 if (net >= exit_floor and proj >= exit_proj) else 0
            if cnt >= need:
                st, cnt = False, 0
        out.append(1 if st else 0)
    return out


try:
    _FRAG_HELD = _precompute_fragile(cycles)
except Exception as _e:
    _FRAG_HELD = [None] * N
    print(f"\n   ! fragile hold precompute failed ({_e}); BG76 blank -> BG72 uses the raw test")
# 2026-10-01 (Giggles): where the archive carries frag_pos (live's published BG76), use it as-is so
# fragile reads exactly as it did live; older archives keep the rebuilt hold above.
_FRAG_N_ARCH = 0
for _fi, _fc in enumerate(cycles):
    if _fc.get('frag_has'):
        _fv = _fc.get('frag')
        _FRAG_HELD[_fi] = (int(_fv) if isinstance(_fv, (int, float)) else None)
        _FRAG_N_ARCH += 1
if _FRAG_N_ARCH:
    print(f"\n   fragile hold: {_FRAG_N_ARCH} cycle(s) from the archive (frag_pos), "
          f"{N - _FRAG_N_ARCH} rebuilt")
# GEX SLOPE TAPE -- one finished (text, colours) per index, no lookahead.
_TAPE = build_tape(cycles)

# MELT-UP / FLOW history readings -- one forward pass, identical math to live's mu_step(),
# using the archive clock. Deterministic per index, so seeks need no rebuild.
mu_reset()
_IVTOP = [iv_top_step(c['dt'].timestamp(), c.get('atm_iv')) for c in cycles]
_IVFAST_CALC = [iv_fast_step(c['dt'].timestamp(), c.get('atm_iv')) for c in cycles]
# 2026-10-04 FIX (Giggles, 7615 on 2026-10-01 16:10:40): the replay recomputed fast ATM IV from the
# archive's ATM IV, sampled only once per archived cycle, so it lagged the live engine by several
# cycles (live recorded DOWN from 16:10:40; the replay read UP, then FLAT, until 16:14:28). Where the
# archive recorded the live engine's own fast reading (atm_iv_fast, from 2026-09-24), use it verbatim;
# older sessions fall back to the recomputed value.
_IVFAST = [(str(c.get('ivfast') or '').strip().upper() or _f) for c, _f in zip(cycles, _IVFAST_CALC)]
mu_reset()
def _minvex_strike(c):
    """2026-10-01: Min VEX strike of a cycle (most negative archived VEX) for the melt-up watch."""
    _v = [(v, k) for k, v in (c.get('vx') or {}).items() if isinstance(v, (int, float)) and v == v]
    return min(_v)[1] if _v else None
_MU_PRE = [mu_step(c['dt'].timestamp(), c['spot'], c.get('atm_iv'), c.get('vix1d'), c.get('vix'),
                   c.get('fl_cd'), c.get('fl_pd'), c.get('fl_cc'), c.get('fl_pc'),
                   minvex=_minvex_strike(c))
           for c in cycles]
mu_reset()

# roll+reclaim observe marker (LE CT26) -- obs_flag_at() replayed 0..idx on EVERY frame,
# which is O(N^2) across a session. One forward pass gives the identical per-index flag.
_obs_reset()
_OBS_FLAG = [_obs_step(c['spot'], c['S'], c.get('vix1d'), c.get('vix')) for c in cycles]
# vanna latch per cycle, replayed from the start of the archive (seek-safe). Uses the locked
# lists and per-strike values live archived; regime = archived flag_gamma Neg OR the fragile hold
# (_FRAG_HELD: archived frag_pos from 2026-10-01, rebuilt before). Thresholds read on the first frame.
_VLATCH_CACHE = {}


def _callwalls(c, topn, minc):
    """2026-10-02: strikes that would read callWall (Level Engine JZ) this cycle, side aside:
       positive GEX in the top `topn` positive-GEX strikes and call OI >= minc and > put OI."""
    gx = {k: v for k, v in (c.get('gx') or {}).items() if isinstance(v, (int, float))}
    out = set()
    for k, v in gx.items():
        if v <= 0 or sum(1 for w in gx.values() if w > v) >= topn:
            continue
        co, po = (c.get('co') or {}).get(k), (c.get('po') or {}).get(k)
        if isinstance(co, (int, float)) and co >= minc and co > (po if isinstance(po, (int, float)) else 0):
            out.add(k)
    return out


def vlatch_series(noise, opp, brk, dex_floor, ncyc, near=5, c5=None, cw_top=1, cw_minc=1000):
    # 2026-10-01: arrival vanna (mirrors live / Level Engine JV): IV top from _IVTOP, the near-spot
    # switch-back distance from BG98, Spot Up / Vol Up from the archived svx_dir.
    # 2026-10-02: simplified merged override (2-cycle on/off, aligned vanna >= BG94, DEX >= BG100).
    # 2026-10-02 FIX: the latch read the ARCHIVED fast-IV column only, so while it was blank
    # (e.g. 10-01 before 14:58) every level near spot / under an IV top read FLAT and never
    # latched, although the workbook (IY/JV) read the same strike as SELL/BUY. The direction now
    # mirrors the workbook exactly: BG80 (engine fast IV) if set, else D5 = C5 override, else the
    # slow ATM IV direction written to B3, else FLAT.
    _c5 = str(c5 or '').strip().upper()
    key = (noise, opp, brk, dex_floor, ncyc, near, _c5, cw_top, cw_minc)
    if key not in _VLATCH_CACHE:
        lat = set(); st = {}; out = []; day = None
        for _ci, c in enumerate(cycles):
            if c['dt'].date() != day:
                lat = set(); st = {}; day = c['dt'].date()
            # 2026-10-01: regime = negative OR fragile positive gamma, as live (A8 Neg or BG72 = 1)
            _reg_ok = c['gneg'] or _FRAG_HELD[_ci] == 1
            vlatch_step(lat, st, c['spot'], c['R'], c['S'], c['vx'], c['rv'], c.get('dx', {}),
                        (str(_IVFAST[_ci] or '').strip().upper() or _c5
                         or str(c.get('atm_iv_dir') or '').strip().upper() or 'FLAT'),
                        _reg_ok, noise, opp, brk, dex_floor, int(ncyc),
                        ivtop=_IVTOP[_ci][0], near_pts=near,
                        svuv=1 if (isinstance(c.get('svx'), (int, float)) and c['svx'] > 0) else 0,
                        callwalls=_callwalls(c, cw_top, cw_minc))
            out.append(frozenset(lat))
        _VLATCH_CACHE[key] = out
    return _VLATCH_CACHE[key]
_obs_reset()


# ============ gDex-rule vanna UNSAFE latch -> Level Engine KO (2026-10-05, Giggles) ============
# POSITIVE gamma only (not fragile). Raw test mirrors Level Engine KN: a strike whose reversal flag
# comes from gDex (isolated DEX -- opposite sign to both ladder neighbours, which share a sign, and
# > 10% of their average |DEX| -- at a POSITIVE-GEX strike) and whose ARRIVAL vanna does not support
# the move (resistance not SELL / support not BUY, any size). Hysteresis: ON after GDV_HOLD cycles in a
# row, OFF after GDV_HOLD cycles in a row without it; reset at a new session or when the regime leaves
# positive gamma. One forward pass, seek-safe. The workbook (KP) uses KO when it is a number, else the
# raw KN -- so the live workbook, which nobody writes KO for yet, keeps the raw rule. UNTESTED.
# 2026-10-05 (later, Giggles): the rule applies only when gDex is the ONLY reason for the reversal flag
# (Level Engine KQ). That test is applied by the workbook on top of KO (KP) every cycle, not latched here.
GDV_ENABLED = True
GDV_HOLD    = 2      # cycles in a row needed to switch on, and to switch off
_GDV_CACHE = {}


def _gdv_raw(c, ci, near):
    """Per ladder row: True where the raw gDex-rule condition holds this cycle."""
    lad = c.get('ladder') or []
    spot = c.get('spot')
    Rl = {round(k) for k in (c.get('R') or []) if isinstance(k, (int, float)) and k == k}
    Sl = {round(k) for k in (c.get('S') or []) if isinstance(k, (int, float)) and k == k}
    ivf = (str(_IVFAST[ci] or '').strip().upper()
           or str(c.get('atm_iv_dir') or '').strip().upper() or 'FLAT')
    svuv = 1 if (isinstance(c.get('svx'), (int, float)) and c['svx'] > 0) else 0
    out = []
    for i, r in enumerate(lad):
        k = r[0]
        if (i == 0 or i == len(lad) - 1 or not isinstance(k, (int, float))
                or not isinstance(spot, (int, float))):
            out.append(False)
            continue
        gx, d0, du, dd, vx = r[2], r[4], lad[i - 1][4], lad[i + 1][4], r[5]
        if not all(isinstance(x, (int, float)) for x in (gx, d0, du, dd)):
            out.append(False)
            continue
        sgn = lambda x: (x > 0) - (x < 0)
        gdex = (gx > 0 and d0 != 0 and sgn(du) != 0 and sgn(du) == sgn(dd)
                and sgn(d0) == -sgn(du) and abs(d0) > (abs(du) + abs(dd)) / 2 * 0.1)
        if not gdex:
            out.append(False)
            continue
        L = round(float(k))
        side = 'R' if L in Rl else ('S' if L in Sl else ('R' if k > spot else 'S'))
        dv = vanna_dir_arrival(L, side, vx, ivf, spot, _IVTOP[ci][0], near, svuv)
        aligned = (side == 'R' and dv == 'SELL') or (side == 'S' and dv == 'BUY')
        out.append(not aligned)
    return out


def gdv_series(near=5, hold=GDV_HOLD):
    """One forward pass over the archive -> per cycle, a 0/1 list per ladder row (row 9+i)."""
    key = (near, hold)
    if key not in _GDV_CACHE:
        res, st, day = [], {}, None
        for ci, c in enumerate(cycles):
            if c['dt'].date() != day:
                st, day = {}, c['dt'].date()
            pos = (not c.get('gneg')) and _FRAG_HELD[ci] != 1
            lad = c.get('ladder') or []
            if not pos:
                st = {}
                res.append([0] * len(lad))
                continue
            raw = _gdv_raw(c, ci, near)
            seen, row = set(), []
            for r, x in zip(lad, raw):
                k = r[0]
                if not isinstance(k, (int, float)):
                    row.append(0)
                    continue
                kk = round(float(k)); seen.add(kk)
                s_ = st.setdefault(kk, {'on': False, 'n_on': 0, 'n_off': 0})
                if s_['on']:
                    s_['n_off'] = 0 if x else s_['n_off'] + 1
                    if s_['n_off'] >= hold:
                        s_.update(on=False, n_on=0, n_off=0)
                else:
                    s_['n_on'] = s_['n_on'] + 1 if x else 0
                    if s_['n_on'] >= hold:
                        s_.update(on=True, n_on=0, n_off=0)
                row.append(1 if s_['on'] else 0)
            for kk in list(st):                         # strike left the ladder: counts as "not raw"
                if kk not in seen:
                    s_ = st[kk]
                    if s_['on']:
                        s_['n_off'] += 1
                        if s_['n_off'] >= hold:
                            del st[kk]
                    else:
                        del st[kk]
            res.append(row)
        _GDV_CACHE[key] = res
    return _GDV_CACHE[key]


# ---- Spd★ 2-cycle hold -> 'Level Engine'!BG123:BG126 (2026-10-07, Giggles) ----------------
# Same contract as the live engine: the Max/Min Speed strikes of the PREVIOUS two cycles of the same
# session (BG123 Max 1 ago, BG124 Max 2 ago, BG125 Min 1 ago, BG126 Min 2 ago). Built from the archived
# ladder by cycle index, so seeking/jumping gives the same answer as playing through. The workbook (KY)
# applies the positive-gamma (not fragile) gate, the side-aligned speed test and the BG127 switch.
SPD_HOLD_N = 2


def _spd_extremes(lad):
    best_hi = best_lo = None
    for r in lad or []:
        try:
            k, v = r[0], r[8]
        except Exception:
            continue
        if not (isinstance(k, (int, float)) and isinstance(v, (int, float))) or k != k or v != v:
            continue
        if best_hi is None or v > best_hi[1]:
            best_hi = (round(float(k)), v)
        if best_lo is None or v < best_lo[1]:
            best_lo = (round(float(k)), v)
    return (best_hi[0] if best_hi else None, best_lo[0] if best_lo else None)


def _write_spd_hold(idx):
    """Level Engine BG123:BG126 = previous SPD_HOLD_N cycles' Max/Min Speed strikes. Never raises."""
    try:
        if not str(sht_le['BF123'].value or '').startswith('(engine) MAX SPEED strike 1 cycle ago'):
            return
        day = cycles[idx]['dt'].date()
        prev = []
        for j in range(idx - 1, max(-1, idx - 1 - SPD_HOLD_N), -1):
            if j >= 0 and cycles[j]['dt'].date() == day:
                prev.append(_spd_extremes(cycles[j].get('ladder')))
            else:
                break
        prev += [(None, None)] * (SPD_HOLD_N - len(prev))
        sht_le.range('BG123:BG126').value = [[prev[0][0]], [prev[1][0]], [prev[0][1]], [prev[1][1]]]
    except Exception as e:
        try:
            sht_le.range('BG123:BG126').value = [[None]] * 4
        except Exception:
            pass
        print(f"   ! Spd★ hold write skipped ({e})")


# ---- VEX breakout take-profit latch -> 'Level Engine'!LO9:LO55 (2026-10-07, Giggles) --------------
# Same contract as the live engine: positive gamma (not fragile), |VEX| >= BG142 working against the level on the
# CURRENT fast IV, held BG143 cycles on / off. One forward pass per (threshold, hold) so seeking gives the same answer.
_VB_CACHE = {}


def vb_series(thr=1000000, hold=2):
    key = (thr, hold)
    if key not in _VB_CACHE:
        res, st, day = [], {}, None
        for ci, c in enumerate(cycles):
            if c['dt'].date() != day:
                st, day = {}, c['dt'].date()
            pos = (not c.get('gneg')) and _FRAG_HELD[ci] != 1
            lad = c.get('ladder') or []
            if not pos:
                st = {}
                res.append([0] * len(lad))
                continue
            spot = c.get('spot')
            iv = str(_IVFAST[ci] or '').strip().upper()
            Rl = {round(k) for k in (c.get('R') or []) if isinstance(k, (int, float)) and k == k}
            Sl = {round(k) for k in (c.get('S') or []) if isinstance(k, (int, float)) and k == k}
            row = []
            for r in lad:
                k, vx = r[0], r[5]
                if not isinstance(k, (int, float)):
                    row.append(0); continue
                kk = round(float(k)); raw = False
                if isinstance(vx, (int, float)) and abs(vx) >= thr and isinstance(spot, (int, float)) and iv in ('UP', 'DOWN'):
                    side = 'R' if kk in Rl else ('S' if kk in Sl else ('R' if k > spot else 'S'))
                    buy = (vx > 0 and iv == 'DOWN') or (vx < 0 and iv == 'UP')
                    raw = buy if side == 'R' else (not buy)
                s_ = st.setdefault(kk, {'on': False, 'n_on': 0, 'n_off': 0})
                if s_['on']:
                    s_['n_off'] = 0 if raw else s_['n_off'] + 1
                    if s_['n_off'] >= hold:
                        s_.update(on=False, n_on=0, n_off=0)
                else:
                    s_['n_on'] = s_['n_on'] + 1 if raw else 0
                    if s_['n_on'] >= hold:
                        s_.update(on=True, n_on=0, n_off=0)
                row.append(1 if s_['on'] else 0)
            res.append(row)
        _VB_CACHE[key] = res
    return _VB_CACHE[key]


def _write_vb(idx):
    """Level Engine LO9:LO55 = latched VEX-breakout flag per ladder row. Never raises."""
    try:
        if not str(sht_le['LO8'].value or '').startswith('vexBreakLatch'):
            return
        thr = sht_le['BG142'].value; thr = thr if isinstance(thr, (int, float)) else 1000000
        hold = sht_le['BG143'].value; hold = max(1, int(hold)) if isinstance(hold, (int, float)) else 2
        v = list(vb_series(thr, hold)[idx] or [])
        v = (v + [0] * 47)[:47]
        sht_le.range('LO9:LO55').value = [[x] for x in v]
    except Exception as e:
        print(f"   ! VEX-breakout latch write skipped ({e})")


# ---- SAND✓ support lock -> 'Level Engine'!MB9:MB55 (2026-10-08, Giggles) -------------------------
# NEGATIVE gamma. A SAND✓ support (Level Engine LR = 1) that is SAFE (HP = 0), ALREADY in the support rows
# (KNM AL49:AL51, rows_s) and within SAND_NEAR_PTS of spot is LOCKED -- the lock holds a slot it earned, never creates one: the workbook then
# stops vanna SELL / vanna flat / zomma acceleration from flipping it UNSAFE. Release: spot 3+ pts below the
# level for 2 cycles in a row (a break), the level stops being SAND✓, spot 5+ pts above it, the regime leaves
# negative gamma, or a new session. Reads LR / HP from the PREVIOUS calc (one-cycle lag), writes MB before this
# cycle's calc. Written only when MB8 carries the sandLock header. Never raises. UNTESTED.
SAND_LOCK_ENABLED = True
SAND_BRK_PTS, SAND_BRK_N, SAND_AWAY_PTS, SAND_NEAR_PTS = 3.0, 2, 5.0, 5.0
_sand_lock = {}          # strike -> {'brk': consecutive break cycles}
_sand_day = None
_sand_last_dt = None


def sand_lock_step(sht_le, spot, neg, day, rows_s=None):
    """One cycle of the SAND✓ lock; writes MB9:MB55 aligned to AA9:AA55. Never raises."""
    global _sand_day
    try:
        if not str(sht_le['MB8'].value or '').startswith('sandLock'):
            return
        if _sand_day != day:
            _sand_lock.clear(); _sand_day = day
        ks = sht_le.range('AA9:AA55').value
        lr = sht_le.range('LR9:LR55').value
        hp = sht_le.range('HP9:HP55').value
        if not neg or not isinstance(spot, (int, float)):
            _sand_lock.clear()
        else:
            for k, l, h in zip(ks, lr, hp):
                if not isinstance(k, (int, float)):
                    continue
                kk = round(float(k)); is_sand = (l in (1, 1.0))
                st = _sand_lock.get(kk)
                if st is None:
                    in_rows = kk in {round(float(x)) for x in (rows_s or []) if isinstance(x, (int, float))}
                    if is_sand and h in (0, 0.0) and in_rows and abs(spot - kk) <= SAND_NEAR_PTS and spot >= kk - SAND_BRK_PTS:
                        _sand_lock[kk] = {'brk': 0}
                    continue
                if not is_sand or spot >= kk + SAND_AWAY_PTS or h in (1, 1.0):   # 1.0 = UNSAFE for a structural reason
                    del _sand_lock[kk]; continue
                st['brk'] = st['brk'] + 1 if spot <= kk - SAND_BRK_PTS else 0
                if st['brk'] >= SAND_BRK_N:
                    del _sand_lock[kk]
        sht_le.range('MB9:MB55').value = [[1 if (isinstance(k, (int, float)) and round(float(k)) in _sand_lock) else 0] for k in ks]
    except Exception as e:
        print(f"   ! SAND lock skipped ({e})")


def _write_gdv(idx):
    """Level Engine KO9:KO55 = latched gDex-rule flag per ladder row. Never raises."""
    try:
        _near = sht_le['BG98'].value
        _near = _near if isinstance(_near, (int, float)) else 5
        v = list(gdv_series(_near)[idx] or [])
        v = (v + [0] * 47)[:47]
        sht_le.range('KO9:KO55').value = [[x] for x in v]
    except Exception as e:
        print(f"   ! gDex-rule latch write skipped ({e})")

# timestamp index for O(log N) time seeks and Jump-to-Time
_CYCLE_DT = [c['dt'] for c in cycles]

# event markers (RECONNECT / RECENTER / SPIKE? ...) for the marker jump list
_EVENTS = [(i, str(cycles[i].get('event'))) for i in range(N)
           if cycles[i].get('event') not in (None, "", 0)]

print(f" done ({time.perf_counter() - _t0_pre:.1f}s)")

# ---- performance counters ----
_PERF = {"frames": 0, "calc_s": 0.0, "ncalc": 0, "frame_s": 0.0,
         "frame_max": 0.0, "excel_s": 0.0, "key_s": 0.0, "keys": 0, "key_max": 0.0}


# ---- chop yield: ported from live 2026-09-22 (identical function) ----
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


# ---- flip resistance gate hold: ported from live 2026-09-22 (identical logic) ----
_flip_gate_active = False
_flip_gate_below = 0


def apply_flip_gate_hysteresis(raw, hold):
    """1 while the latched Flip gate should stand, else 0. Instant-on, re-trigger during
       the hold resets the counter, clears after `hold` consecutive cycles with the raw
       gate off."""
    global _flip_gate_active, _flip_gate_below
    if raw:
        _flip_gate_active = True;  _flip_gate_below = 0
    elif _flip_gate_active:
        _flip_gate_below += 1
        if _flip_gate_below >= hold:
            _flip_gate_active = False; _flip_gate_below = 0
    return 1 if _flip_gate_active else 0


# ---- shelf/wall hysteresis: ported from live 2026-09-22 (identical logic) ----
# A new shelf/wall must persist SW_LOCK_HOLD cycles in a row before the locked copy
# (CT/CW) moves. Replay previously copied the raw detection straight through.
SW_LOCK_HOLD = 3
_swR_lock = None; _swR_pend = None
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


def _calc():
    """wb.app.calculate() with timing. Identical behaviour, measured."""
    _t = time.perf_counter()
    wb.app.calculate()
    _PERF["calc_s"] += time.perf_counter() - _t
    _PERF["ncalc"] += 1


def perf_report():
    f = _PERF["frames"] or 1
    return (
        "\n" + "=" * 58 + "\n  REPLAY PERFORMANCE\n" + "=" * 58 + "\n"
        f"  frames rendered      {_PERF['frames']}\n"
        f"  average frame time   {_PERF['frame_s'] / f * 1000:7.1f} ms\n"
        f"  maximum frame time   {_PERF['frame_max'] * 1000:7.1f} ms\n"
        f"  Excel recalc time    {_PERF['calc_s'] / f * 1000:7.1f} ms/frame"
        f"   ({_PERF['ncalc']} calls)\n"
        f"  Excel write+read     {_PERF['excel_s'] / f * 1000:7.1f} ms/frame\n"
        f"  keyboard latency     "
        f"{(_PERF['key_s'] / (_PERF['keys'] or 1)) * 1000:7.1f} ms avg"
        f"   / {_PERF['key_max'] * 1000:.1f} ms max\n" + "=" * 58)


# ---- latch reset (both latches are sheet-driven and cannot be replayed offline) ----
_last_idx = None

def _sv_sq_clear():
    """Wipe all spot-vol / squeeze session state back to start-of-day."""
    global _sv_open_spot, _sv_open_v1d, _sv_run, _sv_corr, _sv_ud_since, _sv_push_since
    global _svx_hold, _svx_dir, _svx_since
    global _sq_node, _sq_ratio_open, _sq_dex_sign, _sq_dex_flips, _sq_since
    # a seek rewinds the session, so the vol-split window must be cleared or a
    # scrub backwards would compare against cycles that have not happened yet.
    _vs_trail.clear()
    _svx_trail.clear()
    _svx_hold = 0; _svx_dir = 0; _svx_since = None
    _sv_spot.clear(); _sv_v1d.clear()
    _sv_open_spot = _sv_open_v1d = None
    _sv_run = 0; _sv_corr = None; _sv_ud_since = None; _sv_push_since = None
    _sq_node = None; _sq_ratio_open = None; _sq_dex_sign = None
    _sq_dex_flips = 0; _sq_since = None


def _sv_sq_rebuild(idx):
    """Re-run both readings over cycles 0..idx-1 so a seek lands with the state the
       day actually had at that point.

       These two are NOT like the box / PROX latches. Those depend on recalculated
       sheet values and cannot be reconstructed offline, so a seek has to clear them.
       These depend only on archived columns -- spot, vix, vix1d, gex, dex -- so the
       state at any cycle is a pure function of the cycles before it and CAN be
       rebuilt exactly. Clearing them instead would re-take the session opens from
       wherever you scrubbed to, which silently reads every condition against the
       wrong reference and blanks both lines."""
    global _RPL_HM, _RPL_TS
    _sv_sq_clear()
    _keep, _keep_ts = _RPL_HM, _RPL_TS
    for _j in range(idx):
        _c = cycles[_j]
        _sp = _c['spot']
        if _sp is None:
            continue
        _RPL_HM = _c['ts'][11:16]
        _RPL_TS = _rpl_ts(_c['ts'])
        spot_vol_flags(_sp, _c['vix1d'], _c['vix'])
        squeeze_conditions(_sp, _c['ladder'], _c['vix'], _c['vix1d'])
        # vol_split is the same kind of reading -- a pure function of archived
        # columns -- so it must be rebuilt here too. Without this its 15-minute
        # window starts empty after every seek and the marker can never fire:
        # it only ever holds the one cycle you landed on.
        vol_split(_c.get('atm_iv'), _c['vix1d'], _rpl_ts(_c['ts']))
    _RPL_HM, _RPL_TS = _keep, _keep_ts


def _reset_latches():
    global _box_node, _box_pend, _prox_strike, _prox_miss
    _box_node = None; _box_pend = None
    _prox_strike, _prox_miss = None, 0
    _shape_hold.clear()      # edge/trough hold: a seek / step-back / gap starts it fresh




# ============ spot/vol co-movement + squeeze counter (ported from live 2026-08-05) ============
# Live stamps "since HH:MM" from the wall clock. In replay that would record the time
# you happened to press play, so both functions read this instead -- set to the cycle's
# own archived timestamp before each render.
_RPL_HM = ""
_RPL_TS = None          # full timestamp of the cycle being rendered, for the sign test
# Replay convention: same code, same thresholds. Both are pure functions of the
# archived spot / vix / vix1d / gex / dex columns, so a replayed day reproduces
# exactly what live would have shown on the day.
# ---- spot / front-end-vol co-movement (Master Dashboard E25) ----------------
# Two separate readings, both OBSERVATION ONLY -- no directive, no play-line
# effect, no Level Test Log entry.
#   1. SPOT UP / VOL UP : spot and VIX1D both above their session opens. Coarse
#      and common; says the rally is being paid for rather than drifting.
#   2. VOL RISING WITH EVERY PUSH : spot ticks and VIX1D ticks moving TOGETHER
#      over a rolling window. Rare -- 2 days in 33 of live archive (2026-07-22,
#      2026-08-04), both +19 and +38 pts at 60 min against a +2.1 null. n=2 is
#      NOT evidence; this exists to accumulate a timestamped sample, nothing more.
#      Every one of the 33 days shows NEGATIVE session correlation except
#      2026-08-04 (+0.13), so a sustained positive reading is genuinely unusual.
SV_CORR_WIN  = 60         # cycles in the rolling correlation window (60 x 30s = 30 min)
SV_CORR_MIN  = 0.30       # correlation above this counts as "moving together"
SV_CORR_HOLD = 6          # consecutive cycles required before it displays (anti-flap)
SV_OPEN_TOL  = 0.05       # VIX1D pts above the open before "vol up" counts (tick noise)

# ---- spot / TERM-vol 10-minute sign test (Master Dashboard E25, third reading)
# Added 2026-08-13. The two readings above both run on VIX1D. On 2026-08-13 spot
# ran 7748 -> 7815 while VIX1D FELL from its open (9.32 -> 6.84 in the first ten
# minutes), so neither fired during the move; the up/up marker only set at 20:10.
# The term VIX rose with the move throughout, which is what this reads.
#
# Sign test rather than correlation: correlation needs its window to fill before
# it can say anything, and on 2026-08-13 it did not clear +0.30 until 15:08, by
# which point 55 of the 66 points were already gone. A trailing sign test fires
# as soon as both legs are true.
#
# CALIBRATION (40 archive days, 4735 trailing-10-min spot-up cycles, baseline
# P(spot higher 20 min later) = 0.525):
#     VIX delta >= 0.00   n=406  29 days  P=0.611
#     VIX delta >= 0.05   n=221  18 days  P=0.692   <- chosen
#     VIX delta >= 0.10   n=116  11 days  P=0.750
#     VIX delta >= 0.15   n= 54   8 days  P=0.630
#     VIX delta >= 0.30   n=  8   4 days  P=0.250
# Monotonic to 0.10 then collapsing is the shape of a threshold running out of
# data, not an optimum, so 0.05 is taken one step back from the peak for roughly
# double the events and 18 days of coverage. The same sweep on VIX1D is FLAT at
# baseline (P=0.513/0.503/0.488 at 0.05/0.10/0.15) -- the edge is in the term
# VIX, not the front end.
#
# n=221 is nowhere near 221 independent observations: the cycles overlap heavily
# and it is closer to 18 day-episodes. 0.692 is directional, not an established
# rate, and it sits above the realism ceiling for exactly that reason.
# OBSERVATION ONLY -- no directive, no play-line effect, no Level Test Log entry,
# and nothing in the Level Engine reads it.
# ---- vol split: ATM IV vs VIX1D disagreeing ----------------------------------
# Added 2026-08-14. On 2026-08-14 ATM IV fell 31% across the session while VIX1D
# ROSE 1.22. The vanna/regime read keys off ATM IV; the vol-bid read keys off
# VIX1D. They pointed opposite ways all day and the tape followed VIX1D, so the
# "Vanna-fueled Melt Up" label sat on the dashboard through a 31-point grind DOWN.
#
# WHAT THIS MARKER DOES AND DOES NOT CLAIM.  It says the two vol measures
# disagree, so any read keyed to one of them is standing on one leg. It does NOT
# say the regime read fails -- that is untested and the available evidence points
# the other way: across 23 days, forward 30-minute absolute move is SMALLER when
# they disagree (7.15 pts) than when aligned (10.01 pts). Divergence goes with
# quieter, choppier tape, not with a breakdown. Wording was chosen to match.
#
# Whether the regime label specifically underperforms during a split becomes
# testable once iv_state has accumulated history -- that column started 2026-08-14
# and has none yet. Do not assert it before then.
#
# FREQUENCY (23 days): among cycles where both measures move materially -- 64% of
# all cycles -- they disagree 21% of the time, every day, range 8%-44%. Frequent
# enough to matter, rare enough not to become wallpaper.
VS_WIN_MIN  = 15.0        # trailing window
VS_IV_MIN   = 0.02        # |ATM IV| relative change before it counts as moving
VS_V1D_MIN  = 0.05        # |VIX1D| absolute change before it counts as moving

_vs_trail = deque()       # (datetime, atm_iv, vix1d)

SVX_WIN_MIN = 10.0        # trailing window, minutes
SVX_WIN_FILL = 0.80       # window must be this full before the test can fire
SVX_SPOT    = 5.0         # spot points over the window
SVX_VIX     = 0.05        # term VIX points over the window
SVX_HOLD    = 8           # cycles the reading is held after it stops firing

_svx_trail = deque()      # (datetime, spot, vix) inside the trailing window
_svx_hold  = 0            # cycles left on the latch
_svx_dir   = 0            # +1 spot up / vol up, -1 spot down / vol up, 0 off
_svx_since = None         # HH:MM the current direction first fired


# ---- squeeze condition counter (Master Dashboard E26) -----------------------
# FIVE conditions, all logged every cycle, DISPLAYED only at 5/5.
# Chosen by comparing the two days that scored best on the (failed) squeeze-gate
# study: 2026-08-04, a genuine +109.6 pt trend closing at 99% of range, and
# 2026-07-24, which the same gate also liked but which opened 7408 and closed
# 7405 after round-tripping a 64 pt range. The set below separates them 5/5 vs
# 2/5. That separation is FITTED to two known days -- it is a description, not a
# tested rule. Nothing here feeds the play line, the regime read or the level log.
#   1 POS-GAMMA   net GEX > 0. 04 Aug: 0% of session negative. 24 Jul: 81%.
#   2 ABOVE NODE  spot above the opening king node -- the pin is behind price.
#   3 THIN ABOVE  |GEX| above spot < SQ_OVERHEAD of the ladder total.
#   4 DEX ONE-WAY net DEX has not changed sign all session. 04 Aug: 0 flips.
#                 24 Jul: 8.
#   5 VOL CHEAP   VIX1D/VIX opened below SQ_RATIO_OPEN and is now above its open.
#                 04 Aug 0.53 -> 0.85 (room to expand). 24 Jul 0.84 -> 0.84 (none).
SQ_OVERHEAD   = 0.25      # overhead |GEX| share below which condition 3 is true
SQ_RATIO_OPEN = 0.60      # VIX1D/VIX must have OPENED below this for condition 5
SQ_RATIO_RISE = 0.02      # and be this much above its own open now

_sv_spot = deque(maxlen=SV_CORR_WIN + 1)   # spot trail for the correlation
_sv_v1d  = deque(maxlen=SV_CORR_WIN + 1)   # VIX1D trail, same cadence
_sv_open_spot = None                        # session opens, set on first good cycle
_sv_open_v1d  = None
_sv_run  = 0                                # consecutive cycles above SV_CORR_MIN
_sv_corr = None                             # last computed correlation (archived)
_sq_node = None                             # opening king node (condition 2 reference)
_sq_ratio_open = None                       # opening VIX1D/VIX (condition 5 reference)
_sq_dex_sign = None                         # first non-zero net-DEX sign seen
_sq_dex_flips = 0                           # sign changes since (condition 4)
_sq_since = None                            # HH:MM the counter first reached 5/5
_sv_ud_since = None                         # HH:MM the day first qualified spot-up/vol-up
_sv_push_since = None                       # HH:MM the correlation flag first fired

def squeeze_conditions(spot, table_rows, vix, v1d):
    """(display_string, count, [c1..c5]) for the squeeze condition counter.

       Every condition is returned regardless of the count so the archive carries
       the full vector -- the point of logging is to be able to ask later whether
       5/5 behaves differently from 2/5, which needs the low readings too."""
    global _sq_node, _sq_ratio_open, _sq_dex_sign, _sq_dex_flips, _sq_since
    if spot is None or math.isnan(spot) or not table_rows:
        return "", 0, [0] * 5

    gex = [(row[0], row[2]) for row in table_rows
           if isinstance(row[0], (int, float)) and isinstance(row[2], (int, float))]
    if not gex:
        return "", 0, [0] * 5
    net_gex = sum(g for _k, g in gex)
    net_dex = sum(row[4] for row in table_rows if isinstance(row[4], (int, float)))
    tot_abs = sum(abs(g) for _k, g in gex)
    above   = sum(abs(g) for k, g in gex if k > spot)

    if _sq_node is None:                       # opening references, set once
        _sq_node = max(((abs(g), k) for k, g in gex))[1]
        if vix and v1d and vix > 0:
            _sq_ratio_open = v1d / vix

    _dsign = 1 if net_dex > 0 else (-1 if net_dex < 0 else 0)
    if _dsign:
        if _sq_dex_sign is None:
            _sq_dex_sign = _dsign
        elif _dsign != _sq_dex_sign:
            _sq_dex_flips += 1
            _sq_dex_sign = _dsign

    ratio = (v1d / vix) if (vix and v1d and vix > 0) else None
    c = [
        1 if net_gex > 0 else 0,
        1 if spot > _sq_node else 0,
        1 if (tot_abs and above / tot_abs < SQ_OVERHEAD) else 0,
        1 if _sq_dex_flips == 0 and _sq_dex_sign is not None else 0,
        1 if (ratio is not None and _sq_ratio_open is not None
              and _sq_ratio_open < SQ_RATIO_OPEN
              and ratio > _sq_ratio_open + SQ_RATIO_RISE) else 0,
    ]
    n = sum(c)
    if n == 5 and _sq_since is None:
        _sq_since = _RPL_HM
    txt = ""
    if n == 5:
        txt = (f"SQUEEZE CONDITIONS 5/5 — pos gamma, spot above node, thin "
               f"overhead, DEX one-way, front-end vol expanding from cheap "
               f"(since {_sq_since})  ·  OBSERVATION ONLY, untested")
    return txt, n, c


def _pearson(xs, ys):
    n = len(xs)
    if n < 5:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)



def _rpl_ts(ts):
    """Archive timestamp -> datetime, for the trailing-window sign test.

       The two readings above need only cycle ORDER, so _RPL_HM was enough. This
       one measures a real 10-minute window, so a replayed cycle has to carry the
       archive's own clock -- using wall time here would make every seek fire or
       suppress the test on the operator's clock instead of the session's."""
    try:
        return datetime.datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def vol_split(atm_iv, v1d, now):
    """Marker string when ATM IV and VIX1D are moving opposite ways, else "".

       Both legs must be moving materially before a direction is read off them --
       comparing the signs of two numbers that are barely changing would fire on
       tick noise and the marker would be permanently lit."""
    if (atm_iv is None or v1d is None or now is None
            or (isinstance(atm_iv, float) and math.isnan(atm_iv))
            or (isinstance(v1d, float) and math.isnan(v1d)) or not atm_iv):
        return ""
    _vs_trail.append((now, float(atm_iv), float(v1d)))
    _cut = now - datetime.timedelta(minutes=VS_WIN_MIN)
    while len(_vs_trail) > 2 and _vs_trail[1][0] <= _cut:
        _vs_trail.popleft()
    if (now - _vs_trail[0][0]).total_seconds() < VS_WIN_MIN * 60 * 0.8:
        return ""
    _iv0, _v0 = _vs_trail[0][1], _vs_trail[0][2]
    if not _iv0:
        return ""
    d_iv = float(atm_iv) / _iv0 - 1.0
    d_v1 = float(v1d) - _v0
    if abs(d_iv) < VS_IV_MIN or abs(d_v1) < VS_V1D_MIN:
        return ""
    if (d_iv > 0) == (d_v1 > 0):
        return ""
    return ("VOL SPLIT \u2014 ATM IV and VIX1D moving opposite ways"
            "  \u00b7  directional reads carry less weight")


def spot_vix_sign(spot, vix, now, hm):
    """(direction, display_string) for the 10-minute spot / term-VIX sign test.

       Latch: once fired the reading is held SVX_HOLD cycles so it does not blink
       through every pause in a trend (on 2026-08-13 the raw condition dropped out
       at 14:44 on a 5-pt pullback and returned at 14:45). The latch clears early
       only when the trailing spot move crosses back through zero -- a genuine
       reversal of the leg being read, not merely a slowdown."""
    global _svx_hold, _svx_dir, _svx_since
    if (spot is None or vix is None or now is None
            or (isinstance(spot, float) and math.isnan(spot))
            or (isinstance(vix, float) and math.isnan(vix))):
        return _svx_dir, ""

    _svx_trail.append((now, float(spot), float(vix)))
    _cut = now - datetime.timedelta(minutes=SVX_WIN_MIN)
    while len(_svx_trail) > 2 and _svx_trail[1][0] <= _cut:
        _svx_trail.popleft()          # keep one sample at/before the window edge

    _age = (now - _svx_trail[0][0]).total_seconds()
    if _age < SVX_WIN_MIN * 60 * SVX_WIN_FILL:
        return _svx_dir, ""           # window not yet filled -- say nothing

    ds = float(spot) - _svx_trail[0][1]
    dv = float(vix) - _svx_trail[0][2]

    fire = 0
    if dv >= SVX_VIX:
        if ds >= SVX_SPOT:
            fire = 1
        elif ds <= -SVX_SPOT:
            fire = -1

    if fire:
        if _svx_dir != fire:
            _svx_since = hm
        _svx_dir, _svx_hold = fire, SVX_HOLD
    elif _svx_hold:
        if (_svx_dir > 0 and ds < 0) or (_svx_dir < 0 and ds > 0):
            _svx_hold, _svx_dir = 0, 0        # trailing move reversed through zero
        else:
            _svx_hold -= 1
            if _svx_hold == 0:
                _svx_dir = 0

    if _svx_dir == 0:
        return 0, ""
    _held = "" if fire else " · holding"
    # HEADLINE WORDING IS LOAD-BEARING. Master Dashboard AT40/AT41/AT47/AT48 fire
    # "UNSAFE·Spot Up Vol Up" on SEARCH("SPOT UP / VOL UP —", $E$26) -- INCLUDING the
    # trailing em-dash. Change this string and those four markers go silently dark.
    # The old wording was "SPOT UP / TERM VOL UP"; it moved here on 2026-08-19 when
    # the session-open reading stopped rendering, and the now-dead "TERM VOL" arm was
    # stripped from all four formulas in the same cut.
    _lead = ("SPOT UP / VOL UP" if _svx_dir > 0 else "SPOT DOWN / VOL UP")
    _what = ("the push is paying up for vol, not drifting"
             if _svx_dir > 0 else "the slide is bidding vol, not bleeding")
    return _svx_dir, (f"{_lead} \u2014 {_what} (10-min: spot {ds:+.1f}, "
                      f"VIX {dv:+.2f} \u00b7 since {_svx_since}{_held}) "
                      f"\u00b7 OBSERVATION ONLY")

def spot_vol_flags(spot, v1d, vix=None):
    """(display_string, updown_flag, correlation) for the two co-movement readings.

       The correlation is taken on CHANGES, not levels: whether each push in spot
       is itself bidding front-end vol, which is what call buying looks like from
       outside. A day can finish spot-up / vol-up with the two rising at entirely
       different times (2026-06-29: +1.45% spot, +39.7% VIX1D, correlation -0.29)
       -- that is the first flag, not the second."""
    global _sv_open_spot, _sv_open_v1d, _sv_run, _sv_corr
    global _sv_ud_since, _sv_push_since
    if spot is None or v1d is None or math.isnan(spot) or math.isnan(v1d) or v1d <= 0:
        return "", 0, _sv_corr
    if _sv_open_spot is None:
        _sv_open_spot, _sv_open_v1d = float(spot), float(v1d)
    _sv_spot.append(float(spot))
    _sv_v1d.append(float(v1d))

    updown = 1 if (spot > _sv_open_spot and v1d > _sv_open_v1d + SV_OPEN_TOL) else 0
    _hm = _RPL_HM
    if updown and _sv_ud_since is None:
        _sv_ud_since = _hm                    # day marker: set once, never cleared

    ds = [_sv_spot[i + 1] - _sv_spot[i] for i in range(len(_sv_spot) - 1)]
    dv = [_sv_v1d[i + 1] - _sv_v1d[i] for i in range(len(_sv_v1d) - 1)]
    c = _pearson(ds, dv) if len(ds) >= SV_CORR_WIN else None
    _sv_corr = c
    _sv_run = _sv_run + 1 if (c is not None and c > SV_CORR_MIN) else 0

    if _sv_run >= SV_CORR_HOLD and _sv_push_since is None:
        _sv_push_since = _hm

    # LIVE READINGS ONLY. Changed 2026-08-19 in live_king_node.py; ported here so the
    # replay renders the same line.
    #
    # This line used to lead with the SESSION-OPEN test -- spot above its open AND
    # VIX1D above its open -- under the headline "SPOT UP / VOL UP". That reads as a
    # live co-movement alert and is not one: it is two levels compared with where
    # they started, it goes true on any gap up that drags the front end with it, and
    # it then stays true all session regardless of what vol does afterwards.
    #
    # The headline now belongs to the 10-minute test below, which is a real
    # co-movement measurement and writes nothing when it is not firing.
    #
    # The session-open flag itself is UNCHANGED and still archived as sv_updown --
    # backtests read that column. It simply no longer renders.
    #
    # No lapsed forms on this line any more. A lapsed marker is a record of the day,
    # not a state, and mixing the two on one line is what made this ambiguous in the
    # first place.
    parts = []
    if _sv_run >= SV_CORR_HOLD:
        parts.append(f"VOL RISING WITH EVERY PUSH — call buying is driving "
                     f"the move (rare · {c:+.2f} · since {_sv_push_since})")

    # Second reading: 10-minute spot / TERM-VIX sign test. Independent of the
    # correlation reading above -- that runs on VIX1D and stayed dark through the
    # 2026-08-13 advance because the front end fell from its open while the term
    # VIX rose. This test now carries the SPOT UP / VOL UP headline.
    _svx_d, _svx_txt = spot_vix_sign(spot, vix, _RPL_TS or datetime.datetime.now(), _RPL_HM)
    if _svx_txt:
        parts.append(_svx_txt)
    return "   ·   ".join(parts), updown, c

# ============ render one snapshot ============
def render_cycle(idx):
    c = cycles[idx]
    # Box + PROX latches carry state across cycles and are driven by recalculated sheet
    # values, so they cannot be rebuilt offline the way obs_flag_at() rebuilds its marker.
    # Clear them on any non-sequential move (seek / step-back / restart), and on a feed
    # gap -- the same rule live applies in reconnect().
    global _last_idx
    if _last_idx is None or idx != _last_idx + 1 or c.get('event') == 'RECONNECT':
        _reset_latches()
        _sv_sq_rebuild(idx)          # replay the day up to here, do not clear
    _last_idx = idx
    if c.get('event') == 'RECONNECT':
        g = c.get('gap_secs')
        gtxt = f" \u2014 feed gap {int(g)//60}m {int(g)%60:02d}s" if g and g > 0 else ""
        sys.stdout.write(
            f"\n  \u27f2 RECONNECT at {c['ts'][11:]}{gtxt}  "
            f"(no data was captured during this window)\n")
        sys.stdout.flush()
    # 2026-09-27: mark the cycle as in progress BEFORE any data goes in. The final label
    # (K26, written at the very end of this function) replaces it, so a workbook saved
    # mid-cycle reads "updating" instead of the previous cycle's time over new data.
    try:
        sht['K26'].value = 'REPLAY ' + c['ts'][11:] + ' \u00b7 updating\u2026'
    except Exception:
        pass
    spot = c['spot']
    sht['B4'].value = spot
    if c['vix']   is not None: sht['B5'].value = c['vix']
    if c['vvix']  is not None: sht['D5'].value = c['vvix']
    if c['vix1d'] is not None: sht['F5'].value = c['vix1d']

    # ---- spot/vol co-movement (E25) + squeeze counter (E26), mirroring live ----
    global _RPL_HM, _RPL_TS
    _RPL_HM = c['ts'][11:16]
    _RPL_TS = _rpl_ts(c['ts'])
    _sv_txt, _sv_ud, _sv_c = spot_vol_flags(spot, c['vix1d'], c['vix'])
    if sht_md is not None and MD_SPOTVOL_CELL:
        sht_md[MD_SPOTVOL_CELL].value = _sv_txt   # probe-resolved, NOT hardcoded
    _sq_txt, _sq_n, _sq_cond = squeeze_conditions(spot, c['ladder'], c['vix'], c['vix1d'])
    if sht_md is not None and MD_SQUEEZE_CELL:
        sht_md[MD_SQUEEZE_CELL].value = _sq_txt   # probe-resolved, NOT hardcoded

    # ---- vol split ----------------------------------------------------------
    # Was missing entirely until 2026-08-14: vol_split() was added to this file but
    # never called, so F19 stayed blank in replay and every downstream warning on
    # rows 40/41/47/48 stayed dark. Uses the archive clock, not wall time.
    if sht_md is not None and MD_VSPLIT_CELL:
        try:
            sht_md[MD_VSPLIT_CELL].value = vol_split(
                c.get('atm_iv'), c.get('vix1d'), _rpl_ts(c['ts']))
        except Exception as e:
            print(f"   ! vol split write failed ({e})")

    # ---- vol directions -> P4/P5/P6 (drives Vol regime line F16 + tension flag) ----
    sht['P4'].value = c['vix_dir']
    sht['P5'].value = c['vvix_dir']
    sht['P6'].value = c['v1d_dir']

    # ---- Front-End warn latch -> Level Engine CT14 (Master amber border reads it) ----
    sht_le['CT14'].value = c['warn']
    # ---- ATM IV direction -> B3. D5 reads it; without this D5 = "FLAT" and the
    # whole reaction table replays EMPTY (CF9=0 -> CG9="" -> CU9/CV9 lose their gates).
    sht_le['B3'].value = c.get('atm_iv_dir') or None
    if c.get('atm_iv'):
        sht_le['C3'].value = round(float(c['atm_iv']), 4)

    # ---- skew monitor -> O11/O12/P11/P12 + KNM AB16 + Master skew line (mirrors live) ----
    if SKEW_ENABLED:
        sht['O11'].value = 'Put skew:'
        sht['P11'].value = c.get('sk_put')
        sht['O12'].value = 'Call skew:'
        sht['P12'].value = c.get('sk_call')
        sht['AB16'].value = c.get('sk_head')
        if sht_md is not None and MD_SKEW_CELL and c.get('sk_head'):
            sht_md[MD_SKEW_CELL].value = c['sk_head'][:155]
            _sk_spans = c.get('sk_spans') or []
            if _sk_spans:
                try:
                    _skew_rng = sht_md[MD_SKEW_CELL]
                    for _sk_st, _sk_ln, (_sk_r, _sk_g, _sk_b) in _sk_spans:
                        _tape_chars(
                            getattr(_skew_rng, "api", _skew_rng),
                            _sk_st, _sk_ln
                        ).Font.Color = _sk_r + (_sk_g << 8) + (_sk_b << 16)
                except Exception as _ske:
                    print(f"   ! skew colour failed ({_ske})")

    # ---- Net GEX monitor -> King Node Model AB12 (Master GEX SLOPE row reads it) ----
    sht['AB12'].value = _GEX_LINE[idx]

    # ---- Vol Tension -> King Node Model AB17 (Master Dashboard F18 reads it) ----
    # Must run after the GEX line (publishes c['gex_per15']) and after the skew block.
    try:
        _vt_ratio = None
        if isinstance(c['vix'], (int, float)) and isinstance(c['vix1d'], (int, float)) and c['vix']:
            _vt_ratio = float(c['vix1d']) / float(c['vix'])
        _vt_flip = None
        if c.get('gex_flip_dt') is not None:
            _vt_flip = (c['dt'] - c['gex_flip_dt']).total_seconds() / 60.0
        _vt_txt = vol_tension(c['net_gex'], _vt_ratio, c['v1d_dir'] == 'Up',
                              c.get('gex_per15'), _vt_flip,
                              c.get('sk_steep'), c.get('sk_psdir'))
        sht['AB17'].value = _vt_txt
        if MD_VT_CELL and sht_md is not None:
            vt_write(sht_md[MD_VT_CELL], _vt_txt)
    except Exception as e:
        print(f"   ! vol tension skipped ({e})")

    # ---- GEX SLOPE TAPE -> Master Dashboard, the line under GEX SLOPE ----
    # Per-cycle passthrough, no multi-cycle hold: index idx renders index idx.
    if MD_TAPE_CELL and sht_md is not None:
        try:
            _tp_txt, _tp_spans = _TAPE[idx]
            sht_md[MD_TAPE_CELL].value = _tp_txt
            if _tp_spans:
                tape_paint(sht_md[MD_TAPE_CELL], _tp_spans)
        except Exception as e:
            print(f"   ! tape line skipped ({e})")

    # ---- IV-top alert -> Level Engine BG78 / BG79 (mirrors live, 2026-09-24) ----
    try:
        sht_le['BG78'].value = _IVTOP[idx][0]
        sht_le['BG79'].value = (round(_IVTOP[idx][1], 4) if isinstance(_IVTOP[idx][1], float) else None)
    except Exception as e:
        print(f"   ! IV-top alert skipped ({e})")
    try:
        sht_le['BG80'].value = _IVFAST[idx] or None      # fast ATM IV direction (vanna)
    except Exception as e:
        print(f"   ! fast IV direction skipped ({e})")

    # ---- MELT-UP WATCH + FLOW (mirrors live, 2026-09-24) -------------------------
    if sht_md is not None:
        try:
            _mu_txt, _mu_n, _mu_cond = meltup_line(
                _MU_PRE[idx], spot, c.get('es_last'), c.get('es_s200'), c.get('gex_per15'),
                sht['D27'].value, sht['D26'].value, sht['A8'].value, sht_le['BG72'].value,
                sht['C11'].value, iv_regime=sht['L5'].value)
            if MD_MELTUP_CELL:
                sht_md[MD_MELTUP_CELL].value = _mu_txt
                try:    # 2026-09-29: Phenomenon-line grey (595959); 2026-10-07 (Giggles): GREEN while the FLOW SHIFT is on
                    _r, _g, _b = FLOW_GREEN if str(_mu_n).strip() in ("1", "1.0") else FLOW_BASE
                    _mu_font = getattr(sht_md[MD_MELTUP_CELL], "api", sht_md[MD_MELTUP_CELL]).Font
                    _mu_font.Color = _r + (_g << 8) + (_b << 16)
                    _mu_font.Bold = str(_mu_n).strip() in ("1", "1.0")
                except Exception as e:
                    print(f"   ! melt-up colour skipped ({e})")
            for _i, (_fc, _ft) in enumerate(zip(MD_FLOW_CELLS, flow_lines(_MU_PRE[idx]))):
                if _fc:
                    flow_paint(_i, sht_md[_fc], *_ft)
            if MD_FLOW1H_CELL:
                flow_h1_write(sht_md[MD_FLOW1H_CELL], *flow_h1_line(_MU_PRE[idx]))
        except Exception as e:
            print(f"   ! melt-up / flow skipped ({e})")

    if PRIOR_TPO_ENABLED:
        prior_tpo_write(sht_md)                  # prior-day SPX TPO -> Master Dashboard F77:H79

    # ---- NET GEX @ open+5 baseline -> King Node Model AB15 (Master line 20 'vs open+5') ----
    sht['AB15'].value = (cycles[_open5_idx]['net_gex']
                         if (_open5_idx is not None and idx >= _open5_idx) else None)

    # ---- VOL BOTTOM / VOL TOP flags -> AB13 / AB14 (Master F16 vol line reads them) ----
    sht['AB13'].value = c['volb_txt']
    sht['AB14'].value = c['volt_txt']

    # ---- move velocity: window of preceding spots, using archived timestamps ----
    win = cycles[max(0, idx - SPOT_HIST + 1): idx + 1]
    s_hist = [w['spot'] for w in win]
    s_dt   = [w['dt']   for w in win]
    vel, acc, vok = move_velocity(s_hist, s_dt, VEL_WINDOW)
    if vok and vel is not None:
        sht_gd['C68'].value = round(vel, 1)
        sht_gd['D68'].value = ('\u25b2 rising' if vel > 0.05 else
                               '\u25bc falling' if vel < -0.05 else '\u2013 flat')
        sht_gd['C69'].value = acc
    else:
        sht_gd['C68'].value = 'warming up'

    # ---- spot direction token -> King Node Model P13 --------------------------
    # Same rolling window and deadband as the velocity monitor above; the ladder's
    # wall-start suppression rule reads this cell. Flat inside the deadband so the
    # shading does not flicker strike to strike.
    try:
        if vok and vel is not None:
            sht['P13'].value = ('Up' if vel > SPOT_DIR_DB else
                                'Down' if vel < -SPOT_DIR_DB else 'Flat')
        else:
            sht['P13'].value = 'Flat'
    except Exception as e:
        print(f"   ! spot direction write failed ({e}); P13 left unchanged")
    sp = list(zip(s_dt, s_hist))[::-1]
    blk = []
    for j in range(SPOT_HIST):
        if j < len(sp):
            t, s = sp[j]
            d = round(s - sp[j + 1][1], 1) if j + 1 < len(sp) else None
            blk.append([t.strftime('%H:%M:%S'), round(s, 2), d])
        else:
            blk.append([None, None, None])
    sht_gd['B74'].value = blk

    # ---- ladder ----
    ladder = c['ladder']
    sht[f'A{FIRST_DATA_ROW}'].value = ladder
    if len(ladder) < MAX_LADDER:                       # blank stale rows from a wider earlier window
        r0 = FIRST_DATA_ROW + len(ladder)
        r1 = FIRST_DATA_ROW + MAX_LADDER - 1
        sht[f'A{r0}:I{r1}'].clear_contents()

    # ---- per-strike OPEN INTEREST -> King Node Model K/L (sync 2026-08-08) ----
    # Mirrors the live engine exactly. Written from the archive's own call_oi/put_oi
    # columns, so a replayed session reproduces the wall-composition panel the live
    # board showed on the day. Archives predating those columns yield blanks, which
    # the panel renders as empty rows rather than as stale structure.
    _oi = c.get('oi') or []
    if _oi:
        sht[f'K{FIRST_DATA_ROW}'].value = _oi
    if len(_oi) < MAX_LADDER:                          # blank stale rows from a wider earlier window
        _r0 = FIRST_DATA_ROW + len(_oi)
        _r1 = FIRST_DATA_ROW + MAX_LADDER - 1
        sht[f'K{_r0}:L{_r1}'].clear_contents()

    # ---- Level Engine DI:DL (dexFrac/dexSlope/dexPeak/brkRisk) intentionally NOT written.
    # live_king_node.py stopped writing these columns; replay writing them put values in
    # front of the sheet that live never produces. Removed to keep the two engines aligned.

    # ---- vomma peak monitor: window of near-spot |vomma| ----
    vwin   = cycles[max(0, idx - VOMMA_HIST + 1): idx + 1]
    vhist  = [w['near_vomma'] for w in vwin]
    vtimes = [w['dt'].strftime('%H:%M:%S') for w in vwin]
    vstat, vsig, vref, vpct = vomma_status(vhist, VOMMA_ROLL, VOMMA_RISE)
    sht_gd['C54'].value = vstat
    sht_gd['C55'].value = round(vref)
    sht_gd['E55'].value = round(vpct * 100, 1)
    rows = list(zip(vtimes, vhist))[::-1]
    vblk = []
    for j in range(VOMMA_HIST):
        if j < len(rows):
            t, v = rows[j]
            d = round(v - rows[j + 1][1]) if j + 1 < len(rows) else None
            vblk.append([t, round(v), d])
        else:
            vblk.append([None, None, None])
    sht_gd['B58'].value = vblk

    # ---- regime flags ----
    sht['A8:G8'].value = [c['flags']]
    if c.get('charm_flag'):
        sht['H8'].value = c['charm_flag']

    # ---- locked R/S levels (archived directly) ----

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
    for _s in (sht_le.range('AA9:AA55').value or []):
        if isinstance(_s, (int, float)):
            _k = float(_s)
            _st = _ft_state.setdefault(_k, {'in': False, 'done': False})
            if not _st['done']:
                if float(c['spot']) >= _k:
                    _st['in'] = True
                elif _st['in'] and float(c['spot']) <= _k - 10.0:
                    _st['done'] = True; _st['in'] = False
            _ei_col.append([0 if _st['done'] else 1])
        else:
            _ei_col.append([None])
    sht_le['EI9:EI55'].value = _ei_col
    # ---- locked R/S levels: RE-DERIVED from the workbook raw split (V) via live's
    #      own hysteresis + lock, NOT the archived r/s slots. Keeps replay side ==
    #      live side cycle-for-cycle; flip/edge rule unchanged. ------------------
    global _locked_R, _locked_S, _pend_R, _pend_S
    _spot_rs = float(c['spot'])
    # 2026-09-22: recalc BEFORE reading the raw split. Until now V9:V23 was read before
    # this cycle's first calculate(), so the lock was built from the PREVIOUS cycle's
    # sheet and replay's locked side trailed live by one cycle whenever a level flipped.
    # Live recalcs first; this makes replay do the same. Costs one calculate() per frame.
    _calc()
    _raw_R = _read_levels('V9:V14')
    _raw_S = _read_levels('V18:V23')
    _thr_rs = sht_le['BG9'].value
    _thr_rs = _thr_rs if isinstance(_thr_rs, (int, float)) else 5
    _strk_rs = sht_le.range('AA9:AA55').value or []
    # box flag comes from the ACTUAL box columns (FB=boxLo / FC=boxHi), never AN.
    # AN is revFlag; reading it here applied the +5 half-box to reversal-flagged levels
    # instead of boxed ones (2026-09-18 -- see the matching note in live).
    # 2026-09-23: cluster members (clReport GF=1) carry the whole cluster range in FB/FC,
    # not a two-strike box, so they get no allowance and flip at level +/- BG9. Matches live.
    _lo_rs = sht_le.range('FB9:FB55').value or []
    _hi_rs = sht_le.range('FC9:FC55').value or []
    try:
        _cl_rs = sht_le.range('GF9:GF55').value or []
    except Exception:
        _cl_rs = []
    _cl_rs = list(_cl_rs) + [None] * (len(_strk_rs) - len(_cl_rs))
    _boxf_rs = {float(s): (1 if (isinstance(lo, (int, float)) and isinstance(hi, (int, float))
                                 and hi > lo and cl != 1) else 0)
                for s, lo, hi, cl in zip(_strk_rs, _lo_rs, _hi_rs, _cl_rs)
                if isinstance(s, (int, float))}
    _qr_pos = (not c.get('gneg')) and _FRAG_HELD[idx] != 1
    _raw_R, _raw_S = apply_rs_hysteresis(_raw_R, _raw_S, _spot_rs, _thr_rs, _boxf_rs,
                                         now=c['dt'].timestamp(), pos=_qr_pos, qr=qr_settings(sht_le))   # quick reclaim (2026-10-05)
    # 2026-10-04: reversal-flagged strikes (Level Engine AN, last calc) get the re-adopt carry-over
    try:
        _rev_set = {round(_k) for _k, _a in zip(sht_le.range('AA9:AA55').value, sht_le.range('AN9:AN55').value)
                    if isinstance(_k, (int, float)) and _a in (1, 1.0, True)}
    except Exception:
        _rev_set = set()
    _locked_R, _pend_R = apply_lock(_locked_R, _pend_R, _raw_R, _spot_rs, 'R', _thr_rs, rev=_rev_set)
    _locked_S, _pend_S = apply_lock(_locked_S, _pend_S, _raw_S, _spot_rs, 'S', _thr_rs, rev=_rev_set)
    _locked_R, _locked_S, _pend_R, _pend_S = qr_apply(_locked_R, _locked_S, _pend_R, _pend_S)   # 2026-10-05 quick reclaim
    _locked_R = dedup_levels(_locked_R, _raw_R)
    _locked_S = dedup_levels(_locked_S, _raw_S)
    _locked_R, _locked_S = force_minvex_R(_locked_R, _locked_S, _spot_rs)   # Min VEX = resistance (neg VEX, High IV, above spot)
    _locked_R, _locked_S = force_minvex_S(_locked_R, _locked_S, _spot_rs)   # Min VEX = support while dealer vanna BUYS (fast IV)
    sht_le['W9:W14'].value  = [[(_locked_R[i] if i < len(_locked_R) else None)] for i in range(6)]
    sht_le['W18:W23'].value = [[(_locked_S[i] if i < len(_locked_S) else None)] for i in range(6)]


    # ---- roll+reclaim observation marker -> Level Engine!CT26 (Master support blue border) ----
    try:
        sht_le['CT26'].value = _OBS_FLAG[idx]
    except Exception:
        pass

    # ---- vanna override latch -> Level Engine JR ----
    if VLATCH_ENABLED:
        try:
            _vs = vlatch_series(_vl_num(sht_le['BG94'].value, 100000), _vl_num(sht_le['BG94'].value, 100000),
                                _vl_num(sht_le['BG9'].value, 3), _vl_num(sht_le['BG100'].value, 100000),
                                max(1, int(_vl_num(sht_le['BG101'].value, 2))),
                                near=_vl_num(sht_le['BG98'].value, 5), c5=sht_le['C5'].value,
                                cw_top=int(_vl_num(sht_le['BG102'].value, 1)),
                                cw_minc=_vl_num(sht_le['BG103'].value, 1000))
            vlatch_write(sht_le, set(_vs[idx]))
        except Exception as e:
            print(f"   ! vanna latch skipped ({e})")

    _write_drain(c)                              # DEX drain -> JT9:JT55 (UNSAFE DEXDRAIN)
    if GDV_ENABLED:
        _write_gdv(idx)                          # gDex-rule vanna UNSAFE latch -> KO9:KO55 (2026-10-05)
    _write_spd_hold(idx)                         # Spd★ 2-cycle hold history -> BG123:BG126 (2026-10-07)
    _write_vb(idx)                               # VEX-breakout take-profit latch -> LO9:LO55 (2026-10-07)
    if SAND_LOCK_ENABLED:                        # SAND✓ support lock -> MB9:MB55 (2026-10-08; sequential, rebuilt after a seek)
        global _sand_last_dt
        if _sand_last_dt is not None and c['dt'] < _sand_last_dt:
            _sand_lock.clear()                       # stepped / jumped backwards: rebuild from here
        _sand_last_dt = c['dt']
        try:
            _rows_s = [v for v in (sht['AL49:AL51'].value or [])]
        except Exception:
            _rows_s = []
        sand_lock_step(sht_le, c['spot'], bool(c.get('gneg')) or _FRAG_HELD[idx] == 1, c['dt'].date(), _rows_s)   # 2026-10-09: fragile = negative
    _write_oedge()
    _write_nvanna()                              # neg-gamma near-vanna zones -> DT9:DT55 (fat Vega + extreme Vex); vSharp -> ET9:ET55
    _write_cluster_admit()                       # cluster admission hysteresis -> HA9:HA55
    _write_gwall_hold()                          # gamma-wall hold -> IT9:IT55 (read by GY)
    _write_stack_hold()                          # chop-zone heavy-strike hold -> IO/IP9:IO/IP55
    # ---- numeric GEX slope -> Level Engine HC9 (gates read the NUMBER, never AB12's text)
    # 2026-09-18: the slope existed only inside the AB12 display string
    # ("GEX SLOPE  X -1.1M/15m ..."). A gate wanting "slope negative" had to parse that
    # sentence -- the display-text-as-input failure [14] exists for: reword the line and
    # the gate silently stops matching. The figure is already computed, so publish it as
    # a number. BLANK means the window is still building = UNKNOWN, never "negative".
    try:
        _p15 = c.get('gex_per15')
        sht_le['HC9'].value = (_p15 if isinstance(_p15, (int, float)) else None)
    except Exception as _e:
        print(f"   ! GEX slope publish failed ({_e}); HC9 blank -> slope-gated rules stay dark")
    try:
        sht_le['BG76'].value = _FRAG_HELD[idx]               # fragile pos-gamma hold (read by BG72)
    except Exception as _e:
        try:
            sht_le['BG76'].value = None
        except Exception:
            pass
        print(f"   ! fragile hold publish failed ({_e}); BG76 blank -> BG72 uses the raw test")

    _calc()
    _write_shape_hold()                          # edge/trough two-cycle hold -> HU/HV (shown by the next _calc)
    _write_peak_hold()    # DEX peak hold -> BG53 (read by BG28)
    _write_cliff_hold()   # dEdge collapse hold -> HZ (read by CZ)

    # ---- dEdge chop-box edges -> held resistance/support (KNM AB18/AB19) ----
    # In a DEX-peaks-in-the-middle chop, the reaction table (AL42/AL49) should point at
    # the DEX drop-off edges the engine flags via dEdge (Level Engine CZ), not the GEX
    # walls. The nearest dEdge each side is picked here; a BG9 (5-pt) hysteresis holds a
    # selected edge while price is testing it, so it doesn't flicker out on a touch, and
    # releases only on a clean break beyond BG9 or when dEdge relocates. State persists
    # across cycles in _dedge_res_hold / _dedge_sup_hold (parallels the live engine).
    _apply_dedge_hold(spot)
    _apply_chop_yield(spot)      # dEdge must not override a NEARER locked level (ported from live)

    # ---- vomma gate: a trigger only stands if price is at the matching vol level ----
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

    # ---- shelf / wall: read the raw CM/CN detection, damp it (live's SW_LOCK_HOLD), write
    #      the locked copy to CT/CW. Ported from live 2026-09-22. ----
    global _swR_lock, _swR_pend, _swS_lock, _swS_pend
    def _read_sw(d, e, fr, t):
        dv = sht_le[d].value; ev = sht_le[e].value
        frv = sht_le[fr].value; tv = sht_le[t].value
        if dv == 1 and isinstance(ev, (int, float)) and isinstance(frv, (int, float)):
            return (round(ev), round(frv), tv if isinstance(tv, str) else "")
        return None
    rR = _read_sw('CM2', 'CM3', 'CM4', 'CM9')
    rS = _read_sw('CN2', 'CN3', 'CN4', 'CN9')
    _swR_lock, _swR_pend = apply_sw_lock(_swR_lock, _swR_pend, rR)
    _swS_lock, _swS_pend = apply_sw_lock(_swS_lock, _swS_pend, rS)
    if _swR_lock:
        sht_le['CT3'].value, sht_le['CT4'].value, sht_le['CT9'].value = _swR_lock
    else:
        sht_le['CT3'].value = sht_le['CT4'].value = sht_le['CT9'].value = None
    if _swS_lock:
        sht_le['CW3'].value, sht_le['CW4'].value, sht_le['CW9'].value = _swS_lock
    else:
        sht_le['CW3'].value = sht_le['CW4'].value = sht_le['CW9'].value = None

    # ---- Flip resistance gate -> Level Engine EL7 (gateToDest) ----
    # In the updated workbook EL7 is a VALUE cell (live's Family B latch writes it) and the
    # raw gate formula moved to EL8 (gateRaw). Replay copies EL8 straight through each cycle.
    # Like the shelf/wall block above and the UNSAFE block below, live's wh-cycle hold is a
    # real-time-only smoother and isn't reproduced here; the per-cycle decision is identical.
    # Written BEFORE the calculate() below so the EM/CU/BT/A consumers of EL7 see it this
    # cycle. On an older replay workbook (no EL8; EL7 still a formula) EL8 reads None and
    # this is skipped entirely, leaving the in-cell formula to drive EL7 as before.
    # 2026-09-22: the wh-cycle hold IS reproduced now (ported from live's
    # apply_flip_gate_hysteresis). Copying the raw gate straight through made the gate,
    # and everything it controls, flicker in replay where live held steady.
    try:
        _fg_raw = sht_le['EL8'].value
        if _fg_raw is not None:
            _wh = sht_le['CT12'].value
            _wh = int(_wh) if isinstance(_wh, (int, float)) and _wh >= 1 else SW_LOCK_HOLD
            sht_le['EL7'].value = apply_flip_gate_hysteresis(_fg_raw == 1, _wh)
    except Exception:
        pass

    # ---- min-GEX node -> KNM T23 (locked cell in the updated workbook; raw in V23) ----
    # Same raw-per-cycle passthrough policy as EL7 above -- live's 3-cycle challenger
    # hold is a real-time-only smoother. On an older replay workbook (no V23 formula,
    # T23 still a formula) V23 reads None/empty and this is skipped.
    try:
        _mg_raw = sht['V23'].value
        if isinstance(_mg_raw, (int, float)):
            sht['T23'].value = round(_mg_raw)
    except Exception:
        pass

    _calc()

    # ---- nGex-wall box arm-and-hold latch -> Level Engine EQ1 (held node) ----
    # Runs after the recalc above because EO2 depends on the W18:W20 supports written
    # earlier this cycle. EO3/EO4 read EQ1 and fall back to the raw EO2, so a failure
    # here degrades to an instantaneous box rather than blanking it. On an older replay
    # workbook (no EO/EQ block) EO2 reads None, the latch stays unarmed and the write is
    # harmless.
    try:
        _box_raw = sht_le['EO2'].value
        _box_raw = round(float(_box_raw)) if isinstance(_box_raw, (int, float)) else None
        sht_le['EQ1'].value = apply_box_latch(_box_raw, spot, sht_le['BG9'].value)
    except Exception as e:
        print(f"   ! box latch failed ({e}); EQ1 left as-is, box falls back to raw EO2")

    # ---- PROX no-skip admission -> Level Engine EN9:EN55 ----
    # Reads the freshly recalced CU/BT of THIS cycle, writes EN, then the recalc below
    # lets Excel re-rank the reaction table on that write -- the same one-cycle-lag
    # construction live has, so the replayed table matches the day.
    _write_shelf_latch(sht_le)
    _write_grank(sht_le)
    _write_prox(spot, (bool(c['flags']) and str(c['flags'][0]).strip() == 'Neg') or _FRAG_HELD[idx] == 1, c['R'], ts=c['ts'])   # 2026-10-09: fragile = negative
    _write_qual_hold(spot)
    _write_vol_delta(c.get('vol_by_strike'))

    _calc()

    # ---- neg-gamma raspberry -> Level Engine CT19:CT24 (reads CJ, mirrors live) ----
    # 2026-09-17  Reads the CJ paint flag directly, exactly as live does. CJ already
    # encodes "unsafe AND not exempt", so the old _unsafe(text) + AX pin-gate pair is
    # dropped -- that combination did not match live's exemption and painted raspberry
    # on exempt levels live suppresses. No wh hysteresis hold here: that is a
    # real-time-only flicker smoother; the per-cycle CJ decision is what live paints.
    if sht_md is not None:
        for _i, _lc in enumerate(MD_NEGG_CELLS):
            _unsafe = str(sht_md[_lc].value or '0').strip() in ('1', '1.0')
            sht_le['CT' + str(19 + _i)].value = 1 if _unsafe else 0

    sht['K26'].value = 'REPLAY ' + c['ts'][11:]


# ============ status line ============
def status(idx, speed_idx, paused, end=False):
    c = cycles[idx]
    state = 'END  (paused)' if end else ('PAUSED ' if paused else 'PLAYING')
    mark = ''
    if c.get('event') == 'RECONNECT':
        g = c.get('gap_secs')
        mark = (f"   \u27f2 RECONNECT (gap {int(g)//60}m {int(g)%60:02d}s)"
                if g and g > 0 else "   \u27f2 RECONNECT")
    sys.stdout.write(
        f"\r  cycle {idx+1:>4}/{N}   {c['ts'][11:]}   spot {c['spot']:>8.2f}"
        f"   {SPEEDS[speed_idx]:>5}x   [{state}]{mark}      ")
    sys.stdout.flush()


def _seek_minutes(cycles, idx, minutes):
    """Index of the cycle nearest to cycles[idx] +/- `minutes` of SESSION time.

       Time-based, not count-based: cycle spacing varies (~30-35s normally, but far
       wider across a feed gap or reconnect), so 'jump 20 cycles' moves a different
       amount of clock time every time you press it. This always moves what it says.

       V2: the old version scanned all N cycles on every press. Same answer, found by
       bisect against the precomputed timestamp index, so a jump is instant."""
    if not cycles:
        return idx
    target = cycles[idx]['dt'] + datetime.timedelta(minutes=minutes)
    best = _nearest_dt(target)
    if best == idx:                                   # target fell outside the session
        best = (len(cycles) - 1) if minutes > 0 else 0
    return best


def _nearest_dt(target):
    """Index of the cycle whose timestamp is closest to `target` (O(log N))."""
    j = bisect.bisect_left(_CYCLE_DT, target)
    if j <= 0:
        return 0
    if j >= N:
        return N - 1
    lo, hi = _CYCLE_DT[j - 1], _CYCLE_DT[j]
    return j if (hi - target) <= (target - lo) else j - 1


def parse_time_string(txt):
    """'11:35' / '11:35:30' / '1135' -> nearest cycle index, or None."""
    t = str(txt).strip().replace(".", ":")
    if t.isdigit() and len(t) in (3, 4):
        t = t[:-2] + ":" + t[-2:]
    bits = t.split(":")
    try:
        h = int(bits[0]); m = int(bits[1]) if len(bits) > 1 else 0
        sec = int(bits[2]) if len(bits) > 2 else 0
    except (ValueError, IndexError):
        return None
    if not (0 <= h < 24 and 0 <= m < 60 and 0 <= sec < 60):
        return None
    base = _CYCLE_DT[0]
    return _nearest_dt(base.replace(hour=h, minute=m, second=sec, microsecond=0))


def banner(path):
    print("\n" + "=" * 64)
    print("  KING NODE  —  SESSION REPLAY")
    print("  " + os.path.basename(path) + f"   ({N} cycles)")
    print("  driving: " + os.path.basename(WORKBOOK))
    print("=" * 64)
    print("  SPACE pause/resume   f/-> faster   s/<- slower")
    print("  n step fwd   b step back   r restart   q quit")
    print(f"  j / k   jump +/- {JUMP_MIN} min       J / K  (or ] / [)  jump +/- {JUMP_HOUR_MIN // 60} hour")
    print("  (jumps move SESSION TIME, not cycle counts)")
    if not _HAVE_KB:
        print("  (live keys unavailable on this OS - autoplaying at 1x)")
    print("=" * 64 + "\n")


# ============================================================================
#  V2 TRANSPORT  —  background render engine + TradingView-style controller
# ============================================================================
#
#  WHAT CHANGED AND WHY IT IS SAFE
#  --------------------------------
#  render_cycle() itself is untouched apart from the three wb.app.calculate() calls
#  becoming _calc() (the same call, timed). No trading calculation, no write order and
#  no written value differs from V1. What changed is WHO calls it and WHEN:
#
#    * a dedicated worker thread owns Excel; the Tk UI thread never touches COM, so a
#      key press or a slider drag is acknowledged immediately instead of waiting for a
#      frame to finish writing.
#    * requests COALESCE. Ten queued arrow presses collapse to one render of the newest
#      target, which is what makes held-arrow seeking scroll smoothly instead of
#      step-wait-step.
#    * screen updating is suppressed only while the engine is BEHIND (scrubbing, held
#      arrow, catching up) and restored the moment it settles, so you still watch the
#      dashboard update live during ordinary playback.
#    * the two O(N) per-frame Python rescans (GEX slope line, observe marker) are now
#      precomputed once — identical values, computed N times instead of N^2.
#
#  ONE DELIBERATE OMISSION — read this
#  -----------------------------------
#  The brief asked for every frame to be precomputed into RAM and merely "displayed".
#  That is not possible for this engine without changing replay output: render_cycle()
#  writes, recalcs, READS the recalculated sheet back, and writes again — the shelf/wall
#  passthrough, EL7, T23, the box latch, PROX and the UNSAFE borders are all decided from
#  values only Excel can produce, after that frame's own writes. A frame's content does
#  not exist until Excel has computed it, so there is nothing to cache. Excel recalc is
#  therefore the floor on frame time; everything above it has been removed.
#
#  Likewise, frame SKIPPING is off during playback by default. render_cycle() resets the
#  box and PROX latches on any non-sequential move, so skipping cycles while playing
#  would silently change what the dashboard shows. Skipping is used only for scrubbing
#  and held-arrow seeking, where those latches are reset anyway. SKIP_WHEN_LAGGING = True
#  enables it during playback too, at that cost.
# ============================================================================

SKIP_WHEN_LAGGING = False   # see note above — True changes what playback displays
UI_REFRESH_MS     = 25      # UI poll interval (never blocks on Excel)


RENDER_FAIL_PAUSE = 3        # 2026-09-30: consecutive failed frames before playback pauses


class ReplayEngine(threading.Thread):
    """Owns Excel. Renders whatever the UI most recently asked for."""

    daemon = True

    def __init__(self):
        super().__init__(name="replay-engine")
        self.lock       = threading.Lock()
        self.wake       = threading.Event()
        self.target     = 0          # what the UI wants on screen
        self.current    = None       # what is actually on screen
        self.playing    = False
        self.speed_idx  = START_SPEED_IDX
        self.req_stamp  = None       # perf_counter of the input that set `target`
        self._stop_flag      = False
        self._quiet     = False
        self._due       = 0.0
        self.ready      = threading.Event()

    # ---------- UI-side API (never blocks) ----------
    def seek(self, i, stamp=None):
        i = max(0, min(N - 1, int(i)))
        with self.lock:
            if i == self.target:
                return
            self.target = i
            self.req_stamp = stamp if stamp is not None else time.perf_counter()
            self._due = 0.0
        self.wake.set()

    def step(self, d, stamp=None):
        with self.lock:
            i = self.target + d
        self.seek(i, stamp)

    def set_playing(self, on):
        with self.lock:
            self.playing = bool(on)
            self._due = time.perf_counter()
        self.wake.set()

    def set_speed(self, k):
        with self.lock:
            self.speed_idx = max(0, min(len(SPEEDS) - 1, int(k)))
            self._due = time.perf_counter()
        self.wake.set()

    def snapshot(self):
        with self.lock:
            return self.target, self.current, self.playing, self.speed_idx

    def shutdown(self):
        self._stop_flag = True
        self.wake.set()

    # ---------- Excel ownership ----------
    def _bind(self):
        """Re-attach the workbook on THIS thread. xlwings COM objects are apartment
           bound; using the main thread's objects here would marshal every call."""
        global wb, sht, sht_le, sht_gd, sht_md
        try:
            import pythoncom
            pythoncom.CoInitialize()
            app = xw.apps[_app_pid]
            b   = app.books[_wbname]
            wb, sht, sht_le = b, b.sheets[SHEET], b.sheets[LE_SHEET]
            sht_gd = b.sheets[GD_SHEET]
            try:
                sht_md = b.sheets["Master Dashboard"]
            except Exception:
                sht_md = None
        except Exception as e:
            print(f"\n  ! engine thread kept the main-thread Excel handles ({e})")
        try:
            wb.app.display_alerts = False
            wb.app.enable_events  = False
        except Exception:
            pass

    def _screen(self, on):
        if self._quiet == (not on):
            return
        try:
            wb.app.screen_updating = on
        except Exception:
            pass
        self._quiet = not on

    def _reconnect(self):
        """2026-09-30: re-attach after the workbook handle goes dead mid-session (a save,
           save-as, close/reopen, or another workbook opened in the same Excel). Finds the
           workbook in any running Excel if the original instance is gone, then rebinds."""
        global _app_pid
        try:
            xw.apps[_app_pid].books[_wbname]
        except Exception:
            for _a in xw.apps:
                try:
                    _a.books[_wbname]
                    _app_pid = _a.pid
                    break
                except Exception:
                    continue
        self._bind()

    def _render_guarded(self, i):
        """Render one frame. On failure: print the error, reconnect, restore screen
           updating and retry once; if the retry fails too, skip the frame. After
           RENDER_FAIL_PAUSE failed frames in a row, playback pauses instead of spinning."""
        try:
            render_cycle(i)
            self._fails = 0
            return
        except Exception as e:
            import traceback
            _ts = cycles[i]['ts'][11:] if 0 <= i < N else '?'
            print(f"\n  ! frame {i + 1} ({_ts}) failed: {type(e).__name__}: {e}")
            traceback.print_exc()
        self._reconnect()
        try:
            wb.app.screen_updating = True
        except Exception:
            pass
        self._quiet = False
        try:
            render_cycle(i)
            self._fails = 0
            print("  \u2713 reconnected to the workbook; frame redrawn")
        except Exception as e2:
            self._fails = getattr(self, "_fails", 0) + 1
            print(f"  ! retry failed ({type(e2).__name__}: {e2}); frame skipped")
            if self._fails >= RENDER_FAIL_PAUSE:
                with self.lock:
                    self.playing = False
                print(f"  ! {self._fails} frames failed in a row -- playback PAUSED. "
                      f"Check Excel (cell edit mode, open dialog, workbook closed), then press SPACE.")

    def _render(self, i):
        t0 = time.perf_counter()
        c0 = _PERF["calc_s"]
        self._render_guarded(i)
        dt = time.perf_counter() - t0
        _PERF["frames"] += 1
        _PERF["frame_s"] += dt
        _PERF["excel_s"] += dt - (_PERF["calc_s"] - c0)
        if dt > _PERF["frame_max"]:
            _PERF["frame_max"] = dt
        with self.lock:
            self.current = i
            st = self.req_stamp
            self.req_stamp = None
        if st is not None:
            lat = time.perf_counter() - st
            _PERF["keys"] += 1
            _PERF["key_s"] += lat
            if lat > _PERF["key_max"]:
                _PERF["key_max"] = lat

    # ---------- main loop ----------
    def run(self):
        self._bind()
        self._render(0)
        with self.lock:
            self.target = 0
        self.ready.set()

        while not self._stop_flag:
            with self.lock:
                tgt, cur, playing, sp = self.target, self.current, self.playing, self.speed_idx
                due = self._due

            if tgt != cur:
                # A single sequential step (ordinary playback, one arrow press) is drawn
                # normally -- you are meant to WATCH it. Only a burst (scrub, held arrow,
                # jump, catch-up) goes quiet, so the intermediate frames don't flicker
                # past; screen updating is restored the instant it settles.
                self._screen(cur is not None and abs(tgt - cur) == 1)
                self._render(tgt)
                with self.lock:
                    self._due = time.perf_counter() + BASE_DELAY / SPEEDS[self.speed_idx]
                continue

            # caught up -> let Excel paint the settled frame
            self._screen(True)

            if playing:
                if cur is not None and cur >= N - 1:
                    with self.lock:
                        self.playing = False
                    continue
                now = time.perf_counter()
                if now >= due:
                    nxt = cur + 1
                    if SKIP_WHEN_LAGGING:
                        behind = int((now - due) / max(BASE_DELAY / SPEEDS[sp], 1e-6))
                        nxt = min(N - 1, nxt + max(0, behind))
                    with self.lock:
                        self.target = nxt
                        self._due = now + BASE_DELAY / SPEEDS[sp]
                    continue
                self.wake.wait(min(due - now, 0.05))
                self.wake.clear()
            else:
                self.wake.wait(0.25)
                self.wake.clear()

        try:
            self._screen(True)
            wb.app.enable_events = True
        except Exception:
            pass


# ============ transport window (scrubbable replay controller) ============
import tkinter as tk
from tkinter import ttk


class Transport:
    """TradingView-style controller. Sends intents to the engine and polls it for
       display; it never calls into Excel, so nothing here can ever block on a recalc."""

    def __init__(self, master, engine):
        self.eng        = engine
        self.master     = master
        self.idx        = 0
        self._scrubbing = False
        self._was_playing = False
        self.bookmarks  = []
        self._held      = None
        self._held_job  = None

        master.title("King Node — Session Replay")
        master.attributes('-topmost', True)
        master.resizable(True, False)
        f = ttk.Frame(master, padding=8)
        f.grid(sticky='ew')
        f.columnconfigure(0, weight=1)
        self.f = f

        # --- readout -------------------------------------------------
        self.lbl = ttk.Label(f, font=('Consolas', 10), anchor='w')
        self.lbl.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 4))

        # --- timeline ------------------------------------------------
        self.var = tk.DoubleVar(value=0)
        self.scale = ttk.Scale(f, from_=0, to=max(N - 1, 1), orient='horizontal',
                               variable=self.var, command=self._on_drag)
        self.scale.grid(row=1, column=0, columnspan=2, sticky='ew')
        self.scale.bind('<ButtonPress-1>',   self._grab)
        self.scale.bind('<ButtonRelease-1>', self._release)

        # --- transport buttons ---------------------------------------
        b = ttk.Frame(f); b.grid(row=2, column=0, sticky='w', pady=(6, 0))
        def btn(txt, cmd, w=4):
            x = ttk.Button(b, text=txt, width=w, command=cmd)
            x.pack(side='left', padx=1)
            return x
        btn('|<',  lambda: self.seek(0))
        btn('<<h', lambda: self.jump(-JUMP_HOUR_MIN), 5)
        btn('<<',  lambda: self.jump(-JUMP_MIN))
        btn('<',   lambda: self.step(-1), 3)
        self.play_btn = btn('\u25b6', self.toggle, 5)
        btn('>',   lambda: self.step(+1), 3)
        btn('>>',  lambda: self.jump(JUMP_MIN))
        btn('h>>', lambda: self.jump(JUMP_HOUR_MIN), 5)
        btn('>|',  lambda: self.seek(N - 1))

        # --- speed ---------------------------------------------------
        sp = ttk.Frame(f); sp.grid(row=2, column=1, sticky='e', pady=(6, 0))
        ttk.Label(sp, text='speed').pack(side='left', padx=(0, 4))
        self.speed_box = ttk.Combobox(sp, width=6, state='readonly',
                                      values=[f'{v}x' for v in SPEEDS])
        self.speed_box.current(START_SPEED_IDX)
        self.speed_box.bind('<<ComboboxSelected>>', self._on_speed)
        self.speed_box.pack(side='left')

        # --- random access row ---------------------------------------
        g = ttk.Frame(f); g.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        ttk.Label(g, text='cycle').pack(side='left')
        self.cyc_e = ttk.Entry(g, width=7); self.cyc_e.pack(side='left', padx=(3, 2))
        self.cyc_e.bind('<Return>', lambda e: self._go_cycle())
        ttk.Button(g, text='go', width=3, command=self._go_cycle).pack(side='left')

        ttk.Label(g, text='  time').pack(side='left')
        self.tim_e = ttk.Entry(g, width=9); self.tim_e.pack(side='left', padx=(3, 2))
        self.tim_e.bind('<Return>', lambda e: self._go_time())
        ttk.Button(g, text='go', width=3, command=self._go_time).pack(side='left')

        ttk.Label(g, text='  marker').pack(side='left')
        self.mk_box = ttk.Combobox(g, width=22, state='readonly',
                                   values=[f"{cycles[i]['ts'][11:]}  {ev}"
                                           for i, ev in _EVENTS] or ['(none)'])
        self.mk_box.pack(side='left', padx=(3, 0))
        self.mk_box.bind('<<ComboboxSelected>>', self._go_marker)

        # --- bookmarks -----------------------------------------------
        k = ttk.Frame(f); k.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        ttk.Button(k, text='\u2691 bookmark  (B)', command=self.bookmark).pack(side='left')
        ttk.Button(k, text='next \u2691  (Shift+B)', command=lambda: self.next_bm(1)).pack(side='left', padx=3)
        ttk.Button(k, text='prev \u2691', command=lambda: self.next_bm(-1)).pack(side='left')
        ttk.Button(k, text='clear', command=self.clear_bm).pack(side='left', padx=3)
        ttk.Button(k, text='perf report', command=lambda: print(perf_report())).pack(side='right')
        self.bm_lbl = ttk.Label(k, text='', font=('Consolas', 8))
        self.bm_lbl.pack(side='right', padx=6)

        # --- keyboard -------------------------------------------------
        m = master
        m.bind('<space>',  lambda e: self.toggle())
        m.bind('<Up>',     lambda e: self._bump(+1))
        m.bind('<Down>',   lambda e: self._bump(-1))
        m.bind('<Prior>',  lambda e: self.jump(JUMP_MIN))
        m.bind('<Next>',   lambda e: self.jump(-JUMP_MIN))
        m.bind('<Home>',   lambda e: self.seek(0))
        m.bind('<End>',    lambda e: self.seek(N - 1))
        m.bind('<KeyPress-Right>',   lambda e: self._hold_start(+1))
        m.bind('<KeyRelease-Right>', lambda e: self._hold_stop())
        m.bind('<KeyPress-Left>',    lambda e: self._hold_start(-1))
        m.bind('<KeyRelease-Left>',  lambda e: self._hold_stop())
        m.bind('<KeyPress-b>', lambda e: self.bookmark())
        m.bind('<KeyPress-B>', lambda e: self.next_bm(1))
        m.bind('<KeyPress-n>', lambda e: self.step(+1))
        m.bind('<KeyPress-r>', lambda e: self.seek(0))

        self.refresh()
        master.after(UI_REFRESH_MS, self.pump)

    # ---------- intents ----------
    def seek(self, i):
        t = time.perf_counter()
        self.idx = max(0, min(N - 1, int(i)))
        self.eng.seek(self.idx, t)
        self.refresh()

    def step(self, d):
        self.seek(self.idx + d)

    def jump(self, minutes):
        self.seek(_seek_minutes(cycles, self.idx, minutes))

    def toggle(self):
        _, cur, playing, _ = self.eng.snapshot()
        if not playing and self.idx >= N - 1:
            self.seek(0)
        self.eng.set_playing(not playing)
        self.refresh()

    def _bump(self, d):
        i = max(0, min(len(SPEEDS) - 1, self.speed_box.current() + d))
        self.speed_box.current(i)
        self.eng.set_speed(i)

    def _on_speed(self, _e):
        self.eng.set_speed(self.speed_box.current())

    # ---------- held-arrow continuous seek ----------
    def _hold_start(self, d):
        if self._held == d:
            return
        self._held = d
        self._held_repeat()

    def _held_repeat(self):
        if self._held is None:
            return
        self.step(self._held)
        self._held_job = self.master.after(40, self._held_repeat)

    def _hold_stop(self):
        self._held = None
        if self._held_job:
            self.master.after_cancel(self._held_job)
            self._held_job = None

    # ---------- random access ----------
    def _go_cycle(self):
        try:
            self.seek(int(self.cyc_e.get().strip()) - 1)
        except ValueError:
            pass
        self.master.focus_set()

    def _go_time(self):
        i = parse_time_string(self.tim_e.get())
        if i is not None:
            self.seek(i)
        self.master.focus_set()

    def _go_marker(self, _e):
        j = self.mk_box.current()
        if 0 <= j < len(_EVENTS):
            self.seek(_EVENTS[j][0])
        self.master.focus_set()

    # ---------- bookmarks ----------
    def bookmark(self):
        if self.idx not in self.bookmarks:
            self.bookmarks.append(self.idx)
            self.bookmarks.sort()
        self.refresh()

    def clear_bm(self):
        self.bookmarks = []
        self.refresh()

    def next_bm(self, d):
        if not self.bookmarks:
            return
        if d > 0:
            nxt = next((b for b in self.bookmarks if b > self.idx), self.bookmarks[0])
        else:
            nxt = next((b for b in reversed(self.bookmarks) if b < self.idx), self.bookmarks[-1])
        self.seek(nxt)

    # ---------- scrubbing ----------
    def _grab(self, _e):
        self._scrubbing = True
        _, _, playing, _ = self.eng.snapshot()
        self._was_playing = playing
        self.eng.set_playing(False)

    def _release(self, _e):
        self._scrubbing = False
        self.seek(round(self.var.get()))
        if self._was_playing:
            self.eng.set_playing(True)

    def _on_drag(self, _v):
        if self._scrubbing:
            i = round(self.var.get())
            if i != self.idx:
                self.idx = i
                self.eng.seek(i, time.perf_counter())
                self.refresh(sync_scale=False)

    # ---------- display ----------
    def refresh(self, sync_scale=True):
        c = cycles[self.idx]
        if sync_scale and not self._scrubbing:
            self.var.set(self.idx)
        _, cur, playing, spi = self.eng.snapshot()
        self.play_btn.config(text='\u2016' if playing else '\u25b6')
        mark = ''
        ev = c.get('event')
        if ev == 'RECONNECT':
            g = c.get('gap_secs')
            mark = (f"  \u27f2 RECONNECT (gap {int(g)//60}m {int(g)%60:02d}s)"
                    if g and g > 0 else "  \u27f2 RECONNECT")
        elif ev:
            mark = f"  \u25c6 {ev}"
        state = 'END' if (self.idx >= N - 1 and not playing) else \
                ('PLAYING' if playing else 'PAUSED')
        lag = '' if cur == self.idx else '  \u2026'
        pct = (self.idx / max(N - 1, 1)) * 100.0
        bm = ' \u2691' if self.idx in self.bookmarks else ''
        self.lbl.config(
            text=f"{c['ts'][11:]}   spot {c['spot']:>8.2f}   "
                 f"cycle {self.idx+1}/{N}   {pct:5.1f}%   "
                 f"{SPEEDS[spi]}x   [{state}]{bm}{mark}{lag}")
        self.bm_lbl.config(text=f"{len(self.bookmarks)} bookmark(s)")

    def pump(self):
        """UI heartbeat. Follows the engine while it is auto-advancing, and keeps the
           readout honest while it catches up. Never touches Excel."""
        if not self._scrubbing:
            tgt, cur, playing, _ = self.eng.snapshot()
            if playing and tgt != self.idx:
                self.idx = tgt
            self.refresh()
        self.master.after(UI_REFRESH_MS, self.pump)


print("\n" + "=" * 64)
print("  KING NODE  —  SESSION REPLAY   (transport V2)")
print("  " + os.path.basename(_archive_path) + f"   ({N} cycles)")
print("  driving: " + os.path.basename(WORKBOOK))
print("  SPACE play/pause   \u2190/\u2192 hold to scrub   \u2191/\u2193 speed")
print("  B bookmark   Shift+B next bookmark   Home/End   PgUp/PgDn \u00b1%d min"
      % JUMP_MIN)
print("  transport window opened — close it to stop.")
print("=" * 64 + "\n")

_app_pid = None
try:
    _app_pid = wb.app.pid
except Exception:
    pass

_engine = ReplayEngine()
_engine.start()
_engine.ready.wait(120)

_root = tk.Tk()
Transport(_root, _engine)
try:
    _root.mainloop()
except KeyboardInterrupt:
    pass
finally:
    _engine.shutdown()
    _engine.join(timeout=10)
    print(perf_report())
    print("Replay stopped.")
