from __future__ import annotations

import pandas as pd

from neural.jepa import evaluate_dual_leg_event_volatility_v1 as module


def frames() -> dict[str, pd.DataFrame]:
    rows = []
    for clock, hold in (("10:30", 60), ("11:00", 30), ("11:30", 30), ("12:00", 30)):
        rows.append(
            {
                "trade_date": "20250102",
                "timestamp": pd.Timestamp(f"2025-01-02 {clock}"),
                "call_return": 0.5,
                "put_return": -0.3,
                "call_exit_minutes": hold,
                "put_exit_minutes": hold,
            }
        )
    return {ticker: pd.DataFrame(rows) for ticker in module.TICKERS}


def test_scheduler_rejects_entries_until_all_tickers_closed() -> None:
    trades = module.run_scheduler(frames())
    accepted = (
        trades.loc[trades["ticker"].eq("QQQ"), "entry_timestamp"]
        .dt.strftime("%H:%M")
        .tolist()
    )
    assert accepted == ["10:30", "11:30", "12:00"]
    assert trades.groupby(["trade_date", "entry_timestamp"]).size().eq(3).all()


def test_equal_capital_return_includes_haircut() -> None:
    trades = module.run_scheduler(frames())
    assert trades["gross_return"].eq(0.1).all()
    assert trades["net_return"].eq(0.098).all()


def test_delta_contract_is_frozen_per_ticker() -> None:
    assert module.DELTA_BUCKET == {"QQQ": "d35", "SPXW": "d25", "SPY": "d35"}
