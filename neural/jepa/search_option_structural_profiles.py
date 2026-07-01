from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Profile:
    ticker: str
    delta_target: float
    max_minutes_to_close: float
    feature: str
    op: str
    threshold: float

    @property
    def name(self) -> str:
        time_part = "alltime" if self.max_minutes_to_close >= 9999 else f"mtc_le_{self.max_minutes_to_close:.0f}"
        if self.feature == "none":
            return f"{self.ticker}_d{self.delta_target:.2f}_{time_part}_nofilter"
        thr = f"{self.threshold:.5g}".replace("-", "m").replace(".", "p")
        return f"{self.ticker}_d{self.delta_target:.2f}_{time_part}_{self.feature}_{self.op}_{thr}"


def month_list(start_month: str, end_month: str) -> list[str]:
    y = int(str(start_month)[:4])
    m = int(str(start_month)[4:6])
    end = int(str(end_month))
    out: list[str] = []
    while y * 100 + m <= end:
        out.append(f"{y:04d}{m:02d}")
        m += 1
        if m == 13:
            y += 1
            m = 1
    return out


def normalize_candidates(path: Path, tickers: list[str]) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["date"] = frame["date"].astype(str).str.replace("-", "", regex=False).str[:8]
    frame["month"] = frame["date"].str[:6]
    frame["side"] = frame["side"].astype(str).str.upper()
    frame = frame[frame["ticker"].isin([t.upper() for t in tickers])].copy()
    return frame.sort_values(["ticker", "date", "time", "signal_id", "candidate_id"]).reset_index(drop=True)


def metrics(trades: pd.DataFrame, expected_months: list[str]) -> dict:
    if trades.empty:
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
    pnl = trades["rule_pnl_dollars"].astype(float).to_numpy()
    wins = pnl[pnl > 0.0]
    losses = pnl[pnl < 0.0]
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    equity = np.cumsum(pnl)
    peak = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
    by_month = trades.groupby("month")["rule_pnl_dollars"].agg(["count", "sum"]).reindex(expected_months, fill_value=0)
    by_day = trades.groupby("date")["rule_pnl_dollars"].sum().sort_index()
    daily_pnl = by_day.astype(float).to_numpy()
    daily_equity = np.cumsum(daily_pnl) if len(daily_pnl) else np.array([], dtype=float)
    daily_peak = np.maximum.accumulate(np.insert(daily_equity, 0, 0.0))[1:] if len(daily_equity) else np.array([], dtype=float)
    total_pnl = float(pnl.sum())
    top_n = min(5, len(daily_pnl))
    top5_share = (
        float(np.sort(daily_pnl)[-top_n:].sum() / total_pnl)
        if top_n > 0 and abs(total_pnl) > 1e-9
        else float("nan")
    )
    return {
        "trades": int(len(trades)),
        "win_rate": float((pnl > 0.0).mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf"),
        "pnl_dollars": total_pnl,
        "return_on_risk": float(trades["rule_return_on_risk"].astype(float).sum()),
        "max_drawdown": float((equity - peak).min()) if len(equity) else 0.0,
        "daily_win_rate": float((daily_pnl > 0.0).mean()) if len(daily_pnl) else float("nan"),
        "median_daily_pnl": float(np.median(daily_pnl)) if len(daily_pnl) else float("nan"),
        "daily_max_drawdown": float((daily_equity - daily_peak).min()) if len(daily_equity) else 0.0,
        "top5_day_share_of_total": top5_share,
        "days_with_trades": int(len(daily_pnl)),
        "long_rate": float((trades["side"] == "LONG").mean()),
        "min_month_trades": int(by_month["count"].min()),
        "positive_month_rate": float((by_month["sum"] > 0.0).mean()),
    }


def score(m: dict, min_month_trades: int, min_pf: float, min_long_rate: float, max_long_rate: float) -> float:
    trades = int(m.get("trades", 0))
    pf = float(m.get("profit_factor", 0.0))
    long_rate = float(m.get("long_rate", float("nan")))
    min_month = int(m.get("min_month_trades", 0))
    pnl = float(m.get("pnl_dollars", 0.0))
    dd = abs(float(m.get("max_drawdown", 0.0)))
    if trades <= 0 or min_month < min_month_trades:
        return -1e18 + trades
    if not np.isfinite(pf) or pf < min_pf:
        return -1e18 + pnl
    if not np.isfinite(long_rate) or long_rate < min_long_rate or long_rate > max_long_rate:
        return -1e18 + pnl
    return (
        4.0 * math.log(max(pf, 1e-6))
        + 0.65 * math.log1p(trades)
        + pnl / 100_000.0
        - dd / 100_000.0
        + float(m.get("positive_month_rate", 0.0))
    )


def select_profile(frame: pd.DataFrame, profile: Profile) -> pd.DataFrame:
    selected = frame[np.isclose(frame["delta_target"].astype(float), profile.delta_target)].copy()
    if selected.empty:
        return selected
    if profile.max_minutes_to_close < 9999 and "minutes_to_close" in selected.columns:
        selected = selected[selected["minutes_to_close"].astype(float) <= profile.max_minutes_to_close].copy()
    if profile.feature != "none":
        values = pd.to_numeric(selected[profile.feature], errors="coerce")
        if profile.op == "<=":
            selected = selected[values <= profile.threshold].copy()
        elif profile.op == ">=":
            selected = selected[values >= profile.threshold].copy()
        else:
            raise ValueError(f"Unsupported op={profile.op}")
    if selected.empty:
        return selected
    selected = selected.sort_values(["signal_id", "candidate_id"]).drop_duplicates("signal_id", keep="first")
    selected["deploy_config"] = profile.name
    return selected


def build_profiles(train: pd.DataFrame, ticker: str, args: argparse.Namespace) -> list[Profile]:
    profiles: list[Profile] = []
    for delta in args.delta_targets:
        for max_mtc in args.max_minutes_to_close:
            profiles.append(Profile(ticker, float(delta), float(max_mtc), "none", "", float("nan")))
            for feature in args.features:
                if feature not in train.columns:
                    continue
                values = pd.to_numeric(train[feature], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
                if values.nunique() < 8:
                    continue
                for q in args.quantiles:
                    threshold = float(values.quantile(float(q)))
                    if not math.isfinite(threshold):
                        continue
                    profiles.append(Profile(ticker, float(delta), float(max_mtc), feature, "<=", threshold))
                    profiles.append(Profile(ticker, float(delta), float(max_mtc), feature, ">=", threshold))
    return profiles


def evaluate_ticker(candidates: pd.DataFrame, ticker: str, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_months = month_list(args.train_start_month, args.train_end_month)
    test_months = month_list(args.test_start_month, args.test_end_month)
    inner_val_months = int(args.inner_val_months)
    if inner_val_months > 0 and len(train_months) > inner_val_months:
        core_months = train_months[:-inner_val_months]
        val_months = train_months[-inner_val_months:]
    else:
        core_months = train_months
        val_months = []
    tdf = candidates[candidates["ticker"].eq(ticker)].copy()
    train = tdf[tdf["month"].isin(train_months)].copy()
    test = tdf[tdf["month"].isin(test_months)].copy()
    profiles = build_profiles(train, ticker, args)
    rows: list[dict] = []
    best_trades: list[pd.DataFrame] = []
    for profile in profiles:
        train_trades = select_profile(train, profile)
        train_metrics = metrics(train_trades, train_months)
        train_score = score(
            train_metrics,
            int(args.min_month_trades),
            float(args.min_train_pf),
            float(args.min_long_rate),
            float(args.max_long_rate),
        )
        core_metrics = metrics(select_profile(train[train["month"].isin(core_months)].copy(), profile), core_months)
        core_score = score(
            core_metrics,
            int(args.min_month_trades),
            float(args.min_train_pf),
            float(args.min_long_rate),
            float(args.max_long_rate),
        )
        if val_months:
            val_metrics = metrics(select_profile(train[train["month"].isin(val_months)].copy(), profile), val_months)
            val_score = score(
                val_metrics,
                int(args.min_month_trades),
                float(args.min_train_pf),
                float(args.min_long_rate),
                float(args.max_long_rate),
            )
            profile_score = min(core_score, val_score) + 0.15 * train_score
        else:
            val_metrics = {
                "trades": 0,
                "win_rate": float("nan"),
                "profit_factor": float("nan"),
                "pnl_dollars": 0.0,
                "return_on_risk": 0.0,
                "max_drawdown": 0.0,
                "long_rate": float("nan"),
                "min_month_trades": 0,
                "positive_month_rate": float("nan"),
            }
            profile_score = train_score
        test_trades = select_profile(test, profile)
        test_metrics = metrics(test_trades, test_months)
        rows.append(
            {
                **asdict(profile),
                "name": profile.name,
                "score": float(profile_score),
                **{f"core_{k}": v for k, v in core_metrics.items()},
                **{f"inner_val_{k}": v for k, v in val_metrics.items()},
                **{f"train_{k}": v for k, v in train_metrics.items()},
                **{f"test_{k}": v for k, v in test_metrics.items()},
            }
        )
    result = pd.DataFrame(rows).sort_values(["score", "train_profit_factor", "train_pnl_dollars"], ascending=False)
    if not result.empty:
        best_name = str(result.iloc[0]["name"])
        for profile in profiles:
            if profile.name == best_name:
                best = select_profile(test, profile)
                if not best.empty:
                    best_trades.append(best)
                break
    return result, pd.concat(best_trades, ignore_index=True) if best_trades else pd.DataFrame()


def main() -> int:
    parser = argparse.ArgumentParser(description="Anchored structural option-profile search over candidate labels.")
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--train-start-month", default="202507")
    parser.add_argument("--train-end-month", default="202512")
    parser.add_argument("--test-start-month", default="202601")
    parser.add_argument("--test-end-month", default="202605")
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
    parser.add_argument("--quantiles", nargs="+", type=float, default=[0.15, 0.25, 0.35, 0.50, 0.65, 0.75, 0.85])
    parser.add_argument("--min-month-trades", type=int, default=15)
    parser.add_argument("--min-train-pf", type=float, default=1.05)
    parser.add_argument("--inner-val-months", type=int, default=0)
    parser.add_argument("--min-long-rate", type=float, default=0.20)
    parser.add_argument("--max-long-rate", type=float, default=0.80)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates = normalize_candidates(Path(args.candidate_labels), args.tickers)

    all_rows: list[pd.DataFrame] = []
    selected_trades: list[pd.DataFrame] = []
    top_rows: list[dict] = []
    for ticker in [t.upper() for t in args.tickers]:
        result, trades = evaluate_ticker(candidates, ticker, args)
        result.to_csv(out_dir / f"structural_profiles_{ticker}.csv", index=False)
        all_rows.append(result)
        if not trades.empty:
            selected_trades.append(trades)
        if not result.empty:
            top = result.iloc[0].to_dict()
            top_rows.append(top)
            print(
                f"[STRUCT_PROFILE] {ticker} best={top['name']} "
                f"train_pf={top['train_profit_factor']:.3f} train_minM={top['train_min_month_trades']} "
                f"test_pf={top['test_profit_factor']:.3f} test_minM={top['test_min_month_trades']} "
                f"test_pnl={top['test_pnl_dollars']:.0f}",
                flush=True,
            )

    combined_profiles = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    combined_profiles.to_csv(out_dir / "structural_profiles_all.csv", index=False)
    selected = pd.concat(selected_trades, ignore_index=True) if selected_trades else pd.DataFrame()
    if not selected.empty:
        selected.to_csv(out_dir / "selected_test_trades.csv", index=False)

    test_months = month_list(args.test_start_month, args.test_end_month)
    overall = metrics(selected, test_months)
    per_ticker = {
        ticker: metrics(part, test_months)
        for ticker, part in selected.groupby("ticker", sort=True)
    } if not selected.empty else {}
    summary = {
        "args": vars(args),
        "top_by_ticker": top_rows,
        "selected_test_overall": overall,
        "selected_test_per_ticker": per_ticker,
    }
    (out_dir / "metrics.json").write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Anchored Structural Option Profiles",
        "",
        "Profile family: fixed delta + max minutes-to-close + at most one regime/Greek threshold. Thresholds are built from train months only.",
        "",
        "```json",
        json.dumps(summary, indent=2, allow_nan=True),
        "```",
        "",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print((out_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
