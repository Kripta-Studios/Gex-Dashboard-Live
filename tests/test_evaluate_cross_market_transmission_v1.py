from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa import evaluate_cross_market_transmission_v1 as subject
from neural.jepa.build_cross_market_transmission_view_v1 import (
    CROSS_FEATURES,
    EARLY_CLOSE_DATES,
    PAIRWISE_E0_FEATURES,
)


def _metric(*, trades: int = 18, pf: float = 1.3, wr: float = 0.5, pnl: float = 1.0) -> dict[str, float | int]:
    return {
        "trades": trades,
        "profit_factor": pf,
        "win_rate": wr,
        "pnl": pnl,
        "minimum_hold": 30.0,
        "maximum_hold": 180.0,
        "max_drawdown": 0.0,
        "call_rate": 0.5,
        "put_rate": 0.5,
    }


def test_runner_protocol_freezes_model_scheduler_and_2026_boundary() -> None:
    protocol = subject.runner_protocol()
    assert protocol["arms"] == ["X0", "X1"]
    assert protocol["model_spec_sha256"] == "53940684518834bed0f45272151f030d740428516ce5c86443d92cf318245499"
    assert len(protocol["outer_months"]) == 24
    assert protocol["scheduler"]["SPY"]["max_trades_per_day"] == 1
    assert protocol["holdout_2026_opened"] is False
    assert protocol["june_2026_sealed"] is True


def test_gate_is_conjunctive_and_does_not_accept_near_miss() -> None:
    assert subject._gate_pass(_metric())
    for override in (
        {"trades": 17},
        {"profit_factor": 1.299},
        {"win_rate": 0.499},
        {"pnl": 0.0},
        {"minimum_hold": 29.0},
    ):
        candidate = _metric()
        candidate.update(override)
        assert not subject._gate_pass(candidate)


def test_inner_selection_requires_every_month(monkeypatch: pytest.MonkeyPatch) -> None:
    grid = [{"utility_percentile": 50, "margin_percentile": 0, "utility_threshold": 0.1, "side_margin": 0.0}]
    fake_trades = pd.DataFrame(
        {
            "month": ["202301", "202302", "202303"],
            "trade_date": ["20230103", "20230201", "20230301"],
            "minute": [630, 630, 630],
            "ticker": ["SPY"] * 3,
            "realized_return": [1.0, 1.0, -1.0],
            "exit_minutes": [30.0] * 3,
            "action": ["CALL"] * 3,
        }
    )
    monkeypatch.setattr(subject, "_schedule", lambda scores, config: (fake_trades, 3))
    values = iter([_metric(), _metric(), _metric(pf=1.0, pnl=-1.0), _metric(trades=3)])
    monkeypatch.setattr(subject, "economic_metrics", lambda trades: next(values))
    selected, rows = subject._select_inner(pd.DataFrame(), grid, ["202301", "202302", "202303"])
    assert selected is None
    assert rows[0]["passed"] is False


def test_view_verifier_requires_exact_30_plus_28_arms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    view = tmp_path / "view.parquet"
    view.write_bytes(b"frozen-test-view")
    x0 = list(PAIRWISE_E0_FEATURES)
    x1 = [*x0, *CROSS_FEATURES]
    expected_columns = list(
        dict.fromkeys([*subject.VIEW_KEY, *PAIRWISE_E0_FEATURES, *CROSS_FEATURES])
    )

    class FakeParquet:
        metadata = type("Metadata", (), {"num_rows": 96_553})()
        schema_arrow = type("Schema", (), {"names": expected_columns})()

    monkeypatch.setattr(subject.pq, "ParquetFile", lambda path: FakeParquet())
    payload = {
        "schema": "cross_market_transmission_view_v1r1",
        "experiment": "CROSS_MARKET_TRANSMISSION_V1R1",
        "status": "PASS_EXACT_CROSS_MARKET_VIEW",
        "outcomes_in_view": False,
        "new_data_source": False,
        "master_rows_preserved": 96_553,
        "master_physical_rows": 97_625,
        "master_sha256": subject.MASTER_SHA256,
        "source_sessions": 3_848,
        "excluded_early_close_rows": 1_072,
        "excluded_early_close_dates": list(EARLY_CLOSE_DATES),
        "live_parity": "BLOCKED_IMPLEMENTATION",
        "view_sha256": subject.sha256_file(view),
        "date_max": "20251231",
        "X0": {"features": x0, "feature_count": 30, "ordered_json_sha256": subject.EXPECTED_X0_SHA256},
        "X1": {"features": x1, "feature_count": 58, "ordered_json_sha256": subject.EXPECTED_X1_SHA256},
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    assert subject._verify_view(view, manifest)["X1"]["feature_count"] == 58
    payload["live_parity"] = "PASS"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(AssertionError, match="view contract"):
        subject._verify_view(view, manifest)


def test_view_verifier_rejects_self_certified_leaky_allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    view = tmp_path / "view.parquet"
    view.write_bytes(b"view")
    x0 = list(PAIRWISE_E0_FEATURES)
    x0[0] = "future_return"
    x1 = [*x0, *CROSS_FEATURES]
    expected_columns = list(
        dict.fromkeys([*subject.VIEW_KEY, *PAIRWISE_E0_FEATURES, *CROSS_FEATURES])
    )

    class FakeParquet:
        metadata = type("Metadata", (), {"num_rows": 96_553})()
        schema_arrow = type("Schema", (), {"names": expected_columns})()

    monkeypatch.setattr(subject.pq, "ParquetFile", lambda path: FakeParquet())
    payload = {
        "schema": "cross_market_transmission_view_v1r1",
        "experiment": "CROSS_MARKET_TRANSMISSION_V1R1",
        "status": "PASS_EXACT_CROSS_MARKET_VIEW",
        "outcomes_in_view": False,
        "new_data_source": False,
        "master_rows_preserved": 96_553,
        "master_physical_rows": 97_625,
        "master_sha256": subject.MASTER_SHA256,
        "source_sessions": 3_848,
        "excluded_early_close_rows": 1_072,
        "excluded_early_close_dates": list(EARLY_CLOSE_DATES),
        "live_parity": "BLOCKED_IMPLEMENTATION",
        "view_sha256": subject.sha256_file(view),
        "date_max": "20251231",
        "X0": {"features": x0, "feature_count": 30, "ordered_json_sha256": subject._canonical_sha(x0)},
        "X1": {"features": x1, "feature_count": 58, "ordered_json_sha256": subject._canonical_sha(x1)},
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(AssertionError, match="predeclared allowlist"):
        subject._verify_view(view, manifest)


def test_month_arithmetic_is_exact_across_year() -> None:
    assert subject.month_add("202401", -3) == "202310"
    assert subject.month_range("202311", "202402") == ["202311", "202312", "202401", "202402"]
    assert subject.development_outer_months("202304", "202312")[0] == "202304"
    with pytest.raises(AssertionError, match="frozen"):
        subject.development_outer_months("202312", "202312")


def test_frozen_manifest_rejects_empty_self_selected_code_closure(tmp_path: Path) -> None:
    view_manifest = {
        "view_sha256": "view-sha",
        "X0": {"features": list(PAIRWISE_E0_FEATURES)},
        "X1": {"features": [*PAIRWISE_E0_FEATURES, *CROSS_FEATURES]},
    }
    frozen = {
        "schema": "cross_market_transmission_v1r1_frozen_runner",
        "status": "PREEXECUTION_FROZEN",
        "runner_protocol_sha256": subject.runner_protocol_sha256(),
        "view_sha256": "view-sha",
        "feature_arms": {arm: view_manifest[arm] for arm in ("X0", "X1")},
        "code_hashes": {},
        "protocol_hashes": {},
        "holdout_2026_opened": False,
        "june_2026_sealed": True,
        "outer_output_dir": subject.FROZEN_OUTER_OUTPUT,
    }
    path = tmp_path / "frozen.json"
    path.write_text(json.dumps(frozen), encoding="utf-8")
    with pytest.raises(AssertionError, match="code closure"):
        subject._verify_frozen_manifest(path, view_manifest)
