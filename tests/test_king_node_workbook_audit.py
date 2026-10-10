from __future__ import annotations

from pathlib import Path

from scripts.audit_king_node_workbook import audit_workbook


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "MASTER_KING_NODE_RECORD_V5.xlsx"
CATALOGUE = ROOT / "MASTER_KING_NODE_RECORD_V5_CATALOGO_COMPLETO_DE_FORMULAS.md"


def test_audit_reconciles_every_formula_and_non_cell_rule_deterministically() -> None:
    first = audit_workbook(WORKBOOK, CATALOGUE)
    second = audit_workbook(WORKBOOK, CATALOGUE)
    assert first["canonical_checksum"] == second["canonical_checksum"]
    summary = first["summary"]
    assert summary == {
        **summary,
        "current_formula_cells": 18302,
        "catalogue_formula_cells": 7382,
        "union_formula_cells": 18531,
        "overlapping_formula_cells": 7153,
        "formula_text_exact": 5429,
        "formula_text_changed": 1724,
        "xlsx_only": 11149,
        "catalogue_only": 229,
        "type_changed": 148,
        "current_family_count": 1898,
        "catalogue_family_count": 683,
        "conditional_formatting_rules": 352,
        "input_validation_rules": 9,
        "input_validation_slots": 17,
        "unmapped_formula_entries": 0,
        "unclassified_formula_entries": 0,
    }
    catalogue_only = [
        item for item in first["formula_entries"] if item["comparison"] == "catalogue_only"
    ]
    assert len(catalogue_only) == 229
    assert all(item["classification"] == "not_runtime_applicable" for item in catalogue_only)
    assert all(item["not_runtime_reason"].startswith("catalogue_formula_absent_from_current_xlsx_at_") for item in catalogue_only)
    assert len(first["non_cell_rules"]["conditional_formatting"]) == 352
    assert len(first["non_cell_rules"]["input_validation"]) == 9
