from pathlib import Path
from datetime import datetime,timezone
import json,os,sys,subprocess,shutil
ROOT=Path(__file__).resolve().parent
CODE=Path(r'C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/research_papers/JEPA/level_oracle_20261018')
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
import psutil
process=psutil.Process();process.cpu_affinity([process.cpu_affinity()[0]])
sys.path.insert(0,str(CODE))
import launch_oof_economic_audit_v2r1_20261024 as s
pins={'launch_oof_economic_audit_v2r1_20261024.py':'93ad3efcc124099ea2a8e4f8c64995671e1922e5ce1974c9f07b3fa02cd3ce1a','test_launch_oof_economic_audit_v2r1_20261024.py':'90e2125bc62c8ff2faf93ea3f380996757afde1dc40a9d09f6bea77645ff54ee','OOF_TRANSITIVE_SOURCE_V2R1_IMPLEMENTATION_CONTRACT_20261024.md':'063f7cc7cf26506dc8a8d9691e841a89c2a55f87ce7b72b79e8743f40db3dc43',s.PIPELINE_REVIEW:'2782b686947c9ddd5f723ad2b279802d21f3adbbee79aa76a6cd6e8bce551a78',s.WRAPPER_REVIEW:'7431a6df11966c46ce5aa66bac5d707b7dfe9e131f59366df24f0f2f66c222c9','launch_oof_economic_audit_v2_20261024.py':'71decd9f97e40029dd4311fb5db3e59e7a68b569bca0fe5a80346bd8ccff69b6','OOF_ECONOMIC_AUDIT_V2_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json':'211b64f7be7d8829eb8161f2853b390a1ade9c67cad2dea4040e4ea78c785556','audit_oof_calibrated_policy.py':'e7481fbe944a9ffadcf637e7a4b69cd8d636cdf50ae295426191db9d76b5d44b'}
assert {n:s.sha(CODE/n) for n in pins}==pins
snapshot=ROOT/'initial_sources';snapshot.mkdir()
for n,h in pins.items():shutil.copyfile(CODE/n,snapshot/n);assert s.sha(snapshot/n)==h
selection='full_preflight or exact_code18 or upstream_review_cannot_be_pending or (v2r1_identity_and_source_admission_exact and (request_v2 or binding_v2 or contract_v2 or external_digest))'
command=[sys.executable,'-m','pytest',str(CODE/'test_launch_oof_economic_audit_v2r1_20261024.py'),'-q','-k',selection]
resources=s.observation();s.gate(resources)
admission=dict(utc=datetime.now(timezone.utc).isoformat(),resources=resources,minimum_free_bytes=s.MIN_FREE,cpu_affinity=process.cpu_affinity(),threads={k:os.environ[k] for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']},pins=pins,command=command)
(ROOT/'admission.json').write_text(json.dumps(admission,indent=2)+'\n',encoding='utf-8')
with (ROOT/'pytest.log').open('wb') as stream:run=subprocess.run(command,cwd=CODE,stdout=stream,stderr=subprocess.STDOUT)
assert {n:s.sha(CODE/n) for n in pins}==pins
(ROOT/'result.json').write_text(json.dumps(dict(exit_code=run.returncode,pins=pins,log_sha256=s.sha(ROOT/'pytest.log')),indent=2)+'\n',encoding='utf-8')
print((ROOT/'pytest.log').read_text(encoding='utf-8'));print(json.dumps(admission,indent=2))
raise SystemExit(run.returncode)
