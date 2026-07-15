from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from neural.jepa import evaluate_tpo_value_migration_v1 as subject
from neural.jepa.build_tpo_value_migration_view_v1 import (
    EARLY_CLOSE_DATES,
    PAIRWISE_E0_FEATURES,
    TPO_FEATURES,
)


def _metric(
    *,
    trades: int = 18,
    pf: float = 1.3,
    wr: float = 0.5,
    pnl: float = 1.0,
) -> dict[str, float | int]:
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


def _view_payload(view: Path) -> dict[str, object]:
    x0 = list(PAIRWISE_E0_FEATURES)
    x1 = [*x0, *TPO_FEATURES]
    return {
        "schema": "tpo_value_migration_view_v1",
        "experiment": subject.EXPERIMENT,
        "status": "PASS_EXACT_TPO_VALUE_VIEW",
        "outcomes_in_view": False,
        "new_data_source": False,
        "master_rows_preserved": subject.ELIGIBLE_ROWS_V1R1,
        "master_physical_rows": 97_625,
        "master_sha256": subject.MASTER_SHA256,
        "excluded_early_close_rows": 1_072,
        "excluded_early_close_dates": list(EARLY_CLOSE_DATES),
        "live_parity": "BLOCKED_IMPLEMENTATION",
        "view_sha256": subject.sha256_file(view),
        "date_max": "20251231",
        "X0": {
            "features": x0,
            "feature_count": 30,
            "ordered_json_sha256": subject.EXPECTED_X0_SHA256,
        },
        "X1": {
            "features": x1,
            "feature_count": 66,
            "ordered_json_sha256": subject.EXPECTED_X1_SHA256,
        },
    }


def test_protocol_freezes_quantile_scheduler_concentration_and_2026() -> None:
    protocol = subject.runner_protocol()
    assert protocol["experiment"] == "H_TPOVALUE1_EXECUTABLE_V1"
    assert protocol["arms"] == ["X0", "X1"]
    assert protocol["model_spec_sha256"] == "53940684518834bed0f45272151f030d740428516ce5c86443d92cf318245499"
    assert protocol["scheduler"]["SPY"]["max_trades_per_day"] == 1
    assert protocol["concentration_gates"] == {
        "pooled_and_each_ticker_top5_trade_gross_profit_share_max": 0.20,
        "pooled_and_each_ticker_top5_day_gross_profit_share_max": 0.30,
    }
    assert protocol["holdout_2026_opened"] is False
    assert protocol["june_2026_sealed"] is True


def test_development_range_is_exactly_april_through_december_2023() -> None:
    assert subject.development_outer_months("202304", "202312") == subject.month_range(
        "202304", "202312"
    )
    for first, last in (("202303", "202312"), ("202304", "202311"), ("202312", "202312")):
        with pytest.raises(AssertionError, match="frozen"):
            subject.development_outer_months(first, last)


def test_gate_is_conjunctive() -> None:
    assert subject._gate_pass(_metric())
    for changed in (
        {"trades": 17},
        {"profit_factor": 1.299},
        {"win_rate": 0.499},
        {"pnl": 0.0},
        {"minimum_hold": 29.0},
    ):
        metric = _metric()
        metric.update(changed)
        assert not subject._gate_pass(metric)


def test_inner_selection_requires_all_three_months(monkeypatch: pytest.MonkeyPatch) -> None:
    grid = [
        {
            "utility_percentile": 50,
            "margin_percentile": 0,
            "utility_threshold": 0.1,
            "side_margin": 0.0,
        }
    ]
    trades = pd.DataFrame(
        {
            "month": ["202301", "202302", "202303"],
            "trade_date": ["20230103", "20230201", "20230301"],
            "minute": [630] * 3,
            "ticker": ["SPY"] * 3,
            "realized_return": [1.0, 1.0, -1.0],
            "exit_minutes": [30.0] * 3,
            "action": ["CALL"] * 3,
        }
    )
    monkeypatch.setattr(subject, "_schedule", lambda scores, config: (trades, 3))
    values = iter([_metric(), _metric(), _metric(pf=1.0, pnl=-1.0), _metric(trades=3)])
    monkeypatch.setattr(subject, "economic_metrics", lambda frame: next(values))
    selected, rows = subject._select_inner(
        pd.DataFrame(), grid, ["202301", "202302", "202303"]
    )
    assert selected is None
    assert rows[0]["passed"] is False


def test_view_requires_exact_30_plus_36_allowlist_and_physical_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = tmp_path / "view.parquet"
    view.write_bytes(b"tpo-view")
    expected_columns = list(
        dict.fromkeys([*subject.VIEW_KEY, *PAIRWISE_E0_FEATURES, *TPO_FEATURES])
    )

    class FakeParquet:
        metadata = type("Metadata", (), {"num_rows": subject.ELIGIBLE_ROWS_V1R1})()
        schema_arrow = type("Schema", (), {"names": expected_columns})()

    monkeypatch.setattr(subject.pq, "ParquetFile", lambda path: FakeParquet())
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(_view_payload(view)), encoding="utf-8")
    checked = subject._verify_view(view, manifest)
    assert checked["X0"]["feature_count"] == 30
    assert checked["X1"]["feature_count"] == 66
    assert checked["X1"]["features"][30:] == list(TPO_FEATURES)


def test_view_rejects_self_certified_leaky_allowlist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = tmp_path / "view.parquet"
    view.write_bytes(b"tpo-view")
    expected_columns = list(
        dict.fromkeys([*subject.VIEW_KEY, *PAIRWISE_E0_FEATURES, *TPO_FEATURES])
    )

    class FakeParquet:
        metadata = type("Metadata", (), {"num_rows": subject.ELIGIBLE_ROWS_V1R1})()
        schema_arrow = type("Schema", (), {"names": expected_columns})()

    monkeypatch.setattr(subject.pq, "ParquetFile", lambda path: FakeParquet())
    payload = _view_payload(view)
    payload["X0"]["features"][0] = "future_return"  # type: ignore[index]
    payload["X0"]["ordered_json_sha256"] = subject._canonical_sha(  # type: ignore[index]
        payload["X0"]["features"]  # type: ignore[index]
    )
    payload["X1"]["features"] = [  # type: ignore[index]
        *payload["X0"]["features"],  # type: ignore[index]
        *TPO_FEATURES,
    ]
    payload["X1"]["ordered_json_sha256"] = subject._canonical_sha(  # type: ignore[index]
        payload["X1"]["features"]  # type: ignore[index]
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(AssertionError, match="predeclared allowlist"):
        subject._verify_view(view, manifest)


def _outcomes(keys: list[tuple[str, str, int]]) -> pd.DataFrame:
    frame = pd.DataFrame(keys, columns=subject.KEY)
    frame["option_price_mode"] = "executable_quote"
    for side in ("call", "put"):
        for bucket in (25, 35):
            frame[f"{side}_d{bucket:02d}_opt_exit_ret"] = 0.1
            frame[f"{side}_d{bucket:02d}_opt_exit_minutes"] = 30.0
    missing = frame["ticker"].eq("SPXW") & frame["trade_date"].eq("20220222")
    frame.loc[missing, "put_d25_opt_exit_ret"] = np.nan
    return frame


def test_loader_excludes_early_closes_and_requires_bidirectional_key_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    normal_keys = [
        ("QQQ", "20230103", 630),
        ("SPXW", "20220222", 630),
        ("SPXW", "20220222", 680),
    ]
    early_key = ("SPY", EARLY_CLOSE_DATES[0], 630)
    features = pd.DataFrame(normal_keys, columns=subject.KEY)
    features["timestamp"] = pd.to_datetime(
        features["trade_date"] + " 10:30", format="%Y%m%d %H:%M"
    )
    outcomes = _outcomes([*normal_keys, early_key])
    monkeypatch.setattr(subject, "_verify_view", lambda path, manifest: {"view_sha256": "x"})
    monkeypatch.setattr(subject, "verify_executable_build_summary", lambda path: {})
    monkeypatch.setattr(subject, "sha256_file", lambda path: subject.MASTER_SHA256)

    def fake_read(path: Path, **kwargs: object) -> pd.DataFrame:
        return features.copy() if path == Path("view") else outcomes.copy()

    monkeypatch.setattr(subject.pd, "read_parquet", fake_read)
    loaded, _ = subject.load_modeling_data(Path("view"), Path("manifest"), maximum_date="20231231")
    assert len(loaded) == 3
    assert not loaded["trade_date"].isin(EARLY_CLOSE_DATES).any()

    monkeypatch.setattr(subject.pd, "read_parquet", lambda path, **kwargs: features.iloc[:2].copy() if path == Path("view") else outcomes.copy())
    with pytest.raises(AssertionError, match="bidirectional key parity"):
        subject.load_modeling_data(Path("view"), Path("manifest"), maximum_date="20231231")


def test_frozen_manifest_rejects_empty_code_closure(tmp_path: Path) -> None:
    view_manifest = {
        "view_sha256": "view-sha",
        "X0": {"features": list(PAIRWISE_E0_FEATURES)},
        "X1": {"features": [*PAIRWISE_E0_FEATURES, *TPO_FEATURES]},
    }
    frozen = {
        "schema": "h_tpovalue1_executable_v1_frozen_runner",
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


def test_concentration_gates_apply_pooled_and_each_ticker() -> None:
    rows: list[dict[str, object]] = []
    for ticker in ("SPXW", "QQQ", "SPY"):
        for day in range(30):
            rows.append(
                {
                    "ticker": ticker,
                    "trade_date": f"202301{day + 1:02d}",
                    "realized_return": 1.0,
                }
            )
    passing = subject._concentration_audit(pd.DataFrame(rows), "X1")
    assert len(passing) == 4
    assert all(row["concentration_pass"] for row in passing)

    concentrated = pd.DataFrame(rows)
    concentrated.loc[concentrated["ticker"].eq("SPY"), "realized_return"] = 0.01
    spy_first = concentrated.index[concentrated["ticker"].eq("SPY")][:5]
    concentrated.loc[spy_first, "realized_return"] = 10.0
    audited = subject._concentration_audit(concentrated, "X1")
    assert not next(row for row in audited if row["scope"] == "SPY")["concentration_pass"]


def test_base_pass_is_never_reported_as_final_candidate() -> None:
    source = Path(subject.__file__).read_text(encoding="utf-8")
    assert '"candidate_found": False' in source
    assert "BASE_ECONOMIC_PASS_PENDING_LIVE_PARITY_STRESS" in source
    assert subject.FROZEN_OUTER_OUTPUT.endswith("h_tpovalue1_executable_v1_202401_202512")


def test_economic_runner_resumes_completed_outer_ticker_arm_folds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, str]] = []

    def fake_compute(
        data: pd.DataFrame,
        view_manifest: dict[str, object],
        *,
        outer_month: str,
        ticker: str,
        arm: str,
        mode: str,
    ) -> dict[str, pd.DataFrame]:
        del data, view_manifest
        calls.append((outer_month, ticker, arm))
        common = {
            "mode": mode,
            "outer_month": outer_month,
            "ticker": ticker,
            "arm": arm,
            "model_family": subject.MODEL_FAMILY,
            "train_date_min": "20220103",
            "train_date_max": "20221230",
            "inner_months": "202301,202302,202303",
            "outer_rows": 10,
        }
        return {
            "selection.csv": pd.DataFrame(
                [{**common, "status": "ABSTAIN_OUTER", "passing_grid_count": 0}]
            ),
            "inner_grid.csv": pd.DataFrame(
                [
                    {
                        **common,
                        "utility_percentile": 50,
                        "margin_percentile": 0,
                        "passed": False,
                    }
                ]
            ),
            "monthly.csv": pd.DataFrame(
                [
                    {
                        **common,
                        "status": "ABSTAIN_OUTER",
                        **subject.economic_metrics(subject._empty_fold_trades()),
                        "policy_candidates": 0,
                        "scheduler_rejections": 0,
                        "abstention_rate": 1.0,
                        "positive_month": False,
                        "gate_pass": False,
                    }
                ]
            ),
            "trades.csv": subject._empty_fold_trades(),
        }

    monkeypatch.setattr(subject, "_compute_fold", fake_compute)
    view_manifest = {
        "view_sha256": "f" * 64,
        "X0": {"ordered_json_sha256": subject.EXPECTED_X0_SHA256},
        "X1": {"ordered_json_sha256": subject.EXPECTED_X1_SHA256},
    }
    output = tmp_path / "economic"
    first = subject.evaluate(
        pd.DataFrame(),
        view_manifest,
        outer_months=["202304"],
        output_dir=output,
        mode="development",
    )
    assert len(calls) == 6
    assert first["checkpoint_contract"]["folds_built_this_run"] == 6
    assert first["checkpoint_contract"]["folds_reused_this_run"] == 0

    second = subject.evaluate(
        pd.DataFrame(),
        view_manifest,
        outer_months=["202304"],
        output_dir=output,
        mode="development",
    )
    assert len(calls) == 6
    assert second["checkpoint_contract"]["folds_built_this_run"] == 0
    assert second["checkpoint_contract"]["folds_reused_this_run"] == 6
    assert len(list((output / "fold_checkpoints").glob("*/*/*/manifest.json"))) == 6
