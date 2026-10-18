"""Predeclared 96-TRAIN/741-validation quote diagnostic panel."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from diagnose_oracle_quote_anomalies import (
    contract_lookup,
    observation,
    relative_comparison,
    sha256,
    summarize,
)


def require(value, message):
    if not bool(value):
        raise AssertionError(message)


def control_attempts(states: pd.DataFrame, actions: pd.DataFrame,
                     labels: pd.DataFrame) -> pd.DataFrame:
    chosen = states.loc[
        states.model_free.astype(bool) & (states.model_action_id.astype(int) >= 0),
        ["state_i", "model_action_id", "model_filled"],
    ].rename(columns={"model_action_id": "action_id"})
    require(not chosen.action_id.duplicated().any(), "Repeated control attempt")
    joined = chosen.merge(actions[["action_id", "state_i", "entry_i", "contract_i"]],
                          on="action_id", suffixes=("_selected", "_action"), validate="one_to_one")
    joined = joined.merge(labels[["action_id", "status", "exit_i"]],
                          on="action_id", validate="one_to_one")
    require(np.array_equal(joined.state_i_selected, joined.state_i_action), "Control state join")
    require(np.array_equal(joined.model_filled.astype(bool), joined.status.eq("FILLED")),
            "Control fill status")
    return joined


def verify_checkpoint(path: Path, artifact: Path, identity_sha: str, day_key: str) -> dict:
    record = json.loads(path.read_text(encoding="utf-8"))
    require(record["identity"] == identity_sha and record["day_key"] == day_key,
            "Control checkpoint identity")
    require(record["artifacts"].get(str(artifact.resolve())) == sha256(artifact),
            "Control state artifact hash")
    return record


def grouped_summary(observations: pd.DataFrame) -> dict:
    output = {}
    for (split, ticker, population), frame in observations.groupby(
        ["split", "ticker", "population"], sort=True
    ):
        output[f"{split}/{ticker}/{population}"] = summarize(frame)
    for (split, population), frame in observations.groupby(["split", "population"], sort=True):
        output[f"{split}/ALL/{population}"] = summarize(frame)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-root", type=Path, required=True)
    parser.add_argument("--oracle-audit", type=Path, required=True)
    parser.add_argument("--diagnostic-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Fresh output root required")

    audit = json.loads(args.oracle_audit.read_text(encoding="utf-8"))
    require(audit["status"] == "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT", "Oracle audit")
    index_path = args.engine_root / "index.parquet"
    require(sha256(index_path) == audit["binding"]["index_sha256"], "Index authority")
    identity_path = args.diagnostic_root / "identity.json"
    summary_path = args.diagnostic_root / "summary.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    diagnostic_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    require(diagnostic_summary["status"] == "COMPLETE_DESCRIPTIVE_ORACLE_MODEL_DIAGNOSTIC",
            "Control diagnostic incomplete")
    require(diagnostic_summary["identity"] == identity, "Control identity differs")
    identity_sha = sha256(identity_path)
    selection_path = args.diagnostic_root / "training_days_preinference.csv"
    require(sha256(selection_path) == identity["training_selection_sha256"], "TRAIN selection hash")
    selection = pd.read_csv(selection_path, dtype={"date": str})
    require(len(selection) == 96, "TRAIN selection count")
    train_keys = set(zip(selection.ticker, selection.date, strict=True))

    index = pd.read_parquet(index_path)
    index["date"] = index.date.astype(str)
    selected = index.loc[
        ((index.split == "validation") & (index.status == "COMPLETE"))
        | pd.Series([(row.ticker, row.date) in train_keys for row in index.itertuples()], index=index.index)
    ].copy()
    require(len(selected) == 837, "Expected 96 TRAIN plus 741 validation days")
    require(int((selected.split == "train").sum()) == 96
            and int((selected.split == "validation").sum()) == 741, "Split coverage")

    rows, daily, consumed = [], [], []
    for number, day in enumerate(selected.sort_values(["split", "ticker", "date"]).itertuples(), 1):
        split = "validation" if day.split == "validation" else "train"
        day_root = Path(day.day_root)
        paths = {name: day_root / name for name in
                 ("actions.parquet", "labels.parquet", "oracle_ledger.parquet")}
        for name, path in paths.items():
            require(sha256(path) == getattr(day, name.removesuffix(".parquet") + "_sha256"),
                    "Engine day hash " + name)
        cache_path = Path(day.cache_path)
        require(sha256(cache_path) == day.cache_npz_sha256, "Cache day hash")
        prefix = f"{day.ticker}_{day.date}"
        state_path = args.diagnostic_root / split / f"{prefix}_gbt_net.parquet"
        checkpoint = args.diagnostic_root / split / f"{prefix}.complete.json"
        verify_checkpoint(checkpoint, state_path, identity_sha, f"{day.ticker}/{day.date}")
        actions = pd.read_parquet(paths["actions.parquet"])
        labels = pd.read_parquet(paths["labels.parquet"])
        oracle = pd.read_parquet(paths["oracle_ledger.parquet"])
        states = pd.read_parquet(state_path)
        control = control_attempts(states, actions, labels)
        with np.load(cache_path, allow_pickle=False) as stored:
            cache = {name: stored[name] for name in stored.files}
        lookup = contract_lookup(cache)
        day_rows = []
        offered = actions[["entry_i", "contract_i"]].drop_duplicates().sort_values(
            ["entry_i", "contract_i"]
        )
        for ordinal, row in enumerate(offered.itertuples(index=False)):
            day_rows.append(observation(cache, lookup, "OFFERED_ENTRY", "ENTRY", -1 - ordinal,
                                        int(row.entry_i), int(row.contract_i)))
        for row in oracle.itertuples(index=False):
            day_rows.append(observation(cache, lookup, "ORACLE_ENTRY", "ENTRY", row.action_id,
                                        int(row.entry_i), int(row.contract_i)))
            day_rows.append(observation(cache, lookup, "ORACLE_EXIT", "EXIT", row.action_id,
                                        int(row.exit_i), int(row.contract_i)))
        for row in control.itertuples(index=False):
            day_rows.append(observation(cache, lookup, "CONTROL_ENTRY", "ENTRY", row.action_id,
                                        int(row.entry_i), int(row.contract_i)))
            if row.status == "FILLED":
                day_rows.append(observation(cache, lookup, "CONTROL_EXIT", "EXIT", row.action_id,
                                            int(row.exit_i), int(row.contract_i)))
        frame = pd.DataFrame(day_rows)
        frame.insert(0, "date", day.date)
        frame.insert(0, "ticker", day.ticker)
        frame.insert(0, "split", split)
        rows.append(frame)
        daily.append({"split": split, "ticker": day.ticker, "date": day.date,
                      **{name: int((frame.population == name).sum())
                         for name in frame.population.unique()}})
        consumed.append({"split": split, "ticker": day.ticker, "date": day.date,
                         "cache_sha256": day.cache_npz_sha256,
                         "actions_sha256": day.actions_sha256,
                         "labels_sha256": day.labels_sha256,
                         "oracle_ledger_sha256": day.oracle_ledger_sha256,
                         "control_states_sha256": sha256(state_path),
                         "control_checkpoint_sha256": sha256(checkpoint)})
        if number % 50 == 0 or number == len(selected):
            print(json.dumps({"stage": "panel", "days": number, "total": len(selected)}), flush=True)

    observations = pd.concat(rows, ignore_index=True)
    summaries = grouped_summary(observations)
    comparisons = {}
    for split in ("train", "validation"):
        for ticker in ("ALL", "QQQ", "SPXW", "SPY"):
            prefix = f"{split}/{ticker}/"
            comparisons[f"{split}/{ticker}/oracle_vs_offered"] = relative_comparison(
                summaries, prefix + "ORACLE_ENTRY", prefix + "OFFERED_ENTRY")
            comparisons[f"{split}/{ticker}/oracle_vs_control"] = relative_comparison(
                summaries, prefix + "ORACLE_ENTRY", prefix + "CONTROL_ENTRY")

    args.output.mkdir(parents=True)
    observations.to_parquet(args.output / "observations.parquet", index=False)
    pd.DataFrame(daily).fillna(0).to_csv(args.output / "daily_coverage.csv", index=False)
    (args.output / "consumed_days.json").write_text(json.dumps(consumed, indent=2), encoding="utf-8")
    result = {
        "status": "COMPLETE_PREDECLARED_ORACLE_QUOTE_ANOMALY_PANEL",
        "coverage": {"train_days": 96, "validation_days": 741, "total_days": 837,
                     "observation_rows": len(observations)},
        "summaries": summaries, "comparisons": comparisons,
        "binding": {"oracle_audit_sha256": sha256(args.oracle_audit),
                    "engine_index_sha256": sha256(index_path),
                    "control_identity_sha256": identity_sha,
                    "control_summary_sha256": sha256(summary_path),
                    "training_selection_sha256": sha256(selection_path),
                    "observations_sha256": sha256(args.output / "observations.parquet"),
                    "daily_coverage_sha256": sha256(args.output / "daily_coverage.csv"),
                    "consumed_days_sha256": sha256(args.output / "consumed_days.json"),
                    "script_sha256": sha256(Path(__file__).resolve())},
        "metrics_and_thresholds_unchanged_from_fixed_pilot": True,
        "diagnostic_only_no_exclusions": True, "original_trades_and_pnl_unchanged": True,
        "option_quote_age_verified": False, "parity_is_approximate_not_arbitrage_proof": True,
        "new_raw_values_read": False, "technical_ready": False, "promotion_approved": False,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (args.output / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": result["status"], "coverage": result["coverage"]}))


if __name__ == "__main__":
    main()

