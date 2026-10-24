"""Descriptive export of one externally pinned, completed OOF H1 audit only."""

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

MODES = ("static", "expanding", "rolling12")
TICKERS = ("SPXW", "SPY", "QQQ")
MONTHS = tuple(f"2026{i:02d}" for i in range(1, 7))
POLICIES = tuple(m + s for m in MODES for s in ("__control", "__corrected"))
MISSING = {(t, d) for t in ("SPY", "QQQ") for d in ("20260401", "20260409", "20260415")}
COSTS = ("net_base", "net_adverse")


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    require(
        type(value) in (int, float) and math.isfinite(value),
        "Nonfinite/non-numeric metric",
    )
    return value


def count(value):
    require(type(value) is int and value >= 0, "Invalid count")
    return value


def equal(a, b):
    require(
        math.isclose(number(a), number(b), rel_tol=1e-10, abs_tol=1e-7),
        "Aggregate mismatch",
    )


def metrics(value):
    count(value["trades"])
    for cost in COSTS:
        net = number(value[cost])
        gain, loss = (
            number(value[cost + suffix]) for suffix in ("_gross_gains", "_gross_losses")
        )
        require(gain >= 0 and loss >= 0, "Negative gross total")
        equal(net, gain - loss)
        pf, infinite = value[cost + "_profit_factor"], value[cost + "_pf_infinite"]
        require(
            type(infinite) is bool and infinite == (gain > 0 and loss == 0),
            "PF flag mismatch",
        )
        if loss:
            equal(pf, gain / loss)
        else:
            require(pf is None, "Undefined PF must be null")


def coverage(rows):
    available = [r for r in rows if r["source_status"] == "COMPLETE"]
    missing = len(rows) - len(available)
    zero = sum(r["trades"] == 0 for r in available)
    return dict(
        expected_days=len(rows),
        available_days=len(available),
        missing_days=missing,
        available_days_without_fill=zero,
        observable_daily_pass=bool(available) and zero == 0,
        universal_daily_pass=bool(available) and not missing and zero == 0,
        universal_daily_status="NO_EVALUABLE"
        if missing
        else ("FAIL" if zero else "PASS"),
    )


def check_coverage(actual, expected):
    require(set(actual) == set(expected), "Coverage schema mismatch")
    for key, value in expected.items():
        require(
            type(actual[key]) is type(value) and actual[key] == value,
            "Coverage mismatch",
        )


def reconcile(parts, total):
    metrics(total)
    require(total["trades"] == sum(p["trades"] for p in parts), "Trades mismatch")
    for cost in COSTS:
        for suffix in ("", "_gross_gains", "_gross_losses"):
            equal(total[cost + suffix], math.fsum(p[cost + suffix] for p in parts))


def tables(audit):
    require(
        audit["status"] == "PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_FULL_H1",
        "Full H1 audit required",
    )
    require(
        audit["scope"]
        == "OOF_OFFSETS_AND_ECONOMIC_EXECUTION_GIVEN_AUDITED_BASE_SCORES",
        "Scope mismatch",
    )
    require(
        audit["binding"]["audited_months"] == list(MONTHS), "Six fixed months required"
    )
    require(
        audit["winner_selected"] is None and audit["development_seen"] is True,
        "Selection/development mismatch",
    )
    for key in (
        "base_fit_reproduced",
        "base_inference_reproduced",
        "raw_quote_replay",
        "technical_ready",
        "promotion_approved",
    ):
        require(audit[key] is False, "Audit limitation flag mismatch")
    require(
        [m["target_month"] for m in audit["months"]] == list(MONTHS),
        "Month order/closure mismatch",
    )
    require(set(audit["policies"]) == set(POLICIES), "Policy closure mismatch")
    monthly, periods, calendars, all_daily = [], [], {}, {p: [] for p in POLICIES}
    for month in audit["months"]:
        stamp = month["target_month"]
        require(
            set(month["policies"]) == set(POLICIES), "Monthly policy closure mismatch"
        )
        for policy in POLICIES:
            report = month["policies"][policy]
            require(set(report["by_ticker"]) == set(TICKERS), "Ticker closure mismatch")
            daily = report["daily"]
            keys = set()
            for row in daily:
                key = (row["ticker"], row["date"])
                require(
                    key not in keys and key[0] in TICKERS and key[1][:6] == stamp,
                    "Duplicate/foreign calendar key",
                )
                require(
                    dt.datetime.strptime(key[1], "%Y%m%d").strftime("%Y%m%d") == key[1],
                    "Invalid date",
                )
                keys.add(key)
                if key in MISSING:
                    require(
                        row["source_status"] == "MISSING_SOURCE",
                        "Missing identity mismatch",
                    )
                    require(
                        all(row[k] is None for k in ("trades", *COSTS)),
                        "Missing economics must be null",
                    )
                else:
                    require(
                        row["source_status"] == "COMPLETE", "Unexpected missing day"
                    )
                    metrics(row)
            require(
                keys == {(t, d) for _, d in keys for t in TICKERS},
                "Incomplete ticker calendar",
            )
            if stamp in calendars:
                require(keys == calendars[stamp], "Policy calendars differ")
            else:
                calendars[stamp] = keys
            check_coverage(report["coverage"], coverage(daily))
            reconcile(
                [r for r in daily if r["source_status"] == "COMPLETE"],
                report["observed"],
            )
            for ticker in TICKERS:
                piece = report["by_ticker"][ticker]
                days = [r for r in daily if r["ticker"] == ticker]
                require(days, "Empty ticker month")
                check_coverage(piece["coverage"], coverage(days))
                reconcile(
                    [r for r in days if r["source_status"] == "COMPLETE"],
                    piece["observed"],
                )
                monthly.append(
                    dict(
                        month=stamp,
                        policy=policy,
                        ticker=ticker,
                        **piece,
                        missing_dates=[
                            r["date"]
                            for r in days
                            if r["source_status"] == "MISSING_SOURCE"
                        ],
                    )
                )
            all_daily[policy].extend(daily)
    require(
        sum(len(v) for v in calendars.values()) == 369,
        "Expected 369 calendar ticker-days",
    )
    require(
        MISSING <= set.union(*calendars.values()), "Six missing identities required"
    )
    for policy in POLICIES:
        report = audit["policies"][policy]
        require(set(report["by_ticker"]) == set(TICKERS), "H1 ticker closure mismatch")
        check_coverage(report["coverage"], coverage(all_daily[policy]))
        for ticker in TICKERS:
            total = report["by_ticker"][ticker]
            pieces = [
                r for r in monthly if r["policy"] == policy and r["ticker"] == ticker
            ]
            reconcile([r["observed"] for r in pieces], total["observed"])
            days = [r for r in all_daily[policy] if r["ticker"] == ticker]
            check_coverage(total["coverage"], coverage(days))
            require(
                type(total["positive_months"]) is int
                and total["positive_months"]
                == sum(r["observed"]["net_base"] > 0 for r in pieces),
                "Positive-month mismatch",
            )
            require(
                total["economic_gate_status"] in ("PASS", "FAIL"),
                "Missing audited gate",
            )
            periods.append(dict(policy=policy, ticker=ticker, **total))
        require(
            report["economic_gate_status"] in ("PASS", "FAIL"), "Missing policy gate"
        )
    return dict(
        monthly=monthly,
        periods=periods,
        winner_selected=None,
        development_seen=True,
        metric_scope="Audited aggregates only; no WR, drawdown, holding-time or portfolio inference",
        missing_scope="Missing days have null economics; monthly totals cover available days only",
        no_fill_scope="available_days_without_fill counts days, not NO_FILL attempts",
    )


def figure(data, out):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    plt.rcParams.update({"svg.hashsalt": "oof-h1-20261024", "font.size": 10})
    fig, axes = plt.subplots(3, 3, figsize=(19, 12), sharex=True)
    lookup = {(r["month"], r["policy"], r["ticker"]): r for r in data["monthly"]}
    variants = [
        ("__control", "net_base", "#426b9e", ""),
        ("__control", "net_adverse", "#426b9e", "//"),
        ("__corrected", "net_base", "#c86c36", ""),
        ("__corrected", "net_adverse", "#c86c36", "//"),
    ]
    for col, ticker in enumerate(TICKERS):
        values = [
            r["observed"][c]
            for r in data["monthly"]
            if r["ticker"] == ticker
            for c in COSTS
        ]
        low, high = min(0, min(values)), max(0, max(values))
        pad = max((high - low) * 0.18, 1)
        for row, mode in enumerate(MODES):
            ax = axes[row, col]
            for index, (suffix, cost, color, hatch) in enumerate(variants):
                ys = [
                    lookup[m, mode + suffix, ticker]["observed"][cost] for m in MONTHS
                ]
                ax.bar(
                    [i + (index - 1.5) * 0.19 for i in range(6)],
                    ys,
                    width=0.18,
                    color=color,
                    hatch=hatch,
                    edgecolor="#333333",
                    linewidth=0.4,
                )
            ax.axhline(0, color="#555555", linewidth=0.7)
            ax.set_ylim(low - pad, high + pad)
            ax.set_title(f"{mode} | {ticker}")
            ax.set_xticks(range(6), [m[4:] for m in MONTHS])
            ax.tick_params(labelbottom=True)
            ax.grid(axis="y", alpha=0.2)
            ax.set_axisbelow(True)
            ax.set_ylabel("Net USD (available days)")
            if ticker in ("SPY", "QQQ"):
                ax.axvspan(2.5, 3.5, color="#dddddd", alpha=0.3, zorder=0)
                ax.text(
                    0.02,
                    0.97,
                    "April: 3 missing days; economics null",
                    transform=ax.transAxes,
                    va="top",
                    fontsize=8,
                    bbox=dict(facecolor="white", alpha=0.85, edgecolor="none"),
                )
    labels = ["Control base", "Control adverse", "Corrected base", "Corrected adverse"]
    fig.legend(
        [Patch(facecolor=v[2], hatch=v[3], edgecolor="#333333") for v in variants],
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.94),
        ncol=4,
        frameon=False,
    )
    fig.suptitle(
        "OOF H1 2026 | all six fixed policies | SEEN_DEVELOPMENT | winner_selected=null",
        y=0.985,
    )
    fig.text(
        0.5,
        0.015,
        "Months 01–06. Same USD scale within each ticker column; different across tickers. Missing days are not zero PnL.\n"
        "Descriptive audited aggregates; no base refit/inference or raw quote reconstruction; no promotion.",
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.055, 1, 0.91))
    fig.savefig(out / "monthly_net_usd.png", dpi=150)
    fig.savefig(out / "monthly_net_usd.svg", metadata={"Date": None})
    plt.close(fig)


def write_json(path, value):
    path.write_text(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def run(audit_path, expected_sha, output):
    source, out = Path(audit_path).resolve(), Path(output).resolve()
    require(
        len(expected_sha) == 64 and all(c in "0123456789abcdef" for c in expected_sha),
        "External SHA required",
    )
    require(sha(source) == expected_sha, "Audit SHA mismatch")
    require(
        not out.exists() and not out.is_relative_to(source.parent),
        "Fresh output outside audit directory required",
    )
    data = tables(json.loads(source.read_text(encoding="utf-8")))
    require(sha(source) == expected_sha, "Audit changed during read")
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "tables.json", data)
    figure(data, out)
    require(sha(source) == expected_sha, "Audit changed before closure")
    files = {
        p.name: dict(sha256=sha(p), bytes=p.stat().st_size)
        for p in sorted(out.iterdir())
    }
    write_json(
        out / "manifest.json",
        dict(
            status="COMPLETE_DESCRIPTIVE_OOF_H1_AUDIT_REPORT",
            audit_path=str(source),
            audit_sha256=expected_sha,
            code_sha256=sha(__file__),
            files=files,
            monthly_rows=108,
            h1_rows=18,
            source_rehashed_before_after=True,
            source_scope="Only the audit JSON; no verified_files payload rehash",
            winner_selected=None,
            technical_ready=False,
            promotion_approved=False,
        ),
    )
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True)
    parser.add_argument("--audit-sha256", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    run(args.audit, args.audit_sha256, args.out)
