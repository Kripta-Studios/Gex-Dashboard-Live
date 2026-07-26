from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import math

import httpx
import pytest

from modules.volatility_indices import (
    OptionQuote,
    VolatilityDataError,
    calculate_term_variance,
    calculate_vix1d,
    calculate_vvix,
    choose_vix1d_expirations,
    choose_vvix_expirations,
    derive_underlying_price,
    flatten_theta_rows,
    normalize_option_quotes,
)
from services.king_node_service import ThetaOptionsVolatilityClient

NOW = datetime(2026, 7, 27, 14, 0, tzinfo=UTC)


def chain(expiration: date, *, center: float = 100.0) -> list[OptionQuote]:
    rows: list[OptionQuote] = []
    strikes = [center + offset for offset in range(-40, 45, 5) if center + offset > 0]
    for strike in strikes:
        time_value = 6.0 * math.exp(-abs(strike - center) / 18.0) + 0.25
        call_mid = max(center - strike, 0.0) + time_value
        put_mid = max(strike - center, 0.0) + time_value
        for right, midpoint in (("C", call_mid), ("P", put_mid)):
            rows.append(
                OptionQuote(
                    strike=float(strike),
                    right=right,
                    bid=max(0.01, midpoint - 0.05),
                    ask=midpoint + 0.05,
                    timestamp=NOW,
                    expiration=expiration,
                )
            )
    return rows


def test_flatten_nested_theta_rows() -> None:
    payload = {
        "response": [
            {
                "contract": {"strike": 100, "right": "C"},
                "data": [{"bid": 1.0, "ask": 1.2, "timestamp": NOW.isoformat()}],
            }
        ]
    }
    assert flatten_theta_rows(payload) == [
        {
            "strike": 100,
            "right": "C",
            "bid": 1.0,
            "ask": 1.2,
            "timestamp": NOW.isoformat(),
        }
    ]


def test_underlying_median_and_dispersion_guard() -> None:
    payload = [
        {"underlying_price": value, "underlying_timestamp": NOW.isoformat()}
        for value in (99.99, 100.0, 100.01, 100.0)
    ]
    result = derive_underlying_price(
        payload,
        now=NOW,
        max_age_seconds=10,
        min_observations=3,
        max_dispersion_pct=0.1,
    )
    assert result.value == pytest.approx(100.0)
    with pytest.raises(VolatilityDataError, match="dispersion"):
        derive_underlying_price(
            payload + [
                {"underlying_price": 102, "underlying_timestamp": NOW.isoformat()}
            ],
            now=NOW,
            max_age_seconds=10,
            min_observations=3,
            max_dispersion_pct=0.1,
        )


def test_normalize_rejects_stale_and_bad_nbbo() -> None:
    payload = [
        {
            "strike": 100,
            "right": "C",
            "bid": 1,
            "ask": 2,
            "timestamp": NOW.isoformat(),
        },
        {
            "strike": 100,
            "right": "P",
            "bid": 3,
            "ask": 2,
            "timestamp": NOW.isoformat(),
        },
        {
            "strike": 105,
            "right": "C",
            "bid": 1,
            "ask": 2,
            "timestamp": (NOW - timedelta(minutes=5)).isoformat(),
        },
    ]
    quotes = normalize_option_quotes(payload, now=NOW, max_age_seconds=60)
    assert [(quote.strike, quote.right) for quote in quotes] == [(100.0, "C")]


def test_term_variance_forward_k0_and_wings() -> None:
    expiration = date(2026, 7, 27)
    term = calculate_term_variance(
        chain(expiration),
        expiration=expiration,
        minutes_to_expiration=375,
        minutes_per_year=102060,
        rate_decimal=0.0433,
        min_valid_strikes=8,
    )
    assert term.forward == pytest.approx(100.0, abs=1e-8)
    assert term.k0 == 100.0
    assert term.call_count > 0
    assert term.put_count > 0
    assert term.variance > 0


def test_two_zero_quotes_stop_an_otm_wing() -> None:
    expiration = date(2026, 7, 27)
    quotes = chain(expiration)
    changed = []
    for quote in quotes:
        if quote.right == "C" and quote.strike in {115, 120}:
            changed.append(
                OptionQuote(
                    quote.strike,
                    quote.right,
                    0.0,
                    0.0,
                    quote.timestamp,
                    quote.expiration,
                )
            )
        else:
            changed.append(quote)
    term = calculate_term_variance(
        changed,
        expiration=expiration,
        minutes_to_expiration=375,
        minutes_per_year=102060,
        rate_decimal=0.04,
        min_valid_strikes=8,
    )
    assert 115.0 in term.rejected_strikes
    assert 120.0 in term.rejected_strikes
    assert 125.0 not in term.included_strikes


def test_vix1d_and_vvix_are_positive() -> None:
    today = date(2026, 7, 27)
    tomorrow = date(2026, 7, 28)
    vix1d, details, persisted = calculate_vix1d(
        chain(today),
        chain(tomorrow),
        now=NOW,
        near_expiration=today,
        next_expiration=tomorrow,
        rate_decimal=0.0433,
    )
    assert vix1d > 0
    assert persisted["variance"] > 0
    assert details["near_variance_frozen"] is False

    near = date(2026, 8, 17)
    far = date(2026, 9, 7)
    vvix, vvix_details = calculate_vvix(
        chain(near, center=20),
        chain(far, center=20),
        now=NOW,
        near_expiration=near,
        next_expiration=far,
        rate_decimal=0.0433,
    )
    assert vvix > 0
    assert vvix_details["target_minutes"] == 43200


def test_expiration_selection() -> None:
    today = date(2026, 7, 27)
    assert choose_vix1d_expirations([today, today + timedelta(days=1)], NOW) == (
        today,
        today + timedelta(days=1),
    )
    near, far = choose_vvix_expirations(
        [today + timedelta(days=20), today + timedelta(days=40)], NOW
    )
    assert near < far


def test_options_client_never_uses_index_endpoint() -> None:
    today = NOW.date()
    tomorrow = today + timedelta(days=1)
    vix_near = today + timedelta(days=20)
    vix_far = today + timedelta(days=40)
    paths: list[str] = []

    def quote_payload(expiration: date, center: float) -> list[dict]:
        return [
            {
                "expiration": expiration.strftime("%Y%m%d"),
                "strike": quote.strike,
                "right": quote.right,
                "bid": quote.bid,
                "ask": quote.ask,
                "timestamp": NOW.isoformat(),
            }
            for quote in chain(expiration, center=center)
        ]

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        assert "/index/" not in request.url.path
        path = request.url.path
        symbol = request.url.params.get("symbol")
        if path.endswith("/option/list/expirations"):
            exps = [today, tomorrow] if symbol == "SPXW" else [today, vix_near, vix_far]
            return httpx.Response(200, json=[{"expiration": item.strftime("%Y%m%d")} for item in exps])
        if path.endswith("/calendar/year_holidays"):
            return httpx.Response(200, json=[])
        if path.endswith("/interest_rate/history/eod"):
            return httpx.Response(200, json=[{"date": today.isoformat(), "rate": 4.33}])
        if path.endswith("/option/snapshot/greeks/first_order"):
            value = 6000.0 if symbol == "SPXW" else 18.5
            return httpx.Response(
                200,
                json=[
                    {
                        "underlying_price": value + offset,
                        "underlying_timestamp": NOW.isoformat(),
                    }
                    for offset in (-0.001, 0.0, 0.001, 0.0)
                ],
            )
        if path.endswith("/option/snapshot/quote"):
            expiration = datetime.strptime(
                request.url.params["expiration"], "%Y%m%d"
            ).date()
            center = 100.0 if symbol == "SPXW" else 20.0
            return httpx.Response(200, json=quote_payload(expiration, center))
        raise AssertionError(path)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = ThetaOptionsVolatilityClient(
        "http://theta.test/v3",
        client=http_client,
        max_age_seconds=60,
        max_underlying_dispersion_pct=0.1,
    )
    try:
        result, _, metadata = client.fetch_all(now=NOW, state={})
    finally:
        http_client.close()
    assert result["vix"]["status"] == "observed_from_option_feed"
    assert result["vix1d"]["status"] == "reconstructed"
    assert result["vvix"]["status"] == "reconstructed"
    assert metadata["direct_index_subscription"] is False
    assert paths and all("/index/" not in path for path in paths)
