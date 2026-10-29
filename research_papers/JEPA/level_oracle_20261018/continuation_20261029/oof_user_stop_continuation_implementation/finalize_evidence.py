"""Package preserved synthetic attempts; no runtime/source admission or producers."""
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parent
repo = Path.cwd()
here = repo / "research_papers/JEPA/level_oracle_20261018"
destination = here / "continuation_20261029/oof_user_stop_continuation_implementation"
checks = root / "final_checks"
checks.mkdir(exist_ok=False)
destination.mkdir(parents=True,exist_ok=False)

def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()

def write(path,value):
    with Path(path).open("x",encoding="utf-8") as stream:
        json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False)

sys.path.insert(0,str(here))
s = importlib.import_module("launch_oof_pipeline_user_stop_continuation_20261029")
code = here / "launch_oof_pipeline_user_stop_continuation_20261029.py"
tests = here / "test_launch_oof_pipeline_user_stop_continuation_20261029.py"
expected_code = "599f6d5c347ebdc3801bbe8cc21de55603a80a46858a8bad1d20729d307eee11"
expected_tests = "e1dc93402ee08eb53e1aaae850efc9b789f0d68fc2ddf05639a285a199471b2b"
assert sha(code)==expected_code and sha(tests)==expected_tests
for path in (code,tests):
    compile(path.read_text(encoding="utf-8"),str(path),"exec")
write(checks/"compile.json",dict(status="PASS_COMPILE_NO_PYC",files={str(code):sha(code),str(tests):sha(tests)}))
with (checks/"ruff.stdout.log").open("xb") as out,(checks/"ruff.stderr.log").open("xb") as err:
    command=[sys.executable,"-m","ruff","check",str(code),str(tests),"--select","F,E9"]
    lint=subprocess.run(command,stdout=out,stderr=err,check=False,creationflags=subprocess.CREATE_NO_WINDOW)
write(checks/"ruff.exit.json",dict(command=command,exit_code=lint.returncode,utc=datetime.now(timezone.utc).isoformat()))
assert lint.returncode==0
files,dependencies=s.implementation_files()
write(checks/"implementation_files.json",dict(files=files,dependencies=dependencies,
    scope="CODE_AND_REVIEW_HASHES_ONLY_NO_RUNTIME_SOURCE_ADMISSION"))
cpu=root/"attempt_08/cpu0_inheritance.json"
cpu_record=json.loads(cpu.read_text(encoding="utf-8"))
assert cpu_record["code_sha256"]==expected_code and cpu_record["tests_sha256"]==expected_tests
assert cpu_record["child_observation"]==dict(mask=1,threads=["1","1","1"])
copies=[]
for path in sorted(root.rglob("*")):
    if not path.is_file():
        continue
    target=destination/path.relative_to(root)
    target.parent.mkdir(parents=True,exist_ok=True)
    assert not target.exists()
    shutil.copyfile(path,target)
    assert sha(path)==sha(target)
    copies.append(dict(original=str(path),copy=str(target),sha256=sha(path),bytes=path.stat().st_size))
manifest=dict(status="EXACT_SYNTHETIC_EVIDENCE_COPIES",copies=copies,
    files=len(copies),bytes=sum(p["bytes"] for p in copies),utc=datetime.now(timezone.utc).isoformat())
write(root/"package_manifest.json",manifest)
shutil.copyfile(root/"package_manifest.json",destination/"package_manifest.json")
result=dict(status="IMPLEMENTED_SYNTHETICALLY_VERIFIED_NOT_RUNTIME_AUTHORITY",scope="IMPLEMENTATION_ONLY",
    runtime_authorized=False,real_preflight_executed=False,real_pipeline_executed=False,economic_auditor_executed=False,
    economic_payloads_interpreted=False,code=dict(path=str(code),sha256=expected_code),
    tests=dict(path=str(tests),sha256=expected_tests),implementation_files=files,dependencies=dependencies,
    cpu0_inheritance_test=dict(status="PASS_FIRST_INSTRUCTION_CPU0_THREADS1",
        evidence=dict(path=str(destination/"attempt_08/cpu0_inheritance.json"),sha256=sha(cpu))),
    author_attempts=[
        dict(attempt=1,passed=0,failed=1,deselected=25,reason="Initial RED: implementation absent; assertion failed before production code existed."),
        dict(attempt=2,passed=25,failed=1,deselected=0,reason="CPU fixture Win32 ABI error: missing pointer argtypes/restype; actual unchecked API returned mask0. Full attempt preserved."),
        dict(attempt=3,passed=1,failed=3,deselected=25,reason="Corrected CPU fixture passed; three new monitor RED cases exposed exit-race/sampling/affinity exception handling."),
        dict(attempt=4,passed=44,failed=1,deselected=0,reason="Snapshot test aliased expected and mutated dict; fixture corrected with independent copies. Frozen wrapper four-phase integration passed."),
        dict(attempt=5,passed=7,failed=2,deselected=45,reason="Foreign failure uncovered missing exact new-log guard, fixed. Busy OS lock correctly raised RuntimeError; fixture exception tuple corrected."),
        dict(attempt=6,passed=54,failed=0,deselected=0,seconds=106.97,code_sha256="bf781067ecfc59ee2d5927d5505c4b4a3301fbc3e5c8fb28a46d0a2c1056d897",
             tests_sha256="c4197f4f834f663604d8298dc2674c8a49885e615b8b3bbdc6c2103bb7c992f2",reason="Complete new suite under CPU0, threads1 and checked RAM/commit gate."),
        dict(attempt=7,passed=0,failed=1,deselected=54,reason="RED for final current economic supervisor process name requested by root/reviewer."),
        dict(attempt=8,passed=2,failed=0,deselected=53,seconds=0.16,code_sha256=expected_code,tests_sha256=expected_tests,
             reason="Final changed competitor rejection plus first-observation CPU0/thread1 child. No old suite repeated.")],
    attempt_counts_must_not_be_summed_as_one_suite=True,
    resource_evidence_scope="Attempts04/05/06/08 explicitly gated and CPU0-pinned before pytest. Earlier RED/focal attempts and attempt02 were not recorded as satisfying this launch-resource protocol.",
    integration_scope="Frozen wrapper resume, artificial empty-calendar correction/replay callbacks only; exact four phases08-11 and final12/27 checked. No real producer, fit or economic values.",
    evidence_manifest=dict(path=str(destination/"package_manifest.json"),sha256=sha(destination/"package_manifest.json")),
    independent_review="SEPARATE_AUTHORITY_PENDING_AT_AUTHOR_RESULT_CREATION",
    technical_ready=False,winner_selected=None,promotion_approved=False,utc=datetime.now(timezone.utc).isoformat())
write(here/"OOF_USER_STOP_CONTINUATION_IMPLEMENTATION_RESULT_20261029.json",result)
print(json.dumps(dict(status=result["status"],code_sha256=expected_code,tests_sha256=expected_tests,
    implementation_files=len(files),dependencies=len(dependencies),copied_files=len(copies),copied_bytes=manifest["bytes"],
    result_sha256=sha(here/"OOF_USER_STOP_CONTINUATION_IMPLEMENTATION_RESULT_20261029.json"),
    cpu0_inheritance_test=result["cpu0_inheritance_test"],evidence_manifest=result["evidence_manifest"]),indent=2))
