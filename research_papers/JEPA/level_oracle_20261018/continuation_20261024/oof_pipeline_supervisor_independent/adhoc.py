from pathlib import Path
import datetime, json, sys, tempfile
ROOT=Path(__file__).resolve().parent
CODE=Path(r'C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/research_papers/JEPA/level_oracle_20261018')
sys.path.insert(0,str(CODE))
import pytest
import launch_oof_pipeline_20261024 as supervisor
import launch_monthly_test_index_v2_audit_20261024 as ops
import test_launch_oof_pipeline_20261024 as fixtures
pins=json.loads((ROOT/'expected_pins.json').read_text(encoding='utf-8'))
assert {n:supervisor.sha(CODE/n) for n in pins} == pins
resources=ops.observation();ops.gate(resources)
(ROOT/'adhoc_admission.json').write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),resources=resources,pins=pins),indent=2),encoding='utf-8')
with tempfile.TemporaryDirectory(prefix='oof_independent_') as temp, pytest.MonkeyPatch.context() as patch:
    a=fixtures.authorities.__wrapped__(Path(temp).resolve(),patch)
    receipt=fixtures.admit(a)
    original=supervisor.importlib.import_module
    calls=[]
    def imported(name):
        result=original(name)
        if name==supervisor.HELPER_NAME.removesuffix('.py'):
            Path(a.request_pin['path']).write_bytes(b'changed synthetic request after pinned import')
            calls.append(name)
        return result
    def prohibited(*args,**kwargs):
        raise AssertionError('Popen must not occur')
    patch.setattr(supervisor.importlib,'import_module',imported)
    patch.setattr(supervisor.subprocess,'Popen',prohibited)
    try:
        supervisor.launch(receipt)
    except ValueError as error:
        assert 'Pinned bytes differ' in str(error),str(error)
    else:
        raise AssertionError('Mutated request admitted')
    assert len(calls)==1
    assert not Path(receipt['logs_root']).exists()
assert {n:supervisor.sha(CODE/n) for n in pins} == pins
result=dict(status='PASS_INDEPENDENT_POST_IMPORT_MUTATION_NEGATIVE',request_mutated_during_late_import=True,popen_called=False,claim_created=False,real_market_execution=False,pins=pins)
(ROOT/'adhoc_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
