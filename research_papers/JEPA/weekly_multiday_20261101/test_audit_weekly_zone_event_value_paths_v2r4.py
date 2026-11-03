"""Focused R4 JSONL regression; real reads restricted to two pinned metadata files."""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pytest

import audit_weekly_zone_event_value_paths_v2r4 as audit


HERE = Path(__file__).resolve().parent
PRIOR = HERE / "audit_weekly_zone_event_value_paths_v2r3.py"
PRIOR_SHA = "effc36ce5cc496698f9aca1ea496046c89ca0d8e0deabe3f354dd892a94a5643"
CACHE_KEYS = tuple("authority binding_source_metadata_sha256 binding_source_sha256 cache_metadata_bytes cache_metadata_path cache_metadata_sha256 cache_status cache_version close_i date feature_metadata_bytes feature_metadata_path feature_metadata_sha256 missing_reason npz_bytes npz_path npz_sha256 session_kind stats ticker ticker_ordinal".split())
SPOT_KEYS = tuple("cache_status date expected_count first_valid_i invalid_count invalid_ranges last_valid_i metadata_path metadata_sha256 missing_reason npz_path npz_sha256 session_kind ticker ticker_ordinal valid_count".split())
METADATA = (
    ("cache_admission", 5104757, "e0b4512791adbe70642d8ca83391dd4f0379037aae02f2af4888242bab3b0e14", CACHE_KEYS),
    ("spot_coverage", 1675844, "2ed4a4b63a2f49f7bb6c1737fb6ae7ab4f5225f7c767185889f7fb591c78b972", SPOT_KEYS),
)


def canonical(rows):
    return [json.loads(json.dumps(row, sort_keys=True, allow_nan=False)) for row in rows]


def invoke_actual_jsonl_call(label, actual, expected):
    """Execute the exact production call statement, without upstream IO or a run."""
    tree = ast.parse(Path(audit.__file__).read_bytes())
    matches = [node for node in ast.walk(tree) if isinstance(node, ast.Expr)
               and isinstance(node.value, ast.Call)
               and isinstance(node.value.func, ast.Name)
               and node.value.func.id == "compare_jsonl_rows"
               and isinstance(node.value.args[-1], ast.Constant)
               and node.value.args[-1].value == label]
    assert len(matches) == 1
    names = [argument.id for argument in matches[0].value.args[:2]]
    scope = {"compare_jsonl_rows": audit.compare_jsonl_rows,
             names[0]: actual, names[1]: expected}
    exec(compile(ast.Module(body=matches, type_ignores=[]), "<production-jsonl-call>", "exec"), scope)


@pytest.mark.parametrize("label", ["cache_admission", "spot_coverage"])
def test_original_failure_and_both_corrected_calls(label):
    expected = [{"ticker": "SPY", "date": "20260105", "amount": 1.25},
                {"ticker": "QQQ", "date": "20260105", "amount": -0.0}]
    actual = canonical(expected)
    before = deepcopy(expected)
    with pytest.raises(audit.AuditError, match="schema/order row 0"):
        audit.compare_rows(actual, expected, label)
    invoke_actual_jsonl_call(label, actual, expected)
    assert expected == before
    assert [list(row) for row in expected] == [list(row) for row in before]


@pytest.mark.parametrize("label", ["cache_admission", "spot_coverage"])
@pytest.mark.parametrize("mutation", ["value", "float_bits", "missing", "extra", "rows", "keys", "count"])
def test_jsonl_rejects_changes(label, mutation):
    expected = [{"ticker": "SPY", "amount": 0.0}, {"ticker": "QQQ", "amount": 2.0}]
    actual = canonical(expected)
    if mutation == "value":
        actual[0]["ticker"] = "SPXW"
    elif mutation == "float_bits":
        actual[0]["amount"] = -0.0
    elif mutation == "missing":
        del actual[0]["amount"]
    elif mutation == "extra":
        actual[0]["unapproved"] = None
        actual = canonical(actual)
    elif mutation == "rows":
        actual.reverse()
    elif mutation == "keys":
        actual[0] = dict(reversed(list(actual[0].items())))
    elif mutation == "count":
        actual.pop()
    with pytest.raises(audit.AuditError):
        invoke_actual_jsonl_call(label, actual, expected)


def test_parquet_field_order_still_strict():
    schema = audit.spot_schema()
    reversed_schema = pa.schema(list(reversed(list(schema))))
    with pytest.raises(audit.AuditError):
        audit.require_schema(reversed_schema, schema, "spot_paths")
    expected = [{"ticker": "SPY", "date": "20260105"}]
    with pytest.raises(audit.AuditError, match="schema/order"):
        audit.compare_rows(canonical(expected), expected, "spot_paths")


def test_only_declared_ast_changes_and_new_identities():
    prior_bytes = PRIOR.read_bytes()
    assert len(prior_bytes) == 120016
    assert hashlib.sha256(prior_bytes).hexdigest() == PRIOR_SHA
    old, new = ast.parse(prior_bytes), ast.parse(Path(audit.__file__).read_bytes())
    identities = {"OUTPUT", "OBSERVER", "TESTS"}
    old_assign = {node.targets[0].id: node for node in old.body
                  if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    helpers = [node for node in new.body if isinstance(node, ast.FunctionDef)
               and node.name == "compare_jsonl_rows"]
    assert len(helpers) == 1
    new.body.remove(helpers[0])
    changed_calls = []
    changed_identities = []
    for node in new.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in identities:
            name = node.targets[0].id
            assert ast.dump(node.value) != ast.dump(old_assign[name].value)
            node.value = deepcopy(old_assign[name].value)
            changed_identities.append(name)
        if isinstance(node, ast.FunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "compare_jsonl_rows":
                    changed_calls.append((node.name, child.args[-1].value))
                    child.func.id = "compare_rows"
    assert set(changed_identities) == identities
    assert sorted(changed_calls) == [("compare_spot", "spot_coverage"), ("run", "cache_admission")]
    assert ast.dump(new, include_attributes=False) == ast.dump(old, include_attributes=False)
    assert audit.OUTPUT == audit.BASE / "weekly_zone_event_value_paths_audit_07"
    assert audit.OBSERVER == audit.BASE / "weekly_zone_event_value_paths_audit_observer_07"
    assert audit.TESTS == HERE / "test_audit_weekly_zone_event_value_paths_v2r4.py"


@pytest.mark.parametrize("label,size,digest,keys", METADATA)
def test_pinned_real_metadata_serialization_only(label, size, digest, keys):
    """Metadata/schema integration only; does not reconstruct or admit actual values."""
    path = audit.PRODUCER / f"{label}.jsonl"
    raw = path.read_bytes()
    assert len(raw) == size
    assert hashlib.sha256(raw).hexdigest() == digest
    assert raw.endswith(b"\n")
    rows = [json.loads(line) for line in raw.splitlines()]
    assert len(rows) == 2790
    assert len(keys) == (21 if label == "cache_admission" else 16)
    assert all(tuple(row) == keys for row in rows)
    # Reverse keys only to exercise reconstruction order against actual serialized keys.
    expected = [dict(reversed(list(row.items()))) for row in rows]
    with pytest.raises(audit.AuditError, match="schema/order row 0"):
        audit.compare_rows(rows, expected, label)
    invoke_actual_jsonl_call(label, rows, expected)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
