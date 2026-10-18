"""Two frozen net regressors, full calendar, no fit, winner selection or threshold search."""

from __future__ import annotations

import argparse
from datetime import date, datetime
import hashlib
from pathlib import Path
import uuid

import numpy as np
import pandas as pd

import features
import market_cue_comparison as comparison
import market_cue_vectors as vectors
import rolling_monthly_schedule as calendar
import train_market_cue_control as training

require, sha, read_json, atomic_json = (
    training.require,
    training.sha,
    training.read_json,
    training.atomic_json,
)
DEPENDENCIES = (
    "evaluate_market_cue_control.py",
    "market_cue_comparison.py",
    *training.DEPENDENCIES,
    "rolling_monthly_schedule.py",
    "MARKET_CUE_COMPARISON_PLAN.md",
    "train_models.py",
)
LABEL_COLUMNS = ["action_id", "status", "exit_i", "net_base", "net_adverse"]


def dependencies():
    return {name: sha(Path(__file__).with_name(name)) for name in DEPENDENCIES}


class Evidence(training.Checkpoints):
    def complete(self, name, required=()):
        if not super().complete(name, required):
            return False
        for path, digest in (
            read_json(self.marker(name))["extra"].get("sources", {}).items()
        ):
            require(sha(path) == digest, "Changed checkpoint input: " + path)
        return True


class OriginalScores:
    """Full-session inference must equal previously audited original scores."""

    def __init__(self, original, audit_path):
        self.original = original
        audit = read_json(audit_path)
        self.manifests, self.manifest_hashes = {}, {}
        for period, field in (
            ("validation", "validation_prediction_manifest_sha256"),
            ("test", "test_prediction_manifest_sha256"),
        ):
            path = original.original / period / "prediction_hashes.json"
            original.verify(path, audit["binding"][field])
            self.manifests[period] = read_json(path)
            self.manifest_hashes[str(path.resolve())] = audit["binding"][field]

    def compare(self, key, close_i, actions, score):
        if close_i == 210:
            return {
                "status": "NO_ORIGINAL_REFERENCE_SHORT_SESSION",
                "bitexact_checked": False,
            }, {}
        require(close_i == 390, "Unknown reference clock")
        ticker, day = key.split("/")
        period = "validation" if day.startswith("2025") else "test"
        manifest_path = self.original.original / period / "prediction_hashes.json"
        self.original.verify(
            manifest_path, self.manifest_hashes[str(manifest_path.resolve())]
        )
        filename = ticker + "_" + day + ".npz"
        path = self.original.original / period / filename
        expected = self.manifests[period][filename]
        self.original.verify(path, expected)
        original_row = self.original.index.loc[(ticker, day)]
        require(original_row.status == "COMPLETE", "Original full session missing")
        action_path = Path(original_row.day_root) / "actions.parquet"
        self.original.verify(action_path, original_row.actions_sha256)
        original_actions = pd.read_parquet(
            action_path, columns=["action_id", "state_i"]
        )
        with np.load(path, allow_pickle=False) as data:
            ids, original_scores = data["action_ids"], data["gbt_net"]
        require(
            np.array_equal(ids, actions.action_id.to_numpy())
            and np.array_equal(original_actions.action_id.to_numpy(), ids)
            and np.array_equal(
                original_actions.state_i.to_numpy(), actions.state_i.to_numpy()
            ),
            "Original control action/state order differs",
        )
        require(
            np.asarray(score).dtype == original_scores.dtype
            and np.asarray(score).shape == original_scores.shape
            and np.asarray(score).tobytes() == original_scores.tobytes(),
            "Original full-session control scores are not bitexact",
        )
        sources = {
            str(path.resolve()): expected,
            str(action_path.resolve()): original_row.actions_sha256,
            str(manifest_path.resolve()): self.manifest_hashes[
                str(manifest_path.resolve())
            ],
        }
        for filename, digest in sources.items():
            self.original.verify(filename, digest)
        return {
            "status": "EXACT_ORIGINAL_FULL_SESSION",
            "bitexact_checked": True,
            "actions": len(actions),
        }, sources


class SessionInputs:
    """Audited 2595 full +24 short sessions; no legacy oracle ledger/advantages."""

    verify = training.OriginalInputs.verify
    recheck = training.OriginalInputs.recheck

    def __init__(self, root, audit_path, original_scores):
        self.original_scores = original_scores
        self.root, self.hashes = Path(root).resolve(), {}
        audit = read_json(audit_path)
        require(
            audit.get("status") == "PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT",
            "Dataset audit required",
        )
        binding = audit["binding"]
        require(
            Path(binding["engine_root"]).resolve() == self.root, "Wrong dataset root"
        )
        require(
            (binding["available_days"], binding["missing_days"]) == (2619, 6),
            "Wrong dataset coverage",
        )
        self.verify(audit_path, sha(audit_path))
        for name, field in (
            ("index.parquet", "index_sha256"),
            ("completion.json", "completion_sha256"),
            ("dataset_contract.json", "dataset_contract_sha256"),
        ):
            self.verify(self.root / name, binding[field])
        require(
            read_json(self.root / "completion.json")["status"] == "COMPLETE",
            "Incomplete dataset",
        )
        self.feature_root = Path(binding["feature_root"]).resolve()
        self.verify(
            self.feature_root / "feature_contract.json",
            binding["feature_contract_sha256"],
        )
        self.contract = read_json(self.feature_root / "feature_contract.json")
        require(
            self.contract.get("outcomes_read") is False, "Noncausal feature contract"
        )
        for name, digest in self.contract["dependencies"].items():
            require(Path(name).name == name, "Unsafe feature dependency")
            self.verify(Path(__file__).with_name(name), digest)
        for name, expected in (
            ("base_names", features.BASE_NAMES),
            ("token_names", features.TOKEN_NAMES),
            ("map_names", features.MAP_NAMES),
            ("action_names", features.ACTION_NAMES),
        ):
            require(
                self.contract["schema"][name] == list(expected), "Causal schema changed"
            )
        paths = [
            "features_path",
            "features_meta_path",
            "action_features_path",
            "action_features_meta_path",
        ]
        self.paths = paths
        self.digests = [
            "features_sha256",
            "features_meta_sha256",
            "action_features_sha256",
            "action_features_meta_sha256",
        ]
        index = pd.read_parquet(
            self.root / "index.parquet",
            columns=[
                "ticker",
                "date",
                "status",
                "day_root",
                "close_i",
                "actions_sha256",
                "labels_sha256",
                "cache_npz_sha256",
                "cache_meta_sha256",
                *paths,
                *self.digests,
            ],
        )
        index["date"] = index.date.astype(str)
        self.index = index.set_index(["ticker", "date"], verify_integrity=True)
        import exchange_calendars as xc

        schedule = xc.get_calendar("XNYS").schedule.loc["2023-01-03":"2026-06-30"]
        durations = (schedule.close - schedule.open) / pd.Timedelta(minutes=1)
        expected = {stamp.date(): int(minutes) for stamp, minutes in durations.items()}
        sessions = [
            calendar.Session(
                ticker,
                datetime.strptime(day, "%Y%m%d").date(),
                int(row.close_i),
                row.status,
            )
            for (ticker, day), row in self.index.iterrows()
        ]
        counts = calendar.require_session_universe(
            sessions, expected, date(2023, 1, 1), date(2026, 7, 1)
        )
        require(
            counts
            == dict(
                expected=2625,
                available=2619,
                missing_no_evaluable=6,
                early_close_ticker_days=24,
            ),
            "Calendar differs",
        )
        missing = {
            (ticker, day)
            for (ticker, day), row in self.index.iterrows()
            if row.status == "MISSING_SOURCE"
        }
        require(
            missing
            == {
                (ticker, day)
                for ticker in ("SPY", "QQQ")
                for day in ("20260401", "20260409", "20260415")
            },
            "Missing identities changed",
        )
        require(
            len(self.keys(2025)) == 750 and len(self.keys(2026)) == 369,
            "Evaluation calendar counts differ",
        )

    def keys(self, year):
        return sorted(
            (ticker + "/" + day)
            for ticker, day in self.index.index
            if day.startswith(str(year))
        )

    def reference_control(self, key, actions, score):
        return self.original_scores.compare(
            key, int(self.row(key).close_i), actions, score
        )

    def row(self, key):
        return self.index.loc[tuple(key.split("/"))]

    def feature_day(self, key):
        row = self.row(key)
        require(row.status == "COMPLETE", "Missing source")
        paths = [Path(row[name]).resolve() for name in self.paths]
        hashes = {str(path): row[field] for path, field in zip(paths, self.digests)}
        for path, digest in hashes.items():
            self.verify(path, digest)
        meta, ameta = read_json(paths[1]), read_json(paths[3])
        for metadata, path in ((meta, paths[0]), (ameta, paths[2])):
            require(
                metadata.get("outcomes_read") is False
                and metadata["sha256"] == hashes[str(path)],
                "Feature metadata differs",
            )
            require(
                metadata["binding"]["dependencies"] == self.contract["dependencies"]
                and metadata["binding"]["source_sha256"] == row.cache_npz_sha256
                and metadata["binding"]["source_metadata_sha256"]
                == row.cache_meta_sha256,
                "Feature provenance differs",
            )
        require(
            meta["schema"] == self.contract["schema"]
            and ameta["action_names"] == list(features.ACTION_NAMES),
            "Feature names differ",
        )
        action_path = Path(row.day_root) / "actions.parquet"
        self.verify(action_path, row.actions_sha256)
        actions = pd.read_parquet(
            action_path, columns=["action_id", *features.ACTION_INPUT_NAMES]
        )
        require(
            hashlib.sha256(actions.to_numpy(np.float64).tobytes()).hexdigest()
            == ameta["binding"]["action_inputs_sha256"],
            "Action feature inputs differ",
        )
        with np.load(paths[0], allow_pickle=False) as data:
            pack = {
                name: data[name]
                for name in (
                    "state_i",
                    "base",
                    "tokens",
                    "token_mask",
                    "bar_mask",
                    "bar_end_i",
                    "maps",
                    "map_mask",
                )
            }
        with np.load(paths[2], allow_pickle=False) as data:
            ids, pack["action_features"] = data["action_id"], data["action_features"]
        require(
            np.array_equal(pack["state_i"], np.arange(60, int(row.close_i) - 14)),
            "Wrong feature horizon",
        )
        hashes[str(action_path.resolve())] = row.actions_sha256
        for path, digest in hashes.items():
            self.verify(path, digest)
        return pack, ids, actions, hashes

    def labels(self, key):
        row = self.row(key)
        path = Path(row.day_root) / "labels.parquet"
        self.verify(path, row.labels_sha256)
        labels = pd.read_parquet(path, columns=LABEL_COLUMNS)
        self.verify(path, row.labels_sha256)
        return labels, {str(path.resolve()): row.labels_sha256}


def predict_both(pack, ids, actions, models, scale, block=1024):
    require(
        set(models) == set(comparison.POLICIES), "Exactly two fixed models required"
    )
    require(
        models[comparison.POLICIES[0]].num_feature() == 1954
        and models[comparison.POLICIES[1]].num_feature() == 152,
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
    result = {comparison.POLICIES[0]: np.empty(len(actions), np.float64)}
    for start in range(0, len(actions), block):
        stop = min(start + block, len(actions))
        x = comparison.flatten_original(pack, ai[start:stop], si[start:stop])
        result[comparison.POLICIES[0]][start:stop] = (
            models[comparison.POLICIES[0]].predict(x, num_threads=4) * scale
        )
    cue_pack = {
        name: value for name, value in pack.items() if name not in ("maps", "map_mask")
    }
    result[comparison.POLICIES[1]] = training.predict_offered_day(
        models[comparison.POLICIES[1]], cue_pack, ids, actions, scale, block
    )["scores"]
    require(
        all(np.isfinite(value).all() for value in result.values()),
        "Nonfinite predictions",
    )
    return result


def save_npz(path, **arrays):
    import os

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        np.savez_compressed(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())


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
    expected_reference = (
        "EXACT_ORIGINAL_FULL_SESSION"
        if int(row.close_i) == 390
        else "NO_ORIGINAL_REFERENCE_SHORT_SESSION"
    )
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
        ],
    ):
        return True
    evidence.preserve(path)
    files, sources = [path, evidence.root / "freeze.json"], {}
    for year in (2025, 2026):
        marker = evidence.marker("period" + str(year))
        record = read_json(marker)
        files.extend([marker, *(evidence.root / member for member in record["files"])])
        sources.update(record["extra"]["sources"])
    atomic_json(
        path,
        dict(
            status="COMPLETE_FIXED_CUE_COMPARISON",
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


def main():
    parser = argparse.ArgumentParser()
    for name in (
        "cue-root",
        "original-root",
        "engine-root",
        "learner-audit",
        "engine-audit",
        "session-root",
        "session-audit",
        "review",
        "out",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--stage", choices=("2025", "2026", "all"), default="2025")
    args = parser.parse_args()
    code = dependencies()
    review = read_json(args.review)
    require(
        review.get("status") == "PASS_MARKET_CUE_COMPARISON_IMPLEMENTATION_REVIEW"
        and review.get("dependencies") == code,
        "Exact comparison implementation review required",
    )
    authority_paths = {
        "learner_audit_sha256": args.learner_audit,
        "engine_audit_sha256": args.engine_audit,
        "session_audit_sha256": args.session_audit,
        "cue_contract_sha256": args.cue_root / "run_contract.json",
        "cue_model_completion_sha256": args.cue_root / "model.complete.json",
    }
    require(
        review.get("authorities")
        == {name: sha(path) for name, path in authority_paths.items()},
        "Comparison authorities differ from review",
    )
    require(
        all(
            not args.out.resolve().is_relative_to(path.resolve())
            for path in (
                args.cue_root,
                args.original_root,
                args.engine_root,
                args.session_root,
            )
        ),
        "Separate output root required",
    )
    with training.output_lock(args.out):
        original = training.OriginalInputs(
            args.original_root, args.engine_root, args.learner_audit, args.engine_audit
        )
        trained = read_json(args.cue_root / "run_contract.json")
        require(
            trained["dependencies"] == training.dependencies()
            and trained["scales"] == original.scales
            and trained["config"] == training.CONFIG
            and trained["training_rows"] == 270377,
            "Cue fit contract differs",
        )
        for path, digest in trained["sources"].items():
            original.verify(path, digest)
        cue = training.Checkpoints(
            args.cue_root, sha(args.cue_root / "run_contract.json")
        )
        require(
            cue.complete("matrix", ["train_x.npy", "targets.npz"])
            and cue.complete(
                "model", ["cue_net.txt", "fit_started.json", "matrix.complete.json"]
            ),
            "Cue model incomplete",
        )
        for filename in (
            "run_contract.json",
            "matrix.complete.json",
            "model.complete.json",
            "fit_started.json",
            "cue_net.txt",
        ):
            original.verify(args.cue_root / filename, sha(args.cue_root / filename))
        source = SessionInputs(
            args.session_root,
            args.session_audit,
            OriginalScores(original, args.learner_audit),
        )
        training.bind_code_snapshots(source, args.out, code)
        source.verify(args.review, sha(args.review))
        frozen_sources = {**original.hashes, **source.hashes}
        freeze = dict(
            models={
                comparison.POLICIES[0]: str(
                    (args.original_root / "gbt_net.txt").resolve()
                ),
                comparison.POLICIES[1]: str((args.cue_root / "cue_net.txt").resolve()),
            },
            sources=frozen_sources,
            scales=original.scales,
            policies=list(comparison.POLICIES),
            threshold=0,
            winner_selection=False,
            dependencies=code,
            calibration_edges_risk_units=comparison.CALIBRATION_EDGES.tolist(),
            status="FROZEN_BEFORE_COMPARISON2025",
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
                    year, source, models, original.scales, evidence, frozen_sources
                )
            complete_comparison(evidence)
            original.recheck()
            source.recheck()
            require(dependencies() == code, "Implementation changed")
            print(
                {
                    "status": "COMPLETE_FIXED_CUE_COMPARISON",
                    "stage": args.stage,
                    "winner_selected": None,
                },
                flush=True,
            )
        except BaseException as error:
            atomic_json(
                args.out / ("failure_" + uuid.uuid4().hex + ".json"),
                {"error": repr(error), "stage": args.stage},
            )
            raise


if __name__ == "__main__":
    main()
