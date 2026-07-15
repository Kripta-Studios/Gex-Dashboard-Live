from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from neural.jepa import evaluate_king_gex_slope_v1 as subject


def _metric(
    *, trades: int = 18, pf: float = 1.3, wr: float = 0.5, pnl: float = 1.0
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


def test_protocol_is_fixed_rule_and_keeps_holdouts_closed() -> None:
    protocol = subject.runner_protocol()
    assert protocol["arms"] == ["K0_LEVEL", "K1_ALIGNED"]
    assert protocol["candidate_arm"] == "K1_ALIGNED"
    assert protocol["fit"] is None
    assert protocol["threshold"] is None
    assert protocol["grid"]["first_minute"] == 680
    assert protocol["source_hashes"]["data_gate_clarification"] == (
        "17d00155c315f007f25d87b22220c161a8360f9ea54128df665224ae5422c504"
    )
    assert protocol["outer_2024_2025_opened"] is False
    assert protocol["holdout_2026_opened"] is False


def test_level_and_aligned_rules_map_gamma_regime_to_action() -> None:
    frame = pd.DataFrame(
        {
            "ret_15m_bps": [5.0, 5.0, 5.0, -5.0],
            "net_gex_proxy": [-10.0, 10.0, -10.0, 10.0],
            "net_gex_slope15": [-2.0, 2.0, 2.0, 2.0],
        }
    )
    level = subject.policy_candidates(frame, "K0_LEVEL")
    assert level["action"].tolist() == ["CALL", "PUT", "CALL", "CALL"]
    aligned = subject.policy_candidates(frame, "K1_ALIGNED")
    assert aligned.index.tolist() == [0, 1, 3]
    assert aligned["action"].tolist() == ["CALL", "PUT", "CALL"]
    assert aligned["score"].eq(1.0).all()


def test_zero_and_nonfinite_inputs_abstain() -> None:
    frame = pd.DataFrame(
        {
            "ret_15m_bps": [0.0, 1.0, 1.0],
            "net_gex_proxy": [1.0, 0.0, np.nan],
            "net_gex_slope15": [1.0, 1.0, 1.0],
        }
    )
    assert subject.policy_candidates(frame, "K0_LEVEL").empty
    assert subject.policy_candidates(frame, "K1_ALIGNED").empty


def test_gate_is_strictly_conjunctive() -> None:
    assert subject.gate_pass(_metric())
    for changed in (
        {"trades": 17},
        {"profit_factor": 1.299},
        {"win_rate": 0.499},
        {"pnl": 0.0},
        {"minimum_hold": 29.0},
    ):
        metric = _metric()
        metric.update(changed)
        assert not subject.gate_pass(metric)


def test_cell_checkpoint_is_reusable_and_hash_validated(tmp_path: Path) -> None:
    run_identity = {
        "schema": subject.RUN_CHECKPOINT_SCHEMA,
        "experiment": subject.EXPERIMENT,
        "months": list(subject.DEVELOPMENT_MONTHS),
        "runner_protocol_sha256": "p",
        "master_sha256": "m",
        "wall_state_sha256": "w",
        "protocol_document_sha256": "d",
        "code_hashes": {"runner": "c"},
    }
    identity = subject._cell_identity(
        run_identity, month="202301", ticker="SPXW", arm="K1_ALIGNED"
    )
    metrics = pd.DataFrame([{"month": "202301", "gate_pass": False}])
    trades = pd.DataFrame(columns=["ticker", "trade_date", "minute"])
    directory = tmp_path / "cell"
    subject._write_cell_checkpoint(directory, identity, metrics, trades)
    cached = subject._read_cell_checkpoint(directory, identity)
    assert cached is not None
    assert len(cached[0]) == 1
    assert cached[1].empty
    (directory / "metrics.csv").write_text("corrupt\n", encoding="utf-8")
    assert subject._read_cell_checkpoint(directory, identity) is None
