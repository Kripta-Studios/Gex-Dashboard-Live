# live_king_node.py  —  V5 layout, dealer exposures (GEX / DEX / VEX, dollar-scaled)
#   A Strike | B Gamma(gross) | C GEX | D Zomma | E Dex | F Vex | G Vomma | H Vega | I Speed
# Smoothing (rolling average) + level lock (hysteresis) keep the display stable.
# Ctrl+C to stop. Reads data only; never trades.

import os
import re
import csv
import math
import datetime
import time
from collections import deque
import xlwings as xw
from ib_async import IB, Index, Option, ContFuture
import sys as _sys

# ---- console logging (tee) -------------------------------------------------
# Every line printed to the console is ALSO appended to a dated file in a "logs"
# folder next to this script, so a closed console window no longer loses the
# record. Added 2026-09-17 after a day archived nothing and the console -- the
# only place the "! archive write failed" / "! reconnect" lines ever appeared --
# had been closed before it could be read. The log rolls by date; delete old
# ones whenever. This changes nothing about how the engine runs; it only copies
# what you already see on screen to disk.
class _Tee:
    def __init__(self, *streams):
        self._streams = streams
    def write(self, data):
        for _st in self._streams:
            try:
                _st.write(data); _st.flush()
            except Exception:
                pass
    def flush(self):
        for _st in self._streams:
            try:
                _st.flush()
            except Exception:
                pass

try:
    _LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(_LOG_DIR, exist_ok=True)
    _LOG_PATH = os.path.join(_LOG_DIR,
                             f"live_king_node_{datetime.date.today():%Y-%m-%d}.log")
    _log_fh = open(_LOG_PATH, "a", encoding="utf-8", buffering=1)   # line-buffered
    _log_fh.write(f"\n===== session start {datetime.datetime.now():%Y-%m-%d %H:%M:%S} "
                  f"=====\n")
    _sys.stdout = _Tee(_sys.__stdout__, _log_fh)
    _sys.stderr = _Tee(_sys.__stderr__, _log_fh)
    print(f"console logging to {_LOG_PATH}")
except Exception as _e:
    # Logging must never stop the engine. If the folder can't be made, run as before.
    print(f"   ! could not start console log ({_e}); running without a log file")
# ---------------------------------------------------------------------------

# ---- settings ----
PORT     = 4001
WORKBOOK = r"C:\AMD\Aimee\Trading\Indicators\IBRK King Node Data\MASTER_KING_NODE_RECORD_V5.xlsx"
SHEET    = "King Node Model"
LE_SHEET = "Level Engine"

REFRESH  = 30
SMOOTH_N = 3             # readings to average before writing (3 x 30s = 90s smoothing window)
LOCK_HOLD = 3            # a challenger must beat a locked level this many cycles in a row to replace it
LOCK_RELEASE = 3         # a locked level must be ABSENT from the raw top-6 this many cycles in a row before eviction (2026-07-30 latch fix)
PROX_MIN_GAP = 10        # no-skip admission: gap (pts) to the displayed structural resistance required for ENTRY
PROX_MISS_HOLD = 3       # no-skip admission: consecutive failing cycles tolerated before the PROX flag releases
                         #   higher = stickier levels; lower = quicker to change
STRIKES_EACH_SIDE = 23
INDEX_TYPE  = 2          # 2 = frozen: live during market hours, last value after close (keep at 2)
OPTION_TYPE = 1          # 1 = live (OPRA active); 3 = delayed; 4 = delayed-frozen (weekend testing)
RATE = 0.043
DIV  = 0.012
SCALE = 0.001
VEGA_PER  = 0.01
FIRST_DATA_ROW = 29
MAX_LADDER_ROWS = 47      # A29:A75 -- the full ladder block the workbook formulas span

GEX_SIGN = 1
DEX_SIGN = 1
VEX_SIGN = 1
# ---- vex sign convention: DEALER-signed ---------------------------------------------
# vex = vanna * (callOI - putOI) * M * spot -- the same coi-poi weighting as GEX, and the
# workbook already reads positive GEX as dealer-long (the dampening regime). Read the same
# way, positive vex = dealers LONG vanna = dealer delta RISES as IV rises = dealers SELL
# on a vol spike. The workbook's vexAct / confluence pairing is written in this sign:
#     IV Up   : support point if vex < 0 ; resistance point if vex > 0
#     IV Down : support point if vex > 0 ; resistance point if vex < 0
# That IS Giggles's flow-side phrasing ("VIX rising + positive VEX -> supportive") once
# translated -- flow-positive vanna is dealer-NEGATIVE here. This bit twice (2026-07 notes,
# 2026-09-18 spec) by reading the column flow-side. Do not flip VEX_SIGN or vexAct to
# "match" a flow-side table; translate the table instead. Archive run 2026-09-18 (392
# episodes) was inconclusive either way, so the mechanics stand.
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
SPOT_DIR_DB = 0.05       # pts/min deadband for the P13 spot-direction token
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
    #   vex is DEALER-signed (see VEX_SIGN note): positive = dealers sell on a vol spike.
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
    # ---- pin state, cycle-level (added 2026-07-26) ----
    # pin_state : King Node Model AC24 -- the shared pinState boolean, archived as 1/0.
    # AC24 = AND(gamma regime <> "Neg", NOT Choppy(S38), GEX at the max-gamma strike > 0).
    # Added because the Choppy term is not otherwise logged, so whether the pin armed
    # could not be reconstructed offline -- on 2026-07-24 two cycles (17:11:41, 17:12:16)
    # met the two archivable conditions and could not be resolved either way. Logging the
    # evaluated flag also lets Choppy be recovered by elimination.
    # Repeated on every strike row like the other cycle-level fields, and sits
    # immediately before "event" so every pre-existing column keeps its index.
    "pin_state",
    # ---- break-suppression flag, per strike (added 2026-07-27) ----
    # ej_brksupp : Level Engine EJ9:EJ55 (header "brkSupp") 0/1 -- the per-strike
    # break-suppression veto. Read back from the computed Level Engine alongside the
    # other CU/CV/BK/DH/DC/CZ qualification internals.
    # Added because EJ is a hard gate on the Master Dashboard reaction markers -- both
    # the late-session chop-reversal marker (rev) and the neg-gamma accelerant
    # marker (75%) require EJ=0 to display -- and it was not logged anywhere. Without
    # it, a backtest cannot tell an archived cycle that met every reconstructable
    # Pocket condition from one that actually plotted the marker, so any hold-rate
    # measured offline is computed on a superset of true firings.
    # Per strike, so it travels in qual_by_strike with cu_qual/cv_qual/bk/dh/dc/cz.
    # Sits immediately before "event" so every pre-existing column keeps its index
    # and replay/seed code that reads by position still works.
    "ej_brksupp",
    # ---- reaction-table SELECTION layer, per strike (added 2026-07-27) ----
    # Everything archived before this point describes whether a level QUALIFIED.
    # Nothing described whether it was SELECTED for display, which is a separate
    # downstream layer -- so "level X qualified but never appeared" was not
    # answerable offline. These five close that gap.
    #   at_boxlo     : AT9 -- box lower bound. Spot-quantised (CEILING/FLOOR($B$4,5)),
    #                  so it moves with spot even when the strike is static.
    #   au_boxhi     : AU9 -- box upper bound. at/au together drive the AL50
    #                  box-overlap dedupe that silently merges two reaction rows.
    #   dm_supgate   : DM9 -- support hold/break-suppression gate. Hard precondition
    #                  on dn_supslot: DM=0 => DN blank => the level is not in the
    #                  reaction table at all, regardless of cu/cv/absorption.
    #   dn_supslot   : DN9 -- support reaction slot. NOT a strength rank: it is a
    #                  PROXIMITY rank, SUMPRODUCT(eligible * below-spot *
    #                  nearer-than-me)+1. Only slots 1 and 2 render (KNM AL51, the
    #                  third row, is hard-disabled via IF(TRUE(),"")), so a level at
    #                  slot 3+ is structurally invisible however strong it is.
    #   ef_supexempt : EF9 -- max-positive-GEX support exemption; one of the OR
    #                  branches that grants DN eligibility.
    # NOTE ON LABELS: Level Engine DM8/DN8 read "brkRankS"/"brkRankR", but BOTH
    # columns are support-side -- DN9 tests $AA9<$B$4 and reads the support locked
    # slots W18:W20. The "R" on DN8 is a stale label, not a wrong calculation
    # (same class as the AB8 gamma/GEX mislabel). Named here by what they compute.
    # Sit immediately before "event" so every pre-existing column keeps its index.
    "at_boxlo", "au_boxhi", "dm_supgate", "dn_supslot", "ef_supexempt",
    # ---- selection-layer completion (added 2026-07-27, second pass) ----
    # The five columns above showed WHICH gate dropped a level; these four show WHY,
    # and extend the same visibility to the resistance side.
    #   al_zommark   : AL9 (header "zomMark") 0/1 -- IF(ABS(zomma)>=KNM!$S$10,1,0).
    #                  For a neg-gamma support with negative GEX whose fat-tail and
    #                  near-node terms are both false, this is the SOLE remaining
    #                  OR-branch in dm_supgate, i.e. the only thing deciding whether
    #                  a fully-qualified support reaches Master Dashboard rows 43/44.
    #                  Logged evaluated rather than inferred: |zomma| alone cannot be
    #                  compared offline because the threshold moves (see below).
    #   s10_zomthr   : KNM S10 = Level Engine A15 -- the zomMark threshold itself.
    #                  Cycle-level, repeated on every strike row. Without it the
    #                  archived |zomma| is uninterpretable: on 2026-07-27 no single
    #                  static S10 could reproduce both the 18:48:02 and 19:42:22
    #                  displays, which is what made that pair undiagnosable.
    #                  NOTE: zomma_ex ~= -gex/sigma is a deterministic function of GEX
    #                  and IV (validated), so zomMark is effectively a GEX/IV gate.
    #   bt_resslot   : BT9 -- resistance reaction slot; the twin of dn_supslot.
    #                  Same proximity-rank construction, gated on CU9=1 / AG9="R" /
    #                  AA9>=spot and the W9:W11 resistance locked slots.
    #   ee_resexempt : EE9 -- resistance max-positive-GEX exemption; the twin of
    #                  ef_supexempt and one of BT9's OR branches. Added because BT
    #                  is not diagnosable without it.
    # Sit immediately before "event" so every pre-existing column keeps its index.
    "al_zommark", "s10_zomthr", "bt_resslot", "ee_resexempt",
    # ---- PROX no-skip admission flag, per strike (added 2026-07-30) ----
    # en_prox : Level Engine EN9:EN55 (header "enProx") 0/1 -- the proximity-only
    # admission written by the engine, not by a sheet formula. 1 on at most ONE
    # strike per cycle: the nearest locked-list resistance that clears both
    # strength floors and is not absorbed, admitted to the reaction table on
    # proximity alone because the structural gate skipped past it by
    # >= PROX_MIN_GAP pts (neg gamma only -- the measured regime). BT9 accepts
    # EN=1 rows; the KNM Source/Type cells and the ladder label render the
    # PROX tag off this flag. Archived so every admission (and every touch that
    # follows one) is auditable offline. Sits immediately before "event" so
    # every pre-existing column keeps its index.
    "en_prox",
    # ---- DEX-cliff diagnostic, per strike (added 2026-08-01) ----------------
    # ARCHIVE ONLY. Nothing here feeds qualification, ranking or display -- these
    # four columns exist purely to measure whether a DEX cliff is worth acting on
    # before any rule is built on it.
    #
    # The workbook already has a dEdge rule (Level Engine CZ9) but it is gated:
    # it only evaluates in chop or positive gamma, only on shelves, and only at
    # strikes >= 10 pts from the DEX peak -- which on a 5-pt grid excludes the
    # strike immediately off the peak, i.e. the one place a cliff actually forms.
    # These columns are deliberately UNGATED so the suppressed cases are captured:
    # every strike, every regime, shelf or not.
    #
    #   dx_peak : strike carrying the largest |dex| this cycle (same on every row)
    #   dx_nbr  : |dex| of the neighbouring strike one step TOWARD dx_peak.
    #             Blank on dx_peak itself and where the neighbour is missing.
    #   dx_frac : (|dx_nbr| - |dex here|) / |dx_nbr|, rounded to 3dp. 1.0 is a
    #             total collapse; negative means dex GREW moving away from the peak.
    #   dx_cliff: 1 when dx_frac >= DXC_FRAC and dx_nbr >= DXC_FLOOR and the strike
    #             is >= DXC_MINDIST from the peak. Uses DXC_MINDIST = 5, NOT the
    #             live rule's 10, so the adjacent-to-peak case is measurable.
    #
    # Question these are here to answer: when dx_cliff fires on the support side,
    # does price hold there more often than the ~55% first-touch baseline? If not,
    # no rule should be built on it. Sit immediately before "event" so every
    # pre-existing column keeps its index.
    "dx_peak", "dx_nbr", "dx_frac", "dx_cliff",
    # ---- zomma window rank + box-edge divergence (added 2026-08-01) --------
    # ARCHIVE ONLY. Nothing here feeds qualification, ranking or display.
    #
    # The workbook's zomMark is the 6th-largest |zomma| across ALL 47 strikes,
    # so near-spot levels compete against far ones and are routinely shut out.
    # These columns rank |zomma| INSIDE the near window instead, which is what
    # the dashboard's zomma column now displays, and record the case that
    # prompted them: a box level whose two edges pull in opposite directions.
    #
    #   zw_rank      : rank of |zomma| among strikes within ZW_WINDOW pts of
    #                  spot. 1 = largest. Blank outside the window.
    #   zw_tier      : 1 = also clears the ladder-wide zomMark (top 6 overall)
    #                  2 = window rank <= 8 but not marked  ("sub-threshold")
    #                  3 = window rank 9+                   ("weak")
    #   zw_dir       : +1 firming / -1 thinning / 0 undecided. Sign of zomma
    #                  taken AGAINST IV direction, matching the sheet.
    #   zdiv         : 1 when this strike is a box level (at_boxlo <> au_boxhi)
    #                  and the two edges carry OPPOSITE zw_dir.
    #   zdiv_far     : the other edge's strike, when zdiv = 1.
    #   zdiv_farrank : that edge's zw_rank.
    #   zdiv_against : 1 when the diverging edge outranks the level itself
    #                  (zdiv_farrank < zw_rank) -- the stronger edge working
    #                  against the level. Observed 2026-07-30 at 7375 (r7)
    #                  boxed with 7380 (r2) pulling the other way.
    #
    # Question these are here to answer: does a level hold less often when
    # zdiv_against = 1 than when its box agrees with it? Sit immediately before
    # "event" so every pre-existing column keeps its index.
    "zw_rank", "zw_tier", "zw_dir", "zdiv", "zdiv_far", "zdiv_farrank", "zdiv_against",
    #   sv_updown : 1 when spot AND VIX1D are both above their session opens.
    #   sv_corr   : rolling 30-min Pearson correlation of spot CHANGES against
    #               VIX1D CHANGES. Negative on 32 of 33 archive days; the lone
    #               positive session (2026-08-04, +0.13) was a 4% melt-up.
    #   Logged so the sample accumulates with a timestamped record -- at roughly
    #   one sustained-positive day in 16, a testable n is a year away. Sit
    #   immediately before "event" so every pre-existing column keeps its index.
    "sv_updown", "sv_corr",
    #   sq_n      : how many of the five squeeze conditions are true this cycle
    #               (0-5). Logged at EVERY level, not just 5/5 -- comparing 5/5
    #               against 2/5 later is the whole point, and that needs the low
    #               readings too.
    #   sq_c1..c5 : the individual conditions, in order -- pos gamma, spot above
    #               the opening node, thin overhead gamma, DEX one-way all
    #               session, front-end vol expanding from a cheap open.
    #   The set was fitted to separate 2026-08-04 (5/5, +109.6 pts) from
    #   2026-07-24 (2/5, closed -2.9 after a round trip). FITTED, not tested --
    #   do not build a rule on it without a pre-registered walk-forward study.
    "sq_n", "sq_c1", "sq_c2", "sq_c3", "sq_c4", "sq_c5",
    #   oi_stall : open-interest stall state for THIS strike this cycle.
    #               0 = clear, 1 = flagged, 2 = flagged and past first escalation.
    #     Added 2026-08-07 after 7710 reported call_oi == put_oi == 615.0 in all 647
    #     snapshots of 2026-08-06. Gamma, dex, vega and IV were live all day; because
    #     gex, zomma and vex are call-minus-put differences, identical OI on both legs
    #     cancelled all three to exactly zero for the whole session with no error
    #     raised. Logged so the condition is auditable offline instead of only
    #     findable by inspection. Sits immediately before "event" so every
    #     pre-existing column keeps its index.
    "oi_stall",
    #   svx_dir  : 10-minute spot / TERM-VIX sign test, cycle-level.
    #               0 = off, 1 = spot up / vol up, -1 = spot down / vol up.
    #     Added 2026-08-13. Distinct from sv_updown/sv_corr, which both run on
    #     VIX1D; the 2026-08-13 advance (7748 -> 7815) had the front end FALLING
    #     from its open throughout, so neither of those fired during the move.
    #     Calibrated on 40 archive days -- see the SVX_ block for the full sweep
    #     and for why 0.05 was taken rather than the nominal 0.10 optimum.
    #     OBSERVATION ONLY. Sits immediately before "event" so every pre-existing
    #     column keeps its index.
    "svx_dir",
    #   iv_regime : the Matrix IV regime read, KNM L5 -- "High" / "Low" / "".
    #     Added 2026-08-14. This classification previously existed ONLY in the live
    #     workbook at the instant it was computed and was never written down, so no
    #     hypothesis involving the IV regime could be tested against any archived
    #     session -- the variable simply was not there. Raw atm_iv / vix / vix1d were
    #     archived, but the regime read is not recoverable from them: L5 resolves
    #     through a Master Dashboard override, then KNM P10, then a J5/B5-vs-H5
    #     comparison, and the override in particular leaves no trace in the Greeks.
    #     Archiving the resolved string is the only way to make it testable.
    #     This does not recover history; it starts the record from today.
    #     OBSERVATION ONLY -- nothing reads it back.
    "iv_regime",
    #   --- Matrix IV chain, added 2026-08-14 -------------------------------
    #   Archiving the resolved L5 alone is not enough to backtest with, because
    #   L5 is the OUTPUT of a three-branch resolution and the branches disagree.
    #   Without knowing which branch won, a future study cannot tell a manual
    #   override from a regime-map read from a plain VIX-vs-threshold band, and
    #   those are different signals that happen to share a cell. The four columns
    #   below record the chain so any archived cycle can be reconstructed.
    #
    #   iv_override : Master Dashboard L5 -- the manual override. Non-empty means
    #                 it WON and every other input below was ignored, whatever
    #                 they say. Check this first when reading the archive back.
    #   iv_map      : KNM P10 -- IV Regime Map verdict, "High"/"Low"/"MIXED"/"".
    #                 Wins when override is empty and this is High or Low.
    #   iv_state    : KNM P9  -- the named regime the map matched, e.g.
    #                 "Hidden Tail Bid". The reason behind iv_map.
    #   iv_band     : KNM J5  -- "HIGH"/"LOW"/"NEUTRAL" from the F5/B5 ratio,
    #                 D5 and B5. The fallback branch, used only when the two
    #                 above are silent; on NEUTRAL it degrades to VIX vs H5.
    #
    #   All four are READ-ONLY observations. Nothing in either engine, the Level
    #   Engine or any sheet consumes them. They exist to make the IV regime
    #   testable from tomorrow onward -- they do not recover any history.
    "iv_override",
    "iv_map",
    "iv_state",
    "iv_band",
    #   net_charm : signed net charm across the ladder, sign-normalised the same
    #     way as the H8 flag (net['Charm'] * CHARM_SIGN).
    #     Added 2026-08-15. flag_charm archives only the SIGN, so charm magnitude
    #     has never been recorded and nothing can be tested against it. That gap
    #     is why the Matrix charm text infers strength from the IV regime -- rows
    #     keyed High say "active", rows keyed Low say "dormant" -- when charm
    #     magnitude has nothing to do with IV. On 2026-08-14 charm was negative
    #     and persistent from 15:57 to the close while the Low row declared it
    #     "dormant, too small to matter" and appended a BUY directive.
    #     With this column the active/dormant call can be measured instead of
    #     guessed, and the claim that negative charm produces a late-session
    #     drift becomes testable rather than asserted from mechanism.
    #     OBSERVATION ONLY -- nothing reads it back.
    "net_charm",
    #   et_vsharp : Level Engine ET9:ET55 (header "vSharp") 0/1 -- the support-side
    #     DEX quality tag on an nVanna zone. 1 when a BELOW-spot nVanna strike carries
    #     net DEX at or above the median net DEX of the +/-NVAN_NEAR window.
    #     Added 2026-08-18. dt_nvanna records that a vol-reaction zone existed but not
    #     whether the dealer book was positioned to hold it, so "the Ⓥ support broke"
    #     and "the Ⓥ support held" are currently indistinguishable offline on the one
    #     dimension the tag is meant to separate.
    #     DISPLAY ONLY -- nothing reads it back, and it is NOT validated: 4-20 touch
    #     events across the archive depending on the touch definition, direction
    #     unstable across those definitions. Archived so a sample can accumulate.
    "et_vsharp",
    #   iv_latch_raw / iv_latch_held / iv_latch_cnt : SHADOW-MODE confirmation latch
    #     on the Matrix IV token. Added 2026-08-20.
    #     The Matrix key (KNM J8) is IV|Gamma|Zomma|Dex|Vex|Vega|Vomma|Speed, and
    #     every phenomenon row is duplicated High/Low with the IV token as the ONLY
    #     discriminator -- Matrix rows 2/3 are identical in all seven Greek signs and
    #     read "Fragile Long Vol" vs "Low-Vol Grind-Up / Melt-Up" purely on it. On
    #     2026-08-19 the Greek signs never moved (gamma Neg for all 554 cycles) while
    #     the token flipped 22 times, so the displayed phenomenon oscillated between
    #     those two rows on every rebound leg.
    #     J5's HIGH/NEUTRAL/LOW zones are a DEAD BAND, not hysteresis: both edges are
    #     fixed, so a value oscillating across either one flips every time. J5 is also
    #     mostly bypassed -- L5 takes P10 whenever it returns High or Low and only
    #     falls through to J5 on blank/MIXED, and P10 is a lookup on the three
    #     per-cycle direction tokens (P4/P5/P6), which repaint intraday.
    #     The latch: hold the token; each cycle compare the freshly derived value to
    #     the held one; count consecutive disagreements; swap only when the count
    #     reaches IV_LATCH_N, then reset. Agreement resets the count to 0.
    #     iv_latch_raw  -- the derived token this cycle (== iv_regime)
    #     iv_latch_held -- what the latch WOULD be showing
    #     iv_latch_cnt  -- consecutive disagreements pending
    #     SHADOW ONLY -- L5 is untouched, nothing reads these back, the dashboard is
    #     unchanged. Logged so the flip count at N=1 (today's behaviour) and at N=2,
    #     3, 4 can all be recovered offline from iv_latch_cnt without a rerun, and so
    #     N is chosen from the burst-length distribution rather than assumed. NOT
    #     VALIDATED: stability is all this measures; nothing here shows the latched
    #     token calls the phenomenon correctly more often than the unlatched one.
    "iv_latch_raw",
    "iv_latch_held",
    "iv_latch_cnt",
    #   md_phenom : Master Dashboard Phenomenon cell -- the phenomenon text as
    #     DISPLAYED at this cycle, verbatim. Added 2026-08-24.
    #     iv_state/iv_map/iv_band record the IV side of the Matrix key only; the
    #     phenomenon itself is the resolved Matrix row and has never been archived,
    #     so no past cycle can be told what it was showing. Trade grading on the
    #     Level Test Log needs the phenomenon that was on screen at entry, and that
    #     is this cell. Read defensively -- a missing cell archives blank rather
    #     than costing a cycle.
    #     OBSERVATION ONLY -- nothing reads it back.
    "md_phenom",
    #   backers : the confluence backer tokens for this strike this cycle, space
    #     separated, in the same order and with the same labels the Level Engine
    #     "Backers" column emits -- Gam Vex Dex Dex-dn Zom Spd iDex Gsh gSh dEdge
    #     oEdge Zsh Vxi Spi Vgf Gxp Gfx ZG. Added 2026-08-24.
    #     confl archives the COUNT only, so no past cycle can say WHICH components
    #     produced it -- two strikes both reading 5 may share no component at all.
    #     The Backers string itself is only ever built for the handful of locked
    #     levels the display block covers, so it does not exist for the rest of the
    #     ladder even live. This column builds it for every strike, every cycle.
    #     Note the tokens are the DISPLAY labels, not the underlying columns: Dex
    #     is the DEX-exceedance flag and Dex-dn the drop-off flag, and they are not
    #     mutually exclusive. Reconstructed here rather than read from the sheet so
    #     it covers strikes the sheet never renders.
    #     OBSERVATION ONLY -- nothing reads it back.
    "backers",
    #   vexstk / spdstk : VEX and Speed summed over this strike +/- 2 (5 strikes),
    #     and vexstk_rank : this strike's rank by vexstk, 1 = most NEGATIVE cluster
    #     on the board. Added 2026-08-27.
    #     Stacking is the part the eye does that no per-strike column can express:
    #     on 2026-08-27 7710/7705/7700 held ~-3.7M of VEX between them from 16:30 to
    #     19:25 and the session low stopped at 7710. The single-strike vex column
    #     cannot say that.
    #     BOTH sums are archived deliberately. Speed and VEX correlate at 0.88 in this
    #     data and picked identical strikes in that block (-1.12M/-0.92M/-1.70M VEX
    #     against -13.6k/-10.7k/-18.8k Speed). If a cluster effect shows up later,
    #     these two columns are what will say whether it is a VEX effect, a Speed
    #     effect, or indistinguishable -- archiving only one would settle that
    #     question by accident.
    #     OBSERVATION ONLY -- nothing reads these back.
    "vexstk", "spdstk", "vexstk_rank",
    #   kn_accel : 0/1 -- 1 when the reaction table is showing the king-node
    #     accelerant label ("UNSAFE.Level at risk / Neg gamma: the king node is an
    #     accelerant, not a floor") on either support slot this cycle. Added
    #     2026-09-03.
    #     The label fires when gamma regime is Neg, the slot level IS the king node
    #     (exact match, not proximity), and the nVanna break-suppression flag is not
    #     set on it. It restates a standing validated finding -- near-node supports
    #     in negative gamma break ~75% of the time -- on the one level the finding
    #     is literally about.
    #     Read verbatim from the display helper cells rather than recomputed, so the
    #     column records what was ON SCREEN, which is what trade grading needs. A
    #     missing sheet or cell archives 0 rather than costing a cycle.
    #     OBSERVATION ONLY -- nothing reads it back.
    "kn_accel",
    #   qual_tag / trough_geo / trough_deep / ppeak_geo / trough_unsafe :
    #     2026-09-18. The qualifying-tag STRING as displayed on the ladder, plus the
    #     four geometry flags behind the shelf-interior shapes, so the tags can be
    #     graded against outcomes later. Archived because none of these has been
    #     validated: TROUGH tested null in both regimes (46.3% vs 51.1%, p=0.56) and
    #     the UNSAFE on it ships as a level-SELECTION preference, not an edge. P-PEAK
    #     (positive-GEX interior maximum) is new and untested.
    #       qual_tag      : Level Engine FA -- DOM / GAP / PEAK- / gSh Edge / Trough / PEAK+ / Cluster
    #                       (2026-09-20: renamed from PEAK / P-PEAK -- archives before
    #                       this date carry the old names; PEAK+ = positive-GEX bump)
    #       trough_geo    : HL 0/1 -- interior local MINIMUM, any depth (names Trough)
    #       trough_deep   : HO 0/1 -- that minimum is >= 20% below both flanks
    #       ppeak_geo     : HN 0/1 -- interior local MAXIMUM with positive GEX
    #       trough_unsafe : HM 0/1 -- what actually fired on screen (Pos gamma only)
    #     OBSERVATION ONLY -- nothing reads these back.
    "qual_tag", "trough_geo", "trough_deep", "ppeak_geo", "trough_unsafe",
    #   call_vol / put_vol / call_vol_d / put_vol_d : per-strike option VOLUME.
    #     Added 2026-09-19. OPEN INTEREST does not move intraday -- IBKR publishes it
    #     once a day from the OCC overnight file, and the archive confirms it: on
    #     2026-09-17 exactly 1 of 47 strikes showed a second distinct put_oi value all
    #     session, 0 for calls. So call_oi/put_oi cannot answer "how is positioning at
    #     this strike changing today", and every question of that shape (the 2026-09-17
    #     7615 first-approach-vs-retest difference being the one that prompted this) is
    #     unanswerable from the existing columns. Volume is the only officially
    #     published per-strike series that does move intraday, and it arrives on the
    #     tick stream already open for each leg -- generic tick 100 added to the
    #     existing 101, no new reqMktData lines, so the batch-of-20 pacing that fixed
    #     the 94-simultaneous-request problem is untouched.
    #       call_vol / put_vol   : cumulative session volume for that leg, as reported.
    #       call_vol_d / put_vol_d : change since the previous archived cycle for this
    #                              strike. Blank on the first cycle a strike appears in
    #                              the window (no prior reading), and clamped at 0 rather
    #                              than going negative if a leg's counter resets or the
    #                              window re-centres onto a strike with a stale reading.
    #     OBSERVATION ONLY -- nothing reads these back, no workbook cell, no gate, no
    #     display. Do NOT build a rule on them until they have been collected for a week
    #     and tested; two candidate tells (vex-thin-on-approach, gamma growth between
    #     tests) both reproduced 2026-09-17 exactly and then tested null across 60
    #     archive days, so this column earns nothing until it is checked the same way.
    #     Sit immediately before "event" so every pre-existing column keeps its index.
    "call_vol", "put_vol", "call_vol_d", "put_vol_d",
    #   unsafe / unsafe_src : 2026-09-19. Per-strike UNSAFE, read from Level Engine
    #     HP (0/1 flag) and HQ (space-separated source codes: EDGE TROUGH BUMP SANDWICH
    #     ACCEL AMPLIFY NVANNA ZACCEL KINGACC KINGNODE LOWIVFALL HIGHIVFALL SPOTUPVOLUP
    #     SQUEEZE). Until this date UNSAFE existed only as text in a DISPLAYED reaction-
    #     table slot, so a level that was never displayed left no record and nothing
    #     could be graded. HP/HQ compute it for every strike, including the ones that
    #     never reach a slot. Slot-dependent warnings (chop edge, pin migration, charm,
    #     support-side spot-up/vol-up) are NOT in HQ -- they cannot be computed per
    #     strike. Blank (not 0) when the workbook has no HP/HQ columns, so an old
    #     workbook cannot masquerade as "nothing unsafe".
    #     OBSERVATION ONLY -- nothing reads these back.
    #     Sit immediately before "event" so every pre-existing column keeps its index.
    "unsafe", "unsafe_src",
    #   regime_key : 2026-09-22. 'King Node Model'!J8 verbatim -- the IV state plus the
    #     seven sign flags, the same key the Matrix and the A20 regime text are looked up
    #     by. Rebuilding it from the seven flag columns is possible but the IV half only
    #     exists in archives from mid-August, which left regime-restricted tests with too
    #     few readings to judge. One column makes those tests trivial.
    #     OBSERVATION ONLY -- nothing reads it back.
    #     Sits immediately before "event" so every pre-existing column keeps its index.
    "regime_key",
    #   rt_row / rt_rasp / rt_boxrow : 2026-09-19. What the REACTION TABLE actually
    #     showed this cycle, read verbatim from Master Dashboard E40:E42 / E47:E49 and
    #     the raspberry border AP40:AP42 / AP47:AP49 -- not recomputed -- so the record
    #     is what was ON SCREEN, which is what grading the ladder's safe levels needs.
    #       rt_row    : 40/41/42 (resistance) or 47/48/49 (support) if this strike is a
    #                   displayed level; blank if it was not displayed
    #       rt_rasp   : 1 if that row carried the raspberry UNSAFE border, else 0
    #                   (includes the slot-only warnings that HQ/unsafe_src cannot see)
    #       rt_boxrow : row number if this strike lies inside the "(box a-b)" of a
    #                   displayed level (box ends are painted on the ladder too)
    #     A "safe ladder level" = rt_row set AND rt_rasp = 0.
    #     All three archive "NA" if the read failed, so a failed read cannot
    #     masquerade as "nothing displayed".
    #     OBSERVATION ONLY -- nothing reads these back.
    #     Sit immediately before "event" so every pre-existing column keeps its index.
    "rt_row", "rt_rasp", "rt_boxrow",
    #   es_last / es_poc / es_vah / es_val : 2026-09-21. Cycle-level, ES points. The
    #     developing RTH volume profile (09:30-16:00 ET, PROFILE_BIN rows, VALUE_AREA)
    #     already shown on the Technical Analysis panel, plus the last ES trade so the
    #     ES->SPX basis can be recovered offline. Blank if the ES feed has no data.
    #     OBSERVATION ONLY -- nothing reads these back.
    #     Sit immediately before "event" so every pre-existing column keeps its index.
    "es_last", "es_poc", "es_vah", "es_val",
    #   mu_n / mu_cond / flow_c15 / flow_p15 : 2026-09-24. Cycle-level. MELT-UP WATCH
    #     count (0-4, blank until any condition is measurable) and condition vector
    #     (price/vol/flow/structure: 1 met, 0 not, - not yet measurable), archived in
    #     EVERY regime; plus 15-minute call / put volume summed across the window.
    #     OBSERVATION ONLY -- nothing reads these back. UNTESTED.
    #     Sit immediately before "event" so every pre-existing column keeps its index.
    "mu_n", "mu_cond", "flow_c15", "flow_p15",
    #   iv_top : 2026-09-24. Cycle-level IV-top alert (Level Engine BG78). The per-strike
    #     vanna-SELL UNSAFE it clears is archived as the VSELL token in unsafe_src.
    #     OBSERVATION ONLY. Sits immediately before "event".
    "iv_top",
    #   atm_iv_fast : 2026-09-24. Cycle-level FAST ATM IV direction (Level Engine BG80: UP /
    #     DOWN / FLAT over the last 5 min, 0.1 vol pt dead zone; blank while building). Drives
    #     the reaction-table vanna reading and the vanna-SELL UNSAFE. Before "event".
    "atm_iv_fast",
    #   frag_pos : 2026-10-01 (Giggles). Cycle-level fragile positive-gamma HOLD exactly as
    #     published to Level Engine BG76 this cycle: 1 = fragile (or armed after a non-positive
    #     cycle), 0 = not fragile, blank = not published (BG72 then used its raw test). The
    #     sheet's BG72 = this value when King Node Model A8 reads Pos, else 0. Replay writes it
    #     back to BG76 so fragile reads exactly as it did live. Before "event".
    "frag_pos",
    #   vlatch / call_wall / zom_dir / zom_safe : 2026-10-02 (Giggles), PER STRIKE, so the rules
    #     built that day can be graded -- an archived SAFE level says WHICH rule made it safe.
    #     vlatch    = Level Engine JR, the engine's vanna-override latch (neg/fragile γ) 1/0
    #     call_wall = Level Engine JZ, call-wall resistance flag (neg/fragile γ) 1/0
    #     zom_dir   = Level Engine KC, IV direction every zomma reading used (UP/DOWN/FLAT,
    #                 arrival basis: support UP, resistance DOWN; current fast within BG98 pts)
    #     zom_safe  = Level Engine JS, Min/Max Zomma SAFE (positive γ) 1/0
    #     All four sit immediately before the event column; blank when the workbook lacks the column.
    "vlatch",
    "call_wall",
    "zom_dir",
    "zom_safe",
    #   safe_src / cleared_src / status_chg : 2026-10-03 (Giggles), PER STRIKE.
    #     safe_src    = Level Engine KH: which rule makes the level SAFE (VLATCH, ZOMSAFE, DOMBUY,
    #                   VOLBOUNCE, MINVEX, CALLWALL) when it is not UNSAFE; blank otherwise
    #     cleared_src = Level Engine KI: UNSAFE reasons the vanna override switched off
    #     status_chg  = engine: TO_SAFE / TO_UNSAFE on the cycle the strike's unsafe flag flips
    "safe_src",
    "cleared_src",
    "status_chg",
    #   king_node : 2026-10-04 (Giggles), CYCLE-LEVEL (same on every strike row): the king node
    #     strike this cycle = King Node Model B23 (max-gamma strike), so king-node rules can be
    #     graded later. Blank if not numeric.
    "king_node",
    #   rt_text : 2026-10-04 (Giggles), PER STRIKE: the reaction table's Neg-γ column text (Master
    #     Dashboard L45:L47 / L52:L54) for a strike shown on the table this cycle -- the exact SAFE
    #     label or UNSAFE reasons on screen, line breaks as " | ". Blank for strikes not on the table.
    #     Captures reasons that exist only as dashboard text (e.g. the chop-edge "IV High + ATM IV
    #     falling (melt-up risk)" resistance warning), which unsafe_src does not carry.
    "rt_text",
    # 2026-10-06 (Giggles): the Vol Tension line (King Node Model AB17, e.g. "VOL TENSION POS GAMMA BUILDING
    # ... resistance leaks -- dips shallow") so the "resistance leaks + negative DEX above" idea can be tested
    # once ~20 sessions carry it. Cycle-level, repeated on every strike row.
    "vol_tension",
    "event",
]

# ---- IV token confirmation latch (shadow mode; archive only) --------------
# Consecutive disagreeing cycles required before the held token swaps. Seeded at
# 3 because the 2026-08-19 flips came in bursts of one or two cycles, while a real
# regime change persists well past that and still gets through with roughly a
# minute of lag. This is a STARTING VALUE to be measured, not a validated one.
IV_LATCH_N = 3

# ---- DEX-cliff diagnostic thresholds (archive only, safe to tune) ----------
# Seeded from the workbook's own dEdge settings (Level Engine BG42/BG43) so the
# measurement is comparable to the live rule. DXC_MINDIST intentionally differs:
# the live rule uses 10, which can never fire adjacent to the peak on a 5-pt grid.
DXC_FRAC = 0.50        # minimum collapse fraction vs the neighbour toward the peak
DXC_FLOOR = 80_000     # that neighbour's |dex| must be at least this big
DXC_MINDIST = 5        # minimum distance from the DEX peak, in points

# ---- zomma window-rank diagnostic (archive only, safe to tune) ------------
ZW_WINDOW = 50         # near window in points; mirrors Level Engine BG7
ZW_BAND = 8            # window rank that still counts as "sub-threshold"
ZW_MARK_N = 6          # ladder-wide zomMark rank, mirrors Level Engine S10
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


# ---- per-strike option VOLUME (archive only, 2026-09-19) ------------------
# Open interest is a once-a-day OCC number and does not move intraday; volume is
# the only per-strike series IBKR publishes that does. Arrives on generic tick 100,
# added to the existing 101 on the SAME reqMktData line per leg -- no extra
# subscriptions, so the batch-of-20 pacing is unaffected.
# _vol_prev holds last cycle's cumulative reading per strike so the per-cycle delta
# can be derived here rather than offline. A strike leaving and re-entering the
# window keeps its last reading; the delta clamps at 0 so a stale or reset counter
# can never archive a negative.
_vol_prev = {}


VOL_CUM_MAX = 1e8     # 2026-09-29: a per-strike session volume at/above this is a feed sentinel,
                      # not a print. IBKR sometimes sends 4,294,967,295 (unsigned -1) or
                      # 2,147,483,647 (UNSET_INTEGER); one such reading put "calls 4294.79M" on
                      # the 15m / session / 1h flow rows on 09-29.
VOL_D_MAX   = 1e6     # ... and a single-strike, single-cycle increase at/above this is rejected too


def vol_sane(v, delta=False):
    """True if an (archived or live) volume number is believable."""
    return isinstance(v, (int, float)) and v == v and 0 <= v < (VOL_D_MAX if delta else VOL_CUM_MAX)


def volnum(x):
    """IBKR sends -1 for 'no volume reported yet' and None before the first tick; it can also
       send an unsigned/unset sentinel (~4.29e9 / ~2.15e9). All of these read as 'no reading'."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not vol_sane(v):      # NaN, the -1 sentinel, or an overflow / unset sentinel
        return None
    return v


def vol_row(k, ct, pt):
    """(call_vol, put_vol, call_vol_d, put_vol_d) for one strike, all blank-safe.
       Deltas are blank on the first reading for a strike -- no prior cycle to
       difference against -- and never raise."""
    try:
        key = round(k)
        cv, pv = volnum(getattr(ct, 'volume', None)), volnum(getattr(pt, 'volume', None))
        prev = _vol_prev.get(key)
        cd = pd_ = ""
        if prev is not None:
            if cv is not None and prev[0] is not None:
                cd = max(0.0, cv - prev[0])
                if not vol_sane(cd, delta=True):
                    cd = ""
            if pv is not None and prev[1] is not None:
                pd_ = max(0.0, pv - prev[1])
                if not vol_sane(pd_, delta=True):
                    pd_ = ""
        _vol_prev[key] = (cv if cv is not None else (prev[0] if prev else None),
                          pv if pv is not None else (prev[1] if prev else None))
        return (cv if cv is not None else "", pv if pv is not None else "", cd, pd_)
    except Exception:
        return ("", "", "", "")


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


def market_open():
    now = utc_to_et(datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))
    if now.weekday() >= 5:
        return False
    return (now.hour, now.minute) >= (9, 30) and (now.hour, now.minute) <= (16, 0)


# ---- IV latch state (shadow mode) ----
_iv_latch_held = None      # token currently held; seeded on the first cycle of the session
_iv_latch_cnt = 0          # consecutive cycles the derived token has disagreed


def iv_latch_step(raw):
    """Advance the shadow latch one cycle and return (held, pending_count).

       Never raises and never blocks the cycle -- a blank or unreadable token
       leaves the held value alone and reports the count unchanged, exactly as a
       failed observation column should behave."""
    global _iv_latch_held, _iv_latch_cnt
    try:
        tok = (raw or "").strip()
        if not tok:
            return (_iv_latch_held or ""), _iv_latch_cnt
        if _iv_latch_held is None:          # first usable cycle of the session
            _iv_latch_held = tok
            _iv_latch_cnt = 0
        elif tok == _iv_latch_held:
            _iv_latch_cnt = 0
        else:
            _iv_latch_cnt += 1
            if _iv_latch_cnt >= IV_LATCH_N:
                _iv_latch_held = tok
                _iv_latch_cnt = 0
        return _iv_latch_held, _iv_latch_cnt
    except Exception:
        return (_iv_latch_held or ""), _iv_latch_cnt


# ---- archive snapshot ----
_next_event = ""   # one-shot marker ("RECONNECT") stamped on the next archived cycle
_last_arch_spot = None   # last archived spot, reference for the single-cycle SPIKE? flag

_ARCH_ROLL_WARNED = {}      # path -> True, so the roll notice prints once, not every cycle


def archive_snapshot(ts, spot, vix, vvix, vix1d, flags_row, charm_flag, locked_R, locked_S, table_rows,
                     qual_by_strike=None, raw_by_strike=None, es_sma200=None, es_sma400=None,
                     put_skew=None, call_skew=None, risk_rev=None,
                     atm_iv=None, atm_iv_dir=None,
                     ct_lo=None, ct_hi=None, cw_lo=None, cw_hi=None,
                     state_by_strike=None, pin_state=None, s10_zomthr=None, prox_strike=None,
                     sv_updown=None, sv_corr=None, sq_n=None, sq_c=None,
                     oi_stall_by_strike=None, svx_dir=None, iv_regime=None,
                     iv_chain=None, net_charm=None, md_phenom=None,
                     backers_by_strike=None, kn_accel=None, vol_by_strike=None,
                     unsafe_by_strike=None, rt_by_strike=None, es_prof=None,
                     geo_by_strike=None, regime_key=None, mu=None, iv_top=None,
                     iv_fast=None, frag_pos=None, rules_by_strike=None, safe_by_strike=None,
                     king_node=None, rt_text_by_strike=None, vol_tension=None):
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
    # ---- IV token confirmation latch, shadow mode (archive only) ----------
    # Stepped once per cycle, before the per-strike loop, so every strike row in
    # this snapshot carries the same latch state.
    _lat_raw = (iv_regime or "").strip() if iv_regime is not None else ""
    _lat_held, _lat_cnt = iv_latch_step(_lat_raw)
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
                with open(path, "r", newline="", encoding="cp1252", errors="replace") as _f:
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
                        with open(_alt, "r", newline="", encoding="cp1252", errors="replace") as _f:
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
        # 2026-09-22: explicit cp1252 + errors="replace". Without an encoding, Windows opened the
        # archive in its default code page, and any non-Latin character in an archived text
        # field (the "γ" in "γSh") raised mid-cycle -- only the rows before it were written,
        # so each cycle kept ONE row (strike row 0) and the ladder was lost. cp1252 keeps every
        # existing archive readable; unencodable characters are written as "?".
        with open(path, "a", newline="", encoding="cp1252", errors="replace") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(ARCHIVE_HEADER)
            _written, _row_errs = 0, []
            qmap = qual_by_strike or {}
            rmap = raw_by_strike or {}

            # ---- DEX-cliff diagnostic (archive only; feeds nothing) ----------
            # Built from table_rows alone so it cannot touch the signal path.
            # row = [strike, gamma, gex, zomma, dex, ...] -> dex is row[4].
            _dx = {}
            _dxpeak = ""
            try:
                _dexmap = {}
                for _r in table_rows:
                    if not isinstance(_r[0], (int, float)):
                        continue
                    _d = _r[4] if len(_r) > 4 else None
                    if isinstance(_d, (int, float)) and not (
                            isinstance(_d, float) and math.isnan(_d)):
                        _dexmap[round(float(_r[0]))] = float(_d)
                if _dexmap:
                    _dxpeak = max(_dexmap, key=lambda k: abs(_dexmap[k]))
                    for _k, _v in _dexmap.items():
                        if _k == _dxpeak:
                            _dx[_k] = ("", "", 0)
                            continue
                        # one strike TOWARD the peak
                        _nb = _k - 5 if _k > _dxpeak else _k + 5
                        _nv = _dexmap.get(_nb)
                        if _nv is None or abs(_nv) <= 0:
                            _dx[_k] = ("", "", 0)
                            continue
                        _frac = (abs(_nv) - abs(_v)) / abs(_nv)
                        _cliff = 1 if (_frac >= DXC_FRAC
                                       and abs(_nv) >= DXC_FLOOR
                                       and abs(_k - _dxpeak) >= DXC_MINDIST) else 0
                        _dx[_k] = (round(abs(_nv)), round(_frac, 3), _cliff)
            except Exception:
                _dx, _dxpeak = {}, ""

            # ---- zomma window rank + box divergence (archive only) ------
            # row = [strike, gamma, gex, zomma, ...] -> zomma is row[3].
            _zw = {}
            try:
                _zmap = {}
                for _r in table_rows:
                    if not isinstance(_r[0], (int, float)):
                        continue
                    _zv = _r[3] if len(_r) > 3 else None
                    if isinstance(_zv, (int, float)) and not (
                            isinstance(_zv, float) and math.isnan(_zv)):
                        _zmap[round(float(_r[0]))] = float(_zv)
                # 2026-10-01 (Giggles): the sheet's zomma direction now reads the FAST ATM IV
                # direction (BG80, else D5), so zw_dir follows it to keep "matching the sheet".
                _ivdir = (iv_fast or atm_iv_dir or "").strip().upper()
                _sgn = 1 if _ivdir.startswith("UP") else (-1 if _ivdir.startswith("DOWN") else 0)
                if _zmap and isinstance(spot, (int, float)):
                    _mark = sorted((abs(v) for v in _zmap.values()), reverse=True)
                    _mark = _mark[ZW_MARK_N - 1] if len(_mark) >= ZW_MARK_N else 0.0
                    _win = sorted((k for k in _zmap if abs(k - spot) <= ZW_WINDOW),
                                  key=lambda k: -abs(_zmap[k]))
                    _rank = {k: i for i, k in enumerate(_win, 1)}
                    for _k in _win:
                        _rk = _rank[_k]
                        _tier = 1 if abs(_zmap[_k]) >= _mark else (2 if _rk <= ZW_BAND else 3)
                        _dir = _sgn * (1 if _zmap[_k] > 0 else (-1 if _zmap[_k] < 0 else 0))
                        _zw[_k] = [_rk, _tier, _dir, 0, "", "", 0]
                    # box edges come from the qualification map (at_boxlo / au_boxhi)
                    for _k in _win:
                        _q = (qual_by_strike or {}).get(_k)
                        if not _q:
                            continue
                        try:
                            _blo, _bhi = float(_q[11]), float(_q[12])
                        except (TypeError, ValueError, IndexError):
                            continue
                        if _blo == _bhi:
                            continue
                        _far = round(_bhi if _k == round(_blo) else _blo)
                        if _far == _k or _far not in _zw:
                            continue
                        _d1, _d2 = _zw[_k][2], _zw[_far][2]
                        if _d1 and _d2 and _d1 != _d2:
                            _zw[_k][3] = 1
                            _zw[_k][4] = _far
                            _zw[_k][5] = _zw[_far][0]
                            _zw[_k][6] = 1 if _zw[_far][0] < _rank[_k] else 0
            except Exception:
                _zw = {}

            # ---- VEX / Speed cluster sums (added 2026-08-27) --------------------
            # Window is +/- 2 strikes = 5 wide, which is roughly what reads as a block
            # on the ladder. Computed from table_rows itself so it needs no sheet read
            # and cannot fail a cycle; a gap in the ladder simply shortens the window.
            _stk = {}
            try:
                _vx = {round(r[0]): (r[5] if isinstance(r[5], (int, float)) else 0.0)
                       for r in table_rows if isinstance(r[0], (int, float))}
                _sp = {round(r[0]): (r[8] if isinstance(r[8], (int, float)) else 0.0)
                       for r in table_rows if isinstance(r[0], (int, float))}
                for _kk in _vx:
                    _win = [_kk + _o * 5 for _o in (-2, -1, 0, 1, 2)]
                    _stk[_kk] = (sum(_vx.get(w, 0.0) for w in _win),
                                 sum(_sp.get(w, 0.0) for w in _win))
                # rank 1 = most negative cluster
                _order = sorted(_stk, key=lambda k: _stk[k][0])
                _vrank = {k: i + 1 for i, k in enumerate(_order)}
            except Exception as e:
                print(f"   ! VEX/Speed stack calc failed ({e}); vexstk columns archive blank")
                _stk, _vrank = {}, {}

            _checked = False
            for idx, row in enumerate(table_rows):
                # row = [strike, gamma, gex, zomma, dex, vex, vomma, vega, speed]
                _k = round(row[0]) if isinstance(row[0], (int, float)) else row[0]
                (_confl, _absg, _ar, _rk,
                 _cu, _cv, _bk, _dh, _dc, _cz, _ej,
                 _at, _au, _dm, _dn, _ef,
                 _al, _bt, _ee) = qmap.get(
                     _k, ("",) * 19)
                _civ, _piv, _coi, _poi = rmap.get(_k, ("", "", "", ""))
                _sv = (state_by_strike or {}).get(round(float(row[0])), (None, None, None, None, None))
                _geo = (geo_by_strike or {}).get(round(float(row[0])), ("", "", "", "", ""))
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
                         pin_state if pin_state is not None else "",
                         _ej,
                         _at, _au, _dm, _dn, _ef,
                         _al,
                         s10_zomthr if s10_zomthr is not None else "",
                         _bt, _ee,
                         (1 if (prox_strike is not None
                                and isinstance(row[0], (int, float))
                                and round(float(row[0])) == round(prox_strike)) else 0),
                         _dxpeak,
                         _dx.get(_k, ("", "", ""))[0],
                         _dx.get(_k, ("", "", ""))[1],
                         _dx.get(_k, ("", "", ""))[2],
                         _zw.get(_k, ["", "", "", "", "", "", ""])[0],
                         _zw.get(_k, ["", "", "", "", "", "", ""])[1],
                         _zw.get(_k, ["", "", "", "", "", "", ""])[2],
                         _zw.get(_k, ["", "", "", "", "", "", ""])[3],
                         _zw.get(_k, ["", "", "", "", "", "", ""])[4],
                         _zw.get(_k, ["", "", "", "", "", "", ""])[5],
                         _zw.get(_k, ["", "", "", "", "", "", ""])[6],
                         sv_updown if sv_updown is not None else "",
                         round(sv_corr, 4) if isinstance(sv_corr, float) else "",
                         sq_n if sq_n is not None else "",
                         *(list(sq_c) if sq_c else [""] * 5),
                         (oi_stall_by_strike or {}).get(_k, 0),
                         svx_dir if svx_dir is not None else "",
                         iv_regime if iv_regime is not None else "",
                         *[(iv_chain or {}).get(_c, "") for _c in
                           ("override", "map", "state", "band")],
                         round(net_charm, 2) if isinstance(net_charm, (int, float)) else "",
                         _sv[4] if _sv[4] is not None else "",
                         _lat_raw, _lat_held, _lat_cnt,
                         md_phenom if md_phenom is not None else "",
                         (backers_by_strike or {}).get(_k, ""),
                         round(_stk[_k][0], 2) if _k in _stk else "",
                         round(_stk[_k][1], 2) if _k in _stk else "",
                         _vrank.get(_k, ""),
                         1 if kn_accel else 0,
                         _geo[0], _geo[1], _geo[2], _geo[3], _geo[4],
                         *((vol_by_strike or {}).get(_k, ("", "", "", ""))),
                         *((unsafe_by_strike or {}).get(round(float(row[0])), ("", ""))),
                         # 2026-09-24: regime_key moved here to match ARCHIVE_HEADER. It was
                         # appended AFTER es_* while the header lists it before rt_row, so
                         # from 2026-09-23 regime_key..es_val each held the NEXT column's
                         # value (the arity guard only checks the count, not the order).
                         ("" if regime_key is None else str(regime_key)),
                         *(("NA", "NA", "NA") if rt_by_strike is None else
                           tuple(rt_by_strike.get(round(float(row[0])), ("", "", "")))),
                         *[("" if _e is None else _e) for _e in (es_prof or (None,) * 4)],
                         *[("" if _e is None else _e) for _e in (mu or ("",) * 4)],
                         ("" if iv_top is None else iv_top),
                         ("" if iv_fast is None else iv_fast),
                         ("" if frag_pos is None else frag_pos),
                         *((rules_by_strike or {}).get(round(float(row[0])), ("", "", "", ""))),
                         *((safe_by_strike or {}).get(round(float(row[0])), ("", "", ""))),
                         (round(float(king_node)) if isinstance(king_node, (int, float)) else ""),
                         (rt_text_by_strike or {}).get(round(float(row[0])), ""),
                         (vol_tension if isinstance(vol_tension, str) else ""),
                         event])
                if not _checked:
                    # Cheap once-per-cycle guard. A column added to ARCHIVE_HEADER without a
                    # matching value here would otherwise shift every later field silently --
                    # the CSV still parses, it is just wrong. Fail loudly instead.
                    if len(_out) != len(ARCHIVE_HEADER):
                        raise ValueError(f"archive row has {len(_out)} fields, "
                                         f"ARCHIVE_HEADER has {len(ARCHIVE_HEADER)}")
                    _checked = True
                try:
                    w.writerow(_out)
                    _written += 1
                except Exception as _we:
                    _row_errs.append(f"{row[0]}: {_we}")
        # ---- 2026-09-22 archive completeness guard -------------------------------
        # A per-row failure used to abort the whole cycle mid-write: on 2026-09-22 an
        # encoding error on the first row carrying "γSh" left ONE row per cycle (the
        # ladder was lost for the session) and the only sign was a one-line warning that
        # looked like a transient. Rows are written individually now, and a short cycle
        # is reported LOUDLY every time, naming the first failures.
        if _row_errs or _written != len(table_rows):
            print(f"   !! ARCHIVE SHORT CYCLE: wrote {_written} of {len(table_rows)} strike "
                  f"rows to {os.path.basename(path)}")
            for _e2 in _row_errs[:3]:
                print(f"   !!   row {_e2}")
            if len(_row_errs) > 3:
                print(f"   !!   ... and {len(_row_errs) - 3} more")
    except Exception as e:
        print(f"   ! archive write failed: {e}")


# ---- level lock (hysteresis) ----
# ============ VANNA OVERRIDE LATCH (2026-09-29, Giggles) ============
# Neg / fragile gamma, reversal-flagged levels on the locked R / S lists. Aligned vanna
# (SELL on a resistance, BUY on a support) at >= BG91 (DOM: BG92) ARMS the latch; it then
# HOLDS through flat, shrinking or small-opposed vanna (the at-the-strike flicker) and is
# RELEASED when the level is broken by more than BG9 pts, when vanna turns opposed at
# >= BG94, when the level leaves the list / loses its reversal flag / the regime leaves
# neg-fragile, or at a new session. The engine writes the result to Level Engine JR; the
# workbook's aligned-vanna override (JI) reads it. Vanna direction: 2026-10-01 (Giggles) the
# ARRIVAL reading, mirroring Level Engine JV (vanna_dir_arrival); was the IY current reading.
# ---- DEX DRAIN (2026-09-30, Giggles) -> 'Level Engine'!JT9:JT55 (ported to LIVE 2026-10-01)
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


_drain_hist = {}
_drain_state = {}
_drain_day = None


def drain_live_step(sht_le, spot, rows, gamma_flag):
    """LIVE: update the DEX-drain flags from this cycle's table rows and write JT9:JT55
       aligned to Level Engine AA9:AA55. Never raises."""
    global _drain_day
    try:
        if _drain_day != et_now().date():
            _drain_hist.clear(); _drain_state.clear(); _drain_day = et_now().date()
        pos = (gamma_flag == 'Pos')
        flag = {}
        for r in rows:
            k = r[0]
            if not isinstance(k, (int, float)):
                continue
            kk = round(float(k)); dx, vx = r[4], r[5]
            a = abs(dx) if isinstance(dx, (int, float)) else None
            q = _drain_hist.setdefault(kk, deque(maxlen=DRAIN_WIN + 1))
            if a is not None:
                q.append(a)
            flag[kk] = drain_step(_drain_state, q, kk, a, vx, spot, pos)
        ks = sht_le.range('AA9:AA55').value
        sht_le.range('JT9:JT55').value = [[flag.get(round(k), 0) if isinstance(k, (int, float)) else 0] for k in ks]
    except Exception as e:
        print(f"   ! DEX drain skipped ({e})")



# ---- gDex-rule vanna UNSAFE latch -> 'Level Engine'!KO9:KO55 (2026-10-05, Giggles; ported from replay) ----
# POSITIVE gamma only (not fragile). Raw test mirrors Level Engine KN: a strike whose reversal flag comes
# from gDex (isolated DEX -- opposite sign to both ladder neighbours, which share a sign, and > 10% of
# their average |DEX| -- at a POSITIVE-GEX strike) and whose ARRIVAL vanna does not support the move
# (resistance not SELL / support not BUY, any size). Hysteresis: ON after GDV_HOLD cycles in a row, OFF
# after GDV_HOLD cycles without it; reset at a new session or when the regime leaves positive gamma.
# The workbook (KP) uses KO when it is a number, else the raw KN. The "gDex is the ONLY reversal reason"
# test (KQ) is applied by the workbook every cycle, not latched here. Written only when KO8 carries the
# gDexVannaLatch header, so an older workbook is never written into. UNTESTED.
GDV_ENABLED = True
GDV_HOLD    = 2
_gdv_state = {}
_gdv_day = None


def gdv_live_step(sht_le, spot, rows, pos, ivfast, ivtop, near, svuv, locked_R, locked_S):
    """LIVE: one cycle of the gDex-rule latch; writes KO9:KO55 aligned to AA9:AA55. Never raises."""
    global _gdv_day
    try:
        if not str(sht_le['KO8'].value or '').startswith('gDexVannaLatch'):
            return
        if _gdv_day != et_now().date():
            _gdv_state.clear(); _gdv_day = et_now().date()
        if not pos:
            _gdv_state.clear()
        lad = sorted([r for r in rows if isinstance(r[0], (int, float)) and r[0] == r[0]], key=lambda r: -r[0])
        Rl = {round(k) for k in (locked_R or []) if isinstance(k, (int, float)) and k == k}
        Sl = {round(k) for k in (locked_S or []) if isinstance(k, (int, float)) and k == k}
        sgn = lambda x: (x > 0) - (x < 0)
        flag = {}
        for i, r in enumerate(lad):
            kk = round(float(r[0]))
            raw = False
            if pos and 0 < i < len(lad) - 1 and isinstance(spot, (int, float)):
                gx, d0, du, dd, vx = r[2], r[4], lad[i - 1][4], lad[i + 1][4], r[5]
                if all(isinstance(x, (int, float)) for x in (gx, d0, du, dd)):
                    if (gx > 0 and d0 != 0 and sgn(du) != 0 and sgn(du) == sgn(dd) and sgn(d0) == -sgn(du)
                            and abs(d0) > (abs(du) + abs(dd)) / 2 * 0.1):
                        side = 'R' if kk in Rl else ('S' if kk in Sl else ('R' if r[0] > spot else 'S'))
                        dv = vanna_dir_arrival(kk, side, vx, ivfast, spot, ivtop, near, svuv)
                        raw = not ((side == 'R' and dv == 'SELL') or (side == 'S' and dv == 'BUY'))
            st = _gdv_state.setdefault(kk, {'on': False, 'n_on': 0, 'n_off': 0})
            if st['on']:
                st['n_off'] = 0 if raw else st['n_off'] + 1
                if st['n_off'] >= GDV_HOLD:
                    st.update(on=False, n_on=0, n_off=0)
            else:
                st['n_on'] = st['n_on'] + 1 if raw else 0
                if st['n_on'] >= GDV_HOLD:
                    st.update(on=True, n_on=0, n_off=0)
            flag[kk] = 1 if st['on'] else 0
        for kk in [k for k in _gdv_state if k not in flag]:     # strike left the ladder: counts as "not raw"
            st = _gdv_state[kk]
            if st['on']:
                st['n_off'] += 1
                if st['n_off'] >= GDV_HOLD:
                    del _gdv_state[kk]
            else:
                del _gdv_state[kk]
        ks = sht_le.range('AA9:AA55').value
        sht_le.range('KO9:KO55').value = [[flag.get(round(k), 0) if isinstance(k, (int, float)) else 0] for k in ks]
    except Exception as e:
        print(f"   ! gDex-rule latch skipped ({e})")


# ---- Spd★ 2-cycle hold -> 'Level Engine'!BG123:BG126 (2026-10-07, Giggles) ----------------
# Publishes the Max/Min Speed strikes of the PREVIOUS two cycles: BG123 Max 1 ago, BG124 Max 2 ago,
# BG125 Min 1 ago, BG126 Min 2 ago. The workbook (KY) keeps Spd★ on a strike that held that spot in
# either of them, POSITIVE gamma only (not fragile), while its speed stays side-aligned -- the regime
# gate and switch (BG127) live in the workbook. Extreme picked exactly as BG118/BG119 do: ladder order
# (descending strike), first occurrence wins. Reset at a new session. Written only when BF123 carries
# the engine label, so an older workbook is never written into. Never raises. UNTESTED.
SPD_HOLD_N = 2
_spd_hist = []        # [(max_strike, min_strike), ...] oldest first, previous cycles only
_spd_day = None


def _spd_extremes(rows):
    """(Max Speed strike, Min Speed strike) from ladder rows [strike, ..., speed(idx 8)] in ladder order."""
    best_hi = best_lo = None
    for r in rows or []:
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


def _write_spd_hold(rows):
    """LIVE: publish the last SPD_HOLD_N cycles' Max/Min Speed strikes, then remember this cycle's."""
    global _spd_day, _spd_hist
    try:
        if not str(sht_le['BF123'].value or '').startswith('(engine) MAX SPEED strike 1 cycle ago'):
            return
        if _spd_day != et_now().date():
            _spd_hist, _spd_day = [], et_now().date()
        prev = list(reversed(_spd_hist))[:SPD_HOLD_N]          # newest first
        prev += [(None, None)] * (SPD_HOLD_N - len(prev))
        sht_le.range('BG123:BG126').value = [[prev[0][0]], [prev[1][0]], [prev[0][1]], [prev[1][1]]]
        _spd_hist.append(_spd_extremes(rows))
        _spd_hist = _spd_hist[-SPD_HOLD_N:]
    except Exception as e:
        try:
            sht_le.range('BG123:BG126').value = [[None]] * 4
        except Exception:
            pass
        print(f"   ! Spd★ hold skipped ({e}); BG123:BG126 blank -> no hold this cycle")


# ---- VEX breakout take-profit latch -> 'Level Engine'!LO9:LO55 (2026-10-07, Giggles) --------------
# POSITIVE gamma only (not fragile). Raw test mirrors Level Engine LN: |VEX| >= BG142 at the strike and the
# CURRENT fast ATM IV direction makes dealer vanna work against the level -- resistance: dealers BUY
# (VEX > 0 with IV DOWN, or VEX < 0 with IV UP); support: dealers SELL. Flat IV = no signal. Hysteresis:
# ON after BG143 cycles in a row, OFF after BG143 cycles without it; reset at a new session or when the
# regime leaves positive gamma. Written only when LO8 carries the vexBreakLatch header. Never raises. UNTESTED.
VB_ENABLED = True
_vb_state = {}
_vb_day = None


def vb_live_step(sht_le, spot, rows, pos, ivfast, locked_R, locked_S):
    """LIVE: one cycle of the VEX-breakout latch; writes LO9:LO55 aligned to AA9:AA55. Never raises."""
    global _vb_day
    try:
        if not str(sht_le['LO8'].value or '').startswith('vexBreakLatch'):
            return
        thr = sht_le['BG142'].value; thr = thr if isinstance(thr, (int, float)) else 1000000
        hold = sht_le['BG143'].value; hold = max(1, int(hold)) if isinstance(hold, (int, float)) else 2
        if _vb_day != et_now().date():
            _vb_state.clear(); _vb_day = et_now().date()
        if not pos:
            _vb_state.clear()
        iv = str(ivfast or '').strip().upper()
        Rl = {round(k) for k in (locked_R or []) if isinstance(k, (int, float)) and k == k}
        Sl = {round(k) for k in (locked_S or []) if isinstance(k, (int, float)) and k == k}
        flag = {}
        for r in rows or []:
            k, vx = r[0], r[5]
            if not isinstance(k, (int, float)) or k != k:
                continue
            kk = round(float(k)); raw = False
            if pos and isinstance(vx, (int, float)) and abs(vx) >= thr and isinstance(spot, (int, float)) and iv in ('UP', 'DOWN'):
                side = 'R' if kk in Rl else ('S' if kk in Sl else ('R' if k > spot else 'S'))
                buy = (vx > 0 and iv == 'DOWN') or (vx < 0 and iv == 'UP')
                raw = buy if side == 'R' else (not buy)
            st = _vb_state.setdefault(kk, {'on': False, 'n_on': 0, 'n_off': 0})
            if st['on']:
                st['n_off'] = 0 if raw else st['n_off'] + 1
                if st['n_off'] >= hold:
                    st.update(on=False, n_on=0, n_off=0)
            else:
                st['n_on'] = st['n_on'] + 1 if raw else 0
                if st['n_on'] >= hold:
                    st.update(on=True, n_on=0, n_off=0)
            flag[kk] = 1 if st['on'] else 0
        ks = sht_le.range('AA9:AA55').value
        sht_le.range('LO9:LO55').value = [[flag.get(round(k), 0) if isinstance(k, (int, float)) else 0] for k in ks]
    except Exception as e:
        print(f"   ! VEX-breakout latch skipped ({e})")


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

_vlatch = set()
_status_prev = {}      # 2026-10-03: last archived unsafe flag per strike (status_chg)
_vlatch_st = {}          # 2026-10-02: per-level on/off counters for the 2-cycle latch
_vlatch_day = None


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
# All time logic is ET wall-clock (EDT or EST from the CLOCKS rules, 2026-09-29).
# NOTE: this is summer (EDT). In winter the offset is UTC-5; the -4 here mirrors
#       the existing market_open() convention and should be changed together with it.

def et_now():
    """Current time as a naive ET datetime (EDT or EST -- see CLOCKS)."""
    return utc_to_et(datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))


def to_et(t):
    """Coerce an IBKR timestamp (epoch int or tz-aware/naive datetime) to naive ET."""
    if isinstance(t, (int, float)):
        t = datetime.datetime.fromtimestamp(t, datetime.timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return utc_to_et(t.astimezone(datetime.timezone.utc).replace(tzinfo=None))


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


def prior_tpo_refresh(ib_, spx_contract):
    """Build yesterday's SPX TPO profile from 1-min RTH bars, once per ET day (retry every
       5 min on failure). Never raises; on failure the rows just show '--'."""
    today = et_now().date()
    if _prior_tpo['for_day'] == today or time.time() - _prior_tpo['tried'] < 300:
        return
    _prior_tpo['tried'] = time.time()
    try:
        bars = ib_.reqHistoricalData(spx_contract, '', '5 D', '1 min', 'TRADES',
                                     useRTH=True, formatDate=2)
    except Exception as e:
        print(f"   ! prior-day SPX profile: history request failed ({e})")
        return
    by_day = {}
    for b in bars or []:
        t = to_et(b.date)
        if t.date() >= today:
            continue
        by_day.setdefault(t.date(), []).append((t, float(b.high), float(b.low)))
    if not by_day:
        print("   ! prior-day SPX profile: no completed session in the history window")
        return
    day = max(by_day)
    poc, vah, val = tpo_levels(tpo_brackets(by_day[day]))
    _prior_tpo.update(date=day, poc=poc, vah=vah, val=val, for_day=today)
    print(f"Prior-day SPX TPO ({day}): POC {poc}  VAH {vah}  VAL {val}")


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
    # prior-day levels are SPX (30-min TPO), not ES -- the status says so
    _ptag = (f"SPX TPO {_prior_tpo['date'].strftime('%d %b')}" if _prior_tpo['date'] else 'SPX TPO --')
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
        ('Prior POC',       _prior_tpo['poc'], 'tk', _ptag),
        ('Prior VAH',       _prior_tpo['vah'], 'tk', _ptag),
        ('Prior VAL',       _prior_tpo['val'], 'tk', _ptag),
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
_prox_strike, _prox_miss = None, 0   # PROX no-skip admission latch (strike, consecutive-miss count)

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
        _sq_since = datetime.datetime.now().strftime("%H:%M")
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
    _hm = datetime.datetime.now().strftime("%H:%M")
    if updown and _sv_ud_since is None:
        _sv_ud_since = _hm                    # day marker: set once, never cleared

    ds = [_sv_spot[i + 1] - _sv_spot[i] for i in range(len(_sv_spot) - 1)]
    dv = [_sv_v1d[i + 1] - _sv_v1d[i] for i in range(len(_sv_v1d) - 1)]
    c = _pearson(ds, dv) if len(ds) >= SV_CORR_WIN else None
    _sv_corr = c
    _sv_run = _sv_run + 1 if (c is not None and c > SV_CORR_MIN) else 0

    if _sv_run >= SV_CORR_HOLD and _sv_push_since is None:
        _sv_push_since = _hm

    # LIVE READINGS ONLY. Changed 2026-08-19.
    #
    # This line used to lead with the SESSION-OPEN test -- spot above its open AND
    # VIX1D above its open -- under the headline "SPOT UP / VOL UP". That reads as a
    # live co-movement alert and is not one: it is two levels compared with where
    # they started, it goes true on any gap up that drags the front end with it, and
    # it then stays true all session regardless of what vol does afterwards. On
    # 2026-08-19 it read SPOT UP / VOL UP from 14:32 to the close while the actual
    # 10-minute co-movement test was dark for all but a handful of cycles.
    #
    # The headline now belongs to the 10-minute test below, which is a real
    # co-movement measurement and writes nothing when it is not firing.
    #
    # The session-open flag itself is UNCHANGED and still archived as sv_updown --
    # backtests read that column. It simply no longer renders.
    #
    # No lapsed forms on this line any more. A lapsed marker is a record of the day,
    # not a state, and mixing the two on one line is what made this ambiguous in the
    # first place. Both "spot up / vol up earlier today..." and "vol rose with every
    # push earlier today..." are gone; each reading now shows or it does not.
    parts = []
    if _sv_run >= SV_CORR_HOLD:
        parts.append(f"VOL RISING WITH EVERY PUSH — call buying is driving "
                     f"the move (rare · {c:+.2f} · since {_sv_push_since})")

    # Second reading: 10-minute spot / TERM-VIX sign test. Independent of the
    # correlation reading above -- that runs on VIX1D and stayed dark through the
    # 2026-08-13 advance because the front end fell from its open while the term
    # VIX rose. This test now carries the SPOT UP / VOL UP headline.
    _svx_d, _svx_txt = spot_vix_sign(spot, vix, datetime.datetime.now(), datetime.datetime.now().strftime("%H:%M"))
    if _svx_txt:
        parts.append(_svx_txt)
    return "   ·   ".join(parts), updown, c
VOLT_PROM = 10.0          # the high must be >= this %% above the prior low (a real bid)
_v1d_lo = _v1d_hi = None  # running session extremes
_v1d_lo_t = _v1d_hi_t = ""
_v1d_hi_prom = 0.0        # how much of a bid built the current high (%% above prior low)
_v1d_top_since = None     # HH:MM the VOL TOP condition first armed; set once, never cleared
GEX_SEED_HISTORY = True   # rebuild the buffer from today's archive CSV at startup
_gex_hist   = deque(maxlen=GEX_SLOPE_WIN + 1)   # (epoch_secs, net_gex) per cycle
_gex_open5  = None        # NET GEX at RTH open+5 (09:35 ET); baseline for the Master 'vs open+5' readout
_gex_sign   = 0           # last committed sign: +1 pos, -1 neg, 0 unset
_gex_per15  = None        # published slope, net GEX change per 15 min (None until the window fills)
_gex_flip_t = None        # epoch secs of the most recent sign flip (None = none yet)
# ---- GEX SLOPE sign-flip tracking (added 2026-07-27) ----
# Separate from _gex_sign/_gex_flip_t above, which track the NET GEX sign. These track
# the sign of the SLOPE itself (per15). Both are surfaced on the dashboard line and are
# explicitly labelled there ("slope flipped ..." vs "Net GEX flipped ...") because they
# routinely disagree -- the slope can turn positive while Net GEX is still deeply
# negative, which is exactly the state that was unreadable before.
_slope_sign   = 0         # last committed slope sign: +1 pos, -1 neg, 0 unset
_slope_flip_t = None      # epoch secs of the most recent slope sign flip (None = none yet)

# ---- GEX SLOPE TAPE (Master Dashboard line directly under GEX SLOPE) ----
# One glyph per 5-minute bucket, oldest left, newest right. Three independent
# encodings, so the line can be read at a glance without decoding a number:
#   colour = SIGN of the slope in that bucket   (green positive / purple negative)
#   glyph  = MAGNITUDE, tiered against the WHOLE SESSION so far (see below)
#   suffix = change vs the previous bucket: + grew, - faded, * flat
# The bucket's value is the LAST published slope inside the window (state at the
# 5-minute close), not the mean -- the tape is a sequence of closes, like a chart.
#
# TIERING IS SESSION-WIDE, DISPLAY IS A ROLLING WINDOW. Every bucket of the day
# feeds the quintile edges; only the last TAPE_SHOW are drawn. That combination is
# deliberate: a rolling tier basis would rescale a quiet afternoon back up to full
# size and make it look like the morning's violence, while a full-session strip is
# too narrow to read. Tier meaning is therefore stable all day; width stays legible.
#
# Colour cannot come from conditional formatting: Excel applies one font colour to a
# whole formula result. The line is written as a VALUE and coloured per character.
TAPE_BUCKET_SECS = 300          # 5-minute buckets
TAPE_SHOW        = 24           # buckets drawn (last 2 hours); ALL are kept for tiering
TAPE_FLAT_PCT    = 10.0         # |change| under this vs the previous bucket reads flat
TAPE_TICK        = 6            # a half-hour separator every N buckets
TAPE_GLYPHS      = "\u2581\u2583\u2585\u2587\u2588"   # weakest -> strongest, one font throughout
TAPE_SEP         = "\u2502"     # half-hour tick
TAPE_GAP         = "\u254e"     # feed gap: the slope window restarted here
TAPE_LIVE        = "\u25c4"     # the rightmost bucket is still filling
# Colour carries TWO things at once: hue = sign of the slope, shade = whether the move
# is growing or fading. Flat gets its own colour rather than inheriting the previous
# bucket's, so a stalled slope stays visible instead of reading as a continuation.
TAPE_POS_UP  = (0x15, 0x80, 0x3D)   # dark green   — positive, growing
TAPE_POS_DN  = (0x4A, 0xDE, 0x80)   # light green  — positive, fading
TAPE_NEG_UP  = (0x6D, 0x28, 0xD9)   # dark purple  — negative, growing
TAPE_NEG_DN  = (0xC4, 0xB5, 0xFD)   # light purple — negative, fading
TAPE_FLAT    = (0xFF, 0xD9, 0xA0)   # peach — flat (the zomma-weakening peach)
TAPE_MARK    = (0x80, 0x80, 0x80)   # half-hour ticks and the live marker
TAPE_GAP_RGB = (0xB4, 0x53, 0x09)   # feed-gap break
_tape        = {}     # bucket id (epoch // TAPE_BUCKET_SECS) -> slope at that bucket's close
_tape_order  = []     # bucket ids in chronological order
_tape_gap    = set()  # bucket ids where the slope window restarted (recentre / reconnect)
_tape_last   = None   # last (text, spans) written; the repaint only runs when it changes

# resistance-warning hysteresis (amber/watch border hold) — state persists across cycles
_warn_tier  = 0           # latched tier: 0 off, 1 WATCH, 2 AMBER/CONFIRMED
_warn_below = 0           # consecutive cycles the drivers have sat below the latched tier

# neg-γ UNSAFE per-row raspberry hysteresis (6 reaction rows: R1-R3, S1-S3) — state persists across cycles
_negg_active = [False] * 6
_negg_below  = [0] * 6

# Flip resistance gate hysteresis (Family B) — state persists across cycles.
# Raw gate lives in Level Engine EL8 (gateQual + shelfTop=maxGEX + Neg regime, recomputed
# every cycle); EL7 (gateToDest, which EM/CU/BT/A and the KNM consumers read) is now the
# LATCHED copy written here. Fires the instant EL8=1; after EL8 drops, holds wh cycles
# (CT12, shared with the amber/UNSAFE holds) before clearing, so a shelf hovering at the
# 10pt-width / 5x-strength bars can't blink the Flip in and out of the reaction table.
_flip_gate_active = False
_flip_gate_below  = 0

# Min-GEX node lock (Family A) -- KNM T23 (the min-GEX strike, read by CU/BT and the
# ladder AK2 marker) flip-flopped for single cycles when two strikes' GEX ran nearly
# tied (2026-07-24 14:56:29: 7350 for one cycle, then back to 7400). The raw argmin
# now lives in KNM V23; T23 is the LOCKED copy written here. Reuses apply_sw_lock:
# a challenger strike must persist SW_LOCK_HOLD (3) cycles in a row before T23 moves.
_t23_lock = None; _t23_pend = None


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

def apply_flip_gate_hysteresis(raw, hold):
    """1 while the latched Flip gate should stand, else 0. Mirrors apply_negg_hysteresis:
       instant-on, re-trigger during the hold resets the counter, clears after `hold`
       consecutive cycles with the raw gate off."""
    global _flip_gate_active, _flip_gate_below
    if raw:
        _flip_gate_active = True;  _flip_gate_below = 0
    elif _flip_gate_active:
        _flip_gate_below += 1
        if _flip_gate_below >= hold:
            _flip_gate_active = False; _flip_gate_below = 0
    return 1 if _flip_gate_active else 0

# ---- negative-GEX wall box: arm-and-hold latch (Family B, 2026-07-30) ----
# The raw box node lives in Level Engine EO2: the largest-|gamma| strike below spot that
# carries NEGATIVE GEX, restricted to the locked S1-S3 that clear the support gate (DM).
# That gate switches OFF the moment price arrives -- on 2026-07-30 price sat inside the
# 7370-7375 box on 11 cycles and the raw node was absent on ALL 11, so an instantaneous
# box can never fire. This latch ARMS on the first raw offer, HOLDS the node through the
# loss of qualification, and releases only on a confirmed break (spot below the box floor
# by more than BG9) -- which is exactly the cut the setup is defined by.
BOX_FLOOR_PTS    = 5.0    # box depth below the node
BOX_MIGRATE_HOLD = 3      # cycles a DIFFERENT node must persist before the held box moves
_box_node = None          # latched node strike, or None when unarmed / failed
_box_pend = None          # (challenger_strike, consecutive_count) or None

def apply_box_latch(raw_node, spot, bg9):
    """Latched nGex-wall box node. Returns the held strike, or None when unarmed.
         raw_node None   -> HOLD whatever is latched (this is the qualification flicker)
         confirmed break -> clear (setup failed; the cut has already been signalled)
         different node  -> migrate only after BOX_MIGRATE_HOLD consecutive cycles
       After a break the node sits ABOVE spot, so the raw side cannot re-offer it as a
       support node until price reclaims it -- no dead-node bookkeeping needed."""
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


# ---- GEX SLOPE sign-flip latch ----
# Shared by the live monitor and the restart seed so both paths commit identical state
# -- duplicating this logic in the replay is how the two would silently diverge.
def _slope_latch(per15, secs):
    """Track the slope sign and stamp the moment it flips, in either direction.
         per15 > 0 / < 0 -> commit that sign; stamp if it differs from the last one
         per15 == 0      -> hold current state
       The first observation of a session commits a sign WITHOUT stamping: if the
       engine starts with the slope already positive we do not know when it crossed,
       and an invented age is worse than no marker. Same convention as the net-GEX
       flip, which also refuses to stamp its first read. A restart re-seeds both from
       today's archive (see seed_gex_history), so the age survives a reconnect."""
    global _slope_sign, _slope_flip_t
    s = 1 if per15 > 0 else (-1 if per15 < 0 else _slope_sign)
    if s != 0 and s != _slope_sign:
        if _slope_sign != 0:              # a genuine cross, not the first read
            _slope_flip_t = secs
        _slope_sign = s
    return _slope_flip_t


def _tape_fold(per15, secs):
    """Fold one published slope reading into its 5-minute bucket. Called from both
       gex_monitor (live cycles) and seed_gex_history (restart replay), so a restart
       rebuilds the whole day's tape rather than starting the tiering from scratch.
       Later cycles in the same bucket overwrite earlier ones: the bucket carries its
       CLOSE."""
    b = int(secs // TAPE_BUCKET_SECS)
    if b not in _tape:
        _tape_order.append(b)
    _tape[b] = per15


def tape_line():
    """Build the tape as (text, spans). spans is a list of (start, length, rgb) with
       1-based character starts, ready to hand straight to Excel's Characters().

       Every drawn token -- bar, half-hour tick, gap break, live marker -- is exactly one
       character and they are joined by single spaces, so token k always begins at
       len(head) + 2*k. That is what keeps the colouring arithmetic trivial even though
       the markers make the line variable-length in bucket terms."""
    if not _tape_order:
        return "GEX TAPE  \u2026 building", []
    mags = sorted(abs(_tape[b]) for b in _tape_order)   # whole session, not the window
    n = len(mags)
    edges = [mags[min(int(q * n), n - 1)] for q in (0.2, 0.4, 0.6, 0.8)]
    # The top-tier edge is published in the label so the tallest bar has a known value.
    # It rises through the session as bigger buckets arrive; that is the tiering working,
    # not drift.
    head = f"GEX TAPE  max {edges[3] / 1e6:.1f}M  "

    first = max(0, len(_tape_order) - TAPE_SHOW)
    toks = []                       # (char, rgb)
    for i in range(first, len(_tape_order)):
        b = _tape_order[i]
        if b in _tape_gap and i > first:
            toks.append((TAPE_GAP, TAPE_GAP_RGB))
        elif i > first and (i - first) % TAPE_TICK == 0:
            toks.append((TAPE_SEP, TAPE_MARK))
        v = _tape[b]
        m = abs(v)
        tier = sum(1 for e in edges if m > e)
        prev = _tape[_tape_order[i - 1]] if i > 0 else None
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
    spans = [(base + 2 * k, 1, rgb) for k, (_, rgb) in enumerate(toks)]
    return text, spans


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

# ---- ATM IV history for the compression reading on the GEX SLOPE line ----
# Timestamped deliberately. _atmiv_hist elsewhere holds bare floats with no clock, which
# is fine for a two-half direction but cannot produce a per-15-min rate. This buffer
# mirrors _gex_hist so the GEX and IV rates are measured over the SAME window -- the
# pairing is the whole point of the reading and comparing two different windows would
# quietly misstate it. Added 2026-08-25.
_ivline_hist = deque(maxlen=64)
IV_FLAT_PP15 = 0.05      # pp/15m deadband; below this IV counts as flat, not moving
GEX_FLAT_M15 = 0.25e6    # GEX/15m deadband, same purpose


# ---- Net GEX intraday monitor ----
# Folds the current whole-book Net GEX into the rolling history, then returns one
# formatted summary line for the dashboard: normalised 45-min slope, sign-flip +
# age, and (observation-only) a vol-bid tension flag. Never a trade trigger.
def gex_monitor(net_gex, now_secs, vix1d_up, vvix_up, atm_iv=None):
    """net_gex   : current whole-book Net GEX (sum of per-strike GEX)
       now_secs  : time.time() epoch seconds for this cycle
       vix1d_up  : bool, Front-End Bidding active (King Node Model P6 == 'Up')
       vvix_up   : bool, VVIX rising (King Node Model P5 == 'Up')
       Returns a display string, e.g.
         'GEX SLOPE  ▲ +3.8M/15m  ·  slope flipped POS 43m ago  ·  '
         'Net GEX flipped NEG 248m ago  ·  ⚠ vol-bid tension' """
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
        _slope_latch(per15, now_secs)
        _tape_fold(per15, now_secs)

    # --- #2 flip text: SLOPE first, then NET GEX, each explicitly labelled ---
    if _slope_flip_t is not None:
        slope_flip_txt = (f"slope flipped {'POS' if _slope_sign > 0 else 'NEG'} "
                          f"{int((now_secs - _slope_flip_t) / 60)}m ago")
    elif _slope_sign:
        slope_flip_txt = f"slope {'POS' if _slope_sign > 0 else 'NEG'} held all session"
    else:
        slope_flip_txt = ""

    if _gex_flip_t is not None:
        mins = int((now_secs - _gex_flip_t) / 60)
        flip_txt = f"Net GEX flipped {'POS' if _gex_sign > 0 else 'NEG'} {mins}m ago"
    else:
        flip_txt = (f"Net GEX {'POS' if _gex_sign > 0 else 'NEG'} held all session"
                    if _gex_sign else "Net GEX —")

    line = slope_txt
    if slope_flip_txt:
        line += f"  ·  {slope_flip_txt}"
    line += f"  ·  {flip_txt}"

    # --- #3 vol-bid tension flag (observation only; no direction implied) ---
    if rising and vix1d_up and not vvix_up:
        line += "  ·  ⚠ vol-bid tension"

    # --- #4 compression reading: GEX rate vs ATM IV rate, in plain English ---
    # Dealers' cushion is net gamma; fear is ATM IV. The four sign combinations mean
    # four different things, and on the dashboard as it stood they all looked alike --
    # GEX was on this line, IV was several rows away in the IV band, and the reader had
    # to hold one in their head while reading the other.
    #
    # OBSERVATION ONLY. This states what the two rates are doing together, nothing more.
    # It does NOT imply a breakout: growing cushion with fading fear is a COMPRESSION
    # reading -- dips get bought back toward the node and moves are damped. Direction
    # belongs to the phenomenon line, not here.
    if isinstance(atm_iv, (int, float)) and atm_iv > 0:
        _ivline_hist.append((now_secs, float(atm_iv) * 100.0))   # store as percentage points
    if len(_ivline_hist) >= 2 and _gex_per15 is not None:
        _t0, _iv0 = _ivline_hist[0]
        _dt = max((now_secs - _t0) / 60.0, 0.5)
        _iv_now = _ivline_hist[-1][1]
        _iv15 = (_iv_now - _iv0) / _dt * 15.0            # pp per 15 min
        _iv_arrow = ("▲" if _iv15 > IV_FLAT_PP15
                     else "▼" if _iv15 < -IV_FLAT_PP15 else "▬")
        line += f"  ·  ATM IV {_iv_now:.1f}% {_iv_arrow} {_iv15:+.2f}pp/15m"

        _g_up = _gex_per15 > GEX_FLAT_M15
        _g_dn = _gex_per15 < -GEX_FLAT_M15
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


def seed_flow_history():
    """Rebuild the MELT-UP / FLOW history from today's archive at startup (2026-09-24),
       so the 15m, 1h and melt-up readings are live on the first cycle after a restart
       instead of "building". Reads every archive file for today (base and __vN), sums
       the per-strike call/put volume per cycle, and folds each cycle through the SAME
       mu_step() the live loop uses, on the archived clock. Failure never blocks startup;
       the lines just accumulate live."""
    import glob as _glob
    day = f"{datetime.date.today():%Y-%m-%d}"
    paths = sorted(_glob.glob(os.path.join(ARCHIVE_DIR, f"king_node_archive_{day}*.csv")))
    if not paths:
        return 0
    cyc = {}
    _num = lambda v: (lambda x: x if x == x else None)(float(v)) if v not in (None, "") else None
    try:
        for p in paths:
            with open(p, newline="", encoding="cp1252", errors="replace") as f:
                for row in csv.DictReader(f):
                    ts = row.get("timestamp")
                    if not ts:
                        continue
                    c = cyc.get(ts)
                    if c is None:
                        try:
                            c = cyc[ts] = {"spot": _num(row.get("spot")), "iv": _num(row.get("atm_iv")),
                                           "v1d": _num(row.get("vix1d")), "vix": _num(row.get("vix")),
                                           "cd": 0.0, "pd": 0.0, "cc": None, "pc": None,
                                           "mvk": None, "mvv": None}
                        except ValueError:
                            continue
                    try:    # 2026-10-01: Min VEX strike per cycle (most negative VEX) for the melt-up watch
                        _vx, _kx = _num(row.get("vex")), _num(row.get("strike"))
                        if _vx is not None and _kx is not None and (c["mvv"] is None or _vx < c["mvv"]):
                            c["mvv"], c["mvk"] = _vx, _kx
                    except ValueError:
                        pass
                    for k, col in (("cd", "call_vol_d"), ("pd", "put_vol_d"),
                                   ("cc", "call_vol"), ("pc", "put_vol")):
                        try:
                            v = _num(row.get(col))
                        except ValueError:
                            v = None
                        if v is not None and vol_sane(v, delta=(k in ("cd", "pd"))):   # skip archived sentinels
                            c[k] = (c[k] or 0.0) + v
    except Exception as e:
        print(f"   ! flow history seed read failed ({e}); will accumulate live only")
        return 0
    mu_reset()
    n = 0
    for ts in sorted(cyc):
        try:
            secs = datetime.datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            continue
        c = cyc[ts]
        mu_step(secs, c["spot"], c["iv"], c["v1d"], c["vix"], c["cd"], c["pd"], c["cc"], c["pc"],
                minvex=c.get("mvk"))
        iv_top_step(secs, c["iv"])
        iv_fast_step(secs, c["iv"])
        n += 1
    return n


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
        with open(path, newline="", encoding="cp1252", errors="replace") as f:
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
            _tape_gap.add(int(secs // TAPE_BUCKET_SECS))   # tape draws a break here
        ng = round(per_cycle[ts])
        _gex_hist.append((secs, ng))
        cur = 1 if ng > 0 else (-1 if ng < 0 else _gex_sign)
        if cur != 0 and cur != _gex_sign:
            if _gex_sign != 0:
                _gex_flip_t = secs
            _gex_sign = cur
        # replay the SLOPE sign the same way, through the shared latch, so
        # "slope flipped ... Xm ago" survives a mid-session restart instead of
        # restarting from scratch. Computed exactly as gex_monitor does it.
        if len(_gex_hist) >= 2:
            _t0, _g0 = _gex_hist[0]
            _p15 = (ng - _g0) / max((secs - _t0) / 60.0, 0.5) * 15.0
            _slope_latch(_p15, secs)
            _tape_fold(_p15, secs)          # rebuilds the whole day's tape on restart
        seeded += 1

    # replay the VIX1D session extremes so VOL BOTTOM / VOL TOP survive a restart
    global _v1d_lo, _v1d_hi, _v1d_lo_t, _v1d_hi_t, _v1d_hi_prom, _v1d_top_since
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
        # Day marker for the VOL TOP lapsed form, so a restart does not lose the
        # record that vol topped earlier. The direction term is deliberately NOT
        # applied here: _v1d_dir is a rolling read that this loop cannot rebuild, so
        # the seeded marker uses prominence + fade only. That is marginally looser
        # than the live arm, and it only ever affects the LAPSED text -- the live
        # VOL TOP and the UNSAFE marker it feeds are recomputed from scratch on the
        # first real cycle and are unaffected.
        if _v1d_top_since is None and _v1d_hi and _v1d_hi_prom >= VOLT_PROM:
            if (_v1d_hi - v1) / _v1d_hi * 100 >= VOLT_PCT:
                _v1d_top_since = hm

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
OBS_BRK_CONFIRM = 2   # 2026-09-29 (Giggles): consecutive cycles >= OBS_BRK below to confirm a
                      # break -- a one-cycle poke no longer counts (09-28 15:14:49: 7705 "broke"
                      # on a single 7700.05 print, next cycle 7702.02, and fired blue at 15:24)
_obs_pend = {}        # K -> consecutive cycles spot has been >= OBS_BRK below K
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
_cs_lo = _cs_hi = None     # call-side session extremes (STEEP CALL SKEW), 2026-09-24
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

# ---- OPEN VOL RESPONSE -> 'Level Engine'!E3 (Master Dashboard Q6 reads it) ----
# One number per session: ATM IV at the end of the measurement window divided by
# its PEAK inside that window. Measures how much of the opening vol shock the
# market handed back while the window ran.
#
#   window   09:31 -> 10:00 ET  (14:31 -> 15:00 Irish), i.e. the first half hour
#            after the cash open, skipping the opening print itself
#   value    last_in_window / max_in_window   -- always <= 1.0
#
# Bands (Master Dashboard Q6 applies them; do NOT duplicate the thresholds here,
# one source only):  <0.80 Slow Trend | 0.80-0.85 Chop | 0.85-0.95 Ordinary |
# >0.95 Expansion.
#
# WRITE-ONCE BY DESIGN. Nothing is written before the window closes, so E3 stays
# empty and Q6 shows an em-dash all morning. At the first cycle at or after 10:00
# ET the ratio is computed, written, and never touched again -- it is a fixed-
# window measurement, and letting it tick afterwards would imply it was still
# taking in new information when it is not. _ovr_done is the latch; it is module
# level so reconnect() (which rebuilds the socket, the tickers and the chain, but
# not this module) cannot silently re-arm it and overwrite a frozen value.
#
# OBSERVATION GRADE. Nothing in the Level Engine or either script reads E3; it
# feeds one display cell. The band boundaries came off a 22-day sample and the
# chop end of the scale rests on two days -- do not gate anything on this until
# it has been pre-registered and re-tested on a larger event count.
OVR_WIN_OPEN  = (9, 31)     # ET, inclusive -- first cycle counted
OVR_WIN_CLOSE = (10, 0)     # ET, exclusive -- window ends, value freezes
_ovr_peak = None            # max ATM IV seen inside the window
_ovr_last = None            # most recent ATM IV seen inside the window
_ovr_done = False           # True once E3 has been written; never re-armed


def open_vol_response(atm_iv, et):
    """Accumulate the window, then freeze. Returns the ratio on the cycle it is
       computed, else None. Safe to call every cycle; a no-op once frozen."""
    global _ovr_peak, _ovr_last, _ovr_done
    if _ovr_done or not atm_iv or atm_iv <= 0:
        return None
    hm = (et.hour, et.minute)
    if hm < OVR_WIN_OPEN:
        return None
    if hm < OVR_WIN_CLOSE:
        _ovr_last = float(atm_iv)
        _ovr_peak = _ovr_last if _ovr_peak is None else max(_ovr_peak, _ovr_last)
        return None
    # window has closed
    _ovr_done = True
    if not _ovr_peak or not _ovr_last:
        return None                      # never saw the window (late start / feed gap)
    return _ovr_last / _ovr_peak


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
    global _ps_lo, _ps_hi, _cs_lo, _cs_hi, _skew_state
    _skew_state = {}                              # cleared each cycle; only a full read refills it
    try:
        calls = [(k, v[0]) for k, v in raw_by_strike.items() if isinstance(v[0], (int, float))]
        puts  = [(k, v[1]) for k, v in raw_by_strike.items() if isinstance(v[1], (int, float))]
        if len(puts) < 3:
            # put IV never arrived from the feed -> say so, do not fake it
            return None, None, None, "SKEW  — no put IV from feed", "n/a", "n/a", []

        atm_c = _interp_iv(calls, spot)
        atm_p = _interp_iv(puts,  spot)
        atm = (atm_c + atm_p) / 2 if (atm_c and atm_p) else (atm_c or atm_p)
        iv_p = _interp_iv(puts,  spot - SKEW_OFF)
        iv_c = _interp_iv(calls, spot + SKEW_OFF)
        if not atm:
            return None, None, None, "SKEW  — building", "…", "…", []

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
                                     (f"{cs:+.1f}vp" if cs is not None else "n/a"), []

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
            _cs_lo = cs_r if _cs_lo is None else min(_cs_lo, cs_r)
            _cs_hi = cs_r if _cs_hi is None else max(_cs_hi, cs_r)

        ps_dir = _two_half_dir(_ps_hist, SKEW_DB) if ps_r is not None else "Flat"
        cs_dir = _two_half_dir(_cs_hist, SKEW_DB) if cs_r is not None else "Flat"

        # "steep" = the residual sits in the top third of today's RESIDUAL range, i.e.
        # unusually put-bid FOR THIS TIME OF DAY. Never the raw level.
        steep = False
        if ps_r is not None and _ps_hi is not None and _ps_lo is not None and (_ps_hi - _ps_lo) > 0.2:
            steep = (ps_r - _ps_lo) / (_ps_hi - _ps_lo) >= SKEW_STEEP_PCT
        # 2026-09-24 FIX: STEEP CALL SKEW could never fire. The branch was gated on
        # `not steep`, and `steep` is the PUT-side test, so the inner `if steep` was always
        # False. The call side now has its own steepness test (call_steep: the call residual
        # in the top SKEW_STEEP_PCT of today's call residual range), mirroring the put test.
        call_steep = False
        if cs_r is not None and _cs_hi is not None and _cs_lo is not None and (_cs_hi - _cs_lo) > 0.2:
            call_steep = (cs_r - _cs_lo) / (_cs_hi - _cs_lo) >= SKEW_STEEP_PCT

        # ---- state machine: EVERY combination must produce a truthful line ----
        # ---- single-sided state machine ----------------------------------------
        # 2026-09-17  The line now shows ONE side only — whichever is dominant —
        # instead of appending both.  The old code concatenated the put state and
        # then conditionally appended "RISING CALL SKEW", so the reader took the
        # last token as the position.  Now the call side REPLACES the put side when
        # its rising direction is the stronger signal and the put side is neutral.
        #
        # Decision rule (unchanged from before): call skew appears only when
        # cs_dir == "Up".  If the put side is already saying something (steep,
        # steepening, flattening), put wins — the call append is suppressed, not
        # shown alongside.  Call wins only when put is neutral AND call is rising.
        #
        # Colour:  steep put / steepening put → RED; flattening put → ORANGE (2026-09-24)
        #          neutral                                      → ORANGE
        #          steep call / rising call                      → GREEN
        #          n/a                                           → no colour
        #
        # Spans follow the tape_paint convention: list of (start, length, rgb),
        # 1-based character positions, tuples are (R, G, B); tape_paint packs them for COM.
        SKEW_RED    = (0xC2, 0x21, 0x18)   # C22118 raspberry red (R,G,B -- was stored reversed and rendered blue until 2026-09-19)
        SKEW_GREEN  = (0x00, 0xB0, 0x50)   # 00B050 green (R,G,B)
        SKEW_ORANGE = (0xFF, 0xA5, 0x00)   # FFA500 orange (R,G,B -- was stored reversed and rendered light blue until 2026-09-19)

        if ps is None:
            skew_label = "PUT SKEW — n/a"
            skew_rgb   = None
        elif cs_dir == "Up" and ps_dir not in ("Down", "Up") and not steep:
            # put neutral, call rising → call side wins
            skew_label = "STEEP CALL SKEW — upside demand building" if call_steep else \
                         "CALL SKEW — upside demand building"
            skew_rgb   = SKEW_GREEN
        elif ps_dir == "Down":
            skew_label = "FLATTENING PUT SKEW — hedging demand easing"
            skew_rgb   = SKEW_ORANGE          # 2026-09-24, Giggles: easing demand is not bearish
        elif steep:
            skew_label = "STEEP PUT SKEW — strong demand for downside protection"
            skew_rgb   = SKEW_RED
        elif ps_dir == "Up":
            skew_label = "STEEPENING PUT SKEW — hedging demand building"
            skew_rgb   = SKEW_RED
        else:
            skew_label = "PUT SKEW NEUTRAL"
            skew_rgb   = SKEW_ORANGE

        head = "SKEW  " + skew_label
        if rr is not None:
            head += f"   (RR {rr:+.1f}vp)"

        # colour spans: paint the label portion (everything after "SKEW  ")
        skew_spans = []
        if skew_rgb is not None:
            _lbl_start = len("SKEW  ") + 1          # 1-based
            _lbl_len   = len(skew_label)
            skew_spans = [(_lbl_start, _lbl_len, skew_rgb)]

        _skew_state = {"ps_dir": ps_dir, "cs_dir": cs_dir, "steep": steep, "rr": rr}
        put_txt  = f"{ps:+.1f}vp {arrow(ps_dir)}" if ps is not None else "n/a"
        call_txt = f"{cs:+.1f}vp {arrow(cs_dir)}" if cs is not None else "n/a"
        return ps, cs, rr, head, put_txt, call_txt, skew_spans
    except Exception as e:
        return None, None, None, f"SKEW  — error ({e})", "n/a", "n/a", []
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
    global _obs_armed, _obs_latch, _obs_prev_S, _obs_broken, _obs_pend
    try:
        if vix and vix1d and float(vix) > 0:
            _obs_ratio.append(float(vix1d) / float(vix))
    except (TypeError, ValueError):
        pass
    _obs_spot.append(spot)
    prev = [s for s in _obs_prev_S if isinstance(s, (int, float))]
    cur  = [s for s in (locked_S or []) if isinstance(s, (int, float))]
    # a break needs OBS_BRK_CONFIRM consecutive cycles at least OBS_BRK below the level.
    # The level must be a support on the cycle the breach starts (it may drop off the
    # list once pierced, so a pending breach is followed even after it leaves).
    for K in list(_obs_pend):
        if spot > K - OBS_BRK:
            del _obs_pend[K]
    for K in set(prev) | set(_obs_pend):                 # breaks judged on prior cycle
        if spot <= K - OBS_BRK and K not in _obs_broken:
            _obs_pend[K] = _obs_pend.get(K, 0) + 1
            if _obs_pend[K] >= OBS_BRK_CONFIRM:
                _obs_broken[K] = True
                del _obs_pend[K]
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
    # A strike present in chain.strikes is not guaranteed to be listed for THIS expiry.
    # Those come back from qualifyContracts with no conId, and reqMktData then raises
    # ValueError ("can't be hashed because no 'conId' value exists"), killing startup.
    # Drop them and carry on with the strikes that did qualify.
    _dropped = sorted({k for (k, _r), c in cons.items() if not getattr(c, 'conId', 0)})
    if _dropped:
        cons = {key: c for key, c in cons.items() if getattr(c, 'conId', 0)}
        sd = [k for k in sd if k not in _dropped]
        print(f"   ! {len(_dropped)} strike(s) not listed for {expiry}, skipped: "
              f"{', '.join(f'{k:.0f}' for k in _dropped)}")
    # Pace requests in batches to avoid IBKR pacing violations (94 simultaneous
    # requests causes silent drops; 20 per batch with 1s gap stays well under the limit)
    tkk = {}
    items = list(cons.items())
    BATCH = 20
    for i in range(0, len(items), BATCH):
        for key, c in items[i:i + BATCH]:
            tkk[key] = ib.reqMktData(c, '100,101', False, False)
        ib.sleep(1)
    return {'center': center, 'strikes': sd, 'cons': cons, 'tk': tkk}


def cancel_window(state):
    for c in state['cons'].values():
        ib.cancelMktData(c)


# ---------------------------------------------------------------------------
# OI STALL DETECTION + PERSISTENT RECOVERY
# ---------------------------------------------------------------------------
# 2026-08-06: strike 7710 reported call_oi == put_oi == 615.0 in every one of the
# session's 647 snapshots. Gamma, dex, vega and IV were live and tracked normally
# throughout, so nothing looked broken. But gex, zomma and vex are all
# call-minus-put differences -- identical OI on both legs cancels them to exactly
# zero. The strike published a false zero GEX all day, sitting between 7715 and
# 7705, and any level qualification that read it read a lie.
#
# A Greeks-subscription retry would not have caught this: the Greeks were fine.
# What failed was one leg's open-interest tick.
#
# Policy (agreed 2026-08-07):
#   * Detect, re-request the affected leg, and keep retrying for the whole session.
#   * NEVER exclude the strike. A stalled strike keeps publishing zeros.
#   * NEVER let a stalled strike stop the engine, delay a write, or interrupt
#     archiving -- every path here is exception-isolated.
OI_STALL_CONFIRM = 3          # consecutive cycles before a strike is flagged
OI_RETRY_STEPS   = ((5, 60), (10, 300), (None, 600))   # (up to attempt N, seconds)

# key: round(strike) -> dict(n, prev, flagged, attempts, next_ts, leg, rule)
_oi_stall = {}


def _oi_retry_gap(attempts):
    """Escalating interval: 1 min for the first 5 tries, then 5 min, then 10 min
       held indefinitely. No cap -- the engine keeps trying all session."""
    for limit, gap in OI_RETRY_STEPS:
        if limit is None or attempts <= limit:
            return gap
    return OI_RETRY_STEPS[-1][1]


def oi_stall_check(k, coi, poi):
    """Update stall state for one strike. Called once per cycle from the strike
       loop, only where the strike has live Greeks. Never raises."""
    try:
        key = round(k)
        st = _oi_stall.setdefault(key, {'n': 0, 'prev': None, 'flagged': False,
                                        'attempts': 0, 'next_ts': 0.0,
                                        'leg': 'P', 'rule': ''})
        prev = st['prev']
        st['prev'] = (coi, poi)

        # Rule B -- a leg is absent while the strike is otherwise live.
        if not coi or not poi:
            rule, leg = 'B', ('C' if not coi else 'P')
        # Rule A -- both legs identical AND frozen since last cycle. A genuine tie
        # is possible but will not sit unchanged; the frozen test is what separates
        # a real tie from one leg's value being mirrored onto the other.
        elif coi == poi and prev is not None and prev == (coi, poi):
            rule, leg = 'A', st['leg']
        else:
            rule, leg = '', ''

        if not rule:
            if st['flagged']:
                print(f"   OI recovered: {key} after {st['attempts']} attempt(s)")
            st.update(n=0, flagged=False, attempts=0, next_ts=0.0, rule='')
            return
        st['n'] += 1
        st['rule'] = rule
        if rule == 'B':
            st['leg'] = leg
        if st['n'] >= OI_STALL_CONFIRM and not st['flagged']:
            st['flagged'] = True
            st['next_ts'] = time.time()      # first retry on the next sweep
            print(f"   ! OI stall: {key} leg {st['leg']} (rule {rule}) "
                  f"- coi {coi} poi {poi}; retrying")
    except Exception as e:
        print(f"   ! oi_stall_check skipped for {k} ({e})")


def oi_recovery_sweep(state):
    """Re-request market data for ONE stalled leg per cycle, round-robin by due
       time. One per cycle keeps this well clear of IBKR pacing limits even when
       several strikes stall at once. Never raises."""
    try:
        now = time.time()
        due = [(st['next_ts'], k) for k, st in _oi_stall.items()
               if st['flagged'] and st['next_ts'] <= now]
        if not due:
            return
        due.sort()
        key = due[0][1]
        st = _oi_stall[key]
        # find the live contract for this strike/leg in the current window
        match = [(kk, rr) for (kk, rr) in state['cons']
                 if round(kk) == key and rr == st['leg']]
        if not match:
            st['next_ts'] = now + _oi_retry_gap(st['attempts'])
            return
        ck = match[0]
        c = state['cons'][ck]
        try:
            ib.cancelMktData(c)
        except Exception:
            pass
        state['tk'][ck] = ib.reqMktData(c, '100,101', False, False)
        st['attempts'] += 1
        st['next_ts'] = now + _oi_retry_gap(st['attempts'])
        # rule A cannot tell which leg is wrong -- alternate on each attempt
        if st['rule'] == 'A':
            st['leg'] = 'C' if st['leg'] == 'P' else 'P'
    except Exception as e:
        print(f"   ! oi_recovery_sweep skipped ({e})")


def oi_stall_snapshot():
    """{strike: 0|1|2} for the archive. 2 == past the first escalation step."""
    try:
        out = {}
        for k, st in _oi_stall.items():
            if not st['flagged']:
                continue
            out[k] = 2 if st['attempts'] > OI_RETRY_STEPS[0][0] else 1
        return out
    except Exception:
        return {}


def oi_stall_count():
    try:
        return sum(1 for st in _oi_stall.values() if st['flagged'])
    except Exception:
        return 0


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


# ---- fragile positive-gamma hold -> Level Engine BG76 (read by BG72) ---------------------
# 2026-09-23. BG72 (fragile pos-gamma: net GEX < BG71, or net + 15-min slope < 0) was a plain
# sheet test and switched every cycle its inputs crossed a line -- 7.4 switches per session over
# 64 archived sessions. Held here like the cluster/edge/cliff holds: ON after BG75 consecutive
# cycles meeting the entry test, OFF only after BG75 consecutive cycles with net GEX >= BG73 AND
# net + slope >= BG74. Any non-positive regime ARMS it (2026-09-24; was: resets it). Matches replay's _precompute_fragile.
# On any failure BG76 is blanked and BG72 falls back to the raw test.
_frag_state, _frag_cnt = False, 0
_frag_pub = None           # 2026-10-01: the value last written to BG76 this cycle (archived as frag_pos)


def _write_fragile_hold(net_gex):
    global _frag_state, _frag_cnt, _frag_pub
    try:
        prm = {'BG71': 1_000_000, 'BG73': 2_000_000, 'BG74': 1_000_000, 'BG75': 2}
        for k in prm:
            try:
                v = sht_le[k].value
                if isinstance(v, (int, float)):
                    prm[k] = v
            except Exception:
                pass
        need = max(1, int(prm['BG75']))
        if sht['A8'].value != 'Pos' or not isinstance(net_gex, (int, float)):
            # 2026-09-24 FIX (matches replay): a non-positive cycle ARMS the fragile state.
            # Positive gamma fresh out of negative gamma is fragile until the EXIT test
            # passes; clearing it here made the first positive cycles after every Neg->Pos
            # flicker read "not fragile" with net GEX near zero.
            _frag_state, _frag_cnt = True, 0
            # 2026-09-24 FIX 2 (matches replay): publish the ARMED state (1), not 0. A8 here is
            # the PREVIOUS cycle's regime; on a Neg->Pos flip the recalc makes A8 Pos while BG76
            # still says 0, which forced BG72 "not fragile" for that cycle. BG72 returns 0 by
            # itself whenever A8 is not Pos, so 1 is harmless in true negative gamma.
            _frag_pub = 1 if sht['A8'].value != 'Pos' else None
            sht_le['BG76'].value = _frag_pub
            return
        proj = net_gex + (_gex_per15 if isinstance(_gex_per15, (int, float)) else 0.0)
        if not _frag_state:
            _frag_cnt = _frag_cnt + 1 if (net_gex < prm['BG71'] or proj < 0) else 0
            if _frag_cnt >= need:
                _frag_state, _frag_cnt = True, 0
        else:
            _frag_cnt = _frag_cnt + 1 if (net_gex >= prm['BG73'] and proj >= prm['BG74']) else 0
            if _frag_cnt >= need:
                _frag_state, _frag_cnt = False, 0
        _frag_pub = 1 if _frag_state else 0
        sht_le['BG76'].value = _frag_pub
    except Exception as e:
        _frag_pub = None
        try:
            sht_le['BG76'].value = None
        except Exception:
            pass
        print(f"   ! fragile hold publish failed ({e}); BG76 blank -> BG72 uses the raw test")


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

# ---- neg-gamma raspberry flags: clear on startup -------------------------------
# CT19:CT24 persist in the saved workbook, so a 1 latched by a previous session
# would paint a border before the first cycle has read anything. Start cold; the
# first cycle re-arms whatever is genuinely unsafe.
try:
    for _i in range(6):
        sht_le['CT' + str(19 + _i)].value = 0
    print("neg-gamma raspberry flags CT19:CT24 cleared at startup")
except Exception as _e:
    print(f"   ! could not clear CT19:CT24 at startup ({_e})")
sht_gd = wb.sheets["GEX Depth"]
try:
    sht_md = wb.sheets["Master Dashboard"]      # neg-gamma UNSAFE cells live here (K32:K34, K37:K39)
except Exception:
    sht_md = None
try:
    sht_rt = wb.sheets["Sheet1"]                # reaction table; AW47/AW48 carry the
except Exception:                               # king-node accelerant label
    sht_rt = None

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
MD_TAPE_CELL  = None
MD_CUSHION_CELL = None
MD_SPOTVOL_CELL = None
MD_SQUEEZE_CELL = None
MD_FLOW_CELLS   = ()     # (15-minute line, session line) -- two rows under squeeze
MD_MELTUP_CELL  = None   # F cell beside the 'Melt-up' label (row 9 on 2026-09-24)
MD_FLOW1H_CELL  = None   # the 1h flow row: third row of the flow block (gex slope +6)
if sht_md is not None:
    try:
        _labels = {}
        # 2026-09-04  range end 34 -> 56.  The scan stopped at row 33, but the
        # reaction-block labels ("NEXT RESISTANCE (above spot)" / "NEXT SUPPORT
        # (below spot)") have been pushed to rows 36 and 43 by successive row
        # inserts above them.  They fell outside the scan, so MD_NEGG_CELLS
        # resolved to () and the CT19:CT24 write loop below ran over an empty
        # list -- the raspberry flags were never written OR CLEARED, and whatever
        # 1s were last saved into the workbook stayed latched permanently.  Rows
        # 40/41 stayed raspberry through a fix to the warning text itself because
        # nothing was ever writing the flag those rows read.
        # First occurrence wins, and rows 10-33 are still scanned first, so the
        # Signs / Skew / GEX SLOPE / Vol split anchors resolve exactly as before.
        for _r in range(10, 56):
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
            # Gamma cushion row -- located by its own label, like Skew, so a row
            # inserted above it cannot misroute the write. Written as a VALUE, so
            # the target must hold no formula: on 2026-08-14 F19 briefly carried
            # the withdrawn ratio formula, and writing over a live formula cell
            # would destroy it permanently with no way back.
            # Spot-vol and squeeze lines. These were HARDCODED at E25/E26 until
            # 2026-08-14, when a row inserted at 19 pushed every line below it down
            # one. The GEX TAPE resolves its target through this probe, so the tape
            # moved to E25 while the hardcoded spot-vol write stayed on E25 -- two
            # writers, same cell, every cycle. The dashboard flickered between
            # "GEX TAPE ..." and "SPOT DOWN / TERM VOL UP ...". The squeeze line at
            # E26 had the identical fault. Both now resolve off MD_ROW_OFFSET like
            # everything else, so a future insert moves them with the rest.
            # Anchored to the GEX SLOPE row, NOT arithmetic off Signs: the old
            # hardcoded E25/E26 were set when two rows had already been inserted
            # above them, so "25 + offset" double-counts and lands two rows low.
            _gsr0 = next((_r for _t, _r in _labels.items()
                          if _t.startswith("gex slope")), None)
            MD_SPOTVOL_CELL = f"E{_gsr0 + 2}" if _gsr0 else None
            MD_SQUEEZE_CELL = f"E{_gsr0 + 3}" if _gsr0 else None
            # FLOW rows (2026-09-24): the two rows under squeeze, same contiguous block
            # under GEX SLOPE (tape +1, spot-vol +2, squeeze +3, flow +4 / +5). Each is
            # written as a VALUE, so a target holding a formula disables that row.
            if _gsr0:
                _fl = []
                for _c in (f"E{_gsr0 + 4}", f"E{_gsr0 + 5}"):
                    try:
                        if str(sht_md[_c].formula or "").startswith("="):
                            print(f"   ! MD probe: {_c} holds a FORMULA - flow row DISABLED")
                            _fl.append(None)
                        else:
                            _fl.append(_c)
                    except Exception:
                        _fl.append(None)
                MD_FLOW_CELLS = tuple(_fl)
                _c = f"E{_gsr0 + 6}"
                try:
                    if str(sht_md[_c].formula or "").startswith("="):
                        print(f"   ! MD probe: {_c} holds a FORMULA - flow 1h row DISABLED")
                    else:
                        MD_FLOW1H_CELL = _c
                except Exception:
                    pass
            # MELT-UP row (2026-09-24): located by its own 'Melt-up' label in column E,
            # which sits ABOVE the row-10 start of the main label scan, so it has its
            # own scan. Value written to F beside it; refused if F holds a formula.
            for _r in range(4, 21):
                if str(sht_md[f"E{_r}"].value or "").strip().lower().startswith("melt-up"):
                    _c = f"F{_r}"
                    if str(sht_md[_c].formula or "").startswith("="):
                        print(f"   ! MD probe: {_c} holds a FORMULA - melt-up row DISABLED")
                    else:
                        MD_MELTUP_CELL = _c
                    break
            else:
                print("   ! MD probe: 'Melt-up' label not found in E4:E20 - melt-up row DISABLED")
            for _nm, _c in (("spot-vol", MD_SPOTVOL_CELL), ("squeeze", MD_SQUEEZE_CELL)):
                try:
                    if str(sht_md[_c].formula or "").startswith("="):
                        print(f"   ! MD probe: {_c} holds a FORMULA - {_nm} write DISABLED")
                        if _nm == "spot-vol": MD_SPOTVOL_CELL = None
                        else: MD_SQUEEZE_CELL = None
                except Exception:
                    pass

            _cush = _labels.get("vol split")
            MD_CUSHION_CELL = f"F{_cush}" if _cush else None
            if MD_CUSHION_CELL:
                try:
                    if str(sht_md[MD_CUSHION_CELL].formula or "").startswith("="):
                        print(f"   ! MD probe: {MD_CUSHION_CELL} still holds a FORMULA "
                              f"- vol split write DISABLED (clear the cell to enable)")
                        MD_CUSHION_CELL = None
                except Exception:
                    MD_CUSHION_CELL = None
            MD_LAYOUT_OK  = True
            # ---- GEX SLOPE TAPE row ----
            # The tape has no label of its own, so it is anchored to the row it belongs
            # to: the line immediately under GEX SLOPE. Unlike every other Master
            # Dashboard line this one is written as a VALUE (character colouring cannot
            # survive a formula), so a misresolved row would PERMANENTLY destroy whatever
            # formula lives there. Two guards, both must pass: the anchor row's text must
            # actually start with "GEX SLOPE", and the target cell must hold no formula.
            _gslope = next((_r for _t, _r in _labels.items()
                            if _t.startswith("gex slope")), None)
            if _gslope is None:
                print("   ! MD probe: 'GEX SLOPE' anchor NOT FOUND - tape line DISABLED")
            else:
                _cand = f"E{_gslope + 1}"
                try:
                    _fx = str(sht_md[_cand].formula or "")
                except Exception:
                    _fx = "="                     # unreadable -> treat as occupied
                if _fx.startswith("="):
                    print(f"   ! MD probe: {_cand} holds a formula - tape line DISABLED")
                else:
                    MD_TAPE_CELL = _cand
            MD_VT_CELL = _vt_resolve(sht_md, range(10, 56))
            print(f"Master Dashboard: layout OK (offset +{MD_ROW_OFFSET}) -> "
                  f"skew to {MD_SKEW_CELL or 'no Skew row (skipped)'}, "
                  f"tape to {MD_TAPE_CELL or 'DISABLED'}, "
                  f"vol tension to {MD_VT_CELL or 'KNM AB17 only'}")
            print(f"Master Dashboard: melt-up -> {MD_MELTUP_CELL or 'DISABLED'}, "
                  f"flow -> {', '.join(c for c in MD_FLOW_CELLS if c) or 'DISABLED'}, "
                  f"flow 1h -> {MD_FLOW1H_CELL or 'DISABLED'}")
            _clear_stale_md_lines(sht_md, (MD_SKEW_CELL, MD_VT_CELL, MD_TAPE_CELL,
                                           MD_CUSHION_CELL, MD_SPOTVOL_CELL, MD_SQUEEZE_CELL,
                                           MD_MELTUP_CELL, *MD_FLOW_CELLS, MD_FLOW1H_CELL))
    except Exception as e:
        print(f"   ! MD layout probe FAILED ({e}) - all Master Dashboard writes DISABLED")
# ---- Neg-gamma UNSAFE reads -> Level Engine CT19:CT24 -------------------------
# TWICE wrong before this cut, both silently:
#   column -- moved L->K on 2026-07-03 when Neg-gamma genuinely sat in K. It has
#             since moved back to L (K is Zomma). The workbook's own RASP CF was
#             corrected L on 2026-08-04; this read was not, so it has been
#             scanning the Zomma text for the word UNSAFE, which never appears.
#   row    -- derived from the "Signs" anchor, which sits ABOVE the reaction
#             block. Rows inserted BETWEEN Signs and the block (2026-08-04)
#             shift the block without shifting the anchor, so the offset stops
#             tracking. Anchored to the block's own labels instead.
# Both failures are silent: the cell resolves, the string just never matches, the
# latch never arms and the raspberry border quietly stops appearing.
# Layout: label row, header row, then 5 display rows. Only the last three of each
# block carry live Neg-gamma formulas -- the first two are inert placeholders.
MD_NEGG_CELLS = ()
if MD_LAYOUT_OK:
    _res = next((_r for _t, _r in _labels.items() if _t.startswith("next resistance")), None)
    _sup = next((_r for _t, _r in _labels.items() if _t.startswith("next support")), None)
    if _res is None or _sup is None:
        print("   ! MD probe: reaction-block labels NOT FOUND - neg-gamma reads DISABLED")
    elif not (0 < _sup - _res <= 12):
        print(f"   ! MD probe: implausible block spacing (res {_res}, sup {_sup}) "
              f"- neg-gamma reads DISABLED")
    else:
        # 2026-09-08  L -> CJ. This used to read column L and test the TEXT for the
        # substring "UNSAFE". That coupled the border to the exact wording: every
        # column move and every rewording broke it silently, and it left no way to
        # suppress a border except by deleting the warning itself. CJ is a 0/1 paint
        # flag computed per row in the workbook (unsafe AND not exempt), so the
        # wording is now free to change without touching behaviour.
        MD_NEGG_CELLS = tuple("CJ" + str(_res + _o) for _o in (4, 5, 6)) + \
                        tuple("CJ" + str(_sup + _o) for _o in (4, 5, 6))
        # Guard: every resolved paint cell must read 0/1. A misresolved row lands on a
        # blank or on text, which this catches; the old check read the column L header
        # text, which no longer has anything to do with where the flag lives.
        _bad = [_c for _c in MD_NEGG_CELLS if sht_md[_c].value not in (0, 1, 0.0, 1.0)]
        if _bad:
            print(f"   ! MD probe: {', '.join(_bad)} do not read 0/1 "
                  f"- neg-gamma reads DISABLED")
            MD_NEGG_CELLS = ()
        else:
            print(f"Master Dashboard: neg-gamma reads -> {', '.join(MD_NEGG_CELLS)}")
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
    global _locked_R, _locked_S, _pend_R, _pend_S, _prox_strike, _prox_miss
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
    global _v1d_lo, _v1d_hi, _v1d_lo_t, _v1d_hi_t, _v1d_hi_prom, _v1d_top_since
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
        # VOL TOP now carries a lapsed form. The live text is what the Master
        # Dashboard vol-regime line turns into "· falling-vol, melt-up possible",
        # and L40:L42 fire "UNSAFE · falling-vol, melt-up" on
        # SEARCH("falling-vol, melt-up", $F$16). Excel's SEARCH is case-INSENSITIVE,
        # so the lapsed wording must not contain that phrase in any casing or the
        # UNSAFE marker would never clear. "topped out" is the deliberate separation
        # -- do not reword it back towards "falling vol" or "melt-up".
        _top_on = (_v1d_hi_prom >= VOLT_PROM and _fade >= VOLT_PCT and _v1d_dir == "Down")
        if _top_on and _v1d_top_since is None:
            _v1d_top_since = _now_hm            # day marker: set once, never cleared
        if _top_on:
            sht['AB14'].value = (f"\u25bd VOL TOP \u2014 vol FALLING, -{_fade:.0f}% down off HoD "
                                 f"{_v1d_hi:.2f} ({_v1d_hi_t}), front-end fading")
        elif _v1d_top_since is not None:
            sht['AB14'].value = (f"vol topped out earlier today, from {_v1d_top_since} "
                                 f"\u2014 not true now")
        else:
            sht['AB14'].value = ""

    # ---- spot / front-end-vol co-movement -> Master Dashboard E25 ----
    # Row 25 is empty and unmerged, so the text spills across the blank cells to
    # its right and no workbook edit is needed. Blank when neither flag is on.
    _sv_txt, _sv_ud, _sv_c = spot_vol_flags(spot, _v1 if isinstance(_v1, (int, float)) else None,
                                            _vx if isinstance(_vx, (int, float)) else None)
    if sht_md is not None:
        if MD_SPOTVOL_CELL:
            sht_md[MD_SPOTVOL_CELL].value = _sv_txt   # probe-resolved, NOT hardcoded

    # ---- ES 5-min SMAs: nudge the forming bar from the cycle in case the tick
    #      stream is thin (delayed futures), then read the levels for panel + archive.
    _es_s200 = _es_s400 = None
    if _es_sma is not None:
        try:
            _es_sma.update(et_now(), _es_profile.last if _es_profile else None)
            _es_s200, _es_s400 = _es_sma.levels()
        except Exception as e:
            print(f"   ! ES SMA update skipped ({e})")

    if PRIOR_TPO_ENABLED:
        try:
            prior_tpo_refresh(ib, spx.contract)
        except Exception as e:
            print(f"   ! prior-day SPX profile skipped ({e})")
        prior_tpo_write(sht_md)
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

    # ---- spot direction token -> King Node Model P13 --------------------------
    # Same rolling window and deadband as the velocity monitor above; the ladder's
    # wall-start suppression rule reads this cell. Flat inside the deadband so the
    # shading does not flicker strike to strike.
    try:
        if _vok and _vel is not None:
            sht['P13'].value = ('Up' if _vel > SPOT_DIR_DB else
                                'Down' if _vel < -SPOT_DIR_DB else 'Flat')
        else:
            sht['P13'].value = 'Flat'
    except Exception as e:
        print(f"   ! spot direction write failed ({e}); P13 left unchanged")
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
    vol_by_strike = {}
    net = dict(Gamma=0, Zomma=0, Dex=0, Vex=0, Vega=0, Vomma=0, Speed=0, Charm=0)
    for k in strikes:
        ct, pt = tk[(k, 'C')], tk[(k, 'P')]
        g = ct.modelGreeks
        if not has_greeks(ct):
            # No call greeks this cycle -> Greeks archive as 0 (unchanged behaviour), but
            # OI and any put IV that DID arrive are still worth keeping.
            raw_by_strike[round(k)] = (iv_of(ct), iv_of(pt),
                                       oi(ct.callOpenInterest), oi(pt.putOpenInterest))
            vol_by_strike[round(k)] = vol_row(k, ct, pt)
            table.append([k, 0, 0, 0, 0, 0, 0, 0, 0]); continue
        iv = g.impliedVol
        cg = greeks(spot, k, T, iv, 'C'); pg = greeks(spot, k, T, iv, 'P')
        coi, poi = oi(ct.callOpenInterest), oi(pt.putOpenInterest)
        oi_stall_check(k, coi, poi)
        # iv is the CALL's IV and is fed to both legs above -- that is existing behaviour
        # and is deliberately NOT changed here. put_iv is captured raw for the record.
        raw_by_strike[round(k)] = (iv, iv_of(pt), coi, poi)
        vol_by_strike[round(k)] = vol_row(k, ct, pt)
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
            sht_le['C3'].value = round(float(_atm_iv), 4)
    except Exception as e:
        print(f"   ! ATM IV direction skipped ({e})")

    # ---- open vol response -> 'Level Engine'!E3 (Master Dashboard Q6) ---------
    # Write-once at the close of the 09:31-10:00 ET window; silent before then and
    # never written again after. Kept in its own try so a failure here cannot take
    # the ATM IV direction (which ~200 cells depend on) down with it.
    try:
        _ovr = open_vol_response(_atm_iv, et_now())
        if _ovr is not None:
            sht_le['E3'].value = round(float(_ovr), 4)
            print(f"   · open vol response {_ovr:.2f} (frozen for the session)")
    except Exception as e:
        print(f"   ! open vol response skipped ({e})")

    # ---- vol split (Master Dashboard, Vol split row) -------------------------
    # MUST stay below the ATM IV block above. _atm_iv is a local of this function
    # and is not assigned until that block runs; placed any earlier this raises
    # UnboundLocalError every cycle -- caught, so the cycle completes and every
    # other line updates, but F19 is never written and the row silently freezes
    # on a stale value. That is exactly what happened on 2026-08-14.
    # Located by its own label, so a row inserted above cannot misroute it, and
    # refused if the target holds a formula.
    if MD_CUSHION_CELL:
        try:
            sht_md[MD_CUSHION_CELL].value = vol_split(
                _atm_iv if isinstance(_atm_iv, (int, float)) else None,
                _v1 if isinstance(_v1, (int, float)) else None,
                datetime.datetime.now())
        except Exception as e:
            print(f"   ! vol split write failed ({e})")


    _ps = _cs = _rr = None
    if SKEW_ENABLED:
        try:
            _ps, _cs, _rr, _sk_head, _sk_put, _sk_call, _sk_spans = skew_monitor(raw_by_strike, spot)
            sht['O11'].value = 'Put skew:'
            sht['P11'].value = _sk_put
            sht['O12'].value = 'Call skew:'
            sht['P12'].value = _sk_call
            sht['AB16'].value = _sk_head
            # ---- Master Dashboard skew line ------------------------------------
            if sht_md is not None and MD_LAYOUT_OK and MD_SKEW_CELL:
                sht_md[MD_SKEW_CELL].value = _sk_head[:155]
                # colour the label portion (red / orange / green)
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

    # ---- per-strike OPEN INTEREST -> King Node Model K/L (Call OI / Put OI) ----
    # 2026-08-08: K28/L28 carry "Call OI"/"Put OI" headers and have done for a long
    # time, but nothing ever wrote the columns -- the ladder write above is A:I only.
    # The Master Dashboard wall-composition panel (P21:R32) reads K/L, so until this
    # existed it was rendering whatever stale values happened to be sitting in the
    # sheet. Stale OI presented as live is exactly the failure the OI-stall work was
    # added to prevent, so the columns are now written every cycle from the same
    # raw_by_strike the Greeks above were built from -- no second data source, no
    # possibility of the panel and the ladder disagreeing.
    #
    # A strike flagged by oi_stall_check writes blank rather than its frozen numbers:
    # a blank cell reads as "no data" in the panel, a frozen one reads as live.
    _oi_block = []
    for _r in smoothed:
        _k = round(_r[0]) if isinstance(_r[0], (int, float)) else None
        _rec = raw_by_strike.get(_k)
        if _rec is None or _oi_stall.get(_k, {}).get('flagged'):
            _oi_block.append([None, None])
        else:
            _oi_block.append([_rec[2], _rec[3]])
    sht[f'K{FIRST_DATA_ROW}'].value = _oi_block
    if len(_oi_block) < MAX_LADDER_ROWS:               # blank stale rows from a wider window
        _r0 = FIRST_DATA_ROW + len(_oi_block)
        _r1 = FIRST_DATA_ROW + MAX_LADDER_ROWS - 1
        sht[f'K{_r0}:L{_r1}'].clear_contents()

    # ---- Net GEX intraday monitor -> King Node Model AB12 (Master Dashboard E21 GEX SLOPE row reads it) ----
    # smoothed row = [strike, gamma, gex, zomma, dex, vex, vomma, vega, speed]; index 2 = GEX.
    net_gex_now = sum(smoothed[i][2] for i in range(len(smoothed))
                      if isinstance(smoothed[i][2], (int, float)))
    _v1d_up = (sht['P6'].value == "Up")          # Front-End Bidding (VIX1D dir)
    _vvx_up = (sht['P5'].value == "Up")          # VVIX dir (confirmation)
    sht['AB12'].value = gex_monitor(net_gex_now, time.time(), _v1d_up, _vvx_up,
                                    _atm_iv if isinstance(_atm_iv, (int, float)) else None)

    # ---- GEX SLOPE TAPE -> Master Dashboard, the line under GEX SLOPE ----
    # MUST run after gex_monitor, which folds this cycle's slope into its bucket.
    # Written as a VALUE, not a formula, because the per-bucket green/purple is
    # character formatting and Excel discards that on a formula result. Repainted
    # only when the rendered line actually changes -- normally once every 5 minutes,
    # not once a cycle, so the COM character calls stay off the hot path.
    global _tape_last
    if MD_TAPE_CELL:
        try:
            _tp_txt, _tp_spans = tape_line()
            if (_tp_txt, _tp_spans) != _tape_last:
                sht_md[MD_TAPE_CELL].value = _tp_txt
                if _tp_spans:
                    tape_paint(sht_md[MD_TAPE_CELL], _tp_spans)
                _tape_last = (_tp_txt, _tp_spans)
        except Exception as e:
            print(f"   ! tape line skipped ({e})")

    # ---- Vol Tension -> King Node Model AB17 (Master Dashboard F18 reads it) ----
    # MUST run after gex_monitor (publishes _gex_per15) and after skew_monitor
    # (publishes _skew_state). Writes AB17 only -- F18 is a formula, so this line
    # needs no Master Dashboard handle and no row offset.
    try:
        _vt_ratio = None
        _vix, _v1d = sht['B5'].value, sht['F5'].value
        if isinstance(_vix, (int, float)) and isinstance(_v1d, (int, float)) and _vix:
            _vt_ratio = float(_v1d) / float(_vix)
        _vt_txt = vol_tension(net_gex_now, _vt_ratio, _v1d_up)
        sht['AB17'].value = _vt_txt
        if MD_VT_CELL and sht_md is not None:
            vt_write(sht_md[MD_VT_CELL], _vt_txt)
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

    # ---- squeeze condition counter -> Master Dashboard E26 ----
    # E26 is the second of the two rows inserted 2026-08-04; like E25 it is empty
    # and unmerged, so the text spills right and no workbook edit is needed.
    # Blank unless all five conditions are true; the count and the full condition
    # vector are archived every cycle regardless.
    _sq_txt, _sq_n, _sq_cond = squeeze_conditions(
        spot, smoothed, sht['B5'].value, sht['F5'].value)
    if sht_md is not None:
        if MD_SQUEEZE_CELL:
            sht_md[MD_SQUEEZE_CELL].value = _sq_txt   # probe-resolved, NOT hardcoded

    # ---- MELT-UP WATCH (Melt-up row) + FLOW (two rows under squeeze), 2026-09-24 ----
    # MUST run after gex_monitor (publishes _gex_per15) and after the ATM IV block.
    # Display + archive only; see the MELT-UP WATCH block for the rule.
    _mu_n = _mu_cond = _fl_c15 = _fl_p15 = ""
    _ivtop = ""
    _ivfast = ""
    # ---- IV-top alert -> Level Engine BG78 / BG79 (2026-09-24) ----
    try:
        _ivtop, _ivtop_hi = iv_top_step(time.time(),
                                        _atm_iv if isinstance(_atm_iv, (int, float)) else None)
        sht_le['BG78'].value = _ivtop
        sht_le['BG79'].value = (round(_ivtop_hi, 4) if isinstance(_ivtop_hi, float) else None)
    except Exception as e:
        print(f"   ! IV-top alert skipped ({e})")
    # ---- FAST ATM IV direction -> Level Engine BG80 (vanna column + vanna warning) ----
    try:
        _ivfast = iv_fast_step(time.time(), _atm_iv if isinstance(_atm_iv, (int, float)) else None)
        sht_le['BG80'].value = _ivfast or None
    except Exception as e:
        print(f"   ! fast IV direction skipped ({e})")
    try:
        _fl_cd = _fl_pd = 0.0
        _fl_cc = _fl_pc = None
        for _vv in (vol_by_strike or {}).values():
            _cv, _pv, _cdd, _pdd = _vv
            if isinstance(_cdd, (int, float)): _fl_cd += _cdd
            if isinstance(_pdd, (int, float)): _fl_pd += _pdd
            if isinstance(_cv, (int, float)): _fl_cc = (_fl_cc or 0.0) + _cv
            if isinstance(_pv, (int, float)): _fl_pc = (_fl_pc or 0.0) + _pv
        _mu_pre = mu_step(time.time(), spot, _atm_iv if isinstance(_atm_iv, (int, float)) else None,
                          sht['F5'].value, sht['B5'].value, _fl_cd, _fl_pd, _fl_cc, _fl_pc,
                          minvex=sht['F24'].value)
        _mu_txt, _mu_n, _mu_cond = meltup_line(
            _mu_pre, spot, (_es_profile.last if _es_profile is not None else None), _es_s200,
            _gex_per15, sht['D27'].value, sht['D26'].value, sht['A8'].value,
            sht_le['BG72'].value, sht['C11'].value, iv_regime=sht['L5'].value)
        _fl_c15 = "" if _mu_pre['c15'] is None else round(_mu_pre['c15'])
        _fl_p15 = "" if _mu_pre['p15'] is None else round(_mu_pre['p15'])
        if sht_md is not None and MD_LAYOUT_OK:
            if MD_MELTUP_CELL:
                sht_md[MD_MELTUP_CELL].value = _mu_txt
                try:    # 2026-09-29: Phenomenon-line grey (595959); 2026-10-07 (Giggles): GREEN while the FLOW SHIFT is on
                    _r, _g, _b = FLOW_GREEN if str(_mu_n).strip() in ("1", "1.0") else FLOW_BASE
                    _mu_font = getattr(sht_md[MD_MELTUP_CELL], "api", sht_md[MD_MELTUP_CELL]).Font
                    _mu_font.Color = _r + (_g << 8) + (_b << 16)
                    _mu_font.Bold = str(_mu_n).strip() in ("1", "1.0")
                except Exception as e:
                    print(f"   ! melt-up colour skipped ({e})")
            _fl_txt = flow_lines(_mu_pre)
            for _i, (_c, _t) in enumerate(zip(MD_FLOW_CELLS, _fl_txt)):
                if _c:
                    flow_paint(_i, sht_md[_c], *_t)
            if MD_FLOW1H_CELL:
                flow_h1_write(sht_md[MD_FLOW1H_CELL], *flow_h1_line(_mu_pre))
    except Exception as e:
        print(f"   ! melt-up / flow skipped ({e})")

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
    _net_charm = net['Charm'] * CHARM_SIGN      # archived; same expression the flag is cut from
    charm_flag = 'Pos' if _net_charm >= 0 else 'Neg'
    sht['H8'].value = charm_flag                         # net charm sign -> Matrix CharmPos(Q)/CharmNeg(P) overlay
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
        sht_le['HC9'].value = (_gex_per15 if isinstance(_gex_per15, (int, float)) else None)
    except Exception as _e:
        print(f"   ! GEX slope publish failed ({_e}); HC9 blank -> slope-gated rules stay dark")
    _write_spd_hold(smoothed)                    # Spd★ 2-cycle hold history -> BG123:BG126 (2026-10-07)
    if SAND_LOCK_ENABLED:                        # SAND✓ support lock -> MB9:MB55 (2026-10-08)
        try:
            sand_lock_step(sht_le, spot, (sht['A8'].value == 'Neg' or sht_le['BG72'].value in (1, 1.0, True)), et_now().date(), [v for v in (sht['AL49:AL51'].value or [])])
        except Exception as e:
            print(f"   ! SAND lock skipped ({e})")
    _write_fragile_hold(net_gex_now)             # fragile pos-gamma hold -> BG76 (read by BG72)
    # ---- level lock: recalc, read raw levels, apply hysteresis, write locked to W ----
    _recalc_full()                                       # full recalc (chain-independent): V (raw levels) + F (vol states) fresh
    _write_shape_hold()                                  # edge/trough two-cycle hold -> HU/HV (shown by the later full recalc)
    _write_peak_hold()    # DEX peak hold -> BG53 (read by BG28)
    _write_cliff_hold()   # dEdge collapse hold -> HZ (read by CZ)

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
        _et_col = sht_le.range('ET9:ET55').value      # vSharp -- support-side DEX tag
        _state_by_strike = {}
        for _s, _an, _ax, _ay, _dt, _et in zip(strikes_col, _an_col, _ax_col, _ay_col,
                                               _dt_col, _et_col):
            if isinstance(_s, (int, float)):
                _state_by_strike[round(float(_s))] = (_an, _ax, _ay, _dt, _et)
    except Exception as e:
        _state_by_strike = {}
        print(f"   ! state-flag read failed ({e}); revflag/ax_vomma/ay_accel/et_vsharp archive blank")
    # ---- qualifying tag + shelf-interior geometry for the archive (read-only) ------
    # 2026-09-18. Archived so the tags can be graded against outcomes later; nothing
    # reads these back. Built HERE, before archive_snapshot() is called -- a helper
    # block placed after its call site is the use-before-def shape check [24] exists
    # for, and it silently kills everything after it in the cycle.
    try:
        _fa_col = sht_le.range('FA9:FA55').value      # qualifying tag as displayed
        _hl_col = sht_le.range('HL9:HL55').value      # trough geometry (any depth)
        _ho_col = sht_le.range('HO9:HO55').value      # trough deep enough to warn
        _hn_col = sht_le.range('HN9:HN55').value      # positive-GEX interior peak
        _hm_col = sht_le.range('HM9:HM55').value      # trough UNSAFE actually fired
        _geo_by_strike = {}
        for _s, _fa, _hl, _ho, _hn, _hm in zip(strikes_col, _fa_col, _hl_col,
                                               _ho_col, _hn_col, _hm_col):
            if isinstance(_s, (int, float)):
                _geo_by_strike[round(float(_s))] = (
                    _fa if isinstance(_fa, str) else "",
                    1 if _hl == 1 else 0, 1 if _ho == 1 else 0,
                    1 if _hn == 1 else 0, 1 if _hm == 1 else 0)
    except Exception as e:
        _geo_by_strike = {}
        print(f"   ! tag/geometry read failed ({e}); qual_tag and the trough columns archive blank")
    # ---- per-strike UNSAFE for the archive (read-only) -----------------------------
    # 2026-09-19. Level Engine HP = flag, HQ = source codes. Built here, before the
    # archive_snapshot() call, for the same use-before-def reason as the block above.
    # The header check keeps an older workbook without these columns from archiving
    # whatever happens to sit in HP/HQ.
    _unsafe_by_strike = {}
    try:
        if str(sht_le['HP8'].value or "").strip() == "unsafeFlag":
            _hp_col = sht_le.range('HP9:HP55').value
            _hq_col = sht_le.range('HQ9:HQ55').value
            for _s, _hp, _hq in zip(strikes_col, _hp_col, _hq_col):
                if isinstance(_s, (int, float)):
                    _unsafe_by_strike[round(float(_s))] = (
                        1 if _hp == 1 else 0,
                        _hq.strip() if isinstance(_hq, str) else "")
        else:
            print("   ! Level Engine HP8 is not 'unsafeFlag'; unsafe/unsafe_src archive blank")
    except Exception as e:
        _unsafe_by_strike = {}
        print(f"   ! unsafe read failed ({e}); unsafe/unsafe_src archive blank")

    # ---- box flag: read the ACTUAL box columns (FB=boxLo / FC=boxHi) --------------
    # 2026-09-18: this used to read AN9:AN55 and call it "box flag (1 = boxed)". AN is
    # revFlag -- the REVERSAL flag -- not a box flag. The consequence was in
    # apply_rs_hysteresis, where box_flags decides `half = 5 if boxed else 0`: the +5 was
    # applied to any REVERSAL-flagged level and never to a genuinely boxed one. On
    # 2026-09-17 that is exactly why 7625 did not flip: revflag went 0 -> 1 at 14:43 as
    # price broke it, so half became 5 and the support-release boundary moved from
    # 7625-3=7622 out to 7625-5-3=7617. Spot bottomed at 7621.32, never reached 7617, and
    # the level stayed support through the break. A level is boxed when it HAS a box:
    # both box edges present and spanning more than a single strike. A gShelf EDGE is one
    # strike and carries no box (FB/FC blank), so it gets half=0 and releases at +/-BG9.
    # 2026-09-23: a CLUSTER member's box (FB/FC) is the whole cluster range, not a
    # two-strike box -- 7740 inside cluster 7725-7745 got half=5 and released at 7732,
    # a line that is neither the level nor the cluster edge. Spot hit 7735.47, 4.5 pts
    # through 7740, and it stayed support. Cluster members (clReport GF=1) now get no
    # allowance and flip at level +/- BG9, like an un-boxed level. Real boxes unchanged.
    box_lo_col = sht_le.range('FB9:FB55').value           # boxLo
    box_hi_col = sht_le.range('FC9:FC55').value           # boxHi
    try:
        cl_col = sht_le.range('GF9:GF55').value           # clReport: 1 = box is a cluster range
    except Exception as e:
        cl_col = [None] * len(strikes_col)
        print(f"   ! cluster flag read failed ({e}); cluster boxes keep the 5-pt allowance")
    box_flags = {}
    for s, _lo, _hi, _cl in zip(strikes_col, box_lo_col, box_hi_col, cl_col):
        if isinstance(s, (int, float)):
            box_flags[float(s)] = (1 if (isinstance(_lo, (int, float))
                                         and isinstance(_hi, (int, float))
                                         and _hi > _lo
                                         and _cl != 1) else 0)

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
    try:
        _qr_pos = (sht['A8'].value == 'Pos') and (sht_le['BG72'].value not in (1, 1.0, True))
    except Exception:
        _qr_pos = False
    raw_R, raw_S = apply_rs_hysteresis(raw_R, raw_S, spot, thr, box_flags,
                                       now=time.time(), pos=_qr_pos, qr=qr_settings(sht_le))  # hold each level's side until price clears its box edge by thr; quick reclaim (2026-10-05)
    # 2026-10-04: reversal-flagged strikes (Level Engine AN, last calc) get the re-adopt carry-over
    try:
        _rev_set = {round(_k) for _k, _a in zip(sht_le.range('AA9:AA55').value, sht_le.range('AN9:AN55').value)
                    if isinstance(_k, (int, float)) and _a in (1, 1.0, True)}
    except Exception:
        _rev_set = set()
    _locked_R, _pend_R = apply_lock(_locked_R, _pend_R, raw_R, spot, 'R', thr, rev=_rev_set)
    _locked_S, _pend_S = apply_lock(_locked_S, _pend_S, raw_S, spot, 'S', thr, rev=_rev_set)
    _locked_R, _locked_S, _pend_R, _pend_S = qr_apply(_locked_R, _locked_S, _pend_R, _pend_S)   # 2026-10-05 quick reclaim
    _locked_R = dedup_levels(_locked_R, raw_R)           # no strike may occupy two slots
    _locked_S = dedup_levels(_locked_S, raw_S)
    _locked_R, _locked_S = force_minvex_R(_locked_R, _locked_S, spot)   # Min VEX = resistance (neg VEX, High IV, above spot)
    _locked_R, _locked_S = force_minvex_S(_locked_R, _locked_S, spot)   # Min VEX = support while dealer vanna BUYS (fast IV)
    sht_le['W9:W14'].value  = [[(_locked_R[i] if i < len(_locked_R) else None)] for i in range(6)]
    sht_le['W18:W23'].value = [[(_locked_S[i] if i < len(_locked_S) else None)] for i in range(6)]
    _write_oedge()               # 2026-09-22: re-run on THIS cycle's lock (side-aware oEdge); matches replay order


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

    # ---- Flip resistance gate hysteresis -> Level Engine EL7 (gateToDest, latched) ----
    # EL8 is fresh from the first _recalc_full() (chain-data dependent only). Written here,
    # BEFORE the recalc below, so the EM/CU/BT/A consumers of EL7 see the latched value
    # within the same cycle. Hold count shared with the amber/UNSAFE borders (wh from CT12).
    try:
        sht_le['EL7'].value = apply_flip_gate_hysteresis(sht_le['EL8'].value == 1, wh)
    except Exception:
        pass

    # ---- min-GEX node lock -> KNM T23 (locked copy of the V23 raw argmin) ----
    # V23 is fresh from the first _recalc_full(); written here, before the recalc below,
    # so T23's consumers (CU/BT valid-level gates, ladder AK2 marker, ↯75% glyph) see the
    # locked strike within the same cycle. A challenger must hold SW_LOCK_HOLD cycles.
    global _t23_lock, _t23_pend
    try:
        _t23_raw = sht['V23'].value
        _t23_raw = round(_t23_raw) if isinstance(_t23_raw, (int, float)) else None
        if _t23_lock is None:
            _t23_lock = _t23_raw          # first cycle of the session: adopt immediately
        else:
            _t23_lock, _t23_pend = apply_sw_lock(_t23_lock, _t23_pend, _t23_raw)
        if _t23_lock is not None:
            sht['T23'].value = _t23_lock  # never blank T23 -- consumers read it every cycle
    except Exception:
        pass

    _recalc_full()                                       # full recalc (chain-independent): refresh displays that read W + CT/CW

    # ---- nGex-wall box arm-and-hold latch -> Level Engine EQ1 (held node) ----
    # Sits AFTER the recalc above, not with the EL7/T23 writes, because EO2 depends on
    # W18:W20 -- written at line ~2622, i.e. after the FIRST _recalc_full(). EO3/EO4 read
    # EQ1 and fall back to the raw EO2, so a failure here degrades to an instantaneous box
    # rather than blanking it. Same auto-recalc reliance as the CT19:CT24 holds below.
    try:
        _box_raw = sht_le['EO2'].value
        _box_raw = round(float(_box_raw)) if isinstance(_box_raw, (int, float)) else None
        sht_le['EQ1'].value = apply_box_latch(_box_raw, spot, sht_le['BG9'].value)
    except Exception as e:
        print(f"   ! box latch failed ({e}); EQ1 left as-is, box falls back to raw EO2")

    # ---- Neg-gamma UNSAFE per-row raspberry hysteresis -> Level Engine CT19:CT24 (Master resolver reads them) ----
    # Shares the hold count wh (from CT12) with the amber border; holds each reaction row's raspberry
    # alert wh cycles after UNSAFE clears so the danger border doesn't flicker. Counters live in Python
    # globals (no extra sheet cells). Read after calculate() so the L neg-gamma formulas are fresh; the
    # raw-UNSAFE term in the resolver covers the current cycle, the held flag carries the persistence.
    # FAIL CLOSED. Before 2026-09-08 this loop was skipped whenever the layout probe
    # failed or resolved no rows -- the six flags were then neither written NOR
    # cleared, and whatever 1s were last saved into the workbook stayed latched
    # permanently. Raspberry painted levels that were not unsafe, no Excel-side edit
    # could clear it, and every row insert above the reaction block re-armed the
    # fault. Silence must mean 0, never "last value".
    if sht_md is not None and MD_LAYOUT_OK and MD_NEGG_CELLS:
        for _i, _lc in enumerate(MD_NEGG_CELLS):
            _unsafe = str(sht_md[_lc].value or '0').strip() in ('1', '1.0')
            sht_le['CT' + str(19 + _i)].value = apply_negg_hysteresis(_i, _unsafe, wh)
    else:
        for _i in range(6):
            _negg_active[_i] = False
            _negg_below[_i]  = 0
            sht_le['CT' + str(19 + _i)].value = 0

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
        _ej = sht_le.range('EJ9:EJ55').value     # brkSupp -- break-suppression veto
        # reaction-table selection layer (added 2026-07-27). Box bounds, the support
        # gate and the support proximity slot -- the inputs that decide whether a
        # qualified level is actually DISPLAYED. See ARCHIVE_HEADER for the label note
        # on DM/DN (both are support-side despite DN8 reading "brkRankR").
        _at = sht_le.range('AT9:AT55').value     # box lo (spot-quantised)
        _au = sht_le.range('AU9:AU55').value     # box hi (spot-quantised)
        _dm = sht_le.range('DM9:DM55').value     # support hold/brk-suppression gate
        _dn = sht_le.range('DN9:DN55').value     # support reaction slot (proximity rank)
        _ef = sht_le.range('EF9:EF55').value     # supExempt (max-pos-GEX exemption)
        # selection-layer completion (added 2026-07-27, second pass). al = the
        # evaluated zomMark gate that dm_supgate ultimately hangs on; bt/ee mirror
        # dn_supslot/ef_supexempt onto the resistance side.
        _al = sht_le.range('AL9:AL55').value     # zomMark 0/1 (ABS(zomma)>=KNM S10)
        _bt = sht_le.range('BT9:BT55').value     # resistance reaction slot
        _ee = sht_le.range('EE9:EE55').value     # resExempt (max-pos-GEX exemption)
        def _v(x): return x if x is not None else ""
        for (_k, _cf, _ag, _rs, _rt, _cuv, _cvv, _bkv, _dhv, _dcv, _czv, _ejv,
             _atv, _auv, _dmv, _dnv, _efv, _alv, _btv, _eev) in zip(
                _aa, _am, _ac, _ar, _bb, _cu, _cv, _bk, _dh, _dc, _cz, _ej,
                _at, _au, _dm, _dn, _ef, _al, _bt, _ee):
            if isinstance(_k, (int, float)):
                qual_by_strike[round(_k)] = (_v(_cf), _v(_ag), _v(_rs), _v(_rt),
                                             _v(_cuv), _v(_cvv), _v(_bkv),
                                             _v(_dhv), _v(_dcv), _v(_czv), _v(_ejv),
                                             _v(_atv), _v(_auv), _v(_dmv),
                                             _v(_dnv), _v(_efv),
                                             _v(_alv), _v(_btv), _v(_eev))
    except Exception as e:
        print(f"   ! qual map read failed ({e}); confl/abs_gamma/ar_score/rank_tag/"
              f"cu_qual/cv_qual/bk/dh/dc/cz/ej_brksupp/at/au/dm/dn/ef/al/bt/ee "
              f"will archive blank")

    # ---- confluence backer tokens, per strike (added 2026-08-24) ----------------
    # Same tokens, same order as the Level Engine Backers column, but built for the
    # whole ladder rather than only the locked levels that column covers. Read-only;
    # a failure here archives blank and never blocks the cycle.
    backers_by_strike = {}
    try:
        # 2026-10-01 (Giggles): REBUILT to mirror the Level Engine confluence count (AM) test
        # for test, so the archived token count equals the archived confl. The old specs used
        # stale tests (Gam on raw rank <= 3, Vex = SELL on either side, Gsh/gSh split, Zsh
        # without the hold, no OI token) and disagreed with confl. Zom now reads JW (zomma
        # size mark AND firming on the fast IV direction). Tokens stay ASCII for the cp1252
        # archive: Dex-dn = Dex-down, gSh = gamma shelf (one token, as the sheet counts it).
        _bk_cols = {_c: sht_le.range(f"{_c}9:{_c}55").value for _c in
                    ("AA", "AG", "AH", "GK", "JV", "AK", "AE", "KG", "KJ", "KK", "KL", "LA", "KY", "BA", "AJ", "AV", "BD", "GZ", "GY",
                     "JX", "BI", "BJ", "BO", "BX", "BY", "CB", "CZ", "DS", "JD")}
        _gl2 = sht_le["GL2"].value
        _pos = (sht["A8"].value == "Pos")
        _one = lambda v: isinstance(v, (int, float)) and v == 1
        for _i, _k in enumerate(_bk_cols["AA"]):
            if not isinstance(_k, (int, float)):
                continue
            _g = lambda c: _bk_cols[c][_i]
            _sd = str(_g("AG") or "").strip().upper()
            if _sd not in ("R", "S"):
                backers_by_strike[round(_k)] = ""
                continue
            _gk, _ah = _g("GK"), _g("AH")
            _iy = str(_g("JV") or "").strip().upper()   # JV = arrival vanna (neg/fragile γ), = IY otherwise
            _jd = str(_g("JD") or "").strip().upper()
            _toks = []
            if _one(_gk) or (_gk in (None, "") and isinstance(_ah, (int, float))
                             and isinstance(_gl2, (int, float)) and _ah <= _gl2):
                _toks.append("Gam")
            if (_sd == "R" and _iy == "SELL") or (_sd == "S" and _iy == "BUY"):
                _toks.append("Vex")
            # 2026-10-02 (Giggles, both regimes): Dex counts only when side-aligned --
            # negative DEX on a resistance, positive on a support (Level Engine AM / C test).
            # Dex-dn (AJ) stays size-only.
            _ae = _g("AE")
            if _one(_g("AK")) and isinstance(_ae, (int, float)) and \
                    ((_sd == "R" and _ae < 0) or (_sd == "S" and _ae > 0)):
                _toks.append("Dex")
            # 2026-10-05 (Giggles): Zom now reads LA (zomma firming on the FAST IV direction now), the
            # same column as the Level Engine confluence count; Spd* = Spd-star, the side-aligned
            # Max/Min Speed strike (KY: Min Speed support / Max Speed resistance), ASCII for cp1252.
            for _lab, _c in (("Zom", "LA"), ("Spd", "BA"), ("Spd*", "KY"), ("Dex-dn", "AJ")):
                if _one(_g(_c)):
                    _toks.append(_lab)
            # 2026-10-03 (Giggles): gDex = isolated DEX at a positive-GEX strike (Level Engine KG).
            # One island counts once: iDex is suppressed where gDex fires (Level Engine AM / C test).
            if _one(_g("AV")) and not _one(_g("KG")):
                _toks.append("iDex")
            if _one(_g("KG")):
                _toks.append("gDex")
            if _one(_g("BD")) or _one(_g("GZ")) or (_one(_g("GY")) and _pos):
                _toks.append("gSh")
            if _one(_g("JX")):          # 2026-10-01: Zsh only when zomma firms on fast IV (JX)
                _toks.append("Zsh")
            for _lab, _c in (("Vxi", "BI"), ("Spi", "BJ"), ("Vgf", "BO"), ("Gxp", "BX"), ("Gfx", "BY"),
                             ("ZG", "CB"), ("dEdge", "CZ"), ("oEdge", "DS")):
                if _one(_g(_c)):
                    _toks.append(_lab)
            if _jd in ("P", "C"):
                _toks.append(_jd + "-OI")
            # 2026-10-03 (Giggles): data-incomplete guard, same as Level Engine AM / C --
            # structure backers next to an empty / half-loaded strike, Gxp on an incomplete strike,
            # and the OI-skew backer with an incomplete strike within 10 pts do not count.
            if _one(_g("KK")):
                _toks = [t for t in _toks if t not in ("Dex-dn", "gSh", "Zsh", "dEdge", "oEdge", "iDex", "gDex", "Vxi", "Spi")]
            if _one(_g("KJ")):
                _toks = [t for t in _toks if t != "Gxp"]
            if _one(_g("KL")):
                _toks = [t for t in _toks if t not in ("P-OI", "C-OI")]
            backers_by_strike[round(_k)] = " ".join(_toks)
    except Exception as e:
        print(f"   ! backers map read failed ({e}); backers will archive blank")
    # ---- PROX no-skip admission (added 2026-07-30) ------------------------------
    # Never let the resistance reaction table jump past a locked-list strike that
    # is nearer to spot, clears both strength floors (AM >= BG20, AC > BG19), and
    # is not absorbed (BK/DH). The nearest such strike gets EN=1 in Level Engine
    # EN9:EN55; BT9 admits EN=1 rows on proximity alone and the KNM Source/Type
    # cells plus the ladder label render the PROX tag. Neg gamma only (the
    # measured regime; 2026-07-20..29 sample). The gap test (>= PROX_MIN_GAP pts
    # to the nearest structurally displayed resistance, own flag excluded) gates
    # ENTRY only -- once latched the strike holds while it stays valid, so the
    # flag cannot oscillate against its own effect on the display. Hard-clears at
    # once when the strike qualifies structurally (CU=1: STRUCT takes over), the
    # regime leaves Neg, the strike flips below spot, or it leaves the
    # (release-damped) locked list; soft wobble in confl/floors/absorption
    # tolerates PROX_MISS_HOLD consecutive failing cycles before release --
    # instant-on / hold-to-clear, same family as the flip gate. One-cycle lag by
    # construction: this runs on the freshly recalced CU/BT of THIS cycle, then
    # writes EN, and Excel re-ranks the table on that write. Read-only
    # degradation: any failure leaves EN unwritten and en_prox archives 0.
    try:
        _reg_neg = (bool(flags_row) and str(flags_row[0]).strip() == "Neg") or sht_le['BG72'].value in (1, 1.0, True)   # 2026-10-09: fragile = negative
        _bg7  = sht_le['BG7'].value
        _bg19 = sht_le['BG19'].value
        _bg20 = sht_le['BG20'].value
        _lockset = {round(float(x)) for x in _locked_R if isinstance(x, (int, float))}
        def _pnum(x):
            return float(x) if isinstance(x, (int, float)) else None
        def _prox_valid(k):
            q = qual_by_strike.get(k)
            if q is None or not isinstance(spot, (int, float)):
                return False
            _cfq, _agq = _pnum(q[0]), _pnum(q[1])
            _bkq, _dhq = _pnum(q[6]), _pnum(q[7])
            if not (_reg_neg and k in _lockset and k > spot):
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
            q = qual_by_strike.get(k)
            return bool(q) and _pnum(q[4]) == 1
        _struct = [k for k, q in qual_by_strike.items()
                   if _pnum(q[17]) is not None and isinstance(spot, (int, float))
                   and k > spot
                   and (_prox_strike is None or k != round(_prox_strike))]
        _near_disp = min(_struct) if _struct else None
        _cands = sorted(k for k in qual_by_strike
                        if _prox_valid(k) and not _prox_cu(k))
        _cstar = _cands[0] if _cands else None
        if _prox_strike is not None:
            _kcur = round(_prox_strike)
            if _prox_cu(_kcur):
                _prox_strike, _prox_miss = None, 0
            elif (not _reg_neg
                  or not (isinstance(spot, (int, float)) and _kcur > spot)
                  or _kcur not in _lockset):
                _prox_strike, _prox_miss = None, 0
            elif not _prox_valid(_kcur):
                _prox_miss += 1
                if _prox_miss >= PROX_MISS_HOLD:
                    _prox_strike, _prox_miss = None, 0
            else:
                _prox_miss = 0
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
    except Exception as e:
        print(f"   ! PROX admission failed ({e}); EN column left as-is, en_prox archives from state")
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

    # ---- pin state (KNM AC24) for the archive ----
    # Read-only, after the recalc, so AC24 reflects this cycle. Excel returns a real bool;
    # normalise to 1/0 and archive blank on any failure rather than blocking the write.
    _pin_state = ""
    try:
        _ac24 = sht['AC24'].value
        if isinstance(_ac24, bool):
            _pin_state = 1 if _ac24 else 0
        elif isinstance(_ac24, (int, float)):
            _pin_state = 1 if _ac24 else 0
        elif isinstance(_ac24, str) and _ac24.strip().upper() in ("TRUE", "FALSE"):
            _pin_state = 1 if _ac24.strip().upper() == "TRUE" else 0
    except Exception as e:
        print(f"   ! pin state read failed ({e}); pin_state will archive blank")

    # ---- zomMark threshold (KNM S10 = Level Engine A15) for the archive ----
    # Read-only, after the recalc. Archived so the per-strike al_zommark flag and the
    # archived |zomma| can be reconciled offline -- the threshold moves cycle to cycle,
    # so |zomma| on its own says nothing about whether the gate fired.
    _s10_zomthr = ""
    try:
        _s10 = sht['S10'].value
        if isinstance(_s10, (int, float)):
            _s10_zomthr = _s10
    except Exception as e:
        print(f"   ! zomMark threshold read failed ({e}); s10_zomthr will archive blank")

    # one stalled leg re-requested per cycle; never blocks the write below
    oi_recovery_sweep(state)

    # Matrix IV regime (KNM L5). Read, never written -- the engine has no say in
    # this classification, it just records what the workbook resolved to. Guarded
    # the same way as the zomMark threshold above: a failed read archives blank
    # rather than blocking the cycle, because a missing observation column must
    # never cost a data cycle.
    def _rd(_cell, _sheet=None):
        try:
            _v = (_sheet or sht)[_cell].value
            return str(_v).strip() if _v is not None else ""
        except Exception:
            return ""

    try:
        _iv_regime = _rd('L5')
        # the chain behind L5, so the archive can say WHICH branch produced it
        _iv_chain = {"override": _rd('L5', sht_md) if sht_md is not None else "",
                     "map":      _rd('P10'),
                     "state":    _rd('P9'),
                     "band":     _rd('J5')}
    except Exception as e:
        _iv_regime, _iv_chain = "", {}
        print(f"   ! Matrix IV read failed ({e}); iv_regime chain will archive blank")

    # Phenomenon as displayed on the Master Dashboard: the VALUE sits in F9, with its
    # label in column E. Read F9 first, then fall back to a column-E label scan so a
    # row insert above this block relocates the read instead of archiving the wrong
    # cell.
    #
    # 2026-08-27: an earlier version of this block scanned column F for the LABEL and
    # read column G beside it. Both are wrong -- the label is in E and the value in F --
    # so the scan never matched and md_phenom archived blank for every row of
    # 2026-08-24 and 2026-08-27. The failure was silent because a miss is supposed to
    # degrade to blank rather than cost a cycle. Hence the explicit warning below: a
    # blank column must never again be indistinguishable from a working one.
    _md_phenom = ""
    if sht_md is not None:
        try:
            # 2026-09-24: label scan FIRST. A row inserted at 9 (the Melt-up row) moved
            # Phenomenon to row 10, and F9 now holds the melt-up line -- reading F9
            # first would archive the melt-up text as the phenomenon.
            if True:
                for _r in range(4, 32):
                    if str(sht_md[f"E{_r}"].value or "").strip().lower().startswith("phenom"):
                        _md_phenom = _rd(f"F{_r}", sht_md)
                        break
                else:
                    print("   ! Phenomenon cell not found (F9 empty, no column-E label); "
                          "md_phenom will archive blank")
        except Exception as e:
            print(f"   ! Phenomenon read failed ({e}); md_phenom will archive blank")

    # king-node accelerant label, read from the reaction table as displayed.
    # 2026-09-19: read from Master Dashboard. It used to read the sheet named "Sheet1",
    # which holds no reaction table (AW47/AW48 are empty there), so kn_accel had been
    # archiving 0 on every cycle. Falls back to Sheet1 only if Master Dashboard is absent.
    _kn_accel = 0
    _kn_sheet = sht_md if sht_md is not None else sht_rt
    if _kn_sheet is not None:
        try:
            # 2026-09-24: anchored to the support block label (+4 / +5 = the first two
            # support reaction rows, AW50/AW51 after the 2026-09-24 inserts). Was
            # hardcoded AW47/AW48, which had already drifted off the rows (AW48/AW49
            # at the time) and read a blank row plus a live one.
            _kn_cells = ("AW47", "AW48")
            if _kn_sheet is sht_md:
                _kn_sup = next((_r for _t, _r in _labels.items()
                                if _t.startswith("next support")), None)
                if _kn_sup is None:
                    raise ValueError("support block label not found")
                _kn_cells = (f"AW{_kn_sup + 4}", f"AW{_kn_sup + 5}")
            _kn_accel = 1 if any(
                str(_kn_sheet[_c].value or "").strip()
                for _c in _kn_cells) else 0
        except Exception as e:
            print(f"   ! king-node label read failed ({e}); kn_accel archives 0")

    # reaction-table rows as DISPLAYED (archive only; see rt_row in ARCHIVE_HEADER).
    # One COM read per column block. None = read failed -> archives "NA".
    _rt_by_strike = None
    if sht_md is not None:
        try:
            import re as _re
            _rt_by_strike = {}
            # 2026-09-22: was hardcoded to E40:E49 / AP40:AP49 with the display rows
            # listed as (40,41,42,47,48,49). A row inserted anywhere above the reaction
            # block (row 11 "Testing Results" on this date) pushes the whole block down
            # and the archive then reads the wrong rows -- silently, since every row
            # still returns a string. Anchored to the same block labels the neg-gamma
            # probe uses; if they did not resolve, the rt columns archive "NA".
            _res_r = _labels.get("next resistance (above spot)") or next(
                (_r for _t, _r in _labels.items() if _t.startswith("next resistance")), None)
            _sup_r = _labels.get("next support (below spot)") or next(
                (_r for _t, _r in _labels.items() if _t.startswith("next support")), None)
            if _res_r is None or _sup_r is None:
                raise ValueError("reaction-block labels not found")
            # 2026-09-24: (3,4,5) -> (4,5,6). The live reaction rows are label +4..+6 (the
            # same rows the CJ paint flags are read from above); +3 is an inert
            # placeholder row and +6, the 3rd slot, was never archived.
            _rows = [_res_r + _o for _o in (4, 5, 6)] + [_sup_r + _o for _o in (4, 5, 6)]
            _first, _last = min(_rows), max(_rows)
            _e_vals = sht_md.range(f'E{_first}:E{_last}').value
            _ap_vals = sht_md.range(f'AP{_first}:AP{_last}').value
            for _i, (_ev, _apv) in enumerate(zip(_e_vals, _ap_vals)):
                _row = _first + _i
                if _row not in _rows:
                    continue
                _txt = str(_ev or "").strip()
                if not _txt:
                    continue
                _rasp = 1 if str(_apv or "").strip() == "RASP" else 0
                for _sk in _re.findall(r"\b(\d{4})\b", _txt.split("(")[0]):
                    _ent = _rt_by_strike.setdefault(int(_sk), ["", "", ""])
                    if _ent[0] == "":
                        _ent[0], _ent[1] = _row, _rasp
                _bm = _re.search(r"\(box\s*(\d{4})\s*[-\u2013]\s*(\d{4})\)", _txt)
                if _bm:
                    _lo, _hi = sorted((int(_bm.group(1)), int(_bm.group(2))))
                    for _sk in range(_lo, _hi + 1, 5):
                        _ent = _rt_by_strike.setdefault(_sk, ["", "", ""])
                        if _ent[2] == "":
                            _ent[2] = _row
        except Exception as e:
            _rt_by_strike = None
            print(f"   ! reaction-table read failed ({e}); rt_row/rt_rasp/rt_boxrow archive NA")

    # ES developing volume profile for the archive (es_last, es_poc, es_vah, es_val).
    _es_prof_arch = None
    if _es_profile is not None:
        try:
            _poc, _vah, _val = _es_profile.poc_va()
            _es_prof_arch = (_es_profile.last, _poc, _vah, _val)
        except Exception as e:
            print(f"   ! ES profile read for archive skipped ({e}); es_* archive blank")

    # ---- DEX drain (positive gamma) with hysteresis -> Level Engine JT ----
    drain_live_step(sht_le, spot, smoothed, sht['A8'].value)

    # ---- vanna override latch -> Level Engine JR (read by the aligned-vanna override JI) ----
    if VLATCH_ENABLED:
        global _vlatch_day
        try:
            if _vlatch_day != et_now().date():
                _vlatch.clear(); _vlatch_st.clear(); _status_prev.clear(); _vlatch_day = et_now().date()
            _vx_by = {round(r[0]): r[5] for r in smoothed if isinstance(r[0], (int, float))}
            _dx_by = {round(r[0]): r[4] for r in smoothed if isinstance(r[0], (int, float))}
            _rv_by = {k_: (1 if v_[0] == 1 else 0) for k_, v_ in _state_by_strike.items()}
            _reg_ok = (sht['A8'].value == 'Neg') or (sht_le['BG72'].value in (1, 1.0, True))
            # 2026-10-02 (Giggles): simplified override -- aligned arrival vanna >= BG94 + DEX aligned >= BG100,
            # on/off after BG101 cycles (see vlatch_step).
            # 2026-10-02 FIX: same direction source as the workbook (IY/JV): BG80 fast IV if set,
            # else D5 = C5 override, else the slow ATM IV direction (B3), else FLAT. Passing the
            # blank fast reading alone made every near-spot level read FLAT while fast IV was building.
            _lat_dir = (str(_ivfast or '').strip().upper() or str(sht_le['C5'].value or '').strip().upper()
                        or str(_atm_iv_dir or '').strip().upper() or 'FLAT')
            # 2026-10-02: call-wall resistances as the workbook flags them (Level Engine JZ)
            _cw = set()
            try:
                for _k, _f in zip(sht_le.range('AA9:AA55').value, sht_le.range('JZ9:JZ55').value):
                    if isinstance(_k, (int, float)) and _f in (1, 1.0, True):
                        _cw.add(round(_k))
            except Exception:
                _cw = set()
            vlatch_step(_vlatch, _vlatch_st, spot, _locked_R, _locked_S, _vx_by, _rv_by, _dx_by, _lat_dir, _reg_ok,
                        _vl_num(sht_le['BG94'].value, 100000), _vl_num(sht_le['BG94'].value, 100000),
                        _vl_num(sht_le['BG9'].value, 3), _vl_num(sht_le['BG100'].value, 100000),
                        max(1, int(_vl_num(sht_le['BG101'].value, 2))),
                        ivtop=sht_le['BG78'].value, near_pts=_vl_num(sht_le['BG98'].value, 5),
                        svuv=sht_le['BG99'].value, callwalls=_cw)
            vlatch_write(sht_le, _vlatch)
        except Exception as e:
            print(f"   ! vanna latch skipped ({e})")

    # ---- 2026-10-05: gDex-rule vanna UNSAFE latch -> Level Engine KO (positive gamma, not fragile) ----
    if GDV_ENABLED:
        try:
            _gdv_pos = (sht['A8'].value == 'Pos') and (sht_le['BG72'].value not in (1, 1.0, True))
            _gdv_dir = (str(_ivfast or '').strip().upper() or str(sht_le['C5'].value or '').strip().upper()
                        or str(_atm_iv_dir or '').strip().upper() or 'FLAT')
            gdv_live_step(sht_le, spot, smoothed, _gdv_pos, _gdv_dir, sht_le['BG78'].value,
                          _vl_num(sht_le['BG98'].value, 5), sht_le['BG99'].value, _locked_R, _locked_S)
        except Exception as e:
            print(f"   ! gDex-rule latch skipped ({e})")
    # ---- 2026-10-07: VEX-breakout take-profit latch -> Level Engine LO (positive gamma, not fragile) ----
    if VB_ENABLED:
        try:
            _vb_pos = (sht['A8'].value == 'Pos') and (sht_le['BG72'].value not in (1, 1.0, True))
            vb_live_step(sht_le, spot, smoothed, _vb_pos, (_ivfast or sht_le['BG80'].value), _locked_R, _locked_S)
        except Exception as e:
            print(f"   ! VEX-breakout latch skipped ({e})")

    # ---- 2026-10-02: per-strike rule flags for the archive (read-only) -----------------
    # Read AFTER the vanna latch write above so JR is this cycle's latch. JR vanna latch, JZ call wall, KC zomma IV direction, JS Min/Max Zomma SAFE. Header-checked
    # so an older workbook without the columns archives blanks instead of whatever sits there.
    _rules_by_strike = {}
    try:
        _hdr = [str(sht_le[c].value or "") for c in ("JR8", "JZ8", "KC8", "JS8")]
        if _hdr[1].startswith("callWall") and _hdr[2].startswith("zomIVarr"):
            _cols4 = [sht_le.range(f"{c}9:{c}55").value for c in ("JR", "JZ", "KC", "JS")]
            for _s, _jr, _jz, _kc, _js in zip(strikes_col, *_cols4):
                if isinstance(_s, (int, float)):
                    _rules_by_strike[round(float(_s))] = (
                        1 if _jr in (1, 1.0, True) else 0,
                        1 if _jz in (1, 1.0, True) else 0,
                        (_kc.strip().upper() if isinstance(_kc, str) else ""),
                        1 if _js in (1, 1.0, True) else 0)
        else:
            print("   ! Level Engine JZ8/KC8 headers not found; vlatch/call_wall/zom_dir/zom_safe archive blank")
    except Exception as e:
        _rules_by_strike = {}
        print(f"   ! rule-flag read failed ({e}); vlatch/call_wall/zom_dir/zom_safe archive blank")

    # ---- 2026-10-03: SAFE source, cleared reasons and SAFE/UNSAFE flips (read-only) ------
    _safe_by_strike = {}
    try:
        if str(sht_le["KH8"].value or "").startswith("safeSrc"):
            _kh = sht_le.range("KH9:KH55").value
            _ki = sht_le.range("KI9:KI55").value
            for _s, _a, _b in zip(strikes_col, _kh, _ki):
                if not isinstance(_s, (int, float)):
                    continue
                _k = round(float(_s))
                _u = (_unsafe_by_strike.get(_k) or ("", ""))[0]
                _prev = _status_prev.get(_k)
                _chg = ""
                if _u in (0, 1) and _prev in (0, 1) and _u != _prev:
                    _chg = "TO_UNSAFE" if _u == 1 else "TO_SAFE"
                if _u in (0, 1):
                    _status_prev[_k] = _u
                _safe_by_strike[_k] = ((_a or "").strip() if isinstance(_a, str) else "",
                                       (_b or "").strip() if isinstance(_b, str) else "", _chg)
        else:
            print("   ! Level Engine KH8 header not found; safe_src/cleared_src/status_chg archive blank")
    except Exception as e:
        _safe_by_strike = {}
        print(f"   ! safe-source read failed ({e}); safe_src/cleared_src/status_chg archive blank")

    # 2026-10-04: reaction-table Neg-γ text per strike for the archive (read-only)
    _rt_text_by = {}
    try:
        _md = wb.sheets['Master Dashboard']
        for _row, _anc in ((45, 'AL42'), (46, 'AL43'), (47, 'AL44'), (52, 'AL49'), (53, 'AL50'), (54, 'AL51')):
            _k = sht[_anc].value
            _txt = _md[f'L{_row}'].value
            if isinstance(_k, (int, float)) and isinstance(_txt, str) and _txt.strip():
                _t = " | ".join(x.strip() for x in _txt.splitlines() if x.strip())
                # the archive is written cp1252 (errors="replace"): spell out symbols cp1252 lacks
                for _a, _b in (("γ", "g"), ("ζ", "zeta "), ("Ⓟ", "(P)"), ("↑", "up"), ("↓", "down"), ("✓", "OK"),
                               ("✗", "X"), ("→", "->"), ("≥", ">="), ("≤", "<="), ("−", "-"), ("▲", "^"), ("Δ", "D")):
                    _t = _t.replace(_a, _b)
                _rt_text_by[round(float(_k))] = _t
    except Exception as e:
        _rt_text_by = {}
        print(f"   ! rt_text read failed ({e}); rt_text archive blank")
    # 2026-10-04: king node for the archive (King Node Model B23, max-gamma strike)
    try:
        _kn_arch = sht['B23'].value
    except Exception:
        _kn_arch = None
    try:
        _vol_tension = sht['AB17'].value
        _vol_tension = _vol_tension if isinstance(_vol_tension, str) else ""
    except Exception:
        _vol_tension = ""   # 2026-10-06: archive only; never block the cycle
    archive_snapshot(ts, spot, vix_v, vvix_v, vix1d_v, flags_row, charm_flag,
                     _locked_R, _locked_S, smoothed, qual_by_strike, raw_by_strike,
                     _es_s200, _es_s400, _ps, _cs, _rr,
                     _atm_iv, _atm_iv_dir,
                     _ct_lo, _ct_hi, _cw_lo, _cw_hi,
                     _state_by_strike, _pin_state, _s10_zomthr, _prox_strike,
                     _sv_ud, _sv_c, _sq_n, _sq_cond,
                     oi_stall_snapshot(), _svx_dir, _iv_regime, _iv_chain,
                     _net_charm, _md_phenom, backers_by_strike, _kn_accel,
                     geo_by_strike=_geo_by_strike, vol_by_strike=vol_by_strike,
                     regime_key=(lambda: (lambda _v: _v if isinstance(_v, str) else "")(
                         sht['J8'].value))(),
                     unsafe_by_strike=_unsafe_by_strike,
                     rt_by_strike=_rt_by_strike,
                     es_prof=_es_prof_arch,
                     mu=(_mu_n, _mu_cond, _fl_c15, _fl_p15),
                     iv_top=_ivtop,
                     iv_fast=_ivfast, frag_pos=_frag_pub, rules_by_strike=_rules_by_strike,
                     safe_by_strike=_safe_by_strike, king_node=_kn_arch,
                     rt_text_by_strike=_rt_text_by,
                     vol_tension=_vol_tension)

    sht['K26'].value = 'Updated ' + ts[11:]
    smooth_label = f'avg {n_buf}/{SMOOTH_N}' if n_buf < SMOOTH_N else f'avg {SMOOTH_N}'
    r1 = _locked_R[0] if _locked_R else '-'
    s1 = _locked_S[0] if _locked_S else '-'
    _stalls = oi_stall_count()
    _stall_txt = f'  OI-STALL {_stalls}' if _stalls else ''
    return (f'updated ({smooth_label}) R1 {r1} / S1 {s1} '
            f'({got}/{len(strikes)} strikes){_stall_txt}')


def reconnect(wait_between=20):
    """Re-establish the Gateway session and resubscribe everything after a drop.
       Called by the main loop whenever the connection is lost or a cycle errors.
       Returns True on success; never raises. The next archived cycle after a
       successful reconnect is stamped event=RECONNECT so the replay can show the
       feed gap."""
    global spx, vix_t, vvix_t, vix1d_t, state, _es_ticker, _next_event, _box_node, _box_pend
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
        _box_node = None; _box_pend = None   # box latch does not survive a feed gap
        _shape_hold.clear()                     # edge/trough hold does not survive a feed gap
        _gex_hist.clear()                       # slope restarts on the new window (sign/flip persist)
        _tape_gap.add(int(time.time() // TAPE_BUCKET_SECS))   # tape draws a break here
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
    try:
        _fl_seeded = seed_flow_history()
        print(f"Flow / melt-up history seeded from today's archive: {_fl_seeded} cycle(s)")
    except Exception as _e:
        print(f"   ! flow history seed skipped ({_e})")
    _ng_seeded = seed_gex_history()
    if _ng_seeded:
        _flip = (f"Net GEX flipped {'POS' if _gex_sign > 0 else 'NEG'}"
                 if _gex_flip_t is not None
                 else f"Net GEX {'POS' if _gex_sign > 0 else 'NEG'} held")
        _sflip = (f"slope flipped {'POS' if _slope_sign > 0 else 'NEG'}"
                  if _slope_flip_t is not None
                  else (f"slope {'POS' if _slope_sign > 0 else 'NEG'} held"
                        if _slope_sign else "slope unset"))
        print(f"Seeded Net GEX history: {_ng_seeded} cycles from today's archive "
              f"({_flip}; {_sflip}).")
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
                    _prox_strike, _prox_miss = None, 0   # strikes change on recentre -> PROX latch resets
                    _swR_lock, _swS_lock = None, None     # reset shelf/wall lock on recentre
                    _swR_pend, _swS_pend = None, None
                    _rs_side.clear()
                    _oi_stall.clear()                     # new window -> stall state is stale
                    _gex_hist.clear()                     # slope restarts on the new window
                    _tape_gap.add(int(time.time() // TAPE_BUCKET_SECS))
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
