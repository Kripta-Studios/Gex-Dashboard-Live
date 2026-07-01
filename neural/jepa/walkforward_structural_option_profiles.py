from __future__ import annotations

import argparse
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.search_option_structural_profiles import (  # noqa: E402
    Profile,
    build_profiles,
    metrics,
    month_list,
    normalize_candidates,
    score,
    select_profile,
)


def empty_metrics() -> dict:
    return {
        "trades": 0,
        "win_rate": float("nan"),
        "profit_factor": float("nan"),
        "pnl_dollars": 0.0,
        "return_on_risk": 0.0,
        "max_drawdown": 0.0,
        "daily_win_rate": float("nan"),
        "median_daily_pnl": float("nan"),
        "daily_max_drawdown": 0.0,
        "top5_day_share_of_total": float("nan"),
        "days_with_trades": 0,
        "long_rate": float("nan"),
        "min_month_trades": 0,
        "positive_month_rate": float("nan"),
    }


def split_prior_months(train_months: list[str], inner_val_months: int) -> tuple[list[str], list[str]]:
    val_count = max(0, int(inner_val_months))
    if val_count <= 0 or len(train_months) <= val_count:
        return list(train_months), []
    return list(train_months[:-val_count]), list(train_months[-val_count:])


def profile_row(
    profile: Profile,
    profile_score: float,
    core_metrics: dict,
    val_metrics: dict,
    train_metrics: dict,
    test_metrics: dict,
) -> dict:
    return {
        **asdict(profile),
        "name": profile.name,
        "score": float(profile_score),
        **{f"core_{k}": v for k, v in core_metrics.items()},
        **{f"inner_val_{k}": v for k, v in val_metrics.items()},
        **{f"train_{k}": v for k, v in train_metrics.items()},
        **{f"test_{k}": v for k, v in test_metrics.items()},
    }


def prepare_frame(frame: pd.DataFrame, args: argparse.Namespace) -> dict:
    delta = pd.to_numeric(frame["delta_target"], errors="coerce").to_numpy(dtype=float)
    minutes = pd.to_numeric(frame["minutes_to_close"], errors="coerce").to_numpy(dtype=float)
    feature_values = {
        feature: pd.to_numeric(frame[feature], errors="coerce").to_numpy(dtype=float)
        for feature in args.features
        if feature in frame.columns
    }
    return {
        "delta_masks": {float(d): np.isclose(delta, float(d)) for d in args.delta_targets},
        "minutes": minutes,
        "features": feature_values,
        "pnl": pd.to_numeric(frame["rule_pnl_dollars"], errors="coerce").fillna(0.0).to_numpy(dtype=float),
        "return_on_risk": pd.to_numeric(frame["rule_return_on_risk"], errors="coerce").fillna(0.0).to_numpy(dtype=float),
        "side_long": frame["side"].astype(str).str.upper().eq("LONG").to_numpy(),
        "month": frame["month"].astype(str).to_numpy(),
        "date": frame["date"].astype(str).to_numpy(),
    }


def profile_mask(prepared: dict, profile: Profile) -> np.ndarray:
    base = prepared["delta_masks"].get(float(profile.delta_target))
    if base is None:
        return np.zeros(len(prepared["pnl"]), dtype=bool)
    mask = base.copy()
    if profile.max_minutes_to_close < 9999:
        mask &= prepared["minutes"] <= float(profile.max_minutes_to_close)
    if profile.feature != "none":
        values = prepared["features"].get(profile.feature)
        if values is None:
            return np.zeros(len(prepared["pnl"]), dtype=bool)
        if profile.op == "<=":
            mask &= values <= float(profile.threshold)
        elif profile.op == ">=":
            mask &= values >= float(profile.threshold)
        else:
            raise ValueError(f"Unsupported op={profile.op}")
        mask &= np.isfinite(values)
    return mask


def metrics_from_mask(prepared: dict, mask: np.ndarray, expected_months: list[str]) -> dict:
    if not bool(mask.any()):
        return empty_metrics()
    pnl = prepared["pnl"][mask]
    wins = pnl[pnl > 0.0]
    losses = pnl[pnl < 0.0]
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    equity = np.cumsum(pnl)
    peak = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
    selected_months = prepared["month"][mask]
    selected_dates = prepared["date"][mask]
    selected_returns = prepared["return_on_risk"][mask]
    selected_long = prepared["side_long"][mask]
    unique_days, day_index = np.unique(selected_dates, return_inverse=True)
    daily_pnl = np.bincount(day_index, weights=pnl) if len(unique_days) else np.array([], dtype=float)
    daily_equity = np.cumsum(daily_pnl) if len(daily_pnl) else np.array([], dtype=float)
    daily_peak = np.maximum.accumulate(np.insert(daily_equity, 0, 0.0))[1:] if len(daily_equity) else np.array([], dtype=float)
    total_pnl = float(pnl.sum())
    top_n = min(5, len(daily_pnl))
    top5_share = (
        float(np.sort(daily_pnl)[-top_n:].sum() / total_pnl)
        if top_n > 0 and abs(total_pnl) > 1e-9
        else float("nan")
    )
    counts = {m: 0 for m in expected_months}
    sums = {m: 0.0 for m in expected_months}
    for month in expected_months:
        month_mask = selected_months == month
        counts[month] = int(month_mask.sum())
        if counts[month]:
            sums[month] = float(pnl[month_mask].sum())
    return {
        "trades": int(len(pnl)),
        "win_rate": float((pnl > 0.0).mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf"),
        "pnl_dollars": total_pnl,
        "return_on_risk": float(selected_returns.sum()),
        "max_drawdown": float((equity - peak).min()) if len(equity) else 0.0,
        "daily_win_rate": float((daily_pnl > 0.0).mean()) if len(daily_pnl) else float("nan"),
        "median_daily_pnl": float(np.median(daily_pnl)) if len(daily_pnl) else float("nan"),
        "daily_max_drawdown": float((daily_equity - daily_peak).min()) if len(daily_equity) else 0.0,
        "top5_day_share_of_total": top5_share,
        "days_with_trades": int(len(daily_pnl)),
        "long_rate": float(selected_long.mean()),
        "min_month_trades": int(min(counts.values())) if counts else 0,
        "positive_month_rate": float(np.mean([sums[m] > 0.0 for m in expected_months])) if expected_months else float("nan"),
    }


def health_score(m: dict, args: argparse.Namespace) -> float:
    base = score(
        m,
        int(args.min_month_trades),
        float(args.min_train_pf),
        float(args.min_long_rate),
        float(args.max_long_rate),
    )
    if base <= -1e17:
        return base

    wr = float(m.get("win_rate", float("nan")))
    daily_wr = float(m.get("daily_win_rate", float("nan")))
    median_daily = float(m.get("median_daily_pnl", float("nan")))
    pnl = float(m.get("pnl_dollars", 0.0))
    dd = abs(float(m.get("daily_max_drawdown", m.get("max_drawdown", 0.0))))
    top5_share = float(m.get("top5_day_share_of_total", float("nan")))

    if pnl < float(args.min_train_pnl):
        return -1e18 + pnl
    if not np.isfinite(wr) or wr < float(args.min_train_win_rate):
        return -1e18 + pnl
    if not np.isfinite(daily_wr) or daily_wr < float(args.min_train_daily_win_rate):
        return -1e18 + pnl
    if not np.isfinite(median_daily) or median_daily < float(args.min_train_median_daily_pnl):
        return -1e18 + pnl
    if (
        np.isfinite(top5_share)
        and float(args.max_train_top5_day_share) > 0.0
        and top5_share > float(args.max_train_top5_day_share)
    ):
        return -1e18 + pnl
    if pnl > 0.0 and float(args.max_train_daily_drawdown_to_pnl) > 0.0 and dd / pnl > float(args.max_train_daily_drawdown_to_pnl):
        return -1e18 + pnl

    return (
        base
        + 6.0 * max(0.0, wr - float(args.min_train_win_rate))
        + 4.0 * max(0.0, daily_wr - float(args.min_train_daily_win_rate))
        + median_daily / 50_000.0
        - (top5_share if np.isfinite(top5_share) and pnl > 0.0 else 0.0)
    )


def evaluate_profile_fast(
    train_prepared: dict,
    core_prepared: dict,
    val_prepared: dict,
    test_prepared: dict,
    profile: Profile,
    train_months: list[str],
    core_months: list[str],
    val_months: list[str],
    test_month: str,
    args: argparse.Namespace,
) -> dict:
    train_metrics = metrics_from_mask(train_prepared, profile_mask(train_prepared, profile), train_months)
    train_score = health_score(train_metrics, args)

    core_metrics = metrics_from_mask(core_prepared, profile_mask(core_prepared, profile), core_months)
    core_score = health_score(core_metrics, args)

    if val_months:
        val_metrics = metrics_from_mask(val_prepared, profile_mask(val_prepared, profile), val_months)
        val_score = health_score(val_metrics, args)
        profile_score = min(core_score, val_score) + float(args.train_score_weight) * train_score
    else:
        val_metrics = empty_metrics()
        profile_score = train_score

    test_metrics = metrics_from_mask(test_prepared, profile_mask(test_prepared, profile), [test_month])
    return profile_row(profile, profile_score, core_metrics, val_metrics, train_metrics, test_metrics)


def evaluate_profile(
    train: pd.DataFrame,
    core: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
    profile: Profile,
    train_months: list[str],
    core_months: list[str],
    val_months: list[str],
    test_month: str,
    args: argparse.Namespace,
) -> dict:
    train_trades = select_profile(train, profile)
    train_metrics = metrics(train_trades, train_months)
    train_score = health_score(train_metrics, args)

    core_metrics = metrics(select_profile(core, profile), core_months)
    core_score = health_score(core_metrics, args)

    if val_months:
        val_metrics = metrics(select_profile(val, profile), val_months)
        val_score = health_score(val_metrics, args)
        profile_score = min(core_score, val_score) + float(args.train_score_weight) * train_score
    else:
        val_metrics = empty_metrics()
        profile_score = train_score

    test_metrics = metrics(select_profile(test, profile), [test_month])
    return profile_row(profile, profile_score, core_metrics, val_metrics, train_metrics, test_metrics)


def clone_args_with_features(args: argparse.Namespace, features: list[str]) -> argparse.Namespace:
    cloned = vars(args).copy()
    cloned["features"] = list(features)
    return Namespace(**cloned)


def prescreen_features(
    profile_source: pd.DataFrame,
    core_prepared: dict,
    ticker: str,
    core_months: list[str],
    args: argparse.Namespace,
) -> list[dict]:
    rows: list[dict] = []
    for feature in args.features:
        if feature not in profile_source.columns:
            continue
        feature_args = clone_args_with_features(args, [feature])
        best_score = -float("inf")
        best_metrics = empty_metrics()
        best_profile = ""
        for profile in build_profiles(profile_source, ticker, feature_args):
            if profile.feature == "none":
                continue
            core_metrics = metrics_from_mask(core_prepared, profile_mask(core_prepared, profile), core_months)
            core_score = health_score(core_metrics, args)
            if core_score > best_score:
                best_score = float(core_score)
                best_metrics = core_metrics
                best_profile = profile.name
        if best_profile:
            rows.append(
                {
                    "feature": feature,
                    "prescreen_score": float(best_score),
                    "prescreen_best_profile": best_profile,
                    **{f"prescreen_core_{k}": v for k, v in best_metrics.items()},
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            float(row.get("prescreen_score", -float("inf"))),
            float(row.get("prescreen_core_profit_factor", 0.0)),
            float(row.get("prescreen_core_pnl_dollars", 0.0)),
        ),
        reverse=True,
    )


def choose_profile(rows: pd.DataFrame, args: argparse.Namespace) -> pd.Series | None:
    if rows.empty:
        return None
    ranked = rows.sort_values(["score", "train_profit_factor", "train_pnl_dollars"], ascending=False).reset_index(drop=True)
    best = ranked.iloc[0]
    if not bool(args.allow_invalid_val_deploy) and float(best["score"]) <= -1e17:
        return None
    return best


def run_fold(
    candidates: pd.DataFrame,
    ticker: str,
    test_month: str,
    all_months: list[str],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    ticker = ticker.upper()
    train_months = [m for m in all_months if str(args.train_start_month) <= m < test_month]
    if len(train_months) < int(args.min_train_months):
        fold_row = {
            "ticker": ticker,
            "test_month": test_month,
            "status": "SKIP_NOT_ENOUGH_TRAIN_MONTHS",
            "train_months": ",".join(train_months),
            "core_months": "",
            "inner_val_months": "",
            "selected_profile": "",
            "score": float("nan"),
            **{f"test_{k}": v for k, v in empty_metrics().items()},
        }
        return pd.DataFrame(), pd.DataFrame(), fold_row

    core_months, val_months = split_prior_months(train_months, int(args.inner_val_months))
    tdf = candidates[candidates["ticker"].eq(ticker)].copy()
    train = tdf[tdf["month"].isin(train_months)].copy()
    core = tdf[tdf["month"].isin(core_months)].copy()
    val = tdf[tdf["month"].isin(val_months)].copy()
    test = tdf[tdf["month"].eq(test_month)].copy()
    if train.empty or core.empty or test.empty:
        fold_row = {
            "ticker": ticker,
            "test_month": test_month,
            "status": "SKIP_EMPTY_FRAME",
            "train_months": ",".join(train_months),
            "core_months": ",".join(core_months),
            "inner_val_months": ",".join(val_months),
            "selected_profile": "",
            "score": float("nan"),
            **{f"test_{k}": v for k, v in empty_metrics().items()},
        }
        return pd.DataFrame(), pd.DataFrame(), fold_row

    train_prepared = prepare_frame(train, args)
    core_prepared = prepare_frame(core, args)
    val_prepared = prepare_frame(val, args)
    test_prepared = prepare_frame(test, args)
    profile_source = core if val_months and str(args.threshold_source) == "core" else train
    selected_features = list(args.features)
    prescreen_rows: list[dict] = []
    if int(args.prescreen_top_features) > 0 and len(selected_features) > int(args.prescreen_top_features):
        prescreen_rows = prescreen_features(profile_source, core_prepared, ticker, core_months, args)
        selected_features = [row["feature"] for row in prescreen_rows[: int(args.prescreen_top_features)]]
        if not selected_features:
            selected_features = list(args.features[: int(args.prescreen_top_features)])
    fold_args = clone_args_with_features(args, selected_features)
    profiles = build_profiles(profile_source, ticker, fold_args)
    if selected_features != list(args.features):
        train_prepared = prepare_frame(train, fold_args)
        core_prepared = prepare_frame(core, fold_args)
        val_prepared = prepare_frame(val, fold_args)
        test_prepared = prepare_frame(test, fold_args)
    rows = [
        evaluate_profile_fast(
            train_prepared,
            core_prepared,
            val_prepared,
            test_prepared,
            profile,
            train_months,
            core_months,
            val_months,
            test_month,
            fold_args,
        )
        for profile in profiles
    ]
    profile_rows = pd.DataFrame(rows)
    best = choose_profile(profile_rows, args)
    if best is None:
        fold_row = {
            "ticker": ticker,
            "test_month": test_month,
            "status": "ABSTAIN_INVALID_PRIOR_SELECTION",
            "train_months": ",".join(train_months),
            "core_months": ",".join(core_months),
            "inner_val_months": ",".join(val_months),
            "selected_profile": "",
            "score": float(profile_rows["score"].max()) if not profile_rows.empty else float("nan"),
            "prescreen_features": ",".join(selected_features),
            **{f"test_{k}": v for k, v in empty_metrics().items()},
        }
        if prescreen_rows and bool(args.write_prescreen_ranking):
            fold_row["prescreen_ranking"] = prescreen_rows[: min(25, len(prescreen_rows))]
        return profile_rows, pd.DataFrame(), fold_row

    selected_profile = Profile(
        ticker=str(best["ticker"]),
        delta_target=float(best["delta_target"]),
        max_minutes_to_close=float(best["max_minutes_to_close"]),
        feature=str(best["feature"]),
        op=str(best["op"]),
        threshold=float(best["threshold"]) if pd.notna(best["threshold"]) else float("nan"),
    )
    trades = select_profile(test, selected_profile)
    if not trades.empty:
        trades["fold_month"] = test_month
        trades["selected_profile"] = selected_profile.name
        trades["profile_score"] = float(best["score"])
        trades["profile_train_months"] = ",".join(train_months)
        trades["profile_inner_val_months"] = ",".join(val_months)
        trades["profile_prescreen_features"] = ",".join(selected_features)

    test_metrics = metrics(trades, [test_month])
    fold_row = {
        "ticker": ticker,
        "test_month": test_month,
        "status": "DEPLOYED",
        "train_months": ",".join(train_months),
        "core_months": ",".join(core_months),
        "inner_val_months": ",".join(val_months),
        "selected_profile": selected_profile.name,
        "score": float(best["score"]),
        "prescreen_features": ",".join(selected_features),
        "train_profit_factor": float(best["train_profit_factor"]),
        "inner_val_profit_factor": float(best["inner_val_profit_factor"]),
        "core_profit_factor": float(best["core_profit_factor"]),
        **{f"test_{k}": v for k, v in test_metrics.items()},
    }
    if prescreen_rows and bool(args.write_prescreen_ranking):
        fold_row["prescreen_ranking"] = prescreen_rows[: min(25, len(prescreen_rows))]
    return profile_rows, trades, fold_row


def requirement_summary(overall: dict, per_ticker: dict[str, dict], args: argparse.Namespace) -> dict:
    checks: dict[str, dict] = {}
    for ticker in [t.upper() for t in args.tickers]:
        item = per_ticker.get(ticker, empty_metrics())
        pf = float(item.get("profit_factor", 0.0))
        pnl = float(item.get("pnl_dollars", 0.0))
        wr = float(item.get("win_rate", float("nan")))
        daily_wr = float(item.get("daily_win_rate", float("nan")))
        median_daily = float(item.get("median_daily_pnl", float("nan")))
        daily_dd = abs(float(item.get("daily_max_drawdown", item.get("max_drawdown", 0.0))))
        top5_share = float(item.get("top5_day_share_of_total", float("nan")))
        long_rate = float(item.get("long_rate", float("nan")))
        checks[ticker] = {
            "profitable": bool(pnl > float(args.min_test_pnl) and np.isfinite(pf) and pf >= float(args.min_test_pf)),
            "win_rate_ok": bool(np.isfinite(wr) and wr >= float(args.min_test_win_rate)),
            "daily_win_rate_ok": bool(np.isfinite(daily_wr) and daily_wr >= float(args.min_test_daily_win_rate)),
            "median_daily_ok": bool(np.isfinite(median_daily) and median_daily >= float(args.min_test_median_daily_pnl)),
            "top5_concentration_ok": bool(
                not np.isfinite(top5_share)
                or float(args.max_test_top5_day_share) <= 0.0
                or top5_share <= float(args.max_test_top5_day_share)
            ),
            "drawdown_to_pnl_ok": bool(
                pnl > 0.0
                and (
                    float(args.max_test_daily_drawdown_to_pnl) <= 0.0
                    or daily_dd / pnl <= float(args.max_test_daily_drawdown_to_pnl)
                )
            ),
            "volume_ok": bool(int(item.get("min_month_trades", 0)) >= int(args.min_test_month_trades)),
            "both_sides_ok": bool(
                np.isfinite(long_rate)
                and long_rate >= float(args.min_test_long_rate)
                and long_rate <= float(args.max_test_long_rate)
            ),
            "metrics": item,
        }
        checks[ticker]["passed"] = bool(
            checks[ticker]["profitable"]
            and checks[ticker]["win_rate_ok"]
            and checks[ticker]["daily_win_rate_ok"]
            and checks[ticker]["median_daily_ok"]
            and checks[ticker]["top5_concentration_ok"]
            and checks[ticker]["drawdown_to_pnl_ok"]
            and checks[ticker]["volume_ok"]
            and checks[ticker]["both_sides_ok"]
        )
    return {
        "overall": overall,
        "per_ticker": checks,
        "all_tickers_passed": bool(all(item["passed"] for item in checks.values())),
    }


def parse_months(value: object) -> list[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def integrity_summary(
    fold_rows: list[dict],
    selected: pd.DataFrame,
    test_months: list[str],
    tickers: list[str],
) -> dict:
    issues: list[str] = []
    expected_months = set(test_months)
    expected_tickers = {ticker.upper() for ticker in tickers}

    for row in fold_rows:
        ticker = str(row.get("ticker", "")).upper()
        test_month = str(row.get("test_month", ""))
        train_months = parse_months(row.get("train_months", ""))
        core_months = parse_months(row.get("core_months", ""))
        val_months = parse_months(row.get("inner_val_months", ""))

        if ticker not in expected_tickers:
            issues.append(f"{ticker} {test_month}: unexpected ticker")
        if test_month not in expected_months:
            issues.append(f"{ticker} {test_month}: unexpected test_month")

        for name, months in {
            "train_months": train_months,
            "core_months": core_months,
            "inner_val_months": val_months,
        }.items():
            non_prior = [month for month in months if month >= test_month]
            if non_prior:
                issues.append(f"{ticker} {test_month}: {name} contains non-prior months {non_prior}")

        if set(core_months) & set(val_months):
            issues.append(f"{ticker} {test_month}: core/inner_val overlap")
        if core_months or val_months:
            if not set(core_months).issubset(set(train_months)) or not set(val_months).issubset(set(train_months)):
                issues.append(f"{ticker} {test_month}: core/inner_val is not subset of train")
            if sorted(core_months + val_months) != sorted(train_months):
                issues.append(f"{ticker} {test_month}: core + inner_val does not reconstruct train")

    selected_rows = int(len(selected)) if selected is not None else 0
    if selected is not None and not selected.empty:
        required_cols = {"ticker", "month", "fold_month", "profile_train_months", "profile_inner_val_months"}
        missing = sorted(required_cols.difference(selected.columns))
        if missing:
            issues.append(f"selected_trades missing columns {missing}")
        else:
            for idx, row in selected.iterrows():
                ticker = str(row.get("ticker", "")).upper()
                month = str(row.get("month", ""))
                fold_month = str(row.get("fold_month", ""))
                train_months = parse_months(row.get("profile_train_months", ""))
                val_months = parse_months(row.get("profile_inner_val_months", ""))

                if ticker not in expected_tickers:
                    issues.append(f"selected row {idx}: unexpected ticker {ticker}")
                if fold_month not in expected_months:
                    issues.append(f"selected row {idx}: unexpected fold_month {fold_month}")
                if month != fold_month:
                    issues.append(f"selected row {idx}: trade month {month} != fold_month {fold_month}")
                non_prior = [prior for prior in train_months + val_months if prior >= fold_month]
                if non_prior:
                    issues.append(f"selected row {idx}: profile prior months contain {non_prior}")
                if len(issues) >= 25:
                    break

    return {
        "passed": bool(not issues),
        "folds_checked": int(len(fold_rows)),
        "selected_rows_checked": selected_rows,
        "issues": issues[:25],
    }


def fold_key(ticker: str, test_month: str) -> str:
    return f"{ticker.upper()}_{test_month}"


def fold_paths(out_dir: Path, ticker: str, test_month: str) -> tuple[Path, Path, Path]:
    fold_dir = out_dir / "folds"
    key = fold_key(ticker, test_month)
    return (
        fold_dir / f"{key}_config.json",
        fold_dir / f"{key}_trades.csv",
        fold_dir / f"{key}_profile_candidates.csv",
    )


def load_fold_checkpoint(out_dir: Path, ticker: str, test_month: str) -> tuple[pd.DataFrame, pd.DataFrame, dict] | None:
    config_path, trades_path, profile_path = fold_paths(out_dir, ticker, test_month)
    if not config_path.exists():
        return None
    fold_row = json.loads(config_path.read_text(encoding="utf-8"))
    trades = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()
    profile_rows = pd.read_csv(profile_path) if profile_path.exists() else pd.DataFrame()
    return profile_rows, trades, fold_row


def save_fold_checkpoint(
    out_dir: Path,
    ticker: str,
    test_month: str,
    profile_rows: pd.DataFrame,
    trades: pd.DataFrame,
    fold_row: dict,
    write_profile_candidates: bool,
) -> None:
    config_path, trades_path, profile_path = fold_paths(out_dir, ticker, test_month)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(fold_row, indent=2, allow_nan=True), encoding="utf-8")
    if trades.empty:
        if trades_path.exists():
            trades_path.unlink()
    else:
        trades.to_csv(trades_path, index=False)
    if write_profile_candidates and not profile_rows.empty:
        profile_rows.to_csv(profile_path, index=False)


def write_summary(out_dir: Path, args: argparse.Namespace, summary: dict) -> None:
    lines = [
        "# Nested Walk-Forward Structural Option Profiles",
        "",
        "For each ticker and test month, profiles are generated from prior months only. "
        "If inner validation is enabled, deployment is blocked unless the selected profile passes prior validation constraints.",
        "",
        f"Candidate labels: `{args.candidate_labels}`",
        f"Test months: `{args.start_month}`..`{args.end_month}`",
        f"Threshold source: `{args.threshold_source}`",
        f"Min train months: `{args.min_train_months}`",
        f"Inner validation months: `{args.inner_val_months}`",
        f"Min test PF: `{args.min_test_pf}`",
        f"Min test WR: `{args.min_test_win_rate}`",
        f"Min test daily WR: `{args.min_test_daily_win_rate}`",
        f"Min test median daily PnL: `{args.min_test_median_daily_pnl}`",
        "",
        "## Requirement Check",
        "",
        "| Ticker | Passed | Trades | WR | PF | PnL | Daily WR | Median Day | Daily DD | Top5 Share | Min Month Trades | Long Rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for ticker, item in summary["requirements"]["per_ticker"].items():
        m = item["metrics"]
        wr = float(m.get("win_rate", float("nan")))
        pf = float(m.get("profit_factor", float("nan")))
        pnl = float(m.get("pnl_dollars", 0.0))
        long_rate = float(m.get("long_rate", float("nan")))
        daily_wr = float(m.get("daily_win_rate", float("nan")))
        median_daily = float(m.get("median_daily_pnl", float("nan")))
        daily_dd = float(m.get("daily_max_drawdown", m.get("max_drawdown", 0.0)))
        top5_share = float(m.get("top5_day_share_of_total", float("nan")))
        lines.append(
            f"| {ticker} | {item['passed']} | {int(m.get('trades', 0))} | "
            f"{wr:.1%} | {pf:.3f} | {pnl:,.0f} | {daily_wr:.1%} | "
            f"{median_daily:,.0f} | {daily_dd:,.0f} | {top5_share:.2f} | "
            f"{int(m.get('min_month_trades', 0))} | {long_rate:.1%} |"
        )
    m = summary["overall"]
    lines += [
        "",
        "## Overall",
        "",
        f"- Trades: {int(m.get('trades', 0))}",
        f"- Win rate: {float(m.get('win_rate', float('nan'))):.1%}",
        f"- Profit factor: {float(m.get('profit_factor', float('nan'))):.3f}",
        f"- PnL: {float(m.get('pnl_dollars', 0.0)):,.0f}",
        f"- Min monthly trades: {int(m.get('min_month_trades', 0))}",
        f"- Daily win rate: {float(m.get('daily_win_rate', float('nan'))):.1%}",
        f"- Median daily PnL: {float(m.get('median_daily_pnl', float('nan'))):,.0f}",
        f"- Daily max drawdown: {float(m.get('daily_max_drawdown', m.get('max_drawdown', 0.0))):,.0f}",
        f"- Top 5 day share of total PnL: {float(m.get('top5_day_share_of_total', float('nan'))):.2f}",
        "",
        "## Walk-Forward Integrity",
        "",
        f"- Passed: {bool(summary.get('integrity', {}).get('passed', False))}",
        f"- Folds checked: {int(summary.get('integrity', {}).get('folds_checked', 0))}",
        f"- Selected rows checked: {int(summary.get('integrity', {}).get('selected_rows_checked', 0))}",
    ]
    issues = summary.get("integrity", {}).get("issues", [])
    if issues:
        lines += [
            "- Issues:",
            *[f"  - {issue}" for issue in issues],
        ]
    lines += [
        "",
        "## JSON",
        "",
        "```json",
        json.dumps(summary, indent=2, allow_nan=True),
        "```",
        "",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Nested walk-forward structural option-profile selector.")
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--train-start-month", default="202507")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument(
        "--exclude-months",
        nargs="*",
        default=[],
        help="YYYYMM months to exclude from train, fold, and requirement windows.",
    )
    parser.add_argument("--min-train-months", type=int, default=6)
    parser.add_argument("--inner-val-months", type=int, default=3)
    parser.add_argument("--threshold-source", choices=["core", "train"], default="core")
    parser.add_argument("--allow-invalid-val-deploy", action="store_true")
    parser.add_argument("--delta-targets", nargs="+", type=float, default=[0.40, 0.50, 0.60, 0.70])
    parser.add_argument("--max-minutes-to-close", nargs="+", type=float, default=[60, 90, 120, 140, 180, 9999])
    parser.add_argument("--features", nargs="+", default=[
        "level_target_bps",
        "net_delta",
        "vix_spot",
        "actual_iv",
        "actual_theta",
        "entry_spread_pct",
        "premium_to_spot_bps",
        "rsi",
        "net_gamma",
        "wk_net_delta",
        "gamma_0dte_vs_wk",
        "delta_0dte_vs_wk",
        "dist_to_min_gamma",
        "dist_to_max_gamma",
        "dist_to_zero_gamma",
    ])
    parser.add_argument("--prescreen-top-features", type=int, default=0)
    parser.add_argument("--write-prescreen-ranking", action="store_true")
    parser.add_argument("--quantiles", nargs="+", type=float, default=[0.15, 0.25, 0.35, 0.50, 0.65, 0.75, 0.85])
    parser.add_argument("--min-month-trades", type=int, default=15)
    parser.add_argument("--min-train-pf", type=float, default=1.05)
    parser.add_argument("--min-train-pnl", type=float, default=-1e18)
    parser.add_argument("--min-train-win-rate", type=float, default=0.0)
    parser.add_argument("--min-train-daily-win-rate", type=float, default=0.0)
    parser.add_argument("--min-train-median-daily-pnl", type=float, default=-1e18)
    parser.add_argument("--max-train-top5-day-share", type=float, default=0.0)
    parser.add_argument("--max-train-daily-drawdown-to-pnl", type=float, default=0.0)
    parser.add_argument("--train-score-weight", type=float, default=0.15)
    parser.add_argument("--min-long-rate", type=float, default=0.20)
    parser.add_argument("--max-long-rate", type=float, default=0.80)
    parser.add_argument("--min-test-pf", type=float, default=1.0)
    parser.add_argument("--min-test-pnl", type=float, default=0.0)
    parser.add_argument("--min-test-win-rate", type=float, default=0.0)
    parser.add_argument("--min-test-daily-win-rate", type=float, default=0.0)
    parser.add_argument("--min-test-median-daily-pnl", type=float, default=-1e18)
    parser.add_argument("--max-test-top5-day-share", type=float, default=0.0)
    parser.add_argument("--max-test-daily-drawdown-to-pnl", type=float, default=0.0)
    parser.add_argument("--min-test-month-trades", type=int, default=15)
    parser.add_argument("--min-test-long-rate", type=float, default=0.20)
    parser.add_argument("--max-test-long-rate", type=float, default=0.80)
    parser.add_argument("--write-profile-candidates", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Reuse completed per-fold checkpoints in output-dir/folds.")
    parser.add_argument("--workers", type=int, default=1, help="Parallel fold workers using threads.")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates = normalize_candidates(Path(args.candidate_labels), [t.upper() for t in args.tickers])
    excluded_months = {str(month)[:6] for month in args.exclude_months}
    if excluded_months:
        candidates = candidates[~candidates["month"].astype(str).isin(excluded_months)].copy()
    test_months = [m for m in month_list(args.start_month, args.end_month) if m not in excluded_months]
    all_months = [m for m in sorted(candidates["month"].astype(str).unique().tolist()) if m not in excluded_months]

    def run_or_load(task: tuple[str, str]) -> tuple[str, str, pd.DataFrame, pd.DataFrame, dict]:
        ticker, test_month = task
        if bool(args.resume):
            checkpoint = load_fold_checkpoint(out_dir, ticker, test_month)
            if checkpoint is not None:
                profile_rows, trades, fold_row = checkpoint
                fold_row["checkpoint_reused"] = True
                return ticker, test_month, profile_rows, trades, fold_row
        profile_rows, trades, fold_row = run_fold(candidates, ticker, test_month, all_months, args)
        save_fold_checkpoint(
            out_dir,
            ticker,
            test_month,
            profile_rows,
            trades,
            fold_row,
            bool(args.write_profile_candidates),
        )
        return ticker, test_month, profile_rows, trades, fold_row

    tasks = [(ticker, test_month) for test_month in test_months for ticker in [t.upper() for t in args.tickers]]
    results: list[tuple[str, str, pd.DataFrame, pd.DataFrame, dict]] = []
    if int(args.workers) > 1:
        with ThreadPoolExecutor(max_workers=int(args.workers)) as executor:
            futures = [executor.submit(run_or_load, task) for task in tasks]
            for future in as_completed(futures):
                results.append(future.result())
    else:
        for task in tasks:
            results.append(run_or_load(task))

    order = {task: idx for idx, task in enumerate(tasks)}
    results.sort(key=lambda item: order[(item[0], item[1])])

    profile_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    for ticker, test_month, profile_rows, trades, fold_row in results:
        if not profile_rows.empty:
            profile_rows["fold_month"] = test_month
            profile_rows["fold_ticker"] = ticker
            if bool(args.write_profile_candidates):
                profile_frames.append(profile_rows)
        if not trades.empty:
            trade_frames.append(trades)
        fold_rows.append(fold_row)
        reused = " reused" if bool(fold_row.get("checkpoint_reused", False)) else ""
        print(
            f"[NESTED_STRUCT] {ticker} {test_month} {fold_row['status']}{reused} "
            f"profile={fold_row.get('selected_profile', '')} "
            f"pf={float(fold_row.get('test_profit_factor', float('nan'))):.3f} "
            f"pnl={float(fold_row.get('test_pnl_dollars', 0.0)):.0f} "
            f"trades={int(fold_row.get('test_trades', 0))}",
            flush=True,
        )

    selected = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    if not selected.empty:
        selected = selected.sort_values(["date", "time", "ticker", "candidate_id"]).reset_index(drop=True)
        selected.to_csv(out_dir / "selected_trades.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(out_dir / "fold_configs.csv", index=False)
    if profile_frames:
        pd.concat(profile_frames, ignore_index=True).to_csv(out_dir / "profile_candidates.csv", index=False)

    overall = metrics(selected, test_months)
    per_ticker = {
        ticker: metrics(selected[selected["ticker"].eq(ticker)].copy(), test_months) if not selected.empty else empty_metrics()
        for ticker in [t.upper() for t in args.tickers]
    }
    summary = {
        "args": vars(args),
        "folds": fold_rows,
        "overall": overall,
        "per_ticker": per_ticker,
    }
    summary["requirements"] = requirement_summary(overall, per_ticker, args)
    summary["integrity"] = integrity_summary(fold_rows, selected, test_months, [t.upper() for t in args.tickers])
    (out_dir / "metrics.json").write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")
    write_summary(out_dir, args, summary)
    print((out_dir / "SUMMARY.md").read_text(encoding="utf-8"), flush=True)
    return 0 if summary["requirements"]["all_tickers_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
