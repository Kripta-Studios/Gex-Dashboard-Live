"""Independent streaming csv/Decimal reconstruction of the fixed IB pilot."""
import csv
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import io
from zoneinfo import ZoneInfo

NY = ZoneInfo('America/New_York')


def require(condition, message):
    if not condition:
        raise ValueError('IB_AUDIT: ' + message)


def clock(raw):
    instant = datetime.fromisoformat(raw)
    return instant.replace(tzinfo=NY) if instant.tzinfo is None else instant.astimezone(NY)


def formatted(value):
    return None if value is None else format(value.normalize(), 'f')


def reconstruct(payload, ticker):
    start = datetime(2022, 8, 1, 9, 30, tzinfo=NY)
    end = start + timedelta(hours=1)
    times, identities = {}, set()
    for row_id, row in enumerate(csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))):
        instant = clock(row['timestamp'])
        if not start <= instant < end:
            continue
        require(instant.microsecond == 0, 'subsecond quote')
        strike = Decimal(row['strike'])
        side = {'C': 'CALL', 'P': 'PUT'}.get(row['right'].upper(), row['right'].upper())
        require(row['symbol'] == ticker and clock(row['expiration']).date() == start.date()
                and strike.is_finite() and strike > 0 and side in ('CALL', 'PUT'), 'identity')
        identity = side, strike, instant
        require(identity not in identities, 'duplicate quote')
        identities.add(identity)
        source = clock(row['underlying_timestamp'])
        require(source <= instant, 'future underlying')
        price = Decimal(row['underlying_price'])
        price = price if price.is_finite() else None
        require(price is not None and price > 0 or ticker == 'SPXW' and instant == start, 'invalid price')
        if instant not in times:
            times[instant] = [price, source, 0, []]
        require(times[instant][:2] == [price, source], 'cross-contract disagreement')
        times[instant][2] += 1
        if instant.second == 59:
            times[instant][3].append(row_id)
    require(set(times) == {start + timedelta(seconds=i) for i in range(3600)}, 'missing seconds')
    bars = []
    for n in range(60):
        beginning = start + timedelta(minutes=n)
        seconds = [beginning + timedelta(seconds=s) for s in range(60)]
        values = [times[t][0] for t in seconds]
        finite = [v for v in values if v is not None]
        require(finite, 'no finite prices')
        before = dict(open=values[0], high=max(finite), low=min(finite) if len(finite) == 60 else None, close=values[-1])
        after = dict(before)
        fields = [k for k in ('open', 'high', 'low', 'close') if before[k] is None or before[k] <= 0]
        repair = None
        if fields:
            require(ticker == 'SPXW' and n == 0 and before['close'] is not None and before['close'] > 0, 'forbidden repair')
            for field in fields:
                after[field] = before['close']
            last = seconds[-1]
            repair = dict(kind='SPXW_INITIAL_ZERO_BAR', fields=fields, source_rows=times[last][3],
                          quote_timestamp=last.isoformat(), underlying_timestamp=times[last][1].isoformat())
        bars.append(dict(timestamp=beginning.isoformat(), available_at=(beginning+timedelta(minutes=1)).isoformat(),
                         original_ohlc={k: formatted(v) for k, v in before.items()},
                         ohlc={k: formatted(v) for k, v in after.items()},
                         tick_count=sum(times[t][2] for t in seconds), repair=repair))
    upper, lower = max(Decimal(b['ohlc']['high']) for b in bars), min(Decimal(b['ohlc']['low']) for b in bars)
    require(upper > lower > 0, 'IB range')
    width = upper-lower
    levels = dict(ibh=formatted(upper), ibl=formatted(lower))
    for name, ratio in (('1272', Decimal('1.272')), ('1618', Decimal('1.618')), ('2000', Decimal('2'))):
        levels['upper_'+name] = formatted(lower + width*ratio)
        levels['lower_'+name] = formatted(upper - width*ratio)
    return dict(ticker=ticker, trade_date='2022-08-01', source_sha256=hashlib.sha256(payload).hexdigest(),
                bars=bars, ib=levels, available_at=end.isoformat(), original_vintage_verified=False)


def verify_record(payload, ticker, record):
    require(reconstruct(payload, ticker) == record, 'bar/repair/IB level mismatch')
