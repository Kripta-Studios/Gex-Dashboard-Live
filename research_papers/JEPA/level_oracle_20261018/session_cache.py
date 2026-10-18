"""Pure variable-session normalization; raw frames are never modified.

Full sessions delegate unchanged. For short sessions, records known after the
close are removed BEFORE identity validation and contract-axis construction.
Invalid clocks remain invalid; missing OI timestamps retain the existing
explicit 09:30 availability assumption. No post-close prices enter the cache.
"""

import numpy as np
import pandas as pd

try:
    from . import build_cache as frozen
    from .session_clock import FULL, SessionClock
except ImportError:
    import build_cache as frozen
    from session_clock import FULL, SessionClock


def normalize_day(greek, oi, ticker, date, clock: SessionClock = FULL):
    if clock.is_full:
        return frozen.normalize_day(greek, oi, ticker, date)
    close = pd.Timestamp(date).normalize() + pd.Timedelta(
        hours=9, minutes=30 + clock.close_i
    )
    effective = frozen.parse_time(
        greek["timestamp"] if "timestamp" in greek else greek["underlying_timestamp"]
    )
    greek_keep = effective.isna() | (effective <= close)
    if "timestamp" in oi:
        available = frozen.parse_time(oi["timestamp"])
        oi_keep = available.isna() | (available <= close)
    else:
        oi_keep = np.ones(len(oi), dtype=bool)
    arrays, metadata = frozen.normalize_day(
        greek.loc[greek_keep].copy(), oi.loc[oi_keep].copy(), ticker, date
    )
    minute_arrays = {
        "time_ns",
        "spot",
        "spot_valid",
        "bid",
        "ask",
        "delta",
        "iv",
        "vega",
        "theta",
        "row_flags",
        "underlying_age_ms",
    }
    arrays = {
        key: value[: clock.n_slots].copy() if key in minute_arrays else value
        for key, value in arrays.items()
    }
    metadata["version"] = "SESSION_CLOCK_CACHE_V1"
    metadata["session_clock"] = clock.as_dict()
    metadata["post_close_removed"] = {
        "greek": int((~greek_keep).sum()),
        "oi": int((~oi_keep).sum()),
    }
    metadata["counters"]["absent_cells"] = int(
        np.count_nonzero(arrays["row_flags"] == 0)
    )
    metadata["uncompressed_array_bytes"] = sum(
        value.nbytes for value in arrays.values()
    )
    metadata["array_schema"] = {
        key: {"shape": list(value.shape), "dtype": str(value.dtype)}
        for key, value in arrays.items()
    }
    return arrays, metadata
