from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa import evaluate_directional_globex_meta_hedge_v4 as module


def component(source: str, profiles: tuple[str, ...], rows: int = 2) -> pd.DataFrame:
    output = []
    for index in range(rows):
        for profile in profiles:
            output.append(
                {
                    "ticker": "QQQ",
                    "source_ticker": "QQQ",
                    "trade_date": f"202501{index + 2:02d}",
                    "month": "202501",
                    "window_id": "W1",
                    "decision_time": "10:00",
                    "entry_time": "10:01",
                    "exit_time": "13:01",
                    "hold_minutes": 180,
                    "entry_spot": 100.0,
                    "exit_spot": 101.0,
                    "future_return_bps": 10.0,
                    "profile_id": profile,
                    "side": "LONG"
                    if (index + len(profile) + len(source)) % 2
                    else "SHORT",
                }
            )
    return pd.DataFrame(output)


def test_candidate_ledger_has_eight_pairs_plus_constants() -> None:
    ledgers = tuple(
        component(source, profiles)
        for source, profiles in module.COMPONENT_PROFILES.items()
    )
    candidates, experts = module.build_candidate_ledger(*ledgers)
    assert len(candidates) == 2
    assert len(experts) == 18
    for name in experts[:8]:
        assert np.array_equal(candidates[name], -candidates[f"inverse::{name}"])


def test_meta_probability_does_not_use_current_outcome() -> None:
    experts = [f"expert_{index}" for index in range(18)]
    history = pd.DataFrame({name: np.ones(21) for name in experts})
    history["future_return_bps"] = 50.0
    current = pd.DataFrame({name: [1.0] for name in experts})
    current["future_return_bps"] = -9999.0
    before = module.meta_probability(history, current, experts, 21)
    current["future_return_bps"] = 9999.0
    after = module.meta_probability(history, current, experts, 21)
    assert before == after == 1.0


def test_meta_cold_start_uses_uniform_paired_vote() -> None:
    experts = [f"expert_{index}" for index in range(18)]
    history = pd.DataFrame(columns=[*experts, "future_return_bps"])
    current = pd.DataFrame(
        {name: [1.0 if index < 9 else -1.0] for index, name in enumerate(experts)}
    )
    probability = module.meta_probability(history, current, experts, 63)
    assert probability == 0.5


def test_meta_memories_are_frozen() -> None:
    assert module.PROFILES == {
        "META_HEDGE21": 21,
        "META_HEDGE42": 42,
        "META_HEDGE63": 63,
    }
