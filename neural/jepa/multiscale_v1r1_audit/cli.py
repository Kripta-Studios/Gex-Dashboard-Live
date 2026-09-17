"""Independent audit CLI, with no imports from evaluator calculation modules."""
import argparse
import json
from pathlib import Path

from .verify import audit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('data-gate', 'fold', 'final'))
    parser.add_argument('--contract', required=True, type=Path)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--inventory-manifest', required=True, type=Path)
    parser.add_argument('--gate-manifest', required=True, type=Path)
    parser.add_argument('--month')
    args = parser.parse_args(argv)
    if args.command != 'data-gate':
        print(json.dumps({'status': 'BLOCKED_DATA', 'reason': 'No economic fold exists; source admission is closed'}))
        return 2
    destination = args.root / 'data_gate_audit'
    if destination.exists() or destination.with_suffix('.staging').exists():
        raise FileExistsError('Independent evidence already exists')
    result = audit(args.inventory_manifest.parent, args.gate_manifest.parent, args.contract)
    staging = destination.with_suffix('.staging')
    staging.mkdir()
    (staging / 'data_gate_audit.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    staging.rename(destination)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
