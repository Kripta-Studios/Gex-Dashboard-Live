"""Export formulas and explicit settings, excluding saved market/state values."""

from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZipFile

from scripts.audit_king_node_workbook import _read_xlsx_formulas, _workbook_sheets

LE_SETTINGS = frozenset(
    [
        "FT2",
        "GG2",
        "GL2",
        "GG3",
        "GL3",
        "Q4",
        "GG4",
        "GL4",
        "F5",
        "H5",
        "GG5",
        "B6",
        "E6",
        "F6",
        "I6",
        "FA6",
        "FO6",
        "HC6",
        "HK6",
        "FA7",
        "HC7",
        "CT12",
        "BF123",
        "KG9",
        "KG55",
    ]
)
LE_DYNAMIC_BG = frozenset({53, 76, 78, 79, 80, 123, 124, 125, 126})
STATIC_SHEETS = frozenset({"Matrix", "IV Regime Map"})


def runtime_cells(workbook_path: Path):
    from scripts.export_king_node_workbook_reference import _sheet_cells

    formulas, _, _ = _read_xlsx_formulas(workbook_path)
    result = {}
    with ZipFile(workbook_path) as archive:
        for sheet, _ in _workbook_sheets(archive):
            if sheet in {"How To Use", "Sheet1", "Rule Log", "Level Test Log"}:
                continue
            cells = _sheet_cells(archive, sheet)
            output = result[sheet] = {}
            for cell, (value, _, formula) in cells.items():
                if formula is not None:
                    output[cell] = {"formula": formulas[f"{sheet}!{cell}"].formula}
                    continue
                column, row = re.fullmatch(r"([A-Z]+)(\d+)", cell).groups()
                row = int(row)
                is_setting = (
                    sheet in STATIC_SHEETS
                    or (sheet == "King Node Model" and cell in {"H5", "L25", "L27"})
                    or (sheet == "GEX Depth" and cell in {"Q2", "Q3", "Q4", "Q5", "Q6"})
                    or (
                        sheet == "Level Engine"
                        and (
                            cell in LE_SETTINGS
                            or (column == "BG" and row not in LE_DYNAMIC_BG)
                            or (row == 8 and isinstance(value, str))
                        )
                    )
                )
                # All other literals are inputs, script-written latches, display
                # history or annotations. Do not propagate saved market snapshots.
                if is_setting and value is not None:
                    output[cell] = {"value": value}
    return result
