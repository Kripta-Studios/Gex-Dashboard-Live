from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


META_COLS = ["ticker", "trade_date", "expiry_mode", "minute"]
BASE_FEATURES = [
    "ret_1m_bps",
    "ret_5m_bps",
    "ret_15m_bps",
    "ret_30m_bps",
    "nearest_level_abs_bps",
    "ib_range_bps",
    "phys_total_volume_skew_call_minus_put",
    "phys_total_oi_skew_call_minus_put",
    "phys_total_option_volume_log",
    "phys_total_option_oi_log",
    "phys_fib_any_min_abs_bps",
    "phys_ib_edge_min_abs_bps",
    "phys_ib_balance",
    "phys_nearest_level_vs_ib_range",
    "phys_abs_ret_5m_bps",
    "phys_abs_ret_15m_bps",
    "ctx_spy_qqq_ret_5m_spread",
    "ctx_spx_spy_ret_5m_spread",
]


@dataclass(frozen=True)
class StaticProfile:
    ticker: str
    delta: int
    side_rule: str
    feature: str
    op: str
    threshold: float
    max_trades_per_day: int

    @property
    def name(self) -> str:
        max_day = "all" if self.max_trades_per_day >= 999 else str(self.max_trades_per_day)
        if self.feature == "none":
            filt = "nofilter"
        else:
            thr = f"{self.threshold:.5g}".replace("-", "m").replace(".", "p")
            filt = f"{self.feature}_{self.op}_{thr}"
        return f"{self.ticker}_d{self.delta}_{self.side_rule}_{filt}_maxday{max_day}"


def month_range(start: str, end: str) -> list[str]:
    y = int(str(start)[:4])
    m = int(str(start)[4:6])
    end_i = int(str(end))
    out: list[str] = []
    while y * 100 + m <= end_i:
        out.append(f"{y:04d}{m:02d}")
        m += 1
        if m == 13:
            y += 1
            m = 1
    return out


def read_frame(path: Path, deltas: list[int], features: list[str]) -> pd.DataFrame:
    available = set(pq.ParquetFile(path).schema.names)
    label_cols: list[str] = []
    for delta in deltas:
        label_cols.extend([f"call_d{delta:02d}_opt_exit_ret", f"put_d{delta:02d}_opt_exit_ret"])
    cols = [c for c in META_COLS + features + label_cols if c in available]
    frame = pd.read_parquet(path, columns=cols)
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["trade_date"] = frame["trade_date"].astype(str).str.replace("-", "", regex=False).str[:8]
    frame["month"] = frame["trade_date"].str[:6]
    frame["date"] = frame["trade_date"]
    frame["minute"] = pd.to_numeric(frame["minute"], errors="coerce").fillna(0).astype(int)
    return frame.sort_values(["ticker", "date", "minute"]).reset_index(drop=True)


def metrics(trades: pd.DataFrame, expected_months: list[str]) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": float("nan"),
            "profit_factor": float("nan"),
            "pnl_return": 0.0,
            "max_drawdown": 0.0,
            "call_rate": float("nan"),
            "min_month_trades": 0,
            "positive_month_rate": float("nan"),
            "days_with_trades": 0,
            "daily_win_rate": float("nan"),
            "median_daily_return": float("nan"),
        }
    ret = trades["realized_return"].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
    wins = ret[ret > 0.0]
    losses = ret[ret < 0.0]
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    equity = np.cumsum(ret)
    peak = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
    by_month = trades.groupby("month")["realized_return"].agg(["count", "sum"]).reindex(expected_months, fill_value=0)
    daily = trades.groupby("date")["realized_return"].sum().astype(float).sort_index()
    return {
        "trades": int(len(trades)),
        "win_rate": float((ret > 0.0).mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf"),
        "pnl_return": float(ret.sum()),
        "max_drawdown": float((equity - peak).min()) if len(equity) else 0.0,
        "call_rate": float((trades["action"].astype(str) == "CALL").mean()),
        "min_month_trades": int(by_month["count"].min()) if not by_month.empty else 0,
        "positive_month_rate": float((by_month["sum"] > 0.0).mean()) if not by_month.empty else float("nan"),
        "days_with_trades": int(len(daily)),
        "daily_win_rate": float((daily > 0.0).mean()) if len(daily) else float("nan"),
        "median_daily_return": float(daily.median()) if len(daily) else float("nan"),
    }


def profile_mask(frame: pd.DataFrame, profile: StaticProfile) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    if profile.feature != "none":
        values = pd.to_numeric(frame[profile.feature], errors="coerce")
        if profile.op == "<=":
            mask &= values <= float(profile.threshold)
        elif profile.op == ">=":
            mask &= values >= float(profile.threshold)
        else:
            raise ValueError(f"Unsupported op={profile.op}")
    return mask


def actions_for(frame: pd.DataFrame, side_rule: str) -> pd.Series:
    if side_rule == "fixed_call":
        return pd.Series("CALL", index=frame.index)
    if side_rule == "fixed_put":
        return pd.Series("PUT", index=frame.index)
    if side_rule.startswith("trend_"):
        col = side_rule.removeprefix("trend_")
        return pd.Series(np.where(pd.to_numeric(frame[col], errors="coerce").fillna(0.0) >= 0.0, "CALL", "PUT"), index=frame.index)
    if side_rule.startswith("contrarian_"):
        col = side_rule.removeprefix("contrarian_")
        return pd.Series(np.where(pd.to_numeric(frame[col], errors="coerce").fillna(0.0) >= 0.0, "PUT", "CALL"), index=frame.index)
    raise ValueError(f"Unsupported side_rule={side_rule}")


def deploy(frame: pd.DataFrame, profile: StaticProfile, cooldown_minutes: int, clip_return: float) -> pd.DataFrame:
    selected = frame[profile_mask(frame, profile)].copy()
    if selected.empty:
        return selected
    selected["action"] = actions_for(selected, profile.side_rule)
    call_col = f"call_d{profile.delta:02d}_opt_exit_ret"
    put_col = f"put_d{profile.delta:02d}_opt_exit_ret"
    selected["realized_return"] = np.where(
        selected["action"].eq("CALL"),
        pd.to_numeric(selected[call_col], errors="coerce"),
        pd.to_numeric(selected[put_col], errors="coerce"),
    )
    selected = selected[np.isfinite(selected["realized_return"].astype(float))].copy()
    if selected.empty:
        return selected
    if float(clip_return) > 0.0:
        selected["realized_return"] = selected["realized_return"].clip(-float(clip_return), float(clip_return))
    rows: list[dict] = []
    for _, day in selected.sort_values(["date", "minute"]).groupby("date", sort=False):
        next_allowed = -1
        taken = 0
        for row in day.itertuples(index=False):
            minute = int(row.minute)
            if minute < next_allowed:
                continue
            if taken >= int(profile.max_trades_per_day):
                break
            values = row._asdict()
            values["deploy_config"] = profile.name
            rows.append(values)
            taken += 1
            next_allowed = minute + int(cooldown_minutes)
    return pd.DataFrame(rows) if rows else selected.iloc[0:0].copy()


def pass_gate(m: dict, args: argparse.Namespace, months: list[str]) -> bool:
    if int(m["trades"]) < int(args.min_trades):
        return False
    if int(m["min_month_trades"]) < int(args.min_month_trades):
        return False
    if not np.isfinite(float(m["win_rate"])) or float(m["win_rate"]) < float(args.min_win_rate):
        return False
    if not np.isfinite(float(m["profit_factor"])) or float(m["profit_factor"]) < float(args.min_pf):
        return False
    if float(m["pnl_return"]) <= 0.0:
        return False
    call_rate = float(m["call_rate"])
    if not np.isfinite(call_rate) or call_rate < float(args.min_call_rate) or call_rate > float(args.max_call_rate):
        return False
    return True


def score(m: dict) -> float:
    if int(m["trades"]) <= 0 or not np.isfinite(float(m["profit_factor"])):
        return -1e18
    return (
        5.0 * math.log(max(float(m["profit_factor"]), 1e-6))
        + 2.0 * float(m["win_rate"])
        + 0.25 * math.log1p(int(m["trades"]))
        + float(m["pnl_return"]) / 25.0
        - abs(float(m["max_drawdown"])) / 10.0
        + float(m.get("positive_month_rate", 0.0))
    )


def build_profiles(train: pd.DataFrame, ticker: str, args: argparse.Namespace, features: list[str]) -> list[StaticProfile]:
    profiles: list[StaticProfile] = []
    for delta in args.deltas:
        for side_rule in args.side_rules:
            for max_day in args.max_day_grid:
                profiles.append(StaticProfile(ticker, int(delta), side_rule, "none", "", float("nan"), int(max_day)))
                for feature in features:
                    if feature not in train.columns:
                        continue
                    values = pd.to_numeric(train[feature], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
                    if values.nunique() < 20:
                        continue
                    for q in args.quantiles:
                        threshold = float(values.quantile(float(q)))
                        if not math.isfinite(threshold):
                            continue
                        profiles.append(StaticProfile(ticker, int(delta), side_rule, feature, "<=", threshold, int(max_day)))
                        profiles.append(StaticProfile(ticker, int(delta), side_rule, feature, ">=", threshold, int(max_day)))
    return profiles


def evaluate_ticker(frame: pd.DataFrame, ticker: str, args: argparse.Namespace, features: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    fit_months = month_range(args.fit_start_month, args.fit_end_month)
    select_months = month_range(args.select_start_month, args.select_end_month)
    test1_months = month_range(args.test1_start_month, args.test1_end_month)
    test2_months = month_range(args.test2_start_month, args.test2_end_month)
    tdf = frame[frame["ticker"].eq(ticker)].copy()
    fit = tdf[tdf["month"].isin(fit_months)].copy()
    select = tdf[tdf["month"].isin(select_months)].copy()
    test1 = tdf[tdf["month"].isin(test1_months)].copy()
    test2 = tdf[tdf["month"].isin(test2_months)].copy()
    profiles = build_profiles(fit, ticker, args, features)
    rows: list[dict] = []
    selected_trades: list[pd.DataFrame] = []
    best_profile: StaticProfile | None = None
    best_score = -1e18
    for profile in profiles:
        select_trades = deploy(select, profile, args.cooldown_minutes, args.clip_return)
        select_metrics = metrics(select_trades, select_months)
        if not pass_gate(select_metrics, args, select_months):
            continue
        test1_trades = deploy(test1, profile, args.cooldown_minutes, args.clip_return)
        test2_trades = deploy(test2, profile, args.cooldown_minutes, args.clip_return)
        test1_metrics = metrics(test1_trades, test1_months)
        test2_metrics = metrics(test2_trades, test2_months)
        row = {
            **asdict(profile),
            "name": profile.name,
            **{f"select_{k}": v for k, v in select_metrics.items()},
            **{f"test1_{k}": v for k, v in test1_metrics.items()},
            **{f"test2_{k}": v for k, v in test2_metrics.items()},
            "select_score": score(select_metrics),
        }
        rows.append(row)
        profile_score = score(select_metrics)
        if profile_score > best_score:
            best_score = profile_score
            best_profile = profile
    if best_profile is not None:
        for label, months, data in [("select", select_months, select), ("test1", test1_months, test1), ("test2", test2_months, test2)]:
            trades = deploy(data, best_profile, args.cooldown_minutes, args.clip_return)
            if not trades.empty:
                trades = trades.copy()
                trades["period"] = label
                selected_trades.append(trades)
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["select_score", "select_profit_factor", "select_pnl_return"], ascending=False)
    trades = pd.concat(selected_trades, ignore_index=True) if selected_trades else pd.DataFrame()
    return result, trades


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal frozen static profile scan for event-option datasets.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--expiry-modes", nargs="+", default=["zero_dte"])
    parser.add_argument("--fit-start-month", default="202201")
    parser.add_argument("--fit-end-month", default="202312")
    parser.add_argument("--select-start-month", default="202401")
    parser.add_argument("--select-end-month", default="202412")
    parser.add_argument("--test1-start-month", default="202501")
    parser.add_argument("--test1-end-month", default="202512")
    parser.add_argument("--test2-start-month", default="202601")
    parser.add_argument("--test2-end-month", default="202606")
    parser.add_argument("--deltas", nargs="+", type=int, default=[35, 50, 65, 80])
    parser.add_argument("--side-rules", nargs="+", default=[
        "trend_ret_5m_bps",
        "contrarian_ret_5m_bps",
        "trend_ret_15m_bps",
        "contrarian_ret_15m_bps",
    ])
    parser.add_argument("--features", nargs="+", default=BASE_FEATURES)
    parser.add_argument("--quantiles", nargs="+", type=float, default=[0.15, 0.25, 0.35, 0.50, 0.65, 0.75, 0.85])
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[999, 12, 8, 6, 4, 2])
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--clip-return", type=float, default=2.0)
    parser.add_argument("--min-trades", type=int, default=216)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-pf", type=float, default=1.3)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = read_frame(Path(args.data), [int(d) for d in args.deltas], list(args.features))
    if args.expiry_modes:
        modes = {str(m) for m in args.expiry_modes}
        frame = frame[frame["expiry_mode"].astype(str).isin(modes)].copy()
    frame = frame[frame["ticker"].isin([str(t).upper() for t in args.tickers])].copy()
    features = [f for f in args.features if f in frame.columns]

    all_rows: list[pd.DataFrame] = []
    best_trades: list[pd.DataFrame] = []
    summary: dict[str, dict] = {}
    test1_months = month_range(args.test1_start_month, args.test1_end_month)
    test2_months = month_range(args.test2_start_month, args.test2_end_month)
    select_months = month_range(args.select_start_month, args.select_end_month)
    for ticker in [str(t).upper() for t in args.tickers]:
        result, trades = evaluate_ticker(frame, ticker, args, features)
        result.to_csv(out_dir / f"static_profile_candidates_{ticker}.csv", index=False)
        all_rows.append(result)
        if not trades.empty:
            trades.to_csv(out_dir / f"best_profile_trades_{ticker}.csv", index=False)
            best_trades.append(trades)
        best = result.iloc[0].to_dict() if not result.empty else {}
        summary[ticker] = {
            "candidate_profiles_passing_select": int(len(result)),
            "best": best,
        }
        print(f"[STATIC_PROFILE] {ticker} select_pass={len(result):,} best={best.get('name', 'none')}", flush=True)

    combined = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    combined.to_csv(out_dir / "static_profile_candidates_all.csv", index=False)
    selected = pd.concat(best_trades, ignore_index=True) if best_trades else pd.DataFrame()
    if not selected.empty:
        selected.to_csv(out_dir / "best_profile_trades_all.csv", index=False)

    period_metrics: dict[str, dict] = {}
    if not selected.empty:
        for label, months in [("select", select_months), ("test1", test1_months), ("test2", test2_months)]:
            part = selected[selected["period"].eq(label)].copy()
            period_metrics[label] = {
                "overall": metrics(part, months),
                "per_ticker": {str(t): metrics(g, months) for t, g in part.groupby("ticker", sort=True)},
            }
    payload = {"args": vars(args), "features": features, "summary": summary, "period_metrics": period_metrics}
    (out_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")

    lines = [
        "# Static Event-Option Profile Scan",
        "",
        "Profiles are fit from fit months, selected on the select window, then frozen for test windows.",
        "",
        "## Best By Ticker",
        "",
        "| Ticker | Select-Pass Profiles | Best Profile | Select WR | Select PF | Test1 WR | Test1 PF | Test1 MinM | Test2 WR | Test2 PF | Test2 MinM |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for ticker, item in summary.items():
        best = item.get("best", {})
        if not best:
            lines.append(f"| {ticker} | 0 | none | nan | nan | nan | nan | 0 | nan | nan | 0 |")
            continue
        lines.append(
            f"| {ticker} | {item['candidate_profiles_passing_select']} | `{best['name']}` | "
            f"{100*float(best['select_win_rate']):.1f}% | {float(best['select_profit_factor']):.3f} | "
            f"{100*float(best['test1_win_rate']):.1f}% | {float(best['test1_profit_factor']):.3f} | {int(best['test1_min_month_trades'])} | "
            f"{100*float(best['test2_win_rate']):.1f}% | {float(best['test2_profit_factor']):.3f} | {int(best['test2_min_month_trades'])} |"
        )
    lines += ["", "## JSON", "", "```json", json.dumps(payload, indent=2, allow_nan=True), "```", ""]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print((out_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
