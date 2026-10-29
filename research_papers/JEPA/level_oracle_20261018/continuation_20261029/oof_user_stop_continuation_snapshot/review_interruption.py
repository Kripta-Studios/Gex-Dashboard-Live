"""Independent stopped-prefix metadata/hash review. Never imports producers."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

B = Path('D:/GexResearchArtifacts/level_oracle_20261018')
R = Path.cwd() / 'research_papers/JEPA/level_oracle_20261018'
OUT = Path(__file__).parent
P = B / 'oof_pipeline_runtime_20261024_v2r1_01'
L = B / 'oof_pipeline_launch_20261024_v2r1_01'
O = B / 'oof_pipeline_v2r1_observer_20261024_01'
REQUEST_SHA = '37f2018c7145d3b82cba2e34fbff9ae3008e33f32b004c5580e433157f38ef15'
BINDING_SHA = '9e4949227dfd8b0aa3e72a35271b081413dbd9dee482b79c98911ea25478813c'
ADMISSION_SHA = 'ec2f728baf2ab28adaaf3855847d74bf6354ac587d440afb83b50278e5ca3234'
ADAPTER_NAMES = {
    'monthly_oof_calibration_adapter.py', 'oof_maximum_calibration.py',
    'rolling_monthly_schedule.py', 'MONTHLY_OOF_CALIBRATION_ADAPTER_SPEC.md',
    'PREQUENTIAL_MAX_CALIBRATION_DESIGN.md', 'OOF_MAXIMUM_CALIBRATION_INTEGRATION.md',
}
REPLAY_NAMES = ADAPTER_NAMES | {'evaluate_oof_calibrated_policy.py', 'OOF_CALIBRATED_POLICY_EVALUATION_SPEC.md'}
checks = []
pins = {}
origins = {}
loaded = {}
observed_hashes = {}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check(label, condition, detail=None):
    checks.append(dict(check=label, passed=bool(condition), detail=detail))
    if not condition:
        raise ValueError(label + ': ' + repr(detail))


def declare(path, expected, origin):
    name = str(Path(path).resolve())
    check('nonconflicting pin', name not in pins or pins[name] == expected, name)
    pins[name] = expected
    origins.setdefault(name, set()).add(origin)


def load(path, expected=None):
    path = Path(path)
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if expected is not None:
        check('compact metadata expected hash', actual == expected, str(path))
    declare(path, actual, 'compact_metadata')
    result = json.loads(raw.decode('utf-8'))
    loaded[str(path.resolve())] = actual
    return result


def add_map(mapping, origin):
    check('map is object', isinstance(mapping, dict), origin)
    for path, expected in mapping.items():
        declare(path, expected, origin)


def tree(root, root_lock=False):
    root = Path(root)
    result = set()
    if not root.exists():
        return result
    for path in root.rglob('*'):
        s = path.lstat()
        check('tree no symlink or reparse', not path.is_symlink() and not (getattr(s, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT), str(path))
        check('tree stays inside root', path.resolve().is_relative_to(root.resolve()), str(path))
        if path.is_file():
            if root_lock and path.name == '.lock' and path.parent == root:
                continue
            check('no partial file', not path.name.endswith('.partial'), str(path))
            result.add(str(path.resolve()))
    return result


def main():
    started = datetime.now(timezone.utc).isoformat()
    request_path = R / 'OOF_PIPELINE_V2R1_RUNTIME_REQUEST_20261024_01.json'
    request = load(request_path, REQUEST_SHA)
    check('stored exact request', load(P / 'request.json', REQUEST_SHA) == request)
    C = Path(request['correction_root'])
    evaluations = {month: Path(path) for month, path in request['evaluation_roots'].items()}
    adapter = {name: request['code'][name] for name in ADAPTER_NAMES}
    replay = {name: request['code'][name] for name in REPLAY_NAMES}
    for name, expected in request['code'].items():
        declare(R / name, expected, 'request_code')
    check('contract identity', load(P / 'contract.json') == {
        'version': 'OOF_PIPELINE_V2R1', 'request_sha256': REQUEST_SHA,
        'code': request['code'], 'correction_layout': 'SHARED_CUMULATIVE',
        'source_admission_sha256': ADMISSION_SHA,
    })
    preflight = load(L / 'preflight.json')
    process = load(L / 'process.json')
    exited = load(L / 'exit.json')
    failure = load(L / 'failure.json')
    stop = load(O / 'user_stop.json')
    post_stop = load(O / 'post_stop_verification.json')
    admission = load(L / 'admission.json')
    load(R / 'OOF_PIPELINE_V2R1_LAUNCH_RUNTIME_BINDING_20261024_01.json', BINDING_SHA)
    add_map(preflight['files'], 'preflight_files')
    add_map(preflight['publication_files'], 'preflight_publication_files')
    check('preflight declared dependency map', preflight['dependencies'] == request['code'])
    check('preflight admission digest', preflight['source_admission_sha256'] == ADMISSION_SHA)
    check('supervisor process and exit pins', all(
        doc['request_sha256'] == REQUEST_SHA and doc['runtime_binding_sha256'] == BINDING_SHA
        and doc['preflight_sha256'] == sha(L / 'preflight.json') for doc in (process, exited)))
    check('retained process and exit identity', exited['pid'] == process['pid'] == 28256
          and exited['creation_time'] == process['creation_time']
          and exited['process_receipt_sha256'] == sha(L / 'process.json')
          and exited['exit_code_source'] == 'GetExitCodeProcess_retained_Popen_handle'
          and exited['exit_code'] == 15 and exited['retry'] is False)
    check('original failure retained', failure['status'] == 'FAILED_OR_INTERRUPTED_PRESERVED'
          and failure['retry'] is False and failure['error'] == "ValueError('OOF child must exit zero')")
    check('stop identity matches retained process', any(
        row['pid'] == process['pid'] and abs(row['creation'] - process['creation_time']) < 0.000001
        and row['command'] == process['command'] for row in stop['identities_before_stop']))
    check('explicit stop and historical empty process list', stop['status'] == 'STOPPED_BY_EXPLICIT_USER_REQUEST'
          and stop['automatic_resume'] is False and stop['remaining_known_research_processes'] == []
          and post_stop['remaining_research_python_pids'] == [])
    check('exit-stop-observer chronology', exited['observed_utc'] < failure['utc'] < stop['utc'] < post_stop['utc'])
    check('initial resource gate', admission['available_ram_bytes'] >= 2_000_000_000
          and admission['free_commit_bytes'] >= 2_000_000_000)
    check('historical monitored resource gate', min(exited['minimum_free_observed'].values()) >= 2_000_000_000)

    names = [f'{i:02d}.json' for i in range(8)]
    check('exact eight starts', sorted(p.name for p in (P / 'starts').iterdir()) == names)
    check('exact eight receipts', sorted(p.name for p in (P / 'receipts').iterdir()) == names)
    check('post-stop inventory agrees', post_stop['phase_starts'] == names and post_stop['phase_receipts'] == names)
    current, prior, phase_rows, closures = {}, None, [], {}
    expected_control = {str((P / name).resolve()) for name in ('request.json', 'contract.json')}
    expected_missing = {(ticker, day) for ticker in ('QQQ', 'SPY') for day in ('20260401', '20260409', '20260415')}
    missing_metadata = {}
    for index in range(8):
        month, stage = request['months'][index // 2], ('correction', 'replay')[index % 2]
        receipt_path, start_path = P / 'receipts' / f'{index:02d}.json', P / 'starts' / f'{index:02d}.json'
        expected_control.update((str(receipt_path.resolve()), str(start_path.resolve())))
        receipt = load(receipt_path)
        start = load(start_path, receipt['start_sha256'])
        check('phase identity and chain', all(doc['request_sha256'] == REQUEST_SHA
              and doc['phase'] == [month, stage] and doc['previous_receipt_sha256'] == prior for doc in (receipt, start)), index)
        check('phase completion technical status', receipt['status'] == 'COMPLETE_OOF_PIPELINE_PHASE'
              and receipt['winner_selected'] is None and receipt['independent_audit_pending'] is True, index)
        check('phase resources historical', min(start['resources'].values()) >= 2_000_000_000, index)
        observed = receipt['output_inventory']
        check('earlier cumulative pins preserved', all(observed.get(p) == h for p, h in current.items()), index)
        if stage == 'correction':
            close_path = C / f'{month}.complete.json'
            closed = load(close_path, receipt['completion_sha256'])
            check('correction closure metadata', closed['status'] == 'COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS'
                  and closed['target_month'] == month and closed['monthly_audit_sha256'] == request['monthly_audit']['sha256']
                  and closed['dependencies'] == adapter and closed['target_labels_read'] is False
                  and closed['base_models_refitted'] is False and closed['winner_selected'] is None
                  and closed['development_seen'] is True, month)
            inputs_path = C / f'{month}.inputs.json'
            inputs = load(inputs_path, closed['inputs_sha256'])
            check('input metadata identity', inputs['dependencies'] == adapter
                  and inputs['monthly_audit_sha256'] == request['monthly_audit']['sha256'], month)
            add_map(inputs['files'], f'{month}_correction_inputs')
            add_map(inputs['run_authorities'], f'{month}_correction_run_authorities')
            impl_path, contract_path = C / 'implementation.json', C / f'{month}.run_contract.json'
            impl = load(impl_path, inputs['run_authorities'][str(impl_path)])
            check('correction implementation exact', impl == dict(dependencies=adapter,
                monthly_root=request['monthly_root'], session_root=request['session_root'],
                version='PREQUENTIAL_MAXIMUM_OFFSET_V1', calibrator_window='EXPANDING_FROM_202501', threshold=0, winner_selected=None))
            run_contract = load(contract_path, inputs['run_authorities'][str(contract_path)])
            check('correction run contract exact', run_contract == dict(target_month=month,
                monthly_audit_sha256=request['monthly_audit']['sha256'], implementation_sha256=sha(impl_path)))
            generated = {str(p.resolve()) for p in (close_path, inputs_path, impl_path, contract_path)}
            check('three procedure identities', set(closed['procedures']) == {'static', 'expanding', 'rolling12'}, month)
            for mode, part in closed['procedures'].items():
                calibration_path = C / mode / month / 'calibration.json'
                declare(calibration_path, part['calibration_sha256'], f'{month}_{mode}_calibration_hash_only')
                generated.add(str(calibration_path.resolve()))
                missing = set()
                for calendar_kind in ('history_calendar', 'target_calendar'):
                    seen = set()
                    for row in part[calendar_kind]:
                        identity = (row['ticker'], row['day'])
                        check('calendar unique identity', identity not in seen, [month, mode, calendar_kind, identity])
                        seen.add(identity)
                        check('calendar metadata binding', row['procedure'] == mode and row['ticker'] in ('SPXW', 'SPY', 'QQQ')
                              and row['source_status'] in ('COMPLETE', 'MISSING_SOURCE'), [month, mode, calendar_kind])
                        check('calendar cutoff', row['day'][:6] < month if calendar_kind == 'history_calendar'
                              else row['day'][:6] == month, [month, mode, calendar_kind])
                        if row['source_status'] == 'MISSING_SOURCE':
                            check('missing belongs to target with null selection', calendar_kind == 'target_calendar'
                                  and row['selection_path'] is None, [month, mode, identity])
                            missing.add(identity)
                            continue
                        selection = C / mode / 'selections' / row['ticker'] / (row['day'] + '.json')
                        declare(selection, row['selection_sha256'], f'{month}_{mode}_selection_hash_only')
                        generated.add(str(selection.resolve()))
                        if calendar_kind == 'history_calendar':
                            realized = C / mode / 'realized' / row['ticker'] / (row['day'] + '.json')
                            generated.add(str(realized.resolve()))
                        else:
                            score = C / mode / month / 'scores' / row['ticker'] / (row['day'] + '.json')
                            check('target metadata paths exact', Path(row['selection_path']) == selection and Path(row['score_path']) == score)
                            declare(score, row['score_sha256'], f'{month}_{mode}_score_hash_only')
                            generated.add(str(score.resolve()))
                check('six April missing identities only', missing == (expected_missing if month == '202604' else set()), [month, mode])
                missing_metadata[f'{month}/{mode}'] = sorted([list(item) for item in missing])
            closures[month] = {'correction_completion_sha256': receipt['completion_sha256']}
        else:
            root = evaluations[month]
            close_path = root / 'completion.json'
            closed = load(close_path, receipt['completion_sha256'])
            check('replay closure metadata', closed['status'] == 'COMPLETE_FIXED_OOF_POLICY_MONTH'
                  and closed['target_month'] == month and closed['dependencies'] == replay and closed['winner_selected'] is None, month)
            add_map(closed['files'], f'{month}_replay_files')
            add_map(closed['monthly_files'], f'{month}_replay_monthly_files')
            correction_sha = closures[month]['correction_completion_sha256']
            check('replay binds exact correction', closed['files'][str(C / f'{month}.complete.json')] == correction_sha, month)
            contract_path = root / 'run_contract.json'
            run_contract = load(contract_path, closed['files'][str(contract_path)])
            check('replay contract exact', run_contract == dict(version='OOF_POLICY_REPLAY_V1', dependencies=replay,
                  monthly_audit_sha256=request['monthly_audit']['sha256'], correction_completion_sha256=correction_sha,
                  target_month=month, threshold=0, winner_selected=None), month)
            generated = {str(close_path.resolve())} | {p for p in closed['files'] if Path(p).is_relative_to(root)}
            for name in ('summary.json', 'all_scores_and_controls.json'):
                check('economic output hash reference only', observed.get(str(root / name)) == closed['files'][str(root / name)], [month, name])
            closures[month]['evaluation_completion_sha256'] = receipt['completion_sha256']
        check('phase generated membership exact', set(observed) == set(current) | generated, index)
        check('closure in inventory exact', observed.get(str(close_path)) == receipt['completion_sha256'], index)
        check('new bytes accounting', receipt['new_output_bytes'] == sum(Path(p).stat().st_size for p in set(observed) - set(current)), index)
        check('cumulative bytes accounting', receipt['cumulative_output_bytes'] == sum(Path(p).stat().st_size for p in observed), index)
        phase_rows.append(dict(index=index, month=month, stage=stage, receipt_sha256=sha(receipt_path),
            start_sha256=receipt['start_sha256'], completion_sha256=receipt['completion_sha256'],
            started_at_utc=start['started_at_utc'], elapsed_seconds=receipt['elapsed_seconds'],
            inventory_files=len(observed), new_output_files=len(set(observed) - set(current)),
            new_output_bytes=receipt['new_output_bytes'], cumulative_output_bytes=receipt['cumulative_output_bytes']))
        current, prior = observed, sha(receipt_path)
    check('exact pipeline control membership', tree(P) == expected_control)
    actual_outputs = tree(C, True)
    for month, root in evaluations.items():
        check('replay directory presence matches closure', root.exists() == (month in closures), month)
        actual_outputs |= tree(root, True)
    check('exact final output tree membership', actual_outputs == set(current), dict(extra=sorted(actual_outputs-set(current)), missing=sorted(set(current)-actual_outputs)))
    check('no pipeline completion', not (P / 'completion.json').exists() and post_stop['pipeline_completion_exists'] is False)
    check('no supervisor completion', not (L / 'completion.json').exists())
    check('no May or June correction markers', all(not (C / f'{m}.{suffix}.json').exists()
          for m in ('202605', '202606') for suffix in ('complete', 'inputs', 'run_contract')))
    add_map(current, 'final_output_inventory')
    for root in (L, O):
        for name in tree(root):
            declare(name, sha(name), 'interruption_evidence_snapshot')
    identities, ancestors, sizes = {}, set(), {}
    for i, (name, expected) in enumerate(sorted(pins.items()), 1):
        path = Path(name)
        for parent in (path, *path.parents):
            parent_name = str(parent)
            if parent_name not in ancestors:
                s = parent.lstat()
                check('pin ancestry no links', not parent.is_symlink() and not (getattr(s, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT), parent_name)
                ancestors.add(parent_name)
        before = path.stat()
        identity = (before.st_dev, before.st_ino)
        check('no alternate pinned physical identity', identity not in identities or identities[identity] == name, name)
        identities[identity] = name
        actual = sha(path)
        after = path.stat()
        check('stable during streaming hash', (before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino), name)
        check('streaming hash matches pin', actual == expected, name)
        sizes[name] = after.st_size
        observed_hashes[name] = actual
        if i % 4000 == 0:
            print(json.dumps({'verified_files': i, 'total_files': len(pins)}), flush=True)
    for name, expected in loaded.items():
        check('compact metadata stable after review', sha(name) == expected, name)
    check('final control tree stable', tree(P) == expected_control)
    final_tree = tree(C, True)
    for root in evaluations.values():
        final_tree |= tree(root, True)
    check('final output tree stable', final_tree == set(current))
    evidence = dict(schema='INDEPENDENT_METADATA_HASH_REVIEW_V1', started_at_utc=started,
        ended_at_utc=datetime.now(timezone.utc).isoformat(), status='PASS_STOPPED_PREFIX_METADATA_AND_HASHES_ONLY',
        verdict='EIGHT_CLOSURES_INTEGRITY_VERIFIED_NOT_YET_ADOPTED', code_imported_or_executed=False,
        economics_interpreted=False, source_admission_rebuilt=False, audit_full_h1_performed=False,
        technical_ready=False, promotion_approved=False, winner_selected=None,
        request_sha256=REQUEST_SHA, original_runtime_binding_sha256=BINDING_SHA,
        source_admission_sha256=ADMISSION_SHA, final_receipt_sha256=prior,
        reviewed_phases=phase_rows, closures=closures, missing_source_metadata=missing_metadata,
        output_files=len(current), output_bytes=sum(sizes[p] for p in current),
        unique_pinned_files=len(pins), unique_pinned_bytes=sum(sizes.values()),
        compact_metadata_files=len(loaded), checks_count=len(checks), failed_checks=0,
        original_exit_code=exited['exit_code'], original_exit_observed_utc=exited['observed_utc'],
        original_failure_preserved=True, next_phase=['202605', 'correction'],
        historical_stop_has_no_live_processes=True, current_process_inventory_not_performed=True,
        final_inventory_sha256=hashlib.sha256(json.dumps(current, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        reviewer_script_sha256=sha(__file__),
        limitations=['No scientific reconstruction or independent inference; metadata and byte integrity only.',
            'Calibration, score, selection, realized, summary and controls payloads hashed only during this review script; their values were not interpreted.',
            'Existing source admission digest was cross-bound, not rebuilt.',
            'Historical process receipts do not establish current process absence.',
            'Original retained exit 15 and failure cannot satisfy upstream exit-zero requirements.'],
        remaining_adoption_requirements=[
            'Root independently inspect and pin this review; explicitly adopt only phase prefix 00..07 under new documented resumption authority.',
            'Keep original request, code, phase receipts, source admission, outputs, exit 15 and failure immutable.',
            'Use reviewed, published resumption supervisor/binding with fresh logs; original launcher requires fresh output roots and is inapplicable.',
            'Recheck exact current prefix, code pins, source authorities, absent May/June roots, process absence, locks and current RAM/commit gate immediately before launch.',
            'Authorize frozen pipeline resume from phase 08 only; do not rerun January-April or auto-retry.',
            'Require all twelve closures and new retained exit zero before separately reviewed/published FULL_H1 economic audit binding.'])
    write_json(OUT / 'verified_files.json', {p:dict(expected_sha256=pins[p], observed_sha256=observed_hashes[p], bytes=sizes[p], origins=sorted(origins[p])) for p in sorted(pins)})
    snapshot_sources = set(loaded)
    for root in (L, O):
        snapshot_sources.update(tree(root))
    snapshot_manifest = []
    for name in sorted(snapshot_sources):
        source = Path(name)
        relative = Path('artifacts') / source.relative_to(B) if source.is_relative_to(B) else Path('repository') / source.relative_to(R)
        destination = OUT / 'compact_snapshot' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as incoming, destination.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        source_sha, copy_sha = sha(source), sha(destination)
        check('exact immutable baseline copy', source_sha == copy_sha == pins[name], name)
        snapshot_manifest.append(dict(source=name, copy=str(destination), sha256=copy_sha, bytes=destination.stat().st_size))
    write_json(OUT / 'compact_snapshot_manifest.json', snapshot_manifest)
    evidence['compact_snapshot_count'] = len(snapshot_manifest)
    evidence['compact_snapshot_bytes'] = sum(row['bytes'] for row in snapshot_manifest)
    evidence['checks_count'] = len(checks)
    write_json(OUT / 'checks.json', checks)
    evidence['evidence_files'] = {name:sha(OUT / name) for name in ('review_interruption.py', 'verified_files.json', 'checks.json', 'compact_snapshot_manifest.json')}
    write_json(OUT / 'review_result.json', evidence)
    print(json.dumps({k:evidence[k] for k in ('status','output_files','output_bytes','unique_pinned_files','unique_pinned_bytes','checks_count','next_phase')}, indent=2))


def write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        write_json(OUT / 'review_failure.json', dict(error=repr(exc), checks=checks,
            observed_hashes=observed_hashes, utc=datetime.now(timezone.utc).isoformat()))
        raise
