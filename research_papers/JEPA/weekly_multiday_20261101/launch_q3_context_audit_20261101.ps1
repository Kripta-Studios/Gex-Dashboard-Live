@'
import hashlib, importlib.util, json, os, pathlib, subprocess, sys, time
from datetime import datetime,timezone
import psutil
repo=pathlib.Path.cwd();week=repo/'research_papers/JEPA/weekly_multiday_20261101';base=pathlib.Path('D:/GexResearchArtifacts/weekly_multiday_20261101')
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();code=week/'audit_weekly_context_q3.py'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==commit
assert subprocess.check_output(['git','ls-remote','origin','refs/heads/research/multiscale-v1r1-net-usd'],text=True).split()[0]==commit
assert sha(code)=='6c1a664772543c8972f61e3e910c561fa4b79f55e2bec9aa29190495aeebcbc6'
assert hashlib.sha256(subprocess.check_output(['git','show',commit+':'+code.relative_to(repo).as_posix()])).hexdigest()==sha(code)
obs=base/'h2_context_q3_audit_observer_01';assert not obs.exists()
helper=repo/'research_papers/JEPA/level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py';assert sha(helper)=='3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046'
spec=importlib.util.spec_from_file_location('gate',helper);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
psutil.Process().cpu_affinity([0])
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS']:os.environ[k]='1'
assert not (base/'h2_context_q3_1030_audit_01').exists()
assert sha(base/'h2_context_q3_extraction_observer_01/exit.json')=='aa606d58e4ec45441b3aa9fa647f9b21475ad43c461e624f1e38a29c8d588a9d'
assert json.loads((base/'h2_context_q3_extraction_observer_01/exit.json').read_text())['exit_code']==0
assert sha(base/'h2_context_q3_1030_01/manifest.json')=='1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66'
assert sha(base/'h2_context_q3_1030_01/inventory.json')=='25da3398984c633a044eef4f20c5525c6224a1b076a5941d0311fae93eab68cf'
binding=week/'Q3_CONTEXT_EXTRACTION_RESULT_AND_AUDIT_BINDING_20261101.md'
assert hashlib.sha256(subprocess.check_output(['git','show',commit+':'+binding.relative_to(repo).as_posix()])).hexdigest()==sha(binding)
assert sha(binding)=='42ef4af9b127040a2ea81945b74e3134f2d8bc1e535fe95c3e8f1acbb9453d04'
launcher=week/'launch_q3_context_audit_20261101.ps1'
assert hashlib.sha256(subprocess.check_output(['git','show',commit+':'+launcher.relative_to(repo).as_posix()])).hexdigest()==sha(launcher)
resources=m.observation();m.gate(resources)
args=[sys.executable,'-X','utf8','-u',str(code),'--execute-reviewed-audit','--producer-root',str(base/'h2_context_q3_1030_01'),'--producer-manifest-sha256','1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66','--inventory',str(base/'h2_context_q3_1030_01/inventory.json'),'--inventory-sha256','25da3398984c633a044eef4f20c5525c6224a1b076a5941d0311fae93eab68cf','--producer-sha256','caa049caccd79a1c344bee03cce70df7e6a4446fa1ab087c31de64692f78845a','--auditor-sha256','6c1a664772543c8972f61e3e910c561fa4b79f55e2bec9aa29190495aeebcbc6','--output-dir',str(base/'h2_context_q3_1030_audit_01')]
obs.mkdir(parents=True)
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
write(obs/'admission.json',dict(utc=now(),command=args,publication_commit=commit,code_sha256=sha(code),resources=resources,cpu_affinity=[0],threads=1))
start=time.monotonic()
with (obs/'stdout.log').open('wb') as stdout,(obs/'stderr.log').open('wb') as stderr:
 p=subprocess.Popen(args,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
 write(obs/'process.json',dict(pid=p.pid,creation_time=psutil.Process(p.pid).create_time(),utc=now(),command=args));result=p.wait()
write(obs/'exit.json',dict(exit_code=result,utc=now(),source='subprocess.Popen.wait_retained_handle',elapsed_seconds=time.monotonic()-start,files={str(obs/n):sha(obs/n) for n in ['admission.json','process.json','stdout.log','stderr.log']}))
print(json.dumps(dict(pid=p.pid,exit_code=result,observer=str(obs))))
if result:print((obs/'stderr.log').read_text(encoding='utf-8'))
sys.exit(result)
'@ | & 'C:/Program Files/Python314/python.exe' -X utf8 -u -
