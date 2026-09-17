"""ELIG-001. Standalone denial-by-default API; not wired to any service."""
import json
from pathlib import Path


def promotion_allowed(registry_path, policy_id, artifact_sha256):
    try:
        rows = json.loads(Path(registry_path).read_text(encoding='utf-8'))['policies']
        matches = [r for r in rows if r.get('policy_id') == policy_id]
        if len(matches) != 1:
            return False
        row = matches[0]
        approval = row.get('approval_ref')
        return bool(
            len(artifact_sha256) == 64
            and row.get('artifact_sha256') == artifact_sha256
            and row.get('artifact_kind') == 'frozen_policy'
            and row.get('technical_ready') is True
            and row.get('promotion_approved') is True
            and row.get('prospective_validation_state') == 'PASS'
            and row.get('economic_evidence_state') == 'DEVELOPMENT_PASS_REQUIRES_SHADOW'
            and isinstance(approval, dict)
            and approval.get('explicit_user_approval') is True
            and approval.get('policy_sha256') == artifact_sha256
            and isinstance(approval.get('reference'), str) and approval['reference'].strip()
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False
