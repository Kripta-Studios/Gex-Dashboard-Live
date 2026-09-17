"""The historical runner is closed at the verified source-admission barrier.

No economic pipeline is claimed implemented/validated by this admission package.
Do not replace a failed source conclusion by wiring partial primitives together.
"""
import json
from pathlib import Path

from .contract import ContractError


def require_gate(path):
    path = Path(path)
    if not path.is_file():
        raise ContractError('FREEZE-001: missing independently audited feature gate')
    gate = json.loads(path.read_text(encoding='utf-8'))
    if gate.get('economic_evidence_state') == 'BLOCKED_DATA':
        raise ContractError('BLOCKED_DATA: ' + gate.get('reason', 'source admission failed'))
    # This source-admission release has no positive feature gate/auditor. A forged
    # success flag must not unlock a payoff reader or an unfinished experiment.
    raise ContractError('FREEZE-001: historical execution capability is not issued by this release')
