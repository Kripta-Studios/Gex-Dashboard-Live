from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from neural.jepa import evaluate_directional_vol_complex_v1 as subject


def daily_series() -> dict[str, pd.DataFrame]:
    dates = pd.date_range("2025-01-01", "2025-01-10", freq="D")
    return {
        series: pd.DataFrame(
            {"source_date": dates, "value": np.arange(1.0, len(dates) + 1.0)}
        )
        for series in subject.SERIES_FILES
    }


def minute_frame(day: str, start: float, step: float) -> pd.DataFrame:
    timestamps = pd.date_range(f"{day} 09:30", f"{day} 16:00", freq="min")
    close = start + np.arange(len(timestamps), dtype=np.float64) * step
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": close - step / 2.0,
            "high": close + abs(step),
            "low": close - abs(step),
            "close": close,
        },
        index=timestamps,
    )
    return frame


def test_term_features_are_strictly_lagged() -> None:
    features, source_dates = subject.build_term_feature_row(daily_series(), "20250110")
    assert set(source_dates.values()) == {"20250109"}
    assert features["cboe_vix_previous_close"] == 9.0
    assert features["cboe_vix_change_1obs"] == 1.0
    assert features["cboe_vix_change_5obs"] == 5.0


def test_strict_prior_observation_rejects_stale_close() -> None:
    frame = pd.DataFrame(
        {
            "source_date": pd.date_range("2025-01-01", "2025-01-06", freq="D"),
            "value": np.arange(6.0),
        }
    )
    with pytest.raises(AssertionError, match="stale"):
        subject._strict_prior_observation(frame, "20250120")


def test_vix_features_ignore_every_bar_after_decision() -> None:
    day = "2025-01-10"
    previous_day = "2025-01-09"
    vix = minute_frame("2025-01-10", 18.0, 0.002)
    previous = minute_frame("2025-01-09", 17.0, 0.001)
    spx = minute_frame("2025-01-10", 5900.0, 0.05)
    before = subject.build_vix_feature_row(day, vix, previous_day, previous, spx)

    mutated = vix.copy()
    future = mutated["timestamp"].dt.strftime("%H:%M") > subject.parent.DECISION_TIME
    mutated.loc[future, ["open", "high", "low", "close"]] *= 3.0
    after = subject.build_vix_feature_row(day, mutated, previous_day, previous, spx)
    assert before == after


def walkforward_frame() -> pd.DataFrame:
    rows: list[dict] = []
    for index in range(410):
        day = (pd.Timestamp("2023-01-01") + pd.Timedelta(days=index)).strftime("%Y%m%d")
        rows.append(
            {
                "ticker": "QQQ",
                "source_ticker": "QQQ",
                "trade_date": day,
                "month": day[:6],
                "decision_time": "10:35",
                "entry_time": "10:36",
                "exit_time": "13:36",
                "hold_minutes": 180,
                "entry_spot": 100.0,
                "exit_spot": 101.0,
                "future_return_bps": 10.0,
                "qqq_ret_5m": float(index),
                "semantic": float(index % 7),
                "vix_feature": 20.0,
                "term_feature": 1.0,
                "vol_source_available": True,
            }
        )
    for day, available in (("20250102", True), ("20250103", False)):
        rows.append(
            {
                "ticker": "QQQ",
                "source_ticker": "QQQ",
                "trade_date": day,
                "month": "202501",
                "decision_time": "10:35",
                "entry_time": "10:36",
                "exit_time": "13:36",
                "hold_minutes": 180,
                "entry_spot": 100.0,
                "exit_spot": 101.0,
                "future_return_bps": 10.0,
                "qqq_ret_5m": 1.0,
                "semantic": 2.0,
                "vix_feature": 20.0 if available else np.nan,
                "term_feature": 1.0,
                "vol_source_available": available,
            }
        )
    return pd.DataFrame(rows)


def test_missing_vix_test_row_uses_exact_parent_prediction(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_predictor(
        train: pd.DataFrame,
        test: pd.DataFrame,
        technical_features: list[str],
        model_features: list[str],
    ) -> tuple[np.ndarray, np.ndarray]:
        del train, technical_features
        if model_features == ["qqq_ret_5m", "semantic"]:
            prediction = np.array([10.0, -11.0])
        else:
            prediction = np.full(len(test), 99.0)
        return prediction, np.zeros(len(test))

    monkeypatch.setattr(subject.parent, "fit_residual_predictor", fake_predictor)
    trades = subject.run_walkforward(
        walkforward_frame(),
        ["202501"],
        ["qqq_ret_5m"],
        ["semantic"],
        ["vix_feature"],
        ["term_feature"],
        profiles_by_ticker={"QQQ": subject.VIX_PROFILE},
    ).sort_values("trade_date")
    assert trades["predicted_return_bps"].tolist() == [99.0, -11.0]
    assert trades["fallback_parent"].tolist() == [False, True]
    assert trades["prediction_origin"].tolist() == [subject.VIX_PROFILE, subject.parent.SEMANTIC_PROFILE]


def test_vix_feature_contract_has_no_duplicates() -> None:
    names = subject.vix_feature_names()
    assert len(names) == 30
    assert len(names) == len(set(names))
