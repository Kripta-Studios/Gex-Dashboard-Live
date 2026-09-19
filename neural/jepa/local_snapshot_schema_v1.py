"""Immutable formats for the local-only source pilot; no shared calculations."""

DAY = '2023-01-03'
TICKERS = ('SPXW', 'SPY', 'QQQ')
GREEK_COLUMNS = (
    'symbol', 'expiration', 'trade_date', 'right', 'strike', 'interval_used',
    'timestamp', 'underlying_timestamp', 'underlying_price',
)
OI_COLUMNS = (
    'symbol', 'expiration', 'trade_date', 'right', 'strike', 'interval_used',
    'timestamp', 'open_interest',
)
AVAILABILITY_BASIS = 'ASSUMED_DELAY_NOT_OBSERVED_RECEIPT'

# These field names are a format, not an implementation of audited semantics.
SAMPLE_FIELDS = (
    'quote_timestamp', 'research_available_at', 'mask', 'reason', 'price',
    'underlying_timestamp', 'underlying_age_ms', 'source_rows',
)
OI_FIELDS = (
    'right', 'strike', 'open_interest', 'timestamp', 'zero', 'after_open',
    'classification',
)
