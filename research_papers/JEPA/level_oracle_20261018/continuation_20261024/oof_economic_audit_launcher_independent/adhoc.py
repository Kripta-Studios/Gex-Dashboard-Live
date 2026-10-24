from pathlib import Path
from datetime import datetime,timezone
import json,sys,tempfile
ROOT=Path(__file__).resolve().parent
CODE=Path(r'C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/research_papers/JEPA/level_oracle_20261018')
sys.path.insert(0,str(CODE))
import pytest
import psutil
import launch_oof_economic_audit_20261024 as s
import test_launch_oof_economic_audit_20261024 as f
pins=json.loads((ROOT/'admission.json').read_text(encoding='utf-8'))['pins']
assert {n:s.sha(CODE/n) for n in pins}==pins
resources=s.observation();s.gate(resources)
(ROOT/'adhoc_admission.json').write_text(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),resources=resources,pins=pins),indent=2)+'\n',encoding='utf-8')
checks=[]
with tempfile.TemporaryDirectory(prefix='audit_oof_review_pid_') as temp,pytest.MonkeyPatch.context() as patch:
    case=f.case.__wrapped__(Path(temp).resolve(),patch)
    ref=case.binding['upstream']['exit'];ended=s.read(ref['path']);ended['pid']=float(ended['pid'])
    assert ended['pid']==789 and type(ended['pid']) is float
    f.rewrite(ref,ended)
    completed_ref=case.binding['upstream']['supervisor_completion'];completed=s.read(completed_ref['path'])
    completed['process_files'][ref['path']]=ref['sha256'];f.rewrite(completed_ref,completed)
    f.rewrite(case.binding_ref,case.binding)
    try:f.admit(case)
    except ValueError as error:assert 'process identity/exit' in str(error),str(error)
    else:raise AssertionError('Numerically equal float PID admitted')
    checks.append('Numerically equal exit.pid=789.0 rejected by strict type guard')
with tempfile.TemporaryDirectory(prefix='audit_oof_review_gate_') as temp,pytest.MonkeyPatch.context() as patch:
    case=f.case.__wrapped__(Path(temp).resolve(),patch);receipt=f.admit(case)
    def forbidden(*args,**kwargs):raise AssertionError('Popen after low commit')
    patch.setattr(s,'observation',lambda:dict(available_ram_bytes=3000000000,free_commit_bytes=1999999999))
    patch.setattr(s.subprocess,'Popen',forbidden)
    try:s.launch(receipt)
    except ValueError as error:assert '2GB RAM/commit' in str(error),str(error)
    else:raise AssertionError('Low commit launch admitted')
    logs=Path(receipt['logs_root'])
    assert (logs/'failure.json').exists() and not (logs/'process.json').exists() and not (logs/'completion.json').exists()
    assert not Path(receipt['output_root']).exists()
    checks.append('Launch low-commit gate preserves failure/claim with no Popen/process/audit output/completion')
assert {n:s.sha(CODE/n) for n in pins}==pins
scientific=['run_oof_calibrated_pipeline','run_monthly_walk_forward','audit_oof_calibrated_policy','monthly_oof_calibration_adapter','evaluate_oof_calibrated_policy','train_models']
assert not any(n in sys.modules for n in scientific)
result=dict(status='PASS_INDEPENDENT_OPERATIONAL_ADHOC',checks=checks,scientific_modules_imported=False,child_processes_started=False,pins=pins)
(ROOT/'adhoc_result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
