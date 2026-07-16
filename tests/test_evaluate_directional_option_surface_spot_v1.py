from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa import evaluate_directional_option_surface_spot_v1 as module


def test_decision_windows_are_non_overlapping() -> None:
    minutes = [int(clock[:2]) * 60 + int(clock[3:]) for clock in module.DECISION_TIMES]
    assert all(right - left > 60 for left, right in zip(minutes, minutes[1:]))
    assert 10 * len(minutes) > 12


def test_feature_partition_removes_surface_from_control() -> None:
    frame = pd.DataFrame(
        {
            "ticker": ["QQQ", "SPXW", "SPY"],
            "expiry_mode": ["zero_dte"] * 3,
            "nearest_level_name": ["ib_high"] * 3,
            "trade_date": ["20250102"] * 3,
            "expiration": ["2025-01-02"] * 3,
            "timestamp": ["2025-01-02T10:35:00"] * 3,
            "time": ["10:35"] * 3,
            "underlying_ticker": ["QQQ", "SPXW", "SPY"],
            "minute": [635] * 3,
            "ret_5m_bps": [1.0, 2.0, 3.0],
            "call_d35_iv": [0.2, 0.21, 0.22],
            "put_d35_iv": [0.21, 0.22, 0.23],
            "phys_d35_iv_mean": [0.205, 0.215, 0.225],
            "ctx_spx_ret_5m_bps": [2.0] * 3,
            "future_close_ret_bps": [999.0] * 3,
            "call_d35_opt_exit_ret": [99.0] * 3,
        }
    )
    _, price, surface = module.build_live_feature_frame(frame)
    assert "ret_5m_bps" in price
    assert "call_d35_iv" not in price
    assert "ctx_spx_ret_5m_bps" not in price
    assert "call_d35_iv" in surface
    assert "future_close_ret_bps" not in surface
    assert "call_d35_opt_exit_ret" not in surface


def test_magnitude_weights_are_clipped() -> None:
    weights = module.magnitude_weights(pd.Series([-1.0, 10.0, 1000.0]))
    assert np.allclose(weights, np.array([0.5, 1.0, 10.0]))


def test_development_advance_requires_surface_and_all_ticker_gates() -> None:
    rows = []
    for profile in module.PROFILES:
        for ticker in ("QQQ", "SPX", "SPY"):
            for month in [f"2025{i:02d}" for i in range(1, 13)]:
                for index in range(13):
                    rows.append(
                        {
                            "ticker": ticker,
                            "profile_id": profile,
                            "month": month,
                            "net_bps": 2.0 if profile == module.SURFACE_PROFILE or index < 7 else -2.0,
                        }
                    )
    selected, _, advance = module.select_profile(pd.DataFrame(rows))
    assert selected == module.SURFACE_PROFILE
    assert advance is True
