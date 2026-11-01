from __future__ import annotations

import math

import pytest

import audit_weekly_h2_ev_v2_independent as audit
import evaluate_weekly_h2_ev_v2 as evaluator
from test_evaluate_weekly_h2_ev_v2 import sha, synthetic_rows, write_dataset


def test_transform_reconstructs_imputation_indicator_and_scaling() -> None:
    values = [float(index) for index in range(len(audit.FEATURES))]
    values[13] = None
    transform = {
        "feature_order": list(audit.FEATURES),
        "missing_indicator_source_indices": [13],
        "missing_indicator_order": ["implied_vol__missing"],
        "medians": [10.0] * len(audit.FEATURES),
        "scaler_mean": [1.0] * (len(audit.FEATURES) + 1),
        "scaler_scale": [2.0] * (len(audit.FEATURES) + 1),
    }
    result = audit.transform_one(values, transform)
    assert result[13] == pytest.approx(4.5)
    assert result[-1] == pytest.approx(0.0)


def test_probability_reconstruction_handles_multiclass_and_binary() -> None:
    multiclass = {
        "classes_present": [0, 2, 4],
        "classes_full": list(range(5)),
        "coefficient": [[0.0], [0.0], [0.0]],
        "intercept": [0.0, 0.0, 0.0],
    }
    assert audit.probabilities([3.0], multiclass) == pytest.approx(
        [1 / 3, 0, 1 / 3, 0, 1 / 3]
    )
    binary = {
        "classes_present": [1, 3],
        "classes_full": list(range(5)),
        "coefficient": [[2.0]],
        "intercept": [0.0],
    }
    result = audit.probabilities([1.0], binary)
    expected = 1 / (1 + math.exp(-2))
    assert result == pytest.approx([0, 1 - expected, 0, expected, 0])


def test_candidate_lower_bound_and_observed_equations() -> None:
    common = {
        "candidate_id": "SPY:20230103:20230110:CALL",
        "ticker": "SPY",
        "entry_date": "20230103",
        "exit_date": "20230105",
        "expiration": "20230110",
        "right": "CALL",
        "entry_ask": 1.0,
        "entry_debit_base": 102.30,
        "entry_debit_adverse": 103.30,
    }
    missing = {
        **common,
        "status": "MISSING_EXIT_QUOTE",
        "scenario": 1,
        "exit_bid": None,
        "payoff_is_lower_bound": True,
        "net_base": -103.60,
        "net_adverse": -104.60,
    }
    audit.validate_candidate_economics(missing)
    observed = {
        **common,
        "status": "OBSERVED_EXIT",
        "scenario": 4,
        "exit_bid": 1.5,
        "payoff_is_lower_bound": False,
        "net_base": 45.40,
        "net_adverse": 43.40,
    }
    audit.validate_candidate_economics(observed)


def test_replay_exits_before_reentry_and_reconciles_cash() -> None:
    def row(entry: str, exit_day: str, expiration: str) -> dict:
        return {
            "candidate_id": f"SPY:{entry}:{expiration}:CALL",
            "ticker": "SPY",
            "entry_date": entry,
            "exit_date": exit_day,
            "expiration": expiration,
            "right": "CALL",
            "status": "OBSERVED_EXIT",
            "entry_ask": 1.0,
            "exit_bid": 1.2,
            "entry_debit_base": 102.30,
            "entry_debit_adverse": 103.30,
            "net_base": 15.40,
            "net_adverse": 13.40,
            "_split": "TRAIN",
            "_ev_base": 1.0,
            "_ev_adverse": 1.0,
        }

    rows = [
        row("20230103", "20230105", "20230110"),
        row("20230105", "20230109", "20230112"),
    ]
    dates = ("20230103", "20230104", "20230105", "20230106", "20230109")
    coverage = {
        "rows": [
            {
                "ticker": ticker,
                "entry_date": day,
                "status": "CANDIDATES_BUILT"
                if ticker == "SPY" and day in {"20230103", "20230105"}
                else "NO_SERIES",
                "reason": None
                if ticker == "SPY" and day in {"20230103", "20230105"}
                else "NO_SERIES",
            }
            for day in dates
            for ticker in audit.TICKERS
        ]
    }
    ledger = audit.replay(rows, coverage, "ALWAYS_CALL_H2", "TRAIN", "base")
    same_day = [
        row["event"]
        for row in ledger
        if row["date"] == "20230105" and row["ticker"] == "SPY"
    ]
    assert same_day == ["EXIT", "ENTRY"]
    exits = [row for row in ledger if row["event"] == "EXIT"]
    assert exits[-1]["cash"] == pytest.approx(100_000 + 2 * 15.40)
    assert audit.metrics(ledger)["trades"] == 2


def test_full_independent_audit_of_synthetic_v2_package(tmp_path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    paths = write_dataset(dataset, synthetic_rows())
    evaluation = tmp_path / "evaluation"
    evaluator.run(*paths, sha(paths[2]), evaluation)
    output = tmp_path / "independent_audit"
    result = audit.run(
        dataset,
        evaluation,
        sha(paths[2]),
        sha(evaluation / "manifest.json"),
        output,
    )
    assert result["status"] == "PASS_INDEPENDENT_WEEKLY_H2_V2_ECONOMIC_AUDIT"
    assert result["calibration_scores_reconstructed"] == 11
    assert result["ledgers_reconstructed"] == 24
    assert (output / "manifest.json").is_file()
