"""Fixed mechanical audit of Greek-wall and IB/Fibonacci interaction states.

This script intentionally contains no fitted model or threshold search. See
research_papers/JEPA/WALL_INTERACTION_EXECQUOTE_PREDECLARATION_V1.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walkforward_event_option_gate import DeployConfig, deploy, metrics


START_DATE = "20220801"
END_DATE = "20251231"
EVAL_START_MONTH = "202401"
EVAL_END_MONTH = "202512"
FIRST_MINUTE = 635
LAST_MINUTE = 870
TOUCH_BPS = 15.0
BUFFER_BPS = 5.0
MAGNET_MAX_BPS = 80.0
MIN_APPROACH_BPS = 3.0
CONFLUENCE_BPS = 15.0

TICKER_CONFIG = {
    "SPXW": {"feature_ticker": "SPX", "bucket": 25, "max_day": 4, "cooldown": 0},
    "QQQ": {"feature_ticker": "QQQ", "bucket": 35, "max_day": 2, "cooldown": 30},
    "SPY": {"feature_ticker": "SPY", "bucket": 35, "max_day": 1, "cooldown": 0},
}

FEATURE_COLUMNS = [
    "spot_price",
    "dist_to_max_gamma", "dist_to_min_gamma", "dist_to_zero_gamma",
    "dist_to_max_dgex", "dist_to_min_dgex",
    *[name for day in range(1, 6) for name in (
        f"dist_ib_high_D{day}", f"dist_ib_low_D{day}",
    )],
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def level_from_distance(spot: pd.Series, distance_bps: pd.Series) -> pd.Series:
    """Invert (spot-level)/spot*10000 without using any future value."""
    return spot.astype(float) * (1.0 - distance_bps.astype(float) / 10_000.0)


def signed_distance_bps(spot: pd.Series, level: pd.Series) -> pd.Series:
    return (spot.astype(float) - level.astype(float)) / spot.astype(float) * 10_000.0


def _add_level(levels: dict[str, tuple[pd.Series, str]], name: str, level: pd.Series, role: str) -> None:
    clean = pd.to_numeric(level, errors="coerce")
    levels[name] = (clean.where(clean > 0.0), role)


def build_level_universe(frame: pd.DataFrame) -> dict[str, tuple[pd.Series, str]]:
    """Return level price series and frozen economic roles."""
    spot = pd.to_numeric(frame["spot"], errors="coerce")
    levels: dict[str, tuple[pd.Series, str]] = {}
    for name, role in (
        ("max_gamma", "resistance"), ("min_gamma", "support"),
        ("zero_gamma", "magnet"), ("max_dgex", "magnet"),
        ("min_dgex", "magnet"),
    ):
        _add_level(levels, name, level_from_distance(spot, frame[f"dist_to_{name}"]), role)

    current = {
        "ib_high": "resistance", "ib_low": "support",
        "fib_127_up": "resistance", "fib_161_up": "resistance", "fib_200_up": "resistance",
        "fib_127_dn": "support", "fib_161_dn": "support", "fib_200_dn": "support",
    }
    for name, role in current.items():
        _add_level(levels, f"d0_{name}", level_from_distance(spot, frame[f"dist_{name}_bps"]), role)

    for day in range(1, 6):
        high = level_from_distance(spot, frame[f"dist_ib_high_D{day}"])
        low = level_from_distance(spot, frame[f"dist_ib_low_D{day}"])
        valid = (high > low) & (low > 0.0)
        high = high.where(valid)
        low = low.where(valid)
        width = high - low
        _add_level(levels, f"d{day}_ib_high", high, "resistance")
        _add_level(levels, f"d{day}_ib_low", low, "support")
        for label, extension in (("127", 0.272), ("161", 0.618), ("200", 1.0)):
            _add_level(levels, f"d{day}_fib_{label}_up", high + width * extension, "resistance")
            _add_level(levels, f"d{day}_fib_{label}_dn", low - width * extension, "support")
    return levels


def join_inputs(events: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    events = events.copy()
    features = features.copy()
    events["trade_date"] = events["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    events = events[events["trade_date"].between(START_DATE, END_DATE)].copy()
    events = events[events["minute"].between(FIRST_MINUTE, LAST_MINUTE)].copy()
    if events["trade_date"].str.startswith("2026").any():
        raise AssertionError("2026 entered the sealed wall audit")
    events["join_ticker"] = events["ticker"].map(lambda value: TICKER_CONFIG[str(value)]["feature_ticker"])
    events["join_date"] = events["trade_date"]
    events["join_time"] = (
        (events["minute"].astype(int) // 60).astype(str).str.zfill(2)
        + ":" + (events["minute"].astype(int) % 60).astype(str).str.zfill(2)
    )

    features["join_ticker"] = features["ticker"].astype(str)
    features["join_date"] = features["date"].astype(str).str.replace(r"\.0$", "", regex=True)
    features["join_time"] = features["time"].astype(str).str[:5]
    feature_keep = ["join_ticker", "join_date", "join_time", *FEATURE_COLUMNS]
    features = features[features["join_date"].between(START_DATE, END_DATE)][feature_keep].copy()
    keys = ["join_ticker", "join_date", "join_time"]
    if events.duplicated(keys).any() or features.duplicated(keys).any():
        raise AssertionError("Join inputs are not unique on ticker/date/minute")
    joined = events.merge(features, on=keys, how="left", validate="one_to_one", indicator=True)
    if not joined["_merge"].eq("both").all():
        raise AssertionError(f"Unmatched wall feature rows: {(joined['_merge'] != 'both').sum()}")
    joined = joined.drop(columns=["_merge"])
    spot_error = ((joined["spot"].astype(float) - joined["spot_price"].astype(float)) / joined["spot"].astype(float) * 10_000.0).abs()
    if float(spot_error.max()) > 1e-9:
        raise AssertionError(f"Spot parity failed: max error {spot_error.max()} bps")
    joined["date"] = joined["trade_date"]
    joined["month"] = joined["trade_date"].str[:6]
    return joined.sort_values(["ticker", "trade_date", "minute"], kind="stable").reset_index(drop=True)


def add_contiguous_spot_lags(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    grouped = out.groupby(["ticker", "trade_date"], sort=False, observed=True)
    for steps in (1, 2, 3):
        minutes = grouped["minute"].shift(steps)
        values = grouped["spot"].shift(steps)
        expected = out["minute"].astype(float) - 5.0 * steps
        out[f"spot_lag_{steps * 5}m"] = values.where(minutes.astype(float).eq(expected))
    return out


def _confluence_counts(level_matrix: np.ndarray, spot: np.ndarray) -> np.ndarray:
    count = np.zeros_like(level_matrix, dtype=np.int16)
    for idx in range(level_matrix.shape[1]):
        anchor = level_matrix[:, idx]
        distance = np.abs(level_matrix - anchor[:, None]) / spot[:, None] * 10_000.0
        valid = np.isfinite(distance) & (distance <= CONFLUENCE_BPS)
        count[:, idx] = valid.sum(axis=1)
    return count


def rejection_pierce_mask(role: str, *lag_distances: np.ndarray) -> np.ndarray:
    """Whether prior spot reached the opposite side of a fixed role-specific level."""
    if role == "support":
        return np.minimum.reduce(lag_distances) <= 0.0
    if role == "resistance":
        return np.maximum.reduce(lag_distances) >= 0.0
    raise ValueError(f"Pierce semantics are undefined for role={role}")


def build_signals(
    frame: pd.DataFrame,
    *,
    require_rejection_pierce: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build descriptive M0 and fixed event-state E1 signals."""
    work = add_contiguous_spot_lags(frame)
    levels = build_level_universe(work)
    names = list(levels)
    roles = [levels[name][1] for name in names]
    level_matrix = np.column_stack([levels[name][0].to_numpy(dtype=float) for name in names])
    spot = work["spot"].to_numpy(dtype=float)
    d0 = (spot[:, None] - level_matrix) / spot[:, None] * 10_000.0
    abs_d0 = np.abs(d0)
    confluence = _confluence_counts(level_matrix, spot)

    lag_distances: dict[int, np.ndarray] = {}
    for lag in (5, 10, 15):
        lag_spot = work[f"spot_lag_{lag}m"].to_numpy(dtype=float)
        lag_distances[lag] = (lag_spot[:, None] - level_matrix) / spot[:, None] * 10_000.0
    momentum5 = (spot - work["spot_lag_5m"].to_numpy(dtype=float)) / spot * 10_000.0
    momentum15 = (spot - work["spot_lag_15m"].to_numpy(dtype=float)) / spot * 10_000.0

    # M0: nearest level in the fixed magnet band, direction toward that level.
    eligible = np.isfinite(abs_d0) & (abs_d0 >= TOUCH_BPS) & (abs_d0 <= MAGNET_MAX_BPS)
    nearest_distance = np.where(eligible, abs_d0, np.inf)
    nearest_idx = nearest_distance.argmin(axis=1)
    nearest_value = nearest_distance[np.arange(len(work)), nearest_idx]
    m0 = work[np.isfinite(nearest_value)].copy()
    m0_idx = nearest_idx[np.isfinite(nearest_value)]
    m0_d = d0[np.isfinite(nearest_value), m0_idx]
    m0["action"] = np.where(m0_d < 0.0, "CALL", "PUT")
    m0["event_type"] = "nearest_magnet"
    m0["level_name"] = np.asarray(names, dtype=object)[m0_idx]
    m0["score"] = 1.0 + (MAGNET_MAX_BPS - np.abs(m0_d)) / MAGNET_MAX_BPS * 0.09

    candidates: list[dict[str, np.ndarray | str]] = []
    touch = np.minimum.reduce([abs_d0, np.abs(lag_distances[5]), np.abs(lag_distances[10]), np.abs(lag_distances[15])]) <= TOUCH_BPS
    approach = np.abs(lag_distances[15]) - abs_d0 >= MIN_APPROACH_BPS
    for idx, (name, role) in enumerate(zip(names, roles, strict=True)):
        proximity = (MAGNET_MAX_BPS - np.minimum(abs_d0[:, idx], MAGNET_MAX_BPS)) / MAGNET_MAX_BPS * 0.09
        bonus = np.minimum(np.maximum(confluence[:, idx] - 1, 0), 3) * 0.25
        magnet_call = (d0[:, idx] <= -TOUCH_BPS) & (d0[:, idx] >= -MAGNET_MAX_BPS) & approach[:, idx] & (momentum15 > 0.0)
        magnet_put = (d0[:, idx] >= TOUCH_BPS) & (d0[:, idx] <= MAGNET_MAX_BPS) & approach[:, idx] & (momentum15 < 0.0)
        candidates.extend([
            {"mask": magnet_call, "action": "CALL", "event": "magnet", "name": name, "score": 1.0 + bonus + proximity},
            {"mask": magnet_put, "action": "PUT", "event": "magnet", "name": name, "score": 1.0 + bonus + proximity},
        ])
        if role == "support":
            rejection = touch[:, idx] & (d0[:, idx] >= BUFFER_BPS) & (momentum5 > 0.0)
            if require_rejection_pierce:
                rejection &= rejection_pierce_mask("support",
                    lag_distances[5][:, idx], lag_distances[10][:, idx], lag_distances[15][:, idx],
                )
            acceptance = (d0[:, idx] <= -BUFFER_BPS) & (lag_distances[5][:, idx] <= -BUFFER_BPS) & (lag_distances[10][:, idx] <= -BUFFER_BPS) & (momentum15 < 0.0)
            candidates.extend([
                {"mask": rejection, "action": "CALL", "event": "rejection", "name": name, "score": 3.0 + bonus + proximity},
                {"mask": acceptance, "action": "PUT", "event": "acceptance", "name": name, "score": 2.0 + bonus + proximity},
            ])
        elif role == "resistance":
            rejection = touch[:, idx] & (d0[:, idx] <= -BUFFER_BPS) & (momentum5 < 0.0)
            if require_rejection_pierce:
                rejection &= rejection_pierce_mask("resistance",
                    lag_distances[5][:, idx], lag_distances[10][:, idx], lag_distances[15][:, idx],
                )
            acceptance = (d0[:, idx] >= BUFFER_BPS) & (lag_distances[5][:, idx] >= BUFFER_BPS) & (lag_distances[10][:, idx] >= BUFFER_BPS) & (momentum15 > 0.0)
            candidates.extend([
                {"mask": rejection, "action": "PUT", "event": "rejection", "name": name, "score": 3.0 + bonus + proximity},
                {"mask": acceptance, "action": "CALL", "event": "acceptance", "name": name, "score": 2.0 + bonus + proximity},
            ])

    best_call = np.full(len(work), -np.inf)
    best_put = np.full(len(work), -np.inf)
    best_call_meta = np.full((len(work), 2), "", dtype=object)
    best_put_meta = np.full((len(work), 2), "", dtype=object)
    for candidate in candidates:
        mask = np.asarray(candidate["mask"], dtype=bool)
        values = np.asarray(candidate["score"], dtype=float)
        target = best_call if candidate["action"] == "CALL" else best_put
        meta = best_call_meta if candidate["action"] == "CALL" else best_put_meta
        improve = mask & (values > target)
        target[improve] = values[improve]
        meta[improve, 0] = str(candidate["event"])
        meta[improve, 1] = str(candidate["name"])
    active = np.isfinite(np.maximum(best_call, best_put)) & ~np.isclose(best_call, best_put, rtol=0.0, atol=1e-12)
    choose_call = best_call > best_put
    e1 = work[active].copy()
    e1["action"] = np.where(choose_call[active], "CALL", "PUT")
    e1["score"] = np.maximum(best_call, best_put)[active]
    e1["event_type"] = np.where(choose_call[active], best_call_meta[active, 0], best_put_meta[active, 0])
    e1["level_name"] = np.where(choose_call[active], best_call_meta[active, 1], best_put_meta[active, 1])
    return m0, e1


def attach_outcomes(signals: pd.DataFrame, ticker: str) -> pd.DataFrame:
    bucket = int(TICKER_CONFIG[ticker]["bucket"])
    out = signals.copy()
    is_call = out["action"].eq("CALL")
    call_ret = pd.to_numeric(out[f"call_d{bucket:02d}_opt_exit_ret"], errors="coerce")
    put_ret = pd.to_numeric(out[f"put_d{bucket:02d}_opt_exit_ret"], errors="coerce")
    call_exit = pd.to_numeric(out[f"call_d{bucket:02d}_opt_exit_minutes"], errors="coerce")
    put_exit = pd.to_numeric(out[f"put_d{bucket:02d}_opt_exit_minutes"], errors="coerce")
    out["realized_return"] = np.where(is_call, call_ret, put_ret)
    out["exit_minutes"] = np.where(is_call, call_exit, put_exit)
    finite = np.isfinite(out["realized_return"].astype(float)) & np.isfinite(out["exit_minutes"].astype(float))
    return out[finite].copy()


def deploy_arm(signals: pd.DataFrame, arm: str) -> pd.DataFrame:
    frames = []
    for ticker, config in TICKER_CONFIG.items():
        selected = attach_outcomes(signals[signals["ticker"].eq(ticker)], ticker)
        if selected.empty:
            continue
        cfg = DeployConfig(threshold=0.0, max_trades_per_day=int(config["max_day"]))
        traded = deploy(selected, cfg, int(config["cooldown"]))
        traded["arm"] = arm
        frames.append(traded)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _safe_metrics(trades: pd.DataFrame, expected_months: list[str]) -> dict:
    result = metrics(trades, expected_months=expected_months)
    if trades.empty:
        result["min_hold_minutes"] = float("nan")
    else:
        result["min_hold_minutes"] = float(pd.to_numeric(trades["exit_minutes"], errors="coerce").min())
    return result


def summarize(trades: pd.DataFrame) -> dict:
    evaluation_months = pd.period_range(EVAL_START_MONTH, EVAL_END_MONTH, freq="M").strftime("%Y%m").tolist()
    report: dict[str, object] = {"evaluation_months": evaluation_months, "arms": {}}
    for arm in ("M0", "E1"):
        arm_trades = trades[trades["arm"].eq(arm)].copy() if not trades.empty else trades.copy()
        arm_report: dict[str, object] = {}
        for ticker in TICKER_CONFIG:
            selected = arm_trades[arm_trades["ticker"].eq(ticker)].copy()
            eval_selected = selected[selected["month"].between(EVAL_START_MONTH, EVAL_END_MONTH)].copy()
            ticker_metrics = _safe_metrics(eval_selected, evaluation_months)
            monthly = {}
            for month in evaluation_months:
                monthly[month] = _safe_metrics(eval_selected[eval_selected["month"].eq(month)], [month])
            passed = (
                arm == "E1"
                and ticker_metrics["profit_factor"] >= 1.3
                and ticker_metrics["win_rate"] >= 0.50
                and ticker_metrics["min_month_trades"] >= 18
                and ticker_metrics["positive_month_rate"] == 1.0
                and ticker_metrics["min_hold_minutes"] >= 30.0
            )
            arm_report[ticker] = {"evaluation": ticker_metrics, "monthly": monthly, "passed": bool(passed)}
        report["arms"][arm] = arm_report
    report["e1_all_tickers_passed"] = all(report["arms"]["E1"][ticker]["passed"] for ticker in TICKER_CONFIG)
    report["delta_wall_materialized"] = False
    report["adaptive_discovery_not_promotable"] = True
    report["contains_2026"] = False
    report["production_modified"] = False
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", required=True)
    parser.add_argument("--features", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--require-rejection-pierce", action="store_true")
    args = parser.parse_args()
    event_path = Path(args.events)
    feature_path = Path(args.features)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite {output_dir}")
    events = pd.read_parquet(event_path)
    features = pd.read_parquet(feature_path, columns=["ticker", "date", "time", *FEATURE_COLUMNS])
    joined = join_inputs(events, features)
    m0, e1 = build_signals(joined, require_rejection_pierce=bool(args.require_rejection_pierce))
    trades = pd.concat([deploy_arm(m0, "M0"), deploy_arm(e1, "E1")], ignore_index=True)
    if not trades.empty and trades["month"].astype(str).str.startswith("2026").any():
        raise AssertionError("2026 appeared in output trades")
    output_dir.mkdir(parents=True)
    compact_columns = [
        "arm", "ticker", "trade_date", "minute", "month", "action", "event_type",
        "level_name", "score", "realized_return", "exit_minutes", "deploy_config",
    ]
    trades[compact_columns].to_csv(output_dir / "trades.csv", index=False)
    report = summarize(trades)
    manifest = {
        "events_sha256": sha256_file(event_path),
        "features_sha256": sha256_file(feature_path),
        "joined_rows": int(len(joined)),
        "m0_signal_rows": int(len(m0)),
        "e1_signal_rows": int(len(e1)),
        "trade_rows": int(len(trades)),
        "parameters": {
            "touch_bps": TOUCH_BPS, "buffer_bps": BUFFER_BPS,
            "magnet_max_bps": MAGNET_MAX_BPS, "min_approach_bps": MIN_APPROACH_BPS,
            "confluence_bps": CONFLUENCE_BPS,
            "require_rejection_pierce": bool(args.require_rejection_pierce),
        },
        "contains_2026": False,
        "production_modified": False,
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": manifest, "e1_all_tickers_passed": report["e1_all_tickers_passed"]}, indent=2))


if __name__ == "__main__":
    main()
