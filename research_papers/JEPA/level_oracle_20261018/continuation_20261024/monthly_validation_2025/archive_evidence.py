"""Copy compact audited 2025 evidence; never parse or rehash large fit arrays."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil

BASE = Path("D:/GexResearchArtifacts/level_oracle_20261018")
REPO = Path(r"C:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live")
HERE = REPO / "research_papers/JEPA/level_oracle_20261018"
SCIENCE = BASE / "monthly_walk_forward_v1"
VALIDATION = BASE / "monthly_resource_overlay_resume_20261023_01"
MONITOR = BASE / "monthly_resume_20261023_01_logs"
RUNTIME = BASE / "monthly_validation_audit_launch_20261024_02"
AUDIT = BASE / "monthly_walk_forward_validation_audit_20261024_02/audit.json"
OUT = HERE / "continuation_20261024/monthly_validation_2025"
AUDIT_SHA = "ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc"
REPORT_SHA = "d7e5215889a796af5bc46e52f9754f60d36c82d4556c9085695ad3dcf1171d4e"
CONTRACT_SHA = "7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    require(not OUT.exists(), "Use a new archive root; never overwrite evidence")
    require(sha(AUDIT) == AUDIT_SHA, "Audited authority changed")
    require(sha(SCIENCE / "reports/2025.json") == REPORT_SHA, "Audited report changed")
    audit = read(AUDIT)
    require(audit["status"] == "PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES",
            "Expected complete conditional audit")
    require(audit["audited"]["months"] == 12 and audit["audited"]["unique_fit_windows"] == 24
            and audit["audited"]["calendar_ticker_days"] == 750, "Wrong audit scope")
    expected = {}
    for group in audit["verified_files"].values():
        for name, digest in group.items():
            require(expected.get(name, digest) == digest, "Conflicting audited hash")
            expected[name] = digest
    for name, digest in read(RUNTIME / "admission.json")["files"].items():
        require(expected.get(name, digest) == digest, "Conflicting admitted hash")
        expected[name] = digest
    contract = read(SCIENCE / "run_contract.json")
    models = sorted(Path(name) for name in audit["verified_files"]["models"] if name.endswith(".txt"))
    require(len(models) == 24, "Exactly 24 audited models required")
    keys = [path.stem for path in models]
    model_files = [SCIENCE / "models" / (key + suffix) for key in keys
                   for suffix in (".txt", ".fit_started.json", ".complete.json")]
    model_bytes = sum(path.stat().st_size for path in model_files)
    require(model_bytes < 30_000_000, "Unexpected compact model size")
    OUT.mkdir(parents=True)
    copies = []

    def copy(source, relative, required_hash=None):
        source = Path(source).resolve()
        target = OUT / relative
        require(not target.exists(), "Duplicate archive destination")
        actual = sha(source)
        authority = required_hash or expected.get(str(source))
        if authority is not None:
            require(actual == authority, "Source differs from authority: " + str(source))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        require(sha(target) == actual == sha(source), "Copy/source changed during archive")
        copies.append(dict(original_path=str(source), archive_path=str(Path(relative).as_posix()),
                           bytes=source.stat().st_size, sha256=actual,
                           authority_sha256=authority, source_and_copy_rehashed=True))

    copy(AUDIT, "audit/audit.json", AUDIT_SHA)
    copy(SCIENCE / "run_contract.json", "run_contract.json", CONTRACT_SHA)
    for name in ("validation_freeze.json", "validation_freeze.complete.json",
                 "reports/2025.json", "reports/2025.complete.json"):
        copy(SCIENCE / name, name)
    for path in model_files:
        copy(path, "models/" + path.name)
    for stamp in [f"2025{m:02d}" for m in range(1, 13)]:
        for name in ("predictions.complete.json", "economics.complete.json", "daily.complete.json"):
            copy(SCIENCE / "months" / stamp / name, f"months/{stamp}/{name}")
    references = []
    for key in keys:
        for kind, suffix in (("inputs", ".json"), ("matrix", ".npy"), ("targets", ".npz")):
            marker_path = SCIENCE / "fits" / key / (kind + ".complete.json")
            payload = SCIENCE / "fits" / key / (kind + suffix)
            marker = read(marker_path)
            require(marker["status"] == "COMPLETE" and marker["binding"] == CONTRACT_SHA,
                    "Fit marker differs")
            members = {str((SCIENCE / relative).resolve()): value for relative, value in marker["files"].items()}
            name = str(payload.resolve())
            require(payload.is_file() and members.get(name) == expected.get(name) and name in expected,
                    "Local fit reference is absent or disagrees with audit")
            relative_marker = f"fit_seals/{key}/{kind}.complete.json"
            copy(marker_path, relative_marker)
            references.append(dict(fit_key=key, kind=kind, path=name, bytes_observed=payload.stat().st_size,
                                   sha256_from_audited_authority=expected[name], marker_archive_path=relative_marker,
                                   audit_marker_hash_agreement=True, exists=True,
                                   payload_rehashed_during_archive=False, payload_copied=False))
    for name, digest in contract["dependencies"].items():
        copy(SCIENCE / "executed_code" / name, "code/scientific_producer/" + name, digest)
    copy(HERE / "MONTHLY_WALK_FORWARD_IMPLEMENTATION_REVIEW.json", "code/scientific_producer/MONTHLY_WALK_FORWARD_IMPLEMENTATION_REVIEW.json")
    snapshot_hashes = {Path(name).name: digest for name, digest in expected.items()
                       if Path(name).parent.resolve() == HERE.resolve()}
    snapshot_hashes.update({Path(name).name: digest for name, digest in
                            read(RUNTIME / "watch_started.json")["own_files"].items()})
    for path in sorted((RUNTIME / "executed_code").iterdir()):
        require(path.is_file() and path.suffix in (".py", ".json", ".md"), "Unexpected executed-code entry")
        require(path.name in snapshot_hashes, "Executed snapshot missing its reviewed hash")
        copy(path, "code/auditor_runtime/" + path.name, snapshot_hashes[path.name])
    review = read(HERE / "MONTHLY_WALK_FORWARD_INDEX_AUDIT_V2_REVIEW_20261024.json")
    receipt = review["author_receipt"]
    copy(HERE / receipt["path"], "code/auditor_runtime/" + receipt["path"], receipt["sha256"])
    launch = read(VALIDATION / "launch.json")
    for name, digest in launch["authority"]["files"].items():
        copy(VALIDATION / "executed_code" / name, "code/validation_overlay/" + name, digest)
    copy(Path(launch["runtime_review_path"]), "code/validation_overlay/MONTHLY_RESOURCE_OVERLAY_REVIEW.json",
         launch["runtime_review_sha256"])
    for name in ("launch.json", "completion.json"):
        copy(VALIDATION / name, "runtime/validation/" + name)
    for name in ("process.json", "process_monitor_binding.json", "monitor_open.json", "monitored_exit.json",
                 "monitor_existing_process_20261023.py", "monitor_observations.jsonl", "stderr.log", "stdout.log"):
        copy(MONITOR / name, "runtime/validation_monitor/" + name)
    runtime_names = ("watch_started.json", "admission.json", "attempt.json", "process.json", "exit.json",
                     "completion.json", "resource_00000.json", "resource_00001.json", "root_launch_review.json",
                     "supervisor_start_receipt.json", "supervisor_stdout.log", "supervisor_stderr.log", "stderr.log")
    for name in runtime_names:
        copy(RUNTIME / name, "runtime/audit_02/" + name)
    for name in ("dataset_contract.json", "feature_contract.json", "completion.json"):
        copy(BASE / "session_clock_dataset_v1" / name, "source_authorities/" + name)
    source_audit = Path(contract["source_audit"]["path"])
    copy(source_audit, "source_authorities/audit.json", contract["source_audit"]["sha256"])
    local_sources = []
    for path in (BASE / "session_clock_dataset_v1/index.parquet", RUNTIME / "stdout.log"):
        name = str(path.resolve())
        # stdout duplicates audit.json's printed content; keep a hash reference only.
        digest = expected.get(name) if path.suffix == ".parquet" else sha(path)
        require(path.is_file() and digest is not None, "Local reference missing")
        local_sources.append(dict(path=name, bytes_observed=path.stat().st_size, sha256=digest,
                                  current_payload_rehashed=path.suffix != ".parquet", copied=False))
    write(OUT / "LOCAL_REFERENCES.json", dict(
        authority_audit_path=str(AUDIT), authority_audit_sha256=AUDIT_SHA,
        verification_scope="Hash agreement audit↔sealed markers plus current file existence and size; no extra payload rehash of fits/index.",
        fit_files=references, other_local_files=local_sources,
        arrays=len([r for r in references if r["kind"] in ("matrix", "targets")]),
        array_bytes=sum(r["bytes_observed"] for r in references if r["kind"] in ("matrix", "targets")),
        large_payload_copies=0, matrix_target_refit_or_evaluation=False))
    copy(Path(__file__), "archive_evidence.py")
    # Verify compact originals and copies once more; no fit payloads are read here.
    for item in copies:
        require(sha(item["original_path"]) == item["sha256"] == sha(OUT / item["archive_path"]),
                "Compact evidence changed before archive completion")
    write(OUT / "MANIFEST.json", dict(
        status="COMPACT_AUDITED_VALIDATION_2025_ARCHIVE", archived_utc=datetime.now(timezone.utc).isoformat(),
        authority_audit_sha256=AUDIT_SHA, source_scientific_root=str(SCIENCE.resolve()),
        copied_files=len(copies), copied_bytes=sum(r["bytes"] for r in copies), copies=copies,
        models=24, model_and_marker_files=72, model_and_marker_bytes=model_bytes,
        fit_payload_reference_files=len(references), local_references_sha256=sha(OUT / "LOCAL_REFERENCES.json"),
        prior_failed_audit_archive="../monthly_validation_audit_01_failure",
        scientific_claim="PASS conditional on sealed scores; no model refit or inference reproduction; no promotion.",
        no_new_market_evaluation=True, no_large_payload_copies=True))
    print(json.dumps(dict(status="ARCHIVE_COPIES_VERIFIED", path=str(OUT), files=len(copies),
                          bytes=sum(r["bytes"] for r in copies), references=len(references),
                          manifest_sha256=sha(OUT / "MANIFEST.json")), indent=2))


if __name__ == "__main__":
    main()
