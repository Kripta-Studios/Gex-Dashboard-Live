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


def _wrapper_sha() -> str:
    return _sha(Path(extension.__file__))


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
        source, calendar_json, json_sha, calendar_parquet, parquet_sha, output, _wrapper_sha()
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
    assert set(inventory["implementation_pins"]) == {
        "wrapper", "builder_v2", "evaluator_v2", "source_pilot", "h2_contract",
        "clock_amendment", "extension_contract", "calendar_json", "calendar_parquet",
        "calendar_manifest", "model", "transform", "conditional_means", "calibration_grid",
        "h1_evaluation_manifest", "h1_dataset_manifest",
    }

    manifest = extension.execute_reviewed_extension(
        source,
        calendar_json,
        json_sha,
        calendar_parquet,
        parquet_sha,
        output,
        _wrapper_sha(),
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
        source, calendar_json, json_sha, calendar_parquet, parquet_sha, output, _wrapper_sha()
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
            _wrapper_sha(),
            inventory,
            frozen_sha,
        )
    assert called is False


def test_tampered_inventory_receipt_fails_before_candidate_builder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    calendar_json, json_sha, calendar_parquet, parquet_sha = _calendar(tmp_path)
    output = tmp_path / "dataset"
    extension.build_reviewed_inventory(
        source, calendar_json, json_sha, calendar_parquet, parquet_sha, output, _wrapper_sha()
    )
    inventory = output / "inventory.json"
    receipt_path = output / "inventory_manifest.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["inventory.json"]["bytes"] += 1
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    frozen = extension._load_frozen(extension.BUILDER_PATH, extension.BUILDER_SHA256)
    called = False

    def forbidden(*args: object, **kwargs: object) -> None:
        nonlocal called
        called = True
        raise AssertionError("candidate builder must not run")

    monkeypatch.setattr(frozen, "build_candidates", forbidden)
    monkeypatch.setattr(extension, "_load_frozen", lambda *args: frozen)
    with pytest.raises(extension.ExtensionError, match="does not bind"):
        extension.execute_reviewed_extension(
            source, calendar_json, json_sha, calendar_parquet, parquet_sha, output,
            _wrapper_sha(), inventory, _sha(inventory),
        )
    assert called is False


def test_evaluator_change_between_phases_fails_before_candidate_builder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    calendar_json, json_sha, calendar_parquet, parquet_sha = _calendar(tmp_path)
    evaluator_copy = tmp_path / "evaluate_weekly_h2_ev_v2.py"
    evaluator_copy.write_bytes(extension.EVALUATOR_PATH.read_bytes())
    monkeypatch.setattr(extension, "EVALUATOR_PATH", evaluator_copy)
    output = tmp_path / "dataset"
    extension.build_reviewed_inventory(
        source, calendar_json, json_sha, calendar_parquet, parquet_sha, output, _wrapper_sha()
    )
    evaluator_copy.write_bytes(evaluator_copy.read_bytes() + b"\n# changed\n")
    frozen = extension._load_frozen(extension.BUILDER_PATH, extension.BUILDER_SHA256)
    called = False

    def forbidden(*args: object, **kwargs: object) -> None:
        nonlocal called
        called = True
        raise AssertionError("candidate builder must not run")

    monkeypatch.setattr(frozen, "build_candidates", forbidden)
    monkeypatch.setattr(extension, "_load_frozen", lambda *args: frozen)
    inventory = output / "inventory.json"
    with pytest.raises(extension.ExtensionError, match="evaluator_v2 pin/path guard failed"):
        extension.execute_reviewed_extension(
            source, calendar_json, json_sha, calendar_parquet, parquet_sha, output,
            _wrapper_sha(), inventory, _sha(inventory),
        )
    assert called is False


def test_frozen_state_change_during_build_fails_closing_rehash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    calendar_json, json_sha, calendar_parquet, parquet_sha = _calendar(tmp_path)
    model_path, model_sha = extension.FROZEN_STATE["model"]
    model_copy = tmp_path / "model.json"
    model_copy.write_bytes(model_path.read_bytes())
    frozen_state = dict(extension.FROZEN_STATE)
    frozen_state["model"] = (model_copy, model_sha)
    monkeypatch.setattr(extension, "FROZEN_STATE", frozen_state)
    output = tmp_path / "dataset"
    extension.build_reviewed_inventory(
        source, calendar_json, json_sha, calendar_parquet, parquet_sha, output, _wrapper_sha()
    )
    frozen = extension._load_frozen(extension.BUILDER_PATH, extension.BUILDER_SHA256)

    def mutate_during_build(*args: object, **kwargs: object) -> tuple[list[object], list[object]]:
        model_copy.write_bytes(model_copy.read_bytes() + b"\n")
        return [], []

    monkeypatch.setattr(frozen, "build_candidates", mutate_during_build)
    monkeypatch.setattr(extension, "_load_frozen", lambda *args: frozen)
    inventory = output / "inventory.json"
    with pytest.raises(extension.ExtensionError, match="model pin/path guard failed"):
        extension.execute_reviewed_extension(
            source, calendar_json, json_sha, calendar_parquet, parquet_sha, output,
            _wrapper_sha(), inventory, _sha(inventory),
        )


def test_same_size_inventory_change_during_build_fails_closing_rehash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    calendar_json, json_sha, calendar_parquet, parquet_sha = _calendar(tmp_path)
    output = tmp_path / "dataset"
    extension.build_reviewed_inventory(
        source, calendar_json, json_sha, calendar_parquet, parquet_sha, output, _wrapper_sha()
    )
    inventory = output / "inventory.json"
    original = inventory.read_bytes()
    changed = original.replace(
        b"Q3_PARTIAL_2026_SEEN_DEVELOPMENT",
        b"X3_PARTIAL_2026_SEEN_DEVELOPMENT",
        1,
    )
    assert len(changed) == len(original) and changed != original
    frozen = extension._load_frozen(extension.BUILDER_PATH, extension.BUILDER_SHA256)

    def mutate_during_build(*args: object, **kwargs: object) -> tuple[list[object], list[object]]:
        inventory.write_bytes(changed)
        return [], []

    monkeypatch.setattr(frozen, "build_candidates", mutate_during_build)
    monkeypatch.setattr(extension, "_load_frozen", lambda *args: frozen)
    with pytest.raises(extension.ExtensionError, match="inventory binding changed"):
        extension.execute_reviewed_extension(
            source, calendar_json, json_sha, calendar_parquet, parquet_sha, output,
            _wrapper_sha(), inventory, _sha(inventory),
        )
    assert not any((output / name).exists() for name in ("candidates.jsonl", "coverage.json", "manifest.json"))


@pytest.mark.parametrize("member", ["builder", "helper"])
def test_frozen_import_link_is_rejected_before_resolve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, member: str) -> None:
    target = extension.BUILDER_PATH if member == "builder" else extension.HELPER_PATH
    link = tmp_path / target.name
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    if member == "builder":
        monkeypatch.setattr(extension, "BUILDER_PATH", link)
        with pytest.raises(extension.ExtensionError, match="builder link/reparse forbidden"):
            extension._load_frozen(link, extension.BUILDER_SHA256)
    else:
        monkeypatch.setattr(extension, "HELPER_PATH", link)
        source = tmp_path / "source"
        source.mkdir()
        calendar_json, json_sha, calendar_parquet, parquet_sha = _calendar(tmp_path)
        with pytest.raises(extension.ExtensionError, match="helper link/reparse forbidden"):
            extension.prepare_inventory_payload(
                source, calendar_json, json_sha, calendar_parquet, parquet_sha, _wrapper_sha()
            )
