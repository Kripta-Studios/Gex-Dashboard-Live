"""Recovery and runnable synthetic engine; historical economics remains gated."""
import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('recovery', 'synthetic-e2e', 'real-component-smoke'))
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--specification', required=True, type=Path)
    parser.add_argument('--old-root', type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[3]
    allowed = repo / 'research_papers/JEPA/multiscale_v1r1'
    expected = '13_RECOVERY_SPEC.md' if args.command == 'recovery' else '14_ENGINE_COMPLETION_SPEC.md'
    if args.specification.resolve() != (allowed / expected).resolve():
        parser.error('Explicit versioned continuation specification required')
    if args.command == 'recovery':
        if args.source_root is None or args.source_root.resolve() != Path('D:/ThetaData').resolve() or args.old_root is None:
            parser.error('Recovery requires explicit permitted D:/ThetaData and original artifact root')
        from .recovery import recover
        result = recover(args.old_root, args.source_root, args.root)
    elif args.command == 'synthetic-e2e':
        from .synthetic_engine import run
        result = run(args.root, args.specification, resume=args.resume)
    else:
        from .component_smoke import run
        result = run(args.root)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
