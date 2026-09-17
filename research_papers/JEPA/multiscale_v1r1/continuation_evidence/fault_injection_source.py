"""Read-only fault injection after successful integrity checks; no artifacts mutated."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import json

from neural.jepa.multiscale_v1r1_audit import engine
from neural.jepa.multiscale_v1r1_audit.snapshot import verify_snapshot
from neural.jepa.multiscale_v1r1.artifacts import digest, write_json

root = Path('D:/GexResearchArtifacts/multiscale_v1r1/continuation_20260917_01')
run = root / 'engine_fast_01'
folder = run / 'folds/202501'
original = engine.read


def change(kind, path, value):
    path = Path(path)
    if kind in ('strike_same_money', 'late_exit', 'removed_commission') and path == run / 'payoffs/202501.json':
        facts = next(iter(value.values()))['0']
        if kind == 'strike_same_money':
            facts['contract_identity'][-1] = '999.0'
        elif kind == 'late_exit':
            facts['actual_exit_timestamp'] = '2025-01-01T16:00:01-05:00'
        else:
            facts['base']['net_dollar_pnl'] = str(float(facts['base']['net_dollar_pnl']) + 1.3)
    elif kind in ('rejection_to_execution', 'overlap') and path == folder / 'ledger.json':
        rejected = next(r for r in value['primary'] if r['reason'] == 'REJECT_OPEN_POSITION')
        rejected['reason'] = 'EXECUTED'
        if kind == 'overlap':
            rejected['payoff'] = deepcopy(next(r['payoff'] for r in value['primary'] if 'payoff' in r))
    elif kind == 'winner_changed' and path == folder / 'selection.json':
        value['winner']['config'] = 'B'
    elif kind == 'action_changed' and path == folder / 'decisions.json':
        value['primary'][0]['action_id'] = 12
    return value


results = []
for kind in ('strike_same_money', 'late_exit', 'removed_commission', 'rejection_to_execution',
             'overlap', 'winner_changed', 'action_changed'):
    def altered(path):
        return change(kind, path, deepcopy(original(path)))
    try:
        with patch.object(engine, 'read', side_effect=altered):
            engine.audit_fold(folder, run)
    except ValueError as error:
        results.append(dict(perturbation=kind, result='REJECTED', reason=str(error)))
        print(kind, str(error), flush=True)
    else:
        raise AssertionError('Undetected semantic perturbation: ' + kind)
snapshot = root / 'recovery/current_documents'
contents = verify_snapshot(snapshot, digest(snapshot / 'manifest.json'))
result = dict(status='PASS_SUPPLEMENTAL_SEMANTIC_FAULT_INJECTION', cases=results,
              method='In-memory parser perturbation after unchanged integrity checks; no original disk artifact overwritten',
              snapshot_documents_reverified=len(contents), snapshot_manifest_sha256=digest(snapshot / 'manifest.json'),
              historical_outcomes_opened=False, promotion_approved=False)
write_json(root / 'supplemental_fault_checks.json', result)
print(json.dumps(result))
