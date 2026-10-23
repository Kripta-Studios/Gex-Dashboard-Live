"""Audit 2026 H1 given sealed scores and a separately audited 2025 closure.

Only the independent 2025 auditor is reused. No producer, model fitting,
inference, producer scheduler or producer selection code is imported.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

import audit_monthly_walk_forward as independent


STATUS = independent.STATUS
SCOPE = "VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1"
REVIEW_STATUS = "PASS_MONTHLY_TEST_AUDITOR_IMPLEMENTATION_REVIEW"
RUNTIME_STATUS = "PASS_MONTHLY_TEST_AUDIT_RUNTIME_REVIEW"
MONTHS_2025 = tuple(f"2025{m:02d}" for m in range(1, 13))
MONTHS_2026 = tuple(f"2026{m:02d}" for m in range(1, 7))
MODES, TICKERS = independent.MODES, independent.TICKERS
HERE = Path(__file__).resolve().parent
SPEC = "MONTHLY_TEST_AUDIT_EXTENSION_SPEC_20261023.md"
require, sha, read_json = independent.require, independent.sha, independent.read_json


def dependencies():
    names = (
        "audit_monthly_walk_forward_test.py",
        "test_audit_monthly_walk_forward_test.py",
        SPEC,
        "audit_monthly_walk_forward.py",
        "test_audit_monthly_walk_forward.py",
        "MONTHLY_WALK_FORWARD_SEALED_SCORE_AUDIT_CONTRACT.md",
    )
    return {name: sha(HERE / name) for name in names}


def absolute_path(value):
    path = Path(value)
    require(path.is_absolute(), "Absolute evidence path required")
    require(".." not in path.parts, "Parent traversal in evidence path")
    return path.resolve()


def flatten_verified(groups):
    require(isinstance(groups, dict) and bool(groups), "Verified groups required")
    result = {}
    for group in groups.values():
        require(isinstance(group, dict), "Invalid verified group")
        for name, digest in group.items():
            path = str(absolute_path(name))
            require(
                isinstance(digest, str) and len(digest) == 64
                and all(c in "0123456789abcdef" for c in digest),
                "Invalid evidence SHA256",
            )
            require(path not in result or result[path] == digest,
                    "Conflicting verified hashes")
            result[path] = digest
    return result


def within(path, roots):
    path = Path(path).resolve()
    return any(path == root or path.is_relative_to(root) for root in roots)


class BoundedVerifier(independent.Verifier):
    def __init__(self, roots):
        super().__init__()
        self.roots = roots

    def file(self, category, path, expected=None):
        require(within(path, self.roots), "Evidence outside declared read roots")
        return super().file(category, path, expected)


def check_prediction(pred, actions, model_hash, scale):
    require(set(pred) == {"action_id", "state_i", "scores", "model_sha256", "scale"},
            "Prediction field schema differs")
    ids, states, scores = (np.asarray(pred[k]) for k in ("action_id", "state_i", "scores"))
    require(ids.dtype.kind in "iu" and states.dtype.kind in "iu"
            and ids.dtype == actions.action_id.dtype and states.dtype == actions.state_i.dtype
            and np.array_equal(ids, actions.action_id)
            and np.array_equal(states, actions.state_i), "Prediction identity/clock schema differs")
    require(scores.dtype == np.dtype("float64") and scores.shape == (len(actions),)
            and np.isfinite(scores).all(), "Prediction scores must be finite float64 vector")
    declared_model, declared_scale = np.asarray(pred["model_sha256"]), np.asarray(pred["scale"])
    require(declared_model.shape == () and declared_model.dtype.kind == "U"
            and str(declared_model) == model_hash, "Prediction model differs")
    require(declared_scale.shape == () and declared_scale.dtype == np.dtype("float64")
            and np.isfinite(scale) and scale > 0 and float(declared_scale) == scale,
            "Prediction scale differs")


def verify_authorities(root, source_audit, validation_audit, expected_validation_sha,
                       implementation_review, runtime_review):
    """This admission reads no actions, labels, scores or economics payloads."""
    verifier = independent.Verifier()
    for path in (implementation_review, runtime_review):
        verifier.file("audit_authorities", path)
    review = read_json(implementation_review)
    expected_dependencies = dependencies()
    require(review.get("status") == REVIEW_STATUS
            and review.get("dependencies") == expected_dependencies,
            "Exact independent test auditor review required")
    for name, digest in expected_dependencies.items():
        verifier.file("audit_code", HERE / name, digest)
    runtime = read_json(runtime_review)
    require(runtime.get("status") == RUNTIME_STATUS, "Runtime review required")
    binding = runtime.get("binding", {})
    require(binding.get("monthly_root") == str(root)
            and binding.get("source_audit") == str(source_audit)
            and binding.get("validation_audit") == str(validation_audit)
            and binding.get("validation_audit_sha256") == expected_validation_sha
            and binding.get("implementation_review_sha256") == sha(implementation_review)
            and runtime.get("dependencies") == expected_dependencies
            and runtime.get("scope") == SCOPE,
            "Runtime authority binding differs")
    roots = tuple(absolute_path(p) for p in runtime.get("allowed_read_roots", []))
    require(roots and all(p.is_dir() and p != Path(p.anchor) for p in roots),
            "Explicit bounded read roots required")
    for path in (root, source_audit, validation_audit, implementation_review,
                 runtime_review, HERE):
        require(within(path, roots), "Authority outside declared read roots")
    verifier.file("prior_validation_audit", validation_audit, expected_validation_sha)
    prior = read_json(validation_audit)
    pb = prior.get("binding", {})
    audited = prior.get("audited", {})
    require(prior.get("status") == STATUS
            and pb.get("completed_months") == list(MONTHS_2025)
            and audited.get("months") == 12
            and audited.get("unique_fit_windows") == 24
            and audited.get("calendar_ticker_days") == 750
            and audited.get("modes") == list(MODES)
            and audited.get("validation_selection_reconstructed") is True
            and audited.get("validation_period_report_reconstructed") is True,
            "Complete independently audited validation 2025 required")
    require(absolute_path(pb["monthly_root"]) == root
            and pb.get("run_contract_sha256") == binding.get("run_contract_sha256")
            and pb.get("session_audit_sha256") == binding.get("source_audit_sha256")
            and pb.get("index_sha256") == binding.get("index_sha256")
            and absolute_path(pb["session_root"]) == absolute_path(binding["session_root"]),
            "Prior validation roots or source bindings differ")
    allowed = flatten_verified(prior.get("verified_files"))
    for path, digest in allowed.items():
        require(within(path, roots), "Prior evidence outside declared read roots")
        verifier.file("inherited_validation", path, digest)
    required = {
        root / "run_contract.json": binding["run_contract_sha256"],
        source_audit: binding["source_audit_sha256"],
        absolute_path(pb["session_root"]) / "index.parquet": binding["index_sha256"],
        root / "validation_freeze.json": binding.get("validation_freeze_sha256"),
    }
    for path, digest in required.items():
        require(digest is not None and allowed.get(str(path)) == digest,
                "Required prior authority absent or different")
        verifier.file("prior_required", path, digest)
    source_binding = read_json(source_audit)["binding"]
    contract = read_json(root / "run_contract.json")
    for value in (source_binding["engine_root"], source_binding["feature_root"],
                  contract["engine_root"], contract["feature_root"]):
        require(within(absolute_path(value), roots), "Dataset root outside declared read roots")
    for name in ("validation_freeze.complete.json", "reports/2025.json",
                 "reports/2025.complete.json"):
        require(str(root / name) in allowed, "Prior freeze/report evidence missing")
    for stamp in MONTHS_2025:
        for name in ("daily.json", "daily.complete.json", "predictions.complete.json",
                     "economics.json", "economics.complete.json"):
            require(str(root / "months" / stamp / name) in allowed,
                    "Prior month closure missing")
    expected_keys = {
        independent.window(mode, date(2025, month, 1))[2]
        for month in range(1, 13) for mode in MODES
    }
    require(len(expected_keys) == 24, "Internal validation window count")
    for key in expected_keys:
        for name in (f"models/{key}.txt", f"models/{key}.fit_started.json",
                     f"models/{key}.complete.json", f"fits/{key}/inputs.json",
                     f"fits/{key}/inputs.complete.json"):
            require(str(root / name) in allowed, "Prior fit authority missing")
    return verifier, runtime, prior, allowed


def merge_verifiers(destination, source):
    """Merge only already checked maps; final recheck covers the complete union."""
    for path, digest in source._flat.items():
        require(path not in destination._flat or destination._flat[path] == digest,
                "Conflicting inherited evidence")
        destination._flat[path] = digest
    for category, group in source.files.items():
        destination.files.setdefault(category, {}).update(group)


class TestAudit(independent.MonthlyAudit):
    __test__ = False

    def __init__(self, monthly_root, source_audit, validation_audit,
                 expected_validation_sha, implementation_review, runtime_review):
        root = Path(monthly_root).resolve()
        source_path, prior_path = Path(source_audit).resolve(), Path(validation_audit).resolve()
        own_review, runtime_path = Path(implementation_review).resolve(), Path(runtime_review).resolve()
        checked, runtime, prior, allowed = verify_authorities(
            root, source_path, prior_path, expected_validation_sha, own_review, runtime_path
        )
        super().__init__(root, source_path)
        merge_verifiers(self.v, checked)
        self.runtime, self.prior, self.prior_allowed = runtime, prior, allowed
        self.prior_path, self.prior_hash = prior_path, expected_validation_sha
        self.allowed_read_roots = tuple(absolute_path(p) for p in runtime["allowed_read_roots"])
        bounded = BoundedVerifier(self.allowed_read_roots)
        merge_verifiers(bounded, self.v)
        self.v = bounded
        self.evidence = independent.Evidence(self.root, self.v, self.contract_hash)
        self.authority_dependencies = dependencies()
        binding = runtime["binding"]
        require(self.contract_hash == binding["run_contract_sha256"]
                and self.source_audit_hash == binding["source_audit_sha256"]
                and self.index_hash == binding["index_sha256"]
                and self.session_root == absolute_path(binding["session_root"])
                and self.contract.get("threshold_usd") == 0,
                "Runtime/scientific contract differs")
        self.freeze_record = self.evidence.member(
            "validation_freeze", self.root / "validation_freeze.json", "freeze"
        )
        self.freeze = read_json(self.root / "validation_freeze.json")
        mode = self.freeze.get("selected_mode")
        require(mode is None or mode in MODES, "Unknown frozen mode")
        require(self.freeze.get("status") == (
            "FAIL_NO_DAILY_COMPLIANT_MODE" if mode is None else "SELECTED_RESEARCH_MODE")
            and self.freeze.get("selection_period") == "2025"
            and self.freeze.get("outcomes_2026_used_for_mode_selection") is False
            and self.freeze.get("update_rule") == "FROZEN_CALENDAR_STATIC_EXPANDING_ROLLING12"
            and self.freeze.get("approved") is False,
            "Frozen validation decision differs")
        self.freeze_time = independent.parse_utc(self.freeze_record["completed_utc"])
        self.check_calendar()
        self.preflight_closure()

    def check_calendar(self):
        index = self.index.reset_index()
        require(index.ticker.isin(TICKERS).all()
                and index.status.isin(["COMPLETE", "MISSING_SOURCE"]).all()
                and index.close_i.isin([210, 390]).all(), "Invalid source calendar")
        prior = index[index.date.str.startswith("2025")]
        current = index[index.date.str.startswith("2026")]
        require(len(prior) == 750 and (prior.status == "COMPLETE").all(),
                "Validation source coverage differs")
        require(len(current) == 369 and (current.status == "COMPLETE").sum() == 363
                and (current.status == "MISSING_SOURCE").sum() == 6
                and current.date.str[:6].isin(MONTHS_2026).all()
                and (current.close_i == 390).all(), "H1 source coverage differs")
        dates = set(current.date)
        require(len(dates) == 123
                and all(set(current[current.ticker == ticker].date) == dates for ticker in TICKERS),
                "Incomplete or unequal ticker calendars")
        self.missing_identities = sorted(
            [list(key) for key, row in self.index.iterrows() if row.status == "MISSING_SOURCE"]
        )
        require(len(self.missing_identities) == 6
                and all(day.startswith("2026") for _, day in self.missing_identities),
                "Missing identities outside declared period")
        for day in self.days.values():
            if day.status == "COMPLETE":
                require(within(day.root, self.allowed_read_roots)
                        and all(within(p, self.allowed_read_roots) for p in day.feature_paths),
                        "Source references outside declared read roots")

    def preflight_closure(self):
        """Require the entire output closure before opening any training labels."""
        for stamp in MONTHS_2026:
            for name in ("daily", "economics"):
                key = f"months/{stamp}/{name}"
                self.evidence.member(key, self.root / (key + ".json"), "test_closure")
            record, sealed = self.evidence.marker(f"months/{stamp}/predictions", "test_closure")
            expected = sorted(independent.window(mode, date(int(stamp[:4]), int(stamp[4:]), 1))[2]
                              for mode in MODES)
            require(record.get("extra", {}).get("fit_keys") == expected
                    and record["extra"].get("labels_read") is False,
                    "All three fit identities must be sealed")
            require(self.freeze_time < independent.parse_utc(record["completed_utc"]),
                    "Test predictions precede validation freeze")
            self.check_month_predictions(stamp, record, sealed)
        for name in ("reports/2025", "reports/2026", "completion"):
            self.evidence.member(name, self.root / (name + ".json"), "test_closure")
        completion = read_json(self.root / "completion.json")
        require(completion == dict(
            status="COMPLETE", modes=list(MODES), evaluated_months=18,
            unique_fit_windows=36, selected_mode=self.freeze["selected_mode"],
            development_seen=True, promotion_approved=False,
            report_hashes={str(year): sha(self.root / f"reports/{year}.json")
                           for year in (2025, 2026)},
        ), "Incomplete or changed full monthly completion")

    def check_month_predictions(self, stamp, month_record, month_sealed):
        prediction_time = independent.parse_utc(month_record["completed_utc"])
        fits = {}
        for key in month_record["extra"]["fit_keys"]:
            model = self.root / f"models/{key}.txt"
            started = self.root / f"models/{key}.fit_started.json"
            model_record = self.evidence.member("models/" + key, model, "models")
            self.evidence.member("models/" + key, started, "models")
            model_time = independent.parse_utc(model_record["completed_utc"])
            require(model_time < prediction_time, "Model completed after monthly prediction seal")
            info_path = self.root / f"fits/{key}/inputs.json"
            self.evidence.member(f"fits/{key}/inputs", info_path, "fit_inputs")
            fits[key] = (read_json(info_path), sha(model), model_time)
        days = sorted((d for d in self.days.values() if d.stamp.startswith(stamp)
                       and d.status == "COMPLETE"), key=lambda d: (d.ticker, d.stamp))
        for day in days:
            actions = self.source_frame(day, "actions.parquet", ["action_id", "state_i"])
            for key, (info, model_hash, model_time) in fits.items():
                name = f"predictions/{stamp}/{key}/{day.ticker}/{day.stamp}"
                path = self.root / (name + ".npz")
                require(str(path) in month_sealed, "Prediction absent from monthly score seal")
                record = self.evidence.member(name, path, "prediction_manifests")
                require(model_time < independent.parse_utc(record["completed_utc"]) <= prediction_time,
                        "Prediction completion outside model/month seal order")
                check_prediction(independent.load_npz(path), actions, model_hash, info["scales"][day.ticker])

    def source_frame(self, day, filename, columns=None):
        require(within(day.root / filename, self.allowed_read_roots),
                "Sidecar outside declared read roots")
        return super().source_frame(day, filename, columns)

    def audit_fit(self, key, start, stop):
        require(date(2026, 1, 1) <= stop <= date(2026, 6, 1),
                "Only the twelve new test fits are reconstructed")
        expected = {independent.window(mode, stop)[:2] for mode in ("expanding", "rolling12")}
        require((start, stop) in expected and key == f"train_{start:%Y%m%d}_{stop:%Y%m%d}_exclusive",
                "Wrong test fit window")
        started_path = self.root / "models" / (key + ".fit_started.json")
        model_path = self.root / "models" / (key + ".txt")
        record = self.evidence.member("models/" + key, model_path, "models")
        self.evidence.member("models/" + key, started_path, "models")
        started = read_json(started_path)
        started_time = independent.parse_utc(started["started_utc"])
        require(self.freeze_time < started_time < independent.parse_utc(record["completed_utc"]),
                "Test fit did not follow validation freeze or completion order")
        info_path = self.root / "fits" / key / "inputs.json"
        self.evidence.member("fits/" + key + "/inputs", info_path, "fit_inputs")
        for path in read_json(info_path)["input_hashes"]:
            require(within(absolute_path(path), self.allowed_read_roots),
                    "Fit input outside declared read roots")
        return super().audit_fit(key, start, stop)

    def inherited_static(self):
        key = independent.window("static", date(2026, 1, 1))[2]
        info_path = self.root / "fits" / key / "inputs.json"
        model_path = self.root / "models" / (key + ".txt")
        for path in (info_path, model_path, model_path.with_suffix(".fit_started.json")):
            require(str(path) in self.prior_allowed, "Static fit absent from prior audit")
            self.v.file("static_inherited", path, self.prior_allowed[str(path)])
        self.evidence.member("fits/" + key + "/inputs", info_path, "static_inherited")
        self.evidence.member("models/" + key, model_path, "static_inherited")
        info = read_json(info_path)
        require(info["fit_key"] == key and info["train_start"] == "2023-01-01"
                and info["train_stop_exclusive"] == "2025-01-01"
                and info["config"] == self.contract["config"]
                and info["scales"] == self.freeze["common_scales"],
                "Inherited static fit differs")
        return key, (info, sha(model_path))

    def period_report(self, records):
        columns = ["ticker", "date", "exit_i", "net_base", "net_adverse", "hold_minutes", "reason"]

        def summarize(rows, ledger):
            available = [r for r in rows if r["source_status"] == "COMPLETE"]
            missing = len(rows) - len(available)
            active = sum(r["trades"] > 0 for r in available)
            zero = len(available) - active
            economy = independent.economic_summary(ledger)
            require(economy["trades"] == sum(r["trades"] for r in available)
                    and np.isclose(economy["net_base"], sum(r["net_base"] for r in available))
                    and np.isclose(economy["net_adverse"], sum(r["net_adverse"] for r in available)),
                    "Period daily/ledger mismatch")
            return dict(expected_ticker_days=len(rows), available_ticker_days=len(available),
                missing_no_evaluable=missing, available_days_with_fill=active,
                available_days_without_fill=zero, observable_daily_pass=bool(available) and zero == 0,
                full_calendar_daily_status=("NO_EVALUABLE_MISSING_SOURCE" if missing else
                    "PASS" if available and zero == 0 else "FAIL_OBSERVED_ZERO"),
                daily_requirement_satisfied=bool(available) and missing == 0 and zero == 0,
                available_economics=economy,
                net_base_per_available_day=economy["net_base"] / len(available) if available else None,
                missing_day_economics=None)

        expected = {(d.ticker, d.stamp): d.status for d in self.days.values()
                    if d.stamp.startswith("2026")}
        modes = {}
        for mode in MODES:
            rows = records[mode]
            keys = [(row["ticker"], row["date"]) for row in rows]
            require(len(keys) == len(set(keys)) and set(keys) == set(expected)
                    and all(row["source_status"] == expected[key] for row, key in zip(rows, keys)),
                    "Test report calendar differs")
            frames = []
            for row in rows:
                if row["source_status"] == "COMPLETE":
                    key = f"ledgers/{row['date'][:6]}/{mode}/{row['ticker']}/{row['date']}"
                    path = self.root / (key + "_ledger.parquet")
                    self.evidence.member(key, path, "test_ledgers")
                    frames.append(pd.read_parquet(path, columns=columns))
            ledger = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)
            ledger = ledger.sort_values(["date", "exit_i", "ticker"], kind="stable")
            modes[mode] = dict(overall=summarize(rows, ledger), tickers={ticker: summarize(
                [row for row in rows if row["ticker"] == ticker], ledger[ledger.ticker == ticker]
            ) for ticker in TICKERS})
        expected_report = dict(year=2026, modes=modes, selected_mode=self.freeze["selected_mode"],
            selection_period=2025, development_seen=True, promotion_approved=False,
            missing_sources_are_not_observed_losses=True)
        require(read_json(self.root / "reports/2026.json") == expected_report,
                "Development period report differs")
        return expected_report

    def audit_test(self):
        key, value = self.inherited_static()
        fit_cache = {key: value}
        records = {mode: [] for mode in MODES}
        for stamp in MONTHS_2026:
            daily = super().audit_month(stamp, fit_cache)
            for mode in MODES:
                records[mode].extend(daily[mode])
        require(len(fit_cache) == 13, "Expected twelve new fits plus static")
        self.period_report(records)
        require(dependencies() == self.authority_dependencies, "Auditor code changed during run")
        self.v.recheck()
        independent.recheck_hashes(self.source_reads, "Source changed after test audit read")
        return dict(status=STATUS, scope=SCOPE,
            binding=dict(monthly_root=str(self.root), run_contract_sha256=self.contract_hash,
                session_root=str(self.session_root), session_audit_sha256=self.source_audit_hash,
                index_sha256=self.index_hash, completed_months=list(MONTHS_2025 + MONTHS_2026)),
            prior_validation_audit=dict(path=str(self.prior_path), sha256=self.prior_hash,
                scope="VALIDATION_2025", inventory_rehashed=True,
                reconstruction_inherited_not_repeated=True),
            verified_files=self.v.files,
            audited=dict(new_months=6, new_unique_fit_windows=12, models_used_test=13,
                total_unique_fit_windows=36, modes=list(MODES), calendar_ticker_days=369,
                available_ticker_days=363, missing_no_evaluable=6,
                missing_identities=self.missing_identities,
                selected_mode=self.freeze["selected_mode"],
                selection_reused_without_test_reselection=True,
                new_fit_samples_targets_weights_matrices_reconstructed=True,
                scheduler_ledgers_economics_reconstructed=True,
                all_three_monthly_fit_scores_sealed_before_ledgers=True,
                test_period_report_reconstructed=True),
            limitations=[
                "Given sealed scores only: no model refit or repeated inference.",
                "Validation 2025 reconstruction is inherited from the pinned prior audit; its inventory was rehashed.",
                "Training feature chunks and matrices are compared; features and quotes are not rebuilt from raw.",
                "Artifact seal order is not historical receipt or historical publication evidence.",
                "Missing daily zeros are structural serialization, not observed zero-return trades.",
                "Seen development only; no prospective or live profitability claim.",
            ], development_seen=True, promotion_approved=False)


@contextmanager
def exclusive_output(root):
    """A new output root and an OS lock; never adopt a partial previous attempt."""
    root.mkdir(parents=True, exist_ok=False)
    with (root / ".lock").open("x+b") as handle:
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def run(args):
    output = args.output.resolve()
    require(not output.exists(), "Use a new audit output directory")
    for protected in (args.monthly_root.resolve(), HERE):
        require(not (output == protected or output.is_relative_to(protected)
                     or protected.is_relative_to(output)), "Output overlaps protected evidence")
    auditor = TestAudit(args.monthly_root, args.source_audit, args.validation_audit,
                        args.expected_validation_audit_sha256,
                        args.implementation_review, args.runtime_review)
    require(not (output == auditor.session_root or output.is_relative_to(auditor.session_root)
                 or auditor.session_root.is_relative_to(output)), "Output overlaps source dataset")
    for day in auditor.days.values():
        if day.status == "COMPLETE":
            require(not (output == day.root or output.is_relative_to(day.root)
                         or day.root.is_relative_to(output)), "Output overlaps referenced source day")
    with exclusive_output(output):
        snapshots = {}
        for name, digest in auditor.authority_dependencies.items():
            path = output / "executed_code" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                handle.write((HERE / name).read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
            require(sha(path) == digest, "Audit snapshot changed")
            snapshots[str(path)] = digest
        for name, original in (("implementation_review.json", args.implementation_review),
                               ("runtime_review.json", args.runtime_review)):
            path = output / "authorities" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                handle.write(original.read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
            require(sha(path) == sha(original), "Audit authority snapshot changed")
            snapshots[str(path)] = sha(path)
        independent.atomic_json(output / "launch.json", dict(scope=SCOPE,
            dependencies=auditor.authority_dependencies, snapshots=snapshots,
            runtime_review_sha256=sha(args.runtime_review),
            validation_audit_sha256=args.expected_validation_audit_sha256))
        try:
            result = auditor.audit_test()
            independent.recheck_hashes(snapshots, "Audit snapshot changed before publication")
            result["audit_script_sha256"] = sha(__file__)
            result["execution_snapshots"] = snapshots
            independent.atomic_json(output / "audit.json", result)
        except BaseException as exc:
            independent.atomic_json(output / "failure.json", dict(
                status="FAILED_OR_INTERRUPTED_PRESERVED", error=repr(exc), scope=SCOPE))
            raise
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--monthly-root", type=Path, required=True)
    parser.add_argument("--source-audit", type=Path, required=True)
    parser.add_argument("--validation-audit", type=Path, required=True)
    parser.add_argument("--expected-validation-audit-sha256", required=True)
    parser.add_argument("--implementation-review", type=Path, required=True)
    parser.add_argument("--runtime-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    result = run(parser.parse_args())
    print(json.dumps({"status": result["status"], "scope": result["scope"]}, indent=2))


if __name__ == "__main__":
    main()
