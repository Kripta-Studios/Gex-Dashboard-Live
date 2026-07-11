from __future__ import annotations

import pandas as pd

from neural.jepa.analyze_event_option_portfolio_var_jepa import paired_test


def test_paired_test_tracks_variant_wins_for_lower_metric() -> None:
    result = paired_test(pd.Series([2.0, 3.0, 4.0]), pd.Series([1.0, 2.0, 5.0]), "less")
    assert result["pairs"] == 3
    assert result["variant_wins"] == 2
    assert result["control_wins"] == 1
    assert result["median_variant_minus_control"] == -1.0


def test_paired_test_tracks_variant_wins_for_higher_metric() -> None:
    result = paired_test(pd.Series([1.0, 2.0, 3.0]), pd.Series([2.0, 2.0, 4.0]), "greater")
    assert result["variant_wins"] == 2
    assert result["ties"] == 1
