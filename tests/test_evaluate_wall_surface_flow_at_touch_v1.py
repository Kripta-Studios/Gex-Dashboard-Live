from __future__ import annotations

import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neural.jepa.evaluate_wall_surface_flow_at_touch_v1 import (  # noqa: E402
    CODE_CLOSURE,
    HORIZONS,
    PROTOCOL_CLOSURE,
    assert_conditional_repair_status,
    assert_data_builder_link,
    assert_evaluation_metadata_committed,
    assert_exact_greek_repair_provenance,
    assert_frozen_hash_closure,
    assert_strict_pass_data_gate,
    hash_inventory,
    label_candidate_session,
    paired_day_bootstrap,
    sha256_file,
    summarize_gate,
)
from neural.jepa import evaluate_wall_surface_flow_at_touch_v1 as evaluator  # noqa: E402


def _candidate(
    *,
    role: str = "support",
    spot: float = 101.0,
    ticker: str = "SPY",
    trade_date: str = "20240102",
    decision: str = "2024-01-02 10:00:00",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": [ticker],
            "trade_date": [trade_date],
            "minute": [pd.Timestamp(decision).hour * 60 + pd.Timestamp(decision).minute],
            "decision_dt": [pd.Timestamp(decision)],
            "wall_identity": ["put_gamma" if role == "support" else "call_gamma"],
            "wall_role": [role],
            "candidate_wall_strike": [100.0],
            "spot": [spot],
        }
    )


def _underlying() -> pd.DataFrame:
    times = pd.date_range("2024-01-02 10:00:00", "2024-01-02 13:00:00", freq="1min")
    frame = pd.DataFrame(
        {
            "bar_start": times,
            "open": 101.0,
            "high": 101.5,
            "low": 100.5,
            "close": 101.0,
        }
    )
    return frame


def test_label_includes_bar_t_excludes_bar_t_plus_h_and_requires_pierce() -> None:
    underlying = _underlying()
    underlying.loc[underlying["bar_start"].eq(pd.Timestamp("2024-01-02 10:00:00")), "low"] = 99.0
    # This extreme belongs to [t+h,t+h+1) and must not enter the 30m label.
    underlying.loc[underlying["bar_start"].eq(pd.Timestamp("2024-01-02 10:30:00")), ["open", "high", "low", "close"]] = [50.0, 50.0, 50.0, 50.0]
    labeled = label_candidate_session(_candidate(), underlying)
    assert labeled["path_complete_30m"].iloc[0] == 1
    assert labeled["pierced_30m"].iloc[0] == 1.0
    assert labeled["true_rejection_30m"].iloc[0] == 1.0
    assert labeled["accepted_break_30m"].iloc[0] == 0.0
    assert labeled["resolved_rejection_30m"].iloc[0] == 1.0


def test_defended_terminal_without_actual_pierce_is_unresolved() -> None:
    labeled = label_candidate_session(_candidate(), _underlying())
    assert labeled["pierced_30m"].iloc[0] == 0.0
    assert labeled["true_rejection_30m"].iloc[0] == 0.0
    assert labeled["accepted_break_30m"].iloc[0] == 0.0
    assert np.isnan(labeled["resolved_rejection_30m"].iloc[0])


def test_candidate_already_beyond_wall_counts_as_pierced() -> None:
    underlying = _underlying()
    labeled = label_candidate_session(_candidate(role="resistance", spot=100.1), underlying)
    assert labeled["pierced_30m"].iloc[0] == 1.0
    assert labeled["accepted_break_30m"].iloc[0] == 1.0
    assert labeled["resolved_rejection_30m"].iloc[0] == 0.0


def test_missing_minute_invalidates_complete_horizon() -> None:
    underlying = _underlying()
    underlying = underlying[underlying["bar_start"].ne(pd.Timestamp("2024-01-02 10:12:00"))]
    labeled = label_candidate_session(_candidate(), underlying)
    assert labeled["path_complete_30m"].iloc[0] == 0
    assert np.isnan(labeled["resolved_rejection_30m"].iloc[0])


def test_half_day_and_regular_day_labels_cannot_cross_underlying_close() -> None:
    half_times = pd.date_range("2024-07-03 12:55:00", "2024-07-03 15:55:00", freq="1min")
    half = pd.DataFrame(
        {"bar_start": half_times, "open": 101.0, "high": 101.5, "low": 99.0, "close": 101.0}
    )
    half_labeled = label_candidate_session(
        _candidate(trade_date="20240703", decision="2024-07-03 12:55:00"),
        half,
    )
    assert half_labeled["path_complete_30m"].iloc[0] == 0
    regular_times = pd.date_range("2024-01-02 14:30:00", "2024-01-02 17:30:00", freq="1min")
    regular = pd.DataFrame(
        {"bar_start": regular_times, "open": 101.0, "high": 101.5, "low": 99.0, "close": 101.0}
    )
    regular_labeled = label_candidate_session(
        _candidate(decision="2024-01-02 14:30:00"),
        regular,
    )
    assert regular_labeled["path_complete_30m"].iloc[0] == 1
    assert regular_labeled["path_complete_60m"].iloc[0] == 1
    assert regular_labeled["path_complete_120m"].iloc[0] == 0
    assert regular_labeled["path_complete_180m"].iloc[0] == 0


def test_candidate_decision_calendar_date_mismatch_fails_closed() -> None:
    candidate = _candidate()
    candidate["trade_date"] = "20240103"
    with pytest.raises(AssertionError, match="timestamp/date mismatch"):
        label_candidate_session(candidate, _underlying())


def test_ticker_day_bootstrap_is_deterministic() -> None:
    test = pd.DataFrame({"trade_date": ["20240102"] * 3 + ["20240103"] * 3})
    y = np.array([0, 1, 0, 1, 0, 1])
    f0 = np.array([0.8, 0.2, 0.7, 0.2, 0.8, 0.3])
    f1 = np.array([0.2, 0.8, 0.3, 0.8, 0.2, 0.7])
    left = paired_day_bootstrap(test, y, f0, f1, seed=17, replicates=100)
    right = paired_day_bootstrap(test, y, f0, f1, seed=17, replicates=100)
    assert left == right
    assert left["bootstrap_valid"] > 0
    assert left["bootstrap_favorable_share"] > 0.5


def _gate_frames(joint_losses: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cell_rows = []
    paired_rows = []
    monthly_rows = []
    index = 0
    for fold in ("2024", "2025"):
        for ticker in ("SPXW", "QQQ", "SPY"):
            for horizon in HORIZONS:
                cell_id = f"{fold}_{ticker}_{horizon}m"
                for arm, auc in (("F0", 0.56), ("F1", 0.58)):
                    cell_rows.append({"cell_id": cell_id, "fold": fold, "ticker": ticker, "horizon": horizon, "arm": arm, "roc_auc": auc})
                loses_both = index < joint_losses
                paired_rows.append(
                    {
                        "cell_id": cell_id,
                        "fold": fold,
                        "ticker": ticker,
                        "horizon": horizon,
                        "valid_pair": True,
                        "auc_delta": 0.02,
                        "average_precision_delta": -0.01 if loses_both else 0.01,
                        "log_loss_delta": 0.01 if loses_both else -0.01,
                    }
                )
                if horizon in (30, 60):
                    for month in range(1, 13):
                        monthly_rows.append(
                            {
                                "fold": fold,
                                "ticker": ticker,
                                "horizon": horizon,
                                "month": f"{fold}{month:02d}",
                                "resolved_episodes": 18,
                                "both_classes": True,
                            }
                        )
                index += 1
    return pd.DataFrame(cell_rows), pd.DataFrame(paired_rows), pd.DataFrame(monthly_rows)


def test_joint_ap_logloss_gate_allows_twelve_not_thirteen_losses() -> None:
    cells, paired, monthly = _gate_frames(12)
    passed = summarize_gate(cells, paired, monthly, provenance_status="PASS", live_parity_status="PASS")
    assert passed["calibration_pass"] is True
    assert passed["physical_mechanism_pass"] is True
    cells, paired, monthly = _gate_frames(13)
    failed = summarize_gate(cells, paired, monthly, provenance_status="PASS", live_parity_status="PASS")
    assert failed["calibration_pass"] is False
    assert failed["physical_mechanism_pass"] is False


def _passing_data_gate() -> dict[str, object]:
    return {
        "status": "PASS_DATA_GATE",
        "data_gate": {
            "authoritative_inputs": True,
            "authoritative_code": True,
            "coverage_pass": True,
            "distinctness_pass": True,
            "control_coverage_pass": True,
            "passed": True,
        },
    }


def test_pass_data_gate_booleans_are_strict_not_truthy_strings() -> None:
    manifest = _passing_data_gate()
    assert_strict_pass_data_gate(manifest)
    manifest["data_gate"]["passed"] = "false"  # type: ignore[index]
    with pytest.raises(AssertionError, match="non-true data-gate fields"):
        assert_strict_pass_data_gate(manifest)
    manifest = _passing_data_gate()
    manifest["data_gate"]["authoritative_code"] = 1  # type: ignore[index]
    with pytest.raises(AssertionError, match="authoritative_code"):
        assert_strict_pass_data_gate(manifest)


def test_source_hash_inventory_is_required_to_be_committed(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[tuple[Path, str]] = []

    def record(path: Path, label: str) -> str:
        observed.append((path, label))
        return str(path)

    monkeypatch.setattr(evaluator, "assert_tracked_clean", record)
    assert_evaluation_metadata_committed(Path("freeze.json"), Path("source.csv"), Path("data.json"))
    assert [label for _, label in observed] == ["frozen manifest", "source hash inventory", "data manifest"]


def test_frozen_hash_closure_rejects_any_code_or_protocol_change() -> None:
    freeze = {
        "code_hashes": hash_inventory(CODE_CLOSURE),
        "protocol_hashes": hash_inventory(PROTOCOL_CLOSURE),
    }
    assert_frozen_hash_closure(freeze)
    freeze["code_hashes"] = dict(freeze["code_hashes"])
    freeze["code_hashes"][CODE_CLOSURE[0]] = "0" * 64
    with pytest.raises(AssertionError, match="code hash closure"):
        assert_frozen_hash_closure(freeze)


def _exact_repair_provenance() -> dict[str, object]:
    root = ROOT / "research_papers/JEPA/results/_diagnostics/wall_exact_greek_repair_artifacts_20221230_v1r2"
    built = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    return {
        "schema": built["schema"],
        "status": built["status"],
        "manifest_path": (root / "manifest.json").relative_to(ROOT).as_posix(),
        "manifest_sha256": sha256_file(root / "manifest.json"),
        "wall_repair_path": (root / "wall_repair.parquet").relative_to(ROOT).as_posix(),
        "wall_repair_sha256": sha256_file(root / "wall_repair.parquet"),
        "event_control_repair_path": (root / "event_control_repair.parquet").relative_to(ROOT).as_posix(),
        "event_control_repair_sha256": sha256_file(root / "event_control_repair.parquet"),
        "frozen_hashes_match": True,
        "target_sessions": built["target_sessions"],
        "wall_target_rows": built["wall_target_rows"],
        "full_control_grid_rows": built["full_control_grid_rows"],
        "event_target_rows": built["event_target_rows"],
        "event_target_rows_by_ticker": built["event_target_rows_by_ticker"],
        "event_target_key_sha256": built["event_target_key_sha256"],
        "historical_provenance": built["historical_provenance"],
        "builder_sha256": built["builder_sha256"],
        "sidecar_builder_sha256": built["sidecar_builder_sha256"],
        "wall_feature_module_sha256": built["wall_feature_module_sha256"],
        "predeclaration_sha256": built["predeclaration_sha256"],
        "runtime_lock_sha256": built["runtime_lock_sha256"],
    }


def test_exact_repair_is_bound_to_artifacts_code_and_conditional_status() -> None:
    code_hashes = hash_inventory(CODE_CLOSURE)
    protocol_hashes = hash_inventory(PROTOCOL_CLOSURE)
    exact = _exact_repair_provenance()
    assert_exact_greek_repair_provenance(exact, code_hashes=code_hashes, protocol_hashes=protocol_hashes)
    with pytest.raises(AssertionError, match="cannot support authoritative"):
        assert_conditional_repair_status(exact, {"historical_timestamp_provenance_status": "PASS"})
    changed = dict(exact)
    changed["event_target_rows"] = 48
    with pytest.raises(AssertionError, match="provenance mismatch"):
        assert_exact_greek_repair_provenance(changed, code_hashes=code_hashes, protocol_hashes=protocol_hashes)


def test_data_manifest_builder_must_equal_frozen_builder_code() -> None:
    code_hashes = hash_inventory(CODE_CLOSURE)
    expected = code_hashes["neural/jepa/build_wall_surface_flow_dataset.py"]
    assert_data_builder_link({"builder_sha256": expected}, code_hashes)
    with pytest.raises(AssertionError, match="builder hash"):
        assert_data_builder_link({"builder_sha256": "0" * 64}, code_hashes)
