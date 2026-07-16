from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa import evaluate_directional_globex_online_expert_v3 as module


def frame(rows: int, current_return: float = 0.0) -> pd.DataFrame:
    data = {name: np.ones(rows) for name in module.base_signal_names("QQQ")[1:]}
    data["future_return_bps"] = np.full(rows, current_return)
    return pd.DataFrame(data)


def test_expert_contract_contains_paired_28_signals() -> None:
    source = frame(3)
    signals = module.expert_signals(source, "QQQ")
    assert signals.shape == (3, 28)
    assert np.array_equal(signals[:, :14], -signals[:, 14:])


def test_hedge_uses_history_outcomes_but_not_current_outcome() -> None:
    history = frame(21, current_return=50.0)
    current = frame(1, current_return=-9999.0)
    before = module.hedge_probability(history, current, "QQQ")
    current["future_return_bps"] = 9999.0
    after = module.hedge_probability(history, current, "QQQ")
    assert before == after
    assert before > 0.5


def test_memories_are_frozen() -> None:
    assert module.PROFILES == {
        "ONLINE_EXPERT_HEDGE21": 21,
        "ONLINE_EXPERT_HEDGE42": 42,
        "ONLINE_EXPERT_HEDGE63": 63,
    }
