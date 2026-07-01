from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_xinput_level_filter import month_add, month_range


@dataclass(frozen=True)
class DeltaConfig:
    delta_target: float
    max_trades_per_day: int

    @property
    def name(self) -> str:
        max_day = "all" if self.max_trades_per_day >= 999 else str(self.max_trades_per_day)
        return f"d{self.delta_target:.2f}_maxday{max_day}"


def metrics(trades: pd.DataFrame, expected_months: list[str] | None = None) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": float("nan"),
            "profit_factor": float("nan"),
            "pnl_dollars": 0.0,
            "return_on_risk": 0.0,
            "max_drawdown": 0.0,
            "avg_pnl": float("nan"),
            "avg_hold_minutes": float("nan"),
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
    by_month = trades.groupby("month")["rule_pnl_dollars"].agg(["count", "sum"])
    if expected_months is not None:
        by_month = by_month.reindex([str(m) for m in expected_months], fill_value=0)
    return {
        "trades": int(len(trades)),
        "win_rate": float((pnl > 0.0).mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf"),
        "pnl_dollars": float(pnl.sum()),
        "return_on_risk": float(trades["rule_return_on_risk"].astype(float).sum()),
        "max_drawdown": float((equity - peak).min()) if len(equity) else 0.0,
        "avg_pnl": float(pnl.mean()),
        "avg_hold_minutes": float(trades["rule_hold_minutes"].astype(float).mean()),
        "long_rate": float((trades["side"].astype(str) == "LONG").mean()),
        "min_month_trades": int(by_month["count"].min()) if not by_month.empty else 0,
        "positive_month_rate": float((by_month["sum"] > 0.0).mean()) if not by_month.empty else float("nan"),
    }


def score(row: dict, min_trades: int, min_month_trades: int) -> float:
    trades = int(row.get("trades", 0))
    min_month = int(row.get("min_month_trades", 0))
    pf = float(row.get("profit_factor", 0.0))
    long_rate = float(row.get("long_rate", float("nan")))
    if trades < int(min_trades) or min_month < int(min_month_trades):
        return -1e18 + trades
    if not np.isfinite(pf) or not np.isfinite(long_rate):
        return -1e18 + trades
    if long_rate < 0.20 or long_rate > 0.80:
        return -1e18 + trades
    pnl = float(row.get("pnl_dollars", 0.0))
    dd = abs(float(row.get("max_drawdown", 0.0)))
    positive_month_rate = float(row.get("positive_month_rate", 0.0))
    return (
        3.0 * math.log1p(min(max(pf, 0.0), 10.0))
        + 0.45 * math.log1p(trades)
        + pnl / 25_000.0
        - dd / 20_000.0
        + positive_month_rate
    )


def apply_max_day(trades: pd.DataFrame, max_day: int) -> pd.DataFrame:
    if trades.empty or int(max_day) >= 999:
        return trades.copy()
    rows: list[dict] = []
    for _, day in trades.sort_values(["date", "time"]).groupby("date", sort=False):
        rows.extend([row._asdict() for row in day.itertuples(index=False)][: int(max_day)])
    return pd.DataFrame(rows) if rows else trades.iloc[0:0].copy()


def select_config(frame: pd.DataFrame, cfg: DeltaConfig) -> pd.DataFrame:
    selected = frame[np.isclose(frame["delta_target"].astype(float), float(cfg.delta_target))].copy()
    if selected.empty:
        return selected
    selected = selected.sort_values(["signal_id", "candidate_id"]).drop_duplicates("signal_id", keep="first")
    selected = apply_max_day(selected, int(cfg.max_trades_per_day))
    if not selected.empty:
        selected["deploy_config"] = cfg.name
    return selected


def oracle_best_delta(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    idx = frame.sort_values(["signal_id", "rule_return_on_risk"]).groupby("signal_id", sort=False)["rule_return_on_risk"].idxmax()
    out = frame.loc[idx].copy()
    out["deploy_config"] = "oracle_best_delta"
    return out


def build_grid(args: argparse.Namespace) -> list[DeltaConfig]:
    return [DeltaConfig(float(delta), int(max_day)) for delta in args.delta_targets for max_day in args.max_day_grid]


def run_walkforward(candidates: pd.DataFrame, args: argparse.Namespace, grid: list[DeltaConfig]) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_trades: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    months = [m for m in sorted(candidates["month"].astype(str).unique()) if str(args.start_month) <= m <= str(args.end_month)]
    for ticker in [str(t).upper() for t in args.tickers]:
        tdf = candidates[candidates["ticker"].astype(str).str.upper() == ticker].copy()
        for test_month in months:
            val_months = [month_add(str(test_month), -i) for i in range(int(args.val_months), 0, -1)]
            val = tdf[tdf["month"].astype(str).isin(val_months)].copy()
            test = tdf[tdf["month"].astype(str) == str(test_month)].copy()
            if val.empty or test.empty:
                continue
            best_cfg = grid[0]
            best_score = -1e18
            best_metrics: dict = {}
            for cfg in grid:
                val_trades = select_config(val, cfg)
                row = metrics(val_trades, val_months)
                cfg_score = score(row, int(args.min_val_trades), int(args.min_month_trades))
                if cfg_score > best_score:
                    best_cfg = cfg
                    best_score = cfg_score
                    best_metrics = row
            if best_score <= -1e17 and not bool(args.allow_invalid_val_deploy):
                test_trades = pd.DataFrame()
                test_metrics = metrics(test_trades, [str(test_month)])
                deploy_name = "ABSTAIN_INVALID_VAL"
                abstained = True
            else:
                test_trades = select_config(test, best_cfg)
                test_metrics = metrics(test_trades, [str(test_month)])
                deploy_name = best_cfg.name
                abstained = False
                if not test_trades.empty:
                    test_trades["test_month"] = str(test_month)
                    all_trades.append(test_trades)
            fold_rows.append(
                {
                    "ticker": ticker,
                    "month": str(test_month),
                    "deploy_config": deploy_name,
                    "val_months": ",".join(val_months),
                    "val_score": float(best_score),
                    "abstained_invalid_val": bool(abstained),
                    **{f"val_{k}": v for k, v in best_metrics.items()},
                    **{f"test_{k}": v for k, v in test_metrics.items()},
                }
            )
            print(
                f"[OPTION_DELTA_WF] {ticker} {test_month} cfg={deploy_name} "
                f"val_pf={best_metrics.get('profit_factor', float('nan')):.3f} "
                f"test_trades={test_metrics.get('trades', 0)} "
                f"test_pf={test_metrics.get('profit_factor', float('nan')):.3f} "
                f"test_pnl={test_metrics.get('pnl_dollars', 0.0):.0f}",
                flush=True,
            )
    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    return trades, folds


def write_summary(output_dir: Path, candidates: pd.DataFrame, trades: pd.DataFrame, folds: pd.DataFrame, metadata: dict) -> None:
    args_meta = metadata.get("args", {})
    expected = month_range(str(args_meta.get("start_month")), str(args_meta.get("end_month")))
    overall = metrics(trades, expected)
    per_ticker = {
        str(ticker): metrics(part, expected)
        for ticker, part in trades.groupby("ticker", sort=True)
    } if not trades.empty else {}
    fixed: dict[str, dict] = {}
    for delta in args_meta.get("delta_targets", []):
        cfg = DeltaConfig(float(delta), 999)
        fixed_trades = select_config(candidates, cfg)
        fixed[f"fixed_delta_{float(delta):.2f}"] = metrics(
            fixed_trades[(fixed_trades["month"].astype(str) >= str(args_meta.get("start_month"))) & (fixed_trades["month"].astype(str) <= str(args_meta.get("end_month")))],
            expected,
        )
    oracle = oracle_best_delta(candidates)
    oracle = oracle[(oracle["month"].astype(str) >= str(args_meta.get("start_month"))) & (oracle["month"].astype(str) <= str(args_meta.get("end_month")))]
    oracle_metrics = metrics(oracle, expected)
    lines = [
        "# Option Delta Walk-Forward From Candidates",
        "",
        "Causal diagnostic: for each ticker/month, select fixed option delta and max trades/day using prior validation months only.",
        "",
        "## Walk-Forward",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        "## Per Ticker",
        "",
        "```json",
        json.dumps(per_ticker, indent=2, allow_nan=True),
        "```",
        "",
        "## Fixed Delta Baselines",
        "",
        "```json",
        json.dumps(fixed, indent=2, allow_nan=True),
        "```",
        "",
        "## Oracle Best Delta",
        "",
        "```json",
        json.dumps(oracle_metrics, indent=2, allow_nan=True),
        "```",
        "",
        "## Fold Configs",
        "",
        "```csv",
        folds.to_csv(index=False),
        "```",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(metadata, indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (output_dir / "metrics.json").write_text(
        json.dumps(
            {
                "overall": overall,
                "per_ticker": per_ticker,
                "fixed_delta": fixed,
                "oracle_best_delta": oracle_metrics,
                "metadata": metadata,
            },
            indent=2,
            allow_nan=True,
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal delta selector over prebuilt option candidate labels.")
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202507")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--min-val-trades", type=int, default=45)
    parser.add_argument("--min-month-trades", type=int, default=15)
    parser.add_argument("--delta-targets", nargs="+", type=float, default=[0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70])
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[999, 12, 8, 4, 2, 1])
    parser.add_argument("--allow-invalid-val-deploy", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = pd.read_parquet(args.candidate_labels)
    candidates["ticker"] = candidates["ticker"].astype(str).str.upper()
    candidates["date"] = candidates["date"].astype(str).str.replace("-", "", regex=False).str[:8]
    candidates["month"] = candidates["date"].str[:6]
    candidates = candidates[candidates["ticker"].isin([str(t).upper() for t in args.tickers])].copy()
    grid = build_grid(args)
    metadata = {"args": vars(args), "grid": [asdict(cfg) for cfg in grid], "candidate_rows": int(len(candidates))}
    trades, folds = run_walkforward(candidates, args, grid)
    if not trades.empty:
        trades.to_csv(output_dir / "option_delta_wf_trades.csv", index=False)
    folds.to_csv(output_dir / "fold_configs.csv", index=False)
    write_summary(output_dir, candidates, trades, folds, metadata)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
