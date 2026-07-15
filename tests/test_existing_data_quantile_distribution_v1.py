from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from neural.jepa import existing_data_quantile_distribution_v1 as subject


EXPECTED_SPEC_SHA256 = "53940684518834bed0f45272151f030d740428516ce5c86443d92cf318245499"


def test_frozen_spec_and_model_contract_are_exact() -> None:
    assert subject.frozen_spec_sha256() == EXPECTED_SPEC_SHA256
    assert subject.QUANTILE_ALPHAS == (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
    assert subject.UTILITY_WEIGHTS == (0.15, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.15)
    assert sum(subject.UTILITY_WEIGHTS) == pytest.approx(1.0)
    assert subject.FROZEN_QUANTILE_PARAMS["objective"] == "quantile"


def test_rearrangement_utility_and_win_probability_are_exact() -> None:
    ordered = np.array([-0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8])
    raw = np.vstack([ordered[::-1], np.arange(1.0, 10.0), -np.arange(1.0, 10.0)])
    quantiles, utility, pwin = subject.summarize_quantiles(raw)
    assert np.all(np.diff(quantiles, axis=1) >= 0.0)
    assert quantiles[0].tolist() == pytest.approx(ordered.tolist())
    assert utility[0] == pytest.approx(0.0)
    assert pwin.tolist() == pytest.approx([0.5, 0.9, 0.1])


def test_piecewise_cdf_interpolation_and_duplicate_zero_are_conservative() -> None:
    interpolated = np.array([-0.8, -0.6, -0.4, -0.1, 0.1, 0.3, 0.5, 0.7, 0.9])
    duplicate_zero = np.array([-0.8, -0.6, -0.4, 0.0, 0.0, 0.3, 0.5, 0.7, 0.9])
    _, _, pwin = subject.summarize_quantiles(np.vstack([interpolated, duplicate_zero]))
    assert pwin[0] == pytest.approx(0.55)
    assert pwin[1] == pytest.approx(0.5)


def test_utility_is_the_frozen_piecewise_quantile_integral() -> None:
    raw = np.arange(1.0, 10.0).reshape(1, -1)
    _, utility, _ = subject.summarize_quantiles(raw)
    expected = 0.15 * 1.0 + 0.10 * sum(range(2, 9)) + 0.15 * 9.0
    assert utility[0] == pytest.approx(expected)


def test_policy_enforces_tie_threshold_margin_and_selected_pwin() -> None:
    scores = pd.DataFrame(
        {
            "row": ["call", "put", "tie", "low_utility", "low_margin", "low_pwin"],
            "utility_call": [0.4, 0.1, 0.3, 0.19, 0.30, 0.5],
            "utility_put": [0.1, 0.5, 0.3, 0.10, 0.25, 0.1],
            "pwin_call": [0.7, 0.8, 0.9, 0.8, 0.8, 0.49],
            "pwin_put": [0.8, 0.6, 0.9, 0.8, 0.8, 0.9],
        }
    )
    selected = subject.apply_quantile_policy(scores, utility_threshold=0.2, side_margin=0.1)
    assert selected["row"].tolist() == ["call", "put"]
    assert selected["action"].tolist() == ["CALL", "PUT"]
    assert selected["selected_pwin"].tolist() == pytest.approx([0.7, 0.6])


def test_policy_mapping_never_uses_realized_outcomes() -> None:
    scores = pd.DataFrame(
        {
            "utility_call": [0.4, 0.1],
            "utility_put": [0.1, 0.5],
            "pwin_call": [0.7, 0.8],
            "pwin_put": [0.8, 0.6],
            "realized_return": [-100.0, 100.0],
            "exit_minutes": [30.0, 180.0],
        }
    )
    first = subject.apply_quantile_policy(scores, utility_threshold=0.0, side_margin=0.0)
    mutated = scores.assign(realized_return=[999.0, -999.0], exit_minutes=[999.0, -1.0])
    second = subject.apply_quantile_policy(mutated, utility_threshold=0.0, side_margin=0.0)
    assert first[["action", "score", "selected_pwin"]].equals(
        second[["action", "score", "selected_pwin"]]
    )


def test_training_percentile_grid_is_exact_and_finite() -> None:
    scores = pd.DataFrame(
        {
            "utility_max": np.arange(100, dtype=float),
            "side_margin_raw": np.arange(100, dtype=float) / 10.0,
        }
    )
    grid = subject.training_percentile_grid(scores)
    assert len(grid) == 42
    assert grid[0] == {
        "utility_percentile": 50,
        "margin_percentile": 0,
        "utility_threshold": pytest.approx(49.5),
        "side_margin": pytest.approx(0.0),
    }
    assert grid[-1]["utility_percentile"] == 95
    assert grid[-1]["margin_percentile"] == 50
    with pytest.raises(AssertionError, match="non-empty and finite"):
        subject.training_percentile_grid(scores.assign(utility_max=np.nan))


def test_train_only_imputer_does_not_refit_while_scoring() -> None:
    train = pd.DataFrame({"a": [1.0, 3.0, np.nan], "all_missing": [np.nan] * 3})
    _, medians = subject._training_matrix(train, ["a", "all_missing"])
    score = pd.DataFrame({"a": [1_000_000.0, np.nan], "all_missing": [8.0, np.nan]})
    transformed = subject._transform_matrix(score, ["a", "all_missing"], medians)
    assert medians.to_dict() == {"a": 2.0, "all_missing": 0.0}
    assert transformed.iloc[1].to_dict() == {"a": 2.0, "all_missing": 0.0}


def test_fit_creates_exact_side_alpha_heads_and_seed_offsets(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[dict[str, object]] = []

    class FakeRegressor:
        def __init__(self, **params: object) -> None:
            self.params = params
            created.append(params)

        def fit(self, matrix: pd.DataFrame, target: np.ndarray) -> "FakeRegressor":
            assert len(matrix) == len(target) == 100
            return self

        def predict(self, matrix: pd.DataFrame) -> np.ndarray:
            return np.full(len(matrix), float(self.params["alpha"]))

    monkeypatch.setattr(subject.lgb, "LGBMRegressor", FakeRegressor)
    train = pd.DataFrame(
        {
            "feature": np.linspace(-1.0, 1.0, 100),
            "call_return": np.linspace(-0.5, 1.0, 100),
            "put_return": np.linspace(1.0, -0.5, 100),
        }
    )
    fitted = subject.fit_quantile_distribution(
        train,
        ["feature"],
        call_return_col="call_return",
        put_return_col="put_return",
        base_seed=42,
    )
    assert len(created) == 18
    assert [params["alpha"] for params in created[:9]] == list(subject.QUANTILE_ALPHAS)
    assert [params["random_state"] for params in created[:9]] == list(range(10_043, 10_052))
    assert [params["random_state"] for params in created[9:]] == list(range(20_043, 20_052))
    scored = fitted.score(train.iloc[:2])
    assert scored["utility_call"].tolist() == pytest.approx([0.5, 0.5])
    assert scored["utility_put"].tolist() == pytest.approx([0.5, 0.5])


def test_development_guard_seals_2024_and_later() -> None:
    subject.assert_development_only(pd.DataFrame({"trade_date": ["20231229"]}))
    with pytest.raises(AssertionError, match="sealed"):
        subject.assert_development_only(pd.DataFrame({"trade_date": ["20240102"]}))
