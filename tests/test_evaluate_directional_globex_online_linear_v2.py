from __future__ import annotations

import pandas as pd

from neural.jepa import evaluate_directional_globex_online_linear_v2 as module


def test_compact_features_match_futures_to_target() -> None:
    qqq = module.feature_names("QQQ")
    spx = module.feature_names("SPX")
    spy = module.feature_names("SPY")
    assert len(qqq) == len(spx) == len(spy) == 37
    assert "nq_ret_6h" in qqq and "es_ret_6h" not in qqq
    assert "es_ret_6h" in spx and "nq_ret_6h" not in spx
    assert spx == spy


def test_online_walkforward_never_uses_same_day() -> None:
    dates = pd.date_range("2024-10-01", periods=70, freq="B")
    rows = []
    features = module.feature_names("QQQ")
    for index, date in enumerate(dates):
        row = {
            "ticker": "QQQ",
            "source_ticker": "QQQ",
            "trade_date": f"{date:%Y%m%d}",
            "month": f"{date:%Y%m}",
            "window_id": "W1",
            "decision_time": "10:00",
            "entry_time": "10:01",
            "exit_time": "13:01",
            "hold_minutes": 180,
            "entry_spot": 100.0,
            "exit_spot": 101.0,
            "future_return_bps": 10.0 if index % 2 else -10.0,
        }
        row.update(
            {
                feature: float((index + offset) % 7)
                for offset, feature in enumerate(features)
            }
        )
        rows.append(row)
    daily = pd.DataFrame(rows)
    test_month = str(daily.iloc[-1]["month"])
    output = module.run_online_walkforward(
        daily,
        [test_month],
        selected_profile="ONLINE_LINEAR_ROLL63",
    )
    first = output.iloc[0]
    expected = int((daily["trade_date"] < first["trade_date"]).sum())
    assert first["training_rows"] == min(63, expected)
    assert first["training_rows"] < len(daily)


def test_memory_profiles_are_frozen() -> None:
    assert module.PROFILES == {
        "ONLINE_LINEAR_ROLL63": 63,
        "ONLINE_LINEAR_ROLL126": 126,
        "ONLINE_LINEAR_EXPANDING": None,
    }
