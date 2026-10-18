"""Independent extension audit given sealed scores; no producer imports."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import time
import traceback

import exchange_calendars as xc
import numpy as np
import pandas as pd

import audit_causal_rollout_economics as independent

require, sha, read_json = independent.require, independent.sha, independent.read_json
DATES = ("20250703", "20251128", "20251224")
TICKERS = independent.TICKERS
SELECTED = "causal_residual__5"
AUDIT_SHA = "6dd69574ed50a5d3d26587b488b347874c40908d55ff8d8b19d2a95d9c581cd3"
SUMMARY_SHA = "cb362fd33b7cfa2f195dc01699861db8ec93f1d22ed14497756a8386af08d89a"
COMPLETION_SHA = "cb24eaa3c1bfd462259a1758d19a4ec588e129edb7e009d9d888f54ed73c607f"
FREEZE_SHA = "a5cda27adeade05f4e8f9577b8fd0e8483eb37690f812342a573b5cab849b6af"
MODEL_SHA = dict(
    net_control="12b8d5a00d06bb482fc6de66263e8c270929d0d276e226a9889e283a801a09ef",
    causal_residual="9fe6a42d2a04459b5eff4b018518a224865b58f2af89ca5903b6e77651303117",
)


def publish_json(path, payload):
    """Publish only a fully flushed audit; preserve a failed temporary file."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    require(not path.exists() and not temporary.exists(), "New audit artifact required")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class Seal:
    def __init__(self):
        self.files = {}

    def check(self, path, digest=None):
        path = Path(path).resolve()
        actual = sha(path)
        require(digest is None or actual == digest, "Hash mismatch: " + str(path))
        require(
            str(path) not in self.files or self.files[str(path)] == actual,
            "Changed input",
        )
        self.files[str(path)] = actual
        return path

    def recheck(self):
        for path, digest in self.files.items():
            require(sha(path) == digest, "Final hash mismatch: " + path)


def verify_marker(root, name, binding, seal, members):
    marker = read_json(seal.check(root / (name + ".complete.json")))
    require(
        marker["status"] == "COMPLETE" and marker["binding"] == binding,
        "Marker binding",
    )
    paths = {}
    for relative, digest in marker["files"].items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root), "Escaping marker")
        paths[path] = digest
        seal.check(path, digest)
    require(set(paths) == {p.resolve() for p in members}, "Exact marker membership")
    return marker


def scores_checked(actions, packed):
    expected = {"action_id", "state_i", *MODEL_SHA, *(m + "_sha256" for m in MODEL_SHA)}
    require(set(packed) == expected, "Prediction keys")
    for key in ("action_id", "state_i"):
        require(np.array_equal(packed[key], actions[key]), "Prediction identity")
    for model, digest in MODEL_SHA.items():
        require(str(packed[model + "_sha256"]) == digest, "Prediction model")
        require(
            packed[model].shape == (len(actions), 2)
            and np.isfinite(packed[model]).all(),
            "Prediction values",
        )


def schedule(actions, labels, scores, threshold):
    require(actions.state_i.between(60, 195).all(), "Short state bounds")
    # Independent full-session primitive freezes rankings without reading labels;
    # the short wrapper rejects all actions outside195 and truncates empty tail.
    choices = independent.ranked_choices(actions, scores, threshold)[:136]
    lab = independent.aligned(actions, labels)
    require(
        (lab.loc[lab.status == "FILLED", "exit_i"] <= 205).all(), "Short exit bounds"
    )
    lookup = {int(key): i for i, key in enumerate(actions.action_id)}
    rows, flags, values = [], [], []
    minute, flag = 60, 0
    while minute <= 195:
        identity = int(choices[minute - 60, flag])
        if identity == -1:
            minute += 1
            continue
        row = lookup[identity]
        rows.append(row)
        flags.append(flag)
        values.append(float(scores[row, flag]))
        if lab.status.iloc[row] == "FILLED":
            flag, minute = 1, int(lab.exit_i.iloc[row]) + 1
        else:
            minute += 1
    attempted = actions.iloc[rows].merge(
        lab.iloc[rows], on="action_id", validate="one_to_one"
    )
    attempted["has_filled_before"] = np.asarray(flags, dtype=np.int64)
    attempted["score"] = np.asarray(values, dtype=np.float64)
    return attempted, attempted.loc[attempted.status == "FILLED"].copy()


def check_costs(labels):
    fill = labels.status == "FILLED"
    for col, slip in (("net_base", 0.01), ("net_adverse", 0.02)):
        expected = (
            np.maximum(labels.loc[fill, "exit_bid"].to_numpy(float) - slip, 0)
            - labels.loc[fill, "entry_ask"].to_numpy(float)
            - slip
        ) * 100 - 2.60
        require(
            np.allclose(expected, labels.loc[fill, col], rtol=0, atol=1e-8),
            "Execution costs",
        )
        require((labels.loc[~fill, col] == 0).all(), "NO_FILL cost")


def check_calendar(frame, expected):
    require(
        not frame.duplicated(["policy", "ticker", "date"]).any(), "Duplicate calendar"
    )
    require(set(frame.policy) == set(independent.POLICIES), "Calendar policies")
    for policy in independent.POLICIES:
        sub = frame.loc[frame.policy == policy]
        require(set(zip(sub.ticker, sub.date)) == set(expected), "Calendar population")
        require(sub.source_available.all(), "Missing extension source")


def run(root, out, original_audit):
    started = time.perf_counter()
    seal = Seal()
    script = Path(__file__).resolve()
    for path in (
        script,
        script.with_name("CAUSAL_SHORT_ECONOMIC_AUDIT_SPEC.md"),
        Path(independent.__file__),
    ):
        seal.check(path)
    contract = read_json(seal.check(root / "run_contract.json"))
    binding = sha(root / "run_contract.json")
    completion = read_json(seal.check(root / "completion.json", COMPLETION_SHA))
    summary = read_json(seal.check(root / "summary.json", SUMMARY_SHA))
    require(
        completion["status"] == "CAUSAL_ROLLOUT_SHORT_SESSIONS_COMPLETE"
        and completion["binding"] == binding,
        "Closure status",
    )
    declared = {(root / p).resolve() for p in completion["files"]}
    require(
        len(declared) == 72 and root / "completion.json" not in declared,
        "Closure72 plus completion",
    )
    expected_members = {root / "run_contract.json"}
    for name, suffixes in [
        ("summary", [".json"]),
        ("source_hashes", [".json"]),
        ("short_daily_calendar", [".parquet"]),
        ("combined_daily_calendar", [".parquet"]),
    ]:
        expected_members.update(
            root / (name + suffix) for suffix in [*suffixes, ".complete.json"]
        )
    for ticker in TICKERS:
        for date in DATES:
            for prefix, suffixes in [
                ("predictions", [".npz"]),
                ("daily", ["_attempts.parquet", "_ledger.parquet"]),
                ("feature_inputs", [".json"]),
            ]:
                expected_members.update(
                    root / f"{prefix}/{ticker}/{date}{suffix}"
                    for suffix in [*suffixes, ".complete.json"]
                )
    require(declared == expected_members, "Exact closure paths")
    for p, digest in completion["files"].items():
        path = (root / p).resolve()
        require(path.is_relative_to(root), "Escaping closure")
        seal.check(path, digest)
    verify_marker(
        root, "completion", binding, seal, [*declared, root / "completion.json"]
    )
    for name, digest in contract["dependencies"].items():
        seal.check(script.with_name(name), digest)
    audit = read_json(seal.check(original_audit, AUDIT_SHA))
    require(
        audit["status"]
        == "PASS_INDEPENDENT_CAUSAL_ROLLOUT_ECONOMIC_AUDIT_GIVEN_SEALED_SCORES",
        "Original audit status",
    )
    original_root = Path(contract["original_root"]).resolve()
    seal.check(original_root / "run_contract.json", contract["original_run_sha256"])
    require(
        audit["run_contract_sha256"] == contract["original_run_sha256"],
        "Original run audit binding",
    )
    require(
        contract["original_audit_sha256"] == AUDIT_SHA
        and contract["selection_freeze_sha256"] == FREEZE_SHA,
        "Authority binding",
    )
    freeze = read_json(seal.check(original_root / "validation_freeze.json", FREEZE_SHA))
    require(
        freeze["selected_policy"]["policy"] == SELECTED
        and contract["selected_policy"] == SELECTED
        and not contract["selection_recomputed"],
        "Frozen selection",
    )
    require(
        contract["model_hashes"] == MODEL_SHA and freeze["model_hashes"] == MODEL_SHA,
        "Fixed models",
    )
    for model, digest in MODEL_SHA.items():
        seal.check(original_root / "models" / (model + ".txt"), digest)
    sources = read_json(root / "source_hashes.json")
    require(set(sources) == {"source", "original"}, "Source groups")
    for group in sources.values():
        for path, digest in group.items():
            seal.check(path, digest)
    for path, digest in sources["original"].items():
        require(
            audit["verified_artifacts"].get(str(Path(path).resolve())) == digest,
            "Original audit membership",
        )
    source_info = contract["source_audit"]
    source_audit = read_json(seal.check(source_info["path"], source_info["sha256"]))
    require(
        source_audit["status"] == "PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT",
        "Source audit",
    )
    independent.equal(source_audit["binding"], source_info["binding"], "Source binding")
    engine = Path(source_info["binding"]["engine_root"])
    for filename, field in (
        ("dataset_contract.json", "dataset_contract_sha256"),
        ("completion.json", "completion_sha256"),
        ("feature_contract.json", "feature_contract_sha256"),
    ):
        seal.check(engine / filename, source_info["binding"][field])
    index = pd.read_parquet(
        seal.check(engine / "index.parquet", source_info["binding"]["index_sha256"])
    )
    index["date"] = index.date.astype(str)
    require(not index.duplicated(["ticker", "date"]).any(), "Duplicate index")
    sessions = xc.get_calendar("XNYS").sessions_in_range("2025-01-01", "2025-12-31")
    dates = [d.strftime("%Y%m%d") for d in sessions]
    require(len(dates) == 250, "XNYS250")
    expected = {(t, d) for t in TICKERS for d in dates}
    short = {(t, d) for t in TICKERS for d in DATES}
    require(
        {(d["ticker"], d["date"]) for d in contract["days"]} == short
        and len(contract["days"]) == 9,
        "Nine declared days",
    )
    available = index.loc[index.date.str.startswith("2025")]
    require(
        set(zip(available.ticker, available.date)) == expected
        and available.status.eq("COMPLETE").all(),
        "Exact750 complete index",
    )
    require(
        set(
            zip(
                available.loc[available.close_i == 210, "ticker"],
                available.loc[available.close_i == 210, "date"],
            )
        )
        == short,
        "Short clock population",
    )
    short_attempts, short_ledgers, old_attempts, old_ledgers = [], [], [], []
    for ticker, date in sorted(short):
        row = available.loc[
            (available.ticker == ticker) & (available.date == date)
        ].iloc[0]
        day = Path(row.day_root)
        actions = pd.read_parquet(
            seal.check(day / "actions.parquet", row.actions_sha256)
        )
        labels = pd.read_parquet(seal.check(day / "labels.parquet", row.labels_sha256))
        check_costs(labels)
        key = ticker + "/" + date
        pred = root / ("predictions/" + key + ".npz")
        pm = verify_marker(root, "predictions/" + key, binding, seal, [pred])
        with np.load(pred, allow_pickle=False) as archive:
            packed = {k: archive[k] for k in archive.files}
        scores_checked(actions, packed)
        paths = [
            root / ("daily/" + key + s)
            for s in ("_attempts.parquet", "_ledger.parquet")
        ]
        dm = verify_marker(root, "daily/" + key, binding, seal, paths)
        require(dm["extra"]["prediction_sha256"] == sha(pred), "Daily prediction hash")
        independent.equal(
            dm["extra"]["clock"],
            dict(
                close_i=210,
                n_slots=211,
                first_state=60,
                last_state=195,
                eod_i=205,
                time_unit_minutes=390,
            ),
            "Clock",
        )
        independent.before(pm, dm, "Predictions before daily")
        tries, trades = [], []
        for model in independent.MODELS:
            for threshold in independent.THRESHOLDS:
                attempted, ledger = schedule(actions, labels, packed[model], threshold)
                for frame in (attempted, ledger):
                    frame["ticker"], frame["date"], frame["policy"] = (
                        ticker,
                        date,
                        f"{model}__{int(threshold)}",
                    )
                tries.append(attempted)
                trades.append(ledger)
        tries, trades = (
            pd.concat(tries, ignore_index=True),
            pd.concat(trades, ignore_index=True),
        )
        independent.frame_equal(tries, pd.read_parquet(paths[0]), key + " attempts")
        independent.frame_equal(trades, pd.read_parquet(paths[1]), key + " ledger")
        short_attempts.append(tries)
        short_ledgers.append(trades)
        print(
            json.dumps(dict(stage="short_day_verified", ticker=ticker, date=date)),
            flush=True,
        )
    for ticker, date in sorted(expected - short):
        name = f"validation/daily/{ticker}/{date}"
        marker_path = original_root / (name + ".complete.json")
        seal.check(marker_path, audit["verified_artifacts"][str(marker_path)])
        marker = read_json(marker_path)
        require(
            marker["binding"] == contract["original_run_sha256"],
            "Original marker binding",
        )
        frames = []
        for suffix in ("_attempts.parquet", "_ledger.parquet"):
            path = original_root / (name + suffix)
            seal.check(path, audit["verified_artifacts"][str(path)])
            require(
                marker["files"][str(path.relative_to(original_root))] == sha(path),
                "Original membership",
            )
            frames.append(pd.read_parquet(path))
        old_attempts.append(frames[0])
        old_ledgers.append(frames[1])
    all_short_a, all_short_l = (
        pd.concat(short_attempts, ignore_index=True),
        pd.concat(short_ledgers, ignore_index=True),
    )
    reports = {}
    for group, attempts, ledger, days, calendar_name in (
        ("short_sessions", all_short_a, all_short_l, short, "short_daily_calendar"),
        (
            "combined_2025",
            pd.concat([*old_attempts, all_short_a], ignore_index=True),
            pd.concat([*old_ledgers, all_short_l], ignore_index=True),
            expected,
            "combined_daily_calendar",
        ),
    ):
        report, calendar = independent.summarize_period(
            attempts, ledger, sorted(days), days
        )
        independent.equal(report, summary[group], group)
        actual = pd.read_parquet(root / (calendar_name + ".parquet"))
        check_calendar(actual, days)
        independent.frame_equal(calendar, actual, calendar_name)
        reports[group] = report[SELECTED]
    old_path = original_root / "validation/daily_calendar.parquet"
    seal.check(old_path, audit["verified_artifacts"][str(old_path)])
    old_calendar = pd.read_parquet(old_path)
    combined = pd.read_parquet(root / "combined_daily_calendar.parquet")
    preserved = combined.loc[~combined.date.isin(DATES)]
    independent.frame_equal(old_calendar, preserved, "Original741 preserved")
    require(
        summary["selected_policy"] == SELECTED
        and summary["selection_recomputed"] is False
        and summary["selection_freeze_sha256"] == FREEZE_SHA
        and summary["terminal_penalty_in_pnl"] is False
        and summary["development_2026_unchanged"] is True,
        "Report authority",
    )
    require(
        summary["status"] == "INFERENCE_EXTENSION_COMPLETE"
        and summary["original_ticker_days"] == 741
        and summary["added_ticker_days"] == 9
        and summary["combined_ticker_days"] == 750
        and summary["training_early_close_days_added"] == 0,
        "Summary coverage",
    )
    seal.recheck()
    result = dict(
        status="PASS_INDEPENDENT_CAUSAL_SHORT_ECONOMIC_AUDIT_GIVEN_SEALED_SCORES",
        completed_utc=datetime.now(timezone.utc).isoformat(),
        wall_seconds=time.perf_counter() - started,
        extension_root=str(root),
        summary_sha256=SUMMARY_SHA,
        completion_sha256=COMPLETION_SHA,
        original_audit_sha256=AUDIT_SHA,
        selected_policy=SELECTED,
        selection_recomputed=False,
        short_days=9,
        original_days=741,
        combined_days=750,
        policies=6,
        closure_members=73,
        independent_refits=0,
        regenerated_predictions=0,
        raw_quote_barrier_replay=False,
        selected_results=reports,
        verified_artifacts=seal.files,
    )
    publish_json(out / "audit.json", result)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ("verified_artifacts", "selected_results")
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--original-audit", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    try:
        run(args.root.resolve(), args.out.resolve(), args.original_audit)
    except Exception:
        (args.out / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
