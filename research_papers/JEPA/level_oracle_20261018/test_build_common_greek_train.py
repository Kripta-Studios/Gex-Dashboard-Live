import numpy as np
import pandas as pd
import pytest

import build_common_greek_train as builder
from test_common_greek_dynamics import raw_fixture


class FakeSource:
    def __init__(self, tmp_path):
        self.sample = pd.DataFrame(
            dict(
                sample_i=[0, 1, 2, 3],
                day_key=["SPY/20230103"] * 2 + ["SPY/20230104"] * 2,
                ticker=["SPY"] * 4,
                date=["20230103"] * 2 + ["20230104"] * 2,
                action_id=[5, 7, 11, 12],
                state_i=[100, 100, 95, 105],
                weight=[0.5, 1.5, 1.0, 1.0],
            )
        )
        self.base = np.arange(4 * 152, dtype=np.float32).reshape(4, 152)
        self.authority = tmp_path / "source-authority"
        self.authority.write_bytes(b"sealed")
        self.hashes = {str(self.authority): builder.sha(self.authority)}
        self.calls = []
        self.fail_day = None

    def day(self, key, rows):
        self.calls.append(key)
        if key == self.fail_day:
            raise RuntimeError("injected day interruption")
        return self.base[rows.sample_i], raw_fixture(), dict(self.hashes)

    def verify(self, path, digest):
        assert builder.sha(path) == digest, "changed source"
        self.hashes[str(path)] = digest

    def recheck(self):
        for path, digest in self.hashes.items():
            self.verify(path, digest)


def test_completed_build_preserves_prefix_keys_ipw_and_never_recomputes(tmp_path):
    source = FakeSource(tmp_path)
    evidence = builder.checkpoint.Checkpoints(tmp_path / "out", "binding")
    builder.prepare(source, evidence)
    x = np.load(evidence.root / "train_x.npy")
    assert x.shape == (4, 424)
    np.testing.assert_array_equal(
        x[:, :152].view(np.uint32), source.base.view(np.uint32)
    )
    with np.load(evidence.root / "row_keys.npz", allow_pickle=False) as keys:
        assert set(keys.files) == set(builder.KEY_COLUMNS)
        for field in ("sample_i", "action_id", "state_i", "weight"):
            np.testing.assert_array_equal(keys[field], source.sample[field])
    assert not (evidence.root / "targets.npz").exists()
    coverage = builder.read_json(evidence.root / "coverage.json")
    assert coverage["denominators"] == {
        "actions": 4.0,
        "ipw": 4.0,
        "unique_states": 3.0,
    }
    source.calls.clear()
    builder.prepare(source, evidence)
    assert source.calls == []
    source.authority.write_bytes(b"mutated")
    with pytest.raises(AssertionError, match="changed source"):
        builder.prepare(source, evidence)


def test_interruption_day_and_matrix_assembly_resume_from_exact_chunks(
    tmp_path, monkeypatch
):
    source = FakeSource(tmp_path)
    evidence = builder.checkpoint.Checkpoints(tmp_path / "out", "binding")
    source.fail_day = "SPY/20230104"
    with pytest.raises(RuntimeError, match="interruption"):
        builder.prepare(source, evidence)
    first = evidence.root / "chunks/SPY/20230103.npz"
    before = builder.sha(first)
    orphan = evidence.root / "chunks/SPY/20230104.npz"
    orphan.write_bytes(b"unfinished")
    source.fail_day = None
    original_memmap = np.lib.format.open_memmap
    monkeypatch.setattr(
        np.lib.format,
        "open_memmap",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("assembly interrupted")),
    )
    with pytest.raises(RuntimeError, match="assembly interrupted"):
        builder.prepare(source, evidence)
    assert builder.sha(first) == before
    assert any(
        path.read_bytes() == b"unfinished"
        for path in (evidence.root / "preserved_orphans").rglob("20230104.npz")
    )
    monkeypatch.setattr(np.lib.format, "open_memmap", original_memmap)
    source.calls.clear()
    builder.prepare(source, evidence)
    assert not source.calls
    assert builder.sha(first) == before


def test_sealed_chunk_mutation_and_wrong_binding_fail_closed(tmp_path):
    source = FakeSource(tmp_path)
    source.fail_day = "SPY/20230104"
    evidence = builder.checkpoint.Checkpoints(tmp_path / "out", "binding")
    with pytest.raises(RuntimeError):
        builder.prepare(source, evidence)
    (evidence.root / "chunks/SPY/20230103.npz").write_bytes(b"modified")
    source.fail_day = None
    with pytest.raises(ValueError, match="Changed checkpoint member"):
        builder.prepare(source, evidence)
    with pytest.raises(ValueError, match="binding differs"):
        builder.prepare(source, builder.checkpoint.Checkpoints(evidence.root, "wrong"))


def make_authorities(tmp_path):
    cue, learner, engine, cache = [
        tmp_path / name for name in ("cue", "learner", "engine", "cache")
    ]
    for path in (cue, learner, engine, cache / "SPY"):
        path.mkdir(parents=True)
    sample = pd.DataFrame(
        dict(
            sample_i=[0, 1],
            day_key=["SPY/20230103"] * 2,
            ticker=["SPY"] * 2,
            date=["20230103"] * 2,
            action_id=[5, 7],
            state_i=[100, 105],
            weight=[0.5, 1.5],
        )
    )
    sample.to_parquet(learner / "training_sample.parquet", index=False)
    raw_path = cache / "SPY/20230103.npz"
    np.savez_compressed(raw_path, **raw_fixture())
    builder.checkpoint.atomic_json(
        raw_path.with_suffix(".json"),
        {"ticker": "SPY", "date": "20230103", "sha256": builder.sha(raw_path)},
    )
    pd.DataFrame(
        [
            dict(
                ticker="SPY",
                date="20230103",
                status="COMPLETE",
                cache_path=str(raw_path),
                cache_npz_sha256=builder.sha(raw_path),
                cache_meta_sha256=builder.sha(raw_path.with_suffix(".json")),
            )
        ]
    ).to_parquet(engine / "index.parquet", index=False)
    builder.checkpoint.atomic_json(
        learner / "freeze.json",
        {
            "artifacts": {
                "training_sample.parquet": builder.sha(
                    learner / "training_sample.parquet"
                )
            }
        },
    )
    learner_audit, engine_audit = (
        tmp_path / "learner_audit.json",
        tmp_path / "engine_audit.json",
    )
    builder.checkpoint.atomic_json(
        learner_audit,
        {
            "status": "PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT",
            "binding": {
                "learner_root": str(learner),
                "freeze_sha256": builder.sha(learner / "freeze.json"),
            },
        },
    )
    builder.checkpoint.atomic_json(
        engine_audit,
        {
            "status": "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT",
            "binding": {
                "engine_root": str(engine),
                "index_sha256": builder.sha(engine / "index.parquet"),
            },
        },
    )
    contract = {
        "authorities": {
            "learner_audit_sha256": builder.sha(learner_audit),
            "engine_audit_sha256": builder.sha(engine_audit),
        },
        "sources": {
            str(path): builder.sha(path)
            for path in (learner / "training_sample.parquet", engine / "index.parquet")
        },
        "schema": {"column_names": [f"base_{i}" for i in range(152)]},
    }
    builder.checkpoint.atomic_json(cue / "run_contract.json", contract)
    binding = builder.sha(cue / "run_contract.json")
    x = np.arange(304, dtype=np.float32).reshape(2, 152)
    np.save(cue / "train_x.npy", x)
    (cue / "cue_net.txt").write_bytes(b"sealed control, never imported")
    builder.checkpoint.atomic_json(
        cue / "matrix.complete.json",
        {
            "status": "COMPLETE",
            "binding": binding,
            "files": {"train_x.npy": builder.sha(cue / "train_x.npy")},
            "extra": {"source_hashes": {}},
        },
    )
    builder.checkpoint.atomic_json(
        cue / "model.complete.json",
        {
            "status": "COMPLETE",
            "binding": binding,
            "files": {
                "cue_net.txt": builder.sha(cue / "cue_net.txt"),
                "matrix.complete.json": builder.sha(cue / "matrix.complete.json"),
            },
        },
    )
    chunk = cue / "chunks/SPY/20230103.npz"
    chunk.parent.mkdir(parents=True)
    np.savez_compressed(
        chunk,
        sample_i=sample.sample_i.to_numpy(),
        action_id=sample.action_id.to_numpy(),
        state_i=sample.state_i.to_numpy(),
        x=x,
    )
    builder.checkpoint.atomic_json(
        cue / "chunks/SPY/20230103.complete.json",
        {
            "status": "COMPLETE",
            "binding": binding,
            "files": {str(chunk.relative_to(cue)): builder.sha(chunk)},
            "extra": {"source_hashes": {}},
        },
    )
    pins = {name: builder.sha(cue / name) for name in builder.PINNED}
    return (cue, learner, engine, cache, learner_audit, engine_audit), pins


def test_real_inputs_synthetic_authority_to_final_matrix_and_mutation(tmp_path):
    paths, pins = make_authorities(tmp_path)
    source = builder.Inputs(*paths, pins=pins, expected_rows=2)
    evidence = builder.checkpoint.Checkpoints(tmp_path / "output", "newbinding")
    builder.prepare(source, evidence)
    assert np.load(evidence.root / "train_x.npy").shape == (2, 424)
    raw = paths[3] / "SPY/20230103.npz"
    raw.write_bytes(b"corrupt source")
    with pytest.raises(ValueError, match="Source differs"):
        builder.prepare(source, evidence)


def test_source_identity_and_control_matrix_are_not_positionally_assumed(tmp_path):
    paths, pins = make_authorities(tmp_path)
    source = builder.Inputs(*paths, pins=pins, expected_rows=2)
    wrong = source.sample.copy()
    wrong["action_id"] = [7, 5]
    with pytest.raises(ValueError, match="sample identity"):
        source.day("SPY/20230103", wrong)
    with pytest.raises(ValueError, match="validation/test"):
        source.day("SPY/20250103", wrong)
    source.base._mmap.close()
    (paths[0] / "train_x.npy").write_bytes(b"mutated matrix")
    with pytest.raises(ValueError, match="Source differs"):
        builder.Inputs(*paths, pins=pins, expected_rows=2)


def test_sources_cannot_be_output_and_binary_files_synced_before_marker(
    tmp_path, monkeypatch
):
    for output in (tmp_path, tmp_path / "sources", tmp_path / "sources/subdir"):
        with pytest.raises(ValueError, match="separate"):
            builder.separate_output(output, [tmp_path / "sources"])
    builder.separate_output(tmp_path / "output", [tmp_path / "sources"])
    source = FakeSource(tmp_path)
    evidence = builder.checkpoint.Checkpoints(tmp_path / "output", "binding")
    synced = set()
    original_sync, original_finish = builder.sync_file, evidence.finish

    def sync(path):
        original_sync(path)
        synced.add(str(path))

    def finish(name, paths, extra=None):
        for path in paths:
            if path.suffix in (".npz", ".npy"):
                assert str(path) in synced
        original_finish(name, paths, extra)

    monkeypatch.setattr(builder, "sync_file", sync)
    monkeypatch.setattr(evidence, "finish", finish)
    builder.prepare(source, evidence)
