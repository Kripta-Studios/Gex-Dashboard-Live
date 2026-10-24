"""Pure 2025 mode selection; complete calendar and shared TRAIN risk scales.

Caller must supply the independently checked full exchange calendar, including
early closes and explicit missing sources. This module never infers eligibility
from only the rows on which a policy happened to trade.
"""

from datetime import datetime
import math

MODES = ("static", "expanding", "rolling12")
TICKERS = ("SPXW", "SPY", "QQQ")


def _key(ticker, day):
    if ticker not in TICKERS or not isinstance(day, str) or len(day) != 8:
        raise ValueError("Invalid ticker/date identity")
    parsed = datetime.strptime(day, "%Y%m%d")
    if parsed.year != 2025 or parsed.strftime("%Y%m%d") != day:
        raise ValueError("Selection uses only validation 2025")
    return ticker, day


def select_monthly_mode(daily_by_mode, expected_keys, common_scales):
    """Choose a daily-compliant research mode, never authorize promotion.

    Each daily record has ticker, date (YYYYMMDD), source_status, trades,
    net_base and net_adverse. Zero-trade days and missing days remain explicit.
    Shared scales must originate from the static TRAIN fit, not validation.
    Their numerical validity is checked here; provenance belongs to the runner.
    """
    if set(daily_by_mode) != set(MODES):
        raise ValueError("All three declared modes are required")
    expected = set(expected_keys)
    if not expected:
        raise ValueError("Empty expected calendar")
    for identity in expected:
        _key(*identity)
    calendar_dates = {day for _, day in expected}
    if expected != {(ticker, day) for ticker in TICKERS for day in calendar_dates}:
        raise ValueError("Expected calendar must cover all three tickers")
    if set(common_scales) != set(TICKERS):
        raise ValueError("Exactly one shared TRAIN scale per ticker is required")
    if any(
        isinstance(value, bool) or not math.isfinite(value) or value <= 0
        for value in common_scales.values()
    ):
        raise ValueError("Shared TRAIN scales must be finite and positive")
    choices = []
    common_status = None
    for mode in MODES:
        rows = list(daily_by_mode[mode])
        identities = [_key(row["ticker"], row["date"]) for row in rows]
        if len(set(identities)) != len(identities) or set(identities) != expected:
            raise ValueError("Mode omitted, duplicated or added calendar ticker-days")
        rows.sort(key=lambda row: (row["date"], row["ticker"]))
        for row in rows:
            if row["source_status"] not in ("COMPLETE", "MISSING_SOURCE"):
                raise ValueError("Unknown source status")
            if type(row["trades"]) is not int or row["trades"] < 0:
                raise ValueError("Trade counts must be nonnegative integers")
            for field in ("net_base", "net_adverse"):
                if isinstance(row[field], bool) or not math.isfinite(row[field]):
                    raise ValueError("PnL must be finite")
            if row["source_status"] == "MISSING_SOURCE" and row["trades"]:
                raise ValueError("A missing source cannot produce trades")
            if not row["trades"] and (row["net_base"] != 0 or row["net_adverse"] != 0):
                raise ValueError("Zero-trade days must have zero PnL")
            if row["net_adverse"] > row["net_base"] + 1e-8:
                raise ValueError("Adverse costs cannot improve the same trajectory")
        statuses = {
            (row["ticker"], row["date"]): row["source_status"] for row in rows
        }
        if common_status is not None and statuses != common_status:
            raise ValueError("Source availability cannot depend on the policy")
        common_status = statuses
        missing = sum(row["source_status"] == "MISSING_SOURCE" for row in rows)
        no_fill = sum(
            row["source_status"] == "COMPLETE" and row["trades"] == 0
            for row in rows
        )
        active = sum(row["trades"] > 0 for row in rows)
        net = math.fsum(row["net_base"] for row in rows)
        adverse = math.fsum(row["net_adverse"] for row in rows)
        score = math.fsum(
            row["net_base"] / common_scales[row["ticker"]] for row in rows
        ) / len(expected)
        choices.append(dict(
            mode=mode, expected_ticker_days=len(expected),
            missing_no_evaluable=missing, available_days_without_fill=no_fill,
            active_ticker_days=active, daily_viable=(missing == 0 and no_fill == 0),
            trades=sum(row["trades"] for row in rows), net_base=net,
            net_adverse=adverse, common_scale_mean_daily_score=score,
            mean_active_day_net_base=net / active if active else None,
        ))
    eligible = [row for row in choices if row["daily_viable"]]
    winner = max(eligible, key=lambda row: row["common_scale_mean_daily_score"]) if eligible else None
    return dict(
        status="SELECTED_RESEARCH_MODE" if winner else "FAIL_NO_DAILY_COMPLIANT_MODE",
        selected_mode=winner["mode"] if winner else None,
        approved=False, common_scales=dict(common_scales), choices=choices,
        selection_period="2025", tie_break=list(MODES),
    )
