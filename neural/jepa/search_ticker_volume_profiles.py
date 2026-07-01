"""
Grid-search ticker-level GBT alert profiles with strict walk-forward inference.

The target for this research pass is stricter than the previous high-precision
profile: each ticker must be independently profitable and generate at least a
minimum number of trades per evaluated month.
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import torch


warnings.filterwarnings(
    "ignore",
    message="X does not have valid feature names",
    category=UserWarning,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backtest"))
sys.path.insert(0, str(PROJECT_ROOT / "neural"))

from backtest_gbt_parquet import (  # noqa: E402
    FEATURE_COLUMNS,
    TradeSimulator,
    calculate_metrics,
    get_device,
    get_independent_signals,
    load_ensemble_model,
)


_ORIGINAL_LOAD_OHLC_DATA = TradeSimulator.load_ohlc_data


@lru_cache(maxsize=20000)
def _cached_ohlc_data(ticker: str, date: str):
    scratch = TradeSimulator()
    scratch._ohlc_data_cache = {}
    return _ORIGINAL_LOAD_OHLC_DATA(scratch, ticker, date)


def _patched_load_ohlc_data(self, ticker, date):
    return _cached_ohlc_data(str(ticker), str(date))


TradeSimulator.load_ohlc_data = _patched_load_ohlc_data


@dataclass(frozen=True)
class Profile:
    ticker: str
    threshold: float
    side_mode: str
    target: float
    stop: float
    cooldown: int
    min_entry_minute: int
    min_short_entry_minute: int | None
    max_time: int


def fmt_pct(x: float) -> str:
    if not np.isfinite(x):
        return "nan"
    return f"{100.0 * x:.1f}%"


def ensure_date(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = out["date"].astype(str).str.replace("-", "", regex=False)
    out["month"] = out["date"].str.slice(0, 6)
    return out


def load_frame(path: Path, start_date: str, end_date: str, tickers: list[str]) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    df = ensure_date(df)
    df = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy()
    if tickers:
        df = df[df["ticker"].isin(tickers)].copy()
    if df.empty:
        raise RuntimeError(f"No rows found for {start_date}..{end_date} tickers={tickers}")
    return df.reset_index(drop=True)


def load_ticker_models(model_path: Path, normalizer_path: Path, model_size: str, device) -> tuple[dict, dict]:
    model_path_str = str(model_path)
    normalizer_path_str = str(normalizer_path)
    if model_path_str.endswith(".joblib") and not model_path_str.endswith("_history.joblib"):
        model_path_str = model_path_str.replace(".joblib", "_history.joblib")

    models: dict[str, object] = {}
    normalizers: dict[str, object] = {}
    for ticker in ["SPX", "QQQ", "SPY"]:
        if "_history.joblib" in model_path_str:
            t_model = Path(model_path_str.replace("_history.joblib", f"_{ticker}_history.joblib"))
        else:
            t_model = Path(model_path_str.replace(".joblib", f"_{ticker}.joblib"))
        t_norm = Path(normalizer_path_str.replace(".npz", f"_{ticker}.npz"))
        if not t_model.exists():
            continue
        model, normalizer = load_ensemble_model(str(t_model), str(t_norm), model_size, device)
        models[ticker] = model
        normalizers[ticker] = normalizer
    if not models:
        model, normalizer = load_ensemble_model(model_path_str, normalizer_path_str, model_size, device)
        models["ALL"] = model
        normalizers["ALL"] = normalizer
    return models, normalizers


def build_features(df: pd.DataFrame, normalizer) -> np.ndarray:
    cols = getattr(normalizer, "feature_names", None)
    expected_cols = cols if cols is not None and len(cols) > 0 else FEATURE_COLUMNS
    features = np.zeros((len(df), len(expected_cols)), dtype=np.float32)
    for i, col in enumerate(expected_cols):
        if col in df.columns:
            features[:, i] = df[col].values.astype(np.float32)
    return np.nan_to_num(features, nan=0.0, posinf=5.0, neginf=-5.0)


def strict_wf_probabilities(df: pd.DataFrame, models: dict, normalizers: dict) -> np.ndarray:
    probs = np.zeros((len(df), 3), dtype=np.float32)
    ticker_specific = "ALL" not in models
    if ticker_specific:
        feature_by_ticker = {
            ticker: build_features(df, normalizers[ticker])
            for ticker in models
        }
        for date in sorted(df["date"].unique()):
            date_mask = df["date"] == date
            for ticker, model in models.items():
                mask = date_mask & (df["ticker"] == ticker)
                idx = np.where(mask.to_numpy())[0]
                if len(idx) == 0:
                    continue
                probs[idx] = model.predict_proba(feature_by_ticker[ticker][idx], date=date)
    else:
        features = build_features(df, normalizers["ALL"])
        model = models["ALL"]
        for date in sorted(df["date"].unique()):
            idx = np.where((df["date"] == date).to_numpy())[0]
            if len(idx) == 0:
                continue
            probs[idx] = model.predict_proba(features[idx], date=date)
    return probs


def predictions_for_side(probs: np.ndarray, threshold: float, side_mode: str) -> np.ndarray:
    preds, _ = get_independent_signals(probs, base_confidence=threshold)
    out = preds.copy()
    if side_mode == "long":
        out[out == 0] = 1
    elif side_mode == "short":
        out[out == 2] = 1
    elif side_mode != "both":
        raise ValueError(f"Unknown side_mode={side_mode}")
    return out


def monthly_stats(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    work = trades.copy()
    work["month"] = work["date"].astype(str).str.slice(0, 6)
    rows = []
    for month, g in work.groupby("month"):
        m = calculate_metrics(g)
        if "error" in m:
            continue
        rows.append({
            "month": month,
            "trades": int(m["total_trades"]),
            "win_rate": float(m["win_rate"]) / 100.0,
            "profit_factor": float(m["profit_factor"]),
            "pnl": float(m["total_pnl"]),
        })
    return pd.DataFrame(rows)


def score_profile(metrics: dict, month_df: pd.DataFrame, min_trades_per_month: int) -> float:
    if "error" in metrics or month_df.empty:
        return -1e9
    wr = float(metrics["win_rate"]) / 100.0
    pf = float(metrics["profit_factor"])
    trades = float(metrics["total_trades"])
    min_month = float(month_df["trades"].min())
    median_month = float(month_df["trades"].median())
    bad_months = int((month_df["trades"] < min_trades_per_month).sum())
    score = 0.0
    score += 40.0 * max(0.0, wr - 0.50)
    score += 8.0 * np.log(max(pf, 0.05))
    score += 0.015 * trades
    score += 0.25 * median_month
    score -= 6.0 * max(0.0, min_trades_per_month - min_month)
    score -= 12.0 * bad_months
    if wr < 0.65:
        score -= 35.0 * (0.65 - wr)
    if pf < 1.30:
        score -= 12.0 * (1.30 - pf)
    return float(score)


def simulate_profile(df: pd.DataFrame, probs: np.ndarray, profile: Profile) -> pd.DataFrame:
    ticker_df = df[df["ticker"] == profile.ticker].copy()
    ticker_probs = probs[ticker_df.index.to_numpy()]
    preds = predictions_for_side(ticker_probs, profile.threshold, profile.side_mode)
    sim = TradeSimulator(
        threshold=profile.threshold,
        cooldown_minutes=profile.cooldown,
        target_long=profile.target,
        target_short=profile.target,
        stop_pct=profile.stop,
        max_time=profile.max_time,
        risk_capital=1000.0,
        min_entry_minute=profile.min_entry_minute,
        min_short_entry_minute=profile.min_short_entry_minute,
        spx_target=profile.target,
        etf_target=profile.target,
        spx_stop=profile.stop,
        etf_stop=profile.stop,
        qqq_target=profile.target,
        spy_target=profile.target,
        qqq_stop=profile.stop,
        spy_stop=profile.stop,
    )
    return sim.simulate(ticker_df.reset_index(drop=True), preds, ticker_probs)


def search_ticker(df: pd.DataFrame, probs: np.ndarray, ticker: str, args) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    rows = []
    monthly_by_key: dict[str, pd.DataFrame] = {}
    thresholds = [float(x) for x in args.thresholds]
    targets = [float(x) for x in args.targets]
    stops = [float(x) for x in args.stops]
    cooldowns = [int(x) for x in args.cooldowns]
    min_entry_minutes = [int(x) for x in args.min_entry_minutes]
    side_modes = list(args.side_modes)

    for threshold in thresholds:
        for side_mode in side_modes:
            for target in targets:
                for stop in stops:
                    for cooldown in cooldowns:
                        for min_entry in min_entry_minutes:
                            profile = Profile(
                                ticker=ticker,
                                threshold=threshold,
                                side_mode=side_mode,
                                target=target,
                                stop=stop,
                                cooldown=cooldown,
                                min_entry_minute=min_entry,
                                min_short_entry_minute=9999 if side_mode == "long" else None,
                                max_time=int(args.max_time),
                            )
                            trades = simulate_profile(df, probs, profile)
                            metrics = calculate_metrics(trades)
                            months = monthly_stats(trades)
                            key = (
                                f"{ticker}_thr{threshold:.3f}_{side_mode}_"
                                f"t{target:.4f}_s{stop:.4f}_cd{cooldown}_me{min_entry}"
                            )
                            monthly_by_key[key] = months
                            if "error" in metrics:
                                rows.append({
                                    "key": key,
                                    "ticker": ticker,
                                    "threshold": threshold,
                                    "side_mode": side_mode,
                                    "target": target,
                                    "stop": stop,
                                    "cooldown": cooldown,
                                    "min_entry_minute": min_entry,
                                    "trades": 0,
                                    "months": 0,
                                    "min_trades_month": 0,
                                    "median_trades_month": 0,
                                    "bad_months": 999,
                                    "win_rate": 0.0,
                                    "profit_factor": 0.0,
                                    "pnl": 0.0,
                                    "score": -1e9,
                                    "passes": False,
                                })
                                continue
                            min_month = int(months["trades"].min()) if not months.empty else 0
                            med_month = float(months["trades"].median()) if not months.empty else 0.0
                            bad_months = int((months["trades"] < args.min_trades_per_month).sum()) if not months.empty else 999
                            score = score_profile(metrics, months, args.min_trades_per_month)
                            wr = float(metrics["win_rate"]) / 100.0
                            pf = float(metrics["profit_factor"])
                            rows.append({
                                "key": key,
                                "ticker": ticker,
                                "threshold": threshold,
                                "side_mode": side_mode,
                                "target": target,
                                "stop": stop,
                                "cooldown": cooldown,
                                "min_entry_minute": min_entry,
                                "trades": int(metrics["total_trades"]),
                                "months": int(months["month"].nunique()) if not months.empty else 0,
                                "min_trades_month": min_month,
                                "median_trades_month": med_month,
                                "bad_months": bad_months,
                                "win_rate": wr,
                                "profit_factor": pf,
                                "pnl": float(metrics["total_pnl"]),
                                "score": score,
                                "passes": bool(
                                    wr >= args.min_win_rate
                                    and pf >= args.min_profit_factor
                                    and bad_months == 0
                                    and min_month >= args.min_trades_per_month
                                ),
                            })
    result = pd.DataFrame(rows).sort_values(["passes", "score"], ascending=[False, False])
    return result, monthly_by_key


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="training_data/training_data_spx_qqq_spy.parquet")
    parser.add_argument("--model", default="neural/models/codex_exp/gbt_candidate_top2_rec1_march2026.joblib")
    parser.add_argument("--normalizer", default="neural/models/codex_exp/gbt_candidate_top2_rec1_march2026_norm.npz")
    parser.add_argument("--model-size", default="small")
    parser.add_argument("--start-date", default="20250701")
    parser.add_argument("--end-date", default="20260605")
    parser.add_argument("--tickers", nargs="+", default=["SPX", "QQQ", "SPY"])
    parser.add_argument("--thresholds", nargs="+", type=float, default=[0.35, 0.40, 0.45, 0.50, 0.55])
    parser.add_argument("--targets", nargs="+", type=float, default=[0.0015, 0.0020, 0.0025, 0.0030, 0.0040])
    parser.add_argument("--stops", nargs="+", type=float, default=[0.0025, 0.0030, 0.0040, 0.0050])
    parser.add_argument("--cooldowns", nargs="+", type=int, default=[0, 5, 8, 15])
    parser.add_argument("--min-entry-minutes", nargs="+", type=int, default=[570, 580, 600])
    parser.add_argument("--side-modes", nargs="+", default=["long", "both"])
    parser.add_argument("--max-time", type=int, default=180)
    parser.add_argument("--min-trades-per-month", type=int, default=15)
    parser.add_argument("--min-win-rate", type=float, default=0.65)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--output-dir", default="research_papers/JEPA/results/ticker_volume_profile_search")
    parser.add_argument("--probabilities-cache", default="", help="Optional parquet with ticker/date/time/p_short/p_hold/p_long.")
    args = parser.parse_args()

    os.environ.setdefault("GBT_STRICT_MIN_VALIDATION_TRADES", "12")
    os.environ.setdefault("GBT_STRICT_MIN_AVG_PF", "1.25")
    os.environ.setdefault("GBT_STRICT_TOP_N_WINDOWS", "3")
    os.environ.setdefault("GBT_STRICT_RECENCY_POWER", "2.0")
    os.environ.setdefault("GBT_TICKER_STRICT_MIN_AVG_PF", "QQQ:1.25")
    os.environ.setdefault("GBT_TICKER_STRICT_TOP_N_WINDOWS", "QQQ:2")
    os.environ.setdefault("GBT_TICKER_STRICT_RECENCY_POWER", "QQQ:0.5")
    os.environ.setdefault("DEPLOYMENT_TICKER_MAX_VIX_SPOT", "SPY:0.4108")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_frame(Path(args.data), args.start_date, args.end_date, args.tickers)
    print(f"[data] rows={len(df):,} dates={df['date'].nunique()} months={df['month'].nunique()} tickers={sorted(df['ticker'].unique())}")
    if args.probabilities_cache:
        cache = pd.read_parquet(args.probabilities_cache)
        cache = ensure_date(cache)
        cache = cache[(cache["date"] >= args.start_date) & (cache["date"] <= args.end_date)].copy()
        if args.tickers:
            cache = cache[cache["ticker"].isin(args.tickers)].copy()
        key_cols = ["ticker", "date", "time"]
        merged = df[key_cols].merge(cache[key_cols + ["p_short", "p_hold", "p_long"]], on=key_cols, how="left")
        if merged[["p_short", "p_hold", "p_long"]].isna().any().any():
            missing = int(merged[["p_short", "p_hold", "p_long"]].isna().any(axis=1).sum())
            raise RuntimeError(f"Probability cache is missing {missing} rows")
        probs = merged[["p_short", "p_hold", "p_long"]].to_numpy(dtype=np.float32)
        print(f"[probs] loaded {args.probabilities_cache}")
    else:
        device = get_device()
        models, normalizers = load_ticker_models(Path(args.model), Path(args.normalizer), args.model_size, device)
        print(f"[model] loaded={sorted(models.keys())}")
        probs = strict_wf_probabilities(df, models, normalizers)
    prob_df = df[["ticker", "date", "time"]].copy()
    prob_df["p_short"] = probs[:, 0]
    prob_df["p_hold"] = probs[:, 1]
    prob_df["p_long"] = probs[:, 2]
    prob_path = out_dir / f"strict_probs_{args.start_date}_{args.end_date}.parquet"
    prob_df.to_parquet(prob_path, index=False)
    print(f"[probs] saved {prob_path}")

    all_results = []
    for ticker in args.tickers:
        ticker_results, monthly_by_key = search_ticker(df, probs, ticker, args)
        ticker_path = out_dir / f"grid_{ticker}_{args.start_date}_{args.end_date}.csv"
        ticker_results.to_csv(ticker_path, index=False)
        all_results.append(ticker_results)
        print(f"\n[{ticker}] top profiles")
        cols = [
            "threshold", "side_mode", "target", "stop", "cooldown", "min_entry_minute",
            "trades", "min_trades_month", "median_trades_month", "bad_months",
            "win_rate", "profit_factor", "pnl", "passes",
        ]
        print(ticker_results[cols].head(12).to_string(index=False, formatters={
            "win_rate": fmt_pct,
            "profit_factor": lambda x: f"{x:.2f}",
            "pnl": lambda x: f"{x:+.0f}",
        }))
        best_key = str(ticker_results.iloc[0]["key"])
        months = monthly_by_key.get(best_key, pd.DataFrame())
        if not months.empty:
            months.to_csv(out_dir / f"best_monthly_{ticker}_{args.start_date}_{args.end_date}.csv", index=False)
            print(f"[{ticker}] best monthly")
            print(months.to_string(index=False, formatters={
                "win_rate": fmt_pct,
                "profit_factor": lambda x: f"{x:.2f}",
                "pnl": lambda x: f"{x:+.0f}",
            }))

    combined = pd.concat(all_results, ignore_index=True)
    combined_path = out_dir / f"grid_all_{args.start_date}_{args.end_date}.csv"
    combined.to_csv(combined_path, index=False)
    passes = combined[combined["passes"]].copy()
    passes.to_csv(out_dir / f"passes_{args.start_date}_{args.end_date}.csv", index=False)
    print(f"\n[done] combined={combined_path}")
    print(f"[done] passing profiles={len(passes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
