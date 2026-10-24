"""Archive producer closure only after externally pinned runtime completion/exit.

Does not parse economic reports, models, fit inputs, predictions or outcomes.
Fit metadata remains local and is hashed once after closure; its referenced
payloads and large matrix/target arrays are not read or rehashed by this tool.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

BASE = Path("D:/GexResearchArtifacts/level_oracle_20261018")
SCIENCE = BASE / "monthly_walk_forward_v1"
RUNTIME = BASE / "monthly_test_resource_overlay_20261024_01"
LAUNCHER = BASE / "monthly_test_launch_20261024_01"
HERE = Path(__file__).resolve().parent
OUT = HERE / "continuation_20261024/monthly_test_2026"
CONTRACT_SHA = "7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f"
LAUNCH_SHA = "dce4a9ab8ab3edd1da90ef82feb59e83a74a5a4f4f8fd230258abad274bc49f3"
VALIDATION_AUDIT_SHA = "ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc"
MAX_COPY_BYTES = 100_000_000
NEW_KEYS = tuple(sorted({f"train_{start}_2026{month:02d}01_exclusive"
                        for month in range(1, 7)
                        for start in ("20230101", f"2025{month:02d}01")}))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def absolute_hashes(mapping):
    result = {}
    for value, digest in mapping.items():
        path = Path(value)
        require(path.is_absolute(), "Absolute authority path required")
        key = str(path.resolve())
        require(key not in result or result[key] == digest, "Conflicting normalized authority")
        result[key] = digest
    return result


def run(runtime_sha, exit_receipt, exit_sha):
    require(not OUT.exists(), "Fresh archive root required")
    completion_path = RUNTIME / "completion.json"
    exit_receipt = exit_receipt.resolve()
    require(exit_receipt.is_relative_to(LAUNCHER.resolve()), "Exit receipt outside expected launcher root")
    require(sha(completion_path) == runtime_sha and sha(exit_receipt) == exit_sha,
            "External runtime completion/exit pins differ")
    require(sha(RUNTIME / "launch.json") == LAUNCH_SHA, "Runtime launch changed")
    completion, exited, launch = read(completion_path), read(exit_receipt), read(RUNTIME / "launch.json")
    require(completion.get("status") == "COMPLETE_MONTHLY_TEST_RESOURCE_OVERLAY"
            and completion.get("original_run_contract_sha256") == CONTRACT_SHA
            and completion.get("validation_audit_sha256") == VALIDATION_AUDIT_SHA
            and completion.get("scientific_inputs_changed") is False,
            "Producer runtime closure differs")
    require(exited.get("status") == "PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE"
            and exited.get("exit_code") == 0 and exited.get("pid") == launch.get("pid"),
            "Actual successful retained-handle exit required")
    require(datetime.fromisoformat(completion["completed_utc"].replace("Z", "+00:00"))
            <= datetime.fromisoformat(exited["observed_utc"].replace("Z", "+00:00")),
            "Runtime completion must precede observed exit")
    expected = {}
    for field in ("final_checkpoints", "preserved_checkpoints", "runtime_members"):
        for key, digest in absolute_hashes(completion[field]).items():
            require(key not in expected or expected[key] == digest, "Conflicting completion authority")
            expected[key] = digest
    require(expected.get(str((RUNTIME / "launch.json").resolve())) == LAUNCH_SHA,
            "Runtime closure omits launch")
    plans, references = [], []

    def plan(source, relative, authority=None):
        source = Path(source).resolve()
        require(source.is_file(), "Required compact source missing: " + str(source))
        require(source.stat().st_size < MAX_COPY_BYTES, "Compact source exceeds 100 MB; keep local and review")
        authority = authority or expected.get(str(source))
        require(authority is not None, "Compact source lacks an explicit authority: " + str(source))
        require(sha(source) == authority, "Compact source differs from authority")
        plans.append((source, Path(relative), authority))

    def seal(relative, required_members=()):
        path = SCIENCE / (relative + ".complete.json")
        require(str(path.resolve()) in expected, "Producer final checkpoint omitted seal")
        plan(path, "science/" + relative + ".complete.json")
        record = read(path)
        require(record.get("status") == "COMPLETE" and record.get("binding") == CONTRACT_SHA,
                "Wrong producer seal binding")
        members = {}
        for member, digest in record["files"].items():
            require(not Path(member).is_absolute(), "Absolute scientific seal member")
            target = (SCIENCE / member).resolve()
            require(target.is_relative_to(SCIENCE.resolve()), "Scientific seal escapes root")
            require(str(target) not in members, "Duplicate scientific seal member")
            members[str(target)] = digest
        for member in required_members:
            target = (SCIENCE / member).resolve()
            require(str(target) in members, "Required scientific seal member missing")
        return members

    plan(SCIENCE / "run_contract.json", "science/run_contract.json", CONTRACT_SHA)
    contract = read(SCIENCE / "run_contract.json")
    model_bytes = 0
    for key in NEW_KEYS:
        members = seal("models/" + key, [f"models/{key}.txt", f"models/{key}.fit_started.json"])
        for suffix in (".txt", ".fit_started.json"):
            path = SCIENCE / "models" / (key + suffix)
            require(expected.get(str(path.resolve())) == members[str(path.resolve())],
                    "Model final-checkpoint/seal hashes differ")
            plan(path, "science/models/" + path.name)
            if suffix == ".txt":
                model_bytes += path.stat().st_size
        for kind, suffix in (("inputs", ".json"), ("matrix", ".npy"), ("targets", ".npz")):
            relative = f"fits/{key}/{kind}"
            payload = SCIENCE / (relative + suffix)
            members = seal(relative, [relative + suffix])
            digest = members[str(payload.resolve())]
            require(payload.is_file(), "Local fit reference missing")
            if kind == "inputs":
                # Hash only the metadata file, without parsing or following its references.
                require(sha(payload) == digest, "Local fit metadata hash differs from producer seal")
            references.append(dict(fit_key=key, kind=kind, path=str(payload.resolve()),
                bytes_observed=payload.stat().st_size, sha256_from_producer_seal=digest,
                marker_archive_path="science/" + relative + ".complete.json",
                payload_rehashed_during_archive=kind == "inputs", payload_copied=False,
                referenced_payloads_read_or_rehashed=False, independently_audited_2026=False))
    for stamp in (f"2026{month:02d}" for month in range(1, 7)):
        for kind in ("predictions", "daily", "economics"):
            seal(f"months/{stamp}/{kind}")
    for name in ("reports/2026", "completion", "validation_freeze"):
        members = seal(name, [name + ".json"])
        # Report2026, freeze and scientific completion are copied, never parsed.
        plan(SCIENCE / (name + ".json"), "science/" + name + ".json",
             members[str((SCIENCE / (name + ".json")).resolve())])
    for name, digest in contract["dependencies"].items():
        plan(SCIENCE / "executed_code" / name, "code/scientific_producer/" + name, digest)
    runtime_files = sorted(p for p in RUNTIME.rglob("*") if p.is_file())
    for path in runtime_files:
        require("__pycache__" not in path.parts and path.suffix != ".partial", "Unexpected runtime transient")
        plan(path, Path("runtime/overlay") / path.relative_to(RUNTIME),
             runtime_sha if path == completion_path else None)
    launcher_files = sorted(p for p in LAUNCHER.rglob("*") if p.is_file())
    for path in launcher_files:
        require("__pycache__" not in path.parts and path.suffix != ".partial", "Unexpected launcher transient")
        plan(path, Path("runtime/launcher") / path.relative_to(LAUNCHER),
             exit_sha if path == exit_receipt else sha(path))
    plan(Path(__file__), "archive_monthly_test_producer_20261024.py", sha(__file__))
    require(len({str(relative) for _, relative, _ in plans}) == len(plans), "Duplicate archive target")
    OUT.mkdir(parents=True)
    copied = []
    for source, relative, digest in plans:
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        require(not target.exists(), "Archive target already exists")
        shutil.copyfile(source, target)
        require(sha(source) == digest == sha(target), "Source/copy changed during archive")
        copied.append(dict(original_path=str(source), archive_path=relative.as_posix(),
                           bytes=source.stat().st_size, sha256=digest,
                           source_and_copy_rehashed=True))
    write(OUT / "LOCAL_REFERENCES.json", dict(status="LOCAL_PRODUCER_SEAL_REFERENCES_NOT_AUDITED_2026",
        files=references, arrays=sum(r["kind"] != "inputs" for r in references),
        array_bytes=sum(r["bytes_observed"] for r in references if r["kind"] != "inputs"),
        metadata_files=sum(r["kind"] == "inputs" for r in references),
        metadata_bytes=sum(r["bytes_observed"] for r in references if r["kind"] == "inputs"),
        verification_scope="Input JSON metadata files hashed once after closure without parsing/following references. Matrix/target producer-seal SHA plus current existence/size only; no array payload read or rehash.",
        raw_features_scores_labels="Remain local; parent scientific checkpoints and fit metadata preserve their paths/hashes.",
        large_payload_copies=0))
    for record in copied:
        require(sha(record["original_path"]) == record["sha256"]
                == sha(OUT / record["archive_path"]), "Compact evidence changed at final archive check")
    manifest = dict(status="COMPACT_PRODUCER_2026_CLOSURE_NOT_INDEPENDENTLY_AUDITED",
        archived_utc=datetime.now(timezone.utc).isoformat(), new_models=12,
        model_payload_bytes=model_bytes, copied_files=len(copied),
        copied_bytes=sum(r["bytes"] for r in copied), copies=copied,
        local_references_sha256=sha(OUT / "LOCAL_REFERENCES.json"),
        runtime_completion_path=str(completion_path.resolve()), runtime_completion_sha256=runtime_sha,
        exit_receipt_path=str(exit_receipt), exit_receipt_sha256=exit_sha,
        actual_exit_code=exited["exit_code"], process_pid=exited["pid"],
        original_run_contract_sha256=CONTRACT_SHA, prior_validation_audit_sha256=VALIDATION_AUDIT_SHA,
        metrics_parsed_by_archive=False, economic_report_copied_without_parsing=True,
        independently_audited_2026=False, new_fit_or_evaluation=False,
        promotion_approved=False,
        limitation="Producer runtime completion is not independent H1 economic/causal audit PASS. No metrics interpreted.")
    write(OUT / "MANIFEST.json", manifest)
    print(json.dumps(dict(status=manifest["status"], files=len(copied), bytes=manifest["copied_bytes"],
                         new_models=12, references=len(references), manifest_sha256=sha(OUT / "MANIFEST.json")), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-completion-sha256", required=True)
    parser.add_argument("--exit-receipt", type=Path, required=True)
    parser.add_argument("--exit-sha256", required=True)
    args = parser.parse_args()
    run(args.runtime_completion_sha256, args.exit_receipt, args.exit_sha256)


if __name__ == "__main__":
    main()
