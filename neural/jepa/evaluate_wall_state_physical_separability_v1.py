"""Evaluate the predeclared physical separability of GEX/DEX wall state."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

START_DATE = "20220801"
END_DATE = "20251231"
HORIZONS = (30, 60, 120, 180)
TOUCH_BPS = 15.0
MAX_DISTANCE_BPS = 80.0
MIN_APPROACH_BPS = 3.0
BUFFER_BPS = 5.0
SEED = 20260711
MAX_WORKERS = 16
WALL_SPECS = {
    "call_gamma": "resistance",
    "put_gamma": "support",
    "call_delta": "resistance",
    "put_delta": "support",
}
CURRENT_LEVEL_SPECS = {
    "ib_high": "resistance", "ib_low": "support",
    "fib_127_up": "resistance", "fib_161_up": "resistance", "fib_200_up": "resistance",
    "fib_127_dn": "support", "fib_161_dn": "support", "fib_200_dn": "support",
}
EXPECTED_HASHES = {
    "walls": "94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef",
    "events": "d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408",
    "prior_ib": "5f908e11090ea6566e3eadeba0a436ab5d01cf99955d6acc5050eae264fe13b5",
    "manifest": "5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88",
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def level_from_distance(spot: pd.Series, distance_bps: pd.Series) -> pd.Series:
    return spot.astype(float) * (1.0 - distance_bps.astype(float) / 10_000.0)


def add_spot_lags(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.sort_values(["ticker", "trade_date", "minute"], kind="stable").copy()
    grouped = out.groupby(["ticker", "trade_date"], observed=True, sort=False)
    for lag in (5, 15, 30):
        steps = lag // 5
        prior_minute = grouped["minute"].shift(steps)
        prior_spot = grouped["spot"].shift(steps)
        contiguous = prior_minute.eq(out["minute"] - lag)
        out[f"spot_lag_{lag}m"] = prior_spot.where(contiguous)
        out[f"spot_ret_{lag}m_bps"] = ((out["spot"] / prior_spot - 1.0) * 10_000.0).where(contiguous)
    return out


def join_causal_inputs(walls: pd.DataFrame, events: pd.DataFrame, prior_ib: pd.DataFrame) -> pd.DataFrame:
    keys = ["ticker", "trade_date", "minute"]
    walls = walls.copy()
    walls["trade_date"] = walls["trade_date"].astype(str)
    events = events.copy()
    events["ticker"] = events["ticker"].astype(str).str.upper()
    events["trade_date"] = events["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    events = events[
        events["trade_date"].between(START_DATE, END_DATE)
        & events["minute"].between(635, 870)
        & ((events["minute"] - 635) % 5 == 0)
    ].copy()
    event_columns = [column for column in events if column in {
        *keys, "spot", "ib_range_bps",
        *[f"dist_{name}_bps" for name in CURRENT_LEVEL_SPECS],
    }]
    events = events[event_columns].groupby(keys, observed=True, as_index=False).median(numeric_only=True)
    joined = events.merge(walls, on=keys, how="inner", suffixes=("_event", ""), validate="one_to_one")
    spot_diff = ((joined["spot"] - joined["spot_event"]).abs() / joined["spot_event"] * 10_000.0)
    if len(joined) != len(events) or float(spot_diff.max()) > 1.0:
        raise AssertionError(f"wall/event parity failed: rows={len(joined)}/{len(events)} max_bps={spot_diff.max()}")
    joined = joined.drop(columns=["spot_event"])

    prior = prior_ib.copy()
    prior["join_ticker"] = prior["ticker"].astype(str).str.upper()
    prior["trade_date"] = prior["date"].astype(str).str.replace(r"\.0$", "", regex=True)
    prior["minute"] = prior["time"].astype(str).str[:2].astype(int) * 60 + prior["time"].astype(str).str[3:5].astype(int)
    prior["ticker"] = prior["join_ticker"].replace({"SPX": "SPXW"})
    prior_columns = ["ticker", "trade_date", "minute", "spot_price", *[
        f"dist_ib_{side}_D{day}" for day in range(1, 6) for side in ("high", "low")
    ]]
    prior = prior[prior["trade_date"].between(START_DATE, END_DATE)][prior_columns].copy()
    if prior.duplicated(keys).any():
        raise AssertionError("prior IB input has duplicate keys")
    joined = joined.merge(prior, on=keys, how="left", validate="one_to_one")
    prior_spot_diff = ((joined["spot"] - joined["spot_price"]).abs() / joined["spot"] * 10_000.0)
    if int(prior_spot_diff.notna().sum()) == 0 or float(prior_spot_diff.dropna().max()) > 1.0:
        raise AssertionError(f"prior IB spot parity failed: {prior_spot_diff.max()}")
    joined = joined.drop(columns=["spot_price"])
    if joined["trade_date"].str.startswith("2026").any():
        raise AssertionError("2026 entered physical wall inputs")
    return add_spot_lags(joined)


def add_ib_level_prices(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    out = frame.copy()
    specs: list[tuple[str, str]] = []
    for name, role in CURRENT_LEVEL_SPECS.items():
        column = f"ib_level_d0_{name}"
        out[column] = level_from_distance(out["spot"], out[f"dist_{name}_bps"])
        specs.append((column, role))
    for day in range(1, 6):
        high = level_from_distance(out["spot"], out[f"dist_ib_high_D{day}"])
        low = level_from_distance(out["spot"], out[f"dist_ib_low_D{day}"])
        valid = (high > low) & (low > 0.0)
        high, low = high.where(valid), low.where(valid)
        width = high - low
        pairs = {
            f"d{day}_ib_high": (high, "resistance"), f"d{day}_ib_low": (low, "support"),
            f"d{day}_fib_127_up": (high + width * 0.272, "resistance"),
            f"d{day}_fib_161_up": (high + width * 0.618, "resistance"),
            f"d{day}_fib_200_up": (high + width, "resistance"),
            f"d{day}_fib_127_dn": (low - width * 0.272, "support"),
            f"d{day}_fib_161_dn": (low - width * 0.618, "support"),
            f"d{day}_fib_200_dn": (low - width, "support"),
        }
        for name, (values, role) in pairs.items():
            column = f"ib_level_{name}"
            out[column] = values
            specs.append((column, role))
    return out, specs


def make_wall_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    work, ib_specs = add_ib_level_prices(frame)
    candidates: list[pd.DataFrame] = []
    for identity, role in WALL_SPECS.items():
        prefix = f"wall_{identity}"
        strike = pd.to_numeric(work[f"{prefix}_strike"], errors="coerce")
        distance = (work["spot"] - strike) / work["spot"] * 10_000.0
        prior_distance = (work["spot_lag_15m"] - strike) / work["spot"] * 10_000.0
        approach = prior_distance.abs() - distance.abs()
        if role == "resistance":
            geometry = distance.between(-MAX_DISTANCE_BPS, -TOUCH_BPS) & work["spot_ret_15m_bps"].gt(0.0)
        else:
            geometry = distance.between(TOUCH_BPS, MAX_DISTANCE_BPS) & work["spot_ret_15m_bps"].lt(0.0)
        selected = work[geometry & approach.ge(MIN_APPROACH_BPS)].copy()
        if selected.empty:
            continue
        selected["wall_identity"] = identity
        selected["wall_role"] = role
        selected["candidate_wall_strike"] = strike.loc[selected.index]
        selected["candidate_distance_bps"] = distance.loc[selected.index]
        selected["candidate_abs_distance_bps"] = distance.loc[selected.index].abs()
        selected["candidate_approach_15m_bps"] = approach.loc[selected.index]

        for suffix in (
            "magnitude_log", "concentration", "dominance_gap", "active_strikes",
            "total_log", "hhi", "effective_strikes", "family_active_strikes",
            "age_minutes", "same_5m", "same_15m", "same_30m",
            "move_5m_bps", "move_15m_bps", "move_30m_bps",
            "magnitude_chg_5m", "magnitude_chg_15m", "magnitude_chg_30m",
        ):
            source = f"{prefix}_{suffix}"
            selected[f"candidate_{suffix}"] = selected[source] if source in selected else np.nan

        all_distances = []
        same_role_distances = []
        for column, level_role in ib_specs:
            values = (selected[column] - selected["candidate_wall_strike"]).abs() / selected["spot"] * 10_000.0
            all_distances.append(values.to_numpy(dtype=float))
            if level_role == role:
                same_role_distances.append(values.to_numpy(dtype=float))
        all_matrix = np.column_stack(all_distances)
        role_matrix = np.column_stack(same_role_distances)
        selected["ib_confluence_count_15bps"] = np.sum(np.isfinite(all_matrix) & (all_matrix <= 15.0), axis=1)
        selected["ib_confluence_same_role_count_15bps"] = np.sum(np.isfinite(role_matrix) & (role_matrix <= 15.0), axis=1)
        selected["ib_confluence_min_bps"] = np.nanmin(all_matrix, axis=1)
        selected["ib_confluence_same_role_min_bps"] = np.nanmin(role_matrix, axis=1)
        candidates.append(selected)
    if not candidates:
        return pd.DataFrame()
    out = pd.concat(candidates, ignore_index=True)
    return out.sort_values(["ticker", "trade_date", "minute", "wall_identity"], kind="stable").reset_index(drop=True)


def label_candidate_session(candidates: pd.DataFrame, underlying_path: str | Path) -> pd.DataFrame:
    out = candidates.copy()
    path = pd.read_parquet(underlying_path, columns=["timestamp", "high", "low", "close"])
    path["dt"] = pd.to_datetime(path["timestamp"], errors="coerce").dt.floor("min")
    for column in ("high", "low", "close"):
        path[column] = pd.to_numeric(path[column], errors="coerce")
    path = path.dropna(subset=["dt", "high", "low", "close"]).sort_values("dt", kind="stable")
    lookup = path.set_index("dt")
    for horizon in HORIZONS:
        out[f"magnet_hit_{horizon}m"] = np.nan
        out[f"true_rejection_{horizon}m"] = np.nan
        out[f"accepted_break_{horizon}m"] = np.nan
        out[f"resolved_rejection_{horizon}m"] = np.nan
    for minute, positions in out.groupby("minute", observed=True).indices.items():
        date = str(out.iloc[int(positions[0])]["trade_date"])
        start = pd.Timestamp(f"{date[:4]}-{date[4:6]}-{date[6:]} {int(minute)//60:02d}:{int(minute)%60:02d}:00")
        for horizon in HORIZONS:
            end = start + pd.Timedelta(minutes=horizon)
            if end not in lookup.index:
                continue
            future = path[(path["dt"] > start) & (path["dt"] <= end)]
            if future.empty:
                continue
            future_high = float(future["high"].max())
            future_low = float(future["low"].min())
            end_row = lookup.loc[end]
            if isinstance(end_row, pd.DataFrame):
                end_row = end_row.iloc[-1]
            future_close = float(end_row["close"])
            idx = np.asarray(positions, dtype=int)
            wall = out.iloc[idx]["candidate_wall_strike"].to_numpy(dtype=float)
            entry_spot = out.iloc[idx]["spot"].to_numpy(dtype=float)
            role = out.iloc[idx]["wall_role"].astype(str).to_numpy()
            touch_low = wall * (1.0 - TOUCH_BPS / 10_000.0)
            touch_high = wall * (1.0 + TOUCH_BPS / 10_000.0)
            hit = (future_low <= touch_high) & (future_high >= touch_low)
            pierced = np.where(role == "support", future_low <= wall, future_high >= wall)
            final_distance = (future_close - wall) / entry_spot * 10_000.0
            rejection = pierced & np.where(role == "support", final_distance >= BUFFER_BPS, final_distance <= -BUFFER_BPS)
            accepted = pierced & np.where(role == "support", final_distance <= -BUFFER_BPS, final_distance >= BUFFER_BPS)
            resolved = rejection ^ accepted
            out.loc[out.index[idx], f"magnet_hit_{horizon}m"] = hit.astype(float)
            out.loc[out.index[idx], f"true_rejection_{horizon}m"] = rejection.astype(float)
            out.loc[out.index[idx], f"accepted_break_{horizon}m"] = accepted.astype(float)
            out.loc[out.index[idx[resolved]], f"resolved_rejection_{horizon}m"] = rejection[resolved].astype(float)
    return out


def add_future_labels(candidates: pd.DataFrame, manifest: pd.DataFrame, workers: int) -> tuple[pd.DataFrame, list[str]]:
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f"workers must be within 1..{MAX_WORKERS}")
    paths = manifest.copy()
    paths["ticker"] = paths["ticker"].astype(str).str.upper()
    paths["trade_date"] = paths["trade_date"].astype(str)
    path_map = paths.set_index(["ticker", "trade_date"])["underlying_path"].to_dict()
    tasks = []
    errors: list[str] = []
    for key, part in candidates.groupby(["ticker", "trade_date"], observed=True, sort=True):
        path = path_map.get(tuple(key))
        if not path:
            errors.append(f"missing underlying path for {key}")
            continue
        tasks.append((part, path))
    frames: list[pd.DataFrame] = []
    if workers == 1:
        for part, path in tasks:
            frames.append(label_candidate_session(part, path))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(label_candidate_session, part, path): (str(part.iloc[0]["ticker"]), str(part.iloc[0]["trade_date"])) for part, path in tasks}
            for index, future in enumerate(as_completed(futures), start=1):
                key = futures[future]
                try:
                    frames.append(future.result())
                except Exception as exc:
                    errors.append(f"{key}: {type(exc).__name__}: {exc}")
                if index % 100 == 0 or index == len(futures):
                    print(f"[WALL_PHYSICS:LABELS] sessions={index}/{len(futures)} errors={len(errors)}", flush=True)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return out.sort_values(["ticker", "trade_date", "minute", "wall_identity"], kind="stable").reset_index(drop=True), errors


D0_FEATURES = [
    "minute_sin", "minute_cos", "candidate_distance_bps", "candidate_abs_distance_bps",
    "candidate_approach_15m_bps", "spot_ret_5m_bps", "spot_ret_15m_bps", "spot_ret_30m_bps",
]
S1_EXTRA = [
    *[f"candidate_{name}" for name in (
        "magnitude_log", "concentration", "dominance_gap", "active_strikes", "total_log", "hhi",
        "effective_strikes", "family_active_strikes", "age_minutes", "same_5m", "same_15m", "same_30m",
        "move_5m_bps", "move_15m_bps", "move_30m_bps", "magnitude_chg_5m", "magnitude_chg_15m",
        "magnitude_chg_30m",
    )],
    "wall_gamma_call_put_balance", "wall_delta_call_put_balance",
    "wall_gamma_separation_bps", "wall_delta_separation_bps",
    "wall_net_gamma_total_log", "wall_net_delta_total_log", "wall_net_dgex_total_log",
]
S2_EXTRA = [
    "ib_range_bps", "ib_confluence_count_15bps", "ib_confluence_same_role_count_15bps",
    "ib_confluence_min_bps", "ib_confluence_same_role_min_bps",
]


def model_matrix(frame: pd.DataFrame, arm: str) -> pd.DataFrame:
    work = frame.copy()
    work["minute_sin"] = np.sin(2.0 * np.pi * work["minute"] / 1440.0)
    work["minute_cos"] = np.cos(2.0 * np.pi * work["minute"] / 1440.0)
    columns = list(D0_FEATURES)
    if arm in {"S1", "S2"}:
        columns.extend(S1_EXTRA)
    if arm == "S2":
        columns.extend(S2_EXTRA)
    matrix = work[columns].apply(pd.to_numeric, errors="coerce")
    identity = pd.get_dummies(work["wall_identity"], prefix="identity", dtype=float)
    for name in WALL_SPECS:
        column = f"identity_{name}"
        if column not in identity:
            identity[column] = 0.0
    return pd.concat([matrix.reset_index(drop=True), identity[sorted(identity)].reset_index(drop=True)], axis=1)


def assert_feature_allowlists() -> None:
    all_features = set(D0_FEATURES + S1_EXTRA + S2_EXTRA)
    forbidden = ("future", "label", "outcome", "exit", "pnl", "return", "high", "low", "close")
    offenders = sorted(column for column in all_features if any(token in column.lower() for token in forbidden))
    if offenders:
        raise AssertionError(f"forbidden physical model features: {offenders}")


def fit_cell(train: pd.DataFrame, test: pd.DataFrame, target: str, arm: str) -> dict[str, Any]:
    train = train[pd.to_numeric(train[target], errors="coerce").notna()].copy()
    test = test[pd.to_numeric(test[target], errors="coerce").notna()].copy()
    y_train = train[target].astype(int).to_numpy()
    y_test = test[target].astype(int).to_numpy()
    result: dict[str, Any] = {
        "train_rows": int(len(train)), "test_rows": int(len(test)),
        "train_positive_rate": float(y_train.mean()) if len(y_train) else None,
        "test_positive_rate": float(y_test.mean()) if len(y_test) else None,
        "valid": False, "roc_auc": None, "average_precision": None, "log_loss": None,
    }
    if len(train) == 0 or len(test) == 0 or len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
        return result
    X_train = model_matrix(train, arm)
    X_test = model_matrix(test, arm)
    positive = max(int((y_train == 1).sum()), 1)
    negative = max(int((y_train == 0).sum()), 1)
    weights = np.where(y_train == 1, len(y_train) / (2.0 * positive), len(y_train) / (2.0 * negative))
    model = lgb.LGBMClassifier(
        objective="binary", n_estimators=300, learning_rate=0.03, num_leaves=15,
        min_child_samples=100, colsample_bytree=0.8, subsample=0.8, subsample_freq=1,
        reg_alpha=0.0, reg_lambda=1.0, random_state=SEED, n_jobs=28,
        deterministic=True, force_col_wise=True, verbosity=-1,
    )
    model.fit(X_train, y_train, sample_weight=weights)
    probability = model.predict_proba(X_test)[:, 1]
    result.update({
        "valid": True,
        "roc_auc": float(roc_auc_score(y_test, probability)),
        "average_precision": float(average_precision_score(y_test, probability)),
        "log_loss": float(log_loss(y_test, probability, labels=[0, 1])),
    })
    return result


def monthly_coverage(test: pd.DataFrame, target: str) -> tuple[int, bool]:
    work = test[pd.to_numeric(test[target], errors="coerce").notna()].copy()
    if work.empty:
        return 0, False
    work["month"] = work["trade_date"].astype(str).str[:6]
    grouped = work.groupby("month", observed=True)[target]
    counts = grouped.size()
    both = grouped.nunique().ge(2)
    return int(counts.min()), bool(both.all())


def evaluate_walkforward(candidates: pd.DataFrame) -> pd.DataFrame:
    assert_feature_allowlists()
    rows = []
    folds = (("2024", "20231231", "20240101", "20241231"), ("2025", "20241231", "20250101", "20251231"))
    for fold, train_end, test_start, test_end in folds:
        for ticker in ("SPXW", "QQQ", "SPY"):
            ticker_frame = candidates[candidates["ticker"].eq(ticker)]
            train_base = ticker_frame[ticker_frame["trade_date"].le(train_end)]
            test_base = ticker_frame[ticker_frame["trade_date"].between(test_start, test_end)]
            for horizon in HORIZONS:
                for task, target in (
                    ("magnet_hit", f"magnet_hit_{horizon}m"),
                    ("resolved_rejection", f"resolved_rejection_{horizon}m"),
                ):
                    min_month_rows, monthly_two_classes = monthly_coverage(test_base, target)
                    for arm in ("D0", "S1", "S2"):
                        metrics = fit_cell(train_base, test_base, target, arm)
                        rows.append({
                            "fold": fold, "ticker": ticker, "task": task, "horizon": horizon,
                            "arm": arm, "target": target, "min_month_rows": min_month_rows,
                            "monthly_two_classes": monthly_two_classes, **metrics,
                        })
                        print(f"[WALL_PHYSICS:MODEL] {fold} {ticker} {task}{horizon} {arm} auc={metrics['roc_auc']}", flush=True)
    return pd.DataFrame(rows)


def summarize_gate(cells: pd.DataFrame) -> dict[str, Any]:
    d0 = cells[cells["arm"].eq("D0")].copy()
    s2 = cells[cells["arm"].eq("S2")].copy()
    keys = ["fold", "ticker", "task", "horizon"]
    paired = d0.merge(s2, on=keys, suffixes=("_d0", "_s2"), validate="one_to_one")
    valid = paired["valid_d0"] & paired["valid_s2"]
    paired["auc_delta"] = paired["roc_auc_s2"] - paired["roc_auc_d0"]
    deltas = paired.loc[valid, "auc_delta"].astype(float)
    pvalue = float(wilcoxon(deltas, alternative="greater").pvalue) if len(deltas) and not np.allclose(deltas, 0.0) else 1.0
    ticker_summary = {}
    ticker_pass = True
    for ticker, part in paired.groupby("ticker", observed=True):
        part_valid = part[part["valid_d0"] & part["valid_s2"]]
        primary = part_valid[part_valid["horizon"].isin([30, 60])]
        data = {
            "valid_cells": int(len(part_valid)),
            "wins": int((part_valid["auc_delta"] > 0.0).sum()),
            "median_auc_delta": float(part_valid["auc_delta"].median()) if len(part_valid) else None,
            "median_s2_auc": float(part_valid["roc_auc_s2"].median()) if len(part_valid) else None,
            "primary_valid_cells": int(len(primary)),
            "primary_median_auc_delta": float(primary["auc_delta"].median()) if len(primary) else None,
            "primary_median_s2_auc": float(primary["roc_auc_s2"].median()) if len(primary) else None,
        }
        data["passed"] = bool(
            data["wins"] >= 9
            and data["median_auc_delta"] is not None and data["median_auc_delta"] > 0.0
            and data["median_s2_auc"] is not None and data["median_s2_auc"] >= 0.55
            and data["primary_valid_cells"] >= 6
            and data["primary_median_auc_delta"] is not None and data["primary_median_auc_delta"] > 0.0
            and data["primary_median_s2_auc"] is not None and data["primary_median_s2_auc"] >= 0.55
        )
        ticker_pass &= data["passed"]
        ticker_summary[str(ticker)] = data
    primary_cells = cells[cells["arm"].eq("S2") & cells["horizon"].isin([30, 60])]
    frequency_pass = bool(
        primary_cells["min_month_rows"].ge(18).all()
        and primary_cells["monthly_two_classes"].all()
    )
    ap_wins = int((paired.loc[valid, "average_precision_s2"] > paired.loc[valid, "average_precision_d0"]).sum())
    ll_wins = int((paired.loc[valid, "log_loss_s2"] < paired.loc[valid, "log_loss_d0"]).sum())
    aggregate_pass = bool(
        int((deltas > 0.0).sum()) >= 32
        and len(deltas) == 48
        and float(deltas.median()) >= 0.010
        and pvalue < 0.05
    )
    calibration_pass = bool(ap_wins >= 24 or ll_wins >= 24)
    passed = bool(aggregate_pass and ticker_pass and frequency_pass and calibration_pass)
    return {
        "planned_cells": 48,
        "valid_paired_cells": int(len(deltas)),
        "s2_auc_wins": int((deltas > 0.0).sum()),
        "median_auc_delta": float(deltas.median()) if len(deltas) else None,
        "wilcoxon_one_sided_p": pvalue,
        "average_precision_wins": ap_wins,
        "log_loss_wins": ll_wins,
        "aggregate_pass": aggregate_pass,
        "frequency_pass": frequency_pass,
        "calibration_pass": calibration_pass,
        "ticker_summary": ticker_summary,
        "advance_to_option_payoff": passed,
        "production_live_ready": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--walls", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--prior-ib", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--reuse-labels", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {name: Path(getattr(args, name if name != "prior_ib" else "prior_ib")) for name in EXPECTED_HASHES}
    hashes = {name: sha256_file(path) for name, path in paths.items()}
    if hashes != EXPECTED_HASHES:
        raise AssertionError(f"sealed input hash mismatch: {hashes}")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    labels_path = output_dir / "wall_physical_candidates.parquet"
    if args.reuse_labels and labels_path.exists():
        candidates = pd.read_parquet(labels_path)
        label_errors: list[str] = []
    else:
        walls = pd.read_parquet(args.walls)
        event_columns = [
            "ticker", "trade_date", "minute", "spot", "ib_range_bps",
            *[f"dist_{name}_bps" for name in CURRENT_LEVEL_SPECS],
        ]
        events = pd.read_parquet(args.events, columns=event_columns)
        prior_columns = ["ticker", "date", "time", "spot_price", *[
            f"dist_ib_{side}_D{day}" for day in range(1, 6) for side in ("high", "low")
        ]]
        prior = pd.read_parquet(args.prior_ib, columns=prior_columns)
        joined = join_causal_inputs(walls, events, prior)
        candidates = make_wall_candidates(joined)
        manifest = pd.read_csv(args.manifest, dtype={"trade_date": str})
        candidates, label_errors = add_future_labels(candidates, manifest, int(args.workers))
        candidates.to_parquet(labels_path, index=False)
    if label_errors:
        raise AssertionError(f"future label errors: {label_errors[:10]}")
    cells = evaluate_walkforward(candidates)
    summary = summarize_gate(cells)
    cells.to_csv(output_dir / "cells.csv", index=False)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    manifest_out = {
        "schema": "wall_state_physical_separability_v1",
        "input_hashes": hashes,
        "script_sha256": sha256_file(__file__),
        "candidate_rows": int(len(candidates)),
        "candidate_rows_by_ticker": candidates.groupby("ticker", observed=True).size().astype(int).to_dict(),
        "candidate_labels_sha256": sha256_file(labels_path),
        "cells_sha256": sha256_file(output_dir / "cells.csv"),
        "summary_sha256": sha256_file(output_dir / "summary.json"),
        "label_errors": label_errors,
        "production_modified": False,
        "june_2026_used": False,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest_out, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"manifest": manifest_out, "summary": summary}, indent=2, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
