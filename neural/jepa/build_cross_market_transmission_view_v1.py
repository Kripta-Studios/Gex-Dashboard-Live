"""Build the outcome-free CROSS_MARKET_TRANSMISSION_V1 feature view.

The builder consumes only master keys and the frozen Pairwise-V1 E0 source
columns.  Cross-market features come from already-present one-minute underlying
files and use exactly the 30 *completed* bars ``[t-30m, t)``.  Every timestamp
is matched by equality; as-of, nearest and floor-time joins are forbidden.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from neural.jepa.walkforward_pairwise_opportunity_side import (
    COMMON_FEATURES,
    DIFF_METRICS,
    build_diff_features,
)


ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet"
UNDERLYING_ROOT = Path(r"D:/ThetaData/data_underlying_derived")
OUTPUT_ROOT = ROOT / "tmp/existing_data_edge_sprint_v1/cross_market_transmission_v1"
DEFAULT_VIEW = OUTPUT_ROOT / "modeling_view.parquet"
DEFAULT_INVENTORY = OUTPUT_ROOT / "source_inventory.csv"
DEFAULT_MANIFEST = OUTPUT_ROOT / "manifest.json"

MASTER_SHA256 = "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408"
MASTER_ROWS = 97_625
KEY = ["ticker", "trade_date", "timestamp", "minute"]
MARKETS = ("SPXW", "SPY", "QQQ", "TLT")
FIXED_PAIRS = (("spxw_spy", "SPXW", "SPY"), ("qqq_spy", "QQQ", "SPY"), ("qqq_spxw", "QQQ", "SPXW"))
PAIR_FIELDS = (
    "beta_30",
    "residual_1m",
    "residual_5m",
    "residual_15m",
    "relative_rv_30",
    "lead_score_30",
    "basis_z_30",
)
CROSS_FEATURES = tuple(
    f"xmt__{prefix}__{field}"
    for prefix in ("spxw_spy", "qqq_spy", "qqq_spxw", "target_tlt")
    for field in PAIR_FIELDS
)
EPSILON = 1e-12
FORBIDDEN_MASTER_TOKENS = ("future_", "_opt_", "target", "label", "pnl", "outcome")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_ordered(values: list[str] | tuple[str, ...]) -> str:
    payload = json.dumps(list(values), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _assert_output_path(path: Path) -> None:
    resolved = path.resolve()
    allowed = OUTPUT_ROOT.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise AssertionError(f"output must remain under {OUTPUT_ROOT}")


def _day(value: pd.Series) -> pd.Series:
    return value.astype(str).str.replace("-", "", regex=False).str[:8]


def _master_read_columns(schema_names: list[str]) -> list[str]:
    raw = [*KEY, *COMMON_FEATURES]
    for bucket in (25, 35):
        raw.extend(
            f"{right}_d{bucket:02d}_{metric}"
            for right in ("call", "put")
            for metric in DIFF_METRICS
        )
    columns = list(dict.fromkeys(column for column in raw if column in schema_names))
    forbidden = [column for column in columns if any(token in column.lower() for token in FORBIDDEN_MASTER_TOKENS)]
    if forbidden:
        raise AssertionError(f"outcome-like master columns requested: {forbidden}")
    required = {*KEY, *COMMON_FEATURES}
    if not required.issubset(columns):
        raise KeyError(f"master is missing E0/key columns: {sorted(required - set(columns))}")
    return columns


def load_master_e0(master_path: Path, *, enforce_authoritative: bool = True) -> tuple[pd.DataFrame, list[str]]:
    if enforce_authoritative and sha256_file(master_path) != MASTER_SHA256:
        raise AssertionError("authoritative executable master hash changed")
    schema = pq.ParquetFile(master_path).schema_arrow.names
    columns = _master_read_columns(schema)
    master = pd.read_parquet(master_path, columns=columns)
    master["ticker"] = master["ticker"].astype(str).str.upper()
    master["trade_date"] = _day(master["trade_date"])
    parsed = pd.to_datetime(master["timestamp"], errors="coerce")
    if parsed.isna().any() or parsed.dt.second.ne(0).any() or parsed.dt.microsecond.ne(0).any():
        raise AssertionError("master timestamps are not exact minute timestamps")
    master["timestamp"] = parsed
    if master.duplicated(["ticker", "trade_date", "minute"]).any():
        raise AssertionError("master keys are not unique")
    if enforce_authoritative and len(master) != MASTER_ROWS:
        raise AssertionError(f"master row count changed: {len(master)} != {MASTER_ROWS}")

    parts: list[pd.DataFrame] = []
    expected_features: list[str] | None = None
    for ticker, bucket in (("SPXW", 25), ("QQQ", 35), ("SPY", 35)):
        part = master.loc[master["ticker"].eq(ticker)].copy()
        part, features = build_diff_features(part, ticker=ticker, bucket=bucket)
        if expected_features is None:
            expected_features = features
        elif features != expected_features:
            raise AssertionError("Pairwise E0 allowlist changed by ticker")
        parts.append(part[list(dict.fromkeys([*KEY, *features]))])
    if expected_features is None:
        raise AssertionError("master contains no supported ticker rows")
    view = pd.concat(parts, ignore_index=True).sort_values(KEY, kind="stable").reset_index(drop=True)
    if len(view) != len(master) or view.duplicated(["ticker", "trade_date", "minute"]).any():
        raise AssertionError("E0 construction did not preserve the master universe")
    return view, expected_features


def _underlying_path(root: Path, symbol: str, trade_date: str) -> Path:
    return root / symbol / trade_date[:4] / trade_date[4:6] / f"{symbol}_{trade_date}.parquet"


def load_exact_underlying_day(path: Path, *, symbol: str, trade_date: str) -> pd.DataFrame:
    required = ["symbol", "date", "timestamp", "open", "high", "low", "close", "tick_count"]
    if not path.exists():
        raise FileNotFoundError(path)
    schema = pq.ParquetFile(path).schema_arrow.names
    if not set(required).issubset(schema):
        raise KeyError(f"{path} lacks required underlying fields")
    frame = pd.read_parquet(path, columns=required)
    timestamp = pd.to_datetime(frame["timestamp"], errors="coerce")
    if timestamp.isna().any() or timestamp.dt.second.ne(0).any() or timestamp.dt.microsecond.ne(0).any():
        raise AssertionError(f"non-exact underlying timestamp in {path}")
    if timestamp.duplicated().any():
        raise AssertionError(f"duplicate underlying timestamp in {path}")
    if not frame["symbol"].astype(str).eq(symbol).all():
        raise AssertionError(f"symbol metadata mismatch in {path}")
    if not _day(frame["date"]).eq(trade_date).all():
        raise AssertionError(f"date metadata mismatch in {path}")
    # Validate values only after selecting a consumed exact window.  Three known
    # SPY rows at 09:54--09:56 on 2023-06-05 are outside every [t-30m,t)
    # window and must be counted by upstream audits, not used to reject or alter
    # an otherwise valid decision.
    numeric = frame[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    numeric["tick_count"] = pd.to_numeric(frame["tick_count"], errors="coerce")
    numeric.index = pd.DatetimeIndex(timestamp)
    return numeric.sort_index()


def exact_completed_window(day: pd.DataFrame, event_timestamp: pd.Timestamp) -> pd.DataFrame:
    event = pd.Timestamp(event_timestamp)
    expected = pd.date_range(event - pd.Timedelta(minutes=30), periods=30, freq="min")
    missing = expected.difference(day.index)
    if len(missing):
        raise AssertionError(f"missing exact completed bars before {event.isoformat()}: {missing[:3].tolist()}")
    window = day.loc[expected].copy()
    if not window.index.equals(expected):
        raise AssertionError("underlying window was not selected by exact timestamp equality")
    if not (window.index < event).all():
        raise AssertionError("current/future underlying bar entered the completed window")
    ohlc = window[["open", "high", "low", "close"]]
    if not np.isfinite(ohlc.to_numpy(dtype=float)).all() or ohlc.le(0.0).any().any():
        raise AssertionError(f"invalid OHLC in consumed exact window before {event.isoformat()}")
    if (ohlc["high"] < ohlc[["open", "close", "low"]].max(axis=1)).any():
        raise AssertionError(f"high envelope failure in consumed window before {event.isoformat()}")
    if (ohlc["low"] > ohlc[["open", "close", "high"]].min(axis=1)).any():
        raise AssertionError(f"low envelope failure in consumed window before {event.isoformat()}")
    tick_count = pd.to_numeric(window["tick_count"], errors="coerce")
    if not np.isfinite(tick_count.to_numpy(dtype=float)).all() or tick_count.lt(0.0).any():
        raise AssertionError(f"invalid tick_count in consumed window before {event.isoformat()}")
    return window


def _strict_corr(x: np.ndarray, y: np.ndarray) -> float:
    x_std = float(np.std(x, ddof=0))
    y_std = float(np.std(y, ddof=0))
    if x_std <= EPSILON or y_std <= EPSILON:
        raise AssertionError("undefined cross-market correlation")
    return float(np.mean((x - x.mean()) * (y - y.mean())) / (x_std * y_std))


def pair_features(first: pd.DataFrame, second: pd.DataFrame) -> dict[str, float]:
    """Compute the seven frozen fields from two exact 30-close windows."""
    if len(first) != 30 or len(second) != 30 or not first.index.equals(second.index):
        raise AssertionError("pair windows must contain the same 30 exact timestamps")
    close_a = first["close"].to_numpy(dtype=float)
    close_b = second["close"].to_numpy(dtype=float)
    returns_a = np.diff(np.log(close_a)) * 10_000.0  # 29 completed 1m returns
    returns_b = np.diff(np.log(close_b)) * 10_000.0
    var_b = float(np.mean((returns_b - returns_b.mean()) ** 2))
    if var_b <= EPSILON:
        raise AssertionError("zero-variance beta denominator")
    covariance = float(np.mean((returns_a - returns_a.mean()) * (returns_b - returns_b.mean())))
    beta = covariance / var_b
    result: dict[str, float] = {"beta_30": float(beta)}
    for horizon in (1, 5, 15):
        ret_a = float(np.log(close_a[-1] / close_a[-1 - horizon]) * 10_000.0)
        ret_b = float(np.log(close_b[-1] / close_b[-1 - horizon]) * 10_000.0)
        result[f"residual_{horizon}m"] = ret_a - beta * ret_b
    rv_a = float(np.sqrt(np.sum(returns_a**2)))
    rv_b = float(np.sqrt(np.sum(returns_b**2)))
    if rv_a <= EPSILON or rv_b <= EPSILON:
        raise AssertionError("zero realized volatility in cross-market pair")
    result["relative_rv_30"] = float(np.log(rv_a / rv_b))
    result["lead_score_30"] = _strict_corr(returns_b[:-1], returns_a[1:]) - _strict_corr(
        returns_a[:-1], returns_b[1:]
    )
    basis = np.log(close_a / close_b)
    basis_std = float(np.std(basis, ddof=0))
    if basis_std <= EPSILON:
        raise AssertionError("zero-variance cross-market basis")
    result["basis_z_30"] = float((basis[-1] - basis.mean()) / basis_std)
    if tuple(result) != PAIR_FIELDS or not np.isfinite(np.asarray(list(result.values()), dtype=float)).all():
        raise AssertionError("cross-market pair feature contract failed")
    return result


def cross_features_for_event(windows: dict[str, pd.DataFrame], *, target: str) -> dict[str, float]:
    if set(windows) != set(MARKETS):
        raise AssertionError("all four exact market windows are required")
    if target not in {"SPXW", "SPY", "QQQ"}:
        raise AssertionError(f"unsupported target ticker: {target}")
    output: dict[str, float] = {}
    for prefix, first, second in FIXED_PAIRS:
        output.update({f"xmt__{prefix}__{key}": value for key, value in pair_features(windows[first], windows[second]).items()})
    output.update(
        {
            f"xmt__target_tlt__{key}": value
            for key, value in pair_features(windows[target], windows["TLT"]).items()
        }
    )
    if tuple(output) != CROSS_FEATURES:
        raise AssertionError("cross-market ordered allowlist changed")
    return output


def build_view(
    *,
    master_path: Path = MASTER,
    underlying_root: Path = UNDERLYING_ROOT,
    output_path: Path = DEFAULT_VIEW,
    inventory_path: Path = DEFAULT_INVENTORY,
    manifest_path: Path = DEFAULT_MANIFEST,
    enforce_authoritative: bool = True,
) -> dict[str, Any]:
    for path in (output_path, inventory_path, manifest_path):
        _assert_output_path(path)
    e0, e0_features = load_master_e0(master_path, enforce_authoritative=enforce_authoritative)
    source_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    for trade_date, events in e0.groupby("trade_date", sort=True):
        days: dict[str, pd.DataFrame] = {}
        for symbol in MARKETS:
            path = _underlying_path(underlying_root, symbol, str(trade_date))
            days[symbol] = load_exact_underlying_day(path, symbol=symbol, trade_date=str(trade_date))
            source_rows.append(
                {"symbol": symbol, "trade_date": str(trade_date), "path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            )
        window_cache: dict[pd.Timestamp, dict[str, pd.DataFrame]] = {}
        for event in events.itertuples(index=False):
            timestamp = pd.Timestamp(event.timestamp)
            if timestamp not in window_cache:
                window_cache[timestamp] = {
                    symbol: exact_completed_window(day, timestamp) for symbol, day in days.items()
                }
            try:
                features = cross_features_for_event(window_cache[timestamp], target=str(event.ticker))
            except AssertionError as exc:
                raise AssertionError(
                    "cross-market feature gate failed at "
                    f"ticker={event.ticker} trade_date={event.trade_date} timestamp={timestamp.isoformat()}: {exc}"
                ) from exc
            feature_rows.append(
                {
                    "ticker": str(event.ticker),
                    "trade_date": str(event.trade_date),
                    "timestamp": timestamp,
                    "minute": int(event.minute),
                    **features,
                }
            )
    cross = pd.DataFrame(feature_rows)
    if len(cross) != len(e0) or cross.duplicated(KEY).any():
        raise AssertionError("cross-market feature rows do not preserve master keys")
    view = e0.merge(cross, on=KEY, how="left", validate="one_to_one")
    ordered = list(dict.fromkeys([*KEY, *e0_features, *CROSS_FEATURES]))
    view = view[ordered].sort_values(KEY, kind="stable").reset_index(drop=True)
    if view[list(CROSS_FEATURES)].isna().any().any() or not np.isfinite(view[list(CROSS_FEATURES)].to_numpy(dtype=float)).all():
        raise AssertionError("cross-market block is not complete and finite")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    view.to_parquet(output_path, index=False, compression="zstd")
    inventory = pd.DataFrame(source_rows).sort_values(["trade_date", "symbol"], kind="stable")
    if inventory.duplicated(["trade_date", "symbol"]).any():
        raise AssertionError("source inventory contains duplicate sessions")
    inventory.to_csv(inventory_path, index=False, lineterminator="\n")
    master_session_count = int(view["trade_date"].nunique())
    source_sessions = int(len(inventory))
    if enforce_authoritative and (master_session_count != 971 or source_sessions != 3_884):
        raise AssertionError(
            f"authoritative session counts changed: master={master_session_count}, sources={source_sessions}"
        )
    x0_features = list(e0_features)
    x1_features = [*x0_features, *CROSS_FEATURES]
    manifest = {
        "schema": "cross_market_transmission_view_v1",
        "status": "PASS_EXACT_CROSS_MARKET_VIEW",
        "outcomes_in_view": False,
        "outcomes_read": False,
        "outer_2024_2025_evaluated": False,
        "new_data_source": False,
        "master_path": str(master_path),
        "master_sha256": sha256_file(master_path),
        "master_rows_preserved": int(len(view)),
        "master_session_count": master_session_count,
        "date_min": str(view["trade_date"].min()),
        "date_max": str(view["trade_date"].max()),
        "join_contract": "exact timestamp equality; exactly 30 completed bars [t-30m,t)",
        "forbidden_joins_used": [],
        "live_parity": "BLOCKED_IMPLEMENTATION",
        "live_source_mapping": {
            "SPXW": "rt_data/YYYYMMDD/spot_SPX_latest.parquet",
            "SPY": "rt_data/YYYYMMDD/spot_SPY_latest.parquet",
            "QQQ": "rt_data/YYYYMMDD/spot_QQQ_latest.parquet",
            "TLT": "rt_data/YYYYMMDD/spot_TLT_latest.parquet",
        },
        "live_requirement": "require all exact completed timestamps and abstain; the existing <=3m as-of context path is forbidden",
        "markets": list(MARKETS),
        "X0": {
            "features": x0_features,
            "feature_count": len(x0_features),
            "ordered_json_sha256": hash_ordered(x0_features),
        },
        "X1": {
            "features": x1_features,
            "feature_count": len(x1_features),
            "ordered_json_sha256": hash_ordered(x1_features),
        },
        "cross_market": {
            "features": list(CROSS_FEATURES),
            "feature_count": len(CROSS_FEATURES),
            "ordered_sha256": hash_ordered(CROSS_FEATURES),
            "window_closes": 30,
            "one_minute_returns": 29,
            "pair_fields": list(PAIR_FIELDS),
            "pairs": ["SPXW/SPY", "QQQ/SPY", "QQQ/SPXW", "TARGET/TLT"],
        },
        "source_inventory_path": str(inventory_path),
        "source_inventory_sha256": sha256_file(inventory_path),
        "source_sessions": source_sessions,
        "view_path": str(output_path),
        "view_sha256": sha256_file(output_path),
        "view_bytes": output_path.stat().st_size,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    manifest["manifest_sha256"] = sha256_file(manifest_path)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master", default=str(MASTER))
    parser.add_argument("--underlying-root", default=str(UNDERLYING_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_VIEW))
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    manifest = build_view(
        master_path=Path(args.master),
        underlying_root=Path(args.underlying_root),
        output_path=Path(args.output),
        inventory_path=Path(args.inventory),
        manifest_path=Path(args.manifest),
    )
    print(json.dumps({key: manifest[key] for key in ("status", "master_rows_preserved", "view_sha256", "manifest_sha256")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
