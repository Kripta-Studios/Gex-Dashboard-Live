from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import build_weekly_h2_q3_partial_extension as extension


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _calendar(tmp_path: Path) -> tuple[Path, str, Path, str]:
    rows = [
        {"ticker": ticker, "date": day, "close_i": 390}
        for ticker in extension.TICKERS
        for day in extension.DATES
    ]
    json_path = tmp_path / "calendar.json"
    json_path.write_text(
        json.dumps(
            {"schema": "weekly_h2_q3_partial_calendar_v1", "sessions": list(extension.DATES), "rows": rows},
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    parquet_path = tmp_path / "calendar.parquet"
    pq.write_table(
        pa.table(
            {
                "ticker": pa.array([row["ticker"] for row in rows], type=pa.string()),
                "date": pa.array([row["date"] for row in rows], type=pa.string()),
                "close_i": pa.array([row["close_i"] for row in rows], type=pa.int64()),
            }
        ),
        parquet_path,
    )
    return json_path, _sha(json_path), parquet_path, _sha(parquet_path)


def test_two_phase_fixture_preserves_165_rows_and_terminal_horizon(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    calendar_json, json_sha, calendar_parquet, parquet_sha = _calendar(tmp_path)
    output = tmp_path / "dataset"

    receipt = extension.build_reviewed_inventory(
        source, calendar_json, json_sha, calendar_parquet, parquet_sha, output
    )
    inventory_path = output / "inventory.json"
    inventory_sha = _sha(inventory_path)
    assert receipt["schema"] == "weekly_h2_q3_partial_inventory_manifest_v1"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    assert len(inventory["calendar_rows"]) == 165
    assert len(inventory["coverage_plan"]) == 165
    assert inventory["sources"] == []
    assert inventory["implementation_pins"]["evaluator_v2"] == {
        "path": str(extension.EVALUATOR_PATH), "sha256": extension.EVALUATOR_SHA256
    }
    assert inventory["implementation_pins"]["h1_dataset_manifest"] == {
        "path": str(extension.H1_DATASET_ROOT / "manifest.json"),
        "sha256": "bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8",
    }

    manifest = extension.execute_reviewed_extension(
        source,
        calendar_json,
        json_sha,
        calendar_parquet,
        parquet_sha,
        output,
        inventory_path,
        inventory_sha,
    )
    coverage = json.loads((output / "coverage.json").read_text(encoding="utf-8"))
    terminal = [row for row in coverage["rows"] if row["entry_date"] in {"20260916", "20260917"}]
    assert len(terminal) == 6
    assert all(row["status"] == "HORIZON_OUTSIDE_CALENDAR" for row in terminal)
    assert all(row["candidate_ids"] == [] for row in terminal)
    assert manifest["schema"] == "weekly_h2_q3_partial_dataset_manifest_v1"
    assert manifest["status"] == extension.STATUS
    assert manifest["split"] == extension.SPLIT
    assert set(manifest["files"]) == {
        "candidates.jsonl", "coverage.json", "inventory.json", "inventory_manifest.json"
    }
    assert all(set(pin) == {"bytes", "sha256"} for pin in manifest["files"].values())
    assert (output / "candidates.jsonl").read_text(encoding="utf-8") == ""


def test_calendar_rejects_49_date_intersection_and_json_parquet_difference(tmp_path: Path) -> None:
    calendar_json, json_sha, calendar_parquet, parquet_sha = _calendar(tmp_path)
    builder = extension._load_frozen(extension.BUILDER_PATH, extension.BUILDER_SHA256)
    pilot = builder.load_pilot(extension.HELPER_PATH, extension.HELPER_SHA256)
    payload = json.loads(calendar_json.read_text(encoding="utf-8"))
    payload["sessions"] = payload["sessions"][6:]
    calendar_json.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(extension.ExtensionError, match="55-session membership"):
        extension.read_calendar_pair(
            calendar_json, _sha(calendar_json), calendar_parquet, parquet_sha, pilot
        )

    calendar_json, json_sha, calendar_parquet, parquet_sha = _calendar(tmp_path)
    table = pq.read_table(calendar_parquet)
    changed = table.set_column(2, "close_i", pa.array([389] + [390] * 164, type=pa.int64()))
    pq.write_table(changed, calendar_parquet)
    with pytest.raises(extension.ExtensionError, match="non-regular close_i"):
        extension.read_calendar_pair(
            calendar_json, json_sha, calendar_parquet, _sha(calendar_parquet), pilot
        )


def test_execute_rejects_inventory_change_before_candidate_builder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    calendar_json, json_sha, calendar_parquet, parquet_sha = _calendar(tmp_path)
    output = tmp_path / "dataset"
    extension.build_reviewed_inventory(
        source, calendar_json, json_sha, calendar_parquet, parquet_sha, output
    )
    inventory = output / "inventory.json"
    frozen_sha = _sha(inventory)
    value = json.loads(inventory.read_text(encoding="utf-8"))
    value["split"] = "TAMPERED"
    inventory.write_text(json.dumps(value), encoding="utf-8")

    called = False

    def forbidden(*args: object, **kwargs: object) -> None:
        nonlocal called
        called = True
        raise AssertionError("candidate builder must not run")

    frozen = extension._load_frozen(extension.BUILDER_PATH, extension.BUILDER_SHA256)
    monkeypatch.setattr(frozen, "build_candidates", forbidden)
    with pytest.raises(extension.ExtensionError, match="binding failed"):
        extension.execute_reviewed_extension(
            source,
            calendar_json,
            json_sha,
            calendar_parquet,
            parquet_sha,
            output,
            inventory,
            frozen_sha,
        )
    assert called is False
