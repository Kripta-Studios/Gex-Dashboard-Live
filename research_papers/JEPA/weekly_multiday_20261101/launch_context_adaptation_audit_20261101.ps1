@'
import hashlib, importlib.util, json, os, pathlib, subprocess, sys, time
from datetime import datetime, timezone
import psutil
repo=pathlib.Path.cwd();week=repo/'research_papers/JEPA/weekly_multiday_20261101';base=pathlib.Path('D:/GexResearchArtifacts/weekly_multiday_20261101')
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert subprocess.check_output(['git','ls-remote','origin','refs/heads/research/multiscale-v1r1-net-usd'],text=True).split()[0]==commit
pins={
  "audit_weekly_context_adaptation.py": "c6a116d3c39e054031b594547d36c54fd0a5eeed0aa6524c10ca89ba0f7198a5",
  "test_audit_weekly_context_adaptation.py": "fd835bbefba283e4d746205941924ceebd3e3937f853591dbf69688d9b83fefd",
  "evaluate_weekly_context_adaptation.py": "d03494bf68e281bc7c9e68f385aa111567eac4206cf5b44133e17bb480ed5df8",
  "test_evaluate_weekly_context_adaptation.py": "2f44f17d459cd7cb43c5c3842fb4b2d72c689278f797426a75ac006f0d5db43f",
  "ADAPTATION_AND_BRIDGE_IMPLEMENTATION_REVIEW_20261101.md": "f4fe3591c0244236573618f52ec167cc490b53698e838915608b6209dc69b674",
  "ADAPTATION_PRODUCER_CLOSURE_AND_AUDIT_BINDING_20261101.md": "ce98ea909d72077f0e5e43f5f7a37b30143cac2e279aca1f6c47bb7d87bbd890",
  "adaptation_producer_archive_01/archive_receipt.json": "cd9f341eadf54680cf99f8c7f68f16062dc64e2b2a2729c0b0942fe9de407361"
}
for name,expected in pins.items():assert sha(week/name)==expected,name
for name in [*pins,'launch_context_adaptation_audit_20261101.ps1']:
 f=week/name
 assert hashlib.sha256(subprocess.check_output(['git','show',commit+':'+f.relative_to(repo).as_posix()])).hexdigest()==sha(f),name
helper=repo/'research_papers/JEPA/level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py'
assert sha(helper)=='3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046'
spec=importlib.util.spec_from_file_location('resource_gate',helper);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
psutil.Process().cpu_affinity([0])
keys=['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS','ARROW_NUM_THREADS','POLARS_MAX_THREADS']
for k in keys:os.environ[k]='1'
obs=base/'h2_context_adaptation_audit_observer_01'
assert not obs.exists();assert not (base/'h2_context_adaptation_audit_01').exists()
for rel,h in [('h2_context_adaptation_01/manifest.json','e8cf5cd4a001cd98cdf29e54cf47bbdf3c34d6652abf34ef7c71fffa0bd97f23'),('h2_boundary_bridge_01/manifest.json','9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86'),('h2_boundary_bridge_audit_01/audit.json','83c9ade0b6b7205484dd275df8593107238f94468d8564f7351e9481a475033c')]:assert sha(base/rel)==h
p=base/'h2_context_adaptation_observer_01'/'exit.json'
assert sha(p)=='2872a00672a43ca7a432372e69b2473a505a56f61f29270dc31896d5b4bec01c' and json.loads(p.read_text())['exit_code']==0
resources=m.observation();m.gate(resources)
code=week/'audit_weekly_context_adaptation.py'
args=[sys.executable,'-X','utf8','-u',str(code),'--execute-reviewed-audit','--producer-manifest-sha256','e8cf5cd4a001cd98cdf29e54cf47bbdf3c34d6652abf34ef7c71fffa0bd97f23','--producer-sha256',pins['evaluate_weekly_context_adaptation.py'],'--producer-tests-sha256',pins['test_evaluate_weekly_context_adaptation.py'],'--bridge-manifest-sha256','9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86','--bridge-audit-sha256','83c9ade0b6b7205484dd275df8593107238f94468d8564f7351e9481a475033c','--auditor-sha256',pins[code.name]]
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
