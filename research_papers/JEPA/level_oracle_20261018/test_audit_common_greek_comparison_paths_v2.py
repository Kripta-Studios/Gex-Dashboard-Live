"""Synthetic Windows/POSIX manifest paths; unchanged independent audit economics."""

import ast
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

import audit_common_greek_comparison as original
import audit_common_greek_comparison_paths_v2 as audit
import test_audit_common_greek_comparison as fixtures


ORIGINAL_SHA = "3898ef3c8ae634a65a2a136c75f2e14a46d5ac6fcad4bcc28bdb77742f3dca70"


@pytest.mark.parametrize("name", [name for name in vars(fixtures) if name.startswith("test_")])
def test_legacy_fixtures_against_v2(name, monkeypatch, tmp_path):
    for function in ("calibration_report", "calibration_sums", "coverage", "digest",
                     "rehash_memo", "schedule", "verify_marker", "verify_training_provenance"):
        monkeypatch.setattr(fixtures, function, getattr(audit, function))
    function = getattr(fixtures, name)
    function(tmp_path) if "tmp_path" in inspect.signature(function).parameters else function()


@pytest.mark.parametrize("relative", ["predictions/QQQ/20250102.npz",
                                     "predictions\\QQQ\\20250102.npz",
                                     "predictions\\QQQ/20250102.npz"])
def test_actual_baseline_member_windows_posix_and_mixed(tmp_path, relative):
    path = tmp_path / "predictions/QQQ/20250102.npz"
    path.parent.mkdir(parents=True)
    np.savez(path, action_id=np.array([1, 2]), state_i=np.array([60, 61]),
             cue_net__0=np.array([-0., 1.], dtype=np.float64))
    expected = audit.digest(path)
    files = audit.canonical_manifest_files(tmp_path, {relative: expected})
    memo = {}
    resolved = audit.remember_baseline_score(tmp_path, files, "predictions/QQQ/20250102.npz", memo)
    assert resolved == path and memo[str(path.resolve())] == expected
    with np.load(resolved, allow_pickle=False) as saved:
        assert saved["cue_net__0"].dtype == np.float64
        assert saved["cue_net__0"].tobytes() == np.array([-0., 1.]).tobytes()
    audit.rehash_memo(memo)


@pytest.mark.parametrize("relative", [
    "", "/absolute", "\\rooted", "C:/absolute", "C:relative", "C:\\absolute",
    "//server/share/file", "\\\\server\\share\\file", "\\\\?\\C:\\file",
    "../escape", "a/../escape", "a\\..\\escape", "./a", "a/./b", "a//b",
    "a\\\\b", "a/", "a/file:stream", "a/file.", "a/file ", "NUL", "a/CON.txt",
    "a/COM1", "a/LPT².txt", "a/fi\x00le", "a/file?", "a/file*",
])
def test_unsafe_relative_paths_rejected_without_file_read(tmp_path, relative, monkeypatch):
    monkeypatch.setattr(audit, "digest", lambda *_: pytest.fail("Unsafe path read"))
    with pytest.raises(AssertionError):
        audit.canonical_manifest_files(tmp_path, {relative: "a" * 64})


@pytest.mark.parametrize("left,right", [
    ("nested/file", "nested\\file"), ("nested/file", "NESTED/FILE"),
    ("a\\b/file", "a/b\\file"),
])
@pytest.mark.parametrize("same_hash", [True, False])
def test_collisions_never_merge_even_with_identical_hash(tmp_path, left, right, same_hash):
    with pytest.raises(AssertionError, match="collision"):
        audit.canonical_manifest_files(tmp_path, {left: "a" * 64, right: ("a" if same_hash else "b") * 64})


def test_resolved_escape_and_alias_rejected(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    real_resolve = Path.resolve

    def resolved(path, *args, **kwargs):
        if path == root / "escape":
            return tmp_path / "outside"
        if path == root / "alias":
            return root / "first"
        return real_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolved)
    with pytest.raises(AssertionError, match="escapes"):
        audit.canonical_manifest_files(root, {"escape": "a" * 64})
    with pytest.raises(AssertionError, match="collision"):
        audit.canonical_manifest_files(root, {"first": "a" * 64, "alias": "a" * 64})


def test_baseline_missing_and_changed_hash_still_fail(tmp_path):
    path = tmp_path / "nested/score.npz"
    path.parent.mkdir()
    path.write_bytes(b"sealed")
    files = audit.canonical_manifest_files(tmp_path, {"nested\\score.npz": audit.digest(path)})
    with pytest.raises(AssertionError, match="Baseline score absent"):
        audit.remember_baseline_score(tmp_path, files, "nested/missing.npz", {})
    path.write_bytes(b"mutated")
    with pytest.raises(AssertionError, match="Consumed artifact authority"):
        audit.remember_baseline_score(tmp_path, files, "nested/score.npz", {})


@pytest.mark.parametrize("consumer", ["baseline", "marker"])
def test_resolution_escape_between_normalization_and_consumption(tmp_path, monkeypatch, consumer):
    root = tmp_path / "root"
    root.mkdir()
    target = root / "file"
    target.write_bytes(b"sealed")
    expected = audit.digest(target)
    (root / "unit.complete.json").write_text(json.dumps(
        dict(status="COMPLETE", binding="bound", files={"file": expected})))
    real_resolve = Path.resolve
    resolutions = []

    def resolve(path, *args, **kwargs):
        if path == target:
            resolutions.append(1)
            if len(resolutions) > 1:
                return tmp_path / "outside"
        return real_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(audit, "digest", lambda *_: pytest.fail("Escaping file consumed"))
    with pytest.raises(AssertionError, match="escapes"):
        if consumer == "baseline":
            files = audit.canonical_manifest_files(root, {"file": expected})
            audit.remember_baseline_score(root, files, "file", {})
        else:
            audit.verify_marker(root, "unit", "bound", {}, ["file"])


def test_marker_collision_missing_and_mutated_hash(tmp_path):
    target = tmp_path / "nested/file.txt"
    target.parent.mkdir()
    target.write_text("sealed")
    expected = audit.digest(target)
    marker = dict(status="COMPLETE", binding="bound", files={"nested\\file.txt": expected})
    path = tmp_path / "unit.complete.json"
    path.write_text(json.dumps(marker))
    with pytest.raises(AssertionError, match="Marker files"):
        audit.verify_marker(tmp_path, "unit", "bound", {}, ["not_present"])
    audit.verify_marker(tmp_path, "unit", "bound", {}, ["nested/file.txt"])
    marker["files"]["nested/file.txt"] = expected
    path.write_text(json.dumps(marker))
    with pytest.raises(AssertionError, match="collision"):
        audit.verify_marker(tmp_path, "unit", "bound", {})
    del marker["files"]["nested/file.txt"]
    path.write_text(json.dumps(marker))
    target.write_text("mutated")
    with pytest.raises(AssertionError, match="Marker artifact"):
        audit.verify_marker(tmp_path, "unit", "bound", {})


def test_original_and_all_unmodified_function_asts_preserved():
    assert audit.digest(Path(original.__file__)) == ORIGINAL_SHA
    source = ast.parse(Path(original.__file__).read_text())
    changed = ast.parse(Path(audit.__file__).read_text())
    old_functions = {n.name: n for n in source.body if isinstance(n, ast.FunctionDef)}
    new_functions = {n.name: n for n in changed.body if isinstance(n, ast.FunctionDef)}
    for name, node in old_functions.items():
        if name not in ("main", "verify_marker"):
            assert ast.dump(node) == ast.dump(new_functions[name]), name
    for name in ("POLICIES", "EDGES", "MISSING"):
        before = next(n for n in source.body if isinstance(n, ast.Assign) and n.targets[0].id == name)
        after = next(n for n in changed.body if isinstance(n, ast.Assign) and n.targets[0].id == name)
        assert ast.dump(before) == ast.dump(after)
    # Exact allowlist of main differences: canonical relative maps and baseline member lookup.
    expected = inspect.getsource(original.main)
    expected = expected.replace('        marker = read_json(root / "model.complete.json")\n',
        '        marker = read_json(root / "model.complete.json")\n'
        '        model_files = canonical_manifest_files(root, marker["files"])\n')
    expected = expected.replace('model_name in marker["files"]', 'model_name in model_files')
    expected = expected.replace('marker["files"][model_name]', 'model_files[model_name]')
    expected = expected.replace('remember(memo, root / model_name, model_files[model_name])',
        'remember(memo, resolved_manifest_target(root, model_name), model_files[model_name])')
    expected = expected.replace('    require(baseline_manifest["status"] == "COMPLETE", "Baseline completion")\n',
        '    require(baseline_manifest["status"] == "COMPLETE", "Baseline completion")\n'
        '    baseline_files = canonical_manifest_files(args.baseline_root, baseline_manifest["files"])\n')
    expected = expected.replace(
        '            require(baseline_rel in baseline_manifest["files"], "Baseline score absent")\n'
        '            reference = args.baseline_root / baseline_rel\n'
        '            remember(memo, reference, baseline_manifest["files"][baseline_rel])\n',
        '            reference = remember_baseline_score(args.baseline_root, baseline_files, baseline_rel, memo)\n')
    assert ast.dump(ast.parse(expected)) == ast.dump(ast.parse(inspect.getsource(audit.main)))
