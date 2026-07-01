from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_range
from rolling_variant_meta_router import trade_metrics


@dataclass(frozen=True)
class RouterConfig:
    recent_window: int
    min_trading_day: int
    w_recent: float
    w_same_month: float
    w_month_cum: float
    w_all: float
    w_trade_density: float

    @property
    def name(self) -> str:
        def fmt(value: float) -> str:
            return str(value).replace(".", "p").replace("-", "m")

        return (
            f"rw{self.recent_window}"
            f"_d{self.min_trading_day}"
            f"_wr{fmt(self.w_recent)}"
            f"_wsm{fmt(self.w_same_month)}"
            f"_wm{fmt(self.w_month_cum)}"
            f"_wa{fmt(self.w_all)}"
            f"_wtd{fmt(self.w_trade_density)}"
        )


def parse_variant(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        path = Path(spec)
        return path.name, path
    name, raw = spec.split("=", 1)
    return name.strip(), Path(raw.strip())


def load_expert_trades(variant_specs: list[str]) -> tuple[list[str], pd.DataFrame]:
    experts: list[str] = []
    parts: list[pd.DataFrame] = []
    for spec in variant_specs:
        name, path = parse_variant(spec)
        trade_file = path / "event_option_gate_trades.csv"
        if not trade_file.exists():
            raise FileNotFoundError(f"Missing trades for expert {name}: {trade_file}")
        trades = pd.read_csv(trade_file, dtype={"ticker": str, "date": str, "month": str, "test_month": str})
        trades["expert"] = name
        experts.append(name)
        parts.append(trades)
    out = pd.concat(parts, ignore_index=True)
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["date"] = out["date"].astype(str)
    out["test_month"] = out["test_month"].astype(str)
    out["realized_return"] = pd.to_numeric(out["realized_return"], errors="coerce").fillna(0.0)
    out["score"] = pd.to_numeric(out.get("score", 0.0), errors="coerce").fillna(0.0)
    return experts, out


def make_daily_frame(trades: pd.DataFrame, experts: list[str], tickers: list[str]) -> pd.DataFrame:
    daily = (
        trades.groupby(["expert", "ticker", "test_month", "date"], as_index=False)
        .agg(daily_R=("realized_return", "sum"), daily_trades=("realized_return", "count"), daily_score=("score", "mean"))
    )
    calendar = daily[["ticker", "test_month", "date"]].drop_duplicates()
    calendar = calendar.sort_values(["ticker", "test_month", "date"], kind="stable")
    calendar["trading_day_index"] = calendar.groupby(["ticker", "test_month"], sort=False).cumcount() + 1
    grid = calendar.assign(_key=1).merge(pd.DataFrame({"expert": experts, "_key": 1}), on="_key", how="left").drop(columns="_key")
    out = grid.merge(daily, on=["expert", "ticker", "test_month", "date"], how="left")
    out["daily_R"] = pd.to_numeric(out["daily_R"], errors="coerce").fillna(0.0)
    out["daily_trades"] = pd.to_numeric(out["daily_trades"], errors="coerce").fillna(0.0)
    out["daily_score"] = pd.to_numeric(out["daily_score"], errors="coerce").fillna(0.0)
    out["date"] = out["date"].astype(str)
    out["test_month"] = out["test_month"].astype(str)
    out["month_num"] = out["test_month"].str[4:6].astype(int)
    out = out[out["ticker"].isin(tickers)].sort_values(["ticker", "expert", "date"], kind="stable").reset_index(drop=True)
    return out


def add_prior_features(daily: pd.DataFrame, recent_windows: list[int]) -> pd.DataFrame:
    out = daily.copy().sort_values(["ticker", "expert", "date"], kind="stable")
    group = out.groupby(["ticker", "expert"], sort=False)
    out["all_days_seen"] = group.cumcount()
    out["all_R_sum"] = group["daily_R"].cumsum() - out["daily_R"]
    out["all_trade_sum"] = group["daily_trades"].cumsum() - out["daily_trades"]
    out["all_R_mean"] = out["all_R_sum"] / out["all_days_seen"].replace(0, np.nan)
    out["all_R_per_trade"] = out["all_R_sum"] / out["all_trade_sum"].replace(0, np.nan)

    month_group = out.groupby(["ticker", "expert", "test_month"], sort=False)
    out["month_cum_R"] = month_group["daily_R"].cumsum() - out["daily_R"]
    out["month_cum_trades"] = month_group["daily_trades"].cumsum() - out["daily_trades"]
    out["month_cum_R_per_trade"] = out["month_cum_R"] / out["month_cum_trades"].replace(0, np.nan)

    same = out.groupby(["ticker", "expert", "month_num"], sort=False)
    out["same_month_days_seen"] = same.cumcount()
    out["same_month_R_sum"] = same["daily_R"].cumsum() - out["daily_R"]
    out["same_month_trade_sum"] = same["daily_trades"].cumsum() - out["daily_trades"]
    out["same_month_R_mean"] = out["same_month_R_sum"] / out["same_month_days_seen"].replace(0, np.nan)
    out["same_month_R_per_trade"] = out["same_month_R_sum"] / out["same_month_trade_sum"].replace(0, np.nan)

    for window in recent_windows:
        shifted_R = group["daily_R"].shift(1)
        shifted_trades = group["daily_trades"].shift(1)
        out[f"recent{window}_R_mean"] = (
            shifted_R.groupby([out["ticker"], out["expert"]], sort=False)
            .rolling(window=int(window), min_periods=1)
            .mean()
            .reset_index(level=[0, 1], drop=True)
        )
        out[f"recent{window}_R_sum"] = (
            shifted_R.groupby([out["ticker"], out["expert"]], sort=False)
            .rolling(window=int(window), min_periods=1)
            .sum()
            .reset_index(level=[0, 1], drop=True)
        )
        out[f"recent{window}_trade_sum"] = (
            shifted_trades.groupby([out["ticker"], out["expert"]], sort=False)
            .rolling(window=int(window), min_periods=1)
            .sum()
            .reset_index(level=[0, 1], drop=True)
        )
    score_cols = [col for col in out.columns if col.endswith(("_mean", "_sum", "_trade", "_trades")) or "_cum_" in col]
    out[score_cols] = out[score_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return out


def config_grid(args: argparse.Namespace) -> list[RouterConfig]:
    return [
        RouterConfig(
            int(window),
            int(min_day),
            float(w_recent),
            float(w_same),
            float(w_month),
            float(w_all),
            float(w_density),
        )
        for window in args.recent_windows
        for min_day in args.min_trading_day_grid
        for w_recent in args.w_recent_grid
        for w_same in args.w_same_month_grid
        for w_month in args.w_month_cum_grid
        for w_all in args.w_all_grid
        for w_density in args.w_trade_density_grid
    ]


def score_daily(daily: pd.DataFrame, cfg: RouterConfig) -> pd.Series:
    recent_mean = daily[f"recent{cfg.recent_window}_R_mean"].astype(float)
    density = np.log1p(daily[f"recent{cfg.recent_window}_trade_sum"].astype(float))
    score = (
        float(cfg.w_recent) * recent_mean
        + float(cfg.w_same_month) * daily["same_month_R_mean"].astype(float)
        + float(cfg.w_month_cum) * daily["month_cum_R"].astype(float)
        + float(cfg.w_all) * daily["all_R_mean"].astype(float)
        + float(cfg.w_trade_density) * density
    )
    return score.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def select_days(daily: pd.DataFrame, cfg: RouterConfig, start_month: str, end_month: str) -> pd.DataFrame:
    part = daily[(daily["test_month"].astype(str) >= str(start_month)) & (daily["test_month"].astype(str) <= str(end_month))].copy()
    if part.empty:
        return pd.DataFrame()
    part = part[pd.to_numeric(part["trading_day_index"], errors="coerce").fillna(0).astype(int) >= int(cfg.min_trading_day)].copy()
    if part.empty:
        return pd.DataFrame()
    part = part[part["daily_trades"].astype(float) > 0.0].copy()
    if part.empty:
        return pd.DataFrame()
    part["router_score"] = score_daily(part, cfg)
    selected = (
        part.sort_values(["ticker", "date", "router_score", "daily_R", "daily_trades"], ascending=[True, True, False, False, False], kind="stable")
        .groupby(["ticker", "date"], sort=False)
        .head(1)
        .copy()
    )
    selected["router_config"] = cfg.name
    return selected


def materialize_trades(trades: pd.DataFrame, selected_days: pd.DataFrame) -> pd.DataFrame:
    if selected_days.empty:
        return pd.DataFrame()
    selected = selected_days[["expert", "ticker", "date", "router_score", "router_config"]].copy()
    out = trades.merge(selected, on=["expert", "ticker", "date"], how="inner", validate="many_to_one")
    out["selected_expert"] = out["expert"]
    return out


def expected_metrics(trades: pd.DataFrame, months: list[str], tickers: list[str]) -> tuple[dict, dict, pd.DataFrame, dict]:
    overall = trade_metrics(trades)
    monthly_rows: list[dict] = []
    per_ticker: dict[str, dict] = {}
    for ticker in tickers:
        part = trades[trades["ticker"].astype(str).str.upper() == ticker] if not trades.empty else pd.DataFrame()
        per_ticker[ticker] = trade_metrics(part)
    grid = pd.MultiIndex.from_product([tickers, months], names=["ticker", "month"])
    if not trades.empty:
        monthly = trades.groupby(["ticker", "test_month"])["realized_return"].agg(["count", "sum"])
        monthly.index = monthly.index.set_names(["ticker", "month"])
        monthly = monthly.reindex(grid, fill_value=0)
    else:
        monthly = pd.DataFrame(index=grid, data={"count": 0, "sum": 0.0})
    for (ticker, month), row in monthly.iterrows():
        monthly_rows.append({"ticker": ticker, "month": month, "trades": int(row["count"]), "R": float(row["sum"])})
    monthly_df = pd.DataFrame(monthly_rows)
    for ticker in tickers:
        sub = monthly.xs(ticker, level="ticker")
        per_ticker[ticker]["min_month"] = int(sub["count"].min())
        per_ticker[ticker]["pos_month_rate"] = float((sub["sum"] > 0.0).mean())
    summary = {
        "pf_min": min(float(v["pf"]) if math.isfinite(float(v["pf"])) else 99.0 for v in per_ticker.values()),
        "wr_min": min(float(v["wr"]) if math.isfinite(float(v["wr"])) else 0.0 for v in per_ticker.values()),
        "min_month_ticker": min(int(v["min_month"]) for v in per_ticker.values()),
        "pos_min": min(float(v["pos_month_rate"]) if math.isfinite(float(v["pos_month_rate"])) else 0.0 for v in per_ticker.values()),
        "losing_ticker_months": int((monthly_df["R"].astype(float) < 0.0).sum()),
    }
    return overall, per_ticker, monthly_df, summary


def score_selection(overall: dict, summary: dict, args: argparse.Namespace) -> float:
    pf = float(overall["pf"]) if math.isfinite(float(overall["pf"])) else 3.0
    score = (
        2.0 * min(max(pf, 0.0), 3.0)
        + 1.5 * float(summary["pf_min"])
        + 0.10 * float(overall["R"])
        + float(summary["pos_min"])
        - 0.35 * int(summary["losing_ticker_months"])
        + 0.02 * int(summary["min_month_ticker"])
    )
    if int(summary["min_month_ticker"]) < int(args.gate_min_month_trades):
        score -= 100.0
    if float(summary["pf_min"]) < float(args.gate_min_pf):
        score -= 100.0
    if float(overall["R"]) <= 0.0:
        score -= 100.0
    call_rate = float((overall.get("call_rate", 0.5) if "call_rate" in overall else 0.5))
    if not (float(args.min_call_rate) <= call_rate <= float(args.max_call_rate)):
        score -= 100.0
    return float(score)


def evaluate_config(
    trades: pd.DataFrame,
    daily: pd.DataFrame,
    cfg: RouterConfig,
    start_month: str,
    end_month: str,
    tickers: list[str],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict, pd.DataFrame, dict]:
    months = month_range(str(start_month), str(end_month))
    selected_days = select_days(daily, cfg, start_month, end_month)
    routed_trades = materialize_trades(trades, selected_days)
    overall, per_ticker, monthly, summary = expected_metrics(routed_trades, months, tickers)
    return routed_trades, selected_days, overall, per_ticker, monthly, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal online daily expert router over precomputed event-option expert streams.")
    parser.add_argument("--variant", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--selection-start-month", default="202401")
    parser.add_argument("--selection-end-month", default="202512")
    parser.add_argument("--test-start-month", default="202601")
    parser.add_argument("--test-end-month", default="202606")
    parser.add_argument("--recent-windows", nargs="+", type=int, default=[5, 10, 21, 42])
    parser.add_argument("--min-trading-day-grid", nargs="+", type=int, default=[1])
    parser.add_argument("--w-recent-grid", nargs="+", type=float, default=[0.5, 1.0, 2.0])
    parser.add_argument("--w-same-month-grid", nargs="+", type=float, default=[0.0, 0.25, 0.5])
    parser.add_argument("--w-month-cum-grid", nargs="+", type=float, default=[0.0, 0.05, 0.10, 0.25])
    parser.add_argument("--w-all-grid", nargs="+", type=float, default=[0.0, 0.25])
    parser.add_argument("--w-trade-density-grid", nargs="+", type=float, default=[0.0, 0.01])
    parser.add_argument("--gate-min-month-trades", type=int, default=18)
    parser.add_argument("--gate-min-pf", type=float, default=1.0)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "args.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    tickers = [str(t).upper() for t in args.tickers]
    experts, trades = load_expert_trades(args.variant)
    trades = trades[trades["ticker"].isin(tickers)].copy()
    configs = config_grid(args)
    daily = make_daily_frame(trades, experts, tickers)
    daily = add_prior_features(daily, sorted(set(int(c.recent_window) for c in configs)))
    daily.to_parquet(output_dir / "daily_expert_features.parquet", index=False)

    rows: list[dict] = []
    payloads: dict[str, tuple[pd.DataFrame, pd.DataFrame, dict, dict, pd.DataFrame, dict]] = {}
    for idx, cfg in enumerate(configs):
        payload = evaluate_config(trades, daily, cfg, args.selection_start_month, args.selection_end_month, tickers, args)
        routed_trades, selected_days, overall, per_ticker, monthly, summary = payload
        label = cfg.name
        payloads[label] = payload
        rows.append(
            {
                "idx": idx,
                "config": label,
                "score_selection": score_selection(overall, summary, args),
                **asdict(cfg),
                **{f"{key}_selection": value for key, value in overall.items()},
                "pf_min_selection": summary["pf_min"],
                "wr_min_selection": summary["wr_min"],
                "min_month_ticker_selection": summary["min_month_ticker"],
                "pos_min_selection": summary["pos_min"],
                "losing_ticker_months_selection": summary["losing_ticker_months"],
            }
        )
    ranked = pd.DataFrame(rows).sort_values("score_selection", ascending=False)
    ranked.to_csv(output_dir / "config_rank_selection.csv", index=False)

    test_rows: list[dict] = []
    for _, ranked_row in ranked.head(int(args.top_k)).iterrows():
        cfg = RouterConfig(
            int(ranked_row["recent_window"]),
            int(ranked_row["min_trading_day"]),
            float(ranked_row["w_recent"]),
            float(ranked_row["w_same_month"]),
            float(ranked_row["w_month_cum"]),
            float(ranked_row["w_all"]),
            float(ranked_row["w_trade_density"]),
        )
        label = cfg.name
        routed_trades, selected_days, overall, per_ticker, monthly, summary = evaluate_config(
            trades, daily, cfg, args.test_start_month, args.test_end_month, tickers, args
        )
        subdir = output_dir / label
        subdir.mkdir(parents=True, exist_ok=True)
        routed_trades.to_csv(subdir / "online_expert_trades.csv", index=False)
        selected_days.to_csv(subdir / "selected_days.csv", index=False)
        monthly.to_csv(subdir / "monthly.csv", index=False)
        (subdir / "metrics.json").write_text(
            json.dumps(
                {
                    "overall": overall,
                    "per_ticker": per_ticker,
                    "monthly_summary": summary,
                    "selection_row": ranked_row.to_dict(),
                    "pnl": float(overall.get("R", 0.0)) * float(args.risk_capital),
                },
                indent=2,
                allow_nan=True,
            ),
            encoding="utf-8",
        )
        test_rows.append(
            {
                **ranked_row.to_dict(),
                **{f"{key}_test": value for key, value in overall.items()},
                "pf_min_test": summary["pf_min"],
                "wr_min_test": summary["wr_min"],
                "min_month_ticker_test": summary["min_month_ticker"],
                "pos_min_test": summary["pos_min"],
                "losing_ticker_months_test": summary["losing_ticker_months"],
                "artifact_dir": str(subdir),
            }
        )
    test = pd.DataFrame(test_rows)
    test.to_csv(output_dir / "top_selection_then_test.csv", index=False)
    cols = [
        "idx",
        "config",
        "score_selection",
        "pf_selection",
        "R_selection",
        "pf_min_selection",
        "min_month_ticker_selection",
        "pos_min_selection",
        "losing_ticker_months_selection",
        "pf_test",
        "wr_test",
        "R_test",
        "pf_min_test",
        "wr_min_test",
        "min_month_ticker_test",
        "pos_min_test",
        "losing_ticker_months_test",
        "artifact_dir",
    ]
    print(test[[c for c in cols if c in test.columns]].to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
