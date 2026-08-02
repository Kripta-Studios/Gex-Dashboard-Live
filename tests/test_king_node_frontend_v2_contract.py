from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KING_NODE_JS = ROOT / "web" / "templates" / "js" / "king_node.js"


def _source() -> str:
    return KING_NODE_JS.read_text(encoding="utf-8")


def test_frontend_declares_v2_contract() -> None:
    source = _source()

    assert 'const SCHEMA_VERSION = "king-node.v2";' in source
    assert 'new Set(["live", "last_completed_session"])' in source
    assert "data.quality?.valid !== true" in source


def test_frontend_uses_nested_v2_inputs_and_provenance() -> None:
    source = _source()

    required = (
        "model.inputs?.underlying",
        "model.inputs?.expiration",
        "model.inputs?.indices",
        "model.provenance?.indices",
        "model.freshness?.oldest_age_seconds",
        "model.monitor?.skew",
        "regime.dealers_action",
        "regime.action",
        "regime.tilt",
    )

    for expression in required:
        assert expression in source


def test_frontend_contains_no_v1_renderer_paths() -> None:
    source = _source()

    forbidden = (
        'const SCHEMA_VERSION = "king-node.v1";',
        "model.delivery",
        "model.source?.indices",
        "model.source?.tastytrade",
        "model.inputs?.spot_change_pct",
        "model.inputs?.dte_hours",
        "model.inputs?.atm_iv",
        "regime.dealer_action",
        "regime.tactical",
    )

    for expression in forbidden:
        assert expression not in source


def test_frontend_preserves_structured_api_errors() -> None:
    source = _source()

    assert "const apiError = data?.error;" in source
    assert "error.retryable =" in source
    assert "wrapper.innerHTML = renderError(error);" in source
