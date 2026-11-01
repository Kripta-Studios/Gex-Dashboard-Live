@'
import hashlib, importlib.util, json, os, pathlib, subprocess, sys, time
from datetime import datetime, timezone
import psutil
repo=pathlib.Path.cwd();week=repo/'research_papers/JEPA/weekly_multiday_20261101';base=pathlib.Path('D:/GexResearchArtifacts/weekly_multiday_20261101')
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert subprocess.check_output(['git','ls-remote','origin','refs/heads/research/multiscale-v1r1-net-usd'],text=True).split()[0]==commit
pins={
  "audit_weekly_h2_boundary_bridge.py": "69cb5c8bc018b80f12a9cf2203ecb1ba2928f419a17d2252dfe383c279a18750",
  "test_audit_weekly_h2_boundary_bridge.py": "5a829742c5035854a336a4eb2cc973106b7d29c427e9721bcdcc818c1f6d1694",
  "build_weekly_h2_boundary_bridge.py": "29d8e7906f0f594ed469b07bb8134a500d26cc01434a77928a09b8a8c90bedb2",
  "ADAPTATION_AND_BRIDGE_IMPLEMENTATION_REVIEW_20261101.md": "f4fe3591c0244236573618f52ec167cc490b53698e838915608b6209dc69b674",
  "H2_BOUNDARY_BRIDGE_EXTRACTION_CLOSURE_AND_AUDIT_BINDING_20261101.md": "80579b57ac21531d88560480e3d902981a8426cc4d3e7565d34768a7c7eaec05",
  "h2_boundary_bridge_extraction_archive_01/archive_receipt.json": "b0a9afbac3f38099ca20a1c37371a53dd2ae42fecc5e0e08e662e50754915570"
}
for name,expected in pins.items():assert sha(week/name)==expected,name
for name in [*pins,'launch_h2_boundary_bridge_audit_20261101.ps1']:
 f=week/name
 assert hashlib.sha256(subprocess.check_output(['git','show',commit+':'+f.relative_to(repo).as_posix()])).hexdigest()==sha(f),name
helper=repo/'research_papers/JEPA/level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py'
assert sha(helper)=='3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046'
spec=importlib.util.spec_from_file_location('resource_gate',helper);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
psutil.Process().cpu_affinity([0])
keys=['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS','ARROW_NUM_THREADS','POLARS_MAX_THREADS']
for k in keys:os.environ[k]='1'
obs=base/'h2_boundary_bridge_audit_observer_01'
assert not obs.exists();assert not (base/'h2_boundary_bridge_audit_01').exists()
root=base/'h2_boundary_bridge_01'
for name,h in [('manifest.json','9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86'),('inventory.json','599ca400fecae12ce4098187a45af3ee0cf8c1b070e060d8c84e422ce92c6161')]:assert sha(root/name)==h
upstream=base/'h2_boundary_bridge_extraction_observer_01'/'exit.json'
assert sha(upstream)=='abdd5914c8649a79da70a562db681a7d384ee01ccb6c0a40e3c4549bb31d53af'
assert json.loads(upstream.read_text())['exit_code']==0
resources=m.observation();m.gate(resources)
code=week/'audit_weekly_h2_boundary_bridge.py'
args=[sys.executable,'-X','utf8','-u',str(code),'--bridge-manifest-sha256','9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86','--inventory-sha256','599ca400fecae12ce4098187a45af3ee0cf8c1b070e060d8c84e422ce92c6161','--wrapper-sha256',pins['build_weekly_h2_boundary_bridge.py'],'--auditor-sha256',pins[code.name]]
obs.mkdir(parents=True)
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
write(obs/'admission.json',dict(utc=now(),command=args,publication_commit=commit,pins=pins,resources=resources,cpu_affinity=psutil.Process().cpu_affinity(),thread_variables={k:os.environ[k] for k in keys}))
start=time.monotonic()
with (obs/'stdout.log').open('wb') as stdout,(obs/'stderr.log').open('wb') as stderr:
 p=subprocess.Popen(args,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
 write(obs/'process.json',dict(pid=p.pid,creation_time=psutil.Process(p.pid).create_time(),utc=now(),command=args));result=p.wait()
write(obs/'exit.json',dict(exit_code=result,utc=now(),source='subprocess.Popen.wait_retained_handle',elapsed_seconds=time.monotonic()-start,files={str(obs/n):sha(obs/n) for n in ['admission.json','process.json','stdout.log','stderr.log']}))
print(json.dumps(dict(pid=p.pid,exit_code=result,observer=str(obs))))
if result:print((obs/'stderr.log').read_text(encoding='utf-8'))
sys.exit(result)
'@ | & 'C:/Program Files/Python314/python.exe' -X utf8 -u -
