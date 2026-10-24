from pathlib import Path
from datetime import datetime,timezone
import json,sys,subprocess,shutil
ROOT=Path(__file__).resolve().parent
CODE=Path(r'C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/research_papers/JEPA/level_oracle_20261018')
sys.path.insert(0,str(CODE))
import launch_oof_economic_audit_v2_20261024 as s
pins={'launch_oof_economic_audit_v2_20261024.py':'71decd9f97e40029dd4311fb5db3e59e7a68b569bca0fe5a80346bd8ccff69b6','test_launch_oof_economic_audit_v2_20261024.py':'c43bc15886b2d9f1ab2ed46e5600fb97de8ecf27f0bdd61d957ba7e8e41be90d','OOF_ECONOMIC_AUDIT_V2_LAUNCH_CONTRACT_20261024.md':'ce60993785b5d551827ecf5ad256e8ecb91567a3e8907fb08d1633b6c68acf11',s.PIPELINE_REVIEW:'8c6e4b570df7a12d27da6ed19c9f142382fa4bb054fcfacdd5dd5334ac7fbfd2',s.WRAPPER_REVIEW:'ca8f11ef9781a1f6996132032b8c7a09bf6f559970c66e0067bffab9507848f5','launch_oof_economic_audit_20261024.py':'17c1604419d0008be94f6922eb87f397143f8c04c87d01c3546ae66b5a643e1e','OOF_ECONOMIC_AUDIT_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json':'765b3a0f448ebe808281e491ad8710753ec0d1ac9b8cf942b0128c4c48c8e019','audit_oof_calibrated_policy.py':'e7481fbe944a9ffadcf637e7a4b69cd8d636cdf50ae295426191db9d76b5d44b'}
assert {n:s.sha(CODE/n) for n in pins}==pins
snapshot=ROOT/'initial_sources';snapshot.mkdir()
for n,h in pins.items():shutil.copyfile(CODE/n,snapshot/n);assert s.sha(snapshot/n)==h
selection='full_preflight or exact_code18 or v2_identity_and_source_admission_exact or upstream_review_cannot_be_pending or (real_empty_child_and_failures and (None or late_snapshot))'
command=[sys.executable,'-m','pytest',str(CODE/'test_launch_oof_economic_audit_v2_20261024.py'),'-q','-k',selection]
resources=s.observation();s.gate(resources)
admission=dict(utc=datetime.now(timezone.utc).isoformat(),resources=resources,minimum_free_bytes=s.MIN_FREE,pins=pins,command=command)
(ROOT/'admission.json').write_text(json.dumps(admission,indent=2)+'\n',encoding='utf-8')
with (ROOT/'pytest.log').open('wb') as stream:run=subprocess.run(command,cwd=CODE,stdout=stream,stderr=subprocess.STDOUT)
assert {n:s.sha(CODE/n) for n in pins}==pins
(ROOT/'result.json').write_text(json.dumps(dict(exit_code=run.returncode,pins=pins,log_sha256=s.sha(ROOT/'pytest.log')),indent=2)+'\n',encoding='utf-8')
print((ROOT/'pytest.log').read_text(encoding='utf-8'));print(json.dumps(admission,indent=2))
raise SystemExit(run.returncode)
