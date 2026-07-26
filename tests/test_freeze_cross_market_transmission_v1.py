from __future__ import annotations

import copy
import subprocess

import pytest

from neural.jepa import freeze_cross_market_transmission_v1 as subject
from neural.jepa.build_cross_market_transmission_view_v1 import CROSS_FEATURES


def _arms() -> dict[str, dict[str, object]]:
    # Names before the 28-field suffix are immaterial to this unit test; their
    # exact authoritative hash is separately frozen and tested below.
    x0 = [f"base_{index}" for index in range(30)]
    x1 = [*x0, *CROSS_FEATURES]
    return {
        "X0": {
            "features": x0,
            "feature_count": 30,
            "ordered_json_sha256": subject._canonical_ordered_sha(x0),
        },
        "X1": {
            "features": x1,
            "feature_count": 58,
            "ordered_json_sha256": subject._canonical_ordered_sha(x1),
        },
    }


def test_freeze_closure_contains_builder_model_runner_scheduler_self_and_predeclaration() -> None:
    assert subject.CODE_CLOSURE == (
        "neural/jepa/build_cross_market_transmission_view_v1.py",
        "neural/jepa/evaluate_cross_market_transmission_v1.py",
        "neural/jepa/existing_data_quantile_distribution_v1.py",
        "neural/jepa/existing_data_edge_scheduler_v1.py",
        "neural/jepa/walkforward_pairwise_opportunity_side.py",
        "neural/jepa/freeze_cross_market_transmission_v1.py",
    )
    assert subject.PROTOCOL_CLOSURE == (
        "research_papers/JEPA/CROSS_MARKET_TRANSMISSION_V1_PREDECLARATION.md",
        "research_papers/JEPA/CROSS_MARKET_TRANSMISSION_V1R1_HALF_DAY_REPAIR.md",
    )


def test_frozen_hashes_match_active_model_protocol_and_cross_block() -> None:
    assert subject.frozen_spec_sha256() == subject.EXPECTED_MODEL_SPEC_SHA256
    assert subject.runner_protocol_sha256() == subject.EXPECTED_RUNNER_PROTOCOL_SHA256
    assert subject._canonical_ordered_sha(list(CROSS_FEATURES)) == subject.EXPECTED_CROSS_SHA256
    assert len(CROSS_FEATURES) == 28


def test_feature_arm_validator_requires_authoritative_hashes(monkeypatch: pytest.MonkeyPatch) -> None:
    arms = _arms()
    monkeypatch.setattr(subject, "EXPECTED_X0_SHA256", arms["X0"]["ordered_json_sha256"])
    monkeypatch.setattr(subject, "EXPECTED_X1_SHA256", arms["X1"]["ordered_json_sha256"])
    assert subject._verify_feature_arms(arms)["X1"]["feature_count"] == 58

    changed = copy.deepcopy(arms)
    changed["X1"]["features"][-1] = "xmt__forbidden_mutation"
    changed["X1"]["ordered_json_sha256"] = subject._canonical_ordered_sha(
        changed["X1"]["features"]
    )
    with pytest.raises(AssertionError, match="exact X0 plus"):
        subject._verify_feature_arms(changed)


def test_git_verifier_checks_origin_staged_unstaged_and_committed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_git(*args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD") or args[:2] == ("rev-parse", "origin/main"):
            return "abc123"
        if args[:2] == ("ls-files", "--error-unmatch"):
            return args[2]
        raise AssertionError(args)

    clean_calls: list[bool] = []

    def clean(*, cached: bool) -> bool:
        clean_calls.append(cached)
        return True

    monkeypatch.setattr(subject, "_git", fake_git)
    monkeypatch.setattr(subject, "_tracked_diff_clean", clean)
    assert subject._verify_git_state() == ("abc123", "abc123")
    assert clean_calls == [False, True]

    monkeypatch.setattr(subject, "_tracked_diff_clean", lambda *, cached: not cached)
    with pytest.raises(AssertionError, match="staged tracked"):
        subject._verify_git_state()


def test_git_verifier_rejects_uncommitted_closure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_git(*args: str) -> str:
        if args[0] == "rev-parse":
            return "same"
        raise subprocess.CalledProcessError(1, ["git", *args])

    monkeypatch.setattr(subject, "_git", fake_git)
    monkeypatch.setattr(subject, "_tracked_diff_clean", lambda *, cached: True)
    with pytest.raises(AssertionError, match="not committed"):
        subject._verify_git_state()


def test_model_protocol_verifier_preserves_2026_and_outer_boundary() -> None:
    model, protocol = subject._verify_model_and_protocol()
    assert model["family"] == "lightgbm_quantile_distribution_utility_v1"
    assert protocol["outer_months"] == list(subject.OUTER_MONTHS)
    assert protocol["holdout_2026_opened"] is False
    assert protocol["june_2026_sealed"] is True


def test_freeze_refuses_to_overwrite_before_reading_any_input(tmp_path) -> None:
    output = tmp_path / "manifest.json"
    output.write_text("already frozen", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        subject.freeze(output)
