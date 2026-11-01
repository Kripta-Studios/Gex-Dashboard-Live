@'
import hashlib,importlib.util,json,os,pathlib,subprocess,sys,time
from datetime import datetime,timezone
import psutil
repo=pathlib.Path.cwd();week=repo/'research_papers/JEPA/weekly_multiday_20261101';base=pathlib.Path('D:/GexResearchArtifacts/weekly_multiday_20261101')
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert subprocess.check_output(['git','ls-remote','origin','refs/heads/research/multiscale-v1r1-net-usd'],text=True).split()[0]==commit
pins={
  "audit_weekly_prequential_ev_filter.py": "16e62e2e3670837f5f3f05020f9dd765bf3c34cdfab7b9e3a439d17be51d7139",
  "test_audit_weekly_prequential_ev_filter.py": "38c278e9c91474f2c90f3710708ddc06d84e13ba4004b345b5e0466ee7c56c62",
  "PREQUENTIAL_EV_FILTER_CONTRACT_20261101.md": "0b81b77b0f058248e5e55b004c263dd0f97e5089cabb96336ae5c74f622312aa",
  "PREQUENTIAL_EV_FILTER_CONTRACT_REVIEW_20261101.md": "d108aa68eac6173a90ea919a8aaa9ffe17f995331b6e729f41e8e022fa320bb6",
  "PREQUENTIAL_EV_FILTER_AUDIT_IMPLEMENTATION_REVIEW_20261101.md": "a99c04e9f7f997855518683370e1b3e3ab4a9978287b766174163dca239b2899",
  "PREQUENTIAL_EV_FILTER_PRODUCER_CLOSURE_20261101.md": "461ca123b214e789214a346b883480421d3fba00d4b5d4f6ebd5f051c221bdb2",
  "prequential_ev_filter_audit_preparation_archive_01/archive_receipt.json": "5334a91e5c3ed6e05f655ffff1440f031744e6541f660f7f0610cd7b2ed5be2f",
  "prequential_ev_filter_producer_archive_01/archive_receipt.json": "a204ae5da05ff39cbe00c15814441fe8ffaf66c6c9b0158896b8ef958d49eb32",
  "PREQUENTIAL_EV_FILTER_AUDIT_RUNTIME_BINDING_20261101.md": "6f0930dfb4eada5cc5010ee00b83f5bbcb6ce6470cd7c8d3fb2b7040428e49a5"
}
for name,h in pins.items():assert sha(week/name)==h,name
for name in [*pins,'launch_prequential_ev_filter_audit_20261101.ps1']:
 p=week/name;assert subprocess.check_output(['git','show',commit+':'+p.relative_to(repo).as_posix()])==p.read_bytes(),name
helper=repo/'research_papers/JEPA/level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py'
assert sha(helper)=='3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046'
spec=importlib.util.spec_from_file_location('resource_gate',helper);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
psutil.Process().cpu_affinity([0])
keys=['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS','ARROW_NUM_THREADS','POLARS_MAX_THREADS']
for k in keys:os.environ[k]='1'
for rel,h in [('h2_context_adaptation_01/manifest.json','e8cf5cd4a001cd98cdf29e54cf47bbdf3c34d6652abf34ef7c71fffa0bd97f23'),('h2_context_adaptation_audit_04/audit.json','9a487fba18504ae4faff2c1dba17d1c000eb237436a09a7fe22747e328cb307a'),('h2_context_adaptation_audit_observer_04/exit.json','5d59d1a3978d8d9aa31c7c3fab567d1ae7e901494aa8efb12377ca65f91de420')]:assert sha(base/rel)==h
assert json.loads((base/'h2_context_adaptation_audit_observer_04/exit.json').read_text(encoding='utf-8'))['exit_code']==0
assert sha(base/'prequential_ev_filter_01/manifest.json')=='4c166202bd3d20d16f88f7d6fbfef9f5fe42d099071be6b414d6786126e3ddec'
assert sha(base/'prequential_ev_filter_observer_01/exit.json')=='76962d8c22e46b87a1d5a52ab049913aed9d3831f1d2766c5eb4e440afd93878'
assert json.loads((base/'prequential_ev_filter_observer_01/exit.json').read_text(encoding='utf-8'))['exit_code']==0
obs=base/'prequential_ev_filter_audit_observer_01';out=base/'prequential_ev_filter_audit_01'
assert not obs.exists() and not out.exists()
args=[sys.executable,'-X','utf8','-u',str(week/'audit_weekly_prequential_ev_filter.py'),'--execute-reviewed-audit','--producer-manifest-sha256','4c166202bd3d20d16f88f7d6fbfef9f5fe42d099071be6b414d6786126e3ddec','--producer-exit-sha256','76962d8c22e46b87a1d5a52ab049913aed9d3831f1d2766c5eb4e440afd93878','--auditor-sha256',pins['audit_weekly_prequential_ev_filter.py']]
obs.mkdir()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
resources=m.observation()
write(obs/'resource_observation.json',dict(utc=now(),resources=resources,cpu_affinity=psutil.Process().cpu_affinity(),thread_variables={k:os.environ[k] for k in keys}))
m.gate(resources)
write(obs/'admission.json',dict(utc=now(),command=args,publication_commit=commit,pins=pins,resources=resources,cpu_affinity=psutil.Process().cpu_affinity(),thread_variables={k:os.environ[k] for k in keys}))
start=time.monotonic()
with (obs/'stdout.log').open('wb') as stdout,(obs/'stderr.log').open('wb') as stderr:
 p=subprocess.Popen(args,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
 write(obs/'process.json',dict(pid=p.pid,creation_time=psutil.Process(p.pid).create_time(),utc=now(),command=args));result=p.wait()
write(obs/'exit.json',dict(exit_code=result,utc=now(),source='subprocess.Popen.wait_retained_handle',elapsed_seconds=time.monotonic()-start,files={str(obs/n):sha(obs/n) for n in ['resource_observation.json','admission.json','process.json','stdout.log','stderr.log']}))
print(json.dumps(dict(pid=p.pid,exit_code=result,observer=str(obs))))
if result:print((obs/'stderr.log').read_text(encoding='utf-8'))
sys.exit(result)
'@ | & 'C:/Program Files/Python314/python.exe' -X utf8 -u -
