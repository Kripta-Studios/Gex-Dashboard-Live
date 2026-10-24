from types import SimpleNamespace
import sys

import pytest

import run_monthly_resource_overlay as overlay


@pytest.mark.parametrize("low", ["available_ram_bytes", "free_commit_bytes"])
def test_exact_decimal_boundaries(tmp_path, monkeypatch, low):
    first = dict(
        available_ram_bytes=2_000_000_000, free_commit_bytes=2_000_000_000, utc="first"
    )
    first[low] -= 1
    observations = iter(
        [
            first,
            dict(
                available_ram_bytes=2_000_000_000,
                free_commit_bytes=2_000_000_000,
                utc="second",
            ),
        ]
    )
    sleeps = []
    monkeypatch.setattr(overlay, "resource_observation", lambda: next(observations))
    monkeypatch.setattr(overlay.time, "sleep", sleeps.append)
    overlay.wait_resources(tmp_path / "science", tmp_path / "runtime")
    records = [
        overlay.shared.read_json(p)
        for p in sorted((tmp_path / "runtime/observations").glob("*.json"))
    ]
    assert [r["stage"] for r in records] == [
        "WAITING_RESOURCES_2GB",
        "RESOURCE_OVERLAY_READY",
    ]
    assert sleeps == [30]
    assert records[-1]["threshold_bytes"] == 2_000_000_000 < 2 * 1024**3


def test_resource_observation_uses_actual_provider(monkeypatch):
    monkeypatch.setattr(
        overlay.shared.psutil, "virtual_memory", lambda: SimpleNamespace(available=123)
    )
    monkeypatch.setattr(overlay.shared, "free_commit_bytes", lambda: 456)
    result = overlay.resource_observation()
    assert result["available_ram_bytes"] == 123
    assert result["free_commit_bytes"] == 456


@pytest.mark.parametrize("failure", [False, True])
def test_only_wait_replaced_and_always_restored(tmp_path, monkeypatch, failure):
    wait, fit, main = (
        overlay.shared.wait_resources,
        overlay.shared.fit_once,
        overlay.monthly.main,
    )
    calls = []
    monkeypatch.setattr(
        overlay, "wait_resources", lambda out, runtime: calls.append((out, runtime))
    )
    try:
        with overlay.resource_overlay(tmp_path):
            assert overlay.shared.fit_once is fit
            assert overlay.monthly.main is main
            overlay.shared.wait_resources("science")
            if failure:
                raise RuntimeError("synthetic failure")
    except RuntimeError:
        assert failure
    assert overlay.shared.wait_resources is wait
    assert calls == [("science", tmp_path)]


def test_cli_validation_only():
    args = overlay.original_argv()
    assert args[-2:] == ["--stage", "validation"]
    assert len(args) == 12
    assert "--out" in args
    assert "test" not in args and "all" not in args


def test_live_previous_pid_rejected(monkeypatch):
    monkeypatch.setattr(overlay.shared.psutil, "pid_exists", lambda pid: True)
    with pytest.raises(ValueError, match="still exists"):
        overlay.assert_stopped(123)


def test_incomplete_fit_is_preserved(tmp_path, monkeypatch):
    (tmp_path / "models").mkdir()
    started = tmp_path / "models/example.fit_started.json"
    started.write_text("{}")
    monkeypatch.setattr(
        overlay.monthly,
        "Artifacts",
        lambda *args: SimpleNamespace(complete=lambda name: False),
    )
    with pytest.raises(ValueError, match="Incomplete started fit"):
        overlay.existing_checkpoints(tmp_path, "binding")
    assert started.read_text() == "{}"


def test_hash_mutation_rejected(tmp_path):
    path = tmp_path / "checkpoint"
    path.write_text("original")
    hashes = {str(path): overlay.shared.sha(path)}
    overlay.verify_hashes(hashes)
    path.write_text("changed")
    with pytest.raises(ValueError, match="Preserved evidence changed"):
        overlay.verify_hashes(hashes)


@pytest.mark.parametrize("failure", [False, True])
def test_continuation_manifest_and_restore(tmp_path, monkeypatch, failure):
    science, here, runtime = (
        tmp_path / "science",
        tmp_path / "code",
        tmp_path / "runtime",
    )
    science.mkdir()
    here.mkdir()
    original_file = science / "completed-model.txt"
    original_file.write_text("old model, never fitted again")
    preserved = {str(original_file): overlay.shared.sha(original_file)}
    dependencies = {str(i): str(i) for i in range(11)}
    contract = science / "run_contract.json"
    overlay.shared.atomic_json(contract, {"dependencies": dependencies})
    source = here / "wrapper.py"
    source.write_text("immutable runtime source")
    review = tmp_path / "review.json"
    review.write_text("{}")
    authority = dict(
        files={source.name: overlay.shared.sha(source)},
        original_dependencies=dependencies,
    )
    monkeypatch.setattr(overlay, "SCIENTIFIC_ROOT", science)
    monkeypatch.setattr(overlay, "HERE", here)
    monkeypatch.setattr(overlay, "RUN_CONTRACT_SHA", overlay.shared.sha(contract))
    monkeypatch.setattr(overlay, "assert_stopped", lambda pid: None)
    monkeypatch.setattr(
        overlay, "require_review", lambda path: (authority, overlay.shared.sha(path))
    )
    monkeypatch.setattr(overlay, "review_expectations", lambda: authority)
    monkeypatch.setattr(
        overlay, "existing_checkpoints", lambda root, binding: dict(preserved)
    )
    original_argv, wait = sys.argv, overlay.shared.wait_resources
    calls = []

    def fake_main():
        calls.append(tuple(sys.argv))
        assert overlay.shared.wait_resources is not wait
        assert original_file.read_text() == "old model, never fitted again"
        if failure:
            raise RuntimeError("synthetic main failure")

    monkeypatch.setattr(overlay.monthly, "main", fake_main)
    if failure:
        with pytest.raises(RuntimeError, match="synthetic main failure"):
            overlay.run(runtime, review, 123)
        assert (runtime / "failure.json").exists()
        assert not (runtime / "completion.json").exists()
    else:
        overlay.run(runtime, review, 123)
        completion = overlay.shared.read_json(runtime / "completion.json")
        overlay.verify_hashes(completion["runtime_members"])
        assert completion["preserved_checkpoints"] == preserved
        assert completion["scientific_inputs_changed"] is False
    assert len(calls) == 1 and calls[0][-1] == "validation"
    assert sys.argv is original_argv and overlay.shared.wait_resources is wait
    overlay.verify_hashes(preserved)
    with pytest.raises(ValueError, match="new runtime attempt"):
        overlay.run(runtime, review, 123)


def test_runtime_path_overlap_rejected():
    for path in [
        overlay.SCIENTIFIC_ROOT,
        overlay.SCIENTIFIC_ROOT / "child",
        overlay.ROOT,
        overlay.HERE,
    ]:
        with pytest.raises(ValueError, match="separate directory"):
            overlay.guard_runtime_root(path)
