from __future__ import annotations

import numpy as np
import pandas as pd

from neural.jepa.evaluate_adajepa_shadow_adapter import evaluate_frame


def _rows(target_shift: float = 0.0) -> pd.DataFrame:
    rows = []
    for day, date in enumerate(("20260102", "20260103")):
        for index, minute in enumerate((635, 640, 645)):
            row = {
                "ticker": "SPY",
                "trade_date": date,
                "timestamp": pd.Timestamp(f"2026-01-{2 + day:02d} 10:{35 + index * 5:02d}"),
                "target_timestamp": pd.Timestamp(f"2026-01-{2 + day:02d} 10:{40 + index * 5:02d}"),
                "target_available_after_timestamp": pd.Timestamp(f"2026-01-{2 + day:02d} 10:{40 + index * 5:02d}"),
                "minute": minute,
            }
            for dim in range(32):
                row[f"z_t_{dim:02d}"] = 0.1 * index
                row[f"pred_z_{dim:02d}"] = 0.1 * index + 0.2
                row[f"target_z_{dim:02d}"] = 0.1 * index + (target_shift if index == 2 else 0.0)
            rows.append(row)
    return pd.DataFrame(rows)


def test_future_target_does_not_change_earlier_shadow_predictions() -> None:
    base = evaluate_frame(_rows(0.0), learning_rate=0.05, grad_clip=1.0, max_parameter_norm=0.5, device="cpu")
    changed = evaluate_frame(_rows(10.0), learning_rate=0.05, grad_clip=1.0, max_parameter_norm=0.5, device="cpu")
    for date in ("20260102", "20260103"):
        left = base[base["trade_date"].eq(date)].reset_index(drop=True)
        right = changed[changed["trade_date"].eq(date)].reset_index(drop=True)
        assert np.allclose(left.loc[:1, "adapted_error"], right.loc[:1, "adapted_error"])


def test_adapter_resets_at_each_ticker_day() -> None:
    evaluated = evaluate_frame(_rows(), learning_rate=0.05, grad_clip=1.0, max_parameter_norm=0.5, device="cpu")
    first = evaluated.groupby("trade_date", sort=True).first()
    assert first["updates_before_prediction"].eq(0).all()
    assert first["adapter_parameter_norm"].eq(0.0).all()
