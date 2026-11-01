@'
import hashlib, importlib.util, json, os, pathlib, subprocess, sys, time
from datetime import datetime,timezone
import psutil
repo=pathlib.Path.cwd();week=repo/'research_papers/JEPA/weekly_multiday_20261101';base=pathlib.Path('D:/GexResearchArtifacts/weekly_multiday_20261101')
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();code=week/'score_weekly_context_q3_frozen.py'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==commit
assert subprocess.check_output(['git','ls-remote','origin','refs/heads/research/multiscale-v1r1-net-usd'],text=True).split()[0]==commit
assert sha(code)=='e7638731fbba44ca45ff0f69418428083226b0f44110819f0ab52e13d3ff1e75'
assert hashlib.sha256(subprocess.check_output(['git','show',commit+':'+code.relative_to(repo).as_posix()])).hexdigest()==sha(code)
obs=base/'h2_context_q3_scoring_observer_01';assert not obs.exists()
helper=repo/'research_papers/JEPA/level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py';assert sha(helper)=='3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046'
spec=importlib.util.spec_from_file_location('gate',helper);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
psutil.Process().cpu_affinity([0])
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS']:os.environ[k]='1'
assert not (base/'h2_context_model_comparison_q3_01').exists()
for rel,h in [('h2_context_q3_audit_observer_01/exit.json','cfc953316b4c2d47d15e8a90a9d6f166238812e82e14b8b8909229c4cf8bc6bd'),('h2_context_q3_1030_01/manifest.json','1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66'),('h2_context_q3_1030_audit_01/audit.json','ae90d005b6fa9a3a1a708fdfafd3361bdef9146312ddda324d103a139cd18633'),('h2_context_q3_1030_audit_01/manifest.json','992c05306cb22a2869ddd0185fbebd8e04d2f049ad15940ab15de11c0bb234d7')]:assert sha(base/rel)==h
assert json.loads((base/'h2_context_q3_audit_observer_01/exit.json').read_text())['exit_code']==0
audit=json.loads((base/'h2_context_q3_1030_audit_01/audit.json').read_text())
assert audit['status']=='PASS_INDEPENDENT_CONTEXT_Q3_1030_GIVEN_FROZEN_FUNCTIONS'
assert audit['schema']=='weekly_context_q3_1030_independent_audit_v1'
assert audit['inputs']['producer_manifest']=={'path':str(base/'h2_context_q3_1030_01/manifest.json'),'bytes':172889,'sha256':'1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66'}
assert all(audit['flags'][k] is False for k in ['fit_performed','models_fit','outcomes_read','promotion_approved'])
binding=week/'Q3_CONTEXT_AUDIT_RESULT_AND_SCORING_BINDING_20261101.md'
assert sha(binding)=='702ccded6d78dcfaf8f5d15e346bcb762538d69f77df352d0db192da80e5adac'
for f in [binding,week/'launch_q3_context_scoring_20261101.ps1']:
 assert hashlib.sha256(subprocess.check_output(['git','show',commit+':'+f.relative_to(repo).as_posix()])).hexdigest()==sha(f)
resources=m.observation();m.gate(resources)
args=[sys.executable,'-X','utf8','-u',str(code),'--execute-reviewed-scoring','--context-manifest-sha256','1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66','--context-audit-sha256','ae90d005b6fa9a3a1a708fdfafd3361bdef9146312ddda324d103a139cd18633','--scorer-sha256','e7638731fbba44ca45ff0f69418428083226b0f44110819f0ab52e13d3ff1e75','--output-dir',str(base/'h2_context_model_comparison_q3_01')]
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
