"""Descriptive monthly stability of an audited fixed comparison, never selection.

Only sealed daily summaries and executed attempts are read. No new predictions,
fits, thresholds, market quotes or counterfactual labels are produced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

import numpy as np
import pandas as pd


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def metrics(values):
    values = np.asarray(values, dtype=float)
    require(np.isfinite(values).all(), "Nonfinite realized net")
    gains, losses = values[values > 0].sum(), -values[values < 0].sum()
    return dict(
        trades=len(values),
        net_usd=float(values.sum()),
        gross_gains_usd=float(gains),
        gross_losses_usd=float(losses),
        profit_factor=float(gains / losses) if losses else None,
        profit_factor_infinite=bool(gains > 0 and losses == 0),
        win_rate=float((values > 0).mean()) if len(values) else None,
    )


def summarize(days, attempts):
    """Each invocation is one fixed policy/ticker/month, with the full calendar."""
    require(len(days) > 0 and len({d["date"] for d in days}) == len(days), "Calendar duplicates or empty")
    require(all(d["source_status"] in ("COMPLETE", "MISSING_SOURCE") for d in days), "Unknown source state")
    require(attempts.status.isin(["FILLED", "NO_FILL"]).all(), "Invalid fill state")
    require(set(attempts.date).issubset({d["date"] for d in days}), "Trade outside calendar")
    require(np.isfinite(attempts[["net_base", "net_adverse"]].to_numpy(float)).all(), "Nonfinite attempts")
    require((attempts.loc[attempts.status == "NO_FILL", ["net_base", "net_adverse"]] == 0).all().all(), "Nonzero no-fill")
    available = [d for d in days if d["source_status"] == "COMPLETE"]
    missing = [d for d in days if d["source_status"] == "MISSING_SOURCE"]
    for day in days:
        offered = attempts.loc[attempts.date == day["date"]]
        fills = offered.loc[offered.status == "FILLED"]
        require(len(fills) == day["trades"] and len(offered) == day["attempts"], "Daily count differs")
        for field in ("net_base", "net_adverse"):
            require(np.isclose(fills[field].sum(), day[field], rtol=0, atol=1e-8), "Daily net differs")
        if day["source_status"] == "MISSING_SOURCE":
            require(len(offered) == 0 and day["net_base"] == day["net_adverse"] == 0, "Fabricated missing-day outcome")
    fills = attempts.loc[attempts.status == "FILLED"]
    no_trade = [d["date"] for d in available if d["trades"] == 0]
    result = dict(
        expected_days=len(days), available_days=len(available), missing_days=len(missing),
        observed_days_without_fill=len(no_trade), no_fill_dates=no_trade,
        missing_dates=[d["date"] for d in missing],
        observable_daily_pass=bool(available) and not no_trade,
        universal_daily_status="NO_EVALUABLE" if missing else ("FAIL" if no_trade else "PASS"),
        base=metrics(fills.net_base), adverse=metrics(fills.net_adverse),
    )
    # Close-to-close cash-PnL path of available sessions; no account return or
    # intraday drawdown claim. Missing sessions never get a fabricated zero.
    available = sorted(available, key=lambda d: d["date"])
    daily_net = np.asarray([d["net_base"] for d in available], float)
    path = np.r_[0., np.cumsum(daily_net)]
    result["available_daily_close_drawdown_usd"] = float(np.max(np.maximum.accumulate(path) - path))
    result["drawdown_scope"] = "AVAILABLE_SESSION_CLOSE_CASH_PNL_NOT_ACCOUNT_RETURN_OR_INTRADAY_DRAWDOWN"
    result["best_available_day_usd"] = float(daily_net.max()) if len(daily_net) else None
    result["worst_available_day_usd"] = float(daily_net.min()) if len(daily_net) else None
    result["observed_positive_days"] = int((daily_net > 0).sum())
    return result


def run(root, audit_path, expected_audit_sha, out):
    root, audit_path, out = Path(root).resolve(), Path(audit_path).resolve(), Path(out).resolve()
    require(not out.exists(), "Immutable new output required")
    require(not out.is_relative_to(root) and not root.is_relative_to(out), "Separate report output required")
    require(digest(audit_path) == expected_audit_sha, "Audit authority differs")
    audit = read_json(audit_path)
    require(audit["status"] == "PASS_INDEPENDENT_MARKET_CUE_COMPARISON_ECONOMIC_AUDIT", "Completed independent audit required")
    binding = audit["binding"]
    require(Path(binding["comparison_root"]).resolve() == root, "Wrong comparison authority")
    sources = {str(audit_path): expected_audit_sha, str(Path(__file__).resolve()): digest(__file__)}

    def consume(path, expected):
        path = Path(path).resolve()
        require(digest(path) == expected, "Changed consumed evidence: " + str(path))
        sources[str(path)] = expected

    for name, field in (("comparison.complete.json", "comparison_complete_sha256"), ("completion.json", "completion_sha256"), ("freeze.json", "freeze_sha256")):
        consume(root / name, binding[field])
    complete = read_json(root / "comparison.complete.json")
    require(complete["status"] == "COMPLETE" and complete["binding"] == binding["freeze_sha256"], "Global seal differs")
    members = {str((root / name).resolve()): value for name, value in complete["files"].items()}
    require(all(Path(name).is_relative_to(root) for name in members), "Unsafe completion path")
    policies = tuple(audit["policies"])
    require(policies == ("original_net__0", "cue_net__0"), "Fixed policies changed")
    groups = {}
    calendar_counts = {2025: 0, 2026: 0}
    for name, expected in sorted(members.items()):
        relative = Path(name).relative_to(root).as_posix()
        match = re.fullmatch(r"days/(QQQ|SPXW|SPY)/(202[56][0-9]{4})\.json", relative)
        if match is None:
            continue
        ticker, day = match.groups()
        calendar_counts[int(day[:4])] += 1
        consume(name, expected)
        daily = read_json(name)
        require(set(daily) == set(policies), "Daily policies differ")
        for policy in policies:
            row = {field: daily[policy][field] for field in (
                "ticker", "date", "source_status", "trades", "attempts", "net_base", "net_adverse",
            )}
            require(row["ticker"] == ticker and row["date"] == day, "Daily identity differs")
            attempts_path = root / "days" / ticker / (day + "." + policy + ".parquet")
            require(str(attempts_path) in members, "Consumed attempts not globally sealed")
            consume(attempts_path, members[str(attempts_path)])
            frame = pd.read_parquet(attempts_path, columns=["status", "net_base", "net_adverse"])
            frame["date"] = day
            item = groups.setdefault((policy, ticker, day[:6]), ([], []))
            item[0].append(row)
            item[1].append(frame)
    require(calendar_counts == {2025: 750, 2026: 369}, "Incomplete calendar")
    result = []
    for (policy, ticker, month), (days, frames) in sorted(groups.items()):
        frame = pd.concat(frames, ignore_index=True)
        result.append(dict(policy=policy, ticker=ticker, month=month, **summarize(days, frame)))
    require(len(result) == 108, "Expected both fixed policies by three tickers by18 months")
    for path, expected in sources.items():
        require(digest(path) == expected, "Source changed during reporting")
    out.mkdir(parents=True)
    record = dict(status="COMPLETE_DESCRIPTIVE_MONTHLY_REPORT", months=result, sources=sources,
                  policy_selection=False, new_fits=0, new_predictions=0,
                  development_seen=True, promotion_approved=False,
                  scope="Same audited fixed-policy attempts; descriptive stability only; no new rule or economic gate")
    target = out / "summary.json"
    temporary = out / "summary.json.partial"
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(target)
    print(json.dumps(dict(status=record["status"], months=len(result), summary_sha256=digest(target))), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("root", "audit", "audit-sha256", "out"):
        parser.add_argument("--" + argument, required=True)
    args = parser.parse_args()
    run(args.root, args.audit, args.audit_sha256, args.out)
