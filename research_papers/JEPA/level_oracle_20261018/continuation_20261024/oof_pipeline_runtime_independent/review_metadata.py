from pathlib import Path
from datetime import datetime,timezone,timedelta
import ast,hashlib,json,math,subprocess,sys
ROOT=Path(__file__).resolve().parent
REPO=Path(r'C:/Users/Álvaro Schwiedop/Desktop/KriptaStudios/Gex-Dashboard-Live')
CODE=REPO/'research_papers/JEPA/level_oracle_20261018'
BASE=Path('D:/GexResearchArtifacts/level_oracle_20261018')
REQUEST=CODE/'OOF_PIPELINE_RUNTIME_REQUEST_20261024_01.json'
BINDING=CODE/'OOF_PIPELINE_LAUNCH_RUNTIME_BINDING_20261024_01.json'
checks=[]; hashed={}
def check(condition,name):
    if not condition:raise AssertionError(name)
    checks.append(name)
def sha(path):
    p=Path(path)
    with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
    hashed[str(p)]=h
    return h
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def pin(path,expected):
    h=sha(path)
    if h!=expected:raise AssertionError('SHA mismatch: '+str(path))
    return h
def safe(value):
    p=Path(value)
    assert p.is_absolute() and '..' not in p.parts and p!=Path(p.anchor)
    assert all(not x.is_symlink() and not x.is_junction() for x in (p,*p.parents))
    assert str(p.resolve())==str(p)
    return p
request_sha,binding_sha=sys.argv[1:3]
pin(REQUEST,request_sha);pin(BINDING,binding_sha)
r,b=read(REQUEST),read(BINDING)
review=CODE/'OOF_PIPELINE_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json'
pin(review,'a78c2ef9019111a1ca98fa6e2517a4db8ce1ef9877596e5807734ce4c843ec95');iv=read(review)
check(iv['decision']=='CLEAR' and iv['scope']=='IMPLEMENTATION_ONLY' and iv['runtime_authorized'] is False,'Frozen implementation review exact and scope limited')
files=iv['files'];check(len(files)==48,'Exact 48 implementation members')
for n,h in files.items():pin(CODE/n,h)
deps=iv['dependency_sets']['oof_request']
check(len(deps)==17 and r['code']==deps,'Request exact 17 frozen dependencies')
for category,count in [('monthly_auditor',13),('original_scientific',11)]:
    group=iv['dependency_sets'][category]
    check(len(group)==count and all(files[n]==h for n,h in group.items()),category+' pins exact')
check(r['version']=='OOF_PIPELINE_RUNTIME_REQUEST_V1' and r['status']=='REVIEWED_OOF_PIPELINE_RUNTIME_REQUEST' and r['runtime_authorized'] is True,'Request contract status/authorization exact')
months=[f'2026{m:02d}' for m in range(1,7)]
check(r['months']==months and set(r['evaluation_roots'])==set(months),'All six fixed months present without selection')
check(b['status']=='PASS_OOF_PIPELINE_LAUNCH_RUNTIME_BINDING','Operational binding status exact')
check(b['request']==dict(path=str(REQUEST),sha256=request_sha) and b['implementation_review']==dict(path=str(review),sha256=hashed[str(review)]),'External request and implementation review references exact')
check(safe(r['coordination_lock'])==BASE/'oof_pipeline_runtime.lock','Frozen global child lock')
check(safe(r['monthly_root'])==BASE/'monthly_walk_forward_v1' and safe(r['session_root'])==BASE/'session_clock_dataset_v1','Fixed monthly/session sources')
allowed=[safe(x) for x in b['allowed_read_roots']]
expected_allowed=[CODE,BASE/'monthly_walk_forward_v1',BASE/'session_clock_dataset_v1',BASE/'session_clock_dataset_v1_audit',BASE/'monthly_walk_forward_validation_audit_20261024_02',BASE/'monthly_walk_forward_test_audit_20261024_01',BASE/'monthly_test_index_v2_audit_launch_20261024_01']
check(allowed==expected_allowed and len(set(allowed))==7,'Seven bounded metadata read roots exact')
outputs=[safe(r['pipeline_root']),safe(r['correction_root'])]+[safe(r['evaluation_roots'][m]) for m in months]+[safe(b['logs_root'])]
check(len(set(outputs))==9 and all(not p.exists() for p in outputs),'Nine distinct fresh output/log roots absent')
protected=allowed+[BASE/'engine_v1',BASE/'features_v1',BASE/'oof_pipeline_runtime.lock',BASE/'oof_pipeline_launch.lock']
check(all(not p.is_relative_to(q) and not q.is_relative_to(p) for i,p in enumerate(outputs) for q in outputs[i+1:]+protected),'Outputs disjoint from each other, all sources, code and locks')
authority_names=['OOF_PIPELINE_RUNTIME_IMPLEMENTATION_REVIEW_20261023.json','MONTHLY_TEST_INDEX_AUDIT_V2_REVIEW_20261024.json','MONTHLY_TEST_RESOURCE_OVERLAY_REVIEW_20261023.json','MONTHLY_TEST_INDEX_V2_AUDIT_RUNTIME_REVIEW_20261024_01.json','MONTHLY_TEST_INDEX_V2_AUDIT_LAUNCH_REVIEW_20261024.json']
expected_published={str(CODE/n):h for n,h in files.items()}
expected_published.update({str(CODE/n):pin(CODE/n,iv['authorities'][n]) for n in authority_names})
expected_published.update({str(REQUEST):request_sha,str(review):hashed[str(review)]})
check(b['published_files']==expected_published and len(expected_published)==55,'Exact 55 publication members, request included and binding external')
codecommit='dd18764dc1537092bde947060f704c2b97651989'
for path,h in expected_published.items():
    pin(path,h)
    if path==str(REQUEST):continue
    relative=Path(path).relative_to(REPO).as_posix()
    blob=subprocess.run(['git','show',codecommit+':'+relative],cwd=REPO,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
    assert hashlib.sha256(blob).hexdigest()==h,path
check(True,'54 pre-existing publication members match exact local Git commit objects; new request/binding publication pending')
u=b['upstream']; logs=BASE/'monthly_test_index_v2_audit_launch_20261024_01';out=BASE/'monthly_walk_forward_test_audit_20261024_01'
paths=dict(preflight=logs/'preflight.json',process=logs/'process.json',exit=logs/'exit.json',completion=logs/'completion.json',audit_launch=out/'launch.json',audit=out/'audit.json')
check(set(u)==set(paths),'Exact six upstream authority members')
values={}
for n,p in paths.items():
    assert u[n]['path']==str(p)
    pin(p,u[n]['sha256']);values[n]=read(p)
check(u['audit']['sha256']=='87bfea586be13e02fd7fd0fe59c819195c62a430f34c867f9ec661812569fd4e' and u['exit']['sha256']=='f7fadc58144d9934f38e2f3af81355b322ac45b36430742fbd42230d704cc259' and u['completion']['sha256']=='1045866ea9fdf7d926a51a221e9e5f453ead5146d835197ec99fabe3466b0165','Actual audit, retained exit and supervisor closure external hashes exact')
pre,proc,exit,complete,audit,launch=[values[n] for n in ['preflight','process','exit','completion','audit','audit_launch']]
check(not (logs/'failure.json').exists() and not (out/'failure.json').exists(),'No upstream failure artifacts')
check(complete['closure_files']=={str(paths[n]):u[n]['sha256'] for n in paths if n!='completion'},'Supervisor closure exactly links five observed files')
check(type(exit['exit_code']) is int and type(complete['exit_code']) is int and exit['exit_code']==complete['exit_code']==0,'Real exit and supervisor completion require integer zero')
check(proc['status']=='PROCESS_HANDLE_RETAINED' and exit['status']=='PROCESS_EXIT_OBSERVED_BY_RETAINED_HANDLE' and complete['status']=='COMPLETE_MONTHLY_TEST_INDEX_V2_AUDIT_SUPERVISION','Retained process and supervisor statuses exact')
check(proc['pid']==exit['pid']==49820 and type(proc['pid']) is int and type(exit['pid']) is int and proc['creation_time']==exit['creation_time']==1792812892.486885,'Actual PID and creation identity exact')
check(proc['creation_time_source']=='GetProcessTimes_retained_Popen_handle' and exit['exit_code_source']=='GetExitCodeProcess_retained_Popen_handle' and exit['process_receipt_sha256']==u['process']['sha256'],'Retained-handle observation sources and process hash exact')
expected_identity=dict(monitor_code_sha256='3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046',runtime_review_sha256='055d2734469a77dc607585d000f594ed3088580400c46f513c209119a793eab1',supervisor_review_sha256='e38ae0fb7ebfc3d5841fe87052d00605f58cba21a8ba987341d0f307ede9e432',publication_commit='03f8a4876f59e5913f2caacf456795bca44b3402',preflight_sha256=u['preflight']['sha256'])
check(all(x[k]==v for x in [proc,exit] for k,v in expected_identity.items()),'Process and exit preserve code/runtime/review/commit/original preflight identity')
check(all(complete[k]==expected_identity[k] for k in ['runtime_review_sha256','supervisor_review_sha256','publication_commit']),'Completion authorities match retained chain')
check(pre['status']=='PASS_AUDIT_SUPERVISOR_PREFLIGHT_NOT_EXECUTED' and pre['command']==proc['command'],'Preflight and retained process command match')
command=[sys.executable,'-u',str(CODE/'audit_monthly_walk_forward_test_index_v2.py'),'--monthly-root',str(BASE/'monthly_walk_forward_v1'),'--source-audit',str(BASE/'session_clock_dataset_v1_audit/audit.json'),'--validation-audit',str(BASE/'monthly_walk_forward_validation_audit_20261024_02/audit.json'),'--expected-validation-audit-sha256','ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc','--implementation-review',str(CODE/'MONTHLY_TEST_INDEX_AUDIT_V2_REVIEW_20261024.json'),'--runtime-review',str(CODE/'MONTHLY_TEST_INDEX_V2_AUDIT_RUNTIME_REVIEW_20261024_01.json'),'--output',str(out)]
check(pre['command']==command,'Upstream exact scientific command with seven fixed arguments')
times=[datetime.fromisoformat(t) for t in [proc['monitor_started_utc'],exit['observed_utc'],complete['completed_utc']]]
check(all(t.tzinfo is not None and t.utcoffset()==timedelta(0) for t in times) and times==sorted(times),'UTC-aware process-exit-supervisor completion chronology')
check(r['monthly_audit']==u['audit'] and complete['audit_path']==str(paths['audit']) and complete['audit_sha256']==u['audit']['sha256'],'Request monthly audit is exact supervised artifact')
check(audit['status']=='PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES' and audit['scope']==launch['scope']=='VALIDATION_2025_PLUS_DEVELOPMENT_TEST_2026H1','Composite given-sealed-scores audit status/scope')
expected_months=[f'2025{m:02d}' for m in range(1,13)]+months
check(audit['binding']['completed_months']==expected_months,'Composite exact eighteen months')
audited=audit['audited'];counts={'new_months':6,'new_unique_fit_windows':12,'models_used_test':13,'total_unique_fit_windows':36,'calendar_ticker_days':369,'available_ticker_days':363,'missing_no_evaluable':6}
check(all(type(audited[k]) is int and audited[k]==v for k,v in counts.items()),'Composite counts 6/12/13/36 and 369/363/6 exact')
check(audited['modes']==['static','expanding','rolling12'] and audited['selected_mode'] is None and audited['selection_reused_without_test_reselection'] is True,'Three modes preserved, null selected policy, no test reselection')
check(audited['missing_identities']==[[t,d] for t in ['QQQ','SPY'] for d in ['20260401','20260409','20260415']],'Six NO_EVALUABLE ticker-days retained')
check(audit['development_seen'] is True and audit['promotion_approved'] is False,'Development-seen and no promotion flags preserved')
check(pre['dependencies']==launch['dependencies']==iv['dependency_sets']['monthly_auditor'],'Thirteen dependency maps agree with frozen independent review')
snapshots=audit['execution_snapshots'];check(len(snapshots)==15 and snapshots==launch['snapshots'],'Exactly fifteen launch/audit snapshots')
expected_snaps={str(out/'executed_code'/n):h for n,h in pre['dependencies'].items()}
expected_snaps.update({str(out/'authorities/implementation_review.json'):iv['authorities']['MONTHLY_TEST_INDEX_AUDIT_V2_REVIEW_20261024.json'],str(out/'authorities/runtime_review.json'):expected_identity['runtime_review_sha256']})
check(snapshots==expected_snaps,'Snapshot membership is thirteen code/contract plus two authorities')
for p,h in snapshots.items():pin(p,h)
check(True,'All fifteen compact snapshots rehashed')
prior=audit['prior_validation_audit'];priorpath=BASE/'monthly_walk_forward_validation_audit_20261024_02/audit.json'
check(prior==dict(path=str(priorpath),sha256='ba9fbd9edf849eb823f098461906feede9782b1e513f4d1954e6d58f52549cbc',scope='VALIDATION_2025',inventory_rehashed=True,reconstruction_inherited_not_repeated=True),'Exact prior 2025 audit inheritance contract')
pin(priorpath,prior['sha256']);pa=read(priorpath)
flat=lambda inv:{p:h for group in inv.values() for p,h in group.items()}
previous,current=flat(pa['verified_files']),flat(audit['verified_files'])
check(all(current.get(p)==h for p,h in previous.items()),'Prior validation inventory hashes preserved as metadata; payloads not rehashed')
sessionpath=Path(r['session_audit']['path']);pin(sessionpath,r['session_audit']['sha256']);session=read(sessionpath)
check(session['status']=='PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT' and session['binding']['engine_root']==r['session_root'] and session['binding']['index_sha256']==audit['binding']['index_sha256'],'Session authority status/root/index consistent')
check(audit['binding']['monthly_root']==r['monthly_root'] and audit['binding']['session_root']==r['session_root'] and audit['binding']['session_audit_sha256']==r['session_audit']['sha256'],'Composite source roots and session SHA match request')
pin(Path(r['monthly_root'])/'run_contract.json',audit['binding']['run_contract_sha256'])
pin(Path(r['session_root'])/'index.parquet',audit['binding']['index_sha256'])
check(True,'Current run contract and metadata index bytes rehashed; no arrays parsed')
check(all(any(safe(p).is_relative_to(root) for root in allowed) for p in hashed),'Every consumed metadata/code path fits allowed read roots')
check(all(not p.exists() for p in outputs),'Nine outputs still absent at review close')
pin(REQUEST,request_sha);pin(BINDING,binding_sha)
result=dict(status='PASS_INDEPENDENT_OOF_RUNTIME_METADATA_CHECKS',scope='METADATA_AND_BINDINGS_ONLY',request=dict(path=str(REQUEST),sha256=request_sha),binding=dict(path=str(BINDING),sha256=binding_sha),checked_utc=datetime.now(timezone.utc).isoformat(),checks=checks,checks_count=len(checks),compact_files_rehashed=hashed,compact_files_count=len(hashed),publication=dict(existing_code_commit=codecommit,existing_git_objects_verified=54,new_request_binding_publication_pending=True,remote_publication_checked=False),outputs=[str(x) for x in outputs],upstream_metadata=dict(pid=proc['pid'],creation_time=proc['creation_time'],monitor_started_utc=proc['monitor_started_utc'],exit_observed_utc=exit['observed_utc'],supervisor_completed_utc=complete['completed_utc'],exit_code=0),prior_inventory_members=len(previous),composite_inventory_members=len(current),preflight_executed=False,MonthlyInputs_instantiated=False,market_arrays_parsed=False,economic_metrics_opened=False,scientific_payloads_rehashed=False)
(ROOT/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['status','checks_count','compact_files_count','prior_inventory_members','composite_inventory_members','publication']},indent=2))
