"""Read-only metadata/pin verification; never imports or executes B06."""
import os
for key in ('ARROW_NUM_THREADS','BLIS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','NUMBA_NUM_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','POLARS_MAX_THREADS','TBB_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
    os.environ[key] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
import ctypes
k = ctypes.WinDLL('kernel32', use_last_error=True)
k.GetCurrentProcess.restype = ctypes.c_void_p
k.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
assert k.SetProcessAffinityMask(k.GetCurrentProcess(), 1)
import ast
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

WEEK = Path(__file__).resolve().parent.parent
REPO = WEEK.parents[2]
LAUNCHER = WEEK / 'launch_weekly_zone_event_value_paths_audit06_20261102.py'
HELPER = REPO / 'research_papers/JEPA/level_oracle_20261018/launch_monthly_test_index_v2_audit_20261024.py'
def pin(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'bytes': path.stat().st_size, 'sha256': digest}

assert pin(HELPER) == {'bytes':31463,'sha256':'3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046'}
# Exact official function ASTs, no launcher-module execution or side effects.
helper_tree = ast.parse(HELPER.read_text(encoding='utf-8-sig'))
helper_nodes = [node for node in helper_tree.body if isinstance(node, ast.FunctionDef) and node.name in ('require','observation','gate')]
assert len(helper_nodes) == 3
scope = {'ctypes':ctypes,'MIN_FREE':2_000_000_000}
exec(compile(ast.Module(body=helper_nodes,type_ignores=[]),str(HELPER),'exec'),scope)
resources = scope['observation']()
disk = shutil.disk_usage('D:/').free
resource_error = None
try:
    scope['gate'](resources)
    if disk < 2_000_000_000:
        raise ValueError('2GB disk gate unmet')
except ValueError as error:
    resource_error = str(error)

tree = ast.parse(LAUNCHER.read_text(encoding='utf-8-sig'))
assignments = {node.targets[0].id:node.value for node in tree.body if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)}
values = {'LAUNCHER':LAUNCHER}
def resolve(node):
    if isinstance(node,ast.Constant): return node.value
    if isinstance(node,ast.Name):
        if node.id not in values: values[node.id] = resolve(assignments[node.id])
        return values[node.id]
    if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div): return resolve(node.left)/resolve(node.right)
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='Path' and len(node.args)==1 and not node.keywords: return Path(resolve(node.args[0]))
    if isinstance(node,ast.Dict): return {resolve(a):resolve(b) for a,b in zip(node.keys,node.values)}
    raise ValueError(ast.dump(node))
maps = {name:resolve(assignments[name]) for name in ('REPO_PINS','REPO_BYTES','EXTERNAL_PINS','EXTERNAL_BYTES')}
differences = []
checked = {}
for group in ('REPO','EXTERNAL'):
    assert set(maps[group+'_PINS']) == set(maps[group+'_BYTES'])
    for path,digest in maps[group+'_PINS'].items():
        actual = pin(path)
        expected = {'bytes':maps[group+'_BYTES'][path],'sha256':digest}
        checked[str(path)] = actual
        if actual != expected: differences.append({'path':str(path),'expected':expected,'actual':actual})
stop = json.loads((WEEK/'PAUSA_20261102/stop_verification.json').read_text(encoding='utf-8-sig'))
for expected in stop['pins']+stop['foreign_files_preserved']:
    path = Path(expected['path'])
    actual = pin(path)
    checked[str(path)] = actual
    if actual['sha256'] != expected['sha256'] or ('bytes' in expected and actual['bytes'] != expected['bytes']):
        differences.append({'path':str(path),'expected':expected,'actual':actual})
archive = WEEK/'weekly_zone_event_value_path_v2r3_fixture_pass_archive_05'
manifest = json.loads((archive/'archive_manifest.json').read_text(encoding='utf-8-sig'))
archive_differences = []
for member in manifest['members']:
    for path,digest in ((Path(member['source_path']),member['source_sha256_after']),(archive/member['destination_relative'],member['copy_sha256'])):
        actual = pin(path)
        if actual != {'bytes':member['bytes'],'sha256':digest}: archive_differences.append({'path':str(path),'actual':actual})
roots = [{'path':str(resolve(assignments[name])),'exists':os.path.lexists(resolve(assignments[name]))} for name in ('OUTPUT','AUDIT_OBSERVER','OBSERVER')]
head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
publication = None
if '--publication' in sys.argv:
    branch = resolve(assignments['BRANCH'])
    remote = subprocess.check_output(['git','ls-remote','origin','refs/heads/'+branch],cwd=REPO,text=True).split()[0]
    assert remote == head
    publication_differences=[]
    for path in list(maps['REPO_PINS'])+[LAUNCHER]:
        content = subprocess.check_output(['git','show',head+':'+path.relative_to(REPO).as_posix()],cwd=REPO)
        if content != path.read_bytes(): publication_differences.append(str(path))
    publication={'head':head,'remote':remote,'checked_files':len(maps['REPO_PINS'])+1,'differences':publication_differences}
receipt={'observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'kind':'B06_RESUMPTION_METADATA_ONLY','script':pin(Path(__file__)),'helper':pin(HELPER),'official_functions_from_exact_ast':True,'resources':resources,'disk_free_bytes':disk,'resource_error':resource_error,'git_head':head,'repo_pins':len(maps['REPO_PINS']),'external_pins':len(maps['EXTERNAL_PINS']),'checked':checked,'pin_differences':differences,'fixture_archive_members':len(manifest['members']),'archive_differences':archive_differences,'runtime_roots':roots,'publication':publication,'scientific_execution':False,'suites_repeated':False}
destination=Path(sys.argv[1])
with destination.open('x',encoding='utf-8',newline='\n') as stream:
    json.dump(receipt,stream,ensure_ascii=False,indent=2)
    stream.write('\n')
print(json.dumps({key:value for key,value in receipt.items() if key!='checked'},ensure_ascii=False))
assert not differences and not archive_differences and not any(item['exists'] for item in roots)
if publication: assert not publication['differences']
