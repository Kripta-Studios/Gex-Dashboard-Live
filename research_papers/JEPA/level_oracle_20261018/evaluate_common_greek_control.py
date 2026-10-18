"""Fixed152 versus424 comparison; no fit, calibration or policy selection.

The completed, independently audited compact comparison is the control-score
authority on every available full AND short session. New raw-Greek inputs are
bound to the same audited SessionClock index before any outcome access.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
import uuid

import numpy as np
import pandas as pd

import build_common_greek_train as builder
import common_greek_dynamics as dynamic
import evaluate_market_cue_control as previous
import market_cue_comparison as metrics
import market_cue_vectors as vectors
import market_cue_vectors_fast as fast
import rolling_monthly_schedule as calendar
import train_market_cue_control as training

require, sha, read_json, atomic_json = (
    training.require,
    training.sha,
    training.read_json,
    training.atomic_json,
)
POLICIES = ("cue_net__0", "common_greek_net__0")
# A separate namespace: never mutate globals of the active compact evaluator.
comparison = SimpleNamespace(
    POLICIES=POLICIES,
    schedule=metrics.schedule,
    trade_metrics=metrics.trade_metrics,
    coverage_report=metrics.coverage_report,
    calibration_sums=metrics.calibration_sums,
    calibration_report=metrics.calibration_report,
    CALIBRATION_EDGES=metrics.CALIBRATION_EDGES,
)
Evidence, save_npz = previous.Evidence, previous.save_npz
DEPENDENCIES = tuple(
    dict.fromkeys(
        (
            "evaluate_common_greek_control.py",
            "COMMON_GREEK_COMPARISON_SPEC.md",
            "common_greek_dynamics.py",
            "build_common_greek_train.py",
            "COMMON_GREEK_DYNAMICS_V1_DESIGN.md",
            "COMMON_GREEK_DYNAMICS_V1_LEARNER_PLAN.md",
            "train_common_greek_control.py",
            "COMMON_GREEK_TRAINER_IMPLEMENTATION.md",
            *previous.DEPENDENCIES,
        )
    )
)


def dependencies():
    return {name: sha(Path(__file__).with_name(name)) for name in DEPENDENCIES}


class TrainingProvenance:
    """Rehash bulk TRAIN inputs at admission/resume and final completion, not per day."""

    verify = training.OriginalInputs.verify
    recheck = training.OriginalInputs.recheck

    def __init__(self):
        self.hashes = {}


def seal_training_provenance(provenance, path):
    record = dict(
        status="PINNED_TRAIN_INPUTS_REHASHED_AT_ADMISSION",
        files=dict(provenance.hashes),
        recheck="ADMISSION_EVERY_RESUME_AND_FINAL_BEFORE_COMPLETION",
    )
    if Path(path).exists():
        require(read_json(path) == record, "TRAIN provenance manifest changed")
    else:
        atomic_json(path, record)
    return sha(path)


class CueScores:
    """Audited completed comparison, not a self-baselined forecast directory."""

    verify = training.OriginalInputs.verify
    recheck = training.OriginalInputs.recheck

    def __init__(self, root, audit_path, expected_audit_sha):
        self.root, self.hashes = Path(root).resolve(), {}
        self.verify(audit_path, expected_audit_sha)
        audit = read_json(audit_path)
        require(
            audit.get("status")
            == "PASS_INDEPENDENT_MARKET_CUE_COMPARISON_ECONOMIC_AUDIT",
            "Completed independent cue comparison audit required",
        )
        binding = audit["binding"]
        require(
            Path(binding["comparison_root"]).resolve() == self.root,
            "Wrong cue comparison root",
        )
        for name, field in (
            ("freeze.json", "freeze_sha256"),
            ("completion.json", "completion_sha256"),
            ("comparison.complete.json", "comparison_complete_sha256"),
        ):
            self.verify(self.root / name, binding[field])
        completion = read_json(self.root / "completion.json")
        require(
            completion["status"] == "COMPLETE_FIXED_CUE_COMPARISON",
            "Cue comparison incomplete",
        )
        self.binding = binding
        self.manifest = read_json(self.root / "comparison.complete.json")
        require(
            self.manifest["status"] == "COMPLETE"
            and self.manifest["binding"] == binding["freeze_sha256"],
            "Cue completion binding differs",
        )
        self.source_hashes = self.manifest["extra"]["sources"]

    def compare(self, key, close_i, actions, score):
        require(close_i in (210, 390), "Unknown reference clock")
        relative = "predictions/" + key
        paths = [
            self.root / (relative + suffix) for suffix in (".npz", ".complete.json")
        ]
        for path in paths:
            name = str(path.relative_to(self.root))
            require(
                name in self.manifest["files"],
                "Prediction absent from audited completion",
            )
            self.verify(path, self.manifest["files"][name])
        marker = read_json(paths[1])
        require(
            marker["status"] == "COMPLETE"
            and marker["binding"] == self.binding["freeze_sha256"],
            "Baseline prediction seal differs",
        )
        require(
            marker["extra"]["outcomes_read"] is False, "Baseline prediction not causal"
        )
        for path, digest in marker["extra"]["sources"].items():
            require(
                self.source_hashes.get(path) == digest,
                "Baseline source authority differs",
            )
            self.verify(path, digest)
        with np.load(paths[0], allow_pickle=False) as data:
            require(
                np.array_equal(data["action_id"], actions.action_id)
                and np.array_equal(data["state_i"], actions.state_i),
                "Baseline action/state order differs",
            )
            reference = data["cue_net__0"]
        score = np.asarray(score)
        require(
            score.dtype == reference.dtype
            and score.shape == reference.shape
            and score.tobytes() == reference.tobytes(),
            "Cue control scores are not bitexact",
        )
        sources = {
            str(path.resolve()): self.manifest["files"][
                str(path.relative_to(self.root))
            ]
            for path in paths
        }
        sources.update(marker["extra"]["sources"])
        for path, digest in sources.items():
            self.verify(path, digest)
        return dict(
            status="EXACT_AUDITED_CUE_ALL_SESSIONS",
            bitexact_checked=True,
            close_i=close_i,
            actions=len(actions),
        ), sources


class SessionInputs(previous.SessionInputs):
    def __init__(self, root, audit_path, cue_scores):
        super().__init__(root, audit_path, cue_scores)
        paths = pd.read_parquet(
            self.root / "index.parquet",
            columns=["ticker", "date", "cache_path", "cache_meta_path"],
        )
        paths["date"] = paths.date.astype(str)
        self.cache_paths = paths.set_index(["ticker", "date"], verify_integrity=True)
        require(
            self.cache_paths.index.equals(self.index.index),
            "Raw cache index identity differs",
        )
        self.verify(
            self.root / "index.parquet",
            self.hashes[str((self.root / "index.parquet").resolve())],
        )

    def feature_day(self, key):
        pack, ids, actions, hashes = super().feature_day(key)
        row, paths = self.row(key), self.cache_paths.loc[tuple(key.split("/"))]
        source, metadata = (
            Path(paths.cache_path).resolve(),
            Path(paths.cache_meta_path).resolve(),
        )
        raw_hashes = {
            str(source): row.cache_npz_sha256,
            str(metadata): row.cache_meta_sha256,
        }
        for path, digest in raw_hashes.items():
            self.verify(path, digest)
        meta = read_json(metadata)
        ticker, stamp = key.split("/")
        require(
            meta["ticker"] == ticker
            and str(meta["date"]) == stamp
            and meta["sha256"] == row.cache_npz_sha256,
            "Raw Greek cache identity differs",
        )
        with np.load(source, allow_pickle=False) as data:
            raw = {name: data[name] for name in builder.RAW_KEYS}
        close_i = int(row.close_i)
        require(
            len(raw["time_ns"]) in (close_i + 1, 391),
            "Unsupported audited raw time shape",
        )
        state = dynamic.prepare_day(raw_for_dynamics(raw, close_i), close_i=close_i)
        pack["dynamics272"] = dynamic.encode_states(state, pack["state_i"])
        for path, digest in raw_hashes.items():
            self.verify(path, digest)
        hashes.update(raw_hashes)
        return pack, ids, actions, hashes


def raw_for_dynamics(raw, close_i):
    """Adapt a211-slot cache to the frozen391-slot OI helper, with masked tail.

    No preclose sample is filled or changed. Padding is an in-memory shape
    adapter, not a new market observation or source artifact.
    """
    require(close_i in (210, 390), "Unknown physical close")
    size = len(raw["time_ns"])
    require(size in (close_i + 1, 391), "Unsupported raw clock length")
    if size == 391:
        return raw
    require(close_i == 210 and size == 211, "Only short211 cache may be padded")
    adapted = dict(raw)
    timestamps = np.asarray(raw["time_ns"])
    require(
        np.issubdtype(timestamps.dtype, np.integer)
        and np.all(np.diff(timestamps) == 60_000_000_000),
        "Cache minute clock differs",
    )
    adapted["time_ns"] = np.r_[
        timestamps, timestamps[-1] + np.arange(1, 181, dtype=np.int64) * 60_000_000_000
    ]
    for name, fill in (
        ("spot", np.nan),
        ("spot_valid", False),
        ("row_flags", 0),
        ("iv", np.nan),
        ("delta", np.nan),
        ("vega", np.nan),
        ("theta", np.nan),
    ):
        array = np.asarray(raw[name])
        require(array.shape[0] == size, "Raw time axis differs")
        padding = np.full((180, *array.shape[1:]), fill, dtype=array.dtype)
        adapted[name] = np.concatenate((array, padding), axis=0)
    return adapted


def predict_both(pack, ids, actions, models, scale, block=1024):
    require(set(models) == set(POLICIES), "Exactly two fixed models required")
    require(
        models[POLICIES[0]].num_feature() == 152
        and models[POLICIES[1]].num_feature() == 424,
        "Model width changed",
    )
    ai, si = vectors.join_action_rows(
        reference_action_ids=actions.action_id.to_numpy(),
        reference_state_i=actions.state_i.to_numpy(),
        pack_action_ids=ids,
        offered_action_ids=actions.action_id.to_numpy(),
        offered_state_i=actions.state_i.to_numpy(),
        pack_state_i=pack["state_i"],
    )
    dynamics = pack["dynamics272"]
    require(
        dynamics.shape == (len(pack["state_i"]), 272)
        and dynamics.dtype == np.float32
        and np.isfinite(dynamics).all(),
        "Dynamic state schema differs",
    )
    cue_pack = {
        name: value
        for name, value in pack.items()
        if name not in ("maps", "map_mask", "dynamics272")
    }
    result = {
        POLICIES[0]: training.predict_offered_day(
            models[POLICIES[0]], cue_pack, ids, actions, scale, block
        )["scores"],
        POLICIES[1]: np.empty(len(actions), np.float64),
    }
    for start in range(0, len(actions), block):
        end = min(start + block, len(actions))
        compact = fast.vectorize_rows(
            **cue_pack, action_positions=ai[start:end], state_positions=si[start:end]
        )
        values = dynamic.append_to_compact(compact, dynamics[si[start:end]])
        result[POLICIES[1]][start:end] = (
            np.asarray(models[POLICIES[1]].predict(values, num_threads=4), np.float64)
            * scale
        )
    require(
        all(np.isfinite(value).all() for value in result.values()),
        "Nonfinite predictions",
    )
    return result


def evaluate_day(key, source, models, scales, evidence, frozen_sources):
    ticker, day = key.split("/")
    row = source.row(key)
    name = "days/" + key
    summary_path = evidence.root / (name + ".json")
    attempts_paths = {
        policy: evidence.root / (name + "." + policy + ".parquet")
        for policy in comparison.POLICIES
    }
    if evidence.complete(
        name,
        [
            str(path.relative_to(evidence.root))
            for path in [summary_path, *attempts_paths.values()]
        ],
    ):
        return read_json(summary_path)
    for path in (summary_path, *attempts_paths.values()):
        evidence.preserve(path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    if row.status == "MISSING_SOURCE":
        empty = pd.DataFrame(
            columns=[
                "action_id",
                "state_i",
                "score_usd",
                "has_filled_before",
                "status",
                "exit_i",
                "net_base",
                "net_adverse",
            ]
        )
        result = {
            policy: dict(
                ticker=ticker,
                date=day,
                source_status="MISSING_SOURCE",
                **comparison.trade_metrics(empty),
                attempts=0,
                calibration={},
            )
            for policy in comparison.POLICIES
        }
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        for path in attempts_paths.values():
            empty.to_parquet(path, index=False)
        atomic_json(summary_path, result)
        evidence.finish(
            name, [summary_path, *attempts_paths.values()], {"sources": frozen_sources}
        )
        return result
    pred_name = "predictions/" + key
    prediction_path = evidence.root / (pred_name + ".npz")
    if not evidence.complete(
        pred_name, [str(prediction_path.relative_to(evidence.root))]
    ):
        evidence.preserve(prediction_path)
        pack, ids, actions, feature_sources = source.feature_day(key)
        scores = predict_both(pack, ids, actions, models, scales[ticker])
        reference, reference_sources = source.reference_control(
            key, actions, scores[comparison.POLICIES[0]]
        )
        feature_sources = {**feature_sources, **reference_sources}
        save_npz(
            prediction_path,
            action_id=actions.action_id.to_numpy(),
            state_i=actions.state_i.to_numpy(),
            **scores,
        )
        for path, digest in {**frozen_sources, **feature_sources}.items():
            require(sha(path) == digest, "Source changed during prediction")
        evidence.finish(
            pred_name,
            [prediction_path],
            {
                "sources": {**frozen_sources, **feature_sources},
                "outcomes_read": False,
                "original_control_reference": reference,
            },
        )
    # Both predictions and their input hashes are published before any label read.
    require(evidence.complete(pred_name), "Prediction seal absent")
    expected_reference = "EXACT_AUDITED_CUE_ALL_SESSIONS"
    require(
        read_json(evidence.marker(pred_name))["extra"]["original_control_reference"][
            "status"
        ]
        == expected_reference,
        "Missing original control reference verification",
    )
    with np.load(prediction_path, allow_pickle=False) as saved:
        actions = pd.DataFrame({name: saved[name] for name in ("action_id", "state_i")})
        scores = {policy: saved[policy] for policy in comparison.POLICIES}
    labels, label_sources = source.labels(key)
    result = {}
    for policy in comparison.POLICIES:
        aligned, attempts, ledger = comparison.schedule(
            actions, labels, scores[policy], int(row.close_i)
        )
        groups = actions.groupby("state_i").state_i.transform("size").to_numpy()
        state_count = actions.state_i.nunique()
        equal_state = 1.0 / (groups * state_count) if state_count else np.empty(0)
        calibration = {
            "all_offers_action_weighted": comparison.calibration_sums(
                scores[policy], aligned.net_base, scales[ticker]
            ),
            "all_offers_equal_day_state": comparison.calibration_sums(
                scores[policy], aligned.net_base, scales[ticker], equal_state
            ),
            "selected_attempts": comparison.calibration_sums(
                attempts.score_usd, attempts.net_base, scales[ticker]
            ),
            "selected_fills": comparison.calibration_sums(
                ledger.score_usd, ledger.net_base, scales[ticker]
            ),
        }
        result[policy] = dict(
            ticker=ticker,
            date=day,
            source_status="COMPLETE",
            **comparison.trade_metrics(ledger),
            attempts=len(attempts),
            calibration=calibration,
        )
        attempts.to_parquet(attempts_paths[policy], index=False)
    prediction_marker = read_json(evidence.marker(pred_name))
    sources = {**prediction_marker["extra"]["sources"], **label_sources}
    for path, digest in sources.items():
        require(sha(path) == digest, "Source changed during daily replay")
    atomic_json(summary_path, result)
    evidence.finish(
        name,
        [
            summary_path,
            *attempts_paths.values(),
            prediction_path,
            evidence.marker(pred_name),
        ],
        {"sources": sources},
    )
    return result


def period_report(keys, daily, evidence):
    reports = {}
    for policy in comparison.POLICIES:
        reports[policy] = {}
        for ticker in ("ALL", *calendar.TICKERS):
            chosen = [
                key for key in keys if ticker == "ALL" or key.split("/")[0] == ticker
            ]
            rows = [daily[key][policy] for key in chosen]
            frames = [
                pd.read_parquet(
                    evidence.root / ("days/" + key + "." + policy + ".parquet")
                )
                for key in chosen
            ]
            nonempty = [frame for frame in frames if len(frame)]
            attempts = (
                pd.concat(nonempty, ignore_index=True)
                if nonempty
                else frames[0].iloc[:0].copy()
            )
            ledger = attempts.loc[attempts.status == "FILLED"]
            reports[policy][ticker] = {
                "coverage": comparison.coverage_report(rows),
                "available_economics": comparison.trade_metrics(ledger),
                "calibration": {
                    kind: comparison.calibration_report(
                        [
                            row["calibration"][kind]
                            for row in rows
                            if kind in row["calibration"]
                        ]
                    )
                    for kind in (
                        "all_offers_action_weighted",
                        "all_offers_equal_day_state",
                        "selected_attempts",
                        "selected_fills",
                    )
                },
            }
    return dict(
        policies=reports,
        winner_selected=None,
        threshold=0,
        development_seen=True,
        promotion_approved=False,
    )


def evaluate_period(year, source, models, scales, evidence, frozen_sources):
    require(year in (2025, 2026), "Undeclared evaluation year")
    if year == 2026:
        require(
            evidence.complete("period2025", ["period2025.json"]),
            "Complete fixed comparison2025 first",
        )
        test_path = evidence.root / "test_freeze.json"
        test_freeze = dict(
            status="FIXED_POLICIES_AFTER_VALIDATION_BEFORE_TEST",
            initial_freeze_sha256=evidence.binding,
            validation_sha256=sha(evidence.root / "period2025.json"),
            validation_completion_sha256=sha(evidence.marker("period2025")),
            policies=list(POLICIES),
            threshold=0,
            winner_selected=None,
        )
        if test_path.exists():
            require(read_json(test_path) == test_freeze, "Test freeze changed")
        else:
            require(
                not any((evidence.root / "predictions").glob("*/2026*")),
                "Test predictions exist without test freeze",
            )
            atomic_json(test_path, test_freeze)
        frozen_sources = {**frozen_sources, str(test_path.resolve()): sha(test_path)}
    name, output = (
        "period" + str(year),
        evidence.root / ("period" + str(year) + ".json"),
    )
    if evidence.complete(name, [output.name]):
        return read_json(output)
    evidence.preserve(output)
    keys, daily = source.keys(year), {}
    for index, key in enumerate(keys):
        daily[key] = evaluate_day(key, source, models, scales, evidence, frozen_sources)
        if (index + 1) % 25 == 0:
            print({"year": year, "days": index + 1, "total": len(keys)}, flush=True)
    report = period_report(keys, daily, evidence)
    source.recheck()
    sources, files = dict(frozen_sources), [output]
    for key in keys:
        marker = evidence.marker("days/" + key)
        record = read_json(marker)
        require(evidence.complete("days/" + key), "Changed daily evidence")
        sources.update(record["extra"]["sources"])
        files.extend([marker, *(evidence.root / path for path in record["files"])])
    atomic_json(output, report)
    evidence.finish(name, files, {"sources": sources})
    return report


def complete_comparison(evidence):
    if not all(
        evidence.complete("period" + str(year), ["period" + str(year) + ".json"])
        for year in (2025, 2026)
    ):
        return False
    path = evidence.root / "completion.json"
    if evidence.complete(
        "comparison",
        [
            "completion.json",
            "freeze.json",
            "period2025.json",
            "period2026.json",
            "period2025.complete.json",
            "period2026.complete.json",
            "test_freeze.json",
        ],
    ):
        return True
    evidence.preserve(path)
    files, sources = (
        [path, evidence.root / "freeze.json", evidence.root / "test_freeze.json"],
        {},
    )
    for year in (2025, 2026):
        marker = evidence.marker("period" + str(year))
        record = read_json(marker)
        files.extend([marker, *(evidence.root / member for member in record["files"])])
        sources.update(record["extra"]["sources"])
    atomic_json(
        path,
        dict(
            status="COMPLETE_FIXED_COMMON_GREEK_COMPARISON",
            freeze_sha256=evidence.binding,
            periods=[2025, 2026],
            policies=list(comparison.POLICIES),
            winner_selected=None,
            development_seen=True,
            promotion_approved=False,
        ),
    )
    evidence.finish("comparison", files, {"sources": sources})
    return True


def validate_trained_contract(contract, control, *, expected_rows=270377):
    require(
        contract["config"] == control["config"] == training.CONFIG,
        "Training configuration differs",
    )
    require(contract["scales"] == control["scales"], "TRAIN scales differ")
    require(
        set(contract["scales"]) == set(calendar.TICKERS)
        and all(np.isfinite(v) and v > 0 for v in contract["scales"].values()),
        "Invalid scales",
    )
    require(
        contract["rows"] == control["training_rows"] == expected_rows
        and contract["train_only"] is True
        and contract["control_model_refitted"] is False,
        "Training scope differs",
    )
    require(
        contract["schema"]["column_names"]
        == [*vectors.COLUMN_NAMES, *dynamic.FEATURE_NAMES],
        "424 column schema differs",
    )
    require(
        control["schema"]["column_names"] == list(vectors.COLUMN_NAMES),
        "Control152 schema differs",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "greek-root",
        "cue-root",
        "cue-comparison-root",
        "cue-comparison-audit",
        "session-root",
        "session-audit",
        "review",
        "out",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--stage", choices=("2025", "2026", "all"), default="2025")
    args = parser.parse_args()
    review_sha = sha(args.review)
    code, review = dependencies(), read_json(args.review)
    require(sha(args.review) == review_sha, "Review changed while loading")
    require(
        review.get("status") == "PASS_COMMON_GREEK_COMPARISON_IMPLEMENTATION_REVIEW"
        and review.get("dependencies") == code,
        "Exact implementation review required",
    )
    authorities = {
        "cue_comparison_audit_sha256": args.cue_comparison_audit,
        "session_audit_sha256": args.session_audit,
        "cue_contract_sha256": args.cue_root / "run_contract.json",
        "cue_model_completion_sha256": args.cue_root / "model.complete.json",
        "greek_contract_sha256": args.greek_root / "run_contract.json",
        "greek_model_completion_sha256": args.greek_root / "model.complete.json",
    }
    require(
        review.get("authorities")
        == {field: sha(path) for field, path in authorities.items()},
        "Authority differs from review",
    )
    builder.separate_output(
        args.out,
        [args.greek_root, args.cue_root, args.cue_comparison_root, args.session_root],
    )
    with training.output_lock(args.out):
        baseline = CueScores(
            args.cue_comparison_root,
            args.cue_comparison_audit,
            review["authorities"]["cue_comparison_audit_sha256"],
        )
        for field in (
            "session_audit_sha256",
            "cue_contract_sha256",
            "cue_model_completion_sha256",
        ):
            require(
                baseline.binding[field] == review["authorities"][field],
                "Baseline comparison used different source/model",
            )
        source = SessionInputs(args.session_root, args.session_audit, baseline)
        source.verify(args.review, review_sha)
        for field, path in authorities.items():
            source.verify(path, review["authorities"][field])
        control, trained = (
            read_json(args.cue_root / "run_contract.json"),
            read_json(args.greek_root / "run_contract.json"),
        )
        validate_trained_contract(trained, control)
        provenance = TrainingProvenance()
        for contract in (control, trained):
            for path, digest in contract["sources"].items():
                provenance.verify(path, digest)
        for root, name, members in (
            (
                args.cue_root,
                "model",
                ["cue_net.txt", "fit_started.json", "matrix.complete.json"],
            ),
            (
                args.greek_root,
                "model",
                [
                    "common_greek_net.txt",
                    "train_readback_predictions.npy",
                    "fit_started.json",
                    "run_contract.json",
                    "export.complete.json",
                ],
            ),
        ):
            checkpoint = training.Checkpoints(root, sha(root / "run_contract.json"))
            require(checkpoint.complete(name, members), "Trained model incomplete")
            marker = read_json(checkpoint.marker(name))
            for member, digest in marker["files"].items():
                source.verify(root / member, digest)
            for path, digest in marker.get("extra", {}).get("sources", {}).items():
                provenance.verify(path, digest)
        training.bind_code_snapshots(source, args.out, code)
        provenance_path = args.out / "training_provenance.json"
        provenance_sha = seal_training_provenance(provenance, provenance_path)
        source.verify(provenance_path, provenance_sha)
        frozen_sources = {**baseline.hashes, **source.hashes}
        freeze = dict(
            status="FROZEN_BEFORE_COMPARISON2025",
            models={
                POLICIES[0]: str((args.cue_root / "cue_net.txt").resolve()),
                POLICIES[1]: str((args.greek_root / "common_greek_net.txt").resolve()),
            },
            sources=frozen_sources,
            training_provenance_sha256=provenance_sha,
            scales=trained["scales"],
            policies=list(POLICIES),
            threshold=0,
            winner_selection=False,
            dependencies=code,
            calibration_edges_risk_units=metrics.CALIBRATION_EDGES.tolist(),
            development_seen=True,
        )
        freeze_path = args.out / "freeze.json"
        if freeze_path.exists():
            require(read_json(freeze_path) == freeze, "Frozen comparison changed")
        else:
            require(
                not (args.out / "predictions").exists()
                and not (args.out / "days").exists(),
                "Evaluation evidence without freeze",
            )
            atomic_json(freeze_path, freeze)
        evidence = Evidence(args.out, sha(freeze_path))
        frozen_sources[str(freeze_path.resolve())] = sha(freeze_path)
        import lightgbm as lgb

        models = {
            policy: lgb.Booster(model_file=path)
            for policy, path in freeze["models"].items()
        }
        try:
            for year in (2025, 2026) if args.stage == "all" else (int(args.stage),):
                evaluate_period(
                    year, source, models, trained["scales"], evidence, frozen_sources
                )
            source.recheck()
            baseline.recheck()
            provenance.recheck()
            require(dependencies() == code, "Implementation changed")
            all_complete = complete_comparison(evidence)
            print(
                dict(
                    status=(
                        "COMPLETE_FIXED_COMMON_GREEK_COMPARISON"
                        if all_complete
                        else "COMPLETE_FIXED_COMMON_GREEK_PERIOD"
                    ),
                    stage=args.stage,
                    winner_selected=None,
                ),
                flush=True,
            )
        except BaseException as error:
            atomic_json(
                args.out / ("failure_" + uuid.uuid4().hex + ".json"),
                dict(error=repr(error), stage=args.stage),
            )
            raise


if __name__ == "__main__":
    main()
