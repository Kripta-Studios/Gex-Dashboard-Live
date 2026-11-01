from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import extract_weekly_context_1030 as extractor


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def schema() -> dict[str, Any]:
    return {
        "version": "SESSION_CLOCK_FEATURES_V1",
        "base_names": [f"b{i:02d}" for i in range(81)],
        "token_names": [f"t{i:02d}" for i in range(45)],
        "map_names": ["fib", "call_oi", "put_oi", "call_gamma", "put_gamma"],
        "action_names": [f"a{i:02d}" for i in range(33)],
        "base_dim": 81,
        "token_dim": 45,
        "action_dim": 33,
        "bars": {"5m": 12, "15m": 8},
    }


def arrays(
    close_i: int,
    *,
    state_valid: bool,
    invalid_bar: bool = False,
    extra_action: bool = False,
) -> dict[str, np.ndarray]:
    state_i = np.arange(60, close_i - 14, dtype=np.int16)
    n = len(state_i)
    result = {
        "state_i": state_i,
        "base": np.zeros((n, 81), dtype=np.float32),
        "tokens": np.zeros((n, 20, 45), dtype=np.float32),
        "maps": np.zeros((n, 20, 5, 64), dtype=np.float32),
        "token_mask": np.zeros((n, 20), dtype=np.bool_),
        "bar_mask": np.zeros((n, 20), dtype=np.bool_),
        "map_mask": np.zeros((n, 20, 5), dtype=np.float32),
        "bar_end_i": np.full((n, 20), -1, dtype=np.int16),
        "state_valid": np.full(n, state_valid, dtype=np.bool_),
    }
    result["base"][0] = np.arange(81, dtype=np.float32)
    result["token_mask"][:, 0] = True
    result["bar_mask"][:, 0] = True
    result["bar_end_i"][:, 0] = state_i - 1
    if invalid_bar:
        result["bar_end_i"][0, 0] = 60
    if extra_action:
        result["actions"] = np.zeros((n, 33), dtype=np.float32)
    return result


def array_schema(close_i: int) -> dict[str, Any]:
    expected = extractor._expected_array_schema(close_i, 81, 45, 5)
    return {
        name: {"shape": list(shape), "dtype": dtype}
        for name, (shape, dtype) in expected.items()
    }


def fixture_config(
    tmp_path: Path, *, invalid_bar: bool = False, extra_action: bool = False
) -> tuple[extractor.ExtractionConfig, dict[str, Path]]:
    dataset = tmp_path / "dataset"
    features = tmp_path / "features"
    dataset.mkdir()
    features.mkdir()
    feature_schema = schema()
    rows = []
    paths: dict[str, Path] = {}
    for ticker, day, close_i, full, valid in (
        ("QQQ", "20250102", 390, True, False),
        ("SPXW", "20250703", 210, False, True),
    ):
        npz = (
            (features / ticker / day / "features.npz")
            if full
            else (dataset / "short" / ticker / day / "features.npz")
        )
        meta = (
            (dataset / "references" / ticker / day / "features.json")
            if full
            else (dataset / "short" / ticker / day / "features.json")
        )
        npz.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            npz,
            **arrays(
                close_i,
                state_valid=valid,
                invalid_bar=invalid_bar and full,
                extra_action=extra_action and full,
            ),
        )
        metadata = {
            "version": "SESSION_CLOCK_FEATURES_V1",
            "ticker": ticker,
            "date": day,
            "sha256": sha(npz),
            "schema": feature_schema,
            "outcomes_read": False,
            "session_clock": {"close_i": close_i, "first_state": 60},
            "array_schema": array_schema(close_i),
        }
        write_json(meta, metadata)
        paths[f"{ticker}_npz"] = npz
        rows.append(
            {
                "ticker": ticker,
                "date": day,
                "status": "COMPLETE",
                "close_i": close_i,
                "reused_full_session": full,
                "features_path": str(npz),
                "features_meta_path": str(meta),
                "features_sha256": sha(npz),
                "features_meta_sha256": sha(meta),
            }
        )
    rows.append(
        {
            "ticker": "SPY",
            "date": "20260401",
            "status": "MISSING_SOURCE",
            "close_i": 390,
            "reused_full_session": False,
            "features_path": None,
            "features_meta_path": None,
            "features_sha256": None,
            "features_meta_sha256": None,
        }
    )
    types = {name: pa.string() for name in extractor.INDEX_COLUMNS}
    types["close_i"], types["reused_full_session"] = pa.int64(), pa.bool_()
    columns: dict[str, pa.Array] = {}
    for name in extractor.INDEX_COLUMNS:
        values = []
        for row in rows:
            if name in row:
                values.append(row[name])
            elif name == "evaluation_status":
                values.append(None)
            else:
                values.append(f"unused:{name}")
        columns[name] = pa.array(values, type=types[name])
    index = dataset / "index.parquet"
    pq.write_table(pa.table(columns), index)
    dataset_contract = dataset / "dataset_contract.json"
    feature_contract = dataset / "feature_contract.json"
    completion = dataset / "completion.json"
    audit = dataset / "audit.json"
    features_py = dataset / "features.py"
    contract = dataset / "contract.md"
    write_json(dataset_contract, {"expected_days": 3})
    write_json(
        feature_contract,
        {
            "version": "SESSION_CLOCK_FEATURES_V1",
            "schema": feature_schema,
            "outcomes_read": False,
        },
    )
    write_json(completion, {"available_days": 2, "missing_days": 1})
    write_json(audit, {"status": "PASS"})
    features_py.write_text("# frozen fixture\n", encoding="utf-8")
    contract.write_text("fixture contract\n", encoding="utf-8")
    authorities = {
        "dataset_contract": (dataset_contract, sha(dataset_contract)),
        "feature_contract": (feature_contract, sha(feature_contract)),
        "completion": (completion, sha(completion)),
        "audit": (audit, sha(audit)),
        "features_py": (features_py, sha(features_py)),
        "extraction_contract": (contract, sha(contract)),
    }
    config = extractor.ExtractionConfig(
        dataset,
        features,
        index,
        sha(index),
        authorities,
        {"identities": 3, "full": 1, "short": 1, "missing": 1},
    )
    paths["index"] = index
    return config, paths


def extractor_sha() -> str:
    return sha(Path(extractor.__file__))


def test_inventory_is_metadata_only_and_preserves_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _ = fixture_config(tmp_path)
    monkeypatch.setattr(
        np,
        "load",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("NPZ opened")),
    )
    output = tmp_path / "out"
    extractor.build_reviewed_inventory(config, output, extractor_sha())
    inventory = json.loads((output / "inventory.json").read_text(encoding="utf-8"))
    assert inventory["counts"] == {"identities": 3, "full": 1, "short": 1, "missing": 1}
    assert inventory["flags"]["npz_opened"] is False
    missing = [
        row for row in inventory["identities"] if row["status"] == "MISSING_SOURCE"
    ]
    assert len(missing) == 1 and missing[0]["features"] is None


def test_two_phase_extracts_full_short_missing_and_preserves_invalid_state(
    tmp_path: Path,
) -> None:
    config, _ = fixture_config(tmp_path)
    output = tmp_path / "out"
    extractor.build_reviewed_inventory(config, output, extractor_sha())
    inventory = output / "inventory.json"
    manifest = extractor.execute_reviewed_extraction(
        config, output, inventory, sha(inventory), extractor_sha()
    )
    rows = [
        json.loads(line)
        for line in (output / "context.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 3 and manifest["counts"]["identities"] == 3
    full = next(row for row in rows if row["ticker"] == "QQQ")
    short = next(row for row in rows if row["ticker"] == "SPXW")
    missing = next(row for row in rows if row["ticker"] == "SPY")
    assert full["state_valid"] is False and full["context_81"] == [
        float(i) for i in range(81)
    ]
    assert short["close_i"] == 210 and short["state_valid"] is True
    assert (
        missing["status"] == "CONTEXT_MISSING_SOURCE" and missing["context_81"] is None
    )
    assert len(full["token_mask_20"]) == 20 and len(full["map_mask_20x5"]) == 20
    assert (
        manifest["flags"]["outcomes_read"] is False and len(manifest["npz_inputs"]) == 2
    )


def test_npz_hash_change_fails_before_array_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, paths = fixture_config(tmp_path)
    output = tmp_path / "out"
    extractor.build_reviewed_inventory(config, output, extractor_sha())
    path = paths["QQQ_npz"]
    data = bytearray(path.read_bytes())
    data[-1] ^= 1
    path.write_bytes(data)
    called = False
    original = np.load

    def tracking(*args: Any, **kwargs: Any):
        nonlocal called
        called = True
        return original(*args, **kwargs)

    monkeypatch.setattr(np, "load", tracking)
    inventory = output / "inventory.json"
    with pytest.raises(extractor.ContextError, match="NPZ SHA-256 mismatch"):
        extractor.execute_reviewed_extraction(
            config, output, inventory, sha(inventory), extractor_sha()
        )
    assert called is False


@pytest.mark.parametrize(
    ("invalid_bar", "extra_action", "message"),
    [(True, False, "not causal"), (False, True, "array name closure")],
)
def test_causal_bar_and_array_closure_fail_closed(
    tmp_path: Path, invalid_bar: bool, extra_action: bool, message: str
) -> None:
    config, _ = fixture_config(
        tmp_path, invalid_bar=invalid_bar, extra_action=extra_action
    )
    output = tmp_path / "out"
    extractor.build_reviewed_inventory(config, output, extractor_sha())
    inventory = output / "inventory.json"
    with pytest.raises(extractor.ContextError, match=message):
        extractor.execute_reviewed_extraction(
            config, output, inventory, sha(inventory), extractor_sha()
        )
    assert not (output / "context.jsonl").exists()


def test_feature_path_escape_is_rejected(tmp_path: Path) -> None:
    config, paths = fixture_config(tmp_path)
    table = pq.read_table(paths["index"])
    values = table.column("features_path").to_pylist()
    outside = tmp_path / "outside.npz"
    outside.write_bytes(paths["QQQ_npz"].read_bytes())
    values[0] = str(outside)
    table = table.set_column(
        table.schema.get_field_index("features_path"),
        "features_path",
        pa.array(values, type=pa.string()),
    )
    pq.write_table(table, paths["index"])
    changed = extractor.ExtractionConfig(
        config.dataset_root,
        config.features_root,
        config.index_path,
        sha(config.index_path),
        config.authorities,
        config.expected_counts,
    )
    with pytest.raises(extractor.ContextError, match="outside declared root"):
        extractor.prepare_inventory_payload(changed, extractor_sha())


def test_feature_symlink_is_rejected_before_inventory(tmp_path: Path) -> None:
    config, paths = fixture_config(tmp_path)
    link = config.features_root / "linked.npz"
    try:
        link.symlink_to(paths["QQQ_npz"])
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    table = pq.read_table(paths["index"])
    values = table.column("features_path").to_pylist()
    values[0] = str(link)
    table = table.set_column(
        table.schema.get_field_index("features_path"),
        "features_path",
        pa.array(values, type=pa.string()),
    )
    pq.write_table(table, paths["index"])
    changed = extractor.ExtractionConfig(
        config.dataset_root,
        config.features_root,
        config.index_path,
        sha(config.index_path),
        config.authorities,
        config.expected_counts,
    )
    with pytest.raises(extractor.ContextError, match="link/reparse forbidden"):
        extractor.prepare_inventory_payload(changed, extractor_sha())
