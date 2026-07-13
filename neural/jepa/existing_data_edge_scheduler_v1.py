"""Fail-closed live-equivalent scheduler for the existing-data edge sprint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from neural.jepa.walkforward_event_option_gate import DeployConfig, deploy


SCHEDULER = {
    "SPXW": {"max_trades_per_day": 4, "cooldown_minutes": 0, "bucket": 25},
    "QQQ": {"max_trades_per_day": 2, "cooldown_minutes": 30, "bucket": 35},
    "SPY": {"max_trades_per_day": 1, "cooldown_minutes": 0, "bucket": 35},
}
EXECUTION_CONTRACT = {
    "option_price_mode": "executable_quote",
    "option_exit_mode": "trailing",
    "horizon_minutes": 180,
    "option_tp_pct": 10.0,
    "option_sl_pct": 0.6,
    "option_min_hold_minutes": 30,
    "option_trail_activation_pct": 0.5,
    "option_trail_drawdown_pct": 0.25,
    "require_open_interest": True,
}


def verify_executable_build_summary(path: str | Path) -> dict[str, Any]:
    """Verify the exact ask-to-bid label contract recorded by the source build."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    args = payload.get("args")
    if not isinstance(args, dict):
        raise AssertionError("executable build summary has no args object")
    mismatches = {
        key: {"expected": expected, "actual": args.get(key)}
        for key, expected in EXECUTION_CONTRACT.items()
        if args.get(key) != expected
    }
    if mismatches:
        raise AssertionError(f"executable build contract mismatch: {mismatches}")
    return payload


def attach_selected_payoff(scored: pd.DataFrame) -> pd.DataFrame:
    """Bind the already-selected side to its exact executable outcome columns."""

    required = ["ticker", "action", "option_price_mode"]
    missing = [col for col in required if col not in scored.columns]
    if missing:
        raise KeyError(f"selected payoff frame missing: {missing}")
    if not scored["option_price_mode"].astype(str).str.lower().eq("executable_quote").all():
        raise AssertionError("selected payoff contains a non-executable price mode")
    out = scored.copy()
    out["realized_return"] = np.nan
    out["exit_minutes"] = np.nan
    for ticker, config in SCHEDULER.items():
        bucket = int(config["bucket"])
        ticker_mask = out["ticker"].astype(str).str.upper().eq(ticker)
        if not bool(ticker_mask.any()):
            continue
        for action, prefix in (("CALL", "call"), ("PUT", "put")):
            mask = ticker_mask & out["action"].astype(str).str.upper().eq(action)
            return_col = f"{prefix}_d{bucket:02d}_opt_exit_ret"
            exit_col = f"{prefix}_d{bucket:02d}_opt_exit_minutes"
            if return_col not in out.columns or exit_col not in out.columns:
                raise KeyError(f"missing selected executable columns: {return_col}, {exit_col}")
            out.loc[mask, "realized_return"] = pd.to_numeric(out.loc[mask, return_col], errors="coerce")
            out.loc[mask, "exit_minutes"] = pd.to_numeric(out.loc[mask, exit_col], errors="coerce")
    if not out["ticker"].astype(str).str.upper().isin(SCHEDULER).all():
        raise AssertionError("unknown ticker in selected payoff frame")
    if not out["action"].astype(str).str.upper().isin(["CALL", "PUT"]).all():
        raise AssertionError("selected payoff action must be CALL or PUT")
    values = out[["realized_return", "exit_minutes"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise AssertionError("selected executable payoff is missing/non-finite")
    if not out["exit_minutes"].between(30.0, 180.0, inclusive="both").all():
        raise AssertionError("selected executable payoff violates 30..180 minute hold")
    return out


def _validate_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if "date" not in out.columns:
        if "trade_date" not in out.columns:
            raise KeyError("scheduler requires date or trade_date")
        out["date"] = out["trade_date"].astype(str)
    required = ["ticker", "date", "minute", "score", "action", "realized_return", "exit_minutes"]
    missing = [col for col in required if col not in out.columns]
    if missing:
        raise KeyError(f"scheduler candidates missing: {missing}")
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["date"] = out["date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    if not out["ticker"].isin(SCHEDULER).all():
        raise AssertionError("scheduler received an unknown ticker")
    if not out["date"].str.fullmatch(r"\d{8}").all():
        raise AssertionError("scheduler received an invalid date")
    if not out["action"].astype(str).str.upper().isin(["CALL", "PUT"]).all():
        raise AssertionError("scheduler action must be CALL or PUT")
    numeric_cols = ["minute", "score", "realized_return", "exit_minutes"]
    numeric = out[numeric_cols].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise AssertionError("scheduler fields must be finite")
    out[numeric_cols] = numeric
    if not np.equal(out["minute"], np.floor(out["minute"])).all() or not out["minute"].between(0, 1439).all():
        raise AssertionError("scheduler minute must be an integer minute-of-day")
    if not out["exit_minutes"].between(30.0, 180.0, inclusive="both").all():
        raise AssertionError("scheduler hold must be within 30..180 minutes")
    keys = ["ticker", "date", "minute"]
    if out.duplicated(keys).any():
        raise AssertionError("scheduler requires one policy decision per ticker timestamp")
    out["minute"] = out["minute"].astype(int)
    return out


def replay_live_equivalent(candidates: pd.DataFrame) -> pd.DataFrame:
    """Replay chronologically with ticker caps, entry cooldown, and no overlap.

    The shared audited scheduler is called separately per ticker so its cap and
    cooldown match the live policy.  A candidate at exactly the prior exit time
    is eligible, matching the existing audited convention.
    """

    checked = _validate_candidates(candidates)
    outputs: list[pd.DataFrame] = []
    for ticker, config in SCHEDULER.items():
        part = checked[checked["ticker"].eq(ticker)].copy()
        if part.empty:
            continue
        selected = deploy(
            part,
            DeployConfig(
                threshold=float("-inf"),
                max_trades_per_day=int(config["max_trades_per_day"]),
            ),
            cooldown_minutes=int(config["cooldown_minutes"]),
            allow_overlapping_positions=False,
        )
        outputs.append(selected)
    if not outputs:
        return checked.iloc[0:0].copy()
    trades = pd.concat(outputs, ignore_index=True).sort_values(
        ["date", "minute", "ticker"], kind="stable"
    ).reset_index(drop=True)
    _assert_scheduler_output(trades)
    return trades


def _assert_scheduler_output(trades: pd.DataFrame) -> None:
    for (ticker, date), day in trades.groupby(["ticker", "date"], sort=False):
        config = SCHEDULER[str(ticker)]
        ordered = day.sort_values("minute", kind="stable")
        if len(ordered) > int(config["max_trades_per_day"]):
            raise AssertionError(f"daily cap violated for {ticker} {date}")
        prior_entry: float | None = None
        prior_exit: float | None = None
        for row in ordered.itertuples(index=False):
            entry = float(row.minute)
            if prior_exit is not None and entry < prior_exit:
                raise AssertionError(f"position overlap for {ticker} {date}")
            if prior_entry is not None and entry < prior_entry + int(config["cooldown_minutes"]):
                raise AssertionError(f"entry cooldown violated for {ticker} {date}")
            prior_entry = entry
            prior_exit = entry + float(row.exit_minutes)
