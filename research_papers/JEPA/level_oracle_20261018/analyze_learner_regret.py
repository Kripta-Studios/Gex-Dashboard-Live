"""Post-completion descriptive regret of the single validation-selected policy.

No model fitting, prediction, raw-market reads, or policy selection. Hindsight
regret is NOT a loss known to be avoidable with causal information. The only
economic labels read are completed, audited oracle sidecars and learner attempts.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

FIRST, LAST = 60, 375
TICKERS = ("SPXW", "SPY", "QQQ")
COMPONENTS = ("wait", "no_fill", "entry_timing", "side", "contract", "target")
ATOL = 1e-7


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(left, right, message, tolerance=ATOL):
    require(bool(np.isclose(left, right, rtol=0, atol=tolerance)), message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")


def decompose_day(actions, labels, values, attempts, first=FIRST, last=LAST):
    """Verify Bellman identities, then follow actual attempts including no-fills.

    For FILLED attempts, nested comparison is all trades -> same side -> same
    contract -> chosen target. Attribution depends on this declared ordering.
    WAIT and NO_FILL both advance one decision minute. Filled trades advance to
    exit+1. Unvisited minutes while a position is open are never charged again.
    """
    required = {"action_id", "state_i", "right", "contract_i", "target_level_id"}
    require(required <= set(actions), "Missing causal action columns")
    require(
        {"action_id", "status", "exit_i", "net_base"} <= set(labels), "Missing labels"
    )
    require(not actions.action_id.duplicated().any(), "Duplicate action IDs")
    require(not labels.action_id.duplicated().any(), "Duplicate label IDs")
    require(
        set(actions.action_id) == set(labels.action_id), "Action-label universe differs"
    )
    joined = actions.merge(labels, on="action_id", validate="one_to_one").sort_values(
        "action_id"
    )
    require(joined.status.isin(["FILLED", "NO_FILL"]).all(), "Unknown fill status")
    values = np.asarray(values, dtype=np.float64)
    require(
        values.ndim == 1 and len(values) > last + 1 and np.isfinite(values).all(),
        "Bad value array",
    )
    require(
        np.all(np.abs(values[last + 1 :]) <= ATOL),
        "Nonzero value after last opportunity",
    )
    require(np.isfinite(joined.net_base.to_numpy(float)).all(), "Nonfinite payoff")
    require(joined.state_i.between(first, last).all(), "Action outside decision range")
    filled = joined.status.eq("FILLED").to_numpy()
    states = joined.state_i.to_numpy(int)
    exits = joined.exit_i.to_numpy(int)
    nets = joined.net_base.to_numpy(float)
    require(
        np.all((exits >= states + np.where(filled, 2, 1)) & (exits + 1 < len(values))),
        "Invalid chronology",
    )
    require(np.all(exits[~filled] == states[~filled] + 1), "No-fill clock differs")
    require(np.all(nets[~filled] == 0), "No-fill has economic reward")
    q = values[states + 1].copy()
    q[filled] = nets[filled] + values[exits[filled] + 1]
    joined["hindsight_q"] = q
    best_trade = np.full(len(values), -np.inf)
    np.maximum.at(best_trade, states[filled], q[filled])
    expected = np.maximum(values[first + 1 : last + 2], best_trade[first : last + 1])
    require(
        np.allclose(values[first : last + 1], expected, rtol=0, atol=ATOL),
        "Value/sidecar Bellman mismatch",
    )

    if len(attempts):
        require(
            {"action_id", "state_i", "status", "exit_i", "net_base"} <= set(attempts),
            "Incomplete attempts",
        )
        require(not attempts.action_id.duplicated().any(), "Repeated attempted action")
        require(
            not attempts.state_i.duplicated().any(), "Multiple attempts at same state"
        )
        require(
            set(attempts.action_id) <= set(joined.action_id),
            "Attempt outside offered universe",
        )
    indexed = joined.set_index("action_id", drop=False)
    attempted = {int(row.state_i): row for row in attempts.itertuples(index=False)}
    groups = {int(i): frame for i, frame in joined.groupby("state_i", sort=True)}
    events, used = [], set()
    minute, pnl = first, 0.0
    while minute <= last:
        row = attempted.get(minute)
        loss = {name: 0.0 for name in COMPONENTS}
        net, action_id, side, contract, target, score = 0.0, -1, -1, -1, -1, np.nan
        optimal_value, rank = False, -1
        if row is None:
            kind, next_i = "WAIT", minute + 1
            chosen_q = float(values[next_i])
            loss["wait"] = float(values[minute] - chosen_q)
        else:
            action_id = int(row.action_id)
            chosen = indexed.loc[action_id]
            require(int(chosen.state_i) == minute, "Attempt state mismatches action")
            require(
                row.status == chosen.status and int(row.exit_i) == int(chosen.exit_i),
                "Attempt fill/exit mismatch",
            )
            same(float(row.net_base), float(chosen.net_base), "Attempt payoff mismatch")
            for field in ("right", "contract_i", "target_level_id"):
                if hasattr(row, field):
                    require(
                        int(getattr(row, field)) == int(chosen[field]),
                        "Attempt identity mismatch: " + field,
                    )
            used.add(action_id)
            side, contract, target = (
                int(chosen.right),
                int(chosen.contract_i),
                int(chosen.target_level_id),
            )
            score = float(getattr(row, "score", np.nan))
            if chosen.status == "NO_FILL":
                kind, next_i = "NO_FILL", minute + 1
                chosen_q = float(values[next_i])
                loss["no_fill"] = float(values[minute] - chosen_q)
            else:
                kind, next_i = "FILLED", int(chosen.exit_i) + 1
                net = float(chosen.net_base)
                chosen_q = net + float(values[next_i])
                offered = groups[minute].loc[groups[minute].status == "FILLED"]
                same_side = offered.loc[offered.right == side]
                same_contract = same_side.loc[same_side.contract_i == contract]
                all_q = float(offered.hindsight_q.max())
                side_q = float(same_side.hindsight_q.max())
                contract_q = float(same_contract.hindsight_q.max())
                loss.update(
                    entry_timing=float(values[minute] - all_q),
                    side=all_q - side_q,
                    contract=side_q - contract_q,
                    target=contract_q - chosen_q,
                )
                rank = 1 + int((offered.hindsight_q > chosen_q + ATOL).sum())
                optimal_value = bool(abs(values[minute] - chosen_q) <= ATOL)
        regret = float(values[minute] - chosen_q)
        require(
            min(loss.values()) >= -ATOL and regret >= -ATOL, "Negative hindsight regret"
        )
        same(sum(loss.values()), regret, "Component regret mismatch")
        events.append(
            dict(
                state_i=minute,
                next_i=next_i,
                decision=kind,
                action_id=action_id,
                right=side,
                contract_i=contract,
                target_level_id=target,
                score=score,
                offered_actions=len(groups.get(minute, ())),
                net_base=net,
                oracle_value=float(values[minute]),
                chosen_hindsight_q=chosen_q,
                hindsight_regret_usd=regret,
                hindsight_trade_rank=rank,
                hindsight_optimal_value=optimal_value,
                **{name + "_regret_usd": value for name, value in loss.items()},
            )
        )
        pnl += net
        minute = next_i
    require(
        used == set(attempts.action_id) if len(attempts) else not used,
        "Attempt occurs while busy/outside traversal",
    )
    frame = pd.DataFrame(events)
    total = float(frame.hindsight_regret_usd.sum())
    difference = float(values[first] - pnl)
    same(float(values[minute]), 0.0, "Nonzero terminal continuation")
    same(total, difference, "Telescoping failed", 1e-6)
    summary = dict(
        oracle_net_base=float(values[first]),
        learner_net_base=pnl,
        hindsight_gap_usd=difference,
        component_sum_usd=total,
        telescoping_error_usd=total - difference,
        visited_states=len(frame),
        filled_trades=int(frame.decision.eq("FILLED").sum()),
        no_fill_attempts=int(frame.decision.eq("NO_FILL").sum()),
        wait_decisions=int(frame.decision.eq("WAIT").sum()),
        positive_regret_waits=int(
            ((frame.decision == "WAIT") & (frame.hindsight_regret_usd > ATOL)).sum()
        ),
        filled_hindsight_optimal_count=int(frame.hindsight_optimal_value.sum()),
        **{
            name + "_regret_usd": float(frame[name + "_regret_usd"].sum())
            for name in COMPONENTS
        },
    )
    return frame, summary


def load_authorities(learner_root, engine_root):
    """Fail before any labels are opened if learners have not fully completed."""
    result = json.loads((learner_root / "summary.json").read_text(encoding="utf-8"))
    require(
        result.get("status") == "COMPLETED_CAUSAL_LEARNER_DEVELOPMENT",
        "Learners must finish before diagnostics",
    )
    freeze = json.loads((learner_root / "freeze.json").read_text(encoding="utf-8"))
    require(
        result["selected_policy"] == freeze["selected_policy"],
        "Selected policy differs from freeze",
    )
    audit = freeze["oracle_audit"]
    require(
        audit["status"] == "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT",
        "Full oracle audit required",
    )
    require(
        Path(audit["binding"]["engine_root"]).resolve() == engine_root.resolve(),
        "Different oracle root",
    )
    require(
        sha(engine_root / "index.parquet") == audit["binding"]["index_sha256"],
        "Changed audited index",
    )
    for path, digest in audit["verified_files"].items():
        require(
            sha(Path(path)) == digest,
            "Changed full oracle audit authority: " + path,
        )
    for name, digest in freeze["artifacts"].items():
        require(
            sha(learner_root / name) == digest,
            "Changed frozen learner artifact: " + name,
        )
    test = json.loads(
        (learner_root / "test" / "summary.json").read_text(encoding="utf-8")
    )
    policy = result["selected_policy"]["policy"]
    expected = None if policy == "CASH" else test[policy]
    require(
        result["selected_test"] == expected,
        "Selected test summary differs from completed learner summary",
    )
    return result, freeze


def check_ledger(attempts, ledger):
    columns = ["action_id", "state_i", "exit_i", "net_base"]
    actual = (
        attempts.loc[attempts.status == "FILLED", columns]
        .sort_values("state_i")
        .reset_index(drop=True)
    )
    expected = ledger[columns].sort_values("state_i").reset_index(drop=True)
    pd.testing.assert_frame_equal(
        actual, expected, check_dtype=False, atol=ATOL, rtol=0
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--learner-root", type=Path, required=True)
    parser.add_argument("--engine-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result, freeze = load_authorities(args.learner_root, args.engine_root)
    selected = result["selected_policy"]["policy"]
    index = pd.read_parquet(args.engine_root / "index.parquet")
    index["date"] = index.date.astype(str)
    require(not index.duplicated(["ticker", "date"]).any(), "Duplicate calendar keys")
    calendar = pd.read_csv(
        args.learner_root / "expected_full_calendar.csv", dtype={"date": str}
    ).date
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.output / "analyze_learner_regret.executed.py")
    sources = {}

    def record(path, expected=None):
        value = sha(path)
        require(
            expected is None or value == expected,
            "Changed diagnostic source: " + str(path),
        )
        sources[str(path.resolve())] = value

    for path in (
        args.learner_root / "summary.json",
        args.learner_root / "freeze.json",
        args.engine_root / "index.parquet",
        args.learner_root / "expected_full_calendar.csv",
    ):
        record(path)
    record(
        args.engine_root / "index.parquet",
        freeze["oracle_audit"]["binding"]["index_sha256"],
    )
    for path, digest in freeze["oracle_audit"]["verified_files"].items():
        record(Path(path), digest)
    daily = []
    writer = None
    try:
        for period, lower, upper in (
            ("validation", "20250101", "20260101"),
            ("test", "20260101", "20260701"),
        ):
            subset = index.loc[
                (index.date >= lower) & (index.date < upper)
            ].sort_values(["date", "ticker"])
            dates = calendar.loc[(calendar >= lower) & (calendar < upper)]
            require(
                set(zip(subset.ticker, subset.date))
                == {(t, d) for t in TICKERS for d in dates},
                "Incomplete diagnostic calendar",
            )
            metrics_path = args.learner_root / period / "summary.json"
            record(metrics_path)
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            if selected == "CASH":
                attempts = pd.DataFrame(
                    columns=[
                        "ticker",
                        "date",
                        "action_id",
                        "state_i",
                        "status",
                        "exit_i",
                        "net_base",
                    ]
                )
                ledger = attempts.copy()
            else:
                attempt_path = (
                    args.learner_root / period / (selected + "_attempts.parquet")
                )
                ledger_path = (
                    args.learner_root / period / (selected + "_ledger.parquet")
                )
                record(attempt_path)
                record(ledger_path)
                attempts, ledger = (
                    pd.read_parquet(attempt_path),
                    pd.read_parquet(ledger_path),
                )
                require(
                    attempts.policy.eq(selected).all()
                    and ledger.policy.eq(selected).all(),
                    "Mixed policy rows",
                )
                attempts["date"], ledger["date"] = (
                    attempts.date.astype(str),
                    ledger.date.astype(str),
                )
                require(
                    set(zip(attempts.ticker, attempts.date))
                    <= set(zip(subset.ticker, subset.date)),
                    "Attempt outside calendar",
                )
                require(
                    set(zip(ledger.ticker, ledger.date))
                    <= set(zip(subset.ticker, subset.date)),
                    "Ledger outside calendar",
                )
            by_attempt = {
                key: frame
                for key, frame in attempts.groupby(["ticker", "date"], sort=False)
            }
            by_ledger = {
                key: frame
                for key, frame in ledger.groupby(["ticker", "date"], sort=False)
            }
            for row in subset.itertuples(index=False):
                key = (row.ticker, row.date)
                actual = by_attempt.get(key, attempts.iloc[:0])
                executed = by_ledger.get(key, ledger.iloc[:0])
                check_ledger(actual, executed)
                if row.status == "MISSING_SOURCE":
                    require(
                        not len(actual) and not len(executed),
                        "Trades on missing source day",
                    )
                    summary = {
                        name: 0.0
                        for name in (
                            "oracle_net_base",
                            "learner_net_base",
                            "hindsight_gap_usd",
                            "component_sum_usd",
                            "telescoping_error_usd",
                        )
                    }
                    summary.update(
                        {
                            name: 0
                            for name in (
                                "visited_states",
                                "filled_trades",
                                "no_fill_attempts",
                                "wait_decisions",
                                "positive_regret_waits",
                                "filled_hindsight_optimal_count",
                            )
                        }
                    )
                    summary.update({name + "_regret_usd": 0.0 for name in COMPONENTS})
                else:
                    require(row.status == "COMPLETE", "Incomplete oracle day")
                    root = Path(row.day_root)
                    require(
                        root.resolve()
                        == (args.engine_root / row.ticker / row.date).resolve(),
                        "Oracle day root mismatch",
                    )
                    for filename, field in (
                        ("actions.parquet", "actions_sha256"),
                        ("labels.parquet", "labels_sha256"),
                        ("oracle_value.npy", "oracle_value_sha256"),
                    ):
                        record(root / filename, getattr(row, field))
                    actions = pd.read_parquet(root / "actions.parquet")
                    labels = pd.read_parquet(root / "labels.parquet")
                    values = np.load(root / "oracle_value.npy", allow_pickle=False)
                    events, summary = decompose_day(actions, labels, values, actual)
                    same(
                        summary["oracle_net_base"],
                        row.net_base,
                        "Oracle index/value disagreement",
                    )
                    (
                        events["ticker"],
                        events["date"],
                        events["period"],
                        events["policy"],
                    ) = row.ticker, row.date, period, selected
                    table = pa.Table.from_pandas(events, preserve_index=False)
                    if writer is None:
                        writer = pq.ParquetWriter(
                            args.output / "visited_decisions.parquet",
                            table.schema,
                            compression="zstd",
                        )
                    writer.write_table(table)
                daily.append(
                    dict(
                        ticker=row.ticker,
                        date=row.date,
                        period=period,
                        status=row.status,
                        policy=selected,
                        **summary,
                    )
                )
            for ticker in TICKERS:
                part = [
                    r for r in daily if r["period"] == period and r["ticker"] == ticker
                ]
                expected_net = (
                    0.0
                    if selected == "CASH"
                    else metrics[selected]["tickers"][ticker]["base_net_usd"]
                )
                expected_trades = (
                    0
                    if selected == "CASH"
                    else metrics[selected]["tickers"][ticker]["trades"]
                )
                same(
                    sum(r["learner_net_base"] for r in part),
                    expected_net,
                    "Learner summary disagreement",
                    1e-5,
                )
                require(
                    sum(r["filled_trades"] for r in part) == expected_trades,
                    "Learner trade count disagreement",
                )
    finally:
        if writer is not None:
            writer.close()
    frame = pd.DataFrame(daily)
    frame.to_parquet(args.output / "daily_regret.parquet", index=False)
    totals = {}
    for (period, ticker), group in frame.groupby(["period", "ticker"], sort=True):
        fields = [
            "oracle_net_base",
            "learner_net_base",
            "hindsight_gap_usd",
            "component_sum_usd",
            *[name + "_regret_usd" for name in COMPONENTS],
        ]
        totals[period + "/" + ticker] = {
            name: float(group[name].sum()) for name in fields
        }
        totals[period + "/" + ticker].update(
            days=len(group),
            missing_source_days=int(group.status.eq("MISSING_SOURCE").sum()),
        )
    for path, digest in sources.items():
        require(sha(path) == digest, "Input changed during diagnostics: " + path)
    write_json(
        args.output / "manifest.json", dict(sources=sources, code_sha256=sha(__file__))
    )
    write_json(
        args.output / "summary.json",
        dict(
            status="COMPLETED_DESCRIPTIVE_HINDSIGHT_REGRET",
            selected_policy=selected,
            completed_utc=datetime.now(timezone.utc).isoformat(),
            totals=totals,
            maximum_daily_telescoping_error_usd=float(
                frame.telescoping_error_usd.abs().max()
            ),
            source_hash_mismatch=0,
            policy_changed=False,
            new_predictions=False,
            refits=0,
            cost_basis="base only; oracle value is base-cost DP",
            attribution_order="WAIT/NO_FILL; for FILLED: entry timing, side, contract, target",
            interpretation="Retrospective gap to privileged oracle, NOT a causally avoidable loss or attainable improvement",
        ),
    )
    print("COMPLETED_DESCRIPTIVE_HINDSIGHT_REGRET", flush=True)


if __name__ == "__main__":
    main()
