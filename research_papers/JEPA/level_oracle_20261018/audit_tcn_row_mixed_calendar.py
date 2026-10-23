"""Independent calendar economic audit given sealed scores, never model inference."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import traceback

import exchange_calendars as xc
import numpy as np
import pandas as pd

import audit_tcn_flags_economics as independent

sha, read, require = independent.digest, independent.load_json, independent.require
HERE = Path(__file__).resolve().parent
SESSION_AUDIT_SHA = "678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9"
FLAGS_AUDIT_SHA = "9911ed97caf16f18802366dd14cb30ddeef68bdbfe05a28f3dc6711dccadb53f"
PRIMITIVES_SHA = "ccb9686b1968fd5328fbcf9ffa18dfd843d302f1fc13a3bd3381a02f35d16e91"
SHORT_DATES = {"20250703", "20251128", "20251224"}
MISSING = {
    (ticker, day)
    for ticker in ("SPY", "QQQ")
    for day in ("20260401", "20260409", "20260415")
}
PERIODS = (
    ("validation", "20250101", "20260101", 750, 750),
    ("test", "20260101", "20260701", 369, 363),
)


def normalized(files):
    result = {}
    for name, digest in files.items():
        path = Path(name)
        require(path.is_absolute(), "Absolute evidence path required")
        key = str(path.resolve())
        require(
            key not in result or result[key] == digest, "Conflicting evidence aliases"
        )
        result[key] = digest
    return result


class Seal:
    def __init__(self):
        self.files = {}
        self.maps = {}

    def normalize(self, files):
        # Retain the original object so Python cannot recycle its identity.
        key = id(files)
        if key not in self.maps:
            self.maps[key] = (files, normalized(files))
        return self.maps[key][1]

    def verify(self, path, digest=None):
        path = Path(path).resolve()
        key = str(path)
        observed = sha(path) if key not in self.files else self.files[key]
        require(digest is None or observed == digest, "Evidence hash: " + key)
        require(
            key not in self.files or self.files[key] == observed, "Evidence changed"
        )
        self.files[key] = observed
        return observed

    def mapping(self, files):
        for path, digest in self.normalize(files).items():
            self.verify(path, digest)

    def member(self, files, path):
        key = str(Path(path).resolve())
        values = self.normalize(files)
        require(key in values, "Unbound consumed member: " + key)
        return self.verify(key, values[key])

    def recheck(self):
        for path, digest in self.files.items():
            require(sha(path) == digest, "Evidence changed during audit: " + path)


def exact(left, right, context):
    left, right = np.asarray(left), np.asarray(right)
    require(
        left.shape == right.shape
        and left.dtype == right.dtype
        and left.tobytes() == right.tobytes(),
        context + " byte identity",
    )


def validate_day(actions, labels, close_i):
    require(close_i in (210, 390), "Unsupported close")
    require(not actions.action_id.duplicated().any(), "Duplicate action")
    require(not labels.action_id.duplicated().any(), "Duplicate label")
    require(set(actions.action_id) == set(labels.action_id), "Action/label universe")
    require(actions.state_i.between(60, close_i - 15).all(), "State outside session")
    require(labels.status.isin(["FILLED", "NO_FILL"]).all(), "Unknown fill status")
    filled = labels.loc[labels.status == "FILLED"]
    require(filled.exit_i.between(62, close_i - 5).all(), "Exit outside session")
    joined = actions[["action_id", "state_i"]].merge(filled, on="action_id")
    require((joined.exit_i >= joined.state_i + 2).all(), "Exit before executable entry")
    for name in ("net_base", "net_adverse"):
        require(
            np.isfinite(filled[name].to_numpy(float)).all(), "Nonfinite filled payoff"
        )
    require(
        (filled.net_adverse <= filled.net_base).all(), "Adverse cost improves payoff"
    )
    require((actions.entry_i == actions.state_i + 1).all(), "Entry delay")
    require(filled.reason.isin(["TARGET", "STOP", "EOD"]).all(), "Exit reason")
    require(
        np.isfinite(filled.entry_ask).all()
        and np.isfinite(filled.exit_bid).all()
        and (filled.entry_ask > 0).all()
        and (filled.exit_bid >= 0).all(),
        "Executable quote",
    )
    require(
        (joined.hold_minutes == joined.exit_i - joined.state_i - 1).all(), "Hold clock"
    )
    for name, slip in (("net_base", 0.01), ("net_adverse", 0.02)):
        rebuilt = (
            np.maximum(filled.exit_bid.to_numpy(float) - slip, 0.0)
            - filled.entry_ask.to_numpy(float)
            - slip
        ) * 100.0 - 2.60
        require(
            np.allclose(rebuilt, filled[name], rtol=0, atol=1e-8),
            "Net cost reconstruction",
        )
    nofill = labels.loc[labels.status == "NO_FILL"]
    require(
        (nofill.net_base == 0).all() and (nofill.net_adverse == 0).all(),
        "NO_FILL is cash",
    )


def validate_calendar(index, record):
    require(not index.duplicated(["ticker", "date"]).any(), "Duplicate calendar row")
    schedule = xc.get_calendar("XNYS").schedule.loc["2025-01-01":"2026-06-30"]
    expected = {
        (ticker, day.strftime("%Y%m%d")): int(
            (row.close - row.open).total_seconds() / 60
        )
        for day, row in schedule.iterrows()
        for ticker in independent.TICKERS
    }
    selected = index.loc[(index.date >= "20250101") & (index.date < "20260701")]
    require(
        set(zip(selected.ticker, selected.date)) == set(expected),
        "NYSE calendar universe",
    )
    observed_missing = set()
    for row in selected.itertuples(index=False):
        require(
            int(row.close_i) == expected[(row.ticker, row.date)], "NYSE close differs"
        )
        require(row.status in ("COMPLETE", "MISSING_SOURCE"), "Unknown source status")
        if row.status != "COMPLETE":
            observed_missing.add((row.ticker, row.date))
    require(observed_missing == MISSING, "Fixed missing sessions changed")
    for period, lower, upper, count, available in PERIODS:
        rows = selected.loc[(selected.date >= lower) & (selected.date < upper)]
        item = record[period]
        require(
            len(rows) == count and int((rows.status == "COMPLETE").sum()) == available,
            "Period coverage",
        )
        require(
            item["expected"] == count and item["available"] == available,
            "Declared coverage",
        )
        declared = {(d["ticker"], d["date"]): d for d in item["days"]}
        require(
            len(declared) == len(item["days"]) == count, "Declared calendar duplicate"
        )
        require(
            set(declared) == set(zip(rows.ticker, rows.date)),
            "Declared calendar membership",
        )
        for row in rows.itertuples(index=False):
            entry = declared[(row.ticker, row.date)]
            clock = dict(
                close_i=int(row.close_i),
                n_slots=int(row.close_i) + 1,
                first_state=60,
                last_state=int(row.close_i) - 15,
                eod_i=int(row.close_i) - 5,
                time_unit_minutes=390,
            )
            require(
                entry["status"] == row.status and entry["clock"] == clock,
                "Declared session clock/status",
            )
    return pd.Series(sorted({day for _, day in expected}), dtype=str)


def require_chronology(root, freeze):
    require(
        freeze["test_evaluated"] is False and freeze["expected_validation_days"] == 750,
        "Pretest freeze contract",
    )
    stamp = datetime.fromisoformat(freeze["frozen_at_utc"])
    require(stamp.tzinfo is not None, "Freeze UTC clock missing")
    paths = [
        p
        for folder in ("test", "control_adapter/test", "control_calendar/test")
        for p in (root / folder).rglob("*")
        if p.is_file()
    ]
    require(bool(paths), "Test artifacts absent")
    for path in paths:
        require(
            path.stat().st_mtime + 0.001 >= (root / "freeze.json").stat().st_mtime,
            "Test artifact predates freeze",
        )
        require(
            path.stat().st_mtime + 0.001 >= stamp.timestamp(),
            "Test artifact predates freeze clock",
        )
    for name in freeze["files"]:
        path = Path(name).resolve()
        if path.is_relative_to(root):
            relative = path.relative_to(root).parts
            require(
                relative[0] != "test"
                and relative[:2]
                not in (("control_adapter", "test"), ("control_calendar", "test")),
                "Test output included in validation freeze",
            )


def require_prediction_features(record, row, seal, external):
    for field, hash_field in (
        ("features_path", "features_sha256"),
        ("features_meta_path", "features_meta_sha256"),
        ("action_features_path", "action_features_sha256"),
        ("action_features_meta_path", "action_features_meta_sha256"),
    ):
        path, digest = getattr(row, field), getattr(row, hash_field)
        seal.member(record["feature_files"], path)
        seal.member(external, path)
        seal.verify(path, digest)


def verify_control_day(root, flags_root, period, row, seal, external):
    stem = f"{row.ticker}_{row.date}"
    name = stem + ".npz"
    calendar_root = root / "control_calendar" / period
    calendar_npz = calendar_root / name
    calendar_hashes = read(calendar_root / "prediction_hashes.json")
    seal.verify(calendar_npz, calendar_hashes[name])
    lineage = read(calendar_root / "lineage.json")[name]
    final = root / period / name
    with (
        np.load(calendar_npz, allow_pickle=False) as saved,
        np.load(final, allow_pickle=False) as evaluated,
    ):
        require(
            set(saved.files) == {"action_ids", "tcn_teacher"}, "Calendar score schema"
        )
        require(
            set(evaluated.files) == {"action_ids", "control", "variant"},
            "Evaluation schema",
        )
        exact(saved["action_ids"], evaluated["action_ids"], "Calendar/evaluation IDs")
        exact(saved["tcn_teacher"], evaluated["control"], "Calendar/evaluation control")
        require(np.isfinite(evaluated["variant"]).all(), "Variant finite")
        if row.close_i == 390:
            original = flags_root / period / name
            adapted = root / "control_adapter" / period / name
            require(
                lineage["kind"] == "AUDITED_FULL_COPY"
                and Path(lineage["source"]).resolve() == adapted.resolve(),
                "Full lineage",
            )
            seal.verify(adapted, lineage["source_sha256"])
            seal.member(external, original)
            manifest_path = flags_root / period / "prediction_manifest.json"
            seal.member(external, manifest_path)
            manifest = read(manifest_path)
            sidecar = original.with_suffix(".json")
            seal.member(external, sidecar)
            seal.verify(sidecar, manifest[sidecar.name])
            source_record = read(sidecar)
            seal.member(source_record["files"], original)
            for group in ("feature_files", "oracle_files"):
                for path, digest in seal.normalize(source_record[group]).items():
                    require(
                        seal.normalize(external).get(path) == digest,
                        "Audited control source omitted from final map",
                    )
            with (
                np.load(original, allow_pickle=False) as base,
                np.load(adapted, allow_pickle=False) as adapter,
            ):
                for key, destination in (
                    ("action_ids", "action_ids"),
                    ("variant", "tcn_teacher"),
                ):
                    exact(base[key], adapter[destination], "FLAGS/adapter")
                    exact(base[key], saved[destination], "FLAGS/calendar")
        else:
            require(
                period == "validation" and row.date in SHORT_DATES,
                "Unexpected short day",
            )
            require(lineage["kind"] == "NEW_SHORT_INFERENCE", "Short lineage kind")
            marker = calendar_npz.with_suffix(".prediction.json")
            require(
                Path(lineage["prediction_seal"]).resolve() == marker.resolve(),
                "Short seal path",
            )
            seal.verify(marker, lineage["prediction_seal_sha256"])
            record = read(marker)
            require(
                record["labels_read"] is False and record["clock"]["close_i"] == 210,
                "Short prediction before labels",
            )
            for path in (
                calendar_npz,
                root / "tcn_control.pt",
                root / "normalizers.json",
                Path(row.day_root) / "actions.parquet",
            ):
                seal.member(record["files"], path)
            seal.mapping(record["feature_files"])
            require_prediction_features(record, row, seal, external)
            require(
                marker.stat().st_mtime
                <= (root / period / (stem + ".json")).stat().st_mtime,
                "Short score seal after economics",
            )
    prediction_marker = root / period / (stem + ".prediction.json")
    record = read(prediction_marker)
    for path in (final, calendar_npz, root / "tcn_variant.pt"):
        seal.member(record["files"], path)
    seal.mapping(record["feature_files"])
    require_prediction_features(record, row, seal, external)
    done = read(root / period / (stem + ".json"))
    seal.member(done["files"], prediction_marker)
    for group in ("feature_files", "oracle_files"):
        for path, digest in seal.normalize(done[group]).items():
            require(
                seal.normalize(external).get(path) == digest,
                "Daily source omitted from final map",
            )
    for ident in independent.policies():
        path = root / period / (stem + "_" + ident + ".parquet")
        seal.member(done["files"], path)
        require(
            prediction_marker.stat().st_mtime <= path.stat().st_mtime,
            "Prediction seal after economic shard",
        )


def verify_period_inputs(root, flags_root, index, period, lower, upper, seal, external):
    rows = index.loc[
        (index.date >= lower) & (index.date < upper) & (index.status == "COMPLETE")
    ]
    expected = {f"{row.ticker}_{row.date}.npz" for row in rows.itertuples(index=False)}
    for filename in ("prediction_hashes.json", "lineage.json"):
        require(
            set(read(root / "control_calendar" / period / filename)) == expected,
            "Calendar control membership",
        )
    full = {
        f"{row.ticker}_{row.date}.npz"
        for row in rows.itertuples(index=False)
        if row.close_i == 390
    }
    adapter = read(root / "control_adapter" / period / "adapter_lineage.json")
    require(set(adapter["days"]) == full, "Adapter full membership")
    for path, digest in adapter["source_files"].items():
        require(
            seal.normalize(external).get(str(Path(path).resolve())) == digest,
            "Adapter source missing from final source map",
        )
    for row in rows.itertuples(index=False):
        day_root = Path(row.day_root)
        for filename, field in (
            ("actions.parquet", "actions_sha256"),
            ("labels.parquet", "labels_sha256"),
        ):
            path = day_root / filename
            seal.member(external, path)
            seal.verify(path, getattr(row, field))
        for field, hash_field in (
            ("features_path", "features_sha256"),
            ("features_meta_path", "features_meta_sha256"),
            ("action_features_path", "action_features_sha256"),
            ("action_features_meta_path", "action_features_meta_sha256"),
        ):
            seal.member(external, getattr(row, field))
            seal.verify(getattr(row, field), getattr(row, hash_field))
        actions, labels = (
            pd.read_parquet(day_root / name)
            for name in ("actions.parquet", "labels.parquet")
        )
        validate_day(actions, labels, int(row.close_i))
        verify_control_day(root, flags_root, period, row, seal, external)
    return {
        "full_control_days": int((rows.close_i == 390).sum()),
        "new_short_control_days": int((rows.close_i == 210).sum()),
    }


def final_summary(root, selection, test):
    summary = read(root / "summary.json")
    require(
        summary["status"] == "COMPLETE"
        and summary["development_seen"] is True
        and summary["promotion_approved"] is False,
        "Nonpromotional completion",
    )
    require(
        summary["control"] == "FLAGS64" and summary["variant"] == "row_mixed",
        "Comparison identity",
    )
    require(summary["freeze_sha256"] == sha(root / "freeze.json"), "Final freeze hash")
    independent.compare_values(selection, summary["selection"], "Final selection")
    selected = selection["selected_policy"]
    independent.compare_values(
        test[selected] if selected else None, summary["selected_test"], "Selected test"
    )
    gate = {"passes": False, "reason": "NO_VALIDATION_DAILY_COMPLIANT_POLICY"}
    if selected:
        gate = independent.economic_gate(selected, test)
        gate["daily_gate"] = test[selected]["daily_gate"]
        gate["passes"] = gate["passes"] and gate["daily_gate"]["passes"]
    independent.compare_values(gate, summary["gate"], "Final gate")
    independent.compare_values(test, summary["test"], "All test policies")
    paired = {
        str(int(t)): {
            cost + "_delta_usd": test[independent.policy_id("variant", t)]["pooled"][
                cost + "_net_usd"
            ]
            - test[independent.policy_id("control", t)]["pooled"][cost + "_net_usd"]
            for cost in ("base", "adverse")
        }
        for t in independent.THRESHOLDS
    }
    independent.compare_values(
        paired, summary["paired_same_threshold_test"], "Paired test"
    )
    return gate, paired


def audit(args):
    root, flags_root, session = (
        args.root.resolve(),
        args.flags_root.resolve(),
        args.session_root.resolve(),
    )
    seal = Seal()
    seal.verify(independent.__file__, PRIMITIVES_SHA)
    for path in (
        root / "identity.json",
        root / "completion.json",
        root / "freeze.json",
        root / "source_inputs.json",
        args.review,
        Path(__file__),
        HERE / "TCN_ROW_MIXED_CALENDAR_AUDIT_SPEC.md",
    ):
        seal.verify(path)
    seal.verify(args.control_audit, FLAGS_AUDIT_SHA)
    seal.verify(args.session_audit, SESSION_AUDIT_SHA)
    control_audit, session_audit = read(args.control_audit), read(args.session_audit)
    require(
        control_audit["status"] == "PASS_INDEPENDENT_TCN_FLAGS_ECONOMIC_AUDIT",
        "FLAGS audit",
    )
    require(
        session_audit["status"] == "PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT",
        "Dataset audit",
    )
    require(
        Path(control_audit["binding"]["root"]).resolve() == flags_root, "FLAGS root"
    )
    require(
        Path(session_audit["binding"]["engine_root"]).resolve() == session,
        "Dataset root",
    )
    for name, key in (
        ("index.parquet", "index_sha256"),
        ("dataset_contract.json", "dataset_contract_sha256"),
        ("completion.json", "completion_sha256"),
        ("feature_contract.json", "feature_contract_sha256"),
    ):
        seal.verify(session / name, session_audit["binding"][key])
    for name, key in (
        ("summary.json", "summary_sha256"),
        ("completion.json", "completion_sha256"),
        ("freeze.json", "freeze_sha256"),
        ("validation/prediction_manifest.json", "validation_manifest_sha256"),
        ("test/prediction_manifest.json", "test_manifest_sha256"),
    ):
        seal.verify(flags_root / name, control_audit["binding"][key])
    seal.mapping(read(flags_root / "completion.json")["files"])
    identity, completion = read(root / "identity.json"), read(root / "completion.json")
    require(completion["status"] == "COMPLETE", "Incomplete producer")
    seal.mapping(identity["files"])
    seal.mapping(completion["files"])
    for path in root.rglob("*"):
        if (
            path.is_file()
            and path.name not in ("completion.json", ".output.lock")
            and "recovery" not in path.relative_to(root).parts
        ):
            seal.member(completion["files"], path)
    require(
        identity["variant"] == "row_mixed_epoch4_calendar750"
        and identity["control"] == "FLAGS64_full_copy_plus9short"
        and identity["training_changed"] is False,
        "Scientific identity",
    )
    require(
        Path(identity["session_root"]).resolve() == session
        and Path(identity["control_root"]).resolve() == flags_root,
        "Input roots",
    )
    seal.member(identity["files"], args.review)
    review = read(args.review)
    require(
        review["status"] == "PASS_TCN_ROW_MIXED_CALENDAR_IMPLEMENTATION_REVIEW"
        and review["dependencies"] == identity["dependencies"],
        "Implementation review",
    )
    for name, digest in identity["dependencies"].items():
        seal.verify(HERE / name, digest)
        seal.verify(root / "executed_code" / name, digest)
    training = read(root / "training_complete.json")
    training_root = Path(identity["training_root"])
    for name in ("training_complete.json", "tcn_variant.pt"):
        seal.member(identity["files"], training_root / name)
        seal.verify(root / name, sha(training_root / name))
    require(
        training["binding"]["epochs"] == 4
        and training["binding"]["variant"] == "row_mixed_original_batch_sizes"
        and [r["epoch"] for r in training["history"]] == [1, 2, 3, 4]
        and all(r["updates"] == 1491 for r in training["history"]),
        "Fourth epoch completion",
    )
    seal.mapping(training["binding"]["files"])
    seal.verify(root / "tcn_variant.pt", training["model_sha256"])
    control_training = read(flags_root / "training_complete.json")
    seal.member(identity["files"], flags_root / "training_complete.json")
    seal.verify(root / "tcn_control.pt", control_training["model_sha256"])
    seal.verify(root / "normalizers.json", sha(flags_root / "normalizers.json"))
    external = read(root / "source_inputs.json")["files"]
    seal.mapping(external)
    for path, digest in seal.normalize(identity["files"]).items():
        require(
            seal.normalize(external).get(path) == digest,
            "Identity absent from source map",
        )
    index = pd.read_parquet(session / "index.parquet")
    index["date"] = index.date.astype(str)
    calendar_record = read(root / "session_calendar.json")
    require(
        identity["evaluation_calendar"] == calendar_record, "Identity calendar mismatch"
    )
    calendar = validate_calendar(index, calendar_record)
    require(
        calendar.tolist()
        == pd.read_csv(root / "expected_full_calendar.csv", dtype=str).date.tolist(),
        "CSV calendar",
    )
    freeze = read(root / "freeze.json")
    seal.mapping(freeze["files"])
    require_chronology(root, freeze)
    for path in (root / "validation").rglob("*"):
        if path.is_file():
            seal.member(freeze["files"], path)
    for path in (root / "control_calendar" / "validation").rglob("*"):
        if path.is_file():
            seal.member(freeze["files"], path)
    counts, summaries = {}, {}
    for period, lower, upper, _, _ in PERIODS:
        controls = verify_period_inputs(
            root, flags_root, index, period, lower, upper, seal, external
        )
        summaries[period], counts[period] = independent.audit_period(
            root, root / "control_calendar", index, calendar, period, lower, upper
        )
        counts[period].update(controls)
        if period == "validation":
            scales = read(root / "normalizers.json")["risk_scales_usd"]
            require(
                all(
                    np.isfinite(scales[t]) and scales[t] > 0
                    for t in independent.TICKERS
                ),
                "Risk scales",
            )
            selection = independent.select_validation(summaries[period], scales)
            independent.compare_values(
                selection, freeze["selection"], "Frozen validation selection"
            )
    gate, paired = final_summary(root, selection, summaries["test"])
    for path in (
        root / "completion.json",
        args.review,
        Path(__file__),
        HERE / "audit_tcn_flags_economics.py",
        HERE / "TCN_ROW_MIXED_CALENDAR_AUDIT_SPEC.md",
    ):
        seal.verify(path)
    seal.recheck()
    return dict(
        status="PASS_INDEPENDENT_TCN_ROW_MIXED_CALENDAR_ECONOMIC_AUDIT",
        scope="ECONOMIC_EXECUTION_GIVEN_SEALED_SCORES_AND_AUDITED_LABELS",
        binding=dict(
            root=str(root),
            summary_sha256=sha(root / "summary.json"),
            completion_sha256=sha(root / "completion.json"),
            source_inputs_sha256=sha(root / "source_inputs.json"),
            freeze_sha256=sha(root / "freeze.json"),
            implementation_review_sha256=sha(args.review),
            audit_script_sha256=sha(__file__),
            independent_primitives_sha256=sha(independent.__file__),
        ),
        counts=counts,
        selection=selection,
        gate=gate,
        paired_same_threshold_test=paired,
        verified_files=seal.files,
        training_reproduced=False,
        gpu_inference_reproduced=False,
        raw_quote_replay=False,
        test_is_seen_development=True,
        technical_ready=False,
        promotion_approved=False,
        finished_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def publish(path, value):
    temporary = path.with_suffix(path.suffix + ".partial")
    require(
        not path.exists() and not temporary.exists(), "Preserve existing audit artifact"
    )
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "root",
        "flags-root",
        "control-audit",
        "session-root",
        "session-audit",
        "review",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    for protected in (
        args.root.resolve(),
        args.flags_root.resolve(),
        args.session_root.resolve(),
        HERE,
    ):
        require(
            not (
                out == protected
                or out.is_relative_to(protected)
                or protected.is_relative_to(out)
            ),
            "Separate audit root required",
        )
    out.mkdir(parents=True, exist_ok=False)
    try:
        result = audit(args)
        publish(out / "audit.json", result)
        print(
            json.dumps({k: v for k, v in result.items() if k != "verified_files"}),
            flush=True,
        )
    except BaseException:
        publish(
            out / "audit_failure.json",
            dict(status="AUDIT_FAILED", traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    main()
