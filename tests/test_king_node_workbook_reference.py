from __future__ import annotations

import json
from pathlib import Path

from modules.king_node_contract import validate_reference
from scripts.export_king_node_workbook_reference import export_reference


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "MASTER_KING_NODE_RECORD_V5.xlsx"
CATALOGUE = ROOT / "MASTER_KING_NODE_RECORD_V5_CATALOGO_COMPLETO_DE_FORMULAS.md"


def test_static_reference_export_is_complete_hash_pinned_and_deterministic() -> None:
    exported = export_reference(WORKBOOK, CATALOGUE)
    checked_in = json.loads(
        (ROOT / "config" / "king_node_reference.json").read_text(encoding="utf-8")
    )
    assert exported == checked_in
    verified = validate_reference(exported)
    assert len(verified.matrix) == 78
    assert len(verified.iv_regime_map) == 54
    assert exported["ranges"]["matrix"]["range"] == "A1:S79"
    assert exported["ranges"]["iv_regime_map"]["range"] == "A1:K55"
    assert exported["integrity"]["duplicate_keys"] == []
    assert exported["integrity"]["iv_materialized_key_cache_mismatches"] == []
