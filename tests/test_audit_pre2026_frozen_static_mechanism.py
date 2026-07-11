from __future__ import annotations

import pandas as pd

from neural.jepa.audit_pre2026_frozen_static_mechanism import passes_gate


def test_pre2026_static_gate_requires_every_month_and_hold() -> None:
    rows = []
    for month in ("202510", "202511", "202512"):
        for index in range(18):
            rows.append(
                {
                    "date": f"{month}{index + 1:02d}",
                    "month": month,
                    "action": "PUT",
                    "realized_return": 0.5 if index < 10 else -0.3,
                    "exit_minutes": 30,
                }
            )
    trades = pd.DataFrame(rows)
    summary = {
        "min_month_trades": 18,
        "win_rate": 10 / 18,
        "profit_factor": (10 * 0.5) / (8 * 0.3),
        "positive_month_rate": 1.0,
    }
    assert passes_gate(summary, trades)
    trades.loc[0, "exit_minutes"] = 29
    assert not passes_gate(summary, trades)
