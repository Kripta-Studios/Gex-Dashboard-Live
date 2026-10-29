"""Independent static comparisons and compact author-evidence verification only."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import sys

code = Path(sys.argv[1]).resolve()
out = Path(__file__).parent
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def refcheck(ref):
    assert sha(ref['path']) == ref['sha256'], ref['path']
    return read(ref['path'])

old_name = 'launch_oof_economic_audit_v2r1_20261024.py'
new_name = 'launch_oof_economic_audit_user_stop_continuation_20261029.py'
old_tree, new_tree = [ast.parse((code/n).read_text(encoding='utf-8')) for n in (old_name, new_name)]
old = {n.name: n for n in old_tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
new = {n.name: n for n in new_tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
unchanged = [n for n in old.keys() & new.keys() if ast.dump(old[n]) == ast.dump(new[n])]
assert set(unchanged) == {'require','sha','digest','utc','stamp','disjoint','read','verify','Evidence','publication','command','destinations','observation','gate','lock','publish','RetainedProcess','drain','validate_audit','main'}
old_tail = copy.deepcopy(old['upstream'].body)
start = next(i for i,n in enumerate(old_tail) if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id == 'pipeline')
old_tail = old_tail[start:]
class NormalizeClosure(ast.NodeTransformer):
    def visit_Subscript(self, node):
        if ast.dump(node) == ast.dump(ast.parse('finished["pipeline_closure"]', mode='eval').body):
            return ast.Name(id='closure', ctx=ast.Load())
        return self.generic_visit(node)
old_tail = [NormalizeClosure().visit(n) for n in old_tail]
new_tail = copy.deepcopy(new['validate_closed_pipeline'].body[1:])
assert ast.unparse(new['validate_closed_pipeline'].body[0]) == "source_sha = refs['pipeline_request']['sha256']"
extra = [n for n in new_tail if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='validate_phase_lifetimes']
assert len(extra) == 1
new_tail = [n for n in new_tail if n not in extra]
dump_old = ast.dump(ast.Module(body=old_tail,type_ignores=[]))
dump_new = ast.dump(ast.Module(body=new_tail,type_ignores=[]))
assert dump_old == dump_new

report = read(code/'OOF_ECONOMIC_AUDIT_USER_STOP_IMPLEMENTATION_RESULT_20261029.json')
for name,pin in report['files'].items(): assert sha(code/name)==pin
invariance = refcheck(report['invariance'])
for name,pin in invariance['frozen_pins'].items(): assert sha(code/name)==pin
manifest = refcheck(report['archive_manifest'])
for pair in manifest['copies']:
    assert sha(pair['original']) == sha(pair['copy']) == pair['sha256']
    assert Path(pair['original']).stat().st_size == Path(pair['copy']).stat().st_size == pair['size']
assert len(manifest['copies']) == manifest['files']
attempts=[]
for attempt in report['attempts']:
    result = refcheck(attempt['receipt'])
    assert result['exit_code']==attempt['exit_code']
    for p,pin in result['logs'].items(): assert sha(p)==pin
    attempts.append({'attempt':attempt['attempt'],'exit_code':result['exit_code'],'passed':attempt['passed'],'failed':attempt['failed']})
final = refcheck(report['attempts'][-1]['receipt'])
assert '53 passed' in Path(next(p for p in final['logs'] if p.endswith('stdout.log'))).read_text(encoding='utf-8')
cpu = refcheck(report['cpu0_inheritance_test']['evidence'])
assert cpu['exit_code']==0 and cpu['parent']['parent_cpu_affinity']==[0] and cpu['child_observation']==dict(mask=1,threads=['1','1','1'])
assert cpu['code_sha256']==report['files'][new_name]
assert cpu['tests_sha256']==report['files']['test_launch_oof_economic_audit_user_stop_continuation_20261029.py']
authorroot=Path(manifest['copies'][0]['original']).parents[1]
for name,field in [('cpu_probe_01.py','probe_sha256'),('cpu_probe_01.stdout.log','stdout_sha256'),('cpu_probe_01.stderr.log','stderr_sha256')]:
    assert sha(authorroot/name)==cpu[field]
assert json.loads((authorroot/'cpu_probe_01.stdout.log').read_text(encoding='utf-8'))==cpu['child_observation']
assert not (authorroot/'cpu_probe_01.stderr.log').read_bytes()
probe=(authorroot/'cpu_probe_01.py').read_text(encoding='utf-8')
assert 'GetProcessAffinityMask' in probe and 'GetCurrentProcess.restype=ctypes.c_void_p' in probe
assert 'cpu_affinity(' not in probe

# Read metadata review document without invoking admission or hashing its payloads.
prefix = read(code/'OOF_INTERRUPTION_INDEPENDENT_REVIEW_20261029.json')
assert prefix['schema']=='INDEPENDENT_METADATA_HASH_REVIEW_V1'
assert prefix['status']=='PASS_STOPPED_PREFIX_METADATA_AND_HASHES_ONLY' and prefix['failed_checks']==0
assert prefix['adoption_authorized_by_this_review'] is False and prefix['audit_full_h1_performed'] is False
assert len(prefix['reviewed_phases'])==8
assert prefix['original_exit_code']==15 and prefix['original_failure_preserved'] is True
for i,part in enumerate(prefix['reviewed_phases']):
    assert part['index']==i
    assert [part['month'],part['stage']]==[f'2026{i//2+1:02d}',('correction','replay')[i%2]]
    for k in ('start_sha256','receipt_sha256','completion_sha256'): assert len(part[k])==64

result=dict(status='PASS_INDEPENDENT_STATIC_AND_COMPACT_EVIDENCE_REVIEW', source_files={n:sha(code/n) for n in (old_name,new_name,'test_launch_oof_economic_audit_user_stop_continuation_20261029.py')}, unchanged_ast_nodes=sorted(unchanged), scientific_validation_tail_identical=True, normalized_tail_ast_sha256=hashlib.sha256(dump_old.encode()).hexdigest(), normalization='finished.pipeline_closure renamed closure; leading source_sha assignment and one new lifetime-validator call excluded.', frozen_pins=invariance['frozen_pins'], author_archive_pairs_verified=len(manifest['copies']), author_archive_bytes_verified=sum(p['size'] for p in manifest['copies']), author_attempts=attempts, cpu_evidence_externally_verified=report['cpu0_inheritance_test'], actual_prefix_review_schema_compatible=True, prefix_admission_executed=False, real_payloads_rehashed=False, scientific_execution=False)
target=out/'static_verification_01.json'
with target.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2)
print(json.dumps(result,indent=2))
