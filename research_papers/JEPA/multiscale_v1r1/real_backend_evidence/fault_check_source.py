"""Post-PASS semantic fault injection; replay models are explicitly test doubles."""
import argparse
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import lightgbm

from neural.jepa.multiscale_v1r1_audit import real_backend as audit


def run(root, output):
    root = Path(root).resolve()
    summary = json.loads((root / 'summary.json').read_bytes())
    independent = json.loads((root / 'audit.json').read_bytes())
    assert summary['status'] == 'PASS_REAL_BACKEND_SYNTHETIC_FOLD'
    assert independent['refits'] == 72 and independent['mismatches'] == 0
    output = Path(output).resolve()
    output.mkdir(exist_ok=False)
    original_read = audit.read
    selection = original_read(root / 'selection.json')
    payoffs = {split: original_read(root / f'{split}_payoffs.json') for split in ('train', 'selection', 'test')}
    model_paths = [root / 'models' / name / f'action_{i:02d}.txt' for name in ('A', 'B', 'ablation') for i in range(24)]
    originals = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in model_paths}
    results = {}

    for mutation in ('model_text', 'winner_threshold'):
        counter = [0]
        class ReplayRegressor:
            # Deliberately does not fit. Actual refits are certified in the input audit.
            def __init__(self, **parameters):
                self.parameters = parameters

            def fit(self, x, y):
                path = model_paths[counter[0]]
                counter[0] += 1
                self.booster_ = lightgbm.Booster(model_file=str(path))
                bundle = original_read(path.parent / 'bundle.json')
                self.booster_.params = bundle['entries'][int(path.stem[-2:])]['parameters']
                return self

        def changed_read(path):
            value = original_read(path)
            if mutation == 'winner_threshold' and Path(path) == root / 'selection.json':
                value = deepcopy(value)
                assert selection['winner']['threshold'] == 0.0
                value['winner']['threshold'] = 5.0
            return value

        original_text = Path.read_text
        def changed_text(path, *args, **kwargs):
            value = original_text(path, *args, **kwargs)
            if mutation == 'model_text' and path == model_paths[0]:
                value = value.replace('leaf_value=', 'leaf_value=999 ', 1)
            return value

        with ExitStack() as stack:
            stack.enter_context(patch.object(lightgbm, 'LGBMRegressor', ReplayRegressor))
            stack.enter_context(patch.object(audit, 'audit_tensor_fixture', lambda path: None))
            stack.enter_context(patch.object(audit, 'reconstruct_payoffs', lambda path, split, events: payoffs[split]))
            stack.enter_context(patch.object(audit, 'read', changed_read))
            stack.enter_context(patch.object(Path, 'read_text', changed_text))
            try:
                audit.audit_run(root)
            except ValueError as error:
                expected = 'real refit model bytes' if mutation == 'model_text' else 'winner mismatch'
                assert expected in str(error), (expected, str(error))
                results[mutation] = dict(rejected=True, reason=str(error), replay_models_loaded=counter[0])
            else:
                raise AssertionError('Semantic mutation was accepted')
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in originals.items())
    result = dict(status='PASS_SEMANTIC_FAULT_CHECKS_WITH_REPLAY_DOUBLES', mutations=results,
                  underlying_independent_real_refits=72, additional_real_refits=0,
                  reused_verified_components=['tensor_reconstruction', 'payoff_reconstruction'],
                  hash_checks_passed_on_unchanged_artifacts=True, mutations_in_memory_only=True,
                  historical_economics='NOT_EVALUATED', promotion_approved=False)
    (output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    (output / 'source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.root, args.output)
