"""Reconcile completed reporter outputs and plot all 2025 monthly groups.

Only documentary outputs are read. No source model, score, feature or label is
opened; no scheduling, fitting, inference or mode selection is performed.
"""

import argparse
import csv
import ctypes
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics


MODES = ("static", "expanding", "rolling12")
TICKERS = ("SPXW", "SPY", "QQQ")
MONTHS = tuple(f"2025{m:02d}" for m in range(1, 13))


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def resources():
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in (
                "total_physical", "available_physical", "total_pagefile", "available_pagefile",
                "total_virtual", "available_virtual", "available_extended")]
    state = Memory()
    state.length = ctypes.sizeof(state)
    require(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)), "Memory API failed")
    result = dict(available_ram_bytes=state.available_physical,
                  free_commit_bytes=state.available_pagefile, minimum_bytes=2_000_000_000)
    require(min(state.available_physical, state.available_pagefile) >= 2_000_000_000,
            "Resource gate failed")
    return result


def flatten(value, prefix=""):
    result = {}
    for key, item in value.items():
        name = prefix + key
        if isinstance(item, dict):
            result.update(flatten(item, name + "."))
        else:
            result[name] = "" if item is None else str(item)
    return result


def csv_matches(path, rows):
    with path.open(encoding="utf-8", newline="") as stream:
        actual = list(csv.DictReader(stream))
    columns = set().union(*(flatten(row).keys() for row in rows))
    expected = [{name: flatten(row).get(name, "") for name in columns} for row in rows]
    require(actual == expected, "CSV differs from JSON: " + path.name)


def close(left, right):
    if right is None:
        return left is None
    return math.isfinite(left) and math.isclose(left, right, abs_tol=1e-8, rel_tol=1e-12)


def reconcile_group(row, frame, daily, attempts):
    frame = frame.sort_values(["date", "exit_i", "ticker"], kind="stable")
    economy = row["available_economics"]
    require(economy["trades"] == len(frame), "Trades differ")
    for field in ("net_base", "net_adverse"):
        values = frame[field].tolist()
        require(all(math.isfinite(v) for v in values), "Nonfinite reward")
        gains, losses = sum(v for v in values if v > 0), -sum(v for v in values if v < 0)
        running = peak = drawdown = 0.0
        for value in values:
            running += value
            peak = max(peak, running)
            drawdown = max(drawdown, peak - running)
        expected = {field: sum(values), field + "_pf": gains / losses if losses else None,
                    field + "_win_rate": sum(v > 0 for v in values) / len(values) if values else None,
                    field + "_max_drawdown": drawdown}
        require(all(close(economy[k], v) for k, v in expected.items()), "Economic aggregate differs")
        require(economy[field + "_pf_infinite"] == (gains > 0 and losses == 0), "PF flag differs")
    holds = frame.hold_minutes.tolist()
    expected_holds = dict(min=min(holds), median=statistics.median(holds), max=max(holds)) if holds else dict(min=None, median=None, max=None)
    require(all(close(economy["holding_minutes"][k], v) for k, v in expected_holds.items()), "Holding differs")
    expected_reasons = {}
    if len(frame):
        for reason in ("TARGET", "STOP", "EOD"):
            selected = frame[frame.reason == reason]
            expected_reasons[reason] = dict(trades=len(selected), net_base=sum(selected.net_base), net_adverse=sum(selected.net_adverse))
    require(set(economy["exit_reasons"]) == set(expected_reasons), "Reasons differ")
    for reason, values in expected_reasons.items():
        require(all(close(economy["exit_reasons"][reason][k], v) for k, v in values.items()), "Reason sum differs")
    active = int((daily.trades > 0).sum())
    require(row["expected_ticker_days"] == row["available_ticker_days"] == len(daily)
            and row["missing_no_evaluable"] == 0 and row["missing_day_economics"] is None
            and row["available_days_with_fill"] == active
            and row["available_days_without_fill"] == len(daily) - active,
            "Coverage differs")
    require(row["attempts"] == len(attempts)
            and row["no_fill_attempts"] == int((attempts.status == "NO_FILL").sum()), "Attempts differ")
    require(close(row["net_base_per_available_day"], sum(frame.net_base) / len(daily)), "Daily denominator differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--exit-receipt", type=Path, required=True)
    parser.add_argument("--exit-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    gate = resources()
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    root, out = args.report.resolve(), args.out.resolve()
    require(not out.exists() and not out.is_relative_to(root), "Fresh independent output required")
    manifest_path, exit_path = root / "output_manifest.json", args.exit_receipt.resolve()
    require(sha(manifest_path) == args.manifest_sha256 and sha(exit_path) == args.exit_sha256,
            "External receipt pin differs")
    manifest, observed_exit = read(manifest_path), read(exit_path)
    require(manifest["status"] == "COMPLETE" and observed_exit["status"] == "PROCESS_EXIT_OBSERVED"
            and observed_exit["exit_code"] == 0 and observed_exit["pins_unchanged"] is True
            and observed_exit["audit_unchanged"] is True and observed_exit["monitor_error"] is None,
            "Completed reporter and observed exit 0 required")
    pinned = {str(manifest_path): args.manifest_sha256, str(exit_path): args.exit_sha256}
    for name, item in manifest["files"].items():
        path = (root / name).resolve()
        require(path.is_relative_to(root) and path.is_file(), "Unsafe output member")
        require(sha(path) == item["sha256"] and path.stat().st_size == item["bytes"], "Output hash differs")
        pinned[str(path)] = item["sha256"]
    summary = read(root / "summary.json")
    require(summary["status"] == "DESCRIPTIVE_TABLES_REQUIRE_COMPLETE_OUTPUT_MANIFEST"
            and summary["months"] == list(MONTHS) and summary["modes"] == list(MODES)
            and summary["tickers"] == list(TICKERS) and summary["selected_mode_cited"] is None
            and summary["development_seen"] is True and summary["promotion_approved"] is False
            and summary["authority"]["sha256"] == manifest["audit_sha256"], "Summary scope differs")
    monthly, periods = summary["monthly"], summary["periods"]
    require(len(monthly) == manifest["monthly_rows"] == 144
            and len(periods) == manifest["period_rows"] == 12, "Group counts differ")
    require({(r["period"], r["mode"], r["ticker"]) for r in monthly}
            == {(p, m, t) for p in MONTHS for m in MODES for t in (*TICKERS, "ALL")}, "Monthly keys differ")
    require({(r["period"], r["mode"], r["ticker"]) for r in periods}
            == {("2025", m, t) for m in MODES for t in (*TICKERS, "ALL")}, "Period keys differ")
    csv_matches(root / "monthly.csv", monthly)
    csv_matches(root / "periods.csv", periods)
    daily = pd.read_csv(root / "daily.csv", dtype={"date": str})
    ledger, attempts = pd.read_parquet(root / "ledger.parquet"), pd.read_parquet(root / "attempts.parquet")
    for frame in (ledger, attempts):
        frame["date"] = frame.date.astype(str)
    require(len(daily) == manifest["daily_rows"] == 2250 and len(ledger) == manifest["ledger_rows"]
            and len(attempts) == manifest["attempt_rows"], "Consolidated row count differs")
    require(not daily.duplicated(["mode", "ticker", "date"]).any()
            and (daily.source_status == "COMPLETE").all()
            and (daily.evaluation_status == "EVALUABLE").all(), "Daily coverage differs")
    require((daily.groupby(["mode", "ticker"]).size() == 250).all(), "Daily ticker counts differ")
    require((ledger.status == "FILLED").all() and attempts.status.isin(["FILLED", "NO_FILL"]).all(), "Fill status differs")
    columns = ["mode", "date", "ticker", "action_id"]
    pd.testing.assert_frame_equal(
        attempts[attempts.status == "FILLED"].sort_values(columns).reset_index(drop=True),
        ledger.sort_values(columns).reset_index(drop=True), check_exact=True)
    for row in monthly + periods:
        filters = []
        for frame in (ledger, daily, attempts):
            mask = (frame["mode"] == row["mode"]) & frame.date.str.startswith(row["period"])
            if row["ticker"] != "ALL":
                mask &= frame.ticker == row["ticker"]
            filters.append(frame[mask])
        reconcile_group(row, *filters)
    by_day = ledger.groupby(["mode", "ticker", "date"], sort=False)
    for row in daily.itertuples():
        key = row.mode, row.ticker, row.date
        frame = by_day.get_group(key) if key in by_day.groups else ledger.iloc[:0]
        require(row.trades == len(frame) and close(row.net_base, sum(frame.net_base))
                and close(row.net_adverse, sum(frame.net_adverse)), "Daily ledger mismatch")

    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, out / Path(__file__).name)
    fig, axes = plt.subplots(3, 3, figsize=(17, 12), sharex=True, layout="constrained")
    colors = ("#176b92", "#b05a23")
    for col, ticker in enumerate(TICKERS):
        rows = [r for r in monthly if r["ticker"] == ticker]
        values = [r["available_economics"][f] for r in rows for f in ("net_base", "net_adverse")]
        low, high = min(0, min(values)), max(0, max(values))
        margin = max((high - low) * .12, 1)
        for row_i, mode in enumerate(MODES):
            ax = axes[row_i, col]
            mapping = {r["period"]: r for r in rows if r["mode"] == mode}
            for offset, field, color, label in ((-.19, "net_base", colors[0], "Base"), (.19, "net_adverse", colors[1], "Adverse")):
                ax.bar([i + offset for i in range(12)], [mapping[m]["available_economics"][field] for m in MONTHS],
                       width=.36, color=color, label=label)
            ax.axhline(0, color="#333333", linewidth=.7)
            ax.set_ylim(low - margin, high + margin)
            ax.set_title(f"{ticker} · {mode}", loc="left", fontsize=12, fontweight="bold")
            ax.set_xticks(range(12), [f"{m:02d}" for m in range(1, 13)])
            ax.set_ylabel("Monthly net PnL (USD)")
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
            ax.grid(axis="y", alpha=.2)
            ax.set_axisbelow(True)
            ax.spines[["top", "right"]].set_visible(False)
            if row_i == 2:
                ax.set_xlabel("Month of 2025")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside upper right", ncols=2, frameon=False)
    fig.suptitle("2025 monthly replay · SEEN DEVELOPMENT\nAll 3 modes × 3 tickers × 12 months · frozen selection: null", fontsize=18, fontweight="bold")
    fig.supxlabel("Audited net USD after stated costs; paired base/adverse scenarios. Same y-scale within each ticker column.\nGiven sealed scores; no prospective/live claim, no promotion, no mode selection by this figure.", fontsize=10)
    figure_name = "monthly_net_usd_all_modes_2025"
    fig.savefig(out / (figure_name + ".png"), dpi=200)
    fig.savefig(out / (figure_name + ".svg"))
    plt.close(fig)
    for path, expected in pinned.items():
        require(sha(path) == expected, "Reporter output changed during reconciliation")
    result = dict(status="PASS_INDEPENDENT_DESCRIPTIVE_RECONCILIATION", scope="CLOSED_REPORTER_OUTPUTS_ONLY",
                  source_outputs=pinned, resource_gate_before=gate,
                  reconciled=dict(ticker_month_mode_groups=108, pooled_month_groups=36,
                                  period_groups=12, daily_rows=2250, ledger_rows=len(ledger), attempt_rows=len(attempts)),
                  metrics_checked=["trades", "base/adverse net", "PF and infinity flag", "win rate", "drawdown",
                                   "holding", "exit reasons", "coverage", "attempts", "daily net"],
                  selected_mode=None, development_seen=True, promotion_approved=False,
                  scientific_reaudit_performed=False, figure=figure_name,
                  limitations=["Only completed reporter outputs were consumed; source audit is inherited by its external pin.",
                               "No source features, scores, labels, models, fit, inference or scheduler replay.",
                               "Observed 2025 development only; this figure is not prospective evidence."])
    write(out / "reconciliation.json", result)
    write(out / "manifest.json", dict(status="COMPLETE", files={p.name: dict(sha256=sha(p), bytes=p.stat().st_size)
          for p in sorted(out.iterdir())}))
    print(json.dumps({"status": result["status"], "output": str(out), "groups": result["reconciled"]}))


if __name__ == "__main__":
    main()
