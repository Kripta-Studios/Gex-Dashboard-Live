"""Build the outcome-free H-TPOVALUE1 developing-value feature view.

The builder reads only the frozen Pairwise E0 feature projection and exact
one-minute underlying bars.  It never requests an option outcome column.  All
profiles use completed bars from 09:30 through ``t-1`` and the exact semantics
frozen in ``H_TPOVALUE1_EXECUTABLE_PREDECLARATION.md``.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from neural.jepa.build_cross_market_transmission_view_v1 import load_master_e0


ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet"
UNDERLYING_ROOT = Path(r"D:/ThetaData/data_underlying_derived")
OUTPUT_ROOT = ROOT / "tmp/existing_data_edge_sprint_v1/tpo_value_migration_v1"
DEFAULT_VIEW = OUTPUT_ROOT / "modeling_view.parquet"
DEFAULT_INVENTORY = OUTPUT_ROOT / "source_inventory.csv"
DEFAULT_DISTINCTNESS = OUTPUT_ROOT / "distinctness.csv"
DEFAULT_MANIFEST = OUTPUT_ROOT / "manifest.json"
DEFAULT_CHECKPOINT_ROOT = OUTPUT_ROOT / "session_checkpoints"
PROTOCOL_PATH = ROOT / "research_papers/JEPA/H_TPOVALUE1_EXECUTABLE_PREDECLARATION.md"

EXPERIMENT = "H_TPOVALUE1_EXECUTABLE_V1"
MASTER_SHA256 = "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408"
MASTER_ROWS = 97_625
ELIGIBLE_ROWS_V1R1 = 96_553
EXPECTED_SOURCE_SESSIONS = 2_777
KEY = ["ticker", "trade_date", "timestamp", "minute"]
EARLY_CLOSE_DATES = (
    "20221125",
    "20230703",
    "20231124",
    "20240703",
    "20241129",
    "20241224",
    "20250703",
    "20251128",
    "20251224",
)
PAIRWISE_E0_FEATURES = (
    "minute",
    "ib_range_bps",
    "dist_ib_high_bps",
    "dist_ib_low_bps",
    "nearest_level_abs_bps",
    "ret_1m_bps",
    "ret_5m_bps",
    "ret_15m_bps",
    "ret_30m_bps",
    "iv_diff",
    "spread_pct_diff",
    "volume_diff",
    "oi_diff",
    "abs_delta_diff",
    "vega_diff",
    "iv_diff_chg_5m",
    "iv_diff_chg_15m",
    "iv_diff_chg_25m",
    "spread_pct_diff_chg_5m",
    "spread_pct_diff_chg_15m",
    "spread_pct_diff_chg_25m",
    "volume_diff_chg_5m",
    "volume_diff_chg_15m",
    "volume_diff_chg_25m",
    "abs_delta_diff_chg_5m",
    "abs_delta_diff_chg_15m",
    "abs_delta_diff_chg_25m",
    "vega_diff_chg_5m",
    "vega_diff_chg_15m",
    "vega_diff_chg_25m",
)
TPO_FEATURES = (
    "tpo_poc_dist_bps",
    "tpo_vah_dist_bps",
    "tpo_val_dist_bps",
    "tpo_value_width_ib",
    "tpo_value_location",
    "tpo_poc_migration_5m_ib",
    "tpo_poc_migration_15m_ib",
    "tpo_poc_migration_30m_ib",
    "tpo_vah_migration_5m_ib",
    "tpo_vah_migration_15m_ib",
    "tpo_vah_migration_30m_ib",
    "tpo_val_migration_5m_ib",
    "tpo_val_migration_15m_ib",
    "tpo_val_migration_30m_ib",
    "tpo_value_overlap_5m",
    "tpo_value_overlap_15m",
    "tpo_value_overlap_30m",
    "tpo_entropy",
    "tpo_poc_concentration",
    "tpo_single_print_fraction",
    "tpo_upper_tail_fraction",
    "tpo_lower_tail_fraction",
    "tpo_profile_skew_ib",
    "tpo_developing_range_ib",
    "tpo_last3_inside_value_fraction",
    "tpo_last3_above_value_fraction",
    "tpo_last3_below_value_fraction",
    "tpo_session_inside_value_fraction",
    "tpo_poc_cross_rate",
    "tpo_vah_cross_rate",
    "tpo_val_cross_rate",
    "tpo_ib_position",
    "tpo_dist_ib_high_bps",
    "tpo_dist_ib_low_bps",
    "tpo_directional_efficiency_15m",
    "tpo_directional_efficiency_30m",
)
EXPECTED_X0_SHA256 = "b68b6c2e17b333597281a7d7fa27237b1f1e2640deb8952867d25eced26cbe38"
EXPECTED_TPO_SHA256 = "73903b48836f7d5a3b1d5943df46aa010403cd6bef9fe1a0f5ec90952ae7c9f5"
EXPECTED_X1_SHA256 = "0d8540768d311fd18d2b93bcd9beb99d7c2d49c2cb8ca0451b1ef1815a467026"
VALUE_AREA_FRACTION = 0.70
IB_BINS = 20
MODAL_FREQUENCY_MAX = 0.995
EXPECTED_DISTINCTNESS_CELLS = 3 * 4 * len(TPO_FEATURES)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_ordered(values: Iterable[str]) -> str:
    payload = json.dumps(list(values), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


if hash_ordered(PAIRWISE_E0_FEATURES) != EXPECTED_X0_SHA256:
    raise AssertionError("Pairwise E0 allowlist hash changed")
if hash_ordered(TPO_FEATURES) != EXPECTED_TPO_SHA256:
    raise AssertionError("TPO ordered allowlist hash changed")
if hash_ordered([*PAIRWISE_E0_FEATURES, *TPO_FEATURES]) != EXPECTED_X1_SHA256:
    raise AssertionError("TPO X1 ordered allowlist hash changed")


def _day(values: pd.Series) -> pd.Series:
    return values.astype(str).str.replace("-", "", regex=False).str[:8]


def _underlying_path(root: Path, ticker: str, trade_date: str) -> Path:
    return root / ticker / trade_date[:4] / trade_date[4:6] / f"{ticker}_{trade_date}.parquet"


def _assert_output_path(path: Path) -> None:
    resolved = path.resolve()
    allowed = OUTPUT_ROOT.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise AssertionError(f"output must remain under {OUTPUT_ROOT}")


def _event_key_sha256(events: pd.DataFrame) -> str:
    normalized = events[KEY].copy()
    normalized["ticker"] = normalized["ticker"].astype(str)
    normalized["trade_date"] = normalized["trade_date"].astype(str)
    normalized["timestamp"] = pd.to_datetime(normalized["timestamp"]).map(
        lambda value: value.isoformat()
    )
    normalized["minute"] = pd.to_numeric(normalized["minute"], errors="raise").astype(int)
    records = normalized.sort_values(KEY, kind="stable").to_dict(orient="records")
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _checkpoint_paths(root: Path, ticker: str, trade_date: str) -> tuple[Path, Path]:
    directory = root / ticker / trade_date[:4]
    stem = f"{ticker}_{trade_date}"
    return directory / f"{stem}.parquet", directory / f"{stem}.json"


def _normalized_checkpoint_keys(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame[KEY].copy()
    output["ticker"] = output["ticker"].astype(str)
    output["trade_date"] = output["trade_date"].astype(str)
    output["timestamp"] = pd.to_datetime(output["timestamp"])
    output["minute"] = pd.to_numeric(output["minute"], errors="raise").astype(int)
    return output.sort_values(KEY, kind="stable").reset_index(drop=True)


def _load_valid_checkpoint(
    *,
    parquet_path: Path,
    manifest_path: Path,
    events: pd.DataFrame,
    source_path: Path,
    source_sha256: str,
    builder_sha256: str,
    protocol_sha256: str,
) -> tuple[pd.DataFrame, dict[str, Any]] | None:
    if not parquet_path.exists() or not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = {
            "schema": "h_tpovalue1_session_checkpoint_v1",
            "status": "PASS_SESSION_FEATURES",
            "source_path": str(source_path),
            "source_sha256": source_sha256,
            "event_keys_sha256": _event_key_sha256(events),
            "builder_sha256": builder_sha256,
            "protocol_sha256": protocol_sha256,
            "tpo_features_sha256": EXPECTED_TPO_SHA256,
            "rows": len(events),
            "outcomes_read": False,
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            return None
        if manifest.get("features_sha256") != sha256_file(parquet_path):
            return None
        frame = pd.read_parquet(parquet_path)
        expected_columns = [*KEY, *TPO_FEATURES]
        if list(frame.columns) != expected_columns or len(frame) != len(events):
            return None
        if frame.duplicated(KEY).any():
            return None
        if not _normalized_checkpoint_keys(frame).equals(_normalized_checkpoint_keys(events)):
            return None
        if not np.isfinite(frame[list(TPO_FEATURES)].to_numpy(dtype=float)).all():
            return None
        return frame, manifest
    except (AssertionError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _write_session_checkpoint(
    *,
    frame: pd.DataFrame,
    parquet_path: Path,
    manifest_path: Path,
    source_path: Path,
    source_sha256: str,
    source_bytes: int,
    source_rows: int,
    consumed_rows: int,
    first_consumed_timestamp: str,
    last_consumed_timestamp: str,
    event_keys_sha256: str,
    builder_sha256: str,
    protocol_sha256: str,
) -> dict[str, Any]:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_tmp = _temporary(parquet_path)
    manifest_tmp = _temporary(manifest_path)
    for path in (parquet_tmp, manifest_tmp):
        if path.exists():
            path.unlink()
    frame.to_parquet(parquet_tmp, index=False, compression="zstd")
    manifest = {
        "schema": "h_tpovalue1_session_checkpoint_v1",
        "status": "PASS_SESSION_FEATURES",
        "ticker": str(frame["ticker"].iloc[0]),
        "trade_date": str(frame["trade_date"].iloc[0]),
        "rows": len(frame),
        "columns": list(frame.columns),
        "event_keys_sha256": event_keys_sha256,
        "source_path": str(source_path),
        "source_sha256": source_sha256,
        "source_bytes": source_bytes,
        "source_rows": source_rows,
        "consumed_rows": consumed_rows,
        "first_consumed_timestamp": first_consumed_timestamp,
        "last_consumed_timestamp": last_consumed_timestamp,
        "builder_sha256": builder_sha256,
        "protocol_sha256": protocol_sha256,
        "tpo_features_sha256": EXPECTED_TPO_SHA256,
        "features_sha256": sha256_file(parquet_tmp),
        "outcomes_read": False,
    }
    manifest_tmp.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    parquet_tmp.replace(parquet_path)
    manifest_tmp.replace(manifest_path)
    return manifest


def load_exact_underlying_day(
    path: Path, *, ticker: str, trade_date: str
) -> tuple[pd.DataFrame, int]:
    required = ["symbol", "date", "timestamp", "open", "high", "low", "close", "tick_count"]
    if not path.exists():
        raise FileNotFoundError(path)
    parquet = pq.ParquetFile(path)
    if not set(required).issubset(parquet.schema_arrow.names):
        raise KeyError(f"{path} lacks required underlying fields")
    frame = pd.read_parquet(path, columns=required)
    timestamp = pd.to_datetime(frame["timestamp"], errors="coerce")
    if timestamp.isna().any() or timestamp.dt.second.ne(0).any() or timestamp.dt.microsecond.ne(0).any():
        raise AssertionError(f"non-exact underlying timestamp in {path}")
    if timestamp.duplicated().any():
        raise AssertionError(f"duplicate underlying timestamp in {path}")
    if not frame["symbol"].astype(str).eq(ticker).all():
        raise AssertionError(f"symbol metadata mismatch in {path}")
    if not _day(frame["date"]).eq(trade_date).all():
        raise AssertionError(f"date metadata mismatch in {path}")
    numeric = frame[["open", "high", "low", "close", "tick_count"]].apply(
        pd.to_numeric, errors="coerce"
    )
    numeric.index = pd.DatetimeIndex(timestamp)
    return numeric.sort_index(), int(parquet.metadata.num_rows)


def exact_consumed_session(
    day: pd.DataFrame,
    *,
    trade_date: str,
    maximum_event_timestamp: pd.Timestamp,
) -> pd.DataFrame:
    start = pd.Timestamp(f"{trade_date} 09:30:00")
    maximum = pd.Timestamp(maximum_event_timestamp)
    expected = pd.date_range(start, maximum - pd.Timedelta(minutes=1), freq="min")
    missing = expected.difference(day.index)
    if len(missing):
        raise AssertionError(f"missing exact completed bars: {missing[:3].tolist()}")
    consumed = day.loc[expected].copy()
    if not consumed.index.equals(expected) or not (consumed.index < maximum).all():
        raise AssertionError("underlying session was not selected by exact completed timestamps")
    ohlc = consumed[["open", "high", "low", "close"]]
    values = ohlc.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0.0).any():
        raise AssertionError("invalid OHLC in consumed TPO session")
    if (ohlc["high"] < ohlc[["open", "close", "low"]].max(axis=1)).any():
        raise AssertionError("high envelope failure in consumed TPO session")
    if (ohlc["low"] > ohlc[["open", "close", "high"]].min(axis=1)).any():
        raise AssertionError("low envelope failure in consumed TPO session")
    ticks = consumed["tick_count"].to_numpy(dtype=float)
    if not np.isfinite(ticks).all() or (ticks < 0.0).any():
        raise AssertionError("invalid tick_count in consumed TPO session")
    return consumed


def _bin_index(price: float, *, ib_low: float, bin_width: float) -> int:
    return int(math.floor((float(price) - ib_low) / bin_width))


@dataclass(frozen=True)
class TPOProfile:
    poc: float
    val: float
    vah: float
    reference: float
    entropy: float
    poc_concentration: float
    single_print_fraction: float
    upper_tail_fraction: float
    lower_tail_fraction: float
    weighted_mean: float
    developing_high: float
    developing_low: float
    closes: np.ndarray


class TPOAccumulator:
    def __init__(self, *, ib_low: float, ib_high: float) -> None:
        self.ib_low = float(ib_low)
        self.ib_high = float(ib_high)
        self.ib_range = self.ib_high - self.ib_low
        if not np.isfinite([self.ib_low, self.ib_high]).all() or self.ib_range <= 0.0:
            raise AssertionError("IB range must be finite and positive")
        self.bin_width = self.ib_range / IB_BINS
        self.counts: dict[int, int] = {}
        self.closes: list[float] = []
        self.highs: list[float] = []
        self.lows: list[float] = []

    def add_bar(self, *, low: float, high: float, close: float) -> None:
        low_index = _bin_index(low, ib_low=self.ib_low, bin_width=self.bin_width)
        high_index = _bin_index(high, ib_low=self.ib_low, bin_width=self.bin_width)
        if high_index < low_index:
            raise AssertionError("bar bin envelope inverted")
        for index in range(low_index, high_index + 1):
            self.counts[index] = self.counts.get(index, 0) + 1
        self.closes.append(float(close))
        self.highs.append(float(high))
        self.lows.append(float(low))

    def snapshot(self) -> TPOProfile:
        if not self.counts or not self.closes:
            raise AssertionError("TPO profile is empty")
        minimum = min(self.counts)
        maximum = max(self.counts)
        indices = np.arange(minimum, maximum + 1, dtype=int)
        counts = np.asarray([self.counts.get(int(index), 0) for index in indices], dtype=float)
        total = float(counts.sum())
        if total <= 0.0 or not np.isfinite(total):
            raise AssertionError("TPO total must be finite and positive")
        centers = self.ib_low + (indices.astype(float) + 0.5) * self.bin_width
        maximum_count = float(counts.max())
        candidates = np.flatnonzero(counts == maximum_count)
        midpoint = (self.ib_low + self.ib_high) / 2.0
        poc_position = min(candidates.tolist(), key=lambda pos: (abs(centers[pos] - midpoint), centers[pos]))
        low_position = high_position = int(poc_position)
        accumulated = float(counts[poc_position])
        target = VALUE_AREA_FRACTION * total
        while accumulated < target:
            lower = counts[low_position - 1] if low_position > 0 else -math.inf
            upper = counts[high_position + 1] if high_position + 1 < len(counts) else -math.inf
            if not np.isfinite([lower, upper]).any():
                raise AssertionError("value-area expansion exhausted lattice")
            if lower >= upper:
                low_position -= 1
                accumulated += float(counts[low_position])
            else:
                high_position += 1
                accumulated += float(counts[high_position])
        poc = float(centers[poc_position])
        val = float(self.ib_low + indices[low_position] * self.bin_width)
        vah = float(self.ib_low + (indices[high_position] + 1) * self.bin_width)
        positive = counts[counts > 0.0] / total
        entropy = (
            float(-np.sum(positive * np.log(positive)) / np.log(len(positive)))
            if len(positive) > 1
            else 0.0
        )
        return TPOProfile(
            poc=poc,
            val=val,
            vah=vah,
            reference=float(self.closes[-1]),
            entropy=entropy,
            poc_concentration=maximum_count / total,
            single_print_fraction=float(np.mean(counts == 1.0)),
            upper_tail_fraction=float(counts[high_position + 1 :].sum() / total),
            lower_tail_fraction=float(counts[:low_position].sum() / total),
            weighted_mean=float(np.sum(centers * counts) / total),
            developing_high=float(max(self.highs)),
            developing_low=float(min(self.lows)),
            closes=np.asarray(self.closes, dtype=float).copy(),
        )


def build_profile_cache(
    consumed: pd.DataFrame,
    cutoffs: Iterable[pd.Timestamp],
    *,
    ib_low: float,
    ib_high: float,
) -> dict[pd.Timestamp, TPOProfile]:
    ordered = sorted({pd.Timestamp(value) for value in cutoffs})
    if not ordered:
        raise AssertionError("profile cache requires cutoffs")
    accumulator = TPOAccumulator(ib_low=ib_low, ib_high=ib_high)
    rows = list(consumed[["low", "high", "close"]].itertuples())
    cursor = 0
    output: dict[pd.Timestamp, TPOProfile] = {}
    for cutoff in ordered:
        while cursor < len(rows) and pd.Timestamp(rows[cursor].Index) < cutoff:
            row = rows[cursor]
            accumulator.add_bar(low=float(row.low), high=float(row.high), close=float(row.close))
            cursor += 1
        if cursor == 0 or not pd.Timestamp(rows[cursor - 1].Index) < cutoff:
            raise AssertionError(f"no completed TPO bars before {cutoff}")
        output[cutoff] = accumulator.snapshot()
    return output


def _overlap(current: TPOProfile, lagged: TPOProfile) -> float:
    intersection = max(0.0, min(current.vah, lagged.vah) - max(current.val, lagged.val))
    union = max(current.vah, lagged.vah) - min(current.val, lagged.val)
    if union <= 0.0:
        raise AssertionError("value overlap union is not positive")
    return intersection / union


def _state_fraction(closes: np.ndarray, *, val: float, vah: float) -> tuple[float, float, float]:
    if len(closes) == 0:
        raise AssertionError("value-state fraction requires closes")
    inside = (closes >= val) & (closes <= vah)
    above = closes > vah
    below = closes < val
    if not np.all(inside | above | below):
        raise AssertionError("value states are not exhaustive")
    return float(inside.mean()), float(above.mean()), float(below.mean())


def _cross_rate(closes: np.ndarray, level: float) -> float:
    if len(closes) < 2:
        raise AssertionError("cross rate requires at least two closes")
    states = np.where(closes < level, -1, np.where(closes > level, 1, 0))
    return float(np.mean(states[1:] != states[:-1]))


def _directional_efficiency(closes: np.ndarray, horizon: int) -> float:
    if len(closes) < horizon + 1:
        raise AssertionError(f"directional efficiency {horizon}m lacks completed closes")
    window = closes[-(horizon + 1) :]
    denominator = float(np.abs(np.diff(window)).sum())
    return 0.0 if denominator == 0.0 else float(abs(window[-1] - window[0]) / denominator)


def tpo_features_for_event(
    profiles: dict[pd.Timestamp, TPOProfile],
    *,
    event_timestamp: pd.Timestamp,
    ib_low: float,
    ib_high: float,
) -> dict[str, float]:
    event = pd.Timestamp(event_timestamp)
    current = profiles[event]
    ib_range = float(ib_high - ib_low)
    if ib_range <= 0.0 or current.reference <= 0.0 or current.vah <= current.val:
        raise AssertionError("undefined TPO event denominator")
    lagged = {lag: profiles[event - pd.Timedelta(minutes=lag)] for lag in (5, 15, 30)}
    last3 = current.closes[-3:]
    if len(last3) != 3:
        raise AssertionError("last-three value state lacks completed closes")
    last_inside, last_above, last_below = _state_fraction(last3, val=current.val, vah=current.vah)
    session_inside, _, _ = _state_fraction(current.closes, val=current.val, vah=current.vah)
    output: dict[str, float] = {
        "tpo_poc_dist_bps": (current.reference - current.poc) / current.reference * 10_000.0,
        "tpo_vah_dist_bps": (current.reference - current.vah) / current.reference * 10_000.0,
        "tpo_val_dist_bps": (current.reference - current.val) / current.reference * 10_000.0,
        "tpo_value_width_ib": (current.vah - current.val) / ib_range,
        "tpo_value_location": (current.reference - current.val) / (current.vah - current.val),
    }
    for field in ("poc", "vah", "val"):
        for lag in (5, 15, 30):
            output[f"tpo_{field}_migration_{lag}m_ib"] = (
                getattr(current, field) - getattr(lagged[lag], field)
            ) / ib_range
    for lag in (5, 15, 30):
        output[f"tpo_value_overlap_{lag}m"] = _overlap(current, lagged[lag])
    output.update(
        {
            "tpo_entropy": current.entropy,
            "tpo_poc_concentration": current.poc_concentration,
            "tpo_single_print_fraction": current.single_print_fraction,
            "tpo_upper_tail_fraction": current.upper_tail_fraction,
            "tpo_lower_tail_fraction": current.lower_tail_fraction,
            "tpo_profile_skew_ib": (current.weighted_mean - current.poc) / ib_range,
            "tpo_developing_range_ib": (current.developing_high - current.developing_low) / ib_range,
            "tpo_last3_inside_value_fraction": last_inside,
            "tpo_last3_above_value_fraction": last_above,
            "tpo_last3_below_value_fraction": last_below,
            "tpo_session_inside_value_fraction": session_inside,
            "tpo_poc_cross_rate": _cross_rate(current.closes, current.poc),
            "tpo_vah_cross_rate": _cross_rate(current.closes, current.vah),
            "tpo_val_cross_rate": _cross_rate(current.closes, current.val),
            "tpo_ib_position": (current.reference - ib_low) / ib_range,
            "tpo_dist_ib_high_bps": (current.reference - ib_high) / current.reference * 10_000.0,
            "tpo_dist_ib_low_bps": (current.reference - ib_low) / current.reference * 10_000.0,
            "tpo_directional_efficiency_15m": _directional_efficiency(current.closes, 15),
            "tpo_directional_efficiency_30m": _directional_efficiency(current.closes, 30),
        }
    )
    if tuple(output) != TPO_FEATURES:
        raise AssertionError("TPO feature order differs from frozen allowlist")
    values = np.asarray(list(output.values()), dtype=float)
    if not np.isfinite(values).all():
        raise AssertionError("TPO event produced non-finite feature")
    return output


def _build_session(
    task: tuple[str, str, pd.DataFrame, str] | tuple[str, str, pd.DataFrame, str, str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ticker, trade_date, events, underlying_root_text = task[:4]
    checkpoint_root = Path(task[4]) if len(task) == 5 else None
    path = _underlying_path(Path(underlying_root_text), ticker, trade_date)
    try:
        if not path.exists():
            raise FileNotFoundError(path)
        source_sha256 = sha256_file(path)
        builder_sha256 = sha256_file(Path(__file__))
        protocol_sha256 = sha256_file(PROTOCOL_PATH)
        checkpoint_parquet: Path | None = None
        checkpoint_manifest: Path | None = None
        if checkpoint_root is not None:
            checkpoint_parquet, checkpoint_manifest = _checkpoint_paths(
                checkpoint_root, ticker, trade_date
            )
            valid = _load_valid_checkpoint(
                parquet_path=checkpoint_parquet,
                manifest_path=checkpoint_manifest,
                events=events,
                source_path=path,
                source_sha256=source_sha256,
                builder_sha256=builder_sha256,
                protocol_sha256=protocol_sha256,
            )
            if valid is not None:
                frame, checkpoint = valid
                inventory = {
                    "ticker": ticker,
                    "trade_date": trade_date,
                    "path": str(path),
                    "sha256": source_sha256,
                    "bytes": int(checkpoint["source_bytes"]),
                    "source_rows": int(checkpoint["source_rows"]),
                    "consumed_rows": int(checkpoint["consumed_rows"]),
                    "first_consumed_timestamp": checkpoint["first_consumed_timestamp"],
                    "last_consumed_timestamp": checkpoint["last_consumed_timestamp"],
                    "checkpoint_path": str(checkpoint_parquet),
                    "checkpoint_sha256": checkpoint["features_sha256"],
                    "checkpoint_manifest_path": str(checkpoint_manifest),
                    "checkpoint_manifest_sha256": sha256_file(checkpoint_manifest),
                    "checkpoint_reused": True,
                }
                return frame.to_dict(orient="records"), inventory
        day, source_rows = load_exact_underlying_day(path, ticker=ticker, trade_date=trade_date)
        maximum_event = pd.Timestamp(events["timestamp"].max())
        consumed = exact_consumed_session(
            day,
            trade_date=trade_date,
            maximum_event_timestamp=maximum_event,
        )
        ib_index = pd.date_range(pd.Timestamp(f"{trade_date} 09:30:00"), periods=60, freq="min")
        if len(ib_index.difference(consumed.index)):
            raise AssertionError("IB 09:30..10:29 is incomplete")
        ib = consumed.loc[ib_index]
        ib_high = float(ib["high"].max())
        ib_low = float(ib["low"].min())
        if not np.isfinite([ib_low, ib_high]).all() or ib_high <= ib_low:
            raise AssertionError("IB high/low is not finite and positive-range")
        event_times = [pd.Timestamp(value) for value in events["timestamp"]]
        cutoffs = {
            event - pd.Timedelta(minutes=lag)
            for event in event_times
            for lag in (0, 5, 15, 30)
        }
        profiles = build_profile_cache(consumed, cutoffs, ib_low=ib_low, ib_high=ib_high)
        rows: list[dict[str, Any]] = []
        for event in events.sort_values("timestamp", kind="stable").itertuples(index=False):
            timestamp = pd.Timestamp(event.timestamp)
            expected_minute = timestamp.hour * 60 + timestamp.minute
            if timestamp.strftime("%Y%m%d") != trade_date or int(event.minute) != expected_minute:
                raise AssertionError("event timestamp/date/minute identity mismatch")
            rows.append(
                {
                    "ticker": ticker,
                    "trade_date": trade_date,
                    "timestamp": timestamp,
                    "minute": int(event.minute),
                    **tpo_features_for_event(
                        profiles,
                        event_timestamp=timestamp,
                        ib_low=ib_low,
                        ib_high=ib_high,
                    ),
                }
            )
        frame = pd.DataFrame(rows)[[*KEY, *TPO_FEATURES]]
        checkpoint: dict[str, Any] | None = None
        if checkpoint_parquet is not None and checkpoint_manifest is not None:
            checkpoint = _write_session_checkpoint(
                frame=frame,
                parquet_path=checkpoint_parquet,
                manifest_path=checkpoint_manifest,
                source_path=path,
                source_sha256=source_sha256,
                source_bytes=path.stat().st_size,
                source_rows=source_rows,
                consumed_rows=len(consumed),
                first_consumed_timestamp=consumed.index.min().isoformat(),
                last_consumed_timestamp=consumed.index.max().isoformat(),
                event_keys_sha256=_event_key_sha256(events),
                builder_sha256=builder_sha256,
                protocol_sha256=protocol_sha256,
            )
        inventory = {
            "ticker": ticker,
            "trade_date": trade_date,
            "path": str(path),
            "sha256": source_sha256,
            "bytes": path.stat().st_size,
            "source_rows": source_rows,
            "consumed_rows": len(consumed),
            "first_consumed_timestamp": consumed.index.min().isoformat(),
            "last_consumed_timestamp": consumed.index.max().isoformat(),
            "checkpoint_path": str(checkpoint_parquet) if checkpoint_parquet else "",
            "checkpoint_sha256": checkpoint["features_sha256"] if checkpoint else "",
            "checkpoint_manifest_path": str(checkpoint_manifest) if checkpoint_manifest else "",
            "checkpoint_manifest_sha256": (
                sha256_file(checkpoint_manifest) if checkpoint_manifest else ""
            ),
            "checkpoint_reused": False,
        }
        return frame.to_dict(orient="records"), inventory
    except Exception as exc:
        raise AssertionError(f"TPO source gate failed for {ticker} {trade_date}: {exc}") from exc


def distinctness_audit(view: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    working = view.assign(year=view["trade_date"].str[:4])
    for (ticker, year), cell in working.groupby(["ticker", "year"], sort=True, observed=True):
        for feature in TPO_FEATURES:
            values = pd.to_numeric(cell[feature], errors="coerce")
            finite = bool(np.isfinite(values.to_numpy(dtype=float)).all())
            counts = values.value_counts(dropna=False)
            unique = int(len(counts))
            modal = float(counts.iloc[0] / len(values)) if len(values) else 1.0
            records.append(
                {
                    "ticker": ticker,
                    "year": year,
                    "feature": feature,
                    "rows": len(values),
                    "finite": finite,
                    "distinct_values": unique,
                    "modal_frequency": modal,
                    "minimum": float(values.min()) if finite else math.nan,
                    "maximum": float(values.max()) if finite else math.nan,
                    "pass": finite and unique >= 2 and modal < MODAL_FREQUENCY_MAX,
                }
            )
    audit = pd.DataFrame(records)
    if len(audit) != EXPECTED_DISTINCTNESS_CELLS:
        raise AssertionError(
            f"ticker-year distinctness census changed: {len(audit)} != {EXPECTED_DISTINCTNESS_CELLS}"
        )
    return audit


def _temporary(path: Path) -> Path:
    return path.with_name(path.name + ".tmp")


def build_view(
    *,
    master_path: Path = MASTER,
    underlying_root: Path = UNDERLYING_ROOT,
    output_path: Path = DEFAULT_VIEW,
    inventory_path: Path = DEFAULT_INVENTORY,
    distinctness_path: Path = DEFAULT_DISTINCTNESS,
    manifest_path: Path = DEFAULT_MANIFEST,
    checkpoint_root: Path = DEFAULT_CHECKPOINT_ROOT,
    workers: int = 8,
    enforce_authoritative: bool = True,
) -> dict[str, Any]:
    paths = (output_path, inventory_path, distinctness_path, manifest_path)
    for path in (*paths, checkpoint_root):
        _assert_output_path(path)
    if manifest_path.exists():
        raise FileExistsError(f"immutable completed TPO output already exists: {manifest_path}")
    for path in paths:
        temporary = _temporary(path)
        if temporary.exists():
            temporary.unlink()
    if workers < 1 or workers > 16:
        raise ValueError("workers must be between 1 and 16")
    e0, e0_features = load_master_e0(master_path, enforce_authoritative=enforce_authoritative)
    if tuple(e0_features) != PAIRWISE_E0_FEATURES:
        raise AssertionError("active Pairwise E0 differs from H-TPO predeclaration")
    if enforce_authoritative and len(e0) != ELIGIBLE_ROWS_V1R1:
        raise AssertionError("eligible master census changed")
    tasks = [
        (
            str(ticker),
            str(trade_date),
            events[KEY].copy(),
            str(underlying_root),
            str(checkpoint_root),
        )
        for (ticker, trade_date), events in e0.groupby(["ticker", "trade_date"], sort=True, observed=True)
    ]
    if enforce_authoritative and len(tasks) != EXPECTED_SOURCE_SESSIONS:
        raise AssertionError(f"source session census changed: {len(tasks)}")
    feature_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    reused_checkpoints = 0
    if workers == 1:
        results = map(_build_session, tasks)
    else:
        executor = ProcessPoolExecutor(max_workers=workers)
        results = executor.map(_build_session, tasks, chunksize=4)
    try:
        for index, (rows, inventory) in enumerate(results, start=1):
            feature_rows.extend(rows)
            source_rows.append(inventory)
            reused_checkpoints += int(bool(inventory["checkpoint_reused"]))
            if index % 100 == 0 or index == len(tasks):
                print(
                    f"TPO sessions {index}/{len(tasks)} rows={len(feature_rows)} "
                    f"reused={reused_checkpoints} new={index - reused_checkpoints}",
                    flush=True,
                )
    finally:
        if workers != 1:
            executor.shutdown(wait=True, cancel_futures=True)
    tpo = pd.DataFrame(feature_rows)
    if len(tpo) != len(e0) or tpo.duplicated(KEY).any():
        raise AssertionError("TPO features did not preserve exact master keys")
    view = e0.merge(tpo, on=KEY, how="left", validate="one_to_one")
    ordered = list(dict.fromkeys([*KEY, *PAIRWISE_E0_FEATURES, *TPO_FEATURES]))
    view = view[ordered].sort_values(KEY, kind="stable").reset_index(drop=True)
    tpo_values = view[list(TPO_FEATURES)].to_numpy(dtype=float)
    if not np.isfinite(tpo_values).all():
        raise AssertionError("TPO block is not 100% finite")
    audit = distinctness_audit(view)
    failures = audit.loc[~audit["pass"]]
    if not failures.empty:
        sample = failures[["ticker", "year", "feature", "distinct_values", "modal_frequency"]].head(20)
        raise AssertionError(f"TPO distinctness gate failed:\n{sample.to_string(index=False)}")
    inventory = pd.DataFrame(source_rows).sort_values(["ticker", "trade_date"], kind="stable")
    if len(inventory) != len(tasks) or inventory.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("TPO source inventory does not match ticker-session universe")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_tmp, inventory_tmp, distinctness_tmp, manifest_tmp = map(_temporary, paths)
    view.to_parquet(output_tmp, index=False, compression="zstd")
    inventory.to_csv(inventory_tmp, index=False, lineterminator="\n")
    audit.to_csv(distinctness_tmp, index=False, lineterminator="\n")
    x0 = list(PAIRWISE_E0_FEATURES)
    x1 = [*x0, *TPO_FEATURES]
    manifest: dict[str, Any] = {
        "schema": "tpo_value_migration_view_v1",
        "experiment": EXPERIMENT,
        "status": "PASS_EXACT_TPO_VALUE_VIEW",
        "outcomes_in_view": False,
        "outcomes_read": False,
        "new_data_source": False,
        "outer_2024_2025_evaluated": False,
        "holdout_2026_opened": False,
        "june_2026_sealed": True,
        "production_modified": False,
        "master_path": str(master_path),
        "master_sha256": sha256_file(master_path),
        "master_rows_preserved": len(view),
        "master_physical_rows": MASTER_ROWS,
        "excluded_early_close_dates": list(EARLY_CLOSE_DATES),
        "excluded_early_close_rows": 1_072,
        "exclusion_contract": "calendar-only full-session exclusion; no outcome or exit inspected",
        "date_min": str(view["trade_date"].min()),
        "date_max": str(view["trade_date"].max()),
        "join_contract": "exact timestamps; completed target bars 09:30..t-1",
        "forbidden_joins_used": [],
        "profile_period": "one TPO per completed one-minute bar per intersected floor bin",
        "profile_uses_volume": False,
        "profile_uses_tick_count_as_alpha": False,
        "live_parity": "BLOCKED_IMPLEMENTATION",
        "live_requirement": "exact completed-bar barrier and abstention; no as-of/floor/nearest fallback",
        "X0": {
            "features": x0,
            "feature_count": len(x0),
            "ordered_json_sha256": hash_ordered(x0),
        },
        "X1": {
            "features": x1,
            "feature_count": len(x1),
            "ordered_json_sha256": hash_ordered(x1),
        },
        "TPO": {
            "features": list(TPO_FEATURES),
            "feature_count": len(TPO_FEATURES),
            "ordered_json_sha256": hash_ordered(TPO_FEATURES),
            "value_area_fraction": VALUE_AREA_FRACTION,
            "ib_bins": IB_BINS,
        },
        "data_gate": {
            "all_tpo_features_finite": True,
            "ticker_year_cells": len(audit),
            "minimum_distinct_values": int(audit["distinct_values"].min()),
            "maximum_modal_frequency": float(audit["modal_frequency"].max()),
            "minimum_distinct_required": 2,
            "modal_frequency_strict_maximum": MODAL_FREQUENCY_MAX,
            "pass": True,
        },
        "source_inventory_path": str(inventory_path),
        "source_inventory_sha256": sha256_file(inventory_tmp),
        "source_sessions": len(inventory),
        "checkpoint_contract": {
            "schema": "h_tpovalue1_session_checkpoint_v1",
            "root": str(checkpoint_root),
            "atomic_manifest_last": True,
            "validated_hashes": [
                "source",
                "event_keys",
                "builder",
                "protocol",
                "feature_allowlist",
                "feature_parquet",
            ],
            "sessions_total": len(inventory),
            "sessions_reused": reused_checkpoints,
            "sessions_built": len(inventory) - reused_checkpoints,
        },
        "distinctness_path": str(distinctness_path),
        "distinctness_sha256": sha256_file(distinctness_tmp),
        "view_path": str(output_path),
        "view_sha256": sha256_file(output_tmp),
        "view_bytes": output_tmp.stat().st_size,
    }
    manifest_tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    output_tmp.replace(output_path)
    inventory_tmp.replace(inventory_path)
    distinctness_tmp.replace(distinctness_path)
    manifest_tmp.replace(manifest_path)
    manifest["manifest_path"] = str(manifest_path)
    manifest["manifest_sha256"] = sha256_file(manifest_path)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master", default=str(MASTER))
    parser.add_argument("--underlying-root", default=str(UNDERLYING_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_VIEW))
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--distinctness", default=str(DEFAULT_DISTINCTNESS))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--checkpoint-root", default=str(DEFAULT_CHECKPOINT_ROOT))
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    manifest = build_view(
        master_path=Path(args.master),
        underlying_root=Path(args.underlying_root),
        output_path=Path(args.output),
        inventory_path=Path(args.inventory),
        distinctness_path=Path(args.distinctness),
        manifest_path=Path(args.manifest),
        checkpoint_root=Path(args.checkpoint_root),
        workers=args.workers,
    )
    print(
        json.dumps(
            {key: manifest[key] for key in ("status", "master_rows_preserved", "source_sessions", "view_sha256", "manifest_sha256")},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
