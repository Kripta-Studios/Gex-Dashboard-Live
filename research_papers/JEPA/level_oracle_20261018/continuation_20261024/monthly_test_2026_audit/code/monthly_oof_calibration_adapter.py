"""Audited monthly artifacts -> sealed OOF maxima; no base fitting or inference.

No operation runs on import. A future independent monthly OUTPUT audit is
mandatory: an implementation review or source-only audit is insufficient.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from contextlib import contextmanager
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

import oof_maximum_calibration as core
import rolling_monthly_schedule as schedule

STATUS = "PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES"
require = core.require


def dependency_hashes():
    return {
        name: core.file_sha(Path(__file__).with_name(name))
        for name in (
            "monthly_oof_calibration_adapter.py",
            "oof_maximum_calibration.py",
            "rolling_monthly_schedule.py",
            "MONTHLY_OOF_CALIBRATION_ADAPTER_SPEC.md",
            "PREQUENTIAL_MAX_CALIBRATION_DESIGN.md",
            "OOF_MAXIMUM_CALIBRATION_INTEGRATION.md",
        )
    }


def flatten_verified(groups):
    """Independent authority groups may repeat a path only with the same hash."""
    result = {}
    require(
        isinstance(groups, dict) and bool(groups), "Verified artifact groups required"
    )
    for group in groups.values():
        require(isinstance(group, dict), "Expected grouped verified_files")
        for name, digest in group.items():
            path = Path(name)
            require(path.is_absolute(), "Verified path must be absolute")
            key = str(path.resolve())
            core.hash_value(digest)
            require(
                key not in result or result[key] == digest,
                "Conflicting verified artifact hashes",
            )
            result[key] = digest
    return result


def publish_or_verify(path, payload):
    """Caller must hold its output-root lock when this can race with a writer."""
    path = Path(path)
    if path.exists():
        expected = core.content_sha(payload)
        core.load_seal(path, expected)
        return expected
    return core.publish(path, payload)


@contextmanager
def output_lock(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


class MonthlyInputs:
    def __init__(
        self, root, audit_path, expected_audit_sha, session_root, session_audit
    ):
        self.root, self.session_root = (
            Path(root).resolve(),
            Path(session_root).resolve(),
        )
        self.used = {}
        audit = core.load_seal(audit_path, expected_audit_sha)
        require(
            audit.get("status") == STATUS, "Independent MONTHLY output audit required"
        )
        self.authority_sha = expected_audit_sha
        self.used[str(Path(audit_path).resolve())] = expected_audit_sha
        binding = audit["binding"]
        require(
            Path(binding["monthly_root"]).resolve() == self.root
            and Path(binding["session_root"]).resolve() == self.session_root,
            "Wrong audited roots",
        )
        self.allowed = flatten_verified(audit["verified_files"])
        self.completed_months = set(binding["completed_months"])
        require(
            len(self.completed_months) == len(binding["completed_months"]),
            "Duplicate audited months",
        )
        require(
            all(
                "202501" <= m <= "202606" and core.month_start(m)
                for m in self.completed_months
            ),
            "Undeclared audited month",
        )
        self.binding = binding["run_contract_sha256"]
        self.verify(self.root / "run_contract.json", self.binding)
        self.contract = self.json(self.root / "run_contract.json")
        require(
            self.contract["version"] == "MONTHLY_NET_WALK_FORWARD_V1"
            and self.contract["features"] == 1954
            and self.contract["threshold_usd"] == 0,
            "Wrong base procedure",
        )
        require(
            Path(self.contract["engine_root"]).resolve() == self.session_root,
            "Monthly source root differs",
        )
        require(
            self.contract["source_audit"]["sha256"] == binding["session_audit_sha256"],
            "Monthly contract used another source audit",
        )
        self.verify(session_audit, binding["session_audit_sha256"])
        source_audit = self.json(session_audit)
        require(
            source_audit["status"] == "PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT"
            and Path(source_audit["binding"]["engine_root"]).resolve()
            == self.session_root,
            "Session source audit differs",
        )
        require(
            source_audit["binding"]["index_sha256"] == binding["index_sha256"],
            "Audits disagree on calendar/index",
        )
        require(
            (
                source_audit["binding"]["available_days"],
                source_audit["binding"]["missing_days"],
            )
            == (2619, 6),
            "Source coverage differs",
        )
        index_path = self.session_root / "index.parquet"
        self.verify(index_path, binding["index_sha256"])
        index = pd.read_parquet(
            index_path,
            columns=[
                "ticker",
                "date",
                "status",
                "close_i",
                "day_root",
                "actions_sha256",
                "labels_sha256",
            ],
        )
        index["date"] = index.date.astype(str)
        require(
            len(index) == 2625 and not index.duplicated(["ticker", "date"]).any(),
            "Incomplete source calendar",
        )
        require(
            index.ticker.isin(core.TICKERS).all()
            and index.close_i.isin([210, 390]).all()
            and index.status.isin(["COMPLETE", "MISSING_SOURCE"]).all(),
            "Invalid calendar fields",
        )
        require(
            int(index.date.str.startswith("2025").sum()) == 750
            and int(index.date.str.startswith("2026").sum()) == 369,
            "Evaluation calendar differs",
        )
        require(
            int((index.status == "MISSING_SOURCE").sum()) == 6,
            "Missing calendar rows changed",
        )
        self.index = index.set_index(["ticker", "date"], verify_integrity=True)
        self.fold_map = {
            (f.mode, f.evaluation_month.strftime("%Y%m")): f
            for f in schedule.build_schedule()
        }
        self.fit_cache = {}

    def verify(self, path, expected=None):
        path = Path(path).resolve()
        key = str(path)
        require(
            key in self.allowed,
            "Artifact absent from independent monthly audit: " + key,
        )
        if expected is not None:
            require(self.allowed[key] == expected, "Authority disagreement: " + key)
        digest = self.allowed[key]
        require(core.file_sha(path) == digest, "Changed audited artifact: " + key)
        self.used[key] = digest
        return digest

    def json(self, path):
        self.verify(path)
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        self.verify(path)
        return value

    def marker(self, name, required):
        path = self.root / (name + ".complete.json")
        record = self.json(path)
        require(
            record["status"] == "COMPLETE" and record["binding"] == self.binding,
            "Producer marker binding differs",
        )
        members = {}
        for relative, digest in record["files"].items():
            member = (self.root / relative).resolve()
            require(member.is_relative_to(self.root), "Marker escapes monthly root")
            members[str(member)] = digest
        for member in required:
            member = Path(member).resolve()
            require(str(member) in members, "Marker omits consumed artifact")
            self.verify(member, members[str(member)])
        return record

    def month_rows(self, month):
        require(month in self.completed_months, "Month not independently completed")
        name = "months/" + month
        marker = self.marker(name + "/predictions", [])
        require(
            marker["extra"]["labels_read"] is False,
            "Monthly prediction seal is not outcome-free",
        )
        self.marker(
            name + "/daily",
            [
                self.root / (name + "/daily.json"),
                self.root / (name + "/predictions.complete.json"),
            ],
        )
        return self.index.loc[
            self.index.index.get_level_values("date").str.startswith(month)
        ]

    def fit(self, procedure, month):
        require((procedure, month) in self.fold_map, "Unknown base fold")
        fold = self.fold_map[(procedure, month)]
        key = fold.fit_key
        if key in self.fit_cache:
            return self.fit_cache[key]
        name = "fits/" + key + "/inputs"
        path = self.root / (name + ".json")
        self.marker(name, [path])
        info = self.json(path)
        require(
            info["fit_key"] == key
            and info["train_start"] == fold.train_start.isoformat()
            and info["train_stop_exclusive"] == fold.train_stop.isoformat(),
            "Audited fit window differs from declared procedure",
        )
        require(info["config"] == self.contract["config"], "Fit configuration differs")
        model_name = "models/" + key
        model = self.root / (model_name + ".txt")
        started = self.root / (model_name + ".fit_started.json")
        self.marker(model_name, [model, started])
        fit_started = self.json(started)
        require(
            fit_started["binding"] == self.binding
            and fit_started["config"] == info["config"]
            and fit_started["shape"] == [info["rows"], 1954],
            "Fit signature differs",
        )
        require(
            set(info["scales"]) == set(core.TICKERS)
            and all(np.isfinite(v) and v > 0 for v in info["scales"].values()),
            "Invalid fold TRAIN scales",
        )
        stop = datetime.combine(
            fold.train_stop, datetime.min.time(), core.NY
        ).isoformat()
        result = dict(
            model_sha256=self.verify(model),
            fit_stop_at=stop,
            scales=info["scales"],
            fit_key=key,
        )
        self.fit_cache[key] = result
        return result

    def source_table(self, ticker, stamp, kind, columns):
        require(kind in ("actions", "labels"), "Source projection not allowed")
        row = self.index.loc[(ticker, stamp)]
        require(row.status == "COMPLETE", "Missing source must remain explicit")
        path = Path(row.day_root) / (kind + ".parquet")
        expected = row[kind + "_sha256"]
        # Source artifact authority is the independently audited index, not a
        # self-baseline and not a requirement to list all raw files twice.
        require(core.file_sha(path) == expected, "Source differs from audited index")
        values = pd.read_parquet(path, columns=columns)
        require(core.file_sha(path) == expected, "Source changed while reading")
        self.used[str(path.resolve())] = expected
        return values, expected

    def select_day(self, procedure, ticker, stamp, output):
        month = stamp[:6]
        self.month_rows(month)
        row = self.index.loc[(ticker, stamp)]
        if row.status == "MISSING_SOURCE":
            return dict(
                procedure=procedure,
                ticker=ticker,
                day=stamp,
                source_status="MISSING_SOURCE",
                selection_path=None,
            )
        fit = self.fit(procedure, month)
        name = (
            "predictions/" + month + "/" + fit["fit_key"] + "/" + ticker + "/" + stamp
        )
        path = self.root / (name + ".npz")
        self.marker(name, [path])
        self.marker("months/" + month + "/predictions", [path])
        with np.load(path, allow_pickle=False) as data:
            ids, states, scores = data["action_id"], data["state_i"], data["scores"]
            require(
                str(data["model_sha256"]) == fit["model_sha256"]
                and float(data["scale"]) == fit["scales"][ticker],
                "Prediction model/scale differs",
            )
        actions, _ = self.source_table(
            ticker, stamp, "actions", ["action_id", "state_i"]
        )
        require(
            np.array_equal(ids, actions.action_id)
            and np.array_equal(states, actions.state_i)
            and scores.shape == ids.shape
            and np.isfinite(scores).all(),
            "Prediction offers/clock differ",
        )
        selected = core.maximum_selection(
            procedure=procedure,
            ticker=ticker,
            day=stamp,
            close_i=int(row.close_i),
            fit_stop_at=fit["fit_stop_at"],
            model_sha256=fit["model_sha256"],
            prediction_sha256=self.verify(path),
            actions=[
                dict(action_id=int(i), state_i=int(s), score_usd=float(v))
                for i, s, v in zip(ids, states, scores)
            ],
        )
        destination = (
            Path(output) / procedure / "selections" / ticker / (stamp + ".json")
        )
        digest = publish_or_verify(destination, selected)
        return dict(
            procedure=procedure,
            ticker=ticker,
            day=stamp,
            source_status="COMPLETE",
            selection_path=str(destination.resolve()),
            selection_sha256=digest,
        )

    def realize_past_day(self, selected, target_month):
        require(
            selected["source_status"] == "COMPLETE"
            and selected["day"][:6] < target_month,
            "Only past available calibration days",
        )
        ticker, stamp = selected["ticker"], selected["day"]
        selection = core.load_seal(
            selected["selection_path"], selected["selection_sha256"]
        )
        available = core.session_close(selection) + timedelta(minutes=1)
        require(
            available < core.month_start(target_month),
            "Historical outcome not yet available",
        )
        row = self.index.loc[(ticker, stamp)]

        def load():
            data, _ = self.source_table(
                ticker, stamp, "labels", ["action_id", "status", "net_base"]
            )
            return data.to_dict("records")

        return core.realized_maxima(
            selected["selection_path"],
            selected["selection_sha256"],
            load,
            labels_sha256=row.labels_sha256,
            outcome_available_at=available.isoformat(),
            availability_semantics="DECLARED_NYSE_CLOSE_PLUS_ONE_MINUTE_NOT_OBSERVED_RECEIPT",
        )

    def recheck(self):
        for path, digest in self.used.items():
            require(
                core.file_sha(path) == digest, "Consumed source changed before closure"
            )


def prepare_correction(source, target_month, output):
    """Exclusive writer entry point; an unchanged implementation is mandatory."""
    core.month_start(target_month)
    require("202601" <= target_month <= "202606", "Only declared2026 development")
    root = Path(output).resolve()
    require(
        not root.is_relative_to(source.root)
        and not source.root.is_relative_to(root)
        and not root.is_relative_to(source.session_root)
        and not source.session_root.is_relative_to(root),
        "Separate calibration root required",
    )
    with output_lock(root):
        code = dependency_hashes()
        implementation_path = root / "implementation.json"
        if not implementation_path.exists():
            require(
                not any(p.name != ".lock" for p in root.iterdir()),
                "Outputs exist without implementation binding",
            )
        implementation = dict(
            dependencies=code,
            monthly_root=str(source.root),
            session_root=str(source.session_root),
            version=core.VERSION,
            calibrator_window="EXPANDING_FROM_202501",
            threshold=0,
            winner_selected=None,
        )
        implementation_sha = publish_or_verify(implementation_path, implementation)
        contract = dict(
            target_month=target_month,
            monthly_audit_sha256=source.authority_sha,
            implementation_sha256=implementation_sha,
        )
        contract_path = root / (target_month + ".run_contract.json")
        contract_sha = publish_or_verify(contract_path, contract)
        initial = {
            str(implementation_path): implementation_sha,
            str(contract_path): contract_sha,
        }
        return _prepare_correction_locked(source, target_month, root, code, initial)


def _prepare_correction_locked(source, target_month, output, code, initial):
    """Future runtime entry point; no target-month labels and no model fit.

    Requires every historical month from2025-01 through target-1, including
    explicit missing days. Retains the original3 procedures, without a winner.
    """
    require(dependency_hashes() == code, "Adapter changed before label access")
    boundary = core.month_start(target_month)
    require("202601" <= target_month <= "202606", "Only declared2026 development")
    root = Path(output).resolve()
    require(
        not root.is_relative_to(source.root)
        and not source.root.is_relative_to(root)
        and not root.is_relative_to(source.session_root)
        and not source.session_root.is_relative_to(root),
        "Separate calibration root required",
    )
    months = [
        f.evaluation_month.strftime("%Y%m")
        for f in schedule.build_schedule()
        if f.mode == "static" and f.evaluation_month < boundary.date()
    ]
    require(
        set(months + [target_month]).issubset(source.completed_months),
        "Prior/target audited month coverage incomplete",
    )
    common = source.fit("static", "202501")
    summaries = {}
    for procedure in core.PROCEDURES:
        records, inventory = [], []
        for month in months:
            rows = source.month_rows(month)
            require(len(rows) > 0, "Empty audited calendar month")
            for ticker, stamp in rows.index:
                chosen = source.select_day(procedure, ticker, stamp, root)
                inventory.append(
                    {k: v for k, v in chosen.items() if k != "selection_path"}
                )
                if chosen["source_status"] == "COMPLETE":
                    realized = source.realize_past_day(chosen, target_month)
                    record_path = (
                        root / procedure / "realized" / ticker / (stamp + ".json")
                    )
                    publish_or_verify(record_path, realized)
                    records.append(realized)
        calibration = core.estimate_offsets(
            records,
            procedure=procedure,
            target_month=target_month,
            common_scales=common["scales"],
            scales_train_stop_at=common["fit_stop_at"],
        )
        calibration_path = root / procedure / target_month / "calibration.json"
        calibration_sha = publish_or_verify(calibration_path, calibration)
        target_inventory = []
        for ticker, stamp in source.month_rows(target_month).index:
            chosen = source.select_day(procedure, ticker, stamp, root)
            if chosen["source_status"] == "COMPLETE":
                score_path = (
                    root
                    / procedure
                    / target_month
                    / "scores"
                    / ticker
                    / (stamp + ".json")
                )
                selected = core.load_seal(
                    chosen["selection_path"], chosen["selection_sha256"]
                )
                expected_rows = [
                    {
                        **r,
                        "corrected_score_usd": float(r["score_usd"])
                        + calibration["offsets_usd"][ticker],
                    }
                    for r in selected["selected"]
                ]
                expected_score = dict(
                    version=core.VERSION,
                    procedure=procedure,
                    ticker=ticker,
                    day=stamp,
                    calibration_sha256=calibration_sha,
                    selection_sha256=chosen["selection_sha256"],
                    rows=expected_rows,
                    threshold=0,
                    ranking_changed=False,
                    outcomes_read=False,
                )
                if score_path.exists():
                    score_sha = publish_or_verify(score_path, expected_score)
                else:
                    score_sha = core.apply_offsets_and_seal(
                        score_path,
                        calibration_path=calibration_path,
                        calibration_sha256=calibration_sha,
                        selection_path=chosen["selection_path"],
                        selection_sha256=chosen["selection_sha256"],
                    )
                    require(
                        score_sha == core.content_sha(expected_score),
                        "Score utility interface changed",
                    )
                chosen = {
                    **chosen,
                    "score_path": str(score_path),
                    "score_sha256": score_sha,
                }
            target_inventory.append(chosen)
        summaries[procedure] = dict(
            calibration_sha256=calibration_sha,
            history_calendar=inventory,
            target_calendar=target_inventory,
        )
    source.recheck()
    require(dependency_hashes() == code, "Adapter implementation changed")
    for path, digest in initial.items():
        core.load_seal(path, digest)
    inputs_path = root / (target_month + ".inputs.json")
    inputs_sha = publish_or_verify(
        inputs_path,
        dict(
            files=source.used,
            run_authorities=initial,
            dependencies=code,
            monthly_audit_sha256=source.authority_sha,
        ),
    )
    result = dict(
        status="COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS",
        target_month=target_month,
        monthly_audit_sha256=source.authority_sha,
        inputs_sha256=inputs_sha,
        dependencies=code,
        procedures=summaries,
        target_labels_read=False,
        base_models_refitted=False,
        winner_selected=None,
        development_seen=True,
    )
    publish_or_verify(root / (target_month + ".complete.json"), result)
    return result
