"""Verify final implementation-only map; never call runtime/source admissions."""
from pathlib import Path
import hashlib
import importlib
import json
import sys

code = Path(sys.argv[1]).resolve()
out = Path(__file__).parent
sys.path.insert(0, str(code))
s = importlib.import_module('launch_oof_economic_audit_user_stop_continuation_20261029')
evidence = s.Evidence([code])
files = s.review_files(evidence)
producer = s.read(code/s.CONTINUATION_REVIEW)
assert producer['decision']=='CLEAR' and producer['runtime_authorized'] is False
assert len(producer['files']) == 60
assert producer['files'][s.CONTINUATION_CODE]=='599f6d5c347ebdc3801bbe8cc21de55603a80a46858a8bad1d20729d307eee11'
assert producer['files'][s.CONTINUATION_TEST]=='e1dc93402ee08eb53e1aaae850efc9b789f0d68fc2ddf05639a285a199471b2b'
s.verify(evidence.files)
ref = producer['cpu0_inheritance_test']['evidence']
cpu = evidence.ref(ref)
assert cpu['child_exit_code']==0 and cpu['win32_api_succeeded'] is True
assert cpu['child_observation']==dict(mask=1,threads=['1','1','1'])
result=dict(status='PASS_EXACT_FINAL_IMPLEMENTATION_REVIEW_FILES_MAP', scope='IMPLEMENTATION_ONLY', runtime_authorized=False, files=files, files_count=len(files), verified_compact_files=evidence.files, producer_review=dict(path=str(code/s.CONTINUATION_REVIEW),sha256=s.sha(code/s.CONTINUATION_REVIEW)), producer_cpu_evidence=producer['cpu0_inheritance_test'], source_admission_executed=False, real_preflight_executed=False, scientific_execution=False)
with (out/'final_map_01.json').open('x',encoding='utf-8') as f: json.dump(result,f,indent=2)
print(json.dumps({'status':result['status'],'files_count':len(files),'producer_review':result['producer_review'],'output_sha256':s.sha(out/'final_map_01.json')},indent=2))
