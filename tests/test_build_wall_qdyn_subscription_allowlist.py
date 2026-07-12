from __future__ import annotations

from pathlib import Path

import pandas as pd

from neural.jepa.build_wall_native_quote_sidecar import sha256_file
from neural.jepa.build_wall_qdyn_subscription_allowlist import (
    audit_session,
    line_hash,
)


def _source(tmp_path: Path, quotes: pd.DataFrame) -> dict[str, str]:
    quote_path = tmp_path / "quotes.parquet"
    manifest_path = tmp_path / "manifest.json"
    quotes.to_parquet(quote_path, index=False)
    manifest_path.write_text("{}", encoding="utf-8")
    return {
        "ticker": "QQQ",
        "trade_date": "20240102",
        "origin": "test",
        "quotes_path": str(quote_path),
        "quotes_sha256": sha256_file(quote_path),
        "session_manifest_path": str(manifest_path),
        "session_manifest_sha256": sha256_file(manifest_path),
    }


def _candidate(*, proximity: bool = True) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event_id": "event-a",
                "ticker": "QQQ",
                "trade_date": "20240102",
                "decision_dt": pd.Timestamp("2024-01-02 10:25:00"),
                "subscription_dt": pd.Timestamp("2024-01-02 10:20:00"),
                "candidate_wall_strike": 400.0,
                "subscription_min_wall_distance_bps": 5.0,
                "wall_proximity_eligible_v1": proximity,
            }
        ]
    )


def _quotes(rights: tuple[str, ...], *, timestamp: str = "2024-01-02 10:20:00") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "QQQ",
                "expiration": "20240102",
                "timestamp": pd.Timestamp(timestamp),
                "strike": 400.0,
                "right": right,
            }
            for right in rights
        ]
    )


def test_exact_both_rights_at_tminus5_are_eligible(tmp_path: Path) -> None:
    result, audit = audit_session(_source(tmp_path, _quotes(("C", "P"))), _candidate())
    row = result.iloc[0]
    assert bool(row["subscription_timestamp_covered"])
    assert bool(row["exact_call_listed_tminus5m"])
    assert bool(row["exact_put_listed_tminus5m"])
    assert bool(row["causal_subscription_eligible_v1r1"])
    assert row["eligibility_reason"] == "eligible"
    assert audit["candidate_rows"] == 1


def test_missing_put_is_rejected(tmp_path: Path) -> None:
    result, _ = audit_session(_source(tmp_path, _quotes(("C",))), _candidate())
    row = result.iloc[0]
    assert not bool(row["exact_put_listed_tminus5m"])
    assert not bool(row["causal_subscription_eligible_v1r1"])
    assert row["eligibility_reason"] == "put_not_listed"


def test_asof_or_future_listing_does_not_prove_subscription(tmp_path: Path) -> None:
    result, _ = audit_session(
        _source(tmp_path, _quotes(("C", "P"), timestamp="2024-01-02 10:21:00")),
        _candidate(),
    )
    row = result.iloc[0]
    assert not bool(row["subscription_timestamp_covered"])
    assert not bool(row["causal_subscription_eligible_v1r1"])
    assert row["eligibility_reason"] == "subscription_timestamp_not_covered"


def test_wall_proximity_is_required_even_when_contract_is_listed(tmp_path: Path) -> None:
    result, _ = audit_session(
        _source(tmp_path, _quotes(("CALL", "PUT"))), _candidate(proximity=False)
    )
    row = result.iloc[0]
    assert bool(row["exact_both_rights_listed_tminus5m"])
    assert not bool(row["causal_subscription_eligible_v1r1"])
    assert row["eligibility_reason"] == "wall_not_in_tminus5_radius"


def test_near_but_nonidentical_strike_is_not_listed(tmp_path: Path) -> None:
    quotes = _quotes(("C", "P"))
    quotes["strike"] = 400.0 + 5e-10
    result, _ = audit_session(_source(tmp_path, quotes), _candidate())
    row = result.iloc[0]
    assert not bool(row["exact_both_rights_listed_tminus5m"])
    assert row["eligibility_reason"] == "exact_strike_not_listed"


def test_line_hash_is_order_invariant() -> None:
    assert line_hash(["b", "a"]) == line_hash(["a", "b"])
