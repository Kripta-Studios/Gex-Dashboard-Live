#!/usr/bin/env python3
"""Build the deterministic KING NODE v2 workbook/catalogue coverage ledger.

The workbook is read directly as an OOXML zip package.  This intentionally does
not depend on Excel, LibreOffice, pandas, or openpyxl: shared-formula followers,
array formulas, conditional formatting, and validation XML are all preserved from
the source package.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable
from xml.etree import ElementTree as ET
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.king_node_contract import (  # noqa: E402
    CATALOGUE_SHA256,
    FORMULA_CLASSIFICATIONS,
    WORKBOOK_SHA256,
    FormulaClassification,
    canonical_json_bytes,
    sha256_json,
)


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN_NS, "r": REL_NS, "pr": PACKAGE_REL_NS}
CELL_COORDINATE = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*)$")
FORMULA_LINE = re.compile(r"^([A-Z]{1,3}[1-9][0-9]*)\t([^\t]+)\t(=.*)$")
CELL_REFERENCE = re.compile(
    r"(?<![A-Z0-9_])((?:'[^']+'|[A-Za-z_][A-Za-z0-9_.]*)!)?(\$?)([A-Z]{1,3})(\$?)([1-9][0-9]*)"
)

SHEET_CLASSIFICATION = {
    "Master Dashboard": FormulaClassification.PRESENTATION_RULE.value,
    "Dashboard": FormulaClassification.PRESENTATION_RULE.value,
    "King Node Model": FormulaClassification.RUNTIME_CALCULATION.value,
    "GEX Depth": FormulaClassification.RUNTIME_CALCULATION.value,
    "Technical Analysis": FormulaClassification.RUNTIME_CALCULATION.value,
    "Level Engine": FormulaClassification.RUNTIME_CALCULATION.value,
    "Level Test Log": FormulaClassification.HISTORICAL_LOG.value,
    "IV Regime Map": FormulaClassification.STATIC_REFERENCE_EXPORT.value,
}


@dataclass(frozen=True)
class FormulaCell:
    sheet: str
    cell: str
    formula_type: str
    formula: str
    formula_sha256: str
    canonical_formula: str
    canonical_sha256: str
    shared_index: str | None = None
    shared_master: str | None = None
    array_ref: str | None = None

    @property
    def key(self) -> str:
        return f"{self.sheet}!{self.cell}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _column_index(label: str) -> int:
    value = 0
    for char in label:
        value = value * 26 + ord(char) - ord("A") + 1
    return value


def _column_label(value: int) -> str:
    output = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        output = chr(ord("A") + remainder) + output
    return output


def _coordinate(value: str) -> tuple[int, int]:
    match = CELL_COORDINATE.match(value)
    if not match:
        raise ValueError(f"invalid A1 coordinate: {value!r}")
    return _column_index(match.group(1)), int(match.group(2))


def _with_quotes_protected(formula: str, transform: Any) -> str:
    """Apply a reference transform outside Excel string literals only."""

    output: list[str] = []
    index = 0
    in_string = False
    chunk_start = 0
    while index < len(formula):
        if formula[index] != '"':
            index += 1
            continue
        if not in_string:
            output.append(transform(formula[chunk_start:index]))
            chunk_start = index
            in_string = True
            index += 1
            continue
        if index + 1 < len(formula) and formula[index + 1] == '"':
            index += 2
            continue
        output.append(formula[chunk_start : index + 1])
        chunk_start = index + 1
        in_string = False
        index += 1
    if in_string:
        # An unterminated literal is kept intact.  It is source evidence, not an
        # invitation for the auditor to repair a formula.
        output.append(formula[chunk_start:])
    else:
        output.append(transform(formula[chunk_start:]))
    return "".join(output)


def _translate_formula(formula: str, origin: str, destination: str) -> str:
    """Expand an OOXML shared formula from its master to one follower cell."""

    origin_col, origin_row = _coordinate(origin)
    destination_col, destination_row = _coordinate(destination)
    column_delta = destination_col - origin_col
    row_delta = destination_row - origin_row

    def replace(match: re.Match[str]) -> str:
        prefix, col_dollar, column, row_dollar, row = match.groups()
        column_value = _column_index(column)
        row_value = int(row)
        if not col_dollar:
            column_value += column_delta
        if not row_dollar:
            row_value += row_delta
        # A malformed relative reference is preserved verbatim so the source can
        # still be represented and the audit does not invent a repaired formula.
        if column_value < 1 or row_value < 1:
            return match.group(0)
        return (
            f"{prefix or ''}{col_dollar}{_column_label(column_value)}"
            f"{row_dollar}{row_value}"
        )

    return _with_quotes_protected(formula, lambda text: CELL_REFERENCE.sub(replace, text))


def _canonical_formula(formula: str, owner: str) -> str:
    """Convert A1 references to position-independent R1C1-like markers."""

    owner_col, owner_row = _coordinate(owner)

    def replace(match: re.Match[str]) -> str:
        prefix, col_dollar, column, row_dollar, row = match.groups()
        column_value = _column_index(column)
        row_value = int(row)
        canonical_col = (
            f"C{column_value}"
            if col_dollar
            else f"C[{column_value - owner_col}]"
        )
        canonical_row = f"R{row_value}" if row_dollar else f"R[{row_value - owner_row}]"
        return f"{prefix or ''}{canonical_col}{canonical_row}"

    return _with_quotes_protected(formula, lambda text: CELL_REFERENCE.sub(replace, text))


def _formula_record(
    sheet: str,
    cell: str,
    formula_type: str,
    formula: str,
    *,
    shared_index: str | None = None,
    shared_master: str | None = None,
    array_ref: str | None = None,
) -> FormulaCell:
    expanded = formula if formula.startswith("=") else f"={formula}"
    canonical = _canonical_formula(expanded, cell)
    return FormulaCell(
        sheet=sheet,
        cell=cell,
        formula_type=formula_type,
        formula=expanded,
        formula_sha256=_sha256_bytes(expanded),
        canonical_formula=canonical,
        canonical_sha256=_sha256_bytes(canonical),
        shared_index=shared_index,
        shared_master=shared_master,
        array_ref=array_ref,
    )


def _workbook_sheets(archive: ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {relation.attrib["Id"]: relation.attrib["Target"] for relation in relations}
    sheets: list[tuple[str, str]] = []
    sheet_nodes = workbook.find("m:sheets", NS)
    for sheet in ([] if sheet_nodes is None else list(sheet_nodes)):
        relationship_id = sheet.attrib[f"{{{REL_NS}}}id"]
        target = targets[relationship_id]
        member = "xl/" + target.lstrip("/")
        member = member.replace("xl/worksheets/../", "xl/")
        sheets.append((sheet.attrib["name"], member))
    return sheets


def _read_xlsx_formulas(
    workbook_path: Path,
) -> tuple[dict[str, FormulaCell], dict[str, Any], dict[str, str]]:
    formulas: dict[str, FormulaCell] = {}
    sheet_summary: dict[str, Any] = {}
    member_hashes: dict[str, str] = {}
    with ZipFile(workbook_path) as archive:
        for name in sorted(archive.namelist()):
            if name.startswith("xl/") and (name.endswith(".xml") or name.endswith(".rels")):
                member_hashes[name] = _sha256_bytes(archive.read(name))
        for sheet_name, member in _workbook_sheets(archive):
            root = ET.fromstring(archive.read(member))
            dimension = root.find("m:dimension", NS)
            masters: dict[str, tuple[str, str]] = {}
            pending: list[tuple[str, str, str | None, str | None, str | None]] = []
            for cell in root.findall(".//m:c", NS):
                formula_node = cell.find("m:f", NS)
                if formula_node is None:
                    continue
                coordinate = cell.attrib["r"]
                formula_type = formula_node.attrib.get("t", "normal")
                shared_index = formula_node.attrib.get("si")
                array_ref = formula_node.attrib.get("ref")
                text = formula_node.text
                if formula_type == "shared" and text is not None:
                    masters[shared_index or ""] = (coordinate, text)
                pending.append((coordinate, formula_type, shared_index, array_ref, text))
            type_counts: Counter[str] = Counter()
            for coordinate, formula_type, shared_index, array_ref, text in pending:
                shared_master = None
                if formula_type == "shared":
                    try:
                        master, master_formula = masters[shared_index or ""]
                    except KeyError as exc:
                        raise ValueError(
                            f"unresolved shared formula {sheet_name}!{coordinate} si={shared_index}"
                        ) from exc
                    shared_master = master
                    text = master_formula if coordinate == master else _translate_formula(
                        master_formula, master, coordinate
                    )
                if text is None:
                    raise ValueError(f"formula text missing at {sheet_name}!{coordinate}")
                record = _formula_record(
                    sheet_name,
                    coordinate,
                    formula_type,
                    text,
                    shared_index=shared_index,
                    shared_master=shared_master,
                    array_ref=array_ref,
                )
                formulas[record.key] = record
                type_counts[formula_type] += 1
            sheet_summary[sheet_name] = {
                "xml_member": member,
                "dimension": dimension.attrib.get("ref") if dimension is not None else None,
                "current_formula_cells": len(pending),
                "current_formula_types": dict(sorted(type_counts.items())),
            }
    return formulas, sheet_summary, member_hashes


def _read_catalogue_formulas(catalogue_path: Path) -> dict[str, FormulaCell]:
    formulas: dict[str, FormulaCell] = {}
    in_annex = False
    active_sheet: str | None = None
    for raw_line in catalogue_path.read_text(encoding="utf-8").splitlines():
        if raw_line == "## Anexo exhaustivo: fórmula exacta de cada celda":
            in_annex = True
            continue
        if not in_annex:
            continue
        if raw_line.startswith("### "):
            active_sheet = raw_line[4:].strip()
            continue
        if not active_sheet:
            continue
        match = FORMULA_LINE.match(raw_line)
        if not match:
            continue
        cell, type_field, formula = match.groups()
        formula_type, _, metadata = type_field.partition(";")
        formula_type = formula_type.strip()
        if formula_type not in {"normal", "shared", "array"}:
            raise ValueError(f"unexpected catalogue formula type at {active_sheet}!{cell}")
        array_ref = None
        if metadata:
            ref_match = re.search(r"\bref=([^\s]+)", metadata)
            array_ref = ref_match.group(1) if ref_match else None
        record = _formula_record(
            active_sheet,
            cell,
            formula_type,
            formula,
            array_ref=array_ref,
        )
        if record.key in formulas:
            raise ValueError(f"duplicate catalogue formula entry: {record.key}")
        formulas[record.key] = record
    if not formulas:
        raise ValueError("catalogue annex contains no formula cells")
    return formulas


def _read_non_cell_rules(workbook_path: Path) -> dict[str, list[dict[str, Any]]]:
    conditional_formatting: list[dict[str, Any]] = []
    input_validation: list[dict[str, Any]] = []
    with ZipFile(workbook_path) as archive:
        for sheet_name, member in _workbook_sheets(archive):
            root = ET.fromstring(archive.read(member))
            for block_index, block in enumerate(root.findall("m:conditionalFormatting", NS), start=1):
                for rule_index, rule in enumerate(block.findall("m:cfRule", NS), start=1):
                    formulas = [node.text or "" for node in rule.findall("m:formula", NS)]
                    record = {
                        "id": f"cf:{sheet_name}:{block_index}:{rule_index}",
                        "sheet": sheet_name,
                        "classification": FormulaClassification.CONDITIONAL_FORMATTING.value,
                        "range": block.attrib.get("sqref"),
                        "type": rule.attrib.get("type"),
                        "priority": int(rule.attrib["priority"]) if "priority" in rule.attrib else None,
                        "stop_if_true": rule.attrib.get("stopIfTrue") == "1",
                        "operator": rule.attrib.get("operator"),
                        "formulas": formulas,
                        "formula_sha256": [_sha256_bytes(item) for item in formulas],
                    }
                    conditional_formatting.append(record)
            validations = root.find("m:dataValidations", NS)
            if validations is None:
                continue
            for index, rule in enumerate(validations.findall("m:dataValidation", NS), start=1):
                slots = []
                for slot_name in ("formula1", "formula2"):
                    node = rule.find(f"m:{slot_name}", NS)
                    if node is not None:
                        slots.append(
                            {
                                "slot": slot_name,
                                "formula": node.text or "",
                                "formula_sha256": _sha256_bytes(node.text or ""),
                            }
                        )
                input_validation.append(
                    {
                        "id": f"dv:{sheet_name}:{index}",
                        "sheet": sheet_name,
                        "classification": FormulaClassification.INPUT_VALIDATION.value,
                        "range": rule.attrib.get("sqref"),
                        "type": rule.attrib.get("type"),
                        "operator": rule.attrib.get("operator"),
                        "allow_blank": rule.attrib.get("allowBlank") == "1",
                        "slots": slots,
                    }
                )
    return {
        "conditional_formatting": conditional_formatting,
        "input_validation": input_validation,
    }


def _classification_for(
    sheet: str,
    cell: str,
    current: FormulaCell | None,
    catalogue: FormulaCell | None,
) -> tuple[str, str | None]:
    if current is None and catalogue is not None:
        # The reason contains the literal cell key and retained catalogue hash; it
        # is not a blanket ignore rule for drifted material.
        return (
            FormulaClassification.NOT_RUNTIME_APPLICABLE.value,
            f"catalogue_formula_absent_from_current_xlsx_at_{sheet}!{cell}_sha256_{catalogue.formula_sha256}",
        )
    if sheet in SHEET_CLASSIFICATION:
        return SHEET_CLASSIFICATION[sheet], None
    # Formula-bearing cells on an otherwise non-formula sheet would be a new source
    # condition and must be explicit rather than silently accepted.
    raise ValueError(f"no v2 classification for current workbook formula {sheet}!{cell}")


def _family_ids(formulas: Iterable[FormulaCell], prefix: str) -> dict[str, str]:
    grouped: dict[tuple[str, str], list[FormulaCell]] = defaultdict(list)
    for formula in formulas:
        grouped[(formula.sheet, formula.canonical_sha256)].append(formula)
    output: dict[str, str] = {}
    for index, ((sheet, _), members) in enumerate(
        sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])), start=1
    ):
        family = f"{prefix}-{index:04d}"
        for member in members:
            output[member.key] = family
    return output


def _serialise_formula(record: FormulaCell | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "formula": record.formula,
        "formula_sha256": record.formula_sha256,
        "formula_type": record.formula_type,
        "canonical_formula": record.canonical_formula,
        "canonical_sha256": record.canonical_sha256,
        "shared_index": record.shared_index,
        "shared_master": record.shared_master,
        "array_ref": record.array_ref,
    }


def audit_workbook(workbook_path: Path, catalogue_path: Path) -> dict[str, Any]:
    """Return the exhaustive deterministic v2 formula coverage ledger."""

    workbook_hash = _sha256_file(workbook_path)
    catalogue_hash = _sha256_file(catalogue_path)
    if workbook_hash != WORKBOOK_SHA256:
        raise ValueError(
            f"workbook SHA256 {workbook_hash} does not match frozen authority {WORKBOOK_SHA256}"
        )
    if catalogue_hash != CATALOGUE_SHA256:
        raise ValueError(
            f"catalogue SHA256 {catalogue_hash} does not match frozen authority {CATALOGUE_SHA256}"
        )
    current, sheets, member_hashes = _read_xlsx_formulas(workbook_path)
    catalogue = _read_catalogue_formulas(catalogue_path)
    rules = _read_non_cell_rules(workbook_path)
    current_families = _family_ids(current.values(), "xlsx-family")
    catalogue_families = _family_ids(catalogue.values(), "catalogue-family")
    formula_entries: list[dict[str, Any]] = []
    classification_counts: Counter[str] = Counter()
    formula_text_exact = formula_text_changed = type_changed = current_only = catalogue_only = 0
    for key in sorted(set(current) | set(catalogue)):
        current_record = current.get(key)
        catalogue_record = catalogue.get(key)
        sheet, cell = key.split("!", 1)
        classification, reason = _classification_for(sheet, cell, current_record, catalogue_record)
        if current_record is None:
            comparison = "catalogue_only"
            catalogue_only += 1
        elif catalogue_record is None:
            comparison = "xlsx_only"
            current_only += 1
        elif current_record.formula == catalogue_record.formula:
            comparison = "formula_text_exact"
            formula_text_exact += 1
        else:
            comparison = "formula_text_changed"
            formula_text_changed += 1
        if current_record and catalogue_record and current_record.formula_type != catalogue_record.formula_type:
            type_changed += 1
        entry = {
            "key": key,
            "sheet": sheet,
            "cell": cell,
            "classification": classification,
            "not_runtime_reason": reason,
            "comparison": comparison,
            "current_family_id": current_families.get(key),
            "catalogue_family_id": catalogue_families.get(key),
            "current": _serialise_formula(current_record),
            "catalogue": _serialise_formula(catalogue_record),
        }
        formula_entries.append(entry)
        classification_counts[classification] += 1
    if set(classification_counts) - set(FORMULA_CLASSIFICATIONS):
        raise ValueError("invalid formula classifications emitted")
    if any(not entry["classification"] for entry in formula_entries):
        raise ValueError("unclassified formula entry emitted")

    family_members: dict[str, list[str]] = defaultdict(list)
    family_metadata: dict[str, tuple[FormulaCell, str]] = {}
    for record in current.values():
        family_id = current_families[record.key]
        family_members[family_id].append(record.key)
        family_metadata.setdefault(family_id, (record, SHEET_CLASSIFICATION[record.sheet]))
    for record in catalogue.values():
        if record.key in current:
            continue
        family_id = catalogue_families[record.key]
        family_members[family_id].append(record.key)
        family_metadata.setdefault(
            family_id,
            (record, FormulaClassification.NOT_RUNTIME_APPLICABLE.value),
        )
    families = []
    for family_id in sorted(family_members):
        record, classification = family_metadata[family_id]
        families.append(
            {
                "id": family_id,
                "sheet": record.sheet,
                "classification": classification,
                "canonical_formula": record.canonical_formula,
                "canonical_sha256": record.canonical_sha256,
                "members": sorted(family_members[family_id]),
            }
        )

    by_sheet_current: Counter[str] = Counter(item.sheet for item in current.values())
    by_sheet_catalogue: Counter[str] = Counter(item.sheet for item in catalogue.values())
    family_by_sheet_current: Counter[str] = Counter(
        family_metadata[family_id][0].sheet
        for family_id in current_families.values()
        if family_id in family_metadata
    )
    # `Counter` above sees one count per member; derive unique IDs for the report.
    family_by_sheet_current = Counter()
    for family_id in set(current_families.values()):
        family_by_sheet_current[family_metadata[family_id][0].sheet] += 1
    family_by_sheet_catalogue = Counter()
    catalogue_family_sheet = {
        family_id: catalogue[next(key for key, value in catalogue_families.items() if value == family_id)].sheet
        for family_id in set(catalogue_families.values())
    }
    for family_id, sheet in catalogue_family_sheet.items():
        family_by_sheet_catalogue[sheet] += 1

    for sheet_name, metadata in sheets.items():
        metadata["catalogue_formula_cells"] = by_sheet_catalogue[sheet_name]
        metadata["current_family_count"] = family_by_sheet_current[sheet_name]
        metadata["catalogue_family_count"] = family_by_sheet_catalogue[sheet_name]
    non_cell_counts = {
        "conditional_formatting_rules": len(rules["conditional_formatting"]),
        "conditional_formatting_expression_rules": sum(
            1 for item in rules["conditional_formatting"] if item["type"] == "expression"
        ),
        "input_validation_rules": len(rules["input_validation"]),
        "input_validation_slots": sum(
            len(item["slots"]) for item in rules["input_validation"]
        ),
    }
    summary = {
        "current_formula_cells": len(current),
        "catalogue_formula_cells": len(catalogue),
        "union_formula_cells": len(formula_entries),
        "overlapping_formula_cells": len(set(current) & set(catalogue)),
        "formula_text_exact": formula_text_exact,
        "formula_text_changed": formula_text_changed,
        "xlsx_only": current_only,
        "catalogue_only": catalogue_only,
        "type_changed": type_changed,
        "current_family_count": len(set(current_families.values())),
        "catalogue_family_count": len(set(catalogue_families.values())),
        "classification_counts": dict(sorted(classification_counts.items())),
        **non_cell_counts,
        "unmapped_formula_entries": 0,
        "unclassified_formula_entries": 0,
    }
    coverage = {
        "schema_version": "king-node.formula-coverage.v2",
        "authority": {
            "workbook_sha256": workbook_hash,
            "catalogue_sha256": catalogue_hash,
            "workbook_member_sha256": member_hashes,
            "current_xlsx_is_executable_authority": True,
            "catalogue_is_explanatory_versioned_authority": True,
        },
        "summary": summary,
        "sheets": [
            {"name": name, **sheets[name]}
            for name in sorted(sheets)
        ],
        "families": families,
        "formula_entries": formula_entries,
        "non_cell_rules": rules,
    }
    coverage["canonical_checksum"] = sha256_json(coverage)
    return coverage


def _markdown(coverage: dict[str, Any]) -> str:
    summary = coverage["summary"]
    lines = [
        "# KING NODE v2 Formula Coverage",
        "",
        "This file is generated by `scripts/audit_king_node_workbook.py`; do not edit it manually.",
        "",
        "## Frozen authority",
        "",
        f"- Current executable workbook SHA-256: `{coverage['authority']['workbook_sha256']}`",
        f"- Explanatory catalogue SHA-256: `{coverage['authority']['catalogue_sha256']}`",
        f"- Coverage checksum: `{coverage['canonical_checksum']}`",
        "",
        "## Reconciliation",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    for key in (
        "current_formula_cells",
        "catalogue_formula_cells",
        "union_formula_cells",
        "overlapping_formula_cells",
        "formula_text_exact",
        "formula_text_changed",
        "xlsx_only",
        "catalogue_only",
        "type_changed",
        "current_family_count",
        "catalogue_family_count",
        "conditional_formatting_rules",
        "input_validation_rules",
        "input_validation_slots",
        "unmapped_formula_entries",
        "unclassified_formula_entries",
    ):
        lines.append(f"| `{key}` | {summary[key]} |")
    lines.extend(
        [
            "",
            "The current XLSX remains executable authority. Catalogue-only entries are retained with a cell-specific absence reason; no formula is silently ignored.",
            "",
            "## Per-sheet totals",
            "",
            "| Sheet | XLSX cells | Catalogue cells | XLSX families | Catalogue families |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for sheet in coverage["sheets"]:
        lines.append(
            "| {name} | {current_formula_cells} | {catalogue_formula_cells} | {current_family_count} | {catalogue_family_count} |".format(
                **sheet
            )
        )
    lines.extend(["", "## Classification coverage", "", "| Classification | Cells |", "|---|---:|"])
    for key, value in summary["classification_counts"].items():
        lines.append(f"| `{key}` | {value} |")
    lines.append("")
    return "\n".join(lines)


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", required=True, type=Path)
    parser.add_argument("--catalogue", required=True, type=Path)
    parser.add_argument("--json", required=True, type=Path)
    parser.add_argument("--markdown", required=True, type=Path)
    arguments = parser.parse_args(argv)
    coverage = audit_workbook(arguments.workbook, arguments.catalogue)
    _write(arguments.json, json.dumps(coverage, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    _write(arguments.markdown, _markdown(coverage))
    summary = coverage["summary"]
    print(
        "KING_NODE_WORKBOOK_AUDIT_OK "
        f"xlsx={summary['current_formula_cells']} catalogue={summary['catalogue_formula_cells']} "
        f"union={summary['union_formula_cells']} families={summary['current_family_count']} "
        f"catalogue_only={summary['catalogue_only']} cf={summary['conditional_formatting_rules']} "
        f"validations={summary['input_validation_rules']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
