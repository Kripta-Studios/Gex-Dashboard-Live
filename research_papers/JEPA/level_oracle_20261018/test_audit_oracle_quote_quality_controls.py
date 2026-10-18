from audit_oracle_quote_quality_controls import classify


def test_basic_quote_checks_do_not_imply_economic_quality_controls():
    cache = """
    quote_valid = np.isfinite(bid) & np.isfinite(ask) & (bid >= 0) & (ask > 0) & (bid <= ask)
    good_spot = (ages >= 0) & (ages <= 60000)
    arrays['underlying_age_ms'] = ages
    """
    engine = """
    return np.isfinite(bid) & np.isfinite(ask) & (bid >= 0) & (ask > 0) & (bid <= ask)
    """
    audit = """
    def raw_clock_and_fill_check():
        validate_raw_ledger_fills()
        mismatch = native != underlying
        expected = paired_clock_mismatch_rows
    """
    result = classify(cache, engine, audit)
    assert result["finite_nonnegative_noncrossed_bid_ask"]
    assert result["selected_raw_fill_equality"]
    assert result["paired_stored_clock_comparison"]
    assert result["underlying_spot_age_0_to_60_seconds"]
    assert not result["option_intrinsic_value_check"]
    assert not result["put_call_parity_check"]
    assert not result["option_quote_staleness_check"]


def test_hypothetical_economic_controls_are_classified_separately():
    source = """
    intrinsic = max(spot - strike, 0)
    parity_residual = call - put - (spot - strike)
    stale_quote = option_quote_age > max_quote_age
    bad_spread = spread_width > max_spread
    vertical_arbitrage = strike_monotonicity
    """
    result = classify(source, source, source)
    assert result["option_intrinsic_value_check"]
    assert result["put_call_parity_check"]
    assert result["option_quote_staleness_check"]
    assert result["spread_width_check"]
    assert result["cross_strike_or_calendar_arbitrage_check"]
