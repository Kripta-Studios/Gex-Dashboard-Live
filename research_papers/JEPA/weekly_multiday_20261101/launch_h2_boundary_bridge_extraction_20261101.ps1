@'
import hashlib, importlib.util, json, os, pathlib, subprocess, sys, time
from datetime import datetime, timezone
import psutil
repo=pathlib.Path.cwd();week=repo/'research_papers/JEPA/weekly_multiday_20261101';base=pathlib.Path('D:/GexResearchArtifacts/weekly_multiday_20261101')
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert subprocess.check_output(['git','ls-remote','origin','refs/heads/research/multiscale-v1r1-net-usd'],text=True).split()[0]==commit
pins={
 'build_weekly_h2_boundary_bridge.py':'29d8e7906f0f594ed469b07bb8134a500d26cc01434a77928a09b8a8c90bedb2',
 'test_build_weekly_h2_boundary_bridge.py':'a3655cda635544cd87d2cb8d1535e2369e10470a4a2651a5c67ba9635c57cc30',
 'H2_JUNE_JULY_BRIDGE_CONTRACT_20261101.md':'fe506ec96812ea582f11d0bc23497c34e51e878ae912ccc76fcc8924c30cda55',
 'H2_BOUNDARY_BRIDGE_BUILDER_REVIEW_20261101.md':'eda3723d54252429539a3046a88e888302b02142e952eea84de4be1514f41753',
 'H2_BOUNDARY_BRIDGE_METADATA_BINDING_20261101.md':'bf250bf5ae5beb6ac91332f0136cb470ccf860880d63ab315104ee16e6e7079d',
 'H2_BOUNDARY_BRIDGE_INVENTORY_CLOSURE_AND_EXTRACTION_BINDING_20261101.md':'069c98f5bc2b0a8077e8bb86c3ca0693ba84abd319204b3eef87bd98b209d141',
 'H2_BOUNDARY_BRIDGE_INVENTORY_REVIEW_20261101.md':'84af8d27b3b1db01005b2137f7c07c1363e243d081371a43d225c9300408f33e',
 'h2_boundary_bridge_inventory_archive_01/archive_receipt.json':'2f0e9d38d7050c9da9fd9b53677075ad5bffa36e7b09e6eb86364c62700479ff',
 'h2_boundary_bridge_builder_evidence_01/archive_receipt.json':'8395304998df6a1362982ad53c0f4e9e3a2830558c7c913f73be77b4499eecf3',
}
for name,expected in pins.items():assert sha(week/name)==expected,name
for name in [*pins,'launch_h2_boundary_bridge_extraction_20261101.ps1']:
 f=week/name
 assert hashlib.sha256(subprocess.check_output(['git','show',commit+':'+f.relative_to(repo).as_posix()])).hexdigest()==sha(f),name
helper=repo/'research_papers/JEPA/level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py'
assert sha(helper)=='3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046'
spec=importlib.util.spec_from_file_location('resource_gate',helper);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
psutil.Process().cpu_affinity([0])
keys=['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS','ARROW_NUM_THREADS','POLARS_MAX_THREADS']
for k in keys:os.environ[k]='1'
obs=base/'h2_boundary_bridge_extraction_observer_01'
assert not obs.exists()
root=base/'h2_boundary_bridge_01'
assert {p.name for p in root.iterdir()}=={'inventory.json','inventory_manifest.json','unified_calendar.json'}
for name,h in [('inventory.json','599ca400fecae12ce4098187a45af3ee0cf8c1b070e060d8c84e422ce92c6161'),('inventory_manifest.json','0a7a5fab0f932d23fdf9a3140027f99eb85ccd958b79ef55152c53ab5ced70f2'),('unified_calendar.json','be622bb24aca35448594743dfeb5236e6b2d08a4410109b20302891f8c1fa7d6')]:assert sha(root/name)==h
upstream=base/'h2_boundary_bridge_inventory_observer_01'/'exit.json'
assert sha(upstream)=='fcf157b50124c40840db9033ec01539abeb2641064bbfb7bee9ab801ff7b183b'
assert json.loads(upstream.read_text())['exit_code']==0
resources=m.observation();m.gate(resources)
code=week/'build_weekly_h2_boundary_bridge.py'
args=[sys.executable,'-X','utf8','-u',str(code),'--execute-reviewed-bridge','--inventory',str(root/'inventory.json'),'--inventory-sha256','599ca400fecae12ce4098187a45af3ee0cf8c1b070e060d8c84e422ce92c6161','--wrapper-sha256',pins[code.name]]
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
