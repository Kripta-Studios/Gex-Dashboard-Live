"""OOF V2R1: exact transitive source admission; scientific producers stay frozen."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import traceback

import monthly_oof_calibration_adapter as adapter
import evaluate_oof_calibrated_policy as evaluator

HERE = Path(__file__).resolve().parent
MONTHS = tuple(f"2026{i:02d}" for i in range(1, 7))
HISTORY = tuple(f"2025{i:02d}" for i in range(1, 13)) + MONTHS
MODES = ("static", "expanding", "rolling12")
MIN_FREE = 2_000_000_000
GLOBAL_LOCK = Path(
    "D:/GexResearchArtifacts/level_oracle_20261018/oof_pipeline_runtime.lock"
)
PINS = {
    "monthly_oof_calibration_adapter.py": "7b80cff43e3887a92e0f89be6daa863a670ccd72d22a0f4aeabd032a39479364",
    "oof_maximum_calibration.py": "19e922dd65855c4cd7e2ec9d482d477a328245bcf642eeeb7771985f247e20b5",
    "evaluate_oof_calibrated_policy.py": "eeaad06f5b862a3153f29e7eab579b19a35e182ab506cf1f59e65631e187e716",
    "audit_oof_calibrated_policy.py": "e7481fbe944a9ffadcf637e7a4b69cd8d636cdf50ae295426191db9d76b5d44b",
}
EXTRA_CODE = (
    "run_oof_calibrated_pipeline_v2r1.py",
    "test_run_oof_calibrated_pipeline_v2r1.py",
    "OOF_TRANSITIVE_SOURCE_V2R1_IMPLEMENTATION_CONTRACT_20261024.md",
    "OOF_TRANSITIVE_SOURCE_V2_DESIGN_20261024.md",
    "OOF_TRANSITIVE_SOURCE_FAILURE_DIAGNOSIS_20261024.md",
    "audit_oof_calibrated_policy.py",
    "test_audit_oof_calibrated_policy.py",
    "OOF_ECONOMIC_AUDITOR_SPEC_20261023.md",
    "OOF_ECONOMIC_AUDITOR_DESIGN_20261023.md",
    "OOF_ECONOMIC_AUDITOR_IMPLEMENTATION_REVIEW_20261023.md",
)


def require(ok, message):
    if not bool(ok):
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value):
    require(
        isinstance(value, str)
        and len(value) == 64
        and set(value) <= set("0123456789abcdef"),
        "Invalid SHA256",
    )
    return value


def declared_path(value):
    """Lexical checks only: never stat the full monthly authority inventory."""
    require(
        isinstance(value, str) and Path(value).is_absolute()
        and ".." not in Path(value).parts, "Bounded absolute path required"
    )
    path = Path(os.path.normpath(value))
    require(path != Path(path.anchor), "Volume root forbidden")
    return path


def absolute(value):
    path = declared_path(value)
    for part in (path, *path.parents):
        require(not part.is_symlink() and not part.is_junction(), "Linked path or ancestor")
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        require(not getattr(info, "st_file_attributes", 0) & 0x400, "Reparse point")
    resolved = path.resolve()
    require(os.path.normcase(str(path)) == os.path.normcase(str(resolved)), "Redirected path")
    return resolved


def path_key(path):
    return os.path.normcase(str(declared_path(str(path))))


def inspect_consumed_identity(path, identities=None):
    """Only indexed sidecars or consumed files; missing fails at actual read."""
    path = absolute(str(path))
    try:
        info = path.stat()
    except FileNotFoundError:
        return path
    require(info.st_nlink == 1, "Hardlinked input")
    require(stat.S_ISREG(info.st_mode), "Input is not a regular file")
    if identities is not None:
        identity = f"{info.st_dev}:{info.st_ino}"
        require(info.st_ino != 0, "Unavailable physical file identity")
        require(identity not in identities or identities[identity] == str(path),
                "Physical input alias")
        identities[identity] = str(path)
    return path


def transitive_admission(monthly, index_path, index_sha, session):
    """Audited JSON metadata union indexed actions/labels; no sidecar values."""
    import pandas as pd

    members, identities = {}, {}

    def add(name, expected, origin):
        path = str(declared_path(name))
        key = path_key(path)
        expected = digest(expected)
        if key in members:
            require(members[key]["declaration"] == name, "Aliased authority path")
            require(members[key]["sha256"] == expected, "Conflicting authority SHA")
            members[key]["origins"].add(origin)
        else:
            members[key] = dict(path=path, declaration=name, sha256=expected, origins={origin})
        return key

    groups = monthly["verified_files"]
    require(isinstance(groups, dict), "Grouped monthly authority required")
    for group, files in groups.items():
        require(isinstance(files, dict), "Monthly authority group must be a map")
        for name, expected in files.items():
            add(name, expected, "monthly:" + group)
    require(sha(index_path) == digest(index_sha), "Index pin differs before metadata")
    index = pd.read_parquet(index_path, columns=[
        "ticker", "date", "status", "close_i", "day_root", "actions_sha256", "labels_sha256",
    ])
    require(sha(index_path) == index_sha, "Index changed during metadata read")
    index["date"] = index["date"].astype(str)
    require(index.date.str.fullmatch(r"[0-9]{8}").all(), "Invalid index date format")
    pd.to_datetime(index.date, format="%Y%m%d", errors="raise")
    require(not index.duplicated(["ticker", "date"]).any(), "Duplicate index identity")
    require(index.ticker.isin(("QQQ", "SPXW", "SPY")).all()
            and index.close_i.isin((210, 390)).all()
            and index.status.isin(("COMPLETE", "MISSING_SOURCE")).all(), "Invalid index metadata")
    binding = session["binding"]
    if "available_days" in binding:
        require(int((index.status == "COMPLETE").sum()) == binding["available_days"],
                "Index available coverage differs")
    if "missing_days" in binding:
        require(int((index.status == "MISSING_SOURCE").sum()) == binding["missing_days"],
                "Index missing coverage differs")
    indexed = set()
    scoped = index.loc[index.date.str[:6].isin(HISTORY)]
    require(set(scoped.date.str[:6]) == set(HISTORY), "Indexed month coverage differs")
    for row in scoped.itertuples(index=False):
        if row.status == "MISSING_SOURCE":
            require(all(pd.isna(value) for value in
                        (row.actions_sha256, row.labels_sha256)),
                    "Missing-source sidecar must remain null")
            continue
        for kind in ("actions", "labels"):
            path = declared_path(row.day_root) / (kind + ".parquet")
            inspect_consumed_identity(path, identities)
            indexed.add(add(str(path), getattr(row, kind + "_sha256"),
                            f"index:{row.ticker}:{row.date}:{kind}"))
    for member in members.values():
        member["origins"] = sorted(member["origins"])
    result = dict(members=members, indexed_sidecars=sorted(indexed), indexed_identities=identities)
    result["map_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result


def protect_transitive_outputs(outputs, admission):
    # Declared paths only: no filesystem scan/stat of A's historical payloads.
    parents = {declared_path(value["path"]).parent for value in admission["members"].values()}
    require(all(disjoint(output, parent) for output in outputs for parent in parents),
            "Output overlaps transitive source directory")


def disjoint(left, right):
    return not left.is_relative_to(right) and not right.is_relative_to(left)


def load(path, expected):
    require(sha(path) == digest(expected), "Changed sealed file: " + str(path))
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    require(sha(path) == expected, "Changed while reading: " + str(path))
    return value


def publish(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".partial")
    require(not path.exists() and not temporary.exists(), "Preserve existing artifact")
    path.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return sha(path)


def dependencies():
    names = set(evaluator.dependencies()) | set(EXTRA_CODE)
    return {name: sha(HERE / name) for name in sorted(names)}


def resource_gate():
    import ctypes
    import psutil

    ram = psutil.virtual_memory().available
    if os.name == "nt":

        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (n, ctypes.c_ulonglong)
                for n in (
                    "total_phys",
                    "avail_phys",
                    "total_page",
                    "avail_page",
                    "total_virtual",
                    "avail_virtual",
                    "avail_extended",
                )
            ]

        info = Memory()
        info.length = ctypes.sizeof(Memory)
        require(
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info)),
            "Memory status failed",
        )
        commit = info.avail_page
    else:
        commit = ram + psutil.swap_memory().free
    require(min(ram, commit) >= MIN_FREE, "2GB RAM/commit resource gate")
    return dict(available_ram_bytes=ram, free_commit_bytes=commit)


@contextmanager
def sequence_lock():
    """Same fixed lock for every request/root, held for the whole pipeline."""
    GLOBAL_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with GLOBAL_LOCK.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def rss_bytes():
    import psutil

    return psutil.Process().memory_info().rss


class Request:
    def __init__(self, path, expected):
        self.path, self.sha = absolute(str(path)), digest(expected)
        value = self.value = load(self.path, self.sha)
        require(
            value["version"] == "OOF_PIPELINE_RUNTIME_REQUEST_V2R1"
            and value["status"] == "REVIEWED_OOF_PIPELINE_RUNTIME_REQUEST"
            and value["runtime_authorized"] is True,
            "Reviewed runtime request required",
        )
        require(value["months"] == list(MONTHS), "Fixed six months required")
        require(
            absolute(value["coordination_lock"]) == GLOBAL_LOCK.resolve(),
            "Fixed global lock required",
        )
        require(value["code"] == dependencies(), "Reviewed code differs")
        require(
            all(value["code"].get(k) == v for k, v in PINS.items()),
            "Frozen producer/auditor changed",
        )
        self.monthly = absolute(value["monthly_root"])
        self.session = absolute(value["session_root"])
        self.pipeline = absolute(value["pipeline_root"])
        self.correction = absolute(value["correction_root"])
        self.evaluations = {
            m: absolute(p) for m, p in value["evaluation_roots"].items()
        }
        require(set(self.evaluations) == set(MONTHS), "Six replay roots required")
        self.authorities = {}
        for kind in ("monthly_audit", "session_audit"):
            item = value[kind]
            self.authorities[kind] = (absolute(item["path"]), digest(item["sha256"]))
        self.outputs = [self.pipeline, self.correction, *self.evaluations.values()]
        protected = [
            HERE,
            self.monthly,
            self.session,
            self.path,
            GLOBAL_LOCK.resolve(),
            *[p for p, _ in self.authorities.values()],
        ]
        require(
            all(
                disjoint(a, b)
                for i, a in enumerate(self.outputs)
                for b in self.outputs[i + 1 :]
            ),
            "Overlapping output roots",
        )
        require(
            all(disjoint(a, b) for a in self.outputs for b in protected),
            "Output overlaps protected input",
        )
        self.recheck()

    def recheck(self):
        require(load(self.path, self.sha) == self.value, "Request changed")
        require(self.value["code"] == dependencies(), "Runtime implementation changed")
        monthly = load(*self.authorities["monthly_audit"])
        session = load(*self.authorities["session_audit"])
        require(monthly["status"] == adapter.STATUS, "Monthly output audit required")
        binding = monthly["binding"]
        require(
            binding["completed_months"] == list(HISTORY),
            "Composite monthly coverage required",
        )
        require(
            absolute(binding["monthly_root"]) == self.monthly
            and absolute(binding["session_root"]) == self.session,
            "Monthly authority roots differ",
        )
        require(
            binding["session_audit_sha256"] == self.authorities["session_audit"][1],
            "Session authority binding differs",
        )
        require(
            session["status"] == "PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT"
            and absolute(session["binding"]["engine_root"]) == self.session,
            "Session authority differs",
        )
        require(
            binding["index_sha256"] == session["binding"]["index_sha256"],
            "Index authority differs",
        )
        for path, expected in (
            (self.monthly / "run_contract.json", binding["run_contract_sha256"]),
            (self.session / "index.parquet", binding["index_sha256"]),
        ):
            require(sha(path) == digest(expected), "Contract/index changed")
        admission = transitive_admission(
            monthly, self.session / "index.parquet", binding["index_sha256"], session,
        )
        if hasattr(self, "admission"):
            require(admission == self.admission, "Transitive admission changed")
        self.admission = admission
        if not hasattr(self, "consumed_identities"):
            self.consumed_identities = dict(admission["indexed_identities"])
        protect_transitive_outputs(self.outputs, admission)

    def source(self):
        return adapter.MonthlyInputs(
            self.monthly,
            self.authorities["monthly_audit"][0],
            self.authorities["monthly_audit"][1],
            self.session,
            self.authorities["session_audit"][0],
        )

    def allowed_file(self, path, expected):
        declaration = str(path)
        p = inspect_consumed_identity(path, self.consumed_identities)
        roots = [
            HERE,
            self.monthly,
            self.session,
            self.correction,
            *self.evaluations.values(),
        ]
        exact = {self.path, *[p for p, _ in self.authorities.values()]}
        if p not in exact and not any(p.is_relative_to(root) for root in roots):
            key = path_key(p)
            require(key in self.admission["members"], "Unadmitted external input")
            member = self.admission["members"][key]
            require(member["path"] == str(p) == declaration, "Aliased consumed external input")
            require(member["sha256"] == digest(expected), "Consumed SHA differs from authority")
            if p.name in ("actions.parquet", "labels.parquet"):
                require(key in self.admission["indexed_sidecars"], "External sidecar outside scoped index")
        return p


def verify_map(request, mapping):
    require(isinstance(mapping, dict), "File map required")
    seen = {}
    for name, expected in mapping.items():
        path = request.allowed_file(name, expected)
        key = str(path)
        require(key not in seen, "Aliased duplicate path")
        seen[key] = digest(expected)
        require(sha(path) == expected, "Changed mapped input: " + key)
    return seen


def inventory(request):
    result = {}
    for root in (request.correction, *request.evaluations.values()):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            require(
                not path.is_symlink() and path.resolve().is_relative_to(root),
                "Linked output forbidden",
            )
            if path.is_file():
                if path.name == ".lock" and path.parent == root:
                    continue
                require(not path.name.endswith(".partial"), "Partial output preserved")
                result[str(path.resolve())] = sha(path)
    return result


def member(mapping, path):
    key = str(Path(path).resolve())
    require(
        key in mapping and sha(path) == mapping[key], "Consumed member missing: " + key
    )
    return mapping[key]


def correction_closure(request, month, expected):
    root = request.correction
    complete_path = root / (month + ".complete.json")
    complete = load(complete_path, expected)
    code = adapter.dependency_hashes()
    require(
        complete["status"] == "COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS"
        and complete["target_month"] == month
        and complete["monthly_audit_sha256"] == request.authorities["monthly_audit"][1]
        and complete["dependencies"] == code
        and complete["target_labels_read"] is False
        and complete["base_models_refitted"] is False
        and complete["winner_selected"] is None,
        "Invalid correction closure",
    )
    require(set(complete["procedures"]) == set(MODES), "Correction procedures differ")
    inputs_path = root / (month + ".inputs.json")
    inputs = load(inputs_path, complete["inputs_sha256"])
    verify_map(request, inputs["files"])
    authority = verify_map(request, inputs["run_authorities"])
    require(
        inputs["dependencies"] == code
        and inputs["monthly_audit_sha256"] == request.authorities["monthly_audit"][1],
        "Correction input binding",
    )
    impl_path, run_path = (
        root / "implementation.json",
        root / (month + ".run_contract.json"),
    )
    impl = load(impl_path, member(authority, impl_path))
    contract = load(run_path, member(authority, run_path))
    require(
        impl
        == dict(
            dependencies=code,
            monthly_root=str(request.monthly),
            session_root=str(request.session),
            version="PREQUENTIAL_MAXIMUM_OFFSET_V1",
            calibrator_window="EXPANDING_FROM_202501",
            threshold=0,
            winner_selected=None,
        ),
        "Correction implementation differs",
    )
    require(
        contract
        == dict(
            target_month=month,
            monthly_audit_sha256=request.authorities["monthly_audit"][1],
            implementation_sha256=sha(impl_path),
        ),
        "Correction contract differs",
    )
    outputs = {
        str(p.resolve()) for p in (complete_path, inputs_path, impl_path, run_path)
    }
    for mode, part in complete["procedures"].items():
        calibration = root / mode / month / "calibration.json"
        calibrated = load(calibration, part["calibration_sha256"])
        require(
            calibrated["procedure"] == mode and calibrated["target_month"] == month,
            "Calibration identity differs",
        )
        training = {(r["ticker"], r["day"]): r for r in calibrated["training_records"]}
        require(
            len(training) == len(calibrated["training_records"]),
            "Duplicate training record",
        )
        expected_history = {
            (r["ticker"], r["day"])
            for r in part["history_calendar"]
            if r["source_status"] == "COMPLETE"
        }
        require(set(training) == expected_history, "Training record calendar differs")
        outputs.add(str(calibration.resolve()))
        for group in ("history_calendar", "target_calendar"):
            for row in part[group]:
                require(
                    row["procedure"] == mode
                    and row["ticker"] in ("SPXW", "SPY", "QQQ")
                    and len(row["day"]) == 8
                    and row["day"].isdigit(),
                    "Calendar identity",
                )
                require(
                    row["source_status"] in ("COMPLETE", "MISSING_SOURCE"),
                    "Source status",
                )
                if row["source_status"] != "COMPLETE":
                    continue
                selection = (
                    root / mode / "selections" / row["ticker"] / (row["day"] + ".json")
                )
                selected = load(selection, row["selection_sha256"])
                require(
                    selected["procedure"] == mode
                    and selected["ticker"] == row["ticker"]
                    and selected["day"] == row["day"],
                    "Selection identity differs",
                )
                outputs.add(str(selection.resolve()))
                if group == "history_calendar":
                    realized = (
                        root
                        / mode
                        / "realized"
                        / row["ticker"]
                        / (row["day"] + ".json")
                    )
                    bound = training[row["ticker"], row["day"]]
                    record = load(realized, bound["record_sha256"])
                    require(
                        record["selection"] == selected
                        and record["selection_sha256"]
                        == bound["selection_sha256"]
                        == row["selection_sha256"]
                        and record["labels_sha256"] == bound["labels_sha256"]
                        and record["outcome_available_at"]
                        == bound["outcome_available_at"]
                        and selected["model_sha256"] == bound["model_sha256"]
                        and selected["prediction_sha256"] == bound["prediction_sha256"],
                        "Realized/calibration binding differs",
                    )
                    outputs.add(str(realized.resolve()))
                else:
                    score = (
                        root
                        / mode
                        / month
                        / "scores"
                        / row["ticker"]
                        / (row["day"] + ".json")
                    )
                    require(
                        absolute(row["score_path"]) == score.resolve()
                        and absolute(row["selection_path"]) == selection.resolve(),
                        "Target output path",
                    )
                    load(score, row["score_sha256"])
                    outputs.add(str(score.resolve()))
    return outputs


def replay_closure(request, month, expected, correction_sha):
    root = request.evaluations[month]
    complete = load(root / "completion.json", expected)
    require(
        complete["status"] == "COMPLETE_FIXED_OOF_POLICY_MONTH"
        and complete["target_month"] == month
        and complete["winner_selected"] is None
        and complete["dependencies"] == evaluator.dependencies(),
        "Invalid replay closure",
    )
    files = verify_map(request, complete["files"])
    verify_map(request, complete["monthly_files"])
    for path in (request.correction / (month + ".complete.json"),):
        require(
            member(files, path) == correction_sha, "Replay/correction closure mismatch"
        )
    contract_path = root / "run_contract.json"
    contract = load(contract_path, member(files, contract_path))
    require(
        contract
        == dict(
            version="OOF_POLICY_REPLAY_V1",
            dependencies=evaluator.dependencies(),
            monthly_audit_sha256=request.authorities["monthly_audit"][1],
            correction_completion_sha256=correction_sha,
            target_month=month,
            threshold=0,
            winner_selected=None,
        ),
        "Replay contract differs",
    )
    for name in ("summary.json", "all_scores_and_controls.json"):
        member(files, root / name)
    outputs = {str((root / "completion.json").resolve())}
    outputs.update(p for p in files if Path(p).is_relative_to(root))
    return outputs


def phases():
    return [(month, stage) for month in MONTHS for stage in ("correction", "replay")]


def start_path(request, index):
    return request.pipeline / "starts" / f"{index:02d}.json"


def receipt_path(request, index):
    return request.pipeline / "receipts" / f"{index:02d}.json"


def validate_control_tree(request, count, failure_paths):
    allowed = {request.pipeline / name for name in ("request.json", "contract.json")}
    allowed |= {start_path(request, i) for i in range(count)}
    allowed |= {receipt_path(request, i) for i in range(count)}
    allowed |= set(failure_paths)
    if (request.pipeline / "completion.json").exists():
        allowed.add(request.pipeline / "completion.json")
    actual = set()
    for p in request.pipeline.rglob("*"):
        require(
            not p.is_symlink() and p.resolve().is_relative_to(request.pipeline),
            "Linked pipeline path",
        )
        if p.is_file():
            actual.add(p)
    require(actual == allowed, "Partial stage or orphan pipeline artifact preserved")


def completed_prefix(request):
    """Revalidate closure chain; cumulative maps allow only legitimate later additions."""
    prior, current, closures, count = None, {}, {}, 0
    for i, (month, stage) in enumerate(phases()):
        path = receipt_path(request, i)
        if not path.exists():
            break
        receipt = json.loads(path.read_text(encoding="utf-8"))
        require(
            receipt["status"] == "COMPLETE_OOF_PIPELINE_PHASE"
            and receipt["request_sha256"] == request.sha
            and receipt["phase"] == [month, stage]
            and receipt["previous_receipt_sha256"] == prior,
            "Receipt authority chain differs",
        )
        begun = load(start_path(request, i), receipt["start_sha256"])
        require(
            begun["request_sha256"] == request.sha
            and begun["phase"] == [month, stage]
            and begun["previous_receipt_sha256"] == prior,
            "Phase start binding differs",
        )
        expected = receipt["completion_sha256"]
        if stage == "correction":
            generated = correction_closure(request, month, expected)
            closures[month] = dict(correction_completion_sha256=expected)
        else:
            generated = replay_closure(
                request,
                month,
                expected,
                closures[month]["correction_completion_sha256"],
            )
            closures[month]["evaluation_completion_sha256"] = expected
        observed = receipt["output_inventory"]
        require(
            set(observed) == set(current) | generated,
            "Receipt output membership differs",
        )
        require(
            all(observed[p] == h for p, h in current.items()), "Prior outputs changed"
        )
        verify_map(request, observed)
        current, prior, count = observed, sha(path), i + 1
    require(
        inventory(request) == current,
        "Output orphan/mutation or partial stage preserved",
    )
    require(request.correction.exists() == (count > 0), "Orphan correction root")
    for month, root in request.evaluations.items():
        require(
            root.exists()
            == ("evaluation_completion_sha256" in closures.get(month, {})),
            "Orphan replay root",
        )
    failures = list((request.pipeline / "failures").glob("*.json"))
    for failure in failures:
        record = json.loads(failure.read_text(encoding="utf-8"))
        require(
            record["status"] == "FAILED_OR_INTERRUPTED_PRESERVED"
            and record["request_sha256"] == request.sha,
            "Foreign failure artifact",
        )
    validate_control_tree(request, count, failures)
    completion = request.pipeline / "completion.json"
    if completion.exists():
        require(count == len(phases()), "Premature pipeline completion preserved")
        expected = pipeline_result(request, prior, closures)
        load(completion, hashlib.sha256(canonical(expected)).hexdigest())
    return count, current, prior, closures


def pipeline_result(request, previous, closures):
    return dict(
        status="PIPELINE_COMPLETE_PENDING_INDEPENDENT_AUDIT",
        request_sha256=request.sha,
        last_receipt_sha256=previous,
        months=closures,
        winner_selected=None,
        technical_ready=False,
        promotion_approved=False,
        auditor_executed=False,
    )


def pipeline(request_path, expected_sha, *, resume=False):
    admission_resources = resource_gate()
    request = Request(request_path, expected_sha)
    with sequence_lock():
        request.recheck()
        if resume:
            require(request.pipeline.is_dir(), "No pipeline to resume")
            stored = load(request.pipeline / "request.json", request.sha)
            require(stored == request.value, "Stored request differs")
            contract = json.loads(
                (request.pipeline / "contract.json").read_text(encoding="utf-8")
            )
            require(
                contract
                == dict(
                    version="OOF_PIPELINE_V2R1",
                    request_sha256=request.sha,
                    code=request.value["code"],
                    correction_layout="SHARED_CUMULATIVE",
                    source_admission_sha256=request.admission["map_sha256"],
                ),
                "Pipeline contract differs",
            )
        else:
            require(
                all(not p.exists() for p in request.outputs),
                "Fresh output roots required",
            )
            request.pipeline.mkdir(parents=True)
            # Preserve exact request bytes, including whitespace, for external SHA.
            with (request.pipeline / "request.json").open("xb") as stream:
                stream.write(request.path.read_bytes())
                stream.flush()
                os.fsync(stream.fileno())
            publish(
                request.pipeline / "contract.json",
                dict(
                    version="OOF_PIPELINE_V2R1",
                    request_sha256=request.sha,
                    code=request.value["code"],
                    correction_layout="SHARED_CUMULATIVE",
                    source_admission_sha256=request.admission["map_sha256"],
                ),
            )
        try:
            count, current, previous, closures = completed_prefix(request)
            for i, (month, stage) in enumerate(phases()[count:], start=count):
                resources = resource_gate()
                request.recheck()
                require(inventory(request) == current, "Output changed between phases")
                rss_start = rss_bytes()
                began = time.monotonic()
                started = publish(
                    start_path(request, i),
                    dict(
                        request_sha256=request.sha,
                        phase=[month, stage],
                        previous_receipt_sha256=previous,
                        resources=resources,
                        rss_start_bytes=rss_start,
                        started_at_utc=datetime.now(timezone.utc).isoformat(),
                    ),
                )
                source = request.source()
                if stage == "correction":
                    adapter.prepare_correction(source, month, request.correction)
                    closed = sha(request.correction / (month + ".complete.json"))
                    generated = correction_closure(request, month, closed)
                    closures[month] = dict(correction_completion_sha256=closed)
                else:
                    correction_sha = closures[month]["correction_completion_sha256"]
                    # The correction receipt is the authority, never an arbitrary current hash.
                    correction_closure(request, month, correction_sha)
                    evaluator.evaluate_month(
                        source,
                        request.correction,
                        month,
                        request.evaluations[month],
                        correction_completion_sha256=correction_sha,
                    )
                    closed = sha(request.evaluations[month] / "completion.json")
                    generated = replay_closure(request, month, closed, correction_sha)
                    closures[month]["evaluation_completion_sha256"] = closed
                source.recheck()
                request.recheck()
                observed = inventory(request)
                require(
                    set(observed) == set(current) | generated,
                    "Unexpected phase outputs",
                )
                require(
                    all(observed[p] == h for p, h in current.items()),
                    "Phase changed earlier output",
                )
                receipt = dict(
                    status="COMPLETE_OOF_PIPELINE_PHASE",
                    request_sha256=request.sha,
                    phase=[month, stage],
                    previous_receipt_sha256=previous,
                    start_sha256=started,
                    completion_sha256=closed,
                    output_inventory=observed,
                    elapsed_seconds=time.monotonic() - began,
                    new_output_bytes=sum(
                        Path(p).stat().st_size for p in set(observed) - set(current)
                    ),
                    cumulative_output_bytes=sum(
                        Path(p).stat().st_size for p in observed
                    ),
                    rss_start_bytes=rss_start,
                    rss_end_bytes=rss_bytes(),
                    rss_peak_measured=False,
                    winner_selected=None,
                    independent_audit_pending=True,
                )
                previous = publish(receipt_path(request, i), receipt)
                current = observed
                print(
                    json.dumps(dict(status=receipt["status"], phase=receipt["phase"])),
                    flush=True,
                )
            result = pipeline_result(request, previous, closures)
            request.recheck()
            completed_prefix(request)
            path = request.pipeline / "completion.json"
            if path.exists():
                require(
                    load(path, hashlib.sha256(canonical(result)).hexdigest()) == result,
                    "Pipeline closure differs",
                )
            else:
                publish(path, result)
            return result
        except BaseException as exc:
            failure = request.pipeline / "failures" / (str(time.time_ns()) + ".json")
            publish(
                failure,
                dict(
                    status="FAILED_OR_INTERRUPTED_PRESERVED",
                    request_sha256=request.sha,
                    error=repr(exc),
                    traceback=traceback.format_exc(),
                    admission_resources=admission_resources,
                    success=False,
                ),
            )
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    result = pipeline(args.request, args.request_sha256, resume=args.resume)
    print(json.dumps(dict(status=result["status"])), flush=True)


if __name__ == "__main__":
    main()
