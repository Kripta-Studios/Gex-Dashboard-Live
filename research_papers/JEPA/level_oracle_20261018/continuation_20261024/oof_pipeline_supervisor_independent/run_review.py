from pathlib import Path
import datetime, hashlib, json, subprocess, sys
ROOT = Path(__file__).resolve().parent
CODE = Path(r'C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/research_papers/JEPA/level_oracle_20261018')
sys.path.insert(0, str(CODE))
import launch_oof_pipeline_20261024 as supervisor
import launch_monthly_test_index_v2_audit_20261024 as ops
names = supervisor.NEW_FILES
pins = {n: supervisor.sha(CODE/n) for n in names}
assert pins == json.loads((ROOT/'expected_pins.json').read_text(encoding='utf-8'))
resources = ops.observation(); ops.gate(resources)
selection = 'complete_metadata_admission or complete_twelve_phase or actual_contract_or_index or extra_local_digest or correction_other_root or simulated_junction_after or destinations_revalidated or preflight or post_popen_junction or post_popen_publication or monitor_init or exit_false or naive or low_commit'
command = [sys.executable, '-m', 'pytest', str(CODE/'test_launch_oof_pipeline_20261024.py'), '-q', '-k', selection]
receipt = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), resources=resources, minimum_free_bytes=2000000000, pins=pins, command=command)
(ROOT/'admission.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
with (ROOT/'pytest.log').open('wb') as stream:
    result=subprocess.run(command, cwd=CODE, stdout=stream, stderr=subprocess.STDOUT)
assert {n:supervisor.sha(CODE/n) for n in names} == pins
(ROOT/'result.json').write_text(json.dumps(dict(exit_code=result.returncode, pins=pins, log_sha256=supervisor.sha(ROOT/'pytest.log')), indent=2),encoding='utf-8')
print((ROOT/'pytest.log').read_text(encoding='utf-8'))
print(json.dumps(receipt, indent=2))
raise SystemExit(result.returncode)
