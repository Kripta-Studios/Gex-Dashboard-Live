"""Explicit research stages. No automatic download, tuning or payoff bypass."""
import argparse
import json
from pathlib import Path

from .artifacts import digest, publication
from .contract import ContractError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('preflight', 'inventory', 'build-gate',
                                          'prepare-fold', 'evaluate-fold', 'summarize'))
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--runtime-manifest', type=Path)
    parser.add_argument('--inventory-manifest', type=Path)
    parser.add_argument('--gate-manifest', type=Path)
    parser.add_argument('--month', choices=[f'{y}{m:02d}' for y in (2025, 2026)
                                          for m in range(1, 13) if y == 2025 or m <= 6])
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[3]
    try:
        if not args.contract.resolve().is_relative_to(repo / 'research_papers/JEPA/multiscale_v1r1'):
            raise ContractError('AUTH-001: contract must be the versioned V1R1 authority')
        if args.contract.name != '01_PREDECLARATION.md':
            raise ContractError('AUTH-001: only V1R1 is selectable')
        if not args.root.resolve().is_relative_to(Path('D:/GexResearchArtifacts/multiscale_v1r1').resolve()):
            raise ContractError('IO-001: use the declared new artifact root')
        contract_hash = digest(args.contract)
        if args.command == 'preflight':
            from .preflight import run
            result = run(repo, args.root, args.contract)
        else:
            code = [p for folder in ('multiscale_v1r1', 'multiscale_v1r1_audit')
                    for p in (repo / 'neural/jepa' / folder).rglob('*.py')]
            publication(repo, [args.contract, *code])
            if not args.runtime_manifest:
                raise ContractError('IO-001: explicit --runtime-manifest required')
            from .preflight import runtime
            observed = json.loads(args.runtime_manifest.read_text(encoding='utf-8'))
            if observed != runtime(repo):
                raise ContractError('IO-001: runtime/code changed after preflight')
            preflight = json.loads((args.runtime_manifest.parent / 'preflight_summary.json').read_text(encoding='utf-8'))
            if preflight['status'] != 'PASS_SYNTHETIC_PREFLIGHT' or preflight['contract_sha256'] != contract_hash:
                raise ContractError('RESOURCE-001: preflight not passed for this contract')
            if args.command == 'inventory':
                from .inventory import SOURCE_ROOT, build_inventory
                result = build_inventory(SOURCE_ROOT, args.root / 'inventory', contract_hash, args.root / 'access_log.jsonl')
            elif args.command == 'build-gate':
                if not args.inventory_manifest or args.inventory_manifest.name != 'source_manifest.parquet':
                    raise ContractError('DATA-001: explicit --inventory-manifest required')
                from .data_gate import build
                result = build(args.inventory_manifest.parent, args.root / 'data_gate', contract_hash, args.root / 'access_log.jsonl')
            else:
                from .runner import require_gate
                if not args.gate_manifest:
                    raise ContractError('FREEZE-001: explicit --gate-manifest required')
                require_gate(args.gate_manifest)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result.get('status', '').startswith(('PASS', 'INVENTORIED')) else 2
    except (ContractError, FileNotFoundError) as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(error), 'outcomes_opened': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
