"""Small synthetic disk fixtures, never market data or fits."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import build_session_dataset as builder
from test_session_clock import frames


def test_short_disk_build_causal_seal_resume_and_tamper(tmp_path):
    greek, oi = frames()
    root = tmp_path / "raw"
    for name, frame in [("greeks", greek), ("oi", oi)]:
        source = builder.build_cache.source_path(root, "SPY", "20230103", name)
        source.parent.mkdir(parents=True)
        frame.to_parquet(source, index=False)
    day = tmp_path / "new/SPY/20230103"
    dependencies = builder.source_dependencies()
    row = builder.build_short(
        "SPY", "20230103", root, day, dependencies, "fixture-contract"
    )
    assert row["close_i"] == 210
    assert row["status"] == "COMPLETE"
    assert not row["reused_full_session"]
    assert builder.verified_resume(day, "fixture-contract") == row
    metadata = builder.read_json(day / "features.json")
    assert metadata["states"] == 136
    assert metadata["binding"]["dependencies"] == dependencies
    assert metadata["outcomes_read"] is False
    sealed = builder.read_json(day / "features_causal_freeze.json")
    assert "labels.parquet" not in sealed
    for name, digest in sealed.items():
        builder.require_hash(day / name, digest)
    with np.load(day / "cache.npz", allow_pickle=False) as arrays:
        assert arrays["time_ns"].shape == (211,)
    with np.load(day / "action_features.npz", allow_pickle=False) as arrays:
        assert arrays["action_features"].shape[1] == 33
    labels = pd.read_parquet(day / "labels.parquet")
    assert labels.exit_i.max() <= 205
    with pytest.raises(ValueError, match="contract changed"):
        builder.verified_resume(day, "different-contract")
    with (day / "features.npz").open("ab") as handle:
        handle.write(b"tamper")
    with pytest.raises(ValueError, match="hash mismatch"):
        builder.verified_resume(day, "fixture-contract")


def test_missing_member_is_not_a_valid_complete_seal(tmp_path):
    row = dict(
        cache_path="a",
        cache_meta_path="b",
        features_path="c",
        features_meta_path="d",
        action_features_path="e",
        action_features_meta_path="f",
        day_root=str(tmp_path),
    )
    builder.write_json(
        tmp_path / "complete.json", dict(contract_sha256="x", row=row, files={})
    )
    with pytest.raises(ValueError, match="membership"):
        builder.verified_resume(tmp_path, "x")


def test_incomplete_evidence_preserved_not_overwritten(tmp_path):
    day = tmp_path / "day"
    day.mkdir()
    (day / "partial.npz").write_bytes(b"old-evidence")
    assert builder.verified_resume(day, "x") is None
    assert not day.exists()
    archived = list(tmp_path.glob("day.incomplete-*"))
    assert len(archived) == 1
    assert (archived[0] / "partial.npz").read_bytes() == b"old-evidence"


def test_calendar_retains_short_days_and_rejects_wrong_flag(tmp_path):
    path = tmp_path / "calendar.csv"
    frame = pd.DataFrame(
        [
            dict(
                open="2023-07-03 13:30:00+00:00",
                close="2023-07-03 17:00:00+00:00",
                date="20230703",
                full_session=False,
            ),
            dict(
                open="2023-07-05 13:30:00+00:00",
                close="2023-07-05 20:00:00+00:00",
                date="20230705",
                full_session=True,
            ),
        ]
    )
    frame.to_csv(path, index=False)
    expected = builder.expected_days(path)
    assert len(expected) == 6
    assert sum(row["close_i"] == 210 for row in expected) == 3
    frame.loc[0, "full_session"] = True
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="flag"):
        builder.expected_days(path)
