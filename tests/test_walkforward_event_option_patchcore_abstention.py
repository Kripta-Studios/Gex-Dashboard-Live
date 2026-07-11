from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa.walkforward_event_option_patchcore_abstention import (
    add_patchcore_distance,
    fit_patchcore_bank,
)


def test_patchcore_bank_is_deterministic_and_train_only() -> None:
    train = pd.DataFrame({"x": [0.0, 1.0, 2.0, 9.0], "y": [0.0, 0.0, 1.0, 9.0]})
    first = fit_patchcore_bank(train, ["x", "y"], 2)
    second = fit_patchcore_bank(train, ["x", "y"], 2)
    assert np.array_equal(first.source_indices, second.source_indices)
    assert np.allclose(first.centers, second.centers)
    before = first.means.copy()
    first.distances(pd.DataFrame({"x": [1000.0], "y": [1000.0]}))
    assert np.array_equal(first.means, before)


def test_patchcore_distance_only_adds_an_abstention_feature() -> None:
    train = pd.DataFrame({"x": [0.0, 1.0, 2.0], "ticker": ["SPXW"] * 3})
    bank = fit_patchcore_bank(train, ["x"], 2)
    scored = pd.DataFrame(
        {"ticker": ["SPXW", "SPXW"], "x": [0.5, 20.0], "action": ["CALL", "PUT"], "score": [0.2, 0.4]}
    )
    output = add_patchcore_distance(scored, {"SPXW": bank})
    assert output["action"].tolist() == scored["action"].tolist()
    assert output["score"].tolist() == scored["score"].tolist()
    assert output.loc[1, "patchcore_distance"] > output.loc[0, "patchcore_distance"]
