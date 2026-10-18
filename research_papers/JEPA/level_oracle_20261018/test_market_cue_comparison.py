"""Synthetic economic clocks and calibration, no historical sources."""

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import market_cue_comparison as core
from test_market_cue_vectors import arrays


def offers():
    actions = pd.DataFrame(
        dict(action_id=[8, 3, 5, 7, 9, 10], state_i=[60, 60, 61, 62, 65, 66])
    )
    labels = pd.DataFrame(
        dict(
            action_id=actions.action_id,
            status=["FILLED", "NO_FILL", "FILLED", "FILLED", "FILLED", "FILLED"],
            exit_i=[63, 61, 64, 64, 67, 68],
            net_base=[99.0, 0, 4, 999, -2, 1],
            net_adverse=[98.0, 0, 3, 998, -3, 0],
        )
    )
    return actions, labels


def test_no_fill_no_rescue_exit_clock_ties_and_has_filled():
    actions, labels = offers()
    _, attempts, ledger = core.schedule(actions, labels, [1, 1, 2, 20, 3, 99], 390)
    assert attempts.action_id.tolist() == [3, 5, 9]
    assert attempts.has_filled_before.tolist() == [0, 0, 1]
    assert ledger.action_id.tolist() == [5, 9]
    _, attempts, _ = core.schedule(actions, labels, np.zeros(6), 390)
    assert attempts.empty


def test_short_clock_and_label_identity_reject_future_exit():
    actions = pd.DataFrame(dict(action_id=[1], state_i=[195]))
    labels = pd.DataFrame(
        dict(
            action_id=[1],
            status=["FILLED"],
            exit_i=[205],
            net_base=[2.0],
            net_adverse=[1.0],
        )
    )
    assert len(core.schedule(actions, labels, [1], 210)[2]) == 1
    labels.loc[0, "exit_i"] = 206
    with pytest.raises(ValueError, match="filled exit"):
        core.schedule(actions, labels, [1], 210)


def test_calibration_bins_residual_and_weighted_merge():
    one = core.calibration_sums([10, 20], [0, 30], 100, [0.25, 0.75])
    two = core.calibration_sums([10], [0], 100, [1])
    row = core.calibration_report([one, two])[4]
    assert row["n"] == 3 and row["weight"] == 2
    assert row["predicted_usd"] == 13.75
    assert row["realized_usd"] == 11.25
    assert row["mean_residual_usd"] == -2.5
    assert row["rmse_usd"] == row["mae_usd"] == 10
    assert core.calibration_report([])[0]["predicted_usd"] is None


def test_missing_calendar_not_economic_loss_or_universal_pass():
    rows = [
        dict(
            ticker="SPY",
            date="20260102",
            source_status="COMPLETE",
            trades=1,
            net_base=5.0,
            net_adverse=4.0,
        ),
        dict(
            ticker="SPY",
            date="20260401",
            source_status="MISSING_SOURCE",
            trades=0,
            net_base=0.0,
            net_adverse=0.0,
        ),
    ]
    result = core.coverage_report(rows)
    assert result["observable_daily_pass"] and not result["universal_daily_pass"]
    assert result["universal_daily_status"] == "NO_EVALUABLE"
    rows[0]["trades"] = 0
    assert not core.coverage_report(rows)["observable_daily_pass"]


def test_original_flatten_bitexact_without_importing_training_stack():
    # Execute ONLY the inspected pure reference function from its source AST;
    # never import train_models/Torch, initialize models, or read market data.
    path = Path(core.__file__).with_name("train_models.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "flatten_gbt"
    )
    namespace = {"np": np}
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace
    )
    pack = arrays()
    rng = np.random.default_rng(99)
    pack["maps"] = rng.standard_normal((2, 20, 5, 64)).astype(np.float32)
    pack["map_mask"] = rng.integers(0, 2, (2, 20, 5))
    ai, si = np.array([1, 0, 1]), np.array([0, 1, 1])
    original = dict(
        pack, token_mask=np.stack((pack["token_mask"], pack["bar_mask"]), axis=-1)
    )
    expected = namespace["flatten_gbt"](original, ai, si)
    result = core.flatten_original(pack, ai, si)
    assert result.shape == (3, 1954)
    assert result.tobytes() == expected.tobytes()


def test_pf_infinite_separate_from_empty_or_all_zero():
    assert core.trade_metrics(pd.DataFrame(dict(net_base=[1.0], net_adverse=[0.0])))[
        "net_base_pf_infinite"
    ]
    assert not core.trade_metrics(pd.DataFrame(dict(net_base=[], net_adverse=[])))[
        "net_base_pf_infinite"
    ]
