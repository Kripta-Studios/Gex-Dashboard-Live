@'
import hashlib, importlib.util, json, os, pathlib, subprocess, sys, time
from datetime import datetime, timezone
import psutil
repo=pathlib.Path.cwd();week=repo/'research_papers/JEPA/weekly_multiday_20261101';base=pathlib.Path('D:/GexResearchArtifacts/weekly_multiday_20261101')
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert subprocess.check_output(['git','ls-remote','origin','refs/heads/research/multiscale-v1r1-net-usd'],text=True).split()[0]==commit
pins={
  "evaluate_weekly_context_adaptation.py": "d03494bf68e281bc7c9e68f385aa111567eac4206cf5b44133e17bb480ed5df8",
  "test_evaluate_weekly_context_adaptation.py": "2f44f17d459cd7cb43c5c3842fb4b2d72c689278f797426a75ac006f0d5db43f",
  "ADAPTATION_WALKFORWARD_CONTRACT_20261101.md": "608dae37c21c19277a36dbcc1eeaa36da0135385a080618d461a4e240855cc61",
  "ADAPTATION_AND_BRIDGE_IMPLEMENTATION_REVIEW_20261101.md": "f4fe3591c0244236573618f52ec167cc490b53698e838915608b6209dc69b674",
  "ADAPTATION_RUNTIME_BINDING_20261101.md": "56e603018df186e049623a0715758dc258ad1b33bb8d7c89553b89bfee02d27e",
  "ADAPTATION_REPORT_ATTRIBUTION_CLARIFICATION_20261101.md": "5b21927e109c22c24af91599b019933b8132f7b1f52f359a7fa2936bcfee5c86",
  "USER_MONTHLY_PROFITABILITY_ACCEPTANCE_20261101.md": "806f7728a2ad434bc08929d3715f307455bd37862ae4c19a2cd2cc1d64a5ee5b",
  "h2_boundary_bridge_audit_archive_01/archive_receipt.json": "c389bbd89bcf59d442a5e3af33bbb0e2a8f8d9e53cdbbdb3a1682cf6732daf40"
}
for name,expected in pins.items():assert sha(week/name)==expected,name
for name in [*pins,'launch_context_adaptation_20261101.ps1']:
 f=week/name
 assert hashlib.sha256(subprocess.check_output(['git','show',commit+':'+f.relative_to(repo).as_posix()])).hexdigest()==sha(f),name
helper=repo/'research_papers/JEPA/level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py'
assert sha(helper)=='3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046'
spec=importlib.util.spec_from_file_location('resource_gate',helper);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
psutil.Process().cpu_affinity([0])
keys=['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS','ARROW_NUM_THREADS','POLARS_MAX_THREADS']
for k in keys:os.environ[k]='1'
obs=base/'h2_context_adaptation_observer_01'
assert not obs.exists();assert not (base/'h2_context_adaptation_01').exists()
for rel,h in [('h2_boundary_bridge_01/manifest.json','9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86'),('h2_boundary_bridge_audit_01/audit.json','83c9ade0b6b7205484dd275df8593107238f94468d8564f7351e9481a475033c')]:assert sha(base/rel)==h
for rel,h in [('h2_boundary_bridge_extraction_observer_01/exit.json','abdd5914c8649a79da70a562db681a7d384ee01ccb6c0a40e3c4549bb31d53af'),('h2_boundary_bridge_audit_observer_01/exit.json','278ff49b30e84506eb6e063d4cf7dd471396b10d901441fdd93ffe93e4ea41fa')]:
 p=base/rel;assert sha(p)==h and json.loads(p.read_text())['exit_code']==0
resources=m.observation();m.gate(resources)
code=week/'evaluate_weekly_context_adaptation.py'
args=[sys.executable,'-X','utf8','-u',str(code),'--execute-reviewed-adaptation','--bridge-manifest-sha256','9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86','--bridge-audit-sha256','83c9ade0b6b7205484dd275df8593107238f94468d8564f7351e9481a475033c']
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
