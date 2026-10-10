"""Pure functions copied verbatim from the user-supplied 2026-10-10 live script.

No broker, Excel or script initialization is imported. Source parity is tested.
"""

import math

RATE = 0.043
DIV = 0.012
SQRT2PI = math.sqrt(2 * math.pi)
LOCK_HOLD = 3
LOCK_RELEASE = 3

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

def vanna_dir(vex, ivfast):
    if not isinstance(vex, (int, float)) or str(ivfast or "").upper() not in ("UP", "DOWN"):
        return "-"
    if str(ivfast).upper() == "UP":
        return "SELL" if vex > 0 else "BUY"
    return "BUY" if vex > 0 else "SELL"

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
