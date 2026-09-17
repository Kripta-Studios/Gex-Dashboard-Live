import ast
import json
import math
from pathlib import Path

import numpy as np
import pytest
import torch

from neural.jepa.multiscale_v1r1.artifacts import digest
from neural.jepa.multiscale_v1r1.contract import CHANNELS, ContractError
from neural.jepa.multiscale_v1r1.eligibility import promotion_allowed
from neural.jepa.multiscale_v1r1.freeze import REQUIRED, seal, verify
from neural.jepa.multiscale_v1r1.preflight import capacity
from neural.jepa.multiscale_v1r1.runner import require_gate
from neural.jepa.multiscale_v1r1.ssl import causal_residual, nce, project_clock


def test_SSL_001_clock_shortcut_then_uniform():
    phase = torch.arange(12, dtype=torch.float32) / 12 * 2 * math.pi
    clock = torch.stack([phase.sin(), phase.cos()], dim=1)
    delta = 2 * math.pi / 12
    rotation = torch.tensor([[math.cos(delta), -math.sin(delta)], [math.sin(delta), math.cos(delta)]])
    logits = (clock[:-1] @ rotation) @ clock[1:].T
    assert torch.equal(logits.argmax(dim=-1), torch.arange(11))
    values = torch.ones(2, 12, 59, 39)
    masks = torch.ones_like(values)
    values[..., CHANNELS.index('time_of_day_sin')] = phase.sin()[None, :, None]
    values[..., CHANNELS.index('time_of_day_cos')] = phase.cos()[None, :, None]
    original = values.clone()
    projected = project_clock(values, masks)
    assert projected.shape == (2, 12, 4602)
    assert torch.equal(values, original)
    assert torch.equal(projected, projected[:, :1].expand_as(projected))
    z = projected[..., :32]
    assert nce(z, z).item() == pytest.approx(math.log(11), rel=1e-6)


def test_SSL_causal_residual_and_no_cross_event_candidates():
    torch.manual_seed(7)
    z = torch.randn(2, 12, 32)
    before = causal_residual(z)
    perturbed = z.clone()
    perturbed[:, 8:] *= 100
    torch.testing.assert_close(before[:, :7], causal_residual(perturbed)[:, :7], rtol=0, atol=0)
    assert nce(z, z).item() == pytest.approx((nce(z[:1], z[:1]) + nce(z[1:], z[1:])).item() / 2)


def test_ELIG_001_deny_default_and_untrusted_label(tmp_path):
    path = tmp_path / 'registry.json'
    checksum = 'a' * 64
    assert not promotion_allowed(path, 'p', checksum)
    row = dict(policy_id='p', artifact_sha256=checksum, technical_ready=True,
               economic_evidence_state='DEVELOPMENT_PASS_REQUIRES_SHADOW',
               prospective_validation_state='NOT_STARTED', promotion_approved=False,
               approval_ref=None, production_live_ready=True)
    path.write_text(json.dumps({'policies': [row]}))
    assert not promotion_allowed(path, 'p', checksum)
    row.update(artifact_kind='frozen_policy', prospective_validation_state='PASS', promotion_approved=True,
               approval_ref={'explicit_user_approval': True, 'policy_sha256': checksum, 'reference': 'synthetic-only'})
    path.write_text(json.dumps({'policies': [row]}))
    assert promotion_allowed(path, 'p', checksum)
    assert not promotion_allowed(path, 'p', 'b' * 64)


def test_FREEZE_001_missing_tampered_and_identical(tmp_path):
    artifact = tmp_path / 'artifact'
    artifact.write_text('synthetic')
    groups = {k: [artifact] for k in REQUIRED}
    with pytest.raises(ContractError):
        seal(tmp_path / 'missing', '202501', 'a' * 64, {})
    seal(tmp_path / 'freeze', '202501', 'a' * 64, groups)
    manifest = tmp_path / 'freeze/freeze_manifest.json'
    checksum = digest(manifest)
    assert verify(manifest, '202501', 'a' * 64, checksum) == verify(manifest, '202501', 'a' * 64, checksum)
    artifact.write_text('mutated')
    with pytest.raises(ContractError):
        verify(manifest, '202501', 'a' * 64, checksum)
    with pytest.raises(ContractError):
        seal(tmp_path / 'freeze', '202501', 'a' * 64, groups)


def test_FREEZE_no_forged_success_can_open_outcomes(tmp_path):
    gate = tmp_path / 'gate.json'
    with pytest.raises(ContractError):
        require_gate(gate)
    gate.write_text(json.dumps({'economic_evidence_state': 'BLOCKED_DATA', 'reason': 'fixture'}))
    with pytest.raises(ContractError, match='BLOCKED_DATA'):
        require_gate(gate)
    gate.write_text(json.dumps({'feature_gate_pass': True, 'economic_evidence_state': 'PASS'}))
    with pytest.raises(ContractError, match='not issued'):
        require_gate(gate)


def test_RESOURCE_no_oversized_allocation():
    assert not capacity(10**7, 10**15)['fits_budget']
    assert not capacity(10, 1024)['fits_budget']
    assert capacity(600, 100 * 1024**3)['fits_budget']
    assert 92048 * np.dtype('float32').itemsize == 368192


def test_AUDIT_001_import_graph_has_no_evaluator_calculations():
    folder = Path('neural/jepa/multiscale_v1r1_audit')
    forbidden = 'neural.jepa.multiscale_v1r1'
    for file in folder.glob('*.py'):
        tree = ast.parse(file.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not name.name.startswith(forbidden) for name in node.names)
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith(forbidden)
            if isinstance(node, ast.Call):
                assert not (isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec', '__import__'))
