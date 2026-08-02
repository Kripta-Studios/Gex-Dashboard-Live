#!/usr/bin/env python3
"""Export the workbook's static Matrix and IV Regime Map into verified v2 JSON."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.king_node_contract import (  # noqa: E402
    CATALOGUE_SHA256,
    REFERENCE_SCHEMA_VERSION,
    WORKBOOK_SHA256,
    canonical_reference_checksum,
    validate_reference,
)
from scripts.audit_king_node_workbook import (  # noqa: E402
    MAIN_NS,
    NS,
    _column_label,
    _read_xlsx_formulas,
    _sha256_file,
    _workbook_sheets,
    audit_workbook,
)


MATRIX_FIELDS = (
    "key",
    "iv",
    "gamma",
    "zomma",
    "dex",
    "vex",
    "vega",
    "vomma",
    "speed",
    "phenomenon",
    "dealer_is",
    "dealers_action",
    "action",
    "regime",
    "tilt",
    "charm_neg",
    "charm_pos",
    "support_levels",
    "resistance_levels",
)
IV_FIELDS = (
    "gamma",
    "vix",
    "vvix",
    "vix1d",
    "regime",
    "lean",
    "outcome",
    "notes",
    "my_regime_iv",
    "key_auto",
    "iv",
)


def _shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(item.itertext()) for item in root.findall("m:si", NS)]


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> tuple[Any, str]:
    cell_type = cell.attrib.get("t", "n")
    value_node = cell.find("m:v", NS)
    inline = cell.find("m:is", NS)
    raw = value_node.text if value_node is not None else None
    if cell_type == "s":
        if raw is None:
            return None, cell_type
        return shared_strings[int(raw)], cell_type
    if cell_type == "inlineStr":
        return ("".join(inline.itertext()) if inline is not None else ""), cell_type
    if cell_type in {"str", "e"}:
        return raw, cell_type
    if cell_type == "b":
        return raw == "1", cell_type
    if raw is None:
        return None, cell_type
    try:
        parsed = float(raw)
    except ValueError:
        return raw, cell_type
    return (int(parsed) if parsed.is_integer() else parsed), cell_type


def _sheet_cells(archive: ZipFile, sheet_name: str) -> dict[str, tuple[Any, str, str | None]]:
    shared_strings = _shared_strings(archive)
    members = dict(_workbook_sheets(archive))
    member = members[sheet_name]
    root = ET.fromstring(archive.read(member))
    output: dict[str, tuple[Any, str, str | None]] = {}
    for cell in root.findall(".//m:c", NS):
        value, cell_type = _cell_value(cell, shared_strings)
        formula = cell.find("m:f", NS)
        output[cell.attrib["r"]] = (
            value,
            cell_type,
            None if formula is None else (formula.text or ""),
        )
    return output


def _row(cells: dict[str, tuple[Any, str, str | None]], row: int, count: int) -> tuple[list[Any], list[str], list[str | None]]:
    values: list[Any] = []
    types: list[str] = []
    formulas: list[str | None] = []
    for column in range(1, count + 1):
        value, cell_type, formula = cells.get(
            f"{_column_label(column)}{row}", (None, "missing", None)
        )
        values.append(value)
        types.append(cell_type)
        formulas.append(formula)
    return values, types, formulas


def _label_map(fields: tuple[str, ...], values: list[Any]) -> dict[str, Any]:
    return {field: values[index] for index, field in enumerate(fields)}


def _export_matrix(cells: dict[str, tuple[Any, str, str | None]]) -> tuple[dict[str, Any], dict[str, Any]]:
    headers, _, _ = _row(cells, 1, 19)
    if tuple(headers) != (
        "KEY", "IV", "Gamma", "Zomma", "Dex", "Vex", "Vega", "Vomma", "Speed",
        "Phenomenon", "DealerIs", "DealersAction", "Action", "Regime", "Tilt", "CharmNeg",
        "CharmPos", "SupportLvls", "ResistLvls",
    ):
        raise ValueError("Matrix A1:S1 labels do not match the frozen workbook contract")
    matrix: dict[str, Any] = {}
    duplicate_keys: list[str] = []
    cell_types: Counter[str] = Counter()
    for row_number in range(2, 80):
        values, types, _ = _row(cells, row_number, 19)
        cell_types.update(types)
        if values[0] in (None, ""):
            continue
        key = str(values[0])
        if key in matrix:
            duplicate_keys.append(key)
            continue
        entry = _label_map(MATRIX_FIELDS, values)
        entry.pop("key")
        entry["source_row"] = row_number
        matrix[key] = entry
    if not matrix:
        raise ValueError("Matrix export is empty")
    return matrix, {
        "sheet": "Matrix",
        "range": "A1:S79",
        "labels": headers,
        "cell_type_counts": dict(sorted(cell_types.items())),
        "non_empty_rows": len(matrix),
        "duplicate_keys": duplicate_keys,
    }


def _export_iv_map(cells: dict[str, tuple[Any, str, str | None]]) -> tuple[dict[str, Any], dict[str, Any]]:
    headers, _, _ = _row(cells, 1, 11)
    expected = (
        "Gamma", "VIX", "VVIX", "VIX1D", "Regime", "Lean", "Outcome", "Notes",
        "My Regime (IV)", "Key (auto)", "IV (auto)",
    )
    if tuple(headers) != expected:
        raise ValueError("IV Regime Map A1:K1 labels do not match the frozen workbook contract")
    result: dict[str, Any] = {}
    duplicate_keys: list[str] = []
    stale_cached_keys: list[dict[str, Any]] = []
    cell_types: Counter[str] = Counter()
    for row_number in range(2, 56):
        values, types, formulas = _row(cells, row_number, 11)
        cell_types.update(types)
        if values[0] in (None, ""):
            continue
        materialized_key = "|".join(str(values[index]) for index in range(4))
        cached_key = values[9]
        if cached_key not in (None, "", materialized_key):
            stale_cached_keys.append(
                {"row": row_number, "cached_key": cached_key, "materialized_key": materialized_key}
            )
        if materialized_key in result:
            duplicate_keys.append(materialized_key)
            continue
        entry = _label_map(IV_FIELDS, values)
        entry["key_auto"] = materialized_key
        entry["key_formula"] = f"={formulas[9]}" if formulas[9] else None
        entry["source_row"] = row_number
        result[materialized_key] = entry
    if not result:
        raise ValueError("IV Regime Map export is empty")
    return result, {
        "sheet": "IV Regime Map",
        "range": "A1:K55",
        "labels": headers,
        "cell_type_counts": dict(sorted(cell_types.items())),
        "non_empty_rows": len(result),
        "materialized_key_column": "J",
        "duplicate_keys": duplicate_keys,
        "stale_cached_keys": stale_cached_keys,
    }


def export_reference(workbook_path: Path, catalogue_path: Path) -> dict[str, Any]:
    """Produce a self-validating static reference from the frozen source pair."""

    if _sha256_file(workbook_path) != WORKBOOK_SHA256:
        raise ValueError("workbook SHA256 does not match frozen v2 authority")
    if _sha256_file(catalogue_path) != CATALOGUE_SHA256:
        raise ValueError("catalogue SHA256 does not match frozen v2 authority")
    coverage = audit_workbook(workbook_path, catalogue_path)
    with ZipFile(workbook_path) as archive:
        matrix, matrix_metadata = _export_matrix(_sheet_cells(archive, "Matrix"))
        iv_map, iv_metadata = _export_iv_map(_sheet_cells(archive, "IV Regime Map"))
    duplicate_keys = sorted(
        set(matrix_metadata["duplicate_keys"]) | set(iv_metadata["duplicate_keys"])
    )
    if duplicate_keys:
        raise ValueError("static export contains duplicate keys: " + ", ".join(duplicate_keys))
    reference: dict[str, Any] = {
        "schema_version": REFERENCE_SCHEMA_VERSION,
        "status": "verified",
        "authority": {
            "workbook_sha256": WORKBOOK_SHA256,
            "catalogue_sha256": CATALOGUE_SHA256,
            "workbook_member_sha256": coverage["authority"]["workbook_member_sha256"],
            "formula_coverage_checksum": coverage["canonical_checksum"],
        },
        "ranges": {
            "matrix": matrix_metadata,
            "iv_regime_map": iv_metadata,
        },
        "matrix": matrix,
        "iv_regime_map": iv_map,
        "integrity": {
            "matrix_rows": len(matrix),
            "iv_regime_rows": len(iv_map),
            "duplicate_keys": [],
            "iv_materialized_key_cache_mismatches": iv_metadata["stale_cached_keys"],
        },
    }
    if reference["integrity"]["iv_materialized_key_cache_mismatches"]:
        raise ValueError("IV Regime Map has stale cached keys")
    reference["canonical_checksum"] = canonical_reference_checksum(reference)
    validate_reference(reference)
    return reference


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", required=True, type=Path)
    parser.add_argument("--catalogue", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    reference = export_reference(arguments.workbook, arguments.catalogue)
    _write(arguments.output, reference)
    print(
        "KING_NODE_REFERENCE_EXPORT_OK "
        f"matrix={len(reference['matrix'])} iv_map={len(reference['iv_regime_map'])} "
        f"checksum={reference['canonical_checksum']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
