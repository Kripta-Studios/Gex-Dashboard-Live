from pathlib import Path
from datetime import datetime,timezone
import json,sys,subprocess,shutil
ROOT=Path(__file__).resolve().parent
CODE=Path(r'C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live/research_papers/JEPA/level_oracle_20261018')
sys.path.insert(0,str(CODE))
import launch_oof_economic_audit_20261024 as s
pins={'launch_oof_economic_audit_20261024.py':'17c1604419d0008be94f6922eb87f397143f8c04c87d01c3546ae66b5a643e1e','test_launch_oof_economic_audit_20261024.py':'2f6f00c06d000ce39305336fae1b6f993fd9ecaf98bf69be15a9a48a43cd992a','OOF_ECONOMIC_AUDIT_LAUNCH_DESIGN_20261024.md':'3c37ef5f4f36c3120dad8fda26f87b32d2c705780093f5c08d8d5bd67714e132'}
assert {n:s.sha(CODE/n) for n in pins}==pins
snapshot=ROOT/'initial_sources';snapshot.mkdir()
for n,h in pins.items():shutil.copyfile(CODE/n,snapshot/n);assert s.sha(snapshot/n)==h
selection='full_preflight or exact_code17 or nested_partial or (resigned_exit_fault and (pid or observed_utc)) or real_empty_child_and_failures or monitor_init or locks_exclusive'
command=[sys.executable,'-m','pytest',str(CODE/'test_launch_oof_economic_audit_20261024.py'),'-q','-k',selection]
resources=s.observation();s.gate(resources)
admission=dict(utc=datetime.now(timezone.utc).isoformat(),resources=resources,minimum_free_bytes=s.MIN_FREE,pins=pins,command=command)
(ROOT/'admission.json').write_text(json.dumps(admission,indent=2)+'\n',encoding='utf-8')
with (ROOT/'pytest.log').open('wb') as stream:run=subprocess.run(command,cwd=CODE,stdout=stream,stderr=subprocess.STDOUT)
assert {n:s.sha(CODE/n) for n in pins}==pins
(ROOT/'result.json').write_text(json.dumps(dict(exit_code=run.returncode,pins=pins,log_sha256=s.sha(ROOT/'pytest.log')),indent=2)+'\n',encoding='utf-8')
print((ROOT/'pytest.log').read_text(encoding='utf-8'));print(json.dumps(admission,indent=2))
raise SystemExit(run.returncode)
